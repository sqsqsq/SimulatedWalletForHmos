"""把来源收件箱 `sources/inbox/` 里的原件导成材料版本：原件、转换正文与图一起按版本留住。

正式命令是 `core/import_sources.py`，本模块只做实现。

一份原件是一个**来源**（source）。系统取材的件按回执认来源（角色 + 单号），本地放进来的件按它在收件箱里的相对路径认；
同一来源每次取得的内容不同就是一个新**版本**，落在 `sources/<标签>-v<N>/`：

    <原文件名>           原件字节，文件名不改（叫 spec.md 也只在版本目录里，不会被当成施工产物）
    text.md              阅读稿：原件是 docx 时的转换正文，图链接指本版本的 images/；原件是带本地引用的 Markdown 时
                         是它的阅读投影，引用按导入前的位置解析、改指导入后的真实位置（原件字节不动）
    images/<名>          原件是 docx 时的内嵌图
    .version.json        这一版的身份：来源、类、取得时刻、原件/阅读稿/图的完整摘要（点文件是控制件）

Markdown 引用的图与文件各按自己的来源导成版本；引用的本地文件不在这一批也没导入过时整批不导，报出缺哪些。

版本一经写下不再改：转换器升级或原件换了内容，都是新版本；旧版本留着，已经引用它的设计与审查仍指得回同一批字节。
同一来源这一次的内容与最新版本相同就复用，不新开版本。导入成功的原件移出收件箱，收件箱只剩还没导入的件。

归类由 AI 写进 `sources/inbox/.classify.json`（`{"<相对收件箱的路径>": "<类>"}`，值域见 `CLASSES`）；
系统取材批次（`sources/inbox/<批次>/`，带 `.receipt.json` 回执）里回执列着的件按回执的角色归类，不用另写。
没归类的件不会被默默忽略——那等于人以为导了、实际没导。

输入与格式的失败（读不开、没归类、链接越界、转换缺口）都在写盘之前一次报全，一个字节不动；
每个新版本先写在 `sources/.staging/` 下再改名落位，中途失败不留半个版本，报出已落位的版本与没动的原件。
材料现在是什么由 `materials/registry.py` 的索引按磁盘现状回答。

只用标准库：docx 是 zip + OOXML，图片抽取本就要走 `zipfile` + XML。
"""
from __future__ import annotations

import json
import os
import posixpath
import re
import shutil
import sys
import time
import uuid
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import quote, unquote
from pathlib import Path, PurePosixPath

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"

DOC_EXT = ".docx"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
# 收件箱里不算材料的文件：目录自解释用的说明书（每一层都不收）
SKIP_NAMES = {"readme.md"}
# AI 写、脚本读的归类件；与它一样的点文件都是控制件，不是材料
CLASSIFY_FILE = ".classify.json"
#: 系统取材批次的回执：对接层逐件写角色、单号与取得状态
RECEIPT_FILE = ".receipt.json"

#: 来源的类：RR 产品需求、SR 系统设计、AR 开发需求、UX 界面材料、IMAGES 只取图的参考稿、MEETING 会议材料。
#: `IMAGES` 是「只抽图、正文不采用」：系统上已有同类正文、这份是原稿或参考稿时走它，正文不作阅读稿。
#: `MEETING` 按会议版本留存（`materials/meeting.py`），读会由模型理解。
CLASSES = ("RR", "SR", "AR", "UX", "IMAGES", "MEETING")
#: 回执里的角色就是类
SYSTEM_ROLES = ("RR", "SR", "AR")

SOURCES = "sources"
INBOX = (SOURCES, "inbox")
STAGING = (SOURCES, ".staging")
VERSION_FILE = ".version.json"
TEXT_FILE, IMAGES_DIR = "text.md", "images"
READING_FILE = "text.reading.md"     # Markdown 原件自己叫 text.md 时，它的阅读投影改用这个名
VERSION_SCHEMA = 1


class ImportError_(Exception):
    """可预期的导入失败：带可执行的补救动作，直接呈给人。"""


def log(msg: str) -> None:
    print(f"[import_sources] {msg}", file=sys.stderr)


def digest(data: bytes) -> str:
    """来源身份用完整 SHA-256（原生来源协议也用它）；给人看时由读者截短。"""
    return sha256(data).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


#: 默认工程根。本扩展装在 `<工程>/doc/extensions/` 下，脚本自己的位置就定死了它。
#: 两个正式入口（import_sources、story_flow）都在这里取，算一次后逐层传下去——
#: 各自数一遍目录层数的话，文件往下挪一层就会有一处漏改。
DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[7]


def _config_paths(project_root: Path) -> dict:
    """工程 framework.config.json 的 paths；没有这份配置是空表，坏 JSON 报出来。"""
    path = project_root / "framework.config.json"
    if not path.is_file():
        return {}
    try:
        cfg = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise ImportError_(f"{path} 不是合法 JSON（{exc}）：需求目录与阶段报告目录登记在它的 paths 里") from exc
    return cfg.get("paths") or {}


def features_dir(project_root: Path) -> str:
    """需求目录叫什么，由工程自己的 framework.config.json 说了算；没有这份配置用默认目录。"""
    value = _config_paths(project_root).get("features_dir")
    return value.strip() if isinstance(value, str) and value.strip() else "doc/features"


def project_root_of(feature_root: Path) -> Path:
    """需求目录所在的工程根：向上第一个有 framework.config.json 的目录；没有配置按默认需求目录（doc/features/<名>）回推。"""
    return next((p for p in feature_root.parents if (p / "framework.config.json").is_file()), feature_root.parents[2])


