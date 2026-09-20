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

import json
import shutil
import sys
import tempfile
import unittest
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
        body: dict = {"schema": 3, "rounds": []}
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


class TheOldFakePhaseIsGone(unittest.TestCase):
    def test_story_review_is_not_an_end_phase_anymore(self) -> None:
        self.assertFalse(hasattr(rc, "STORY_REVIEW"))
        self.assertNotIn("story-review", rmc.VALID_END)
