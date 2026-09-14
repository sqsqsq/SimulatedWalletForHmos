"""成文流程的第两步是「统稿」——逐章渲染之后必须有一次通读全篇。

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


def read_ext(rel: str) -> str:
    """扩展根下的文件——任务包在 hooks 那边，与作业书不在同一棵子树。"""
    return (REPO_ROOT / "doc" / "extensions" / rel).read_text(encoding="utf-8")


class TestFinalPassIsInTheFlow(unittest.TestCase):
    def test_phase_order_lists_it(self) -> None:
        spec = read("phases/spec.md")
        self.assertIn("②b 写后核对", spec)
        self.assertLess(spec.index("② 按章写"), spec.index("②b 写后核对"),
                        "统稿在按章写之后")
        self.assertLess(spec.index("②b 写后核对"), spec.index("③ 登记"),
                        "统稿在登记之前——登记那一步会渲染 review，"
                        "评审记录面对的应当是收过口的全篇")

    def test_the_authoring_guide_carries_the_checklist(self) -> None:
        guide = read("phases/story-write.md")
        self.assertIn("## 四、写后核对", guide)
        section = guide.split("## 四、写后核对", 1)[1].split("\n## ", 1)[0]
        for action in ("比较信息归属", "推演关系与结果", "核重组后的表达"):
            self.assertIn(action, section, f"写后核对少了「{action}」这个动作")
        items = re.findall(r"^\d+\. ", section, flags=re.M)
        # 七条是作者的清单，不再对着机器里的一个数——那个数（COPYEDIT_ROWS）随七行
        # 自证一起退场了。条数变了改这一行，不要回头再造一个计数判据。
        self.assertEqual(7, len(items), f"写后核对是七条，现在 {len(items)} 条")
        for needle in ("同一件事", "逐字", "引导", "承接", "读者视角", "对着读", "指代"):
            self.assertIn(needle, section, f"自查清单少了「{needle}」那一条")

    def test_the_actions_do_not_order_unconditional_deletion(self) -> None:
        """动作一判的是「这一处还回答了什么别处没回答的问题」，不是「见到重复就删」。

        写后核对是作者读到的最后一段具体指令。它与第一节的「三者互补」「必要的重现
        不是重复」相反时，赢的是最近的那一条——验收表里与正文一致的触发条件就这么
        被删掉，而验收从此判不独立。
        """
        guide = read("phases/story-write.md")
        section = guide.split("## 四、写后核对", 1)[1].split("\n## ", 1)[0]
        self.assertNotIn("有就删掉一处", section,
                         "「逐字相同就删一处」是无条件删除，与必要重现相反")
        for needle in ("独有用途", "完整复述", "互补", "验收独立判"):
            self.assertIn(needle, section, f"动作一没给出判断依据「{needle}」")

    def test_the_guide_says_two_steps(self) -> None:
        """两处说同一件事时先问该由谁说——步数只在开头声明一次，别处引用它。"""
        guide = read("phases/story-write.md")
        self.assertNotIn("成文分三步", guide)
        self.assertIn("成文分两步", guide)


class TheWholeDesignComesBeforeTheChapters(unittest.TestCase):
    """整篇写作设计是成文的第一步：作业书、阶段页、分析规则与流程路由说的是同一条路。

    旧路线「不另落规划文件、在各章草稿里拟标题就算设计过」要整段退出——
    与新路线并存时，作者读到哪句就走哪条，整篇设计又会缩回十份草稿里的几个标题。
    """

    def test_the_old_route_without_a_design_is_gone(self) -> None:
        guide = read("phases/story-write.md")
        for gone in ("不另落规划文件", "也没有「先分配」那一步", "直接写进各章草稿的正文区"):
            self.assertNotIn(gone, guide, f"作业书还留着旧路线「{gone}」")

    def test_the_guide_says_what_the_design_holds_and_how_it_binds(self) -> None:
        guide = read("phases/story-write.md")
        self.assertIn("## 二、动笔前：先有整篇写作设计", guide)
        design = guide.split("## 二、动笔前：先有整篇写作设计", 1)[1].split("\n## ", 1)[0]
        for needle in ("`## 阅读主线`", "`## 章节安排`", "`## 结构选择`", "story-template.md",
                       "来源初筛", "不是新的业务事实源", "设计里没列的有效内容照样写进正文", "reopen"):
            self.assertIn(needle, design, f"写作设计那一节少了「{needle}」")

    def test_the_phase_order_puts_the_design_between_skeleton_and_chapters(self) -> None:
        spec = read("phases/spec.md")
        self.assertLess(spec.index("① 当前输入"), spec.index("①b 写整篇写作设计"))
        self.assertLess(spec.index("①b 写整篇写作设计"), spec.index("② 按章写"))
        route = read("scripts/core/flow/routing.py")
        self.assertIn("写整篇写作设计", route, "流程路由的顺序里没有写作设计")
        self.assertNotIn("先重取一次任务包", route, "当前输入已由 skeleton 给出，路由不该再让作者重取任务包")

    def test_the_analysis_keeps_its_source_screening_for_later(self) -> None:
        rules = read("rules/init_analysis.md")
        self.assertIn("### ⑥ 来源初筛", rules)
        self.assertNotIn("`/spec` 不读它", rules, "Spec 从来源初筛起步，分析规则不能再说 Spec 不读它")
        self.assertIn("init-analysis.md", read("phases/spec.md"), "Spec 的必读输入里没有来源初筛")


class TestChapterDimensions(unittest.TestCase):
    def test_repetition_is_one_of_the_dimensions(self) -> None:
        dims = CONTRACT["verdicts"]["chapter_dimensions"]
        self.assertEqual(7, len(dims), "逐章维度数变了：改维度要连着改这一行")
        self.assertTrue(any("一处完整表述" in d for d in dims),
                        "缺「同一件事只在一处完整表述」这一维")

    def test_the_repetition_dimension_allows_the_complementary_three(self) -> None:
        """裁决面与作者面是同一条规则：图关系、表属性、文理由并存不算重复。

        维度写着「同一个事实用表、文、图各讲一遍」是缺陷的话，独立审查会把作业书
        要求的互补写法报成重复——按标题名误报那一类，换个位置又回来了。
        """
        dim = next(d for d in CONTRACT["verdicts"]["chapter_dimensions"]
                   if "一处完整表述" in d)
        self.assertNotIn("各讲一遍", dim,
                         "「表、文、图各讲一遍」与作业书的三者互补相反")
        self.assertIn("互补", dim, "维度要说清什么不算重复")

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


class TheFinalPassLandsThroughChapterSubmit(unittest.TestCase):
    """统稿改的那几章仍逐章提交——留痕不再是另写一份七行自证。

    七行自证退场（Q5）：它是「做过没做」的代理，而代理只证明有人写了七行。
    统稿真正留下的痕迹是**被替换的那几章**，以及提交时本章判据的那一次核对。
    """

    def test_the_guide_sends_the_changed_chapter_back_through_submit(self) -> None:
        guide = read("phases/story-write.md")
        section = guide.split("## 四、写后核对", 1)[1].split("\n## ", 1)[0]
        self.assertIn("chapter", section, "改完的章要说明怎么落盘")
        self.assertNotIn("copyedit", section, "七行自证已退场，作业书不该还要它")
        self.assertNotIn("恰好七行", section)

    def test_no_seven_line_ledger_is_asked_for_anywhere(self) -> None:
        """生产者、校验、冻结、指令四处一起退——留一处，它就还会被人当成要求。"""
        for rel in ("phases/story-write.md", "phases/spec.md", "rules/review_reflow.md",
                    "scripts/core/story-build.mjs", "scripts/core/story/check.mjs",
                    "scripts/core/story/context.mjs", "scripts/core/story_flow.py"):
            self.assertNotIn("copyedit", read(rel), f"{rel} 还在要七行自证")


class TestIssueDefinitionIsOneText(unittest.TestCase):
    """议题的正面定义只维护一份：阶段页指过去，不再抄一遍。

    两份逐字一致靠的是有人记得同步；改一处忘一处，作者就会在两个地方读到两种说法。
    """

    ANCHOR = "**什么算一条议题**"

    def definition(self) -> str:
        text = read("phases/story-write.md")
        self.assertIn(self.ANCHOR, text, "作业书里没有议题的正面定义")
        return text.split(self.ANCHOR, 1)[1].split("\n\n", 1)[0]

    def test_the_phase_page_points_at_it_instead_of_repeating(self) -> None:
        phase = read("phases/spec.md")
        self.assertNotIn(self.ANCHOR, phase, "阶段页又抄了一份议题定义")
        self.assertIn("story-write.md", phase, "阶段页没给出定义在哪")
        self.assertIn("什么算一条议题", phase, "阶段页连指路都没有，作者不知道去哪读")

    def test_it_names_the_admission_rule_and_the_two_registrations(self) -> None:
        """准入判据只有一条：表态「不同意」会有产物要改。两种登记态各有去处。"""
        body = self.definition()
        for needle in ("表态", "不同意", "settled", "open", "漏登记"):
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
                "同意当前建议", "暂缓原因", "（暂无）", "审核结果（由评审人填写）",
                # 编号归机器铺之后，判自己输出的那条判据与它的合同键一并退场
                "heading_shapes",
                # 窄准入定义（「依据不在材料里才是决策」）与六方向提示同轮退场
                "依据不在材料里", "想一圈")
        for path in sorted(SKILL.rglob("*")):
            if not path.is_file() or path.suffix not in (".mjs", ".json", ".md", ".py", ".js"):
                continue
            lines = [ln for ln in path.read_text(encoding="utf-8").split("\n")
                     if not ln.lstrip().startswith(("//", "*", "/*"))]
            text = "\n".join(lines)
            for word in gone:
                self.assertNotIn(word, text, f"{path.name} 还留着「{word}」")

    def test_the_scan_map_survives_as_a_hint_for_people(self) -> None:
        """删的是骨架义务，不是扫描地图——地图是给人的，空槽是给机器数的。

        六个方向换成十一类：粗粒度的「技术方案与依赖」一个筐装下准入、入口、规则、
        数据、依赖五个热点，模型对不上号。新表拆到「内容特征可识别」的粒度。
        """
        guide = read("phases/story-write.md")
        self.assertIn("对着这十一类过一遍", guide)
        self.assertIn("这是扫描地图，不是配额", guide)

    def test_the_guide_says_what_the_overview_figure_should_show(self) -> None:
        """总览图讲给评审者什么——不说清的话，作者会把上游契约图复制一遍；
        只说「要不一样」又会逼出为了不同而不同的图。图种按内容的关系选，一处维护。
        """
        guide = read("phases/story-write.md")
        flow = guide.split("### 业务流程", 1)[1].split("\n### ", 1)[0]
        for needle in ("主路径与全部分支去向", "交接点", "不为了与上游不同而刻意画不同"):
            self.assertIn(needle, flow, f"业务流程那一段少了「{needle}」")
        form = guide.split("### 形式按内容的关系选", 1)[1].split("\n## ", 1)[0]
        for relation in ("先后与分支", "状态与转移", "调用与返回"):
            self.assertIn(relation, form, f"形式选择表里少了「{relation}」这一行")

    def test_the_guide_registers_a_declined_image_outside_the_appendix(self) -> None:
        """不用的图，理由登记在材料清单里；附录那一节只列初始资料。

        **方法在作业书，那条命令在任务包**：命令带着这一轮的真实路径，抄进方法页就成了
        第二份会过期的写法。两边各自都要在。
        """
        guide = read("phases/story-write.md")
        self.assertIn("写明为什么不用", guide, "作业书没说不用的图要登记理由")
        self.assertIn("附录的材料清单不列图", guide)
        package = read_ext("hooks/spec/author.mjs")
        self.assertIn("--unused", package, "任务包里没有那条登记命令")

    def test_the_scan_map_and_the_contract_word_list_agree(self) -> None:
        """作业书里的类型名与合同 `decision_categories` 的 key 一一对上——
        对不上时，模型按作业书写的类别会被 check 判「不在词表里」。
        """
        import json
        contract = json.loads((SKILL / "contracts" / "story-chapters.json")
                              .read_text(encoding="utf-8"))
        keys = [c["key"] for c in contract["decision_categories"]]
        guide = read("phases/story-write.md")
        table = guide.split("对着这十一类过一遍", 1)[1].split("\n\n**", 1)[0]
        for key in keys:
            self.assertIn(f"| {key} |", table, f"作业书的扫描表里没有「{key}」")


class TestFormHasOneSourceOfTruth(unittest.TestCase):
    """结构只有一处真源——两份说法迟早对不上，而没人保证会同步。

    必要结构在章节合同的 `structure` 里：chapter-contract 唯一解释，
    skeleton 章头与 check ⑪ 都从它走。作业书只留机器不判、要作者自己把关的几条。
    """

    def test_the_retired_template_is_gone(self) -> None:
        self.assertFalse((SKILL / "templates" / "story-template.md").exists(),
                         "story-template.md 该随形态进合同一起退场")

    def test_the_guide_keeps_what_no_check_covers(self) -> None:
        """没有判据接的约定要留着，但留在它该在的那一节，不另起一段重讲一遍。"""
        guide = read("phases/story-write.md")
        self.assertIn("表前有一句引导", guide.split("## 四、写后核对", 1)[1],
                      "表前引导没有判据接，写后核对要问它")
        self.assertIn("标题用真实业务名", guide.split("## 一、", 1)[1],
                      "小节怎么起名没有判据接，读者原则要说")
        self.assertNotIn("不是三次机会", guide,
                         "「表文图是三次机会」与「三者互补」相反，不能两句都留着")
        self.assertIn("三者互补", guide)

    def test_turning_a_table_into_prose_is_judged_by_what_is_lost(self) -> None:
        """同一页两处说表与散文：一处要求「每一列都要有落点」，一处说「压成散文都是降级」。

        两句并存时作者只能各取一条。留下的那条要给判据——丢了结构、条件、单位或例外
        才是有损转换；转得完整就合法。源图那一半不因此撤销：图的关系退化成箭头文字仍是降级。
        """
        guide = read("phases/story-write.md")
        self.assertNotIn("把表压成散文", guide,
                         "「把表压成散文都是降级」与「表格转成散文时每一列都要有落点」相反")
        self.assertIn("有损", guide, "留下的那条要说清什么才算有损")
        self.assertIn("每一列都要有落点", guide)
        self.assertIn("把流程图压成箭头文字是降级", guide, "源图的义务不因此撤销")

    def test_every_chapter_declares_its_boundary(self) -> None:
        """章头唯一化之后，boundary 是草稿章头与读者审查的合同数据，一章不能缺。"""
        import json
        contract = json.loads((SKILL / "contracts" / "story-chapters.json")
                              .read_text(encoding="utf-8"))
        for ch in contract["chapters"]:
            self.assertTrue(str(ch.get("boundary", "")).strip(),
                            f"{ch['id']} 没有内容边界——章头的「主要职责」从它渲染")
            self.assertTrue(ch.get("questions"), f"{ch['id']} 没有读者问题")


if __name__ == "__main__":
    unittest.main()
