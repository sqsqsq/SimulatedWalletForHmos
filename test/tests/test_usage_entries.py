"""使用记录的入口接线：正常产品入口被执行就采集，测试不手工调用记录器垫数据。

- Story 命令（init/round 记使用，update 起手与开轮为起点、关轮结算、撤回终止，status 只对账）；
- spec 作者任务包与 story-build 写作入口是本轮工作的起点；
- 真实 harness-runner 触发扩展 pre_phase：未建 Story 流程的直接 Coding 起手也登记，名称待补由 post_check 提醒，
  补齐后冻结；pre_phase 不往审查提示里放统计内容。
"""
from __future__ import annotations

import _winapi
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_story_update import NOTES, UpdateCase  # noqa: E402
from test_story_build import BUILD, FEATURE, StoryBuildCase  # noqa: E402
from ext_workspace import DEV_EXT  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DEMO = REPO / "demo"


def usage(root: Path) -> dict:
    return json.loads((root / "doc" / "usage.json").read_text(encoding="utf-8"))


class StoryCommandsRecordUse(UpdateCase):
    def steps(self) -> dict:
        return usage(self.root)["requirements"][FEATURE]["steps"]

    def test_the_story_flow_walk_already_recorded_story_use(self) -> None:
        self.assertIn("story", self.steps(), "init/round 走过了却没记 story 的使用")
        self.assertIsNone(usage(self.root)["requirements"][FEATURE]["name"], "没有初始化输入却填了名称")

    def test_an_update_round_is_timed_from_opening_to_closing(self) -> None:
        rid = self.update()["update"]
        s = self.steps()["story update"]
        self.assertTrue(s["start"] and s["spent"] == 0, s)
        (self.updates / rid / "update-notes.md").write_text(NOTES, encoding="utf-8")
        out = self.update("--action", "close")
        self.assertEqual("closed", out.get("status"), out)
        s = self.steps()["story update"]
        self.assertEqual((True, None), (s["completed"], s["start"]))
        self.assertIsInstance(s["spent"], int)
        before = (self.root / "doc" / "usage.json").read_bytes()
        self.assertTrue(self.update("--action", "status").get("success"))
        self.assertEqual(before, (self.root / "doc" / "usage.json").read_bytes(), "对账把已结算的一轮又算了一遍")

    def test_a_restore_ends_the_round_without_completing_it(self) -> None:
        self.update()
        self.assertEqual("restored", self.update("--action", "restore")["status"])
        s = self.steps()["story update"]
        self.assertEqual((False, None), (s["completed"], s["start"]))
        self.assertIsInstance(s["spent"], int)

    def test_a_broken_record_does_not_undo_the_business_result(self) -> None:
        record = self.root / "doc" / "usage.json"
        record.write_text("{ 坏了", encoding="utf-8")
        out = self.update()
        self.assertTrue(out.get("success"), out)
        self.assertTrue(out.get("update"), "业务没开成轮")
        self.assertTrue(any("不是合法 JSON" in e for e in out.get("usage_errors", [])), out)
        self.assertEqual("{ 坏了", record.read_text(encoding="utf-8"))

    def test_a_lock_that_cannot_open_is_a_record_error_and_a_later_entry_catches_up(self) -> None:
        record = self.root / "doc" / "usage.json"
        lock = record.with_name("usage.json.lock")
        before = record.read_bytes()
        os.chmod(lock, stat.S_IREAD)
        try:
            out = self.update()
        finally:
            os.chmod(lock, stat.S_IREAD | stat.S_IWRITE)
        self.assertTrue(out.get("success"), out)
        self.assertTrue(out.get("update"), "业务没开成轮")
        self.assertTrue(any("usage.json.lock" in e for e in out.get("usage_errors", [])), out)
        self.assertEqual(before, record.read_bytes(), "记录失败却改了原文件")
        (self.updates / out["update"] / "update-notes.md").write_text(NOTES, encoding="utf-8")
        closed = self.update("--action", "close")
        self.assertNotIn("usage_errors", closed)
        s = self.steps()["story update"]
        self.assertEqual((True, None), (s["completed"], s["spent"]), "缺了起点的一轮被编出了耗时")


