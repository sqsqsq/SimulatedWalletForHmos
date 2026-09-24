"""spec / plan 的扩展门禁一轮报全：判据按数据前置分组，能判的组一次全判，缺前置的组说明缺什么。

上一轮实跑里，作者修完一类才看得见下一类——`knowledgeExitProblems` 缺章就 return、判断不成立就
return、契约读失败整体 return，同一个 check id 洋葱式 FAIL 八轮。这里锁的是：互不依赖的问题同轮同现；
真有依赖的（判断不成立时不核投影、契约读不出时不核义务）以 skipped 写明前置，而不是让别的组陪着沉默。
"""
from __future__ import annotations

import unittest

import test_knowledge_protocol as kp


class SpecProblemsShowUpTogether(kp.ProtocolCase):
    """spec：章节、知识判断、acceptance 桥接、投影四组各按自己的前置判。"""

    def acceptance_with(self, *extra: str) -> None:
        """夹具判了 NEU-01/02/03 三条命中：桥三条都有，`extra` 再多桥几条。"""
        rules = ["NEU-01", "NEU-02", "NEU-03", *extra]
        rows = "".join(f"  - id: AC-{i + 1}\n    knowledge_rule: {r}\n    description: 桥\n"
                       for i, r in enumerate(rules))
        (self.feature_root / "acceptance.yaml").write_text("criteria:\n" + rows, encoding="utf-8")

    def drop_heading(self, heading: str) -> None:
        text = self.spec_path.read_text(encoding="utf-8")
        self.assertIn(heading, text)
        self.spec_path.write_text(text.replace(heading, "", 1), encoding="utf-8")

    def test_three_independent_problems_are_named_in_one_run(self) -> None:
        """缺候选章（章节组）、编号不在册（判断组）、桥指向没要求的条目（桥接组）——一次全出。"""
        self.judged()
        self.drop_heading("## 11. 设计模式候选登记")
        self.write_use(neutral=kp.judgement() + "\n  - id: NEU-99\n    applicable: false\n    reason: 没有这一条")
        self.acceptance_with("NEU-04")
        message = self.hook("spec")
        self.assertIn("缺「设计模式候选登记」章", message)
        self.assertIn("NEU-99", message, "编号不在册没有与章节问题同轮出现")
        self.assertIn("指向了 spec 里没有要求的条目", message)
        self.assertIn("【", message, "报错没有按组分节")
        self.assertIn("先修它们再核投影", message, "投影组该说明它为什么没跑")

    def test_a_missing_exit_chapter_no_longer_hides_the_bridge(self) -> None:
        """缺「规约约束要求」章曾经直接 return：桥接问题要等作者补完章才第一次露面。"""
        self.judged()
        self.drop_heading("## 10. 规约约束要求")
        self.acceptance_with("NEU-04")
        message = self.hook("spec")
        self.assertIn("缺「规约约束要求」章", message)
        self.assertIn("指向了 spec 里没有要求的条目", message, "章缺失屏蔽了桥接组")
        self.assertIn("投影区不存在", message)

    def test_a_clean_spec_passes(self) -> None:
        self.judged()
        self.acceptance_with()
        # 中性工程没配 profile：没有问题，只如实记章号那一条未执行
        message = self.hook("spec")
        self.assertTrue(message.startswith("扩展门禁有 1 条判据未执行："), message)
        self.assertIn("spec 主章号（framework.config.json 没有配 project_profile.name", message)


