"""本地需求系统替身：一个目录就是一套需求系统，一个子目录就是一张单。

外网 demo 用 `story.js` 屏蔽内网需求系统。它读一个真实存在的目录：取材把上游正文写进来源收件箱下的
取材批次、查无此单会停住、归档覆盖系统正文之前把系统上那一版备份到需求目录的 `.backups/cloud/`、
restore 用那份备份恢复系统正文。这里判的就是这几件事（KM-1…KM-4），因为它们是被测模型在实跑里
唯一能观察到的「系统行为」。
"""
from __future__ import annotations

import hashlib
import json
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from ext_workspace import DEV_EXT

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = DEV_EXT / "skills" / "story" / "scripts" / "adapters"
STORY_JS = SCRIPTS / "story.js"

AR = "AR70001"
SR = "SR70001"
RR = "RR70001"

PRD_TEXT = "# 产品需求正文\n\n用户要的是这一段。\n"
SR_TEXT = "# 系统设计正文\n\n分工写在这一段。\n"
AR_TEXT = "# 系统预填的开发需求\n\n上游先填了一版。\n"
DESIGN_REVIEW_TEXT = "# 蓝图评审投影\n\n完整技术契约在这一份。\n"


def short(path: Path) -> str:
    """与对接层回执同一口径的摘要。"""
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()[:16]