def inbox_of(feature_root: Path) -> Path:
    return feature_root.joinpath(*INBOX)


# ---------------------------------------------------------------------------
# 扫描与归类（零依赖层）

def source_key(inbox: Path, path: Path) -> str:
    """收件箱里一份件的键：相对收件箱的 POSIX 路径。归类、待导入与清单都用它，只在这里算。"""
    return path.relative_to(inbox).as_posix()


def check_inbox_root(inbox: Path) -> None:
    """收件箱根本身得是需求目录下的实目录：根是链接或目录联接，等于把别处的文件当成本需求的原件。"""
    if inbox.is_symlink() or inbox.is_junction() or inbox.resolve() != inbox.parent.resolve() / inbox.name:
        raise ImportError_("来源收件箱 sources/inbox 本身是链接或目录联接、指到了需求目录之外："
                           "收件箱只认需求目录下的实目录，把原件放进实目录再导；没有移动或写入任何文件")


def scan_sources(inbox: Path) -> list[Path]:
    """递归收件：任意深度的普通文件，按相对路径排序。

    每一层的点目录与点文件是控制件、README 是说明书，都不收；空目录没有条目。
    链接（含目录联接）不跟随：跟过去就可能读到收件箱之外的东西，而登记的路径还写在收件箱里。
    """
    if not inbox.is_dir():
        return []
    check_inbox_root(inbox)
    root = inbox.resolve()
    found: list[Path] = []

    def walk(directory: Path) -> None:
        for path in sorted(directory.iterdir()):
            if path.name.startswith("."):
                continue
            if path.is_symlink() or path.is_junction() or not path.resolve().is_relative_to(root):
                raise ImportError_(f"「{source_key(inbox, path)}」是链接或指到收件箱之外："
                                   "收件箱只收普通文件与目录，把实际文件放进来再导")
            if path.is_dir():
                walk(path)
            elif path.is_file() and path.name.lower() not in SKIP_NAMES:
                found.append(path)

    walk(inbox)
    return sorted(found, key=lambda p: source_key(inbox, p))


def read_classify(inbox: Path) -> dict[str, str]:
    """读 AI 写下的归类件。没有 = 没归类（有料却没归类由 validate 显式报错）。"""
    path = inbox / CLASSIFY_FILE
    if not path.is_file():
        return {}
    # utf-8-sig：写它的可能是任何宿主，PowerShell 的 UTF8 会带 BOM，多一个字节不该是失败
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise ImportError_(f"sources/inbox/{CLASSIFY_FILE} 不是合法 JSON：{exc}") from exc
    if not isinstance(data, dict):
        raise ImportError_(f"sources/inbox/{CLASSIFY_FILE} 应是 {{\"<相对收件箱的路径>\": \"{'|'.join(CLASSES)}\"}} 对象")
    # 一份原件只有一种键：绝对路径、`..`、`.`、反斜杠或多余的斜杠会让同一个文件有两个键，或指到收件箱之外
    bad = [k for k in data if not k or k != PurePosixPath(k).as_posix() or "\\" in k
           or PurePosixPath(k).is_absolute() or {".", ".."} & set(PurePosixPath(k).parts)]
    if bad:
        raise ImportError_(f"sources/inbox/{CLASSIFY_FILE} 的键 {'、'.join(map(repr, bad))} 不是规范的相对路径："
                           "键写相对收件箱的路径，用 `/` 分隔，不带 `./`、`..`、盘符或多余的斜杠")
    return data


def read_receipts(inbox: Path) -> dict[str, dict]:
    """系统取材批次回执里列着的件：`{相对收件箱的路径: 回执条目（含批次头）}`。

    回执由对接层写，逐件给角色、单号与取得状态；只认 `fetched` 且角色是 RR/SR/AR 的条目。
    回执写坏了报出来——当成没有回执，系统件就会被当成没归类的本地件。
    """
    out: dict[str, dict] = {}
    if not inbox.is_dir():
        return out
    for path in sorted(inbox.rglob(RECEIPT_FILE)):
        rel_dir = path.parent.relative_to(inbox).as_posix()
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except ValueError as exc:
            raise ImportError_(f"sources/inbox/{rel_dir}/{RECEIPT_FILE} 不是合法 JSON（{exc}）：它由取材命令写，重新取材") from exc
        head = {k: data.get(k) for k in ("reqNo", "parentNo", "rrNo", "fetchedAt")} if isinstance(data, dict) else {}
        for item in (data.get("items") if isinstance(data, dict) else None) or []:
            if not (isinstance(item, dict) and item.get("status") == "fetched" and item.get("role") in SYSTEM_ROLES
                    and item.get("ticket") and item.get("name")):
                continue
            key = f"{rel_dir}/{item['name']}" if rel_dir != "." else str(item["name"])
            out[key] = {**item, "batch": rel_dir, **head}
    return out


def is_text(path: Path) -> bool:
    """能不能当文本读——问文件本身，不问扩展名：严格 utf-8 解得开就是文本。"""
    try:
        path.read_text(encoding="utf-8")
        return True
    except (UnicodeDecodeError, OSError):
        return False


def class_of(key: str, classify: dict[str, str], receipts: dict[str, dict]) -> str | None:
    """一份件的类：系统回执列着的按角色，其余按归类件。"""
    if key in receipts:
        return receipts[key]["role"]
    return classify.get(key) if classify.get(key) in CLASSES else None


