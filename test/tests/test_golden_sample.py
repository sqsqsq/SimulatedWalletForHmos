"""金样完整性：审定过的效果正本一个字节没变，目录里只有登记过的文件，配图都能打开。

金样定义给定输入下期望的交付结果；业务质量由语义评价与用户审定确认，确定性判据用专项夹具验证，
金样不经生产链装配。这份测试只守已审结果：

  ① 正本与配图逐字节不变（指纹）；
  ② 目录里没有未登记的文件；
  ③ 正文里的配图链接都指得到文件。

指纹只保护已审字节，不证明业务永远正确：某条判据与审定金样冲突时，先定位来源、样本或当前规则是否真的变化，
再回责任方修。
"""
from __future__ import annotations

import hashlib
import re
import sys
import unittest
from pathlib import Path
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN = REPO_ROOT / "test" / "golden"

#: 定稿时点 2026-08-30（用户逐轮批注后认可）；同日二次修订：材料清单每行带原文链接。sha256 前 16 位。
GOLDEN_FINGERPRINTS = {
    # 2026-09-26 按现行载体重立；2026-10-08 议题标题显示 D 编号（2.0.3 复核 R4）
    "review-金样-AR90006.md": "5b5c5a73529efb68",
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
    # 2026-10-09 第四轮复核：退出已失效的「拦金样即判据错」门禁与「单向否决锚」说法，改为冲突时先定位来源、样本或规则；只是职责说明变更，不是业务正本审定。
    "story-金样-AR90006-说明.md": "5b110699df7606c6",
    "assets/AR90006/detail-entry.png": "328419dced4a2be5",
    "assets/AR90006/disabled-state.png": "adeefcff56af7d05",
    "assets/AR90006/manage-page.png": "24fbb597b158d849",
    "assets/AR90006/signup-page.png": "6c8da20cbbc6fdd4",
    "assets/AR90006/verify-page.png": "c8b62984ec0018e2",
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
    # 不是定稿金样；逐个登记，不放行整个目录。
    "bank-card-opening-reporting-candidate/README.md",
    "bank-card-opening-reporting-candidate/spec.md",
    "bank-card-opening-reporting-candidate/story.md",
    "bank-card-opening-reporting-candidate/plan.md",
}

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


class GoldenIsFrozen(unittest.TestCase):
    def test_every_file_matches_its_fingerprint(self) -> None:
        for rel, want in GOLDEN_FINGERPRINTS.items():
            path = GOLDEN / rel
            with self.subTest(file=rel):
                self.assertTrue(path.is_file(), f"金样少了 {rel}")
                self.assertEqual(want, digest(path), f"{rel} 变了——金样正本只有维护者能改，改了要同步指纹")

    def test_canonical_directory_has_no_unregistered_files(self) -> None:
        actual = {p.relative_to(GOLDEN).as_posix() for p in GOLDEN.rglob("*") if p.is_file()}
        self.assertEqual(EXPECTED_CANONICAL_FILES, actual)

    def test_every_image_link_resolves(self) -> None:
        """正文配图用金样目录内的相对链接，读者打开就能看到图。"""
        for story in sorted(GOLDEN.rglob("*.md")):
            for target in re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", story.read_text(encoding="utf-8")):
                with self.subTest(story=story.relative_to(GOLDEN).as_posix(), image=target):
                    self.assertTrue((story.parent / unquote(target)).is_file(), f"配图打不开：{target}")


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False).result.wasSuccessful() else 1)
