"""`/story update` 的文件侧支持：先检测再决定要不要模型读，以及只读取材。

这一组锁住的是**确定性的那一半**——变化意味着什么归模型（方法在 `phases/update.md`），
这里只核脚本有没有把事实说准：

  ① 四种去向各走各的：真没变就退出、上一轮开着就不另起、基准缺席不冒充无变化、有变化才往下；
  ② 无变化那一趟**不留任何痕迹**，也不碰历史备份；
  ③ 启动前有人手改过的交付件必须被检出来——判定只看人和上游会动的八项，中间真源不算；
  ④ 读不到的来源单列成缺口，不当成「这份被删了」；
  ⑤ 输入阶段先停在材料关卡问补料，人答了、料登记进本轮才比；
  ⑥ `fetch` 只往本单 inbox 写正文，回执不进 inbox，一个业务文件都不碰；缺席与故障分开。

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
        """不写 `--action` 就是 prepare：多数用例测的是比较本身，输入阶段另有一组。"""
        if "--action" not in extra:
            extra = ("--action", "prepare", *extra)
        return self.flow("update", *extra)

    def flow(self, mode: str, *extra: str) -> dict:
        proc = subprocess.run(
            [sys.executable, str(FLOW), mode, "--feature", FEATURE,
             "--project-root", str(self.root), *extra],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        rows = [l for l in proc.stdout.splitlines() if l.strip().startswith("{")]
        self.assertTrue(rows, f"stdout 里没有结果 JSON：{proc.stdout}\n{proc.stderr}")
        return json.loads(rows[-1])

    def rounds(self) -> list[str]:
        """盘上有几轮 —— **只数轮次目录**。

        `updates/` 下还有一份 `.last-prepare.json`：那是 prepare 留的机械痕迹
        （点开头、过程件），说的是「这一次检测完了、结论是什么」，不是一轮更新。
        把它数进来的话，「无变化那一趟没有新建一轮」这条判据就永远红。
        """
        return sorted(d.name for d in self.updates.iterdir()
                      if d.is_dir() and not d.name.startswith("."))

    def close_latest(self) -> str:
        """把最后一轮标成 closed——正常由 C2 的 `close` 做，这里只为构造「上次已处理的版本」。"""
        latest = self.updates / self.rounds()[-1]
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

    def test_reports_and_backups_stay_out_of_the_mirror(self) -> None:
        """阶段报告、导入备份与重验过程件不是业务内容；报告的 64 位哈希文件名套进检查点目录
        还会超 Windows 路径上限（预跑 auto 的第二检查点快照第一次就是这么失败的）。"""
        for rel in ("spec/reports/verifier.material." + "a" * 64 + ".json",
                    ".backup/prd-20260920.md", "spec/revalidation.json"):
            target = self.feature_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("{}", encoding="utf-8")
        before = self.updates / self.update()["update"] / "before"
        self.assertFalse((before / "spec" / "reports").exists(), "阶段报告进了镜像")
        self.assertFalse((before / ".backup").exists(), "导入备份进了镜像")
        self.assertFalse((before / "spec" / "revalidation.json").exists(), "重验过程件进了镜像")
        self.assertTrue((before / "spec" / "spec.md").is_file(), "排除得太宽，业务正文也没了")


class OneRoundAtATime(UpdateCase):
    def test_an_open_round_is_resumed_not_restarted(self) -> None:
        """上一轮还开着就接着做：新镜像会把旧的恢复依据盖掉。"""
        first = self.update()["update"]
        again = self.update()
        self.assertEqual("resume", again["comparison"])
        self.assertEqual(first, again["update"])
        self.assertEqual(1, len(self.rounds()), "开着的时候又建了一轮")


class NothingChangedMeansNothingHappens(UpdateCase):
    def setUp(self) -> None:
        super().setUp()
        self.update()
        self.closed = self.close_latest()

    def test_it_says_unchanged_and_leaves_no_trace(self) -> None:
        out = self.update()
        self.assertEqual("unchanged", out["comparison"], out)
        self.assertEqual([self.closed], self.rounds(), "无变化那一趟留下了临时目录")

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
    #: 人会直接动的交付件。**少盯一份，它的手改就永远检不出来**，
    #: 而且会被报成「无变化」退出——比漏报更糟的是它看起来像结论。
    WATCHED = {
        "AR/review.md": "# 评审记录\n\n首版。\n",
        "plan/plan.md": "# 设计\n\n首版。\n",
    }
    #: 模型据交付件写出来的中间真源：随交付件的修订而变，是结果不是原因，不进判定。
    DERIVED = {
        "AR/story-src/decisions.json": '{"decisions": []}\n',
        "contracts.yaml": "contracts: []\n",
    }

    def setUp(self) -> None:
        super().setUp()
        # 基准要在「人动手之前」建好，所以这几份先写进去再跑第一轮。
        for rel, text in {**self.WATCHED, **self.DERIVED}.items():
            target = self.feature_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        self.update()
        self.close_latest()

    def test_every_watched_product_shows_up_when_hand_edited(self) -> None:
        """逐份核：改了哪一份就报哪一份。

        `plan/plan.md` 是 plan 单的常改处（car 就是 plan 单），漏掉它的话，
        一次 plan 阶段的 update 会整个报成「没变化」。
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

    def test_intermediate_sources_do_not_count(self) -> None:
        """决策登记与强契约手改了也不报：报出来只是对人没有意义的几行。
        人要直接改强契约，那是 framework 的修正入口，不是 update。"""
        for rel in self.DERIVED:
            target = self.feature_root / rel
            target.write_text(target.read_text(encoding="utf-8") + "# 手改\n", encoding="utf-8")
        self.assertEqual("unchanged", self.update()["comparison"])

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
        self.assertTrue(out["fetch"].replace("\\", "/").endswith(f"{FEATURE}/inbox"), out["fetch"])
        self.assertIn("--project-root", out["fetch"], "回执会跟着脚本位置落到别的工程里")

    def test_a_local_feature_has_no_fetch(self) -> None:
        """本地单不挂在需求系统上：没有这条命令，输入阶段直接问补料。"""
        core = REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts" / "core"
        sys.path.insert(0, str(core))
        try:
            from flow import update as update_mod  # noqa: PLC0415
            self.assertIsNone(update_mod._fetch_command(self.feature_root, "local-demo", self.root))
        finally:
            sys.path.remove(str(core))

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


