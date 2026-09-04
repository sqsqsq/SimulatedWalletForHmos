"""Tests for the multi-case coordinator's scheduling contract.

These tests do not start a provider CLI.  Formal behavior still belongs to
the existing per-case runner and its immutable run evidence.
"""
from __future__ import annotations

import json
import os
import unittest
import sys
import tempfile
import shutil
import time
from datetime import datetime
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
        self.assertIn("动态读取可用 Case", guide)
        self.assertIn("宿主模型启动外层协调器时使用非沙箱环境", guide)
        self.assertIn("不得写入 Case prompt", guide)
        self.assertIn("同一个 heartbeat 每 15 秒唤醒", guide)
        self.assertIn("poll --wait-sec 0", guide)
        self.assertIn("同一个 heartbeat 更新为", guide)
        self.assertIn("本轮 workspace/output 也保留到下一轮", guide)
        self.assertIn("`finalize --cleanup` 已停用", guide)


class MultiCasePlanTest(unittest.TestCase):
    def test_selected_suite_uses_exact_dynamic_case_set(self) -> None:
        selected = sorted(path.name for path in run_multi_case.CASES_ROOT.iterdir()
                          if path.is_dir() and (path / "case.yaml").is_file())
        plans = run_multi_case.select_cases(selected, all_cases=False)
        self.assertEqual(selected, [plan.case_id for plan in plans])
        self.assertEqual(len(plans), len({plan.feature for plan in plans}))


class StructuredPhaseStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.feature = "AR-PHASE"

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def record(self) -> dict[str, object]:
        return {
            "case": "phase-case", "feature": self.feature,
            "workspace": str(self.root), "requested_start_phase": "story",
            "last_phase": "story", "current_phase": "story",
        }

    def write_current_phase(self, phase: str, feature: str | None = None) -> None:
        path = self.root / "framework/harness/state/.current-phase.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({
            "phase": phase, "feature": feature or self.feature,
            "updated_at": "2026-08-22T03:43:28Z",
        }), encoding="utf-8")

    def test_framework_state_corrects_story_to_spec(self) -> None:
        record = self.record()
        self.write_current_phase("spec")
        changes = run_multi_case.reconcile_record_phase(record)
        self.assertEqual("spec", record["current_phase"])
        self.assertEqual("spec", record["highest_phase_reached"])
        self.assertEqual("framework_current_phase", record["phase_source"])
        self.assertIn("current_phase", changes)
        self.assertTrue(record["spec_entered_at"])

    def test_phase_artifact_is_structured_fallback(self) -> None:
        artifact = self.root / f"doc/features/{self.feature}/spec/spec.md"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("# spec", encoding="utf-8")
        record = self.record()
        run_multi_case.reconcile_record_phase(record)
        self.assertEqual("spec", record["current_phase"])
        self.assertEqual("phase_artifact", record["phase_source"])

    def test_framework_phase_is_current_while_artifact_advances_highest(self) -> None:
        self.write_current_phase("spec")
        artifact = self.root / f"doc/features/{self.feature}/plan/plan.md"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("# plan", encoding="utf-8")
        record = self.record()
        run_multi_case.reconcile_record_phase(record)
        self.assertEqual("spec", record["current_phase"])
        self.assertEqual("plan", record["highest_phase_reached"])
        self.assertEqual("framework_current_phase", record["phase_source"])

    def test_invalid_or_foreign_framework_state_is_ignored(self) -> None:
        record = self.record()
        self.write_current_phase("spec", feature="OTHER")
        run_multi_case.reconcile_record_phase(record)
        self.assertEqual("story", record["current_phase"])
        self.assertFalse(record.get("spec_entered_at"))

    def test_model_prose_does_not_change_phase(self) -> None:
        record = self.record()
        record["last_model_text"] = "已经进入 /spec 并读取 Spec Skill"
        run_multi_case.reconcile_record_phase(record)
        self.assertEqual("story", record["current_phase"])

    def test_highest_phase_never_regresses(self) -> None:
        record = self.record()
        record.update({"current_phase": "plan", "last_phase": "plan",
                       "highest_phase_reached": "plan",
                       "spec_entered_at": "2026-08-22T03:00:00Z"})
        run_multi_case.reconcile_record_phase(record)
        self.assertEqual("plan", record["highest_phase_reached"])
        self.assertEqual("2026-08-22T03:00:00Z", record["spec_entered_at"])


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
        self.assertEqual(len(case_ids), len(plans))
        self.assertEqual(len(plans), len({plan.feature for plan in plans}))
        for plan in plans:
            self.assertIn(plan.start_phase, run_multi_case.VALID_START)
            self.assertIn(plan.end_phase, run_multi_case.VALID_END)
            self.assertEqual(plan.contains_coding, "coding" in plan.phases)

    def test_all_cases_form_one_suite_with_unique_features(self) -> None:
        plans = run_multi_case.select_cases([], all_cases=True)
        discovered = [path for path in run_multi_case.CASES_ROOT.iterdir()
                      if path.is_dir() and (path / "case.yaml").is_file()]
        self.assertEqual(len(discovered), len(plans))
        self.assertEqual(len(plans), len({plan.feature for plan in plans}))

    def test_interactive_flag_matches_loaded_script(self) -> None:
        for directory in run_multi_case.CASES_ROOT.iterdir():
            if not (directory / "case.yaml").is_file():
                continue
            plan = run_multi_case.load_case_plan(directory.name)
            if plan.interaction_script:
                self.assertTrue(plan.interactive)


