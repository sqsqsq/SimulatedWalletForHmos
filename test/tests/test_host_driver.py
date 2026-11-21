"""宿主装置不替模型说话、不吞模型的问题：检查点留着待答的一问，规划只作候选展示，检查点不收回话，
watch 只敲门，评审表态按宿主指定的 D 议题写进人工区、写前核全、原换行不动。
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "test" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_multi_case  # noqa: E402


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rc = _load("story_run_case_host_driver", "run_case.py")

REVIEW = (
    "# 评审记录\n\n## 1. 待确认事项\n\n### 1.1 业务规则\n\n"
    "#### 1.1.1 撤销宽限的时长\n\n**决策点**：撤销后多久失效。\n\n请产品负责人评审。\n\n"
    "评审结论：\n- [ ] 同意\n- [ ] 需修改\n- [ ] 暂缓\n修改意见：\n\n<!-- decision: D2 -->\n\n"
    "#### 1.1.2 转分享是否允许\n\n**决策点**：拿到钥匙的人能否再分享。\n\n请产品负责人评审。\n\n"
    "评审结论：\n- [ ] 同意\n- [ ] 需修改\n- [ ] 暂缓\n修改意见：\n\n<!-- decision: D3 -->\n"
)


class TheCheckpointKeepsThePendingQuestion(unittest.TestCase):
    """AC29：第一检查点带着模型最后那句话给宿主评；续跑只投第二段请求，不替模型答别的。"""

    def test_the_resume_request_carries_only_the_update_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / rc.RESUME_FILE).write_text(json.dumps(
                {"text": "/story update AR90006", "answer": "送审。"}, ensure_ascii=False),
                encoding="utf-8")
            got = rc.pop_resume_request(out)
            self.assertEqual({"text": "/story update AR90006"}, got)
            self.assertFalse((out / rc.RESUME_FILE).exists(), "取走之后请求还在")

    def test_the_update_request_and_a_reply_file_reach_the_driver_verbatim(self) -> None:
        """第二段请求默认取 case.yaml 的 update_request；回话文件按原样读，以 / 开头、多行与引号都不变。"""
        import yaml  # noqa: PLC0415
        multi = run_multi_case
        case = yaml.safe_load((REPO_ROOT / "test" / "cases" / "auto-topup" / "case.yaml").read_text(encoding="utf-8"))
        self.assertEqual("/story update AR90006", case["update_request"])
        text = '/story update AR90006\n第二行 "引号" \'单引号\' E:/a/b'
        with tempfile.TemporaryDirectory() as tmp:
            reply = Path(tmp) / "reply.txt"
            reply.write_bytes((text + "\n").encode("utf-8"))
            self.assertEqual(text, multi.text_from_file(reply))

    def test_waiting_at_the_checkpoint_shows_the_models_question(self) -> None:
        feed, runlog = mock.Mock(), mock.Mock()
        state: dict = {}
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(rc, "refresh_worker_lease"), \
                mock.patch.object(rc, "pop_resume_request",
                                  return_value={"text": "/story update AR90006"}):
            got = rc.wait_for_resume(Path(tmp), feed, runlog, state, turn=7,
                                     pending="要归档送审，还是进入 plan？")
        self.assertEqual("要归档送审，还是进入 plan？", state["awaiting_prompt"])
        self.assertEqual("要归档送审，还是进入 plan？", state["pending_question"])
        emitted = feed.emit.call_args_list[0]
        self.assertEqual("initial_checkpoint", emitted.args[0])
        self.assertEqual("要归档送审，还是进入 plan？", emitted.kwargs["pending_question"])
        self.assertEqual({"text": "/story update AR90006"}, got)


class ThePlanIsShownOnlyWhenItFits(unittest.TestCase):
    """AC30：类型或已知阶段对不上的条目不展示；阶段未知时只作 phase_ready 为假的候选。"""

    def record(self, kind: str, phase: str | None = None) -> dict:
        return {"case": "c", "status": run_multi_case.WAITING_STATUS, "current_phase": phase,
                "interaction_index": 0,
                "interaction_script": [{"id": "enter-plan", "expected_kind": "story_gate",
                                        "expected_phase": "spec", "text": "进入 plan。"}],
                "last_awaiting": {"turn": 3, "kind": kind, "prompt": "模型的那一问"}}

    def request(self, record: dict) -> dict:
        with mock.patch.object(run_multi_case, "append_event"), \
                mock.patch.object(run_multi_case, "append_case_observation"):
            run_multi_case.request_host_reply(record, {"case_states": {}})
        return record["last_adaptive_request"]

    def test_a_checkpoint_does_not_get_a_gate_stance(self) -> None:
        got = self.request(self.record("initial_checkpoint", "spec"))
        self.assertIsNone(got["planned_step_id"])
        self.assertEqual("规划里没有对应这一问：按 answered 只答所问", got["plan_note"])
        self.assertEqual("模型的那一问", got["question"])

    def test_a_gate_in_another_phase_does_not_get_it_either(self) -> None:
        self.assertIsNone(self.request(self.record("story_gate", "plan"))["planned_step_id"])

    def test_story_and_spec_do_not_take_each_others_stances(self) -> None:
        record = self.record("story_gate", "story")
        self.assertIsNone(self.request(record)["planned_step_id"], "story 阶段展示了 spec 的立场")
        record = self.record("story_gate", "spec")
        record["interaction_script"][0]["expected_phase"] = "story"
        self.assertIsNone(self.request(record)["planned_step_id"], "spec 阶段展示了 story 的立场")

    def test_an_unknown_phase_only_gets_a_candidate_not_ready(self) -> None:
        got = self.request(self.record("story_gate", None))
        self.assertEqual([("enter-plan", False)], [(c["id"], c["phase_ready"]) for c in got["candidate_steps"]])

    def test_a_matching_gate_gets_the_stance_as_a_candidate(self) -> None:
        got = self.request(self.record("story_gate", "spec"))
        self.assertEqual("enter-plan", got["planned_step_id"])
        self.assertEqual("候选，需按完整问题核立场", got["plan_note"])


class TheCheckpointRefusesReplies(unittest.TestCase):
    """第二检查点等待期间 reply 被拒，说明该用哪个命令；第一检查点上的回话见 test_update_checkpoints（S4 §2：答完仍在第一段）。"""

    def test_a_reply_at_the_checkpoint_is_refused(self) -> None:
        for kind in ("update_checkpoint",):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp, \
                    mock.patch.object(rc, "_load_case", return_value=({}, Path(tmp), "AR1")), \
                    mock.patch.object(rc, "reconcile_worker_state",
                                      return_value={"status": "awaiting_reply", "awaiting_kind": kind}), \
                    mock.patch.object(rc, "read_state", return_value={}), \
                    mock.patch("builtins.print") as printed:
                self.assertEqual(1, rc.cmd_reply("c", "好的"))
                self.assertFalse((Path(tmp) / rc.REPLY_FILE).exists(), "检查点上收下了回话")
                self.assertIn("不收回话", printed.call_args.args[0])


class WatchOnlyKnocks(unittest.TestCase):
    """AC31：watch 要回话、要收尾、连续失败时退出并写明原因，不产生回话。"""

    def test_exit_reasons(self) -> None:
        reason = run_multi_case.watch_exit_reason
        self.assertIsNone(reason({"cases": [{"case": "a", "status": "running"}]}))
        self.assertIn("要回话", reason({"adaptive_reply_requests": [{"case": "a"}], "cases": []}))
        self.assertIn("要宿主处置", reason({"cases": [{"case": "a", "status": run_multi_case.WAITING_STATUS}]}))
        self.assertIn("finalize", reason({"suite_terminal": True}))

    def test_it_stops_after_repeated_failures_and_never_replies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(run_multi_case, "load_suite",
                                  side_effect=[(Path(tmp), {})] + [RuntimeError("坏了")] * 5), \
                mock.patch.object(run_multi_case, "command_reply") as replied, \
                mock.patch.object(run_multi_case.time, "sleep"), \
                mock.patch("builtins.print") as printed:
            self.assertEqual(2, run_multi_case.command_watch("s", 1, 1000))
        replied.assert_not_called()
        self.assertIn("连续失败", printed.call_args.args[0])

    def test_it_writes_the_last_poll_and_exits_when_a_reply_is_needed(self) -> None:
        payload = {"adaptive_reply_requests": [{"case": "a"}], "cases": []}
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(run_multi_case, "load_suite", return_value=(Path(tmp), {"status": "running"})), \
                mock.patch.object(run_multi_case, "poll_suite"), \
                mock.patch.object(run_multi_case, "settle_scripted_interactions"), \
                mock.patch.object(run_multi_case, "finalize_suite_status", return_value="running"), \
                mock.patch.object(run_multi_case, "save_suite"), \
                mock.patch.object(run_multi_case, "control_payload", return_value=payload), \
                mock.patch.object(run_multi_case, "command_reply") as replied, \
                mock.patch("builtins.print"):
            self.assertEqual(0, run_multi_case.command_watch("s", 1, 1000))
            self.assertEqual(payload, json.loads((Path(tmp) / "host" / "last-poll.json").read_text(encoding="utf-8")))
        replied.assert_not_called()


class ReviewOpinionsLandOnTheChosenIssues(unittest.TestCase):
    """人工区意见：宿主为每条静态意见选真实 D 议题；脚本核完全部输入才一次写入，机器区不动、原换行保持。"""

    STATIC = "- verdict: 需修改\n  opinion: 定为 36 小时。\n- verdict: 暂缓\n  opinion: 转分享这次仍不定。\n"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.feature = self.root / "feature"
        self.out = self.root / "run"
        (self.feature / "AR").mkdir(parents=True)
        (self.out / "checkpoints" / "initial" / "AR").mkdir(parents=True)
        self.review = self.feature / "AR" / "review.md"
        self.put(REVIEW)
        self.zone = self.root / "static.yaml"
        self.zone.write_text(self.STATIC, encoding="utf-8")

    def put(self, text: str, newline: str = "\n") -> None:
        data = text.replace("\n", newline).encode("utf-8")
        self.review.write_bytes(data)
        (self.out / "checkpoints" / "initial" / "AR" / "review.md").write_bytes(data)

    def feedback(self, items: list[dict]) -> Path:
        import yaml  # noqa: PLC0415
        f = self.root / "feedback.yaml"
        f.write_text(yaml.safe_dump(items, allow_unicode=True), encoding="utf-8")
        return f

    GOOD = [{"source_item": 1, "decision_id": "D2", "verdict": "需修改", "opinion": "定为 36 小时。"},
            {"source_item": 2, "decision_id": "D3", "verdict": "暂缓", "opinion": "转分享这次仍不定。"}]

    def deliver(self, items: list[dict]) -> None:
        _, write = rc._review_zone_plan(self.feature, self.out, [self.zone], self.feedback(items))
        write()

    def test_each_opinion_lands_on_its_chosen_issue_with_the_newlines_kept(self) -> None:
        for newline in ("\n", "\r\n"):
            with self.subTest(newline=repr(newline)):
                self.put(REVIEW, newline)
                self.deliver(self.GOOD)
                raw = self.review.read_bytes().decode("utf-8")
                self.assertEqual(REVIEW.count("\n"), raw.count(newline), "换行被改了")
                first, second = raw.replace("\r\n", "\n").split("#### 1.1.2", 1)
                self.assertIn("- [x] 需修改\n- [ ] 暂缓", first)
                self.assertIn("修改意见：定为 36 小时。", first)
                self.assertIn("- [ ] 需修改\n- [x] 暂缓", second)
                self.assertEqual(rc._machine_view(REVIEW.split("\n")), rc._machine_view(raw.replace("\r\n", "\n").split("\n")),
                                 "机器区被改了")
                self.deliver(self.GOOD)
                self.assertEqual(raw, self.review.read_bytes().decode("utf-8"), "同样的输入重投不幂等")

    def test_a_retitled_issue_is_found_by_its_identity(self) -> None:
        self.put(REVIEW.replace("撤销宽限的时长", "收回钥匙的期限"))
        self.deliver(self.GOOD)
        self.assertIn("修改意见：定为 36 小时。", self.review.read_text(encoding="utf-8").split("#### 1.1.2")[0])

    def test_bad_inputs_write_nothing(self) -> None:
        g1, g2 = self.GOOD
        cases = {
            "空": [], "漏一条": [g1], "重复 source_item": [g1, {**g2, "source_item": 1}],
            "改了静态立场": [g1, {**g2, "verdict": "同意"}], "改了意见": [g1, {**g2, "opinion": "可以转分享。"}],
            "未知 D": [g1, {**g2, "decision_id": "D9"}], "重复 D": [g1, {**g2, "decision_id": "D2"}],
            "没有对应议题": [g1, {**g2, "decision_id": ""}],
        }
        before = self.review.read_bytes()
        for label, items in cases.items():
            with self.subTest(case=label), self.assertRaises(SystemExit):
                self.deliver(items)
            self.assertEqual(before, self.review.read_bytes(), f"{label}：写了盘")

    def test_a_broken_zone_or_another_version_is_refused(self) -> None:
        for label, text, initial in (
                ("缺人工区", REVIEW.replace("- [ ] 暂缓\n修改意见：\n\n<!-- decision: D2", "\n<!-- decision: D2"), None),
                ("初段不是这一份", REVIEW, REVIEW.replace("撤销后多久失效", "另一版的决策点"))):
            with self.subTest(case=label):
                self.put(text)
                if initial:
                    (self.out / "checkpoints" / "initial" / "AR" / "review.md").write_text(initial, encoding="utf-8")
                with self.assertRaises(SystemExit):
                    self.deliver(self.GOOD)
                self.assertNotIn("- [x]", self.review.read_text(encoding="utf-8"))

    def test_a_repeated_tick_or_opinion_line_is_refused(self) -> None:
        """F4：同一议题的三态有重复行或意见行有两行：写前拒绝，原件不动，不替人删多余的行。"""
        for label, old, new in (
                ("三态重复", "- [ ] 暂缓\n修改意见：\n\n<!-- decision: D2", "- [ ] 暂缓\n- [x] 需修改\n修改意见：\n\n<!-- decision: D2"),
                ("意见两行", "- [ ] 暂缓\n修改意见：\n\n<!-- decision: D2", "- [ ] 暂缓\n修改意见：\n修改意见：另一处\n\n<!-- decision: D2")):
            with self.subTest(case=label):
                self.put(REVIEW.replace(old, new))
                before = self.review.read_bytes()
                with self.assertRaises(SystemExit) as stopped:
                    self.deliver(self.GOOD)
                self.assertIn("各恰好一行", str(stopped.exception))
                self.assertEqual(before, self.review.read_bytes())

    def test_a_different_human_opinion_is_kept_as_a_conflict(self) -> None:
        self.put(REVIEW.replace("- [ ] 同意\n- [ ] 需修改\n- [ ] 暂缓\n修改意见：\n\n<!-- decision: D2",
                                "- [x] 同意\n- [ ] 需修改\n- [ ] 暂缓\n修改意见：评审人自己写的\n\n<!-- decision: D2"))
        before = self.review.read_bytes()
        with self.assertRaises(SystemExit) as stopped:
            self.deliver(self.GOOD)
        self.assertIn("投递冲突", str(stopped.exception))
        self.assertEqual(before, self.review.read_bytes())


class AllUpdateInputsAreCheckedBeforeWriting(unittest.TestCase):
    """resume-update：Case 的全部更新输入与额外补料先成完整计划再写——同目标不同内容整批拒绝、同字节合并；
    执行中途失败分已投、失败（带目标现状）、未执行，不排话。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "doc" / "features" / "AR90006").mkdir(parents=True)

    def run_delivery(self, supplements: list[str], env: dict) -> list:
        with mock.patch.object(rc, "REPO_ROOT", self.root), mock.patch.dict("os.environ", env, clear=False):
            return rc.deliver_update_inputs("auto-topup", "AR90006", self.root / "run", None, supplements)

    def test_a_bad_input_anywhere_stops_before_any_write(self) -> None:
        system = self.root / "system"
        for label, supplements, env in (("缺需求系统", [], {"STORY_REQUIREMENT_SYSTEM_DIR": ""}),
                                        ("补料不存在", ["没有这份.docx"], {"STORY_REQUIREMENT_SYSTEM_DIR": str(system)})):
            with self.subTest(case=label), self.assertRaises(SystemExit):
                self.run_delivery(supplements, env)
            self.assertFalse((self.root / "doc" / "features" / "AR90006" / "inbox").exists(), f"{label}：写了收件箱")
            self.assertFalse(system.exists(), f"{label}：写了需求系统")

    def supplement_named(self, name: str, data: bytes) -> Path:
        extra = self.root / "extra" / name
        extra.parent.mkdir(parents=True, exist_ok=True)
        extra.write_bytes(data)
        return extra

    def test_different_bytes_for_one_target_stop_the_whole_batch(self) -> None:
        """F3：Case 更新输入与额外补料同名不同内容，都要写 inbox 同一份：整批拒绝，收件箱与需求系统都没写。"""
        system = self.root / "system"
        clash = self.supplement_named("交通卡自动充值-v2.docx", b"another version")
        with mock.patch.object(rc, "supplement_sources", return_value=[clash]), self.assertRaises(SystemExit) as stopped:
            self.run_delivery(["交通卡自动充值-v2.docx"], {"STORY_REQUIREMENT_SYSTEM_DIR": str(system)})
        self.assertIn("内容不同", str(stopped.exception))
        self.assertFalse((self.root / "doc" / "features" / "AR90006" / "inbox").exists())
        self.assertFalse(system.exists())

    def test_the_same_bytes_for_one_target_are_written_once(self) -> None:
        source = REPO_ROOT / "test" / "cases" / "auto-topup" / "update-inputs" / "交通卡自动充值-v2.docx"
        twin = self.supplement_named(source.name, source.read_bytes())
        with mock.patch.object(rc, "supplement_sources", return_value=[twin]):
            done = self.run_delivery([source.name], {"STORY_REQUIREMENT_SYSTEM_DIR": str(self.root / "system")})
        local = [d for d in done if d["destination"] == f"inbox/{source.name}"]
        self.assertEqual(1, len(local), "同一目标写了两次")
        self.assertEqual([{"file": source.name, "kind": "supplement"}], local[0]["merged"], "合并后来源明细丢了")
        self.assertEqual(source.read_bytes(), (self.root / "doc" / "features" / "AR90006" / "inbox" / source.name).read_bytes())

    def test_a_failure_midway_is_told_apart_from_what_never_ran(self) -> None:
        """F5：第二项写到一半失败：第一项已投，第二项失败并报目标现状（这里写了一部分），之后的未执行；不说成零写入。"""
        real = Path.write_bytes
        calls = []

        def flaky(path, data):
            calls.append(path)
            if len(calls) == 2:
                real(path, data[:3])
                raise OSError("磁盘写不进")
            return real(path, data)

        with mock.patch.object(rc.Path, "write_bytes", flaky), self.assertRaises(rc.UpdateDeliveryError) as failed:
            self.run_delivery([], {"STORY_REQUIREMENT_SYSTEM_DIR": str(self.root / "system")})
        err = failed.exception
        self.assertEqual(["local_material"], [d["kind"] for d in err.done])
        self.assertEqual("system", err.failed["kind"])
        self.assertEqual((True, 3), (err.failed["target_now"]["exists"], err.failed["target_now"]["size"]), "部分写入被说成没写")
        self.assertEqual([], err.pending)


