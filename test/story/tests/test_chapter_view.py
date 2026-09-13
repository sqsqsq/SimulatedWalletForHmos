"""一章解析一次：`core/story/document.mjs` 的视图，与判据对它的消费。

判据各自切文时，同一章在一次 check 里会被切上七八遍，而每一处对「围栏里的算不算」
「小节到哪结束」都有自己的一份答案——首表误认与围栏样例顶替真小节都是从这里来的。
这一份锁两件事：**视图本身的语义**（原文不动、围栏不入正文、表知道自己在哪一节），
以及**一次 check 里每章只解析一次**。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
EXT = REPO_ROOT / "doc" / "extensions"
DOCUMENT = EXT / "skills" / "story" / "scripts" / "core" / "story" / "document.mjs"
BUILD = EXT / "skills" / "story" / "scripts" / "core" / "story-build.mjs"
FIXTURE = (REPO_ROOT / "test" / "story" / "fixtures" / "failure-modes"
           / "R01-verdict-echo" / "good")
FEATURE = "AR90001"

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


if __name__ == "__main__":
    unittest.main()
