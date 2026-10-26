"""Tests for the multi-case coordinator's scheduling contract.

These tests do not start a provider CLI.  Formal behavior still belongs to
the existing per-case runner and its immutable run evidence.
"""
from __future__ import annotations

import hashlib
import json
import os
import unittest
import subprocess
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


class MultiCasePlanTest(unittest.TestCase):
    def test_selected_suite_uses_exact_dynamic_case_set(self) -> None:
        selected = sorted(path.name for path in run_multi_case.CASES_ROOT.iterdir()
                          if path.is_dir() and (path / "case.yaml").is_file())
        plans = run_multi_case.select_cases(selected, all_cases=False)
        self.assertEqual(selected, [plan.case_id for plan in plans])
        self.assertEqual(len(plans), len({plan.feature for plan in plans}))


#: 终点观测：一个可施工的施工单位，spec 已闭环、plan 还没闭环
AT_PLAN = {"end_at": "phase:plan", "units": [{"change_unit_id": "cu1", "design": "constructable", "phases": {
    "spec": {"state": "closed", "missing": []}, "plan": {"state": "open", "missing": ["完成回执"]}}}]}


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

    def register(self) -> None:
        flow = self.root / f"doc/features/{self.feature}/AR/story-src/story-flow.json"
        flow.parent.mkdir(parents=True)
        flow.write_text(json.dumps({"status": "story_written"}), encoding="utf-8")

    def test_native_observation_moves_the_phase(self) -> None:
        """需求登记成文、终点观测列出施工单位之后，阶段是所有施工单位里最早还没闭环的那个。"""
        self.register()
        record = {**self.record(), "closure": AT_PLAN}
        changes = run_multi_case.reconcile_record_phase(record)
        self.assertEqual("plan", record["current_phase"])
        self.assertEqual("plan", record["highest_phase_reached"])
        self.assertEqual("flow_and_native_observation", record["phase_source"])
        self.assertIn("current_phase", changes)
        self.assertTrue(record["story_done_at"])

    def test_waiting_for_units_is_design_handoff(self) -> None:
        self.register()
        record = {**self.record(), "closure": {"end_at": "phase:plan", "units": []}}
        run_multi_case.reconcile_record_phase(record)
        self.assertEqual("design_handoff", record["current_phase"])
        record["closure"] = {"end_at": "story", "units": []}
        run_multi_case.reconcile_record_phase(record)
        self.assertEqual("story", record["current_phase"], "终点是 story 时不往施工推")

    def test_a_phase_directory_or_the_global_slot_alone_does_not_advance(self) -> None:
        """目录出现、全局阶段槽写着 spec，都不是阶段证据。"""
        artifact = self.root / f"doc/features/{self.feature}/spec/spec.md"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("# spec", encoding="utf-8")
        self.write_current_phase("spec")
        record = self.record()
        run_multi_case.reconcile_record_phase(record)
        self.assertEqual("story", record["current_phase"])
        self.assertFalse(record.get("story_done_at"))

    def test_model_prose_does_not_change_phase(self) -> None:
        record = self.record()
        record["last_model_text"] = "已经进入 /spec 并读取 Spec Skill"
        run_multi_case.reconcile_record_phase(record)
        self.assertEqual("story", record["current_phase"])

    def test_highest_phase_never_regresses(self) -> None:
        record = self.record()
        record.update({"current_phase": "plan", "last_phase": "plan",
                       "highest_phase_reached": "plan",
                       "story_done_at": "2026-08-22T03:00:00Z",
                       "closure": {"end_at": "phase:plan", "units": [
                           {"design": "constructable", "phases": {"spec": {"state": "open"}}}]}})
        run_multi_case.reconcile_record_phase(record)
        self.assertEqual("spec", record["current_phase"])
        self.assertEqual("plan", record["highest_phase_reached"])
        self.assertEqual("2026-08-22T03:00:00Z", record["story_done_at"])


