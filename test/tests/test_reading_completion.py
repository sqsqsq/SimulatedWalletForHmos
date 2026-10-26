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
            "problems": [], "next": f"完成本地阅读：fig-a {fig_state}"}


DONE = {"state": "complete", "items": [{"id": "fig-a", "state": "ready", "reason": ""}],
        "problems": [], "next": None}
UNKNOWN = {"state": "unknown", "error": "本地阅读状态读不出（退出码 1：node 起不来）"}


class FakeClient:
    """每次 start 记下 prompt；每个 run 一页事件就结束，带模型这一轮说的话与 session。"""

    def __init__(self, said: str = "这一轮做完了", status: str = "succeeded", session: str | None = "s1") -> None:
        self.prompts: list[str] = []
        self.said, self.status, self.session = said, status, session

    def start(self, request):
        self.prompts.append(request.prompt)
        return SimpleNamespace(run_id=f"r{len(self.prompts)}")

    def poll(self, run_id, **_):
        event = SimpleNamespace(type="text", content=self.said, session_id=None, to_dict=lambda: {"type": "text"})
        return SimpleNamespace(events=[event], next_cursor=1, has_more=False,
                               run={"status": self.status, "session_id": self.session})

    def stop(self, *_, **__):
        return None


class TheWorkerFinishesTheReading(unittest.TestCase):
    def drive(self, readings: list[dict], *, after_initial: str = "", interactive: bool = False,
              resume: dict | list | None = None, host: list | None = None, client: FakeClient | None = None,
              facts=None) -> dict:
        """`readings[n]` 是模型跑完第 n+1 轮之后读到的阅读状态；`host` 依次是宿主在阅读停等上的回话（None = 收工）；
        `resume` 是宿主在第一检查点上的动作，给列表时依次取（None = 收工）。
        `host` 里的 "RECHECK" 表示宿主没回话、停等里装置用传进来的重探回调读到了什么；`facts` 给出就按调用顺序取阅读状态。"""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "run"
        client = self.client = client or FakeClient()
        answers = list(host or [])
        self.asked: list[tuple[int, str, str]] = []

        def ask(*_, prompt: str = "", kind: str = "story_gate", recheck=None, **__):
            self.asked.append((len(client.prompts), kind, prompt))
            answer = answers.pop(0) if answers else None
            if answer == "RECHECK":
                self.assertIsNotNone(recheck, "读不出的停等没给重探回调")
                self.rechecking = True
                got = recheck()
                self.published = json.loads((out / "state.json").read_text(encoding="utf-8"))
                return rc.READING_RECHECK_COMPLETE if got["state"] in ("complete", "not_applicable") else None
            return answer

        case = {"prompt": "执行 /story init", "end_at": "phase:spec", "after_initial": after_initial,
                "interactive": interactive}
        resumed: list = []
        self.checkpoints: list[dict] = []
        plan = list(resume) if isinstance(resume, list) else None

        def at_checkpoint(*_a, **k):
            resumed.append(len(client.prompts))
            self.checkpoints.append(k)
            return (plan.pop(0) if plan else None) if plan is not None else resume

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
            p(rc, "observe_target", return_value={"reached": True, "missing": [], "units": []}),
            p(rc, "reading_facts", side_effect=facts or (lambda *_a, **_k: readings[min(len(client.prompts), len(readings)) - 1])),
            p(rc, "run_gates", return_value={}),
            p(rc, "expected_gate_names", return_value=()),
            p(rc, "build_phase_results", return_value={}),
            p(rc, "publish_phase_results", return_value=[]),
            p(rc, "wait_for_human_reply", side_effect=ask),
            p(rc, "wait_for_resume", side_effect=at_checkpoint),
            unittest.mock.patch("sys.stdout", new=io.StringIO()),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.resumed = resumed
        rc.foreground("case", prepared=False)
        self.result = json.loads(sys.stdout.getvalue())
        return json.loads((out / "state.json").read_text(encoding="utf-8"))

    def update_segment(self) -> list[int]:
        """第二段的替身：第一段收口时更新号是 u0，之后收口成 u1；第二检查点记下进入时跑过几轮。"""
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
        return stopped

    def assert_concluded_once(self, state: dict, rounds: int) -> None:
        self.assertEqual(rounds, len(self.client.prompts), "宿主收工后又起了 CLI 轮次")
        self.assertEqual(1, len(self.asked), "收工被要求了不止一次")
        self.assertEqual(("host_concluded", "host_concluded"),
                         (self.result["stop_reason"], self.result["reading_handoff"]))
        self.assertFalse(self.result["closure"]["target_complete"])
        self.assertEqual("business_closed_reading_incomplete", state["pipeline"]["status"])

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

    def test_a_recovered_unreadable_status_needs_no_human_reply(self) -> None:
        """读不出是技术故障：停等里装置重探到完成，就停到第一检查点，不要宿主回一句「收到」、不多起一轮 CLI。"""
        self.rechecking = False     # 停等里重探之前一直读不出，重探起读得出、已完成
        state = self.drive([], interactive=True, after_initial="update", host=["RECHECK"], resume=None,
                           facts=lambda *_a, **_k: DONE if self.rechecking else UNKNOWN)
        self.assertEqual(1, len(self.client.prompts), "重探恢复后又续了一轮")
        self.assertEqual([1], self.resumed, "恢复后没有停到第一检查点")
        self.assertEqual("complete", self.result["closure"]["reading"]["state"])
        self.assertEqual("complete", self.published["closure"]["reading"]["state"],
                         "重探恢复了，宿主看到的 closure 还是读不出")
        self.assertNotEqual("host_concluded", self.result.get("reading_handoff"), "技术恢复被记成了宿主收工")
        self.assertEqual(0, int(state.get("human_wait_events") or 0), "技术恢复被记成了人答")

    def test_a_pending_probe_is_published_to_the_host(self) -> None:
        """重探读得出了、但确实没做完：宿主看到的 closure 与等待提示换成这份真实待办，不再是读不出。"""
        self.rechecking = False
        self.drive([], interactive=True, after_initial="update", host=["RECHECK"],
                   facts=lambda *_a, **_k: pending("no-report") if self.rechecking else UNKNOWN)
        self.assertEqual("pending", self.published["closure"]["reading"]["state"], "宿主看到的 closure 没跟上重探")
        self.assertIn("fig-a no-report", self.published["awaiting_prompt"], "等待提示还是读不出，没换成真实待办")

    def test_a_pending_status_is_not_rechecked_into_completion(self) -> None:
        """读得出、确实没做完：不给重探回调，照常交宿主；装置不替产品宣布完成。"""
        self.drive([pending("no-report")], interactive=True, host=[None])
        self.assertEqual(1, len(self.asked))

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

    def test_an_interactive_initial_stops_at_the_checkpoint_for_the_delivery_choice(self) -> None:
        """没配第二段的交互用例到目标不立即终止：宿主按交互规划答交付选择，模型做完再停，宿主收工。"""
        client = FakeClient(said="Spec 已闭环。要归档送审，还是先进入 plan？")
        state = self.drive([DONE, DONE], interactive=True, client=client,
                           resume=[{"reply": "归档送审"}, None])
        self.assertEqual([1, 2], self.resumed, "到目标没有停在检查点，或答完后没再停一次")
        self.assertEqual([False, False], [k.get("next_segment") for k in self.checkpoints], "没有第二段却当成有")
        self.assertEqual("归档送审", client.prompts[1], "检查点上的回话没交给同一次对话")
        self.assertEqual("host_concluded", self.result["stop_reason"])
        self.assertTrue(self.result["closure"]["target_complete"])
        self.assertEqual(("finished", "completed_at_requested_end"), (state["status"], state["pipeline"]["status"]))
        self.assertIsNone(state.get("resumed_at"), "没配第二段却进了第二段")

    def test_an_interactive_initial_with_nothing_left_is_concluded(self) -> None:
        """交付已无待办：宿主按原规则在检查点收工，一轮也不多跑。"""
        state = self.drive([DONE], interactive=True, resume=None)
        self.assertEqual([1], self.resumed)
        self.assertEqual(1, len(self.client.prompts))
        self.assertEqual(("host_concluded", "finished"), (self.result["stop_reason"], state["status"]))

    def test_an_interactive_initial_without_a_session_is_not_reported_finished(self) -> None:
        """交付选择还在等人答而 CLI 没给回 session：如实报会话丢失，不报到达目标，也不另起一轮冒充续行。"""
        client = FakeClient(said="Spec 已闭环。1 归档送审 / 2 进入 plan，请选择", session=None)
        state = self.drive([DONE], interactive=True, client=client, resume={"reply": "归档送审"})
        self.assertEqual([], self.resumed, "续不了的会话停到了检查点")
        self.assertEqual(1, len(client.prompts), "另起了一轮")
        self.assertEqual("cli_session_lost", self.result["stop_reason"])
        self.assertNotEqual("finished", state["status"], "阶段闭环冒充了本段交付完成")
        self.assertIsNone(state.get("cli_session_id"))

    def test_an_automatic_initial_still_ends_at_the_target(self) -> None:
        state = self.drive([DONE])
        self.assertEqual([], self.resumed, "自动用例到目标不该停在检查点")
        self.assertEqual(("target_reached", "finished"), (self.result["stop_reason"], state["status"]))

    def test_the_first_checkpoint_waits_for_the_reading(self) -> None:
        self.drive([pending("no-svg"), DONE], after_initial="update")
        self.assertEqual([2], self.resumed, "阅读没做完就停到了第一检查点")
        self.assertIn("fig-a no-svg", self.client.prompts[1])

    def test_a_conclusion_during_the_first_reading_wait_ends_the_run(self) -> None:
        """阅读停等里宿主收工：这就是结束运行，不再进第一检查点等第二次收工。"""
        stopped = self.update_segment()
        state = self.drive([pending("no-report")], after_initial="update", host=[None])
        self.assertEqual([], self.resumed, "收工之后还进了第一检查点")
        self.assertEqual([], stopped)
        self.assert_concluded_once(state, rounds=2)

    def test_a_conclusion_during_the_update_reading_wait_ends_the_run(self) -> None:
        stopped = self.update_segment()
        state = self.drive([DONE, pending("stale")], after_initial="update", host=[None],
                           resume={"answer": "", "text": "按评审改"})
        self.assertEqual([1], self.resumed, "第一段本该正常停到第一检查点")
        self.assertEqual([], stopped, "收工之后还进了第二检查点")
        self.assert_concluded_once(state, rounds=3)

    def test_the_second_checkpoint_waits_for_the_reading_too(self) -> None:
        """update 改了图之后阅读又有待办：第二段收口时同样续同一段，做完再停到第二检查点。"""
        stopped = self.update_segment()
        self.drive([DONE, pending("stale"), DONE], after_initial="update", resume={"answer": "", "text": "按评审改"})
        self.assertEqual([3], stopped, "update 后阅读没做完就停到了第二检查点")
        self.assertIn("按评审改", self.client.prompts[1])
        self.assertIn("fig-a stale", self.client.prompts[2])


