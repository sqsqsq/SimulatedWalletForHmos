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
        """配置组的顺序就是熔断切换的顺序，所以它是契约、要锁住。

        首位是 deepseek（用户 2026-09-04 裁定）。依据是步骤 7 资格实跑的实测：
        同一份任务上 deepseek 每份 100–265 秒，GLM 275–600 秒且出过一份 600 秒超时零输出。
        换配置的代价是与 GLM 跑的旧成品不再同模型可比——步骤 11 的产物验收对照的是金样
        （固定仲裁锚，与模型无关），结论按 `cli_config_id` 记、不外推。

        换顺序时这条会红，那是它该做的：**顺序变了就得有人确认**。
        """
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


class RealProviderAuthSignatures(unittest.TestCase):
    """凭据失效的真实报文，必须被认成鉴权失败——不是笼统的命令失败。

    实测（2026-08-31 F7 首跑）：两个 Case 在 30 秒内双双 `cli_failed`，
    failure_kind 记的是 `command_failed`，配置组一次都没熔断，三个配置里
    只用了第一个就整轮报废。原因是签名对不上——

        阿里云返回 {"code":"invalid_api_key","message":"Incorrect API key provided."}

    而模式表里写的是带空格的 `invalid api key`：`invalid_api_key` 是下划线、
    `Incorrect API key provided` 里压根没有 "invalid"。两个都不匹配。

    识别不出来的后果不是「少切一次配置」，是**整个配置组形同虚设**：
    provider 换一种说法拼错误消息，熔断就不会发生，而外面看到的仍然是
    「跑挂了」这三个字。所以这里锁的是真实报文，不是构造的理想字符串。
    """

    ALIYUN = ('{"error":{"message":"Incorrect API key provided. For details, see: '
              'https://help.aliyun.com/zh/model-studio/error-code#apikey-error",'
              '"type":"invalid_request_error","param":null,"code":"invalid_api_key"},'
              '"request_id":"ca5b2094-6c83-9477-8b25-261181d2f924"}')

    def test_aliyun_invalid_api_key_is_auth_required(self) -> None:
        from tools.cli.runner import classify_failure
        from tools.cli.models import FailureKind
        self.assertEqual(FailureKind.AUTH_REQUIRED, classify_failure(self.ALIYUN))

    def test_both_spellings_are_covered(self) -> None:
        """下划线与「Incorrect API key」各锁一条——去掉任一条都会漏掉一类 provider。"""
        from tools.cli.runner import classify_failure
        from tools.cli.models import FailureKind
        for text in ('code: invalid_api_key', 'Incorrect API key provided.'):
            with self.subTest(text=text):
                self.assertEqual(FailureKind.AUTH_REQUIRED, classify_failure(text))
