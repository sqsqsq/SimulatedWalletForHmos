"""宿主装置不替模型说话、不吞模型的问题：检查点留着待答的一问，规划只作候选展示，检查点不收回话，
watch 只敲门，评审表态按宿主指定的 D 议题写进人工区、写前核全、原换行不动。
"""
from __future__ import annotations

import importlib.util
import json
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
    """AC30：检查点等待期间 reply 被拒，说明该用哪个命令。"""

    def test_a_reply_at_the_checkpoint_is_refused(self) -> None:
        for kind in ("initial_checkpoint", "update_checkpoint"):
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


if __name__ == "__main__":
    unittest.main()
