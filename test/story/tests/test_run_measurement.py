# -*- coding: utf-8 -*-
"""实跑观测的三条事实链：度量读的是真事件、阶段只由证据推进、材料版本认不认得出补图。

对应 P8 / P10 / P9。三者都属于**测试域自己的账**——观测错了，后面每一轮的结论都建在错数上，
而且错得毫无信号：旧口径的「反复 FAIL 的 check」在任何一份真实事件流上恒为空，看上去就像
「没有反复失败」。

每个指标都配**能改变结果的正反样本**：只测「有数据时算得出」，测不出「没数据时会不会凭空造数」。
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPTS = REPO / "test" / "story" / "scripts"
STORY_SCRIPTS = REPO / "doc" / "extensions" / "skills" / "story" / "scripts"

sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(STORY_SCRIPTS))
import materials  # noqa: E402
import measure_run  # noqa: E402
import phase_state  # noqa: E402
import story_flow  # noqa: E402

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
                           ".readFileSync('doc/extensions/skills/story/scripts/story-build.mjs',"
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

        实测反例：驱动器在 `gates_started` 把 `end_phase` 当观测阶段写进状态，
        于是两个 Case 在没有任何 plan 产物时被报成到达 plan。
        """
        state = self._state()
        state["phase_intent"] = {"phase": "plan", "event": "gates_started"}
        result = phase_state.derive_phase_state(self.ws, self.feature, state)
        self.assertEqual("story", result["current_phase"])
        self.assertEqual("story", result["highest_phase_reached"])

    def test_framework_state_advances(self):
        """正样本：framework 自己说到了 spec → 抬升。"""
        self._write_framework_phase("spec")
        result = phase_state.derive_phase_state(self.ws, self.feature, self._state())
        self.assertEqual("spec", result["current_phase"])
        self.assertEqual("framework_current_phase", result["phase_source"])

    def test_real_artifact_advances(self):
        """正样本：真产物落盘 → 抬升。"""
        art = self.ws / "doc/features" / self.feature / "spec" / "spec.md"
        art.parent.mkdir(parents=True)
        art.write_text("# spec", encoding="utf-8")
        result = phase_state.derive_phase_state(self.ws, self.feature, self._state())
        self.assertEqual("spec", result["highest_phase_reached"])
        self.assertEqual("phase_artifact", result["phase_source"])

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
        return materials.compute_digest(materials.collect_materials(root))

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

        按 TEST.md §2.2，图片进来只有一条路：人给的 docx 里内嵌，导入时抽出来落
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
        images = [m for m in materials.collect_materials(root) if m["kind"] == "image"]
        self.assertEqual(1, len(images), "同一张图被登记成了两张")
        self.assertEqual(["assets/supp/image1.png", "ux-reference/签约页.png"],
                         images[0]["paths"], "两个落点没有都记下来")


class BatchFiveArtifactsStayVersioned(unittest.TestCase):
    """只做回归确认，不另建第二份状态记录。"""

    def test_batch5_design_dir_is_tracked(self):
        d = REPO / "test/story/design/2026-08-25-story分批次交付/batch-5-实跑问题诊断"
        self.assertTrue(d.is_dir())
        proc = subprocess.run(["git", "check-ignore", str(d / "STATUS.md")],
                              cwd=str(REPO), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual("", proc.stdout.strip(), "批次 5 方案目录被 .gitignore 吞了")

    def test_golden_output_has_a_single_canonical_copy(self):
        """金样**输出**只有一处正本；fixture 里只留构造场景所需的原始输入。

        两者区别不是目录名而是性质：`golden/` 是被对照的成品（story / review / 归档图），
        `fixtures/golden/AR90004/` 是喂进去的单据与素材。输出一旦有第二份副本，
        改了哪一份、对照的又是哪一份，就再也说不清。
        """
        golden = REPO / "test/story/golden"
        for canonical in ("assets/image1.png", "assets/image2.png",
                          "story-金样-AR90004.md", "review-金样-AR90006.md"):
            self.assertTrue((golden / canonical).exists(), f"金样正本缺 {canonical}")

        fixture_root = REPO / "test/story/fixtures/golden"
        strays = [p.relative_to(REPO).as_posix() for p in fixture_root.rglob("*")
                  if p.is_file() and p.name in {"story.md", "review.md"}]
        self.assertEqual([], strays, f"fixture 里出现了金样输出副本：{strays}")


if __name__ == "__main__":
    unittest.main()
