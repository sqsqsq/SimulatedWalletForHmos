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
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path, PurePosixPath
from unittest import mock
from urllib.parse import unquote
from ext_workspace import DEV_EXT
from flow_steps import ensure_framework

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "test" / "scripts"
sys.path.insert(0, str(REPO_ROOT))
STORY_SCRIPTS = DEV_EXT / "skills" / "story" / "scripts" / "core"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(STORY_SCRIPTS))
from materials import registry  # noqa: E402
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
            f"id: {CASE_ID}\nar: {FEATURE}\nstart_phase: story\nend_at: {{kind: story}}\n"
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
    """协调器那一侧：快照落在 workspace 之外、环境变量指过去、回话带上补料。"""

    def test_requirement_system_snapshot_is_copied_per_case(self) -> None:
        workspace_root = self.root / "wsroot"
        workspace_root.mkdir()
        with mock.patch.object(run_multi_case, "CASES_ROOT", self.cases):
            seeded = run_multi_case.seed_requirement_system(CASE_ID, workspace_root)
        self.assertEqual(2, len(seeded))
        system = run_multi_case.requirement_system_path(workspace_root, CASE_ID)
        self.assertTrue((system / FEATURE / "detail.json").is_file())

    def test_snapshot_never_lands_inside_a_case_workspace(self) -> None:
        """需求系统在远端，被测侧的目录树里不该有它。

        放进 workspace 根下，模型一个 `ls` 就看见了——实测它确实去看了。
        那一轮它仍规矩走了对接层，但这条路存在，下一轮就可能被绕过去，
        「系统按单号拉取」这条链就测不到了。
        """
        workspace_root = self.root / "wsroot2"
        workspace = workspace_root / CASE_ID
        workspace.mkdir(parents=True)
        with mock.patch.object(run_multi_case, "CASES_ROOT", self.cases):
            run_multi_case.seed_requirement_system(CASE_ID, workspace_root)
        system = run_multi_case.requirement_system_path(workspace_root, CASE_ID)
        self.assertFalse(system.is_relative_to(workspace))
        self.assertEqual([], [item.name for item in workspace.rglob("*")])

    def test_boundary_check_rejects_a_snapshot_put_back_inside(self) -> None:
        """哪天有人又把它挪回 workspace 里，起跑就得停——这条判据防的就是漂移。"""
        workspace = self.root / "wsroot3" / CASE_ID
        (workspace / run_multi_case.LEGACY_REQUIREMENT_SYSTEM_DIR).mkdir(parents=True)
        with self.assertRaises(RuntimeError) as caught:
            run_multi_case._verify_workspace_boundary(workspace, FEATURE)
        self.assertIn(run_multi_case.LEGACY_REQUIREMENT_SYSTEM_DIR, str(caught.exception))

    def test_environment_points_at_the_case_own_system(self) -> None:
        workspace_root = self.root / "wsroot4"
        workspace = workspace_root / CASE_ID
        workspace.mkdir(parents=True)
        system = run_multi_case.requirement_system_path(workspace_root, CASE_ID)
        system.mkdir(parents=True)
        suite = {"bundle_root": str(self.root), "workspace_root": str(workspace_root),
                 "case_states": {CASE_ID: {"case": CASE_ID, "workspace": str(workspace)}}}
        environment = run_multi_case.suite_environment(suite, CASE_ID)
        self.assertEqual(str(system), environment[run_multi_case.REQUIREMENT_SYSTEM_ENV])

    def test_case_without_a_snapshot_points_nowhere_not_at_the_default(self) -> None:
        """没有快照的 Case 要指向一个**不存在**的路径，而不是把变量空着。

        让替身自己报「系统不可达」，比指向空目录报「查无此单」诚实——这条没变。
        变的是实现：空着变量时 `story.js` 会落到它的默认目录，而人手跑用的那套单据
        （`bootstrap_local_story.py` 放在维护域 `test/requirement-system`）不能被任何 Case 读到。装置读到它就不是在测本 Case 的输入了，
        而且一声不吭。所以显式指向一个不存在的路径。
        """
        workspace_root = self.root / "wsroot5"
        workspace = workspace_root / CASE_ID
        workspace.mkdir(parents=True)
        suite = {"bundle_root": str(self.root), "workspace_root": str(workspace_root),
                 "case_states": {CASE_ID: {"case": CASE_ID, "workspace": str(workspace)}}}
        environment = run_multi_case.suite_environment(suite, CASE_ID)
        pointer = environment[run_multi_case.REQUIREMENT_SYSTEM_ENV]
        self.assertFalse(Path(pointer).is_dir(), "指过去的目录不该存在")
        self.assertNotEqual(
            str((REPO_ROOT / "test" / "requirement-system").resolve()),
            str(Path(pointer)),
            "绝不能落到 story.js 的默认目录——那里是人手跑用的单据")

    def test_the_local_requirement_system_is_never_copied_into_a_workspace(self) -> None:
        """人装的那套需求系统不能进被测 workspace——进去了模型 `ls` 就看见了。

        它在维护域 `test/` 下，工作区从 demo 复制。这条守的是「demo 顶层出现 `test` 就报结构漂移」
        ——哪天有人把它拿掉，本地需求系统会跟着混进 demo、再进工作区。
        """
        self.assertIn("test", run_multi_case.MAINTENANCE_TOP_LEVEL,
                      "demo 顶层出现 test 不再报结构漂移——本地需求系统会跟着进 workspace")
        self.assertIn("doc/features", run_multi_case.WORKSPACE_EXCLUDED_DIRS,
                      "真实需求目录会跟着进被测侧")

    def test_the_default_dir_never_leaks_into_any_case(self) -> None:
        """机械回归：人装了本地需求系统之后，装置给任何 Case 的指针都不指向它。"""
        default_dir = (REPO_ROOT / "test" / "requirement-system").resolve()
        workspace_root = self.root / "wsroot6"
        for case_id in (CASE_ID, "another-fixture"):
            (workspace_root / case_id).mkdir(parents=True)
        suite = {"bundle_root": str(self.root), "workspace_root": str(workspace_root),
                 "case_states": {cid: {"case": cid,
                                       "workspace": str(workspace_root / cid)}
                                 for cid in (CASE_ID, "another-fixture")}}
        for case_id in suite["case_states"]:
            environment = run_multi_case.suite_environment(suite, case_id)
            pointer = Path(environment[run_multi_case.REQUIREMENT_SYSTEM_ENV])
            self.assertNotEqual(default_dir, pointer.resolve()
                                if pointer.is_absolute() else pointer)


    def test_the_plan_tells_the_host_which_material_to_hand_over(self) -> None:
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

        # 规划不再自己发话：它把「这一关该交出哪份材料」告诉宿主，宿主回话时带上
        # `--deliver`。人说「我把文档放进去了」的同时文件就该在那儿，这一点没变，
        # 变的是说这句话的人——脚本换成宿主。
        with mock.patch.object(run_multi_case, "invoke_case", fake_invoke), \
                mock.patch.object(run_multi_case, "append_case_observation",
                                  lambda *a, **k: None):
            run_multi_case.request_host_reply(record, suite)
        self.assertEqual(0, len(calls), "规划不该自己去发话")
        request = record["last_adaptive_request"]
        self.assertEqual([DOC_NAME], request["planned_deliver"])
        self.assertEqual("ask", request["planned_step_id"])
        self.assertEqual("文档放进去了。", request["planned_intent"])
        # 材料还在人手上：宿主带着 `--deliver` 说那句话时才落进收件箱。
        # 规划自己把它投出去，就等于「文件到了、但没人说过给你」。
        self.assertEqual([DOC_NAME], record["supplements_pending"])
        self.assertEqual([], record.get("supplements_delivered") or [])

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
        workspace_root = self.root / "wsroot6"
        workspace = workspace_root / CASE_ID
        workspace.mkdir(parents=True)
        system = run_multi_case.requirement_system_path(workspace_root, CASE_ID) / FEATURE
        system.mkdir(parents=True)
        (system / "design.md").write_text("# 归档上去的叙事件\n", encoding="utf-8")
        (system / "history").mkdir()
        (system / "history" / "design-20260829120000.md").write_text(
            "# 旧版\n", encoding="utf-8")
        bundle = self.root / "bundle"
        (bundle / "cases" / CASE_ID).mkdir(parents=True)
        record = {"case": CASE_ID, "workspace": str(workspace)}
        result = run_multi_case.capture_requirement_system(
            {"bundle_root": str(bundle), "workspace_root": str(workspace_root)}, record)
        self.assertEqual("captured", result["status"])
        self.assertIn(f"{FEATURE}/design.md", result["files"])
        self.assertIn(f"{FEATURE}/history/design-20260829120000.md", result["files"])
        self.assertEqual(
            "# 归档上去的叙事件\n",
            (bundle / "cases" / CASE_ID / "system-after" / FEATURE / "design.md")
            .read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()


class SupplementForImagesOnlyLeavesTheTextAlone(unittest.TestCase):
    """补料是为了补图时，正文不采用。

    「原稿放进去了，图在里面」——人要的是图。原稿归 IMAGES 时导入只取图，它的正文不作阅读稿，
    已有的定稿仍是这类来源唯一的正文。
    """

    TEXT = "# 定稿\n\n这是系统上的正文，补图不该动它。\n"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.feature_root = self.root / "doc" / "features" / "IM90002"
        self.inbox = self.feature_root / "inbox"
        self.inbox.mkdir(parents=True)
        (self.inbox / "prd.md").write_text(self.TEXT, encoding="utf-8")
        (self.inbox / ".classify.json").write_text('{"prd.md": "RR"}', encoding="utf-8")
        self.assertEqual(0, self.run_import().returncode)

    def write_docx(self, name: str = "原稿.docx") -> Path:
        """最小 docx：一段正文 + 一张内嵌图。"""
        path = self.inbox / name
        document = (
            '<?xml version="1.0"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
            ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<w:body><w:p><w:r><w:t>草稿正文，比定稿旧</w:t></w:r></w:p>'
            '<w:p><w:r><w:drawing><a:blip xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
            ' r:embed="rId1"/></w:drawing></w:r></w:p></w:body></w:document>'
        )
        rels = (
            '<?xml version="1.0"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/image" Target="media/image1.png"/></Relationships>'
        )
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("word/document.xml", document)
            zf.writestr("word/_rels/document.xml.rels", rels)
            zf.writestr("word/media/image1.png", b"\x89PNG\r\n\x1a\nfigure")
        return path

    def classify(self, cls: str) -> None:
        (self.inbox / ".classify.json").write_text(
            json.dumps({"原稿.docx": cls}, ensure_ascii=False), encoding="utf-8")

    def run_import(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(DEV_EXT / "skills/story/scripts/core/import_sources.py"),
             "--feature", "IM90002", "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)

    def manifest(self) -> dict:
        return json.loads((self.feature_root / "AR" / "story-src" / "materials.json").read_text(encoding="utf-8"))

    def readable_docs(self) -> list[str]:
        return sorted(p for m in self.manifest()["materials"] if m["kind"] == "doc" for p in m["paths"])

    def test_the_text_is_not_adopted_and_the_figure_lands(self) -> None:
        self.write_docx()
        self.classify("IMAGES")
        proc = self.run_import()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertFalse([d for d in self.readable_docs() if "原稿" in d and d.endswith(".md")], "补图那一档把原稿正文也当成了阅读稿")
        self.assertFalse(list((self.feature_root / ".backups" / "local").glob("*/原稿-v1.md")))
        self.assertNotIn("草稿正文", (self.feature_root / "RR" / "prd.md").read_text(encoding="utf-8"), "补图那一档的正文并进了当前阅读稿")
        self.assertTrue(list(self.feature_root.glob("assets/原稿.*/*.png")),
                        "图没抽出来——这一档抽图是它唯一要做的事")

    def test_a_text_class_takes_the_text(self) -> None:
        """反样本：归 RR 就是要采用正文——这一档不是把正文转换废掉。"""
        self.write_docx()
        self.classify("RR")
        self.assertEqual(0, self.run_import().returncode)
        self.assertIn(".backups/local/RR/原稿-v1.md", self.readable_docs())
        self.assertIn("草稿正文", (self.feature_root / ".backups/local/RR/原稿-v1.md").read_text(encoding="utf-8"))
        self.assertIn("草稿正文", (self.feature_root / "RR" / "prd.md").read_text(encoding="utf-8"))

    def test_a_docx_without_figures_is_refused_in_that_class(self) -> None:
        """没有图却归了只抽图——那是归类错了，不能静默丢掉正文。"""
        path = self.inbox / "原稿.docx"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("word/document.xml",
                        '<?xml version="1.0"?><w:document xmlns:w="http://schemas.'
                        'openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                        '<w:p><w:r><w:t>只有字</w:t></w:r></w:p></w:body></w:document>')
        self.classify("IMAGES")
        proc = self.run_import()
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("没有图", proc.stdout + proc.stderr)

    def test_the_material_version_still_moves(self) -> None:
        """正文没动，但材料确实变了——图是材料，轮次要看得见它。"""
        self.write_docx()
        self.classify("IMAGES")
        before = self.manifest()["digest"]
        self.assertEqual(0, self.run_import().returncode)
        after = self.manifest()["digest"]
        self.assertNotEqual(before, after, "只抽图没有形成新材料版本")


class MarkdownKeepsItsPictures(unittest.TestCase):
    """Markdown 原件按它在收件箱里的位置引用图与别的文档：原件字节不动，阅读稿的链接改指导入后对方给人读的那一份。

    目标按 `markdownLinks` 的完整读法：尖括号包起来的可含空格与括号，不包的括号成对。A 链到 B、B 链到图，
    沿着 A 的阅读稿读下去，B 的阅读稿与它的图都在；设计采用 A 时，B 的版本与图一起进入采用集合。
    """

    TEXT = ("# 说明\n\n![流程](<images/流程 (修订).png>)\n\n![旧版](images/flow(v2).png)\n\n"
            "[外部](https://example.com/a.png) [本节](#说明)\n\n见 [附录](附录.md#口径)\n")
    APPENDIX = "# 附录\n\n## 口径\n\n![口径图](images/口径.png)\n"
    PICTURES = ("流程 (修订).png", "flow(v2).png", "口径.png")

    ADOPTED = """
    const [access, root, feature, ref] = process.argv.slice(1);
    const { adoptedSources } = await import(access);
    const blueprint = { blueprint_id: feature, discovery: { inputs: { current_scope_items: [] },
      facts: [{ fact_id: 'fact-intro', provenance: { source_kind: 'requirement_material', source_ref: ref, evidence_strength: 'observed' } }] } };
    const out = adoptedSources(root, blueprint, { requirement: feature });
    process.stdout.write(JSON.stringify({ problems: out.problems, files: out.requirements[0].files.map(f => f.path) }));
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.feature_root = self.root / "doc" / "features" / "MD90001"
        self.inbox = self.feature_root / "inbox"
        (self.inbox / "docs" / "images").mkdir(parents=True)

    def put(self, files: dict[str, bytes | str], classify: dict[str, str]) -> None:
        for rel, body in files.items():
            (self.inbox / rel).parent.mkdir(parents=True, exist_ok=True)
            data = body.encode("utf-8") if isinstance(body, str) else body
            (self.inbox / rel).write_bytes(data)
        (self.inbox / ".classify.json").write_text(json.dumps(classify, ensure_ascii=False), encoding="utf-8")

    def run_import(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(DEV_EXT / "skills/story/scripts/core/import_sources.py"),
             "--feature", "MD90001", "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)

    def manifest(self) -> dict:
        return json.loads((self.feature_root / "AR" / "story-src" / "materials.json").read_text(encoding="utf-8"))

    def first_import(self) -> None:
        files = {"docs/说明.md": self.TEXT, "docs/附录.md": self.APPENDIX,
                 **{f"docs/images/{n}": b"\x89PNG\r\n\x1a\n" + n.encode("utf-8") for n in self.PICTURES}}
        self.put(files, {rel: ("UX" if "/images/" in rel else "RR") for rel in files})
        proc = self.run_import()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def follow(self, reading: Path) -> dict[str, Path]:
        """阅读稿里每个本地链接按链接写法解析到的文件（用产品的同一读法）。"""
        from materials import importer  # noqa: PLC0415
        out = {}
        for line in reading.read_text(encoding="utf-8").splitlines():
            for _, _, target in importer.markdown_links(line):
                if re.match(r"^[a-z]+:", target) or target.startswith("#"):
                    continue
                out[target] = (reading.parent / unquote(re.split(r"[?#]", target)[0])).resolve()
        return out

    @staticmethod
    def shown(name: str) -> str:
        """导入后按内容起名的图（`<主名>.<16 位摘要><后缀>`）还原成原件名。"""
        return re.sub(r"\.[0-9a-f]{16}(\.[^.]+)$", r"\1", name)

    def reading_of(self, source_id: str) -> Path:
        version = next(s for s in self.manifest()["sources"] if s["source_id"] == source_id)["versions"][-1]
        return self.feature_root / version["readable"]["path"]

    def test_the_reading_chain_reaches_every_picture(self) -> None:
        self.first_import()
        intro = self.reading_of("local:docs/说明.md")
        self.assertEqual(self.TEXT.encode("utf-8"), (self.inbox / "docs" / "说明.md").read_bytes(), "原件字节被改了")
        links = self.follow(intro)
        self.assertEqual(3, len(links), f"本地链接没认全：{list(links)}")
        for target, file in links.items():
            self.assertTrue(file.is_file(), f"说明的阅读稿链接 {target} 指向不存在的文件")
        text = intro.read_text(encoding="utf-8")
        self.assertIn("https://example.com/a.png", text, "外部链接被改写")
        self.assertIn("](#说明)", text, "文内锚点被改写")
        appendix = next(f for t, f in links.items() if "附录" in unquote(t))
        self.assertEqual(self.reading_of("local:docs/附录.md").resolve(), appendix, "说明链到的不是附录给人读的那一份")
        [(target, picture)] = self.follow(appendix).items()
        self.assertTrue(picture.is_file(), f"附录阅读稿的图 {target} 断了")
        pictures = {self.shown(p.name) for p in links.values() if p.suffix == ".png"} | {self.shown(picture.name)}
        self.assertEqual(set(self.PICTURES), pictures)

    def test_the_design_reads_the_linked_version_and_its_pictures(self) -> None:
        """设计只在事实里引用说明的阅读稿：附录的版本与三张图都进采用集合。"""
        self.first_import()
        ensure_framework(self.root)
        access = (DEV_EXT / "hooks" / "shared" / "framework-access.mjs").resolve().as_uri()
        ref = f"doc/features/MD90001/{self.reading_of('local:docs/说明.md').relative_to(self.feature_root).as_posix()}"
        proc = subprocess.run(["node", "--input-type=module", "-e", self.ADOPTED, access, str(self.root), "MD90001", ref],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        got = json.loads(proc.stdout)
        self.assertEqual([], got["problems"])
        names = {self.shown(PurePosixPath(p).name) for p in got["files"]}
        self.assertTrue(set(self.PICTURES) <= names, f"采用集合缺图：{sorted(names)}")
        self.assertIn(self.reading_of("local:docs/附录.md").name, names)
        self.assertIn("附录.md", names)

    def test_a_new_picture_reaches_the_top_of_the_reading_chain(self) -> None:
        """同一包再交一次，只有附录的图换了：这一次的说明沿阅读链读到的是这一次的附录与新图；
        上一次的版本原样留着，仍读到旧图；没换的两张图复用。"""
        self.first_import()
        old_intro = self.reading_of("local:docs/说明.md")
        new_picture = b"\x89PNG\r\n\x1a\n" + "口径 第二版".encode("utf-8")
        files = {"docs/说明.md": self.TEXT, "docs/附录.md": self.APPENDIX,
                 **{f"docs/images/{n}": b"\x89PNG\r\n\x1a\n" + n.encode("utf-8") for n in self.PICTURES},
                 "docs/images/口径.png": new_picture}
        self.put(files, {rel: ("UX" if "/images/" in rel else "RR") for rel in files})
        proc = self.run_import()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(3, len(out["versions"]), f"该出新版本的没出全：{out['versions']}")
        self.assertEqual({"docs/images/流程 (修订).png", "docs/images/flow(v2).png"}, {r["file"] for r in out["reused"]})

        intro = self.reading_of("local:docs/说明.md")
        self.assertNotEqual(old_intro, intro, "说明还停在上一次的版本")
        appendix = next(f for target, f in self.follow(intro).items() if "附录" in unquote(target))
        self.assertEqual(self.reading_of("local:docs/附录.md").resolve(), appendix, "说明链到的不是这一次的附录")
        [(_, picture)] = self.follow(appendix).items()
        self.assertEqual(new_picture, picture.read_bytes(), "沿阅读链读到的不是这一次的图")

        old_appendix = next(f for target, f in self.follow(old_intro).items() if "附录" in unquote(target))
        [(_, old_picture)] = self.follow(old_appendix).items()
        self.assertEqual(b"\x89PNG\r\n\x1a\n" + "口径.png".encode("utf-8"), old_picture.read_bytes(), "上一次的版本被改写了")

    def test_the_whole_package_again_reuses_every_version(self) -> None:
        self.first_import()
        files = {"docs/说明.md": self.TEXT, "docs/附录.md": self.APPENDIX,
                 **{f"docs/images/{n}": b"\x89PNG\r\n\x1a\n" + n.encode("utf-8") for n in self.PICTURES}}
        self.put(files, {rel: ("UX" if "/images/" in rel else "RR") for rel in files})
        proc = self.run_import()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual([], json.loads(proc.stdout)["versions"], "原样重交的整包开了新版本")

    def test_a_document_linking_to_its_own_section_is_reused(self) -> None:
        """说明链到自己的一节：原样再交一次，阅读稿按它所在的旧版本目录渲染，内容不变，复用，不多出一版。"""
        text = self.TEXT + "\n回到[本节](说明.md#说明)\n"
        files = {"docs/说明.md": text, "docs/附录.md": self.APPENDIX,
                 **{f"docs/images/{n}": b"\x89PNG\r\n\x1a\n" + n.encode("utf-8") for n in self.PICTURES}}
        classify = {rel: ("UX" if "/images/" in rel else "RR") for rel in files}
        self.put(files, classify)
        self.assertEqual(0, self.run_import().returncode)
        self.put(files, classify)
        proc = self.run_import()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual([], json.loads(proc.stdout)["versions"], "原样重交的自链文档多出了一版")

    def test_the_same_input_again_reuses_the_version(self) -> None:
        self.first_import()
        self.put({"docs/说明.md": self.TEXT}, {"docs/说明.md": "RR"})
        proc = self.run_import()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual([], json.loads(proc.stdout)["versions"], "同一份输入又开了新版本")

    def test_a_missing_local_picture_refuses_the_batch(self) -> None:
        self.put({"docs/新.md": "![缺](<images/缺 (1).png>)\n"}, {"docs/新.md": "RR"})
        proc = self.run_import()
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("images/缺 (1).png", json.loads(proc.stdout)["error"])
        self.assertTrue((self.inbox / "docs" / "新.md").is_file(), "整批没导却把原件移出了收件箱")
        self.assertFalse(list((self.feature_root / ".backups").rglob("新*")), "缺图还落了版本")


class AnOldIndexIsNotTakenOver(unittest.TestCase):
    """旧版生成的需求目录：导入在写任何版本之前就拒绝，提示另建新需求，索引与收件箱原样不动。"""

    def test_import_refuses_and_leaves_the_directory_alone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feature_root = root / "doc" / "features" / "OLD90001"
            inbox = feature_root / "inbox"
            inbox.mkdir(parents=True)
            (inbox / "prd.md").write_text("# 产品需求\n", encoding="utf-8")
            (inbox / ".classify.json").write_text('{"prd.md": "RR"}', encoding="utf-8")
            index = feature_root / "AR" / "story-src" / "materials.json"
            index.parent.mkdir(parents=True)
            index.write_text(json.dumps({"schema": 2, "materials": [], "notes": {}}), encoding="utf-8")
            before = {p.relative_to(feature_root).as_posix(): p.read_bytes() for p in feature_root.rglob("*") if p.is_file()}
            proc = subprocess.run(
                [sys.executable, str(DEV_EXT / "skills/story/scripts/core/import_sources.py"),
                 "--feature", "OLD90001", "--project-root", str(root)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
            self.assertNotEqual(0, proc.returncode)
            self.assertIn("另建一个新需求", json.loads(proc.stdout)["error"])
            after = {p.relative_to(feature_root).as_posix(): p.read_bytes() for p in feature_root.rglob("*") if p.is_file()}
            self.assertEqual(before, after, "旧目录被改写了")
