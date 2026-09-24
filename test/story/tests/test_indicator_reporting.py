"""埋点以指标为单位：spec §9.4 的结构、plan 埋点逐统计点落实、作者任务包与审查并列。

锁住：
  ① spec 门禁只核 9.4 的结构——总述在首个指标前，表都在某个指标（####）下，每个指标有带「统计点」列的点位表；
     说明表不算点位，统计点列不必在第一列；写「不涉及：<依据>」的整节不判；不核指标名、统计点名与结果写法；
  ② plan 门禁核三件事：spec 的每个统计点在 plan 埋点小节有结果行（一点可以多行）；每条结果行的责任方法
     能解析到契约的 `interfaces[].methods[]`；spec 把规约落在某个统计点上时，该点结果行的责任方法挂了那条 must。
     照抄 spec 表的 plan（没有责任方法）FAIL，逐点落实的形状 PASS；spec 不涉及时显式未执行；
     走 /story 而 spec 缺埋点一节或没有点位表时报上游缺口，没走 /story 的按原范围跳过；
  ③ plan 任务包给 §9.4 原文与各指标的统计点，逐结果落实的作业只在作者页；
  ④ 审查任务把 spec 的每个统计点与 plan 的全部结果行按名并列，共用的点每个指标下都看得到，对不上的两边各自单列；
  ⑤ 激活清单里没有项目事实时，任务包、门禁、审查照常，只说明没有事实可核。
全部在中性工作区里跑：机制不认识任何项目知识专名。
"""
from __future__ import annotations

import json
import subprocess
import unittest

import test_neutral_knowledge as nk

SPEC = """# {feature} spec

## 9. 技术契约

### 9.1 端云接口

| 名称 | 用途 |
|---|---|
| 预约接口 | 查时段与提交预约 |

### 9.4 埋点

采集预约与核销的结果分类，供运维看成功率；页面进入与点击已由工程自动采集覆盖，不重复列；字段只带阶段与结果分类。

#### 预约成功率（预约流程）

衡量从提交预约到服务方确认的比例。要算它，需要查询时段、提交预约两点的结果。

| 统计点（步骤/子点） | 业务动作 | 实际适用结果 | 本端何时得知 | 已有或新增 | 代码现状 |
|---|---|---|---|---|---|
| 查询时段 | 进入预约时查可约时段 | 有时段 / 无时段 / 查询失败 | 查询请求返回时 | 新增 | 检索零命中 |
| 提交预约 | 提交预约请求 | 成功 / 失败 / 用户取消 | 提交请求返回时 | 新增 | 检索零命中 |

#### 到场核销率（核销流程）

衡量预约后到场核销的比例。

| 统计点（步骤/子点） | 业务动作 | 实际适用结果 | 本端何时得知 | 已有或新增 | 代码现状 |
|---|---|---|---|---|---|
| 到场核销 | 服务方扫码核销 | 已核销 | 刷新列表回查状态时 | 新增 | 检索零命中 |

- 核销在服务方发生，本端只在刷新列表时得知；超期未到由服务方统计。

## 10. 规约约束要求

<!-- 由 knowledge-use.yaml 生成 -->

## 11. 设计模式候选登记

<!-- 由 knowledge-use.yaml 生成 -->
"""

#: 逐统计点落实的 plan 埋点小节（金样形状）；`rows` 覆写统计点表。
PLAN = """# 计划

## 知识决策（设计输入）

略。

## 6. 服务层接口定义

### 埋点

| 指标（流程） | 责任方法 |
|---|---|
| 预约成功率（预约流程） | BookingRepo.querySlots、BookingFlow.submit |

#### 预约成功率（预约流程）

{rows}
"""

ROWS = """| 统计点 | 结果 | 本端何时得知 | 责任方法 | 去重与耗时 | 验证 |
|---|---|---|---|---|---|
| 查询时段 | 有时段 / 无时段 / 查询失败 | 查询请求返回时 | BookingRepo.querySlots | 一次进入一次 | 三种结果各一条 |
| 提交预约 | 成功 / 失败 / 用户取消 | 提交请求返回时 | BookingFlow.submit | 同一幂等键只记一次；耗时=请求起止 | 三种结果各一条 |
| 到场核销 | 已核销 | 刷新列表回查状态时 | BookingRepo.refreshList | 同一预约只记一次 | 刷新前后状态变化各一条 |"""