class RestoreRefusesWithoutAScene(UpdateCase):
    """还原不了时说清原因，**当前内容一个字节不动**——不能为了「还原」先把现在的丢了。"""

    def test_nothing_to_restore_when_no_update_was_made(self) -> None:
        spec = self.feature_root / "spec" / "spec.md"
        was = spec.read_bytes()
        out = self.update("--action", "restore")
        self.assertIn("没有做过 update", out.get("error", ""), out)
        self.assertEqual(was, spec.read_bytes())

    def test_a_missing_scene_is_refused_and_current_content_kept(self) -> None:
        rid = self.update()["update"]
        spec = self.feature_root / "spec" / "spec.md"
        spec.write_text(spec.read_text(encoding="utf-8") + "\n这一轮改的\n", encoding="utf-8")
        was = spec.read_bytes()
        shutil.rmtree(self.updates / rid / "before")
        out = self.update("--action", "restore")
        self.assertIn("没有留下 before/", out.get("error", ""), out)
        self.assertEqual(was, spec.read_bytes(), "还原失败却改了当前内容")


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


class TheInputsStageAsksFirst(UpdateCase):
    """一次 update 先报输入、在材料关卡问一次要不要补料，人答了才比（D21）。

    关卡、侧车、人签、登记全是 init 第一级那一套；答的那一笔记在当前轮，不开新轮。
    """

    def setUp(self) -> None:
        super().setUp()
        self.update()
        self.close_latest()

    def contract(self) -> dict:
        return json.loads((self.src / "story-flow.json").read_text(encoding="utf-8"))

    def next_of(self) -> str:
        return self.flow("status")["next"]

    def answer(self, chosen: str = "confirm_scope", basis: str = "不补。") -> dict:
        sys.path.insert(0, str(FLOW.parent))
        from flow.inputs import material_options  # noqa: PLC0415
        (self.src / ".gate-options.json").write_text(json.dumps(
            {"gate": "material_scope", "options": [dict(o) for o in material_options()]},
            ensure_ascii=False), encoding="utf-8")
        return self.flow("decide", "--gate", "material_scope", "--chosen", chosen, "--basis", basis)

    def test_it_reports_and_stops_at_the_material_gate(self) -> None:
        was = self.rounds()
        out = self.update("--action", "inputs")
        self.assertEqual("inputs", out["stage"], out)
        self.assertIn("fetch", out)
        self.assertEqual("inputs", self.contract()["update"]["stage"])
        self.assertEqual("await_gate:material_scope", self.next_of())
        self.assertEqual(was, self.rounds(), "输入阶段只报告，却建了一轮")

    def test_the_earlier_answer_is_not_this_one(self) -> None:
        """init 那一笔不是这一次的回答——哪怕时刻看起来在后面。

        时刻只精确到秒，夹具里 init 的关卡与输入阶段常在同一秒（手工实跑就撞上了）。
        按时刻比会把上一次的回答当成这一次的，材料关卡整个被跳过。
        """
        flow = self.contract()
        for gate in flow["rounds"][-1]["gates"]:
            gate["at"] = "2999-01-01T00:00:00+00:00"
        (self.src / "story-flow.json").write_text(json.dumps(flow, ensure_ascii=False), encoding="utf-8")
        self.update("--action", "inputs")
        self.assertEqual("await_gate:material_scope", self.next_of())

    def test_prepare_waits_for_the_answer(self) -> None:
        self.update("--action", "inputs")
        self.assertIn("补料", self.update().get("error", ""))

    def test_the_answer_goes_into_the_same_round(self) -> None:
        rounds = len(self.contract()["rounds"])
        self.update("--action", "inputs")
        out = self.answer()
        self.assertEqual("accepted", out["outcome"], out)
        self.assertEqual(rounds, len(self.contract()["rounds"]), "答补料开了新轮")
        gates = [g for g in self.contract()["rounds"][-1]["gates"] if g["gate"] == "material_scope"]
        self.assertEqual(2, len(gates), "这一笔没追加到本轮")
        self.assertEqual("update_prepare", self.next_of())

    def test_no_supplement_and_nothing_changed_is_unchanged(self) -> None:
        self.update("--action", "inputs")
        self.answer()
        out = self.update()
        self.assertEqual("unchanged", out["comparison"], out)
        self.assertNotIn("stage", self.contract()["update"], "输入阶段的记号没清，路由会一直停在关卡")
        mark = json.loads((self.updates / ".last-prepare.json").read_text(encoding="utf-8"))
        self.assertEqual("unchanged", mark["comparison"])

    def test_a_new_original_in_the_inbox_is_a_change(self) -> None:
        inbox = self.feature_root / "inbox"
        inbox.mkdir(exist_ok=True)
        (inbox / "交通卡自动充值-v2.md").write_text("# 产品需求\n\n单日上限 300。\n", encoding="utf-8")
        out = self.update("--action", "inputs")
        self.assertIn("交通卡自动充值-v2.md", out["pending"], out)
        self.assertEqual("accepted", self.answer("supplied", "新版放进去了")["outcome"])
        self.assertEqual("import_materials", self.next_of(), "有未并入的原件却没先让导入")
        out = self.update()
        self.assertEqual("changed", out["comparison"], out)
        self.assertIn("交通卡自动充值-v2.md", out["pending"])

    def test_after_reopen_the_route_is_the_revision_not_the_gates(self) -> None:
        self.update("--action", "inputs")
        self.answer()
        self.assertEqual("changed", self.update("--request", "把单日上限改成 300")["comparison"])
        self.flow("reopen")
        self.assertEqual("update_in_progress", self.next_of())