def validate(inbox: Path, sources: list[Path], classify: dict[str, str], receipts: dict[str, dict]) -> None:
    """先验后写：问题一次列全，任何一项不合格就整批不动，不存在半改状态。"""
    problems: list[str] = []
    keys = {source_key(inbox, p) for p in sources}
    for path in sources:
        ext = path.suffix.lower()
        key = source_key(inbox, path)
        if ext != DOC_EXT and ext not in IMAGE_EXTS and not is_text(path):
            problems.append(
                f"「{key}」读不开：本脚本能物化的是文本、{DOC_EXT} 与图片"
                f"（{'、'.join(sorted(IMAGE_EXTS))}）。"
                "若你能读懂它的内容，请自行转写成 .md 放回收件箱再归类；"
                "若你也读不了，请让用户提供可读版本")
        if key in receipts:
            continue
        if key not in classify:
            problems.append(
                f"「{key}」未给出归类：请在 sources/inbox/{CLASSIFY_FILE} 以相对收件箱的路径为键，"
                f"指明它属 {' / '.join(CLASSES)} 中的哪一类")
        elif classify[key] not in CLASSES:
            problems.append(f"「{key}」的归类「{classify[key]}」非法，须为 {'/'.join(CLASSES)}")
        elif classify[key] == "MEETING" and ext != DOC_EXT:
            problems.append(f"「{key}」归类为 MEETING，但会议材料只收原始 {DOC_EXT}"
                            "：原件要按版本留住，引用才指得回同一段原文")
        elif ext in IMAGE_EXTS and classify[key] != "UX":
            problems.append(f"「{key}」是图片但归类为 {classify[key]}：图片只能归 UX（界面设计）")
    for key in sorted(set(classify) - keys):
        problems.append(f"sources/inbox/{CLASSIFY_FILE} 的键「{key}」没有对应的原件：移走或改名的原件把它的归类键一并删掉或改掉")
    if problems:
        raise ImportError_("\n".join(problems))


# ---------------------------------------------------------------------------
# 抽图（zipfile 层）

def read_media(zf: zipfile.ZipFile) -> tuple[dict[str, str], dict[str, bytes]]:
    """返回 (rId → 媒体文件名, 媒体文件名 → 字节)。

    `document.xml` 里的图片只给 rId，真实文件名在 rels 里——两张表拼起来才能定位。
    """
    rel_map: dict[str, str] = {}
    try:
        rels = ET.fromstring(zf.read("word/_rels/document.xml.rels"))
    except KeyError:
        return {}, {}
    for rel in rels.findall(f"{REL_NS}Relationship"):
        target = rel.get("Target", "")
        if "media/" in target:
            rel_map[rel.get("Id", "")] = target.split("/")[-1]

    blobs = {name.split("/")[-1]: zf.read(name)
             for name in zf.namelist() if name.startswith("word/media/")}
    return rel_map, blobs


# ---------------------------------------------------------------------------
# docx → markdown（xml.etree 层）
#
# 转换只搬形态：段落、标题、表格、软换行、制表符、超链接与图片按文档顺序搬成
# Markdown。**不认语义单元**——谁在发言、哪一段是议题、哪一列是时间，由读它的模型判断。
#
# 包装型结构（内容控件、修订插入、智能标记）只是外壳，展开即可；没有正文的标记
# （分节属性、书签、批注范围、被删除或移走的内容）跳过。两类都不是、里面却有文字或图的
# 结构一律报出来：静默丢掉的话，下游拿到的是一份看上去完整的残稿。

V = "{urn:schemas-microsoft-com:vml}"

#: 展开子节点即可的包装（块级与行内共用）
UNWRAP = {f"{W}ins", f"{W}moveTo", f"{W}smartTag", f"{W}customXml", f"{W}fldSimple",
          f"{W}hyperlink", f"{W}bdo", f"{W}dir", f"{W}sdtContent"}
#: 正文挂在 w:sdtContent 上的包装：外层还带着属性节点
SDT = f"{W}sdt"
#: 没有正文的标记：跳过，不算转换缺口
SKIP_TAGS = {f"{W}pPr", f"{W}rPr", f"{W}sectPr", f"{W}tblPr", f"{W}tblGrid", f"{W}trPr",
             f"{W}tcPr", f"{W}sdtPr", f"{W}sdtEndPr", f"{W}bookmarkStart", f"{W}bookmarkEnd",
             f"{W}commentRangeStart", f"{W}commentRangeEnd", f"{W}permStart", f"{W}permEnd",
             f"{W}del", f"{W}moveFrom", f"{W}moveFromRangeStart", f"{W}moveFromRangeEnd",
             f"{W}moveToRangeStart", f"{W}moveToRangeEnd"}
#: 带正文的节点：认不出的结构里有它们才算缺口
CONTENT_TAGS = (f"{W}t", f"{W}drawing", f"{W}pict", f"{W}object")


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def _has_content(node: ET.Element) -> bool:
    """这个结构里还有没有文字或图——认不出它时，据此决定是跳过还是报缺口。"""
    return any(n.tag in CONTENT_TAGS for n in node.iter())


def _heading_level(para: ET.Element, style_names: dict[str, str]) -> int:
    """标题级别：pStyle 名 → styles.xml 反查 → outlineLvl，三者都不中当普通段落。

    中文版 Word 的 pStyle 常是 `2`、`a3` 这类非语义 ID，所以不能只认名字。
    """
    ppr = para.find(f"{W}pPr")
    if ppr is None:
        return 0
    style = ppr.find(f"{W}pStyle")
    if style is not None:
        val = style.get(f"{W}val", "")
        for candidate in (val, style_names.get(val, "")):
            m = re.match(r"^(?:Heading|heading|标题)\s*([1-6])$", candidate.strip())
            if m:
                return int(m.group(1))
    outline = ppr.find(f"{W}outlineLvl")
    if outline is not None:
        try:
            return min(int(outline.get(f"{W}val", "0")) + 1, 6)
        except ValueError:
            pass
    return 0


