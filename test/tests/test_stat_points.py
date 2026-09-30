"""埋点逐点落实：设计里的统计点从蓝图的埋点明细读，plan 的逐点表按列名找，不认固定章节。

锁的是读法：蓝图 `story_details` 里 `kind: event`、依据落在本施工单位设计引用上的明细，正文里表头含「统计点」的表逐行是
统计点；plan.md 里表头同时含「统计点」与「责任方法」的表在哪一节都认，同一统计点可以多行。没有蓝图、没有落在本单位的
明细、明细里没有统计点表各自说清，不当作「有统计点」。
"""
from __future__ import annotations

import json
import subprocess
import unittest

from ext_workspace import DEV_EXT

MODULE = (DEV_EXT / "hooks" / "shared" / "stat-points.mjs").resolve().as_uri()

EVENT = """总述：开票结果进成功率统计。

#### 电子发票开具成功率

成功数 / 发起数。

| 统计点 | 业务动作 | 实际适用结果 |
|---|---|---|
| 开票流程 / 提交 | 点提交 | 成功、失败 |
| 开票流程 / 回执 | 收到回执 | 成功 |
"""

PLAN = """# 计划

## 3. 开票

| 统计点 | 结果 | 责任方法 |
|---|---|---|
| 开票流程 / 提交 | 成功 | InvoiceService.submit |
| 开票流程/提交 | 失败 | `InvoiceService.submit` |
"""


def run(expr: str, design: dict | None = None, plan: str = "") -> object:
    script = (f"const m = await import({json.dumps(MODULE)});"
              "const [design, plan] = JSON.parse(process.argv[1]);"
              "if (design) design.scope = design.scope ? new Set(design.scope) : null;"
              f"process.stdout.write(JSON.stringify({expr}));")
    proc = subprocess.run(["node", "--input-type=module", "-e", script, json.dumps([design, plan], ensure_ascii=False)],
                          capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def design(details: list[dict], scope: list[str] | None = ("view:runtime/flow:invoice",)) -> dict:
    return {"blueprint": {"blueprint_id": "bp-invoice", "story_details": details}, "scope": list(scope) if scope else None}


def detail(kind: str = "event", body: str = EVENT, refs: tuple[str, ...] = ("view:runtime/flow:invoice",)) -> dict:
    return {"id": "detail-invoice", "kind": kind, "title": "开票埋点", "body": body, "evidence_refs": list(refs)}


class DesignPointsComeFromTheBlueprint(unittest.TestCase):
    def test_points_are_the_rows_of_the_stat_point_table(self) -> None:
        got = run("m.designStatPoints(design)", design([detail()]))
        self.assertEqual("ready", got["state"])
        self.assertEqual(["开票流程 / 提交", "开票流程 / 回执"], [r[0] for r in got["details"][0]["rows"]])

    def test_only_event_details_in_this_unit_count(self) -> None:
        others = [detail(kind="data_policy"), detail(refs=("view:runtime/flow:other",))]
        got = run("m.designStatPoints(design)", design(others))
        self.assertEqual("missing", got["state"])
        self.assertIn("bp-invoice", got["why"])

    def test_a_detail_without_a_point_table_is_empty_not_ready(self) -> None:
        self.assertEqual("empty", run("m.designStatPoints(design).state", design([detail(body="只有一句话。")])))

    def test_no_blueprint_says_so(self) -> None:
        got = run("m.designStatPoints(design)", {"scope": None})
        self.assertEqual("none", got["state"])


class PlanRowsAreFoundByTheirColumns(unittest.TestCase):
    def test_rows_are_read_wherever_the_table_is(self) -> None:
        rows = run("m.planStatRows(plan)", plan=PLAN)
        self.assertEqual([["开票流程 / 提交", ["InvoiceService.submit"]], ["开票流程/提交", ["InvoiceService.submit"]]],
                         [[r["point"], r["methods"]] for r in rows])

    def test_point_names_align_without_spaces_and_marks(self) -> None:
        self.assertEqual(1, run("new Set(m.planStatRows(plan).map(r => m.pointKey(r.point))).size", plan=PLAN))

    def test_a_table_without_the_method_column_is_not_the_plan_table(self) -> None:
        self.assertEqual([], run("m.planStatRows(plan)", plan=EVENT))



#: 一条带附加条件、多种结果的合法埋点明细
CONDITIONAL = """保存结果进统计。失败原因必须保留，拒绝时带上拒绝码。

| 统计点 | 业务动作 | 实际适用结果 |
|---|---|---|
| 保存结果 | 点保存 | 成功、拒绝 |
"""

CONTRACTS = {"interfaces": [{"name": "SaveService", "methods": [
    {"name": "save", "description": "统计点「保存结果」：成功报成功；拒绝报拒绝并带拒绝码与失败原因"}, {"name": "load"}]}]}

ACCEPTANCE = {"criteria": [{"id": "AC-001", "description": "拒绝时上报拒绝码", "verification_steps": ["触发一次拒绝"],
                            "expected_result": "统计里有一条拒绝，带拒绝码与失败原因", "ut_layer": "both",
                            "device_focus": "抓包看上报字段"}],
              "boundaries": [{"id": "BD-001", "scenario": "网络断开时保存", "expected": "报拒绝，失败原因为网络"}]}


class TheDeliveryCarriesTheOriginals(unittest.TestCase):
    """没有 plan.md 时送给作者与审查的是原文：明细正文与身份、方法说明、验收完整条目，不是只剩统计点名。"""

    def test_the_whole_body_the_methods_and_every_acceptance_field_are_there(self) -> None:
        got = "\n".join(run("m.statDelivery(design, plan.contracts, plan.acceptance)",
                            {**design([{**detail(body=CONDITIONAL), "id": "detail-save"}])},
                            plan={"contracts": CONTRACTS, "acceptance": ACCEPTANCE}))
        for needle in ("失败原因必须保留，拒绝时带上拒绝码", "| 保存结果 | 点保存 | 成功、拒绝 |",
                       "detail-save；依据 view:runtime/flow:invoice",
                       "`interfaces.SaveService.save`：统计点「保存结果」：成功报成功；拒绝报拒绝并带拒绝码与失败原因",
                       "criteria `AC-001`", "expected_result：统计里有一条拒绝，带拒绝码与失败原因", "ut_layer：both",
                       "device_focus：抓包看上报字段", 'verification_steps：["触发一次拒绝"]',
                       "boundaries `BD-001`", "scenario：网络断开时保存", "expected：报拒绝，失败原因为网络"):
            self.assertIn(needle, got)
        self.assertNotIn("SaveService.load", got, "没有说明的方法不列")

    def test_a_detail_outside_this_unit_sends_nothing(self) -> None:
        self.assertEqual([], run("m.statDelivery(design, null, null)", design([detail(refs=("view:runtime/flow:other",))])))


if __name__ == "__main__":
    unittest.main()
