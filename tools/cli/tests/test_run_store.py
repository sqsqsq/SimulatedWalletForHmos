from __future__ import annotations

import json
import os
import shutil
import tracemalloc
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


def _fill_events(store, count, content_chars=1000):
    """Write `count` synthetic events straight to the log, bypassing append_event."""
    content = "x" * content_chars
    with store.events_path.open("w", encoding="utf-8", newline="\n") as handle:
        for seq in range(1, count + 1):
            handle.write(
                json.dumps(
                    {
                        "seq": seq,
                        "timestamp": "now",
                        "run_id": store.run_id,
                        "type": "text",
                        "content": content,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )
    return store.events_path.stat().st_size


def _new_store(workspace_tmp, run_id="run-1"):
    store = run_store.RunStore(workspace_tmp, run_id)
    store.create(
        CliRunRequest(cli="fake", model="fake", prompt="test", cwd=workspace_tmp)
    )
    return store


def test_page_streams_a_large_event_log_instead_of_reading_it_whole(workspace_tmp):
    # A poll must cost the page it returns, not the log it reads. Two parallel
    # workers polling a multi-megabyte log this way is what ran out of memory.
    store = _new_store(workspace_tmp)
    size = _fill_events(store, 5000)
    assert size > 5_000_000

    tracemalloc.start()
    try:
        tracemalloc.reset_peak()
        cursor = 0
        for _ in range(20):
            page = store.page(cursor=cursor, max_events=50, max_chars=100_000)
            cursor = page.next_cursor
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert cursor == 1000, "20 polls x 50 events must have drained 1000 events"
    assert peak < size // 5, f"peak {peak} should stay well under the {size}-byte log"


def test_page_returns_the_same_events_as_before_streaming(workspace_tmp):
    # Regression: streaming changed how the log is read, nothing about paging.
    store = _new_store(workspace_tmp)
    _fill_events(store, 12, content_chars=10)

    first = store.page(cursor=0, max_events=5, max_chars=100_000)
    assert [e.seq for e in first.events] == [1, 2, 3, 4, 5]
    assert first.next_cursor == 5
    assert first.has_more is True

    rest = store.page(cursor=first.next_cursor, max_events=100, max_chars=100_000)
    assert [e.seq for e in rest.events] == list(range(6, 13))
    assert rest.has_more is False


def test_truncated_event_log_reads_short_and_refills(workspace_tmp):
    # No read offset is carried between polls, so a truncated or rotated log
    # needs no recovery step: the next poll simply sees the file as it now is.
    store = _new_store(workspace_tmp)
    _fill_events(store, 40, content_chars=10)
    assert len(store.page(cursor=0, max_events=100, max_chars=100_000).events) == 40

    _fill_events(store, 3, content_chars=10)
    after = store.page(cursor=0, max_events=100, max_chars=100_000)
    assert [e.seq for e in after.events] == [1, 2, 3]

    _fill_events(store, 9, content_chars=10)
    refilled = store.page(cursor=3, max_events=100, max_chars=100_000)
    assert [e.seq for e in refilled.events] == [4, 5, 6, 7, 8, 9]


def test_last_seq_streams_the_log_too(workspace_tmp):
    # append_event seeds its counter from the log once per store; that read is
    # on the same unbounded file and had the same whole-file cost.
    store = _new_store(workspace_tmp)
    _fill_events(store, 2000, content_chars=100)

    tracemalloc.start()
    try:
        tracemalloc.reset_peak()
        event = store.append_event("text", content="next")
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert event.seq == 2001
    assert peak < 1_000_000
