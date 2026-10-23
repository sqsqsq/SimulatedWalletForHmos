"""使用记录的入口接线：正常产品入口被执行就采集，测试不手工调用记录器垫数据。

- Story 命令（init 建身份与节点，其余命令刷新；update 一轮从开轮到关轮计时，撤回不计，status 不建记录）；
- spec 作者任务包与 story-build 写作入口不再是计时起点，不写 usage；
- 真实 harness-runner 触发扩展 pre_phase：未建 Story 流程的直接 Coding 起手也建身份与节点，
  自报身份由下一次阶段检查接收；pre_phase 不往审查提示里放统计内容。
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
    def node(self) -> dict:
        stamp = (self.feature_root / ".usage-id").read_text(encoding="utf-8").strip()
        return usage(self.root)["requirements"][f"{FEATURE}-{stamp}"]

    def test_init_made_the_identity_and_the_node(self) -> None:
        node = self.node()
        self.assertEqual((None, None), (node["agent"], node["model"]), "没有自报却填了身份")
        self.assertEqual({"ext", "fw", "agent", "model", "steps"}, set(node))

    def test_an_update_round_is_timed_from_opening_to_closing(self) -> None:
        rid = self.update()["update"]
        self.assertNotIn("story update", self.node()["steps"], "没收口就出了行")
        (self.updates / rid / "update-notes.md").write_text(NOTES, encoding="utf-8")
        out = self.update("--action", "close")
        self.assertEqual("closed", out.get("status"), out)
        row = self.node()["steps"]["story update"]
        self.assertEqual(1, row["rounds"])
        self.assertIsInstance(row["spent"], int)
        before = (self.root / "doc" / "usage.json").read_bytes()
        self.assertTrue(self.update("--action", "status").get("success"))
        self.assertEqual(before, (self.root / "doc" / "usage.json").read_bytes(), "刷新把已结算的一轮又算了一遍")

    def test_a_restore_ends_the_round_without_completing_it(self) -> None:
        self.update()
        self.assertEqual("restored", self.update("--action", "restore")["status"])
        self.assertNotIn("story update", self.node()["steps"])

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
        row = self.node()["steps"]["story update"]
        self.assertEqual(1, row["rounds"], "开轮时没记上，收口轮数就丢了")
        self.assertIsInstance(row["spent"], int, "耗时由原生记录的开轮与收口时刻得出")


class StatusCreatesNothing(unittest.TestCase):
    def test_status_on_an_unrecorded_requirement_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "doc" / "features" / "AR7").mkdir(parents=True)
            subprocess.run([sys.executable, str(DEV_EXT / "skills/story/scripts/core/story_flow.py"), "status",
                            "--feature", "AR7", "--project-root", str(root)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
            self.assertEqual([], [p.name for p in (root / "doc").iterdir() if p.name != "features"])


class WritingEntriesDoNotTime(StoryBuildCase):
    """作者任务包与写作入口不是 V5 的计时真源：跑它们不动使用记录。"""

    def test_skeleton_and_the_spec_author_package_leave_usage_alone(self) -> None:
        self.init_audit()
        self.assertEqual(0, self.run_build("skeleton").returncode)     # 起手夹具在这里走 story init，建了节点
        record = self.root / "doc" / "usage.json"
        before = record.read_bytes()
        self.assertEqual(0, self.run_build("skeleton").returncode)
        subprocess.run(["node", str(DEV_EXT / "hooks/spec/author.mjs"), "--feature", FEATURE], cwd=self.root,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(before, record.read_bytes(), "写作入口或作者包动了使用记录")


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

    def test_direct_coding_creates_the_identity_and_a_later_phase_takes_the_self_report(self) -> None:
        proc = self.harness("coding")
        stamp = (self.fr / ".usage-id").read_text(encoding="utf-8").strip()
        node = usage(self.root)["requirements"][f"{self.FEATURE}-{stamp}"]
        self.assertEqual((None, None), (node["agent"], node["model"]), proc.stdout[-1500:])
        text = (self.fr / "coding" / "reports" / "merged-report.md").read_text(encoding="utf-8")
        self.assertNotIn('"spent"', text, "统计内容进了阶段报告")
        (self.fr / ".usage-input.json").write_text(json.dumps({"agent": "opencode", "model": "m1"}), encoding="utf-8")
        self.harness("review")
        node = usage(self.root)["requirements"][f"{self.FEATURE}-{stamp}"]
        self.assertEqual(("opencode", "m1"), (node["agent"], node["model"]))
        self.assertFalse((self.fr / ".usage-input.json").exists())


if __name__ == "__main__":
    unittest.main()
