"""用例终点在真实工程上的观测：到了就闭合，没到就说清缺在哪（test/scripts/end_target.py）。

用 demo Framework 与夹具蓝图（`wallet-balance-refresh`，一个施工单位）在临时工程里走原生入口：
蓝图终点看准入与评审投影，设计交接看活动施工单位的原生设计判定，阶段终点逐施工单位看原生范围与完成回执；
需求交付终点复用真实的「审查 → 登记 → 交付门」正常链。需求与蓝图异名，只凭需求流程契约的设计关联找蓝图。
多施工单位的汇总只替换原生观测的结果，核扩展这一侧怎么消费：有一个没到，整单就没到。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_knowledge_task import BLUEPRINT, make_project, prepare  # noqa: E402  —— 它把 test/scripts 放进导入路径
from test_verifier_report_protocol import STORY_BUILD as DEV_STORY_BUILD, TheStoryIsReviewedRegisteredAndDeliveredCase  # noqa: E402
import end_target  # noqa: E402
from run_case import phase_evidence_complete  # noqa: E402

STORY_BUILD = "doc/extensions/skills/story/scripts/core/story-build.mjs"
UNIT = "balance-refresh"

RENDER = """
import * as fs from 'node:fs';
import * as path from 'node:path';
import { pathToFileURL } from 'node:url';
const [root, blueprint] = process.argv.slice(1);
const { loadNative } = await import(pathToFileURL(path.join(root, 'doc/extensions/hooks/shared/framework-access.mjs')).href);
const native = loadNative(root);
const loaded = native.module('scripts/utils/component-blueprint-path.ts').loadCanonicalBlueprint(native.root, blueprint);
const { renderBlueprintReviewMarkdown } = native.module('scripts/utils/blueprint-review-projection.ts');
fs.writeFileSync(path.join(path.dirname(loaded.canonicalPath), 'component-blueprint.review.md'),
  renderBlueprintReviewMarkdown(loaded.blueprint, loaded.artifactSha256));
"""


def observe(root: Path, end_at: dict, *, feature: str = "REQ-DESIGN", blueprint: str | None = BLUEPRINT,
            story_build: str = STORY_BUILD) -> dict:
    return end_target.observe(root, "doc/features", feature, end_at, case={"blueprint_id": blueprint} if blueprint else None,
                              story_build=story_build, receipt=phase_evidence_complete)


def close_phase(unit_root: Path, phase: str) -> None:
    """一个阶段的完成凭证：trace、summary（PASS 且正式收口）、verifier 报告与完成回执。"""
    reports = unit_root / phase / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "trace.json").write_text("{}", encoding="utf-8")
    (reports / "verifier.report.md").write_text("PASS", encoding="utf-8")
    (reports / "summary.json").write_text(json.dumps({"verdict": "PASS", "receipt_status": "passed",
                                                      "closure_status": "closed"}), encoding="utf-8")
    (unit_root / phase / "phase-completion-receipt.md").write_text("ok", encoding="utf-8")


class DesignEndpointsOnTheRealBlueprint(unittest.TestCase):
    """范围还没冻结的真实蓝图：准入与投影、设计交接、阶段终点的缺口。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = make_project(root=Path(cls._tmp.name) / "p")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_blueprint_needs_its_review_projection(self) -> None:
        before = observe(self.root, {"kind": "blueprint"})
        self.assertFalse(before["reached"])
        self.assertTrue(any("评审投影还没生成" in m for m in before["missing"]), before["missing"])
        self.assertEqual([], before["units"], "蓝图终点不看施工单位")
        proc = subprocess.run(["node", "--input-type=module", "-e", RENDER, str(self.root), BLUEPRINT],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, proc.returncode, proc.stderr[-600:])
        after = observe(self.root, {"kind": "blueprint"})
        self.assertTrue(after["reached"], after["missing"])

    def test_design_handoff_lists_each_unit_with_its_verdict(self) -> None:
        facts = observe(self.root, {"kind": "design_handoff"})
        self.assertTrue(facts["reached"], facts["missing"])
        self.assertEqual([UNIT], [u["change_unit_id"] for u in facts["units"]])
        unit = facts["units"][0]
        self.assertEqual("constructable", unit["design"])
        self.assertEqual(f"doc/features/{BLUEPRINT}/{UNIT}", unit["feature_path"])
        self.assertTrue(unit["feature_id"].startswith("cu-"))

    def test_a_phase_end_before_freezing_names_the_scope(self) -> None:
        facts = observe(self.root, {"kind": "phase", "phase": "plan"})
        self.assertFalse(facts["reached"])
        self.assertEqual({"spec", "plan"}, set(facts["units"][0]["phases"]))
        self.assertTrue(all("执行范围还没冻结" in m for m in facts["missing"]), facts["missing"])

    def test_the_link_finds_a_differently_named_blueprint(self) -> None:
        """需求名与蓝图名不同：只凭流程契约的设计关联找蓝图，没有关联就说缺关联，不按目录名猜。"""
        self.assertIn("还没有设计关联", observe(self.root, {"kind": "design_handoff"}, blueprint=None)["missing"][0])
        flow = self.root / "doc" / "features" / "REQ-DESIGN" / "AR" / "story-src" / "story-flow.json"
        flow.parent.mkdir(parents=True, exist_ok=True)
        flow.write_text(json.dumps({"design_binding": {"blueprint_id": BLUEPRINT}}), encoding="utf-8")
        try:
            facts = observe(self.root, {"kind": "design_handoff"}, blueprint=None)
            self.assertEqual(BLUEPRINT, facts["blueprint_id"])
            self.assertTrue(facts["reached"], facts["missing"])
        finally:
            shutil.rmtree(self.root / "doc" / "features" / "REQ-DESIGN")

    def test_no_unit_is_a_design_preparation_gap(self) -> None:
        """准入的蓝图还没有施工单位：设计交接没到，缺口是设计准备，不是某个阶段。"""
        copy = Path(self._tmp.name) / "zero"
        shutil.copytree(self.root, copy, symlinks=True)
        shutil.rmtree(copy / "doc" / "features" / BLUEPRINT / UNIT)
        facts = observe(copy, {"kind": "design_handoff"})
        self.assertFalse(facts["reached"])
        self.assertEqual([], facts["units"])
        self.assertTrue(any("还没有活动施工单位" in m for m in facts["missing"]), facts["missing"])


