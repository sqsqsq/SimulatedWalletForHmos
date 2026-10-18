# -*- coding: utf-8 -*-
"""实跑观测的三条事实链：度量读的是真事件、阶段只由证据推进、材料版本认不认得出补图。

对应 P8 / P10 / P9。三者都属于**测试域自己的账**——观测错了，后面每一轮的结论都建在错数上，
而且错得毫无信号：旧口径的「反复 FAIL 的 check」在任何一份真实事件流上恒为空，看上去就像
「没有反复失败」。

每个指标都配**能改变结果的正反样本**：只测「有数据时算得出」，测不出「没数据时会不会凭空造数」。
"""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote
from ext_workspace import DEV_EXT

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "test" / "scripts"
STORY_SCRIPTS = DEV_EXT / "skills" / "story" / "scripts" / "core"

sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(STORY_SCRIPTS))
from materials import frozen, registry  # noqa: E402
import measure_run  # noqa: E402
import phase_state  # noqa: E402

# 真实门禁控制台输出的形态（report-generator.printReportToConsole）。
GATE_FAIL = """
============================================================
  Harness Script Report — spec/demo-feature
============================================================

  ✗ FAIL [BLOCKER] feature_to_acceptance
       功能清单有 3 项在验收标准里找不到对应 AC。
  ✗ FAIL [BLOCKER] verifier_provider_unavailable
       当前 adapter 未登记 interactive 模式的 verifier 能力。
  ⚠ WARN [MAJOR] glossary_terms_used_in_body

  Total: 22  |  PASS: 19  |  FAIL: 2  |  WARN: 1  |  SKIP: 0
  Blockers: 2
"""

GATE_PASS = """
  Harness Script Report — spec/demo-feature
  No FAIL/WARN checks.
  Total: 22  |  PASS: 22  |  FAIL: 0  |  WARN: 0  |  SKIP: 0
  Blockers: 0
"""

# Windows 控制台把中文压成乱码的真实形态：ASCII 段完好，中文整段花掉。
GATE_FAIL_MOJIBAKE = (
    "  � FAIL [BLOCKER] feature_to_acceptance\n"
    "       ¹¦ÄÜÇåµ¥ÓÐ 3 Ïî\n"
    "  Total: 22  |  PASS: 21  |  FAIL: 1  |  WARN: 0  |  SKIP: 0\n"
)


def _events(*records: dict) -> list[dict]:
    out = []
    for i, r in enumerate(records):
        base = {"seq": i, "timestamp": f"2026-09-02T10:{i:02d}:00", "type": "tool",
                "content": "", "tool_name": "bash", "tool_status": "completed",
                "tool_input": {}, "tool_output": None}
        base.update(r)
        out.append(base)
    return out


def _harness(output, *, cmd: str = "cd framework/harness && npx ts-node harness-runner.ts --phase spec") -> dict:
    return {"tool_name": "bash", "tool_input": {"command": cmd}, "tool_output": output}


