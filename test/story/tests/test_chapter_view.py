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


class TheViewKeepsWhatJudgesNeed(unittest.TestCase):
    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")

    def view(self, text: str = CHAPTER) -> dict:
        return node_eval(
            "import {pathToFileURL} from 'node:url';"
            "const m = await import(pathToFileURL(process.argv[1]).href);"
            "const v = m.parseChapter(process.argv[2]);"
            "process.stdout.write(JSON.stringify({text: v.text,"
            "  sections: v.sections.map(s => s.name), tables: v.tables,"
            "  fences: v.fences, diagram: m.hasDiagram(v),"
            "  甲: m.sectionBody(v, '甲节'), 乙: m.sectionBody(v, '乙节'),"
            "  缺: m.sectionBody(v, '没有这一节'),"
            "  甲表: m.tablesIn(v, '甲节'), 乙表: m.tablesIn(v, '乙节的业务名更长'),"
            "  缺表: m.tablesIn(v, '没有这一节'), 全章表: m.tablesIn(v)}));",
            str(DOCUMENT), text)

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
        self.assertIn("结尾一句。", v["乙"], "围栏之后的正文被吞掉了")

    def test_a_table_knows_which_section_it_sits_in(self) -> None:
        v = self.view()
        self.assertEqual([{"header": ["编号", "说明"], "section": "甲节", "line": 9}],
                         v["tables"])
        self.assertEqual([["编号", "说明"]], v["甲表"])
        self.assertEqual([], v["乙表"], "那一节在但没有表")
        self.assertIsNone(v["缺表"], "那一节缺席与「有节没表」不是一回事")
        self.assertEqual([["编号", "说明"]], v["全章表"])

    def test_a_section_is_found_by_exact_then_containing_name(self) -> None:
        v = self.view()
        self.assertIn("AC-1", v["甲"])
        self.assertIsNotNone(v["乙"], "合同给的是这一节讲什么，作者按业务命名")
        self.assertIsNone(v["缺"])

    def test_blank_lines_inside_a_section_are_kept(self) -> None:
        v = self.view()
        self.assertTrue(v["甲"].startswith("\n"), "小节正文的空行被吃掉了")

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
