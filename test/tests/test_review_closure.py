"""审查与闭环：判据全量下发、报告核对、可机械核的一致性前移到 spec 门禁。

  ① 审查请求含本阶段 overlay 的全部判据；报告缺一条，门禁点名缺行（AC19）；
  ② 报告格式不合、判据缺行重复或取值不合每次都报、一次报全、不计结论；重新派审得到的新报告按同样判据核，门禁不写结论账本；
     报告位置取原生阶段报告目录（含配置的 reports_dir_pattern），坏 summary 是输入故障；
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

from ext_workspace import link_harness_yaml, DEV_EXT

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


LONG_EVIDENCE = "证据（一行：文件:行 / 引文 / 数值）"


def report_text(ids: list[str], statuses: dict[str, str] | None = None, note: str = "", evidence: str = "证据",
                extra: list[str] | None = None) -> str:
    statuses = statuses or {}
    rows = [f"| id | status | severity | {evidence} |", "|---|---|---|---|"]
    rows += [f"| {i} | {statuses.get(i, 'PASS')} | MAJOR | 看过第 3 章{note} |" for i in ids] + (extra or [])
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
            {"schema": 5, "status": "complete", "rounds": [{"round": 1, "gates": []}]}), encoding="utf-8")
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

    def put_report(self, text: str, reports: Path | None = None) -> Path:
        reports = reports or self.reports
        reports.mkdir(parents=True, exist_ok=True)
        rel = (reports / f"verifier.report.{SUBJECT}.md").relative_to(self.root).as_posix()
        (reports / "summary.json").write_text(json.dumps(
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
        self.assertIn(f"判据 {ids[0]} 缺行", self.gate())


class TheReportIsCheckedReadOnly(ClosureCase):
    def test_a_malformed_reply_is_reported_every_run_and_not_counted(self) -> None:
        target = self.put_report("审查员说：都看过了，没问题。\n")
        for _ in range(2):
            out = self.gate()
            for needle in ("终态块不是恰好一个", "没有表头为"):
                self.assertIn(needle, out, "第二次运行问题消失了，或没有一次报全")
        self.assertTrue(target.exists(), "门禁动了报告文件")

    def test_a_full_resubmission_after_a_missing_check_is_accepted(self) -> None:
        """缺判据的回复不登记；重投完整回复之后不再报报告问题。"""
        ids = self.overlay_ids()
        target = self.put_report(report_text(ids[1:]))
        self.assertIn(f"判据 {ids[0]} 缺行", self.gate())
        target.write_text(report_text(ids), encoding="utf-8")
        self.assertNotIn("不合合同的报告", self.gate())

    def test_a_new_reply_from_a_real_rereview_is_not_refused_as_a_second_copy(self) -> None:
        """重新派审拿回的新报告照常核，不因「同一对象已有过一份」被拒；门禁只读，不留结论账本。"""
        ids = self.overlay_ids()
        target = self.put_report(report_text(ids))
        first = self.gate()
        target.write_text(report_text(ids, note="，重新派审后的回复"), encoding="utf-8")
        second = self.gate()
        for out in (first, second):
            for needle in ("不合合同的报告", "合规结论"):
                self.assertNotIn(needle, out)
        self.assertEqual([], sorted(p.name for p in self.reports.glob("*.conclusions.json")), "门禁写了结论账本")


DIRECT = """
import { pathToFileURL } from 'node:url';
const [ext, root, phase, ...features] = process.argv.slice(2);
const report = await import(pathToFileURL(`${ext}/hooks/shared/verifier-report.mjs`).href);
const access = await import(pathToFileURL(`${ext}/hooks/shared/framework-access.mjs`).href);
const out = {};
for (const f of features) out[f] = { dir: access.phaseReportsDir(root, f, phase), problems: report.reportProblems(root, f, phase) };
process.stdout.write(JSON.stringify(out));
"""


class TheNativeReportDirectoryIsRead(ClosureCase):
    """报告位置取原生 featurePhaseReportsDir：配置的目录、施工单位的目录都按原生解析；解析失败与坏 summary 不当作未派审。"""

    def direct(self, *features: str) -> dict:
        (self.root / "direct.mjs").write_text(DIRECT, encoding="utf-8")
        proc = subprocess.run(["node", str(self.root / "direct.mjs"), str(self.root / "doc" / "extensions"), str(self.root),
                               "spec", *features], capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr[-800:])
        return json.loads(proc.stdout)

    def test_a_configured_pattern_is_where_the_report_is_read(self) -> None:
        (self.root / "framework.config.json").write_text(json.dumps(
            {"paths": {"reports_dir_pattern": "doc/reviews/<feature>/<phase>"}}), encoding="utf-8")
        ids = self.overlay_ids()
        self.put_report(report_text(ids[1:]))
        self.assertNotIn("缺行", self.gate(), "默认目录里的报告被当成了本阶段报告")
        custom = self.root / "doc" / "reviews" / FEATURE / "spec"
        kept = self.put_report(report_text(ids[1:]), custom).read_bytes()
        self.assertIn(f"判据 {ids[0]} 缺行", self.gate(), "配置目录里的不完整报告被放过")
        self.assertEqual(kept, (custom / f"verifier.report.{SUBJECT}.md").read_bytes(), "核对改了报告")

    def test_same_named_units_of_two_blueprints_read_their_own_reports(self) -> None:
        encode = subprocess.run(["node", "-e", "const f=require(process.argv[1]);"
                                 "process.stdout.write(JSON.stringify([f.encodeCuFeatureId('bp-alpha','cu-share'),"
                                 "f.encodeCuFeatureId('bp-beta','cu-share')]))",
                                 str(self.root / "framework" / "harness" / "scripts" / "utils" / "feature-identity.js")],
                                capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(0, encode.returncode, encode.stderr)
        alpha, beta = json.loads(encode.stdout)
        before = self.direct(alpha, beta)
        dirs = {f: Path(before[f]["dir"]["dir"]) for f in (alpha, beta)}
        self.assertNotEqual(dirs[alpha], dirs[beta])
        self.assertEqual([[], []], [before[alpha]["problems"], before[beta]["problems"]], "没有 summary 也报了问题")
        ids = self.overlay_ids()
        self.put_report(report_text(ids[1:]), dirs[alpha])
        after = self.direct(alpha, beta)
        self.assertIn(f"判据 {ids[0]} 缺行", " ".join(after[alpha]["problems"]))
        self.assertEqual([], after[beta]["problems"], "另一份蓝图的同名单位读到了别人的报告")

    def test_a_bad_identity_or_summary_fails_and_a_missing_summary_waits(self) -> None:
        bad = self.direct("cu-***")["cu-***"]
        self.assertIn("error", bad["dir"])
        self.assertIn("报告目录按原生配置解析失败", " ".join(bad["problems"]))
        waiting = self.gate()
        for needle in ("在但读不出", "解析失败", "不合合同的报告"):
            self.assertNotIn(needle, waiting, "没有 summary 时报了审查报告问题")
        self.reports.mkdir(parents=True, exist_ok=True)
        (self.reports / "summary.json").write_text("{", encoding="utf-8")
        self.assertIn("在但读不出或不是 JSON 对象", self.gate())


class TheSummaryTableIsChecked(ClosureCase):
    """四格汇总表逐判据核：缺行、重复、非法取值、缺列、空证据分别拒绝；顺序、Framework 自有判据与两种合法表头不影响。"""

    def test_each_structure_fault_is_refused_and_the_file_is_kept(self) -> None:
        ids = self.overlay_ids()
        good = report_text(ids)
        first = f"| {ids[0]} | PASS | MAJOR | 看过第 3 章 |"
        faults = {
            "重复": (good.replace(first, first + "\n" + first), f"判据 {ids[0]} 有 2 行"),
            "非法状态": (good.replace(first, f"| {ids[0]} | OK | MAJOR | 看过第 3 章 |"), "status「OK」"),
            "非法严重性": (good.replace(first, f"| {ids[0]} | PASS | INFO | 看过第 3 章 |"), "severity「INFO」"),
            "缺列": (good.replace(first, f"| {ids[0]} | PASS | MAJOR |"), "有 3 格"),
            "空证据": (good.replace(first, f"| {ids[0]} | SKIP | MAJOR |  |"), "证据为空"),
        }
        for label, (text, needle) in faults.items():
            with self.subTest(fault=label):
                target = self.put_report(text)
                kept = target.read_bytes()
                self.assertIn(needle, self.gate())
                self.assertEqual(kept, target.read_bytes(), "核对改了报告")

    def test_order_framework_rows_and_both_headers_pass(self) -> None:
        ids = list(reversed(self.overlay_ids()))
        for evidence in ("证据", LONG_EVIDENCE):
            with self.subTest(header=evidence):
                self.put_report("正文先提一句 " + ids[0] + "。\n\n"
                                + report_text(ids, evidence=evidence, extra=["| framework_own_check | PASS | BLOCKER | 原生核 |"]))
                self.assertNotIn("不合合同的报告", self.gate())

    def test_the_request_states_the_same_structure(self) -> None:
        request = self.gate(phase="pre")
        for needle in ("PASS / WARN / FAIL / SKIP", "BLOCKER / MAJOR / MINOR", "PASS 的核验方法写进报告说明"):
            self.assertIn(needle, request)
        self.assertNotIn("各追加一条", request, "仍要求为 PASS 的知识判据另列明细")


class EveryWarnHasADisposition(ClosureCase):
    def test_a_warn_row_needs_a_line_in_the_notes(self) -> None:
        ids = self.overlay_ids()
        self.put_report(report_text(ids, {ids[0]: "WARN"}))
        out = self.gate()
        self.assertIn(f"spec/notes.md：审查结论 {ids[0]}（WARN）没有处置记录", out)
        # 门禁报错只说在哪、什么问题、机制（10 §3.3）：没有统一开头，也不追加与这条无关的处置尾巴
        self.assertNotIn("补齐 spec 宿主扩展章节", out)
        self.assertNotIn("先读 ", out)
        (self.fr / "spec" / "notes.md").write_text(
            f"# notes\n\n- {ids[0]}：只改表达，已按闭环表重验。\n", encoding="utf-8")
        self.assertNotIn(f"{ids[0]}（WARN）", self.gate())


class TheAcceptanceIdsLineUp(ClosureCase):
    def edit_spec(self, old: str, new: str) -> None:
        text = self.spec().read_text(encoding="utf-8")
        self.assertIn(old, text, "夹具变了，用例要跟着改")
        self.spec().write_text(text.replace(old, new, 1), encoding="utf-8")

    def test_aligned_ids_raise_nothing(self) -> None:
        """实跑夹具经 spec 门禁：「验收标准」与 acceptance.yaml 的编号一致性不报。"""
        out = self.gate()
        for needle in ("在 acceptance.yaml 里没有", "关联功能两处不一致", "同号不同义"):
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


if __name__ == "__main__":
    unittest.main()
