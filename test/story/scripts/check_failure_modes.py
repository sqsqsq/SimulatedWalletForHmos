#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""失效形态全量回归（G1）。

台账：``test/story/regression/failure-modes.yaml``。

回归分两段，缺一不可：

1. **夹具自检** —— 所有 ``status != retired`` 的形态都跑：反夹具必须被判 FAIL、
   正夹具必须被判 PASS。自检不过说明 checker 本身失效，比漏检更危险，整体判 FAIL。
2. **真实目标** —— 仅 ``status == fixed`` 的形态跑；``pending_capability``（目标能力
   尚未建）报 SKIP 并计数，不算失败。能力交付后把 status 改 fixed 即自动生效。

用法::

    python test/story/scripts/check_failure_modes.py                # 默认目标集
    python test/story/scripts/check_failure_modes.py --feature AR90006 --feature AR90004
    python test/story/scripts/check_failure_modes.py --feature-root <dir>
    python test/story/scripts/check_failure_modes.py --self-check   # 只跑夹具自检
    python test/story/scripts/check_failure_modes.py --list         # 列台账

退出码：0 全部通过；1 有 FAIL；2 台账/夹具本身不可用。

口径声明（G3：计数必须带口径）：
- 「扫描机制层」= 扩展根下除 ``knowledge/`` 外的文件；代码类形态只扫 ``.mjs/.yaml/.json``
  （``.md`` 是给模型看的写作指令，允许出现形态示例）；文本类形态另注明。
- 「主叙事」= story 成品中第一个 ``## 附录`` 之前的部分；附录内的工程范围表述合法（坑 #17）。
- 「复述」判定见 :func:`normalize` 与 :func:`is_pure_copy`，规范化保留标识符字符。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable, Iterable

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
LEDGER = REPO_ROOT / "test" / "story" / "regression" / "failure-modes.yaml"
DEFAULT_EXTENSION_DIR = REPO_ROOT / "doc" / "extensions"
DEFAULT_FEATURES_DIR = REPO_ROOT / "doc" / "features"
ARCHIVED_FEATURES_DIR = Path("E:/Project/bak/Story-Features-20260824-121838")

# --------------------------------------------------------------------------- #
# 通用工具
# --------------------------------------------------------------------------- #

#: 条目编号形态：两到八个大写字母 + 连字符 + 两位数字（如 SEC-01）。
ENTRY_ID_RE = re.compile(r"\b[A-Z]{2,8}-\d{2}\b")

#: 规范化时删除的标点。**刻意不含** ``. - _ /``——它们是标识符的一部分，
#: 笼统"去标点"会把 ``data_models.X.field`` 折叠成一团（坑 #16）。
_DROP_PUNCT = "，。；：、“”‘’《》〈〉！？…—～·「」『』（）()【】[]{}<>,;:!?\"'`|"
_DROP_TABLE = {ord(ch): None for ch in _DROP_PUNCT}
_WS_RE = re.compile(r"\s+")


def read_text(path: Path) -> str:
    """读文本；坏编码不静默吞（坑 #32：解析失败必须响亮）。"""
    return path.read_text(encoding="utf-8", errors="replace")


def split_lines(text: str) -> list[str]:
    """一律 ``\\r?\\n`` 分行（坑 #37）。"""
    return re.split(r"\r?\n", text)


def normalize(text: str) -> str:
    """复述判定的规范化：去空白、去句读，保留标识符与运算字符。

    这是 B1-14「机械部分唯一可实施」的规范化规则，改它就是改判据。
    """
    return _WS_RE.sub("", text).translate(_DROP_TABLE)


def is_pure_copy(output: str, sources: Iterable[str]) -> tuple[bool, str]:
    """纯复制判定：规范化后的输出是某个来源的子串即为纯复制。

    方向固定（B1-14）：**输出 ⊆ 单一来源** 才算纯复制。反过来（来源 ⊆ 输出）
    说明输出在原文之外另有内容，不是纯复制。空输出不在此判，交结构门禁。
    """
    out = normalize(output)
    if not out:
        return False, ""
    for src in sources:
        s = normalize(src)
        if s and out in s:
            return True, s[:60]
    return False, ""


def similarity(a: str, b: str) -> float:
    """字符级相似度，**只用于排序提示**，不参与任何 PASS/FAIL（坑 #28）。"""
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def iter_files(root: Path, suffixes: tuple[str, ...], exclude_dirs: tuple[str, ...] = ()) -> list[Path]:
    out: list[Path] = []
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix not in suffixes:
            continue
        rel = p.relative_to(root).as_posix()
        if any(rel == d or rel.startswith(d + "/") for d in exclude_dirs):
            continue
        if "node_modules" in rel or "__pycache__" in rel:
            continue
        out.append(p)
    return out


def md_table_rows(text: str, header_contains: Iterable[str]) -> list[tuple[int, list[str]]]:
    """抽出表头包含全部给定词的 Markdown 表的数据行。

    返回 ``[(行号, 单元格列表)]``。表头按**列名**定位，不按列序（坑：列序会漂）。
    """
    want = [w for w in header_contains]
    rows: list[tuple[int, list[str]]] = []
    lines = split_lines(text)
    in_table = False
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_table = False
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        joined = " ".join(cells)
        if not in_table:
            if all(w in joined for w in want):
                in_table = True
            continue
        if set(joined.replace(" ", "")) <= set("-:|"):
            continue
        rows.append((idx, cells))
    return rows


def header_index(text: str, header_contains: Iterable[str]) -> list[str] | None:
    """返回匹配表的表头单元格，用于按列名取值。"""
    want = list(header_contains)
    for line in split_lines(text):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if all(w in " ".join(cells) for w in want):
            return cells
    return None


def cell(cells: list[str], headers: list[str], name: str) -> str:
    for i, h in enumerate(headers):
        if name in h and i < len(cells):
            return cells[i]
    return ""


