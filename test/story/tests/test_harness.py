"""Story runner 机制回归。

跑法：python -m unittest discover -s test/story/tests

只测**会被静默吞掉的机制**：游标丢事件、指纹忙轮询、历史迁移越界、`stop_failed` 伪装成
`stopped`——这四类坏了都看不出来，必须有回归。

本文件只保护运行、观测、恢复和阶段事实，不判断被测产物内容质量。
"""
from __future__ import annotations

import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "test" / "story" / "scripts"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPTS))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


observe = _load("story_observe", "observe.py")
rc = _load("story_run_case", "run_case.py")


class PollCadenceTest(unittest.TestCase):
    """观测节奏是 harness 契约，避免观察者退回逐事件高频轮询。"""

    def test_normal_batch_waits_two_minutes_before_next_poll(self) -> None:
        self.assertEqual(120, rc.OBSERVATION_INTERVAL_SEC)
        self.assertEqual(120, rc.next_poll_after_sec(
            "running", has_more=False, changed=True, deadline_reached=False))

    def test_urgent_or_backlogged_states_are_not_throttled(self) -> None:
        self.assertEqual(0, rc.next_poll_after_sec(
            "running", has_more=True, changed=True, deadline_reached=False))
        self.assertEqual(0, rc.next_poll_after_sec(
            "awaiting_reply", has_more=False, changed=True, deadline_reached=False))
        self.assertEqual(0, rc.next_poll_after_sec(
            "finished", has_more=False, changed=True, deadline_reached=False))

    def test_silent_long_poll_can_continue_immediately(self) -> None:
        self.assertEqual(0, rc.next_poll_after_sec(
            "running", has_more=False, changed=False, deadline_reached=True))


class CaseConfigTest(unittest.TestCase):
    """用例配置的机械看护——把「测的是交互还是记忆」这件事钉死在配置里。

    实测教训：为了测「用户要求按特性拆分」，曾把那句话预塞进初始 prompt。
    模型走到关卡时它已在几十步之外，于是概括任务描述、整句丢掉，判成「无范围指示」。
    那测出来的是记忆衰减，与关卡交互无关。

    所以：拆分诉求要么由真人在关卡上口述（`interactive: true`），
    要么用例头注明说自己是「对照组」（专测事先说过的话还认不认得出）。
    两条路都合法，**含糊不清不合法**。
    """

    CASES = REPO_ROOT / "test" / "story" / "cases"
    # 用户表达「本次只做一部分」的说法，用于识别 prompt 里预塞了拆分诉求。
    SPLIT_WORDS = ("只做其中一部分", "切开", "先做第一份", "本单承载", "拆开", "只做一部分")

    def _cases(self) -> list[tuple[str, Path, dict, str]]:
        import yaml
        out = []
        for path in sorted(self.CASES.glob("*/case.yaml")):
            text = path.read_text(encoding="utf-8")
            out.append((path.parent.name, path, yaml.safe_load(text) or {}, text))
        return out

    def test_every_case_is_wellformed(self) -> None:
        cases = self._cases()
        self.assertTrue(cases, "一个用例都没解析出来，看护形同虚设")
        for name, path, cfg, _ in cases:
            with self.subTest(case=name):
                self.assertEqual(cfg.get("id"), name, f"{path} 的 id 与目录名不一致")
                self.assertTrue(str(cfg.get("ar") or "").strip(), f"{path} 缺 ar")
                self.assertTrue(str(cfg.get("prompt") or "").strip(), f"{path} 缺 prompt")
                self.assertTrue(str(cfg.get("start_phase") or "").strip(),
                                f"{path} 缺 start_phase，gate 区间不能靠默认值猜")
                self.assertTrue(str(cfg.get("end_phase") or "").strip(),
                                f"{path} 缺 end_phase，正常停止点不明确")
                rc.resolve_start_phase(cfg)
                rc.phase_index(str(cfg["end_phase"]))

    def test_interactive_cases_do_not_preload_the_answer(self) -> None:
        """交互用例的诉求必须由人在关卡上说出口——写进 prompt 就白搭了。"""
        for name, path, cfg, _ in self._cases():
            if not rc.is_interactive(cfg):
                continue
            with self.subTest(case=name):
                prompt = str(cfg.get("prompt") or "")
                hit = [w for w in self.SPLIT_WORDS if w in prompt]
                self.assertFalse(
                    hit, f"{path} 声明了交互模式，prompt 里却预塞了诉求 {hit}"
                         "——那又退回测记忆了")
                # 回话要有个固定来源，否则每轮现编，轮次之间就不可比。
                # 逐关卡的 `interaction-script.yaml` 是它的完整形态（还能带补料投放）；
                # 只有一关要回的用例可以用 case.yaml 的 `suggested_reply` 顶。
                script = path.parent / "interaction-script.yaml"
                self.assertTrue(
                    script.is_file() or str(cfg.get("suggested_reply") or "").strip(),
                    f"{path} 既没有 interaction-script.yaml 也没有 suggested_reply："
                    "每轮现编回话，轮次之间就不可比")

    def test_a_prompt_that_claims_seeded_material_actually_ships_it(self) -> None:
        """prompt 说「材料我已经放好了」，`workspace/` 里就必须真有东西。

        实测踩过：新建用例时抄了 prompt 却漏建 `workspace/`，跑起来 inbox 是空的。
        模型只会如实报告「没有待导入材料」，一路跑完——**没有任何一步会失败**，
        而这一轮测的其实是另一个场景。
        """
        claims = ("放到这个需求的目录下", "已经把", "放好了", "放进")
        for name, path, cfg, _ in self._cases():
            prompt = str(cfg.get("prompt") or "")
            if not any(w in prompt for w in claims):
                continue
            workspace = path.parent / "workspace"
            with self.subTest(case=name):
                files = [p for p in workspace.rglob("*") if p.is_file()] if workspace.is_dir() else []
                self.assertTrue(
                    files,
                    f"{path} 的 prompt 声称材料已放进工作区，但 {workspace} 是空的"
                    "——跑起来 inbox 没东西，模型如实说「无待导入材料」，测的是另一个场景")

    def test_a_preloaded_split_request_declares_itself_a_control_case(self) -> None:
        """自动用例若在 prompt 里给了拆分诉求，头注必须写明它是对照组。"""
        for name, path, cfg, raw in self._cases():
            if rc.is_interactive(cfg):
                continue
            prompt = str(cfg.get("prompt") or "")
            if not any(w in prompt for w in self.SPLIT_WORDS):
                continue
            header = raw.split("id:")[0]
            with self.subTest(case=name):
                # 认「对照组」这个词，不认「对照」——后者在正文里随处可见
                # （「对照他说过的话」），宽一个字就漏掉整条看护。
                self.assertIn(
                    "对照组", header,
                    f"{path} 把拆分诉求预塞进了 prompt 却没声明自己是对照组——"
                    "读的人会以为它测的是交互")


