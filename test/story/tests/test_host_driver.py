"""宿主装置不替模型说话、不吞模型的问题：检查点留着待答的一问，规划对上才展示，检查点不收回话，
watch 只敲门，评审表态按原换行写进议题人工区。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "test" / "story" / "scripts"
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
    """AC29：第一检查点带着模型那一问；续跑先答它，再投业务请求。"""

    def test_the_resume_request_carries_the_answer_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / rc.RESUME_FILE).write_text(json.dumps(
                {"text": "/story update AR90006", "answer": "归档送审。"}, ensure_ascii=False),
                encoding="utf-8")
            got = rc.pop_resume_request(out)
            self.assertEqual({"text": "/story update AR90006", "answer": "归档送审。"}, got)
            self.assertFalse((out / rc.RESUME_FILE).exists(), "取走之后请求还在")

    def test_waiting_at_the_checkpoint_shows_the_models_question(self) -> None:
        feed, runlog = mock.Mock(), mock.Mock()
        state: dict = {}
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(rc, "refresh_worker_lease"), \
                mock.patch.object(rc, "pop_resume_request",
                                  return_value={"text": "继续", "answer": "进入 plan。"}):
            got = rc.wait_for_resume(Path(tmp), feed, runlog, state, turn=7,
                                     pending="要归档送审，还是进入 plan？")
        self.assertEqual("要归档送审，还是进入 plan？", state["awaiting_prompt"])
        self.assertEqual("要归档送审，还是进入 plan？", state["pending_question"])
        emitted = feed.emit.call_args_list[0]
        self.assertEqual("initial_checkpoint", emitted.args[0])
        self.assertEqual("要归档送审，还是进入 plan？", emitted.kwargs["pending_question"])
        self.assertEqual("进入 plan。", got["answer"])


class ThePlanIsShownOnlyWhenItFits(unittest.TestCase):
    """AC30：规划条目与当前提问不相符时不展示，标「规划里没有对应这一问」。"""

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

    def test_an_unknown_phase_does_not_get_it(self) -> None:
        got = self.request(self.record("story_gate", None))
        self.assertIsNone(got["planned_step_id"])
        self.assertIn("规划里没有对应这一问", got["plan_note"])

    def test_a_matching_gate_gets_the_stance(self) -> None:
        got = self.request(self.record("story_gate", "spec"))
        self.assertEqual("enter-plan", got["planned_step_id"])
        self.assertIsNone(got["plan_note"])


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


class TheReviewVerdictLandsInTheIssueZone(unittest.TestCase):
    """AC32：评审表态写进对应议题的人工区，评审记录的换行保持原样。"""

    def write(self, root: Path, newline: str) -> Path:
        review = root / "AR" / "review.md"
        review.parent.mkdir(parents=True)
        review.write_bytes(REVIEW.replace("\n", newline).encode("utf-8"))
        return review

    def feedback(self, root: Path) -> Path:
        f = root / "feedback.yaml"
        f.write_text("- match: [撤销]\n  verdict: 需修改\n  opinion: 定为 36 小时。\n"
                     "- match: [不存在的议题]\n  verdict: 暂缓\n  opinion: 仍不定。\n", encoding="utf-8")
        return f

    def test_it_ticks_the_verdict_and_writes_the_opinion(self) -> None:
        for newline in ("\n", "\r\n"):
            with self.subTest(newline=repr(newline)), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                review = self.write(root, newline)
                done = rc._write_review_zones(root, self.feedback(root))
                raw = review.read_bytes().decode("utf-8")
                self.assertEqual(REVIEW.count("\n"), raw.count(newline), "换行被改了")
                if newline == "\n":
                    self.assertNotIn("\r", raw)
                text = raw.replace("\r\n", "\n")
                first, second = text.split("#### 1.1.2", 1)
                self.assertIn("- [x] 需修改", first)
                self.assertIn("修改意见：定为 36 小时。", first)
                self.assertNotIn("- [x]", second, "写到了别的议题")
                self.assertIn("没有写", done[1]["note"])


if __name__ == "__main__":
    unittest.main()
