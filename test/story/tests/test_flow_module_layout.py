"""流程与材料按职责归位之后，仍只有一条调用方向与一条资源定位规则。

三件事各自会静默出问题，所以各有一组：

1. **方向**——命令问路由、路由不问命令。反过来接一条，`decide` 与 `next_step`
   就会互相 import 成环；环的报错出现在第一个 import 它的人身上，与真正接错的那处无关。
2. **导入不等于执行**——子模块被 import 时不许解析参数、不许写盘。谁在 import 期
   跑了 CLI，测试与 hook 只要读一个常量就会顺带改动工作区。
3. **定位**——合同、模板与公共 CLI 都由脚本自己的位置定。数错一层目录的表现是
   「命令在仓里跑得通、在别人的工程上跑不通」：本地看不出来。
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CORE = REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts" / "core"
FLOW = CORE / "flow"
FLOW_CLI = CORE / "story_flow.py"
IMPORT_CLI = CORE / "import_sources.py"

#: 允许的依赖方向：键可以 import 值，值不能反过来 import 键。
#: state 一个兄弟都不 import；lifecycle/decisions/rounds/submission 是命令，谁也不 import 它们。
ALLOWED = {
    "state": set(),
    "inputs": {"state"},
    "meetings": {"state"},
    "routing": {"state", "inputs", "meetings"},
    "decisions": {"state", "inputs", "routing", "meetings"},
    "rounds": {"state", "inputs", "routing", "meetings"},
    "submission": {"state", "inputs", "routing"},
    "lifecycle": {"state", "inputs", "routing", "meetings"},
}


def imported_modules(path: Path) -> set[str]:
    """这个文件 import 了哪些 `flow.*` 兄弟（含函数内的延迟 import）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("flow."):
            out.add(node.module.split(".", 1)[1])
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("flow."):
                    out.add(alias.name.split(".", 1)[1])
    return out