class FeedCursorTest(unittest.TestCase):
    """同一 cursor 不重复消费，推进后不漏事件，超限分页且不丢内容。"""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.path = self.tmp / "live.jsonl"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_duplicate_no_gap(self) -> None:
        feed = observe.LiveFeed(self.path)
        for i in range(5):
            feed.emit("turn", n=i)

        first, cursor, has_more = observe.read_feed(self.path, 0, 1_000_000)
        self.assertEqual([e["seq"] for e in first], [1, 2, 3, 4, 5])
        self.assertEqual(cursor, 5)
        self.assertFalse(has_more)

        again, cursor2, _ = observe.read_feed(self.path, 5, 1_000_000)
        self.assertEqual(again, [])
        self.assertEqual(cursor2, 5)

        feed.emit("turn", n=5)
        more, cursor3, _ = observe.read_feed(self.path, 5, 1_000_000)
        self.assertEqual([e["seq"] for e in more], [6])
        self.assertEqual(cursor3, 6)

    def test_paging_loses_nothing(self) -> None:
        feed = observe.LiveFeed(self.path)
        for i in range(10):
            feed.emit("turn", n=i, note="x" * 200)
        seen, cursor, has_more = observe.read_feed(self.path, 0, 500)
        self.assertTrue(has_more)
        while has_more:
            page, cursor, has_more = observe.read_feed(self.path, cursor, 500)
            seen.extend(page)
        self.assertEqual([e["seq"] for e in seen], list(range(1, 11)))

    def test_partial_line_does_not_advance(self) -> None:
        feed = observe.LiveFeed(self.path)
        feed.emit("turn", n=0)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write('{"seq": 2, "type": "trunc')   # 半行
        events, cursor, _ = observe.read_feed(self.path, 0, 1_000_000)
        self.assertEqual([e["seq"] for e in events], [1])
        self.assertEqual(cursor, 1)


class ModelStreamTest(unittest.TestCase):
    """`model` 流是评价者读模型行为的通道，游标与 live feed 相互独立。"""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.path = self.tmp / "events.jsonl"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, *records: dict) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    def test_keeps_reasoning_and_condenses_tools(self) -> None:
        self._write(
            {"type": "reasoning", "content": "我先读 SKILL"},
            {"type": "tool", "tool_name": "bash",
             "tool_input": {"command": "node story-build.mjs check"},
             "tool_status": "completed"},
            {"type": "usage", "content": "ignored"},
            {"type": "text", "content": "已完成"},
        )
        items, cursor, _ = observe.read_model(self.path, 0, 1_000_000)
        self.assertEqual([i["type"] for i in items], ["reasoning", "tool", "text"])
        self.assertEqual(items[1]["detail"], "node story-build.mjs check")
        self.assertEqual(cursor, 3, "usage 不进流，游标只数进流的条目")

    def test_cursor_resumes(self) -> None:
        self._write({"type": "text", "content": "a"}, {"type": "text", "content": "b"})
        _, cursor, _ = observe.read_model(self.path, 0, 1_000_000)
        self._write({"type": "text", "content": "c"})
        items, _, _ = observe.read_model(self.path, cursor, 1_000_000)
        self.assertEqual([i["content"] for i in items], ["c"])


class SnapshotTest(unittest.TestCase):
    """产物变化要唤醒 poll；只有 activity_age_sec 变化时不得唤醒。"""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.out = self.tmp / "out"
        self.feature = self.tmp / "AR1"
        self.out.mkdir(parents=True)
        self.feature.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_age_alone_does_not_change_revision(self) -> None:
        (self.out / "runlog.md").write_text("a", encoding="utf-8")
        first = observe.snapshot(self.out, self.feature)
        time.sleep(1.1)
        second = observe.snapshot(self.out, self.feature)
        self.assertNotEqual(first["activity_age_sec"], second["activity_age_sec"])
        self.assertEqual(first["revision"], second["revision"],
                         "只有年龄在变却改了指纹，会造成无意义的忙轮询")

    def test_new_artifact_changes_revision(self) -> None:
        (self.out / "runlog.md").write_text("a", encoding="utf-8")
        before = observe.snapshot(self.out, self.feature)["revision"]
        (self.feature / "AR").mkdir()
        (self.feature / "AR" / "story.md").write_text("x", encoding="utf-8")
        self.assertNotEqual(before, observe.snapshot(self.out, self.feature)["revision"],
                            "产物出现却没唤醒 poll")


class FeatureHistoryMigrationTest(unittest.TestCase):
    """新链只迁移当前 feature 到仓外；其它需求、扩展与续跑输入保持原位。"""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.backup = self.tmp / "bak"
        self._root, self._dir = rc.REPO_ROOT, rc.FEATURES_DIR
        self._backup = rc.FEATURE_HISTORY_ROOT
        rc.REPO_ROOT = self.repo
        rc.FEATURE_HISTORY_ROOT = self.backup

    def tearDown(self) -> None:
        rc.REPO_ROOT, rc.FEATURES_DIR = self._root, self._dir
        rc.FEATURE_HISTORY_ROOT = self._backup
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_rejects_dangerous_roots(self) -> None:
        for bad in (".", "doc", "framework"):
            rc.FEATURES_DIR = bad
            with self.assertRaises(SystemExit, msg=f"未拦截危险产物根: {bad}"):
                rc.migrate_feature_history("AR1", "story")

    def test_moves_only_current_feature_and_keeps_siblings(self) -> None:
        rc.FEATURES_DIR = "doc/features"
        (self.repo / "doc" / "features" / "AR1" / "AR").mkdir(parents=True)
        history = self.repo / "doc" / "features" / "AR1" / "AR" / "story.md"
        history.write_text("上一轮", encoding="utf-8")
        (self.repo / "doc" / "features" / "AR2").mkdir(parents=True)
        (self.repo / "doc" / "extensions").mkdir(parents=True)
        subject = self.repo / "doc" / "extensions" / "skill.md"
        subject.write_text("被测对象", encoding="utf-8")

        result = rc.migrate_feature_history("AR1", "story", "run-1")
        self.assertEqual(result["status"], "moved")
        target = Path(result["target"])
        self.assertTrue((target / "AR" / "story.md").is_file())
        self.assertFalse((self.repo / "doc" / "features" / "AR1").exists())
        self.assertTrue((self.repo / "doc" / "features" / "AR2").is_dir())
        self.assertTrue(subject.exists(), "迁移碰了被测对象")

    def test_missing_history_is_a_recorded_noop(self) -> None:
        rc.FEATURES_DIR = "doc/features"
        result = rc.migrate_feature_history("AR1", "story")
        self.assertEqual(result["status"], "no_existing_feature")
        self.assertFalse(self.backup.exists(), "没有历史产物时不应创建空备份目录")

    def test_resume_never_moves_history(self) -> None:
        rc.FEATURES_DIR = "doc/features"
        feature = self.repo / "doc" / "features" / "AR1"
        feature.mkdir(parents=True)
        result = rc.migrate_feature_history("AR1", "plan")
        self.assertEqual(result["status"], "not_new_chain")
        self.assertTrue(feature.exists())


