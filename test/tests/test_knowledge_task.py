"""原生身份读取与动作前知识任务（步骤 1）：在接入 demo Framework 的临时工程里，用真实蓝图与施工单位跑。

锁五件：蓝图与施工单位按 Framework 原生身份读，坏身份、缺对象、过期引用各自报出；阶段输入走原生当前阶段的
只读解析，选哪份输入、过期与 invalid 都照原生，范围未冻结时不代为冻结；知识任务六块齐全、知识原文按激活顺序
完整给出，空清单与坏登记分开；必需输入缺失或损坏时 stdout 不给半份、stderr 写对象、缺口与责任；审查者经
pre_verifier 拿到的是同一个加载器出的任务。
"""
from __future__ import annotations

import atexit
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


def make_project(features_dir: str = "doc/features", root: Path | None = None) -> Path:
    """接入 demo Framework、装好开发版扩展、放进夹具蓝图与施工单位的临时工程；不给 `root` 就新建一个临时目录。"""
    root = root or Path(tempfile.mkdtemp(prefix="story-kt-")) / "p"
    root.mkdir(parents=True)
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


#: 本进程准备工程用的固定位置。冻结记录与需求绑定写的是绝对路径：状态在这里造、复制回这里用，路径原样有效，
#: 不靠原生的换根重定位（需求来源不在需求目录下时它推不出旧根，会读回原处的文件）。同一进程的用例是串行的。
_WORK = Path(tempfile.mkdtemp(prefix="story-kt-work-")) / "p"
atexit.register(shutil.rmtree, _WORK.parent, True)
_PREPARED: dict[tuple, Path] = {}


def _without_framework(src: Path):
    return lambda d, names: ["framework"] if Path(d) == src else []


def prepared_project(steps: tuple[str, ...], requirement: str = REQUIREMENT) -> Path:
    """按原生入口准备好的工程：每种准备每个进程只造一次（冻结一次二三十秒）并存档，每次调用把存档复制回 `_WORK`，
    用例在上面随便改。`requirement` 不是夹具需求时，先把夹具需求拷成这份只给请求用的来源文件。"""
    key = (steps, requirement)
    if key not in _PREPARED:
        shutil.rmtree(_WORK, ignore_errors=True)
        make_project(root=_WORK)
        if requirement != REQUIREMENT:
            shutil.copy2(_WORK / REQUIREMENT, _WORK / requirement)
        for step in steps:
            prepare(_WORK, step, requirement=requirement)
        archive = Path(tempfile.mkdtemp(prefix="story-kt-prepared-")) / "p"
        atexit.register(shutil.rmtree, archive.parent, True)
        shutil.copytree(_WORK, archive, ignore=_without_framework(_WORK))
        _PREPARED[key] = archive
    shutil.rmtree(_WORK, ignore_errors=True)
    shutil.copytree(_PREPARED[key], _WORK, ignore=_without_framework(_PREPARED[key]))
    link_framework(_WORK)
    return _WORK


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

    def test_the_summary_is_the_same_read_without_the_blueprint_body(self) -> None:
        """--summary 只核状态：同一读取与校验，字段与完整输出一致，只少蓝图正文；失败照样失败。"""
        full = self.access("--action", "blueprint", "--blueprint", BLUEPRINT, "--purpose", "delivery")
        summary = self.access("--action", "blueprint", "--blueprint", BLUEPRINT, "--purpose", "delivery", "--summary")
        self.assertIn("blueprint", full[1])
        self.assertEqual((full[0], {k: v for k, v in full[1].items() if k != "blueprint"}), summary)
        self.assertEqual((1, "missing"), (lambda c, o: (c, o.get("status")))(
            *self.access("--action", "blueprint", "--blueprint", "not-there", "--summary")))
        self.assertEqual(2, self.access("--action", "feature", "--feature", CU, "--phase", "plan", "--summary")[0],
                         "摘要只属于蓝图读取")

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

    def test_an_unusable_framework_is_named_with_its_path_and_cause(self) -> None:
        """没接入 Framework、或 harness 依赖装不上：说清是哪个根、缺什么，退出 2，不写任何文件。"""
        with tempfile.TemporaryDirectory() as tmp:
            bare = Path(tmp) / "bare"
            bare.mkdir()
            proc = self.node("hooks/shared/framework-access.mjs", "--action", "blueprint", "--blueprint", BLUEPRINT,
                             "--purpose", "draft", root=bare)
            self.assertEqual(2, proc.returncode, proc.stdout)
            self.assertIn(str(bare), proc.stderr)
            self.assertIn("framework/harness/package.json", proc.stderr)
            broken = Path(tmp) / "broken"
            (broken / "framework/harness").mkdir(parents=True)
            (broken / "framework/harness/package.json").write_text("{}", encoding="utf-8")
            proc = self.node("hooks/shared/framework-access.mjs", "--action", "blueprint", "--blueprint", BLUEPRINT,
                             "--purpose", "draft", root=broken)
            self.assertEqual(2, proc.returncode, proc.stdout)
            self.assertIn("MODULE_NOT_FOUND", proc.stderr)
            self.assertIn(str(broken / "framework" / "harness"), proc.stderr)
            self.assertEqual([], list(bare.iterdir()), "读取失败却写了文件")
            self.assertEqual(["framework"], [p.name for p in broken.iterdir()], "读取失败却写了文件")

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
    """每条用例一份自己的工程：范围冻结只能做一次，各用例要自己的候选与冻结记录。"""

    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")

    def use(self, *steps: str, requirement: str = REQUIREMENT) -> None:
        self.root = prepared_project(steps, requirement)

    def run_script(self, script: str, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["node", str(self.root / "doc/extensions/hooks/shared" / script), "--project-root", str(self.root), *args],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)

    def feature(self, phase: str) -> tuple[int, dict]:
        proc = self.run_script("framework-access.mjs", "--action", "feature", "--feature", CU, "--phase", phase)
        return proc.returncode, json.loads(proc.stdout)


