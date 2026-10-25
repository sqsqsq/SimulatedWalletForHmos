"""工作区必须带着 verifier 链——不带，被测侧就没有 verifier，也没有作者入口。

`run_multi_case.py` 的工作区白名单漏掉 `.opencode` 时的后果是可观察的：

  · `skill story` 在被测侧找不到，作者只能自己去翻 `SKILL.md` 找命令；
  · verifier 起的是 `general` 子代理（全工具），不是 frontmatter 里逐工具 deny 的只读 verifier。

那样的一跑，verifier 轴是失真的。

**这条测试不跑模型、不是 smoke**：它只建一次工作区模板，断言那两件在，
并且子代理定义说的是当前这一版协议。
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "test" / "scripts"
#: 被测侧从它复制：verifier 装置与宿主入口都以 demo 里的为准
DEMO = REPO_ROOT / "demo"
#: 宿主钩子配置：由 framework-init 物化进消费工程
HOOK_CONFIGS =(".claude/settings.json", ".cac/settings.json", ".codex/hooks.json", ".cursor/hooks.json")

# verifier 链的两件：只读子代理、作者入口。
# 报告由调用方原样写出，没有第三件——发布器那一环整体退场了。
CHAIN = (
    Path(".opencode/agent/verifier.md"),
    Path(".opencode/skill/story/SKILL.md"),
)

VERIFIER_DEF = Path(".opencode/agent/verifier.md")
#: dsh 的只读审查员是配置层里的一个工具实例，模板随被测 Framework 的本地补丁进来
DSH_LAYER = Path(".dsh/framework-verifier.patch.yml")
DSH_TEMPLATE = Path("framework/agents/dsh/templates/agents/framework-verifier.patch.yml")


def load_runner():
    """按路径加载驱动器——它不是包，直接 import 会因同名冲突取到别的模块。"""
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "run_multi_case_for_test", SCRIPTS / "run_multi_case.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def demo_state() -> tuple[str, str]:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(DEMO), capture_output=True, text=True).stdout
    status = subprocess.run(["git", "status", "--porcelain", "-uall", "--", "."], cwd=str(DEMO),
                            capture_output=True, text=True, encoding="utf-8").stdout
    return head.strip(), status


def framework_blob(cfg: dict, rel: str) -> bytes | None:
    proc = subprocess.run(["git", "cat-file", "blob", f"{cfg['release_commit']}:{cfg['framework_path']}/{rel}"],
                          cwd=str(REPO_ROOT), capture_output=True)
    return proc.stdout if proc.returncode == 0 else None


def framework_plus_patch(cfg: dict) -> dict[str, bytes]:
    """独立推算补丁涉及的文件：只取这些文件的发布原件放进空目录，单独打一次补丁，得到期望字节。"""
    rels = [line[len("+++ b/"):] for line in Path(cfg["patch_path"]).read_text(encoding="utf-8").splitlines()
            if line.startswith("+++ b/")]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "pkg"
        for rel in rels:
            body = framework_blob(cfg, rel)
            if body is not None:
                (root / "framework" / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / "framework" / rel).write_bytes(body)
        root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--directory=framework", str(cfg["patch_path"])],
                       cwd=str(root), check=True, capture_output=True,
                       env={**os.environ, "GIT_CEILING_DIRECTORIES": str(root.parent)})
        return {rel: (root / "framework" / rel).read_bytes() for rel in rels}


class AssembledFromTheFixedInputs:
    """一次装配的身份核对：被测 Framework、本地补丁与物化、开发源、demo 都按固定输入推算，不拿另一次装配互证。
    两个类各从空目录建一份 template，各自过这组核对，即两次重建结果一致。"""

    template: Path
    runner: object
    _tmp: tempfile.TemporaryDirectory

    @classmethod
    def build(cls, label: str) -> None:
        cls.runner = load_runner()
        cls.cfg = cls.runner.load_framework_under_test()
        cls._tmp = tempfile.TemporaryDirectory()
        cls.suite_root = Path(cls._tmp.name) / "suite"
        cls.suite_root.mkdir(parents=True)
        cls.demo_before = demo_state()
        # suite-id 带进程号：模板落在共享的系统临时目录下，并行跑时几个 worker 会撞同一条路径
        cls.template, _ = cls.runner.create_workspace_template(cls.suite_root, f"{label}-{os.getpid()}")
        cls.demo_after = demo_state()

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.template.parent, ignore_errors=True)
        cls._tmp.cleanup()

    def test_the_template_carries_the_framework_under_test(self) -> None:
        """template 的 Framework 是固定发布树加本地补丁：发布清单原样，补丁没碰的文件按清单摘要，补丁动过的等于单独打补丁的结果。"""
        import hashlib
        manifest_bytes = framework_blob(self.cfg, "RELEASE-MANIFEST.json")
        self.assertEqual(manifest_bytes, (self.template / "framework/RELEASE-MANIFEST.json").read_bytes())
        expected = framework_plus_patch(self.cfg)
        for rel, body in expected.items():
            with self.subTest(patched=rel):
                self.assertEqual(body, (self.template / "framework" / rel).read_bytes())
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        differ = [f["path"] for f in manifest["files"] if f["path"] not in expected
                  and hashlib.sha256((self.template / "framework" / f["path"]).read_bytes()).hexdigest() != f["sha256"]]
        self.assertEqual([], differ, "template 的 Framework 与被测发布件不是同一份")

    def test_patched_subagents_are_materialised_from_their_templates(self) -> None:
        """模板 → 物化产物逐字节同源：dsh 的审查员配置层与 opencode 的只读子代理。"""
        for materialised, source in ((DSH_LAYER, DSH_TEMPLATE),
                                     (VERIFIER_DEF, Path("framework/agents/opencode/templates/agents/verifier.md"))):
            with self.subTest(materialised=str(materialised)):
                self.assertEqual((self.template / source).read_bytes(), (self.template / materialised).read_bytes())

    def test_the_dev_source_is_installed_byte_for_byte(self) -> None:
        publish = self.runner.publish_to_demo
        files = publish.enumerate_source(self.runner.DEV_SOURCE)
        self.assertEqual(files, publish.enumerate_source(self.template / "doc/extensions"))
        for rel in files:
            with self.subTest(rel):
                self.assertEqual((self.runner.DEV_SOURCE / rel).read_bytes(),
                                 (self.template / "doc/extensions" / rel).read_bytes())

    def test_the_assembly_leaves_demo_untouched_and_records_its_inputs(self) -> None:
        self.assertEqual(self.demo_before, self.demo_after, "装配前后 demo 的提交或工作区变了")
        record = json.loads((self.suite_root / "workspace-boundary.json").read_text(encoding="utf-8"))["framework"]
        for key in ("release_commit", "tree_oid", "local_patch"):
            with self.subTest(key):
                self.assertEqual(self.cfg[key], record[key])
        self.assertEqual(self.cfg["patch_sha256"], record["local_patch_sha256"])
        self.assertIn("dsh", record["materialized_adapters"])
        self.assertIn(str(DSH_LAYER.as_posix()), record["subagents"])


class ASecondEmptyDirectoryRebuildsTheSameCombination(AssembledFromTheFixedInputs, unittest.TestCase):
    """第二次从空目录经同一入口重建：身份核对与第一次相同，不复用第一次的任何产物。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.build("assembly-rebuild-test")