class MultiCaseSchedulingTest(unittest.TestCase):
    """调度判据只看 case 与 feature 是否相同，与它们叫什么无关。

    所以这里一律用**构造出来的夹具名**：写真实 Case 名的话，换一批用例就会亮起
    一片红灯，而调度逻辑一个字都没改。
    """

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
        pending = self.record("case-alpha-fixture", "AR-ALPHA", "pending")
        waiting = self.record("same-feature-fixture", "AR-ALPHA", "awaiting_reply")
        self.assertEqual(
            "same_feature:same-feature-fixture",
            run_multi_case.start_block_reason(pending, self.suite(pending, waiting)),
        )

    def test_different_feature_waiting_case_can_overlap(self) -> None:
        pending = self.record("case-beta-fixture", "ISSUE-BETA", "pending")
        waiting = self.record("same-feature-fixture", "AR-ALPHA", "awaiting_reply")
        self.assertIsNone(
            run_multi_case.start_block_reason(pending, self.suite(pending, waiting))
        )

    def test_cases_never_share_a_phase_slot(self) -> None:
        """**2026-09-02 改判**：阶段槽串行是非隔离模式的产物，那个模式已经退场。

        每个 Case 有自己的临时工作区，框架阶段互不相干，没有槽位可抢。
        原用例断言的 `shared_current_phase_slot` 阻塞随非隔离分支一起删掉了。
        """
        pending = self.record("case-delta-fixture", "AR-DELTA", "pending")
        running = self.record("case-beta-fixture", "ISSUE-BETA", "running")
        suite = self.suite(pending, running)
        suite["jobs"] = 4
        self.assertIsNone(run_multi_case.start_block_reason(pending, suite))

    def test_the_shared_slot_reason_is_gone_from_the_source(self) -> None:
        """槽位串行的理由码不许长回来——它一回来就是非隔离模式又开了口子。"""
        body = (Path(run_multi_case.__file__)).read_text(encoding="utf-8")
        self.assertNotIn("shared_current_phase_slot:", body)

    def test_start_retries_three_times_before_failing(self) -> None:
        record = self.record("case-gamma-fixture", "AR-GAMMA", "pending")
        record.update({"start_phase": "story", "requested_start_phase": "story",
                       "requested_end_phase": None, "start_history": []})
        record["workspace"] = tempfile.mkdtemp()   # 工作区已备好，本例只测重试计数
        suite = self.suite(record)
        suite.update({"bundle_root": tempfile.mkdtemp()})
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
        record = self.record("case-gamma-fixture", "AR-GAMMA", "pending")
        record.update({"start_phase": "story", "requested_start_phase": "story",
                       "requested_end_phase": None, "start_history": []})
        record["workspace"] = tempfile.mkdtemp()   # 同上：本例测的是丢响应后的认领
        suite = self.suite(record)
        suite.update({"bundle_root": tempfile.mkdtemp()})
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

    def test_poll_calls_the_host_even_without_a_plan(self) -> None:
        """经**真实调用点** `poll_suite` 驱动一次，且这个 Case 没有规划文件。

        两件事一起验：① 调用点与函数定义对得上（上一版改名漏了调用点，
        任何带规划的 Case 进 awaiting_reply 都 NameError，而五条单测全都直调
        新名字、一条没响）；② 没写规划的 Case 也要被叫人——上一版的
        `and record.get("interaction_script")` 前置会让它静默挂着，谁也不知道它在等谁。
        """
        record = self.record("case-alpha-fixture", "AR-ALPHA", "awaiting_reply")
        record.update({"interaction_script": [], "interaction_index": 0,
                       "next_observation_at": None})
        suite = self.suite(record)
        suite["bundle_root"] = tempfile.mkdtemp()
        suite["events"] = []
        try:
            polled = {
                "case": "case-alpha-fixture", "status": "awaiting_reply",
                "returncode": 0,
                "awaiting_reply": {"turn": 3, "kind": "story_gate",
                                   "prompt": "范围怎么定？"},
            }
            with mock.patch.object(run_multi_case, "poll_one", return_value=polled), \
                    mock.patch.object(run_multi_case, "append_case_observation",
                                      lambda *a, **k: None), \
                    mock.patch.object(run_multi_case, "update_automation_stability",
                                      lambda *a, **k: None):
                run_multi_case.poll_suite(suite, wait_sec=0, max_chars=1000)
            self.assertEqual("adaptive_reply_required", record["interaction_state"])
            request = record["last_adaptive_request"]
            self.assertEqual("no_plan_for_this_case", request["reason"],
                             "没写规划与规划走完了是两回事，要分开报")
            self.assertEqual("范围怎么定？", request["question"])
        finally:
            shutil.rmtree(suite["bundle_root"], ignore_errors=True)

    def test_every_gate_goes_to_the_host(self) -> None:
        """每一关都交给宿主——规划不再自己发话。

        宿主替代的是**人**：人不会两次说出一模一样的句子，也不会对着一段没有问题的
        独白照本宣科。规划留在那儿供宿主判断这一关该表达什么立场。
        """
        record = self.record("case-alpha-fixture", "AR-ALPHA", "awaiting_reply")
        record.update({"interaction_script": [], "interaction_index": 0,
                       "last_awaiting": {"turn": 4, "kind": "story_gate",
                                         "prompt": "unexpected question"}})
        suite = self.suite(record)
        suite["bundle_root"] = tempfile.mkdtemp()
        try:
            with mock.patch.object(run_multi_case, "invoke_case") as invoke:
                run_multi_case.request_host_reply(record, suite)
            invoke.assert_not_called()
            self.assertEqual("adaptive_reply_required", record["interaction_state"])
            self.assertEqual("no_plan_for_this_case",
                             record["last_adaptive_request"]["reason"])
        finally:
            shutil.rmtree(suite["bundle_root"], ignore_errors=True)

    def test_the_request_carries_what_this_gate_should_convey(self) -> None:
        """回落信息要带上「这一关按规划本该表达什么」。

        上一版只给「模型说了什么」，宿主要自己去翻脚本；翻漏了就临场发挥，
        观测到的于是掺进了宿主自己的话——实测发生过一次。
        """
        record = self.record("case-alpha-fixture", "AR-ALPHA", "awaiting_reply")
        record.update({
            "interaction_script": [
                {"id": "scope", "text": "这次不拆单，一起做完。", "expected_turn": 1,
                 "expected_phase": "story", "deliver": []},
            ],
            "interaction_index": 0,
            "last_awaiting": {"turn": 7, "kind": "story_gate", "prompt": "范围怎么定？"},
        })
        suite = self.suite(record)
        suite["bundle_root"] = tempfile.mkdtemp()
        try:
            with mock.patch.object(run_multi_case, "invoke_case") as invoke:
                run_multi_case.request_host_reply(record, suite)
            invoke.assert_not_called()
            request = record["last_adaptive_request"]
            self.assertEqual("scope", request["planned_step_id"])
            self.assertEqual("这次不拆单，一起做完。", request["planned_intent"])
            self.assertEqual("范围怎么定？", request["question"])
            # 关卡编号对不上不再决定任何事——它只是参考
            self.assertEqual(7, request["turn"])
            self.assertEqual(1, request["planned_turn"])
            self.assertEqual("0/1", request["script_cursor"])
        finally:
            shutil.rmtree(suite["bundle_root"], ignore_errors=True)

    def test_next_gate_is_replied_even_when_previous_reply_was_accepted(self) -> None:
        """新关卡按编号识别：不依赖协调器观测到 WAITING→ACTIVE 的跳变。

        被测模型常在一个轮询周期内消费回复并抛出下一关，两次 poll 看到的都是 awaiting；
        按「上一次回复被消费了没有」判，第二关永远等不到回复（实测两次都卡在这里）。
        """
        record = self.record("case-alpha-fixture", "AR-ALPHA", "awaiting_reply")
        record.update({
            "interaction_script": [
                {"id": "s1", "text": "第一关回复", "expected_turn": 1},
                {"id": "s2", "text": "第二关回复", "expected_turn": 2},
            ],
            "interaction_index": 0,
            "last_awaiting": {"turn": 1, "kind": "story_gate"},
        })
        suite = self.suite(record)
        suite["bundle_root"] = tempfile.mkdtemp()
        try:
            with mock.patch.object(run_multi_case, "invoke_case") as invoke:
                self.assertTrue(run_multi_case.is_new_gate(record))
                run_multi_case.request_host_reply(record, suite)
                # 宿主回话之后这一关才算回过（`command_reply` 里记）
                record["last_replied_turn"] = 1
                record["last_reply_status"] = "accepted"

                # 同一关卡再来一次 poll：不重复叫宿主
                self.assertFalse(run_multi_case.is_new_gate(record))

                # 新关卡出现（上一次回复仍标 accepted）：照样要叫
                record["last_awaiting"] = {"turn": 2, "kind": "story_gate"}
                self.assertTrue(run_multi_case.is_new_gate(record))
                run_multi_case.request_host_reply(record, suite)
            invoke.assert_not_called()
            self.assertEqual(2, record["adaptive_reply_count"])
        finally:
            shutil.rmtree(suite["bundle_root"], ignore_errors=True)

    def test_the_phase_precondition_is_handed_to_the_host_not_enforced(self) -> None:
        """阶段前提随规划条目一起交给宿主判断，装置不再据它决定发不发。

        评审意见这类话依赖尚未发生的事（归档）。上一版的做法是「前提不满足就回落」，
        而现在**每一关都回落**——前提写进 `planned_phase`，宿主看着它决定这一关
        该不该把那个意思说出口。判据仍是「装置一个字都没发出去」。
        """
        record = self.record("case-alpha-fixture", "AR-ALPHA", "awaiting_reply")
        workspace = Path(tempfile.mkdtemp())
        flow_dir = workspace / "doc" / "features" / "AR-ALPHA" / "AR"
        flow_dir.mkdir(parents=True)
        (flow_dir / "story-flow.json").write_text(
            json.dumps({"archived": False}), encoding="utf-8")
        record.update({
            "interaction_script": [
                {"id": "review", "text": "评审意见", "expected_turn": 3,
                 "expected_kind": "story_gate", "expected_phase": "archived"},
            ],
            "interaction_index": 0,
            "workspace": str(workspace),
            "highest_phase_reached": "spec",
            "last_awaiting": {"turn": 3, "kind": "story_gate", "prompt": "请给评审意见"},
        })
        suite = self.suite(record)
        suite["bundle_root"] = tempfile.mkdtemp()
        try:
            def must_not_send(*a, **kw):
                raise AssertionError("装置替宿主发了回复")

            with mock.patch.object(run_multi_case, "invoke_case", must_not_send):
                run_multi_case.request_host_reply(record, suite)
            request = record["last_adaptive_request"]
            self.assertEqual("adaptive_reply_required", record["interaction_state"])
            self.assertEqual("archived", request["planned_phase"],
                             "阶段前提要交到宿主手上，让他判断这话现在该不该说")
            self.assertEqual("评审意见", request["planned_intent"])
            # 指针只由宿主 `--step` 推进，装置自己不动它
            self.assertEqual(0, record["interaction_index"])
        finally:
            shutil.rmtree(suite["bundle_root"], ignore_errors=True)
            shutil.rmtree(workspace, ignore_errors=True)

    def test_gate_phase_ready_reads_reached_phase_not_prose(self) -> None:
        record = {"highest_phase_reached": None}
        self.assertTrue(run_multi_case.gate_phase_ready(record, "story"))
        self.assertFalse(run_multi_case.gate_phase_ready(record, "spec"))
        record["highest_phase_reached"] = "spec"
        self.assertFalse(run_multi_case.gate_phase_ready(record, "story"))
        self.assertTrue(run_multi_case.gate_phase_ready(record, "spec"))
        record["highest_phase_reached"] = "plan"
        self.assertTrue(run_multi_case.gate_phase_ready(record, "spec"))
        # 空字符串 = 未声明前提，一律放行
        self.assertTrue(run_multi_case.gate_phase_ready(record, ""))

    def test_poll_uses_story_and_spec_cadences(self) -> None:
        record = self.record("case-gamma-fixture", "AR-GAMMA", "running")
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
        story = self.record("case-alpha-fixture", "AR-ALPHA", "running")
        story["last_phase"] = "story"
        spec = self.record("case-beta-fixture", "ISSUE-BETA", "running")
        spec["last_phase"] = "spec"
        spec["spec_entered_at"] = "2026-08-22T00:00:00+08:00"
        suite = self.suite(story, spec)
        suite["automation_stability"] = {"ready_at": None}
        self.assertFalse(run_multi_case.suite_automation_ready(suite))
        story["last_phase"] = "spec"
        story["spec_entered_at"] = "2026-08-22T00:00:00+08:00"
        self.assertFalse(run_multi_case.suite_automation_ready(suite))

    def test_two_complete_spec_rounds_are_required_and_regression_resets(self) -> None:
        first = self.record("case-alpha-fixture", "AR-ALPHA", "running")
        second = self.record("case-beta-fixture", "ISSUE-BETA", "running")
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
        with mock.patch.object(run_multi_case.time, "time", return_value=100.0):
            run_multi_case.update_automation_stability(suite, results)
        self.assertEqual(1, suite["automation_stability"]["consecutive_confirmations"])
        self.assertFalse(run_multi_case.suite_automation_ready(suite))
        with mock.patch.object(run_multi_case.time, "time", return_value=116.0):
            run_multi_case.update_automation_stability(suite, results)
        self.assertTrue(run_multi_case.suite_automation_ready(suite))
        second["status"] = "awaiting_reply"
        run_multi_case.update_automation_stability(suite, results)
        self.assertEqual(0, suite["automation_stability"]["consecutive_confirmations"])
        self.assertFalse(run_multi_case.suite_automation_ready(suite))

    def test_control_payload_is_dynamic_and_has_only_protocol_actions(self) -> None:
        records = [self.record(f"case-{index}", f"feature-{index}", "running")
                   for index in range(1, 4)]
        suite = self.suite(*records)
        suite.update({"suite_id": "dynamic", "status": "running",
                      "automation_stability": {"required_confirmations": 2,
                                               "consecutive_confirmations": 0}})
        payload = run_multi_case.control_payload(suite)
        self.assertEqual(len(records), payload["selected_case_count"])
        self.assertEqual([record["case"] for record in records],
                         [case["case"] for case in payload["cases"]])
        self.assertIn(payload["next_action"], {
            "poll_after_interval", "reply_then_poll", "finalize",
        })
        self.assertEqual(15, payload["next_interval_sec"])
        self.assertFalse(payload["progress_changed"])
        self.assertEqual([], payload["changes"])

    def test_adaptive_request_requires_reply_then_poll(self) -> None:
        record = self.record("case-x", "feature-x", "awaiting_reply")
        record.update({"interaction_state": "adaptive_reply_required",
                       "last_adaptive_request": {"turn": 2, "kind": "question",
                                                 "prompt": "choose scope"}})
        suite = self.suite(record)
        suite.update({"suite_id": "adaptive", "status": "running"})
        payload = run_multi_case.control_payload(suite)
        self.assertEqual("reply_then_poll", payload["next_action"])
        self.assertEqual("choose scope",
                         payload["adaptive_reply_requests"][0]["prompt"])
        self.assertEqual(15, payload["next_interval_sec"])

    def test_ready_suite_switches_same_heartbeat_to_120_seconds(self) -> None:
        record = self.record("case-x", "feature-x", "running")
        record.update({"last_phase": "spec", "spec_entered_at": "entered"})
        suite = self.suite(record)
        suite.update({"suite_id": "ready", "status": "running",
                      "automation_stability": {
                          "required_confirmations": 2,
                          "consecutive_confirmations": 2,
                          "ready_at": "ready",
                      }})
        payload = run_multi_case.control_payload(suite)
        self.assertEqual("poll_after_interval", payload["next_action"])
        self.assertEqual(120, payload["next_interval_sec"])

    def test_terminal_suite_requests_finalize_and_no_next_interval(self) -> None:
        record = self.record("case-x", "feature-x", "finished")
        suite = self.suite(record)
        suite.update({"suite_id": "done", "status": "finished"})
        payload = run_multi_case.control_payload(suite)
        self.assertTrue(payload["suite_terminal"])
        self.assertEqual("finalize", payload["next_action"])
        self.assertIsNone(payload["next_interval_sec"])

    def test_progress_changes_cover_dynamic_case_fields_and_interactions(self) -> None:
        record = self.record("arbitrary-case", "feature-x", "running")
        record.update({"last_phase": "story", "interaction_state": "waiting",
                       "last_reply_status": None, "last_error": None})
        suite = self.suite(record)
        before = run_multi_case.progress_snapshot(suite)
        record.update({"last_phase": "spec", "spec_entered_at": "entered",
                       "interaction_state": "complete",
                       "last_reply_status": "accepted"})
        changes = run_multi_case.progress_changes(before, suite, [{
            "name": "scripted_reply_accepted", "case": "arbitrary-case"}])
        self.assertEqual("case_progress", changes[0]["kind"])
        self.assertIn("last_phase", changes[0]["fields"])
        self.assertEqual("interaction", changes[1]["kind"])

    def test_zero_wait_poll_does_not_add_cli_sleep(self) -> None:
        record = self.record("case-x", "feature-x", "running")
        record.update({"cursor": 0, "model_cursor": 0, "last_phase": "story"})
        suite = self.suite(record)
        payload = {"run": {"status": "running", "last_phase": "story"}}
        with mock.patch.object(run_multi_case, "invoke_case",
                               return_value=(0, payload, "", "")) as invoke:
            run_multi_case.poll_one(record, 0, 1000, suite)
        args = invoke.call_args.args
        self.assertEqual("0", args[args.index("--wait-sec") + 1])


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

    def test_cleanup_failure_is_warning_and_does_not_block_start(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="story-cleanup-warning-"))
        original_out = run_multi_case.OUT_ROOT
        original_gettempdir = tempfile.gettempdir
        try:
            output_root = root / "output/story"
            old_output = output_root / "story-suite-old"
            new_output = output_root / "story-suite-new"
            old_output.mkdir(parents=True)
            new_output.mkdir(parents=True)
            run_multi_case.write_json(old_output / "suite.json", {
                "suite_id": "story-suite-old", "status": "finished",
                "case_states": {},
            })
            run_multi_case.OUT_ROOT = output_root
            tempfile.gettempdir = lambda: str(root / "temp")
            with mock.patch.object(run_multi_case, "_process_inventory",
                                   return_value=(True, [], None)), \
                    mock.patch.object(
                        run_multi_case, "_remove_tree_with_recovery",
                        side_effect=OSError("residual snapshot")):
                report = run_multi_case.cleanup_previous_test_runs(
                    new_output, "story-suite-new")
            self.assertEqual("completed_with_warnings", report["status"])
            self.assertEqual(1, len(report["warnings"]))
            self.assertTrue(old_output.exists())
            self.assertTrue(new_output.exists())
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
            (source / "01-Product" / "nested" / "tools").mkdir(parents=True)
            (source / "01-Product" / "nested" / "tools" / "secret.txt").write_text(
                "excluded", encoding="utf-8")
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
            self.assertFalse((template / "01-Product" / "nested" / "tools").exists())
            boundary = run_multi_case.read_json(suite_root / "workspace-boundary.json")
            self.assertIn("copied", boundary)
            self.assertIn("excluded", boundary)
            self.assertIn("case_seeded", boundary)
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

    def test_batch_promotion_keeps_later_features_and_is_idempotent(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="story-promotion-batch-"))
        original_repo = run_multi_case.REPO_ROOT
        original_features = run_multi_case.FEATURES_ROOT
        try:
            host = root / "host"
            bundle = root / "bundle"
            (host / "doc/features").mkdir(parents=True)
            (host / "01-Product").mkdir(parents=True)
            (host / "01-Product/base.txt").write_text("base", encoding="utf-8")
            main_baseline = run_multi_case.snapshot_workspace_sources(host)
            suite = {"bundle_root": str(bundle),
                     "main_source_baseline": main_baseline}
            records = []
            for index in (1, 2):
                workspace = root / f"workspace-{index}"
                shutil.copytree(host, workspace)
                feature = f"AR-{index}"
                feature_root = workspace / "doc/features" / feature
                feature_root.mkdir(parents=True)
                (feature_root / "story.md").write_text(feature, encoding="utf-8")
                baseline = run_multi_case.snapshot_workspace_sources(workspace)
                if index == 1:
                    (workspace / "01-Product/base.txt").write_text(
                        "case-one", encoding="utf-8")
                baseline_path = bundle / f"cases/case-{index}/workspace-baseline.json"
                baseline_path.parent.mkdir(parents=True)
                run_multi_case.write_json(baseline_path, baseline)
                records.append({
                    "case": f"case-{index}", "feature": feature,
                    "workspace": str(workspace),
                    "workspace_baseline": str(baseline_path),
                    "status": "finished", "execution_status": "finished",
                })
            run_multi_case.REPO_ROOT = host
            run_multi_case.FEATURES_ROOT = host / "doc/features"

            first = run_multi_case.promote_case_workspace(suite, records[0])
            second = run_multi_case.promote_case_workspace(suite, records[1])
            repeated = run_multi_case.promote_case_workspace(suite, records[0])

            self.assertEqual("promoted", first["status"])
            self.assertEqual("promoted", second["status"])
            self.assertEqual("already_promoted", repeated["status"])
            self.assertTrue(repeated["accepted"])
            self.assertEqual("AR-1", (host / "doc/features/AR-1/story.md").read_text())
            self.assertEqual("AR-2", (host / "doc/features/AR-2/story.md").read_text())
            self.assertEqual("case-one", (host / "01-Product/base.txt").read_text())
        finally:
            run_multi_case.REPO_ROOT = original_repo
            run_multi_case.FEATURES_ROOT = original_features
            shutil.rmtree(root, ignore_errors=True)


