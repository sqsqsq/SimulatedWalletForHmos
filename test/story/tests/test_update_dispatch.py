"""update 改过的阶段要按新的审查对象审一次 —— 这一组锁住**错路**。

派审本身是模型的动作，测不了；能测的是它据以判断的那几条确定性事实，
而每一条判错的方向都一样危险：**表面闭环、实际没审**。

  ① 当前 subject 有 PASS 报告 → 这一轮真的审过了；
  ② 当前 subject 没有报告、历史有 PASS → 框架沿用历史，标 `completed_with_prior_review`——
     update 必须认出这一条不是「已审」；
  ③ 报告写在了当前路径但里面是旧 subject → `subject_mismatch`，不许退回沿用历史；
  ④ 当前 subject 判 FAIL → 就是 FAIL，历史的 PASS 盖不住它；
  ⑤ 报告只写在旧 subject 的路径上（投错了）→ 当前仍算缺报告，照样退回沿用历史。
     **这正是「拿错请求」的后果**：两个文件名都带 subject 哈希，拿错一个就走到这条路上。

用的是 framework 自己那份证据读取与闭环派生（`utils/verifier-evidence.ts`），
不是我们仿写的一份——仿写的话，框架换了判据这组测试还会绿。
夹具是隔离的临时目录，不碰主仓的任何 feature。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HARNESS = REPO_ROOT / "framework" / "harness"
EVIDENCE = HARNESS / "scripts" / "utils" / "verifier-evidence.ts"

FEATURE = "AR90009"
PHASE = "spec"
CURRENT = "c" * 64
PRIOR = "b" * 64

#: 在隔离夹具上跑框架那份证据读取，回答「这一轮到底审没审」。
DRIVER = r"""
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const tsNode = require.resolve('ts-node/dist/bin.js', { paths: [process.argv[2]] });
require(path.join(path.dirname(tsNode), '..', '..', 'ts-node')).register({
  transpileOnly: true, compilerOptions: { module: 'commonjs' },
});
const mod = require(process.argv[3]);
const [root, feature, phase] = process.argv.slice(4);
const loaded = mod.loadVerifierEvidence(root, feature, phase, { frameworkRoot: process.argv[2] });
const closure = mod.deriveVerifierClosureRecord(root, feature, phase, process.argv[2]);
console.log(JSON.stringify({
  ok: loaded.ok === true,
  code: loaded.code ?? null,
  verdict: loaded.evidence ? loaded.evidence.verdict : null,
  closureMode: closure ? closure.mode : null,
}));
"""


def report(subject: str, verdict: str) -> str:
    """verifier 报告的最小形态：框架认的是那对终态块标记里的三个字段。

    形状取自 `framework/harness/scripts/utils/verifier-subject.ts::parseResultBlock`——
    照它写，不自己另编一份；编的话这一组测的就是我们仿写的解析器，框架改了判据也照绿。
    """
    return ("# 审查报告\n\n<!-- maison-verifier-result:v1 -->\n"
            f"verifier_subject_id: {subject}\n"
            f"verdict: {verdict}\n"
            f"blocker_count: {0 if verdict == 'PASS' else 1}\n"
            "<!-- /maison-verifier-result:v1 -->\n")


class VerifierEvidenceCase(unittest.TestCase):
    """每个用例一份隔离夹具：这一组只读框架代码，不碰主仓的 feature。"""

    @classmethod
    def setUpClass(cls) -> None:
        if not EVIDENCE.is_file():
            raise unittest.SkipTest(f"没有 {EVIDENCE}，这一组只在装了 framework 的工作区跑")

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.reports = self.root / "doc" / "features" / FEATURE / PHASE / "reports"
        self.reports.mkdir(parents=True)
        self.driver = self.root / "driver.cjs"
        self.driver.write_text(DRIVER, encoding="utf-8")

    def summary(self, subject: str | None) -> None:
        body: dict = {"phase": PHASE, "feature": FEATURE}
        if subject:
            body["verifier_subject_id"] = subject
            body["verifier_report"] = (
                f"doc/features/{FEATURE}/{PHASE}/reports/verifier.report.{subject}.md")
        (self.reports / "summary.json").write_text(json.dumps(body), encoding="utf-8")

    def write_report(self, at_subject: str, says_subject: str, verdict: str) -> None:
        """报告落在 `at_subject` 的文件名下，内容里写的是 `says_subject`——两者可以不一致。"""
        (self.reports / f"verifier.report.{at_subject}.md").write_text(
            report(says_subject, verdict), encoding="utf-8")

    def ask(self) -> dict:
        proc = subprocess.run(
            ["node", str(self.driver), str(HARNESS), str(EVIDENCE), str(self.root), FEATURE, PHASE],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        rows = [l for l in proc.stdout.splitlines() if l.strip().startswith("{")]
        if not rows:
            raise unittest.SkipTest(f"起不来框架那份证据读取：{proc.stderr[-400:]}")
        return json.loads(rows[-1])


class WhatCountsAsReviewedThisRound(VerifierEvidenceCase):
    def test_a_pass_on_the_current_subject_is_a_real_review(self) -> None:
        self.summary(CURRENT)
        self.write_report(CURRENT, CURRENT, "PASS")
        got = self.ask()
        self.assertTrue(got["ok"], got)
        self.assertEqual("PASS", got["verdict"])
        self.assertIsNone(got["closureMode"], "当前有有效报告，不该派生成沿用历史")

    def test_no_current_report_falls_back_to_history_and_says_so(self) -> None:
        """这一条是 update 最该认出来的：闭环成立，但**这一轮的材料没人审过**。"""
        self.summary(CURRENT)
        self.write_report(PRIOR, PRIOR, "PASS")
        got = self.ask()
        self.assertFalse(got["ok"])
        self.assertEqual("report_missing", got["code"])
        self.assertEqual("completed_with_prior_review", got["closureMode"])

    def test_a_report_naming_another_subject_is_not_accepted(self) -> None:
        """报告写在当前路径、内容却是旧 subject：不认，也不退回沿用历史。"""
        self.summary(CURRENT)
        self.write_report(CURRENT, PRIOR, "PASS")
        got = self.ask()
        self.assertFalse(got["ok"])
        self.assertEqual("subject_mismatch", got["code"])
        self.assertIsNone(got["closureMode"], "对不上的报告不该被算成沿用历史")

    def test_a_current_fail_is_not_covered_by_an_old_pass(self) -> None:
        self.summary(CURRENT)
        self.write_report(CURRENT, CURRENT, "FAIL")
        self.write_report(PRIOR, PRIOR, "PASS")
        got = self.ask()
        self.assertEqual("FAIL", got["verdict"], got)

    def test_posting_to_the_old_path_leaves_this_round_unreviewed(self) -> None:
        """**拿错请求的后果**：回复写到了旧 subject 的路径上，当前这一轮仍然没人审。

        两个文件名都带 subject 哈希，看起来只差几个字符；走到这里时退出码照样是 0，
        闭环也成立——所以 update 不能只看退出码，要核当前 subject 的报告在不在。
        """
        self.summary(CURRENT)
        self.write_report(PRIOR, PRIOR, "PASS")
        self.write_report(PRIOR, CURRENT, "PASS")   # 内容对、位置错
        got = self.ask()
        self.assertFalse(got["ok"], "投错位置却被当成审过了")
        self.assertEqual("report_missing", got["code"])

    def test_no_subject_means_no_request_was_issued(self) -> None:
        """本宿主没启用 verifier、或这一轮没生成请求：如实说没有，不许当成审过。"""
        self.summary(None)
        got = self.ask()
        self.assertFalse(got["ok"])
        self.assertEqual("subject_absent", got["code"])
        self.assertIsNone(got["closureMode"])


class TheMethodPageSaysHowToGetItRight(unittest.TestCase):
    """方法页要把上面这几条错路写给模型——判据在框架那边，做对与否在提示这边。"""

    def test_it_names_the_wrong_paths(self) -> None:
        page = (REPO_ROOT / "doc" / "extensions" / "skills" / "story" / "phases"
                / "update.md").read_text(encoding="utf-8")
        for needle in ("verifier_request", "原样全文", "sync-closure",
                       "semantic_not_reverified", "report_missing", "不要自己拼 subject"):
            self.assertIn(needle, page, f"方法页没说「{needle}」")
        self.assertIn("没有完成独立审查", page, "没说宿主没有审查员时该如实报告")
