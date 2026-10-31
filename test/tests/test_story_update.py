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
import inspect
import json
import re
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
from flow_steps import answer, open_decision, write_gaps  # noqa: E402
import design_kit  # noqa: E402
import shared_state  # noqa: E402
from ext_workspace import DEV_EXT, link_framework

FLOW = (DEV_EXT / "skills" / "story" / "scripts"
        / "core" / "story_flow.py")


#: 一份能收口的 update-notes：四段里至少有「不变项与理由」表
NOTES = ("## 当前依据\n读过了。\n\n## 不变项与理由\n\n| 不变项 | 为什么不用改 |\n|---|---|\n"
         "| 验收口径 | 这一轮没有动到它 |\n")


#: 交给设计之后那份工作区的键：夹具、开发版扩展、造状态的脚本与 Framework 版本
WALKED = shared_state.digest(FIXTURE, *shared_state.COMMON, Path(__file__).with_name("flow_steps.py"),
                             FEATURE, shared_state.framework_version())


def import_into(root: Path, feature_root: Path, files: dict[str, tuple[bytes, str]]) -> None:
    """往来源收件箱放件、写归类，经真实导入命令导成材料版本。"""
    inbox = feature_root / "sources" / "inbox"
    classify = {}
    for rel, (body, cls) in files.items():
        (inbox / rel).parent.mkdir(parents=True, exist_ok=True)
        (inbox / rel).write_bytes(body)
        classify[rel] = cls
    (inbox / ".classify.json").write_text(json.dumps(classify, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(FLOW.parent / "import_sources.py"), "--feature", FEATURE,
                           "--project-root", str(root)], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def cite_latest_prd(feature_root: Path) -> None:
    """作者把材料表里产品需求那一行改成新取得的版本（材料表按各来源最新版本核对）。"""
    story = feature_root / "AR" / "story.md"
    story.write_text(story.read_text(encoding="utf-8").replace("sources/prd-v1/prd.md", "sources/prd-v2/prd.md"),
                     encoding="utf-8")


class UpdateCase(unittest.TestCase):
    """每个用例一份新工作区：update 会往需求目录里写镜像。

    走完交给设计的状态（夹具 → `before_init` → 真实流程命令走完 S1–S3 并提交提取稿）整轮只造一次（shared_state），各用例复制；
    改写了 `before_init` 的类按它自己的源码另造一份。
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        own = type(self).before_init is not UpdateCase.before_init
        name, key = ("update-walked", WALKED) if not own else (
            f"update-walked-{type(self).__name__}", shared_state.digest(WALKED, Path(inspect.getfile(type(self)))))
        shared_state.copy_tree(shared_state.shared_tree(name, key, self._walk), self.root)
        link_framework(self.root)
        self.feature_root = self.root / "doc" / "features" / FEATURE
        self.src = self.feature_root / "AR" / "story-src"
        self.updates = self.src / "updates"

    def _walk(self, base: Path) -> None:
        shutil.copytree(FIXTURE, base)
        link_framework(base)                 # 使用记录按原生身份认需求：init 之前的 begin 也要接上 Framework
        own = self.root, getattr(self, "feature_root", None)
        self.root, self.feature_root = base, base / "doc" / "features" / FEATURE     # 钩子按 self.root 操作：指向在造的这一份
        try:
            self.before_init()
        finally:
            self.root, self.feature_root = own
        ensure_flow_state(base, FEATURE, base / "doc" / "features" / FEATURE / "AR" / "story-src")

    def before_init(self) -> None:
        """夹具走 story init 之前的一步：多数用例什么也不做。"""

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
        """只取图的原件也是一个来源：上次收口以来新导入的就列出来，带没带来业务变化由模型读原件判。"""
        docx = REPO_ROOT / "test" / "cases" / "auto-topup" / "supplements" / "交通卡自动充值.docx"
        import_into(self.root, self.feature_root, {"改版稿.docx": (docx.read_bytes(), "IMAGES")})
        self.flow("round")
        out = self.update()
        self.assertEqual("changed", out["comparison"], out)
        self.assertEqual([("local:改版稿.docx", "IMAGES")], [(s["source_id"], s["class"]) for s in out["imported"]])
        self.assertIn(f"{out['imported'][0]['dir']}（IMAGES）", out["action"])


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

    def test_a_new_upstream_version_shows_up(self) -> None:
        """上游来源取得了新版本：按来源身份报出来，不按文件路径猜。"""
        prd = self.feature_root / "sources" / "prd-v1" / "prd.md"
        import_into(self.root, self.feature_root, {"RR/prd.md": (prd.read_bytes() + "\n补一句。\n".encode("utf-8"), "RR")})
        out = self.update()
        self.assertEqual("changed", out["comparison"], out)
        self.assertIn("source:local:RR/prd.md", out["changed"])

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
                return update_mod.cmd_update_prepare(self.feature_root, FEATURE, "documents")
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


class StatusReportsFactsNotJudgementCase(UpdateCase):
    """`status` 只报事实：有没有开着的、说明在不在、阶段闭没闭环。"""


class StatusReportsFactsNotJudgement(StatusReportsFactsNotJudgementCase):
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
                inbox = (self.feature_root / "sources" / "inbox").resolve().as_posix()
                self.assertEqual({"project_root": self.root.resolve().as_posix(),
                                  "feature_root": self.feature_root.resolve().as_posix(), "inbox": inbox},
                                 {k: v for k, v in out["paths"].items() if k != "fetch_batch"})
                self.assertTrue(out["paths"]["fetch_batch"].startswith(inbox + "/fetch-"), out["paths"])
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


class StatusReportsFactsNotJudgementPart2(StatusReportsFactsNotJudgementCase):
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
        self.assertEqual((ar / "sources" / "inbox").resolve().as_posix(), out["paths"]["inbox"])

    def test_a_resumed_update_still_gives_the_paths(self) -> None:
        self.update()                                  # 开一轮，不收口
        out = self.update("--action", "inputs")
        self.assertEqual("resume", out["comparison"], out)
        self.assertEqual((self.feature_root / "sources" / "inbox").resolve().as_posix(), out["paths"]["inbox"])

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
        self.assertEqual((feature / "sources" / "inbox").resolve().as_posix(), out["paths"]["inbox"])

    def test_without_a_design_link_there_are_no_units(self) -> None:
        self.assertEqual([], self.update("--action", "status")["units"])


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
        changed = {}
        for rel in ("sources/design-v1/design.md", "blueprint/component-blueprint.yaml"):
            target = self.feature_root / rel
            changed[rel] = target.read_bytes() + "开轮之后被改的字节\n".encode("utf-8")
            target.write_bytes(changed[rel])
        self.complete_point()
        out = self.update("--action", "restore")
        for rel, data in changed.items():
            self.assertEqual(data, (self.feature_root / rel).read_bytes(), f"受保护件 {rel} 被还原了")
            self.assertNotIn(rel, [c["file"] for c in out["conflicts"]])

    def test_design_files_and_the_framework_keep_their_bytes(self) -> None:
        """这一轮里新写的蓝图侧文件与 Framework 都不是本扩展拥有的文件：恢复不删、不改，也不列冲突。"""
        frozen = self.feature_root / "blueprint" / "requirement-source-materialization.json"
        frozen.write_text('{"artifact": "in-round"}\n', encoding="utf-8")
        framework = self.root / "framework"

        def tree(base: Path) -> dict[str, bytes]:
            return {p.relative_to(base).as_posix(): p.read_bytes() for p in base.rglob("*") if p.is_file()} if base.is_dir() else {}

        before = tree(framework)
        self.complete_point()
        out = self.update("--action", "restore")
        self.assertEqual('{"artifact": "in-round"}\n', frozen.read_text(encoding="utf-8"), "蓝图侧文件被恢复动了")
        self.assertFalse(any(c["file"].startswith("blueprint/") for c in out["conflicts"]))
        self.assertEqual(before, tree(framework), "恢复改了 Framework 的字节")

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


class RestoreKeepsTheReviewersWords(UpdateCase):
    """评审记录的人工区归人：撤回时有人写过意见的 Review 保留现状、列成冲突，不整文件退回或删掉；只有机器内容的照真值表处理。"""

    ISSUE = ("<!-- story-build:begin 议题 D1 · 由决策登记表生成，改它请改真源 · sha256:0123456789abcdef -->\n"
             "#### 1.1.1 余额刷新的触发时机\n\n请产品负责人评审。\n\n")
    EMPTY = "评审结论：\n- [ ] 同意\n- [ ] 需修改\n- [ ] 暂缓\n修改意见：\n\n<!-- decision: D1 -->\n"
    FILLED = "评审结论：\n- [ ] 同意\n- [x] 需修改\n- [ ] 暂缓\n修改意见：切账号时也要刷新。\n\n<!-- decision: D1 -->\n"

    def review(self) -> Path:
        return self.feature_root / "AR" / "review.md"

    def write(self, human: str) -> bytes:
        body = f"# 评审记录\n\n{self.ISSUE}{human}".encode("utf-8")
        self.review().write_bytes(body)
        return body

    def complete_point(self) -> None:
        core = DEV_EXT / "skills" / "story" / "scripts" / "core"
        sys.path.insert(0, str(core))
        try:
            from flow.update import record_owned_after  # noqa: PLC0415
            record_owned_after(self.feature_root)
        finally:
            sys.path.remove(str(core))

    def test_a_new_review_with_the_reviewers_words_is_kept(self) -> None:
        self.review().unlink(missing_ok=True)
        self.update()
        filled = self.write(self.FILLED)
        self.complete_point()
        out = self.update("--action", "restore")
        self.assertEqual("restore_conflicted", out["status"], out)
        self.assertEqual(filled, self.review().read_bytes(), "本轮收到的人工意见随撤回丢了")
        row = next(c for c in out["conflicts"] if c["file"] == "AR/review.md")
        self.assertIn("D1", row["why"])

    def test_an_existing_review_with_the_reviewers_words_is_not_rolled_back(self) -> None:
        self.write(self.EMPTY)
        self.update()
        filled = self.write(self.FILLED)
        self.complete_point()
        out = self.update("--action", "restore")
        self.assertEqual("restore_conflicted", out["status"], out)
        self.assertEqual(filled, self.review().read_bytes(), "人工意见被退回开轮时的空区")

    def test_a_review_with_only_machine_content_follows_the_table(self) -> None:
        was = self.write(self.EMPTY)
        self.update()
        self.review().write_bytes(was.replace("请产品负责人评审。".encode("utf-8"), "请端侧负责人评审。".encode("utf-8")))
        self.complete_point()
        out = self.update("--action", "restore")
        self.assertEqual("restored", out["status"], out)
        self.assertEqual(was, self.review().read_bytes())


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

    def exported(self) -> dict:
        """最新导出的人答记录（answers.json）。"""
        index = json.loads((self.src / "materials.json").read_text(encoding="utf-8"))
        answers = next(s for s in index["sources"] if s["kind"] == "answer")
        return json.loads((self.feature_root / answers["versions"][-1]["original"]["path"]).read_text(encoding="utf-8"))

    def test_the_answer_is_exported_with_the_issue_shown(self) -> None:
        """人在 update 里定的事一记下就导出：当前有效组里有原话与当时看到的议题正文。"""
        self.update()
        self.put_issue()
        self.decide("--update", "撤销宽限改 36 小时", "--issue", "D1", "--reply", "按 36 小时做")
        [row] = [d for d in self.exported()["current"] if d.get("issue") == "D1"]
        self.assertEqual(("撤销宽限改 36 小时", "按 36 小时做"), (row["item"], row["reply"]))
        self.assertIn("撤销宽限的时长", row["question"])

    def test_a_restored_round_keeps_the_answer_for_context(self) -> None:
        """本地撤回不撤销人的业务决定：原话留在「需结合上下文」组并说明出处，不再算当前有效。"""
        self.put_issue()
        self.update()
        self.decide("--update", "撤销宽限改 36 小时", "--issue", "D1", "--reply", "按 36 小时做")
        self.assertEqual("restored", self.update("--action", "restore").get("status"))
        answers = self.exported()
        self.assertEqual([], [d for d in answers["current"] if d.get("issue") == "D1"])
        [row] = [d for d in answers["context"] if d.get("issue") == "D1"]
        self.assertEqual("按 36 小时做", row["reply"])
        self.assertIn("撤回", row["why"])

    def test_a_changed_issue_moves_the_answer_to_context(self) -> None:
        """议题在评审记录里换了问法：旧原话不冒充对新问法的回答，移到「需结合上下文」组。"""
        self.update()
        self.put_issue()
        self.decide("--update", "撤销宽限改 36 小时", "--issue", "D1", "--reply", "按 36 小时做")
        (self.feature_root / "AR" / "review.md").write_text(
            "# 评审记录\n\n" + self.MARK.replace("0123456789abcdef", "fedcba9876543210")
            + "\n#### 1.1.1 撤销宽限的时长与通知\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(FLOW), "round", "--feature", FEATURE, "--project-root", str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        [row] = [d for d in self.exported()["context"] if d.get("issue") == "D1"]
        self.assertIn("问法", row["why"])

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
        self.assertEqual((self.feature_root / "sources" / "inbox").resolve().as_posix(), out["paths"]["inbox"])
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
        inbox = self.feature_root / "sources" / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        (inbox / "交通卡自动充值-v2.md").write_text("# 产品需求\n\n单日上限 300。\n", encoding="utf-8")
        out = self.update("--action", "inputs")
        self.assertIn("交通卡自动充值-v2.md", out["pending"], out)
        self.assertEqual("accepted", self.answer("supplied", "新版放进去了")["outcome"])
        self.assertEqual("import_materials", self.next_of(), "有未并入的原件却没先让导入")
        out = self.update()
        self.assertIn("先导入", out.get("error", ""), "AC15：收件箱有未并入的原件时 prepare 要拒绝")
        self.assertIn("交通卡自动充值-v2.md", out["error"])

    def test_inside_an_open_round_every_command_agrees(self) -> None:
        """AC13：update 这一轮开着时，status、round、decide 判定一致。

        新材料登记进当前轮，范围沿用已定的；关卡不再问人。
        09-25、09-26 两次实跑都卡在这条序列上。要重拍范围时 reopen 在 update 里同样合法，
        update 照旧开着（锁在 test_material_rounds 的 reopen 用例里）。
        """
        self.update("--action", "inputs")
        self.answer()
        self.update()
        rounds = len(self.contract()["rounds"])
        prd = self.feature_root / "sources" / "prd-v1" / "prd.md"
        import_into(self.root, self.feature_root, {"RR/prd.md": (prd.read_bytes() + "\n单日上限 300。\n".encode("utf-8"), "RR")})
        self.assertEqual("refresh_round", self.next_of())
        self.flow("round")
        self.assertEqual(rounds, len(self.contract()["rounds"]), "update 期间开了新轮")
        out = self.flow("decide", "--gate", "scope_decision", "--ask", "x", "--reply", "1")
        self.assertIn("当前这一步不是 scope_decision", out.get("error", ""))
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
        self.assertEqual([], out["units"], "没有设计关联时施工事实为空，不挡收口")


class ConstructionFactsComeFromTheUnits(unittest.TestCase):
    """施工事实按需求关联的蓝图逐个施工单位读：身份与目录由原生读蓝图时给出，阶段读 harness 自己写的 summary。"""

    @classmethod
    def setUpClass(cls) -> None:
        from test_knowledge_task import BLUEPRINT, make_project  # noqa: PLC0415 —— 真实蓝图与施工单位的工程
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = make_project(root=Path(cls._tmp.name) / "p")
        cls.unit = cls.root / "doc" / "features" / BLUEPRINT / "balance-refresh"
        # 需求与蓝图同根：需求目录就是蓝图所在的那一个
        feature_root = cls.root / "doc" / "features" / BLUEPRINT
        (feature_root / "AR" / "story-src").mkdir(parents=True)
        cls.feature = BLUEPRINT
        core = DEV_EXT / "skills" / "story" / "scripts" / "core"
        sys.path.insert(0, str(core))
        try:
            from flow.state import save  # noqa: PLC0415
            save(feature_root, {"schema": 6, "status": "gathering", "rounds": []})
        finally:
            sys.path.remove(str(core))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def status(self) -> dict:
        proc = subprocess.run([sys.executable, str(FLOW), "update", "--feature", self.feature, "--project-root", str(self.root),
                               "--action", "status"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        return json.loads([l for l in proc.stdout.splitlines() if l.strip().startswith("{")][-1])

    def summary(self, text: str) -> None:
        reports = self.unit / "spec" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "summary.json").write_text(text, encoding="utf-8")

    def test_each_unit_reports_its_phases(self) -> None:
        self.summary(json.dumps({"verdict": "PASS", "closure_status": "closed"}))
        [unit] = self.status()["units"]
        self.assertEqual("balance-refresh", unit["change_unit_id"])
        self.assertTrue(unit["feature_id"].startswith("cu-"))
        self.assertEqual([("spec", "closed")], [(p["phase"], p["closure"]) for p in unit["phases"]])

    def test_an_unreadable_summary_is_not_guessed(self) -> None:
        """闭没闭环不许猜——猜错的方向永远是「以为闭了」。"""
        self.summary("{坏的")
        [phase] = self.status()["units"][0]["phases"]
        self.assertFalse(phase["readable"])
        self.assertNotIn("closure", phase)


    def test_a_configured_report_dir_is_where_the_phase_is_read(self) -> None:
        """工程配置了 reports_dir_pattern：按原生给的目录读，默认目录里的旧 summary 不算。"""
        config = self.root / "framework.config.json"
        original = config.read_bytes()
        self.addCleanup(config.write_bytes, original)
        data = json.loads(original)
        data.setdefault("paths", {})["reports_dir_pattern"] = "doc/reviews/<feature>/<phase>"
        config.write_text(json.dumps(data), encoding="utf-8")
        self.summary(json.dumps({"verdict": "FAIL", "closure_status": "open"}))
        custom = self.root / "doc" / "reviews" / self.unit.relative_to(self.root / "doc" / "features") / "plan"
        custom.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, self.root / "doc" / "reviews", True)
        (custom / "summary.json").write_text(json.dumps({"verdict": "PASS", "closure_status": "closed"}), encoding="utf-8")
        [unit] = self.status()["units"]
        self.assertEqual([("plan", "closed")], [(p["phase"], p["closure"]) for p in unit["phases"]],
                         "默认目录的 summary 被当成了本阶段的，或配置目录没读")

    def test_a_closed_phase_without_fresh_evidence_is_listed_as_stale(self) -> None:
        """summary 写着闭环，原生证据此刻却不新鲜：不算这一轮的完成，按单位列出过期阶段与接手动作。"""
        self.summary(json.dumps({"verdict": "PASS", "closure_status": "closed"}))
        out = self.status()
        [unit] = out["units"]
        [phase] = unit["phases"]
        self.assertNotEqual("fresh", phase["evidence"])
        self.assertFalse(phase["current"])
        [stale] = out["stale_units"]
        self.assertEqual(("balance-refresh", "spec"), (stale["change_unit_id"], stale["from"]))

    def test_an_old_pass_does_not_hide_the_current_must_fix(self) -> None:
        """summary 写着闭环 PASS，原生当前处置却还有完成阻断：历史闭环照列，当前不算完成，阻断项与动作点名，不报无待办。"""
        self.summary(json.dumps({"verdict": "PASS", "closure_status": "closed"}))
        out = self.status()
        [unit] = out["units"]
        self.assertEqual("closed", unit["phases"][0]["closure"], "历史闭环被抹掉了")
        self.assertIs(False, unit["disposition"]["completion_eligible"])
        blocking = unit["phases"][0]["blocking"]
        self.assertTrue(blocking, "原生的当前必修没有落到这个阶段")
        self.assertTrue(all(b["action"] in ("repair", "verify", "wait") for b in blocking), blocking)
        [stale] = out["stale_units"]
        self.assertEqual(blocking, stale["phases"][0]["blocking"])

    def test_reading_the_disposition_writes_nothing(self) -> None:
        """当前处置只读：查一次，需求目录与 harness 状态一个字节不变。"""
        self.summary(json.dumps({"verdict": "PASS", "closure_status": "closed"}))
        watched = [self.root / "doc" / "features", self.root / "framework" / "harness" / "state"]
        snapshot = lambda: {p: p.read_bytes() for d in watched if d.is_dir() for p in d.rglob("*") if p.is_file()}  # noqa: E731
        before = snapshot()
        proc = subprocess.run(["node", str(self.root / "doc/extensions/hooks/shared/framework-access.mjs"), "--project-root",
                               str(self.root), "--action", "disposition", "--feature", self.status()["units"][0]["feature_id"],
                               "--phases", "spec"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertIn(proc.returncode, (0, 1), proc.stderr)
        self.assertEqual("ok", json.loads(proc.stdout)["status"])
        self.assertEqual(before, snapshot(), "查当前处置写了盘")

    def test_the_disclosure_names_units_phases_and_who_takes_over(self) -> None:
        core = DEV_EXT / "skills" / "story" / "scripts" / "core"
        sys.path.insert(0, str(core))
        try:
            from flow.update import stale_text, stale_units  # noqa: PLC0415
        finally:
            sys.path.remove(str(core))
        units = [{"change_unit_id": "a", "feature_id": "cu-a", "phases": [
                     {"phase": "spec", "readable": True, "closure": "closed", "evidence": "fresh", "current": True},
                     {"phase": "plan", "readable": True, "closure": "closed", "evidence": "stale", "current": False}]},
                 {"change_unit_id": "b", "feature_id": "cu-b", "phases": [
                     {"phase": "spec", "readable": True, "closure": "closed", "evidence": "fresh", "current": True}]},
                 {"blueprint_id": "bp", "readable": False, "why": "原生读取 invalid"}]
        stale = stale_units(units)
        self.assertEqual(["a", None], [s.get("change_unit_id") for s in stale], "新鲜的单位被列成过期，或读不出的被略过")
        text = stale_text(stale)
        self.assertIn("a（cu-a）：阶段 plan（证据 stale）", text)
        self.assertIn("蓝图 bp 读不出（原生读取 invalid）", text)
        self.assertIn("闭环到 Plan", text)
        self.assertIn("不沿用旧 Plan", text)
        self.assertEqual("", stale_text(stale_units(units[1:2])))

    def test_unit_level_dispositions_are_disclosed_apart_from_phases(self) -> None:
        """阶段都闭环且新鲜，原生处置还有单位级的事：完成阻断、只限发布、可披露、读不出各有输出，不编造从哪个阶段重做。"""
        core = DEV_EXT / "skills" / "story" / "scripts" / "core"
        sys.path.insert(0, str(core))
        try:
            from flow.update import stale_text, stale_units  # noqa: PLC0415
        finally:
            sys.path.remove(str(core))

        def unit(disposition: dict, current: bool = True) -> dict:
            return {"change_unit_id": "a", "feature_id": "cu-a", "disposition": disposition, "phases": [
                {"phase": "spec", "readable": True, "closure": "closed", "evidence": "fresh", "current": current, "blocking": []}]}

        def ok(**over) -> dict:
            return {"status": "ok", "completion_eligible": True, "release_ready": True,
                    "completion_blocking": [], "release_blocking": [], "disclosed": [], **over}

        cases = {
            "单位完成阻断": (ok(completion_eligible=False, release_ready=False, completion_blocking=[
                {"id": "goal_run_identity_intact", "phase": "*", "owner": "harness", "action": "repair", "detail": "运行身份断了"}]),
                "completion_blocking", ["单位完成受阻：goal_run_identity_intact（repair，负责方 harness）", "不重做没受影响的业务阶段"]),
            "只限制发布": (ok(release_ready=False, release_blocking=[
                {"id": "release_gate", "phase": "spec", "owner": "spec", "action": "verify", "detail": "发布前要复核"}]),
                "release_blocking", ["只限制发布：release_gate（verify，负责方 spec）", "普通完成照原生结论"]),
            "可披露": (ok(disclosed=[{"id": "known_residual", "phase": "*", "owner": None, "action": "disclose", "detail": "已知残差"}]),
                     "disclosed", ["交付时要披露：known_residual（disclose）", "不当作缺陷"]),
        }
        for name, (disposition, key, pieces) in cases.items():
            with self.subTest(case=name):
                [stale] = stale_units([unit(disposition)])
                self.assertEqual([], stale["phases"])
                self.assertNotIn("from", stale)
                self.assertEqual([key], list(stale["unit"]))
                text = stale_text([stale])
                for piece in pieces:
                    self.assertIn(piece, text)
                self.assertNotIn("最早未完成的阶段", text)
        with self.subTest(case="处置读不出"):
            [stale] = stale_units([unit({"status": "unknown", "why": "原生读取失败"}, current=False)])
            self.assertEqual(([], "原生读取失败"), (stale["phases"], stale["disposition_unknown"]))
            self.assertNotIn("from", stale)
            text = stale_text([stale])
            self.assertIn("当前处置读不出（原生读取失败）", text)
            self.assertIn("不据此重做阶段", text)
            self.assertNotIn("最早未完成的阶段", text)
        self.assertEqual([], stale_units([unit(ok())]), "没有要交代的事却被列出")

    def test_a_directory_the_framework_cannot_resolve_is_unreadable(self) -> None:
        core = DEV_EXT / "skills" / "story" / "scripts" / "core"
        sys.path.insert(0, str(core))
        try:
            from flow.update import _phase_facts  # noqa: PLC0415
        finally:
            sys.path.remove(str(core))
        [phase] = _phase_facts([{"phase": "spec", "error": "配置坏了"}], {})
        self.assertEqual({"phase": "spec", "readable": False}, {k: phase[k] for k in ("phase", "readable")})
        self.assertIn("配置坏了", phase["why"])


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
        self.assertIn("只能从 materials 改为 documents", refused.get("error", ""), refused)
        rec = json.loads((self.updates / rid / "record.json").read_text(encoding="utf-8"))
        self.assertEqual("documents", rec["requested_result"])


class ANewVersionKeepsTheOldOne(UpdateCase):
    """同一来源的新版本落成新版本，旧版本原样留着；换了名字的改版稿是新来源，update 列出同类的已有来源由模型读了判。"""

    def test_a_renamed_revision_is_a_new_source_and_the_same_class_is_hinted(self) -> None:
        import_into(self.root, self.feature_root, {"产品原稿-v1.md": ("# 产品需求\n\n单日上限 200。\n".encode("utf-8"), "RR")})
        inbox = self.feature_root / "sources" / "inbox"
        (inbox / "RR-prd.md").write_text("# 产品需求\n\n单日上限 300。\n", encoding="utf-8")
        (inbox / ".classify.json").write_text(json.dumps({"RR-prd.md": "RR"}, ensure_ascii=False), encoding="utf-8")
        hint = self.update("--action", "inputs")["superseded_hint"]
        self.assertEqual("RR-prd.md", hint[0]["new"])
        self.assertIn("local:产品原稿-v1.md", hint[0]["same_class"], "没提示同类的已有来源")
        import_into(self.root, self.feature_root, {"RR-prd.md": ("# 产品需求\n\n单日上限 300。\n".encode("utf-8"), "RR")})
        index = json.loads((self.src / "materials.json").read_text(encoding="utf-8"))
        ids = {s["source_id"]: s for s in index["sources"]}
        self.assertIn("local:RR-prd.md", ids)
        old = self.feature_root / ids["local:产品原稿-v1.md"]["versions"][0]["original"]["path"]
        self.assertIn("单日上限 200", old.read_text(encoding="utf-8"), "旧来源被动了")

    def test_the_same_place_again_is_a_new_version(self) -> None:
        import_into(self.root, self.feature_root, {"产品原稿.md": ("# 产品需求\n\n单日上限 200。\n".encode("utf-8"), "RR")})
        import_into(self.root, self.feature_root, {"产品原稿.md": ("# 产品需求\n\n单日上限 300。\n".encode("utf-8"), "RR")})
        index = json.loads((self.src / "materials.json").read_text(encoding="utf-8"))
        versions = next(s for s in index["sources"] if s["source_id"] == "local:产品原稿.md")["versions"]
        self.assertEqual([1, 2], [v["version"] for v in versions])
        texts = [(self.feature_root / v["original"]["path"]).read_text(encoding="utf-8") for v in versions]
        self.assertIn("单日上限 200", texts[0])
        self.assertIn("单日上限 300", texts[1])


class SameNamedOriginalSteps:
    """V01 的真实入口步骤：update inputs、材料关卡、import_sources、prepare、round、设计同步、restore、close。
    同一位置放入改过的原件导入后就是同一来源的新版本，旧版本留着；设计同步后需求条目采用各来源最新的版本。
    不手改材料索引或蓝图条目。混入 UpdateCase 一族使用。"""

    NOTES = ("## 当前依据\n读过了。\n\n## 不变项与理由\n\n| 不变项 | 为什么不用改 |\n|---|---|\n"
             "| 验收口径 | 没动 |\n")
    NAME = "甲需求.md"

    def setUp(self) -> None:
        super().setUp()
        self.inbox = self.feature_root / "sources" / "inbox"
        self.inbox.mkdir(parents=True, exist_ok=True)
        #: 作者据新材料改写的可改件：撤回按它的指纹判冲突
        self.basis = self.src / "doc-refresh.md"

    def index(self) -> dict:
        return json.loads((self.src / "materials.json").read_text(encoding="utf-8"))

    def versions(self) -> list[dict]:
        """这份原件这个来源的全部版本。"""
        return next((s["versions"] for s in self.index()["sources"] if s["source_id"] == f"local:{self.NAME}"), [])

    def canonical(self) -> Path:
        return self.feature_root / "blueprint" / "component-blueprint.yaml"

    def adopted(self) -> int | None:
        """蓝图需求条目采用的是这个来源的第几版；没采用为 None。"""
        stem = Path(self.NAME).stem
        hits = {int(m) for m in re.findall(rf"sources/{re.escape(stem)}-v(\d+)/", self.canonical().read_text(encoding="utf-8"))}
        self.assertLessEqual(len(hits), 1, f"同一来源采用了不止一版：{hits}")
        return next(iter(hits), None)

    def original(self, version: int) -> bytes:
        """这个来源第 `version` 版的原件字节（材料版本导入后不改）。"""
        v = next(v for v in self.versions() if v["version"] == version)
        return (self.feature_root / v["original"]["path"]).read_bytes()

    def adopt(self, data: bytes, basis: str) -> str:
        """一次采用：材料关卡答补料 → 导入 → 开轮 → 登记本轮 → 作者写下依据 → 设计同步，需求条目采用新版本；返回本轮 id。"""
        (self.inbox / self.NAME).write_bytes(data)
        self.assertIn(self.NAME, self.update("--action", "inputs")["pending"])
        write_gaps(self.src)
        self.assertEqual("accepted", answer(self.flow, "material_scope", "放了甲需求", "--chosen", "supplied")["outcome"])
        (self.inbox / ".classify.json").write_text(json.dumps({self.NAME: "RR"}, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(FLOW.parent / "import_sources.py"), "--feature", FEATURE,
                               "--project-root", str(self.root)], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        rid = self.update()["update"]
        self.assertIsNone(self.flow("round").get("error"))
        self.basis.write_text(f"# 当前依据\n\n{basis}\n", encoding="utf-8")
        design_kit.install_blueprint(self.root, FEATURE, design_kit.ACCESS)
        self.assertEqual(self.versions()[-1]["version"], self.adopted(), "设计同步后没采用新版本")
        return rid

    def close(self, rid: str) -> None:
        (self.updates / rid / "update-notes.md").write_text(self.NOTES, encoding="utf-8")
        self.assertEqual("closed", self.update("--action", "close").get("status"))

    def resolve_conflicts(self, out: dict) -> None:
        """人按冲突给的开轮版本定回去（开轮时没有的那份就删掉）。"""
        for c in out["conflicts"]:
            if c.get("before"):
                (self.feature_root / c["file"]).write_bytes((self.feature_root / c["before"]).read_bytes())
            else:
                (self.feature_root / c["file"]).unlink()


class TheAdoptedOriginalIsTracedThroughRetirement(SameNamedOriginalSteps, UpdateCase):
    """设计采用的那一版原件按材料版本的路径与摘要核：同一位置导入新版、登记本轮之后，审查对象仍列着采用的那一版；
    那一版的原件不在了就报缺口，不拿同一来源的新版本顶替。"""

    OBJECT = """
import { pathToFileURL } from 'node:url';
const [mod, root, feature] = process.argv.slice(1);
const { reviewObject } = await import(pathToFileURL(mod).href);
const o = reviewObject(root, feature, { withTask: false });
process.stdout.write(JSON.stringify({ rows: o.rows.map(r => [r.path, r.label]), problems: o.problems }));
"""

    def review_object(self) -> dict:
        mod = DEV_EXT / "skills" / "story" / "scripts" / "core" / "story" / "review-object.mjs"
        proc = subprocess.run(["node", "--input-type=module", "-e", self.OBJECT, str(mod), str(self.root), FEATURE],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr[-800:])
        return json.loads(proc.stdout)

    NAME = "甲需求.docx"
    DOCX = REPO_ROOT / "test" / "cases" / "auto-topup"

    def test_the_adopted_version_is_traced_and_a_lost_one_is_named(self) -> None:
        v1 = (self.DOCX / "supplements" / "交通卡自动充值.docx").read_bytes()
        self.close(self.adopt(v1, "按甲需求第一版。"))
        first = self.versions()[0]
        (self.inbox / self.NAME).write_bytes((self.DOCX / "update-inputs" / "交通卡自动充值-v2.docx").read_bytes())
        self.update("--action", "inputs")
        write_gaps(self.src)
        answer(self.flow, "material_scope", "放了甲需求新版", "--chosen", "supplied")
        (self.inbox / ".classify.json").write_text(json.dumps({self.NAME: "RR"}, ensure_ascii=False), encoding="utf-8")
        done = subprocess.run([sys.executable, str(FLOW.parent / "import_sources.py"), "--feature", FEATURE,
                               "--project-root", str(self.root)], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120)
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)
        self.update()
        self.assertIsNone(self.flow("round").get("error"))
        self.assertEqual(1, self.adopted(), "设计没同步，采用版应仍是第一版")
        self.assertEqual([1, 2], [v["version"] for v in self.versions()])

        got = self.review_object()
        original = first["original"]["path"]
        traced = [label for rel, label in got["rows"] if rel.endswith(original)]
        self.assertEqual(1, len(traced), got["rows"])
        self.assertIn(f"设计采用版本的原件 {original}", traced[0])
        self.assertIn(f"设计采用的阅读稿 {first['readable']['path']}", [label for _, label in got["rows"]])
        self.assertFalse([p for p in got["problems"] if "设计采用的" in p], got["problems"])

        (self.feature_root / original).unlink()
        lost = [p for p in self.review_object()["problems"] if original in p]
        self.assertTrue(lost, "采用的那一版原件不在了却没报")


class ASameNamedOriginalGoesThroughTheRealEntries(SameNamedOriginalSteps, UpdateCase):
    """V01（未登记起点）：同名原件换版、撤回与重新采用旧原件。"""

    def test_an_open_round_withdrawal_keeps_versions_and_the_design(self) -> None:
        v1 = "# 甲需求\n\n单日上限 200。\n".encode("utf-8")
        self.close(self.adopt(v1, "单日上限 200，按甲需求。"))
        basis_v1 = self.basis.read_bytes()

        self.adopt("# 甲需求\n\n单日上限 300。\n".encode("utf-8"), "单日上限 300，按甲需求新版。")
        canonical = self.canonical().read_bytes()
        self.assertEqual(2, self.adopted())

        out = self.update("--action", "restore")
        self.assertEqual("restore_conflicted", out["status"], "本轮改动没有登记的一版可比，应列冲突")
        self.assertIn("AR/story-src/doc-refresh.md", [c["file"] for c in out["conflicts"]])
        self.assertIn("单日上限 300", self.basis.read_text(encoding="utf-8"), "冲突的现状被覆盖了")
        self.resolve_conflicts(out)
        out = self.update("--action", "restore")
        self.assertEqual(("restored", []), (out["status"], out["conflicts"]), out)
        self.assertEqual(basis_v1, self.basis.read_bytes())
        self.assertEqual(canonical, self.canonical().read_bytes(), "撤回回写了蓝图")
        self.assertEqual(2, self.versions()[-1]["version"], "撤回动了材料版本")
        self.assertIn("单日上限 300", self.original(2).decode("utf-8"), "撤回回写了材料版本")
        self.assertIn("单日上限 200", self.original(1).decode("utf-8"), "旧版本被动了")

    def test_a_closed_round_readopts_the_old_content_as_a_new_version(self) -> None:
        """换版之后又改回旧内容：旧版本一直留在原处，改回的内容作为新一版取得并被采用，中间那一版不动。"""
        v1 = "# 甲需求\n\n单日上限 200。\n".encode("utf-8")
        self.close(self.adopt(v1, "单日上限 200，按甲需求。"))
        self.close(self.adopt("# 甲需求\n\n单日上限 300。\n".encode("utf-8"), "单日上限 300，按甲需求新版。"))
        self.assertEqual(v1, self.original(1), "第一版的原件不是当时的字节")
        self.close(self.adopt(self.original(1), "单日上限 200，按甲需求。"))
        self.assertEqual([1, 2, 3], [v["version"] for v in self.versions()], "换版的各版没各留一份")
        self.assertEqual(3, self.adopted())
        self.assertEqual(self.original(1), self.original(3), "重新采用的正文不是旧版")
        self.assertIn("单日上限 300", self.original(2).decode("utf-8"), "中间那一版被覆盖了")


class FetchOnlyWritesToTheInbox(unittest.TestCase):
    """只读取材：三份正文放本单来源收件箱的取材批次，与人补的料走同一条导入链；业务文件一个字节都不碰。"""

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
        self.out = self.feature / "sources" / "inbox" / "fetch-1"
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
        self.assertEqual([".receipt.json"], [p.name for p in self.out.glob("*.json")],
                         "批次里只该有点文件回执（控制件，不当材料导入）")
        receipt = json.loads((self.src / "fetched.json").read_text(encoding="utf-8"))
        prd = [i for i in receipt["items"] if i["name"] == "RR-prd.md"][0]
        self.assertEqual(f"{RR}/prd.md", prd["origin"])
        self.assertTrue(prd["digest"].startswith("sha256:"))
        batch = json.loads((self.out / ".receipt.json").read_text(encoding="utf-8"))
        self.assertEqual((AR, SR, RR), (batch["reqNo"], batch["parentNo"], batch["rrNo"]))
        roles = {i["name"]: (i["role"], i["ticket"], i["title"]) for i in batch["items"]}
        self.assertEqual(("RR", RR, "产品需求"), roles["RR-prd.md"])
        self.assertEqual(("AR", AR, "开发需求"), roles["AR-design.md"])

    def test_what_equals_a_stored_version_is_not_dropped_in(self) -> None:
        """与来源索引里同一来源已存的某一版逐字相同的不落盘：放进去它就是一份待导入的件，每次 update 都被报成新料。"""
        self.assertEqual(0, self.fetch(AR, "--out", str(self.out))[0])
        proc = subprocess.run([sys.executable, str(FLOW.parent / "import_sources.py"), "--feature", AR,
                               "--project-root", str(self.project)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        again = self.feature / "sources" / "inbox" / "fetch-2"
        code, receipt = self.fetch(AR, "--out", str(again))
        self.assertEqual(0, code, receipt)
        states = {i["name"]: i["status"] for i in receipt["items"]}
        self.assertEqual(("same", "same", "same"), (states["RR-prd.md"], states["SR-design.md"], states["AR-design.md"]))
        self.assertFalse(again.exists(), "没有新内容却建了取材批次")

    def test_our_own_published_story_is_not_new_upstream(self) -> None:
        """本单系统正文与本地 story 相同，就是自己归档上去的那一版：不当成上游新需求取回。"""
        (self.feature / "AR" / "story.md").write_text("# 开发需求\n\n上游先填了一版。\n", encoding="utf-8")
        code, receipt = self.fetch(AR, "--out", str(self.out))
        self.assertEqual(0, code, receipt)
        states = {i["name"]: i["status"] for i in receipt["items"]}
        self.assertEqual("same", states["AR-design.md"])
        self.assertFalse((self.out / "AR-design.md").exists())

    def test_the_adapter_reports_facts_not_core_steps(self) -> None:
        """对接层只报取回、落盘的事实，不提示 core 的下一步命令。"""
        for cmd in (["fetch", AR, "token", "--out", str(self.out)],):
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


#: 登记好的那份工作区里，造它时那一次登记的原样输出
FIRST_REGISTRATION = ".first-registration.json"
REGISTERED = shared_state.digest(WALKED, "registered")


def _registered(base: Path) -> None:
    """走完交给设计的工作区装上审查机制，按正常一轮定稿、夹具审查者通过、接收、登记；记下那次登记的输出。"""
    shared_state.copy_tree(shared_state.shared_tree("update-walked", WALKED, UpdateCase()._walk), base)
    link_framework(base)
    design_kit.install_review_mechanism(base, DEV_EXT)
    build = DEV_EXT / "skills" / "story" / "scripts" / "core" / "story-build.mjs"

    def run(*args: str) -> subprocess.CompletedProcess:
        proc = subprocess.run(list(args), capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=180, cwd=str(base))
        if proc.returncode:
            raise RuntimeError(f"{args[:3]}：{proc.stdout}{proc.stderr}")
        return proc

    run("node", str(build), "review", "--action", "prepare", "--feature", FEATURE, "--project-root", str(base))
    design_kit.write_review(base, FEATURE, "pass")
    run("node", str(build), "review", "--action", "prepare", "--feature", FEATURE, "--project-root", str(base))
    proc = run(sys.executable, str(FLOW), "story", "--feature", FEATURE, "--project-root", str(base))
    out = json.loads([line for line in proc.stdout.splitlines() if line.strip().startswith("{")][-1])
    if not out.get("success"):
        raise RuntimeError(f"登记没成：{out}")
    (base / FIRST_REGISTRATION).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")


class StoryIsRegisteredAgainAfterChangesCase(UpdateCase):
    """story 登记之后要改：改完重跑 `story` 就是重新登记，不退状态、不碰流程契约（U39）。

    spec 阶段返修、update 轮内修订、归档后重拍范围三种情形走同一条链；
    09-26 实跑里 update 段卡在 reopen → complete → story 的死路上，模型手改了四次契约。
    """

    BUILD = DEV_EXT / "skills" / "story" / "scripts" / "core" / "story-build.mjs"
    #: 起手就是登记好的工作区：整轮只造一次（shared_state），本用例第一次 register() 交出造它时那次真实登记的原样结果
    START_REGISTERED = False

    def setUp(self) -> None:
        self.outputs: list[str] = []
        self._first: dict | None = None
        if not self.START_REGISTERED:
            super().setUp()
            # 登记前要经独立审查：审查对象里的章节合同与判据取工程里装的扩展
            design_kit.install_review_mechanism(self.root, DEV_EXT)
            return
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        shared_state.copy_tree(shared_state.shared_tree("update-registered", REGISTERED, _registered), self.root)
        link_framework(self.root)
        self.feature_root = self.root / "doc" / "features" / FEATURE
        self.src = self.feature_root / "AR" / "story-src"
        self.updates = self.src / "updates"
        self._first = json.loads((self.root / FIRST_REGISTRATION).read_text(encoding="utf-8"))

    def run_cmd(self, *args: str) -> subprocess.CompletedProcess:
        proc = subprocess.run(list(args), capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120, cwd=str(self.root))
        self.outputs.append(proc.stdout + proc.stderr)
        return proc

    def register(self) -> dict:
        """定稿并准备审查，夹具审查者给出通过的回复，重跑 prepare 接收，再登记。"""
        if getattr(self, "_first", None) is not None:      # 别的类借用这个方法时没有预登记
            out, self._first = self._first, None
            self.outputs.append(json.dumps(out, ensure_ascii=False))
            return out
        prepared = self.run_cmd("node", str(self.BUILD), "review", "--action", "prepare", "--feature", FEATURE,
                                "--project-root", str(self.root))
        self.assertEqual(0, prepared.returncode, prepared.stdout + prepared.stderr)
        design_kit.write_review(self.root, FEATURE, "pass")
        received = self.run_cmd("node", str(self.BUILD), "review", "--action", "prepare", "--feature", FEATURE,
                                "--project-root", str(self.root))
        self.assertEqual(0, received.returncode, received.stdout + received.stderr)
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
        """设计按当前材料同步：设计职责在 component-design 里让需求条目采用各来源最新的版本并重新准入。"""
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



class TheRegistrationSaysWhatRan(StoryIsRegisteredAgainAfterChangesCase):
    """登记链（全篇检查 → 审查结果 → 成文依据）哪一步没成：说清做完了什么、哪几步没跑、归谁处理，已有登记原样保留；
    同内容重新登记不换登记时刻。故障注入只换子进程，其余照真跑。"""

    START_REGISTERED = True

    CORE = DEV_EXT / "skills" / "story" / "scripts" / "core"

    def modules(self):
        sys.path.insert(0, str(self.CORE))
        self.addCleanup(lambda: str(self.CORE) in sys.path and sys.path.remove(str(self.CORE)))
        from flow import lifecycle, publish  # noqa: PLC0415
        from flow.state import FlowError  # noqa: PLC0415
        return lifecycle, publish, FlowError

    def registration_broken_at(self, step: int, outcome) -> tuple[str, list]:
        """在本进程里跑登记，第 step 个子进程换成 outcome（异常就抛，整数就是那个退出码），其余照真跑。"""
        lifecycle, _, FlowError = self.modules()
        real, calls = subprocess.run, []

        def run(cmd, *args, **kwargs):
            calls.append(cmd)
            if len(calls) - 1 != step:
                return real(cmd, *args, **kwargs)
            if isinstance(outcome, Exception):
                raise outcome
            return subprocess.CompletedProcess(cmd, outcome, "", "[story-build] 脚本自身异常：注入的故障")

        with unittest.mock.patch.object(lifecycle.subprocess, "run", run), self.assertRaises(FlowError) as caught:
            lifecycle.cmd_story(self.feature_root, self.root)
        return str(caught.exception), calls

    def test_registering_unchanged_content_again_keeps_the_registration_time(self) -> None:
        """同内容重新登记仍跑完整核对，登记时刻与依据不换；内容变了、重新审过再登记才换。"""
        self.assertTrue(self.register().get("registered"), self.outputs[-1])
        sys.path.insert(0, str(FLOW.parent))
        from flow.state import load, save  # noqa: PLC0415
        contract = load(self.feature_root)
        contract["story_written_at"] = earlier = "2026-01-01T00:00:00+00:00"
        save(self.feature_root, contract)
        first = self.contract()
        again = self.flow("story")
        self.assertFalse(again.get("registered"), again)
        self.assertEqual((earlier, first["story_basis"]), (self.contract()["story_written_at"], self.contract()["story_basis"]))
        self.rewrite_background("支付提交后用户要能看到回执状态。登记之后补的一句。")
        self.assertTrue(self.register().get("registered"), self.outputs[-1])
        self.assertNotEqual(first["story_basis"], self.contract()["story_basis"])
        self.assertGreater(self.contract()["story_written_at"], earlier)

    def test_a_failed_first_step_says_nothing_else_ran(self) -> None:
        """第一步全篇检查没过：已完成无、后两步没跑，原输出带出来；已有登记原样保留，修好后重新审过即可登记。"""
        self.assertTrue(self.register().get("registered"), self.outputs[-1])
        registered = self.contract()
        story = self.feature_root / "AR" / "story.md"
        good = story.read_text(encoding="utf-8")
        head, rest = good.split("\n## ", 1)
        first, others = rest.split("\n## ", 1)
        story.write_text(f"{head}\n## {first}\n<!-- 待写：背景 -->\n\n## {others}", encoding="utf-8")
        out = self.flow("story")
        error = out.get("error", "")
        self.assertIn("story-build check 没通过", error, out)
        self.assertIn("已有的登记原样保留", error)
        self.assertIn("已完成：无", error)
        self.assertIn("没跑：review --action check、basis", error)
        self.assertIn("story_flow.py story --feature", error, "没给重新登记的入口")
        self.assertEqual((registered["status"], registered["story_basis"]),
                         (self.contract()["status"], self.contract()["story_basis"]), "没登记成却改了已有登记")
        story.write_text(good, encoding="utf-8")
        self.assertEqual("story_written", self.contract()["status"])
        self.assertFalse(self.flow("story").get("registered"), "改回原样后应与已有登记一致")

    def test_a_step_that_cannot_start_keeps_the_progress(self) -> None:
        """第三步进程起不来：前两步做了什么、这一步没跑，归运行环境，不让作者改稿；恢复后登记即成。"""
        self.register()
        error, calls = self.registration_broken_at(2, FileNotFoundError("node 不见了"))
        self.assertIn("story-build basis 没能启动", error)
        self.assertIn("已完成：全篇检查通过；独立审查结果可消费", error)
        self.assertIn("运行环境问题，业务稿与派生件都不用改", error)
        self.assertEqual(3, len(calls), "起不来之后还接着跑了后面的步骤")

    def test_an_internal_error_is_not_sent_to_the_author(self) -> None:
        """成文依据退出 2（脚本自身异常）：归扩展维护者，不让作者改稿，原始输出带出来。"""
        self.register()
        error, calls = self.registration_broken_at(2, 2)
        self.assertIn("story-build basis 没有正常结束（退出码 2）", error)
        self.assertIn("不要为它改真源或草稿", error)
        self.assertIn("扩展维护者", error)
        self.assertNotIn("按下面的报告处理", error)
        self.assertIn("注入的故障", error, "原始输出没带出来")
        self.assertEqual(3, len(calls))

    def test_an_interrupted_step_is_an_environment_matter(self) -> None:
        """退出码既不是 1 也不是 2（进程被杀之类）：查进程与环境，不让作者改稿，也不说成脚本缺陷。"""
        self.register()
        error, calls = self.registration_broken_at(0, 137)
        self.assertIn("story-build check 没有正常结束（退出码 137）", error)
        self.assertIn("进程被中断或运行环境出错", error)
        self.assertNotIn("扩展维护者", error)
        self.assertEqual(1, len(calls))

    def test_without_node_nothing_runs(self) -> None:
        lifecycle, _, FlowError = self.modules()
        with unittest.mock.patch.object(lifecycle.shutil, "which", lambda _name: None), \
                unittest.mock.patch.object(lifecycle.subprocess, "run") as run, self.assertRaises(FlowError) as caught:
            lifecycle.cmd_story(self.feature_root, self.root)
        run.assert_not_called()
        self.assertIn("找不到 node，story-build 一步都没启动", str(caught.exception))
        self.assertIn("运行环境问题", str(caught.exception))

    def archived_with(self, outcome, *, node: bool = True) -> str:
        """需求系统已写入之后的本地归档登记：交付门子进程换成 outcome（异常就抛，整数是退出码）。返回报错。"""
        _, publish, FlowError = self.modules()

        def run(cmd, *args, **kwargs):
            if isinstance(outcome, Exception):
                raise outcome
            return subprocess.CompletedProcess(cmd, outcome, "", "[story-build] 交付门的原始输出")

        which = (lambda _n: "node") if node else (lambda _n: None)
        with unittest.mock.patch.object(publish.subprocess, "run", run), \
                unittest.mock.patch.object(publish.shutil, "which", which), self.assertRaises(FlowError) as caught:
            publish.cmd_archived(self.feature_root, self.root)
        return str(caught.exception)

    def test_a_failed_local_archive_registration_never_asks_for_another_upload(self) -> None:
        """远端已写入后本地登记失败：哪一类失败都只补登记、不重新上传，也不断言远端那一份不合格。"""
        self.assertTrue(self.register().get("registered"), self.outputs[-1])
        cases = {"自身异常": (2, True, "扩展维护者"), "进程起不来": (FileNotFoundError("node 不见了"), True, "运行环境问题"),
                 "没有 node": (0, False, "装好 node"), "被中断": (137, True, "进程被中断"),
                 "交付门没过": (1, True, "不是需求系统里那一份")}
        for name, (outcome, node, why) in cases.items():
            with self.subTest(name):
                error = self.archived_with(outcome, node=node)
                self.assertIn(why, error)
                self.assertIn("只补登记：`python doc/extensions/skills/story/scripts/core/story_flow.py archived", error)
                self.assertIn("不要重新上传", error)
                self.assertNotIn("重新归档", error)
                self.assertNotIn("不合格", error)
                self.assertNotIn("archived", self.contract(), "没登记成却记了归档态")


class TheReviewersWordsSurviveAFailedRegistration(StoryIsRegisteredAgainAfterChangesCase):
    """评审人填过的意见在登记中途失败后逐字保留：要先写决策再登记，不从登记好的工作区起手。"""

    CORE = TheRegistrationSaysWhatRan.CORE
    modules = TheRegistrationSaysWhatRan.modules
    registration_broken_at = TheRegistrationSaysWhatRan.registration_broken_at

    def test_the_review_human_zone_survives_a_failed_registration(self) -> None:
        """评审人填过的意见：登记中途失败、修好重新准备审查再登记，都一个字节不丢。"""
        decisions = self.src / "decisions.json"
        data = json.loads(decisions.read_text(encoding="utf-8"))
        data.pop("no_pending", None)
        data["decisions"] = [open_decision("D1", "回执超时后是否自动重查待定", "回执超时后要不要自动再查一次。",
                                           [("自动重查一次", "少一次手动操作；多一次请求"),
                                            ("提示用户手动刷新", "请求少；用户多点一下")],
                                           "选择方案 1。", category="业务规则")]
        decisions.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.assertTrue(self.register().get("registered"), self.outputs[-1])
        review = self.feature_root / "AR" / "review.md"
        filled = review.read_text(encoding="utf-8").replace("- [ ] 同意", "- [x] 同意").replace(
            "修改意见：\n", "修改意见：\n重查间隔写进规格。\n")
        self.assertNotEqual(filled, review.read_text(encoding="utf-8"), "夹具的评审区形状变了，用例要跟着改")
        review.write_text(filled, encoding="utf-8")
        error, _ = self.registration_broken_at(1, 137)
        self.assertIn("没有正常结束", error)
        self.assertEqual(filled, review.read_text(encoding="utf-8"))
        self.register()
        human = filled[filled.index("评审结论："):filled.index("<!-- decision: D1 -->")]
        self.assertIn("重查间隔写进规格。", human)
        self.assertIn(human, review.read_text(encoding="utf-8"))



class ARegisteredStoryGoesThroughTheRealEntries(SameNamedOriginalSteps, StoryIsRegisteredAgainAfterChangesCase):
    """V01（已登记起点）：v1 走真实审查与 `story` 登记并收口后，新一轮同名换版或只改表达，再撤回。
    撤回只退可改件；登记、材料版本、蓝图、人签与轮次记录不回写，当前资格照实报，交付门不放行。"""

    def deliver(self) -> subprocess.CompletedProcess:
        return self.run_cmd("node", str(self.BUILD), "check", "--deliver", "--feature", FEATURE, "--project-root", str(self.root))

    def registered_v1(self) -> None:
        """v1 原件经材料关卡导入，设计同步采用它，材料清单改列原件（作者的事），审查通过后登记并收口。"""
        rid = self.adopt("# 甲需求\n\n单日上限 200。\n".encode("utf-8"), "单日上限 200，按甲需求。")
        story = self.feature_root / "AR" / "story.md"
        row = "| 甲需求 PRD [prd.md](../sources/prd-v1/prd.md) | [prd.md](../sources/prd-v1/prd.md) |"
        mine = self.versions()[-1]["original"]["path"]
        text = story.read_bytes().decode("utf-8")
        self.assertIn(row, text)
        story.write_bytes(text.replace(row, f"| 甲需求 [甲需求.md](../{mine}) | [甲需求.md](../{mine}) | 单日上限。 |\n" + row)
                          .encode("utf-8"))
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        self.close(rid)
        self.mark_archived()
        self.assertEqual("story_written", self.contract()["status"])

    def kept(self) -> dict:
        """撤回不该回写的：蓝图、关卡记录（含人的原话）、归档标记。"""
        contract = self.contract()
        return {"blueprint": self.canonical().read_bytes(),
                "gates": contract["rounds"][-1]["gates"], "archived": contract.get("archived")}

    def test_a_new_version_withdrawn_leaves_the_registration_to_sync(self) -> None:
        self.registered_v1()
        self.adopt("# 甲需求\n\n单日上限 300。\n".encode("utf-8"), "单日上限 300，按甲需求新版。")
        self.assertEqual(("story_written", "register_story"), (self.contract()["status"], self.flow("status")["next"]),
                         "设计采用了新版本，登记仍算成立")
        before = self.kept()
        out = self.update("--action", "restore")
        self.assertEqual("restore_conflicted", out["status"], out)
        self.resolve_conflicts(out)
        out = self.update("--action", "restore")
        self.assertEqual(("restored", []), (out["status"], out["conflicts"]), out)
        self.assertEqual(before, self.kept(), "撤回回写了蓝图、关卡记录或归档标记")
        self.assertEqual(2, self.adopted())
        self.assertIn("单日上限 200", self.original(1).decode("utf-8"), "v1 被动了")
        self.assertIn("单日上限 300", self.original(2).decode("utf-8"), "v2 被动了")
        self.assertEqual(("story_written", "register_story"), (self.contract()["status"], self.flow("status")["next"]),
                         "撤回之后把旧登记当成了现在的")
        self.assertNotEqual(0, self.deliver().returncode, "设计采用的来源换了而稿没重新登记，交付门却放行了")

    def test_a_registered_expression_change_withdrawn_needs_registering_again(self) -> None:
        self.registered_v1()
        story = self.feature_root / "AR" / "story.md"
        registered = story.read_bytes()
        rid = self.update()["update"]
        self.rewrite_background("支付提交后用户要能看到回执状态，以服务端为准。")
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        before = self.kept()
        out = self.update("--action", "restore")
        self.assertEqual(("restored", []), (out["status"], out["conflicts"]), out)
        self.assertEqual(registered, story.read_bytes(), "已登记的修改没退回开轮时的那一版")
        self.assertEqual(["AR/story.md"], out["needs_sync"], "Story 回退之后与这一轮的登记不再一致，没报出来")
        self.assertEqual(("story_written", "register_story"), (self.contract()["status"], self.flow("status")["next"]))
        self.assertEqual(before, self.kept())
        gate = self.deliver()
        self.assertNotEqual(0, gate.returncode)
        self.assertIn("登记之后改过", gate.stdout + gate.stderr)
        self.assertIsNone(self.flow("update", "--action", "status")["open"], f"{rid} 撤回后仍开着")


class StoryIsRegisteredAgainAfterChanges(StoryIsRegisteredAgainAfterChangesCase):
    START_REGISTERED = True

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


class StoryIsRegisteredAgainAfterChangesPart2(StoryIsRegisteredAgainAfterChangesCase):
    START_REGISTERED = True

    def test_a_design_change_in_the_round_needs_the_story_registered_again(self) -> None:
        """update 轮内设计改了需求条目（材料字节没变）：上一次登记的依据不再是现在的，不重跑 `story` 就不收口。"""
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        self.mark_archived()
        rid = self.update()["update"]
        items = design_kit.handed_items(self.root, FEATURE, design_kit.ACCESS)
        items[0]["kind"] = "goal"
        design_kit.install_blueprint(self.root, FEATURE, design_kit.ACCESS, items=items)
        self.assertEqual("register_story", self.flow("status")["next"], "设计改了，没指向重新登记")
        (self.updates / rid / "update-notes.md").write_text(NOTES, encoding="utf-8")
        refused = self.update("--action", "close")
        self.assertIn("重新登记", refused.get("error", ""), refused)
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        self.assertEqual("closed", self.update("--action", "close").get("status"))
        self.assert_no_hand_edit()

    def test_changed_materials_need_a_registration_after_them_before_close(self) -> None:
        """update 轮里材料变了：登记还是变化之前的那一份——不收口；设计采用新版本、按它重新登记后收口。"""
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        self.mark_archived()
        rid = self.update()["update"]
        prd = self.feature_root / "sources" / "prd-v1" / "prd.md"
        import_into(self.root, self.feature_root,
                    {"RR/prd.md": (prd.read_bytes() + "\n改版：回执状态以服务端为准。\n".encode("utf-8"), "RR")})
        self.flow("round")
        (self.updates / rid / "update-notes.md").write_text(NOTES, encoding="utf-8")
        refused = self.update("--action", "close")
        self.assertIn("材料又变了", refused.get("error", ""), refused)
        self.design_syncs()             # 设计改为采用产品需求的新版本
        cite_latest_prd(self.feature_root)
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        self.assertEqual("closed", self.update("--action", "close").get("status"))
        self.assert_no_hand_edit()


class StoryIsRegisteredAgainAfterChangesPart3(StoryIsRegisteredAgainAfterChangesCase):
    """不采用的新材料与归档后改范围：设计采用关系与范围关卡各按自己的规则走。"""

    START_REGISTERED = True

    def test_a_new_material_left_out_needs_a_registration_but_no_design_change(self) -> None:
        """来了一份新材料而本轮不采用：设计不用同步，成文按当前材料重新登记（材料清单写明它的去处）后收口。"""
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        self.mark_archived()
        rid = self.update()["update"]
        canonical = (self.feature_root / "blueprint" / "component-blueprint.yaml").read_bytes()
        import_into(self.root, self.feature_root, {"meeting-photo.png": (b"\x89PNG\r\n\x1a\n" + b"0" * 32, "UX")})
        unused = self.run_cmd(sys.executable, str(FLOW.parent / "import_sources.py"), "--feature", FEATURE,
                              "--project-root", str(self.root), "--caption-image",
                              f"doc/features/{FEATURE}/sources/meeting-photo-v1/meeting-photo.png", "--unused", "会场照片，不是需求依据")
        self.assertEqual(0, unused.returncode, unused.stdout + unused.stderr)
        self.flow("round")
        (self.updates / rid / "update-notes.md").write_text(NOTES, encoding="utf-8")
        refused = self.update("--action", "close")
        self.assertIn("材料又变了", refused.get("error", ""), refused)
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        closed = self.update("--action", "close")
        self.assertEqual("closed", closed.get("status"), closed)
        self.assertEqual(canonical, (self.feature_root / "blueprint" / "component-blueprint.yaml").read_bytes(),
                         "不采用的新材料改了设计")

    def test_rescoping_after_archive_goes_through_the_scope_gate(self) -> None:
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        self.mark_archived()
        reopened = self.flow("reopen")
        self.assertEqual("await_gate:scope_decision", reopened.get("next"), reopened)
        answer(self.flow, "scope_decision", "还是整体承载", "--chosen", "carry_all")
        self.design_syncs()
        self.assertEqual("register_story", self.flow("status")["next"])
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
            design_kit.install_review_mechanism(self.root, DEV_EXT)
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



class TheUpdateRoundRunsEndToEnd(RegisteredCase):
    """update 的正常第二段串成一条：新材料 → 报输入、问一次补料 → 开轮 → 新料登记进本轮 → reopen 由人确认范围
    → 设计采用新版本 → 重新独立审查并登记 → 收口。只测协议与状态，不假装模型的语义；
    每一步都是新起的进程，中途断开后从盘上的状态接着走（跨会话就是重载已有状态）。"""

    def test_the_whole_round(self) -> None:
        contract = lambda: json.loads((self.src / "story-flow.json").read_text(encoding="utf-8"))
        status = lambda: self.flow("status")
        # 上游材料出了新版：同一位置放入改版稿导入，成为产品需求的第二版
        prd = self.feature_root / "sources" / "prd-v1" / "prd.md"
        import_into(self.root, self.feature_root,
                    {"RR/prd.md": (prd.read_bytes() + "\n改版：余额刷新失败要提示用户。\n".encode("utf-8"), "RR")})
        # 先报输入，在材料关卡问一次要不要补料；人说就这些
        self.assertEqual("inputs", self.update("--action", "inputs")["stage"])
        write_gaps(self.src)
        self.assertEqual("accepted", answer(self.flow, "material_scope", "不补，材料就这些", "--chosen", "confirm_scope")["outcome"])
        rid = self.update("--result", "documents")["update"]
        self.assertEqual(rid, contract()["update"]["open"])
        # 改版的材料登记进本轮，不开新轮
        rounds = len(contract()["rounds"])
        self.assertEqual("refresh_round", status()["next"])
        self.flow("round")
        self.assertEqual(rounds, len(contract()["rounds"]))
        # 要重拍范围：reopen 由人在范围关卡确认；这一轮 update 照旧开着
        self.assertEqual("await_gate:scope_decision", self.flow("reopen").get("next"))
        self.assertEqual(rid, self.flow("update", "--action", "status")["open"], "重载状态：开着的这一轮还在")
        answer(self.flow, "scope_decision", "还是整体承载", "--chosen", "carry_all")
        # 设计按新料同步：需求条目采用产品需求的新版本，蓝图重新准入
        StoryIsRegisteredAgainAfterChanges.design_syncs(self)
        cite_latest_prd(self.feature_root)
        self.assertEqual("register_story", status()["next"])
        # 收口前要按当前设计重新登记：没登记不收口
        (self.updates / rid / "update-notes.md").write_text(NOTES, encoding="utf-8")
        self.assertIn("重新登记", self.update("--action", "close").get("error", ""))
        self.assertTrue(StoryIsRegisteredAgainAfterChanges.register(self).get("success"), self.outputs[-1])
        closed = self.update("--action", "close")
        self.assertEqual("closed", closed.get("status"), closed)
        self.assertEqual({"open": None, "last_closed": rid}, contract()["update"])
        self.assertEqual("story_written", contract()["status"])


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

    def test_a_qualified_opinion_is_not_an_acceptance(self) -> None:
        """候选资格够格不等于接受：状态一律待确认，资格按提交时评审的版本记下。"""
        self.said()
        out = self.feedback()
        self.assertEqual([], out["problems"], out)
        self.assertTrue(out["eligible"], out)
        self.assertEqual([("D1", "待确认", [])], [(x["feedback_id"], x["state"], x["related_decisions"]) for x in out["feedback"]])
        self.assertIn("候选资格不等于接受", out["action"])
        rec = json.loads((self.updates / self.rid / "record.json").read_text(encoding="utf-8"))
        self.assertEqual(self.revision, rec["design_feedback"]["source_revision"])

    def add_decision(self, source_ref: str, status: str) -> None:
        """蓝图负责方调和时记的一条决定：来源写到它依据的那份反馈。"""
        blueprint = design_kit.blueprint_of(self.root, FEATURE)
        canonical = self.root / design_kit.features_dir(self.root) / blueprint / "blueprint" / "component-blueprint.yaml"
        doc = yaml.safe_load(canonical.read_text(encoding="utf-8"))
        doc["decisions_and_gaps"]["decisions"].append({
            "decision_id": "feedback-d1", "kind": "review_feedback", "status": status, "owner": "design-author",
            "rationale": "切账号时同样刷新余额", "verification_refs": [self.TARGET],
            "provenance": {"source_kind": "review_feedback", "observed_at": "2026-09-30T00:00:00Z", "evidence_strength": "observed",
                           "extraction_method": "reconcile", "source_ref": source_ref}})
        canonical.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
        design_kit.render_projection(self.root, blueprint, design_kit.ACCESS)

    def test_an_exact_reference_is_shown_but_stays_to_be_confirmed(self) -> None:
        """来源精确指向这份反馈的决定列成相关决定、带原生状态；接受与否仍看负责方的回复，状态不变。"""
        self.said()
        self.feedback()
        self.add_decision(f"doc/features/{FEATURE}/AR/story-src/updates/{self.rid}/design-feedback.json#D1", "open_decision")
        out = self.update("--action", "feedback")
        self.assertEqual([("D1", "待确认", [{"decision_id": "feedback-d1", "status": "open_decision"}])],
                         [(x["feedback_id"], x["state"], x["related_decisions"]) for x in out["feedback"]], out)

    def test_the_same_anchor_in_another_file_is_not_related(self) -> None:
        """别的轮次、别的文件里同样写 #D1 的决定，不算这份反馈的相关决定。"""
        self.said()
        self.feedback()
        self.add_decision(f"doc/features/{FEATURE}/AR/story-src/updates/20000101-000000/design-feedback.json#D1", "answered_with_evidence")
        out = self.update("--action", "feedback")
        self.assertEqual([[]], [x["related_decisions"] for x in out["feedback"]], out)

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
        self.assertIn("不是当前蓝图", proc.stdout + proc.stderr)


class PublishChecksTheExternalVersion(RegisteredCase):
    """发布前按交付门核资格，用取材回执逐件核 Story 正文、Review 附件与设计附件：E=L 跳过，E=B 可写，其余交人；
    三件都有这一版登记之后的读回才登记归档。本地单没有远端动作。需求系统单由编号决定，这里在进程内把本单当作系统单。"""

    NAMES = {"AR-design.md": "story.md", "review.md": "review.md", "design-review.md": "design-review.md"}

    def call(self, name: str, *args, system: bool = True):
        core = DEV_EXT / "skills" / "story" / "scripts" / "core"
        sys.path.insert(0, str(core))
        try:
            from flow import publish  # noqa: PLC0415
            with unittest.mock.patch.object(publish, "system_requirement", lambda _: system):
                return getattr(publish, name)(self.feature_root, *args)
        finally:
            sys.path.remove(str(core))

    @staticmethod
    def digest(body: bytes) -> str:
        return "sha256:" + hashlib.sha256(body).hexdigest()[:16]

    def local(self, name: str) -> bytes:
        return (self.feature_root / "AR" / self.NAMES[name]).read_bytes()

    def system_body(self) -> bytes:
        """系统上原来那份开发需求正文：取材导入的开发需求来源第一版。"""
        return (self.feature_root / "sources" / "design-v1" / "design.md").read_bytes()

    def receipt(self, body: bytes | None, when: str = "2099-01-01T00:00:00+00:00", status: str = "fetched",
                attachments: dict | None = None, checked: str | None = None) -> None:
        """取材回执：正文给 body（None 是系统上没有），两个附件默认系统上没有；`checked` 给出时三件都记成上传读回。"""
        items = []
        for name, value in (("AR-design.md", body), *((n, (attachments or {}).get(n)) for n in ("review.md", "design-review.md"))):
            item = {"name": name, "status": (status if name == "AR-design.md" else "fetched") if value is not None else "absent"}
            if value is not None:
                item["digest"] = self.digest(value)
            if checked:
                item["checkedAt"] = checked
            items.append(item)
        (self.src / "fetched.json").write_text(json.dumps({"fetchedAt": when, "items": items}), encoding="utf-8")

    def uploaded(self, checked: str = "2099-01-01T00:00:00+00:00") -> None:
        """三件都已上传并读回：回执里每件是本地当前这一份。"""
        self.receipt(self.local("AR-design.md"), checked=checked,
                     attachments={n: self.local(n) for n in ("review.md", "design-review.md")})

    def publish(self, reply=None) -> dict:
        return self.call("cmd_publish", self.root, reply)

    def actions(self, out: dict) -> dict:
        return {r["item"]: r["action"] for r in out["items"]}

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

    def contract(self) -> dict:
        return json.loads((self.src / "story-flow.json").read_text(encoding="utf-8"))

    def test_a_local_requirement_has_no_remote_action(self) -> None:
        self.assertIn("本地单没有远端动作", self.error(lambda: self.call("cmd_publish", self.root, None, system=False)))

    def test_it_needs_a_fetch_after_the_registration(self) -> None:
        self.assertIn("先取一次材", self.error(self.publish))
        self.receipt(self.system_body(), when="2000-01-01T00:00:00+00:00")
        self.assertIn("重新取一次材", self.error(self.publish))

    def test_the_first_publish_baseline_is_the_fetched_development_requirement(self) -> None:
        """首次发布时正文允许覆盖的那一版，是需求系统给本单取回的开发需求正文最新取得的那一版。"""
        batch = self.feature_root / "sources" / "inbox" / "fetch-1"
        batch.mkdir(parents=True)
        body = "# 开发需求\n\n上游先填了一版。\n".encode("utf-8")
        (batch / "AR-design.md").write_bytes(body)
        (batch / ".receipt.json").write_text(json.dumps({"reqNo": FEATURE, "items": [
            {"name": "AR-design.md", "role": "AR", "ticket": FEATURE, "status": "fetched"}]}), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(FLOW.parent / "import_sources.py"), "--feature", FEATURE,
                               "--project-root", str(self.root)], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual(self.digest(body), self.call("_baselines", self.contract())["AR-design.md"])

    def test_the_first_publish_with_nothing_external_writes_all_three(self) -> None:
        self.receipt(None)
        out = self.publish()
        self.assertTrue(out["publishable"], out)
        self.assertEqual({"AR-design.md": "write", "review.md": "write", "design-review.md": "write"}, self.actions(out))
        self.assertIn("首次发布", out["diff"])
        self.assertEqual(["D1 余额刷新的触发时机待定"], out["open_topics"])

    def test_an_external_edit_goes_to_a_person_and_the_grant_covers_only_that_change(self) -> None:
        external = "别人在需求系统上改过的正文\n".encode("utf-8")
        self.receipt(external)
        out = self.publish()
        self.assertFalse(out["publishable"], out)
        self.assertIn("不直接覆盖", out["action"])
        confirmed = self.publish("看过了，按本地这一版覆盖")
        self.assertTrue(confirmed["publishable"], confirmed)
        grant = self.contract()["publish_overrides"][-1]
        self.assertEqual(("AR-design.md", self.digest(external), self.digest(self.local("AR-design.md")), "看过了，按本地这一版覆盖"),
                         (grant["item"], grant["external"], grant["local"], grant["reply"]))
        self.assertTrue(self.publish()["publishable"], "同一处改动、同一份本地件，授权该沿用")
        self.receipt("别人又改了一次\n".encode("utf-8"))
        self.assertFalse(self.publish()["publishable"], "外部又变了，旧授权被泛化沿用")

    def test_a_same_named_attachment_nobody_published_is_a_conflict(self) -> None:
        """首次发布附件：系统上已有同名却不是我们的内容，所有权未确认，交人。"""
        self.receipt(self.system_body(), attachments={"review.md": "别人的附件\n".encode("utf-8")})
        out = self.publish()
        self.assertFalse(out["publishable"], out)
        self.assertEqual("conflict", self.actions(out)["review.md"])
        self.assertEqual("write", self.actions(out)["design-review.md"])

    def test_archived_needs_three_readbacks_of_this_version(self) -> None:
        self.receipt(self.system_body())
        self.assertIn("上传读回不全", self.error(lambda: self.call("cmd_archived", self.root)))
        self.uploaded(checked="2000-01-01T00:00:00+00:00")
        self.assertIn("早于这一版的登记", self.error(lambda: self.call("cmd_archived", self.root)), "旧读回放行了这一版")
        self.uploaded()
        receipt = json.loads((self.src / "fetched.json").read_text(encoding="utf-8"))
        receipt["items"][2] = {**receipt["items"][2], "status": "failed", "note": "本次发布读回尚未完成"}
        (self.src / "fetched.json").write_text(json.dumps(receipt), encoding="utf-8")
        self.assertIn("design-review.md", self.error(lambda: self.call("cmd_archived", self.root)))
        self.assertNotIn("archived", self.contract())
        self.uploaded()
        out = self.call("cmd_archived", self.root)
        self.assertTrue(out["archived"])
        archived = self.contract()["archived"]
        self.assertEqual(self.digest(self.local("design-review.md")), archived["design_review_digest"])
        self.assertEqual(self.contract()["story_basis"]["blueprint_ref"], archived["design_blueprint_ref"])
        for name in ("story.md", "review.md", "design-review.md"):
            self.assertEqual((self.feature_root / "AR" / name).read_bytes(),
                             (self.feature_root / ".backups" / "published" / name).read_bytes())

    def test_after_a_publish_each_item_is_its_own_baseline(self) -> None:
        self.uploaded()
        self.call("cmd_archived", self.root)
        self.uploaded()
        out = self.publish()
        self.assertTrue(out["publishable"], out)
        self.assertEqual({"skip"}, set(self.actions(out).values()))
        self.assertEqual("与上次发布逐字相同", out["diff"])
        self.receipt(self.system_body(),
                     attachments={n: self.local(n) for n in ("review.md", "design-review.md")})
        self.assertFalse(self.publish()["publishable"], "发布之后外部回到了旧版却没当成外部改动")
        self.receipt(self.local("AR-design.md"), attachments={"review.md": self.local("review.md")})
        self.assertEqual("conflict", self.actions(self.publish())["design-review.md"], "发布过的附件被删也是外部改动")

    def test_a_remote_restore_moves_only_the_body_baseline_and_keeps_local_files(self) -> None:
        self.assertIn("还没归档过", self.error(lambda: self.call("cmd_restored")))
        self.uploaded()
        self.call("cmd_archived", self.root)
        story = self.local("AR-design.md")
        older = self.system_body()
        attachments = {n: self.local(n) for n in ("review.md", "design-review.md")}
        self.receipt(older, status="same", attachments=attachments)
        out = self.call("cmd_restored")
        self.assertTrue(out["differs"], out)
        self.assertEqual(story, self.local("AR-design.md"), "远端恢复动了本地文件")
        self.receipt(older, status="same", attachments=attachments)
        out = self.publish()
        self.assertTrue(out["publishable"], "恢复之后外部就是恢复的那一版，不该再当成别人改过")
        self.assertEqual({"AR-design.md": "write", "review.md": "skip", "design-review.md": "skip"}, self.actions(out))
