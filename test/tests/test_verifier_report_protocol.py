"""读者审查的报告读得出来吗、交付门拦不拦得住 —— 审了没有、写成形态没有。

**逐行裁决的核对早已退场**：那条路径要求 verifier 把每条判定写成一行、每行附一段够长的
引文，门禁再逐行核键与引文。它逼出的是把清单里的字抄进证据列的回声，而不是判断。
留下的是两件仍然确定的事：

  ① 报告在哪、读不读得出来（落点由 harness 写在 `summary.verifier_report`）；
  ② 读者审查那一项在汇总表里有没有一行、证据空不空、非 PASS 时两类结论齐不齐。

报几条、报得对不对由人抽查，门禁判不了。

## 报告是调用方写的

派 verifier 的那个 agent 把子代理的回复**原样全文**写到 `summary.verifier_report`
指向的路径。身份归框架：文件在不在、终态块回显的 subject 对不对、verdict 与
blocker 数一致不一致，都是 `check-receipt` 的判断，扩展不重复核。

## 交付门这一份测到哪儿

`check --deliver` 先跑 `check-receipt`，通过之后才核报告形态。这里测的是**接线**
（普通 check 不碰它；框架不在时如实报「跑不了」而不是当通过）与**报告形态判据本身**。
「回执真的绿了之后交付门放行」要一次真实闭环才有对象，那是 CLI 实跑的判据。

## 送达与任务定义，比结果块更早的两道

判据没进 verifier 的任务清单，或者任务里没有一条问「材料登记的每张图用了没有」，
落盘那一步就没有对象。这两道也在这一份里锚住。
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from ext_workspace import link_harness_yaml, DEV_EXT

REPO = Path(__file__).resolve().parents[2]
MODULE = DEV_EXT / "hooks" / "shared" / "verifier-report.mjs"
STORY_BUILD = DEV_EXT / "skills/story/scripts/core/story-build.mjs"
CONTRACT = DEV_EXT / "skills/story/contracts/story-chapters.json"
FEATURE = "RT90001"

SUBJECT = "a" * 64
REPORT_REL = f"doc/features/SMPFEAT/spec/reports/verifier.report.{SUBJECT}.md"

STORY_MD = """# 甲需求（SMPFEAT）

## 背景