class PidReuseDoesNotBlockCleanup(unittest.TestCase):
    """判进程存活要比身份——只比 pid 号会被系统的号码复用骗到。

    实测（首跑起跑前）：三个几天前的 worker 早已退出，pid 被发给了别的进程
    （37520→conhost、23876→cmd、10456→VSCode 安装程序），于是历史现场清理预检报
    「active state, pid or lease」，新 suite 起不来。那三份 state 的 status 都是终态、
    lease 过期二十万秒以上，只有 pid 那一项把它们判成活的。
    """

    def test_a_live_pid_with_an_ancient_started_at_is_not_the_same_process(self) -> None:
        """同一个活着的 pid，配一条三天前的启动记录 → 那是号码被复用了。"""
        ancient = datetime.fromtimestamp(time.time() - 3 * 86400).strftime("%Y-%m-%d %H:%M:%S")
        self.assertFalse(run_multi_case._pid_alive(os.getpid(), ancient),
                         "创建时间比记录晚三天，仍被当成同一个进程")

    def test_the_same_pid_with_a_fresh_record_is_alive(self) -> None:
        """反面：记录就是刚才写的，那就是它本人，不能误判成死。"""
        fresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.assertTrue(run_multi_case._pid_alive(os.getpid(), fresh))

    def test_without_a_record_it_falls_back_to_the_pid(self) -> None:
        """拿不到启动记录时退回只比 pid：**宁可判成活的**。

        误判成活只是拦住清理（有人来看），误判成死会删掉正在跑的现场。
        """
        self.assertTrue(run_multi_case._pid_alive(os.getpid(), None))
        self.assertTrue(run_multi_case._pid_alive(os.getpid(), ""))

    def test_state_evidence_stops_calling_a_reused_pid_active(self) -> None:
        """整条预检：一个终态 + lease 过期 + pid 被复用的历史 run，不该判 active。"""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "cases" / "auto-topup" / "20260831-215912-21320-718c965a"
            run_dir.mkdir(parents=True)
            (run_dir / "state.json").write_text(json.dumps({
                "case": "auto-topup",
                "pid": os.getpid(),                       # 活着，但不是当初那个
                "status": "stopped",
                "started_at": datetime.fromtimestamp(
                    time.time() - 3 * 86400).strftime("%Y-%m-%d %H:%M:%S"),
                "lease_expires_epoch": time.time() - 200000,
            }, ensure_ascii=False), encoding="utf-8")
            evidence = run_multi_case._state_evidence(Path(tmp))
            self.assertEqual(1, len(evidence))
            self.assertFalse(evidence[0]["active"],
                             f"pid 复用仍被判成活的：{evidence[0]}")

    def test_a_genuinely_running_worker_is_still_protected(self) -> None:
        """真的在跑的现场不能被删——这是上一条的反面，两条一起才是判据。"""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "cases" / "auto-topup" / "run-live"
            run_dir.mkdir(parents=True)
            (run_dir / "state.json").write_text(json.dumps({
                "case": "auto-topup",
                "pid": os.getpid(),
                "status": "running",
                "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "lease_expires_epoch": time.time() + 600,
            }, ensure_ascii=False), encoding="utf-8")
            evidence = run_multi_case._state_evidence(Path(tmp))
            self.assertTrue(evidence[0]["active"], "正在跑的现场被判成可删")


