"""内容基线对照工具：它说「找不到」的时候，必须真的找不到。

这个工具是批次 4「不丢」那一轴的唯一量化手段。它自己错了，整轴的数字就都不作数，
而且错得很隐蔽——报出一堆假缺失，人会先不信它，再不看它。

这里判三件事：
  ① 自对照是天花板：基线对它自己，覆盖率必须等于报出来的「机器可核上限」；
  ② 有区分力：换一份不相干的 story，覆盖率要塌下去；
  ③ 形态降级看得见：图少了、表少了，报告里要指出来。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL = REPO_ROOT / "test" / "story" / "scripts" / "baseline_coverage.py"
BASELINE = REPO_ROOT / "test" / "story" / "fixtures" / "content-baseline"


def run(story: Path, baseline: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(TOOL), str(story), "--baseline", baseline, "--json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    if proc.returncode != 0:
        raise AssertionError(f"工具跑不起来：{proc.stderr[:400]}")
    return json.loads(proc.stdout)


class SelfComparisonIsTheCeiling(unittest.TestCase):
    """基线对它自己——这就是机器能核到的上限，不是 1.0。

    有些单元短到切不出可核片段（「分享只读」这类），机器在**任何**文档里都核不到，
    生产链里它们归裁决者的三张表。不把这个数报出来，人会把 0.95 当成「丢了 5%」。
    """

    def test_each_baseline_reaches_its_own_ceiling(self) -> None:
        for name in ("AR90004", "AR90006", "ISSUE-410"):
            with self.subTest(baseline=name):
                result = run(BASELINE / name / "AR" / "story.md", name)
                self.assertEqual(result["覆盖率"], result["机器可核上限"],
                                 f"{name} 对照自己却没到上限——工具的口径与枚举器漂移了")
                self.assertEqual(result["缺失"], result["上限外的"])

    def test_ceiling_is_reported_even_when_it_is_one(self) -> None:
        result = run(BASELINE / "AR90004" / "AR" / "story.md", "AR90004")
        self.assertIn("机器可核上限", result)
        self.assertEqual(1.0, result["机器可核上限"])


class ItActuallyDiscriminates(unittest.TestCase):
    def test_an_unrelated_story_collapses_the_coverage(self) -> None:
        """拿另一个需求的 story 去对照，覆盖率要塌下去。

        不塌就说明判「有落点」的口径太松——那样这个工具永远报 0 缺失，
        「不丢」这一轴就等于没人在守。
        """
        result = run(BASELINE / "ISSUE-410" / "AR" / "story.md", "AR90004")
        self.assertLess(result["覆盖率"], 0.1)
        self.assertGreater(len(result["缺失清单"]), 50)

    def test_missing_items_are_named_not_counted(self) -> None:
        """缺失要逐条点名——只报个数字，人无从判断丢的要不要紧。"""
        result = run(BASELINE / "ISSUE-410" / "AR" / "story.md", "AR90004")
        first = result["缺失清单"][0]
        for key in ("来源行", "类型", "正文"):
            self.assertIn(key, first)
        self.assertTrue(str(first["正文"]).strip())


class ShapeDowngradeIsVisible(unittest.TestCase):
    def test_report_carries_both_shapes(self) -> None:
        result = run(BASELINE / "ISSUE-410" / "AR" / "story.md", "AR90004")
        base, new = result["形态"]["基线"], result["形态"]["新"]
        for key in ("行数", "章", "表行", "围栏图", "图片"):
            self.assertIn(key, base)
            self.assertIn(key, new)
        # AR90004 基线有一张图片，ISSUE-410 没有——降级要看得见
        self.assertGreater(base["图片"], new["图片"])


if __name__ == "__main__":
    unittest.main()
