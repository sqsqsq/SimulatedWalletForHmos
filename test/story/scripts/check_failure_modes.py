#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""失效形态全量回归（G1）。

台账：``test/story/regression/failure-modes.yaml``。

回归分两段，缺一不可：

1. **夹具自检** —— 所有 ``status != retired`` 的形态都跑：反夹具必须被判 FAIL、
   正夹具必须被判 PASS。自检不过说明 checker 本身失效，比漏检更危险，整体判 FAIL。
2. **真实目标** —— 仅 ``status == fixed`` 的形态跑；``pending_capability``（目标能力
   尚未建）报 SKIP 并计数，不算失败。能力交付后把 status 改 fixed 即自动生效。
3. **责任已委派** —— ``responsibility`` 写成 ``verifier`` 或 ``behavior_test`` 的形态
   两步都不跑：它的发现者不是脚本了。回归里单列一档报出来，「这一条现在靠谁守」
   因此在每次输出里都看得见，而不是从台账里消失。

用法::

    python test/story/scripts/check_failure_modes.py                # 默认目标集
    python test/story/scripts/check_failure_modes.py --feature AR90004 --feature ISSUE-206
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
import shutil
import subprocess
import tempfile
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
        # 点开头的目录是工作件（adapt 的 `.adapt-<版本>/` 就是一例），不随包交付，
        # 与预算门同一口径；扫进去会把扫描自己写的清单当成机制层报出来
        if any(part.startswith(".") for part in p.relative_to(root).parts[:-1]):
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


#: 附录那一行标题：`## 附录`、`## 10. 附录`、`### 附录：规约符合性` 都算。
#: 章编号由 `number` 机器铺，成文的归档件带的正是带编号那种——不认它的话，
#: 整份 story 会被当成主叙事，附录里的规约表与材料清单于是被判成泄漏。
APPENDIX_HEADING = re.compile(r"^#{1,3}\s*(?:[0-9]+[.、)]\s*)?附录")


def split_main_and_appendix(text: str) -> tuple[str, str]:
    """按第一个附录标题切主叙事与附录（M10/P07/P08 的作用域口径）。"""
    lines = split_lines(text)
    for i, line in enumerate(lines):
        if APPENDIX_HEADING.match(line.strip()):
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


def load_constraint_domains(knowledge_root: Path | None) -> list[dict]:
    """从知识目录派生规约域及其命中条件（frontmatter 的 applies_when）。

    写 ``always`` 的是常驻域，域内条目逐条判；其余是条件域，先判域再判条目。
    域前缀从条目编号派生，不吃 frontmatter 里可能缺失的 domain 字段。
    """
    out: list[dict] = []
    if knowledge_root is None or not knowledge_root.exists():
        return out
    for path in sorted(knowledge_root.rglob("*.md")):
        text = read_text(path)
        if not header_index(text, ["编号", "约束"]):
            continue
        fm = re.match(r"^---\r?\n(.*?)\r?\n---", text, flags=re.DOTALL)
        applies = ""
        if fm:
            m = re.search(r"^applies_when\s*:\s*(.*)$", fm.group(1), flags=re.MULTILINE)
            applies = m.group(1).strip() if m else ""
        prefixes = {
            cell(cells, header_index(text, ["编号", "约束"]) or [], "编号").strip().split("-")[0]
            for _, cells in md_table_rows(text, ["编号", "约束"])
        }
        for prefix in sorted(p for p in prefixes if p):
            out.append({"prefix": prefix, "applies_when": applies, "always": applies == "always",
                        "file": path.name})
    return out


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
#: 不属于机制层、机制层判据不适用的目录。
#: - ``knowledge``：知识层，它的域前缀、条目编号、路径本来就是内容。
#: - ``adapt``：``story adapt`` 在目标工程就地生成的工作目录（两棵树清单、备份、方案、
#:   安装记录）。它按定义会照录目标工程的知识标识、层名与绝对路径，扫它等于把运行产物
#:   当交付件判；SKILL 明写「包不交付它」，机制类文件也不会落在这里。
NON_MECHANISM_DIRS = ("knowledge", "_knowledge", "adapt")


#: 占位前缀：刻意表示「任意域」的示例编号，不是硬编码（`XXX-01` 这类）。
PLACEHOLDER_PREFIX_RE = re.compile(r"^(X{2,}|N{2,}|A{2,}|YYY|ZZZ)$")


def activation_names(root: Path) -> dict:
    """从 manifest 的激活清单派生「真实存在的知识标识」集合。

    这是判「硬编码」与「悬空引用」的基准：**能在清单里查到的就是真实标识**，
    机制层写它就是把知识内容抄了一份；**查不到却长得像的**是死判据，更糟。

    自己也从清单派生——写死一份清单来查「有没有写死清单」，那就滑稽了。

    清单只有一份（``provides.knowledge``）；文件属于哪类由它自己 frontmatter 的
    ``kind`` 决定。本函数只需要「有哪些文件、哪些条目」，不关心分类。
    """
    manifest = root / "manifest.yaml"
    if not manifest.exists():
        return {"entries": set(), "prefixes": set(), "slugs": set(), "derived": False}
    try:
        data = yaml.safe_load(read_text(manifest)) or {}
    except yaml.YAMLError:
        return {"entries": set(), "prefixes": set(), "slugs": set(), "derived": False}
    listed = (data.get("provides") or {}).get("knowledge") or []
    slugs, entries, prefixes = set(), set(), set()
    for rel in listed:
        rel = str(rel).replace("\\", "/")
        slug = rel.rsplit("/", 1)[-1].removesuffix(".md")
        # 通用文件名（README/index）不具标识性：写它不等于耦合了知识内容，
        # 而把它当标识会把所有提到 README 的地方一起误报。
        # 这类文件的显式路径引用由 M17 的第二条判据覆盖。
        if slug.lower() not in ("readme", "index"):
            slugs.add(slug)
        f = root / rel
        if not f.exists():
            continue
        text = read_text(f)
        headers = header_index(text, ["编号", "约束"])
        if not headers:
            continue
        for _, cells in md_table_rows(text, ["编号", "约束"]):
            eid = cell(cells, headers, "编号").strip()
            if ENTRY_ID_RE.fullmatch(eid):
                entries.add(eid)
                prefixes.add(eid.split("-")[0])
    return {"entries": entries, "prefixes": prefixes, "slugs": slugs, "derived": bool(slugs)}


@checker
def m01_hardcoded_domain_prefix(root: Path, ctx: Ctx) -> Outcome:
    """机制层不得出现真实知识标识的字面（域/条目/文件名应运行期派生）。

    口径（G3）：

    - **扫描面**：机制层（扩展根下除 ``knowledge/`` 外）的**代码与 Markdown 全部**。
      早先只扫代码、放过 ``.md``（理由是「写作指令允许出现形态示例」），结果 16 处硬编码里
      有 10 处藏在 ``.md`` 中全部逃检——注入件恰恰是模型直接读到的东西，它写死了域名，
      新增一个域时模型就照着旧清单干活。
    - **计**：能在激活清单里查到的**真实条目编号**与**知识文件 slug**；
    - **不计**：① 占位形态（``XXX-01``——刻意表示任意域，正是不硬编码的写法）；
      ② 注释/说明中作为**反例**出现的（同行含「不写」「禁止」「反例」「改为」等否定词）；
      ③ 清单派生不出来时不判（报证据不足，不拿空集当通过）。
    """
    names = activation_names(root)
    if not names["derived"]:
        return Outcome(True, "激活清单派生不出知识标识（证据不足，不判）")

    negation = re.compile(r"不写|不得|禁止|反例|改为|改用|换成|已退役|不是|别写")
    hits = []
    for path in iter_files(root, ALL_SUFFIXES, NON_MECHANISM_DIRS):
        rel = path.relative_to(root).as_posix()
        if rel == "manifest.yaml":
            continue   # 激活清单**就是**登记文件名的地方，它不是「抄了一份」
        for n, line in enumerate(split_lines(read_text(path)), start=1):
            if negation.search(line):
                continue
            for m in ENTRY_ID_RE.finditer(line):
                if PLACEHOLDER_PREFIX_RE.match(m.group(0).split("-")[0]):
                    continue
                if m.group(0) in names["entries"]:
                    hits.append(f"{rel}:{n} 条目编号 `{m.group(0)}`")
            for slug in names["slugs"]:
                if re.search(rf"\b{re.escape(slug)}\b", line):
                    hits.append(f"{rel}:{n} 知识文件名 `{slug}`")
                    break
    if hits:
        return Outcome(False, "机制层写死了知识标识：" + "；".join(hits[:6]))
    return Outcome(
        True,
        f"机制层零知识标识字面（基准：{len(names['entries'])} 条目 / {len(names['slugs'])} 文件）",
    )


@checker
def m17_dangling_knowledge_reference(root: Path, ctx: Ctx) -> Outcome:
    """机制层引用的知识标识必须在激活清单里真实存在。

    比硬编码更糟的一类：写着 ``TEL-05``、``app-lifecycle-config`` 这种**查无此物**的编号与
    文件名，模型照着它去找判定基准，找不到就只能自己编。实测这类死判据在注入件里存活了
    很久——因为没有任何检查会去核对「这个编号真的有吗」。

    口径（G3）：只判**两类明确的引用**，不做形态猜测（猜测会把脚本名、目录名一并误报）——
    ① 编号：前缀在册（说明它确实指某个已激活的域）而编号查不到；
    ② 显式写出的 ``knowledge/xxx.md`` 路径，其文件不在激活清单。
    占位形态不计。
    """
    names = activation_names(root)
    if not names["derived"]:
        return Outcome(True, "激活清单派生不出知识标识（证据不足，不判）")

    hits = []
    for path in iter_files(root, ALL_SUFFIXES, NON_MECHANISM_DIRS):
        rel = path.relative_to(root).as_posix()
        for n, line in enumerate(split_lines(read_text(path)), start=1):
            # a) 编号：前缀在册说明它确实指某个已激活的域，编号却查不到 = 死判据
            for m in ENTRY_ID_RE.finditer(line):
                eid = m.group(0)
                if PLACEHOLDER_PREFIX_RE.match(eid.split("-")[0]):
                    continue
                if eid.split("-")[0] in names["prefixes"] and eid not in names["entries"]:
                    hits.append(f"{rel}:{n} 编号 `{eid}` 在激活清单里不存在（死判据）")
            # b) 显式的知识文件路径引用：写出来了就必须真的在册
            for pm in re.finditer(r"knowledge/[\w./-]+\.md", line):
                slug = pm.group(0).rsplit("/", 1)[-1].removesuffix(".md")
                if slug not in names["slugs"] and slug != "README":
                    hits.append(f"{rel}:{n} 知识路径 `{pm.group(0)}` 不在激活清单")
    if hits:
        return Outcome(False, "引用了不存在的知识标识：" + "；".join(hits[:6]))
    return Outcome(True, "机制层引用的知识标识全部在册")


@checker
def m18_knowledge_boundary_leak(root: Path, ctx: Ctx) -> Outcome:
    """知识文件越出自己的边界。

    四种形态，全部由激活清单与目录结构派生（AGENTS.md §2「知识不含维护信息，定位只写一处」）：
    ① 项目知识引用在册规约编号（时机与要求归规约）；② 任一知识文件指向机制
    （manifest / hooks 等目录——维护坐标不进知识）；③ 规约携带源码路径；④ 阶段消费矩阵。

    判定不在这里重实现：经 ``run_self_check.mjs`` 调真实 ``selfCheck``，退出码与问题清单即结论。
    夹具是自带 ``framework.config.json``（``extension_dir: "."``）的迷你扩展根，把它当工程根传入；
    真实目标把仓根当工程根（扩展根由仓根配置解析）。
    """
    runner = REPO_ROOT / "test" / "story" / "scripts" / "run_self_check.mjs"
    if not runner.exists():
        return Outcome(False, "缺自检脚本 run_self_check.mjs")
    project_root = root if (root / "framework.config.json").exists() else REPO_ROOT
    proc = subprocess.run(
        ["node", str(runner), str(project_root)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO_ROOT),
    )
    if proc.returncode == 2:
        return Outcome(False, f"知识派生失败（不当作通过）：{proc.stderr.strip() or proc.stdout.strip()}")
    problems = [l.strip() for l in split_lines(proc.stdout) if l.strip()]
    if proc.returncode != 0 or problems:
        return Outcome(False, "知识边界泄漏：" + "；".join(problems[:6]))
    return Outcome(True, "全部激活知识文件边界自检 0 问题")