#: 同一统计点按结果分行：提交预约三种结果各一行，顺序即作者写的顺序。
MULTI = """| 统计点 | 结果 | 责任方法 | 验证 |
|---|---|---|---|
| 查询时段 | 有时段 / 无时段 / 查询失败 | BookingRepo.querySlots | 三种各一条 |
| 提交预约 | 成功 | BookingFlow.submit | 预期一条成功 |
| 提交预约 | 失败 | BookingFlow.submit | 预期一条失败 |
| 提交预约 | 用户取消 | BookingFlow.submit | 预期一条取消 |
| 到场核销 | 已核销 | BookingRepo.refreshList | 一条 |"""

CONTRACTS = """interfaces:
  - name: BookingRepo
    methods:
      - name: querySlots
      - name: refreshList
  - name: BookingFlow
    methods:
      - name: submit
        must:
          - rule: NEU-01
            text: 提交预约的各实际结果确定时按项目协议记录一次
            verify: ut
"""

#: NEU-01 落在统计点「提交预约」上（§10 的落点引统计点名）。
JUDGEMENT = ("  - id: NEU-01\n    applicable: true\n    requirement: 提交预约的结果按项目协议记录一次\n"
             "    contract: 提交预约\n  - id: NEU-02\n    applicable: false\n    reason: 本需求没有重试路径")


def js(module, expr: str) -> str:
    proc = nk.node("--input-type=module", "-e",
                   f"const m = await import({nk.as_url(module)}); process.stdout.write(JSON.stringify({expr}));")
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


class TheSpecSectionIsShapedByIndicator(unittest.TestCase):
    """① 只核结构，不核名字与行数。"""

    SHAPE = nk.EXT / "hooks" / "spec" / "post_check.mjs"

    def problems(self, body: str) -> list[str]:
        return js(self.SHAPE, f"m.indicatorShape('§9「埋点」', {json.dumps(body.split(chr(10)))})")

    def test_an_overview_and_indicators_with_rows_pass(self) -> None:
        body = SPEC.split("### 9.4 埋点", 1)[1].split("## 10.", 1)[0]
        self.assertEqual([], self.problems(body))

    def test_a_table_outside_any_indicator_is_named(self) -> None:
        got = self.problems("总述一句。\n\n| 统计点 | 结果 |\n|---|---|\n| 提交 | 成功 |")
        self.assertTrue(any("不在指标小标题" in p for p in got), got)

    def test_a_missing_overview_is_named(self) -> None:
        got = self.problems("#### 提交成功率（提交流程）\n\n| 统计点 | 结果 |\n|---|---|\n| 提交 | 成功 |")
        self.assertTrue(any("缺总述" in p for p in got), got)

    def test_an_indicator_without_rows_is_named(self) -> None:
        got = self.problems("总述一句。\n\n#### 提交成功率（提交流程）\n\n衡量提交成功的比例。")
        self.assertTrue(any("下没有统计点" in p for p in got), got)

    def test_an_explanation_table_is_not_a_point_table(self) -> None:
        got = self.problems("总述一句。\n\n#### 提交成功率（提交流程）\n\n| 口径 | 说明 |\n|---|---|\n| 分母 | 发起的提交 |")
        self.assertTrue(any("下没有统计点" in p for p in got), got)

    def test_the_point_column_need_not_come_first(self) -> None:
        body = ("总述一句。\n\n#### 提交成功率（提交流程）\n\n| 口径 | 说明 |\n|---|---|\n| 分母 | 发起的提交 |\n\n"
                "| 实际业务结果 | 统计点 | 本端获知时机 |\n|---|---|---|\n| 已受理、拒绝 | 提交/请求 | 响应返回时 |")
        self.assertEqual([], self.problems(body))
        got = js(nk.EXT / "hooks" / "shared" / "stat-points.mjs",
                 f"m.specStatPoints({json.dumps('### 9.4 埋点' + chr(10) + chr(10) + body)})")
        self.assertEqual(["提交/请求"], got["groups"][0]["points"])
        self.assertEqual(["提交/请求", "已受理、拒绝", "响应返回时"], got["groups"][0]["rows"][0])
        self.assertIn("发起的提交", got["text"], "说明表留在原文里给模型读")

    def test_not_applicable_is_a_conclusion(self) -> None:
        self.assertEqual([], self.problems("不涉及：本需求没有需要统计的业务步骤。"))