class TheTechnicalWaitRechecks(unittest.TestCase):
    """停等本身：读不出时按间隔重探，恢复了返回哨兵；宿主的回话与收工先于探针；读得出但没做完就停止重探。"""

    def wait(self, recheck, *, before=None, conclude_after: int = 0):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name)
        state: dict = {}
        events: list[str] = []
        feed = SimpleNamespace(emit=lambda name, **_: events.append(name))
        runlog = SimpleNamespace(event=lambda *_: None)
        if before:
            before(out)
        p = unittest.mock.patch.object
        slept: list[int] = []

        def sleep(_s):
            slept.append(1)
            if conclude_after and len(slept) == conclude_after:
                (out / rc.CONCLUDE_FILE).write_text(json.dumps({"reason": "够了"}), encoding="utf-8")
        with p(rc, "refresh_worker_lease", return_value=None), p(rc.time, "sleep", side_effect=sleep), \
                p(rc, "READING_RECHECK_SEC", 1), unittest.mock.patch("sys.stderr", new=io.StringIO()):
            got = rc.wait_for_human_reply(out, feed, runlog, state, turn=3, kind="local_reading", recheck=recheck)
        return got, state, events, out

    def test_a_recovered_probe_returns_without_a_human_answer(self) -> None:
        seq = iter([UNKNOWN, DONE])
        got, state, events, _ = self.wait(lambda: next(seq))
        self.assertIs(rc.READING_RECHECK_COMPLETE, got)
        self.assertEqual(("running", None), (state["status"], state["awaiting_kind"]))
        self.assertNotIn("human_reply", events)
        self.assertEqual(0, int(state.get("human_wait_events") or 0))

    def test_a_reply_that_arrives_during_the_probe_wins(self) -> None:
        def probe() -> dict:
            (out_dir[0] / rc.REPLY_FILE).write_text(json.dumps({"text": "先停一下"}), encoding="utf-8")
            return DONE
        out_dir: list[Path] = []
        got, state, _, _ = self.wait(probe, before=out_dir.append)
        self.assertEqual("先停一下", got, "探针期间到达的回话被吞掉了")
        self.assertEqual(1, state["human_wait_events"])

    def test_a_pending_probe_stops_rechecking_and_waits_for_the_host(self) -> None:
        calls: list[int] = []
        got, _, _, _ = self.wait(lambda: calls.append(1) or pending("no-report"), conclude_after=6)
        self.assertIsNone(got, "宿主收工没收到")
        self.assertEqual(1, len(calls), "读得出、没做完之后还在重探")


