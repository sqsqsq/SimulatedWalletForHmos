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
from dataclasses import asdict
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml
from pathlib import Path, PureWindowsPath
from urllib.parse import unquote
from ext_workspace import DEV_EXT

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "test" / "scripts"
STORY_SCRIPTS = DEV_EXT / "skills" / "story" / "scripts" / "core"

sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(STORY_SCRIPTS))
from materials import importer, registry  # noqa: E402
import measure_run  # noqa: E402
sys.path.insert(0, str(REPO))
from tools.cli.adapters import get_adapter  # noqa: E402
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
            "tool_input": {"filePath": "doc/extensions/hooks/shared/knowledge-use.mjs"},
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
                           "node doc/extensions/skills/story/scripts/core/story-build.mjs check "
                           "--feature X | tail -20"},
            "tool_output": "[story-build check] 通过",
        }])
        self.assertEqual(0, r["reads_checker_source"])
        self.assertEqual(0, r["reads_rule_text"])
        self.assertEqual(1, r["bash_rule_path_not_read"], "执行判据脚本要记成未分类，看得见")
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
        """门禁 / verifier / 成文 分开归属——只报总墙钟看不出时间花在哪。"""
        r = self._measure([
            {"tool_name": "write", "tool_input": {"filePath": "a.md"}},
            _harness(GATE_FAIL),
            {"tool_name": "task", "tool_input": {"subagent_type": "verifier"}},
        ])
        gaps = r["gap_sec_by_kind"]
        self.assertGreater(gaps["gate"], 0)
        self.assertGreater(gaps["verifier"], 0)


