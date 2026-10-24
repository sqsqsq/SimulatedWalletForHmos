"""使用记录的入口接线：正常产品入口被执行就采集，测试不手工往运行态里垫起点。

- 开始工作的入口就是起点：Spec / Plan 的作者任务包 CLI 自动 begin（被导入的渲染函数不写），其余步骤跑共享的
  `usage.py --begin`；update 的 begin 暂存在运行态，prepare 开轮时移进 record 的 started_at，收口时算这一轮；
- Story 命令（init 沿用取材前 begin 建的身份，其余命令刷新；撤回不计，status 不建记录）；skeleton 等写作入口不计时；
- update 起点只在 record 存下同一个值之后才清暂存：读、写或清理失败都保留暂存并报出，重试照原值移交；
- 真实 harness-runner 的阶段检查不是开始工作：不建身份、不登记起点，也不往审查提示里放统计内容。
"""
from __future__ import annotations

import _winapi
import contextlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_story_update import NOTES, UpdateCase  # noqa: E402
from test_usage import CORE, USAGE  # noqa: E402
sys.path.insert(0, str(CORE))           # 进程内注入失败的用例要和产品入口用同一个记录器模块
from test_story_build import BUILD, FEATURE, StoryBuildCase  # noqa: E402
from ext_workspace import DEV_EXT  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DEMO = REPO / "demo"


def usage(root: Path) -> dict:
    return json.loads((root / "doc" / "usage.json").read_text(encoding="utf-8"))