class WorkspaceSeedTest(unittest.TestCase):
    """用例材料在历史迁移之后重铺，新链起点干净且不会丢当前夹具。"""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self._root, self._dir, self._here = rc.REPO_ROOT, rc.FEATURES_DIR, rc.HERE
        self._backup = rc.FEATURE_HISTORY_ROOT
        rc.REPO_ROOT, rc.FEATURES_DIR = self.repo, "doc/features"
        rc.FEATURE_HISTORY_ROOT = self.tmp / "bak"
        rc.HERE = self.repo / "test" / "story" / "scripts"
        self.workspace = self.repo / "test" / "story" / "cases" / "c1" / "workspace"

    def tearDown(self) -> None:
        rc.REPO_ROOT, rc.FEATURES_DIR, rc.HERE = self._root, self._dir, self._here
        rc.FEATURE_HISTORY_ROOT = self._backup
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_seeds_subtree_and_reports_relative_paths(self) -> None:
        (self.workspace / "inbox").mkdir(parents=True)
        (self.workspace / "inbox" / "prd.docx").write_bytes(b"PK\x03\x04material")

        self.assertEqual(rc.seed_case_workspace("c1", "AR1"), ["inbox/prd.docx"])
        landed = self.repo / "doc" / "features" / "AR1" / "inbox" / "prd.docx"
        self.assertEqual(landed.read_bytes(), b"PK\x03\x04material", "材料未按原字节铺设")

    def test_seeds_after_history_migration(self) -> None:
        """先迁移旧 feature 再铺材料，新链拿到本轮夹具且旧产物留有备份。"""
        (self.workspace / "inbox").mkdir(parents=True)
        (self.workspace / "inbox" / "prd.docx").write_bytes(b"material")
        (self.repo / "doc" / "features" / "AR1" / "AR").mkdir(parents=True)

        moved = rc.migrate_feature_history("AR1", "story")
        rc.seed_case_workspace("c1", "AR1")
        self.assertEqual(moved["status"], "moved")
        self.assertTrue((self.repo / "doc" / "features" / "AR1" / "inbox" / "prd.docx").exists())

    def test_case_without_workspace_starts_empty(self) -> None:
        self.assertEqual(rc.seed_case_workspace("no-such-case", "AR1"), [])
        self.assertFalse((self.repo / "doc" / "features" / "AR1").exists(),
                         "无材料的用例不该凭空建出 feature 目录")


class AuditDirCleanupTest(unittest.TestCase):
    """审计目录是 harness 自己的产物，只读位不该拦住清理。

    实证：opencode 在审计目录里建 git 快照库，git object 在 Windows 上是只读文件，
    于是同一用例第二次 start 必然失败——且被报成「上一轮 CLI/worker 未回收」，
    把人引去查根本不存在的残留进程。
    """

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        for path in self.tmp.rglob("*"):
            if path.is_file():
                path.chmod(0o600)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_removes_read_only_files(self) -> None:
        import os
        target = self.tmp / "out" / "snapshot" / "objects" / "10"
        target.mkdir(parents=True)
        blob = target / "89902e19"
        blob.write_bytes(b"git object")
        blob.chmod(0o400)

        rc._rmtree_force(self.tmp / "out")
        self.assertFalse((self.tmp / "out").exists(), "只读文件挡住了审计目录清理")
        self.assertTrue(os.access(self.tmp, os.W_OK), "清理越出了目标目录")


class StateMachineTest(unittest.TestCase):
    """stop_failed 必须是独立终态，不能被伪装成 stopped。"""

    def test_sets_are_disjoint(self) -> None:
        self.assertFalse(rc.ACTIVE_STATUS & rc.TERMINAL_STATUS)

    def test_stop_failed_is_distinct(self) -> None:
        self.assertIn("stop_failed", rc.TERMINAL_STATUS)
        self.assertIn("stopped", rc.TERMINAL_STATUS)

    def test_waiting_is_active_and_worker_lost_is_terminal(self) -> None:
        self.assertIn("awaiting_reply", rc.ACTIVE_STATUS)
        self.assertIn("worker_lost", rc.TERMINAL_STATUS)

    def test_dead_worker_waits_for_lease_then_converges(self) -> None:
        root = Path(tempfile.mkdtemp())
        try:
            state = {"case": "c", "pid": 123, "status": "running",
                     "lease_expires_epoch": 200.0, "last_phase": "plan"}
            rc.write_state(root, state)
            with mock.patch.object(rc, "_pid_alive", return_value=False):
                before = rc.reconcile_worker_state(root, state, now=199.0, reap_cli=False)
                self.assertEqual(before["status"], "running")
                after = rc.reconcile_worker_state(root, state, now=201.0, reap_cli=False)
            self.assertEqual(after["status"], "worker_lost")
            self.assertEqual(after["last_phase"], "plan")
            self.assertIn("重新执行", after["recovery_advice"])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_heartbeat_renews_the_lease_atomically(self) -> None:
        root = Path(tempfile.mkdtemp())
        try:
            state = {"pid": 123, "status": "running"}
            rc.refresh_worker_lease(root, state, force=True, now=100.0,
                                    event="cli_poll", phase="plan")
            published = rc.read_state(root)
            self.assertEqual(published["heartbeat_epoch"], 100.0)
            self.assertEqual(published["lease_expires_epoch"], 100.0 + rc.WORKER_LEASE_SEC)
            self.assertEqual(published["last_phase"], "plan")
            self.assertEqual(published["last_event"]["name"], "cli_poll")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_live_pid_is_not_lost_even_if_lease_timestamp_is_old(self) -> None:
        state = {"pid": 123, "status": "running", "lease_expires_epoch": 1.0}
        with mock.patch.object(rc, "_pid_alive", return_value=True):
            self.assertEqual(
                rc.reconcile_worker_state(Path(tempfile.gettempdir()), state,
                                          now=999.0, reap_cli=False)["status"],
                "running")

    def test_stop_is_idempotent_after_terminal_result(self) -> None:
        root = Path(tempfile.mkdtemp())
        try:
            phase_results = {"plan": {"execution_status": "pass", "closure_status": "closed"}}
            state = {"case": "c", "pid": 123, "status": "finished",
                     "phase_results": phase_results}
            rc.write_state(root, state)
            with mock.patch.object(rc, "_load_case", return_value=({}, root, "AR1")):
                output = io.StringIO()
                with redirect_stdout(output):
                    code = rc.cmd_stop("c", force=False)
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(output.getvalue())["already_terminal"])
            self.assertEqual(rc.read_state(root)["phase_results"], phase_results)
            self.assertEqual(rc.read_state(root)["status"], "finished")
        finally:
            shutil.rmtree(root, ignore_errors=True)