class SuiteFeatureArchiveTest(unittest.TestCase):
    """起跑前把回流根下的需求目录归档进 doc/features/archive/<批次>/；archive 自身、spec/plan/release 不动。"""

    def maintenance_doc(self) -> Path:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        doc = root / "repo" / "doc"
        (doc / "spec/1.9.8").mkdir(parents=True)
        (doc / "spec/1.9.8/00.md").write_text("需求", encoding="utf-8")
        for name, value in (("DOC_ROOT", doc), ("FEATURES_ROOT", doc / "features")):
            self.addCleanup(setattr, run_multi_case, name, getattr(run_multi_case, name))
            setattr(run_multi_case, name, value)
        return doc

    def test_current_features_move_into_a_new_batch_and_history_stays(self) -> None:
        doc = self.maintenance_doc()
        features = doc / "features"
        (features / "AR1").mkdir(parents=True)
        (features / "AR2").mkdir()
        (features / "AR1/story.md").write_text("one", encoding="utf-8")
        (features / "archive/Story-Features-20260101-000000/AR0").mkdir(parents=True)

        result = run_multi_case.migrate_existing_features(doc.parent / "suite-1")

        destination = Path(result["destination_root"])
        self.assertEqual("completed", result["status"])
        self.assertRegex(destination.name, r"^Story-Features-\d{8}-\d{6}")
        self.assertEqual((features / "archive").resolve(), destination.parent)
        self.assertTrue((destination / "AR1/story.md").is_file())
        self.assertTrue((destination / "AR2").is_dir())
        self.assertEqual(["archive"], [p.name for p in features.iterdir()])
        self.assertTrue((features / "archive/Story-Features-20260101-000000/AR0").is_dir(), "上一批历史被动了")
        self.assertEqual("需求", (doc / "spec/1.9.8/00.md").read_text(encoding="utf-8"))

    def test_only_archive_means_nothing_to_archive(self) -> None:
        doc = self.maintenance_doc()
        (doc / "features/archive/Story-Features-20260101-000000/AR0").mkdir(parents=True)

        result = run_multi_case.migrate_existing_features(doc.parent / "suite-1")

        self.assertEqual("no_existing_features", result["status"])
        self.assertIsNone(result["destination_root"])
        self.assertEqual(["Story-Features-20260101-000000"],
                         [p.name for p in (doc / "features/archive").iterdir()], "不该建空批次")

    def test_empty_features_does_not_create_archive_directory(self) -> None:
        doc = self.maintenance_doc()
        (doc / "features").mkdir()

        result = run_multi_case.migrate_existing_features(doc.parent / "suite-1")

        self.assertEqual("no_existing_features", result["status"])
        self.assertFalse((doc / "features/archive").exists())

    def test_archive_in_other_case_is_the_same_reserved_directory(self) -> None:
        """Archive 与 archive 在 Windows 上是同一个目录：跳过它，新批次也放进它。"""
        doc = self.maintenance_doc()
        features = doc / "features"
        (features / "Archive/Story-Features-20260101-000000").mkdir(parents=True)
        (features / "AR1").mkdir()

        result = run_multi_case.migrate_existing_features(doc.parent / "suite-1")

        self.assertEqual("completed", result["status"])
        self.assertEqual("Archive", Path(result["destination_root"]).parent.name)
        self.assertEqual(["Archive"], [p.name for p in features.iterdir()])

    def test_a_batch_name_already_taken_gets_a_suffix(self) -> None:
        doc = self.maintenance_doc()
        features = doc / "features"
        self.addCleanup(setattr, run_multi_case, "FEATURE_ARCHIVE_TIMESTAMP_FORMAT",
                        run_multi_case.FEATURE_ARCHIVE_TIMESTAMP_FORMAT)
        run_multi_case.FEATURE_ARCHIVE_TIMESTAMP_FORMAT = "fixed"
        (features / "archive/Story-Features-fixed/AR0").mkdir(parents=True)
        (features / "AR1").mkdir()

        result = run_multi_case.migrate_existing_features(doc.parent / "suite-1")

        self.assertEqual("Story-Features-fixed-suite-1", Path(result["destination_root"]).name)
        self.assertTrue((features / "archive/Story-Features-fixed/AR0").is_dir(), "重名批次被覆盖")

    def test_unexpected_files_stay_and_are_reported(self) -> None:
        doc = self.maintenance_doc()
        features = doc / "features"
        (features / "AR1").mkdir(parents=True)
        (features / "notes.txt").write_text("不是需求", encoding="utf-8")

        result = run_multi_case.migrate_existing_features(doc.parent / "suite-1")

        self.assertEqual(["notes.txt"], result["kept_unexpected"])
        self.assertEqual("不是需求", (features / "notes.txt").read_text(encoding="utf-8"))
        self.assertFalse((Path(result["destination_root"]) / "notes.txt").exists())

    def test_a_root_other_than_doc_features_is_refused(self) -> None:
        """回流根指错到 doc 本身时，spec/plan/release 会被当成产物搬走——拒绝，一个文件都不动。"""
        doc = self.maintenance_doc()
        run_multi_case.FEATURES_ROOT = doc
        with self.assertRaises(SystemExit) as caught:
            run_multi_case.migrate_existing_features(doc.parent / "suite-1")
        self.assertIn("spec、plan、release", str(caught.exception))
        self.assertTrue((doc / "spec/1.9.8/00.md").is_file())
        self.assertFalse((doc / "archive").exists())

    def test_a_case_whose_feature_is_the_reserved_name_is_refused_before_start(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        (root / "c1").mkdir()
        (root / "c1/case.yaml").write_text("id: c1\nar: Archive\n", encoding="utf-8")
        self.addCleanup(setattr, run_multi_case, "CASES_ROOT", run_multi_case.CASES_ROOT)
        run_multi_case.CASES_ROOT = root
        with self.assertRaises(SystemExit) as caught:
            run_multi_case.load_case_plan("c1")
        self.assertIn("doc/features/archive", str(caught.exception))


class MultiCasePlanContinuationTest(unittest.TestCase):

    PLAN = run_multi_case.CasePlan("c1", "AR-1", "story", {"kind": "story", "delivery": "local"}, False, ())

    def test_an_override_is_recorded_beside_the_case_value(self) -> None:
        """命令行覆盖记在 requested_end_at，实际终点记 effective_end_at，end_at 仍回显 Case 配置原值。"""
        plain = run_multi_case.new_case_record(self.PLAN)
        self.assertEqual((None, "story:local", "story:local", []),
                         (plain["requested_end_at"], plain["effective_end_at"], plain["end_at"], plain["effective_phase_scope"]))
        moved = run_multi_case.new_case_record(self.PLAN, "phase:plan")
        self.assertEqual(("phase:plan", "phase:plan", "story:local", ["spec", "plan"]),
                         (moved["requested_end_at"], moved["effective_end_at"], moved["end_at"], moved["effective_phase_scope"]))

    def test_the_continued_case_gets_its_own_end(self) -> None:
        other = run_multi_case.CasePlan("c2", "AR-2", "story", {"kind": "story", "delivery": "local"}, False, ())
        self.assertEqual("phase:plan", run_multi_case.requested_end_at(self.PLAN, "blueprint", "c1", "phase:plan"))
        self.assertEqual("blueprint", run_multi_case.requested_end_at(other, "blueprint", "c1", "phase:plan"))
        self.assertIsNone(run_multi_case.requested_end_at(other, None, "c1", "phase:plan"))

    def test_bad_overrides_are_refused_before_anything_starts(self) -> None:
        plans = [self.PLAN]
        for args in (("phase", None, None), ("spec", None, None), (None, "c1", None),
                     (None, "c1", "phase:codeing"), (None, "nobody", "story")):
            with self.subTest(args=args), self.assertRaises(SystemExit):
                run_multi_case.validate_phase_overrides(*args, plans)
        run_multi_case.validate_phase_overrides("design_handoff", "c1", "phase:plan", plans)

    def test_all_case_definitions_are_loaded_without_new_schema(self) -> None:
        case_ids = sorted(path.name for path in run_multi_case.CASES_ROOT.iterdir()
                          if path.is_dir() and (path / "case.yaml").is_file())
        plans = [run_multi_case.load_case_plan(case_id) for case_id in case_ids]
        self.assertEqual(len(case_ids), len(plans))
        self.assertEqual(len(plans), len({plan.feature for plan in plans}))
        for plan in plans:
            self.assertIn(plan.start_phase, run_multi_case.VALID_START)
            self.assertIn(plan.end_at["kind"], ("story", "blueprint", "design_handoff", "phase"))
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
                       "requested_end_at": None, "start_history": []})
        record["workspace"] = tempfile.mkdtemp()   # 工作区已备好，本例只测重试计数
        suite = self.suite(record)
        suite.update({"bundle_root": tempfile.mkdtemp()})
        failed = (1, None, "", "lock busy")
        try:
            with mock.patch.object(run_multi_case, "invoke_case", return_value=failed), \
                    mock.patch.object(run_multi_case, "ensure_case_git", return_value={"status": "ready"}), \
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
                       "requested_end_at": None, "start_history": []})
        record["workspace"] = tempfile.mkdtemp()   # 同上：本例测的是丢响应后的认领
        suite = self.suite(record)
        suite.update({"bundle_root": tempfile.mkdtemp()})
        try:
            with mock.patch.object(run_multi_case, "invoke_case",
                                   return_value=(1, None, "", "response lost")), \
                    mock.patch.object(run_multi_case, "ensure_case_git", return_value={"status": "ready"}), \
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
            "current_phase": "story",
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

    def test_a_step_for_another_phase_is_not_shown(self) -> None:
        """当前阶段未知、条目要的前提（已归档）不成立：只作 phase_ready 为假的候选，不能当 planned 提交。
        判据仍是「装置一个字都没发出去」，指针也不动。
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
            self.assertEqual([("review", False)], [(c["id"], c["phase_ready"]) for c in request["candidate_steps"]])
            self.assertEqual("候选，需按完整问题核立场", request["plan_note"])
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
        record["last_phase"] = "plan"
        record["story_done_at"] = "2026-08-22T00:00:00+08:00"
        record["closure"] = AT_PLAN
        suite["automation_stability"] = {
            "required_confirmations": 2, "consecutive_confirmations": 2,
            "ready_at": "2026-08-22T00:00:30+08:00",
        }
        payload["run"]["last_phase"] = "plan"
        with mock.patch.object(run_multi_case, "invoke_case",
                               return_value=(0, payload, "", "")):
            result = run_multi_case.poll_one(record, 15, 1000, suite)
        self.assertEqual(120, result["observation_cadence_sec"])

    def test_mixed_story_and_spec_suite_stays_on_fifteen_seconds(self) -> None:
        story = self.record("case-alpha-fixture", "AR-ALPHA", "running")
        story["last_phase"] = "story"
        spec = self.record("case-beta-fixture", "ISSUE-BETA", "running")
        spec["last_phase"] = "plan"
        spec["story_done_at"] = "2026-08-22T00:00:00+08:00"
        suite = self.suite(story, spec)
        suite["automation_stability"] = {"ready_at": None}
        self.assertFalse(run_multi_case.suite_automation_ready(suite))
        story["last_phase"] = "plan"
        story["story_done_at"] = "2026-08-22T00:00:00+08:00"
        self.assertFalse(run_multi_case.suite_automation_ready(suite))

    def test_two_complete_spec_rounds_are_required_and_regression_resets(self) -> None:
        first = self.record("case-alpha-fixture", "AR-ALPHA", "running")
        second = self.record("case-beta-fixture", "ISSUE-BETA", "running")
        for record in (first, second):
            record.update({"last_phase": "plan", "story_done_at": "entered"})
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
        record.update({"last_phase": "plan", "story_done_at": "entered"})
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
        record.update({"last_phase": "plan", "story_done_at": "entered",
                       "interaction_state": "complete",
                       "last_reply_status": "accepted"})
        changes = run_multi_case.progress_changes(before, suite, [{
            "name": "adaptive_reply_required", "case": "arbitrary-case"}])
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


class TheReplyLandsOnTheQuestionTheHostSaw(unittest.TestCase):
    """回复由宿主指明目标（run、turn）：完整问题可得、候选只按阶段与类型列、一次回答可覆盖多条、
    重入幂等、换了问题不落、失败不消费。"""

    SCRIPT = [
        {"id": "scope", "text": "不拆单。", "expected_turn": 1, "expected_kind": "story_gate",
         "expected_phase": "story", "deliver": []},
        {"id": "priority", "text": "先做签约。", "expected_turn": 2, "expected_kind": "story_gate",
         "expected_phase": "story", "deliver": []},
        {"id": "later", "text": "进 plan。", "expected_turn": 3, "expected_kind": "story_gate",
         "expected_phase": "spec", "deliver": []},
    ]

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.record = {"case": "c", "feature": "AR-1", "status": run_multi_case.WAITING_STATUS, "run_id": "run-1",
                       "current_phase": "story", "interaction_script": [dict(s) for s in self.SCRIPT],
                       "answered_steps": [], "interaction_index": 0, "supplements": [],
                       "last_awaiting": {"turn": 4, "kind": "story_gate", "prompt": "范围怎么定？先做哪个？"}}
        self.suite = {"bundle_root": self._tmp.name, "case_states": {"c": self.record}, "events": []}
        self.sent: list[tuple] = []
        self.answer: tuple = (0, {"ok": True, "delivered": []}, "", "")

    def fake_invoke(self, case_id, command, *args, suite=None):
        self.sent.append(args)
        return self.answer

    def reply(self, text: str = "不拆单，先做签约。", steps: tuple = ("scope", "priority"),
              kind: str = "planned", run: str = "run-1", turn: str = "4") -> tuple[int, dict]:
        with mock.patch.object(run_multi_case, "load_suite", return_value=(Path(self._tmp.name), self.suite)), \
                mock.patch.object(run_multi_case, "refresh_record", side_effect=lambda r: r), \
                mock.patch.object(run_multi_case, "save_suite"), \
                mock.patch.object(run_multi_case, "invoke_case", self.fake_invoke), \
                mock.patch("builtins.print") as printed:
            code = run_multi_case.command_reply("s", "c", text, "adaptive", "", [], list(steps), kind, run, turn)
        return code, json.loads(printed.call_args.args[0])

    def request(self) -> dict:
        with mock.patch.object(run_multi_case, "append_event"), \
                mock.patch.object(run_multi_case, "append_case_observation"):
            run_multi_case.request_host_reply(self.record, self.suite)
        return self.record["last_adaptive_request"]

    def observations(self) -> list[dict]:
        path = Path(self._tmp.name) / "cases" / "c" / "observations.jsonl"
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []

    def test_a_long_question_is_given_whole(self) -> None:
        self.record["last_awaiting"]["prompt"] = "长" * 3000
        got = self.request()
        self.assertEqual(3000, len(got["model_prompt"]))
        self.assertEqual((1200, True), (len(got["question"]), got["question_truncated"]))
        self.assertEqual(("run-1", 4), (got["run_id"], got["turn"]))

    def test_same_phase_steps_are_only_candidates(self) -> None:
        got = self.request()
        self.assertEqual([("scope", True), ("priority", True)], [(c["id"], c["phase_ready"]) for c in got["candidate_steps"]])
        self.assertEqual({"id", "text", "deliver", "expected_kind", "expected_phase", "phase_ready"},
                         set(got["candidate_steps"][0]))
        self.assertEqual(("scope", "候选，需按完整问题核立场"), (got["planned_step_id"], got["plan_note"]))

    def test_one_reply_covers_two_steps_and_keeps_the_unasked_one(self) -> None:
        code, _ = self.reply()
        self.assertEqual(0, code)
        self.assertEqual((["scope", "priority"], 2), (self.record["answered_steps"], self.record["interaction_index"]))
        args = self.sent[0]
        self.assertEqual(("run-1", "4"), (args[args.index("--run-id") + 1], args[args.index("--turn") + 1]))
        seen = self.observations()[-1]
        self.assertEqual(("run-1", "4", ["priority", "scope"], "accepted"),
                         (seen["run_id"], seen["turn"], seen["covered_steps"], seen["result"]))
        self.record["last_awaiting"] = {"turn": 5, "kind": "story_gate", "prompt": "再确认一次范围？"}
        self.assertEqual(0, self.reply("还是不拆单。", ("scope",), turn="5")[0])
        self.assertEqual(["scope", "priority"], self.record["answered_steps"], "再次确认同一立场重复计入了")

    def test_bad_input_and_stale_targets_fail_before_sending(self) -> None:
        cases = {"重复 step": dict(steps=("scope", "scope")), "未知 step": dict(steps=("nope",)),
                 "planned 不带 step": dict(steps=()), "answered 带 step": dict(kind="answered"),
                 "阶段不成立": dict(steps=("later",)), "旧 turn": dict(turn="3"), "别的 run": dict(run="run-0")}
        for label, kw in cases.items():
            with self.subTest(case=label):
                code, out = self.reply(**kw)
                self.assertEqual((1, False), (code, out["ok"]))
        self.assertEqual([], self.sent, "预检失败仍发了")
        self.assertEqual([], self.record["answered_steps"])

    def test_a_retry_of_an_answered_turn_returns_the_old_result(self) -> None:
        self.assertEqual(0, self.reply()[0])
        self.record.update(status="running", last_awaiting={"turn": 5, "kind": "story_gate", "prompt": "下一问"})
        code, out = self.reply()
        self.assertEqual((0, True), (code, out.get("already_sent")))
        self.assertEqual(1, len(self.sent), "同一问同样的话又发了一次")
        code, out = self.reply("改主意了，拆单。")
        self.assertEqual((1, False), (code, out["ok"]))
        self.assertEqual(1, len(self.sent))

    def test_a_retry_after_the_phase_moved_on_still_returns_the_old_result(self) -> None:
        """F2：回复成功后已进入别的阶段、在等别的类型：同一请求重试返回原结果，不按新阶段拒绝，也不再发。"""
        self.assertEqual(0, self.reply()[0])
        self.record.update(status="running", current_phase="spec",
                           last_awaiting={"turn": 6, "kind": "spec_gate", "prompt": "进下一阶段？"})
        code, out = self.reply()
        self.assertEqual((0, True), (code, out.get("already_sent")), out)
        self.assertEqual(1, len(self.sent), "重试又发了一次")
        self.assertEqual((1, False), (self.reply(steps=("scope", "scope"))[0], False), "重入也要先过参数形态")

    def test_an_old_reply_never_lands_on_the_next_question(self) -> None:
        self.record["last_awaiting"] = {"turn": 5, "kind": "story_gate", "prompt": "下一问"}
        code, out = self.reply(turn="4")
        self.assertEqual(1, code)
        self.assertIn("不是当前在等的那一问", out["error"])
        self.assertEqual([], self.sent)

    def test_a_failed_or_unknown_send_consumes_nothing(self) -> None:
        self.answer = (1, {"ok": False, "error": "目标已换"}, "", "")
        self.assertEqual(1, self.reply()[0])
        self.answer = (1, None, "", "崩了")
        code, out = self.reply()
        self.assertEqual(("unknown", 1), (out["result"], code))
        self.assertIn("不自动重发", out["note"])
        self.assertEqual([], self.record["answered_steps"])
        self.assertEqual(["refused", "unknown"], [o["result"] for o in self.observations()])

    def test_a_neutral_reply_without_a_plan_goes_through(self) -> None:
        self.record["interaction_script"] = []
        self.assertEqual(0, self.reply("继续。", (), "neutral")[0])
        self.assertEqual(([], 0), (self.record["answered_steps"], self.record["interaction_index"]))


class WorkspaceBoundaryTest(unittest.TestCase):
    def test_next_suite_clears_every_old_scene_under_sw_story(self) -> None:
        """旧 suite 工作区、离线模板、别的名字的临时现场都删；suite 的需求系统副本按同一工作区根算出确切位置删，
        同前缀的别的副本不动；output 下的运行证据保留。"""
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
            others = [temp_root / "sw-story" / name for name in ("offline-20261021-100544", "s2-replay")]
            for other in others:
                (other / "workspace-template").mkdir(parents=True)
            run_multi_case.OUT_ROOT = output_root
            tempfile.gettempdir = lambda: str(temp_root)
            system = run_multi_case.requirement_system_root(old_workspace)
            (system / "case-a").mkdir(parents=True)
            stranger = system.with_name(system.name + "0")
            stranger.mkdir()
            with mock.patch.object(run_multi_case, "_process_inventory",
                                   return_value=(True, [], None)):
                report = run_multi_case.cleanup_previous_test_runs(
                    new_output, "story-suite-new")
            self.assertEqual("completed", report["status"])
            self.assertFalse(old_workspace.exists())
            self.assertFalse(any(other.exists() for other in others), "没登记、名字不像 suite 的临时现场没清")
            self.assertFalse(system.exists(), "suite 的需求系统副本没随工作区删")
            self.assertTrue(stranger.is_dir(), "按前缀带删了别的需求系统副本")
            self.assertTrue((old_output / "suite.json").is_file(), "删了 output 下的运行证据")
            self.assertTrue(new_output.exists())
        finally:
            run_multi_case.OUT_ROOT = original_out
            tempfile.gettempdir = original_gettempdir
            shutil.rmtree(root, ignore_errors=True)

    def test_a_link_out_of_sw_story_stops_the_cleanup_and_its_target_is_kept(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="story-cleanup-link-"))
        self.addCleanup(shutil.rmtree, root, True)
        outside, sw, new_output = root / "elsewhere", root / "temp/sw-story", root / "output/story/story-suite-new"
        for path in (outside, sw, new_output):
            path.mkdir(parents=True)
        (outside / "keep.txt").write_text("keep", encoding="utf-8")
        if os.name == "nt":
            made = subprocess.run(["cmd", "/c", "mklink", "/J", str(sw / "linked"), str(outside)],
                                  capture_output=True, text=True)
            if made.returncode:
                self.skipTest(f"建不了目录联接：{made.stderr}")
        else:
            (sw / "linked").symlink_to(outside, target_is_directory=True)
        with mock.patch.object(run_multi_case, "OUT_ROOT", root / "output/story"), \
                mock.patch.object(tempfile, "gettempdir", return_value=str(root / "temp")), \
                mock.patch.object(run_multi_case, "_process_inventory", return_value=(True, [], None)), \
                self.assertRaises(SystemExit):
            run_multi_case.cleanup_previous_test_runs(new_output, "story-suite-new")
        report = run_multi_case.read_json(new_output / "previous-run-cleanup.json", {})
        self.assertEqual("blocked_path_boundary", report["targets"][0]["status"])
        self.assertEqual("keep", (outside / "keep.txt").read_text(encoding="utf-8"))

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
            old_workspace = root / "temp/sw-story/story-suite-old"
            old_output.mkdir(parents=True)
            new_output.mkdir(parents=True)
            old_workspace.mkdir(parents=True)
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
                        return_value={"removed": False, "error": "OSError: residual snapshot",
                                      "remaining": ["a/b"],
                                      "attempts": [{"attempt": 1, "status": "retry",
                                                    "error": "OSError: residual snapshot"}]}):
                report = run_multi_case.cleanup_previous_test_runs(
                    new_output, "story-suite-new")
            self.assertEqual("completed_with_warnings", report["status"])
            self.assertEqual(1, len(report["warnings"]))
            kept = report["targets"][0]["deletion_attempts"][0]
            self.assertEqual((False, ["a/b"], 1), (kept["removed"], kept["remaining"], len(kept["attempts"])),
                             "失败时的尝试记录没进清理报告")
            self.assertTrue(old_workspace.exists())
            self.assertTrue(new_output.exists())
        finally:
            run_multi_case.OUT_ROOT = original_out
            tempfile.gettempdir = original_gettempdir
            shutil.rmtree(root, ignore_errors=True)

    def test_status_lists_each_turn_with_its_runtime_record(self) -> None:
        """status 的运行视图从已有记录派生：回合来自 cli_run_started，会话与状态来自 run.json；缺的如实标。"""
        root = Path(tempfile.mkdtemp(prefix="story-run-view-"))
        self.addCleanup(shutil.rmtree, root, True)
        run_dir = root / "run-1"
        (run_dir / "cli-runtime" / "r1").mkdir(parents=True)
        (run_dir / "live.jsonl").write_text(
            '{"seq": 1, "type": "cli_run_started", "cli_run_id": "r1", "turn": 1}\n'
            '{"seq": 2, "type": "text"}\n'
            '{"seq": 3, "type": "cli_run_started", "cli_run_id": "r2", "turn": 2}\n', encoding="utf-8")
        run_multi_case.write_json(run_dir / "cli-runtime" / "r1" / "run.json",
                                  {"session_id": "s-1", "status": "succeeded"})
        with mock.patch.object(run_multi_case, "run_pointer_state",
                               return_value={"run_dir": str(run_dir), "cli_run_id": "r2"}):
            view = run_multi_case.run_view({"case": "c", "run_id": "run-1"})
        self.assertEqual([(1, "r1", "succeeded", "s-1"), (2, "r2", "runtime_record_missing", None)],
                         [(r["turn"], r["runtime_id"], r["status"], r.get("session_id")) for r in view["cli_runs"]])
        self.assertEqual((str(run_dir), "r2"), (view["run_dir"], view["cli_run_id"]))

    def test_the_default_suite_name_is_dated_and_suffixed_on_collision(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="story-suite-name-"))
        self.addCleanup(shutil.rmtree, root, True)
        at = datetime(2026, 10, 20, 9, 17, 31)
        with mock.patch.object(run_multi_case, "SUITES_ROOT", root):
            first = run_multi_case.default_suite_id(at)
            (root / first).mkdir()
            second = run_multi_case.default_suite_id(at)
            (root / second).mkdir()
            third = run_multi_case.default_suite_id(at)
        self.assertEqual(("story-suite-20261020-091731", "story-suite-20261020-091731-01",
                          "story-suite-20261020-091731-02"), (first, second, third))

    def test_a_failed_delete_returns_every_attempt_instead_of_raising(self) -> None:
        """删不掉时不抛异常带走记录：每次尝试与剩余路径都回给调用方，removed 以目录确实不在为准。"""
        root = Path(tempfile.mkdtemp(prefix="story-rm-"))
        self.addCleanup(shutil.rmtree, root, True)
        (root / "tree" / "sub").mkdir(parents=True)
        (root / "tree" / "sub" / "f.txt").write_text("x", encoding="utf-8")
        with mock.patch.object(run_multi_case, "_process_inventory", return_value=(True, [], None)), \
                mock.patch.object(run_multi_case.shutil, "rmtree", side_effect=OSError(145, "目录不是空的")), \
                mock.patch.object(run_multi_case.time, "sleep"):
            outcome = run_multi_case._remove_tree_with_recovery(root / "tree", attempts=3)
        self.assertFalse(outcome["removed"])
        self.assertEqual(["retry"] * 3, [a["status"] for a in outcome["attempts"]])
        self.assertIn("目录不是空的", outcome["error"])
        self.assertIn(str(Path("sub") / "f.txt"), outcome["remaining"])
        with mock.patch.object(run_multi_case, "_process_inventory", return_value=(True, [], None)):
            done = run_multi_case._remove_tree_with_recovery(root / "tree")
        self.assertEqual((True, [], None), (done["removed"], done["remaining"], done["error"]))

    def _deep_tree(self, root: Path) -> tuple[Path, Path]:
        """一棵叶子路径超过 300 字符的树（用长路径前缀建，普通路径够不着叶子）。"""
        tree = root / "tree"
        leaf = tree.joinpath(*[ch * 60 for ch in "abcde"])
        run_multi_case._long(leaf).mkdir(parents=True)
        (run_multi_case._long(leaf) / "f.txt").write_text("x", encoding="utf-8")
        self.assertGreater(len(str(leaf / "f.txt")), 300)
        return tree, leaf

    def test_a_long_tree_is_really_deleted(self) -> None:
        """355 字符级的深树：普通路径删到叶子报「目录不是空的」，走长路径前缀后确实删掉。"""
        root = Path(tempfile.mkdtemp(prefix="story-rm-long-"))
        self.addCleanup(shutil.rmtree, run_multi_case._long(root), True)
        tree, _ = self._deep_tree(root)
        with mock.patch.object(run_multi_case, "_process_inventory", return_value=(True, [], None)):
            out = run_multi_case._remove_tree_with_recovery(tree)
        self.assertEqual((True, None), (out["removed"], out["error"]), out)
        self.assertFalse(run_multi_case._long(tree).exists())

    def test_read_only_and_busy_files_and_retry_after_release(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="story-rm-busy-"))
        self.addCleanup(shutil.rmtree, run_multi_case._long(root), True)
        tree, leaf = self._deep_tree(root)
        locked = run_multi_case._long(leaf) / "f.txt"
        os.chmod(locked, 0o400)
        if os.name == "nt":
            handle = open(locked, "rb")  # noqa: SIM115 —— Windows 上打开着的文件删不掉，模拟被占用
            with mock.patch.object(run_multi_case, "_process_inventory", return_value=(True, [], None)), \
                    mock.patch.object(run_multi_case.time, "sleep"):
                busy = run_multi_case._remove_tree_with_recovery(tree, attempts=2)
            self.assertFalse(busy["removed"])
            self.assertEqual(["retry", "retry"], [a["status"] for a in busy["attempts"]])
            self.assertTrue(busy["remaining"], "残留路径没留下")
            handle.close()
        with mock.patch.object(run_multi_case, "_process_inventory", return_value=(True, [], None)):
            done = run_multi_case._remove_tree_with_recovery(tree)
        self.assertEqual((True, None), (done["removed"], done["error"]), "只读件或半删后的重试没删干净")

    def test_a_link_inside_the_tree_does_not_reach_its_target(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="story-rm-link-"))
        self.addCleanup(shutil.rmtree, root, True)
        outside = root / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_text("keep", encoding="utf-8")
        tree = root / "tree"
        tree.mkdir()
        if os.name == "nt":
            made = subprocess.run(["cmd", "/c", "mklink", "/J", str(tree / "link"), str(outside)],
                                  capture_output=True, text=True)
            if made.returncode:
                self.skipTest(f"建不了目录联接：{made.stderr}")
        else:
            (tree / "link").symlink_to(outside, target_is_directory=True)
        with mock.patch.object(run_multi_case, "_process_inventory", return_value=(True, [], None)):
            out = run_multi_case._remove_tree_with_recovery(tree)
        self.assertTrue(out["removed"], out)
        self.assertEqual("keep", (outside / "keep.txt").read_text(encoding="utf-8"), "删树时穿过链接删了外部目录")

    def test_an_unreadable_process_list_blocks_the_delete(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="story-rm-inv-"))
        self.addCleanup(shutil.rmtree, root, True)
        (root / "tree").mkdir()
        with mock.patch.object(run_multi_case, "_process_inventory", return_value=(False, [], "枚举失败")):
            out = run_multi_case._remove_tree_with_recovery(root / "tree")
        self.assertEqual((False, "blocked_process_recheck"), (out["removed"], out["attempts"][0]["status"]))
        self.assertTrue((root / "tree").exists())

    def test_one_failed_target_does_not_stop_the_others(self) -> None:
        """一处删除失败留证、记 warning，其它可删的旧现场照删，新 suite 的起跑不被拦。"""
        root = Path(tempfile.mkdtemp(prefix="story-cleanup-mixed-"))
        self.addCleanup(shutil.rmtree, root, True)
        output_root, sw = root / "output/story", root / "temp/sw-story"
        (output_root / "story-suite-new").mkdir(parents=True)
        for name in ("story-suite-old1", "story-suite-old2"):
            (sw / name).mkdir(parents=True)
        real = run_multi_case._remove_tree_with_recovery

        def remove(path: Path, **kw):
            if "old1" in str(path):
                return {"removed": False, "error": "OSError: 注入的删除失败", "remaining": ["x"],
                        "attempts": [{"attempt": 1, "status": "retry", "error": "OSError: 注入的删除失败"}]}
            return real(path, **kw)
        with mock.patch.object(run_multi_case, "OUT_ROOT", output_root), \
                mock.patch.object(tempfile, "gettempdir", return_value=str(root / "temp")), \
                mock.patch.object(run_multi_case, "_process_inventory", return_value=(True, [], None)), \
                mock.patch.object(run_multi_case, "_remove_tree_with_recovery", side_effect=remove):
            report = run_multi_case.cleanup_previous_test_runs(output_root / "story-suite-new", "story-suite-new")
        self.assertEqual("completed_with_warnings", report["status"])
        self.assertTrue((sw / "story-suite-old1").exists(), "删除失败的现场被当成清掉了")
        self.assertFalse((sw / "story-suite-old2").exists(), "一处失败拦住了其它可删的旧现场")
        self.assertEqual(1, len(report["warnings"]))
        self.assertIn("old1", report["warnings"][0])

    def _seed_workspace(self, materialized: list[str]) -> tuple[dict, dict, Path]:
        root = Path(tempfile.mkdtemp(prefix="story-seed-"))
        self.addCleanup(shutil.rmtree, root, True)
        ws = root / "ws"
        for name in materialized:
            (ws / "framework" / "agents" / name).mkdir(parents=True)
            (ws / "framework" / "agents" / name / "adapter.yaml").write_text(f"adapter_name: {name}\n", encoding="utf-8")
        (ws / "framework" / "harness").mkdir(parents=True, exist_ok=True)
        run_multi_case.write_json(ws / "framework.config.json", {"materialized_adapters": materialized})
        (root / "suite").mkdir()
        return {"bundle_root": str(root / "suite")}, {"case": "c1", "workspace": str(ws)}, root

    def test_the_known_cli_is_seeded_as_the_active_adapter(self) -> None:
        """已选 CLI 有同名已物化 adapter：走 Framework 的 --select-adapter，只对这个隔离工程，结果进起跑记录。"""
        suite, case, root = self._seed_workspace(["generic", "dsh", "opencode"])
        done = subprocess.CompletedProcess([], 0, stdout='{"ok": true, "code": "ok", "activeAdapter": "dsh"}', stderr="")
        with mock.patch.object(run_multi_case.subprocess, "run", return_value=done) as run:
            seed = run_multi_case.seed_agent_adapter(suite, case, "dsh")
        command = run.call_args.args[0]
        self.assertIn("--select-adapter dsh", command)
        self.assertIn(f'--project-root "{case["workspace"]}"', command)
        self.assertEqual(("seeded", "dsh"), (seed["status"], seed["adapter"]))
        boundary = run_multi_case.read_json(root / "suite" / "workspace-boundary.json", {})
        self.assertEqual("seeded", boundary["adapter_seed"]["c1"]["status"])

    def test_an_unmatched_cli_is_a_gap_not_a_guess(self) -> None:
        suite, case, _ = self._seed_workspace(["generic", "cursor"])
        with mock.patch.object(run_multi_case.subprocess, "run") as run:
            seed = run_multi_case.seed_agent_adapter(suite, case, "agent")
        run.assert_not_called()
        self.assertEqual(("unmapped", None), (seed["status"], seed["adapter"]))

    def test_a_refused_selection_is_recorded_as_failed(self) -> None:
        suite, case, _ = self._seed_workspace(["dsh"])
        refused = subprocess.CompletedProcess([], 1, stdout='{"ok": false, "code": "needs_adapter_choice"}', stderr="坏了")
        with mock.patch.object(run_multi_case.subprocess, "run", return_value=refused):
            seed = run_multi_case.seed_agent_adapter(suite, case, "dsh")
        self.assertEqual(("failed", "needs_adapter_choice"), (seed["status"], seed["code"]))

    def _session_file(self, path: Path, rows: list[dict]) -> None:
        """用 Node 内置 zstd 写一个两帧的会话文件（dsh 的 session.v4.jsonl.zstd 就是多帧首尾相接）。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(r, ensure_ascii=False) + "\n" for r in rows]
        script = ("const fs=require('fs'),z=require('zlib');const p=JSON.parse(process.argv[2]);"
                  "fs.writeFileSync(process.argv[1],Buffer.concat(p.map(s=>z.zstdCompressSync(Buffer.from(s)))));")
        halves = ["".join(lines[:1]), "".join(lines[1:])]
        subprocess.run(["node", "-e", script, str(path), json.dumps(halves)], check=True)

    def _native_fixture(self) -> tuple[dict, dict, Path, Path]:
        root = Path(tempfile.mkdtemp(prefix="story-native-"))
        self.addCleanup(shutil.rmtree, root, True)
        ws, run_dir, home = root / "ws", root / "run", root / "dsh"
        ws.mkdir()
        (run_dir / "cli-runtime" / "r1").mkdir(parents=True)
        run_multi_case.write_json(run_dir / "cli-runtime" / "r1" / "run.json", {"cli": "dsh", "session_id": "session-p1"})
        sessions = home / "sessions" / "--ws--"
        self._session_file(sessions / "session-p1" / "session.v4.jsonl.zstd", [
            {"type": "session", "version": 4, "id": "session-p1", "cwd": str(ws)},
            {"type": "subagent/catalog", "data": {"childId": "c1", "label": "审查"}}])
        self._session_file(sessions / "c1" / "session.v4.jsonl.zstd", [
            {"type": "session", "version": 4, "id": "c1", "parentSession": "session-p1", "cwd": str(ws)}])
        return {"bundle_root": str(root)}, {"case": "c", "run_id": "r", "workspace": str(ws)}, run_dir, home

    def _capture(self, suite: dict, record: dict, run_dir: Path, home: Path) -> dict:
        with mock.patch.object(run_multi_case, "run_pointer_state", return_value={"run_dir": str(run_dir)}), \
                mock.patch.dict(os.environ, {"DSH_HOME": str(home)}):
            return run_multi_case.capture_native_sessions(suite, record)

    def test_native_sessions_are_copied_by_their_recorded_id(self) -> None:
        suite, record, run_dir, home = self._native_fixture()
        out = self._capture(suite, record, run_dir, home)
        self.assertEqual("captured", out["status"], out)
        session = out["sessions"][0]
        self.assertEqual((True, 2, None), (session["header_matches"], session["lines"], session["error"]))
        self.assertEqual([("c1", True)], [(c["child_id"], c["parent_matches"]) for c in session["children"]])
        copy = run_dir / "native-sessions" / "session-p1" / "session.v4.jsonl.zstd"
        self.assertEqual((home / "sessions" / "--ws--" / "session-p1" / "session.v4.jsonl.zstd").read_bytes(), copy.read_bytes())
        self.assertTrue((run_dir / "native-sessions" / "manifest.json").is_file())

    def test_missing_ambiguous_or_foreign_sessions_are_reported_not_guessed(self) -> None:
        suite, record, run_dir, home = self._native_fixture()
        shutil.copytree(home / "sessions" / "--ws--" / "c1", home / "sessions" / "--other--" / "c1")
        out = self._capture(suite, record, run_dir, home)
        self.assertEqual("incomplete", out["status"])
        self.assertEqual([("c1", "候选 2 个")], [(x["session_id"], x["reason"]) for x in out["not_captured"]])
        out = self._capture(suite, dict(record, workspace=str(home)), run_dir, home)
        self.assertFalse(out["sessions"][0]["header_matches"], "别的工程的会话被当成本 run 的")
        shutil.rmtree(home / "sessions" / "--ws--" / "session-p1")
        out = self._capture(suite, record, run_dir, home)
        self.assertEqual([("session-p1", "候选 0 个")], [(x["session_id"], x["reason"]) for x in out["not_captured"]])

    def test_a_child_copied_past_the_old_path_limit_is_still_taken(self) -> None:
        """子会话落在 native-sessions/<父>/children/<子>/ 下，正式 suite 目录里这条路径常过 260 字符：照样取得。"""
        suite, record, run_dir, home = self._native_fixture()
        # 运行目录本身约 205 字符（与正式 suite 同量级），只有子会话那一级越过 260
        deep = run_dir.parent / ("x" * max(1, 205 - len(str(run_dir.parent)) - 1))
        shutil.copytree(run_dir, deep)
        self.addCleanup(shutil.rmtree, run_multi_case._long(deep), True)
        out = self._capture(suite, record, deep, home)
        copied = out["sessions"][0]["children"][0]
        self.assertGreater(len(copied["copy"]), 260, "夹具没有越过老上限")
        self.assertEqual(("captured", []), (out["status"], out["not_captured"]), out)
        self.assertEqual((home / "sessions" / "--ws--" / "c1" / "session.v4.jsonl.zstd").read_bytes(),
                         run_multi_case._long(Path(copied["copy"])).read_bytes())

    def test_a_child_that_cannot_be_trusted_makes_the_capture_incomplete(self) -> None:
        """子会话解不开、头部 id 不是 catalog 登记的、parentSession 指向别处：都拷了原字节，但整体不算取得。"""
        child = Path("sessions") / "--ws--" / "c1" / "session.v4.jsonl.zstd"
        cases = {
            "坏 zstd": lambda home: (home / child).write_bytes(b"not zstd"),
            "子头 id 不符": lambda home: self._session_file(home / child, [
                {"type": "session", "version": 4, "id": "c9", "parentSession": "session-p1"}]),
            "parentSession 不符": lambda home: self._session_file(home / child, [
                {"type": "session", "version": 4, "id": "c1", "parentSession": "session-x"}]),
        }
        for name, spoil in cases.items():
            with self.subTest(name):
                suite, record, run_dir, home = self._native_fixture()
                spoil(home)
                out = self._capture(suite, record, run_dir, home)
                self.assertEqual("incomplete", out["status"], out)
                copied = out["sessions"][0]["children"][0]
                self.assertTrue(copied["problems"], copied)
                self.assertEqual((home / child).read_bytes(), Path(copied["copy"]).read_bytes(), "取证失败的原件没留")
                manifest = run_multi_case.read_json(run_dir / "native-sessions" / "manifest.json", {})
                self.assertEqual("incomplete", manifest["status"])

    def test_a_foreign_parent_brings_no_children_and_a_failed_copy_keeps_the_rest(self) -> None:
        suite, record, run_dir, home = self._native_fixture()
        out = self._capture(suite, dict(record, workspace=str(home)), run_dir, home)
        session = out["sessions"][0]
        self.assertEqual(("incomplete", []), (out["status"], session["children"]), "别的工程的 catalog 被当成本 run 的子级来源")
        self.assertTrue((run_dir / "native-sessions" / "session-p1" / "session.v4.jsonl.zstd").is_file())

        suite, record, run_dir, home = self._native_fixture()
        real = run_multi_case._copy_session

        def copy(source: Path, destination: Path) -> dict:
            if source.parent.name == "c1":
                raise PermissionError("被占用（注入）")
            return real(source, destination)

        with mock.patch.object(run_multi_case, "_copy_session", copy):
            out = self._capture(suite, record, run_dir, home)
        self.assertEqual("incomplete", out["status"])
        self.assertEqual(["c1"], [x["session_id"] for x in out["not_captured"]])
        self.assertIn("复制失败", out["not_captured"][0]["reason"])
        self.assertEqual(([], True), (out["sessions"][0]["problems"], out["sessions"][0]["header_matches"]),
                         "子会话复制失败连累了已取得的父会话")

    def test_active_historical_suite_blocks_cleanup_before_delete(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="story-active-"))
        original_out = run_multi_case.OUT_ROOT
        original_gettempdir = tempfile.gettempdir
        try:
            output_root = root / "output/story"
            old_output = output_root / "story-suite-active"
            new_output = output_root / "story-suite-new"
            active_workspace = root / "temp/sw-story/story-suite-active"
            old_output.mkdir(parents=True)
            new_output.mkdir(parents=True)
            active_workspace.mkdir(parents=True)
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
            self.assertTrue(active_workspace.exists())
        finally:
            run_multi_case.OUT_ROOT = original_out
            tempfile.gettempdir = original_gettempdir
            shutil.rmtree(root, ignore_errors=True)

    def test_terminal_case_pid_reuse_does_not_block_cleanup(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="story-terminal-reuse-"))
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
                "case_states": {
                    "case-a": {"worker_pid": 999999, "status": "finished",
                               "started_at": time.time() - 86400},
                },
            })
            run_multi_case.OUT_ROOT = output_root
            tempfile.gettempdir = lambda: str(temp_root)
            with mock.patch.object(run_multi_case, "_pid_alive",
                                   return_value=True), \
                    mock.patch.object(run_multi_case, "_process_inventory",
                                      return_value=(True, [], None)):
                report = run_multi_case.cleanup_previous_test_runs(
                    new_output, "story-suite-new")
            self.assertEqual("completed", report["status"])
            self.assertFalse(old_workspace.exists())
            self.assertTrue(new_output.exists())
        finally:
            run_multi_case.OUT_ROOT = original_out
            tempfile.gettempdir = original_gettempdir
            shutil.rmtree(root, ignore_errors=True)

    def test_non_terminal_case_alive_pid_still_blocks_cleanup(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="story-nonterminal-live-"))
        original_out = run_multi_case.OUT_ROOT
        original_gettempdir = tempfile.gettempdir
        try:
            output_root = root / "output/story"
            old_output = output_root / "story-suite-old"
            new_output = output_root / "story-suite-new"
            live_workspace = root / "temp/sw-story/story-suite-old"
            old_output.mkdir(parents=True)
            new_output.mkdir(parents=True)
            live_workspace.mkdir(parents=True)
            run_multi_case.write_json(old_output / "suite.json", {
                "suite_id": "story-suite-old", "status": "finished",
                "case_states": {
                    "case-a": {"worker_pid": 999999, "status": "running",
                               "started_at": time.time() - 60},
                },
            })
            run_multi_case.OUT_ROOT = output_root
            tempfile.gettempdir = lambda: str(root / "temp")
            with mock.patch.object(run_multi_case, "_pid_alive",
                                   return_value=True), \
                    mock.patch.object(run_multi_case, "_process_inventory",
                                      return_value=(True, [], None)):
                with self.assertRaises(SystemExit):
                    run_multi_case.cleanup_previous_test_runs(
                        new_output, "story-suite-new")
            self.assertTrue(live_workspace.exists())
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
            orphan_workspace = root / "temp/sw-story/story-suite-orphan"
            state_path.parent.mkdir(parents=True)
            new_output.mkdir(parents=True)
            orphan_workspace.mkdir(parents=True)
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
            self.assertTrue(orphan_workspace.exists())
        finally:
            run_multi_case.OUT_ROOT = original_out
            tempfile.gettempdir = original_gettempdir
            shutil.rmtree(root, ignore_errors=True)

    def test_finalize_cleanup_is_disabled(self) -> None:
        with self.assertRaises(SystemExit) as caught:
                run_multi_case.command_finalize("unused", False, True)
        self.assertIn("下一轮 suite 起跑时清理", str(caught.exception))

    def fake_demo(self, root: Path) -> Path:
        """一个最小但完整的消费工程：业务、framework、配置、入口文件、宿主目录与依赖。"""
        demo = root / "demo"
        for relative in ("01-Product/src/main", "01-Product/src/test", "framework/harness/state",
                         ".opencode/plugin", "framework/harness/node_modules/pkg",
                         "doc/extensions/hooks/retired"):
            (demo / relative).mkdir(parents=True, exist_ok=True)
        (demo / "01-Product/src/main/main.ets").write_text("product", encoding="utf-8")
        (demo / "01-Product/src/test/Case.test.ets").write_text("业务单测", encoding="utf-8")
        (demo / "framework/harness/state/phase.json").write_text("state", encoding="utf-8")
        (demo / "framework/harness/state/.gitkeep").write_text("", encoding="utf-8")
        (demo / ".opencode/plugin/publish.js").write_text("x", encoding="utf-8")
        (demo / "framework/harness/node_modules/pkg/i.js").write_text("dep", encoding="utf-8")
        (demo / "doc/extensions/hooks/retired/old.mjs").write_text("上一版的机制", encoding="utf-8")
        (demo / "framework.config.json").write_text("{}", encoding="utf-8")
        for name in ("AGENTS.md", "CLAUDE.md"):
            (demo / name).write_text("# demo\n\n## 实例扩展\n\n", encoding="utf-8")
        (demo / ".gitignore").write_text("node_modules/\ndoc/features/\nframework/harness/state/*\n"
                                         "!framework/harness/state/.gitkeep\n", encoding="utf-8")
        # 与真实布局一致：demo 是外层仓里的子目录，自己不是仓
        for cmd in (["init", "-q"], ["add", "-A"],
                    ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "发布基线"]):
            subprocess.run(["git", "-C", str(root), *cmd], check=True, capture_output=True)
        return demo

    def setUp(self) -> None:
        super().setUp()
        # 宿主入口的核与物化走 Framework 原生能力，已由 test_publish_to_demo 在真 Framework 上测过；
        # 这里的假 demo 没有 Framework，只替换那一步，测装配本身（复制边界、同源核对、失败即作废）。
        self.entry_calls: list[tuple[str, str]] = []
        self.entry_results = {"plan": (0, {"retire": [], "conflicts": [], "entries": []}),
                              "materialize": (0, {"written": [], "removed": [], "problems": []})}

        def fake_entries(script, target, *args):
            action = args[args.index("--action") + 1]
            self.entry_calls.append((str(target), action))
            return self.entry_results[action]

        patcher = mock.patch.object(run_multi_case.publish_to_demo, "_entries", fake_entries)
        patcher.start()
        self.addCleanup(patcher.stop)
        # 换被测 Framework 与原生物化同理：真发布树上的装配由 test_verifier_chain_in_workspace 从空目录建两次核过
        self.framework_calls: list[str] = []

        def fake_framework(template):
            self.framework_calls.append(str(template))
            return {"release_commit": "fake"}

        framework_patcher = mock.patch.object(run_multi_case, "install_framework_under_test", fake_framework)
        framework_patcher.start()
        self.addCleanup(framework_patcher.stop)

    def build_template(self, demo: Path, suite_id: str) -> Path:
        root = demo.parent
        suite_root = root / "suite"
        suite_root.mkdir(parents=True, exist_ok=True)
        original = run_multi_case.DEMO_ROOT
        run_multi_case.DEMO_ROOT = demo
        self.addCleanup(setattr, run_multi_case, "DEMO_ROOT", original)
        self.addCleanup(shutil.rmtree, Path(tempfile.gettempdir()) / "sw-story" / suite_id, True)
        template, _ = run_multi_case.create_workspace_template(suite_root, suite_id)
        return template

    def test_the_template_is_demo_plus_the_dev_source(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="story-multi-boundary-"))
        self.addCleanup(shutil.rmtree, root, True)
        demo = self.fake_demo(root)
        snapshot = {p.relative_to(demo).as_posix(): p.read_bytes() for p in demo.rglob("*") if p.is_file()}
        template = self.build_template(demo, f"boundary-test-{os.getpid()}")

        self.assertTrue((template / "01-Product/src/main/main.ets").is_file())
        self.assertTrue((template / "01-Product/src/test/Case.test.ets").is_file(), "业务模块自己的单测目录被当成维护目录丢了")
        self.assertTrue((template / ".opencode/plugin/publish.js").is_file())
        self.assertTrue((template / "framework/harness/node_modules/pkg/i.js").is_file())
        self.assertFalse((template / "framework/harness/state/phase.json").exists())
        self.assertTrue((template / "framework/harness/state/.gitkeep").is_file())
        self.assertEqual([], list((template / "doc/features").iterdir()), "template 的需求目录应是空的")
        ext = template / "doc/extensions"
        for rel in run_multi_case.publish_to_demo.enumerate_source(run_multi_case.DEV_SOURCE):
            self.assertEqual((run_multi_case.DEV_SOURCE / rel).read_bytes(), (ext / rel).read_bytes(), rel)
        self.assertFalse((ext / "hooks/retired/old.mjs").exists(), "demo 里上一版的机制文件残留在 template")
        self.assertEqual([str(template)] * 2, [call[0] for call in self.entry_calls],
                         "宿主入口没有按「写前核 → 物化」在 template 上各走一次")
        self.assertEqual([str(template)], self.framework_calls, "被测 Framework 没有装进 template")
        after = {p.relative_to(demo).as_posix(): p.read_bytes() for p in demo.rglob("*") if p.is_file()}
        self.assertEqual(snapshot, after, "装配写了 demo")
        boundary = run_multi_case.read_json(root / "suite" / "workspace-boundary.json")
        self.assertEqual("installed", boundary["installed"]["status"])
        self.assertTrue(boundary["demo"]["head"], "没记下装配所用的 demo 提交")

    def test_a_maintenance_directory_in_demo_stops_the_assembly(self) -> None:
        for name in sorted(run_multi_case.MAINTENANCE_TOP_LEVEL):
            with self.subTest(name):
                root = Path(tempfile.mkdtemp(prefix="story-multi-drift-"))
                self.addCleanup(shutil.rmtree, root, True)
                demo = self.fake_demo(root)
                (demo / name).mkdir()
                suite_id = f"drift-test-{os.getpid()}-{name.strip('.')}"
                with self.assertRaises(SystemExit) as caught:
                    self.build_template(demo, suite_id)
                self.assertIn("维护目录", str(caught.exception))
                self.assertFalse((Path(tempfile.gettempdir()) / "sw-story" / suite_id).exists(),
                                 "结构漂移时还是建了 template")

    def test_an_unclean_demo_is_not_assembled(self) -> None:
        """demo 是发布基线：业务或宿主文件有没提交的改动、git 查询失败，都不复制、不建 template。"""
        cases = {
            "业务文件改了": lambda demo: (demo / "01-Product/src/main/main.ets").write_text("人改了", encoding="utf-8"),
            "宿主文件新增": lambda demo: (demo / ".opencode/plugin/extra.js").write_text("y", encoding="utf-8"),
        }
        for name, dirty in cases.items():
            with self.subTest(name):
                root = Path(tempfile.mkdtemp(prefix="story-multi-dirty-"))
                self.addCleanup(shutil.rmtree, root, True)
                demo = self.fake_demo(root)
                dirty(demo)
                suite_id = f"dirty-demo-{os.getpid()}-{len(name)}"
                with self.assertRaises(SystemExit) as caught:
                    self.build_template(demo, suite_id)
                self.assertIn("没提交的改动", str(caught.exception))
                self.assertFalse((Path(tempfile.gettempdir()) / "sw-story" / suite_id).exists())
        with self.subTest("git 查询失败"):
            root = Path(tempfile.mkdtemp(prefix="story-multi-gitfail-"))
            self.addCleanup(shutil.rmtree, root, True)
            demo = self.fake_demo(root)
            suite_id = f"git-fail-{os.getpid()}"
            failing = mock.patch.object(run_multi_case.publish_to_demo, "git_dirty",
                                        side_effect=run_multi_case.publish_to_demo.InputError(["模拟失败"]))
            with failing, self.assertRaises(SystemExit) as caught:
                self.build_template(demo, suite_id)
            self.assertIn("查不出", str(caught.exception))
            self.assertFalse((Path(tempfile.gettempdir()) / "sw-story" / suite_id).exists())
        with self.subTest("提交查询失败"):
            root = Path(tempfile.mkdtemp(prefix="story-multi-headfail-"))
            self.addCleanup(shutil.rmtree, root, True)
            demo = self.fake_demo(root)
            suite_id = f"head-fail-{os.getpid()}"
            real = subprocess.run

            def failing(cmd, *a, **k):
                if cmd[:1] == ["git"] and cmd[-2:] == ["rev-parse", "HEAD"]:
                    return subprocess.CompletedProcess(cmd, 128, "", "fatal: 模拟失败")
                return real(cmd, *a, **k)

            with mock.patch.object(run_multi_case.subprocess, "run", failing), \
                    self.assertRaises(SystemExit) as caught:
                self.build_template(demo, suite_id)
            self.assertIn("提交查不出", str(caught.exception))
            self.assertFalse((Path(tempfile.gettempdir()) / "sw-story" / suite_id).exists())

    def test_features_left_in_demo_stop_the_assembly(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="story-multi-features-"))
        self.addCleanup(shutil.rmtree, root, True)
        demo = self.fake_demo(root)
        (demo / "doc/features/REAL01").mkdir(parents=True)
        (demo / "doc/features/REAL01/spec.md").write_text("真实需求", encoding="utf-8")
        suite_id = f"features-left-{os.getpid()}"
        with self.assertRaises(SystemExit) as caught:
            self.build_template(demo, suite_id)
        self.assertIn("demo/doc/features", str(caught.exception))
        self.assertTrue((demo / "doc/features/REAL01/spec.md").is_file(), "装配动了 demo 里的产物")
        self.assertFalse((Path(tempfile.gettempdir()) / "sw-story" / suite_id).exists(), "停下前已经建了 template")

    def test_a_template_whose_install_fails_is_not_used(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="story-multi-install-"))
        self.addCleanup(shutil.rmtree, root, True)
        demo = self.fake_demo(root)
        self.entry_results["plan"] = (1, {"retire": [], "conflicts": ["AGENTS.md：有原生生成之外的内容"], "entries": []})
        with self.assertRaises(SystemExit) as caught:
            self.build_template(demo, f"install-fail-{os.getpid()}")
        self.assertIn("template 作废", str(caught.exception))

    def test_failed_terminal_case_promotes_document_and_source_with_labels(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="story-promotion-"))
        original_repo = run_multi_case.DEMO_ROOT
        original_features = run_multi_case.FEATURES_ROOT
        try:
            host = root / "host"
            workspace = root / "workspace"
            bundle = root / "bundle"
            host.mkdir()
            (workspace / "doc/features/AR-X").mkdir(parents=True)
            (workspace / "01-Product").mkdir(parents=True)
            (workspace / "doc/features/AR-X/story.md").write_text(
                "failed evidence", encoding="utf-8")
            baseline = run_multi_case.snapshot_workspace_sources(workspace)
            (workspace / "01-Product/new.txt").write_text("source", encoding="utf-8")
            baseline_path = bundle / "cases/case-x/workspace-baseline.json"
            baseline_path.parent.mkdir(parents=True)
            run_multi_case.write_json(baseline_path, baseline)
            run_multi_case.DEMO_ROOT = host
            run_multi_case.FEATURES_ROOT = root / "maintenance/doc/features"
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
            self.assertTrue((root / "maintenance/doc/features/AR-X/story.md").is_file())
            self.assertFalse((host / "doc/features").exists(), "需求产物回流进了 demo")
            self.assertTrue((host / "01-Product/new.txt").is_file())
        finally:
            run_multi_case.DEMO_ROOT = original_repo
            run_multi_case.FEATURES_ROOT = original_features
            shutil.rmtree(root, ignore_errors=True)

    def test_batch_promotion_keeps_later_features_and_is_idempotent(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="story-promotion-batch-"))
        original_repo = run_multi_case.DEMO_ROOT
        original_features = run_multi_case.FEATURES_ROOT
        try:
            host = root / "host"
            bundle = root / "bundle"
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
            run_multi_case.DEMO_ROOT = host
            maintenance = root / "maintenance/doc/features"
            run_multi_case.FEATURES_ROOT = maintenance

            first = run_multi_case.promote_case_workspace(suite, records[0])
            second = run_multi_case.promote_case_workspace(suite, records[1])
            repeated = run_multi_case.promote_case_workspace(suite, records[0])

            self.assertEqual("promoted", first["status"])
            self.assertEqual("promoted", second["status"])
            self.assertEqual("already_promoted", repeated["status"])
            self.assertTrue(repeated["accepted"])
            self.assertEqual("AR-1", (maintenance / "AR-1/story.md").read_text())
            self.assertEqual("AR-2", (maintenance / "AR-2/story.md").read_text())
            self.assertFalse((host / "doc/features").exists(), "需求产物回流进了 demo")
            self.assertEqual("case-one", (host / "01-Product/base.txt").read_text())
        finally:
            run_multi_case.DEMO_ROOT = original_repo
            run_multi_case.FEATURES_ROOT = original_features
            shutil.rmtree(root, ignore_errors=True)


