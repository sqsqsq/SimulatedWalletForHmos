# -*- coding: utf-8 -*-
"""机制层预算门：一次完整需求对 doc/extensions（knowledge 之外）规模的承诺（规则见 AGENTS §7.5）。

它不按步骤拦中间态：需求进行中只核「没超过方案自己声明的峰值 interim_ceiling」；需求完成
（requirement.status = closed）时核「回到完成后上限 target 以内」。语义代理标识不分进行中与完成——
那是方向不是规模，任何时候都不得增长。红了先读报错里指的 AGENTS 条款；为了过门禁砍方案，才是错。
"""
import re
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]

# 每条红都带这一段：门禁的作用是把人叫回 AGENTS 的要求前面，不是让人把方案砍到门禁以内。
REMINDER = (
    "\n\n【这条红是提醒，不是裁剪令】先回 test/story/AGENTS.md 看两处：§4.2 模型与脚本按能力分工、"
    "§7.5 一次完整需求的规模预算。"
    "峰值估错就回方案改 test/story/regression/mechanism-budget.yaml 的 interim_ceiling 并写 reason；"
    "完成时压不到 target 就回开退场步骤，或由用户签字改 target。"
    "新增脚本行须归 D2 §4 的某一类确定性失败；为了过门禁去砍方案、拆功能、少写测试，才是错。"
)
EXT = REPO / "doc" / "extensions"
BUDGET = REPO / "test" / "story" / "regression" / "mechanism-budget.yaml"


def classify(path: Path) -> str | None:
    rel = path.relative_to(EXT).as_posix()
    if rel.startswith("knowledge/") or "node_modules" in path.parts:
        return None
    suf = path.suffix
    if rel.startswith("skills/") and suf == ".mjs":
        return "scripts_mjs"
    if rel.startswith("skills/") and suf == ".py":
        return "scripts_py"
    if rel.startswith("hooks/") and suf == ".mjs":
        return "hooks_mjs"
    if suf == ".md":
        return "prompts_md"
    if suf in (".json", ".yaml", ".yml"):
        return "data"
    return None


def measure() -> tuple[dict[str, int], dict[str, list[Path]]]:
    lines: dict[str, int] = {}
    files: dict[str, list[Path]] = {}
    for p in sorted(EXT.rglob("*")):
        if not p.is_file():
            continue
        cat = classify(p)
        if cat is None:
            continue
        n = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
        lines[cat] = lines.get(cat, 0) + n
        files.setdefault(cat, []).append(p)
    return lines, files


class MechanismBudget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.budget = yaml.safe_load(BUDGET.read_text(encoding="utf-8"))
        cls.lines, cls.files = measure()

    def bound(self, entry: dict) -> tuple[int, str]:
        """进行中看方案声明的峰值；完成后看完成上限。"""
        closed = str(self.budget["requirement"]["status"]).strip() == "closed"
        if closed:
            return int(entry["target"]), "完成后上限 target（需求已 closed）"
        return int(entry["interim_ceiling"]), "方案声明的峰值 interim_ceiling（需求进行中）"

    def test_every_budget_line_is_signed(self):
        """预算是纪律不是数字：每一项都要有人签、有理由，和 drift_allowlist 同一套要求。"""
        entries = dict(self.budget["categories"])
        entries["total"] = self.budget["total"]
        for name, e in entries.items():
            with self.subTest(name):
                self.assertTrue(str(e.get("approved_by") or "").strip(), f"{name} 缺 approved_by")
                self.assertTrue(str(e.get("reason") or "").strip(), f"{name} 缺 reason")
                self.assertIsInstance(e.get("interim_ceiling"), int)
                self.assertIsInstance(e.get("target"), int)
        req = self.budget["requirement"]
        self.assertIn(req.get("status"), ("in_progress", "closed"))
        self.assertTrue(str(req.get("approved_by") or "").strip())
        sp = self.budget["semantic_proxy"]
        self.assertTrue(str(sp.get("approved_by") or "").strip())
        self.assertIsInstance(sp.get("ceiling"), int)

    def test_each_category_is_within_bound(self):
        for name, e in self.budget["categories"].items():
            with self.subTest(name):
                actual = self.lines.get(name, 0)
                limit, why = self.bound(e)
                self.assertLessEqual(actual, limit, f"{name} 现在 {actual} 行，超过{why} {limit}。" + REMINDER)

    def test_total_is_within_bound(self):
        total = sum(self.lines.values())
        limit, why = self.bound(self.budget["total"])
        self.assertLessEqual(total, limit, f"机制层总量 {total} 行，超过{why} {limit}。" + REMINDER)

    def test_semantic_proxy_identifiers_do_not_grow(self):
        """脚本里再出现相似度/复述/最短引文这类词，就是又在用字符串近似语义。"""
        sp = self.budget["semantic_proxy"]
        pat = re.compile(sp["pattern"], re.I)
        hits: dict[str, int] = {}
        for cat in sp["scope"]:
            for p in self.files.get(cat, []):
                n = len(pat.findall(p.read_text(encoding="utf-8", errors="replace")))
                if n:
                    hits[p.relative_to(EXT).as_posix()] = n
        total = sum(hits.values())
        self.assertLessEqual(
            total, sp["ceiling"],
            f"语义代理标识 {total} 处，预算 {sp['ceiling']}：{hits}。"
            "这些词出现在脚本里，说明有人又在用字符串近似「讲清没讲清」——不合入" + REMINDER)

    def test_interim_is_not_below_target(self):
        """峰值不能低于完成上限——否则「进行中」比「完成」还严，说明两个数写反了。"""
        for name, e in self.budget["categories"].items():
            with self.subTest(name):
                self.assertGreaterEqual(e["interim_ceiling"], e["target"])


if __name__ == "__main__":
    unittest.main()
