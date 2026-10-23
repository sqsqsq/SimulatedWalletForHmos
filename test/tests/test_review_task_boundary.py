# -*- coding: utf-8 -*-
"""读者审查任务的交付边界：判据挂在 Framework 的 verifier 上，交付面里没有测试坐标。

审查能不能区分好坏稿是模型行为，只在正式 CLI 里取证（TEST §6.3）；这里只核交付出去的机制内容本身。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from ext_workspace import DEV_EXT

SCRIPTS = Path(__file__).resolve().parents[2] / "test" / "scripts"
OVERLAY = DEV_EXT / "rules" / "spec-rules.overlay.yaml"

sys.path.insert(0, str(SCRIPTS))
from check_failure_modes import maintenance_path_hits  # noqa: E402


class TheAnswerIsNotInTheDeliverable(unittest.TestCase):
    """交付给消费模型与 verifier 的机制内容里，不能有夹具路径、期望结论或测试坐标。"""

    def test_a_maintenance_path_is_told_apart_from_names_that_merely_contain_test(self) -> None:
        """指向维护域的路径要认出来；别处碰巧含 `test/` 的名字不算。"""
        for leak in ("按 test/fixtures/sample/input.md 写", "`test/TEST.md`", "(test/cases/a/case.yaml)"):
            with self.subTest(leak=leak):
                self.assertTrue(maintenance_path_hits(leak), leak)
        for legal in ("Read docs/latest/reference.md before using the API.",
                      "单测放在 entry/src/test/ 下", "contest/rules.md", "写 test/ 目录的说明"):
            with self.subTest(legal=legal):
                self.assertEqual([], maintenance_path_hits(legal), legal)

    def test_no_fixture_or_test_path_in_the_extension(self) -> None:
        offenders = []
        for path in DEV_EXT.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in (
                    ".md", ".mjs", ".js", ".py", ".yaml", ".yml", ".json"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for needle in ("narrative-variants", "fixtures/", "金样"):
                if needle in text:
                    offenders.append(f"{path.relative_to(DEV_EXT).as_posix()}：{needle}")
            for hit in maintenance_path_hits(text):
                offenders.append(f"{path.relative_to(DEV_EXT).as_posix()}：{hit}")
        self.assertEqual([], offenders, "交付面出现了测试坐标：%s" % offenders)


class TheReviewTaskIsRegistered(unittest.TestCase):
    """审查任务挂在 Framework 的 verifier 上，不自建通道。"""

    def overlay(self) -> str:
        return OVERLAY.read_text(encoding="utf-8")

    def test_the_check_exists_with_two_result_kinds(self) -> None:
        text = self.overlay()
        self.assertIn("story_reader_review:", text)
        self.assertIn("blocking_findings", text)
        self.assertIn("advisories", text)

    def test_it_does_not_ask_for_a_per_unit_verdict_table(self) -> None:
        """逐条抄回的对账表随材料条数涨，读者拿到的判断却不增加——任务不要那张表。"""
        block = self.overlay().split("story_reader_review:")[1].split("\n\n")[0]
        for gone in ("裁决表", "source-units.json"):
            self.assertNotIn(gone, block, f"审查任务又要了一张逐条对账表：{gone}")

    def test_it_reads_the_material_manifest(self) -> None:
        """审查的输入是材料清单指向的材料，不是作者转述的摘要。"""
        self.assertIn("materials.json", self.overlay())


if __name__ == "__main__":
    unittest.main()