class FeaturesFlowBackToTheMaintenanceDoc(unittest.TestCase):
    """检查点快照与 update 终态都回流到维护仓 doc/features；重复回流幂等，内容不同的目标两边都留。"""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="story-flow-back-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.demo = self.root / "demo"
        (self.demo / "01-Product").mkdir(parents=True)
        self.features = self.root / "maintenance/doc/features"
        for name, value in (("DEMO_ROOT", self.demo), ("FEATURES_ROOT", self.features),
                            ("SUITES_ROOT", self.root / "suites")):
            self.addCleanup(setattr, run_multi_case, name, getattr(run_multi_case, name))
            setattr(run_multi_case, name, value)
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)

    def workspace_with(self, name: str, text: str, feature: str = "AR-9") -> Path:
        workspace = self.root / name
        (workspace / "doc/features" / feature).mkdir(parents=True)
        (workspace / "doc/features" / feature / "story.md").write_text(text, encoding="utf-8")
        return workspace

    def test_the_checkpoint_snapshot_lands_in_the_maintenance_doc(self) -> None:
        snapshot = self.root / "snapshot/AR-9"
        snapshot.mkdir(parents=True)
        (snapshot / "story.md").write_text("第一段", encoding="utf-8")
        suite_id = "suite-flow"
        bundle = self.root / "suites" / suite_id
        record = {"case": "case-9", "feature": "AR-9", "status": "awaiting_reply",
                  "checkpoints": {"after_initial": {"path": str(snapshot)}}}
        run_multi_case.write_json(bundle / "suite.json", {"bundle_root": str(bundle),
                                                          "case_states": {"case-9": record}, "events": []})
        with mock.patch.object(run_multi_case, "refresh_record", side_effect=lambda r: r), \
                mock.patch("sys.stdout"):
            first = run_multi_case.command_promote_checkpoint(suite_id, "case-9", "after_initial")
            again = run_multi_case.command_promote_checkpoint(suite_id, "case-9", "after_initial")
            (snapshot / "story.md").write_text("被改过的快照", encoding="utf-8")
            conflict = run_multi_case.command_promote_checkpoint(suite_id, "case-9", "after_initial")
        self.assertEqual((0, 0, 1), (first, again, conflict))
        self.assertEqual("第一段", (self.features / "AR-9/story.md").read_text(encoding="utf-8"))
        self.assertFalse((self.demo / "doc/features").exists(), "检查点快照回流进了 demo")

    def test_the_global_usage_is_kept_per_run(self) -> None:
        """全局 usage 不随需求回流：按运行留一份原字节快照；重复幂等，内容变了不覆盖已固定的，缺失如实记。"""
        suite = {"bundle_root": str(self.root / "bundle")}
        workspace = self.workspace_with("ws-usage", "终态")
        record = {"case": "case-u", "run_id": "run-1", "workspace": str(workspace)}
        usage = workspace / "doc" / "usage.json"
        with mock.patch.object(run_multi_case, "run_pointer_state", return_value=None):
            missing = run_multi_case.snapshot_usage(suite, record, "final")
            usage.write_bytes(b'{"schema": 1, "requirements": {}}\n')
            first = run_multi_case.snapshot_usage(suite, record, "initial")
            again = run_multi_case.snapshot_usage(suite, record, "initial")
            usage.write_bytes(b'{"schema": 1, "requirements": {"AR-9": {}}}\n')
            changed = run_multi_case.snapshot_usage(suite, record, "initial")
        target = self.root / "bundle/cases/case-u/run-1/usage/initial/usage.json"
        self.assertEqual("missing", missing["status"])
        self.assertFalse((self.root / "bundle/cases/case-u/run-1/usage/final").exists(), "缺失时造了空记录")
        self.assertEqual(("captured", "already_captured", "conflict"), (first["status"], again["status"], changed["status"]))
        self.assertEqual(b'{"schema": 1, "requirements": {}}\n', target.read_bytes(), "已固定的快照被覆盖")
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), first["sha256"])

    def test_the_update_terminal_lands_under_its_own_name_and_conflicts_keep_both(self) -> None:
        suite = {"bundle_root": str(self.root / "bundle"),
                 "main_source_baseline": run_multi_case.snapshot_workspace_sources(self.demo)}

        def record(workspace: Path, case: str, after_initial: str = "", feature: str = "AR-9", **extra) -> dict:
            baseline = self.root / "bundle/cases" / case / "workspace-baseline.json"
            run_multi_case.write_json(baseline, run_multi_case.snapshot_workspace_sources(workspace))
            return {"case": case, "feature": feature, "workspace": str(workspace),
                    "workspace_baseline": str(baseline), "status": "finished",
                    "execution_status": "finished", "after_initial": after_initial, **extra}

        plain_ws = self.workspace_with("ws-plain", "普通终态")
        report = plain_ws / "doc/reports/story/AR-9/k1/review-original.1.md"
        report.parent.mkdir(parents=True)
        report.write_text("审查原件", encoding="utf-8")
        plain = record(plain_ws, "case-plain")
        update = record(self.workspace_with("ws-update", "更新后的终态"), "case-update", "update",
                        resumed_update={"text": "按评审更新"},
                        checkpoints={"initial": {"path": "a"}, "update": {"path": "b"}})
        self.assertEqual("promoted", run_multi_case.promote_case_workspace(suite, plain)["status"])
        kept = self.root / "bundle/cases/case-plain/story-reports/k1/review-original.1.md"
        self.assertEqual("审查原件", kept.read_text(encoding="utf-8"), "需求目录外的 Story 审查报告没留进证据")
        landed = run_multi_case.promote_case_workspace(suite, update)
        self.assertEqual(("promoted", "update", False), (landed["status"], landed["segment"], landed["partial"]))
        self.assertEqual("普通终态", (self.features / "AR-9/story.md").read_text(encoding="utf-8"))
        self.assertEqual("更新后的终态", (self.features / "AR-9-update/story.md").read_text(encoding="utf-8"))

        # 计划了 update 但只跑了第一段就停：回流到原编号并标未走完，不冒称 update
        stopped = record(self.workspace_with("ws-stopped", "只有第一段", "AR-8"), "case-stopped", "update",
                         feature="AR-8", status="stop_failed")
        landed = run_multi_case.promote_case_workspace(suite, stopped)
        self.assertEqual(("promoted", "initial", True), (landed["status"], landed["segment"], landed["partial"]))
        self.assertEqual("只有第一段", (self.features / "AR-8/story.md").read_text(encoding="utf-8"))
        self.assertFalse((self.features / "AR-8-update").exists(), "只跑了第一段却按 update 命名")

        other = record(self.workspace_with("ws-other", "另一份普通终态"), "case-other")
        result = run_multi_case.promote_case_workspace(suite, other)
        self.assertIn("feature_destination_conflict", json.dumps(result, ensure_ascii=False))
        self.assertEqual("普通终态", (self.features / "AR-9/story.md").read_text(encoding="utf-8"), "冲突时覆盖了目标")
        self.assertTrue((self.root / "ws-other/doc/features/AR-9/story.md").is_file(), "冲突时动了来源")
        self.assertFalse((self.demo / "doc/features").exists(), "终态回流进了 demo")

    def link_blueprint(self, workspace: Path, text: str) -> None:
        """需求关联一份异名的蓝图工作区（流程契约的 design_binding）。"""
        src = workspace / "doc/features/AR-9/AR/story-src"
        src.mkdir(parents=True, exist_ok=True)
        (src / "story-flow.json").write_text(json.dumps(
            {"design_binding": {"component_id": "c", "blueprint_id": "bp-AR-9"}}), encoding="utf-8")
        (workspace / "doc/features/bp-AR-9/blueprint").mkdir(parents=True)
        (workspace / "doc/features/bp-AR-9/blueprint/component-blueprint.yaml").write_text(text, encoding="utf-8")

    def test_the_linked_blueprint_flows_back_under_its_own_name(self) -> None:
        """需求与蓝图工作区分开：终态与检查点回流都按关联把蓝图工作区一起带回，按它自己的身份落地。"""
        suite = {"bundle_root": str(self.root / "bundle"),
                 "main_source_baseline": run_multi_case.snapshot_workspace_sources(self.demo)}
        workspace = self.workspace_with("ws-bp", "终态")
        self.link_blueprint(workspace, "设计")
        self.assertEqual("bp-AR-9", run_multi_case.run_layout.linked_blueprint(workspace / "doc/features", "AR-9"))
        baseline = self.root / "bundle/cases/case-bp/workspace-baseline.json"
        run_multi_case.write_json(baseline, run_multi_case.snapshot_workspace_sources(workspace))
        record = {"case": "case-bp", "feature": "AR-9", "workspace": str(workspace), "workspace_baseline": str(baseline),
                  "status": "finished", "execution_status": "finished"}
        self.assertEqual("promoted", run_multi_case.promote_case_workspace(suite, record)["status"])
        self.assertEqual("设计", (self.features / "bp-AR-9/blueprint/component-blueprint.yaml").read_text(encoding="utf-8"))

        snapshot, design = self.root / "snapshot/AR-10", self.root / "snapshot/AR-10.blueprint"
        (snapshot).mkdir(parents=True)
        (snapshot / "story.md").write_text("第一段", encoding="utf-8")
        (design / "blueprint").mkdir(parents=True)
        (design / "blueprint/component-blueprint.yaml").write_text("第一段的设计", encoding="utf-8")
        suite_id = "suite-bp"
        bundle = self.root / "suites" / suite_id
        run_multi_case.write_json(bundle / "suite.json", {"bundle_root": str(bundle), "events": [], "case_states": {
            "case-10": {"case": "case-10", "feature": "AR-10", "status": "awaiting_reply", "checkpoints": {
                "after_initial": {"path": str(snapshot), "blueprint": "bp-AR-10", "blueprint_path": str(design)}}}}})
        with mock.patch.object(run_multi_case, "refresh_record", side_effect=lambda r: r), mock.patch("sys.stdout"):
            self.assertEqual(0, run_multi_case.command_promote_checkpoint(suite_id, "case-10", "after_initial"))
        self.assertEqual("第一段的设计", (self.features / "bp-AR-10/blueprint/component-blueprint.yaml").read_text(encoding="utf-8"))

    def test_a_requirement_without_a_separate_blueprint_links_nothing(self) -> None:
        workspace = self.workspace_with("ws-none", "终态")
        features = workspace / "doc/features"
        self.assertIsNone(run_multi_case.run_layout.linked_blueprint(features, "AR-9"), "没有流程契约却推测出了蓝图")
        src = features / "AR-9/AR/story-src"
        src.mkdir(parents=True)
        (src / "story-flow.json").write_text(json.dumps({"design_binding": {"blueprint_id": "AR-9"}}), encoding="utf-8")
        self.assertIsNone(run_multi_case.run_layout.linked_blueprint(features, "AR-9"), "与需求同名的不算另一份工作区")

    def test_the_reserved_archive_name_is_never_written_back(self) -> None:
        """回流根下的 archive 是历史归档：检查点与终态回流都不许写进它。"""
        history = self.features / "archive/Story-Features-20260101-000000/AR0"
        history.mkdir(parents=True)
        (history / "story.md").write_text("历史", encoding="utf-8")

        workspace = self.root / "ws-archive"
        (workspace / "doc/features/archive").mkdir(parents=True)
        (workspace / "doc/features/archive/story.md").write_text("覆盖", encoding="utf-8")
        baseline = self.root / "bundle/cases/case-a/workspace-baseline.json"
        run_multi_case.write_json(baseline, run_multi_case.snapshot_workspace_sources(workspace))
        suite = {"bundle_root": str(self.root / "bundle"),
                 "main_source_baseline": run_multi_case.snapshot_workspace_sources(self.demo)}
        record = {"case": "case-a", "feature": "archive", "workspace": str(workspace),
                  "workspace_baseline": str(baseline), "status": "finished", "execution_status": "finished"}
        result = run_multi_case.promote_case_workspace(suite, record)
        self.assertIn("reserved_archive_name", json.dumps(result, ensure_ascii=False))
        self.assertFalse((self.features / "archive/story.md").exists(), "终态回流写进了归档目录")

        snapshot = self.root / "snapshot/Archive"
        snapshot.mkdir(parents=True)
        suite_id = "suite-reserved"
        bundle = self.root / "suites" / suite_id
        run_multi_case.write_json(bundle / "suite.json", {
            "bundle_root": str(bundle), "events": [],
            "case_states": {"case-a": {"case": "case-a", "feature": "Archive", "status": "awaiting_reply",
                                       "checkpoints": {"initial": {"path": str(snapshot)}}}}})
        with mock.patch.object(run_multi_case, "refresh_record", side_effect=lambda r: r), \
                self.assertRaises(SystemExit):
            run_multi_case.command_promote_checkpoint(suite_id, "case-a", "initial")
        self.assertEqual(["Story-Features-20260101-000000"], [p.name for p in (self.features / "archive").iterdir()])


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

    @unittest.skipUnless(sys.platform == "win32", "打不开的进程这一路只在 Windows 上出现")
    def test_a_pid_taken_over_by_a_process_we_cannot_open_is_not_ours(self) -> None:
        """号码被系统进程接手：打不开它，创建时间也读不出来——那就不是我们的 worker。

        实测（本轮起跑前）：两个历史 run 的 pid 被 dwm.exe 之类接手，`OpenProcess` 返回
        ERROR_ACCESS_DENIED，创建时间读不到，于是按「读不出就算活着」退让，
        两处历史现场被永久判成活动的，新 suite 起不来。
        """
        ancient = datetime.fromtimestamp(time.time() - 7 * 86400).strftime("%Y-%m-%d %H:%M:%S")
        self.assertIsNone(run_multi_case._process_create_epoch(4), "系统进程的创建时间本来就读不到")
        self.assertFalse(run_multi_case._pid_alive(4, ancient), "打不开的进程被当成了我们的 worker")
        self.assertFalse(run_multi_case._pid_alive(4, None), "连启动记录都没有时也不该判成我们的")

    def test_liveness_never_calls_os_kill_on_windows(self) -> None:
        """Windows 上 `os.kill(pid, 0)` 走的是 TerminateProcess：有权限的那一下会杀掉进程。"""
        source = (SCRIPTS / "run_multi_case.py").read_text(encoding="utf-8")
        windows_branch = source.split("def _win_running", 1)[1].split("def _pid_alive", 1)[0]
        self.assertNotIn("os.kill(", windows_branch, "Windows 这一支又拿 os.kill 探活了")
        self.assertIn("_win_running(int(pid))", source, "win32 分支没走这条判定")

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


