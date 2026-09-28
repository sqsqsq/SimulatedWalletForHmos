"""统一安装动作（publish_to_demo）：同一动作服务开发 template 与发布 demo。

锁四件：源集合按当前字节取、排除运行态；预检有问题一个字节不写；写入面只有扩展目录、登记入口与
入口标记区；中途失败时凭安装清单能回到原字节，清单证明不了的现场如实留成冲突。
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


def sha(path: Path) -> str | None:
    return pub.sha256(path.read_bytes()) if path.is_file() else None


class PublishCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.evidence = self.root / "evidence"
        self.source = self.root / "src"
        shutil.copytree(SOURCE, self.source, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        self.target = self.root / "consumer"
        self.target.mkdir()
        (self.target / "framework.config.json").write_text(json.dumps({"project_name": "C"}), encoding="utf-8")
        (self.target / "AGENTS.md").write_text(ENTRY, encoding="utf-8")
        (self.target / "CLAUDE.md").write_text(ENTRY, encoding="utf-8")

    def install(self, **kw) -> pub.InstallResult:
        return pub.install_extension(self.source, self.target, pub.manifest_bridges(self.source),
                                     evidence_root=self.evidence, **kw)

    def snapshot(self) -> dict[str, bytes]:
        return {p.relative_to(self.target).as_posix(): p.read_bytes()
                for p in sorted(self.target.rglob("*")) if p.is_file() and ".git" not in p.parts}

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.target), *args], capture_output=True, check=True)

    def commit(self, message: str) -> None:
        if not (self.target / ".git").exists():
            self.git("init", "-q")
        self.git("add", "-A")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", message)


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

    def test_everything_in_the_source_lands_including_its_knowledge(self) -> None:
        self.assertEqual("installed", self.install().status)
        ext = self.target / "doc" / "extensions"
        for rel in pub.enumerate_source(self.source):
            self.assertEqual((self.source / rel).read_bytes(), (ext / rel).read_bytes(), rel)
        for bridge in pub.manifest_bridges(self.source):
            self.assertEqual(bridge.source.read_bytes(), (self.target / bridge.target).read_bytes())


class PreflightProblemsWriteNothing(PublishCase):
    def assert_refused(self, needle: str) -> None:
        before = self.snapshot()
        result = self.install()
        self.assertEqual("preflight_failed", result.status)
        self.assertTrue(any(needle in p for p in result.problems), result.problems)
        self.assertEqual(before, self.snapshot(), "预检没过却写了目标")
        self.assertFalse(self.evidence.exists(), "预检没过却落了安装清单")

    def test_a_dry_run_only_plans(self) -> None:
        before = self.snapshot()
        result = self.install(dry_run=True)
        self.assertEqual("planned", result.status)
        self.assertTrue(result.planned)
        self.assertEqual(before, self.snapshot())
        self.assertIsNone(result.manifest_path)

    def test_a_missing_bridge_source(self) -> None:
        (self.source / "bridges" / "cac-command-story.md").unlink()
        self.assert_refused("入口源")

    def test_broken_or_repeated_markers(self) -> None:
        (self.target / "CLAUDE.md").write_text(ENTRY + f"\n{pub.BEGIN}\nx\n", encoding="utf-8")
        self.assert_refused("不成对")
        (self.target / "CLAUDE.md").write_text(ENTRY + f"\n{pub.BEGIN}\n{pub.END}\n{pub.BEGIN}\n{pub.END}\n",
                                               encoding="utf-8")
        self.assert_refused("重复")

    def test_an_unreadable_target_config(self) -> None:
        (self.target / "framework.config.json").write_text("{ not json", encoding="utf-8")
        self.assert_refused("目标配置读不出")

    def test_uncommitted_work_on_the_write_face(self) -> None:
        self.commit("baseline")
        (self.target / "AGENTS.md").write_text(ENTRY + "人改了没提交\n", encoding="utf-8")
        self.assert_refused("没提交的修改")


class TheWriteFaceIsExact(PublishCase):
    def test_a_second_run_changes_nothing(self) -> None:
        self.assertEqual("installed", self.install().status)
        again = self.install()
        self.assertEqual(("installed", []), (again.status, again.completed))

    def test_a_file_the_source_dropped_leaves_and_runtime_state_stays(self) -> None:
        ext = self.target / "doc" / "extensions"
        (ext / "hooks" / "retired").mkdir(parents=True)
        (ext / "hooks" / "retired" / "old.mjs").write_text("gone", encoding="utf-8")
        (ext / "hooks" / "__pycache__").mkdir(parents=True)
        (ext / "hooks" / "__pycache__" / "x.pyc").write_text("rt", encoding="utf-8")
        result = self.install()
        self.assertIn("doc/extensions/hooks/retired/old.mjs", result.completed)
        self.assertFalse((ext / "hooks" / "retired").exists(), "删空的目录没收拢")
        self.assertTrue((ext / "hooks" / "__pycache__" / "x.pyc").is_file(), "目标的运行态被当旧文件删了")

    def test_the_zone_is_rendered_exactly_as_adapt_renders_it(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        other = self.root / "by-adapt"
        shutil.copytree(self.target, other)
        link_harness_yaml(other)
        subprocess.run(["git", "-C", str(other), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(other), "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(other), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "b"],
                       check=True, capture_output=True)
        proc = subprocess.run(["node", str(self.source / "skills/story-adaptation/scripts/adapt-scan.mjs"),
                               "--apply", "--target", str(other)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual("installed", self.install().status)
        for name in pub.ENTRIES:
            self.assertEqual((other / name).read_bytes(), (self.target / name).read_bytes(), name)
        self.assertIn("原有的一句话", (self.target / "AGENTS.md").read_text(encoding="utf-8"), "区外内容被动了")


def recover(manifest_path: Path) -> list[str]:
    """维护者按安装清单与恢复表（分册 04 §1.3）恢复；返回冲突路径。"""
    record = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    target = Path(record["target"])
    conflicts = []
    for item in record["items"]:
        path = target / item["path"]
        current = sha(path)
        before_path = Path(item["before_path"]) if item["before_path"] else None
        if current == item["before_sha256"]:
            continue
        if item["operation"] == "replace" and current == item["desired_sha256"] and before_path:
            path.write_bytes(before_path.read_bytes())
        elif item["operation"] == "delete" and current is None and before_path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(before_path.read_bytes())
        elif item["operation"] == "add" and current == item["desired_sha256"]:
            path.unlink()
        else:
            conflicts.append(item["path"])
    return conflicts


class AnInterruptedPublishCanBeUndone(PublishCase):
    """demo 已有上一版、已提交；本次安装在第 N 个文件处断掉，凭清单回到原字节。"""

    def setUp(self) -> None:
        super().setUp()
        self.assertEqual("installed", self.install().status)
        ext = self.target / "doc" / "extensions"
        (ext / "hooks" / "retired.mjs").write_text("上一版有、这一版没有", encoding="utf-8")
        skill = self.source / "skills" / "story" / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\n这一版改的一行。\n", encoding="utf-8")
        (self.source / "hooks" / "shared" / "added.mjs").write_text("export const y = 2;\n", encoding="utf-8")
        self.commit("上一版已发布")
        self.baseline = self.snapshot()

    def interrupted(self, operation: str) -> pub.InstallResult:
        """第一个 `operation` 类操作落盘之后、登记完成之前进程断掉。"""
        real_write, real_unlink = pub._write_file, Path.unlink
        target = self.target.resolve()
        state = {"fired": False}

        def maybe_stop(kind: str) -> None:
            if kind == operation and not state["fired"]:
                state["fired"] = True
                raise OSError("模拟中断")

        def write(path, data, item):
            kind = "add" if item["before_sha256"] is None else "replace"
            real_write(path, data, item)
            maybe_stop(kind)

        def unlink(path, *a, **k):
            real_unlink(path, *a, **k)
            if Path(path).resolve().is_relative_to(target):
                maybe_stop("delete")

        with mock.patch.object(pub, "_write_file", write), mock.patch.object(Path, "unlink", unlink):
            result = self.install()
        self.assertEqual("write_failed", result.status)
        return result

    def test_each_kind_of_interruption_recovers_to_the_original_bytes(self) -> None:
        for operation in ("replace", "delete", "add"):
            with self.subTest(operation):
                result = self.interrupted(operation)
                self.assertNotEqual(self.baseline, self.snapshot(), "中断前一个文件都没写，测不出恢复")
                again = self.install()
                self.assertEqual("preflight_failed", again.status, "恢复前再次发布没被脏面拦下")
                self.assertEqual([], recover(Path(result.manifest_path)))
                self.assertEqual(self.baseline, self.snapshot(), "没回到安装前的原字节")

    def test_a_file_edited_after_the_interruption_is_kept_as_a_conflict(self) -> None:
        result = self.interrupted("add")
        record = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
        done = next(i for i in record["items"]
                    if i["desired_sha256"] and sha(self.target / i["path"]) == i["desired_sha256"])
        edited = self.target / done["path"]
        edited.write_text("中断后人又改了", encoding="utf-8")
        conflicts = recover(Path(result.manifest_path))
        self.assertIn(done["path"], conflicts)
        self.assertEqual("中断后人又改了", edited.read_text(encoding="utf-8"))

    def test_a_source_that_changes_mid_install_stops_it(self) -> None:
        real_write = pub._write_file
        touched = {"done": False}

        def write(path, data, item):
            if not touched["done"]:
                touched["done"] = True
                later = self.source / "skills" / "story" / "SKILL.md"
                later.write_text("安装途中被改了", encoding="utf-8")
            return real_write(path, data, item)

        with mock.patch.object(pub, "_write_file", write):
            result = self.install()
        self.assertEqual("write_failed", result.status)
        record = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
        self.assertTrue(any("源在安装过程中变了" in (i["error"] or "") for i in record["items"]))


if __name__ == "__main__":
    unittest.main()
