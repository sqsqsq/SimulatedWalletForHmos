"""CU 文档的本文编号与带号引用 —— 只核文档自己写的号与自己的标题对不对得上，不定一套固定章号。

锁住：
  ① 带号子节以所属带号父节的号开头，各层都核；同一层两个标题同号报出；
  ② 不编号的章（Scope、宿主扩展章、附录）不造号，它下面带号的子节不按它核；序号不连续、不从 1 开始都合法；
     围栏里的标题不算；
  ③ 表里「号. 章名」的引用，号与章名指本文同一个二级标题；只写章名、写链接、表头没有这一列的不判。
spec / plan 真实 post_check 的消费在 test_cu_knowledge_chain。
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from ext_workspace import DEV_EXT

MODULE = DEV_EXT / "hooks" / "shared" / "chapters.mjs"

DRIVER = """
import { pathToFileURL } from 'node:url';
const [modulePath, fn, ...args] = process.argv.slice(2);
const mod = await import(pathToFileURL(modulePath).href);
process.stdout.write(JSON.stringify(mod[fn](...JSON.parse(args[0]))));
"""

#: 依当前 Framework 模板的形态：0 起的术语章、无号的 Scope、宿主扩展章与附录
DOC = """# 规格

## 0. 术语映射表

## 1. 功能概述

## Scope 声明

### Scope 模块清单

## 2. 目标用户与使用场景

### 2.1 目标用户

### 2.2 使用场景

## 4. 页面描述

### 4.1 页面总览

#### 区域 1: 顶部

#### 4.1.1 状态

## 宿主扩展治理项

### 规约

## 附录

### A. 术语表
"""


def call(fn: str, *args):
    with tempfile.TemporaryDirectory() as d:
        driver = Path(d) / "drive.mjs"
        driver.write_text(DRIVER, encoding="utf-8")
        r = subprocess.run(["node", str(driver), str(MODULE), fn, json.dumps(args, ensure_ascii=False)],
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr[-600:]
    return json.loads(r.stdout)


class NumberedChildrenFollowTheirParent(unittest.TestCase):
    def test_free_and_unnumbered_chapters_pass(self) -> None:
        self.assertEqual([], call("chapterNumberProblems", DOC))

    def test_a_child_under_the_wrong_parent_is_named_at_every_level(self) -> None:
        got = call("chapterNumberProblems", DOC.replace("### 2.2 使用场景", "### 3.2 使用场景")
                   .replace("#### 4.1.1 状态", "#### 4.2.1 状态"))
        self.assertEqual(2, len(got), got)
        self.assertIn("「### 3.2 使用场景」挂在「## 2. 目标用户与使用场景」下，号却是 3.2", got[0])
        self.assertIn("「#### 4.2.1 状态」挂在「### 4.1 页面总览」下，号却是 4.2.1", got[1])

    def test_children_of_an_unnumbered_chapter_are_not_renumbered(self) -> None:
        doc = DOC.replace("### Scope 模块清单", "### 7.1 模块清单")
        self.assertEqual([], call("chapterNumberProblems", doc))

    def test_the_same_number_twice_on_one_level_is_ambiguous(self) -> None:
        got = call("chapterNumberProblems", DOC.replace("## 4. 页面描述", "## 2. 页面描述"))
        self.assertTrue(any("「## 2. 页面描述」与第" in p and "同号" in p for p in got), got)

    def test_headings_inside_a_fence_do_not_count(self) -> None:
        doc = DOC + "\n```markdown\n## 2. 示例\n### 9.9 示例子节\n```\n"
        self.assertEqual([], call("chapterNumberProblems", doc))


class NumberedReferencesPointAtTheirOwnChapter(unittest.TestCase):
    PLAN = ("## 范围声明\n\n| 条目 | 承载设计章 |\n|---|---|\n| 甲 | 1. 架构（入口） |\n| 乙 | 2. 架构 |\n"
            "| 丙 | [架构](#1-架构) |\n| 丁 | 数据 |\n| 戊 | 2. 数据存储 |\n\n## 1. 架构\n\n## 2. 数据\n")

    def test_only_mismatched_numbered_references_are_named(self) -> None:
        got = call("chapterRefProblems", self.PLAN, "承载设计章")
        self.assertEqual(["「承载设计章」列的「2. 架构」对不上本文的章：「架构」在本文是第 1 章——带号引用的号与章名指本文同一个二级标题",
                          "「承载设计章」列的「2. 数据存储」对不上本文的章：本文第 2 章是「数据」——带号引用的号与章名指本文同一个二级标题"],
                         got, "名称前缀相同不能算指到同一章")

    def test_a_table_without_the_column_has_no_reference_duty(self) -> None:
        self.assertEqual([], call("chapterRefProblems", self.PLAN.replace("承载设计章", "spec章节"), "承载设计章"))


if __name__ == "__main__":
    unittest.main()
