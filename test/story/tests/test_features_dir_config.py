# -*- coding: utf-8 -*-
"""features_dir 配置的归一真源——JS 与 Python 必须解析出同一个 feature 目录。

公共入口（paths.mjs 的 featuresDir）与 Python 侧（import_sources.features_dir）
同一语义：只有字符串且 trim 后非空才采用配置值，其余一律回默认 doc/features。
合并前两个 JS 调用方各自实现过这层归一，合并时只留 `??` 会丢掉它——空串指向
工程根、两端空白原样进路径，Python 建的流程文件 JS 就找不到了，
Spec hook 还会把「文件不在」误读成「Spec 尚未生成」。

这里黑盒跑真实 story-build（node 子进程）作判别：夹具只在**预期目录**放
流程台账，JS 归一到别处时台账判据先红（台账缺），归一对了才会走到
「读不到 <预期目录>/AR/story.md」。另用 Python 先建工作区，JS 必须读到
同一个（trim 后的）目录。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BUILD = (REPO_ROOT / "doc" / "extensions" / "skills" / "story"
         / "scripts" / "core" / "story-build.mjs")
FLOW = (REPO_ROOT / "doc" / "extensions" / "skills" / "story"
        / "scripts" / "core" / "story_flow.py")
FEATURE = "B01FEAT"
LEDGERS = ("decisions.json", "copyedit.md")


class FeaturesDirConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.node = shutil.which("node")
        if self.node is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def write_config(self, value) -> None:
        (self.root / "framework.config.json").write_text(
            json.dumps({"paths": {"features_dir": value}}, ensure_ascii=False),
            encoding="utf-8")

    def put_ledgers(self, rel: str) -> None:
        """只在预期解析到的 feature 里放台账：台账红 = JS 没归一到这个目录。"""
        story_src = self.root / rel / FEATURE / "AR" / "story-src"
        story_src.mkdir(parents=True, exist_ok=True)
        (story_src / LEDGERS[0]).write_text("[]", encoding="utf-8")
        (story_src / LEDGERS[1]).write_text("", encoding="utf-8")

    def check_missing_story_path(self) -> str:
        proc = subprocess.run(
            [self.node, str(BUILD), "check", "--feature", FEATURE,
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=90)
        out = (proc.stderr + proc.stdout).strip()
        self.assertNotEqual(proc.returncode, 0, out)
        self.assertNotIn("台账缺", out, f"JS 没有读到预期目录里的台账：\n{out}")
        self.assertIn("读不到", out, out)
        return out

    def test_trimmed_values_reach_the_same_feature(self) -> None:
        for value in ("feat dir", " feat dir "):
            with self.subTest(value=value):
                self.write_config(value)
                self.put_ledgers("feat dir")
                self.assertIn(
                    str(self.root / "feat dir" / FEATURE / "AR" / "story.md"),
                    self.check_missing_story_path())

    def test_blank_and_non_string_values_fall_back_to_default(self) -> None:
        for value in ("", "   ", 123, None):
            with self.subTest(value=repr(value)):
                self.write_config(value)
                self.put_ledgers("doc/features")
                self.assertIn(
                    str(self.root / "doc" / "features" / FEATURE / "AR" / "story.md"),
                    self.check_missing_story_path())

    def test_missing_config_falls_back_to_default(self) -> None:
        self.put_ledgers("doc/features")
        self.assertIn(
            str(self.root / "doc" / "features" / FEATURE / "AR" / "story.md"),
            self.check_missing_story_path())

    def test_js_reads_the_feature_python_created(self) -> None:
        """Python（import_sources 语义）先建，JS 必须在同一个 trim 后的目录读到。"""
        self.write_config(" feat dir ")
        proc = subprocess.run(
            [sys.executable, str(FLOW), "init", "--feature", FEATURE,
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=90)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse((self.root / " feat dir ").exists(),
                         "带边缘空格的目录不该被创建")
        self.assertTrue((self.root / "feat dir" / FEATURE / "AR" / "design.md").is_file())
        self.put_ledgers("feat dir")
        self.assertIn(
            str(self.root / "feat dir" / FEATURE / "AR" / "story.md"),
            self.check_missing_story_path())


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False).result.wasSuccessful() else 1)
