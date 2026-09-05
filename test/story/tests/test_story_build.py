"""`story-build` 各命令的单元断言——init 派生什么、chapter 怎么落盘、check 拦什么。

台账（`check_failure_modes.py`）判的是**形态回不回来**：一个已知会犯的错，机制现在抓不抓得住。
本文件判的是**判据本身的边界**：同一条判据，改一个字符就该翻面的那些地方。两者都要有，
因为台账只覆盖曾经真实发生过的错，而边界是它没走到的地方。

夹具借用 `R01-verdict-echo/good`——它是一份最小但完整的工作区（材料 + story + 激活清单 +
决策件）。每个用例在**副本**上跑：这几条命令会写 `decisions.json` 与 `story.md`，
在夹具原地跑会把它写脏，且上一个用例的产物会影响下一个。
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BUILD = REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts" / "story-build.mjs"
FIXTURE = (REPO_ROOT / "test" / "story" / "fixtures" / "failure-modes"
           / "R01-verdict-echo" / "good")
FEATURE = "AR90001"
FLOW = REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "scripts" / "story_flow.py"

CHAPTER_OUT_OF_CONTRACT = "第十五章"
QUOTE = "提交之后回执没到之前，界面停在等待态"


def _chapter_bodies(story_path) -> dict:
    """把 story 切成 {章标题: 正文}——夹具的引文要从真正的那一章里取。"""
    out, cur, buf = {}, None, []
    if story_path is None or not Path(story_path).is_file():
        return out
    for line in Path(story_path).read_text(encoding="utf-8").split("\n"):
        if line.startswith("## "):
            if cur:
                out[cur] = "\n".join(buf).strip()
            cur, buf = line[3:].strip(), []
            continue
        if cur is not None:
            buf.append(line)
    if cur:
        out[cur] = "\n".join(buf).strip()
    return out


def _is_empty_chapter(body: str) -> bool:
    """空章：正文恰是那一句。它已明说这件事不在本需求里，读者的问题也就不存在。"""
    return body.strip() == "本需求不涉及。"


def _chapter_quote(body: str) -> str:
    """取该章正文的一段连续原文作引文。

    不能只找散文句：术语章与异常章天然是表、业务流程章天然是图，
    它们里面的文字同样是「答了这个问题」的证据。所以按**原文顺序**拼，
    取够长的一段——check 只要求它是该章的逐字子串且 ≥12 字。
    """
    for line in body.split("\n"):
        s = line.strip()
        if not s or s.startswith(("#", "```", "~~~")):
            continue
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            cells = [c for c in cells if c and not set(c) <= set("-: ")]
            if not cells:
                continue
            s = max(cells, key=len)
        if len(s) >= 14:
            return s[:60]
    return ""


def _appendix_title() -> str:
    """附录那一章的标题从合同取——用例不写死章名，合同改了它跟着变。"""
    contract = json.loads((REPO_ROOT / "doc/extensions/skills/story/contracts"
                           / "story-chapters.json").read_text(encoding="utf-8"))
    hit = next((c for c in contract.get("chapters") or [] if c.get("appendix")), None)
    return (hit or {}).get("title", "")


class StoryBuildCase(unittest.TestCase):
    """每个用例一份新工作区；子类只关心自己那一条判据。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "work"
        shutil.copytree(FIXTURE, self.root)
        self.addCleanup(self._tmp.cleanup)
        self.src = self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
        self.story_path = self.root / "doc" / "features" / FEATURE / "AR" / "story.md"

    # ---- 驱动 ----

    def run_build(self, command: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["node", str(BUILD), command, "--feature", FEATURE,
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    def init_audit(self) -> None:
        """起手：材料齐备检查 + 决策登记骨架。

        名字留着不改是因为几十处在用；`audit` 那一半随逐单元系统退场，没有对象了。
        """
        proc = self.run_build("init")
        self.assertEqual(proc.returncode, 0, f"init 跑不起来：{proc.stderr}")

    def check_output(self) -> tuple[int, str]:
        proc = self.run_build("check")
        return proc.returncode, ((proc.stderr or "") + (proc.stdout or "")).strip()

    def assert_check_names(self, needle: str) -> str:
        """check 必须失败，且**点名**了原因——笼统说「有问题」等于没有区分力。"""
        code, out = self.check_output()
        self.assertEqual(code, 1, f"check 应当失败却过了：{out}")
        self.assertIn(needle, out)
        return out

    # ---- 产物读写 ----

    def story(self) -> str:
        return self.story_path.read_text(encoding="utf-8")

    def rewrite_story(self, old: str, new: str) -> None:
        text = self.story()
        self.assertIn(old, text, "夹具变了，用例要跟着改")
        self.story_path.write_text(text.replace(old, new), encoding="utf-8")


class TestArchiveRedlines(StoryBuildCase):
    """归档件四红线里机器判得了的那条：正文不许出现仓内路径。

    术语表实体词守恒随逐单元系统退场，这个类只剩红线这一面。
    """

    def test_repo_path_in_story_is_named(self) -> None:
        self.init_audit()
        self.rewrite_story("本需求不涉及。\n\n## 术语",
                           "详见 doc/features/AR90001/AR/design.md。\n\n## 术语")
        self.assert_check_names("仓内路径")


class TestErrorWordingPointsAtForm(StoryBuildCase):
    """报错说的是「这一类事实的落点长什么样」，不是一张待抄的字面清单。

    上一版报的是「落点标在『附录』，但那一章里找不到：WalletMain、cardId、…」。
    模型逐轮照做，把这些字面一个个抄进附录——首跑那个占了全篇 58% 的倾倒区
    不是模型自己想出来的，是门禁一条一条教出来的（失败数 35→11→9→1→6→18）。
    """

    def drop_from_appendix(self, fragment: str) -> None:
        self.rewrite_story(fragment, "")

    def test_the_bare_token_list_style_is_gone_from_the_source(self) -> None:
        """禁止样式在源码里也不该留——留着下一轮就会有人接回去。"""
        source = (REPO_ROOT / "doc/extensions/skills/story/scripts/story-build.mjs"
                  ).read_text(encoding="utf-8")
        self.assertNotIn("但那一章里找不到", source)


REVIEW_HUMAN_ZONE = "审核结果：\n"


class TestReviewForm(StoryBuildCase):
    """评审人要填的只剩「审核结果：」一行——需要说明书就是设计错了。

    曾经这里还有暂缓责任人、完成期限、是否阻塞执行、后续动作、确认人、确认日期、
    确认依据七个字段。评审人打开它先要读一遍字段表，而其中六格他答不上来
    （责任人和期限是排期的事，确认依据是审计的事）。答不上来的格子只会被跳过或胡填。
    三态勾选是同一个问题的轻量版：勾「需要修改」而不写改成什么，那一勾传不出任何信息；
    既然要写字，框就是多余的。
    """

    review_path = property(
        lambda self: self.root / "doc" / "features" / FEATURE / "AR" / "review.md")

    def write_decision(self) -> None:
        (self.src / "decisions.json").write_text(json.dumps({
            "decisions": [{
                "id": "submit-boundary", "status": "settled",
                "title": "提交入口与补卡由两张开发单分别承接",
                "clarification": "**要定的事**：提交与补卡要不要放在同一张单里做。\n\n"
                                 "**根据**：上游已经拆成两张开发单。\n\n"
                                 "**结论与影响**：本单只做提交与回执展示，验收不含补卡。",
                "decider": "需求负责人",
            }],
        }, ensure_ascii=False), encoding="utf-8")

    def test_the_human_zone_is_one_line(self) -> None:
        self.write_decision()
        self.assertEqual(0, self.run_build("build").returncode)
        text = self.review_path.read_text(encoding="utf-8")
        self.assertIn(REVIEW_HUMAN_ZONE, text)
        for gone in ("暂缓责任人", "完成期限", "是否阻塞执行", "后续动作",
                     "确认人", "确认日期", "确认依据", "**状态**",
                     "- [ ]", "同意当前建议", "暂缓原因"):
            self.assertNotIn(gone, text, f"「{gone}」不该再出现在评审记录里")

    def test_filled_human_zone_survives_a_rerender(self) -> None:
        """人填过的内容一个字节都不能动——重算它等于把做完的决定推回去一次。

        连**旧形态**留下的字也要保住：字段是被裁掉了，人当时写在里面的话不是。
        """
        self.write_decision()
        self.assertEqual(0, self.run_build("build").returncode)
        text = self.review_path.read_text(encoding="utf-8")
        anchor = "<!-- decision: submit-boundary -->"
        filled = text.replace(
            "审核结果：\n\n" + anchor,
            "审核结果：范围要含补卡入口。\n\n**确认人**：某评审人\n\n" + anchor)
        self.review_path.write_text(filled, encoding="utf-8")

        self.assertEqual(0, self.run_build("build").returncode)
        again = self.review_path.read_text(encoding="utf-8")
        self.assertIn("审核结果：范围要含补卡入口。", again)
        self.assertIn("**确认人**：某评审人", again, "旧形态里人写过的字也要保住")

    def test_legacy_fields_in_the_review_are_named(self) -> None:
        """人工区之外又长回签署字段与状态行时，check 要点名。"""
        self.init_audit()
        self.review_path.write_text(
            "# 评审记录\n\n### 1. 提交入口与补卡由两张开发单分别承接\n\n"
            "审核结果：\n\n"
            "<!-- decision: submit-boundary -->\n\n"
            "**确认日期**：\n\n**状态**：草稿（待开发确认）\n",
            encoding="utf-8")
        out = self.assert_check_names("评审记录里出现")
        self.assertIn("确认日期", out)
        self.assertIn("状态行", out)


class TestRequirementIdInTitle(StoryBuildCase):
    """大标题带需求编号——归档件离开这个仓库后，编号是它回到需求系统的唯一一根绳子。"""

    def test_title_without_the_id_is_named(self) -> None:
        self.init_audit()
        first = self.story().split("\n", 1)[0]
        self.rewrite_story(first, "# " + first[2:].replace(FEATURE, "").strip())
        out = self.assert_check_names("大标题缺需求编号")
        self.assertIn(FEATURE, out, "报错要把该写的编号给出来")

    def test_offline_falls_back_to_the_shape(self) -> None:
        """离线只有一份 story，不知道 feature 叫什么——此时核形态，不放过去。"""
        story = Path(self._tmp.name) / "AR" / "story.md"
        story.parent.mkdir(parents=True, exist_ok=True)
        text = self.story()
        story.write_text(text.replace(text.split("\n", 1)[0], "# 某需求"), encoding="utf-8")
        proc = subprocess.run(
            ["node", str(BUILD), "check", "--offline", "--story", str(story),
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(1, proc.returncode)
        self.assertIn("大标题缺需求编号", (proc.stderr or "") + (proc.stdout or ""))


class TestRedlineScope(StoryBuildCase):
    """逐类作用域：多数红线只管附录之外，取证语言与装置词在附录里同样不该有。"""

    def _put_in_appendix(self, line: str) -> None:
        bodies = _chapter_bodies(self.story_path)
        anchor = bodies[_appendix_title()].split("\n")[0]
        self.rewrite_story(anchor, anchor + "\n\n" + line)

    def test_search_phrase_in_the_appendix_is_named(self) -> None:
        self.init_audit()
        self.assertEqual(0, self.check_output()[0])
        self._put_in_appendix("检索挂失回执封装零命中。")
        self.assert_check_names("这是起草过程")

    def test_harness_word_in_the_appendix_is_named(self) -> None:
        self.init_audit()
        self._put_in_appendix("本次交付先以模拟实现替代真实通道。")
        self.assert_check_names("造它的装置与流程说的话")

    def test_identifiers_stay_legal_in_the_appendix(self) -> None:
        """附录仍是工程标识的落点——顺手把它一起收紧，作者就无处可写了。"""
        self.init_audit()
        self._put_in_appendix("| 接口 | 用途 |\n|---|---|\n| queryLossState | 查挂失结果 |")
        self.assertEqual(0, self.check_output()[0])


class TestDecisionUnits(StoryBuildCase):
    """决策登记走独立派生通道：取舍理由在材料里没有，它是起草时判出来的。"""

    DECISIONS = {
        "decisions": [
            {"id": "DEC-001", "status": "settled",
             "title": "挂失结果以卡片服务的回执为准",
             "clarification": "**要定的事**：挂失办没办成，以哪一侧的说法为准。\n\n"
                              "**根据**：本端只有请求态，判不了卡是否真的停用。\n\n"
                              "**结论与影响**：以卡片服务的回执为准，页面照回执显示。",
             "decider": "需求负责人", "category": "验收口径"},
            {"id": "DEC-002", "status": "settled",
             "title": "同卡同状态的重复提交按一次算",
             "clarification": "**要定的事**：同一张卡短时间内重复提交怎么处理。\n\n"
                              "**根据**：重复提交只会让用户以为办了两次。\n\n"
                              "**结论与影响**：按一次算，第二次直接回到等待态。",
             "decider": "需求负责人", "category": "流程顺序与准入"},
            {"id": "DEC-003", "status": "open",
             "title": "线下渠道的入口这轮收不收",
             "clarification": "**要定的事**：线下渠道的入口要不要一起收进本单。\n\n"
                              "**可选的做法**：1. 本单先不收，等渠道方给时间表；"
                              "2. 一起收，范围扩到渠道侧。\n\n"
                              "**建议**：按第 1 种做。",
             "decider": "产品负责人", "category": "范围与拆分"},
        ],
    }

    def write_decisions(self, decisions=None) -> None:
        path = self.src / "decisions.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["decisions"] = decisions if decisions is not None else self.DECISIONS["decisions"]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_an_empty_register_speaks_up(self) -> None:
        """一条决策都没登记时要出声——不能当作「这个需求没做过任何判断」静默通过。"""
        self.write_decisions([])
        proc = self.run_build("init")
        self.assertEqual(0, proc.returncode)
        self.assertIn("决策登记里一条都没有", proc.stdout)

    def test_editing_a_decision_never_trips_the_material_drift_gate(self) -> None:
        """决策件是流程里的活件：评审回填、遗漏补写都是既定动作，不该撞指纹门禁。"""
        self.write_decisions()
        self.init_audit()
        self.assertEqual(0, self.check_output()[0])
        self.write_decisions(self.DECISIONS["decisions"] + [
            {"id": "DEC-004", "status": "open", "title": "回执超时的等待时长",
             "clarification": "**要定的事**：回执迟迟不到时等多久。\n\n"
                              "**可选的做法**：1. 先按现网默认值；2. 等渠道方给数。\n\n"
                              "**建议**：按第 1 种做。",
             "decider": "需求负责人", "category": "规则与数值"}])
        code, out = self.check_output()
        self.assertEqual(0, code, out)
        self.assertNotIn("材料在枚举之后变了", out)


class TestOwnRequirementIdIsNotAnIdentifier(StoryBuildCase):
    """本需求自己的编号不是工程标识。

    ①b 要求大标题带着它，材料清单也要写清这份文档出自哪张单——它恰恰是归档件与
    需求系统之间唯一的绳子。判它违规，两条判据就打架，作者无路可走。
    实测一轮实跑卡死在这里：模型反复改标题、始终过不了，最后没登记成文就交了。

    这条**离线跑不出来**（离线没有来源单元，标识符表是空的），所以必须在线跑。
    """

    def _put_id_in_materials(self) -> None:
        # 目录自己建：夹具里的空目录不进版本控制，clone 出来就没有
        spec = self.root / "doc" / "features" / FEATURE / "spec" / "spec.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(
            "# " + FEATURE + " 规格\n\n"
            "## 1. 范围\n\n本单 " + FEATURE + " 只改提交入口。\n",
            encoding="utf-8")

    def test_the_title_carrying_the_id_passes(self) -> None:
        self._put_id_in_materials()
        self.init_audit()
        code, out = self.check_output()
        self.assertEqual(0, code, out)
        self.assertIn(FEATURE, self.story().split("\n", 1)[0], "夹具的大标题本来就带编号")

    def test_another_repo_identifier_is_still_named(self) -> None:
        """放行的只有本需求编号这一个——别的标识照拦，不然等于把 ⑩ 关掉。"""
        self._put_id_in_materials()
        self.init_audit()
        first = self.story().split("\n", 1)[0]
        self.rewrite_story(first, first + "\n\n提交走 queryLossEligibility 这个接口。")
        self.assert_check_names("工程标识")


class TestCopyeditTrace(StoryBuildCase):
    """统稿留痕：恰好七行，**内容不判**。

    统稿是唯一一步没有产物的动作，于是跳过它零成本——实测两份产物都有「同一件事
    讲三遍」「图题一章一个样」这类只有通读才看得见的毛病，而门禁全绿。
    留痕不是为了核内容（那归裁决面与抽样人核），是为了让「没做」留下痕迹。
    """

    SIX = "\n".join("第 {} 项：查过，无需改。".format(i) for i in range(1, 8)) + "\n"

    def write_copyedit(self, text: str) -> None:
        (self.src / "copyedit.md").write_text(text, encoding="utf-8")

    def test_missing_file_is_named(self) -> None:
        (self.src / "copyedit.md").unlink()
        self.init_audit()
        self.assert_check_names("copyedit.md")

    def test_exactly_seven_lines_passes(self) -> None:
        self.write_copyedit(self.SIX)
        self.init_audit()
        code, out = self.check_output()
        self.assertEqual(0, code, out)

    def test_writing_more_is_not_rewarded(self) -> None:
        """写成检查报告不加分——不然下一轮就有人为了显得认真而灌水。"""
        self.write_copyedit(self.SIX + "另外还查了一遍标题。\n")
        self.init_audit()
        self.assert_check_names("恰好 7 行")

    def test_blank_lines_do_not_count(self) -> None:
        self.write_copyedit(self.SIX.replace("\n", "\n\n"))
        self.init_audit()
        self.assertEqual(0, self.check_output()[0])


class TestFormLints(StoryBuildCase):
    """三条形态 lint：图的承接与图题、材料清单的行形态、正文小节的编号。

    三条此前都只写在模板注释里，实测两轮四份产物一条都没达成——三张图全部把说明
    写在图后（读者先看见图再看见它是什么）、材料清单被写成表且没有一条能定位到原件、
    小节编号一章一个样。有判据的形态则全部达成。形态要么接上判据，要么承认它是建议。
    """

    IMAGE = "![图 1 · 提交入口页面布局](entry.png)"

    def put_features(self, body: str) -> None:
        text = self.story()
        head = "## 功能说明\n\n"
        start = text.index(head) + len(head)
        end = text.index("\n## ", start)
        self.story_path.write_text(text[:start] + body + text[end:], encoding="utf-8")

    def put_materials(self, body: str) -> None:
        text = self.story()
        head = "### E. 材料清单\n\n"
        start = text.index(head) + len(head)
        self.story_path.write_text(text[:start] + body, encoding="utf-8")

    # ---- lint 1：图前承接 + 图题形态 ----

    def test_an_image_with_a_lead_sentence_passes(self) -> None:
        self.put_features("### 6.1 提交与回执\n\n图 1 是提交入口的位置：\n\n"
                          + self.IMAGE + "\n")
        self.init_audit()
        code, out = self.check_output()
        self.assertNotIn("图前一句承接", out)
        self.assertNotIn("图题", out)

    # ---- lint 2：材料清单的行形态 ----

    def test_a_material_list_written_as_a_table_is_named(self) -> None:
        self.put_materials("| 材料 | 贡献 |\n|---|---|\n| 甲需求 PRD | 状态取值 |\n")
        self.init_audit()
        self.assert_check_names("材料清单用列表不用表")

    def test_a_material_row_without_a_link_is_named(self) -> None:
        self.put_materials("- 甲需求 PRD：提交回执的业务诉求与状态取值。\n")
        self.init_audit()
        self.assert_check_names("每份材料给一条原文链接")

    def test_a_link_that_cannot_be_opened_is_named(self) -> None:
        """链接得能点开——裸相对路径解析错一层就是断链。

        实测的失效形态：E 节写 `[RR/prd.md](RR/prd.md)`。story.md 在 AR/ 下，
        这个路径解析出来是 `AR/RR/prd.md`，不存在。行形态判抓不到它——那条只看
        链接落在需求目录的哪一段，`RR` 在允许集里就放行。「这一段允许链」与
        「这个链接能不能点开」是两件事，得分开判。
        """
        self.put_materials("- 甲需求 PRD：提交回执的业务诉求与状态取值。"
                           "原文：[RR/prd.md](RR/prd.md)\n")
        self.init_audit()
        out = self.assert_check_names("链接点不开")
        self.assertIn("RR/prd.md", out, "报错要把点不开的那个目标给出来")

    def test_a_link_that_resolves_passes(self) -> None:
        """同一份材料写对了相对层级就该过——判的是能不能点开，不是长什么样。"""
        self.put_materials("- 甲需求 PRD：提交回执的业务诉求与状态取值。"
                           "原文：[RR/prd.md](../RR/prd.md)\n")
        self.init_audit()
        code, out = self.check_output()
        self.assertNotIn("链接点不开", out)

    def test_offline_does_not_judge_whether_the_file_exists(self) -> None:
        """离线不判存在性：那时没有 feature 上下文，基准目录只能靠猜。

        判据一旦开始猜就没法解释也没法回归。金样正是离线跑的——它是独立文件，
        身边没有 RR/ 也没有 AR/，存在性判在那里必然全红。
        """
        self.put_materials("- 甲需求 PRD：提交回执的业务诉求与状态取值。"
                           "原文：[RR/prd.md](RR/prd.md)\n")
        self.init_audit()
        proc = subprocess.run(
            ["node", str(BUILD), "check", "--offline", "--story", str(self.story_path),
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertNotIn("链接点不开", (proc.stderr or "") + (proc.stdout or ""))

    def test_the_material_link_is_the_one_place_a_repo_path_may_appear(self) -> None:
        """豁免只到这一节的链接语法：正文里的仓内路径照拦。"""
        self.init_audit()
        code, out = self.check_output()
        self.assertEqual(0, code, out)          # 夹具的材料清单本来就带链接

        first = self.story().split("\n", 1)[0]
        self.rewrite_story(first, first + "\n\n实现见 doc/features/AR90001/spec/spec.md。")
        self.assert_check_names("仓内路径")


class TestAuthorWrittenNumbersAreStripped(unittest.TestCase):
    """作者自己写的裸序号要先剥掉，否则 `number` 再铺一层就是两个号。

    实测（`story-suite-20260904-091600`）：39 处小节标题里 32 处长成
    `### 1.1 1 闸机前的窘境`——`1.1` 是机器铺的，后面那个 `1` 是作者写的。

    **判据是位置不是词**：作者编号是一条从 1 开始的递增序列，一个裸整数接得上
    这条序列才算序号。上一版拿「后面不是量词」当主判据，被钱包域最常见的形态打穿——
    `20 元面额`、`30 秒超时`、`4 位密码`、`7 天内生效` 全会被剥掉第一个字，
    而量词白名单是一张会不断长的词表。量词现在退为第二道，只挡「内容数字恰好接上序列」。

    剥的动作在 `renumberStory` 里，不在 `normalizeHeading`——后者没有位置信息，
    而它被十几处标题匹配共用，剥错一个字那一节就「找不到」。
    """

    @staticmethod
    def renumber(*subsections: str) -> list[str]:
        """把几个小节摆进同一章重编号，返回 `### ` 行。"""
        body = "".join(f"### {t}\n\n正文。\n\n" for t in subsections)
        doc = "# X\n\n## 背景\n\n" + body
        script = (
            "import { renumberStory } from "
            + json.dumps((REPO_ROOT / "doc/extensions/skills/story/scripts/headings.mjs")
                         .resolve().as_uri())
            + ";import { readFileSync } from 'node:fs';"
            + "const c = JSON.parse(readFileSync("
            + json.dumps(str(REPO_ROOT / "doc/extensions/skills/story/contracts/story-chapters.json"))
            + ", 'utf-8'));"
            + "process.stdout.write(renumberStory(process.argv[1], c.chapters, c.heading_counters));")
        proc = subprocess.run(["node", "--input-type=module", "-e", script, "--", doc],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=60)
        assert proc.returncode == 0, proc.stderr
        return [l for l in proc.stdout.split("\n") if l.startswith("### ")]

    def test_a_bare_sequence_is_stripped(self) -> None:
        """1、2、3 接得上序列，全剥。"""
        self.assertEqual(
            ["### 1.1 闸机前的窘境", "### 1.2 本需求改变什么", "### 1.3 成功怎么衡量"],
            self.renumber("1 闸机前的窘境", "2 本需求改变什么", "3 成功怎么衡量"))

    def test_an_unnumbered_section_does_not_break_the_sequence(self) -> None:
        """作者漏编中间某节：他自己的序列没断，后面那个仍是序号。

        这正是实跑产物 6 章的形状——1、2、（页面状态无号）、3。
        按「等于机器序位」判就剥不掉最后那个，按序列判剥得掉。
        """
        self.assertEqual(
            ["### 1.1 签约入口", "### 1.2 签约页", "### 1.3 页面状态", "### 1.4 管理页"],
            self.renumber("1 签约入口", "2 签约页", "页面状态", "3 管理页"))

    def test_content_numbers_are_never_touched(self) -> None:
        """业务名开头的数字是内容——它们接不上序列，一个都不许动。

        这九个是复审者拿钱包域试出来的：上一版全被剥掉了第一个字。
        """
        for title in ("20 元面额的取舍", "30 秒超时", "7 天内生效", "24 小时",
                      "4 位密码", "6 位验证码", "3 方联调", "12 月账单", "2 期分批"):
            with self.subTest(title=title):
                self.assertEqual([f"### 1.1 {title}"], self.renumber(title))

    def test_a_content_number_that_lands_on_the_sequence_is_held_by_the_counter(self) -> None:
        """第二道：内容数字恰好接上序列时，看它后面是不是量词。"""
        self.assertEqual(["### 1.1 3 种签约情形"], self.renumber("3 种签约情形"))
        self.assertEqual(["### 1.1 1 元起充"], self.renumber("1 元起充"))

    def test_a_number_that_skips_the_sequence_stays(self) -> None:
        """作者跳号（1 之后直接写 3）是他写错了——留着让人看见，不猜。"""
        self.assertEqual(["### 1.1 签约入口", "### 1.2 3 管理页"],
                         self.renumber("1 签约入口", "3 管理页"))

    def test_normalize_heading_does_not_strip_bare_numbers(self) -> None:
        """`normalizeHeading` 被十几处标题匹配共用，它不碰裸序号。"""
        script = ("import { normalizeHeading } from "
                  + json.dumps((REPO_ROOT / "doc/extensions/skills/story/scripts/headings.mjs")
                               .resolve().as_uri())
                  + ";process.stdout.write(normalizeHeading(process.argv[1]));")
        for title, want in (("1 闸机前的窘境", "1 闸机前的窘境"),   # 不剥
                            ("1.1 已经带号", "已经带号"),
                            ("1. 单级带点", "单级带点"),
                            ("A. 接口", "接口")):
            with self.subTest(title=title):
                proc = subprocess.run(["node", "--input-type=module", "-e", script, "--", title],
                                      capture_output=True, text=True, encoding="utf-8",
                                      errors="replace", timeout=60)
                self.assertEqual(0, proc.returncode, proc.stderr)
                self.assertEqual(want, proc.stdout)


class TestNumbering(StoryBuildCase):
    """`number`：章序、小节序、图题序号由机器铺。

    上一轮它们是模板里的一句要求加一条 lint。实测顺境的那份做了、逆境的那份整章丢光
    ——而这件事根本不需要人来做：章序由合同定死，节序就是出现顺序，图序就是全篇顺序。
    机器铺完，判据也就不必再判自己的输出（lint 3 与图题前缀判随之退役）。
    """

    def put_features(self, body: str) -> None:
        text = self.story()
        head = "## 功能说明\n\n"
        start = text.index(head) + len(head)
        end = text.index("\n## ", start)
        self.story_path.write_text(text[:start] + body + text[end:], encoding="utf-8")

    def number(self) -> str:
        proc = self.run_build("number")
        self.assertEqual(proc.returncode, 0, f"number 跑不起来：{proc.stderr}")
        return self.story()

    def subsections(self, text: str) -> list:
        return [l for l in text.split("\n") if l.startswith("### ")]

    def test_a_missing_number_is_filled_in(self) -> None:
        self.put_features("### 提交与回执\n\n提交之后停在等待态。\n")
        self.assertIn("### 6.1 提交与回执", self.number())

    def test_a_number_from_another_chapter_is_corrected(self) -> None:
        """`### 4.1` 出现在第六章，「见 4.1」就指错地方——机器按它所在的章重编。"""
        self.put_features("### 4.1 提交与回执\n\n提交之后停在等待态。\n")
        self.assertIn("### 6.1 提交与回执", self.number())

    def test_out_of_order_numbers_are_resequenced(self) -> None:
        self.put_features("### 6.3 提交与回执\n\n提交之后停在等待态。\n\n"
                          "### 6.1 失败与重试\n\n失败之后可以重试。\n")
        subs = [s for s in self.subsections(self.number()) if s.startswith("### 6.")]
        self.assertEqual(["### 6.1 提交与回执", "### 6.2 失败与重试"], subs)

    def test_running_it_twice_changes_nothing(self) -> None:
        self.put_features("### 提交与回执\n\n提交之后停在等待态。\n")
        once = self.number()
        self.assertEqual(once, self.number(), "幂等：已经对的文件重跑一个字节都不该动")

    def test_figure_titles_are_numbered_across_the_whole_document(self) -> None:
        self.put_features("### 提交与回执\n\n下面是提交入口的位置：\n\n"
                          "![提交入口页面布局](entry.png)\n\n"
                          "状态走向如下：\n\n"
                          "![图 7 · 状态走向](flow.png)\n")
        text = self.number()
        self.assertIn("![图 1 · 提交入口页面布局](entry.png)", text)
        self.assertIn("![图 2 · 状态走向](flow.png)", text)

    def test_the_appendix_keeps_its_letters(self) -> None:
        """附录小节用字母序号，机器不动它——那是附录判据管的地方。"""
        text = self.number()
        self.assertIn("### A. 接口", text)

    def test_a_chapter_outside_the_contract_is_left_alone(self) -> None:
        """合同里没有的章原样留着：那是 check ① 要点名的事，不是编号该悄悄接受的。"""
        self.rewrite_story("## 功能说明", "## " + CHAPTER_OUT_OF_CONTRACT)
        text = self.number()
        self.assertIn("## " + CHAPTER_OUT_OF_CONTRACT, text)


class TestGoldenNumbering(unittest.TestCase):
    """金样是编号的仲裁锚：跑一遍不变，去掉号再跑还原成它。"""

    GOLDEN = REPO_ROOT / "test" / "story" / "golden" / "story-金样-AR90004.md"

    def renumber(self, text: str) -> str:
        script = (
            "import * as fs from 'node:fs';"
            "import { renumberStory } from './doc/extensions/skills/story/scripts/headings.mjs';"
            "const c = JSON.parse(fs.readFileSync("
            "'doc/extensions/skills/story/contracts/story-chapters.json','utf-8'));"
            "let s=''; process.stdin.on('data',d=>s+=d).on('end',()=>"
            "process.stdout.write(renumberStory(s, c.chapters)));"
        )
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            input=text, capture_output=True, text=True, encoding="utf-8",
            cwd=str(REPO_ROOT), timeout=60)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return proc.stdout

    def test_the_golden_is_a_fixed_point(self) -> None:
        text = self.GOLDEN.read_text(encoding="utf-8")
        self.assertEqual(text, self.renumber(text), "编号拦金样即编号错")

    def test_a_de_numbered_golden_comes_back_byte_for_byte(self) -> None:
        import re
        text = self.GOLDEN.read_text(encoding="utf-8")
        stripped = "\n".join(
            re.sub(r"!\[图\s*\d+\s*[·・]\s*", "![",
                   re.sub(r"^(#{2,4})\s+\d+(?:\.\d+)*\.?\s+", r"\1 ", line))
            for line in text.split("\n"))
        self.assertNotEqual(text, stripped, "去号版该和金样不一样，否则这条什么都没验")
        self.assertEqual(text, self.renumber(stripped))


class TestSmallLedgerItems(StoryBuildCase):
    """六件小账里能机器判的那几条：澄清正文禁标题行、装置词表。"""

    def decisions(self) -> dict:
        return json.loads((self.src / "decisions.json").read_text(encoding="utf-8"))

    def write_decisions(self, data: dict) -> None:
        (self.src / "decisions.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def a_decision(self, clarification: str) -> dict:
        """一条字段齐备的决策——本用例只想让澄清正文那一条判据翻面。"""
        contract = json.loads(
            (REPO_ROOT / "doc/extensions/skills/story/contracts/story-chapters.json")
            .read_text(encoding="utf-8"))
        category = (contract.get("decision_categories") or [{}])[0].get("key", "")
        return {
            "id": "D-1", "title": "入口的摆放位置按上游稿走", "status": "settled",
            "category": category, "decider": "产品负责人",
            "clarification": clarification,
        }

    def test_a_heading_line_in_the_clarification_is_named(self) -> None:
        """澄清正文里的小标题写成加粗段首，不用 `#` 标题行。"""
        self.init_audit()
        self.write_decisions({"decisions": [
            self.a_decision("### 背景\n\n本条说明这件事的来龙去脉。")]})
        out = self.assert_check_names("的澄清正文里有标题行")
        self.assertIn("加粗段首", out)

    def test_a_bold_lead_in_the_clarification_passes(self) -> None:
        """反面：加粗段首是定稿形态，不该被拦。"""
        self.init_audit()
        self.write_decisions({"decisions": [
            self.a_decision("**背景**：本条说明这件事的来龙去脉。")]})
        _, out = self.check_output()
        self.assertNotIn("的澄清正文里有标题行", out)

    def test_the_two_new_harness_words_are_registered(self) -> None:
        """装置词表补两词——它们是造这份文档的装置说的话，不是需求事实。

        词表是合同数据（按 kind 带作用域），不写死在脚本里。
        """
        contract = json.loads(
            (REPO_ROOT / "doc/extensions/skills/story/contracts/story-chapters.json")
            .read_text(encoding="utf-8"))
        terms = contract["language_redline"]["harness_terms"]
        for word in ("import_sources", "人话"):
            self.assertIn(word, terms)

    def test_a_harness_word_in_the_appendix_is_still_named(self) -> None:
        """装置词的作用域是全篇——换个位置它仍然不是需求事实。"""
        self.init_audit()
        appendix = _appendix_title()
        text = self.story()
        marker = f"## {appendix}"
        hit = next((l for l in text.split("\n") if l.strip().startswith(marker)), None)
        if hit is None:
            self.skipTest("夹具里没有附录章")
        self.rewrite_story(hit, hit + "\n\n这一节按 import_sources 的导入结果整理。")
        self.assert_check_names("import_sources")


class TestRetiredThings(unittest.TestCase):
    """本轮退场的东西，机制层不该再有它们的痕迹——退场靠 grep 守，不靠记性。"""

    EXT = REPO_ROOT / "doc" / "extensions"

    def ext_text(self) -> str:
        out = []
        for path in sorted(self.EXT.rglob("*")):
            if path.suffix in (".mjs", ".js", ".py", ".md", ".json", ".yaml"):
                out.append(path.read_text(encoding="utf-8", errors="replace"))
        return "\n".join(out)

    def test_the_adapt_preconditions_are_gone(self) -> None:
        """framework 版本门槛与热修清单退场——framework 的事不归 adapt 管。"""
        text = self.ext_text()
        for gone in ("3.0.0", "capability-resolution", "MaisonPrimaryButton"):
            self.assertNotIn(gone, text, f"「{gone}」还留在扩展包里")

    def test_the_adapt_work_dir_carries_the_package_version(self) -> None:
        """工作目录带版本、点开头——两个版本的工作件互不覆盖，且一眼看出是临时件。"""
        scan = (self.EXT / "skills/story-adaptation/scripts/adapt-scan.mjs").read_text(
            encoding="utf-8")
        self.assertIn(".adapt-${PKG_VERSION}", scan)
        gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("doc/extensions/.adapt-*/", gitignore)

    def test_the_entry_section_moved_into_the_skill(self) -> None:
        """入口段随 skill 走，根目录不再有它——旧路径全仓零残留。"""
        self.assertTrue((self.EXT / "skills/story/AGENTS.section.md").is_file())
        self.assertFalse((self.EXT / "AGENTS.section.md").exists())
        for path in sorted(self.EXT.rglob("*.mjs")):
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in text.split("\n"):
                if "AGENTS.section.md" in line:
                    self.assertIn("skills/story/AGENTS.section.md", line,
                                  f"{path.name} 还指着旧路径：{line.strip()}")

    def test_the_manifest_version_covers_this_round(self) -> None:
        """机制变了，manifest 版本要跟着走——它是 adapt 升级路径的唯一真源。

        **版本号写死在这里是故意的**：谁改了机制面，这一条就会红，逼他回答
        「这轮该不该升版本」。版本不升的代价不是洁癖问题——`adapt` 判态直接比它，
        版本相同判「重适配」，而重适配**不执行机制行**，于是机制改动一条都装不进
        目标工程。红了就一起改，别只把断言改绿。
        """
        manifest = (self.EXT / "manifest.yaml").read_text(encoding="utf-8")
        self.assertIn('version: "1.5.0"', manifest)


class TestLedgerFrozenAfterRegistration(StoryBuildCase):
    """成文登记之后台账随稿冻结——story.md 冻了，账本也得冻。

    实测一轮：登记 00:04，spec 阶段 00:20 又跑了一次 init，登记那一刻的落点账被冲掉。
    产物还在，它据以成文的依据换了一批，谁也看不出来。
    """

    FROZEN = ("decisions.json", "copyedit.md")

    def ledger_digest(self, name: str) -> str | None:
        path = self.src / name
        if not path.is_file():
            return None
        text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def register(self) -> None:
        """把成文态登记写进流程契约——含登记那一刻的台账指纹。"""
        flow = {
            "schema": 3, "feature": FEATURE, "status": "story_written",
            "rounds": [{"round": 1, "gates": []}],
            "story_src_digests": {n: self.ledger_digest(n) for n in self.FROZEN},
        }
        (self.root / "doc" / "features" / FEATURE / "AR" / "story-flow.json").write_text(
            json.dumps(flow, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_init_is_refused_after_registration(self) -> None:
        self.init_audit()
        self.register()
        proc = self.run_build("init")
        self.assertEqual(1, proc.returncode, "登记之后 init 还能跑，台账就没冻住")
        out = (proc.stderr or "") + (proc.stdout or "")
        self.assertIn("台账随稿冻结", out)
        self.assertNotIn("撤登记", out, "登记单向，报错不该指向一个不存在的动作")

    def test_a_changed_ledger_is_named_by_check(self) -> None:
        """拒绝两条命令挡不住有人直接改文件——指纹核对补上那一面。"""
        self.init_audit()
        self.register()
        path = self.src / "decisions.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("decisions", []).append({
            "id": "sneaked-in", "status": "settled", "title": "登记之后偷加的一条",
            "category": "范围与拆分",
            "clarification": "**要定的事**：无。\n\n**根据**：无。\n\n**结论与影响**：无。",
            "decider": "需求负责人",
        })
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        out = self.assert_check_names("与成文登记时的台账对不上")
        self.assertIn("decisions.json", out)

    def test_nothing_changes_before_registration(self) -> None:
        """登记之前一切照旧——冻结只在定稿之后生效。"""
        self.init_audit()
        self.assertEqual(0, self.run_build("init").returncode,
                         "没登记就拦 init，那是把正常流程拦了")

class Step8Case(StoryBuildCase):
    """本组用例都要一份真的材料清单——它由 `story_flow.py round` 按磁盘现状生成。"""

    review_path = property(
        lambda self: self.root / "doc" / "features" / FEATURE / "AR" / "review.md")

    def feature_root(self) -> Path:
        return self.root / "doc" / "features" / FEATURE

    def round_now(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(FLOW), "round", "--feature", FEATURE,
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def write_decision(self, extra: list[dict] | None = None) -> None:
        rows = [{
            "id": "submit-boundary", "status": "settled",
            "title": "提交入口与补卡由两张开发单分别承接",
            "clarification": "**要定的事**：提交与补卡要不要放在同一张单里做。\n\n"
                             "**根据**：上游已经拆成两张开发单。\n\n"
                             "**结论与影响**：本单只做提交与回执展示，验收不含补卡。",
            "decider": "需求负责人",
        }] + (extra or [])
        (self.src / "decisions.json").write_text(
            json.dumps({"decisions": rows}, ensure_ascii=False), encoding="utf-8")


class TestReviewComesAfterTheStory(Step8Case):
    """review 是判断的台账，而判断在成文过程中还会长出来。

    实测形态是「story 还没写完，review 先出来了」——那不是模型跑偏，
    是作业顺序把渲染排在了成文前面。顺序本身因此要成为一条判据。
    """

    def test_build_refuses_before_the_story_is_written(self) -> None:
        self.write_decision()
        self.story_path.write_text("# 交通卡紧急挂失（AR90001）\n", encoding="utf-8")
        proc = self.run_build("build")
        self.assertEqual(1, proc.returncode, "story 还没成文，review 却渲染出来了")
        out = (proc.stderr or "") + (proc.stdout or "")
        self.assertIn("story 还没成文", out)
        self.assertFalse(self.review_path.exists(), "拒绝渲染却还是落了一份 review")

    def test_build_runs_once_the_story_has_chapters(self) -> None:
        self.write_decision()
        self.assertEqual(0, self.run_build("build").returncode)
        self.assertIn("提交入口与补卡由两张开发单分别承接",
                      self.review_path.read_text(encoding="utf-8"))

    def test_rebuilding_is_byte_stable(self) -> None:
        """同一份登记表渲染两次，字节完全相同——机器区没有随机量。"""
        self.write_decision()
        self.assertEqual(0, self.run_build("build").returncode)
        first = self.review_path.read_bytes()
        self.assertEqual(0, self.run_build("build").returncode)
        self.assertEqual(first, self.review_path.read_bytes())

    def test_a_decision_found_while_writing_reaches_the_review(self) -> None:
        """成文时才发现的判断，登记之后能进 review，人已经填的表态不动。"""
        self.write_decision()
        self.assertEqual(0, self.run_build("build").returncode)
        text = self.review_path.read_text(encoding="utf-8")
        filled = text.replace(
            "审核结果：\n\n<!-- decision: submit-boundary -->",
            "审核结果：范围要含补卡入口。\n\n<!-- decision: submit-boundary -->")
        self.assertNotEqual(text, filled, "夹具变了，用例要跟着改")
        self.review_path.write_text(filled, encoding="utf-8")

        self.write_decision(extra=[{
            "id": "receipt-timeout", "status": "open",
            "title": "回执超时后由谁重试",
            "clarification": "**要定的事**：写第五章时发现材料没说超时之后谁重试。\n\n"
                             "**根据**：PRD 只写了超时按未提交处理。\n\n"
                             "**结论与影响**：待评审人定。",
            "decider": "需求负责人",
        }])
        self.assertEqual(0, self.run_build("build").returncode)
        again = self.review_path.read_text(encoding="utf-8")
        self.assertIn("回执超时后由谁重试", again, "成文中新登记的判断没进 review")
        self.assertIn("审核结果：范围要含补卡入口。", again, "人填的表态被重渲染冲掉了")

    def test_the_machine_zone_cannot_be_maintained_by_hand(self) -> None:
        """机器区改了也会被重算回来——它不是第二份真源，改它等于白改。"""
        self.write_decision()
        self.assertEqual(0, self.run_build("build").returncode)
        text = self.review_path.read_text(encoding="utf-8")
        self.review_path.write_text(
            text.replace("提交入口与补卡由两张开发单分别承接", "手改过的标题"),
            encoding="utf-8")
        self.assertEqual(0, self.run_build("build").returncode)
        again = self.review_path.read_text(encoding="utf-8")
        self.assertIn("提交入口与补卡由两张开发单分别承接", again)
        self.assertNotIn("手改过的标题", again, "机器区被人维护成了第二份真源")


class TestUxReferenceNeedsNoReadme(Step8Case):
    """`ux-reference/` 有图而没有 README —— 不阻断，也不再提起。

    那一档判据当初的话是「图片在而索引不在，导入做了一半」——它建立在
    **README 承载图片登记**之上。登记收成 `materials.json` 一处真源之后，
    README 不再是登记；图片的语义（哪张是签约页）也有了确定的家（`.captions.json`），
    于是它连「可选来源」都不是了，合同里那一条随之退场。

    实跑里这条的代价是具体的：首跑 `init` 被拦下 → 补 README → 材料指纹变了 →
    契约开出新一轮 → 轮次死锁，18 分钟；二跑它降成记一笔，仍出现两次，
    作者两次都停下来处理，其中一次顺手删了附录材料清单里的那一行。
    """

    def setUp(self) -> None:
        super().setUp()
        ux = self.feature_root() / "ux-reference"
        ux.mkdir(parents=True, exist_ok=True)
        (ux / "signup.png").write_bytes(b"\x89PNG\r\n\x1a\n1")
        (ux / "manage.png").write_bytes(b"\x89PNG\r\n\x1a\n2")
        self.assertFalse((ux / "README.md").exists(), "夹具要的就是没有 README")

    def test_init_passes_without_mentioning_the_readme(self) -> None:
        proc = self.run_build("init")
        self.assertEqual(0, proc.returncode,
                         f"有图无 README 又把 init 拦住了：{proc.stderr}")
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertNotIn("ux-reference/README.md", out,
                         "README 已不是来源，不该再被提起——那一笔两跑各出现两次")
        self.assertNotIn("导入做了一半", out, "那句话属于已退场的判据")

    def test_the_image_check_still_reads_the_manifest(self) -> None:
        """不拦不等于放弃判据：④ 图片身份照旧按 materials.json 认图。"""
        self.round_now()
        self.init_audit()
        self.rewrite_story("## 业务方案",
                           "![图 1 签约页](../ux-reference/signup.png)\n\n## 业务方案")
        _, out = self.check_output()
        self.assertNotIn("不在材料的图片登记里", out, "清单里有的图被判成没登记")


class TestImageIdentityComesFromTheManifest(Step8Case):
    """图片的身份是它的内容，登记只有一处：材料清单。

    早先登记是从材料正文的 `![](…)` 语法枚举的，于是「算不算数」取决于有没有人
    给它写过一条 markdown 链接——目录里四张、登记里两张，作者只能把差额标成不进 story。
    """

    def setUp(self) -> None:
        super().setUp()
        self.material_image = self.feature_root() / "assets" / "上游文档" / "image1.png"
        self.material_image.parent.mkdir(parents=True, exist_ok=True)
        self.material_image.write_bytes(b"PNGDATA1")
        self.round_now()
        self.init_audit()

    def put_image_ref(self, *refs: str) -> None:
        block = "\n\n".join(f"![图 {i + 1} 上游页面示意]({ref})" for i, ref in enumerate(refs))
        self.rewrite_story("## 业务方案", block + "\n\n## 业务方案")

    def test_a_reference_to_a_registered_image_passes(self) -> None:
        self.put_image_ref("../assets/上游文档/image1.png")
        _, out = self.check_output()
        self.assertNotIn("不在材料的图片登记里", out)
        self.assertNotIn("同一张图被两个路径引用", out)

    def test_an_unregistered_image_is_named(self) -> None:
        self.put_image_ref("../assets/别处/image9.png")
        self.assert_check_names("不在材料的图片登记里")

    def test_the_same_image_under_two_paths_is_named(self) -> None:
        """同一张图改个名复制进归档目录——只比文件名的判据拦不住这一种。"""
        copy = self.feature_root() / "AR" / "assets" / "签约页.png"
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_bytes(self.material_image.read_bytes())
        self.put_image_ref("../assets/上游文档/image1.png", "assets/签约页.png")
        self.assert_check_names("同一张图被两个路径引用")

    def test_a_stranger_in_the_archive_dir_is_named(self) -> None:
        """归档目录只放材料里那些图的副本，放别的等于凭空多出一张没有出处的图。"""
        stray = self.feature_root() / "AR" / "assets" / "自己画的.png"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_bytes(b"SOMETHINGELSE")
        self.put_image_ref("assets/自己画的.png")
        self.assert_check_names("不是材料里任何一张图的副本")

    def test_without_a_manifest_the_check_says_it_did_not_run(self) -> None:
        """没有清单时不许静默放过：说清楚这条判据没执行、怎么让它能执行。"""
        (self.src / "materials.json").unlink()
        self.put_image_ref("../assets/别处/image9.png")
        _, out = self.check_output()
        self.assertIn("图片身份与落点判据未执行", out)
        self.assertIn("story_flow.py round", out)


class TestMaterialListMatchesTheManifest(Step8Case):
    """材料清单列到的，与这一轮真正在手里的那几份材料对得上。"""

    LISTED = "- 甲需求 PRD：提交回执的业务诉求与状态取值。原文：[RR/prd.md](../RR/prd.md)"

    def setUp(self) -> None:
        super().setUp()
        self.round_now()
        self.init_audit()

    def test_the_listed_material_passes(self) -> None:
        _, out = self.check_output()
        self.assertNotIn("少了一份材料", out)
        self.assertNotIn("列了不是材料的东西", out)

    def test_a_missing_material_is_named(self) -> None:
        """漏一份等于那份材料没人知道——读者据这一节把材料找出来。"""
        self.rewrite_story(self.LISTED, "- 甲需求 PRD：提交回执的业务诉求与状态取值。"
                                        "原文：[别的](../AR/story-src/decisions.json)")
        out = self.assert_check_names("少了一份材料")
        self.assertIn("RR/prd.md", out)

    def test_an_intermediate_product_is_named(self) -> None:
        """本轮自己生成的记录不是材料，进了清单就把它变成倾倒区。"""
        self.rewrite_story(self.LISTED, self.LISTED
                           + "\n- 本轮的落点账：原文：[audit](../AR/story-src/audit.json)")
        self.assert_check_names("列了不是材料的东西")

    def test_without_a_manifest_the_check_says_it_did_not_run(self) -> None:
        (self.src / "materials.json").unlink()
        self.rewrite_story(self.LISTED, "- 甲需求 PRD：提交回执的业务诉求与状态取值。"
                                        "原文：[别的](../AR/story-src/decisions.json)")
        _, out = self.check_output()
        self.assertIn("的集合判据未执行", out)

    def test_one_wrong_row_is_reported_once(self) -> None:
        """有清单时按清单逐份对，目录白名单那条粗判让位——同一行报两遍，读的人以为是两个问题。

        图片文件单列成行同时踩两条：它所在的目录不在白名单里，它本身也不是「一份材料」。
        """
        image = self.feature_root() / "assets" / "入口原型说明" / "image1.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"PNGDATA1")
        self.round_now()
        self.rewrite_story(self.LISTED, self.LISTED
                           + "\n- 入口原型图：原文：[图 1](../assets/入口原型说明/image1.png)")
        _, out = self.check_output()
        hits = [line for line in out.splitlines() if "assets/入口原型说明/image1.png" in line]
        self.assertEqual(1, len(hits), "同一行被报了不止一次：%s" % hits)
        self.assertIn("列了不是材料的东西", hits[0])


class TestNonPlaceholderChecksOnlyTwoThings(Step8Case):
    """「写没写」可以机械判，「写得够不够」不行。

    所以这里只认两件事：章有正文、模板占位符换掉了。设了下限的判据逼出来的都是凑数——
    给不涉及表格的章设「至少一张表」，作者只会造一张空表。
    """

    def setUp(self) -> None:
        super().setUp()
        self.init_audit()

    def test_a_chapter_with_only_a_title_is_named(self) -> None:
        text = self.story()
        marker = "## 背景\n"
        start = text.index(marker) + len(marker)
        end = text.index("## 术语")
        self.story_path.write_text(text[:start] + "\n" + text[end:], encoding="utf-8")
        self.assert_check_names("只有标题没有正文")

    def test_a_leftover_template_placeholder_is_named(self) -> None:
        self.rewrite_story("## 术语", "## 术语\n\n{{在这里写本需求的术语}}\n")
        out = self.assert_check_names("模板占位符")
        self.assertIn("{{在这里写本需求的术语}}", out)

    def test_one_sentence_in_a_chapter_is_enough(self) -> None:
        """最短正例：某章只有一句合法内容，不因为「太短」被拦。"""
        text = self.story()
        marker = "## 背景\n"
        start = text.index(marker) + len(marker)
        end = text.index("## 术语")
        self.story_path.write_text(
            text[:start] + "\n本需求把提交回执的等待态补齐。\n\n" + text[end:],
            encoding="utf-8")
        _, out = self.check_output()
        self.assertNotIn("只有标题没有正文", out)
        for quota in ("至少", "不少于", "过短", "太短"):
            self.assertNotIn(quota, out, "有判据在拿长度下限说话：%s" % quota)


class ChaptersLandOneAtATime(Step8Case):
    """落盘只有一条路：一次一章，其余字节不动。

    作者拿编辑工具直接改整篇时，「已完成的章一个字节没动」只是期望；经这条命令落盘，
    它是机械事实。统稿也走它——要改第五章就替换第五章，不重新输出整篇：
    整篇重出是全有或全无，中途断了磁盘上什么都没有。
    """

    def setUp(self) -> None:
        super().setUp()
        self.story_path.unlink()
        self.assertEqual(0, self.run_build("skeleton").returncode)

    def titles(self) -> list[str]:
        return [c["title"] for c in json.loads(
            (REPO_ROOT / "doc/extensions/skills/story/contracts/story-chapters.json")
            .read_text(encoding="utf-8"))["chapters"]]

    def put_chapter(self, title: str, body: str) -> subprocess.CompletedProcess:
        src = self.root / "chapter.md"
        src.write_text(body, encoding="utf-8")
        return subprocess.run(
            ["node", str(BUILD), "chapter", "--feature", FEATURE,
             "--project-root", str(self.root), "--chapter", title, "--from", str(src)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    def chapter_text(self, title: str) -> str:
        text = self.story()
        start = text.index(f"## {title}")
        rest = text[start + 3:]
        nxt = rest.find("\n## ")
        return rest if nxt < 0 else rest[:nxt]

    def test_the_skeleton_has_every_chapter_and_a_pending_mark(self) -> None:
        text = self.story()
        for title in self.titles():
            self.assertIn(f"## {title}", text)
            self.assertIn(f"<!-- 待写：{title} -->", text)

    def test_the_skeleton_never_overwrites_an_existing_story(self) -> None:
        """骨架命令重跑不能把写过的内容抹掉——它是起手动作，不是重置键。"""
        self.put_chapter("背景", "用户现在拿不到凭据。\n")
        before = self.story_path.read_bytes()
        self.assertEqual(0, self.run_build("skeleton").returncode)
        self.assertEqual(before, self.story_path.read_bytes())

    def test_writing_one_chapter_leaves_the_others_byte_identical(self) -> None:
        others_before = {t: self.chapter_text(t) for t in self.titles() if t != "背景"}
        self.assertEqual(0, self.put_chapter("背景", "用户现在拿不到凭据。\n").returncode)
        self.assertIn("用户现在拿不到凭据。", self.chapter_text("背景"))
        for title, before in others_before.items():
            with self.subTest(chapter=title):
                self.assertEqual(before, self.chapter_text(title))

    def test_an_interrupted_run_only_writes_what_is_still_pending(self) -> None:
        """第 4 章中断：恢复时前三章逐字节不变，只写仍带 marker 的那几章。"""
        titles = self.titles()
        for i, title in enumerate(titles[:3]):
            self.assertEqual(0, self.put_chapter(title, f"第 {i + 1} 章的正文。\n").returncode)
        done = {t: self.chapter_text(t) for t in titles[:3]}
        proc = self.put_chapter(titles[3], "第 4 章的正文。\n")
        self.assertEqual(0, proc.returncode)
        out = (proc.stderr or "") + (proc.stdout or "")
        self.assertIn("还剩 6 章待写", out, "剩几章要报出来，恢复时才知道从哪续")
        for title, before in done.items():
            with self.subTest(chapter=title):
                self.assertEqual(before, self.chapter_text(title), "已完成的章被动过了")

    def test_no_unit_ledger_is_produced_at_any_point(self) -> None:
        """全程零 audit：从 init 到写满十章再到 check，逐单元台账一个都不该出现。

        逐单元系统退场的机械证据。它们只要还被生成，就还有人会去读、去维护，
        退场就只是名义上的。
        """
        gone = ("source-units.json", "audit.json", "story-verdicts.md")
        stages = ["init"]
        self.assertEqual(0, self.run_build("init").returncode)
        for i, title in enumerate(self.titles()):
            self.assertEqual(0, self.put_chapter(title, f"第 {i + 1} 章的正文。\n").returncode)
            stages.append(f"chapter {i + 1}")
            for name in gone:
                self.assertFalse((self.src / name).exists(),
                                 f"{stages[-1]} 之后冒出了 {name}")
        self.check_output()
        for name in gone:
            self.assertFalse((self.src / name).exists(), f"check 之后冒出了 {name}")

    def test_a_copyedit_pass_replaces_one_chapter_only(self) -> None:
        """统稿夹具：十章写完之后只改第 5 章，其余九章字节相同。"""
        titles = self.titles()
        for i, title in enumerate(titles):
            self.assertEqual(0, self.put_chapter(title, f"第 {i + 1} 章的正文。\n").returncode)
        before = {t: self.chapter_text(t) for t in titles}
        self.assertEqual(0, self.put_chapter(titles[4], "统稿之后的第 5 章。\n").returncode)
        for title in titles:
            with self.subTest(chapter=title):
                if title == titles[4]:
                    self.assertIn("统稿之后的第 5 章。", self.chapter_text(title))
                else:
                    self.assertEqual(before[title], self.chapter_text(title))

    def test_an_unknown_chapter_is_refused(self) -> None:
        proc = self.put_chapter("并不存在的章", "随便写点。\n")
        self.assertEqual(1, proc.returncode)
        self.assertIn("合同里没有", (proc.stderr or "") + (proc.stdout or ""))

    def test_an_empty_body_is_refused(self) -> None:
        """空正文不是一章：真的不涉及时那句话本身就是结论。"""
        proc = self.put_chapter("背景", "   \n")
        self.assertEqual(1, proc.returncode)
        self.assertIn("空正文不是一章", (proc.stderr or "") + (proc.stdout or ""))

    def test_the_content_goes_through_a_file_not_an_argument(self) -> None:
        """正文走文件：它带换行、引号与 markdown，任何 shell 都会再解析一遍。"""
        proc = subprocess.run(
            ["node", str(BUILD), "chapter", "--feature", FEATURE,
             "--project-root", str(self.root), "--chapter", "背景"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(1, proc.returncode)
        self.assertIn("--from", (proc.stderr or "") + (proc.stdout or ""))

    def test_check_names_the_chapters_still_pending(self) -> None:
        """骨架当成品交，要被点名——marker 是明确记号，判它不用读懂任何一句话。"""
        self.init_audit()
        out = self.assert_check_names("待写 marker")
        self.assertIn("背景", out)


class RealRunCase(unittest.TestCase):
    """拿真实一跑的产物走作者路径。

    手造的最小样本全是 LF、字段规整、图片路径不带中文目录名，真实产物哪一样都不是。
    """

    REAL = REPO_ROOT / "test" / "story" / "fixtures" / "real-run" / "AR90006"
    EXTENSION = REPO_ROOT / "doc" / "extensions"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.feature = self.root / "doc" / "features" / "AR90006"
        shutil.copytree(self.REAL, self.feature)
        ext = self.root / "doc" / "extensions"
        ext.mkdir(parents=True)
        shutil.copy2(self.EXTENSION / "manifest.yaml", ext / "manifest.yaml")
        shutil.copytree(self.EXTENSION / "knowledge", ext / "knowledge")
        self.story_path = self.feature / "AR" / "story.md"
        self.drafts = self.feature / "AR" / "story-src" / "drafts"

    def build(self, *args: str) -> subprocess.CompletedProcess:
        proc = subprocess.run(
            ["node", str(BUILD), *args, "--feature", "AR90006",
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return proc

    def draft(self, name: str) -> Path:
        return self.drafts / name

    def story(self) -> str:
        return self.story_path.read_text(encoding="utf-8")


class DraftsCarryTheDeterministicWork(RealRunCase):
    """作者拿到的不是白纸：形态、槽位表、术语起始行、流程图都已经在草稿里。

    这几样都是确定性工作，脚本在他动笔前做完；他填的是语义。
    草稿是作者区——`chapter --from` 消费它，story.md 的骨架只有章锚。
    """

    def test_a_draft_per_chapter(self) -> None:
        self.build("skeleton")
        made = sorted(p.name for p in self.drafts.glob("*.md"))
        self.assertEqual(10, len(made), made)
        self.assertTrue(made[0].startswith("01-"))

    def test_the_skeleton_itself_holds_no_seed(self) -> None:
        """种子只在草稿里：留在骨架里，作者就要把它们搬进自己的章文件。"""
        self.build("skeleton")
        story = self.story()
        self.assertNotIn("```mermaid", story, "流程图不该留在骨架里")
        self.assertNotIn("| 术语 |", story, "术语起始行不该留在骨架里")
        self.assertIn("<!-- 待写：术语 -->", story)

    def test_the_terms_seed_comes_from_the_real_crlf_spec(self) -> None:
        """真实的 spec 是 CRLF——`scopeList` 的正则曾在它上面静默零命中。"""
        self.build("skeleton")
        draft = self.draft("02-术语.md").read_text(encoding="utf-8")
        rows = [l for l in draft.split("\n") if l.startswith("|") and "---" not in l]
        self.assertGreaterEqual(len(rows), 3, "术语起始行没从 spec §0 派生出来")

    def test_the_flow_diagram_is_copied(self) -> None:
        self.build("skeleton")
        self.assertIn("```mermaid", self.draft("05-业务流程.md").read_text(encoding="utf-8"))

    def test_fixed_slots_are_rendered_not_just_described(self) -> None:
        """槽位给表头 + 分隔 + 占位，不是一行「机器核」注释。"""
        self.build("skeleton")
        draft = self.draft("04-业务方案.md").read_text(encoding="utf-8")
        self.assertIn("| 参与方 |", draft)
        self.assertIn("| {{参与方}} |", draft)
        self.assertIn("| 否了什么 |", draft)
        # 异常两张表各自搭好，不再是一句「这一章要有 2 张表」的注释
        exceptions = self.draft("07-异常与恢复.md").read_text(encoding="utf-8")
        self.assertIn("### 设计内的受限结果", exceptions)
        self.assertIn("### 需要处理的异常", exceptions)
        self.assertIn("| 受限情形 |", exceptions)
        self.assertIn("| 异常 |", exceptions)

    def test_the_appendix_draft_only_asks_for_what_is_his(self) -> None:
        """附录 A–D 归机器区，草稿里不放——放了他就要在两处维护同一张表。"""
        draft = (self.build("skeleton"), self.draft("10-附录.md").read_text(encoding="utf-8"))[1]
        self.assertIn("{{一句这一节给评审者看什么}}", draft)
        self.assertIn("- 产品需求：", draft, "材料清单的类别与链接该由清单给")
        self.assertNotIn("getAutoTopupPolicy", draft, "接口表不该进草稿")

    def test_existing_drafts_are_never_overwritten(self) -> None:
        """中断恢复：缺哪章补哪章，写过的一个字节不动。"""
        self.build("skeleton")
        mine = self.draft("02-术语.md")
        mine.write_text("## 术语\n\n我写到一半的内容\n", encoding="utf-8")
        self.draft("03-范围.md").unlink()
        self.build("skeleton")
        self.assertEqual("## 术语\n\n我写到一半的内容\n", mine.read_text(encoding="utf-8"))
        self.assertTrue(self.draft("03-范围.md").exists(), "缺的那份没补回来")


class TheMachineZoneComesFromTheSource(RealRunCase):
    """附录 A–D 每次都从当前真源重算，不读旧 story、不含占位。

    读旧的就成了「真源 + 一份会漂移的副本」；含占位则作者填了会被下一次投影打回。
    """

    def author_appendix(self) -> str:
        """作者填完草稿里属于他的那几处。"""
        draft = self.draft("10-附录.md")
        text = (draft.read_text(encoding="utf-8")
                .replace("{{一句这一节给评审者看什么}}", "给评审看这一节。")
                .replace("{{这份材料贡献了什么}}", "给出了业务规则"))
        draft.write_text(text, encoding="utf-8")
        self.build("chapter", "--chapter", "附录", "--from", str(draft))
        return self.story()

    def test_landing_the_appendix_projects_a_to_d(self) -> None:
        self.build("skeleton")
        appendix = self.author_appendix().split("## 附录", 1)[1]
        self.assertEqual(4, appendix.count("story-build:begin"), "A–D 四节没投影")
        self.assertIn("getAutoTopupPolicy", appendix)
        self.assertIn("给评审看这一节。", appendix, "作者写的目的句丢了")
        self.assertIn("给出了业务规则", appendix, "材料贡献句丢了")

    def test_the_machine_zone_holds_no_placeholder(self) -> None:
        self.build("skeleton")
        appendix = self.author_appendix().split("## 附录", 1)[1]
        for zone in appendix.split("<!-- story-build:begin ")[1:]:
            body = zone.split("<!-- story-build:end -->", 1)[0]
            self.assertNotIn("{{", body, "机器区里有作者要填的占位")

    def test_the_code_status_column_stays_out(self) -> None:
        """「代码现状」是 spec 给下游 AI 的仓内路径与检索结论，不进归档件。"""
        self.build("skeleton")
        appendix = self.author_appendix().split("## 附录", 1)[1]
        self.assertNotIn("代码现状", appendix)
        self.assertNotIn("oh-package.json5", appendix, "仓内路径进了归档件")

    def test_reprojection_follows_the_source(self) -> None:
        """真源变了，重投影跟上；作者区一个字节不动。"""
        self.build("skeleton")
        self.author_appendix()
        use = self.feature / "spec" / "knowledge-use.yaml"
        text = use.read_text(encoding="utf-8")
        self.assertIn("本项目界面不新增图片或图标", text)
        use.write_text(text.replace("本项目界面不新增图片或图标",
                                    "改过的依据：本项目界面不新增图片或图标", 1),
                       encoding="utf-8")
        self.build("project")
        story = self.story()
        self.assertIn("改过的依据", story, "重投影没跟上真源")
        self.assertEqual(4, story.count("story-build:begin"), "重投影后机器区数量变了")
        self.assertIn("给评审看这一节。", story)
        self.assertIn("给出了业务规则", story)

    def test_the_verdict_basis_comes_from_the_source(self) -> None:
        """判定的依据取 knowledge-use.yaml 的原文，不留 `{{依据}}` 让作者再抄。"""
        self.build("skeleton")
        appendix = self.author_appendix().split("## 附录", 1)[1]
        self.assertIn("方向性布局参数一律用 start/end", appendix)

    def test_tables_do_not_run_together(self) -> None:
        """多张投影表之间要空行——连着写会被 markdown 并成一张错表。"""
        self.build("skeleton")
        story = self.author_appendix()
        data = story.split("### 数据、配置与事件", 1)[1].split("### 改动边界", 1)[0]
        lines = [l.strip() for l in data.split("\n")]
        # 表头 = 下一行是分隔行的那一行。分隔行必须**非空**且只由 | - : 空格组成——
        # 少了「非空」这一条，空行也满足，于是表后的第一行数据被当成新表头。
        heads = [i for i, l in enumerate(lines)
                 if l.startswith("|") and i + 1 < len(lines) and lines[i + 1]
                 and set(lines[i + 1]) <= set("|-: ")]
        self.assertGreaterEqual(len(heads), 3, "spec §9.2/9.3/9.4 三张表没都投过来")
        for i in heads[1:]:
            self.assertEqual("", lines[i - 1], "两张表之间没有空行，markdown 会并成一张")


class WhatTheAuthorLandsIsCleanAndLinkable(RealRunCase):
    """草稿原样落盘之后，story.md 里不该留下写给作者的东西，链接也要点得开。

    作者按指引「在草稿上写、写完 chapter --from 草稿」，那么草稿里的一切都会进
    story.md：形态说明里的「spec §0」被语言红线判成工程坐标，待写标记让写完的章
    仍被数成待写，材料链接差一层 `AR/` 点不开。三样都是脚本给他的，算对是脚本的事。
    """

    def landed(self, name: str, title: str) -> str:
        draft = self.draft(name)
        self.build("chapter", "--chapter", title, "--from", str(draft))
        return self.story()

    def test_guidance_never_reaches_the_archive(self) -> None:
        self.build("skeleton")
        story = self.landed("02-术语.md", "术语")
        body = story.split("## 术语", 1)[1].split("## 范围", 1)[0]
        self.assertNotIn("<!--", body, "写给作者的注释进了归档件")
        self.assertIn("| 术语 |", body, "术语表本身该留下")

    def test_a_landed_chapter_is_no_longer_pending(self) -> None:
        """待写标记只在骨架里：它跟着草稿进正文，写完的章会一直被数成待写。"""
        self.build("skeleton")
        story = self.landed("02-术语.md", "术语")
        self.assertNotIn("待写：术语", story)
        self.assertIn("待写：范围", story, "别的章的待写标记该还在")

    def test_material_links_point_from_the_story(self) -> None:
        """链接按 story.md 所在目录算——`RR/prd.md` 在 `AR/story.md` 里点不开。"""
        self.build("skeleton")
        draft = self.draft("10-附录.md").read_text(encoding="utf-8")
        self.assertIn("(../RR/prd.md)", draft)
        self.assertNotIn("](RR/prd.md)", draft)


class ProjectionRefusesToInventContent(RealRunCase):
    """机器区宁可停下也不写占位——作者改不了它，挂着就永远不会被填。"""

    def test_a_missing_basis_stops_the_projection(self) -> None:
        """激活清单里有、判断骨架里没有——投影不替它编一个依据出来。"""
        self.build("skeleton")
        self.build("chapter", "--chapter", "附录", "--from", str(self.draft("10-附录.md")))
        use = self.feature / "spec" / "knowledge-use.yaml"
        text = use.read_text(encoding="utf-8")
        start = text.index("  - id: UX-01")
        end = text.index("  - id: ", start + 10)
        use.write_text(text[:start] + text[end:], encoding="utf-8")
        proc = subprocess.run(
            ["node", str(BUILD), "project", "--feature", "AR90006",
             "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(1, proc.returncode, "缺依据还照投不误")
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertIn("UX-01", out, "没指向缺依据的那一条")
        self.assertIn("knowledge-use.yaml", out)

    def test_a_zone_outside_the_contract_is_removed(self) -> None:
        """合同里没有的旧机器区要删：它指的真源已经没人维护了。"""
        self.build("skeleton")
        draft = self.draft("10-附录.md")
        draft.write_text(draft.read_text(encoding="utf-8")
                         + "\n\n### 旧节\n\n<!-- story-build:begin 旧节 · 由某处生成，改它请改真源 -->\n"
                         + "| 旧 |\n|---|\n| 行 |\n<!-- story-build:end -->\n",
                         encoding="utf-8")
        self.build("chapter", "--chapter", "附录", "--from", str(draft))
        story = self.story()
        self.assertNotIn("story-build:begin 旧节", story, "合同外的旧机器区没被删")
        self.assertIn("story-build:begin 接口", story)


class DraftsFollowWhatIsStillUnwritten(RealRunCase):
    """恢复时只补还没写的章：给已落盘的章重建初始草稿，等于把成品换回起点。"""

    def test_a_landed_chapter_gets_no_fresh_draft(self) -> None:
        self.build("skeleton")
        draft = self.draft("02-术语.md")
        self.build("chapter", "--chapter", "术语", "--from", str(draft))
        draft.unlink()
        self.build("skeleton")
        self.assertFalse(draft.exists(), "已落盘的章又被建了一份初始草稿")
        self.assertTrue(self.draft("03-范围.md").exists(), "还没写的章该有草稿")


class TheProjectionSpeaksTheSourceLanguage(RealRunCase):
    """投影要认真源的每一种合法写法，也要跟着它变空。

    作者按 `knowledge-use.yaml` 的规矩写「整域不适用」，投影却说他缺依据；
    spec 某一节被删空，story 里挂着上一版冒充现状——两样都是「机器区不认真源」。
    """

    def landed_appendix(self) -> str:
        self.build("skeleton")
        self.build("chapter", "--chapter", "附录", "--from", str(self.draft("10-附录.md")))
        return self.story()

    def use_file(self):
        return self.feature / "spec" / "knowledge-use.yaml"

    def test_a_domain_marked_not_applicable_projects_one_row(self) -> None:
        """整域不适用：一个域一行，域内条目不必逐条登记——那份 YAML 就是这么规定的。"""
        self.landed_appendix()
        use = self.use_file()
        text = use.read_text(encoding="utf-8")
        start = text.index("  - id: RES-01")
        end = text.index("  - id: ", start + 10)
        text = (text[:start] + text[end:]).replace(
            "constraint_domains: []",
            "constraint_domains:\n  - prefix: RES\n    applicable: false\n"
            "    reason: 本需求不新增任何工程资源，整域不适用。", 1)
        # RES 域里另一条也要移走，整域才谈得上「不逐条登记」
        start = text.index("  - id: RES-02")
        end = text.index("  - id: ", start + 10)
        use.write_text(text[:start] + text[end:], encoding="utf-8")

        self.build("project")
        story = self.story()
        self.assertIn("| 整域不适用 |", story, "整域那一行没投出来")
        self.assertIn("本需求不新增任何工程资源", story, "域级依据没投出来")
        self.assertNotIn("| RES-01 |", story, "整域不适用时域内条目不该再逐条出现")

    def test_a_source_gone_empty_takes_the_old_zone_with_it(self) -> None:
        """spec 那一节被删空：旧区要删，不能留着上一版冒充现状。"""
        story = self.landed_appendix()
        self.assertIn("story-build:begin 接口", story)
        spec = self.feature / "spec" / "spec.md"
        text = spec.read_text(encoding="utf-8")
        start = text.index("### 9.1")
        end = text.index("### 9.2")
        spec.write_text(text[:start] + "### 9.1 端云接口\r\n\r\n" + text[end:], encoding="utf-8")
        self.build("project")
        self.assertNotIn("story-build:begin 接口", self.story(),
                         "真源空了，旧机器区还挂着")

    def test_a_not_applicable_line_reaches_the_appendix(self) -> None:
        """§9.5 写「不涉及：…」也是结论——丢了它，story 相对 spec 就减了一条。"""
        spec = self.feature / "spec" / "spec.md"
        text = spec.read_text(encoding="utf-8")
        start = text.index("### 9.5")
        end = text.index("## 10.") if "## 10." in text[start:] else len(text)
        end = text.index("## 10.", start)
        spec.write_text(text[:start]
                        + "### 9.5 依赖变更\r\n\r\n不涉及：本需求不新增任何三方依赖。\r\n\r\n"
                        + text[end:], encoding="utf-8")
        story = self.landed_appendix()
        boundary = story.split("### 改动边界", 1)[1].split("###", 1)[0]
        self.assertIn("不涉及：本需求不新增任何三方依赖。", boundary)
        self.assertIn("| 改动 |", boundary, "Scope 两行也要在")


if __name__ == "__main__":
    unittest.main()
