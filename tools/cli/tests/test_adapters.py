from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.cli.adapters import get_adapter


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class AdapterTests(unittest.TestCase):
    def parse(self, name: str):
        adapter = get_adapter(name)
        events = []
        for line in (FIXTURES / f"{name}.jsonl").read_text(encoding="utf-8").splitlines():
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


if __name__ == "__main__":
    unittest.main()
