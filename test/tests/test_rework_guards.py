"""人的原话只认整句选择；旧版本的流程契约不读。"""
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

    def refused(self, reply: str) -> str:
        with self.assertRaises(state.FlowError, msg=f"「{reply}」被当成了选择") as got:
            asks.pick_explicit(OPTIONS, reply)
        return str(got.exception)

    def test_everyday_numbers_and_keys_do_not_pick(self) -> None:
        for reply in ("不用补，1 份 PRD 够了", "我再等 1 天", "10 月前要交付的那份", "按 plan 走，保持待定",
                      "第 2 份材料还没到，请先等等。", "等第 2 次会议开完再说。",
                      "2.5 个月后交付，先按第 2 次评审意见改。"):
            with self.subTest(reply=reply):
                self.refused(reply)

    def test_number_forms_and_labels_pick(self) -> None:
        for reply, want in (("1", 1), ("第2项", 2), ("选 3", 3), ("2.", 2), ("1）就这样", 1),
                            ("2）就这样吧", 2), ("材料够了，往下走", 1), ("材料够了，往下走。", 1),
                            ("选 2，还要补料", 2), ("2，还要补料", 2)):
            with self.subTest(reply=reply):
                self.assertEqual(want, self.picked(reply))

    def test_a_question_mark_does_not_become_a_choice(self) -> None:
        """「选2？」还在问这个选项是什么意思，不是「选2」；附言里没有决定也不签认。"""
        for reply in ("选2？", "选2？我还没有决定，材料还没齐。", "1）要等材料到了才这样",
                      "材料够了，往下走？", "材料够了，往下走，但先别动"):
            with self.subTest(reply=reply):
                self.refused(reply)

    def test_a_compound_choice_needs_every_clause_and_one_affirmation(self) -> None:
        self.assertEqual(2, self.picked("不选 1，选 2"))
        message = self.refused("选 1，选 2")
        self.assertIn("同时指到了几项", message)
        self.refused("不选 1")
        self.refused("选 2，不选 2")

    def test_an_unpointed_reply_is_refused_instead_of_picked_for_the_person(self) -> None:
        message = self.refused("不用补，1 份 PRD 够了")
        self.assertIn("没有明确选到任何一项", message)
        self.assertIn("再问人", message)
        # 模型替人挑一项的旧入口已经退出：选哪一项只由人的原话决定。
        self.assertFalse(hasattr(asks, "map_reply"))
        self.assertNotIn("--chosen", FLOW_CLI.read_text(encoding="utf-8"))

    def test_the_negation_word_list_branch_is_gone(self) -> None:
        """旧的分句比对器退场：不再有先丢标点、拆句、忽略不认识分句的词表实现。"""
        for gone in ("NEGATION", "_negated", "_affirmed", "CLAUSE", "PUNCT"):
            self.assertFalse(hasattr(asks, gone), f"asks 里还留着旧比对器 {gone}")
        body = (DEV_EXT / "skills/story/scripts/core/flow/asks.py").read_text(encoding="utf-8")
        self.assertNotIn("NEGATION", body)
        self.assertNotIn("finditer", body)


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