if __name__ == "__main__":
    unittest.main()


class WorkspaceMustLiveInTemp(unittest.TestCase):
    """测量工具不许在被测对象的仓里跑 —— 两道物理校验。

    隔离曾经是**可选的**（`--isolated-workspaces`，缺省关）。缺省关的那一轮，
    被测 CLI 直接跑在主仓里，被测模型改了判据所在目录的一个文件。它自己报备了，
    所以这次看得见；看不见的那次会把「机制被改过之后的读数」当成干净的读数。

    开关已经退场。下面锁的是「退场之后不许从别的地方回来」：工作区必须落在系统
    临时目录，且不得是主仓的子路径。
    """

    def suite_with_workspace_root(self, root: Path) -> dict:
        return {
            "bundle_root": str(root),
            "workspace_template": str(root / "template"),
            "workspace_root": str(root),
        }

    def test_a_workspace_under_the_main_repo_is_refused(self) -> None:
        """工作区落在主仓里——起跑前就拒绝，不是跑完再后悔。"""
        suite = self.suite_with_workspace_root(run_multi_case.REPO_ROOT / "output")
        with self.assertRaises(SystemExit) as ctx:
            run_multi_case.create_case_workspace(suite, {"case": "any-case"})
        self.assertRegex(str(ctx.exception), "临时目录|主仓",
                         "报错要说清是哪一条不成立")

    def test_the_isolation_switch_is_gone(self) -> None:
        """`--isolated-workspaces` 与非隔离分支一起退场，不留关掉隔离的入口。"""
        body = Path(run_multi_case.__file__).read_text(encoding="utf-8")
        for gone in ("--isolated-workspaces", "isolated_workspaces",
                     "not_isolated", "current_workspace"):
            self.assertNotIn(gone, body, "「%s」还在，隔离仍可被关掉" % gone)