用户现在拿不到凭据。
"""

DRIVER = """
const [, , modulePath, projectRoot, feature, phase] = process.argv;
const mod = await import(modulePath);
process.stdout.write(JSON.stringify(mod.storyReviewProblems(projectRoot, feature, phase)));
"""

# 汇总表：每项一行，PASS 也列，最后一格是一行证据。
def row(status: str, evidence: str = "逐章过了背景、范围、流程、异常、验收") -> str:
    return (
        "| id | status | severity | 证据 |\n"
        "|---|---|---|---|\n"
        "| acceptance_testable | PASS | BLOCKER | §8 每条都可判 |\n"
        f"| story_reader_review | {status} | BLOCKER | {evidence} |\n"
    )


DETAILS = """
```yaml
verification_result:
  checks:
    - id: story_reader_review
      status: FAIL
      details:
        blocking_findings:
          - 第 5 章说未实名可下单，第 8 章验收里没有这个入口
        advisories: []
```
"""

DETAILS_MISSING_ADVISORIES = DETAILS.replace("        advisories: []\n", "")

PER_UNIT_TABLE = """
| 单元键 | 裁决 | 引文 |
|---|---|---|
| PRD:7:2c7fc380 | 讲清 | 用户现在拿不到凭据 |
"""


class TheReportIsReadAtItsDeclaredLanding(unittest.TestCase):
    """报告的落点只有一个来源：harness 写的 `summary.verifier_report`。"""

    def _run(self, *, summary, report: str | None,
             extra: dict[str, str] | None = None) -> dict:
        """summary=None 表示 harness 还没跑过；extra 是报告目录里另放的文件。"""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            reports = root / "doc" / "features" / "SMPFEAT" / "spec" / "reports"
            reports.mkdir(parents=True)
            (root / "doc/features/SMPFEAT/AR").mkdir(parents=True)
            (root / "doc/features/SMPFEAT/AR/story.md").write_text(STORY_MD, encoding="utf-8")
            if summary is not None:
                (reports / "summary.json").write_text(
                    json.dumps(summary, ensure_ascii=False), encoding="utf-8")
            if report is not None:
                (root / REPORT_REL).write_text(report, encoding="utf-8")
            for name, text in (extra or {}).items():
                (reports / name).write_text(text, encoding="utf-8")

            driver = root / "driver.mjs"
            driver.write_text(DRIVER, encoding="utf-8")
            r = subprocess.run(
                ["node", str(driver), MODULE.as_uri(), str(root), "SMPFEAT", "spec"],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(r.returncode, 0, f"driver 挂了：{r.stderr[:600]}")
            return json.loads(r.stdout)

    def run_with(self, report: str | None) -> dict:
        return self._run(summary={"verifier_report": REPORT_REL}, report=report)

    def test_before_harness_runs_it_is_not_applicable(self) -> None:
        """没有 summary = harness 还没跑——那不是通过，是还轮不到判。"""
        out = self._run(summary=None, report=None)
        self.assertEqual("NOT_APPLICABLE", out["status"])
        self.assertEqual([], out["problems"])

    def test_a_host_without_a_reviewer_is_not_applicable(self) -> None:
        """脚本 PASS 而审查字段全都没有 = 本宿主未启用 verifier：如实披露，不当缺件。"""
        out = self._run(summary={"phase": "spec", "verdict": "PASS"}, report=None)
        self.assertEqual("NOT_APPLICABLE", out["status"])
        self.assertIn("未启用 verifier", out["detail"])

    def test_a_failed_script_round_is_not_a_host_without_a_reviewer(self) -> None:
        """脚本没过时 harness 不派审：字段同样全缺，但推不出宿主没有审查员。"""
        for summary in ({"phase": "spec", "verdict": "FAIL", "blocker_count": 1, "closure_status": "open"},
                        {"phase": "spec"}):
            with self.subTest(summary=summary):
                out = self._run(summary=summary, report=None)
                self.assertEqual("FAIL", out["status"])
                self.assertIn("还轮不到审查", out["problems"][0])
                self.assertNotIn("未启用", out["problems"][0])

    def test_a_summary_missing_only_the_landing_is_incomplete(self) -> None:
        """有审查对象或请求而没有落点：summary 不完整，推不出宿主没有审查员。"""
        for summary in ({"verifier_subject_id": "a" * 16},
                        {"verifier_request": "doc/features/SMPFEAT/spec/reports/verifier.request.json"}):
            with self.subTest(summary=summary):
                out = self._run(summary=summary, report=None)
                self.assertEqual("FAIL", out["status"])
                self.assertIn("summary 不完整", out["problems"][0])
                self.assertNotIn("未启用", out["problems"][0])

    def test_a_declared_landing_with_no_file_fails(self) -> None:
        """落点写了、文件不在：推不出回复存在——报错说清落点只认对当前请求的原样全文回复。"""
        out = self.run_with(None)
        self.assertEqual("FAIL", out["status"])
        said = out["problems"][0]
        self.assertIn("当前审查对象还没有报告", said)
        self.assertIn("落点只认 verifier 对当前请求", said)
        self.assertIn("当前审查只认对当前请求的原样回复", said)

    def test_a_prior_review_closure_says_the_current_object_was_not_reviewed(self) -> None:
        """沿用历史审查收口时，照 summary 说出当前对象没有独立审查、沿用的是谁，不当成通过。"""
        out = self._run(summary={
            "verifier_report": REPORT_REL, "verifier_subject_id": SUBJECT,
            "verifier_request": f"doc/features/SMPFEAT/spec/reports/verifier.request.{SUBJECT}.json",
            "verifier_closure": {"mode": "completed_with_prior_review", "reviewed_subject_id": "b" * 64,
                                 "current_subject_id": SUBJECT,
                                 "current_material_not_reverified": ["lifecycle_hook_fragments"]},
        }, report=None)
        self.assertEqual("FAIL", out["status"])
        self.assertIn("当前对象未独立审查", out["detail"])
        said = out["problems"][0]
        self.assertIn("按 completed_with_prior_review 收口", said)
        self.assertIn("没有独立审查，沿用的是 bbbbbbbbbbbb", said)
        self.assertIn("lifecycle_hook_fragments", said)
        self.assertIn(f"verifier.request.{SUBJECT}.json", said)



class ACorrectionMayCarryTheReviewedPass(TheReportIsReadAtItsDeclaredLanding):
    """当前对象没有报告时的分流：只有修正重验、且沿用的历史报告就是那个对象的有效 PASS，
    才按沿用交付，并留一笔「当前材料未独立重审」；其余都按未完成报。
    update 里改了业务的阶段由 `update --action close` 核当前报告，交付门不再按「update 开着」一律拦。"""

    PRIOR = "b" * 64

    def summary(self, signals=("script_revalidated",)) -> dict:
        return {"verifier_report": REPORT_REL, "verifier_subject_id": SUBJECT, "verdict": "PASS",
                "closure_status": "closed", "readiness_signals": [{"id": s} for s in signals],
                "verifier_closure": {"mode": "completed_with_prior_review", "reviewed_subject_id": self.PRIOR,
                                     "current_subject_id": SUBJECT,
                                     "current_material_not_reverified": ["lifecycle_hook_fragments"]}}

    def history(self, subject: str | None = None, verdict: str = "PASS", row: str = "PASS") -> dict[str, str]:
        return {f"verifier.report.{self.PRIOR}.md": row_text(row) + "\n<!-- maison-verifier-result:v1 -->\n"
                f"verifier_subject_id: {subject or self.PRIOR}\nverdict: {verdict}\nblocker_count: 0\n"
                "<!-- /maison-verifier-result:v1 -->\n"}

    def test_a_correction_with_a_valid_reviewed_pass_is_carried_with_a_note(self) -> None:
        out = self._run(summary=self.summary(), report=None, extra=self.history())
        self.assertEqual("PASS", out["reviewVerdict"])
        self.assertIn("当前材料未独立重审", out["notes"][0])
        self.assertIn("lifecycle_hook_fragments", out["notes"][0])

    def test_a_missing_or_failed_history_is_not_carried(self) -> None:
        for name, extra in (("缺席", {}), ("FAIL", self.history(verdict="FAIL")),
                            ("对象不符", self.history(subject="c" * 64)), ("读者审查未过", self.history(row="FAIL"))):
            with self.subTest(name):
                out = self._run(summary=self.summary(), report=None, extra=extra)
                self.assertEqual("FAIL", out["status"])
                self.assertEqual("沿用的历史审查无效", out["detail"])

    def test_without_the_revalidate_mark_it_cannot_be_confirmed(self) -> None:
        out = self._run(summary=self.summary(signals=()), report=None, extra=self.history())
        self.assertEqual("FAIL", out["status"])
        self.assertEqual("当前对象未独立审查", out["detail"])

    def test_the_update_state_does_not_decide_the_carry(self) -> None:
        """交付门不读流程契约判 update 开没开：沿用只看修正重验与历史报告。"""
        out = self._run(summary=self.summary(), report=None, extra=self.history())
        self.assertEqual("PASS", out["reviewVerdict"], out)
        self.assertIn("当前材料未独立重审", out["notes"][0])


class TheCommandTellsUnreviewedFromIncomplete(unittest.TestCase):
    """命令出口：脚本 PASS 而审查字段全缺 = 未启用，未审、退出 0；脚本没过或只缺落点 = 判不了，退出 2、不说宿主没审查员。"""

    def run_cli(self, summary: dict) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as d:
            reports = Path(d) / "doc" / "features" / "SMPFEAT" / "spec" / "reports"
            reports.mkdir(parents=True)
            (reports / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
            return subprocess.run(["node", str(MODULE), "--feature", "SMPFEAT", "--phase", "spec", "--project-root", d],
                                  capture_output=True, text=True, encoding="utf-8")

    def test_no_reviewer_fields_is_unreviewed(self) -> None:
        r = self.run_cli({"phase": "spec", "verdict": "PASS"})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("未审，不是 PASS", r.stdout)

    def test_a_failed_script_round_does_not_exit_as_unreviewed(self) -> None:
        r = self.run_cli({"phase": "spec", "verdict": "FAIL", "blocker_count": 1, "closure_status": "open"})
        self.assertEqual(2, r.returncode, r.stdout)
        self.assertIn("还轮不到审查", r.stderr)

    def test_a_subject_without_a_landing_is_incomplete(self) -> None:
        r = self.run_cli({"verifier_subject_id": SUBJECT})
        self.assertEqual(2, r.returncode, r.stdout)
        self.assertIn("summary 不完整", r.stderr)
        self.assertNotIn("未启用", r.stderr)


def row_text(status: str) -> str:
    return row(status) + ("" if status == "PASS" else DETAILS)

class TheSummaryRowIsTheConclusion(unittest.TestCase):
    """上游的输出契约：汇总表每项一行（PASS 也列），明细只列非 PASS。"""

    def _run(self, report: str) -> dict:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            reports = root / "doc" / "features" / "SMPFEAT" / "spec" / "reports"
            reports.mkdir(parents=True)
            (reports / "summary.json").write_text(
                json.dumps({"verifier_report": REPORT_REL}), encoding="utf-8")
            (root / REPORT_REL).write_text(report, encoding="utf-8")
            driver = root / "driver.mjs"
            driver.write_text(DRIVER, encoding="utf-8")
            r = subprocess.run(
                ["node", str(driver), MODULE.as_uri(), str(root), "SMPFEAT", "spec"],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(r.returncode, 0, f"driver 挂了：{r.stderr[:600]}")
            return json.loads(r.stdout)

    def test_a_pass_row_alone_is_enough(self) -> None:
        """判 PASS 的项按契约不写明细——要求它写就是给本项设例外，正常 PASS 会被拒。"""
        out = self._run(row("PASS"))
        self.assertEqual("PASS", out["status"], out)
        self.assertEqual([], out["problems"])

    def test_a_report_without_the_row_fails(self) -> None:
        out = self._run("| id | status | severity | 证据 |\n|---|---|---|---|\n"
                        "| acceptance_testable | PASS | BLOCKER | §8 每条都可判 |\n")
        self.assertEqual("FAIL", out["status"])
        self.assertIn("汇总表里没有", out["problems"][0])

    def test_an_empty_evidence_cell_fails(self) -> None:
        """空证据与没审长得一样。"""
        for empty in ("", "—"):
            with self.subTest(evidence=empty or "(空)"):
                out = self._run(row("PASS", empty))
                self.assertEqual("FAIL", out["status"], out)
                self.assertIn("证据格", out["problems"][0])

    def test_a_non_pass_row_needs_both_keys(self) -> None:
        out = self._run(row("FAIL") + DETAILS)
        self.assertEqual("PASS", out["status"], f"带两键的 FAIL 报告解析不过：{out}")

    def test_a_three_column_row_is_not_evidence(self) -> None:
        """少一列时最后一格是 severity，非空——按「取最后一格」判会把它当证据放过去。"""
        out = self._run("| id | status | severity |\n|---|---|---|\n"
                        "| story_reader_review | PASS | BLOCKER |\n")
        self.assertEqual("FAIL", out["status"], out)
        self.assertIn("少了证据列", out["problems"][0])

    def test_another_checks_keys_do_not_count_as_this_ones(self) -> None:
        """两个键要在**这一条自己**的 details 下——全文搜的话别项的键会算到它头上。"""
        borrowed = (
            "\n```yaml\n"
            "verification_result:\n"
            "  checks:\n"
            "    - id: other_check\n"
            "      status: FAIL\n"
            "      details:\n"
            "        blocking_findings: []\n"
            "        advisories: []\n"
            "    - id: story_reader_review\n"
            "      status: FAIL\n"
            "      details: |\n"
            "        第 5 章与第 8 章对不上。\n"
            "```\n")
        out = self._run(row("FAIL") + borrowed)
        self.assertEqual("FAIL", out["status"], f"借了别项的键就放行：{out}")
        self.assertIn("它自己的明细里缺", out["problems"][0])

    def test_the_fix_hint_never_asks_the_author_to_write_the_report(self) -> None:
        """读报错的是作者，而报告必须是子代理回复的原样落盘——叫他补就是叫他伪造证据。"""
        reports = {
            "缺行": "| id | status | severity | 证据 |\n|---|---|---|---|\n",
            "证据空": row("PASS", ""),
            "缺键": row("FAIL"),
        }
        for name, report in reports.items():
            with self.subTest(shape=name):
                out = self._run(report)
                self.assertEqual("FAIL", out["status"])
                self.assertIn("不要自己补", out["problems"][0])
                self.assertIn("再投给 verifier", out["problems"][0])

    def test_a_non_pass_row_missing_a_key_fails(self) -> None:
        out = self._run(row("FAIL") + DETAILS_MISSING_ADVISORIES)
        self.assertEqual("FAIL", out["status"])
        self.assertIn("advisories", out["problems"][0])

    def test_key_names_outside_the_fence_are_not_the_keys(self) -> None:
        """围栏外的附注里出现键名不算数——那是在讲这两个键，不是这一项的结论。"""
        report = row("FAIL") + (
            "\n```yaml\n"
            "verification_result:\n"
            "  checks:\n"
            "    - id: story_reader_review\n"
            "      status: FAIL\n"
            "      details: {}\n"
            "```\n"
            "\n"
            "附注：blocking_findings 与 advisories 的写法见任务书。\n")
        out = self._run(report)
        self.assertEqual("FAIL", out["status"], f"围栏外的字样被当成了键：{out}")
        self.assertIn("它自己的明细里缺", out["problems"][0])

    def test_a_prose_details_is_not_two_conclusions(self) -> None:
        """`details:` 是一段话时，里面写着「未提供 blocking_findings 和 advisories」
        恰恰说明这两类结论**没有**——子串搜却会判它有。
        """
        report = row("FAIL") + (
            "\n```yaml\n"
            "verification_result:\n"
            "  checks:\n"
            "    - id: story_reader_review\n"
            "      status: FAIL\n"
            "      details: |\n"
            "        未提供 blocking_findings 和 advisories，只写了一段说明。\n"
            "```\n")
        out = self._run(report)
        self.assertEqual("FAIL", out["status"], f"一段散文被当成了两类结论：{out}")
        self.assertIn("它自己的明细里缺", out["problems"][0])

    def test_a_details_entry_at_the_end_of_the_yaml_still_reads(self) -> None:
        """本项排在末尾、后面跟着 `summary:` 时，范围止于围栏，键照样读得出来。"""
        report = row("FAIL") + (
            "\n```yaml\n"
            "verification_result:\n"
            "  checks:\n"
            "    - id: story_reader_review\n"
            "      status: FAIL\n"
            "      details:\n"
            "        blocking_findings:\n"
            "          - 第 5 章与第 8 章对不上\n"
            "        advisories: []\n"
            "```\n")
        out = self._run(report)
        self.assertEqual("PASS", out["status"], f"正常的 FAIL 明细被拒了：{out}")

    def with_checks(self, *blocks: str) -> str:
        """一份带 YAML 结构块的报告；`blocks` 是 `checks` 下的几条，按给的顺序排。"""
        return row("FAIL") + ("\n```yaml\nverification_result:\n  checks:\n"
                              + "".join(blocks) + "```\n")

    #: 读者审查那一条，写全了两类结论。
    GOOD = ("    - id: story_reader_review\n"
            "      status: FAIL\n"
            "      details:\n"
            "        blocking_findings:\n"
            "          - 第 5 章说未实名可下单，第 8 章验收里没有这个入口\n"
            "        advisories: []\n")

    #: 别的一条，正文是块标量——真实报告里几乎每条都长这样。
    OTHER = ("    - id: visual_handoff_semantics\n"
             "      status: WARN\n"
             "      details: |\n"
             "        §4 说界面规格以产品原稿为准，而 handoff 块声明没有参考图，\n"
             "        两处对不上；authoritative_refs 是空数组。\n"
             "      suggestion: |\n"
             "        把参考图填进 authoritative_refs，或说明为什么维持降级。\n")

    def test_it_reads_wherever_this_item_sits(self) -> None:
        """排最前、夹在中间、排最后都读得到——位置不该改变结论。

        此前是切片读：从这一条划到下一条或围栏结束。**别的条目里的块标量会把范围搅乱**，
        于是同一份报告换个顺序就判出不同结果，而作者写的是合法 YAML。
        """
        for name, report in (
            ("排最前", self.with_checks(self.GOOD, self.OTHER)),
            ("夹中间", self.with_checks(self.OTHER, self.GOOD, self.OTHER)),
            ("排最后", self.with_checks(self.OTHER, self.GOOD)),
        ):
            with self.subTest(位置=name):
                out = self._run(report)
                self.assertEqual("PASS", out["status"], f"{name}时读不出来：{out}")

    def test_a_block_scalar_in_this_item_does_not_hide_its_keys(self) -> None:
        """本条自己也有块标量字段时，两个键照样读得出来。"""
        item = self.GOOD.replace(
            "        advisories: []\n",
            "        advisories: []\n      suggestion: |\n        先补第 8 章那条验收。\n")
        out = self._run(self.with_checks(self.OTHER, item))
        self.assertEqual("PASS", out["status"], out)

    def test_a_multi_line_advisory_is_still_a_list_item(self) -> None:
        """一条 advisory 写成多行就是 `- |`，那是合法 YAML。

        不认它的话，读取器的局限又一次被说成作者写错了——他会被要求重写报告。
        """
        item = ("    - id: story_reader_review\n"
                "      status: WARN\n"
                "      details:\n"
                "        blocking_findings: []\n"
                "        advisories:\n"
                "          - |\n"
                "            第 5 章说未实名可下单，\n"
                "            第 8 章验收里没有这个入口。\n"
                "          - 图 3 前面没有承接句\n")
        out = self._run(self.with_checks(self.OTHER, item))
        self.assertEqual("PASS", out["status"], f"多行 advisory 被判成读不出结构：{out}")

    def test_yaml_that_cannot_be_parsed_is_said_so(self) -> None:
        """读不出结构与「缺这两个键」是两回事。

        说成缺键的话，作者会去补两个已经写着的键，补完还报，他只能去翻这个脚本。
        """
        broken = self.with_checks(
            "    - id: story_reader_review\n"
            "      status: FAIL\n"
            "      details:\n"
            "        blocking_findings: []\n"
            "           advisories: []\n")     # 缩进对不上，整块读不出结构
        out = self._run(broken)
        self.assertEqual("FAIL", out["status"], out)
        self.assertIn("读不出来", out["problems"][0], out["problems"][0])
        self.assertNotIn("明细里缺", out["problems"][0], "读不出结构被说成了缺键")

class TheDeliveryGateIsWiredToTheFramework(unittest.TestCase):
    """交付门只在 `--deliver` 起作用，而且跑不起来不算通过。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        (self.root / "doc").mkdir(parents=True)
        shutil.copytree(DEV_EXT, self.root / "doc" / "extensions",
                        ignore=shutil.ignore_patterns("__pycache__", ".adapt-*", "node_modules"))
        link_harness_yaml(self.root)
        # 台账齐备，check 才走得到后面的判据；这一份 story 本身合不合格不是这里要判的。
        src = self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
        src.mkdir(parents=True)
        (src.parent / "story.md").write_text(STORY_MD, encoding="utf-8")
        (src / "decisions.json").write_text("[]", encoding="utf-8")
        shutil.copy2(REPO / "test/fixtures/failure-modes/R01-verdict-echo/good/doc/features"
                     "/REQ-DEMO/AR/story-src/story-template.md", src / "story-template.md")

    def check(self, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["node", str(STORY_BUILD), "check", "--feature", FEATURE,
             "--project-root", str(self.root), *extra],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)

    def test_plain_check_never_touches_the_delivery_gate(self) -> None:
        """登记前与返修中跑的是普通 check：那时读者审查还没发生，判它只会恒定不适用。"""
        out = self.check()
        self.assertNotIn("交付门", out.stdout + out.stderr,
                         "普通 check 去判了还没发生的事")

    def test_a_repo_without_the_framework_is_not_a_pass(self) -> None:
        """闭环归框架判；框架不在就判不了交付，别把「跑不了」当通过。"""
        out = self.check("--deliver")
        self.assertNotEqual(0, out.returncode)
        self.assertIn("check-receipt.ts", out.stderr,
                      f"交付门没接到框架回执上：{out.stderr[-600:]}")

    def test_the_gate_really_spawns_the_receipt(self) -> None:
        """门要真的把回执跑起来——起不来的话它「报了个跑不了」，等于没有门。

        `npx` 在 Windows 上是 `npx.cmd`，Node 18.20 / 20.12 之后拒绝不带 shell 地起 `.cmd`。
        这里放一个替身 runner：断言它被 node 起起来了、它的话被原样带出来。
        替身站的是 ts-node 的位置——要回归的是**怎么起**，不是 ts-node 本身。
        """
        self._stub_receipt(1, "替身回执：这个阶段没闭环")
        out = self.check("--deliver")
        self.assertNotEqual(0, out.returncode)
        self.assertIn("替身回执", out.stderr,
                      f"回执没被起起来，门只报了个「跑不了」：{out.stderr[-600:]}")
        self.assertNotIn("交付门跑不了", out.stderr)

    def test_a_long_receipt_diagnosis_arrives_whole_with_its_category_first(self) -> None:
        """回执的原始输出整段带回：首项与末项都在，类别与恢复入口在原始输出之前。"""
        lines = [f"第 {i} 行诊断" for i in range(1, 31)]
        self._stub_receipt(1, chr(10).join(lines))
        out = self.check("--deliver")
        both = out.stdout + out.stderr
        self.assertIn("第 1 行诊断", both, "长诊断的首项被截掉了")
        self.assertIn("第 30 行诊断", both)
        self.assertLess(both.index("spec 阶段闭环未成立"), both.index("第 1 行诊断"), "类别与恢复入口没先给")
        self.assertIn("「闭环」那张表", both)

    def test_a_missing_dependency_is_named_as_environment(self) -> None:
        harness = self.root / "framework" / "harness"
        (harness / "scripts").mkdir(parents=True, exist_ok=True)
        (harness / "scripts" / "check-receipt.ts").write_text("", encoding="utf-8")
        out = self.check("--deliver")
        self.assertIn("环境依赖缺失", out.stderr)
        self.assertIn("npm install", out.stderr)
        self.assertNotIn("产物不合格", out.stderr)

    def _stub_receipt(self, exit_code: int, say: str) -> None:
        """替身回执：站 ts-node 的位置，按给定退出码与话术回。"""
        harness = self.root / "framework" / "harness"
        (harness / "scripts").mkdir(parents=True, exist_ok=True)
        (harness / "scripts" / "check-receipt.ts").write_text("", encoding="utf-8")
        dist = harness / "node_modules" / "ts-node" / "dist"
        dist.mkdir(parents=True, exist_ok=True)
        (dist.parent / "package.json").write_text('{"name":"ts-node","version":"0.0.0"}',
                                                  encoding="utf-8")
        (dist / "bin.js").write_text(
            f"process.stderr.write({say!r});process.exit({exit_code});", encoding="utf-8")

    def test_a_host_without_a_reviewer_says_so_instead_of_passing_silently(self) -> None:
        """回执过了、本宿主没审查员——不拦，但要出声。

        静默通过的话，没经过读者审查的 story 就这么交出去了，事后没人看得出来。
        """
        self._stub_receipt(0, "回执通过")
        reports = self.root / "doc" / "features" / FEATURE / "spec" / "reports"
        reports.mkdir(parents=True)
        (reports / "summary.json").write_text(json.dumps({"phase": "spec", "verdict": "PASS"}), encoding="utf-8")

        out = self.check("--deliver")
        self.assertIn("未经读者语义审查即交付", out.stdout,
                      f"降级没出声：{out.stdout[-600:]}")

    def write_report(self, status: str) -> None:
        """把一份合规的审查回复放到落点上：本阶段全部判据的汇总表、终态块，FAIL/WARN 时两类结论写全。

        交付门先核报告形态（格式、判据全不全、处置记录），再看读者审查这一项的结论——夹具要是一份完整回复。
        """
        import yaml  # noqa: PLC0415
        reports = self.root / "doc" / "features" / FEATURE / "spec" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "summary.json").write_text(
            json.dumps({"phase": "spec", "verifier_report": REPORT_REL}),
            encoding="utf-8")
        ids = list(yaml.safe_load((DEV_EXT / "rules" / "spec-rules.overlay.yaml")
                                  .read_text(encoding="utf-8"))["semantic_checks"])
        body = row(status) + "".join(f"| {i} | PASS | MAJOR | 看过 |\n"
                                     for i in ids if i not in ("story_reader_review", "acceptance_testable"))
        body += ("\n<!-- maison-verifier-result:v1 -->\n"
                 f"verifier_subject_id: {SUBJECT}\nverdict: {'PASS' if status == 'PASS' else 'FAIL'}\n"
                 "<!-- /maison-verifier-result:v1 -->\n")
        if status != "PASS":
            (reports.parent / "notes.md").write_text(
                f"# notes\n\n- story_reader_review（报告 {SUBJECT[:8]}）：按报告处置。\n", encoding="utf-8")
        if status != "PASS":
            body += ("\n```yaml\nverification_result:\n  checks:\n"
                     "    - id: story_reader_review\n"
                     f"      status: {status}\n"
                     "      details:\n"
                     "        blocking_findings:\n"
                     "          - 第 5 章说未实名可下单，第 8 章验收里没有这个入口\n"
                     "        advisories: []\n```\n")
        target = self.root / REPORT_REL
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")

    def test_a_complete_report_that_failed_is_not_a_pass(self) -> None:
        """报告的**结构**齐备不等于**审查判它过了**。

        结构齐备而 verdict 是 FAIL 时放行，等于把「审出问题」当成了「审过了」——
        那份 story 会带着一句没发生过的结论交出去。
        """
        self._stub_receipt(0, "回执通过")
        self.write_report("FAIL")
        out = self.check("--deliver")
        self.assertNotEqual(0, out.returncode, (out.stdout + out.stderr)[-600:])
        self.assertIn("判 FAIL", out.stdout + out.stderr)
        self.assertIn("第 5 章说未实名可下单", out.stdout + out.stderr, "没指到那一条阻断问题")

    def test_a_warn_without_blocking_passes_with_its_advisories(self) -> None:
        """AC21：读者审查判 WARN 而没有阻断项，交付门放行，建议项进 notes。"""
        self._stub_receipt(0, "回执通过")
        self.write_report("WARN")
        target = self.root / REPORT_REL
        target.write_text(target.read_text(encoding="utf-8").replace(
            "        blocking_findings:\n          - 第 5 章说未实名可下单，第 8 章验收里没有这个入口\n        advisories: []",
            "        blocking_findings: []\n        advisories:\n          - 第 3 章标题可以更短"), encoding="utf-8")
        out = self.check("--deliver")
        both = out.stdout + out.stderr
        self.assertNotIn("[⑭ 交付门]", both, f"WARN 无阻断却被交付门拦住：{both[-600:]}")
        self.assertIn("第 3 章标题可以更短", both, "建议项没进 notes")

    def test_a_passing_report_raises_nothing_at_the_gate(self) -> None:
        """审查判 PASS、回执过了、结构齐备——交付门这一类不该有问题。

        这份夹具的 story 本身只有一章，别的判据照样会红；**这里只核交付门那一类**，
        不拿整体退出码当交付结论。
        """
        self._stub_receipt(0, "回执通过")
        self.write_report("PASS")
        out = self.check("--deliver")
        both = out.stdout + out.stderr
        self.assertNotIn("判的是", both, "审查判了 PASS 却被交付门拦住")
        self.assertNotIn("未经读者语义审查", both, "有报告却说没审过")
        self.assertNotIn("[⑭ 交付门]", both, f"交付门报了问题：{both[-600:]}")

