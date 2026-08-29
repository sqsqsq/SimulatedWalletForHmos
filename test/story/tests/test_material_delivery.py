"""材料按真实体验投放：起跑时收件箱是空的，补料等人开口要才到。

此前四个 Case 把全部材料（含收件箱里的 docx、含图片）在起跑前整棵铺进需求目录。
于是「模型会不会发现材料不够、会不会开口要」这件事从来没被测到——材料一直都够。

现在分三处：`system/` 是需求系统上挂着的单据（`story.js` 去拉），`workspace/` 是起跑
那一刻需求目录里就有的东西，`supplements/` 是人手上备着、**要来的**那几份。
这里判 KM-5：起跑时收件箱只有说明书；脚本条目声明的补料随那句回话一起到达；
`reply --deliver` 在宿主实时回话时同样能投。
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "test" / "story" / "scripts"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPTS))
import run_multi_case  # noqa: E402


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rc = _load("story_run_case_delivery", "run_case.py")

CASE_ID = "delivery-fixture"
FEATURE = "AR70011"
DOC_NAME = "产品同事给的说明.md"


class FixtureCase(unittest.TestCase):
    """造一个只有本测试看得到的 Case：三处材料各放一份。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.cases = self.root / "cases"
        self.case = self.cases / CASE_ID
        (self.case / "workspace" / "SR").mkdir(parents=True)
        (self.case / "workspace" / "SR" / "design.md").write_text(
            "# 系统设计说明\n", encoding="utf-8")
        (self.case / "system" / "AR70011").mkdir(parents=True)
        (self.case / "system" / "AR70011" / "detail.json").write_text(
            json.dumps({"reqNo": FEATURE, "type": "AR"}), encoding="utf-8")
        (self.case / "system" / "AR70011" / "design.md").write_text(
            "# 系统预填\n", encoding="utf-8")
        (self.case / "supplements").mkdir()
        (self.case / "supplements" / DOC_NAME).write_text("# 产品文档\n", encoding="utf-8")
        self.write_case_yaml("on_request")

    def write_case_yaml(self, deliver: str) -> None:
        (self.case / "case.yaml").write_text(
            f"id: {CASE_ID}\nar: {FEATURE}\nstart_phase: story\nend_phase: spec\n"
            f"prompt: |\n  做这张单。\n"
            f"supplements:\n  - file: {DOC_NAME}\n    deliver: {deliver}\n",
            encoding="utf-8")

    def write_script(self, deliver: list[str]) -> None:
        lines = ["replies:", "  - id: ask-for-doc", "    expected_turn: 1",
                 "    text: 我把产品同事给的文档放进需求目录了。"]
        if deliver:
            lines.append("    deliver:")
            lines.extend(f"      - {name}" for name in deliver)
        (self.case / "interaction-script.yaml").write_text(
            "\n".join(lines) + "\n", encoding="utf-8")


class TestDeclaration(FixtureCase):
    def test_supplements_are_declared_with_a_delivery_moment(self) -> None:
        with mock.patch.object(run_multi_case, "CASES_ROOT", self.cases):
            items = run_multi_case.load_supplements(CASE_ID)
        self.assertEqual(1, len(items))
        self.assertEqual(DOC_NAME, items[0]["file"])
        self.assertEqual("on_request", items[0]["deliver"])

    def test_unknown_delivery_moment_is_refused(self) -> None:
        self.write_case_yaml("someday")
        with mock.patch.object(run_multi_case, "CASES_ROOT", self.cases):
            with self.assertRaises(SystemExit) as caught:
                run_multi_case.load_supplements(CASE_ID)
        self.assertIn("deliver 非法", str(caught.exception))

    def test_declared_but_missing_file_is_refused(self) -> None:
        (self.case / "supplements" / DOC_NAME).unlink()
        with mock.patch.object(run_multi_case, "CASES_ROOT", self.cases):
            with self.assertRaises(SystemExit) as caught:
                run_multi_case.load_supplements(CASE_ID)
        self.assertIn("补料不存在", str(caught.exception))

    def test_script_can_only_deliver_declared_supplements(self) -> None:
        """脚本要投的东西必须在 case.yaml 里备过案。

        写错文件名时当场拒绝，比实跑到那一关才发现「说了放进去、其实没有」强得多
        ——后者要等模型自己找不到文件、开始猜，观测就被污染了。
        """
        self.write_script(["别的文件.docx"])
        with mock.patch.object(run_multi_case, "CASES_ROOT", self.cases):
            with self.assertRaises(SystemExit) as caught:
                run_multi_case.load_interaction_script(CASE_ID)
        self.assertIn("未在 case.yaml 声明", str(caught.exception))

    def test_script_carries_the_declared_delivery(self) -> None:
        self.write_script([DOC_NAME])
        with mock.patch.object(run_multi_case, "CASES_ROOT", self.cases):
            script = run_multi_case.load_interaction_script(CASE_ID)
        self.assertEqual([DOC_NAME], script[0]["deliver"])


