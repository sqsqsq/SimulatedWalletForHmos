# -*- coding: utf-8 -*-
"""verifier 报告协议：两种落盘方式并存，按宿主能力分流。

谁写这份报告，取决于宿主 adapter 声明的 ``verifier_capability``：

- 声明了 ``publisher: subagent_stop`` 的（claude / codeagent）：报告不由 verifier
  自己写，SubagentStop 钩子从子 agent 的**终态消息**生成，按 subject 分区落盘
  ``verifier.report.<64位subject>.json``；
- **没声明的（opencode / codex / generic）**：那个宿主没有这个钩子，框架也不为它
  生成 request，报告由执行方自己写成文件（历史上四种文件名）。

两个断点，方向相反，这一份两边都锚：

1. 升级后扩展只按旧文件名找报告 → 带 hash 的 JSON 一种都不匹配 → 判「报告缺失」
   → 有钩子的宿主上 spec 闭环第三步必卡；
2. 反过来只认 JSON → 没有钩子的那半边宿主上，裁决核对被整条砍断，而那恰恰是
   当前被测宿主（opencode）。

所以两种都认**不是双轨**：同一个宿主上只有一种协议在产出。认少了就是在某半边
宿主上失明，而判据要服务的是所有宿主，不是当前这台机器上跑的那一个。
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
MODULE = REPO / "doc" / "extensions" / "hooks" / "shared" / "verifier-report.mjs"

SUBJECT = "a" * 64
OTHER_SUBJECT = "b" * 64

SPEC_MD = """# 甲需求规格

## 10. 规约约束要求

| 编号 | 本需求的要求 | 落点契约名 |
|---|---|---|
| UX-01 | 弹窗方向性参数只用 start/end | OrderSheet |
| OBS-01 | 六步骤每步进入与结果都记日志 | OrderFlowLogger |
"""

# 引文须是目标产物里连续 12 字以上的原话，所以裁决表直接抄 spec 的原句。
FULL_TABLE = """结论如下。

| 编号 | 裁决 | 证据 |
|---|---|---|
| UX-01 | PASS | 弹窗方向性参数只用 start/end |
| OBS-01 | PASS | 六步骤每步进入与结果都记日志 |

verifier_subject_id: %s
verdict: PASS
""" % SUBJECT

PARTIAL_TABLE = """结论如下。

