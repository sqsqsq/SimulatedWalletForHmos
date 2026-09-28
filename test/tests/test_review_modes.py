"""评审记录的人工区与议题形态：三态加修改意见，形态由状态定。

脚本只照登记表给填写位、查有限的形状、保住人写的字：

  ① 每条议题的人工区都是「评审结论：同意 / 需修改 / 暂缓」与「修改意见：」，不预选；
  ② 待评审的写成 choice，「可选的做法」至少两项、每项写后果，并有建议；
     已定的写成 confirm，依据引人的原话；决定人只写角色——不合规时渲染前一次报全；
  ③ 人写过的人工区在重渲染、议题重排时一个字节不动；CRLF 存盘不算写过字；
  ④ 找人工区只在本议题里找，删掉一条的填写位不会借到邻居的。

测不了的是选项合不合理、推荐有没有依据——那归作者与独立审查。
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flow_steps import HUMAN_ZONE  # noqa: E402
from test_review_golden import RendererCase  # noqa: E402

CHOICE_BODY = ("**决策点**：受理超时后由谁发起重试。\n\n"
               "**依据**：接口说明只写了超时按未受理处理。\n\n"
               "**可选的做法**：\n\n"
               "1. 客户端自动重试——用户无感，要受理方保证同一请求只处理一次。\n"
               "2. 提示用户手动重试——不依赖受理方去重，用户多一步。\n\n"
               "**建议**：选择方案 2（提示用户手动重试）。\n\n"
               "**理由**：受理方目前没有去重承诺。")
CONFIRM_BODY = ("**决策点**：提交与补卡由两张单分别承接。\n\n"
                "**依据**：产品负责人在需求澄清会上说「补卡另起一张单」。\n\n"
                "**结论与影响**：本单只做提交与回执展示。")
#: 与 CHOICE_BODY 同一个决策点，定下来之后的样子
CHOICE_BODY_SETTLED = ("**决策点**：受理超时后由谁发起重试。\n\n"
                       "**依据**：受理方负责人在评审会上说「我们不做去重」。\n\n"
                       "**结论与影响**：本单按提示用户手动重试做，验收加一条重试入口。")
ZONE = HUMAN_ZONE + "\n"


def entry(dec_id: str, mode: str, body: str, status: str = "open", decider: str = "需求负责人") -> dict:
    return {"id": dec_id, "status": status, "category": "范围与交付", "review_mode": mode,
            "title": f"{dec_id} 的陈述句标题", "clarification": body, "decider": decider}


def choice(dec_id: str = "retry-owner", body: str = CHOICE_BODY) -> dict:
    return entry(dec_id, "choice", body)


def confirm(dec_id: str = "split", body: str = CONFIRM_BODY) -> dict:
    return entry(dec_id, "confirm", body, status="settled")


class ModesCase(RendererCase):
    def build(self, *decisions: dict):
        self.write_decisions(list(decisions))
        return self.run_build()

    def text(self) -> str:
        return self.review.read_text(encoding="utf-8")

    def fill(self, old: str, new: str) -> None:
        text = self.text()
        self.assertIn(old, text, "夹具变了，用例要跟着改")
        self.review.write_text(text.replace(old, new, 1), encoding="utf-8")

    def write_flow_carry(self, *items: str) -> None:
        """在流程契约里记下「这一轮人说了沿用哪几条」——正常由 `decide --update` 写。"""
        flow = self.src / "story-flow.json"
        data = json.loads(flow.read_text(encoding="utf-8")) if flow.is_file() else {}
        data["update"] = {"open": "20260920-000000",
                          "decisions": [{"item": "沿用上一版表态", "issue": i, "reply": "意思没变，沿用",
                                         "by": "human", "at": "2026-09-20T00:00:00+00:00"}
                                        for i in items]}
        flow.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def anchor(self, dec_id: str) -> str:
        return f"<!-- decision: {dec_id} -->"


class EveryIssueGetsThreeStatesAndAnOpinion(ModesCase):
    def test_both_forms_share_the_zone_and_nothing_is_preselected(self) -> None:
        proc = self.build(choice(), confirm())
        self.assertEqual(0, proc.returncode, proc.stderr)
        text = self.text()
        self.assertIn("请需求负责人评审。\n\n" + ZONE + self.anchor("retry-owner"), text)
        self.assertIn(ZONE + self.anchor("split"), text)
        self.assertNotIn("- [x]", text, "替人预选了")
        self.assertIn("\n2. 提示用户手动重试", text, "选项没原样留在机器区")
        head = text.split("\n## ", 1)[0]
        self.assertIn("评审结论", head, "顶部提示没说怎么表态")
        self.assertIn("修改意见", head, "顶部提示没说要改的写在哪")
        for gone in ("方案选择：", "审核结果：", "不同意原因", "调整结论"):
            self.assertNotIn(gone, text)


class TheFormFollowsTheStatus(ModesCase):
    """AC17：形态不合规在渲染前报出来，各给改法，盘上不写。"""

    def refused(self, *decisions: dict) -> str:
        before = self.review.read_bytes() if self.review.exists() else None
        proc = self.build(*decisions)
        self.assertEqual(1, proc.returncode, proc.stdout)
        after = self.review.read_bytes() if self.review.exists() else None
        self.assertEqual(before, after, "不合规却写了评审记录")
        return proc.stderr

    def test_an_open_issue_must_offer_options(self) -> None:
        out = self.refused(entry("retry-owner", "confirm", CONFIRM_BODY))
        self.assertIn("要写成 choice", out)

    def test_a_single_option_is_not_a_choice(self) -> None:
        body = CHOICE_BODY.replace("2. 提示用户手动重试——不依赖受理方去重，用户多一步。\n", "")
        self.assertIn("至少两项", self.refused(choice(body=body)))

    def test_a_settled_issue_quotes_the_person(self) -> None:
        body = CONFIRM_BODY.replace("产品负责人在需求澄清会上说「补卡另起一张单」。", "上游已经拆成两张开发单。")
        self.assertIn("引人的表态", self.refused(confirm(body=body)))

    def test_a_settled_issue_is_a_confirmation(self) -> None:
        self.assertIn("写成 confirm", self.refused(entry("split", "choice", CHOICE_BODY, status="settled")))

    def test_the_decider_is_a_role(self) -> None:
        for bad in ("产品负责人在评审会上确认", "改版稿", "需求负责人确认"):
            with self.subTest(decider=bad):
                self.assertIn("不是角色", self.refused(entry("split", "confirm", CONFIRM_BODY,
                                                         status="settled", decider=bad)))

    def test_role_names_with_action_words_inside_are_roles(self) -> None:
        for good in ("审核员", "评审组长"):
            with self.subTest(decider=good):
                proc = self.build(entry("split", "confirm", CONFIRM_BODY, status="settled", decider=good))
                self.assertNotIn("不是角色", proc.stderr + proc.stdout)

    def test_an_unknown_mode_is_named(self) -> None:
        self.assertIn("review_mode「vote」不认识", self.refused(entry("split", "vote", CONFIRM_BODY)))

    def test_every_problem_is_listed_at_once(self) -> None:
        out = self.refused(entry("a", "confirm", CONFIRM_BODY),
                           entry("b", "confirm", CONFIRM_BODY.replace("「补卡另起一张单」", "补卡另起"),
                                 status="settled"))
        self.assertIn("决策 a", out)
        self.assertIn("决策 b", out)


class ChoiceOptionsAreARealList(ModesCase):
    def test_options_squeezed_into_one_paragraph_are_named(self) -> None:
        body = CHOICE_BODY.replace(
            "1. 客户端自动重试——用户无感，要受理方保证同一请求只处理一次。\n"
            "2. 提示用户手动重试——不依赖受理方去重，用户多一步。",
            "1、客户端自动重试；2、提示用户手动重试。")
        proc = self.build(choice(body=body))
        self.assertEqual(1, proc.returncode)
        self.assertIn("决策 retry-owner 把几个选项写在了同一段", proc.stderr)

    def test_numbers_that_are_not_options_do_not_trip_the_check(self) -> None:
        body = CHOICE_BODY.replace("接口说明只写了超时按未受理处理。",
                                   "接口说明写了超时 1.5 秒、重试间隔 2.0 秒。")
        self.assertEqual(0, self.build(choice(body=body)).returncode)

    def test_a_list_only_in_the_basis_does_not_count_as_options(self) -> None:
        body = CHOICE_BODY.replace(
            "1. 客户端自动重试——用户无感，要受理方保证同一请求只处理一次。\n"
            "2. 提示用户手动重试——不依赖受理方去重，用户多一步。",
            "客户端自动重试，或者提示用户手动重试。").replace(
            "接口说明只写了超时按未受理处理。", "接口说明写了两步：\n\n1. 提交请求\n2. 等待受理")
        proc = self.build(choice(body=body))
        self.assertEqual(1, proc.returncode)
        self.assertIn("至少两项有序列表", proc.stderr)

    def test_three_options_and_numbers_inside_an_option_pass(self) -> None:
        body = CHOICE_BODY.replace(
            "2. 提示用户手动重试——不依赖受理方去重，用户多一步。",
            "2. 提示用户手动重试——不依赖受理方去重，用户多一步。\n"
            "3. 升级到 2.0 版接口后由受理方重试——每月 3、4 号维护窗口不可用。")
        self.assertEqual(0, self.build(choice(body=body)).returncode)

    def test_an_option_without_its_consequence_is_named(self) -> None:
        second = "2. 提示用户手动重试——不依赖受理方去重，用户多一步。"
        for name, line in {"没有分隔": "2. 提示用户手动重试。", "分隔之后为空": "2. 提示用户手动重试——"}.items():
            with self.subTest(case=name):
                proc = self.build(choice(body=CHOICE_BODY.replace(second, line)))
                self.assertEqual(1, proc.returncode, proc.stdout)
                self.assertIn("第 2 项没写选它会怎样", proc.stderr)

    def test_a_choice_without_a_suggestion_is_named(self) -> None:
        body = CHOICE_BODY.split("**建议**")[0].rstrip()
        proc = self.build(choice(body=body))
        self.assertEqual(1, proc.returncode)
        self.assertIn("缺「**建议**」", proc.stderr)


class WhatTheReviewerWroteStays(ModesCase):
    def test_filled_zones_survive_rerender_and_reordering(self) -> None:
        a, b = choice(), confirm()
        self.assertEqual(0, self.build(a, b).returncode)
        said_a = ("评审结论：\n- [ ] 同意\n- [x] 需修改\n- [ ] 暂缓\n"
                  "修改意见：选方案 1，受理方已经答应去重。\n\n")
        said_b = "评审结论：\n- [x] 同意\n- [ ] 需修改\n- [ ] 暂缓\n修改意见：\n\n"
        self.fill(ZONE + self.anchor("retry-owner"), said_a + self.anchor("retry-owner"))
        self.fill(ZONE + self.anchor("split"), said_b + self.anchor("split"))

        b["title"] = "split 的陈述句标题（复议）"
        self.assertEqual(0, self.build(b, a).returncode)
        text = self.text()
        self.assertIn(said_a + self.anchor("retry-owner"), text, "需修改的表态被冲掉了")
        self.assertIn(said_b + self.anchor("split"), text, "同意的表态被冲掉了")

    def test_settling_an_untouched_issue_rerenders_its_zone(self) -> None:
        """议题从待评审变成已定，人工区为空：照当前形态重渲，没有旧填写位残留。"""
        a = choice()
        self.assertEqual(0, self.build(a).returncode)
        a.update(status="settled", review_mode="confirm", clarification=CHOICE_BODY_SETTLED)
        proc = self.build(a)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn(ZONE + self.anchor("retry-owner"), self.text())

    def test_a_crlf_file_is_not_mistaken_for_an_opinion(self) -> None:
        """AC16：评审人的编辑器把文件存成 CRLF，人没写字就不算写过，删掉议题照常渲染。"""
        a, b = choice(), confirm()
        self.assertEqual(0, self.build(a, b).returncode)
        self.review.write_bytes(self.review.read_bytes().replace(b"\n", b"\r\n"))
        proc = self.build(a)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertNotIn("写过意见", proc.stderr)

    def test_a_deleted_zone_does_not_borrow_its_neighbour(self) -> None:
        a, b = confirm(), choice()
        self.assertEqual(0, self.build(a, b).returncode)
        said = "评审结论：\n- [x] 同意\n- [ ] 需修改\n- [ ] 暂缓\n修改意见：\n\n"
        self.fill(ZONE + self.anchor("split"), said + self.anchor("split"))
        self.fill(ZONE + self.anchor("retry-owner"), self.anchor("retry-owner"))

        self.assertEqual(0, self.build(a, b).returncode)
        text = self.text()
        self.assertEqual(1, text.count(said), "邻居的表态被复制了一份")
        self.assertIn(ZONE + self.anchor("retry-owner"), text, "删掉的填写位没有重新给出")


class AnOpinionNeverDisappearsInARerender(ModesCase):
    """`build` 是整份覆盖。人写过字的那几条，**不能靠「这次没渲染它」悄悄没掉**。"""

    SAID = "评审结论：\n- [ ] 同意\n- [x] 需修改\n- [ ] 暂缓\n修改意见：选 2。\n\n"

    def test_deleting_an_issue_someone_answered_stops_the_build(self) -> None:
        a, b = choice(), confirm()
        self.assertEqual(0, self.build(a, b).returncode)
        self.fill(ZONE + self.anchor("split"), self.SAID + self.anchor("split"))
        before = self.text()
        proc = self.build(a)                      # 登记表里把 split 删了
        self.assertEqual(1, proc.returncode, proc.stdout)
        self.assertIn("split", proc.stderr)
        self.assertIn("写过意见", proc.stderr)
        self.assertEqual(before, self.text(), "停手了却还是把文件覆盖了")

    def test_a_zone_not_in_the_current_form_stops_the_build(self) -> None:
        """人工区不是当前形态（没有行首「评审结论：」）：不认、不搬，停下要求按当前形态重写，文件不动。"""
        a = choice()
        self.assertEqual(0, self.build(a).returncode)
        self.fill(ZONE + self.anchor("retry-owner"),
                  "审核结果：不同意\n不同意原因：XYZ 要改\n\n" + self.anchor("retry-owner"))
        before = self.text()
        proc = self.build(a)
        self.assertEqual(1, proc.returncode, proc.stdout)
        self.assertIn("人工区不是当前形态", proc.stderr)
        self.assertEqual(before, self.text(), "停手了却还是把文件覆盖了")
        self.assertIn("XYZ", self.text())

    def test_deleting_an_issue_nobody_answered_is_fine(self) -> None:
        a, b = choice(), confirm()
        self.assertEqual(0, self.build(a, b).returncode)
        self.assertEqual(0, self.build(a).returncode)
        self.assertNotIn("split", self.text())

    def test_changing_the_question_under_an_answer_stops_the_build(self) -> None:
        a = choice()
        self.assertEqual(0, self.build(a).returncode)
        self.fill(ZONE + self.anchor("retry-owner"), self.SAID + self.anchor("retry-owner"))
        before = self.text()
        a.update(status="settled", review_mode="confirm", clarification=CONFIRM_BODY)
        proc = self.build(a)
        self.assertEqual(1, proc.returncode, proc.stdout)
        self.assertIn("已经在它下面写过意见", proc.stderr)
        self.assertIn("decide --update", proc.stderr, "没给出沿用旧表态的那条出路")
        self.assertEqual(before, self.text(), "停手了却还是把文件覆盖了")

    def test_recording_the_carry_over_unlocks_it(self) -> None:
        a = choice()
        self.assertEqual(0, self.build(a).returncode)
        self.fill(ZONE + self.anchor("retry-owner"), self.SAID + self.anchor("retry-owner"))
        a.update(status="settled", review_mode="confirm", clarification=CONFIRM_BODY)
        self.assertEqual(1, self.build(a).returncode, "问题换了却没停手")
        self.write_flow_carry("retry-owner")
        proc = self.build(a)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn(self.SAID + self.anchor("retry-owner"), self.text(), "说了沿用却没带回表态")
        self.assertIn("沿用上一版的表态", proc.stdout)

    def test_a_carry_over_for_another_issue_does_not_unlock_this_one(self) -> None:
        a = choice()
        self.assertEqual(0, self.build(a).returncode)
        self.fill(ZONE + self.anchor("retry-owner"), self.SAID + self.anchor("retry-owner"))
        a.update(status="settled", review_mode="confirm", clarification=CONFIRM_BODY)
        self.write_flow_carry("split")
        self.assertEqual(1, self.build(a).returncode, "别条议题的记录把这一条放行了")


class QuotedLabelsStayInsideTheHumanZone(ModesCase):
    """人工区从哪一行开始按生成时记下的正文摘要认：人在意见里引用标签，不会把意见算进机器正文。"""

    def test_quoting_the_label_in_an_opinion_is_kept(self) -> None:
        a, b = confirm(), choice()
        self.assertEqual(0, self.build(a, b).returncode)
        said = ("评审结论：\n- [ ] 同意\n- [x] 需修改\n- [ ] 暂缓\n"
                "修改意见：表单上仍叫\n评审结论：\n两处都保留。\n\n")
        self.fill(ZONE + self.anchor("split"), said + self.anchor("split"))
        proc = self.build(b, a)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn(said + self.anchor("split"), self.text())

    def test_a_label_line_inside_the_generated_body_is_not_the_zone(self) -> None:
        body = CONFIRM_BODY + "\n\n表单上的字段名如下\n\n评审结论：\n\n以上沿用现有表单。"
        a = confirm(body=body)
        self.assertEqual(0, self.build(a).returncode)
        said = "评审结论：\n- [x] 同意\n- [ ] 需修改\n- [ ] 暂缓\n修改意见：\n\n"
        self.fill(ZONE + self.anchor("split"), said + self.anchor("split"))
        proc = self.build(a)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn(said + self.anchor("split"), self.text())

    def test_a_real_edit_to_the_body_is_still_refused(self) -> None:
        a = confirm()
        self.assertEqual(0, self.build(a).returncode)
        said = "评审结论：\n- [ ] 同意\n- [x] 需修改\n- [ ] 暂缓\n修改意见：示例\n\n"
        self.fill(ZONE + self.anchor("split"), said + self.anchor("split"))
        self.fill("本单只做提交与回执展示。", "手改过的结论。")
        before = self.review.read_bytes()
        proc = self.build(a)
        self.assertEqual(1, proc.returncode, "正文手改被静默盖掉了")
        self.assertEqual(before, self.review.read_bytes(), "拒绝了却写了盘")
        self.assertIn("人写的内容不要删", proc.stderr)


if __name__ == "__main__":
    unittest.main()
