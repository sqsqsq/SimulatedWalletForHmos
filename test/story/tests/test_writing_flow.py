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
        """机器只守既有的两条重复判据；相似度与配额是模型判的事，机器判它必然误伤。

        判的是**可执行的那部分**：注释里写「比的不是相似度」正是该写的话，
        把它一起判掉，就只能靠删注释过关。
        """
        banned = ("相似度", "重复率", "字数配额", "similarity", "重复度")
        for path in list(SKILL.rglob("*.mjs")) + list(SKILL.rglob("*.json")):
            lines = [ln for ln in path.read_text(encoding="utf-8").split("\n")
                     if not ln.lstrip().startswith(("//", "*", "/*"))]
            if path.suffix == ".json":
                lines = [ln for ln in lines if not re.match(r'\s*"_?note', ln)]
            text = "\n".join(lines)
            for word in banned:
                self.assertNotIn(word, text, f"{path.name} 混进了指标类判据「{word}」")


class TestFinalPassLeavesATrace(unittest.TestCase):
    """统稿是唯一一步没有产物的动作，于是跳过它零成本——留痕让「没做」藏不住。"""

    def test_the_guide_asks_for_exactly_six_lines(self) -> None:
        guide = read("phases/story-write.md")
        section = guide.split("# 第三步 · 统稿", 1)[1]
        self.assertIn("copyedit.md", section)
        self.assertIn("恰好六行", section)
        self.assertIn("写多不奖励", section, "防苦役条款要写在作业书里")

    def test_the_phase_order_points_at_the_same_file(self) -> None:
        self.assertIn("copyedit.md", read("phases/spec.md"))

    def test_the_check_does_not_judge_its_content(self) -> None:
        """只核行数。内容真不真归裁决面与抽样人核——机器判它必然逼出套话。"""
        build = read("scripts/story-build.mjs")
        block = build.split("⑫d", 1)[1].split("⑬", 1)[0]
        for metric in ("includes(", "test(", "match("):
            self.assertNotIn(metric, block, "统稿留痕只核行数，不核内容")


class TestIssueDefinitionIsOneText(unittest.TestCase):
    """议题的正面定义只有一份文字，三处逐字一致——改一处忘一处就又有两份说法。"""

    ANCHOR = "**什么算一条议题**"

    def paragraphs(self) -> list[str]:
        out = []
        for rel in ("phases/story-write.md", "phases/spec.md", "rules/rules.md"):
            text = read(rel)
            self.assertIn(self.ANCHOR, text, f"{rel} 里没有议题的正面定义")
            body = text.split(self.ANCHOR, 1)[1].split("\n\n", 1)[0]
            out.append(body)
        return out

    def test_the_three_copies_are_identical(self) -> None:
        first, *rest = self.paragraphs()
        for other in rest:
            self.assertEqual(first, other)

    def test_it_names_the_two_registrations_and_the_six_directions(self) -> None:
        body = self.paragraphs()[0]
        for needle in ("settled", "open", "漏登记",
                       "需求与范围", "上线与协同"):
            self.assertIn(needle, body)


class TestSixCategorySkeletonIsGone(unittest.TestCase):
    """六类骨架是无效机制：好的时候议题来自真实决策不靠它，坏的时候它拦不住。

    判据只拦「零条目又没写 none_reason」，一句「本轮扫过，无开放议题」就能过；
    而同一个域的工程决策在另一轮实打实登记了十条，本轮一条未登记。
    """

    def test_the_skeleton_and_the_old_fields_left_the_extension(self) -> None:
        """判的是**可执行与要模型照做的那部分**：注释里交代「这几样为什么被裁掉」
        正是该写的话，把它一起判掉，下一轮就只能靠删掉退场理由过关。
        """
        gone = ("SCANNED_CATEGORIES", "scanned_categories", "none_reason",
                "同意当前建议", "暂缓原因", "（暂无）", "审核结果（由评审人填写）")
        for path in sorted(SKILL.rglob("*")):
            if not path.is_file() or path.suffix not in (".mjs", ".json", ".md", ".py", ".js"):
                continue
            lines = [ln for ln in path.read_text(encoding="utf-8").split("\n")
                     if not ln.lstrip().startswith(("//", "*", "/*"))]
            text = "\n".join(lines)
            for word in gone:
                self.assertNotIn(word, text, f"{path.name} 还留着「{word}」")

    def test_the_six_directions_survive_as_a_hint_for_people(self) -> None:
        """删的是骨架义务，不是那六个方向——方向提示是给人的，空槽是给机器数的。"""
        guide = read("phases/story-write.md")
        self.assertIn("找议题时把六个方向", guide)


class TestTemplateDoesNotRepeatWhatCheckHolds(unittest.TestCase):
    """判据在的地方不再写一遍约定——两份说法迟早对不上，而没人保证会同步。"""

    def test_the_style_block_keeps_only_what_no_check_covers(self) -> None:
        template = read("templates/story-template.md")
        block = template.split("全篇样式约定", 1)[1].split("归档件自包含", 1)[0]
        for kept in ("表前一句引导", "小节名用常规业务名", "只占一个结构位置"):
            self.assertIn(kept, block, f"「{kept}」没有判据接，约定要留着")
        for dropped in ("编号体系一处不缺", "图题写进图片的替换文本"):
            self.assertNotIn(dropped, block, f"「{dropped}」已由 check 接住，约定不再重复")


if __name__ == "__main__":
    unittest.main()