class CliRuntimeIsolationTest(unittest.TestCase):
    """运行隔离避免 OpenCode 启动时写入或误建用户的配置目录。"""

    def test_opencode_runtime_paths_stay_under_case_output(self) -> None:
        root = Path(tempfile.mkdtemp())
        try:
            env = rc.build_cli_env(root)
            self.assertEqual(Path(env["XDG_CONFIG_HOME"]).parent, root)
            self.assertEqual(Path(env["XDG_DATA_HOME"]).parent, root)
        finally:
            shutil.rmtree(root, ignore_errors=True)


class ImmutableRunLayoutTest(unittest.TestCase):
    """稳定 case 命令只是索引；每轮证据都在新 run-id 目录且不覆盖。"""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_active_then_latest_resolves_the_same_immutable_run(self) -> None:
        first, first_id = rc.run_layout.create_run(self.root, "case-a", "run-001")
        (first / "evidence.txt").write_text("first", encoding="utf-8")
        resolved, rid = rc.run_layout.resolve_run(self.root, "case-a")
        self.assertEqual((resolved, rid), (first, first_id))

        rc.run_layout.publish_latest(self.root, "case-a", first_id, "finished")
        self.assertFalse((self.root / "case-a" / "active.json").exists())
        self.assertEqual(rc.run_layout.resolve_run(self.root, "case-a"), (first, first_id))

        second, second_id = rc.run_layout.create_run(self.root, "case-a", "run-002")
        self.assertNotEqual(first, second)
        self.assertTrue((first / "evidence.txt").is_file(), "新 run 覆盖了历史证据")
        self.assertEqual(rc.run_layout.resolve_run(self.root, "case-a"), (second, second_id))

    def test_pointer_cannot_escape_the_run_root(self) -> None:
        with self.assertRaises(ValueError):
            rc.run_layout.create_run(self.root, "case-a", "../escape")


class SourceTransactionTest(unittest.TestCase):
    """Coding 在真实工作区运行，但跑前脏状态必须逐字节恢复。"""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.source = self.root / "01-Product"
        self.source.mkdir()
        self._git("init")
        self._git("config", "user.email", "story-test@example.invalid")
        self._git("config", "user.name", "Story Test")
        self._git("config", "core.autocrlf", "false")
        (self.source / "tracked.txt").write_bytes(b"base\r\n")
        (self.source / "kept.txt").write_bytes(b"kept\n")
        self._git("add", ".")
        self._git("commit", "-m", "baseline")
        self.original_root = rc.REPO_ROOT
        self.original_dirs = rc.SOURCE_DIRS
        rc.REPO_ROOT = self.root
        rc.SOURCE_DIRS = ("01-Product",)
        self.out = self.root / "output" / "run"
        self.out.mkdir(parents=True)

    def tearDown(self) -> None:
        rc.REPO_ROOT = self.original_root
        rc.SOURCE_DIRS = self.original_dirs
        shutil.rmtree(self.root, ignore_errors=True)

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=self.root, check=True,
                              capture_output=True, text=False)

    def test_success_archives_real_diff_and_restores_index_worktree_and_untracked(self) -> None:
        tracked = self.source / "tracked.txt"
        tracked.write_bytes(b"user staged\r\n")
        self._git("add", "01-Product/tracked.txt")
        tracked.write_bytes(b"user unstaged\x00bytes")
        untracked = self.source / "personal.bin"
        untracked.write_bytes(b"personal\x00data")
        before = rc.source_state_fingerprint()
        before_status = self._git("status", "--porcelain=v1", "-z", "--",
                                  "01-Product").stdout

        manifest = rc.begin_source_transaction(self.out)
        self.assertEqual(manifest["status"], "baseline_ready")
        self.assertEqual(tracked.read_bytes(), b"base\r\n")
        self.assertFalse(untracked.exists())
        self.assertEqual(self._git("status", "--porcelain=v1", "-z", "--",
                                   "01-Product").stdout, b"")

        tracked.write_bytes(b"coding result\n")
        created = self.source / "created.ets"
        created.write_text("export const changed = true;\n", encoding="utf-8")
        self._git("add", "01-Product/created.ets")  # 即使被测 CLI 误暂存也要恢复
        evidence = rc.archive_source_evidence(self.out)
        self.assertIn("01-Product/tracked.txt", evidence["changed_paths"])
        self.assertIn("01-Product/created.ets", evidence["changed_paths"])
        self.assertTrue((self.out / rc.SOURCE_TRANSACTION_DIR / evidence["patch"]).is_file())

        restored = rc.restore_source_transaction(self.out)
        self.assertEqual(restored["status"], "restored")
        self.assertEqual(rc.source_state_fingerprint(), before)
        self.assertEqual(tracked.read_bytes(), b"user unstaged\x00bytes")
        self.assertEqual(untracked.read_bytes(), b"personal\x00data")
        self.assertFalse(created.exists(), "本轮 Coding 新建文件未被删除")
        self.assertEqual(self._git("status", "--porcelain=v1", "-z", "--",
                                   "01-Product").stdout, before_status)

    def test_restore_failure_is_an_explicit_terminal_condition(self) -> None:
        (self.source / "tracked.txt").write_text("user change", encoding="utf-8")
        rc.begin_source_transaction(self.out)
        snapshot = (self.out / rc.SOURCE_TRANSACTION_DIR / "pre-run" / "tracked"
                    / "01-Product" / "tracked.txt")
        snapshot.unlink()
        (self.source / "tracked.txt").write_text("coding", encoding="utf-8")
        restored = rc.restore_source_transaction(self.out)
        self.assertEqual(restored["status"], "source_restore_failed")
        state = rc.settle_terminal_source(self.out, {"status": "stopped"})
        self.assertEqual(state["status"], "source_restore_failed")
        self.assertIn("recovery", restored)

    def test_terminal_finalizer_publishes_retry_success_not_first_failure(self) -> None:
        first = {"status": "source_restore_failed", "errors": ["transient"]}
        second = {"status": "restored", "restored_fingerprint": {"digest": "ok"}}
        with mock.patch.object(rc, "restore_source_transaction", side_effect=[first, second]) as restore:
            result = rc.finalize_source_transaction(self.out)
        self.assertEqual(result["status"], "restored")
        self.assertEqual([item["status"] for item in result["attempts"]],
                         ["source_restore_failed", "restored"])
        self.assertEqual(restore.call_count, 2)