class CloseKnowsWhetherTheReviewWasAdopted(UpdateCase):
    """收口前逐阶段看审查闭环：报告写了、判 PASS，阶段却仍沿用历史 → 不收口。

    framework 不改写已闭环的 summary，`--sync-closure` 输出「已闭环」也不代表报告被采纳了；
    只有再跑一次完整 harness 才会采纳（C5 实验）。正式 T2 两个模型都据「已闭环」报了完成。
    """

    SUBJECT = "a" * 64

    def setUp(self) -> None:
        super().setUp()
        self.rid = self.update()["update"]
        (self.updates / self.rid / "update-notes.md").write_text("## 当前依据\n读过了。\n", encoding="utf-8")
        self.reports = self.feature_root / "spec" / "reports"
        self.reports.mkdir(parents=True, exist_ok=True)
        (self.reports / f"verifier.report.{self.SUBJECT}.md").write_text(
            "审查正文。\n\n<!-- maison-verifier-result:v1 -->\n"
            f"verifier_subject_id: {self.SUBJECT}\nverdict: PASS\nblocker_count: 0\n"
            "<!-- /maison-verifier-result:v1 -->\n", encoding="utf-8")

    def summary(self, adopted: bool) -> None:
        body = {"closure_status": "closed", "verdict": "PASS", "verifier_subject_id": self.SUBJECT,
                "readiness_signals": [] if adopted else [{"id": "semantic_not_reverified"}]}
        if not adopted:
            body["verifier_closure"] = {"mode": "completed_with_prior_review"}
        (self.reports / "summary.json").write_text(json.dumps(body), encoding="utf-8")

    def test_a_written_but_unadopted_report_blocks_the_close(self) -> None:
        self.summary(adopted=False)
        out = self.update("--action", "close")
        self.assertIn("没被采纳", out.get("error", ""), out)
        self.assertIn("--phase", out["error"])

    def test_an_adopted_report_closes_and_the_facts_come_back(self) -> None:
        self.summary(adopted=True)
        out = self.update("--action", "close")
        self.assertEqual("closed", out.get("status"), out)
        spec = [f for f in out["phases"] if f["phase"] == "spec"][0]
        self.assertIsNone(spec["closure_mode"])
        self.assertEqual([], spec["signals"])

    def test_no_report_is_not_this_guard(self) -> None:
        """没派审（无变化、只改过程记录）时仍能收口：守卫只管「报告在却没被采纳」。"""
        (self.reports / f"verifier.report.{self.SUBJECT}.md").unlink()
        self.summary(adopted=False)
        out = self.update("--action", "close")
        self.assertEqual("closed", out.get("status"), out)
        self.assertEqual("completed_with_prior_review", out["phases"][0]["closure_mode"])