class ReportingCase(nk.NeutralKnowledgeCase):
    """中性工作区：一份以指标组织的 spec §9.4、一份判断（NEU-01 落在「提交预约」）、契约与 plan。"""

    def setUp(self) -> None:
        super().setUp()
        self.spec_path.write_text(SPEC.format(feature=nk.FEATURE), encoding="utf-8")
        self.write_use(neutral=JUDGEMENT)
        proc = self.render()
        self.assertEqual(0, proc.returncode, proc.stderr)
        (self.feature_root / "plan").mkdir(parents=True, exist_ok=True)
        self.write_plan(ROWS)
        (self.feature_root / "contracts.yaml").write_text(CONTRACTS, encoding="utf-8")

    def write_plan(self, rows: str) -> None:
        (self.feature_root / "plan" / "plan.md").write_text(PLAN.format(rows=rows), encoding="utf-8")

    def plan_check(self) -> str:
        proc = nk.node("--input-type=module", "-e",
                       f"const hook = (await import({nk.as_url(self.ext / 'hooks/plan/post_check.mjs')})).default;"
                       f"const out = await hook({{ phase: 'plan', feature: {json.dumps(nk.FEATURE)},"
                       f" projectRoot: {json.dumps(self.root.as_posix())} }});"
                       "process.stdout.write(JSON.stringify(out));")
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout or "{}").get("message") or ""

    def task_package(self) -> str:
        proc = subprocess.run(["node", str(self.ext / "hooks/plan/author.mjs"), "--feature", nk.FEATURE],
                              cwd=self.root, capture_output=True, text=True, encoding="utf-8", timeout=90)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return proc.stdout

    def review_task(self) -> str:
        proc = nk.node("--input-type=module", "-e",
                       f"const pv = (await import({nk.as_url(self.ext / 'hooks/shared/pre_verifier.mjs')})).default;"
                       f"const out = await pv({{ phase: 'plan', feature: {json.dumps(nk.FEATURE)},"
                       f" projectRoot: {json.dumps(self.root.as_posix())} }});"
                       "process.stdout.write(out.promptFragments.join('\\n'));")
        self.assertEqual(0, proc.returncode, proc.stderr)
        return proc.stdout

    def drop_stat_section(self) -> None:
        text = self.spec_path.read_text(encoding="utf-8")
        start, end = text.index("### 9.4 埋点"), text.index("## 10.")
        self.spec_path.write_text(text[:start] + text[end:], encoding="utf-8")

    def drop_facts(self) -> None:
        """激活清单里去掉全部项目事实：知识换成没有事实的一份。"""
        manifest = self.ext / "manifest.yaml"
        keep = [l for l in manifest.read_text(encoding="utf-8").split("\n")
                if not ("knowledge/facts/" in l and not l.strip().endswith("README.md"))]
        manifest.write_text("\n".join(keep), encoding="utf-8")


