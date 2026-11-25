# -*- coding: utf-8 -*-
"""两种范围命令与提示词的当前承接者（S13：R6、补审 R2/R3）。

这些判据判的是**实际加载的页面/规则里写了什么**：同一需求用「本次只要 A」与
「要求完整设计 A、B 而先做 A」两条命令时，作者读到的预期必须不同；update 的主动意见
与「先问后记」次序不能互相打架；错误恢复与委派只指向当前 Story、蓝图与原话承担者。
"""
from __future__ import annotations

import unittest
from ext_workspace import DEV_EXT

SKILL = DEV_EXT / "base" / "skills" / "story"


def read(rel: str) -> str:
    return (SKILL / rel).read_text(encoding="utf-8")


def read_ext(rel: str) -> str:
    return (DEV_EXT / "base" / rel).read_text(encoding="utf-8")


class TheTwoScopeCommandsRouteDifferently(unittest.TestCase):
    """R6：缩小本期范围与保留完整设计只把施工交给本次，是两条路。"""

    def test_the_design_page_routes_them_to_different_results(self) -> None:
        design = read("phases/design.md")
        body = design.split("## 二、交给设计", 1)[1].split("\n## ", 1)[0]
        for needle in ("本次只要 A", "要求完整设计 A、B 而先做 A", "缩小本期业务范围",
                       "保留 A、B 的全部需求义务", "只把 A 对应的施工单位交给本次执行",
                       "纯送审允许零 CU"):
            self.assertIn(needle, body, f"范围分流少了「{needle}」")

    def test_init_analysis_only_positions_and_points_at_the_design_page(self) -> None:
        rules = read("rules/init_analysis.md")
        self.assertIn("两种范围命令在 `phases/design.md`", rules)
        self.assertNotIn("「本需求只做 X」或「完整设计先实施 X」写进蓝图的需求条目与边界", rules,
                         "init_analysis 又把两条命令并成同一个落点")

    def test_the_condition_definition_stays_in_one_place(self) -> None:
        """M19：必要问人条件的完整定义只在 design 页写一份，别处按节名指过去。"""
        self.assertIn("必要问人条件", read("phases/design.md"))
        self.assertIn("上位依据冲突且现授权不能裁决", read("phases/design.md"))
        for page in ("SKILL.md", "rules/init_analysis.md", "phases/update.md", "phases/story-write.md",
                     "phases/meeting-read.md"):
            self.assertNotIn("上位依据冲突且现授权不能裁决", read(page), f"{page} 又抄了一份条件定义")


class UpdateKeepsProactiveInputAndAskInOrder(unittest.TestCase):
    """补审 R2、R4：主动意见直接保留为原件；确需提问才先写问法再记原话；三方合并步骤送达。"""

    def test_proactive_comment_is_not_backfilled_into_an_ask(self) -> None:
        update = read("phases/update.md")
        self.assertIn("先问后记；主动意见另有入口", update)
        self.assertNotIn("人答了之后先记下，再照决定改", update)
        self.assertIn("已在 Story 改稿、会话或附件中**主动给过的意见**直接保留为回流原件", update)
        self.assertIn("先判权限与来源", update)
        self.assertNotIn("**交蓝图负责方形成 `gap`（owner、等什么、本期影响），两边来源并列，停下问人**", update)

    def test_the_three_way_merge_steps_are_in_the_edit_instructions(self) -> None:
        update = read("phases/update.md")
        for needle in ("同时取齐", "相对共同底稿分别查变化", "异段", "同段", "只有意见文档",
                       "缺共同基准", "原话与理由留在 `update-notes.md`"):
            self.assertIn(needle, update, f"三方合并少了「{needle}」")
        self.assertIn("不靠文字相似度判采纳", update)
        # S36-A：主入口、update 输入阶段与 prepare 提示统一为三方核底稿，退场旧「编辑底稿/以人的为准」
        skill = read("SKILL.md")
        update_py = read("scripts/core/flow/update.py")
        self.assertIn("原样保存人的改稿，首次改写 Story 前按 `phases/update.md` 输入阶段的三方方法核共同底稿与两边变化", skill)
        for surface_name, text in (("SKILL.md", skill), ("phases/update.md", update), ("flow/update.py", update_py)):
            for retired in ("编辑底稿", "以人的为准", "以人的这一版为准"):
                self.assertNotIn(retired, text, f"{surface_name} 仍残余已退出的覆盖式指路「{retired}」")

    def test_human_reply_effect_separates_sourced_verbatim_ruling_and_gap(self) -> None:
        """S36-B：主入口「人签」与 design.md 首次质询后答复统一保留原话、仅将有权且范围明确的决定交 owner、未决保持 gap。"""
        skill = read("SKILL.md")
        design = read("phases/design.md")
        self.assertIn("先保留有出处的原话。仅将其中有权、对象与适用范围明确的决定交 owner 核定；仍未决定的部分保持 gap。", skill)
        self.assertNotIn("人确认前不记录、不往下走", skill)
        self.assertIn("材料门用现有 `ask`/`decide` 及澄清返回，不把自由附言写成已接受签认", skill)
        self.assertIn("按第 4 步现有 owner 合同分派——仅将其中有权、对象与适用范围明确的决定（含本轮临时授权）交 owner 核定，仍未决定的部分保持 gap。", design)

    def test_story_write_points_at_the_design_page_not_a_spec_rule(self) -> None:
        guide = read("phases/story-write.md")
        self.assertNotIn("按 R01", guide)
        self.assertNotIn("Spec 三条件", guide)
        self.assertIn("phases/design.md`「首次质询后的集中问答与初始反馈」", guide)