def _images_in(node: ET.Element, rel_map: dict[str, str], asset_ref: str) -> list[str]:
    """一处图形里引用到的图片：新式 DrawingML 与旧式 VML 都认。"""
    names = [rel_map.get(blip.get(f"{R}embed", "")) for blip in node.iter(f"{A}blip")]
    names += [rel_map.get(data.get(f"{R}id", "")) for data in node.iter(f"{V}imagedata")]
    return [f"![{name}]({md_target(f'{asset_ref}/{name}')})" for name in names if name]


def md_target(path: str) -> str:
    """路径写成合法的 Markdown 链接目标：`%`、`#`、`?` 与尖括号编码（读者把未编码的 `#`、`?` 当片段与查询），
    含空白或括号时包进 `<…>`——派生目录随原件主名，名字不改。"""
    s = re.sub(r"[%#?<>]", lambda m: f"%{ord(m.group()):02X}", path)
    return f"<{s}>" if re.search(r"[\s()]", s) else s


def _run_text(run: ET.Element, rel_map: dict[str, str], asset_ref: str) -> str:
    """一个 run 的文本：软换行与制表符按原位保留，图片就地插入。

    软换行在 Word 里是 `w:br`，它把一段分成几行——记录类文档常用它分开抬头与正文。
    只读 `w:t` 会把两行粘成一行，而行是引用的定位单位。
    """
    pieces: list[str] = []
    for node in run:
        tag = node.tag
        if tag == f"{W}t":
            pieces.append(node.text or "")
        elif tag in (f"{W}br", f"{W}cr"):
            pieces.append("\n")
        elif tag == f"{W}tab":
            pieces.append("\t")
        elif tag == f"{W}noBreakHyphen":
            pieces.append("-")
        elif tag in (f"{W}drawing", f"{W}pict", f"{W}object"):
            pieces.extend(_images_in(node, rel_map, asset_ref))
    text = "".join(pieces)
    rpr = run.find(f"{W}rPr")
    # 跨行的强调标记会把 Markdown 弄坏，这种 run 只保留文字
    if not text.strip() or "\n" in text or rpr is None:
        return text
    if rpr.find(f"{W}b") is not None:
        text = f"**{text}**"
    if rpr.find(f"{W}i") is not None:
        text = f"*{text}*"
    return text


def _para_markdown(para: ET.Element, style_names: dict[str, str],
                   rel_map: dict[str, str], asset_ref: str, gaps: set[str]) -> str:
    text = "".join(_run_text(r, rel_map, asset_ref)
                   for r in _walk(para, {f"{W}r"}, gaps)).strip()
    if not text:
        return ""

    level = _heading_level(para, style_names)
    if level:
        return f"{'#' * level} " + " ".join(t for t in text.split("\n") if t.strip())

    ppr = para.find(f"{W}pPr")
    if ppr is not None and ppr.find(f"{W}numPr") is not None:
        ilvl = ppr.find(f"{W}numPr/{W}ilvl")
        depth = int(ilvl.get(f"{W}val", "0")) if ilvl is not None else 0
        return f"{'  ' * depth}- {text}"
    return text


def _walk(node: ET.Element, want: set[str], gaps: set[str]):
    """按文档顺序取某一层想要的节点：段落与表格、表格的行与格、段落里的 run 都走它。

    包装（内容控件、超链接、修订插入）展开继续找；没有正文的标记跳过；
    认不出而里面有文字或图的结构记成缺口——静默丢内容比报错难查得多。
    """
    for child in node:
        tag = child.tag
        if tag in want:
            yield child
        elif tag == SDT:
            content = child.find(f"{W}sdtContent")
            if content is not None:
                yield from _walk(content, want, gaps)
        elif tag in UNWRAP:
            yield from _walk(child, want, gaps)
        elif tag in SKIP_TAGS or not _has_content(child):
            continue
        else:
            gaps.add(_local(tag))


def _cell_markdown(tc: ET.Element, style_names: dict[str, str], rel_map: dict[str, str],
                   asset_ref: str, gaps: set[str]) -> str:
    """单元格：多段、软换行与嵌套表格都留住，用 `<br>` 连成一格，竖线转义。

    一行一条记录是表格的读法，所以格内换行不能变成真的换行——那会把一行拆成几行，
    引用的行号也就跟着错位。
    """
    lines = [line for block in _blocks(tc, style_names, rel_map, asset_ref, gaps)
             for line in block.split("\n")]
    cleaned = [re.sub(r"^\s*(?:#{1,6}\s+|-\s+)", "", line).replace("|", "\\|").strip()
               for line in lines]
    return "<br>".join(line for line in cleaned if line)


def _table_markdown(tbl: ET.Element, style_names: dict[str, str], rel_map: dict[str, str],
                    asset_ref: str, gaps: set[str]) -> str:
    rows = [[_cell_markdown(tc, style_names, rel_map, asset_ref, gaps)
             for tc in _walk(tr, {f"{W}tc"}, gaps)]
            for tr in _walk(tbl, {f"{W}tr"}, gaps)]
    rows = [r for r in rows if r]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |",
           "|" + "---|" * width]
    out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(out)