@checker
def m02_test_case_features(root: Path, ctx: Ctx) -> Outcome:
    """机制层不得出现测试数据（反过拟合）。

    执行者会直接打开脚本读。注释里的测试数据就成了它照着写的样板，
    测出来的是「照抄那一次」而不是「在未知需求上做对」。

    四种形态，词表都从配置与 Case 目录取，不写死：
      · 需求单号（`AR-1234` 这类形态）；
      · 业务特征词（补充文档名、资产目录名——它们会变成路径）；
      · Case 名与 suite 前缀（配置里登记的那些）；
      · 某次运行的计数（「实测 3 处」这类）；
      · 轮次叙述（「两跑的作者都…」「一次真实实跑说明了…」——不带数字也算）；
      · 历史与替代叙述（「此前…」「早先…」「三态勾选块退场」——讲这段以前怎么样）；
      · 以错误为参照的指路（「不必去读 Y」——正确的位置本身就是答案）。

    「不在 X 下」这一形状不入词表：它同时覆盖规则本身的禁止（`不在归档目录下造副本`），
    机械分不开，归评审按 `AGENTS.md` §5.3 逐句读。

    后两样与前四样同一类：**非当前信息进了交付面**。它们的家在 `test/story/`
    的方案、评审与提交说明里，那里正需要说清「为什么改」。

    豁免按语境登记，逐条具名（见 `M02_EXEMPT`）：产品动作本身用这些词、
    合同数据里的业务项、禁用词的替换说法。
    """
    case_ids = re.compile(r"\b(AR|DTS|ISSUE)-?\d{4,}\b")
    run_counts = re.compile(r"(实测|首跑|上一版|曾经|改动前)[^。；\n]{0,12}?\d")
    # 轮次叙述：不带数字也算。「两跑的作者都…」「一次真实实跑说明了…」都是维护痕迹，
    # 交付面用现在时讲道理就够。`上一轮` 不在列——那是流程概念（round 开出的上一轮）。
    run_narrative = re.compile(r"实跑|首跑|[一二三四五六七八九十两]跑|[两三四]轮(?!次)")
    # 历史与替代叙述：讲这段以前怎么样、什么退场了。只收有区分力的字面——
    # 「旧的」「不在 X 下」这类同时覆盖规则本身的禁止（`不读旧 story`、
    # `不在归档目录下造副本`），机械分不开，那一类归评审按 §5.3 逐句读。
    history = re.compile(r"此前|早先|原先|曾经|迁移期|不再是|退场")
    # 「不必去读源码」这类：正确的位置本身就是答案，不用拿错误当参照。
    negative_pointer = re.compile(r"不必去|不要去|别去")
    business_words = _case_business_words()
    case_names = _case_and_suite_names()
    hits = []
    for path in iter_files(root, ALL_SUFFIXES, NON_MECHANISM_DIRS):
        rel = path.relative_to(root).as_posix()
        for n, line in enumerate(split_lines(read_text(path)), start=1):
            m = case_ids.search(line)
            if m:
                hits.append(f"{rel}:{n} `{m.group(0)}`")
                continue
            m = run_counts.search(line)
            if m:
                hits.append(f"{rel}:{n} 运行计数「{m.group(0)}」")
                continue
            m = run_narrative.search(line)
            if m:
                hits.append(f"{rel}:{n} 轮次叙述「{m.group(0)}」——交付面用现在时讲道理，"
                            "不讲哪一跑发生过什么")
                continue
            if not _m02_exempt(rel, line):
                m = history.search(line)
                if m:
                    hits.append(f"{rel}:{n} 历史叙述「{m.group(0)}」——"
                                "只写现在是什么、为什么这样；为什么改写在方案与评审里")
                    continue
                m = negative_pointer.search(line)
                if m:
                    hits.append(f"{rel}:{n} 以错误为参照「{m.group(0)}」——"
                                "直接给出正确的位置或做法，它本身就是答案")
                    continue
            hit_word = next((w for w in business_words if w in line), None) \
                or next((w for w in case_names if w in line), None)
            if hit_word:
                hits.append(f"{rel}:{n} 测试数据「{hit_word}」")
    if hits:
        return Outcome(False, "机制层出现测试数据：" + "；".join(hits[:5]))
    return Outcome(True,
                   f"机制层零测试数据（业务词 {len(business_words)}、Case 与 suite 名 {len(case_names)}）")


#: M02 的豁免，逐条具名。词表是兜底，判断归评审——所以豁免也具名，不写成通配。
M02_EXEMPT = (
    # 产品动作本身就叫这个：`/story restore` 恢复到上一版、archive 覆盖后的状态转移。
    ("skills/story/SKILL.md", "上一版"),
    ("hooks/spec/post_check.mjs", "不再是"),
    ("skills/story/scripts/story-build.mjs", "上一版"),
    # 版本头注就是给升级方看的行为变化清单，那是它的用途。
    ("manifest.yaml", "退场"),
    # 合同数据里的业务项与禁用词的替换说法。
    ("contracts/story-chapters.json", "旧版本"),
    ("skills/story/scripts/lint-rules.mjs", "旧版本"),
    # adapt 面对的是目标工程里可能真的存在的旧目录。
    ("skills/story-adaptation/SKILL.md", "退场"),
    ("skills/story-adaptation/SKILL.md", "旧的"),
    ("skills/story-adaptation/SKILL.md", "早先"),
)


def _m02_exempt(rel: str, line: str) -> bool:
    """这一行按语境豁免吗——文件与词一起登记，避免整份文件开天窗。"""
    return any(f in rel and w in line for f, w in M02_EXEMPT)


def _case_and_suite_names() -> list[str]:
    """Case 目录名、`case.yaml` 里的 id 与 suite 前缀——**从配置取，不写死**。

    机制层出现它们，就是它照着某一轮的测试装置写的。
    """
    names: set[str] = set()
    cases_dir = REPO_ROOT / "test" / "story" / "cases"
    if cases_dir.is_dir():
        for case_yaml in cases_dir.glob("*/case.yaml"):
            names.add(case_yaml.parent.name)
            try:
                data = yaml.safe_load(read_text(case_yaml)) or {}
            except yaml.YAMLError:
                continue
            if isinstance(data, dict) and data.get("id"):
                names.add(str(data["id"]))
    config = REPO_ROOT / "test" / "story" / "config" / "test.yaml"
    if config.is_file():
        try:
            data = yaml.safe_load(read_text(config)) or {}
        except yaml.YAMLError:
            data = {}
        for item in ((data.get("cli") or {}).get("configurations") or []):
            for key in ("id", "model"):
                if isinstance(item, dict) and item.get(key):
                    names.add(str(item[key]))
    names.add("story-suite-")
    return sorted(n for n in names if len(n) >= 6)


def _case_business_words() -> list[str]:
    """从测试 Case 派生业务特征词；派生不到就只用单号形态（不硬编码业务名）。

    取的是**会变成路径的那些名字**：人给的补充文档（文件名会成为
    `assets/<stem>/` 目录名与导入后的小节名）与工作区里已有的资产目录。
    机制层出现这类词，就是它照着某一轮的测试数据写死了。
    """
    cases_dir = REPO_ROOT / "test" / "story" / "cases"
    words: set[str] = set()
    if not cases_dir.exists():
        return []
    for case_yaml in cases_dir.glob("*/case.yaml"):
        try:
            yaml.safe_load(read_text(case_yaml))
        except yaml.YAMLError:
            continue
        case_root = case_yaml.parent
        for material in (*(case_root / "supplements").glob("*"),
                         *(case_root / "workspace" / "inbox").glob("*")):
            stem = material.stem
            if len(stem) >= 4 and not stem.startswith("."):
                words.add(stem)
        for asset_dir in (case_root / "workspace").rglob("assets/*"):
            if asset_dir.is_dir() and len(asset_dir.name) >= 4:
                words.add(asset_dir.name)
    return sorted(w for w in words if re.search(r"[\u4e00-\u9fff]", w))


@checker
def m03_hardcoded_layer_names(root: Path, ctx: Ctx) -> Outcome:
    """机制层不得写死架构外层目录名（层清单从架构 DSL 派生）。"""
    layer_re = re.compile(r"\b0[1-9]-[A-Z][A-Za-z]{3,}\b")
    hits = []
    for path in iter_files(root, ALL_SUFFIXES, NON_MECHANISM_DIRS):
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
    for path in iter_files(root, ALL_SUFFIXES, NON_MECHANISM_DIRS):
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
    for path in iter_files(root, (".mjs", ".js"), NON_MECHANISM_DIRS):
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
    for path in iter_files(root, TEXT_SUFFIXES, NON_MECHANISM_DIRS):
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
    for path in iter_files(root, TEXT_SUFFIXES, NON_MECHANISM_DIRS):
        for n, line in enumerate(split_lines(read_text(path)), start=1):
            m = quota_re.search(line)
            if m:
                hits.append(f"{path.relative_to(root).as_posix()}:{n} `{m.group(0)}`")
    if hits:
        return Outcome(False, "写作指令含形式配额：" + "；".join(hits[:5]))
    return Outcome(True, "写作指令零形式配额")


@checker
def m14_criteria_instruction_divergence(root: Path, ctx: Ctx) -> Outcome:
    """内容自检问句必须随写作指令下发给被测模型。

    口径（G3）：**只计写判定结论的阶段**（spec / plan）的注入件——它们要求模型自己写出
    「这条规约在本需求里落成什么」，而机械门禁只拦得住原文照抄，拦不住换个说法，
    所以自检问句必须和判据同批下发。**不计**下游阶段的注入件：它们消费的是已冻结的结论，
    不产生新的判定文字。

    按**路径**判归属，不按文件名——各阶段的注入件同名（`on_context_load.md`），
    按文件名比对会把下游的也算成写作注入件。
    """
    injections = [
        p for p in iter_files(root, TEXT_SUFFIXES, NON_MECHANISM_DIRS)
        if "on_context_load" in p.name
    ]
    if not injections:
        return Outcome(True, "无写作注入件（不适用）")
    writer_phases = [
        p for p in injections
        if re.search(r"(^|/)(spec|plan)(/|$)", p.relative_to(root).as_posix())
    ]
    if not writer_phases:
        return Outcome(True, "无写判定结论阶段的注入件（不适用）")
    self_check = re.compile(r"自问|自检问句|这句话里有没有|遮住")
    missing = [
        p.relative_to(root).as_posix() for p in writer_phases
        if not self_check.search(read_text(p))
    ]
    if missing:
        return Outcome(False, "写作注入件缺内容自检问句：" + "、".join(missing))
    return Outcome(True, f"{len(writer_phases)} 份写作注入件均含内容自检问句")