| 编号 | 裁决 | 证据 |
|---|---|---|
| UX-01 | PASS | 弹窗方向性参数只用 start/end |
"""

DRIVER = """
const [, , modulePath, projectRoot, feature, phase, specPath] = process.argv;
const mod = await import(modulePath);
const out = mod.adjudicationProblems(
  { projectRoot, feature, phase }, null, [specPath],
);
process.stdout.write(JSON.stringify(out));
"""


class VerifierReportProtocol(unittest.TestCase):
    def _run(self, *, reports: dict) -> dict:
        """建一个最小工程，按 reports 落盘报告文件，跑 adjudicationProblems。

        reports 的键是文件名（协议换没换全看它），值是文件内容。
        """
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            spec_dir = root / "doc" / "features" / "SMPFEAT" / "spec"
            (spec_dir / "reports").mkdir(parents=True)
            spec = spec_dir / "spec.md"
            spec.write_text(SPEC_MD, encoding="utf-8")
            for name, body in reports.items():
                (spec_dir / "reports" / name).write_text(body, encoding="utf-8")

            driver = root / "driver.mjs"
            driver.write_text(DRIVER, encoding="utf-8")
            r = subprocess.run(
                ["node", str(driver), MODULE.as_uri(), str(root),
                 "SMPFEAT", "spec", str(spec)],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(r.returncode, 0, f"driver 挂了：{r.stderr[:600]}")
            return json.loads(r.stdout)

    @staticmethod
    def _json_report(text: str, subject: str = SUBJECT) -> dict:
        return {f"verifier.report.{subject}.json": json.dumps(
            {"schema_version": 1, "state": "published", "feature": "SMPFEAT",
             "phase": "spec", "subject_id": subject, "verdict": "PASS",
             "blocker_count": 0, "report_text": text},
            ensure_ascii=False)}

    def test_new_format_is_recognised_and_passes_when_fully_adjudicated(self):
        out = self._run(reports=self._json_report(FULL_TABLE))
        self.assertEqual("PASS", out["status"], f"新格式没被认出来：{out}")
        self.assertEqual([], out["problems"])

    def test_new_format_missing_row_fails_rather_than_reads_as_not_run(self):
        out = self._run(reports=self._json_report(PARTIAL_TABLE))
        self.assertEqual("FAIL", out["status"], f"漏裁没被报出来：{out}")
        self.assertTrue(any("OBS-01" in p for p in out["problems"]),
                        f"没点名漏掉的那一行：{out['problems']}")

    def test_self_written_reports_are_recognised_too(self):
        """执行方自己写的报告也得认——那不是旧协议，是另一半宿主的现协议。

        谁写这份报告取决于宿主 adapter 的 `verifier_capability`：声明了
        `publisher: subagent_stop` 的（claude / codeagent）由钩子从终态消息生成
        JSON；**没声明的（opencode / codex / generic）根本没有那个钩子**，框架也不
        为它生成 request，报告由执行方自己落成文件。

        所以这不是双轨——同一个宿主上只有一种协议在产出。只认 JSON 会在没有钩子的
        那半边宿主上把裁决核对整条砍断，而那恰恰是当前被测宿主。
        """
        for name in ("verifier.report.md", "verifier-spec.md",
                     "verify-spec.md", "verifier-spec-result.yaml"):
            with self.subTest(name=name):
                out = self._run(reports={name: FULL_TABLE})
                self.assertEqual("PASS", out["status"],
                                 f"{name} 没被当报告读——没有钩子的宿主就核不了裁决：{out}")

    def test_a_self_written_report_missing_a_row_still_fails(self):
        """认它，不等于放宽它：自己写的报告漏裁一样判 FAIL。"""
        out = self._run(reports={"verifier.report.md": PARTIAL_TABLE})
        self.assertEqual("FAIL", out["status"], f"漏裁没被报出来：{out}")
        self.assertTrue(any("OBS-01" in p for p in out["problems"]), out["problems"])

    def test_all_subjects_are_collected(self):
        """一个阶段可能有多份 subject 报告，得全收集合并判。

        少收一份就可能把「裁过了」判成「没裁」：换代/并发时两条裁决本就分在两份文件里。
        """
        reports = {}
        reports.update(self._json_report(
            "| UX-01 | PASS | 弹窗方向性参数只用 start/end |", SUBJECT))
        reports.update(self._json_report(
            "| OBS-01 | PASS | 六步骤每步进入与结果都记日志 |", OTHER_SUBJECT))
        out = self._run(reports=reports)
        self.assertEqual("PASS", out["status"],
                         f"两份 subject 报告没被合起来判：{out}")

    def test_unreadable_report_is_not_disguised_as_not_run(self):
        """文件在却读不出正文 → 报「报告坏了」，不能说成「verifier 还没跑」。

        两者的处置完全不同：一个要去查报告，一个是等 verifier 执行。混成一句，
        协议再变一次时又会静默判 NOT_APPLICABLE，跟这次的断点一模一样。
        """
        out = self._run(reports={f"verifier.report.{SUBJECT}.json": "{ 不是 json"})
        self.assertEqual("FAIL", out["status"], f"坏报告被当成没跑：{out}")
        self.assertTrue(any("读不出结论正文" in p for p in out["problems"]),
                        out["problems"])

    def test_missing_report_text_field_is_reported_too(self):
        body = json.dumps({"subject_id": SUBJECT, "verdict": "PASS"}, ensure_ascii=False)
        out = self._run(reports={f"verifier.report.{SUBJECT}.json": body})
        self.assertEqual("FAIL", out["status"], f"没有正文字段却放行了：{out}")


if __name__ == "__main__":
    unittest.main()