class MechanismContaminationIsAlwaysVisible(unittest.TestCase):
    """机制层被改过这件事，永远不会悄悄混进读数。

    哨兵**不拦**（改动可能来自维护者自己），它只保证这件事出现在 suite 终态里。
    """

    def suite_all_finished(self) -> dict:
        return {"case_states": {"c": {"case": "c", "status": "finished",
                                      "source_restore_status": "not_required"}}}

    def test_a_clean_tree_finishes_normally(self) -> None:
        suite = self.suite_all_finished()
        with mock.patch.object(run_multi_case, "mechanism_contamination",
                               return_value={"checked": True, "clean": True}):
            self.assertEqual("finished", run_multi_case.finalize_suite_status(suite))

    def test_a_dirty_mechanism_marks_the_suite(self) -> None:
        """`doc/extensions` 有未提交改动 → suite 终态变 `harness_contaminated`。"""
        suite = self.suite_all_finished()
        dirty = {"checked": True, "clean": False,
                 "status": " M doc/extensions/skills/story/scripts/story_flow.py",
                 "diff": "@@ -1 +1 @@\n-a\n+b\n"}
        with mock.patch.object(run_multi_case, "mechanism_contamination",
                               return_value=dirty):
            self.assertEqual("harness_contaminated",
                             run_multi_case.finalize_suite_status(suite))
        self.assertEqual(dirty, suite["mechanism_contamination"],
                         "diff 要落进 suite，事后能查是哪一处被改了")

    def test_an_unusable_git_does_not_fail_the_suite(self) -> None:
        """哨兵自己跑不起来时不冒充结论——记「没核过」，不把 suite 判脏。"""
        suite = self.suite_all_finished()
        with mock.patch.object(run_multi_case, "mechanism_contamination",
                               return_value={"checked": False, "reason": "git 不可用"}):
            self.assertEqual("finished", run_multi_case.finalize_suite_status(suite))