class TheModelTempIsInsideTheCaseWorkspace(unittest.TestCase):
    """TV02：模型子进程的 TMP/TEMP 与溢出输出根在**本 Case 工作区内**的独立工具输出目录，
    宿主结果目录与跨 Case 原件仍在外；Windows 上该目录要能继承完全控制项（DSH 沙箱 mkdtemp 改属主）。"""

    def make_workspace(self, root: Path) -> Path:
        workspace = root / "case-workspace"
        (workspace / "doc" / "features").mkdir(parents=True)
        return workspace

    def test_the_private_tmp_is_the_case_workspace_tool_output_not_the_host_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "run"
            out_dir.mkdir(parents=True)
            workspace = self.make_workspace(root)
            env = rc.build_cli_env(out_dir, "dsh", workspace=workspace)
            expected = (workspace / rc.TOOL_OUTPUT_DIR).resolve()
            self.assertEqual(str(expected), env["TMP"])
            self.assertEqual(env["TMP"], env["TEMP"])
            self.assertTrue(expected.is_dir(), "工具输出目录没建")
            self.assertFalse(expected.is_relative_to(out_dir.resolve()), "模型临时目录落回了宿主结果目录")
            self.assertTrue(expected.is_relative_to(workspace.resolve()))
            # 宿主结果目录里没有模型临时目录的残留（旧 cli-tmp 不会再被创建）。
            self.assertFalse((out_dir / "cli-tmp").exists())

    def test_a_direct_debug_run_keeps_temp_in_the_run_dir_not_in_demo(self) -> None:
        """直接跑 run_case（调试用）没有隔离工作区：临时目录退到本轮结果目录，不往 demo 发布基线写运行态。"""
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "run"
            out_dir.mkdir(parents=True)
            env = rc.build_cli_env(out_dir, "dsh")
            self.assertEqual(str((out_dir / "tool-output").resolve()), env["TMP"])
            self.assertEqual(env["TMP"], env["TEMP"])
            self.assertFalse((REPO_ROOT / "demo" / rc.TOOL_OUTPUT_DIR).exists(),
                             "调试跑把运行态写进了 demo")

    def test_the_tool_output_parent_is_the_workspace_root_only(self) -> None:
        """TMP 只能落在工作区根下的固定一层；传相对/嵌套路径不改变归属，越界直接拒绝。"""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            self.assertEqual((workspace / rc.TOOL_OUTPUT_DIR).resolve(), rc.tool_output_root(workspace))
            outside = Path(tmp) / "not-the-workspace"
            outside.mkdir()
            self.assertNotEqual(outside.resolve(), rc.tool_output_root(workspace).parent)

    def test_the_case_git_status_does_not_show_tool_output(self) -> None:
        """工具输出目录是运行态：写进 Case 自己的 .git/info/exclude，模型 `git status` 不被污染。"""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            info = workspace / ".git" / "info"
            info.mkdir(parents=True)
            (info / "exclude").write_text("*.log\n", encoding="utf-8")
            rc.build_cli_env(Path(tmp) / "run", "dsh", workspace=workspace)
            rc.build_cli_env(Path(tmp) / "run", "dsh", workspace=workspace)
            lines = (info / "exclude").read_text(encoding="utf-8").splitlines()
            self.assertEqual(1, lines.count(f"{rc.TOOL_OUTPUT_DIR}/"), "重复追加或没写排除项")
            self.assertIn("*.log", lines, "原有排除项被覆盖")

    def test_build_cli_env_grants_the_private_tmp_an_inheritable_full_control(self) -> None:
        if sys.platform != "win32":
            self.skipTest("Windows ACL 专属")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = self.make_workspace(root)
            env = rc.build_cli_env(root / "run", "dsh", workspace=workspace)
            probe = Path(env["TMP"]) / "grant-probe"
            probe.mkdir()
            listing = subprocess.run(["icacls", str(probe)], capture_output=True, text=True,
                                     encoding="utf-8", errors="replace", check=True).stdout
            granted = [line.strip() for line in listing.splitlines()
                       if "(I)(OI)(CI)(F)" in line and "Administrators" not in line and "SYSTEM" not in line]
            self.assertTrue(granted, f"mkdtemp 子目录没有继承到当前用户的完全控制项：\n{listing}")


