from __future__ import annotations

import json
import shutil
import unittest
import uuid
from pathlib import Path

from tools.cli.models import CliRunRequest
from tools.cli.registry import (
    DEFAULT_CONFIG_PATH,
    CliConfigurationError,
    CliRegistry,
)


class RegistryTests(unittest.TestCase):
    def test_default_registry_contains_supported_clis(self) -> None:
        registry = CliRegistry(DEFAULT_CONFIG_PATH)
        self.assertEqual(["agent", "claude", "codex", "opencode"], registry.cli_names())
        for cli in registry.cli_names():
            request = CliRunRequest(
                cli=cli,
                model="test-model",
                prompt="test",
                cwd=Path("."),
            )
            start = registry.build(request, check_executable=False)
            self.assertNotEqual("readonly", start.profile)
            resumed = registry.build(
                CliRunRequest(
                    **{
                        **request.to_dict(),
                        "cwd": Path("."),
                        "session_id": "session-1",
                    }
                ),
                check_executable=False,
            )
            self.assertIn("session-1", resumed.argv)

    def test_prompt_is_the_last_argument(self) -> None:
        """位置参数必须排在所有选项之后，否则多行 prompt 会把后续选项吃掉。

        实证（AR90004 三跑）：`opencode run [message..]` 的 positional 是 **array**。
        配置曾写成 `run {prompt} --dir … --format json`——单行 prompt 相安无事，
        换成多行长 prompt（真实用例就是多行）后，yargs 把后面的选项一并吸进 message，
        **`--format json` 从未生效**：输出退回 TUI 文本，于是
        ①`model` 流全空（TEST.md 要求「必须读 model 流」，通道等于没有）；
        ②`session_id` 拿不到 → 无法 `resume` → 驱动器无法回答关卡菜单 →
        单轮会话停在 S3、产物全无。三轮实测全部卡死在这里，一度被误判成 skill 缺陷。

        prompt 放末尾即按构造消除：选项在它之前已经解析完。

        **只约束 opencode**：这条是从它的 yargs array positional 实证来的，
        是否适用于别家取决于各自的参数解析器（claude 的 `-p`、codex 的 exec 都另有形态）。
        把一次实证当普适规则去套，是另一种打补丁——别家出问题时按各自的证据再加。
        """
        raw = json.loads(Path(DEFAULT_CONFIG_PATH).read_text(encoding="utf-8"))
        for pname, profile in raw["clis"]["opencode"]["profiles"].items():
            for key in ("args", "resume_args"):
                argv = profile.get(key)
                if not argv or "{prompt}" not in argv:
                    continue
                self.assertEqual(
                    argv[-1], "{prompt}",
                    f"opencode.{pname}.{key}: {{prompt}} 是 array positional，必须排在末尾，"
                    f"否则多行 prompt 会吞掉它后面的选项（实为 {argv}）")

    def test_build_start_and_resume(self) -> None:
        registry = CliRegistry(DEFAULT_CONFIG_PATH)
        request = CliRunRequest(
            cli="opencode",
            model="test-model",
            prompt="hello {literal}",
            cwd=Path("."),
            profile="build",
        )
        start = registry.build(request, check_executable=False)
        self.assertEqual("opencode", Path(start.executable).stem.lower())
        self.assertIn("hello {literal}", start.argv)
        self.assertNotIn("-s", start.argv)

        resume = registry.build(
            CliRunRequest(
                **{**request.to_dict(), "cwd": Path("."), "session_id": "ses-1"}
            ),
            check_executable=False,
        )
        self.assertIn("-s", resume.argv)
        self.assertIn("ses-1", resume.argv)

    def test_unknown_placeholder_is_rejected(self) -> None:
        value = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
        value["clis"]["opencode"]["profiles"]["readonly"]["args"].append("{business_field}")
        temp = Path(__file__).resolve().parents[3] / "output" / "cli-tests" / uuid.uuid4().hex
        temp.mkdir(parents=True)
        try:
            path = temp / "invalid.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(CliConfigurationError):
                CliRegistry(path)
        finally:
            shutil.rmtree(temp, ignore_errors=True)
            try:
                temp.parent.rmdir()
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
