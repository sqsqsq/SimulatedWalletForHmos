"""verifier 报告的读取与 story 审查落盘 —— 报告认不认得出、审了没有。

**逐行裁决的核对在步骤 10 退场**：那条路径要求 verifier 把每条判定写成一行、
每行附一段够长的引文，门禁再逐行核键与引文。它逼出的是把清单里的字抄进证据列的回声，
而不是判断。留下的是两件仍然确定的事：

  ① 报告文件认不认得出、读不读得动（两种协议、多份 subject、坏文件不冒充「还没跑」）；
  ② story 审查那一项的结果块在不在、两类结论齐不齐。

报几条、报得对不对由人抽查，门禁判不了。

## 只认发布器落盘的那一份（2026-09-04 换边）

谁写这份报告，取决于宿主 adapter 声明的 ``verifier_capability``：声明了的
（claude / codeagent 的 ``subagent_stop``、opencode 的 ``task_tool_result``）由钩子
从子 agent 的**终态消息**生成，按 subject 分区落盘 ``verifier.report.<64位subject>.json``。

早先这里还认执行方自己写的四种文件名，理由是「没有发布机制的宿主也得能核」。
一次真实实跑给了反例：审查项没做成，最后是**主模型把 verifier 的文本转写成
`verifier-report.md`**，门收下了、harness 判 PASS。主模型能写出来的东西作不了
「它被独立审查过」的证据。代价如实记：没有发布器的宿主上这一项记 NOT_APPLICABLE。

## 送达与任务定义，比结果块更早的两道

二跑的失效不在落盘那一步：判据压根没进 verifier 的任务清单（framework 只送它自己那些，
扩展这边又按 `knowledge_` 前缀过滤掉了读者审查），而任务里也没有一条问
「材料登记的每张图用了没有」——于是三张图全丢，审查判「零阻断」。
这两道也在这一份里锚住。
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
MODULE = REPO / "doc" / "extensions" / "hooks" / "shared" / "verifier-report.mjs"
PRE_VERIFIER = REPO / "doc" / "extensions" / "hooks" / "shared" / "pre_verifier.mjs"
CONTRACT = REPO / "doc/extensions/skills/story/contracts/story-chapters.json"

SUBJECT = "a" * 64
OTHER_SUBJECT = "b" * 64

STORY_MD = """# 甲需求（SMPFEAT）

## 背景

用户现在拿不到凭据。
"""

STORY_REVIEW_DRIVER = """
const [, , modulePath, projectRoot, feature, phase, storyPath] = process.argv;
const mod = await import(modulePath);
const out = mod.storyReviewProblems({ projectRoot, feature, phase }, storyPath);
process.stdout.write(JSON.stringify(out));
"""

CLEAN_BLOCK = """## story_reader_review

blocking_findings: []

advisories:
- 术语章「凭证」与「交易详情」的区别可以更靠前

逐章过了：背景、术语、范围、业务方案、业务流程、功能说明、异常与恢复、验收、交付与上线、附录。
"""

BLOCK_MISSING_ADVISORIES = """## story_reader_review

blocking_findings: []
"""

BLOCK_AS_PER_UNIT_TABLE = """## story_reader_review

blocking_findings: []

advisories: []

