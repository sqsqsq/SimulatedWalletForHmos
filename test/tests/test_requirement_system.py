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
        notes = "# 评审记录\n\n草稿（待开发确认）\n"
        (self.feature / "AR").mkdir(parents=True, exist_ok=True)
        (self.feature / "AR" / "story.md").write_text(story, encoding="utf-8")
        (self.feature / "AR" / "review.md").write_text(notes, encoding="utf-8")
        (self.feature / "blueprint").mkdir(parents=True, exist_ok=True)
        (self.feature / "blueprint" / "component-blueprint.review.md").write_text(DESIGN_REVIEW_TEXT, encoding="utf-8")
        return story, notes

    def batch(self) -> Path:
        return self.feature / "sources" / "inbox" / "fetch-test"

    def fetch(self) -> dict:
        proc = subprocess.run(
            ["node", str(STORY_JS), "fetch", AR, "token", "--out", str(self.batch()),
             "--project-root", str(self.project)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, env={**_env(), "STORY_REQUIREMENT_SYSTEM_DIR": str(self.system)})
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads((self.feature / "AR" / "story-src" / "fetched.json").read_text(encoding="utf-8"))

    def items(self) -> dict:
        receipt = json.loads((self.feature / "AR" / "story-src" / "fetched.json").read_text(encoding="utf-8"))
        return {i["name"]: i for i in receipt["items"]}


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
                                 if not w.startswith(("sources/inbox/fetch-test/", "AR/story-src/"))})

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
    """归档是往系统上写三件：正文、评审记录附件、设计参考附件（蓝图原生评审投影的原字节），逐件写入并读回；
    本地只多一份系统正文的备份，回执记读回。"""

    def setUp(self) -> None:
        super().setUp()
        self.story_text, self.notes_text = self.write_spec_products()
        self.before = self.fetch()

    def test_three_items_are_written_and_read_back(self) -> None:
        proc = self.story("archive", AR)
        self.assertEqual(0, proc.returncode, proc.stderr)
        receipt = self.receipt(proc)
        self.assertTrue(receipt["archived"])
        self.assertTrue(receipt["verified"])
        self.assertEqual(self.story_text, (self.system / AR / "design.md").read_text("utf-8"))
        self.assertEqual(self.notes_text, (self.system / AR / "attachments" / "review.md").read_text("utf-8"))
        self.assertEqual(DESIGN_REVIEW_TEXT, (self.system / AR / "attachments" / "design-review.md").read_text("utf-8"))
        backups = sorted((self.feature / ".backups" / "cloud").glob("design-*.md"))
        self.assertEqual(1, len(backups))
        self.assertEqual(AR_TEXT, backups[0].read_text("utf-8"))
        self.assertEqual(f".backups/cloud/{backups[0].name}", receipt["backupPath"])
        items = self.items()
        for name, local in (("AR-design.md", "AR/story.md"), ("review.md", "AR/review.md"), ("design-review.md", "blueprint/component-blueprint.review.md")):
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
        (self.system / AR / "attachments" / "review.md").write_text("评审人在线上改的\n", encoding="utf-8")
        proc = self.story("archive", AR)
        self.assertEqual(1, proc.returncode)
        self.assertIn("预检之后又变了", self.receipt(proc)["error"])
        self.assertEqual(AR_TEXT, (self.system / AR / "design.md").read_text("utf-8"))
        self.assertEqual("评审人在线上改的\n", (self.system / AR / "attachments" / "review.md").read_text("utf-8"))

    def test_a_failed_item_keeps_the_written_ones_and_a_retry_skips_them(self) -> None:
        """第三件写不进去：前两件已写并读回，第三件记失败；重新取材后重试，已写的两件判相同、不再写。"""
        target = self.system / AR / "attachments" / "design-review.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("旧附件\n", encoding="utf-8")
        target.chmod(stat.S_IREAD)
        self.addCleanup(target.chmod, stat.S_IREAD | stat.S_IWRITE)
        self.fetch()
        proc = self.story("archive", AR)
        self.assertEqual(1, proc.returncode)
        items = self.items()
        self.assertEqual(("fetched", "fetched", "failed"),
                         tuple(items[n]["status"] for n in ("AR-design.md", "review.md", "design-review.md")))
        self.assertNotIn("checkedAt", items["design-review.md"])
        target.chmod(stat.S_IREAD | stat.S_IWRITE)
        self.fetch()
        proc = self.story("archive", AR)
        self.assertEqual(0, proc.returncode, proc.stderr)
        items = self.items()
        self.assertEqual(("same", "same", "fetched"),
                         tuple(items[n]["status"] for n in ("AR-design.md", "review.md", "design-review.md")))
        self.assertEqual(DESIGN_REVIEW_TEXT, target.read_text("utf-8"))

    def test_local_ticket_has_no_place_to_archive(self) -> None:
        """没有系统单据的本地单不走归档——交付终点就是仓内那三份产物。"""
        local = self.project / "doc" / "features" / "ISSUE-70002" / "AR"
        local.mkdir(parents=True)
        (local / "story.md").write_text("# 叙事件\n", encoding="utf-8")
        (local / "review.md").write_text("# 评审记录\n", encoding="utf-8")
        proc = self.story("archive", "ISSUE-70002")
        self.assertEqual(1, proc.returncode)
        self.assertFalse((self.system / "ISSUE-70002").exists())


class TestRestore(SystemCase):
    """restore 用 `.backups/cloud/` 里的备份恢复系统正文，附件与本地业务文件不动。"""

    def setUp(self) -> None:
        super().setUp()
        self.story_text, self.notes_text = self.write_spec_products()
        self.fetch()

    def test_restore_returns_the_previous_body_and_leaves_the_attachments(self) -> None:
        self.story("archive", AR)
        self.assertEqual(self.story_text, (self.system / AR / "design.md").read_text("utf-8"))
        proc = self.story("restore", AR)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertTrue(self.receipt(proc)["restored"])
        self.assertEqual(AR_TEXT, (self.system / AR / "design.md").read_text("utf-8"))
        self.assertEqual(self.story_text, (self.feature / "AR" / "story.md").read_text("utf-8"))
        self.assertEqual(DESIGN_REVIEW_TEXT, (self.system / AR / "attachments" / "design-review.md").read_text("utf-8"))

    def test_restore_takes_the_latest_cloud_backup(self) -> None:
        self.story("archive", AR)
        cloud = self.feature / ".backups" / "cloud"
        (cloud / "design-29990101000000.md").write_text("# 更晚的备份\n", encoding="utf-8")
        proc = self.story("restore", AR)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual("# 更晚的备份\n", (self.system / AR / "design.md").read_text("utf-8"))
        self.assertEqual(2, len(list(cloud.glob("design-*.md"))), "restore 不该再备份一份")

    def test_restore_without_backup_fails(self) -> None:
        proc = self.story("restore", AR)
        self.assertEqual(1, proc.returncode)
        receipt = self.receipt(proc)
        self.assertFalse(receipt["success"])
        self.assertIn(".backups", receipt["error"])



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
             f"doc/features/{AR}/sources/inbox/fetch-test"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, cwd=self.project, env={**_env(), "STORY_REQUIREMENT_SYSTEM_DIR": str(self.system)})
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertTrue((self.feature / "AR" / "story-src" / "fetched.json").is_file(), "回执没落在本工程的需求目录")
        self.assertFalse((self.project / "doc" / "doc").exists(),
                         "默认根少算一级：材料落进了 doc/ 底下的第二层 doc/features/")


if __name__ == "__main__":
    unittest.main()
