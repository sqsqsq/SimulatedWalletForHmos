"""把收件箱 `inbox/` 里的原件导成材料版本，并按各类来源的最新版本出当前阅读稿：原件留在收件箱，版本字节另存一份。

正式命令是 `core/import_sources.py`，本模块只做实现。目录沿 1.9.9：

    inbox/                       原件（人放的与系统取材批次 `inbox/<批次>/`），导入后原样留着
    RR/prd.md、SR/design.md      当前阅读稿：同类来源各自最新版本的阅读稿按来源拼成，一份原件一节
    AR/design.md                 系统取得的本单 AR 正文的当前阅读稿；本地补录的 AR 材料落 AR/story-src/upstream.md
    assets/<原件派生名>/         docx 内嵌图；assets/ux/ 是界面图与界面说明（README.md）
    .backups/local/inbox/...     每个版本的原件字节：<原相对目录>/<主名>.<内容摘要><后缀>
    .backups/local/<类>/         每个版本的阅读稿：<标签>-v<N>.md；当前阅读稿每一版的稳定副本：<主名>-聚合-v<N>.md

一份原件是一个**来源**（source）。系统取材的件按回执认来源（角色 + 单号），本地放进来的件按它在收件箱里的相对路径认；
同一来源每次取得的内容不同就是一个新**版本**，登记在材料索引里（`materials/registry.py`，版本关系只登记在那里）。
图按内容身份起名、换了内容另起一个名；留存文件只增不改，已经引用它的设计与审查仍指得回同一批字节。
收件箱里有文件不等于待导入：已并入的原样件留着，重跑不新开版本。

归类由 AI 写进 `inbox/.classify.json`（`{"<相对收件箱的路径>": "<类>"}`，值域见 `CLASSES`）；
系统取材批次（带 `.receipt.json` 回执）里回执列着的件按回执的角色归类，不用另写。
没归类的件不会被默默忽略——那等于人以为导了、实际没导。

输入与格式的失败（读不开、没归类、链接越界、转换缺口）都在写盘之前一次报全，一个字节不动。
直接给在 RR/SR/AR 的原文也是合法来源：第一次见到时登记原字节；之后原文或它引用的图改了算待导入，由导入登记成新版本。

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
from urllib.parse import unquote
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

INBOX = ("inbox",)
#: 版本留存与覆盖前备份都在需求目录的 `.backups/local/`
BACKUP = (".backups", "local")
ASSETS, UX_DIR = "assets", "assets/ux"
#: 可以直接给原文的当前稿 → 类：不经收件箱、直接写在这里的也是合法来源，首次见到时登记
DIRECT = {"RR/prd.md": "RR", "SR/design.md": "SR", "AR/design.md": "AR"}


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
        raise ImportError_("收件箱 inbox 本身是链接或目录联接、指到了需求目录之外："
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
        raise ImportError_(f"inbox/{CLASSIFY_FILE} 不是合法 JSON：{exc}") from exc
    if not isinstance(data, dict):
        raise ImportError_(f"inbox/{CLASSIFY_FILE} 应是 {{\"<相对收件箱的路径>\": \"{'|'.join(CLASSES)}\"}} 对象")
    # 一份原件只有一种键：绝对路径、`..`、`.`、反斜杠或多余的斜杠会让同一个文件有两个键，或指到收件箱之外
    bad = [k for k in data if not k or k != PurePosixPath(k).as_posix() or "\\" in k
           or PurePosixPath(k).is_absolute() or {".", ".."} & set(PurePosixPath(k).parts)]
    if bad:
        raise ImportError_(f"inbox/{CLASSIFY_FILE} 的键 {'、'.join(map(repr, bad))} 不是规范的相对路径："
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
            raise ImportError_(f"inbox/{rel_dir}/{RECEIPT_FILE} 不是合法 JSON（{exc}）：它由取材命令写，重新取材") from exc
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
                f"「{key}」未给出归类：请在 inbox/{CLASSIFY_FILE} 以相对收件箱的路径为键，"
                f"指明它属 {' / '.join(CLASSES)} 中的哪一类")
        elif classify[key] not in CLASSES:
            problems.append(f"「{key}」的归类「{classify[key]}」非法，须为 {'/'.join(CLASSES)}")
        elif classify[key] == "MEETING" and ext != DOC_EXT:
            problems.append(f"「{key}」归类为 MEETING，但会议材料只收原始 {DOC_EXT}"
                            "：原件要按版本留住，引用才指得回同一段原文")
        elif ext in IMAGE_EXTS and classify[key] != "UX":
            problems.append(f"「{key}」是图片但归类为 {classify[key]}：图片只能归 UX（界面设计）")
    for key in sorted(set(classify) - keys):
        problems.append(f"inbox/{CLASSIFY_FILE} 的键「{key}」没有对应的原件：移走或改名的原件把它的归类键一并删掉或改掉")
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
            "例如 `doc/features/<需求名>/assets/<图片目录>/<文件名>`；"
            "绝对路径也认。导入那次打印出来的路径可以直接复制")


def resolve_image_arg(project_root: Path, raw: str) -> Path:
    """图片参数落到哪个文件——**相对工程根**，或者绝对路径。只认一种基准：两处恰好同名时回落会取到另一张图。"""
    path = Path(raw)
    return path if path.is_absolute() else project_root / path


def _image_sha(feature_root: Path, target: Path) -> str:
    """说明与取舍写在哪张图上：图的身份是内容。只收导入后的图（`assets/` 与会议留存里）——收件箱里的原件与别处的图不是登记的材料。"""
    if not target.is_file():
        raise ImportError_(_no_such_image(target))
    if target.suffix.lower() not in IMAGE_EXTS:
        raise ImportError_(f"{target.name} 不是图片（认这些后缀：{'、'.join(sorted(IMAGE_EXTS))}）")
    at = target.resolve()
    if not any(at.is_relative_to((feature_root / Path(*d)).resolve()) for d in ((ASSETS,), ("AR", "story-src", "meetings"))):
        raise ImportError_(f"{target.name} 不是导入后的图：先导入它所在的原件，再给 assets/ 里导入后的那张图写说明")
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
# 落点：1.9.9 的目录，版本字节另存一份

def derived_name(key: str) -> str:
    """原件派生目录的名字：主名 + 身份键 UTF-8 的 SHA256 前 16 位。不同目录下的同名原件各落各的，不用人改名。"""
    return f"{PurePosixPath(key).stem}.{sha256(key.encode('utf-8')).hexdigest()[:16]}"


def stored_name(name: str, blob: bytes) -> str:
    """按内容身份起名：主名 + 内容摘要前 16 位 + 原后缀。同一内容落同一个名，换了内容另起一个，谁也不覆盖谁。"""
    p = PurePosixPath(name)
    return f"{p.stem}.{digest(blob)[:16]}{p.suffix.lower()}"


def kept_path(key: str, blob: bytes) -> str:
    """一个版本的原件字节另存在哪（相对需求目录）：`.backups/local/inbox/<原相对目录>/<主名>.<内容摘要><后缀>`。
    收件箱里同名原件被换掉时，已登记版本仍指得回这份字节；退掉的原件也落在这里。"""
    p = PurePosixPath(key)
    return "/".join([*BACKUP, INBOX[-1], *p.parts[:-1], stored_name(p.name, blob)])


def reading_path(cls: str, label: str, number: int, suffix: str = ".md") -> str:
    """一个版本的阅读稿存在哪：`.backups/local/<类>/<标签>-v<N>.md`。文本原件不用转换时阅读稿是原字节，沿原后缀。
    每个版本一个阅读地址：内容相同的原件共用一份字节留存，阅读地址仍指认得出是哪一版。"""
    return "/".join([*BACKUP, cls, f"{label}-v{number}{suffix}"])


#: 当前阅读稿 → 它的类（稳定副本落在 `.backups/local/<类>/`）
DRAFT_CLASS = {"RR/prd.md": "RR", "SR/design.md": "SR", "AR/design.md": "AR", "AR/story-src/upstream.md": "AR",
               f"{UX_DIR}/README.md": "UX"}


def draft_label(target: str) -> str:
    """当前阅读稿稳定副本的标签：`<主名>-聚合`。来源标签不取这个形状。"""
    return f"{safe_label(PurePosixPath(target).stem)}-聚合"


def draft_reading(target: str, number: int) -> str:
    """当前阅读稿第 N 版的稳定副本：`.backups/local/<类>/<主名>-聚合-v<N>.md`。设计引用它，不引用会换版的当前稿。"""
    return reading_path(DRAFT_CLASS[target], draft_label(target), number)


def draft_target(cls: str, kind: str) -> str | None:
    """当前阅读稿的落点：RR、SR 与需求系统取得的 AR 正文沿 1.9.9 的位置；本地补录的 AR 材料落 upstream
    （`AR/design.md` 留给本单取得的原文）；界面材料的文字说明并进 `assets/ux/README.md`。IMAGES 与 MEETING 不并进正文。"""
    if cls == "AR":
        return "AR/design.md" if kind == "system" else "AR/story-src/upstream.md"
    return {"RR": "RR/prd.md", "SR": "SR/design.md", "UX": f"{UX_DIR}/README.md"}.get(cls)


def relink(text: str, move) -> str:
    """把正文里的本地链接按 `move(路径) -> 新路径 | None` 改写；返回 None 的、外部地址与文内锚点不动。"""
    out = []
    for line in text.splitlines(keepends=True):
        for start, end, target in reversed(markdown_links(line)):
            if not _local_ref(target):
                continue
            path, suffix = _split_target(target)
            new = move(path)
            if new is not None:
                line = line[:start] + markdown_target(new, suffix) + line[end:]
        out.append(line)
    return "".join(out)


def reroot(text: str, from_dir: str, to_dir: str) -> str:
    """同一份正文换个位置放：本地链接按原位置解析，改写成相对新位置的路径。"""
    return relink(text, lambda p: posixpath.relpath(posixpath.normpath(posixpath.join(from_dir, p)), to_dir))


def write_once(feature_root: Path, rel: str, data: bytes) -> bool:
    """写一份留存文件：已在且字节相同就不动（返回 False），字节不同报出来——留存不覆盖。"""
    path = feature_root / rel
    if path.is_file():
        if path.read_bytes() == data:
            return False
        raise OSError(f"{rel} 已存在且内容不同：留存文件不覆盖，查明它从哪来")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return True


# ---------------------------------------------------------------------------
# 导入：原件 → 材料版本

def safe_label(text: str) -> str:
    """版本留存文件名用的可读标签：去掉路径与 shell 敏感字符，空白连成 `-`；不以点开头。"""
    label = re.sub(r"[\\/:*?\"<>|\s]+", "-", str(text)).strip(".-")[:60].strip(".-")
    return label or "材料"


def unique_label(stored: dict, source_id: str, base: str, planned: dict[str, str] | None = None) -> str:
    """来源的标签：已登记的沿用；新来源撞了别的来源（含这一批里先定下的）的标签就加身份摘要——
    不区分大小写，盘上 Flow 与 flow 是同一个文件。定下的记进 `planned`。"""
    planned = {} if planned is None else planned
    for s in stored["sources"]:
        if s["source_id"] == source_id and s.get("label"):
            return s["label"]
    if source_id in planned:
        return planned[source_id]
    label = safe_label(base)
    taken = {str(s.get("label") or "").casefold() for s in stored["sources"] if s["source_id"] != source_id}
    taken |= {v.casefold() for k, v in planned.items() if k != source_id}
    taken |= {draft_label(t).casefold() for t in DRAFT_CLASS}
    planned[source_id] = label if label.casefold() not in taken else f"{label}-{digest(source_id.encode('utf-8'))[:6]}"
    return planned[source_id]


def known_classes(stored: dict, inbox: Path, files: list[Path]) -> dict[str, str]:
    """已经并入、字节没变的本地原件的类：取它登记的类，归类件里不必再写一遍；新件与改过的件仍要归类。"""
    out = {}
    for path in files:
        key = source_key(inbox, path)
        source = next((s for s in stored["sources"] if s["source_id"] == f"local:{key}"), None)
        if source and source["versions"] and source["versions"][-1]["original"]["sha256"] == digest(path.read_bytes()):
            out[key] = source["class"]
    return out


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


#: docx 内嵌图在转换时先写成这个占位目录下的原名，落点定了再改写
MEDIA_TOKEN = "@media"


def convert(path: Path, key: str, cls: str, ident: dict, here: str) -> tuple[str | None, dict[str, bytes]]:
    """一份 docx 这一版的阅读稿（链接相对 `here`）与内嵌图（落点 → 字节，都在内存里）。

    图按内容身份落在 `assets/<原件派生名>/`；`IMAGES` 只取图：正文不作阅读稿，没有图就报。
    """
    markdown, blobs = docx_to_markdown(path, MEDIA_TOKEN)
    folder = f"{ASSETS}/{derived_name(key if ident['kind'] == 'local' else ident['label'])}"
    names = {n: f"{folder}/{stored_name(n, b)}" for n, b in blobs.items()}
    images = {names[n]: b for n, b in blobs.items()}
    if cls == "IMAGES":
        if not blobs:
            raise ImportError_(f"「{key}」归类为 IMAGES（只抽图）但里面没有图——要采用正文的话改归 RR / SR / AR / UX")
        return None, images
    lead = f"{MEDIA_TOKEN}/"
    text = relink(markdown, lambda p: posixpath.relpath(names[p[len(lead):]], here)
                  if p.startswith(lead) and p[len(lead):] in names else None)
    return (text if text.endswith("\n") else text + "\n"), images


MD_EXTS = {".md", ".markdown"}


def markdown_links(line: str) -> list[tuple[int, int, str]]:
    """一行里 `[文字](目标)` 与 `![文字](目标)` 的目标：(目标在行里的起止, 目标)。

    与 `story/language.mjs` 的 `markdownLinks` 同一读法：`<…>` 包起来的目标可含空格与括号（起止含尖括号），
    否则不含空白、括号成对，`\\` 转义下一个字符；表格里转义的 `\\|`、`\\(`、`\\)` 在目标里还原。解析不出目标的不算链接。
    """
    out: list[tuple[int, int, str]] = []
    i = 0
    while (i := line.find("](", i)) >= 0:
        j = i + 2
        if line[j:j + 1] == "<":
            close = line.find(">", j)
            if close > j and line[close + 1:close + 2] == ")":
                out.append((j, close + 1, re.sub(r"\\([|()])", r"\1", line[j + 1:close])))
                i = close + 2
                continue
        else:
            depth, k = 0, j
            while k < len(line):
                c = line[k]
                if c == "\\":
                    k += 2
                    continue
                if c.isspace():
                    break
                if c == "(":
                    depth += 1
                elif c == ")":
                    if not depth:
                        break
                    depth -= 1
                k += 1
            if line[k:k + 1] == ")" and k > j:
                out.append((j, k, re.sub(r"\\([|()])", r"\1", line[j:k])))
                i = k + 1
                continue
        i += 2
    return out


def markdown_target(path: str, suffix: str = "") -> str:
    """写回链接的目标：与 `language.mjs` 的 `markdownTarget` 同一写法——`% # ? < >` 编码，含空白或括号时用尖括号包起来。
    `suffix` 是原链接的 `#片段` 或 `?查询`，原样接在后面。"""
    s = re.sub(r"[%#?<>]", lambda m: f"%{ord(m.group(0)):02X}", path) + suffix
    return f"<{s}>" if re.search(r"[\s()]", s) else s


def _local_ref(target: str) -> bool:
    """本地相对引用：不是外部地址、不是文内锚点、不是绝对路径。"""
    return bool(target) and not re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) and not target.startswith(("#", "/"))


def _split_target(target: str) -> tuple[str, str]:
    """(按 URL 读法还原的路径, 原样的 `#片段`/`?查询`)。"""
    cut = re.search(r"[?#]", target)
    head, suffix = (target[:cut.start()], target[cut.start():]) if cut else (target, "")
    return unquote(head), suffix


def has_local_links(text: str) -> bool:
    return any(_local_ref(target) for line in text.splitlines() for _, _, target in markdown_links(line))


def project_markdown(text: str, key: str, here: str, targets: dict[str, str]) -> tuple[str | None, list[str]]:
    """Markdown 原件按导入前的位置解析本地引用，换成指向导入后可读产物的阅读投影。

    `key` 是它在收件箱里的位置，`here` 是阅读投影所在目录（相对需求目录），`targets` 是收件箱位置 → 导入后给人读的那一份
    （本批导入的与已登记的：有阅读稿的指阅读稿，图与文本原件指留存）。返回 (阅读投影, 找不到的引用)；
    没有本地引用为 (None, [])，原件自己就是阅读稿。
    """
    missing: list[str] = []
    changed = False
    lines = []
    for line in text.splitlines(keepends=True):
        for start, end, target in reversed(markdown_links(line)):
            if not _local_ref(target):
                continue
            path, suffix = _split_target(target)
            final = targets.get(posixpath.normpath(posixpath.join(posixpath.dirname(key), path)))
            if final is None:
                missing.append(target)
                continue
            changed = True
            line = line[:start] + markdown_target(posixpath.relpath(final, here), suffix) + line[end:]
        lines.append(line)
    return ("".join(lines) if changed else None), missing


def _reading(v: dict) -> str:
    """一个已登记版本给人读的那一份：有阅读稿取阅读稿，否则原件留存（图、文本原件）。"""
    return (v.get("readable") or v["original"])["path"]


def cmd_import(feature_root: Path, project_root: Path) -> dict:
    """把收件箱里还没并入的件导成材料版本，再按各类来源的最新版本重出当前阅读稿。原件留在收件箱。

    输入与格式的问题在写盘前一次报全，盘上一个字节不动：转换全部在内存里做完才开始写。
    留存文件按内容起名、只增不改；中途失败如实报出已登记的版本与没动的原件，重跑会把这一批写全。
    """
    from materials import meeting, registry  # 延迟导入：两者都引用本模块

    try:
        stored = registry.load(feature_root)
        registry.verify(feature_root, stored)
    except registry.MaterialError as exc:
        raise ImportError_(str(exc)) from exc
    inbox = inbox_of(feature_root)
    receipts = read_receipts(inbox)
    sources = scan_sources(inbox)
    classify = {**known_classes(stored, inbox, sources), **read_classify(inbox)}
    validate(inbox, sources, classify, receipts)
    reused: list[dict] = []

    # 已留存的会议版本：转换文本缺了或被改过就按同目录原件补回来；补不成原样的明说，不重编号——引用记的是行号
    for folder in meeting.versions(feature_root).values():
        if meeting.raw_lines(folder)[1]:
            failed = meeting.restore_raw(folder)
            if failed:
                raise ImportError_(failed)

    # 收件箱位置 → 已登记的最新版本给人读的那一份：Markdown 引用的本地文件可能早已导入
    targets: dict[str, str] = {}
    for s in stored["sources"]:
        for v in s["versions"]:
            if v.get("inbox_path"):
                targets[v["inbox_path"]] = _reading(v)

    def number_of(ident: dict) -> int:
        last = registry.latest(stored, ident["source_id"])
        taken = sum(1 for item in plan if item.get("ident", {}).get("source_id") == ident["source_id"])
        return (last or {}).get("version", 0) + taken + 1

    # ── 先全部转换到内存，全成功才写盘 ──────────────────────────────
    plan: list[dict] = []
    planned: dict[str, str] = {}
    markdown: list[tuple[Path, str, str]] = []
    for path in sources:
        key = source_key(inbox, path)
        cls = class_of(key, classify, receipts)
        if cls not in ("MEETING", "IMAGES") and path.suffix.lower() in MD_EXTS:
            markdown.append((path, key, cls))       # 第二遍：等本批其余件的位置定了再出阅读投影
            continue
        if cls == "MEETING":
            if not meeting.saved(feature_root, path):
                plan.append({"key": key, "path": path, "meeting": docx_to_markdown(path, meeting.MEDIA)})
            continue
        ident = identify(inbox, path, cls, receipts)
        blob = path.read_bytes()
        if registry.imported(stored, key, cls, digest(blob), ident["source_id"]):
            reused.append({"file": key, "version": (registry.latest(stored, ident["source_id"]) or {}).get("dir")})
            continue
        label, number = unique_label(stored, ident["source_id"], ident["label"], planned), number_of(ident)
        ident = {**ident, "label": label}
        here = "/".join([*BACKUP, cls])
        if path.suffix.lower() in IMAGE_EXTS:
            original, readable, images = f"{UX_DIR}/{stored_name(path.name, blob)}", None, {}
        elif path.suffix.lower() == DOC_EXT:
            readable, images = convert(path, key, cls, ident, here)
            original = kept_path(key, blob)
        else:
            original, readable, images = kept_path(key, blob), None, {}
        text_original = readable is None and path.suffix.lower() not in IMAGE_EXTS and cls != "IMAGES"
        reading = (reading_path(cls, label, number) if readable is not None
                   else reading_path(cls, label, number, path.suffix.lower()) if text_original else None)
        plan.append({"key": key, "path": path, "ident": ident, "number": number, "blob": blob, "original": original,
                     "readable": readable, "reading": reading, "images": images, "text_original": text_original})
        targets[key] = reading or original
    # Markdown：本批的阅读版本先在内存里定稳，再出最终稿。新原件出新版本；原件没变的按已有版本的阅读位置渲染，
    # 阅读内容变了（它引用的本批材料换了版本）就提升为新版本、更新目标，引用它的再重算——每份至多提升一次，有限输入自然收敛。
    docs: list[dict] = []
    for path, key, cls in markdown:
        ident = identify(inbox, path, cls, receipts)
        blob = path.read_bytes()
        have = registry.latest(stored, ident["source_id"])
        new = not registry.imported(stored, key, cls, digest(blob), ident["source_id"])
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = ""
        label = unique_label(stored, ident["source_id"], ident["label"], planned)
        number = number_of(ident)
        target = reading_path(cls, label, number, path.suffix.lower())
        docs.append({"path": path, "key": key, "cls": cls, "ident": {**ident, "label": label}, "have": have, "blob": blob,
                     "number": number, "text": text, "new": new, "target": target})
        targets[key] = target if new else _reading(have)
    here_of = lambda doc: "/".join([*BACKUP, doc["cls"]])  # noqa: E731

    def rendered(doc: dict) -> tuple[str | None, list[str]]:
        return project_markdown(doc["text"], doc["key"], here_of(doc), targets)

    def same(doc: dict) -> bool:
        readable, _ = rendered(doc)
        have = doc["have"]
        return bool(have.get("readable")) and have["readable"]["sha256"] == (
            have["original"]["sha256"] if readable is None else digest(readable.encode("utf-8")))

    promoted = True
    while promoted:
        promoted = False
        for doc in docs:
            if not doc["new"] and not same(doc):
                doc["new"], promoted = True, True
                targets[doc["key"]] = doc["target"]
    gaps: list[str] = []
    for doc in docs:
        readable, missing = rendered(doc)
        gaps += [f"「{doc['key']}」引用的 {m}" for m in missing]
        if not doc["new"]:
            reused.append({"file": doc["key"], "version": doc["have"].get("dir")})
            continue
        plan.append({"key": doc["key"], "path": doc["path"], "ident": doc["ident"], "number": doc["number"],
                     "blob": doc["blob"], "original": kept_path(doc["key"], doc["blob"]), "readable": readable,
                     "reading": doc["target"], "images": {}, "text_original": readable is None})
    if gaps:
        raise ImportError_("Markdown 引用的本地文件找不到（不在收件箱里，也没导入过）：" + "；".join(gaps)
                           + "——把引用的图或文件按原来的相对位置一起放进收件箱再导；外部链接与文内锚点不受影响")

    # ── 写盘 ────────────────────────────────────────────────────────
    out = {"imported": [], "reused": reused, "versions": [], "meetings": [], "drafts": [], "held": [], "direct": []}
    try:
        for item in plan:
            if "meeting" in item:
                text, blobs = item["meeting"]
                folder, _ = meeting.save_version(feature_root, item["path"], text, blobs)
                out["meetings"].append(folder.relative_to(feature_root).as_posix())
            else:
                _write_version(feature_root, stored, item)
                out["versions"].append(f"{item['ident']['label']}-v{item['number']}")
            out["imported"].append(item["key"])
        out["drafts"], out["held"] = write_drafts(feature_root, stored)
        out["direct"] = register_direct(feature_root, stored, changes=True)
    except OSError as exc:
        _save(feature_root, stored)
        left = [i["key"] for i in plan if i["key"] not in out["imported"]]
        done = [f"{i['key']}（{i['ident']['label']}-v{i['number']}）" for i in plan if "ident" in i and i["key"] in out["imported"]]
        raise ImportError_(f"写盘中途失败（{exc}）：已登记的 {'、'.join(done) or '无'}；"
                           f"还没登记的 {'、'.join(left) or '无'}；原件都还在收件箱。留存文件按内容起名、只增不改，"
                           "先排除写入故障（权限、占用、磁盘），再重跑导入") from exc
    _save(feature_root, stored)
    for item in plan:
        if "ident" in item:
            log(f"{item['key']} → {item['ident']['label']}-v{item['number']}"
                + (f"（阅读稿 {item['reading']}" + (f"，{len(item['images'])} 张图" if item["images"] else "") + "）"
                   if item["reading"] else f"（{len(item['images'])} 张图）" if item["images"] else f"（留存 {item['original']}）"))
    for rel in out["drafts"]:
        log(f"当前阅读稿 → {rel}")
    for rel in out["held"]:
        log(f"{rel} 是人写或人改过的，不覆盖：同类原件各自按自己的阅读稿读")
    for rel in out["direct"]:
        log(f"{rel} 是直接写的原文，已登记成新版本")
    manifest = registry.refresh(feature_root)
    root = project_root.resolve()
    out["images"] = [_shown(root, feature_root / p) for i in manifest.get("materials", [])
                     if i.get("kind") == "image" for p in i.get("paths", [])[:1]]
    out["digest"] = manifest.get("digest")
    return out


def _save(feature_root: Path, stored: dict) -> None:
    """登记落盘：先把已写好的版本记下来，再整份重算。"""
    from materials import registry  # noqa: PLC0415
    registry.write(feature_root, registry.build(feature_root, stored))


def _shown(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _write_version(feature_root: Path, stored: dict, item: dict) -> None:
    """写一个新版本的留存（原件字节、阅读稿与图都按内容起名、只增不改），写全了再登记。"""
    from materials import registry  # noqa: PLC0415
    blob = item["blob"]
    write_once(feature_root, item["original"], blob)
    original = {"path": item["original"], "sha256": digest(blob)}
    readable = None
    if item["readable"] is not None or item["text_original"]:
        # 原件共用按内容起名的字节留存；阅读稿每版一份（文本原件就是原字节），设计引用它就指认得出这一版
        data = blob if item["readable"] is None else item["readable"].encode("utf-8")
        write_once(feature_root, item["reading"], data)
        readable = {"path": item["reading"], "sha256": digest(data)}
    images = []
    for rel, data in item["images"].items():
        write_once(feature_root, rel, data)
        images.append({"path": rel, "sha256": digest(data)})
    registry.add_version(stored, item["ident"], {
        "version": item["number"], "dir": f"{item['ident']['label']}-v{item['number']}", "acquired_at": now(),
        "inbox_path": item["key"], "original": original, "readable": readable, "images": images})


GENERATED_MARK = ("<!-- 本文件由 import_sources.py 按收件箱与已取得的系统材料生成；直接改了它，导入时登记为直接原文、不再覆盖 -->")


def demote_headings(markdown: str, shift: int) -> str:
    """把文档自带的标题整体降级，使其嵌在节标题之下：每份材料在当前阅读稿里占一个 `##` 节，降级到 6 级封顶。"""
    def fix(line: str) -> str:
        m = re.match(r"^(#{1,6})(\s)", line)
        if not m:
            return line
        return "#" * min(len(m.group(1)) + shift, 6) + line[len(m.group(1)):]
    return "\n".join(fix(x) for x in markdown.split("\n"))


def render_target(sections: list[tuple[str, str]]) -> str:
    """当前阅读稿 = 本类各来源最新版本按来源排序拼接（每节 `(标题, 正文)`）。无时间戳等易变量，重跑字节一致。"""
    parts = [GENERATED_MARK, ""]
    for title, body in sections:
        parts += [f"## {title}", "", demote_headings(body.strip(), 2), ""]
    return "\n".join(parts).rstrip() + "\n"


def write_drafts(feature_root: Path, stored: dict) -> tuple[list[str], list[str]]:
    """按各类来源的最新版本重出当前阅读稿：系统取得的在前、本地的按收件箱位置排；本地原件已不在收件箱（退掉或移走）的不再并入。
    内容没变不动。盘上那份不是上次生成的——人直接给的原文，或生成后被人改过——人的内容优先，不覆盖：这一类来源不再合成当前稿，
    各自按自己的阅读稿读，人改过的由直接原文登记保住。返回 (写了的当前稿, 保留了人的内容的当前稿)。"""
    groups: dict[str, list[tuple[tuple, str, str, str]]] = {}
    for s in stored["sources"]:
        if s["kind"] not in ("system", "local") or not s["versions"]:
            continue
        v = s["versions"][-1]
        target = draft_target(s.get("class") or "", s["kind"])
        if not target or not v.get("readable"):
            continue
        if s["kind"] == "local" and not (inbox_of(feature_root) / v["inbox_path"]).is_file():
            continue
        o = s.get("origin") or {}
        title = (" ".join(str(x) for x in (o.get("role"), o.get("ticket"), o.get("title")) if x) if s["kind"] == "system"
                 else v["inbox_path"])
        body = reroot((feature_root / v["readable"]["path"]).read_text(encoding="utf-8"),
                      posixpath.dirname(v["readable"]["path"]), posixpath.dirname(target))
        groups.setdefault(target, []).append(((0 if s["kind"] == "system" else 1, title), title, body,
                                              f"{s['source_id']}@{v['version']}"))
    written, held = [], []
    for target, items in sorted(groups.items()):
        items.sort(key=lambda x: x[0])
        text = render_target([(t, b) for _, t, b, _ in items])
        data = text.encode("utf-8")
        sha = digest(data)
        components = [c for *_, c in items]
        last = latest_draft(stored, target)
        path = feature_root / target
        have = digest(path.read_bytes()) if path.is_file() else None
        if have is not None and have != sha and have != (last or {}).get("current_sha256"):
            held.append(target)           # 人写或人改过：不覆盖，已有的聚合版本留着
            continue
        if have != sha:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            written.append(target)
        if last and last["current_sha256"] == sha and last["components"] == components:
            continue
        # 组成或正文变了就是新的一版：当前稿给人读，稳定副本按自己的位置改写链接、只增不改，设计引用它
        number = (last or {}).get("version", 0) + 1
        stable = draft_reading(target, number)
        projected = reroot(text, posixpath.dirname(target), posixpath.dirname(stable)).encode("utf-8")
        write_once(feature_root, stable, projected)
        stored["drafts"].setdefault(target, {"versions": []})["versions"].append(
            {"version": number, "current_sha256": sha, "readable": {"path": stable, "sha256": digest(projected)},
             "components": components, "generated_at": now()})
    return written, held


def latest_draft(stored: dict, target: str) -> dict | None:
    """当前阅读稿最近生成的一版；还没生成过为 None。"""
    versions = (stored["drafts"].get(target) or {}).get("versions") or []
    return versions[-1] if versions else None


def register_direct(feature_root: Path, stored: dict, changes: bool = False) -> list[str]:
    """直接给在 RR/SR/AR 的原文登记成来源版本（`direct_version` 算这一版留存什么）。第一次见到时登记；
    `changes` 为真（导入时）原文、引到的图或由它们生成的阅读稿变了也登记成新版本——生成后被人改过、这次又没重新生成的阅读稿
    同样登记，保住人的改动。

    这一批先在内存里定稳：原文换了的出新版本、占好它的阅读地址；直接原文之间的链接改指对方这一批的阅读地址，
    阅读结果因此变了的再提升为新版本，直到不再变化——登记结果与 RR/SR/AR 的先后无关。全部算完才写盘。返回登记了的位置。"""
    from materials import registry  # noqa: PLC0415
    plan: dict[str, dict] = {}
    planned: dict[str, str] = {}          # 这一批定下的标签：同主名的 SR/design.md 与 AR/design.md 各得各的
    for rel, cls in DIRECT.items():
        path = feature_root / rel
        if not path.is_file():
            continue
        blob = path.read_bytes()
        draft, last = latest_draft(stored, rel), registry.latest(stored, f"direct:{rel}")
        if draft and draft["current_sha256"] == digest(blob):
            continue                      # 导入生成的当前稿，没被人改过
        if (draft or last) and not changes:
            continue                      # 改过的是待导入：查询不替人登记
        sid = f"direct:{rel}"
        label = unique_label(stored, sid, f"{PurePosixPath(rel).stem}-直接", planned)
        number = (last or {}).get("version", 0) + 1
        plan[rel] = {"cls": cls, "sid": sid, "label": label, "number": number, "blob": blob, "last": last,
                     "new": not last or last["original"]["sha256"] != digest(blob)}
    targets = {rel: reading_path(p["cls"], p["label"], p["number"]) if p["new"] else p["last"]["readable"]["path"]
               for rel, p in plan.items()}

    def same(p: dict) -> bool:
        last, version = p["last"], p["version"]
        return bool(last) and last["original"]["sha256"] == version["original"]["sha256"] \
            and (last.get("image_inputs") or []) == version["image_inputs"] \
            and last["readable"]["sha256"] == version["readable"]["sha256"]

    promoted = True
    while promoted:
        promoted = False
        for rel, p in plan.items():
            p["version"], p["files"] = direct_version(feature_root, stored, rel, p["cls"], p["label"], p["number"],
                                                      p["blob"], targets)
            if not p["new"] and not same(p):
                p["new"], promoted = True, True
                targets[rel] = reading_path(p["cls"], p["label"], p["number"])
    done = []
    for rel, p in plan.items():
        if not p["new"]:
            continue
        for at, data in p["files"].items():
            write_once(feature_root, at, data)
        registry.add_version(stored, {"source_id": p["sid"], "kind": "direct", "class": p["cls"], "origin": {"file": rel},
                                      "label": p["label"]},
                             {"version": p["number"], "dir": f"{p['label']}-v{p['number']}", "acquired_at": now(), **p["version"]})
        done.append(rel)
    return done


def direct_version(feature_root: Path, stored: dict, rel: str, cls: str, label: str, number: int,
                   blob: bytes, batch: dict[str, str] | None = None) -> tuple[dict, dict[str, bytes]]:
    """直接原文这一版的登记与要写的留存（只算不写）。

    没有本地链接时原字节就是阅读稿 `<标签>-v<N>.md`。有本地链接时原字节原样另存为 `<标签>-v<N>.original.md`，阅读稿是它在
    留存位置的投影：引到的图按内容身份落成稳定资源（已登记的同内容图直接复用，否则存一份到 `assets/ux/` 或这份原文的
    `assets/<派生名>/`，用户原图留在原处），链接改指稳定资源；引到会换版的当前位置（收件箱原件、当前阅读稿）改指它此刻的
    稳定阅读地址，引到同一批登记的直接原文改指它这一批的阅读地址（`batch`）；其余按原处解析改写。`images` 只登记稳定资源，原图位置与此刻的摘要记在 `image_inputs`，判下一次换没换图。
    引到的图不在报出来。"""
    from materials import registry  # noqa: PLC0415
    sha = digest(blob)
    reading = reading_path(cls, label, number)
    text = blob.decode("utf-8", errors="replace")
    if not has_local_links(text):
        same = {"path": reading, "sha256": sha}
        return {"original": same, "readable": dict(same), "images": [], "image_inputs": []}, {reading: blob}
    here, there = posixpath.dirname(rel), posixpath.dirname(reading)
    stable = {at: a["path"] for at, a in registry.aliases(feature_root, stored).items()} | (batch or {})
    files: dict[str, bytes] = {}
    images: list[dict] = []
    inputs: list[dict] = []
    missing: list[str] = []

    def move(p: str) -> str | None:
        linked = posixpath.normpath(posixpath.join(here, p))
        if posixpath.splitext(linked)[1].lower() not in IMAGE_EXTS:
            return posixpath.relpath(stable.get(linked, linked), there)
        picture = feature_root / linked
        if not picture.is_file():
            missing.append(linked)
            return None
        data = picture.read_bytes()
        h = digest(data)
        known = registry.stable_image(stored, h)
        kept_image = known or (
            linked if PurePosixPath(linked).stem.endswith(f".{h[:16]}") else
            f"{UX_DIR if linked.startswith(UX_DIR + '/') else ASSETS + '/' + derived_name(rel)}/"
            f"{stored_name(PurePosixPath(linked).name, data)}")
        if known is None:
            files[kept_image] = data
        if kept_image not in [i["path"] for i in images]:
            images.append({"path": kept_image, "sha256": h})
        if linked not in [i["path"] for i in inputs]:
            inputs.append({"path": linked, "sha256": h, "stable_path": kept_image})
        return posixpath.relpath(kept_image, there)

    projected = relink(text, move).encode("utf-8")
    if missing:
        raise ImportError_(f"{rel} 引用的图不在：{'、'.join(sorted(set(missing)))}——把图放回引用的位置，"
                           "或改掉正文里的引用，再重跑")
    kept = reading.removesuffix(".md") + ".original.md"
    files.update({kept: blob, reading: projected})
    return {"original": {"path": kept, "sha256": sha}, "readable": {"path": reading, "sha256": digest(projected)},
            "images": images, "image_inputs": inputs}, files


def retire_source(feature_root: Path, key: str) -> dict:
    """被新原件取代的旧原件移出收件箱：留在 `.backups/local/inbox/<原相对目录>/<主名>.<内容摘要><扩展名>`（与版本留存同一个名）。

    已经留存过同一份字节就只把收件箱里那份拿走；同名而内容不同的已在时拒绝，不覆盖历史原件。归类键随之删掉。
    能先核的都在动第一个文件之前核完，不过就一个文件都不动；真正写盘中途失败，报出已经做了什么、东西在哪、怎样恢复。
    """
    inbox = inbox_of(feature_root)
    refuse = f"--retire「{key}」不动任何文件："
    pure = PurePosixPath(key or "")
    if (not key or key != pure.as_posix() or "\\" in key or ":" in key or pure.is_absolute()
            or {".", ".."} & set(pure.parts)):
        raise ImportError_(f"{refuse}写相对收件箱的路径，与 .classify.json 的键同一写法（不带盘符、`..`、`./` 或反斜杠）")
    src = inbox / Path(*pure.parts)
    try:
        check_inbox_root(inbox)
    except ImportError_ as exc:
        raise ImportError_(f"{refuse}{exc}") from exc
    if not src.resolve().is_relative_to(inbox.resolve()) or not src.is_file():
        raise ImportError_(f"{refuse}收件箱里没有这份原件（或它经链接指到了收件箱之外）")
    blob = src.read_bytes()
    shown = kept_path(key, blob)
    dest = feature_root / shown
    backup_root = feature_root.joinpath(*BACKUP, INBOX[-1])
    if not dest.resolve().is_relative_to(backup_root.resolve()) or not backup_root.resolve().is_relative_to(feature_root.resolve()):
        raise ImportError_(f"{refuse}留存位置经链接指到了需求目录之外（{shown}）")
    classify = read_classify(inbox)          # 归类件坏了在这里就停下，原件还在原处
    if dest.exists() and dest.read_bytes() != blob:
        raise ImportError_(f"{refuse}{shown} 已在且内容不同，不覆盖历史原件——先查明这份留存从哪来")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            src.unlink()
        else:
            shutil.move(str(src), str(dest))
    except OSError as exc:
        moved = dest.exists() and not src.exists()
        raise ImportError_(f"--retire「{key}」移动时失败（{exc}）：" + (
            f"原件已在 {shown}，归类键还没删——删掉 .classify.json 里的「{key}」即完成" if moved
            else "原件还在收件箱原处，没有移动——排除故障后重跑")) from exc
    removed = classify.pop(key, None)
    if removed is not None:
        try:
            (inbox / CLASSIFY_FILE).write_text(json.dumps(classify, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            raise ImportError_(f"--retire「{key}」原件已移到 {shown}，但归类件写不回（{exc}）："
                               f"手动删掉 .classify.json 里的「{key}」；要撤回，把 {shown} 移回 inbox/{key}") from exc
    return {"retired": key, "backup": shown, "classify_key_removed": removed is not None}