class TheCallGraphHasOneDirection(unittest.TestCase):
    """命令问路由，路由不问命令。"""

    def test_no_module_imports_a_command_module(self) -> None:
        for name, allowed in ALLOWED.items():
            with self.subTest(module=name):
                actual = imported_modules(FLOW / f"{name}.py")
                self.assertTrue(
                    actual <= allowed,
                    f"flow/{name}.py 反向 import 了 {sorted(actual - allowed)}——"
                    "方向反过来就会成环")

    def test_no_module_imports_the_entry(self) -> None:
        """功能模块不许 import 入口：入口 import 它们，两向都有就是环。"""
        for path in sorted(FLOW.glob("*.py")) + sorted((CORE / "materials").glob("*.py")):
            with self.subTest(module=path.name):
                body = path.read_text(encoding="utf-8")
                tree = ast.parse(body)
                names = {
                    alias.name
                    for node in ast.walk(tree) if isinstance(node, ast.Import)
                    for alias in node.names
                } | {
                    node.module for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom) and node.module
                }
                self.assertNotIn("story_flow", names, f"{path.name} 反向 import 了流程入口")
                self.assertNotIn("import_sources", names, f"{path.name} 反向 import 了导入入口")

    def test_the_entries_only_parse_and_dispatch(self) -> None:
        """入口只留 `main`：判断留在各自的模块里，入口不再是第二个落点。"""
        for cli in (FLOW_CLI, IMPORT_CLI):
            with self.subTest(cli=cli.name):
                tree = ast.parse(cli.read_text(encoding="utf-8"))
                defined = [n.name for n in tree.body
                           if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
                self.assertEqual(["main"], defined,
                                 f"{cli.name} 里还留着 {defined}——入口只做解析与分派")


class ImportingAModuleChangesNothing(unittest.TestCase):
    """import 一个子模块不该解析参数、不该输出、不该写盘。"""

    MODULES = ("flow.state", "flow.inputs", "flow.meetings", "flow.routing", "flow.decisions",
               "flow.rounds", "flow.submission", "flow.lifecycle",
               "materials.registry", "materials.importer", "materials.meeting")

    def test_import_is_silent_and_writes_nothing(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module), tempfile.TemporaryDirectory() as tmp:
                work = Path(tmp)
                proc = subprocess.run(
                    [sys.executable, "-c",
                     "import sys; sys.path.insert(0, sys.argv[1]);"
                     f"__import__({module!r})", str(CORE)],
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", cwd=str(work), timeout=120)
                self.assertEqual(0, proc.returncode,
                                 f"{module} 单独 import 就失败：{proc.stderr}")
                self.assertEqual("", proc.stdout.strip(), f"{module} 在 import 期就输出了")
                self.assertEqual("", proc.stderr.strip(), f"{module} 在 import 期就报到 stderr")
                self.assertEqual([], sorted(p.name for p in work.iterdir()),
                                 f"{module} 在 import 期写了盘")


class OneRuleFindsEveryResource(unittest.TestCase):
    """合同、模板与公共 CLI 由脚本自己的位置定，与谁在哪儿调它无关。

    所以这一组**故意**在别的工作目录下跑，工程根还带空格——两者都是真实现场：
    hook 从框架目录起进程，Windows 上的工程路径常带空格。
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # 目录名带空格：定位只要拼字符串没加引号，这里就会断成两段
        self.root = Path(self._tmp.name) / "我 的 工程"
        self.feature_root = self.root / "doc" / "features" / "AR90001"
        for part in ("RR", "SR", "AR"):
            (self.feature_root / part).mkdir(parents=True)
        (self.feature_root / "RR" / "prd.md").write_text("# 产品需求\n\n背景。\n",
                                                         encoding="utf-8")
        (self.feature_root / "SR" / "design.md").write_text("# 系统设计\n\n分工。\n",
                                                           encoding="utf-8")
        (self.feature_root / "AR" / "design.md").write_text(
            "# AR90001 上游预填\n\n## 上游先写下的几条\n\n- 判定在服务端。\n",
            encoding="utf-8")
        # cwd 故意不是工程根、也不是仓根
        self.cwd = Path(self._tmp.name)

    def flow(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(FLOW_CLI), *args, "--feature", "AR90001",
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(self.cwd))

    def payload(self, proc: subprocess.CompletedProcess) -> dict:
        self.assertIn("{", proc.stdout, proc.stdout + proc.stderr)
        return json.loads(proc.stdout[proc.stdout.index("{"):])

    def test_the_workspace_template_is_found_from_another_cwd(self) -> None:
        """`init` 落下的收件箱说明书来自 Skill 自带的模板：定位错一层就没有这个文件。"""
        out = self.payload(self.flow("init"))
        self.assertTrue(out["success"], out)
        readme = self.feature_root / "inbox" / "README.md"
        self.assertTrue(readme.is_file(), "inbox/README.md 没落地——模板没找到")
        template = CORE.parents[1] / "templates" / "inbox-readme.md"
        self.assertEqual(template.read_text(encoding="utf-8"),
                         readme.read_text(encoding="utf-8"),
                         "落下的不是 Skill 自带的那份模板")

    def test_the_gate_values_come_from_the_chapter_contract(self) -> None:
        """第一级的值域是章节合同给的：读不到合同，这条命令连值域都报不出来。"""
        contract = json.loads(
            (CORE.parents[1] / "contracts" / "story-chapters.json")
            .read_text(encoding="utf-8").lstrip(chr(0xFEFF)))
        keys = [o["key"] for o in contract["gates"]["material_scope"]["options"]]
        self.payload(self.flow("init"))
        self.payload(self.flow("round"))
        # 侧车自己说这一项合法：值域的真源是合同，侧车说了不算
        made_up = "压根不存在的键"
        src = self.feature_root / "AR" / "story-src"
        src.mkdir(parents=True, exist_ok=True)
        (src / ".gate-options.json").write_text(json.dumps(
            {"gate": "material_scope",
             "options": [{"key": made_up, "label": "侧车现编的一项"}]},
            ensure_ascii=False), encoding="utf-8")
        out = self.payload(self.flow("decide", "--gate", "material_scope",
                                     "--chosen", made_up,
                                     "--basis", "用户原话"))
        self.assertFalse(out["success"], out)
        for key in keys:
            self.assertIn(key, out["error"], f"报错没列出合同里的 {key}")

    def test_the_default_project_root_is_defined_once(self) -> None:
        """默认工程根只有一处定义，两个入口都引它。

        各自数一遍目录层数的话，把文件往下挪一层只会有一个入口被改对，而另一个入口
        在同一台机器上指向另一个工程——它照样跑得完，只是读写的不是这个仓。
        """
        defs = [f for f in sorted(CORE.rglob("*.py"))
                if "DEFAULT_PROJECT_ROOT = " in f.read_text(encoding="utf-8")]
        self.assertEqual([CORE / "materials" / "importer.py"], defs,
                         "默认工程根不止一处定义")
        for cli in (FLOW_CLI, IMPORT_CLI):
            body = cli.read_text(encoding="utf-8")
            self.assertIn("importer.DEFAULT_PROJECT_ROOT", body,
                          f"{cli.name} 没用那一处定义")
            self.assertNotIn("parents[", body,
                             f"{cli.name} 又自己数了一遍目录层数")

    def test_the_importer_runs_from_another_cwd(self) -> None:
        """导入命令也要在别处的 cwd、带空格的工程根上跑得完（收件箱空 = 什么都不导）。"""
        out = json.loads(subprocess.run(
            [sys.executable, str(IMPORT_CLI), "--feature", "AR90001",
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(self.cwd)).stdout)
        # 收件箱是空的：这条命令要能走到「没有料」而不是「找不到工程」
        self.assertEqual("import", out["mode"], out)
        self.assertTrue(out.get("success"), out)
        self.assertEqual([], out["converted"], out)


if __name__ == "__main__":
    unittest.main()