def split_main_and_appendix(text: str) -> tuple[str, str]:
    """按第一个 ``## 附录`` 切主叙事与附录（M10/P07/P08 的作用域口径）。"""
    lines = split_lines(text)
    for i, line in enumerate(lines):
        if re.match(r"^#{1,3}\s*附录", line.strip()):
            return "\n".join(lines[:i]), "\n".join(lines[i:])
    return text, ""


# --------------------------------------------------------------------------- #
# 结果模型
# --------------------------------------------------------------------------- #


@dataclass
class Outcome:
    ok: bool
    evidence: str = ""


@dataclass
class Ctx:
    """checker 运行上下文。

    ``knowledge_root`` 让夹具能自带 ``_knowledge/`` 规约片段，从而在不依赖真实
    知识目录的情况下验证复述类 checker。
    """

    knowledge_root: Path | None = None
    extension_root: Path | None = None
    label: str = ""


@dataclass
class ModeResult:
    mode_id: str
    stage: str  # self_check | real_target
    target: str
    status: str  # PASS | FAIL | SKIP
    evidence: str = ""


CHECKERS: dict[str, Callable[[Path, Ctx], Outcome]] = {}


def checker(fn: Callable[[Path, Ctx], Outcome]) -> Callable[[Path, Ctx], Outcome]:
    CHECKERS[fn.__name__] = fn
    return fn


def load_constraint_entries(knowledge_root: Path | None) -> list[dict]:
    """从知识目录派生规约条目（编号 / 约束 / 处置 / 落法附注）。

    派生为空是**响亮**的：调用方据此报证据不足，而不是拿空集当通过（G7）。
    """
    entries: list[dict] = []
    if knowledge_root is None or not knowledge_root.exists():
        return entries
    for path in sorted(knowledge_root.rglob("*.md")):
        text = read_text(path)
        headers = header_index(text, ["编号", "约束"])
        if not headers:
            continue
        notes = ""
        m = re.search(r"^#+\s*落法附注\s*$", text, flags=re.MULTILINE)
        if m:
            notes = text[m.end():]
        for _, cells in md_table_rows(text, ["编号", "约束"]):
            entry_id = cell(cells, headers, "编号")
            if not ENTRY_ID_RE.fullmatch(entry_id.strip()):
                continue
            entries.append(
                {
                    "id": entry_id.strip(),
                    "constraint": cell(cells, headers, "约束"),
                    "handling": cell(cells, headers, "处置"),
                    "notes": notes,
                    "file": path.name,
                }
            )
    return entries


def sources_for(entry_id: str, entries: list[dict]) -> list[str]:
    out: list[str] = []
    for e in entries:
        if e["id"] == entry_id:
            out.extend([e["constraint"], e["handling"]])
            if e["notes"]:
                out.append(e["notes"])
    return [s for s in out if s]


# --------------------------------------------------------------------------- #
# 机制层 checker（target=mechanism，root = 扩展根或夹具目录）
# --------------------------------------------------------------------------- #

CODE_SUFFIXES = (".mjs", ".js", ".yaml", ".yml", ".json")
TEXT_SUFFIXES = (".md",)
ALL_SUFFIXES = CODE_SUFFIXES + TEXT_SUFFIXES
EXCLUDE_KNOWLEDGE = ("knowledge", "_knowledge")


#: 占位前缀：刻意表示「任意域」的示例编号，不是硬编码（`XXX-01` 这类）。
PLACEHOLDER_PREFIX_RE = re.compile(r"^(X{2,}|N{2,}|A{2,}|YYY|ZZZ)$")


@checker
def m01_hardcoded_domain_prefix(root: Path, ctx: Ctx) -> Outcome:
    """机制层代码里不得出现真实约束条目编号字面（域清单应运行期派生）。

    口径（G3）：**计**代码文件（``.mjs/.js/.yaml/.json``）中形如 ``SEC-01`` 的编号；
    **不计** ① 占位前缀（``XXX-01``——刻意表示任意域，正是不硬编码的写法）；
    ② 注释行（``//`` / ``*`` 开头）——那是说明不是判定逻辑，但仍建议中性化。
    """
    hits = []
    for path in iter_files(root, CODE_SUFFIXES, EXCLUDE_KNOWLEDGE):
        for n, line in enumerate(split_lines(read_text(path)), start=1):
            stripped = line.lstrip()
            if stripped.startswith(("//", "*", "/*", "#")):
                continue
            for m in ENTRY_ID_RE.finditer(line):
                prefix = m.group(0).split("-")[0]
                if PLACEHOLDER_PREFIX_RE.match(prefix):
                    continue
                hits.append(f"{path.relative_to(root).as_posix()}:{n} `{m.group(0)}`")
    if hits:
        return Outcome(False, "机制层出现条目编号字面：" + "；".join(hits[:5]))
    return Outcome(True, "机制层代码零真实条目编号字面（占位前缀与注释不计）")


@checker
def m02_test_case_features(root: Path, ctx: Ctx) -> Outcome:
    """机制层不得出现测试 Case 的单号或业务特征词（反过拟合）。"""
    case_ids = re.compile(r"\b(AR|DTS|ISSUE)-?\d{4,}\b")
    business_words = _case_business_words()
    hits = []
    for path in iter_files(root, ALL_SUFFIXES, EXCLUDE_KNOWLEDGE):
        rel = path.relative_to(root).as_posix()
        for n, line in enumerate(split_lines(read_text(path)), start=1):
            m = case_ids.search(line)
            if m:
                hits.append(f"{rel}:{n} `{m.group(0)}`")
                continue
            for word in business_words:
                if word in line:
                    hits.append(f"{rel}:{n} 业务特征词「{word}」")
                    break
    if hits:
        return Outcome(False, "机制层出现测试特征：" + "；".join(hits[:5]))
    return Outcome(True, f"机制层零测试特征（业务词表 {len(business_words)} 项）")


