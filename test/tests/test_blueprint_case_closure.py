"""用例终点在真实工程上的观测：到了就闭合，没到就说清缺在哪（test/scripts/end_target.py）。

用 demo Framework 与夹具蓝图（`wallet-balance-refresh`，一个施工单位）在临时工程里走原生入口：
蓝图终点看准入与评审投影，设计交接看活动施工单位的原生设计判定，阶段终点逐施工单位看原生范围与完成回执；
需求交付终点复用真实的「审查 → 登记 → 交付门」正常链。需求与蓝图异名，只凭需求流程契约的设计关联找蓝图。
多施工单位的汇总只替换原生观测的结果，核扩展这一侧怎么消费：有一个没到，整单就没到。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
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
import shared_state  # noqa: E402
from ext_workspace import link_framework  # noqa: E402
import design_fixture  # noqa: E402
from test_knowledge_task import IMPACT_BASIS, REPO_ROOT, REQUIREMENT  # noqa: E402
import yaml  # noqa: E402

STORY_BUILD = "doc/extensions/base/skills/story/scripts/core/story-build.mjs"
UNIT = "balance-refresh"

RENDER = """
import * as path from 'node:path';
import { pathToFileURL } from 'node:url';
const [root, blueprint] = process.argv.slice(1);
const { loadNative } = await import(pathToFileURL(path.join(root, 'doc/extensions/base/hooks/shared/framework-access.mjs')).href);
const native = loadNative(root);
const r = native.module('scripts/utils/blueprint-review-materialization.ts').materializeBlueprintReview(native.root, blueprint);
if (r.status === 'failed') { process.stderr.write(`评审投影原生物化失败：${r.reason ?? ''}`); process.exit(1); }
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
const access = await import(pathToFileURL(path.join(root, 'doc/extensions/base/hooks/shared/framework-access.mjs')).href);
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

    def test_the_blueprint_is_found_in_its_requirement(self) -> None:
        """蓝图与需求同根：需求目录下有 canonical 蓝图就是它，没有就说缺，不另按目录名猜一份。"""
        self.assertIn("需求目录下还没有蓝图", observe(self.root, {"kind": "design_handoff"}, blueprint=None)["missing"][0])
        facts = observe(self.root, {"kind": "design_handoff"}, feature=BLUEPRINT, blueprint=None)
        self.assertEqual(BLUEPRINT, facts["blueprint_id"])
        self.assertTrue(facts["reached"], facts["missing"])

    def test_no_unit_is_a_design_preparation_gap(self) -> None:
        """准入的蓝图还没有施工单位：设计交接没到，缺口是设计准备，不是某个阶段。"""
        copy = Path(self._tmp.name) / "zero"
        shared_state.copy_tree(self.root, copy)       # 跳过 framework junction 再重接，不顺着它复制整个 Framework
        link_framework(copy)
        shutil.rmtree(copy / "doc" / "features" / BLUEPRINT / UNIT)
        facts = observe(copy, {"kind": "design_handoff"})
        self.assertFalse(facts["reached"])
        self.assertEqual([], facts["units"])
        self.assertTrue(any("还没有活动施工单位" in m for m in facts["missing"]), facts["missing"])


class TheStoryDeliveryNeedsTheBlueprintCommonAcceptance(TheStoryIsReviewedRegisteredAndDeliveredCase):
    """零 CU 的 Story 交付门取的是同一份蓝图共同验收：删掉适用条目唯一承接的共同验收，
    `check --deliver` 不放行并点名对象、条目与设计职责；补回后回到正常交付门状态。"""

    def blueprint_path(self) -> Path:
        return self.root / "doc" / "features" / "REQ-DEMO" / "blueprint" / "component-blueprint.yaml"

    def drop_criterion(self) -> bytes:
        import design_kit  # noqa: PLC0415
        canonical = self.blueprint_path()
        original = canonical.read_bytes()
        lines = canonical.read_text(encoding="utf-8").splitlines(keepends=True)
        start = next(i for i, line in enumerate(lines) if line.strip() == "- id: AC-G01")
        indent = len(lines[start]) - len(lines[start].lstrip())
        end = start + 1
        while end < len(lines) and len(lines[end]) - len(lines[end].lstrip()) > indent:
            end += 1
        design_kit.change_blueprint(self.root, "REQ-DEMO", design_kit.ACCESS, "".join(lines[start:end]), "")
        return original

    def test_the_delivery_gate_names_the_missing_common_acceptance(self) -> None:
        base = self.check()
        self.assertEqual(0, base.returncode, base.stdout + base.stderr)
        original = self.drop_criterion()
        out = self.check("--deliver")
        text = out.stdout + out.stderr
        self.assertNotEqual(0, out.returncode, f"缺共同验收却到了交付门：{text}")
        self.assertIn("没有共同验收承接它", text)
        self.assertIn("SMP-01", text)
        self.assertIn("view:logical/node:wallet-balance", text)
        self.assertIn("由设计职责在 component-design 里修订", text)
        self.blueprint_path().write_bytes(original)
        import design_kit  # noqa: PLC0415
        design_kit.render_projection(self.root, "REQ-DEMO", design_kit.ACCESS)
        back = self.check("--deliver")
        text = back.stdout + back.stderr
        self.assertIn("还没登记成文", text, "补回共同验收后交付门没回到正常状态")
        self.assertNotIn("没有共同验收承接它", text)


