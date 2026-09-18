"""会议材料：公共转换、版本留存、逐行纠偏、单话题判断与当前结果的输入绑定。

锁 1.9.2 步骤 7 工作包 1 的离线验收。构造件只证明脚本按合同工作——转换搬得对、原件留得住、
差异应用得准、话题清单立得住、人的裁决落得下、当前结果声明的输入与引用查得到；
**不证明模型读会的判断力**，那归独立审查与真实会议材料的实跑。
用例刻意换几种排版，因为脚本不认语义单元，任何排版都该能转换并定位。
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
from materials import importer, meeting, registry  # noqa: E402

FEATURE = "MT90001"
NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"')


def run(*pieces: object) -> str:
    """一个 run：字符串是文字，`br` / `tab` 是软换行与制表符。"""
    out = []
    for piece in pieces:
        if piece == "br":
            out.append("<w:br/>")
        elif piece == "tab":
            out.append("<w:tab/>")
        else:
            out.append(f'<w:t xml:space="preserve">{escape(str(piece))}</w:t>')
    return "<w:r>" + "".join(out) + "</w:r>"


def para(*pieces: object, style: str | None = None) -> str:
    props = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return "<w:p>" + props + run(*pieces) + "</w:p>"


def raw_para(inner: str, style: str | None = None) -> str:
    props = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return "<w:p>" + props + inner + "</w:p>"


def table(rows: list[list[str]]) -> str:
    body = "".join(
        "<w:tr>" + "".join(f"<w:tc>{para(cell)}</w:tc>" for cell in row) + "</w:tr>"
        for row in rows)
    return f"<w:tbl><w:tblPr/>{body}</w:tbl>"


def document(*blocks: str) -> str:
    return (f'<?xml version="1.0"?><w:document {NS}><w:body>'
            + "".join(blocks) + "</w:body></w:document>")


def write_docx(path: Path, xml: str) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", xml)
    return path


#: 同一场讨论的几种排版：脚本都只搬形态，谁在说话由模型判断
SAME_LINE = document(
    para("需求澄清会", style="Heading1"),
    para("会议时间：2026-09-01 10:00"), para("参会人：张三、李四"),
    para("议题一 受理上限", style="Heading2"),
    para("张三 10:02：上限先按五个来"), para("补一句，超出的排队"),
    para("李四 10:05：同意，按五个"),
    para("议题二 通知方式", style="Heading2"),
    para("李四 10:20：通知方式下次再定"))
SPLIT_LINE = document(
    para("需求澄清会", style="Heading1"),
    para("张三", "br", "10:02", "br", "上限先按五个来"),
    para("李四", "br", "10:05", "br", "同意，按五个"))
TABLE_LAYOUT = document(
    para("需求澄清会", style="Heading1"),
    table([["发言人", "时间", "内容"],
           ["张三", "10:02", "上限先按五个来"],
           ["李四", "10:05", "同意，按五个"]]))
TIME_FIRST = document(
    para("需求澄清会", style="Heading1"),
    para("[10:02] 张三\t上限先按五个来"), para("[10:05] 李四\t同意，按五个"))
NO_TIME = document(
    para("需求澄清会", style="Heading1"),
    para("张三：上限先按五个来"), para("李四：同意，按五个"))

#: 一份立得住的会议判断：一个话题不必问人，一个要问人。finding 是模型写的自然语言。
TOPICS = [
    {"id": "T1", "title": "受理上限", "ownership": "ours",
     "evidence": [{"start": 5, "end": 7}],
     "finding": "会上定了上限五个、超出排队；系统设计里那一节还写着未定，要按会上的改。"},
    {"id": "T2", "title": "通知方式", "ownership": "ours",
     "evidence": [{"start": 9, "end": 9}],
     "finding": "通知方式会上只说下次再定，本需求的通知行为因此还没有依据。",
     "question": "通知方式现在定下来，还是继续挂着？",
     "recommend": "a",
     "options": [{"key": "a", "label": "按短信通知，通知那一段据此写"},
                 {"key": "b", "label": "维持待定，正文只写边界"}]},
]


class MeetingCase(unittest.TestCase):
    """每个用例一份新工作区，跑真脚本。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.fr = self.root / "doc" / "features" / FEATURE
        for rel, text in (("RR/prd.md", "# 产品需求\n\n背景。\n"),
                          ("SR/design.md", "# 系统设计\n\n分工。\n"),
                          ("AR/design.md", "# 提取件\n\n范围。\n")):
            (self.fr / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.fr / rel).write_text(text, encoding="utf-8")
        self.inbox = self.fr / "inbox"
        self.inbox.mkdir()

    def cli(self, script: str, *args: str) -> tuple[int, dict, str]:
        proc = subprocess.run(
            [sys.executable, str(CORE / script), *args, "--feature", FEATURE,
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        out = json.loads(proc.stdout[proc.stdout.index("{"):]) if "{" in proc.stdout else {}
        return proc.returncode, out, proc.stdout + proc.stderr

    def status(self) -> dict:
        return self.cli("story_flow.py", "status")[1]

    def contract(self) -> dict:
        return json.loads((self.fr / "AR" / "story-src" / "story-flow.json")
                          .read_text(encoding="utf-8"))

    def place(self, name: str = "澄清会.docx", xml: str = SAME_LINE,
              cls: str = "MEETING") -> Path:
        path = self.inbox / name
        if name.endswith(".docx"):
            write_docx(path, xml)
        else:
            path.write_text("张三 10:02：上限五个\n", encoding="utf-8")
        classify = meeting.read_json(self.inbox / ".classify.json") or {}
        classify[name] = cls
        (self.inbox / ".classify.json").write_text(
            json.dumps(classify, ensure_ascii=False), encoding="utf-8")
        return path

    def imported(self, **kwargs) -> Path:
        path = self.place(**kwargs)
        code, _, log = self.cli("import_sources.py")
        self.assertEqual(0, code, log)
        return path

    def folder(self, docx: Path) -> tuple[str, Path]:
        folder = meeting.version_dir(self.fr, docx)
        return f"{docx.stem}@{folder.name}", folder

    def notes_path(self) -> Path:
        path = self.fr / "AR" / "story-src" / "meeting-notes.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def read_meeting(self, docx: Path, *, corrections=None, topics=None,
                     refresh: bool = True) -> str:
        """写读会产物：一份纠偏差异、一份会议判断。默认是一份立得住的读法。"""
        key, folder = self.folder(docx)
        (folder / meeting.CORRECTIONS).write_text(
            json.dumps(corrections if corrections is not None else [], ensure_ascii=False),
            encoding="utf-8")
        source = meeting.read_json(folder / meeting.SOURCE)
        section = {"source": source["file"], "source_sha": source["sha256"],
                   "title": "需求澄清会", "attendee_roles": [],
                   "topics": topics if topics is not None else TOPICS}
        self.notes_path().write_text(
            json.dumps({"meetings": [section]}, ensure_ascii=False), encoding="utf-8")
        if refresh:
            code, _, log = self.cli("story_flow.py", "meeting-refresh", "--meeting", key)
            self.assertEqual(0, code, log)
        return key

    def write_result(self, *, basis: str | None = None, topics=("T1", "T2"),
                     body: str = "本需求按会上的结论写。") -> Path:
        """模型写的当前会议结果：输入绑定 + 每个话题一个标题。"""
        notes = meeting.read_notes(self.fr, [])
        mark = basis if basis is not None else meetings.meeting_basis(notes, self.contract())
        key = next(iter(notes), "澄清会@00000000")
        rows = [f"<!-- meeting-basis:{mark} -->", "", "# 当前会议结果", ""]
        for tid in topics:
            rows += [f"### {key}/{tid} 话题", "", body, ""]
        path = self.fr / "AR" / "story-src" / "doc-refresh.md"
        path.write_text("\n".join(rows), encoding="utf-8")
        return path

    def confirm_materials(self, chosen: str = "confirm_scope") -> None:
        """人在第一级材料关卡上表态（第一轮无条件停这一次）。"""
        (self.fr / "AR" / "story-src" / ".gate-options.json").write_text(json.dumps(
            {"gate": "material_scope", "options": [{"key": "supplied"}, {"key": "confirm_scope"}]}),
            encoding="utf-8")
        code, _, log = self.cli("story_flow.py", "decide", "--gate", "material_scope",
                                "--chosen", chosen, "--basis", "材料够了")
        self.assertEqual(0, code, log)

    def decide_meeting(self, key: str, item: str = "T2", chosen: str = "a") -> None:
        code, _, log = self.cli("story_flow.py", "decide", "--gate", "meeting", "--meeting", key,
                                "--item", item, "--chosen", chosen, "--basis", "就用短信")
        self.assertEqual(0, code, log)

    def problems(self) -> list[str]:
        return meeting.inspect(self.fr)["problems"]

    def result_problems(self) -> list[str]:
        return meetings.refresh_problems(self.fr, meeting.read_notes(self.fr, []), self.contract())


class TheConverterMovesShapeNotMeaning(MeetingCase):
    """转换只搬形态：顺序、软换行、制表符、表格与内容控件；语义一个都不推断。"""

    def convert(self, xml: str) -> str:
        docx = write_docx(self.root / "一份.docx", xml)
        return importer.docx_to_markdown(docx, ".")[0]

    def test_text_keeps_document_order_with_breaks_and_links(self) -> None:
        text = self.convert(document(raw_para(
            run("张三") + '<w:hyperlink r:id="rId9">' + run("（外链）") + "</w:hyperlink>"
            + run("br", "10:02", "tab", "上限先按五个来"))))
        self.assertEqual(["张三（外链）", "10:02\t上限先按五个来"], text.split("\n"),
                         "超链接被挪到了末尾，或软换行/制表符没留住")

    def test_a_table_keeps_its_cells(self) -> None:
        text = self.convert(document(table([["发言人", "时间"], ["张三", "10:02"]])))
        self.assertEqual(["| 发言人 | 时间 |", "|---|---|", "| 张三 | 10:02 |"], text.split("\n"))

    def test_a_cell_keeps_its_line_break_and_escapes_pipes(self) -> None:
        cell = "<w:tc>" + raw_para(run("张三", "br", "同意 | 不反对")) + "</w:tc>"
        text = self.convert(document(f"<w:tbl><w:tblPr/><w:tr>{cell}</w:tr></w:tbl>"))
        self.assertIn(r"张三<br>同意 \| 不反对", text, "格内换行拆了行，或竖线没转义")

    def test_content_controls_are_transparent(self) -> None:
        text = self.convert(document(
            "<w:sdt><w:sdtPr/><w:sdtContent>" + para("控件里的一句") + "</w:sdtContent></w:sdt>"))
        self.assertEqual("控件里的一句", text)

    def test_an_unknown_structure_carrying_text_is_reported(self) -> None:
        with self.assertRaises(importer.ImportError_) as caught:
            self.convert(document("<w:altChunk>" + para("藏在里面的一句") + "</w:altChunk>"))
        self.assertIn("altChunk", str(caught.exception))
        self.assertIn("整份不导", str(caught.exception))

    def test_no_speaker_or_topic_is_inferred(self) -> None:
        docx = self.imported()
        _, folder = self.folder(docx)
        self.assertEqual(sorted(p.name for p in folder.iterdir()),
                         ["original.docx", "raw.md", "source.json"],
                         "转换阶段就生成了别的产物")
        raw = (folder / meeting.RAW).read_text(encoding="utf-8")
        self.assertNotIn("S1", raw)
        self.assertIn("张三 10:02：上限先按五个来", raw)


class AnyLayoutLandsAndCanBeCited(MeetingCase):
    """姓名时间同行、分行、表格、时间在前、没有时间——都能转换，也都引得到。"""

    def test_each_layout_is_convertible_and_citable(self) -> None:
        layouts = {"同一行": SAME_LINE, "分行": SPLIT_LINE, "表格": TABLE_LAYOUT,
                   "时间在前": TIME_FIRST, "没有时间": NO_TIME}
        for name, xml in layouts.items():
            with self.subTest(name):
                docx = self.imported(name=f"{name}会.docx", xml=xml)
                _, folder = self.folder(docx)
                lines, broken = meeting.raw_lines(folder)
                self.assertEqual("", broken)
                hit = [i + 1 for i, line in enumerate(lines) if "上限先按五个来" in line]
                self.assertTrue(hit, f"{name} 的原话没落进 raw.md")
                self.assertIn("上限先按五个来", lines[hit[0] - 1], "行号指不回那句原话")
        self.assertEqual(len(layouts), len(meeting.versions(self.fr)), "每种排版各留一版")


class EachVersionKeepsItsOwnOriginal(MeetingCase):
    """一个源版本一个目录，身份是原件；转换件坏了明说，能按原件补回。"""

    def test_import_registers_by_the_original_and_keeps_old_versions(self) -> None:
        docx = self.place()
        source = next(s for s in registry.build(self.fr)["sources"] if s["file"] == docx.name)
        self.assertEqual(("MEETING", False), (source["class"], source["ingested"]))
        self.assertEqual(0, self.cli("import_sources.py")[0])
        _, first = self.folder(docx)
        built = registry.build(self.fr)
        self.assertTrue(next(s for s in built["sources"] if s["file"] == docx.name)["ingested"])
        item = next(m for m in built["materials"] if m["kind"] == "meeting")
        self.assertEqual([f"AR/story-src/meetings/澄清会/{first.name}/original.docx"], item["paths"])
        self.imported(xml=SAME_LINE.replace("</w:body>", para("张三 10:30：补充一句") + "</w:body>"))
        self.assertTrue((first / meeting.RAW).is_file(), "新版本把旧版本的原文冲掉了")
        self.assertEqual(2, len(meeting.versions(self.fr)))

    def test_reimporting_the_same_original_does_not_touch_the_conversion(self) -> None:
        docx = self.imported()
        _, folder = self.folder(docx)
        before = (folder / meeting.RAW).read_bytes()
        self.assertEqual(0, self.cli("import_sources.py")[0])
        self.assertEqual(before, (folder / meeting.RAW).read_bytes(), "重导把旧转换件重算了")

    def test_a_broken_conversion_names_the_recovery(self) -> None:
        docx = self.imported()
        _, folder = self.folder(docx)
        (folder / meeting.RAW).write_text("被人手改过的原文\n", encoding="utf-8")
        self.assertTrue(any("对不上" in p and "original.docx" in p for p in self.problems()),
                        self.problems())
        digest_before = registry.build(self.fr)["digest"]
        (folder / meeting.RAW).write_text("再改一次\n", encoding="utf-8")
        self.assertEqual(digest_before, registry.build(self.fr)["digest"],
                         "材料身份跟着转换件变了——它应当只认原件")

    def test_a_missing_conversion_is_rebuilt_from_the_stored_original(self) -> None:
        docx = self.imported()
        _, folder = self.folder(docx)
        before = (folder / meeting.RAW).read_text(encoding="utf-8")
        (folder / meeting.RAW).unlink()
        code, _, log = self.cli("import_sources.py")
        self.assertEqual(0, code, log)
        self.assertEqual(before, (folder / meeting.RAW).read_text(encoding="utf-8"),
                         "补回来的原文与原来那一份不一样")
        self.assertEqual("", meeting.raw_lines(folder)[1])

    def test_a_version_that_cannot_be_rebuilt_says_so(self) -> None:
        """重建结果与登记摘要对不上（等同换过转换器）：明说恢复不了，不拿另一份文本冒充。"""
        docx = self.imported()
        _, folder = self.folder(docx)
        source = json.loads((folder / meeting.SOURCE).read_text(encoding="utf-8"))
        source["text_sha256"] = "0" * 64
        (folder / meeting.SOURCE).write_text(json.dumps(source), encoding="utf-8")
        (folder / meeting.RAW).unlink()
        code, out, log = self.cli("import_sources.py")
        self.assertEqual(1, code, log)
        self.assertIn("找回这一版的 raw.md 快照", out["error"])
        self.assertFalse((folder / meeting.RAW).is_file(), "对不上却还是写了一份")

    def test_a_meeting_must_be_the_original_docx(self) -> None:
        self.place(name="纪要.md")
        code, _, log = self.cli("import_sources.py")
        self.assertEqual(1, code)
        self.assertIn("只收原始", log)


class TheCorrectionsAreDiffsOnly(MeetingCase):
    """模型只交差异，阅读件由脚本出；问题一次报全，报了就不出件。"""

    def test_an_empty_diff_still_produces_a_verbatim_copy(self) -> None:
        docx = self.imported()
        key, folder = self.folder(docx)
        (folder / meeting.CORRECTIONS).write_text("[]", encoding="utf-8")
        self.assertEqual(0, self.cli("story_flow.py", "meeting-refresh", "--meeting", key)[0],
                         "空数组也该出件")
        self.assertEqual((folder / meeting.RAW).read_text(encoding="utf-8").rstrip("\n"),
                         (folder / meeting.EVIDENCE).read_text(encoding="utf-8").rstrip("\n"))

    def test_a_declared_fix_lands_and_the_other_lines_stay(self) -> None:
        docx = self.imported()
        _, folder = self.folder(docx)
        lines = meeting.raw_lines(folder)[0]
        line = next(i + 1 for i, text in enumerate(lines) if "上限先按五个来" in text)
        self.read_meeting(docx, corrections=[{
            "line": line, "original": lines[line - 1],
            "corrected": lines[line - 1].replace("五个", "5 个"), "basis": "系统设计里写的是数字"}])
        fixed = (folder / meeting.EVIDENCE).read_text(encoding="utf-8").split("\n")
        self.assertIn("5 个", fixed[line - 1])
        self.assertEqual(len(lines), len(fixed), "行数变了")
        self.assertEqual(lines[:line - 1], fixed[:line - 1], "没改的行也被动了")
        self.assertEqual([], self.problems())

    def test_every_breach_is_named_at_once_and_nothing_is_overwritten(self) -> None:
        docx = self.imported()
        key, folder = self.folder(docx)
        lines = meeting.raw_lines(folder)[0]
        line = next(i + 1 for i, text in enumerate(lines) if "上限先按五个来" in text)
        self.read_meeting(docx)
        good = (folder / meeting.EVIDENCE).read_text(encoding="utf-8")
        (folder / meeting.CORRECTIONS).write_text(json.dumps([
            {"line": 999, "original": "x", "corrected": "y", "basis": "术语表"},
            {"line": line, "original": "对不上的原文", "corrected": "y", "basis": "术语表"},
            {"line": 1, "original": lines[0], "corrected": "换\n行", "basis": "术语表"},
            {"line": 1, "original": lines[0], "corrected": "第二条", "basis": "术语表"},
            {"line": 2, "original": lines[1], "corrected": "少了依据", "basis": "  "},
        ], ensure_ascii=False), encoding="utf-8")
        code, out, log = self.cli("story_flow.py", "meeting-refresh", "--meeting", key)
        self.assertEqual(1, code, log)
        for needle in ("不是 raw.md 里的行号", "与 raw.md 对不上", "有换行", "两条纠偏", "没写 basis"):
            self.assertIn(needle, out["error"], out["error"])
        self.assertEqual(good, (folder / meeting.EVIDENCE).read_text(encoding="utf-8"),
                         "报错的那一跑把已有的阅读件覆盖了")

    def test_an_unknown_version_is_refused(self) -> None:
        self.imported()
        code, out, _ = self.cli("story_flow.py", "meeting-refresh", "--meeting", "不存在@12345678")
        self.assertEqual(1, code)
        self.assertIn("没有会议版本", out["error"])


class TheTopicListStandsOnItsOwn(MeetingCase):
    """一个话题只登记一次：编号、归属、原话、finding 与要问人的那几项。"""

    def test_a_sound_reading_passes_without_any_topic_index(self) -> None:
        docx = self.imported()
        key, folder = self.folder(docx)
        self.assertEqual([key], meeting.inspect(self.fr)["missing"])
        self.read_meeting(docx)
        seen = meeting.inspect(self.fr)
        self.assertEqual(([], [], []), (seen["problems"], seen["missing"], seen["stale"]))
        self.assertFalse((folder / "topics.json").exists(), "还要求一份话题索引")

    def test_an_old_topic_index_is_named_as_unsupported(self) -> None:
        docx = self.imported()
        _, folder = self.folder(docx)
        (folder / "topics.json").write_text("[]", encoding="utf-8")
        self.read_meeting(docx)
        self.assertTrue(any("topics.json" in p and "本轮" in p for p in self.problems()),
                        self.problems())

    def test_each_breach_in_the_list(self) -> None:
        docx = self.imported()
        loose = json.loads(json.dumps(TOPICS))
        cases = {
            "话题编号重复": ([loose[0], {**loose[0], "title": "另一说法"}], "话题 T1 重复"),
            "没写归属": ([{**loose[0], "ownership": "x"}], "ownership 要写"),
            "没写标题": ([{**loose[0], "title": " "}], "没写 title"),
            "没写 finding": ([{**loose[0], "finding": ""}], "没写 finding"),
            "引用越界": ([{**loose[0], "evidence": [{"start": 1, "end": 900}]}],
                       "不在 raw.md 里"),
            "没写引用": ([{**loose[0], "evidence": []}], "没有指回 raw.md 的行范围"),
            "归属不明却不问": ([{**loose[0], "ownership": "unclear"}], "要写 question"),
            "不问却摆了选项": ([{**loose[0], "options": [{"key": "a", "label": "x"}]}],
                          "没有 question 却写了 options"),
            "选项 key 重复": ([{**loose[1], "options": [
                {"key": "a", "label": "x"}, {"key": "a", "label": "y"}]}], "选项 key 有重复"),
            "推荐不在选项里": ([{**loose[1], "recommend": "z"}], "不在选项里"),
            "问人却没有选项": ([{**loose[1], "options": []}], "至少一个真实选项"),
        }
        for name, (topics, needle) in cases.items():
            with self.subTest(name):
                self.read_meeting(docx, topics=topics)
                self.assertTrue(any(needle in p for p in self.problems()), self.problems())

    def test_a_duplicate_version_section_is_refused(self) -> None:
        docx = self.imported()
        self.read_meeting(docx)
        data = json.loads(self.notes_path().read_text(encoding="utf-8"))
        data["meetings"].append(dict(data["meetings"][0]))
        self.notes_path().write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.assertTrue(any("有两节" in p for p in self.problems()), self.problems())

    def test_the_finding_is_not_read_by_the_script(self) -> None:
        """finding 里写什么词都不改变脚本的判断：它不替模型判业务。"""
        docx = self.imported()
        for text in ("会上定了上限五个。", "未决：上限没定。", "不涉及本需求。"):
            with self.subTest(text):
                self.read_meeting(docx, topics=[{**TOPICS[0], "finding": text}])
                self.assertEqual([], self.problems())


class TheHumanChoiceIsTheOnlyDecision(MeetingCase):
    """问不问由 question 说了算；人选的 key 与原话落进契约，脚本不替他选。"""

    def setUp(self) -> None:
        super().setUp()
        self.docx = self.imported()
        self.assertEqual(0, self.cli("story_flow.py", "round")[0])
        self.confirm_materials()
        self.key = self.read_meeting(self.docx)

    def decide(self, *args: str) -> tuple[int, dict, str]:
        return self.cli("story_flow.py", "decide", "--gate", "meeting",
                        "--meeting", self.key, "--item", "T2", *args)

    def test_only_a_listed_key_is_recorded(self) -> None:
        code, out, _ = self.decide("--chosen", "不存在", "--basis", "就用短信")
        self.assertEqual(1, code)
        self.assertIn("不在本次选项集里", out["error"])
        code, _, log = self.decide("--chosen", "a", "--basis", "就用短信")
        self.assertEqual(0, code, log)
        gate = next(g for g in self.contract()["rounds"][-1]["gates"] if g["gate"] == "meeting")
        self.assertEqual(("a", "就用短信", "human"), (gate["chosen"], gate["basis"], gate["by"]))
        self.assertEqual({"key", "label"}, set(gate["options"][0]), "关卡记录里多抄了别的东西")

    def test_a_topic_without_a_question_is_never_asked(self) -> None:
        self.assertEqual(["T2"], [a.split("/")[-1] for a in meetings.pending_asks(
            meeting.read_notes(self.fr, []), self.contract())])
        code, out, _ = self.cli("story_flow.py", "decide", "--gate", "meeting",
                                "--meeting", self.key, "--item", "T1",
                                "--chosen", "a", "--basis", "随便")
        self.assertEqual(1, code)
        self.assertIn("没有要问人的话题", out["error"])

    def test_the_answer_the_human_actually_gave_is_what_lands(self) -> None:
        """人给了自选答案：把它补成真实选项再记，不替他选推荐项。"""
        topics = json.loads(json.dumps(TOPICS))
        topics[1]["options"].append({"key": "c", "label": "先按站内信通知，短信下一轮再说"})
        self.read_meeting(self.docx, topics=topics)
        code, _, log = self.decide("--chosen", "c", "--basis", "先站内信")
        self.assertEqual(0, code, log)
        gate = next(g for g in self.contract()["rounds"][-1]["gates"] if g["gate"] == "meeting")
        self.assertEqual("c", gate["chosen"], "记成了推荐项")


class TheCurrentResultIsWrittenByTheModel(MeetingCase):
    """当前会议结果由模型写：脚本只核输入绑定、话题去向与引用，不判业务。"""

    def setUp(self) -> None:
        super().setUp()
        self.docx = self.imported()
        self.assertEqual(0, self.cli("story_flow.py", "round")[0])
        self.confirm_materials()
        self.key = self.read_meeting(self.docx)

    def settle(self) -> None:
        """人答完会议里要他定的那一条。"""
        self.decide_meeting(self.key)

    def test_the_result_is_asked_for_only_after_the_human_has_spoken(self) -> None:
        self.assertEqual("await_gate:meeting", self.status()["next"])
        self.assertFalse((self.fr / "AR" / "story-src" / "doc-refresh.md").exists(),
                         "人还没表态就写了当前结果")
        self.settle()
        state = self.status()
        self.assertEqual("read_meeting", state["next"])
        self.assertIn("meeting-basis:", state["action"])
        self.write_result()
        self.assertEqual("run_analysis", self.status()["next"], "结果写好了却还卡在会议这一段")

    def test_a_stale_basis_names_the_gap(self) -> None:
        self.settle()
        self.write_result(basis="0" * 16)
        self.assertTrue(any("声明的输入是" in p for p in self.result_problems()),
                        self.result_problems())

    def test_a_changed_judgement_makes_the_old_result_stale(self) -> None:
        self.settle()
        self.write_result()
        self.assertEqual([], self.result_problems())
        topics = json.loads(json.dumps(TOPICS))
        topics.append({"id": "T3", "title": "另一个话题", "ownership": "not_ours",
                       "evidence": [{"start": 3, "end": 3}], "finding": "这条归别的单子。"})
        self.read_meeting(self.docx, topics=topics)
        self.assertTrue(self.result_problems(), "会议判断变了，旧结果却还算数")

    def test_every_topic_needs_a_destination_including_the_ones_that_are_not_ours(self) -> None:
        topics = json.loads(json.dumps(TOPICS))
        topics.append({"id": "T3", "title": "余额提醒", "ownership": "not_ours",
                       "evidence": [{"start": 3, "end": 3}], "finding": "另一张单子的事。"})
        self.read_meeting(self.docx, topics=topics)
        self.settle()
        self.write_result(topics=("T1", "T2"))
        problems = self.result_problems()
        self.assertTrue(any("缺这几个话题的去向" in p and "T3" in p for p in problems), problems)

    def test_a_citation_must_point_at_a_real_line(self) -> None:
        self.settle()
        path = self.write_result()
        _, folder = self.folder(self.docx)
        rel = (folder / meeting.RAW).relative_to(self.fr).as_posix()
        path.write_text(path.read_text(encoding="utf-8") + f"\n引用 {rel}:L900\n", encoding="utf-8")
        self.assertTrue(any("指不到真实的原文行" in p for p in self.result_problems()),
                        self.result_problems())
        path.write_text(path.read_text(encoding="utf-8").replace(":L900", ":L5-L6"),
                        encoding="utf-8")
        self.assertEqual([], self.result_problems())

    def test_the_wording_of_the_result_is_not_judged(self) -> None:
        """正文里写没写「未决」两个字，脚本不管——那是审查要读的。"""
        self.settle()
        self.write_result(body="这一段还没有结论。")
        self.assertEqual([], self.result_problems())

    def test_a_second_heading_for_one_topic_is_refused(self) -> None:
        self.settle()
        self.write_result(topics=("T1", "T2", "T2"))
        self.assertTrue(any("有两个标题" in p for p in self.result_problems()),
                        self.result_problems())


class AMeetingNameWithSpacesStillResolves(MeetingCase):
    """会议文件名带空格是合法的：标题与引用都按已知版本与实际目录认，不靠「没有空格」这个假设。"""

    def setUp(self) -> None:
        super().setUp()
        self.docx = self.imported(name="需求 讨论.docx")
        self.assertEqual(0, self.cli("story_flow.py", "round")[0])
        self.confirm_materials()
        self.key = self.read_meeting(self.docx, topics=[TOPICS[0]])
        self.rel = (self.folder(self.docx)[1] / meeting.RAW).relative_to(self.fr).as_posix()

    def result(self, tail: str = "") -> Path:
        path = self.write_result(topics=("T1",))
        if tail:
            path.write_text(path.read_text(encoding="utf-8") + tail, encoding="utf-8")
        return path

    def test_a_heading_with_a_spaced_version_counts_as_a_destination(self) -> None:
        self.assertIn(" ", self.key, "这一版的主名本来就带空格")
        self.result()
        self.assertEqual([], self.result_problems(), "带空格的版本名把正确的标题判成了缺去向")

    def test_a_citation_under_a_spaced_path_is_range_checked(self) -> None:
        self.result(f"\n原话见 {self.rel}:L999\n")
        self.assertTrue(any("指不到真实的原文行" in p for p in self.result_problems()),
                        self.result_problems())
        self.result(f"\n原话见 {self.rel}:L5-L6\n")
        self.assertEqual([], self.result_problems(), "路径带空格的合法引用被判成了越界")

    #: 三种合法围栏写法：普通三反引号、波浪号、以及四反引号里再嵌一层三反引号
    FENCES = {
        "三反引号": ["```markdown", "示例：", "{title}", "```"],
        "波浪号": ["~~~markdown", "示例：", "{title}", "~~~"],
        "四反引号里包三反引号": ["````markdown", "```markdown", "{title}", "```", "````"],
        # 带语言标记的那一行是围栏里的代码，不是关闭行
        "围栏里还有一行带语言标记": ["```text", "```python", "{title}", "```"],
    }

    def fenced_result(self, kind: str, *, real: bool = False) -> None:
        """把标题样例放进围栏；`real` 再在围栏之后补一个真的标题。"""
        path = self.fr / "AR" / "story-src" / "doc-refresh.md"
        mark = meetings.meeting_basis(meeting.read_notes(self.fr, []), self.contract())
        title = f"### {self.key}/T1 受理上限"
        rows = [f"<!-- meeting-basis:{mark} -->", "", "# 当前会议结果", "", "写法示例：", ""]
        rows += [line.replace("{title}", title) for line in self.FENCES[kind]] + [""]
        if real:
            rows += [title, "", "本需求采纳上限五个。", ""]
        path.write_text("\n".join(rows), encoding="utf-8")

    def test_an_example_in_a_fence_is_not_a_destination(self) -> None:
        """围栏里抄一份标题样例，不能顶替真的去向——反引号、波浪号与嵌套围栏都算。"""
        for kind in self.FENCES:
            with self.subTest(kind):
                self.fenced_result(kind)
                problems = self.result_problems()
                self.assertTrue(any("缺这几个话题的去向" in p for p in problems), problems)

    def test_a_real_heading_after_a_fence_still_counts(self) -> None:
        """围栏关掉之后的标题是真的去向：关闭要同字符、不短于开启。"""
        for kind in self.FENCES:
            with self.subTest(kind):
                self.fenced_result(kind, real=True)
                self.assertEqual([], self.result_problems())


class TheFlowStopsOnceForTheMeeting(MeetingCase):
    """会议是材料的一种：问料 → 交料 → 读会 → 有要人定的话题才停一次 → 当前结果 → 需求分析。"""

    def test_read_refresh_ask_decide(self) -> None:
        docx = self.imported()
        self.assertEqual(0, self.cli("story_flow.py", "round")[0])
        self.assertEqual("await_gate:material_scope", self.status()["next"],
                         "第一轮先问材料，会议不排在材料关卡前面")
        self.confirm_materials()
        self.assertEqual("read_meeting", self.status()["next"])
        key, folder = self.folder(docx)
        (folder / meeting.CORRECTIONS).write_text("[]", encoding="utf-8")
        self.assertEqual("refresh_meeting", self.status()["next"], "阅读件还没出就往下走了")
        self.assertEqual(0, self.cli("story_flow.py", "meeting-refresh", "--meeting", key)[0])
        self.read_meeting(docx)
        state = self.status()
        self.assertEqual("await_gate:meeting", state["next"])
        self.assertEqual(["T1", "T2"], [t["topic"] for t in state["meetings"]],
                         "关卡那一轮没把全部话题摆出来")
        self.assertEqual([None, "a"], [t.get("recommend") for t in state["meetings"]])
        self.decide_meeting(key)
        self.assertEqual("read_meeting", self.status()["next"], "裁决之后该写当前结果")
        self.write_result()
        self.assertEqual("run_analysis", self.status()["next"], "会议之后又回头问了一次材料")

    def test_materials_supplied_later_are_not_asked_about_again(self) -> None:
        """人说「料放进去了」，交来的料里有会议：导入、读会，不再回头问一次材料。"""
        (self.inbox / "readme.md").write_text("空收件箱" + chr(10), encoding="utf-8")
        self.assertEqual(0, self.cli("story_flow.py", "round")[0])
        docx = self.place()
        self.confirm_materials("supplied")
        self.assertEqual("import_materials", self.status()["next"])
        self.assertEqual(0, self.cli("import_sources.py")[0])
        self.assertEqual(0, self.cli("story_flow.py", "round")[0])
        self.assertEqual("read_meeting", self.status()["next"])
        key = self.read_meeting(docx)
        self.assertEqual("await_gate:meeting", self.status()["next"])
        self.decide_meeting(key)
        self.write_result()
        self.assertEqual("run_analysis", self.status()["next"])
        asked = [g for r in self.contract()["rounds"] for g in r.get("gates") or []
                 if g["gate"] == "material_scope"]
        self.assertEqual(1, len(asked), "材料关卡问了不止一次")

    def test_a_meeting_with_nothing_to_ask_does_not_stop(self) -> None:
        docx = self.imported()
        self.assertEqual(0, self.cli("story_flow.py", "round")[0])
        self.confirm_materials()
        self.read_meeting(docx, topics=[TOPICS[0]])
        state = self.status()
        self.assertEqual("read_meeting", state["next"], "没有要问人的话题却停下来问了")
        self.assertIn("meeting-basis:", state["action"])
        self.write_result(topics=("T1",))
        self.assertEqual("run_analysis", self.status()["next"])

    def test_the_material_gate_is_not_reopened_by_a_meeting(self) -> None:
        docx = self.imported()
        self.assertEqual(0, self.cli("story_flow.py", "round")[0])
        self.confirm_materials()
        self.read_meeting(docx)
        code, out, _ = self.cli("story_flow.py", "decide", "--gate", "material_scope",
                                "--chosen", "confirm_scope", "--basis", "再确认一次")
        self.assertEqual(1, code)
        self.assertIn("本轮第一级已经定了", out["error"])

    def test_a_meeting_arriving_after_closure_reopens(self) -> None:
        """收口之后才导进来的会议没有会议判断：先 reopen 再读会；读过的会不算迟到。"""
        from flow import routing
        docx = self.imported()
        self.assertEqual(0, self.cli("story_flow.py", "round")[0])
        contract = {**self.contract(), "status": "complete"}
        self.assertEqual("reopen_meeting", routing.next_step(self.fr, contract)[0])
        self.read_meeting(docx)
        self.assertNotEqual("reopen_meeting", routing.next_step(self.fr, contract)[0])

    def test_every_topic_shows_up_including_the_ones_that_are_not_ours(self) -> None:
        docx = self.imported()
        self.assertEqual(0, self.cli("story_flow.py", "round")[0])
        self.confirm_materials()
        topics = [{**TOPICS[0], "ownership": "not_ours"},
                  {**TOPICS[1], "ownership": "unclear"}]
        self.read_meeting(docx, topics=topics)
        rows = self.status()["meetings"]
        self.assertEqual(["not_ours", "unclear"], [r["ownership"] for r in rows])
        self.assertTrue(all(r["evidence"][0].startswith("AR/story-src/meetings/") for r in rows
                            if r.get("evidence")))

    def test_a_feature_without_meetings_keeps_the_old_path(self) -> None:
        (self.inbox / "readme.md").write_text("空收件箱\n", encoding="utf-8")
        self.assertEqual(0, self.cli("story_flow.py", "round")[0])
        state = self.status()
        self.assertNotIn("meetings", state)
        self.assertEqual("await_gate:material_scope", state["next"])
        self.assertFalse((self.fr / "AR" / "story-src" / "doc-refresh.md").exists(),
                         "没有会议却造了一份会议结果")


class TwoMeetingsKeepBothSources(MeetingCase):
    """两场会：原文与判断各自留着，脚本不按文件名或时间替谁覆盖谁。"""

    def test_neither_file_order_nor_time_decides(self) -> None:
        first = self.imported(name="早会.docx")
        later = self.imported(name="晚会.docx",
                              xml=SAME_LINE.replace("上限先按五个来", "上限改成八个"))
        self.assertEqual(0, self.cli("story_flow.py", "round")[0])
        sections = []
        for docx, finding in ((first, "早会定的是五个。"), (later, "晚会改成八个，与早会不一致。")):
            key, folder = self.folder(docx)
            (folder / meeting.CORRECTIONS).write_text("[]", encoding="utf-8")
            self.assertEqual(0, self.cli("story_flow.py", "meeting-refresh", "--meeting", key)[0])
            source = meeting.read_json(folder / meeting.SOURCE)
            sections.append({"source": source["file"], "source_sha": source["sha256"],
                             "topics": [{**TOPICS[0], "finding": finding}]})
        self.notes_path().write_text(json.dumps({"meetings": sections}, ensure_ascii=False),
                                     encoding="utf-8")
        self.assertEqual([], self.problems())
        notes = meeting.read_notes(self.fr, [])
        self.assertEqual(2, len(notes), "两场会只剩一场")
        rows = meetings.topic_digest(self.fr, notes, self.contract())
        self.assertEqual(2, len(rows), "摆给人的话题被合并了")
        self.assertEqual({"早会定的是五个。", "晚会改成八个，与早会不一致。"},
                         {r["finding"] for r in rows}, "脚本改写了模型的判断")


if __name__ == "__main__":
    unittest.main()
