"""测试进程内的 node 宿主（`node_host.mjs` + `node_host_bridge.py`）与命令行同语义：同一个脚本经宿主与经真实进程，
退出码、stdout、stderr 一致；argv、cwd、env 每条请求各自设好、互不留存；每条请求的扩展模块状态从零开始；
只转约定的那几种形态，其余照原样起进程。"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import node_host_bridge as bridge  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
FLOW = REPO / "extensions" / "skills" / "story" / "scripts" / "core" / "story_flow.py"


def write(root: Path, name: str, body: str) -> Path:
    path = root / name
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return path


class TheHostRunsAScriptLikeTheCommandLine(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        if not bridge.ENABLED:
            self.skipTest("宿主关着（STORY_TEST_NODE_HOST=0）：这组比的就是宿主与命令行")

    def both(self, args: list[str], **kwargs) -> tuple[subprocess.CompletedProcess, subprocess.CompletedProcess]:
        """同一条命令经宿主与经真实进程各跑一次。"""
        before = bridge.jobs
        host = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", **kwargs)
        self.assertEqual(before + 1, bridge.jobs, "这条命令没交给宿主")
        real = bridge._real_run(args, capture_output=True, text=True, encoding="utf-8", **kwargs)
        return host, real

    def same(self, args: list[str], **kwargs) -> subprocess.CompletedProcess:
        host, real = self.both(args, **kwargs)
        self.assertEqual((real.returncode, real.stdout, real.stderr), (host.returncode, host.stdout, host.stderr))
        return host

    def test_exit_stops_the_command_where_it_is_called(self) -> None:
        """`process.exit(n)` 当场结束：其后的输出不出现，退出码就是 n——失败路径不落到别的分支。"""
        script = write(self.root, "exit.mjs", """
            process.stdout.write('前\\n');
            Promise.resolve().then(() => { process.exit(3); process.stdout.write('后\\n'); });
            """)
        got = self.same(["node", str(script)])
        self.assertEqual((3, "前\n"), (got.returncode, got.stdout))

    def test_exit_code_without_exit_and_a_thrown_error(self) -> None:
        code = write(self.root, "code.mjs", "process.exitCode = 4; console.log('设了退出码');\n")
        self.assertEqual(4, self.same(["node", str(code)]).returncode)
        boom = write(self.root, "boom.mjs", "setTimeout(() => { throw new Error('异步里炸了'); }, 1);\n")
        host, real = self.both(["node", str(boom)])
        self.assertEqual((1, 1), (real.returncode, host.returncode))
        self.assertIn("异步里炸了", host.stderr)
        named = write(self.root, "named.mjs", """
            class KnowledgeError extends Error {}
            throw new KnowledgeError('不合协议', { cause: new Error('底层') });
            """)
        host, real = self.both(["node", str(named)])
        for line in ("KnowledgeError: 不合协议", "[cause]: Error: 底层"):
            self.assertIn(line, real.stderr)
            self.assertIn(line, host.stderr, "未捕获异常的写法与命令行不同")

    def test_argv_cwd_and_env_belong_to_the_request(self) -> None:
        script = write(self.root, "who.mjs", """
            import * as path from 'node:path';
            console.log(JSON.stringify([process.argv.slice(2), path.basename(process.cwd()), process.env.STORY_HOST_PROBE ?? null]));
            """)
        here = self.root / "here"
        here.mkdir()
        env = {**os.environ, "STORY_HOST_PROBE": "甲"}
        self.assertEqual('[["a","b c"],"here","甲"]\n', self.same(["node", str(script), "a", "b c"], cwd=here, env=env).stdout)
        # 下一条请求不带那个变量、不给 cwd：上一条的设置不留下
        self.assertNotIn("甲", self.same(["node", str(script)]).stdout)

    def test_module_state_starts_over_for_every_request(self) -> None:
        """被导入的扩展模块里的模块级缓存每条请求从零开始，与每条命令一个进程时一样。"""
        write(self.root, "state.mjs", "export const seen = []; \n")
        script = write(self.root, "use.mjs", """
            import { seen } from './state.mjs';
            seen.push(1);
            console.log(seen.length);
            """)
        for _ in range(3):
            self.assertEqual("1\n", self.same(["node", str(script)]).stdout)

    def test_an_inline_module_with_its_arguments(self) -> None:
        source = "console.log(JSON.stringify(process.argv.slice(1)));"
        self.assertEqual('["x","y"]\n', self.same(["node", "--input-type=module", "-e", source, "--", "x", "y"]).stdout)
        self.assertEqual('["x"]\n', self.same(["node", "--input-type=module", "-e", source, "x"]).stdout)

    def test_bytes_mode_and_newlines_match_subprocess(self) -> None:
        script = write(self.root, "crlf.mjs", "process.stdout.write('一\\r\\n二\\n');\n")
        host = subprocess.run(["node", str(script)], capture_output=True)
        real = bridge._real_run(["node", str(script)], capture_output=True)
        self.assertEqual(real.stdout, host.stdout, "字节模式不能转换换行")
        self.same(["node", str(script)])          # 文本模式按 subprocess 的通用换行

    def test_a_missing_script_fails_like_the_command_line(self) -> None:
        host, real = self.both(["node", str(self.root / "没有这个.mjs")])
        self.assertEqual(real.returncode, host.returncode)
        self.assertIn("没有这个.mjs", host.stderr)

    def test_commands_from_another_thread_start_real_processes(self) -> None:
        """宿主一次只执行一条请求：用例自己开线程起的命令照常起真实进程。"""
        script = write(self.root, "t.mjs", "console.log('ok');\n")
        before, box = bridge.jobs, {}
        t = threading.Thread(target=lambda: box.setdefault("p", subprocess.run(["node", str(script)], capture_output=True, text=True)))
        t.start()
        t.join()
        self.assertEqual((before, "ok\n"), (bridge.jobs, box["p"].stdout))

    def test_a_restarted_host_does_not_hold_the_directory_the_test_was_in(self) -> None:
        """宿主在请求之间重启时不继承用例那时所在的 cwd——否则 Windows 上那个目录删不掉。"""
        here = self.root / "here"
        here.mkdir()
        script = write(self.root, "y.mjs", "console.log('ok');\n")
        bridge._host.stop()
        os.chdir(here)
        try:
            self.assertEqual("ok\n", self.same(["node", str(script)]).stdout)
        finally:
            os.chdir(REPO)
        shutil.rmtree(here)


class PythonCommandsKeepTheRealProcess(unittest.TestCase):
    """Python 命令一律起真实解释器：外层 timeout 照样截断，输出与同环境的真实解释器逐字节相同，脚本里再起的 node 也不进宿主。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name) / "extensions" / "skills" / "probe"     # 与产品脚本同样的目录形状
        self.dir.mkdir(parents=True)

    def test_a_timeout_still_cuts_the_command(self) -> None:
        script = write(self.dir, "slow.py", "import time\ntime.sleep(5)\n")
        before = bridge.jobs
        with self.assertRaises(subprocess.TimeoutExpired):
            subprocess.run([sys.executable, str(script)], capture_output=True, timeout=0.5)
        self.assertEqual(before, bridge.jobs)

    def test_the_product_help_is_byte_for_byte_the_real_interpreter(self) -> None:
        """产品入口在解析参数时就退出的输出（如 --help）不经任何包装：编码现象按真实解释器原样留给测试看见。"""
        args = [sys.executable, str(FLOW), "--help"]
        before = bridge.jobs
        mine = subprocess.run(args, capture_output=True)
        real = bridge._real_run(args, capture_output=True)
        self.assertEqual(before, bridge.jobs)
        self.assertEqual((real.returncode, real.stdout, real.stderr), (mine.returncode, mine.stdout, mine.stderr))

    def test_a_node_command_inside_a_python_script_stays_a_real_process(self) -> None:
        mjs = write(self.dir, "x.mjs", "console.log('来自 node');\n")
        script = write(self.dir, "calls_node.py", f"""
            import subprocess, sys
            r = subprocess.run(["node", {str(mjs)!r}], capture_output=True, text=True, encoding="utf-8")
            print(r.stdout, end="")
            sys.exit(r.returncode)
            """)
        before = bridge.jobs
        got = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual((0, "来自 node\n"), (got.returncode, got.stdout))
        self.assertEqual(before, bridge.jobs, "Python 脚本里的 node 命令进了测试进程的宿主")