class StoryCommandsRecordUse(UpdateCase):
    def before_init(self) -> None:
        self.begin("story")             # Skill 里 init 的第 ⓪ 步：取材之前

    def node(self) -> dict:
        stamp = (self.feature_root / ".usage-id").read_text(encoding="utf-8").strip()
        return usage(self.root)["requirements"][f"{FEATURE}-{stamp}"]

    def test_the_begin_before_init_made_the_identity_and_init_kept_it(self) -> None:
        node = self.node()
        self.assertEqual((None, None), (node["agent"], node["model"]), "没有自报却填了身份")
        self.assertEqual({"ext", "fw", "agent", "model", "steps"}, set(node))
        self.assertEqual(1, len(usage(self.root)["requirements"]), "init 另建了身份")

    def begin(self, step: str = "story update") -> None:
        """Skill 里 update 的第 ⓪ 步，原样。"""
        proc = subprocess.run([sys.executable, str(USAGE), "--project-root", str(self.root), "--feature", FEATURE,
                               "--begin", "--step", step], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=60)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def state(self) -> dict:
        path = self.root / "doc" / "features" / ".usage-state.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def test_an_update_round_runs_from_its_begin_to_closing(self) -> None:
        self.begin()
        stash = next(iter(self.state().values()))["starts"]["story update"]
        rid = self.update()["update"]
        record = json.loads((self.updates / rid / "record.json").read_text(encoding="utf-8"))
        self.assertEqual(stash, record["started_at"], "开轮没把开始时刻移进这一轮")
        self.assertLessEqual(record["started_at"][:19], record["opened_at"][:19], "开始晚于开轮")
        self.assertFalse(any("story update" in (s.get("starts") or {}) for s in self.state().values()),
                         "移进 record 之后运行态还留着一份")
        self.begin()                                       # 开着的轮次再跑一次：沿用原起点，不再暂存
        self.assertFalse(any("story update" in (s.get("starts") or {}) for s in self.state().values()))
        self.assertNotIn("story update", self.node()["steps"], "没收口就出了行")
        (self.updates / rid / "update-notes.md").write_text(NOTES, encoding="utf-8")
        out = self.update("--action", "close")
        self.assertEqual("closed", out.get("status"), out)
        self.assertTrue(out.get("next") and "下一步：" in out.get("action", ""), f"收口只报 closed，没给本轮下一步：{out}")
        row = self.node()["steps"]["story update"]
        self.assertEqual(1, row["rounds"])
        self.assertIsInstance(row["spent"], int)
        before = (self.root / "doc" / "usage.json").read_bytes()
        self.assertTrue(self.update("--action", "status").get("success"))
        self.assertEqual(before, (self.root / "doc" / "usage.json").read_bytes(), "刷新把已结算的一轮又算了一遍")

    def test_a_round_without_begin_counts_but_has_no_time(self) -> None:
        rid = self.update()["update"]
        (self.updates / rid / "update-notes.md").write_text(NOTES, encoding="utf-8")
        self.update("--action", "close")
        self.assertNotIn("started_at", self.record(rid), "没有 begin 却拿开轮时刻补了起点")
        self.assertEqual({"rounds": 1}, self.node()["steps"]["story update"], "没有开始记录却拿开轮时刻补了耗时")
        before = (self.root / "doc" / "usage.json").read_bytes()
        for _ in range(2):                  # 收口的记录动作再来：不加轮数、不加耗时
            subprocess.run([sys.executable, str(USAGE), "--project-root", str(self.root)],
                           input=json.dumps({"action": "close", "feature": FEATURE}), capture_output=True,
                           text=True, encoding="utf-8", timeout=60)
        self.assertEqual(before, (self.root / "doc" / "usage.json").read_bytes(), "重复收口多记了")

    # ---- 起点移交：record 存下同一个值才清暂存 ----

    def record(self, rid: str) -> dict:
        return json.loads((self.updates / rid / "record.json").read_text(encoding="utf-8"))

    def stash(self) -> str | None:
        return next(iter(self.state().values()), {}).get("starts", {}).get("story update")

    def update_in_process(self, *args: str, patch=None) -> dict:
        """进程内跑同一个 story_flow 入口，好往移交那一步注入一次失败。"""
        import story_flow  # noqa: PLC0415
        if "--action" not in args:
            args = ("--action", "prepare", *args)
        out = io.StringIO()
        argv = ["story_flow.py", "update", "--feature", FEATURE, "--project-root", str(self.root), *args]
        with unittest.mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(out), \
                (patch or contextlib.nullcontext()):
            story_flow.main()
        return json.loads([l for l in out.getvalue().splitlines() if l.startswith("{")][-1])

    def test_a_failed_read_keeps_the_start_and_a_retry_moves_the_same_value(self) -> None:
        import usage as recorder  # noqa: PLC0415
        self.begin()
        held = self.stash()
        out = self.update_in_process(patch=unittest.mock.patch.object(
            recorder, "update_start", side_effect=recorder.UsageError("运行态读不出（注入）")))
        self.assertTrue(out.get("success") and out.get("update"), out)
        self.assertIn("暂存保留", out.get("usage_error", ""), "读失败没报出来")
        self.assertNotIn("started_at", self.record(out["update"]))
        self.assertEqual(held, self.stash(), "没移成就清了暂存")
        again = self.update()                           # 重跑 prepare：续这一轮，照原值移交
        self.assertNotIn("usage_error", again)
        self.assertEqual(held, self.record(out["update"])["started_at"], "重试换成了别的时刻")
        self.assertIsNone(self.stash(), "移交后暂存还在")

    def test_a_record_that_cannot_be_written_keeps_the_start_until_closing(self) -> None:
        self.begin()
        held, real = self.stash(), Path.write_text

        def refuse(path, data, *a, **k):
            if path.name == "record.json" and '"started_at"' in data:
                raise OSError("磁盘写保护（注入）")
            return real(path, data, *a, **k)

        out = self.update_in_process(patch=unittest.mock.patch.object(Path, "write_text", refuse))
        self.assertIn("暂存保留", out.get("usage_error", ""))
        self.assertEqual(held, self.stash(), "record 没写成却清了暂存")
        (self.updates / out["update"] / "update-notes.md").write_text(NOTES, encoding="utf-8")
        closed = self.update("--action", "close")       # 收口前再移一次
        self.assertEqual("closed", closed.get("status"), closed)
        self.assertEqual(held, self.record(out["update"])["started_at"])
        self.assertIsNone(self.stash())
        self.assertIsInstance(self.node()["steps"]["story update"]["spent"], int)

    def test_a_cleanup_failure_after_moving_keeps_one_value(self) -> None:
        import usage as recorder  # noqa: PLC0415
        self.begin()
        held = self.stash()
        out = self.update_in_process(patch=unittest.mock.patch.object(
            recorder, "drop_update_start", side_effect=recorder.UsageError("运行态被占用（注入）")))
        self.assertIn("暂存保留", out.get("usage_error", ""))
        self.assertEqual((held, held), (self.record(out["update"])["started_at"], self.stash()))
        self.update()                                   # 续这一轮：record 已有起点，只清暂存
        self.assertEqual(held, self.record(out["update"])["started_at"], "清理重试改了已移交的值")
        self.assertIsNone(self.stash(), "重试后还剩两份")

    def test_a_start_that_cannot_move_by_closing_is_kept_and_not_carried_on(self) -> None:
        """收口时也没移成：记录动作不清这份暂存、报出来；下一轮 begin 不把它当成新一轮的起点。"""
        import usage as recorder  # noqa: PLC0415
        self.begin()
        held = self.stash()
        failing = unittest.mock.patch.object(recorder, "update_start",
                                             side_effect=recorder.UsageError("运行态读不出（注入）"))
        rid = self.update_in_process(patch=failing)["update"]
        (self.updates / rid / "update-notes.md").write_text(NOTES, encoding="utf-8")
        closed = self.update_in_process("--action", "close", patch=failing)
        self.assertEqual("closed", closed.get("status"), closed)
        self.assertIn("暂存保留", closed.get("usage_error", ""))
        self.assertEqual(held, self.stash(), "收口的记录动作清掉了还没移交的起点")
        self.assertEqual({"rounds": 1}, self.node()["steps"]["story update"])
        self.begin()
        self.assertNotEqual(held, self.stash(), "上一轮没移成的起点带进了新一轮")
        moment = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))  # noqa: E731
        self.assertGreaterEqual(moment(self.stash()), moment(self.record(rid)["closed_at"]))

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
        self.begin()
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
        self.assertIsInstance(row["spent"], int, "开始时刻已随开轮进了 record，收口照常得出耗时")
        self.assertFalse(any("story update" in (s.get("starts") or {}) for s in self.state().values()),
                         "开轮时没清掉的暂存，收口时也该清掉")


