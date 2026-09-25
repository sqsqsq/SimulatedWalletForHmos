"""双检查点：到目标不终止、同一次对话续第二段、两段各自回流。

D18 要的形态是「先给初评、回流原结果且不终止，再触发同一会话的 update，
第二次评测后终止、回流为 `<需求编号>-update`」。装置原来做不到：到目标就 break，
finalize 的目的地固定成原编号。这一组锁住改完之后的几件确定的事：

  ① **不配就不变**：没有 `after_initial` 的用例行为逐字节照旧；
  ② 第一段到目标停在检查点上，`session` 落了盘、租约照常续，**不终止**；
  ③ 快照要在 worker 停着的时候取；复制期间目录变了就判这次快照作废；
  ④ 没固定快照不许续跑，没回流不许续跑——顺序错了，第一段的产物就只剩快照里那一份；
  ⑤ 第二段的终点**看流程契约那一笔**，不看模型说没说「更新完成」；
  ⑥ 终态文档另名落地，第一段回流的那一份不被覆盖。

真实的两段实跑归 T2，这里一个被测模型都不起。
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_case as rc  # noqa: E402
import run_multi_case as rmc  # noqa: E402


class CaseConfigIsOptional(unittest.TestCase):
    """`after_initial` 不配就是普通单终点——既有用例一个字节不用改。"""

    def test_a_plain_case_has_no_second_segment(self) -> None:
        plan = rmc.CasePlan("c", "AR1", "story", "spec", False, ("spec",))
        self.assertEqual("", plan.after_initial)
        self.assertIsNone(plan.as_dict()["after_initial"])

    def test_only_update_is_accepted(self) -> None:
        """值域一个字：别的写法当场拒绝，不要跑到一半才发现它没生效。"""
        self.assertIn("after_initial", (SCRIPTS / "run_multi_case.py").read_text(encoding="utf-8"))
        plan = rmc.CasePlan("c", "AR1", "story", "spec", False, ("spec",), (), (), "update")
        self.assertEqual("update", plan.as_dict()["after_initial"])


class TheSecondSegmentEndsOnTheContract(unittest.TestCase):
    """第二段写完没有，看 `story-flow.json` 里那一笔，不看模型的说法。"""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.src = self.tmp / "doc" / "features" / "AR1" / "AR" / "story-src"
        self.src.mkdir(parents=True)
        self._real_root = rc.REPO_ROOT
        rc.REPO_ROOT = self.tmp
        self.addCleanup(lambda: setattr(rc, "REPO_ROOT", self._real_root))

    def write_flow(self, update: dict | None) -> None:
        body: dict = {"schema": 4, "rounds": []}
        if update is not None:
            body["update"] = update
        (self.src / "story-flow.json").write_text(json.dumps(body), encoding="utf-8")

    def test_no_contract_is_not_a_finished_round(self) -> None:
        got = rc.update_round("AR1")
        self.assertFalse(got["readable"])
        self.assertIsNone(got["last_closed"])

    def test_an_open_round_is_not_finished(self) -> None:
        self.write_flow({"open": "20260920-100000"})
        self.assertEqual("20260920-100000", rc.update_round("AR1")["open"])
        self.assertIsNone(rc.update_round("AR1")["last_closed"])

    def test_a_closed_round_is_reported(self) -> None:
        self.write_flow({"open": None, "last_closed": "20260920-100000"})
        got = rc.update_round("AR1")
        self.assertIsNone(got["open"])
        self.assertEqual("20260920-100000", got["last_closed"])


class TheCheckpointNeedsAStoppedWorker(unittest.TestCase):
    """快照要在 worker 停着的时候取：跑着复制，复制到一半模型又写一笔。"""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_the_digest_only_sees_content_and_place(self) -> None:
        """同一份东西复制一遍摘要不变——不然「复制期间变没变」根本判不了。"""
        a, b = self.tmp / "a", self.tmp / "b"
        (a / "x").mkdir(parents=True)
        (a / "x" / "f.md").write_text("内容\n", encoding="utf-8")
        shutil.copytree(a, b)
        self.assertEqual(rc._tree_digest(a), rc._tree_digest(b))
        (b / "x" / "f.md").write_text("改了\n", encoding="utf-8")
        self.assertNotEqual(rc._tree_digest(a), rc._tree_digest(b))

    def test_a_moved_file_changes_the_digest(self) -> None:
        """位置也算：同一份内容挪个地方，那是另一个目录状态。"""
        a = self.tmp / "a"
        (a / "x").mkdir(parents=True)
        (a / "x" / "f.md").write_text("内容\n", encoding="utf-8")
        first = rc._tree_digest(a)
        (a / "x" / "f.md").rename(a / "f.md")
        self.assertNotEqual(first, rc._tree_digest(a))


class TheOrderIsSnapshotThenPromoteThenResume(unittest.TestCase):
    """顺序错了，第一段的产物就只剩快照里那一份——三处各自把关。"""

    def test_the_case_side_requires_a_snapshot(self) -> None:
        src = (SCRIPTS / "run_case.py").read_text(encoding="utf-8")
        self.assertIn("第一段的快照还没固定", src)
        self.assertIn('awaiting_kind") != "initial_checkpoint"', src,
                      "没有检查 worker 是不是停在第一检查点上")

    def test_the_suite_side_requires_a_promotion(self) -> None:
        src = (SCRIPTS / "run_multi_case.py").read_text(encoding="utf-8")
        self.assertIn("第一段还没回流", src)
        self.assertIn("promote-checkpoint", src)

    def test_the_snapshot_is_what_gets_promoted(self) -> None:
        """回流的是固定下来的那一份，不是还在跑第二段的工作区。"""
        src = (SCRIPTS / "run_multi_case.py").read_text(encoding="utf-8")
        body = src.split("def command_promote_checkpoint", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("checkpoints", body)
        self.assertIn("destination_conflict", body, "目的地有不同内容时没有保留两边")


class TheTwoSegmentsLandInDifferentPlaces(unittest.TestCase):
    def test_the_final_documents_use_a_separate_directory(self) -> None:
        """终态文档另名：原编号那一份是第一段回流的，两段分开才比得出更新改了什么。"""
        src = (SCRIPTS / "run_multi_case.py").read_text(encoding="utf-8")
        self.assertIn('f"{record[\'feature\']}-update"', src)
        self.assertIn('after_initial") == "update"', src)

    def test_the_terminal_sets_agree_between_the_two_sides(self) -> None:
        """两边的终态名单要一致：Case 已经收尾，宿主却判它还活着就拒绝回灌。"""
        for status in ("concluded_by_host", "cli_session_lost", "harness_incomplete"):
            with self.subTest(status=status):
                self.assertIn(status, rc.TERMINAL_STATUS)
                self.assertIn(status, rmc.TERMINAL_STATUS)


class TheSecondCheckpointAlsoWaits(unittest.TestCase):
    """第二段写完也要停着 —— **快照要在停着的时候取**。

    上一版这里直接 break，run 以 `finished` 收场，而 `checkpoint` 只认等待态：
    TEST §5.9 第 7 步「checkpoint --point update → 后评 → conclude」会卡在第一条命令上。
    """

    def test_it_stops_instead_of_finishing(self) -> None:
        src = (SCRIPTS / "run_case.py").read_text(encoding="utf-8")
        self.assertIn("def wait_at_update_checkpoint(", src)
        self.assertIn('awaiting_kind="update_checkpoint"', src)
        body = src.split("def wait_at_update_checkpoint", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("pop_conclude_request", body, "第二检查点没有出口")
        self.assertNotIn("pop_resume_request", body,
                         "第二段之后没有第三段，这里不该再收续跑请求")

    def test_the_checkpoint_command_still_requires_a_stopped_worker(self) -> None:
        """两个检查点用同一条判据：worker 停着才复制。"""
        src = (SCRIPTS / "run_case.py").read_text(encoding="utf-8")
        body = src.split("def cmd_checkpoint", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('status != "awaiting_reply"', body)


class NothingToUpdateIsAlsoAnEnding(unittest.TestCase):
    """这一轮检测下来真的没变化，也是一条正当的结束，不是「还没跑完」。

    「无变化」那条路按设计什么都不建、什么都不删——契约上那一笔不会动。
    不认它的话，一次「没什么要改」的更新会一直停着等人来收，而它早就走完了。
    """

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.updates = self.tmp / "doc" / "features" / "AR1" / "AR" / "story-src" / "updates"
        self.updates.mkdir(parents=True)
        self._real = rc.REPO_ROOT
        rc.REPO_ROOT = self.tmp
        self.addCleanup(lambda: setattr(rc, "REPO_ROOT", self._real))

    def test_the_mark_is_read_back(self) -> None:
        (self.updates / ".last-prepare.json").write_text(
            json.dumps({"comparison": "unchanged", "at": "2026-09-20T10:00:00+00:00"}),
            encoding="utf-8")
        got = rc.last_prepare("AR1")
        self.assertEqual("unchanged", got["comparison"])

    def test_a_missing_or_broken_mark_is_not_an_ending(self) -> None:
        """读不出来就是读不出来——不能拿它当「没变化」把一轮结束掉。"""
        self.assertEqual({}, rc.last_prepare("AR1"))
        (self.updates / ".last-prepare.json").write_text("{坏的", encoding="utf-8")
        self.assertEqual({}, rc.last_prepare("AR1"))

    def test_only_a_mark_left_after_resuming_counts(self) -> None:
        """比的是时刻：续跑之前那一次检测的结论，不能拿来结束第二段。"""
        src = (SCRIPTS / "run_case.py").read_text(encoding="utf-8")
        self.assertIn('state.get("resumed_at")', src, "没有按续跑时刻比对")

    def test_the_mark_is_a_process_file_not_a_product(self) -> None:
        """留痕落在过程目录、点开头：不进材料清单，也不该被当成业务产物。"""
        upd = (REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts"
               / "core" / "flow" / "update.py").read_text(encoding="utf-8")
        self.assertIn('".last-prepare.json"', upd)
        body = upd.split("def _note_prepare", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("except OSError", body, "留痕失败不该让一次正常的检测失败")


class LongPathsDoNotBreakTheRun(unittest.TestCase):
    """T2 实跑撞上的：Windows 260 字符上限。

    更新轮次的 `before/` 镜像里原样套着带 64 位哈希的阶段报告，放进 output 下的
    检查点目录或 run 的 artifact 副本就过了 300 字符。上一版三处都崩：检查点快照、
    收尾的 artifact 副本（崩在这里 worker 连终态都没写成，被判 worker_lost）、
    宿主侧的回流与摘要。报错还说成「系统找不到指定的路径」——文件明明在。
    """

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(rc._long(self.tmp), ignore_errors=True))

    def deep_tree(self) -> Path:
        """造一棵真的超过 260 字符的目录：路径长度照实跑里那一条的形态。"""
        root = self.tmp / "src"
        leaf = root.joinpath("AR", "story-src", "updates", "20260920-123715", "before",
                             "spec", "reports")
        name = "verifier.material." + "a" * 64 + ".json"
        rc._long(leaf).mkdir(parents=True)
        (rc._long(leaf) / name).write_text("{}", encoding="utf-8")
        return root

    def test_the_prefix_is_added_once_on_windows(self) -> None:
        p = rc._long(self.tmp)
        if os.name == "nt":
            self.assertTrue(str(p).startswith("\\\\?\\"))
            self.assertEqual(p, rc._long(p), "前缀加了两次")
        else:
            self.assertEqual(self.tmp, p)

    def test_both_sides_agree_on_the_digest(self) -> None:
        """两侧的摘要口径一致：不然「复制期间变没变」「目的地是不是同一份」判出两种答案。"""
        root = self.deep_tree()
        self.assertIsNotNone(rc._tree_digest(root))
        self.assertIsNotNone(rmc._tree_digest(root))

    @unittest.skipUnless(os.name == "nt", "260 字符上限只在 Windows 上存在")
    def test_a_deep_tree_copies_into_a_deep_destination(self) -> None:
        root = self.deep_tree()
        dest = self.tmp.joinpath("output", "story", "story-suite-20260920-1155", "cases",
                                 "auto-topup", "20260920-194122-28204-8bae2f56",
                                 "checkpoints", "update")
        self.assertGreater(len(str(dest)) + 150, 260, "这棵树不够深，测不到上限")
        shutil.copytree(rc._long(root), rc._long(dest))
        self.assertEqual(rc._tree_digest(root), rc._tree_digest(dest))

    def test_every_whole_tree_copy_goes_through_it(self) -> None:
        """整目录复制一处都不能漏——漏一处，那一处就是下一次的 worker_lost。"""
        case = (SCRIPTS / "run_case.py").read_text(encoding="utf-8")
        self.assertIn("shutil.copytree(_long(src), _long(artifact))", case)
        self.assertIn("shutil.copytree(_long(source), _long(dest))", case)
        multi = (SCRIPTS / "run_multi_case.py").read_text(encoding="utf-8")
        self.assertIn("shutil.copytree(_long(feature_source), _long(feature_destination))", multi)
        self.assertIn("shutil.copytree(_long(source), _long(destination))", multi)

    def test_a_failed_snapshot_leaves_no_half_copy(self) -> None:
        """复制一半的快照比没有更糟：下一次重试会撞上「已有一份不同的快照」。"""
        case = (SCRIPTS / "run_case.py").read_text(encoding="utf-8")
        body = case.split("def cmd_checkpoint", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("已清掉半成品", body)


class ASuiteThatFinishedDirtyIsStillFinished(unittest.TestCase):
    """`harness_contaminated` 是在全部 Case 都终态之后才算出来的——它是终态。

    清理预检的名单漏了它，上一轮 suite 就会永远挡住之后每一次起跑，
    而它早就结束了、一个活进程都没有（T2 起跑时撞上的）。
    """

    def test_the_cleanup_precheck_accepts_it(self) -> None:
        src = (SCRIPTS / "run_multi_case.py").read_text(encoding="utf-8")
        at = src.index("terminal_suite = str(suite.get(\"status\")) in {")
        self.assertIn("harness_contaminated", src[at:at + 200])


class TheTwoSegmentsAreMeasuredApart(unittest.TestCase):
    """分界取 `state.json` 的 `resumed_at`——带日期与时区。

    `live.jsonl` 的 `ts` 只有时分秒：两段跨过午夜时（第一段晚上跑完、第二段第二天早上
    才续上）根本比不出先后。T2 里 car 两段合计量出 919 分钟，全是夜里的睡眠空档。
    """

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        sys.path.insert(0, str(SCRIPTS))
        import measure_run  # noqa: PLC0415
        self.mr = measure_run

    def test_it_cuts_across_midnight(self) -> None:
        (self.tmp / "state.json").write_text(
            json.dumps({"resumed_at": "2026-09-21T02:34:36+00:00"}), encoding="utf-8")
        events = [{"timestamp": "2026-09-20T20:40:00+08:00"},   # 第一段，前一晚
                  {"timestamp": "2026-09-20T20:51:00+08:00"},
                  {"timestamp": "2026-09-21T10:35:00+08:00"},   # 第二段，第二天早上
                  {"timestamp": "2026-09-21T10:50:00+08:00"}]
        self.assertEqual(2, self.mr.split_at_checkpoint(events, self.tmp))

    def test_a_plain_run_has_no_split(self) -> None:
        (self.tmp / "state.json").write_text("{}", encoding="utf-8")
        self.assertIsNone(self.mr.split_at_checkpoint([{"timestamp": "2026-09-21T10:00:00+08:00"}],
                                                      self.tmp))


class TheSecondCheckpointShowsTheReviewClosure(unittest.TestCase):
    """第二检查点把各阶段审查闭环是哪一种带给宿主。

    预跑里 auto 写了审查报告却没同步闭环，summary 仍是「沿用历史 PASS」，模型报了完成；
    宿主要逐份翻文件才看得见。这里只报事实，不判。
    """

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        feature = self.tmp / "doc" / "features" / "AR1"
        for phase, body in (("spec", {"verifier_closure": {"mode": "completed_with_prior_review"},
                                      "readiness_signals": [{"id": "semantic_not_reverified"}],
                                      "verifier_subject_id": "e1de"}),
                            ("plan", {"readiness_signals": [], "verifier_subject_id": "6233"})):
            (feature / phase / "reports").mkdir(parents=True)
            (feature / phase / "reports" / "summary.json").write_text(json.dumps(body),
                                                                      encoding="utf-8")
        patcher = unittest.mock.patch.multiple(rc, REPO_ROOT=self.tmp, FEATURES_DIR="doc/features")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_it_reports_each_phase_as_it_is(self) -> None:
        out = rc.review_closure("AR1")
        self.assertEqual("completed_with_prior_review", out["spec"]["mode"])
        self.assertEqual(["semantic_not_reverified"], out["spec"]["signals"])
        self.assertEqual([], out["plan"]["signals"])
        self.assertNotIn("coding", out, "没有产物的阶段不该出现")

    def test_phase_results_carry_the_review_apart_from_closure(self) -> None:
        results = rc.build_phase_results("AR1", "spec", "plan", {})
        self.assertEqual("completed_with_prior_review", results["spec"]["review"]["mode"])
        self.assertFalse(results["spec"]["review"]["report_adopted"])

    def test_the_event_carries_it(self) -> None:
        src = (SCRIPTS / "run_case.py").read_text(encoding="utf-8")
        at = src.index('feed.emit("update_checkpoint"')
        self.assertIn("closure=review_closure(feature)", src[at:at + 300])


class ReportAdoptedMeansTheCurrentReportPassedAndWasTakenIn(unittest.TestCase):
    """`report_adopted` 只在当前报告确实被采纳且通过时为 true。

    判据同 phases/update.md「与闭环、修正入口的关系」第 4 步：summary 闭环、PASS、零阻断；
    报告在盘，终态块的 subject 是当前 subject、PASS、零阻断；没有兜底闭环、没挂未重审信号。
    终态块按 framework `parseResultBlock` 的协议读：恰好一个完整块，块外文字不算，字段值合法。
    """

    SUBJECT = "5a036a42e5bf1aafcb49d8e64a8f2e33e93200bc96d1dda1abb2a999c5bb8a8d"
    OTHER = "208a977e110f80d2be405b8298bf9f07c46b36b4acb98d7d13cbee3870b32d36"

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.reports = self.tmp / "doc" / "features" / "AR1" / "plan" / "reports"
        self.reports.mkdir(parents=True)
        patcher = unittest.mock.patch.multiple(rc, REPO_ROOT=self.tmp, FEATURES_DIR="doc/features")
        patcher.start()
        self.addCleanup(patcher.stop)

    def summary(self, **overrides) -> None:
        rel = f"doc/features/AR1/plan/reports/verifier.report.{self.SUBJECT}.md"
        body = {"verdict": "PASS", "blocker_count": 0, "closure_status": "closed",
                "readiness_signals": [], "verifier_subject_id": self.SUBJECT, "verifier_report": rel}
        body.update(overrides)
        (self.reports / "summary.json").write_text(json.dumps(body), encoding="utf-8")

    @staticmethod
    def block(subject: str, verdict: str = "PASS", blockers: str = "0", close: bool = True) -> str:
        return ("<!-- maison-verifier-result:v1 -->\n"
                f"verifier_subject_id: {subject}\nverdict: {verdict}\nblocker_count: {blockers}\n"
                + ("<!-- /maison-verifier-result:v1 -->\n" if close else ""))

    def report(self, text: str) -> None:
        (self.reports / f"verifier.report.{self.SUBJECT}.md").write_text(
            "审查正文\n\n" + text, encoding="utf-8")

    def review(self) -> dict:
        return rc.review_closure("AR1")["plan"]

    def test_the_current_passing_report_taken_in_counts(self) -> None:
        self.summary()
        self.report(self.block(self.SUBJECT))
        self.assertTrue(self.review()["report_adopted"])

    def test_no_report_on_disk_does_not(self) -> None:
        self.summary()
        self.assertFalse(self.review()["report_adopted"])
        self.assertEqual({"present": False}, self.review()["report"])

    def test_a_report_for_another_subject_does_not(self) -> None:
        self.summary()
        self.report(self.block(self.OTHER))
        self.assertFalse(self.review()["report_adopted"])

    def test_an_open_failing_phase_does_not(self) -> None:
        """评审复现的形态：open、FAIL、报告未验证、subject 是当前的、信号为空、没有报告。"""
        self.summary(closure_status="open", verdict="FAIL", report_validity="UNVERIFIED")
        self.assertFalse(self.review()["report_adopted"])

    def test_a_failing_report_does_not(self) -> None:
        self.summary()
        self.report(self.block(self.SUBJECT, "FAIL", "2"))
        self.assertFalse(self.review()["report_adopted"])

    def test_closing_on_a_prior_review_does_not(self) -> None:
        self.summary(verifier_closure={"mode": "completed_with_prior_review"},
                     readiness_signals=[{"id": "semantic_not_reverified"}])
        self.report(self.block(self.SUBJECT))
        self.assertFalse(self.review()["report_adopted"])

    def test_text_after_the_block_does_not_rewrite_it(self) -> None:
        """评审复现：终态块判 FAIL，块外备注里写着 PASS 与 0——终态仍是 FAIL。"""
        self.summary()
        self.report(self.block(self.SUBJECT, "FAIL", "1") + "\n备注\nverdict: PASS\nblocker_count: 0\n")
        review = self.review()
        self.assertFalse(review["report_adopted"])
        self.assertEqual("FAIL", review["report"]["verdict"])

    def test_a_block_without_its_end_marker_is_not_a_result(self) -> None:
        self.summary()
        self.report(self.block(self.SUBJECT, close=False))
        review = self.review()
        self.assertFalse(review["report_adopted"])
        self.assertFalse(review["report"]["valid"])

    def test_two_blocks_are_not_a_result(self) -> None:
        self.summary()
        self.report(self.block(self.SUBJECT) + self.block(self.SUBJECT))
        self.assertFalse(self.review()["report"]["valid"])
        self.assertFalse(self.review()["report_adopted"])

    def test_a_malformed_subject_is_not_a_result(self) -> None:
        self.summary(verifier_subject_id="5a03")
        self.report(self.block("5a03"))
        self.assertFalse(self.review()["report"]["valid"])
        self.assertFalse(self.review()["report_adopted"])

    def test_an_unreadable_report_is_reported_not_raised(self) -> None:
        self.summary()
        self.report(self.block(self.SUBJECT))
        real = Path.read_text

        def read_text(path, *args, **kwargs):
            if path.name.startswith("verifier.report."):
                raise OSError("拒绝访问")
            return real(path, *args, **kwargs)

        with unittest.mock.patch.object(Path, "read_text", read_text):
            review = self.review()
        self.assertFalse(review["report"]["readable"])
        self.assertFalse(review["report_adopted"])


class StoryGatesTellNotRunFromFailed(unittest.TestCase):
    """收尾的 story 门禁：「检查没跑成」与「内容不通过」分开记，同一份输入只跑一次。

    T2 两个 Case 收工之后 node 起不来（0xC0000142、日志为空），被记成 gate_failed；
    事后在同一工作区重跑，检查通过。那是机器的账，不是被测产物的。
    """

    PASS = ("[story-build check] 通过：10 章\n", "", 0)
    CONTENT_FAIL = ("", "[story-build check] 2 处未通过\n", 1)
    PREFLIGHT_FAIL = ("", "[story-build] spec/knowledge-use.yaml 还有 3 条没有判断\n", 1)
    NOT_STARTED = ("", "", 3221225794)
    POST_OK = ('{"ok":true}\n', "", 0)

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        hook = self.tmp / "doc" / "extensions" / "hooks" / "spec" / "post_check.mjs"
        hook.parent.mkdir(parents=True)
        hook.write_text("// 替身\n", encoding="utf-8")
        self.feature = self.tmp / "doc" / "features" / "AR1"
        (self.feature / "AR" / "story-src").mkdir(parents=True)
        (self.feature / "AR" / "story.md").write_text("# story\n", encoding="utf-8")
        self.out = self.tmp / "run"
        self.out.mkdir()
        patcher = unittest.mock.patch.multiple(rc, REPO_ROOT=self.tmp, FEATURES_DIR="doc/features")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.calls = 0
        self.build = self.PASS

    def fake_gate(self, command, *, cwd, log_path, shell=False):
        self.calls += 1
        out, err, code = self.POST_OK if "--input-type=module" in command else self.build
        log_path.write_text(out + err, encoding="utf-8")
        return (subprocess.CompletedProcess(command, code, out, err),
                {"command": command, "returncode": code})

    def run_gates(self, feed=None) -> dict:
        with unittest.mock.patch.object(rc, "_run_logged_gate", self.fake_gate):
            return rc._run_story_gates("AR1", self.out, feed)

    def test_the_verdict_follows_the_output_protocol(self) -> None:
        cases = {self.PASS: "pass", self.CONTENT_FAIL: "fail", self.PREFLIGHT_FAIL: "fail",
                 self.NOT_STARTED: None, ("", "", 1): None, ("随便什么\n", "", 0): None}
        for (out, err, code), want in cases.items():
            with self.subTest(code=code, out=out, err=err):
                self.assertEqual(want, rc._story_build_verdict(
                    subprocess.CompletedProcess([], code, out, err)))
        self.assertIsNone(rc._story_build_verdict(None), "启动异常也是没跑成")
        self.assertIsNone(rc._post_check_verdict(subprocess.CompletedProcess([], 0, "", "")))
        self.assertEqual("fail", rc._post_check_verdict(
            subprocess.CompletedProcess([], 0, '{"ok":false}\n', "")))

    def test_a_check_that_did_not_run_is_absent_not_failed(self) -> None:
        """没跑成的不写进结果——缺席的门禁由现有语义判成 harness_incomplete，不是 gate_failed。"""
        self.build = self.NOT_STARTED
        gates = self.run_gates()
        self.assertNotIn("story_build_check", gates)
        self.assertEqual("pass", gates["post_check"])
        diag = json.loads((self.out / "gate_diagnostics.json").read_text(encoding="utf-8"))
        self.assertEqual("not_run", diag["story_build_check"]["status"])
        self.assertIn("story_build_check",
                      set(rc.expected_gate_names("story", "spec")) - set(gates),
                      "缺席没有落到装置的账上")

    def test_a_real_content_failure_stays_a_failure(self) -> None:
        self.build = self.CONTENT_FAIL
        self.assertEqual("fail", self.run_gates()["story_build_check"])

    def test_the_same_inputs_are_checked_once(self) -> None:
        first = self.run_gates()
        self.assertEqual(2, self.calls)
        self.assertEqual(first, self.run_gates(), "复用的结果与第一次不同")
        self.assertEqual(2, self.calls, "输入一字未变，却又起了检查进程")

    def test_any_input_change_reruns(self) -> None:
        """正文、侧车、检查器实现变了都重跑——旧 PASS 不沿用。"""
        for rel in ("doc/features/AR1/AR/story.md", "doc/features/AR1/AR/story-src/story-template.md",
                    "doc/extensions/hooks/spec/post_check.mjs"):
            with self.subTest(rel=rel):
                self.run_gates()
                before = self.calls
                target = self.tmp / rel
                target.write_text((target.read_text(encoding="utf-8") if target.exists() else "")
                                  + "改了一行\n", encoding="utf-8")
                self.run_gates()
                self.assertEqual(before + 2, self.calls, f"{rel} 变了却复用了旧结果")

    def test_a_run_that_did_not_finish_is_checked_again(self) -> None:
        """没跑成那次不是业务结论，不缓存：环境恢复后下一次调用真的重查、拿到新结论。"""
        self.build = self.NOT_STARTED
        self.assertNotIn("story_build_check", self.run_gates())
        self.build = self.PASS
        gates = self.run_gates()
        self.assertEqual(4, self.calls, "输入没变，但上次没跑成，这次该重查")
        self.assertEqual("pass", gates["story_build_check"])

    def test_a_real_content_failure_is_reused(self) -> None:
        """有效的内容不通过是结论，输入没变就复用。"""
        self.build = self.CONTENT_FAIL
        self.run_gates()
        self.assertEqual("fail", self.run_gates()["story_build_check"])
        self.assertEqual(2, self.calls)

    def test_a_config_change_reruns(self) -> None:
        """检查器按工程配置找扩展与需求目录：配置变了，旧结论不能再用。"""
        self.run_gates()
        (self.tmp / "framework.config.json").write_text(
            json.dumps({"paths": {"extension_dir": "tools/other-ext"}}), encoding="utf-8")
        self.run_gates()
        self.assertEqual(4, self.calls, "改了扩展目录配置却复用了旧结论")

    def test_a_diagnostics_write_failure_reaches_the_host(self) -> None:
        """写不进诊断要让宿主看见（stderr 进 worker.log，再发一条事件），且下次重查。"""
        (self.out / "gate_diagnostics.json").mkdir()
        events = []

        class Feed:
            def emit(self, name, **kw):
                events.append(name)

        with unittest.mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            self.run_gates(Feed())
        self.assertIn("gate_diagnostics.json 写不进去", err.getvalue())
        self.assertIn("gate_diagnostics_write_failed", events)
        self.run_gates(Feed())
        self.assertEqual(4, self.calls, "缓存没落盘却被当成已检查")

    def test_the_second_checkpoint_runs_the_gates_before_waiting(self) -> None:
        src = (SCRIPTS / "run_case.py").read_text(encoding="utf-8")
        at = src.index('result["stop_reason"] = "update_checkpoint"')
        body = src[at:at + 1500]
        self.assertLess(body.index("_run_story_gates"), body.index("wait_at_update_checkpoint"))


class TheOldFakePhaseIsGone(unittest.TestCase):
    def test_story_review_is_not_an_end_phase_anymore(self) -> None:
        self.assertFalse(hasattr(rc, "STORY_REVIEW"))
        self.assertNotIn("story-review", rmc.VALID_END)
