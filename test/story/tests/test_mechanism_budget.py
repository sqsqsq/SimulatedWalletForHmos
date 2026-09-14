# -*- coding: utf-8 -*-
"""机制层当前规模检查；超限处置按test/story/AGENTS.md §5。

**数的是代码行，注释与空行不计**。配额限的是机制的规模，不是文字的长短——把注释算进配额，
省下来的只会是解释，而解释正是下一个维护者判断「这条判据还该不该在」的依据。

它不按步骤拦中间态：需求进行中只核「没超过方案自己声明的峰值 interim_ceiling」；需求完成
（requirement.status = closed）时核「回到完成后上限 target 以内」。语义代理标识不分进行中与完成——
那是方向不是规模，任何时候都不得增长。当前检查尚未接入新增预算的分级复核，
不能将这里的峰值比例当成维护规约的 100%/125%/150% 的新增实现比例。
"""
import ast
import re
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]

# 在实际报错时送达项目准则；不改变当前测量算法或阈值。
REMINDER = (
    "\n\n【预算用于防走偏，不用于裁剪正常功能】按 test/story/AGENTS.md §5，核重复实现、补丁叠加、旧机制未退与功能干扰；"
    "同时核方案是否错误、遗漏或不够直接。不要删能力、测试或说明凑数，也不要只抬预算换绿。"
    "记录实际新增、退出与差额，按本项目维护分级规则交对应角色复核。"
    "当前脚本仍查既有峰值/总量，尚未计算新增预算分级；不得用本次总量比例代替新增实现比例。"
)
EXT = REPO / "doc" / "extensions"
BUDGET = REPO / "test" / "story" / "regression" / "mechanism-budget.yaml"


def classify(path: Path) -> str | None:
    """这个文件算不算进机制规模。

    不算的三类：知识层（内容归目标工程）、依赖目录，以及**安装期工具**——
    `skills/story-adaptation/**` 是把这套机制装到别的工程去的东西，装完就不参与任何
    一次需求；预算限的是「本需求的机制有多大」，把安装器算进去，等于让「更好装」和
    「机制更小」互相挤占（用户 2026-09-05 裁定）。
    """
    rel = path.relative_to(EXT).as_posix()
    if rel.startswith("knowledge/") or "node_modules" in path.parts:
        return None
    if rel.startswith("skills/story-adaptation/"):
        return None
    # 点开头的目录是工作件，不随包交付
    if any(seg.startswith(".") for seg in rel.split("/")[:-1]):
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


def code_lines(path: Path) -> int:
    """这个文件有多少行**代码**——注释与空行不算。

    配额限的是机制的规模，不是文字的长短。把注释算进去，省下来的只会是解释，
    而解释正是下一个维护者判断「这条判据还该不该在」的依据。

    各类文件的注释形态不同，逐类剥：
      · `.mjs` —— `//` 起头的行与 `/* */` 块；
      · `.py`  —— `#` 起头的行与三引号 docstring；
      · `.yaml`—— `#` 起头的行；
      · `.json`—— 说明键（键名以 `_` 开头或以 `note` 结尾）；
      · `.md`  —— 提示词正文本身就是内容，只去空行。
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    suffix = path.suffix
    if suffix == ".mjs":
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        rows = [ln for ln in text.split("\n") if not ln.lstrip().startswith("//")]
    elif suffix == ".py":
        rows = _python_code_rows(text)
    elif suffix in (".yaml", ".yml"):
        rows = [ln for ln in text.split("\n") if not ln.lstrip().startswith("#")]
    elif suffix == ".json":
        rows = [ln for ln in text.split("\n")
                if not re.match(r'\s*"(?:_[^"]*|[^"]*note)"\s*:', ln)]
    else:
        rows = text.split("\n")
    return sum(1 for ln in rows if ln.strip())


def _python_code_rows(text: str) -> list[str]:
    """去掉 `#` 行与 docstring。docstring 用 ast 定位，靠猜引号会把普通字符串也剥掉。"""
    rows = text.split("\n")
    drop: set[int] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [ln for ln in rows if not ln.lstrip().startswith("#")]
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = getattr(node, "body", None) or []
        first = body[0] if body else None
        if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            drop.update(range(first.lineno - 1, (first.end_lineno or first.lineno)))
    return [ln for i, ln in enumerate(rows)
            if i not in drop and not ln.lstrip().startswith("#")]


def measure() -> tuple[dict[str, int], dict[str, list[Path]]]:
    lines: dict[str, int] = {}
    files: dict[str, list[Path]] = {}
    for p in sorted(EXT.rglob("*")):
        if not p.is_file():
            continue
        cat = classify(p)
        if cat is None:
            continue
        lines[cat] = lines.get(cat, 0) + code_lines(p)
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
        """脚本里再出现相似度/复述/最短引文这类词，就是又在用字符串近似语义。

        **只数可执行的那部分**：注释里交代「这条路径为什么退场」正是该写的话
        （`test_writing_flow` 的同类判据是同一口径）。把退场理由一起数进来，
        下一轮就只能靠删掉注释过关——那时代码里没有这些词，而知道它们为什么不该回来的
        那段文字也没了。
        """
        sp = self.budget["semantic_proxy"]
        pat = re.compile(sp["pattern"], re.I)
        hits: dict[str, int] = {}
        for cat in sp["scope"]:
            for p in self.files.get(cat, []):
                code = "\n".join(
                    ln for ln in p.read_text(encoding="utf-8", errors="replace").split("\n")
                    if not ln.lstrip().startswith(("//", "*", "/*", "#")))
                n = len(pat.findall(code))   # 同「只数代码行」那把尺子
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