class EndPhaseTest(unittest.TestCase):
    """end_phase：跑到哪个阶段为止。

    加它是因为 harness 原来只驱动到 spec——三份产物一齐备就 break，
    后面的 plan/coding/review/ut 无从驱动。**缺省必须是 spec**：既有用例一个字没改，
    行为要与从前逐字节一致，否则这次改造本身就成了变量。
    """

    def test_phase_order_matches_the_workflow(self) -> None:
        """阶段序列取自 framework 的 feature full 轨，顺序错了闭环判据就查错阶段。"""
        self.assertEqual(rc.PHASE_ORDER,
                         ("spec", "plan", "coding", "review", "ut", "testing"))

    def test_unknown_phase_is_rejected_loudly(self) -> None:
        """写错 end_phase 要当场报，不能默默按 spec 跑完然后让人以为测了全流程。"""
        with self.assertRaises(SystemExit) as ctx:
            rc.phase_index("codeing")       # 常见拼写错
        self.assertIn("codeing", str(ctx.exception))

    def test_spec_target_requires_its_formal_closure(self) -> None:
        """三份阅读产物出现不等于 spec 闭环，不能据此提前结束整条用例。"""
        root = Path(tempfile.mkdtemp())
        original = rc.REPO_ROOT
        try:
            rc.REPO_ROOT = root
            feature = "AR90099"
            feature_root = root / rc.FEATURES_DIR / feature
            (feature_root / "AR").mkdir(parents=True)
            (feature_root / "AR" / "story.md").write_text("story", encoding="utf-8")
            (feature_root / "AR" / "review.md").write_text("review", encoding="utf-8")
            phase_root = feature_root / "spec"
            phase_root.mkdir()
            (phase_root / "spec.md").write_text("spec", encoding="utf-8")
            self.assertFalse(rc.target_reached(feature, "spec"))

            reports = phase_root / "reports"
            reports.mkdir()
            (reports / "trace.json").write_text("{}", encoding="utf-8")
            (reports / "verifier.report.md").write_text("PASS", encoding="utf-8")
            (reports / "summary.json").write_text(
                json.dumps({"verdict": "PASS", "receipt_status": "passed",
                            "closure_status": "closed"}), encoding="utf-8")
            (phase_root / "phase-completion-receipt.md").write_text("ok", encoding="utf-8")
            self.assertTrue(rc.target_reached(feature, "spec"))
        finally:
            rc.REPO_ROOT = original
            shutil.rmtree(root, ignore_errors=True)

    def test_turn_budget_grows_with_the_target_phase(self) -> None:
        """跑得越远给的轮次越多；否则模型会在 coding 中途被轮次上限掐断。"""
        to_spec = rc.PHASE_TURNS["spec"]
        to_ut = sum(rc.PHASE_TURNS[p] for p in rc.PHASE_ORDER[:rc.phase_index("ut") + 1])
        self.assertGreater(to_ut, to_spec * 3)

    def test_source_reset_scope_is_enumerated_not_inferred(self) -> None:
        """源码复位范围必须是**列举**的。

        写成「除 doc/test 之外」那种反向规则，一旦仓库多出一个顶层目录就会被卷进去删——
        而被测件（doc/extensions）与 harness 自己（test/story）都在仓库里。
        漏列一个目录只是少复位一处，多算一个目录是删掉被测对象。
        """
        for forbidden in ("doc", "test", "framework", "tools", "output", ""):
            self.assertNotIn(forbidden, rc.SOURCE_DIRS)
        self.assertTrue(all(d[:2].isdigit() for d in rc.SOURCE_DIRS),
                         f"源码目录应是 NN-Name 形态：{rc.SOURCE_DIRS}")