class MeasureReadsRealEvents(unittest.TestCase):
    """P8：度量必须读 `tool_output`，且**只**从输出面取门禁结论。"""

    def _measure(self, records, *, state: dict | None = None) -> dict:
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            (run / "events.jsonl").write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in _events(*records)),
                encoding="utf-8")
            if state is not None:
                (run / "state.json").write_text(json.dumps(state), encoding="utf-8")
            return measure_run.measure(run / "events.jsonl", run_dir=run)

    def test_check_ids_come_from_tool_output(self):
        """正样本：门禁 FAIL 在输出里 → 认得出、点得出名。"""
        r = self._measure([_harness(GATE_FAIL)])
        ids = dict(r["repeated_check_fails"])
        self.assertEqual(1, ids.get("feature_to_acceptance"))
        self.assertEqual(1, ids.get("verifier_provider_unavailable"))
        self.assertNotIn("glossary_terms_used_in_body", ids, "WARN 不该被算成 FAIL")
        self.assertEqual(1, r["gate_rounds_with_fail"])

    def test_no_failure_means_zero_not_missing(self):
        """反样本：门禁全绿 → 计数为零，且不是「识别不到」。"""
        r = self._measure([_harness(GATE_PASS)])
        self.assertEqual([], r["repeated_check_fails"])
        self.assertEqual(0, r["gate_rounds_with_fail"])
        self.assertEqual(1, r["harness_runs"], "门禁确实跑了——零失败不等于没跑")

    def test_output_only_in_input_side_is_not_counted(self):
        """反样本：同样的文本只出现在**入参**里 → 不算门禁结论。

        这条守的是方向：门禁结论是工具**回**的，不是作者**要**的。反过来会把
        「我打算去看看 FAIL 的那几条」算成一轮真实失败。
        """
        r = self._measure([{"tool_name": "bash",
                            "tool_input": {"command": f"echo '{GATE_FAIL}'"},
                            "tool_output": None}])
        self.assertEqual([], r["repeated_check_fails"])

    def test_mojibake_does_not_break_classification(self):
        """Windows 乱码只毁中文，ASCII 段完好——分类不能因此失明。"""
        r = self._measure([_harness(GATE_FAIL_MOJIBAKE)])
        self.assertEqual(1, dict(r["repeated_check_fails"]).get("feature_to_acceptance"))

    def test_same_id_within_one_round_counts_once(self):
        """同一轮里同一个 id 出现两次（console 一次、cat 报告一次）只算一轮。"""
        r = self._measure([_harness(GATE_FAIL + GATE_FAIL)])
        self.assertEqual(1, dict(r["repeated_check_fails"])["feature_to_acceptance"])

    def test_repeat_across_rounds_accumulates(self):
        """跨轮才累加——判据问的是「同一个 id 在多少轮里失败」。"""
        r = self._measure([_harness(GATE_FAIL), _harness(GATE_FAIL)])
        self.assertEqual(2, dict(r["repeated_check_fails"])["feature_to_acceptance"])
        self.assertEqual(2, r["gate_rounds_with_fail"])

    def test_recovery_after_failure_does_not_keep_counting(self):
        """失败后修好了：第二轮全绿，计数停在 1，轮次也只记 1。"""
        r = self._measure([_harness(GATE_FAIL), _harness(GATE_PASS)])
        self.assertEqual(1, dict(r["repeated_check_fails"])["feature_to_acceptance"])
        self.assertEqual(1, r["gate_rounds_with_fail"])
        self.assertEqual(2, r["harness_runs"])

    def test_various_tool_output_shapes_are_tolerated(self):
        """输出面形态不止字符串：dict / list / None 都不能让度量炸掉或误报。"""
        for shape in (None, "", {"stdout": GATE_FAIL}, [GATE_FAIL], 0):
            with self.subTest(shape=type(shape).__name__):
                r = self._measure([_harness(shape)])
                self.assertIsInstance(r["repeated_check_fails"], list)

    def test_reading_own_artifact_is_not_counted_as_reading_rules(self):
        """读自己的产物时，**输出正文**里出现 framework/ 不改变归类。

        Read 的输出带整份文件内容；把输出掺进路径判定，一份提到 framework/ 的
        spec.md 就会被算成「在猜门禁要什么」，两个指标同时失真。
        """
        r = self._measure([{
            "tool_name": "read",
            "tool_input": {"filePath": "doc/features/demo/spec/spec.md"},
            "tool_output": "<content>见 framework/harness/scripts/check-spec.ts 的判据</content>",
        }])
        self.assertEqual(1, r["reads_own_artifacts"])
        self.assertEqual(0, r["reads_rule_text"])
        self.assertEqual(0, r["reads_checker_source"], "输出里提到 checker 不等于读了它")

    def test_reading_checker_source_is_counted(self):
        """正样本：真去读 checker 源码 → 记 1（目标是 0，所以它必须能被看见）。"""
        r = self._measure([{
            "tool_name": "read",
            "tool_input": {"filePath": "framework/harness/scripts/check-spec.ts"},
            "tool_output": "export function checkSpec() {}",
        }])
        self.assertEqual(1, r["reads_checker_source"])
        self.assertEqual(1, r["reads_rule_text"])

    def test_reading_checker_through_bash_is_counted_too(self):
        """一轮实跑读判据脚本 68 次全走 `node -e readFileSync`，而报表写着 0。

        度量报 0 而实际 68，比没有这项度量更坏——它让人以为这条已经解决了。
        """
        r = self._measure([{
            "tool_name": "bash",
            "tool_input": {"command":
                           "node -e \"const s=require('fs')"
                           ".readFileSync('doc/extensions/skills/story/scripts/core/story-build.mjs',"
                           "'utf8');console.log(s.slice(0,400))\""},
            "tool_output": "function cmdCheck(ctx) {",
        }])
        self.assertEqual(1, r["reads_checker_source"],
                         "bash 里读判据脚本没被算进去——那正是实跑里唯一的读法")

    def test_extension_checkers_count_not_just_framework_ones(self):
        """被读得最多的是扩展自己的判据脚本，不是 framework 的 check-*.ts。"""
        r = self._measure([{
            "tool_name": "read",
            "tool_input": {"filePath": "doc/extensions/hooks/shared/knowledge-application.mjs"},
            "tool_output": "export function coverageProblems() {}",
        }])
        self.assertEqual(1, r["reads_checker_source"])

    def test_equivalent_path_spellings_count_the_same(self):
        """同一次读取，路径写成反斜杠、正斜杠或带重复分隔符，读数一样。

        入参先序列化再匹配时，Windows 路径的反斜杠在 JSON 里变成两个，规则读取全部报 0。
        """
        spellings = {
            "反斜杠": "C:\\ws\\case\\doc\\extensions\\skills\\story\\scripts\\core\\story-build.mjs",
            "正斜杠": "C:/ws/case/doc/extensions/skills/story/scripts/core/story-build.mjs",
            "重复分隔符": "C:\\\\ws\\\\case\\\\doc\\\\extensions//skills/story/scripts/core/story-build.mjs",
        }
        for name, path in spellings.items():
            with self.subTest(spelling=name):
                r = self._measure([{"tool_name": "read", "tool_input": {"filePath": path},
                                    "tool_output": "export function cmdCheck() {}"}])
                self.assertEqual(1, r["reads_checker_source"])
                self.assertEqual(1, r["reads_rule_text"])

    def test_windows_paths_in_bash_and_grep_are_seen(self):
        """bash 与 grep 仍按实际命令判是不是读；路径写法不影响。"""
        r = self._measure([
            {"tool_name": "bash",
             "tool_input": {"command": "type C:\\ws\\doc\\extensions\\hooks\\spec\\post_check.mjs"}},
            {"tool_name": "grep",
             "tool_input": {"pattern": "cmdCheck", "path": "C:\\ws\\doc\\extensions\\skills"}},
        ])
        self.assertEqual(2, r["reads_rule_text"])
        self.assertEqual(2, r["reads_checker_source"], "在 skills 目录里检索也是读源码")

    def test_paths_only_in_output_or_in_writes_are_not_reads(self):
        """输出里出现的路径不是模型读入；写文件提到规则路径也不是读。"""
        r = self._measure([
            {"tool_name": "bash", "tool_input": {"command": "git status"},
             "tool_output": "M doc\\extensions\\skills\\story\\scripts\\core\\story-build.mjs"},
            {"tool_name": "write",
             "tool_input": {"filePath": "C:\\ws\\doc\\extensions\\skills\\story\\x.mjs",
                            "content": "export {}"}},
        ])
        self.assertEqual(0, r["reads_rule_text"])
        self.assertEqual(0, r["reads_checker_source"])

    def test_running_a_checker_and_piping_its_output_is_not_a_read(self):
        """执行判据脚本再截输出不是读它的源码（算法 v2）：`tail` 作用于管道，不作用于路径。"""
        r = self._measure([{
            "tool_name": "bash",
            "tool_input": {"command":
                           "node doc/extensions/skills/story/scripts/core/story-build.mjs skeleton "
                           "--feature X | tail -20"},
            "tool_output": "[story-build skeleton] 已起手",
        }, {
            "tool_name": "bash",
            "tool_input": {"command":
                           "node doc/extensions/skills/story/scripts/core/story-build.mjs check "
                           "--feature X | tail -20"},
            "tool_output": "[story-build check] 通过：10 章",
        }])
        self.assertEqual(0, r["reads_checker_source"])
        self.assertEqual(0, r["reads_rule_text"])
        self.assertEqual(1, r["bash_rule_path_not_read"], "执行非门禁脚本要记成未分类，看得见；check 是门禁")
        self.assertEqual("v3", r["read_algorithm"])

    def test_an_escaped_bar_in_a_grep_pattern_is_not_a_pipe(self):
        """grep 模式里的 `\\|` 是「或」，不是管道：模式之后的路径仍在读取动词那一段里。"""
        r = self._measure([{
            "tool_name": "bash",
            "tool_input": {"command": 'grep -n "Code Facts\\|code_facts" framework/harness/scripts/utils/context-facts.ts | head'},
        }])
        self.assertEqual(1, r["reads_checker_source"])

    def test_framework_source_beyond_check_scripts_counts(self):
        """framework 下的工具源码、`*.ts` 通配与 harness 源码目录里的递归检索都算读机制源码。"""
        for command in ("sed -n '1,80p' framework/harness/scripts/utils/context-facts.ts",
                        "grep -n applySequentialMultiplier framework/harness/scripts/utils/*.ts",
                        "grep -rn acceptance_flow_structure framework/harness/scripts/utils/ | head",
                        "grep -rn knowledge_rule framework/harness",
                        "rg flowProblems doc/extensions/hooks"):
            with self.subTest(command=command):
                r = self._measure([{"tool_name": "bash", "tool_input": {"command": command}}])
                self.assertEqual(1, r["reads_checker_source"])

    def test_prompts_and_reports_under_harness_are_not_source(self):
        """harness 目录下的提示词与报告不是源码：目录检索只认到目录为止的路径。"""
        for command in ("cat framework/harness/prompts/spec-verifier.md",
                        "cat framework/harness/reports/summary.json",
                        "grep -rn x framework/harness/prompts/",
                        "grep -rn x framework/harness/prompts",
                        "rg x doc/extensions/skills/story/phases",
                        'grep -rn "framework" 02-Feature/WalletMain/src/main/ets'):
            with self.subTest(command=command):
                r = self._measure([{"tool_name": "bash", "tool_input": {"command": command}}])
                self.assertEqual(0, r["reads_checker_source"])

    def test_a_glob_counts_only_when_it_lists_source_files(self):
        """Glob 列的是它的模式要的文件：在 framework 下找 `.md` 不是读源码，找 `.mjs` 才是。"""
        md = self._measure([{"tool_name": "glob", "tool_input": {"path": "C:/ws/framework", "pattern": "**/spec*.md"}}])
        self.assertEqual(0, md["reads_checker_source"])
        mjs = self._measure([{"tool_name": "glob", "tool_input": {"pattern": "doc/extensions/hooks/**/*.mjs"}}])
        self.assertEqual(1, mjs["reads_checker_source"])

    def test_knowledge_and_phase_rule_yaml_are_not_source(self):
        """知识与阶段规则是写给模型读的，不是机制源码。"""
        r = self._measure([
            {"tool_name": "read", "tool_input": {"filePath": "doc/extensions/knowledge/facts/demo.md"}},
            {"tool_name": "bash", "tool_input": {"command": "cat framework/specs/phase-rules/spec-rules.yaml"}},
        ])
        self.assertEqual(0, r["reads_checker_source"])

    def test_read_and_execute_in_one_command_counts_the_read(self):
        """读与执行混在一条命令里：读的那一段照算，执行的那一段不算。"""
        r = self._measure([{
            "tool_name": "bash",
            "tool_input": {"command":
                           "cat doc/extensions/hooks/spec/post_check.mjs && "
                           "node doc/extensions/skills/story/scripts/core/story-build.mjs check | head"},
        }])
        self.assertEqual(1, r["reads_checker_source"])
        self.assertEqual(0, r["bash_rule_path_not_read"])

    def test_powershell_wrapped_read_is_seen(self):
        """PowerShell 外壳里的读取动词照样认。"""
        r = self._measure([{
            "tool_name": "bash",
            "tool_input": {"command":
                           "\"C:\\Windows\\powershell.exe\" -Command "
                           "\"Get-Content doc/extensions/hooks/spec/post_check.mjs | Select-Object -First 40\""},
        }])
        self.assertEqual(1, r["reads_checker_source"])

    def test_reading_knowledge_is_not_reverse_engineering(self):
        """反样本：知识层是给模型实现需求用的内容，读它正当，不算逆向判据。"""
        r = self._measure([{
            "tool_name": "read",
            "tool_input": {"filePath": "doc/extensions/knowledge/constraints/ux.md"},
            "tool_output": "UX-01 …",
        }])
        self.assertEqual(0, r["reads_checker_source"])
        self.assertEqual(1, r["reads_rule_text"])

    def test_startup_gap_measures_until_the_model_moves(self):
        """起跑到模型动第一下。装置起跑当场就写事件，拿它当锚点量到的是装置自己。"""
        r = self._measure([_harness(GATE_PASS)],
                          state={"started_at": "2026-09-04 14:20:51"})
        self.assertIsNotNone(r["startup_gap_sec"])
        self.assertEqual("run_state", r["startup_gap_source"])

    def test_startup_gap_unknown_is_not_zero(self):
        r = self._measure([_harness(GATE_PASS)])
        self.assertIsNone(r["startup_gap_sec"])
        self.assertEqual("unavailable", r["startup_gap_source"])

    def _measure_with_story(self, story_text: str) -> dict:
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            (run / "events.jsonl").write_text(
                "\n".join(json.dumps(r, ensure_ascii=False)
                          for r in _events(_harness(GATE_PASS))),
                encoding="utf-8")
            work = run / "work" / "AR"
            work.mkdir(parents=True)
            (work / "story.md").write_text(story_text, encoding="utf-8")
            return measure_run.measure(run / "events.jsonl", run_dir=run)

    def test_diagrams_are_counted_per_chapter(self):
        """图数得出来，而且分得清流程章有没有。"""
        r = self._measure_with_story(
            "# AR90001\n\n## 业务流程\n\n```mermaid\nflowchart TD\n  A --> B\n```\n\n"
            "## 功能说明\n\n```mermaid\nstateDiagram\n  s1 --> s2\n```\n")
        self.assertEqual(2, r["diagrams_total"])
        self.assertEqual(1, r["diagrams_in_flow_chapter"])

    def test_a_flow_chapter_without_a_diagram_shows_zero(self):
        """流程章一张图都没有时它是零，不是「没测」——那正是连着几跑的形态。"""
        r = self._measure_with_story(
            "# AR90001\n\n## 业务流程\n\n主路径：进入 → 提交 → 结果。\n\n"
            "## 功能说明\n\n```mermaid\nstateDiagram\n  s1 --> s2\n```\n")
        self.assertEqual(1, r["diagrams_total"])
        self.assertEqual(0, r["diagrams_in_flow_chapter"])

    def test_no_story_means_unknown_not_zero(self):
        """没有产物时不报零——「没画图」与「没产物」是两件事。"""
        r = self._measure([_harness(GATE_PASS)])
        self.assertIsNone(r["diagrams_total"])

    def test_human_wait_unknown_is_not_zero(self):
        """没记录人工等待时报 None：0 会被当成「这轮没人等过」，那是编数。"""
        r = self._measure([_harness(GATE_PASS)])
        self.assertIsNone(r["human_wait_sec"])
        self.assertIn(r["human_wait_source"], {"unavailable", "not_recorded"})

    def test_human_wait_comes_from_the_driver(self):
        """驱动器记了就照实报，并与模型耗时分开——混进总墙钟就分不出「没人回话」。"""
        r = self._measure([_harness(GATE_PASS)],
                          state={"human_wait_sec": 930.0, "human_wait_events": 2})
        self.assertEqual(930.0, r["human_wait_sec"])
        self.assertEqual(2, r["human_wait_events"])
        self.assertEqual("run_state", r["human_wait_source"])

    def test_time_is_split_by_what_was_running(self):
        """门禁 / 子任务 / 成文 分开归属——只报总墙钟看不出时间花在哪。Story 自己的检查命令也算门禁。"""
        r = self._measure([
            {"tool_name": "write", "tool_input": {"filePath": "a.md"}},
            _harness(GATE_FAIL),
            {"tool_name": "task", "tool_input": {"subagent_type": "verifier"}},
            _story_review("fail"),
        ])
        gaps = r["gap_sec_by_kind"]
        self.assertGreater(gaps["gate"], 60, "story-build review --action check 没算进门禁")
        self.assertGreater(gaps["task"], 0)