def _blocks(node: ET.Element, style_names: dict[str, str], rel_map: dict[str, str],
            asset_ref: str, gaps: set[str]) -> list[str]:
    """按文档顺序把一层正文转成块：段落一块，表格一块。"""
    out = []
    for node in _walk(node, {f"{W}p", f"{W}tbl"}, gaps):
        md = (_para_markdown(node, style_names, rel_map, asset_ref, gaps)
              if node.tag == f"{W}p"
              else _table_markdown(node, style_names, rel_map, asset_ref, gaps))
        if md:
            out.append(md)
    return out


def docx_to_markdown(path: Path, asset_ref: str) -> tuple[str, dict[str, bytes]]:
    """返回 (markdown, 需落盘的媒体)。媒体只返回文档实际引用到的那些。

    同一份 docx 转多少次都是同一份结果：不带时间戳、不编号、不推断语义。
    """
    try:
        with zipfile.ZipFile(path) as zf:
            body = ET.fromstring(zf.read("word/document.xml")).find(f"{W}body")
            rel_map, blobs = read_media(zf)
            style_names = {}
            try:
                styles = ET.fromstring(zf.read("word/styles.xml"))
                for style in styles.findall(f"{W}style"):
                    name = style.find(f"{W}name")
                    if name is not None:
                        style_names[style.get(f"{W}styleId", "")] = name.get(f"{W}val", "")
            except KeyError:
                pass
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise ImportError_(
            f"「{path.name}」无法解析（{type(exc).__name__}）："
            "请确认是有效的 .docx，或用 Word 重新另存后重放") from exc

    if body is None:
        raise ImportError_(f"「{path.name}」内容为空：Word 文档正文缺失")

    gaps: set[str] = set()
    blocks = _blocks(body, style_names, rel_map, asset_ref, gaps)
    if gaps:
        raise ImportError_(
            f"「{path.name}」里有本转换器不认、而且带着文字或图的结构："
            f"{'、'.join(sorted(gaps))}。这部分内容不会出现在转换结果里，所以整份不导："
            "请在 Word 里把它转成普通段落或表格后重放，或提供同内容的 .md 版本")

    used = {name for rid, name in rel_map.items() if name in blobs}
    return "\n\n".join(blocks), {n: blobs[n] for n in sorted(used)}


# ---------------------------------------------------------------------------
# 预览与图片说明

def preview(path: Path) -> dict:
    """只读预览一份材料：正文文本 + 图清单，**不落盘任何东西**。

    归类是判断，判断要读内容；而 .docx 是压缩包，不解开就读不了。预览与导入用**同一个解析器**：
    预览看到的正文，就是导入会写进去的正文。
    """
    if not path.is_file():
        raise ImportError_(f"「{path}」不存在")
    if is_text(path):
        return {"file": path.name, "kind": "text",
                "text": path.read_text(encoding="utf-8", errors="replace"), "images": []}
    markdown, blobs = docx_to_markdown(path, ".")
    return {"file": path.name, "kind": "docx", "text": markdown,
            "images": sorted(blobs.keys())}


def _no_such_image(target: Path) -> str:
    """读不到的时候，把正确的写法一起给出来——只说「读不到」等于让人去翻脚本。"""
    return (f"读不到 {target}——路径相对工程根，"
            "例如 `doc/features/<需求名>/sources/<材料版本>/images/<文件名>`；"
            "绝对路径也认。导入那次打印出来的路径可以直接复制")


def resolve_image_arg(project_root: Path, raw: str) -> Path:
    """图片参数落到哪个文件——**相对工程根**，或者绝对路径。只认一种基准：两处恰好同名时回落会取到另一张图。"""
    path = Path(raw)
    return path if path.is_absolute() else project_root / path


def _image_sha(feature_root: Path, target: Path) -> str:
    """说明与取舍写在哪张图上：图的身份是内容。只收材料版本里的图——别处的图不是本需求的材料。"""
    if not target.is_file():
        raise ImportError_(_no_such_image(target))
    if target.suffix.lower() not in IMAGE_EXTS:
        raise ImportError_(f"{target.name} 不是图片（认这些后缀：{'、'.join(sorted(IMAGE_EXTS))}）")
    sources_root = (feature_root / SOURCES).resolve()
    if not target.resolve().is_relative_to(sources_root) or target.resolve().is_relative_to(inbox_of(feature_root).resolve()):
        raise ImportError_(f"{target.name} 不在已导入的材料版本里：先导入它所在的原件，再给导入后的那张图写说明")
    return digest(target.read_bytes())


def _note(feature_root: Path, target: Path, field: str, value: str | None) -> dict:
    from materials import registry  # 延迟导入：registry 引用本模块，顶层互相 import 会成环
    sha = _image_sha(feature_root, target)
    registry.write_note(feature_root, sha, field, value)
    manifest = registry.refresh(feature_root)
    return {"sha256": sha, "digest": manifest.get("digest")}


def caption_image(feature_root: Path, target: Path, caption: str) -> dict:
    """给材料里的一张图写下「它是什么」。**不复制、不改名、不动文件**；说明跟着图的内容走，记在索引里。"""
    if not caption.strip():
        raise ImportError_("缺 --caption：一句「这张图是什么」")
    return {**_note(feature_root, target, "caption", caption.strip()), "caption": caption.strip()}


def mark_unused(feature_root: Path, target: Path, reason: str) -> dict:
    """登记本需求为什么不用这张图：成文输入与读者审查逐张读得到。"""
    if not reason.strip():
        raise ImportError_("缺 --unused 的理由：一句「本需求为什么不用它」")
    return {**_note(feature_root, target, "unused", reason.strip()), "unused": reason.strip()}


def mark_used(feature_root: Path, target: Path) -> dict:
    """这张图要用了——撤掉「不用」的理由，说明留着。"""
    return {**_note(feature_root, target, "unused", None), "unused": ""}


