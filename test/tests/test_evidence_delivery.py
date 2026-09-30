"""做判断的那一刻把原义送到：知识任务、审查任务书、决策登记与路由各自送到该给的那一份。

锁的是送达，不是判断：
  ① 规约连附注一起按原文送到知识任务，不在册的编号报出来；
  ② 处置是评审动作的条目适用时不产生代码要求：不要验收桥，也不要实体上的义务；
  ③ verifier 任务书里原条目与当前判断并列（spec 判断、plan 契约），会议逐话题四栏并列，
     上游图与承接它的 story 图并排——取不到的写未验证，不给空；
  ④ 选方案的议题要有「建议」段；⑤ 章级合同表跟着模板选定的位置只铺一次；⑥ 归档后下一步是 done。
全部用中性题材；判断对不对归审查，这里不判。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_knowledge_protocol as kp  # noqa: E402
import test_neutral_knowledge as nk  # noqa: E402
from test_review_modes import CHOICE_BODY, ModesCase, entry  # noqa: E402
from test_writing_plan import ACCEPTANCE_LINE, PlanCase, with_chapter  # noqa: E402

NOTES = """
## 落法附注

- 出口按用户视角切：用户会说「我卡在哪一步」的那些。
- **NEU-02**：重试指同一次操作的再次提交。
  换一个操作不算重试。