class SystemCase(unittest.TestCase):
    """每个用例一套独立的需求系统与工作区——系统状态会被 archive 改写。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.system = root / "system"
        self.project = root / "project"
        self.feature = self.project / "doc" / "features" / AR
        for no, detail in (
            (RR, {"reqNo": RR, "type": "RR", "title": "产品需求"}),
            (SR, {"reqNo": SR, "type": "SR", "title": "系统设计", "rrNo": RR}),
            (AR, {"reqNo": AR, "type": "AR", "title": "开发需求",
                  "parentNo": SR, "rrNo": RR}),
        ):
            (self.system / no).mkdir(parents=True)
            (self.system / no / "detail.json").write_text(
                json.dumps(detail, ensure_ascii=False), encoding="utf-8")
        (self.system / RR / "prd.md").write_text(PRD_TEXT, encoding="utf-8")
        (self.system / SR / "design.md").write_text(SR_TEXT, encoding="utf-8")
        (self.system / AR / "design.md").write_text(AR_TEXT, encoding="utf-8")

    def story(self, *args: str, system: Path | None = None) -> subprocess.CompletedProcess:
        target = self.system if system is None else system
        return subprocess.run(
            ["node", str(STORY_JS), *args, "token", "--project-root", str(self.project)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, env={**_env(), "STORY_REQUIREMENT_SYSTEM_DIR": str(target)})

    def receipt(self, proc: subprocess.CompletedProcess) -> dict:
        line = [l for l in proc.stdout.splitlines() if l.strip().startswith("{")]
        self.assertTrue(line, f"stdout 里没有回执 JSON：{proc.stdout}\n{proc.stderr}")
        return json.loads(line[-1])

    def write_spec_products(self) -> tuple[str, str]:
        story = "# 叙事件\n\n评审看的是这一份。\n"
        (self.feature / "AR").mkdir(parents=True, exist_ok=True)
        (self.feature / "AR" / "story.md").write_text(story, encoding="utf-8")
        (self.feature / "blueprint").mkdir(parents=True, exist_ok=True)
        (self.feature / "blueprint" / "component-blueprint.review.md").write_text(DESIGN_REVIEW_TEXT, encoding="utf-8")
        return story, ""

    def batch(self) -> Path:
        return self.feature / "inbox" / "fetch-test"

    def deliver(self) -> None:
        """发布前核对记下的交付集合（`story_flow.py publish` 写进取材回执的 delivery）：本地交付件的来源与此刻的摘要。"""
        path = self.feature / "AR" / "story-src" / "fetched.json"
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["delivery"] = {"prepared_at": "2099-01-01T00:00:00+00:00", "items": [
            {"name": name, "local": rel, "digest": short(self.feature / rel)}
            for name, rel in (("AR-design.md", "AR/story.md"),
                              ("design-review.md", "blueprint/component-blueprint.review.md"))]}
        path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")

    def fetch(self) -> dict:
        proc = subprocess.run(
            ["node", str(STORY_JS), "fetch", AR, "token", "--out", str(self.batch()),
             "--project-root", str(self.project)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, env={**_env(), "STORY_REQUIREMENT_SYSTEM_DIR": str(self.system)})
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads((self.feature / "AR" / "story-src" / "fetched.json").read_text(encoding="utf-8"))

    def items(self) -> dict:
        return {i["name"]: i for i in self.receipt_file()["items"]}

    def receipt_file(self) -> dict:
        return json.loads((self.feature / "AR" / "story-src" / "fetched.json").read_text(encoding="utf-8"))


def _env() -> dict[str, str]:
    import os
    return {k: v for k, v in os.environ.items()
            if k != "STORY_REQUIREMENT_SYSTEM_DIR"}


class TestFetch(SystemCase):
    """KM-1：按单号取上游正文，写进来源收件箱下的一个取材批次。"""

    def fetch_into(self, ticket: str = AR, system: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["node", str(STORY_JS), "fetch", ticket, "token", "--out", str(self.batch()),
             "--project-root", str(self.project)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            env={**_env(), "STORY_REQUIREMENT_SYSTEM_DIR": str(self.system if system is None else system)})

    def test_pulls_three_documents_into_one_batch(self) -> None:
        proc = self.fetch_into()
        self.assertEqual(0, proc.returncode, proc.stderr)
        receipt = self.receipt(proc)
        self.assertEqual(("fetch", AR, SR, RR, True),
                         (receipt["mode"], receipt["reqNo"], receipt["parentNo"], receipt["rrNo"], receipt["success"]))
        self.assertEqual(PRD_TEXT, (self.batch() / "RR-prd.md").read_text("utf-8"))
        self.assertEqual(SR_TEXT, (self.batch() / "SR-design.md").read_text("utf-8"))
        self.assertEqual(AR_TEXT, (self.batch() / "AR-design.md").read_text("utf-8"))
        batch = json.loads((self.batch() / ".receipt.json").read_text(encoding="utf-8"))
        self.assertEqual({("AR", AR, "开发需求"), ("SR", SR, "系统设计"), ("RR", RR, "产品需求")},
                         {(i["role"], i["ticket"], i["title"]) for i in batch["items"]})

    def test_system_carries_no_images(self) -> None:
        """系统只支持 md：取一次材，需求目录里不该出现任何图片。

        图片走的是另一条路——人手上的设计文档进收件箱、由导入抽出来。
        真让系统吐出图片，本地就跑通了一条真实环境里不存在的取材路径。
        """
        self.fetch_into()
        images = [p for p in self.feature.rglob("*")
                  if p.is_file() and p.suffix.lower() in
                  {".png", ".jpg", ".jpeg", ".svg", ".webp", ".bmp"}]
        self.assertEqual([], images)

    def test_fetch_writes_no_business_file(self) -> None:
        """取材只写批次与 `AR/story-src` 下的回执：本地已有的业务文件一个字不动。"""
        (self.feature / "AR").mkdir(parents=True)
        (self.feature / "AR" / "story.md").write_text("# 我自己写的\n", encoding="utf-8")
        self.fetch_into()
        self.assertEqual("# 我自己写的\n", (self.feature / "AR" / "story.md").read_text("utf-8"))
        written = {p.relative_to(self.feature).as_posix() for p in self.feature.rglob("*") if p.is_file()}
        self.assertEqual(set(), {w for w in written - {"AR/story.md"}
                                 if not w.startswith(("inbox/fetch-test/", "AR/story-src/"))})

    def test_review_attachments_are_inputs_in_their_own_batch(self) -> None:
        """评审回稿、历史评审附件与设计参考附件都进当次评审批次，带来源与摘要；回执指明批次。"""
        (self.system / AR / "attachments").mkdir(parents=True)
        (self.system / AR / "attachments" / "review.md").write_text("评审记录\n", encoding="utf-8")
        (self.system / AR / "attachments" / "design-review.md").write_text(DESIGN_REVIEW_TEXT, encoding="utf-8")
        (self.system / AR / "review-feedback.md").write_text("评审回稿\n", encoding="utf-8")
        proc = self.fetch_into()
        self.assertEqual(0, proc.returncode, proc.stderr)
        receipt = json.loads((self.feature / "AR" / "story-src" / "fetched.json").read_text(encoding="utf-8"))
        self.assertEqual("inbox/review/fetch-test", receipt["review_out"])
        batch = json.loads((self.feature / "inbox" / "review" / "fetch-test" / ".receipt.json").read_text(encoding="utf-8"))
        rows = {i["name"]: i for i in batch["items"]}
        self.assertEqual({"review.md", "design-review.md", "review-feedback.md"}, set(rows),
                         "未发布的本单正文仍是材料原件，不进评审批次")
        for name in ("review.md", "design-review.md", "review-feedback.md"):
            self.assertEqual(("fetched", f"inbox/review/fetch-test/{name}"), (rows[name]["status"], rows[name]["saved"]))
            self.assertIn("sha256", rows[name])
        self.assertFalse((self.feature / "AR" / "story-src" / "fetched-design-review.md").exists(),
                         "设计参考又写了一份不在评审批次里的副本")

    def test_a_failed_review_attachment_is_in_the_batch_receipt(self) -> None:
        """附件读取失败不只在总回执里：评审批次回执也要有这一件，update 才说得出缺哪件。"""
        bad = self.system / AR / "attachments" / "design-review.md"
        bad.mkdir(parents=True)                    # 同名目录：读取附件失败
        proc = self.fetch_into()
        self.assertEqual(1, proc.returncode, proc.stderr)
        receipt = self.receipt(proc)
        self.assertFalse(receipt["success"])
        self.assertEqual("inbox/review/fetch-test", json.loads(
            (self.feature / "AR" / "story-src" / "fetched.json").read_text(encoding="utf-8"))["review_out"])
        rows = {i["name"]: i for i in json.loads(
            (self.feature / "inbox" / "review" / "fetch-test" / ".receipt.json").read_text(encoding="utf-8"))["items"]}
        self.assertEqual("failed", rows["design-review.md"]["status"])
        self.assertNotIn("saved", rows["design-review.md"])

    def test_absent_attachments_do_not_create_an_empty_review_batch(self) -> None:
        proc = self.fetch_into()
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertNotIn("review_out", self.receipt(proc))
        self.assertFalse((self.feature / "inbox" / "review").exists())

    def test_missing_body_is_reported_absent_not_written_empty(self) -> None:
        """系统上没有正文就不写：空文件会让下游分不清「没有」和「拉到了空的」。"""
        (self.system / RR / "prd.md").unlink()
        proc = self.fetch_into()
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertFalse((self.batch() / "RR-prd.md").exists())
        self.assertTrue((self.batch() / "SR-design.md").exists())
        self.assertEqual("absent", {i["name"]: i for i in self.receipt(proc)["items"]}["RR-prd.md"]["status"])

    def test_unknown_ticket_stops_without_a_feature_dir(self) -> None:
        proc = self.fetch_into("AR70099")
        self.assertEqual(1, proc.returncode)
        receipt = self.receipt(proc)
        self.assertFalse(receipt["success"])
        self.assertIn("查无此单", receipt["error"])
        self.assertFalse((self.project / "doc" / "features" / "AR70099").exists())

    def test_unreachable_system_is_not_reported_as_unknown_ticket(self) -> None:
        """两种「取不到」的补救动作完全不同，报同一句话就分不出该找谁。"""
        proc = self.fetch_into(system=self.system.parent / "nowhere")
        self.assertEqual(1, proc.returncode)
        error = self.receipt(proc)["error"]
        self.assertTrue(error.startswith("需求系统不可达"), error)
        self.assertIn("STORY_REQUIREMENT_SYSTEM_DIR", error)


class TestArchive(SystemCase):
    """归档是往系统上写 Story 正文与（系统要求时的）设计参考附件（蓝图原生评审投影的原字节），逐件写入并读回；
    本地只多一份系统正文的备份，回执记读回。"""

    def setUp(self) -> None:
        super().setUp()
        self.story_text, self.notes_text = self.write_spec_products()
        self.before = self.fetch()
        self.deliver()

    def test_the_delivery_is_written_and_read_back(self) -> None:
        proc = self.story("archive", AR)
        self.assertEqual(0, proc.returncode, proc.stderr)
        receipt = self.receipt(proc)
        self.assertTrue(receipt["archived"])
        self.assertTrue(receipt["verified"])
        self.assertEqual(self.story_text, (self.system / AR / "design.md").read_text("utf-8"))
        self.assertEqual(DESIGN_REVIEW_TEXT, (self.system / AR / "attachments" / "design-review.md").read_text("utf-8"))
        backups = sorted((self.feature / ".backups" / "cloud").glob("design-*.md"))
        self.assertEqual(1, len(backups))
        self.assertEqual(AR_TEXT, backups[0].read_text("utf-8"))
        self.assertEqual(f".backups/cloud/{backups[0].name}", receipt["backupPath"])
        items = self.items()
        for name, local in (("AR-design.md", "AR/story.md"), ("design-review.md", "blueprint/component-blueprint.review.md")):
            item = items[name]
            self.assertEqual("fetched", item["status"], item)
            self.assertEqual(short(self.feature / local), item["digest"])
            self.assertIn("checkedAt", item)
        after = json.loads((self.feature / "AR" / "story-src" / "fetched.json").read_text(encoding="utf-8"))
        self.assertEqual(self.before["fetchedAt"], after["fetchedAt"], "上传刷新了取材时间")
        self.assertEqual({i["name"]: i for i in self.before["items"]}["SR-design.md"], items["SR-design.md"], "上传动了上游材料的回执")

    def test_only_markdown_reaches_the_system(self) -> None:
        """本地有图也不上传：系统不承载图片，链接更不该被改写。"""
        assets = self.feature / "assets" / "ux"
        assets.mkdir(parents=True)
        (assets / "screen.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        story = self.story_text + "\n![界面参考](../assets/ux/screen.png)\n"
        (self.feature / "AR" / "story.md").write_text(story, encoding="utf-8")
        self.deliver()
        self.story("archive", AR)
        uploaded = sorted(p.suffix.lower() for p in (self.system / AR).rglob("*") if p.is_file())
        self.assertEqual({".json", ".md"}, set(uploaded))
        self.assertIn("../assets/ux/screen.png", (self.system / AR / "design.md").read_text("utf-8"))

    def test_only_the_cloud_backup_and_the_receipt_change_locally(self) -> None:
        before = {p.relative_to(self.feature).as_posix(): p.read_bytes()
                  for p in sorted(self.feature.rglob("*")) if p.is_file()}
        self.story("archive", AR)
        after = {p.relative_to(self.feature).as_posix(): p.read_bytes()
                 for p in sorted(self.feature.rglob("*")) if p.is_file()}
        added = sorted(set(after) - set(before))
        self.assertEqual(1, len(added), added)
        self.assertTrue(added[0].startswith(".backups/cloud/design-"), added)
        changed = sorted(k for k in before if before[k] != after.get(k))
        self.assertEqual(["AR/story-src/fetched.json"], changed)

    def test_a_missing_item_fails_without_touching_the_system(self) -> None:
        for rel in ("AR/story.md", "blueprint/component-blueprint.review.md"):
            with self.subTest(missing=rel):
                kept = (self.feature / rel).read_bytes()
                (self.feature / rel).unlink()
                proc = self.story("archive", AR)
                self.assertEqual(1, proc.returncode)
                self.assertIn(rel, self.receipt(proc)["error"])
                self.assertEqual(AR_TEXT, (self.system / AR / "design.md").read_text("utf-8"))
                (self.feature / rel).write_bytes(kept)

    def test_a_change_after_the_preflight_stops_before_any_write(self) -> None:
        """预检之后有人在系统上写了附件：一件都不写。"""
        (self.system / AR / "attachments").mkdir(parents=True, exist_ok=True)
        (self.system / AR / "attachments" / "design-review.md").write_text("评审人在线上改的\n", encoding="utf-8")
        proc = self.story("archive", AR)
        self.assertEqual(1, proc.returncode)
        self.assertIn("预检之后又变了", self.receipt(proc)["error"])
        self.assertEqual(AR_TEXT, (self.system / AR / "design.md").read_text("utf-8"))
        self.assertEqual("评审人在线上改的\n", (self.system / AR / "attachments" / "design-review.md").read_text("utf-8"))

    def test_a_failed_item_keeps_the_written_ones_and_a_retry_skips_them(self) -> None:
        """设计参考附件写不进去：正文已写并读回，附件记失败；重新取材后重试，已写的正文判相同、不再写。"""
        target = self.system / AR / "attachments" / "design-review.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("旧附件\n", encoding="utf-8")
        target.chmod(stat.S_IREAD)
        self.addCleanup(target.chmod, stat.S_IREAD | stat.S_IWRITE)
        self.fetch()
        self.deliver()
        proc = self.story("archive", AR)
        self.assertEqual(1, proc.returncode)
        items = self.items()
        self.assertEqual(("fetched", "failed"),
                         tuple(items[n]["status"] for n in ("AR-design.md", "design-review.md")))
        self.assertNotIn("checkedAt", items["design-review.md"])
        # 正文已真实覆盖：覆盖关联记在回执顶层，附件失败不撤销它，重新取材也保留
        wrote = self.receipt_file()["body_write"]
        self.assertEqual((short(self.feature / "AR" / "story.md"), AR_TEXT),
                         (wrote["target_digest"], (self.feature / wrote["backup"]).read_text("utf-8")))
        self.assertIn("verified_at", wrote)
        target.chmod(stat.S_IREAD | stat.S_IWRITE)
        self.fetch()
        self.assertEqual(wrote, self.receipt_file()["body_write"], "重新取材把正文覆盖关联丢了")
        self.deliver()
        self.assertEqual(wrote, self.receipt_file()["body_write"], "发布前核对把正文覆盖关联丢了")
        proc = self.story("archive", AR)
        self.assertEqual(0, proc.returncode, proc.stderr)
        items = self.items()
        self.assertEqual(("same", "fetched"),
                         tuple(items[n]["status"] for n in ("AR-design.md", "design-review.md")))
        self.assertEqual(DESIGN_REVIEW_TEXT, target.read_text("utf-8"))
        self.assertEqual(wrote, self.receipt_file()["body_write"], "续传时正文没再写，覆盖关联却变了")

    def test_a_local_change_after_the_publish_check_stops_before_any_write(self) -> None:
        """发布前核对记下交付集合之后本地又改了一件：一件都不写，报出哪件变了。"""
        (self.feature / "AR" / "story.md").write_text(self.story_text + "核对之后补的一句\n", encoding="utf-8")
        proc = self.story("archive", AR)
        self.assertEqual(1, proc.returncode)
        self.assertIn("AR/story.md 在发布前核对之后又变了", self.receipt(proc)["error"])
        self.assertEqual(AR_TEXT, (self.system / AR / "design.md").read_text("utf-8"))
        self.assertFalse((self.system / AR / "attachments" / "design-review.md").exists())

    def test_without_a_delivery_set_nothing_is_written(self) -> None:
        """取材之后没做发布前核对（回执里没有交付集合）：一件都不写，要求先核对。"""
        self.fetch()
        proc = self.story("archive", AR)
        self.assertEqual(1, proc.returncode)
        self.assertIn("交付集合", self.receipt(proc)["error"])
        self.assertEqual(AR_TEXT, (self.system / AR / "design.md").read_text("utf-8"))

    def test_local_ticket_has_no_place_to_archive(self) -> None:
        """没有系统单据的本地单不走归档——交付终点就是仓内那三份产物。"""
        local = self.project / "doc" / "features" / "ISSUE-70002" / "AR"
        local.mkdir(parents=True)
        (local / "story.md").write_text("# 叙事件\n", encoding="utf-8")
        proc = self.story("archive", "ISSUE-70002")
        self.assertEqual(1, proc.returncode)
        self.assertFalse((self.system / "ISSUE-70002").exists())


class TestRestore(SystemCase):
    """restore 照取材回执里的恢复准备把那次覆盖前的备份写回系统正文并读回；附件与本地业务文件不动。
    远端在准备之后又变了一字不写；远端已是目标只读回；写不进去记 failed，恢复未确认。"""

    def setUp(self) -> None:
        super().setUp()
        self.story_text, self.notes_text = self.write_spec_products()
        self.fetch()
        self.deliver()
        proc = self.story("archive", AR)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.backup = self.receipt(proc)["backupPath"]
        self.fetch()

    def prepare(self, action: str = "write") -> None:
        """恢复准备（`story_flow.py restored --prepare` 写进取材回执的 restore）：目标是归档留下的备份，远端是刚取回的那一版。"""
        path = self.feature / "AR" / "story-src" / "fetched.json"
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["restore"] = {"prepared_at": "2099-01-01T00:00:00+00:00", "name": "AR-design.md", "local": self.backup,
                              "digest": short(self.feature / self.backup), "external": short(self.system / AR / "design.md"),
                              "action": action}
        path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_restore_returns_the_previous_body_and_leaves_the_attachments(self) -> None:
        self.assertEqual(self.story_text, (self.system / AR / "design.md").read_text("utf-8"))
        self.prepare()
        proc = self.story("restore", AR)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertTrue(self.receipt(proc)["restored"])
        self.assertEqual(AR_TEXT, (self.system / AR / "design.md").read_text("utf-8"))
        self.assertEqual(self.story_text, (self.feature / "AR" / "story.md").read_text("utf-8"))
        self.assertEqual(DESIGN_REVIEW_TEXT, (self.system / AR / "attachments" / "design-review.md").read_text("utf-8"))
        body = self.items()["AR-design.md"]
        self.assertEqual(("fetched", short(self.feature / self.backup)), (body["status"], body["digest"]))
        self.assertIn("checkedAt", body)
        self.assertEqual(1, len(list((self.feature / ".backups" / "cloud").glob("design-*.md"))), "restore 不该再备份一份")

    def test_a_change_after_the_preparation_writes_nothing(self) -> None:
        self.prepare()
        (self.system / AR / "design.md").write_text("评审人后来改的正文\n", encoding="utf-8")
        proc = self.story("restore", AR)
        self.assertEqual(1, proc.returncode)
        self.assertIn("在恢复准备之后又变了", self.receipt(proc)["error"])
        self.assertEqual("评审人后来改的正文\n", (self.system / AR / "design.md").read_text("utf-8"))

    def test_a_body_already_at_the_target_is_only_read_back(self) -> None:
        (self.system / AR / "design.md").write_text(AR_TEXT, encoding="utf-8")
        self.prepare("skip")
        before = (self.system / AR / "design.md").stat().st_mtime_ns
        proc = self.story("restore", AR)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual(before, (self.system / AR / "design.md").stat().st_mtime_ns, "已是目标还重写了一次")
        self.assertEqual("same", self.items()["AR-design.md"]["status"])

    def test_a_failed_write_is_not_reported_as_restored(self) -> None:
        self.prepare()
        target = self.system / AR / "design.md"
        target.chmod(stat.S_IREAD)
        self.addCleanup(target.chmod, stat.S_IREAD | stat.S_IWRITE)
        proc = self.story("restore", AR)
        self.assertEqual(1, proc.returncode)
        self.assertIn("恢复未确认", self.receipt(proc)["error"])
        self.assertEqual("failed", self.items()["AR-design.md"]["status"])

    def test_restore_without_a_preparation_fails(self) -> None:
        proc = self.story("restore", AR)
        self.assertEqual(1, proc.returncode)
        receipt = self.receipt(proc)
        self.assertFalse(receipt["success"])
        self.assertIn("恢复准备", receipt["error"])


class TestNoStaleDataSource(unittest.TestCase):
    """KM-4：代码域里不许再有指向那个已被删除的演示数据目录的引用。

    留着不报错的引用比留着坏代码更糟：它让「替身接没接上」看起来像「正常走默认」。
    历史设计文档记录的是当时的事实，不在扫描面内。
    """

    SCAN = (
        DEV_EXT,
        REPO_ROOT / "test" / "scripts",
        REPO_ROOT / "test" / "tests",
        REPO_ROOT / "test" / "config",
        REPO_ROOT / "test" / "regression",
        REPO_ROOT / "test" / "TEST.md",
        REPO_ROOT / "AGENTS.md",
    )
    # 拼出来而不是写成字面：写成字面，这个 checker 每次都会先扫到自己。
    PATTERN = re.compile("|".join(f"mock{sep}data" for sep in ("-", "_")), re.IGNORECASE)

    def test_no_reference_to_the_removed_demo_data_dir(self) -> None:
        hits = []
        for target in self.SCAN:
            paths = [target] if target.is_file() else [
                p for p in target.rglob("*")
                if p.is_file() and p.suffix in {".py", ".js", ".mjs", ".md", ".yaml", ".json"}
                and "__pycache__" not in p.parts]
            for path in paths:
                try:
                    text = path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
                for number, line in enumerate(text.splitlines(), start=1):
                    if self.PATTERN.search(line):
                        hits.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{number}")
        self.assertEqual([], hits)


class TheDefaultEntryFindsTheProjectRoot(SystemCase):
    """不传 `--project-root` 时，脚本自己上溯到实例根。

    SKILL 正文给的取材命令就是这个形态：`node doc/extensions/skills/story/scripts/
    adapters/story.js fetch <AR> <token> --out <取材批次>`。上溯的级数错一级，回执落到 `doc/` 底下
    再开一层 `doc/features/`，消费模型得改扩展源码才跑得下去。

    别的用例都显式传根（它们要的是隔离的工作区），所以这一条单独走默认入口。
    """

    def setUp(self) -> None:
        super().setUp()
        installed = (self.project / "doc" / "extensions" / "skills" / "story"
                     / "scripts" / "adapters")
        installed.mkdir(parents=True)
        for source in SCRIPTS.glob("*.js"):
            (installed / source.name).write_bytes(source.read_bytes())
        self.installed = installed / "story.js"

    def test_material_lands_in_the_features_dir_of_the_project(self) -> None:
        proc = subprocess.run(
            ["node", str(self.installed), "fetch", AR, "token", "--out",
             f"doc/features/{AR}/inbox/fetch-test"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, cwd=self.project, env={**_env(), "STORY_REQUIREMENT_SYSTEM_DIR": str(self.system)})
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertTrue((self.feature / "AR" / "story-src" / "fetched.json").is_file(), "回执没落在本工程的需求目录")
        self.assertFalse((self.project / "doc" / "doc").exists(),
                         "默认根少算一级：材料落进了 doc/ 底下的第二层 doc/features/")


class TestPublishIdentityAndReceiptRecovery(SystemCase):
    """S39：发布身份与取材回执写前保护——未发布、已发布、契约损坏、备份缺失/冲突、坏回执、部分发布与恢复后再取。"""

    def fetch_into(self, batch_name: str = "fetch-s39") -> subprocess.CompletedProcess:
        return subprocess.run(
            ["node", str(STORY_JS), "fetch", AR, "token", "--out", str(self.feature / "inbox" / batch_name),
             "--project-root", str(self.project)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            env={**_env(), "STORY_REQUIREMENT_SYSTEM_DIR": str(self.system)})

    def _snapshot_tree(self) -> dict[str, bytes]:
        if not self.feature.exists():
            return {}
        return {p.relative_to(self.feature).as_posix(): p.read_bytes()
                for p in sorted(self.feature.rglob("*")) if p.is_file()}

    def test_seven_states_identity_protection_and_recovery(self) -> None:
        src = self.feature / "AR" / "story-src"
        pub_backup = self.feature / ".backups" / "published" / "story.md"

        # 1. 未发布（首次无回执）：正常走 AR 材料批次
        p_init = self.fetch_into("fetch-01-init")
        self.assertEqual(0, p_init.returncode, p_init.stderr)
        ar_init = next(i for i in self.receipt(p_init)["items"] if i["name"] == "AR-design.md")
        self.assertEqual(("AR", "inbox/fetch-01-init/AR-design.md"), (ar_init.get("role"), ar_init.get("saved")))
        self.assertNotIn("delivery_return", self.receipt_file())

        # 2. 已发布（双证成立）：走 inbox/review/<batch>/ 且无 role，记 delivery_return
        src.mkdir(parents=True, exist_ok=True)
        valid_contract = json.dumps({"schema": 7, "archived": {"at": "2026-11-22T00:00:00+00:00"}}, ensure_ascii=False)
        (src / "story-flow.json").write_text(valid_contract, encoding="utf-8")
        pub_backup.parent.mkdir(parents=True, exist_ok=True)
        pub_backup.write_text("# 已发布 Story\n", encoding="utf-8")
        p_pub = self.fetch_into("fetch-02-pub")
        self.assertEqual(0, p_pub.returncode, p_pub.stderr)
        ar_pub = next(i for i in self.receipt(p_pub)["items"] if i["name"] == "AR-design.md")
        self.assertNotIn("role", ar_pub)
        self.assertEqual("inbox/review/fetch-02-pub/AR-design.md", ar_pub.get("saved"))
        self.assertTrue(self.receipt_file().get("delivery_return"))

        # 3. 契约损坏（JSON 不可读但备份仍在）：写前报错、不改任何文件、不建新批次
        (src / "story-flow.json").write_text('{"archived": ', encoding="utf-8")
        before = self._snapshot_tree()
        p_bad_c = self.fetch_into("fetch-03-bad-contract")
        self.assertEqual(1, p_bad_c.returncode)
        self.assertIn("story-flow.json", self.receipt(p_bad_c)["error"])
        self.assertEqual(before, self._snapshot_tree(), "契约损坏时改写了工作区或新建了批次")

        # 4a. 备份缺失（契约有 archived 但发布备份没了）：写前报错、不退回 role=AR、不改现场
        (src / "story-flow.json").write_text(valid_contract, encoding="utf-8")
        pub_backup.unlink()
        before = self._snapshot_tree()
        p_no_bk = self.fetch_into("fetch-04a-lost-backup")
        self.assertEqual(1, p_no_bk.returncode)
        self.assertIn(".backups/published/story.md", self.receipt(p_no_bk)["error"])
        self.assertEqual(before, self._snapshot_tree())

        # 4b. 反向冲突（有发布备份但契约未记 archived）：写前报错、不按首次 AR 取材
        pub_backup.write_text("# 已发布 Story\n", encoding="utf-8")
        (src / "story-flow.json").write_text(json.dumps({"schema": 7}), encoding="utf-8")
        before = self._snapshot_tree()
        p_no_arch = self.fetch_into("fetch-04b-no-archived")
        self.assertEqual(1, p_no_arch.returncode)
        self.assertIn("story-flow.json", self.receipt(p_no_arch)["error"])
        self.assertEqual(before, self._snapshot_tree())

        # 5. 坏回执（旧 fetched.json 截断在 body_write）：写前报错、原回执字节不覆写
        (src / "story-flow.json").write_text(valid_contract, encoding="utf-8")
        truncated = '{"body_write":'
        (src / "fetched.json").write_text(truncated, encoding="utf-8")
        before = self._snapshot_tree()
        p_bad_r = self.fetch_into("fetch-05-bad-receipt")
        self.assertEqual(1, p_bad_r.returncode)
        self.assertIn("fetched.json", self.receipt(p_bad_r)["error"])
        self.assertEqual(truncated, (src / "fetched.json").read_text(encoding="utf-8"))
        self.assertEqual(before, self._snapshot_tree())

        # 恢复损坏回执后再取 → 恢复成功，回流落 review/
        (src / "fetched.json").write_text(json.dumps({"mode": "fetch", "items": []}), encoding="utf-8")
        p_rec = self.fetch_into("fetch-05b-recovered")
        self.assertEqual(0, p_rec.returncode, p_rec.stderr)
        ar_rec = next(i for i in self.receipt(p_rec)["items"] if i["name"] == "AR-design.md")
        self.assertEqual("inbox/review/fetch-05b-recovered/AR-design.md", ar_rec.get("saved"))

    def test_partial_publish_body_write_and_after_restore_fetch(self) -> None:
        """部分发布（正文已覆盖写下 body_write，附件失败无 archived）不按首次 AR 取材；缺失 cloud 备份拒写；远端恢复登记后再取恢复 AR 角色。"""
        story_text, _ = self.write_spec_products()
        self.fetch()
        target = self.system / AR / "attachments" / "design-review.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("旧附件\n", encoding="utf-8")
        target.chmod(stat.S_IREAD)
        self.addCleanup(target.chmod, stat.S_IREAD | stat.S_IWRITE)
        self.fetch()
        self.deliver()
        proc_arch = self.story("archive", AR)
        self.assertEqual(1, proc_arch.returncode)
        wrote = self.receipt_file()["body_write"]
        self.assertTrue((self.feature / wrote["backup"]).is_file())

        # 部分发布态（无 archived、无发布备份，但有 body_write）：fetch 仍视为已覆盖回流表面、不标 role=AR、保 body_write
        p_part = self.fetch_into("fetch-06-partial")
        self.assertEqual(0, p_part.returncode, p_part.stderr)
        ar_part = next(i for i in self.receipt(p_part)["items"] if i["name"] == "AR-design.md")
        self.assertNotIn("role", ar_part, "部分发布已覆盖正文，不能再当首次 AR 原件")
        self.assertEqual("inbox/review/fetch-06-partial/AR-design.md", ar_part.get("saved"))
        self.assertEqual(wrote, self.receipt_file()["body_write"])

        # 若 body_write 指向的 cloud 备份丢失：写前拒改现场
        backup_abs = self.feature / wrote["backup"]
        saved_bytes = backup_abs.read_bytes()
        backup_abs.unlink()
        before = self._snapshot_tree()
        p_lost_cloud = self.fetch_into("fetch-06b-lost-cloud")
        self.assertEqual(1, p_lost_cloud.returncode)
        self.assertIn(wrote["backup"], self.receipt(p_lost_cloud)["error"])
        self.assertEqual(before, self._snapshot_tree())
        backup_abs.write_bytes(saved_bytes)

        # 模拟远端正文恢复并登记 contract.restored 后再取：正文回到 AR 原件，不再当作未归档覆盖回流
        (self.system / AR / "design.md").write_text(AR_TEXT, encoding="utf-8")
        (self.feature / "AR" / "story-src" / "story-flow.json").write_text(
            json.dumps({"schema": 7, "restored": {
                "at": "2099-01-01T00:00:00+00:00", "backup": wrote["backup"], "external_digest": short(backup_abs),
            }}, ensure_ascii=False),
            encoding="utf-8",
        )
        p_after_restore = self.fetch_into("fetch-07-after-restore")
        self.assertEqual(0, p_after_restore.returncode, p_after_restore.stderr)
        ar_restored = next(i for i in self.receipt(p_after_restore)["items"] if i["name"] == "AR-design.md")
        self.assertEqual(("AR", "inbox/fetch-07-after-restore/AR-design.md"), (ar_restored.get("role"), ar_restored.get("saved")))
        self.assertEqual(wrote, self.receipt_file()["body_write"])
        self.assertNotIn("delivery_return", self.receipt_file())

    def test_incomplete_body_write_is_rejected_and_first_write_null_backup_allowed(self) -> None:
        """S39 R1/R2：坏字段、目录路径、自指/越界无关文件作 body_write.backup 均在写前拒收且不覆写回执；真实备份文件与首次写 backup=null 合法。"""
        src = self.feature / "AR" / "story-src"
        src.mkdir(parents=True, exist_ok=True)
        cloud_dir = self.feature / ".backups" / "cloud"
        cloud_dir.mkdir(parents=True, exist_ok=True)
        (cloud_dir / "nested-dir").mkdir(exist_ok=True)
        real_backup = cloud_dir / "design-20261122000000.md"
        real_backup.write_text("# 覆盖前系统旧正文\n", encoding="utf-8")
        for label, bad_bw in (
            ("empty_object", {}),
            ("missing_digest", {"written_at": "2026-11-22T00:00:00Z", "backup": None}),
            ("missing_written_at", {"target_digest": "sha256:0123456789abcdef", "backup": None}),
            ("missing_backup_key", {"target_digest": "sha256:0123456789abcdef", "written_at": "2026-11-22T00:00:00Z"}),
            ("null_body_write", None),
            ("backup_is_cloud_dir", {"target_digest": "sha256:0123456789abcdef", "backup": ".backups/cloud", "written_at": "2026-11-22T00:00:00Z"}),
            ("backup_is_nested_dir", {"target_digest": "sha256:0123456789abcdef", "backup": ".backups/cloud/nested-dir", "written_at": "2026-11-22T00:00:00Z"}),
            ("backup_is_self_receipt", {"target_digest": "sha256:0123456789abcdef", "backup": "AR/story-src/fetched.json", "written_at": "2026-11-22T00:00:00Z"}),
            ("backup_escapes_cloud", {"target_digest": "sha256:0123456789abcdef", "backup": ".backups/cloud/../../AR/story-src/fetched.json", "written_at": "2026-11-22T00:00:00Z"}),
            ("backup_missing_file", {"target_digest": "sha256:0123456789abcdef", "backup": ".backups/cloud/design-missing.md", "written_at": "2026-11-22T00:00:00Z"}),
        ):
            with self.subTest(case=label):
                raw = json.dumps({"mode": "fetch", "items": [], "body_write": bad_bw}, ensure_ascii=False)
                (src / "fetched.json").write_text(raw, encoding="utf-8")
                before = self._snapshot_tree()
                proc = self.fetch_into(f"fetch-bad-{label}")
                self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
                self.assertIn("body_write", self.receipt(proc)["error"])
                self.assertEqual(before, self._snapshot_tree(), f"{label} 损坏凭据时改动了现场")
                self.assertEqual(raw, (src / "fetched.json").read_text(encoding="utf-8"))

        # 合法真实备份文件（与 target_digest 不同，表示覆盖前系统旧正文）：放行并按交付回流分流、原样保留 body_write
        valid_backup = {"target_digest": "sha256:0123456789abcdef", "backup": ".backups/cloud/design-20261122000000.md", "written_at": "2026-11-22T00:00:00Z"}
        (src / "fetched.json").write_text(json.dumps({"mode": "fetch", "items": [], "body_write": valid_backup}), encoding="utf-8")
        proc_real = self.fetch_into("fetch-valid-real-backup")
        self.assertEqual(0, proc_real.returncode, proc_real.stderr)
        ar_real = next(i for i in self.receipt(proc_real)["items"] if i["name"] == "AR-design.md")
        self.assertNotIn("role", ar_real)
        self.assertEqual("inbox/review/fetch-valid-real-backup/AR-design.md", ar_real.get("saved"))
        self.assertEqual(valid_backup, self.receipt_file()["body_write"])

        # 合法首次覆盖（系统原无正文，archive 记 backup: null）：允许通过并视为已覆盖回流表面、原样保留 body_write
        valid_first = {"target_digest": "sha256:0123456789abcdef", "backup": None, "written_at": "2026-11-22T00:00:00Z"}
        (src / "fetched.json").write_text(json.dumps({"mode": "fetch", "items": [], "body_write": valid_first}), encoding="utf-8")
        proc_ok = self.fetch_into("fetch-first-null-backup")
        self.assertEqual(0, proc_ok.returncode, proc_ok.stderr)
        ar_item = next(i for i in self.receipt(proc_ok)["items"] if i["name"] == "AR-design.md")
        self.assertNotIn("role", ar_item)
        self.assertEqual("inbox/review/fetch-first-null-backup/AR-design.md", ar_item.get("saved"))
        self.assertEqual(valid_first, self.receipt_file()["body_write"])

    def test_upgrade_changes_carries_fetch_write_before_contract(self) -> None:
        text = (DEV_EXT / "skills" / "story-adaptation" / "reference" / "upgrade-changes.md").read_text(encoding="utf-8")
        for token in ("body_write", ".backups/published/story.md", "story-flow.json", "fetched.json"):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
