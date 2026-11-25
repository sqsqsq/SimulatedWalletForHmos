"""流程契约的材料关卡取值读自章节合同：读不到要出声，合法记录照判，每条记录是完整的人签；
设计问答的原话记录只存证据，旧 schema 与旧范围/会议裁决记录明确不接续。"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from ext_workspace import DEV_EXT

REPO_ROOT = Path(__file__).resolve().parents[2]
FEATURE = "AR90001"

MINIMAL_FLOW = {
    "schema": 7,
    "feature": FEATURE,
    "status": "gathering",
    "rounds": [{"round": 1, "gates": []}],
}


class TestTheGateChoicesComeFromTheContract(unittest.TestCase):
    """第一级关卡的值域读自章节合同：**读不到要出声**，不退化成空集。

    退化成空集的话，每一条合法的 `material_scope` 记录都会被判成「chosen 非法」，
    作者拿着一份合法契约去改它，而坏掉的是合同的读取路径。
    """

    EXT = DEV_EXT / "base" / "skills" / "story"

    def setUp(self) -> None:
        self.node = shutil.which("node")
        if self.node is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # 按机制自己的相对定位复制一份：flow/check 从它自己的位置找 contracts/
        self.skill = Path(self._tmp.name) / "story"
        shutil.copytree(self.EXT / "scripts", self.skill / "scripts")
        shutil.copytree(self.EXT / "contracts", self.skill / "contracts")
        self.feature_root = Path(self._tmp.name) / "doc" / "features" / FEATURE
        (self.feature_root / "AR" / "story-src").mkdir(parents=True)
        flow = dict(MINIMAL_FLOW)
        flow["rounds"] = [{
            "round": 1, "materials": {"digest": "d1"},
            "positioning": {"scope_text": "本 AR 承载提交与回执", "sr_related_ars": []},
            "gates": [{"gate": "material_scope", "chosen": "confirm_scope",
                       "options": [{"key": "confirm_scope"}], "outcome": "accepted",
                       "at": "2026-09-12T00:00:00", "by": "human", "ask_id": "a1", "reply": "1"}],
        }]
        (self.feature_root / "AR" / "story-src" / "story-flow.json").write_text(
            json.dumps(flow, ensure_ascii=False, indent=2), encoding="utf-8")

    def problems(self) -> list[str]:
        script = (
            "import {pathToFileURL} from 'node:url';"
            "const m=await import(pathToFileURL(process.argv[1]).href);"
            "console.log(JSON.stringify(m.flowProblems(process.argv[2])));")
        proc = subprocess.run(
            [self.node, "--input-type=module", "-e", script, "--",
             str(self.skill / "scripts" / "core" / "flow" / "check.mjs"), str(self.feature_root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_a_legal_contract_judges_the_choice(self) -> None:
        self.assertEqual([], self.problems())

    def test_a_broken_contract_is_reported_not_swallowed(self) -> None:
        (self.skill / "contracts" / "story-chapters.json").write_text("{ 坏了", encoding="utf-8")
        problems = self.problems()
        self.assertTrue(any("章节合同" in p for p in problems), problems)
        self.assertFalse(any("chosen 非法" in p for p in problems),
                         f"合同读不到却去说人的选择非法：{problems}")

    def flow_path(self) -> Path:
        return self.feature_root / "AR" / "story-src" / "story-flow.json"

    def edit_flow(self, mutate) -> None:
        data = json.loads(self.flow_path().read_text(encoding="utf-8"))
        mutate(data)
        self.flow_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_the_flow_constants_come_from_the_contract(self) -> None:
        """schema、关卡名、整体承载键只在合同的 `flow` 里：合同缺了它就判不了，不退回写死的值。"""
        contract = self.skill / "contracts" / "story-chapters.json"
        data = json.loads(contract.read_text(encoding="utf-8"))
        del data["flow"]
        contract.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        problems = self.problems()
        self.assertTrue(any("flow" in p for p in problems), problems)
        self.assertFalse(any("schema 为" in p for p in problems), "合同读不到却拿写死的 schema 去判")

    def test_shape_only_fields_are_not_judged(self) -> None:
        """时间戳、outcome 值域、被拒的 reason：写入侧已保证，手改成错形状也不改变流程走向。"""
        def mutate(data):
            gates = data["rounds"][0]["gates"]
            del gates[0]["at"]
            gates.insert(0, {"gate": "material_scope", "chosen": "supplied",
                             "options": [{"key": "supplied"}], "outcome": "rejected",
                             "by": "human", "ask_id": "a0", "reply": "放好了"})
        self.edit_flow(mutate)
        self.assertEqual([], self.problems())

    def test_every_gate_record_is_a_full_human_sign(self) -> None:
        """人签缺问法编号、原话或写成模型签的，门禁点名——关卡记录只由 decide 在问过之后写。"""
        for field, value in (("by", "ai"), ("ask_id", ""), ("reply", "")):
            with self.subTest(field=field):
                def mutate(data, field=field, value=value):
                    data["rounds"][0]["gates"][0][field] = value
                self.setUp()
                self.edit_flow(mutate)
                self.assertTrue(any("不是一笔完整的人签" in p for p in self.problems()))

    def test_a_choice_outside_the_options_is_still_caught(self) -> None:
        """改了 chosen 而没改 options——这一条决定后续流程，手改也要抓。"""
        def mutate(data):
            data["rounds"][0]["gates"][0]["chosen"] = "by_screen"
        self.edit_flow(mutate)
        problems = self.problems()
        self.assertTrue(any("不在 options 里" in p for p in problems), problems)

    def test_an_old_schema_contract_is_not_continued(self) -> None:
        """schema6 旧现场：明确报不接续，不自动迁移，也不拿新规则继续判。"""
        def mutate(data):
            data["schema"] = 6
        self.edit_flow(mutate)
        problems = self.problems()
        self.assertTrue(any("不接续" in p and "init" in p for p in problems), problems)

    def test_old_scope_and_meeting_gate_records_are_not_continued(self) -> None:
        """旧范围/会议裁决关卡与份表字段：新契约没有它们，旧现场不接续。"""
        def mutate(data):
            data["split"] = {"decided": "carry_all"}
            data["rounds"][0]["gates"].append(
                {"gate": "meeting", "chosen": "a", "options": [{"key": "a"}],
                 "outcome": "accepted", "by": "human", "ask_id": "m1", "reply": "1"})
            data["rounds"][0]["scope_options"] = [{"key": "carry_all"}]
        self.edit_flow(mutate)
        problems = self.problems()
        self.assertTrue(any("split" in p for p in problems), problems)
        self.assertTrue(any("scope_options" in p for p in problems), problems)
        self.assertTrue(any("gate 非法" in p for p in problems), problems)

    def test_an_answer_record_is_evidence_only(self) -> None:
        """设计问答原话记录：必要的问法、题号、问题、原话、时刻与出处缺一不可，带目标/版本字段要报。"""
        answer = {"ask_id": "b1", "item_id": "Q1", "question": "要不要重试？",
                  "options": ["允许", "保持待定"], "reply": "允许", "at": "2026-09-12T00:00:00",
                  "source_ref": "RR/prd.md#3"}

        def mutate(data):
            data["rounds"][0]["answers"] = [dict(answer)]
        self.edit_flow(mutate)
        self.assertEqual([], self.problems())

        def drop_source(data):
            data["rounds"][0]["answers"][0].pop("source_ref")
        self.edit_flow(drop_source)
        self.assertTrue(any("source_ref" in p for p in self.problems()))

        def add_target(data):
            data["rounds"][0]["answers"][0]["target_ref"] = "view:logical/node:x"
        self.edit_flow(add_target)
        self.assertTrue(any("target_ref" in p for p in self.problems()))


if __name__ == "__main__":
    unittest.main()