"""

REVIEW_ACTION_ROW = "| NEU-05 | 出口说明文档已归档 | 基线 | 有新增出口 | （评审动作）声明归档状态 | 人工：归档动作 | 无 |\n"


class DeliveryCase(kp.ProtocolCase):
    def with_constraint(self, rows: str = "", notes: str = "") -> None:
        self.put("constraints/neutral-domain.md", kp.CONSTRAINT + rows + notes)

    def pre_verifier(self, phase: str) -> str:
        proc = nk.node("--input-type=module", "-e",
                       f"const m = (await import({nk.as_url(self.ext / 'hooks/shared/pre_verifier.mjs')})).default;"
                       f"const out = await m({{ phase: '{phase}', feature: {json.dumps(nk.FEATURE)},"
                       f" projectRoot: {json.dumps(self.root.as_posix())} }});"
                       "process.stdout.write((out.promptFragments ?? []).join('\\n\\n'));")
        self.assertEqual(0, proc.returncode, proc.stderr)
        return proc.stdout

    def reader_task(self) -> str:
        proc = nk.node("--input-type=module", "-e",
                       f"const m = await import({nk.as_url(self.ext / 'hooks/shared/reader-review-task.mjs')});"
                       f"process.stdout.write(m.readerReviewTask({json.dumps(self.root.as_posix())},"
                       f" {json.dumps(nk.FEATURE)}, 'story_reader_review'));")
        self.assertEqual(0, proc.returncode, proc.stderr)
        return proc.stdout

    def src(self) -> Path:
        path = self.feature_root / "AR" / "story-src"
        path.mkdir(parents=True, exist_ok=True)
        return path


class KnowledgeGuideReachesEveryReader(DeliveryCase):
    """spec / plan 的知识任务与 plan 审查拿到同一份「路径 —— 何时读」与读写规则位置，按知识的自我描述，不点名。"""

    def test_the_three_readers_see_the_same_guide(self) -> None:
        self.write_contracts()
        outputs = {}
        for action in ("spec", "plan"):
            proc = self.knowledge_task(action)
            self.assertEqual(0, proc.returncode, proc.stderr)
            outputs[f"{action} 知识任务"] = proc.stdout
        outputs["plan 审查"] = self.pre_verifier("plan")
        for who, text in outputs.items():
            with self.subTest(who=who):
                self.assertIn("`doc/extensions/knowledge/facts/neutral-facts.md`", text)
                self.assertIn("设计出口与重试时：本工程已有的出口登记与重试入口", text)
                self.assertIn("doc/extensions/skills/story/reference/knowledge/protocol.md", text)


class NotesReachTheJudgement(DeliveryCase):
    def test_an_entry_note_reaches_the_task_verbatim(self) -> None:
        """附注是要求的一部分：连同条目表一起按原文送到，作者判断时读得到。"""
        self.with_constraint(notes=NOTES)
        proc = self.knowledge_task()
        self.assertEqual(0, proc.returncode, proc.stderr)
        block = proc.stdout.split("knowledge/constraints/neutral-domain.md", 1)[1]
        self.assertIn("- **NEU-02**：重试指同一次操作的再次提交。", block)
        self.assertIn("- 出口按用户视角切", block)

    def test_a_note_for_an_id_that_is_not_in_the_table_is_named(self) -> None:
        self.with_constraint(notes=NOTES + "- **NEU-09**：没有这一条。\n")
        self.assertIn("「NEU-09」，条目表里没有这个编号", self.load_error())


class AReviewActionAsksForNoCode(DeliveryCase):
    """处置是评审动作的条目适用时，它要的是动作与留痕，不产生代码要求：spec 不要验收桥，plan 不要义务。"""

    def setUp(self) -> None:
        super().setUp()
        self.with_constraint(rows=REVIEW_ACTION_ROW)
        self.judged()
        self.decisions.append(self.decision("NEU-05", "applied", "本需求新增了一个出口",
                                            requirement="出口说明文档归档", target_refs=[nk.TARGET]))

    def test_spec_does_not_ask_for_an_acceptance_bridge(self) -> None:
        self.write_contracts()
        (self.feature_root / "acceptance.yaml").write_text(
            "criteria:\n" + "".join(f"  - id: AC-{n}\n    knowledge_rule: NEU-0{n}\n    knowledge_decision_id: k-neu-0{n}\n"
                                    for n in (1, 2, 3)), encoding="utf-8")
        message = self.hook("spec")
        self.assertNotIn("NEU-05", message)
        self.assertNotIn("知识应用", message)

    def test_plan_does_not_ask_for_an_obligation(self) -> None:
        self.write_contracts(kp.contracts(second02="ut"))
        self.assertNotIn("k-neu-05", self.hook("plan"))


class TheTaskBookCarriesTheOriginal(DeliveryCase):
    def test_spec_rows_put_the_entry_next_to_the_judgement(self) -> None:
        self.write_contracts()
        text = self.pre_verifier("spec")
        self.assertIn("原知识与仓内事实是审查依据", text)
        row = next(l for l in text.splitlines() if l.startswith("| k-neu-02 |"))
        for part in ("NEU-02", "重复触发时复用同一个标识", "applied", "重试复用标识", nk.TARGET):
            self.assertIn(part, row)
        self.assertIn("本需求的出口不计耗时", next(l for l in text.splitlines() if l.startswith("| k-neu-04 |")))

    def test_a_missing_judgement_is_a_design_gap_not_empty(self) -> None:
        super(kp.ProtocolCase, self).write_contracts("", [])
        text = self.pre_verifier("spec")
        self.assertIn("没有本施工单位承接的知识判断", text)
        self.assertIn("**设计缺口**", text)
        self.assertIn("没有判断激活规约 NEU-01", text)

    def test_plan_rows_put_the_entry_next_to_every_must(self) -> None:
        self.write_contracts(kp.contracts(second02="both"))
        row = next(l for l in self.pre_verifier("plan").splitlines() if l.startswith("| NEU-02 |") and "reuseTrace" in l)
        self.assertIn("重复触发时复用同一个标识", row)
        self.assertIn("interfaces.中性出口接口.reuseTrace：重试时复用入口生成的标识 · ut · k-neu-02", row)
        self.assertIn("interfaces.中性出口接口.emitWithTrace：重试时复用入口生成的标识 · both · k-neu-02", row)

    def test_meeting_topics_come_in_four_columns(self) -> None:
        src = self.src()
        (self.feature_root / "AR" / "story.md").write_text("# NK90001 中性需求\n\n## 背景\n\n正文。\n", encoding="utf-8")
        version = src / "meetings" / "澄清会" / "abcdef12"
        version.mkdir(parents=True)
        (version / "raw.md").write_text("甲 10:00：出口先按旧方式。\n乙 10:01：重试要不要换标识，先别写死。\n", encoding="utf-8")
        topic = {"id": "T1", "title": "重试标识", "finding": "重试是否换标识未定",
                 "evidence": [{"start": 2, "end": 2}], "question": "怎么处理？",
                 "options": [{"key": "a", "label": "换标识"}, {"key": "defer", "label": "保持待定"}]}
        other = {"id": "T2", "title": "出口方式", "finding": "要问而没问", "evidence": [{"start": 2, "end": 2}],
                 "question": "要不要换？", "options": [{"key": "a", "label": "换"}]}
        (src / "meeting-notes.json").write_text(json.dumps({"meetings": [{
            "source": "澄清会.docx", "source_sha": "abcdef1234", "topics": [topic, other]}]}, ensure_ascii=False),
            encoding="utf-8")
        (src / "story-flow.json").write_text(json.dumps({"rounds": [{"gates": [{
            "gate": "meeting", "meeting": "澄清会@abcdef12", "item": "T1", "chosen": "defer",
            "options": topic["options"], "basis": "用户回复：T1 保持待定"}]}]}, ensure_ascii=False), encoding="utf-8")
        (src / "doc-refresh.md").write_text("### 澄清会@abcdef12/T1 重试标识\n\n本期换标识。\n", encoding="utf-8")
        text = self.reader_task()
        section = text.split("#### 澄清会@abcdef12/T1", 1)[1].split("####", 1)[0]
        self.assertIn("**会议判断**：重试是否换标识未定", section)
        self.assertIn("> 乙 10:01：重试要不要换标识，先别写死。", section)
        self.assertIn("选了「defer」保持待定；没选：「a」换标识", section)
        self.assertIn("> 本期换标识。", section)
        t2 = text.split("#### 澄清会@abcdef12/T2", 1)[1]
        self.assertIn("同 T1", t2, "同一范围的原话取了两次")
        self.assertIn("未裁决", t2)
        self.assertIn("doc-refresh.md 里没有这个话题的段落", t2)

    def test_each_open_decision_comes_with_its_options_for_a_verdict(self) -> None:
        """U41：每条 open 议题带澄清原文，审查逐条给结论——只给标题时两个用例都放过了替人选边的正文。"""
        src = self.src()
        (self.feature_root / "AR" / "story.md").write_text("# NK90001 中性需求\n\n## 背景\n\n正文。\n", encoding="utf-8")
        (src / "decisions.json").write_text(json.dumps({"decisions": [
            {"id": "D-2", "status": "open", "title": "超时后是否自动重试", "decider": "需求方",
             "clarification": "**要定的事**：超时之后怎么办。\n\n1. 自动重试一次\n2. 提示用户手动重试"},
            {"id": "D-3", "status": "open", "title": "宽限期多长", "decider": "产品负责人",
             "clarification": "**要定的事**：宽限期。\n\n1. 24 小时\n2. 48 小时"},
            {"id": "D-1", "status": "settled", "title": "只做签约", "decider": "需求方", "clarification": "依据"}]},
            ensure_ascii=False), encoding="utf-8")
        section = self.reader_task().split("### 仍开着的选择", 1)[1].split("### 登记成已定", 1)[0]
        self.assertIn("每一条都写一句结论", section)
        self.assertIn("各选项（含保持待定）都会有的行为才是共同要求", section)
        for head, option in (("#### D-2 超时后是否自动重试", "  > 1. 自动重试一次"),
                             ("#### D-3 宽限期多长", "  > 2. 48 小时")):
            self.assertIn(head, section)
            self.assertIn(option, section, "选项原文没带到审查者手上")
        self.assertNotIn("D-1", section, "已定的归下一节")

    def test_upstream_diagrams_sit_next_to_the_story_diagram_that_carries_them(self) -> None:
        (self.feature_root / "SR").mkdir(parents=True, exist_ok=True)
        (self.feature_root / "SR" / "design.md").write_text(
            "## 3. 协作\n\n```mermaid\nflowchart TD\n  甲 --> 乙\n  乙 -->|失败| 丙\n```\n\n"
            "## 4. 恢复\n\n```mermaid\nflowchart TD\n  丁 --> 戊\n```\n", encoding="utf-8")
        (self.feature_root / "AR" / "story.md").parent.mkdir(parents=True, exist_ok=True)
        (self.feature_root / "AR" / "story.md").write_text(
            "# NK90001 中性需求\n\n## 业务流程\n\n```mermaid\n%% 图源 SR §3 #1\nflowchart TD\n  甲 --> 乙\n```\n",
            encoding="utf-8")
        text = self.reader_task().split("### 上游图与 story 里承接它的图", 1)[1]
        first = text.split("#### SR §3 #1", 1)[1].split("#### ", 1)[0]
        self.assertIn("乙 -->|失败| 丙", first, "上游原图内容没给")
        self.assertIn("story 里承接它的图", first)
        self.assertIn("%% 图源 SR §3 #1", first)
        self.assertIn("story 里没有带这个图源标记的图", text.split("#### SR §4 #1", 1)[1])


class AChoiceNeedsASuggestion(ModesCase):
    def test_a_choice_without_a_suggestion_is_named(self) -> None:
        body = CHOICE_BODY.split("**建议**", 1)[0].rstrip()
        proc = self.build(entry("retry-owner", "choice", body))
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("缺「**建议**」段", proc.stderr + proc.stdout)
        self.assertEqual(0, self.build(entry("retry-owner", "choice", CHOICE_BODY)).returncode)

    def test_a_confirm_needs_no_suggestion(self) -> None:
        body = "**决策点**：甲。\n\n**依据**：产品负责人说「就这么做」。\n\n**结论与影响**：丙。"
        self.assertEqual(0, self.build(entry("retry-owner", "confirm", body, status="settled")).returncode)


class TheChapterTableIsSeededOnce(PlanCase):
    def test_a_table_picked_in_a_section_takes_the_chapter_seed(self) -> None:
        block = "- 本章主线：做到什么算完成\n#### 验收点\n- 答：每条怎么算通过\n" + ACCEPTANCE_LINE
        self.write_plan(with_chapter("08-acceptance", block))
        self.cmd("skeleton")
        draft = self.draft("08").read_text(encoding="utf-8")
        self.assertEqual(1, draft.count("| 编号 |"), "章头与小节各铺了一张")
        self.assertLess(draft.index("验收点"), draft.index("| 编号 |"), "种子没跟着选定的那一节")


if __name__ == "__main__":
    unittest.main()
