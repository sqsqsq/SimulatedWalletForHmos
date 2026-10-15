"""审查与闭环：判据全量下发、报告核对、可机械核的一致性前移到 spec 门禁。

  ① 审查请求含本阶段 overlay 的全部判据；报告缺一条，报告核对报「缺判据」（AC19）；
  ② 报告格式不合或缺判据每次都报、不计结论；同一对象已有合规结论时，换了内容的重投被拒（AC23）；
  ③ 报告里 WARN、FAIL 的判据在 notes 里要有处置记录（AC20 的记录一侧）；
  ①–③ 由落报告之后跑的 `verifier-report.mjs` 命令核，审前的 spec 门禁不读报告；
  ④ §8 与 acceptance.yaml 的编号、关联功能、同号同义，上游原始验收编号的承接（AC24）；
  ⑤ 数值来源一次列全，序数不当数值（AC25）。

全部经生产入口（spec 门禁的默认导出、pre_verifier 的默认导出）驱动。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from ext_workspace import link_harness_yaml, DEV_EXT, reader_review_details

REPO_ROOT = Path(__file__).resolve().parents[2]
EXT = DEV_EXT
REAL = REPO_ROOT / "test" / "fixtures" / "real-run" / "AR90006"
FEATURE = "AR90006"
SUBJECT = "a" * 64

DRIVER = """
import { pathToFileURL } from 'node:url';
const [hookPath, phase, feature, projectRoot] = process.argv.slice(-4);
const hook = (await import(pathToFileURL(hookPath).href)).default;
process.stdout.write(JSON.stringify(await hook({ phase, feature, projectRoot })));
"""

ACCEPTANCE = """criteria:
  - id: AC-1
    prd_function: F1, F2
    description: 第 1 条验收
  - id: AC-2
    prd_function: F2, F5, F6
    description: 第 2 条验收
  - id: AC-3
    prd_function: F6
    description: 第 3 条验收
  - id: AC-4
    prd_function: F1
    description: 第 4 条验收
  - id: AC-5
    prd_function: F6
    description: 第 5 条验收
  - id: AC-7
    prd_function: F3, F4
    description: 第 6 条验收
  - id: AC-8
    prd_function: F1, F2
    description: 第 7 条验收
  - id: AC-9
    prd_function: F1, F4
    description: 第 8 条验收
  - id: AC-6
    prd_function: F7, F8
    description: 第 9 条验收
  - id: AC-10
    prd_function: F9
    description: 第 10 条验收
  - id: AC-11
    prd_function: F10
    description: 第 11 条验收
  - id: AC-G1
    description: 第 12 条验收
  - id: AC-G2
    description: 第 13 条验收
  - id: AC-G3
    description: 第 14 条验收
  - id: AC-G4
    description: 第 15 条验收
  - id: AC-G5
    description: 第 16 条验收
