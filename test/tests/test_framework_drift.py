"""framework 发布件漂移自查：同版本 0、版本差 1、读不出 2；同版本不同构建只报事实。"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "test" / "scripts" / "check_framework_drift.py"
sys.path.insert(0, str(SCRIPT.parent))
import check_framework_drift as drift  # noqa: E402


class DriftCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.repo = self.root / "repo"
        (self.repo / "framework").mkdir(parents=True)
        self.git("init", "-q")

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, check=True)

    def main_branch(self, text: str) -> str:
        (self.repo / drift.MANIFEST).write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "m")
        return "HEAD"

    def demo(self, text: str) -> Path:
        path = self.root / "demo-manifest.json"
        path.write_text(text, encoding="utf-8")
        return path

    def run_check(self, main_text: str, demo_text: str) -> tuple[int, dict]:
        try:
            return drift.compare(drift.read_ref(self.main_branch(main_text), self.repo),
                                 drift.read_file(self.demo(demo_text)))
        except drift.ReadError as exc:
            return 2, {"status": "read_failed", "error": str(exc)}

    @staticmethod
    def manifest(version: str | None, commit: str = "aaa") -> str:
        doc = {"schema_version": "1.0", "source_commit": commit}
        if version is not None:
            doc["version"] = version
        return json.dumps(doc)

    def test_same_version_and_build(self) -> None:
        code, result = self.run_check(self.manifest("3.0.0"), self.manifest("3.0.0"))
        self.assertEqual((0, "same_version"), (code, result["status"]))
        self.assertNotIn("note", result)

    def test_same_version_different_build_is_reported_as_a_fact(self) -> None:
        code, result = self.run_check(self.manifest("3.0.0", "aaa"), self.manifest("3.0.0", "bbb"))
        self.assertEqual(0, code)
        self.assertIn("不代表两侧文件一致", result["note"])
        self.assertEqual(("aaa", "bbb"), (result["main"]["source_commit"], result["demo"]["source_commit"]))

    def test_a_version_difference_points_at_the_integration_protocol(self) -> None:
        code, result = self.run_check(self.manifest("3.1.0"), self.manifest("3.0.0"))
        self.assertEqual((1, "version_differs"), (code, result["status"]))
        self.assertIn("接入协议", result["guide"])

    def test_read_failures_are_exit_two(self) -> None:
        cases = {
            "缺字段": (self.manifest(None), self.manifest("3.0.0")),
            "坏 JSON": (self.manifest("3.0.0"), "{ not json"),
        }
        for name, (main_text, demo_text) in cases.items():
            with self.subTest(name):
                code, result = self.run_check(main_text, demo_text)
                self.assertEqual((2, "read_failed"), (code, result["status"]))
        with self.subTest("demo 缺文件"):
            with self.assertRaises(drift.ReadError):
                drift.read_file(self.root / "nowhere.json")
        with self.subTest("git 读不出"):
            proc = subprocess.run([sys.executable, str(SCRIPT), "--ref", "no-such-ref-for-drift"],
                                  capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(2, proc.returncode, proc.stdout)
            self.assertEqual("read_failed", json.loads(proc.stdout)["status"])


if __name__ == "__main__":
    unittest.main()
