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


if __name__ == "__main__":
    unittest.main()
