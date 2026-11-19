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
from flow_steps import answer, write_gaps  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import end_target  # noqa: E402
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
    inbox = feature_root / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
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
    """材料表里产品需求那一行指当前阅读稿 `RR/prd.md`：它就是最新登记的那一版，作者不用改链接。"""


def revise_prd(root: Path, feature_root: Path, extra: str) -> None:
    """上游产品需求出了新版：直接给的原文 RR/prd.md 被改，导入把它登记成新版本。"""
    prd = feature_root / "RR" / "prd.md"
    prd.write_bytes(prd.read_bytes() + extra.encode("utf-8"))
    import_into(root, feature_root, {})


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

    def ask_questions(self, *items: dict) -> dict:
        """按本轮必要问题写问法文件，经真实 `status --questions-file` 生成一次集中 ask。"""
        path = self.root / ".questions.json"
        path.write_text(json.dumps({"items": list(items)}, ensure_ascii=False), encoding="utf-8")
        out = self.flow("status", "--questions-file", str(path))
        self.assertTrue(out.get("success", True), out)
        return out["ask"]

    def business_question(self, item_id: str, question: str | None = None,
                          options: list[str] | None = None) -> dict:
        return {"item_id": item_id, "question": question or f"{item_id}：要定的是哪一件？",
                "options": options if options is not None else [],
                "recommend": "", "reason": "阻断当前切片，当前用户有权决定",
                "source_ref": "AR/story.md"}

    def answer_question(self, ask: dict, item_id: str, reply: str) -> dict:
        return self.flow("decide", "--ask", ask["ask_id"], "--item", item_id, "--reply", reply)

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
        "AR/story.md": "# 需求故事\n\n首版。\n",
    }
    #: 模型据交付件写出来的中间真源：随交付件的修订而变，是结果不是原因，不进判定。
    DERIVED = {
        "AR/story-src/story-template.md": "# 写作设计\n",
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
        revise_prd(self.root, self.feature_root, "\n补一句。\n")
        out = self.update()
        self.assertEqual("changed", out["comparison"], out)
        self.assertIn("source:direct:RR/prd.md", out["changed"])

    def test_intermediate_sources_do_not_count(self) -> None:
        """决策登记与契约手改了也不报：报出来只是对人没有意义的几行。"""
        for rel in self.DERIVED:
            target = self.feature_root / rel
            target.write_text(target.read_text(encoding="utf-8") + "# 手改\n", encoding="utf-8")
        self.assertEqual("unchanged", self.update()["comparison"])

    def test_a_removed_product_is_reported_as_removed(self) -> None:
        (self.feature_root / "AR" / "story.md").unlink()
        out = self.update()
        self.assertIn("AR/story.md", out["changed"], out)


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
                inbox = (self.feature_root / "inbox").resolve().as_posix()
                self.assertEqual({"project_root": self.root.resolve().as_posix(),
                                  "feature_root": self.feature_root.resolve().as_posix(), "inbox": inbox,
                                  "review_inbox": (self.feature_root / "inbox" / "review").resolve().as_posix()},
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
        self.assertTrue(out["restore_copy"].startswith(f"AR/story-src/updates/{self.rid}/restore-"), out["restore_copy"])
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
        for rel in ("AR/design.md", "blueprint/component-blueprint.yaml"):
            target = self.feature_root / rel
            changed[rel] = target.read_bytes() + "开轮之后被改的字节\n".encode("utf-8")
            target.write_bytes(changed[rel])
        # 本轮里原生施工单位写下的阶段产物：不是本扩展拥有的文件，撤回不删、不改
        unit = self.feature_root / "balance-refresh" / "spec" / "spec.md"
        unit.parent.mkdir(parents=True, exist_ok=True)
        unit.write_text("# 施工单位的 Spec（本轮原生写下）\n", encoding="utf-8")
        changed[unit.relative_to(self.feature_root).as_posix()] = unit.read_bytes()
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
    """update 里人定的设计问题沿同一组集中问答记录原话：只存问法、原话与出处，不另立决定账。"""

    def setUp(self) -> None:
        super().setUp()
        self.update()

    def test_it_records_the_asked_question_and_the_actual_words(self) -> None:
        ask = self.ask_questions(self.business_question("D1", "撤销宽限改多少小时？", ["保持 24 小时", "改 36 小时"]))
        out = self.answer_question(ask, "D1", "按 36 小时做")
        self.assertTrue(out.get("success"), out)
        record = json.loads((self.updates / self.rounds()[-1] / "record.json").read_text(encoding="utf-8"))
        row = record["answers"][0]
        self.assertEqual((ask["ask_id"], "D1", "按 36 小时做"),
                         (row["ask_id"], row["item_id"], row["reply"]))
        self.assertEqual("撤销宽限改多少小时？", row["question"])
        self.assertEqual(["保持 24 小时", "改 36 小时"], row["options"])
        self.assertEqual("AR/story.md", row["source_ref"])
        self.assertFalse({"target_ref", "source_revision", "mapped_by"} & set(row),
                         "原话记录带着目标/版本/映射来源")
        self.assertNotIn("答案已批准", json.dumps(out, ensure_ascii=False))
        flow = json.loads((self.src / "story-flow.json").read_text(encoding="utf-8"))
        self.assertNotIn("answers", flow["rounds"][-1], "开着的 update 把原话又抄进材料轮")

    def test_the_words_stay_on_record_after_the_close(self) -> None:
        """收口只关这一轮：人的原话留在该操作记录与导出的答案原件里，不随轮次关闭消失。"""
        ask = self.ask_questions(self.business_question("D1"))
        self.answer_question(ask, "D1", "按 36 小时做")
        (self.updates / self.rounds()[-1] / "update-notes.md").write_text(NOTES, encoding="utf-8")
        self.assertEqual("closed", self.update("--action", "close").get("status"))
        record = json.loads((self.updates / self.rounds()[-1] / "record.json").read_text(encoding="utf-8"))
        self.assertEqual(["按 36 小时做"], [a["reply"] for a in record["answers"]])
        self.assertNotIn("decisions", json.loads((self.src / "story-flow.json").read_text(encoding="utf-8")).get("update") or {},
                         "update 又存了一份决定账")
        self.assertIn("按 36 小时做", json.dumps(self.exported(), ensure_ascii=False))

    def test_the_words_stay_on_record_after_a_restore(self) -> None:
        """还原那一轮不撤销人的原话：原话记录在该操作记录里，导出里仍可追溯。"""
        ask = self.ask_questions(self.business_question("D1"))
        self.answer_question(ask, "D1", "按 36 小时做")
        self.assertEqual("restored", self.update("--action", "restore").get("status"))
        record = json.loads((self.updates / self.rounds()[-1] / "record.json").read_text(encoding="utf-8"))
        self.assertEqual(["按 36 小时做"], [a["reply"] for a in record["answers"]])
        self.assertEqual(["按 36 小时做"],
                         [d["reply"] for d in self.exported()["records"] if d.get("item_id") == "D1"])

    def exported(self) -> dict:
        """最新导出的人答记录（answers.json）。"""
        index = json.loads((self.src / "materials.json").read_text(encoding="utf-8"))
        answers = next(s for s in index["sources"] if s["kind"] == "answer")
        return json.loads((self.feature_root / answers["versions"][-1]["original"]["path"]).read_text(encoding="utf-8"))

    def test_the_answer_is_exported_with_the_question_shown(self) -> None:
        """原话一记下就导出：记录里有当时的问题、候选、原话与出处，不写「所选 = 人的裁决」。"""
        ask = self.ask_questions(self.business_question("D1", "撤销宽限改多少小时？", ["保持 24 小时", "改 36 小时"]))
        self.answer_question(ask, "D1", "按 36 小时做")
        [row] = [d for d in self.exported()["records"] if d.get("item_id") == "D1"]
        self.assertEqual(("撤销宽限改多少小时？", "按 36 小时做"), (row["question"], row["reply"]))
        self.assertEqual(["保持 24 小时", "改 36 小时"], row["options"])
        self.assertNotIn("chosen", row)
        self.assertFalse({"target_ref", "source_revision", "mapped_by"} & set(row))
        text = next(p for p in (self.src / "answers").glob("人工答复-v*.md")
                    if "按 36 小时做" in p.read_text(encoding="utf-8"))
        self.assertNotIn("当前有效", text.read_text(encoding="utf-8"))

    def test_a_new_update_round_does_not_reuse_the_previous_rounds_answer(self) -> None:
        """同一道题在新一次操作里仍要按本操作重新答：不拿上一轮同名题抵扣。"""
        ask = self.ask_questions(self.business_question("D1"))
        self.answer_question(ask, "D1", "按 36 小时做")
        (self.updates / self.rounds()[-1] / "update-notes.md").write_text(NOTES, encoding="utf-8")
        self.assertEqual("closed", self.update("--action", "close").get("status"))
        self.update()                                   # 新一次操作
        again = self.ask_questions(self.business_question("D1"))
        self.assertEqual(["D1"], again["pending"], "新一次操作把上一轮的同名题当成已答")
        self.assertTrue(self.answer_question(again, "D1", "还是 36 小时").get("success"))
        rec = json.loads((self.updates / self.rounds()[-1] / "record.json").read_text(encoding="utf-8"))
        self.assertEqual(["还是 36 小时"], [a["reply"] for a in rec["answers"]])

    def test_it_needs_a_current_ask_and_a_known_item(self) -> None:
        out = self.flow("decide", "--ask", "deadbeef", "--item", "D1", "--reply", "按 36 小时做")
        self.assertIn("没有待回答的设计问答", out.get("error", ""))
        ask = self.ask_questions(self.business_question("D1"))
        out = self.flow("decide", "--ask", ask["ask_id"], "--item", "D9", "--reply", "按 36 小时做")
        self.assertIn("没有题「D9」", out.get("error", ""))
        out = self.flow("decide", "--ask", ask["ask_id"], "--reply", "按 36 小时做")
        self.assertIn("--item", out.get("error", ""))

    def test_an_empty_reply_is_refused(self) -> None:
        """人签只认真实原话——模型的转述不算。"""
        ask = self.ask_questions(self.business_question("D1"))
        out = self.flow("decide", "--ask", ask["ask_id"], "--item", "D1", "--reply", "   ")
        self.assertIn("--reply", out.get("error", ""))

    def test_the_same_question_cannot_be_answered_twice(self) -> None:
        ask = self.ask_questions(self.business_question("D1"), self.business_question("D2"))
        self.assertTrue(self.answer_question(ask, "D1", "按 36 小时做").get("success"))
        out = self.answer_question(ask, "D1", "改成 48 小时")
        self.assertIn("已经记过原话", out.get("error", ""))

    def test_a_changed_question_with_the_old_ask_id_is_refused(self) -> None:
        """问法内容被改却沿用旧 ask_id：读取时重算身份，拒绝记人答。"""
        ask = self.ask_questions(self.business_question("D1"))
        sidecar = self.src / ".ask.json"
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        data["items"][0]["question"] = "换了一个问法"
        sidecar.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        out = self.answer_question(ask, "D1", "按 36 小时做")
        self.assertIn("ask_id 对不上", out.get("error", ""))


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

    def answer(self, chosen: str = "confirm_scope", reply: str = "") -> dict:
        """答材料关卡：明确说编号（1=请人放料、2=材料就是全部），与真实人答同一协议。"""
        write_gaps(self.src)
        text = reply if reply.strip() in ("1", "2") else ("1" if chosen == "supplied" else "2")
        return answer(self.flow, "material_scope", text)

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
        inbox.mkdir(parents=True, exist_ok=True)
        (inbox / "交通卡自动充值-v2.md").write_text("# 产品需求\n\n单日上限 300。\n", encoding="utf-8")
        out = self.update("--action", "inputs")
        self.assertIn("inbox/交通卡自动充值-v2.md", out["pending"], out)
        self.assertEqual("accepted", self.answer("supplied", "新版放进去了")["outcome"])
        self.assertEqual("import_materials", self.next_of(), "有未并入的原件却没先让导入")
        out = self.update()
        self.assertIn("先导入", out.get("error", ""), "AC15：收件箱有未并入的原件时 prepare 要拒绝")
        self.assertIn("交通卡自动充值-v2.md", out["error"])

    def test_inside_an_open_round_every_command_agrees(self) -> None:
        """AC13：update 这一轮开着时，status、round、decide 判定一致。

        新材料登记进当前轮，材料没有第二次关卡的授权；范围沿用已定的、由蓝图承载。
        09-25、09-26 两次实跑都卡在这条序列上。
        """
        self.update("--action", "inputs")
        self.answer()
        self.update()
        rounds = len(self.contract()["rounds"])
        revise_prd(self.root, self.feature_root, "\n单日上限 300。\n")
        self.assertEqual("refresh_round", self.next_of())
        self.flow("round")
        self.assertEqual(rounds, len(self.contract()["rounds"]), "update 期间开了新轮")
        out = self.flow("decide", "--gate", "material_scope", "--ask", "x", "--reply", "1")
        self.assertIn("本轮材料已经确认过了", out.get("error", ""))
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
            save(feature_root, {"schema": 7, "status": "gathering", "rounds": []})
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
        inbox = self.feature_root / "inbox"
        (inbox / "RR-prd.md").write_text("# 产品需求\n\n单日上限 300。\n", encoding="utf-8")
        (inbox / ".classify.json").write_text(json.dumps({"RR-prd.md": "RR"}, ensure_ascii=False), encoding="utf-8")
        hint = self.update("--action", "inputs")["superseded_hint"]
        self.assertEqual("inbox/RR-prd.md", hint[0]["new"])
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
        self.inbox = self.feature_root / "inbox"
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
        text = self.canonical().read_text(encoding="utf-8")
        # 留存按内容起名：改回旧内容的新版本与旧版本共用一份文件，引用那个文件就是采用了用它的最新一版
        by_path: dict[str, int] = {}
        for r in self.index()["files"]:
            if r["source_id"] == f"local:{self.NAME}":
                by_path[r["path"]] = max(by_path.get(r["path"], 0), r["version"])
        hits = {v for path, v in by_path.items() if f"doc/features/{FEATURE}/{path}" in text}
        self.assertLessEqual(len(hits), 1, f"同一来源采用了不止一版：{hits}")
        return next(iter(hits), None)

    def original(self, version: int) -> bytes:
        """这个来源第 `version` 版的原件字节（材料版本导入后不改）。"""
        v = next(v for v in self.versions() if v["version"] == version)
        return (self.feature_root / v["original"]["path"]).read_bytes()

    def adopt(self, data: bytes, basis: str) -> str:
        """一次采用：材料关卡答补料 → 导入 → 开轮 → 登记本轮 → 作者写下依据 → 设计同步，需求条目采用新版本；返回本轮 id。"""
        (self.inbox / self.NAME).write_bytes(data)
        self.assertIn(f"inbox/{self.NAME}", self.update("--action", "inputs")["pending"])
        write_gaps(self.src)
        self.assertEqual("accepted", answer(self.flow, "material_scope", "1")["outcome"])
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
        out = self.update("--action", "close")
        self.assertEqual("closed", out.get("status"), out)

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
        answer(self.flow, "material_scope", "1")
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
        self.out = self.feature / "inbox" / "fetch-1"
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
                         "评审回稿不是需求正文，进了材料批次就没有类别可归")
        self.assertTrue((self.feature / "inbox" / "review" / "fetch-1" / "review-feedback.md").is_file(),
                        "显式评审回稿该落在这次取材批次的评审用途区")

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
        again = self.feature / "inbox" / "fetch-2"
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

    def test_a_published_story_comes_back_as_a_review_input(self) -> None:
        """发布过 Story 之后，系统上的本单正文是交付回流表面：进评审用途区，不带 role 进材料批次。"""
        self.src.mkdir(parents=True, exist_ok=True)
        (self.src / "story-flow.json").write_text(json.dumps({"archived": {"at": "2099-01-01T00:00:00+00:00"}}),
                                                  encoding="utf-8")
        backup = self.feature / ".backups" / "published" / "story.md"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text("# 已发布\n", encoding="utf-8")
        code, receipt = self.fetch(AR, "--out", str(self.out))
        self.assertEqual(0, code, receipt)
        self.assertTrue((self.feature / "inbox" / "review" / "fetch-1" / "AR-design.md").is_file(),
                        "交付回流件没进评审用途区")
        self.assertTrue((self.feature / "inbox" / "review" / "fetch-1" / ".receipt.json").is_file(),
                        "评审批次没有自己的回执")
        self.assertFalse((self.out / "AR-design.md").exists(), "回流件进了材料批次")
        batch = json.loads((self.out / ".receipt.json").read_text(encoding="utf-8"))
        self.assertNotIn("AR-design.md", [i["name"] for i in batch["items"]],
                         "回流件带着 role 进了材料批次回执")
        fetched = json.loads((self.src / "fetched.json").read_text(encoding="utf-8"))
        self.assertEqual("fetched", {i["name"]: i["status"] for i in fetched["items"]}["AR-design.md"])

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

    run("node", str(build), "review", "--action", "prepare", "--reader", "task", "--feature", FEATURE, "--project-root", str(base))
    design_kit.write_review(base, FEATURE, "pass")
    run("node", str(build), "review", "--action", "prepare", "--reader", "task", "--feature", FEATURE, "--project-root", str(base))
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
        prepared = self.run_cmd("node", str(self.BUILD), "review", "--action", "prepare", "--reader", "task", "--feature", FEATURE,
                                "--project-root", str(self.root))
        self.assertEqual(0, prepared.returncode, prepared.stdout + prepared.stderr)
        design_kit.write_review(self.root, FEATURE, "pass")
        received = self.run_cmd("node", str(self.BUILD), "review", "--action", "prepare", "--reader", "task", "--feature", FEATURE,
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
    """登记链（全篇检查 → 审查结果 → 成文依据，一个 story-build 进程里按序跑）哪一步没成：说清做完了什么、哪几步没跑、
    归谁处理，已有登记原样保留；同内容重新登记不换登记时刻。故障注入只换那一个子进程，其余照真跑。"""

    START_REGISTERED = True

    CORE = DEV_EXT / "skills" / "story" / "scripts" / "core"

    def modules(self):
        sys.path.insert(0, str(self.CORE))
        self.addCleanup(lambda: str(self.CORE) in sys.path and sys.path.remove(str(self.CORE)))
        from flow import lifecycle, publish  # noqa: PLC0415
        from flow.state import FlowError  # noqa: PLC0415
        return lifecycle, publish, FlowError

    def registration_returning(self, outcome) -> tuple[str, list]:
        """在本进程里跑登记，登记前核的那个 story-build 子进程换成 outcome（异常就抛；
        `(退出码, stdout)` 就照它返回），其余子进程照真跑。返回报错与登记前核被调了几次。"""
        lifecycle, _, FlowError = self.modules()
        real, calls = subprocess.run, []

        def run(cmd, *args, **kwargs):
            if "registration-check" not in cmd:
                return real(cmd, *args, **kwargs)
            calls.append(cmd)
            if isinstance(outcome, Exception):
                raise outcome
            code, stdout = outcome
            return subprocess.CompletedProcess(cmd, code, stdout, "")

        with unittest.mock.patch.object(lifecycle.subprocess, "run", run), self.assertRaises(FlowError) as caught:
            lifecycle.cmd_story(self.feature_root, self.root)
        return str(caught.exception), calls

    def test_the_three_checks_run_in_one_process(self) -> None:
        """正常登记：三项核对只起一个 story-build 进程，结果照常登记。"""
        lifecycle, _, _ = self.modules()
        real, checks = subprocess.run, []

        def run(cmd, *args, **kwargs):
            if any("story-build" in str(c) for c in cmd):
                checks.append([str(c) for c in cmd])
            return real(cmd, *args, **kwargs)

        with unittest.mock.patch.object(lifecycle.subprocess, "run", run):
            lifecycle.cmd_story(self.feature_root, self.root)
        names = [c[2] for c in checks]
        self.assertEqual(1, names.count("registration-check"), checks)
        self.assertFalse({"check", "review"} & set(names), f"三项核对又各起了进程：{names}")
        self.assertEqual("registration-check", names[0], "登记之后的路由（下一步）之前先跑登记前核")

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

    def test_a_check_process_that_cannot_start_is_an_environment_matter(self) -> None:
        """登记前核的进程起不来：一步都没做，归运行环境，不让作者改稿。"""
        self.register()
        error, calls = self.registration_returning(FileNotFoundError("node 不见了"))
        self.assertIn("story-build registration-check 没能启动", error)
        self.assertIn("已完成：无", error)
        self.assertIn("运行环境问题，业务稿与派生件都不用改", error)
        self.assertEqual(1, len(calls))

    def test_an_internal_error_is_not_sent_to_the_author(self) -> None:
        """成文依据那一步脚本自身异常（退出 2）：说出前两步已完成，归扩展维护者，不让作者改稿，原始输出带出来。"""
        self.register()
        steps = [{"name": "check", "status": "passed", "detail": ""}, {"name": "review", "status": "passed", "detail": ""},
                 {"name": "basis", "status": "error", "detail": "[story-build] 脚本自身异常：注入的故障"}]
        error, calls = self.registration_returning((2, json.dumps({"ok": False, "steps": steps, "review": {"result": "pass"}})))
        self.assertIn("story-build basis 没有正常结束", error)
        self.assertIn("已完成：全篇检查通过；独立审查结果可消费", error)
        self.assertIn("不要为它改真源或草稿", error)
        self.assertIn("扩展维护者", error)
        self.assertNotIn("按下面的报告处理", error)
        self.assertIn("注入的故障", error, "原始输出没带出来")

    def test_an_interrupted_check_process_is_an_environment_matter(self) -> None:
        """退出码既不是 0/1/2（进程被杀之类）、也没给结果：查进程与环境，不让作者改稿，也不说成脚本缺陷。"""
        self.register()
        error, calls = self.registration_returning((137, ""))
        self.assertIn("story-build registration-check 没有正常结束（退出码 137）", error)
        self.assertIn("进程被中断或运行环境出错", error)
        self.assertNotIn("扩展维护者", error)

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

class ARegisteredStoryGoesThroughTheRealEntries(SameNamedOriginalSteps, StoryIsRegisteredAgainAfterChangesCase):
    """V01（已登记起点）：v1 走真实审查与 `story` 登记并收口后，新一轮同名换版或只改表达，再撤回。
    撤回只退可改件；登记、材料版本、蓝图、人签与轮次记录不回写，当前资格照实报，交付门不放行。"""

    def deliver(self) -> subprocess.CompletedProcess:
        return self.run_cmd("node", str(self.BUILD), "check", "--deliver", "--feature", FEATURE, "--project-root", str(self.root))

    def registered_v1(self) -> None:
        """v1 原件经材料关卡导入，设计同步采用它，材料清单改列原件（作者的事），审查通过后登记并收口。"""
        rid = self.adopt("# 甲需求\n\n单日上限 200。\n".encode("utf-8"), "单日上限 200，按甲需求。")
        story = self.feature_root / "AR" / "story.md"
        row = "| 甲需求 PRD [prd.md](../RR/prd.md) | [prd.md](../RR/prd.md) |"
        text = story.read_bytes().decode("utf-8")
        self.assertIn(row, text)
        story.write_bytes(text.replace(row, f"| 甲需求 [甲需求.md](../inbox/{self.NAME}) | [甲需求.md](../inbox/{self.NAME}) | 单日上限。 |\n" + row)
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

    def test_the_json_check_keeps_the_same_conclusion_and_full_notes(self) -> None:
        """机器调用 check --json 与普通人读输出是同一次检查：成功状态、完整 notes 与 problems 同退出码。"""
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        base = ["node", str(self.BUILD), "check", "--deliver", "--feature", FEATURE, "--project-root", str(self.root)]
        human = self.run_cmd(*base)
        machine = self.run_cmd(*base, "--json")
        self.assertEqual(human.returncode, machine.returncode)
        rows = [line for line in machine.stdout.splitlines() if line.startswith("{")]
        self.assertEqual(1, len(rows), machine.stdout)
        data = json.loads(rows[0])
        self.assertEqual({"ok", "deliver", "chapters", "notes", "problems"}, set(data))
        self.assertTrue(data["ok"], data)
        story = self.feature_root / "AR" / "story.md"
        story.write_text(story.read_text(encoding="utf-8").replace("## ", "## 待写：", 1), encoding="utf-8")
        bad = self.run_cmd(*base, "--json")
        self.assertEqual(1, bad.returncode, bad.stdout + bad.stderr)
        broken = json.loads([line for line in bad.stdout.splitlines() if line.startswith("{")][-1])
        self.assertFalse(broken["ok"], broken)
        self.assertTrue(broken["problems"], "失败却没有 problems")

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
        revise_prd(self.root, self.feature_root, "\n改版：回执状态以服务端为准。\n")
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
    """不采用的新材料与归档后改范围：设计采用关系与蓝图修订各按自己的规则走。"""

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
                              f"doc/features/{FEATURE}/assets/ux/meeting-photo.{hashlib.sha256(b'\x89PNG\r\n\x1a\n' + b'0' * 32).hexdigest()[:16]}.png",
                              "--unused", "会场照片，不是需求依据")
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

    def test_rescoping_after_archive_goes_through_the_blueprint(self) -> None:
        """归档后改范围：走 update，由蓝图负责方修订设计；没有 reopen，也没有范围关卡。"""
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        self.mark_archived()
        rid = self.update("--result", "documents")["update"]
        self.assertEqual(rid, self.contract()["update"]["open"])
        design_kit.change_blueprint(self.root, FEATURE, design_kit.ACCESS,
                                    "返回首页时余额刷新", "返回首页或切换账号时余额刷新")
        self.assertEqual("register_story", self.flow("status")["next"])
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        self.assertEqual("story_written", self.contract()["status"])
        self.assert_no_hand_edit()


class RegisteredCase(UpdateCase):
    """已按蓝图成文登记的工程。"""

    #: 登记好 story 的工程只做一次（登记要定稿、审查、登记，一次约 4 秒），每条用例复制一份再开 update
    _registered: Path | None = None

    def setUp(self) -> None:
        self.outputs: list[str] = []
        cls = type(self)
        if cls._registered is None:
            super().setUp()
            design_kit.install_review_mechanism(self.root, DEV_EXT)
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
    """update 的正常第二段串成一条：新材料 → 报输入、问一次补料 → 开轮 → 新料登记进本轮
    → 设计采用新版本（范围由蓝图承载）→ 重新独立审查并登记 → 收口。只测协议与状态，不假装模型的语义；
    每一步都是新起的进程，中途断开后从盘上的状态接着走（跨会话就是重载已有状态）。"""

    def test_the_whole_round(self) -> None:
        contract = lambda: json.loads((self.src / "story-flow.json").read_text(encoding="utf-8"))
        status = lambda: self.flow("status")
        # 上游材料出了新版：同一位置放入改版稿导入，成为产品需求的第二版
        revise_prd(self.root, self.feature_root, "\n改版：余额刷新失败要提示用户。\n")
        # 先报输入，在材料关卡问一次要不要补料；人说就这些
        self.assertEqual("inputs", self.update("--action", "inputs")["stage"])
        write_gaps(self.src)
        self.assertEqual("accepted", answer(self.flow, "material_scope", "2")["outcome"])
        rid = self.update("--result", "documents")["update"]
        self.assertEqual(rid, contract()["update"]["open"])
        # 改版的材料登记进本轮，不开新轮
        rounds = len(contract()["rounds"])
        self.assertEqual("refresh_round", status()["next"])
        self.flow("round")
        self.assertEqual(rounds, len(contract()["rounds"]))
        self.assertEqual(rid, self.flow("update", "--action", "status")["open"], "重载状态：开着的这一轮还在")
        # 范围由蓝图承载：设计按新料同步，需求条目采用产品需求的新版本，蓝图重新准入
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

class PublishChecksTheExternalVersion(RegisteredCase):
    """发布前按交付门核资格，用取材回执逐件核 Story 正文、Review 附件与设计参考附件（蓝图的原生评审投影原字节）：
    E=L 跳过，E=B 可写，其余交人；三件都有这一版登记之后的读回才登记归档。本地单没有远端动作。
    需求系统单由编号决定，这里在进程内把本单当作系统单。"""

    #: 回执里的名字 → 本地来源（相对需求目录）
    NAMES = {"AR-design.md": "AR/story.md", "design-review.md": "blueprint/component-blueprint.review.md"}
    #: 发布前核对的交付门结果。这一组核的是外部版本、基线与授权的政策，交付门本身另有用例：默认把门的结论
    #: 换成「通过」，不为每个政策例重跑一次完整 deliver 检查；`None` 时跑真实的交付门（门的接线用例用它）
    GATE: tuple[bool, dict] | None = (True, {"ok": True, "notes": [], "problems": []})

    def call(self, name: str, *args, system: bool = True):
        core = DEV_EXT / "skills" / "story" / "scripts" / "core"
        sys.path.insert(0, str(core))
        try:
            from flow import publish  # noqa: PLC0415
            gate = self.GATE
            with unittest.mock.patch.object(publish, "system_requirement", lambda _: system), \
                    unittest.mock.patch.object(publish, "_gate", (lambda *_: gate) if gate is not None else publish._gate):
                return getattr(publish, name)(self.feature_root, *args)
        finally:
            sys.path.remove(str(core))

    @staticmethod
    def digest(body: bytes) -> str:
        return "sha256:" + hashlib.sha256(body).hexdigest()[:16]

    def local(self, name: str) -> bytes:
        return (self.feature_root / self.NAMES[name]).read_bytes()

    def system_body(self) -> bytes:
        """系统上原来那份开发需求正文：取材导入的开发需求来源第一版。"""
        return (self.feature_root / "AR" / "design.md").read_bytes()

    #: 对接层给出的系统交付要求：这一组用例的系统要求设计参考附件（三件）；两件的组合在专门的用例里改
    DESIGN_REQUIRED = True

    def receipt(self, body: bytes | None, when: str = "2099-01-01T00:00:00+00:00", status: str = "fetched",
                attachments: dict | None = None, checked: str | None = None, design_required: bool | None = None) -> None:
        """取材回执：正文给 body（None 是系统上没有），设计参考附件默认系统上没有；`checked` 给出时两件都记成上传读回；
        交付要求照对接层写（`design_required`，缺省取本组的系统要求）。"""
        items = []
        for name, value in (("AR-design.md", body), ("design-review.md", (attachments or {}).get("design-review.md"))):
            item = {"name": name, "status": (status if name == "AR-design.md" else "fetched") if value is not None else "absent"}
            if value is not None:
                item["digest"] = self.digest(value)
            if checked:
                item["checkedAt"] = checked
            items.append(item)
        required = self.DESIGN_REQUIRED if design_required is None else design_required
        (self.src / "fetched.json").write_text(json.dumps({"fetchedAt": when, "delivery_requirements": {"design_reference": required},
                                                           "items": items}), encoding="utf-8")

    def readback(self, checked: str, **digests: bytes) -> None:
        """对接层逐件写入并读回之后的回执：给出的各件记成读回的这一份与读回时刻，交付集合等其余字段原样。"""
        path = self.src / "fetched.json"
        receipt = json.loads(path.read_text(encoding="utf-8"))
        for item in receipt["items"]:
            name = item["name"].replace("-", "_").replace(".", "_")
            if name in digests:
                item.update(status="fetched", digest=self.digest(digests[name]), checkedAt=checked)
        path.write_text(json.dumps(receipt), encoding="utf-8")

    def uploaded(self, checked: str = "2099-01-01T00:00:00+00:00") -> None:
        """两件都已上传并读回：发布前核对（真实生产者）记下交付集合，回执里每件是本地当前这一份。"""
        self.receipt(self.local("AR-design.md"), attachments={"design-review.md": self.local("design-review.md")})
        self.publish()
        self.readback(checked, AR_design_md=self.local("AR-design.md"),
                      design_review_md=self.local("design-review.md"))

    def publish(self, reply=None, with_design: bool = False) -> dict:
        return self.call("cmd_publish", self.root, reply, with_design)

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
        batch = self.feature_root / "inbox" / "fetch-1"
        batch.mkdir(parents=True)
        body = "# 开发需求\n\n上游先填了一版。\n".encode("utf-8")
        (batch / "AR-design.md").write_bytes(body)
        (batch / ".receipt.json").write_text(json.dumps({"reqNo": FEATURE, "items": [
            {"name": "AR-design.md", "role": "AR", "ticket": FEATURE, "status": "fetched"}]}), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(FLOW.parent / "import_sources.py"), "--feature", FEATURE,
                               "--project-root", str(self.root)], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual(self.digest(body), self.call("_baselines", self.contract())["AR-design.md"]["digest"])

    def test_publishing_goes_through_the_real_delivery_gate(self) -> None:
        """发布前核对真跑交付门：已登记的这一份过门才可发布；门没过就不发布，报出门的原话。"""
        self.GATE = None
        self.receipt(None)
        self.assertTrue(self.publish()["publishable"], "登记过的稿没过真实的交付门")
        self.GATE = (False, {"ok": False, "notes": [], "problems": ["[story-build check] 交付门的原话"]})
        self.assertIn("交付门没过", self.error(self.publish))

    def test_the_first_publish_with_nothing_external_writes_the_delivery(self) -> None:
        self.receipt(None)
        out = self.publish()
        self.assertTrue(out["publishable"], out)
        self.assertEqual({"AR-design.md": "write", "design-review.md": "write"}, self.actions(out))
        self.assertIn("首次发布", out["diff"])
        self.assertIsInstance(out["pending_gaps"], list)

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
        self.receipt(self.system_body(), attachments={"design-review.md": "别人的附件\n".encode("utf-8")})
        out = self.publish()
        self.assertFalse(out["publishable"], out)
        self.assertEqual("conflict", self.actions(out)["design-review.md"])

    def test_archived_needs_the_readbacks_of_this_version(self) -> None:
        self.receipt(self.system_body())
        self.assertIn("上传读回不全", self.error(lambda: self.call("cmd_archived", self.root)))
        self.uploaded(checked="2000-01-01T00:00:00+00:00")
        self.assertIn("早于这一版的登记", self.error(lambda: self.call("cmd_archived", self.root)), "旧读回放行了这一版")
        self.uploaded()
        receipt = json.loads((self.src / "fetched.json").read_text(encoding="utf-8"))
        receipt["items"][1] = {**receipt["items"][1], "status": "failed", "note": "本次发布读回尚未完成"}
        (self.src / "fetched.json").write_text(json.dumps(receipt), encoding="utf-8")
        self.assertIn("design-review.md", self.error(lambda: self.call("cmd_archived", self.root)))
        self.assertNotIn("archived", self.contract())
        self.uploaded()
        out = self.call("cmd_archived", self.root)
        self.assertTrue(out["archived"])
        archived = self.contract()["archived"]
        self.assertEqual(self.digest(self.local("design-review.md")), archived["design_review_digest"])
        self.assertEqual(self.contract()["story_basis"]["blueprint_ref"], archived["design_blueprint_ref"])
        for name, published in (("AR-design.md", "story.md"), ("design-review.md", "design-review.md")):
            self.assertEqual(self.local(name), (self.feature_root / ".backups" / "published" / published).read_bytes())

    def test_the_delivery_gate_notes_keep_their_original_meaning(self) -> None:
        """交付门的完整 notes 按结构原样带给归档主作者：多行说明、warn 建议、unreviewed 披露都不丢行。"""
        cases = (
            ({"ok": True, "notes": [], "problems": []}, []),
            ({"ok": True, "notes": ["独立审查带非阻断建议通过：把刷新失败提示写清",
                                    "原生问题 1 条：\n  第一行\n  第二行"], "problems": []},
             ["独立审查带非阻断建议通过：把刷新失败提示写清", "原生问题 1 条：\n  第一行\n  第二行"]),
            ({"ok": True, "notes": ["本次没有可用的独立读者（只有阶段 JSON 入口）——已写进 Story 交付章的审查状态"],
              "problems": []},
             ["本次没有可用的独立读者（只有阶段 JSON 入口）——已写进 Story 交付章的审查状态"]),
        )
        for gate, expected in cases:
            with self.subTest(gate=gate):
                self.GATE = (True, gate)
                self.receipt(None)
                out = self.publish()
                self.assertEqual(expected, out["delivery_notes"], out)
                self.assertNotIn("unverified", out, "还在按字面筛未验证项")

    def test_after_a_publish_each_item_is_its_own_baseline(self) -> None:
        self.uploaded()
        self.call("cmd_archived", self.root)
        self.uploaded()
        out = self.publish()
        self.assertTrue(out["publishable"], out)
        self.assertEqual({"skip"}, set(self.actions(out).values()))
        self.assertEqual("与上次发布逐字相同", out["diff"])
        self.receipt(self.system_body(),
                     attachments={"design-review.md": self.local("design-review.md")})
        self.assertFalse(self.publish()["publishable"], "发布之后外部回到了旧版却没当成外部改动")
        self.receipt(self.local("AR-design.md"), attachments={})
        self.assertEqual("conflict", self.actions(self.publish())["design-review.md"], "发布过的附件被删也是外部改动")

    def overwrite_the_system_body(self) -> bytes:
        """一次覆盖了系统正文的归档：发布前核对记下集合，对接层留下覆盖前正文的备份并逐件读回，再登记。返回那份备份。"""
        older = self.system_body()
        self.receipt(older)
        self.assertTrue(self.publish("系统上那份正文看过了，按本地这一版覆盖")["publishable"])
        backup = self.feature_root / ".backups" / "cloud" / "design-20990101000000.md"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(older)
        path = self.src / "fetched.json"
        receipt = json.loads(path.read_text(encoding="utf-8"))
        # 对接层真写了正文：覆盖关联记在回执顶层（取材与发布前核对都保留它）
        receipt["body_write"] = {"target_digest": self.digest(self.local("AR-design.md")),
                                 "backup": ".backups/cloud/design-20990101000000.md",
                                 "written_at": "2099-01-01T00:00:00+00:00", "verified_at": "2099-01-01T00:00:00+00:00"}
        path.write_text(json.dumps(receipt), encoding="utf-8")
        self.readback("2099-01-01T00:00:00+00:00", AR_design_md=self.local("AR-design.md"),
                      design_review_md=self.local("design-review.md"))
        self.assertTrue(self.call("cmd_archived", self.root)["archived"])
        self.assertEqual(".backups/cloud/design-20990101000000.md", self.contract()["archived"]["body_backup"])
        return older

    def restored(self, prepare: bool = False, reply: str | None = None):
        return self.call("cmd_restored", prepare, reply)

    def test_a_remote_restore_moves_only_the_body_baseline_and_keeps_local_files(self) -> None:
        self.assertIn("没有可核的正文覆盖", self.error(lambda: self.restored(True)))
        older = self.overwrite_the_system_body()
        story = self.local("AR-design.md")
        attachments = {"design-review.md": self.local("design-review.md")}
        self.receipt(story, status="same", attachments=attachments, when="2099-01-02T00:00:00+00:00")
        prepared = self.restored(True)
        self.assertEqual(("write", self.digest(older)), (prepared["restore"]["action"], prepared["restore"]["digest"]), prepared)
        self.assertIn("恢复未确认", self.error(self.restored), "没有读回就登记了恢复")
        self.readback("2100-01-01T00:00:00+00:00", AR_design_md=older)
        out = self.restored()
        self.assertTrue(out["differs"], out)
        self.assertEqual(story, self.local("AR-design.md"), "远端恢复动了本地文件")
        self.assertEqual(self.digest(older), self.contract()["archived"]["external_digest"])
        self.receipt(older, status="same", attachments=attachments, when="2100-01-02T00:00:00+00:00")
        out = self.publish()
        self.assertTrue(out["publishable"], "恢复之后外部就是恢复的那一版，不该再当成别人改过")
        self.assertEqual({"AR-design.md": "write", "design-review.md": "skip"}, self.actions(out))

    def test_a_body_written_before_an_attachment_failed_keeps_its_backup_for_restore_and_registration(self) -> None:
        """正文已真实覆盖、附件没写成、还没登记归档：重新取材之后，恢复准备取这次覆盖前的原件；
        同版续传读回齐了再登记，归档记的也是这次覆盖的备份。两条分支从同一个前态出发。"""
        older, story = self.system_body(), self.local("AR-design.md")
        self.receipt(older)
        self.assertTrue(self.publish("系统上那份正文看过了，按本地这一版覆盖")["publishable"])
        # 对接层：覆盖前备份、写正文并读回，记下覆盖关联；之后的附件写失败，没有登记归档
        rel = ".backups/cloud/design-20990101000000.md"
        (self.feature_root / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.feature_root / rel).write_bytes(older)
        written = {"target_digest": self.digest(story), "backup": rel,
                   "written_at": "2099-01-01T00:00:00+00:00", "verified_at": "2099-01-01T00:00:01+00:00"}
        # 重新取材：外部正文已是本地这一份；对接层取材时原样带着覆盖关联（对接层的保留在 test_requirement_system 核）
        self.receipt(story, status="same", when="2099-01-02T00:00:00+00:00")
        path = self.src / "fetched.json"
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["body_write"] = written
        path.write_text(json.dumps(receipt), encoding="utf-8")
        self.assertNotIn("archived", self.contract())
        before = path.read_bytes()

        prepared = self.restored(True)
        self.assertEqual((rel, "write", self.digest(older)),
                         (prepared["restore"]["local"], prepared["restore"]["action"], prepared["restore"]["digest"]), prepared)

        path.write_bytes(before)
        out = self.publish()
        self.assertTrue(out["publishable"], out)
        self.assertEqual("skip", self.actions(out)["AR-design.md"], "正文已是本地这一份还要再写")
        self.assertEqual(written, json.loads(path.read_text(encoding="utf-8"))["body_write"], "发布前核对把覆盖关联丢了")
        self.readback("2099-01-03T00:00:00+00:00", AR_design_md=story,
                      design_review_md=self.local("design-review.md"))
        self.assertTrue(self.call("cmd_archived", self.root)["archived"])
        self.assertEqual(rel, self.contract()["archived"]["body_backup"], "登记没记这次覆盖的备份")

    def test_a_required_design_reference_left_out_of_the_set_is_not_registered(self) -> None:
        """系统要求设计参考附件：交付集合里少了它（被改小了），读回核对不成立、不登记。"""
        self.uploaded()
        path = self.src / "fetched.json"
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["delivery"]["items"] = [i for i in receipt["delivery"]["items"] if i["name"] != "design-review.md"]
        path.write_text(json.dumps(receipt), encoding="utf-8")
        self.assertIn("缺系统要求的设计参考附件", self.error(lambda: self.call("cmd_archived", self.root)))

    def test_a_later_edit_on_the_system_is_not_restored_over_without_a_decision(self) -> None:
        """归档之后有人在系统上改了正文：恢复准备报冲突、不写准备项；人看过仍要恢复，原话只授权这一次的这一处。
        系统上已是恢复目标时只读回。"""
        older = self.overwrite_the_system_body()
        edited = "评审人后来改过的正文\n".encode("utf-8")
        self.receipt(edited, when="2099-01-02T00:00:00+00:00")
        out = self.restored(True)
        self.assertEqual((False, "conflict"), (out["restorable"], out["restore"]["action"]), out)
        self.assertNotIn("restore", json.loads((self.src / "fetched.json").read_text(encoding="utf-8")))
        out = self.restored(True, "看过了，按备份恢复")
        self.assertEqual("authorized", out["restore"]["action"], out)
        self.assertEqual(self.digest(edited), self.contract()["restore_overrides"][-1]["external"])
        self.receipt(older, when="2099-01-03T00:00:00+00:00")
        self.assertEqual("skip", self.restored(True)["restore"]["action"], "系统上已是恢复目标还要写")

    def test_the_design_reference_follows_the_system_requirement(self) -> None:
        """系统不要求设计参考附件时只交正文；本单已有交付请求带上它时交两件；对接层没给交付要求是对接层缺口。"""
        self.receipt(None, design_required=False)
        self.assertEqual({"AR-design.md"}, set(self.actions(self.publish())))
        delivery = json.loads((self.src / "fetched.json").read_text(encoding="utf-8"))["delivery"]
        self.assertEqual(["AR-design.md"], [i["name"] for i in delivery["items"]])
        self.assertEqual({"AR-design.md", "design-review.md"}, set(self.actions(self.publish(with_design=True))))
        path = self.src / "fetched.json"
        receipt = json.loads(path.read_text(encoding="utf-8"))
        del receipt["delivery_requirements"]
        path.write_text(json.dumps(receipt), encoding="utf-8")
        self.assertIn("对接层", self.error(self.publish))

    def test_a_one_item_delivery_keeps_the_earlier_design_attachment(self) -> None:
        """上次交过设计参考附件，这次系统不要求、也没请求：只交正文，发布记录保留上次的附件基线并标明不是这一次的新版。"""
        self.uploaded()
        self.call("cmd_archived", self.root)
        first = self.contract()["archived"]
        self.receipt(self.local("AR-design.md"), attachments={"design-review.md": self.local("design-review.md")},
                     design_required=False)
        self.assertTrue(self.publish()["publishable"])
        self.readback("2099-01-01T00:00:00+00:00", AR_design_md=self.local("AR-design.md"))
        self.call("cmd_archived", self.root)
        archived = self.contract()["archived"]
        self.assertEqual(["AR-design.md"], archived["items"])
        self.assertEqual(first["design_review_digest"], archived["design_review_digest"])
        self.assertIn("这一次没有更新", archived["design_reference"])


class TheDeliveryChainRunsThroughTheAdapter(RegisteredCase):
    """发布、上传、登记与恢复串成一条真实交接：生产者写下的交付集合与恢复准备由对接层（本地替身系统上的真实函数）消费，
    对接层写下的读回由登记消费，测试不代填。核心侧在进程内把本单当系统单；对接层替身只认 AR 单号的命令行入口不经过，
    直接调它导出的函数。系统先不要求设计参考附件（两件）；之后系统要求它，再交付带上它（三件），送审终点据系统上的三件核到。"""

    # 只借发布用例的辅助（进程内调核心、摘要、本地来源），不继承它的用例
    NAMES = PublishChecksTheExternalVersion.NAMES
    #: 这条链真跑交付门
    GATE = None
    digest = staticmethod(PublishChecksTheExternalVersion.digest)
    call, local, system_body, publish, actions, contract = (
        PublishChecksTheExternalVersion.call, PublishChecksTheExternalVersion.local,
        PublishChecksTheExternalVersion.system_body, PublishChecksTheExternalVersion.publish,
        PublishChecksTheExternalVersion.actions, PublishChecksTheExternalVersion.contract)
    ADAPTERS = DEV_EXT / "skills" / "story" / "scripts" / "adapters"
    CALL = """
const [dir, fn, reqNo, out] = process.argv.slice(1, 5);
const mod = require(require('path').join(dir, fn === 'fetchUpstream' ? 'fetch.js' : fn === 'archiveOne' ? 'archive.js' : 'restore.js'));
mod[fn](reqNo, 'token', ...(out ? [{ outDir: out }] : []))
  .then(r => process.stdout.write(JSON.stringify(r)), e => { process.stdout.write(JSON.stringify({ error: e.message })); process.exitCode = 1; });
"""

    def setUp(self) -> None:
        super().setUp()
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.system = Path(holder.name) / "system"
        ticket = self.system / FEATURE
        (ticket / "attachments").mkdir(parents=True)
        (ticket / "detail.json").write_text(json.dumps({"reqNo": FEATURE, "type": "AR", "title": "余额刷新"}), encoding="utf-8")
        (ticket / "design.md").write_bytes(self.system_body())

    def adapter(self, fn: str, out: str | None = None) -> dict:
        proc = subprocess.run(["node", "-e", self.CALL, str(self.ADAPTERS), fn, FEATURE, *([out] if out else []),
                               "--project-root", str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                              env={**_env(), "STORY_REQUIREMENT_SYSTEM_DIR": str(self.system)})
        return json.loads(proc.stdout or "{}")

    def fetch(self) -> None:
        got = self.adapter("fetchUpstream", str(self.feature_root / "inbox" / "fetch-chain"))
        self.assertNotIn("error", got, got)

    def remote(self, rel: str) -> bytes | None:
        f = self.system / FEATURE / rel
        return f.read_bytes() if f.is_file() else None

    def submitted(self) -> list[str]:
        """送审终点没到的原因（空表是到了）。"""
        return end_target.story_submitted(self.root, "doc/features", FEATURE, self.system)

    def test_publish_archive_register_redeliver_and_restore(self) -> None:
        self.fetch()
        self.assertEqual({"AR-design.md"}, set(self.actions(self.publish("系统上那份正文看过了，按本地这一版覆盖"))))
        self.assertNotIn("error", self.adapter("archiveOne"))
        self.assertTrue(self.call("cmd_archived", self.root)["archived"])
        self.assertEqual((self.local("AR-design.md"), None),
                         (self.remote("design.md"), self.remote("attachments/design-review.md")))
        archived = self.contract()["archived"]
        self.assertEqual(["AR-design.md"], archived["items"])
        self.assertEqual(self.system_body(), (self.feature_root / archived["body_backup"]).read_bytes(), "覆盖前的正文没留住")
        self.assertEqual([], self.submitted())

        # 系统改为要求设计参考附件：取材带回这条要求，两件的交付就不算送到；再交付一次，正文与 Review 判相同、只写设计参考附件
        detail = self.system / FEATURE / "detail.json"
        detail.write_text(json.dumps({**json.loads(detail.read_text(encoding="utf-8")), "design_reference_required": True}), encoding="utf-8")
        self.fetch()
        self.assertTrue(any("要求设计参考附件" in m for m in self.submitted()), self.submitted())
        out = self.publish()
        self.assertEqual({"AR-design.md": "skip", "design-review.md": "write"}, self.actions(out))
        self.assertNotIn("error", self.adapter("archiveOne"))
        self.assertTrue(self.call("cmd_archived", self.root)["archived"])
        self.assertEqual(self.local("design-review.md"), self.remote("attachments/design-review.md"))
        self.assertEqual(["AR-design.md", "design-review.md"], self.contract()["archived"]["items"])
        self.assertEqual([], self.submitted())

        # 评审人之后在系统上改了正文：再发布被拦，对接层不被调用
        (self.system / FEATURE / "design.md").write_text("评审人改过的正文\n", encoding="utf-8")
        self.fetch()
        self.assertFalse(self.publish()["publishable"])

        # 远端恢复：准备看到他人改动报冲突、不写；改回之后准备可写，对接层只照准备写正文并读回，登记据读回
        out = self.call("cmd_restored", True, None)
        self.assertEqual("conflict", out["restore"]["action"], out)
        (self.system / FEATURE / "design.md").write_bytes(self.local("AR-design.md"))
        self.fetch()
        self.assertEqual("write", self.call("cmd_restored", True, None)["restore"]["action"])
        self.assertNotIn("error", self.adapter("restoreOne"))
        self.assertEqual(self.system_body(), self.remote("design.md"))
        self.assertIsNone(self.remote("attachments/review.md"), "恢复动了不存在的历史附件")
        restored = self.call("cmd_restored", False, None)
        self.assertEqual(self.digest(self.system_body()), restored["external"])


class DesignFeedbackGoesToTheBlueprintOwner(RegisteredCase):
    """设计反馈只作为原生 blueprint-review-feedback@1 传输件：候选资格由原生判，这里不记第二套决定状态。"""

    TARGET = "view:logical/node:wallet-balance"
    contract = PublishChecksTheExternalVersion.contract

    def setUp(self) -> None:
        super().setUp()
        self.update()
        self.rid = self.contract()["update"]["open"]
        blueprint = yaml.safe_load((self.feature_root / "blueprint" / "component-blueprint.yaml").read_text(encoding="utf-8"))
        self.blueprint_id = blueprint["blueprint_id"]
        self.component_id = blueprint["component_id"]
        self.reviewed = self.contract()["story_basis"]["blueprint_ref"]["revision"]

    def item(self, fid: str = "f1", **kw) -> dict:
        base = {"feedback_id": fid, "kind": "opinion", "source_revision": self.reviewed,
                "target_ref": self.TARGET, "body": "余额刷新要在回到首页时发生，材料没写切账号之后怎样。"}
        return {**base, **kw}

    def write(self, items: list[dict], *, batch: dict | None = None) -> None:
        doc = {"artifact": "blueprint-review-feedback@1", "blueprint_id": self.blueprint_id,
               "component_id": self.component_id, "source_revision": self.reviewed, "items": items, **(batch or {})}
        path = self.updates / self.rid / "design-feedback.json"
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def feedback(self) -> dict:
        return self.update("--action", "feedback")

    def test_a_qualified_opinion_is_not_an_acceptance(self) -> None:
        self.write([self.item()])
        out = self.feedback()
        self.assertTrue(out.get("eligible"), out)
        self.assertIn("update-notes", out["action"], "update 的下一步没指本轮 notes")
        self.assertEqual([("f1", "待确认", [])],
                         [(x["feedback_id"], x["state"], x["related_decisions"]) for x in out["feedback"]])
        record = json.loads((self.updates / self.rid / "record.json").read_text(encoding="utf-8"))
        self.assertEqual(self.reviewed, record["design_feedback"]["source_revision"])

    def test_a_new_problem_may_point_at_the_blueprint_itself(self) -> None:
        """新问题还没有 gap：指现有蓝图并说明受影响范围，由 owner 形成真正的新 gap，不先让人再签一张表。"""
        self.write([self.item("new-problem", target_ref=f"blueprint:{self.blueprint_id}",
                              body="余额刷新的范围还没有结论，按当前蓝图看受影响节点。")])
        out = self.feedback()
        self.assertTrue(out.get("eligible"), out)

    def test_a_fact_without_evidence_is_not_a_candidate(self) -> None:
        self.write([self.item("fact-1", kind="fact_supplement", body="材料里写了回到首页刷新。")])
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("review_feedback_fact_without_evidence", [i.get("id") for i in out["native_issues"]], out)

    def test_a_ruling_without_authority_is_not_a_ruling(self) -> None:
        self.write([self.item("ruling-1", kind="authoritative_ruling")])
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("review_feedback_authority_insufficient", [i.get("id") for i in out["native_issues"]], out)

    def test_an_old_revision_is_named_not_relabelled(self) -> None:
        self.write([self.item(source_revision=self.reviewed + 1)], batch={"source_revision": self.reviewed + 1})
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("被评的蓝图版本", "；".join(out["problems"]), out)
        self.assertIn("review_feedback_stale_source_revision", [i.get("id") for i in out["native_issues"]], out)

    def test_a_target_outside_the_blueprint_is_refused(self) -> None:
        self.write([self.item(target_ref="view:logical/node:no-such-node")])
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("review_feedback_target_unresolvable", [i.get("id") for i in out["native_issues"]], out)

    def test_evidence_refs_must_point_at_a_real_original(self) -> None:
        self.write([self.item("fact-2", kind="fact_supplement", body="材料里写了回到首页刷新。",
                              evidence_refs=["inbox/review/no-such-batch/AR-design.md"])])
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("读不到", "；".join(out["problems"]), out)

    def test_an_opinion_carrying_a_decision_is_refused(self) -> None:
        self.write([self.item(kind="opinion", decision={"verdict": "accept", "rationale": "我同意"})])
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("review_feedback_non_ruling_carries_decision", [i.get("id") for i in out["native_issues"]], out)

    def test_the_initial_round_reads_its_feedback_from_the_answers_directory(self) -> None:
        """首次问答不要求先伪造一次 update：反馈文件从本轮 init 的问法答复目录定位。"""
        rid = self.contract()["update"]["open"]
        rec = json.loads((self.updates / rid / "record.json").read_text(encoding="utf-8"))
        rec["status"] = "closed"
        (self.updates / rid / "record.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        contract = self.contract()
        contract["update"] = {"open": None, "last_closed": rid}
        (self.src / "story-flow.json").write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
        answers = self.src / "answers"
        answers.mkdir(parents=True, exist_ok=True)
        doc = {"artifact": "blueprint-review-feedback@1", "blueprint_id": self.blueprint_id,
               "component_id": self.component_id, "source_revision": self.reviewed, "items": [self.item("first-1")]}
        (answers / "design-feedback.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        out = self.flow("update", "--action", "feedback")
        self.assertTrue(out.get("success", True), out)
        self.assertTrue(out.get("eligible"), out)
        self.assertEqual("AR/story-src/answers/design-feedback.json", out["where"])
        self.assertIn("design_feedback", self.contract())


class ReviewInputFailuresAndMissingOriginalsAreReported(RegisteredCase):
    """评审输入按当次取材回执的逐件结果核：取得、失败、回执有件而原件缺失、摘要不符各说各的，
    历史批次不重复当成本轮输入，本地评审件按原件列。"""

    def inputs(self) -> dict:
        out = self.flow("update", "--action", "inputs")
        self.assertEqual("inputs", out["stage"], out)
        return out

    def deliver(self, batch: str, items: list[dict], when: str = "2099-02-02T00:00:00+00:00") -> Path:
        folder = self.feature_root / "inbox" / "review" / batch
        folder.mkdir(parents=True, exist_ok=True)
        (folder / ".receipt.json").write_text(json.dumps({"fetchedAt": when, "items": items}, ensure_ascii=False),
                                              encoding="utf-8")
        (self.src / "fetched.json").write_text(json.dumps({
            "fetchedAt": when, "delivery_requirements": {"design_reference": True},
            "review_out": f"inbox/review/{batch}", "items": items}, ensure_ascii=False), encoding="utf-8")
        return folder

    @staticmethod
    def row(name: str, body: bytes | None, *, saved: str | None = None, sha: str | None = None,
            status: str = "fetched", digest: str | None = None) -> dict:
        out = {"name": name, "status": status}
        if body is not None:
            out["sha256"] = hashlib.sha256(body).hexdigest()
            out["digest"] = f"sha256:{out['sha256'][:16]}"
        if saved:
            out["saved"] = saved
        if sha:
            out["sha256"] = sha
        return out

    def test_each_item_state_says_what_actually_happened(self) -> None:
        body = "评审人改过的正文\n".encode("utf-8")
        batch = "fetch-mixed"
        folder = self.feature_root / "inbox" / "review" / batch
        (folder / "AR-design.md").parent.mkdir(parents=True, exist_ok=True)
        (folder / "AR-design.md").write_bytes(body)
        design = "系统上的设计参考\n".encode("utf-8")
        (folder / "design-review.md").write_bytes(design)
        items = [
            self.row("AR-design.md", body, saved=f"inbox/review/{batch}/AR-design.md"),
            self.row("review-feedback.md", None, status="failed"),
            self.row("review.md", b"x", saved=f"inbox/review/{batch}/review.md"),
            self.row("design-review.md", design, saved=f"inbox/review/{batch}/design-review.md",
                     sha="0" * 64),
        ]
        self.deliver(batch, items)
        out = self.inputs()
        states = {e["system_item"]: e for e in out["review_inputs"]}
        self.assertEqual("已取得", states["AR-design.md"]["state"])
        self.assertEqual("失败", states["review-feedback.md"]["state"])
        self.assertEqual("缺原件", states["review.md"]["state"])
        self.assertEqual("摘要或身份不符", states["design-review.md"]["state"])
        self.assertIn("缺原件", out["action"])
        self.assertIn("不符", out["action"])

    def review_inputs(self) -> list[dict]:
        core = DEV_EXT / "skills" / "story" / "scripts" / "core"
        sys.path.insert(0, str(core))
        try:
            from flow import update as update_mod  # noqa: PLC0415
            return update_mod._review_inputs(self.feature_root)
        finally:
            sys.path.remove(str(core))

    def local_opinion(self, text: str = "本地评审意见\n") -> Path:
        path = self.feature_root / "inbox" / "review" / "本地意见.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_a_missing_whole_batch_still_names_every_expected_item(self) -> None:
        """整批目录被移走时，总回执里本应取得的件仍逐件列名、状态、来源与恢复提示；本地意见不顶替它。"""
        body = "评审人改过的正文\n".encode("utf-8")
        folder = self.deliver("fetch-gone", [
            self.row("AR-design.md", body, saved="inbox/review/fetch-gone/AR-design.md"),
            self.row("review-feedback.md", None, status="failed")])
        (folder / "AR-design.md").write_bytes(body)
        self.local_opinion()
        shutil.rmtree(folder)
        out = self.inputs()
        states = {e["system_item"]: e for e in out["review_inputs"] if e.get("system_item")}
        self.assertEqual("缺原件", states["AR-design.md"]["state"], states)
        self.assertEqual("失败", states["review-feedback.md"]["state"], states)
        self.assertEqual("inbox/review/fetch-gone", states["AR-design.md"]["batch"])
        self.assertIn("从 inbox/review/fetch-gone 重新取回或核实", out["action"])
        self.assertTrue(any(str(e["path"]).endswith("本地意见.md") for e in out["review_inputs"]),
                        "只剩本地意见时系统件消失了")

    def test_a_broken_current_batch_receipt_names_the_file(self) -> None:
        """当前批次的回执损坏要报具体文件，不把这一批说成没有、也不拿本地件顶替。"""
        body = "这一批的正文\n".encode("utf-8")
        folder = self.deliver("fetch-broken", [self.row("AR-design.md", body,
                                                        saved="inbox/review/fetch-broken/AR-design.md")])
        (folder / "AR-design.md").write_bytes(body)
        (folder / ".receipt.json").write_text("{ 坏", encoding="utf-8")
        out = self.flow("update", "--action", "inputs")
        self.assertFalse(out.get("success", True), out)
        self.assertIn("inbox/review/fetch-broken/.receipt.json", out.get("error", ""))

    def test_a_broken_historical_receipt_is_listed_without_blocking_the_current_batch(self) -> None:
        old = self.feature_root / "inbox" / "review" / "fetch-old"
        old.mkdir(parents=True, exist_ok=True)
        (old / ".receipt.json").write_text("{ 坏", encoding="utf-8")
        (old / "旧意见.md").write_text("上一批的本地文件\n", encoding="utf-8")
        body = "这一批的正文\n".encode("utf-8")
        folder = self.deliver("fetch-now", [self.row("AR-design.md", body,
                                                     saved="inbox/review/fetch-now/AR-design.md")])
        (folder / "AR-design.md").write_bytes(body)
        rows = self.review_inputs()
        self.assertEqual("fetched", next(r for r in rows if r.get("system_item") == "AR-design.md")["status"])
        self.assertEqual("unclear", next(r for r in rows if r.get("path") == "inbox/review/fetch-old/旧意见.md")["status"])
        self.assertEqual("batch_unreadable", next(r for r in rows if r["status"] == "batch_unreadable")["status"])

    def test_each_historical_receipt_is_read_at_most_once(self) -> None:
        """8 批历史回执加 1 份本地件：一次枚举每份回执至多读一次。"""
        for i in range(8):
            folder = self.feature_root / "inbox" / "review" / f"fetch-{i}"
            folder.mkdir(parents=True, exist_ok=True)
            body = f"第 {i} 批\n".encode("utf-8")
            (folder / f"file-{i}.md").write_bytes(body)
            (folder / ".receipt.json").write_text(json.dumps({"items": [
                {"name": f"file-{i}.md", "saved": f"inbox/review/fetch-{i}/file-{i}.md",
                 "sha256": hashlib.sha256(body).hexdigest(), "status": "fetched"}]}), encoding="utf-8")
        self.local_opinion()
        self.deliver("fetch-current", [])
        real = Path.read_text
        reads: list[str] = []

        def counting(path, *args, **kwargs):
            if path.name == ".receipt.json":
                reads.append(path.as_posix())
            return real(path, *args, **kwargs)

        with unittest.mock.patch.object(Path, "read_text", counting):
            self.review_inputs()
        self.assertEqual(sorted(reads), sorted(set(reads)), "同一份历史回执被读了不止一次")
        self.assertLessEqual(len(reads), 9, f"一次枚举读了 {len(reads)} 次回执")

    def test_a_historical_batch_is_not_reported_as_this_round_input(self) -> None:
        old = "上一批的正文\n".encode("utf-8")
        self.deliver("fetch-old", [self.row("AR-design.md", old, saved="inbox/review/fetch-old/AR-design.md")])
        (self.feature_root / "inbox" / "review" / "fetch-old" / "AR-design.md").write_bytes(old)
        current = "这一批的正文\n".encode("utf-8")
        self.deliver("fetch-new", [self.row("AR-design.md", current, saved="inbox/review/fetch-new/AR-design.md")])
        (self.feature_root / "inbox" / "review" / "fetch-new" / "AR-design.md").write_bytes(current)
        out = self.inputs()
        self.assertEqual([f"inbox/review/fetch-new/AR-design.md"],
                         [e["path"] for e in out["review_inputs"] if e.get("system_item")],
                         "历史批次被当成本轮输入")

    def test_a_local_review_note_is_listed_as_an_original(self) -> None:
        local = self.feature_root / "inbox" / "review" / "本地意见.md"
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text("评审人的批注\n", encoding="utf-8")
        self.deliver("fetch-empty", [])
        out = self.inputs()
        row = next(e for e in out["review_inputs"] if e["path"] == "inbox/review/本地意见.md")
        self.assertEqual((None, "未读"), (row["system_item"], row["state"]))


class FirstFeedbackNeedsTheQuestioningCandidate(RegisteredCase):
    """首次反馈（还没有成文登记）评的是质询当时那一版候选：由调用方带第 7 块的候选路径，
    读候选只在一处（同轮目录身份、task/reply、YAML 蓝图与版本），不能靠目录排序或只凭盘上一份 draft；
    授权裁决要先有可追到人的可读原话，独立读者的建议不能代替人的答复。"""

    TARGET = "view:logical/node:wallet-balance"
    contract = PublishChecksTheExternalVersion.contract

    def setUp(self) -> None:
        super().setUp()
        contract = self.contract()
        self.reviewed = contract["story_basis"]["blueprint_ref"]["revision"]
        contract.pop("story_basis", None)          # 还没有成文登记：首次问答
        (self.src / "story-flow.json").write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
        self.blueprint = yaml.safe_load(
            (self.feature_root / "blueprint" / "component-blueprint.yaml").read_text(encoding="utf-8"))
        self.round = self.candidate(self.reviewed)

    def candidate(self, revision: int, *, quoted: bool = False, reply: bool = True, task: bool = True) -> Path:
        quote = '"' if quoted else ''
        body = (f"artifact: component-blueprint@1\nblueprint_id: {quote}{self.blueprint['blueprint_id']}{quote}\n"
                f"component_id: {quote}{self.blueprint['component_id']}{quote}\nrevision: {revision}\n")
        sha = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
        folder = self.feature_root / "blueprint" / "questioning" / sha
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "candidate.yaml").write_bytes(body.encode("utf-8"))
        if task:
            (folder / "task.md").write_text("质询任务原件\n", encoding="utf-8")
        if reply:
            (folder / "reply.md").write_text("本轮仅允许人工受理，最终规则待定。\n", encoding="utf-8")
        return folder

    def path_of(self, folder: Path) -> str:
        return (folder / "candidate.yaml").relative_to(self.root).as_posix()

    def human_words(self, text: str = "本轮仅允许人工受理，最终规则待定。") -> str:
        """已导出的人答原件：走真实 `status` 生成问法、`decide` 记原话，由产品导出，不手写。"""
        if getattr(self, "_human_ref", None):
            return self._human_ref
        ask = self.ask_questions(self.business_question(
            "owner-answer", "本轮允许的处理方式？", [text, "按原规则"]))
        out = self.answer_question(ask, "owner-answer", text)
        self.assertTrue(out.get("success", True), out)
        path = sorted((self.src / "answers").glob("人工答复-v*.md"))[-1]
        self._human_ref = path.relative_to(self.feature_root).as_posix()
        return self._human_ref

    def write(self, *, revision: int | None = None, kind: str = "authoritative_ruling",
              refs: list[str] | None = None) -> None:
        item = {"feedback_id": "f1", "kind": kind, "source_revision": revision or self.reviewed,
                "target_ref": self.TARGET, "body": "本轮仅允许人工受理，最终规则待定。"}
        if kind == "authoritative_ruling":
            item["authority"] = {"owner": "需求负责人", "role": "需求负责人"}
            item["decision"] = {"verdict": "amend", "rationale": "按原话限定本轮范围"}
        item["evidence_refs"] = refs if refs is not None else [self.human_words()]
        doc = {"artifact": "blueprint-review-feedback@1", "blueprint_id": self.blueprint["blueprint_id"],
               "component_id": self.blueprint["component_id"], "source_revision": revision or self.reviewed,
               "items": [item]}
        answers = self.src / "answers"
        answers.mkdir(parents=True, exist_ok=True)
        (answers / "design-feedback.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def feedback(self, candidate: Path | None = None) -> dict:
        extra = ["--questioning-candidate", self.path_of(candidate or self.round)] if candidate or self.round else []
        return self.flow("update", "--action", "feedback", *extra)

    def test_a_ruling_with_its_words_is_checked_against_the_questioned_candidate(self) -> None:
        self.write()
        out = self.feedback()
        self.assertTrue(out.get("eligible"), out)
        self.assertRegex(self._human_ref, r"^AR/story-src/answers/人工答复-v\d+\.md$",
                         "出处不是产品导出的人答原件")
        self.assertEqual((self.round.name, self.reviewed),
                         (out["questioning"]["round"], out["questioning"]["revision"]))
        self.assertEqual(self.path_of(self.round), out["questioning"]["candidate"])
        self.assertTrue(out["candidates"], "够格却没有给出原生候选")
        self.assertIn("质询原件", out["action"], "init 成功提示没有指本轮质询原件")
        self.assertNotIn("本轮 update-notes", out["action"], "init 成功提示指错了落点")

    def test_a_sole_author_draft_is_not_a_person_original(self) -> None:
        """作者自己的计划/报告只是可读文件：没有来源身份，不能承担人的授权。"""
        draft = self.src / "作者计划.md"
        draft.write_text("# 作者计划\n\n本轮只允许人工受理。\n", encoding="utf-8")
        self.write(refs=["AR/story-src/作者计划.md"])
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("不能代替人的答复", "；".join(out["problems"]), out)
        self.assertIsNone(out["candidates"], "阻断反馈同时给出了可提交候选")

    def test_a_file_that_only_looks_like_an_answer_export_is_not_one(self) -> None:
        """目录名像 answers、文件名像导出的手写件，没有材料索引登记就不是人答。"""
        fake = self.src / "answers" / "人工答复-伪造.md"
        fake.parent.mkdir(parents=True, exist_ok=True)
        fake.write_text("# 人工答复\n\n本轮只允许人工受理。\n", encoding="utf-8")
        self.write(refs=["AR/story-src/answers/人工答复-伪造.md"])
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("不能代替人的答复", "；".join(out["problems"]), out)

    def test_changed_bytes_of_the_exported_answer_are_a_digest_drift(self) -> None:
        ref = self.human_words()
        path = self.feature_root / ref
        path.write_bytes(path.read_bytes() + "后补的一句。\n".encode("utf-8"))
        self.write(refs=[ref])
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("摘要漂移", "；".join(out["problems"]), out)

    def test_a_person_original_may_be_accompanied_by_technical_evidence(self) -> None:
        """多条引用允许人的原件与技术佐证并存；只有技术佐证时才不能单独承担授权。"""
        draft = self.src / "作者计划.md"
        draft.write_text("# 作者计划\n\n转述。\n", encoding="utf-8")
        self.write(refs=[self.human_words(), "AR/story-src/作者计划.md"])
        out = self.feedback()
        self.assertTrue(out.get("eligible"), out)
        self.assertTrue(out["candidates"], out)

    def test_a_reference_outside_this_requirement_is_refused(self) -> None:
        self.write(refs=["framework.config.json"])
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("越出本需求的来源集合", "；".join(out["problems"]), out)

    def test_an_annotation_actually_obtained_before_the_update_is_a_source(self) -> None:
        """init 还没有 prepare：本次实际取得、来源可核的评审输入（本地批注）也可作裁决出处。"""
        review = self.feature_root / "inbox" / "review"
        review.mkdir(parents=True, exist_ok=True)
        (review / "本轮批注.md").write_text("本轮同意：只允许人工受理，仅本轮。\n", encoding="utf-8")
        self.write(refs=["inbox/review/本轮批注.md"])
        out = self.feedback()
        self.assertTrue(out.get("eligible"), out)

    def test_a_registered_original_is_a_formal_source(self) -> None:
        """材料索引登记的原件有来源身份；它是“可能载有人签的来源”，具体效力仍由 owner 核定。"""
        self.write(refs=["AR/design.md"])
        out = self.feedback()
        self.assertTrue(out.get("eligible"), out)
        self.assertTrue(out["candidates"], out)

    def test_an_opinion_is_not_upgraded_to_a_ruling(self) -> None:
        """「本轮同意」与「建议以后做」都是人在说话，但不由脚本当成授权裁决：意见不产生裁决候选。"""
        doc = {"artifact": "blueprint-review-feedback@1", "blueprint_id": self.blueprint["blueprint_id"],
               "component_id": self.blueprint["component_id"], "source_revision": self.reviewed,
               "items": [{"feedback_id": "agree", "kind": "opinion", "source_revision": self.reviewed,
                          "target_ref": self.TARGET, "body": "本轮同意，按这个做。"},
                         {"feedback_id": "later", "kind": "suggestion", "source_revision": self.reviewed,
                          "target_ref": self.TARGET, "body": "建议以后再做。"}]}
        (self.src / "answers").mkdir(parents=True, exist_ok=True)
        (self.src / "answers" / "design-feedback.json").write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        out = self.feedback()
        self.assertTrue(out.get("eligible"), out)
        self.assertEqual([], (out["candidates"] or {}).get("rulings") or [],
                         "意见被当成了授权裁决候选")
        self.assertEqual(["待确认", "待确认"], [x["state"] for x in out["feedback"]])

    def test_the_explicit_candidate_wins_over_directory_order(self) -> None:
        """多份候选并存（含合法引号与后建目录）：被评对象是显式给的那一份，不按目录排序取最后。"""
        later = self.candidate(self.reviewed, quoted=True)
        self.assertNotEqual(self.round, later)
        self.write()
        out = self.feedback(self.round)
        self.assertTrue(out.get("eligible"), out)
        self.assertEqual(self.round.name, out["questioning"]["round"], "按目录排序选了别的候选")

    def test_a_ruling_without_any_original_is_not_eligible(self) -> None:
        self.write(refs=[])
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("有权裁决却没有引用", "；".join(out["problems"]), out)
        self.assertIsNone(out["candidates"], "阻断反馈同时给出了可提交候选")

    def test_an_unreadable_or_blank_original_is_not_eligible(self) -> None:
        cases = {
            "空白": ([""], "是空白"),
            "原生地址": (["evidence:somewhere"], "不是可读原件"),
            "缺失": (["AR/story-src/answers/不存在.md"], "读不到"),
        }
        for name, (refs, why) in cases.items():
            with self.subTest(name):
                self.write(refs=refs)
                out = self.feedback()
                self.assertFalse(out.get("eligible"), out)
                self.assertIn(why, "；".join(out["problems"]), out)

    def test_a_readers_reply_cannot_stand_in_for_the_persons_words(self) -> None:
        self.write(refs=[f"blueprint/questioning/{self.round.name}/reply.md"])
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("不能代替人的答复", "；".join(out["problems"]), out)

    def test_an_old_revision_cannot_be_relabelled(self) -> None:
        self.write(revision=self.reviewed + 1)
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("被评的蓝图版本", "；".join(out["problems"]), out)

    def test_a_candidate_without_task_or_reply_is_not_a_questioning_round(self) -> None:
        for missing in ("task", "reply"):
            with self.subTest(missing):
                folder = self.candidate(self.reviewed + (1 if missing == "task" else 2),
                                        reply=missing != "reply", task=missing != "task")
                self.write()
                out = self.feedback(folder)
                self.assertFalse(out.get("eligible"), out)
                self.assertIn("质询原件", "；".join(i.get("message", "") for i in out["native_issues"]), out)

    def test_without_a_questioning_candidate_the_first_feedback_stops_with_the_entry(self) -> None:
        self.write()
        out = self.flow("update", "--action", "feedback")
        self.assertFalse(out.get("success", True), out)
        self.assertIn("第 7 块", out.get("error", ""), out)
        self.assertIn("--questioning-candidate", out.get("error", ""), out)

    def test_a_fixed_candidate_is_rechecked_after_an_ineligible_attempt(self) -> None:
        """因缺原件没获资格的那次只留诊断：补上 reply 后重跑要重新核这份原件。"""
        folder = self.candidate(self.reviewed, quoted=True, reply=False)
        self.write()
        first = self.feedback(folder)
        self.assertFalse(first.get("eligible"), first)
        (folder / "reply.md").write_text("本轮仅允许人工受理，最终规则待定。\n", encoding="utf-8")
        again = self.feedback(folder)
        self.assertTrue(again.get("eligible"), again)


class ARulingSourceIsCheckedAgainstTheRegisterAndThisRound(RegisteredCase):
    """R2：有权裁决的出处按材料索引与本轮 prepare 固定的评审输入核，不按「文件存在」给身份。

    同一条反馈只换出处：真实导出的人答、本轮实际取得的人工批注、材料索引登记的原件与可换版位置的稳定行
    够格；作者稿、质询回复与 prepare 之后才到的文件只能随附，不能单独承担人的授权。
    """

    TARGET = DesignFeedbackGoesToTheBlueprintOwner.TARGET
    contract = DesignFeedbackGoesToTheBlueprintOwner.contract
    ANNOTATION = "inbox/review/本轮批注.md"

    def before_prepare(self) -> None:
        """prepare 之前的输入替身（子类往这里放系统回流的评审输入）。"""

    def setUp(self) -> None:
        super().setUp()
        blueprint = yaml.safe_load((self.feature_root / "blueprint" / "component-blueprint.yaml")
                                   .read_text(encoding="utf-8"))
        self.blueprint_id = blueprint["blueprint_id"]
        self.component_id = blueprint["component_id"]
        self.annotation = self.feature_root / self.ANNOTATION
        self.annotation.parent.mkdir(parents=True, exist_ok=True)
        self.annotation.write_text("本轮同意：只允许人工受理，仅本轮。\n", encoding="utf-8")
        self.before_prepare()
        # 评审输入由本轮 prepare 固定：批注/系统件在这之前就位才算这一轮的原件
        self.update()
        self.rid = self.contract()["update"]["open"]
        self.reviewed = self.contract()["story_basis"]["blueprint_ref"]["revision"]

    def human_answer(self, text: str = "本轮同意：只允许人工受理，仅本轮。") -> str:
        """真实 `status`→`decide` 导出的人答原件；不手写产品应导出的证据。"""
        if getattr(self, "_human_ref_update", None):
            return self._human_ref_update
        ask = self.ask_questions(self.business_question(
            "owner-answer", "本轮允许的处理方式？", [text, "按原规则"]))
        out = self.answer_question(ask, "owner-answer", text)
        self.assertTrue(out.get("success", True), out)
        path = sorted((self.src / "answers").glob("人工答复-v*.md"))[-1]
        self._human_ref_update = path.relative_to(self.feature_root).as_posix()
        return self._human_ref_update

    def write(self, refs: list[str], *, kind: str = "authoritative_ruling", body: str | None = None) -> None:
        item = {"feedback_id": "f1", "kind": kind, "source_revision": self.reviewed,
                "target_ref": self.TARGET, "body": body or "本轮仅允许人工受理，最终规则待定。",
                "evidence_refs": refs}
        if kind == "authoritative_ruling":
            item["authority"] = {"owner": "需求负责人", "role": "需求负责人"}
            item["decision"] = {"verdict": "amend", "rationale": "按原话限定本轮范围"}
        doc = {"artifact": "blueprint-review-feedback@1", "blueprint_id": self.blueprint_id,
               "component_id": self.component_id, "source_revision": self.reviewed, "items": [item]}
        (self.updates / self.rid / "design-feedback.json").write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def feedback(self) -> dict:
        return self.flow("update", "--action", "feedback")

    def test_the_exported_human_answer_is_a_source(self) -> None:
        ref = self.human_answer()
        self.write([ref])
        out = self.feedback()
        self.assertTrue(out.get("eligible"), out)
        self.assertEqual(["f1"], (out["candidates"] or {}).get("rulings"))
        self.assertIn("update-notes", out["action"], "成功提示没指本轮 notes")

    def test_the_local_annotation_fixed_by_this_round_is_a_source(self) -> None:
        self.write([self.ANNOTATION])
        out = self.feedback()
        self.assertTrue(out.get("eligible"), out)

    def test_an_annotation_that_arrived_after_prepare_is_not_this_round_input(self) -> None:
        late = self.feature_root / "inbox" / "review" / "会后意见.md"
        late.write_text("评审人后来才提的意见。\n", encoding="utf-8")
        self.write(["inbox/review/会后意见.md"])
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("不能代替人的答复", "；".join(out["problems"]), out)

    def test_a_registered_original_is_a_source(self) -> None:
        """材料索引登记的原件有来源身份：正式来源的话可作裁决依据，具体效力由蓝图负责方对原件核定。"""
        self.write(["AR/design.md"])
        out = self.feedback()
        self.assertTrue(out.get("eligible"), out)

    def test_a_mutable_position_resolves_to_its_stable_version(self) -> None:
        """会换版的当前位置（当前阅读稿）落到稳定版本行：引用同一份、摘要核得上才够格。"""
        self.write(["RR/prd.md"])
        out = self.feedback()
        self.assertTrue(out.get("eligible"), out)

    def test_a_person_original_may_be_accompanied_by_technical_evidence(self) -> None:
        draft = self.src / "作者计划.md"
        draft.write_text("# 作者计划\n\n转述。\n", encoding="utf-8")
        self.write([self.human_answer(), "AR/story-src/作者计划.md"])
        out = self.feedback()
        self.assertTrue(out.get("eligible"), out)

    def test_an_opinion_citing_the_persons_words_stays_an_opinion(self) -> None:
        """同一句人的原话可以支撑意见，但意见不被脚本升成授权裁决。"""
        self.write([self.human_answer()], kind="opinion", body="本轮同意，按原话做。")
        out = self.feedback()
        self.assertTrue(out.get("eligible"), out)
        self.assertEqual([], (out["candidates"] or {}).get("rulings") or [])

    def alias_row(self, rel: str = "RR/prd.md") -> dict:
        """材料索引里会换版的当前位置那一行（带 reference 指稳定版本）。"""
        manifest = json.loads((self.src / "materials.json").read_text(encoding="utf-8"))
        return next(r for r in manifest["files"] if r["path"] == rel and r.get("reference"))

    def test_a_moved_stable_original_of_an_alias_is_not_eligible(self) -> None:
        """别名当前字节还在，但它所指的稳定原件被移走：读不到当时那一版，就不给可提交裁决候选。"""
        stable = self.feature_root / self.alias_row()["reference"]["path"]
        self.assertTrue(stable.is_file())
        stable.rename(stable.with_suffix(".unavailable"))
        self.write(["RR/prd.md"])
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("稳定版本", "；".join(out["problems"]), out)
        self.assertIsNone(out["candidates"], "稳定原件缺失仍给出了可提交候选")

    def test_a_changed_stable_original_of_an_alias_is_a_digest_drift(self) -> None:
        stable = self.feature_root / self.alias_row()["reference"]["path"]
        stable.write_bytes(stable.read_bytes() + "稳定原件被改了。\n".encode("utf-8"))
        self.write(["RR/prd.md"])
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("摘要漂移", "；".join(out["problems"]), out)
        self.assertIsNone(out["candidates"], "稳定原件漂移仍给出了可提交候选")

    def test_a_changed_alias_position_is_a_digest_drift(self) -> None:
        alias = self.feature_root / "RR/prd.md"
        alias.write_bytes(alias.read_bytes() + "工作区里被改了一句。\n".encode("utf-8"))
        self.write(["RR/prd.md"])
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("当前位置不一致", "；".join(out["problems"]), out)

    def test_the_alias_record_keeps_the_checked_stable_landing(self) -> None:
        """记录写下这一次核到的稳定落点：别名以后换版，记录仍指得回当时那一份原件。"""
        self.write(["RR/prd.md"])
        out = self.feedback()
        self.assertTrue(out.get("eligible"), out)
        row = self.alias_row()
        place = (json.loads((self.updates / self.rid / "record.json")
                            .read_text(encoding="utf-8"))["design_feedback"]["items"][0]
                 .get("evidence_resolved") or [{}])[0]
        self.assertEqual((row["reference"]["path"], row["reference"]["sha256"]),
                         (place.get("path"), place.get("sha256")), "记录没写稳定落点")
        # 别名随后换成别的版本（这里直接改当前位置字节）：记录里的落点与字节仍是提交时核到的那一份
        alias = self.feature_root / "RR/prd.md"
        alias.write_bytes(alias.read_bytes() + "别名换版。\n".encode("utf-8"))
        self.assertEqual(place["sha256"], hashlib.sha256(
            (self.feature_root / place["path"]).read_bytes()).hexdigest())


class ASystemReviewInputIsCheckedAgainstItsBatchReceipt(
        ARulingSourceIsCheckedAgainstTheRegisterAndThisRound):
    """R2：系统回流的评审输入同时核实际批次回执；prepare 固定的原件与完整 SHA 才是本轮证据。"""

    BATCH = "fetch-s15"
    SYSTEM_INPUT = f"inbox/review/{BATCH}/AR-design.md"

    def before_prepare(self) -> None:
        folder = self.feature_root / "inbox" / "review" / self.BATCH
        folder.mkdir(parents=True, exist_ok=True)
        body = "评审人回流的开发需求正文（系统件）\n".encode("utf-8")
        (folder / "AR-design.md").write_bytes(body)
        sha = hashlib.sha256(body).hexdigest()
        items = [{"name": "AR-design.md", "status": "fetched", "origin": f"{FEATURE}/design.md",
                  "saved": self.SYSTEM_INPUT, "sha256": sha, "digest": f"sha256:{sha[:16]}"}]
        when = "2099-02-02T00:00:00+00:00"
        (folder / ".receipt.json").write_text(json.dumps({"fetchedAt": when, "items": items},
                                                         ensure_ascii=False), encoding="utf-8")
        (self.src / "fetched.json").write_text(json.dumps({
            "fetchedAt": when, "delivery_requirements": {"design_reference": False},
            "review_out": f"inbox/review/{self.BATCH}", "items": items}, ensure_ascii=False),
            encoding="utf-8")

    def before_dir(self) -> Path:
        record = json.loads((self.updates / self.rid / "record.json").read_text(encoding="utf-8"))
        return self.feature_root / record["mirror"]["path"]

    def feedback_record(self) -> dict:
        return json.loads((self.updates / self.rid / "record.json").read_text(encoding="utf-8"))

    def test_the_batch_receipt_backs_the_system_input(self) -> None:
        record = self.feedback_record()
        row = next(e for e in record["review_inputs"] if e["path"] == self.SYSTEM_INPUT)
        self.assertEqual(("fetched", "AR-design.md"), (row["status"], row["system_item"]),
                         "系统评审输入没有按批次回执登记")
        self.write([self.SYSTEM_INPUT])
        out = self.feedback()
        self.assertTrue(out.get("eligible"), out)

    def test_a_changed_system_input_breaks_the_fixed_sha(self) -> None:
        (self.feature_root / self.SYSTEM_INPUT).write_bytes("prepare 之后被换掉的内容\n".encode("utf-8"))
        self.write([self.SYSTEM_INPUT])
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("摘要漂移", "；".join(out["problems"]), out)

    def test_a_missing_before_batch_receipt_blocks_the_system_input(self) -> None:
        """prepare 时固定的批次回执随后被移走：原件字节还在也不能再给可提交候选。"""
        receipt = self.before_dir() / Path(self.SYSTEM_INPUT).parent / ".receipt.json"
        self.assertTrue(receipt.is_file())
        receipt.unlink()
        self.write([self.SYSTEM_INPUT])
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("批次回执", "；".join(out["problems"]), out)
        self.assertIsNone(out["candidates"], "批次回执缺失仍给出了可提交候选")

    def test_a_moved_before_original_blocks_the_system_input(self) -> None:
        """prepare 时固定的原件随后被移走：只见收件箱里的同一字节分不出系统身份。"""
        original = self.before_dir() / Path(self.SYSTEM_INPUT)
        self.assertTrue(original.is_file())
        original.rename(original.with_suffix(".unavailable"))
        self.write([self.SYSTEM_INPUT])
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("找不到与 prepare 固定摘要一致的这一件原件", "；".join(out["problems"]), out)
        self.assertIsNone(out["candidates"], "before 原件缺失仍给出了可提交候选")

    def test_the_checked_before_landing_is_written_into_the_record(self) -> None:
        """反馈记录写下这一次实际核到的稳定落点：本轮 before/ 里的这一份，owner 可按它复查。"""
        self.write([self.SYSTEM_INPUT])
        out = self.feedback()
        self.assertTrue(out.get("eligible"), out)
        record = self.feedback_record()
        item = record["design_feedback"]["items"][0]
        place = (item.get("evidence_resolved") or [{}])[0]
        mirror = record["mirror"]["path"]
        self.assertEqual((self.SYSTEM_INPUT, f"{mirror}/{self.SYSTEM_INPUT}"),
                         (place.get("ref"), place.get("path")), "反馈记录没有给可复查的稳定落点")
        self.assertTrue((self.feature_root / place["path"]).is_file())
        self.assertEqual(place["sha256"], hashlib.sha256(
            (self.feature_root / place["path"]).read_bytes()).hexdigest())


class AnAggregateDraftIsCheckedAgainstItsRegisteredOriginals(
        ARulingSourceIsCheckedAgainstTheRegisterAndThisRound):
    """R2：聚合成当前阅读稿的 component 按**该版本登记的实际原件**核。

    同版登记里还有阅读件这类其它文件；拿其中任一在盘文件通过，会让阅读件代替原件，
    原件被移走或漂移也看不出来。这里用真实导入生成聚合当前阅读稿，再只动 component 的原件。
    """

    DRAFT = "SR/design.md"
    SOURCE = "SR/系统设计.md"

    def setUp(self) -> None:
        super().setUp()
        # 一份本地系统设计经真实导入生成聚合成当前阅读稿的稳定版本与 component
        import_into(self.root, self.feature_root, {self.SOURCE: ("# 系统设计\n\n分工。\n".encode("utf-8"), "SR")})

    def component_and_original(self) -> tuple[str, dict]:
        manifest = json.loads((self.src / "materials.json").read_text(encoding="utf-8"))
        draft = manifest["drafts"][self.DRAFT]["versions"][-1]
        component = draft["components"][0]
        source_id, _, version = component.rpartition("@")
        source = next(s for s in manifest["sources"] if s["source_id"] == source_id)
        original = next(v for v in source["versions"] if str(v["version"]) == version)["original"]
        return component, original

    def test_a_component_whose_registered_original_is_gone_does_not_qualify(self) -> None:
        self.write([self.DRAFT])
        first = self.feedback()
        self.assertTrue(first.get("eligible"), first)
        component, original = self.component_and_original()
        self.assertEqual("local:SR/系统设计.md@1", component)
        path = self.feature_root / original["path"]
        self.assertTrue(path.is_file())
        path.rename(path.with_suffix(".unavailable"))
        # 同版阅读件还在盘上：旧实现会拿它代签这一版的原件
        manifest = json.loads((self.src / "materials.json").read_text(encoding="utf-8"))
        still = [r for r in manifest["files"]
                 if r.get("source_id") == "local:SR/系统设计.md" and r["path"] != original["path"]]
        self.assertTrue(still, "夹具里没有同版其它文件，测不出代签")
        self.write([self.DRAFT], body="聚合稿出处补一句新说明")
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("追不到该版本登记的原件", "；".join(out["problems"]), out)
        self.assertIsNone(out["candidates"], "component 原件缺失仍给出了可提交候选")

    def test_a_component_original_drift_is_not_hidden_by_another_same_version_file(self) -> None:
        self.write([self.DRAFT])
        self.assertTrue(self.feedback().get("eligible"))
        _, original = self.component_and_original()
        path = self.feature_root / original["path"]
        path.write_bytes(path.read_bytes() + "原件被改。\n".encode("utf-8"))
        self.write([self.DRAFT], body="聚合稿出处再补一句")
        out = self.feedback()
        self.assertFalse(out.get("eligible"), out)
        self.assertIn("追不到该版本登记的原件", "；".join(out["problems"]), out)


class AClaimedExternalVersionBecomesTheReleaseBaseline(RegisteredCase):
    """最近一次非撤回的 documents 轮已按当前 Story 承接的外部版本成为逐件发布基线：
    同一外部变化不再需要 `--reply`，承接之后又被改仍冲突；未完成、materials-only、更晚恢复都不放进基线。
    承接记录、before 原件与回执、投影登记都由真实 `update prepare/close` 产生，不手写产品基线字段。"""

    NAMES = PublishChecksTheExternalVersion.NAMES
    DESIGN_REQUIRED = True
    GATE = (True, {"ok": True, "notes": [], "problems": []})
    digest = staticmethod(PublishChecksTheExternalVersion.digest)
    call = PublishChecksTheExternalVersion.call
    local = PublishChecksTheExternalVersion.local
    system_body = PublishChecksTheExternalVersion.system_body
    publish = PublishChecksTheExternalVersion.publish
    actions = PublishChecksTheExternalVersion.actions
    contract = PublishChecksTheExternalVersion.contract
    receipt = PublishChecksTheExternalVersion.receipt
    readback = PublishChecksTheExternalVersion.readback
    overwrite_the_system_body = PublishChecksTheExternalVersion.overwrite_the_system_body
    BUILD = StoryIsRegisteredAgainAfterChanges.BUILD
    run_cmd = StoryIsRegisteredAgainAfterChanges.run_cmd
    register = StoryIsRegisteredAgainAfterChanges.register

    def setUp(self) -> None:
        super().setUp()
        self.overwrite_the_system_body()          # 一次真实归档：发布记录与覆盖前备份都由产品命令写下
        # 归档是更早发生的外部事件：把它的时刻放在本轮收口之前，免得同一秒内比先后
        contract = self.contract()
        contract["archived"]["at"] = "2000-01-01T00:00:00+00:00"
        (self.src / "story-flow.json").write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")

    def deliver(self, external: bytes, *, design: bytes | None = None,
                when: str = "2099-02-02T00:00:00+00:00", batch: str = "fetch-review") -> str:
        """外部服务的替身：把评审人在线上改过的正文/附件取回到 one 评审批次并写现状回执。

        这只是外部输入；本轮记录、before 快照与承接关系都由真实 prepare/close 产生。
        """
        folder = self.feature_root / "inbox" / "review" / batch
        folder.mkdir(parents=True, exist_ok=True)
        items = []

        def put(name: str, body: bytes) -> None:
            (folder / name).write_bytes(body)
            sha = hashlib.sha256(body).hexdigest()
            items.append({"name": name, "status": "fetched", "origin": f"{FEATURE}/{'attachments/' if name != 'AR-design.md' else ''}"
                          + ("design-review.md" if name != "AR-design.md" else "design.md"),
                          "saved": f"inbox/review/{batch}/{name}", "digest": self.digest(body), "sha256": sha})

        put("AR-design.md", external)
        if design is not None:
            put("design-review.md", design)
        (folder / ".receipt.json").write_text(json.dumps({"fetchedAt": when, "items": items}, ensure_ascii=False),
                                              encoding="utf-8")
        (self.src / "fetched.json").write_text(json.dumps({
            "fetchedAt": when, "delivery_requirements": {"design_reference": design is not None},
            "review_out": f"inbox/review/{batch}", "items": items}, ensure_ascii=False), encoding="utf-8")
        return folder.name

    def process(self, external: bytes, *, design: bytes | None = None,
                when: str = "2099-02-02T00:00:00+00:00", result: str = "documents",
                close: bool = True, batch: str = "fetch-review") -> dict:
        """一轮真实的 update：取材 → 输入关卡 → prepare → 说明 → 收口；返回 close 结果或开着的轮次记录。"""
        self.deliver(external, design=design, when=when, batch=batch)
        self.assertEqual("inputs", self.flow("update", "--action", "inputs")["stage"])
        write_gaps(self.src)
        self.assertEqual("accepted", answer(self.flow, "material_scope", "2")["outcome"])
        out = self.flow("update", "--action", "prepare", "--result", result)
        rid = out["update"]
        (self.updates / rid / "update-notes.md").write_text(NOTES, encoding="utf-8")
        if not close:
            return {"update": rid, "record": json.loads((self.updates / rid / "record.json").read_text(encoding="utf-8"))}
        if result == "documents":
            # 本轮的输入与原话改变了成文依据：按当前材料重新定稿、审查并登记，收口核的才是当前这一版
            self.assertTrue(self.register().get("success"), self.outputs[-1])
        closed = self.flow("update", "--action", "close")
        self.assertEqual("closed", closed.get("status"), closed)
        return closed

    def test_a_close_without_this_round_registration_stays_open(self) -> None:
        """本轮没有成文登记记下的承接键：close 不补发承接资格，保持 open 且仍按原发布基线比较。"""
        external = "开轮已取回、但本轮没有登记的正文\n".encode("utf-8")
        self.deliver(external)
        self.assertEqual("inputs", self.flow("update", "--action", "inputs")["stage"])
        write_gaps(self.src)
        answer(self.flow, "material_scope", "2")
        rid = self.flow("update", "--action", "prepare", "--result", "documents")["update"]
        (self.updates / rid / "update-notes.md").write_text(NOTES, encoding="utf-8")
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        # 本轮登记其实发生过；抹掉它记下的承接键，等价于收口前没有任何本轮登记
        path = self.updates / rid / "record.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record.pop("registered_material_key", None)
        record.pop("registered_review", None)
        path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        out = self.flow("update", "--action", "close")
        self.assertFalse(out.get("success", True), out)
        self.assertIn("这份评审输入还没随当前 Story 登记", out.get("error", ""))
        record = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual("open", record["status"], "缺登记却收口了")
        self.assertNotIn("registered_material_key", record, "close 补发了承接资格")
        self.receipt(external)
        self.assertFalse(self.publish()["publishable"], "缺登记的轮次被当成已承接基线")

    def test_notes_changed_after_registration_needs_registering_again(self) -> None:
        """登记之后改 notes 会换掉当前报告键：即使已有新报告，也必须重新运行 story 登记才能收口。"""
        external = "本轮已承接的正文\n".encode("utf-8")
        self.deliver(external)
        self.assertEqual("inputs", self.flow("update", "--action", "inputs")["stage"])
        write_gaps(self.src)
        answer(self.flow, "material_scope", "2")
        rid = self.flow("update", "--action", "prepare", "--result", "documents")["update"]
        notes = self.updates / rid / "update-notes.md"
        notes.write_text(NOTES, encoding="utf-8")
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        notes.write_text(NOTES + "\n## 补记\n\n登记之后又补的一句判断。\n", encoding="utf-8")
        out = self.flow("update", "--action", "close")
        self.assertFalse(out.get("success", True), out)
        self.assertIn("这份评审输入还没随当前 Story 登记", out.get("error", ""))
        self.assertIn("story 登记", out.get("error", ""), "没有指出要重新登记")
        self.assertEqual("open", json.loads((self.updates / rid / "record.json").read_text(encoding="utf-8"))["status"])

    def test_a_processed_external_change_needs_no_reply(self) -> None:
        external = "评审人在系统上改过、本轮 update 已按 Story 承接的正文\n".encode("utf-8")
        closed = self.process(external)
        self.assertEqual(external, (self.feature_root / closed["review_inputs"][0]["path"]).read_bytes(),
                         "收口记录的评审输入不是 prepare 固定的那一份")
        self.receipt(external, attachments={"design-review.md": self.local("design-review.md")})
        out = self.publish()
        self.assertTrue(out["publishable"], out)
        self.assertEqual("write", self.actions(out)["AR-design.md"])
        self.assertIn(closed["update"], [r.get("baseline_source") for r in out["items"] if r["item"] == "AR-design.md"][0])

    def test_an_external_change_after_the_claim_still_conflicts(self) -> None:
        self.process("承接的那一版\n".encode("utf-8"))
        self.receipt("承接之后又被改了一版\n".encode("utf-8"))
        out = self.publish()
        self.assertFalse(out["publishable"], out)
        self.assertEqual("conflict", self.actions(out)["AR-design.md"])

    def test_a_late_revision_is_not_carried_by_the_closed_round(self) -> None:
        """prepare 之后、收口之前又改过的稿不属于本轮：收口不列它，发布仍要求处理。"""
        external = "本轮已承接的那一版\n".encode("utf-8")
        late = "收口前晚到的另一版\n".encode("utf-8")
        self.deliver(external, when="2099-02-02T00:00:00+00:00")
        self.assertEqual("inputs", self.flow("update", "--action", "inputs")["stage"])
        write_gaps(self.src)
        answer(self.flow, "material_scope", "2")
        rid = self.flow("update", "--action", "prepare", "--result", "documents")["update"]
        self.deliver(late, when="2099-02-03T00:00:00+00:00", batch="fetch-late")
        (self.updates / rid / "update-notes.md").write_text(NOTES, encoding="utf-8")
        self.assertTrue(self.register().get("success"), self.outputs[-1])
        closed = self.flow("update", "--action", "close")
        self.assertEqual("closed", closed.get("status"), closed)
        self.assertEqual([external], [(self.feature_root / e["path"]).read_bytes() for e in closed["review_inputs"]],
                         "收口把晚到件补列成本轮已承接")
        self.assertEqual(1, len(closed["review_inputs_not_carried"]), closed)
        self.receipt(late)
        out = self.publish()
        self.assertFalse(out["publishable"], "晚到的外部稿被当成已处理")
        self.assertEqual("conflict", self.actions(out)["AR-design.md"])

    def test_the_same_revision_after_the_claim_needs_no_reply_again(self) -> None:
        external = "已承接且之后没再变\n".encode("utf-8")
        self.process(external)
        self.process(external, when="2099-02-05T00:00:00+00:00", batch="fetch-same")
        self.receipt(external, attachments={"design-review.md": self.local("design-review.md")})
        out = self.publish()
        self.assertTrue(out["publishable"], out)
        self.assertEqual("write", self.actions(out)["AR-design.md"])

    def test_an_unclosed_round_is_not_a_baseline(self) -> None:
        external = "外部改过、但这一轮没有收口\n".encode("utf-8")
        self.process(external, close=False)
        self.receipt(external)
        self.assertFalse(self.publish()["publishable"], "未收口的轮次被当成已承接基线")

    def test_a_materials_only_round_is_not_a_baseline(self) -> None:
        external = "外部改过、但这一轮只取材\n".encode("utf-8")
        self.process(external, result="materials")
        self.receipt(external)
        self.assertFalse(self.publish()["publishable"], "只取材的轮次被当成已承接基线")

    def test_a_restored_round_is_not_a_baseline(self) -> None:
        external = "外部改过、但这一轮被撤回\n".encode("utf-8")
        self.deliver(external)
        self.assertEqual("inputs", self.flow("update", "--action", "inputs")["stage"])
        write_gaps(self.src)
        answer(self.flow, "material_scope", "2")
        self.flow("update", "--action", "prepare", "--result", "documents")
        self.assertEqual("restored", self.flow("update", "--action", "restore").get("status"))
        self.receipt(external)
        self.assertFalse(self.publish()["publishable"], "撤回的轮次被当成已承接基线")

    def test_a_later_remote_restore_invalidates_the_claim(self) -> None:
        self.process("承接的那一版\n".encode("utf-8"))
        contract = self.contract()
        contract["archived"]["restored_at"] = "2099-03-01T00:00:00+00:00"
        (self.src / "story-flow.json").write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
        self.receipt("承接的那一版\n".encode("utf-8"))
        self.assertFalse(self.publish()["publishable"], "更晚的远端恢复之后，旧承接轮不能当基线")

    def test_a_processed_design_attachment_becomes_its_own_baseline(self) -> None:
        external = "本轮已承接的正文\n".encode("utf-8")
        design = "系统上这一轮已承接的设计参考\n".encode("utf-8")
        closed = self.process(external, design=design)
        entry = next(e for e in closed["review_inputs"] if e["system_item"] == "design-review.md")
        self.assertIn("projection", entry, "承接的设计附件没有随成文登记只读投影摘要")
        self.receipt(external, attachments={"design-review.md": design})
        out = self.publish()
        self.assertTrue(out["publishable"], out)
        self.assertEqual({"AR-design.md": "write", "design-review.md": "write"}, self.actions(out))

    def test_a_changed_projection_after_the_claim_blocks_the_attachment(self) -> None:
        external = "本轮已承接的正文\n".encode("utf-8")
        design = "系统上这一轮已承接的设计参考\n".encode("utf-8")
        self.process(external, design=design)
        projection = self.feature_root / "blueprint" / "component-blueprint.review.md"
        projection.write_bytes(projection.read_bytes() + b"\n<!-- \xe6\x9c\xac\xe5\x9c\xb0\xe6\x94\xb9\xe4\xba\x86 -->\n")
        self.receipt(external, attachments={"design-review.md": design})
        out = self.publish()
        self.assertEqual("conflict", self.actions(out)["design-review.md"],
                         "当前投影不是登记的那一份却仍按承接基线放行")

    def test_the_body_and_the_design_attachment_are_claimed_per_item(self) -> None:
        external = "外部的正文这一轮已承接\n".encode("utf-8")
        self.process(external)                     # 只承接了正文，设计参考没有
        other = "系统上另一份设计参考\n".encode("utf-8")
        self.receipt(external, attachments={"design-review.md": other})
        out = self.publish()
        self.assertFalse(out["publishable"], out)
        actions = self.actions(out)
        self.assertEqual("write", actions["AR-design.md"])
        self.assertEqual("conflict", actions["design-review.md"], "正文处理了不能顺带放行未处理的设计附件")


#: 审查对象与材料键的机器事实：与 prepare/check 内部同一组函数（reviewObject/withTaskRow/materialKey）。
#: 逐文件 SHA 一并取出，收口前后比的是完整对象，不只看材料键。
REVIEW_OBJECT_FACTS = """
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import { pathToFileURL } from 'node:url';
const [mod, root, feature] = process.argv.slice(1);
const m = await import(pathToFileURL(mod).href);
const base = m.reviewObject(root, feature, { withTask: false });
const full = m.withTaskRow(root, feature, base);
const sha = rel => crypto.createHash('sha256').update(fs.readFileSync(`${root}/${rel}`)).digest('hex');
process.stdout.write(JSON.stringify({ rows: full.rows.map(row => ({ ...row, sha256: sha(row.path) })),
  problems: full.problems, comparison: full.comparison,
  key: full.problems.length ? null : m.materialKey(root, full.rows) }));
"""

#: 阶段审查（Plan 的必审输入）与 Story 读者取同一份比较依据结论：缺口按同一组函数 `reviewInputs` 取，
#: 评审输入的实际路径也取出，核 Story 对象与阶段必审取的是同一件。
REVIEW_INPUT_FACTS = """
import { pathToFileURL } from 'node:url';
const [mod, root, feature, purpose] = process.argv.slice(1);
const m = await import(pathToFileURL(mod).href);
const r = m.reviewInputs(root, feature, purpose);
process.stdout.write(JSON.stringify({ update: r.update, gaps: r.gaps, inputs: r.inputs.map(x => x.path) }));
"""


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReviewLifecycleCase(RegisteredCase):
    """已登记工程上的一次真实 update 审查：开轮、改稿、准备审查、读者报告、接收、登记、收口都走实际入口。"""

    def rewrite(self, text: str) -> None:
        """经 `chapter` 提交改一章正文：被审的是盘上实际这一份，不是手写 Story 的替换。"""
        body = self.root / "chapter.md"
        body.write_text(text + "\n", encoding="utf-8")
        proc = self.run_cmd("node", str(self.BUILD), "chapter", "--feature", FEATURE,
                            "--project-root", str(self.root), "--chapter", "背景", "--from", str(body))
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def review_prepare(self) -> dict:
        proc = self.run_cmd("node", str(self.BUILD), "review", "--action", "prepare", "--reader", "task",
                            "--feature", FEATURE, "--project-root", str(self.root))
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads([line for line in proc.stdout.splitlines() if line.startswith("{")][-1])

    def review_check(self) -> dict:
        proc = self.run_cmd("node", str(self.BUILD), "review", "--action", "check",
                            "--feature", FEATURE, "--project-root", str(self.root))
        return json.loads([line for line in proc.stdout.splitlines() if line.startswith("{")][-1])

    def review_prepare_proc(self) -> subprocess.CompletedProcess:
        """不替作者断言成功的 prepare：比较依据残缺时它必须停下，不派出新材料键。"""
        return self.run_cmd("node", str(self.BUILD), "review", "--action", "prepare", "--reader", "task",
                            "--feature", FEATURE, "--project-root", str(self.root))

    def input_gaps(self) -> dict:
        """阶段审查这一侧对同一份比较依据的结论（`reviewInputs` 的 gaps 与本轮 update）。"""
        mod = DEV_EXT / "hooks" / "shared" / "review-inputs.mjs"
        proc = subprocess.run(["node", "--input-type=module", "-e", REVIEW_INPUT_FACTS,
                               str(mod), str(self.root), FEATURE, "plan"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(0, proc.returncode, proc.stderr[-800:])
        return json.loads(proc.stdout)

    def object_facts(self) -> dict:
        mod = DEV_EXT / "skills" / "story" / "scripts" / "core" / "story" / "review-object.mjs"
        proc = subprocess.run(["node", "--input-type=module", "-e", REVIEW_OBJECT_FACTS,
                               str(mod), str(self.root), FEATURE],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr[-800:])
        return json.loads(proc.stdout)

    def local_review_input(self, text: str) -> str:
        """本机放进评审用途区的一份意见：prepare 把它固定进本轮 before/ 与 review_inputs。"""
        path = self.feature_root / "inbox" / "review" / "本地意见.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path.relative_to(self.feature_root).as_posix()

    def open_round(self, change: str | None = None) -> tuple[str, dict]:
        """开这一轮、写说明、准备审查、读者交报告、再准备接收；返回轮次与第一次准备的结果。"""
        rid = self.update()["update"]
        if change:
            self.rewrite(change)
        (self.updates / rid / "update-notes.md").write_text(NOTES, encoding="utf-8")
        first = self.review_prepare()
        self.assertFalse(first["reused"], first)
        design_kit.write_review(self.root, FEATURE, "pass")
        received = self.review_prepare()
        self.assertEqual((first["material_key"], first["report_file"]),
                         (received["material_key"], received["report_file"]), received)
        self.assertIn("last_received", json.loads((self.src / "review" / "prepared.json").read_text(encoding="utf-8")))
        return rid, first

    def register_round(self) -> dict:
        """本轮改动按当前内容重新独立审查后登记；登记本身核过可消费的审查结果。"""
        out = StoryIsRegisteredAgainAfterChanges.register(self)
        self.assertTrue(out.get("success"), self.outputs[-1])
        return out

    def review_snapshot(self) -> dict:
        """收口前后要比的全部审查事实：逐文件 SHA 的对象行、任务与载体字节、报告位置与复用、人答版本。"""
        prepared = json.loads((self.src / "review" / "prepared.json").read_text(encoding="utf-8"))
        report_dir = self.root / prepared["report_dir"]
        return {
            "object": self.object_facts(),
            "task": file_digest(self.src / "review" / "task.md"),
            "dispatch": file_digest(self.src / "review" / "dispatch.md"),
            "prepared": {key: prepared.get(key)
                         for key in ("material_key", "report_dir", "report_file", "reused", "last_received")},
            "reports": sorted(path.name for path in report_dir.glob("*")),
            "answers": [[path.name, file_digest(path)] for path in sorted((self.src / "answers").glob("*"))],
        }


class AReviewSurvivesTheClose(ReviewLifecycleCase):
    """收口只改轮次状态与完成点：审过的那一版对象、任务、材料键与已接收的报告原样留下，不再派审一次。"""

    def test_a_reviewed_round_keeps_the_same_object_task_key_and_report(self) -> None:
        rel = self.local_review_input("评审人本地意见：回执状态要以服务端为准。\n")
        rid, first = self.open_round("支付提交后用户要能看到回执状态，以服务端为准。")
        # 本轮固定的评审输入原件在打开时就进了对象与记录：对象读的是 before/ 快照，不是当前收件箱
        entered = [row["path"] for row in self.object_facts()["rows"]]
        fixed = f"AR/story-src/updates/{rid}/before/{rel}"
        self.assertIn(f"doc/features/{FEATURE}/{fixed}", entered, "评审输入原件没进审查对象")
        self.assertNotIn(f"doc/features/{FEATURE}/{rel}", entered, "对象还在读当前收件箱里的同名件")
        self.assertIn(rel, [entry["path"] for entry in json.loads(
            (self.updates / rid / "record.json").read_text(encoding="utf-8"))["review_inputs"]])
        self.register_round()
        before = self.review_snapshot()
        closed = self.update("--action", "close")
        self.assertEqual("closed", closed.get("status"), closed)
        self.assertEqual(rid, closed["update"])
        after = self.review_snapshot()
        self.assertEqual(before, after, "收口改了审查对象、任务、材料键或已接收的报告")
        self.assertIn(f"doc/features/{FEATURE}/{fixed}", [row["path"] for row in after["object"]["rows"]],
                      "收口把本轮固定的评审输入原件移出了同一审查上下文")
        self.assertIn(rel, [entry["path"] for entry in json.loads(
            (self.updates / rid / "record.json").read_text(encoding="utf-8"))["review_inputs"]],
            "收口改写了本轮固定的评审输入原件")
        # 同报告可复用：check 仍是对这一份的通过结论，prepare 直接复用、不增加独审轮
        checked = self.review_check()
        self.assertEqual(("pass", first["material_key"]),
                         (checked.get("result"), checked.get("material_key")), checked)
        again = self.review_prepare()
        self.assertTrue(again["reused"], again)
        self.assertEqual((first["material_key"], first["report_file"]),
                         (again["material_key"], again["report_file"]), again)
        self.assertEqual(before["reports"], self.review_snapshot()["reports"], "收口后的 prepare 另派了一轮")

    def test_a_round_that_changed_no_material_only_closed_is_not_stale(self) -> None:
        """材料与 Story 都没动，只开一轮并收口：比较依据仍在对象里，已审的报告不因 close 失效。"""
        rid, first = self.open_round()
        self.register_round()
        self.assertEqual("closed", self.update("--action", "close").get("status"))
        self.assertEqual(first["material_key"], self.object_facts()["key"])
        self.assertEqual("pass", self.review_check().get("result"))


class ARealChangeRefreshesTheReviewBasis(ReviewLifecycleCase):
    """真实依据变了（Story、人答、蓝图）或新开一轮：旧审查按 subject_stale 失效，不拿旧报告顶新对象。"""

    def test_changing_the_story_after_the_close_is_stale(self) -> None:
        _, first = self.open_round("支付提交后用户要能看到回执状态。")
        self.register_round()
        self.assertEqual("closed", self.update("--action", "close").get("status"))
        self.rewrite("退款到账后用户能看到余额已更新。")
        self.assertNotEqual(first["material_key"], self.object_facts()["key"])
        self.assertEqual("subject_stale", self.review_check().get("result"))

    def test_a_new_human_answer_changes_the_review_subject(self) -> None:
        rid = self.update()["update"]
        (self.updates / rid / "update-notes.md").write_text(NOTES, encoding="utf-8")
        first = self.review_prepare()
        ask = self.ask_questions(self.business_question("D1", "回执状态以谁为准？", ["以服务端为准", "以本地缓存为准"]))
        self.assertTrue(self.answer_question(ask, "D1", "以服务端回执为准").get("success"))
        self.assertNotEqual(first["material_key"], self.object_facts()["key"])
        self.assertEqual("subject_stale", self.review_check().get("result"))

    def test_a_changed_blueprint_is_a_new_review_subject(self) -> None:
        rid = self.update()["update"]
        (self.updates / rid / "update-notes.md").write_text(NOTES, encoding="utf-8")
        first = self.review_prepare()
        canonical = self.feature_root / "blueprint" / "component-blueprint.yaml"
        canonical.write_bytes(canonical.read_bytes() + "\n# 设计依据这一版改了。\n".encode("utf-8"))
        self.assertNotEqual(first["material_key"], self.object_facts()["key"])
        self.assertEqual("subject_stale", self.review_check().get("result"))

    def test_a_new_round_gets_a_new_comparison_basis(self) -> None:
        rid1, first = self.open_round("支付提交后用户要能看到回执状态。")
        self.register_round()
        self.assertEqual("closed", self.update("--action", "close").get("status"))
        rid2 = self.update()["update"]
        facts = self.object_facts()
        self.assertNotEqual(rid1, rid2)
        self.assertEqual(rid2, facts["comparison"]["rid"])
        self.assertNotEqual(first["material_key"], facts["key"], "新开一轮还是旧审查对象")
        self.assertEqual("subject_stale", self.review_check().get("result"))


class WithdrawingARoundKeepsTheOriginalsAndThePreviousBasis(ReviewLifecycleCase):
    """撤回只退可改件：人的原件与这一轮的 before/ 不动，比较依据回到仍有效的上一轮。"""

    def test_restore_returns_to_the_previous_review_basis_and_keeps_the_originals(self) -> None:
        rid1, first = self.open_round("支付提交后用户要能看到回执状态。")
        self.register_round()
        self.assertEqual("closed", self.update("--action", "close").get("status"))
        registered_story = file_digest(self.feature_root / "AR" / "story.md")
        rid2 = self.update()["update"]
        self.rewrite("退回前又改的一版。")
        (self.updates / rid2 / "update-notes.md").write_text(NOTES, encoding="utf-8")
        second = self.review_prepare()
        self.assertNotEqual(first["material_key"], second["material_key"])
        before = self.updates / rid2 / "before"
        kept = {path.relative_to(before).as_posix(): file_digest(path)
                for path in before.rglob("*") if path.is_file()}
        out = self.update("--action", "restore")
        self.assertEqual("restore_conflicted", out["status"], out)
        for conflict in out["conflicts"]:
            if conflict.get("before"):
                (self.feature_root / conflict["file"]).write_bytes(
                    (self.feature_root / conflict["before"]).read_bytes())
            else:
                (self.feature_root / conflict["file"]).unlink()
        out = self.update("--action", "restore")
        self.assertEqual(("restored", []), (out["status"], out["conflicts"]), out)
        self.assertEqual({"open": None, "last_restored": rid2, "last_closed": rid1},
                         json.loads((self.src / "story-flow.json").read_text(encoding="utf-8"))["update"],
                         "撤回后没把仍有效的上一轮留作比较依据")
        # 重新准备：任务按撤回后的比较依据（上一轮）重生成，材料键回到那一轮审过的那一版
        again = self.review_prepare()
        self.assertEqual(first["material_key"], again["material_key"], "恢复后的审查对象不是上一轮审过的那一版")
        facts = self.object_facts()
        self.assertEqual(rid1, facts["comparison"]["rid"], "撤回后比较依据不是仍有效的上一轮")
        self.assertEqual(first["material_key"], facts["key"], "恢复后的 Story 与当前比较依据不是同一版")
        self.assertEqual(registered_story, file_digest(self.feature_root / "AR" / "story.md"))
        now = {path.relative_to(before).as_posix(): file_digest(path)
               for path in before.rglob("*") if path.is_file()}
        self.assertEqual(kept, now, "撤回动了这一轮 before/ 里的原件")


class ABrokenComparisonBasisIsReported(ReviewLifecycleCase):
    """缺 before/ 或轮次记录坏了：沿既有 input_invalid 报位置，不吞成「没有 update」或「报告没到」。"""

    def test_a_missing_before_directory_is_input_invalid(self) -> None:
        rid, _ = self.open_round()
        self.register_round()
        self.assertEqual("closed", self.update("--action", "close").get("status"))
        before = self.updates / rid / "before"
        before.rename(self.updates / rid / "before.saved")
        out = self.review_check()
        self.assertEqual("input_invalid", out.get("result"), out)
        self.assertIn(f"updates/{rid}/before", out.get("detail", ""))
        self.assertIn("比较基准", out.get("detail", ""))

    def test_a_broken_round_record_is_input_invalid_not_no_update(self) -> None:
        rid, _ = self.open_round()
        self.register_round()
        self.assertEqual("closed", self.update("--action", "close").get("status"))
        (self.updates / rid / "record.json").write_text("{ 坏了", encoding="utf-8")
        out = self.review_check()
        self.assertEqual("input_invalid", out.get("result"), out)
        self.assertIn("record.json", out.get("detail", ""))
        self.assertIn(rid, out.get("detail", ""))


class AFixedBeforeOriginalIsCheckedNotInferred(ReviewLifecycleCase):
    """R3（S18）：比较依据取这一轮 record 固定下来的清单与摘要，逐件核 before/ 里的实际文件；不按目录非空判存在。

    「当前 Story 合法修改」照常派新审；固定 before 的一件丢失或字节改变、已收口轮的 update-notes 丢失时，
    prepare 停在残缺集上、check 沿 input_invalid 报位置与恢复来源；恢复同一份字节后对象回到原样、已接收的报告仍可消费。
    还开着的一轮可以还没写 update-notes，那不是缺件。
    """

    def fixed(self, rid: str) -> dict:
        return dict(json.loads((self.updates / rid / "record.json").read_text(encoding="utf-8"))["owned_before"])

    def closed_round(self, change: str = "支付提交后用户要能看到回执状态，以服务端为准。") -> str:
        rid, _ = self.open_round(change)
        self.register_round()
        self.assertEqual("closed", self.update("--action", "close").get("status"))
        return rid

    def before_original(self, rid: str, rel: str = "AR/story.md") -> Path:
        return self.updates / rid / "before" / Path(rel)

    def test_a_lost_fixed_original_holds_the_new_review_until_restored(self) -> None:
        rid = self.closed_round()
        self.assertIn("AR/story.md", self.fixed(rid), "这一轮 record 没固定动手前的 Story")
        before = self.review_prepare()
        self.assertTrue(before["reused"], before)
        path = self.before_original(rid)
        kept = path.read_bytes()
        rel = path.relative_to(self.feature_root).as_posix()
        path.unlink()
        out = self.review_check()
        self.assertEqual("input_invalid", out.get("result"), out)
        for needle in (rel, rid, "恢复"):
            self.assertIn(needle, out.get("detail", ""), out)
        proc = self.review_prepare_proc()
        self.assertNotEqual(0, proc.returncode, "固定 before 缺了一件仍派出了新审")
        self.assertIn(rel, proc.stdout + proc.stderr)
        # 恢复同一份字节：对象与任务回到原样，已接收的报告仍可消费，不另派一轮
        path.write_bytes(kept)
        again = self.review_prepare()
        self.assertTrue(again["reused"], again)
        self.assertEqual(before["material_key"], self.object_facts()["key"])
        self.assertEqual("pass", self.review_check().get("result"))

    def test_a_changed_before_original_is_not_a_usable_basis(self) -> None:
        rid = self.closed_round()
        before = self.review_prepare()
        path = self.before_original(rid)
        kept = path.read_bytes()
        rel = path.relative_to(self.feature_root).as_posix()
        path.write_bytes(kept + "\n审查之后又改的一句话。\n".encode("utf-8"))
        out = self.review_check()
        self.assertEqual("input_invalid", out.get("result"), out)
        self.assertIn(rel, out.get("detail", ""))
        self.assertIn("字节", out.get("detail", ""))
        self.assertNotEqual(0, self.review_prepare_proc().returncode, "动手前那一版被改过仍派了新审")
        path.write_bytes(kept)
        self.assertTrue(self.review_prepare()["reused"])
        self.assertEqual("pass", self.review_check().get("result"))

    def test_lost_closed_notes_are_reported_not_silently_dropped(self) -> None:
        rid = self.closed_round()
        before = self.review_prepare()
        notes = self.updates / rid / "update-notes.md"
        kept = notes.read_text(encoding="utf-8")
        notes.unlink()
        out = self.review_check()
        self.assertEqual("input_invalid", out.get("result"), out)
        self.assertIn(f"updates/{rid}/update-notes.md", out.get("detail", ""))
        self.assertIn("已收口", out.get("detail", ""))
        self.assertNotEqual(0, self.review_prepare_proc().returncode, "已收口轮的 notes 丢了仍派了新审")
        notes.write_text(kept, encoding="utf-8")
        again = self.review_prepare()
        self.assertTrue(again["reused"], again)
        self.assertEqual(before["material_key"], self.object_facts()["key"])
        self.assertEqual("pass", self.review_check().get("result"))

    def test_an_open_round_may_not_have_the_notes_yet(self) -> None:
        """还开着的一轮可以还没写 update-notes：它不是缺件；写完就是作者的判断，审查对象跟着换。"""
        rid = self.update()["update"]
        facts = self.object_facts()
        self.assertEqual([], facts["problems"], facts["problems"])
        self.assertNotIn(f"doc/features/{FEATURE}/AR/story-src/updates/{rid}/update-notes.md",
                         [row["path"] for row in facts["rows"]], "还没写的 notes 被列进了对象")
        first = self.review_prepare()
        self.assertTrue(first["material_key"], first)
        (self.updates / rid / "update-notes.md").write_text(NOTES, encoding="utf-8")
        self.assertNotEqual(first["material_key"], self.object_facts()["key"], "作者的判断没进审查对象")
        self.assertEqual("subject_stale", self.review_check().get("result"))

    def test_a_legit_story_edit_is_a_new_review_not_a_broken_basis(self) -> None:
        self.closed_round()
        first = self.review_prepare()
        self.assertTrue(first["reused"], first)
        self.rewrite("回执状态以服务端为准，本地只做展示。")
        facts = self.object_facts()
        self.assertEqual([], facts["problems"], "合法改稿被当成了固定依据损坏")
        self.assertNotEqual(first["material_key"], facts["key"])
        self.assertEqual("subject_stale", self.review_check().get("result"))
        self.assertFalse(self.review_prepare()["reused"], "改过稿仍复用了旧报告")

    def test_an_external_review_input_is_pinned_to_the_rounds_before_copy(self) -> None:
        """R3（S20）：同轮外部评审输入按 before/ 固定件送审，Story 任务与阶段读者用同一件。

        第一版固定 → 第二版到达当前收件箱 → 固定件移走 → 恢复：核实际任务列的路径与字节、check、prepare、
        阶段必审输入，以及失败时旧载体（task／dispatch／prepared）的字节。
        """
        rel = self.local_review_input("第一版意见：回执以服务端为准。\n")
        rid, first = self.open_round("支付提交后用户要能看到回执状态，以服务端为准。")
        fixed = self.updates / rid / "before" / rel
        fixed_rel = f"doc/features/{FEATURE}/AR/story-src/updates/{rid}/before/{rel}"
        first_bytes = fixed.read_bytes()
        row = next(r for r in self.object_facts()["rows"] if r["path"].endswith(rel))
        self.assertEqual(fixed_rel, row["path"], "对象没有指向本轮固定的 before 件")
        self.assertEqual(file_digest(fixed), row["sha256"], "对象读到的不是第一版字节")
        stage = self.input_gaps()
        self.assertIn(fixed_rel, stage["inputs"], "阶段必审输入没有取同一件固定件")
        self.assertEqual([], [gap for gap in stage["gaps"] if rel in gap], stage["gaps"])
        # 第二版到达当前收件箱：本轮的固定件与对象不动，prepare 复用；新版本归下一次 update
        (self.feature_root / rel).write_text("第二版，与本轮授权相反。\n", encoding="utf-8")
        again = self.review_prepare()
        self.assertTrue(again["reused"], again)
        self.assertEqual((first["material_key"], first["report_file"]),
                         (again["material_key"], again["report_file"]), "收件箱第二版换了这一轮的审查对象")
        self.assertEqual(first_bytes, fixed.read_bytes(), "当前收件箱的第二版改写了本轮固定件")
        # 固定件移走：prepare 失败、check 按轮次报恢复，旧载体一字不改
        task = self.src / "review" / "task.md"
        dispatch = self.src / "review" / "dispatch.md"
        prepared = self.src / "review" / "prepared.json"
        carriers = {path: path.read_bytes() for path in (task, dispatch, prepared)}
        fixed.unlink()
        out = self.review_check()
        self.assertEqual("input_invalid", out.get("result"), out)
        for needle in (f"updates/{rid}/before/{rel}", rid, "恢复"):
            self.assertIn(needle, out.get("detail", ""), out)
        proc = self.review_prepare_proc()
        self.assertNotEqual(0, proc.returncode, "固定件移走仍派出了新审")
        self.assertIn(f"updates/{rid}/before/{rel}", proc.stdout + proc.stderr)
        for path, kept in carriers.items():
            self.assertEqual(kept, path.read_bytes(), f"prepare 失败时改写了旧载体 {path.name}")
        # 恢复同一份字节：对象回到原样，已接收的报告仍可消费
        fixed.write_bytes(first_bytes)
        again = self.review_prepare()
        self.assertTrue(again["reused"], again)
        self.assertEqual(first["material_key"], self.object_facts()["key"])
        self.assertEqual("pass", self.review_check()["result"])

    def test_a_failed_object_check_leaves_the_review_carriers_untouched(self) -> None:
        """R3（S20）：对象核验先于替换 task／派审载体；固定 before 缺件时失败，盘上旧载体一字不改。"""
        rid = self.closed_round()
        self.assertTrue(self.review_prepare()["reused"])
        task = self.src / "review" / "task.md"
        dispatch = self.src / "review" / "dispatch.md"
        prepared = self.src / "review" / "prepared.json"
        kept = {path: path.read_bytes() for path in (task, dispatch, prepared)}
        original = self.before_original(rid)
        saved = original.read_bytes()
        original.unlink()
        proc = self.review_prepare_proc()
        self.assertNotEqual(0, proc.returncode, "缺固定 before 仍派出了新审")
        self.assertIn("审查对象不全", proc.stdout + proc.stderr)
        for path, data in kept.items():
            self.assertEqual(data, path.read_bytes(), f"失败时改写了 {path.name}")
        original.write_bytes(saved)
        self.assertTrue(self.review_prepare()["reused"], "恢复固定件后没有回到原对象")

    def test_the_stage_review_reaches_the_same_conclusion(self) -> None:
        rid = self.closed_round()
        path = self.before_original(rid)
        rel = path.relative_to(self.feature_root).as_posix()
        path.unlink()
        got = self.input_gaps()
        self.assertEqual(rid, got["update"])
        self.assertTrue([gap for gap in got["gaps"] if rel in gap and "恢复" in gap], got["gaps"])
