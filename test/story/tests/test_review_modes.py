"""评审记录的两种填写位：人要选方案，还是复核一个结论。

`review_mode` 由作者按人实际要做的事登记，脚本只照它给填写位、查有限的形状、保住人写的字：

  ① choice 给「方案选择：」，confirm 给「审核结果：」加确认 / 不同意；都不预选；
  ② choice 的选项要是真正的有序列表——挤在一段、或根本没有列表，都点到那条议题；
  ③ 人写过的填写位在重渲染、议题重排、交互方式改变时一个字节不动；没人动过的首版跟着当前方式重生成；
  ④ 找人工区只在本议题里找，删掉一条的填写位不会借到邻居的。

测不了的是选项合不合理、推荐有没有依据、交互方式选得对不对——那归作者与独立审查。
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_review_golden import RendererCase  # noqa: E402

CHOICE_BODY = ("**决策点**：受理超时后由谁发起重试。\n\n"
               "**依据**：接口说明只写了超时按未受理处理。\n\n"
               "**可选的做法**：\n\n"
               "1. 客户端自动重试——用户无感，要受理方保证同一请求只处理一次。\n"
               "2. 提示用户手动重试——不依赖受理方去重，用户多一步。\n\n"
               "**建议**：选择方案 2（提示用户手动重试）。\n\n"
               "**理由**：受理方目前没有去重承诺。")
CONFIRM_BODY = ("**决策点**：提交与补卡由两张单分别承接。\n\n"
                "**依据**：上游已经拆成两张开发单。\n\n"
                "**结论与影响**：本单只做提交与回执展示。")
CHOICE_ZONE = "方案选择：\n请填写上方选项编号；另有方案时写明具体结论与理由。\n\n"
CONFIRM_ZONE = "审核结果：\n- [ ] 确认\n- [ ] 不同意\n不同意原因：\n调整结论：\n\n"


def entry(dec_id: str, mode: str | None, body: str, status: str = "open") -> dict:
    out = {"id": dec_id, "status": status, "category": "范围与拆分",
           "title": f"{dec_id} 的陈述句标题", "clarification": body, "decider": "需求负责人"}
    if mode is not None:
        out["review_mode"] = mode
    return out


class ModesCase(RendererCase):
    def build(self, *decisions: dict):
        self.write_decisions(list(decisions))
        return self.run_build()

    def text(self) -> str:
        return self.review.read_text(encoding="utf-8")

    def anchor(self, dec_id: str) -> str:
        return f"<!-- decision: {dec_id} -->"


class EachModeGetsItsOwnZone(ModesCase):
    def test_choice_and_confirm_zones_are_rendered_without_a_preselection(self) -> None:
        proc = self.build(entry("retry-owner", "choice", CHOICE_BODY),
                          entry("split", "confirm", CONFIRM_BODY, status="settled"))
        self.assertEqual(0, proc.returncode, proc.stderr)
        text = self.text()
        self.assertIn(CHOICE_ZONE + self.anchor("retry-owner"), text)
        self.assertIn(CONFIRM_ZONE + self.anchor("split"), text)
        self.assertNotIn("- [x]", text, "替人预选了")
        self.assertIn("1. 客户端自动重试", text, "有序列表没原样进评审记录")
        self.assertIn("\n2. 提示用户手动重试", text, "选项没独立成行")
        head = text.split("\n## ", 1)[0]
        self.assertIn("方案选择：", head, "顶部提示没说选方案怎么填")
        self.assertIn("「确认」或「不同意」", head, "顶部提示没说复核怎么填")

    def test_an_entry_without_a_mode_keeps_the_single_line(self) -> None:
        proc = self.build(entry("split", None, CONFIRM_BODY, status="settled"))
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("请需求负责人确认。\n\n审核结果：\n\n" + self.anchor("split"), self.text())

    def test_an_unknown_mode_is_named(self) -> None:
        proc = self.build(entry("split", "vote", CONFIRM_BODY))
        self.assertEqual(1, proc.returncode)
        self.assertIn("review_mode「vote」不认识", proc.stderr)


class ChoiceOptionsAreARealList(ModesCase):
    def test_options_squeezed_into_one_paragraph_are_named(self) -> None:
        body = CHOICE_BODY.replace(
            "1. 客户端自动重试——用户无感，要受理方保证同一请求只处理一次。\n"
            "2. 提示用户手动重试——不依赖受理方去重，用户多一步。",
            "1、客户端自动重试；2、提示用户手动重试。")
        proc = self.build(entry("retry-owner", "choice", body))
        self.assertEqual(1, proc.returncode)
        self.assertIn("决策 retry-owner 把几个选项写在了同一段", proc.stderr)

    def test_a_choice_without_any_list_is_named(self) -> None:
        proc = self.build(entry("retry-owner", "choice", CONFIRM_BODY))
        self.assertEqual(1, proc.returncode)
        self.assertIn("决策 retry-owner 是选方案的议题", proc.stderr)

    def test_a_confirmation_needs_no_invented_options(self) -> None:
        """复核一个结论不需要备选：没有列表是正常形状，不逼作者造选项。"""
        self.assertEqual(0, self.build(entry("split", "confirm", CONFIRM_BODY)).returncode)

    def test_numbers_that_are_not_options_do_not_trip_the_check(self) -> None:
        body = CHOICE_BODY.replace("接口说明只写了超时按未受理处理。",
                                   "接口说明写了超时 1.5 秒、重试间隔 2.0 秒。")
        self.assertEqual(0, self.build(entry("retry-owner", "choice", body)).returncode)


class EachOptionSaysWhatChoosingItChanges(ModesCase):
    """「可选的做法」每一项写成「做法——选它会怎样」：写不出后果差别的不是真取舍。只判字面。"""

    SECOND = "2. 提示用户手动重试——不依赖受理方去重，用户多一步。"

    def test_an_option_without_its_consequence_is_named(self) -> None:
        for name, line in {"没有分隔": "2. 提示用户手动重试。", "分隔之后为空": "2. 提示用户手动重试——"}.items():
            with self.subTest(case=name):
                proc = self.build(entry("retry-owner", "choice", CHOICE_BODY.replace(self.SECOND, line)))
                self.assertEqual(1, proc.returncode, proc.stdout)
                self.assertIn("决策 retry-owner 的「可选的做法」第 2 项没写选它会怎样", proc.stderr)
                self.assertIn("confirm", proc.stderr, "没给出降级为复核这条出路")

    def test_options_with_consequences_pass(self) -> None:
        self.assertEqual(0, self.build(entry("retry-owner", "choice", CHOICE_BODY)).returncode)


class WhatTheReviewerWroteStays(ModesCase):
    def fill(self, old: str, new: str) -> None:
        text = self.text()
        self.assertIn(old, text, "夹具变了，用例要跟着改")
        self.review.write_text(text.replace(old, new, 1), encoding="utf-8")

    def test_filled_zones_survive_rerender_and_reordering(self) -> None:
        a = entry("retry-owner", "choice", CHOICE_BODY)
        b = entry("split", "confirm", CONFIRM_BODY)
        self.assertEqual(0, self.build(a, b).returncode)
        chose = "方案选择：\n1，受理方已经答应去重。\n\n"
        judged = "审核结果：\n- [ ] 确认\n- [x] 不同意\n不同意原因：补卡入口要留。\n调整结论：本单含补卡入口。\n\n"
        self.fill(CHOICE_ZONE + self.anchor("retry-owner"), chose + self.anchor("retry-owner"))
        self.fill(CONFIRM_ZONE + self.anchor("split"), judged + self.anchor("split"))

        b["title"] = "split 的陈述句标题（复议）"
        self.assertEqual(0, self.build(b, a).returncode)
        text = self.text()
        self.assertIn(chose + self.anchor("retry-owner"), text, "选方案的表态被冲掉了")
        self.assertIn(judged + self.anchor("split"), text, "复核的表态被冲掉了")
        self.assertLess(text.index("（复议）"), text.index("retry-owner 的陈述句标题"), "没按新顺序重排")

    def test_changing_the_mode_never_drops_what_was_written(self) -> None:
        a = entry("retry-owner", "choice", CHOICE_BODY)
        self.assertEqual(0, self.build(a).returncode)
        chose = "方案选择：\n2\n\n"
        self.fill(CHOICE_ZONE + self.anchor("retry-owner"), chose + self.anchor("retry-owner"))

        a.update(review_mode="confirm", clarification=CONFIRM_BODY)
        proc = self.build(a)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn(chose + self.anchor("retry-owner"), self.text(), "改了交互方式就把人写的删了")
        self.assertNotIn("- [ ] 确认", self.text(), "人写过的填写位被换成了新形式")
        self.assertIn("原样保留", proc.stdout, "没说这条议题还是旧的填写位")

    def test_an_untouched_zone_follows_the_current_mode(self) -> None:
        """首版原样没人动过：里面没有人的意见，换成当前方式的填写位不丢任何东西。"""
        a = entry("retry-owner", "choice", CHOICE_BODY)
        self.assertEqual(0, self.build(a).returncode)
        a.update(review_mode="confirm", clarification=CONFIRM_BODY)
        proc = self.build(a)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn(CONFIRM_ZONE + self.anchor("retry-owner"), self.text())
        self.assertNotIn("方案选择：", self.text().split("\n## ", 1)[1])

    def test_a_deleted_zone_does_not_borrow_its_neighbour(self) -> None:
        """前一条填过「审核结果：」，后一条的填写位被整段删掉：后一条只在自己范围里找，给回首版。"""
        a = entry("split", "confirm", CONFIRM_BODY)
        b = entry("retry-owner", "choice", CHOICE_BODY)
        self.assertEqual(0, self.build(a, b).returncode)
        said = "审核结果：\n- [x] 确认\n- [ ] 不同意\n不同意原因：\n调整结论：\n\n"
        self.fill(CONFIRM_ZONE + self.anchor("split"), said + self.anchor("split"))
        self.fill(CHOICE_ZONE + self.anchor("retry-owner"), self.anchor("retry-owner"))

        self.assertEqual(0, self.build(a, b).returncode)
        text = self.text()
        self.assertEqual(1, text.count(said), "邻居的表态被复制了一份")
        self.assertIn(CHOICE_ZONE + self.anchor("retry-owner"), text, "删掉的填写位没有重新给出")


class OnlyTheOptionsSegmentIsChecked(ModesCase):
    """选项检查只看「可选的做法」那一段：别的段里的编号是说明，不是方案。"""

    def test_a_numbered_basis_next_to_real_options_passes(self) -> None:
        body = CHOICE_BODY.replace("接口说明只写了超时按未受理处理。", "接口结果分为 1. 成功；2. 失败。")
        proc = self.build(entry("retry-owner", "choice", body))
        self.assertEqual(0, proc.returncode, proc.stderr)

    def test_a_list_only_in_the_basis_does_not_count_as_options(self) -> None:
        body = CHOICE_BODY.replace(
            "1. 客户端自动重试——用户无感，要受理方保证同一请求只处理一次。\n"
            "2. 提示用户手动重试——不依赖受理方去重，用户多一步。",
            "客户端自动重试，或者提示用户手动重试。").replace(
            "接口说明只写了超时按未受理处理。", "接口说明写了两步：\n\n1. 提交请求\n2. 等待受理")
        proc = self.build(entry("retry-owner", "choice", body))
        self.assertEqual(1, proc.returncode)
        self.assertIn("「**可选的做法**」这一段却没有有序列表", proc.stderr)

    def test_any_number_of_options_and_numbers_inside_an_option_pass(self) -> None:
        body = CHOICE_BODY.replace(
            "2. 提示用户手动重试——不依赖受理方去重，用户多一步。",
            "2. 提示用户手动重试——不依赖受理方去重，用户多一步。\n"
            "3. 升级到 2.0 版接口后由受理方重试——每月 3、4 号维护窗口不可用。")
        self.assertEqual(0, self.build(entry("retry-owner", "choice", body)).returncode)


class SqueezedOptionsAreCaughtInEveryArrangement(ModesCase):
    """同一组选项三种排列：标题同一行挤、列表行里挤都拒绝且不写评审记录；各占一行通过。"""

    OPTIONS = ("1. 客户端自动重试——用户无感，要受理方保证同一请求只处理一次。\n"
               "2. 提示用户手动重试——不依赖受理方去重，用户多一步。")
    SQUEEZED = ("1. 客户端自动重试——用户无感，要受理方保证同一请求只处理一次；"
                "2. 提示用户手动重试——不依赖受理方去重，用户多一步。")

    def arrangements(self) -> dict[str, str]:
        return {
            "标题同一行": CHOICE_BODY.replace("**可选的做法**：\n\n" + self.OPTIONS,
                                         "**可选的做法**：" + self.SQUEEZED),
            "列表行里挤": CHOICE_BODY.replace(self.OPTIONS, self.SQUEEZED),
        }

    def test_squeezed_arrangements_are_refused_without_writing(self) -> None:
        for name, body in self.arrangements().items():
            with self.subTest(arrangement=name):
                self.assertNotEqual(CHOICE_BODY, body, "夹具变了，用例要跟着改")
                before = self.review.read_bytes() if self.review.exists() else None
                proc = self.build(entry("retry-owner", "choice", body))
                self.assertEqual(1, proc.returncode, proc.stdout)
                self.assertIn("决策 retry-owner 把几个选项写在了同一段", proc.stderr)
                after = self.review.read_bytes() if self.review.exists() else None
                self.assertEqual(before, after, "结构不对却写了评审记录")

    def test_one_option_per_line_passes(self) -> None:
        self.assertEqual(0, self.build(entry("retry-owner", "choice", CHOICE_BODY)).returncode)


class QuotedLabelsStayInsideTheHumanZone(ModesCase):
    """人工区从哪一行开始按生成时记下的正文摘要认：人在意见里引用标签，不会把意见算进机器正文。"""

    def fill(self, old: str, new: str) -> None:
        text = self.text()
        self.assertIn(old, text, "夹具变了，用例要跟着改")
        self.review.write_text(text.replace(old, new, 1), encoding="utf-8")

    def test_quoting_either_label_in_either_zone_is_kept(self) -> None:
        a = entry("split", "confirm", CONFIRM_BODY)
        b = entry("retry-owner", "choice", CHOICE_BODY)
        self.assertEqual(0, self.build(a, b).returncode)
        judged = ("审核结果：\n- [ ] 确认\n- [x] 不同意\n不同意原因：界面文案要统一。\n"
                  "调整结论：请保留以下标签示例：\n方案选择：\n填写方案编号。\n\n")
        chose = "方案选择：\n2\n补充：表单上仍叫\n审核结果：\n方案选择：\n两处都保留。\n\n"
        self.fill(CONFIRM_ZONE + self.anchor("split"), judged + self.anchor("split"))
        self.fill(CHOICE_ZONE + self.anchor("retry-owner"), chose + self.anchor("retry-owner"))

        proc = self.build(b, a)
        self.assertEqual(0, proc.returncode, proc.stderr)
        text = self.text()
        self.assertIn(judged + self.anchor("split"), text)
        self.assertIn(chose + self.anchor("retry-owner"), text)

        a.update(review_mode="choice", clarification=CHOICE_BODY)
        proc = self.build(b, a)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn(judged + self.anchor("split"), self.text(), "改了交互方式就把人写的动了")

    def test_a_label_line_inside_the_generated_body_is_not_the_zone(self) -> None:
        body = CONFIRM_BODY + "\n\n**结论与影响**：表单上的字段名如下\n\n审核结果：\n\n以上沿用现有表单。"
        a = entry("split", "confirm", body)
        self.assertEqual(0, self.build(a).returncode)
        judged = "审核结果：\n- [x] 确认\n- [ ] 不同意\n不同意原因：\n调整结论：\n\n"
        self.fill(CONFIRM_ZONE + self.anchor("split"), judged + self.anchor("split"))
        proc = self.build(a)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn(judged + self.anchor("split"), self.text())

    def test_a_real_edit_to_the_body_is_still_refused_without_asking_to_delete_opinions(self) -> None:
        a = entry("split", "confirm", CONFIRM_BODY)
        self.assertEqual(0, self.build(a).returncode)
        judged = "审核结果：\n- [ ] 确认\n- [x] 不同意\n不同意原因：\n调整结论：示例\n方案选择：\n1\n\n"
        self.fill(CONFIRM_ZONE + self.anchor("split"), judged + self.anchor("split"))
        self.fill("上游已经拆成两张开发单。", "手改过的依据。")
        before = self.review.read_bytes()
        proc = self.build(a)
        self.assertEqual(1, proc.returncode, "正文手改被静默盖掉了")
        self.assertEqual(before, self.review.read_bytes(), "拒绝了却写了盘")
        self.assertIn("人写的内容不要删", proc.stderr)


if __name__ == "__main__":
    unittest.main()