class ClosedPhasesMustStayClosed(UpdateCase):
    """开这一轮时已闭环的阶段，收口时要仍然闭环；本来没闭环的阶段不是这一轮要推进的。

    完整跑一次 harness 时，报告对不上当前 subject 或判 FAIL，阶段会回到 open（1.9.5 plan 实验）。
    此前的守卫只拦「报告在、却沿用历史」，拦不住这一种——一轮更新会带着没闭环的阶段收口。
    """

    def summary(self, phase: str, closure: str) -> None:
        reports = self.feature_root / phase / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "summary.json").write_text(json.dumps(
            {"closure_status": closure, "verdict": "PASS", "verifier_subject_id": "b" * 64,
             "readiness_signals": []}), encoding="utf-8")

    def open_round(self) -> None:
        rid = self.update()["update"]
        (self.updates / rid / "update-notes.md").write_text("## 当前依据\n读过了。\n", encoding="utf-8")

    def test_a_phase_reopened_by_this_round_blocks_the_close(self) -> None:
        self.summary("spec", "closed")
        self.open_round()
        self.summary("spec", "open")
        out = self.update("--action", "close")
        self.assertIn("spec（仍未闭环）", out.get("error", ""), out)

    def test_a_vanished_summary_blocks_the_close(self) -> None:
        self.summary("spec", "closed")
        self.open_round()
        (self.feature_root / "spec" / "reports" / "summary.json").unlink()
        self.assertIn("spec（summary 不见了）", self.update("--action", "close").get("error", ""))

    def test_a_phase_that_was_never_closed_does_not_block(self) -> None:
        """Plan 本来就在途：这一轮只更新已有产物，不负责把它推到闭环。"""
        self.summary("spec", "closed")
        self.summary("plan", "open")
        self.open_round()
        out = self.update("--action", "close")
        self.assertEqual("closed", out.get("status"), out)