# ---------------------------------------------------------------------------
# 导入：原件 → 材料版本

def safe_label(text: str) -> str:
    """材料版本目录的可读标签：去掉路径与 shell 敏感字符，空白连成 `-`；不以点开头。"""
    label = re.sub(r"[\\/:*?\"<>|\s]+", "-", str(text)).strip(".-")[:60].strip(".-")
    return label or "材料"


def identify(inbox: Path, path: Path, cls: str, receipts: dict[str, dict]) -> dict:
    """这份件属于哪个来源：系统件按回执的角色与单号，本地件按它在收件箱里的相对路径。"""
    key = source_key(inbox, path)
    if key in receipts:
        r = receipts[key]
        origin = {"ticket": r["ticket"], "role": r["role"], "title": r.get("title"), "origin": r.get("origin"),
                  "reqNo": r.get("reqNo"), "parentNo": r.get("parentNo"), "rrNo": r.get("rrNo"),
                  "fetched_at": r.get("fetchedAt"), "batch": r.get("batch")}
        return {"source_id": f"system:{r['role']}:{r['ticket']}", "kind": "system", "class": cls,
                "origin": {k: v for k, v in origin.items() if v is not None}, "label": f"{r['role']}-{r['ticket']}"}
    return {"source_id": f"local:{key}", "kind": "local", "class": cls, "origin": {"inbox_path": key},
            "label": PurePosixPath(key).stem}


def convert(path: Path, key: str, cls: str) -> tuple[str | None, dict[str, bytes]]:
    """一份原件这一版的阅读稿与内嵌图（都在内存里）。

    docx 转 Markdown、内嵌图引用指本版本的 `images/`；文本原件本身就是阅读稿，不另造；图片原件没有阅读稿。
    `IMAGES` 只取图：正文不作阅读稿，没有图就报。
    """
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        return None, {}
    if ext == DOC_EXT:
        markdown, blobs = docx_to_markdown(path, IMAGES_DIR)
    else:
        markdown, blobs = None, {}
    if cls == "IMAGES":
        if not blobs:
            raise ImportError_(f"「{key}」归类为 IMAGES（只抽图）但里面没有图——要采用正文的话改归 RR / SR / AR / UX")
        return None, blobs
    return (markdown + "\n" if markdown is not None and not markdown.endswith("\n") else markdown), blobs


#: Markdown 正文里的链接与图片（含 HTML img）：分组保留前后缀，只换目标
MD_EXTS = {".md", ".markdown"}
MD_LINK = re.compile(r'(!?\[[^\]]*\]\(\s*<?)([^)\s>]+)(>?(?:\s+"[^"]*")?\s*\))|(<img\b[^>]*?\bsrc\s*=\s*["\'])([^"\']+)(["\'])', re.I)


def _local_ref(target: str) -> bool:
    """本地相对引用：不是外部地址、不是文内锚点、不是绝对路径。"""
    return bool(target) and not re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) and not target.startswith(("#", "/"))


def project_markdown(text: str, key: str, here: str, targets: dict[str, str]) -> tuple[str | None, list[str]]:
    """Markdown 原件按导入前的位置解析本地引用，换成指向导入后真实位置的阅读投影。

    `key` 是它在收件箱里的位置，`here` 是阅读投影所在目录（相对需求目录），`targets` 是收件箱位置 → 导入后位置
    （本批导入的与已登记的）。返回 (阅读投影, 找不到的引用)；没有本地引用为 (None, [])，原件自己就是阅读稿。
    """
    missing: list[str] = []
    changed = False

    def swap(m: re.Match) -> str:
        nonlocal changed
        head, target, tail = (m.group(1), m.group(2), m.group(3)) if m.group(1) else (m.group(4), m.group(5), m.group(6))
        if not _local_ref(target):
            return m.group(0)
        path, _, fragment = target.partition("#")
        where = posixpath.normpath(posixpath.join(posixpath.dirname(key), unquote(path)))
        final = targets.get(where)
        if final is None:
            missing.append(target)
            return m.group(0)
        changed = True
        new = posixpath.relpath(final, here) + (f"#{fragment}" if fragment else "")
        return f"{head}{quote(new, safe='/#.-_~')}{tail}"

    projected = MD_LINK.sub(swap, text)
    return (projected if changed else None), missing


def _same(record: dict, original: str, readable: str | None, images: dict[str, str]) -> bool:
    """这一次的内容与已有版本是不是同一份：原件、阅读稿与内嵌图都相同。"""
    have_readable = (record.get("readable") or {}).get("sha256")
    if record.get("original", {}).get("sha256") != original:
        return False
    if readable is not None and have_readable != readable:
        return False
    if readable is None and record.get("readable") and record["readable"].get("path") != record["original"].get("path"):
        return False
    return {PurePosixPath(i["path"]).name: i["sha256"] for i in record.get("images") or []} == images


