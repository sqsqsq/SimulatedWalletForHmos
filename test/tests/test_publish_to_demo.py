"""统一安装动作（publish_to_demo）：测试装一次性 template，发布时装 demo。

锁四件：源集合按当前字节取、排除运行态；输入读不出或宿主入口写前核不过就不写；写入面只有扩展目录与
Framework 物化的宿主入口；目标在 git 里时有改动或查询失败就不装。失败只如实报告实际完成项，还原交给 git
或重建 template。

目标是接入了 demo Framework 的临时工程：宿主入口的核与物化走 Framework 原生能力，假工程测不出它。
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ext_workspace import git_init_excluding_framework, link_framework

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = REPO_ROOT / "extensions"
sys.path.insert(0, str(REPO_ROOT / "test" / "scripts"))
import publish_to_demo as pub  # noqa: E402

ENTRY_FILES = ("AGENTS.md", "CLAUDE.md")


def files_of(root: Path) -> dict[str, bytes]:
    """工程里的文件（相对路径 → 字节），不进 .git 与指向 demo 的 framework 链接。"""
    out: dict[str, bytes] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        if rel == Path("."):
            dirnames[:] = [d for d in dirnames if d not in (".git", "framework")]
        for name in filenames:
            path = Path(dirpath) / name
            out[(rel / name).as_posix()] = path.read_bytes()
    return dict(sorted(out.items()))


class PublishCase(unittest.TestCase):
    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.source = self.root / "src"
        shutil.copytree(SOURCE, self.source, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        self.target = self.root / "consumer"
        self.target.mkdir()
        config = json.loads((REPO_ROOT / "demo" / "framework.config.json").read_text(encoding="utf-8"))
        config["project_name"] = "C"
        (self.target / "framework.config.json").write_text(json.dumps(config), encoding="utf-8")
        link_framework(self.target)
        # 还没装扩展的工程：入口文件由 Framework 按「没有扩展」物化
        proc = subprocess.run(["node", str(self.source / pub.ENTRIES_SCRIPT), "--project-root", str(self.target),
                               "--action", "materialize"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, proc.returncode, proc.stderr)

    def install(self, **kw) -> pub.InstallResult:
        return pub.install_extension(self.source, self.target, **kw)

    def snapshot(self) -> dict[str, bytes]:
        return files_of(self.target)

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.target), *args], capture_output=True, check=True)

    def commit(self) -> None:
        git_init_excluding_framework(self.target)
        self.git("add", "-A")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "baseline")

    def cli(self) -> tuple[int, dict]:
        proc = subprocess.run([sys.executable, str(REPO_ROOT / "test/scripts/publish_to_demo.py"),
                               "--source", str(self.source), "--target", str(self.target)],
                              capture_output=True, text=True, encoding="utf-8")
        return proc.returncode, json.loads(proc.stdout)


class TheSourceSetIsWhatIsOnDisk(PublishCase):
    def test_untracked_and_modified_files_are_installed_and_runtime_state_is_not(self) -> None:
        (self.source / "hooks" / "shared" / "new-probe.mjs").write_text("export const x = 1;\n", encoding="utf-8")
        skill = self.source / "skills" / "story" / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\n还没提交的一行。\n", encoding="utf-8")
        for rel in ("node_modules/pkg/i.js", ".adapt-1.9.8/plan.json", "adapt/old.md",
                    "skills/story/scripts/core/__pycache__/m.cpython-313.pyc", "hooks/stale.pyc"):
            (self.source / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.source / rel).write_text("runtime", encoding="utf-8")
        (self.source / "rules" / ".keep").write_text("", encoding="utf-8")

        result = self.install()
        self.assertEqual("installed", result.status, result.problems)
        ext = self.target / "doc" / "extensions"
        self.assertTrue((ext / "hooks" / "shared" / "new-probe.mjs").is_file(), "未跟踪的新文件没进来")
        self.assertIn("还没提交的一行", (ext / "skills" / "story" / "SKILL.md").read_text(encoding="utf-8"))
        self.assertTrue((ext / "rules" / ".keep").is_file(), "普通隐藏文件被当成运行态丢了")
        for rel in ("node_modules", ".adapt-1.9.8", "adapt", "skills/story/scripts/core/__pycache__", "hooks/stale.pyc"):
            self.assertFalse((ext / rel).exists(), f"运行态 {rel} 进了目标")

    def test_everything_in_the_source_lands_and_every_skill_gets_its_host_entries(self) -> None:
        result = self.install()
        self.assertEqual("installed", result.status, result.problems)
        ext = self.target / "doc" / "extensions"
        for rel in pub.enumerate_source(self.source):
            self.assertEqual((self.source / rel).read_bytes(), (ext / rel).read_bytes(), rel)
        for skill in ("story", "story-adaptation"):
            for rel in (f".claude/commands/{skill}.md", f".opencode/skill/{skill}/SKILL.md"):
                text = (self.target / rel).read_text(encoding="utf-8")
                self.assertIn("agent-maison:instance-extension-bridge", text, rel)
                self.assertIn(f"doc/extensions/skills/{skill}/SKILL.md", text, rel)
        for name in ENTRY_FILES:
            self.assertIn("doc/extensions/skills/story/SKILL.md", (self.target / name).read_text(encoding="utf-8"))


class BadInputWritesNothing(PublishCase):
    def assert_refused(self, needle: str) -> None:
        before = self.snapshot()
        result = self.install()
        self.assertEqual("preflight_failed", result.status)
        self.assertTrue(any(needle in p for p in result.problems), result.problems)
        self.assertEqual(before, self.snapshot(), "输入有问题却写了目标")

    def test_a_dry_run_only_plans(self) -> None:
        before = self.snapshot()
        result = self.install(dry_run=True)
        self.assertEqual("planned", result.status)
        self.assertIn("materialize host entries", result.planned)
        self.assertEqual(before, self.snapshot())

    def test_an_entry_file_with_content_of_its_own(self) -> None:
        """入口文件里有 Framework 生成之外的内容：物化会整份重写它，写前就停。"""
        claude = self.target / "CLAUDE.md"
        claude.write_text(claude.read_text(encoding="utf-8") + "\n## 我们自己的约定\n", encoding="utf-8")
        self.assert_refused("CLAUDE.md")

    def test_a_stray_story_ext_zone_without_an_installed_section(self) -> None:
        """目标上没装旧版扩展，却有 story-ext 标记：认不出是谁的东西，不当作旧扩展段撤掉。"""
        claude = self.target / "CLAUDE.md"
        claude.write_text(claude.read_text(encoding="utf-8") + "\n<!-- story-ext:begin -->\nx\n", encoding="utf-8")
        self.assert_refused("CLAUDE.md")


class TheWriteFaceIsExact(PublishCase):
    def test_a_second_run_leaves_the_same_bytes(self) -> None:
        self.assertEqual("installed", self.install().status)
        first = self.snapshot()
        self.assertEqual("installed", self.install().status)
        self.assertEqual(first, self.snapshot())

    def test_the_extension_directory_is_replaced_whole(self) -> None:
        """源里没有的旧文件、旧运行态都退出；同名的文件与目录两个方向互换都装得上。"""
        self.assertEqual("installed", self.install().status)
        ext = self.target / "doc" / "extensions"
        (ext / "hooks" / "retired").mkdir(parents=True)
        (ext / "hooks" / "retired" / "old.mjs").write_text("gone", encoding="utf-8")
        (ext / "adapt").mkdir()
        (ext / "adapt" / "old.json").write_text("{}", encoding="utf-8")
        (ext / "asset").write_text("旧版是文件", encoding="utf-8")
        (ext / "sheet" / "inner").mkdir(parents=True)
        (ext / "sheet" / "inner" / "old.md").write_text("旧版是目录", encoding="utf-8")
        (self.source / "asset").mkdir()
        (self.source / "asset" / "new.md").write_text("新版是目录", encoding="utf-8")
        (self.source / "sheet").write_text("新版是文件", encoding="utf-8")

        result = self.install()
        self.assertEqual("installed", result.status, result.problems)
        for gone in ("hooks/retired", "adapt"):
            self.assertFalse((ext / gone).exists(), f"{gone} 没随整体替换退出")
        self.assertEqual("新版是目录", (ext / "asset" / "new.md").read_text(encoding="utf-8"))
        self.assertEqual("新版是文件", (ext / "sheet").read_text(encoding="utf-8"))
        self.assertEqual(sorted(pub.enumerate_source(self.source)), sorted(pub.enumerate_source(ext)))

    def test_the_entries_match_what_the_installed_adapt_materializes(self) -> None:
        """同一份扩展、同一个 Framework：维护安装与装好的 adapt 物化出的宿主入口逐字节相同。"""
        other = self.root / "by-adapt"
        shutil.copytree(self.target, other, ignore=shutil.ignore_patterns("framework"))
        link_framework(other)
        self.assertEqual("installed", self.install().status)
        git_init_excluding_framework(other)
        for cmd in (["add", "-A"], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "b"]):
            subprocess.run(["git", "-C", str(other), *cmd], check=True, capture_output=True)
        scan = self.target / "doc/extensions/skills/story-adaptation/scripts/adapt-scan.mjs"
        proc = subprocess.run(["node", str(scan), "--apply", "--target", str(other)],
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, proc.returncode, proc.stderr)
        for rel in (*ENTRY_FILES, ".claude/commands/story.md", ".codex/skills/story-adaptation/SKILL.md"):
            self.assertEqual((other / rel).read_bytes(), (self.target / rel).read_bytes(), rel)

    def test_a_write_failure_reports_what_was_actually_done(self) -> None:
        """物化中途写不进去：报失败，列出实际完成的写入，不留安装日志。"""
        claude = self.target / "CLAUDE.md"
        claude.chmod(stat.S_IREAD)
        self.addCleanup(claude.chmod, stat.S_IWRITE | stat.S_IREAD)
        result = self.install()
        self.assertEqual("write_failed", result.status, result.problems)
        self.assertEqual(["materialize host entries"], result.failed)
        self.assertTrue(result.problems)
        for rel in result.completed:
            self.assertTrue((self.target / rel).exists(), rel)
        self.assertEqual([], [p for p in self.root.rglob("install-*")], "留下了安装日志")


class APublishTargetInGitMustBeClean(PublishCase):
    def test_uncommitted_work_stops_the_publish(self) -> None:
        self.commit()
        (self.target / "01-Product.ets").write_text("人改了没提交", encoding="utf-8")
        before = self.snapshot()
        code, result = self.cli()
        self.assertEqual((2, "preflight_failed"), (code, result["status"]))
        self.assertTrue(any("没提交的改动" in p for p in result["problems"]))
        self.assertEqual(before, self.snapshot())

    def test_a_failed_git_query_stops_the_publish(self) -> None:
        """在不在仓里、状态两条查询，任一失败都不装，目标不写。"""
        self.commit()
        real = subprocess.run
        for word in ("rev-parse", "status"):
            with self.subTest(word):
                def failing(cmd, *a, _word=word, **k):
                    if cmd[:1] == ["git"] and _word in cmd:
                        return subprocess.CompletedProcess(cmd, 128, "", "fatal: 模拟查询失败")
                    return real(cmd, *a, **k)

                before = self.snapshot()
                with mock.patch.object(pub.subprocess, "run", failing), \
                        mock.patch("sys.stdout"), mock.patch("sys.stderr"):
                    code = pub.main(["--source", str(self.source), "--target", str(self.target)])
                self.assertEqual(2, code)
                self.assertEqual(before, self.snapshot())

    def test_a_target_outside_git_is_not_published(self) -> None:
        """命令行只用于发布 git 里的 demo：拿不到确定的 git 结果就不装。"""
        with mock.patch.object(pub.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 128, "", "not a git repository")):
            with self.assertRaises(pub.InputError):
                pub.git_dirty(self.target)

    def test_a_clean_target_publishes(self) -> None:
        self.commit()
        code, result = self.cli()
        self.assertEqual((0, "installed"), (code, result["status"]))


if __name__ == "__main__":
    unittest.main()
