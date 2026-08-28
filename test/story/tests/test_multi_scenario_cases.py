"""当前组合 Story Case 的静态覆盖与抗过拟合检查。

本文件不启动 Story CLI。标题与组织方式变化由 fixtures 验证，不再复制正式 Case。
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "test/story/cases"
FIXTURES = ROOT / "test/story/fixtures/narrative-variants"
CASE_IDS = {
    path.name for path in CASES.iterdir()
    if path.is_dir() and (path / "case.yaml").is_file()
}
VALID_START = {"story", "spec", "plan", "coding", "review", "ut", "testing"}
VALID_END = VALID_START | {"story-review"}
VARIANTS = ("brief.md", "role.md", "process.md")


def definition(case_id: str) -> dict:
    return yaml.safe_load((CASES / case_id / "case.yaml").read_text(encoding="utf-8"))


def case_text(case_id: str) -> str:
    workspace = CASES / case_id / "workspace"
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(workspace.rglob("*.md"))
    )


def case_directories() -> list[Path]:
    return sorted(
        path for path in CASES.iterdir()
        if path.is_dir() and (path / "case.yaml").is_file()
    )


class CaseShapeTest(unittest.TestCase):
    def test_formal_case_set_is_discovered_dynamically(self) -> None:
        self.assertEqual(CASE_IDS, {path.name for path in case_directories()})
        features = {definition(case_id)["ar"] for case_id in CASE_IDS}
        self.assertEqual(len(CASE_IDS), len(features))

    def test_every_case_uses_existing_schema_and_safe_workspace(self) -> None:
        for directory in case_directories():
            case = definition(directory.name)
            self.assertEqual(directory.name, case.get("id"))
            self.assertTrue(str(case.get("ar", "")).strip())
            self.assertIn(case.get("start_phase", "story"), VALID_START)
            self.assertIn(case.get("end_phase", "spec"), VALID_END)
            self.assertTrue(str(case.get("prompt", "")).strip())

            workspace = directory / "workspace"
            self.assertTrue(workspace.is_dir(), directory.name)
            for path in workspace.rglob("*"):
                self.assertFalse(path.is_symlink(), path)
                if path.is_file():
                    path.resolve().relative_to(workspace.resolve())

    def test_story_start_cases_have_inputs_but_no_expected_outputs(self) -> None:
        forbidden = {"story.md", "review.md", "spec.md", "acceptance.yaml",
                     "plan.md", "contracts.yaml", "use-cases.yaml"}
        for directory in case_directories():
            case = definition(directory.name)
            if case.get("start_phase", "story") != "story":
                continue
            inputs = [path for path in (directory / "workspace").rglob("*") if path.is_file()]
            self.assertTrue(any(part in {"RR", "SR", "inbox"}
                                for path in inputs for part in path.parts), directory.name)
            self.assertEqual([], [str(path) for path in inputs if path.name in forbidden])

    def test_prompts_do_not_contain_maintenance_or_expected_story_answers(self) -> None:
        for case_id in CASE_IDS:
            prompt = str(definition(case_id)["prompt"])
            for leaked in ("历史答案", "期望 Story"):
                self.assertNotIn(leaked, prompt, case_id)

    def test_prompts_do_not_drive_phase_advancement(self) -> None:
        """阶段推进归驱动器，不归被测模型。

        `run_case.py` 在每个阶段边界按 `end_phase` 算出下一个未闭环阶段并**指名下发**
        推进指令。prompt 里再写一遍阶段链，就是和驱动器双写：改终点时两边对不上
        （实测协调器记着「到 spec 为止」而 prompt 写着「继续完成 plan」，模型照 prompt 走），
        而且把「模型会不会自己一路跑」混进了观测——测的就不再是驱动器能不能推动它。

        `/story` 自己的动作（init / archive / review）不在 PHASE_ORDER 里，驱动器不发，
        必须写在 prompt 里，所以不在本判据的拦截范围内。
        """
        chain = re.compile(
            r"(依次完成|继续执行|随后执行\s*/?(spec|plan)|一路走到|"
            r"(spec|plan|coding|review)\s*(阶段)?(闭环)?后(继续|再|本轮)|"
            r"到\s*(spec|plan|coding|review|ut|testing)\s*(阶段)?为止|"
            r"不进入\s*(plan|coding|review|UT|真机))")
        for case_id in sorted(CASE_IDS):
            prompt = str(definition(case_id)["prompt"])
            hit = chain.search(prompt)
            self.assertIsNone(
                hit, f"{case_id} 的 prompt 在替驱动器安排阶段推进：「{hit.group(0) if hit else ''}」"
                     f"——终点只由 end_phase 定，prompt 只写起点动作与业务要求")


class NarrativeFixtureTest(unittest.TestCase):
    def test_three_styles_share_the_same_semantic_fact_tokens(self) -> None:
        required = {
            "COMPLETED", "PENDING", "FAILED", "PDF", "PNG", "maskCounterparty",
            "wallet_receipt_temp", "GET /wallet/transactions/{transactionId}",
            "IDLE", "RENDERING", "READY", "ERROR", "CANCELLED",
            "receipt_render_start", "receipt_render_success", "receipt_render_fail",
            "RECEIPT-001", "RECEIPT-002", "RECEIPT-003",
        }
        for name in VARIANTS:
            text = (FIXTURES / name).read_text(encoding="utf-8")
            self.assertEqual([], sorted(token for token in required if token not in text), name)
            self.assertIn("端侧渲染", text)
            self.assertIn("服务端生成", text)
            self.assertIn("上报失败", text)

    def test_styles_have_different_titles_and_organization(self) -> None:
        texts = [(FIXTURES / name).read_text(encoding="utf-8") for name in VARIANTS]
        heading_sets = [tuple(re.findall(r"^#{1,3}\s+(.+)$", text, re.M)) for text in texts]
        self.assertEqual(3, len(set(heading_sets)))
        self.assertIn("## 用户为什么需要它", texts[1])
        self.assertRegex(texts[2], r"(?m)^1\. ")
        self.assertNotIn("## 用户为什么需要它", texts[0])

    def test_narrative_variants_are_fixtures_not_cases(self) -> None:
        for case_id in ("narrative-brief", "narrative-role", "narrative-process"):
            self.assertFalse((CASES / case_id / "case.yaml").exists())


class CompositeCoverageTest(unittest.TestCase):
    def test_all_story_scenarios_have_a_composite_carrier(self) -> None:
        carriers = {
            "single_feature": {"pattern-image-review", "source-conflict-review"},
            "cross_component_and_sibling_context": {"pattern-image-review"},
            "preexisting_sibling_ar": {"split-two-ar"},
            "predeclared_and_interactive_split": {"split-interactive"},
            "supplement_arbitrary_filename_and_images": {"split-interactive"},
            "same_round_conflict_and_open_decision": {"source-conflict-review"},
            "local_image": {"pattern-image-review"},
            "review_archive_and_reflow": {"split-interactive"},
            "local_non_ar_start": {"source-conflict-review"},
            "normal_restriction_and_real_failure": {"pattern-image-review", "split-two-ar"},
            "interfaces_data_config_events_compatibility_delivery": {"pattern-image-review"},
            "plan_boundary_propagation": {"pattern-image-review", "split-two-ar"},
        }
        for scenario, expected in carriers.items():
            self.assertTrue(expected <= CASE_IDS, scenario)

    def test_pattern_case_contains_rich_business_and_delivery_material(self) -> None:
        text = case_text("pattern-image-review")
        for token in ("freezeTicketId", "支付中断", "通知失败", "queryLossEligibility",
                      "loss_report_recovery_context", "traffic_card_emergency_loss_enabled",
                      "loss_flow_recovery", "RTL", "回退"):
            self.assertIn(token, text)

    def test_split_case_combines_supplement_split_and_review(self) -> None:
        case = definition("split-interactive")
        self.assertIn(case["end_phase"], VALID_END)
        self.assertIn("文件名不带需求类型", case["prompt"])
        self.assertIn("本轮不会整体交付", case["prompt"])

        raw = (CASES / "split-interactive/case.yaml").read_text(encoding="utf-8")
        if case["end_phase"] == "spec":
            self.assertNotIn("/story archive", case["prompt"])
            # 评审回流是本 Case 的长期观测资产，收窄终点时不能顺手删掉——
            # 素材留着，并在文件里写明放开时怎么接回去。
            self.assertIn("review_feedback", raw)
            self.assertIn("放开到 review 时", raw)
        else:
            self.assertIn("/story archive", case["prompt"])
        docx = sorted((CASES / "split-interactive/workspace/inbox").glob("*.docx"))
        self.assertEqual(1, len(docx))
        sr = (CASES / "split-interactive/workspace/SR/design.md").read_text(encoding="utf-8")
        for token in ("wallet_auto_topup_contract", "扣款成功但写卡未完成",
                      "端侧不存在", "参与方", "不记录卡号"):
            self.assertIn(token, sr)
        script = yaml.safe_load((CASES / "split-interactive/interaction-script.yaml")
                                .read_text(encoding="utf-8"))
        self.assertEqual([1, 2, 3], [item["expected_turn"] for item in script["replies"]])
        self.assertIn("完成 /story review", script["replies"][-1]["text"])

    def test_local_conflict_case_combines_local_start_and_share_reentry(self) -> None:
        case = definition("source-conflict-review")
        self.assertFalse(str(case["ar"]).startswith("AR"))
        detail = yaml.safe_load((CASES / "source-conflict-review/workspace/AR/detail.json")
                                .read_text(encoding="utf-8"))
        self.assertEqual(case["ar"], detail["reqNo"])
        self.assertEqual("local-workspace", detail["source"])
        rr = (CASES / "source-conflict-review/workspace/RR/prd.md").read_text(encoding="utf-8")
        sr = (CASES / "source-conflict-review/workspace/SR/design.md").read_text(encoding="utf-8")
        self.assertIn("网络不可用时仍可打开", rr)
        self.assertIn("网络不可用时一律阻止查看", sr)
        self.assertIn("shareInProgress", sr)
        self.assertIn("不同登录账号", rr)
        self.assertIn("本轮尚未决定", rr)
        self.assertNotIn("产品已确认", case["prompt"])
        self.assertIn("产品已确认", case["suggested_reply"])
        self.assertIn("保持 open", case["suggested_reply"])
        self.assertIn("不要要求需求系统 token", case["prompt"])

    def test_split_two_ar_keeps_handoff_lifecycle_and_failures(self) -> None:
        text = case_text("split-two-ar")
        for token in ("freezeTicketId", "共享挂失上下文", "订单确认前不扣费",
                      "地址校验失败", "订单创建失败", "联调与开放"):
            self.assertIn(token, text)

    def test_local_markdown_images_resolve_inside_their_workspace(self) -> None:
        for directory in case_directories():
            workspace = directory / "workspace"
            for markdown in workspace.rglob("*.md"):
                text = markdown.read_text(encoding="utf-8")
                for target in re.findall(r"!\[[^\]]+\]\(([^)]+)\)", text):
                    if re.match(r"^(?:https?:|data:|//)", target):
                        continue
                    resolved = (markdown.parent / target.split("#", 1)[0]).resolve()
                    resolved.relative_to(workspace.resolve())
                    self.assertTrue(resolved.is_file(), f"{markdown}: {target}")


if __name__ == "__main__":
    unittest.main()
