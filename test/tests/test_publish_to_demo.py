"""统一安装动作（publish_to_demo）：测试装一次性 template，发布时装 demo。

锁四件：源集合按当前字节取、排除运行态；输入读不出或标记区坏了就不写；写入面只有扩展目录、登记入口与
入口标记区；目标在 git 里时有改动或查询失败就不装。失败只如实报告实际完成项，还原交给 git 或重建 template。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ext_workspace import link_harness_yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = REPO_ROOT / "extensions"
sys.path.insert(0, str(REPO_ROOT / "test" / "scripts"))
import publish_to_demo as pub  # noqa: E402

ENTRY = "# 工程\n\n## 实例扩展\n\n原有的一句话。\n\n## 其他\n\n收尾。\n"


class PublishCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.source = self.root / "src"
        shutil.copytree(SOURCE, self.source, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        self.target = self.root / "consumer"
        self.target.mkdir()
        (self.target / "framework.config.json").write_text(json.dumps({"project_name": "C"}), encoding="utf-8")
        (self.target / "AGENTS.md").write_text(ENTRY, encoding="utf-8")
        (self.target / "CLAUDE.md").write_text(ENTRY, encoding="utf-8")

    def install(self, **kw) -> pub.InstallResult:
        return pub.install_extension(self.source, self.target, pub.manifest_bridges(self.source), **kw)

    def snapshot(self) -> dict[str, bytes]:
        return {p.relative_to(self.target).as_posix(): p.read_bytes()
                for p in sorted(self.target.rglob("*")) if p.is_file() and ".git" not in p.parts}

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.target), *args], capture_output=True, check=True)

    def commit(self) -> None:
        self.git("init", "-q")
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

    def test_everything_in_the_source_lands_including_its_knowledge_and_six_entries(self) -> None:
        self.assertEqual("installed", self.install().status)
        ext = self.target / "doc" / "extensions"
        for rel in pub.enumerate_source(self.source):
            self.assertEqual((self.source / rel).read_bytes(), (ext / rel).read_bytes(), rel)
        bridges = pub.manifest_bridges(self.source)
        self.assertEqual(6, len(bridges))
        for bridge in bridges:
            self.assertEqual(bridge.source.read_bytes(), (self.target / bridge.target).read_bytes())


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
        self.assertTrue(result.planned)
        self.assertEqual(before, self.snapshot())

    def test_a_missing_bridge_source(self) -> None:
        (self.source / "bridges" / "cac-command-story.md").unlink()
        self.assert_refused("入口源读不出")

    def test_broken_or_repeated_markers(self) -> None:
        (self.target / "CLAUDE.md").write_text(ENTRY + f"\n{pub.BEGIN}\nx\n", encoding="utf-8")
        self.assert_refused("不成对")
        (self.target / "CLAUDE.md").write_text(ENTRY + f"\n{pub.BEGIN}\n{pub.END}\n{pub.BEGIN}\n{pub.END}\n",
                                               encoding="utf-8")
        self.assert_refused("重复")


class TheWriteFaceIsExact(PublishCase):
    def test_a_second_run_changes_nothing(self) -> None:
        self.assertEqual("installed", self.install().status)
        again = self.install()
        self.assertEqual(("installed", []), (again.status, again.completed))

    def test_a_file_the_source_dropped_leaves(self) -> None:
        ext = self.target / "doc" / "extensions"
        (ext / "hooks" / "retired").mkdir(parents=True)
        (ext / "hooks" / "retired" / "old.mjs").write_text("gone", encoding="utf-8")
        result = self.install()
        self.assertIn("doc/extensions/hooks/retired/old.mjs", result.completed)
        self.assertFalse((ext / "hooks" / "retired").exists(), "删空的目录没收拢")

    def test_the_zone_matches_what_the_installed_adapt_writes(self) -> None:
        """同一份扩展段，发布安装器与装好的 adapt 写进入口文件的结果逐字节相同；区外不动。"""
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        other = self.root / "by-adapt"
        shutil.copytree(self.target, other)
        self.assertEqual("installed", self.install().status)
        link_harness_yaml(self.target)
        for cmd in (["init", "-q"], ["add", "-A"], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "b"]):
            subprocess.run(["git", "-C", str(other), *cmd], check=True, capture_output=True)
        scan = self.target / "doc/extensions/skills/story-adaptation/scripts/adapt-scan.mjs"
        proc = subprocess.run(["node", str(scan), "--apply", "--target", str(other)],
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, proc.returncode, proc.stderr)
        for name in pub.ENTRIES:
            self.assertEqual((other / name).read_bytes(), (self.target / name).read_bytes(), name)
        self.assertIn("原有的一句话", (self.target / "AGENTS.md").read_text(encoding="utf-8"), "区外内容被动了")

    def test_a_write_failure_reports_what_was_actually_done(self) -> None:
        blocker = self.target / ".cac" / "commands" / "story.md"
        blocker.mkdir(parents=True)
        result = self.install()
        self.assertEqual("write_failed", result.status)
        self.assertEqual([".cac/commands/story.md"], result.failed)
        for rel in result.completed:
            self.assertTrue((self.target / rel).is_file(), rel)
        self.assertNotIn(".cac/commands/story.md", result.completed)
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
        self.commit()
        real = subprocess.run

        def failing(cmd, *a, **k):
            if cmd[:1] == ["git"] and "status" in cmd:
                return subprocess.CompletedProcess(cmd, 128, "", "fatal: 模拟查询失败")
            return real(cmd, *a, **k)

        with mock.patch.object(pub.subprocess, "run", failing):
            with self.assertRaises(pub.InputError):
                pub.git_dirty(self.target)

    def test_a_clean_target_publishes(self) -> None:
        self.commit()
        code, result = self.cli()
        self.assertEqual((0, "installed"), (code, result["status"]))


if __name__ == "__main__":
    unittest.main()