class SubtaskRolesAreInferredFromStructure(unittest.TestCase):
    """子任务保留说明、子代理类型与引用的文件；角色只按引用的任务文件或子代理类型推断，提示词里提到某个动作不算依据。"""

    CASES = {
        "审查任务里提到格式问题重给": ({"description": "独立审查 N Story",
                                    "prompt": "按 `doc/features/N/AR/story-src/review/task.md` 逐字执行；报告格式问题由审查者重给"},
                                   "reader_review"),
        "作者任务里提到质询": ({"description": "写蓝图候选",
                             "prompt": "独立质询由主执行者派遣，你只完成作者工作：写 doc/features/bp-N/blueprint/component-blueprint.yaml"},
                            "unknown"),
        "只查路径的任务": ({"description": "看看文件在不在", "prompt": "列出 doc/features/N/AR/story.md 是否存在"}, "unknown"),
        "正常的人读审查": ({"description": "审查", "prompt": "任务文件 doc/features/N/AR/story-src/review/task.md，材料键 k"},
                         "reader_review"),
        "原生阶段 verifier": ({"subagent_type": "verifier", "prompt": "审 spec 阶段产物"}, "stage_verifier"),
        "蓝图质询": ({"description": "质询", "prompt": "回复写到 doc/features/bp-N/blueprint/questioning/k/reply.md"},
                   "design_questioning"),
        "依据指向两种角色": ({"prompt": "doc/features/N/AR/story-src/review/task.md 与 doc/features/bp-N/blueprint/questioning/k/reply.md"},
                          "unknown"),
    }

    def test_each_call_keeps_its_facts_and_an_inferred_role(self) -> None:
        for label, (tool_input, role) in self.CASES.items():
            with self.subTest(case=label):
                call = measure_run.task_call({"tool_name": "task", "tool_input": tool_input})
                self.assertEqual(role, call["inferred_role"], call)
                self.assertEqual(tool_input.get("description", ""), call["description"])
                self.assertTrue(call["inferred_from"])

    def test_the_run_lists_every_call_with_its_basis(self) -> None:
        records = [{"tool_name": "task", "tool_input": t} for t, _ in self.CASES.values()]
        r = MeasureReadsRealEvents._measure(MeasureReadsRealEvents(), records)
        self.assertEqual(len(self.CASES), len(r["tasks"]))
        self.assertEqual(sorted(role for _, role in self.CASES.values()), sorted(t["inferred_role"] for t in r["tasks"]))
        refs = next(t["refs"] for t in r["tasks"] if t["description"] == "看看文件在不在")
        self.assertEqual(["doc/features/N/AR/story.md"], refs)
        self.assertIn("unknown", r["task_gap_sec_inferred"])