def cmd_import(feature_root: Path, project_root: Path) -> dict:
    """把收件箱里这一批件导成材料版本，导入成功的原件移出收件箱。

    输入与格式的问题在写盘前一次报全，盘上一个字节不动：转换全部在内存里做完才开始写。
    每个新版本先写进 `sources/.staging/`，写全了再改名落位；中途失败如实报出已落位的版本与还在收件箱的原件。
    """
    from materials import meeting, registry  # 延迟导入：两者都引用本模块

    # 旧版生成的需求：写任何版本之前就拒绝，目录原样保留
    try:
        registry.read_notes(feature_root)
    except registry.MaterialError as exc:
        raise ImportError_(str(exc)) from exc
    inbox = inbox_of(feature_root)
    classify = read_classify(inbox)
    receipts = read_receipts(inbox)
    sources = scan_sources(inbox)
    validate(inbox, sources, classify, receipts)

    # 已留存的会议版本：转换文本缺了或被改过就按同目录原件补回来；补不成原样的明说，不重编号——引用记的是行号
    for folder in meeting.versions(feature_root).values():
        if meeting.raw_lines(folder)[1]:
            failed = meeting.restore_raw(folder)
            if failed:
                raise ImportError_(failed)

    records = registry.version_records(feature_root)
    latest: dict[str, dict] = {}
    labels: dict[str, str] = {}
    for rec in records:
        if rec["version"] > latest.get(rec["source_id"], {}).get("version", 0):
            latest[rec["source_id"]] = rec
        labels.setdefault(rec["source_id"], re.sub(r"-v\d+$", "", PurePosixPath(rec["dir"]).name))
    # 收件箱位置 → 已登记的最新原件位置：Markdown 引用的本地文件可能早已导入
    targets = {rec["origin"]["inbox_path"]: rec["original"]["path"] for rec in latest.values()
               if (rec.get("origin") or {}).get("inbox_path")}

    # ── 先全部转换到内存，全成功才写盘 ──────────────────────────────
    plan: list[dict] = []
    markdown: list[tuple[Path, str, str]] = []
    for path in sources:
        key = source_key(inbox, path)
        cls = class_of(key, classify, receipts)
        if cls not in ("MEETING", "IMAGES") and path.suffix.lower() in MD_EXTS:
            markdown.append((path, key, cls))       # 第二遍：等本批其余件的位置定了再出阅读投影
            continue
        if cls == "MEETING":
            plan.append({"key": key, "path": path,
                         "meeting": None if meeting.saved(feature_root, path) else docx_to_markdown(path, meeting.MEDIA)})
            continue
        ident = identify(inbox, path, cls, receipts)
        readable, blobs = convert(path, key, cls)
        original = digest(path.read_bytes())
        readable_sha = digest(readable.encode("utf-8")) if readable is not None else None
        images = {name: digest(blob) for name, blob in blobs.items()}
        have = latest.get(ident["source_id"])
        if have and _same(have, original, readable_sha, images):
            plan.append({"key": key, "path": path, "reuse": have})
            targets[key] = have["original"]["path"]
            continue
        if ident["source_id"] not in labels:
            # 撞名按不区分大小写判：Windows 与 macOS 的盘上 Flow 与 flow 是同一个目录
            base = safe_label(ident["label"])
            taken = {v.casefold() for s, v in labels.items() if s != ident["source_id"]}
            labels[ident["source_id"]] = base if base.casefold() not in taken \
                else f"{base}-{digest(ident['source_id'].encode('utf-8'))[:6]}"
        number = (have or {}).get("version", 0) + 1
        latest[ident["source_id"]] = {"version": number}
        plan.append({"key": key, "path": path, "ident": ident, "readable": readable, "blobs": blobs,
                     "dir": f"{labels[ident['source_id']]}-v{number}", "version": number,
                     "original": original, "readable_sha": readable_sha, "images": images})
        targets[key] = f"{SOURCES}/{plan[-1]['dir']}/{path.name}"
    # Markdown：先按原件字节定每份落在哪（原件没变落回已有版本），文档之间互链也能指到真实位置
    pending: list[tuple[Path, str, dict, dict | None, str, int]] = []
    for path, key, cls in markdown:
        ident = identify(inbox, path, cls, receipts)
        have = latest.get(ident["source_id"])
        if ident["source_id"] not in labels:
            base = safe_label(ident["label"])
            taken = {v.casefold() for s, v in labels.items() if s != ident["source_id"]}
            labels[ident["source_id"]] = base if base.casefold() not in taken \
                else f"{base}-{digest(ident['source_id'].encode('utf-8'))[:6]}"
        original = digest(path.read_bytes())
        number = (have or {}).get("version", 0) + 1
        same = have and have.get("original", {}).get("sha256") == original
        targets[key] = have["original"]["path"] if same else f"{SOURCES}/{labels[ident['source_id']]}-v{number}/{path.name}"
        pending.append((path, key, ident, have, original, number))
    gaps: list[str] = []
    for path, key, ident, have, original, number in pending:
        here = f"{SOURCES}/{labels[ident['source_id']]}-v{number}"
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = ""
        readable, missing = project_markdown(text, key, here, targets)
        gaps += [f"「{key}」引用的 {m}" for m in missing]
        readable_sha = digest(readable.encode("utf-8")) if readable is not None else None
        if have and _same(have, original, readable_sha, {}):
            plan.append({"key": key, "path": path, "reuse": have})
            continue
        latest[ident["source_id"]] = {"version": number}
        plan.append({"key": key, "path": path, "ident": ident, "readable": readable, "blobs": {},
                     "dir": f"{labels[ident['source_id']]}-v{number}", "version": number,
                     "original": original, "readable_sha": readable_sha, "images": {}})
    if gaps:
        raise ImportError_("Markdown 引用的本地文件找不到（不在这次的收件箱里，也没导入过）：" + "；".join(gaps)
                           + "——把引用的图或文件按原来的相对位置一起放进收件箱再导；外部链接与文内锚点不受影响")

    # ── 写盘 ────────────────────────────────────────────────────────
    done: list[str] = []
    out = {"imported": [], "reused": [], "versions": [], "meetings": []}
    try:
        for item in plan:
            if "meeting" in item:
                folder = meeting.version_dir(feature_root, item["path"])
                if item["meeting"] is not None:
                    text, blobs = item["meeting"]
                    folder, _ = meeting.save_version(feature_root, item["path"], text, blobs)
                out["meetings"].append(folder.relative_to(feature_root).as_posix())
            elif "reuse" in item:
                out["reused"].append({"file": item["key"], "version": item["reuse"]["dir"]})
            else:
                _write_version(feature_root, item)
                out["versions"].append(f"{SOURCES}/{item['dir']}")
            item["path"].unlink()
            classify.pop(item["key"], None)
            done.append(item["key"])
            out["imported"].append(item["key"])
    except OSError as exc:
        left = [i["key"] for i in plan if i["key"] not in done]
        raise ImportError_(f"写盘中途失败（{exc}）：已导入并移出收件箱的原件 {'、'.join(done) or '无'}；"
                           f"还在收件箱、没有版本落位的 {'、'.join(left) or '无'}。新版本都先写在 sources/.staging/ 再改名，"
                           "没有半个版本落位；先排除写入故障（权限、占用、磁盘），再重跑导入") from exc
    finally:
        _tidy_inbox(inbox, classify, sources)
        clear_staging(feature_root)
    for item in plan:
        if "ident" in item:
            log(f"{item['key']} → {SOURCES}/{item['dir']}/"
                + ("（转换正文 text.md" + (f"，{len(item['blobs'])} 张图" if item["blobs"] else "") + "）"
                   if item["readable"] is not None and item["path"].suffix.lower() == DOC_EXT
                   else "（阅读稿 text.md，本地引用指向导入后的位置）" if item["readable"] is not None
                   else (f"（{len(item['blobs'])} 张图）" if item["blobs"] else "")))
        elif "reuse" in item:
            log(f"{item['key']} 与 {item['reuse']['dir']}/ 是同一份内容，复用已有版本")
    manifest = registry.refresh(feature_root)
    root = project_root.resolve()
    out["images"] = [f"{shown}" for shown in (_shown(root, feature_root / p) for i in manifest.get("materials", [])
                                               if i.get("kind") == "image" for p in i.get("paths", [])[:1])]
    out["digest"] = manifest.get("digest")
    return out


