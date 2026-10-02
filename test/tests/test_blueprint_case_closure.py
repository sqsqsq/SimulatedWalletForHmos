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
from test_knowledge_task import BLUEPRINT, CU, make_project, prepare  # noqa: E402  —— 它把 test/scripts 放进导入路径
from test_verifier_report_protocol import STORY_BUILD as DEV_STORY_BUILD, TheStoryIsReviewedRegisteredAndDeliveredCase  # noqa: E402
import end_target  # noqa: E402

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


LOCAL = {"kind": "story", "delivery": "local"}
SUBMITTED = {"kind": "story", "delivery": "submitted"}


def observe(root: Path, end_at: dict, *, feature: str = "REQ-DESIGN", blueprint: str | None = BLUEPRINT,
            story_build: str = STORY_BUILD, system_dir: Path | None = None) -> dict:
    return end_target.observe(root, "doc/features", feature, end_at, case={"blueprint_id": blueprint} if blueprint else None,
                              story_build=story_build, system_dir=system_dir)


#: 原生收口时写阶段物证清单的同一对函数：按本阶段的原生输入与产出落哈希（包括 summary）
MANIFEST = """
import * as path from 'node:path';
import { pathToFileURL } from 'node:url';
const [root, feature, phase] = process.argv.slice(1);
const access = await import(pathToFileURL(path.join(root, 'doc/extensions/hooks/shared/framework-access.mjs')).href);
const native = access.loadNative(root);
const m = native.module('scripts/utils/phase-evidence-manifest.ts');
const summary = path.join(access.featureDir(root, feature), phase, 'reports', 'summary.json');
m.writePhaseEvidenceManifest(native.root, m.resolvePhaseEvidenceManifest({ projectRoot: native.root, feature, phase,
  frameworkRoot: native.frameworkRoot, extraOutputs: [summary] }));
"""


def summary(unit_root: Path, where: str, **fields) -> None:
    """阶段收口时 harness 写的 summary（身份、质量结论与收口状态），放在 `where` 阶段目录；`fields` 覆盖默认值造反例。"""
    reports = unit_root / where / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    body = {"feature": CU, "phase": where, "verdict": "PASS", "closure_status": "closed", **fields}
    (reports / "summary.json").write_text(json.dumps(body), encoding="utf-8")