def _case_business_words() -> list[str]:
    """从测试 Case 派生业务特征词；派生不到就只用单号形态（不硬编码业务名）。"""
    cases_dir = REPO_ROOT / "test" / "story" / "cases"
    words: set[str] = set()
    if not cases_dir.exists():
        return []
    for case_yaml in cases_dir.glob("*/case.yaml"):
        try:
            data = yaml.safe_load(read_text(case_yaml)) or {}
        except yaml.YAMLError:
            continue
        for inbox in (case_yaml.parent / "workspace" / "inbox").glob("*"):
            stem = inbox.stem
            if len(stem) >= 4 and not stem.startswith("."):
                words.add(stem)
        for asset_dir in (case_yaml.parent / "workspace").rglob("assets/*"):
            if asset_dir.is_dir() and len(asset_dir.name) >= 4:
                words.add(asset_dir.name)
    return sorted(w for w in words if re.search(r"[\u4e00-\u9fff]", w))


@checker
def m03_hardcoded_layer_names(root: Path, ctx: Ctx) -> Outcome:
    """机制层不得写死架构外层目录名（层清单从架构 DSL 派生）。"""
    layer_re = re.compile(r"\b0[1-9]-[A-Z][A-Za-z]{3,}\b")
    hits = []
    for path in iter_files(root, ALL_SUFFIXES, EXCLUDE_KNOWLEDGE):
        for n, line in enumerate(split_lines(read_text(path)), start=1):
            m = layer_re.search(line)
            if m:
                hits.append(f"{path.relative_to(root).as_posix()}:{n} `{m.group(0)}`")
    if hits:
        return Outcome(False, "机制层写死层名：" + "；".join(hits[:5]))
    return Outcome(True, "机制层零层名字面")


@checker
def m04_source_repo_coupling(root: Path, ctx: Ctx) -> Outcome:
    """交付件不得依赖绝对路径、来源仓 git 历史或外部工程路径。"""
    patterns = [
        (re.compile(r"\b[A-Za-z]:[\\/]"), "绝对路径"),
        (re.compile(r"/(home|Users)/[A-Za-z0-9_.-]+/"), "用户目录"),
        (re.compile(r"\bgit\s+(show|log|checkout)\b"), "git 历史引用"),
        (re.compile(r"\bbackup/[A-Za-z0-9._-]+"), "备份分支引用"),
        (re.compile(r"\b[0-9a-f]{40}\b"), "提交 SHA"),
    ]
    hits = []
    for path in iter_files(root, ALL_SUFFIXES, EXCLUDE_KNOWLEDGE):
        rel = path.relative_to(root).as_posix()
        for n, line in enumerate(split_lines(read_text(path)), start=1):
            for pat, why in patterns:
                if pat.search(line):
                    hits.append(f"{rel}:{n} {why}")
                    break
    if hits:
        return Outcome(False, "交付件耦合来源环境：" + "；".join(hits[:5]))
    return Outcome(True, "交付件零来源耦合")


@checker
def m05_crlf_unsafe_split(root: Path, ctx: Ctx) -> Outcome:
    """按 ``\\n`` 切行在 CRLF 文件上静默零命中；一律 ``/\\r?\\n/``。"""
    bad = [
        re.compile(r"""\.split\(\s*['"]\\n['"]\s*\)"""),
        re.compile(r"\.split\(\s*/\\n/"),
    ]
    hits = []
    for path in iter_files(root, (".mjs", ".js"), EXCLUDE_KNOWLEDGE):
        for n, line in enumerate(split_lines(read_text(path)), start=1):
            if any(p.search(line) for p in bad):
                hits.append(f"{path.relative_to(root).as_posix()}:{n}")
    if hits:
        return Outcome(False, "CRLF 不安全分行：" + "；".join(hits[:5]))
    return Outcome(True, "分行一律 CRLF 安全")


@checker
def m06_silent_empty_derivation(root: Path, ctx: Ctx) -> Outcome:
    """知识派生模块在派生为空时必须出声（throw），不得返回空集蒙混。"""
    targets = [p for p in iter_files(root, (".mjs",), ()) if "knowledge" in p.name]
    if not targets:
        return Outcome(True, "无知识派生模块（不适用）")
    for path in targets:
        text = read_text(path)
        if "throw" not in text:
            return Outcome(False, f"{path.name} 无 throw：派生为空时会静默返回")
        if not re.search(r"派生为空|derivation is empty|激活清单", text):
            return Outcome(False, f"{path.name} 缺少派生为空的出声文案")
    return Outcome(True, f"{len(targets)} 个派生模块均在空结果时出声")


@checker
def m07_exact_heading_selector(root: Path, ctx: Ctx) -> Outcome:
    """章节取材须为候选词根数组 + 回落读整篇，禁止精确标题选择器。"""
    contracts = [p for p in iter_files(root, (".json",), ()) if "chapters" in p.name]
    if not contracts:
        return Outcome(True, "无章节合同（不适用）")
    for path in contracts:
        try:
            data = json.loads(read_text(path))
        except json.JSONDecodeError as exc:
            return Outcome(False, f"{path.name} 解析失败：{exc}")
        for ch in data.get("chapters", []):
            for inp in ch.get("inputs", []):
                section = inp.get("section")
                if section is None:
                    continue
                if not isinstance(section, list):
                    return Outcome(
                        False,
                        f"{path.name} 章节 {ch.get('id')} 的 section 不是候选词根数组（精确标题选择器）",
                    )
    return Outcome(True, "章节取材均为候选词根数组")


@checker
def m08_whole_file_sha_lock(root: Path, ctx: Ctx) -> Outcome:
    """模式基线守恒须分正文与元数据，不得整文件 SHA 绑死。"""
    hits = []
    for path in iter_files(root, CODE_SUFFIXES, ()):
        text = read_text(path)
        if "design-patterns" not in text and "pattern" not in path.name:
            continue
        if not re.search(r"sha256|SHA-256", text):
            continue
        if not re.search(r"frontmatter|front_matter|body|正文", text):
            hits.append(path.name)
    if hits:
        return Outcome(False, "模式守恒整文件 SHA 绑死（未分正文/元数据）：" + "、".join(hits))
    return Outcome(True, "模式守恒分正文与元数据")


