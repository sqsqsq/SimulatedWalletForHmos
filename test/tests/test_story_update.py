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

import atexit
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_story_build import (  # noqa: E402
    FEATURE, FIXTURE, REPO_ROOT, StoryBuildCase, ensure_flow_state,
)
from test_requirement_system import AR, RR, SR, STORY_JS, _env  # noqa: E402
from flow_steps import answer, write_gaps  # noqa: E402
import design_kit  # noqa: E402
from ext_workspace import DEV_EXT, link_framework

FLOW = (DEV_EXT / "skills" / "story" / "scripts"
        / "core" / "story_flow.py")


#: 一份能收口的 update-notes：四段里至少有「不变项与理由」表
NOTES = ("## 当前依据\n读过了。\n\n## 不变项与理由\n\n| 不变项 | 为什么不用改 |\n|---|---|\n"
         "| 验收口径 | 这一轮没有动到它 |\n")


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
        if "prepare" in extra and "--result" not in extra:
            extra = (*extra, "--result", "documents")
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
        """盘上有几轮 —— 只数轮次目录。"""
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

    def test_the_owned_files_are_kept_and_protected_ones_are_not(self) -> None:
        """镜像只留本扩展拥有的文件（恢复据它写回）；受保护的上游原件恢复从不改写，不进镜像。"""
        out = self.update()
        before = self.updates / out["update"] / "before"
        self.assertTrue((before / "AR" / "story.md").is_file(), "镜像里没有 story")
        self.assertFalse((before / "AR" / "design.md").exists(), "受保护的上游原件进了镜像")
        rec = json.loads((self.updates / out["update"] / "record.json").read_text(encoding="utf-8"))
        self.assertIn("AR/story.md", rec["owned_before"])
        self.assertNotIn("AR/design.md", rec["owned_before"])
        self.assertEqual("documents", rec["requested_result"])

    def test_the_mirror_does_not_contain_itself(self) -> None:
        """镜像不复制本层自己的落点——复制了就是把镜像套进镜像，每轮翻一倍。"""
        out = self.update()
        nested = self.updates / out["update"] / "before" / "AR" / "story-src" / "updates"
        self.assertFalse(nested.exists(), "镜像套娃了")

    def test_reports_and_backups_stay_out_of_the_mirror(self) -> None:
        """阶段报告、导入备份与重验过程件不是业务内容；报告的 64 位哈希文件名套进检查点目录
        还会超 Windows 路径上限（预跑 auto 的第二检查点快照第一次就是这么失败的）。"""
        for rel in ("spec/reports/verifier.material." + "a" * 64 + ".json",
                    ".backups/local/prd-20260920.md", "spec/revalidation.json"):
            target = self.feature_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("{}", encoding="utf-8")
        before = self.updates / self.update()["update"] / "before"
        self.assertFalse((before / "spec" / "reports").exists(), "阶段报告进了镜像")
        self.assertFalse((before / ".backups").exists(), "导入备份进了镜像")
        self.assertFalse((before / "spec" / "revalidation.json").exists(), "重验过程件进了镜像")
        self.assertTrue((before / "AR" / "story.md").is_file(), "排除得太宽，业务正文也没了")


class OneRoundAtATime(UpdateCase):
    def test_an_open_round_is_resumed_not_restarted(self) -> None:
        """上一轮还开着就接着做：新镜像会把旧的恢复依据盖掉。"""
        first = self.update()["update"]
        again = self.update()
        self.assertEqual("resume", again["comparison"])
        self.assertEqual(first, again["update"])
        self.assertEqual(1, len(self.rounds()), "开着的时候又建了一轮")


class NothingChangedIsAFactNotAnExit(UpdateCase):
    """八项都没变是交给模型的事实：照常开这一轮，要不要改由模型读原文与人的要求判（U44）。"""

    def setUp(self) -> None:
        super().setUp()
        self.update()
        self.closed = self.close_latest()

    def test_it_says_unchanged_and_still_opens_the_round(self) -> None:
        out = self.update()
        self.assertEqual("unchanged", out["comparison"], out)
        self.assertEqual(2, len(self.rounds()), "没变化就没开轮：人这次的要求没有地方承接")
        self.assertIn("照常收口", out["action"])

    def test_it_does_not_touch_the_earlier_rounds(self) -> None:
        """清理只管本次的临时副本——**历史备份一个字节都不许动**。"""
        keep = self.updates / self.closed / "before" / "AR" / "story.md"
        was = keep.read_bytes()
        self.update()
        self.assertEqual(was, keep.read_bytes(), "上一轮的镜像被这一趟改了")

    def test_an_original_imported_since_the_last_close_is_listed(self) -> None:
        """只取图的原件正文不进八项：它新并进来了就列出来，带没带来业务变化由模型读原件判。"""
        manifest_path = self.src / "materials.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.setdefault("sources", []).append(
            {"file": "改版稿.docx", "sha256": "sha256:0123456789abcdef", "class": "IMAGES", "ingested": True})
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        out = self.update()
        self.assertEqual("changed", out["comparison"], out)
        self.assertEqual(["改版稿.docx"], [s["file"] for s in out["imported"]])
        self.assertIn("改版稿.docx（IMAGES）", out["action"])