class PlanProblemsShowUpTogether(kp.ProtocolCase):
    """plan：章节位置、契约形状、每条 must、集合一致、模式五组。"""

    def write_plan(self, decision_first: bool) -> None:
        decision = "## 知识决策（设计输入）\n\n### 设计模式选型\n\n" \
            "| 适用单元 | 候选 | 选型 | 角色 | 理由 |\n|---|---|---|---|---|\n" \
            "| 出口标识的生成与消费 | neutral-pattern | 采用 | 标识生成者 | 标识贯穿三步 |\n\n"
        design = "## 2. 模块架构图\n\n略。\n\n"
        (self.feature_root / "plan").mkdir(parents=True, exist_ok=True)
        (self.feature_root / "plan" / "plan.md").write_text(
            "# 计划\n\n" + (decision + design if decision_first else design + decision), encoding="utf-8")

    def test_chapter_order_and_must_placement_are_named_together(self) -> None:
        self.judged()
        self.write_plan(decision_first=False)
        self.write_contracts("data_models:\n  - name: 出口记录\n    must:\n"
                             "      - rule: NEU-01\n        text: x\n        verify: review\n"
                             + kp.contracts())
        message = self.hook("plan")
        self.assertIn("晚于第一个设计章", message)
        self.assertIn("data_models.出口记录 顶层挂了 must", message, "挂位问题没有与章节问题同轮出现")

    def test_an_unreadable_contract_reports_the_chapter_and_says_what_waits(self) -> None:
        self.judged()
        self.write_plan(decision_first=False)
        self.write_contracts("interfaces: [\n")
        message = self.hook("plan")
        self.assertIn("解析失败", message)
        self.assertIn("晚于第一个设计章", message, "契约读不出屏蔽了章节组")
        self.assertIn("契约解析失败", message.split("未能执行")[-1], "义务与集合组该以 skipped 写明前置")

    def test_a_clean_plan_passes(self) -> None:
        self.judged()
        self.write_plan(decision_first=True)
        self.write_contracts(kp.contracts())
        # 中性工程没配 profile、也没有 spec：没有问题，如实记章号与埋点两条未执行
        message = self.hook("plan")
        self.assertTrue(message.startswith("扩展门禁有 2 条判据未执行："), message)
        self.assertIn("plan 主章号（framework.config.json 没有配 project_profile.name", message)
        self.assertIn("埋点逐统计点落实（本需求没走 /story，spec 未提供统计设计）", message)

    def test_use_cases_cite_acceptance_ids_that_exist(self) -> None:
        """验收编号取 acceptance 各列表条目的 id，不认前缀；只报悬空的那几个，并说出在哪条用例。"""
        self.judged()
        self.write_plan(decision_first=True)
        self.write_contracts(kp.contracts())
        (self.feature_root / "acceptance.yaml").write_text(
            "criteria:\n  - id: 开户-01\n    description: x\nboundaries:\n  - id: B7\n    description: y\n",
            encoding="utf-8")
        (self.feature_root / "use-cases.yaml").write_text(
            "use_cases:\n  - id: 开户\n    branches:\n      - id: 正常\n        linked_acceptance: [开户-01, B7]\n"
            "      - id: 失败\n        linked_acceptance: [AC-K9]\n", encoding="utf-8")
        message = self.hook("plan")
        self.assertIn("验收 AC-K9（失败）", message)
        self.assertNotIn("开户-01（", message)
        self.assertNotIn("B7（", message)

    def test_a_design_chapter_is_cited_by_its_real_number(self) -> None:
        self.judged()
        self.write_plan(decision_first=True)
        self.write_contracts(kp.contracts())
        plan = self.feature_root / "plan" / "plan.md"
        plan.write_text(plan.read_text(encoding="utf-8").replace(
            "## 2. 模块架构图",
            "| 条目编号 | 落点实体 | 承载设计章 |\n|---|---|---|\n| NEU-01 | 甲 | 2. 模块架构图（出口） |\n"
            "| NEU-02 | 乙 | 3. 模块架构图 |\n\n## 2. 模块架构图"), encoding="utf-8")
        message = self.hook("plan")
        self.assertIn("「3. 模块架构图」对不上本文的章：「模块架构图」在本文是第 2 章", message)
        self.assertEqual(1, message.count("对不上本文的章"), "号与章名对得上的那一行不该报")


if __name__ == "__main__":
    unittest.main()
