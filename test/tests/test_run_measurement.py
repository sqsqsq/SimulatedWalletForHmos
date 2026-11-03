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
        for key in ("duration_min", "model_gap_sec", "tool_gap_sec", "verifier_gap_sec"):
            self.assertIn(key, second)


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
            case = repo / "doc/plan/2.1.0/主题/金样候选/demo-case"
            feature = case / "doc/features/ISSUE-1"
            (feature / "AR").mkdir(parents=True)
            (feature / "ux-reference").mkdir()
            (feature / "ux-reference/设置页.png").write_bytes(b"page")
            (feature / "AR/story.md").write_text("![设置页](../ux-reference/%E8%AE%BE%E7%BD%AE%E9%A1%B5.png)\n",
                                                 encoding="utf-8")
            self.assertEqual([], self.stray_evidence(repo), "Story 引用的候选配图不是运行证据")

            base = "doc/plan/2.1.0/主题/金样候选/demo-case/"
            (feature / "ux-reference/没人引用.png").write_bytes(b"x")
            (feature / "ux-reference/只在说明里.png").write_bytes(b"y")
            (case / "README.md").write_text("![图](doc/features/ISSUE-1/ux-reference/只在说明里.png)\n", encoding="utf-8")
            (feature / "blueprint").mkdir()
            (feature / "blueprint/blueprint.target.md").write_text("![图](../ux-reference/没人引用.png)\n",
                                                                    encoding="utf-8")
            other = case / "doc/features/ISSUE-2/ux-reference/别的需求.png"
            other.parent.mkdir(parents=True)
            other.write_bytes(b"z")
            outside = repo / "doc/plan/2.1.0/主题/截图.png"
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
                              base + "doc/features/ISSUE-2/ux-reference/别的需求.png", "doc/plan/2.1.0/主题/截图.png",
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


def _session(path: Path, session_id: str, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plain = path.with_suffix(".plain")
    plain.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in
                                [{"type": "session", "version": 4, "id": session_id, "cwd": "w"}, *rows]) + "\n", encoding="utf-8")
    subprocess.run(["node", "-e", ZSTD, str(plain), str(path)], check=True)
    plain.unlink()


class NativeDelegationsAreReadByWhatWasSent(unittest.TestCase):
    """委派的角色按原生会话里实际派出去的正文与子会话实际产出认，不按工具名或 label：
    产品载体 → 那一类审查；写了需求 blueprint/ 下的设计产物 → 蓝图作者；专用 verifier → 阶段审查；其余 unresolved。
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
                {"type": "tool/call", "time": 5, "data": {"callId": "c4", "name": "verifier", "arguments": "{}"}}]
        _session(base / "session.v4.jsonl.zstd", parent, rows)
        _session(base / "children" / "k-author" / "session.v4.jsonl.zstd", "k-author", [
            {"type": "tool/call", "time": 1, "data": {"callId": "w", "name": "write",
                                                      "arguments": json.dumps({"file_path": "doc/features/X/blueprint/contracts/a.yaml"})}}])
        _session(base / "children" / "k-other" / "session.v4.jsonl.zstd", "k-other", [
            {"type": "tool/call", "time": 1, "data": {"callId": "r", "name": "read", "arguments": json.dumps({"file_path": "src/a.ets"})}}])
        got = measure_run.native_delegations(self.run_dir)["delegations"]
        self.assertEqual({"story_review": 1, "blueprint_author": 1, "unresolved": 1, "stage_verifier": 1}, got["by_role"])
        by_child = {i["child_id"]: i for i in got["items"]}
        self.assertEqual((10.0, "finished"), (by_child["k-review"]["observed_span_min"], by_child["k-review"]["settled"]))
        self.assertEqual("failed", by_child["k-author"]["settled"])
        self.assertEqual((None, "unknown"), (by_child["k-other"]["observed_span_min"], by_child["k-other"]["settled"]),
                         "没有收尾通知的跨度被当成了一个数")

    def test_without_kept_sessions_the_roles_are_unknown(self) -> None:
        self.assertIsNone(measure_run.native_delegations(self.run_dir)["delegations"])

if __name__ == "__main__":
    unittest.main()