def _story_review(result: str | None, *, feature: str = "N", order: str = "action-first") -> dict:
    """一次 `story-build review --action check`；result 为 None 时输出里没有结构化结论。"""
    args = (f"review --action check --feature {feature}" if order == "action-first"
            else f"review --feature {feature} --action check")
    out = "" if result is None else json.dumps({"result": result, "detail": "…"}, ensure_ascii=False)
    return {"tool_name": "bash", "tool_input": {"command": f"node doc/extensions/skills/story/scripts/core/story-build.mjs {args}"},
            "tool_output": out}


class StoryGatesCountFailuresAndRework(unittest.TestCase):
    """Story 门禁与原生门禁同一份计算：失败轮次、首次门禁、返工，参数换序结果相同，读不到结论记未知。"""

    def measure(self, *records) -> dict:
        return MeasureReadsRealEvents._measure(MeasureReadsRealEvents(), list(records))

    def test_a_failed_review_then_a_pass_on_the_same_object_is_rework(self) -> None:
        r = self.measure(_story_review("fail"), _story_review("pass"))
        seg = r["segments"]["whole"]
        self.assertEqual(1, r["gate_rounds_with_fail"])
        self.assertEqual({"action": "story_review", "object": "N", "outcome": "fail", "fail_count": 1}, seg["first_gate"])
        self.assertEqual(1.0, seg["rework_min"])
        self.assertEqual([], seg["rework_open"])

    def test_a_first_pass_has_no_rework(self) -> None:
        seg = self.measure(_story_review("warn"))["segments"]["whole"]
        self.assertEqual("pass", seg["first_gate"]["outcome"])
        self.assertEqual((0, 0.0), (seg["gate_rounds_with_fail"], seg["rework_min"]))

    def test_argument_order_does_not_change_the_result(self) -> None:
        a = self.measure(_story_review("fail"), _story_review("pass"))
        b = self.measure(_story_review("fail", order="feature-first"), _story_review("pass", order="feature-first"))
        for key in ("gate_rounds_with_fail", "gap_sec_by_kind"):
            self.assertEqual(a[key], b[key], key)
        self.assertEqual(a["segments"]["whole"]["rework_min"], b["segments"]["whole"]["rework_min"])

    def test_an_unreadable_result_is_unknown_not_zero_failures(self) -> None:
        r = self.measure(_story_review(None))
        seg = r["segments"]["whole"]
        self.assertEqual(1, r["gate_rounds_unknown"])
        self.assertEqual("unknown", seg["first_gate"]["outcome"])
        self.assertEqual(0, r["gate_rounds_with_fail"])

    def test_interleaved_objects_are_reworked_separately(self) -> None:
        r = self.measure(_story_review("fail", feature="A"), _story_review("fail", feature="B"),
                         _story_review("pass", feature="A"), _story_review("subject_stale", feature="B"))
        seg = r["segments"]["whole"]
        self.assertEqual(3, r["gate_rounds_with_fail"])
        self.assertEqual(2.0, seg["rework_min"], "A 从 10:00 到 10:02")
        self.assertEqual(["story_review@B"], seg["rework_open"])

    def test_check_and_registration_read_their_own_conclusions(self) -> None:
        check = {"tool_name": "bash", "tool_input": {"command": "node x/story-build.mjs check --feature N"},
                 "tool_output": "[story-build check] 3 处未通过，分属 1 类"}
        passed = {**check, "tool_output": "[story-build check] 通过：10 章"}
        register = {"tool_name": "bash", "tool_input": {"command": "python x/story_flow.py story --feature N"},
                    "tool_output": json.dumps({"success": False, "error": "审查结果 fail"}, ensure_ascii=False)}
        r = self.measure(check, passed, register)
        seg = r["segments"]["whole"]
        self.assertEqual({"action": "story_check", "object": "N", "outcome": "fail", "fail_count": 3}, seg["first_gate"])
        self.assertEqual("fail", seg["first_story_register"]["outcome"])
        self.assertEqual(2, r["gate_rounds_with_fail"])
        self.assertEqual(["story_register@N"], seg["rework_open"])


    def test_reading_a_gate_script_is_not_a_gate(self) -> None:
        """脚本名只出现在读取里（cat 源码）不是一轮门禁：不计次数、不计门禁时间、不记未知。"""
        r = self.measure(
            {"tool_name": "bash", "tool_input": {"command": "cat framework/harness/harness-runner.ts"}, "tool_output": ""},
            {"tool_name": "bash", "tool_input": {"command": "cat doc/extensions/skills/story/scripts/core/story-build.mjs check --feature A"},
             "tool_output": ""})
        self.assertEqual((0, 0, 0), (r["harness_runs"], r["gate_rounds_unknown"], len(r["gate_calls_unattributed"])))
        self.assertEqual(0, r["gap_sec_by_kind"]["gate"])
        self.assertIsNone(r["segments"]["whole"]["first_gate"])

    def test_a_combined_output_of_two_gates_is_unattributed(self) -> None:
        """一次调用先后执行 A、B 两个审查核对，合并输出 fail 又 pass：归属不了，A 不记成通过，单列成一次调用。"""
        both = {"tool_name": "bash", "tool_input": {"command":
                "node x/story-build.mjs review --action check --feature A; node x/story-build.mjs review --action check --feature B"},
                "tool_output": '{"result": "fail"}\n{"result": "pass"}'}
        r = self.measure(both)
        seg = r["segments"]["whole"]
        self.assertEqual((0, 0), (r["gate_rounds_with_fail"], r["gate_rounds_unknown"]))
        self.assertEqual([{"seq": 0, "candidates": ["story_review@A", "story_review@B"], "reason": "一次执行了多个门禁"}],
                         r["gate_calls_unattributed"])
        self.assertIsNone(seg["first_gate"])

    def test_an_unattributed_call_does_not_close_rework(self) -> None:
        """A 单独失败之后，一次合并执行 A、B 输出 pass：归属不了，不结束 A 的返工。"""
        both = {"tool_name": "bash", "tool_input": {"command":
                "node x/story-build.mjs review --action check --feature A && node x/story-build.mjs review --action check --feature B"},
                "tool_output": '{"result": "pass"}\n{"result": "pass"}'}
        seg = self.measure(_story_review("fail", feature="A"), both)["segments"]["whole"]
        self.assertEqual(["story_review@A"], seg["rework_open"])
        self.assertEqual(0.0, seg["rework_min"])
        self.assertEqual(1, len(seg["gate_calls_unattributed"]))


    def test_another_output_source_after_the_gate_is_unattributed(self) -> None:
        """单个门禁后面又读了别的报告：输出不能可靠归给本次门禁，不覆盖已有的 fail，也不结束返工。"""
        mixed = {"tool_name": "bash", "tool_input": {"command":
                 "node x/story-build.mjs review --action check --feature A; cat saved-report.json"},
                 "tool_output": '{"result": "fail"}\n{"result": "pass"}'}
        r = self.measure(_story_review("fail", feature="A"), mixed)
        seg = r["segments"]["whole"]
        self.assertEqual(1, r["gate_rounds_with_fail"], "混合输出被算成了一轮")
        self.assertEqual(["story_review@A"], seg["rework_open"])
        [call] = r["gate_calls_unattributed"]
        self.assertEqual(["story_review@A"], call["candidates"])
        self.assertIn("门禁之外还有输出来源", call["reason"])

    def test_contradicting_conclusions_in_one_output_are_unattributed(self) -> None:
        """只执行一个门禁、输出里却有互相矛盾的结论：不挑一个当结论。"""
        for name, record in {
            "审查核对": {"tool_name": "bash", "tool_input": {"command": "node x/story-build.mjs review --action check --feature A"},
                     "tool_output": '{"result": "fail"}\n{"result": "pass"}'},
            "成文登记": {"tool_name": "bash", "tool_input": {"command": "python x/story_flow.py story --feature A"},
                     "tool_output": '{"success": false}\n{"success": true}'},
            "结构检查": {"tool_name": "bash", "tool_input": {"command": "node x/story-build.mjs check --feature A"},
                     "tool_output": "[story-build check] 2 处未通过\n[story-build check] 通过：10 章"},
            "原生门禁": _harness(GATE_FAIL + GATE_PASS),
        }.items():
            with self.subTest(gate=name):
                r = self.measure(record)
                self.assertEqual((0, 0), (r["gate_rounds_with_fail"], r["gate_rounds_unknown"]))
                self.assertEqual(1, len(r["gate_calls_unattributed"]))

    def test_cutting_the_gate_output_keeps_the_attribution(self) -> None:
        """前面切目录、后面经管道截取门禁自己的输出：仍归给这一次门禁。"""
        cut = {"tool_name": "bash", "tool_input": {"command":
               "cd work && node x/story-build.mjs review --feature A --action check 2>&1 | tail -5"},
               "tool_output": '{"result": "fail"}'}
        r = self.measure(cut)
        self.assertEqual(1, r["gate_rounds_with_fail"])
        self.assertEqual([], r["gate_calls_unattributed"])