class StatusCreatesNothing(unittest.TestCase):
    def test_status_on_an_unrecorded_requirement_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "doc" / "features" / "AR7").mkdir(parents=True)
            subprocess.run([sys.executable, str(DEV_EXT / "skills/story/scripts/core/story_flow.py"), "status",
                            "--feature", "AR7", "--project-root", str(root)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
            self.assertEqual([], [p.name for p in (root / "doc").iterdir() if p.name != "features"])


class WorkEntriesBegin(StoryBuildCase):
    def steps(self) -> dict:
        return usage(self.root)["requirements"][FEATURE]["steps"]

    def test_the_writing_entry_starts_the_story_round_and_check_does_not(self) -> None:
        self.init_audit()
        self.assertEqual(0, self.run_build("skeleton").returncode)
        start = self.steps()["story"]["start"]
        self.assertTrue(start, "写作入口没记起点")
        self.run_build("check")
        self.run_build("skeleton")
        self.assertEqual(start, self.steps()["story"]["start"], "同轮重复进入覆盖了起点")

    def test_the_spec_author_package_starts_the_spec_round(self) -> None:
        subprocess.run(["node", str(DEV_EXT / "hooks/spec/author.mjs"), "--feature", FEATURE], cwd=self.root,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertTrue(self.steps()["spec"]["start"], "作者任务包没记 spec 起点")


def demo_toolchain() -> dict | None:
    """本机 DevEco 工具链：取 demo 的个人配置 `framework.local.json`（不入库）里的 toolchain，没配返回 None。"""
    try:
        return json.loads((DEMO / "framework.local.json").read_text(encoding="utf-8")).get("toolchain")
    except (OSError, ValueError):
        return None


@unittest.skipUnless((DEMO / "framework" / "harness" / "node_modules" / "ts-node").is_dir(), "没有 demo harness 依赖")
@unittest.skipUnless(demo_toolchain(), "demo/framework.local.json 没配 DevEco 工具链：coding 等阶段过不了 harness 前置")
class TheRealHarnessRecordsUse(unittest.TestCase):
    """隔离工程：framework 副本（依赖只读链接 demo）、各宿主入口产物、开发源扩展，工具链沿用 demo 的个人配置。"""

    FEATURE = "AR90123"

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        root = cls.root = Path(cls._tmp.name) / "proj"
        shutil.copytree(DEMO / "framework", root / "framework",
                        ignore=shutil.ignore_patterns("node_modules", "state", "reports"))
        _winapi.CreateJunction(str(DEMO / "framework" / "harness" / "node_modules"),
                               str(root / "framework" / "harness" / "node_modules"))
        shutil.copy2(DEMO / "framework.config.json", root / "framework.config.json")
        for name in (".agents", ".cac", ".claude", ".codex", ".cursor", ".opencode"):
            shutil.copytree(DEMO / name, root / name)
        for name in ("AGENTS.md", "CLAUDE.md"):
            shutil.copy2(DEMO / name, root / name)
        shutil.copytree(DEV_EXT, root / "doc" / "extensions")
        (root / "framework.local.json").write_text(json.dumps({
            "schema_version": "1.0", "agent_adapter": "opencode", "toolchain": demo_toolchain()}), encoding="utf-8")
        cls.fr = root / "doc" / "features" / cls.FEATURE
        cls.fr.mkdir(parents=True)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.root / "framework" / "harness" / "node_modules", ignore_errors=True)
        cls._tmp.cleanup()

    def harness(self, phase: str) -> subprocess.CompletedProcess:
        return subprocess.run(["node", "node_modules/ts-node/dist/bin.js", "--transpile-only", "harness-runner.ts",
                               "--phase", phase, "--feature", self.FEATURE], cwd=self.root / "framework" / "harness",
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)

    def test_direct_coding_then_review_records_use_and_freezes_the_name_once(self) -> None:
        proc = self.harness("coding")
        node = usage(self.root)["requirements"][self.FEATURE]
        self.assertIn("coding", node["steps"], proc.stdout[-1500:])
        coding = node["steps"]["coding"]
        self.assertEqual((None, None, None), (node["name"], coding["start"], coding["spent"]),
                         "检查时刻冒充了开工，或没有输入却填了名称")
        text = (self.fr / "coding" / "reports" / "merged-report.md").read_text(encoding="utf-8")
        self.assertIn("使用记录待补", text, "待补初始化没送到本阶段报告")
        self.assertIn(".usage-input.json", text, "提醒没给输入位置")
        self.assertNotIn('"spent"', text, "统计内容进了阶段报告")
        checks = json.loads((self.fr / "coding" / "reports" / "script-report.json").read_text(encoding="utf-8"))["checks"]
        pending = [c for c in checks if "使用记录待补" in str(c.get("details"))]
        self.assertEqual(["MINOR"], [c["severity"] for c in pending], "待补提醒的级别会改阶段结论")
        (self.fr / ".usage-input.json").write_text(json.dumps(
            {"requirement": self.FEATURE, "name": "通知订阅设置", "version": "4.2.0"}, ensure_ascii=False), encoding="utf-8")
        self.harness("review")
        node = usage(self.root)["requirements"][self.FEATURE]
        self.assertEqual(("通知订阅设置", "4.2.0"), (node["name"], node["version"]))
        self.assertIn("review", node["steps"])
        self.assertFalse((self.fr / ".usage-input.json").exists())


if __name__ == "__main__":
    unittest.main()