class ThePlanLandsEveryStatisticPoint(ReportingCase):
    """② 只核对应、引用与挂点。"""

    def test_the_point_by_point_shape_passes(self) -> None:
        message = self.plan_check()
        for phrase in ("没有对应行", "没写责任方法", "找不到", "没挂这条 must", "没有「埋点」小节"):
            self.assertNotIn(phrase, message)

    def test_a_plan_that_copies_the_spec_fails(self) -> None:
        """照抄 spec 的表：统计点都在，却没有一列是抄 spec 填不上的——责任方法。"""
        self.write_plan("| 统计点 | 业务动作 | 实际适用结果 | 本端何时得知 | 已有或新增 |\n|---|---|---|---|---|\n"
                        "| 查询时段 | 进入预约时查可约时段 | 有时段 / 无时段 / 查询失败 | 查询请求返回时 | 新增 |\n"
                        "| 提交预约 | 提交预约请求 | 成功 / 失败 / 用户取消 | 提交请求返回时 | 新增 |\n"
                        "| 到场核销 | 服务方扫码核销 | 已核销 | 刷新列表回查状态时 | 新增 |")
        message = self.plan_check()
        self.assertIn("没写责任方法", message)
        self.assertNotIn("没有对应行", message, "统计点是齐的，缺的只是落实")

    def test_a_missing_point_is_named(self) -> None:
        self.write_plan("\n".join(l for l in ROWS.split("\n") if "到场核销" not in l))
        message = self.plan_check()
        self.assertIn("没有对应行", message)
        self.assertIn("到场核销", message)

    def test_an_undeclared_method_is_named(self) -> None:
        self.write_plan(ROWS.replace("BookingRepo.refreshList", "BookingRepo.pollStatus"))
        self.assertIn("BookingRepo.pollStatus 在 contracts.yaml", self.plan_check())

    def test_a_statistic_obligation_left_off_its_method_is_named(self) -> None:
        """spec 把 NEU-01 落在「提交预约」上，plan 把它的责任方法写成另一个没挂义务的方法。"""
        self.write_plan(ROWS.replace("| BookingFlow.submit |", "| BookingRepo.querySlots |"))
        self.assertIn("没挂这条 must", self.plan_check())

    def test_a_spec_that_does_not_apply_is_an_explicit_skip(self) -> None:
        text = self.spec_path.read_text(encoding="utf-8")
        start, end = text.index("### 9.4 埋点"), text.index("## 10.")
        self.spec_path.write_text(text[:start] + "### 9.4 埋点\n\n不涉及：本需求没有需要统计的业务步骤。\n\n"
                                  + text[end:], encoding="utf-8")
        self.assertIn("埋点逐统计点落实（spec 的埋点一节写了不涉及）", self.plan_check())

    def test_one_point_may_have_a_row_per_result(self) -> None:
        self.write_plan(MULTI)
        message = self.plan_check()
        for phrase in ("没有对应行", "没写责任方法", "找不到", "没挂这条 must"):
            self.assertNotIn(phrase, message)

    def test_a_bad_method_is_named_on_its_own_result_row(self) -> None:
        self.write_plan(MULTI.replace("| 用户取消 | BookingFlow.submit |", "| 用户取消 | BookingFlow.cancelSubmit |"))
        message = self.plan_check()
        self.assertIn("「提交预约」第 3 条结果行的责任方法 BookingFlow.cancelSubmit", message)
        self.assertNotIn("第 1 条结果行", message, "另外两行合法")

    def test_a_story_spec_without_the_section_is_an_upstream_gap(self) -> None:
        self.drop_stat_section()
        (self.feature_root / "AR" / "story-src").mkdir(parents=True, exist_ok=True)
        (self.feature_root / "AR" / "story-src" / "story-flow.json").write_text("{}", encoding="utf-8")
        self.assertIn("spec 没有埋点一节，plan 的埋点无从承接", self.plan_check())

    def test_a_direct_spec_without_the_section_keeps_its_scope(self) -> None:
        self.drop_stat_section()
        self.assertIn("本需求没走 /story，spec 未提供统计设计", self.plan_check())

    def test_a_section_without_point_tables_is_a_structure_gap(self) -> None:
        text = self.spec_path.read_text(encoding="utf-8")
        start, end = text.index("### 9.4 埋点"), text.index("## 10.")
        self.spec_path.write_text(text[:start] + "### 9.4 埋点\n\n总述一句。\n\n#### 预约成功率（预约流程）\n\n只有一段话。\n\n"
                                  + text[end:], encoding="utf-8")
        self.assertIn("没有指标点位表", self.plan_check())