def seal(root: Path, phase: str) -> None:
    """用原生的物证清单函数给这一阶段落证据（真实流程里由 harness 收口时做）。"""
    proc = subprocess.run(["node", "--input-type=module", "-e", MANIFEST, str(root), CU, phase],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    assert proc.returncode == 0, proc.stderr[-600:]


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
        self.assertEqual([f"施工单位 {UNIT} 的执行范围还没冻结"], facts["missing"])

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
    """范围冻结之后，阶段结论全取原生事实（真实冻结工程、真实原生判定）。

    夹具的冻结范围只执行 coding 之后的阶段：spec、plan 的义务由蓝图派生的输入承接（`satisfied_by`），是原生合法复用。
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = make_project(root=Path(cls._tmp.name) / "p")
        prepare(cls.root, "freeze")
        cls.unit = cls.root / "doc" / "features" / BLUEPRINT / UNIT

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_a_plan_end_is_reached_by_native_reuse(self) -> None:
        """spec、plan 不在执行链上，义务由原生承接证据满足：不跑这两个阶段、没有回执也到了。"""
        facts = observe(self.root, {"kind": "phase", "phase": "plan"})
        self.assertTrue(facts["reached"], facts["missing"])
        self.assertEqual({"spec": "reused", "plan": "reused"}, {p: r["state"] for p, r in facts["units"][0]["phases"].items()})
        self.assertEqual("satisfied", facts["units"][0]["phases"]["spec"]["native"]["kind"])


class TheExecutedPhaseNeedsCurrentNativeEvidence(unittest.TestCase):
    """执行链上的阶段：原生完成证据身份相符、收口且通过，认定到达时阶段物证仍新鲜；输入变了旧结论不能沿用。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = make_project(root=Path(cls._tmp.name) / "p")
        prepare(cls.root, "freeze")
        cls.unit = cls.root / "doc" / "features" / BLUEPRINT / UNIT

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    END = {"kind": "phase", "phase": "coding"}

    def test_evidence_must_be_this_units_closed_current_and_passing(self) -> None:
        # 执行链上的阶段没有完成证据：不因为它不要求新 Markdown 就算复用
        self.assertIn("没有身份相符的原生完成证据", observe(self.root, self.END)["missing"][0])
        # 别的 Feature、别的阶段的 summary：身份不符
        for wrong in ({"feature": "cu-other"}, {"phase": "spec"}):
            with self.subTest(wrong=wrong):
                summary(self.unit, "coding", **wrong)
                self.assertIn("没有身份相符的原生完成证据", observe(self.root, self.END)["missing"][0])
        summary(self.unit, "coding", verdict="FAIL")
        self.assertIn("质量结论是 FAIL", observe(self.root, self.END)["missing"][0])
        # 身份、收口与结论都对，但没有阶段物证：认定到达时核不出新鲜
        summary(self.unit, "coding")
        self.assertIn("不再新鲜", observe(self.root, self.END)["missing"][0])
        seal(self.root, "coding")
        facts = observe(self.root, self.END)
        self.assertTrue(facts["reached"], facts["missing"])
        self.assertEqual("fresh", facts["units"][0]["phases"]["coding"]["native"]["freshness"]["verdict"])
        # 阶段输入变了（物证清单里记为不存在的 plan.md 出现了）：原生判物证过期，旧结论不能沿用
        plan = self.unit / "plan" / "plan.md"
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text("# 计划\n", encoding="utf-8")
        stale = observe(self.root, self.END)
        self.assertFalse(stale["reached"])
        self.assertIn("不再新鲜", stale["missing"][0])
        plan.unlink()
        self.assertTrue(observe(self.root, self.END)["reached"], "输入恢复原样，物证又是新鲜的")
        # 复用承接的输入变了（物化出本地验收与契约）：spec 的承接证据失效，不再算复用
        prepare(self.root, "materialize")
        reuse = observe(self.root, {"kind": "phase", "phase": "spec"})
        self.assertFalse(reuse["reached"])
        self.assertIn("input binding stale", reuse["missing"][0])


class OneUnitShortIsNotTheWholeRequirement(unittest.TestCase):
    """多个施工单位：逐个列身份与结论，有一个没到整单就没到。

    **分支消费用例**：原生观测结果由这里给出（夹具只有一个施工单位），只核扩展这一侧怎么汇总；真实原生判定见上面两类。
    """

    FROZEN = {"status": "frozen", "source": "feature", "phase_chain": ["coding"]}
    NATIVE = {"blueprint": {"status": "ok", "admitted": True, "projection": "valid", "issues": []}, "problems": [], "units": [
        {"change_unit_id": "a", "feature_id": "cu-a", "feature_path": "doc/features/bp/a", "scope": FROZEN,
         "design": {"verdict": "constructable", "issues": []},
         "phases": {"spec": {"kind": "satisfied", "obligations": ["acceptance-context:candidate"], "unsatisfied": [], "issues": []}}},
        {"change_unit_id": "b", "feature_id": "cu-b", "feature_path": "doc/features/bp/b", "scope": FROZEN,
         "design": {"verdict": "constructable", "issues": []},
         "phases": {"spec": {"kind": "satisfied", "obligations": ["acceptance-context:candidate"], "unsatisfied": [],
                             "issues": ["acceptance-context:candidate: input binding stale doc/features/bp/blueprint/component-blueprint.yaml"]}}}]}

    def test_the_unit_that_is_short_is_named(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(end_target, "observe_native", return_value=self.NATIVE):
            facts = end_target.observe(Path(tmp), "doc/features", "REQ", {"kind": "phase", "phase": "spec"},
                                       case={"blueprint_id": "bp"}, story_build=STORY_BUILD)
        self.assertFalse(facts["reached"])
        self.assertEqual({"a": "reused", "b": "open"}, {u["change_unit_id"]: u["phases"]["spec"]["state"] for u in facts["units"]})
        self.assertEqual(1, len(facts["missing"]))
        self.assertIn("施工单位 b 的 acceptance-context:candidate: input binding stale", facts["missing"][0])
        self.assertEqual(("b", "spec"), end_target.first_open(facts))


class TheStoryEndIsTheDeliveryGate(TheStoryIsReviewedRegisteredAndDeliveredCase):
    """需求交付终点：登记过成文，且只读交付门通过；三份文件在不在不算。

    这份夹具工程只装了审查机制，交付门用开发源的入口按 `--project-root` 跑（与交付门自己的测试同一个跑法）。"""

    def test_unregistered_is_not_delivered_and_delivered_is_reached(self) -> None:
        before = observe(self.root, LOCAL, feature="REQ-DEMO", blueprint=None,
                         story_build=str(DEV_STORY_BUILD))
        self.assertFalse(before["reached"])
        self.assertIn("还没登记成文", before["missing"][0])
        self.reviewed("pass")
        self.assertEqual(0, self.register().returncode)
        after = observe(self.root, LOCAL, feature="REQ-DEMO", blueprint=None,
                         story_build=str(DEV_STORY_BUILD))
        self.assertTrue(after["reached"], after["missing"])
        self.assertEqual({"ok": True, "kind": "local"}, after["delivery"])

    def test_submitted_needs_the_current_version_in_the_requirement_system(self) -> None:
        """送审终点：交付门通过之外，发布记录指当前 Story，需求系统上的正文逐字是它、评审记录附件在。"""
        self.reviewed("pass")
        self.assertEqual(0, self.register().returncode)
        system = self.root.parent / "system"

        def submitted() -> dict:
            return observe(self.root, SUBMITTED, feature="REQ-DEMO", blueprint=None,
                           story_build=str(DEV_STORY_BUILD), system_dir=system)

        self.assertIn("还没送审", submitted()["missing"][0])
        archived = subprocess.run(["python", str(self.FLOW), "archived", "--feature", "REQ-DEMO",
                                   "--project-root", str(self.root)],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, archived.returncode, archived.stdout + archived.stderr)
        self.assertIn("正文", submitted()["missing"][0], "只登记了归档、系统上没有正文，不算送审")

        # 对接层上传后的需求系统：正文是 Story，评审记录是附件
        ticket = system / "REQ-DEMO"
        (ticket / "attachments").mkdir(parents=True)
        (ticket / "design.md").write_bytes(self.story.read_bytes())
        (ticket / "attachments" / "review.md").write_bytes((self.story.parent / "review.md").read_bytes())
        reached = submitted()
        self.assertTrue(reached["reached"], reached["missing"])
        self.assertEqual({"ok": True, "kind": "submitted"}, reached["delivery"])

        (ticket / "design.md").write_bytes(self.story.read_bytes() + "系统上被改过。\n".encode("utf-8"))
        self.assertFalse(submitted()["reached"], "系统上的正文不是当前这一版")

    def tree(self) -> dict[str, bytes]:
        doc = self.root / "doc"
        return {p.relative_to(doc).as_posix(): p.read_bytes() for p in doc.rglob("*") if p.is_file()}

    def test_observing_writes_nothing(self) -> None:
        """观测只读已验证的审查结论：前后整棵 doc/ 逐字节不变；改了正文之后只读地说待同步，不重写报告。"""
        self.reviewed("pass")
        self.assertEqual(0, self.register().returncode)
        before = self.tree()
        self.assertTrue(observe(self.root, LOCAL, feature="REQ-DEMO", blueprint=None,
                                story_build=str(DEV_STORY_BUILD))["reached"])
        self.assertEqual(before, self.tree(), "终点观测改了被测工程的文件")
        self.story.write_bytes(self.story.read_bytes() + "登记之后改的一句。\n".encode("utf-8"))
        edited = self.tree()
        moved = observe(self.root, LOCAL, feature="REQ-DEMO", blueprint=None, story_build=str(DEV_STORY_BUILD))
        self.assertFalse(moved["reached"])
        self.assertEqual(edited, self.tree(), "正文变了之后观测重写了报告")

    def test_a_reply_not_yet_checked_is_pointed_back_to_the_author(self) -> None:
        """回复写好了但还没跑原生检查：交付门不替作者检查，指回 `review --action check`。"""
        original = self.reviewed("pass")
        self.assertEqual(0, self.register().returncode)
        original.write_bytes(original.read_bytes() + "\n补一句。\n".encode("utf-8"))
        facts = observe(self.root, LOCAL, feature="REQ-DEMO", blueprint=None, story_build=str(DEV_STORY_BUILD))
        self.assertFalse(facts["reached"])
        self.assertTrue(any("review --action check" in m for m in facts["missing"]), facts["missing"])


if __name__ == "__main__":
    unittest.main()