class EachSegmentIsMeasured(unittest.TestCase):
    """双检查点单按续跑那一刻切两段，各报时长、模型与工具时间、verifier、首次门禁与登记、返工。"""

    def test_the_two_segments_carry_their_own_fields(self):
        records = [
            {"type": "usage", "usage": {"context_total": 10}},
            _harness(GATE_FAIL),
            {"tool_name": "task", "tool_input": {"subagent_type": "verifier"}},
            _harness(GATE_PASS),
            {"tool_name": "bash", "tool_input": {"command": "python story_flow.py story --feature X"},
             "tool_output": "[story-build check] 2 处未通过"},
            {"tool_name": "bash", "tool_input": {"command": "python story_flow.py story --feature X"},
             "tool_output": "登记成文"},
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
        self.assertEqual({"fail_count": 2, "status": "completed"}, first["first_harness"])
        self.assertEqual(1, first["verifier_runs"])
        self.assertEqual(2.0, first["rework_min"], "门禁 10:01 没过、10:03 通过")
        self.assertEqual({"fail_count": 1, "status": "completed"}, second["first_story_register"])
        self.assertEqual(1.0, second["rework_min"])
        for key in ("duration_min", "nontool_gap_sec", "tool_gap_sec", "tool_interval_sec",
                    "verifier_gap_sec"):
            self.assertIn(key, second)
        self.assertNotIn("model_gap_sec", second, "非工具事件间隔不能叫模型耗时：它含等待与空档")


def _public_events(provider: str, runs: list[tuple[str, list[dict]]], *, minute: int = 0) -> list[dict]:
    """宿主原始事件经**当前中央 adapter** 投影成公共事件，再加 runner 写进 events.jsonl 的 run_id 与时刻。"""
    adapter = get_adapter(provider)
    out = []
    for run_id, raws in runs:
        for raw in raws:
            for event in adapter.parse(raw):
                record = asdict(event)
                record.update(run_id=run_id, timestamp=f"2026-10-20T10:{minute:02d}:00+00:00")
                out.append(record)
                minute += 1
    return out


def _dsh_call(call_id: str, tool: str, **tool_input) -> dict:
    return {"type": "tool_call", "callId": call_id, "tool": tool, "input": tool_input}


def _dsh_result(call_id: str, result: str, status: str = "completed") -> dict:
    return {"type": "tool_result", "callId": call_id, "status": status, "result": result}


HARNESS_PWSH = "cd framework/harness; npx ts-node harness-runner.ts --phase spec --feature SAMPLE"


class ToolCallsArePairedFromPublicEvents(unittest.TestCase):
    """开始与结果两条事件是一次调用：按 run 与调用编号配，不按条数、相邻行或工具名。"""

    def _measure(self, events: list[dict], *, state: dict | None = None) -> dict:
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            (run / "events.jsonl").write_text(
                "\n".join(json.dumps(e, ensure_ascii=False) for e in events), encoding="utf-8")
            if state is not None:
                (run / "state.json").write_text(json.dumps(state), encoding="utf-8")
            return measure_run.measure(run / "events.jsonl", run_dir=run)

    def test_pwsh_reads_harness_and_the_verifier_tool_are_recognised_once_each(self):
        r = self._measure(_public_events("dsh", [("run-a", [
            _dsh_call("r", "pwsh", command="Get-Content framework/harness/scripts/check-spec.ts"),
            _dsh_result("r", "file contents"),
            _dsh_call("h", "pwsh", command=HARNESS_PWSH),
            _dsh_result("h", "  FAIL [BLOCKER] sample_rule"),
            _dsh_call("v", "verifier", description="阶段独立审查", prompt="{}"),
            _dsh_result("v", "review report"),
            _dsh_call("s", "subagent", description="研究工程", prompt="读源码"),
            _dsh_result("s", "started subagent child-1"),
        ])]))
        self.assertEqual(4, r["tool_calls"], "四次调用，八条事件")
        self.assertEqual({"pwsh": 2, "verifier": 1, "subagent": 1}, dict(r["tools"]))
        self.assertEqual((1, 1, 1), (r["reads_rule_text"], r["reads_checker_source"], r["harness_runs"]))
        self.assertEqual([["sample_rule", 1]], [list(x) for x in r["repeated_check_fails"]])
        whole = r["segments"]["whole"]
        self.assertEqual({"fail_count": 1, "status": "completed"}, whole["first_harness"])
        self.assertEqual((1, 1), (whole["verifier_runs"], whole["delegations_unresolved"]),
                         "普通 subagent 研究不是审查")
        self.assertEqual([], r["incomplete_tool_events"])

    def test_interleaved_calls_pair_by_id_and_outcomes_follow_arrival(self):
        r = self._measure(_public_events("dsh", [("run-a", [
            _dsh_call("h1", "pwsh", command=HARNESS_PWSH),
            _dsh_call("h2", "pwsh", command=HARNESS_PWSH),
            _dsh_result("h2", GATE_PASS),
            _dsh_result("h1", GATE_FAIL),
        ])]))
        self.assertEqual((2, 2, 1), (r["tool_calls"], r["harness_runs"], r["gate_rounds_with_fail"]))
        self.assertEqual({"fail_count": 0, "status": "completed"}, r["segments"]["whole"]["first_harness"],
                         "先到的结果是 h2 的全绿")

    def test_a_call_id_reused_by_another_run_is_another_call(self):
        events = _public_events("dsh", [
            ("run-a", [_dsh_call("c1", "pwsh", command=HARNESS_PWSH), _dsh_result("c1", GATE_FAIL)]),
            ("run-b", [_dsh_call("c1", "pwsh", command=HARNESS_PWSH), _dsh_result("c1", GATE_PASS)]),
        ])
        r = self._measure(events)
        self.assertEqual((2, 2, 1), (r["tool_calls"], r["harness_runs"], r["gate_rounds_with_fail"]))
        self.assertEqual(2.0, r["segments"]["whole"]["rework_min"], "run-a 10:01 没过、run-b 10:03 通过")

    def test_an_error_result_is_not_a_pass(self):
        r = self._measure(_public_events("dsh", [("run-a", [
            _dsh_call("h1", "pwsh", command=HARNESS_PWSH),
            _dsh_result("h1", "Error: harness crashed", status="error"),
            _dsh_call("h2", "pwsh", command=HARNESS_PWSH),
            _dsh_result("h2", GATE_PASS),
        ])]))
        whole = r["segments"]["whole"]
        self.assertEqual({"fail_count": 0, "status": "error"}, whole["first_harness"])
        self.assertEqual(2.0, whole["rework_min"], "报错那轮到全绿那轮是返工")

    def test_reading_a_failed_report_again_is_not_another_gate_round(self):
        r = self._measure(_public_events("dsh", [("run-a", [
            _dsh_call("h", "pwsh", command=HARNESS_PWSH),
            _dsh_result("h", GATE_FAIL),
            _dsh_call("c", "pwsh", command="Get-Content doc/features/X/spec/reports/harness.txt"),
            _dsh_result("c", GATE_FAIL),
        ])]))
        self.assertEqual((1, 1), (r["harness_runs"], r["gate_rounds_with_fail"]))
        self.assertEqual(1, dict(r["repeated_check_fails"])["feature_to_acceptance"])

    def test_a_lone_start_or_a_lone_result_is_reported_not_guessed(self):
        events = _public_events("dsh", [("run-a", [
            _dsh_call("h", "pwsh", command=HARNESS_PWSH),
            _dsh_result("ghost", GATE_FAIL),
        ])])
        r = self._measure(events)
        self.assertEqual((1, 1), (r["tool_calls"], r["harness_runs"]), "开始了就算跑过门禁")
        self.assertIsNone(r["segments"]["whole"]["first_harness"], "没有结果就没有门禁结论")
        self.assertEqual(0, r["gate_rounds_with_fail"], "孤立结果不造一次调用、不造一轮失败")
        self.assertNotIn("", dict(r["tools"]))
        self.assertEqual([("no_result", "h"), ("result_without_call", "ghost")],
                         [(i["reason"], i["tool_call_id"]) for i in r["incomplete_tool_events"]])
        self.assertIn("统计不完整", measure_run.render(r))

    def test_a_repeated_result_counts_once_and_a_conflicting_one_is_listed(self):
        call = _dsh_call("h", "pwsh", command=HARNESS_PWSH)
        twice = self._measure(_public_events("dsh", [("run-a", [call, _dsh_result("h", GATE_FAIL),
                                                                _dsh_result("h", GATE_FAIL)])]))
        self.assertEqual((1, 1, []), (twice["tool_calls"], twice["gate_rounds_with_fail"],
                                      twice["incomplete_tool_events"]))
        clash = self._measure(_public_events("dsh", [("run-a", [call, _dsh_result("h", GATE_FAIL),
                                                                _dsh_result("h", GATE_PASS)])]))
        self.assertEqual(1, clash["tool_calls"])
        self.assertEqual(["conflicting_events"], [i["reason"] for i in clash["incomplete_tool_events"]])
        self.assertEqual(0, clash["gate_rounds_with_fail"], "两个结果互相矛盾，不任取一个")
        self.assertIsNone(clash["segments"]["whole"]["first_harness"])

    def test_a_result_shortened_by_the_host_gives_no_gate_verdict(self):
        """dsh 把长输出截断后，没看到 FAIL 不等于通过：这次门禁不出结论，列进不完整条目；没截断的照常判。"""
        shortened = dict(_dsh_result("h1", "  Harness Script Report …（后面被截掉）"), truncated=True)
        r = self._measure(_public_events("dsh", [("run-a", [
            _dsh_call("h1", "pwsh", command=HARNESS_PWSH), shortened,
            _dsh_call("h2", "pwsh", command=HARNESS_PWSH), _dsh_result("h2", GATE_FAIL),
        ])]))
        self.assertEqual(2, r["harness_runs"])
        self.assertEqual({"fail_count": 2, "status": "completed"}, r["segments"]["whole"]["first_harness"],
                         "被截断的那次不能当成一次全绿门禁")
        self.assertEqual([("source_truncated", "h1")],
                         [(i["reason"], i["tool_call_id"]) for i in r["incomplete_tool_events"]])

    def test_codex_started_and_completed_items_are_one_call(self):
        item = {"id": "item_1", "type": "command_execution", "command": "bash -lc 'npx ts-node harness-runner.ts'"}
        r = self._measure(_public_events("codex", [("run-a", [
            {"type": "item.started", "item": {**item, "status": "in_progress"}},
            {"type": "item.completed", "item": {**item, "status": "completed", "aggregated_output": GATE_FAIL}},
        ])]))
        self.assertEqual({"command_execution": 1}, dict(r["tools"]))
        self.assertEqual([], r["incomplete_tool_events"])

    def test_a_call_spanning_the_checkpoint_belongs_to_where_it_started(self):
        events = _public_events("dsh", [("run-a", [
            _dsh_call("h", "pwsh", command=HARNESS_PWSH),
            _dsh_result("h", GATE_FAIL),
        ])])
        r = self._measure(events, state={"resumed_at": "2026-10-20T10:01:00+00:00"})
        first, second = r["segments"]["initial"], r["segments"]["update"]
        self.assertEqual({"fail_count": 2, "status": "completed"}, first["first_harness"])
        self.assertIsNone(second["first_harness"], "同一结果不在两段各算一轮")
        self.assertEqual(["crosses_checkpoint"], [i["reason"] for i in r["incomplete_tool_events"]])


class ParentAndChildCountsAndDurationsAreVerifiable(unittest.TestCase):
    """TV03：父/子 assistant 响应与工具调用分列；耗时只报墙钟、可核区间（并集）、返修与未知；
    事件间隔不是纯推理，未归属部分不叫推理时间。"""

    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_dir = Path(self._tmp.name)

    def measure(self, events: list[dict]) -> dict:
        path = self.run_dir / "events.jsonl"
        path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n", encoding="utf-8")
        return measure_run.measure(path, run_dir=self.run_dir)

    def test_parent_and_child_counts_are_reported_separately(self) -> None:
        events = _public_events("dsh", [("run-a", [
            {"type": "text", "text": "第一段回复"},
            _dsh_call("c1", "pwsh", command="echo one"),
            _dsh_result("c1", "one"),
            {"type": "text", "text": "第二段回复"},
            _dsh_call("c2", "read", file_path="a.md"),
            _dsh_result("c2", "body"),
        ])])
        parent = "session-p"
        _session(self.run_dir / "native-sessions" / parent / "session.v4.jsonl.zstd", parent, [])
        _session(self.run_dir / "native-sessions" / parent / "children" / "k-1" / "session.v4.jsonl.zstd", "k-1", [
            {"type": "assistant/message", "time": 1, "data": {}},
            {"type": "assistant/message", "time": 2, "data": {}},
            {"type": "assistant/message", "time": 3, "data": {}},
            {"type": "tool/call", "time": 4, "data": {"callId": "x", "name": "read", "arguments": "{}"}},
            {"type": "tool/call", "time": 5, "data": {"callId": "y", "name": "read", "arguments": "{}"}},
        ])
        got = self.measure(events)
        self.assertEqual({"assistant_responses": 2, "tool_calls": 2}, got["parent_counts"])
        self.assertEqual({"sessions": 1, "assistant_responses": 3, "tool_calls": 2, "problems": None},
                         got["child_counts"])
        self.assertNotEqual(got["parent_counts"]["assistant_responses"], got["child_counts"]["assistant_responses"],
                            "父/子数被合成了一列")

    def test_without_kept_child_sessions_the_child_counts_are_unknown_not_zero(self) -> None:
        got = self.measure(_public_events("dsh", [("run-a", [
            {"type": "text", "text": "回复"}, _dsh_call("c1", "pwsh", command="echo x"), _dsh_result("c1", "x")])]))
        self.assertEqual({"sessions": None, "assistant_responses": None, "tool_calls": None, "problems": None},
                         got["child_counts"])

    def test_overlapping_call_intervals_are_a_union_not_a_sum(self) -> None:
        events = [
            {"seq": 0, "timestamp": "2026-10-20T10:00:00+00:00", "type": "tool", "content": "",
             "tool_name": "pwsh", "tool_status": "started", "tool_call_id": "a", "run_id": "r",
             "tool_input": {"command": "echo a"}},
            {"seq": 1, "timestamp": "2026-10-20T10:01:00+00:00", "type": "tool", "content": "",
             "tool_name": "pwsh", "tool_status": "started", "tool_call_id": "b", "run_id": "r",
             "tool_input": {"command": "echo b"}},
            {"seq": 2, "timestamp": "2026-10-20T10:02:00+00:00", "type": "tool", "content": "",
             "tool_name": "pwsh", "tool_status": "completed", "tool_call_id": "a", "run_id": "r",
             "tool_output": "a"},
            {"seq": 3, "timestamp": "2026-10-20T10:03:00+00:00", "type": "tool", "content": "",
             "tool_name": "pwsh", "tool_status": "completed", "tool_call_id": "b", "run_id": "r",
             "tool_output": "b"},
        ]
        got = self.measure(events)
        self.assertEqual(180.0, got["tool_interval_sec"], "交叠区间被相加成 240 秒")
        self.assertEqual(180.0, got["wall_clock_sec"])
        self.assertEqual(0.0, got["not_attributed_sec"], "未归属部分被扣成负数")
        self.assertIn("不是纯推理", measure_run.render(got))

    def test_an_unpaired_call_contributes_no_verifiable_interval(self) -> None:
        events = _public_events("dsh", [("run-a", [
            _dsh_call("h", "pwsh", command="echo hanging")])])
        got = self.measure(events)
        self.assertIsNone(got["tool_interval_sec"], "只有开始、没有结果的调用不是可核区间")
        # 只有一条事件时墙钟本身是 0；未归属是墙钟减可核区间的差，不是凭空补的数。
        self.assertEqual(0.0, got["wall_clock_sec"])
        self.assertEqual(0.0, got["not_attributed_sec"])


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
    """只补图片算不算新材料版本 —— 图片进来的两条路（单独的界面图、文档内嵌图）都要算。"""

    def _root(self) -> Path:
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        feature = d / "doc" / "features" / "MV90001"
        self._put(feature, {"prd.md": ("正文一字不改".encode("utf-8"), "RR")})
        return feature

    @staticmethod
    def _docx(*images: bytes) -> bytes:
        """最小 docx：一段正文，按顺序内嵌给定的图。"""
        import io  # noqa: PLC0415
        import zipfile  # noqa: PLC0415
        blips = "".join(f'<w:p><w:r><w:drawing><a:blip xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
                        f' r:embed="rId{i}"/></w:drawing></w:r></w:p>' for i in range(1, len(images) + 1))
        rels = "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                       f'relationships/image" Target="media/image{i}.png"/>' for i in range(1, len(images) + 1))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("word/document.xml",
                        '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
                        ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                        f'<w:body><w:p><w:r><w:t>补充稿</w:t></w:r></w:p>{blips}</w:body></w:document>')
            zf.writestr("word/_rels/document.xml.rels",
                        '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                        f'{rels}</Relationships>')
            for i, data in enumerate(images, start=1):
                zf.writestr(f"word/media/image{i}.png", data)
        return buf.getvalue()

    @staticmethod
    def _put(feature: Path, files: dict[str, tuple[bytes, str]]) -> None:
        """把原件放进来源收件箱，经产品的导入形成材料版本。"""
        inbox = feature / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        for rel, (data, _) in files.items():
            (inbox / rel).write_bytes(data)
        (inbox / ".classify.json").write_text(json.dumps({rel: cls for rel, (_, cls) in files.items()}), encoding="utf-8")
        importer.cmd_import(feature, feature.parents[2])

    def _fingerprint(self, feature: Path) -> str:
        return registry.build(feature)["digest"]

    def test_text_change_changes_the_version(self):
        """基线正样本：正文变了必须换版本，否则这个指纹什么都证明不了。"""
        root = self._root()
        before = self._fingerprint(root)
        self._put(root, {"prd.md": ("正文改了".encode("utf-8"), "RR")})
        self.assertNotEqual(before, self._fingerprint(root))

    def test_ui_reference_image_changes_the_version(self):
        """导入一张界面图 → 材料变了。"""
        root = self._root()
        before = self._fingerprint(root)
        self._put(root, {"flow.png": (b"PNG", "UX")})
        self.assertNotEqual(before, self._fingerprint(root))

    def test_docx_embedded_image_supplement_changes_the_version(self):
        """同一份参考稿的新版本只多了一张内嵌图：材料版本必须看见它。

        「补了一份只多几张图的文档」对轮次隐形的话，既不换轮次，也没有任何信号说材料变过。
        """
        root = self._root()
        self._put(root, {"supp.docx": (self._docx(b"PNG1"), "IMAGES")})
        before = self._fingerprint(root)
        self._put(root, {"supp.docx": (self._docx(b"PNG1", b"PNG2"), "IMAGES")})
        self.assertNotEqual(before, self._fingerprint(root), "只补图片没有形成新材料版本")

    def test_the_same_image_in_two_places_is_one_material(self):
        """同一张图出现在两份来源里是同一张图，不是两张。

        两处各登记一条时，下游看到的是两张一模一样的图，于是要么重复引用、要么各引各的。
        """
        root = self._root()
        self._put(root, {"supp.docx": (self._docx(b"PNG1"), "IMAGES"), "签约页.png": (b"PNG1", "UX")})
        images = [m for m in registry.build(root)["materials"] if m["kind"] == "image"]
        self.assertEqual(1, len(images), "同一张图被登记成了两张")
        self.assertEqual(2, len(images[0]["paths"]), f"两个落点没有都记下来：{images[0]['paths']}")
        self.assertTrue(any(p.startswith("assets/ux/签约页.") for p in images[0]["paths"]), images[0]["paths"])


class ProcessArtifactsEnterTheIndex(unittest.TestCase):
    """过程件入库（用户 2026-09-25 裁定）：spec 与 plan 各版本的方案、评审与交回都随提交留下历史；
    实跑的运行证据（事件流、运行日志、截图、材料原件、压缩包）放在 `output/story/`，不进过程件目录。
    """

    ROOTS = ("doc/spec", "doc/plan", "doc/archive/legacy-2.x/spec", "doc/archive/legacy-2.x/plan")
    EVIDENCE_SUFFIXES = {".jsonl", ".log", ".zip", ".docx", ".png"}

    def test_process_roots_are_on_disk_and_not_ignored(self):
        for rel in self.ROOTS:
            with self.subTest(root=rel):
                self.assertTrue((REPO / rel).is_dir(), f"{rel} 不在盘上")
                ignored = subprocess.run(["git", "check-ignore", "-q", f"{rel}/1.9.0/00-总览.md"],
                                         cwd=str(REPO)).returncode == 0
                self.assertFalse(ignored, f"{rel} 被忽略了")

    #: 已授权保留的历史原稿：迁移清单按确切路径与原始字节摘要登记，登记在内且字节没变的原件不是新的运行证据
    HISTORY_MANIFEST = "doc/archive/legacy-2.x/spec/2.1.0/历史参考/迁移清单.json"
    #: 金样候选的登记位置（2.0.3 的 05 合同 §2：`实施反馈/金样候选/<case>/<情景>/`）。目标稿自带的配图在情景的
    #: `assets/` 下、被本情景文档引用、且是产品支持的图片类型（`materials.importer.IMAGE_EXTS`）；
    #: 日志、事件、原件附件与压缩包被引用也不算。图里画的是否适用于该情景由评审者核，这里不看字节
    CANDIDATE_ROOTS = ("doc/plan/*/*/实施反馈/金样候选",
                       "doc/archive/legacy-2.x/plan/*/*/实施反馈/金样候选")
    #: 当前的候选位置（TEST §5：`doc/plan/<版本>/<主题>/金样候选/<case>/`，里面是该 Case 的需求树）。
    #: 目标 UX 配图是该需求的 Story 实际引用、落在同一需求根内的图片；README、蓝图等别的文档引用不代 Story 的配图用途
    STORY_CANDIDATE_ROOTS = ("doc/plan/*/*/金样候选",)
    LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")

    @classmethod
    def _linked_images(cls, doc: Path, within: Path) -> set[Path]:
        """文档里引用的、落在 within 之内的产品支持图片。"""
        out = set()
        for target in cls.LINK.findall(doc.read_text(encoding="utf-8")):
            if re.match(r"^[a-z]+:", target) or target.startswith("#"):
                continue
            f = (doc.parent / unquote(target.split("#")[0])).resolve()
            if f.is_file() and within in f.parents and f.suffix.lower() in importer.IMAGE_EXTS:
                out.add(f)
        return out

    @classmethod
    def candidate_assets(cls, repo: Path) -> set[str]:
        """候选里的目标配图：历史候选情景文档引用的本情景 assets/ 图，当前候选各需求 Story 引用的本需求根内的图。"""
        found: set[Path] = set()
        for root in (root for pattern in cls.CANDIDATE_ROOTS for root in repo.glob(pattern)):
            for scene in (s for s in root.glob("*/*") if s.is_dir()):
                for doc in scene.rglob("*.md"):
                    found |= cls._linked_images(doc, (scene / "assets").resolve())
        for root in (root for pattern in cls.STORY_CANDIDATE_ROOTS for root in repo.glob(pattern)):
            for story in root.glob("*/doc/features/*/AR/story.md"):
                found |= cls._linked_images(story, story.parent.parent.resolve())
        return {f.relative_to(repo.resolve()).as_posix() for f in found}

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
            history = repo / "doc/archive/legacy-2.x/spec/2.1.0/历史参考"
            original = history / "原1.9.9/data/a.png"
            original.parent.mkdir(parents=True)
            original.write_bytes(b"original")
            (repo / "doc/plan").mkdir(parents=True)
            (history / "迁移清单.json").write_text(json.dumps({
                "destination_root": "doc/archive/legacy-2.x/spec/2.1.0/历史参考/原1.9.9",
                "files": [{"path": "data/a.png", "sha256": hashlib.sha256(b"original").hexdigest()}]}),
                encoding="utf-8")
            self.assertEqual([], self.stray_evidence(repo))
            (history / "原1.9.9/data/b.png").write_bytes(b"new")
            (repo / "doc/plan/run.log").write_text("x", encoding="utf-8")
            self.assertEqual({"doc/archive/legacy-2.x/spec/2.1.0/历史参考/原1.9.9/data/b.png", "doc/plan/run.log"},
                             set(self.stray_evidence(repo)))
            original.write_bytes(b"edited")
            self.assertIn("doc/archive/legacy-2.x/spec/2.1.0/历史参考/原1.9.9/data/a.png", self.stray_evidence(repo))

    def test_candidate_assets_are_recognised_by_place_and_reference(self):
        """候选情景 assets/ 下、被本情景文档引用的配图是目标稿的一部分，新画的也算；
        引用不到的、放在候选范围外的（哪怕与已审原图同字节）、运行截图，都还是运行证据。"""
        for base in ("doc/plan/2.0.0/设计/实施反馈/",
                     "doc/archive/legacy-2.x/plan/2.0.3/设计/实施反馈/"):
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

    def test_current_candidate_story_images_are_target_assets(self):
        """当前候选（`金样候选/<case>/doc/features/<需求>/`）里该需求 Story 引用的本需求图是目标配图；
        没人引用的、只被 README 或蓝图引用的、引用越出本需求根的、运行原件即使被 Story 链接，都还是运行证据。"""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "doc/spec").mkdir(parents=True)
            case = repo / "doc/plan/2.0.1/主题/金样候选/demo-case"
            feature = case / "doc/features/ISSUE-1"
            (feature / "AR").mkdir(parents=True)
            (feature / "ux-reference").mkdir()
            (feature / "ux-reference/设置页.png").write_bytes(b"page")
            (feature / "AR/story.md").write_text("![设置页](../ux-reference/%E8%AE%BE%E7%BD%AE%E9%A1%B5.png)\n",
                                                 encoding="utf-8")
            self.assertEqual([], self.stray_evidence(repo), "Story 引用的候选配图不是运行证据")

            base = "doc/plan/2.0.1/主题/金样候选/demo-case/"
            (feature / "ux-reference/没人引用.png").write_bytes(b"x")
            (feature / "ux-reference/只在说明里.png").write_bytes(b"y")
            (case / "README.md").write_text("![图](doc/features/ISSUE-1/ux-reference/只在说明里.png)\n", encoding="utf-8")
            (feature / "blueprint").mkdir()
            (feature / "blueprint/blueprint.target.md").write_text("![图](../ux-reference/没人引用.png)\n",
                                                                    encoding="utf-8")
            other = case / "doc/features/ISSUE-2/ux-reference/别的需求.png"
            other.parent.mkdir(parents=True)
            other.write_bytes(b"z")
            outside = repo / "doc/plan/2.0.1/主题/截图.png"
            outside.write_bytes(b"shot")
            for name in ("run.log", "原稿.docx", "包.zip", "events.jsonl"):
                (feature / "ux-reference" / name).write_text("x", encoding="utf-8")
            (feature / "AR/story.md").write_text(
                "![设置页](../ux-reference/%E8%AE%BE%E7%BD%AE%E9%A1%B5.png)\n"
                "![别的需求](../../ISSUE-2/ux-reference/别的需求.png)\n"
                "![越界](../../../../../../截图.png)\n"
                + "".join(f"[{n}](../ux-reference/{n})\n" for n in ("run.log", "原稿.docx", "包.zip", "events.jsonl")),
                encoding="utf-8")
            prefix = base + "doc/features/ISSUE-1/ux-reference/"
            self.assertEqual({prefix + "没人引用.png", prefix + "只在说明里.png",
                              base + "doc/features/ISSUE-2/ux-reference/别的需求.png", "doc/plan/2.0.1/主题/截图.png",
                              *(prefix + n for n in ("run.log", "原稿.docx", "包.zip", "events.jsonl"))},
                             set(self.stray_evidence(repo)))

    @staticmethod
    def golden_copies(root: Path) -> list[str]:
        """审定正文在 `test/golden/` 之外的第二份：内容与登记的正文相同的文件，以及审定后还留着正文的候选目录。

        判的是性质不是文件名：中性夹具自己的 story.md、历史报告里对正本的引文与链接都不算；
        同一份审定正文换个位置存着才算——改了哪一份、对照的又是哪一份，就再也说不清。
        """
        from test_golden_sample import DOCUMENTS, REGISTRY, digest  # noqa: PLC0415
        approved = {REGISTRY[f"{case}/{rel}"]: f"{case}/{rel}" for case, docs in DOCUMENTS.items() for rel in docs}
        golden = root / "test" / "golden"
        found = []
        for top in ("doc", "test"):
            for p in (root / top).rglob("*.md"):
                # 归档目录保存的是历史版本的原始字节（批次一保全），不是第二份正本
                if golden in p.parents or "node_modules" in p.parts or (root / "doc" / "archive") in p.parents:
                    continue
                if digest(p) in approved:
                    found.append(f"{p.relative_to(root).as_posix()}：与正本 {approved[digest(p)]} 相同")
        for case, docs in DOCUMENTS.items():
            for cand in (root / "doc" / "plan").glob(f"*/{"金样候选"}/{case}"):
                for rel in docs:
                    if (cand / rel).is_file():
                        found.append(f"{(cand / rel).relative_to(root).as_posix()}：审定后的候选目录还留着正文")
        return found

    def test_golden_output_has_a_single_canonical_copy(self):
        self.assertEqual([], self.golden_copies(REPO))

    def test_a_second_copy_is_found_and_neutral_texts_are_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ("auto-topup/AR/story.md", "car-key-sharing/plan/plan.md"):
                (root / "test/golden" / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(REPO / "test/golden" / rel, root / "test/golden" / rel)
            fixture = root / "test/fixtures/neutral/AR/story.md"
            fixture.parent.mkdir(parents=True)
            fixture.write_text("# 中性夹具\n\n## 1. 背景\n", encoding="utf-8")
            report = root / "doc/plan/9.9/评审.md"
            report.parent.mkdir(parents=True)
            report.write_text("正本见 [story](../../../test/golden/auto-topup/AR/story.md)。\n", encoding="utf-8")
            self.assertEqual([], self.golden_copies(root), "中性夹具或历史引用被当成了副本")

            copy = root / "test/fixtures/neutral/copy.md"
            shutil.copy(REPO / "test/golden/auto-topup/AR/story.md", copy)
            cand = root / "doc/plan/9.9" / "金样候选" / "car-key-sharing/plan/plan.md"
            cand.parent.mkdir(parents=True)
            cand.write_text("候选时期的另一稿\n", encoding="utf-8")
            found = self.golden_copies(root)
            self.assertEqual(2, len(found), found)
            self.assertIn("test/fixtures/neutral/copy.md", found[0])
            self.assertIn("car-key-sharing/plan/plan.md", found[1])

    CANDIDATES = "金样候选"

    @classmethod
    def candidate_figure(cls, p: Path, root: Path = REPO) -> bool:
        """待审定的效果稿配图是被审产物，不是运行证据。

        只认登记的候选位置 `doc/plan/<版本>/金样候选/<Case>/ux-reference/<图>`，且这个 Case 的 story 真引用它；
        同样的 AR/ux-reference 布局出现在别处（运行目录、工作区副本）仍按运行证据报。
        """
        parts = p.relative_to(root).parts
        if not (len(parts) == 7 and parts[:2] == ("doc", "plan") and parts[3] == cls.CANDIDATES
                and parts[5] == "ux-reference" and p.suffix == ".png"):
            return False
        story = p.parent.parent / "AR" / "story.md"
        return story.is_file() and f"](../ux-reference/{p.name})" in story.read_text(encoding="utf-8")

    ANALYSIS_ARCHIVE = "doc/spec/1.9.9/04-稳定性与性能分析/data/golden"

    @staticmethod
    def archive_references(obj: Path) -> tuple[dict[Path, str], list[str]]:
        """对象自身引用的图：story 的 Markdown 图片（相对 story 所在目录），spec Visual Handoff 的
        authoritative_refs（消费工程路径 `doc/features/<对象>/…` 映射到对象子目录）。

        返回（合法引用的目标 → 引用原文，非法引用）。绝对路径、不带本对象前缀的 Visual Handoff 路径、
        映射后逃出本对象子目录的引用都是非法引用，不进允许集合；文件碰巧存在也不算。"""
        import yaml  # noqa: PLC0415
        home = obj.resolve()
        refs: dict[Path, str] = {}
        bad: list[str] = []

        def take(rel: str, src: str) -> None:
            if PureWindowsPath(rel).drive or rel.startswith(("/", "\\")):
                bad.append(f"{src}：不是相对路径")
                return
            target = (obj / rel).resolve()
            if target.is_relative_to(home):
                refs[target] = src
            else:
                bad.append(f"{src}：逃出了对象目录")

        story = obj / "story.md"
        if story.is_file():
            for target in re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", story.read_text(encoding="utf-8")):
                take(target, f"story.md {target}")
        spec = obj / "spec.md"
        if spec.is_file():
            prefix = f"doc/features/{obj.name}/"
            for block in re.findall(r"```yaml\n(.*?)```", spec.read_text(encoding="utf-8"), re.S):
                data = yaml.safe_load(block)
                handoff = data.get("visual_handoff") if isinstance(data, dict) else None
                for ref in (handoff or {}).get("authoritative_refs") or []:
                    path, src = str(ref.get("path", "")), f"spec.md visual_handoff {ref.get('path', '')}"
                    if path.startswith(prefix):
                        take(path[len(prefix):], src)
                    else:
                        bad.append(f"{src}：不是 {prefix} 下的消费工程路径")
        return refs, bad

    @classmethod
    def analysis_reference(cls, p: Path, root: Path = REPO) -> bool:
        """分析归档里被所属对象 story 或 spec 实际引用的 PNG 是评价参照，不是运行截图。

        只认这一份归档：MANIFEST.md 在，图在 `<对象>/assets|ux-reference/` 下，且所属对象的引用映射到它。
        不按目录名放行，未引用、映射错的图与其它后缀照常按运行证据报。
        """
        base = root / cls.ANALYSIS_ARCHIVE
        if p.suffix != ".png" or not p.is_relative_to(base) or not (base / "MANIFEST.md").is_file():
            return False
        parts = p.relative_to(base).parts
        if len(parts) != 3 or parts[1] not in ("assets", "ux-reference"):
            return False
        return p.resolve() in cls.archive_references(base / parts[0])[0]

    @classmethod
    def broken_archive_references(cls, root: Path = REPO) -> list[str]:
        """非法引用逐条报（同一张图另有合法引用也报），合法引用指不到文件的也报。"""
        base = root / cls.ANALYSIS_ARCHIVE
        out: list[str] = []
        for obj in (sorted(o for o in base.iterdir() if o.is_dir()) if base.is_dir() else []):
            refs, bad = cls.archive_references(obj)
            out += [f"{obj.name}/{b}" for b in bad]
            out += [f"{obj.name}/{src}：指不到文件" for target, src in refs.items() if not target.is_file()]
        return out

    def test_both_roots_are_on_disk_and_not_ignored(self):
        for rel in self.ROOTS:
            with self.subTest(root=rel):
                self.assertTrue((REPO / rel).is_dir(), f"{rel} 不在盘上")
                ignored = subprocess.run(["git", "check-ignore", "-q", f"{rel}/1.9.0/00-总览.md"],
                                         cwd=str(REPO)).returncode == 0
                self.assertFalse(ignored, f"{rel} 被忽略了")

    def test_a_candidate_figure_is_recognised_only_where_candidates_are_registered(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)

            def case(base: Path) -> tuple[Path, Path]:
                (base / "AR").mkdir(parents=True)
                (base / "ux-reference").mkdir()
                used, spare = base / "ux-reference" / "a.png", base / "ux-reference" / "b.png"
                for f in (used, spare):
                    f.write_bytes(b"PNG")
                (base / "AR" / "story.md").write_text("![图 1 · 甲](../ux-reference/a.png)\n", encoding="utf-8")
                return used, spare

            used, spare = case(root / "doc" / "plan" / "1.9.9" / "金样候选" / "某案")
            self.assertTrue(self.candidate_figure(used, root))
            self.assertFalse(self.candidate_figure(spare, root), "story 没引用的图也被当成了产物")
            for elsewhere in (root / "doc" / "plan" / "1.9.9" / "实跑-0101" / "某案",
                              root / "doc" / "spec" / "1.9.9" / "金样候选" / "某案",
                              root / "doc" / "plan" / "1.9.9" / "金样候选" / "某案" / "副本"):
                with self.subTest(where=elsewhere.relative_to(root).as_posix()):
                    run_used, _ = case(elsewhere)
                    self.assertFalse(self.candidate_figure(run_used, root), "候选位置之外的同样布局被当成了产物")



class GateConclusionsAreCountedByKind(unittest.TestCase):
    """同一调用结果派生按种类的门禁结论：harness 与 story_register 分计；没结果、冲突或截断记判不了；
    原生 harness 的失败轮数保持原义，登记成功不算失败。"""

    def measure(self, events: list[dict]) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n", encoding="utf-8")
            return measure_run.measure(path)

    @staticmethod
    def call(seq: int, command: str, output: str | None, **extra) -> dict:
        event = {"type": "tool", "tool_name": "bash", "tool_call_id": f"c{seq}", "run_id": "r",
                 "timestamp": f"2026-10-26T10:0{seq}:00+08:00", "tool_input": {"command": command},
                 "tool_status": "completed"}
        if output is not None:
            event["tool_output"] = output
        return {**event, **extra}

    def test_harness_and_registration_are_counted_apart(self) -> None:
        got = self.measure([
            self.call(1, "npx ts-node harness-runner.ts --phase spec --feature X", "FAIL [BLOCKER] check_a"),
            self.call(2, "python story_flow.py story --feature X", "{\"ok\": false, \"error\": \"未通过\"}"),
            self.call(3, "python story_flow.py story --feature X", "{\"ok\": true}"),
        ])
        self.assertEqual(1, got["gate_rounds_with_fail"], "harness 失败轮数的原义变了")
        self.assertEqual({"harness": 1, "story_register": 1, "story_check": 0, "review_check": 0, "deliver": 0}, got["gate_fail_by_kind"])
        self.assertEqual({"harness": 0, "story_register": 0, "story_check": 0, "review_check": 0, "deliver": 0}, got["gate_unknown_by_kind"])

    def test_a_truncated_or_missing_result_is_unknown_not_a_pass(self) -> None:
        got = self.measure([
            self.call(1, "npx ts-node harness-runner.ts --phase spec --feature X", "PASS", source_truncated=True),
            {**self.call(2, "python story_flow.py story --feature X", None), "tool_status": "started"},
        ])
        self.assertEqual({"harness": 1, "story_register": 1, "story_check": 0, "review_check": 0, "deliver": 0}, got["gate_unknown_by_kind"])
        self.assertEqual({"harness": 0, "story_register": 0, "story_check": 0, "review_check": 0, "deliver": 0}, got["gate_fail_by_kind"])

    def test_story_check_review_conclusions_and_the_delivery_gate_are_counted_apart(self) -> None:
        """成文检查没过、审查结论 report_invalid、交付门一次过各自计：交付门过了不抹掉之前的检查与审查结论。"""
        build = "node doc/extensions/skills/story/scripts/core/story-build.mjs"
        got = self.measure([
            self.call(1, f"{build} check --feature X", "{\"ok\": false, \"problems\": [\"2 处未通过\"]}"),
            self.call(2, f"{build} review --action check --feature X", "{\"result\": \"report_invalid\", \"detail\": \"缺判据\"}"),
            self.call(3, f"{build} review --action check --feature X", "{\"result\": \"warn\"}"),
            self.call(4, f"{build} check --deliver --feature X", "{\"ok\": true}"),
        ])
        self.assertEqual({"harness": 0, "story_register": 0, "story_check": 1, "review_check": 1, "deliver": 0},
                         got["gate_fail_by_kind"])
        self.assertEqual({"report_invalid": 1, "warn": 1}, got["review_results"])


#: 造一份 dsh v4 原生会话：行写成 jsonl，用 Node 内置 zstd 压成一个 frame
ZSTD = "const fs = require('fs'); const zlib = require('zlib');" \
       "fs.writeFileSync(process.argv[2], zlib.zstdCompressSync(fs.readFileSync(process.argv[1])));"


def _session(path: Path, session_id: str, rows: list[dict], cwd: str = "w") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plain = path.with_suffix(".plain")
    plain.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in
                                [{"type": "session", "version": 4, "id": session_id, "cwd": cwd}, *rows]) + "\n", encoding="utf-8")
    subprocess.run(["node", "-e", ZSTD, str(plain), str(path)], check=True)
    plain.unlink()