@checker
def m15_paraphrase_branch_drift(root: Path, ctx: Ctx) -> Outcome:
    """复述判定的每个对抗分支都要维持冻结时的判定档位。

    口径（G3）：**逐分支比对，不合并计数**——把九个分支合成一个通过率时，
    某一类样本整体失效也能被其它分支的通过数掩盖（已实测过这种凑数通过）。

    判定逻辑不在这里重实现：调用真实模块跑
    ``test/story/scripts/check_paraphrase_branches.mjs``，退出码即结论。
    重实现一份出来的是「测试对测试」，判据一改两边就分叉。
    """
    module = root / "hooks" / "shared" / "paraphrase.mjs"
    if not module.exists():
        return Outcome(True, "无复述判定模块（不适用）")
    runner = REPO_ROOT / "test" / "story" / "scripts" / "check_paraphrase_branches.mjs"
    if not runner.exists():
        return Outcome(False, "缺分支验证脚本 check_paraphrase_branches.mjs")
    # 夹具目录下的模块只作存在性演示；分支预期始终对交付件跑（判据的真源只有一处）
    proc = subprocess.run(
        ["node", str(runner)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO_ROOT),
    )
    tail = [l for l in split_lines(proc.stdout) if l.strip()][-1:] or ["(无输出)"]
    if proc.returncode != 0:
        bad = [l.strip() for l in split_lines(proc.stdout) if l.strip().startswith("[FAIL]")]
        return Outcome(False, f"分支偏离：{'；'.join(bad) or tail[0]}")

    # 双实现一致性：门禁侧是 JS（paraphrase.mjs），产物回归侧是本文件的 Python 实现。
    # 两份实现是被迫的（跨语言），但**判据必须只有一个**——所以在这里把它们机械绑起来：
    # 同一批样本上判定不一致，立刻报出来，而不是等某天门禁放过、回归报错时才发现。
    fixture = REPO_ROOT / "test" / "story" / "fixtures" / "knowledge" / "adversarial.json"
    if fixture.exists():
        data = json.loads(read_text(fixture))
        src = data["source"]
        drift = []
        for c in data["cases"]:
            py_copied, _ = is_pure_copy(c["text"], [src])
            js_expects_copy = c.get("expect_verdict") == "PURE_COPY"
            js_forbids_copy = c.get("expect_not_verdict") == "PURE_COPY"
            if js_expects_copy and not py_copied:
                drift.append(f"{c['id']}：JS 判纯复制，Python 未判")
            if js_forbids_copy and py_copied:
                drift.append(f"{c['id']}：JS 不判纯复制，Python 判了")
        if drift:
            return Outcome(False, "Python 与 JS 的复述判定漂移：" + "；".join(drift))
    return Outcome(True, f"{tail[0]}；双实现判定一致")


@checker
def _exported_names(text: str):
    """一个模块导出了哪些名字：`export function/const/class X` 与尾部 `export { A, B }`。"""
    for n, line in enumerate(split_lines(text), start=1):
        m = re.match(r"\s*export\s+(?:async\s+)?(?:function|const|class)\s+([A-Za-z_$][\w$]*)", line)
        if m:
            yield m.group(1), n
            continue
        m = re.match(r"\s*export\s*\{([^}]*)\}", line)
        if m:
            for part in m.group(1).split(","):
                name = part.split(" as ")[0].strip()
                if name:
                    yield name, n


def _test_domain_code() -> list[Path]:
    """测试域的代码文件——给测试用的导出是真消费者，不是死代码。"""
    base = REPO_ROOT / "test" / "story"
    if not base.exists():
        return []
    out = []
    for p in base.rglob("*"):
        if p.suffix in (".mjs", ".js", ".py") and not any(
                part in {"__pycache__", "design", "output", "fixtures"} for part in p.parts):
            out.append(p)
    return out


@checker
def m16_patch_residue(root: Path, ctx: Ctx) -> Outcome:
    """补丁式修补的残留：死代码、静默降级、跨轮次的临时标记。

    口径（G3）：三类各自可独立判定，**逐类报出**——

    1. **死代码**：``export function X`` 在整个扩展根内零调用方（定义处不计）。
       零调用的导出不只是多余，它守着的数据会成为「从不生效的第二真源」——
       实测出现过一份硬编码的模式清单，被一个从没人调的自检函数守着。
    2. **静默降级**：``catch`` 块里直接 ``return`` 空值且**同块内无任何出声**
       （无 ``console``、无 ``throw``、无 ``problems.push``）。降级本身合法，静默不合法：
       它把「没接上」伪装成「正常路径」。
    3. **跨轮次临时标记**：``TODO`` / ``FIXME`` / ``暂时`` / ``临时`` / ``待迁移``。
       留过一轮的临时方案就是永久方案，只是没人认领。

    **不计**：注释里描述这些反模式本身的行（同行含「不得」「禁止」等否定词）——
    维护契约与本 checker 的说明文字正属此类。
    """
    negation = re.compile(r"不得|禁止|不许|反例|应出声|必须出声|要出声")
    code_files = iter_files(root, (".mjs", ".js"), ())
    blobs = {p: read_text(p) for p in code_files}
    all_code = "\n".join(blobs.values())

    dead, silent, temp = [], [], []

    # 1. 死代码：**零消费者的导出**
    #
    # 判的是「别的文件用不用它」，不是「本文件里调没调」。三处收紧过：
    #   · `export const` 与尾部 `export { A, B }` 也算导出——漏掉它们放过了 24 个；
    #   · 出现在某个 `export { … }` 列表里**不算**被用到——那正是零消费者的藏身处；
    #   · 消费面含测试域：给测试用的导出是真消费者，不该被当成死代码删掉。
    consumer_texts = [(p, t) for p, t in blobs.items()]
    consumer_texts += [(p, read_text(p)) for p in _test_domain_code()]
    for path, text in blobs.items():
        rel = path.relative_to(root).as_posix()
        for name, line_no in _exported_names(text):
            pattern = re.compile(rf"\b{re.escape(name)}\b")
            if any(p != path and pattern.search(t) for p, t in consumer_texts):
                continue
            dead.append(f"{rel}:{line_no} `{name}` 零消费者导出")

    # 2. 静默降级：catch 块内直接 return 且无出声
    for path, text in blobs.items():
        rel = path.relative_to(root).as_posix()
        rows = split_lines(text)
        for i, line in enumerate(rows):
            if not re.search(r"\bcatch\s*(\([^)]*\))?\s*{", line):
                continue
            block = "\n".join(rows[i: i + 6])
            if re.search(r"console\.|throw |problems\.push|fail\(|log\(", block):
                continue
            # 只判返回**空集合**：`return null` 是显式的「没有」信号，调用方被迫判空；
            # `return []` 才是静默——`for...of` 一声不响地跳过，看起来一切正常
            if re.search(r"return\s*(\[\]|{})", block):
                if negation.search(line) or negation.search(rows[max(0, i - 1)]):
                    continue
                silent.append(f"{rel}:{i + 1} catch 内静默返回空值")

    # 3. 跨轮次临时标记。
    # 「临时/暂时」在业务描述里是常用词（「临时改名再还原」「允许临时硬编码」都是被设计的行为），
    # 所以只判它作为**遗留标记**的形态：待办标记，或明说是临时方案/待迁移。
    # 知识层不扫——那里的「临时」是业务规则的一部分，不是代码里欠的债。
    marker = re.compile(r"\bTODO\b|\bFIXME\b|\bXXX:|临时方案|临时措施|临时实现|暂时保留|待迁移|待重构")
    for path in iter_files(root, ALL_SUFFIXES, NON_MECHANISM_DIRS):
        rel = path.relative_to(root).as_posix()
        for n, line in enumerate(split_lines(read_text(path)), start=1):
            if negation.search(line):
                continue
            m = marker.search(line)
            if m:
                temp.append(f"{rel}:{n} `{m.group(0)}`")

    parts = []
    if dead:
        parts.append(f"死代码 {len(dead)} 处：" + "；".join(dead[:4]))
    if silent:
        parts.append(f"静默降级 {len(silent)} 处：" + "；".join(silent[:4]))
    if temp:
        parts.append(f"临时标记 {len(temp)} 处：" + "；".join(temp[:4]))
    if parts:
        return Outcome(False, " | ".join(parts))
    return Outcome(True, f"零死代码 / 零静默降级 / 零临时标记（扫 {len(code_files)} 个代码文件）")


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

def _contracts_path(root: Path) -> Path | None:
    """契约只有一份，在 feature 根下——与 framework 同路径。

    原来这里按「先子目录、后根」两处试。回退看着稳，实际是把「两份真源」
    合法化了：哪一份被读到取决于哪一份先存在，两份不一致时谁也不报错。
    """
    p = root / "contracts.yaml"
    return p if p.exists() else None


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


@checker
def p14_image_broken_link(root: Path, ctx: Ctx) -> Outcome:
    """归档件里的图片引用必须解析得到文件。

    形态守恒只数图的条数——数得到「有一张图」，看不出它打不开。评审者拿到的是红叉。
    """
    story = root / "AR" / "story.md"
    if not story.exists():
        return Outcome(True, "无归档件叙事主件（不适用）")
    text = read_text(story)
    broken: list[str] = []
    total = 0
    for idx, line in enumerate(text.splitlines(), start=1):
        for m in re.finditer(r"!\[[^\]]*\]\(([^)\s]+)\)", line):
            ref = m.group(1)
            if re.match(r"^(https?:|data:)", ref, flags=re.IGNORECASE):
                continue
            total += 1
            if not (story.parent / ref).exists():
                broken.append(f"第 {idx} 行「{ref}」")
    if broken:
        return Outcome(False, "图片引用解析不到文件：" + "；".join(broken[:5]))
    return Outcome(True, f"{total} 处图片引用均可解析")


@checker
def p15_domain_gating_not_applied(root: Path, ctx: Ctx) -> Outcome:
    """有命中条件的规约域，须先做域级判定，不是对着域内条目逐条写「不涉及」。"""
    registry = _registry(root)
    if registry is None:
        return Outcome(True, "无判定登记件（不适用）")
    domains = load_constraint_domains(ctx.knowledge_root)
    if not domains:
        return Outcome(True, "知识目录派生不出规约域（证据不足）")
    conditional = {d["prefix"]: d for d in domains if not d["always"]}
    if not conditional:
        return Outcome(True, "激活的规约域都是常驻域（不适用）")
    declared = {
        str(d.get("prefix", "")).strip()
        for d in registry.get("domains", []) or []
        if isinstance(d, dict)
    }
    listed = {
        eid.split("-")[0]
        for c in registry.get("constraints", []) or []
        if isinstance(c, dict) and (eid := str(c.get("id", "")).strip())
    }
    missing = [p for p in conditional if p not in declared and p in listed]
    if missing:
        return Outcome(False, "条件域未做域级判定却逐条登记：" + "、".join(sorted(missing)))
    no_basis = [
        str(d.get("prefix", ""))
        for d in registry.get("domains", []) or []
        if isinstance(d, dict) and not str(d.get("basis", "")).strip()
    ]
    if no_basis:
        return Outcome(False, "域级判定缺依据：" + "、".join(sorted(no_basis)))
    return Outcome(True, f"{len(conditional)} 个条件域都先判了域")


@checker
def p16_spec_exit_diverges(root: Path, ctx: Ctx) -> Outcome:
    """规格件的出口章与判定登记件同文——同一条结论只有一份。"""
    registry = _registry(root)
    if registry is None:
        return Outcome(True, "无判定登记件（不适用）")
    spec = root / "spec" / "spec.md"
    if not spec.exists():
        return Outcome(True, "无规格件（不适用）")
    text = read_text(spec)
    headers = header_index(text, ["编号", "要求"])
    if not headers:
        return Outcome(True, "规格件无约束要求表（不适用）")
    registered = {
        str(c.get("id", "")).strip(): str(c.get("conclusion", "")).strip()
        for c in registry.get("constraints", []) or []
        if isinstance(c, dict)
    }
    diverged: list[str] = []
    checked = 0
    for _, cells in md_table_rows(text, ["编号", "要求"]):
        rid = cell(cells, headers, "编号").strip(" `*")
        want = registered.get(rid)
        if not want:
            continue
        checked += 1
        got = cell(cells, headers, "要求")
        if _norm(got) != _norm(want):
            diverged.append(f"{rid}（登记「{want[:24]}…」/ 出口「{got[:24]}…」）")
    if diverged:
        return Outcome(False, "出口章与登记源不同文：" + "；".join(diverged[:5]))
    if checked == 0:
        return Outcome(True, "出口章没有与登记源对应的编号（不适用）")
    return Outcome(True, f"{checked} 行与登记源同文")