GOOD_PENDING = {"applicable": True, "complete": False, "items": [{"id": "f", "line": 3, "state": "blocked",
                "reason": "块坏了"}], "problems": ["孤立标记"], "next": "去修"}


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
        with p(rc, "reading_facts", return_value=reading), p(rc, "observe_target", return_value={"reached": True, "missing": [], "units": []}), \
                p(rc, "story_registered", return_value=True):
            return rc.closure_facts("AR1", "story", {"kind": "phase", "phase": "spec"}, None)["target_complete"]

    def test_each_variant_has_one_conclusion_down_the_chain(self) -> None:
        variants = {
            "明确不采用": (json.dumps({"applicable": False, "complete": True, "items": [], "problems": [],
                                  "next": None}), "not_applicable"),
            "全部就绪": (json.dumps({"applicable": True, "complete": True, "items": [{"id": "f", "line": 3, "state": "ready",
                                  "reason": ""}], "problems": [], "next": None}), "complete"),
            "有待办": (json.dumps(GOOD_PENDING), "pending"),
            "读取失败": ("{}", "unknown"),
            "缺 applicable": (json.dumps({"complete": False, "items": [], "problems": ["unresolved"]}), "unknown"),
            "applicable 是文字": (json.dumps({**GOOD_PENDING, "applicable": "yes"}), "unknown"),
            "说完成却有问题": (json.dumps({**GOOD_PENDING, "complete": True, "next": None}), "unknown"),
            "说不适用却有问题": (json.dumps({"applicable": False, "complete": True, "items": [],
                                     "problems": ["unresolved"], "next": None}), "unknown"),
            "没完成却没下一动作": (json.dumps({**GOOD_PENDING, "next": None}), "unknown"),
            "没完成却没有待办": (json.dumps({"applicable": True, "complete": False, "items": [],
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
        self.assertEqual(("块坏了", ["孤立标记"], "去修"),
                         (kept["items"][0]["reason"], kept["problems"], kept["next"]))

    def test_a_missing_story_is_not_applicable_only_before_the_story_is_due(self) -> None:
        self.assertEqual("not_applicable", self.facts("", story=False)["state"])
        got = self.facts("", story=False, required=True)
        self.assertEqual("unknown", got["state"])
        self.assertFalse(self.closure_complete(got))


if __name__ == "__main__":
    unittest.main()