class NativeDelegationsAreReadByWhatWasSent(unittest.TestCase):
    """委派的角色按原生会话里实际派出去的正文与子会话实际产出认，不按工具名或 label：
    产品载体 → 那一类审查（专用 verifier 工具派的也是）；写了需求 blueprint/ 下的设计产物 → 蓝图作者；
    派出去的是原生阶段审查请求 → 阶段审查；其余 unresolved。
    观察跨度从原生登记到收尾通知，没有收尾通知是 unknown，不是 0；没有保全原件时整项为 null。"""

    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_dir = Path(self._tmp.name)

    def spawn(self, seq: int, call_id: str, child: str, prompt: str, label: str, *, settled: str | None) -> list[dict]:
        rows = [{"type": "tool/call", "time": seq * 60000, "data": {"callId": call_id, "name": "subagent",
                                                                  "arguments": json.dumps({"description": label, "prompt": prompt})}},
                {"type": "subagent/catalog", "time": seq * 60000, "data": {"childId": child, "childCreatedAt": seq * 60000, "label": label}},
                {"type": "tool/result", "time": seq * 60000, "data": {"message": {"toolCallId": call_id,
                                                                                  "content": [{"type": "text", "text": f"started subagent {child}"}]}}}]
        if settled:
            rows.append({"type": "agent/inbox/spliced", "time": (seq + 10) * 60000, "data": {"inserted": [{
                "content": [{"type": "text", "text": "报告正文"}],
                "source": {"kind": "subagent-settled", "senderSessionId": child,
                           "summary": f"Background subagent {child} {settled}."}}]}})
        return rows

    def test_roles_spans_and_unknowns(self) -> None:
        parent = "session-p"
        base = self.run_dir / "native-sessions" / parent
        rows = [*self.spawn(1, "c1", "k-review", "# Story 独立人读审查 · 派审\n\n- 材料键：x", "随便起的名字", settled="finished and will do no further work"),
                *self.spawn(2, "c2", "k-author", "你来写这份蓝图", "看起来像审查的 label", settled="failed before it finished"),
                *self.spawn(3, "c3", "k-other", "帮我查一下代码", "研究", settled=None),
                {"type": "tool/call", "time": 5, "data": {"callId": "c4", "name": "verifier", "arguments": json.dumps(
                    {"prompt": json.dumps({"schema_version": "1.1", "kind": "maison_verifier_request", "subject_id": "s" * 64})})}},
                # 实跑里见过：Story 审查载体、蓝图质询载体被交给专用 verifier 工具
                {"type": "tool/call", "time": 6, "data": {"callId": "c5", "name": "verifier", "arguments": json.dumps(
                    {"prompt": "# Story 独立人读审查 · 派审\n\n- 材料键：y"})}},
                {"type": "tool/call", "time": 7, "data": {"callId": "c6", "name": "verifier", "arguments": json.dumps(
                    {"prompt": "# 蓝图独立质询 · 派审\n"})}},
                {"type": "tool/call", "time": 8, "data": {"callId": "c7", "name": "verifier", "arguments": "{}"}}]
        _session(base / "session.v4.jsonl.zstd", parent, rows)
        _session(base / "children" / "k-author" / "session.v4.jsonl.zstd", "k-author", [
            {"type": "tool/call", "time": 1, "data": {"callId": "w", "name": "write",
                                                      "arguments": json.dumps({"file_path": "doc/features/X/blueprint/contracts/a.yaml"})}}])
        _session(base / "children" / "k-other" / "session.v4.jsonl.zstd", "k-other", [
            {"type": "tool/call", "time": 1, "data": {"callId": "r", "name": "read", "arguments": json.dumps({"file_path": "src/a.ets"})}}])
        got = measure_run.native_delegations(measure_run._native_sessions(self.run_dir))["delegations"]
        self.assertEqual({"story_review": 2, "blueprint_author": 1, "unresolved": 2, "stage_verifier": 1, "questioning": 1},
                         got["by_role"], "专用 verifier 工具派的 Story 审查或质询被算成了阶段审查")
        by_child = {i["child_id"]: i for i in got["items"]}
        self.assertEqual((10.0, "finished"), (by_child["k-review"]["observed_span_min"], by_child["k-review"]["settled"]))
        self.assertEqual("failed", by_child["k-author"]["settled"])
        self.assertEqual((None, "unknown"), (by_child["k-other"]["observed_span_min"], by_child["k-other"]["settled"]),
                         "没有收尾通知的跨度被当成了一个数")

    def test_the_review_mode_is_what_the_carrier_says(self) -> None:
        """Story 派审的种类照载体写明的那一节：先首读、复核、补正；旧版本的载体没有这几节，判 unknown，不按先后次序猜。"""
        parent = "session-p"
        head = "# Story 独立人读审查 · 派审\n\n- 材料键：x\n\n"
        rows = [*self.spawn(1, "c1", "k-1", head + "## 先首读\n\n先只读 Story。\n", "审查", settled=None),
                *self.spawn(2, "c2", "k-2", head + "## 复核\n\n这是复核。\n", "审查", settled=None),
                *self.spawn(3, "c3", "k-3", head + "## 补正上一份回复\n\n补正。\n", "审查", settled=None),
                *self.spawn(4, "c4", "k-4", head + "请审查。\n", "审查", settled=None)]
        _session(self.run_dir / "native-sessions" / parent / "session.v4.jsonl.zstd", parent, rows)
        got = measure_run.native_delegations(measure_run._native_sessions(self.run_dir))["delegations"]
        self.assertEqual({"k-1": "first_read", "k-2": "recheck", "k-3": "correction", "k-4": "unknown"},
                         {i["child_id"]: i["review_mode"] for i in got["items"]})
        self.assertEqual({"first_read": 1, "recheck": 1, "correction": 1, "unknown": 1}, got["story_review_modes"])

    def test_without_kept_sessions_the_roles_are_unknown(self) -> None:
        self.assertIsNone(measure_run.native_delegations(measure_run._native_sessions(self.run_dir))["delegations"])

    KEY = "a" * 64

    def write_rows(self, path: str, content: str | None = None, *, outcome: str = "ok",
                   name: str = "write", call_id: str = "w1") -> list[dict]:
        """读者子会话里的一次写文件调用：`outcome` 取 ok / error / no_result（只有调用、没有结果）。"""
        args = {"file_path": path}
        if content is not None:
            args["content"] = content
        rows = [{"type": "tool/call", "time": 2 * 60000,
                 "data": {"callId": call_id, "name": name,
                          "arguments": json.dumps(args, ensure_ascii=False)}}]
        if outcome != "no_result":
            rows.append({"type": "tool/result", "time": 2 * 60000,
                         "data": {"message": {"toolCallId": call_id, "isError": outcome == "error",
                                              "content": [{"type": "text",
                                                           "text": "writing failed" if outcome == "error" else "ok"}]}}})
        return rows

    def review(self, reply: str, *, key: str | None = None, original: str | None = None,
               dispatch: str = "current", child_rows: list[dict] | None = None,
               cwd: str = "w") -> dict:
        """派一次 Story 独审，子会话正常收尾，收尾通知带着 `reply`；回给这一项的委派条目。

        `dispatch="current"` 是现行载体（写明本次报告文件）；`dispatch="historical"` 是按 2.0.2 及以前
        身份保全的旧载体（没有这一行，最终回复就是报告）。`original` 给定时保全读者子会话里「读者把
        `original` 写进本次报告文件、工具返回成功」这一动作；`child_rows` 给定时按它保全子会话，用来造
        工具返回错误、只有调用没有结果、写进别的相对目录或别的工作区这些反例。
        """
        shutil.rmtree(self.run_dir, ignore_errors=True)  # 每次派审只留这一次的子会话
        parent = "session-p"
        report = self.report_file(key)
        head = (f"# Story 独立人读审查 · 派审\n\n- 材料键：`{key or self.KEY}`\n"
                + (f"- 本次报告文件：`{report}`\n" if dispatch == "current" else ""))
        rows = self.spawn(1, "c1", "k-review", head, "审查", settled=None)
        rows.append({"type": "agent/inbox/spliced", "time": 11 * 60000, "data": {"inserted": [{
            "content": [{"type": "text", "text": "Background subagent k-review finished and will do no further work.\n"
                                                 "Its closing message:\n" + reply}],
            "source": {"kind": "subagent-settled", "senderSessionId": "k-review",
                       "summary": "Background subagent k-review finished and will do no further work."}}]}})
        _session(self.run_dir / "native-sessions" / parent / "session.v4.jsonl.zstd", parent, rows, cwd=cwd)
        child = child_rows if child_rows is not None else (
            self.write_rows(report, original) if original is not None else None)
        if child is not None:
            _session(self.run_dir / "native-sessions" / parent / "children" / "k-review" / "session.v4.jsonl.zstd",
                     "k-review", child, cwd=cwd)
        got = measure_run.native_delegations(measure_run._native_sessions(self.run_dir))["delegations"]
        [item] = got["items"]
        return {**item, "conclusions": got["story_review_conclusions"]}

    def report(self, conclusion: str) -> str:
        """已保全的 2.0.2 及以前运行记录里的报告形态（只读识别）。"""
        return (f"material_key: {self.KEY}\n\n## 判据核对\n\n| 判据 ID | 结果 | 依据 |\n|---|---|---|\n| story_reader_review | fail | 口径冲突 |\n\n"
                "## 发现\n\n| 编号 | 严重程度 | 判据 ID | 材料位置 | 问题与依据 | 修正责任 |\n|---|---|---|---|---|---|\n"
                f"| F1 | MAJOR | story_reader_review | AR/story.md | 转化率分子分母冲突 | 设计 |\n\n## 总体结论\n\n{conclusion}\n")

    def test_review_tasks_are_counted_by_task_id_reply_and_verified_report(self) -> None:
        """审查按实际任务 ID / 取得回复文本 / 可核完整报告 / 对象数分开计；完整回复只计可核完整的那几份。
        这里的报告是 2.0.2 及以前载体保全下来的历史派审（没有现行报告文件），按当时的完整报告形态读取。"""
        got = self.review(self.report("fail\n\n理由。"), dispatch="historical")
        self.assertEqual(("k-review", True, {"value": "complete", "why": None, "basis": "recorded_report",
                                             "report_file": None}, ["a" * 64]),
                         (got["task_id"], got["reply_received"], got["report_completeness"], got["objects"]))
        aggregate = measure_run.native_delegations(measure_run._native_sessions(self.run_dir))["delegations"]
        self.assertEqual((1, 1, 1, 1, 0),
                         (aggregate["story_review_tasks"], aggregate["story_review_settled"],
                          aggregate["story_review_replies"], aggregate["story_review_full_replies"],
                          aggregate["story_review_reports_unknown"]),
                         "完整回复、取得回复文本与已收尾混成了同一个数")

    def test_a_finished_task_without_a_reply_is_not_a_full_report(self) -> None:
        """任务收尾了、收尾通知里却没有收尾回复：`settled` 仍是 finished，但没取得回复文本，报告不可核。"""
        parent = "session-p"
        rows = self.spawn(1, "c1", "k-review", f"# Story 独立人读审查 · 派审\n\n- 材料键：`{self.KEY}`\n", "审查", settled=None)
        rows.append({"type": "agent/inbox/spliced", "time": 11 * 60000, "data": {"inserted": [{
            "content": [{"type": "text", "text": "Background subagent k-review finished and will do no further work."}],
            "source": {"kind": "subagent-settled", "senderSessionId": "k-review",
                       "summary": "Background subagent k-review finished and will do no further work."}}]}})
        _session(self.run_dir / "native-sessions" / parent / "session.v4.jsonl.zstd", parent, rows)
        got = measure_run.native_delegations(measure_run._native_sessions(self.run_dir))["delegations"]
        [item] = got["items"]
        self.assertEqual(("finished", False, {"value": "unknown", "why": "收尾通知里没有收尾回复",
                                              "basis": None, "report_file": None}),
                         (item["settled"], item["reply_received"], item["report_completeness"]))
        self.assertEqual((1, 1, 0, 0, 1),
                         (got["story_review_tasks"], got["story_review_settled"], got["story_review_replies"],
                          got["story_review_full_replies"], got["story_review_reports_unknown"]))
        self.assertFalse(item["reply_received"], "只有收尾状态、没有完整回复，被算成了取得回复文本")

    def test_empty_pointer_and_complete_replies_are_three_different_facts(self) -> None:
        """同一原生任务三种收尾回复：空正文、「报告已写入」、完整报告都已收尾；
        空正文没取得回复文本，指针取得了文本但不是完整报告，只有带材料键与结论行、且读者把同一份正文
        成功写进本次报告文件的完整回复计可核完整；未核证的单独计数，不把判断结果未知当任务失败。"""
        head = (f"# Story 独立人读审查 · 派审\n\n- 材料键：`{self.KEY}`\n"
                f"- 本次报告文件：`{self.report_file()}`\n")
        parent = "session-p"
        rows: list[dict] = []
        for seq, child, reply in ((1, "k-empty", ""), (2, "k-pointer", "报告已写入\n"),
                                  (3, "k-full", self.current_report("pass"))):
            rows += self.spawn(seq, f"c{child}", child, head, "审查", settled=None)
            rows.append({"type": "agent/inbox/spliced", "time": (seq + 10) * 60000, "data": {"inserted": [{
                "content": [{"type": "text", "text": f"Background subagent {child} finished and will do no further work.\n"
                                                     "Its closing message:\n" + reply}],
                "source": {"kind": "subagent-settled", "senderSessionId": child,
                           "summary": f"Background subagent {child} finished and will do no further work."}}]}})
        _session(self.run_dir / "native-sessions" / parent / "session.v4.jsonl.zstd", parent, rows)
        _session(self.run_dir / "native-sessions" / parent / "children" / "k-full" / "session.v4.jsonl.zstd",
                 "k-full", self.write_rows(self.report_file(), self.current_report("pass")))
        got = measure_run.native_delegations(measure_run._native_sessions(self.run_dir))["delegations"]
        by_child = {i["child_id"]: i for i in got["items"]}
        self.assertEqual(
            {"k-empty": ("finished", False, "unknown"),
             "k-pointer": ("finished", True, "unknown"),
             "k-full": ("finished", True, "complete")},
            {child: (i["settled"], i["reply_received"], i["report_completeness"]["value"])
             for child, i in by_child.items()})
        self.assertEqual({"unknown": 2, "pass": 1}, got["story_review_conclusions"])
        self.assertEqual((3, 3, 2, 1, 2),
                         (got["story_review_tasks"], got["story_review_settled"], got["story_review_replies"],
                          got["story_review_full_replies"], got["story_review_reports_unknown"]),
                         "三种回复被数成了同一个完整回复数")

    def test_a_review_that_finished_normally_can_still_fail(self) -> None:
        """子会话正常收尾，回复写明总体结论 fail：业务结论是 fail，收尾仍是 finished，历史报告按原身份可核完整；
        三件事分开记，并给出回复里的行号——真实 fail 没有被算成任务失败或报告不可核。"""
        got = self.review(self.report("fail\n\n理由：存在 1 条 MAJOR。"), dispatch="historical")
        self.assertEqual(("finished", "fail", "complete"),
                         (got["settled"], got["review_conclusion"]["value"], got["report_completeness"]["value"]))
        self.assertEqual({"child_id": "k-review", "settled_time": 11 * 60000, "reply_line": 17}, got["review_conclusion"]["at"])
        self.assertEqual({"fail": 1}, got["conclusions"])

    def current_report(self, conclusion: str) -> str:
        return (f"material_key: {self.KEY}\nconclusion: {conclusion}\n\n复核：按影响核了口径冲突。\n\n"
                "- F1（MAJOR）AR/story.md：转化率分子分母冲突。修正：设计。\n")

    def test_the_current_reply_gives_its_conclusion_line(self) -> None:
        """现行回复：结论照开头第二行读，正文里的字样不参与；报告完整性按读者原件对照整份 final 核。"""
        original = self.current_report("fail") + "\n结论差点写 pass。\n"
        got = self.review(original, original=original)
        self.assertEqual(("fail", None, 2), (got["review_conclusion"]["value"], got["review_conclusion"]["why"],
                                             got["review_conclusion"]["at"]["reply_line"]))
        self.assertEqual({"value": "complete", "why": None, "basis": "reader_original",
                          "report_file": self.report_file()},
                         got["report_completeness"])

    def report_file(self, key: str | None = None) -> str:
        return f"doc/reports/story/AR/{(key or self.KEY)[:16]}/review-original.1.md"

    def test_report_completeness_needs_the_whole_report_not_the_header(self) -> None:
        """五组对照：原文件、去掉全部正文、两行加部分正文、真实 fail、无对应原件。

        完整性只认「读者写进本次报告文件的原件」与整份 final 是同一份正文：只有开头两行、
        只有部分正文、或没有原件可核时都记 unknown，并保留已收尾、已取得回复文本、已声明结论
        这些各自的事实；真实 fail 的完整报告仍可核；没有原件时也不据回复长短推断完整。
        """
        original = self.current_report("pass") + "\n## 复核范围\n\n- 核了口径冲突与三处引用位置。\n"
        lines = original.splitlines()
        header_only = "\n".join(lines[:2])
        with_part = "\n".join(lines[:4])
        cases = {
            "原文件": (self.review(original, original=original), "complete", None),
            "只有开头两行": (self.review(header_only, original=original), "unknown", "最终回复只有报告开头"),
            "两行加部分正文": (self.review(with_part, original=original), "unknown",
                        "最终回复只是读者原件的一部分，缺正文"),
        }
        for name, (got, value, why) in cases.items():
            with self.subTest(name):
                self.assertEqual((value, why), (got["report_completeness"]["value"], got["report_completeness"]["why"]))
                self.assertEqual(("finished", True), (got["settled"], got["reply_received"]),
                                 f"{name}：收尾与取得回复文本是另一件事，被完整性结论改写了")
        # 真实 fail：完整报告 + 读者原件，结论照第二行读，报告仍可核
        failed = self.current_report("fail") + "\n- F1（MAJOR）AR/story.md：转化率冲突。\n"
        got = self.review(failed, original=failed)
        self.assertEqual(("complete", "fail"),
                         (got["report_completeness"]["value"], got["review_conclusion"]["value"]))
        self.assertEqual("reader_original", got["report_completeness"]["basis"])
        # 无对应原件：现行形态只有回复本身，没有可直接核的读者原件，完整与否 unknown，事实照记
        got = self.review(original)
        self.assertEqual(("unknown", "finished", True, "pass"),
                         (got["report_completeness"]["value"], got["settled"], got["reply_received"],
                          got["review_conclusion"]["value"]))
        self.assertIn("没有保全的读者子会话", got["report_completeness"]["why"])

    def test_markdown_headings_do_not_change_the_evidence_standard(self) -> None:
        """现行作者自己选「判据核对／发现／总体结论」三个标题，不能让报告完整性走历史分支：
        同次派审有较长的读者原件、final 删掉末段时按原件对照记 unknown。
        历史载体（没有本次报告文件）才按当时身份读三个标题——出处见
        `output/story/story-suite-20261102-210800/cases/auto-topup/20261102-211017-28956-f6207c49/` 的父会话。"""
        historical_like = self.report("pass\n\n理由：存在 0 条阻断。")
        final = historical_like[:historical_like.index("理由：")]
        got = self.review(final, original=historical_like)
        self.assertEqual(("unknown", None),
                         (got["report_completeness"]["value"], got["report_completeness"]["basis"]),
                         "现行派审只凭作者标题被当成了历史报告")
        self.assertIn("最终回复只是读者原件的一部分", got["report_completeness"]["why"])
        self.assertEqual(("finished", True, "pass"),
                         (got["settled"], got["reply_received"], got["review_conclusion"]["value"]),
                         "报告完整性结论改写了收尾/回复/结论这些独立事实")
        aggregate = measure_run.native_delegations(measure_run._native_sessions(self.run_dir))["delegations"]
        self.assertEqual((0, 1), (aggregate["story_review_full_replies"], aggregate["story_review_reports_unknown"]))
        # 同一个回复在历史载体下按当时的完整报告形态读取
        got = self.review(historical_like, dispatch="historical")
        self.assertEqual(("complete", "recorded_report"),
                         (got["report_completeness"]["value"], got["report_completeness"]["basis"]),
                         "有来源的历史派审样本不再按原身份读取")

    def test_only_a_successful_write_at_the_assigned_location_is_the_original(self) -> None:
        """写入参数与 final 相同也不够：工具返回错误、只有调用没有结果、写进别的相对目录、
        或写进另一个工作区的同名后缀，都不能证明本次报告文件存在；四种都记 unknown 并写明原因。"""
        body = self.current_report("pass")
        cases = {
            "工具返回错误": (self.write_rows(self.report_file(), body, outcome="error"), "返回错误"),
            "只有调用没有结果": (self.write_rows(self.report_file(), body, outcome="no_result"), "没有结果"),
            "别的相对目录": (self.write_rows("archive-copy/" + self.report_file(), body), "同名后缀不能跨目录"),
            "另一个工作区": (self.write_rows("/other-workspace/" + self.report_file(), body), "同名后缀不能跨目录"),
        }
        for name, (rows, why) in cases.items():
            with self.subTest(name):
                got = self.review(body, child_rows=rows)
                self.assertEqual(("unknown", None),
                                 (got["report_completeness"]["value"], got["report_completeness"]["basis"]),
                                 f"{name}：写入参数被当成了成功写入事实")
                self.assertIn(why, got["report_completeness"]["why"])
                self.assertEqual(("finished", True, "pass"),
                                 (got["settled"], got["reply_received"], got["review_conclusion"]["value"]),
                                 f"{name}：完整性结论改写了收尾/回复/结论这些独立事实")

    def test_an_absolute_write_inside_the_same_workspace_is_the_assigned_location(self) -> None:
        """读者按工作区绝对路径写本次报告文件，仍是所配位置：与整份 final 一致时计可核完整。"""
        body = self.current_report("pass")
        cwd = "/workspace"
        got = self.review(body, cwd=cwd,
                          child_rows=self.write_rows(f"{cwd}/{self.report_file()}", body))
        self.assertEqual(("complete", "reader_original"),
                         (got["report_completeness"]["value"], got["report_completeness"]["basis"]))

    def test_the_original_is_the_latest_successful_write(self) -> None:
        """同一位置写了两次：取最近一次成功写出的字节，不拿旧字节冒充；最后一次成功改动不是
        写出全文（edit）时重建不出原样正文；后面的失败写入不推翻已有的成功原件。"""
        first = self.current_report("pass")
        second = first + "\n补充：复核范围已核。\n"
        rows = (self.write_rows(self.report_file(), first, call_id="w1")
                + self.write_rows(self.report_file(), second, call_id="w2"))
        got = self.review(second, child_rows=rows)
        self.assertEqual(("complete", "reader_original"),
                         (got["report_completeness"]["value"], got["report_completeness"]["basis"]))
        got = self.review(first, child_rows=rows)
        self.assertEqual("unknown", got["report_completeness"]["value"], "拿旧一次写出的字节冒充原样")
        rows = (self.write_rows(self.report_file(), first, call_id="w1")
                + self.write_rows(self.report_file(), None, call_id="e1", name="edit"))
        got = self.review(second, child_rows=rows)
        self.assertEqual("unknown", got["report_completeness"]["value"])
        self.assertIn("不是写出全文", got["report_completeness"]["why"])
        rows = (self.write_rows(self.report_file(), second, call_id="w1")
                + self.write_rows(self.report_file(), second, call_id="w2", outcome="error"))
        got = self.review(second, child_rows=rows)
        self.assertEqual("complete", got["report_completeness"]["value"],
                         "后面的失败写入被当成了原件的否定证据")

    def test_a_recorded_report_is_still_read(self) -> None:
        """已保全的历史记录按当时的三个二级标题读出结论，旧报告格式按原身份读取仍算可核完整。"""
        got = self.review(self.report("fail\n\n理由。"), dispatch="historical")
        self.assertEqual(("fail", None), (got["review_conclusion"]["value"], got["review_conclusion"]["why"]))
        self.assertEqual({"value": "complete", "why": None, "basis": "recorded_report", "report_file": None},
                         got["report_completeness"], "旧报告格式不再被认作可核完整")

    def test_a_reply_that_is_not_the_whole_report_is_unknown(self) -> None:
        """收尾回复只是摘要（正文里写着「总体结论：warn」）、材料键不是派出去的那一份：都判不了，不从字样推断；
        取得过回复文本这一件事实照记，完整报告单列未知。"""
        summary = f"material_key: {self.KEY}\n\n## 判据核对\n\n（全文已发给父代理）\n\n**总体结论：warn**\n"
        got = self.review(summary)
        self.assertEqual(("unknown", True, "unknown"),
                         (got["review_conclusion"]["value"], got["reply_received"], got["report_completeness"]["value"]))
        loose = f"material_key: {self.KEY}\n\n结论：pass\n"
        self.assertEqual("unknown", self.review(loose)["review_conclusion"]["value"], "结论不在第二行也被读出来了")
        other = self.review(self.report("fail\n\n理由。"), key="b" * 64)
        self.assertEqual(("unknown", "回复的材料键对不上派出去的审查对象"),
                         (other["review_conclusion"]["value"], other["review_conclusion"]["why"]))
        self.assertEqual("unknown", other["report_completeness"]["value"], "材料键对不上被算成了完整报告")

    def test_the_report_counts_only_verified_reports_and_names_the_unverified(self) -> None:
        """报表消费者：旧的「Story 独审任务 …（完整回复 …，审查对象 …）」行保留，完整回复只计可核完整的那几份；
        未核证的回复单列并说明不是任务失败。完整的那一份有同次读者原件可对照。"""
        parent = "session-p"
        full = self.current_report("pass")
        head = (f"# Story 独立人读审查 · 派审\n\n- 材料键：`{self.KEY}`\n"
                f"- 本次报告文件：`{self.report_file()}`\n")
        rows: list[dict] = []
        for seq, child, reply in ((1, "k-pointer", "报告已写入\n"), (2, "k-full", full)):
            rows += self.spawn(seq, f"c{child}", child, head, "审查", settled=None)
            rows.append({"type": "agent/inbox/spliced", "time": (seq + 10) * 60000, "data": {"inserted": [{
                "content": [{"type": "text", "text": f"Background subagent {child} finished and will do no further work.\n"
                                                     "Its closing message:\n" + reply}],
                "source": {"kind": "subagent-settled", "senderSessionId": child,
                           "summary": f"Background subagent {child} finished and will do no further work."}}]}})
        _session(self.run_dir / "native-sessions" / parent / "session.v4.jsonl.zstd", parent, rows)
        _session(self.run_dir / "native-sessions" / parent / "children" / "k-full" / "session.v4.jsonl.zstd",
                 "k-full", self.write_rows(self.report_file(), full))
        (self.run_dir / "events.jsonl").write_text(
            json.dumps({"type": "usage", "timestamp": "2026-09-02T10:00:00", "usage": {"context_total": 1}}),
            encoding="utf-8")
        text = measure_run.render(measure_run.measure(self.run_dir / "events.jsonl", run_dir=self.run_dir))
        self.assertIn("Story 独审任务 2 个（完整回复 1 个，审查对象 1 个）", text)
        self.assertIn("取得回复文本 2 个", text)
        self.assertIn("未核证完整报告 1 个", text)
        self.assertIn("不是任务失败", text)