def _shown(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _write_version(feature_root: Path, item: dict) -> None:
    """写一个新版本：先在暂存目录写全，再改名成最终目录。目标已在就报，不覆盖已有版本。"""
    final = feature_root / SOURCES / item["dir"]
    if final.exists():
        raise OSError(f"{SOURCES}/{item['dir']} 已存在：版本目录不覆盖，查明它从哪来")
    staging = feature_root.joinpath(*STAGING) / uuid.uuid4().hex
    staging.mkdir(parents=True)
    base = f"{SOURCES}/{item['dir']}"
    name = item["path"].name
    shutil.copyfile(item["path"], staging / name)
    original = {"path": f"{base}/{name}", "sha256": item["original"]}
    readable = None
    if item["readable"] is not None:
        text_file = TEXT_FILE if name != TEXT_FILE else READING_FILE
        (staging / text_file).write_text(item["readable"], encoding="utf-8", newline="\n")
        readable = {"path": f"{base}/{text_file}", "sha256": item["readable_sha"]}
    elif item["path"].suffix.lower() not in IMAGE_EXTS and item["ident"]["class"] != "IMAGES":
        readable = dict(original)   # 文本原件本身就是阅读稿
    images = []
    for img, blob in item["blobs"].items():
        (staging / IMAGES_DIR).mkdir(exist_ok=True)
        (staging / IMAGES_DIR / img).write_bytes(blob)
        images.append({"path": f"{base}/{IMAGES_DIR}/{img}", "sha256": item["images"][img]})
    record = {"schema": VERSION_SCHEMA, "source_id": item["ident"]["source_id"], "kind": item["ident"]["kind"],
              "class": item["ident"]["class"], "origin": item["ident"]["origin"], "version": item["version"],
              "acquired_at": now(), "original": original, "readable": readable, "images": images}
    (staging / VERSION_FILE).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8", newline="\n")
    publish_dir(staging, final)


def publish_dir(staging: Path, final: Path) -> None:
    """把写全的暂存目录改名成最终目录。Windows 上刚写完的文件可能被杀毒或索引进程短暂占用，
    改名报拒绝访问时稍等重试几次；仍失败按原错误报出，暂存目录留着不算版本。"""
    for wait in (0.05, 0.1, 0.2, 0.4, 0):
        try:
            os.replace(staging, final)
            return
        except PermissionError:
            if not wait:
                raise
            time.sleep(wait)


def clear_staging(feature_root: Path) -> None:
    """暂存目录只在写一个版本的那一刻有内容；空了就移走，不在来源容器里留控制目录。"""
    staging = feature_root.joinpath(*STAGING)
    if staging.is_dir() and not any(staging.iterdir()):
        staging.rmdir()


def _tidy_inbox(inbox: Path, classify: dict[str, str], scanned: list[Path]) -> None:
    """收尾：归类件只留还在收件箱里的键；导空了的取材批次连回执一起移走（来源关系已记进版本）。"""
    if not inbox.is_dir():
        return
    path = inbox / CLASSIFY_FILE
    if path.is_file():
        path.write_text(json.dumps(classify, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    for receipt in sorted(inbox.rglob(RECEIPT_FILE), reverse=True):
        batch = receipt.parent
        if batch != inbox and not any(p.is_file() and p.name != RECEIPT_FILE for p in batch.rglob("*")):
            shutil.rmtree(batch)
    for directory in sorted({p.parent for p in scanned}, key=lambda p: len(p.parts), reverse=True):
        if directory != inbox and directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
