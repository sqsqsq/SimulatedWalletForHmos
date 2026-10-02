"""金样是判据的仲裁锚——改它就是挪掉仲裁源。

四轮机制迭代的判据全部从「病」反推：见到一种坏产物就加一条判据，从不存在
「期望的 story 长什么样」的具体定义。后果是判据之间互相打架时没有仲裁源——
批次 4 首跑就撞上了：一边要求人读的改写，一边要求逐字命中，倾倒成了唯一合法解。

所以先有金样，再有判据。规则只有一条：**任何判据若拦金样，错的是判据**。
这份测试守两件事：

  ① 唯一金样正本与构造场景所需的同轮材料一个字节没变（指纹 + 形态数）；
  ② 现行判据对金样零 FAIL——判据改动先跑这一行。
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "test" / "scripts"))
import golden_design  # noqa: E402
import golden_workspace  # noqa: E402
import yaml  # noqa: E402
GOLDEN = REPO_ROOT / "test" / "golden"
INPUT_FIXTURE = REPO_ROOT / "test" / "fixtures" / "golden" / "AR90004"
GOLDEN_STORY = GOLDEN / "story-金样-AR90004.md"

#: 定稿时点 2026-08-30（用户逐轮批注后认可）；同日二次修订：材料清单每行带原文链接
#: ——原文链接是仓内路径唯一允许出现的位置，读者据它把那份材料找出来。sha256 前 16 位。
#: 金样正文与归档图片只在 test/golden 维护；原始材料夹具保留自己的来源图片。
GOLDEN_FINGERPRINTS = {
    # 2026-09-27 附录·改动边界的机器区不再投 Scope 的切分理由（plan/1.9.7/2026-09-25-整体设计/10 §3.4），
    # 只替换那一个机器区，作者写的部分不动。
    # 2026-09-26 附录按合同改成「定位句 + 机器区 + 作者说明」，机器区由输入夹具投影
    # （plan/1.9.7/2026-09-25-整体设计/06 §3.4）；埋点改按指标组织，8.6 末段与灰度观察随之按两个指标写。
    # 2026-09-23 附录改为登记处（plan/1.9.5/2026-09-23-第三轮结果与表达正向设计/01 §2.1）：
    # 两份金样的附录合为四节，A 技术约定下分接口 / 数据 / 配置 / 埋点四个 H4，埋点按指标分 H5；正文未动。
    # 2026-09-07 用户裁定：章首那张时序图补两行来源标记——它同时承接
    # SR §3 的端到端时序与 spec §5.1 的流程图（改画成了时序），
    # 正是「重复来源合并、一个围栏多行标记」的形态。
    # 2026-09-05 步骤 16 S2：形态收紧后金样跟上——异常章拆 7.1/7.2 两节、
    # 9.3 回退设计改三标签段。正文一个字没删，只是把已经分好的两张表与三件事摆明。
    # 2026-09-27 步骤 9（U55，用户同日确认）：附录改为技术契约（端云接口、数据存储、配置项、依赖变更）、规约、埋点、
    # 改动边界、材料清单平列，机器区按当前真源重投；只改标题层级、编号与节名。
    "story-金样-AR90004.md": "eb78b66b0f7e97a5",
    "assets/image1.png": "7a0b672988d707e2",
    "assets/image2.png": "da8a096f4a859ddb",
    # 2026-09-26 AR90006 按 0903 澄清会结论与答案卷更新（签约更新接口、AC-R1 与开关口径、两件待定），
    # 埋点标题只写指标名，材料清单按归档件的相对位置并补澄清会记录；说明里的来源与编号事实随之修正。
    # 2026-09-11 A段回退保留：AR90006 Story效果金样、编写说明与归档图片，
    # 供维护侧评价参照；不自动获得AR90004金样的判据锚地位。
    # 2026-09-27 步骤 9（U55，用户同日确认）：附录节名与层级按平列形态重排，内容未动。
    "story-金样-AR90006.md": "216e138ed4667f8d",
    # 2026-09-25 过程件目录 design 改名 plan：说明里的历史分析链接改到 plan/1.9.1/ 下的实际位置，正文未动。
    # 2026-09-28 方案目录迁到仓根 doc/plan（1.9.8 P3 目录归属纠正）：同一条链接改到 doc/plan/1.9.1/，正文未动。
    "story-金样-AR90006-说明.md": "27c234bb7b3a8a26",
    "assets/AR90006/detail-entry.png": "328419dced4a2be5",
    "assets/AR90006/disabled-state.png": "adeefcff56af7d05",
    "assets/AR90006/manage-page.png": "24fbb597b158d849",
    "assets/AR90006/signup-page.png": "6c8da20cbbc6fdd4",
    "assets/AR90006/verify-page.png": "c8b62984ec0018e2",
}

INPUT_FINGERPRINTS = {
    # 2026-09-26 夹具补成可由现行机制检查的需求工作区（06 §3.5）：spec 9.1.4 按指标组织、
    # 9.2/9.3 由新增的知识判断投影；补写作设计、决策登记与界面原型原件。
    "AR/design.md": "ed2119f15893b568",
    "AR/story-src/decisions.json": "36d7a7c82f3822a6",
    "AR/story-src/story-template.md": "e4b02703194c89bd",
    "inbox/紧急挂失界面原型说明.docx": "5fa860eb01b25972",
    "RR/prd.md": "ff0013420c4c0741",
    # 2026-10-02 用户决定接口走模拟真实场景：§4 三个接口段后补 SE 接口明细（版本、字段类型、必填与可空），原段落一字未改；
    # 草案与来源对照见 doc/plan/2.0.0/实施反馈/2026-10-02-步骤4-模拟SE接口草案.md，与 CLI 结果一并交设计者审定。
    "SR/design.md": "46f04c03a511d971",
    "spec/knowledge-use.yaml": "073dcaed046304a7",
    # 2026-09-27 步骤 9（U55）：扩展章平列——埋点提为 9.4、依赖变更为 9.1.4，规约与设计模式两节改名。
    # 同日步骤 9 返修 R3：「规约」生成区的落点前缀写名字所在的节（技术契约 / 埋点）。
    "spec/spec.md": "4a2b81e36d35c45f",
    "ux-reference/README.md": "b7d62b1835408302",
    "assets/紧急挂失界面原型说明/image1.png": "7a0b672988d707e2",
    "assets/紧急挂失界面原型说明/image2.png": "da8a096f4a859ddb",
}

EXPECTED_CANONICAL_FILES = {
    "README.md",
    "story-金样-AR90004.md",
    "review-金样-AR90006.md",
    "story-金样-AR90006.md",
    "story-金样-AR90006-说明.md",
    "assets/image1.png",
    "assets/image2.png",
    "assets/AR90006/detail-entry.png",
    "assets/AR90006/disabled-state.png",
    "assets/AR90006/manage-page.png",
    "assets/AR90006/signup-page.png",
    "assets/AR90006/verify-page.png",
    # 设计者的候选样稿（2026-09-22，上报的多流程、多指标组织方式）：只供效果审视，
    # 不是定稿金样，不进形态比对与否决锚；逐个登记，不放行整个目录。
    "bank-card-opening-reporting-candidate/README.md",
    "bank-card-opening-reporting-candidate/spec.md",
    "bank-card-opening-reporting-candidate/story.md",
    "bank-card-opening-reporting-candidate/plan.md",
}

#: 定稿时点的形态。验收拿新产物与它并排比：任一项显著低于它就是缩水。
SHAPE = {"lines": 476, "chapters": 10, "subsections": 35,
         "table_rows": 174, "diagrams": 1, "images": 2}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def workspace_check(story: str | None = None) -> tuple[int, str]:
    """金样放进它的需求工作区，经 `story-build check --feature` 判。"""
    with tempfile.TemporaryDirectory() as tmp:
        golden_workspace.build(Path(tmp), story)
        return golden_workspace.check(Path(tmp))


class GoldenIsFrozen(unittest.TestCase):
    def test_every_file_matches_its_fingerprint(self) -> None:
        for root, fingerprints in ((GOLDEN, GOLDEN_FINGERPRINTS),
                                   (INPUT_FIXTURE, INPUT_FINGERPRINTS)):
            for rel, want in fingerprints.items():
                path = root / rel
                with self.subTest(file=path.relative_to(REPO_ROOT)):
                    self.assertTrue(path.is_file(), f"金样或输入夹具少了 {path}")
                    self.assertEqual(
                        want, digest(path),
                        f"{path} 变了——金样正本或冻结输入只有维护者能改，改了要同步指纹")

    def test_no_duplicate_golden_outputs_in_fixture(self) -> None:
        for rel in ("AR/story.md", "AR/review.md", "AR/assets/image1.png", "AR/assets/image2.png"):
            with self.subTest(file=rel):
                path = INPUT_FIXTURE / rel
                self.assertFalse(path.exists(), f"{path} 重复保存金样输出；测试须直接读取 test/golden")

    def test_input_fixture_has_only_frozen_inputs(self) -> None:
        """输入夹具只保存构造场景需要的材料，不保存 story/review 金样副本。"""
        actual = {p.relative_to(INPUT_FIXTURE).as_posix()
                  for p in INPUT_FIXTURE.rglob("*") if p.is_file()}
        self.assertEqual(set(INPUT_FINGERPRINTS), actual)

    def test_canonical_golden_files_exist(self) -> None:
        for rel in GOLDEN_FINGERPRINTS:
            with self.subTest(file=rel):
                path = GOLDEN / rel
                self.assertTrue(path.is_file(), f"金样少了 {rel}")

    def test_canonical_directory_has_no_unregistered_files(self) -> None:
        actual = {p.relative_to(GOLDEN).as_posix()
                  for p in GOLDEN.rglob("*") if p.is_file()}
        self.assertEqual(EXPECTED_CANONICAL_FILES, actual)

    def test_shape_is_unchanged(self) -> None:
        lines = GOLDEN_STORY.read_text(encoding="utf-8").split("\n")
        actual = {
            "lines": len(lines) - (1 if lines and lines[-1] == "" else 0),
            "chapters": sum(1 for x in lines if x.startswith("## ")),
            "subsections": sum(1 for x in lines if x.startswith("### ")),
            "table_rows": sum(1 for x in lines if x.startswith("|")),
            "diagrams": sum(1 for x in lines if x.startswith("```mermaid")),
            "images": sum(x.count("![") for x in lines),
        }
        self.assertEqual(SHAPE, actual)


class TheGoldenCarriesEveryUpstreamDiagram(unittest.TestCase):
    """章首那张时序图承接系统设计的端到端时序：围栏里一行 `%% 图源 SR §3 #1`。

    正本里同一个围栏还有一行 `spec §5.1 #1`：2.0 的直接上游不再有 spec，那张流程图的各分支由蓝图的场景与运行对象
    承载（映射表逐分支登记），迁移只删这一行（步骤 4 阶段评审 §4 第 3 条）。**只核图对应这一类**。
    """

    MARK = "%% 图源 SR §3 #1\n"

    def diagram_complaints(self, story: str) -> list[str]:
        out = self.check_output(story)
        return [l.strip() for l in out.split("\n") if "在 story 里没有" in l]

    def check_output(self, story: str) -> str:
        return workspace_check(story)[1]

    def test_the_system_design_diagram_is_carried(self) -> None:
        complaints = self.diagram_complaints(
            GOLDEN_STORY.read_text(encoding="utf-8"))
        self.assertEqual([], complaints, "上游有图没被金样带着")

    def test_dropping_the_mark_is_caught(self) -> None:
        """去掉标记就该报——不然上一条是在空跑。"""
        story = GOLDEN_STORY.read_text(encoding="utf-8")
        self.assertIn(self.MARK, story, "金样的系统设计图源标记不在了")
        complaints = self.diagram_complaints(story.replace(self.MARK, ""))
        self.assertEqual(1, len(complaints), f"该报一条，实报 {len(complaints)}：{complaints}")
        self.assertIn("SR §3", complaints[0])

    def test_missing_carry_is_its_own_class_one_line_per_diagram(self) -> None:
        """缺承接归自己的一类「⑫d 上游图承接」，一张图一行——不混进机器区一致性，也不逐张重复写法。"""
        story = GOLDEN_STORY.read_text(encoding="utf-8").replace(self.MARK, "")
        out = self.check_output(story)
        self.assertIn("[⑫d 上游图承接] 1 处", out)
        lines = [l for l in out.split("\n") if "在 story 里没有" in l]
        self.assertEqual(1, len(lines), lines)
        self.assertIn("%% 图源", lines[0], "去向写法要在同一行里")


class TheMigrationIsRegistered(unittest.TestCase):
    """正本的旧元数据按映射表迁移（步骤 4 阶段评审 §4）：只动登记过的，没登记的报错；映射指向的蓝图对象真实存在。"""

    def setUp(self) -> None:
        self.plan = golden_design.mapping()
        self.story = GOLDEN_STORY.read_text(encoding="utf-8")
        self.migrated = golden_design.migrate(self.story)

    def test_only_the_registered_lines_change(self) -> None:
        """删的只有 spec 图源那一行与依赖变更机器区的首尾两行标记，两处图片链接改指登记的原件抽图，其余一个字节不动。"""
        self.assertIn("%% 图源 SR §3 #1", self.migrated)
        lines = self.story.split("\n")
        at = next(k for k, l in enumerate(lines) if l.startswith("<!-- story-build:begin 技术契约·依赖变更 "))
        end = next(k for k in range(at, len(lines)) if lines[k].startswith("<!-- story-build:end -->"))
        drop = {lines.index("%% 图源 spec §5.1 #1"), at, end}
        expected = "\n".join(l for k, l in enumerate(lines) if k not in drop)
        for ref in self.plan["image_refs"]:
            self.assertEqual(1, expected.count(f"]({ref['from']})"))
            expected = expected.replace(f"]({ref['from']})", f"]({ref['to']})")
        self.assertEqual(expected, self.migrated)

    def test_the_dependency_section_keeps_its_text_as_author_zone(self) -> None:
        self.assertNotIn("story-build:begin 技术契约·依赖变更", self.migrated)
        zone = next(z for z in self.plan["zones"] if z["zone"] == "技术契约·依赖变更")
        for fact in zone["facts"]:
            self.assertIn(fact, self.migrated)

    def test_an_unregistered_mark_or_zone_fails(self) -> None:
        with self.assertRaisesRegex(golden_design.MappingError, "没登记"):
            golden_design.migrate(self.story.replace("%% 图源 SR §3 #1", "%% 图源 SR §9 #1"))
        with self.assertRaisesRegex(golden_design.MappingError, "没登记"):
            golden_design.migrate(self.story.replace("story-build:begin 改动边界 ", "story-build:begin 别的区 "))
        with self.assertRaisesRegex(golden_design.MappingError, "没登记"):
            golden_design.migrate(self.story.replace("](assets/image1.png)", "](assets/image9.png)"))

    def test_every_mapped_address_exists_in_the_blueprint(self) -> None:
        blueprint = yaml.safe_load((golden_design.DESIGN / "component-blueprint.yaml").read_text(encoding="utf-8"))
        addresses = {f"view:{v['view_id']}/node:{n['node_id']}" for v in blueprint["design_views"]
                     for n in v.get("nodes") or []}
        refs = [ref for mark in self.plan["diagram_marks"] for b in mark.get("branches", []) for ref in b["blueprint"]]
        refs += list(self.plan["knowledge_targets"].values())
        refs += [ref for d in self.plan["story_details"] for ref in d["evidence_refs"]]
        refs += [ref for z in self.plan["zones"] for ref in z.get("blueprint", []) if ref.startswith("view:")]
        self.assertTrue(refs)
        self.assertEqual([], [ref for ref in refs if ref not in addresses])

    def test_stale_zones_do_not_count_as_found(self) -> None:
        """没重投的 1.x 机器区里的旧事实不算找到。"""
        self.assertTrue(any("没按蓝图重投" in m for m in golden_design.verify(self.migrated)))


class JudgementsDoNotBlockTheGolden(unittest.TestCase):
    """判据改动先跑这一行：拦住金样的判据，错的是判据。"""

    def test_the_golden_passes_in_its_workspace(self) -> None:
        """检查零 FAIL，且映射表登记的每条旧事实在重投后的新输出里都在。

        冻结输入里 AR/design.md 是原件、交给设计的提取稿是另一份文件，两者角色不混。"""
        with tempfile.TemporaryDirectory() as tmp:
            golden_workspace.build(Path(tmp))
            code, out = golden_workspace.check(Path(tmp))
            missing = golden_design.verify(golden_workspace.story(Path(tmp)))
            src = Path(tmp) / "doc" / "features" / "AR90004" / "AR" / "story-src"
            snapshot = json.loads(next(src.glob("inputs/*/snapshot.json")).read_text(encoding="utf-8"))
            listed = golden_workspace.review_object(Path(tmp))
        roles = {f["path"]: f["role"] for f in snapshot["files"]}
        for name in ("se-interfaces.yaml", "mappings.yaml"):
            self.assertIn(f"doc/features/bp-AR90004/blueprint/contracts/{name}", listed,
                          "Story 审查对象没带上蓝图契约引用的接口转写或映射")
        self.assertEqual("original", roles.get("AR/design.md"), roles)
        self.assertEqual("extracted_analysis", roles.get("AR/story-src/design-draft.md"), roles)
        self.assertEqual(0, code, f"判据拦住了金样——修判据，不修金样：\n{out[:1500]}")
        self.assertEqual([], missing, "旧事实在新输出里找不到")

    def test_the_judgements_actually_run(self) -> None:
        """零 FAIL 要是「真的判过了」，不是「一条都没跑」。

        往主叙事里塞一个工程标识与一个模板占位，两条判据都该点名。
        """
        text = GOLDEN_STORY.read_text(encoding="utf-8")
        marker = "\n\n这里塞一个 queryLossEligibility 进主叙事，再留一个 {{待替换的占位}}。"
        code, out = workspace_check(text.replace("## 2. 术语", "## 2. 术语" + marker, 1))
        self.assertEqual(1, code)
        self.assertIn("工程标识", out)
        self.assertIn("模板占位符", out)


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False).result.wasSuccessful() else 1)
