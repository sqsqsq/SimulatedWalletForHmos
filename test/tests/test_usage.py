"""使用记录（core/usage.py）按 V5：身份件与复合键、完成态与累计耗时、版本与自报身份、两文件写入保护。

隔离目标工程里放 framework 树、原生 summary / update 记录与 Story 流程契约，经正式机器入口（stdin JSON / CLI）调用，
不写维护仓的 usage。阶段的起止是 begin 与收尾那一刻的机器时刻：算术用例在进程内固定记录器的时钟（`at_time`），
起点仍由 begin 动作产生，不往运行态里手填。
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
FLOW = CORE / "story_flow.py"
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
                      feature: str = "AR1", begun: bool = True) -> None:
        """一轮 update 的原生记录；`begun` 表示开轮时有 begin 的起点移进来（记成 started_at，取开轮时刻）。"""
        folder = self.fr(feature) / "AR" / "story-src" / "updates" / rid
        folder.mkdir(parents=True, exist_ok=True)
        rec = {"id": rid, "opened_at": at(opened), **({"started_at": at(opened)} if begun else {}),
               "status": status or ("closed" if closed else "open")}
        if closed:
            rec["closed_at"] = at(closed)
        (folder / "record.json").write_text(json.dumps(rec), encoding="utf-8")

    def story_init(self, feature: str = "AR1") -> dict:
        """真实的 `story_flow.py init`：建骨架，成功后由它调记录器的 init 动作（时刻取真实时钟，init 不记时刻）。"""
        proc = subprocess.run([sys.executable, str(FLOW), "init", "--feature", feature, "--project-root", str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90, env=self.env)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout[proc.stdout.index("{"):])

    def story_done(self, when: datetime, feature: str = "AR1") -> dict:
        """`story_flow.py story` 登记成功之后的那次回调（`after_command` 的 story 分支），成功时刻固定在 `when`。"""
        sys.path.insert(0, str(CORE))
        import usage  # noqa: PLC0415
        self.fr(feature)
        with unittest.mock.patch.object(usage, "now", return_value=when), \
                unittest.mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": self.env["GIT_CEILING_DIRECTORIES"]}):
            return usage.after_command(self.root, feature, "story")

    def story_start(self, feature: str = "AR1") -> object:
        """运行态里 Story 的起点：没有这个键时返回字符串 "absent"，好和 null 分开。"""
        return self.state().get(self.key(feature), {}).get("starts", {}).get("story", "absent")

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True, env=self.env)

    def at_time(self, action: str, step: str | None = None, when: datetime = T0, feature: str = "AR1") -> dict:
        """进程内调正式记录器，机器时钟固定在 `when`：begin 与收尾各取这一刻，耗时就能复算。"""
        sys.path.insert(0, str(CORE))
        import usage  # noqa: PLC0415
        self.fr(feature)
        with unittest.mock.patch.object(usage, "now", return_value=when), \
                unittest.mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": self.env["GIT_CEILING_DIRECTORIES"]}):
            return usage.record(self.root, action, feature=feature, step=step)


class IdentityAndNodes(UsageCase):
    def test_begin_writes_the_identity_once_and_init_or_refresh_keep_the_key(self) -> None:
        out = self.call("begin", "story")
        self.assertTrue(out["ok"], out)
        key = self.key()
        self.assertRegex(key, r"^AR1-\d{8}T\d{6}\.\d{3}Z$")
        self.assertEqual({key: {"ext": self.node()["ext"], "fw": None, "agent": None, "model": None, "steps": {}}},
                         self.usage()["requirements"])
        for action in ("init", "refresh"):
            self.call(action)
        self.assertEqual([key], list(self.usage()["requirements"]), "init 或刷新换了身份")

    def test_init_without_a_begin_makes_the_identity_but_not_a_start(self) -> None:
        """身份只标识需求：init 可以建它，但 Story 的起点记成未知（null），不写 init 时刻，也不出完成行。"""
        out = self.call("init")
        self.assertTrue(out["ok"], out)
        self.assertIn("没有开始记录", out["note"], "漏了 begin 没说")
        self.assertEqual({}, self.steps(), "还没成文就出了 Story 行")
        self.assertIsNone(self.story_start(), "init 写了一个起点，或没记下起点未知")

    def test_a_framework_phase_creates_the_identity_and_refresh_or_finalize_do_not(self) -> None:
        self.assertTrue(self.call("refresh", feature="AR2")["ok"])
        self.assertFalse((self.fr("AR2") / ".usage-id").exists(), "refresh 造了身份")
        self.close_phase("coding", T0, feature="AR2")
        out = self.finalize("coding", feature="AR2")
        self.assertNotEqual(0, out.returncode, "没有身份时收尾造了一个")
        self.assertIn("没有使用记录身份", out.stdout)
        self.assertFalse((self.fr("AR2") / ".usage-id").exists())
        self.call("begin", "coding", feature="AR2")          # 纯框架需求：开始工作就建身份
        node = self.node("AR2")
        self.assertEqual((None, None), (node["agent"], node["model"]), "纯框架使用没有自报身份")
        self.assertEqual(1, len(self.usage()["requirements"]))
        self.assertIn("coding", self.state()[self.key("AR2")]["starts"])
        for retired in ("reconcile", "phase"):
            self.assertIn(f"未知动作 {retired}", self.call(retired, "coding")["errors"][0], f"{retired} 动作还在")

    def test_the_same_number_started_twice_keeps_both_once_committed(self) -> None:
        self.git("init", "-q")
        self.git("config", "user.email", "a@b")
        self.git("config", "user.name", "A")
        self.call("begin", "story")
        first = self.key()
        self.git("add", "-A")
        self.git("commit", "-qm", "first")
        (self.fr() / ".usage-id").unlink()
        self.call("begin", "story")
        self.assertIn(first, self.usage()["requirements"], "已提交的同编号节点被删了")
        self.assertEqual(2, len(self.usage()["requirements"]))

    def test_a_local_restart_replaces_only_its_uncommitted_node(self) -> None:
        self.git("init", "-q")
        self.call("begin", "story")
        self.call("begin", "story", feature="AR10")
        old, other = self.key(), self.key("AR10")
        (self.fr() / ".usage-id").unlink()
        out = self.call("begin", "story")
        self.assertTrue(out["ok"], out)
        reqs = self.usage()["requirements"]
        self.assertNotIn(old, reqs, "本地重启没替换未提交的旧节点")
        self.assertIn(other, reqs, "按编号前缀连删了别的需求")
        self.assertIn(self.key(), reqs)

    def test_without_git_an_old_node_is_kept_and_said(self) -> None:
        self.call("begin", "story")
        old = self.key()
        (self.fr() / ".usage-id").unlink()
        out = self.call("begin", "story")
        self.assertIn(old, self.usage()["requirements"], "查不了 Git 却当成未提交删了")
        self.assertTrue(any("同编号旧节点" in e for e in out["errors"]), out)


class Completion(UsageCase):
    """阶段一轮从 begin 到收尾请求那一刻；原生闭环只是完成资格（此刻有、且不早于本轮开始）。中途的检查、刷新与闭环
    不开始也不结算；闭环早于开始的旧事实不结算；漏了 begin 的完成只出行、记缺口；重复 begin 保留最早，重复收尾不加。"""

    def test_a_round_runs_from_begin_to_the_finalize_request(self) -> None:
        """T0 开始工作，T1 写稿，T2 第一次检查，T3 闭环，T4 收尾：记 T4−T0，不是 T3−T2。"""
        self.at_time("begin", "spec", T0)
        self.trace("spec", T0 + timedelta(seconds=1200))            # 检查不是开始
        self.close_phase("spec", T0 + timedelta(seconds=1500))
        for _ in range(2):
            self.call("refresh")
        self.assertNotIn("spec", self.steps(), "刷新提前结算了阶段")
        self.at_time("finalize", "spec", T0 + timedelta(seconds=1800))
        self.assertEqual({"spent": 1800}, self.steps()["spec"])
        self.at_time("finalize", "spec", T0 + timedelta(seconds=2500))
        self.assertEqual({"spent": 1800}, self.steps()["spec"], "重复收尾多记了")
        self.assertFalse(self.state_file.exists(), "结算后留下了空的运行态")

    def test_an_intermediate_closure_and_rework_stay_in_the_round(self) -> None:
        self.at_time("begin", "spec", T0)
        self.close_phase("spec", T0 + timedelta(seconds=2143))
        self.call("refresh")
        self.at_time("begin", "spec", T0 + timedelta(seconds=2200))   # 返修时又跑了一次入口：起点不换
        self.close_phase("spec", T0 + timedelta(seconds=5046))
        self.at_time("finalize", "spec", T0 + timedelta(seconds=5100))
        self.assertEqual({"spent": 5100}, self.steps()["spec"], "中途闭环切掉了后面的返修")

    def test_an_unclosed_round_is_not_settled_and_keeps_its_start(self) -> None:
        self.at_time("begin", "plan", T0)
        self.assertNotIn("plan", self.steps(), "没做完的步骤出了行")
        out = self.at_time("finalize", "plan", T0 + timedelta(seconds=20))
        self.assertFalse(out["ok"], "没闭环却收了尾")
        self.close_phase("plan", T0 + timedelta(seconds=25))
        self.at_time("finalize", "plan", T0 + timedelta(seconds=30))
        self.assertEqual({"spent": 30}, self.steps()["plan"])

    def test_a_new_round_needs_a_new_closure(self) -> None:
        self.at_time("begin", "testing", T0)
        self.close_phase("testing", T0 + timedelta(seconds=500))
        self.at_time("finalize", "testing", T0 + timedelta(seconds=600))
        self.at_time("begin", "testing", T0 + timedelta(seconds=1000))      # 真机没过，重新开始：旧闭环还在盘上
        out = self.at_time("finalize", "testing", T0 + timedelta(seconds=1100))
        self.assertTrue(out["ok"], out)
        self.assertIn("还没有新的闭环", out["note"], "旧闭环被当成新一轮的完成")
        self.assertEqual({"spent": 600}, self.steps()["testing"])
        self.close_phase("testing", T0 + timedelta(seconds=1250))
        self.at_time("finalize", "testing", T0 + timedelta(seconds=1300))
        self.assertEqual({"spent": 900}, self.steps()["testing"])

    def test_a_missing_begin_is_a_gap_and_nothing_fills_it(self) -> None:
        self.call("begin", "story")
        self.trace("review", T0)                                        # trace 与检查不能当起点
        self.close_phase("review", T0 + timedelta(seconds=60))
        out = self.at_time("finalize", "review", T0 + timedelta(seconds=90))
        self.assertEqual({}, self.steps()["review"], "缺起点的完成编了耗时或没出行")
        self.assertIn("没有开始记录", out["note"])
        self.at_time("begin", "review", T0 + timedelta(seconds=100))
        self.close_phase("review", T0 + timedelta(seconds=150))
        self.at_time("finalize", "review", T0 + timedelta(seconds=160))
        self.assertEqual({"spent": 60}, self.steps()["review"], "只累计可核实的轮次")
        self.state_file.unlink(missing_ok=True)                         # 运行态丢了：已累计的不受影响
        self.close_phase("review", T0 + timedelta(seconds=400))
        self.at_time("finalize", "review", T0 + timedelta(seconds=410))
        self.assertEqual({"spent": 60}, self.steps()["review"])

    def test_waiting_and_interruptions_are_inside_the_round(self) -> None:
        self.at_time("begin", "coding", T0)
        self.close_phase("coding", None)
        self.call("refresh")
        self.at_time("begin", "coding", T0 + timedelta(hours=1))        # 中断后回来
        self.close_phase("coding", T0 + timedelta(hours=1, minutes=50))
        self.at_time("finalize", "coding", T0 + timedelta(hours=2))
        self.assertEqual({"spent": 7200}, self.steps()["coding"])

    def test_an_update_close_settles_only_the_phases_this_round_began(self) -> None:
        self.at_time("begin", "spec", T0)
        self.close_phase("spec", T0 + timedelta(seconds=50))
        self.at_time("finalize", "spec", T0 + timedelta(seconds=100))
        self.close_phase("plan", T0 + timedelta(seconds=50))            # 这一轮没开始过的阶段
        self.at_time("begin", "spec", T0 + timedelta(seconds=200))      # update 里重新做 spec
        self.at_time("begin", "ut", T0 + timedelta(seconds=210))        # 开始了还没闭环
        self.close_phase("spec", T0 + timedelta(seconds=250))
        out = self.at_time("close", None, T0 + timedelta(seconds=260))
        self.assertTrue(out["ok"], out)
        self.assertEqual({"spent": 160}, self.steps()["spec"], "update 收口没结算这一轮做过的阶段")
        self.assertNotIn("plan", self.steps(), "没开始的阶段也被收了尾")
        self.assertNotIn("ut", self.steps(), "没闭环的阶段被收了尾")
        self.assertIn("ut", self.state()[self.key()]["starts"], "没闭环的阶段丢了起点")
        self.at_time("close", None, T0 + timedelta(seconds=300))
        self.at_time("finalize", "spec", T0 + timedelta(seconds=310))
        self.assertEqual({"spent": 160}, self.steps()["spec"], "update 收口与收尾重复累计")

    def test_story_runs_from_its_begin_to_each_successful_registration(self) -> None:
        """用户预放了材料，模型照常取材前 begin、再真实 init、成文：计完整跨度。预放的材料不是开工证据；
        重复 begin / init / refresh 不重启身份、不改起点。之后真正再开一轮（begin）并登记成功，累计；
        内容没变、盘上成文时间也没变的那一轮同样累计；没有新 begin 的重复登记不加。"""
        (self.fr() / "inbox").mkdir()
        (self.fr() / "inbox" / "requirements.md").write_text("用户预放的需求材料\n", encoding="utf-8")
        self.at_time("begin", "story", T0)
        key = self.key()
        self.assertEqual(native(T0), self.story_start(), "正常 begin 没记下起点")
        self.at_time("begin", "story", T0 + timedelta(seconds=30))
        self.story_init()                                               # 取材之后才 init：起点不是它
        self.assertEqual((key, native(T0)), (self.key(), self.story_start()), "init 或重复 begin 改了身份或起点")
        self.assertNotIn("story", self.steps(), "还没成文就出了 Story 行")
        self.story_written(T0 + timedelta(seconds=900))
        self.call("refresh")
        self.assertNotIn("story", self.steps(), "刷新拿盘上的成文时间结算了 Story")
        self.story_done(T0 + timedelta(seconds=900))
        self.assertEqual({"spent": 900}, self.steps()["story"], "Story 不是从开始工作算起")
        self.assertEqual("absent", self.story_start(), "结算后起点还留着")
        self.story_done(T0 + timedelta(seconds=950))                    # 没有新 begin 的重复登记
        self.assertEqual({"spent": 900}, self.steps()["story"], "重复登记多记了")
        self.at_time("begin", "story", T0 + timedelta(seconds=1000))   # 返修：再开一轮
        self.story_init()
        self.call("refresh")                                            # 盘上旧成文时间 + 刷新：不收这一轮
        self.assertEqual(({"spent": 900}, native(T0 + timedelta(seconds=1000))), (self.steps()["story"], self.story_start()))
        self.story_done(T0 + timedelta(seconds=1100))                   # 内容没变、成文时间没变也算这一轮
        self.at_time("begin", "story", T0 + timedelta(seconds=2000))
        self.story_done(T0 + timedelta(seconds=2010))
        self.assertEqual((key, {"spent": 1010}, "absent"), (self.key(), self.steps()["story"], self.story_start()))

    def test_a_missed_begin_leaves_the_story_start_unknown(self) -> None:
        """漏了取材前的 begin：真实 init 记起点未知；迟到的 begin 保持未知；成文之前没有 Story 行，
        登记成功后只出缺口行，不拿 init 或迟到 begin 的时刻补。usage 写失败时缺口行照待写赋值。"""
        for late in (True, False):
            with self.subTest(late_begin=late):
                feature = f"M{int(late)}"
                said = self.story_init(feature)
                self.assertIn("没有开始记录", said.get("usage_note", ""), said)
                self.assertIsNone(self.story_start(feature))
                if late:
                    out = self.at_time("begin", "story", T0 + timedelta(seconds=60), feature=feature)
                    self.assertIn("起点不可核", out["note"])
                    self.assertIsNone(self.story_start(feature), "迟到的 begin 补成了时刻")
                self.story_init(feature)                                 # 重复 init：未知保持未知
                self.assertIsNone(self.story_start(feature))
                self.assertNotIn("story", self.steps(feature), "还没成文就出了 Story 行")
                _, restore = TheExtensionClosesTheStep.inject(self, "usage.json")
                self.assertFalse(self.story_done(T0 + timedelta(seconds=510), feature=feature)["ok"])
                restore()
                self.assertEqual({"story": {}}, self.state()[self.key(feature)]["pending"], "缺口行没进待写")
                self.call("refresh", feature=feature)
                self.assertEqual({}, self.steps(feature)["story"], "缺起点的 Story 编了耗时")
                self.assertEqual("absent", self.story_start(feature), "结算后未知起点还留着")

    def test_an_unknown_later_round_keeps_what_was_counted(self) -> None:
        """已有累计后，又一轮起点不可核（例如 begin 记了 null）：这一轮记缺口，已记的累计不抹。
        登记成功早于起点（时钟异常）不结算、起点保留到下一次。"""
        self.at_time("begin", "story", T0)
        self.story_done(T0 + timedelta(seconds=100))
        st = self.state()
        st.setdefault(self.key(), {}).setdefault("starts", {})["story"] = None
        self.state_file.write_text(json.dumps(st), encoding="utf-8")
        out = self.story_done(T0 + timedelta(seconds=300))
        self.assertIn("起点不可核", out["note"])
        self.assertEqual(({"spent": 100}, "absent"), (self.steps()["story"], self.story_start()))
        self.at_time("begin", "story", T0 + timedelta(seconds=500))
        out = self.story_done(T0 + timedelta(seconds=400))
        self.assertIn("早于", out["note"])
        self.assertEqual(({"spent": 100}, native(T0 + timedelta(seconds=500))), (self.steps()["story"], self.story_start()))

    def test_only_a_successful_registration_completes_the_story(self) -> None:
        """登记成功是完成的唯一事件：从没被看到开始、第一次登记成功只记缺口，不补现在；
        盘上只有成文时间或只有 story.md 文件、没有这一次成功的，不算完成。"""
        self.story_written(T0, feature="W1")
        self.at_time("begin", "spec", T0 + timedelta(seconds=100), feature="W1")
        self.assertNotIn("story", self.steps("W1"), "盘上旧成文时间被当成了完成")
        self.story_done(T0 + timedelta(seconds=200), feature="W1")
        self.assertEqual({}, self.steps("W1")["story"], "没有开始记录的完成编了耗时")
        story_md = self.fr("W2") / "AR" / "story.md"
        story_md.parent.mkdir(parents=True)
        story_md.write_text("# 只有文件\n", encoding="utf-8")
        self.at_time("begin", "spec", T0, feature="W2")
        self.assertNotIn("story", self.steps("W2"), "文件在就当成文了")

    def test_a_framework_identity_is_not_the_story_start(self) -> None:
        """纯 Framework 先开始建了身份，后来才第一次做 Story：Story 只从自己的 begin 算。"""
        self.at_time("begin", "spec", T0)
        self.assertEqual("20261021T080000.000Z", self.key().split("-", 1)[1])
        self.assertNotIn("story", self.steps(), "没做 Story 却出了行")
        self.at_time("begin", "story", T0 + timedelta(seconds=500))
        self.story_done(T0 + timedelta(seconds=800))
        self.assertEqual({"spent": 300}, self.steps()["story"], "Story 从需求身份时刻算了")

    def test_a_failed_story_command_is_not_a_completion(self) -> None:
        """story 命令失败不调成功回调：经真实 story_flow 入口，登记没成就没有完成、起点保留。"""
        self.at_time("begin", "story", T0)
        proc = subprocess.run([sys.executable, str(FLOW), "story", "--feature", "AR1", "--project-root", str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90, env=self.env)
        self.assertNotEqual(0, proc.returncode, proc.stdout)
        self.assertEqual(native(T0), self.story_start(), "失败的登记清了起点")
        self.assertNotIn("story", self.steps(), "失败的登记记成了完成")

    def test_update_rounds_come_from_the_records_even_without_local_state(self) -> None:
        self.call("begin", "story")
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

    def test_an_opened_round_without_begin_has_no_time(self) -> None:
        """开轮时刻是业务事实，不是工作起点：没有 begin 移入的 started_at，这一轮只计轮数，不拿 opened_at 补。"""
        self.call("begin", "story")
        self.update_record("u1", T0, T0 + timedelta(seconds=300), begun=False)
        self.call("refresh")
        self.assertEqual({"rounds": 1}, self.steps()["story update"])
        self.update_record("u2", T0 + timedelta(seconds=1000), T0 + timedelta(seconds=1100))
        self.call("refresh")
        self.assertEqual({"spent": 100, "rounds": 2}, self.steps()["story update"])

    def test_a_round_closed_within_its_start_second_is_still_timed(self) -> None:
        """起点带毫秒、收口时刻只到秒：同一秒里收口的一轮照常计时（0 秒），不当成起止颠倒丢掉。"""
        self.call("begin", "story")
        folder = self.fr() / "AR" / "story-src" / "updates" / "u1"
        folder.mkdir(parents=True)
        (folder / "record.json").write_text(json.dumps({"id": "u1", "status": "closed", "opened_at": at(T0),
                                                        "started_at": native(T0 + timedelta(milliseconds=700)),
                                                        "closed_at": at(T0)}), encoding="utf-8")
        self.call("refresh")
        self.assertEqual({"spent": 0, "rounds": 1}, self.steps()["story update"])

    def test_restores_baselines_and_missing_starts(self) -> None:
        """没收口就撤回不计；收口后再撤回仍是收口过一轮；缺起点的轮只计轮数；baseline 不算一轮。"""
        self.call("begin", "story")
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
        self.call("begin", "story")
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
    """阶段的 Extension 收尾：最后一步不靠下一阶段、story 命令或 stats 就进 usage；失败重跑同一命令即收敛。"""

    PHASES = ("spec", "plan", "coding", "review", "ut", "testing")

    def test_every_phase_can_be_the_last_one_through_the_cli(self) -> None:
        for phase in self.PHASES:
            with self.subTest(phase=phase):
                feature = f"F-{phase}"
                begun = subprocess.run([sys.executable, str(USAGE), "--project-root", str(self.root), "--feature", feature,
                                        "--begin", "--step", phase], capture_output=True, text=True, encoding="utf-8",
                                       errors="replace", timeout=60, env=self.env)
                self.assertEqual(0, begun.returncode, begun.stderr)
                self.close_phase(phase, datetime.now(timezone.utc), feature=feature)
                out = self.finalize(phase, feature=feature)
                self.assertEqual(0, out.returncode, out.stderr)
                said = json.loads(out.stdout)
                self.assertEqual((phase, False), (said["phase"], said["timing_gap"]))
                self.assertIsInstance(said["recorded"]["spent"], int)
                self.assertEqual(said["recorded"], self.steps(feature)[phase], "最后一步没落进 usage")
        self.assertFalse(self.state_file.exists(), "收尾之后留着运行态")

    def test_the_finalize_is_idempotent_and_never_reopens(self) -> None:
        self.at_time("begin", "spec", T0)
        self.close_phase("spec", T0 + timedelta(seconds=500))
        for k in range(3):
            self.assertTrue(self.at_time("finalize", "spec", T0 + timedelta(seconds=600 + k))["ok"])
            self.call("refresh")
        self.assertEqual({"spent": 600}, self.steps()["spec"], "重复收尾或刷新多记了")
        summary = json.loads((self.reports("spec") / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual("closed", summary["closure_status"], "收尾改了原生闭环")

    def test_an_unclosed_phase_is_refused_and_records_nothing(self) -> None:
        self.call("begin", "story")
        self.call("begin", "ut")
        out = self.finalize("ut")
        self.assertNotEqual(0, out.returncode)
        self.assertIn("还没有原生有效闭环", out.stdout)
        self.assertIn("先完成阶段", out.stderr)
        self.assertNotIn("已闭环", out.stderr, "没闭环却说业务已闭环")
        self.assertNotIn("ut", self.steps(), "没闭环却记了一行")

    def test_a_closed_phase_that_cannot_be_written_says_why(self) -> None:
        """闭环成立而记录写不进：报出写不进的原因，不说没闭环；修好后重跑同一条就记上。"""
        self.at_time("begin", "ut", T0)
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
        self.assertIsInstance(self.steps()["ut"]["spent"], int)

    def test_a_closure_without_a_begin_is_recorded_without_inventing_time(self) -> None:
        self.call("begin", "story")
        self.close_phase("review", T0)
        said = json.loads(self.finalize("review").stdout)
        self.assertEqual(({}, True), (said["recorded"], said["timing_gap"]), "缺起点的完成行编了耗时或没出现")

    def test_milliseconds_are_kept_until_the_difference(self) -> None:
        self.at_time("begin", "spec", T0 + timedelta(milliseconds=900))
        self.assertRegex(self.state()[self.key()]["starts"]["spec"], r"\.900Z$", "起点丢了毫秒")
        self.close_phase("spec", T0 + timedelta(seconds=5))
        self.at_time("finalize", "spec", T0 + timedelta(seconds=10, milliseconds=600))
        self.assertEqual({"spent": 10}, self.steps()["spec"], "起止各截到秒再相减，差出 1 秒")

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
        """usage 写失败、运行态写失败：业务闭环不回退，重跑收尾后只记一次，不需要 stats 补。
        usage 没写成时待写行已在运行态，重跑照它赋值（终点是那次算好的）；运行态本身没写成时这次收尾整个没落盘，
        起点还在，终点是重跑成功的那一刻。两种都不重复累加。"""
        for fail_on, want in (("usage.json", 40), (".usage-state.json", 90)):
            with self.subTest(fail_on=fail_on):
                feature = f"R{len(fail_on)}"
                self.at_time("begin", "spec", T0, feature=feature)
                self.close_phase("spec", T0 + timedelta(seconds=30), feature=feature)
                _, restore = self.inject(fail_on)
                out = self.at_time("finalize", "spec", T0 + timedelta(seconds=40), feature=feature)
                self.assertFalse(out["ok"], "写失败却报收尾成功")
                restore()
                for k in range(2):
                    self.assertTrue(self.at_time("finalize", "spec", T0 + timedelta(seconds=90 + k), feature=feature)["ok"])
                self.assertEqual({"spent": want}, self.steps(feature)["spec"], "失败后重试重复累加或丢了")

    def test_a_cleanup_failure_is_reported_and_converges(self) -> None:
        self.at_time("begin", "spec", T0)
        self.close_phase("spec", T0 + timedelta(seconds=5))
        self.at_time("finalize", "spec", T0 + timedelta(seconds=5))
        self.at_time("begin", "spec", T0 + timedelta(seconds=100))
        self.close_phase("spec", T0 + timedelta(seconds=105))
        sys.path.insert(0, str(CORE))
        import usage  # noqa: PLC0415
        real = Path.unlink

        def busy(path, *a, **k):
            if path.name == ".usage-state.json":
                raise OSError("被占用（注入）")
            return real(path, *a, **k)

        with unittest.mock.patch.object(Path, "unlink", busy):
            out = self.at_time("finalize", "spec", T0 + timedelta(seconds=107))
        self.assertFalse(out["ok"])
        self.assertTrue(any("清不掉" in e for e in out["errors"]), out)
        self.at_time("finalize", "spec", T0 + timedelta(seconds=200))
        self.assertEqual({"spent": 12}, self.steps()["spec"])
        self.assertFalse(self.state_file.exists())


class TheLocalStateIsMinimal(UsageCase):
    def test_init_story_and_update_leave_no_empty_state(self) -> None:
        self.at_time("begin", "story", T0)
        self.story_done(T0 + timedelta(seconds=30))
        self.update_record("u1", T0, T0 + timedelta(seconds=60))
        self.call("refresh")
        self.assertEqual({"story": {"spent": 30}, "story update": {"spent": 60, "rounds": 1}}, self.steps())
        self.assertFalse(self.state_file.exists(), "init / Story / update 留下了运行态")

    def test_pending_only_carries_what_this_settlement_changed(self) -> None:
        self.call("begin", "story")
        self.close_phase("plan", T0)
        self.finalize("plan")
        self.at_time("begin", "spec", T0)
        self.close_phase("spec", T0 + timedelta(seconds=5))
        TheExtensionClosesTheStep.inject(self, "usage.json")
        self.assertFalse(self.at_time("finalize", "spec", T0 + timedelta(seconds=9))["ok"])
        self.assertEqual({"spec": {"spent": 9}}, self.state()[self.key()]["pending"], "待写里带了别的完成历史")

    def test_a_version_or_input_change_alone_does_not_stage_steps(self) -> None:
        self.call("begin", "story")
        self.close_phase("plan", T0)
        self.finalize("plan")
        (self.fr() / ".usage-input.json").write_text('{"agent": "a", "model": "m"}', encoding="utf-8")
        self.call("refresh")
        self.assertEqual(("a", "m"), (self.node()["agent"], self.node()["model"]))
        self.assertNotIn("pending", self.state().get(self.key(), {}), "只改自报身份也记了待写行")


class VersionsAndIdentity(UsageCase):
    def test_versions_follow_the_last_activity(self) -> None:
        self.call("begin", "story")
        node = self.node()
        self.assertIsNone(node["fw"], "没有 summary 却填了 Framework 版本")
        manifest = (DEV_EXT / "manifest.yaml").read_text(encoding="utf-8")
        self.assertIn(f'version: "{node["ext"]}"' if f'version: "{node["ext"]}"' in manifest else f"version: {node['ext']}",
                      manifest, "ext 不是已装 manifest 的版本")
        self.close_phase("spec", T0, gate="3.0.0:aaaa")
        self.call("refresh")
        self.assertEqual("3.0.0", self.node()["fw"])

    def test_the_self_report_is_taken_once_and_story_needs_it(self) -> None:
        self.call("begin", "story")
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

    def test_each_field_is_fixed_once_known_and_unknown_stays_null(self) -> None:
        """宿主不知道就是 null：按字段固定已知值，后来补上的另一项照收，不为一半未知再催。"""
        self.call("begin", "story")
        (self.fr() / "AR" / "story-src").mkdir(parents=True, exist_ok=True)
        self.story_written(T0)
        path = self.fr() / ".usage-input.json"
        path.write_text(json.dumps({"agent": None, "model": "m1"}), encoding="utf-8")
        out = self.call("refresh")
        self.assertEqual((None, "m1"), (self.node()["agent"], self.node()["model"]))
        self.assertFalse(out["pending_identity"], "一半已知又催了一轮")
        path.write_text(json.dumps({"agent": "dsh", "model": "m2"}), encoding="utf-8")
        self.call("refresh")
        self.assertEqual(("dsh", "m1"), (self.node()["agent"], self.node()["model"]), "已固定的字段被改，或补上的字段没收")

    def test_the_update_close_from_story_flow_is_the_close_action(self) -> None:
        sys.path.insert(0, str(CORE))
        import usage  # noqa: PLC0415
        from unittest import mock  # noqa: PLC0415
        for (mode, action), want in ((("update", "close"), "close"), (("update", "status"), "refresh"),
                                     (("init", None), "init"), (("story", None), "refresh")):
            with self.subTest(mode=mode, action=action), mock.patch.object(usage, "record") as rec, \
                    mock.patch.object(usage, "now", return_value=T0):
                usage.after_command(self.root, "AR1", mode, action)
                rec.assert_called_once_with(self.root, want, feature="AR1",
                                            story_completed_at=T0 if mode == "story" else None)

    def test_a_pure_framework_requirement_is_not_asked(self) -> None:
        out = self.call("begin", "coding")
        self.assertFalse(out["pending_identity"], "纯框架使用没有填写时机，不该催")


class WriteProtection(UsageCase):
    def test_two_requirements_written_at_once_both_survive(self) -> None:
        threads = [threading.Thread(target=self.call, args=("begin", "story", f"AR{i}")) for i in range(1, 5)]
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
        """运行态已清起点、usage 没写成：重跑收尾按运行态里的待写行赋值，不再加一遍、也不换成重跑那一刻。"""
        self.at_time("begin", "spec", T0)
        self.close_phase("spec", T0 + timedelta(seconds=400))
        _, restore = TheExtensionClosesTheStep.inject(self, "usage.json")
        first = self.at_time("finalize", "spec", T0 + timedelta(seconds=500))
        restore()
        self.assertFalse(first["ok"])
        self.assertNotIn("spec", self.steps(), "失败的那次写进了 usage")
        self.call("refresh")
        self.finalize("spec")
        self.finalize("spec")
        self.assertEqual({"spent": 500}, self.steps()["spec"])

    def test_a_lock_that_cannot_open_is_an_ordinary_record_error(self) -> None:
        self.call("begin", "story")
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
        self.call("begin", "story")
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