class TheAuthorAndReviewerGetThePoints(ReportingCase):
    """③ 任务包逐条列问题；④ 审查按名并列；⑤ 没有项目事实时照常。"""

    def test_the_task_package_lists_each_point_with_its_questions(self) -> None:
        out = self.task_package()
        self.assertIn("衡量从提交预约到服务方确认的比例", out, "spec 原文没照列")
        self.assertIn("「四、埋点」的作业逐个业务结果落实", out)
        self.assertNotIn("每个统计点都回答这几问", out, "作业只在作者页写一处")
        self.assertIn("- **预约成功率（预约流程）**：查询时段、提交预约", out)
        self.assertIn("- **到场核销率（核销流程）**：到场核销", out)
        self.assertIn("neutral-facts.md", out)

    def test_the_reviewer_sees_both_sides_of_every_point(self) -> None:
        self.write_plan("\n".join(l for l in ROWS.split("\n") if "到场核销" not in l))
        task = self.review_task()
        self.assertIn("埋点逐统计点并列", task)
        row = next(l for l in task.split("\n") if l.startswith("| 预约成功率") and "提交预约" in l)
        self.assertIn("BookingFlow.submit", row, "spec 行旁边没有 plan 的那一行")
        self.assertIn("（plan 没有这个统计点）", task, "对不上的统计点没有单列")

    def test_the_reviewer_sees_every_result_row_in_order(self) -> None:
        self.write_plan(MULTI)
        row = next(l for l in self.review_task().split("\n") if l.startswith("| 预约成功率") and "提交预约" in l)
        self.assertLess(row.index("成功"), row.index("失败"))
        self.assertLess(row.index("失败"), row.index("用户取消"), "三行都在、顺序保留")

    def test_a_point_shared_by_two_indicators_shows_under_both(self) -> None:
        text = self.spec_path.read_text(encoding="utf-8").replace(
            "| 到场核销 | 服务方扫码核销 |", "| 提交预约 | 提交预约请求 | 成功 | 提交请求返回时 | 已有 | 同上 |\n| 到场核销 | 服务方扫码核销 |")
        self.spec_path.write_text(text, encoding="utf-8")
        self.write_plan(MULTI)
        task = self.review_task()
        rows = [l for l in task.split("\n") if "提交预约" in l and l.startswith(("| 预约成功率", "| 到场核销率"))]
        self.assertEqual(2, len(rows), rows)
        self.assertTrue(all("用户取消" in r for r in rows), "第二个指标没看到同一组 plan 行")
        self.assertNotIn("（plan 没有这个统计点）", task)

    def test_an_identity_written_as_a_rule_reference_reaches_the_reviewer(self) -> None:
        """把身份写成引用知识条款：并列表原样带过去，overlay 按没落地判。"""
        self.write_plan(ROWS.replace("一次进入一次", "身份按知识首次登记"))
        self.assertIn("身份按知识首次登记", self.review_task())
        overlay = (self.ext / "rules" / "plan-rules.overlay.yaml").read_text(encoding="utf-8")
        self.assertIn("「按知识条款首次登记」这类引用规则代替给值的，按没落地判", overlay)

    def test_a_spec_that_does_not_apply_says_so_everywhere(self) -> None:
        """spec §9.4 写不涉及：任务包、审查、门禁各自显式说不适用，不是静默跳过。"""
        text = self.spec_path.read_text(encoding="utf-8")
        start, end = text.index("### 9.4 埋点"), text.index("## 10.")
        self.spec_path.write_text(text[:start] + "### 9.4 埋点\n\n不涉及：本需求没有需要统计的业务步骤。\n\n"
                                  + text[end:], encoding="utf-8")
        self.write_use(neutral=JUDGEMENT.replace("contract: 提交预约", "contract: 预约接口"))
        self.assertIn("plan 的埋点小节写一行「本需求不涉及：<依据>」", self.task_package())
        self.assertIn("核这条依据是否成立", self.review_task())
        self.assertIn("埋点逐统计点落实（spec 的埋点一节写了不涉及）", self.plan_check())

    def test_without_project_facts_everything_still_runs(self) -> None:
        self.drop_facts()
        self.assertIn("激活清单里没有项目事实", self.task_package())
        self.assertIn("激活清单里没有项目事实", self.review_task())
        message = self.plan_check()
        self.assertNotIn("没写责任方法", message)
        self.assertNotIn("没有对应行", message)


if __name__ == "__main__":
    unittest.main()
