from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.cli.adapters import get_adapter
from tools.cli.adapters.base import AdapterEvent


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class AdapterTests(unittest.TestCase):
    def parse(self, name: str, fixture: str | None = None):
        adapter = get_adapter(name)
        events = []
        for line in (FIXTURES / f"{fixture or name}.jsonl").read_text(encoding="utf-8").splitlines():
            events.extend(adapter.parse(json.loads(line)))
        return events

    def test_opencode(self) -> None:
        events = self.parse("opencode")
        self.assertIn("ses-open", [event.session_id for event in events])
        self.assertIn("open text", [event.content for event in events])
        self.assertIn("tool", [event.type for event in events])
        tool = next(event for event in events if event.type == "tool")
        self.assertEqual("completed", tool.tool_status)
        self.assertEqual("done", tool.tool_output)
        self.assertIn("usage", [event.type for event in events])

    def test_cursor_agent(self) -> None:
        events = self.parse("cursor_agent")
        self.assertIn("ses-cursor", [event.session_id for event in events])
        self.assertIn("cursor thought", [event.content for event in events])
        self.assertIn("cursor text", [event.content for event in events])
        self.assertIn("tool", [event.type for event in events])

    def test_claude(self) -> None:
        events = self.parse("claude")
        self.assertIn("ses-claude", [event.session_id for event in events])
        self.assertIn("claude thought", [event.content for event in events])
        self.assertIn("claude text", [event.content for event in events])
        self.assertIn("tool", [event.type for event in events])

    def test_codex(self) -> None:
        events = self.parse("codex")
        self.assertIn("thread-codex", [event.session_id for event in events])
        self.assertIn("codex text", [event.content for event in events])
        self.assertIn("tool", [event.type for event in events])
        tool = next(event for event in events if event.type == "tool")
        self.assertEqual("completed", tool.tool_status)
        self.assertEqual("Python 3", tool.tool_output)
        self.assertIn("usage", [event.type for event in events])

    def test_dsh(self) -> None:
        events = self.parse("dsh")
        self.assertIn("ses-dsh", [event.session_id for event in events])
        self.assertIn("dsh thought", [event.content for event in events])
        self.assertIn("SMOKE-OK", [event.content for event in events])
        usage = next(event for event in events if event.type == "usage")
        self.assertEqual(7789, usage.usage["input"])
        self.assertEqual(44, usage.usage["output"])
        self.assertEqual(8729, usage.usage["context_total"])
        self.assertEqual(896, usage.usage["cache_read"])

    def test_dsh_tool_calls_pair_with_their_results(self) -> None:
        # 夹具剪自 2026-10-20 真实 dsh 运行：两张图并发读取都失败、一次 subagent、一个被截断的读取
        tools = [event for event in self.parse("dsh", "dsh_tools") if event.type == "tool"]
        lines = [
            json.loads(line)
            for line in (FIXTURES / "dsh_tools.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        raw = [line for line in lines if line["type"] in {"tool_call", "tool_result"}]
        self.assertEqual(len(raw), len(tools))
        for line, event in zip(raw, tools):
            if line["type"] == "tool_call":
                expected = AdapterEvent(
                    "tool",
                    content=line["tool"],
                    tool_call_id=line["callId"],
                    tool_name=line["tool"],
                    tool_status="started",
                    tool_input=line["input"],
                    source_truncated=line.get("truncated") is True,
                )
            else:
                expected = AdapterEvent(
                    "tool",
                    content=line["result"],
                    tool_call_id=line["callId"],
                    tool_status=line["status"],
                    tool_output=line["result"],
                    source_truncated=line.get("truncated") is True,
                )
            self.assertEqual(expected, event)
        # 两个读图调用都先开出、再各自收到失败结果，失败不投影为完成
        first, second, first_result, second_result = tools[:4]
        self.assertEqual(
            [first.tool_call_id, second.tool_call_id],
            [first_result.tool_call_id, second_result.tool_call_id],
        )
        self.assertNotEqual(first.tool_call_id, second.tool_call_id)
        self.assertEqual(["error", "error"], [first_result.tool_status, second_result.tool_status])
        subagent = next(event for event in tools if event.tool_name == "subagent")
        self.assertIn("prompt", subagent.tool_input)
        ends = {event.tool_call_id: event for event in tools if event.tool_status != "started"}
        self.assertTrue(ends[subagent.tool_call_id].tool_output.startswith("started subagent "))

    def test_dsh_tool_results_keep_what_the_provider_said(self) -> None:
        adapter = get_adapter("dsh")
        result = {"type": "tool_result", "callId": "c-1", "status": "cancelled", "result": "stopped"}
        # 结果先于调用到达（例如续跑的新进程）也独立成立：适配器不靠前一次解析补名字
        alone = adapter.parse(result)
        adapter.parse({"type": "tool_call", "callId": "c-1", "tool": "pwsh", "input": {"command": "x"}})
        self.assertEqual(alone, adapter.parse(result))
        self.assertEqual("cancelled", alone[0].tool_status)
        self.assertIsNone(alone[0].tool_name)
        no_status = adapter.parse({"type": "tool_result", "callId": "c-2"})[0]
        self.assertEqual(("unknown", None), (no_status.tool_status, no_status.tool_output))
        structured = adapter.parse(
            {"type": "tool_result", "callId": "c-3", "status": "completed", "result": {"n": 1}}
        )[0]
        self.assertEqual('{"n": 1}', structured.tool_output)
        self.assertEqual([], [e for e in adapter.parse({"type": "plan_update"}) if e.type == "tool"])

    def test_dsh_stream_shortening_is_flagged_and_other_hosts_stay_unknown(self) -> None:
        # 夹具里那条被 dsh 投影截断的读取结果带 truncated=true；其余都没截
        flags = [event.source_truncated for event in self.parse("dsh", "dsh_tools") if event.type == "tool"]
        self.assertEqual(1, flags.count(True))
        self.assertTrue(all(flag in (True, False) for flag in flags))
        adapter = get_adapter("dsh")
        text = adapter.parse({"type": "text", "text": "很长的回复", "truncated": True})
        self.assertEqual([("text", "很长的回复", True)], [(e.type, e.content, e.source_truncated) for e in text])
        for name in ("opencode", "codex", "claude"):
            with self.subTest(provider=name):
                self.assertTrue(all(e.source_truncated is None for e in self.parse(name)))

    def test_dsh_error_turn(self) -> None:
        adapter = get_adapter("dsh")
        events = adapter.parse(
            {
                "type": "status",
                "phase": "turn_end",
                "turn": 1,
                "reason": {
                    "kind": "error",
                    "error": {
                        "message": "no API key for provider route \"deepseek-official\"",
                        "code": "MISSING_CREDENTIAL",
                    },
                },
            }
        )
        self.assertEqual(1, len(events))
        self.assertEqual("error", events[0].type)
        self.assertIn("no API key", events[0].content)


if __name__ == "__main__":
    unittest.main()