class KnowledgeDeliveriesAreReadFromTheTaskOutput(unittest.TestCase):
    """每次取知识任务送到了什么：从这次调用的输出读字节与第 4 块送到的正文文件与篇；输出被截断时是 unknown（None），不是 0。
    预期从这个工程的登记推：平铺维护 Feature 还没有知识判断时，受众可达的正文都送，上下篇知识在 plan 只送下篇。"""

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("环境里没有 node")
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import test_knowledge_task as kt  # noqa: PLC0415
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = kt.make_project(root=Path(cls._tmp.name) / "p")
        (cls.root / "doc" / "features" / "flat-start").mkdir(parents=True)
        cls.cmd = (f"node doc/extensions/hooks/shared/knowledge-task.mjs --project-root {cls.root.as_posix()} "
                   "--feature flat-start --action plan --audience reviewer")
        proc = subprocess.run(["node", str(cls.root / "doc/extensions/hooks/shared/knowledge-task.mjs"), "--project-root",
                               str(cls.root), "--feature", "flat-start", "--action", "plan", "--audience", "reviewer"],
                              capture_output=True, timeout=300)
        assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")[-600:]
        cls.output = proc.stdout.decode("utf-8")
        manifest = yaml.safe_load((cls.root / "doc/extensions/manifest.yaml").read_text(encoding="utf-8"))
        cls.registered = manifest["provides"]["knowledge"]

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def measured(self, output, **extra) -> list[dict]:
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            record = {"tool_name": "bash", "tool_input": {"command": self.cmd}, "tool_output": output, **extra}
            (run / "events.jsonl").write_text(json.dumps(_events(record)[0], ensure_ascii=False), encoding="utf-8")
            return measure_run.measure(run / "events.jsonl", run_dir=run)["knowledge_deliveries"]

    def test_the_bodies_and_bytes_of_one_task(self) -> None:
        [got] = self.measured(self.output)
        self.assertEqual(("flat-start", "plan", "reviewer"), (got["target"], got["action"], got["audience"]))
        self.assertEqual(len(self.output.encode("utf-8")), got["bytes"])
        def entry(k):
            path = k["path"] if isinstance(k, dict) else k
            return path
        files = [f"doc/extensions/{entry(k)}" for k in self.registered]
        self.assertEqual(sorted(files), sorted(b["file"] for b in got["bodies"]))
        halves = {b["file"]: b["part"] for b in got["bodies"]}
        for f in files:
            text = (self.root / f).read_text(encoding="utf-8")
            self.assertEqual("下篇" if "form: halves" in text else "全文", halves[f], f)

    def test_equivalent_command_spellings_give_the_same_record(self) -> None:
        """同一次取知识任务的几种合法写法：不加引号、双引号、单引号、等号；对象、动作、读者一致，字节与正文不变。
        值读不清（空值、引号没闭合）是 unknown，不猜。"""
        base = "node doc/extensions/hooks/shared/knowledge-task.mjs --project-root p"
        spellings = (f"{base} --feature flat-start --action plan --audience reviewer",
                     f'{base} --feature "flat-start" --action "plan" --audience "reviewer"',
                     f"{base} --feature 'flat-start' --action 'plan' --audience 'reviewer'",
                     f"{base} --feature=flat-start --action=plan --audience=reviewer")
        [reference] = self.measured(self.output)
        for cmd in spellings:
            with self.subTest(cmd=cmd):
                self.cmd = cmd
                self.assertEqual(reference, self.measured(self.output)[0])
        for cmd in (f'{base} --feature "" --action plan', f'{base} --feature "flat-start --action plan'):
            with self.subTest(cmd=cmd):
                self.cmd = cmd
                self.assertIsNone(self.measured(self.output)[0]["target"])

    def test_a_truncated_output_is_unknown(self) -> None:
        [got] = self.measured(self.output[:200], source_truncated=True)
        self.assertEqual((None, None), (got["bytes"], got["bodies"]))