class CaseWorkspaceOwnsItsGitRoot(unittest.TestCase):
    """Case 根是它自己的 Git 仓：外层目录本身在某个仓里时（实测落在用户配置仓下），被测工程不继承那个仓的 HEAD。

    用真实 git 与本地夹具父仓，不碰真实用户仓与 demo。
    """

    def git(self, cwd: Path, *args: str) -> str:
        return subprocess.run(["git", "-c", "user.name=fixture", "-c", "user.email=fixture@localhost", *args],
                              cwd=str(cwd), capture_output=True, text=True, check=True).stdout.strip()

    def setUp(self) -> None:
        self.parent = Path(tempfile.mkdtemp(prefix="story-git-parent-")).resolve()
        self.addCleanup(shutil.rmtree, self.parent, onexc=run_multi_case._clear_readonly_and_retry)
        self.git(self.parent, "init", "-q")
        (self.parent / "user.txt").write_text("用户配置\n", encoding="utf-8")
        self.git(self.parent, "add", "-A")
        self.git(self.parent, "commit", "-q", "-m", "parent")
        ws = self.parent / "Temp" / "c1"
        files = {".gitignore": "doc/features/\nframework.local.json\n**/node_modules\n",
                 "framework.config.json": "{}", "framework.local.json": '{"agent_adapter": "dsh"}',
                 "framework/RELEASE-MANIFEST.json": "{}", "doc/extensions/story/AGENTS.section.md": "x",
                 "02-Feature/src/Page.ets": "page", "framework/harness/node_modules/dep/index.js": "dep",
                 "doc/features/AR1/inbox/需求.md": "需求"}
        for relative, text in files.items():
            (ws / relative).parent.mkdir(parents=True, exist_ok=True)
            (ws / relative).write_text(text, encoding="utf-8")
        self.ws = ws.resolve()
        bundle = Path(tempfile.mkdtemp(prefix="story-git-bundle-"))
        self.addCleanup(shutil.rmtree, bundle, True)
        self.suite = {"bundle_root": str(bundle)}
        self.case = {"case": "c1", "feature": "AR1", "workspace": str(self.ws),
                     "case_seeded": [{"target": "doc/features/AR1/inbox/需求.md"}]}

    def test_the_case_root_gets_its_own_baseline_and_the_parent_is_untouched(self) -> None:
        self.assertEqual(self.parent.as_posix(), self.git(self.ws, "rev-parse", "--show-toplevel"),
                         "夹具前提：装配前 Case 根继承外层仓")
        parent_before = (self.git(self.parent, "rev-parse", "HEAD"), self.git(self.parent, "status", "--porcelain"))
        result = run_multi_case.ensure_case_git(self.suite, self.case)
        self.assertEqual("ready", result["status"], result)
        self.assertEqual(self.ws.as_posix(), self.git(self.ws, "rev-parse", "--show-toplevel"))
        self.assertEqual((self.parent.as_posix(), self.git(self.ws, "rev-parse", "HEAD")),
                         (result["inherited_toplevel"], result["initial_head"]))
        tracked = self.git(self.ws, "ls-files").splitlines()
        for path in ("framework.config.json", "02-Feature/src/Page.ets", "doc/extensions/story/AGENTS.section.md"):
            self.assertIn(path, tracked)
        for path in ("framework.local.json", "framework/harness/node_modules/dep/index.js"):
            self.assertNotIn(path, tracked, "工程忽略的个人设置或依赖被强行提交")
        self.assertEqual(["doc/features/AR1/inbox/需求.md"], result["ignored_key_files"],
                         "被工程规则忽略的 Case 输入要如实列成缺口")
        self.assertEqual("story-suite", self.git(self.ws, "log", "-1", "--format=%an"))
        self.assertEqual(parent_before, (self.git(self.parent, "rev-parse", "HEAD"),
                                         self.git(self.parent, "status", "--porcelain")), "装配改了外层仓")
        boundary = run_multi_case.read_json(Path(self.suite["bundle_root"]) / "workspace-boundary.json", {})
        self.assertEqual(result["initial_head"], boundary["git_boundary"]["c1"]["initial_head"])
        (self.parent / "user.txt").write_text("用户又提交了\n", encoding="utf-8")
        self.git(self.parent, "commit", "-q", "-am", "parent moves")
        self.assertEqual(result["initial_head"], self.git(self.ws, "rev-parse", "HEAD"), "外层仓提交带动了 Case HEAD")

    def test_resuming_only_checks_identity_and_keeps_the_models_commits(self) -> None:
        first = run_multi_case.ensure_case_git(self.suite, self.case)
        (self.ws / "02-Feature/src/Page.ets").write_text("模型改过", encoding="utf-8")
        self.git(self.ws, "commit", "-q", "-am", "model work")
        model_head = self.git(self.ws, "rev-parse", "HEAD")
        again = run_multi_case.ensure_case_git(self.suite, self.case)
        self.assertEqual(("ready", first["initial_head"]), (again["status"], again["initial_head"]))
        self.assertEqual((model_head, "2"), (self.git(self.ws, "rev-parse", "HEAD"),
                                             self.git(self.ws, "rev-list", "--count", "HEAD")), "续跑重新提交了")
        self.git(self.ws, "config", "core.worktree", str(self.parent))
        redirected = run_multi_case.ensure_case_git(self.suite, dict(self.case))
        self.assertEqual("failed", redirected["status"], "仓根被 core.worktree 指到外层还当成立")
        self.git(self.ws, "config", "--unset", "core.worktree")
        shutil.rmtree(self.ws / ".git", onexc=run_multi_case._clear_readonly_and_retry)
        lost = run_multi_case.ensure_case_git(self.suite, self.case)
        self.assertEqual("failed", lost["status"], "仓没了还当续跑成立")

    def test_a_git_pointer_or_nested_repo_is_still_refused(self) -> None:
        (self.ws / ".git").write_text(f"gitdir: {self.parent / '.git'}\n", encoding="utf-8")
        result = run_multi_case.ensure_case_git(self.suite, self.case)
        self.assertEqual("failed", result["status"])
        self.assertIn("已有 .git", result["reason"])
        for own_git in (False, True):
            with self.assertRaises(RuntimeError, msg=f"own_git={own_git}"):
                run_multi_case._verify_workspace_boundary(self.ws, "AR1", own_git=own_git)
        (self.ws / ".git").unlink()
        self.assertEqual("ready", run_multi_case.ensure_case_git(self.suite, self.case)["status"])
        run_multi_case._verify_workspace_boundary(self.ws, "AR1", own_git=True)
        with self.assertRaises(RuntimeError):
            run_multi_case._verify_workspace_boundary(self.ws, "AR1")
        (self.ws / "02-Feature" / ".git").mkdir()
        with self.assertRaises(RuntimeError) as caught:
            run_multi_case._verify_workspace_boundary(self.ws, "AR1", own_git=True)
        self.assertIn("02-Feature/.git", str(caught.exception))

    def test_without_git_the_case_does_not_start(self) -> None:
        with mock.patch.object(run_multi_case.subprocess, "run", side_effect=FileNotFoundError("git")):
            result = run_multi_case.ensure_case_git(self.suite, self.case)
        self.assertEqual("failed", result["status"])
        self.assertFalse((self.ws / ".git").exists())
        suite = {**self.suite, "case_states": {"c1": self.case}}
        with mock.patch.object(run_multi_case, "select_healthy_cli", return_value=(0, "dsh-1")), \
                mock.patch.object(run_multi_case, "suite_cli_configurations", return_value=[{"name": "dsh"}]), \
                mock.patch.object(run_multi_case, "seed_agent_adapter", return_value={"cli": "dsh"}), \
                mock.patch.object(run_multi_case, "ensure_case_git", return_value=result), \
                mock.patch.object(run_multi_case, "invoke_case") as invoke:
            run_multi_case.start_one(self.case, suite)
        invoke.assert_not_called()
        self.assertEqual("coordinator_start_failed", self.case["status"])
        self.assertIn("git_boundary", self.case["last_error"])

    def test_a_retried_workspace_can_be_removed_with_its_repository(self) -> None:
        run_multi_case.ensure_case_git(self.suite, self.case)
        shutil.rmtree(self.ws, onexc=run_multi_case._clear_readonly_and_retry)
        self.assertFalse(self.ws.exists())


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
        """开发源 `extensions` 有未提交改动 → suite 终态变 `harness_contaminated`。"""
        suite = self.suite_all_finished()
        dirty = {"checked": True, "clean": False,
                 "status": " M extensions/skills/story/scripts/core/story_flow.py",
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


class TheTestedObjectIsComparedWithItsOwnBaseline(unittest.TestCase):
    """污染按本轮前后身份比：开发源与每个 Case 的机制各自比起跑基线；基线缺失是「无法核实」，不是干净。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def tree(self, name: str, files: dict[str, str]) -> Path:
        base = self.root / name
        for rel, text in files.items():
            (base / rel).parent.mkdir(parents=True, exist_ok=True)
            (base / rel).write_text(text, encoding="utf-8")
        return base

    def test_drift_names_changed_added_and_removed_files(self) -> None:
        ext = self.tree("ext", {"manifest.yaml": "version: 1\n", "hooks/a.mjs": "a\n", "hooks/b.mjs": "b\n"})
        with mock.patch.object(run_multi_case.publish_to_demo, "enumerate_source",
                               side_effect=lambda r: sorted(p.relative_to(r).as_posix() for p in Path(r).rglob("*") if p.is_file())):
            before = run_multi_case.tree_identity(ext)
            (ext / "hooks/a.mjs").write_text("a2\n", encoding="utf-8")
            (ext / "hooks/b.mjs").unlink()
            (ext / "hooks/c.mjs").write_text("c\n", encoding="utf-8")
            drift = run_multi_case.identity_drift(before, run_multi_case.tree_identity(ext))
        self.assertTrue(drift["verified"])
        self.assertFalse(drift["clean"])
        self.assertEqual(["hooks/a.mjs"], [c["path"] for c in drift["changed"]])
        self.assertEqual(["hooks/c.mjs"], drift["added"])
        self.assertEqual(["hooks/b.mjs"], drift["removed"])

    def test_a_missing_baseline_is_unverified_not_clean(self) -> None:
        drift = run_multi_case.identity_drift(None, {"readable": True, "digest": "x", "files": {}})
        self.assertFalse(drift["verified"])
        self.assertNotIn("clean", drift)

    def test_a_case_that_changed_its_own_mechanism_contaminates_the_suite(self) -> None:
        bundle = self.root / "suite"
        workspace = self.tree("ws", {"doc/extensions/manifest.yaml": "version: 1\n"})
        listing = lambda r: sorted(p.relative_to(r).as_posix() for p in Path(r).rglob("*") if p.is_file())  # noqa: E731
        with mock.patch.object(run_multi_case.publish_to_demo, "enumerate_source", side_effect=listing), \
                mock.patch.object(run_multi_case, "DEV_SOURCE", workspace / "doc" / "extensions"):
            ident = run_multi_case.tree_identity(workspace / "doc" / "extensions")
            run_multi_case.write_json(bundle / "workspace-boundary.json", {"identity": {"dev_source": ident}})
            run_multi_case.write_json(bundle / "cases" / "c" / "mechanism-baseline.json", ident)
            suite = {"bundle_root": str(bundle), "case_states": {"c": {"workspace": str(workspace)}}}
            self.assertTrue(run_multi_case.mechanism_contamination(suite)["clean"])
            (workspace / "doc/extensions/manifest.yaml").write_text("version: 2\n", encoding="utf-8")
            got = run_multi_case.mechanism_contamination(suite)
        self.assertTrue(got["checked"])
        self.assertFalse(got["clean"])
        self.assertEqual(["manifest.yaml"], [c["path"] for c in got["case_mechanism"]["c"]["changed"]])
