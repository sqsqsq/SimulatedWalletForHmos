from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from tools.cli import run_store
from tools.cli.models import CliRunRequest


ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def workspace_tmp(request):
    parent = ROOT / "output" / "cli-store-tests"
    path = parent / request.node.name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)
    try:
        parent.rmdir()
    except OSError:
        pass


def test_atomic_json_retries_transient_replace_failure(workspace_tmp, monkeypatch):
    target = workspace_tmp / "run.json"
    real_replace = os.replace
    attempts = []

    def flaky_replace(source, destination):
        attempts.append((source, destination))
        if len(attempts) < 4:
            raise PermissionError("simulated Windows sharing violation")
        real_replace(source, destination)

    monkeypatch.setattr(run_store.os, "replace", flaky_replace)

    run_store.atomic_json(
        target,
        {"status": "running"},
        attempts=5,
        retry_delay_sec=0,
    )

    assert target.read_text(encoding="utf-8").find('"running"') > 0
    assert len(attempts) == 4
    assert list(workspace_tmp.glob("run.json.*.tmp")) == []


def test_atomic_json_cleans_temp_after_exhausted_retries(workspace_tmp, monkeypatch):
    target = workspace_tmp / "run.json"

    def blocked_replace(source, destination):
        raise PermissionError("persistent sharing violation")

    monkeypatch.setattr(run_store.os, "replace", blocked_replace)

    try:
        run_store.atomic_json(
            target,
            {"status": "running"},
            attempts=2,
            retry_delay_sec=0,
        )
    except PermissionError:
        pass
    else:
        raise AssertionError("atomic_json must surface persistent write failure")

    assert not target.exists()
    assert list(workspace_tmp.glob("run.json.*.tmp")) == []


def test_terminal_page_reports_unread_event_from_newer_state_snapshot(workspace_tmp):
    store = run_store.RunStore(workspace_tmp, "run-1")
    store.create(
        CliRunRequest(
            cli="fake",
            model="fake",
            prompt="test",
            cwd=workspace_tmp,
        )
    )
    store.events_path.write_text(
        '{"seq":1,"timestamp":"now","run_id":"run-1","type":"text","content":"one"}\n',
        encoding="utf-8",
    )
    store.update(
        status="succeeded",
        last_event_seq=2,
    )

    page = store.page(cursor=1, max_events=10, max_chars=1000)

    assert page.events == []
    assert page.run["status"] == "succeeded"
    assert page.has_more is True