class TheUpdateDeliveryRecordsTimeAndOriginalBytes(unittest.TestCase):
    """更新输入投放要能回答「什么时候真的投了、投的是哪一版」：逐件记投放时刻与原件 SHA-256；
    收到另按两种现有来源核（本地件 importer 导入记录、系统件本次取材回执），不拿投放时刻冒充。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "doc" / "features" / "AR90006").mkdir(parents=True)

    def test_each_delivered_input_carries_its_time_hash_and_size(self) -> None:
        system = self.root / "system"
        with mock.patch.object(rc, "REPO_ROOT", self.root), \
                mock.patch.dict("os.environ", {"STORY_REQUIREMENT_SYSTEM_DIR": str(system)}, clear=False):
            done = rc.deliver_update_inputs("auto-topup", "AR90006", self.root / "run", None, [])
        self.assertTrue(done, "没有投任何更新输入")
        for record in done:
            self.assertRegex(str(record.get("delivered_at") or ""), r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
            self.assertRegex(str(record.get("sha256") or ""), r"^[0-9a-f]{64}$")
            self.assertIsInstance(record.get("bytes"), int)
            destination = record["destination"]
            target = (system / destination) if record["kind"] == "system" else (
                self.root / "doc" / "features" / "AR90006" / destination)
            import hashlib
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), record["sha256"],
                             f"{record['file']}：记的摘要不是实际投出的原件")


class TheUpdateDeliveryRecordTellsReceiptFromDelivery(unittest.TestCase):
    """B（S21/R3 返修）+ S26/R2：投放记录逐件保投放时刻与原件字节；**收到**按两种现有来源分别核——
    本地件（投进 inbox）看 importer 导入记录的时间与原件字节，系统件（投进需求系统、由模型 fetch 取回）
    看本次取材回执的状态/时间/原件字节与批次回执。逐件复用三份记录的原生身份（投放目标所在需求单、总回执
    `reqNo`、同名条目 `ticket`、已有字节数），同次同件相互矛盾时保留两边原值并记 unknown——不优先 fetched、
    不取第一个同名条目，也不为本来没有落盘文件的合法否定回执虚设文件义务。系统评审件的三处落点（总回执
    saved、批次条目 saved、存在的 review_out）归一后对不上同样记 unknown 并留两边原值；相对/绝对等价写法
    与普通非评审件各守原合同。身份不矛盾后再给精度与结论：
    投放本身不得写成实际收到；批次回执缺失或对不上、时刻不可比都记 unknown；同字节记录早于投放只有先后
    关系并注明粒度；只有可归入本次投放且未被同次批次推翻的否定回执才记 not_received；没有事件记 unknown；
    旧格式的统一 received_at_source 不是逐件依据。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.feature = self.root / "doc" / "features" / "AR90006"
        self.feature.mkdir(parents=True)
        self.run = self.root / "run"

    def reset(self) -> None:
        """同一用例里的下一组对照：清掉上一组写下的需求目录与投放记录。"""
        shutil.rmtree(self.root / "doc", ignore_errors=True)
        shutil.rmtree(self.root / "system", ignore_errors=True)
        shutil.rmtree(self.run, ignore_errors=True)
        self.feature.mkdir(parents=True)

    def deliver(self) -> dict:
        with mock.patch.object(rc, "REPO_ROOT", self.root), \
                mock.patch.dict("os.environ", {"STORY_REQUIREMENT_SYSTEM_DIR": str(self.root / "system")}, clear=False):
            rc.deliver_update_inputs("auto-topup", "AR90006", self.run, None, [])
        return self.record()

    def record(self) -> dict:
        return json.loads((self.run / rc.UPDATE_DELIVERY_RECORD).read_text(encoding="utf-8"))

    def rewrite(self, payload: dict) -> None:
        (self.run / rc.UPDATE_DELIVERY_RECORD).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def delivered(self, payload: dict) -> dict:
        return {item["kind"]: item for item in payload["delivered"]}

    def assert_summary_matches_items(self, payload: dict) -> None:
        """最终记录能反查：汇总里每个状态的数量等于逐件明细里该状态的件数。"""
        for status in ("received", "unknown", "not_received", "ordered_only"):
            self.assertEqual(sum(1 for item in payload["delivered"] if item["receipt"]["status"] == status),
                             payload["receipt_check"]["counts"][status], f"汇总里的 {status} 与逐件明细对不上")

    def assert_delivery_kept(self, before: dict, after: dict) -> None:
        """原始投放记录逐件保留：逐件归账只加 `receipt`，不改写投出的字节与时刻。"""
        for old, new in zip(before["delivered"], after["delivered"], strict=True):
            for key in ("file", "kind", "destination", "sha256", "bytes", "delivered_at"):
                self.assertEqual(old.get(key), new.get(key), f"{key} 被逐件归账改写了")

    def write_import(self, delivered: dict, *, acquired_at: str, sha: str | None = None) -> None:
        """本地件的 importer 导入记录：`AR/story-src/materials.json` 的来源版本（inbox_path 与原件字节）。"""
        src = self.feature / "AR" / "story-src"
        src.mkdir(parents=True, exist_ok=True)
        name = Path(delivered["destination"]).name
        (src / "materials.json").write_text(json.dumps({"schema": 5, "sources": [{
            "source_id": "local:AR:交通卡自动充值", "kind": "local", "class": "AR",
            "label": "交通卡自动充值", "versions": [{
                "version": 1, "dir": "交通卡自动充值-v1", "acquired_at": acquired_at,
                "inbox_path": name,
                "original": {"path": f".backups/local/AR/{name}", "sha256": sha or delivered["sha256"]},
                "readable": None, "images": []}]}]}, ensure_ascii=False), encoding="utf-8")

    def write_fetch(self, delivered: dict, *, fetched_at: str, status: str = "fetched",
                    sha: str | None = None, batch: bool = True) -> dict:
        """系统件的本次取材回执：`AR/story-src/fetched.json` 与它的批次 `.receipt.json`。"""
        src = self.feature / "AR" / "story-src"
        src.mkdir(parents=True, exist_ok=True)
        name = Path(delivered["destination"]).name
        saved = f"inbox/review/fetch-20261119-180000/{name}"
        item = {"name": name, "label": "评审人留下的回稿", "ticket": "AR90006", "status": status,
                "saved": saved, "sha256": sha or delivered["sha256"], "bytes": delivered["bytes"]}
        receipt = {"mode": "fetch", "reqNo": "AR90006", "fetchedAt": fetched_at, "items": [item],
                   "review_out": str(Path(saved).parent.as_posix())}
        (src / "fetched.json").write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
        batch_file = self.feature / saved
        batch_file.parent.mkdir(parents=True, exist_ok=True)
        batch_file.write_bytes((self.root / "system" / "AR90006" / name).read_bytes())
        if batch:
            (batch_file.parent / ".receipt.json").write_text(
                json.dumps({**receipt, "items": [item]}, ensure_ascii=False), encoding="utf-8")
        return item

    def test_delivery_alone_is_not_written_as_receipt(self) -> None:
        """投放记录只证明写了什么字节：没有收到事件时逐件记 unknown 并写明去哪类记录核，
        不再整文件写一个 `received_at_source` 把两种来源混成一种。"""
        payload = self.deliver()
        self.assertEqual(2, payload["schema_version"])
        self.assertNotIn("received_at_source", payload)
        self.assertEqual("not_checked", payload["receipt_check"]["status"])
        for item in payload["delivered"]:
            self.assertRegex(item["delivered_at"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
            self.assertEqual("unknown", item["receipt"]["status"], "投放本身被写成了实际收到")
            self.assertTrue(item["receipt"]["source"], "没写明这一件的收到去哪类记录核")

    def test_only_fetched_without_import_links_each_source_separately(self) -> None:
        """对照①：系统件取回了、本地件没导入——系统件按本次取材回执记 received（时间/字节/批次可核），
        本地件没有导入记录记 unknown；两者不共用一个取材时刻。"""
        payload = self.deliver()
        items = self.delivered(payload)
        fetched_at = "2099-01-01T00:00:00+08:00"
        self.write_fetch(items["system"], fetched_at=fetched_at)
        summary = rc.reconcile_update_receipts(self.run, self.feature)
        payload = self.record()
        items = self.delivered(payload)
        system = items["system"]["receipt"]
        self.assertEqual(("received", fetched_at, items["system"]["sha256"]),
                         (system["status"], system["at"], system["sha256"]))
        self.assertEqual(("verified", "inbox/review/fetch-20261119-180000/.receipt.json"),
                         (system["batch"], system["batch_receipt"]), "批次回执没被核")
        local = items["local_material"]["receipt"]
        self.assertEqual("unknown", local["status"])
        self.assertIn("没有导入记录", local["why"])
        self.assertIsNone(local["at"], "没有导入事件却记了一个收到时刻")
        self.assertEqual((1, 1), (summary["received"], summary["unknown"]))
        self.assertEqual("checked", payload["receipt_check"]["status"])

    def test_imported_local_material_without_the_system_fetch_links_the_import_record(self) -> None:
        """对照②：本地件导入了、系统件没取回——本地件按导入记录记 received（导入时刻/原件字节/版本），
        系统件按取材回执的 absent 记 not_received；没有拿投放时刻当导入时刻。"""
        payload = self.deliver()
        items = self.delivered(payload)
        self.write_import(items["local_material"], acquired_at="2099-01-01T00:00:00+08:00")
        self.write_fetch(items["system"], fetched_at="2099-01-01T00:00:00+08:00", status="absent")
        summary = rc.reconcile_update_receipts(self.run, self.feature)
        payload = self.record()
        items = self.delivered(payload)
        local = items["local_material"]["receipt"]
        self.assertEqual(("received", "2099-01-01T00:00:00+08:00", items["local_material"]["sha256"],
                          "交通卡自动充值-v1"),
                         (local["status"], local["at"], local["sha256"], local["version"]))
        self.assertNotEqual(items["local_material"]["delivered_at"], local["at"], "导入时刻被换成了投放时刻")
        system = items["system"]["receipt"]
        self.assertEqual(("not_received", "本次取材回执记 review-feedback.md 为 absent"),
                         (system["status"], system["why"]))
        self.assertEqual((1, 1), (summary["received"], summary["not_received"]))

    def test_an_earlier_receipt_only_gives_the_order_not_this_delivery(self) -> None:
        """同字节的导入记录早于本次投放：只能证明先后与字节相同，记 ordered_only 并注明粒度，
        不把它说成本次投放已被接收。"""
        payload = self.deliver()
        items = self.delivered(payload)
        self.write_import(items["local_material"], acquired_at="2020-01-01T00:00:00+08:00")
        summary = rc.reconcile_update_receipts(self.run, self.feature)
        local = self.delivered(self.record())["local_material"]["receipt"]
        self.assertEqual(("ordered_only", "sequence_only"), (local["status"], local["granularity"]))
        self.assertIn("早于本次投放", local["why"])
        self.assertEqual(1, summary["ordered_only"])

    def test_a_missing_or_conflicting_batch_receipt_is_unknown_not_received(self) -> None:
        """同一投放、总回执 SHA 与时间不变，只移走批次回执或把其中 SHA 改成另一版：
        证据不闭合，系统件记 unknown 并写明批次，不再判 received；原始投放记录不动，汇总可反查。"""
        for name, batch, conflict in (("移走批次回执", False, False), ("批次回执 SHA 是另一版", True, True)):
            with self.subTest(name):
                self.reset()
                before = self.deliver()
                items = self.delivered(before)
                self.write_fetch(items["system"], fetched_at="2099-01-01T00:00:00+08:00", batch=batch)
                if conflict:
                    path = self.feature / "inbox" / "review" / "fetch-20261119-180000" / ".receipt.json"
                    doc = json.loads(path.read_text(encoding="utf-8"))
                    doc["items"][0]["sha256"] = "0" * 64
                    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
                summary = rc.reconcile_update_receipts(self.run, self.feature)
                after = self.record()
                system = self.delivered(after)["system"]["receipt"]
                self.assertEqual("unknown", system["status"], f"{name}：批次证据不闭合却被判成收到")
                self.assertIn("批次回执", system["why"])
                self.assertEqual("missing" if not conflict else "mismatch", system["batch"])
                self.assertEqual(0, summary["received"])
                self.assert_summary_matches_items(after)
                self.assert_delivery_kept(before, after)

    def test_batch_identity_or_bytes_conflicts_are_unknown_not_received(self) -> None:
        """同一投放、总回执时间/SHA/字节不变，只改批次回执的需求单号、条目主人或字节数：
        两边的原值都保留并记 unknown，不再按「批次可核」判 received；原始投放字段逐件不变。"""
        for name, change in (
            ("批次 reqNo 指向另一需求", lambda doc, item: doc.__setitem__("reqNo", "AR-other")),
            ("批次条目 ticket 指向另一需求", lambda doc, item: doc["items"][0].__setitem__("ticket", "AR-other")),
            ("批次字节数与总回执冲突", lambda doc, item: doc["items"][0].__setitem__("bytes", item["bytes"] + 9)),
        ):
            with self.subTest(name):
                self.reset()
                before = self.deliver()
                items = self.delivered(before)
                self.write_fetch(items["system"], fetched_at="2099-01-01T00:00:00+08:00")
                path = self.feature / "inbox" / "review" / "fetch-20261119-180000" / ".receipt.json"
                doc = json.loads(path.read_text(encoding="utf-8"))
                change(doc, items["system"])
                path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
                summary = rc.reconcile_update_receipts(self.run, self.feature)
                after = self.record()
                system = self.delivered(after)["system"]["receipt"]
                self.assertEqual("unknown", system["status"], f"{name}：冲突身份或字节仍被判 received")
                self.assertEqual("mismatch", system["batch"])
                self.assertTrue(system.get("conflicts"), "冲突两边的原值没有留下")
                self.assertIn("field", system["conflicts"][0])
                self.assertEqual(0, summary["received"])
                self.assert_summary_matches_items(after)
                self.assert_delivery_kept(before, after)

    def test_a_batch_entry_saved_pointing_to_another_batch_is_unknown_not_received(self) -> None:
        """同一需求、同名件、时间/SHA/字节数不动，只把批次明细的 saved 改成另一批目录，总回执 saved
        与 review_out 仍指原批：三处落点归一后前两者不是同一原件，系统件记 unknown，`conflicts` 留下
        总回执与批次条目两边的原值，不再按「批次可核」判 received。"""
        before = self.deliver()
        items = self.delivered(before)
        self.write_import(items["local_material"], acquired_at="2099-01-01T00:00:01+08:00")
        self.write_fetch(items["system"], fetched_at="2099-01-01T00:00:00+08:00")
        path = self.feature / "inbox" / "review" / "fetch-20261119-180000" / ".receipt.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["items"][0]["saved"] = "inbox/review/different-batch/review-feedback.md"
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        summary = rc.reconcile_update_receipts(self.run, self.feature)
        after = self.record()
        system = self.delivered(after)["system"]["receipt"]
        self.assertEqual(("unknown", "mismatch"), (system["status"], system["batch"]),
                         "批次条目 saved 指别处仍被判 received")
        conflict = next(c for c in system["conflicts"] if c["field"] == "saved")
        self.assertEqual(("inbox/review/fetch-20261119-180000/review-feedback.md",
                          "inbox/review/different-batch/review-feedback.md"),
                         (conflict["total"]["value"], conflict["batch"]["value"]),
                         "冲突两边原值没有留下")
        self.assertIn("fetched.json", conflict["total"]["source"])
        self.assertIn(".receipt.json", conflict["batch"]["source"])
        self.assertEqual((1, 1), (summary["received"], summary["unknown"]))
        self.assert_summary_matches_items(after)
        self.assert_delivery_kept(before, after)

    def test_a_review_out_pointing_to_another_directory_is_unknown_not_received(self) -> None:
        """只把总回执的 review_out 改成另一个目录，saved 仍在原批：review_out 不是该原件所属的
        评审批次，系统件记 unknown，`conflicts` 留下总回执与批次回执两边的原值。"""
        before = self.deliver()
        items = self.delivered(before)
        self.write_import(items["local_material"], acquired_at="2099-01-01T00:00:01+08:00")
        self.write_fetch(items["system"], fetched_at="2099-01-01T00:00:00+08:00")
        path = self.feature / "AR" / "story-src" / "fetched.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["review_out"] = "inbox/review/different-batch"
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        summary = rc.reconcile_update_receipts(self.run, self.feature)
        after = self.record()
        system = self.delivered(after)["system"]["receipt"]
        self.assertEqual(("unknown", "mismatch"), (system["status"], system["batch"]),
                         "review_out 指别的目录仍被判 received")
        conflict = next(c for c in system["conflicts"] if c["field"] == "review_out")
        self.assertEqual(("inbox/review/different-batch", "inbox/review/fetch-20261119-180000"),
                         (conflict["total"]["value"], conflict["batch"]["value"]),
                         "冲突两边原值没有留下")
        self.assertEqual(1, summary["unknown"])
        self.assert_summary_matches_items(after)
        self.assert_delivery_kept(before, after)

    def test_equivalent_relative_and_absolute_review_locations_stay_received(self) -> None:
        """同一原件的相对/绝对等价写法不是位置冲突：批次条目 saved、总回执 saved 或 review_out 用
        绝对路径，归一后仍指同一原件与同一评审批次，系统件保持 received/exact。"""
        for name, mutate in (
            ("批次条目 saved 用绝对路径", "batch_saved"),
            ("总回执 saved 用绝对路径", "total_saved"),
            ("总回执 review_out 用绝对路径", "total_review_out"),
        ):
            with self.subTest(name):
                self.reset()
                before = self.deliver()
                items = self.delivered(before)
                self.write_import(items["local_material"], acquired_at="2099-01-01T00:00:01+08:00")
                self.write_fetch(items["system"], fetched_at="2099-01-01T00:00:00+08:00")
                batch_dir = self.feature / "inbox" / "review" / "fetch-20261119-180000"
                absolute = (batch_dir / "review-feedback.md").resolve().as_posix()
                if mutate == "batch_saved":
                    path = batch_dir / ".receipt.json"
                    doc = json.loads(path.read_text(encoding="utf-8"))
                    doc["items"][0]["saved"] = absolute
                else:
                    path = self.feature / "AR" / "story-src" / "fetched.json"
                    doc = json.loads(path.read_text(encoding="utf-8"))
                    if mutate == "total_saved":
                        doc["items"][0]["saved"] = absolute
                    else:
                        doc["review_out"] = batch_dir.resolve().as_posix()
                path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
                summary = rc.reconcile_update_receipts(self.run, self.feature)
                after = self.record()
                system = self.delivered(after)["system"]["receipt"]
                self.assertEqual(("received", "verified"), (system["status"], system["batch"]),
                                 f"{name}：等价写法被当成了位置冲突")
                self.assertEqual(2, summary["received"])
                self.assert_summary_matches_items(after)
                self.assert_delivery_kept(before, after)

    def test_total_saved_moved_out_of_review_batch_conflicts_with_batch_and_review_out(self) -> None:
        """反向位置错位（R2）：同一评审回稿的摘要、票号与时间不变，只把总回执 saved 改到普通目录
        `inbox/fetch-alt/review-feedback.md`（其批次明细仍写原评审批次与 review_out），或两边 saved
        同改普通目录而无 role 且 review_out 仍指评审批次：均归 unknown/mismatch，两边原值保留。"""
        for name, mirror_batch_saved in (
            ("总回执 saved 移出评审批次，批次条目仍指评审批次", False),
            ("无 role 的评审件两边 saved 同移普通目录而 review_out 指评审批次", True),
        ):
            with self.subTest(name):
                self.reset()
                before = self.deliver()
                items = self.delivered(before)
                self.write_import(items["local_material"], acquired_at="2099-01-01T00:00:01+08:00")
                self.write_fetch(items["system"], fetched_at="2099-01-01T00:00:00+08:00")
                alt_dir = self.feature / "inbox" / "fetch-alt"
                alt_dir.mkdir(parents=True, exist_ok=True)
                alt_saved = "inbox/fetch-alt/review-feedback.md"
                orig_batch = self.feature / "inbox" / "review" / "fetch-20261119-180000" / ".receipt.json"
                batch_doc = json.loads(orig_batch.read_text(encoding="utf-8"))
                if mirror_batch_saved:
                    batch_doc["items"][0]["saved"] = alt_saved
                (alt_dir / ".receipt.json").write_text(json.dumps(batch_doc, ensure_ascii=False), encoding="utf-8")
                total_path = self.feature / "AR" / "story-src" / "fetched.json"
                total_doc = json.loads(total_path.read_text(encoding="utf-8"))
                total_doc["items"][0]["saved"] = alt_saved
                total_path.write_text(json.dumps(total_doc, ensure_ascii=False), encoding="utf-8")
                summary = rc.reconcile_update_receipts(self.run, self.feature)
                after = self.record()
                system = self.delivered(after)["system"]["receipt"]
                self.assertEqual(("unknown", "mismatch"), (system["status"], system["batch"]),
                                 f"{name}：反向位置错位仍被判 received")
                if not mirror_batch_saved:
                    saved_conflict = next(c for c in system["conflicts"] if c["field"] == "saved")
                    self.assertEqual((alt_saved, "inbox/review/fetch-20261119-180000/review-feedback.md"),
                                     (saved_conflict["total"]["value"], saved_conflict["batch"]["value"]))
                review_conflict = next(c for c in system["conflicts"] if c["field"] == "review_out")
                self.assertEqual("inbox/review/fetch-20261119-180000", review_conflict["total"]["value"])
                self.assertEqual((1, 1), (summary["received"], summary["unknown"]))
                self.assert_summary_matches_items(after)
                self.assert_delivery_kept(before, after)

    def test_an_ordinary_upstream_item_is_not_held_to_the_review_batch(self) -> None:
        """真实带 role 的普通上游材料按原合同核取材批次：同一次取材另有 review_out 指评审子树时，
        带 role 的上游正文（落在 inbox/fetch-<批次>/）仍按自己的批次回执记 received；若该普通件的
        总/批 saved 互相指向不同批次，照旧记 unknown 并保留两边原值。"""
        # 用真实上游系统正文（SR-design.md，带 role="SR"）走同一投放与回执核对入口
        self.deliver()
        sys_file = self.root / "system" / "AR90006" / "SR-design.md"
        sys_file.parent.mkdir(parents=True, exist_ok=True)
        sys_file.write_text("# SR90006 系统设计修订\n", encoding="utf-8")
        before = self.record()
        for item in before["delivered"]:
            if item["kind"] == "system":
                data = sys_file.read_bytes()
                item["file"] = "SR-design.md"
                item["destination"] = "AR90006/SR-design.md"
                item["bytes"] = len(data)
                item["sha256"] = hashlib.sha256(data).hexdigest()
        self.rewrite(before)
        items = self.delivered(before)
        self.write_import(items["local_material"], acquired_at="2099-01-01T00:00:01+08:00")
        src = self.feature / "AR" / "story-src"
        src.mkdir(parents=True, exist_ok=True)
        saved = "inbox/fetch-20261119-180000/SR-design.md"
        row = {"name": "SR-design.md", "role": "SR", "label": "系统设计正文", "ticket": "AR90006", "status": "fetched",
               "saved": saved, "sha256": items["system"]["sha256"], "bytes": items["system"]["bytes"]}
        receipt = {"mode": "fetch", "reqNo": "AR90006", "fetchedAt": "2099-01-01T00:00:00+08:00",
                   "items": [row], "review_out": "inbox/review/fetch-20261119-180000"}
        (src / "fetched.json").write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
        batch_file = self.feature / saved
        batch_file.parent.mkdir(parents=True, exist_ok=True)
        batch_file.write_bytes(sys_file.read_bytes())
        batch_receipt = batch_file.parent / ".receipt.json"
        batch_receipt.write_text(json.dumps({**receipt, "items": [row]}, ensure_ascii=False), encoding="utf-8")
        summary = rc.reconcile_update_receipts(self.run, self.feature)
        after = self.record()
        system = self.delivered(after)["system"]["receipt"]
        self.assertEqual(("received", "verified"), (system["status"], system["batch"]),
                         "真实带 role 的普通上游材料被误判成评审件位置冲突")
        self.assertEqual(2, summary["received"])
        self.assert_summary_matches_items(after)
        self.assert_delivery_kept(before, after)

        # 同一带 role 普通材料，批次条目 saved 改指向另一普通批次 → 仍按 saved 归一冲突判 unknown
        bad_doc = json.loads(batch_receipt.read_text(encoding="utf-8"))
        bad_doc["items"][0]["saved"] = "inbox/fetch-other/SR-design.md"
        batch_receipt.write_text(json.dumps(bad_doc, ensure_ascii=False), encoding="utf-8")
        summary_bad = rc.reconcile_update_receipts(self.run, self.feature)
        after_bad = self.record()
        system_bad = self.delivered(after_bad)["system"]["receipt"]
        self.assertEqual(("unknown", "mismatch"), (system_bad["status"], system_bad["batch"]))
        conflict = next(c for c in system_bad["conflicts"] if c["field"] == "saved")
        self.assertEqual((saved, "inbox/fetch-other/SR-design.md"),
                         (conflict["total"]["value"], conflict["batch"]["value"]))
        self.assertEqual((1, 1), (summary_bad["received"], summary_bad["unknown"]))
        self.assert_summary_matches_items(after_bad)
        self.assert_delivery_kept(before, after_bad)

    def test_role_contradictions_never_exempt_review_batch_or_pass_as_ordinary(self) -> None:
        """S31（R4）：先比较同一件的原生 role 与两份实际落点，再决定是否适用评审批次。
        ① 底稿双边移出至普通目录、review_out 仍指原评审批次时，只给总回执或只给批次条目加 role="SR"，
           不得豁免评审批次核对：保留两边 role 原值与来源，系统件归 unknown/mismatch；
        ② 两边明确角色相异（SR vs AR）同样记 role 冲突归 unknown/mismatch；
        ③ 普通 role 落在 inbox/review/<批次>/ 评审子树与位置抵触，同样归 unknown/mismatch；
        ④ 旧格式双方缺可选字段（无 role 且无 review_out，落普通目录）不凭空增加义务，仍 received。"""
        # ① 单边 role（分别试总回执加 SR、批次条目加 SR）
        for label, side in (("仅总回执加 role=SR", "total"), ("仅批次条目加 role=SR", "batch")):
            with self.subTest(label):
                self.reset()
                before = self.deliver()
                items = self.delivered(before)
                self.write_import(items["local_material"], acquired_at="2099-01-01T00:00:01+08:00")
                self.write_fetch(items["system"], fetched_at="2099-01-01T00:00:00+08:00")
                alt_dir = self.feature / "inbox" / "fetch-alt"
                alt_dir.mkdir(parents=True, exist_ok=True)
                alt_saved = "inbox/fetch-alt/review-feedback.md"
                orig_batch = self.feature / "inbox" / "review" / "fetch-20261119-180000" / ".receipt.json"
                batch_doc = json.loads(orig_batch.read_text(encoding="utf-8"))
                batch_doc["items"][0]["saved"] = alt_saved
                total_path = self.feature / "AR" / "story-src" / "fetched.json"
                total_doc = json.loads(total_path.read_text(encoding="utf-8"))
                total_doc["items"][0]["saved"] = alt_saved
                if side == "total":
                    total_doc["items"][0]["role"] = "SR"
                else:
                    batch_doc["items"][0]["role"] = "SR"
                (alt_dir / ".receipt.json").write_text(json.dumps(batch_doc, ensure_ascii=False), encoding="utf-8")
                total_path.write_text(json.dumps(total_doc, ensure_ascii=False), encoding="utf-8")
                summary = rc.reconcile_update_receipts(self.run, self.feature)
                after = self.record()
                system = self.delivered(after)["system"]["receipt"]
                self.assertEqual(("unknown", "mismatch"), (system["status"], system["batch"]),
                                 f"{label}：单边 role 豁免了评审批次核对")
                role_c = next(c for c in system["conflicts"] if c["field"] == "role")
                expected_pair = ("SR", None) if side == "total" else (None, "SR")
                self.assertEqual(expected_pair, (role_c["total"]["value"], role_c["batch"]["value"]))
                self.assertTrue(any(c["field"] == "review_out" for c in system["conflicts"]))
                self.assertEqual((1, 1), (summary["received"], summary["unknown"]))
                self.assert_summary_matches_items(after)
                self.assert_delivery_kept(before, after)

        # ② 两边明确角色相异（总 SR vs 批 AR）
        with self.subTest("两边明确角色相异 SR vs AR"):
            self.reset()
            self.deliver()
            sys_file = self.root / "system" / "AR90006" / "SR-design.md"
            sys_file.write_text("# SR90006 修订\n", encoding="utf-8")
            before = self.record()
            data = sys_file.read_bytes()
            for item in before["delivered"]:
                if item["kind"] == "system":
                    item.update(file="SR-design.md", destination="AR90006/SR-design.md",
                                bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            self.rewrite(before)
            items = self.delivered(before)
            self.write_import(items["local_material"], acquired_at="2099-01-01T00:00:01+08:00")
            src = self.feature / "AR" / "story-src"
            src.mkdir(parents=True, exist_ok=True)
            saved = "inbox/fetch-20261119-180000/SR-design.md"
            total_row = {"name": "SR-design.md", "role": "SR", "label": "系统设计正文", "ticket": "AR90006",
                         "status": "fetched", "saved": saved, "sha256": items["system"]["sha256"],
                         "bytes": items["system"]["bytes"]}
            batch_row = {**total_row, "role": "AR"}
            base_doc = {"mode": "fetch", "reqNo": "AR90006", "fetchedAt": "2099-01-01T00:00:00+08:00",
                        "review_out": "inbox/review/fetch-20261119-180000"}
            (src / "fetched.json").write_text(json.dumps({**base_doc, "items": [total_row]}, ensure_ascii=False), encoding="utf-8")
            bfile = self.feature / saved
            bfile.parent.mkdir(parents=True, exist_ok=True)
            bfile.write_bytes(data)
            (bfile.parent / ".receipt.json").write_text(json.dumps({**base_doc, "items": [batch_row]}, ensure_ascii=False), encoding="utf-8")
            summary = rc.reconcile_update_receipts(self.run, self.feature)
            after = self.record()
            system = self.delivered(after)["system"]["receipt"]
            self.assertEqual(("unknown", "mismatch"), (system["status"], system["batch"]))
            role_c = next(c for c in system["conflicts"] if c["field"] == "role")
            self.assertEqual(("SR", "AR"), (role_c["total"]["value"], role_c["batch"]["value"]))
            self.assertEqual((1, 1), (summary["received"], summary["unknown"]))
            self.assert_summary_matches_items(after)
            self.assert_delivery_kept(before, after)

        # ③ 普通 role 落在评审子树（身份与位置抵触）
        with self.subTest("带 role 的条目落评审子树"):
            self.reset()
            before = self.deliver()
            items = self.delivered(before)
            self.write_import(items["local_material"], acquired_at="2099-01-01T00:00:01+08:00")
            self.write_fetch(items["system"], fetched_at="2099-01-01T00:00:00+08:00")
            for p in (self.feature / "AR" / "story-src" / "fetched.json",
                      self.feature / "inbox" / "review" / "fetch-20261119-180000" / ".receipt.json"):
                doc = json.loads(p.read_text(encoding="utf-8"))
                doc["items"][0]["role"] = "SR"
                p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            summary = rc.reconcile_update_receipts(self.run, self.feature)
            after = self.record()
            system = self.delivered(after)["system"]["receipt"]
            self.assertEqual(("unknown", "mismatch"), (system["status"], system["batch"]))
            self.assertTrue(any(c["field"] == "role" for c in system["conflicts"]))
            self.assertEqual((1, 1), (summary["received"], summary["unknown"]))

        # ④ 旧格式双方缺可选字段（无 role 且无 review_out，落普通批次）→ 不凭空增义务，仍 received
        with self.subTest("旧格式双方无 role 无 review_out 落普通批次"):
            self.reset()
            before = self.deliver()
            items = self.delivered(before)
            self.write_import(items["local_material"], acquired_at="2099-01-01T00:00:01+08:00")
            src = self.feature / "AR" / "story-src"
            src.mkdir(parents=True, exist_ok=True)
            name = Path(items["system"]["destination"]).name
            saved = f"inbox/fetch-legacy/{name}"
            row = {"name": name, "ticket": "AR90006", "status": "fetched", "saved": saved,
                   "sha256": items["system"]["sha256"], "bytes": items["system"]["bytes"]}
            doc = {"mode": "fetch", "reqNo": "AR90006", "fetchedAt": "2099-01-01T00:00:00+08:00", "items": [row]}
            (src / "fetched.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            bfile = self.feature / saved
            bfile.parent.mkdir(parents=True, exist_ok=True)
            bfile.write_bytes((self.root / "system" / "AR90006" / name).read_bytes())
            (bfile.parent / ".receipt.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            summary = rc.reconcile_update_receipts(self.run, self.feature)
            after = self.record()
            system = self.delivered(after)["system"]["receipt"]
            self.assertEqual(("received", "verified"), (system["status"], system["batch"]))
            self.assertEqual(2, summary["received"])
            self.assert_summary_matches_items(after)
            self.assert_delivery_kept(before, after)

    def test_a_fetched_review_item_without_review_out_is_still_received(self) -> None:
        """`review_out` 不是收到的前提：总回执与批次回执都没写 review_out 时，落点与批次一致的
        评审件仍按批次回执与时间记 received，不新增「所有回执都须有 review_out」的义务。"""
        before = self.deliver()
        items = self.delivered(before)
        self.write_import(items["local_material"], acquired_at="2099-01-01T00:00:01+08:00")
        self.write_fetch(items["system"], fetched_at="2099-01-01T00:00:00+08:00")
        for path in (self.feature / "AR" / "story-src" / "fetched.json",
                     self.feature / "inbox" / "review" / "fetch-20261119-180000" / ".receipt.json"):
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc.pop("review_out", None)
            path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        summary = rc.reconcile_update_receipts(self.run, self.feature)
        after = self.record()
        system = self.delivered(after)["system"]["receipt"]
        self.assertEqual(("received", "verified"), (system["status"], system["batch"]),
                         "没有 review_out 的评审件被当成了位置不闭合")
        self.assertNotIn("review_out", system)
        self.assertEqual(2, summary["received"])
        self.assert_summary_matches_items(after)
        self.assert_delivery_kept(before, after)

    def test_review_locations_escaping_the_feature_root_are_unknown(self) -> None:
        """落点逃出需求根按现有规则不认：批次条目 saved 或 review_out 指 ../outside 都不是同一原件/
        同一批次，系统件记 unknown，并保留回执写下的原值。"""
        for name, mutate in (("批次条目 saved 逃出需求根", "batch_saved"),
                             ("review_out 逃出需求根", "review_out")):
            with self.subTest(name):
                self.reset()
                before = self.deliver()
                items = self.delivered(before)
                self.write_import(items["local_material"], acquired_at="2099-01-01T00:00:01+08:00")
                self.write_fetch(items["system"], fetched_at="2099-01-01T00:00:00+08:00")
                if mutate == "batch_saved":
                    path = self.feature / "inbox" / "review" / "fetch-20261119-180000" / ".receipt.json"
                    doc = json.loads(path.read_text(encoding="utf-8"))
                    doc["items"][0]["saved"] = "../outside/review-feedback.md"
                else:
                    path = self.feature / "AR" / "story-src" / "fetched.json"
                    doc = json.loads(path.read_text(encoding="utf-8"))
                    doc["review_out"] = "../outside"
                path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
                summary = rc.reconcile_update_receipts(self.run, self.feature)
                after = self.record()
                system = self.delivered(after)["system"]["receipt"]
                self.assertEqual("unknown", system["status"], f"{name}：逃出需求根的落点仍被判 received")
                conflict = system["conflicts"][-1]
                self.assertEqual("saved" if mutate == "batch_saved" else "review_out", conflict["field"])
                self.assertIn("../outside", str(conflict["got"]))
                self.assertEqual(1, summary["unknown"])
                self.assert_summary_matches_items(after)
                self.assert_delivery_kept(before, after)

    def test_an_item_for_another_requirement_is_unknown(self) -> None:
        """总回执的 reqNo 或同名条目的 ticket 指向另一需求：这一件不属于本次投放，
        保留回执原值记 unknown，不按文件同名、时间与 SHA 相同就算收到。"""
        for name, change in (
            ("总回执 reqNo 指向另一需求", lambda doc: doc.__setitem__("reqNo", "AR-other")),
            ("条目 ticket 指向另一需求", lambda doc: doc["items"][0].__setitem__("ticket", "AR-other")),
        ):
            with self.subTest(name):
                self.reset()
                before = self.deliver()
                items = self.delivered(before)
                self.write_fetch(items["system"], fetched_at="2099-01-01T00:00:00+08:00")
                path = self.feature / "AR" / "story-src" / "fetched.json"
                doc = json.loads(path.read_text(encoding="utf-8"))
                change(doc)
                path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
                summary = rc.reconcile_update_receipts(self.run, self.feature)
                after = self.record()
                system = self.delivered(after)["system"]["receipt"]
                self.assertEqual("unknown", system["status"], f"{name}：身份不符却判 received")
                self.assertTrue(system.get("identity"), "身份冲突的原值没有留下")
                self.assertEqual(0, summary["received"])
                self.assert_summary_matches_items(after)
                self.assert_delivery_kept(before, after)

    def test_same_name_entries_with_opposite_status_are_unknown(self) -> None:
        """同一件在总回执同时有 fetched 与 absent：不优先 fetched、也不取第一个同名条目，
        各条原值都留着，归 unknown 并写明冲突。"""
        before = self.deliver()
        items = self.delivered(before)
        self.write_import(items["local_material"], acquired_at="2099-01-01T00:00:01+08:00")
        self.write_fetch(items["system"], fetched_at="2099-01-01T00:00:00+08:00")
        path = self.feature / "AR" / "story-src" / "fetched.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["items"].append({**doc["items"][0], "status": "absent"})
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        summary = rc.reconcile_update_receipts(self.run, self.feature)
        after = self.record()
        system = self.delivered(after)["system"]["receipt"]
        self.assertEqual("unknown", system["status"], "按有利的那一条给出了确定结论")
        self.assertEqual(["fetched", "absent"], [i["status"] for i in system["items"]])
        self.assertIn("互相矛盾", system["why"])
        self.assertEqual((1, 1), (summary["received"], summary["unknown"]))
        self.assert_summary_matches_items(after)
        self.assert_delivery_kept(before, after)

    def test_a_negative_receipt_contradicted_by_its_batch_is_unknown(self) -> None:
        """总回执记 absent、同次关联批次明细却记 fetched：不按任意一侧给确定结论，
        保留两边的状态与摘要归 unknown，不记 not_received。"""
        before = self.deliver()
        items = self.delivered(before)
        self.write_fetch(items["system"], fetched_at="2099-01-01T00:00:00+08:00")
        path = self.feature / "AR" / "story-src" / "fetched.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["items"][0]["status"] = "absent"
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        summary = rc.reconcile_update_receipts(self.run, self.feature)
        after = self.record()
        system = self.delivered(after)["system"]["receipt"]
        self.assertEqual(("unknown", "absent"), (system["status"], system["total_status"]))
        self.assertEqual(("fetched", items["system"]["sha256"]),
                         (system["conflict_batch"]["status"], system["conflict_batch"]["sha256"]))
        self.assertIn("同次同件相互矛盾", system["why"])
        self.assertEqual(0, summary["not_received"])
        self.assert_summary_matches_items(after)
        self.assert_delivery_kept(before, after)

    def test_a_legitimate_negative_receipt_needs_no_file_obligation(self) -> None:
        """absent 本来就没有落盘文件：总回执该件没有 saved、也没有批次可核，
        不妨碍按可归入本次的否定回执记 not_received，不因此记成未知。"""
        before = self.deliver()
        items = self.delivered(before)
        name = Path(items["system"]["destination"]).name
        src = self.feature / "AR" / "story-src"
        src.mkdir(parents=True, exist_ok=True)
        receipt = {"mode": "fetch", "reqNo": "AR90006", "fetchedAt": "2099-01-01T00:00:00+08:00",
                   "items": [{"name": name, "label": "评审人留下的回稿", "ticket": "AR90006",
                              "status": "absent", "note": "系统上现在没有这一份"}]}
        (src / "fetched.json").write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
        summary = rc.reconcile_update_receipts(self.run, self.feature)
        after = self.record()
        system = self.delivered(after)["system"]["receipt"]
        self.assertEqual(("not_received", "本次取材回执记 review-feedback.md 为 absent：系统上现在没有这一份"),
                         (system["status"], system["why"]))
        self.assertNotIn("batch", system)
        self.assertEqual(1, summary["not_received"])
        self.assert_summary_matches_items(after)
        self.assert_delivery_kept(before, after)

    def test_an_earlier_absent_receipt_is_not_this_deliverys(self) -> None:
        """早于投放的 absent 不可归入本次投放：不记本次 not_received，记 unknown 并写明回执早于投放；
        回执没有时刻时同样不可判，不把「读不到时刻」当成「投放之后」。"""
        for name, fetched_at in (("回执早于投放", "2020-01-01T00:00:00+08:00"), ("回执没有时刻", "")):
            with self.subTest(name):
                self.reset()
                before = self.deliver()
                items = self.delivered(before)
                self.write_fetch(items["system"], fetched_at=fetched_at, status="absent")
                summary = rc.reconcile_update_receipts(self.run, self.feature)
                after = self.record()
                system = self.delivered(after)["system"]["receipt"]
                self.assertEqual("unknown", system["status"], f"{name}：否定回执被判成本次没收到")
                self.assertEqual(0, summary["not_received"])
                self.assert_summary_matches_items(after)
                self.assert_delivery_kept(before, after)
                if fetched_at:
                    self.assertIn("早于本次投放", system["why"])
                else:
                    self.assertIn("没有可比的时刻", system["why"])

    def test_a_local_import_without_a_time_is_not_an_exact_receipt(self) -> None:
        """本地件同 SHA 但没有导入时刻：不可比就不是「不更早」，记 unknown，不判 received/exact。"""
        before = self.deliver()
        items = self.delivered(before)
        self.write_import(items["local_material"], acquired_at="")
        summary = rc.reconcile_update_receipts(self.run, self.feature)
        after = self.record()
        local = self.delivered(after)["local_material"]["receipt"]
        self.assertEqual("unknown", local["status"])
        self.assertIn("没有可比的导入时刻", local["why"])
        self.assertNotEqual("exact", local.get("granularity"))
        self.assertEqual(0, summary["received"])
        self.assert_summary_matches_items(after)
        self.assert_delivery_kept(before, after)

    def test_a_fetch_receipt_without_a_time_is_not_an_exact_receipt(self) -> None:
        """系统件同 SHA、批次可核，但取材回执没有时刻：无法判断是否在投放之后，记 unknown。"""
        before = self.deliver()
        items = self.delivered(before)
        self.write_fetch(items["system"], fetched_at="")
        summary = rc.reconcile_update_receipts(self.run, self.feature)
        after = self.record()
        system = self.delivered(after)["system"]["receipt"]
        self.assertEqual(("unknown", "verified"), (system["status"], system["batch"]))
        self.assertIn("没有可比的时刻", system["why"])
        self.assertEqual(0, summary["received"])
        self.assert_summary_matches_items(after)
        self.assert_delivery_kept(before, after)

    def test_a_fetch_with_other_bytes_is_unknown_not_received(self) -> None:
        """本次取回的字节与投放的不是同一版：记 unknown 并给出回执摘要，不按 received 计。"""
        payload = self.deliver()
        items = self.delivered(payload)
        self.write_fetch(items["system"], fetched_at="2099-01-01T00:00:00+08:00", sha="0" * 64)
        rc.reconcile_update_receipts(self.run, self.feature)
        system = self.delivered(self.record())["system"]["receipt"]
        self.assertEqual(("unknown", "本次取回的字节与投放的不是同一版（回执 sha256 不同）"),
                         (system["status"], system["why"]))

    def test_the_old_global_received_at_source_is_kept_apart_and_never_used(self) -> None:
        """旧格式（schema 1）的统一 received_at_source 不是逐件依据：另存原值并标 legacy；
        旧记录没有逐件原件摘要时按 unknown 记，不据旧字段推本地件被接收。"""
        payload = self.deliver()
        payload["schema_version"] = 1
        payload["received_at_source"] = "model fetch receipt (fetched.json fetchedAt)"
        for item in payload["delivered"]:
            item.pop("receipt", None)
            item.pop("sha256", None)
        self.rewrite(payload)
        summary = rc.reconcile_update_receipts(self.run, self.feature)
        payload = self.record()
        self.assertNotIn("received_at_source", payload)
        self.assertEqual("model fetch receipt (fetched.json fetchedAt)", payload["legacy_received_at_source"])
        self.assertTrue(summary["legacy"])
        for item in payload["delivered"]:
            self.assertEqual("unknown", item["receipt"]["status"])
            self.assertIn("旧格式", item["receipt"]["why"])
        self.assertEqual("checked", payload["receipt_check"]["status"])

    def test_no_record_means_nothing_to_reconcile(self) -> None:
        self.assertIsNone(rc.reconcile_update_receipts(self.run, self.feature))


if __name__ == "__main__":
    unittest.main()
