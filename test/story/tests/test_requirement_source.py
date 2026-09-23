"""需求来源：本项目只有 AR 开头的需求挂在需求系统上，其余编号都是本地需求。

锁住：
  ① 对接层四条命令对本地需求在访问系统之前失败，名字不限 local——问题单、自定义名、
     中间含 AR 的编号都算本地；AR 开头而系统上查无此单仍是故障，不降级成本地；
  ② 对接层只有 init / fetch / archive / restore，流程帮助归 `/story help`；
  ③ core 两侧（Python 的 `system_requirement`、mjs 的 `isSystemRequirement`）对同一组编号判定一致，
     建骨架的来源标记按编号，需求目录里留着 `AR/detail.json` 也照编号判；
  ④ core 与对接层互不认识对方：core 的代码里没有对接层的路径或程序名，对接层的代码里没有 core 的命令。
     注释与文档字符串里描述另一层的职责不算。
"""
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
STORY = REPO / "doc" / "extensions" / "skills" / "story"
STORY_JS = STORY / "scripts" / "adapters" / "story.js"
CORE = STORY / "scripts" / "core"
CONTEXT = CORE / "story" / "context.mjs"

LOCAL = ["ISSUE-206", "local-demo", "myreq", "XAR1", "ar90001"]
SYSTEM = ["AR90006", "AR-not-exist"]


def run_story(*args: str, system: Path) -> tuple[int, dict]:
    proc = subprocess.run(["node", str(STORY_JS), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=60,
                          env={**os.environ, "STORY_REQUIREMENT_SYSTEM_DIR": str(system)})
    rows = [l for l in proc.stdout.splitlines() if l.strip().startswith("{")]
    assert rows, proc.stdout + proc.stderr
    return proc.returncode, json.loads(rows[-1])


class TheAdapterServesOnlySystemRequirements(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.system = Path(self._tmp.name) / "no-such-system"

    def test_every_command_refuses_a_local_requirement_before_touching_the_system(self) -> None:
        for cmd in ("init", "fetch", "archive", "restore"):
            for no in LOCAL:
                with self.subTest(cmd=cmd, no=no):
                    code, out = run_story(cmd, no, "token", "--out", "x", "--project-root", self._tmp.name,
                                          system=self.system)
                    self.assertNotEqual(0, code)
                    self.assertIn("本地需求", out["error"])
                    self.assertNotIn("需求系统不可达", out["error"])

    def test_a_system_requirement_that_cannot_be_read_stays_a_failure(self) -> None:
        code, out = run_story("init", "AR-not-exist", "token", "--project-root", self._tmp.name,
                              system=self.system)
        self.assertNotEqual(0, code)
        self.assertIn("需求系统不可达", out["error"])

    def test_the_adapter_has_no_help_command(self) -> None:
        code, out = run_story("help", system=self.system)
        self.assertNotEqual(0, code)
        self.assertIn("<init|archive|restore|fetch>", out["error"])
        self.assertNotIn("help", out["error"])


class BothSidesOfCoreJudgeTheSame(unittest.TestCase):
    def mjs(self, ids: list[str]) -> list[bool]:
        script = (f"const m = await import({json.dumps(CONTEXT.as_uri())});"
                  f"process.stdout.write(JSON.stringify({json.dumps(ids)}.map(m.isSystemRequirement)));")
        proc = subprocess.run(["node", "--input-type=module", "-e", script],
                              capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def test_python_and_mjs_agree(self) -> None:
        sys.path.insert(0, str(CORE))
        try:
            from flow.state import system_requirement
        finally:
            sys.path.remove(str(CORE))
        ids = LOCAL + SYSTEM
        want = [False] * len(LOCAL) + [True] * len(SYSTEM)
        self.assertEqual(want, [system_requirement(i) for i in ids])
        self.assertEqual(want, self.mjs(ids))

    def test_a_leftover_detail_file_does_not_make_a_local_requirement_remote(self) -> None:
        sys.path.insert(0, str(CORE))
        try:
            from flow import inputs
        finally:
            sys.path.remove(str(CORE))
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "ISSUE-206"
            (root / "AR").mkdir(parents=True)
            (root / "AR" / "detail.json").write_text('{"reqNo": "ISSUE-206"}', encoding="utf-8")
            self.assertTrue(inputs.cmd_init(root, "ISSUE-206")["local"])
            self.assertFalse(inputs.cmd_init(Path(d) / "AR90006", "AR90006")["local"])



def code_strings(path: Path) -> str:
    """一个文件里真正参与执行的文字：Python 取字符串常量（不含文档字符串），JS 去掉注释。"""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        tree = ast.parse(text)
        docs = {id(n.body[0].value) for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        return "\n".join(n.value for n in ast.walk(tree)
                         if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs)
    return re.sub(r"//.*", "", re.sub(r"/\*.*?\*/", "", text, flags=re.S))


class CoreAndAdapterDoNotKnowEachOther(unittest.TestCase):
    def test_core_names_no_adapter(self) -> None:
        hits = [f"{f.relative_to(CORE).as_posix()}: {word}"
                for f in sorted(CORE.rglob("*")) if f.suffix in {".py", ".mjs"} and "__pycache__" not in f.parts
                for word in ("adapters", "story.js", "token.js") if word in code_strings(f)]
        self.assertEqual([], hits)

    def test_the_adapter_names_no_core_command(self) -> None:
        for f in sorted((STORY / "scripts" / "adapters").glob("*.js")):
            code = code_strings(f)
            for word in ("story_flow", "story-build", "/core/"):
                with self.subTest(file=f.name, word=word):
                    self.assertNotIn(word, code)


if __name__ == "__main__":
    unittest.main()
