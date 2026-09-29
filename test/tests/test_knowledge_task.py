"""原生身份读取与动作前知识任务（步骤 1）：在接入 demo Framework 的临时工程里，用真实蓝图与施工单位跑。

锁四件：蓝图与施工单位按 Framework 原生身份读，坏身份、缺对象、过期引用各自报出；知识任务六块齐全、知识原文
按激活顺序完整给出，空清单与坏登记分开；该失败时 stdout 不给半份、stderr 写对象、缺口与责任；审查者经
pre_verifier 拿到的是同一个加载器出的任务。
"""
from __future__ import annotations

import base64
import json
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
    shutil.copytree(FIXTURE / "doc" / "requirements", root / "doc" / "requirements", dirs_exist_ok=True)
    # 蓝图的开发视图按工程的模块目录解析模块：用 demo 的那份，夹具蓝图写的是 demo 的模块
    shutil.copy2(REPO_ROOT / "demo" / "doc" / "module-catalog.yaml", root / "doc" / "module-catalog.yaml")
    return root


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

    def test_a_unit_reads_its_blueprint_reference_design_refs_and_derived_inputs(self) -> None:
        code, out = self.access("--action", "feature", "--feature", CU)
        self.assertEqual((0, "ok"), (code, out["status"]), out)
        self.assertEqual({"kind": "cu", "blueprintId": BLUEPRINT, "changeUnitId": "balance-refresh"},
                         {k: out["identity"][k] for k in ("kind", "blueprintId", "changeUnitId")})
        self.assertEqual("doc/features/wallet-balance-refresh/balance-refresh", out["feature_path"])
        self.assertTrue(out["design_refs"])
        self.assertEqual({"acceptance": "resolved", "contracts": "resolved"},
                         {k: v["state"] for k, v in out["inputs"].items()})

    def test_bad_identities_and_missing_objects_fail_with_native_codes(self) -> None:
        cases = {
            ("--action", "blueprint", "--blueprint", "../evil"): ("invalid", "blueprint_id_invalid"),
            ("--action", "blueprint", "--blueprint", "not-there"): ("missing", "component_blueprint_missing"),
            ("--action", "feature", "--feature", "cu-!!!"): ("invalid", "change_unit_feature_id_invalid"),
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
        code, out = self.access("--action", "feature", "--feature", other)
        self.assertEqual(1, code, out)

    def test_a_unit_whose_blueprint_changed_is_stale(self) -> None:
        canonical = self.root / "doc/features" / BLUEPRINT / "blueprint" / "component-blueprint.yaml"
        original = canonical.read_bytes()
        self.addCleanup(canonical.write_bytes, original)
        canonical.write_bytes(original + b"\n# changed after the unit was prepared\n")
        code, out = self.access("--action", "feature", "--feature", CU)
        self.assertEqual((1, "stale"), (code, out.get("status")), out)

    def test_arguments_are_checked_before_anything_is_read(self) -> None:
        for args in (("--action", "feature"), ("--action", "blueprint", "--blueprint", BLUEPRINT, "--purpose", "x"),
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
        unit = json.loads(run("--action", "feature", "--feature", CU).stdout)
        self.assertEqual(("ok", "work/features/wallet-balance-refresh/balance-refresh"), (unit["status"], unit["feature_path"]))
        self.assertFalse((root / "doc" / "features").exists(), "读取造出了默认需求目录")


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