class OnlyTheAgreedFormsGoToTheHost(unittest.TestCase):
    def test_other_forms_start_a_real_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = write(Path(tmp), "x.mjs", "console.log('ok');\n")
            forms = [
                (["node", "-e", "console.log('ok')"], {}),                                   # 不是 ESM 内联
                (["node", str(script)], {"input": ""}),                                        # 要 stdin
                (["node", str(script)], {"env": {**os.environ, "NODE_OPTIONS": ""}}),          # 换了预载
                (["node", "--trace-warnings", str(script)], {}),                               # 带别的 node 参数
                ([sys.executable, "-c", "print('ok')"], {}),                                   # 不是 node
            ]
            for args, kwargs in forms:
                with self.subTest(args=args[:2], kwargs=list(kwargs)):
                    before = bridge.jobs
                    proc = subprocess.run(args, capture_output=True, text=True, **kwargs)
                    self.assertEqual(before, bridge.jobs, "不该交给宿主的形态被转了")
                    self.assertEqual(0, proc.returncode, proc.stderr)


class AProcessBoundaryWitnessUsesTheRealCommandLine(unittest.TestCase):
    """声明 `REAL_CLI = True` 的用例照常起真实进程。"""
    REAL_CLI = True

    def test_nothing_goes_to_the_host(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = write(Path(tmp), "x.mjs", "console.log('ok');\n")
            before = bridge.jobs
            self.assertEqual("ok\n", subprocess.run(["node", str(script)], capture_output=True, text=True).stdout)
            self.assertEqual(before, bridge.jobs)


if __name__ == "__main__":
    unittest.main()