class ThePhaseEndAfterFreezing(unittest.TestCase):
    """范围冻结之后，阶段结论全取原生事实（真实冻结工程、真实原生判定）。

    夹具的冻结范围里 spec 的义务由蓝图派生的输入承接（`satisfied_by`），是原生合法复用；plan 起在执行链上。
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

    def test_a_spec_end_is_reached_by_native_reuse(self) -> None:
        """spec 不在执行链上，义务由原生承接证据满足：不跑这个阶段、没有回执也到了；plan 在链上，没有收口证据就没到。"""
        facts = observe(self.root, {"kind": "phase", "phase": "spec"})
        self.assertTrue(facts["reached"], facts["missing"])
        self.assertEqual({"spec": "reused"}, {p: r["state"] for p, r in facts["units"][0]["phases"].items()})
        self.assertEqual("satisfied", facts["units"][0]["phases"]["spec"]["native"]["kind"])
        with mock.patch.dict(os.environ, {"MAISON_GOAL_RUN_ID": "foreign-cu-run-id"}):
            isolated = observe(self.root, {"kind": "phase", "phase": "spec"})
        self.assertTrue(isolated["reached"], "普通无 run 冻结工程不应被全局 MAISON_GOAL_RUN_ID 污染")
        plan = observe(self.root, {"kind": "phase", "phase": "plan"})
        self.assertFalse(plan["reached"])
        self.assertEqual("executed", plan["units"][0]["phases"]["plan"]["native"]["kind"])


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
        # 链上 coding 之前的 plan 已收口、物证在
        summary(self.unit, "plan")
        seal(self.root, "plan")
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


def native_cli(root: Path, *args: str) -> subprocess.CompletedProcess:
    """在消费工程的 `framework/harness` 下跑原生入口（与 `phases/design.md` 第六节同一组命令）。
    测试进程的 NODE_OPTIONS（转译缓存钩子）不带进去：原生 harness 把它当注入拦下，真实宿主也没有它。"""
    env = {k: v for k, v in os.environ.items() if k != "NODE_OPTIONS"}
    return subprocess.run(["node", "node_modules/ts-node/dist/bin.js", "--transpile-only", *args],
                          cwd=root / "framework" / "harness", capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=600, env=env)


def private_harness_state(root: Path) -> None:
    """跑真实 harness 的工程用自己的 `framework/harness/state` 与 `reports`：原生 harness 把运行状态写在那里，
    整个 framework 接成共享被测副本的链接时会写进共享副本，让别的用例看到它在变。其余部分照旧链接或复制自被测副本。"""
    framework = root / "framework"
    if framework.is_symlink() or design_fixture._is_junction(framework):
        os.rmdir(framework)  # 只去掉链接本身，共享副本不动
    for name in ("state", "reports"):
        (framework / "harness" / name).mkdir(parents=True, exist_ok=True)
    design_fixture.overlay_framework(root)


def last_json(text: str) -> dict:
    """原生入口的 JSON 输出：取最后一个从行首 `{` 开始的完整对象。"""
    return json.loads(text[text.rindex("\n{") + 1 if "\n{" in text else text.index("{"):])


class TheRequestChainFromANewlyAcceptedUnit(unittest.TestCase):
    """实现方案的原生接续（`phases/design.md` 第六节）：施工单位经原生接受新建 → 一次 prepare-scope 声明 request spec,plan →
    按原生派生的阶段链准备与正式 harness → 终点观测消费同一份原生事实。

    夹具蓝图已带完整验收，原生判 Spec 由蓝图依据复用、只执行 Plan。Plan 的作者产物与审查由真实作者与 verifier 完成，
    这里不造：harness 只应报本阶段作者的缺口，终点观测说 Plan 还没收口。宿主用夹具已物化的 codex 跑原生检查，不代表 DSH 运行。
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        root = cls.root = make_project(root=Path(cls._tmp.name) / "p")
        private_harness_state(root)
        blueprint = root / "doc" / "features" / BLUEPRINT
        cls.unit = blueprint / UNIT
        # 设计准备段：夹具的施工单位改为分解候选，删掉 canonical 后经原生 consumer 接受
        artifact = yaml.safe_load((cls.unit / "change-unit.yaml").read_text(encoding="utf-8"))
        shutil.rmtree(cls.unit)
        candidates = blueprint / "blueprint" / "change-unit-candidates.json"
        candidates.write_text(json.dumps([{"providerId": artifact["provenance"]["extraction_method"], "artifact": artifact}],
                                         ensure_ascii=False, default=lambda value: value.isoformat()), encoding="utf-8")
        cls.accepted = native_cli(root, "scripts/check-change-unit.ts", "--project-root", str(root), "--blueprint", BLUEPRINT,
                                  "--accept-candidates", candidates.relative_to(root).as_posix(), "--json")
        feature = (last_json(cls.accepted.stdout).get("accepted") or [{}])[0].get("feature_id", "") \
            if cls.accepted.returncode == 0 else ""
        cls.feature = feature
        (root / IMPACT_BASIS).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / "demo" / IMPACT_BASIS, root / IMPACT_BASIS)
        cls.readiness = native_cli(root, "scripts/check-change-unit.ts", "--project-root", str(root), "--blueprint", BLUEPRINT,
                                   "--readiness", "--json")
        # 只授权一个阶段时按那个阶段请求：只看原生派生，不冻结；每种之前删掉上一份候选
        cls.single = {}
        for phase in ("spec", "plan"):
            (cls.unit / "feature.yaml").unlink(missing_ok=True)
            cls.single[phase] = native_cli(root, "scripts/goal-mode-entry.ts", "--project-root", str(root), "--framework-root",
                                           str(root / "framework"), "--feature", feature, "--prepare-scope", "--completion-target",
                                           "request", "--requested-results", f"只要 {phase}", "--requested-phases", phase,
                                           "--requirement-file", REQUIREMENT)
        (cls.unit / "feature.yaml").unlink(missing_ok=True)
        cls.scope = native_cli(root, "scripts/goal-mode-entry.ts", "--project-root", str(root), "--framework-root",
                               str(root / "framework"), "--feature", feature, "--prepare-scope", "--completion-target", "request",
                               "--requested-results", "返回首页余额刷新的设计到 Plan", "--requested-phases", "spec,plan",
                               "--requirement-file", REQUIREMENT)
        cls.prepared = native_cli(root, "scripts/prepare-blueprint-design.ts", "--feature", feature, "--phase", "plan",
                                  "--project-root", str(root), "--framework-root", str(root / "framework"))
        (root / "framework.local.json").write_text(json.dumps({"schema_version": "1.0", "agent_adapter": "codex"}),
                                                    encoding="utf-8")
        cls.harness = native_cli(root, "harness-runner.ts", "--project-root", str(root), "--phase", "plan", "--feature", feature)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_the_unit_identity_comes_from_native_acceptance(self) -> None:
        self.assertEqual(0, self.accepted.returncode, self.accepted.stdout[-1500:] + self.accepted.stderr[-800:])
        self.assertEqual(CU, self.feature, "Feature 标识不是原生接受返回的那一个")
        self.assertTrue((self.unit / "change-unit.yaml").is_file())

    def test_readiness_gives_identity_in_the_inventory_and_work_in_ready_ids(self) -> None:
        """已有施工单位跑 --readiness：accepted 为空（这次没接受），身份从 inventory 取，往下做的只看 ready_ids。"""
        self.assertEqual(0, self.readiness.returncode, self.readiness.stdout[-1500:] + self.readiness.stderr[-800:])
        got = last_json(self.readiness.stdout)
        self.assertEqual([], got["accepted"])
        self.assertEqual([(UNIT, CU)], [(u["change_unit_id"], u["feature_id"]) for u in got["inventory"]])
        self.assertEqual([UNIT], got["ready_ids"])

    def test_a_single_phase_request_goes_by_its_own_phase(self) -> None:
        """授权到哪个阶段就请求哪个阶段，执行链由原生派生：蓝图验收齐时只请求 Spec，f894 起原生复用 Spec 且不追加 Plan（链为空）；
        只请求 Plan 时链为 ['plan'] 与授权一致。"""
        expected = {"spec": [], "plan": ["plan"]}
        for phase, proc in self.single.items():
            with self.subTest(phase=phase):
                self.assertEqual(0, proc.returncode, proc.stdout[-1500:] + proc.stderr[-800:])
                self.assertEqual(expected[phase], last_json(proc.stdout)["phase_chain"])
        method = (DEV_STORY_BUILD.parents[2] / "phases" / "design.md").read_text(encoding="utf-8").split("## 六、", 1)[1]
        for row in ("| 只要 Spec | 第 1—4 步 | `spec` |", "| 只要 Plan | 第 1—4 步 | `plan` |",
                    "| 实现方案（到 Plan） | 第 1—4 步 | `spec,plan` |", "原生要求的阶段超出本次授权时，停下照实说明"):
            self.assertIn(row, method)

    def test_one_request_declares_the_chain_and_reuses_the_satisfied_spec(self) -> None:
        self.assertEqual(0, self.scope.returncode, self.scope.stdout[-1500:] + self.scope.stderr[-800:])
        scope = last_json(self.scope.stdout)
        self.assertEqual("scope_candidate_prepared", scope["type"])
        self.assertEqual(["plan"], scope["phase_chain"], "蓝图验收完整时 Spec 应由原生依据复用、不进执行链")
        self.assertFalse((self.unit / "spec").exists(), "复用的 Spec 不应产生阶段报告")

    def test_the_plan_stage_prepares_only_its_typed_input_and_freezes_on_the_formal_run(self) -> None:
        self.assertEqual(0, self.prepared.returncode, self.prepared.stdout[-1500:] + self.prepared.stderr[-800:])
        self.assertTrue((self.unit / "contracts.yaml").is_file())
        self.assertFalse((self.unit / "acceptance.yaml").exists(), "Plan 的阶段准备写了 Spec 的验收")
        frozen = json.loads((self.unit / "execution-scope.json").read_text(encoding="utf-8"))
        self.assertEqual("feature", frozen["scope_source"], "无 run 的 Feature 载体冻结，不经 Goal run")
        self.assertEqual(("request", ["plan"]),
                         (frozen["execution_scope"]["completion_target"], frozen["execution_scope"]["phase_chain"]))

    def test_the_formal_plan_check_names_only_the_authors_duties(self) -> None:
        out = self.harness.stdout + self.harness.stderr
        self.assertNotEqual(0, self.harness.returncode, "作者产物没写，Plan 不该通过")
        for duty in ("change_unit_contracts_sidecar_missing", "context_exploration_facts_present"):
            self.assertIn(duty, out)
        for wrong in ("change_unit_missing", "acceptance_yaml_present", "Goal"):
            self.assertNotIn(wrong, out.split("NEXT:", 1)[-1], f"阶段检查报了不属于 Plan 作者的缺口：{wrong}")

    def test_the_end_observer_consumes_the_same_native_facts(self) -> None:
        spec = observe(self.root, {"kind": "phase", "phase": "spec"}, feature=BLUEPRINT)
        self.assertTrue(spec["reached"], spec["missing"])
        self.assertEqual("reused", spec["units"][0]["phases"]["spec"]["state"])
        plan = observe(self.root, {"kind": "phase", "phase": "plan"}, feature=BLUEPRINT)
        self.assertFalse(plan["reached"])
        self.assertIn("plan 还没正式收口", plan["missing"][0])


#: 原生 SpecLoader 的冻结范围指纹与 Extension 报告核对：都走真实模块
FINGERPRINT = """
import * as fs from 'node:fs';
import * as path from 'node:path';
import { pathToFileURL } from 'node:url';
const [root, file] = process.argv.slice(1);
const { loadNative } = await import(pathToFileURL(path.join(root, 'doc/extensions/base/hooks/shared/framework-access.mjs')).href);
process.stdout.write(loadNative(root).module('scripts/utils/execution-scope.ts')
  .executionScopeFingerprint(JSON.parse(fs.readFileSync(file, 'utf8')).execution_scope));
"""
REVIEW_INPUTS = """
import { pathToFileURL } from 'node:url';
const [root, feature] = process.argv.slice(1);
const { reviewInputs } = await import(pathToFileURL(root + '/doc/extensions/base/hooks/shared/review-inputs.mjs').href);
const b = reviewInputs(root, feature, 'plan');
process.stdout.write(JSON.stringify({ inputs: b.inputs.map(({ key, required, missing, output }) => ({ key, required, missing, output: !!output })),
  gaps: b.gaps }));
"""
FREEZE = """
import * as path from 'node:path';
import { pathToFileURL } from 'node:url';
const [root, feature] = process.argv.slice(1);
const { loadNative } = await import(pathToFileURL(path.join(root, 'doc/extensions/base/hooks/shared/framework-access.mjs')).href);
const n = loadNative(root);
const frozen = n.module('scripts/utils/feature-execution-scope.ts').ensureFeatureExecutionScopeFrozen({ projectRoot: root, frameworkRoot: n.frameworkRoot, feature });
if (!['frozen', 'reused'].includes(frozen.status)) { process.stderr.write(JSON.stringify(frozen)); process.exit(1); }
"""