class EachSegmentIsMeasured(unittest.TestCase):
    """双检查点单按续跑那一刻切两段，各报时长、模型与工具时间、各类子任务、首次门禁与登记、返工。"""

    def test_the_two_segments_carry_their_own_fields(self):
        records = [
            {"type": "usage", "usage": {"context_total": 10}},
            _harness(GATE_FAIL),
            {"tool_name": "task", "tool_input": {"subagent_type": "verifier"}},
            _harness(GATE_PASS),
            {"tool_name": "bash", "tool_input": {"command": "python story_flow.py story --feature X"},
             "tool_output": '{"success": false, "error": "结构检查没过"}'},
            {"tool_name": "bash", "tool_input": {"command": "python story_flow.py story --feature X"},
             "tool_output": '{"success": true, "registered": true}'},
        ]
        events = _events(*records)
        for e in events:
            e["timestamp"] += "+00:00"
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            (run / "events.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in events),
                                             encoding="utf-8")
            (run / "state.json").write_text(json.dumps({"resumed_at": "2026-09-02T10:04:00+00:00"}), encoding="utf-8")
            r = measure_run.measure(run / "events.jsonl", run_dir=run)
        first, second = r["segments"]["initial"], r["segments"]["update"]
        self.assertEqual({"action": "harness:spec", "object": "?", "outcome": "fail", "fail_count": 2}, first["first_gate"])
        self.assertEqual(1, first["task_runs_inferred"]["stage_verifier"])
        self.assertEqual(2.0, first["rework_min"], "门禁 10:01 没过、10:03 通过")
        self.assertEqual({"action": "story_register", "object": "X", "outcome": "fail", "fail_count": 1},
                         second["first_story_register"])
        self.assertEqual(1.0, second["rework_min"])
        for key in ("duration_min", "model_gap_sec", "tool_gap_sec", "task_runs_inferred", "task_gap_sec_inferred"):
            self.assertIn(key, second)
        self.assertEqual(r["gate_rounds_with_fail"], first["gate_rounds_with_fail"] + second["gate_rounds_with_fail"],
                         "全程与分段的失败轮次不一致")


