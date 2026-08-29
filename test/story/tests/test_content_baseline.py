"""内容基线是批次 4 判「不丢」的标尺，改它就是挪标尺。

批次 4 要重写 story 的骨架、判据与作业书。「新写出来的有没有比以前少讲」这件事，
只跟 `fixtures/content-baseline/` 里那三份批次 1 实跑产出的 story 比——不跟上一个
子批比（那会让每轮只需比上一轮好一点，慢慢滑走），也不跟批次 3 的产物比
（那本身是已知劣化的）。

所以标尺本身必须钉死：指纹写在这里，改了基线而没改这里，测试就红。
"""
from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BASELINE = REPO_ROOT / "test" / "story" / "fixtures" / "content-baseline"

#: 冻结时点 2026-08-29。sha256 前 16 位。
FINGERPRINTS = {
    "AR90004/AR/design.md": "dafdaf1a370a771e",
    "AR90004/AR/story.md": "6234f3221b52984b",
    "AR90004/RR/prd.md": "c674ac15d2ce5658",
    "AR90004/SR/design.md": "4ec7b2c05d383f93",
    "AR90004/spec/spec.md": "cd81d17f774ae43f",
    "AR90006/AR/design.md": "8c628f4d2665d77b",
    "AR90006/AR/story.md": "216bf749040bc2e6",
    "AR90006/RR/prd.md": "ad4e8eb73e30438b",
    "AR90006/SR/design.md": "0da37518fd99c443",
    "AR90006/spec/spec.md": "2ffcc2380b97d225",
    "ISSUE-410/AR/design.md": "f261b6bf08f42781",
    "ISSUE-410/AR/story.md": "0c1414840dc41695",
    "ISSUE-410/RR/prd.md": "d60ff729c11b385c",
    "ISSUE-410/SR/design.md": "6bb145d5faa553a4",
    "ISSUE-410/spec/spec.md": "2c0fc08405822f2b",
}

#: 冻结时点的形态。批次 4 的「形态守恒」以此为源侧参照。
SHAPES = {
    "AR90006": {"lines": 553, "chapters": 17, "table_rows": 239, "diagrams": 3, "images": 2},
    "AR90004": {"lines": 291, "chapters": 10, "table_rows": 80, "diagrams": 1, "images": 1},
    "ISSUE-410": {"lines": 219, "chapters": 10, "table_rows": 71, "diagrams": 1, "images": 0},
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def shape(text: str) -> dict[str, int]:
    lines = text.split("\n")
    return {
        "lines": len(lines) - (1 if lines and lines[-1] == "" else 0),
        "chapters": sum(1 for line in lines if line.startswith("## ")),
        "table_rows": sum(1 for line in lines if line.startswith("|")),
        "diagrams": sum(1 for line in lines if line.startswith("```mermaid")),
        "images": sum(line.count("![") for line in lines),
    }


class BaselineIsFrozen(unittest.TestCase):
    def test_every_declared_file_is_present_and_unchanged(self) -> None:
        actual = {}
        for path in sorted(BASELINE.rglob("*")):
            if path.is_file() and path.name != "README.md":
                actual[path.relative_to(BASELINE).as_posix()] = digest(path)
        self.assertEqual(FINGERPRINTS, actual,
                         "内容基线变了——它是批次 4 全部「不丢」判据的标尺，"
                         "改它等于挪标尺。确认是有意为之后，同步更新本文件与冻结清单")

    def test_each_baseline_ships_its_own_round_material(self) -> None:
        """光有 story 不够：没有材料就说不出「基线里这个事实来自哪」。"""
        for ar in SHAPES:
            for relative in ("AR/story.md", "AR/design.md", "RR/prd.md",
                             "SR/design.md", "spec/spec.md"):
                self.assertTrue((BASELINE / ar / relative).is_file(), f"{ar}/{relative}")


class BaselineShape(unittest.TestCase):
    """形态数是批次 4「不降级」的源侧参照，记在这里省得每次重数。"""

    def test_recorded_shape_matches_the_files(self) -> None:
        for ar, expected in SHAPES.items():
            text = (BASELINE / ar / "AR" / "story.md").read_text(encoding="utf-8")
            self.assertEqual(expected, shape(text), ar)

    def test_two_baselines_already_use_the_ten_chapter_skeleton(self) -> None:
        """十章骨架在批次 1 时代真跑出过完整 story，不是没落过地的假设。

        这不证明「十章一定对」——那两份是在当时的机制上写的——但它说明骨架本身
        写得出东西，问题出在别处（合同按章路由材料、形态判据管语义那些）。
        """
        for ar in ("AR90004", "ISSUE-410"):
            text = (BASELINE / ar / "AR" / "story.md").read_text(encoding="utf-8")
            titles = [line[3:].strip() for line in text.split("\n") if line.startswith("## ")]
            self.assertEqual(10, len(titles), ar)
            for keyword in ("术语", "业务方案", "业务流程", "功能说明",
                            "异常与恢复", "验收", "交付与上线", "附录"):
                self.assertTrue(any(keyword in title for title in titles),
                                f"{ar} 缺「{keyword}」章：{titles}")


if __name__ == "__main__":
    unittest.main()