@checker
def p17_landing_md_yaml_mismatch(root: Path, ctx: Ctx) -> Outcome:
    """方案正文的落点与契约里的落点是同一份冻结的两次渲染，不能各写各的。"""
    freeze = _freeze(root)
    if freeze is None:
        return Outcome(True, "无知识冻结块（不适用）")
    plan = root / "plan" / "plan.md"
    if not plan.exists():
        return Outcome(True, "无方案正文（不适用）")
    text = read_text(plan)
    headers = header_index(text, ["编号", "落点"])
    if not headers:
        return Outcome(False, "方案正文缺义务表（须有编号与落点两列）")
    md: dict[str, str] = {}
    for _, cells in md_table_rows(text, ["编号", "落点"]):
        for rid in ENTRY_ID_RE.findall(cell(cells, headers, "编号")):
            md[rid] = cell(cells, headers, "落点")
    bad: list[str] = []
    for ob in _obligations(freeze):
        rid = str(ob.get("rule", "")).strip()
        landings = ob.get("landing")
        refs = landings if isinstance(landings, list) else ([landings] if landings else [])
        tails = [str(r).split(".")[-1] for r in refs if str(r).strip()]
        if not rid or not tails:
            continue
        row = md.get(rid)
        if row is None:
            bad.append(f"{rid}（正文表缺行）")
        elif not any(t in row for t in tails):
            bad.append(f"{rid}（正文「{row[:20]}」/ 契约「{'、'.join(tails)}」）")
    if bad:
        return Outcome(False, "落点两处对不上：" + "；".join(bad[:5]))
    return Outcome(True, f"{len(md)} 条义务的落点两处一致")


@checker
def p18_step_equals_criterion(root: Path, ctx: Ctx) -> Outcome:
    """业务步骤不能拿验收编号顶替——那样这条义务在流程里没有落点。"""
    freeze = _freeze(root)
    if freeze is None:
        return Outcome(True, "无知识冻结块（不适用）")
    obligations = _obligations(freeze)
    if not obligations:
        return Outcome(True, "冻结无义务条目（不适用）")
    same = [
        str(ob.get("rule", ""))
        for ob in obligations
        if str(ob.get("step", "")).strip()
        and str(ob.get("step", "")).strip() == str(ob.get("criterion", "")).strip()
    ]
    if same:
        return Outcome(False, "step 拿验收编号顶替：" + "、".join(same[:8]))
    return Outcome(True, f"{len(obligations)} 条义务的 step 都是业务步骤")


# --------------------------------------------------------------------------- #
# adapt（工程适配）
# --------------------------------------------------------------------------- #

ADAPT_SCRIPT = "skills/story-adaptation/scripts/adapt-scan.mjs"


@checker
def a01_adapt_couples_to_mechanism(root: Path, ctx: Ctx) -> Outcome:
    """adapt 的交付件写死了扩展内部结构。

    adapt 只该认**类别边界**——目录、后缀、frontmatter、manifest 段。一旦 Skill 或脚本里
    出现某个 hook 的「阶段目录 + 文件」、某个知识文件名或模式名，机制一改 adapt 就跟着废；
    而「机制大改后能用 adapt 快速适配」正是把它排在机制重构之前的全部理由（B3-10 / KD-10）。

    判定基准全部派生：阶段名取 ``hooks/`` 的子目录，知识文件名与条目编号取激活清单。
    **派生为空不当作通过**——那说明基准没建起来，不是「零命中」（G7）。
    """
    adapt_dir = root / "skills" / "story-adaptation"
    if not adapt_dir.exists():
        return Outcome(True, "无 adapt 交付件（能力未建）")
    hooks_dir = root / "hooks"
    phases = sorted(p.name for p in hooks_dir.iterdir() if p.is_dir()) if hooks_dir.exists() else []
    names = activation_names(root)
    slugs, entries = names["slugs"], names["entries"]
    if not phases and not slugs:
        return Outcome(False, "判定基准派生为空（hooks 阶段目录与激活清单都取不到），不当作通过")
    hits: list[str] = []
    for path in iter_files(adapt_dir, ALL_SUFFIXES):
        rel = path.relative_to(root).as_posix()
        for lineno, line in enumerate(split_lines(read_text(path)), 1):
            for ph in phases:
                if re.search(rf"\bhooks/{re.escape(ph)}/\S", line):
                    hits.append(f"{rel}:{lineno} 写死 hook 路径 `hooks/{ph}/…`")
            for slug in sorted(slugs):
                if slug in line:
                    hits.append(f"{rel}:{lineno} 写死知识文件名 `{slug}`")
            for entry in sorted(entries):
                if re.search(rf"\b{re.escape(entry)}\b", line):
                    hits.append(f"{rel}:{lineno} 写死条目编号 `{entry}`")
    if hits:
        return Outcome(False, "adapt 交付件耦合机制内部：" + "；".join(dict.fromkeys(hits[:6])))
    return Outcome(True, f"adapt 交付件只认类别边界（基准：{len(phases)} 阶段 / {len(slugs)} 知识文件）")