class EditsMadeBeforeTheRunAreCaught(UpdateCase):
    #: 人会直接动的交付件。**少盯一份，它的手改就永远检不出来**，
    #: 而且会被报成「无变化」退出——比漏报更糟的是它看起来像结论。
    WATCHED = {
        "AR/review.md": "# 评审记录\n\n首版。\n",
        "AR/story.md": "# 需求故事\n\n首版。\n",
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
        """逐份核：改了哪一份就报哪一份——人读件被评审人或作者直接改过，漏盯的话整轮会报成「没变化」。"""
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
        design = self.feature_root / "AR" / "design.md"
        design.write_text(design.read_text(encoding="utf-8") + "\n<!-- 人手改的一行 -->\n",
                          encoding="utf-8")
        out = self.update()
        self.assertEqual("changed", out["comparison"], out)
        self.assertIn("AR/design.md", out["changed"])

    def test_intermediate_sources_do_not_count(self) -> None:
        """决策登记与契约手改了也不报：报出来只是对人没有意义的几行。"""
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
        core = (DEV_EXT / "skills" / "story" / "scripts" / "core")
        sys.path.insert(0, str(core))
        try:
            from flow import update as update_mod  # noqa: PLC0415
            real = update_mod.registry.file_digest

            def flaky(path):
                if path.name == broken:
                    raise OSError("装作读不出来")
                return real(path)

            with unittest.mock.patch.object(update_mod.registry, "file_digest", flaky):
                return update_mod.cmd_update_prepare(self.feature_root, "documents")
        finally:
            sys.path.remove(str(core))

    def test_it_is_reported_as_a_gap(self) -> None:
        out = self.prepare_with_broken_read("story.md")
        self.assertNotEqual("unchanged", out["comparison"], "读不到却报了无变化")
        self.assertIn("AR/story.md", out["unreadable"], out)
        self.assertIn("这是缺口", out["action"])

    def test_it_is_not_counted_as_removed(self) -> None:
        """上次在、这次读不出来，`removed` 里不许有它——模型会拿着它去删下游功能。"""
        out = self.prepare_with_broken_read("story.md")
        self.assertNotIn("AR/story.md", out["changed"], out)


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

    def test_status_gives_local_paths_and_no_adapter_command(self) -> None:
        """core 只报本地位置：取材命令由 SKILL 指导模型调用，core 不认识对接层的路径与参数。
        本工作区没有 `adapters/` 目录，core 照常工作。"""
        self.assertFalse((self.root / "doc" / "extensions" / "skills" / "story" / "scripts" / "adapters").exists())
        for action in ("status", "inputs"):
            with self.subTest(action):
                out = self.update("--action", action)
                self.assertEqual({"project_root": self.root.resolve().as_posix(),
                                  "feature_root": self.feature_root.resolve().as_posix(),
                                  "inbox": (self.feature_root / "inbox").resolve().as_posix()}, out["paths"])
                self.assertNotIn("fetch", out)
                text = json.dumps(out, ensure_ascii=False)
                self.assertNotIn("story.js", text)
                self.assertNotIn("adapters", text)

    def test_a_system_requirement_without_a_fetch_stops(self) -> None:
        """AC15：系统需求这一轮没取过上游就不报输入，指明取材那一步。"""
        core = DEV_EXT / "skills" / "story" / "scripts" / "core"
        ar = self.feature_root.parent / "AR90008"
        shutil.copytree(self.feature_root, ar)
        sys.path.insert(0, str(core))
        try:
            from flow import update as update_mod  # noqa: PLC0415
            from flow.state import FlowError  # noqa: PLC0415
            with self.assertRaises(FlowError) as caught:
                update_mod.cmd_update_inputs(ar, "AR90008", self.root)
        finally:
            sys.path.remove(str(core))
        self.assertIn("还没取上游", str(caught.exception))

    def test_a_receipt_time_without_a_zone_stops(self) -> None:
        """回执的取材时刻按合同带时区；不带的报流程错误并指明重跑取材，不在比较时刻时崩出类型错误。"""
        core = DEV_EXT / "skills" / "story" / "scripts" / "core"
        ar = self.feature_root.parent / "AR90010"
        shutil.copytree(self.feature_root, ar)
        receipt = {"mode": "fetch", "reqNo": "AR90010", "fetchedAt": "2026-09-23T10:00:00", "items": []}
        (ar / "AR" / "story-src" / "fetched.json").write_text(json.dumps(receipt), encoding="utf-8")
        sys.path.insert(0, str(core))
        try:
            from flow import update as update_mod  # noqa: PLC0415
            from flow.state import FlowError  # noqa: PLC0415
            with self.assertRaises(FlowError) as caught:
                update_mod.cmd_update_inputs(ar, "AR90010", self.root)
        finally:
            sys.path.remove(str(core))
        self.assertIn("带时区", str(caught.exception))

    def test_a_local_requirement_has_no_upstream(self) -> None:
        out = self.update("--action", "inputs")
        self.assertIsNone(out["upstream"])
        self.assertIn("本地需求没有上游", out["action"])

    def test_a_system_requirement_reads_its_receipt(self) -> None:
        """AR 需求按来源展示最近一次取材回执；有没有回执不决定来源。"""
        core = DEV_EXT / "skills" / "story" / "scripts" / "core"
        ar = self.feature_root.parent / "AR90009"
        shutil.copytree(self.feature_root, ar)
        receipt = {"mode": "fetch", "reqNo": "AR90009", "fetchedAt": "2026-09-23T10:00:00Z", "items": []}
        (ar / "AR" / "story-src" / "fetched.json").write_text(json.dumps(receipt), encoding="utf-8")
        sys.path.insert(0, str(core))
        try:
            from flow import update as update_mod  # noqa: PLC0415
            out = update_mod.cmd_update_inputs(ar, "AR90009", self.root)
        finally:
            sys.path.remove(str(core))
        self.assertEqual(receipt, out["upstream"])
        self.assertEqual((ar / "inbox").resolve().as_posix(), out["paths"]["inbox"])

    def test_a_resumed_update_still_gives_the_paths(self) -> None:
        self.update()                                  # 开一轮，不收口
        out = self.update("--action", "inputs")
        self.assertEqual("resume", out["comparison"], out)
        self.assertEqual((self.feature_root / "inbox").resolve().as_posix(), out["paths"]["inbox"])

    def test_paths_follow_the_configured_features_dir_with_spaces(self) -> None:
        """需求目录按 `paths.features_dir` 解析，工程根与需求目录都含空格时也原样给出绝对路径。"""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "my project"
            feature = root / "work items" / "feats" / FEATURE
            (feature / "AR" / "story-src").mkdir(parents=True)
            (root / "framework.config.json").write_text(
                json.dumps({"paths": {"features_dir": "work items/feats"}}), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(FLOW), "update", "--feature", FEATURE,
                                   "--project-root", str(root), "--action", "status"],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
            out = json.loads([l for l in proc.stdout.splitlines() if l.strip().startswith("{")][-1])
        self.assertEqual(root.resolve().as_posix(), out["paths"]["project_root"])
        self.assertEqual((feature / "inbox").resolve().as_posix(), out["paths"]["inbox"])

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

    def notes(self, text: str = NOTES) -> None:
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

    def test_notes_without_the_unchanged_table_do_not_close(self) -> None:
        """AC15：不列不变项与理由就不收口——防的是优化一处、损坏另一处。"""
        self.notes("## 当前依据\n读过了。\n\n## 变化与影响\n改了上限。\n")
        out = self.update("--action", "close")
        self.assertIn("不变项与理由", out.get("error", ""), out)

    def test_closing_keeps_text_for_the_next_comparison(self) -> None:
        self.notes()
        out = self.update("--action", "close")
        self.assertEqual("closed", out.get("status"), out)
        self.assertTrue((self.updates / self.rid / "after").is_dir())
        # 有了 after/，下一轮改动才算得出正文差异（没有它只能说「这几份变了」）
        story = self.feature_root / "AR" / "story.md"
        story.write_text(story.read_text(encoding="utf-8") + "\n新加的一行\n", encoding="utf-8")
        nxt = self.update()
        self.assertGreaterEqual(nxt["diffs"], 1, "有了比较正文却没算出差异")


class RestoreFollowsTheTruthTable(UpdateCase):
    """恢复只动本扩展拥有的文件，逐份按开轮时、本轮完成点与现在的指纹判；受保护件与流程契约的其余字段一个字节不动。"""

    def setUp(self) -> None:
        super().setUp()
        self.rid = self.update()["update"]
        self.story = self.feature_root / "AR" / "story.md"
        self.was = self.story.read_bytes()

    def complete_point(self) -> None:
        """本轮完成点（story 登记或收口）记下的指纹：真实流程里由 `story` 登记与 `close` 写。"""
        core = DEV_EXT / "skills" / "story" / "scripts" / "core"
        sys.path.insert(0, str(core))
        try:
            from flow.update import record_owned_after  # noqa: PLC0415
            self.assertEqual(self.rid, record_owned_after(self.feature_root))
        finally:
            sys.path.remove(str(core))

    def record(self) -> dict:
        return json.loads((self.updates / self.rid / "record.json").read_text(encoding="utf-8"))

    def test_a_registered_change_goes_back_and_a_new_draft_goes_away(self) -> None:
        self.story.write_bytes(self.was + "这一轮改的\n".encode("utf-8"))
        draft = self.src / "drafts" / "这一轮新建的.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("开始之后才有的。\n", encoding="utf-8")
        self.complete_point()
        out = self.update("--action", "restore")
        self.assertEqual("restored", out["status"], out)
        self.assertEqual(self.was, self.story.read_bytes())
        self.assertFalse(draft.exists(), "本轮新建、登记过的草稿没退掉")
        saved = self.feature_root / out["restore_copy"]
        self.assertIn("这一轮改的", (saved / "AR" / "story.md").read_text(encoding="utf-8"), "被退掉的那一版没留下来")
        self.assertIsNone(self.flow("update", "--action", "status")["open"], "没有冲突却没关掉这一轮")

    def test_an_unregistered_change_is_kept_as_a_conflict(self) -> None:
        """没到完成点的改动没有登记的那一版可比：保留现状，列冲突，这一轮照旧开着。"""
        self.story.write_bytes(self.was + "中断稿\n".encode("utf-8"))
        out = self.update("--action", "restore")
        self.assertEqual("restore_conflicted", out["status"], out)
        self.assertIn("中断稿", self.story.read_text(encoding="utf-8"), "冲突的现状被覆盖了")
        row = next(c for c in out["conflicts"] if c["file"] == "AR/story.md")
        self.assertTrue((self.feature_root / row["before"]).is_file(), "没给开轮时那一版")
        self.assertTrue((self.feature_root / row["current"]).is_file(), "没存现在这一版")
        status = self.flow("update", "--action", "status")
        self.assertEqual(self.rid, status["open"])
        self.assertIn("AR/story.md", [c["file"] for c in status["restore_conflicts"]])
        self.assertIn("冲突", self.update("--action", "close").get("error", ""), "有冲突却收口了")

    def test_a_change_after_the_complete_point_is_a_conflict(self) -> None:
        self.story.write_bytes(self.was + "登记过的\n".encode("utf-8"))
        self.complete_point()
        self.story.write_bytes(self.was + "登记之后又改的\n".encode("utf-8"))
        out = self.update("--action", "restore")
        self.assertEqual(["AR/story.md"], [c["file"] for c in out["conflicts"]])
        self.assertIn("登记之后又改的", self.story.read_text(encoding="utf-8"))

    def test_a_resolved_conflict_is_restored_on_the_next_run(self) -> None:
        """人把冲突那份定回开轮时的样子，再跑一次就收掉这一轮。"""
        self.story.write_bytes(self.was + "中断稿\n".encode("utf-8"))
        self.assertEqual("restore_conflicted", self.update("--action", "restore")["status"])
        self.story.write_bytes(self.was)
        out = self.update("--action", "restore")
        self.assertEqual("restored", out["status"], out)
        self.assertEqual([], out["conflicts"])

    def test_protected_bytes_are_never_touched(self) -> None:
        design = self.feature_root / "AR" / "design.md"
        changed = design.read_bytes() + "冻结之后的新版\n".encode("utf-8")
        design.write_bytes(changed)
        self.complete_point()
        out = self.update("--action", "restore")
        self.assertEqual(changed, design.read_bytes(), "受保护件被还原了")
        self.assertNotIn("AR/design.md", [c["file"] for c in out["conflicts"]])

    def test_the_flow_contract_keeps_its_other_fields(self) -> None:
        """流程契约只动开着的这一轮的指针：轮次、人签、设计关联这些字段不随恢复回退。"""
        path = self.src / "story-flow.json"
        core = DEV_EXT / "skills" / "story" / "scripts" / "core"
        sys.path.insert(0, str(core))
        try:
            from flow.state import load, save  # noqa: PLC0415
            contract = load(self.feature_root)
            contract["archived"] = {"at": "2026-09-30T00:00:00+00:00"}
            save(self.feature_root, contract)
        finally:
            sys.path.remove(str(core))
        self.assertEqual("restored", self.update("--action", "restore")["status"])
        flow = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual({"at": "2026-09-30T00:00:00+00:00"}, flow.get("archived"), "契约的其他字段被还原了")
        self.assertEqual({"open": None, "last_restored": self.rid}, flow["update"])


class RestoreRefusesWithoutAScene(UpdateCase):
    """还原不了时说清原因，**当前内容一个字节不动**——不能为了「还原」先把现在的丢了。"""

    def test_nothing_to_restore_when_no_update_was_made(self) -> None:
        spec = self.feature_root / "AR" / "story.md"
        was = spec.read_bytes()
        out = self.update("--action", "restore")
        self.assertIn("没有开着的更新可以还原", out.get("error", ""), out)
        self.assertEqual(was, spec.read_bytes())

    def test_a_missing_scene_is_refused_and_current_content_kept(self) -> None:
        rid = self.update()["update"]
        spec = self.feature_root / "AR" / "story.md"
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

    MARK = "<!-- story-build:begin 议题 D1 · 由决策登记表生成，改它请改真源 · sha256:0123456789abcdef -->"

    def put_issue(self) -> None:
        (self.feature_root / "AR" / "review.md").write_text(
            f"# 评审记录\n\n{self.MARK}\n#### 1.1.1 撤销宽限的时长\n", encoding="utf-8")

    def test_it_needs_an_open_round(self) -> None:
        """不挂在某一轮上的话，事后无从定位这条人签属于哪一次更新。"""
        out = self.decide("--update", "撤销宽限改 36 小时", "--issue", "D1", "--reply", "需求方在评审会上说的")
        self.assertIn("没有开着的更新", out.get("error", ""))

    def test_it_records_the_actual_words_and_the_issue_shown(self) -> None:
        self.update()
        self.put_issue()
        out = self.decide("--update", "撤销宽限改 36 小时", "--issue", "D1", "--reply", "按 36 小时做")
        self.assertEqual("human", out["recorded"]["by"])
        flow = json.loads((self.src / "story-flow.json").read_text(encoding="utf-8"))
        row = flow["update"]["decisions"][0]
        self.assertEqual(("按 36 小时做", "D1", "0123456789abcdef"), (row["reply"], row["issue"], row["asked"]))

    def test_the_words_stay_on_record_after_the_close(self) -> None:
        """收口只清开着的那一轮：这一轮人的每句原话与问法摘要随 record.json 留档。"""
        self.put_issue()
        rid = self.update()["update"]
        self.decide("--update", "撤销宽限改 36 小时", "--issue", "D1", "--reply", "按 36 小时做")
        self.decide("--update", "开关默认关闭", "--issue", "D1", "--reply", "默认关，灰度开关由运营开")
        (self.updates / rid / "update-notes.md").write_text(NOTES, encoding="utf-8")
        self.assertEqual("closed", self.update("--action", "close").get("status"))
        rec = json.loads((self.updates / rid / "record.json").read_text(encoding="utf-8"))
        self.assertEqual([("按 36 小时做", "0123456789abcdef"), ("默认关，灰度开关由运营开", "0123456789abcdef")],
                         [(d["reply"], d["asked"]) for d in rec["decisions"]])
        flow = json.loads((self.src / "story-flow.json").read_text(encoding="utf-8"))
        self.assertNotIn("decisions", flow["update"])

    def test_the_words_stay_on_record_after_a_restore(self) -> None:
        """还原的那一轮同样留档：人说过的话不随现场一起撤回。"""
        self.put_issue()
        rid = self.update()["update"]
        self.decide("--update", "撤销宽限改 36 小时", "--issue", "D1", "--reply", "按 36 小时做")
        self.assertEqual("restored", self.update("--action", "restore").get("status"))
        rec = json.loads((self.updates / rid / "record.json").read_text(encoding="utf-8"))
        self.assertEqual([("按 36 小时做", "0123456789abcdef")],
                         [(d["reply"], d["asked"]) for d in rec["decisions"]])

    def test_it_needs_the_issue(self) -> None:
        self.update()
        self.put_issue()
        out = self.decide("--update", "撤销宽限改 36 小时", "--reply", "按 36 小时做")
        self.assertIn("--issue", out.get("error", ""))
        out = self.decide("--update", "撤销宽限改 36 小时", "--issue", "D9", "--reply", "按 36 小时做")
        self.assertIn("评审记录里没有议题 D9", out.get("error", ""))

    def test_an_empty_reply_is_refused(self) -> None:
        """人签只认真实原话——模型的转述不算。"""
        self.update()
        out = self.decide("--update", "撤销宽限改 36 小时", "--issue", "D1", "--reply", "   ")
        self.assertIn("--reply", out.get("error", ""))


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

    def answer(self, chosen: str = "confirm_scope", reply: str = "不补。") -> dict:
        write_gaps(self.src)
        return answer(self.flow, "material_scope", reply, "--chosen", chosen)

    def test_it_reports_and_stops_at_the_material_gate(self) -> None:
        was = self.rounds()
        out = self.update("--action", "inputs")
        self.assertEqual("inputs", out["stage"], out)
        self.assertEqual((self.feature_root / "inbox").resolve().as_posix(), out["paths"]["inbox"])
        self.assertEqual("inputs", self.contract()["update"]["stage"])
        self.assertEqual("inventory_materials", self.next_of())
        write_gaps(self.src)
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
        self.assertEqual("inventory_materials", self.next_of())

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

    def test_no_supplement_and_nothing_changed_still_opens(self) -> None:
        self.update("--action", "inputs")
        self.answer()
        out = self.update()
        self.assertEqual("unchanged", out["comparison"], out)
        self.assertNotIn("stage", self.contract()["update"], "输入阶段的记号没清，路由会一直停在关卡")
        self.assertEqual(out["update"], self.contract()["update"]["open"])

    def test_a_new_original_in_the_inbox_is_a_change(self) -> None:
        inbox = self.feature_root / "inbox"
        inbox.mkdir(exist_ok=True)
        (inbox / "交通卡自动充值-v2.md").write_text("# 产品需求\n\n单日上限 300。\n", encoding="utf-8")
        out = self.update("--action", "inputs")
        self.assertIn("交通卡自动充值-v2.md", out["pending"], out)
        self.assertEqual("accepted", self.answer("supplied", "新版放进去了")["outcome"])
        self.assertEqual("import_materials", self.next_of(), "有未并入的原件却没先让导入")
        out = self.update()
        self.assertIn("先导入", out.get("error", ""), "AC15：收件箱有未并入的原件时 prepare 要拒绝")
        self.assertIn("交通卡自动充值-v2.md", out["error"])

    def test_inside_an_open_round_every_command_agrees(self) -> None:
        """AC13：update 这一轮开着时，status、round、complete、decide 判定一致。

        新材料登记进当前轮；提取稿改了由 complete 冻结新一版输入、范围沿用已定的；关卡不再问人。
        09-25、09-26 两次实跑都卡在这条序列上。要重拍范围时 reopen 在 update 里同样合法，
        update 照旧开着（锁在 test_material_rounds 的 reopen 用例里）。
        """
        self.update("--action", "inputs")
        self.answer()
        self.update()
        rounds = len(self.contract()["rounds"])
        prd = self.feature_root / "RR" / "prd.md"
        prd.write_text(prd.read_text(encoding="utf-8") + "\n单日上限 300。\n", encoding="utf-8")
        self.assertEqual("refresh_round", self.next_of())
        self.flow("round")
        self.assertEqual(rounds, len(self.contract()["rounds"]), "update 期间开了新轮")
        out = self.flow("decide", "--gate", "scope_decision", "--ask", "x", "--reply", "1")
        self.assertIn("当前这一步不是 scope_decision", out.get("error", ""))
        draft = self.src / "design-draft.md"
        draft.write_text(draft.read_text(encoding="utf-8") + "\n单日上限按改版稿核对。\n", encoding="utf-8")
        done = self.flow("complete", "--from", "AR/story-src/design-draft.md")
        self.assertEqual("complete", done.get("status"), done)
        self.assertTrue(done.get("committed"), done)
        self.assertEqual(rounds, len(self.contract()["rounds"]))


class ConstructionIsReportedNotRequired(UpdateCase):
    """施工归 Framework：阶段闭没闭环只读报告，update 不推进、不因它挡收口。"""

    def test_an_open_phase_is_reported_and_the_round_closes(self) -> None:
        rid = self.update()["update"]
        reports = self.feature_root / "spec" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "summary.json").write_text(json.dumps(
            {"closure_status": "open", "verdict": "FAIL", "verifier_subject_id": "b" * 64}), encoding="utf-8")
        (self.updates / rid / "update-notes.md").write_text(NOTES, encoding="utf-8")
        out = self.update("--action", "close")
        self.assertEqual("closed", out.get("status"), out)
        self.assertEqual([("spec", "open")], [(p["phase"], p["closure"]) for p in out["phases"]])