class PhaseAdvancesOnlyOnEvidence(unittest.TestCase):
    """P10：目标阶段、runner 提示、准备执行 gate 都不能把阶段抬上去。"""

    def setUp(self) -> None:
        self.ws = Path(tempfile.mkdtemp())
        self.feature = "demo-feature"

    def _state(self) -> dict:
        return {"feature": self.feature, "requested_start_phase": "story",
                "current_phase": "story", "last_phase": "story"}

    def _write_framework_phase(self, phase: str) -> None:
        p = self.ws / "framework/harness/state/.current-phase.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"phase": phase, "feature": self.feature,
                                 "updated_at": "2026-09-02T10:00:00Z"}), encoding="utf-8")

    def test_target_phase_alone_does_not_advance(self):
        """只有「本轮目标是 plan」这一个事实时，阶段仍是 story。

        实测反例：驱动器在 `gates_started` 把终点当观测阶段写进状态，
        于是两个 Case 在没有任何 plan 产物时被报成到达 plan。
        """
        state = self._state()
        state["phase_intent"] = {"phase": "plan", "event": "gates_started"}
        result = phase_state.derive_phase_state(self.ws, self.feature, state)
        self.assertEqual("story", result["current_phase"])
        self.assertEqual("story", result["highest_phase_reached"])

    def test_native_observation_advances(self):
        """正样本：原生终点观测里施工单位的 spec 还没闭环 → 阶段是 spec。"""
        state = {**self._state(), "closure": {"end_at": "phase:plan", "units": [
            {"design": "constructable", "phases": {"spec": {"state": "open"}, "plan": {"state": "open"}}}]}}
        result = phase_state.derive_phase_state(self.ws, self.feature, state)
        self.assertEqual("spec", result["current_phase"])
        self.assertEqual("flow_and_native_observation", result["phase_source"])

    def test_the_slot_or_a_phase_directory_alone_does_not_advance(self):
        """反样本：全局阶段槽写着 spec、需求目录下出现 spec/，都不是阶段证据。"""
        self._write_framework_phase("spec")
        art = self.ws / "doc/features" / self.feature / "spec" / "spec.md"
        art.parent.mkdir(parents=True)
        art.write_text("# spec", encoding="utf-8")
        result = phase_state.derive_phase_state(self.ws, self.feature, self._state())
        self.assertEqual("story", result["highest_phase_reached"])

    def test_reports_dir_alone_is_not_an_artifact(self):
        """反样本：只有 reports/ 不算到达——门禁跑过不等于阶段产物有了。"""
        (self.ws / "doc/features" / self.feature / "plan" / "reports").mkdir(parents=True)
        result = phase_state.derive_phase_state(self.ws, self.feature, self._state())
        self.assertEqual("story", result["highest_phase_reached"])

    def test_runner_never_writes_phase_from_a_hint(self):
        """驱动器里不许再有「把提示写成阶段」的那条路径。"""
        source = (SCRIPTS / "run_case.py").read_text(encoding="utf-8")
        self.assertNotIn('state["phase_source"] = "runner_hint"', source)
        self.assertIn('state["phase_intent"]', source, "提示仍要留痕，只是不当证据")