class TestPhysicalDelivery(FixtureCase):
    """真的把文件搬进收件箱——回执说投了，目录里就必须有。"""

    def setUp(self) -> None:
        super().setUp()
        self.workspace = self.root / "workspace"
        self.feature_root = self.workspace / "doc" / "features" / FEATURE
        self.inbox = self.feature_root / "inbox"
        self.inbox.mkdir(parents=True)
        (self.inbox / "README.md").write_text("# 收件箱\n", encoding="utf-8")
        self._patch = mock.patch.multiple(
            rc, HERE=self.cases.parent / "scripts", REPO_ROOT=self.workspace,
            FEATURES_DIR="doc/features")
        self._patch.start()
        self.addCleanup(self._patch.stop)
        (self.cases.parent / "scripts").mkdir(exist_ok=True)

    def test_inbox_holds_only_the_readme_before_anyone_asks(self) -> None:
        seeded = rc.seed_case_workspace(CASE_ID, FEATURE)
        self.assertEqual(["README.md"], sorted(p.name for p in self.inbox.iterdir()))
        self.assertIn("SR/design.md", seeded)

    def test_start_delivery_lands_with_the_workspace_material(self) -> None:
        """人手上本来就有、起跑前已经放好的那一类，与工作区材料同时到位。"""
        self.write_case_yaml("start")
        seeded = rc.seed_case_workspace(CASE_ID, FEATURE)
        self.assertIn(f"inbox/{DOC_NAME}", seeded)
        self.assertTrue((self.inbox / DOC_NAME).is_file())

    def test_requested_delivery_lands_in_the_inbox(self) -> None:
        delivered = rc.deliver_supplements(CASE_ID, FEATURE, [DOC_NAME])
        self.assertEqual([DOC_NAME], delivered)
        self.assertEqual("# 产品文档\n", (self.inbox / DOC_NAME).read_text("utf-8"))

    def test_delivery_of_an_undeclared_path_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            rc.deliver_supplements(CASE_ID, FEATURE, ["../case.yaml"])


