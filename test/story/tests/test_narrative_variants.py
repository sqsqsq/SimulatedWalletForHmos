# -*- coding: utf-8 -*-
"""Story 审查的资格夹具：成对样本本身立不立得住。

这一份**不判 verifier 的区分力**——那要跑真实模型，结论按 `cli_config_id` 记在评审报告里。
这里只保证实验器材没坏：样本能生成、每种缺陷都有换业务名的变体、good 基底结构完整、
生成是确定性的，以及**交付面没有把答案泄漏出去**（样本路径、期望结论都不能出现在
执行者或 verifier 读得到的机制内容里，否则测的是它有没有背过答案）。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "test" / "story" / "scripts"
PAIRS = (REPO_ROOT / "test" / "story" / "fixtures" / "narrative-variants" / "pairs"
         / "pairs.json")
CONTRACT = (REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "contracts"
            / "story-chapters.json")
OVERLAY = REPO_ROOT / "doc" / "extensions" / "rules" / "spec-rules.overlay.yaml"
EXTENSION = REPO_ROOT / "doc" / "extensions"

sys.path.insert(0, str(SCRIPTS))
import make_narrative_variants as maker  # noqa: E402


class TheFixtureItselfHolds(unittest.TestCase):
    """样本能不能生成，是「实验做没做成」的前提，与 verifier 判得对不对无关。"""

    def setUp(self) -> None:
        self.spec = maker.load_pairs()
        self.samples = maker.build(self.spec)

    def test_every_anchor_still_matches_its_base(self) -> None:
        """锚点在基底里恰好一次——基底改过而定义没跟上时，这里就该红。"""
        self.assertTrue(self.samples, "一个样本都没生成")

    def test_each_family_has_two_variants_in_two_domains(self) -> None:
        """同一种缺陷要有换业务名的第二个变体，否则测的是记住了固定文本。"""
        for family in self.spec["families"]:
            with self.subTest(family=family["key"]):
                variants = [s for s in self.samples.values()
                            if s["family"] == family["key"]]
                self.assertGreaterEqual(len(variants), 2, "这一族只有一个变体")
                self.assertGreaterEqual(len({v["domain"] for v in variants}), 2,
                                        "这一族的变体都在同一个业务域里")

    def test_the_six_families_are_all_there(self) -> None:
        """六种缺陷齐备：删事实、掏空章、编造、清零界面图、知识回显、同义改写。"""
        self.assertEqual(
            {"fact_deleted", "chapter_hollow", "fabricated", "image_dropped",
             "knowledge_echo", "same_meaning"},
            {f["key"] for f in self.spec["families"]})

    def test_a_same_meaning_variant_is_expected_clean(self) -> None:
        """同等清楚的另一种表达不该被判问题——只拦得住坏稿的判据才有用。"""
        clean = [s for s in self.samples.values()
                 if s["family"] == "same_meaning" and s["expect"] == "clean"]
        self.assertGreaterEqual(len(clean), 2)

    def test_every_bad_sample_differs_from_its_base(self) -> None:
        for key, sample in self.samples.items():
            if sample["family"] == "good_baseline":
                continue
            with self.subTest(sample=key):
                base = self.samples[f"{sample['base']}.good"]["text"]
                self.assertNotEqual(base, sample["text"])

    def test_the_good_baselines_have_every_chapter(self) -> None:
        """good 基底要是完整稿：十章缺一，它就不再是「本该通过」的那一份。"""
        titles = [c["title"] for c in json.loads(
            CONTRACT.read_text(encoding="utf-8"))["chapters"]]
        for key, sample in self.samples.items():
            if sample["family"] != "good_baseline":
                continue
            with self.subTest(sample=key):
                for title in titles:
                    self.assertIn(f"## {title}", sample["text"], f"缺「{title}」章")

    def test_generating_twice_gives_the_same_bytes(self) -> None:
        """确定性：两次生成不一致的话，实验前后的差异就说不清是哪来的。"""
        outs = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as tmp:
                subprocess.run(
                    [sys.executable, str(SCRIPTS / "make_narrative_variants.py"),
                     "--out", tmp],
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=60, check=True)
                outs.append({p.name: p.read_bytes()
                             for p in sorted(Path(tmp).glob("*"))})
        self.assertEqual(outs[0], outs[1])

    def test_a_drifted_anchor_stops_the_generator(self) -> None:
        """锚点对不上时停下报错，不产出半份——半份样本会被当成某种缺陷去解读。"""
        with self.assertRaises(maker.VariantError):
            maker.apply_edit("一段与锚点无关的正文。",
                             {"op": "replace", "old": "不存在的锚点", "new": "x"},
                             "自检")


class TheAnswerIsNotInTheDeliverable(unittest.TestCase):
    """交付给执行者与 verifier 的机制内容里，不能有样本路径、期望结论或测试坐标。"""

    def test_no_fixture_or_test_path_in_the_extension(self) -> None:
        offenders = []
        for path in EXTENSION.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in (
                    ".md", ".mjs", ".js", ".py", ".yaml", ".yml", ".json"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for needle in ("narrative-variants", "pairs.json", "test/story",
                           "fixtures/", "金样"):
                if needle in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}：{needle}")
        self.assertEqual([], offenders, "交付面出现了测试坐标：%s" % offenders)

    def test_the_review_check_names_no_business_of_the_fixtures(self) -> None:
        """审查任务不能提夹具里的业务名——提了就是把答案写进了题面。"""
        text = OVERLAY.read_text(encoding="utf-8")
        for needle in ("凭证", "排队", "叫号", "RECEIPT-", "QUEUE-"):
            self.assertNotIn(needle, text, f"审查任务里出现了夹具的业务名：{needle}")


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
        """逐条核来源单元的量随材料涨，读者拿到的判断却不增加——新任务不要那张表。"""
        block = self.overlay().split("story_reader_review:")[1].split("\n\n")[0]
        for gone in ("裁决表", "逐条核来源单元", "source-units.json"):
            self.assertNotIn(gone, block.replace("不逐条核来源单元、不出裁决表", ""),
                             f"审查任务又要了一张逐单元表：{gone}")

    def test_it_reads_the_material_manifest(self) -> None:
        """审查的输入是材料清单指向的材料，不是作者转述的摘要。"""
        self.assertIn("materials.json", self.overlay())


if __name__ == "__main__":
    unittest.main()
