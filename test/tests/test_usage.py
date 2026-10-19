"""使用记录（core/usage.py）：初始化、幂等、终态游标结算与单文件事务，用真实文件与子进程验证。

隔离目标工程里放 framework 树与原生 summary / update 记录，经正式机器入口（stdin JSON）调用，
不写维护仓的 usage。时间区间按落盘的起点与原生结束时刻构造。
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ext_workspace import DEV_EXT

USAGE = DEV_EXT / "skills" / "story" / "scripts" / "core" / "usage.py"


def at(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def native(dt: datetime) -> str:
    """Framework 闭环时刻的写法（JS toISOString）：UTC、毫秒。"""
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class UsageCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "proj"
        (self.root / "framework" / "skills").mkdir(parents=True)
        (self.root / "framework" / "package.json").write_text('{"version": "3.0.0"}', encoding="utf-8")
        (self.root / "framework.config.json").write_text("{}", encoding="utf-8")
        self.record = self.root / "doc" / "usage.json"

    def fr(self, feature: str = "AR1") -> Path:
        path = self.root / "doc" / "features" / feature
        path.mkdir(parents=True, exist_ok=True)
        return path

    def call(self, action: str, step: str | None = None, feature: str | None = "AR1", **extra) -> dict:
        if feature:
            self.fr(feature)
        proc = subprocess.run([sys.executable, str(USAGE), "--project-root", str(self.root)],
                              input=json.dumps({"action": action, "step": step, "feature": feature, **extra}),
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        return json.loads(proc.stdout)

    def usage(self) -> dict:
        return json.loads(self.record.read_text(encoding="utf-8"))

    def step(self, step: str, req: str = "AR1") -> dict:
        return self.usage()["requirements"][req]["steps"][step]

    def put_input(self, feature: str = "AR1", **fields) -> Path:
        path = self.fr(feature) / ".usage-input.json"
        path.write_text(json.dumps(fields, ensure_ascii=False), encoding="utf-8")
        return path

    def set_start(self, step: str, when: datetime, req: str = "AR1") -> None:
        data = self.usage()
        data["requirements"][req]["steps"][step]["start"] = at(when)
        self.record.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def close_phase(self, phase: str, when: str, feature: str = "AR1", verdict: str = "PASS",
                    closed: bool = True, subject: str = "s1") -> None:
        reports = self.fr(feature) / phase / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "summary.json").write_text(json.dumps({
            "verdict": verdict, "closure_status": "closed" if closed else "open", "verifier_subject_id": subject,
            "closure_commit": {"schema_version": "1.0", "committed_at": when, "receipt_path": f"{phase}/receipt.md"}}),
            encoding="utf-8")


class Initialisation(UsageCase):
    def test_first_use_is_kept_while_the_name_waits_then_freezes_once(self) -> None:
        out = self.call("observe", "coding")
        self.assertTrue(out["ok"] and out["pending_init"], out)
        node = self.usage()["requirements"]["AR1"]
        self.assertEqual((None, None, "3.0.0", ["AR1"]), (node["name"], node["version"], node["fw"], node["features"]))
        self.assertIn("coding", node["steps"], "待补名称时丢了已观察到的使用")
        title_only = self.put_input(requirement="AR1", name="通知订阅设置")
        out = self.call("observe", "coding")
        self.assertFalse(out["ok"])
        self.assertTrue(any("缺 version" in e for e in out["errors"]), out)
        self.assertIsNone(self.usage()["requirements"]["AR1"]["name"], "只有名称就先冻结了")
        self.assertTrue(title_only.exists(), "坏输入被清掉了，模型没东西可改")
        self.put_input(requirement="AR1", name="通知订阅设置", version=None, agent="opencode", model="m1")
        out = self.call("observe", "coding")
        node = self.usage()["requirements"]["AR1"]
        self.assertTrue(out["ok"] and not out["pending_init"], out)
        self.assertEqual(("通知订阅设置", None), (node["name"], node["version"]), "显式 null 是已判断未知")
        self.assertEqual((None, None), (node["agent"], node["model"]), "晚到的 agent/model 冒充了首次环境")
        self.assertFalse((self.fr() / ".usage-input.json").exists(), "接收后没清理输入")
        kept = self.put_input(requirement="AR1", name="改了名字", version="4.0")
        out = self.call("observe", "coding")
        self.assertTrue(any("已固定" in e for e in out["errors"]), out)
        self.assertEqual("通知订阅设置", self.usage()["requirements"]["AR1"]["name"])
        self.assertTrue(kept.exists())

    def test_the_first_observation_brings_its_environment(self) -> None:
        self.put_input(requirement="AR1", name="甲", version="4.2.0", agent="opencode", model=None)
        self.call("observe", "spec")
        node = self.usage()["requirements"]["AR1"]
        self.assertEqual(("甲", "4.2.0", "opencode", None), (node["name"], node["version"], node["agent"], node["model"]))
        self.assertTrue(node["ext"], "Extension 版本没取实际安装的 manifest")

    def test_a_feature_cannot_be_moved_to_another_requirement(self) -> None:
        self.call("observe", "spec", requirement="AR1")
        out = self.call("observe", "spec", requirement="AR2")
        self.assertFalse(out["ok"])
        self.assertIn("不跨需求改写", out["errors"][0])
        self.assertEqual(["AR1"], list(self.usage()["requirements"]))


class Writing(UsageCase):
    def test_two_requirements_written_at_once_both_survive(self) -> None:
        features = [f"AR{i}" for i in range(1, 7)]
        for f in features:
            self.fr(f)
        threads = [threading.Thread(target=self.call, args=("observe", "spec"), kwargs={"feature": f}) for f in features]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(features), sorted(self.usage()["requirements"]))

    def test_repeating_an_observation_writes_nothing(self) -> None:
        self.call("observe", "spec")
        before = self.record.read_bytes(), self.record.stat().st_mtime_ns
        out = self.call("observe", "spec")
        self.assertFalse(out["changed"])
        self.assertEqual(before, (self.record.read_bytes(), self.record.stat().st_mtime_ns))

    def test_a_broken_or_conflicted_record_is_never_overwritten(self) -> None:
        self.fr()
        self.record.parent.mkdir(parents=True, exist_ok=True)
        for name, text in {"坏 JSON": "{ 坏了", "冲突标记": '<<<<<<< HEAD\n{"schema": 1}\n=======\n{}\n>>>>>>> b\n',
                           "不支持的 schema": '{"schema": 9, "requirements": {}}',
                "节点是数组": '{"schema": 1, "requirements": {"AR1": []}}',
                "步骤字段错类型": '{"schema": 1, "requirements": {"AR1": {"name": null, "version": null, "fw": null, '
                                  '"ext": null, "agent": null, "model": null, "features": ["AR1"], "steps": {"spec": '
                                  '{"start": null, "spent": "60", "verdict": null, "completed": false, '
                                  '"last_result": null}}}}}'}.items():
            with self.subTest(name):
                self.record.write_text(text, encoding="utf-8")
                out = self.call("observe", "spec")
                self.assertFalse(out["ok"])
                self.assertEqual(text, self.record.read_text(encoding="utf-8"))

    def test_a_failed_write_keeps_the_old_record(self) -> None:
        self.call("observe", "spec")
        before = self.record.read_bytes()
        os.chmod(self.record, stat.S_IREAD)
        self.addCleanup(os.chmod, self.record, stat.S_IWRITE | stat.S_IREAD)
        out = self.call("observe", "plan")
        self.assertFalse(out["ok"])
        self.assertIn("写不进去", out["errors"][0])
        self.assertEqual(before, self.record.read_bytes())

    def test_a_lock_that_cannot_open_is_an_ordinary_record_error(self) -> None:
        self.call("observe", "spec")
        before = self.record.read_bytes()
        lock = self.record.with_name("usage.json.lock")
        os.chmod(lock, stat.S_IREAD)
        self.addCleanup(os.chmod, lock, stat.S_IWRITE | stat.S_IREAD)
        out = self.call("observe", "plan")
        self.assertEqual((False, False), (out["ok"], out["changed"]), out)
        self.assertIn("usage.json.lock", out["errors"][0])
        self.assertEqual(before, self.record.read_bytes())


class Settlement(UsageCase):
    def begun(self, step: str = "spec", minutes_ago: int = 30) -> datetime:
        self.call("begin", step)
        start = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=minutes_ago)
        self.set_start(step, start)
        return start

    def test_two_rounds_add_up_and_a_repeated_closure_counts_once(self) -> None:
        start = self.begun()
        self.close_phase("spec", at(start + timedelta(seconds=600)))
        self.call("reconcile")
        s = self.step("spec")
        self.assertEqual((600, True, None, "PASS"), (s["spent"], s["completed"], s["start"], s["verdict"]))
        self.call("reconcile")
        self.assertEqual(600, self.step("spec")["spent"], "同一闭环对账两次累计了两次")
        second = self.begun(minutes_ago=10)
        self.call("reconcile")
        self.assertEqual(at(second), self.step("spec")["start"], "旧闭环结束了新一轮")
        self.close_phase("spec", at(second + timedelta(seconds=120)), subject="s2")
        self.call("reconcile")
        self.assertEqual((720, None), (self.step("spec")["spent"], self.step("spec")["start"]))

    def test_a_middle_fail_does_not_move_the_cursor(self) -> None:
        start = self.begun()
        a = at(start + timedelta(seconds=300))
        self.close_phase("spec", a)
        self.call("reconcile")
        cursor = self.step("spec")["last_result"]
        self.close_phase("spec", a, verdict="FAIL", closed=False)
        self.call("reconcile")
        self.assertEqual(("FAIL", cursor), (self.step("spec")["verdict"], self.step("spec")["last_result"]))
        self.close_phase("spec", a)
        self.call("reconcile")
        s = self.step("spec")
        self.assertEqual((300, cursor), (s["spent"], s["last_result"]), "读回 A 被当成新完成")

    def test_an_older_snapshot_does_not_rewind(self) -> None:
        start = self.begun()
        self.close_phase("spec", at(start + timedelta(seconds=300)))
        self.call("reconcile")
        cursor = self.step("spec")["last_result"]
        self.close_phase("spec", at(start + timedelta(seconds=100)), subject="old")
        self.call("reconcile")
        self.assertEqual((cursor, 300), (self.step("spec")["last_result"], self.step("spec")["spent"]))

    def test_an_unreadable_source_is_reported_and_changes_nothing(self) -> None:
        start = self.begun()
        summary = self.fr() / "spec" / "reports" / "summary.json"
        summary.parent.mkdir(parents=True)
        summary.write_text("{ 坏了", encoding="utf-8")
        before = self.record.read_bytes()
        out = self.call("reconcile")
        self.assertFalse(out["ok"])
        self.assertIn("读不出", out["errors"][0])
        self.assertEqual(before, self.record.read_bytes())
        self.close_phase("spec", at(start + timedelta(seconds=60)))
        self.call("reconcile")
        self.call("reconcile")
        self.assertEqual(60, self.step("spec")["spent"])

    def test_a_closure_without_a_start_completes_but_time_is_unknown_for_good(self) -> None:
        self.call("observe", "coding")
        self.close_phase("coding", at(datetime.now(timezone.utc)))
        self.call("reconcile")
        s = self.step("coding")
        self.assertEqual((True, None), (s["completed"], s["spent"]))
        start = self.begun("coding", minutes_ago=5)
        self.close_phase("coding", at(start + timedelta(seconds=60)), subject="s2")
        self.call("reconcile")
        self.assertIsNone(self.step("coding")["spent"], "已未知的累计因后一轮可算被改回了精确值")

    def test_time_zones_and_zero_seconds(self) -> None:
        start = self.begun()
        east = (start + timedelta(seconds=90)).astimezone(timezone(timedelta(hours=8))).isoformat()
        self.close_phase("spec", east)
        self.call("reconcile")
        self.assertEqual(90, self.step("spec")["spent"])
        start = self.begun("plan")
        self.close_phase("plan", at(start))
        self.call("reconcile")
        self.assertEqual((0, True), (self.step("plan")["spent"], self.step("plan")["completed"]))

    def test_restore_settles_the_round_but_an_interruption_does_not(self) -> None:
        start = self.begun("story update", minutes_ago=20)
        rec = self.fr() / "AR" / "story-src" / "updates" / "r1"
        rec.mkdir(parents=True)
        self.call("abort-own", "story update")
        self.assertEqual(at(start), self.step("story update")["start"], "没有终止证据就结算了")
        (rec / "record.json").write_text(json.dumps({"id": "r1", "status": "restored",
                                                     "restored_at": at(start + timedelta(seconds=240))}), encoding="utf-8")
        self.call("abort-own", "story update")
        s = self.step("story update")
        self.assertEqual((240, False, None), (s["spent"], s["completed"], s["start"]))
        self.call("abort-own", "story update")
        self.assertEqual(240, self.step("story update")["spent"], "重复撤回改了已结算的耗时")

    def test_story_completes_only_when_registered_and_spec_closed(self) -> None:
        """Story 成文登记了而 spec 还没闭环：保留待对账；闭环后完成，结束取两者较晚的时刻。"""
        sys.path.insert(0, str(USAGE.parent))
        from flow import state  # noqa: PLC0415
        start = self.begun("story", minutes_ago=60)
        written = start + timedelta(seconds=1200)
        state.save(self.fr(), {"schema": state.SCHEMA, "rounds": [{"round": 1}], "status": "story_written",
                               "story_written_at": at(written), "story_digests": {}})
        self.call("reconcile")
        self.assertEqual((False, at(start)), (self.step("story")["completed"], self.step("story")["start"]))
        self.close_phase("spec", at(written + timedelta(seconds=600)))
        self.call("reconcile")
        s = self.step("story")
        self.assertEqual((True, 1800, None), (s["completed"], s["spent"], s["start"]))

    def test_two_features_of_one_requirement_count_once_and_time_stays_honest(self) -> None:
        start = self.begun()
        self.call("observe", "spec", feature="AR1-b", requirement="AR1")
        self.close_phase("spec", at(start + timedelta(seconds=60)))
        self.close_phase("spec", at(start + timedelta(seconds=90)), feature="AR1-b", subject="b")
        self.call("reconcile")
        data = self.usage()
        self.assertEqual(["AR1"], list(data["requirements"]))
        s = data["requirements"]["AR1"]["steps"]["spec"]
        self.assertEqual((True, None), (s["completed"], s["spent"]), "两个来源的区间归属证明不了却相加了")

    def test_one_features_start_is_not_paired_with_another_features_closure(self) -> None:
        start = self.begun()
        self.call("observe", "spec", feature="AR1-b", requirement="AR1")
        self.close_phase("spec", at(start + timedelta(seconds=60)), feature="AR1-b", subject="b")
        self.call("reconcile")
        s = self.step("spec")
        self.assertEqual((True, None, None), (s["completed"], s["spent"], s["start"]), "A 的起点配给了 B 的闭环")

    def test_a_native_millisecond_closure_settles_once_in_any_time_zone(self) -> None:
        start = self.begun()
        end = start + timedelta(seconds=60, milliseconds=500)
        self.close_phase("spec", native(end))
        self.assertTrue(self.call("reconcile")["changed"])
        settled = self.record.read_bytes()
        self.assertEqual((60, True), (self.step("spec")["spent"], self.step("spec")["completed"]))
        for _ in range(2):
            self.assertFalse(self.call("reconcile")["changed"], "同一个带毫秒的闭环被当成新事件")
        self.close_phase("spec", end.astimezone(timezone(timedelta(hours=8))).isoformat(timespec="milliseconds"))
        self.assertFalse(self.call("reconcile")["changed"], "同一时刻换成东八区写法被当成新事件")
        self.assertEqual(settled, self.record.read_bytes())
        second = self.begun(minutes_ago=10)
        self.close_phase("spec", native(second + timedelta(seconds=30, milliseconds=250)), subject="s2")
        self.call("reconcile")
        self.assertEqual((90, None), (self.step("spec")["spent"], self.step("spec")["start"]), "更晚的一轮没推进")

    def test_simultaneous_closures_settle_once_and_a_later_one_still_moves_on(self) -> None:
        start = self.begun()
        self.call("observe", "spec", feature="AR1-b", requirement="AR1")
        same = native(start + timedelta(seconds=60, milliseconds=500))
        self.close_phase("spec", same)
        self.close_phase("spec", same, feature="AR1-b", subject="b")
        self.assertTrue(self.call("reconcile")["changed"])
        settled, cursor = self.record.read_bytes(), self.step("spec")["last_result"]
        for _ in range(3):
            self.assertFalse(self.call("reconcile")["changed"], "同时刻的两个终态来回切换游标")
        self.assertEqual(settled, self.record.read_bytes())
        self.assertEqual((True, None), (self.step("spec")["completed"], self.step("spec")["spent"]))
        self.close_phase("spec", at(start + timedelta(seconds=300)), subject="s2")
        self.call("reconcile")
        self.assertNotEqual(cursor, self.step("spec")["last_result"], "真实更晚的终态推进不了游标")

    def test_a_tie_with_the_settled_closure_makes_time_unknown_once(self) -> None:
        start = self.begun("story update")
        same = at(start + timedelta(seconds=60))
        updates = self.fr() / "AR" / "story-src" / "updates"
        for rid in ("r1", "r2"):
            (updates / rid).mkdir(parents=True)
        (updates / "r1" / "record.json").write_text(json.dumps({"id": "r1", "status": "closed", "closed_at": same}),
                                                    encoding="utf-8")
        self.call("reconcile")
        self.assertEqual(60, self.step("story update")["spent"])
        (updates / "r2" / "record.json").write_text(json.dumps({"id": "r2", "status": "closed", "closed_at": same}),
                                                    encoding="utf-8")
        self.assertTrue(self.call("reconcile")["changed"])
        self.assertIsNone(self.step("story update")["spent"], "分不出先后的同刻终态却保留了精确耗时")
        self.assertFalse(self.call("reconcile")["changed"])


class TheRecordFileIsSetUpOnce(UsageCase):
    """ensure 缺了建空表、在了只核；inspect 只读；真实记录照常追加。"""

    def ensure(self) -> dict:
        return self.call("ensure", feature=None)

    def test_ensure_creates_the_empty_table_once(self) -> None:
        out = self.ensure()
        self.assertEqual((True, True), (out["ok"], out["changed"]), out)
        self.assertEqual({"schema": 1, "requirements": {}}, self.usage())
        before = self.record.read_bytes(), self.record.stat().st_mtime_ns
        self.assertFalse(self.ensure()["changed"])
        self.assertEqual(before, (self.record.read_bytes(), self.record.stat().st_mtime_ns))

    def test_inspect_only_reads(self) -> None:
        out = self.call("inspect", feature=None)
        self.assertFalse(out["ok"])
        self.assertIn("不存在", out["errors"][0])
        self.assertFalse((self.root / "doc").exists(), "只读检查建了目录")
        self.ensure()
        self.assertTrue(self.call("inspect", feature=None)["ok"])

    def test_ensure_never_rewrites_an_existing_record(self) -> None:
        self.record.parent.mkdir(parents=True, exist_ok=True)
        for text in ('{"schema":1,"requirements":{}}', "{ 坏了", '{"schema": 9, "requirements": {}}'):
            with self.subTest(text=text):
                self.record.write_text(text, encoding="utf-8")
                out = self.ensure()
                self.assertFalse(out["changed"])
                self.assertEqual(text.startswith('{"schema":1'), out["ok"], out)
                self.assertEqual(text, self.record.read_text(encoding="utf-8"))

    def test_ensure_waits_for_a_real_write_and_keeps_it(self) -> None:
        sys.path.insert(0, str(USAGE.parent))
        try:
            import usage as writer  # noqa: PLC0415
        finally:
            sys.path.remove(str(USAGE.parent))
        result: dict = {}
        with writer.locked(self.record):
            worker = threading.Thread(target=lambda: result.update(self.ensure()))
            worker.start()
            time.sleep(0.5)
            self.record.write_text('{"schema":1,"requirements":{}}', encoding="utf-8")   # 真实记录先写进来
        worker.join()
        self.assertEqual((True, False), (result["ok"], result["changed"]), result)
        self.assertEqual('{"schema":1,"requirements":{}}', self.record.read_text(encoding="utf-8"))

    def test_stdin_is_read_as_utf8_with_or_without_a_bom(self) -> None:
        """PowerShell 管道可能在开头带 BOM；输入按 UTF-8 字节读，不随控制台代码页变。"""
        for prefix in (b"", b"\xef\xbb\xbf"):
            with self.subTest(bom=bool(prefix)):
                proc = subprocess.run([sys.executable, str(USAGE), "--project-root", str(self.root)],
                                      input=prefix + b'{"action": "inspect"}', capture_output=True, timeout=60)
                self.assertNotIn("stdin 不是 JSON", proc.stdout.decode("utf-8"))

    def test_real_use_appends_to_the_set_up_record(self) -> None:
        self.ensure()
        self.call("observe", "spec")
        self.assertEqual(["AR1"], list(self.usage()["requirements"]))
        self.assertEqual(["usage.json", "usage.json.lock"],
                         sorted(p.name for p in self.record.parent.iterdir() if p.name.startswith("usage")), "多出第二份记录")


if __name__ == "__main__":
    unittest.main()
