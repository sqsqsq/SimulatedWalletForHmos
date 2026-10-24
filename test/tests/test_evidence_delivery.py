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
        (self.src() / "story-flow.json").write_text('{"schema": 4, "rounds": []}', encoding="utf-8")
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
        self.assertIn("没走 /story、没有议题登记——decision 按", self.hook("spec"))
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
        for part in ("红线", "重复触发时复用同一个标识", "有重试路径", "重试复用", "命中：重试复用标识", "技术契约 · 中性出口接口"):
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
            "options": topic["options"], "reply": "T1 保持待定", "by": "human", "outcome": "accepted"}]}]},
            ensure_ascii=False), encoding="utf-8")
        (src / "doc-refresh.md").write_text("### 澄清会@abcdef12/T1 重试标识\n\n本期换标识。\n", encoding="utf-8")
        text = self.reader_task()
        section = text.split("#### 澄清会@abcdef12/T1", 1)[1].split("####", 1)[0]
        self.assertIn("**会议判断**：重试是否换标识未定", section)
        self.assertIn("> 乙 10:01：重试要不要换标识，先别写死。", section)
        self.assertIn("选了「defer」保持待定；没选：「a」换标识；原话见「关卡人签」", section)
        self.assertEqual(1, text.count("> T1 保持待定"), "同一笔人签的原话在一份任务里贴了两遍")
        self.assertIn("> 本期换标识。", section)
        t2 = text.split("#### 澄清会@abcdef12/T2", 1)[1]
        self.assertIn("同 T1", t2, "同一范围的原话取了两次")
        self.assertIn("未裁决", t2)
        self.assertIn("doc-refresh.md 里没有这个话题的段落", t2)

    def signed(self, label: str = "后续由负责人定", **gate) -> dict:
        record = {"gate": "scope_decision", "ask_id": "a1", "no": 2, "at": "2026-01-01T00:00:00Z",
                  "options": [{"no": 1, "key": "retry", "label": "失败后允许再试"},
                              {"no": 2, "key": "later", "label": label}],
                  "chosen": "later", "label": label, "reply": "失败怎么处理先不定，后面负责人定",
                  "mapped_by": "reply", "by": "human", "outcome": "accepted"}
        record.update(gate)
        return record

    def write_flow(self, *gates: dict) -> None:
        (self.src() / "story-flow.json").write_text(json.dumps({"rounds": [{"round": 1, "gates": list(gates)}]},
                                                               ensure_ascii=False), encoding="utf-8")

    def test_the_signed_original_comes_before_the_authors_reading(self) -> None:
        """人选了「后续定」，作者登记却写成可再试：任务同时交两份不同内容，人签在前，原话取 reply。"""
        src = self.src()
        (self.feature_root / "AR" / "story.md").write_text("# NK90001 中性需求\n\n## 背景\n\n正文。\n", encoding="utf-8")
        self.write_flow(self.signed())
        (src / "decisions.json").write_text(json.dumps({"decisions": [
            {"id": "D-4", "status": "settled", "title": "失败处理", "decider": "需求方",
             "clarification": "失败后可默认再试一次"}]}, ensure_ascii=False), encoding="utf-8")
        task = self.reader_task()
        signed = task.split("### 关卡人签", 1)[1].split("\n### ", 1)[0]
        self.assertLess(task.index("### 关卡人签"), task.index("### 登记成已定"), "作者解释排在人签前面")
        self.assertIn("选了「later」后续由负责人定", signed)
        self.assertIn("「retry」失败后允许再试；「later」后续由负责人定", signed, "当时摆出的选项没带全")
        self.assertIn("> 失败怎么处理先不定，后面负责人定", signed, "人答不是 reply 原文")
        self.assertNotIn("可默认再试", signed, "作者解释混进了关卡人签")
        self.assertIn("失败后可默认再试一次", task.split("### 登记成已定", 1)[1], "作者解释没作为待核对象送到")
        self.assertIn("引用的问答原话是依据，其余是作者的解释", task, "澄清正文里引用的人答没被当作可用依据送到")
        self.assertIn("没有已开始的同图增强", task.split("### 已有的同图增强（机械事实）", 1)[1], "已有增强的机械事实没送到")
        for phrase in ("—", "basis"):
            self.assertNotIn(phrase, signed)

    def test_only_effective_human_answers_are_signatures(self) -> None:
        """模型提议、被退回的回话不呈为人签；没有流程契约是没有这类人签，契约坏了是缺口。"""
        self.write_flow(self.signed(by="model"), self.signed(outcome="rejected", reply="放好了"))
        rows = self.signed_rows()
        self.assertIn("还没有生效的人签", rows)
        self.assertNotIn("后面负责人定", rows)
        self.assertNotIn("放好了", rows)
        (self.src() / "story-flow.json").write_text("{ 坏", encoding="utf-8")
        self.assertIn("读不出关卡记录", self.signed_rows())
        (self.src() / "story-flow.json").unlink()
        self.assertIn("没有这类人签", self.signed_rows())

    def signed_rows(self) -> str:
        proc = nk.node("--input-type=module", "-e",
                       f"const m = await import({nk.as_url(self.ext / 'hooks/shared/review-inputs.mjs')});"
                       f"process.stdout.write(m.signedGateRows({json.dumps(self.feature_root.as_posix())}).join('\\n'));")
        self.assertEqual(0, proc.returncode, proc.stderr)
        return proc.stdout

    def test_both_author_packages_carry_the_same_signatures(self) -> None:
        """spec 与 plan 作者包在作者登记之前给同一份人签原文；作者登记仍在，标成待核解释。"""
        self.write_flow(self.signed())
        (self.src() / "decisions.json").write_text(json.dumps({"decisions": [
            {"id": "D-4", "status": "open", "title": "失败处理", "decider": "需求方", "clarification": "待定"}]},
            ensure_ascii=False), encoding="utf-8")
        rows = self.signed_rows()
        for phase, mine in (("spec", "### 作者登记"), ("plan", "### 作者登记里仍开着的")):
            with self.subTest(phase):
                proc = subprocess.run(["node", str(self.ext / "hooks" / phase / "author.mjs"), "--feature", nk.FEATURE],
                                      cwd=self.root, capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(0, proc.returncode, proc.stderr)
                out = proc.stdout
                self.assertIn(rows, out, "两个作者包的人签不是同一份渲染")
                self.assertLess(out.index("### 人签原文"), out.index(mine))
                self.assertIn("D-4", out.split(mine, 1)[1])

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
        task = self.reader_task()
        self.assertLess(task.index("### 先核：仍开着的选择与正文的冲突"), task.index("### 审查对象"),
                        "决定冲突要在逐章阅读之前核")
        section = task.split("### 先核：仍开着的选择与正文的冲突", 1)[1].split("### 登记成已定", 1)[0]
        self.assertIn("「核的先后」①逐条给结论", section, "没指到判法所在")
        overlay = (self.ext / "rules" / "spec-rules.overlay.yaml").read_text(encoding="utf-8")
        for needle in ("每条 open 写一句结论", "不按作者声称已覆盖的位置缩小范围", "稍后问人",
                       "各选项（含保持待定）都会有的行为才是共同要求", "不授权其中任何一个备选"):
            self.assertIn(needle, overlay, f"判法里少了「{needle}」")
            self.assertNotIn(needle, task, f"任务书又抄了一份判法：{needle}")
        for head, option in (("#### D-2 超时后是否自动重试", "  > 1. 自动重试一次"),
                             ("#### D-3 宽限期多长", "  > 2. 48 小时")):
            self.assertIn(head, section)
            self.assertIn(option, section, "选项原文没带到审查者手上")
        self.assertNotIn("D-1", section, "已定的归下一节")

    def test_upstream_diagrams_sit_next_to_every_section_that_carries_them(self) -> None:
        """原图与写作设计登记承接它的小节并排：那一节的正文、表、图都给；没登记的明说。"""
        (self.feature_root / "SR").mkdir(parents=True, exist_ok=True)
        (self.feature_root / "SR" / "design.md").write_text(
            "## 3. 协作\n\n```mermaid\nflowchart TD\n  甲 --> 乙\n  乙 -->|失败| 丙\n```\n\n"
            "## 4. 恢复\n\n```mermaid\nflowchart TD\n  丁 --> 戊\n```\n", encoding="utf-8")
        (self.feature_root / "AR" / "story.md").parent.mkdir(parents=True, exist_ok=True)
        (self.feature_root / "AR" / "story.md").write_text(
            "# NK90001 中性需求\n\n## 业务流程\n\n### 受理\n\n甲交给乙；乙失败时交丙处理。\n\n"
            "| 结果 | 谁接手 |\n|---|---|\n| 失败 | 丙 |\n", encoding="utf-8")
        (self.feature_root / "AR" / "story-src").mkdir(parents=True, exist_ok=True)
        (self.feature_root / "AR" / "story-src" / "story-template.md").write_text(
            "# 写作设计\n\n## 骨架\n\n### 05-flow\n#### 受理\n- 承接上游图：SR §3 #1\n", encoding="utf-8")
        text = self.reader_task().split("### 上游图与 story 里承接它的小节", 1)[1]
        first = text.split("#### SR §3 #1", 1)[1].split("#### ", 1)[0]
        self.assertIn("乙 -->|失败| 丙", first, "上游原图内容没给")
        self.assertIn("承接它的「业务流程 > 受理」", first)
        self.assertIn("乙失败时交丙处理", first, "承接小节的正文没给")
        self.assertIn("| 失败 | 丙 |", first, "承接小节里的表没给")
        self.assertIn("写作设计没有登记承接这张图的小节", text.split("#### SR §4 #1", 1)[1])


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
