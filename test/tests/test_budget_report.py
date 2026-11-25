# -*- coding: utf-8 -*-
"""budget_report 各指标的独立算例：合成小仓，预期值手算，不照抄实现。

仓的演变（有效行，`//` 注释不计）：
  base  hooks/a.mjs = A B C（另有一行注释）；skills/x.md = row1 row2；knowledge/k.md 不计量
  c1    a.mjs = A B2 C D                         → G2 X1
  c2    a.mjs = A C D；新增 skills/y.py 两行代码   → G2 X1
  工作区 x.md 第一行只改缩进                       → G1 X1，relocated 1
两端：base 5 行 → 工作区 7 行；endpoint G4 X2；invested G5 X3；churn G1 X1；总量峰值 7 首次出现在 c2。
包从 c1 起：invested G3 X2；endpoint 退出 B2（本版新增行）与 row1（基线保留行）各 1。
"""
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("budget_report", REPO / "test" / "scripts" / "budget_report.py")
br = importlib.util.module_from_spec(spec)
spec.loader.exec_module(br)


def run(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root,
                          check=True, capture_output=True, text=True).stdout.strip()


def write(root: Path, rel: str, text: str) -> None:
    p = root / "extensions" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


class SyntheticHistory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = cls.root = Path(cls.tmp.name)
        run(root, "init", "-q")
        write(root, "hooks/a.mjs", "// 说明\nA\nB\nC\n")
        write(root, "skills/x.md", "row1\nrow2\n")
        write(root, "knowledge/k.md", "k1\nk2\n")
        run(root, "add", "-A"); run(root, "commit", "-qm", "base")
        cls.base = run(root, "rev-parse", "HEAD")
        write(root, "hooks/a.mjs", "// 说明\nA\nB2\nC\nD\n")
        run(root, "commit", "-qam", "c1")
        cls.c1 = run(root, "rev-parse", "HEAD")
        write(root, "hooks/a.mjs", "// 说明\nA\nC\nD\n")
        write(root, "skills/y.py", '"""doc"""\nx = 1\ny = 2\n')
        run(root, "add", "-A"); run(root, "commit", "-qm", "c2")
        cls.c2 = run(root, "rev-parse", "HEAD")
        write(root, "skills/x.md", "  row1\nrow2\n")
        cls.ledger = root / "ledger.yaml"
        cls.ledger.write_text(yaml.safe_dump({
            "release": {"id": "t", "baseline_ref": cls.base, "control_g": 3},
            "requirement": {"status": "in_progress"},
            "categories": {"hooks_mjs": {"interim_ceiling": 4, "target": 3}},
            "total": {"interim_ceiling": 8, "target": 7},
            "packages": [
                {"id": "p", "start_ref": cls.c1, "approved_g": 2,
                 "scopes": {"钩子": ["hooks/*"], "技能": ["skills/*"]}},
                {"id": "p-ok", "start_ref": cls.c1, "approved_g": 2,
                 "confirmations": [{"band": "125–150%", "by": "reviewer", "at": "2026-10-25"}]},
                {"id": "p-no-by", "start_ref": cls.c1, "approved_g": 2,
                 "confirmations": [{"band": "125–150%", "at": "2026-10-25"}]},
                {"id": "p-blank-by", "start_ref": cls.c1, "approved_g": 2,
                 "confirmations": [{"band": "125–150%", "by": "  ", "at": "2026-10-25"}]},
            ]}, allow_unicode=True), encoding="utf-8")
        cls.r = br.build(root, cls.ledger, None, br.WORKTREE, "p", None)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_totals_by_category_skip_comments_and_uncounted(self):
        t = self.r["totals"]
        self.assertEqual(5, t["base"]["total"])
        self.assertEqual({"hooks_mjs": 3, "prompts_md": 2, "scripts_py": 2}, {k: v for k, v in t["to"]["by_category"].items() if v})
        self.assertEqual(7, t["to"]["total"])

    def test_endpoint_by_category_status_and_relocated(self):
        e = self.r["endpoint"]
        self.assertEqual((4, 2, 1), (e["total"]["G"], e["total"]["X"], e["total"]["relocated"]))
        self.assertEqual((1, 1), (e["by_category"]["hooks_mjs"]["G"], e["by_category"]["hooks_mjs"]["X"]))
        self.assertEqual("added", e["files"]["skills/y.py"]["status"])
        self.assertEqual(1, e["total"]["files_added"])
        self.assertNotIn("knowledge/k.md", e["files"])
        self.assertEqual({"hooks", "skills"}, set(e["by_module"]))

    def test_series_invested_churn_and_peak(self):
        self.assertEqual([self.c1, self.c2, br.WORKTREE], [s["at"] for s in self.r["series"]])
        self.assertEqual([(2, 1), (2, 1), (1, 1)], [(s["total"]["G"], s["total"]["X"]) for s in self.r["series"]])
        self.assertEqual((5, 3), (self.r["invested"]["total"]["G"], self.r["invested"]["total"]["X"]))
        self.assertEqual({"G": 1, "X": 1}, self.r["churn"])
        self.assertEqual({"value": 7, "at": self.c2}, self.r["peak"]["total"])
        self.assertEqual({"value": 4, "at": self.c1}, self.r["peak"]["by_category"]["hooks_mjs"])

    def test_identity_lists_uncommitted_counted_files(self):
        i = self.r["identity"]
        self.assertEqual(["extensions/skills/x.md"], i["uncommitted_counted"])
        self.assertEqual(4, i["delivered_files"]["total"])
        self.assertEqual(3, i["counted_files"]["total"])

    def test_package_r_band_and_x_origin(self):
        p = self.r["package"]
        self.assertEqual((3, 2), (p["invested"]["total"]["G"], p["invested"]["total"]["X"]))
        self.assertEqual((1, 1), (p["endpoint"]["total"]["X_retained"], p["endpoint"]["total"]["X_version_added"]))
        self.assertEqual((1.5, "125–150%", True), (p["control"]["R"], p["control"]["band"], p["control"]["confirmation_missing"]))
        self.assertEqual((0, 1), (p["endpoint"]["by_scope"]["钩子"]["G"], p["endpoint"]["by_scope"]["钩子"]["X"]))
        self.assertEqual(3, p["invested"]["by_scope"]["技能"]["G"])

    def test_named_confirmation_closes_the_band(self):
        r = br.build(self.root, self.ledger, None, br.WORKTREE, "p-ok", None)
        self.assertFalse(r["package"]["control"]["confirmation_missing"])
        self.assertEqual(1, len(r["package"]["control"]["confirmations"]))

    def test_confirmation_without_a_name_is_still_missing(self):
        for pid in ("p-no-by", "p-blank-by"):
            with self.subTest(pid):
                c = br.build(self.root, self.ledger, None, br.WORKTREE, pid, None)["package"]["control"]
                self.assertEqual(("125–150%", True, []), (c["band"], c["confirmation_missing"], c["confirmations"]))
                self.assertIn("缺具名确认", br.markdown(br.build(self.root, self.ledger, None, br.WORKTREE, pid, None)))

    def test_control_only_reports(self):
        c = self.r["control"]
        self.assertEqual({"id": "t", "G": 4, "control_g": 3, "within": False}, c["version"])
        self.assertEqual(("interim_ceiling", True), (c["categories"]["hooks_mjs"]["bound_in_force"], c["categories"]["hooks_mjs"]["within"]))

    def test_commit_endpoint_and_unknown_package(self):
        r = br.build(self.root, self.ledger, self.base, self.c2, None, 1)
        self.assertEqual((3, 1), (r["endpoint"]["total"]["G"], r["endpoint"]["total"]["X"]))
        self.assertEqual([], r["identity"]["uncommitted"])
        with self.assertRaises(br.ReportError):
            br.build(self.root, self.ledger, None, br.WORKTREE, "nope", None)