class TheCandidatesClaimTheRequiredObligations(unittest.TestCase):
    """施工单位设计准备的认领（`phases/design.md` 第六节第 1 步）：整批候选认领原生派生的必需设计义务。
    缺了必需决定的认领，原生点名要认领的承载、候选留着、不写施工单位；不适用的缺口是事实，不要求认领；
    施工单位承担的决定还是待定时，原生拒绝施工。三种情形各用一份夹具工程，只经原生公开的接受命令。"""

    NOT_APPLICABLE_GAP = ("  gaps:\n"
                          "    - gap_id: refresh-telemetry-later\n"
                          "      status: not_applicable\n"
                          "      owner: product-owner\n"
                          "      needed_by: component-closure\n"
                          "      unlock_condition: 运营确认不需要单独的刷新埋点\n"
                          "      provenance: *a2\n")
    DECIDED = "    - decision_id: balance-refresh-policy\n      status: decided_with_authority\n"

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.unclaimed = cls.accept("unclaimed", without_decision=True)
        cls.not_applicable = cls.accept("not-applicable", revise=("  gaps: []\n", cls.NOT_APPLICABLE_GAP))
        cls.open_decision = cls.accept("open-decision", revise=(cls.DECIDED, cls.DECIDED.replace("decided_with_authority",
                                                                                                    "open_decision")))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    @classmethod
    def accept(cls, name: str, *, without_decision: bool = False, revise: tuple[str, str] | None = None) -> dict:
        root = make_project(root=Path(cls._tmp.name) / name)
        private_harness_state(root)
        blueprint = root / "doc" / "features" / BLUEPRINT
        if revise:
            cls.revise(root, *revise)
        artifact = yaml.safe_load((blueprint / UNIT / "change-unit.yaml").read_text(encoding="utf-8"))
        if without_decision:
            artifact["design_refs"] = [ref for ref in artifact["design_refs"] if ref["target"]["kind"] != "decision"]
        shutil.rmtree(blueprint / UNIT)
        candidates = blueprint / "blueprint" / "change-unit-candidates.json"
        candidates.write_text(json.dumps([{"providerId": artifact["provenance"]["extraction_method"], "artifact": artifact}],
                                         ensure_ascii=False, default=lambda value: value.isoformat()), encoding="utf-8")
        proc = native_cli(root, "scripts/check-change-unit.ts", "--project-root", str(root), "--blueprint", BLUEPRINT,
                          "--accept-candidates", candidates.relative_to(root).as_posix(), "--json")
        return {"proc": proc, "result": last_json(proc.stdout), "candidates_kept": candidates.exists(),
                "unit_written": (blueprint / UNIT).exists()}

    @staticmethod
    def revise(root: Path, old: str, new: str) -> None:
        """设计职责修订蓝图：换一段原文，按原生算法重算来源指纹，施工单位的蓝图引用跟着更新（与 `test_cu_knowledge_chain.design` 同一口径）。"""
        import design_kit  # noqa: PLC0415
        canonical = root / "doc" / "features" / BLUEPRINT / "blueprint" / "component-blueprint.yaml"
        digest = lambda: "sha256:" + hashlib.sha256(canonical.read_bytes()).hexdigest()  # noqa: E731
        stamp = lambda text: text.split("source_fingerprint: ", 1)[1].split("\n", 1)[0]  # noqa: E731
        before, before_text = digest(), canonical.read_text(encoding="utf-8")
        assert before_text.count(old) == 1, old
        canonical.write_bytes(before_text.replace(old, new).encode("utf-8"))
        proc = subprocess.run(["node", "--input-type=module", "-e", design_kit.REFINGERPRINT, str(root), str(design_kit.ACCESS),
                               BLUEPRINT, str(canonical)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=120)
        assert proc.returncode == 0, proc.stderr[-600:]
        unit = root / "doc" / "features" / BLUEPRINT / UNIT / "change-unit.yaml"
        unit.write_bytes(unit.read_bytes().replace(before.encode(), digest().encode())
                         .replace(stamp(before_text).encode(), stamp(canonical.read_text(encoding="utf-8")).encode()))

    def test_an_unclaimed_required_decision_is_named_and_nothing_is_written(self) -> None:
        got = self.unclaimed
        self.assertNotEqual(0, got["proc"].returncode)
        message = " ".join(issue["message"] for issue in got["result"]["issues"])
        self.assertIn("change_unit_design_closure_incomplete", message)
        self.assertIn("decision:balance-refresh-policy", message, "没点名要认领的承载")
        self.assertTrue(got["candidates_kept"], "被拒的候选要留着，改了再接受")
        self.assertFalse(got["unit_written"], "被拒时写了施工单位")

    def test_a_not_applicable_gap_needs_no_claim(self) -> None:
        got = self.not_applicable
        self.assertEqual(0, got["proc"].returncode, got["proc"].stdout[-1500:])
        self.assertEqual([UNIT], [unit["change_unit_id"] for unit in got["result"]["accepted"]])
        self.assertEqual([UNIT], got["result"]["ready_ids"])
        self.assertFalse(got["candidates_kept"], "接受成功后原生删除候选")

    def test_an_open_decision_the_unit_carries_refuses_construction(self) -> None:
        got = self.open_decision
        self.assertNotEqual(0, got["proc"].returncode)
        message = " ".join(issue["message"] for issue in got["result"]["issues"])
        self.assertIn("change_unit_current_design_unresolved", message)
        self.assertIn("decision:balance-refresh-policy", message)
        self.assertTrue(got["candidates_kept"])
        self.assertFalse(got["unit_written"])


def review_inputs(root: Path) -> dict:
    proc = subprocess.run(["node", "--input-type=module", "-e", REVIEW_INPUTS, str(root), CU], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300)
    assert proc.returncode == 0, proc.stderr[-600:]
    return json.loads(proc.stdout)


REPORT_CHECK = """
import { pathToFileURL } from 'node:url';
const [root, feature] = process.argv.slice(1);
const { reportProblems } = await import(pathToFileURL(root + '/doc/extensions/base/hooks/shared/verifier-report.mjs').href);
process.stdout.write(JSON.stringify(reportProblems(root, feature, 'plan')));
"""
#: 夹具作者读过的工程来源：从 demo 复制，是消费工程里本来就有的文件
EXPLORED = ("02-Feature/WalletMain/src/main/ets/data/repository/HomeRepository.ets",
            "02-Feature/WalletMain/src/main/ets/data/repository/CardRepository.ets",
            "02-Feature/WalletMain/src/main/ets/data/model/HomeCardState.ets",
            "02-Feature/WalletMain/src/main/ets/data/model/FinanceEntry.ets",
            "02-Feature/WalletMain/src/main/module.json5", "02-Feature/WalletMain/build-profile.json5", "build-profile.json5")


class APlanClosesThroughTheNativeRequest(unittest.TestCase):
    """B01 成功组合：新施工单位经原生接受 → request 只要 Plan → 阶段准备 → 夹具作者补本阶段产物 → 正式 harness 签发审查请求
    → 审查边界用测试替身回复（回显这次的 subject、按任务的必审表写四键）→ 原生 check-receipt 收口 → 终点观测认 phase:plan。

    Spec 由蓝图验收复用、本地没有 spec.md 与 acceptance.yaml：必审集合按原生选中的输入（input_id）与本阶段要交的产物取，
    知识只取同一份审查者任务送了正文的那几份。替身只证明确定性消费，不证明业务审查。"""

    @classmethod
    def setUpClass(cls) -> None:
        import test_cu_knowledge_chain as chain  # noqa: PLC0415
        cls._tmp = tempfile.TemporaryDirectory()
        root = cls.root = make_project(root=Path(cls._tmp.name) / "p")
        private_harness_state(root)
        chain.design(root, True)
        blueprint = root / "doc" / "features" / BLUEPRINT
        unit = cls.unit = blueprint / UNIT
        artifact = yaml.safe_load((unit / "change-unit.yaml").read_text(encoding="utf-8"))
        shutil.rmtree(unit)
        candidates = blueprint / "blueprint" / "change-unit-candidates.json"
        candidates.write_text(json.dumps([{"providerId": artifact["provenance"]["extraction_method"], "artifact": artifact}],
                                         ensure_ascii=False, default=lambda value: value.isoformat()), encoding="utf-8")
        accepted = native_cli(root, "scripts/check-change-unit.ts", "--project-root", str(root), "--blueprint", BLUEPRINT,
                              "--accept-candidates", candidates.relative_to(root).as_posix(), "--json")
        assert accepted.returncode == 0, accepted.stdout[-800:]
        for rel in EXPLORED:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO_ROOT / "demo" / rel, root / rel)
        scope = native_cli(root, "scripts/goal-mode-entry.ts", "--project-root", str(root), "--framework-root", str(root / "framework"),
                           "--feature", CU, "--prepare-scope", "--completion-target", "request", "--requested-results",
                           "返回首页余额刷新的 Plan", "--requested-phases", "plan", "--requirement-file", REQUIREMENT)
        assert scope.returncode == 0, scope.stdout[-800:]
        prepared = native_cli(root, "scripts/prepare-blueprint-design.ts", "--feature", CU, "--phase", "plan", "--project-root",
                              str(root), "--framework-root", str(root / "framework"))
        assert prepared.returncode == 0, prepared.stdout[-800:]
        (root / "framework.local.json").write_text(json.dumps({"schema_version": "1.0", "agent_adapter": "codex"}), encoding="utf-8")
        # 第一次正式运行冻结范围（作者产物还没写，原生报缺），之后夹具作者按原生 required_outputs 写本阶段产物
        cls.usage_before = cls.usage_files(root, unit)
        native_cli(root, "harness-runner.ts", "--project-root", str(root), "--phase", "plan", "--feature", CU)
        cls.author(root, unit)
        cls.harness = native_cli(root, "harness-runner.ts", "--project-root", str(root), "--phase", "plan", "--feature", CU)
        cls.usage_after = cls.usage_files(root, unit)
        summary = json.loads((unit / "plan" / "reports" / "summary.json").read_text(encoding="utf-8"))
        cls.before = summary
        assert summary.get("verifier_request"), cls.harness.stdout[-2500:]
        request = json.loads((root / summary["verifier_request"]).read_text(encoding="utf-8"))
        cls.prompt = (root / request["prompt_path"]).read_text(encoding="utf-8")
        cls.reply = cls.stand_in(cls.prompt, request["subject_id"])
        cls.report = root / summary["verifier_report"]
        cls.report.write_text(cls.reply, encoding="utf-8")
        cls.problems = cls.check_report(root)
        cls.receipt = native_cli(root, "scripts/check-receipt.ts", "--project-root", str(root), "--feature", CU, "--phase", "plan")
        cls.after = json.loads((unit / "plan" / "reports" / "summary.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    @staticmethod
    def usage_files(root: Path, unit: Path) -> dict[str, bytes | None]:
        """使用记录的三处：本单位的身份、项目的起点暂存与使用记录；不在的记 None。"""
        files = {"usage-id": unit / ".usage-id", "usage-state": root / "doc" / "features" / ".usage-state.json",
                 "usage": root / "doc" / "usage.json"}
        return {name: path.read_bytes() if path.exists() else None for name, path in files.items()}

    @staticmethod
    def author(root: Path, unit: Path) -> None:
        """夹具作者：本阶段的 change_unit 映射与 context/facts.md（原生 required_outputs 与 facts 合同要求的那几项）。"""
        cu_bytes = (unit / "change-unit.yaml").read_bytes()
        cu = yaml.safe_load(cu_bytes)
        impl = f"planned:{EXPLORED[0]}#HomeRepository.refreshBalance"
        test = "planned:02-Feature/WalletMain/src/test/HomeRepository.test.ets#refreshBalance"
        contracts = yaml.safe_load((unit / "contracts.yaml").read_text(encoding="utf-8"))
        contracts["change_unit"] = {
            "change_unit_ref": {"artifact": "change-unit@1", "component_id": cu["component_id"], "blueprint_id": cu["blueprint_id"],
                                "change_unit_id": cu["change_unit_id"], "revision": cu["revision"],
                                "artifact_sha256": "sha256:" + hashlib.sha256(cu_bytes).hexdigest()},
            "predicate_mappings": [{"predicate_id": x["predicate_id"], "implementation_refs": [impl], "test_refs": [test]}
                                   for x in cu.get("target_predicates") or []],
            "provide_mappings": [{"provide_id": x["provide_id"], "implementation_refs": [impl], "test_refs": [test]}
                                 for x in cu.get("provides") or []],
            "design_ref_mappings": [{"design_ref": ref, "implementation_refs": [impl], "verification_refs": [test]}
                                    for ref in cu["design_refs"]]}
        (unit / "contracts.yaml").write_text(yaml.safe_dump(contracts, allow_unicode=True, sort_keys=False), encoding="utf-8")
        fingerprint = subprocess.run(["node", "--input-type=module", "-e", FINGERPRINT, str(root), str(unit / "execution-scope.json")],
                                     capture_output=True, text=True, encoding="utf-8", timeout=300)
        assert fingerprint.returncode == 0, fingerprint.stderr
        rows = "".join(f"| {r} | 读过 {r.rsplit('/', 1)[-1]} 的现有结构 | 刷新入口按它落 |\n" for r in EXPLORED)
        (unit / "context").mkdir(exist_ok=True)
        (unit / "context" / "facts.md").write_text(
            f'---\nschema_version: "1.1"\nfeature: "{CU}"\nphase: "plan"\nestablished_by: "plan"\n'
            f'frozen_scope_fingerprint: "{fingerprint.stdout.strip()}"\nready_to_produce: true\nhas_blocker_coverage_risk: false\n'
            'key_inputs_read:\n  - "paths.module_catalog — 已读"\n  - "doc/extensions/base/hooks/plan/author.md — 已读"\n'
            '  - "build-profile.json5 — 已读"\n  - "module.json5 — 已读"\nsource_code_paths:\n'
            + "".join(f"  - {r}\n" for r in EXPLORED)
            + 'exploration_mode: "sequential"\nchange_intent: "feature"\nestimated_loc_delta: 20\ntouches_layers: ["02-Feature"]\n'
            'adds_new_exports: false\nsingle_function_scope: true\ndecisions_unlocked:\n  - "HomeRepository.refreshBalance 承接返回首页刷新"\n'
            'subagents_used: ""\nsearches_performed_estimate: 12\nfiles_inspected_count: 12\n---\n\n## Code Facts\n\n'
            '| 路径 | 发现的事实 | 对本阶段产出的影响 |\n|------|-----------|------------------|\n' + rows, encoding="utf-8")

    @staticmethod
    def required_keys(prompt: str) -> list[str]:
        table = prompt.split("的必审输入（报告的 examined_inputs 按这张表逐项声明）", 1)[1].split("\n\n上面每一项", 1)[0]
        return re.findall(r"^- (?:原生输入 )?`([^`]+)`", table, re.M)

    @classmethod
    def stand_in(cls, prompt: str, subject: str, keys: list[str] | None = None) -> str:
        """审查边界的测试替身：判据与严重度照这次真实请求的 prompt 列，四键按任务的必审表写；不代表业务审查。"""
        native = re.findall(r"^\| ([a-z_]+) \| (BLOCKER|MAJOR|MINOR) \|$",
                            prompt.split("## 七、输出格式", 1)[1].split("### 7.1", 1)[0], re.M)
        ext = re.findall(r"^- `([a-z_]+)`（(BLOCKER|MAJOR|MINOR)）", prompt.split("## 本阶段全部判据（逐条出结论）", 1)[1], re.M)
        rows = ["| id | status | severity | 证据 |", "|---|---|---|---|",
                *[f"| {i} | PASS | {sev} | 测试替身：只核确定性消费 |" for i, sev in native + ext]]
        listed = cls.required_keys(prompt) if keys is None else keys
        return ("测试替身回复：只用于验证原生请求、收口与观测的确定性消费，不是业务审查结论。\n\n" + "\n".join(rows) + "\n\n"
                "```yaml\nverification_result:\n  phase: \"plan\"\n  checks:\n    - id: knowledge_obligation_substance\n"
                "      status: PASS\n      severity: BLOCKER\n      details:\n        blocking_findings: []\n        advisories: []\n"
                "        examined_inputs:\n" + "".join(f"          - {k}\n" for k in listed) + "        unreviewed: []\n```\n\n"
                f"<!-- maison-verifier-result:v1 -->\nverifier_subject_id: {subject}\nverdict: PASS\nblocker_count: 0\n"
                "<!-- /maison-verifier-result:v1 -->\n")

    @staticmethod
    def check_report(root: Path) -> list[str]:
        proc = subprocess.run(["node", "--input-type=module", "-e", REPORT_CHECK, str(root), CU], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300)
        assert proc.returncode == 0, proc.stderr[-600:]
        return json.loads(proc.stdout)

    def test_the_formal_run_issues_a_request_carrying_the_native_values(self) -> None:
        self.assertEqual(("PASS", "run_verifier_then_receipt"), (self.before["verdict"], self.before["next_action"]),
                         self.harness.stdout[-1500:])
        for id_ in ("acceptance", "contracts"):
            self.assertIn(f"### (resolved input {id_})", self.prompt, f"原生主 prompt 没带选中的 {id_}")

    def test_the_required_set_is_the_native_inputs_the_stage_output_and_this_units_knowledge(self) -> None:
        keys = self.required_keys(self.prompt)
        unit = f"doc/features/{BLUEPRINT}/{UNIT}"
        self.assertEqual(["acceptance", "contracts"], [k for k in keys if "/" not in k], "原生选中的输入没按 input_id 列")
        self.assertIn(f"{unit}/contracts.yaml", keys, "本阶段要交的产物没进必审")
        for gone in (f"{unit}/spec/spec.md", f"{unit}/acceptance.yaml", f"{unit}/plan/plan.md", f"{unit}/use-cases.yaml"):
            self.assertNotIn(gone, keys, f"复用的 Spec 或没有的产物被列成必审：{gone}")
        sent = re.findall(r"^- 位置：`(doc/extensions/knowledge/[^`]+)`", self.prompt, re.M)
        self.assertEqual(sorted(sent), sorted(k for k in keys if k.startswith("doc/extensions/knowledge/")),
                         "必审的知识与同一份请求里送了正文的知识不是同一组")
        self.assertLess(len(sent), len(yaml.safe_load((self.root / "doc/extensions/manifest.yaml").read_text(encoding="utf-8"))
                                       ["provides"]["knowledge"]), "必审又成了全部激活知识")

    def test_the_extension_report_check_reads_the_same_set(self) -> None:
        self.assertEqual([], self.problems)
        keys = self.required_keys(self.prompt)
        subject = self.before["verifier_subject_id"]
        try:
            self.report.write_text(self.stand_in(self.prompt, subject, [k for k in keys if k != "acceptance"]), encoding="utf-8")
            got = self.check_report(self.root)
        finally:
            self.report.write_text(self.reply, encoding="utf-8")
        self.assertTrue(any("必审输入既没出现在 examined_inputs 也没列进 unreviewed" in p and "acceptance" in p for p in got), got)

    def test_related_knowledge_the_audience_keeps_out_is_a_gap(self) -> None:
        """契约 must 引的规约受众含 plan：没有登记冲突的缺口。把它的受众改成只有 spec：必审缺口点名这份知识，
        四键齐全的 PASS 回复以「缺口没有清零」拒收。"""
        conflict = "登记与消费者冲突"
        self.assertFalse([g for g in review_inputs(self.root)["gaps"] if conflict in g])
        manifest = self.root / "doc" / "extensions" / "manifest.yaml"
        kept = manifest.read_bytes()
        line = "    - knowledge/constraints/observability.md\n"
        self.assertEqual(1, kept.decode("utf-8").count(line), "夹具变了：激活清单里找不到 observability 那一行")
        try:
            manifest.write_bytes(kept.decode("utf-8").replace(
                line, "    - {path: knowledge/constraints/observability.md, audience: [spec]}\n").encode("utf-8"))
            gaps = review_inputs(self.root)["gaps"]
            got = self.check_report(self.root)
        finally:
            manifest.write_bytes(kept)
        self.assertTrue(any(conflict in g and "knowledge/constraints/observability.md" in g for g in gaps), gaps)
        self.assertTrue(any("必审输入还有缺口没有清零" in p and "observability.md" in p for p in got), got)

    def test_a_missing_stage_output_is_missing_not_backfilled(self) -> None:
        """本阶段要交的 contracts.yaml 不在：它照样必审、记缺，缺口点名；不拿原生选中的契约输入顶上。"""
        contracts = self.unit / "contracts.yaml"
        kept = contracts.read_bytes()
        contracts.unlink()
        try:
            got = review_inputs(self.root)
        finally:
            contracts.write_bytes(kept)
        rel = f"doc/features/{BLUEPRINT}/{UNIT}/contracts.yaml"
        self.assertIn({"key": rel, "required": True, "missing": True, "output": True}, got["inputs"])
        self.assertTrue(any("本阶段要交的 contracts.yaml 还没写出" in g for g in got["gaps"]), got["gaps"])

    def test_the_receipt_closes_and_the_observer_reaches_the_plan(self) -> None:
        self.assertEqual(0, self.receipt.returncode, self.receipt.stdout[-1500:])
        self.assertEqual(("closed", "phase_closed_wait_user"), (self.after["closure_status"], self.after["next_action"]))
        facts = observe(self.root, {"kind": "phase", "phase": "plan"}, feature=BLUEPRINT)
        self.assertTrue(facts["reached"], facts["missing"])

    def test_the_formal_harness_runs_leave_usage_alone(self) -> None:
        """两次正式 harness（冻结范围、签发审查请求）都不开始统计：使用记录三处与运行前逐字节相同，阶段报告里没有统计内容。"""
        self.assertTrue(self.before.get("verifier_request"), "第二次正式运行没签发审查请求，不能据此说没有副作用")
        self.assertEqual(self.usage_before, self.usage_after, "正式 harness 改了使用记录")
        text = (self.unit / "plan" / "reports" / "script-report.json").read_text(encoding="utf-8")
        self.assertNotIn('"spent"', text, "统计内容进了阶段报告")


class ARequestedPlanBodyIsAStageOutput(unittest.TestCase):
    """请求结果里单列一项 `plan.md`（phases/design.md 第六节第 2 步）：原生把 plan/plan.md 列进本阶段要交的产物，
    必审集合照它要求、缺了点名；只要原生阶段结果的请求不列它（见上面的成功组合）。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        root = cls.root = make_project(root=Path(cls._tmp.name) / "p")
        scope = native_cli(root, "scripts/goal-mode-entry.ts", "--project-root", str(root), "--framework-root", str(root / "framework"),
                           "--feature", CU, "--prepare-scope", "--completion-target", "request",
                           "--requested-results", "返回首页余额刷新的 Plan", "--requested-results", "plan.md",
                           "--requested-phases", "plan", "--requirement-file", REQUIREMENT)
        assert scope.returncode == 0, scope.stdout[-800:]
        frozen = subprocess.run(["node", "--input-type=module", "-e", FREEZE, str(root), CU], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=300)
        assert frozen.returncode == 0, frozen.stderr[-600:]
        cls.got = review_inputs(root)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_the_plan_body_is_required_and_named_when_missing(self) -> None:
        rel = f"doc/features/{BLUEPRINT}/{UNIT}/plan/plan.md"
        self.assertIn({"key": rel, "required": True, "missing": True, "output": True}, self.got["inputs"])
        self.assertTrue(any("本阶段要交的 plan/plan.md 还没写出" in g for g in self.got["gaps"]), self.got["gaps"])


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
        """送审终点：仅对 AR 系统单成立，交付门通过之外核取材回执布尔交付要求、发布记录与已发布副本、
        需求系统正文与（必交或可选已交付时的）设计参考附件；本地非 AR 单拒判送审但保留 story:local。"""
        import design_kit
        from designed_fixture import designed_copy
        from test_verifier_report_protocol import READER_TASK, with_reader

        # 1. 本地非 AR 单（REQ-DEMO）：story:local 仍通过；即使全局 system 目录存在同名目录，story:submitted 仍拒判
        self.reviewed("pass")
        self.assertEqual(0, self.register().returncode)
        system = self.root.parent / "system"
        local_ok = observe(self.root, LOCAL, feature="REQ-DEMO", blueprint=None, story_build=str(DEV_STORY_BUILD))
        self.assertTrue(local_ok["reached"], local_ok["missing"])
        (system / "REQ-DEMO").mkdir(parents=True)
        (system / "REQ-DEMO" / "design.md").write_bytes(self.story.read_bytes())
        local_sub = observe(self.root, SUBMITTED, feature="REQ-DEMO", blueprint=None,
                            story_build=str(DEV_STORY_BUILD), system_dir=system)
        self.assertFalse(local_sub["reached"])
        self.assertTrue(any("只有 AR 开头" in m for m in local_sub["missing"]), local_sub["missing"])

        # 2. 系统 AR 单（AR-DEMO）：走完整真实审查 → 登记 → 归档 → observe(story:submitted)
        ar_feat = "AR-DEMO"
        ar_fixture = Path(self._tmp.name) / "ar-fixture"
        shutil.copytree(self.FIXTURE, ar_fixture)
        ar_dir = ar_fixture / "doc" / "features" / ar_feat
        (ar_fixture / "doc" / "features" / "REQ-DEMO").rename(ar_dir)
        (ar_dir / "SR").mkdir(parents=True, exist_ok=True)
        (ar_dir / "SR" / "design.md").write_text("# AR-DEMO 系统设计\n\n本部件承接甲需求。\n", encoding="utf-8")
        for rel in ("AR/story.md", "AR/story-src/materials.json"):
            p = ar_dir / rel
            txt = p.read_text(encoding="utf-8").replace("REQ-DEMO", ar_feat)
            if rel == "AR/story.md":
                txt = txt.rstrip() + "\n| 系统设计 [design.md](../SR/design.md) | [design.md](../SR/design.md) | 本部件系统设计分工。 |\n"
            p.write_text(txt, encoding="utf-8")
        ar_root = Path(self._tmp.name) / "ar-work"
        designed_copy(ar_fixture, ar_feat, ar_root)
        imp_py = DEV_STORY_BUILD.parent / "import_sources.py"
        imp = subprocess.run(["python", str(imp_py), "--feature", ar_feat, "--project-root", str(ar_root)],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, imp.returncode, imp.stdout + imp.stderr)
        design_kit.install_review_mechanism(ar_root, DEV_STORY_BUILD.parents[5])
        ar_story = ar_root / "doc" / "features" / ar_feat / "AR" / "story.md"
        ar_src = ar_story.parent / "story-src"
        ar_design = ar_story.parent.parent / "blueprint" / "component-blueprint.review.md"

        def ar_node(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run(["node", str(DEV_STORY_BUILD), *with_reader(args, READER_TASK),
                                   "--feature", ar_feat, "--project-root", str(ar_root)],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)

        p1 = ar_node("review", "--action", "prepare")
        self.assertEqual(0, p1.returncode, p1.stdout + p1.stderr)
        design_kit.write_review(ar_root, ar_feat, "pass")
        p2 = ar_node("review", "--action", "prepare")
        self.assertEqual(0, p2.returncode, p2.stdout + p2.stderr)
        reg = subprocess.run(["python", str(self.FLOW), "story", "--feature", ar_feat, "--project-root", str(ar_root)],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, reg.returncode, reg.stdout + reg.stderr)

        def submitted() -> dict:
            return observe(ar_root, SUBMITTED, feature=ar_feat, blueprint=None,
                           story_build=str(DEV_STORY_BUILD), system_dir=system)

        self.assertIn("还没送审", submitted()["missing"][0])
        ticket = system / ar_feat
        attachment = ticket / "attachments" / "design-review.md"
        attachment.parent.mkdir(parents=True)
        (ticket / "design.md").write_bytes(ar_story.read_bytes())

        def write_receipt(req_flag: object, include_design: bool) -> dict:
            pairs = (("AR-design.md", "AR/story.md"),
                     *(("design-review.md", "blueprint/component-blueprint.review.md") for _ in ([1] if include_design else ())))
            items = [{"name": name, "status": "fetched", "checkedAt": "2099-01-01T00:00:00+00:00",
                      "digest": "sha256:" + hashlib.sha256((ar_story.parent.parent / local).read_bytes()).hexdigest()[:16]}
                     for name, local in pairs]
            delivery = {"prepared_at": "2099-01-01T00:00:00+00:00", "items": [
                {"name": i["name"], "local": local, "digest": i["digest"]} for i, (_, local) in zip(items, pairs)]}
            doc = {"fetchedAt": "2099-01-01T00:00:00+00:00", "items": items, "delivery": delivery}
            if req_flag is not None:
                doc["delivery_requirements"] = {"design_reference": req_flag}
            (ar_src / "fetched.json").write_text(json.dumps(doc), encoding="utf-8")
            return doc

        # 2a. 可选未交（design_reference=False，只交 Story 正文）→ 通过
        write_receipt(False, include_design=False)
        arch1 = subprocess.run(["python", str(self.FLOW), "archived", "--feature", ar_feat, "--project-root", str(ar_root)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, arch1.returncode, arch1.stdout + arch1.stderr)
        opt_not_sent = submitted()
        self.assertTrue(opt_not_sent["reached"], opt_not_sent["missing"])

        # 2b. 系统声明必交（design_reference=True）但发布记录不含附件 → 拒判
        write_receipt(True, include_design=False)
        req_missing = submitted()
        self.assertFalse(req_missing["reached"])
        self.assertTrue(any("要求设计参考附件" in m for m in req_missing["missing"]), req_missing["missing"])

        # 2c. 缺取材回执 / 损坏回执 / 字符串布尔声明 → 均拒判（不把缺/坏回执当成无附件义务）
        (ar_src / "fetched.json").unlink()
        no_rec = submitted()
        self.assertFalse(no_rec["reached"])
        self.assertTrue(any("fetched.json" in m for m in no_rec["missing"]), no_rec["missing"])

        (ar_src / "fetched.json").write_text("{bad-json", encoding="utf-8")
        bad_rec = submitted()
        self.assertFalse(bad_rec["reached"])
        self.assertTrue(any("fetched.json" in m for m in bad_rec["missing"]), bad_rec["missing"])

        for raw_non_obj in ("null", "[]", '"str"', "123"):
            (ar_src / "fetched.json").write_text(raw_non_obj, encoding="utf-8")
            non_obj = submitted()
            self.assertFalse(non_obj["reached"], f"合法非对象 JSON {raw_non_obj} 不应放行")
            self.assertTrue(any("顶层不是 JSON 对象" in m for m in non_obj["missing"]), non_obj["missing"])

        for bad_flag in ("true", "false", 1, None):
            write_receipt(bad_flag, include_design=False)
            bad_decl = submitted()
            self.assertFalse(bad_decl["reached"], f"非布尔声明 {bad_flag!r} 不应放行")
            self.assertTrue(any("布尔交付要求声明" in m for m in bad_decl["missing"]), bad_decl["missing"])

        # 2d. 可选选择交付设计参考附件（design_reference=False + delivery 含 design-review.md）：核远端附件空/旧/匹配与幂等
        write_receipt(False, include_design=True)
        arch2 = subprocess.run(["python", str(self.FLOW), "archived", "--feature", ar_feat, "--project-root", str(ar_root)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, arch2.returncode, arch2.stdout + arch2.stderr)
        for stale, why in ((b"", "空附件"), (b"\xe4\xb8\x8a\xe4\xb8\x80\xe7\x89\x88\n", "旧附件")):
            attachment.write_bytes(stale)
            self.assertTrue(any("设计参考" in m for m in submitted()["missing"]), f"{why}被当成送到了")
        attachment.write_bytes(ar_design.read_bytes())

        def ar_snapshot() -> dict[str, bytes]:
            doc_dir = ar_root / "doc"
            return {**{p.relative_to(doc_dir).as_posix(): p.read_bytes() for p in doc_dir.rglob("*") if p.is_file()},
                    **{f"system/{p.relative_to(system).as_posix()}": p.read_bytes() for p in system.rglob("*") if p.is_file()}}

        before = ar_snapshot()
        for _ in range(2):
            reached = submitted()
            self.assertTrue(reached["reached"], reached["missing"])
        self.assertEqual({"ok": True, "kind": "submitted"}, reached["delivery"])
        self.assertEqual(before, ar_snapshot(), "重复观察写了文件")

        # 2e. 远端正文陈旧 / 本地设计参考陈旧 → 拒判
        (ticket / "design.md").write_bytes(ar_story.read_bytes() + "系统上被改过。\n".encode("utf-8"))
        self.assertFalse(submitted()["reached"], "系统上的正文不是当前这一版")
        (ticket / "design.md").write_bytes(ar_story.read_bytes())

        ar_design.write_bytes(ar_design.read_bytes() + "归档之后改的一句。\n".encode("utf-8"))
        attachment.write_bytes(ar_design.read_bytes())
        missing = end_target.story_submitted(ar_root, "doc/features", ar_feat, system)
        self.assertTrue(any("设计参考" in m for m in missing), missing)
        self.assertFalse(any("Story" in m for m in missing), missing)

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

    def test_a_reply_broken_after_registration_is_not_delivered(self) -> None:
        """登记之后回复被改（结论行不合合同、原样摘要也变了）：交付门读的就是这份回复，照实拦下，不沿用登记时的通过。"""
        original = self.reviewed("pass")
        self.assertEqual(0, self.register().returncode)
        original.write_text(original.read_text(encoding="utf-8").replace("conclusion: pass", "conclusion: 通过"), encoding="utf-8")
        facts = observe(self.root, LOCAL, feature="REQ-DEMO", blueprint=None, story_build=str(DEV_STORY_BUILD))
        self.assertFalse(facts["reached"])
        self.assertTrue(any("report_invalid" in m for m in facts["missing"]), facts["missing"])


def physical_framework(root: Path) -> None:
    """物理隔离的 Framework 副本（仅 `harness/node_modules` 接联接，`state`/`reports` 独立）：
    `goal-mode-entry` 内部运行 harness 时会沿脚本真实路径反推工程根，联接 `scripts/` 会跳到共享缓存。"""
    fw = design_fixture.framework_under_test()
    dest = root / "framework"
    if dest.is_symlink() or design_fixture._is_junction(dest):
        os.rmdir(dest)
    elif dest.exists():
        shutil.rmtree(dest)

    def skip(directory: str, names: list[str]) -> set[str]:
        if Path(directory) == fw / "harness":
            return {"node_modules", "state", "reports"}.intersection(names)
        return {".git", "__pycache__"}.intersection(names)

    shutil.copytree(fw, dest, ignore=skip)
    design_fixture._link_dir(fw / "harness" / "node_modules", dest / "harness" / "node_modules")
    for name in ("state", "reports"):
        (dest / "harness" / name).mkdir(parents=True, exist_ok=True)


class TheAuthorPromptDistinguishesThreeFrozenStates(unittest.TestCase):
    """S30/R1 作者提示的最早落点与无歧义终点（`phases/design.md` 第六节第 5 步、`phases/update.md`）：
    对三种合法但走不同路径的输入（未冻结普通接续 / 已冻结且来源有效仍欠 Plan / 已失效无可用转交或宿主不可用或空链）
    加只准改业务文档的 update 输入，核实动作前上下文顺序与三个独立终点——相反指令与失败后仍回第 4 步必须被拒。"""

    def test_design_and_update_prompts_cover_all_three_frozen_branches(self) -> None:
        design_md = (DEV_STORY_BUILD.parents[2] / "phases" / "design.md").read_text(encoding="utf-8")
        step5 = design_md.split("5. **共同设计在这一段变了**", 1)[1].split("原生报候选 `differs`", 1)[0]
        # 1) 分支 1（未冻结）→ 分支 2（已冻结先转交再改、后继至原终点）→ 仅成功修订后同步 Story 回第 4 步 → 独立失败出口
        unfrozen_pos = step5.index("**未冻结**")
        frozen_pos = step5.index("**已冻结且旧来源仍可验证**")
        transfer_pos = step5.index("先在改权威来源前")
        revise_pos = step5.index("再由设计负责方修订")
        sync_pos = step5.index("**仅上述成功修订后**")
        fail_pos = step5.index("**已失效且无可用转交**")
        self.assertLess(unfrozen_pos, frozen_pos)
        self.assertLess(frozen_pos, transfer_pos)
        self.assertLess(transfer_pos, revise_pos, "必须先取转交身份再修订权威来源")
        self.assertLess(revise_pos, sync_pos)
        self.assertLess(sync_pos, fail_pos, "成功修订后的 Story 同步与回第 4 步必须先于失败分支")
        # 关键判别：失败分支之后不得再出现公共尾句「同步 Story」或「回到第 4 步」，且明确结束接续
        fail_tail = step5[fail_pos:]
        self.assertIn("结束此次接续", fail_tail)
        self.assertIn("不进入上述同步或第 4 步", fail_tail)
        self.assertNotIn("同步 Story", fail_tail, "失败分支后仍挂了同步 Story 的公共尾句")
        self.assertNotIn("回到第 4 步", fail_tail, "失败分支后仍挂了回到第 4 步的公共尾句")
        for token in (
            "goal-mode-entry --feature <FID> --prepare-run --adapter <已核可用宿主> --run-mode attended --requirement-file <需求文件>",
            "--supersede <source run ID>", "continuation=successor", "requested_results", "--next", "scope_revised",
            "不重发请求、不写 Feature 完成", "未获施工扩权的文档更新只报告施工影响",
            "宿主不支持 attended", "原生返回空链", "不造缺口开 run", "不改授权", "不代换宿主或转 headless",
            "story-build review --action prepare", "story_flow.py story", "无业务变化时不另派审查",
        ):
            self.assertIn(token, step5, f"design.md 第六节第 5 步缺少关键指引：{token}")

        # 2) update.md：在正文流程（第二节）首次可能请蓝图负责方改共同设计的动作之前即给出事前保原请求提示；已换版不补造；表只留结果与责任
        update_md = (DEV_STORY_BUILD.parents[2] / "phases" / "update.md").read_text(encoding="utf-8")
        sec2 = update_md.split("## 二、一条线：从还原依据到收口", 1)[1]
        first_owner_edit = sec2.index("由蓝图负责方")
        first_design_feedback = sec2.index("交蓝图负责方（第 5 步）")
        first_new_rev = sec2.index("接受之后蓝图出新版本")
        first_pre_transfer = sec2.index("先按 `phases/design.md` 第六节第 5 步保住原请求")
        self.assertLess(first_pre_transfer, first_owner_edit,
                        "update.md 保住原请求的提示出现在第二节首次请蓝图负责方改设计之后")
        self.assertLess(first_pre_transfer, first_design_feedback,
                        "update.md 保住原请求的提示出现在交蓝图负责方之前之后")
        self.assertLess(first_pre_transfer, first_new_rev,
                        "update.md 保住原请求的提示出现在接受之后蓝图出新版本之后")
        self.assertIn("读到蓝图已换版时不补造事前转交", sec2[:first_owner_edit])
        sec5 = update_md.split("### 5 对设计的意见交给蓝图负责方", 1)[1].split("### 6 ", 1)[0]
        self.assertLess(sec5.index("先按 `phases/design.md` 第六节第 5 步保住原请求"),
                        sec5.index("接受之后蓝图出新版本"))
        cu_row = next(line for line in update_md.splitlines() if line.startswith("| 已有施工结果 |"))
        self.assertEqual(1, cu_row.count("phases/design.md"), "已有施工结果行仍有重复指路")
        self.assertIn("只授权更新业务文档的，列出受影响 CU、过期阶段与接手动作", cu_row)

        # 3) S32：update.md §二第 2 步「蓝图已经改了」行区分三态，旧无条件同步指路退出，命令仍归 design.md
        bp_changed_row = next(line for line in update_md.splitlines() if line.startswith("| 蓝图已经改了 |"))
        self.assertNotEqual(
            "| 蓝图已经改了 | 读当前蓝图与评审投影，同步受影响的 Story 章节与附录，重新定稿、审查、登记 |",
            bp_changed_row.strip(), "旧的无条件同步指路未退出")
        for token in (
            "已换版不补造事前转交",
            "本次有文档授权、换版有效且无需接回施工请求",
            "纯文档任务不新增施工或等审义务",
            "同步受影响的 Story 章节与附录，重新定稿、审查、登记",
            "仍须接回欠 Plan 原请求且已有合法接续身份",
            "沿 `phases/design.md` 第六节第 5 步办理并仅在其成功出口同步",
            "旧权威已失效且无可用转交",
            "保留 Story、登记与原现场，报告缺口并结束此次接续",
        ):
            self.assertIn(token, bp_changed_row, f"蓝图已经改了行缺少关键边界：{token}")
        for cmd_tok in ("goal-mode-entry", "--prepare-run", "--supersede", "story_flow.py"):
            self.assertNotIn(cmd_tok, bp_changed_row, f"蓝图已经改了行不应重复承担命令：{cmd_tok}")


#: 原生 900c 修订链与绑定直接反例探针（只读，不修改原现场）
S08_NATIVE_CONTROLS = """
import * as fs from 'node:fs';
import * as path from 'node:path';
import { pathToFileURL } from 'node:url';
const [root, feature, runDir] = process.argv.slice(1);
const access = await import(pathToFileURL(path.join(root, 'doc/extensions/base/hooks/shared/framework-access.mjs')).href);
const native = access.loadNative(root);
const { loadScopeRevisions } = native.module('scripts/utils/goal-run-creation.ts');
const { assertRevisionKeepsRequiredObligations } = native.module('scripts/utils/execution-scope.ts');
const cap = native.module('scripts/utils/capability-resolution.ts');
const manifest = JSON.parse(fs.readFileSync(path.join(runDir, 'manifest.json'), 'utf8'));
const events = fs.readFileSync(path.join(runDir, 'events.jsonl'), 'utf8').trim().split(/\\r?\\n/).map(JSON.parse);
const birth = manifest.execution_scope;
const ctx = { projectRoot: root, feature, runId: manifest.run_id, frameworkRoot: native.frameworkRoot };
const revOut = {};
function check(tag, fn) {
  try { revOut[tag] = { ok: true, value: fn() ?? null }; } catch (e) { revOut[tag] = { ok: false, error: String(e?.message ?? e) }; }
}
function variant(mut) {
  const es = structuredClone(events);
  mut(es.find(e => e.type === 'scope_revised'));
  return loadScopeRevisions(es, birth, ctx).length;
}
check('control', () => loadScopeRevisions(events, birth, ctx).length);
check('wrong_previous_fingerprint', () => variant(e => { e.previous_scope_fingerprint = '0'.repeat(64); }));
check('changed_requested_results', () => variant(e => { e.execution_scope.requested_results = ['改成完整实现并发布']; }));
check('lost_required_obligation', () => {
  const next = structuredClone(events.find(e => e.type === 'scope_revised').execution_scope);
  next.obligations = next.obligations.filter(o => o.id !== 'acceptance-context:candidate');
  return assertRevisionKeepsRequiredObligations(birth, next);
});
const scope = events.find(e => e.type === 'scope_revised').execution_scope;
const acc = scope.obligations.find(o => o.kind === 'acceptance-context');
const binding = acc.satisfied_by.find(s => s.input_id);
const opt = { projectRoot: root, frameworkRoot: native.frameworkRoot, feature, phase: acc.owner_phase, track: 'full', goalRunId: manifest.run_id };
const bindOut = {};
function checkBind(tag, b) {
  try { bindOut[tag] = { ok: true, hasValue: cap.readBoundInput(opt, b) != null }; }
  catch (e) { bindOut[tag] = { ok: false, error: String(e?.message ?? e) }; }
}
checkBind('valid', binding);
const prevManifest = JSON.parse(fs.readFileSync(path.join(path.dirname(runDir), manifest.successor_of, 'manifest.json'), 'utf8'));
const oldBinding = prevManifest.execution_scope.obligations.find(o => o.kind === 'acceptance-context').satisfied_by.find(s => s.input_id);
checkBind('obsolete_pre_revision_acceptance', oldBinding);
const foreign = structuredClone(binding); foreign.source = { kind: 'derive', provider_id: 'not-installed-provider' };
checkBind('foreign_provider', foreign);
const unrelated = structuredClone(binding); unrelated.dependencies[0].path = path.join(root, 'doc', 'requirements', 'unrelated-requirement.txt');
checkBind('unrelated_file', unrelated);
process.stdout.write(JSON.stringify({ revisions: revOut, bindings: bindOut }));
"""


class TheFrozenRequestRecoversAndObserverTracksPerUnitAuthority(unittest.TestCase):
    """S08 正式 900c 完整原生恢复组合、受控中断恢复、观察器逐 CU 权威与正反例：
    1. 独立冻结后先转 attended、设计 owner 修订共同验收并过质询/准入/CU 就绪、原授权有 Plan 义务时用 `--supersede`
       取得 `continuation=successor`，执行 Plan 与真实 harness/receipt，消费 1 笔 `scope_revised`；
    2. 在 `scope_revised` 落盘且 `run_end` 未写时受控终止本地桥接进程，新进程沿同一后继 `--next` 恢复到
       `CHAIN_SLICE_COMPLETED`，无重复作者调用、无 Feature completion；
    3. `observe_target.mjs` 不传 `MAISON_GOAL_RUN_ID` 逐 CU 读出 `Spec: reused`、`Plan: closed/fresh`，
       拒绝旧 summary/错 run_id 串用、回执破坏、失效转交身份，也不被全局 `MAISON_GOAL_RUN_ID` 覆盖别的 CU；
    4. 修订后才事后转交、错误前序指纹、改写请求结果、删除必需义务、过期 acceptance 绑定均被原生拒绝。"""

    @classmethod
    def setUpClass(cls) -> None:
        import textwrap  # noqa: PLC0415
        import time  # noqa: PLC0415
        import test_cu_knowledge_chain as chain  # noqa: PLC0415
        cls._tmp = tempfile.TemporaryDirectory()
        root = cls.root = make_project(root=Path(cls._tmp.name) / "p")
        physical_framework(root)
        unit = cls.unit = root / "doc" / "features" / BLUEPRINT / UNIT
        bp = unit.parent / "blueprint" / "component-blueprint.yaml"
        cu_path = unit / "change-unit.yaml"
        (root / "framework.local.json").write_text(json.dumps({"schema_version": "1.0", "agent_adapter": "codex"}),
                                                   encoding="utf-8")
        # 原始需求文件在初次冻结前就声明异常恢复要求；首版蓝图漏掉它
        src = root / REQUIREMENT
        old_src = src.read_bytes()
        old_bp = bp.read_bytes()
        src.write_bytes(old_src + "\n本次交付止于可读实现方案。服务暂不可用时保留最近一次成功的余额，同时显示该次更新时间；不得将它标为新鲜数据。\n".encode("utf-8"))
        sha = lambda b: "sha256:" + hashlib.sha256(b).hexdigest()  # noqa: E731
        old_ref = yaml.safe_load(old_bp.decode("utf-8"))["discovery"]["inputs"]["current_scope_items"][0]["source_sha256"]
        bp.write_bytes(old_bp.decode("utf-8").replace(old_ref, sha(src.read_bytes())).encode("utf-8"))
        cu_path.write_bytes(cu_path.read_bytes().replace(sha(old_bp).encode(), sha(bp.read_bytes()).encode()))
        draft = textwrap.dedent(chain.design(root, True, pattern="none", nested=False))
        design_fixture.render_projection(root, BLUEPRINT, root / "doc/extensions/base/hooks/shared/framework-access.mjs")
        for rel in EXPLORED:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO_ROOT / "demo" / rel, root / rel)
        subprocess.run(["git", "-C", str(root), "init", "-q"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(root), "add", "doc/features", "doc/requirements",
                        "framework.config.json", "framework.local.json"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(root), "-c", "user.name=fixture", "-c", "user.email=fixture@local",
                        "commit", "-qm", "design baseline"], check=True, capture_output=True)

        entry = "scripts/goal-mode-entry.ts"
        ad = ["--adapter", "codex", "--run-mode", "attended"]
        req = ["--requirement-file", REQUIREMENT]
        # 1) 独立冻结
        scope = native_cli(root, entry, "--project-root", str(root), "--feature", CU, "--prepare-scope",
                           "--completion-target", "request", "--requested-phases", "spec,plan",
                           "--requested-results", "返回刷新设计的可读实现方案", *req)
        assert scope.returncode == 0, scope.stdout[-800:] + scope.stderr[-400:]
        native_cli(root, "harness-runner.ts", "--project-root", str(root), "--feature", CU, "--phase", "plan")
        assert (unit / "execution-scope.json").is_file()

        # 另复制一份未转交快照用于“修订后才事后转交”负例
        post_root = cls.post_root = Path(cls._tmp.name) / "post_transfer"
        shutil.copytree(root, post_root, ignore=lambda d, names: {"node_modules"} if Path(d) == root / "framework" / "harness" else set())
        design_fixture._link_dir(design_fixture.framework_under_test() / "harness" / "node_modules",
                                 post_root / "framework" / "harness" / "node_modules")

        # 2) 改前转交 attended，保留 source run ID
        birth = native_cli(root, entry, "--project-root", str(root), "--feature", CU, "--prepare-run", *ad, *req)
        assert birth.returncode == 0, birth.stdout[-800:] + birth.stderr[-400:]
        cls.source_run_id = json.loads(birth.stdout)["run_id"]
        cls.birth_manifest = json.loads((unit / "goal-runs" / cls.source_run_id / "manifest.json").read_text(encoding="utf-8"))

        # 3) 设计 owner 修订蓝图、登记质询、校验准入与 CU 修订/就绪
        def revise_design(proj: Path) -> tuple[subprocess.CompletedProcess, subprocess.CompletedProcess]:
            p_unit = proj / "doc" / "features" / BLUEPRINT / UNIT
            p_bp = p_unit.parent / "blueprint" / "component-blueprint.yaml"
            p_cu = p_unit / "change-unit.yaml"
            before_txt = p_bp.read_text(encoding="utf-8")
            bcu = p_cu.read_bytes()
            u_doc = yaml.safe_load(bcu)
            base_rev = u_doc["component_blueprint_ref"]["revision"]
            new_rev = base_rev + 1
            needle = "expected_result: 账户卡片展示最新余额"
            assert before_txt.count(needle) == 1
            p_bp.write_bytes(before_txt.replace(f"revision: {base_rev}", f"revision: {new_rev}", 1)
                             .replace(needle, needle + "；服务暂不可用时保留上次余额并显示其更新时间。").encode("utf-8"))
            changed = yaml.safe_load(p_bp.read_bytes())
            q = next(i for i in changed["review_summary"]["questioning"]["items"] if i["scope_ref"] == "view:logical")
            q.update(question="返回首页但余额服务暂不可用时，本期界面的余额和更新时间有什么依据？",
                     answer="原始需求要求保留最后成功的余额并标示该次时间。已补验收；不得把旧值显示为刚刚刷新。",
                     evidence_refs=[REQUIREMENT])
            p_bp.write_text(yaml.safe_dump(changed, allow_unicode=True, sort_keys=False), encoding="utf-8")
            bp_check = native_cli(proj, "scripts/check-component-blueprint.ts", "--project-root", str(proj),
                                  "--blueprint", BLUEPRINT, "--json")
            assert bp_check.returncode == 0, bp_check.stdout[-800:]
            design_fixture.render_projection(proj, BLUEPRINT, proj / "doc/extensions/base/hooks/shared/framework-access.mjs")
            expected = {k: u_doc[k] for k in ("artifact", "component_id", "blueprint_id", "change_unit_id", "revision")}
            expected["artifact_sha256"] = sha(bcu)
            for ref in [u_doc["component_blueprint_ref"], *u_doc["design_refs"],
                        *[m["design_ref"] for m in u_doc.get("touches", []) if "design_ref" in m]]:
                ref.update(revision=new_rev, artifact_sha256=sha(p_bp.read_bytes()))
            rev_proc = subprocess.run(
                ["node", str(proj / "doc/extensions/base/hooks/shared/framework-access.mjs"),
                 "--action", "change-unit-revise", "--project-root", str(proj), "--blueprint", BLUEPRINT],
                input=json.dumps([{"expectedRef": expected,
                                   "candidate": {"providerId": u_doc["provenance"]["extraction_method"], "artifact": u_doc}}],
                                 default=lambda x: x.isoformat()),
                capture_output=True, text=True, encoding="utf-8", timeout=120)
            ready_proc = native_cli(proj, "scripts/check-change-unit.ts", "--project-root", str(proj),
                                    "--blueprint", BLUEPRINT, "--readiness", "--json")
            return rev_proc, ready_proc

        cls.rev_proc, cls.ready_proc = revise_design(root)
        assert cls.rev_proc.returncode == 0 and cls.ready_proc.returncode == 0, cls.rev_proc.stderr + cls.ready_proc.stdout

        # 负例：未提前转交、修订后才事后尝试转交 → 原生拒绝
        post_rev, post_ready = revise_design(post_root)
        assert post_rev.returncode == 0 and post_ready.returncode == 0
        cls.post_transfer = native_cli(post_root, entry, "--project-root", str(post_root), "--feature", CU,
                                       "--prepare-run", *ad, *req)

        # 4) 保全旧阶段输入并按新权威重新准备
        for fname in ("acceptance.yaml", "contracts.yaml"):
            asset = unit / fname
            if asset.exists():
                asset.rename(unit / f"before-{fname}")
        for phase in ("spec", "plan"):
            prep = native_cli(root, "scripts/prepare-blueprint-design.ts", "--project-root", str(root),
                              "--framework-root", str(root / "framework"), "--feature", CU, "--phase", phase)
            assert prep.returncode == 0, prep.stdout[-600:]

        # 5) 后继出生（--supersede）
        sup = native_cli(root, entry, "--project-root", str(root), "--feature", CU,
                         "--prepare-run", "--supersede", cls.source_run_id, *ad, *req)
        assert sup.returncode == 0, sup.stdout[-800:] + sup.stderr[-400:]
        cls.supersede_out = json.loads(sup.stdout)
        cls.successor_id = cls.supersede_out["run_id"]
        cls.successor_manifest = json.loads((unit / "goal-runs" / cls.successor_id / "manifest.json").read_text(encoding="utf-8"))

        # 6) 写 Plan 作者产物 + 拿 --next 签发的身份跑 harness / stand-in verifier / check-receipt
        contracts_file = unit / "contracts.yaml"
        if not contracts_file.exists():
            contracts_file.write_text(
                yaml.safe_dump(yaml.safe_load(draft)["contracts"], allow_unicode=True, sort_keys=False),
                encoding="utf-8")
        APlanClosesThroughTheNativeRequest.author(root, unit)
        facts_md = unit / "context" / "facts.md"
        facts_md.write_text(re.sub(r"(?m)^frozen_scope_fingerprint: [^\n]+$", f"run_id: {cls.successor_id}",
                                   facts_md.read_text(encoding="utf-8")), encoding="utf-8")
        next_args = ["--project-root", str(root), "--feature", CU, *ad, "--run-id", cls.successor_id, "--next"]
        first_next = native_cli(root, entry, *next_args)
        assert first_next.returncode == 0, first_next.stdout[-800:]
        next_doc = json.loads(first_next.stdout)
        req_path = next_doc["request"]["path"]
        ctx = json.loads(Path(req_path).read_text(encoding="utf-8"))["context"]
        owner = ctx["owner"]
        extra = ["--goal-run-id", cls.successor_id, "--goal-attempt-id", ctx["attemptId"],
                 "--goal-owner-id", owner["owner_id"], "--goal-owner-epoch", str(owner["epoch"])]
        h_proc = native_cli(root, "harness-runner.ts", "--project-root", str(root), "--feature", CU, "--phase", "plan", *extra)
        summ = json.loads((unit / "plan" / "reports" / "summary.json").read_text(encoding="utf-8"))
        assert summ.get("verifier_request"), h_proc.stdout[-1500:] + h_proc.stderr[-600:]
        vreq = json.loads((root / summ["verifier_request"]).read_text(encoding="utf-8"))
        vrep = APlanClosesThroughTheNativeRequest.stand_in((root / vreq["prompt_path"]).read_text(encoding="utf-8"),
                                                           vreq["subject_id"])
        (root / summ["verifier_report"]).write_text(vrep, encoding="utf-8")
        rec_proc = native_cli(root, "scripts/check-receipt.ts", "--project-root", str(root), "--feature", CU, "--phase", "plan", *extra)
        assert rec_proc.returncode == 0, rec_proc.stdout[-1500:]

        # 7) 回报作者结果并在观测到 scope_revised 且 run_end 未写时受控中断桥接进程，随后新进程 --next 恢复
        reply = {"phase": ctx["phase"], "status": "passed",
                 "details": "隔离作者已写入修订后的方案契约；阶段与整项结果由原生 harness、receipt 与 runtime 决定。"}
        journal = unit / "goal-runs" / cls.successor_id / "events.jsonl"
        env = {k: v for k, v in os.environ.items() if k != "NODE_OPTIONS"}
        report_cmd = ["node", "node_modules/ts-node/dist/bin.js", "--transpile-only", entry,
                      "--project-root", str(root), "--feature", CU, *ad, "--run-id", cls.successor_id,
                      "--request", req_path, "--report-result", json.dumps(reply, ensure_ascii=False)]
        child = subprocess.Popen(report_cmd, cwd=root / "framework" / "harness", env=env,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        killed = False
        start = time.monotonic()
        while child.poll() is None:
            lines = journal.read_bytes().splitlines() if journal.exists() else []
            if any(b'"type":"scope_revised"' in line.replace(b" ", b"") for line in lines):
                if any(b'"type":"run_end"' in line.replace(b" ", b"") for line in lines):
                    break
                child.kill()
                child.wait(timeout=15)
                killed = True
                break
            if time.monotonic() - start > 120:
                child.kill()
                child.wait(timeout=15)
                break
            time.sleep(0.005)
        child.wait(timeout=120)
        if child.stdout:
            child.stdout.close()
        cls.killed_after_revision = killed
        cls.interrupt_exit_code = child.returncode
        cls.interrupt_outcome = "interrupted" if killed else "completed_without_window"
        cls.events_at_interrupt = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines() if line.strip()]
        cls.resume_next = native_cli(root, entry, *next_args)
        assert cls.resume_next.returncode == 0, cls.resume_next.stdout[-800:] + cls.resume_next.stderr[-400:]
        cls.final_events = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines() if line.strip()]
        cls.final_summary = json.loads((unit / "plan" / "reports" / "summary.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_successor_rebinds_and_recovers_after_interruption_without_feature_completion(self) -> None:
        self.assertEqual("successor", self.supersede_out.get("continuation"))
        self.assertEqual(self.source_run_id, self.successor_manifest.get("successor_of"))
        birth_scope = self.birth_manifest["execution_scope"]
        succ_scope = self.successor_manifest["execution_scope"]
        self.assertEqual(birth_scope["completion_target"], succ_scope["completion_target"])
        self.assertEqual(birth_scope["requested_results"], succ_scope["requested_results"])
        birth_req = {o["id"] for o in birth_scope["obligations"] if o["applicability"] == "required"}
        succ_req = {o["id"] for o in succ_scope["obligations"] if o["applicability"] == "required"}
        self.assertTrue(birth_req.issubset(succ_req), "后继丢失原必需义务")
        # S30/R3：中断取证无条件核验，普通退出不得签中断恢复
        self.assertEqual("interrupted", self.interrupt_outcome,
                         "原桥接进程正常退出未截到 scope_revised 后、run_end 前窗口，按普通完成计，不得签中断恢复")
        self.assertNotEqual(0, self.interrupt_exit_code, "原桥接进程未被终止")
        self.assertEqual(1, sum(1 for e in self.events_at_interrupt if e.get("type") == "scope_revised"),
                         "中断前 journal 须已有 1 笔 scope_revised")
        self.assertFalse(any(e.get("type") == "run_end" for e in self.events_at_interrupt),
                         "中断前 journal 已出现 run_end，不是中断恢复")
        # 恢复后保留原 journal 前缀、经新进程 resume 收口唯一终局、无重复作者调用或 Feature completion
        self.assertEqual(self.events_at_interrupt, self.final_events[:len(self.events_at_interrupt)],
                         "恢复后 journal 改写了中断前原事件")
        tail_types = [e.get("type") for e in self.final_events[len(self.events_at_interrupt):]]
        self.assertIn("resume", tail_types, "恢复后 journal 缺少 resume 事件")
        self.assertEqual(1, sum(1 for e in self.final_events if e.get("type") == "scope_revised"))
        self.assertEqual(1, sum(1 for e in self.final_events if e.get("type") == "agent_invoke_start"),
                         "中断恢复后重复调用了作者")
        self.assertEqual([("plan", "PASS")], [(e["phase"], e["verdict"]) for e in self.final_events if e.get("type") == "phase_verdict"])
        self.assertEqual([("run_end", "CHAIN_SLICE_COMPLETED")],
                         [(e["type"], e.get("status")) for e in self.final_events if e.get("type") == "run_end"])
        self.assertEqual(("PASS", "closed", self.successor_id, "passed"),
                         (self.final_summary["verdict"], self.final_summary["closure_status"],
                          self.final_summary["run_id"], self.final_summary.get("receipt_status")))
        self.assertEqual([], list(self.unit.glob("*feature-completion*")))

    def test_observer_tracks_transferred_cu_without_env_and_rejects_identity_mismatch(self) -> None:
        # 1) 不带 MAISON_GOAL_RUN_ID：逐 CU 读当前转交权威，Spec reused、Plan closed/fresh
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MAISON_GOAL_RUN_ID", None)
            facts = observe(self.root, {"kind": "phase", "phase": "plan"}, feature=BLUEPRINT)
        self.assertTrue(facts["reached"], facts["missing"])
        phases = facts["units"][0]["phases"]
        self.assertEqual("reused", phases["spec"]["state"])
        self.assertEqual("closed", phases["plan"]["state"])
        self.assertEqual("executed", phases["plan"]["native"]["kind"])
        self.assertEqual("fresh", phases["plan"]["native"]["freshness"]["verdict"])

        # 1b) S30/R2：phase-completion-receipt.md 是提交后的尽力人读投影——保留 / 清空 / 移走均判同一已执行 Plan 到达
        receipt_md = self.unit / "plan" / "phase-completion-receipt.md"
        kept_receipt_md = receipt_md.read_bytes()
        try:
            for tag, action in (("清空人读投影", lambda p: p.write_bytes(b"")),
                                ("移走人读投影", lambda p: p.unlink())):
                with self.subTest(tag):
                    action(receipt_md)
                    got = observe(self.root, {"kind": "phase", "phase": "plan"}, feature=BLUEPRINT)
                    self.assertTrue(got["reached"], f"{tag} 不应使已正式收口的 Plan 变未到达：{got['missing']}")
                    self.assertEqual(("reused", "closed", "fresh"),
                                     (got["units"][0]["phases"]["spec"]["state"],
                                      got["units"][0]["phases"]["plan"]["state"],
                                      got["units"][0]["phases"]["plan"]["native"]["freshness"]["verdict"]))
                    receipt_md.write_bytes(kept_receipt_md)
        finally:
            receipt_md.write_bytes(kept_receipt_md)

        # 2) 全局 MAISON_GOAL_RUN_ID 指向其他 CU 的 run 时，不覆盖本 CU 自身转交权威
        with mock.patch.dict(os.environ, {"MAISON_GOAL_RUN_ID": "other-cu-run-999"}):
            isolated = observe(self.root, {"kind": "phase", "phase": "plan"}, feature=BLUEPRINT)
        self.assertTrue(isolated["reached"], isolated["missing"])

        # 3) 反例：旧 summary / 错 run_id 串用 / 正式收口失败 → 生产 end_target.observe 拒绝到达
        summ_path = self.unit / "plan" / "reports" / "summary.json"
        kept_summ = summ_path.read_bytes()
        try:
            for tag, mutate in (
                ("上一代 run_id 串用", lambda d: d.__setitem__("run_id", self.source_run_id)),
                ("无 run_id 旧 summary 串用", lambda d: d.pop("run_id", None)),
                ("receipt_status 非 passed", lambda d: d.__setitem__("receipt_status", "failed")),
                ("closure_status 非 closed", lambda d: d.__setitem__("closure_status", "open")),
            ):
                with self.subTest(tag):
                    doc = json.loads(kept_summ.decode("utf-8"))
                    mutate(doc)
                    summ_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
                    bad = observe(self.root, {"kind": "phase", "phase": "plan"}, feature=BLUEPRINT)
                    self.assertFalse(bad["reached"], f"{tag} 被误判到达")
        finally:
            summ_path.write_bytes(kept_summ)

        # 3b) S30/R2：正式物证过期（context/facts.md 被改或 phase-evidence-manifest.json 缺失）→ 不可到达
        facts_md_path = self.unit / "context" / "facts.md"
        kept_facts_md = facts_md_path.read_bytes()
        manifest_path = self.unit / "plan" / "reports" / "phase-evidence-manifest.json"
        kept_manifest = manifest_path.read_bytes()
        try:
            facts_md_path.write_bytes(kept_facts_md + b"\n- mutated after closure\n")
            stale = observe(self.root, {"kind": "phase", "phase": "plan"}, feature=BLUEPRINT)
            self.assertFalse(stale["reached"], "阶段产物变化后物证应过期")
            self.assertTrue(any("不再新鲜" in m for m in stale["missing"]), stale["missing"])
            facts_md_path.write_bytes(kept_facts_md)
            manifest_path.unlink()
            missing_m = observe(self.root, {"kind": "phase", "phase": "plan"}, feature=BLUEPRINT)
            self.assertFalse(missing_m["reached"], "正式物证清单缺失后不应判到达")
            self.assertTrue(any("不再新鲜" in m for m in missing_m["missing"]), missing_m["missing"])
        finally:
            facts_md_path.write_bytes(kept_facts_md)
            manifest_path.write_bytes(kept_manifest)

        # 4) 反例：失效转交身份（指向不存在的 run）→ scope 报 invalid，不从目录名猜最新
        scope_path = self.unit / "execution-scope.json"
        kept_scope = scope_path.read_bytes()
        try:
            doc = json.loads(kept_scope.decode("utf-8"))
            doc["transfers"][-1]["run_id"] = "20990101T000000Z-missing"
            scope_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            bad = observe(self.root, {"kind": "phase", "phase": "plan"}, feature=BLUEPRINT)
            self.assertFalse(bad["reached"])
            self.assertTrue(any("执行范围读不出" in m for m in bad["missing"]), bad["missing"])
        finally:
            scope_path.write_bytes(kept_scope)

    def test_post_revision_transfer_and_tampered_revisions_or_bindings_are_rejected(self) -> None:
        # 1) 未提前转交、修订后才事后尝试转交被原生旧 binding 拒绝
        self.assertNotEqual(0, self.post_transfer.returncode, "修订后事后转交不应绕过旧 binding 检查")
        # 2) 原生修订链与绑定直接反例
        run_dir = self.unit / "goal-runs" / self.successor_id
        proc = subprocess.run(["node", "--input-type=module", "-e", S08_NATIVE_CONTROLS,
                               str(self.root), CU, str(run_dir)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, proc.returncode, proc.stderr[-800:])
        got = json.loads(proc.stdout)
        self.assertEqual({"ok": True, "value": 1}, got["revisions"]["control"])
        for neg in ("wrong_previous_fingerprint", "changed_requested_results", "lost_required_obligation"):
            self.assertFalse(got["revisions"][neg]["ok"], f"原生未拒绝修订反例 {neg}: {got['revisions'][neg]}")
        self.assertTrue(got["bindings"]["valid"]["ok"])
        for neg in ("obsolete_pre_revision_acceptance", "foreign_provider", "unrelated_file"):
            self.assertFalse(got["bindings"][neg]["ok"], f"原生未拒绝绑定反例 {neg}: {got['bindings'][neg]}")


if __name__ == "__main__":
    unittest.main()