class ReviewTaskReachesTheVerifier(unittest.TestCase):
    """判据要先成为「任务」，才谈得上做没做。

    注入的清单只列 framework 自己那十项、扩展这边又按前缀过滤，两道都漏，
    读者审查就不是「任务」，审查者不会去做它。

    输入自带：临时工作区里造一个最小需求目录。拿仓内真实需求当输入的话，
    CLI 起跑时装置会把 `doc/features` 整个迁走，测试跟着一起塌。
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        (self.root / "doc").mkdir(parents=True)
        shutil.copytree(DEV_EXT, self.root / "doc" / "extensions")
        link_harness_yaml(self.root)
        src = self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
        src.mkdir(parents=True)
        (src.parent / "story.md").write_text(STORY_MD, encoding="utf-8")
        (src / "materials.json").write_text(json.dumps({"materials": [
            {"kind": "image", "paths": ["assets/doc-a/one.png"], "caption": "签约页"},
        ]}, ensure_ascii=False), encoding="utf-8")

    def inject(self, feature: str = FEATURE) -> str:
        driver = """
        import(process.argv[2]).then(async m => {
          const out = await m.default({ projectRoot: process.argv[3],
                                        feature: process.argv[4], phase: 'spec' });
          process.stdout.write((out.promptFragments || []).join('\\n\\n'));
        });
        """
        script = self.root / "drive.mjs"
        script.write_text(driver, encoding="utf-8")
        hook = self.root / "doc/extensions/hooks/shared/pre_verifier.mjs"
        r = subprocess.run(
            ["node", str(script), hook.resolve().as_uri(), str(self.root), feature],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(0, r.returncode, r.stderr[:600])
        return r.stdout

    def test_the_reader_review_is_injected_not_filtered_out(self) -> None:
        text = self.inject()
        self.assertIn("story_reader_review", text, "读者审查被滤掉了")

    def test_it_comes_first(self) -> None:
        """它要通读一份 300 行的归档件，排在后面最容易被当附注跳过。"""
        text = self.inject()
        self.assertLess(text.index("story_reader_review"), text.index("知识判据"))

    @property
    def overlay(self) -> Path:
        return self.root / "doc" / "extensions" / "rules" / "spec-rules.overlay.yaml"

    def overlay_method(self) -> str:
        """判据与结论要求的**唯一维护处**：spec overlay 的 `story_reader_review`。"""
        text = self.overlay.read_text(encoding="utf-8")
        at = text.index("story_reader_review:")
        end = text.index("\n# ", at)
        return text[at:end]

    def test_the_task_lists_every_image_with_its_state(self) -> None:
        """任务里没有的**数据**，审查者拿不到：图逐张列出，连它是什么、用不用一起。"""
        text = self.inject()
        self.assertIn("材料里的图", text)
        self.assertIn("assets/doc-a/one.png", text)
        self.assertIn("签约页", text)

    def test_a_broken_manifest_is_an_input_gap_not_no_images(self) -> None:
        """审查端与作者端对同一份坏清单给同一个含义：**缺口**，不是「本项无图不适用」。

        `materials` 是字符串时直接 `.filter` 会抛——审查者拿到的会是一个没有来源说明的
        TypeError，而它本该读到「清单坏了」。
        """
        src = self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
        for name, payload in (("空对象", "{}"),
                              ("materials 是字符串", '{"materials":"invalid"}'),
                              ("旧的 items/path",
                               '{"items":[{"kind":"image","path":"a.png"}]}'),
                              ("坏 JSON", "{ 坏了")):
            with self.subTest(shape=name):
                (src / "materials.json").write_text(payload, encoding="utf-8")
                text = self.inject()
                self.assertIn("输入有缺口", text, "坏清单被当成「无图不适用」")
                self.assertIn("story_flow.py round", text, "没给修法")
                self.assertNotIn("材料清单里没有图片", text)

    def test_a_legal_empty_manifest_is_no_images(self) -> None:
        src = self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
        (src / "materials.json").write_text(
            json.dumps({"materials": [{"kind": "doc", "paths": ["RR/prd.md"]}], "sources": [], "origins": []},
                       ensure_ascii=False), encoding="utf-8")
        text = self.inject()
        self.assertIn("材料清单里没有图片", text)
        self.assertNotIn("输入有缺口", text)

    def test_an_image_the_disk_cannot_read_is_marked(self) -> None:
        """登记着而盘上读不到：审查要知道这一张现在看不了，不是「作者没用它」。"""
        text = self.inject()
        self.assertIn("盘上读不到", text)

    def test_the_host_assembly_really_carries_the_overlay_method(self) -> None:
        """正常路径的证据：**宿主装配之后**任务里有这份方法。

        只断言「fragment 里没有方法」加「overlay 文件里有那段文字」证明不了它到得了
        审查者手上——中间那一步（框架把 overlay 合进本阶段判据）没被核过。
        这里调框架自己那个合并函数（`mergePhaseRuleSpec`），不启动真实 CLI、不改 Framework。
        """
        harness = REPO / "demo" / "framework" / "harness"
        runner = harness / "node_modules" / "ts-node" / "dist" / "bin.js"
        if not runner.is_file():
            self.skipTest("framework/harness 里没有 ts-node")
        script = (
            "const { mergePhaseRuleSpec } = require('./profile-loader');"
            "const YAML = require('yaml'); const fs = require('fs');"
            f"const overlay = YAML.parse(fs.readFileSync({json.dumps(str(self.overlay))}, 'utf-8'));"
            "const base = { phase: 'spec', semantic_checks: { framework_own: { description: 'x' } } };"
            "const merged = mergePhaseRuleSpec(base, overlay);"
            "const item = merged.semantic_checks.story_reader_review || {};"
            "process.stdout.write(JSON.stringify({"
            "  hint: String(item.ai_prompt_hint || ''),"
            "  desc: String(item.description || ''),"
            "  keptFrameworkOwn: !!merged.semantic_checks.framework_own }));")
        out = subprocess.run(["node", str(runner), "-e", script],
                             cwd=str(harness), capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(0, out.returncode, out.stderr[-600:])
        got = json.loads(out.stdout)
        self.assertTrue(got["keptFrameworkOwn"], "合并把框架自己那几项挤掉了")
        both = got["desc"] + got["hint"]
        for needle in ("跨章对着读", "blocking_findings", "advisories", "不许空",
                       "按实际关系判"):
            self.assertIn(needle, both, f"宿主装配后的任务里没有「{needle}」")

    def test_the_method_is_maintained_only_in_the_overlay(self) -> None:
        """方法一份：overlay 维护「怎么判」，构造器只给这一次的数据。

        两处各写一遍时改一处另一处静默过期——而过期的那一份仍会被送到审查者手上。
        """
        method = self.overlay_method()
        for needle in ("总览与局部加起来", "端到端过程", "分支去向", "理由成不成立",
                       "跨章对着读", "blocking_findings", "advisories", "不许空"):
            self.assertIn(needle, method, f"overlay 里没有「{needle}」")
        fragment = self.inject()
        for needle in ("总览与局部加起来", "端到端过程", "理由成不成立", "blocking_findings"):
            self.assertNotIn(needle, fragment, f"构造器又复制了一份方法：{needle}")

    def test_the_collaboration_order_is_judged_by_relation_not_headcount(self) -> None:
        """两方之间也可能有复杂往返，多方单向直通反而不需要——不设人数门槛。"""
        method = self.overlay_method()
        self.assertNotIn("三个以上参与方", method)
        self.assertIn("按实际关系判", method)
        self.assertNotIn("三个以上参与方", self.inject())

    def test_the_task_indexes_the_story_instead_of_copying_it(self) -> None:
        """审查对象给阅读入口：文件、内容摘要、按作者区标题排好的阅读段；正文由审查者分段读盘上原文，不搬进任务。"""
        task = self.inject()
        self.assertIn("### 审查对象：当前 `AR/story.md`", task)
        section = task.split("### 审查对象", 1)[1].split("\n### ", 1)[0]
        self.assertRegex(section, r"内容摘要 [0-9a-f]{16}")
        self.assertIn("  - ## 背景", section)
        self.assertIn("## 背景", section)
        self.assertNotIn("用户现在拿不到凭据。", task, "正文又整段搬进了任务")

    def test_a_projection_refresh_keeps_the_task_and_an_authored_edit_changes_it(self) -> None:
        """AC22：机器区重投不改审查片段（审查对象不变）；作者区改了，片段跟着变。片段不含机器区内容。"""
        story = self.root / "doc" / "features" / FEATURE / "AR" / "story.md"
        zone = ("\n<!-- story-build:begin 技术契约·端云接口 · 由spec 「宿主扩展治理项 › 技术契约 › 端云接口」生成，改它请改真源 · sha256:0000000000000000 -->\n"
                "| 接口 | 用途 |\n|---|---|\n| queryState | 查状态 |\n<!-- story-build:end -->\n")
        story.write_text(STORY_MD + zone, encoding="utf-8")
        first = self.inject()
        story.write_text(STORY_MD + zone.replace("queryState | 查状态", "queryState | 查处理状态"), encoding="utf-8")
        self.assertEqual(first, self.inject(), "机器区重投换了审查对象")
        self.assertNotIn("queryState", first, "机器区内容进了审查片段")
        story.write_text(STORY_MD + "\n作者补的一句。\n" + zone, encoding="utf-8")
        self.assertNotEqual(first, self.inject(), "作者区改了，审查对象没跟着变")

    def test_a_heading_inside_a_fence_is_not_a_section(self) -> None:
        """围栏里的标题是被引用的样例，不进段落范围；正文改了摘要跟着变。"""
        story = self.root / "doc" / "features" / FEATURE / "AR" / "story.md"
        before = self.inject()
        story.write_text(STORY_MD + "\n```markdown\n## 样例里的标题\n```\n", encoding="utf-8")
        task = self.inject()
        self.assertNotIn("样例里的标题", task.split("### 审查对象", 1)[1].split("\n### ", 1)[0])
        self.assertNotEqual(before, task, "正文变了审查对象没跟着变")

    def reading_section(self) -> str:
        return self.inject().split("### 审查对象", 1)[1].split("\n### ", 1)[0]

    def test_the_reading_segments_cover_the_story_once(self) -> None:
        """阅读段按作者区标题依次排开：每个标题一段、顺序与正文一致，章节标题不重复成段；围栏里的标题不成段。"""
        bodies = {
            "标题前有前言": ("开头一句说明。\n\n" + STORY_MD, ["（第一个标题之前的开头）", "# 甲需求（SMPFEAT）", "## 背景"]),
            "嵌套与无节": (STORY_MD + "\n## 业务流程\n\n总述。\n\n### 发起\n\n甲。\n\n### 撤销\n\n乙。\n\n## 验收\n\n丙。\n",
                       ["# 甲需求（SMPFEAT）", "## 背景", "## 业务流程", "## 业务流程 › ### 发起", "## 业务流程 › ### 撤销", "## 验收"]),
            "围栏标题与长附录": (STORY_MD + "\n```markdown\n## 样例\n```\n\n## 附录\n\n" + "| a | b |\n" * 200,
                         ["# 甲需求（SMPFEAT）", "## 背景", "## 附录"]),
        }
        story = self.root / "doc" / "features" / FEATURE / "AR" / "story.md"
        for name, (body, expected) in bodies.items():
            with self.subTest(name):
                story.write_text(body, encoding="utf-8")
                rows = [line.strip()[2:] for line in self.reading_section().splitlines() if line.startswith("  - ")]
                self.assertEqual(expected, rows)
                self.assertNotRegex(self.reading_section(), r"L\d+–L\d+", "阅读段又带回了行号")

    def test_layout_only_changes_in_a_machine_zone_keep_the_task(self) -> None:
        """机器区等行数替换、多一个空行、内容变长：审查任务都不变；作者区改一个字就变（G04）。"""
        story = self.root / "doc" / "features" / FEATURE / "AR" / "story.md"
        zone = ("\n## 附录\n\n<!-- story-build:begin 技术契约·端云接口 · 由spec 「宿主扩展治理项 › 技术契约 › 端云接口」生成，改它请改真源 · sha256:0000000000000000 -->\n"
                "| 接口 | 用途 |\n|---|---|\n| queryState | 查状态 |\n<!-- story-build:end -->\n")
        story.write_text(STORY_MD + zone, encoding="utf-8")
        first = self.inject()
        for variant in (zone.replace("查状态", "查询状态"), zone.replace("| queryState | 查状态 |\n", "| queryState | 查状态 |\n\n"),
                        zone.replace("查状态", "查状态" + "，并带回最近一次的处理结果" * 5)):
            story.write_text(STORY_MD + variant, encoding="utf-8")
            self.assertEqual(first, self.inject(), "机器区排版刷新换了审查对象")
        story.write_text(STORY_MD.replace("拿不到", "拿不到了") + zone, encoding="utf-8")
        self.assertNotEqual(first, self.inject(), "作者区改了，审查对象没跟着变")
        self.assertIn("## 附录", self.reading_section(), "附录不在阅读段里，机器区没人审")

    def test_an_unreadable_story_is_a_skip_not_an_empty_full_text(self) -> None:
        """空串冒充全文 = 审查会对着空白作答；如实 SKIP。"""
        (self.root / "doc" / "features" / FEATURE / "AR" / "story.md").write_text(
            "   \n", encoding="utf-8")
        task = self.inject()
        self.assertIn("SKIP", task)
        self.assertNotIn("```````markdown", task)

    def test_the_task_says_where_the_overwritten_ar_is_kept(self) -> None:
        """当前 AR/design.md 是提取稿：回查上游原话给 .backups/local/ 的位置，不让它用提取稿替。"""
        task = self.inject()
        self.assertIn("`.backups/local/`", task)
        self.assertIn("提取稿", task)

    def test_the_task_carries_the_recheck_list(self) -> None:
        """审查拿到的回看清单与作者手里的是同一张：逐条核去向，不另编一份。"""
        task = self.inject()
        self.assertIn("### 回看清单", task)
        self.assertIn("这句话材料里有吗", task.split("### 回看清单", 1)[1])
        method = self.overlay_method()
        for needle in ("回看清单逐条核去向", "撞点", "算没写依据"):
            self.assertIn(needle, method, f"overlay 的审查提示里没有「{needle}」")

    def test_the_task_carries_the_contract_questions(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        text = self.inject()
        for chapter in contract["chapters"]:
            self.assertIn(chapter["questions"][0], text,
                          f"「{chapter['title']}」的读者问题没送到")

    def test_the_output_contract_lives_with_the_method(self) -> None:
        """PASS 只进汇总表、明细只列非 PASS——本项不设例外，否则正常 PASS 会被拒。

        它与方法同处一份（overlay）：输出要求与判据分在两个文件时，改一处就对不上。
        """
        method = self.overlay_method()
        self.assertIn("汇总表", method)
        self.assertIn("不许空", method)
        self.assertIn("blocking_findings", method)
        self.assertIn("advisories", method)
        self.assertNotIn("为标记的一块", method, "又要求了 markdown 块")

    def plan_path(self) -> Path:
        return self.root / "doc" / "features" / FEATURE / "AR" / "story-src" / "story-template.md"

    def base_plan(self) -> str:
        return (REPO / "test/fixtures/failure-modes/R01-verdict-echo/good/doc/features"
                / "REQ-DEMO/AR/story-src/story-template.md").read_text(encoding="utf-8")

    def test_the_task_points_at_the_writing_design_and_follows_it(self) -> None:
        """写作设计给阅读入口与摘要；改了设计，任务跟着变——审查核的是这一版。"""
        base = self.base_plan()
        self.plan_path().write_text(
            base.replace("## 阅读主线\n\n", "## 阅读主线\n\n设计里独有的一句甲。\n"), encoding="utf-8")
        task = self.inject()
        self.assertIn("### 作者的写作设计", task)
        self.assertIn("待核的作者判断", task, "没说清设计是待核的判断而不是标准")
        self.assertIn("## 阅读主线", task)
        self.assertNotIn("设计里独有的一句甲。", task, "设计全文又搬进了任务")
        self.plan_path().write_text(
            base.replace("## 阅读主线\n\n", "## 阅读主线\n\n改过之后的一句乙。\n"), encoding="utf-8")
        self.assertNotEqual(task, self.inject(), "任务没跟着当前设计走")

    def test_a_missing_writing_design_is_a_gap_not_an_empty_design(self) -> None:
        section = self.inject().split("### 作者的写作设计", 1)[1].split("###", 1)[0]
        self.assertIn("写作设计缺口", section)
        self.assertNotIn("```", section, "拿一段空围栏冒充审过了设计")

    def test_the_task_points_at_the_original_materials(self) -> None:
        """审查要能回到原件：必审输入逐份给位置与摘要；该有而读不到的点名，不替它下结论。"""
        feature = self.root / "doc" / "features" / FEATURE
        (feature / "RR").mkdir(parents=True, exist_ok=True)
        (feature / "RR" / "prd.md").write_text("# 产品需求\n", encoding="utf-8")
        reads = lambda text: text.split("### 读这些", 1)[1].split("\n### ", 1)[0]
        section = reads(self.inject())
        self.assertIn("`RR/prd.md`（摘要 ", section)
        self.assertIn("acceptance.yaml", section)
        self.assertNotIn("读不到 `SR/design.md`", self.inject(), "本地单没有系统设计是正常的")
        (feature / "AR" / "detail.json").write_text("{}", encoding="utf-8")
        self.assertNotIn("读不到 `SR/design.md`", self.inject(), "本地需求留着 detail.json 仍是本地需求")
        remote = f"AR{FEATURE}"
        shutil.copytree(feature, feature.parent / remote)
        self.assertIn("读不到 `SR/design.md`", self.inject(remote), "系统需求缺必备来源没点名")

    def test_every_registered_reading_copy_is_a_required_input(self) -> None:
        """必审集合从 origins 派生：作者表漏写一行，那份原件仍在审查者面前；只取图的原件由图片登记核。"""
        src = self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
        (src / "materials.json").write_text(json.dumps({"materials": [], "origins": [
            {"path": "inbox/规则 (终版).docx", "kind": "converted-source", "readable_paths": ["AR/story-src/upstream.md"]},
            {"path": "inbox/截图.docx", "kind": "converted-source", "readable_paths": ["inbox/截图.docx"],
             "image_paths": ["assets/截图/a.png"]},
        ]}, ensure_ascii=False), encoding="utf-8")
        section = self.inject().split("### 读这些", 1)[1].split("\n### ", 1)[0]
        self.assertIn("`AR/story-src/upstream.md`", section)
        self.assertIn("**读不到**", section, "登记了却不在盘上的阅读稿没点名")
        self.assertNotIn("inbox/截图.docx`", section)

    def test_an_open_update_brings_its_before_and_a_missing_one_is_a_gap(self) -> None:
        src = self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
        (src / "story-flow.json").write_text(json.dumps({"update": {"open": "20260101-000000"}}), encoding="utf-8")
        task = self.inject()
        self.assertIn("缺比较基准，不是没有变化", task)
        before = src / "updates" / "20260101-000000" / "before" / "AR"
        before.mkdir(parents=True)
        (before / "story.md").write_text("# 旧稿\n", encoding="utf-8")
        task = self.inject()
        self.assertIn("`AR/story-src/updates/20260101-000000/before/AR/story.md`（摘要 ", task)
        self.assertIn("### 本轮 update 20260101-000000：新稿对照有效旧依据", task)

    def test_the_fragment_follows_the_basis_not_the_flow_bookkeeping(self) -> None:
        """依据变了审查片段跟着变；流程状态记一笔、notes 改写不制造新的审查对象。"""
        src = self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
        (src / "story-flow.json").write_text(json.dumps({"rounds": []}), encoding="utf-8")
        first = self.inject()
        (src / "story-flow.json").write_text(json.dumps({"rounds": [], "closed_at": "x"}), encoding="utf-8")
        self.assertEqual(first, self.inject(), "流程簿记变化换了审查对象")
        (src / "decisions.json").write_text(json.dumps({"decisions": []}), encoding="utf-8")
        self.assertNotEqual(first, self.inject(), "登记的决定变了，审查对象却没变")

    def test_the_overlay_judges_against_sources_not_the_design(self) -> None:
        """先按原材料独立判断，再用设计定位作者的安排——设计不是审查标准；方法只在 overlay。"""
        method = self.overlay_method()
        for needle in ("先独立想清楚", "写作设计", "设计漏掉的不因此算不在范围", "写了理由不等于理由成立",
                       "还开着的决定被写成已定", "acceptance.yaml", "正文提到过", "真实待决写清了边界",
                       "写明未验证与影响"):
            self.assertIn(needle, method, f"overlay 里没有「{needle}」")
        fragment = self.inject()
        for needle in ("先独立想清楚", "设计漏掉的不因此算不在范围", "还开着的决定被写成已定"):
            self.assertNotIn(needle, fragment, f"构造器又复制了一份方法：{needle}")

    def test_the_task_does_not_mention_a_publisher(self) -> None:
        """报告由调用方原样写出，没有钩子代它发布——任务书里不该还有那一环。"""
        text = self.inject()
        self.assertNotIn("插件", text)



class TheTaskMovesOnlyWithTheAuthorsInput(unittest.TestCase):
    """U38：审查片段只随作者输入变化，登记一份报告不铸出新的审查对象。

    framework 按材料摘要给审查对象寻址，钩子片段在摘要里。片段里写「上一份报告的路径」时，
    每登记一份报告下一次就是新对象，同一份材料审了又审（09-26 实跑 auto 派审 20 次）。
    """

    setUp = ReviewTaskReachesTheVerifier.setUp
    inject = ReviewTaskReachesTheVerifier.inject

    def register_report(self, subject: str) -> None:
        reports = self.root / "doc" / "features" / FEATURE / "spec" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        ledger = reports / "verifier.conclusions.json"
        data = json.loads(ledger.read_text(encoding="utf-8")) if ledger.is_file() else {}
        data[subject] = {"verdict": "PASS"}
        ledger.write_text(json.dumps(data), encoding="utf-8")
        (reports / f"verifier.report.{subject}.md").write_text("审查正文。\n", encoding="utf-8")

    def decisions(self, title: str) -> None:
        src = self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
        (src / "decisions.json").write_text(json.dumps({"decisions": [
            {"id": "D1", "status": "open", "title": title, "decider": "需求方",
             "clarification": "1. 甲\n2. 乙"}]}, ensure_ascii=False), encoding="utf-8")

    def test_registering_reports_leaves_the_task_unchanged(self) -> None:
        self.decisions("超时后怎么办")
        first = self.inject()
        self.register_report("a" * 64)
        second = self.inject()
        self.register_report("b" * 64)
        third = self.inject()
        self.assertEqual(first, second, "登记一份报告就改了审查片段：审查对象会跟着换代")
        self.assertEqual(first, third)
        self.assertIn("verifier.conclusions.json", self.overlay_text(),
                      "上一份报告的找法要写在判据里，片段里不写")

    def test_the_authors_input_still_moves_the_task(self) -> None:
        self.decisions("超时后怎么办")
        before = self.inject()
        self.decisions("超时之后是否自动重试")
        self.assertNotEqual(before, self.inject(), "决策登记改了，审查片段却没变")

    def overlay_text(self) -> str:
        return (self.root / "doc" / "extensions" / "rules" / "spec-rules.overlay.yaml").read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