class MaterialVersionSeesSupplements(unittest.TestCase):
    """只补图片算不算新材料版本 —— 图片进来的两条路都要算。"""

    def _root(self) -> Path:
        d = Path(tempfile.mkdtemp())
        (d / "RR").mkdir()
        (d / "RR" / "prd.md").write_text("正文一字不改", encoding="utf-8")
        return d

    def _fingerprint(self, root: Path) -> str:
        return registry.compute_digest(registry.collect_materials(root))

    def test_text_change_changes_the_version(self):
        """基线正样本：正文变了必须换版本，否则这个指纹什么都证明不了。"""
        root = self._root()
        before = self._fingerprint(root)
        (root / "RR" / "prd.md").write_text("正文改了", encoding="utf-8")
        self.assertNotEqual(before, self._fingerprint(root))

    def test_ui_reference_image_changes_the_version(self):
        """界面参考目录里加一张图 → 材料变了（现行机制已覆盖这条路）。"""
        root = self._root()
        before = self._fingerprint(root)
        (root / "ux-reference").mkdir()
        (root / "ux-reference" / "flow.png").write_bytes(b"PNG")
        self.assertNotEqual(before, self._fingerprint(root))

    def test_docx_embedded_image_supplement_changes_the_version(self):
        """文档内嵌图落 `assets/`，材料版本必须看见它。

        按 test/cases/README.md，图片进来只有一条路：人给的 docx 里内嵌，导入时抽出来落
        `<feature>/assets/<源文档名>/`；判为界面图的再从那里复制一份进 `ux-reference/`。
        材料版本一度只覆盖四份文本与 `ux-reference/`——于是「补了一份只多几张图的文档」
        对轮次完全隐形：既不换轮次，也没有任何信号说材料变过。
        """
        root = self._root()
        (root / "assets" / "supp").mkdir(parents=True)
        (root / "assets" / "supp" / "image1.png").write_bytes(b"PNG1")
        before = self._fingerprint(root)
        (root / "assets" / "supp" / "image2.png").write_bytes(b"PNG2")
        self.assertNotEqual(before, self._fingerprint(root),
                            "只补图片没有形成新材料版本")

    def test_the_same_image_in_two_places_is_one_material(self):
        """同一张图复制到第二个落点是同一张图，不是两张。

        界面图按规则要从内嵌位置复制一份到 `ux-reference/` 起语义名。两处各登记一条时，
        下游看到的是两张一模一样的图，于是要么重复引用、要么各引各的。
        """
        root = self._root()
        (root / "assets" / "supp").mkdir(parents=True)
        (root / "assets" / "supp" / "image1.png").write_bytes(b"PNG1")
        (root / "ux-reference").mkdir()
        (root / "ux-reference" / "签约页.png").write_bytes(b"PNG1")
        images = [m for m in registry.collect_materials(root) if m["kind"] == "image"]
        self.assertEqual(1, len(images), "同一张图被登记成了两张")
        self.assertEqual(["assets/supp/image1.png", "ux-reference/签约页.png"],
                         images[0]["paths"], "两个落点没有都记下来")


