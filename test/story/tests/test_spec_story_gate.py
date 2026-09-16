"""story 是 spec 阶段的第三份产物——spec 门禁核它成没成文。

批次 3 曾把成文挪到 spec 之后当独立一步，触发条件写「spec 闭环之后、归档之前」。
本地单没有归档，这个时点不存在，于是没有任何阶段边界要求它：实测一个 Case
四个阶段 harness 全 pass，而 `AR/story.md` 从来没被写出来。

判据查**登记态**不查文件在不在：手写一份简版照样能骗过「文件存在」——
基线就是这么判的，它的注释里自己承认过。`story_flow.py story` 登记前会重跑
`story-build check`，登记成功即九项判据都过了。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FLOW_CHECK = (REPO_ROOT / "doc" / "extensions" / "skills" / "story"
              / "scripts" / "core" / "flow" / "check.mjs")
FEATURE = "AR90001"

MINIMAL_FLOW = {
    "schema": 3,
    "feature": FEATURE,
    "status": "complete",
    "rounds": [{"round": 1, "gates": []}],
}


class TestSpecStoryGate(unittest.TestCase):
    def setUp(self) -> None:
        self.node = shutil.which("node")
        if self.node is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.feature_root = Path(self._tmp.name) / "doc" / "features" / FEATURE
        (self.feature_root / "AR" / "story-src").mkdir(parents=True)

    def write_flow(self, status: str | None) -> None:
        """status=None 表示这个 feature 没走过 /story（没有契约文件）。"""
        path = self.feature_root / "AR" / "story-src" / "story-flow.json"
        if status is None:
            path.unlink(missing_ok=True)
            return
        flow = dict(MINIMAL_FLOW, status=status)
        path.write_text(json.dumps(flow, ensure_ascii=False, indent=2), encoding="utf-8")

    def problems(self) -> list[str]:
        script = (
            "import {pathToFileURL} from 'node:url';"
            "const m=await import(pathToFileURL(process.argv[1]).href);"
            "console.log(JSON.stringify(m.storyProduced(process.argv[2])));")
        proc = subprocess.run(
            [self.node, "--input-type=module", "-e", script, "--",
             str(FLOW_CHECK), str(self.feature_root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_not_written_is_blocked_and_says_how(self) -> None:
        self.write_flow("complete")
        problems = self.problems()
        self.assertEqual(len(problems), 1)
        self.assertIn("缺叙事件", problems[0])
        self.assertIn("story_flow.py story", problems[0], "报错要带上登记命令")

    def test_registered_passes(self) -> None:
        self.write_flow("story_written")
        self.assertEqual(self.problems(), [])

    def test_feature_without_story_flow_is_untouched(self) -> None:
        """没走 /story 的 feature 不受本判据影响——扩展不给它凭空加要求。"""
        self.write_flow(None)
        self.assertEqual(self.problems(), [])

    def test_broken_contract_says_it_cannot_tell(self) -> None:
        """读不出状态就判不了成文态：既不当作没成文，也不当作成文了。"""
        (self.feature_root / "AR" / "story-src" / "story-flow.json").write_text("{ 坏的", encoding="utf-8")
        problems = self.problems()
        self.assertEqual(len(problems), 1)
        self.assertIn("不是合法 JSON", problems[0])


class TestTheGateChoicesComeFromTheContract(unittest.TestCase):
    """第一级关卡的值域读自章节合同：**读不到要出声**，不退化成空集。

    退化成空集的话，每一条合法的 `material_scope` 记录都会被判成「chosen 非法」，
    作者拿着一份合法契约去改它，而坏掉的是合同的读取路径。
    """

    EXT = REPO_ROOT / "doc" / "extensions" / "skills" / "story"

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
            "scope_options": [{"key": "carry_all", "label": "按当前范围整体承载"}],
            "gates": [{"gate": "material_scope", "chosen": "confirm_scope",
                       "options": [{"key": "confirm_scope"}], "outcome": "accepted",
                       "at": "2026-09-12T00:00:00", "by": "human"},
                      {"gate": "scope_decision", "chosen": "carry_all",
                       "options": [{"key": "carry_all"}], "outcome": "accepted",
                       "at": "2026-09-12T00:00:00", "by": "human"}],
        }]
        flow["design_generated_at"] = "2026-09-12T00:00:00"
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
        """签名人、时间戳、outcome 值域、被拒的 reason：写入侧已保证，手改成错形状也不改变流程走向。"""
        def mutate(data):
            gates = data["rounds"][0]["gates"]
            gates[0]["by"] = "ai"
            del gates[0]["at"]
            gates.insert(0, {"gate": "material_scope", "chosen": "supplied",
                             "options": [{"key": "supplied"}], "outcome": "rejected"})
        self.edit_flow(mutate)
        self.assertEqual([], self.problems())

    def test_a_choice_outside_the_options_is_still_caught(self) -> None:
        """改了 chosen 而没改 options——这一条决定后续流程，手改也要抓。"""
        def mutate(data):
            data["rounds"][0]["gates"][1]["chosen"] = "by_screen"
        self.edit_flow(mutate)
        problems = self.problems()
        self.assertTrue(any("不在 options 里" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
