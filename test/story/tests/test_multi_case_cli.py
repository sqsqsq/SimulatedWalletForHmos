"""Tests for the multi-case coordinator's scheduling contract.

These tests do not start a provider CLI.  Formal behavior still belongs to
the existing per-case runner and its immutable run evidence.
"""
from __future__ import annotations

import unittest
import sys
import tempfile
import shutil
import time
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_multi_case  # noqa: E402


class OperatorProtocolTest(unittest.TestCase):
    def test_test_guide_exposes_new_session_multiselect_and_host_boundary(self) -> None:
        guide = (SCRIPTS.parent / "TEST.md").read_text(encoding="utf-8")
        self.assertIn("## 0. 新会话协议", guide)
        self.assertIn("用户输入“开始测试”", guide)
        self.assertIn("允许回复 `1,3`", guide)
        self.assertIn("宿主模型启动外层协调器时使用非沙箱环境", guide)
        self.assertIn("不得写入 Case prompt", guide)
        self.assertIn("每 2 分钟触发一次的 heartbeat", guide)
        self.assertIn("连续两轮、间隔 15 秒", guide)
        self.assertIn("本轮 workspace/output 也保留到下一轮", guide)
        self.assertIn("`finalize --cleanup` 已停用", guide)


class MultiCasePlanTest(unittest.TestCase):
    def test_selected_minimum_suite_has_four_unique_ars_and_scripted_replies(self) -> None:
        selected = [
            "split-two-ar", "split-interactive",
            "source-conflict-review", "pattern-image-review",
        ]
        plans = run_multi_case.select_cases(selected, all_cases=False)
        self.assertEqual(4, len(plans))
        self.assertEqual(4, len({plan.feature for plan in plans}))
        self.assertEqual(3, len(run_multi_case.load_interaction_script("split-interactive")))
        self.assertEqual(1, len(run_multi_case.load_interaction_script("source-conflict-review")))
        self.assertEqual((), run_multi_case.load_interaction_script("split-two-ar"))


class SuiteFeatureArchiveTest(unittest.TestCase):
    def test_moves_all_features_to_timestamped_external_archive(self) -> None:
        root = Path(tempfile.mkdtemp())
        original_repo = run_multi_case.REPO_ROOT
        original_features = run_multi_case.FEATURES_ROOT
        original_archive = run_multi_case.FEATURE_ARCHIVE_ROOT
        try:
            repo = root / "repo"
            features = repo / "doc/features"
            archive = root / "bak"
            (features / "AR1").mkdir(parents=True)
            (features / "AR2").mkdir()
            (features / "AR1/story.md").write_text("one", encoding="utf-8")
            run_multi_case.REPO_ROOT = repo
            run_multi_case.FEATURES_ROOT = features
            run_multi_case.FEATURE_ARCHIVE_ROOT = archive

            result = run_multi_case.migrate_existing_features(root / "suite-1")

            destination = Path(result["destination_root"])
            self.assertEqual("completed", result["status"])
            self.assertRegex(destination.name, r"^Story-Features-\d{8}-\d{6}")
            self.assertEqual(archive.resolve(), destination.parent)
            self.assertTrue((destination / "AR1/story.md").is_file())
            self.assertTrue((destination / "AR2").is_dir())
            self.assertEqual([], list(features.iterdir()))
        finally:
            run_multi_case.REPO_ROOT = original_repo
            run_multi_case.FEATURES_ROOT = original_features
            run_multi_case.FEATURE_ARCHIVE_ROOT = original_archive
            shutil.rmtree(root, ignore_errors=True)

    def test_empty_features_does_not_create_archive_directory(self) -> None:
        root = Path(tempfile.mkdtemp())
        original_repo = run_multi_case.REPO_ROOT
        original_features = run_multi_case.FEATURES_ROOT
        original_archive = run_multi_case.FEATURE_ARCHIVE_ROOT
        try:
            repo = root / "repo"
            features = repo / "doc/features"
            features.mkdir(parents=True)
            archive = root / "bak"
            run_multi_case.REPO_ROOT = repo
            run_multi_case.FEATURES_ROOT = features
            run_multi_case.FEATURE_ARCHIVE_ROOT = archive

            result = run_multi_case.migrate_existing_features(root / "suite-1")

            self.assertEqual("no_existing_features", result["status"])
            self.assertIsNone(result["destination_root"])
            self.assertFalse(archive.exists())
        finally:
            run_multi_case.REPO_ROOT = original_repo
            run_multi_case.FEATURES_ROOT = original_features
            run_multi_case.FEATURE_ARCHIVE_ROOT = original_archive
            shutil.rmtree(root, ignore_errors=True)


