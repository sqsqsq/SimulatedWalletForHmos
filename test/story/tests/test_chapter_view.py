"""一章解析一次：`core/story/document.mjs` 的视图，与判据对它的消费。

判据各自切文时，同一章在一次 check 里会被切上七八遍，而每一处对「围栏里的算不算」
「小节到哪结束」都有自己的一份答案——首表误认与围栏样例顶替真小节都是从这里来的。
这一份锁两件事：**视图本身的语义**（原文不动、围栏不入正文、表知道自己在哪一节），
以及**一次 check 里每章只解析一次**。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from ext_workspace import link_harness_yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
EXT = REPO_ROOT / "doc" / "extensions"
DOCUMENT = EXT / "skills" / "story" / "scripts" / "core" / "story" / "document.mjs"
BUILD = EXT / "skills" / "story" / "scripts" / "core" / "story-build.mjs"
FIXTURE = (REPO_ROOT / "test" / "story" / "fixtures" / "failure-modes"
           / "R01-verdict-echo" / "good")
FEATURE = "REQ-DEMO"

CHAPTER = (
    "章首一段话。\n"
    "\n"
    "```mermaid\n"
    "flowchart TD\n"
    "  A --> B\n"
    "```\n"
    "\n"
    "### 甲节\n"
    "\n"
    "| 编号 | 说明 |\n"
    "|---|---|\n"
    "| AC-1 | 提交成功 |\n"
    "\n"
    "### 乙节的业务名更长\n"
    "\n"
    "正文。\n"
    "\n"
    "```markdown\n"
    "### 假节\n"
    "\n"
    "| 交付物 | 给谁 |\n"
    "|---|---|\n"
    "```\n"
    "\n"
    "结尾一句。\n")


def node_eval(script: str, *args: str) -> object:
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script, "--", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120, cwd=str(REPO_ROOT))
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


class ViewCase(unittest.TestCase):
    """两个取法：整章视图，以及按名字查一个小节拿到的正文与表。"""

    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")

    def view(self, text: str = CHAPTER) -> dict:
        return node_eval(
            "import {pathToFileURL} from 'node:url';"
            "const m = await import(pathToFileURL(process.argv[1]).href);"
            "const v = m.parseChapter(process.argv[2]);"
            "process.stdout.write(JSON.stringify({text: v.text, tables: v.tables,"
            "  sections: v.sections.map(s => s.name), fences: v.fences,"
            "  diagram: m.hasDiagram(v), 全章表: m.tablesIn(v)}));",
            str(DOCUMENT), text)

    def section(self, text: str, name: str) -> dict:
        return node_eval(
            "import {pathToFileURL} from 'node:url';"
            "const m = await import(pathToFileURL(process.argv[1]).href);"
            "const v = m.parseChapter(process.argv[2]);"
            "process.stdout.write(JSON.stringify({body: m.sectionBody(v, process.argv[3]),"
            "  tables: m.tablesIn(v, process.argv[3])}));",
            str(DOCUMENT), text, name)


class TheViewKeepsWhatJudgesNeed(ViewCase):
    def test_the_original_text_is_kept_byte_for_byte(self) -> None:
        """报错要指回原文：视图改写了原文，行号与引文就都对不上。"""
        self.assertEqual(CHAPTER, self.view()["text"])

    def test_fenced_content_is_not_structure(self) -> None:
        """围栏里的标题与表是被引用的样例：算进来的话，贴一段别处的示例就能顶掉
        本章真正缺的那一节。围栏**之后**的正文不能跟着被吞掉。
        """
        v = self.view()
        self.assertEqual(["甲节", "乙节的业务名更长"], v["sections"], "围栏里的标题成了小节")
        self.assertNotIn("交付物", json.dumps(v["tables"], ensure_ascii=False),
                         "围栏里的表算成了本章的表")
        self.assertIn("结尾一句。", self.section(CHAPTER, "乙节")["body"],
                      "围栏之后的正文被吞掉了")

    def test_a_table_belongs_to_the_section_it_sits_in(self) -> None:
        v = self.view()
        self.assertEqual([{"header": ["编号", "说明"], "line": 9}], v["tables"])
        self.assertEqual([["编号", "说明"]], self.section(CHAPTER, "甲节")["tables"])
        self.assertEqual([], self.section(CHAPTER, "乙节的业务名更长")["tables"],
                         "那一节在但没有表")
        self.assertIsNone(self.section(CHAPTER, "没有这一节")["tables"],
                          "那一节缺席与「有节没表」不是一回事")
        self.assertEqual([["编号", "说明"]], v["全章表"])

    def test_a_section_is_found_by_exact_then_containing_name(self) -> None:
        self.assertIn("AC-1", self.section(CHAPTER, "甲节")["body"])
        self.assertIsNotNone(self.section(CHAPTER, "乙节")["body"],
                             "合同给的是这一节讲什么，作者按业务命名")
        self.assertIsNone(self.section(CHAPTER, "没有这一节")["body"])

    def test_blank_lines_inside_a_section_are_kept(self) -> None:
        body = self.section(CHAPTER, "甲节")["body"]
        self.assertTrue(body.startswith(chr(10)), "小节正文的空行被吃掉了")

    def test_only_a_drawing_fence_counts_as_a_diagram(self) -> None:
        self.assertTrue(self.view()["diagram"])
        self.assertFalse(self.view('一段话。\n\n```json\n{"a": 1}\n```\n')["diagram"],
                         "贴一段数据不该顶掉这一章该画的那张图")

    def test_an_unclosed_fence_does_not_swallow_the_rest(self) -> None:
        v = self.view("一段话。\n\n```mermaid\nflowchart TD\n")
        self.assertEqual(1, len(v["fences"]), "没闭合的围栏也要看得见")
        self.assertTrue(v["diagram"])


class OneParsePerChapterPerRun(unittest.TestCase):
    """一次 check 里每章只解析一次——判据读同一份结果。

    数的办法是把**副本树**里的 `parseChapter` 记一笔：机制自己按相对位置找模块，
    所以副本跑起来与正本同一条路径，不必给生产代码加计数开关。
    """

    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        shutil.copytree(FIXTURE, self.root)      # 工程侧：夹具自己的清单与知识不动
        self.mech = Path(self._tmp.name) / "mech" / "doc" / "extensions"
        shutil.copytree(EXT, self.mech)          # 机制侧：副本按相对位置自己找模块
        link_harness_yaml(self.mech.parents[1])
        self.log = Path(self._tmp.name) / "parse.log"
        doc = (self.mech / "skills" / "story" / "scripts"
               / "core" / "story" / "document.mjs")
        text = doc.read_text(encoding="utf-8")
        text = text.replace(
            "export function parseChapter(text) {",
            "import * as __fs from 'node:fs';\n"
            "export function parseChapter(text) {\n"
            "  __fs.appendFileSync(process.env.PARSE_LOG, 'x');", 1)
        doc.write_text(text, encoding="utf-8")
        decisions = self.root / "doc" / "features" / FEATURE / "AR" / "story-src" / "decisions.json"
        if not decisions.exists():
            decisions.write_text('{"decisions": []}', encoding="utf-8")

    def test_each_chapter_is_parsed_once(self) -> None:
        build = self.mech / "skills" / "story" / "scripts" / "core" / "story-build.mjs"
        env = dict(**{k: v for k, v in __import__("os").environ.items()},
                   PARSE_LOG=str(self.log))
        proc = subprocess.run(
            ["node", str(build), "check", "--feature", FEATURE,
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, env=env)
        self.assertEqual(0, proc.returncode, (proc.stdout or "") + (proc.stderr or ""))
        count = len(self.log.read_text(encoding="utf-8")) if self.log.exists() else 0
        # 这份夹具里只有两章有正文（功能说明、附录），其余是「本需求不涉及。」空章；
        # 附录那一章一次 check 里被问十来次（五个小节、名字集合、spec 契约比对）。
        self.assertEqual(2, count,
                         f"解析了 {count} 次：每章一次的话应当是 2 次（有正文的那两章）")


class FencesCloseOnlyOnTheirOwnMarker(ViewCase):
    """围栏只能被**同种、不短于它**的标记关闭。

    一个反引号块里贴一段波浪号样例是常事；把任意围栏行都当关闭符，样例里的标题与表
    就会被算成本章的正文结构——贴一段别处的示例即可满足必要结构，后面的范围也跟着错位。
    """

    BT = "`" * 3
    TD = "~" * 3

    def test_a_different_kind_of_fence_does_not_close_the_block(self) -> None:
        v = self.view(chr(10).join([
            "章首一段。", "",
            self.BT + "text",
            self.TD + "markdown",
            "### 交付物", "",
            "| 交付物 | 给谁 | 做什么用 |", "|---|---|---|", "| a | b | c |",
            self.TD,
            self.BT, "",
            "后面的正文还要被认出来。", "",
            "### 真的交付物", "",
            "| 交付物 | 给谁 | 做什么用 |", "|---|---|---|", "| 说明 | 评审人 | 过目 |",
        ]))
        self.assertEqual(["真的交付物"], v["sections"], "样例里的标题成了本章小节")
        self.assertEqual(1, len(v["tables"]), "样例里的表算成了本章的表")

    def test_a_shorter_marker_of_the_same_kind_does_not_close_it(self) -> None:
        v = self.view(chr(10).join([
            "`" * 4, "### 假节", self.BT, "### 也在围栏里", "`" * 4, "", "### 真节",
        ]))
        self.assertEqual(["真节"], v["sections"])

    def test_structure_after_a_real_close_is_seen_again(self) -> None:
        v = self.view(chr(10).join([
            self.BT + "json", '{"a": 1}', self.BT, "", "### 真节", "",
            "| 编号 | 可观察的通过条件 |", "|---|---|", "| AC-1 | 显示编号 |",
        ]))
        self.assertEqual(["真节"], v["sections"])
        self.assertEqual([["编号", "可观察的通过条件"]], v["全章表"])
        self.assertFalse(v["diagram"], "数据围栏不是图")


class SameNameSectionsKeepTheirOwnTables(ViewCase):
    """两个同名小节各管自己的表：按名字记归属，后一节的表会被算给前一节。

    形状是第一个「交付物」只有一句话、第二个才有完整表：查正文得到第一节，查表却拿到
    第二节的——缺表的那一节因此通过，而别的消费者读到的还是缺表的那一份。
    """

    def test_the_body_and_the_tables_come_from_the_same_section(self) -> None:
        text = chr(10).join([
            "### 交付物", "", "前节无表。", "",
            "### 交付物", "",
            "| 交付物 | 给谁 | 做什么用 |", "|---|---|---|", "| 说明 | 评审人 | 过目 |",
        ])
        got = self.section(text, "交付物")
        self.assertIn("前节无表。", got["body"])
        self.assertEqual([], got["tables"], "拿到的是后一个同名小节的表")

    def test_another_section_still_has_its_own(self) -> None:
        """范围限定不等于只认第一个节：别的节自己那张表照样查得到。"""
        text = chr(10).join([
            "### 交付物", "", "前节无表。", "",
            "### 交付物与接收方", "",
            "| 交付物 | 给谁 | 做什么用 |", "|---|---|---|", "| 说明 | 评审人 | 过目 |",
        ])
        self.assertEqual([["交付物", "给谁", "做什么用"]],
                         self.section(text, "交付物与接收方")["tables"])




class SectionShapesAreChecked(ViewCase):
    """同一章里同名小节两处、小节标题下什么都没有：章提交与全篇 check 同一条判据点名。"""

    CHAPTER = chr(10).join([
        "章首一段。", "",
        "### 取件提醒", "",
        "### 取件提醒", "",
        "到柜后提醒取件。", "",
        "### 状态流转", "",
        "```mermaid", "stateDiagram-v2", "  A --> B", "```", "",
        "```markdown", "### 样例里的节", "### 样例里的节", "```", "",
        "### 结尾", "",
        "收尾一句。",
    ])

    def problems(self, text: str) -> list[str]:
        chapter = DOCUMENT.parent / "chapter.mjs"
        return node_eval(
            "import {pathToFileURL} from 'node:url';"
            "const m = await import(pathToFileURL(process.argv[1]).href);"
            "const ctx = {storyPath: process.argv[3], idShapes: {drop: []}};"
            "process.stdout.write(JSON.stringify("
            "  m.chapterProblems(ctx, {title: '功能说明'}, process.argv[2])));",
            str(chapter), text, str(REPO_ROOT / "AR" / "story.md"))

    def test_a_repeated_and_an_empty_section_are_named(self) -> None:
        got = self.problems(self.CHAPTER)
        repeated = [p for p in got if "两个「取件提醒」" in p]
        empty = [p for p in got if "「取件提醒」小节下面没有正文" in p]
        self.assertEqual(1, len(repeated), got)
        self.assertEqual(1, len(empty), got)
        self.assertIn("合成一节", repeated[0])
        self.assertIn("删掉这个标题", empty[0])

    def test_a_diagram_only_section_and_fenced_samples_pass(self) -> None:
        got = self.problems(self.CHAPTER)
        self.assertFalse([p for p in got if "状态流转" in p or "样例里的节" in p or "结尾" in p],
                         got)


class OnlyACleanMarkerLineCloses(ViewCase):
    """关闭行的三个条件：同种标记、不短于开启标记、标记之后到行末只有空白。

    开启行与关闭行不是同一种语法。把带语言信息的那一行（一段样例的开启行）当成关闭符，
    两件坏事同时发生：样例里的标题与表泄漏成本章结构，真正的关闭符又被当成新的开启，
    它后面的真正文跟着丢掉。
    """

    BT = "`" * 3

    def sample_block(self, second: str) -> str:
        """外层是一段 text 围栏，里面贴一段样例：`second` 是样例的那一行。"""
        return chr(10).join([
            self.BT + "text",
            second,
            "### 样例里的节", "",
            "| 甲 | 乙 |", "|---|---|",
            self.BT,
            "### 真的节", "",
            "| 编号 | 可观察的通过条件 |", "|---|---|", "| AC-1 | 显示编号 |",
        ])

    def test_a_marker_with_trailing_content_does_not_close(self) -> None:
        for second in (self.BT + "markdown", self.BT + " 说明", self.BT + ".",
                       self.BT + "text 再来一段"):
            with self.subTest(second=second):
                v = self.view(self.sample_block(second))
                self.assertEqual(["真的节"], v["sections"],
                                 f"「{second}」被当成了关闭行，样例里的标题泄漏进结构")
                self.assertEqual([["编号", "可观察的通过条件"]], v["全章表"],
                                 "样例里的表算进来了，或真正文的表丢了")

    def test_a_bare_marker_or_only_whitespace_closes(self) -> None:
        for closer in (self.BT, self.BT + "   ", self.BT + "\t", "`" * 5):
            with self.subTest(closer=closer):
                v = self.view(chr(10).join([
                    self.BT + "text", "样例正文。", closer, "", "### 真的节", "",
                    "| 编号 | 可观察的通过条件 |", "|---|---|", "| AC-1 | 显示编号 |",
                ]))
                self.assertEqual(["真的节"], v["sections"], f"「{closer}」没关上围栏")
                self.assertEqual([["编号", "可观察的通过条件"]], v["全章表"])

    def test_a_shorter_or_different_marker_still_does_not_close(self) -> None:
        for closer in ("~" * 3, "`" * 2):
            with self.subTest(closer=closer):
                v = self.view(chr(10).join([
                    "`" * 4, "### 样例里的节", closer, "### 也在围栏里",
                    "`" * 4, "", "### 真的节",
                ]))
                self.assertEqual(["真的节"], v["sections"], f"「{closer}」关上了不该关的围栏")


class OneFenceScannerForEveryConsumer(unittest.TestCase):
    """围栏的开闭判断**只有一处**：`fenceRanges`。别处一律从它派生。

    从前三份（切章、区间定位、重编号）后来两份（`parseChapter` 与掩码）。两份在样例上
    一致不等于只有一份实现：以后改一个边界条件仍要改两处，而漏改的那一处会静默切错。
    这一组按**实际消费者**断言，不数 helper。
    """

    #: 四种「关不上」：不同种、比开启短、标记后还有字、压根没有关闭行
    OPEN = "`" * 4
    CASES = {
        "不同种": "~" * 4,
        "更短": "`" * 3,
        "尾随内容": "`" * 4 + " json",
        "没有关闭行": None,
    }

    def consumers(self, chapter_body: str) -> dict:
        """一次跑完四个消费者：章视图、切章、区间定位、重编号。"""
        src = rf"""
        import {{ parseChapter, storySections, chapterSpan, renumberStory, fencedLines }}
          from {json.dumps(DOCUMENT.resolve().as_uri())};
        const CONTRACT = JSON.parse(process.argv[3]);
        const body = process.argv[2];
        const story = '# AR1 夹具\n\n## 背景\n\n' + body + '\n\n## 术语\n\n正文。\n';
        const view = parseChapter(body);
        process.stdout.write(JSON.stringify({{
          sections: view.sections.map(s => s.raw),
          tables: view.tables.length,
          closed: view.fences.map(f => f.closed),
          chapters: storySections(story).map(s => s.raw),
          spanEndsAtNext: (() => {{
            const at = chapterSpan(story, '背景');
            return at ? story.slice(at.start, at.end).includes('## 术语') : null;
          }})(),
          numbered: renumberStory(story, CONTRACT.chapters, CONTRACT.heading_counters)
            .split('\\n').filter(l => /^###\\s+\\d/.test(l)),
          fenced: [...fencedLines(body)].length,
        }}));
        """
        contract = (EXT / "skills" / "story" / "contracts" / "story-chapters.json"
                    ).read_text(encoding="utf-8")
        proc = subprocess.run(["node", "--input-type=module", "-e", src, "x",
                               chapter_body, contract],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=60)
        self.assertEqual(0, proc.returncode, proc.stderr[-800:])
        return json.loads(proc.stdout)

    def body_for(self, closer) -> str:
        rows = [self.OPEN, "### 样例里的节", "## 样例里的章", "| 甲 | 乙 |", "|---|---|", "| 1 | 2 |"]
        if closer is not None:
            rows.append(closer)
        rows += ["### 后面的真节", "", "本节正文。"]
        return "\n".join(rows)

    def test_an_unclosable_marker_keeps_everything_inside_for_all_consumers(self) -> None:
        """关不上就一路到末行——**四个消费者对同一段文字给同一个答案**。

        「后半篇被吞掉」本身不是这里要修的事：它是围栏没关上的必然后果，
        由章提交那一条「围栏没有闭合」拒绝（见 test_story_build）。这里锁的是一致：
        不能出现「切章认为吞了、定位认为没吞」这种两份实现各说一套。
        """
        for name, closer in self.CASES.items():
            with self.subTest(case=name):
                out = self.consumers(self.body_for(closer))
                self.assertEqual([], out["sections"], "围栏里的 H3 顶替了真小节")
                self.assertEqual(0, out["tables"], "围栏里的表被算成本章的表")
                self.assertEqual([False], out["closed"], "关不上的围栏被当成关上了")
                self.assertEqual(["背景"], out["chapters"],
                                 "切章与视图对「后半篇在围栏里」给出了不同答案")
                self.assertTrue(out["spanEndsAtNext"], "定位与切章对不上")
                self.assertEqual([], out["numbered"], "围栏里的标题被编了号")

    def test_a_legal_closer_lets_the_real_structure_through(self) -> None:
        out = self.consumers(self.body_for(self.OPEN))
        self.assertEqual(["后面的真节"], out["sections"])
        self.assertEqual(["背景", "术语"], out["chapters"])
        self.assertEqual(0, out["tables"], "围栏里的表仍不算本章的")
        # 编号只按位置铺，本用例不核它铺到第几号；这里只核**围栏里那一行没被铺上号**。
        self.assertNotIn("样例里的节", "".join(out["numbered"]))

    def test_the_open_close_rule_exists_in_exactly_one_place(self) -> None:
        """源码核：扩展里每个模块（成文侧与 hooks）都从 document.mjs 拿围栏，没有第二份开闭或开启识别。"""
        text = DOCUMENT.read_text(encoding="utf-8")
        code = [l for l in text.split("\n") if not l.strip().startswith(("//", "*", "/*"))]
        self.assertEqual(1, "\n".join(code).count("CLOSING.test("), "关闭行判断不止一处")
        self.assertEqual(1, len([l for l in code if "(`{3,}|~{3,})" in l]), "围栏开启的识别不止一处")
        own_scanner = re.compile(r"/\^\\s\*\(?`{3}|/\^\[ \\t\]\*`{3}|\(\?:`{3}\|~{3}\)|`{3}\|~{3}")
        extension = DOCUMENT.parents[5]          # doc/extensions：成文侧与 hooks 一起核
        for other in sorted(extension.rglob("*.mjs")):
            if other == DOCUMENT or "node_modules" in other.parts:
                continue
            body = other.read_text(encoding="utf-8")
            self.assertIsNone(own_scanner.search(body), other.name + " 自己又写了一份围栏识别")
            self.assertNotIn("inFence", body, other.name + " 自己又在逐行翻转围栏状态")


class OneRuleOnEveryPath(unittest.TestCase):
    """同一段带围栏样例的文字，语言红线、图身份、附录投影、材料清单四条路径给同一个答案。

    样例里的标题、表、图与文档坐标都是被引用的例子：四反引号里嵌三反引号、`~~~` 围栏、
    围栏里的 `## ` 标题，哪一条路径都不该把它们当成真的。
    """

    OUTER = "`" * 4

    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")

    def run_js(self, body: str, *argv: str):
        script = ("import {pathToFileURL} from 'node:url';"
                  "const at = (f) => pathToFileURL(" + json.dumps(str(DOCUMENT.parent)) + " + '/' + f).href;"
                  + body)
        proc = subprocess.run(["node", "--input-type=module", "-e", script, "--", *argv],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(0, proc.returncode, proc.stderr[-800:])
        return json.loads(proc.stdout)

    def test_the_redline_skips_quoted_samples(self) -> None:
        text = "\n".join([
            "# AR1 夹具", "", "## 背景", "",
            self.OUTER + "markdown", "见 spec §5.1。", "```mermaid", "flowchart TD", "```", "## 样例章", self.OUTER, "",
            "~~~text", "口径以 prd.md 为准。", "~~~", "",
            "正文里写着 prd.md。",
        ])
        hits = self.run_js("const m = await import(at('language.mjs'));"
                           "process.stdout.write(JSON.stringify(m.scanLanguageRedline(process.argv[1],"
                           " {kinds: [{kind: 'doc_coordinate', scope: 'all'}]}).map(h => h.line)));", text)
        self.assertEqual([len(text.split("\n"))], hits, "围栏里的样例被当成了正文")

    def test_diagram_identity_skips_quoted_samples(self) -> None:
        text = "\n".join([
            "## 5. 业务流程", "",
            self.OUTER + "markdown", "### 9.9 样例节", "```mermaid", "flowchart TD", "  X --> Y", "```", self.OUTER, "",
            "### 5.2 真节", "",
            "~~~mermaid", "flowchart TD", "  A --> B", "~~~",
        ])
        ids = self.run_js("const m = await import(at('images.mjs'));"
                          "process.stdout.write(JSON.stringify(m.diagramsOf(process.argv[1]).map(d => d.id)));", text)
        self.assertEqual(["§5.2 #1"], ids)

    def test_the_appendix_projection_reads_the_real_section(self) -> None:
        spec = "\n".join([
            "in_scope_modules:", "  - 甲模块", "", "~~~markdown",
            "## 0. 术语映射表", "", "| 术语 | 权威模块 | 解释 |", "|---|---|---|", "| 样例词 | 甲模块 | 样例解释 |",
            "~~~", "",
            "## 0. 术语映射表", "", "| 术语 | 权威模块 | 解释 |", "|---|---|---|", "| 真词 | 甲模块 | 真解释 |", "",
        ])
        terms = self.run_js("const m = await import(at('appendix.mjs'));"
                            "process.stdout.write(JSON.stringify(m.specTerms(process.argv[1])));", spec)
        self.assertEqual([["真词", "真解释"]], terms)

    def test_the_material_list_is_located_past_quoted_headings(self) -> None:
        story = "\n".join([
            "# AR1 夹具", "", "## 背景", "", "~~~markdown", "## 附录", "### 材料清单", "~~~", "",
            "## 附录", "", self.OUTER, "### 材料清单", "- 样例", self.OUTER, "",
            "### 材料清单", "", "- 真材料",
        ])
        span = self.run_js("const m = await import(at('document.mjs'));"
                           "process.stdout.write(JSON.stringify(m.subsectionSpan(process.argv[1], '附录', '材料清单')));",
                           story)
        self.assertEqual("- 真材料", story.split("\n")[span["start"] + 1])

    def test_a_name_matching_two_sections_is_named_not_guessed(self) -> None:
        chapter = "\n".join(["### 参与方与分工", "", "甲。", "", "### 参与方不在本轮", "", "乙。"])
        got = self.run_js(
            "const d = await import(at('document.mjs'));"
            "const c = await import(at('chapter-contract.mjs'));"
            "const v = d.parseChapter(process.argv[1]);"
            "process.stdout.write(JSON.stringify({body: d.sectionBody(v, '参与方'),"
            " problems: c.chapterStructureProblems({title: '业务方案', structure: {h3: [{title: '参与方'}]}}, v)}));",
            chapter)
        self.assertIsNone(got["body"], "两个都像时取了第一个")
        self.assertEqual(1, len(got["problems"]), got)
        self.assertIn("同时像「参与方与分工」、「参与方不在本轮」", got["problems"][0])
        exact = self.run_js("const d = await import(at('document.mjs'));"
                            "process.stdout.write(JSON.stringify(d.sectionBody(d.parseChapter(process.argv[1]), '参与方与分工')));",
                            chapter)
        self.assertIn("甲", exact, "精确名仍要直接命中")

if __name__ == "__main__":
    unittest.main()
