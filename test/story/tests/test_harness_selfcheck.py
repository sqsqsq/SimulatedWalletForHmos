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


class LedgerDoesNotDirtyItsFixtures(unittest.TestCase):
    """台账跑一遍，夹具一个字节都不该变。

    实测踩过：spec post_check 在夹具**原地**跑，而 hook 通过时也会写留痕
    （`spec/reports/ext-post-check.json`，里面有时间戳）。于是每跑一次台账就有两个
    夹具文件变脏，长期挂在工作区里被一次次捎带提交——而谁也说不清它们改了什么。
    """

    def test_the_spec_post_check_runs_on_a_copy(self) -> None:
        source = (SCRIPTS / "check_failure_modes.py").read_text(encoding="utf-8")
        body = source.split("def _spec_post_check")[1].split("\ndef ")[0]
        self.assertIn("TemporaryDirectory", body,
                      "spec post_check 要在副本上跑——它会写留痕，原地跑就把夹具写脏了")
        self.assertIn("copytree", body)


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


class StallReadingReachesEveryCaseProjection(unittest.TestCase):
    """停滞读数要落在**每一份** Case 投影里，不是其中几份。

    由来是一个真实的漏网：`refresh_record` 把 `events_idle_sec` 算好挂在 record 上，
    另外两处投影也带着它，唯独 `poll` 输出的那一份漏了——于是「CLI 多久没吐字了」
    这条告警对宿主完全不可见。**它要防的正是「每个指标都正常而它已经停了」，
    自己却以那个形态失效了一整轮。**

    判法不点名某一处：把**交到宿主手上的** Case 行都找出来——同时报 `case` 与
    `feature`、且各列是从 record 上取的那种字典——逐个要求带上读数。
    再加一处这样的投影时它自动生效。

    内部结构不在此列：新建记录的模板、attempt 记录、稳定性与 diff 快照都不是给宿主
    看的那份，把它们一起要求只会逼出一堆无意义的字段。
    """

    RUN_MULTI = SCRIPTS / "run_multi_case.py"
    REQUIRED = ("events_idle_sec", "stalled")

    @staticmethod
    def _reads_from_record(node: ast.Dict) -> bool:
        """各列是 `record.get(...)` 取出来的 —— 投影的形态，不是模板的形态。"""
        reads = 0
        for value in node.values:
            if (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
                    and value.func.attr == "get"
                    and isinstance(value.func.value, ast.Name)
                    and value.func.value.id == "record"):
                reads += 1
        return reads >= 5

    def case_row_dicts(self) -> list:
        tree = ast.parse(self.RUN_MULTI.read_text(encoding="utf-8"),
                         filename=str(self.RUN_MULTI))
        rows = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            keys = {k.value for k in node.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)}
            if {"case", "feature", "status"} <= keys and self._reads_from_record(node):
                rows.append((node, keys))
        return rows

    def test_every_case_row_carries_the_reading(self) -> None:
        rows = self.case_row_dicts()
        self.assertTrue(rows, "找不到任何 Case 行投影——判据失去对象")
        missing = []
        for node, keys in rows:
            for field in self.REQUIRED:
                if field not in keys:
                    missing.append("行 %s 缺 %s" % (node.lineno, field))
        self.assertEqual(missing, [],
                         "有 Case 投影不带停滞读数：" + "；".join(missing))

    def test_the_reading_is_computed_somewhere(self) -> None:
        """投影带着它，但没人算它，同样是空的。"""
        body = self.RUN_MULTI.read_text(encoding="utf-8")
        self.assertIn("def events_idle_sec(", body)
        self.assertIn('record["events_idle_sec"] = ', body)


if __name__ == "__main__":
    unittest.main()
