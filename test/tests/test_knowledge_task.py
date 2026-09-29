"""原生身份读取与动作前知识任务（步骤 1）：在接入 demo Framework 的临时工程里，用真实蓝图与施工单位跑。

锁五件：蓝图与施工单位按 Framework 原生身份读，坏身份、缺对象、过期引用各自报出；阶段输入走原生当前阶段的
只读解析，选哪份输入、过期与 invalid 都照原生，范围未冻结时不代为冻结；知识任务六块齐全、知识原文按激活顺序
完整给出，空清单与坏登记分开；必需输入缺失或损坏时 stdout 不给半份、stderr 写对象、缺口与责任；审查者经
pre_verifier 拿到的是同一个加载器出的任务。
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from ext_workspace import DEV_SOURCE, REPO_ROOT, link_framework

sys.path.insert(0, str(REPO_ROOT / "test" / "scripts"))
import publish_to_demo  # noqa: E402

FIXTURE = REPO_ROOT / "test" / "fixtures" / "blueprint" / "wallet-balance-refresh"
BLUEPRINT = "wallet-balance-refresh"


def cu_id(blueprint: str, unit: str) -> str:
    """Framework 的施工单位 Feature id：`cu-` + base64url（蓝图 id NUL 单位 id），不带填充。"""
    return "cu-" + base64.urlsafe_b64encode(f"{blueprint}\0{unit}".encode()).decode().rstrip("=")


CU = cu_id(BLUEPRINT, "balance-refresh")


def make_project(features_dir: str = "doc/features") -> Path:
    """接入 demo Framework、装好开发版扩展、放进夹具蓝图与施工单位的临时工程。"""
    root = Path(tempfile.mkdtemp(prefix="story-kt-")) / "p"
    root.mkdir()
    config = json.loads((REPO_ROOT / "demo" / "framework.config.json").read_text(encoding="utf-8"))
    config.setdefault("paths", {})["features_dir"] = features_dir
    (root / "framework.config.json").write_text(json.dumps(config), encoding="utf-8")
    link_framework(root)
    result = publish_to_demo.install_extension(DEV_SOURCE, root)
    if result.status != "installed":
        raise RuntimeError(f"开发版装不进临时工程：{result.problems}")
    shutil.copytree(FIXTURE / "doc" / "features", root / features_dir, dirs_exist_ok=True)
    if features_dir != "doc/features":
        # 夹具施工单位的来源路径按默认需求目录写；换目录时来源路径随之换，身份与引用不变
        unit = root / features_dir / BLUEPRINT / "balance-refresh" / "change-unit.yaml"
        unit.write_text(unit.read_text(encoding="utf-8").replace("source_ref: doc/features/", f"source_ref: {features_dir}/"),
                        encoding="utf-8")
    shutil.copytree(FIXTURE / "doc" / "requirements", root / "doc" / "requirements", dirs_exist_ok=True)
    # 蓝图的开发视图按工程的模块目录解析模块：用 demo 的那份，夹具蓝图写的是 demo 的模块
    shutil.copy2(REPO_ROOT / "demo" / "doc" / "module-catalog.yaml", root / "doc" / "module-catalog.yaml")
    return root


#: 夹具范围候选的影响依据：CU 契约写集里的一份 demo 业务源码
IMPACT_BASIS = "02-Feature/WalletMain/src/main/ets/data/repository/HomeRepository.ets"

PREPARE = """
import * as fs from 'node:fs';
import * as path from 'node:path';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
const [root, feature, action, basis, REQUIREMENT] = process.argv.slice(1);
const { loadNative } = await import(pathToFileURL(path.join(root, 'doc/extensions/hooks/shared/framework-access.mjs')).href);
const native = loadNative(root);
if (action === 'materialize') {
  native.module('scripts/utils/blueprint-skill-projection.ts').materializeBlueprintSkillInputs(root, feature, native.frameworkRoot);
} else if (action === 'edit') {
  const file = native.module('config.ts').resolveFeatureArtifact(root, feature, 'contracts.yaml').actualPath;
  const YAML = native.require('yaml');
  const value = YAML.parse(fs.readFileSync(file, 'utf8'));
  (value.components ??= []).push({ name: 'LocalOwner', file: value.files[0], kind: 'page',
    must: [{ rule: 'LOCAL-1', text: '本地加的义务', verify: 'ut' }] });
  fs.writeFileSync(file, YAML.stringify(value));
} else {
  // 需求按来源文件给（候选记下来源），或 inline 给正文（候选只记正文指纹）
  const requirement = action.endsWith('-inline')
    ? ['--requirement', fs.readFileSync(path.join(root, REQUIREMENT), 'utf8').trim()] : ['--requirement-file', REQUIREMENT];
  const prep = spawnSync(process.execPath, [path.join(native.harness, 'node_modules/ts-node/dist/bin.js'), '--transpile-only',
    path.join(native.harness, 'scripts/goal-mode-entry.ts'), '--project-root', root, '--feature', feature, '--prepare-scope',
    '--completion-target', 'feature', '--requested-results', '返回首页余额刷新', '--requested-phases', 'spec,plan,coding,review,ut',
    ...requirement, '--impact-behavior-change', 'true',
    '--impact-reason', '用户可见余额展示变化', '--impact-basis', basis], { cwd: native.harness, encoding: 'utf8' });
  if (prep.status !== 0) { process.stderr.write(prep.stdout + prep.stderr); process.exit(1); }
  if (action.startsWith('candidate')) process.exit(0);
  const frozen = native.module('scripts/utils/feature-execution-scope.ts')
    .ensureFeatureExecutionScopeFrozen({ projectRoot: root, frameworkRoot: native.frameworkRoot, feature });
  if (!['frozen', 'reused'].includes(frozen.status)) { process.stderr.write(JSON.stringify(frozen.checks)); process.exit(1); }
}
"""


#: 夹具蓝图的来源需求；范围候选默认也用它作需求来源
REQUIREMENT = "doc/requirements/wallet-balance-refresh.md"


def prepare(root: Path, action: str, feature: str = CU, requirement: str = REQUIREMENT) -> None:
    """测试准备，只用原生入口：materialize 物化施工输入、edit 改本地契约字节、candidate 只生成范围候选、
    freeze 生成候选并冻结；带 -inline 的两种把需求正文直接交给 prepare-scope，候选里不记来源文件。"""
    if action.startswith(("freeze", "candidate")):
        (root / IMPACT_BASIS).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / "demo" / IMPACT_BASIS, root / IMPACT_BASIS)
    proc = subprocess.run(["node", "--input-type=module", "-e", PREPARE, str(root), feature, action, IMPACT_BASIS, requirement],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(f"准备 {action} 失败：{proc.stderr[-800:]}")


def files_under(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


class NativeCase(unittest.TestCase):
    root: Path

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("环境里没有 node")
        cls.root = make_project()

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.root.parent, ignore_errors=True)

    @property
    def ext(self) -> Path:
        return self.root / "doc" / "extensions"

    def node(self, script: str, *args: str, root: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(["node", str(self.ext / script), "--project-root", str(root or self.root), *args],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)

    def access(self, *args: str, root: Path | None = None) -> tuple[int, dict]:
        proc = self.node("hooks/shared/framework-access.mjs", *args, root=root)
        return proc.returncode, (json.loads(proc.stdout) if proc.stdout.strip() else {})

    def task(self, *args: str) -> subprocess.CompletedProcess:
        return self.node("hooks/shared/knowledge-task.mjs", *args)


class BlueprintAndUnitIdentity(NativeCase):
    def test_an_admitted_blueprint_reads_with_its_full_reference(self) -> None:
        code, out = self.access("--action", "blueprint", "--blueprint", BLUEPRINT, "--purpose", "delivery")
        self.assertEqual((0, "ok"), (code, out["status"]), out)
        self.assertTrue(out["admitted"])
        ref = out["blueprint_ref"]
        self.assertEqual({"kind": "blueprint", "id": BLUEPRINT}, ref["target"])
        for key in ("component_id", "revision", "source_fingerprint", "artifact_sha256"):
            self.assertTrue(ref[key], key)

    def test_a_unit_before_its_scope_is_frozen_has_identity_but_no_phase_inputs(self) -> None:
        """范围未冻结：身份、蓝图引用与承担的设计对象都在；本阶段输入不由 Extension 自己派生顶上。"""
        code, out = self.access("--action", "feature", "--feature", CU, "--phase", "plan")
        self.assertEqual((0, "ok"), (code, out["status"]), out)
        self.assertEqual({"kind": "cu", "blueprintId": BLUEPRINT, "changeUnitId": "balance-refresh"},
                         {k: out["identity"][k] for k in ("kind", "blueprintId", "changeUnitId")})
        self.assertEqual("doc/features/wallet-balance-refresh/balance-refresh", out["feature_path"])
        self.assertTrue(out["design_refs"])
        self.assertEqual(("not_frozen", {}), (out["scope"], out["inputs"]))
        self.assertFalse((self.root / out["feature_path"] / "execution-scope.json").exists(), "读取代为冻结了范围")

    def test_bad_identities_and_missing_objects_fail_with_native_codes(self) -> None:
        cases = {
            ("--action", "blueprint", "--blueprint", "../evil"): ("invalid", "blueprint_id_invalid"),
            ("--action", "blueprint", "--blueprint", "not-there"): ("missing", "component_blueprint_missing"),
            ("--action", "feature", "--feature", "cu-!!!", "--phase", "plan"): ("invalid", "change_unit_feature_id_invalid"),
            ("--action", "feature", "--feature", "no-such-flat", "--phase", "coding"): ("missing", "feature_missing"),
        }
        for args, (status, code) in cases.items():
            with self.subTest(args=args):
                exit_code, out = self.access(*args)
                self.assertEqual((1, status), (exit_code, out.get("status")), out)
                self.assertEqual(code, out["issues"][0]["code"])

    def test_a_same_named_unit_under_another_blueprint_is_not_this_one(self) -> None:
        """两个蓝图下同名施工单位是两个身份：另一个蓝图没有这个单位，读它失败，不落到本蓝图的那一份上。"""
        other = cu_id("other-blueprint", "balance-refresh")
        self.assertNotEqual(CU, other)
        code, out = self.access("--action", "feature", "--feature", other, "--phase", "plan")
        self.assertEqual(1, code, out)

    def test_two_blueprints_with_a_same_named_unit_each_resolve_to_their_own(self) -> None:
        """两个真实蓝图下都有 balance-refresh：各自按身份读到自己的蓝图与引用，不混用。"""
        second = "wallet-balance-refresh-b"
        src = self.root / "doc/features" / BLUEPRINT
        dst = self.root / "doc/features" / second
        shutil.copytree(src, dst)
        self.addCleanup(shutil.rmtree, dst, True)
        canonical = dst / "blueprint" / "component-blueprint.yaml"
        canonical.write_bytes(canonical.read_bytes().replace(
            f"blueprint_id: {BLUEPRINT}\n".encode(), f"blueprint_id: {second}\n".encode(), 1))
        old_sha = "sha256:" + hashlib.sha256((src / "blueprint" / "component-blueprint.yaml").read_bytes()).hexdigest()
        new_sha = "sha256:" + hashlib.sha256(canonical.read_bytes()).hexdigest()
        unit = dst / "balance-refresh" / "change-unit.yaml"
        text = unit.read_text(encoding="utf-8").replace(f"blueprint_id: {BLUEPRINT}\n", f"blueprint_id: {second}\n")
        text = text.replace(f"id: {BLUEPRINT}\n", f"id: {second}\n").replace(
            f"features/{BLUEPRINT}/blueprint/component-blueprint.yaml#blueprint:{BLUEPRINT}",
            f"features/{second}/blueprint/component-blueprint.yaml#blueprint:{second}").replace(old_sha, new_sha)
        unit.write_text(text, encoding="utf-8")
        for blueprint in (BLUEPRINT, second):
            with self.subTest(blueprint=blueprint):
                code, out = self.access("--action", "feature", "--feature", cu_id(blueprint, "balance-refresh"), "--phase", "plan")
                self.assertEqual((0, "ok"), (code, out.get("status")), out)
                self.assertEqual((blueprint, blueprint), (out["identity"]["blueprintId"], out["blueprint_ref"]["blueprint_id"]))
                self.assertEqual(f"doc/features/{blueprint}/balance-refresh", out["feature_path"])

    def test_a_unit_whose_blueprint_changed_is_stale(self) -> None:
        canonical = self.root / "doc/features" / BLUEPRINT / "blueprint" / "component-blueprint.yaml"
        original = canonical.read_bytes()
        self.addCleanup(canonical.write_bytes, original)
        canonical.write_bytes(original + b"\n# changed after the unit was prepared\n")
        code, out = self.access("--action", "feature", "--feature", CU, "--phase", "plan")
        self.assertEqual((1, "stale"), (code, out.get("status")), out)

    def test_arguments_are_checked_before_anything_is_read(self) -> None:
        for args in (("--action", "feature"), ("--action", "feature", "--feature", CU),
                     ("--action", "blueprint", "--blueprint", BLUEPRINT, "--purpose", "x"),
                     ("--action", "other")):
            with self.subTest(args=args):
                self.assertEqual(2, self.access(*args)[0])


class ACustomFeaturesDirIsFollowed(unittest.TestCase):
    def test_blueprint_and_unit_resolve_under_the_configured_dir(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        root = make_project("work/features")
        self.addCleanup(shutil.rmtree, root.parent, True)
        self.assertFalse((root / "doc" / "features").exists())
        script = root / "doc/extensions/hooks/shared/framework-access.mjs"
        run = lambda *a: subprocess.run(["node", str(script), "--project-root", str(root), *a],
                                        capture_output=True, text=True, encoding="utf-8")
        blueprint = json.loads(run("--action", "blueprint", "--blueprint", BLUEPRINT).stdout)
        self.assertEqual("work/features/wallet-balance-refresh/blueprint/component-blueprint.yaml", blueprint["canonical_path"])
        prepare(root, "freeze")
        unit = json.loads(run("--action", "feature", "--feature", CU, "--phase", "plan").stdout)
        self.assertEqual(("ok", "work/features/wallet-balance-refresh/balance-refresh"), (unit["status"], unit["feature_path"]))
        self.assertEqual(("frozen", "resolved"), (unit["scope"], unit["inputs"]["contracts"]["state"]))
        self.assertFalse((root / "doc" / "features").exists(), "读取造出了默认需求目录")


class FreshProject(unittest.TestCase):
    """每条用例一个新工程：范围冻结只能做一次，各用例要自己的候选与冻结记录。"""

    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        self.root = make_project()
        self.addCleanup(shutil.rmtree, self.root.parent, True)

    def run_script(self, script: str, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["node", str(self.root / "doc/extensions/hooks/shared" / script), "--project-root", str(self.root), *args],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)

    def feature(self, phase: str) -> tuple[int, dict]:
        proc = self.run_script("framework-access.mjs", "--action", "feature", "--feature", CU, "--phase", phase)
        return proc.returncode, json.loads(proc.stdout)


class PhaseInputsComeFromTheNativeResolver(FreshProject):
    """范围冻结后，本阶段输入按原生阶段解析：选哪份、过期、invalid 与必需能力缺失都照原生，读取不写任何东西。"""

    def test_the_blueprint_derivation_is_what_the_resolver_selects_before_local_inputs_exist(self) -> None:
        prepare(self.root, "freeze")
        code, out = self.feature("plan")
        self.assertEqual((0, "ok", "frozen"), (code, out["status"], out["scope"]), out)
        self.assertEqual("derive", out["inputs"]["contracts"]["binding"]["kind"])
        task = self.run_script("knowledge-task.mjs", "--feature", CU, "--action", "plan", "--audience", "author")
        self.assertEqual(0, task.returncode, task.stderr)
        self.assertIn("契约来自 derive", task.stdout)

    def test_a_materialized_local_contract_is_what_the_resolver_selects(self) -> None:
        prepare(self.root, "materialize")
        prepare(self.root, "freeze")
        code, out = self.feature("plan")
        self.assertEqual((0, "ok"), (code, out["status"]), out)
        self.assertEqual({"kind": "artifact", "artifact": "contracts@1"}, out["inputs"]["contracts"]["binding"])

    def test_a_local_contract_changed_after_freezing_is_not_replaced_by_the_blueprint(self) -> None:
        """原生判过期的本地契约，不能借蓝图派生变绿；知识任务失败、不给半份，读取不写任何东西。"""
        prepare(self.root, "materialize")
        prepare(self.root, "freeze")
        prepare(self.root, "edit")
        features = self.root / "doc" / "features"
        state = REPO_ROOT / "demo" / "framework" / "harness" / "state"
        before, state_before = files_under(features), sorted(p.name for p in state.iterdir())
        for phase in ("plan", "review"):
            with self.subTest(phase=phase):
                code, out = self.feature(phase)
                self.assertEqual((1, "invalid"), (code, out["status"]), out)
                self.assertIn("stale", json.dumps(out["issues"], ensure_ascii=False))
                task = self.run_script("knowledge-task.mjs", "--feature", CU, "--action", phase, "--audience", "author")
                self.assertEqual((1, ""), (task.returncode, task.stdout))
                self.assertIn("缺口：", task.stderr)
        self.assertEqual(before, files_under(features), "读取写了需求目录")
        self.assertEqual(state_before, sorted(p.name for p in state.iterdir()), "读取写了 harness 状态")

    def test_a_phase_the_native_resolver_blocks_fails_the_task(self) -> None:
        """原生判本阶段缺必需能力（无 run 的 coding 缺需求正文）：照原生结论失败，不当作空义务。"""
        prepare(self.root, "freeze")
        code, out = self.feature("coding")
        self.assertEqual((1, "invalid", "blocked"), (code, out["status"], out["assurance"]), out)
        self.assertEqual("capability_blocked", out["issues"][0]["code"])
        task = self.run_script("knowledge-task.mjs", "--feature", CU, "--action", "coding", "--audience", "author")
        self.assertEqual((1, ""), (task.returncode, task.stdout))

    def test_the_reviewer_is_told_when_its_task_cannot_be_read(self) -> None:
        prepare(self.root, "materialize")
        prepare(self.root, "freeze")
        prepare(self.root, "edit")
        probe = ("const m = (await import(process.argv[1])).default;"
                 "const out = await m({ phase: 'review', feature: process.argv[2], projectRoot: process.argv[3] });"
                 "process.stdout.write(out.promptFragments.join('\\n\\n'));")
        module = (self.root / "doc/extensions/hooks/shared/pre_verifier.mjs").resolve().as_uri()
        proc = subprocess.run(["node", "--input-type=module", "-e", probe, module, CU, str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("## 知识任务（取不到）", proc.stdout)
        self.assertIn("未验证", proc.stdout)
        self.assertNotIn("# 知识任务：review（审查者）", proc.stdout)


#: 原生 harness 无 run 的 spec 在阶段解析前恢复需求的那一段（harness-runner.ts 的 runlessRequirement），照原样调用：
#: 候选的需求绑定 → 显式需求或唯一来源文件 → 按绑定核对 → 带需求组装入口 → 阶段解析。
NATIVE_SPEC = """
import * as path from 'node:path';
import { pathToFileURL } from 'node:url';
const [root, feature, explicit] = process.argv.slice(1);
const { loadNative } = await import(pathToFileURL(path.join(root, 'doc/extensions/hooks/shared/framework-access.mjs')).href);
const n = loadNative(root);
const binding = n.module('scripts/utils/feature-track.ts').featureRequirementBinding(root, feature);
const rel = n.module('scripts/utils/project-relative-path.ts');
const legacyRoot = rel.inferLegacyProjectRoot(root, binding);
const { resolveRequirementInput } = n.module('scripts/utils/goal-manifest.ts');
const sources = binding.dependencies.filter(d => d.exists).map(d => rel.resolveDependencyPath(root, d.path, legacyRoot));
const req = explicit ? resolveRequirementInput({ requirement: explicit, projectRoot: root })
  : resolveRequirementInput({ requirementFile: sources[0], projectRoot: root });
