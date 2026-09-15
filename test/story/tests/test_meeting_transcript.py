"""会议转写：解析、按版本落盘、读会产物自检、关卡裁决与有效结果。

锁 1.9.2 步骤 3 的离线验收（05 §10）。构造件只用于脚本自检——证明解析、留痕、结构与派生按合同工作，
不证明模型读会的判断力；那归独立审查与真实会议 docx 的统一实跑。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

REPO_ROOT = Path(__file__).resolve().parents[3]
CORE = REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts" / "core"
sys.path.insert(0, str(CORE))
from flow import meetings  # noqa: E402
from materials import meeting, registry  # noqa: E402

FEATURE = "MT90001"

MEETING = [("Heading1", "需求澄清会"), (None, "会议时间：2026-09-01 10:00"), (None, "参会人：张三、李四"),
           ("Heading2", "议题一 受理上限"), (None, "张三 10:02：上限先按五个来"), (None, "补一句，超出的排队"),
           (None, "李四 10:05：同意，按五个"),
           ("Heading2", "议题二 通知方式"), (None, "李四 10:20：通知方式下次再定")]

LIMIT = {"id": "C1", "kind": "modify", "doc": "SR/design.md", "section": "§3.2", "before": "上限未定",
         "after": "上限五个，超出排队", "impact": "受理校验", "evidence": ["S1", "S2"]}
NOTICE = {"kind": "add", "doc": "SR/design.md", "section": "§4", "before": "未写通知",
          "after": "受理后短信通知", "impact": "通知章", "resolves": "O1"}
TOPICS = [
    {"id": "T1", "ownership": "ours", "changes": [LIMIT], "open_points": [], "ask": False,
     "conclusion": {"text": "上限五个", "scope": "受理", "evidence": ["S2"]}},
    {"id": "T2", "ownership": "ours", "changes": [], "ask": True, "ask_reason": "unresolved", "recommend": "opt_a",
     "open_points": [{"id": "O1", "what": "通知方式未定", "impact": "通知章", "needs": "产品定"}],
     "options": [
         {"key": "opt_a", "label": "按短信通知",
          "effect": {"ownership": "ours", "apply_changes": [], "add_changes": [NOTICE], "supersedes": []}},
         {"key": "opt_b", "label": "维持待定",
          "effect": {"ownership": "ours", "apply_changes": [], "add_changes": [], "supersedes": [],
                     "keep_open": ["O1"]}}]},
]


def write_docx(path: Path, paragraphs: list[tuple[str | None, str]]) -> None:
    body = "".join(
        "<w:p>" + (f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else "")
        + f'<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>' for style, text in paragraphs)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml",
                    '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
                    f'wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>')


class MeetingCase(unittest.TestCase):
    """每个用例一份新工作区，跑真脚本。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.fr = self.root / "doc" / "features" / FEATURE
        for rel, text in (("RR/prd.md", "# 产品需求\n\n背景。\n"), ("SR/design.md", "# 系统设计\n\n分工。\n"),
                          ("AR/design.md", "# 提取件\n\n范围。\n")):
            (self.fr / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.fr / rel).write_text(text, encoding="utf-8")
        self.inbox = self.fr / "inbox"
        self.inbox.mkdir()

    def cli(self, script: str, *args: str) -> tuple[int, dict, str]:
        proc = subprocess.run(
            [sys.executable, str(CORE / script), *args, "--feature", FEATURE, "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        out = json.loads(proc.stdout[proc.stdout.index("{"):]) if "{" in proc.stdout else {}
        return proc.returncode, out, proc.stdout + proc.stderr

    def status(self) -> dict:
        return self.cli("story_flow.py", "status")[1]

    def place(self, name: str = "澄清会.docx", paragraphs=MEETING, cls: str = "MEETING") -> Path:
        path = self.inbox / name
        if name.endswith(".docx"):
            write_docx(path, paragraphs)
        else:
            path.write_text("张三 10:02：上限五个\n", encoding="utf-8")
        (self.inbox / ".classify.json").write_text(json.dumps({name: cls}, ensure_ascii=False), encoding="utf-8")
        return path

    def imported(self, **kwargs) -> Path:
        path = self.place(**kwargs)
        code, _, log = self.cli("import_sources.py")
        self.assertEqual(0, code, log)
        return path

    def folder(self, docx: Path) -> tuple[str, Path]:
        path = meeting.transcript_path(self.fr, docx)
        return f"{docx.stem}@{path.parent.name}", path.parent

    def read_meeting(self, docx: Path, *, evidence=None, topics=None, notes=None) -> str:
        """写三份读会产物：默认是一份立得住的读法。"""
        key, folder = self.folder(docx)
        transcript = json.loads((folder / "transcript.json").read_text(encoding="utf-8"))
        (folder / "evidence.json").write_text(json.dumps(
            evidence if evidence is not None else {**transcript, "attendees": [], "corrections": []},
            ensure_ascii=False), encoding="utf-8")
        (folder / "topics.json").write_text(json.dumps(
            topics if topics is not None else [{"id": "T1", "title": "受理上限", "speeches": ["S1", "S2"]},
                                               {"id": "T2", "title": "通知方式", "speeches": ["S3"]}],
            ensure_ascii=False), encoding="utf-8")
        section = {"source": transcript["source"]["file"], "source_sha": transcript["source"]["sha256"],
                   "attendee_roles": [], "topics": notes if notes is not None else TOPICS}
        (self.fr / "AR" / "story-src" / "meeting-notes.json").write_text(
            json.dumps({"meetings": [section]}, ensure_ascii=False), encoding="utf-8")
        return key

    def problems(self) -> list[str]:
        return meeting.inspect(self.fr)["problems"]


class TheTranscriptIsParsed(MeetingCase):
    """D3 的形态：会名、时间、参会人、按议题分节、发言全场连续编号，认不出的段落不丢。"""

    def test_the_structure(self) -> None:
        docx = self.imported()
        data = json.loads(meeting.transcript_path(self.fr, docx).read_text(encoding="utf-8"))
        self.assertEqual({"title": "需求澄清会", "date": "2026-09-01 10:00", "attendees": ["张三", "李四"]},
                         data["meeting"])
        self.assertEqual(["议题一 受理上限", "议题二 通知方式"], [s["title"] for s in data["sections"]])
        speeches = [s for sec in data["sections"] for s in sec["speeches"]]
        self.assertEqual(["S1", "S2", "S3"], [s["id"] for s in speeches])
        self.assertEqual(("张三", "10:02"), (speeches[0]["speaker"], speeches[0]["time"]))
        self.assertEqual("上限先按五个来\n补一句，超出的排队", speeches[0]["text"], "认不出形态的段落没接进最近一条发言")


class EachVersionLandsInItsOwnFolder(MeetingCase):
    """一个源版本一个目录；导没导过按这一版的解析件在不在判。"""

    def test_import_registers_and_keeps_old_versions(self) -> None:
        docx = self.place()
        source = next(s for s in registry.build(self.fr)["sources"] if s["file"] == docx.name)
        self.assertEqual(("MEETING", False), (source["class"], source["ingested"]))
        self.assertEqual(0, self.cli("import_sources.py")[0])
        first = meeting.transcript_path(self.fr, docx)
        built = registry.build(self.fr)
        self.assertTrue(next(s for s in built["sources"] if s["file"] == docx.name)["ingested"])
        self.assertIn("meeting", [m["kind"] for m in built["materials"]], "转写不算材料，新会议开不出新一轮")
        self.imported(paragraphs=MEETING + [(None, "张三 10:30：补充一句")])
        self.assertTrue(first.is_file(), "新版本把旧版本的原文冲掉了")
        self.assertEqual(2, len(meeting.versions(self.fr)))

    def test_a_meeting_must_be_the_original_docx(self) -> None:
        self.place(name="纪要.md")
        code, _, log = self.cli("import_sources.py")
        self.assertEqual(1, code)
        self.assertIn("只收原始", log)


class TheSelfCheckNamesEachBreach(MeetingCase):
    """留痕、编号、去向、选项结果：结构上的缺口各自点名；语义归审查。"""

    def test_a_sound_reading_passes_and_an_unread_one_is_pending(self) -> None:
        docx = self.imported()
        key, _ = self.folder(docx)
        self.assertEqual([key], meeting.inspect(self.fr)["missing"])
        self.read_meeting(docx)
        self.assertEqual(([], []), (self.problems(), meeting.inspect(self.fr)["missing"]))

    def test_evidence_breaches(self) -> None:
        docx = self.imported()
        _, folder = self.folder(docx)
        base = json.loads((folder / "transcript.json").read_text(encoding="utf-8"))

        def variant(edit, corrections=()):
            data = json.loads(json.dumps(base))
            edit([s for sec in data["sections"] for s in sec["speeches"]], data)
            return {**data, "attendees": [], "corrections": list(corrections)}

        cases = {
            "删了一条发言": (variant(lambda s, d: d["sections"][1]["speeches"].clear()), "发言编号与转写对不上"),
            "改了编号": (variant(lambda s, d: s[1].update(id="S9")), "发言编号与转写对不上"),
            "留痕引了不存在的原文": (variant(lambda s, d: None, [{"speech": "S1", "original": "不存在的字",
                                                                "corrected": "x", "basis": "术语表"}]), "转写原文里没有"),
            "没登记的改动": (variant(lambda s, d: s[1].update(text="同意，按六个")), "没登记进 corrections"),
        }
        for name, (evidence, needle) in cases.items():
            with self.subTest(name):
                self.read_meeting(docx, evidence=evidence)
                self.assertTrue(any(needle in p for p in self.problems()), self.problems())
        self.read_meeting(docx, evidence=variant(
            lambda s, d: s[0].update(text=s[0]["text"].replace("五个", "5 个")),
            [{"speech": "S1", "original": "五个", "corrected": "5 个", "basis": "SR §3.2 写的是数字"}]))
        self.assertEqual([], self.problems(), "登记过的改动也被报了")

    def test_note_breaches(self) -> None:
        docx = self.imported()
        loose = json.loads(json.dumps(TOPICS))
        cases = {
            "登记的话题没去向": ({"topics": [{"id": "T1", "speeches": []}, {"id": "T2", "speeches": []},
                                        {"id": "T3", "speeches": []}]}, "没有去向"),
            "结论没原话": ({"notes": [{**loose[0], "conclusion": {"text": "上限五个"}}, loose[1]]}, "结论没有指回"),
            "选项缺结果": ({"notes": [loose[0], {**loose[1], "options": [
                {"key": "opt_a", "label": "按短信通知"}, loose[1]["options"][1]]}]}, "缺 effect"),
            "判不准却不问": ({"notes": [{**loose[0], "ownership": "unclear"}, loose[1]]}, "要 ask: true"),
        }
        for name, (kwargs, needle) in cases.items():
            with self.subTest(name):
                self.read_meeting(docx, **kwargs)
                self.assertTrue(any(needle in p for p in self.problems()), self.problems())


KEY, OLD = "澄清会@aaaaaaaa", "澄清会@bbbbbbbb"


def notes_of(**sections: list[dict]) -> dict:
    return {key.replace("_", "@"): {"topics": topics} for key, topics in sections.items()}


def contract(*gates: dict) -> dict:
    return {"rounds": [{"round": 1, "gates": list(gates)}]}


def shown(*keys: str) -> dict:
    return {"gate": "material_scope", "chosen": "confirm_scope", "outcome": "accepted", "meetings": list(keys)}


def signed(key: str, item: str, chosen: str, basis: str = "人的原话") -> dict:
    return {"gate": "meeting", "meeting": key, "item": item, "chosen": chosen, "outcome": "accepted", "basis": basis}


class TheEffectiveResultsFollowTheSignatures(unittest.TestCase):
    """人最终接受的 = 会议结论 × 契约里的裁决；派生只有一处。"""

    def results(self, notes: dict, *gates: dict) -> list[dict]:
        return meetings.effective_meeting_results(notes, contract(*gates))

    def test_an_unclear_topic_follows_the_chosen_ownership(self) -> None:
        topic = {"id": "T1", "ownership": "unclear", "ask": True, "changes": [LIMIT], "options": [
            {"key": "k1", "effect": {"ownership": "ours", "apply_changes": ["C1"]}},
            {"key": "k2", "effect": {"ownership": "not_ours", "apply_changes": ["C1"]}}]}
        notes = {KEY: {"topics": [topic]}}
        self.assertEqual(["C1"], [c["id"] for e in self.results(notes, signed(KEY, "T1", "k1")) for c in e["changes"]])
        self.assertEqual([], self.results(notes, signed(KEY, "T1", "k2")), "不属于本需求的也生效了")

    def test_a_decision_made_by_the_human_is_marked_as_such(self) -> None:
        notes = {KEY: {"topics": [TOPICS[1]]}}
        text = meetings.render(self.results(notes, signed(KEY, "T2", "opt_a", "就用短信")))
        for needle in ("受理后短信通知", "人工补定，原话「就用短信」", "落定遗留 O1"):
            self.assertIn(needle, text)
        self.assertNotIn("受理后短信通知", meetings.render(self.results(notes)), "没签就生效了")

    def test_unasked_topics_wait_for_the_first_gate(self) -> None:
        notes = {KEY: {"topics": [TOPICS[0]]}}
        self.assertEqual([], self.results(notes), "第一级表态之前就生效了")
        self.assertIn("上限五个，超出排队", meetings.render(self.results(notes, shown(KEY))))

    def test_a_converged_conclusion_changes_no_document(self) -> None:
        notes = {KEY: {"topics": [{**TOPICS[0], "changes": []}]}}
        text = meetings.render(self.results(notes, shown(KEY)))
        self.assertIn("（没有生效的变化）", text)
        self.assertIn(f"{KEY}/T1：上限五个", text.split("## 原文已确认", 1)[1])

    def test_only_the_chosen_option_decides_what_an_old_decision_becomes(self) -> None:
        """选项 key 不带含义：同一话题一个选项替代旧决定、一个不替代，旧决定只按选中的那个处理。"""
        old = {"id": "T1", "ownership": "ours", "ask": False, "changes": [LIMIT]}
        new = {"id": "T1", "ownership": "ours", "ask": True, "overturns": f"{OLD}/T1", "changes": [], "options": [
            {"key": "k1", "effect": {"ownership": "ours", "supersedes": []}},
            {"key": "k2", "effect": {"ownership": "ours", "supersedes": [f"{OLD}/T1"]}}]}
        notes = {OLD: {"topics": [old]}, KEY: {"topics": [new]}}
        refs = lambda *g: [e["ref"] for e in self.results(notes, shown(OLD), *g)]  # noqa: E731
        self.assertIn(f"{OLD}/T1", refs(), "新版本没裁决就撤销了旧决定")
        self.assertIn(f"{OLD}/T1", refs(signed(KEY, "T1", "k1")), "选了不替代的选项，旧决定却失效了")
        self.assertNotIn(f"{OLD}/T1", refs(signed(KEY, "T1", "k2")), "选了替代的选项，旧决定还在")


class TheFlowStopsOnceForTheMeeting(MeetingCase):
    """读会 → 与第一级同一轮摆给人 → 逐条裁决 → 第一级表态 → 有效结果写进 doc-refresh.md。"""

    def test_read_ask_decide_and_refresh(self) -> None:
        docx = self.imported()
        self.assertEqual(0, self.cli("story_flow.py", "round")[0])
        self.assertEqual("read_meeting", self.status()["next"])
        key = self.read_meeting(docx)
        self.assertEqual("await_gate:meeting", self.status()["next"])
        ask = ("story_flow.py", "decide", "--gate", "meeting", "--meeting", key, "--item", "T2", "--basis", "就用短信")
        code, out, _ = self.cli(*ask, "--chosen", "不存在")
        self.assertEqual(1, code)
        self.assertIn("不在本次选项集里", out["error"])
        code, _, log = self.cli(*ask, "--chosen", "opt_a")
        self.assertEqual(0, code, log)
        refresh = self.fr / "AR" / "story-src" / "doc-refresh.md"
        self.assertIn("人工补定，原话「就用短信」", refresh.read_text(encoding="utf-8"))
        self.assertNotIn("上限五个，超出排队", refresh.read_text(encoding="utf-8"), "没问人的话题在第一级表态前生效了")
        self.assertEqual("await_gate:material_scope", self.status()["next"])
        (self.fr / "AR" / "story-src" / ".gate-options.json").write_text(json.dumps(
            {"gate": "material_scope", "options": [{"key": "supplied"}, {"key": "confirm_scope"}]}), encoding="utf-8")
        code, _, log = self.cli("story_flow.py", "decide", "--gate", "material_scope",
                                "--chosen", "confirm_scope", "--basis", "材料够了")
        self.assertEqual(0, code, log)
        self.assertIn("上限五个，超出排队", refresh.read_text(encoding="utf-8"))
        flow = json.loads((self.fr / "AR" / "story-src" / "story-flow.json").read_text(encoding="utf-8"))
        self.assertEqual([key], flow["rounds"][-1]["gates"][-1]["meetings"], "第一级没记下摆给人的会议版本")


if __name__ == "__main__":
    unittest.main()