def _run_adapt_check(target: Path, package: Path) -> subprocess.CompletedProcess:
    """在给定的包/目标上跑真实 ``--scan`` 建基线，施加 ``after/`` 变更，再跑 ``--check``。

    判定不在这里重实现：调真实脚本，退出码即结论（同 M15 / M18 的做法）。
    """
    script = package / "doc" / "extensions" / ADAPT_SCRIPT
    if not script.exists():
        script = REPO_ROOT / "doc" / "extensions" / ADAPT_SCRIPT
    run = lambda mode: subprocess.run(
        ["node", str(script), mode, "--target", str(target), "--package", str(package)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(REPO_ROOT))
    scan = run("--scan")
    if scan.returncode != 0:
        return scan
    after = target.parent / "after"
    if after.exists():
        for src in sorted(after.rglob("*")):
            if src.is_file():
                dst = target / src.relative_to(after)
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(src.read_bytes())
    return run("--check")


@checker
def a02_adapt_check_blind(root: Path, ctx: Ctx) -> Outcome:
    """适配后的核对判不出已知违规（核对形同虚设）。

    四项各自要有区分力：① 机制目录留着旧文件 ② 目标知识正文被改写 ③ 未确认的事实面进了
    启用清单 ④ 目标自定义文件被动过。这四种只要有一种漏过，「适配完成」就只是句口号。

    夹具自带 ``package/`` 与 ``target/`` 两棵树、可选 ``after/``（写入后的状态）；整棵树先复制到
    临时目录再跑，夹具本身不被写脏。真实目标用**当前包**去核一棵已提交的未适配目标树，
    验证它在真包上同样判得出——不是只在迷你夹具里有效。
    """
    import shutil, tempfile

    if not (REPO_ROOT / "doc" / "extensions" / ADAPT_SCRIPT).exists():
        return Outcome(True, "无 adapt 辅助脚本（能力未建）")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        if (root / "target").exists() and (root / "package").exists():   # 夹具
            shutil.copytree(root, tmp / "case")
            proc = _run_adapt_check(tmp / "case" / "target", tmp / "case" / "package")
        else:                                                            # 真实目标
            src = REPO_ROOT / "test" / "story" / "fixtures" / "adapt" / "target-prior"
            if not src.exists():
                return Outcome(False, "缺未适配目标树夹具，真实目标无法取证")
            shutil.copytree(src, tmp / "target")
            proc = _run_adapt_check(tmp / "target", REPO_ROOT)
        out = (proc.stdout + proc.stderr).strip()

    if (root / "target").exists():                       # 夹具：退出码即结论
        return Outcome(proc.returncode == 0, out[:400] if proc.returncode else "四项核对通过")
    # 真实目标：未适配的树必须被判出来；判通过才是形态成立（核对瞎了）
    if proc.returncode == 0:
        return Outcome(False, "对未适配的目标树判了通过——核对失效")
    return Outcome(True, "当前包对未适配目标树判得出差异：" + out.splitlines()[0][:160])


# --------------------------------------------------------------------------- #
# 批次 3 子批 A：作者面通道
# --------------------------------------------------------------------------- #

#: `author.md` 的行数上限——它是索引不是教材，长过这个数说明判据推理又搬回来了。
AUTHOR_DOC_MAX_LINES = 60

#: 判据推理搬回 author.md 的形态——**整段**展开「怎么判」，而不是一句「门禁会拦什么」。
#: 只认带标题的推理块。一句「判据是 X 不是 Y」是简洁的门禁说明，属于须知该有的内容，
#: 拿它当推理段会把正确的写法也判掉（实测 ut/author.md 就撞在这上面）。
REASONING_MARKERS = ("三个自问", "写每一行前", "自问：")

#: author.md 的四段结构：读哪些文件 / 产出形态 / 跑哪条命令 / 门禁拦什么。
#: 段落数明显超出，说明教材内容又搬回来了——这比关键词更能代表「不再是索引」。
AUTHOR_DOC_MAX_SECTIONS = 6


@checker
def a03_author_channel_broken(root: Path, ctx: Ctx) -> Outcome:
    """给阶段作者的要求写在了只有 verifier 读得到的地方。

    8 个 hook 事件全部在 harness 同一进程、verifier 子 agent 之前跑完，片段唯一去处是
    ``ai-prompt.md`` 尾部——``hooks/<phase>/*.md`` 里写什么，**写产物的那个主 agent 都看不到**。
    基线态六份 ``on_context_load.md`` 400 行通篇是作者向文本（「spec 是什么」「三个自问」
    「不写文档坐标」），于是作者只能靠门禁报错反推要求，内网实测 plan「仅展示」、coding「完全失效」。

    本条守两件事：``hooks/**/*.md`` 只剩 ``author.md``；每份是**索引**不是教材
    （≤60 行、不整段展开判据推理）。判定基准派生自 ``hooks/`` 的阶段目录，不写死阶段名。
    """
    hooks_dir = root / "hooks"
    if not hooks_dir.exists():
        return Outcome(True, "无 hooks 目录")
    phases = sorted(p.name for p in hooks_dir.iterdir() if p.is_dir() and p.name != "shared")
    if not phases:
        return Outcome(False, "判定基准派生为空（hooks/ 下没有阶段目录），不当作通过")

    hits: list[str] = []
    for md in sorted(hooks_dir.rglob("*.md")):
        rel = md.relative_to(root).as_posix()
        if md.name != "author.md":
            hits.append(f"{rel} 是给作者的文本却放在 hooks 里——它只进 ai-prompt，作者读不到")
            continue
        # 末尾换行是文件的正常形态，不是内容行——算进去会让每份都多 1 行。
        lines = split_lines(read_text(md))
        while lines and not lines[-1].strip():
            lines.pop()
        if len(lines) > AUTHOR_DOC_MAX_LINES:
            hits.append(f"{rel} {len(lines)} 行，超过 {AUTHOR_DOC_MAX_LINES}——author.md 只做索引，不做教材")
        body = read_text(md)
        for marker in REASONING_MARKERS:
            if marker in body:
                hits.append(f"{rel} 含判据推理段「{marker}」——那属于模板注释或 overlay，不属于须知")
        sections = [ln for ln in lines if ln.startswith("## ")]
        if len(sections) > AUTHOR_DOC_MAX_SECTIONS:
            hits.append(f"{rel} 有 {len(sections)} 个二级段落，超过 {AUTHOR_DOC_MAX_SECTIONS}"
                        "——须知是四段索引（读什么 / 写成什么 / 跑什么 / 拦什么），不是教材")
    if hits:
        return Outcome(False, "；".join(hits[:6]))
    covered = [p for p in phases if (hooks_dir / p / "author.md").exists()]
    if not covered:
        return Outcome(False, f"{len(phases)} 个阶段一个 author.md 都没有——作者面通道不存在")
    return Outcome(True, f"{len(covered)}/{len(phases)} 个阶段有 author.md，均 ≤{AUTHOR_DOC_MAX_LINES} 行且无判据推理段")


@checker
def a04_gate_pass_leaves_no_trace(root: Path, ctx: Ctx) -> Outcome:
    """门禁通过时不留痕——「跑了并通过」与「根本没跑」事后同形。

    框架的 dispatcher 只在 hook 返回 ``ok:false`` 时把结果记进报告，通过的那次什么都不留。
    基线态六个 ``post_check.mjs`` 里只有两个写留痕，AR90004 的 ``coding/reports/`` 里
    没有 ``ext-post-check.json``——要证明某条判据在真实链路上生效过，举不出任何证据。

    判据：每个阶段的 ``post_check.mjs`` 都能追溯到留痕（直接 import ``evidence.mjs``，
    或经统一出口间接调用）。阶段清单派生自 ``hooks/`` 子目录。
    """
    hooks_dir = root / "hooks"
    if not hooks_dir.exists():
        return Outcome(True, "无 hooks 目录")
    phases = sorted(p.name for p in hooks_dir.iterdir() if p.is_dir() and p.name != "shared")
    if not phases:
        return Outcome(False, "判定基准派生为空（hooks/ 下没有阶段目录），不当作通过")

    # 间接留痕：shared/ 下哪些模块自己写了留痕，import 它们就等于留了痕。
    tracing: set[str] = set()
    shared = hooks_dir / "shared"
    if shared.exists():
        for mod in sorted(shared.glob("*.mjs")):
            if "writePostCheckEvidence" in read_text(mod):
                tracing.add(mod.name)

    missing: list[str] = []
    for phase in phases:
        pc = hooks_dir / phase / "post_check.mjs"
        if not pc.exists():
            continue
        body = read_text(pc)
        if "writePostCheckEvidence" in body:
            continue
        if any(re.search(rf"from ['\"][^'\"]*{re.escape(name)}['\"]", body) for name in tracing):
            continue
        missing.append(f"hooks/{phase}/post_check.mjs 通过时不留痕")
    if missing:
        return Outcome(False, "；".join(missing))
    return Outcome(True, f"{len(phases)} 个阶段的 post_check 均留痕（含经 {sorted(tracing)} 间接留痕）")


@checker
def a05_entry_file_misses_extension_section(root: Path, ctx: Ctx) -> Outcome:
    """扩展交付了入口段，宿主入口文件却没带上它。

    主 agent 会话开始时自动进入上下文的只有入口文件（claude 读 CLAUDE.md，
    codex 只读 AGENTS.md、不加载任何 rules 目录）。扩展把「动笔前先读 author.md」
    这句话交付成 ``AGENTS.section.md`` 之后，若没写进两份入口文件，作者面通道就是断的
    ——文件在仓里躺着，没有任何机制会把它送到作者眼前。

    包没有 ``AGENTS.section.md`` 时本条不适用（未启用该形态）。

    **交付位置有两处**：扩展根（夹具形态）与 ``skills/story/``（本仓实际交付的位置）。
    只认扩展根时，本条在真实仓上恒判「该形态未启用」而静默跳过——检查入口段有没有
    送达的这条判据，自己没送达。
    """
    section = next((p for p in (root / "AGENTS.section.md",
                                root / "skills" / "story" / "AGENTS.section.md")
                    if p.exists()), None)
    if section is None:
        return Outcome(True, "包未交付 AGENTS.section.md（该形态未启用）")
    body = _norm(read_text(section))
    if not body:
        return Outcome(False, "AGENTS.section.md 是空的——交付了一个空通道")

    # 入口文件在宿主工程根：从扩展目录向上找，最多三级。
    host = None
    probe = root
    for _ in range(4):
        if (probe / "CLAUDE.md").exists() or (probe / "AGENTS.md").exists():
            host = probe
            break
        if probe.parent == probe:
            break
        probe = probe.parent
    if host is None:
        return Outcome(False, "找不到宿主入口文件（CLAUDE.md / AGENTS.md）——无从证明这段送达了")

    missing: list[str] = []
    seen: list[str] = []
    for name in ("AGENTS.md", "CLAUDE.md"):
        entry = host / name
        if not entry.exists():
            if name == "AGENTS.md":
                missing.append(f"{name} 不存在")
            continue
        seen.append(name)
        if body not in _norm(read_text(entry)):
            missing.append(f"{name} 的「实例扩展」节没有 AGENTS.section.md 全文")
    if missing:
        return Outcome(False, "；".join(missing) + "——写入后须重渲染 / 重写入口文件")
    return Outcome(True, f"{seen} 均含 AGENTS.section.md 全文")


# --------------------------------------------------------------------------- #
# 批次 3 子批 B：探针区分力与引文核实
# --------------------------------------------------------------------------- #


def _run_node(root: Path, name: str, script: str) -> tuple[dict | None, str]:
    """在夹具目录里跑一段 ESM，取最后一行 JSON。

    直接调**扩展里真实的执行器**，不在 checker 里重实现判定——重实现出来的是
    「我以为它这么判」，与真实链路上跑的那个可以悄悄分叉（同 A02 / M15 的做法）。
    """
    tmp = root / name
    try:
        tmp.write_text(script, encoding="utf-8")
        # 显式 utf-8：Windows 上 text=True 走 GBK，探针文案里的中文会让 stdout 解码失败、
        # 悄悄变成 None——「跑了没输出」与「判据没过」就此同形。
        r = subprocess.run(["node", str(tmp)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
    except Exception as e:  # noqa: BLE001
        return None, f"跑不起来：{e}"
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    if r.returncode != 0:
        return None, f"退出码 {r.returncode}：{(r.stderr or '').strip()[:200]}"
    out = (r.stdout or "").strip().splitlines()
    if not out:
        return None, "没有输出"
    try:
        return json.loads(out[-1]), ""
    except Exception:  # noqa: BLE001
        return None, f"输出不是 JSON：{out[-1][:160]}"


def _ext_file(root: Path, rel: str) -> Path | None:
    """夹具里没有就退回真实扩展目录——夹具只放源码片段，执行器始终是真的那一份。"""
    for base in (root, DEFAULT_EXTENSION_DIR):
        p = base / rel
        if p.exists():
            return p
    return None


@checker
def b01_probe_no_discrimination(root: Path, ctx: Ctx) -> Outcome:
    """探针对已知违规没有区分力——恒真探针换了个写法。

    基线的 coding 探针是 ``\\b名\\b`` 跨文件文本存在性：不分声明/调用/注释，
    末段是容器名时恒真。实测一条明晃晃的违规（方向性布局参数写成 left/right）被它放行，
    因为它查的是「组件名在不在」，而组件名当然在。

    本条调**真实的探针执行器**，用两个形态验判别力：
      ① ``absent_regex`` 要报出不该出现的写法；
      ② ``referenced_outside_definition`` 要判出零调用的角色类，
         且**不被另一个文件注释里的提及骗过**（实施中真的踩过这一下）。
    """
    probes = _ext_file(root, "hooks/shared/probes.mjs")
    if probes is None:
        return Outcome(False, "找不到探针执行器 probes.mjs——判定基准不存在，不当作通过")
    files = sorted(p.name for p in root.glob("*.ets"))
    if not files:
        return Outcome(True, "夹具里没有源码片段（该形态未启用）")

    script = "\n".join([
        f"import {{ runProbe }} from {json.dumps(probes.resolve().as_uri())};",
        f"const files = {json.dumps(files)};",
        f"const root = {json.dumps(str(root.resolve()))};",
        # r-string：`\b` 在普通字符串里是退格符，会被悄悄吃掉（坑 #36 的又一次）
        r"const a = runProbe({kind:'absent_regex',pattern:String.raw`\b(left|right)\s*:`,"
        r"count:null,raw:''}, {projectRoot: root, files, entityName:'Sheet', entityKind:'components'});",
        "const b = runProbe({kind:'referenced_outside_definition',pattern:'',count:null,raw:''},"
        " {projectRoot: root, files, entityName:'Orphan', entityKind:'files'});",
        "console.log(JSON.stringify({absent: a, ref: b}));",
    ])
    out, err = _run_node(root, "_probe_check.mjs", script)
    if out is None:
        return Outcome(False, f"探针执行器{err}")

    # checker 只如实判「这份源码有没有违规」，**不去猜自己在跑哪个夹具**——
    # 正反由框架的 self_check 核对（反夹具必 FAIL、正夹具必 PASS）。
    # 让 checker 按夹具名分支，等于把判定和期望写在同一处，两边一起错也发现不了。
    bad = []
    if not out["absent"]["ok"]:
        bad.append(f"方向性写法：{out['absent']['detail'][:90]}")
    if not out["ref"]["ok"]:
        bad.append(f"角色引用：{out['ref']['detail'][:90]}")
    if bad:
        return Outcome(False, "；".join(bad))
    return Outcome(True, f"两个探针都放行（扫 {out['absent']['scanned']} 个文件）")

def _story_build_cycle(root: Path, extra_verdict: str | None = None) -> tuple[int, str]:
    """跑 init → audit →（可选写裁决表）→ check，返回 check 的退出码与输出。

    **在夹具的副本上跑**：`init` 会写决策登记骨架，直接在夹具里跑会把它写脏，
    且上一次的产物会影响下一次的判定。
    """
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / root.name
        shutil.copytree(root, work)
        return _story_build_in(work, extra_verdict)


def _story_build_in(root: Path, extra_verdict: str | None) -> tuple[int, str]:
    build = _ext_file(root, "skills/story/scripts/story-build.mjs")
    if build is None:
        build = DEFAULT_EXTENSION_DIR / "skills" / "story" / "scripts" / "story-build.mjs"

    # 先让材料清单就位：图片身份与材料清单集合这两条判据都问它，没有清单它们只会
    # 说「未执行」——而夹具自检要的是**判据真的跑过**，跳过等于放过。
    flow = _ext_file(root, "skills/story/scripts/story_flow.py")
    if flow is None:
        flow = DEFAULT_EXTENSION_DIR / "skills" / "story" / "scripts" / "story_flow.py"
    subprocess.run(
        [sys.executable, str(flow), "round", "--feature", "AR90001",
         "--project-root", str(root)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    def run(cmd: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["node", str(build), cmd, "--feature", "AR90001", "--project-root", str(root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    r = run("init")
    if r.returncode != 0:
        return r.returncode, f"init 跑不起来：{(r.stderr or r.stdout or '')[:200]}"

    r = run("check")
    return r.returncode, ((r.stderr or "") + (r.stdout or "")).strip()


_NORM_RE = re.compile(r"[\s，。、；：!?！？（）()「」【】｜|*`>-]")


def _norm(text: str) -> str:
    return _NORM_RE.sub("", str(text or ""))

@checker
def r02_knowledge_row_missing(root: Path, ctx: Ctx) -> Outcome:
    """激活规约条目在合规章的判定表里缺行——逐条判定又丢了。

    判定原先落在一份独立的记录文件里，那份文件退场后既无作业指引也无门禁。
    现在条目是来源单元，缺一条要点名一条。
    """
    if not (root / "doc" / "features" / "AR90001" / "AR" / "story.md").exists():
        return Outcome(True, "夹具里没有 story（该形态未启用）")
    code, out = _story_build_cycle(root, "提交之后回执没到之前，界面停在等待态")
    if code == 0:
        return Outcome(True, "激活规约条目在判定表里逐条有行")
    if "判定表里没有行" in out:
        return Outcome(False, f"判定表缺行被点名：{out.split('判定表里没有行')[0][-60:]}判定表里没有行")
    return Outcome(False, f"check 未过（非缺行原因）：{out[:200]}")


#: story 专属要求的说法——它们出现在**非** story 需求的门禁回话里，就是作者面泄漏。
_STORY_ONLY_WORDS = ("story", "三份产物", "叙事件", "技术契约", "归档件", "三级关卡")


def _spec_post_check(root: Path) -> tuple[bool, str] | None:
    """跑真实的 spec post_check，回 (ok, message)；跑不起来回 None。

    **在副本上跑**，与 `_story_build_cycle` 同一口径：hook 通过时也会写留痕
    （`spec/reports/ext-post-check.json`，里面有时间戳），在夹具原地跑就是每跑一次
    把夹具写脏一次——那两个文件因此长期挂在工作区里，被一次次捎带提交，
    而谁也说不清它们到底改了什么。
    """
    script = (
        "import {pathToFileURL} from 'node:url';"
        "const hook=(await import(pathToFileURL(process.argv[1]).href)).default;"
        "const r=await hook({phase:'spec',feature:process.argv[3],projectRoot:process.argv[2]});"
        "console.log(JSON.stringify({ok:r.ok!==false,message:r.message??''}));")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / root.name
        shutil.copytree(root, work)
        hook = _ext_file(work, "hooks/spec/post_check.mjs")
        if hook is None:
            hook = DEFAULT_EXTENSION_DIR / "hooks" / "spec" / "post_check.mjs"
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", script, "--",
             str(hook), str(work), "AR90001"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    return bool(data["ok"]), str(data["message"])


@checker
def w01_non_story_invisible(root: Path, ctx: Ctx) -> Outcome:
    """不走 /story 的需求被 story 专属要求拦住——扩展对它该是隐形的。

    判据面本身已经按 `isStoryFeature` 分好了：§9 技术契约、术语解释列、三份产物
    只在有流程契约时才要求；§10 / §11 是知识判定的出口，对所有需求生效
    （判定产生的代码要求不进 spec，编码那里就拿不到）。

    这一条守的是**它别退回去**：只写 §10/§11 的需求跑 spec 门禁要能过，
    而且回话里不能提 story 专属的那几样——作者读到「三份产物」「技术契约」，
    就会去写他根本不需要写的东西。
    """
    spec = root / "doc" / "features" / "AR90001" / "spec" / "spec.md"
    if not spec.exists():
        return Outcome(True, "夹具里没有规格件（该形态未启用）")
    result = _spec_post_check(root)
    if result is None:
        return Outcome(False, "spec post_check 跑不起来")
    ok, message = result
    has_flow = (root / "doc" / "features" / "AR90001" / "AR" / "story-flow.json").exists()
    if has_flow:
        # 有流程契约 = 走了 /story：该被要求写全，拦住才对
        if ok:
            return Outcome(False, "走了 /story 却没拦——§9 与三份产物本该是硬要求")
        return Outcome(False, f"story 需求被正常拦下：{message.splitlines()[2][:70] if len(message.splitlines()) > 2 else message[:70]}")
    if not ok:
        return Outcome(False, f"非 story 需求被拦住了：{message[:220]}")
    leaked = [w for w in _STORY_ONLY_WORDS if w in message.lower()]
    if leaked:
        return Outcome(False, f"门禁回话里提了 story 专属要求 {leaked}——对这个需求它们不存在")
    return Outcome(True, "非 story 需求只写两节即通过，回话里没有 story 专属要求")

@checker
def s05_main_text_identifier(root: Path, ctx: Ctx) -> Outcome:
    """工程标识、规约编号、检索措辞出现在主叙事里——打断了面向人的阅读。

    它们不是不该在归档件里：评审者要查接口名、要核规约判定，查得到才行。
    问题在于位置——读者顺着九章读下来，每隔两行撞见一个 camelCase 就得停下来
    判断「这是我要懂的东西吗」。附录是它们的唯一落点，主叙事写中文业务名。

    判据不是「报了错」而是**点名了是哪一类、在哪一行**：只说「不合规」的门禁，
    作者只能靠删字去试。
    """
    if not (root / "doc" / "features" / "AR90001" / "AR" / "story.md").exists():
        return Outcome(True, "夹具里没有 story（该形态未启用）")
    code, out = _story_build_cycle(root, "待提交状态：用户点了提交但未收到回执")
    if code == 0:
        return Outcome(True, "主叙事零工程标识、零规约编号、零检索措辞")
    if "主叙事出现" not in out:
        return Outcome(False, f"check 未过（非语言红线原因）：{out[:200]}")
    kinds = [k for k in ("工程标识", "rule_id", "search_phrase") if k in out]
    if len(kinds) < 3:
        return Outcome(False, f"语言红线只报了 {kinds}，三类应当各自点名：{out[:220]}")
    return Outcome(False, f"三类语言红线各自被点名：{'、'.join(kinds)}")


@checker
def s06_appendix_dump(root: Path, ctx: Ctx) -> Outcome:
    """附录长出合同之外的小节、材料原文成段搬进围栏块——附录成了倾倒区。

    附录是全篇唯一允许出现工程标识的地方，于是它天然最容易变成倾倒区。
    首跑实测：产物在附录下多长出一个「机器核对索引」小节，255 行原文占全篇 58%，
    而当时的判据只核「附录这一章存在」，倾倒完全合法。
    判的是结构不是内容——约定之外的小节、非 mermaid 的围栏块、空节，三样都不该有。
    """
    if not (root / "doc" / "features" / "AR90001" / "AR" / "story.md").exists():
        return Outcome(True, "夹具里没有 story（该形态未启用）")
    code, out = _story_build_cycle(root, "待提交状态：用户点了提交但未收到回执")
    if code == 0:
        return Outcome(True, "附录只有约定的几节，节内是表和列表")
    if "多了一节" in out or "不是原文存放处" in out or "是空的" in out:
        return Outcome(False, "附录的倾倒被点名（合同外小节 / 围栏块 / 空节）")
    return Outcome(False, f"check 未过（非附录结构原因）：{out[:200]}")


@checker
def s07_review_legacy_fields(root: Path, ctx: Ctx) -> Outcome:
    """评审记录长回签署字段与状态行——表单再次膨胀成需要说明书的东西。

    判据是「需要说明书就是设计错了」。七个字段加一行状态每次都以「让评审更规范」的
    名义长回来，实际后果是评审人先读一遍字段表，再在六个答不上来的格子里跳过或胡填，
    而「已确认」因此不可信。留下的只有「审核结果：」一行，评审人在它后面写具体内容。
    """
    if not (root / "doc" / "features" / "AR90001" / "AR" / "review.md").exists():
        return Outcome(True, "夹具里没有评审记录（该形态未启用）")
    code, out = _story_build_cycle(root, "待提交状态：用户点了提交但未收到回执")
    if code == 0:
        return Outcome(True, "评审记录只有「审核结果：」一行留给评审人")
    if "评审记录里出现" in out:
        return Outcome(False, "签署字段与状态行被点名")
    return Outcome(False, f"check 未过（非评审表单原因）：{out[:200]}")

@checker
def s10_image_path_copied(root: Path, ctx: Ctx) -> Outcome:
    """图片被复制进归档目录、改个名再引用——副本没人维护，改名后认不出是原来那张。

    实测链条：材料抽图落在素材目录（机制内）→ 模型复制一份进界面参考目录（合理）
    → **又复制第三份进归档目录并改名**，story 按裸文件名引用。模板从来只约定图题形态，
    没约定引用路径口径，于是这条链一路无人拦。
    """
    if not (root / "doc" / "features" / "AR90001" / "AR" / "story.md").exists():
        return Outcome(True, "夹具里没有 story（该形态未启用）")
    code, out = _story_build_cycle(root, "待提交状态：用户点了提交但未收到回执")
    if code == 0:
        return Outcome(True, "图片引的是登记里那张图的既有落盘位置")
    if "不在材料的图片登记里" in out:
        return Outcome(False, "归档目录下的副本引用被点名")
    return Outcome(False, f"check 未过（非图片路径原因）：{out[:200]}")


@checker
def s11_image_two_names(root: Path, ctx: Ctx) -> Outcome:
    """同一张图被两个路径引用，story 里当成两张不同的图各引一次。

    实测：两个文件的内容完全相同，story 分别称它们为「管理页」与「管理页布局参考」，
    后一张没有任何说明段——读者以为看漏了什么，其实是同一张图。
    """
    if not (root / "doc" / "features" / "AR90001" / "AR" / "story.md").exists():
        return Outcome(True, "夹具里没有 story（该形态未启用）")
    code, out = _story_build_cycle(root, "待提交状态：用户点了提交但未收到回执")
    if code == 0:
        return Outcome(True, "同一张图只引一次")
    if "同一张图被两个路径引用" in out:
        return Outcome(False, "同图两名被点名")
    return Outcome(False, f"check 未过（非图片路径原因）：{out[:200]}")

# --------------------------------------------------------------------------
# 形态守恒（check ⑪）的七条：正反例都是一段章正文
# --------------------------------------------------------------------------

#: 底样：十章齐、附录合法的一份 story。除被测那一章外，其余章都是「本需求不涉及。」，
#: ⑪ 对空节豁免，所以这份底样只会响被测的那一条。
FORM_BASE = (REPO_ROOT / "test" / "story" / "fixtures" / "failure-modes"
             / "R01-verdict-echo" / "good")


def _story_with_chapter(chapter: str, body: str) -> tuple[int, str]:
    """把底样的某一章换成给定正文，跑一次 story-build check。"""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work"
        shutil.copytree(FORM_BASE, work)
        path = work / "doc" / "features" / "AR90001" / "AR" / "story.md"
        lines = path.read_text(encoding="utf-8").split("\n")
        out, skipping = [], False
        for line in lines:
            if line.startswith("## "):
                skipping = line[3:].strip() == chapter
                out.append(line)
                if skipping:
                    out.append("")
                    out.extend(body.strip().split("\n"))
                    out.append("")
                continue
            if not skipping:
                out.append(line)
        path.write_text("\n".join(out), encoding="utf-8")
        return _story_build_in(work, "待提交状态：用户点了提交但未收到回执")


def _form_outcome(chapter: str, bad: str, good: str, needle: str) -> Outcome:
    """反例必须被点名，正例必须放行——两头都验，判据才既有区分力又不误伤。"""
    _, out = _story_with_chapter(chapter, bad)
    if needle not in out:
        return Outcome(False, f"反例没被点名（找「{needle}」）：{out[:200]}")
    _, out = _story_with_chapter(chapter, good)
    if "形态守恒" in out:
        return Outcome(False, f"正例被形态判据拦下：{out[:200]}")
    return Outcome(True, "反例被点名、正例放行")


@checker
def s01_diagram_degraded(root: Path, ctx: Ctx) -> Outcome:
    """流程图压成「A → B → C」箭头文字——上一版只判「图有落点」，箭头文字也算落点。"""
    return _form_outcome(
        "业务流程",
        "主路径：进入页面 → 查询资格 → 风险确认 → 提交 → 查询结果。\n\n"
        "### 主路径\n\n1. 进入页面查询资格。\n2. 确认风险后提交。",
        "一次挂失从卡包进入，到看到真实结果结束：\n\n"
        "```mermaid\nflowchart TD\n  A[进入页面] --> B[查询资格]\n  B --> C[风险确认]\n"
        "  C --> D[提交]\n  D --> E[查询冻结结果]\n```\n\n"
        "### 主路径\n\n1. 进入页面查询资格。\n2. 确认风险后提交。",
        "一张图都没有")


@checker
def s02_terms_not_table(root: Path, ctx: Ctx) -> Outcome:
    """材料里的表在 story 里被摊成散文，逐项比对的那几列丢了。"""
    return _form_outcome(
        "术语",
        "紧急挂失是用户发现卡遗失后发起的冻结流程；冻结结果是卡云给出的最终答复；"
        "卡云是管理交通卡状态的云端服务。",
        "| 术语 | 在本需求里的意思 |\n|---|---|\n"
        "| 紧急挂失 | 用户发现交通卡遗失后发起的冻结原卡流程。 |\n"
        "| 冻结结果 | 卡云对一份挂失申请给出的最终答复。 |",
        "缺一张表")


@checker
def s08_solution_chapter_flat(root: Path, ctx: Ctx) -> Outcome:
    """已定决策成堆而方案章没有分工这一节——参与方与取舍化进散文，评审者要读完整章。"""
    return _form_outcome(
        "业务方案",
        "钱包主应用负责页面与提交，账号能力负责身份，卡云是冻结结果的唯一裁判；"
        "成功的判定上我们只认云侧明确返回已冻结。",
        "### 参与方与分工\n\n"
        "| 参与方 | 拿到什么 | 守住什么 |\n|---|---|---|\n"
        "| 钱包主应用 | 用户动作与各方返回 | 不自行认定冻结成功 |\n"
        "| 卡云 | 脱敏卡片标识 | 资格与冻结结果的唯一事实源 |\n\n"
        "业务结果以卡云为准。",
        "缺「参与方与分工」这一节")


@checker
def s09_flow_chapter_flat(root: Path, ctx: Ctx) -> Outcome:
    """有内容的流程章一个小节都没有——主路径与全部支线压在一坨散文里。"""
    return _form_outcome(
        "业务流程",
        "```mermaid\nflowchart TD\n  A[进入] --> B[提交]\n```\n\n"
        "用户进入页面查询资格，确认风险后提交，云侧受理后查询真实冻结结果；"
        "身份未完成时先去补身份，状态冲突时刷新后重新确认。",
        "```mermaid\nflowchart TD\n  A[进入] --> B[提交]\n```\n\n"
        "### 主路径\n\n1. 进入页面查询资格。\n2. 确认风险后提交。\n\n"
        "### 身份未完成的恢复\n\n**时机**：查询资格时身份未完成。\n\n"
        "**方案**：转入既有身份流程。\n\n**走向**：回来后重新查询资格。",
        "缺「主路径」这一节")


@checker
def s12_tradeoff_prose(root: Path, ctx: Ctx) -> Outcome:
    """关键取舍那一节写成散文——「否了什么、为什么被否的不行」被化进句子里。"""
    return _form_outcome(
        "业务方案",
        "### 参与方与分工\n\n| 参与方 | 守住什么 |\n|---|---|\n| 卡云 | 唯一事实源 |\n\n"
        "### 关键取舍\n\n"
        "成功的判定上我们选择只认云侧明确返回已冻结，没有采用端侧提交成功即宣告冻结的做法，"
        "因为那样在响应丢失时会出现假冻结。",
        "### 参与方与分工\n\n| 参与方 | 守住什么 |\n|---|---|\n| 卡云 | 唯一事实源 |\n\n"
        "### 关键取舍\n\n"
        "| 取舍 | 选了什么 | 否了什么 | 为什么被否的不行 |\n|---|---|---|---|\n"
        "| 成功的判定 | 云侧明确返回已冻结才展示成功 | 端侧提交成功即宣告冻结 | "
        "响应丢失时宣告成功是假冻结，用户以为卡安全了而原卡还能用。 |",
        "缺一张表")


@checker
def s13_limited_and_error_in_one_table(root: Path, ctx: Ctx) -> Outcome:
    """设计内的受限结果与真正的失败混进同一张表——读者分不清哪些要处理。"""
    return _form_outcome(
        "异常与恢复",
        "| 情况 | 用户看到什么 |\n|---|---|\n"
        "| 身份未完成 | 身份说明与检查点提示 |\n"
        "| 提交响应丢失 | 处理中，可确认结果 |",
        "先分清两类。\n\n"
        "### 设计内的受限结果\n\n"
        "| 受限状态 | 用户看到什么 | 出路 |\n|---|---|---|\n"
        "| 身份未完成 | 身份说明与检查点提示 | 完成身份流程后从检查点继续 |\n\n"
        "### 需要处理的异常\n\n"
        "| 异常 | 用户看到什么 | 系统怎么处理 |\n|---|---|---|\n"
        "| 提交响应丢失 | 处理中，可确认结果 | 用同一幂等标识查既有申请 |",
        "缺「设计内的受限结果」这一节")


@checker
def s14_acceptance_bulleted(root: Path, ctx: Ctx) -> Outcome:
    """验收写成 bullet——编号与通过条件挤在一行文字里，没法逐条比对。"""
    return _form_outcome(
        "验收",
        "### 主流程\n\n"
        "- AC-R1：正常用户完成提交，只创建一次申请。\n"
        "- AC-1：未确认时提交不可用。",
        "### 主流程\n\n"
        "| 编号 | 可观察的通过条件 |\n|---|---|\n"
        "| AC-R1 | 正常用户完成提交，只创建一次申请。 |\n"
        "| AC-1 | 未确认时提交不可用，确认后可进入提交中。 |",
        "缺一张表")


@checker
def s15_appendix_prose_tail(root: Path, ctx: Ctx) -> Outcome:
    """附录表后挂散文尾巴——没地方去的工程细节挤成段。

    开头那一句目的句不算，判的是表或列表**之后**的正文段。
    """
    return _form_case(root, "表后还有一段正文", "附录每节只有目的句加表")


@checker
def s16_material_list_intermediate(root: Path, ctx: Ctx) -> Outcome:
    """材料清单里列中间产物与图片直链——清单变成倾倒区。"""
    return _form_case(root, "只列进 spec 之前的原始输入", "材料清单只有原始输入")


@checker
def s17_image_new_dir(root: Path, ctx: Ctx) -> Outcome:
    """同名图片被复制进新建的目录——按文件名比对的判据一路放行。

    实测一轮：模型自建了一个图片目录再复制一份，全树因此有五份同一张图。
    同一张图散在几个目录里，改了一处其余几处就成了旧图。
    """
    if not (root / "doc" / "features" / "AR90001" / "AR" / "story.md").exists():
        return Outcome(True, "夹具里没有 story（该形态未启用）")
    code, out = _story_build_cycle(root, "待提交状态：用户点了提交但未收到回执")
    if code == 0:
        return Outcome(True, "图片引的是既有落盘位置")
    if "新建的图片目录" in out:
        return Outcome(False, "新目录里的副本引用被点名")
    return Outcome(False, f"check 未过（非图片目录原因）：{out[:200]}")


@checker
def s18_appendix_image(root: Path, ctx: Ctx) -> Outcome:
    """图整批迁进附录——正文的承接句留在原地，读者手边没有图。

    落点判够不到：图片单元的落点是按引用位置反推的，图放哪儿它跟到哪儿。
    这一条与图守恒合围，把图逼回它讲的那一章。
    """
    return _form_case(root, "里有", "图在它讲的那一章")


@checker
def s19_material_list_prose_head(root: Path, ctx: Ctx) -> Outcome:
    """材料清单的列表之前塞散文——上一版只看列表之后。"""
    return _form_case(root, "目的句之外还有", "材料清单只有目的句和列表行")

def _form_case(root: Path, needle: str, ok: str) -> Outcome:
    """A 档固定形式的五条共用同一套跑法：good 该过，bad 该被点名。"""
    if not (root / "doc" / "features" / "AR90001" / "AR" / "story.md").exists():
        return Outcome(True, "夹具里没有 story（该形态未启用）")
    code, out = _story_build_cycle(root, "待提交状态：用户点了提交但未收到回执")
    if code == 0:
        return Outcome(True, ok)
    if needle in out:
        return Outcome(False, "固定形式被点名")
    return Outcome(False, f"check 未过（非固定形式原因）：{out[:200]}")


GOLDEN_STORY = REPO_ROOT / "test/story/golden/story-金样-AR90004.md"
GOLDEN_ASSETS = REPO_ROOT / "test/story/golden/assets"


@checker
def g01_judgement_blocks_golden(root: Path, ctx: Ctx) -> Outcome:
    """判据把已定稿的理想产物判成违规。

    这是**常驻正例**，与其它形态反过来：这里 PASS 的意思是「判据没拦金样」。
    金样是唯一的效果定义，判据从它正推——所以任何判据改动先跑这一行，
    拦住金样就是判据错，修判据不修金样。

    两个分支都验。只验「零 FAIL」不够：判项集体空转时也是零 FAIL，
    那种「通过」比拦错更难发现。
    """
    build = _ext_file(root, "skills/story/scripts/story-build.mjs")
    if build is None:
        build = DEFAULT_EXTENSION_DIR / "skills" / "story" / "scripts" / "story-build.mjs"
    if not GOLDEN_STORY.exists():
        return Outcome(False, "金样不在库里——判据失去仲裁锚")

    def run(story: Path) -> tuple[int, str]:
        proc = subprocess.run(
            ["node", str(build), "check", "--offline", "--story", str(story),
             "--project-root", str(REPO_ROOT)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        return proc.returncode, ((proc.stderr or "") + (proc.stdout or "")).strip()

    code, out = run(GOLDEN_STORY)
    if code != 0:
        return Outcome(False, f"判据拦住了金样：{out[:260]}")

    # 反分支：塞一个工程标识与一段超长的话进主叙事，判项应当各自点名
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "AR"
        work.mkdir(parents=True)
        shutil.copy2(GOLDEN_STORY, work / "story.md")
        shutil.copytree(GOLDEN_ASSETS, work / "assets")
        story = work / "story.md"
        text = read_text(story)
        head = text.split("\n## ", 2)
        if len(head) < 3:
            return Outcome(False, "金样切不出第二章——形态变了，本条的注入点要重定")
        injected = text.replace(
            "\n## " + head[2].split("\n", 1)[0],
            "\n## " + head[2].split("\n", 1)[0]
            + "\n\n这里塞一个 queryLossEligibility 进主叙事，再留一个 {{待替换的占位}}。",
            1)
        story.write_text(injected, encoding="utf-8")
        bad_code, bad_out = run(story)
    if bad_code == 0:
        return Outcome(False, "往金样里塞了工程标识与模板占位符却仍然全过——判项在空转")
    # 两个违例都取**确定性的明确记号**：工程标识与模板占位符。原先用的「超长段落」
    # 归可读性，那条随固定形式类判据退场了——反分支要验的是判项没空转，
    # 不该挂在一条会退场的判据上。
    missed = [w for w in ("工程标识", "模板占位符") if w not in bad_out]
    if missed:
        return Outcome(False, f"注入的违例没被点名：{missed}；实际输出 {bad_out[:200]}")
    return Outcome(True, "金样零 FAIL，且注入违例时判项各自点名")



#: 验证资产的名字。机制层提到它们，就是判据在照着某一份样本长——
#: 而样本是用来检验机制的，被检验的东西反过来指向检验它的东西，这条链就闭合成了自证。
VERIFICATION_ASSET_WORDS = ("金样", "golden", "fixtures", "夹具目录", "test/story")


@checker
def g02_mechanism_points_at_assets(root: Path, ctx: Ctx) -> Outcome:
    """机制层指向验证资产（金样、夹具、测试目录）。

    金样是判据的仲裁锚：判据从它正推，拦它就是判据错。但这条关系是**单向**的——
    机制层一旦提到金样或夹具，判据就从「形态规则」滑成了「照着那一份写」，
    换个业务域立刻不成立，而台账还是全绿。

    与 M02 分工：M02 判的是业务字面（单号、业务名），这条判的是**指向验证资产本身**。
    """
    def scan(lines):
        out = []
        for rel, n, line in lines:
            for word in VERIFICATION_ASSET_WORDS:
                if word in line:
                    out.append(f"{rel}:{n} 「{word}」")
                    break
        return out

    # 反例内建：判项本身也要证明它抓得住——不然「零命中」可能只是它在空转
    sample = [("<样本>", 1, "写之前先照着金样那一份的第四章排布"),
              ("<样本>", 2, "本章按合同的形态规则写就")]
    caught = scan(sample)
    if len(caught) != 1:
        return Outcome(False, f"判项抓不住自带反例（命中 {len(caught)} 条，应为 1 条）——它在空转")

    hits = scan((path.relative_to(root).as_posix(), n, line)
                for path in iter_files(root, ALL_SUFFIXES, NON_MECHANISM_DIRS)
                for n, line in enumerate(split_lines(read_text(path)), start=1))
    if hits:
        return Outcome(False, "机制层指向了验证资产：" + "；".join(hits[:5]))
    return Outcome(True, f"机制层不指向任何验证资产（词表 {len(VERIFICATION_ASSET_WORDS)} 项，反例可命中）")

_CHAIN_LINK = re.compile(r"\]\(([^)\s]+)\)")
_CHAIN_SCRIPT = re.compile(r"`([A-Za-z0-9_./-]+\.(?:mjs|py|js))`")
_CHAIN_OWNED = ("scripts/", "doc/extensions/")


def _chain_files(root: Path):
    """作者必读链：主 agent 的阶段须知、子 agent 的作业书、Skill 正文。"""
    yield from root.glob("hooks/*/author.md")
    yield from root.glob("**/phases/*.md")
    yield from root.glob("**/SKILL.md")


def _chain_resolves(root: Path, src: Path, ref: str) -> bool:
    """相对写法逐级向上试：`rules/x.md` 写在 `skills/story/phases/` 里指的是 skill 根下那份。"""
    ref = ref.split("#")[0]
    if not ref:
        return True
    cands = [root / ref]
    if ref.startswith("doc/extensions/"):
        cands.append(root / ref[len("doc/extensions/"):])
    cur = src.parent
    while True:
        cands.append(cur / ref)
        if cur == root:
            break
        cur = cur.parent
    return any(c.exists() for c in cands)


@checker
def r03_author_chain_dangling(root: Path, ctx: Ctx) -> Outcome:
    """作者必读链指向已删文件——模型照着链去读，读到的是 404。

    机制退场时最容易漏的不是代码而是**指路的那句话**：文件删了，指向它的作业书还在，
    下一个模型仍会去读、读不到就自己编一套。判的是 Markdown 链接（作者写它就是让人去读的）
    与脚本路径；工作区产物路径（`AR/story.md` 这类，在扩展包里本就不存在）与
    **历史版本结构签名**（adapt 用来识别旧版目标仓的文件名，故意不在本包里）不在判定面内。
    """
    hits = []
    for src in sorted(set(_chain_files(root))):
        for n, line in enumerate(split_lines(read_text(src)), start=1):
            refs = [r for r in _CHAIN_LINK.findall(line)
                    if not r.startswith(("http", "mailto:", "#"))]
            refs += [r for r in _CHAIN_SCRIPT.findall(line) if r.startswith(_CHAIN_OWNED)]
            for ref in refs:
                if not _chain_resolves(root, src, ref):
                    hits.append(f"{src.relative_to(root).as_posix()}:{n} → {ref}")
    if hits:
        return Outcome(False, "作者必读链指向不存在的文件：" + "；".join(hits[:5]))
    return Outcome(True, "作者必读链的引用全部落地")


@checker
def f02_verifier_task_not_well_defined(root: Path, ctx: Ctx) -> Outcome:
    """裁决者的作业书掺进整篇印象题——逐条那件事就被稀释掉了。

    实测：43 条裁决全「讲清」、0「未讲清」，引文里 15 条与被裁的单元无关。
    原因之一是同一份作业书既要它逐条对齐「这个单元 → 那一章讲没讲」，
    又要它对整篇给「好不好读、有没有取舍」的结论。两件事的粒度差着一个数量级。

    判据不写具体词：**自检维度的名字从 writer 的作业书里现取**，
    再核它们没有出现在裁决者的作业书里。同一条作业要求只该待在一份作业书里。
    """
    write_doc = _find_phase_doc(root, "story-write.md")
    # 独立审查的任务已经不是一份独立作业书了，它是 spec overlay 里的一条判据。
    # 旧文件没了就返回「未启用」是静默放过——判据要跟着对象走。
    overlay = _ext_file(root, "rules/spec-rules.overlay.yaml")
    if overlay is None:
        overlay = DEFAULT_EXTENSION_DIR / "rules" / "spec-rules.overlay.yaml"
    verify_doc = overlay if overlay.is_file() else None
    if write_doc is None or verify_doc is None:
        return Outcome(True, "作业书不全（该形态未启用）")
    dimensions = _self_check_dimensions(read_text(write_doc))
    if not dimensions:
        return Outcome(False, "writer 作业书里派生不出自检维度——不是「没有维度」，是解析坏了")
    verify_text = read_text(verify_doc)
    leaked = [d for d in dimensions if d in verify_text]
    if leaked:
        return Outcome(False, "裁决者作业书里出现了整篇维度：" + "、".join(leaked))
    return Outcome(True, f"逐对裁决任务良定（writer 自检 {len(dimensions)} 维，未泄漏到裁决者）")


def _find_phase_doc(root: Path, name: str) -> Path | None:
    hits = sorted(root.rglob(f"phases/{name}"))
    return hits[0] if hits else None


def _self_check_dimensions(text: str) -> list[str]:
    """从 writer 作业书的自检节取维度名：`**一、独立可读。**` → `独立可读`。"""
    out = []
    for line in split_lines(text):
        m = re.match(r"^\*\*[一二三四五六七八九十]+、(.+?)。?\*\*", line.strip())
        if m:
            out.append(m.group(1).strip())
    return out


@checker
def f01_spec_without_story(root: Path, ctx: Ctx) -> Outcome:
    """spec 四阶段全绿，叙事件却从来没被写出来。

    story 是 spec 阶段三份产物之一（spec.md / review.md / story.md）。曾经把它挪到
    spec 之后当独立一步，触发条件写「归档之前」——本地单没有归档，这个时点不存在，
    于是没有任何阶段边界要求它。实测：四阶段 harness 全 pass、`AR/story.md` 不存在。

    判据查**登记态**不查文件在不在：手写一份简版照样能骗过「文件存在」
    （基线就这么判，注释里自己承认过）。`story_flow.py story` 登记前会重跑
    `story-build check`，登记成功即九项判据都过了。
    """
    feature_root = root / "doc" / "features" / "AR90001"
    if not (feature_root / "AR" / "story-flow.json").exists():
        return Outcome(True, "夹具里没有流程契约（该形态未启用）")
    problems = _flow_check_call(root, feature_root, "storyProduced")
    if problems is None:
        return Outcome(False, "storyProduced 跑不起来")
    if problems:
        return Outcome(False, f"叙事件未成文被点名：{problems[0][:80]}")
    return Outcome(True, "成文已登记，spec 三份产物齐")


def _flow_check_call(root: Path, feature_root: Path, fn: str) -> list[str] | None:
    """调 flow-check.mjs 的某个导出，回问题串数组；跑不起来回 None。"""
    script = (
        "import {pathToFileURL} from 'node:url';"
        "const m=await import(pathToFileURL(process.argv[1]).href);"
        "console.log(JSON.stringify(m[process.argv[3]](process.argv[2])));")
    check = _ext_file(root, "skills/story/scripts/flow-check.mjs")
    if check is None:
        check = DEFAULT_EXTENSION_DIR / "skills" / "story" / "scripts" / "flow-check.mjs"
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script, "--", str(check), str(feature_root), fn],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    if proc.returncode != 0:
        return None
    return json.loads(proc.stdout or "[]")


@checker
def r04_flow_status_after_s5(root: Path, ctx: Ctx) -> Outcome:
    """spec 的流程契约门禁把 S5 之后的状态判成「未收口」，回头拦住自己的产物。

    契约状态机是 `complete` →（spec）→ `story_written`（S5 登记）→ `archived`。
    门禁问的是「进 spec 之前范围定了没有」，`complete` 之后每个状态都满足这个前提；
    写成「等于 complete」就会在 S5 之后让 spec harness 一重跑就 FAIL，
    `upstream_verdict_gate` 再把 coding、review 一并判 FAIL——四个已闭环的阶段集体翻红。
    """
    feature_root = root / "doc" / "features" / "AR90001"
    if not (feature_root / "AR" / "story-flow.json").exists():
        return Outcome(True, "夹具里没有流程契约（该形态未启用）")
    script = (
        "import {pathToFileURL} from 'node:url';"
        "const m=await import(pathToFileURL(process.argv[1]).href);"
        "console.log(JSON.stringify(m.flowProblems(process.argv[2])));")
    check = _ext_file(root, "skills/story/scripts/flow-check.mjs")
    if check is None:
        check = DEFAULT_EXTENSION_DIR / "skills" / "story" / "scripts" / "flow-check.mjs"
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script, "--", str(check), str(feature_root)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    if proc.returncode != 0:
        return Outcome(False, f"flowProblems 跑不起来：{(proc.stderr or '')[-200:]}")
    problems = json.loads(proc.stdout or "[]")
    unclosed = [p for p in problems if "未收口" in p]
    if unclosed:
        return Outcome(False, f"契约被判未收口：{unclosed[0][:120]}")
    return Outcome(True, f"收口判定正确（其余 {len(problems)} 条与本形态无关）")

def adjudication_keys(spec_text: str) -> list[str]:
    """必答集的核对键 —— 与扩展侧 ``verdict-set.mjs`` 的 ``specSet`` 同口径。

    **数据源是 spec §10「规约约束要求」表本身**。上一版两边都读
    ``AR/story-src/knowledge.json``，那是同一批结论的第二份写法——两处判定对不上时，
    评审者无从知道哪个是准的，所以那份登记件退场了。

    两边各自实现（一边给 verifier 注入清单、一边在测试域核对目标产物），口径靠
    ``test_adjudication_parity.py`` 绑定：改了一边不改另一边，那个测试会红。
    """
    lines = split_lines(spec_text)
    start = next(
        (i for i, l in enumerate(lines) if re.match(r"^#{2,4}\s+.*规约约束要求", l.strip())),
        -1,
    )
    if start < 0:
        return []
    level = len(re.match(r"^(#{2,4})", lines[start].strip()).group(1))
    keys: list[str] = []
    headers_seen = False
    for line in lines[start + 1:]:
        h = re.match(r"^(#{2,4})\s+", line.strip())
        if h and len(h.group(1)) <= level:
            break
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if all(re.fullmatch(r"[-: ]*", c) for c in cells):
            continue
        if not headers_seen:
            headers_seen = True
            continue
        rid = cells[0].replace("`", "").replace("*", "").strip() if cells else ""
        if _ENTRY_ID_RE.match(rid):
            keys.append(rid)
    seen: set[str] = set()
    return [k for k in keys if not (k in seen or seen.add(k))]


def _registry(root: Path) -> dict | None:
    """判定登记件（归档件的知识判定源）。"""
    path = root / "AR" / "story-src" / "knowledge.json"
    if not path.exists():
        return None
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"knowledge.json 解析失败：{exc}") from exc
    return data if isinstance(data, dict) else None


def _norm(text: str) -> str:
    """同文比对的规范化：只去空白与强调符，不做同义归并。"""
    return re.sub(r"[\s`*　]", "", str(text or ""))


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


#: 发现者不是脚本时它是谁。缺省 script —— 不写这个字段的形态照旧跑 checker。
#:
#: - ``verifier`` / ``behavior_test``：判据挪给另一个执行体；
#: - ``observed``：不挪给谁，就在真实运行的结果里看。这一档必须写 ``observed_by``——
#:   不写清「谁在什么时候看什么」，「由真实结果兜底」就只是一句话。
DELEGATES = ("observed", "verifier", "behavior_test")


def delegated_to(mode: dict) -> str:
    """这一条的发现者是不是已经换人了。

    换人要有人签字（reason + approved_by）：把一条形态从脚本手里拿走，等于承认
    「机械发现者缺席、由别的东西兜底」，那是需要有人负责的决定，不是改个字段。
    """
    who = str(mode.get("responsibility", "")).strip()
    return who if who in DELEGATES else ""


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
    """反夹具必 FAIL、正夹具必 PASS。

    ``self_check: internal`` 的形态例外：它的正反例内建在 checker 的数据里
    （每条样本各带预期），外部 bad/good 目录对它没有意义——那种形态跑一次 checker
    本身，checker 内部逐条比对预期并把偏离项报出来。
    """
    if str(mode.get("self_check", "")).strip() == "internal":
        outcome = run_checker(mode["checker"], DEFAULT_EXTENSION_DIR, Ctx(
            knowledge_root=DEFAULT_EXTENSION_DIR / "knowledge",
            extension_root=DEFAULT_EXTENSION_DIR,
        ))
        report.add(ModeResult(
            mode["id"], "self_check", "internal（逐分支预期）",
            "PASS" if outcome.ok else "FAIL", outcome.evidence,
        ))
        return
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
        who = delegated_to(mode)
        if who:
            missing = [k for k in ("reason", "approved_by") if not mode.get(k)]
            if who == "observed" and not mode.get("observed_by"):
                missing.append("observed_by")
            if missing:
                report.add(ModeResult(mode["id"], "ledger", "-", "FAIL",
                                      f"责任委派缺 {'/'.join(missing)}——换发现者要有人签字，"
                                      "observed 还要写清真实运行里谁看什么"))
            else:
                report.add(ModeResult(mode["id"], "delegated", who, "SKIP", mode["reason"]))
            continue
        self_check(mode, report)

    if not args.self_check:
        for mode in modes:
            if delegated_to(mode):
                continue
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
    delegated = {mid for mid, rs in by_mode.items()
                 if mid not in failed and any(r.stage == "delegated" for r in rs)}
    skipped_only = {
        mid for mid, rs in by_mode.items()
        if mid not in failed and mid not in delegated and all(r.status == "SKIP" for r in rs)
    }
    print("\n" + "=" * 78)
    print(
        f"形态 {total} 条：FAIL {len(failed)}，SKIP(能力未建) {len(skipped_only)}，"
        f"委派 {len(delegated)}，PASS {total - len(failed) - len(skipped_only) - len(delegated)}"
    )
    if delegated:
        print("责任已委派（发现者不是脚本）：" + "、".join(sorted(delegated)))
    if failed:
        print("失败形态：" + "、".join(sorted(failed)))
    print("=" * 78)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
