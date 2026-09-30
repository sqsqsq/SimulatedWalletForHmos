"""spec / plan 的扩展门禁一轮报全：判据按数据前置分组，能判的组一次全判，缺前置的组说明缺什么。

上一轮实跑里，作者修完一类才看得见下一类——缺章就 return、判断不成立就 return、契约读失败整体 return，
同一个 check id 洋葱式 FAIL 八轮。这里锁的是：互不依赖的问题同轮同现；
真有依赖的（契约读不出时不核义务）以 skipped 写明前置，而不是让别的组陪着沉默。
"""
from __future__ import annotations

import json
import unittest

import test_knowledge_protocol as kp


class SpecProblemsShowUpTogether(kp.ProtocolCase):
    """spec：设计里的知识判断、验收承接、验收标准一致三组各按自己的前置判。"""

    def acceptance_with(self, *extra: str) -> None:
        """夹具判了 NEU-01/02/03 三条适用：桥三条都有，`extra` 再多桥几条（写规约编号，决定按夹具的命名）。"""
        rules = ["NEU-01", "NEU-02", "NEU-03", *extra]
        rows = "".join(f"  - id: AC-{i + 1}\n    knowledge_rule: {r}\n    knowledge_decision_id: k-{r.lower()}\n"
                       "    description: 桥\n" for i, r in enumerate(rules))
        (self.feature_root / "acceptance.yaml").write_text("criteria:\n" + rows, encoding="utf-8")

    def spec_md(self, *ids: str) -> None:
        (self.feature_root / "spec").mkdir(parents=True, exist_ok=True)
        (self.feature_root / "spec" / "spec.md").write_text(
            "# 规格\n\n## 验收标准\n\n" + "".join(f"- {i} 出口带标识\n" for i in ids), encoding="utf-8")

    def test_three_independent_problems_are_named_in_one_run(self) -> None:
        """单元不在册（判断组）、桥指向不适用的判断（承接组）、验收标准的编号在 acceptance 里没有（一致组）——一次全出。"""
        self.judged()
        self.decisions.append(self.decision("NEU-01", "not_applicable", "占位"))
        self.decisions[-1].update(decision_id="k-neu-99")
        self.decisions[-1]["knowledge"]["unit"] = "NEU-99"
        self.write_contracts()
        self.acceptance_with("NEU-04")
        self.spec_md("AC-1", "AC-9")
        message = self.hook("spec")
        self.assertIn("单元 NEU-99 不在", message)
        self.assertIn("k-neu-04，它不是本施工单位承接的适用判断", message, "承接问题没有与判断问题同轮出现")
        self.assertIn("AC-9 在 acceptance.yaml 里没有", message, "一致问题没有同轮出现")
        self.assertIn("【", message, "报错没有按组分节")

    def test_a_design_gap_does_not_hide_the_bridge(self) -> None:
        """判断的原文变了是设计缺口，交设计负责方；它不挡住验收承接那一组。"""
        self.judged()
        self.write_contracts()
        self.edit_knowledge("constraints/neutral-domain.md", "出口处记一条耗时", "出口处记一条总耗时")
        (self.feature_root / "acceptance.yaml").write_text("criteria:\n  - id: AC-1\n    description: x\n", encoding="utf-8")
        message = self.hook("spec")
        self.assertIn("知识原文变了", message)
        self.assertIn("k-neu-02（NEU-02）没有验收条目承接", message, "设计缺口屏蔽了承接组")

    def test_a_clean_spec_passes(self) -> None:
        """合法的普通 Feature 没走 /story、没有 Story：spec 门禁照常通过，不要求 Story。"""
        self.judged()
        self.write_contracts()
        self.acceptance_with()
        self.assertFalse((self.feature_root / "AR").exists(), "这个 Feature 本来就没有 Story")
        result = self.hook_result("spec")
        self.assertTrue(result.get("ok"), result)
        self.assertNotIn("story", json.dumps(result, ensure_ascii=False).lower(), "普通 Feature 被要求了 Story")
        self.assertIn("验收标准与 acceptance.yaml（这一次没有生成 spec.md）", self.fragments(result))


class PlanProblemsShowUpTogether(kp.ProtocolCase):
    """plan：契约与挂位、设计判断、每条 must、判断与义务一致、模式角色、用例引用各组一次判完。"""

    def test_placement_obligation_and_consistency_are_named_together(self) -> None:
        self.judged()
        self.write_contracts("data_models:\n  - name: 出口记录\n    must:\n"
                             "      - rule: NEU-01\n        decision_id: k-neu-01\n        text: x\n        verify: review\n"
                             + kp.contracts().replace("decision_id: k-neu-03", "decision_id: k-neu-04"))
        message = self.hook("plan")
        self.assertIn("data_models.出口记录 顶层挂了 must", message)
        self.assertIn("NEU-03 的 must 指向 k-neu-04，它不是本施工单位承接的适用判断", message, "义务问题没有与挂位同轮出现")
        self.assertIn("k-neu-03（NEU-03", message, "判断没人扛没有同轮出现")

    def test_an_unreadable_contract_says_what_waits(self) -> None:
        """契约读不出：义务与一致两组写明前置；不依赖契约的用例引用组照判。"""
        (self.feature_root / "contracts.yaml").write_text("interfaces: [\n", encoding="utf-8")
        (self.feature_root / "acceptance.yaml").write_text("criteria:\n  - id: AC-1\n    description: x\n", encoding="utf-8")
        (self.feature_root / "use-cases.yaml").write_text(
            "use_cases:\n  - id: 开户\n    branches:\n      - id: 失败\n        linked_acceptance: [AC-K9]\n", encoding="utf-8")
        message = self.hook("plan")
        self.assertIn("解析失败", message)
        self.assertIn("验收 AC-K9（失败）", message, "契约读不出屏蔽了用例引用组")
        self.assertIn("解析失败", message.split("未能执行")[-1], "义务与一致组该以 skipped 写明前置")

    def test_a_clean_plan_passes(self) -> None:
        self.judged()
        self.write_contracts(kp.contracts())
        result = self.hook_result("plan")
        self.assertTrue(result.get("ok"), result)

    def test_use_cases_cite_acceptance_ids_that_exist(self) -> None:
        """验收编号取 acceptance 各列表条目的 id，不认前缀；只报悬空的那几个，并说出在哪条用例。"""
        self.judged()
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


if __name__ == "__main__":
    unittest.main()