class MultiCasePlanContinuationTest(unittest.TestCase):

    def test_all_case_definitions_are_loaded_without_new_schema(self) -> None:
        case_ids = sorted(path.name for path in run_multi_case.CASES_ROOT.iterdir()
                          if path.is_dir() and (path / "case.yaml").is_file())
        plans = [run_multi_case.load_case_plan(case_id) for case_id in case_ids]
        self.assertEqual(4, len(plans))
        self.assertEqual(4, len({plan.feature for plan in plans}))
        self.assertTrue(any(plan.contains_coding for plan in plans))
        self.assertTrue(any(plan.interactive for plan in plans))
        self.assertEqual(
            ("spec", "plan", "coding", "review"),
            run_multi_case.load_case_plan("pattern-image-review").phases,
        )

    def test_all_cases_form_one_suite_with_unique_features(self) -> None:
        plans = run_multi_case.select_cases([], all_cases=True)
        self.assertEqual(4, len(plans))
        self.assertEqual(4, len({plan.feature for plan in plans}))

    def test_story_review_is_interactive_but_does_not_reach_coding(self) -> None:
        plan = run_multi_case.load_case_plan("split-interactive")
        self.assertTrue(plan.interactive)
        self.assertEqual(("spec",), plan.phases)
        self.assertFalse(plan.contains_coding)


