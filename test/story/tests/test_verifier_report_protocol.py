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

REPO = Path(__file__).resolve().parents[3]
MODULE = REPO / "doc" / "extensions" / "hooks" / "shared" / "verifier-report.mjs"
STORY_BUILD = REPO / "doc/extensions/skills/story/scripts/story-build.mjs"
CONTRACT = REPO / "doc/extensions/skills/story/contracts/story-chapters.json"
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

    def _run(self, *, summary, report: str | None) -> dict:
        """summary=None 表示 harness 还没跑过。"""
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
        """summary 在而没有落点 = 本宿主没登记审查员：如实披露，不当缺件。"""
        out = self._run(summary={"phase": "spec"}, report=None)
        self.assertEqual("NOT_APPLICABLE", out["status"])
        self.assertIn("没有登记审查员", out["detail"])

    def test_a_declared_landing_with_no_file_fails(self) -> None:
        """落点写了、文件不在 = 派了 verifier 却没把回复写下来。"""
        out = self.run_with(None)
        self.assertEqual("FAIL", out["status"])
        self.assertIn("原样写到", out["problems"][0])


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

    def test_a_non_pass_row_missing_a_key_fails(self) -> None:
        out = self._run(row("FAIL") + DETAILS_MISSING_ADVISORIES)
        self.assertEqual("FAIL", out["status"])
        self.assertIn("advisories", out["problems"][0])

    def test_a_per_unit_table_is_named_as_the_wrong_shape(self) -> None:
        """做成逐单元裁决表 = 做成了另一件事：那张表的量随材料条数涨。"""
        out = self._run(row("PASS") + PER_UNIT_TABLE)
        self.assertEqual("FAIL", out["status"])
        self.assertIn("逐单元裁决表", out["problems"][0])


class TheDeliveryGateIsWiredToTheFramework(unittest.TestCase):
    """交付门只在 `--deliver` 起作用，而且跑不起来不算通过。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "work"
        (self.root / "doc").mkdir(parents=True)
        shutil.copytree(REPO / "doc" / "extensions", self.root / "doc" / "extensions",
                        ignore=shutil.ignore_patterns("__pycache__", ".adapt-*", "node_modules"))
        # 台账齐备，check 才走得到后面的判据；这一份 story 本身合不合格不是这里要判的。
        src = self.root / "doc" / "features" / FEATURE / "AR" / "story-src"
        src.mkdir(parents=True)
        (src.parent / "story.md").write_text(STORY_MD, encoding="utf-8")
        (src / "decisions.json").write_text("[]", encoding="utf-8")
        rows = [f"第 {i} 项：查过，无。" for i in range(1, 8)]
        (src / "copyedit.md").write_text("\n".join(rows) + "\n", encoding="utf-8")

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

    def test_deliver_is_refused_offline(self) -> None:
        out = subprocess.run(
            ["node", str(STORY_BUILD), "check", "--deliver", "--offline",
             "--story", str(REPO / "test/story/golden/story-金样-AR90004.md")],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertNotEqual(0, out.returncode)
        self.assertIn("互斥", out.stderr)


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
        shutil.copytree(REPO / "doc" / "extensions", self.root / "doc" / "extensions")
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

    def test_the_task_asks_about_every_image(self) -> None:
        """任务里没有的问题，审查者不会去问。图逐张列出，连它是什么一起。"""
        text = self.inject()
        self.assertIn("材料里的图，逐张回答", text)
        self.assertIn("assets/doc-a/one.png", text)
        self.assertIn("签约页", text)
        self.assertIn("story 用了没有", text)

    def test_the_task_carries_the_contract_questions(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        text = self.inject()
        for chapter in contract["chapters"]:
            self.assertIn(chapter["questions"][0], text,
                          f"「{chapter['title']}」的读者问题没送到")

    def test_the_task_follows_the_upstream_output_contract(self) -> None:
        """PASS 只进汇总表、明细只列非 PASS——本项不设例外，否则正常 PASS 会被拒。"""
        text = self.inject()
        self.assertIn("汇总表", text)
        self.assertIn("不许空", text)
        self.assertIn("blocking_findings", text)
        self.assertIn("advisories", text)
        self.assertNotIn("为标记的一块", text, "又要求了 markdown 块")

    def test_the_task_does_not_mention_a_publisher(self) -> None:
        """报告由调用方原样写出，没有钩子代它发布——任务书里不该还有那一环。"""
        text = self.inject()
        self.assertNotIn("插件", text)


if __name__ == "__main__":
    unittest.main()