class PhaseResultModelTest(unittest.TestCase):
    """phase 结果是不可变事实；case stop 只聚合，不覆盖它。"""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.original = rc.REPO_ROOT
        rc.REPO_ROOT = self.root
        self.feature = "AR90099"
        self.feature_root = self.root / rc.FEATURES_DIR / self.feature

    def tearDown(self) -> None:
        rc.REPO_ROOT = self.original
        shutil.rmtree(self.root, ignore_errors=True)

    def _closed_phase(self, phase: str, artifact_name: str) -> None:
        phase_root = self.feature_root / phase
        reports = phase_root / "reports"
        reports.mkdir(parents=True)
        (phase_root / artifact_name).write_text(phase, encoding="utf-8")
        (reports / "trace.json").write_text("{}", encoding="utf-8")
        (reports / "verifier.report.md").write_text("PASS", encoding="utf-8")
        (reports / "summary.json").write_text(
            json.dumps({"verdict": "PASS", "receipt_status": "passed",
                        "closure_status": "closed"}), encoding="utf-8")
        (phase_root / "phase-completion-receipt.md").write_text("ok", encoding="utf-8")

    def test_phase_and_gate_scope_match_start_end(self) -> None:
        self.assertEqual(rc.applicable_phases("story", "plan"), ("story", "spec", "plan"))
        self.assertEqual(rc.applicable_phases("plan", "plan"), ("plan",))
        plan_gates = rc.expected_gate_names("plan", "plan")
        self.assertEqual(plan_gates, ("harness_plan", "upstream_fingerprint"))
        self.assertNotIn("story_criteria", plan_gates)

    def test_closed_plan_records_execution_and_closure(self) -> None:
        self._closed_phase("plan", "plan.md")
        results = rc.build_phase_results(
            self.feature, "plan", "plan",
            {"harness_plan": "pass", "upstream_fingerprint": "pass"})
        self.assertEqual(results["plan"]["execution_status"], "completed")
        self.assertEqual(results["plan"]["closure_status"], "closed")

    def test_plan_gate_can_pass_while_formal_closure_is_open(self) -> None:
        self._closed_phase("plan", "plan.md")
        summary = self.feature_root / "plan" / "reports" / "summary.json"
        summary.write_text(json.dumps({
            "verdict": "PASS", "receipt_status": "failed", "closure_status": "open",
        }), encoding="utf-8")
        results = rc.build_phase_results(
            self.feature, "plan", "plan", {"harness_plan": "pass"})
        self.assertEqual(results["plan"]["execution_status"], "completed")
        self.assertEqual(results["plan"]["closure_status"], "open")
        self.assertIn("formal closure", results["plan"]["closure_missing"][0])

    def test_published_phase_result_is_write_once(self) -> None:
        out = self.root / "out"
        original = {"plan": {"phase": "plan", "execution_status": "pass"}}
        rc.publish_phase_results(out, original)
        rc.publish_phase_results(out, original)  # 相同内容可重入
        with self.assertRaises(RuntimeError):
            rc.publish_phase_results(
                out, {"plan": {"phase": "plan", "execution_status": "fail"}})

    def test_downstream_files_do_not_change_upstream_fingerprint(self) -> None:
        (self.feature_root / "AR").mkdir(parents=True)
        (self.feature_root / "AR" / "story.md").write_text("story", encoding="utf-8")
        (self.feature_root / "spec").mkdir()
        spec = self.feature_root / "spec" / "spec.md"
        spec.write_text("spec", encoding="utf-8")
        before = rc.compute_upstream_fingerprint(self.feature, "plan")
        (self.feature_root / "plan").mkdir()
        (self.feature_root / "plan" / "plan.md").write_text("plan", encoding="utf-8")
        self.assertEqual(before, rc.compute_upstream_fingerprint(self.feature, "plan"))
        spec.write_text("changed", encoding="utf-8")
        self.assertNotEqual(before, rc.compute_upstream_fingerprint(self.feature, "plan"))


class ResumeFromPhaseTest(unittest.TestCase):
    """任意阶段 start / 任意阶段 stop。

    story+spec 跑一趟要 40 分钟。要观测 plan 就重跑一遍上游，是把最贵的部分白烧一次；
    而上一轮的产物还在、闭环凭证齐全，它本来就是 plan 的合法输入。

    这里守的是续跑最容易被搞砸的三处：历史迁移、前置校验、prompt。
    """

    def test_start_phase_defaults_to_story(self) -> None:
        """缺省从头跑——既有用例一个字没改，行为必须与从前逐字节一致。"""
        self.assertEqual(rc.resolve_start_phase({}), "story")
        self.assertEqual(rc.resolve_start_phase({"ar": "AR90003"}), "story")

    def test_resume_never_wipes_the_artifacts_it_needs(self) -> None:
        """**最要命的一条**：续跑时迁移当前 feature 等于把自己的输入挪走。

        历史迁移是从头跑的前提（保证起跑点干净且保留对比），却是续跑的反面——
        同一个动作，在两种模式下的含义正好相反。
        """
        self.assertFalse(rc.should_migrate_feature_history("plan"))
        self.assertFalse(rc.should_migrate_feature_history("coding"))
        self.assertTrue(rc.should_migrate_feature_history("story"))

    def test_resume_requires_the_previous_phase_to_be_closed(self) -> None:
        """在半成品上跑下游是沙上盖楼——失败了也分不清是谁的错。"""
        self.assertEqual(rc.phase_before("plan"), "spec")
        self.assertEqual(rc.phase_before("coding"), "plan")
        self.assertIsNone(rc.phase_before("story"), "从头跑没有前序阶段可校验")

    def test_evidence_check_ignores_head_movement(self) -> None:
        """前置校验查的是「上游跑完并闭环过」，不是「自那以后没人提交过」。

        `check-receipt` 还会比对 summary.source_commit_sha 与当前 HEAD——那条判据
        对继续开发是对的（代码变了旧结论可能不成立），对续跑测试却是错的：
        拿它当阻断条件等于要求测试期间全仓静止。这里读取 summary 已定稿的 formal closure，
        不因之后一次提交抹掉“当时已闭环”的事实。
        """
        root = Path(tempfile.mkdtemp())
        try:
            feature = "AR90099"
            phase_root = root / "doc" / "features" / feature / "spec"
            (phase_root / "reports").mkdir(parents=True)
            for name in ("trace.json", "verifier.report.md"):
                (phase_root / "reports" / name).write_text("{}", encoding="utf-8")
            (phase_root / "reports" / "summary.json").write_text(
                json.dumps({"verdict": "PASS",
                            "receipt_status": "passed", "closure_status": "closed",
                            "source_commit_sha": "0000000000000000000000000000000000000000"}),
                encoding="utf-8")
            (phase_root / "phase-completion-receipt.md").write_text("ok\n", encoding="utf-8")

            original = rc.REPO_ROOT
            try:
                rc.REPO_ROOT = root
                ok, missing = rc.phase_evidence_complete(feature, "spec")
            finally:
                rc.REPO_ROOT = original
            self.assertTrue(ok, f"四件套与 formal closure 均齐备却被判不齐：缺 {missing}")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_evidence_check_still_catches_a_missing_receipt(self) -> None:
        """放宽的只是 git 时效，凭证缺失照样拦——否则这条校验就白设了。"""
        root = Path(tempfile.mkdtemp())
        try:
            feature = "AR90099"
            phase_root = root / "doc" / "features" / feature / "spec"
            (phase_root / "reports").mkdir(parents=True)
            for name in ("trace.json", "verifier.report.md"):
                (phase_root / "reports" / name).write_text("{}", encoding="utf-8")
            (phase_root / "reports" / "summary.json").write_text(
                json.dumps({"verdict": "PASS", "receipt_status": "passed",
                            "closure_status": "closed"}), encoding="utf-8")
            # 故意不写 phase-completion-receipt.md
            original = rc.REPO_ROOT
            try:
                rc.REPO_ROOT = root
                ok, missing = rc.phase_evidence_complete(feature, "spec")
            finally:
                rc.REPO_ROOT = original
            self.assertFalse(ok)
            self.assertIn("完成回执", missing)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_resume_prompt_does_not_restart_the_pipeline(self) -> None:
        """续跑 prompt 不能复用「执行 /story init …」——那会让模型重跑已完成的阶段。"""
        prompt = rc.resume_prompt("AR90003", "plan", "plan")
        self.assertNotIn("/story init", prompt)
        self.assertIn("plan", prompt)
        self.assertIn("AR90003", prompt)