class TruncatedPublicCallsAreCompletedByTheSameNativeCall(unittest.TestCase):
    """公共事件里截断的入参或缺失、截断的结果，由同一原生调用（同 callId、只在一个原生会话里、工具名一致）补齐后再分类计数；
    同一 callId 落在两个会话、或原生对它有两份不同结果时不补，照旧判不了。"""

    BUILD = "node doc/extensions/skills/story/scripts/core/story-build.mjs"

    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_dir = Path(self._tmp.name)

    def native(self, session: str, call_id: str, command: str, *results: str) -> None:
        rows = [{"type": "tool/call", "time": 1, "data": {"callId": call_id, "name": "pwsh",
                                                          "arguments": json.dumps({"command": command})}}]
        rows += [{"type": "tool/result", "time": 2 + i, "data": {"message": {
            "toolCallId": call_id, "content": [{"type": "text", "text": text}]}}} for i, text in enumerate(results)]
        _session(self.run_dir / "native-sessions" / session / "session.v4.jsonl.zstd", session, rows)

    def measure(self, *, input_cut: bool = True, output_cut: bool = False) -> dict:
        start = {"type": "tool", "tool_name": "pwsh", "tool_call_id": "call_x", "run_id": "r", "tool_status": "started",
                 "timestamp": "2026-11-03T01:19:02+08:00",
                 "tool_input": {"command": "$r = \"review-original.6.md\"\n$content = @'\nmaterial_key: 1"} if input_cut
                 else {"command": f"{self.BUILD} review --action check --feature X"}, "source_truncated": input_cut}
        end = {"type": "tool", "tool_call_id": "call_x", "run_id": "r", "tool_status": "completed",
               "timestamp": "2026-11-03T01:19:09+08:00",
               "tool_output": "report6 saved\n{\"res" if output_cut else "report6 saved\n{\"result\": \"report_invalid\"}",
               "source_truncated": output_cut}
        path = self.run_dir / "events.jsonl"
        path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in (start, end)) + "\n", encoding="utf-8")
        return measure_run.measure(path, run_dir=self.run_dir)

    def full(self) -> str:
        return f"$r = \"review-original.6.md\"\nWrite-Output saved\n{self.BUILD} review --action check --feature X"

    def test_the_cut_command_is_read_from_the_native_call(self) -> None:
        """入参被截断，命令落在截断的部分：原生完整入参补齐后，这次是审查结论检查，结论照公共结果计。"""
        self.native("session-p", "call_x", self.full(), "report6 saved\n{\"result\": \"report_invalid\"}")
        got = self.measure()
        self.assertEqual(1, got["tool_calls_completed_from_native"])
        self.assertEqual((1, 0), (got["gate_fail_by_kind"]["review_check"], got["gate_unknown_by_kind"]["review_check"]))
        self.assertEqual([], [i for i in got["incomplete_tool_events"] if i["reason"] == "source_truncated"])

    def test_a_cut_result_is_taken_from_the_one_native_result(self) -> None:
        self.native("session-p", "call_x", self.full(), "report8 saved\n{\"result\": \"warn\"}")
        got = self.measure(input_cut=False, output_cut=True)
        self.assertEqual({"warn": 1}, got["review_results"])
        self.assertEqual(0, got["gate_unknown_by_kind"]["review_check"])

    def test_an_ambiguous_native_record_is_not_used(self) -> None:
        """同一 callId 出现在两个原生会话：认不出是哪一次，不补，照旧是截断的 other。原生对它有两份不同结果：结果不挑，照旧判不了。"""
        self.native("session-p", "call_x", self.full(), "{\"result\": \"report_invalid\"}")
        self.native("session-q", "call_x", self.full(), "{\"result\": \"report_invalid\"}")
        got = self.measure()
        self.assertEqual((0, 0, 0), (got["tool_calls_completed_from_native"], got["gate_fail_by_kind"]["review_check"],
                                     got["gate_unknown_by_kind"]["review_check"]))
        shutil.rmtree(self.run_dir / "native-sessions")
        self.native("session-p", "call_x", self.full(), "{\"result\": \"report_invalid\"}", "{\"result\": \"warn\"}")
        got = self.measure(input_cut=False, output_cut=True)
        self.assertEqual((1, {}), (got["gate_unknown_by_kind"]["review_check"], got["review_results"]))


