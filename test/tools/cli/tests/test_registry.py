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
        self.assertEqual(["agent", "claude", "codex", "dsh", "opencode"], registry.cli_names())
        for cli in registry.cli_names():
            request = CliRunRequest(
                cli=cli,
                model="test-model",
                prompt="test",
                cwd=Path("."),
            )
            start = registry.build(request, check_executable=False)
            self.assertNotEqual("plan", start.profile)
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
        value["clis"]["opencode"]["profiles"]["plan"]["args"].append("{business_field}")
        temp = Path(__file__).resolve().parents[4] / "output" / "cli-tests" / uuid.uuid4().hex
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
