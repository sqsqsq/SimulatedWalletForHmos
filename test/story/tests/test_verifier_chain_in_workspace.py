"""工作区必须带着 verifier 链——不带，被测侧就没有 verifier，也没有作者入口。

首跑（`story-suite-20260904-091600`）实测的后果：`run_multi_case.py` 的工作区白名单
不含 `.opencode`，于是

  · `skill story` 在被测侧找不到，作者只能自己去翻 `SKILL.md` 找命令；
  · verifier 起的是 `general` 子代理（全工具），不是 frontmatter 里逐工具 deny 的只读 verifier；
  · 发布插件不在，`verifier.report.<subject>.json` 由被测主模型**自己手造**
    （`agent_id: storiesuite-verifier-stub`），而 `check-receipt` 照收。

那一跑的 verifier 轴因此失真，步骤 1 的 D1 链路等于没验。

**这条测试不跑模型、不是 smoke**：它只建一次工作区模板，断言那三个文件在。
删掉任一个都会红——那正是它要拦的事。
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "test" / "story" / "scripts"

# verifier 链的三件：只读子代理、结论发布插件、作者入口
CHAIN = (
    Path(".opencode/agent/verifier.md"),
    Path(".opencode/plugin/record-verifier-report.js"),
    Path(".opencode/skill/story/SKILL.md"),
)


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
    def setUp(self) -> None:
        self.runner = load_runner()

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
        """建一次模板，三件都要在里面。这是白名单真的生效的唯一证据。"""
        with tempfile.TemporaryDirectory() as tmp:
            suite_root = Path(tmp) / "suite"
            suite_root.mkdir(parents=True)
            template, _ = self.runner.create_workspace_template(
                suite_root, "verifier-chain-test")
            self.addCleanup(shutil.rmtree, template.parent, True)
            for rel in CHAIN:
                with self.subTest(file=str(rel)):
                    self.assertTrue((template / rel).is_file(),
                                    f"工作区模板里没有 {rel}——被测侧就没有 verifier 或作者入口")

    def test_node_modules_does_not_ride_along(self) -> None:
        """`.opencode/` 下有 opencode 自装的依赖，那些不该进工作区。"""
        with tempfile.TemporaryDirectory() as tmp:
            suite_root = Path(tmp) / "suite"
            suite_root.mkdir(parents=True)
            template, _ = self.runner.create_workspace_template(
                suite_root, "verifier-chain-nm")
            self.addCleanup(shutil.rmtree, template.parent, True)
            self.assertFalse((template / ".opencode" / "node_modules").exists(),
                             "node_modules 跟着进了工作区")


if __name__ == "__main__":
    unittest.main()
