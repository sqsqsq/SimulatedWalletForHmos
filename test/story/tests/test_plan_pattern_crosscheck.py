"""spec §11 判命中的候选，在 plan 有没有给结论——以及不选时有没有写理由。

实测一轮：spec §11 正确命中了两条候选（业务信号真实），plan 用「演示仓储一步完成」
「加节点表会扩大文件面」把它们否了——拿临时承载形态当信号输入。否决在闭环内完成，
没有任何人过目。

这条判据只判**形式**两件事：命中的候选有没有行、不选时理由列空不空。
「理由引的是业务信号还是承载形态」是语义，归 verifier 逐问——用措辞正则去拦，
拦出来的是换一种说法的同一件事（上一轮已经实测过一次躲避）。
所以 F4 那两条**不该**被这条判据点名，它们有行也有理由；本文件因此正反两面都验：
真实存档不被误拦，构造的缺行与空理由被点名。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPO_ROOT / "doc" / "extensions" / "hooks" / "plan" / "post_check.mjs"
ARCHIVE = (REPO_ROOT / "test" / "story" / "design" / "2026-08-25-story分批次交付"
           / "batch-4-评审载体内容与表达" / "F4-形机器化与review承载" / "实跑-1"
           / "car-key-sharing" / "artifact")
FEATURE = "ISSUE-206"

DRIVER = """
import { pathToFileURL } from 'node:url';
const [hookPath, feature, projectRoot] = process.argv.slice(-3);
const hook = (await import(pathToFileURL(hookPath).href)).default;
const out = await hook({ phase: 'plan', feature, projectRoot });
process.stdout.write(JSON.stringify(out));
"""


class PlanPatternCrossCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("环境里没有 node")
        if not (ARCHIVE / "plan" / "plan.md").is_file():
            raise unittest.SkipTest("F4 实跑存档不在，跳过（判据本身由构造反例守）")

    def workspace(self) -> Path:
        """把存档摆成一个 projectRoot：doc/extensions + doc/features/<feature>。"""
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        shutil.copytree(REPO_ROOT / "doc" / "extensions", tmp / "doc" / "extensions")
        shutil.copytree(ARCHIVE, tmp / "doc" / "features" / FEATURE)
        return tmp

    def run_hook(self, root: Path) -> str:
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", DRIVER, "--",
             str(HOOK), FEATURE, str(root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(REPO_ROOT), timeout=120)
        self.assertEqual(0, proc.returncode, proc.stderr)
        payload = json.loads(proc.stdout or "{}")
        return payload.get("message") or ""

    @staticmethod
    def plan_path(root: Path) -> Path:
        return root / "doc" / "features" / FEATURE / "plan" / "plan.md"

    def test_the_archive_is_not_falsely_named(self) -> None:
        """存档的两条候选有行也有理由——形式判不该碰它们。

        它们的病是「理由引的是承载形态」，那一格归 verifier；机器在这里越权下语义结论，
        换来的只是模型换一种说法。
        """
        message = self.run_hook(self.workspace())
        self.assertNotIn("plan 的设计模式选型表里没有这一行", message)
        self.assertNotIn("理由列是空的", message)

    def test_a_hit_candidate_missing_from_the_plan_table_is_named(self) -> None:
        """漏掉一行，那条候选就在闭环里悄悄消失了。"""
        root = self.workspace()
        path = self.plan_path(root)
        rows = path.read_text(encoding="utf-8").split("\n")
        keep = [r for r in rows if "decision-tree" not in r or not r.strip().startswith("|")]
        self.assertLess(len(keep), len(rows), "存档变了：选型表里没有 decision-tree 那一行")
        path.write_text("\n".join(keep), encoding="utf-8")
        self.assertIn("plan 的设计模式选型表里没有这一行", self.run_hook(root))

    def test_an_unselected_candidate_without_a_reason_is_named(self) -> None:
        """不选是表态有后果的决策——理由列不能空。"""
        root = self.workspace()
        path = self.plan_path(root)
        rows = path.read_text(encoding="utf-8").split("\n")
        hit = next(i for i, r in enumerate(rows)
                   if r.strip().startswith("|") and "decision-tree" in r)
        cells = rows[hit].strip().strip("|").split("|")
        cells[-1] = " "
        rows[hit] = "|" + "|".join(cells) + "|"
        path.write_text("\n".join(rows), encoding="utf-8")
        message = self.run_hook(root)
        self.assertIn("理由列是空的", message)
        self.assertIn("业务信号的反证", message)

    def test_no_candidate_rows_do_not_trigger(self) -> None:
        """spec 全写「无候选」时本判据不响——零命中是正常结论，不是遗漏。"""
        root = self.workspace()
        spec = root / "doc" / "features" / FEATURE / "spec" / "spec.md"
        rows = spec.read_text(encoding="utf-8").split("\n")
        out = []
        for r in rows:
            if r.strip().startswith("|") and ("decision-tree" in r or "page-interaction" in r):
                cells = r.strip().strip("|").split("|")
                cells[1] = " 无候选 "
                r = "|" + "|".join(cells) + "|"
            out.append(r)
        spec.write_text("\n".join(out), encoding="utf-8")
        message = self.run_hook(root)
        self.assertNotIn("设计模式选型表里没有这一行", message)
        self.assertNotIn("理由列是空的", message)


if __name__ == "__main__":
    unittest.main()
