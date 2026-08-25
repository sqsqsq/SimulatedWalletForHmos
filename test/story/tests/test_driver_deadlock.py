"""驱动器死锁三条回归。

这三条都属于「坏了看不出来」的机制：它们不会报错，只会让 Case 空转到预算耗尽，
而空转在日志里长得跟「模型在长思考」一模一样。2026-08-24 一次实跑里，
一个已经闭环的 spec 因为 verifier 报告换了个文件名而被判未闭环，
驱动器反复下发同一条推进指令 27 轮（该阶段上限本是 6），最终耗尽整轮时间。

跑法：python -m unittest discover -s test/story/tests
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "test" / "story" / "scripts"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPTS))

import run_case  # noqa: E402
import run_multi_case  # noqa: E402


class VerifierReportNaming(unittest.TestCase):
    """verifier 产物的**文件名不是契约**：认一组名字，任一存在即算闭环凭证。"""

    def setUp(self):
        self.tmp = REPO_ROOT / "doc" / "features" / "ZZTEST9001"
        self.reports = self.tmp / "spec" / "reports"
        self.reports.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_recognises_each_known_naming(self):
        for name in ("verifier.report.md", "verifier-report.yaml",
                     "verifier-spec-result.yaml", "verifier-spec.md"):
            for old in self.reports.iterdir():
                old.unlink()
            (self.reports / name).write_text("verdict: PASS\n", encoding="utf-8")
            self.assertIsNotNone(
                run_case.verifier_report("ZZTEST9001", "spec"),
                f"{name} 应被认作 verifier 凭证——命名一变就判未闭环会让 Case 空转")

    def test_absent_report_is_missing(self):
        for old in self.reports.iterdir():
            old.unlink()
        self.assertIsNone(run_case.verifier_report("ZZTEST9001", "spec"))
        ok, missing = run_case.phase_evidence_complete("ZZTEST9001", "spec")
        self.assertFalse(ok)
        self.assertIn("verifier 报告", missing)


class PhaseTurnBudget(unittest.TestCase):
    """阶段级预算存在且各阶段都有上限——只求和当全局上限等于没有阶段预算。"""

    def test_every_phase_has_a_budget(self):
        for phase in run_case.PHASE_ORDER:
            self.assertIn(phase, run_case.PHASE_TURNS,
                          f"{phase} 没有续话上限，卡在这一阶段时只能耗到全程预算用尽")
            self.assertGreater(run_case.PHASE_TURNS[phase], 0)

    def test_budget_source_is_read_by_loop(self):
        # 判据是「循环里真的按阶段计数并会中止」，不是「常量存在」——
        # 上一版常量存在却只被 sum() 用掉，阶段预算实际从未生效。
        src = (SCRIPTS / "run_case.py").read_text(encoding="utf-8")
        self.assertIn("phase_turn_budget_exhausted", src)
        self.assertIn("stuck_turns > limit", src)


class AwaitingReplyCadence(unittest.TestCase):
    """有 Case 在等回话时，观测间隔必须回到最短——等待期的每一秒都是白等的。"""

    def test_waiting_forces_interaction_interval(self):
        src = (SCRIPTS / "run_multi_case.py").read_text(encoding="utf-8")
        self.assertIn("any_waiting", src)
        self.assertLess(run_multi_case.INTERACTION_INTERVAL_SEC,
                        run_multi_case.AUTOMATION_INTERVAL_SEC)

    def test_adaptive_request_carries_question(self):
        # 只给状态、要宿主再去翻 runlog，一轮观测就变成两轮。
        src = (SCRIPTS / "run_multi_case.py").read_text(encoding="utf-8")
        self.assertIn('"question"', src)
        self.assertIn("case_inputs_hint", src)



class FrameworkIntegrityProvisioning(unittest.TestCase):
    """workspace 必须带上发布清单声明的占位文件——丢了会被判 framework 漂移。

    2026-08-24 实测：`WORKSPACE_EXCLUDED_DIR_NAMES` 用裸名 "state" 排除运行态目录，
    连带把 `framework/harness/state/.gitkeep` 丢掉，两个 Case 各花十几分钟排查
    framework_integrity BLOCKER。裸名排除还会误伤任何叫 state 的产品源码目录。
    """

    def test_stateful_dirs_are_path_scoped(self):
        self.assertNotIn("state", run_multi_case.WORKSPACE_EXCLUDED_DIR_NAMES,
                         "裸名排除会误伤同名的产品源码目录")
        self.assertIn("framework/harness/state", run_multi_case.WORKSPACE_STATEFUL_DIRS)

    def test_placeholder_is_kept(self):
        self.assertIn(".gitkeep", run_multi_case.WORKSPACE_STATEFUL_KEEP)


class SpecRequirementProvider(unittest.TestCase):
    """L2 完整流程的需求真源必须被 derive.requirement 认出来。

    上游只认 goal 入参与 lite 轨 change.md，于是手动 /spec（L2 正统入口）的需求
    永远解析不到 → functional 轴 UNVERIFIED → summary INCOMPLETE → 闭环被拒。
    本地热修（drift_allowlist 具名审批）补齐 AR/RR/SR 三个来源；本测试防止它再次
    在回退中被误删而无人察觉。
    """

    def test_provider_reads_full_track_docs(self):
        src = (REPO_ROOT / "framework" / "harness" / "scripts" / "utils"
               / "capability-resolution.ts").read_text(encoding="utf-8")
        head = src[src.index("case 'derive.requirement'"):][:2000]
        for doc in ("'AR', 'design.md'", "'RR', 'prd.md'", "'SR', 'design.md'"):
            self.assertIn(doc, head, f"derive.requirement 未覆盖 {doc}")

    def test_hotfix_is_named_approved(self):
        import json
        cfg = json.loads((REPO_ROOT / "framework.config.json").read_text(encoding="utf-8-sig"))
        allow = {e["path"]: e for e in cfg.get("integrity", {}).get("drift_allowlist", [])}
        entry = allow.get("harness/scripts/utils/capability-resolution.ts")
        self.assertIsNotNone(entry, "热修缺 drift_allowlist 具名审批，framework_integrity 会判漂移")
        self.assertTrue(entry.get("approved_by", "").strip())
        self.assertTrue(entry.get("rationale", "").strip())


if __name__ == "__main__":
    unittest.main()