class TheAuthorTaskBeginsThePhase(FreshProject):
    """作者取 Feature 阶段的正式任务就是开始这一阶段：命令入口记使用记录的 begin，重取保留最早的起点；
    预览、审查者与被导入的渲染函数都不记。"""

    def starts(self) -> dict:
        path = self.root / "doc" / "features" / ".usage-state.json"
        state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        return {k: v for node in state.values() for k, v in (node.get("starts") or {}).items()}

    def task(self, action: str, audience: str = "author") -> subprocess.CompletedProcess:
        return self.run_script("knowledge-task.mjs", "--feature", CU, "--action", action, "--audience", audience)

    def test_a_preview_does_not_begin(self) -> None:
        self.use("candidate")
        self.assertEqual(0, self.task("spec").returncode)
        self.assertNotIn("spec", self.starts(), "预览任务开始了阶段计时")

    def test_the_formal_author_task_begins_once_and_the_rest_do_not(self) -> None:
        self.use("freeze")
        module = (self.root / "doc/extensions/hooks/shared/knowledge-task.mjs").resolve().as_uri()
        imported = subprocess.run(["node", "--input-type=module", "-e",
                                   "await import(process.argv[1]); process.stdout.write('imported');", module],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual("imported", imported.stdout, imported.stderr)
        self.assertEqual(0, self.task("plan", "reviewer").returncode)
        self.assertEqual({}, self.starts(), "导入模块或取审查者任务就写了使用记录")
        self.assertEqual(0, self.task("plan").returncode)
        first = self.starts()["plan"]
        self.assertEqual(0, self.task("plan").returncode)
        self.assertEqual(first, self.starts()["plan"], "重取任务换了起点")


class PhaseInputsBeforeLocalContracts(FreshProject):
    """范围冻结、还没有本地施工输入：本阶段输入照原生阶段解析——蓝图派生，或原生判缺必需能力。"""

    def test_the_blueprint_derivation_is_what_the_resolver_selects_before_local_inputs_exist(self) -> None:
        self.use("freeze")
        code, out = self.feature("plan")
        self.assertEqual((0, "ok", "frozen"), (code, out["status"], out["scope"]), out)
        self.assertEqual("derive", out["inputs"]["contracts"]["binding"]["kind"])
        task = self.run_script("knowledge-task.mjs", "--feature", CU, "--action", "plan", "--audience", "author")
        self.assertEqual(0, task.returncode, task.stderr)
        self.assertIn("契约来自 derive", task.stdout)

    def test_a_phase_the_native_resolver_blocks_fails_the_task(self) -> None:
        """原生判本阶段缺必需能力（无 run 的 coding 缺需求正文）：照原生结论失败，不当作空义务。"""
        self.use("freeze")
        code, out = self.feature("coding")
        self.assertEqual((1, "invalid", "blocked"), (code, out["status"], out["assurance"]), out)
        self.assertEqual("capability_blocked", out["issues"][0]["code"])
        task = self.run_script("knowledge-task.mjs", "--feature", CU, "--action", "coding", "--audience", "author")
        self.assertEqual((1, ""), (task.returncode, task.stdout))


class PhaseInputsFromMaterializedContracts(FreshProject):
    """先物化本地契约再冻结：原生选本地契约；冻结后改了它，原生判过期，读取不写任何东西、不拿蓝图顶上。"""

    def test_a_materialized_local_contract_is_what_the_resolver_selects(self) -> None:
        self.use("materialize", "freeze")
        code, out = self.feature("plan")
        self.assertEqual((0, "ok"), (code, out["status"]), out)
        self.assertEqual({"kind": "artifact", "artifact": "contracts@1"}, out["inputs"]["contracts"]["binding"])

    def test_a_local_contract_changed_after_freezing_follows_the_native_owner(self) -> None:
        """冻结后改了本地契约：契约归 plan 产出，plan 读到的就是改后的本地契约；下游 review 原生判过期，
        不能借蓝图派生变绿，知识任务失败、不给半份。读取不写任何东西。"""
        self.use("materialize", "freeze")
        prepare(self.root, "edit")
        features = self.root / "doc" / "features"
        state = self.root / "framework" / "harness" / "state"
        listed = lambda: sorted(p.name for p in state.iterdir()) if state.is_dir() else []  # noqa: E731
        before, state_before = files_under(features), listed()
        code, out = self.feature("plan")
        self.assertEqual((0, "ok"), (code, out["status"]), out)
        self.assertEqual({"kind": "artifact", "artifact": "contracts@1"}, out["inputs"]["contracts"]["binding"])
        task = self.run_script("knowledge-task.mjs", "--feature", CU, "--action", "plan", "--audience", "author")
        self.assertEqual(0, task.returncode, task.stderr)
        self.assertIn("LOCAL-1", task.stdout, "plan 没读到它自己改过的本地契约")
        code, out = self.feature("review")
        self.assertEqual((1, "invalid"), (code, out["status"]), out)
        self.assertIn("stale", json.dumps(out["issues"], ensure_ascii=False))
        task = self.run_script("knowledge-task.mjs", "--feature", CU, "--action", "review", "--audience", "author")
        self.assertEqual((1, ""), (task.returncode, task.stdout))
        self.assertIn("缺口：", task.stderr)
        # 作者取正式任务唯一的副作用是使用记录的开始（运行态与身份件），其余一个字节不写
        business = lambda files: {k: v for k, v in files.items()  # noqa: E731
                                  if not k.endswith((".usage-state.json", ".usage-id"))}
        self.assertEqual(business(before), business(files_under(features)), "读取写了需求目录")
        self.assertEqual(state_before, listed(), "读取写了 harness 状态")

    def test_the_reviewer_is_told_when_its_task_cannot_be_read(self) -> None:
        self.use("materialize", "freeze")
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


class SpecCase(FreshProject):
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


class SpecFromARequirementFile(SpecCase):
    """候选记下了需求来源文件：按它恢复，与原生同结果，审查者拿到同一份任务。"""

    def test_a_file_bound_spec_resolves_as_the_native_harness_does(self) -> None:
        self.use("freeze")
        native = self.native_spec()
        self.assertEqual(("full", "resolved", []), (native["assurance"], native["requirement"], native["blocked"]))
        code, out = self.spec()
        self.assertEqual((0, "ok", native["assurance"]), (code, out["status"], out["assurance"]), out)
        task = self.run_script("knowledge-task.mjs", "--feature", CU, "--action", "spec", "--audience", "author")
        self.assertEqual(0, task.returncode, task.stderr)
        self.assertNotIn("预览", task.stdout.splitlines()[0])

    def test_the_reviewer_gets_the_spec_task_on_the_same_object(self) -> None:
        self.use("freeze")
        probe = ("const m = (await import(process.argv[1])).default;"
                 "const out = await m({ phase: 'spec', feature: process.argv[2], projectRoot: process.argv[3] });"
                 "process.stdout.write(out.promptFragments.join('\\n\\n'));")
        module = (self.root / "doc/extensions/hooks/shared/pre_verifier.mjs").resolve().as_uri()
        proc = subprocess.run(["node", "--input-type=module", "-e", probe, module, CU, str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("# 知识任务：spec（审查者）", proc.stdout)
        self.assertNotIn("取不到", proc.stdout)


class SpecRequirementSourceChanged(SpecCase):
    """冻结后需求来源变了：照原生报过期。"""

    def test_a_requirement_source_changed_after_freezing_is_stale(self) -> None:
        """需求来源是一份只给这次请求用的文件（夹具需求同时是蓝图来源，改它先让蓝图失效）。"""
        request = "doc/requirements/balance-refresh-request.md"
        self.use("freeze", requirement=request)
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


class SpecWithAnInlineRequirement(SpecCase):
    """候选只记了需求正文的指纹：要调用方给原文，并按绑定核对。"""

    def test_an_inline_requirement_is_asked_for_and_checked_against_the_binding(self) -> None:
        self.use("freeze-inline")
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


class TheFirstPhaseIsPreparedNatively(FreshProject):
    """首阶段：先原生准备范围，再重取任务动笔。"""

    def test_the_first_phase_is_prepared_natively_before_the_task_is_used(self) -> None:
        """首阶段：候选有了、范围未冻结时任务只是预览；照 story-knowledge Skill 给的原生准备命令冻结后，重取得到真实输入。"""
        self.use("candidate")
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
    BLOCKS = ("## 1. 当前动作与对象", "## 2. 有效事实与决定", "## 3. 当前契约与义务",
              "## 4. 激活知识及原文", "## 5. 本次完成条件", "## 6. 缺口与责任")

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

    def test_unjudged_patterns_reach_the_author_and_the_questioner(self) -> None:
        """夹具蓝图还没有模式判断：设计作者与质询者的缺口里都点名每个激活模式，与门禁同一集合。"""
        patterns = [rel for rel in self.registered() if rel.startswith("knowledge/design-patterns/")]
        self.assertTrue(patterns, "夹具要有激活模式")
        for action, audience in (("design", "author"), ("questioning", "reviewer")):
            with self.subTest(action=action):
                gaps = self.task("--blueprint", BLUEPRINT, "--action", action, "--audience", audience).stdout.split("## 6. 缺口与责任", 1)[1]
                for rel in patterns:
                    self.assertIn(f"没有判断激活模式 doc/extensions/{rel}", gaps)

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

    def test_the_questioning_task_carries_the_handoff(self) -> None:
        """质询任务交给隔离质询者：被评候选与原件位置、原生质询范围逐项、每项要回什么。"""
        proc = self.task("--blueprint", BLUEPRINT, "--action", "questioning", "--audience", "reviewer")
        self.assertEqual(0, proc.returncode, proc.stderr)
        canonical = self.root / "doc/features" / BLUEPRINT / "blueprint/component-blueprint.yaml"
        key = hashlib.sha256(canonical.read_bytes()).hexdigest()[:16]
        base = f"doc/features/{BLUEPRINT}/blueprint/questioning/{key}"
        self.assertIn(f"`{base}/candidate.yaml`", proc.stdout)
        self.assertIn(f"`{base}/reply.md`", proc.stdout)
        blueprint = yaml.safe_load(canonical.read_text(encoding="utf-8"))
        for view in blueprint["design_views"]:
            if view.get("applicability") == "applicable":
                self.assertIn(f"`view:{view['view_id']}`（view）", proc.stdout)
        for relation in blueprint.get("relations") or []:
            self.assertIn(f"`relation:{relation['relation_id']}`（relation）", proc.stdout)
        self.assertIn("你只读材料、逐项回复", proc.stdout)
        dispatch = proc.stdout.split("## 7. 派审与留存（主执行者）", 1)[1]
        self.assertIn(f"`{base}/reply.md`", dispatch, "派审与留存没单列给主执行者")

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
        self.assertIn("## 4. 激活知识及原文", proc.stdout)



class ANativeEntryNeedsNoStory(unittest.TestCase):
    """蓝图的需求条目直接来自原生需求文件（不在需求冻结输入布局里）：没有 Story 是正常的，任务照常给出、不报缺口。"""

    def test_the_task_says_there_is_no_story_and_goes_on(self) -> None:
        root = make_project()
        self.addCleanup(shutil.rmtree, root.parent, True)
        from ext_workspace import DEV_EXT  # noqa: PLC0415
        proc = subprocess.run(
            ["node", str(DEV_EXT / "hooks" / "shared" / "knowledge-task.mjs"), "--project-root", str(root),
             "--action", "spec", "--audience", "author", "--feature", CU],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(0, proc.returncode, proc.stderr[-800:])
        self.assertIn("原生直接入口", proc.stdout)
        self.assertNotIn("关联 Story：", proc.stdout, "没有 Story 被当成了缺口")


def place_unit(root: Path, blueprint: str, ref: dict) -> tuple[Path, str]:
    """在 `blueprint` 下放夹具施工单位 balance-refresh，引用改指这一版蓝图（`ref` 是原生读到的 blueprint_ref）。"""
    unit = (FIXTURE / "doc" / "features" / BLUEPRINT / "balance-refresh" / "change-unit.yaml").read_text(encoding="utf-8")
    for old, new in (("revision: 3", f"revision: {ref['revision']}"),
                     ("sha256:80b296f54d8978722ba6390fa5aadcb4c0deb1b93a1f0760ae6bb57d86259b72", ref["source_fingerprint"]),
                     ("sha256:9ebbfd035f89aacdb9f001b9e73df0ee5cc3f6c14cf496366778296eb3b7cbf5", ref["artifact_sha256"]),
                     (BLUEPRINT, blueprint)):
        unit = unit.replace(old, new)
    unit_dir = root / "doc" / "features" / blueprint / "balance-refresh"
    unit_dir.mkdir(parents=True, exist_ok=True)
    (unit_dir / "change-unit.yaml").write_text(unit, encoding="utf-8")
    # 评审投影随施工单位集合变化：放进单位后按原生物化重出，与设计职责的产物一致
    import design_kit  # noqa: PLC0415
    from ext_workspace import DEV_EXT  # noqa: PLC0415
    design_kit.render_projection(root, blueprint, DEV_EXT / "hooks" / "shared" / "framework-access.mjs")
    return unit_dir, cu_id(blueprint, "balance-refresh")


class RelatedStoryExpressionReachesTheUnit(unittest.TestCase):
    """施工单位按蓝图实际消费的冻结来源找到关联需求，Story 仍是成文登记的那一份时，照录依据落在本单位设计责任内的小节。

    需求 REQ-DEMO 已交给设计，蓝图 bp-REQ-DEMO 消费了它的冻结输入；这里在同一蓝图下放一个施工单位，
    它的设计引用是开发视图的模块节点、逻辑视图的余额节点与两者之间的关系。成文登记用真实的成文依据（`registered_basis`）。
    """

    FEATURE = "REQ-DEMO"
    BLUEPRINT = "bp-REQ-DEMO"
    STORY_FIXTURE = REPO_ROOT / "test" / "fixtures" / "failure-modes" / "R01-verdict-echo" / "good"
    DIAGRAM = "flowchart TD\n  提交 --> 等待\n  等待 -->|回执到达| 完成\n"

    @classmethod
    def setUpClass(cls) -> None:
        from designed_fixture import DRAFT, designed_copy  # noqa: PLC0415
        from ext_workspace import DEV_EXT  # noqa: PLC0415  —— 开发源在消费工程里才跑得起来
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name) / "work"
        designed_copy(cls.STORY_FIXTURE, cls.FEATURE, DRAFT, cls.root)
        cls.ext = DEV_EXT
        cls.access = DEV_EXT / "hooks" / "shared" / "framework-access.mjs"
        ref = cls.node("const r = fa.readBlueprint(root, process.argv[3], 'draft'); out(r.blueprint_ref);", cls.BLUEPRINT)
        cls.unit_dir, cls.unit = place_unit(cls.root, cls.BLUEPRINT, ref)
        # 夹具工程只装了知识与清单：阶段判据 overlay 从本次扩展补进来，审查侧的片段才按真实判据装配
        shutil.copytree(DEV_EXT / "rules", cls.root / "doc" / "extensions" / "rules", dirs_exist_ok=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    @classmethod
    def node(cls, body: str, *args: str):
        proc = subprocess.run(
            ["node", "--input-type=module", "-e",
             "const fa = await import(process.argv[1]); const root = process.argv[2];"
             "const out = v => process.stdout.write(JSON.stringify(v));" + body,
             cls.access.resolve().as_uri(), str(cls.root), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr[-800:])
        return json.loads(proc.stdout)

    def setUp(self) -> None:
        req = self.root / "doc" / "features" / self.FEATURE / "AR"
        self.flow_file = req / "story-src" / "story-flow.json"
        self.plan_file = req / "story-src" / "story-template.md"
        self.story_file = req / "story.md"
        self.saved = {p: p.read_bytes() for p in (self.flow_file, self.plan_file, self.story_file)}
        self.addCleanup(self.restore)
        plan = self.plan_file.read_bytes().decode("utf-8")
        plan = plan.replace("### 05-flow\n", "### 05-flow\n- 依据：蓝图 `view:runtime`\n", 1)
        plan = plan.replace("### 06-features\n", "### 06-features\n#### 提交与回执\n"
                            "- 依据：蓝图 `view:development/node:wallet-main-module`、`contract:nope`\n", 1)
        self.plan_file.write_bytes(plan.encode("utf-8"))
        story = self.story_file.read_bytes().decode("utf-8")
        self.story_file.write_bytes(story.replace("### 6.1 提交与回执\n", f"### 6.1 提交与回执\n\n```mermaid\n{self.DIAGRAM}```\n", 1)
                                    .encode("utf-8"))
        self.register()

    def restore(self) -> None:
        for p, data in self.saved.items():
            p.write_bytes(data)
        for name in ("spec", "plan"):
            shutil.rmtree(self.unit_dir / name, ignore_errors=True)

    def register(self) -> None:
        """与 `story_flow.py story` 登记同形：当前的成文依据与登记文件指纹。"""
        import design_kit  # noqa: PLC0415
        flow = json.loads(self.flow_file.read_text(encoding="utf-8"))
        flow["status"] = "story_written"
        flow["story_basis"] = design_kit.registered_basis(self.root, self.FEATURE)
        self.flow_file.write_text(json.dumps(flow, ensure_ascii=False), encoding="utf-8")

    def edit_flow(self, change) -> None:
        flow = json.loads(self.flow_file.read_text(encoding="utf-8"))
        change(flow)
        self.flow_file.write_text(json.dumps(flow, ensure_ascii=False), encoding="utf-8")

    def task(self) -> str:
        proc = subprocess.run(
            ["node", str(self.ext / "hooks" / "shared" / "knowledge-task.mjs"), "--project-root", str(self.root),
             "--action", "spec", "--audience", "author", "--feature", self.unit],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(0, proc.returncode, proc.stderr[-800:])
        return proc.stdout

    def section(self, text: str | None = None) -> str:
        return (text or self.task()).split("### 关联 Story 的已定表达", 1)[1].split("\n## ", 1)[0]

    def selected_body(self) -> str:
        story = self.story_file.read_bytes().decode("utf-8")
        return story.split("### 6.1 提交与回执\n", 1)[1].split("\n## ", 1)[0].strip()

    # ---- 当前的 Story：照录、身份、选取范围 ----

    def test_the_section_inside_the_units_scope_comes_verbatim_with_a_stable_identity(self) -> None:
        body = self.selected_body()
        section = self.section()
        self.assertIn(body, section, "相关小节没有照录")
        self.assertIn("sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest(), section, "身份摘要不是照录内容的摘要")
        self.assertIn("功能说明 / 提交与回执", section)
        self.assertNotRegex(section, r"第 \d+–\d+ 行", "身份里带了随无关插入漂移的行号")

    def test_a_section_outside_the_scope_is_not_given(self) -> None:
        """业务流程章的依据是运行视图，不在本单位的设计责任里：不交。"""
        story = self.story_file.read_bytes().decode("utf-8")
        flow_text = story.split("## 业务流程", 1)[1].split("\n## ", 1)[0].strip().splitlines()[0]
        self.assertNotIn(flow_text, self.section())

    def test_an_address_without_backticks_is_read_the_same(self) -> None:
        before = self.section()
        plan = self.plan_file.read_bytes().decode("utf-8").replace("`view:development/node:wallet-main-module`",
                                                                   "view:development/node:wallet-main-module")
        self.plan_file.write_bytes(plan.encode("utf-8"))
        self.register()
        self.assertEqual(before, self.section())

    def test_an_unrelated_insertion_leaves_the_selected_input_unchanged(self) -> None:
        """选中节之前插一段无关正文并合法重登记：交给施工单位的这一节逐字不变。"""
        before = self.section()
        story = self.story_file.read_bytes().decode("utf-8")
        self.story_file.write_bytes(story.replace("## 范围\n", "## 范围\n\n补一句与本单位无关的范围说明。\n", 1).encode("utf-8"))
        self.register()
        self.assertEqual(before, self.section())

    def test_a_change_in_the_selected_diagram_changes_the_input(self) -> None:
        before = self.section()
        story = self.story_file.read_bytes().decode("utf-8")
        self.story_file.write_bytes(story.replace("回执到达", "回执超时", 1).encode("utf-8"))
        self.register()
        after = self.section()
        self.assertNotEqual(before, after)
        self.assertIn("回执超时", after)

    def material_sha(self) -> str:
        """审查侧的材料身份：pre_verifier 交给原生的片段，经原生 `buildVerifierMaterialView` 算出的 material_sha256。"""
        return self.node(
            "const pre = (await import(process.argv[4])).default;"
            "const r = await pre({ phase: 'spec', feature: process.argv[3], projectRoot: root });"
            "const vm = fa.loadNative(root).module('scripts/utils/verifier-material.ts');"
            "out(vm.buildVerifierMaterialView({ projectRoot: root, feature: process.argv[3], phase: 'spec', gateFingerprint: 'g',"
            " phaseRuleText: '', templateText: '', checks: [], contextFiles: [], lifecycleFragments: r.promptFragments }).material_sha256);",
            self.unit, (self.ext / "hooks" / "shared" / "pre_verifier.mjs").resolve().as_uri())

    def test_the_native_material_identity_follows_only_the_selected_fragment(self) -> None:
        """无关段落改动并合法重登记：材料身份不变（审查可复用）；选中节的图变了并重登记：材料身份变（要重审）。"""
        base = self.material_sha()
        story = self.story_file.read_bytes().decode("utf-8")
        self.story_file.write_bytes(story.replace("## 范围\n", "## 范围\n\n补一句与本单位无关的范围说明。\n", 1).encode("utf-8"))
        self.register()
        self.assertEqual(base, self.material_sha(), "无关表达变化换了审查对象")
        story = self.story_file.read_bytes().decode("utf-8")
        self.story_file.write_bytes(story.replace("回执到达", "回执超时", 1).encode("utf-8"))
        self.register()
        self.assertNotEqual(base, self.material_sha(), "相关片段变了，审查对象没换")

    def test_both_phases_receive_the_consistency_contract(self) -> None:
        """spec 与 plan 的审查任务都列出这条判据；判据把「共同设计错影响本单位」判 FAIL，与「只有 Story 表达错」分开。"""
        import yaml  # noqa: PLC0415
        for phase in ("spec", "plan"):
            with self.subTest(phase=phase):
                fragments = self.node(
                    "const pre = (await import(process.argv[4])).default;"
                    "out((await pre({ phase: process.argv[5], feature: process.argv[3], projectRoot: root })).promptFragments);",
                    self.unit, (self.ext / "hooks" / "shared" / "pre_verifier.mjs").resolve().as_uri(), phase)
                self.assertIn("`design_content_consistency`（BLOCKER）", "\n".join(fragments))
                rule = yaml.safe_load((self.root / "doc" / "extensions" / "rules" / f"{phase}-rules.overlay.yaml")
                                      .read_text(encoding="utf-8"))["semantic_checks"]["design_content_consistency"]["description"]
                for words in ("共同设计错了或缺了", "FAIL，回设计负责方", "「错在上游」不降级", "只有 Story 的表达与有效设计矛盾", "人读交付还没同步"):
                    self.assertIn(words, rule)

    def test_a_free_text_basis_reaches_no_unit(self) -> None:
        """写作设计里只写自由文字的依据没有机器关联：不拿它给任何施工单位片段，也不当找不到小节报缺口。"""
        plan = self.plan_file.read_bytes().decode("utf-8")
        self.plan_file.write_bytes(plan.replace("### 07-exceptions\n", "### 07-exceptions\n#### 回执迟到\n"
                                                "- 依据：评审会上对迟到回执的说法\n", 1).encode("utf-8"))
        self.register()
        out = self.task()
        self.assertNotIn("回执迟到", out)
        self.assertIn(self.selected_body(), self.section(out), "有地址的那一节照旧交")

    # ---- 不是当前那一份：旧表达或缺口 ----

    def test_story_or_design_changed_after_registration_is_old_expression(self) -> None:
        for target in (self.story_file, self.plan_file):
            with self.subTest(changed=target.name):
                data = target.read_bytes()
                target.write_bytes(data + "\n补一行。\n".encode("utf-8"))
                section = self.section()
                self.assertIn("旧表达", section)
                self.assertNotIn(self.selected_body(), section)
                target.write_bytes(data)

    def test_a_registered_input_that_no_longer_matches_is_old_expression(self) -> None:
        self.edit_flow(lambda f: f["story_basis"].update(input_sha256="0" * 64))
        section = self.section()
        self.assertIn("旧表达", section)
        self.assertIn("交给设计的输入", section)

    def test_missing_registration_data_is_a_gap_not_a_source(self) -> None:
        self.edit_flow(lambda f: f["story_basis"].pop("files"))
        out = self.task()
        self.assertIn("登记数据不完整", out)
        self.assertNotIn(self.selected_body(), self.section(out))

    def test_a_bad_skeleton_and_a_repeated_chapter_are_gaps(self) -> None:
        plan = self.plan_file.read_bytes()
        self.plan_file.write_bytes(plan.replace(b"### 10-appendix\n", "### 99-unknown\n- 本章主线：不在合同里\n\n### 10-appendix\n"
                                                .encode("utf-8"), 1))
        self.register()
        self.assertIn("写作设计读不全", self.task())
        self.plan_file.write_bytes(plan)
        story = self.story_file.read_bytes().decode("utf-8")
        self.story_file.write_bytes((story + "\n## 功能说明\n\n重复的一章。\n").encode("utf-8"))
        self.register()
        out = self.task()
        self.assertIn("认不开", out)
        self.assertNotIn(self.selected_body(), self.section(out))

    def test_an_address_the_blueprint_does_not_have_is_a_gap(self) -> None:
        self.assertIn("contract:nope 在蓝图里解析不了", self.task())

    def test_a_story_bound_to_another_blueprint_is_a_source_problem(self) -> None:
        self.edit_flow(lambda f: f["design_binding"].update(blueprint_id="bp-other"))
        out = self.task()
        self.assertIn("关联的设计对象是", out)
        self.assertNotIn(self.selected_body(), self.section(out))


class AdoptedSourcesAreReadThroughOneReader(unittest.TestCase):
    """候选声明的来源与冻结包按同一底层读取（原生 resolveCurrentScopeSource 核原字节、片段与声明摘要）：
    蓝图设计/质询任务交真实来源索引，CU 来源（unitSources）对同一文件得到同样的结论；
    任一份坏了蓝图任务不给半份，失败不写盘。
    """

    FEATURE = "REQ-DEMO"
    BLUEPRINT = "bp-REQ-DEMO"
    STORY_FIXTURE = REPO_ROOT / "test" / "fixtures" / "failure-modes" / "R01-verdict-echo" / "good"
    PROBE = """
const ds = await import(process.argv[1]);
const [root, flow, feature] = process.argv.slice(2);
const unit = ds.unitSources(root, feature);
process.stdout.write(JSON.stringify({
  unit: { documents: Object.fromEntries(unit.documents), excluded: Object.fromEntries(unit.excluded), problems: unit.problems } }));
"""

    def setUp(self) -> None:
        from designed_fixture import DRAFT, designed_copy  # noqa: PLC0415
        from ext_workspace import DEV_EXT  # noqa: PLC0415
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        designed_copy(self.STORY_FIXTURE, self.FEATURE, DRAFT, self.root)
        self.ext = DEV_EXT
        self.flow_file = self.root / "doc" / "features" / self.FEATURE / "AR" / "story-src" / "story-flow.json"
        self.snapshot_ref = json.loads(self.flow_file.read_text(encoding="utf-8"))["input"]["snapshot_ref"]
        self.pack = (self.root / self.snapshot_ref).parent
        self.prd = f"{Path(self.snapshot_ref).parent.as_posix()}/files/RR/prd.md"
        self.canonical = self.root / "doc" / "features" / self.BLUEPRINT / "blueprint" / "component-blueprint.yaml"
        ref = json.loads(subprocess.run(
            ["node", "--input-type=module", "-e",
             "const fa = await import(process.argv[1]); process.stdout.write(JSON.stringify("
             "fa.readBlueprint(process.argv[2], process.argv[3], 'draft').blueprint_ref));",
             (DEV_EXT / "hooks" / "shared" / "framework-access.mjs").resolve().as_uri(), str(self.root), self.BLUEPRINT],
            capture_output=True, text=True, encoding="utf-8", timeout=120).stdout)
        _, self.unit = place_unit(self.root, self.BLUEPRINT, ref)

    def task(self, action: str = "design", audience: str = "author") -> subprocess.CompletedProcess:
        return subprocess.run(["node", str(self.ext / "hooks" / "shared" / "knowledge-task.mjs"), "--project-root", str(self.root),
                               "--blueprint", self.BLUEPRINT, "--action", action, "--audience", audience],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)

    def readers(self) -> dict:
        module = (self.ext / "skills" / "story" / "scripts" / "core" / "story" / "design-source.mjs").resolve().as_uri()
        proc = subprocess.run(["node", "--input-type=module", "-e", self.PROBE, module, str(self.root), str(self.flow_file), self.unit],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, proc.returncode, proc.stderr[-800:])
        return json.loads(proc.stdout)

    def snapshot(self) -> dict:
        return json.loads((self.root / self.snapshot_ref).read_text(encoding="utf-8"))

    def put_snapshot(self, data: dict) -> None:
        (self.root / self.snapshot_ref).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def assert_task_fails(self, *words: str) -> None:
        before = files_under(self.root / "doc")
        for action, audience in (("design", "author"), ("questioning", "reviewer")):
            with self.subTest(action=action):
                proc = self.task(action, audience)
                self.assertEqual((1, ""), (proc.returncode, proc.stdout), "来源坏了还交了任务")
                for word in ("候选采用的来源", *words):
                    self.assertIn(word, proc.stderr)
        self.assertEqual(before, files_under(self.root / "doc"), "失败时写了盘")

    def test_the_design_and_questioning_tasks_index_every_adopted_source(self) -> None:
        for action, audience in (("design", "author"), ("questioning", "reviewer")):
            with self.subTest(action=action):
                proc = self.task(action, audience)
                self.assertEqual(0, proc.returncode, proc.stderr[-800:])
                index = proc.stdout.split("### 候选采用的来源", 1)[1].split("## 2.", 1)[0]
                self.assertIn(f"`{self.prd}`", index)
                self.assertIn(f"`{self.snapshot_ref}`", index, "没交候选那一版的快照位置")
                for row in self.snapshot()["files"]:
                    self.assertIn(f"`{Path(self.snapshot_ref).parent.as_posix()}/files/{row['path']}`（{row['role']}，"
                                  f"{row['provenance']['evidence_strength']}），sha256:{row['sha256']}", index)

    def test_the_same_good_file_reaches_all_three_readers(self) -> None:
        got = self.readers()
        self.assertEqual([], got["unit"]["problems"])
        text = (self.root / self.prd).read_text(encoding="utf-8")
        self.assertEqual(text, got["unit"]["documents"][self.prd])

    def test_a_changed_or_missing_file_is_the_same_gap_everywhere(self) -> None:
        target = self.root / self.prd
        original = target.read_bytes()
        for label, change, word in (("字节变了", lambda: target.write_bytes(original + b"\n"), "不符"),
                                    ("读不到", target.unlink, "不存在")):
            with self.subTest(case=label):
                change()
                self.assert_task_fails(self.prd, word)
                got = self.readers()
                self.assertIn(word, got["unit"]["excluded"][self.prd])
                target.write_bytes(original)

    def test_a_wrong_declaration_fails_even_when_the_pack_is_intact(self) -> None:
        """冻结包逐份都对，但候选声明的片段或摘要错了：蓝图任务照样不给，不因包校验成功或草稿 status=ok 放过。"""
        original = self.canonical.read_bytes()
        declared = "sha256:" + hashlib.sha256((self.root / self.prd).read_bytes()).hexdigest()
        text = original.decode("utf-8")
        self.assertIn(declared, text, "夹具变了，用例要跟着改")
        for label, changed, word in (
                ("片段解析不了", text.replace(self.prd, f"{self.prd}#不存在的片段"), "fragment"),
                ("摘要不符", text.replace(declared, "sha256:" + "0" * 64), "不符")):
            with self.subTest(case=label):
                self.canonical.write_bytes(changed.encode("utf-8"))
                self.assertEqual(0, self.access_status(), "草稿读取本身应仍为 ok")
                self.assert_task_fails(word)
                self.canonical.write_bytes(original)

    def access_status(self) -> int:
        proc = subprocess.run(["node", str(self.ext / "hooks" / "shared" / "framework-access.mjs"), "--project-root", str(self.root),
                               "--action", "blueprint", "--blueprint", self.BLUEPRINT, "--purpose", "draft", "--summary"],
                              capture_output=True, text=True, encoding="utf-8", timeout=120)
        return proc.returncode

    def test_a_broken_snapshot_or_a_row_outside_the_pack_is_never_an_empty_success(self) -> None:
        good = self.snapshot()
        for label, write, word in (
                ("坏 JSON", lambda: (self.root / self.snapshot_ref).write_text("{", encoding="utf-8"), "读不出来"),
                ("没有 files", lambda: self.put_snapshot({**good, "files": "x"}), "没有 files 清单"),
                ("越出包外", lambda: self.put_snapshot({**good, "files": [*good["files"], {**good["files"][0], "path": "../../../x.md"}]}),
                 "不在包内")):
            with self.subTest(case=label):
                write()
                self.assert_task_fails(word)
                self.put_snapshot(good)

    def test_non_markdown_and_bom_files_are_checked_on_their_raw_bytes(self) -> None:
        good = self.snapshot()
        extra = {"RR/flow.png": b"\x89PNG\r\n\x1a\nnot-really", "RR/notes.md": "\ufeff# 备注\n人签过的边界。\n".encode("utf-8")}
        rows = []
        for name, data in extra.items():
            (self.pack / "files" / name).write_bytes(data)
            rows.append({"path": name, "sha256": hashlib.sha256(data).hexdigest(), "role": "original",
                         "provenance": good["files"][0]["provenance"]})
        self.put_snapshot({**good, "files": [*good["files"], *rows]})
        base = Path(self.snapshot_ref).parent.as_posix()
        self.assertEqual([], self.readers()["unit"]["problems"])
        index = self.task().stdout
        for name in extra:
            self.assertIn(f"`{base}/files/{name}`", index, f"{name} 没进来源索引")

    def test_an_older_candidate_keeps_its_own_pack_when_the_flow_moved_on(self) -> None:
        """候选仍采用 v1、流程已登记 v2：蓝图任务交 v1 的包，Story 侧按流程读 v2，各取各的。"""
        v2 = self.pack.parent / "v2-later"
        shutil.copytree(self.pack, v2)
        prd2 = v2 / "files" / "RR" / "prd.md"
        prd2.write_bytes(prd2.read_bytes() + "新版本补的一句。\n".encode("utf-8"))
        snap = json.loads((v2 / "snapshot.json").read_text(encoding="utf-8"))
        for row in snap["files"]:
            if row["path"] == "RR/prd.md":
                row["sha256"] = hashlib.sha256(prd2.read_bytes()).hexdigest()
        (v2 / "snapshot.json").write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
        flow = json.loads(self.flow_file.read_text(encoding="utf-8"))
        flow["input"]["snapshot_ref"] = (v2 / "snapshot.json").relative_to(self.root).as_posix()
        self.flow_file.write_text(json.dumps(flow, ensure_ascii=False), encoding="utf-8")
        index = self.task().stdout.split("## 2.", 1)[0]
        self.assertIn(f"`{self.snapshot_ref}`", index)
        self.assertNotIn("v2-later", index, "候选配上了流程里的新版本")


    def test_backslash_references_reach_the_same_project_path(self) -> None:
        """R1：候选声明与流程快照用反斜杠写（原生判合法）：施工单位来源的键仍是正斜杠工程路径。"""
        slash = self.readers()
        text = self.canonical.read_bytes().decode("utf-8")
        self.assertIn(self.prd, text, "夹具变了，用例要跟着改")
        self.canonical.write_bytes(text.replace(self.prd, self.prd.replace("/", "\\\\")).encode("utf-8"))
        flow = json.loads(self.flow_file.read_text(encoding="utf-8"))
        flow["input"]["snapshot_ref"] = self.snapshot_ref.replace("/", "\\")
        self.flow_file.write_text(json.dumps(flow, ensure_ascii=False), encoding="utf-8")
        back = self.readers()
        self.assertEqual([], back["unit"]["problems"])
        self.assertEqual(sorted(slash["unit"]["documents"]), sorted(back["unit"]["documents"]))
        self.assertIn(self.prd, back["unit"]["documents"], "反斜杠声明的来源没按工程路径交出")

class ANativeSourceKeepsItsFragment(NativeCase):
    """原生直接入口：声明带片段的需求文件按原引用交给原生定位；片段找不到时任务不给，不先去掉片段再读。"""

    def test_the_fragment_is_indexed_and_a_missing_one_stops_the_task(self) -> None:
        index = self.task("--blueprint", BLUEPRINT, "--action", "design", "--audience", "author").stdout.split("## 2.", 1)[0]
        self.assertIn(f"`{REQUIREMENT}#REQ-WALLET-BALANCE-REFRESH`", index)
        canonical = self.root / "doc" / "features" / BLUEPRINT / "blueprint" / "component-blueprint.yaml"
        original = canonical.read_bytes()
        self.addCleanup(canonical.write_bytes, original)
        canonical.write_bytes(original.replace(b"#REQ-WALLET-BALANCE-REFRESH", b"#NO-SUCH-PART"))
        proc = self.task("--blueprint", BLUEPRINT, "--action", "design", "--audience", "author")
        self.assertEqual((1, ""), (proc.returncode, proc.stdout))
        self.assertIn("NO-SUCH-PART", proc.stderr)


if __name__ == "__main__":
    unittest.main()
