"""成文流程的第三步是「统稿」——逐章渲染之后必须有一次通读全篇。

②③ 把整篇切成十次有界的小任务，代价是没有任何一步从头读到尾：同一件事在三章
各讲一遍、两句逐字重复、图连图没有承接、图题一章一个样子——每章单看都对，
合起来才看得出来。实测两份产物的重复与样式问题全部落在这个缺口上。

这里判三件事：
  ① 流程里真的有这一步（阶段说明与作业书都写着，且两处不打架）；
  ② 逐章维度里有「一处完整表述」这一维——统稿判不了的那部分交裁决者；
  ③ **没有**混进相似度 / 重复率 / 字数配额类的新判据——多形态重复只有通读的人能判，
     机器守既有的两条（同段重复、跨章同引文）就够，加指标只会逼出凑数的改写。
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL = REPO_ROOT / "doc" / "extensions" / "skills" / "story"
CONTRACT = json.loads((SKILL / "contracts" / "story-chapters.json").read_text(encoding="utf-8"))


def read(rel: str) -> str:
    return (SKILL / rel).read_text(encoding="utf-8")


class TestFinalPassIsInTheFlow(unittest.TestCase):
    def test_phase_order_lists_it(self) -> None:
        spec = read("phases/spec.md")
        self.assertIn("③b 统稿", spec)
        self.assertLess(spec.index("③ 逐章渲染"), spec.index("③b 统稿"),
                        "统稿在逐章渲染之后")
        self.assertLess(spec.index("③b 统稿"), spec.index("④ 裁决"),
                        "统稿在裁决之前——裁决面对的应当是收过口的全篇")

    def test_the_authoring_guide_carries_the_checklist(self) -> None:
        guide = read("phases/story-write.md")
        self.assertIn("# 第三步 · 统稿", guide)
        section = guide.split("# 第三步 · 统稿", 1)[1].split("\n# ", 1)[0]
        items = re.findall(r"^\d+\. ", section, flags=re.M)
        self.assertEqual(6, len(items), f"自查清单应是六项，现在 {len(items)} 项")
        for needle in ("同一件事", "逐字", "引导", "承接", "样式约定", "读者视角"):
            self.assertIn(needle, section, f"自查清单少了「{needle}」那一项")

    def test_the_guide_says_three_steps_not_two(self) -> None:
        """两处说同一件事时先问该由谁说——步数只在开头声明一次，别处引用它。"""
        guide = read("phases/story-write.md")
        self.assertNotIn("成文分两步", guide)
        self.assertIn("成文分三步", guide)


class TestChapterDimensions(unittest.TestCase):
    def test_repetition_is_one_of_the_dimensions(self) -> None:
        dims = CONTRACT["verdicts"]["chapter_dimensions"]
        self.assertEqual(7, len(dims), "逐章维度数变了：改维度要连着改这一行")
        self.assertTrue(any("一处完整表述" in d for d in dims),
                        "缺「同一件事只在一处完整表述」这一维")

    def test_no_similarity_or_quota_metric_sneaked_in(self) -> None:
        """机器只守既有的两条重复判据；相似度与配额是模型判的事，机器判它必然误伤。"""
        banned = ("相似度", "重复率", "字数配额", "similarity", "重复度")
        for path in list(SKILL.rglob("*.mjs")) + list(SKILL.rglob("*.json")):
            text = path.read_text(encoding="utf-8")
            for word in banned:
                self.assertNotIn(word, text, f"{path.name} 混进了指标类判据「{word}」")


if __name__ == "__main__":
    unittest.main()
