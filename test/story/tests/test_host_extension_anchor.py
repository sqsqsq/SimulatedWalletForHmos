"""宿主扩展章挂在 framework 预留的锚点下。

锁住：
  ① spec：扩展内容是「9. 宿主扩展治理项」的下一级小节（技术契约在走 /story 时必有），附录是全文最后一章；
     扩展小节写成锚点外的独立二级章、附录夹在正文中间，都报出现在的位置；
  ② plan：知识决策是「9. 宿主扩展」的 9.1，下挂设计模式选型、规约义务、项目知识影响；
     写在锚点外、缺锚点、缺一节，各报各的；
  ③ 两份模板自身满足上面的结构：模板与门禁同一份形态。
"""
from __future__ import annotations

import json
import unittest

import test_neutral_knowledge as nk
from test_indicator_reporting import js

SPEC_GATE = nk.EXT / "hooks" / "spec" / "post_check.mjs"
PLAN_GATE = nk.EXT / "hooks" / "plan" / "post_check.mjs"
TEMPLATES = nk.EXT / "skills" / "story" / "templates"

ANCHORED_SPEC = """# 需求 spec

## 8. 验收标准

略。

## 9. 宿主扩展治理项

| 扩展项 | 是否涉及 | 承载位置 |
|---|---|---|
| 技术契约 | 是 | 9.1 |

### 9.1 技术契约

#### 9.1.1 端云接口

不涉及：复用既有接口。

### 9.2 规约约束要求

<!-- 生成区 -->

### 9.3 设计模式候选登记

<!-- 生成区 -->

## 附录

### A. 术语表

略。
"""

#: 锚点空着、扩展内容另起三章、附录夹在中间——实跑里出现过的排法。
DETACHED_SPEC = """# 需求 spec

## 8. 验收标准

略。

## 宿主扩展治理项

略。

## 附录

略。

## 9. 技术契约

### 9.1 端云接口

不涉及：复用既有接口。

## 10. 规约约束要求

<!-- 生成区 -->

## 11. 设计模式候选登记

<!-- 生成区 -->
"""

ANCHORED_PLAN = """# 计划

## 8. spec 功能映射表

略。

## 9. 宿主扩展

### 9.1 知识决策（设计输入）

#### 9.1.1 设计模式选型

本需求不涉及：无候选。

#### 9.1.2 规约义务

略。

#### 9.1.3 项目知识影响

略。
"""


def spec_problems(text: str, is_story: bool = True) -> list[str]:
    return js(SPEC_GATE, f"m.hostAnchorProblems({json.dumps(text.split(chr(10)))}, {json.dumps(is_story)})")


def plan_problems(text: str) -> list[str]:
    return js(PLAN_GATE, f"m.hostExtensionProblems({json.dumps(text)})")


class TheSpecExtensionHangsUnderTheAnchor(unittest.TestCase):
    """①"""

    def test_the_anchored_layout_passes(self) -> None:
        self.assertEqual([], spec_problems(ANCHORED_SPEC))

    def test_detached_chapters_and_a_middle_appendix_are_each_reported(self) -> None:
        got = "\n".join(spec_problems(DETACHED_SPEC))
        for name, now in (("技术契约", "## 9. 技术契约"), ("规约约束要求", "## 10. 规约约束要求"),
                          ("设计模式候选登记", "## 11. 设计模式候选登记")):
            with self.subTest(name=name):
                self.assertIn(f"「{name}」要写成「9. 宿主扩展治理项」的下一级小节", got)
                self.assertIn(now, got, "没说出现在写在哪")
        self.assertIn("附录要是全文最后一章", got)

    def test_a_missing_anchor_names_what_goes_under_it(self) -> None:
        text = ANCHORED_SPEC.replace("## 9. 宿主扩展治理项", "## 9. 扩展")
        got = "\n".join(spec_problems(text))
        self.assertIn("缺「9. 宿主扩展治理项」章", got)
        self.assertIn("「技术契约」", got)

    def test_the_contract_section_is_asked_only_on_the_story_chain(self) -> None:
        """没走 /story 的需求不写技术契约：锚点只挂 9.2、9.3 也成立。"""
        text = ANCHORED_SPEC.replace("### 9.1 技术契约\n\n#### 9.1.1 端云接口\n\n不涉及：复用既有接口。\n\n", "")
        self.assertEqual([], spec_problems(text, is_story=False))

    def test_a_subsection_one_level_too_deep_is_reported(self) -> None:
        text = ANCHORED_SPEC.replace("### 9.2 规约约束要求", "#### 9.2 规约约束要求")
        self.assertIn("「规约约束要求」要写成", "\n".join(spec_problems(text)))


class ThePlanKnowledgeDecisionIsAnchorSection(unittest.TestCase):
    """②"""

    def test_the_anchored_layout_passes(self) -> None:
        self.assertEqual([], plan_problems(ANCHORED_PLAN))

    def test_a_decision_chapter_outside_the_anchor_is_placed(self) -> None:
        text = ("# 计划\n\n## 知识决策（设计输入）\n\n### 设计模式选型\n\n略。\n\n"
                "## 1. 模块架构图\n\n略。\n\n## 9. 宿主扩展\n\n### 9.2 埋点\n\n略。\n")
        got = plan_problems(text)
        self.assertEqual(1, len(got), got)
        self.assertIn("要写成「9. 宿主扩展」的下一级小节 9.1——现在是「## 知识决策（设计输入）」", got[0])

    def test_no_anchor_is_one_problem(self) -> None:
        got = plan_problems("# 计划\n\n## 1. 模块架构图\n\n略。\n")
        self.assertEqual(1, len(got), got)
        self.assertIn("plan.md 缺「9. 宿主扩展」章", got[0])

    def test_each_missing_part_is_named(self) -> None:
        text = ANCHORED_PLAN.replace("#### 9.1.2 规约义务\n\n略。\n\n", "").replace("#### 9.1.3 项目知识影响", "#### 9.1.3 其它")
        got = "\n".join(plan_problems(text))
        self.assertIn("下缺「规约义务」一节", got)
        self.assertIn("下缺「项目知识影响」一节", got)
        self.assertNotIn("设计模式选型", got)


class TheTemplatesHaveTheShapeTheGatesCheck(unittest.TestCase):
    """③ 模板照抄出来的结构，门禁判过。"""

    @staticmethod
    def headings(path) -> str:
        """模板只留标题行：注释里的说明与样例表不参与结构。"""
        lines = path.read_text(encoding="utf-8").split("\n")
        return "\n\n".join(line for line in lines if line.startswith("#"))

    def test_the_spec_template(self) -> None:
        text = "# 需求 spec\n\n## 8. 验收标准\n\n" + self.headings(TEMPLATES / "spec-sections.md") + "\n\n## 附录\n"
        self.assertEqual([], spec_problems(text))

    def test_the_plan_template(self) -> None:
        text = "# 计划\n\n" + self.headings(TEMPLATES / "plan-sections.md")
        self.assertEqual([], plan_problems(text))
        for name in ("#### 9.2.1 共同约定", "#### 9.2.2 逐点实现", "#### 9.2.3 待登记与缺依据"):
            with self.subTest(name=name):
                self.assertIn(name, text, "plan 9.2 埋点按共同约定、逐点实现、待登记三节组织")


if __name__ == "__main__":
    unittest.main()