class TestCoordinatorWiring(FixtureCase):
    """协调器那一侧：快照进 workspace、环境变量指过去、回话带上补料。"""

    def test_requirement_system_snapshot_is_copied_per_case(self) -> None:
        workspace = self.root / "ws"
        workspace.mkdir()
        with mock.patch.object(run_multi_case, "CASES_ROOT", self.cases), \
                mock.patch.object(run_multi_case, "REPO_ROOT", self.root):
            seeded = run_multi_case.seed_requirement_system(CASE_ID, workspace)
        self.assertEqual(2, len(seeded))
        self.assertTrue((workspace / run_multi_case.REQUIREMENT_SYSTEM_DIR
                         / FEATURE / "detail.json").is_file())

    def test_environment_points_at_the_case_own_system(self) -> None:
        workspace = self.root / "ws2"
        (workspace / run_multi_case.REQUIREMENT_SYSTEM_DIR).mkdir(parents=True)
        suite = {"bundle_root": str(self.root), "case_states": {
            CASE_ID: {"case": CASE_ID, "workspace": str(workspace)}}}
        environment = run_multi_case.suite_environment(suite, CASE_ID)
        self.assertEqual(
            str((workspace / run_multi_case.REQUIREMENT_SYSTEM_DIR).resolve()),
            environment[run_multi_case.REQUIREMENT_SYSTEM_ENV])

    def test_case_without_a_snapshot_gets_no_system_pointer(self) -> None:
        """没有快照就别指过去：让替身自己报「系统不可达」，比指向空目录报「查无此单」诚实。"""
        workspace = self.root / "ws3"
        workspace.mkdir()
        suite = {"bundle_root": str(self.root), "case_states": {
            CASE_ID: {"case": CASE_ID, "workspace": str(workspace)}}}
        environment = run_multi_case.suite_environment(suite, CASE_ID)
        self.assertNotIn(run_multi_case.REQUIREMENT_SYSTEM_ENV, environment)

    def test_scripted_reply_delivers_before_it_speaks(self) -> None:
        record = {
            "case": CASE_ID, "feature": FEATURE, "status": run_multi_case.WAITING_STATUS,
            "interaction_script": [{"id": "ask", "text": "文档放进去了。",
                                    "expected_turn": 1, "expected_kind": "story_gate",
                                    "expected_phase": "", "deliver": [DOC_NAME]}],
            "interaction_index": 0,
            "last_awaiting": {"turn": 1, "kind": "story_gate"},
            "supplements": [{"file": DOC_NAME, "deliver": "on_request"}],
            "supplements_pending": [DOC_NAME],
        }
        suite = {"case_states": {CASE_ID: record}, "events": [],
                 "bundle_root": str(self.root)}
        calls: list[tuple] = []

        def fake_invoke(case_id, command, *args, suite=None):
            calls.append((case_id, command, args))
            return 0, {"reply_status": "accepted", "delivered": [DOC_NAME]}, "", ""

        with mock.patch.object(run_multi_case, "invoke_case", fake_invoke), \
                mock.patch.object(run_multi_case, "append_case_observation",
                                  lambda *a, **k: None):
            run_multi_case.send_scripted_reply(record, suite)
        self.assertEqual(1, len(calls))
        self.assertIn("--deliver", calls[0][2])
        self.assertIn(DOC_NAME, calls[0][2])
        self.assertEqual([], record["supplements_pending"])
        self.assertEqual([DOC_NAME], record["supplements_delivered"])

    def test_public_inputs_list_what_the_host_has(self) -> None:
        record = {"case": CASE_ID, "feature": FEATURE,
                  "supplements": [{"file": DOC_NAME, "deliver": "on_request"}],
                  "supplements_delivered": []}
        with mock.patch.object(run_multi_case, "CASES_ROOT", self.cases):
            inputs = run_multi_case.case_public_inputs(record)
        self.assertTrue(any("需求系统" in item for item in inputs), inputs)
        self.assertTrue(any(DOC_NAME in item and "未投" in item for item in inputs), inputs)

    def test_finalize_keeps_the_system_state_as_evidence(self) -> None:
        """跑完之后系统上是什么样，只有系统侧的状态答得了。"""
        workspace = self.root / "ws4"
        system = workspace / run_multi_case.REQUIREMENT_SYSTEM_DIR / FEATURE
        system.mkdir(parents=True)
        (system / "design.md").write_text("# 归档上去的叙事件\n", encoding="utf-8")
        (system / "history").mkdir()
        (system / "history" / "design-20260829120000.md").write_text("# 旧版\n", encoding="utf-8")
        bundle = self.root / "bundle"
        (bundle / "cases" / CASE_ID).mkdir(parents=True)
        record = {"case": CASE_ID, "workspace": str(workspace)}
        result = run_multi_case.capture_requirement_system(
            {"bundle_root": str(bundle)}, record)
        self.assertEqual("captured", result["status"])
        self.assertIn(f"{FEATURE}/design.md", result["files"])
        self.assertIn(f"{FEATURE}/history/design-20260829120000.md", result["files"])
        self.assertEqual(
            "# 归档上去的叙事件\n",
            (bundle / "cases" / CASE_ID / "system-after" / FEATURE / "design.md")
            .read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
