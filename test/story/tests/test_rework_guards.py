"""人签只认人的原话指到的那一项；旧版本的流程契约不读。"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "doc/extensions/skills/story/scripts/core"))
from flow import asks, state  # noqa: E402

OPTIONS = [{"no": 1, "key": "plan", "label": "材料够了，往下走"},
           {"no": 2, "key": "more", "label": "还要补料"},
           {"no": 3, "key": "wait", "label": "保持待定"}]


class AReplyPointsOnlyByNumberFormOrLabel(unittest.TestCase):
    def hits(self, reply: str) -> list[int]:
        return [o["no"] for o in OPTIONS if asks._marks(o, reply)]

    def test_everyday_numbers_and_keys_do_not_pick(self) -> None:
        for reply in ("不用补，1 份 PRD 够了", "我再等 1 天", "10 月前要交付的那份"):
            with self.subTest(reply=reply):
                self.assertEqual([], self.hits(reply))
        self.assertEqual([3], self.hits("按 plan 走，保持待定"), "键 plan 被当成了选择")

    def test_number_forms_and_labels_pick(self) -> None:
        for reply, want in (("1", [1]), ("第2项", [2]), ("选 3", [3]), ("2.", [2]), ("1）就这样", [1]),
                            ("材料够了，往下走", [1])):
            with self.subTest(reply=reply):
                self.assertEqual(want, self.hits(reply))

    def test_an_unpointed_reply_needs_chosen(self) -> None:
        with self.assertRaises(state.FlowError):
            asks.map_reply(OPTIONS, "不用补，1 份 PRD 够了", None, None)
        pick, how = asks.map_reply(OPTIONS, "不用补，1 份 PRD 够了", "1", None)
        self.assertEqual((1, "model"), (pick["no"], how))


class AnOldContractIsNotRead(unittest.TestCase):
    def test_a_schema_other_than_current_stops_with_a_restart_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "AR" / "story-src" / "story-flow.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"schema": 3, "rounds": []}), encoding="utf-8")
            with self.assertRaises(state.FlowError) as got:
                state.load(root)
            self.assertIn("不是当前版本的流程契约", str(got.exception))
            self.assertIn("从 init 重新起单", str(got.exception))


if __name__ == "__main__":
    unittest.main()