class ErrorsAndDelegationPointAtCurrentBearers(unittest.TestCase):
    """补审 R3：错误恢复与委派不再指向已退出的 Story Review / 决策登记，保留的投影与独审仍在。"""

    def test_sources_and_next_steps_name_current_bearers(self) -> None:
        self.assertNotIn("与 Review 里受影响的章节", read("scripts/core/story/design-source.mjs"))
        self.assertIn("同步 Story 里受影响的章节", read("scripts/core/story/design-source.mjs"))
        self.assertNotIn("决策登记", read("scripts/core/story/chapter.mjs"))
        self.assertNotIn("决策登记", read("scripts/core/story/writing-plan.mjs"))
        author = read_ext("hooks/blueprint/author.md")
        self.assertIn("Story、施工单位与设计参考投影", author)

    def test_s42_blueprint_example_is_neutral_and_retired_scope_gate_phrases_are_gone(self) -> None:
        """S42：蓝图作者 story_details 示例中性化且保留缓存设计能力；初析/设计/更新/主入口退出旧 reopen 与范围关卡维护口令。"""
        author = read_ext("hooks/blueprint/author.md")
        for prefilled in ("detail-balance-cache", "余额缓存有效期", "余额缓存 5 分钟", "切换账号时清空", "flow:balance-cache"):
            self.assertNotIn(prefilled, author, f"hooks/blueprint/author.md 仍残留预填项目结论「{prefilled}」")
        for kept in ("数据的有效期与清理", "story_details:", "data_policy", "evidence_refs"):
            self.assertIn(kept, author)
        # S42 R3：story_details YAML 示例本身须可被解析且 kind 为单个合法枚举值（不得用竖线拼接）
        import re, yaml
        m = re.search(r"```yaml\s*\n(story_details:[\s\S]*?)\n```", author)
        self.assertIsNotNone(m, "hooks/blueprint/author.md 缺少 story_details YAML 示例")
        parsed = yaml.safe_load(m.group(1))
        self.assertIsInstance(parsed, dict)
        self.assertIn(parsed["story_details"][0]["kind"], {"data_policy", "configuration", "event", "special_design"})
        self.assertNotIn("|", str(parsed["story_details"][0]["kind"]))
        for rel in ("SKILL.md", "rules/init_analysis.md", "phases/design.md", "phases/update.md"):
            text = read(rel)
            for retired in ("reopen", "范围关卡", "范围定法/承载哪份的关卡"):
                self.assertNotIn(retired, text, f"{rel} 仍残留已退役口令「{retired}」")
        self.assertNotIn("Story、Review 与施工单位", author)
        rules = read_ext("rules/plan-rules.overlay.yaml")
        self.assertNotIn("回关卡人签", rules)
        self.assertIn("按当前 Story、蓝图里的决定与缺口、记下的原话", rules)
        # 保留项仍在：蓝图评审投影、独立审查、历史意见附件
        self.assertIn("蓝图的原生评审投影", read("scripts/core/story/review-object.mjs"))
        self.assertTrue((SKILL / "scripts/core/story/review-report-contract.mjs").is_file())
        self.assertTrue((SKILL / "scripts/core/story/independent-review.mjs").is_file())


if __name__ == "__main__":
    unittest.main()