class MultiCaseSchedulingTest(unittest.TestCase):
    @staticmethod
    def record(case_id: str, feature: str, status: str) -> dict[str, object]:
        return {
            "case": case_id,
            "feature": feature,
            "status": status,
            "run_id": None,
            "source_restore_status": "not_started",
        }

    def suite(self, *records: dict[str, object]) -> dict[str, object]:
        return {"jobs": 3, "case_states": {str(r["case"]): r for r in records}}

    def test_same_feature_waiting_case_is_blocked(self) -> None:
        pending = self.record("split-interactive", "AR90006", "pending")
        waiting = self.record("same-feature-fixture", "AR90006", "awaiting_reply")
        self.assertEqual(
            "same_feature:same-feature-fixture",
            run_multi_case.start_block_reason(pending, self.suite(pending, waiting)),
        )

    def test_different_feature_waiting_case_can_overlap(self) -> None:
        pending = self.record("source-conflict-review", "ISSUE-410", "pending")
        waiting = self.record("same-feature-fixture", "AR90006", "awaiting_reply")
        self.assertIsNone(
            run_multi_case.start_block_reason(pending, self.suite(pending, waiting))
        )

    def test_phase_active_case_blocks_every_other_case(self) -> None:
        pending = self.record("split-two-ar", "AR90005", "pending")
        running = self.record("phase-active-fixture", "AR90004", "running")
        self.assertEqual(
            "shared_current_phase_slot:phase-active-fixture",
            run_multi_case.start_block_reason(pending, self.suite(pending, running)),
        )

    def test_isolated_cases_do_not_share_phase_slot(self) -> None:
        pending = self.record("pattern-image-review", "AR90004", "pending")
        running = self.record("source-conflict-review", "ISSUE-410", "running")
        suite = self.suite(pending, running)
        suite["isolated_workspaces"] = True
        suite["jobs"] = 4
        self.assertIsNone(run_multi_case.start_block_reason(pending, suite))

    def test_start_retries_three_times_before_failing(self) -> None:
        record = self.record("split-two-ar", "AR90005", "pending")
        record.update({"start_phase": "story", "requested_start_phase": "story",
                       "requested_end_phase": None, "start_history": []})
        suite = self.suite(record)
        suite.update({"isolated_workspaces": False, "bundle_root": tempfile.mkdtemp()})
        failed = (1, None, "", "lock busy")
        try:
            with mock.patch.object(run_multi_case, "invoke_case", return_value=failed), \
                    mock.patch.object(run_multi_case, "run_pointer_state", return_value=None):
                run_multi_case.start_one(record, suite)
            self.assertEqual("coordinator_start_failed", record["status"])
            self.assertEqual(3, record["start_attempts"])
            self.assertEqual(3, len(record["start_history"]))
        finally:
            shutil.rmtree(suite["bundle_root"], ignore_errors=True)

    def test_lost_start_response_adopts_matching_active_run(self) -> None:
        record = self.record("split-two-ar", "AR90005", "pending")
        record.update({"start_phase": "story", "requested_start_phase": "story",
                       "requested_end_phase": None, "start_history": []})
        suite = self.suite(record)
        suite.update({"isolated_workspaces": False, "bundle_root": tempfile.mkdtemp()})
        try:
            with mock.patch.object(run_multi_case, "invoke_case",
                                   return_value=(1, None, "", "response lost")), \
                    mock.patch.object(run_multi_case, "run_pointer_state", return_value={
                        "status": "running", "run_id": "run-1", "pid": 123}):
                run_multi_case.start_one(record, suite)
            self.assertEqual("running", record["status"])
            self.assertEqual("run-1", record["run_id"])
            self.assertEqual("adopted_active_run", record["start_history"][0]["result"])
        finally:
            shutil.rmtree(suite["bundle_root"], ignore_errors=True)

    def test_unexpected_gate_requires_host_adaptive_reply(self) -> None:
        record = self.record("split-interactive", "AR90006", "awaiting_reply")
        record.update({"interaction_script": [], "interaction_index": 0,
                       "last_awaiting": {"turn": 4, "kind": "story_gate",
                                         "prompt": "unexpected question"}})
        suite = self.suite(record)
        suite["bundle_root"] = tempfile.mkdtemp()
        try:
            with mock.patch.object(run_multi_case, "invoke_case") as invoke:
                run_multi_case.send_scripted_reply(record, suite)
            invoke.assert_not_called()
            self.assertEqual("adaptive_reply_required", record["interaction_state"])
        finally:
            shutil.rmtree(suite["bundle_root"], ignore_errors=True)

    def test_poll_uses_story_and_spec_cadences(self) -> None:
        record = self.record("split-two-ar", "AR90005", "running")
        record.update({"cursor": 0, "model_cursor": 0, "last_phase": "story"})
        suite = self.suite(record)
        payload = {"run": {"status": "running", "last_phase": "story"}}
        with mock.patch.object(run_multi_case, "invoke_case",
                               return_value=(0, payload, "", "")) as invoke:
            result = run_multi_case.poll_one(record, 120, 1000, suite)
        self.assertEqual(15, result["observation_cadence_sec"])
        self.assertIn("15", invoke.call_args.args)
        record["last_phase"] = "spec"
        record["spec_entered_at"] = "2026-08-22T00:00:00+08:00"
        suite["automation_stability"] = {
            "required_confirmations": 2, "consecutive_confirmations": 2,
            "ready_at": "2026-08-22T00:00:30+08:00",
        }
        payload["run"]["last_phase"] = "spec"
        with mock.patch.object(run_multi_case, "invoke_case",
                               return_value=(0, payload, "", "")):
            result = run_multi_case.poll_one(record, 15, 1000, suite)
        self.assertEqual(120, result["observation_cadence_sec"])

    def test_mixed_story_and_spec_suite_stays_on_fifteen_seconds(self) -> None:
        story = self.record("split-interactive", "AR90006", "running")
        story["last_phase"] = "story"
        spec = self.record("source-conflict-review", "ISSUE-410", "running")
        spec["last_phase"] = "spec"
        spec["spec_entered_at"] = "2026-08-22T00:00:00+08:00"
        suite = self.suite(story, spec)
        suite["automation_stability"] = {"ready_at": None}
        self.assertFalse(run_multi_case.suite_automation_ready(suite))
        story["last_phase"] = "spec"
        story["spec_entered_at"] = "2026-08-22T00:00:00+08:00"
        self.assertFalse(run_multi_case.suite_automation_ready(suite))

    def test_two_complete_spec_rounds_are_required_and_regression_resets(self) -> None:
        first = self.record("split-interactive", "AR90006", "running")
        second = self.record("source-conflict-review", "ISSUE-410", "running")
        for record in (first, second):
            record.update({"last_phase": "spec", "spec_entered_at": "entered"})
        suite = self.suite(first, second)
        suite["automation_stability"] = {
            "required_confirmations": 2, "consecutive_confirmations": 0,
            "last_confirmation_at": None, "ready_at": None, "cases": {},
        }
        results = [
            {"case": first["case"], "returncode": 0, "status": "running"},
            {"case": second["case"], "returncode": 0, "status": "running"},
        ]
        run_multi_case.update_automation_stability(suite, results)
        self.assertEqual(1, suite["automation_stability"]["consecutive_confirmations"])
        self.assertFalse(run_multi_case.suite_automation_ready(suite))
        run_multi_case.update_automation_stability(suite, results)
        self.assertTrue(run_multi_case.suite_automation_ready(suite))
        second["status"] = "awaiting_reply"
        run_multi_case.update_automation_stability(suite, results)
        self.assertEqual(0, suite["automation_stability"]["consecutive_confirmations"])
        self.assertFalse(run_multi_case.suite_automation_ready(suite))


