"""做判断的那一刻把原义送到：知识任务、审查任务书、决策登记与路由各自送到该给的那一份。

锁的是送达，不是判断：
  ① 规约连附注一起按原文送到知识任务，不在册的编号报出来；
  ② 处置是评审动作的条目适用时不产生代码要求：不要验收桥，也不要实体上的义务；
  ③ verifier 任务书里原条目与当前判断并列（spec 判断、plan 契约），会议逐话题判断/原话/当前结果并列，
     上游图与承接它的 story 图并排——取不到的写未验证，不给空；
  ④ 选方案的议题要有「建议」段；⑤ 章级合同表跟着模板选定的位置只铺一次；⑥ 归档后下一步是 done。
全部用中性题材；判断对不对归审查，这里不判。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_knowledge_protocol as kp  # noqa: E402
import test_neutral_knowledge as nk  # noqa: E402
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
                       f" {json.dumps(nk.FEATURE)}));")
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
        """附注是要求的一部分：判过这份规约的 Feature 拿到的原文连同条目表与附注，作者判断时读得到。"""
        self.with_constraint(notes=NOTES)
        self.write_contracts()
        proc = self.knowledge_task("plan")
        self.assertEqual(0, proc.returncode, proc.stderr)
        block = proc.stdout.split("- 位置：`doc/extensions/knowledge/constraints/neutral-domain.md`", 1)[1]
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
        self.facts[0]["value"]["items"].append(self.item("NEU-05", "applied", "本需求新增了一个出口，出口说明文档归档"))

    def test_spec_does_not_ask_for_an_acceptance_bridge(self) -> None:
        self.write_contracts()
        (self.feature_root / "acceptance.yaml").write_text(
            "criteria:\n" + "".join(f"  - id: AC-{n}\n    knowledge_refs: [{kp.REF}#NEU-0{n}]\n"
                                    for n in (1, 2, 3)), encoding="utf-8")
        message = self.hook("spec")
        self.assertNotIn("NEU-05", message)
        self.assertNotIn("的契约 的事实", message)

    def test_plan_does_not_ask_for_an_obligation(self) -> None:
        self.write_contracts(kp.contracts(second02="ut"))
        self.assertNotIn("NEU-05", self.hook("plan"))


class TheTaskBookCarriesTheOriginal(DeliveryCase):
    def test_spec_rows_put_the_entry_next_to_the_judgement(self) -> None:
        self.write_contracts()
        text = self.pre_verifier("spec")
        self.assertIn("原知识与仓内事实是审查依据", text)
        row = next(l for l in text.splitlines() if l.startswith(f"| {kp.REF}#NEU-02 |"))
        for part in ("NEU-02", "重复触发时复用同一个标识", "applied", "重试复用标识", nk.TARGET):
            self.assertIn(part, row)
        self.assertIn("本需求的出口不计耗时", next(l for l in text.splitlines() if l.startswith(f"| {kp.REF}#NEU-04 |")))

    def test_a_half_judged_domain_is_a_design_gap_not_empty(self) -> None:
        self.judged()
        self.facts[0]["value"]["items"] = self.facts[0]["value"]["items"][:1]
        self.write_contracts()
        text = self.pre_verifier("spec")
        self.assertIn("**设计缺口**", text)
        self.assertIn("相关域没有逐条判断 NEU-02", text)

    def test_plan_rows_put_the_entry_next_to_every_must(self) -> None:
        self.write_contracts(kp.contracts(second02="both"))
        row = next(l for l in self.pre_verifier("plan").splitlines() if l.startswith(f"| {kp.REF}#NEU-02 |") and "reuseTrace" in l)
        self.assertIn("重复触发时复用同一个标识", row)
        self.assertIn("interfaces.中性出口接口.reuseTrace：重试时复用入口生成的标识 · ut", row)
        self.assertIn("interfaces.中性出口接口.emitWithTrace：重试时复用入口生成的标识 · both", row)

    def test_meeting_topics_come_with_judgement_original_and_result(self) -> None:
        src = self.src()
        (self.feature_root / "AR" / "story.md").write_text("# NK90001 中性需求\n\n## 背景\n\n正文。\n", encoding="utf-8")
        version = src / "meetings" / "澄清会" / "abcdef12"
        version.mkdir(parents=True)
        (version / "raw.md").write_text("甲 10:00：出口先按旧方式。\n乙 10:01：重试要不要换标识，先别写死。\n", encoding="utf-8")
        topic = {"id": "T1", "title": "重试标识", "finding": "重试是否换标识未定",
                 "evidence": [{"start": 2, "end": 2}], "question": "怎么处理？"}
        other = {"id": "T2", "title": "出口方式", "finding": "要问而没问", "evidence": [{"start": 2, "end": 2}],
                 "question": "要不要换？"}
        (src / "meeting-notes.json").write_text(json.dumps({"meetings": [{
            "source": "澄清会.docx", "source_sha": "abcdef1234", "topics": [topic, other]}]}, ensure_ascii=False),
            encoding="utf-8")
        (src / "doc-refresh.md").write_text("### 澄清会@abcdef12/T1 重试标识\n\n本期换标识。\n", encoding="utf-8")
        text = self.reader_task()
        section = text.split("#### 澄清会@abcdef12/T1", 1)[1].split("####", 1)[0]
        self.assertIn("**会议判断**：重试是否换标识未定", section)
        self.assertIn("> 乙 10:01：重试要不要换标识，先别写死。", section)
        self.assertIn("**会上提出的问题**：怎么处理？", section)
        self.assertIn("对照前面「人的原话原件」", section, "会上问题没有要求对照后续人答判是否解决")
        self.assertNotIn("- **人的裁决**", text, "会议裁决关卡已退出，任务书还在按它投影")
        self.assertIn("> 本期换标识。", section)
        t2 = text.split("#### 澄清会@abcdef12/T2", 1)[1]
        self.assertIn("同 T1", t2, "同一范围的原话取了两次")
        self.assertIn("**会上提出的问题**：要不要换？", t2)
        self.assertIn("doc-refresh.md 里没有这个话题的段落", t2)

    def answer(self, item_id: str = "Q1", question: str = "失败怎么处理？",
               options: list[str] | None = None, reply: str = "失败怎么处理先不定，后面负责人定",
               source_ref: str = "RR/prd.md#3", **extra) -> dict:
        record = {"ask_id": "a1", "item_id": item_id, "question": question,
                  "options": options if options is not None else ["失败后允许再试", "后续由负责人定"],
                  "reply": reply, "at": "2026-01-01T00:00:00Z", "source_ref": source_ref}
        record.update(extra)
        return record

    def write_flow(self, *answers: dict, material: dict | None = None) -> None:
        gates = [material] if material else []
        (self.src() / "story-flow.json").write_text(json.dumps(
            {"rounds": [{"round": 1, "gates": gates, "answers": list(answers)}]},
            ensure_ascii=False), encoding="utf-8")

    def test_the_human_words_entry_points_at_the_exported_originals(self) -> None:
        """任务不再另拼一份同义投影：人答原件（导出里的完整原话）是必读入口，没导出就明说缺口。"""
        src = self.src()
        (self.feature_root / "AR" / "story.md").write_text("# NK90001 中性需求\n\n背景。\n", encoding="utf-8")
        self.write_flow(self.answer())
        task = self.reader_task()
        self.assertIn("### 人的原话原件（必读）", task, "任务没有指向必读的人答原件")
        self.assertIn("人答原件没有导出", task, "没有导出人答时没有明说缺口")
        self.assertNotIn("### 人的原话记录", task, "任务还在拼一份 flow.rounds 的同义投影")
        self.assertIn("本轮仅允许人工受理", task, "判据不承认有原话、对象与期限的临时授权")
        self.assertIn("没有已开始的同图增强", task.split("### 已有的同图增强（机械事实）", 1)[1], "已有增强的机械事实没送到")

    def test_upstream_diagrams_sit_next_to_every_section_that_carries_them(self) -> None:
        """原图与写作设计登记承接它的小节并排：那一节的正文、表、图都给；没登记的明说。"""
        inbox = self.feature_root / "inbox"
        (inbox / "SR").mkdir(parents=True, exist_ok=True)
        (inbox / "SR" / "design.md").write_text(
            "## 3. 协作\n\n```mermaid\nflowchart TD\n  甲 --> 乙\n  乙 -->|失败| 丙\n```\n\n"
            "## 4. 恢复\n\n```mermaid\nflowchart TD\n  丁 --> 戊\n```\n", encoding="utf-8")
        (inbox / ".classify.json").write_text('{"SR/design.md": "SR"}', encoding="utf-8")
        proc = subprocess.run([sys.executable, str(self.ext / "skills/story/scripts/core/import_sources.py"),
                               "--feature", nk.FEATURE, "--project-root", str(self.root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
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
        unmapped = text.split("#### SR §4 #1", 1)[1]
        self.assertIn("作者没有指定承接位置", unmapped)
        self.assertIn("有没有漏讲", unmapped, "没指定位置的图要交审查者核相关关系")

    def test_the_reader_is_told_to_write_the_report_file_itself(self) -> None:
        """报告写者是读者：任务书给写入约定（写到载体分配的报告位置、完成调用前落盘、最终回复同一份），
        不再让父执行者把回复转写进文件。"""
        (self.feature_root / "AR").mkdir(parents=True, exist_ok=True)
        (self.feature_root / "AR" / "story.md").write_text("# NK90001 中性需求\n\n## 背景\n\n正文。\n", encoding="utf-8")
        text = self.reader_task()
        report = text.split("### 报告怎么写", 1)[1]
        for needle in ("完成调用前", "UTF-8 写到派审载体指定的报告文件", "最终回复原样返回同一正文",
                       "其他材料只读", "写入失败时回复写入失败及位置", "不额外包代码围栏"):
            self.assertIn(needle, report)
        for gone in ("主执行者把它原样写到", "你只读材料，不写任何文件", "它只此一份"):
            self.assertNotIn(gone, text)


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
