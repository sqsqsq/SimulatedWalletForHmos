"""`/story update` 的文件侧支持：先检测再决定要不要模型读，以及只读取材。

这一组锁住的是**确定性的那一半**——变化意味着什么归模型（方法在 `phases/update.md`），
这里只核脚本有没有把事实说准：

  ① 四种去向各走各的：真没变就退出、上一轮开着就不另起、基准缺席不冒充无变化、有变化才往下；
  ② 无变化那一趟**不留任何痕迹**，也不碰历史备份；
  ③ 启动前有人手改过的文件必须被检出来——只比材料指纹的话，产物那几份改了看不见；
  ④ 读不到的来源单列成缺口，不当成「这份被删了」；
  ⑤ `fetch` 只往暂存区写，一个业务文件都不碰；缺席与故障分开。

测不了的是「这次变化该怎么改」——那要读原文，归模型与真实运行。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_story_build import (  # noqa: E402
    FEATURE, FIXTURE, REPO_ROOT, StoryBuildCase, ensure_flow_state,
)
from test_requirement_system import AR, RR, SR, STORY_JS, _env  # noqa: E402

FLOW = (REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts"
        / "core" / "story_flow.py")


class UpdateCase(unittest.TestCase):
    """每个用例一份新工作区：update 会往需求目录里写镜像。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        shutil.copytree(FIXTURE, self.root)
        self.feature_root = self.root / "doc" / "features" / FEATURE
        self.src = self.feature_root / "AR" / "story-src"
        ensure_flow_state(self.root, FEATURE, self.src, StoryBuildCase.DRAFT)
        self.updates = self.src / "updates"

    def update(self, *extra: str) -> dict:
        proc = subprocess.run(
            [sys.executable, str(FLOW), "update", "--feature", FEATURE,
             "--project-root", str(self.root), *extra],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        rows = [l for l in proc.stdout.splitlines() if l.strip().startswith("{")]
        self.assertTrue(rows, f"stdout 里没有结果 JSON：{proc.stdout}\n{proc.stderr}")
        return json.loads(rows[-1])

    def close_latest(self) -> str:
        """把最后一轮标成 closed——正常由 C2 的 `close` 做，这里只为构造「上次已处理的版本」。"""
        latest = sorted(self.updates.iterdir())[-1]
        rec = json.loads((latest / "record.json").read_text(encoding="utf-8"))
        rec["status"] = "closed"
        (latest / "record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
        return latest.name


class TheFirstRunHasNoBaseline(UpdateCase):
    def test_no_previous_version_is_incomplete_not_unchanged(self) -> None:
        """首次没有可比的版本：说清「说不出原来怎么写」，**不许报无变化**。

        报成无变化的话，第一次 update 会直接退出，而它恰恰是最该看一遍的那一次。
        """
        out = self.update()
        self.assertEqual("incomplete", out["comparison"], out)
        self.assertFalse(out["baseline"])
        self.assertIn("没有上次已处理的版本", out["action"])

    def test_the_scene_before_this_run_is_kept_whole(self) -> None:
        out = self.update()
        before = self.updates / out["update"] / "before"
        self.assertTrue((before / "spec" / "spec.md").is_file(), "镜像里没有 spec")
        self.assertTrue((before / "AR" / "story.md").is_file(), "镜像里没有 story")

    def test_the_mirror_does_not_contain_itself(self) -> None:
        """镜像不复制本层自己的落点——复制了就是把镜像套进镜像，每轮翻一倍。"""
        out = self.update()
        nested = self.updates / out["update"] / "before" / "AR" / "story-src" / "updates"
        self.assertFalse(nested.exists(), "镜像套娃了")


class OneRoundAtATime(UpdateCase):
    def test_an_open_round_is_resumed_not_restarted(self) -> None:
        """上一轮还开着就接着做：新镜像会把旧的恢复依据盖掉。"""
        first = self.update()["update"]
        again = self.update()
        self.assertEqual("resume", again["comparison"])
        self.assertEqual(first, again["update"])
        self.assertEqual(1, len(list(self.updates.iterdir())), "开着的时候又建了一轮")


class NothingChangedMeansNothingHappens(UpdateCase):
    def setUp(self) -> None:
        super().setUp()
        self.update()
        self.closed = self.close_latest()

    def test_it_says_unchanged_and_leaves_no_trace(self) -> None:
        out = self.update()
        self.assertEqual("unchanged", out["comparison"], out)
        self.assertEqual([self.closed], [d.name for d in self.updates.iterdir()],
                         "无变化那一趟留下了临时目录")

    def test_it_does_not_touch_the_earlier_rounds(self) -> None:
        """清理只管本次的临时副本——**历史备份一个字节都不许动**。"""
        keep = self.updates / self.closed / "before" / "spec" / "spec.md"
        was = keep.read_bytes()
        self.update()
        self.assertEqual(was, keep.read_bytes(), "上一轮的镜像被这一趟改了")

    def test_an_explicit_request_is_not_a_no_op(self) -> None:
        """文件没变不等于没事做：人明确要求改一件事时照样往下走。"""
        out = self.update("--request", "把单日上限从 200 改成 300")
        self.assertEqual("changed", out["comparison"], out)
        self.assertIn("有人明确要求改的事", out["action"])


class EditsMadeBeforeTheRunAreCaught(UpdateCase):
    #: 人可能直接动、又决定下游成不成立的那几份。**少盯一份，它的手改就永远检不出来**，
    #: 而且会被报成「无变化」退出——比漏报更糟的是它看起来像结论。
    WATCHED = {
        "AR/review.md": "# 评审记录\n\n首版。\n",
        "spec/knowledge-use.yaml": "entries: []\n",
        "AR/story-src/decisions.json": '{"decisions": []}\n',
        "AR/story-src/story-template.md": "# 写作设计\n\n## 阅读主线\n\n先看这里。\n",
        "plan/plan.md": "# 设计\n\n首版。\n",
        "contracts.yaml": "contracts: []\n",
        "use-cases.yaml": "use_cases: []\n",
    }

    def setUp(self) -> None:
        super().setUp()
        # 基准要在「人动手之前」建好，所以这几份先写进去再跑第一轮。
        for rel, text in self.WATCHED.items():
            target = self.feature_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        self.update()
        self.close_latest()

    def test_every_watched_product_shows_up_when_hand_edited(self) -> None:
        """逐份核：改了哪一份就报哪一份。

        `plan/plan.md` 与根目录那两份强契约是 plan 单的常改处（car 就是 plan 单），
        漏掉它们的话，一次 plan 阶段的 update 会整个报成「没变化」。
        `contracts.yaml` / `use-cases.yaml` **在需求根目录不在 `plan/` 下**，按目录名猜会全盘落空。
        """
        for rel in self.WATCHED:
            with self.subTest(rel=rel):
                target = self.feature_root / rel
                target.write_text(target.read_text(encoding="utf-8") + "\n# 人手改的一行\n",
                                  encoding="utf-8")
                out = self.update()
                self.assertEqual("changed", out["comparison"], out)
                self.assertIn(rel, out["changed"], out)
                # 每一轮都要关掉，否则下一份会撞上 resume。
                self.close_latest()

    def test_a_hand_edited_product_shows_up(self) -> None:
        """有人在起跑前直接改了产物——只比材料指纹的话，这一笔永远看不见。"""
        spec = self.feature_root / "spec" / "spec.md"
        spec.write_text(spec.read_text(encoding="utf-8") + "\n<!-- 人手改的一行 -->\n",
                        encoding="utf-8")
        out = self.update()
        self.assertEqual("changed", out["comparison"], out)
        self.assertIn("spec/spec.md", out["changed"])

    def test_a_removed_product_is_reported_as_removed(self) -> None:
        (self.feature_root / "AR" / "review.md").unlink()
        out = self.update()
        self.assertIn("AR/review.md", out["changed"], out)


class UnreadableIsAGapNotADeletion(UpdateCase):
    """在盘上、但读不出来——这是缺口，**不是「它被删了」，更不是「没有变化」**。

    这一条要在进程内跑：让某一份的读取抛 OSError，子进程里没法构造。
    """

    def setUp(self) -> None:
        super().setUp()
        self.update()
        self.close_latest()

    def prepare_with_broken_read(self, broken: str) -> dict:
        core = (REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts" / "core")
        sys.path.insert(0, str(core))
        try:
            from flow import update as update_mod  # noqa: PLC0415
            real = update_mod.registry.file_digest

            def flaky(path):
                if path.name == broken:
                    raise OSError("装作读不出来")
                return real(path)

            with unittest.mock.patch.object(update_mod.registry, "file_digest", flaky):
                return update_mod.cmd_update_prepare(self.feature_root)
        finally:
            sys.path.remove(str(core))

    def test_it_is_reported_as_a_gap(self) -> None:
        out = self.prepare_with_broken_read("spec.md")
        self.assertNotEqual("unchanged", out["comparison"], "读不到却报了无变化")
        self.assertIn("spec/spec.md", out["unreadable"], out)
        self.assertIn("这是缺口", out["action"])

    def test_it_is_not_counted_as_removed(self) -> None:
        """上次在、这次读不出来，`removed` 里不许有它——模型会拿着它去删下游功能。"""
        out = self.prepare_with_broken_read("spec.md")
        self.assertNotIn("spec/spec.md", out["changed"], out)


class StatusReportsFactsNotJudgement(UpdateCase):
    """`status` 只报事实：有没有开着的、说明在不在、阶段闭没闭环。"""

    def test_it_says_there_is_nothing_open(self) -> None:
        out = self.update("--action", "status")
        self.assertIsNone(out["open"])
        self.assertEqual(0, out["rounds"])

    def test_it_points_at_the_open_round_and_asks_for_notes(self) -> None:
        rid = self.update()["update"]
        out = self.update("--action", "status")
        self.assertEqual(rid, out["open"])
        self.assertIsNone(out["notes"], "还没写说明却说有")
        self.assertIn("update-notes", out["action"])

    def test_the_fetch_command_comes_from_the_script(self) -> None:
        """取材落点由脚本给，模型不自己拼 `--out`——拼了就能指到需求目录外面。"""
        out = self.update("--action", "status")
        self.assertIn("--out", out["fetch"])
        self.assertIn("AR/story-src/incoming", out["fetch"].replace("\\", "/"))

    def test_phase_facts_come_from_the_harness_summary(self) -> None:
        reports = self.feature_root / "spec" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "summary.json").write_text(
            json.dumps({"phase": "spec", "verdict": "PASS", "closure_status": "closed"}),
            encoding="utf-8")
        out = self.update("--action", "status")
        self.assertEqual("closed", out["phases"][0]["closure"])

    def test_an_unreadable_summary_is_not_guessed(self) -> None:
        """闭没闭环不许猜——猜错的方向永远是「以为闭了」。"""
        reports = self.feature_root / "spec" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "summary.json").write_text("{坏的", encoding="utf-8")
        out = self.update("--action", "status")
        self.assertFalse(out["phases"][0]["readable"])
        self.assertNotIn("closure", out["phases"][0])


class ClosingBindsTheNotes(UpdateCase):
    def setUp(self) -> None:
        super().setUp()
        self.rid = self.update()["update"]

    def notes(self, text: str = "## 当前依据\n首版。\n") -> None:
        (self.updates / self.rid / "update-notes.md").write_text(text, encoding="utf-8")

    def test_no_notes_no_close(self) -> None:
        """没有说明就收口的话，下一轮拿到的基准背后没有任何解释。"""
        out = self.update("--action", "close")
        self.assertIn("update-notes", out.get("error", ""))
        rec = json.loads((self.updates / self.rid / "record.json").read_text(encoding="utf-8"))
        self.assertEqual("open", rec["status"], "没收口成却把记录改了")

    def test_empty_notes_do_not_count(self) -> None:
        self.notes("   \n\n")
        self.assertIn("update-notes", self.update("--action", "close").get("error", ""))

    def test_closing_keeps_text_for_the_next_comparison(self) -> None:
        self.notes()
        out = self.update("--action", "close")
        self.assertEqual("closed", out["status"])
        self.assertTrue((self.updates / self.rid / "after").is_dir())
        # 有了 after/，下一轮改动才算得出正文差异（没有它只能说「这几份变了」）
        spec = self.feature_root / "spec" / "spec.md"
        spec.write_text(spec.read_text(encoding="utf-8") + "\n新加的一行\n", encoding="utf-8")
        nxt = self.update()
        self.assertGreaterEqual(nxt["diffs"], 1, "有了比较正文却没算出差异")


class RestoreKeepsBothSides(UpdateCase):
    def setUp(self) -> None:
        super().setUp()
        self.rid = self.update()["update"]
        self.spec = self.feature_root / "spec" / "spec.md"

    def test_it_puts_the_scene_back_and_saves_what_came_after(self) -> None:
        self.spec.write_text(self.spec.read_text(encoding="utf-8") + "\n这一轮改的\n",
                             encoding="utf-8")
        later = self.feature_root / "AR" / "story-src" / "这一轮新建的.md"
        later.write_text("开始之后才有的。\n", encoding="utf-8")

        out = self.update("--action", "restore")
        self.assertEqual("restored", out["status"])
        self.assertNotIn("这一轮改的", self.spec.read_text(encoding="utf-8"))
        self.assertFalse(later.exists(), "这一轮之后新建的文件没被还原掉")
        saved = self.updates / self.rid / Path(out["conflict_copy"]).name
        self.assertIn("这一轮改的", (saved / "spec" / "spec.md").read_text(encoding="utf-8"),
                      "被覆盖的那一版没留下来")
        self.assertTrue((saved / "AR" / "story-src" / "这一轮新建的.md").is_file())

    def test_our_own_bookkeeping_is_not_reported_as_a_conflict(self) -> None:
        """流程契约里那一笔记号是本层自己写的。报成冲突的话，真冲突会被这条噪声埋掉。"""
        out = self.update("--action", "restore")
        self.assertNotIn("AR/story-src/story-flow.json", out["conflicts"])


class AHumanDecisionInThisRoundIsRecordedVerbatim(UpdateCase):
    def decide(self, *extra: str) -> dict:
        proc = subprocess.run(
            [sys.executable, str(FLOW), "decide", "--feature", FEATURE,
             "--project-root", str(self.root), *extra],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        rows = [l for l in proc.stdout.splitlines() if l.strip().startswith("{")]
        return json.loads(rows[-1])

    def test_it_needs_an_open_round(self) -> None:
        """不挂在某一轮上的话，事后无从定位这条人签属于哪一次更新。"""
        out = self.decide("--update", "撤销宽限改 36 小时", "--basis", "需求方在评审会上说的")
        self.assertIn("没有开着的更新", out.get("error", ""))

    def test_it_records_the_actual_words(self) -> None:
        self.update()
        out = self.decide("--update", "撤销宽限改 36 小时", "--basis", "需求方原话：按 36 小时做")
        self.assertEqual("human", out["recorded"]["by"])
        flow = json.loads((self.src / "story-flow.json").read_text(encoding="utf-8"))
        self.assertEqual("需求方原话：按 36 小时做", flow["update"]["decisions"][0]["basis"])

    def test_an_empty_basis_is_refused(self) -> None:
        """人签只认真实原话——模型的转述不算。"""
        self.update()
        out = self.decide("--update", "撤销宽限改 36 小时", "--basis", "   ")
        self.assertIn("--basis", out.get("error", ""))


class FetchOnlyWritesToTheStagingArea(unittest.TestCase):
    """只读取材：取回来放暂存，业务文件一个字节都不碰。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.system, self.project = root / "system", root / "project"
        self.feature = self.project / "doc" / "features" / AR
        for no, detail in ((RR, {"reqNo": RR, "type": "RR", "title": "产品需求"}),
                           (SR, {"reqNo": SR, "type": "SR", "title": "系统设计", "rrNo": RR}),
                           (AR, {"reqNo": AR, "type": "AR", "title": "开发需求",
                                 "parentNo": SR, "rrNo": RR})):
            (self.system / no).mkdir(parents=True)
            (self.system / no / "detail.json").write_text(
                json.dumps(detail, ensure_ascii=False), encoding="utf-8")
        (self.system / RR / "prd.md").write_text("# 产品需求\n\n单日上限 200。\n", encoding="utf-8")
        (self.system / SR / "design.md").write_text("# 系统设计\n\n三方分工。\n", encoding="utf-8")
        (self.system / AR / "design.md").write_text("# 开发需求\n\n上游先填了一版。\n",
                                                    encoding="utf-8")
        (self.feature / "AR").mkdir(parents=True)
        self.review = self.feature / "AR" / "review.md"
        self.review.write_text("# 评审记录\n\n人已经写过的意见。\n", encoding="utf-8")
        self.out = self.feature / "AR" / "story-src" / "incoming"

    def fetch(self, ar: str = AR, *extra: str) -> tuple[int, dict]:
        proc = subprocess.run(
            ["node", str(STORY_JS), "fetch", ar, "token", "--project-root", str(self.project),
             *extra],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            env={**_env(), "STORY_REQUIREMENT_SYSTEM_DIR": str(self.system)})
        rows = [l for l in proc.stdout.splitlines() if l.strip().startswith("{")]
        self.assertTrue(rows, f"stdout 里没有回执：{proc.stdout}\n{proc.stderr}")
        return proc.returncode, json.loads(rows[-1])

    def test_absent_is_not_failure(self) -> None:
        """系统上没有评审回稿是常态；把它算成失败，正常的一次取材就永远退不出 0。"""
        code, receipt = self.fetch(AR, "--out", str(self.out))
        self.assertEqual(0, code, receipt)
        states = {i["name"]: i["status"] for i in receipt["items"]}
        self.assertEqual("absent", states["review-feedback.md"])
        self.assertEqual(3, receipt["fetched"])

    def test_it_does_not_overwrite_the_human_notes(self) -> None:
        was = self.review.read_text(encoding="utf-8")
        (self.system / AR / "review-feedback.md").write_text("撤销宽限改为 36 小时。\n",
                                                             encoding="utf-8")
        code, receipt = self.fetch(AR, "--out", str(self.out))
        self.assertEqual(0, code)
        self.assertEqual(4, receipt["fetched"])
        self.assertEqual(was, self.review.read_text(encoding="utf-8"),
                         "取回评审回稿时覆盖了 AR/review.md")
        self.assertTrue((self.out / "review-feedback.md").is_file())

    def test_the_receipt_says_where_each_one_came_from(self) -> None:
        self.fetch(AR, "--out", str(self.out))
        receipt = json.loads((self.out / "fetched.json").read_text(encoding="utf-8"))
        prd = [i for i in receipt["items"] if i["name"] == "RR-prd.md"][0]
        self.assertEqual(f"{RR}/prd.md", prd["origin"])
        self.assertTrue(prd["digest"].startswith("sha256:"))

    def test_a_local_feature_is_refused(self) -> None:
        """本地单不挂在需求系统上：不取 token、不访问系统，当场说清楚。"""
        code, receipt = self.fetch("local-demo", "--out", str(self.out))
        self.assertNotEqual(0, code)
        self.assertIn("本地单", receipt["error"])

    def test_an_unknown_ticket_leaves_no_placeholder(self) -> None:
        code, receipt = self.fetch("AR-not-exist", "--out", str(self.out))
        self.assertNotEqual(0, code)
        self.assertFalse(self.out.exists(), "查无此单却建了暂存目录")

    def test_out_is_required(self) -> None:
        """没有默认落点：默认一个的话，两个单同时更新会写进同一处。"""
        code, receipt = self.fetch(AR)
        self.assertNotEqual(0, code)
        self.assertIn("--out", receipt["error"])


if __name__ == "__main__":
    unittest.main()