class ANewVersionReplacesTheOldOriginal(UpdateCase):
    """同一来源的新版本：旧原件移进 `.backup/` 再导入，目标正文只含新版。

    导入链的不变量是「某类目标全文 = 该类 inbox 原件按名拼接」，没有「替代」语义；
    旧原件留在 inbox 的话，`RR/prd.md` 就是两版拼在一起（预跑里 auto 为了躲开它把 v2 归成了 AR）。
    """

    def import_all(self, classes: dict[str, str]) -> None:
        inbox = self.feature_root / "inbox"
        (inbox / ".classify.json").write_text(json.dumps(classes, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(FLOW.parent / "import_sources.py"), "--feature", FEATURE,
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def test_only_the_new_version_lands(self) -> None:
        inbox = self.feature_root / "inbox"
        inbox.mkdir(exist_ok=True)
        (inbox / "产品原稿-v1.md").write_text("# 产品需求\n\n单日上限 200。\n", encoding="utf-8")
        self.import_all({"产品原稿-v1.md": "RR"})
        (inbox / "RR-prd.md").write_text("# 产品需求\n\n单日上限 300。\n", encoding="utf-8")
        hint = self.update("--action", "inputs")["superseded_hint"]
        self.assertEqual([{"new": "RR-prd.md", "same_class": ["产品原稿-v1.md"]}],
                         [{k: h[k] for k in ("new", "same_class")} for h in hint],
                         "没提示同类的旧原件")
        backup = self.feature_root / ".backup"
        backup.mkdir(exist_ok=True)
        (inbox / "产品原稿-v1.md").rename(backup / "产品原稿-v1.md")
        self.import_all({"RR-prd.md": "RR"})
        prd = (self.feature_root / "RR" / "prd.md").read_text(encoding="utf-8")
        self.assertIn("单日上限 300", prd)
        self.assertNotIn("单日上限 200", prd, "旧版还拼在正文里")
        self.assertTrue((backup / "产品原稿-v1.md").is_file(), "旧原件被删了，不是移走")


class FetchOnlyWritesToTheInbox(unittest.TestCase):
    """只读取材：三份正文放本单 inbox，与人补的料走同一条导入链；业务文件一个字节都不碰。"""

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
        self.out = self.feature / "inbox"
        self.src = self.feature / "AR" / "story-src"

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
        self.assertFalse((self.out / "review-feedback.md").exists(),
                         "评审回稿不是需求正文，进了 inbox 就没有类别可归")
        self.assertTrue((self.src / "review-feedback.md").is_file())

    def test_the_receipt_says_where_each_one_came_from(self) -> None:
        self.fetch(AR, "--out", str(self.out))
        self.assertEqual([], list(self.out.glob("*.json")), "回执进了 inbox，会被当成材料导入")
        receipt = json.loads((self.src / "fetched.json").read_text(encoding="utf-8"))
        prd = [i for i in receipt["items"] if i["name"] == "RR-prd.md"][0]
        self.assertEqual(f"{RR}/prd.md", prd["origin"])
        self.assertTrue(prd["digest"].startswith("sha256:"))

    def test_what_equals_the_local_copy_is_not_dropped_in(self) -> None:
        """与本地逐字相同的不落盘：放进去它就是一份「未并入的原件」，每次 update 都被报成新料。
        本单系统正文与本地 story 相同，就是自己归档上去的那一版。"""
        (self.feature / "RR").mkdir()
        (self.feature / "RR" / "prd.md").write_text("# 产品需求\n\n单日上限 200。\n", encoding="utf-8")
        (self.feature / "AR" / "story.md").write_text("# 开发需求\n\n上游先填了一版。\n",
                                                      encoding="utf-8")
        code, receipt = self.fetch(AR, "--out", str(self.out))
        self.assertEqual(0, code, receipt)
        states = {i["name"]: i["status"] for i in receipt["items"]}
        self.assertEqual("same", states["RR-prd.md"])
        self.assertEqual("same", states["AR-design.md"])
        self.assertEqual(["SR-design.md"], sorted(f.name for f in self.out.iterdir()))

    def test_a_local_feature_is_refused(self) -> None:
        """本地单不挂在需求系统上：不取 token、不访问系统，当场说清楚。"""
        code, receipt = self.fetch("local-demo", "--out", str(self.out))
        self.assertNotEqual(0, code)
        self.assertIn("本地单", receipt["error"])

    def test_an_unknown_ticket_leaves_no_placeholder(self) -> None:
        code, receipt = self.fetch("AR-not-exist", "--out", str(self.out))
        self.assertNotEqual(0, code)
        self.assertFalse(self.out.exists(), "查无此单却建了 inbox")

    def test_out_is_required(self) -> None:
        """没有默认落点：默认一个的话，两个单同时更新会写进同一处。"""
        code, receipt = self.fetch(AR)
        self.assertNotEqual(0, code)
        self.assertIn("--out", receipt["error"])


if __name__ == "__main__":
    unittest.main()