"""


def report_text(ids: list[str], statuses: dict[str, str] | None = None, note: str = "") -> str:
    statuses = statuses or {}
    rows = ["| 检查项 | 状态 | 级别 | 证据 |", "|---|---|---|---|"]
    rows += [f"| {i} | {statuses.get(i, 'PASS')} | MAJOR | 看过第 3 章{note} |" for i in ids]
    return ("\n".join(rows) + "\n\n<!-- maison-verifier-result:v1 -->\n"
            f"verifier_subject_id: {SUBJECT}\nverdict: PASS\nblocker_count: 0\n"
            "<!-- /maison-verifier-result:v1 -->\n")


class ClosureCase(unittest.TestCase):
    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        (self.root / "doc").mkdir(parents=True)
        shutil.copytree(EXT, self.root / "doc" / "extensions")
        link_harness_yaml(self.root)
        self.fr = self.root / "doc" / "features" / FEATURE
        shutil.copytree(REAL, self.fr)
        # 留存的运行产物是旧清单形态（没有 origins）；现行 round 生成的清单带原材料集合，缺了它审查输入就有缺口
        manifest = self.fr / "AR" / "story-src" / "materials.json"
        manifest.write_text(json.dumps({**json.loads(manifest.read_text(encoding="utf-8")), "origins": []},
                                       ensure_ascii=False), encoding="utf-8")
        (self.fr / "acceptance.yaml").write_text(ACCEPTANCE, encoding="utf-8")
        # 走过 /story 的需求才判上游承接与数值来源
        (self.fr / "AR" / "story-src" / "story-flow.json").write_text(json.dumps(
            {"schema": 4, "status": "complete", "rounds": [{"round": 1, "gates": []}]}), encoding="utf-8")
        (self.root / "drive.mjs").write_text(DRIVER, encoding="utf-8")
        self.reports = self.fr / "spec" / "reports"

    def gate(self, phase: str = "spec") -> str:
        proc = subprocess.run(
            ["node", str(self.root / "drive.mjs"),
             str(self.root / f"doc/extensions/hooks/{'spec/post_check' if phase == 'spec' else 'shared/pre_verifier'}.mjs"),
             "spec", FEATURE, str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr[-800:])
        return proc.stdout

    def report_check(self) -> str:
        """落报告之后的核对出口：输出与退出码一起带回，问题在哪一路都看得到。"""
        proc = subprocess.run(
            ["node", str(self.root / "doc/extensions/hooks/shared/verifier-report.mjs"),
             "--feature", FEATURE, "--phase", "spec", "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        return f"exit={proc.returncode}\n{proc.stdout}{proc.stderr}"

    def overlay_ids(self) -> list[str]:
        import yaml
        return list(yaml.safe_load((EXT / "rules" / "spec-rules.overlay.yaml").read_text(encoding="utf-8"))
                    ["semantic_checks"])

    def put_report(self, text: str) -> Path:
        self.reports.mkdir(parents=True, exist_ok=True)
        rel = f"doc/features/{FEATURE}/spec/reports/verifier.report.{SUBJECT}.md"
        (self.reports / "summary.json").write_text(json.dumps(
            {"verifier_report": rel, "verifier_subject_id": SUBJECT}), encoding="utf-8")
        target = self.root / rel
        status = re.search(r"\| story_reader_review \| (\w+) \|", text)
        if status and "examined_inputs" not in text:
            # 读者审查无论结论都带四键明细：照当前必审集合写一份合规的
            text += reader_review_details(self.root, FEATURE, status.group(1),
                                          ("第 5 章与第 8 章对不上",) if status.group(1) == "FAIL" else ())
        target.write_text(text, encoding="utf-8")
        return target

    def spec(self) -> Path:
        return self.fr / "spec" / "spec.md"


class EveryCheckReachesTheReviewer(ClosureCase):
    def test_the_request_names_every_overlay_check(self) -> None:
        fragments = self.gate(phase="pre")
        for cid in self.overlay_ids():
            self.assertIn(cid, fragments, f"判据 {cid} 没进审查请求")
        self.assertIn("报告结构", fragments)

    def test_a_report_missing_a_check_is_named(self) -> None:
        ids = self.overlay_ids()
        self.put_report(report_text(ids[1:]))
        self.assertIn(f"缺判据：{ids[0]}", self.report_check())


class OneSubjectOneConclusion(ClosureCase):
    def test_a_malformed_reply_is_reported_every_run_and_not_counted(self) -> None:
        target = self.put_report("审查员说：都看过了，没问题。\n")
        for _ in range(2):
            self.assertIn("审查回复格式不合", self.report_check(), "第二次运行问题消失了")
        self.assertTrue(target.exists(), "门禁动了报告文件")
        self.assertFalse((self.reports / "verifier.conclusions.json").exists(), "格式不合的回复登记成了结论")

    def test_a_full_resubmission_after_a_missing_check_is_accepted(self) -> None:
        """缺判据的回复不登记；重投完整回复之后不再报报告问题。"""
        ids = self.overlay_ids()
        target = self.put_report(report_text(ids[1:]))
        self.assertIn(f"缺判据：{ids[0]}", self.report_check())
        self.put_report(report_text(ids))
        out = self.report_check()
        for needle in ("缺判据", "已经有过一份合规结论", "审查回复格式不合"):
            self.assertNotIn(needle, out)

    def test_the_pre_review_gate_does_not_read_the_report(self) -> None:
        """审前门禁跑在派审之前，不读本阶段报告：落一份坏回复不改变它的结论。"""
        before = self.gate()
        self.put_report("审查员说：都看过了，没问题。\n")
        after = self.gate()
        self.assertEqual(before, after, "spec 门禁读了报告：报告一落盘，审前结论就跟着变")
        self.assertNotIn("审查回复格式不合", after)

    def test_a_missing_summary_is_not_a_pass(self) -> None:
        out = self.report_check()
        self.assertIn("exit=1", out)
        self.assertIn("summary.json 不在", out)

    def test_a_second_valid_reply_for_the_same_subject_is_refused(self) -> None:
        ids = self.overlay_ids()
        target = self.put_report(report_text(ids))
        self.assertNotIn("已经有过一份合规结论", self.report_check())
        self.put_report(report_text(ids, note="，重投后换了措辞"))
        self.assertIn("已经有过一份合规结论", self.report_check())


class EveryWarnHasADisposition(ClosureCase):
    def test_a_warn_row_needs_a_line_in_the_notes(self) -> None:
        ids = self.overlay_ids()
        self.put_report(report_text(ids, {ids[0]: "WARN"}))
        out = self.report_check()
        self.assertIn(f"spec/notes.md：审查结论 {ids[0]}（WARN）没有指向这份报告的处置记录", out)
        self.assertIn("exit=1", out)
        # 上一份报告的同号处置不替这一份豁免：处置要指向当前报告对象
        (self.fr / "spec" / "notes.md").write_text(
            f"# notes\n\n- {ids[0]}（报告 bbbbbbbb）：只改表达，已按闭环表重验。\n", encoding="utf-8")
        self.assertIn(f"{ids[0]}（WARN）", self.report_check(), "旧报告的处置豁免了新报告")
        (self.fr / "spec" / "notes.md").write_text(
            f"# notes\n\n- {ids[0]}（报告 {SUBJECT[:8]}）：只改表达，已按闭环表重验。\n", encoding="utf-8")
        self.assertNotIn(f"{ids[0]}（WARN）", self.report_check())


class TheAcceptanceIdsLineUp(ClosureCase):
    def edit_spec(self, old: str, new: str) -> None:
        text = self.spec().read_text(encoding="utf-8")
        self.assertIn(old, text, "夹具变了，用例要跟着改")
        self.spec().write_text(text.replace(old, new, 1), encoding="utf-8")

    def test_aligned_ids_raise_nothing(self) -> None:
        """实跑夹具经 spec 门禁：验收编号、上游编号承接与知识登记都不报。"""
        out = self.gate()
        for needle in ("在 acceptance.yaml 里没有", "关联功能两处不一致", "同号不同义",
                       "上游材料的验收编号没有承接", "没有篇", "没有面", "manifest_digest"):
            self.assertNotIn(needle, out)

    def test_an_id_missing_from_acceptance_is_named(self) -> None:
        self.edit_spec("**AC-5** (AC-R5, F6)", "**AC-15** (AC-R5, F6)")
        self.assertIn("spec.md「验收标准」：AC-15 在 acceptance.yaml 里没有", self.gate())

    def test_a_function_drift_is_named(self) -> None:
        self.edit_spec("**AC-3** (AC-R3, F6)", "**AC-3** (AC-R3, F5)")
        self.assertIn("AC-3 的关联功能两处不一致", self.gate())

    def test_an_acceptance_id_shaped_like_a_function_is_not_split(self) -> None:
        """`AC-F1` 是验收编号：先剔掉验收编号再认功能编号，不从里面切出 `F1`。"""
        self.edit_spec("**AC-3** (AC-R3, F6)", "**AC-3** (AC-F1, F6)")
        self.assertNotIn("AC-3 的关联功能两处不一致", self.gate())

    def test_one_id_with_two_meanings_is_named(self) -> None:
        (self.fr / "acceptance.yaml").write_text(
            ACCEPTANCE + "  - id: AC-2\n    prd_function: F9\n    description: 另一件事\n", encoding="utf-8")
        self.assertIn("AC-2 同号不同义", self.gate())

    def test_an_upstream_id_that_was_renumbered_is_named(self) -> None:
        prd = self.fr / "RR" / "prd.md"
        prd.write_text(prd.read_text(encoding="utf-8") + "\n| AC-K7 | 上游写的一条验收 |\n", encoding="utf-8")
        lost = next(l for l in self.gate().split("\\n") if "上游材料的验收编号没有承接" in l)
        self.assertIn("AC-K7", lost)
        self.edit_spec("### P0 功能验收标准", "不承接：AC-K7 归兄弟单验收。\n\n### P0 功能验收标准")
        self.assertNotIn("AC-K7", self.gate())


class TheNumericSourcesAreListedInFull(ClosureCase):
    def test_every_line_is_listed_once_and_ordinals_are_skipped(self) -> None:
        lines = "".join(f"\n第 {i} 行说明：等待 {i}0 秒。\n" for i in range(1, 8))
        text = self.spec().read_text(encoding="utf-8")
        self.spec().write_text(text.replace("## 8. 验收标准", lines + "\n连续第 2 次失败时提示。\n\n## 8. 验收标准", 1),
                               encoding="utf-8")
        message = json.loads(self.gate())["message"]
        numeric = [line for line in message.split("\n") if "处数值未标来源类型" in line]
        self.assertEqual(1, len(numeric), "数值来源问题要合成一条、列全")
        for i in range(1, 8):
            self.assertIn(f"{i}0 秒", numeric[0], f"第 {i} 处没列出来")
        self.assertNotIn("第 2 次", numeric[0], "序数被当成了数值")


    def numeric_line(self, body: str) -> str:
        text = self.spec().read_text(encoding="utf-8")
        self.spec().write_text(text.replace("## 8. 验收标准", body + "\n\n## 8. 验收标准", 1), encoding="utf-8")
        message = json.loads(self.gate()).get("message", "")
        return next((line for line in message.split("\n") if "处数值未标来源类型" in line), "")

    def test_money_size_percent_and_chinese_numerals_are_values(self) -> None:
        found = self.numeric_line("单笔不超过 200 元。\n\n缓存上限 512 KB。\n\n成功率不低于 99.5%。\n\n"
                                  "超时三十秒后提示。\n\n最多重试三次，二十次后锁定。\n\n两小时内有效。")
        for value in ("200 元", "512 KB", "99.5%", "三十秒", "三次", "二十次", "两小时"):
            self.assertIn(value, found, f"{value} 没被当成要标来源的数值")

    def test_counts_whose_form_is_certain_are_values_wherever_they_sit(self) -> None:
        """形态就能确定是数量的次数，不论前后接什么词都核：阿拉伯数字与「两次」及以上。"""
        lines = ("连续失败两次后停用。", "连续失败 2 次后停用。", "每天最多两次重试。", "每天最多 2 次重试。",
                 "失败超过三次便停用。", "失败二十次即锁定。")
        found = self.numeric_line("\n\n".join(lines))
        for line in lines:
            self.assertIn(line.rstrip("。"), found, f"「{line}」里的次数没被当成要标来源的数值")

    def test_an_ambiguous_count_is_sent_to_the_review_not_judged_by_wording(self) -> None:
        """「一次」「二次」光看形态分不出次数还是操作名：门禁不按后接什么词猜，判项写明交审查核。"""
        found = self.numeric_line("连续失败二次后停用。\n\n每天最多二次重试。\n\n关闭前二次确认。")
        self.assertNotIn("二次", found)
        overlay = (DEV_EXT / "rules" / "spec-rules.overlay.yaml").read_text(encoding="utf-8")
        self.assertIn("「一次」「二次」机械门不核，由你判", overlay)
        self.assertIn("「两次」及以上", (DEV_EXT / "hooks" / "spec" / "author.md").read_text(encoding="utf-8"))

    def test_versions_ids_and_a_single_time_are_not_values(self) -> None:
        found = self.numeric_line("这一节一次讲清，关闭前二次确认。\n\n自 1.9.9 版起生效，编号 AR90006 的需求。\n\n"
                                  "第 3 次失败时提示。\n\n第二次进入时回填。")
        for word in ("一次", "二次", "1.9.9", "AR90006", "第 3 次", "第二次"):
            self.assertNotIn(word, found, f"{word} 被当成了阈值")


class TheUpstreamNameIsALocatableMaterial(ClosureCase):
    """依据标签要指认到本轮唯一一份材料或一条已定决定：泛称不放行，重名给唯一写法；解析与任务包、附录投影同源。"""

    def setUp(self) -> None:
        super().setUp()
        (self.fr / "AR" / "story-src" / "materials.json").write_text(json.dumps({
            "schema": 2, "materials": [], "sources": [],
            "origins": [{"path": p, "sha256": "sha256:0", "kind": "direct", "readable_paths": [p]}
                        for p in ("RR/prd.md", "SR/design.md", "AR/design.md")]}), encoding="utf-8")

    def names(self, *tags: str) -> str:
        body = "".join(f"\n超时 {i}0 秒（上游约束：{t}）。\n" for i, t in enumerate(tags, 1))
        text = self.spec().read_text(encoding="utf-8")
        self.spec().write_text(text.replace("## 8. 验收标准", body + "\n## 8. 验收标准", 1), encoding="utf-8")
        message = json.loads(self.gate()).get("message", "")
        return next((line for line in message.split("\n") if "依据标签要指认到" in line), "")

    def test_registered_names_pass(self) -> None:
        line = self.names("产品需求", "系统设计", "SR/design.md", "prd.md")
        for tag in ("产品需求", "系统设计", "SR/design.md", "prd.md"):
            self.assertNotIn(f"「{tag}」", line)

    def test_a_generic_name_and_an_ambiguous_one_are_named(self) -> None:
        line = self.names("上游文档", "design.md")
        self.assertIn("「上游约束：上游文档」对不上本轮任何一份材料", line)
        self.assertIn("「上游约束：design.md」对上了 2 份", line)

    def test_real_file_names_with_brackets_commas_and_spaces_pass(self) -> None:
        """合同允许真实文件名带括号、逗号、空格：照登记的名字写就认，不按标点截断（G02）。"""
        manifest = self.fr / "AR" / "story-src" / "materials.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        extra = ["inbox/规则(v2).md", "inbox/规则（终版）.md", "inbox/规则,定稿.md", "inbox/会议 纪要.md"]
        data["origins"] += [{"path": p, "sha256": "sha256:0", "kind": "converted-source", "readable_paths": [p]}
                            for p in extra]
        manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tags = ("规则(v2).md", "规则（终版）", "规则,定稿.md", "会议 纪要.md", "inbox/规则(v2).md")
        line = self.names(*tags)
        for tag in tags:
            self.assertNotIn(f"「{tag}", line, f"合法的登记名被截断后判成对不上：{line}")
        for cut in ("规则(v2", "规则（终版", "「规则」"):
            self.assertNotIn(cut, line)

    def meeting(self, stem: str, sha: str, file: str, recorded: str | None = None) -> None:
        """留存一版会议：目录名是主名与原件摘要前 8 位，原文件名只在 source.json 里。"""
        base = f"AR/story-src/meetings/{stem}/{sha[:8]}"
        (self.fr / base).mkdir(parents=True, exist_ok=True)
        (self.fr / base / "source.json").write_text(json.dumps(
            {"file": file, "sha256": recorded or sha, "text_sha256": "0"}, ensure_ascii=False), encoding="utf-8")
        manifest = self.fr / "AR" / "story-src" / "materials.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["origins"].append({"path": f"{base}/original.docx", "sha256": f"sha256:{sha[:16]}", "kind": "meeting",
                                "readable_paths": [f"{base}/raw.md", f"{base}/evidence.md"]})
        manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_a_meeting_is_cited_by_its_original_file_name(self) -> None:
        """会议原件留存为 original.docx：作者写的是会上那份文件的原名，认得到那一版。"""
        self.meeting("评审纪要（终版）", "ab" * 32, "评审纪要（终版）.docx")
        line = self.names("评审纪要（终版）.docx", "评审纪要（终版）")
        self.assertEqual("", line, "会议原名认不到")

    def test_two_versions_of_one_meeting_need_the_version(self) -> None:
        self.meeting("周会", "11" * 32, "周会.docx")
        self.meeting("周会", "22" * 32, "周会.docx")
        line = self.names("周会.docx", "周会.docx@11111111")
        self.assertIn("「上游约束：周会.docx」对上了 2 份", line)
        self.assertIn("周会.docx@22222222", line, "歧义没给出唯一写法")
        self.assertNotIn("「周会.docx@11111111」", line)

    def test_a_meeting_whose_record_does_not_match_is_reported_not_guessed(self) -> None:
        self.meeting("周会", "33" * 32, "周会.docx", recorded="44" * 32)
        line = self.names("周会.docx")
        self.assertIn("对不上本轮任何一份材料", line)
        self.assertIn("source.json", line, "元数据坏了没有点名，作者只能猜目录名")

    def test_a_settled_decision_is_a_basis_and_an_open_one_is_not(self) -> None:
        (self.fr / "AR" / "story-src" / "decisions.json").write_text(json.dumps({"decisions": [
            {"id": "D1", "status": "settled", "title": "上限定为 200", "clarification": "会上产品负责人定", "decider": "产品负责人"},
            {"id": "D2", "status": "open", "title": "要不要再验证", "clarification": "两种做法", "decider": "支付负责人"},
            {"id": "D3", "status": "settled", "title": "无依据", "clarification": "", "decider": "产品负责人"},
        ]}, ensure_ascii=False), encoding="utf-8")
        body = "\n上限 200 元（已确认决定：D1）。\n\n再验证 2 次（已确认决定：D2）。\n\n等 3 秒（已确认决定：D3）。\n\n等 4 秒（已确认决定：D9）。\n"
        text = self.spec().read_text(encoding="utf-8")
        self.spec().write_text(text.replace("## 8. 验收标准", body + "\n## 8. 验收标准", 1), encoding="utf-8")
        message = json.loads(self.gate()).get("message", "")
        line = next((x for x in message.split("\n") if "依据标签要指认到" in x), "")
        self.assertNotIn("已确认决定：D1」", line)
        self.assertIn("「已确认决定：D2」：这条是 open", line)
        self.assertIn("「已确认决定：D3」：登记缺澄清正文或 decider", line)
        self.assertIn("「已确认决定：D9」：decisions.json 里没有这个 id", line)
        self.assertNotIn("：上限 200 元（已确认决定：D1）", message, "已确认决定是合法的来源类型")

    def test_a_longer_unregistered_name_is_not_taken_for_a_registered_prefix(self) -> None:
        line = self.names("产品需求说明", "规则")
        self.assertIn("「上游约束：产品需求说明」对不上本轮任何一份材料", line)
        self.assertIn("「上游约束：规则」对不上本轮任何一份材料", line)


    def test_a_tag_without_a_material_list_is_named(self) -> None:
        (self.fr / "AR" / "story-src" / "materials.json").unlink()
        line = self.names("产品需求")
        self.assertIn("还没有材料清单", line)

    def test_a_duplicated_decision_is_not_a_basis(self) -> None:
        (self.fr / "AR" / "story-src" / "decisions.json").write_text(json.dumps({"decisions": [
            {"id": "D1", "status": "open", "title": "甲", "clarification": "两种做法", "decider": "产品负责人"},
            {"id": "D1", "status": "settled", "title": "甲", "clarification": "会上定了", "decider": "产品负责人"},
        ]}, ensure_ascii=False), encoding="utf-8")
        body = "\n上限 200 元（已确认决定：D1）。\n"
        text = self.spec().read_text(encoding="utf-8")
        self.spec().write_text(text.replace("## 8. 验收标准", body + "\n## 8. 验收标准", 1), encoding="utf-8")
        message = json.loads(self.gate()).get("message", "")
        line = next((x for x in message.split("\n") if "依据标签要指认到" in x), "")
        self.assertIn("D1 各登记了不止一条", line)
        self.assertIn("「已确认决定：", line, "重复的 D1 被当成了已定依据")

    def test_a_broken_meeting_record_is_reported_without_any_bad_tag(self) -> None:
        self.meeting("周会", "55" * 32, "周会.docx", recorded="66" * 32)
        line = self.names("产品需求")
        self.assertIn("source.json", line, "登记缺口要等标签报错才出现")


class TheDocumentFollowsItsTemplateForm(ClosureCase):
    """H1 照模板的文档类型、占位换掉；模板章节里的 `>` 流程提示不留在文档里。文档自己的引用块不管。"""

    TEMPLATE = ("# {功能模块名称} — 需求规格（Spec）\n\n> **版本**: v1.0\n\n## 0. 术语映射表\n\n"
                "> **本节是本 spec 的第一道 BLOCKER**：\n\n| 原始术语 |\n|---|\n")

    def form(self, text: str) -> list[str]:
        driver = ("const m = await import(process.argv[1]);"
                  "process.stdout.write(JSON.stringify(m.templateFormProblems(process.argv[2], process.argv[3], 'spec.md')));")
        proc = subprocess.run(["node", "--input-type=module", "-e", driver,
                               (self.root / "doc/extensions/hooks/shared/chapters.mjs").as_uri(), text, self.TEMPLATE],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def test_a_named_document_with_its_own_quote_passes(self) -> None:
        text = "# 交通卡自动充值 — 需求规格（Spec）\n\n> **版本**: v1.0\n\n## 0. 术语映射表\n\n> 用户原话：「别让我卡在闸机前」。\n"
        self.assertEqual([], self.form(text))

    def test_a_placeholder_title_and_a_left_prompt_are_named(self) -> None:
        text = "# {功能模块名称} — 需求规格（Spec）\n\n## 0. 术语映射表\n\n> **本节是本 spec 的第一道 BLOCKER**：\n"
        got = "\n".join(self.form(text))
        self.assertIn("还留着花括号占位", got)
        self.assertIn("模板的流程提示原样留下", got)

    def test_two_titles_or_a_wrong_document_type_are_named(self) -> None:
        self.assertIn("一级标题有 2 个", "\n".join(self.form("# 甲 — 需求规格（Spec）\n\n# 乙\n")))
        self.assertIn("缺「— 需求规格（Spec）」", "\n".join(self.form("# 甲 — 实现计划\n")))


if __name__ == "__main__":
    unittest.main()


class ThePlanReviewUsesTheSameCoverageContract(ClosureCase):
    """Plan 的义务审查与读者审查同一份局部明细合同：无明细、漏必审、未核却 PASS 都拒收，完整报告收下。"""

    def plan_report(self, details: str) -> str:
        import yaml
        ids = list(yaml.safe_load((EXT / "rules" / "plan-rules.overlay.yaml").read_text(encoding="utf-8"))["semantic_checks"])
        rows = "\n".join(f"| {i} | PASS | MAJOR | 看过设计章 |" for i in ids)
        reports = self.fr / "plan" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        rel = f"doc/features/{FEATURE}/plan/reports/verifier.report.{SUBJECT}.md"
        (reports / "summary.json").write_text(json.dumps({"verifier_report": rel, "verifier_subject_id": SUBJECT}),
                                              encoding="utf-8")
        (self.root / rel).write_text("| 检查项 | 状态 | 级别 | 证据 |\n|---|---|---|---|\n" + rows
                                     + "\n\n<!-- maison-verifier-result:v1 -->\n"
                                     f"verifier_subject_id: {SUBJECT}\nverdict: PASS\nblocker_count: 0\n"
                                     "<!-- /maison-verifier-result:v1 -->\n" + details, encoding="utf-8")
        proc = subprocess.run(
            ["node", str(self.root / "doc/extensions/hooks/shared/verifier-report.mjs"),
             "--feature", FEATURE, "--phase", "plan", "--project-root", str(self.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        return f"exit={proc.returncode}\n{proc.stdout}{proc.stderr}"

    DETAILS = ("\n```yaml\nverification_result:\n  checks:\n    - id: knowledge_obligation_substance\n"
               "      status: PASS\n      details:\n        blocking_findings: []\n        advisories: []\n"
               "        examined_inputs: []\n        unreviewed: []\n```\n")

    def test_no_details_and_silent_inputs_are_refused(self) -> None:
        self.assertIn("明细里没有 knowledge_obligation_substance", self.plan_report(""))
        out = self.plan_report(self.DETAILS)
        self.assertIn("既没出现在 examined_inputs 也没列进 unreviewed", out)
        self.assertIn("plan/plan.md", out, "Plan 自己的审查对象不在必审集合里")

    def test_a_complete_plan_report_is_accepted(self) -> None:
        from ext_workspace import cover_report  # noqa: PLC0415
        out = self.plan_report(cover_report(self.DETAILS, self.root, FEATURE, "plan"))
        self.assertTrue(out.startswith("exit=0"), out[-800:])

