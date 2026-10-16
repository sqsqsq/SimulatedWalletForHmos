"""业务收口不等于交付完成：装置在目标阶段（与第二段 update）收口时消费产品的本地阅读状态。

自动用例里产品给了可执行的下一动作、且待办与上次转交时不同，就原样交回同一段；交互用例、状态判不了、
转交后没有可见变化，都沿既有停等交宿主决定继续或停止；会话续不了不续。阅读状态按产品输出合同校验，
缺字段、类型错、自相矛盾都是判不了，不当完成或不适用。CLI 用替身，被测的是 worker 的真实续行与终态判定。
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


def pending(fig_state: str) -> dict:
    return {"state": "pending", "items": [{"id": "fig-a", "state": fig_state, "reason": f"fig-a {fig_state}"}],
            "unmanaged": [], "problems": [], "next": f"完成本地阅读：fig-a {fig_state}"}


DONE = {"state": "complete", "items": [{"id": "fig-a", "state": "ready", "reason": ""}],
        "unmanaged": [], "problems": [], "next": None}
UNKNOWN = {"state": "unknown", "error": "本地阅读状态读不出（退出码 1：node 起不来）"}


class FakeClient:
    """每次 start 记下 prompt；每个 run 一页事件就结束，带模型这一轮说的话与 session。"""

    def __init__(self, said: str = "这一轮做完了", status: str = "succeeded") -> None:
        self.prompts: list[str] = []
        self.said, self.status = said, status

    def start(self, request):
        self.prompts.append(request.prompt)
        return SimpleNamespace(run_id=f"r{len(self.prompts)}")

    def poll(self, run_id, **_):
        event = SimpleNamespace(type="text", content=self.said, session_id=None, to_dict=lambda: {"type": "text"})
        return SimpleNamespace(events=[event], next_cursor=1, has_more=False,
                               run={"status": self.status, "session_id": "s1"})

    def stop(self, *_, **__):
        return None


class TheWorkerFinishesTheReading(unittest.TestCase):
    def drive(self, readings: list[dict], *, after_initial: str = "", interactive: bool = False,
              resume: dict | None = None, host: list | None = None, client: FakeClient | None = None) -> dict:
        """`readings[n]` 是模型跑完第 n+1 轮之后读到的阅读状态；`host` 依次是宿主在阅读停等上的回话（None = 收工）。"""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "run"
        client = self.client = client or FakeClient()
        answers = list(host or [])
        self.asked: list[tuple[int, str, str]] = []

        def ask(*_, prompt: str = "", kind: str = "story_gate", **__):
            self.asked.append((len(client.prompts), kind, prompt))
            return answers.pop(0) if answers else None

        case = {"prompt": "执行 /story init", "end_phase": "spec", "after_initial": after_initial,
                "interactive": interactive}
        resumed: list = []
        p = unittest.mock.patch.object
        for patch in (
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
            p(rc, "reading_facts", side_effect=lambda *_a, **_k: readings[min(len(client.prompts), len(readings)) - 1]),
            p(rc, "run_gates", return_value={}),
            p(rc, "expected_gate_names", return_value=()),
            p(rc, "build_phase_results", return_value={}),
            p(rc, "publish_phase_results", return_value=[]),
            p(rc, "derive_phase_state", return_value={}),
            p(rc, "wait_for_human_reply", side_effect=ask),
            p(rc, "wait_for_resume", side_effect=lambda *a, **k: resumed.append(len(client.prompts)) or resume),
            unittest.mock.patch("sys.stdout", new_callable=io.StringIO),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.resumed = resumed
        rc.foreground("case", prepared=False)
        return json.loads((out / "state.json").read_text(encoding="utf-8"))

    def test_legitimate_work_takes_as_many_rounds_as_it_needs(self) -> None:
        stages = ["no-svg", "no-request", "no-report", "incomplete"]
        state = self.drive([pending(s) for s in stages] + [DONE])
        self.assertEqual(len(stages) + 1, len(self.client.prompts), "有可见进展的正常工作被次数截断")
        for i, s in enumerate(stages, start=1):
            self.assertIn(f"fig-a {s}", self.client.prompts[i], "续话没转交产品给的下一动作")
        self.assertEqual([], self.asked)
        self.assertEqual("completed_at_requested_end", state["pipeline"]["status"])

    def test_no_visible_change_goes_to_the_host_who_can_let_it_continue(self) -> None:
        """待办没变不等于没在干：转交后没有可见变化就交宿主，宿主说继续就继续，做完照常完成。"""
        state = self.drive([pending("no-svg"), pending("no-svg"), DONE], host=["接着画，渲染图还在生成"])
        self.assertEqual(1, len(self.asked))
        at, kind, prompt = self.asked[0]
        self.assertEqual((2, "local_reading"), (at, kind))
        self.assertIn("这一轮做完了", prompt, "交宿主时丢了模型原话")
        self.assertIn("没有可见变化", prompt)
        self.assertEqual("接着画，渲染图还在生成", self.client.prompts[2])
        self.assertEqual("completed_at_requested_end", state["pipeline"]["status"])

    def test_a_missing_capability_stops_only_when_the_host_says_so(self) -> None:
        client = FakeClient(said="我看不了图片，没法核对渲染结果。要怎么处理？")
        state = self.drive([pending("no-report")], host=[None], client=client)
        self.assertEqual(2, len(client.prompts), "交了宿主却还在自动续")
        self.assertIn("我看不了图片", self.asked[0][2])
        self.assertEqual("business_closed_reading_incomplete", state["pipeline"]["status"])
        self.assertEqual("finished", state["status"], "进程收场照常记 finished，任务目标另说")

    def test_an_interactive_case_asks_the_host_at_once(self) -> None:
        """交互用例里模型这一轮可能正在问人：不拿产品待办替人回答，直接交宿主。"""
        client = FakeClient(said="分享入口那张图要不要拆成两张？")
        state = self.drive([pending("no-svg"), DONE], interactive=True, host=["拆成两张"], client=client)
        self.assertEqual((1, "local_reading"), self.asked[0][:2])
        self.assertIn("要不要拆成两张", self.asked[0][2])
        self.assertEqual("拆成两张", client.prompts[1])
        self.assertEqual("completed_at_requested_end", state["pipeline"]["status"])

    def test_an_unreadable_status_goes_to_the_host_not_to_not_applicable(self) -> None:
        state = self.drive([UNKNOWN], host=[None])
        self.assertIn("判不了", self.asked[0][2])
        self.assertEqual("business_closed_reading_incomplete", state["pipeline"]["status"])

    def test_a_session_that_cannot_continue_is_not_continued(self) -> None:
        client = FakeClient(status="failed")
        state = self.drive([pending("no-svg")], client=client)
        self.assertEqual(1, len(client.prompts))
        self.assertEqual([], self.asked)
        self.assertNotEqual("completed_at_requested_end", state["pipeline"]["status"])

    def test_a_host_conclusion_ends_the_run_with_the_reading_unfinished(self) -> None:
        with unittest.mock.patch.object(rc, "pop_conclude_request", return_value={"reason": "够了"}):
            state = self.drive([pending("no-svg")])
        self.assertEqual(1, len(self.client.prompts))
        self.assertNotEqual("completed_at_requested_end", state["pipeline"]["status"])

    def test_the_first_checkpoint_waits_for_the_reading(self) -> None:
        self.drive([pending("no-svg"), DONE], after_initial="update")
        self.assertEqual([2], self.resumed, "阅读没做完就停到了第一检查点")
        self.assertIn("fig-a no-svg", self.client.prompts[1])

    def test_the_second_checkpoint_waits_for_the_reading_too(self) -> None:
        """update 改了图之后阅读又有待办：第二段收口时同样续同一段，做完再停到第二检查点。"""
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
        self.drive([DONE, pending("svg-stale"), DONE], after_initial="update", resume={"answer": "", "text": "按评审改"})
        self.assertEqual([3], stopped, "update 后阅读没做完就停到了第二检查点")
        self.assertIn("按评审改", self.client.prompts[1])
        self.assertIn("fig-a svg-stale", self.client.prompts[2])


GOOD_PENDING = {"applicable": True, "complete": False, "items": [{"id": "f", "line": 3, "state": "invalid-block",
                "reason": "块坏了"}], "unmanaged": [7], "problems": ["孤立标记"], "next": "去修"}


class TheReadingFactsKeepTheProductsContract(unittest.TestCase):
    """产品输出 → reading_facts → closure_facts 的整体目标，同一组变体结论一致。"""

    def facts(self, stdout: str, code: int = 0, *, story: bool = True, required: bool = False) -> dict:
        with tempfile.TemporaryDirectory() as d:
            fr = Path(d) / "AR1"
            (fr / "AR").mkdir(parents=True)
            if story:
                (fr / "AR" / "story.md").write_text("# 甲\n", encoding="utf-8")
            done = SimpleNamespace(returncode=code, stdout=stdout, stderr="坏了" if code else "")
            with unittest.mock.patch.object(rc.subprocess, "run", return_value=done):
                return rc.reading_facts(fr, story_required=required)

    def closure_complete(self, reading: dict) -> bool:
        p = unittest.mock.patch.object
        with p(rc, "reading_facts", return_value=reading), p(rc, "target_reached", return_value=True), \
                p(rc, "phase_evidence_complete", return_value=(True, [])), p(rc, "artifacts_ready", return_value=True), \
                p(rc, "next_unclosed_phase", return_value=None), p(rc, "phase_was_reached", return_value=False):
            return rc.closure_facts("AR1", "story", "spec")["target_complete"]

    def test_each_variant_has_one_conclusion_down_the_chain(self) -> None:
        variants = {
            "合法无图": (json.dumps({"applicable": False, "complete": True, "items": [], "unmanaged": [], "problems": [],
                                  "next": None}), "not_applicable"),
            "全部就绪": (json.dumps({"applicable": True, "complete": True, "items": [{"id": "f", "line": 3, "state": "ready",
                                  "reason": ""}], "unmanaged": [], "problems": [], "next": None}), "complete"),
            "有待办": (json.dumps(GOOD_PENDING), "pending"),
            "读取失败": ("{}", "unknown"),
            "缺 applicable": (json.dumps({"complete": False, "items": [], "problems": ["unresolved"]}), "unknown"),
            "applicable 是文字": (json.dumps({**GOOD_PENDING, "applicable": "yes"}), "unknown"),
            "说完成却有问题": (json.dumps({**GOOD_PENDING, "complete": True, "next": None}), "unknown"),
            "说不适用却有问题": (json.dumps({"applicable": False, "complete": True, "items": [], "unmanaged": [],
                                     "problems": ["unresolved"], "next": None}), "unknown"),
            "没完成却没下一动作": (json.dumps({**GOOD_PENDING, "next": None}), "unknown"),
            "没完成却没有待办": (json.dumps({"applicable": True, "complete": False, "items": [], "unmanaged": [],
                                     "problems": [], "next": "去做"}), "unknown"),
            "没就绪却没原因": (json.dumps({**GOOD_PENDING, "items": [{"id": "f", "line": 3, "state": "no-svg", "reason": ""}]}),
                         "unknown"),
        }
        for name, (out, want) in variants.items():
            with self.subTest(name):
                got = self.facts(out, 1 if name == "读取失败" else 0)
                self.assertEqual(want, got["state"], got)
                self.assertEqual(want in ("complete", "not_applicable"), self.closure_complete(got))
                if want == "unknown":
                    self.assertTrue(got["error"])
        kept = self.facts(json.dumps(GOOD_PENDING))
        self.assertEqual(("块坏了", [7], ["孤立标记"], "去修"),
                         (kept["items"][0]["reason"], kept["unmanaged"], kept["problems"], kept["next"]))

    def test_a_missing_story_is_not_applicable_only_before_the_story_is_due(self) -> None:
        self.assertEqual("not_applicable", self.facts("", story=False)["state"])
        got = self.facts("", story=False, required=True)
        self.assertEqual("unknown", got["state"])
        self.assertFalse(self.closure_complete(got))


if __name__ == "__main__":
    unittest.main()
