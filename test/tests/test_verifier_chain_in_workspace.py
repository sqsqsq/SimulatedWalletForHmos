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
#: demo 当前的发布基线（1.9.7 发布提交）
HOOK_CONFIGS = (".claude/settings.json", ".cac/settings.json", ".codex/hooks.json", ".cursor/hooks.json")

# verifier 链的两件：只读子代理、作者入口。
# 报告由调用方原样写出，没有第三件——发布器那一环整体退场了。
# dsh 的只读子代理是配置层里的一个工具实例，作者入口与 generic 共用 `.agents`。
CHAIN = (
    Path(".opencode/agent/verifier.md"),
    Path(".opencode/skill/story/SKILL.md"),
    Path(".dsh/framework-verifier.patch.yml"),
    Path(".dsh/skills/story/SKILL.md"),
    Path(".agents/skills/story/SKILL.md"),
)

VERIFIER_DEF = Path(".opencode/agent/verifier.md")
DSH_LAYER = Path(".dsh/framework-verifier.patch.yml")
DSH_ADAPTER = Path("framework/agents/dsh")


def load_runner():
    """按路径加载驱动器——它不是包，直接 import 会因同名冲突取到别的模块。"""
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "run_multi_case_for_test", SCRIPTS / "run_multi_case.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TheWorkspaceCarriesTheVerifierChain(unittest.TestCase):
    """模板一个类建一次：它是只读夹具，而建一次要复制一份带依赖的完整工程。"""

    template: Path
    _tmp: tempfile.TemporaryDirectory

    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = load_runner()
        cls._tmp = tempfile.TemporaryDirectory()
        suite_root = Path(cls._tmp.name) / "suite"
        suite_root.mkdir(parents=True)
        # suite-id 带进程号：模板落在共享的系统临时目录下，并行跑时几个 worker 会撞同一条路径
        cls.template, _ = cls.runner.create_workspace_template(
            suite_root, f"verifier-chain-test-{os.getpid()}")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.template.parent, ignore_errors=True)
        cls._tmp.cleanup()

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

    def test_the_dsh_verifier_is_a_read_only_spawn_with_the_same_protocol(self) -> None:
        """dsh 审查员（DSH 0.2.1 写法）：根目录与 demo 同一份配置层，人设放在 Agent Preset，子级 in-process spawn，
        preset 只装读与检索工具；registry 默认空 preset，主会话不受影响。阶段协议与 opencode 子代理同一版，另有自足审查任务的分支。
        adapter 模板、demo 物化件与根目录维护拷贝是同一份：UPDATE 重新物化不会换掉可用的配置层。"""
        import yaml
        layer = DEMO / DSH_LAYER
        self.assertEqual((REPO_ROOT / DSH_LAYER).read_bytes(), layer.read_bytes(), "根目录与 demo 的 dsh 配置层不是同一份")
        template = DEMO / DSH_ADAPTER / "templates" / "agents" / DSH_LAYER.name
        self.assertEqual(template.read_bytes(), layer.read_bytes(), "dsh adapter 模板与 demo 物化件不是同一份")
        adapter = yaml.safe_load((DEMO / DSH_ADAPTER / "adapter.yaml").read_text(encoding="utf-8"))
        self.assertEqual({"target_dir": ".dsh", "template_dir": "templates/agents", "update_policy": "auto_overwrite"},
                         adapter["commands"]["subagents"])
        self.assertIs(True, adapter["verifier_subagent"], "demo 的 dsh 审查员已正式入册")
        # 与 opencode 同构的自有 bundle：阶段技能与规则物化在 .dsh 下，不再借 generic/chrys 的 .agents
        self.assertEqual(".dsh/skills", adapter["skill_bridge"]["target_dir"])
        self.assertEqual(".dsh/rules", adapter["rules"]["target_dir"])
        phase = lambda root: {p.parent.name for p in (DEMO / root).glob("*/SKILL.md")} - {"story", "story-adaptation"}
        self.assertEqual(phase(".opencode/skill"), phase(".dsh/skills"), ".dsh 的阶段技能与 .opencode 不是同一套")
        self.assertEqual({p.name for p in (DEMO / ".opencode/rules").iterdir()},
                         {p.name for p in (DEMO / ".dsh/rules").iterdir()})
        rows = {row["id"]: row for row in yaml.safe_load(layer.read_text(encoding="utf-8"))[0]["insert"]}
        self.assertEqual(["agent-preset-registry", "preset-standard", "preset-maison-verifier", "maison-verifier"], list(rows))
        self.assertEqual({"default": "standard"}, rows["agent-preset-registry"]["config"])
        self.assertEqual({"id": "standard", "plugins": []}, rows["preset-standard"]["config"])
        self.assertEqual({"provider": "spawn", "toolName": "verifier", "maxDepth": 1, "agentPreset": "maison-verifier"},
                         rows["maison-verifier"]["config"])
        plugins = {row["id"]: row for row in rows["preset-maison-verifier"]["config"]["plugins"]}
        self.assertEqual(["persona", "tool-fs", "tool-fs-search"], list(plugins))
        self.assertEqual({"write": False, "edit": False}, plugins["tool-fs"]["config"], "审查员 preset 带了写工具")
        persona = plugins["persona"]["config"]["prefix"]
        stage = (DEMO / VERIFIER_DEF).read_text(encoding="utf-8")
        for needle in ('"schema_version": "1.1"', "material_sha256", "maison-verifier-result:v1",
                       "verifier_subject_id: <request.subject_id>", "## 其它独立只读审查任务"):
            with self.subTest(needle=needle):
                self.assertIn(needle, persona)
        # 终态块合同与 opencode 子代理逐字同一版；任务另有结构明细要求时不被通用精简规则省掉
        ending = stage.split("**回答的最后必须且只能出现一个终态块**", 1)[1].split("## 硬性规则", 1)[0]
        self.assertIn(ending, persona, "阶段报告合同与 opencode 子代理不是同一版")
        self.assertIn("精简规则不省略它要求的明细", persona)

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

    def test_the_two_agents_entries_follow_their_owners(self) -> None:
        """story 入口归 Extension：demo 与 template 各等于自己所装包登记的来源；
        story-adaptation 入口不在登记里，是 Framework 物化的那份，template 保持 demo 的原样。"""
        bridges = self.runner.publish_to_demo.manifest_bridges
        for target in (".agents/skills/story/SKILL.md", ".dsh/skills/story/SKILL.md"):
            with self.subTest(target=target):
                installed = next(b for b in bridges(DEMO / "doc/extensions") if b.target == target)
                self.assertEqual(installed.source.read_bytes(), (DEMO / target).read_bytes(), "demo 的 story 入口不是它已装包登记的那份")
                dev = next(b for b in bridges(self.runner.DEV_SOURCE) if b.target == target)
                self.assertEqual(dev.source.read_bytes(), (self.template / target).read_bytes())
        rel = ".agents/skills/story-adaptation/SKILL.md"
        self.assertNotIn(rel, [b.target for b in bridges(self.runner.DEV_SOURCE)])
        self.assertEqual((DEMO / rel).read_bytes(), (self.template / rel).read_bytes())

    def test_hook_configs_live_in_the_consumer_and_resolve_from_its_root(self) -> None:
        """四份钩子配置只在消费工程里；Codex 的 Stop 命令从消费根（含带空格的 workspace）找得到脚本。"""
        import json
        for rel in HOOK_CONFIGS:
            with self.subTest(rel):
                self.assertTrue((DEMO / rel).is_file())
                self.assertTrue((self.template / rel).is_file())
                self.assertFalse((REPO_ROOT / rel).exists(), f"维护仓根还挂着消费钩子 {rel}")
        command = json.loads((DEMO / ".codex/hooks.json").read_text(encoding="utf-8"))["hooks"]["Stop"][0]["hooks"][0]["command"]
        self.assertNotIn(":\\", command, "还是写死的机器路径")
        script = command.split('"')[1]
        spaced = Path(tempfile.mkdtemp(prefix="ws with space-"))
        self.addCleanup(shutil.rmtree, spaced, True)
        (spaced / ".codex" / "hooks").mkdir(parents=True)
        shutil.copy2(self.template / script, spaced / script)
        for root in (DEMO, self.template, spaced):
            with self.subTest(root=str(root)):
                self.assertTrue((root / script).is_file(), f"{root} 下找不到 {script}")