class S02IsolationAndReviewDispatchCounting(unittest.TestCase):
    """2.0.6 S02：隔离越界（相对路径按 cwd 解析、动态拼接/会话库访问、仅路径文字与实际读取分流）、
    常驻审查子代理跨 send_message 多轮派发与多次 settled 配对，以及执行脚本不误判读源码。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_dir = Path(self._tmp.name)

    def _run_measure(self, records: list[dict], *, workspace: str | None = None) -> dict:
        if workspace is not None:
            (self.run_dir / "state.json").write_text(json.dumps({"workspace": workspace}), encoding="utf-8")
        path = self.run_dir / "events.jsonl"
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in _events(*records)) + "\n", encoding="utf-8")
        return measure_run.measure(path, run_dir=self.run_dir)

    def test_executing_script_with_open_in_args_is_not_counted_as_reading_checker_source(self) -> None:
        got = self._run_measure([{
            "tool_name": "pwsh",
            "tool_input": {"command": 'python doc/extensions/skills/story/scripts/core/story_flow.py decide --answer "用户未确认 open(door) 策略"'},
            "tool_output": "ok",
        }])
        self.assertEqual(0, got["reads_checker_source"])

    def test_relative_escape_and_legitimate_parent_return_inside_workspace(self) -> None:
        ws = r"C:\Temp\sw-story\suite-1\car-key-sharing"
        got = self._run_measure([
            # 合法：cd framework/harness 后用 ../.. 回到本工作区根，不算越界
            {"tool_name": "pwsh",
             "tool_input": {"command": "cd framework/harness; npx ts-node scripts/harness-runner.ts --project-root ../.."},
             "tool_output": "ok"},
            # 仅出现路径文字无读取动作：归 mentions_only，不污染
            {"tool_name": "pwsh",
             "tool_input": {"command": "echo 'see ../auto-topup/doc/features for reference'"},
             "tool_output": "see ../auto-topup/doc/features for reference"},
            # 真实相对路径越界列旁案目录：confirmed_access → 污染
            {"tool_name": "pwsh",
             "tool_input": {"command": "Get-ChildItem ../auto-topup/doc/features -Recurse -File"},
             "tool_output": "doc\\features\\AR90006\\AR\\story.md"},
        ], workspace=ws)
        iso = got["isolation_boundary"]
        self.assertTrue(iso["contaminated"])
        self.assertEqual(["whole"], iso["contaminated_segments"])
        self.assertEqual(1, len(iso["findings"]))
        self.assertEqual("relative_escape", iso["findings"][0]["kind"])
        self.assertEqual("confirmed_access", iso["findings"][0]["access"])
        self.assertEqual(3, iso["findings"][0]["line"])
        self.assertIn("auto-topup/doc/features", iso["findings"][0]["resolved_path"])
        self.assertEqual(1, len(iso["mentions_only"]))
        self.assertEqual(2, iso["mentions_only"][0]["line"])

    def test_dynamic_host_session_store_access_is_detected(self) -> None:
        ws = r"C:\Temp\sw-story\suite-1\auto-topup"
        got = self._run_measure([
            {"tool_name": "pwsh",
             "tool_input": {"command": "const dirs=fs.readdirSync(process.env.USERPROFILE+'\\\\.dsh\\\\sessions');"},
             "tool_output": "session-1"},
        ], workspace=ws)
        iso = got["isolation_boundary"]
        self.assertTrue(iso["contaminated"])
        self.assertEqual("host_session_store_access", iso["findings"][0]["kind"])
        self.assertEqual("confirmed_access", iso["findings"][0]["access"])

    def test_persistent_subagent_dispatches_via_send_message_pair_each_settled_and_object(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("环境里没有 node")
        k1, k2 = "a" * 64, "b" * 64
        r1 = "doc/features/AR1/AR/story-src/review/review-original.1.md"
        r2 = "doc/features/AR1/AR/story-src/review/review-original.2.md"
        p1 = f"# Story 独立人读审查 · 派审\n\n- 材料键：`{k1}`\n- 本次报告文件：`{r1}`\n\n## 先首读\n"
        p2 = f"# Story 独立人读审查 · 派审（复核）\n\n- 材料键：`{k2}`\n- 本次报告文件：`{r2}`\n\n## 复核\n"
        body1 = f"material_key: {k1}\nconclusion: fail\n\n## 发现\n- 缺分支"
        body2 = f"material_key: {k2}\nconclusion: warn\n\n## 复核\n- 已修"
        child_uuid = "50d697b7-3e12-46ed-be67-5f0995f54c8a"
        q_uuid = "a113720c-c9b8-4208-b240-a2f50713bf11"
        parent_rows = [
            {"type": "subagent/catalog", "time": 1000, "data": {"childId": q_uuid, "label": "蓝图独立质询", "childCreatedAt": 1000}},
            {"type": "tool/call", "time": 1000, "data": {"callId": "c1", "name": "subagent",
             "arguments": json.dumps({"name": "questioner-1", "description": "蓝图独立质询", "prompt": "# 蓝图独立质询 · 派审\n"})}},
            {"type": "tool/result", "time": 1010, "data": {"message": {"toolCallId": "c1", "content": [{"type": "text", "text": "started subagent questioner-1"}]}}},
            {"type": "agent/inbox/spliced", "time": 2000, "data": {"inserted": [{"source": {"kind": "subagent-settled", "senderSessionId": q_uuid,
             "summary": "Background subagent questioner-1 finished"}, "content": [{"type": "text", "text": "Background subagent questioner-1 finished\nIts closing message:\nok1"}]}]}},
            {"type": "tool/call", "time": 3000, "data": {"callId": "c2", "name": "send_message",
             "arguments": json.dumps({"agent": "questioner-1", "message": "复核第二轮"})}},
            {"type": "agent/inbox/spliced", "time": 4000, "data": {"inserted": [{"source": {"kind": "subagent-settled", "senderSessionId": q_uuid,
             "summary": "Background subagent questioner-1 finished"}, "content": [{"type": "text", "text": "Background subagent questioner-1 finished\nIts closing message:\nok2"}]}]}},
            {"type": "subagent/catalog", "time": 5000, "data": {"childId": child_uuid, "label": "Story 独立人读审查", "childCreatedAt": 5000}},
            {"type": "tool/call", "time": 5000, "data": {"callId": "c3", "name": "subagent",
             "arguments": json.dumps({"name": "story-reviewer", "description": "Story 独立人读审查", "prompt": p1})}},
            {"type": "tool/result", "time": 5010, "data": {"message": {"toolCallId": "c3", "content": [{"type": "text", "text": "started subagent story-reviewer"}]}}},
            {"type": "agent/inbox/spliced", "time": 6000, "data": {"inserted": [{"source": {"kind": "subagent-settled", "senderSessionId": child_uuid,
             "summary": "Background subagent story-reviewer finished"}, "content": [{"type": "text", "text": f"Background subagent story-reviewer finished\nIts closing message:\n{body1}"}]}]}},
            {"type": "tool/call", "time": 7000, "data": {"callId": "c4", "name": "send_message",
             "arguments": json.dumps({"agent": "story-reviewer", "message": p2})}},
            {"type": "agent/inbox/spliced", "time": 8000, "data": {"inserted": [{"source": {"kind": "subagent-settled", "senderSessionId": child_uuid,
             "summary": "Background subagent story-reviewer finished"}, "content": [{"type": "text", "text": f"Background subagent story-reviewer finished\nIts closing message:\n{body2}"}]}]}},
        ]
        child_rows = [
            {"type": "tool/call", "time": 5500, "data": {"callId": "w1", "name": "write",
             "arguments": json.dumps({"file_path": r1, "content": body1})}},
            {"type": "tool/result", "time": 5510, "data": {"message": {"toolCallId": "w1", "isError": False, "content": [{"type": "text", "text": "ok"}]}}},
            {"type": "tool/call", "time": 7500, "data": {"callId": "w2", "name": "write",
             "arguments": json.dumps({"file_path": r2, "content": body2})}},
            {"type": "tool/result", "time": 7510, "data": {"message": {"toolCallId": "w2", "isError": False, "content": [{"type": "text", "text": "ok"}]}}},
        ]
        _session(self.run_dir / "native-sessions" / "session-p" / "session.v4.jsonl.zstd", "session-p", parent_rows)
        _session(self.run_dir / "native-sessions" / "session-p" / "children" / child_uuid / "session.v4.jsonl.zstd", child_uuid, child_rows)
        got = self._run_measure([{"tool_name": "read", "tool_input": {"filePath": "doc/features/AR1/AR/story.md"}}])
        d = got["delegations"]
        self.assertEqual((2, 2), (d["questioning_dispatches"], d["questioning_settled"]))
        self.assertEqual((2, 2, 2, 2), (d["story_review_dispatches"], d["story_review_objects"],
                                        d["story_review_unique_reports"], d["story_review_full_replies"]))
        self.assertEqual({"fail": 1, "warn": 1}, d["story_review_conclusions"])
        self.assertEqual({"first_read": 1, "recheck": 1}, d["story_review_modes"])


if __name__ == "__main__":
    unittest.main()