class SecondParentBaseline(unittest.TestCase):
    """基线在合并进来的第二父链上：endpoint 照算，逐提交序列不适用；包起点按自己是否在 first-parent 链上判定。

      base0  hooks/a.mjs = A B
      m1     （主线）新增 skills/x.md = r1                 主线总量 3
      s1     （支线，自 base0）a.mjs = A B C               支线总量 3
      M      合并 s1 进主线：a.mjs = A B C，x.md = r1      总量 4
    以 s1 为基线到 M：endpoint G1（x.md 一行）X0；series/invested/peak 不适用。
    包从 m1 起：endpoint 与 invested 都是 G1 X0（C 一行）；包从 s1 起：前置不成立。
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = cls.root = Path(cls.tmp.name)
        run(root, "init", "-q", "-b", "main")
        write(root, "hooks/a.mjs", "A\nB\n")
        run(root, "add", "-A"); run(root, "commit", "-qm", "base0")
        run(root, "checkout", "-qb", "side")
        write(root, "hooks/a.mjs", "A\nB\nC\n")
        run(root, "commit", "-qam", "s1")
        cls.s1 = run(root, "rev-parse", "HEAD")
        run(root, "checkout", "-q", "main")
        write(root, "skills/x.md", "r1\n")
        run(root, "add", "-A"); run(root, "commit", "-qm", "m1")
        cls.m1 = run(root, "rev-parse", "HEAD")
        run(root, "merge", "-q", "--no-ff", "-m", "M", "side")
        cls.merge = run(root, "rev-parse", "HEAD")
        cls.ledger = root / "ledger.yaml"
        cls.ledger.write_text(yaml.safe_dump({
            "release": {"id": "t", "baseline_ref": cls.s1, "control_g": 5},
            "requirement": {"status": "in_progress"},
            "packages": [{"id": "main-line", "start_ref": cls.m1, "approved_g": 10},
                         {"id": "side-line", "start_ref": cls.s1, "approved_g": 10}]}), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_endpoint_is_kept_and_the_series_is_not_applicable(self):
        r = br.build(self.root, self.ledger, None, self.merge, None, None)
        self.assertEqual((3, 4), (r["totals"]["base"]["total"], r["totals"]["to"]["total"]))
        self.assertEqual((1, 0), (r["endpoint"]["total"]["G"], r["endpoint"]["total"]["X"]))
        self.assertFalse(r["applicability"]["first_parent"])
        self.assertIn("invested 守恒检查", r["applicability"]["not_executed"])
        self.assertEqual((None, None, None, None), (r["series"], r["invested"], r["churn"], r["peak"]))
        self.assertIsNone(r["control"]["categories"]["total"]["peak"])
        self.assertEqual(1, r["control"]["version"]["G"])
        self.assertIn("不适用", br.markdown(r))

    def test_a_package_on_the_first_parent_line_is_still_counted(self):
        r = br.build(self.root, self.ledger, None, self.merge, "main-line", None)
        p = r["package"]
        self.assertEqual((1, 0), (p["endpoint"]["total"]["G"], p["endpoint"]["total"]["X"]))
        self.assertEqual((1, 0), (p["invested"]["total"]["G"], p["invested"]["total"]["X"]))
        self.assertEqual(0.1, p["control"]["R"])

    def test_a_package_starting_off_the_line_is_a_failed_precondition(self):
        with self.assertRaises(br.ReportError) as caught:
            br.build(self.root, self.ledger, None, self.merge, "side-line", None)
        self.assertIn("first-parent", str(caught.exception))

    def test_a_linear_baseline_keeps_the_series(self):
        r = br.build(self.root, self.ledger, self.m1, self.merge, None, None)
        self.assertTrue(r["applicability"]["first_parent"])
        self.assertEqual((1, 0), (r["invested"]["total"]["G"], r["invested"]["total"]["X"]))


class BaseLayoutMigration(unittest.TestCase):
    """2.0.6 目录搬迁到 `base/` 后的逻辑对齐、排除边界与双副本重复计量独立算例。

    演变（有效行）：
      base   hooks/a.mjs (3行: A B C)
             skills/x.md (2行: row1 row2)
             manifest.yaml (2行: name: d / version: 1)
             adaptation.yaml (1行: adapted_for: 1)
             knowledge/k.md (排除)
             skills/story/scripts/adapters/story.js (排除)
             → 总量 8 行（hooks_mjs 3, prompts_md 2, data 3）
      c1_pure_move:
             全部机制同字节搬入 base/（manifest.yaml -> base/package-manifest.yaml），
             旧路径删除，adaptation.yaml 退出外网交付（X1），
             另增排除项 base/.gitignore、base/examples/knowledge/facts/a.md、
             base/skills/story-adaptation/reference/upgrade-changes.md、adapters/story.js
             → 总量 7 行（hooks_mjs 3, prompts_md 2, data 2）；相对 base 逻辑 G0 / X1（仅 adaptation.yaml）
      c2_move_and_edit:
             在 base/hooks/a.mjs 改写 2 行并新增 1 行（B->B2, C->C2, +D → G3/X2）
             → 总量 8 行；相对 c1 G3/X2；相对 base G3/X3（a.mjs G3/X2 + adaptation.yaml X1）
      c3_duplicate_old_copy:
             在 c1 基础上恢复旧路径 hooks/a.mjs（与 base/hooks/a.mjs 同时存活）
             → 两份分别计量，hooks_mjs 变为 6 行、总量 10 行；报 duplicates["hooks/a.mjs"]
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = cls.root = Path(cls.tmp.name)
        run(root, "init", "-q", "-b", "main")
        write(root, "hooks/a.mjs", "A\nB\nC\n")
        write(root, "skills/x.md", "row1\nrow2\n")
        write(root, "manifest.yaml", "name: d\nversion: 1\n")
        write(root, "adaptation.yaml", "adapted_for: 1\n")
        write(root, "knowledge/k.md", "k1\n")
        write(root, "skills/story/scripts/adapters/story.js", "console.log(1);\n")
        run(root, "add", "-A"); run(root, "commit", "-qm", "base")
        cls.base = run(root, "rev-parse", "HEAD")

        # c1: 纯搬迁到 base/ + adaptation.yaml 退出 + 排除项
        for old in ("hooks/a.mjs", "skills/x.md", "manifest.yaml", "adaptation.yaml",
                    "knowledge/k.md", "skills/story/scripts/adapters/story.js"):
            (root / "extensions" / old).unlink()
        write(root, "base/hooks/a.mjs", "A\nB\nC\n")
        write(root, "base/skills/x.md", "row1\nrow2\n")
        write(root, "base/package-manifest.yaml", "name: d\nversion: 1\n")
        write(root, "base/.gitignore", "/examples/\n")
        write(root, "base/examples/knowledge/facts/a.md", "ex1\nex2\n")
        write(root, "base/skills/story-adaptation/reference/upgrade-changes.md", "u1\nu2\n")
        write(root, "adapters/story.js", "console.log(2);\n")
        run(root, "add", "-A"); run(root, "commit", "-qm", "c1_pure_move")
        cls.c1 = run(root, "rev-parse", "HEAD")

        # c2: 搬迁后改三行（改两行 + 增一行 → G3/X2）
        write(root, "base/hooks/a.mjs", "A\nB2\nC2\nD\n")
        run(root, "add", "-A"); run(root, "commit", "-qm", "c2_move_and_edit")
        cls.c2 = run(root, "rev-parse", "HEAD")

        # c3: 旧副本与新路径并存
        write(root, "hooks/a.mjs", "A\nB\nC\n")
        run(root, "add", "-A"); run(root, "commit", "-qm", "c3_dup")
        cls.c3 = run(root, "rev-parse", "HEAD")

        cls.ledger = root / "ledger.yaml"
        cls.ledger.write_text(yaml.safe_dump({
            "release": {"id": "2.0.6", "baseline_ref": cls.base, "control_g": 20},
            "requirement": {"status": "in_progress"},
            "packages": [{"id": "pkg", "start_ref": cls.base, "approved_g": 10,
                          "scopes": {"钩子": ["hooks/*"], "元数据": ["manifest.yaml", "adaptation.yaml"]}}],
        }, allow_unicode=True), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_pure_move_reports_relocation_with_zero_logical_g_and_only_adaptation_exits(self):
        r = br.build(self.root, self.ledger, self.base, self.c1, "pkg", None)
        e = r["endpoint"]
        self.assertEqual((8, 7), (r["totals"]["base"]["total"], r["totals"]["to"]["total"]))
        self.assertEqual((0, 1), (e["total"]["G"], e["total"]["X"]))
        self.assertEqual("removed", e["files"]["adaptation.yaml"]["status"])
        self.assertEqual(1, e["files"]["adaptation.yaml"]["X"])
        self.assertEqual("moved", e["files"]["base/hooks/a.mjs"]["status"])
        self.assertEqual("hooks/a.mjs", e["files"]["base/hooks/a.mjs"]["moved_from"])
        self.assertEqual("moved", e["files"]["base/package-manifest.yaml"]["status"])
        self.assertEqual("manifest.yaml", e["files"]["base/package-manifest.yaml"]["moved_from"])
        self.assertEqual(3, len(e["moved"]))
        for excluded in ("base/.gitignore", "base/examples/knowledge/facts/a.md",
                         "base/skills/story-adaptation/reference/upgrade-changes.md", "adapters/story.js"):
            self.assertNotIn(excluded, e["files"])
        self.assertEqual((0, 1), (r["invested"]["total"]["G"], r["invested"]["total"]["X"]))
        self.assertIn("base/package-manifest.yaml", br.markdown(r))
        self.assertIn("manifest.yaml", br.markdown(r))

    def test_move_plus_three_changed_rows_reports_exact_gx(self):
        r = br.build(self.root, self.ledger, self.base, self.c2, "pkg", None)
        e = r["endpoint"]
        self.assertEqual((3, 3), (e["total"]["G"], e["total"]["X"]))
        self.assertEqual((3, 2), (e["files"]["base/hooks/a.mjs"]["G"], e["files"]["base/hooks/a.mjs"]["X"]))
        self.assertEqual("moved_changed", e["files"]["base/hooks/a.mjs"]["status"])
        self.assertEqual("hooks/a.mjs", e["files"]["base/hooks/a.mjs"]["moved_from"])
        self.assertEqual((3, 2), (r["package"]["endpoint"]["by_scope"]["钩子"]["G"],
                                  r["package"]["endpoint"]["by_scope"]["钩子"]["X"]))

    def test_keeping_old_copy_counts_both_and_reports_duplicate(self):
        r = br.build(self.root, self.ledger, self.base, self.c3, "pkg", None)
        self.assertEqual(11, r["totals"]["to"]["total"])
        self.assertEqual(7, r["totals"]["to"]["by_category"]["hooks_mjs"])
        self.assertIn("hooks/a.mjs", r["endpoint"]["duplicates"])
        self.assertEqual(["base/hooks/a.mjs", "hooks/a.mjs"],
                         r["identity"]["duplicate_counted"]["hooks/a.mjs"])
        self.assertEqual(4, r["endpoint"]["files"]["base/hooks/a.mjs"]["G"])
        self.assertIn("重复并存", br.markdown(r))


class DuplicateExitAttribution(unittest.TestCase):
    """2.0.6 S14 R2：包起点原路径与新增副本同时并存时，删新增副本须计 X_version_added、
    不重复认领原路径基线来源；删原路径则核其真实基线来源 X_retained；仅唯一搬迁才继承基线来源。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = cls.root = Path(cls.tmp.name)
        run(root, "init", "-q", "-b", "main")
        # release 基线：仅旧路径 2 行
        write(root, "hooks/a.mjs", "line1\nline2\n")
        run(root, "add", "-A"); run(root, "commit", "-qm", "release_base")
        cls.rel_base = run(root, "rev-parse", "HEAD")

        # pkg_start（分支 A：并存）：新旧两路径同时存活
        write(root, "base/hooks/a.mjs", "line1\nline2\n")
        run(root, "add", "-A"); run(root, "commit", "-qm", "coexist_start")
        cls.coexist_start = run(root, "rev-parse", "HEAD")

        # 场景 1：并存后删新增的 base 副本，原路径完整保留 → X 全属本版新增（X_retained=0, X_version_added=2）
        (root / "extensions" / "base" / "hooks" / "a.mjs").unlink()
        run(root, "add", "-A"); run(root, "commit", "-qm", "delete_added_copy")
        cls.del_added = run(root, "rev-parse", "HEAD")

        # 场景 2：从 coexist_start 切新分支，删原路径保留 base 副本 → X 属退出原基线（X_retained=2, X_version_added=0）
        run(root, "checkout", "-qb", "drop-old", cls.coexist_start)
        (root / "extensions" / "hooks" / "a.mjs").unlink()
        run(root, "add", "-A"); run(root, "commit", "-qm", "delete_original_path")
        cls.del_old = run(root, "rev-parse", "HEAD")

        # 场景 3：从 rel_base 切新分支，先做唯一搬迁到 base/hooks/a.mjs，再删除 1 行基线 + 1 行新增 → X_retained=1, X_version_added=1
        run(root, "checkout", "-qb", "unique-move", cls.rel_base)
        (root / "extensions" / "hooks" / "a.mjs").unlink()
        write(root, "base/hooks/a.mjs", "line1\nline2\nadded3\n")
        run(root, "add", "-A"); run(root, "commit", "-qm", "unique_move_start")
        cls.unique_start = run(root, "rev-parse", "HEAD")
        write(root, "base/hooks/a.mjs", "line1\n")
        run(root, "add", "-A"); run(root, "commit", "-qm", "unique_move_trim")
        cls.unique_trim = run(root, "rev-parse", "HEAD")

        run(root, "checkout", "-q", "main")
        cls.ledger = root / "ledger.yaml"
        cls.ledger.write_text(yaml.safe_dump({
            "release": {"id": "2.0.6", "baseline_ref": cls.rel_base, "control_g": 20},
            "requirement": {"status": "in_progress"},
            "packages": [
                {"id": "coexist-pkg", "start_ref": cls.coexist_start, "approved_g": 10},
                {"id": "unique-pkg", "start_ref": cls.unique_start, "approved_g": 10},
            ],
        }, allow_unicode=True), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_deleting_added_duplicate_while_original_remains_is_all_version_added(self):
        r = br.build(self.root, self.ledger, self.rel_base, self.del_added, "coexist-pkg", None)
        p = r["package"]["endpoint"]
        self.assertEqual((0, 2), (p["total"]["G"], p["total"]["X"]))
        self.assertEqual((0, 2), (p["total"]["X_retained"], p["total"]["X_version_added"]))
        self.assertEqual(0, p["files"]["base/hooks/a.mjs"]["X_retained"])
        self.assertEqual(2, p["files"]["base/hooks/a.mjs"]["X_version_added"])
        self.assertIn("退出保留行 0、退出本版新增行 2", br.markdown(r))

    def test_deleting_original_while_duplicate_remains_is_retained_exit(self):
        r = br.build(self.root, self.ledger, self.rel_base, self.del_old, "coexist-pkg", None)
        p = r["package"]["endpoint"]
        self.assertEqual((0, 2), (p["total"]["G"], p["total"]["X"]))
        self.assertEqual((2, 0), (p["total"]["X_retained"], p["total"]["X_version_added"]))
        self.assertEqual(2, p["files"]["hooks/a.mjs"]["X_retained"])
        self.assertEqual(0, p["files"]["hooks/a.mjs"]["X_version_added"])
        self.assertIn("退出保留行 2、退出本版新增行 0", br.markdown(r))

    def test_unique_relocation_still_inherits_release_baseline_attribution(self):
        r = br.build(self.root, self.ledger, self.rel_base, self.unique_trim, "unique-pkg", None)
        p = r["package"]["endpoint"]
        self.assertEqual((0, 2), (p["total"]["G"], p["total"]["X"]))
        self.assertEqual((1, 1), (p["total"]["X_retained"], p["total"]["X_version_added"]))
        self.assertEqual((1, 1), (p["files"]["base/hooks/a.mjs"]["X_retained"],
                                  p["files"]["base/hooks/a.mjs"]["X_version_added"]))


if __name__ == "__main__":
    unittest.main()
