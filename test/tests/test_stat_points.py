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

MODULE = (DEV_EXT / "base" / "hooks" / "shared" / "stat-points.mjs").resolve().as_uri()

EVENT = """总述：开票结果进成功率统计。

#### 电子发票开具成功率

成功数 / 发起数。

| 统计点 | 业务动作 | 实际适用结果 |
|---|---|---|
| 开票流程 / 提交 | 点提交 | 成功、失败 |
| 开票流程 / 回执 | 收到回执 | 成功 |
"""

PLAN = """# 计划

## 宿主扩展（可选）

### 埋点

| 统计点 | 结果 | 责任方法 |
|---|---|---|
| 开票流程 / 提交 | 成功 | InvoiceService.submit |
| 开票流程/提交 | 失败 | `InvoiceService.submit` |
"""

BARE_PLAN = """# 计划

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

    def test_s41_distinct_columns_annotated_headers_multi_methods_and_order_swap(self) -> None:
        swapped = (
            "# 计划\n\n## 宿主扩展（可选）\n\n### 埋点\n\n"
            "| 责任方法（接口.方法） | 结果 | 统计点（主点位） |\n|---|---|---|\n"
            "| Gateway.save、Gateway.flush | 成功 | 保存结果 |\n"
            "| `Gateway.save` | 失败 | 保存结果 |\n"
        )
        rows = run("m.planStatRows(plan)", plan=swapped)
        self.assertEqual(
            [["保存结果", ["Gateway.save", "Gateway.flush"]], ["保存结果", ["Gateway.save"]]],
            [[r["point"], r["methods"]] for r in rows],
        )

    def test_s41_single_column_and_historical_examples_never_fill_obligations(self) -> None:
        single_col = "# 计划\n\n| 统计点与责任方法示例 |\n|---|\n| Gateway.save |\n"
        self.assertEqual([], run("m.planStatRows(plan)", plan=single_col))

        hist_only = "# 计划\n\n| 历史统计点示例 | 原责任方法示例 |\n|---|---|\n| Gateway.save | Gateway.save |\n"
        self.assertEqual([], run("m.planStatRows(plan)", plan=hist_only))

        hist_outside_empty_events = (
            "# 计划\n\n## 1. 历史参考\n\n| 统计点 | 责任方法 |\n|---|---|\n| 旧点 | OldService.save |\n\n"
            "## 宿主扩展（可选）\n\n### 埋点\n\n待补充当前逐点表。\n"
        )
        self.assertEqual([], run("m.planStatRows(plan)", plan=hist_outside_empty_events))

    def test_s41_historical_and_current_coexist_reads_only_current_section(self) -> None:
        coexist = (
            "# 计划\n\n## 1. 历史方案示例\n\n| 历史统计点示例 | 原责任方法示例 |\n|---|---|\n| 旧点 | OldService.save |\n\n"
            "| 统计点 | 责任方法 |\n|---|---|\n| 历史对照点 | Legacy.run |\n\n"
            "## 宿主扩展（可选）\n\n### 埋点\n\n| 统计点 | 结果 | 责任方法 |\n|---|---|---|\n"
            "| 当前提交 | 成功 | Gateway.save |\n"
        )
        rows = run("m.planStatRows(plan)", plan=coexist)
        self.assertEqual([["当前提交", ["Gateway.save"]]], [[r["point"], r["methods"]] for r in rows])

    def test_s41_r4_rejects_history_subsections_no_full_doc_fallback_and_accepts_colon_annotation(self) -> None:
        """S41 R4：拒收「历史埋点示例」节与「埋点」下「历史示例」子节，完整 Plan 缺职责段不回捞全文，支持「责任方法：接口.方法」附注。"""
        hist_sub = (
            "# 计划\n\n## 宿主扩展（可选）\n\n### 历史埋点示例\n\n"
            "| 统计点 | 责任方法 |\n|---|---|\n| 当前提交 | Gateway.save |\n"
        )
        self.assertEqual([], run("m.planStatRows(plan)", plan=hist_sub))

        nested_hist = (
            "# 计划\n\n## 宿主扩展（可选）\n\n### 埋点\n\n#### 历史示例\n\n"
            "| 统计点 | 责任方法 |\n|---|---|\n| 当前提交 | Gateway.save |\n"
        )
        self.assertEqual([], run("m.planStatRows(plan)", plan=nested_hist))

        # 完整 Plan 缺少宿主扩展章/埋点段时，planStatRows 不回捞全文
        self.assertEqual([], run("m.planStatRows(plan)", plan=BARE_PLAN))
        self.assertEqual([0, 2], run("m.statTableCols(['统计点：主点位', '结果', '责任方法：接口.方法'], ['统计点', '责任方法'])"))
        self.assertIsNone(run("m.statTableCols(['统计点/责任方法', '结果'], ['统计点', '责任方法'])"))

        # 冒号附注列名（责任方法：接口.方法）合法识别，单列双职责（统计点/责任方法）仍拒收
        colon_plan = (
            "# 计划\n\n## 宿主扩展（可选）\n\n### 埋点\n\n"
            "| 统计点：主点位 | 结果 | 责任方法：接口.方法 |\n|---|---|---|\n"
            "| 当前提交 | 成功 | Gateway.save |\n"
        )
        self.assertEqual([["当前提交", ["Gateway.save"]]], [[r["point"], r["methods"]] for r in run("m.planStatRows(plan)", plan=colon_plan)])
        dual_col = "# 计划\n\n## 宿主扩展（可选）\n\n### 埋点\n\n| 统计点/责任方法 | 结果 |\n|---|---|\n| Gateway.save | 成功 |\n"
        self.assertEqual([], run("m.planStatRows(plan)", plan=dual_col))

        # S41 R2：「### 埋点（历史参考）」不是规范「### 埋点」小节，不承担本期义务；规范「### 埋点」后附同列名历史子表只取当前表
        hist_note = (
            "# 计划\n\n## 宿主扩展（可选）\n\n### 埋点（历史参考）\n\n"
            "| 统计点 | 责任方法 |\n|---|---|\n| 当前提交 | Gateway.save |\n"
        )
        self.assertEqual([], run("m.planStatRows(plan)", plan=hist_note))
        both = (
            "# 计划\n\n## 宿主扩展（可选）\n\n### 埋点\n\n"
            "| 统计点 | 责任方法 |\n|---|---|\n| 当前提交 | Gateway.save |\n\n"
            "#### 历史对照\n\n| 统计点 | 责任方法 |\n|---|---|\n| 旧点 | Legacy.old |\n"
        )
        self.assertEqual([["当前提交", ["Gateway.save"]]], [[r["point"], r["methods"]] for r in run("m.planStatRows(plan)", plan=both)])

    def test_s07_annotated_method_headers_with_role_word_or_example_and_ambiguity_diagnostics(self) -> None:
        """S07：按主列名识别，附注含另一职责词或「示例」不再误拒；单格混合两职责与重复职责列报行号和实际表头。"""
        for header in (
            "责任方法（该统计点的归属）",
            "责任方法（示例：InvoiceService.submit）",
            "责任方法：接口.方法",
            "责任方法 - 该统计点落点",
        ):
            with self.subTest(header=header):
                plan = (
                    "# 计划\n\n## 宿主扩展（可选）\n\n### 埋点\n\n"
                    f"| {header} | 结果 | 统计点（含示例说明） |\n|---|---|---|\n"
                    "| Gateway.save | 成功 | 当前提交 |\n"
                )
                rows = run("m.planStatRows(plan)", plan=plan)
                self.assertEqual([["当前提交", ["Gateway.save"]]], [[r["point"], r["methods"]] for r in rows])
                self.assertEqual([], run("m.planStatTableIssues(plan)", plan=plan))

        # 单格混合两职责：不认作有效逐点表，并给出精确行号与实际表头
        mixed = "# 计划\n\n## 宿主扩展（可选）\n\n### 埋点\n\n| 统计点/责任方法 | 结果 |\n|---|---|\n| Gateway.save | 成功 |\n"
        self.assertEqual([], run("m.planStatRows(plan)", plan=mixed))
        issues = run("m.planStatTableIssues(plan)", plan=mixed)
        self.assertEqual(1, len(issues), issues)
        self.assertIn("第 7 行", issues[0])
        self.assertIn("| 统计点/责任方法 | 结果 |", issues[0])
        self.assertIn("结构歧义", issues[0])

        # 重复同职责列：不静默猜第一列，报结构歧义
        dup_col = (
            "# 计划\n\n## 宿主扩展（可选）\n\n### 埋点\n\n"
            "| 统计点 | 责任方法（主） | 责任方法（备） |\n|---|---|---|\n"
            "| 当前提交 | Gateway.save | Gateway.backup |\n"
        )
        self.assertEqual([], run("m.planStatRows(plan)", plan=dup_col))
        dup_issues = run("m.planStatTableIssues(plan)", plan=dup_col)
        self.assertEqual(1, len(dup_issues), dup_issues)
        self.assertIn("第 7 行", dup_issues[0])
        self.assertIn("责任方法", dup_issues[0])
        self.assertIn("出现 2 个「责任方法」列", dup_issues[0])

    def test_s22_mixed_connector_and_valid_plus_mixed_tables_are_diagnosed_without_wordlist(self) -> None:
        """S22 R2：去掉有限连接词黑名单；未拆两职责却承载统计点/方法数据的表（含「统计点以及责任方法」），
        无论单独出现还是并排在合法表之后均报精确行号、原表头与原表行预览，且行不计入已覆盖；纯说明表继续放行。"""
        # 1) 仅有「统计点以及责任方法」混合表
        mixed_only = (
            "# 计划\n\n## 宿主扩展（可选）\n\n### 埋点\n\n"
            "| 统计点以及责任方法 | 场景 |\n|---|---|\n"
            "| 余额刷新 HomeRepository.refreshBalance | 返回首页 |\n"
        )
        self.assertEqual([], run("m.planStatRows(plan)", plan=mixed_only))
        only_issues = run("m.planStatTableIssues(plan)", plan=mixed_only)
        self.assertEqual(1, len(only_issues), only_issues)
        self.assertIn("第 7 行", only_issues[0])
        self.assertIn("| 统计点以及责任方法 | 场景 |", only_issues[0])
        self.assertIn("HomeRepository.refreshBalance", only_issues[0])

        # 2) 合法逐点表 + 纯说明表 + 追加的混合数据表：合法表不掩盖混合表，纯说明表不误报
        combo = (
            "# 计划\n\n## 宿主扩展（可选）\n\n### 埋点\n\n"
            "| 统计点与责任方法说明 | 备注 |\n|---|---|\n"
            "| 仅记录主链路结果 | 辅助说明，无方法调用 |\n\n"
            "| 统计点 | 责任方法 | 结果 |\n|---|---|---|\n"
            "| 余额刷新 | HomeRepository.refreshBalance | 成功 |\n\n"
            "| 统计点以及责任方法 | 场景 |\n|---|---|\n"
            "| 余额刷新 HomeRepository.refreshBalance | 返回首页 |\n"
        )
        rows = run("m.planStatRows(plan)", plan=combo)
        self.assertEqual([["余额刷新", ["HomeRepository.refreshBalance"]]], [[r["point"], r["methods"]] for r in rows])
        combo_issues = run("m.planStatTableIssues(plan)", plan=combo)
        self.assertEqual(1, len(combo_issues), combo_issues)
        self.assertIn("第 15 行", combo_issues[0])
        self.assertIn("| 统计点以及责任方法 | 场景 |", combo_issues[0])
        self.assertNotIn("统计点与责任方法说明", combo_issues[0])



#: 一条带附加条件、多种结果的合法埋点明细
CONDITIONAL = """保存结果进统计。失败原因必须保留，拒绝时带上拒绝码。

| 统计点 | 业务动作 | 实际适用结果 |
|---|---|---|
| 保存结果 | 点保存 | 成功、拒绝 |
"""

CONTRACTS = {"interfaces": [{"class": "SaveService", "methods": [
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