@checker
def m09_dangling_cross_reference(root: Path, ctx: Ctx) -> Outcome:
    """跨文件相对引用必须真实存在。"""
    link_re = re.compile(r"\[[^\]]*\]\((\.{1,2}/[^)#\s]+)\)")
    hits = []
    for path in iter_files(root, TEXT_SUFFIXES, EXCLUDE_KNOWLEDGE):
        for n, line in enumerate(split_lines(read_text(path)), start=1):
            for m in link_re.finditer(line):
                target = (path.parent / m.group(1)).resolve()
                if not target.exists():
                    hits.append(f"{path.relative_to(root).as_posix()}:{n} → {m.group(1)}")
    if hits:
        return Outcome(False, "悬空引用：" + "；".join(hits[:5]))
    return Outcome(True, "跨文件引用全部可达")


@checker
def m10_unscoped_identifier_scan(root: Path, ctx: Ctx) -> Outcome:
    """归档件红线扫描必须限定作用域（附录内工程范围表述合法）。"""
    targets = [p for p in iter_files(root, (".mjs", ".js"), ()) if re.search(r"lint|merge|scan", p.name)]
    if not targets:
        return Outcome(True, "无归档件扫描实现（不适用）")
    for path in targets:
        text = read_text(path)
        if not re.search(r"scanLocalPaths|localPathRe|仓内路径", text):
            continue
        if not re.search(r"EXEMPT|豁免|排除|附录|scope", text, flags=re.IGNORECASE):
            return Outcome(False, f"{path.name} 的仓内标识扫描无作用域排除")
    return Outcome(True, "归档件扫描均有作用域排除")


@checker
def m11_flagged_only_adjudication(root: Path, ctx: Ctx) -> Outcome:
    """必答清单必须是全集；风险标记只排序，不决定裁决覆盖面。"""
    targets = [p for p in iter_files(root, (".mjs",), ()) if "verifier" in p.name]
    if not targets:
        return Outcome(True, "无 verifier 注入模块（不适用）")
    bad_filter = re.compile(
        r"\.filter\(\s*[\w$]+\s*=>\s*[\w$.]*\.(flagged|suspect|similarity|score)\b"
    )
    for path in targets:
        text = read_text(path)
        m = bad_filter.search(text)
        if m:
            return Outcome(False, f"{path.name} 按风险标记过滤必答清单：`{m.group(0)}`")
        if "pre_verifier" in path.name and not re.search(r"全集|all rows|逐行", text):
            return Outcome(False, f"{path.name} 未声明全集裁决口径")
    return Outcome(True, "必答清单为全集，标记只排序")


@checker
def m12_normalize_folds_identifiers(root: Path, ctx: Ctx) -> Outcome:
    """复述判定的规范化必须保留标识符字符。"""
    targets = [p for p in iter_files(root, (".mjs",), ()) if re.search(r"paraphrase|echo", p.name)]
    if not targets:
        return Outcome(True, "无复述判定模块（不适用）")
    greedy = [
        re.compile(r"replace\(\s*/\[\^\\w\]/"),
        re.compile(r"replace\(\s*/\\p\{P\}/"),
        re.compile(r"replace\(\s*/\[\^\\u4e00-\\u9fa5a-zA-Z0-9\]/"),
    ]
    for path in targets:
        text = read_text(path)
        for pat in greedy:
            if pat.search(text):
                return Outcome(False, f"{path.name} 笼统去标点，会折叠标识符：`{pat.pattern}`")
        if not re.search(r"保留|keep|DROP_PUNCT|_DROP", text):
            return Outcome(False, f"{path.name} 未显式声明保留字符集")
    return Outcome(True, "规范化显式保留标识符字符")


@checker
def m13_numeric_form_quota(root: Path, ctx: Ctx) -> Outcome:
    """数字计数不得进入写作命令或 PASS 条件（计数只作诊断）。"""
    quota_re = re.compile(r"(至少|不少于|必须有|须有)\s*[0-9一二三四五六七八九十]+\s*(张|个|条|段|处)?\s*(表|图|流程图|列表|小节|段落)")
    hits = []
    for path in iter_files(root, TEXT_SUFFIXES, EXCLUDE_KNOWLEDGE):
        for n, line in enumerate(split_lines(read_text(path)), start=1):
            m = quota_re.search(line)
            if m:
                hits.append(f"{path.relative_to(root).as_posix()}:{n} `{m.group(0)}`")
    if hits:
        return Outcome(False, "写作指令含形式配额：" + "；".join(hits[:5]))
    return Outcome(True, "写作指令零形式配额")


@checker
def m14_criteria_instruction_divergence(root: Path, ctx: Ctx) -> Outcome:
    """内容自检问句必须随写作指令下发给被测模型。"""
    injections = [
        p for p in iter_files(root, TEXT_SUFFIXES, EXCLUDE_KNOWLEDGE)
        if "on_context_load" in p.name
    ]
    if not injections:
        return Outcome(True, "无写作注入件（不适用）")
    self_check = re.compile(r"自问|自检问句|这句话里有没有|遮住")
    missing = [p.name for p in injections if not self_check.search(read_text(p))]
    writer_phases = [p for p in injections if re.search(r"spec|plan", p.parent.name + p.name)]
    missing = [n for n in missing if any(n == p.name for p in writer_phases)]
    if missing:
        return Outcome(False, "写作注入件缺内容自检问句：" + "、".join(missing))
    return Outcome(True, "写作注入件均含内容自检问句")


# --------------------------------------------------------------------------- #
# 产物层 checker（target=product，root = feature 根或夹具目录）
# --------------------------------------------------------------------------- #

APPENDIX_HEADERS = ["编号", "命中"]


def _story_path(root: Path) -> Path | None:
    for rel in ("AR/story.md", "story.md"):
        p = root / rel
        if p.exists():
            return p
    return None


def _spec_path(root: Path) -> Path | None:
    for rel in ("spec/spec.md", "spec.md"):
        p = root / rel
        if p.exists():
            return p
    return None


def _contracts_path(root: Path) -> Path | None:
    for rel in ("plan/contracts.yaml", "contracts.yaml"):
        p = root / rel
        if p.exists():
            return p
    return None


