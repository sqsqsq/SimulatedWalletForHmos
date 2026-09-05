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

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "test" / "story" / "scripts"

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
        """先看本仓：模板没物化的话，工作区带什么都带不出来。"""
        for rel in CHAIN:
            with self.subTest(file=str(rel)):
                self.assertTrue((REPO_ROOT / rel).is_file(),
                                f"{rel} 没物化——按 framework/agents/opencode/adapter.yaml 落它")

    def test_the_chain_is_not_git_ignored(self) -> None:
        """`.opencode/.gitignore` 忽略了它们的话，换台机器 clone 出来就又没有了。"""
        import subprocess
        for rel in CHAIN:
            with self.subTest(file=str(rel)):
                proc = subprocess.run(
                    ["git", "check-ignore", "-q", str(rel)],
                    cwd=str(REPO_ROOT), capture_output=True, text=True)
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
        text = (REPO_ROOT / VERIFIER_DEF).read_text(encoding="utf-8")
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
        if not (self.runner.REPO_ROOT / "framework" / "harness" / "node_modules").is_dir():
            self.skipTest("本仓还没装 harness 依赖，无从判断它带没带过来")
        self.assertTrue((self.template / "framework" / "harness" / "node_modules").is_dir(),
                        "harness 依赖没进工作区——被测模型又要现装一遍")


if __name__ == "__main__":
    unittest.main()