class GateReplyRoutingTest(unittest.TestCase):
    """续话文案按**卡在哪一层**分流。

    实测教训：spec 闭环后模型给的推荐链路是「评审 → 归档」，「进 plan」排在其后。
    驱动器回一句"按你推荐的选项继续"，模型照办执行了归档、宣布"全链已交付"，
    随后空转 5 次——`plan/` 目录从未建立。

    一句通用回话应付不了两种关卡：材料关卡要的是"按推荐走"，
    阶段边界要的是**指名道姓的推进指令**。
    """

    def test_material_gate_keeps_the_recommendation_reply(self) -> None:
        """产物未齐时推荐项就是「进入 /spec」，按推荐走是对的。"""
        reply = rc.continuation_reply("AR90003", artifacts_done=False, next_phase=None)
        self.assertIn("推荐", reply)

    def test_phase_boundary_names_the_next_phase(self) -> None:
        """产物齐但阶段未闭环 = 卡在阶段边界，必须指名下一个阶段。"""
        reply = rc.continuation_reply("AR90003", artifacts_done=True, next_phase="plan")
        self.assertIn("plan", reply)
        self.assertNotIn("按你推荐的选项继续", reply,
                         "阶段边界仍在说「按推荐走」——模型会照 spec 的推荐去归档")


class StoryReviewEndPhaseTest(unittest.TestCase):
    """story 侧终点：跑到评审意见处置完成为止。

    归档送审与 `/story review` 回流都发生在 spec 闭环**之后**，而 end_phase 原先
    只认 framework 六阶段——用 spec 跑，驱动器在三产物齐备时就停了，续不到回流。
    借道 `end_phase: plan` 能让循环不停，但读用例的人会困惑为什么要 plan。
    """

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.feature = self.tmp / "AR"
        self.feature.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_it_is_an_accepted_end_phase(self) -> None:
        self.assertEqual(rc.phase_index(rc.STORY_REVIEW), 0,
                         "story 侧终点应沿用 spec 的产物判据再叠回流凭证")

    def test_an_unknown_end_phase_still_fails(self) -> None:
        with self.assertRaises(SystemExit):
            rc.phase_index("nowhere")

    def test_the_disposition_ledger_is_the_evidence(self) -> None:
        """判据是处置台账：意见逐条有了去向，这一趟才算走完。"""
        src = (REPO_ROOT / "test" / "story" / "scripts" / "run_case.py").read_text(encoding="utf-8")
        self.assertIn("review-disposition.json", src,
                      "story 侧终点未以处置台账为凭证")


class HumanReplyTest(unittest.TestCase):
    """交互模式：真人回话的投递、取用与「取走即消失」。

    为什么需要这条通道：自动模式替人给出的永远是同一句「按你推荐的走」，
    它只模拟得了**全自动用户**这一种人。关卡呈现质量、用户口述新诉求、
    拆分讨论这些行为在自动模式下结构上就测不到——曾为了测「用户要求拆分」
    把答案预塞进初始 prompt，逼出来的是记忆衰减，与真实交互无关。

    这些点坏了都是静默的：回话没被取走 → 驱动器一直等；取了不删 → 同一句话
    被反复送进被测会话；上一轮的残留没清 → 新一轮开局就被一句陈年回话推着走。
    """

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _queue(self, text: str) -> None:
        (self.tmp / rc.REPLY_FILE).write_text(
            json.dumps({"text": text, "at": "2026-08-15T20:00:00"}, ensure_ascii=False),
            encoding="utf-8")

    def test_a_queued_reply_is_taken_once(self) -> None:
        """一句话只用一次：取走即删，否则它会成为此后每一关的答案。"""
        self._queue("本次先做挂失申请流程，其余留给后续单据")
        self.assertEqual(rc.pop_pending_reply(self.tmp),
                         "本次先做挂失申请流程，其余留给后续单据")
        self.assertIsNone(rc.pop_pending_reply(self.tmp), "回话被取走后仍然存在")
        self.assertFalse((self.tmp / rc.REPLY_FILE).exists())

    def test_no_reply_reads_as_none(self) -> None:
        self.assertIsNone(rc.pop_pending_reply(self.tmp))

    def test_a_half_written_file_is_not_a_reply(self) -> None:
        """写到一半的文件当作没有——把残缺内容送进被测会话比多等一秒糟得多。"""
        (self.tmp / rc.REPLY_FILE).write_text('{"text": "本次先做', encoding="utf-8")
        self.assertIsNone(rc.pop_pending_reply(self.tmp))

    def test_an_empty_text_is_not_a_reply(self) -> None:
        self._queue("   ")
        self.assertIsNone(rc.pop_pending_reply(self.tmp))

    def test_interactive_defaults_to_off(self) -> None:
        """既有用例一字不改，行为逐字节一致。"""
        self.assertFalse(rc.is_interactive({}))
        self.assertFalse(rc.is_interactive({"id": "x", "ar": "AR-FIXTURE"}))
        self.assertTrue(rc.is_interactive({"interactive": True}))

    def test_waiting_gives_up_instead_of_answering_for_the_person(self) -> None:
        """等不到人**不降级成自动回话**。

        降级会把「没人应答」悄悄变成「有人说按推荐走」，测出来的交互行为是假的
        ——而报告上看不出这一步是谁答的。
        """
        feed = observe.LiveFeed(self.tmp / "live.jsonl")
        runlog = observe.RunLog(self.tmp / "runlog.md")
        state: dict = {}
        got = rc.wait_for_human_reply(self.tmp, feed, runlog, state, turn=1, timeout=0)
        runlog.close()
        self.assertIsNone(got, "等不到回话却给出了内容")
        events = [json.loads(ln) for ln in
                  (self.tmp / "live.jsonl").read_text(encoding="utf-8").splitlines()
                  if ln.strip()]
        kinds = [e.get("type") for e in events]
        self.assertIn("awaiting_reply", kinds, "没有喊出「在等人回话」")
        self.assertIn("awaiting_reply_timeout", kinds, "超时没有留痕")

    def test_waiting_publishes_a_state_the_poller_can_see(self) -> None:
        """状态要能被轮询看到，否则观察者不知道该自己动手了。"""
        feed = observe.LiveFeed(self.tmp / "live.jsonl")
        runlog = observe.RunLog(self.tmp / "runlog.md")
        rc.wait_for_human_reply(self.tmp, feed, runlog, {}, turn=1, timeout=0)
        runlog.close()
        self.assertEqual(rc.read_state(self.tmp).get("status"), "awaiting_reply")

    def test_replying_to_nothing_is_refused(self) -> None:
        """没人在跑就别回「已入队」。

        那句话不会有人读，而回执写着入队成功，人会以为说过了，
        然后一直等一个不会到来的下一轮。
        """
        # 挑哪个用例无所谓，只要它存在且没在跑；用例集是动态的，别写死名字。
        case_id = sorted(p.parent.name for p in
                         (REPO_ROOT / "test" / "story" / "cases").glob("*/case.yaml"))[0]
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "run_case.py"), case_id,
             "reply", "--text", "本次先做第一份"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(REPO_ROOT))
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertFalse(out["ok"], "对着没在跑的用例说话却回了成功")
        self.assertNotEqual(proc.returncode, 0)

    def test_a_queued_reply_ends_the_wait(self) -> None:
        feed = observe.LiveFeed(self.tmp / "live.jsonl")
        runlog = observe.RunLog(self.tmp / "runlog.md")
        self._queue("按端侧特性切开，本单先做第一份")
        got = rc.wait_for_human_reply(self.tmp, feed, runlog, {}, turn=1, timeout=5)
        runlog.close()
        self.assertEqual(got, "按端侧特性切开，本单先做第一份")
        self.assertEqual(rc.read_state(self.tmp).get("status"), "running")


