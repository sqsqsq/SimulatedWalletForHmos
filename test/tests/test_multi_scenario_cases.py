"""当前组合 Story Case 的静态覆盖与抗过拟合检查。

本文件不启动 Story CLI。标题与组织方式变化由 fixtures 验证，不再复制正式 Case。
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import yaml
from ext_workspace import DEV_EXT

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import end_target  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "test/cases"
FIXTURES = ROOT / "test/fixtures/narrative-variants"
CASE_IDS = {
    path.name for path in CASES.iterdir()
    if path.is_dir() and (path / "case.yaml").is_file()
}
VALID_START = {"story", "spec", "plan", "coding", "review", "ut", "testing"}
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
            self.assertNotIn("end_phase", case)
            end_target.parse_end_at(case.get("end_at"), where=directory.name)
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
        # 只登记走得到的能力：两个 Case 的终点是需求交付（story）与实现方案（phase: plan），coding 与真实改码不在这一轮。
        carriers = {
            "系统按单号拉取": {"auto-topup"},
            "没有系统单据的本地起手": {"car-key-sharing"},
            "系统只给 md，界面材料要另外要": {"auto-topup"},
            "占位件识别与按需补料": {"auto-topup", "car-key-sharing"},
            "docx 转正文并抽图": {"auto-topup", "car-key-sharing"},
            "材料冲突登记为议题、评审回流定源": {"car-key-sharing"},
            "材料写明尚未决定的问题保持 open": {"car-key-sharing"},
            "归档送审与 update 取回评审回稿": {"auto-topup"},
            "零施工单位下完成需求交付": {"auto-topup"},
            "交付后继续施工设计，逐施工单位到 plan": {"car-key-sharing"},
            "评审人在议题人工区表态、update 承接": {"car-key-sharing"},
            "多方协作与多步分支流程": {"car-key-sharing"},
            "会议转写进需求输入": {"auto-topup"},
        }
        for capability, expected in carriers.items():
            self.assertTrue(expected <= CASE_IDS, capability)
        ends = {case_id: definition(case_id).get("end_at") for case_id in CASE_IDS}
        self.assertEqual({"auto-topup": {"kind": "story", "delivery": "submitted"}, "car-key-sharing": {"kind": "phase", "phase": "plan"}}, ends,
                         "终点变了，上面的能力登记要跟着核")

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
        supplements = [item for item in definition("auto-topup")["supplements"]
                       if item.get("kind") != "meeting"]
        self.assertEqual(1, len(supplements))
        self.assertEqual("on_request", supplements[0]["deliver"])
        self.assertTrue((CASES / "auto-topup/supplements"
                         / supplements[0]["file"]).is_file())

    def test_system_case_holds_a_meeting_record_after_the_archived_docs(self) -> None:
        """会议记录要真的带着文档里没有的变化与没收敛的事，并且转换得出文本。

        转换用机制的公共脚本：这份记录转不出文本，实跑时模型就读不到它。
        谁在发言、哪一段是议题由被测模型自己判断，这里不替它断言。
        """
        import sys  # noqa: PLC0415
        sys.path.insert(0, str(DEV_EXT / "skills/story/scripts/core"))
        from materials import importer  # noqa: PLC0415

        declared = [item for item in definition("auto-topup")["supplements"] if item.get("kind") == "meeting"]
        self.assertEqual(1, len(declared))
        self.assertEqual("on_request", declared[0]["deliver"])
        text = importer.docx_to_markdown(CASES / "auto-topup/supplements" / declared[0]["file"], ".")[0]
        self.assertGreater(len(text.splitlines()), 30, "会议记录转换后几乎没有内容")
        for token in ("updateAutoTopupContract", "AC-R1", "开关只管新签约", "先挂着", "今天不定"):
            self.assertIn(token, text)
        # 一场会覆盖多个需求：有一个议题明写是另一张单的
        self.assertIn("RR90007", text)
        # 归档文档里没有新接口：会议带来的是文档之外的变化
        self.assertNotIn("updateAutoTopupContract", case_text("auto-topup"))

    def test_system_case_split_is_decided_by_a_human_and_review_reply_waits(self) -> None:
        # SR 提出可拆两份、范围由人拍板——交互脚本里那句「不拆了」对应的材料前提。
        sr = (CASES / "auto-topup/system/SR90006/design.md").read_text(encoding="utf-8")
        for token in ("可拆成", "contractNo", "阻塞", "与开发确认后定"):
            self.assertIn(token, sr)
        # 评审回稿送审之后才有：起跑时系统上没有，第二段前由装置放上系统，update 取上游时取回。
        self.assertFalse((CASES / "auto-topup/system/AR90006/review-feedback.md").exists())
        inputs = {i["file"]: i for i in definition("auto-topup")["update_inputs"]}
        self.assertEqual("system", inputs["review-feedback.md"]["kind"])
        feedback = (CASES / "auto-topup/update-inputs/review-feedback.md").read_text(encoding="utf-8")
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
        """界面补料要带图；会议记录是语音转写，本来就没有图。"""
        import zipfile
        for directory in case_directories():
            meetings = {item["file"] for item in definition(directory.name).get("supplements") or []
                        if item.get("kind") == "meeting"}
            for path in (directory / "supplements").glob("*.docx"):
                if path.name in meetings:
                    continue
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

    def test_story_cases_start_and_update_with_the_command_only(self) -> None:
        """起手与第二段请求只给命令和单号。

        材料在哪、开过什么会、做到哪一步，都由模型在流程里问、宿主在关卡上答；
        写进请求就把要观测的取材与交付选择提前告诉了它。
        """
        for case_id in sorted(CASE_IDS):
            cfg = definition(case_id)
            ar = str(cfg["ar"])
            self.assertEqual(f"/story init {ar}", str(cfg["prompt"]).strip(), case_id)
            if cfg.get("after_initial") == "update":
                self.assertEqual(f"/story update {ar}", str(cfg["update_request"]).strip(), case_id)

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
