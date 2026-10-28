"""测试配置的启动选项：dsh 默认配置在每个 Case 工作区装载该工作区里的审查员配置层，展开由中央 runtime 负责。"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "test" / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import cli_config_group  # noqa: E402
from tools.cli import CliClient, CliRunRequest  # noqa: E402

LAYER = ".dsh/framework-verifier.patch.yml"


def default_configuration() -> dict:
    config = yaml.safe_load((REPO_ROOT / "test" / "config" / "test.yaml").read_text(encoding="utf-8"))
    configurations, _ = cli_config_group.load_cli_group(config)
    return configurations[0]


class TheDefaultDshConfigurationLoadsTheWorkspaceLayer(unittest.TestCase):
    def test_the_default_configuration_names_the_layer(self) -> None:
        dsh = default_configuration()
        self.assertEqual("dsh", dsh["name"])
        self.assertEqual({"patch": [LAYER]}, dsh["options"])

    def test_start_and_resume_carry_the_layer_of_each_case_workspace(self) -> None:
        dsh = default_configuration()
        with tempfile.TemporaryDirectory() as tmp:
            client = CliClient(runtime_root=Path(tmp) / "rt")
            for case in ("auto-topup", "car key"):
                workspace = Path(tmp) / case
                (workspace / LAYER).parent.mkdir(parents=True)
                (workspace / LAYER).write_text("- insert: []\n", encoding="utf-8")
                options = cli_config_group.resolve_cli_options(dsh, workspace)
                for session in (None, "session-1"):
                    with self.subTest(case=case, session=session):
                        argv = client.describe(CliRunRequest(
                            cli=dsh["name"], model=dsh["model"], prompt="p", cwd=workspace,
                            profile=dsh["profile"], session_id=session, options=options))["argv"]
                        self.assertEqual(1, argv.count("--patch"))
                        at = argv.index("--patch")
                        self.assertEqual(str((workspace / LAYER).resolve()), argv[at + 1])
                        self.assertEqual(["--profile", "headless"], argv[at - 2:at])
                        self.assertEqual(session is not None, "--session-id" in argv)

    def test_a_missing_layer_stops_before_the_cli_starts(self) -> None:
        dsh = default_configuration()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as raised:
                cli_config_group.resolve_cli_options(dsh, Path(tmp))
            self.assertIn(dsh["id"], str(raised.exception))
            self.assertIn("framework-verifier.patch.yml", str(raised.exception))

    def test_configurations_without_options_pass_nothing(self) -> None:
        self.assertEqual({}, cli_config_group.resolve_cli_options({"id": "oc", "name": "opencode"}, Path.cwd()))


class MalformedOptionsAreRejected(unittest.TestCase):
    def load(self, options) -> None:
        cli_config_group.load_cli_group({"cli": {"configurations": [
            {"id": "x", "name": "dsh", "model": "m", "profile": "build", "options": options}]}})

    def test_shapes(self) -> None:
        for options in ({}, [LAYER], {"patch": LAYER}, {"patch": []}, {"patch": [""]}):
            with self.subTest(options=options), self.assertRaises(SystemExit):
                self.load(options)


if __name__ == "__main__":
    unittest.main()