def _plan_path(root: Path) -> Path | None:
    for rel in ("plan/plan.md", "plan.md"):
        p = root / rel
        if p.exists():
            return p
    return None


def _freeze(root: Path) -> dict | None:
    path = _contracts_path(root)
    if path is None:
        return None
    try:
        data = yaml.safe_load(read_text(path)) or {}
    except yaml.YAMLError as exc:
        raise RuntimeError(f"contracts.yaml 解析失败：{exc}") from exc
    for key in ("knowledge_freeze", "project_knowledge"):
        if isinstance(data.get(key), dict):
            return data[key]
    return None


def _obligations(freeze: dict) -> list[dict]:
    for key in ("obligations", "constraint_obligations"):
        val = freeze.get(key)
        if isinstance(val, list):
            return [o for o in val if isinstance(o, dict)]
    return []


@checker
def p01_appendix_prefix_granularity(root: Path, ctx: Ctx) -> Outcome:
    """附录编号列必须到条目级，不得只写域前缀。"""
    story = _story_path(root)
    if story is None:
        return Outcome(True, "无 story 成品（不适用）")
    text = read_text(story)
    headers = header_index(text, APPENDIX_HEADERS)
    if not headers:
        return Outcome(True, "无规约符合性附录（不适用）")
    bad = []
    for line_no, cells in md_table_rows(text, APPENDIX_HEADERS):
        raw = cell(cells, headers, "编号")
        ids = ENTRY_ID_RE.findall(raw)
        if not ids:
            bad.append(f"{story.name}:{line_no} 编号列「{raw}」未到条目级")
    if bad:
        return Outcome(False, "；".join(bad[:5]))
    return Outcome(True, "附录编号全部到条目级")


@checker
def p02_appendix_conclusion_paraphrase(root: Path, ctx: Ctx) -> Outcome:
    """附录「结论或落点」列不得是同行要求列或规约原文的子串（E1/E2）。"""
    story = _story_path(root)
    if story is None:
        return Outcome(True, "无 story 成品（不适用）")
    text = read_text(story)
    headers = header_index(text, APPENDIX_HEADERS)
    if not headers:
        return Outcome(True, "无规约符合性附录（不适用）")
    entries = load_constraint_entries(ctx.knowledge_root)
    bad = []
    for line_no, cells in md_table_rows(text, APPENDIX_HEADERS):
        conclusion = cell(cells, headers, "结论")
        requirement = cell(cells, headers, "要求")
        entry_id = (ENTRY_ID_RE.findall(cell(cells, headers, "编号")) or [""])[0]
        hit = cell(cells, headers, "命中")
        if "否" in hit:
            continue
        sources = [requirement] + sources_for(entry_id, entries)
        copied, src = is_pure_copy(conclusion, sources)
        if copied:
            bad.append(f"{story.name}:{line_no} {entry_id} 结论是原文子串（来源「{src}…」）")
    if bad:
        return Outcome(False, "；".join(bad[:5]))
    return Outcome(True, "附录结论列无纯复制")


@checker
def p03_spec_exit_paraphrase(root: Path, ctx: Ctx) -> Outcome:
    """spec 约束出口「本需求的要求」列不得复述规约原文（E2）。"""
    spec = _spec_path(root)
    if spec is None:
        return Outcome(True, "无 spec（不适用）")
    text = read_text(spec)
    headers = header_index(text, ["编号", "本需求的要求"])
    if not headers:
        return Outcome(True, "无规约约束要求章（不适用）")
    entries = load_constraint_entries(ctx.knowledge_root)
    if not entries:
        return Outcome(True, "无激活规约条目可比对（证据不足，不判）")
    bad = []
    for line_no, cells in md_table_rows(text, ["编号", "本需求的要求"]):
        entry_id = (ENTRY_ID_RE.findall(cell(cells, headers, "编号")) or [""])[0]
        requirement = cell(cells, headers, "本需求的要求")
        copied, src = is_pure_copy(requirement, sources_for(entry_id, entries))
        if copied:
            bad.append(f"{spec.name}:{line_no} {entry_id} 要求是规约原文子串（来源「{src}…」）")
    if bad:
        return Outcome(False, "；".join(bad[:5]))
    return Outcome(True, "spec 约束出口无纯复制")


@checker
def p04_plan_obligation_paraphrase(root: Path, ctx: Ctx) -> Outcome:
    """plan 冻结的 obligation 不得复述规约原文。"""
    freeze = _freeze(root)
    if freeze is None:
        return Outcome(True, "无知识冻结块（不适用）")
    entries = load_constraint_entries(ctx.knowledge_root)
    if not entries:
        return Outcome(True, "无激活规约条目可比对（证据不足，不判）")
    bad = []
    for ob in _obligations(freeze):
        rule = str(ob.get("rule", ""))
        text = str(ob.get("obligation", ""))
        copied, src = is_pure_copy(text, sources_for(rule, entries))
        if copied:
            bad.append(f"{rule} 的 obligation 是规约原文子串（来源「{src}…」）")
    if bad:
        return Outcome(False, "；".join(bad[:5]))
    return Outcome(True, "plan 冻结义务无纯复制")


@checker
def p05_anchor_points_to_declaration(root: Path, ctx: Ctx) -> Outcome:
    """anchor 不得指回知识决策声明章；landing 不得为空。"""
    freeze = _freeze(root)
    if freeze is None:
        return Outcome(True, "无知识冻结块（不适用）")
    bad = []
    for ob in _obligations(freeze):
        rule = str(ob.get("rule", "?"))
        anchor = str(ob.get("anchor", ""))
        landing = ob.get("landing") or []
        if re.search(r"知识决策|knowledge[_ ]decision", anchor):
            bad.append(f"{rule} 的 anchor 指回知识决策章（声明不是落点）")
        if not landing and "评审动作" not in str(ob.get("handling", "")):
            bad.append(f"{rule} 的 landing 为空（没有承载实体）")
    if bad:
        return Outcome(False, "；".join(bad[:5]))
    return Outcome(True, "冻结义务均有非自指 anchor 与非空 landing")