class ThePhaseEndAfterFreezing(unittest.TestCase):
    """范围冻结之后：每个施工单位的每个负责阶段要有正式收口的完成凭证。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = make_project(root=Path(cls._tmp.name) / "p")
        prepare(cls.root, "freeze")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_each_open_phase_is_named_then_receipts_close_it(self) -> None:
        end = {"kind": "phase", "phase": "plan"}
        facts = observe(self.root, end)
        self.assertFalse(facts["reached"])
        self.assertEqual({"spec": "open", "plan": "open"}, {p: r["state"] for p, r in facts["units"][0]["phases"].items()})
        self.assertTrue(any(m.startswith(f"施工单位 {UNIT} 的 spec") and "完成回执" in m for m in facts["missing"]),
                        facts["missing"])
        unit_root = self.root / facts["units"][0]["feature_path"]
        close_phase(unit_root, "spec")
        half = observe(self.root, end)
        self.assertFalse(half["reached"])
        self.assertEqual("closed", half["units"][0]["phases"]["spec"]["state"])
        close_phase(unit_root, "plan")
        self.assertTrue(observe(self.root, end)["reached"])


class OneUnitShortIsNotTheWholeRequirement(unittest.TestCase):
    """多个施工单位：逐个列身份与结论，有一个没到整单就没到。原生观测结果由这里给出，只核扩展这一侧的汇总。"""

    NATIVE = {"blueprint": {"status": "ok", "admitted": True, "projection": "valid", "issues": []}, "problems": [], "units": [
        {"change_unit_id": "a", "feature_id": "cu-a", "feature_path": "doc/features/bp/a",
         "design": {"verdict": "constructable", "issues": []},
         "phases": {"spec": {"status": "ok", "scope": "frozen", "issues": [], "required_outputs": []}}},
        {"change_unit_id": "b", "feature_id": "cu-b", "feature_path": "doc/features/bp/b",
         "design": {"verdict": "constructable", "issues": []},
         "phases": {"spec": {"status": "ok", "scope": "frozen", "issues": [], "required_outputs": ["acceptance.yaml"]}}}]}

    def test_the_unit_that_is_short_is_named(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(end_target, "observe_native", return_value=self.NATIVE):
            facts = end_target.observe(Path(tmp), "doc/features", "REQ", {"kind": "phase", "phase": "spec"},
                                       case={"blueprint_id": "bp"}, story_build=STORY_BUILD, receipt=phase_evidence_complete)
        self.assertFalse(facts["reached"])
        self.assertEqual({"a": "reused", "b": "open"}, {u["change_unit_id"]: u["phases"]["spec"]["state"] for u in facts["units"]})
        self.assertEqual(1, len(facts["missing"]))
        self.assertIn("施工单位 b 的 spec", facts["missing"][0])
        self.assertEqual(("b", "spec"), end_target.first_open(facts))


class TheStoryEndIsTheDeliveryGate(TheStoryIsReviewedRegisteredAndDeliveredCase):
    """需求交付终点：登记过成文，且只读交付门通过；三份文件在不在不算。

    这份夹具工程只装了审查机制，交付门用开发源的入口按 `--project-root` 跑（与交付门自己的测试同一个跑法）。"""

    def test_unregistered_is_not_delivered_and_delivered_is_reached(self) -> None:
        before = observe(self.root, {"kind": "story"}, feature="REQ-DEMO", blueprint=None,
                         story_build=str(DEV_STORY_BUILD))
        self.assertFalse(before["reached"])
        self.assertIn("还没登记成文", before["missing"][0])
        self.reviewed("pass")
        self.assertEqual(0, self.register().returncode)
        after = observe(self.root, {"kind": "story"}, feature="REQ-DEMO", blueprint=None,
                         story_build=str(DEV_STORY_BUILD))
        self.assertTrue(after["reached"], after["missing"])
        self.assertEqual({"ok": True}, after["delivery"])


if __name__ == "__main__":
    unittest.main()
