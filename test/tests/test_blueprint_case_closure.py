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

STORY_BUILD = "doc/extensions/skills/story/scripts/core/story-build.mjs"
UNIT = "balance-refresh"

RENDER = """
import * as path from 'node:path';
import { pathToFileURL } from 'node:url';
const [root, blueprint] = process.argv.slice(1);
const { loadNative } = await import(pathToFileURL(path.join(root, 'doc/extensions/hooks/shared/framework-access.mjs')).href);
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
        """授权到哪个阶段就请求哪个阶段，执行链由原生派生：蓝图验收齐时只请求 Spec，原生仍要执行 Plan——
        超出只要 Spec 的授权，按第六节停下照实说明；只请求 Plan 时链与授权一致。"""
        for phase, proc in self.single.items():
            with self.subTest(phase=phase):
                self.assertEqual(0, proc.returncode, proc.stdout[-1500:] + proc.stderr[-800:])
                self.assertEqual(["plan"], last_json(proc.stdout)["phase_chain"])
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
const { loadNative } = await import(pathToFileURL(path.join(root, 'doc/extensions/hooks/shared/framework-access.mjs')).href);
process.stdout.write(loadNative(root).module('scripts/utils/execution-scope.ts')
  .executionScopeFingerprint(JSON.parse(fs.readFileSync(file, 'utf8')).execution_scope));
"""
REVIEW_INPUTS = """
import { pathToFileURL } from 'node:url';
const [root, feature] = process.argv.slice(1);
const { reviewInputs } = await import(pathToFileURL(root + '/doc/extensions/hooks/shared/review-inputs.mjs').href);
const b = reviewInputs(root, feature, 'plan');
process.stdout.write(JSON.stringify({ inputs: b.inputs.map(({ key, required, missing, output }) => ({ key, required, missing, output: !!output })),
  gaps: b.gaps }));
"""
FREEZE = """
import * as path from 'node:path';
import { pathToFileURL } from 'node:url';
const [root, feature] = process.argv.slice(1);
const { loadNative } = await import(pathToFileURL(path.join(root, 'doc/extensions/hooks/shared/framework-access.mjs')).href);
const n = loadNative(root);
const frozen = n.module('scripts/utils/feature-execution-scope.ts').ensureFeatureExecutionScopeFrozen({ projectRoot: root, frameworkRoot: n.frameworkRoot, feature });
if (!['frozen', 'reused'].includes(frozen.status)) { process.stderr.write(JSON.stringify(frozen)); process.exit(1); }
"""


def review_inputs(root: Path) -> dict:
    proc = subprocess.run(["node", "--input-type=module", "-e", REVIEW_INPUTS, str(root), CU], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300)
    assert proc.returncode == 0, proc.stderr[-600:]
    return json.loads(proc.stdout)


REPORT_CHECK = """
import { pathToFileURL } from 'node:url';
const [root, feature] = process.argv.slice(1);
const { reportProblems } = await import(pathToFileURL(root + '/doc/extensions/hooks/shared/verifier-report.mjs').href);
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
        native_cli(root, "harness-runner.ts", "--project-root", str(root), "--phase", "plan", "--feature", CU)
        cls.author(root, unit)
        cls.harness = native_cli(root, "harness-runner.ts", "--project-root", str(root), "--phase", "plan", "--feature", CU)
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
            'key_inputs_read:\n  - "paths.module_catalog — 已读"\n  - "doc/extensions/hooks/plan/author.md — 已读"\n'
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
        """送审终点：交付门通过之外，发布记录与已发布副本是当前 Story、Review 与设计参考（蓝图的原生评审投影），
        需求系统上的正文与两个附件逐字是这三件。"""
        self.reviewed("pass")
        self.assertEqual(0, self.register().returncode)
        system = self.root.parent / "system"

        def submitted() -> dict:
            return observe(self.root, SUBMITTED, feature="REQ-DEMO", blueprint=None,
                           story_build=str(DEV_STORY_BUILD), system_dir=system)

        self.assertIn("还没送审", submitted()["missing"][0])
        # 对接层逐件上传并读回：取材回执里三件记这一版的读回
        items = [{"name": name, "status": "fetched", "checkedAt": "2099-01-01T00:00:00+00:00",
                  "digest": "sha256:" + hashlib.sha256((self.story.parent.parent / local).read_bytes()).hexdigest()[:16]}
                 for name, local in (("AR-design.md", "AR/story.md"), ("review.md", "AR/review.md"),
                                     ("design-review.md", "blueprint/component-blueprint.review.md"))]
        # 发布前核对记下的这一次交付集合（三件：本单的交付请求带了设计参考）
        delivery = {"prepared_at": "2099-01-01T00:00:00+00:00", "items": [
            {"name": i["name"], "local": local, "digest": i["digest"]}
            for i, local in zip(items, ("AR/story.md", "AR/review.md", "blueprint/component-blueprint.review.md"))]}
        (self.story.parent / "story-src" / "fetched.json").write_text(
            json.dumps({"fetchedAt": "2099-01-01T00:00:00+00:00", "items": items, "delivery": delivery}), encoding="utf-8")
        archived = subprocess.run(["python", str(self.FLOW), "archived", "--feature", "REQ-DEMO",
                                   "--project-root", str(self.root)],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, archived.returncode, archived.stdout + archived.stderr)
        self.assertIn("正文", submitted()["missing"][0], "只登记了归档、系统上没有正文，不算送审")

        # 对接层上传后的需求系统：正文是 Story，评审记录是附件
        review = self.story.parent / "review.md"
        ticket = system / "REQ-DEMO"
        attachment = ticket / "attachments" / "review.md"
        attachment.parent.mkdir(parents=True)
        (ticket / "design.md").write_bytes(self.story.read_bytes())
        (ticket / "attachments" / "design-review.md").write_bytes(
            (self.story.parent.parent / "blueprint" / "component-blueprint.review.md").read_bytes())
        for stale, why in ((b"", "空附件"), (review.read_bytes() + "上一版的评审记录。\n".encode("utf-8"), "旧附件")):
            attachment.write_bytes(stale)
            self.assertTrue(any("评审记录附件" in m for m in submitted()["missing"]), f"{why}被当成送到了")
        attachment.write_bytes(review.read_bytes())

        def snapshot() -> dict[str, bytes]:
            return {**self.tree(), **{f"system/{p.relative_to(system).as_posix()}": p.read_bytes()
                                      for p in system.rglob("*") if p.is_file()}}

        before = snapshot()
        for _ in range(2):
            reached = submitted()
            self.assertTrue(reached["reached"], reached["missing"])
        self.assertEqual({"ok": True, "kind": "submitted"}, reached["delivery"])
        self.assertEqual(before, snapshot(), "重复观察写了文件")

        (ticket / "design.md").write_bytes(self.story.read_bytes() + "系统上被改过。\n".encode("utf-8"))
        self.assertFalse(submitted()["reached"], "系统上的正文不是当前这一版")
        (ticket / "design.md").write_bytes(self.story.read_bytes())

        # 只改了 Review、Story 没动：系统上也换成新 Review，旧的发布记录仍不代表这一版送审过
        review.write_bytes(review.read_bytes() + "归档之后改的一句。\n".encode("utf-8"))
        attachment.write_bytes(review.read_bytes())
        missing = end_target.story_submitted(self.root, "doc/features", "REQ-DEMO", system)
        self.assertTrue(any("发布记录里的 Review" in m for m in missing), missing)
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


if __name__ == "__main__":
    unittest.main()
