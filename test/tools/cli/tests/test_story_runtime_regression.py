from __future__ import annotations

import json
import os
import shutil
import tracemalloc
import hashlib
import unittest
from tools.cli.runner import classify_failure
from tools.cli.registry import DEFAULT_CONFIG_PATH
from pathlib import Path

import pytest

from tools.cli import run_store
from tools.cli.models import CliRunRequest


ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def workspace_tmp(request):
    parent = ROOT / "output" / "scratch" / "cli-runtime-local-tests"
    path = parent / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:12]
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)
    try:
        parent.rmdir()
    except OSError:
        pass








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


class StoryArgvRegression(unittest.TestCase):
    def test_prompt_is_the_last_argument(self) -> None:
        """位置参数必须排在所有选项之后，否则多行 prompt 会把后续选项吃掉。

        实证（AR90004 三跑）：`opencode run [message..]` 的 positional 是 **array**。
        配置曾写成 `run {prompt} --dir … --format json`——单行 prompt 相安无事，
        换成多行长 prompt（真实用例就是多行）后，yargs 把后面的选项一并吸进 message，
        **`--format json` 从未生效**：输出退回 TUI 文本，于是
        ①`model` 流全空（TEST.md 要求「必须读 model 流」，通道等于没有）；
        ②`session_id` 拿不到 → 无法 `resume` → 驱动器无法回答关卡菜单 →
        单轮会话停在 S3、产物全无。三轮实测全部卡死在这里，一度被误判成 skill 缺陷。

        prompt 放末尾即按构造消除：选项在它之前已经解析完。

        **只约束 opencode**：这条是从它的 yargs array positional 实证来的，
        是否适用于别家取决于各自的参数解析器（claude 的 `-p`、codex 的 exec 都另有形态）。
        把一次实证当普适规则去套，是另一种打补丁——别家出问题时按各自的证据再加。
        """
        raw = json.loads(Path(DEFAULT_CONFIG_PATH).read_text(encoding="utf-8"))
        for pname, profile in raw["clis"]["opencode"]["profiles"].items():
            for key in ("args", "resume_args"):
                argv = profile.get(key)
                if not argv or "{prompt}" not in argv:
                    continue
                self.assertEqual(
                    argv[-1], "{prompt}",
                    f"opencode.{pname}.{key}: {{prompt}} 是 array positional，必须排在末尾，"
                    f"否则多行 prompt 会吞掉它后面的选项（实为 {argv}）")


class StoryFailureRegression(unittest.TestCase):
    def test_provider_content_inspection_is_classified_without_claiming_all_400s(self) -> None:
        rejected = (
            '"<400> InternalError.Algo.DataInspectionFailed: '
            'Output data may contain inappropriate content."'
        )
        self.assertEqual("content_policy_rejected", classify_failure(rejected).value)
        self.assertEqual("command_failed", classify_failure("400 bad request: invalid field").value)

    def test_angled_401_is_auth_required(self) -> None:
        self.assertEqual("auth_required", classify_failure("<401> Unauthorized").value)
