"""已定稿金样正本与它的冻结输入：内容不被悄悄改动。

金样是给人对照效果用的正本，替换要经用户审定（候选在 doc/plan/1.9.9/金样候选/）；
在新正本审定之前，旧正本与输入夹具原样保留。判据不以「拦不拦金样」定对错——
判据的对错按它的真实依据与中性正反例判（结构、图源承接、人工区等回归在中性夹具里）。
这份测试守金样正本与构造场景所需的同轮材料内容没变：指纹按 LF 归一后比，行尾不算改动，另核形态数。
正本的文件身份只在这里登记一处；spec 门禁对上游承接、知识登记与埋点结构的正反例在
test_review_closure.py、test_knowledge_forms.py、test_knowledge_use.py、test_indicator_reporting.py。
"""
from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
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
    # 2026-09-26 按现行载体重立（三态人工区、议题形态随状态、通用决策类别、D 编号）。
    # 2026-10-16 从 test_review_golden.py 移入本登记：渲染测试改用中性登记表，正本身份只在这里登记一处。
    "review-金样-AR90006.md": "c2055c1dcbca18ad",
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
    "SR/design.md": "d9ccbd10489f89d1",
    "spec/knowledge-use.yaml": "073dcaed046304a7",
    # 2026-09-27 步骤 9（U55）：扩展章平列——埋点提为 9.4、依赖变更为 9.1.4，规约与设计模式两节改名。
    # 同日步骤 9 返修 R3：「规约」生成区的落点前缀写名字所在的节（技术契约 / 埋点）。
    "spec/spec.md": "4a2b81e36d35c45f",
    # 2026-10-16 指纹改按 LF 归一后计：原登记 b7d62b1835408302 是同一内容的 CRLF 字节（现文件转 CRLF 后
    # 逐字节复算即得该值），内容自 d1ecf903 入库未变，仓库按 LF 存储。
    "ux-reference/README.md": "18602db64f0fd154",
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
    # 不是定稿金样，不进形态比对；逐个登记，不放行整个目录。
    "bank-card-opening-reporting-candidate/README.md",
    "bank-card-opening-reporting-candidate/spec.md",
    "bank-card-opening-reporting-candidate/story.md",
    "bank-card-opening-reporting-candidate/plan.md",
}

#: 定稿时点的形态。验收拿新产物与它并排比：任一项显著低于它就是缩水。
SHAPE = {"lines": 476, "chapters": 10, "subsections": 35,
         "table_rows": 174, "diagrams": 1, "images": 2}


#: 按文本比的后缀：行尾在不同检出里可能是 CRLF，那不是内容改动
TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".txt"}


def digest(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix in TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()[:16]


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


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False).result.wasSuccessful() else 1)