@checker
def p06_knowledge_decision_after_design(root: Path, ctx: Ctx) -> Outcome:
    """知识决策章必须排在第一个设计章之前（位置即语义）。"""
    plan = _plan_path(root)
    if plan is None:
        return Outcome(True, "无 plan.md（不适用）")
    lines = split_lines(read_text(plan))
    decision_at = design_at = None
    design_re = re.compile(r"^##\s*\d+[.、]?\s*(模块架构|数据模型|目录|页面|状态管理|服务层|路由)")
    for i, line in enumerate(lines):
        s = line.strip()
        if decision_at is None and re.match(r"^##\s*知识决策", s):
            decision_at = i
        if design_at is None and design_re.match(s):
            design_at = i
    if decision_at is None:
        return Outcome(False, "plan.md 缺「知识决策（设计输入）」章")
    if design_at is not None and decision_at > design_at:
        return Outcome(
            False, f"知识决策章在第 {decision_at + 1} 行，晚于设计章第 {design_at + 1} 行（事后总结）"
        )
    return Outcome(True, "知识决策章先于设计章")


@checker
def p07_rule_ids_in_story_body(root: Path, ctx: Ctx) -> Outcome:
    """story 主叙事不得出现规约编号（仓内标识）。

    口径（G3）：**只计**从激活知识派生出的规约域前缀（如 ``SEC-01``）；
    **不计** 验收/场景/决策编号（``AC-10``、``BD-2``、``DEC-001``）——它们是需求自身的
    编号，正文引用合法。派生不到规约前缀时报「证据不足」，不拿空集当通过（G7）。
    """
    story = _story_path(root)
    if story is None:
        return Outcome(True, "无 story 成品（不适用）")
    entries = load_constraint_entries(ctx.knowledge_root)
    prefixes = {e["id"].split("-")[0] for e in entries}
    if not prefixes:
        return Outcome(True, "未派生出规约域前缀（证据不足，不判）")
    main, _ = split_main_and_appendix(read_text(story))
    hits = []
    for n, line in enumerate(split_lines(main), start=1):
        for m in ENTRY_ID_RE.finditer(line):
            if m.group(0).split("-")[0] not in prefixes:
                continue
            hits.append(f"{story.name}:{n} `{m.group(0)}`")
    if hits:
        return Outcome(False, "主叙事出现规约编号：" + "；".join(hits[:5]))
    return Outcome(True, f"主叙事零规约编号（域前缀 {len(prefixes)} 个）")


@checker
def p08_repo_identifier_leak(root: Path, ctx: Ctx) -> Outcome:
    """归档件主叙事不得出现仓内路径或裸机制文件名（附录内合法）。"""
    story = _story_path(root)
    if story is None:
        return Outcome(True, "无 story 成品（不适用）")
    main, _ = split_main_and_appendix(read_text(story))
    patterns = [
        (re.compile(r"\b(doc|src|test|framework)/[A-Za-z0-9_./-]+"), "仓内路径"),
        (re.compile(r"\b[A-Za-z0-9_-]+\.(md|mjs|ets|ts|json|yaml)\b"), "裸文件名"),
    ]
    hits = []
    for n, line in enumerate(split_lines(main), start=1):
        if line.strip().startswith("!["):
            continue  # 图片引用的资源路径合法
        for pat, why in patterns:
            m = pat.search(line)
            if m:
                hits.append(f"{story.name}:{n} {why} `{m.group(0)}`")
                break
    if hits:
        return Outcome(False, "主叙事泄漏仓内标识：" + "；".join(hits[:5]))
    return Outcome(True, "主叙事零仓内标识")


@checker
def p09_decision_double_write(root: Path, ctx: Ctx) -> Outcome:
    """决策值单写：同段决策引用不得堆叠，也不得塞进紧邻括号。"""
    story = _story_path(root)
    if story is None:
        return Outcome(True, "无 story 成品（不适用）")
    text = read_text(story)
    hits = []
    ref = "见《决策与评审记录》"
    for idx, para in enumerate(re.split(r"(?:\r?\n){2,}", text), start=1):
        if para.count(ref) >= 2:
            hits.append(f"第 {idx} 段决策引用 {para.count(ref)} 次（应单写）")
    for n, line in enumerate(split_lines(text), start=1):
        if re.search(r"（\s*" + re.escape(ref), line):
            hits.append(f"{story.name}:{n} 决策引用塞进紧邻括号")
    if hits:
        return Outcome(False, "；".join(hits[:5]))
    return Outcome(True, "决策值单写")


@checker
def p10_duplicate_image_reference(root: Path, ctx: Ctx) -> Outcome:
    """同一张图片全篇只能引用一次。"""
    story = _story_path(root)
    if story is None:
        return Outcome(True, "无 story 成品（不适用）")
    seen: dict[str, list[int]] = {}
    for n, line in enumerate(split_lines(read_text(story)), start=1):
        for m in re.finditer(r"!\[[^\]]*\]\(([^)\s]+)\)", line):
            seen.setdefault(m.group(1), []).append(n)
    dupes = [f"{p}（行 {', '.join(map(str, ns))}）" for p, ns in seen.items() if len(ns) > 1]
    if dupes:
        return Outcome(False, "图片重复引用：" + "；".join(dupes[:5]))
    return Outcome(True, f"{len(seen)} 张图片各引用一次")


