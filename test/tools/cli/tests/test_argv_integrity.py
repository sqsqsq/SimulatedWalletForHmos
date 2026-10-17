"""argv 完整性：多行 prompt 必须逐字送达 provider。

Windows 上 npm 装的是 `.CMD` 批处理包装器，而 `.CMD` 由 cmd.exe 解释。cmd.exe 按行解析命令，
参数里只要含换行，命令行就在那里终止——`%*` 展开后**后续内容连同再往后的参数一起丢失**。
表现是 prompt 被悄悄截断在第一行，且排在它之后的开关（`--format json` 之类）一并失效，
provider 于是退回默认输出格式，**整个过程没有任何报错**。

这组用例把这个形态锁死：既验证包装器被解析到底层程序，也验证含换行的参数原样到达子进程。

夹具里的 Windows 路径一律用原始字符串——`"%dp0%\\real.exe"` 这种写法里的 `\r` 会被
Python 解释成回车，夹具本身就先坏了。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from tools.cli.registry import resolve_batch_wrapper  # noqa: E402

MULTILINE = "第一行：这是指令\n\n  第二行是路径 E:\\a\\b.md\n\n第三行还有内容"
TEST_ROOT = Path(__file__).resolve().parents[4] / "output" / "cli-tests"


class BatchWrapperResolutionTest(unittest.TestCase):
    def setUp(self) -> None:
        if sys.platform != "win32":
            self.skipTest("批处理包装器是 Windows 特有形态")
        # 每个用例独立目录：resolve_batch_wrapper 带 lru_cache，复用路径会命中旧结果
        self.tmp = TEST_ROOT / "wrapper" / uuid.uuid4().hex[:8]
        self.tmp.mkdir(parents=True, exist_ok=True)

    def _write(self, name: str, body: str) -> Path:
        path = self.tmp / name
        path.write_text(body, encoding="utf-8")
        return path

    def test_exe_style_wrapper_resolves_to_real_executable(self) -> None:
        real = self.tmp / "real-target.exe"
        real.write_bytes(b"stub")
        wrapper = self._write(
            "exe-style.cmd", '@ECHO off\r\n"%dp0%\\real-target.exe"   %*\r\n'
        )
        executable, prefix = resolve_batch_wrapper(str(wrapper))
        self.assertEqual(str(real.resolve()), executable)
        self.assertEqual((), prefix)

    def test_node_style_wrapper_prefixes_the_script(self) -> None:
        script = self.tmp / "real-target.js"
        script.write_text("// stub", encoding="utf-8")
        wrapper = self._write(
            "node-style.cmd", '@ECHO off\r\n"%_prog%"  "%dp0%\\real-target.js" %*\r\n'
        )
        executable, prefix = resolve_batch_wrapper(str(wrapper))
        self.assertTrue(
            executable.lower().endswith("node.exe") or executable == "node", executable
        )
        self.assertEqual((str(script.resolve()),), prefix)

    def test_unrecognized_wrapper_keeps_the_original_path(self) -> None:
        """解析不出目标时保留原路径——这条只是加固，不该让本来能跑的调用失败。"""
        wrapper = self._write("weird.cmd", "@ECHO off\r\nsomething-else\r\n")
        self.assertEqual((str(wrapper), ()), resolve_batch_wrapper(str(wrapper)))

    def test_wrapper_pointing_at_missing_target_keeps_original(self) -> None:
        wrapper = self._write(
            "dangling.cmd", '@ECHO off\r\n"%dp0%\\does-not-exist.exe"   %*\r\n'
        )
        self.assertEqual((str(wrapper), ()), resolve_batch_wrapper(str(wrapper)))

    def test_non_batch_executable_is_untouched(self) -> None:
        exe = self.tmp / "plain.exe"
        exe.write_bytes(b"stub")
        self.assertEqual((str(exe), ()), resolve_batch_wrapper(str(exe)))

    def test_electron_wrapper_preserves_script_and_node_flag(self) -> None:
        exe = self.tmp / "host app.exe"
        script = self.tmp / "entry.js"
        exe.write_bytes(b"stub")
        script.write_text("// stub", encoding="utf-8")
        wrapper = self._write("desktop.cmd", 'set "ELECTRON_RUN_AS_NODE=1"\n"%~dp0host app.exe" --expose-internals "%~dp0entry.js" %*\n')
        self.assertEqual((str(exe.resolve()), ("--expose-internals", str(script.resolve()))), resolve_batch_wrapper(str(wrapper)))

    def test_electron_wrapper_with_missing_script_is_not_unwrapped(self) -> None:
        exe = self.tmp / "host.exe"
        exe.write_bytes(b"stub")
        wrapper = self._write("missing-script.cmd", '"%~dp0host.exe" --expose-internals "%~dp0missing.js" %*\n')
        self.assertEqual((str(wrapper), ()), resolve_batch_wrapper(str(wrapper)))

    def test_electron_wrapper_accepts_virtual_asar_entry(self) -> None:
        exe = self.tmp / "host.exe"
        archive = self.tmp / "bundle.asar"
        exe.write_bytes(b"stub")
        archive.write_bytes(b"asar stub")
        wrapper = self._write("archive.cmd", '"%~dp0host.exe" --expose-internals "%~dp0bundle.asar/plugin/entry.js" %*\n')
        expected_script = str((archive / "plugin/entry.js").resolve())
        self.assertEqual((str(exe.resolve()), ("--expose-internals", expected_script)), resolve_batch_wrapper(str(wrapper)))


class MultilineArgvTest(unittest.TestCase):
    """直接执行程序时，含换行的参数与其后的参数必须逐字送达。"""

    def setUp(self) -> None:
        self.tmp = TEST_ROOT / "argv"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.echo = self.tmp / "echo_argv.py"
        self.echo.write_text(
            "import json, sys\n"
            "sys.stdout.reconfigure(encoding='utf-8')\n"
            "print(json.dumps(sys.argv[1:], ensure_ascii=False))\n",
            encoding="utf-8",
        )

    def test_multiline_argument_and_trailing_flags_survive(self) -> None:
        argv = [sys.executable, str(self.echo), MULTILINE, "--format", "json", "--verbose"]
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        received = json.loads(proc.stdout)
        self.assertEqual([MULTILINE, "--format", "json", "--verbose"], received)
        self.assertIn("\n", received[0], "换行必须原样保留")
        self.assertIn("第三行还有内容", received[0], "prompt 不得被截断在第一行")


if __name__ == "__main__":
    unittest.main()
