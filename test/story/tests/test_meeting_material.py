"""会议材料：公共转换、版本留存、逐行纠偏、引用与有效结果。

锁 1.9.2 步骤 6 工作包 1 的离线验收。构造件只证明脚本按合同工作——转换搬得对、原件留得住、
差异应用得准、引用指得到、派生按人签的结果算；**不证明模型读会的判断力**，那归独立审查与
真实会议材料的实跑。用例刻意换几种排版，因为脚本不认语义单元，任何排版都该能转换并定位。
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

LIMIT = {"id": "C1", "kind": "modify", "doc": "SR/design.md", "section": "§3.2",
         "before": "上限未定", "after": "上限五个，超出排队", "impact": "受理校验",
         "evidence": [{"start": 5, "end": 6}]}
NOTICE = {"kind": "add", "doc": "SR/design.md", "section": "§4", "before": "未写通知",
          "after": "受理后短信通知", "impact": "通知章", "resolves": "O1"}
TOPICS_INDEX = [{"id": "T1", "title": "受理上限", "evidence": [{"start": 5, "end": 7}]},
                {"id": "T2", "title": "通知方式", "evidence": [{"start": 9, "end": 9}]}]
NOTES_TOPICS = [
    {"id": "T1", "ownership": "ours", "changes": [LIMIT], "open_points": [], "ask": False,
     "conclusion": {"text": "上限五个", "scope": "受理", "evidence": [{"start": 7, "end": 7}]}},
    {"id": "T2", "ownership": "ours", "changes": [], "ask": True, "ask_reason": "unresolved",
     "recommend": "opt_a",
     "open_points": [{"id": "O1", "what": "通知方式未定", "impact": "通知章", "needs": "产品定",
                      "evidence": [{"start": 9, "end": 9}]}],
     "options": [
         {"key": "opt_a", "label": "按短信通知",
          "effect": {"ownership": "ours", "apply_changes": [], "add_changes": [NOTICE],
                     "supersedes": []}},
         {"key": "opt_b", "label": "维持待定",
          "effect": {"ownership": "ours", "apply_changes": [], "add_changes": [],
                     "supersedes": [], "keep_open": ["O1"]}}]},
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

    def read_meeting(self, docx: Path, *, corrections=None, topics=None, notes=None,
                     refresh: bool = True) -> str:
        """写三份读会产物：默认是一份立得住的读法。"""
        key, folder = self.folder(docx)
        (folder / meeting.CORRECTIONS).write_text(
            json.dumps(corrections if corrections is not None else [], ensure_ascii=False),
            encoding="utf-8")
        (folder / meeting.TOPICS).write_text(
            json.dumps(topics if topics is not None else TOPICS_INDEX, ensure_ascii=False),
            encoding="utf-8")
        source = meeting.read_json(folder / meeting.SOURCE)
        section = {"source": source["file"], "source_sha": source["sha256"],
                   "attendee_roles": [],
                   "topics": notes if notes is not None else NOTES_TOPICS}
        (self.fr / "AR" / "story-src" / "meeting-notes.json").parent.mkdir(
            parents=True, exist_ok=True)
        (self.fr / "AR" / "story-src" / "meeting-notes.json").write_text(
            json.dumps({"meetings": [section]}, ensure_ascii=False), encoding="utf-8")
        if refresh:
            code, _, log = self.cli("story_flow.py", "meeting-refresh", "--meeting", key)
            self.assertEqual(0, code, log)
        return key

    def problems(self) -> list[str]:
        return meeting.inspect(self.fr)["problems"]


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
                quoted = meeting.quote(lines, {"start": hit[0], "end": hit[0]})
                self.assertIn("上限先按五个来", quoted)
        self.assertEqual(len(layouts), len(meeting.versions(self.fr)), "每种排版各留一版")


class EachVersionKeepsItsOwnOriginal(MeetingCase):
    """一个源版本一个目录，身份是原件；转换件坏了明说，不静默重建。"""

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
        key, folder = self.folder(docx)
        lines = meeting.raw_lines(folder)[0]
        line = next(i + 1 for i, text in enumerate(lines) if "上限先按五个来" in text)
        self.read_meeting(docx, corrections=[{
            "line": line, "original": lines[line - 1],
            "corrected": lines[line - 1].replace("五个", "5 个"), "basis": "SR §3.2 写的是数字"}])
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


class TheSelfCheckNamesEachBreach(MeetingCase):
    """引用、编号、去向、选项结果：结构上的缺口各自点名；语义归审查。"""

    def test_a_sound_reading_passes_and_an_unread_one_is_pending(self) -> None:
        docx = self.imported()
        key, _ = self.folder(docx)
        self.assertEqual([key], meeting.inspect(self.fr)["missing"])
        self.read_meeting(docx)
        seen = meeting.inspect(self.fr)
        self.assertEqual(([], [], []), (seen["problems"], seen["missing"], seen["stale"]))

    def test_the_index_breaches(self) -> None:
        docx = self.imported()
        cases = {
            "编号重复": ([{"id": "T1", "evidence": [{"start": 1, "end": 1}]},
                          {"id": "T1", "evidence": [{"start": 2, "end": 2}]}], "重复"),
            "引用越界": ([{"id": "T1", "evidence": [{"start": 1, "end": 900}]},
                          {"id": "T2", "evidence": [{"start": 2, "end": 2}]}], "不在 raw.md 里"),
            "没写引用": ([{"id": "T1"}, {"id": "T2", "evidence": [{"start": 2, "end": 2}]}],
                         "没有指回 raw.md 的行范围"),
        }
        for name, (topics, needle) in cases.items():
            with self.subTest(name):
                self.read_meeting(docx, topics=topics)
                self.assertTrue(any(needle in p for p in self.problems()), self.problems())

    def test_the_note_breaches(self) -> None:
        docx = self.imported()
        loose = json.loads(json.dumps(NOTES_TOPICS))
        cases = {
            "登记的话题没去向": ([loose[0]], "没有去向"),
            "结论没原话": ([{**loose[0], "conclusion": {"text": "上限五个"}}, loose[1]], "没有指回"),
            "选项缺结果": ([loose[0], {**loose[1], "options": [
                {"key": "opt_a", "label": "按短信通知"}, loose[1]["options"][1]]}], "缺 effect"),
            "判不准却不问": ([{**loose[0], "ownership": "unclear"}, loose[1]], "要 ask: true"),
            "写了原因却不问": ([{**loose[0], "ask_reason": "high_impact"}, loose[1]],
                               "ask 却是 false"),
            "问人没写原因": ([loose[0], {**loose[1], "ask_reason": "因为重要"}], "ask_reason 写"),
            "保留的遗留不在册": ([loose[0], {**loose[1], "options": [
                loose[1]["options"][0],
                {**loose[1]["options"][1], "effect": {
                    **loose[1]["options"][1]["effect"], "keep_open": ["O9"]}}]}],
                "keep_open 要指向"),
            "既落定又保留": ([loose[0], {**loose[1], "options": [
                {**loose[1]["options"][0], "effect": {
                    **loose[1]["options"][0]["effect"], "keep_open": ["O1"]}},
                loose[1]["options"][1]]}], "既落定又保留"),
            "替代了不存在的决定": ([loose[0], {**loose[1], "overturns": "别的会@aaaaaaaa/T1",
                                              "options": loose[1]["options"]}], "不存在"),
            "话题编号重复": ([loose[0], loose[1], {**loose[1], "conclusion": None}], "话题 T2 重复"),
            "变化编号重复": ([{**loose[0], "changes": [LIMIT, {**LIMIT, "after": "另一种说法"}]},
                              loose[1]], "变化 C1 重复"),
            "选项 key 重复": ([loose[0], {**loose[1], "options": [
                loose[1]["options"][0], {**loose[1]["options"][1], "key": "opt_a"}]}],
                "选项 key 有重复"),
            "遗留没给原话": ([loose[0], {**loose[1], "open_points": [
                {"id": "O1", "what": "通知方式未定", "impact": "通知章", "needs": "产品定"}]}],
                "遗留 O1：没有指回"),
            "替代指着自己": ([loose[0], {**loose[1], "options": [
                {**loose[1]["options"][0], "effect": {
                    **loose[1]["options"][0]["effect"],
                    "supersedes": ["澄清会@REPLACE/T2"]}},
                loose[1]["options"][1]]}], "指着自己"),
        }
        key, _ = self.folder(self.place())
        for name, (notes, needle) in cases.items():
            with self.subTest(name):
                text = json.dumps(notes, ensure_ascii=False).replace("澄清会@REPLACE", key)
                self.read_meeting(docx, notes=json.loads(text))
                self.assertTrue(any(needle in p for p in self.problems()), self.problems())


KEY, OLD = "澄清会@aaaaaaaa", "早会@bbbbbbbb"


def contract(*gates: dict) -> dict:
    return {"rounds": [{"round": 1, "gates": list(gates)}]}


def shown(*keys: str) -> dict:
    return {"gate": "material_scope", "chosen": "confirm_scope", "outcome": "accepted",
            "meetings": list(keys)}


def signed(key: str, item: str, chosen: str, basis: str = "人的原话") -> dict:
    return {"gate": "meeting", "meeting": key, "item": item, "chosen": chosen,
            "outcome": "accepted", "basis": basis}


class TheEffectiveResultsFollowTheSignatures(unittest.TestCase):
    """人最终接受的 = 会议结论 × 契约里的裁决；未决跟着一起传，派生只有一处。"""

    def results(self, notes: dict, *gates: dict) -> list[dict]:
        return meetings.effective_meeting_results(notes, contract(*gates))

    def test_an_unclear_topic_follows_the_chosen_ownership(self) -> None:
        topic = {"id": "T1", "ownership": "unclear", "ask": True, "changes": [LIMIT], "options": [
            {"key": "k1", "effect": {"ownership": "ours", "apply_changes": ["C1"]}},
            {"key": "k2", "effect": {"ownership": "not_ours", "apply_changes": ["C1"]}}]}
        notes = {KEY: {"topics": [topic]}}
        self.assertEqual(["C1"], [c["id"] for e in self.results(notes, signed(KEY, "T1", "k1"))
                                  for c in e["changes"]])
        self.assertEqual([], self.results(notes, signed(KEY, "T1", "k2")), "不属于本需求的也生效了")

    def test_an_unsigned_topic_does_not_take_effect(self) -> None:
        notes = {KEY: {"topics": [NOTES_TOPICS[1]]}}
        self.assertEqual([], self.results(notes), "没签就生效了")

    def test_the_chosen_option_decides_what_is_adopted_and_what_stays_open(self) -> None:
        notes = {KEY: {"topics": [NOTES_TOPICS[1]]}}
        adopted = self.results(notes, signed(KEY, "T2", "opt_a", "就用短信"))[0]
        self.assertEqual(["受理后短信通知"], [c["after"] for c in adopted["added"]])
        self.assertEqual([], adopted["open_points"], "落定了的遗留还留着")
        self.assertEqual({"key": "opt_a", "label": "按短信通知"}, adopted["chosen"])
        kept = self.results(notes, signed(KEY, "T2", "opt_b", "先不定"))[0]
        self.assertEqual([], kept["added"])
        self.assertEqual(["O1"], [o["id"] for o in kept["open_points"]], "拒绝变化时遗留丢了")

    def test_unasked_topics_wait_for_the_first_gate(self) -> None:
        notes = {KEY: {"topics": [NOTES_TOPICS[0]]}}
        self.assertEqual([], self.results(notes), "第一级表态之前就生效了")
        self.assertEqual(["C1"], [c["id"] for e in self.results(notes, shown(KEY))
                                  for c in e["changes"]])

    def test_only_the_chosen_option_decides_what_an_old_decision_becomes(self) -> None:
        old = {"id": "T1", "ownership": "ours", "ask": False, "changes": [LIMIT]}
        new = {"id": "T1", "ownership": "ours", "ask": True, "overturns": f"{OLD}/T1",
               "changes": [], "options": [
                   {"key": "k1", "effect": {"ownership": "ours", "supersedes": []}},
                   {"key": "k2", "effect": {"ownership": "ours", "supersedes": [f"{OLD}/T1"]}}]}
        notes = {OLD: {"topics": [old]}, KEY: {"topics": [new]}}
        refs = lambda *g: [e["ref"] for e in self.results(notes, shown(OLD), *g)]  # noqa: E731
        self.assertIn(f"{OLD}/T1", refs(), "新版本没裁决就撤销了旧决定")
        self.assertIn(f"{OLD}/T1", refs(signed(KEY, "T1", "k1")), "选了不替代的选项，旧决定却失效了")
        self.assertNotIn(f"{OLD}/T1", refs(signed(KEY, "T1", "k2")), "选了替代的选项，旧决定还在")

    def test_file_order_does_not_decide_which_meeting_wins(self) -> None:
        """两场会说得不一样而谁也没声明替代：两条都在，等人裁决，不按文件名自动覆盖。"""
        first = {"id": "T1", "ownership": "ours", "ask": False,
                 "changes": [{**LIMIT, "after": "上限五个"}]}
        later = {"id": "T1", "ownership": "ours", "ask": False,
                 "changes": [{**LIMIT, "id": "C2", "after": "上限八个"}]}
        notes = {OLD: {"topics": [first]}, KEY: {"topics": [later]}}
        adopted = [c["after"] for e in self.results(notes, shown(OLD, KEY)) for c in e["changes"]]
        self.assertEqual(["上限五个", "上限八个"], sorted(adopted, key=len), adopted)


class TheRefreshShowsChangesOpenPointsAndOriginals(MeetingCase):
    """`doc-refresh.md` 三段固定，引文取自阅读件、路径是真实文件。"""

    def refresh(self, *gates: dict, notes=None) -> str:
        docx = self.imported()
        key = self.read_meeting(docx, notes=notes,
                                topics=TOPICS_INDEX[:1] if notes else None)
        notes = meeting.read_notes(self.fr, [])
        bound = [{**g, **({"meeting": key} if g.get("gate") == "meeting" else {}),
                  **({"meetings": [key]} if g.get("gate") == "material_scope" else {})}
                 for g in gates]
        return meetings.render(
            self.fr, meetings.effective_meeting_results(notes, contract(*bound)))

    def test_the_three_sections_and_a_real_quote(self) -> None:
        text = self.refresh(shown(), signed("", "T2", "opt_b", "先不定"))
        for section in ("## 采纳的变化", "## 仍未决", "## 会议原结论及采纳情况"):
            self.assertIn(section, text)
        self.assertIn("上限五个，超出排队", text)
        self.assertIn("通知方式未定", text.split("## 仍未决", 1)[1], "保留的遗留没传下去")
        quoted = text.split("## 采纳的变化", 1)[1]
        self.assertIn("raw.md:L5-L6", quoted, "引用不是真实路径与行号")
        self.assertIn("上限先按五个来", quoted, "没给原话")
        self.assertIn("人选「维持待定」（opt_b）", text)

    def test_a_rejected_change_is_not_presented_as_accepted(self) -> None:
        text = self.refresh(shown(), signed("", "T2", "opt_b", "先不定"))
        adopted = text.split("## 采纳的变化", 1)[1].split("## 仍未决", 1)[0]
        self.assertNotIn("受理后短信通知", adopted, "没被选中的变化写进了采纳")

    def test_a_topic_without_changes_is_not_called_settled(self) -> None:
        text = self.refresh(shown(), notes=[{**NOTES_TOPICS[0], "changes": []}])
        tail = text.split("## 会议原结论及采纳情况", 1)[1]
        self.assertIn("没有引出文档变化", tail)
        self.assertNotIn("原文已确认", text, "没有变化被当成业务已收敛")


class TheFlowStopsOnceForTheMeeting(MeetingCase):
    """读会 → 出阅读件 → 与第一级同一轮摆给人 → 逐条裁决 → 有效结果写进 doc-refresh.md。"""

    def test_read_refresh_ask_decide(self) -> None:
        docx = self.imported()
        self.assertEqual(0, self.cli("story_flow.py", "round")[0])
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
        self.assertEqual([None, "opt_a"], [t.get("recommend") for t in state["meetings"]])

        ask = ("story_flow.py", "decide", "--gate", "meeting", "--meeting", key,
               "--item", "T2", "--basis", "就用短信")
        code, out, _ = self.cli(*ask, "--chosen", "不存在")
        self.assertEqual(1, code)
        self.assertIn("不在本次选项集里", out["error"])
        self.assertEqual(0, self.cli(*ask, "--chosen", "opt_a")[1] and 0)
        refresh = self.fr / "AR" / "story-src" / "doc-refresh.md"
        self.assertIn("人工补定，原话「就用短信」", refresh.read_text(encoding="utf-8"))
        self.assertNotIn("上限五个，超出排队", refresh.read_text(encoding="utf-8"),
                         "没问人的话题在第一级表态前生效了")
        self.assertEqual("await_gate:material_scope", self.status()["next"])

        (self.fr / "AR" / "story-src" / ".gate-options.json").write_text(json.dumps(
            {"gate": "material_scope", "options": [{"key": "supplied"}, {"key": "confirm_scope"}]}),
            encoding="utf-8")
        code, _, log = self.cli("story_flow.py", "decide", "--gate", "material_scope",
                                "--chosen", "confirm_scope", "--basis", "材料够了")
        self.assertEqual(0, code, log)
        self.assertIn("上限五个，超出排队", refresh.read_text(encoding="utf-8"))
        flow = json.loads((self.fr / "AR" / "story-src" / "story-flow.json").read_text(
            encoding="utf-8"))
        gates = flow["rounds"][-1]["gates"]
        self.assertEqual([key], gates[-1]["meetings"], "第一级没记下摆给人的会议版本")
        meeting_gate = next(g for g in gates if g["gate"] == "meeting")
        self.assertEqual({"key", "label"}, set(meeting_gate["options"][0]),
                         "关卡记录里多抄了一份 effect")

    def test_every_topic_shows_up_including_the_ones_that_are_not_ours(self) -> None:
        docx = self.imported()
        self.assertEqual(0, self.cli("story_flow.py", "round")[0])
        notes = [{**NOTES_TOPICS[0], "ownership": "not_ours"},
                 {**NOTES_TOPICS[1], "ownership": "unclear",
                  "ask_reason": "unclear_ownership",
                  "options": [{"key": "opt_a", "label": "算本需求的",
                               "effect": {"ownership": "ours", "apply_changes": [],
                                          "add_changes": [], "supersedes": []}},
                              {"key": "opt_b", "label": "不算本需求的",
                               "effect": {"ownership": "not_ours", "apply_changes": [],
                                          "add_changes": [], "supersedes": [],
                                          "keep_open": ["O1"]}}]}]
        self.read_meeting(docx, notes=notes)
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


if __name__ == "__main__":
    unittest.main()