class TheWorkspaceCarriesTheVerifierChain(AssembledFromTheFixedInputs, unittest.TestCase):
    """模板一个类建一次：它是只读夹具，而建一次要复制一份带依赖的完整工程。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.build("verifier-chain-test")

    def test_the_repo_has_the_chain_materialised(self) -> None:
        """先看 demo：它没物化的话，工作区带什么都带不出来。"""
        for rel in CHAIN:
            with self.subTest(file=str(rel)):
                self.assertTrue((DEMO / rel).is_file(),
                                f"demo 里没有 {rel}——按 framework/agents/opencode/adapter.yaml 落它")

    def test_the_chain_is_not_git_ignored(self) -> None:
        """`.opencode/.gitignore` 忽略了它们的话，换台机器 clone 出来就又没有了。"""
        import subprocess
        for rel in CHAIN:
            with self.subTest(file=str(rel)):
                proc = subprocess.run(
                    ["git", "check-ignore", "-q", str(rel)],
                    cwd=str(DEMO), capture_output=True, text=True)
                self.assertNotEqual(0, proc.returncode,
                                    f"{rel} 被 git 忽略了——它是随仓交付的协议件")

    def test_the_workspace_template_carries_the_chain(self) -> None:
        """三件都要在模板里。这是复制规则真的生效的唯一证据。"""
        for rel in CHAIN:
            with self.subTest(file=str(rel)):
                self.assertTrue((self.template / rel).is_file(),
                                f"工作区模板里没有 {rel}——被测侧就没有 verifier 或作者入口")

    def test_the_subagent_definition_speaks_the_current_protocol(self) -> None:
        """子代理定义停在旧协议上，交回来的稿就对不上这一版 request。"""
        text = (DEMO / VERIFIER_DEF).read_text(encoding="utf-8")
        for needle in ('"schema_version": "1.1"', "material_sha256", "verifier_subject_id"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        self.assertIn("mode: subagent", text, "opencode 认的是 frontmatter 里的 mode")
        self.assertIn("write: deny", text, "只读来自逐工具 deny 的声明，不是模型自述")

    def test_dependencies_ride_along_so_nothing_needs_installing(self) -> None:
        """依赖跟着进工作区（用户 2026-09-04 裁定）——工作区就是一个能直接跑的工程。

        这条 2026-09-04 换了边。原来断言的是「不带依赖」，理由是体积；代价的另一半是：
        工作区不带 `framework/harness/node_modules`，被测模型开跑先装一遍依赖，
        那几分钟每一轮都要付一次。
        """
        if not (DEMO / "framework" / "harness" / "node_modules").is_dir():
            self.skipTest("本仓还没装 harness 依赖，无从判断它带没带过来")
        self.assertTrue((self.template / "framework" / "harness" / "node_modules").is_dir(),
                        "harness 依赖没进工作区——被测模型又要现装一遍")


    def test_the_maintenance_copy_of_the_verifier_is_the_demo_one(self) -> None:
        """根的 verifier 维护装置是 demo 物化件的拷贝，两份逐字节相同。"""
        self.assertEqual((DEMO / VERIFIER_DEF).read_bytes(), (REPO_ROOT / VERIFIER_DEF).read_bytes())

    def test_the_dsh_verifier_is_a_read_only_spawn_with_the_framework_protocol(self) -> None:
        """dsh 审查员按 DSH 0.2.1 Preset 写法：人设在 Agent Preset，子级 in-process spawn，preset 只装读与检索工具；
        registry 默认空 preset，主会话不受影响。人设沿用被测 Framework 的阶段协议（含产品失败诊断例外与物理路径规则），
        另有自足审查任务的分支。"""
        import yaml
        adapter = yaml.safe_load((self.template / "framework/agents/dsh/adapter.yaml").read_text(encoding="utf-8"))
        self.assertIsNone(adapter["commands"])
        self.assertEqual({"target_dir": ".dsh", "template_dir": "templates/agents", "update_policy": "auto_overwrite"},
                         adapter["subagents"])
        self.assertIs(True, adapter["verifier_subagent"])
        self.assertNotIn("goal_capability", adapter, "dsh 只承接 interactive")
        config = json.loads((self.template / "framework.config.json").read_text(encoding="utf-8"))
        self.assertIn("dsh", config["materialized_adapters"])
        rows = {row["id"]: row for row in yaml.safe_load((self.template / DSH_LAYER).read_text(encoding="utf-8"))[0]["insert"]}
        self.assertEqual(["agent-preset-registry", "preset-standard", "preset-maison-verifier", "maison-verifier"], list(rows))
        self.assertEqual({"default": "standard"}, rows["agent-preset-registry"]["config"])
        self.assertEqual({"id": "standard", "plugins": []}, rows["preset-standard"]["config"])
        self.assertEqual({"provider": "spawn", "toolName": "verifier", "maxDepth": 1, "agentPreset": "maison-verifier"},
                         rows["maison-verifier"]["config"], "审查员工具带了已退的 persona / toolFilter 等字段")
        plugins = {row["id"]: row for row in rows["preset-maison-verifier"]["config"]["plugins"]}
        self.assertEqual(["persona", "tool-fs", "tool-fs-search"], list(plugins))
        self.assertEqual({"write": False, "edit": False}, plugins["tool-fs"]["config"], "审查员 preset 带了写工具")
        persona = plugins["persona"]["config"]["prefix"]
        stage = (self.template / "framework/agents/claude/templates/agents/verifier.md").read_text(encoding="utf-8")
        for needle in ('"schema_version": "1.1"', "material_sha256", "verifier_subject_id: <request.subject_id>",
                       "本轮为产品失败诊断", "路径解析（BLOCKER）", "## 其它独立只读审查任务", "精简规则不省略它要求的明细"):
            with self.subTest(needle=needle):
                self.assertIn(needle, persona)
        ending = stage.split("**回答的最后必须且只能出现一个终态块**", 1)[1].split("## 硬性规则", 1)[0]
        self.assertIn(ending, persona, "阶段报告合同与被测 Framework 的 verifier 不是同一版")

    def test_the_init_registry_offers_exactly_the_adapters_on_disk(self) -> None:
        """framework-init 的物化选项与 framework/agents 下的 adapter 双向对上：本地补丁加了 dsh 就要有它的选项。"""
        import yaml
        registry = yaml.safe_load((self.template / "framework/skills/reference/confirmation-registry.yaml")
                                  .read_text(encoding="utf-8"))
        entry = next(e for e in registry["entries"] if e["id"] == "init.materialized_adapters")
        on_disk = {p.parent.name for p in (self.template / "framework/agents").glob("*/adapter.yaml")}
        self.assertEqual(on_disk, {o["value"] for o in entry["options"]})

    #: 作者读到的 verifier 调用指引：本地补丁统一为「专用 verifier 角色」
    CALL_TEXTS = (
        "framework/agents/shared/agent-bundle/templates/rules/framework-agent-execution.mdc",
        "framework/skills/reference/agents-entry-detail.md",
        "framework/skills/feature/spec/SKILL.md",
        "framework/skills/feature/plan/SKILL.md",
        "framework/skills/feature/coding/SKILL.md",
        "framework/skills/reference/code-review-workflow-detail.md",
        "framework/skills/reference/business-ut-workflow-detail.md",
        "framework/skills/reference/device-testing-workflow-detail.md",
        "framework/harness/harness-runner.ts",
        "framework/harness/scripts/utils/verifier-evidence.ts",
    )

    def test_every_call_text_names_the_dedicated_role(self) -> None:
        for rel in self.CALL_TEXTS:
            with self.subTest(rel):
                text = (self.template / rel).read_text(encoding="utf-8")
                self.assertIn("专用 verifier 角色", text)
                for stale in ("通过 Task 工具触发", "Task 触发 verifier", "作为 Task prompt 投给", "投给 subagent_type=verifier"):
                    self.assertNotIn(stale, text, "还把任意 Task 调用当成审查入口")

    def test_the_receipt_does_not_claim_a_task_call(self) -> None:
        for rel in ("framework/harness/scripts/utils/receipt-scaffold.ts",
                    "framework/harness/templates/phase-completion-receipt.md"):
            with self.subTest(rel):
                text = (self.template / rel).read_text(encoding="utf-8")
                self.assertNotIn("Task(subagent_type=verifier)", text)
                self.assertIn("host_verifier_role", text)


    def test_the_two_agents_entries_follow_their_owners(self) -> None:
        """demo 装着 1.9.8：story 入口等于它已装包登记的来源。template 装着开发版：两个 Skill 入口都由
        Framework 按 manifest 物化，带归属标记、指向各自的 SKILL。"""
        import yaml
        installed = yaml.safe_load((DEMO / "doc/extensions/manifest.yaml").read_text(encoding="utf-8"))
        for item in installed["provides"].get("bridges", []):
            with self.subTest(demo=item["target"]):
                self.assertEqual((DEMO / "doc/extensions" / item["source"]).read_bytes(),
                                 (DEMO / item["target"]).read_bytes(), "demo 的入口不是它已装包登记的那份")
        for skill in ("story", "story-adaptation"):
            with self.subTest(template=skill):
                text = (self.template / f".agents/skills/{skill}/SKILL.md").read_text(encoding="utf-8")
                self.assertIn("agent-maison:instance-extension-bridge", text)
                self.assertIn(f"doc/extensions/skills/{skill}/SKILL.md", text)

    def test_hook_configs_live_in_the_consumer_and_resolve_from_its_root(self) -> None:
        """四份钩子配置只在消费工程里；其中每条命令都从消费根（含带空格的 workspace）找得到脚本。

        命令登记由 Framework 物化决定（3.1 起 Codex 不再登记 Stop 钩子），这里不预设哪个宿主有哪条钩子。
        """
        import re

        def commands(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == "command" and isinstance(value, str):
                        yield value
                    else:
                        yield from commands(value)
            elif isinstance(node, list):
                for item in node:
                    yield from commands(item)

        scripts = []
        for rel in HOOK_CONFIGS:
            with self.subTest(rel):
                self.assertTrue((DEMO / rel).is_file())
                self.assertTrue((self.template / rel).is_file())
                self.assertFalse((REPO_ROOT / rel).exists(), f"维护仓根还挂着消费钩子 {rel}")
                for command in commands(json.loads((DEMO / rel).read_text(encoding="utf-8"))):
                    self.assertNotIn(":\\", command, f"{rel} 还是写死的机器路径：{command}")
                    # `node "<脚本>"` 或 `node <脚本>`；脚本以消费根为基准（${…_PROJECT_DIR}/ 前缀即消费根）
                    script = re.sub(r"^\$\{[A-Z0-9_]+\}/", "", command.split(None, 1)[1].strip().strip('"'))
                    scripts.append(script)
        self.assertTrue(scripts, "四份钩子配置里一条命令都没有")
        spaced = Path(tempfile.mkdtemp(prefix="ws with space-"))
        self.addCleanup(shutil.rmtree, spaced, True)
        for script in scripts:
            (spaced / script).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.template / script, spaced / script)
        for root in (DEMO, self.template, spaced):
            for script in scripts:
                with self.subTest(root=str(root), script=script):
                    self.assertTrue((root / script).is_file(), f"{root} 下找不到 {script}")


class AFrameworkInputThatDoesNotMatchStopsTheAssembly(unittest.TestCase):
    """固定输入登记的树 OID 与发布提交对不上：装配在写任何东西之前停下，不拿别的版本顶替。"""

    def test_a_wrong_tree_oid_stops(self) -> None:
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            cfg = json.loads(runner.FRAMEWORK_UNDER_TEST.read_text(encoding="utf-8"))
            cfg["tree_oid"] = "0" * 40
            wrong = Path(tmp) / "framework-under-test.json"
            wrong.write_text(json.dumps(cfg), encoding="utf-8")
            original = runner.FRAMEWORK_UNDER_TEST
            runner.FRAMEWORK_UNDER_TEST = wrong
            try:
                with self.assertRaises(SystemExit) as caught:
                    runner.load_framework_under_test()
            finally:
                runner.FRAMEWORK_UNDER_TEST = original
        self.assertIn("被测 Framework 发布树", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
