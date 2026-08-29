"""本地需求系统替身：一个目录就是一套需求系统，一个子目录就是一张单。

外网 demo 用 `story.js` 屏蔽内网需求系统。此前那份替身把 RR/SR 从一个演示数据目录里
按模板渲染出来，而那个目录早已不在——`init` 走到拉材料就崩，`review` 永远 `unchanged`，
四个 Case 全靠测试驱动把材料预先铺进需求目录，**被测模型从来没有真的从系统拉过单**。

现在它读一个真实存在的目录：查无此单会停住、归档会覆盖系统正文并留下历史版本、
restore 回退那次覆盖、review 拉回评审人留在系统上的回稿。这里判的就是这四件事
（KM-1…KM-4），因为它们是被测模型在实跑里唯一能观察到的「系统行为」。
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts"
STORY_JS = SCRIPTS / "story.js"

AR = "AR70001"
SR = "SR70001"
RR = "RR70001"

PRD_TEXT = "# 产品需求正文\n\n用户要的是这一段。\n"
SR_TEXT = "# 系统设计正文\n\n分工写在这一段。\n"
AR_TEXT = "# 系统预填的开发需求\n\n上游先填了一版。\n"


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
        return story, notes


def _env() -> dict[str, str]:
    import os
    return {k: v for k, v in os.environ.items()
            if k != "STORY_REQUIREMENT_SYSTEM_DIR"}


class TestInit(SystemCase):
    """KM-1：按单号拉单据。"""

    def test_pulls_three_documents_and_three_tickets(self) -> None:
        proc = self.story("init", AR)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual({"mode": "init", "reqNo": AR, "parentNo": SR,
                          "rrNo": RR, "success": True}, self.receipt(proc))
        self.assertEqual(PRD_TEXT, (self.feature / "RR" / "prd.md").read_text("utf-8"))
        self.assertEqual(SR_TEXT, (self.feature / "SR" / "design.md").read_text("utf-8"))
        self.assertEqual(AR_TEXT, (self.feature / "AR" / "design.md").read_text("utf-8"))
        for rel, expect in ((("AR", "detail.json"), {"reqNo": AR, "parentNo": SR, "rrNo": RR}),
                            (("SR", "detail.json"), {"reqNo": SR, "rrNo": RR}),
                            (("RR", "detail.json"), {"reqNo": RR})):
            detail = json.loads((self.feature.joinpath(*rel)).read_text("utf-8"))
            for key, value in expect.items():
                self.assertEqual(value, detail[key], rel)

    def test_system_carries_no_images(self) -> None:
        """系统只支持 md：拉一次单，需求目录里不该出现任何图片。

        图片走的是另一条路——人手上的设计文档进收件箱、由导入抽出来。
        真让系统吐出图片，本地就跑通了一条真实环境里不存在的取材路径。
        """
        self.story("init", AR)
        images = [p for p in self.feature.rglob("*")
                  if p.is_file() and p.suffix.lower() in
                  {".png", ".jpg", ".jpeg", ".svg", ".webp", ".bmp"}]
        self.assertEqual([], images)

    def test_existing_local_design_is_never_overwritten(self) -> None:
        """AR/design.md 已有内容就是需求分析的成果，拉取不能盖掉它。"""
        (self.feature / "AR").mkdir(parents=True)
        (self.feature / "AR" / "design.md").write_text("# 我自己写的\n", encoding="utf-8")
        self.story("init", AR)
        self.assertEqual("# 我自己写的\n", (self.feature / "AR" / "design.md").read_text("utf-8"))

    def test_missing_body_is_left_for_the_placeholder_step(self) -> None:
        """系统上没有正文就不写：空文件会让下游分不清「没有」和「拉到了空的」。"""
        (self.system / RR / "prd.md").unlink()
        proc = self.story("init", AR)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertFalse((self.feature / "RR" / "prd.md").exists())
        self.assertTrue((self.feature / "SR" / "design.md").exists())

    def test_unknown_ticket_stops_instead_of_seeding_placeholders(self) -> None:
        proc = self.story("init", "AR70099")
        self.assertEqual(1, proc.returncode)
        receipt = self.receipt(proc)
        self.assertFalse(receipt["success"])
        self.assertIn("查无此单", receipt["error"])
        self.assertFalse((self.project / "doc" / "features" / "AR70099").exists())

    def test_unreachable_system_is_not_reported_as_unknown_ticket(self) -> None:
        """两种「取不到」的补救动作完全不同，报同一句话就分不出该找谁。"""
        proc = self.story("init", AR, system=self.system.parent / "nowhere")
        self.assertEqual(1, proc.returncode)
        error = self.receipt(proc)["error"]
        self.assertTrue(error.startswith("需求系统不可达"), error)
        self.assertIn("STORY_REQUIREMENT_SYSTEM_DIR", error)


class TestArchive(SystemCase):
    """KM-2：归档是往系统上写，本地一个字节都不动。"""

    def setUp(self) -> None:
        super().setUp()
        self.story("init", AR)
        self.story_text, self.notes_text = self.write_spec_products()

    def test_body_is_replaced_and_previous_version_kept(self) -> None:
        proc = self.story("archive", AR)
        self.assertEqual(0, proc.returncode, proc.stderr)
        receipt = self.receipt(proc)
        self.assertTrue(receipt["archived"])
        self.assertTrue(receipt["verified"])
        self.assertEqual(self.story_text, (self.system / AR / "design.md").read_text("utf-8"))
        self.assertEqual(self.notes_text,
                         (self.system / AR / "attachments" / "review.md").read_text("utf-8"))
        history = sorted((self.system / AR / "history").glob("design-*.md"))
        self.assertEqual(1, len(history))
        self.assertEqual(AR_TEXT, history[0].read_text("utf-8"))
        self.assertEqual(str(receipt["backupPath"]),
                         f"{AR}/history/{history[0].name}")

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

    def test_workspace_is_untouched(self) -> None:
        before = {p.relative_to(self.feature).as_posix(): p.read_bytes()
                  for p in sorted(self.feature.rglob("*")) if p.is_file()}
        self.story("archive", AR)
        after = {p.relative_to(self.feature).as_posix(): p.read_bytes()
                 for p in sorted(self.feature.rglob("*")) if p.is_file()}
        self.assertEqual(before, after)

    def test_missing_story_fails_without_touching_the_system(self) -> None:
        (self.feature / "AR" / "story.md").unlink()
        proc = self.story("archive", AR)
        self.assertEqual(1, proc.returncode)
        self.assertIn("AR/story.md", self.receipt(proc)["error"])
        self.assertEqual(AR_TEXT, (self.system / AR / "design.md").read_text("utf-8"))

    def test_local_ticket_has_no_place_to_archive(self) -> None:
        """没有系统单据的本地单不走归档——交付终点就是仓内那三份产物。"""
        local = self.project / "doc" / "features" / "ISSUE-70002" / "AR"
        local.mkdir(parents=True)
        (local / "story.md").write_text("# 叙事件\n", encoding="utf-8")
        (local / "review.md").write_text("# 评审记录\n", encoding="utf-8")
        proc = self.story("archive", "ISSUE-70002")
        self.assertEqual(1, proc.returncode)
        self.assertFalse((self.system / "ISSUE-70002").exists())


class TestRestoreAndReview(SystemCase):
    """KM-3：回退那次覆盖；拉回评审人写下的东西。"""

    def setUp(self) -> None:
        super().setUp()
        self.story("init", AR)
        self.story_text, self.notes_text = self.write_spec_products()

    def test_restore_returns_the_previous_body(self) -> None:
        self.story("archive", AR)
        self.assertEqual(self.story_text, (self.system / AR / "design.md").read_text("utf-8"))
        proc = self.story("restore", AR)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertTrue(self.receipt(proc)["restored"])
        self.assertEqual(AR_TEXT, (self.system / AR / "design.md").read_text("utf-8"))
        self.assertEqual(self.story_text, (self.feature / "AR" / "story.md").read_text("utf-8"))

    def test_restore_without_history_fails(self) -> None:
        proc = self.story("restore", AR)
        self.assertEqual(1, proc.returncode)
        self.assertFalse(self.receipt(proc)["success"])

    def test_review_writes_the_feedback_back_after_backing_up(self) -> None:
        feedback = "# 评审记录\n\n结论：同意，但第三章要改。\n"
        (self.system / AR / "review-feedback.md").write_text(feedback, encoding="utf-8")
        proc = self.story("review", AR)
        self.assertEqual(0, proc.returncode, proc.stderr)
        receipt = self.receipt(proc)
        self.assertEqual("confirmed", receipt["status"])
        self.assertEqual(feedback, (self.feature / "AR" / "review.md").read_text("utf-8"))
        backup = self.feature / receipt["backupPath"]
        self.assertEqual(self.notes_text, backup.read_text("utf-8"))

    def test_review_without_feedback_changes_nothing(self) -> None:
        """不伪造表态：系统上没人批注，本地就该原样保留。"""
        proc = self.story("review", AR)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual("unchanged", self.receipt(proc)["status"])
        self.assertEqual(self.notes_text, (self.feature / "AR" / "review.md").read_text("utf-8"))

    def test_review_requires_a_first_draft(self) -> None:
        (self.feature / "AR" / "review.md").unlink()
        proc = self.story("review", AR)
        self.assertEqual(1, proc.returncode)
        self.assertIn("AR/review.md", self.receipt(proc)["error"])


class TestNoStaleDataSource(unittest.TestCase):
    """KM-4：代码域里不许再有指向那个已被删除的演示数据目录的引用。

    留着不报错的引用比留着坏代码更糟：它让「替身接没接上」看起来像「正常走默认」。
    历史设计文档记录的是当时的事实，不在扫描面内。
    """

    SCAN = (
        REPO_ROOT / "doc" / "extensions",
        REPO_ROOT / "test" / "story" / "scripts",
        REPO_ROOT / "test" / "story" / "tests",
        REPO_ROOT / "test" / "story" / "config",
        REPO_ROOT / "test" / "story" / "regression",
        REPO_ROOT / "test" / "story" / "TEST.md",
        REPO_ROOT / "test" / "story" / "AGENTS.md",
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


if __name__ == "__main__":
    unittest.main()