class TheVerifierCallTextNamesTheDedicatedRole(unittest.TestCase):
    """作者读到的调用指引都指向宿主登记的专用 verifier 角色，不让通用研究/开发子 agent 顶替（本地定制，AGENTS §2）。"""

    RULE = "framework/agents/shared/agent-bundle/templates/rules/framework-agent-execution.mdc"
    CALL_TEXTS = (
        "AGENTS.md", "CLAUDE.md", "framework/templates/AGENTS.md.template",
        "framework/skills/reference/agents-entry-detail.md", RULE,
        "framework/harness/harness-runner.ts", "framework/harness/scripts/utils/verifier-evidence.ts",
        *(f"framework/skills/feature/{s}/SKILL.md"
          for s in ("business-ut", "code-review", "coding", "device-testing", "plan", "spec")),
    )

    def test_every_call_text_names_the_dedicated_role(self) -> None:
        for rel in self.CALL_TEXTS:
            with self.subTest(rel):
                text = (DEMO / rel).read_text(encoding="utf-8")
                self.assertIn("专用 verifier 角色", text)
                for stale in ("通过 Task 工具触发", "Task 触发 verifier", "作为 Task prompt 投给", "投给 subagent_type=verifier"):
                    self.assertNotIn(stale, text, "还把任意 Task 调用当成审查入口")

    def test_the_installed_rule_copies_are_the_template(self) -> None:
        template = (DEMO / self.RULE).read_bytes()
        for host in (".agents", ".codex", ".cursor", ".opencode"):
            with self.subTest(host):
                self.assertEqual(template, (DEMO / host / "rules" / "framework-agent-execution.mdc").read_bytes())

    def test_the_receipt_does_not_claim_a_task_call(self) -> None:
        for rel in ("framework/harness/scripts/utils/receipt-scaffold.ts",
                    "framework/harness/templates/phase-completion-receipt.md"):
            with self.subTest(rel):
                text = (DEMO / rel).read_text(encoding="utf-8")
                self.assertNotIn("Task(subagent_type=verifier)", text)
                self.assertIn("host_verifier_role", text)

if __name__ == "__main__":
    unittest.main()
