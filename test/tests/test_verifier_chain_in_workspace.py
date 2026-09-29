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
        target = ".agents/skills/story/SKILL.md"
        installed = next(b for b in bridges(DEMO / "doc/extensions") if b.target == target)
        self.assertEqual(installed.source.read_bytes(), (DEMO / target).read_bytes(), "demo 的 story 入口不是它已装包登记的那份")
        dev = next(b for b in bridges(self.runner.DEV_SOURCE) if b.target == target)
        self.assertEqual(dev.source.read_bytes(), (self.template / target).read_bytes())
        rel = ".agents/skills/story-adaptation/SKILL.md"
        self.assertNotIn(rel, [b.target for b in bridges(self.runner.DEV_SOURCE)])
        self.assertEqual((DEMO / rel).read_bytes(), (self.template / rel).read_bytes())

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


if __name__ == "__main__":
    unittest.main()