const cr = n.module('scripts/utils/capability-resolution.ts');
cr.readBoundInput({ frameworkRoot: n.frameworkRoot, projectRoot: root, feature, phase: 'spec', track: 'full', requirement: req.text,
  requirementSourceFiles: binding.dependencies.length ? req.sources : [],
  inputContext: { schema_version: '1.1', subject: { feature }, obligations: {}, required_outputs: [] } }, binding, legacyRoot);
const args = { frameworkRoot: n.frameworkRoot, projectRoot: root, feature, phase: 'spec', featuresDir: 'doc/features',
  requirement: req.text, requirementSourceFiles: req.sources };
const entry = n.module('scripts/utils/capability-resolution-entry-input.ts').resolveCapabilityResolutionEntryInput(args);
const track = n.module('scripts/utils/runtime-policy.ts').resolveFeatureTrack(n.module('scripts/utils/feature-track.ts').loadFeatureTrackDecl(root, feature));
const r = cr.resolveCapabilityInputs({ ...args, track, ...entry });
process.stdout.write(JSON.stringify({ assurance: r.report.assurance, requirement: r.inputs?.values?.requirement?.state,
  blocked: r.report.capabilities.filter(c => c.state === 'blocked').map(c => c.id) }));
"""


class SpecRecoversTheRequirementLikeTheNativeHarness(FreshProject):
    """无 run 的 spec：需求正文按冻结候选的来源恢复并核对后再交给阶段解析，与原生 harness 同结果；恢复不出时要调用方给原文。"""

    def native_spec(self, explicit: str = "") -> dict:
        proc = subprocess.run(["node", "--input-type=module", "-e", NATIVE_SPEC, str(self.root), CU, explicit],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, proc.returncode, proc.stderr[-800:])
        return json.loads(proc.stdout)

    def spec(self, *extra: str) -> tuple[int, dict]:
        proc = self.run_script("framework-access.mjs", "--action", "feature", "--feature", CU, "--phase", "spec", *extra)
        return proc.returncode, json.loads(proc.stdout)

    def requirement_text(self) -> str:
        return (self.root / "doc/requirements/wallet-balance-refresh.md").read_text(encoding="utf-8").strip()

    def test_a_file_bound_spec_resolves_as_the_native_harness_does(self) -> None:
        prepare(self.root, "freeze")
        native = self.native_spec()
        self.assertEqual(("full", "resolved", []), (native["assurance"], native["requirement"], native["blocked"]))
        code, out = self.spec()
        self.assertEqual((0, "ok", native["assurance"]), (code, out["status"], out["assurance"]), out)
        task = self.run_script("knowledge-task.mjs", "--feature", CU, "--action", "spec", "--audience", "author")
        self.assertEqual(0, task.returncode, task.stderr)
        self.assertNotIn("预览", task.stdout.splitlines()[0])

    def test_a_requirement_source_changed_after_freezing_is_stale(self) -> None:
        """需求来源是一份只给这次请求用的文件（夹具需求同时是蓝图来源，改它先让蓝图失效）。"""
        request = "doc/requirements/balance-refresh-request.md"
        shutil.copy2(self.root / REQUIREMENT, self.root / request)
        prepare(self.root, "freeze", requirement=request)
        code, out = self.spec()
        self.assertEqual((0, "ok"), (code, out["status"]), out)
        source = self.root / request
        source.write_bytes(source.read_bytes() + "\n补一句冻结后才加的需求。\n".encode("utf-8"))
        code, out = self.spec()
        self.assertEqual((1, "invalid", "requirement_stale"), (code, out["status"], out["issues"][0]["code"]), out)
        self.assertIn("stale", out["issues"][0]["message"])
        task = self.run_script("knowledge-task.mjs", "--feature", CU, "--action", "spec", "--audience", "author")
        self.assertEqual((1, ""), (task.returncode, task.stdout))
        self.assertIn("不换一份需求顶上", task.stderr)

    def test_an_inline_requirement_is_asked_for_and_checked_against_the_binding(self) -> None:
        prepare(self.root, "freeze-inline")
        code, out = self.spec()
        self.assertEqual((1, "requirement_text_needed"), (code, out["issues"][0]["code"]), out)
        task = self.run_script("knowledge-task.mjs", "--feature", CU, "--action", "spec", "--audience", "author")
        self.assertEqual((1, ""), (task.returncode, task.stdout))
        self.assertIn("--requirement-file", task.stderr)
        code, out = self.spec("--requirement", "另一句不是冻结时的需求")
        self.assertEqual((1, "requirement_stale"), (code, out["issues"][0]["code"]), out)
        native = self.native_spec(self.requirement_text())
        for extra in (("--requirement", self.requirement_text()),
                      ("--requirement-file", "doc/requirements/wallet-balance-refresh.md")):
            with self.subTest(given=extra[0]):
                code, out = self.spec(*extra)
                self.assertEqual((0, "ok", native["assurance"]), (code, out["status"], out["assurance"]), out)
                task = self.run_script("knowledge-task.mjs", "--feature", CU, "--action", "spec", "--audience", "author", *extra)
                self.assertEqual(0, task.returncode, task.stderr)

    def test_the_reviewer_gets_the_spec_task_on_the_same_object(self) -> None:
        prepare(self.root, "freeze")
        probe = ("const m = (await import(process.argv[1])).default;"
                 "const out = await m({ phase: 'spec', feature: process.argv[2], projectRoot: process.argv[3] });"
                 "process.stdout.write(out.promptFragments.join('\\n\\n'));")
        module = (self.root / "doc/extensions/hooks/shared/pre_verifier.mjs").resolve().as_uri()
        proc = subprocess.run(["node", "--input-type=module", "-e", probe, module, CU, str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("# 知识任务：spec（审查者）", proc.stdout)
        self.assertNotIn("取不到", proc.stdout)

    def test_the_first_phase_is_prepared_natively_before_the_task_is_used(self) -> None:
        """首阶段：候选有了、范围未冻结时任务只是预览；照 story-knowledge Skill 给的原生准备命令冻结后，重取得到真实输入。"""
        prepare(self.root, "candidate")
        task = self.run_script("knowledge-task.mjs", "--feature", CU, "--action", "spec", "--audience", "author")
        self.assertEqual(0, task.returncode, task.stderr)
        self.assertIn("预览，执行范围未冻结", task.stdout.splitlines()[0])
        skill = (self.root / "doc/extensions/skills/story-knowledge/SKILL.md").read_text(encoding="utf-8")
        command = re.search(r"```\s*\n\s*(node -e .+?)\s*\n\s*```", skill, re.S).group(1)
        script = shlex.split(command.replace("<工程根> <Feature id>", ""))[2]
        harness = self.root / "framework" / "harness"
        frozen = subprocess.run(["node", "-e", script, str(self.root), CU], cwd=harness,
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, frozen.returncode, frozen.stdout + frozen.stderr)
        self.assertEqual("frozen", json.loads(frozen.stdout)["status"])
        for phase in ("spec", "plan"):
            with self.subTest(phase=phase):
                code, out = self.feature(phase)
                self.assertEqual((0, "ok", "frozen"), (code, out["status"], out["scope"]), out)
                task = self.run_script("knowledge-task.mjs", "--feature", CU, "--action", phase, "--audience", "author")
                self.assertEqual(0, task.returncode, task.stderr)
                self.assertNotIn("预览", task.stdout.splitlines()[0])
        self.assertIn("契约来自 derive", task.stdout)


class TheKnowledgeTaskHasSixBlocks(NativeCase):
    BLOCKS = ("## 1. 当前动作与对象", "## 2. 激活知识及原文", "## 3. 有效事实与决定",
              "## 4. 当前契约与义务", "## 5. 本次完成条件", "## 6. 缺口与责任")

    def registered(self) -> list[str]:
        return yaml.safe_load((self.ext / "manifest.yaml").read_text(encoding="utf-8"))["provides"]["knowledge"]

    def test_discovery_before_the_blueprint_exists(self) -> None:
        proc = self.task("--blueprint", "new-thing", "--action", "discovery", "--audience", "author")
        self.assertEqual(0, proc.returncode, proc.stderr)
        for block in self.BLOCKS:
            self.assertIn(block, proc.stdout)
        self.assertIn("尚未建立", proc.stdout)
        self.assertIn("hooks/blueprint/author.md", proc.stdout)

    def test_every_registered_file_arrives_in_order_with_its_text(self) -> None:
        proc = self.task("--blueprint", BLUEPRINT, "--action", "design", "--audience", "author")
        self.assertEqual(0, proc.returncode, proc.stderr)
        at = [proc.stdout.index(f"`doc/extensions/{rel}`") for rel in self.registered()]
        self.assertEqual(sorted(at), at, "知识没有按激活顺序给")
        for rel in self.registered():
            body = (self.ext / rel).read_text(encoding="utf-8").split("\n---\n", 1)[1].strip()
            self.assertIn(body.splitlines()[0], proc.stdout, f"{rel} 的原文没到")

    def test_halves_are_marked_for_the_side_that_uses_them(self) -> None:
        design = self.task("--blueprint", BLUEPRINT, "--action", "design", "--audience", "author").stdout
        plan = self.task("--feature", CU, "--action", "plan", "--audience", "author").stdout
        self.assertIn("本动作主要用上篇", design)
        self.assertIn("本动作主要用下篇", plan)

    def test_a_unit_task_names_the_unit_and_the_design_objects_it_carries(self) -> None:
        proc = self.task("--feature", CU, "--action", "plan", "--audience", "author")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("施工单位 `balance-refresh`", proc.stdout)
        self.assertIn("本施工单位承担的设计对象：", proc.stdout)
        self.assertIn("hooks/plan/author.md", proc.stdout)

    def test_questioning_without_a_draft_fails_without_half_a_task(self) -> None:
        proc = self.task("--blueprint", "new-thing", "--action", "questioning", "--audience", "reviewer")
        self.assertEqual(1, proc.returncode)
        self.assertEqual("", proc.stdout)
        for word in ("对象：", "缺口：", "责任："):
            self.assertIn(word, proc.stderr)

    def test_a_missing_or_broken_maintenance_feature_fails(self) -> None:
        """平铺维护 Feature 不存在、或本地契约形状坏了：失败、不给半份，不当作没有义务。"""
        broken = self.root / "doc" / "features" / "flat-bad"
        broken.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, broken, True)
        (broken / "contracts.yaml").write_text("feature: flat-bad\nfiles: wrong-shape\n", encoding="utf-8")
        for feature, reason in (("flat-bad", "feature_spec_shape"), ("no-such-flat", "feature_missing")):
            with self.subTest(feature=feature):
                proc = self.task("--feature", feature, "--action", "coding", "--audience", "author")
                self.assertEqual((1, ""), (proc.returncode, proc.stdout))
                self.assertIn(reason, proc.stderr)

    def test_a_unit_before_freezing_says_its_inputs_are_not_yet_determined(self) -> None:
        proc = self.task("--feature", CU, "--action", "plan", "--audience", "author")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("执行范围未冻结", proc.stdout)

    def test_a_bad_unit_id_fails_with_the_native_reason(self) -> None:
        proc = self.task("--feature", "cu-bad", "--action", "plan", "--audience", "author")
        self.assertEqual((1, ""), (proc.returncode, proc.stdout))
        self.assertIn("change_unit_feature_id_invalid", proc.stderr)

    def test_arguments(self) -> None:
        for args in (("--blueprint", BLUEPRINT, "--feature", CU, "--action", "design", "--audience", "author"),
                     ("--blueprint", BLUEPRINT, "--action", "plan", "--audience", "author"),
                     ("--feature", CU, "--action", "plan", "--audience", "someone")):
            with self.subTest(args=args):
                self.assertEqual(2, self.task(*args).returncode)

    def test_an_empty_list_is_zero_and_a_broken_one_names_the_file(self) -> None:
        manifest = self.ext / "manifest.yaml"
        original = manifest.read_bytes()
        self.addCleanup(manifest.write_bytes, original)
        text = original.decode("utf-8")
        start = text.index("  knowledge:\n")
        end = text.index("\n\n", start)
        manifest.write_bytes((text[:start] + "  knowledge: []" + text[end:]).encode("utf-8"))
        proc = self.task("--blueprint", BLUEPRINT, "--action", "design", "--audience", "author")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("零项", proc.stdout)
        manifest.write_bytes((text[:start] + "  knowledge:\n    - knowledge/facts/gone.md" + text[end:]).encode("utf-8"))
        proc = self.task("--blueprint", BLUEPRINT, "--action", "design", "--audience", "author")
        self.assertEqual((1, ""), (proc.returncode, proc.stdout))
        self.assertIn("knowledge/facts/gone.md", proc.stderr)


    def test_object_registrations_keep_their_audience(self) -> None:
        """manifest 1.1 的对象登记：摘要与受众照登记给出，Feature 阶段只送受众里有它的那几份。"""
        manifest = self.ext / "manifest.yaml"
        original = manifest.read_bytes()
        self.addCleanup(manifest.write_bytes, original)
        text = original.decode("utf-8")
        start = text.index("  knowledge:\n")
        end = text.index("\n\n", start)
        first, second = self.registered()[:2]
        objects = ("  knowledge:\n"
                   f"    - {{path: {first}, summary: 部件是谁, audience: global}}\n"
                   f"    - {{path: {second}, summary: 已有能力, audience: [spec]}}")
        manifest.write_bytes((text[:start] + objects + text[end:]).encode("utf-8"))
        plan = self.task("--feature", CU, "--action", "plan", "--audience", "author")
        self.assertEqual(0, plan.returncode, plan.stderr)
        self.assertIn(f"`doc/extensions/{first}`", plan.stdout)
        self.assertIn('登记：受众 "global"，摘要「部件是谁」', plan.stdout)
        self.assertNotIn(f"`doc/extensions/{second}`", plan.stdout, "受众只有 spec 的知识送进了 plan")
        spec = self.task("--feature", CU, "--action", "spec", "--audience", "author").stdout
        self.assertIn(f"`doc/extensions/{second}`", spec)
        design = self.task("--blueprint", BLUEPRINT, "--action", "design", "--audience", "author").stdout
        self.assertIn(f"`doc/extensions/{second}`", design, "蓝图设计要看全部登记的知识")


class TheReviewerGetsTheSameLoader(NativeCase):
    def test_pre_verifier_carries_the_reviewer_task(self) -> None:
        probe = ("const m = (await import(process.argv[1])).default;"
                 "const out = await m({ phase: 'plan', feature: process.argv[2], projectRoot: process.argv[3] });"
                 "process.stdout.write(out.promptFragments.join('\\n\\n'));")
        module = (self.ext / "hooks/shared/pre_verifier.mjs").resolve().as_uri()
        proc = subprocess.run(["node", "--input-type=module", "-e", probe, module, CU, str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("# 知识任务：plan（审查者）", proc.stdout)
        self.assertIn("## 2. 激活知识及原文", proc.stdout)


if __name__ == "__main__":
    unittest.main()
