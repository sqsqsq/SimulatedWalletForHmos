"""业务收口不等于交付完成：装置在目标阶段（与第二段 update）收口时消费产品的本地阅读状态。

阅读待办在就把产品给的下一动作交回同一段继续；同一待办连续没变化就不再续，如实记未完成；
读不出的阅读状态不当不适用。CLI 用替身，被测的是 worker 的真实续行与终态判定。
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path
from types import SimpleNamespace

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_case as rc  # noqa: E402

PENDING_A = {"state": "pending", "items": [{"id": "fig-a", "state": "no-svg", "reason": "还没有阅读图"}],
             "unmanaged": [], "problems": [], "next": "完成本地阅读：fig-a 还没有阅读图"}
PENDING_B = {**PENDING_A, "items": [{"id": "fig-a", "state": "no-request", "reason": "还没有验收请求"}],
             "next": "完成本地阅读：fig-a 还没有验收请求"}
DONE = {"state": "complete", "items": [{"id": "fig-a", "state": "ready", "reason": ""}],
        "unmanaged": [], "problems": [], "next": None}
UNKNOWN = {"state": "unknown", "error": "本地阅读状态读不出（退出码 1：node 起不来）"}


class FakeClient:
    """每次 start 记下 prompt；每个 run 一页事件就结束、成功、带同一 session。"""

    def __init__(self, runtime_root=None) -> None:
        self.prompts: list[str] = []

    def start(self, request):
        self.prompts.append(request.prompt)
        return SimpleNamespace(run_id=f"r{len(self.prompts)}")

    def poll(self, run_id, **_):
        return SimpleNamespace(events=[], next_cursor=1, has_more=False,
                               run={"status": "succeeded", "session_id": "s1"})

    def stop(self, *_, **__):
        return None


class TheWorkerFinishesTheReading(unittest.TestCase):
    def drive(self, readings: list[dict], *, after_initial: str = "",
              resume: dict | None = None) -> tuple[dict, FakeClient, list]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "run"
        client = self.client = FakeClient()

        def next_reading(_root):
            # 阅读状态只随模型又干了一轮而变：第 n 轮之后读到的是第 n 份
            return readings[min(len(client.prompts), len(readings)) - 1]

        resumed: list = []
        case = {"prompt": "执行 /story init", "end_phase": "spec", "after_initial": after_initial}
        p = unittest.mock.patch.object
        patches = [
            p(rc, "_load_case_definition", return_value=(case, None, "AR1")),
            p(rc.run_layout, "read_pointer", return_value=None),
            p(rc.run_layout, "create_run", return_value=(out, "run1")),
            p(rc.run_layout, "publish_latest", return_value=None),
            p(rc, "select_cli", return_value={"id": "c", "name": "cli", "model": "m", "profile": None}),
            p(rc, "build_cli_env", return_value={}),
            p(rc, "CliClient", return_value=client),
            p(rc, "snapshot_phase_slot", return_value=None),
            p(rc, "restore_phase_slot", return_value="kept"),
            p(rc, "should_migrate_feature_history", return_value=False),
            p(rc, "phase_before", return_value=None),
            p(rc, "compute_upstream_fingerprint", return_value=None),
            p(rc, "interval_contains_coding", return_value=False),
            p(rc, "artifacts_ready", return_value=True),
            p(rc, "phase_evidence_complete", return_value=(True, [])),
            p(rc, "phase_was_reached", return_value=False),
            p(rc, "reading_facts", side_effect=next_reading),
            p(rc, "run_gates", return_value={}),
            p(rc, "expected_gate_names", return_value=()),
            p(rc, "build_phase_results", return_value={}),
            p(rc, "publish_phase_results", return_value=[]),
            p(rc, "derive_phase_state", return_value={}),
            p(rc, "wait_for_resume", side_effect=lambda *a, **k: resumed.append(len(client.prompts)) or resume),
            unittest.mock.patch("sys.stdout", new_callable=io.StringIO),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        rc.foreground("case", prepared=False)
        state = json.loads((out / "state.json").read_text(encoding="utf-8"))
        return state, client, resumed

    def test_the_products_next_action_is_handed_back_until_the_reading_is_done(self) -> None:
        state, client, _ = self.drive([PENDING_A, PENDING_B, DONE])
        self.assertEqual(3, len(client.prompts), client.prompts)
        self.assertIn("fig-a 还没有阅读图", client.prompts[1], "续话没转交产品给的下一动作")
        self.assertIn("fig-a 还没有验收请求", client.prompts[2])
        self.assertEqual("completed_at_requested_end", state["pipeline"]["status"])

    def test_a_reading_that_stops_moving_is_reported_unfinished(self) -> None:
        state, client, _ = self.drive([PENDING_A])
        self.assertEqual(1 + rc.READING_ATTEMPTS, len(client.prompts), "同一待办没有变化却一直续")
        self.assertEqual("business_closed_reading_incomplete", state["pipeline"]["status"])
        self.assertEqual("finished", state["status"], "进程收场照常记 finished，任务目标另说")

    def test_an_unreadable_status_is_not_taken_as_no_figures(self) -> None:
        state, client, _ = self.drive([UNKNOWN, DONE])
        self.assertIn("读不出", client.prompts[1])
        self.assertEqual("completed_at_requested_end", state["pipeline"]["status"])
        state, _, _ = self.drive([UNKNOWN])
        self.assertEqual("business_closed_reading_incomplete", state["pipeline"]["status"])

    def test_the_first_checkpoint_waits_for_the_reading(self) -> None:
        _, client, resumed = self.drive([PENDING_A, DONE], after_initial="update")
        self.assertEqual([2], resumed, "阅读没做完就停到了第一检查点")
        self.assertIn("fig-a 还没有阅读图", client.prompts[1])

    def test_the_second_checkpoint_waits_for_the_reading_too(self) -> None:
        """update 改了图之后阅读又有待办：第二段收口时同样先把它做完，再停到第二检查点。"""
        stopped: list[int] = []
        p = unittest.mock.patch.object
        for patch in (
            p(rc, "update_round", side_effect=lambda _f: {"readable": True, "open": None,
                                                        "last_closed": "u0" if len(self.client.prompts) <= 1 else "u1"}),
            p(rc, "_run_story_gates", return_value={}),
            p(rc, "review_closure", return_value={}),
            p(rc, "wait_at_update_checkpoint", side_effect=lambda *a, **k: stopped.append(len(self.client.prompts))),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        _, client, _ = self.drive([DONE, PENDING_A, DONE], after_initial="update",
                                  resume={"answer": "", "text": "按评审改"})
        self.assertEqual([3], stopped, "update 后阅读没做完就停到了第二检查点")
        self.assertIn("按评审改", client.prompts[1])
        self.assertIn("fig-a 还没有阅读图", client.prompts[2])


class TheReadingFactsKeepTheProductsAnswer(unittest.TestCase):
    def facts(self, stdout: str, code: int = 0) -> dict:
        with tempfile.TemporaryDirectory() as d:
            fr = Path(d) / "AR1"
            (fr / "AR").mkdir(parents=True)
            (fr / "AR" / "story.md").write_text("# 甲\n", encoding="utf-8")
            done = SimpleNamespace(returncode=code, stdout=stdout, stderr="坏了" if code else "")
            with unittest.mock.patch.object(rc.subprocess, "run", return_value=done):
                return rc.reading_facts(fr)

    def test_reasons_problems_and_next_action_survive(self) -> None:
        got = self.facts(json.dumps({"applicable": True, "complete": False, "items": [{"id": "f", "state": "invalid-block",
                                     "reason": "块坏了"}], "unmanaged": [3], "problems": ["孤立标记"], "next": "去修"}))
        self.assertEqual("pending", got["state"])
        self.assertEqual(("块坏了", [3], ["孤立标记"], "去修"),
                         (got["items"][0]["reason"], got["unmanaged"], got["problems"], got["next"]))

    def test_a_failed_or_misshapen_answer_is_unknown(self) -> None:
        for name, (out, code) in {"退出码非 0": ("{}", 1), "不是 JSON": ("不是 JSON", 0),
                                 "缺 complete": (json.dumps({"applicable": False, "items": []}), 0)}.items():
            with self.subTest(name):
                got = self.facts(out, code)
                self.assertEqual("unknown", got["state"])
                self.assertIn("读不出", got["error"])

    def test_the_whole_target_needs_both(self) -> None:
        self.assertFalse(rc.target_complete({"target_closed": True, "reading": PENDING_A}))
        self.assertFalse(rc.target_complete({"target_closed": True, "reading": UNKNOWN}))
        self.assertTrue(rc.target_complete({"target_closed": True, "reading": {"state": "not_applicable"}}))
        self.assertFalse(rc.target_complete({"target_closed": False, "reading": DONE}))


if __name__ == "__main__":
    unittest.main()