class ProcessArtifactsEnterTheIndex(unittest.TestCase):
    """过程件入库（用户 2026-09-25 裁定）：spec 与 plan 各版本的方案、评审与交回都随提交留下历史；
    实跑的运行证据（事件流、运行日志、截图、材料原件、压缩包）放在 `output/story/`，不进过程件目录。
    """

    ROOTS = ("doc/spec", "doc/plan", "docs/archive/legacy-2.x/spec", "docs/archive/legacy-2.x/plan")
    EVIDENCE_SUFFIXES = {".jsonl", ".log", ".zip", ".docx", ".png"}

    def test_process_roots_are_on_disk_and_not_ignored(self):
        for rel in self.ROOTS:
            with self.subTest(root=rel):
                self.assertTrue((REPO / rel).is_dir(), f"{rel} 不在盘上")
                ignored = subprocess.run(["git", "check-ignore", "-q", f"{rel}/1.9.0/00-总览.md"],
                                         cwd=str(REPO)).returncode == 0
                self.assertFalse(ignored, f"{rel} 被忽略了")

    #: 已授权保留的历史原稿：迁移清单按确切路径与原始字节摘要登记，登记在内且字节没变的原件不是新的运行证据
    HISTORY_MANIFEST = "docs/archive/legacy-2.x/spec/2.1.0/历史参考/迁移清单.json"
    #: 金样候选的登记位置（2.0.3 的 05 合同 §2：`实施反馈/金样候选/<case>/<情景>/`）。目标稿自带的配图在情景的
    #: `assets/` 下、被本情景文档引用、且是产品支持的图片类型（`materials.frozen.IMAGE_SUFFIXES`）；
    #: 日志、事件、原件附件与压缩包被引用也不算。图里画的是否适用于该情景由评审者核，这里不看字节
    CANDIDATE_ROOTS = ("doc/plan/*/*/实施反馈/金样候选",
                       "docs/archive/legacy-2.x/plan/*/*/实施反馈/金样候选")

    @classmethod
    def candidate_assets(cls, repo: Path) -> set[str]:
        """各候选情景文档实际引用、落在本情景 assets/ 下的图片。"""
        link = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
        out: set[str] = set()
        for root in (root for pattern in cls.CANDIDATE_ROOTS for root in repo.glob(pattern)):
            for scene in (s for s in root.glob("*/*") if s.is_dir()):
                assets = (scene / "assets").resolve()
                for doc in scene.rglob("*.md"):
                    for target in link.findall(doc.read_text(encoding="utf-8")):
                        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
                            continue
                        f = (doc.parent / unquote(target)).resolve()
                        if f.is_file() and assets in f.parents and f.suffix.lower() in frozen.IMAGE_SUFFIXES:
                            out.add(f.relative_to(repo.resolve()).as_posix())
        return out

    @classmethod
    def stray_evidence(cls, repo: Path) -> list[str]:
        kept: dict[str, str] = {}
        manifest = repo / cls.HISTORY_MANIFEST
        if manifest.is_file():
            data = json.loads(manifest.read_text(encoding="utf-8"))
            kept = {f"{data['destination_root']}/{f['path']}": f["sha256"] for f in data["files"]}
        candidate = cls.candidate_assets(repo)
        out = []
        for rel in cls.ROOTS:
            for p in (repo / rel).rglob("*"):
                if not p.is_file() or not (p.suffix in cls.EVIDENCE_SUFFIXES or p.name == "runlog.md"):
                    continue
                path = p.relative_to(repo).as_posix()
                if kept.get(path) == hashlib.sha256(p.read_bytes()).hexdigest() or path in candidate:
                    continue
                out.append(path)
        return out

    def test_run_evidence_lives_under_output(self):
        self.assertEqual([], self.stray_evidence(REPO), "运行证据放到 output/story/ 下")

    def test_only_listed_unchanged_history_originals_are_kept(self):
        """清单内且字节没变的原件放过；新增的图片、字节被改的原件照样算运行证据。"""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            history = repo / "docs/archive/legacy-2.x/spec/2.1.0/历史参考"
            original = history / "原1.9.9/data/a.png"
            original.parent.mkdir(parents=True)
            original.write_bytes(b"original")
            (repo / "doc/plan").mkdir(parents=True)
            (history / "迁移清单.json").write_text(json.dumps({
                "destination_root": "docs/archive/legacy-2.x/spec/2.1.0/历史参考/原1.9.9",
                "files": [{"path": "data/a.png", "sha256": hashlib.sha256(b"original").hexdigest()}]}),
                encoding="utf-8")
            self.assertEqual([], self.stray_evidence(repo))
            (history / "原1.9.9/data/b.png").write_bytes(b"new")
            (repo / "doc/plan/run.log").write_text("x", encoding="utf-8")
            self.assertEqual({"docs/archive/legacy-2.x/spec/2.1.0/历史参考/原1.9.9/data/b.png", "doc/plan/run.log"},
                             set(self.stray_evidence(repo)))
            original.write_bytes(b"edited")
            self.assertIn("docs/archive/legacy-2.x/spec/2.1.0/历史参考/原1.9.9/data/a.png", self.stray_evidence(repo))

    def test_candidate_assets_are_recognised_by_place_and_reference(self):
        """候选情景 assets/ 下、被本情景文档引用的配图是目标稿的一部分，新画的也算；
        引用不到的、放在候选范围外的（哪怕与已审原图同字节）、运行截图，都还是运行证据。"""
        for base in ("doc/plan/2.0.0/设计/实施反馈/",
                     "docs/archive/legacy-2.x/plan/2.0.3/设计/实施反馈/"):
            with self.subTest(base=base), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp)
                (repo / "doc/spec").mkdir(parents=True)
                scene = repo / base / "金样候选/demo-case/initial"
                (scene / "AR").mkdir(parents=True)
                (scene / "assets/页面").mkdir(parents=True)
                (scene / "assets/页面/新画的图.png").write_bytes(b"brand-new")
                (scene / "AR/story.md").write_text("![提交页](../assets/%E9%A1%B5%E9%9D%A2/新画的图.png)\n",
                                                   encoding="utf-8")
                self.assertEqual([], self.stray_evidence(repo), "被引用的新候选配图不是运行证据")

                (scene / "assets/页面/没人引用.png").write_bytes(b"x")
                (scene / "AR/截图.png").write_bytes(b"shot")
                (scene / "AR/run.log").write_text("x", encoding="utf-8")
                elsewhere = repo / base / "别处/assets/新画的图.png"
                elsewhere.parent.mkdir(parents=True)
                elsewhere.write_bytes(b"brand-new")
                (elsewhere.parent.parent / "说明.md").write_text("![图](assets/新画的图.png)\n", encoding="utf-8")
                self.assertEqual({base + "金样候选/demo-case/initial/assets/页面/没人引用.png",
                                  base + "金样候选/demo-case/initial/AR/截图.png",
                                  base + "金样候选/demo-case/initial/AR/run.log",
                                  base + "别处/assets/新画的图.png"},
                                 set(self.stray_evidence(repo)))

                # 文档引用了 assets/ 外的文件也不放行：引用不是放行理由，位置与引用要同时成立
                (scene / "AR/story.md").write_text("![截图](截图.png)\n", encoding="utf-8")
                self.assertIn(base + "金样候选/demo-case/initial/AR/截图.png", self.stray_evidence(repo))

                # 放在 assets/ 里、被正文链接的日志、原件与压缩包也不放行：例外只给图片
                for name in ("run.log", "原稿.docx", "包.zip", "events.jsonl"):
                    (scene / "assets" / name).write_text("x", encoding="utf-8")
                (scene / "AR/story.md").write_text(
                    "![提交页](../assets/%E9%A1%B5%E9%9D%A2/新画的图.png)\n\n"
                    + "".join(f"[{n}](../assets/{n})\n" for n in ("run.log", "原稿.docx", "包.zip", "events.jsonl")),
                    encoding="utf-8")
                stray = set(self.stray_evidence(repo))
                for name in ("run.log", "原稿.docx", "包.zip", "events.jsonl"):
                    self.assertIn(base + f"金样候选/demo-case/initial/assets/{name}", stray, name)
                self.assertNotIn(base + "金样候选/demo-case/initial/assets/页面/新画的图.png", stray)

    def test_golden_output_has_a_single_canonical_copy(self):
        """金样成品只有 `test/golden/` 一处正本；夹具里出现逐字节副本，改了哪一份、对照的又是哪一份就说不清。"""
        golden = REPO / "test/golden"
        for canonical in ("assets/image1.png", "assets/image2.png",
                          "story-金样-AR90004.md", "review-金样-AR90006.md"):
            self.assertTrue((golden / canonical).exists(), f"金样正本缺 {canonical}")

        canon = {p.read_bytes() for p in golden.rglob("*.md")}
        strays = [p.relative_to(REPO).as_posix() for p in (REPO / "test/fixtures").rglob("*.md")
                  if p.read_bytes() in canon]
        self.assertEqual([], strays, f"夹具里出现了金样成品副本：{strays}")


if __name__ == "__main__":
    unittest.main()
