"""埋点以指标为单位：蓝图里一条 `kind: event` 的明细就是一个指标，作者与审查拿到的是同一份解析。

锁住：
  ① 指标形状只核结构——第一张表之前有定义段（注释不算），有表头含「统计点」的点位表且至少一行；说明表不算点位，
     统计点列不必在第一列；正文以「不涉及：<依据>」起头的不判；不核指标名、统计点名与结果写法；
  ② 解析：统计点取「统计点」列，其余列照原表顺序跟在后面；定义段是第一张表之前的第一行正文；
  ③ 形状缺口随明细正文一起送到作者与审查，指回设计负责方。
plan 逐点落实（责任方法、多结果行、漏点）与 CU 作者/审查的送达在 test_cu_knowledge_chain 里按真实施工单位核。
全部用中性内容：机制不认识任何项目知识专名。
"""
from __future__ import annotations

import json
import unittest

import test_neutral_knowledge as nk

SHAPE = nk.EXT / "hooks" / "shared" / "stat-points.mjs"
TABLE = "| 统计点 | 结果 |\n|---|---|\n| 提交 | 成功 |"


def js(expr: str):
    proc = nk.node("--input-type=module", "-e",
                   f"const m = await import({nk.as_url(SHAPE)}); process.stdout.write(JSON.stringify({expr}));")
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def detail(body: str, title: str = "提交成功率") -> dict:
    return {"id": "detail-submit", "kind": "event", "title": title, "body": body, "evidence_refs": ["view:logical/node:n"]}


class TheIndicatorIsShaped(unittest.TestCase):
    """① 只核结构，不核名字与行数。"""

    def problems(self, body: str) -> list[str]:
        """按产品入口取：明细交给 designStatPoints，形状缺口随它出。"""
        bp = {"blueprint_id": "bp-neutral", "story_details": [detail(body)]}
        return js(f"m.designStatPoints({{ blueprint: {json.dumps(bp, ensure_ascii=False)}, scope: null }})")["details"][0]["problems"]

    def test_a_definition_and_a_point_table_pass(self) -> None:
        self.assertEqual([], self.problems(f"衡量提交成功的比例：分子提交成功，分母全部提交。\n\n{TABLE}\n\n- 表后补充一条。"))

    def test_an_indicator_without_rows_is_named(self) -> None:
        got = self.problems("衡量提交成功的比例。")
        self.assertTrue(any("没有统计点" in p for p in got), got)

    def test_an_explanation_table_is_not_a_point_table(self) -> None:
        got = self.problems("衡量提交成功的比例。\n\n| 口径 | 说明 |\n|---|---|\n| 分母 | 发起的提交 |")
        self.assertTrue(any("没有统计点" in p for p in got), got)

    def test_an_indicator_without_a_definition_is_named(self) -> None:
        """第一张表之前要有一行正文；注释不算正文。只核有没有，不核写了什么。"""
        for lead in ("", "<!-- 这里写定义 -->\n\n"):
            with self.subTest(lead=lead):
                got = self.problems(f"{lead}{TABLE}")
                self.assertTrue(any("「提交成功率」（detail-submit）缺定义段" in p for p in got), got)
        self.assertEqual([], self.problems(f"- 衡量提交成功的比例。\n\n{TABLE}"))

    def test_not_applicable_is_a_conclusion(self) -> None:
        self.assertEqual([], self.problems("不涉及：本需求没有需要统计的业务步骤。"))


class ThePointsAreReadOnce(unittest.TestCase):
    """② 统计点、定义段与原文由同一份解析给出。"""

    def design(self, *details: dict) -> dict:
        bp = {"blueprint_id": "bp-neutral", "story_details": list(details)}
        return js(f"m.designStatPoints({{ blueprint: {json.dumps(bp, ensure_ascii=False)}, scope: null }})")

    def test_the_point_column_need_not_come_first(self) -> None:
        body = ("衡量提交成功的比例。\n\n| 口径 | 说明 |\n|---|---|\n| 分母 | 发起的提交 |\n\n"
                "| 实际业务结果 | 统计点 | 本端获知时机 |\n|---|---|---|\n| 已受理、拒绝 | 提交/请求 | 响应返回时 |")
        got = self.design(detail(body))
        self.assertEqual("ready", got["state"])
        [d] = got["details"]
        self.assertEqual([], d["problems"])
        self.assertEqual([["提交/请求", "已受理、拒绝", "响应返回时"]], d["rows"])
        self.assertIn("发起的提交", d["body"], "说明表留在原文里给模型读")

    def test_the_definition_is_the_first_prose_line_before_the_table(self) -> None:
        got = self.design(detail(f"{TABLE}\n\n表后边界。", "甲"),
                          {**detail(f"<!-- 注释 -->\n衡量乙的比例。\n第二行。\n\n{TABLE}", "乙"), "id": "detail-b"})
        self.assertEqual(["", "衡量乙的比例。"], [d["lead"] for d in got["details"]])

    def test_a_design_without_point_tables_is_empty(self) -> None:
        got = self.design(detail("衡量提交成功的比例。"))
        self.assertEqual("empty", got["state"])


class TheShapeGapReachesAuthorAndReviewer(unittest.TestCase):
    """③ 形状缺口跟着明细正文送达，同一份给作者与审查。"""

    def test_the_gap_is_listed_under_its_detail(self) -> None:
        bp = {"blueprint_id": "bp-neutral", "story_details": [detail("衡量提交成功的比例。")]}
        lines = js(f"m.statDelivery({{ blueprint: {json.dumps(bp, ensure_ascii=False)}, scope: null }}, null, null)")
        text = "\n".join(lines)
        self.assertIn("衡量提交成功的比例。", text)
        self.assertIn("- 形状缺口：埋点明细「提交成功率」（detail-submit）没有统计点", text)
        self.assertIn("设计负责方在蓝图里补齐", text)


if __name__ == "__main__":
    unittest.main()
