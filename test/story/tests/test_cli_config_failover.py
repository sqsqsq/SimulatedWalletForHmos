"""CLI configuration priority and per-Case retry policy."""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "test" / "story" / "scripts"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPTS))

import run_multi_case as multi  # noqa: E402


def suite_with(record: dict) -> dict:
    configurations = [dict(item) for item in multi.CLI_CONFIGURATIONS]
    return {
        "bundle_root": tempfile.mkdtemp(),
        "isolated_workspaces": True,
        "case_states": {record["case"]: record},
        "events": [],
        "cli_configuration_group": {
            "configurations": configurations,
            "retry_policy": dict(multi.CLI_RETRY_POLICY),
            "health": {
                item["id"]: {"status": "available"}
                for item in configurations
            },
        },
    }


def failed_record(kind: str) -> dict:
    return {
        "case": "provider-fixture", "feature": "AR-FIXTURE",
        "status": "cli_failed", "failure_kind": kind,
        "cli_config_index": 0,
        "cli_config_id": multi.CLI_CONFIGURATIONS[0]["id"],
        "run_id": "run-1", "current_attempt": 1,
        "attempts": [{"attempt": 1, "run_id": "run-1",
                      "cli_config_id": multi.CLI_CONFIGURATIONS[0]["id"]}],
        "content_rejection_counts": {},
    }


class ConfigContractTests(unittest.TestCase):
    def test_declared_priority_and_models(self) -> None:
        self.assertEqual(
            [
                ("opencode", "bailian/deepseek-v4-flash-0731"),
                ("opencode", "volcengine/GLM5.3-Flash"),
                ("codex", "gpt-5.6-luna"),
            ],
            [(item["name"], item["model"]) for item in multi.CLI_CONFIGURATIONS],
        )

    def test_401_trips_configuration_for_the_suite_and_selects_next(self) -> None:
        record = failed_record("auth_required")
        suite = suite_with(record)
        self.addCleanup(shutil.rmtree, suite["bundle_root"], True)

        def schedule(_suite, current, *, config_index, reason, failure_kind):
            current.update(status="pending", cli_config_index=config_index,
                           cli_config_id=multi.CLI_CONFIGURATIONS[config_index]["id"])

        with mock.patch.object(multi, "refresh_record", side_effect=lambda value: value), \
                mock.patch.object(multi, "request_case_retry", side_effect=schedule) as retry:
            multi.process_retryable_failures(suite)

        first = multi.CLI_CONFIGURATIONS[0]["id"]
        self.assertEqual("unavailable_auth",
                         suite["cli_configuration_group"]["health"][first]["status"])
        self.assertEqual(multi.CLI_CONFIGURATIONS[1]["id"], record["cli_config_id"])
        self.assertEqual("switch_after_auth_failure", retry.call_args.kwargs["reason"])
        self.assertEqual((1, multi.CLI_CONFIGURATIONS[1]["id"]),
                         multi.select_healthy_cli(suite, 0))

    def test_content_rejection_retries_once_then_finishes_only_the_case(self) -> None:
        record = failed_record("content_policy_rejected")
        suite = suite_with(record)
        self.addCleanup(shutil.rmtree, suite["bundle_root"], True)

        with mock.patch.object(multi, "refresh_record", side_effect=lambda value: value), \
                mock.patch.object(multi, "request_case_retry") as retry, \
                mock.patch.object(multi, "request_host_reply") as host_reply:
            multi.process_retryable_failures(suite)
        retry.assert_called_once()
        host_reply.assert_not_called()
        self.assertEqual(0, retry.call_args.kwargs["config_index"])
        self.assertEqual(1, record["content_rejection_counts"][record["cli_config_id"]])

        # Simulate the clean retry returning the same provider rejection.
        record["status"] = "cli_failed"
        with mock.patch.object(multi, "refresh_record", side_effect=lambda value: value):
            multi.process_retryable_failures(suite)
        self.assertEqual("content_policy_rejected", record["status"])
        self.assertTrue(record["retry_finalized"])

    def test_all_401_configurations_exhaust_only_the_case(self) -> None:
        record = failed_record("auth_required")
        record["cli_config_index"] = len(multi.CLI_CONFIGURATIONS) - 1
        record["cli_config_id"] = multi.CLI_CONFIGURATIONS[-1]["id"]
        suite = suite_with(record)
        self.addCleanup(shutil.rmtree, suite["bundle_root"], True)
        for item in multi.CLI_CONFIGURATIONS[:-1]:
            suite["cli_configuration_group"]["health"][item["id"]]["status"] = \
                "unavailable_auth"

        with mock.patch.object(multi, "refresh_record", side_effect=lambda value: value):
            multi.process_retryable_failures(suite)
        self.assertEqual("cli_config_exhausted", record["status"])


class CleanRetryTests(unittest.TestCase):
    def test_retry_rebuilds_workspace_and_requirement_system(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cases = root / "cases"
            case_root = cases / "clean-fixture"
            system_source = case_root / "system" / "AR-CLEAN"
            system_source.mkdir(parents=True)
            (system_source / "detail.json").write_text("fresh", encoding="utf-8")

            template = root / "template"
            (template / "framework").mkdir(parents=True)
            (template / "baseline.txt").write_text("baseline", encoding="utf-8")
            workspace_root = root / "workspaces"
            workspace = workspace_root / "clean-fixture"
            workspace.mkdir(parents=True)
            (workspace / "stale.txt").write_text("stale", encoding="utf-8")
            bundle = root / "bundle"
            bundle.mkdir()
            multi.write_json(bundle / "workspace-boundary.json", {})

            record = {
                "case": "clean-fixture", "feature": "AR-CLEAN",
                "workspace": str(workspace), "supplements": [],
                "failure_kind": "content_policy_rejected",
                "interaction_index": 3, "last_reply_text": "old reply",
            }
            suite = {
                "isolated_workspaces": True, "bundle_root": str(bundle),
                "workspace_template": str(template),
                "workspace_root": str(workspace_root),
                "case_states": {"clean-fixture": record},
            }
            system = multi.requirement_system_path(workspace_root, "clean-fixture")
            system.mkdir(parents=True, exist_ok=True)
            (system / "stale.txt").write_text("stale", encoding="utf-8")
            self.addCleanup(shutil.rmtree, system.parent, True)

            with mock.patch.object(multi, "CASES_ROOT", cases):
                multi.prepare_case_retry(suite, record)

            self.assertFalse((workspace / "stale.txt").exists())
            self.assertTrue((workspace / "baseline.txt").is_file())
            self.assertFalse((system / "stale.txt").exists())
            self.assertEqual("fresh", (system / "AR-CLEAN" / "detail.json").read_text("utf-8"))
            self.assertEqual("pending", record["status"])
            self.assertIsNone(record["failure_kind"])
            self.assertEqual(0, record["interaction_index"])
            self.assertIsNone(record["last_reply_text"])


if __name__ == "__main__":
    unittest.main()