class TheRequestedResultDecidesTheClose(UpdateCase):
    """本轮终点照人的请求记：只取材与澄清是 materials，要同步人读件是 documents；终点不为收口降级。"""

    def open_round(self, result: str) -> str:
        rid = self.update("--result", result)["update"]
        (self.updates / rid / "update-notes.md").write_text(NOTES, encoding="utf-8")
        return rid

    def test_prepare_needs_the_result(self) -> None:
        out = self.flow("update", "--action", "prepare")
        self.assertIn("--result", out.get("error", ""), out)
        self.assertFalse(self.updates.exists() and self.rounds(), "没记终点却开了轮")

    def test_a_materials_round_closes_without_touching_documents(self) -> None:
        self.open_round("materials")
        out = self.update("--action", "close")
        self.assertEqual("closed", out.get("status"), out)
        self.assertIn("还没有设计或成文", out["action"])

    def test_a_materials_round_that_touched_the_story_does_not_close(self) -> None:
        self.open_round("materials")
        story = self.feature_root / "AR" / "story.md"
        story.write_text(story.read_text(encoding="utf-8") + "\n改了一段\n", encoding="utf-8")
        out = self.update("--action", "close")
        self.assertIn("documents", out.get("error", ""), out)

    def test_the_result_can_grow_but_not_shrink(self) -> None:
        rid = self.open_round("materials")
        self.assertEqual("documents", self.update("--result", "documents")["requested_result"])
        refused = self.update("--result", "materials")
        self.assertIn("不能改成 materials", refused.get("error", ""), refused)
        rec = json.loads((self.updates / rid / "record.json").read_text(encoding="utf-8"))
        self.assertEqual("documents", rec["requested_result"])


