"""人的原话只认明确指到的一项；旧版本的流程契约不读。"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from ext_workspace import DEV_EXT

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(DEV_EXT / "skills/story/scripts/core"))
from flow import asks, state  # noqa: E402

OPTIONS = [{"no": 1, "key": "plan", "label": "材料够了，往下走"},
           {"no": 2, "key": "more", "label": "还要补料"},
           {"no": 3, "key": "wait", "label": "保持待定"}]

FLOW_CLI = DEV_EXT / "skills" / "story" / "scripts" / "core" / "story_flow.py"


class AReplyPointsOnlyByNumberFormOrLabel(unittest.TestCase):
    def picked(self, reply: str) -> int:
        return asks.pick_explicit(OPTIONS, reply)["no"]

    def test_everyday_numbers_and_keys_do_not_pick(self) -> None:
        for reply in ("不用补，1 份 PRD 够了", "我再等 1 天", "10 月前要交付的那份", "按 plan 走，保持待定"):
            with self.subTest(reply=reply):
                with self.assertRaises(state.FlowError, msg=f"「{reply}」被当成了选择"):
                    asks.pick_explicit(OPTIONS, reply)

    def test_number_forms_and_labels_pick(self) -> None:
        for reply, want in (("1", 1), ("第2项", 2), ("选 3", 3), ("2.", 2), ("1）就这样", 1),
                            ("材料够了，往下走", 1)):
            with self.subTest(reply=reply):
                self.assertEqual(want, self.picked(reply))

    def test_an_unpointed_reply_is_refused_instead_of_picked_for_the_person(self) -> None:
        with self.assertRaises(state.FlowError) as got:
            asks.pick_explicit(OPTIONS, "不用补，1 份 PRD 够了")
        self.assertIn("没有明确选到任何一项", str(got.exception))
        self.assertIn("再问人", str(got.exception))
        with self.assertRaises(state.FlowError) as got:
            asks.pick_explicit(OPTIONS, "选 1，选 2")
        self.assertIn("同时指到了几项", str(got.exception))
        # 模型替人挑一项的旧入口已经退出：选哪一项只由人的原话决定。
        self.assertFalse(hasattr(asks, "map_reply"))
        self.assertNotIn("--chosen", FLOW_CLI.read_text(encoding="utf-8"))


class AnOldContractIsNotRead(unittest.TestCase):
    def test_a_schema_other_than_current_stops_with_a_restart_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "AR" / "story-src" / "story-flow.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"schema": 3, "rounds": []}), encoding="utf-8")
            with self.assertRaises(state.FlowError) as got:
                state.load(root)
            message = str(got.exception)
            self.assertIn("不是当前版本的流程契约", message)
            self.assertIn("本版不接续旧版现场", message)
            self.assertIn("也不自动迁移、不改写这个目录", message)
            self.assertIn("要按旧版收口就留在原版", message)
            self.assertIn("为新需求另跑 `init`", message)


if __name__ == "__main__":
    unittest.main()