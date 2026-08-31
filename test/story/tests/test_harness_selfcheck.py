"""测试装置自己的回归：调用点与定义对不对得上、时限有没有被偷偷放回来。

这一份的由来是一个真实的漏网：`send_scripted_reply` 改名成 `request_host_reply` 时
**调用点漏改**，任何带规划的 Case 进入 `awaiting_reply` 都会 NameError。全部既有单测
都直接调新名字，绕过了 `poll_suite` 那个唯一的生产调用点，于是一条都没响。

装置自己的代码没有编译器守着——Python 要到那一行真的执行才报 NameError，而那一行
只在实跑的某个分支上。所以这里用 AST 静态扫一遍：**每个被调用的裸名都得有出处**。
"""
from __future__ import annotations

import ast
import builtins
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "test" / "story" / "scripts"
RUN_CASE = SCRIPTS / "run_case.py"
CLIS_JSON = REPO_ROOT / "tools" / "cli" / "config" / "clis.json"


def _module_names(tree: ast.Module) -> set[str]:
    """模块级能解析到的名字：import、赋值、函数、类。"""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            names.update(node.names)
    return names


class CallSitesResolve(unittest.TestCase):
    """每个被调用的裸名都得有定义——抓「改了名字忘了改调用点」。"""

    def test_every_called_name_has_a_definition(self) -> None:
        known_builtins = set(dir(builtins))
        for path in sorted(SCRIPTS.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            defined = _module_names(tree) | known_builtins
            unresolved = sorted({
                node.func.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id not in defined
            })
            self.assertEqual([], unresolved,
                             f"{path.name} 调用了没有定义的名字：{unresolved}"
                             "——多半是改名时漏了调用点")


    def test_the_check_itself_catches_a_renamed_function(self) -> None:
        """反向锁：把真实发生过的那个 bug 缩成三行喂进来，本判据必须报出来。

        判据自己不出声，等于没有判据——上一轮五条单测全绿而生产代码是坏的，
        就是因为它们绕过了那个调用点。
        """
        broken = "def request_host_reply(record):\n    pass\n\nsend_scripted_reply(1)\n"
        tree = ast.parse(broken)
        defined = _module_names(tree) | set(dir(builtins))
        unresolved = [node.func.id for node in ast.walk(tree)
                      if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                      and node.func.id not in defined]
        self.assertEqual(["send_scripted_reply"], unresolved)


class NoTimeLimitStaysExplicit(unittest.TestCase):
    """`clis.json` 的全局默认仍是有限时限，story 侧靠显式传 0 绕开。

    哪天有人把这两个关键字参数删了，1 小时硬超时就会**静默**回来——正是本域
    刚刚才裁掉的那种「装置限制先于终点到达」。
    """

    def test_story_runner_passes_zero_timeouts_explicitly(self) -> None:
        defaults = json.loads(CLIS_JSON.read_text(encoding="utf-8"))["defaults"]["timeout"]
        if defaults.get("soft_sec", 0) <= 0 and defaults.get("hard_sec", 0) <= 0:
            self.skipTest("全局默认已是无限制，这条守卫无对象")
        tree = ast.parse(RUN_CASE.read_text(encoding="utf-8"), filename=str(RUN_CASE))
        requests = [node for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "CliRunRequest"]
        self.assertTrue(requests, "run_case.py 里找不到 CliRunRequest 的构造")
        for call in requests:
            passed = {kw.arg for kw in call.keywords}
            for key in ("soft_timeout_sec", "hard_timeout_sec"):
                self.assertIn(key, passed,
                              f"CliRunRequest 没有显式传 {key}——"
                              "会落回 clis.json 的全局默认，硬超时就回来了")


if __name__ == "__main__":
    unittest.main()
