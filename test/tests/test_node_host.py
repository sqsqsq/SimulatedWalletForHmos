"""测试进程内的 node 宿主（`node_host.mjs` + `node_host_bridge.py`）与命令行同语义：同一个脚本经宿主与经真实进程，
退出码、stdout、stderr 一致；argv、cwd、env 每条请求各自设好、互不留存；每条请求的扩展模块状态从零开始；
只转约定的那几种形态，其余照原样起进程。"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import node_host_bridge as bridge  # noqa: E402


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