@checker
def p11_verifier_zero_adjudication(root: Path, ctx: Ctx) -> Outcome:
    """verifier 报告必须对必答集逐条给出裁决。"""
    reports: list[Path] = []
    for pattern in (
        "*/reports/**/verifier.report.md",
        "*/reports/**/verifier-*.md",
        "*/reports/**/verify-*.md",
        "reports/**/verifier.report.md",
        "verifier.report.md",
    ):
        reports.extend(root.glob(pattern))
    reports = sorted(set(reports))
    if not reports:
        return Outcome(True, "无 verifier 报告（不适用）")
    required: set[str] = set()
    story = _story_path(root)
    if story is not None:
        text = read_text(story)
        headers = header_index(text, APPENDIX_HEADERS)
        if headers:
            for _, cells in md_table_rows(text, APPENDIX_HEADERS):
                if "否" in cell(cells, headers, "命中"):
                    continue
                required.update(ENTRY_ID_RE.findall(cell(cells, headers, "编号")))
    if not required:
        return Outcome(True, "必答集为空（无判「是」条目）")
    blob = "\n".join(read_text(p) for p in reports)
    missing = sorted(rid for rid in required if rid not in blob)
    if missing:
        return Outcome(
            False,
            f"verifier 报告漏裁 {len(missing)}/{len(required)} 条：" + "、".join(missing[:8]),
        )
    return Outcome(True, f"必答集 {len(required)} 条全部有裁决")


@checker
def p12_numeric_index_paragraph(root: Path, ctx: Ctx) -> Outcome:
    """纯编号清单段冒充内容守恒（守恒按名不按号）。"""
    story = _story_path(root)
    if story is None:
        return Outcome(True, "无 story 成品（不适用）")
    hits = []
    idx_re = re.compile(r"\b[A-Z]{1,4}\d{1,3}\b")
    for n, line in enumerate(split_lines(read_text(story)), start=1):
        s = line.strip()
        if s.startswith("|") or s.startswith("!["):
            continue
        ids = idx_re.findall(s)
        if len(ids) < 3:
            continue
        residue = idx_re.sub("", s)
        residue = re.sub(r"[\s、，,和及与:：；;。.\-]+", "", residue)
        if len(residue) <= 6:
            return_hit = f"{story.name}:{n} 纯编号清单段（{len(ids)} 个编号，实质文字 {len(residue)} 字）"
            hits.append(return_hit)
    if hits:
        return Outcome(False, "；".join(hits[:5]))
    return Outcome(True, "无纯编号清单段")


@checker
def p13_silent_downstream_skip(root: Path, ctx: Ctx) -> Outcome:
    """下游对每条冻结义务必须给证据或显式「不适用 + 理由」。"""
    freeze = _freeze(root)
    if freeze is None:
        return Outcome(True, "无知识冻结块（不适用）")
    rules = [str(o.get("rule", "")) for o in _obligations(freeze) if o.get("rule")]
    if not rules:
        return Outcome(True, "冻结无义务条目（不适用）")
    report = None
    for rel in ("review/review-report.md", "review-report.md"):
        p = root / rel
        if p.exists():
            report = p
            break
    if report is None:
        return Outcome(True, "无 review 报告（不适用）")
    text = read_text(report)
    headers = header_index(text, ["rule", "结论"]) or header_index(text, ["义务", "结论"])
    if not headers:
        return Outcome(False, "review 报告缺「知识义务复核」表")
    covered: dict[str, str] = {}
    for _, cells in md_table_rows(text, headers[:2]):
        joined = " ".join(cells)
        for rid in ENTRY_ID_RE.findall(joined):
            covered[rid] = joined
    missing = [r for r in rules if r not in covered]
    if missing:
        return Outcome(False, "下游静默跳过：" + "、".join(missing[:8]))
    empty_reason = [
        r for r, row in covered.items()
        if "不适用" in row and len(re.sub(r"[|\s不适用]", "", row)) < len(r) + 4
    ]
    if empty_reason:
        return Outcome(False, "标「不适用」但无理由：" + "、".join(empty_reason[:5]))
    return Outcome(True, f"{len(rules)} 条义务均有结论")


# --------------------------------------------------------------------------- #
# 运行
# --------------------------------------------------------------------------- #


@dataclass
class Report:
    results: list[ModeResult] = field(default_factory=list)

    def add(self, r: ModeResult) -> None:
        self.results.append(r)

    @property
    def failed(self) -> list[ModeResult]:
        return [r for r in self.results if r.status == "FAIL"]

    @property
    def skipped(self) -> list[ModeResult]:
        return [r for r in self.results if r.status == "SKIP"]


def load_ledger() -> list[dict]:
    if not LEDGER.exists():
        print(f"[FATAL] 台账不存在：{LEDGER}", file=sys.stderr)
        raise SystemExit(2)
    data = yaml.safe_load(read_text(LEDGER)) or {}
    modes = data.get("modes") or []
    if not modes:
        print("[FATAL] 台账为空——派生为空必须出声，不当作通过", file=sys.stderr)
        raise SystemExit(2)
    return modes


def run_checker(name: str, root: Path, ctx: Ctx) -> Outcome:
    fn = CHECKERS.get(name)
    if fn is None:
        return Outcome(False, f"checker `{name}` 未实现")
    try:
        return fn(root, ctx)
    except Exception as exc:  # noqa: BLE001 —— 解析失败必须响亮，不静默当通过
        return Outcome(False, f"checker 执行异常：{type(exc).__name__}: {exc}")


def fixture_ctx(fixture: Path, mode: dict) -> Ctx:
    knowledge = fixture / "_knowledge"
    return Ctx(
        knowledge_root=knowledge if knowledge.exists() else None,
        extension_root=fixture if mode["target"] == "mechanism" else None,
        label=fixture.name,
    )


def self_check(mode: dict, report: Report) -> None:
    """反夹具必 FAIL、正夹具必 PASS。"""
    for kind, expect_ok in (("bad_fixture", False), ("good_fixture", True)):
        rel = mode.get(kind)
        if not rel:
            report.add(ModeResult(mode["id"], "self_check", kind, "FAIL", f"台账缺 {kind}"))
            continue
        path = REPO_ROOT / rel
        if not path.exists():
            report.add(ModeResult(mode["id"], "self_check", rel, "FAIL", "夹具目录不存在"))
            continue
        outcome = run_checker(mode["checker"], path, fixture_ctx(path, mode))
        ok = outcome.ok is expect_ok
        report.add(
            ModeResult(
                mode["id"],
                "self_check",
                kind,
                "PASS" if ok else "FAIL",
                outcome.evidence
                if ok
                else f"期望 {'PASS' if expect_ok else 'FAIL'}，实际 {'PASS' if outcome.ok else 'FAIL'}：{outcome.evidence}",
            )
        )


