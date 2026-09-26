"""审查与闭环：判据全量下发、报告核对、可机械核的一致性前移到 spec 门禁。

  ① 审查请求含本阶段 overlay 的全部判据；报告缺一条，门禁报「缺判据」（AC19）；
  ② 报告格式不合或缺判据每次都报、不计结论；同一对象已有合规结论时，换了内容的重投被拒（AC23）；
  ③ 报告里 WARN、FAIL 的判据在 notes 里要有处置记录（AC20 的记录一侧）；
  ④ §8 与 acceptance.yaml 的编号、关联功能、同号同义，上游原始验收编号的承接（AC24）；
  ⑤ 数值来源一次列全，序数不当数值（AC25）。

全部经生产入口（spec 门禁的默认导出、pre_verifier 的默认导出）驱动。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from ext_workspace import link_harness_yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
EXT = REPO_ROOT / "doc" / "extensions"
REAL = REPO_ROOT / "test" / "story" / "fixtures" / "real-run" / "AR90006"
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
        self.assertIn(f"缺判据：{ids[0]}", self.gate())


class OneSubjectOneConclusion(ClosureCase):
    def test_a_malformed_reply_is_reported_every_run_and_not_counted(self) -> None:
        target = self.put_report("审查员说：都看过了，没问题。\n")
        for _ in range(2):
            self.assertIn("审查回复格式不合", self.gate(), "第二次运行问题消失了")
        self.assertTrue(target.exists(), "门禁动了报告文件")
        self.assertFalse((self.reports / "verifier.conclusions.json").exists(), "格式不合的回复登记成了结论")

    def test_a_full_resubmission_after_a_missing_check_is_accepted(self) -> None:
        """缺判据的回复不登记；重投完整回复之后不再报报告问题。"""
        ids = self.overlay_ids()
        target = self.put_report(report_text(ids[1:]))
        self.assertIn(f"缺判据：{ids[0]}", self.gate())
        target.write_text(report_text(ids), encoding="utf-8")
        out = self.gate()
        for needle in ("缺判据", "已经有过一份合规结论", "审查回复格式不合"):
            self.assertNotIn(needle, out)

    def test_a_second_valid_reply_for_the_same_subject_is_refused(self) -> None:
        ids = self.overlay_ids()
        target = self.put_report(report_text(ids))
        self.assertNotIn("已经有过一份合规结论", self.gate())
        target.write_text(report_text(ids, note="，重投后换了措辞"), encoding="utf-8")
        self.assertIn("已经有过一份合规结论", self.gate())


class EveryWarnHasADisposition(ClosureCase):
    def test_a_warn_row_needs_a_line_in_the_notes(self) -> None:
        ids = self.overlay_ids()
        self.put_report(report_text(ids, {ids[0]: "WARN"}))
        self.assertIn(f"{ids[0]}（WARN）", self.gate())
        (self.fr / "spec" / "notes.md").write_text(
            f"# notes\n\n- {ids[0]}：只改表达，已按闭环表重验。\n", encoding="utf-8")
        self.assertNotIn(f"{ids[0]}（WARN）", self.gate())


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
        self.assertIn("§8 的 AC-15 在 acceptance.yaml 里没有", self.gate())

    def test_a_function_drift_is_named(self) -> None:
        self.edit_spec("**AC-3** (AC-R3, F6)", "**AC-3** (AC-R3, F5)")
        self.assertIn("AC-3 的关联功能两处不一致", self.gate())

    def test_one_id_with_two_meanings_is_named(self) -> None:
        (self.fr / "acceptance.yaml").write_text(
            ACCEPTANCE + "  - id: AC-2\n    prd_function: F9\n    description: 另一件事\n", encoding="utf-8")
        self.assertIn("同号不同义：AC-2", self.gate())

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


if __name__ == "__main__":
    unittest.main()