class WorkspaceBoundaryTest(unittest.TestCase):
    def test_next_suite_deletes_terminal_workspace_and_output_pair(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="story-cleanup-"))
        original_out = run_multi_case.OUT_ROOT
        original_gettempdir = tempfile.gettempdir
        try:
            output_root = root / "output/story"
            temp_root = root / "temp"
            old_output = output_root / "story-suite-old"
            new_output = output_root / "story-suite-new"
            old_workspace = temp_root / "sw-story/story-suite-old"
            old_output.mkdir(parents=True)
            new_output.mkdir(parents=True)
            old_workspace.mkdir(parents=True)
            run_multi_case.write_json(old_output / "suite.json", {
                "suite_id": "story-suite-old", "status": "finished",
                "case_states": {},
            })
            run_multi_case.OUT_ROOT = output_root
            tempfile.gettempdir = lambda: str(temp_root)
            with mock.patch.object(run_multi_case, "_process_inventory",
                                   return_value=(True, [], None)):
                report = run_multi_case.cleanup_previous_test_runs(
                    new_output, "story-suite-new")
            self.assertEqual("completed", report["status"])
            self.assertFalse(old_output.exists())
            self.assertFalse(old_workspace.exists())
            self.assertTrue(new_output.exists())
        finally:
            run_multi_case.OUT_ROOT = original_out
            tempfile.gettempdir = original_gettempdir
            shutil.rmtree(root, ignore_errors=True)

    def test_orphan_is_deleted_only_after_process_inventory_is_clear(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="story-orphan-"))
        original_out = run_multi_case.OUT_ROOT
        original_gettempdir = tempfile.gettempdir
        try:
            output_root = root / "output/story"
            new_output = output_root / "story-suite-new"
            orphan = root / "temp/sw-story/story-suite-orphan"
            new_output.mkdir(parents=True)
            orphan.mkdir(parents=True)
            run_multi_case.OUT_ROOT = output_root
            tempfile.gettempdir = lambda: str(root / "temp")
            with mock.patch.object(run_multi_case, "_process_inventory",
                                   return_value=(True, [], None)):
                run_multi_case.cleanup_previous_test_runs(new_output, "story-suite-new")
            self.assertFalse(orphan.exists())
        finally:
            run_multi_case.OUT_ROOT = original_out
            tempfile.gettempdir = original_gettempdir
            shutil.rmtree(root, ignore_errors=True)

    def test_active_historical_suite_blocks_cleanup_before_delete(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="story-active-"))
        original_out = run_multi_case.OUT_ROOT
        original_gettempdir = tempfile.gettempdir
        try:
            output_root = root / "output/story"
            old_output = output_root / "story-suite-active"
            new_output = output_root / "story-suite-new"
            old_output.mkdir(parents=True)
            new_output.mkdir(parents=True)
            run_multi_case.write_json(old_output / "suite.json", {
                "suite_id": "story-suite-active", "status": "running",
                "case_states": {},
            })
            run_multi_case.OUT_ROOT = output_root
            tempfile.gettempdir = lambda: str(root / "temp")
            with mock.patch.object(run_multi_case, "_process_inventory",
                                   return_value=(True, [], None)):
                with self.assertRaises(SystemExit):
                    run_multi_case.cleanup_previous_test_runs(
                        new_output, "story-suite-new")
            self.assertTrue(old_output.exists())
        finally:
            run_multi_case.OUT_ROOT = original_out
            tempfile.gettempdir = original_gettempdir
            shutil.rmtree(root, ignore_errors=True)

    def test_unexpired_orphan_lease_blocks_cleanup(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="story-lease-"))
        original_out = run_multi_case.OUT_ROOT
        original_gettempdir = tempfile.gettempdir
        try:
            output_root = root / "output/story"
            orphan_output = output_root / "story-suite-orphan"
            new_output = output_root / "story-suite-new"
            state_path = orphan_output / "cases/case/run/state.json"
            state_path.parent.mkdir(parents=True)
            new_output.mkdir(parents=True)
            run_multi_case.write_json(state_path, {
                "status": "running", "pid": 999999,
                "lease_expires_epoch": time.time() + 600,
            })
            run_multi_case.OUT_ROOT = output_root
            tempfile.gettempdir = lambda: str(root / "temp")
            with mock.patch.object(run_multi_case, "_pid_alive", return_value=False), \
                    mock.patch.object(run_multi_case, "_process_inventory",
                                      return_value=(True, [], None)):
                with self.assertRaises(SystemExit):
                    run_multi_case.cleanup_previous_test_runs(
                        new_output, "story-suite-new")
            self.assertTrue(orphan_output.exists())
        finally:
            run_multi_case.OUT_ROOT = original_out
            tempfile.gettempdir = original_gettempdir
            shutil.rmtree(root, ignore_errors=True)

    def test_finalize_cleanup_is_disabled(self) -> None:
        with self.assertRaises(SystemExit) as caught:
                run_multi_case.command_finalize("unused", False, True)
        self.assertIn("下一轮 suite 起跑时清理", str(caught.exception))

    def test_allowlist_workspace_excludes_test_tools_output_and_git(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="story-multi-boundary-"))
        suite_root = root / "suite"
        original_root = run_multi_case.REPO_ROOT
        original_tmp = tempfile.gettempdir
        try:
            run_multi_case.REPO_ROOT = root / "repo"
            source = run_multi_case.REPO_ROOT
            for relative in ("01-Product", "framework", "doc/extensions", "test",
                             "tools", "output", ".git"):
                (source / relative).mkdir(parents=True, exist_ok=True)
                (source / relative / "marker.txt").write_text(relative, encoding="utf-8")
            (source / "01-Product" / "main.ets").write_text("product", encoding="utf-8")
            (source / "framework" / "harness" / "state").mkdir(parents=True, exist_ok=True)
            (source / "framework" / "harness" / "state" / "phase.json").write_text("state", encoding="utf-8")
            for relative in run_multi_case.WORKSPACE_ALLOWED_FILES:
                (source / relative).parent.mkdir(parents=True, exist_ok=True)
                (source / relative).write_text(relative, encoding="utf-8")
            suite_root.mkdir(parents=True)
            template, workspace_root = run_multi_case.create_workspace_template(
                suite_root, "boundary-test")
            self.assertTrue((template / "01-Product" / "main.ets").is_file())
            self.assertFalse((template / "test").exists())
            self.assertFalse((template / "tools").exists())
            self.assertFalse((template / "output").exists())
            self.assertFalse((template / ".git").exists())
            self.assertFalse((template / "framework" / "harness" / "state" / "phase.json").exists())
            self.assertTrue(str(workspace_root).endswith("boundary-test"))
        finally:
            run_multi_case.REPO_ROOT = original_root
            shutil.rmtree(root, ignore_errors=True)
            shutil.rmtree(Path(tempfile.gettempdir()) / "sw-story" / "boundary-test",
                          ignore_errors=True)

    def test_failed_terminal_case_promotes_document_and_source_with_labels(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="story-promotion-"))
        original_repo = run_multi_case.REPO_ROOT
        original_features = run_multi_case.FEATURES_ROOT
        try:
            host = root / "host"
            workspace = root / "workspace"
            bundle = root / "bundle"
            (host / "doc/features").mkdir(parents=True)
            (workspace / "doc/features/AR-X").mkdir(parents=True)
            (workspace / "01-Product").mkdir(parents=True)
            (workspace / "doc/features/AR-X/story.md").write_text(
                "failed evidence", encoding="utf-8")
            baseline = run_multi_case.snapshot_workspace_sources(workspace)
            (workspace / "01-Product/new.txt").write_text("source", encoding="utf-8")
            baseline_path = bundle / "cases/case-x/workspace-baseline.json"
            baseline_path.parent.mkdir(parents=True)
            run_multi_case.write_json(baseline_path, baseline)
            run_multi_case.REPO_ROOT = host
            run_multi_case.FEATURES_ROOT = host / "doc/features"
            suite = {
                "bundle_root": str(bundle),
                "main_source_baseline": run_multi_case.snapshot_workspace_sources(host),
            }
            record = {
                "case": "case-x", "feature": "AR-X", "workspace": str(workspace),
                "workspace_baseline": str(baseline_path), "status": "cli_failed",
                "execution_status": "failed",
            }
            result = run_multi_case.promote_case_workspace(suite, record)
            self.assertEqual("promoted", result["status"])
            self.assertEqual("cli_failed", result["case_status"])
            self.assertTrue((host / "doc/features/AR-X/story.md").is_file())
            self.assertTrue((host / "01-Product/new.txt").is_file())
        finally:
            run_multi_case.REPO_ROOT = original_repo
            run_multi_case.FEATURES_ROOT = original_features
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