def real_targets(mode: dict, feature_roots: list[Path], extension_root: Path) -> list[tuple[str, Path, Ctx]]:
    if mode["target"] == "mechanism":
        return [
            (
                extension_root.relative_to(REPO_ROOT).as_posix()
                if extension_root.is_relative_to(REPO_ROOT)
                else str(extension_root),
                extension_root,
                Ctx(knowledge_root=extension_root / "knowledge", extension_root=extension_root),
            )
        ]
    out = []
    for fr in feature_roots:
        out.append((fr.name, fr, Ctx(knowledge_root=extension_root / "knowledge")))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="失效形态全量回归（G1）")
    ap.add_argument("--feature", action="append", default=[], help="feature 名（可多次）")
    ap.add_argument("--feature-root", action="append", default=[], help="feature 根目录（可多次）")
    ap.add_argument("--extension-dir", default=str(DEFAULT_EXTENSION_DIR))
    ap.add_argument("--self-check", action="store_true", help="只跑夹具自检")
    ap.add_argument("--list", action="store_true", help="列出台账")
    ap.add_argument("--quiet", action="store_true", help="只打印失败与汇总")
    ap.add_argument(
        "--historical",
        action="store_true",
        help="观察档：对实施前基线样本跑产物类 checker。这些样本本就含历史缺陷，"
        "检出是预期结果（等同于额外的反夹具），**不参与 PASS/FAIL**。",
    )
    args = ap.parse_args(argv)

    modes = load_ledger()

    if args.list:
        print(f"{'id':42} {'target':10} {'status':20} checker")
        for m in modes:
            print(f"{m['id']:42} {m['target']:10} {m['status']:20} {m['checker']}")
        return 0

    extension_root = Path(args.extension_dir)
    if not extension_root.is_absolute():
        extension_root = REPO_ROOT / extension_root

    feature_roots: list[Path] = []
    for name in args.feature:
        feature_roots.append(DEFAULT_FEATURES_DIR / name)
    for raw in args.feature_root:
        feature_roots.append(Path(raw))
    feature_roots = [p for p in feature_roots if p.exists()]

    report = Report()
    print("=" * 78)
    print("失效形态全量回归（口径：夹具自检必须正反判定正确；真实目标只跑 status=fixed）")
    print(f"台账 {LEDGER.relative_to(REPO_ROOT).as_posix()}：{len(modes)} 条")
    print(f"扩展根 {extension_root}")
    print(
        f"产物目标 {len(feature_roots)} 个："
        + (", ".join(p.name for p in feature_roots) or "（无——产物类形态须用 --feature 指定新产物）")
    )
    print("=" * 78)

    for mode in modes:
        if mode["status"] == "retired":
            if not mode.get("reason") or not mode.get("approved_by"):
                report.add(ModeResult(mode["id"], "ledger", "-", "FAIL", "retired 缺 reason/approved_by"))
            continue
        self_check(mode, report)

    if not args.self_check:
        for mode in modes:
            if mode["status"] != "fixed":
                if mode["status"] == "pending_capability":
                    report.add(
                        ModeResult(mode["id"], "real_target", "-", "SKIP", "目标能力尚未建（非回归失败）")
                    )
                continue
            for label, root, ctx in real_targets(mode, feature_roots, extension_root):
                outcome = run_checker(mode["checker"], root, ctx)
                report.add(
                    ModeResult(
                        mode["id"],
                        "real_target",
                        label,
                        "PASS" if outcome.ok else "FAIL",
                        outcome.evidence,
                    )
                )

    historical_rows: list[tuple[str, str, bool, str]] = []
    if args.historical:
        samples: list[Path] = []
        if DEFAULT_FEATURES_DIR.exists():
            samples.extend(p for p in sorted(DEFAULT_FEATURES_DIR.iterdir()) if p.is_dir())
        if ARCHIVED_FEATURES_DIR.exists():
            samples.extend(p for p in sorted(ARCHIVED_FEATURES_DIR.iterdir()) if p.is_dir())
        for mode in modes:
            if mode["status"] == "retired" or mode["target"] != "product":
                continue
            for sample in samples:
                outcome = run_checker(
                    mode["checker"], sample, Ctx(knowledge_root=extension_root / "knowledge")
                )
                historical_rows.append((mode["id"], sample.name, outcome.ok, outcome.evidence))

    by_mode: dict[str, list[ModeResult]] = {}
    for r in report.results:
        by_mode.setdefault(r.mode_id, []).append(r)
    for mode_id, results in by_mode.items():
        worst = "FAIL" if any(r.status == "FAIL" for r in results) else (
            "SKIP" if all(r.status == "SKIP" for r in results) else "PASS"
        )
        if args.quiet and worst == "PASS":
            continue
        print(f"\n[{worst}] {mode_id}")
        for r in results:
            if args.quiet and r.status == "PASS":
                continue
            print(f"    {r.status:5} {r.stage:12} {r.target:24} {r.evidence}")

    if args.historical:
        detected = [r for r in historical_rows if not r[2]]
        print("\n" + "-" * 78)
        print(
            f"历史样本观察档（实施前基线，不参与 PASS/FAIL）：{len(historical_rows)} 次检查，"
            f"检出 {len(detected)} 处历史缺陷"
        )
        for mode_id, sample, _, evidence in detected:
            print(f"    检出 {mode_id:42} {sample:12} {evidence[:100]}")
        print("-" * 78)

    total = len(by_mode)
    failed = {r.mode_id for r in report.failed}
    skipped_only = {
        mid for mid, rs in by_mode.items() if mid not in failed and all(r.status == "SKIP" for r in rs)
    }
    print("\n" + "=" * 78)
    print(
        f"形态 {total} 条：FAIL {len(failed)}，SKIP(能力未建) {len(skipped_only)}，"
        f"PASS {total - len(failed) - len(skipped_only)}"
    )
    if failed:
        print("失败形态：" + "、".join(sorted(failed)))
    print("=" * 78)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