class PhaseSlotTest(unittest.TestCase):
    """全局阶段槽的快照/还原。

    `.current-phase.json` 是 framework 的**全局单槽**，观测者会话与被测模型共用。
    被测模型跑 /spec 会写它；观测者会话的 Stop hook 会读它并盖上观测者自己的
    session_id，于是把被测模型的阶段误判成观测者的未闭环阶段、反复拦截。
    framework 是只读 vendored 目录，改不了那个 hook，只能由 harness 善后。

    TEST.md 承诺了「运行前快照，终态还原」，但驱动器里一直没实现——
    实测被拦过一次才发现。这组断言把它钉住。
    """

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.original = rc.REPO_ROOT
        rc.REPO_ROOT = self.root
        self.slot = self.root / rc.PHASE_SLOT
        self.slot.parent.mkdir(parents=True)

    def tearDown(self) -> None:
        rc.REPO_ROOT = self.original
        shutil.rmtree(self.root, ignore_errors=True)

    def test_absent_before_and_after_is_left_alone(self) -> None:
        snap = rc.snapshot_phase_slot()
        self.assertIsNone(snap)
        self.assertEqual(rc.restore_phase_slot(snap), "absent")

    def test_slot_created_during_the_run_is_removed(self) -> None:
        """跑之前没有、跑完多出来的，是这一轮留下的——删掉，否则会拦住观测者。"""
        snap = rc.snapshot_phase_slot()
        self.slot.write_text('{"phase":"ut"}', encoding="utf-8")
        self.assertEqual(rc.restore_phase_slot(snap), "removed")
        self.assertFalse(self.slot.exists())

    def test_pre_existing_slot_is_restored_verbatim(self) -> None:
        """跑之前就有的槽是别人的状态，要一字不差地还回去。"""
        self.slot.write_text('{"phase":"spec","feature":"AR90001"}', encoding="utf-8")
        snap = rc.snapshot_phase_slot()
        self.slot.write_text('{"phase":"ut","feature":"AR90003"}', encoding="utf-8")
        self.assertEqual(rc.restore_phase_slot(snap), "restored")
        self.assertEqual(self.slot.read_text(encoding="utf-8"),
                         '{"phase":"spec","feature":"AR90001"}')

    def test_untouched_slot_reports_unchanged(self) -> None:
        self.slot.write_text('{"phase":"spec"}', encoding="utf-8")
        snap = rc.snapshot_phase_slot()
        self.assertEqual(rc.restore_phase_slot(snap), "unchanged")


class GateScopeTest(unittest.TestCase):
    """只为**实际到达过**的阶段跑 harness。

    实测教训：`end_phase=ut` 时驱动器为 plan/coding/review/ut 四个从未执行过的阶段
    跑了 harness，13 秒内连产四份 FAIL summary，并把 framework 的全局阶段槽写成 ut，
    反过来拦住观测者会话的 Stop hook。

    跑一个没有产物的阶段，得到的 FAIL 不含任何信息——它只说明"没跑过"，而这件事
    我们本来就知道。
    """

    def test_phase_without_artifacts_is_skipped(self) -> None:
        root = Path(tempfile.mkdtemp())
        try:
            feature_root = root / "doc" / "features" / "AR90099"
            (feature_root / "plan" / "reports").mkdir(parents=True)
            # 只有 reports/（上一轮空跑留下的），没有任何真产物
            (feature_root / "plan" / "reports" / "summary.json").write_text("{}", encoding="utf-8")
            self.assertFalse(rc.phase_was_reached(feature_root, "plan"),
                             "只有 reports/ 不算到达过——那正是空跑留下的痕迹")
            (feature_root / "plan" / "plan.md").write_text("# plan\n", encoding="utf-8")
            self.assertTrue(rc.phase_was_reached(feature_root, "plan"))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_gate_launch_exception_is_a_diagnostic_not_a_silent_crash(self) -> None:
        root = Path(tempfile.mkdtemp())
        try:
            log = root / "gate.log"
            completed, diagnosis = rc._run_logged_gate(
                [str(root / "definitely-not-an-executable")], cwd=root, log_path=log)
            self.assertIsNone(completed)
            self.assertIn("exception", diagnosis)
            self.assertIsNone(diagnosis["returncode"])
            self.assertTrue(log.is_file())
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
