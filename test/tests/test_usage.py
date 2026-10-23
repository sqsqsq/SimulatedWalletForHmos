"""使用记录（core/usage.py）按 V5：身份件与复合键、完成态与累计耗时、版本与自报身份、两文件写入保护。

隔离目标工程里放 framework 树、原生 summary / trace / update 记录与 Story 流程契约，经正式机器入口（stdin JSON）调用，
不写维护仓的 usage。时间区间由落盘的原生时刻与运行态起点构造。
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
import unittest.mock
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ext_workspace import DEV_EXT

CORE = DEV_EXT / "skills" / "story" / "scripts" / "core"
USAGE = CORE / "usage.py"
T0 = datetime(2026, 10, 21, 8, 0, 0, tzinfo=timezone.utc)


def at(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def native(dt: datetime) -> str:
    """Framework 时刻的写法（JS toISOString）：UTC、毫秒。"""
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class UsageCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "proj"
        (self.root / "framework" / "skills").mkdir(parents=True)
        (self.root / "framework.config.json").write_text("{}", encoding="utf-8")
        self.record = self.root / "doc" / "usage.json"
        self.state_file = self.root / "doc" / "features" / ".usage-state.json"
        # 不让临时目录外层的 Git 仓（比如用户目录本身是仓）冒充本工程的版本库
        self.env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(Path(self._tmp.name).resolve())}

    def fr(self, feature: str = "AR1") -> Path:
        path = self.root / "doc" / "features" / feature
        path.mkdir(parents=True, exist_ok=True)
        return path

    def call(self, action: str, step: str | None = None, feature: str | None = "AR1") -> dict:
        if feature:
            self.fr(feature)
        proc = subprocess.run([sys.executable, str(USAGE), "--project-root", str(self.root)],
                              input=json.dumps({"action": action, "step": step, "feature": feature}),
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
                              env=self.env)
        return json.loads(proc.stdout)

    def finalize(self, phase: str, feature: str = "AR1") -> subprocess.CompletedProcess:
        """消费模型在阶段闭环后执行的那条收尾命令，原样。"""
        return subprocess.run([sys.executable, str(USAGE), "--project-root", str(self.root), "--feature", feature,
                               "--finalize", "--phase", phase],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, env=self.env)

    def usage(self) -> dict:
        return json.loads(self.record.read_text(encoding="utf-8"))

    def key(self, feature: str = "AR1") -> str:
        return f"{feature}-{(self.fr(feature) / '.usage-id').read_text(encoding='utf-8').strip()}"

    def node(self, feature: str = "AR1") -> dict:
        return self.usage()["requirements"][self.key(feature)]

    def steps(self, feature: str = "AR1") -> dict:
        return self.node(feature)["steps"]

    def set_identity(self, when: datetime, feature: str = "AR1") -> None:
        """把身份时刻放到已知时间：Story 的起点按它算。"""
        old = self.key(feature)
        stamp = when.strftime("%Y%m%dT%H%M%S.000Z")
        (self.fr(feature) / ".usage-id").write_text(stamp + "\n", encoding="utf-8")
        data = self.usage()
        data["requirements"][f"{feature}-{stamp}"] = data["requirements"].pop(old)
        self.record.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def state(self) -> dict:
        return json.loads(self.state_file.read_text(encoding="utf-8")) if self.state_file.exists() else {}

    def set_start(self, step: str, when: datetime, feature: str = "AR1") -> None:
        st = self.state()
        st.setdefault(self.key(feature), {}).setdefault("starts", {})[step] = at(when)
        self.state_file.write_text(json.dumps(st), encoding="utf-8")

    def reports(self, phase: str, feature: str = "AR1") -> Path:
        path = self.fr(feature) / phase / "reports"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def trace(self, phase: str, when: datetime, feature: str = "AR1") -> None:
        (self.reports(phase, feature) / "trace.json").write_text(json.dumps(
            {"phase": phase, "started_at": native(when), "start_commit": "abc"}), encoding="utf-8")

    def close_phase(self, phase: str, when: datetime | None, feature: str = "AR1", gate: str = "3.0.0:e88e81fec381") -> None:
        (self.reports(phase, feature) / "summary.json").write_text(json.dumps({
            "verdict": "PASS", "closure_status": "closed" if when else "open", "gate_fingerprint": gate,
            **({"closure_commit": {"schema_version": "1.0", "committed_at": native(when)}} if when else {})}), encoding="utf-8")

    def story_written(self, when: datetime, feature: str = "AR1") -> None:
        sys.path.insert(0, str(CORE))
        from flow import state  # noqa: PLC0415
        state.save(self.fr(feature), {"schema": state.SCHEMA, "rounds": [{"round": 1}], "status": "story_written",
                                      "story_written_at": at(when), "story_digests": {}})

    def update_record(self, rid: str, opened: datetime, closed: datetime | None = None, status: str | None = None,
                      feature: str = "AR1") -> None:
        folder = self.fr(feature) / "AR" / "story-src" / "updates" / rid
        folder.mkdir(parents=True, exist_ok=True)
        rec = {"id": rid, "opened_at": at(opened), "status": status or ("closed" if closed else "open")}
        if closed:
            rec["closed_at"] = at(closed)
        (folder / "record.json").write_text(json.dumps(rec), encoding="utf-8")

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True, env=self.env)


class IdentityAndNodes(UsageCase):
    def test_init_writes_the_identity_once_and_refreshes_keep_the_key(self) -> None:
        out = self.call("init")
        self.assertTrue(out["ok"], out)
        key = self.key()
        self.assertRegex(key, r"^AR1-\d{8}T\d{6}\.\d{3}Z$")
        self.assertEqual({key: {"ext": self.node()["ext"], "fw": None, "agent": None, "model": None, "steps": {}}},
                         self.usage()["requirements"])
        for action in ("init", "refresh"):
            self.call(action)
        self.assertEqual([key], list(self.usage()["requirements"]), "刷新换了身份")

    def test_a_framework_phase_creates_the_identity_and_refresh_or_finalize_do_not(self) -> None:
        self.assertTrue(self.call("refresh", feature="AR2")["ok"])
        self.assertFalse((self.fr("AR2") / ".usage-id").exists(), "refresh 造了身份")
        self.close_phase("coding", T0, feature="AR2")
        out = self.finalize("coding", feature="AR2")
        self.assertNotEqual(0, out.returncode, "没有身份时收尾造了一个")
        self.assertIn("没有使用记录身份", out.stdout)
        self.assertFalse((self.fr("AR2") / ".usage-id").exists())
        self.call("phase", "coding", feature="AR2")
        node = self.node("AR2")
        self.assertEqual((None, None), (node["agent"], node["model"]), "纯框架使用没有自报身份")
        self.assertEqual(1, len(self.usage()["requirements"]))
        self.assertIn("未知动作 reconcile", self.call("reconcile")["errors"][0], "对账动作还在")

    def test_the_same_number_started_twice_keeps_both_once_committed(self) -> None:
        self.git("init", "-q")
        self.git("config", "user.email", "a@b")
        self.git("config", "user.name", "A")
        self.call("init")
        first = self.key()
        self.git("add", "-A")
        self.git("commit", "-qm", "first")
        (self.fr() / ".usage-id").unlink()
        self.call("init")
        self.assertIn(first, self.usage()["requirements"], "已提交的同编号节点被删了")
        self.assertEqual(2, len(self.usage()["requirements"]))

    def test_a_local_restart_replaces_only_its_uncommitted_node(self) -> None:
        self.git("init", "-q")
        self.call("init")
        self.call("init", feature="AR10")
        old, other = self.key(), self.key("AR10")
        (self.fr() / ".usage-id").unlink()
        out = self.call("init")
        self.assertTrue(out["ok"], out)
        reqs = self.usage()["requirements"]
        self.assertNotIn(old, reqs, "本地重启没替换未提交的旧节点")
        self.assertIn(other, reqs, "按编号前缀连删了别的需求")
        self.assertIn(self.key(), reqs)

    def test_without_git_an_old_node_is_kept_and_said(self) -> None:
        self.call("init")
        old = self.key()
        (self.fr() / ".usage-id").unlink()
        out = self.call("init")
        self.assertIn(old, self.usage()["requirements"], "查不了 Git 却当成未提交删了")
        self.assertTrue(any("同编号旧节点" in e for e in out["errors"]), out)


class Completion(UsageCase):
    def test_a_round_is_timed_from_its_start_and_repeated_closures_count_once(self) -> None:
        self.call("init")
        self.trace("spec", T0)
        self.call("phase", "spec")
        self.assertEqual({}, self.state(), "首轮把 trace 的起点又抄了一份")
        self.close_phase("spec", T0 + timedelta(seconds=900))
        for _ in range(2):
            self.call("refresh")
        self.assertEqual({"spent": 900}, self.steps()["spec"])
        self.assertFalse(self.state_file.exists(), "结算后留下了空的运行态")

    def test_unfinished_steps_have_no_row_and_a_retry_keeps_its_start(self) -> None:
        self.call("init")
        self.trace("plan", T0)
        self.call("phase", "plan")
        self.call("phase", "plan")
        self.assertNotIn("plan", self.steps(), "没做完的步骤出了行")
        self.close_phase("plan", T0 + timedelta(seconds=30))
        self.call("phase", "plan")          # 闭环后再跑一轮：这一轮才要自己的起点
        first = self.state()[self.key()]["starts"]["plan"]
        self.call("phase", "plan")
        self.assertEqual(first, self.state()[self.key()]["starts"]["plan"], "同一轮重复进入换了起点")
        self.assertEqual({"spent": 30}, self.steps()["plan"], "重试轮没结束就计进了 spent")

    def test_a_retry_adds_and_an_old_closure_never_ends_the_new_round(self) -> None:
        self.call("init")
        self.trace("testing", T0)
        self.call("phase", "testing")
        self.close_phase("testing", T0 + timedelta(seconds=600))
        self.call("refresh")
        self.call("phase", "testing")       # 真机没过，重进：旧闭环还在盘上
        self.set_start("testing", T0 + timedelta(seconds=1000))
        self.call("refresh")
        self.assertEqual({"spent": 600}, self.steps()["testing"], "旧闭环结算了新一轮")
        self.close_phase("testing", T0 + timedelta(seconds=1300))
        self.call("refresh")
        self.assertEqual({"spent": 900}, self.steps()["testing"])

    def test_a_revalidation_after_a_closure_keeps_the_known_time(self) -> None:
        """闭环后改稿、重新登记、再跑阶段检查：耗时累计这一段，已知的数字不被抹成未知。"""
        self.call("init")
        self.trace("spec", T0)
        self.call("phase", "spec")
        self.close_phase("spec", T0 + timedelta(seconds=2094))
        self.call("refresh")
        self.call("refresh")                # 改稿与 Story 重登记之间的刷新
        self.call("phase", "spec")          # revalidate 进入阶段检查
        self.set_start("spec", T0 + timedelta(seconds=2500))
        self.close_phase("spec", T0 + timedelta(seconds=2560))
        self.call("refresh")
        self.assertEqual({"spent": 2154}, self.steps()["spec"])

    def test_a_closure_without_any_start_shows_the_row_and_keeps_known_time(self) -> None:
        self.call("init")
        self.close_phase("review", T0)
        self.call("refresh")
        self.assertEqual({}, self.steps()["review"], "完成过却没有行，或编了耗时")
        self.call("phase", "review")
        self.set_start("review", T0 + timedelta(seconds=100))
        self.close_phase("review", T0 + timedelta(seconds=160))
        self.call("refresh")
        self.assertEqual({"spent": 60}, self.steps()["review"], "只累计可核实的轮次")
        self.state_file.unlink(missing_ok=True)     # 运行态丢了：已累计的不受影响
        self.close_phase("review", T0 + timedelta(seconds=400))
        self.call("refresh")
        self.assertEqual({"spent": 60}, self.steps()["review"])

    def test_an_interruption_keeps_the_start_and_counts_once_closed(self) -> None:
        """首轮被中断：起点仍是 trace，不计 spent；闭环后这一轮从 trace 起点算到闭环，中间的等待与中断都在里面。"""
        self.call("init")
        self.trace("coding", T0)
        self.call("phase", "coding")
        self.close_phase("coding", None)
        self.call("refresh")
        self.assertNotIn("coding", self.steps())
        self.call("phase", "coding")        # 中断后重进同一轮
        self.close_phase("coding", T0 + timedelta(hours=2))
        self.call("refresh")
        self.assertEqual({"spent": 7200}, self.steps()["coding"])

    def test_story_counts_from_the_identity_to_its_first_registration(self) -> None:
        self.call("init")
        self.set_identity(T0)
        self.story_written(T0 + timedelta(seconds=1656))
        self.call("refresh")
        self.assertEqual({"spent": 1656}, self.steps()["story"], "Story 不等 Spec 闭环就算完成")
        self.story_written(T0 + timedelta(seconds=9000))   # 修稿后重新登记
        self.call("refresh")
        self.assertEqual({"spent": 1656}, self.steps()["story"], "重新登记重复计了")

    def test_update_rounds_come_from_the_records_even_without_local_state(self) -> None:
        self.call("init")
        self.update_record("u1", T0)
        self.call("refresh")
        self.assertNotIn("story update", self.steps(), "没收口就出了行")
        self.state_file.unlink(missing_ok=True)      # 本地运行态丢了
        self.update_record("u1", T0, T0 + timedelta(seconds=300))
        for _ in range(3):
            self.call("refresh")
        self.assertEqual({"spent": 300, "rounds": 1}, self.steps()["story update"], "丢了运行态就丢了收口轮数")
        self.update_record("u2", T0 + timedelta(seconds=1000))
        self.call("refresh")
        self.assertEqual({"spent": 300, "rounds": 1}, self.steps()["story update"], "开着的一轮被算了进去")
        self.update_record("u2", T0 + timedelta(seconds=1000), T0 + timedelta(seconds=1100))
        self.call("refresh")
        self.assertEqual({"spent": 400, "rounds": 2}, self.steps()["story update"])

    def test_restores_baselines_and_missing_starts(self) -> None:
        """没收口就撤回不计；收口后再撤回仍是收口过一轮；缺起点的轮只计轮数；baseline 不算一轮。"""
        self.call("init")
        self.update_record("u1", T0, T0 + timedelta(seconds=60), status="restored")      # 收口后撤回：closed_at 留着
        self.update_record("u2", T0 + timedelta(seconds=500), status="restored")          # 没收口就撤回
        folder = self.fr() / "AR" / "story-src" / "updates"
        (folder / "u3").mkdir(parents=True)
        (folder / "u3" / "record.json").write_text(json.dumps(
            {"id": "u3", "status": "closed", "closed_at": at(T0 + timedelta(seconds=900))}), encoding="utf-8")
        (folder / "u0").mkdir(parents=True)
        (folder / "u0" / "record.json").write_text(json.dumps(
            {"id": "u0", "kind": "story_baseline", "status": "closed", "closed_at": at(T0)}), encoding="utf-8")
        self.call("refresh")
        self.assertEqual({"spent": 60, "rounds": 2}, self.steps()["story update"])

    def test_a_failed_usage_write_keeps_the_update_round_once(self) -> None:
        self.call("init")
        self.update_record("u1", T0, T0 + timedelta(seconds=120))
        sys.path.insert(0, str(CORE))
        import usage  # noqa: PLC0415
        real, calls = usage.write_json, []

        def flaky(path, data):
            calls.append(path.name)
            if path.name == "usage.json" and calls.count("usage.json") == 1:
                raise usage.UsageError("磁盘写保护（注入）")
            return real(path, data)

        usage.write_json = flaky
        try:
            self.assertFalse(usage.record(self.root, "refresh", feature="AR1")["ok"])
        finally:
            usage.write_json = real
        self.call("refresh")
        self.call("refresh")
        self.assertEqual({"spent": 120, "rounds": 1}, self.steps()["story update"])


class TheExtensionClosesTheStep(UsageCase):
    """阶段原生闭环后的 Extension 收尾：最后一步不靠下一阶段、story 命令或 stats 就进 usage；失败重跑同一命令即收敛。"""

    PHASES = ("spec", "plan", "coding", "review", "ut", "testing")

    def test_every_phase_can_be_the_last_one(self) -> None:
        for phase in self.PHASES:
            with self.subTest(phase=phase):
                feature = f"F-{phase}"
                self.trace(phase, T0, feature=feature)
                self.call("phase", phase, feature=feature)       # 纯框架需求：pre_phase 建身份
                self.close_phase(phase, T0 + timedelta(seconds=75), feature=feature)
                out = self.finalize(phase, feature=feature)
                self.assertEqual(0, out.returncode, out.stderr)
                said = json.loads(out.stdout)
                self.assertEqual((phase, {"spent": 75}, False), (said["phase"], said["recorded"], said["timing_gap"]))
                self.assertEqual({"spent": 75}, self.steps(feature)[phase], "最后一步没落进 usage")
        self.assertFalse(self.state_file.exists(), "收尾之后留着运行态")

    def test_the_finalize_is_idempotent_and_never_reopens(self) -> None:
        self.call("init")
        self.trace("spec", T0)
        self.call("phase", "spec")
        self.call("phase", "spec")                  # 同一轮门禁又跑了一次
        self.close_phase("spec", T0 + timedelta(seconds=600))
        for _ in range(3):
            self.assertEqual(0, self.finalize("spec").returncode)
            self.call("refresh")
        self.assertEqual({"spent": 600}, self.steps()["spec"], "重复收尾或刷新多记了")
        summary = json.loads((self.reports("spec") / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual("closed", summary["closure_status"], "收尾改了原生闭环")

    def test_an_unclosed_phase_is_refused_and_records_nothing(self) -> None:
        self.call("init")
        self.trace("ut", T0)
        self.call("phase", "ut")
        out = self.finalize("ut")
        self.assertNotEqual(0, out.returncode)
        self.assertIn("还没有原生有效闭环", out.stdout)
        self.assertIn("先完成阶段", out.stderr)
        self.assertNotIn("已闭环", out.stderr, "没闭环却说业务已闭环")
        self.assertNotIn("ut", self.steps(), "没闭环却记了一行")

    def test_a_closed_phase_that_cannot_be_written_says_why(self) -> None:
        """闭环成立而记录写不进：报出写不进的原因，不说没闭环；修好后重跑同一条就记上。"""
        self.call("init")
        self.trace("ut", T0)
        self.close_phase("ut", T0 + timedelta(seconds=20))
        lock = self.record.with_name("usage.json.lock")
        lock.unlink(missing_ok=True)
        lock.mkdir()                                    # 锁文件位置被目录占住：记录器打不开
        out = self.finalize("ut")
        self.assertNotEqual(0, out.returncode)
        self.assertIn("打不开", out.stdout)
        self.assertNotIn("还没有原生有效闭环", out.stdout + out.stderr)
        self.assertIn("重跑同一条收尾命令", out.stderr)
        lock.rmdir()
        self.assertEqual(0, self.finalize("ut").returncode)
        self.assertEqual({"spent": 20}, self.steps()["ut"])

    def test_a_closure_without_a_start_is_recorded_without_inventing_time(self) -> None:
        self.call("init")
        self.close_phase("review", T0)
        said = json.loads(self.finalize("review").stdout)
        self.assertEqual(({}, True), (said["recorded"], said["timing_gap"]), "缺起点的完成行编了耗时或没出现")

    def test_milliseconds_are_kept_until_the_difference(self) -> None:
        self.call("init")
        (self.reports("spec") / "trace.json").write_text(json.dumps(
            {"phase": "spec", "started_at": "2026-10-21T08:00:00.900Z"}), encoding="utf-8")
        self.close_phase("spec", T0 + timedelta(seconds=10, milliseconds=600))
        self.finalize("spec")
        self.assertEqual({"spent": 10}, self.steps()["spec"], "起止各截到秒再相减，差出 1 秒")
        self.call("phase", "spec")
        self.assertRegex(self.state()[self.key()]["starts"]["spec"], r"\.\d{3}Z$", "重试轮起点丢了毫秒")

    def inject(self, fail_on: str):
        """进程内调记录器，让 `fail_on` 那份文件第一次写失败；返回模块与撤掉注入的函数。"""
        sys.path.insert(0, str(CORE))
        import usage  # noqa: PLC0415
        real, seen = usage.write_json, []

        def flaky(path, data):
            seen.append(path.name)
            if path.name == fail_on and seen.count(fail_on) == 1:
                raise usage.UsageError(f"{fail_on} 写不进去（注入）")
            return real(path, data)

        usage.write_json = flaky
        restore = lambda: setattr(usage, "write_json", real)  # noqa: E731
        self.addCleanup(restore)
        return usage, restore

    def test_failures_converge_by_retrying_the_finalize(self) -> None:
        """usage 写失败、运行态写失败：业务闭环不回退，重跑收尾后只记一次，不需要 stats 补。"""
        for fail_on in ("usage.json", ".usage-state.json"):
            with self.subTest(fail_on=fail_on):
                feature = f"R{len(fail_on)}"
                self.call("init", feature=feature)
                self.call("phase", "spec", feature=feature)
                self.close_phase("spec", T0, feature=feature)
                self.call("phase", "spec", feature=feature)           # 闭环后再跑一轮：有了重试起点
                start = self.state()[self.key(feature)]["starts"]["spec"]
                self.close_phase("spec", datetime.fromisoformat(start.replace("Z", "+00:00")) + timedelta(seconds=40),
                                 feature=feature)
                usage, restore = self.inject(fail_on)
                out = usage.record(self.root, "finalize", feature=feature, step="spec")
                self.assertFalse(out["ok"], "写失败却报收尾成功")
                restore()
                for _ in range(2):
                    self.assertEqual(0, self.finalize("spec", feature=feature).returncode)
                self.assertEqual({"spent": 40}, self.steps(feature)["spec"], "失败后重试重复累加或丢了")

    def test_a_cleanup_failure_is_reported_and_converges(self) -> None:
        self.call("init")
        self.trace("spec", T0)
        self.close_phase("spec", T0 + timedelta(seconds=5))
        self.call("phase", "spec")
        start = datetime.fromisoformat(self.state()[self.key()]["starts"]["spec"].replace("Z", "+00:00"))
        self.close_phase("spec", start + timedelta(seconds=7))
        sys.path.insert(0, str(CORE))
        import usage  # noqa: PLC0415
        real = Path.unlink

        def busy(path, *a, **k):
            if path.name == ".usage-state.json":
                raise OSError("被占用（注入）")
            return real(path, *a, **k)

        with unittest.mock.patch.object(Path, "unlink", busy):
            out = usage.record(self.root, "finalize", feature="AR1", step="spec")
        self.assertFalse(out["ok"])
        self.assertTrue(any("清不掉" in e for e in out["errors"]), out)
        self.assertEqual(0, self.finalize("spec").returncode)
        self.assertEqual({"spent": 12}, self.steps()["spec"])
        self.assertFalse(self.state_file.exists())


class TheLocalStateIsMinimal(UsageCase):
    def test_init_story_and_update_leave_no_empty_state(self) -> None:
        self.call("init")
        self.set_identity(T0)
        self.story_written(T0 + timedelta(seconds=30))
        self.call("refresh")
        self.update_record("u1", T0, T0 + timedelta(seconds=60))
        self.call("refresh")
        self.assertEqual({"story": {"spent": 30}, "story update": {"spent": 60, "rounds": 1}}, self.steps())
        self.assertFalse(self.state_file.exists(), "init / Story / update 留下了运行态")

    def test_pending_only_carries_what_this_settlement_changed(self) -> None:
        self.call("init")
        self.close_phase("plan", T0)
        self.finalize("plan")
        self.trace("spec", T0)
        self.close_phase("spec", T0 + timedelta(seconds=9))
        usage, _ = TheExtensionClosesTheStep.inject(self, "usage.json")
        self.assertFalse(usage.record(self.root, "finalize", feature="AR1", step="spec")["ok"])
        self.assertEqual({"spec": {"spent": 9}}, self.state()[self.key()]["pending"], "待写里带了别的完成历史")

    def test_a_version_or_input_change_alone_does_not_stage_steps(self) -> None:
        self.call("init")
        self.close_phase("plan", T0)
        self.finalize("plan")
        (self.fr() / ".usage-input.json").write_text('{"agent": "a", "model": "m"}', encoding="utf-8")
        self.call("refresh")
        self.assertEqual(("a", "m"), (self.node()["agent"], self.node()["model"]))
        self.assertFalse(self.state_file.exists(), "只改自报身份也建了运行态")


class VersionsAndIdentity(UsageCase):
    def test_versions_follow_the_last_activity(self) -> None:
        self.call("init")
        node = self.node()
        self.assertIsNone(node["fw"], "没有 summary 却填了 Framework 版本")
        manifest = (DEV_EXT / "manifest.yaml").read_text(encoding="utf-8")
        self.assertIn(f'version: "{node["ext"]}"' if f'version: "{node["ext"]}"' in manifest else f"version: {node['ext']}",
                      manifest, "ext 不是已装 manifest 的版本")
        self.close_phase("spec", T0, gate="3.0.0:aaaa")
        self.call("refresh")
        self.assertEqual("3.0.0", self.node()["fw"])

    def test_the_self_report_is_taken_once_and_story_needs_it(self) -> None:
        self.call("init")
        (self.fr() / "AR" / "story-src").mkdir(parents=True, exist_ok=True)
        self.story_written(T0)
        out = self.call("refresh")
        self.assertTrue(out["pending_identity"], out)
        self.assertIn(".usage-input.json", out["note"])
        path = self.fr() / ".usage-input.json"
        path.write_text(json.dumps({"agent": "dsh", "model": "m1"}), encoding="utf-8")
        out = self.call("refresh")
        self.assertEqual(("dsh", "m1", False), (self.node()["agent"], self.node()["model"], out["pending_identity"]))
        self.assertFalse(path.exists(), "接收后输入没删")
        path.write_text(json.dumps({"agent": "codex", "model": "m2"}), encoding="utf-8")
        self.call("refresh")
        self.assertEqual(("dsh", "m1"), (self.node()["agent"], self.node()["model"]), "换会话改了已固定的身份")

    def test_a_pure_framework_requirement_is_not_asked(self) -> None:
        out = self.call("phase", "coding")
        self.assertFalse(out["pending_identity"], "纯框架使用没有填写时机，不该催")


class WriteProtection(UsageCase):
    def test_two_requirements_written_at_once_both_survive(self) -> None:
        threads = [threading.Thread(target=self.call, args=("init", None, f"AR{i}")) for i in range(1, 5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(4, len(self.usage()["requirements"]))

    def test_a_broken_conflicted_or_old_record_is_never_overwritten(self) -> None:
        self.record.parent.mkdir(parents=True)
        for text, said in (("{坏", "不是合法 JSON"), ('<<<<<<< HEAD\n{}\n=======\n{}\n>>>>>>> x\n', "冲突标记"),
                           ('{"schema": 1, "requirements": {"AR1": {"name": "甲", "version": null, "features": ["AR1"], '
                            '"fw": null, "ext": null, "agent": null, "model": null, "steps": {}}}}', "旧合同")):
            with self.subTest(said):
                self.record.write_text(text, encoding="utf-8")
                out = self.call("init")
                self.assertFalse(out["ok"])
                self.assertTrue(any(said in e for e in out["errors"]), out)
                self.assertEqual(text, self.record.read_text(encoding="utf-8"))

    def test_a_failed_usage_write_does_not_count_twice(self) -> None:
        """运行态已清起点、usage 没写成：下一次刷新按运行态里的待写行赋值，不再加一遍。"""
        self.call("init")
        self.trace("spec", T0)
        self.call("phase", "spec")
        self.close_phase("spec", T0 + timedelta(seconds=500))
        sys.path.insert(0, str(CORE))
        import usage  # noqa: PLC0415
        real = usage.write_json
        calls = []

        def flaky(path, data):
            calls.append(path.name)
            if path.name == "usage.json" and calls.count("usage.json") == 1:
                raise usage.UsageError("磁盘写保护（注入）")
            return real(path, data)

        usage.write_json = flaky
        try:
            first = usage.record(self.root, "refresh", feature="AR1")
        finally:
            usage.write_json = real
        self.assertFalse(first["ok"])
        self.assertNotIn("spec", self.steps(), "失败的那次写进了 usage")
        self.call("refresh")
        self.call("refresh")
        self.assertEqual({"spent": 500}, self.steps()["spec"])

    def test_a_lock_that_cannot_open_is_an_ordinary_record_error(self) -> None:
        self.call("init")
        before = self.record.read_bytes()
        lock = self.record.with_name("usage.json.lock")
        lock.unlink(missing_ok=True)
        lock.mkdir()
        out = self.call("refresh")
        self.assertFalse(out["ok"])
        self.assertEqual(before, self.record.read_bytes())

    def test_stdin_is_read_as_utf8_with_or_without_a_bom(self) -> None:
        for raw in (b'{"action": "init", "feature": "AR1"}', b'\xef\xbb\xbf{"action": "refresh", "feature": "AR1"}'):
            self.fr()
            proc = subprocess.run([sys.executable, str(USAGE), "--project-root", str(self.root)], input=raw,
                                  capture_output=True, timeout=60)
            self.assertEqual(0, proc.returncode, proc.stderr.decode("utf-8", "replace"))


class TheRecordFileIsSetUpOnce(UsageCase):
    def test_ensure_creates_the_empty_table_once_and_never_rewrites(self) -> None:
        self.assertTrue(self.call("ensure", feature=None)["changed"])
        self.assertEqual({"schema": 1, "requirements": {}}, self.usage())
        self.call("init")
        before = self.record.read_bytes()
        out = self.call("ensure", feature=None)
        self.assertEqual((True, False), (out["ok"], out["changed"]))
        self.assertEqual(before, self.record.read_bytes())

    def test_inspect_only_reads(self) -> None:
        out = self.call("inspect", feature=None)
        self.assertFalse(out["ok"])
        self.assertFalse(self.record.parent.exists(), "只读检查建了目录")

    def test_ensure_refuses_a_read_only_directory_without_damage(self) -> None:
        if os.name == "nt":
            self.skipTest("Windows 上目录只读位不阻止写入")
        self.record.parent.mkdir(parents=True)
        self.record.parent.chmod(stat.S_IREAD | stat.S_IEXEC)
        self.addCleanup(self.record.parent.chmod, stat.S_IRWXU)
        self.assertFalse(self.call("ensure", feature=None)["ok"])


if __name__ == "__main__":
    unittest.main()