| 单元键 | 裁决 | 引文 |
|---|---|---|
| PRD:7:2c7fc380 | 讲清 | 用户现在拿不到凭据 |
"""


class StoryReviewLanding(unittest.TestCase):
    """注入了不等于执行了 —— 报告里找不到这一项，就等于这一轮没审。

    只核形态：结果块在不在、两类结论齐不齐、有没有做成另一件事。
    报几条、报得对不对是资格门用成对样本量的，门禁判不了。
    """

    def _run(self, *, reports: dict, with_story: bool = True) -> dict:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            feature_root = root / "doc" / "features" / "SMPFEAT"
            (feature_root / "spec" / "reports").mkdir(parents=True)
            if with_story:
                (feature_root / "AR").mkdir(parents=True)
                (feature_root / "AR" / "story.md").write_text(STORY_MD, encoding="utf-8")
            for name, body in reports.items():
                (feature_root / "spec" / "reports" / name).write_text(body, encoding="utf-8")

            driver = root / "driver.mjs"
            driver.write_text(STORY_REVIEW_DRIVER, encoding="utf-8")
            r = subprocess.run(
                ["node", str(driver), MODULE.as_uri(), str(root), "SMPFEAT", "spec",
                 str(feature_root / "AR" / "story.md")],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(r.returncode, 0, f"driver 挂了：{r.stderr[:600]}")
            return json.loads(r.stdout)

    @staticmethod
    def _report(text: str, subject: str = SUBJECT) -> dict:
        return {f"verifier.report.{subject}.json": json.dumps(
            {"schema_version": 1, "state": "published", "feature": "SMPFEAT",
             "phase": "spec", "subject_id": subject, "verdict": "PASS",
             "blocker_count": 0, "report_text": text},
            ensure_ascii=False)}

    def test_a_report_without_the_block_fails(self) -> None:
        out = self._run(reports=self._report("结论如下。一切正常。\n"))
        self.assertEqual("FAIL", out["status"])
        self.assertIn("story_reader_review", out["problems"][0])
        self.assertIn("等于这一轮没审", out["problems"][0])

    def test_empty_lists_are_a_conclusion(self) -> None:
        """审过而没发现问题，与没审是两件事——前者留得下痕迹。"""
        out = self._run(reports=self._report(CLEAN_BLOCK))
        self.assertEqual("PASS", out["status"], out)
        self.assertEqual([], out["problems"])

    def test_a_missing_section_is_named(self) -> None:
        out = self._run(reports=self._report(BLOCK_MISSING_ADVISORIES))
        self.assertEqual("FAIL", out["status"])
        self.assertIn("advisories", out["problems"][0])

    def test_a_per_unit_table_is_named_as_the_wrong_shape(self) -> None:
        """做成逐单元裁决表 = 做成了另一件事：那张表的量随材料条数涨。"""
        out = self._run(reports=self._report(BLOCK_AS_PER_UNIT_TABLE))
        self.assertEqual("FAIL", out["status"])
        self.assertIn("逐单元裁决表", out["problems"][0])

    def test_no_story_is_not_applicable(self) -> None:
        out = self._run(reports=self._report(CLEAN_BLOCK), with_story=False)
        self.assertEqual("NOT_APPLICABLE", out["status"])
        self.assertEqual([], out["problems"])

    def test_no_report_yet_is_not_applicable(self) -> None:
        """首跑时报告还不存在——那不是通过，是还轮不到判。"""
        out = self._run(reports={})
        self.assertEqual("NOT_APPLICABLE", out["status"])
        self.assertEqual([], out["problems"])


    def test_a_self_written_file_is_not_evidence(self) -> None:
        """执行方自己写的文件不算证据——它证明不了「被独立审查过」。

        这条 2026-09-04 换了边。原来认四种自写文件名，理由是「没有发布器的宿主
        （codex / generic / cursor）也得能核」。一次真实实跑给了反例：审查项没做成，
        最后是**主模型把 verifier 的文本转写成 `verifier-report.md`**，门收下了、
        harness 判 PASS。主模型能写出来的东西作不了它自己被审过的证明。

        代价如实记：没有发布器的宿主上，这一项记 **NOT_APPLICABLE**——
        那台宿主证明不了，不等于没审，所以不判 FAIL。这比收一份可伪造的证明诚实。
        """
        for name in ("verifier.report.md", "verifier-spec.md",
                     "verify-spec.md", "verifier-spec-result.yaml"):
            with self.subTest(name=name):
                out = self._run(reports={name: CLEAN_BLOCK})
                self.assertEqual("NOT_APPLICABLE", out["status"],
                                 f"{name} 被当成了证据——主模型自己就能写出它：{out}")

    def test_all_subjects_are_collected(self) -> None:
        """一个阶段可能有多份 subject 报告，得全收集合并判。

        少收一份就可能把「审过了」判成「没审」：换代或并发时结论本就分在两份文件里。
        """
        reports = {}
        reports.update(self._report("结论如下。这一份没有 story 审查那一块。"))
        reports.update(self._report(CLEAN_BLOCK, OTHER_SUBJECT))
        out = self._run(reports=reports)
        self.assertEqual("PASS", out["status"], f"两份 subject 报告没被合起来判：{out}")

    def test_unreadable_report_is_not_disguised_as_not_run(self) -> None:
        """文件在却读不出正文 → 报「报告坏了」，不能说成「verifier 还没跑」。

        两者的处置完全不同：一个要去查报告，一个是等 verifier 执行。混成一句，
        协议再变一次时又会静默判 NOT_APPLICABLE，跟当初那次断点一模一样。
        """
        out = self._run(reports={f"verifier.report.{SUBJECT}.json": "{ 不是 json"})
        self.assertEqual("FAIL", out["status"], f"坏报告被当成没跑：{out}")
        self.assertTrue(any("读不出结论正文" in p for p in out["problems"]),
                        out["problems"])

    def test_missing_report_text_field_is_reported_too(self) -> None:
        body = json.dumps({"subject_id": SUBJECT, "verdict": "PASS"}, ensure_ascii=False)
        out = self._run(reports={f"verifier.report.{SUBJECT}.json": body})
        self.assertEqual("FAIL", out["status"], f"没有正文字段却放行了：{out}")


if __name__ == "__main__":
    unittest.main()


class ReviewTaskReachesTheVerifier(unittest.TestCase):
    """判据要先成为「任务」，才谈得上做没做。

    二跑 verifier 第一次的报告里完全没有 story 审查：framework 的任务清单只列它自己的项，
    而扩展的注入又按 `knowledge_` 前缀把读者审查滤掉了——两道都漏，它就不是任务。
    """

    def inject(self, feature: str = "AR90006") -> str:
        driver = f"""
        import(process.argv[2]).then(async m => {{
          const out = await m.default({{ projectRoot: process.argv[3],
                                         feature: process.argv[4], phase: 'spec' }});
          process.stdout.write((out.promptFragments || []).join('\\n\\n'));
        }});
        """
        with tempfile.TemporaryDirectory() as d:
            script = Path(d) / "drive.mjs"
            script.write_text(driver, encoding="utf-8")
            r = subprocess.run(
                ["node", str(script), PRE_VERIFIER.as_uri(), str(REPO), feature],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=60)
            self.assertEqual(0, r.returncode, r.stderr[:600])
            return r.stdout

    def test_the_reader_review_is_injected_not_filtered_out(self) -> None:
        text = self.inject()
        self.assertIn("story_reader_review", text,
                      "读者审查又被滤掉了——二跑就是这样一次没做")

    def test_it_comes_first(self) -> None:
        """它要通读一份 300 行的归档件，排在后面最容易被当附注跳过。"""
        text = self.inject()
        self.assertLess(text.index("story_reader_review"), text.index("知识判据"))

    def test_the_task_asks_about_every_image(self) -> None:
        """任务里没有的问题，审查者不会去问——两轮丢图，它一次都没报。"""
        text = self.inject()
        self.assertIn("材料里的图，逐张回答", text)
        self.assertIn("story 用了没有", text)

    def test_the_task_carries_the_contract_questions(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        text = self.inject()
        for chapter in contract["chapters"]:
            self.assertIn(chapter["questions"][0], text,
                          f"「{chapter['title']}」的读者问题没送到")

    def test_one_format_only(self) -> None:
        """结论只按 framework 的 YAML 契约写——两套格式让二跑补做又失败一次。"""
        text = self.inject()
        self.assertIn("blocking_findings", text)
        self.assertIn("advisories", text)
        self.assertNotIn("为标记的一块", text, "又要求了 markdown 块")

    def test_it_says_self_written_files_are_not_evidence(self) -> None:
        self.assertIn("不要另写文件", self.inject())


if __name__ == "__main__":
    unittest.main()
