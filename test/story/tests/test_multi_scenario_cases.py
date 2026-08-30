"""当前组合 Story Case 的静态覆盖与抗过拟合检查。

本文件不启动 Story CLI。标题与组织方式变化由 fixtures 验证，不再复制正式 Case。
"""
from __future__ import annotations

import json
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
    """本 Case 全部可读材料：需求系统上挂的 + 起跑时就在工作区的。

    补料是二进制文档，不在这里；它的内容由投放链路自己保证。
    """
    return "\n".join(
        path.read_text(encoding="utf-8")
        for source in ("system", "workspace")
        for path in sorted((CASES / case_id / source).rglob("*.md"))
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

            # 材料分三处，都可以为空，但不能三处都空——那样这个 Case 没有输入。
            sources = [directory / name
                       for name in ("system", "workspace", "supplements")]
            self.assertTrue(any(source.is_dir() for source in sources), directory.name)
            for source in sources:
                if not source.is_dir():
                    continue
                for path in source.rglob("*"):
                    self.assertFalse(path.is_symlink(), path)
                    if path.is_file():
                        path.resolve().relative_to(source.resolve())

    def test_story_start_cases_have_inputs_but_no_expected_outputs(self) -> None:
        """从取材起手的 Case 要有上游材料，且不能预先摆好下游产物。"""
        forbidden = {"story.md", "review.md", "spec.md", "acceptance.yaml",
                     "plan.md", "contracts.yaml", "use-cases.yaml"}
        for directory in case_directories():
            case = definition(directory.name)
            if case.get("start_phase", "story") != "story":
                continue
            inputs = [path
                      for name in ("system", "workspace", "supplements")
                      for path in (directory / name).rglob("*")
                      if path.is_file()]
            self.assertTrue(inputs, directory.name)
            # `system/` 下 `<AR号>/design.md` 是需求系统上的开发单正文（上游预填的
            # 提取件），不是本轮该产出的 story/spec——按目录判，不按文件名判。
            in_workspace = [path for path in inputs
                            if (directory / "workspace") in path.parents]
            self.assertEqual([], [str(path) for path in in_workspace
                                  if path.name in forbidden])

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
    """两个 Case 合起来要覆盖的能力点，逐条有承载者。

    能力点写成清单不是为了好看：删一个 Case、改一份材料时，看得见丢的是哪一条。
    """

    def test_every_story_capability_has_a_carrier(self) -> None:
        # 「上游已拆两张单与兄弟交接」由退役的 traffic-card-loss（金样回归锚，
        # case.retired.yaml，不进常规 suite）承载，不在此表。
        carriers = {
            "系统按单号拉取": {"auto-topup"},
            "没有系统单据的本地起手": {"car-key-sharing"},
            "系统只给 md，界面材料要另外要": {"auto-topup"},
            "占位件识别与按需补料": {"auto-topup", "car-key-sharing"},
            "docx 转正文并抽图": {"auto-topup", "car-key-sharing"},
            "同轮材料冲突与人工定源": {"car-key-sharing"},
            "材料写明尚未决定的问题保持 open": {"car-key-sharing"},
            "归档到系统与评审回稿处置": {"auto-topup"},
            "多方协作与多步分支流程": {"car-key-sharing"},
            "知识链传到 coding 并真实改码": {"auto-topup", "car-key-sharing"},
        }
        for capability, expected in carriers.items():
            self.assertTrue(expected <= CASE_IDS, capability)

    def test_retired_case_stays_out_of_the_suite(self) -> None:
        """AR90004 与金样材料同源（训练集），退役为回归锚：材料保留、不进 Case 集。"""
        retired = CASES / "traffic-card-loss"
        self.assertTrue((retired / "case.retired.yaml").is_file())
        self.assertFalse((retired / "case.yaml").exists())
        self.assertNotIn("traffic-card-loss", CASE_IDS)

    def test_system_case_pulls_everything_from_the_requirement_system(self) -> None:
        case = definition("auto-topup")
        self.assertTrue(case["system"])
        system = CASES / "auto-topup" / "system"
        # 一个子目录一张单，每张单一份 detail.json——对接层认的就是这个形状。
        tickets = sorted(path.name for path in system.iterdir() if path.is_dir())
        self.assertEqual(["AR90006", "RR90006", "SR90006"], tickets)
        for no in tickets:
            detail = json.loads((system / no / "detail.json").read_text(encoding="utf-8"))
            self.assertEqual(no, detail["reqNo"])
        ar = json.loads((system / case["ar"] / "detail.json").read_text(encoding="utf-8"))
        self.assertEqual("SR90006", ar["parentNo"])
        self.assertEqual("RR90006", ar["rrNo"])

    def test_system_case_keeps_the_rich_business_material(self) -> None:
        text = case_text("auto-topup")
        for token in ("getAutoTopupPolicy", "wallet_auto_topup_contract", "contractNo",
                      "扣款成功但写卡未完成", "单日充值上限", "免密", "脱敏",
                      "唯一真源", "连续 3 次"):
            self.assertIn(token, text)

    def test_system_case_leaves_the_ui_material_off_the_system(self) -> None:
        """系统上只写到「图见原稿」为止，界面本身在人手上那份 docx 里。

        这是本 Case 的材料关卡：模型要自己发现界面部分讲不下去、开口要，
        才会拿到补料。产品正文里把界面画完，这一关就白设了。
        """
        prd = (CASES / "auto-topup/system/RR90006/prd.md").read_text(encoding="utf-8")
        self.assertIn("见原稿", prd)
        self.assertNotIn("![", prd)
        supplements = definition("auto-topup")["supplements"]
        self.assertEqual(1, len(supplements))
        self.assertEqual("on_request", supplements[0]["deliver"])
        self.assertTrue((CASES / "auto-topup/supplements"
                         / supplements[0]["file"]).is_file())

    def test_system_case_split_is_decided_by_a_human_and_review_reply_waits(self) -> None:
        # SR 提出可拆两份、范围由人拍板——交互脚本里那句「不拆了」对应的材料前提。
        sr = (CASES / "auto-topup/system/SR90006/design.md").read_text(encoding="utf-8")
        for token in ("可拆成", "contractNo", "阻塞", "与开发确认后定"):
            self.assertIn(token, sr)
        # 评审回稿放在系统上，等归档之后拉回来。
        feedback = (CASES / "auto-topup/system/AR90006/review-feedback.md") \
            .read_text(encoding="utf-8")
        self.assertIn("要改", feedback)
        self.assertIn("暂缓", feedback)

    def test_local_case_starts_from_half_the_material(self) -> None:
        case = definition("car-key-sharing")
        self.assertFalse(case["system"])
        self.assertFalse((CASES / "car-key-sharing" / "system").exists())
        self.assertFalse(str(case["ar"]).startswith("AR"))
        detail = json.loads((CASES / "car-key-sharing/workspace/AR/detail.json")
                            .read_text(encoding="utf-8"))
        self.assertEqual(case["ar"], detail["reqNo"])
        self.assertEqual("local-workspace", detail["source"])
        # 本地单没有上游单号：写了就等于谎称它有系统单据。
        self.assertNotIn("parentNo", detail)
        self.assertNotIn("rrNo", detail)
        # 产品正文缺席，起跑时工作区里只有系统设计那一份。
        self.assertFalse((CASES / "car-key-sharing/workspace/RR").exists())
        self.assertTrue((CASES / "car-key-sharing/workspace/SR/design.md").is_file())

    @staticmethod
    def _docx_text(path: Path) -> str:
        import zipfile
        with zipfile.ZipFile(path) as zf:
            return zf.read("word/document.xml").decode("utf-8")

    def test_local_case_holds_one_conflict_and_two_undecided_items(self) -> None:
        """冲突要在两份材料之间真实存在，未决项要在材料里写明还没定。"""
        sr = (CASES / "car-key-sharing/workspace/SR/design.md").read_text(encoding="utf-8")
        self.assertIn("48 小时", sr)     # 补料里的产品文档写的是 24 小时
        for token in ("queryKeySharingQuota", "key_sharing_draft", "幂等",
                      "回滚", "车厂云", "脱敏"):
            self.assertIn(token, sr)
        prd = self._docx_text(CASES / "car-key-sharing/supplements/数字车钥匙分享.docx")
        self.assertIn("24 小时", prd)
        self.assertIn("还没定的两件事", prd)
        self.assertIn("安全评审", prd)
        self.assertIn("先不做结论", prd)

    def test_local_case_flow_has_multi_step_branches_for_pattern_selection(self) -> None:
        """分享创建每分支多步且各带失败处理——泛化样本上模式选型「选」路径的材料前提。"""
        sr = (CASES / "car-key-sharing/workspace/SR/design.md").read_text(encoding="utf-8")
        for token in ("一成一败必须回滚", "撤销中", "宽限", "草稿续办", "sequenceDiagram"):
            self.assertIn(token, sr)

    def test_pictures_only_reach_the_flow_through_a_supplement(self) -> None:
        """需求系统不承载图片，Case 目录里也不该躺着图片文件。

        图只有一条路进来：人给的文档里内嵌，导入时抽出来。多留一条路，
        「归档件里的图能不能打开」测的就不是真实链路了。
        """
        for directory in case_directories():
            for source in ("system", "workspace"):
                for path in (directory / source).rglob("*"):
                    self.assertNotIn(
                        path.suffix.lower(),
                        {".png", ".jpg", ".jpeg", ".svg", ".webp", ".bmp"},
                        f"{path} 是图片，但图片只能经补料文档进来")
            for path in (directory / "supplements").glob("*"):
                self.assertEqual(".docx", path.suffix.lower(), path)

    def test_supplement_documents_carry_at_least_two_images(self) -> None:
        import zipfile
        for directory in case_directories():
            for path in (directory / "supplements").glob("*.docx"):
                with zipfile.ZipFile(path) as zf:
                    media = [name for name in zf.namelist()
                             if name.startswith("word/media/")]
                self.assertGreaterEqual(len(media), 2, f"{path} 内嵌图片不足两张")

    def test_scripts_speak_in_turn_and_deliver_declared_material(self) -> None:
        for directory in case_directories():
            script_path = directory / "interaction-script.yaml"
            if not script_path.is_file():
                continue
            script = yaml.safe_load(script_path.read_text(encoding="utf-8"))
            turns = [item["expected_turn"] for item in script["replies"]]
            self.assertEqual(list(range(1, len(turns) + 1)), turns, directory.name)
            declared = {item["file"] for item in definition(directory.name).get("supplements") or []}
            delivered = {name for item in script["replies"]
                         for name in (item.get("deliver") or [])}
            self.assertTrue(delivered <= declared, directory.name)
            # 备着的补料要有人投，否则它永远到不了被测模型手上。
            on_request = {item["file"] for item in definition(directory.name).get("supplements") or []
                          if item.get("deliver") == "on_request"}
            self.assertTrue(on_request <= delivered, directory.name)

    def test_prompts_stay_in_the_voice_of_the_person_who_asked(self) -> None:
        """prompt 只说业务：单号、材料在哪、做到哪一步。

        点了命令、脚本、文件名、关卡名，测的就不再是「模型能不能自己走通」，
        而是「出题的人知不知道答案」；写了处置法（图片怎么办、冲突怎么办、
        要不要拆），那几个观测点当场作废。
        """
        banned = ("/story", "story.js", "story_flow", "import_sources", "harness",
                  "AR/design.md", "spec.md", "story.md", "review.md", "inbox",
                  "关卡", "收件箱", "占位件",
                  "图片", "兄弟", "冲突", "拆分", "未决", "定源", "补料")
        # 「这轮别动被测对象」是工作纪律，不是需求信息，先摘掉再查。
        discipline = ("doc/extensions/", "test/story/", "framework/")
        for case_id in sorted(CASE_IDS):
            prompt = str(definition(case_id)["prompt"])
            for word in discipline:
                prompt = prompt.replace(word, "")
            hit = [word for word in banned if word in prompt]
            self.assertEqual([], hit, f"{case_id} 的 prompt 泄题：{hit}")

    def test_local_markdown_images_resolve_inside_their_case(self) -> None:
        for directory in case_directories():
            for source in ("system", "workspace"):
                root = directory / source
                for markdown in root.rglob("*.md"):
                    text = markdown.read_text(encoding="utf-8")
                    for target in re.findall(r"!\[[^\]]+\]\(([^)]+)\)", text):
                        if re.match(r"^(?:https?:|data:|//)", target):
                            continue
                        resolved = (markdown.parent / target.split("#", 1)[0]).resolve()
                        resolved.relative_to(root.resolve())
                        self.assertTrue(resolved.is_file(), f"{markdown}: {target}")


if __name__ == "__main__":
    unittest.main()
