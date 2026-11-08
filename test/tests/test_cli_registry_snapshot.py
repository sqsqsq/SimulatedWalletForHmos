"""suite 的调用配置快照：dsh 启动与续跑都装载工程里的审查员配置层，别的宿主照用中央注册表。"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "test" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO_ROOT))

import cli_config_group  # noqa: E402
from tools.cli import CliClient, CliRunRequest  # noqa: E402

CENTRAL = json.loads((REPO_ROOT / "tools" / "cli" / "config" / "clis.json").read_text(encoding="utf-8"))
DSH = {"id": "dsh-flash", "name": "dsh", "model": "m", "profile": "build"}
OPENCODE = {"id": "oc", "name": "opencode", "model": "m", "profile": "build"}
LAYER = ".dsh/framework-verifier.patch.yml"


def load_runner():
    spec = importlib.util.spec_from_file_location("run_multi_case_for_registry", SCRIPTS / "run_multi_case.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TheSnapshotLoadsTheVerifierLayer(unittest.TestCase):
    def test_only_dsh_gets_the_layer_and_every_argv_keeps_its_order(self) -> None:
        self.assertIsNone(cli_config_group.registry_snapshot([OPENCODE], CENTRAL))
        snapshot = cli_config_group.registry_snapshot([OPENCODE, DSH], CENTRAL)
        self.assertEqual(["dsh"], list(snapshot["clis"]))
        self.assertEqual(CENTRAL["defaults"], snapshot["defaults"])
        for name, profile in CENTRAL["clis"]["dsh"]["profiles"].items():
            for key in ("args", "resume_args"):
                with self.subTest(profile=name, key=key):
                    before = profile[key]
                    after = snapshot["clis"]["dsh"]["profiles"][name][key]
                    at = before.index("--profile") + 2
                    self.assertEqual(before[:at] + ["--patch", "{cwd}/" + LAYER] + before[at:], after)
        self.assertNotIn("--patch", json.dumps(CENTRAL), "中央注册表被改动了")

    def test_start_and_resume_resolve_the_layer_in_each_case_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cli-registry.json"
            path.write_text(json.dumps(cli_config_group.registry_snapshot([DSH], CENTRAL)), encoding="utf-8")
            client = CliClient(runtime_root=Path(tmp) / "rt", registry_path=path)
            for case in ("auto-topup", "car key"):
                workspace = Path(tmp) / case
                workspace.mkdir()
                for session in (None, "session-1"):
                    with self.subTest(case=case, session=session):
                        argv = client.describe(CliRunRequest(
                            cli="dsh", model="m", prompt="p", cwd=workspace, session_id=session))["argv"]
                        at = argv.index("--patch")
                        self.assertEqual(str(workspace.resolve()) + "/" + LAYER, argv[at + 1])
                        self.assertEqual(1, argv.count("--patch"))
                        self.assertEqual(session is not None, "--session-id" in argv)

    def test_the_case_runner_uses_the_snapshot_only_for_hosts_it_lists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cli-registry.json"
            path.write_text(json.dumps(cli_config_group.registry_snapshot([DSH], CENTRAL)), encoding="utf-8")
            environ = {cli_config_group.CLI_REGISTRY_ENV: str(path)}
            self.assertEqual(path, cli_config_group.registry_for("dsh", environ))
            self.assertIsNone(cli_config_group.registry_for("opencode", environ))
            self.assertIsNone(cli_config_group.registry_for("dsh", {}))


class TheSuiteWritesOneSnapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = load_runner()

    def setUp(self) -> None:
        self._saved = self.runner.CLI_CONFIGURATIONS
        self.addCleanup(setattr, self.runner, "CLI_CONFIGURATIONS", self._saved)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.suite_dir = Path(tmp.name) / "suite"
        self.workspace = Path(tmp.name) / "template"
        self.suite_dir.mkdir()
        self.workspace.mkdir()

    def test_no_dsh_means_no_snapshot_and_no_variable(self) -> None:
        self.runner.CLI_CONFIGURATIONS = [OPENCODE]
        self.assertIsNone(self.runner.write_cli_registry(self.suite_dir, self.workspace))
        environment = self.runner.suite_environment({"cli_registry": None})
        self.assertNotIn(cli_config_group.CLI_REGISTRY_ENV, environment)

    def test_dsh_without_the_materialised_layer_stops_before_any_case_starts(self) -> None:
        self.runner.CLI_CONFIGURATIONS = [DSH]
        with self.assertRaises(SystemExit) as raised:
            self.runner.write_cli_registry(self.suite_dir, self.workspace)
        self.assertIn(LAYER, str(raised.exception))
        self.assertFalse((self.suite_dir / "cli-registry.json").exists())

    def test_dsh_with_the_layer_writes_the_snapshot_every_case_receives(self) -> None:
        self.runner.CLI_CONFIGURATIONS = [OPENCODE, DSH]
        (self.workspace / LAYER).parent.mkdir()
        (self.workspace / LAYER).write_text("- insert: []\n", encoding="utf-8")
        path = self.runner.write_cli_registry(self.suite_dir, self.workspace)
        self.assertEqual(self.suite_dir / "cli-registry.json", path)
        self.assertEqual(cli_config_group.registry_snapshot([DSH], CENTRAL), json.loads(path.read_text(encoding="utf-8")))
        environment = self.runner.suite_environment({"cli_registry": str(path)})
        self.assertEqual(str(path), environment[cli_config_group.CLI_REGISTRY_ENV])



class TheCliVersionIsReadFromTheBinary(unittest.TestCase):
    """起跑前记下 CLI 二进制版本：照注册表找可执行文件、跑它自己的 --version；取不到写明原因，不编一个版本。"""

    def snapshot(self, clis: dict) -> dict:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "clis.json"
        path.write_text(json.dumps({"schema_version": 1, "defaults": {}, "clis": clis}), encoding="utf-8")
        return {cli_config_group.CLI_REGISTRY_ENV: str(path)}

    def test_the_version_line_of_the_registered_binary(self) -> None:
        env = self.snapshot({"fake": {"executable": sys.executable}})
        got = cli_config_group.cli_version("fake", env)
        self.assertEqual((None, f"{sys.executable} --version"), (got["why"], got["source"]))
        self.assertTrue(got["value"].startswith("Python 3."), got)

    def test_a_missing_binary_or_entry_says_why(self) -> None:
        env = self.snapshot({"fake": {"executable": "story-no-such-cli-binary"}})
        got = cli_config_group.cli_version("fake", env)
        self.assertIsNone(got["value"])
        self.assertIn("找不到 story-no-such-cli-binary", got["why"])
        other = cli_config_group.cli_version("story-unregistered", self.snapshot({}))
        self.assertIsNone(other["value"])
        self.assertIn("取不到 story-unregistered 的可执行文件", other["why"])


if __name__ == "__main__":
    unittest.main()