class StatusCreatesNothing(unittest.TestCase):
    def test_status_on_an_unrecorded_requirement_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "doc" / "features" / "AR7").mkdir(parents=True)
            subprocess.run([sys.executable, str(DEV_EXT / "skills/story/scripts/core/story_flow.py"), "status",
                            "--feature", "AR7", "--project-root", str(root)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
            self.assertEqual([], [p.name for p in (root / "doc").iterdir() if p.name != "features"])


class AuthorEntriesBeginTheirPhase(StoryBuildCase):
    """Spec / Plan 的作者任务包 CLI 是开始工作的入口：跑它就记起点，重跑保留最早的；
    skeleton 等写作入口与被导入的渲染函数不写使用记录。"""

    def starts(self) -> dict:
        path = self.root / "doc" / "features" / ".usage-state.json"
        st = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        return next(iter(st.values()), {}).get("starts", {})

    def author(self, phase: str) -> subprocess.CompletedProcess:
        return subprocess.run(["node", str(DEV_EXT / f"hooks/{phase}/author.mjs"), "--feature", FEATURE], cwd=self.root,
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)

    def test_the_task_package_cli_begins_and_rendering_alone_does_not(self) -> None:
        self.init_audit()
        self.assertEqual(0, self.run_build("skeleton").returncode)     # 起手夹具在这里走 story init，建了节点
        self.assertEqual(0, self.run_build("skeleton").returncode)
        self.assertFalse({"spec", "plan"} & set(self.starts()), "写作入口开始了阶段计时")
        for phase in ("spec", "plan"):        # 预检与独审装配会导入作者模块：导入本身不开始计时
            driver = "await import(process.argv[1]); process.stdout.write('imported');"
            imported = subprocess.run(["node", "--input-type=module", "-e", driver,
                                       (DEV_EXT / f"hooks/{phase}/author.mjs").as_uri()], cwd=self.root,
                                      capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
            self.assertEqual("imported", imported.stdout, imported.stderr)
        self.assertFalse({"spec", "plan"} & set(self.starts()), "导入作者模块就写了使用记录")
        for phase in ("spec", "plan"):
            with self.subTest(phase=phase):
                self.assertEqual(0, self.author(phase).returncode)
                first = self.starts()[phase]
                self.author(phase)
                self.assertEqual(first, self.starts()[phase], "重取任务包换了起点")


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

    def test_a_harness_check_is_not_the_start_of_work(self) -> None:
        """阶段检查不建身份、不登记起点；开始工作的 begin 才建，并在那时接收自报身份。"""
        proc = self.harness("coding")
        self.assertFalse((self.fr / ".usage-id").exists(), "检查建了使用记录身份：" + proc.stdout[-800:])
        self.assertFalse((self.root / "doc" / "features" / ".usage-state.json").exists(), "检查登记了起点")
        text = (self.fr / "coding" / "reports" / "merged-report.md").read_text(encoding="utf-8")
        self.assertNotIn('"spent"', text, "统计内容进了阶段报告")
        (self.fr / ".usage-input.json").write_text(json.dumps({"agent": "opencode", "model": "m1"}), encoding="utf-8")
        begun = subprocess.run([sys.executable, str(USAGE), "--project-root", str(self.root), "--feature", self.FEATURE,
                                "--begin", "--step", "review"], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=60)
        self.assertEqual(0, begun.returncode, begun.stdout + begun.stderr)
        stamp = (self.fr / ".usage-id").read_text(encoding="utf-8").strip()
        node = usage(self.root)["requirements"][f"{self.FEATURE}-{stamp}"]
        self.assertEqual(("opencode", "m1"), (node["agent"], node["model"]))
        self.assertFalse((self.fr / ".usage-input.json").exists())

if __name__ == "__main__":
    unittest.main()
