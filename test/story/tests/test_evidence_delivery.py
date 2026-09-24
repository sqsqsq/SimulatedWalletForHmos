"""做判断的那一刻把原义送到：判断骨架、审查任务书、决策登记与路由各自送到该给的那一份。

锁的是送达，不是判断：
  ① 规约的附注按条目切开送到判断骨架，整域通则单列，不在册的编号报出来；
  ② 处置是评审动作的条目命中后落到议题（走 /story）或写明谁表态（不走），指不到的报出来；
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
    """spec / plan 作者包与审查拿到同一份「路径 —— 用途」与读写规则位置，按知识的自我描述，不点名。"""

    def test_the_three_readers_see_the_same_guide(self) -> None:
        self.judged()
        line = "- `doc/extensions/knowledge/facts/neutral-facts.md` —— 设计出口与重试时：本工程已有的出口登记与重试入口"
        outputs = {}
        for phase in ("spec", "plan"):
            proc = subprocess.run(["node", str(self.ext / "hooks" / phase / "author.mjs"), "--feature", nk.FEATURE],
                                  cwd=self.root, capture_output=True, text=True, encoding="utf-8", timeout=90)
            self.assertEqual(0, proc.returncode, proc.stderr)
            outputs[f"{phase} 作者包"] = proc.stdout
        outputs["plan 审查"] = self.pre_verifier("plan")
        for who, text in outputs.items():
            with self.subTest(who=who):
                self.assertIn(line, text)
                self.assertIn("doc/extensions/skills/story/reference/knowledge/protocol.md", text)


class NotesReachTheJudgement(DeliveryCase):
    def skeleton(self) -> str:
        proc = nk.node(str(self.module("knowledge-use.mjs")), "init",
                       "--feature", nk.FEATURE, "--project-root", str(self.root))
        self.assertEqual(0, proc.returncode, proc.stderr)
        return self.use_path.read_text(encoding="utf-8")

    def test_an_entry_note_goes_under_its_entry_and_the_general_rule_once(self) -> None:
        self.with_constraint(notes=NOTES)
        text = self.skeleton()
        block = text.split("  - id: NEU-02", 1)[1].split("  - id: ", 1)[0]
        self.assertIn("# 附注：重试指同一次操作的再次提交。 换一个操作不算重试。", block)
        self.assertNotIn("附注", text.split("  - id: NEU-01", 1)[1].split("  - id: ", 1)[0],
                         "没有附注的条目不该有附注行")
        self.assertEqual(1, text.count("中性域·通则：出口按用户视角切"), "整域通则没单列或列了不止一次")
        self.assertNotIn("用户视角切", block, "通则被并进了上一条条目的附注")

    def test_a_note_for_an_id_that_is_not_in_the_table_is_named(self) -> None:
        self.with_constraint(notes=NOTES + "- **NEU-09**：没有这一条。\n")
        self.assertIn("「NEU-09」，条目表里没有这个编号", self.load_error())


class AReviewActionLandsOnADecision(DeliveryCase):
    def judged_with_action(self, landing: str) -> None:
        self.with_constraint(rows=REVIEW_ACTION_ROW)
        self.write_use(neutral=kp.judgement()
                       + "\n  - id: NEU-05\n    applicable: true\n    reason: 本需求新增了一个出口\n" + landing)
        self.render()

    def make_story_feature(self, ids: list[str]) -> None:
        (self.src() / "story-flow.json").write_text('{"schema": 3, "rounds": []}', encoding="utf-8")
        (self.src() / "decisions.json").write_text(
            json.dumps({"decisions": [{"id": i} for i in ids]}), encoding="utf-8")

    def test_a_story_feature_needs_an_existing_decision(self) -> None:
        self.make_story_feature(["D-1"])
        self.judged_with_action("")
        self.assertIn("NEU-05 是命中的评审动作，没写 decision", self.hook("spec"))
        self.judged_with_action("    decision: D-9\n")
        self.assertIn("decision「D-9」在 AR/story-src/decisions.json 里没有这个议题", self.hook("spec"))
        self.judged_with_action("    decision: D-1\n")
        self.assertNotIn("NEU-05", self.hook("spec"))

    def test_a_feature_without_story_writes_who_answers(self) -> None:
        self.judged_with_action("    decision: D-1\n")
        self.assertIn("没走 /story、没有议题登记——改写 impact", self.hook("spec"))
        self.judged_with_action("    impact: 出口负责人在评审记录里表态\n")
        self.assertNotIn("NEU-05", self.hook("spec"))

    def test_decision_is_only_for_review_actions(self) -> None:
        self.write_use(neutral=kp.judgement(NEU_01="applicable: true\n    requirement: 出口生成一次标识\n"
                                            "    decision: D-1"))
        proc = self.render()
        self.assertIn("NEU-01 写了 decision", proc.stderr + proc.stdout)


class TheTaskBookCarriesTheOriginal(DeliveryCase):
    def test_spec_rows_put_the_entry_next_to_the_judgement(self) -> None:
        self.judged()
        text = self.pre_verifier("spec")
        self.assertIn("原知识与仓内事实是审查依据", text)
        row = next(l for l in text.splitlines() if l.startswith("| NEU-02 |"))
        for part in ("红线", "重复触发时复用同一个标识", "有重试路径", "重试复用", "命中：重试复用标识", "§9 · 中性出口接口"):
            self.assertIn(part, row)
        self.assertIn("不命中：本需求的出口不计耗时", next(l for l in text.splitlines() if l.startswith("| NEU-04 |")))

    def test_a_missing_judgement_is_unverified_not_empty(self) -> None:
        text = self.pre_verifier("spec")
        self.assertIn("作者判断读不到", text)
        self.assertIn("未取得，未验证", text)

    def test_plan_rows_put_the_entry_next_to_every_must(self) -> None:
        self.judged()
        self.write_contracts(kp.contracts(second02="both"))
        row = next(l for l in self.pre_verifier("plan").splitlines() if l.startswith("| NEU-02 |"))
        self.assertIn("重复触发时复用同一个标识", row)
        self.assertIn("interfaces.中性出口接口.reuseTrace：重试时复用入口生成的标识 · ut", row)
        self.assertIn("interfaces.中性出口接口.emitWithTrace：重试时复用入口生成的标识 · both", row)

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

    def test_open_decisions_are_listed_for_a_consequence_check(self) -> None:
        src = self.src()
        (self.feature_root / "AR" / "story.md").write_text("# NK90001 中性需求\n\n## 背景\n\n正文。\n", encoding="utf-8")
        (src / "decisions.json").write_text(json.dumps([
            {"id": "D-2", "status": "open", "title": "超时后是否自动重试", "decider": "需求方"},
            {"id": "D-1", "status": "settled", "title": "只做签约", "decider": "需求方", "clarification": "依据"}],
            ensure_ascii=False), encoding="utf-8")
        section = self.reader_task().split("### 仍开着的选择", 1)[1].split("### 登记成已定", 1)[0]
        self.assertIn("按各选项的实际后果", section)
        self.assertIn("- **D-2** 超时后是否自动重试（该谁定：需求方）", section)
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
        self.assertIn("缺「**建议**」这一段", proc.stderr + proc.stdout)
        self.assertEqual(0, self.build(entry("retry-owner", "choice", CHOICE_BODY)).returncode)

    def test_a_confirm_needs_no_suggestion(self) -> None:
        body = "**决策点**：甲。\n\n**依据**：乙。\n\n**结论与影响**：丙。"
        self.assertEqual(0, self.build(entry("retry-owner", "confirm", body)).returncode)


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