class ANewVersionReplacesTheOldOriginal(UpdateCase):
    """同一来源的新版本：旧原件移进 `.backups/local/` 再导入，目标正文只含新版。

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
        backup = self.feature_root / ".backups" / "local"
        backup.mkdir(parents=True, exist_ok=True)
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

    def test_the_adapter_reports_facts_not_core_steps(self) -> None:
        """对接层只报取回、落盘的事实，不提示 core 的下一步命令。"""
        for cmd in (["init", AR, "token"], ["fetch", AR, "token", "--out", str(self.out)]):
            with self.subTest(cmd[0]):
                proc = subprocess.run(["node", str(STORY_JS), *cmd, "--project-root", str(self.project)],
                                      capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
                                      env={**_env(), "STORY_REQUIREMENT_SYSTEM_DIR": str(self.system)})
                self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
                for word in ("story_flow", "story-build", "core/"):
                    self.assertNotIn(word, proc.stdout + proc.stderr)

    def refused(self, ar: str, *extra: str) -> tuple[int, str, str]:
        """参数错：退出码、stdout、stderr——入口只写 stderr，不写 JSON。"""
        proc = subprocess.run(
            ["node", str(STORY_JS), "fetch", ar, "token", "--project-root", str(self.project), *extra],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            env={**_env(), "STORY_REQUIREMENT_SYSTEM_DIR": str(self.system)})
        return proc.returncode, proc.stdout, proc.stderr

    def test_a_local_feature_is_refused(self) -> None:
        """本地单不挂在需求系统上：不访问系统，当场说清楚。"""
        code, out, err = self.refused("local-demo", "--out", str(self.out))
        self.assertNotEqual(0, code)
        self.assertEqual("", out.strip())
        self.assertIn("本地需求", err)

    def test_an_unknown_ticket_leaves_no_placeholder(self) -> None:
        code, receipt = self.fetch("AR-not-exist", "--out", str(self.out))
        self.assertNotEqual(0, code)
        self.assertFalse(self.out.exists(), "查无此单却建了 inbox")

    def test_out_is_required(self) -> None:
        """没有默认落点：默认一个的话，两个单同时更新会写进同一处。"""
        code, out, err = self.refused(AR)
        self.assertNotEqual(0, code)
        self.assertEqual("", out.strip())
        self.assertIn("--out", err)


if __name__ == "__main__":
    unittest.main()


class TheStoryRegistrationLeavesTheFirstBaseline(UpdateCase):
    """成文登记即留基准：第一次 update 也比得出「原来怎么写」，不再永远是 incomplete。"""

    def test_the_first_update_compares_against_the_registered_story(self) -> None:
        core = DEV_EXT / "skills" / "story" / "scripts" / "core"
        sys.path.insert(0, str(core))
        try:
            from flow.update import record_baseline  # noqa: PLC0415
            first = record_baseline(self.feature_root)
            self.assertTrue(first)
            # reopen 后再登记：只有成文基准、没有 update 记录时，基准换成这一次登记的
            (self.src / "updates" / first).rename(self.src / "updates" / "20000101-000000-story")
            second = record_baseline(self.feature_root)
            self.assertTrue(second)
            self.assertEqual([second], sorted(p.name for p in (self.src / "updates").iterdir()),
                             "旧的成文基准没换掉")
        finally:
            sys.path.remove(str(core))
        story = self.feature_root / "AR" / "story.md"
        story.write_text(story.read_text(encoding="utf-8") + "\n登记之后改的一行\n", encoding="utf-8")
        out = self.update()
        self.assertTrue(out["baseline"], out)
        self.assertIn("AR/story.md", out["changed"])


class StoryIsRegisteredAgainAfterChanges(UpdateCase):
    """story 登记之后要改：改完重跑 `story` 就是重新登记，不退状态、不碰流程契约（U39）。

    spec 阶段返修、update 轮内修订、归档后重拍范围三种情形走同一条链；
    09-26 实跑里 update 段卡在 reopen → complete → story 的死路上，模型手改了四次契约。
    """

    BUILD = DEV_EXT / "skills" / "story" / "scripts" / "core" / "story-build.mjs"

    def setUp(self) -> None:
        super().setUp()
        # 夹具的材料清单少一份系统设计，补齐后 story 能过全篇 check
        story = self.feature_root / "AR" / "story.md"
        text = story.read_text(encoding="utf-8")
        row = "- 开发需求：本轮从上游提取的开发需求，业务分工与本单范围。原文：[AR/design.md](design.md)\n"
        self.assertIn(row, text)
        story.write_text(text.replace(row, row + "- 系统设计：接口与端云分工。原文：[SR/design.md](../SR/design.md)\n"),
                         encoding="utf-8")
        # 登记前要经独立审查：审查对象里的章节合同与判据取工程里装的扩展；1.x 的平铺 Spec 产物与蓝图工作区
        # 同在需求目录时原生按歧义拒绝，2.0 的需求目录没有它
        design_kit.install_review_mechanism(self.root, DEV_EXT)
        shutil.rmtree(self.feature_root / "spec", ignore_errors=True)
        self.outputs: list[str] = []

    def run_cmd(self, *args: str) -> subprocess.CompletedProcess:
        proc = subprocess.run(list(args), capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120, cwd=str(self.root))
        self.outputs.append(proc.stdout + proc.stderr)
        return proc

    def register(self) -> dict:
        """定稿并准备审查，夹具审查者给出通过的回复，再登记。"""
        prepared = self.run_cmd("node", str(self.BUILD), "review", "--action", "prepare", "--feature", FEATURE,
                                "--project-root", str(self.root))
        self.assertEqual(0, prepared.returncode, prepared.stdout + prepared.stderr)
        design_kit.write_review(self.root, FEATURE, "pass")
        out = self.flow("story")
        self.outputs.append(json.dumps(out, ensure_ascii=False))
        return out

    def rewrite_background(self, text: str) -> None:
        body = self.root / "chapter.md"
        body.write_text(text + "\n", encoding="utf-8")
        proc = self.run_cmd("node", str(self.BUILD), "chapter", "--feature", FEATURE,
                            "--project-root", str(self.root), "--chapter", "背景", "--from", str(body))
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def contract(self) -> dict:
        return json.loads((self.src / "story-flow.json").read_text(encoding="utf-8"))

    def design_syncs(self) -> None:
        """交给设计的输入换了一版：设计职责在 component-design 里按新输入同步蓝图并重新准入。"""
        design_kit.install_blueprint(self.root, FEATURE, design_kit.ACCESS)

    def mark_archived(self) -> None:
        """归档由数据对接层执行、`archived` 登记要过交付门；这里经契约的读写函数记下标记。"""
        sys.path.insert(0, str(FLOW.parent))
        from flow.state import load, save  # noqa: PLC0415
        contract = load(self.feature_root)
        contract["archived"] = {"at": "2026-09-26T00:00:00+00:00"}
        save(self.feature_root, contract)

    def assert_no_hand_edit(self) -> None:
        for out in self.outputs:
            self.assertNotIn("手改", out)

    def test_spec_stage_change_is_registered_again(self) -> None:
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        self.rewrite_background("支付提交后用户要能看到回执状态。登记之后补的一句。")
        self.assertEqual("register_story", self.flow("status")["next"], "改了章却没指向重新登记")
        again = self.register()
        self.assertTrue(again.get("success"), again)
        self.assertEqual("story_written", self.contract()["status"])
        self.assertNotEqual("register_story", self.flow("status")["next"])
        self.assert_no_hand_edit()

    def test_update_round_change_is_registered_before_close(self) -> None:
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        self.mark_archived()
        rid = self.update()["update"]
        self.rewrite_background("支付提交后用户要能看到回执状态，以服务端为准。")
        (self.updates / rid / "update-notes.md").write_text(NOTES, encoding="utf-8")
        refused = self.update("--action", "close")
        self.assertIn("重新登记", refused.get("error", ""), refused)
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        closed = self.update("--action", "close")
        self.assertEqual("closed", closed.get("status"), closed)
        self.assertTrue(self.contract().get("archived"), "重新登记把归档标记弄丢了")
        status = self.flow("status")
        self.assertEqual("done", status["next"])
        self.assertIn("回写需求系统等人确认", status["action"], "收口之后没说本地已更新、回写待人确认")
        self.assert_no_hand_edit()

    def test_a_recommitted_extract_needs_the_story_registered_again(self) -> None:
        """update 轮内重新提交提取稿：上一次登记随之作废，不重跑 `story` 就不收口。"""
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        self.mark_archived()
        rid = self.update()["update"]
        draft = self.src / "design-draft.md"
        draft.write_text(draft.read_text(encoding="utf-8") + "\n按改版稿核过一遍。\n", encoding="utf-8")
        done = self.flow("complete", "--from", "AR/story-src/design-draft.md")
        self.assertTrue(done.get("committed"), done)
        self.assertEqual("design_blueprint", self.flow("status")["next"], "输入换了版本，蓝图还没按它同步")
        self.design_syncs()
        self.assertEqual("register_story", self.flow("status")["next"])
        (self.updates / rid / "update-notes.md").write_text(NOTES, encoding="utf-8")
        refused = self.update("--action", "close")
        self.assertIn("重新登记", refused.get("error", ""), refused)
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        self.assertEqual("closed", self.update("--action", "close").get("status"))
        self.assert_no_hand_edit()

    def test_rescoping_after_archive_goes_through_the_scope_gate(self) -> None:
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        self.mark_archived()
        reopened = self.flow("reopen")
        self.assertEqual("await_gate:scope_decision", reopened.get("next"), reopened)
        answer(self.flow, "scope_decision", "还是整体承载", "--chosen", "carry_all")
        draft = self.src / "design-draft.md"
        draft.write_text(draft.read_text(encoding="utf-8") + "\n重拍范围后核过一遍。\n", encoding="utf-8")
        (self.src / "design-input.json").write_text(  # 设计输入带重新确认的那条人签
            json.dumps(design_kit.design_input(self.src), ensure_ascii=False), encoding="utf-8")
        done = self.flow("complete", "--from", "AR/story-src/design-draft.md")
        self.assertEqual("complete", done.get("status"), done)
        self.design_syncs()
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        self.assertEqual("story_written", self.contract()["status"])
        self.assert_no_hand_edit()


class RegisteredCase(UpdateCase):
    """已按蓝图成文登记的工程，带一条设计议题。"""

    TARGET = "view:logical/node:wallet-balance"
    TOPIC = {"id": "D1", "status": "open", "review_mode": "choice", "category": "依赖与承载",
             "title": "余额刷新的触发时机待定", "decider": "产品负责人",
             "clarification": "**决策点**：首页余额在什么时候刷新。\n\n**依据**：蓝图写回到首页时刷新，材料没说切账号时怎样。\n\n"
                              "**可选的做法**：\n\n1. 回到首页就刷新——余额总是新的；每次回首页多一次请求。\n"
                              "2. 只在下拉时刷新——请求少；用户可能看到旧余额。\n\n**建议**：选择方案 1（回到首页就刷新）。\n\n"
                              "**理由**：余额是用户最先看的数。",
             "design_target": {"target_ref": TARGET}}

    #: 登记好 story 的工程只做一次（登记要定稿、审查、登记，一次约 4 秒），每条用例复制一份再开 update
    _registered: Path | None = None

    def setUp(self) -> None:
        self.outputs: list[str] = []
        cls = type(self)
        if cls._registered is None:
            super().setUp()
            story = self.feature_root / "AR" / "story.md"
            text = story.read_text(encoding="utf-8")
            row = "- 开发需求：本轮从上游提取的开发需求，业务分工与本单范围。原文：[AR/design.md](design.md)\n"
            story.write_text(text.replace(row, row + "- 系统设计：接口与端云分工。原文：[SR/design.md](../SR/design.md)\n"),
                             encoding="utf-8")
            design_kit.install_review_mechanism(self.root, DEV_EXT)
            shutil.rmtree(self.feature_root / "spec", ignore_errors=True)
            (self.src / "decisions.json").write_text(json.dumps({"decisions": [self.TOPIC]}, ensure_ascii=False), encoding="utf-8")
            self.assertTrue(StoryIsRegisteredAgainAfterChanges.register(self).get("success"), self.outputs[-1])
            cls._registered = Path(tempfile.mkdtemp(prefix="story-update-registered-")) / "work"
            atexit.register(shutil.rmtree, cls._registered.parent, True)
            root = self.root
            shutil.copytree(root, cls._registered, ignore=lambda d, names: ["framework"] if Path(d) == root else [])
        else:
            self._tmp = tempfile.TemporaryDirectory()
            self.addCleanup(self._tmp.cleanup)
            self.root = Path(self._tmp.name) / "work"
            base = cls._registered
            shutil.copytree(base, self.root, ignore=lambda d, names: ["framework"] if Path(d) == base else [])
            link_framework(self.root)
            self.feature_root = self.root / "doc" / "features" / FEATURE
            self.src = self.feature_root / "AR" / "story-src"
            self.updates = self.src / "updates"

    run_cmd = StoryIsRegisteredAgainAfterChanges.run_cmd
    BUILD = StoryIsRegisteredAgainAfterChanges.BUILD


class DesignFeedbackGoesToTheBlueprintOwner(RegisteredCase):
    """评审人对设计议题的意见在 update 里交给蓝图负责方：挂在有设计目标的议题上、带本轮记下的原话、
    指向成文登记时评审的蓝图版本；原生只判够不够格，处理之前一律「待处理」。"""

    def setUp(self) -> None:
        super().setUp()
        self.rid = self.update("--result", "documents")["update"]
        self.revision = json.loads((self.src / "story-flow.json").read_text(encoding="utf-8"))["story_basis"]["blueprint_ref"]["revision"]

    def said(self) -> None:
        proc = subprocess.run([sys.executable, str(FLOW), "decide", "--feature", FEATURE, "--project-root", str(self.root),
                               "--update", "余额刷新时机", "--issue", "D1", "--reply", "切账号时也要刷新"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def feedback(self, **item) -> dict:
        body = {"feedback_id": "D1", "kind": "opinion", "source_revision": self.revision,
                "target_ref": self.TARGET, "body": "切账号时也要刷新余额", **item}
        doc = {"artifact": "blueprint-review-feedback@1", "blueprint_id": design_kit.blueprint_of(self.root, FEATURE),
               "component_id": "wallet-main", "source_revision": self.revision, "items": [body]}
        (self.updates / self.rid / "design-feedback.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return self.update("--action", "feedback")

    def test_a_qualified_opinion_is_pending_until_the_owner_handles_it(self) -> None:
        self.said()
        out = self.feedback()
        self.assertEqual([], out["problems"], out)
        self.assertEqual([("D1", "待处理")], [(x["feedback_id"], x["state"]) for x in out["feedback"]])
        self.assertIn("不写成已接受", out["action"])
        rec = json.loads((self.updates / self.rid / "record.json").read_text(encoding="utf-8"))
        self.assertEqual(self.revision, rec["design_feedback"]["source_revision"])

    def test_a_decision_pointing_at_it_makes_it_handled(self) -> None:
        """蓝图负责方调和之后，蓝图里有决定的来源指向这条反馈：状态读成已处理，带上那条决定。"""
        self.said()
        self.feedback()
        blueprint = design_kit.blueprint_of(self.root, FEATURE)
        canonical = self.root / design_kit.features_dir(self.root) / blueprint / "blueprint" / "component-blueprint.yaml"
        doc = yaml.safe_load(canonical.read_text(encoding="utf-8"))
        doc["decisions_and_gaps"]["decisions"].append({
            "decision_id": "feedback-d1", "kind": "review_feedback", "status": "answered_with_evidence", "owner": "design-author",
            "rationale": "切账号时同样刷新余额", "verification_refs": [self.TARGET],
            "provenance": {"source_kind": "review_feedback", "observed_at": "2026-09-30T00:00:00Z", "evidence_strength": "observed",
                           "extraction_method": "reconcile",
                           "source_ref": f"doc/features/{FEATURE}/AR/story-src/updates/{self.rid}/design-feedback.json#D1"}})
        canonical.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
        design_kit.render_projection(self.root, blueprint, design_kit.ACCESS)
        out = self.update("--action", "feedback")
        self.assertEqual([("D1", "已处理", "feedback-d1")],
                         [(x["feedback_id"], x["state"], x.get("handled_by", {}).get("decision_id")) for x in out["feedback"]], out)

    def test_without_the_human_words_it_is_named(self) -> None:
        self.assertIn("没有记下人的原话", "；".join(self.feedback()["problems"]))

    def test_a_ruling_without_authority_is_not_a_ruling(self) -> None:
        self.said()
        out = self.feedback(kind="authoritative_ruling")
        self.assertIn("review_feedback_authority_insufficient", [i.get("id") for i in out["native_issues"]], out)

    def test_an_old_revision_is_named(self) -> None:
        self.said()
        out = self.feedback(source_revision=self.revision + 1)
        self.assertTrue(any("review_feedback_item_revision_mismatch" == i.get("id") for i in out["native_issues"]), out)

    def test_a_topic_without_a_design_target_stays_on_the_requirement_side(self) -> None:
        self.said()
        topic = {**self.TOPIC}
        topic.pop("design_target")
        (self.src / "decisions.json").write_text(json.dumps({"decisions": [topic]}, ensure_ascii=False), encoding="utf-8")
        self.assertIn("留在需求侧", "；".join(self.feedback()["problems"]))

    def test_a_target_outside_the_blueprint_is_refused_at_registration(self) -> None:
        topic = {**self.TOPIC, "design_target": {"target_ref": "view:logical/node:no-such-node"}}
        (self.src / "decisions.json").write_text(json.dumps({"decisions": [topic]}, ensure_ascii=False), encoding="utf-8")
        proc = self.run_cmd("node", str(self.BUILD), "check", "--feature", FEATURE, "--project-root", str(self.root))
        self.assertIn("不是已准入蓝图", proc.stdout + proc.stderr)


class PublishChecksTheExternalVersion(RegisteredCase):
    """发布前按交付门核资格、用取材回执核外部正文还是不是上次知道的那一版；被别人改过就交人，不直接覆盖。
    本地单没有远端动作。需求系统单由编号决定，这里在进程内把本单当作系统单。"""

    def call(self, name: str, *args, system: bool = True):
        core = DEV_EXT / "skills" / "story" / "scripts" / "core"
        sys.path.insert(0, str(core))
        try:
            from flow import publish  # noqa: PLC0415
            with unittest.mock.patch.object(publish, "system_requirement", lambda _: system):
                return getattr(publish, name)(self.feature_root, *args)
        finally:
            sys.path.remove(str(core))

    def receipt(self, body: bytes | None, when: str = "2099-01-01T00:00:00+00:00", status: str = "fetched") -> None:
        item = {"name": "AR-design.md", "status": status if body is not None else "absent"}
        if body is not None:
            item["digest"] = "sha256:" + hashlib.sha256(body).hexdigest()[:16]
        (self.src / "fetched.json").write_text(json.dumps({"fetchedAt": when, "items": [item]}), encoding="utf-8")

    def publish(self, reply=None) -> dict:
        return self.call("cmd_publish", self.root, reply)

    def error(self, fn, *args) -> str:
        core = DEV_EXT / "skills" / "story" / "scripts" / "core"
        sys.path.insert(0, str(core))
        try:
            from flow.state import FlowError  # noqa: PLC0415
            with self.assertRaises(FlowError) as caught:
                fn(*args)
            return str(caught.exception)
        finally:
            sys.path.remove(str(core))

    def test_a_local_requirement_has_no_remote_action(self) -> None:
        self.assertIn("本地单没有远端动作", self.error(lambda: self.call("cmd_publish", self.root, None, system=False)))

    def test_it_needs_a_fetch_after_the_registration(self) -> None:
        self.assertIn("先取一次材", self.error(self.publish))
        self.receipt((self.feature_root / "AR" / "design.md").read_bytes(), when="2000-01-01T00:00:00+00:00")
        self.assertIn("重新取一次材", self.error(self.publish))

    def test_the_first_publish_starts_from_the_adopted_design(self) -> None:
        self.receipt((self.feature_root / "AR" / "design.md").read_bytes())
        out = self.publish()
        self.assertTrue(out["publishable"], out)
        self.assertIn("首次发布", out["diff"])
        self.assertEqual(["D1 余额刷新的触发时机待定"], out["open_topics"])

    def test_an_external_edit_goes_to_a_person(self) -> None:
        self.receipt("别人在需求系统上改过的正文\n".encode("utf-8"))
        out = self.publish()
        self.assertFalse(out["publishable"], out)
        self.assertIn("不直接覆盖", out["action"])
        confirmed = self.publish("看过了，按本地这一版覆盖")
        self.assertTrue(confirmed["publishable"], confirmed)
        flow = json.loads((self.src / "story-flow.json").read_text(encoding="utf-8"))
        self.assertEqual("看过了，按本地这一版覆盖", flow["publish_overrides"][-1]["reply"])

    def test_after_a_publish_the_published_version_is_the_baseline(self) -> None:
        core = DEV_EXT / "skills" / "story" / "scripts" / "core"
        sys.path.insert(0, str(core))
        try:
            from flow.state import load, save  # noqa: PLC0415
            contract = load(self.feature_root)
            from flow.lifecycle import publication_record  # noqa: PLC0415
            contract["archived"] = publication_record(self.feature_root)
            save(self.feature_root, contract)
        finally:
            sys.path.remove(str(core))
        self.receipt((self.feature_root / "AR" / "story.md").read_bytes(), status="same")
        out = self.publish()
        self.assertTrue(out["publishable"], out)
        self.assertEqual("与上次发布逐字相同", out["diff"])
        self.receipt((self.feature_root / "AR" / "design.md").read_bytes())
        self.assertFalse(self.publish()["publishable"], "发布之后外部回到了旧版却没当成外部改动")

    def test_a_remote_restore_moves_the_external_baseline_and_keeps_local_files(self) -> None:
        self.assertIn("还没归档过", self.error(lambda: self.call("cmd_restored")))
        core = DEV_EXT / "skills" / "story" / "scripts" / "core"
        sys.path.insert(0, str(core))
        try:
            from flow.state import load, save  # noqa: PLC0415
            contract = load(self.feature_root)
            from flow.lifecycle import publication_record  # noqa: PLC0415
            contract["archived"] = publication_record(self.feature_root)
            save(self.feature_root, contract)
        finally:
            sys.path.remove(str(core))
        story = (self.feature_root / "AR" / "story.md").read_bytes()
        older = (self.feature_root / "AR" / "design.md").read_bytes()
        self.receipt(older, status="same")
        out = self.call("cmd_restored")
        self.assertTrue(out["differs"], out)
        self.assertEqual(story, (self.feature_root / "AR" / "story.md").read_bytes(), "远端恢复动了本地文件")
        self.receipt(older, status="same")
        self.assertTrue(self.publish()["publishable"], "恢复之后外部就是恢复的那一版，不该再当成别人改过")
