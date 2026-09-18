"""把 inbox/ 里的人工材料转成流程能消费的形态：docx 转正文、图片抽取与登记。

正式命令是 `core/import_sources.py`，本模块只做实现。归类由 AI 写进
`inbox/.classify.json`（`{"文件名": "<类>"}`，值域见 `CLASSES`），脚本只负责执行与收敛；
没给归类的文件不会被默默忽略——那等于人以为导了、实际没导。

核心不变量：

    某类材料的目标文件全文 = 该类 inbox 文件集合（按文件名排序拼接）的转换结果。

由此重跑幂等、改了重放即重转、某类清空则该类目标不再被本模块改写（不是清空——
「不动」才是收敛语义）。覆盖前旧内容进 `.backup/`。

只用标准库：docx 是 zip + OOXML，图片抽取本就要走 `zipfile` + XML；再引第三方解析器
等于结构走一套、图片走另一套，还给交付件添一项部署依赖。

任何失败都不写盘——整批要么都落，要么一个字节不动，不存在「部分导入成功」的中间态。
导入也不留回执：材料现在是什么、哪些原件已经并入正文，一律去 `materials/registry.py`
的清单里按磁盘现状问。同一事实两处写，其中一处过期或被清掉时，两边都还理直气壮。
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"

DOC_EXT = ".docx"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
# inbox 里不算材料的文件：目录自解释用的说明书
SKIP_NAMES = {"readme.md"}
# AI 写、脚本读的归类件；与它一样的点文件都是控制件，不是材料
CLASSIFY_FILE = ".classify.json"

#: `IMAGES` 是「只抽图、正文不动」：补料是为了补图时走它。
#: 系统上已有同类正文，而这份补料是原稿或参考稿——把它并进正文会用草稿盖掉定稿，
#: 而人要的只是里面的图。选哪一档由归类时判断，不另外问人一次。
#: `MEETING` 是会议材料：讨论态的证据，不并进任何正文，按版本留住原件与转换文本
#: （`materials/meeting.py`），内容由读会的模型理解。
CLASSES = ("RR", "SR", "AR", "UX", "IMAGES", "MEETING")

# 各类正文的落点。RR / SR / AR 三类的路径是章节合同登记的来源（取 `sources` 的哪一项见下表），
# 不在这里另抄一份。AR 类补料落 upstream.md：`AR/design.md` 是上游给进来的输入件，S4 提交
# 提取稿时整份覆盖它，人工补录的本部件材料要有自己的落点才留得住。
# UX 分两路：图片进参考图目录，文档并入其 README——那个目录按文件登记为材料，不是合同里的来源。
# `IMAGES` 不在这里：它没有正文落点，那正是它与别的类的区别。
DOC_SOURCE = {"RR": "PRD", "SR": "SE", "AR": "UPSTREAM"}
UX_DOC_TARGET = Path("ux-reference/README.md")
UX_IMAGE_DIR = Path("ux-reference")
#: 章节合同：正文来源的路径、是不是本轮派生，登记在它的 `sources` 里。路径只在 flow.state 定一次。
from flow.state import STORY_CONTRACT  # noqa: E402

GENERATED_MARK = "<!-- 本文件由 import_sources.py 从 inbox/ 生成，直接编辑会在下次导入时丢失 -->"


class ImportError_(Exception):
    """可预期的导入失败：带可执行的补救动作，直接呈给人。"""


def contract_sources() -> dict[str, dict]:
    """章节合同登记的正文来源。读不出来就报：当成没有来源，清单会少算整份正文而不出声。"""
    try:
        sources = json.loads(STORY_CONTRACT.read_text(encoding="utf-8")).get("sources")
    except (OSError, ValueError) as exc:
        raise ImportError_(f"读不出章节合同的来源登记（{exc}）：{STORY_CONTRACT}") from exc
    if not isinstance(sources, dict) or not sources:
        raise ImportError_(f"章节合同里没有来源登记 sources：{STORY_CONTRACT}")
    return sources


def doc_targets() -> dict[str, Path]:
    """各类正文的落点：RR / SR / AR 取合同登记的路径，UX 并入参考图目录的说明文件。"""
    sources = contract_sources()
    targets: dict[str, Path] = {}
    for cls, key in DOC_SOURCE.items():
        rel = (sources.get(key) or {}).get("path")
        if not rel:
            raise ImportError_(f"章节合同的来源登记缺 {key}：「{cls}」类材料没有落点")
        targets[cls] = Path(rel)
    targets["UX"] = UX_DOC_TARGET
    return targets


def log(msg: str) -> None:
    print(f"[import_sources] {msg}", file=sys.stderr)


#: 默认工程根。本扩展装在 `<工程>/doc/extensions/` 下，脚本自己的位置就定死了它。
#: 两个正式入口（import_sources、story_flow）都在这里取，算一次后逐层传下去——
#: 各自数一遍目录层数的话，文件往下挪一层就会有一处漏改。
DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[7]


def features_dir(project_root: Path) -> str:
    """需求目录叫什么，由工程自己的 framework.config.json 说了算。"""
    try:
        cfg = json.loads((project_root / "framework.config.json").read_text(encoding="utf-8"))
        value = (cfg.get("paths") or {}).get("features_dir")
        if isinstance(value, str) and value.strip():
            return value.strip()
    except (OSError, ValueError):
        pass
    return "doc/features"


# ---------------------------------------------------------------------------
# 扫描与路由（零依赖层）

def scan_sources(inbox: Path) -> list[Path]:
    """只扫一层：inbox 是声明，不是搜索起点。递归会把子目录里的无关文件卷进来。"""
    if not inbox.is_dir():
        return []
    return sorted((p for p in inbox.iterdir()
                   if p.is_file() and not p.name.startswith(".")
                   and p.name.lower() not in SKIP_NAMES),
                  key=lambda p: p.name)


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
        raise ImportError_(f"inbox/{CLASSIFY_FILE} 应是 {{\"文件名\": \"RR|SR|AR|UX\"}} 对象")
    return data


def is_text(path: Path) -> bool:
    """能不能当文本读——问文件本身，不问扩展名。

    扩展名白名单会把 `.md`/`.txt`/`.log`/无后缀这些模型直接读得懂的材料挡在门外，
    逼人绕道 Word 转一圈。严格 utf-8 解码是更诚实的判据：解得开就是文本。
    """
    try:
        path.read_text(encoding="utf-8")
        return True
    except (UnicodeDecodeError, OSError):
        return False


def validate(sources: list[Path], classify: dict[str, str]) -> None:
    """先验后写：任何一项不合格就整批不动，不存在半改状态。"""
    for path in sources:
        ext = path.suffix.lower()
        if ext != DOC_EXT and ext not in IMAGE_EXTS and not is_text(path):
            raise ImportError_(
                f"「{path.name}」读不开：本脚本能物化的是文本、{DOC_EXT} 与图片"
                f"（{'、'.join(sorted(IMAGE_EXTS))}）。"
                "若你能读懂它的内容，请自行转写成 .md 放回收件箱再归类；"
                "若你也读不了，请让用户提供可读版本")
        if path.name not in classify:
            raise ImportError_(
                f"「{path.name}」未给出归类：请指明它属 {' / '.join(CLASSES)} 中的哪一类")
        if classify[path.name] not in CLASSES:
            raise ImportError_(
                f"「{path.name}」的归类「{classify[path.name]}」非法，须为 {'/'.join(CLASSES)}")
        if classify[path.name] == "MEETING" and ext != DOC_EXT:
            raise ImportError_(f"「{path.name}」归类为 MEETING，但会议材料只收原始 {DOC_EXT}"
                               "：原件要按版本留住，引用才指得回同一段原文")


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
    return [f"![{name}]({asset_ref}/{name})" for name in names if name]


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
# 写盘（零依赖层）

def _backup_stem(feature_root: Path, target: Path) -> str:
    return str(target.relative_to(feature_root)).replace("/", "-").replace("\\", "-")


def backup(feature_root: Path, target: Path) -> Path | None:
    """覆盖前留一份：被抹掉的内容必须有退路。沿用 archive 的 .backup/ 约定。"""
    if not target.exists():
        return None
    dest_dir = feature_root / ".backup"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{_backup_stem(feature_root, target)}-{time.strftime('%Y%m%d%H%M%S')}.md"
    shutil.copyfile(target, dest)
    return dest


def backups_of(feature_root: Path, target: Path) -> list[Path]:
    """`target` 在 `.backup/` 里的全部副本，按文件名排序。命名只在 `backup` 这一处定。"""
    return sorted((feature_root / ".backup").glob(f"{_backup_stem(feature_root, target)}-*.md"))


def demote_headings(markdown: str, shift: int) -> str:
    """把文档自带的标题整体降级，使其嵌在节标题之下。

    每份材料在目标文件里占一个 `##` 节，而文档自己的 `#` 会与之平级甚至反超——
    层级一乱，story 成文后的结构就散了。降级到 6 级封顶（markdown 上限）。
    """
    def fix(line: str) -> str:
        m = re.match(r"^(#{1,6})(\s)", line)
        if not m:
            return line
        return "#" * min(len(m.group(1)) + shift, 6) + line[len(m.group(1)):]
    return "\n".join(fix(l) for l in markdown.split("\n"))


def render_target(sections: list[tuple[str, str]]) -> str:
    """目标文件 = 本类材料按文件名排序拼接。无时间戳等易变量，保证重跑字节一致。"""
    parts = [GENERATED_MARK, ""]
    for title, body in sections:
        parts.append(f"## {title}")
        parts.append("")
        parts.append(demote_headings(body, 2))  # 节标题占 ##，文档 # 降到 ###
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def preview(path: Path) -> dict:
    """只读预览一份材料：正文文本 + 图清单，**不落盘任何东西**。

    归类是判断（这份文档主体是 RR / SR / AR / UX 哪一类），判断要读内容；
    而 .docx 是压缩包，不解开就读不了。落盘那一步的解析器本来就在这里，
    预览复用它——否则读文档的人只能自己写一遍 zipfile + OOXML，
    否则每轮都要重写，还得先猜对 namespace。

    与导入用的是**同一个解析器**：预览看到的正文，就是导入会写进去的正文。
    """
    if not path.is_file():
        raise ImportError_(f"「{path}」不存在")
    if is_text(path):
        return {"file": path.name, "kind": "text",
                "text": path.read_text(encoding="utf-8", errors="replace"), "images": []}
    markdown, blobs = docx_to_markdown(path, ".")
    return {"file": path.name, "kind": "docx", "text": markdown,
            "images": sorted(blobs.keys())}


def convert_sources(sources: list[Path], classify: dict[str, str]
                    ) -> tuple[dict[str, list[tuple[str, str]]],
                               dict[str, dict[str, bytes]], list[Path]]:
    """把这批材料整批转换到内存：正文按类分节、docx 内嵌图按源文档归组、界面图单列。

    返回的就是「这批料落盘后该长成什么样」。`registry.py` 反过来拿它问磁盘：正文是不是
    这批料的转换结果——判「已并入」与真正写进去的东西必须出自同一个算法，否则两边会分叉。
    """
    doc_sections: dict[str, list[tuple[str, str]]] = {c: [] for c in CLASSES}
    media: dict[str, dict[str, bytes]] = {}
    ux_images: list[Path] = []

    for path in sources:
        cls = classify[path.name]
        if cls == "MEETING":
            continue          # 会议转写不并进正文：按版本留存，由读会处理
        if path.suffix.lower() in IMAGE_EXTS:
            if cls != "UX":
                raise ImportError_(
                    f"「{path.name}」是图片但归类为 {cls}：图片只能归 UX（界面设计）")
            ux_images.append(path)
            continue
        stem = path.stem
        if path.suffix.lower() == DOC_EXT:
            # docx 是压缩包，必须脚本转：zip + OOXML，顺带把内嵌图抽出来
            markdown, blobs = docx_to_markdown(path, f"../assets/{stem}")
            if blobs:
                media[stem] = blobs
        else:
            # 文本原样并入——它已经是可读格式，任何"转换"都只会丢东西
            markdown = path.read_text(encoding="utf-8").strip()
        if cls == "IMAGES":
            if not media.get(stem):
                raise ImportError_(
                    f"「{path.name}」归类为 IMAGES（只抽图）但里面没有图——"
                    "要并入正文的话改归 RR / SR / AR / UX")
            continue          # 图已经在 media 里，正文丢掉：这一档就是不动正文
        doc_sections[cls].append((stem, markdown))

    return doc_sections, media, ux_images


def _no_such_image(target: Path) -> str:
    """读不到的时候，把正确的写法一起给出来——只说「读不到」等于让人去翻脚本。"""
    return (f"读不到 {target}——路径相对工程根，"
            "例如 `doc/features/<需求名>/assets/<文件名>`；"
            "绝对路径也认。`--feature <名>` 那次导入打印出来的路径可以直接复制")


def caption_image(feature_root: Path, target: Path, caption: str) -> dict:
    """给材料里的一张图写下「它是什么」。**不复制、不改名、不动文件**。

    不是界面的图也要有说明——流程图、时序图、状态机都算。成文时作者面上关于一张图的
    全部信息就是路径与这句话；没有它，作者无从知道该在哪一章用它。
    """
    from materials import registry  # 延迟导入：本模块被 materials 引用，顶层互相 import 会成环

    if not target.is_file():
        raise ImportError_(_no_such_image(target))
    if target.suffix.lower() not in IMAGE_EXTS:
        raise ImportError_(f"{target.name} 不是图片（认这些后缀：{'、'.join(sorted(IMAGE_EXTS))}）")
    if not caption.strip():
        raise ImportError_("缺 --caption：一句「这张图是什么」")
    # 身份由清单模块算——两处各算一份，差一位截断就会静默挂不上
    sha = registry.file_digest(target)
    registry.write_caption(feature_root, sha, caption.strip())
    manifest = registry.refresh(feature_root)
    return {"sha256": sha, "caption": caption.strip(), "digest": manifest.get("digest")}


def resolve_image_arg(project_root: Path, raw: str) -> Path:
    """图片参数落到哪个文件——**相对工程根**，或者绝对路径。

    只认一种基准。「先按工程根找、找不到再按需求目录找」这种回落，在两处恰好同名时
    会取到另一张图而且不报错；而 `--feature` 打印出来的就是相对工程根的写法，
    作者手上本来就有一份可以直接复制的串。
    """
    path = Path(raw)
    return path if path.is_absolute() else project_root / path


def _image_for_mark(feature_root: Path, target: Path) -> str:
    """取舍写在哪张图上——身份由清单模块算，两处各算一份会差一位截断。"""
    from materials import registry  # 延迟导入：本模块被 materials 引用，顶层互相 import 会成环

    if not target.is_file():
        raise ImportError_(_no_such_image(target))
    if target.suffix.lower() not in IMAGE_EXTS:
        raise ImportError_(f"{target.name} 不是图片（认这些后缀：{'、'.join(sorted(IMAGE_EXTS))}）")
    return registry.file_digest(target)


def mark_unused(feature_root: Path, target: Path, reason: str) -> dict:
    """登记本需求为什么不用这张图。**不复制、不改名、不动文件**。

    材料里的图不都属于本需求——废弃的对照稿、友商参考、别的单据的页面都可能在里面。
    它们的去向要有个落点：写在这里，作者任务包与读者审查逐张读得到，
    归档件里也就不必为了解释一张不用的图而把它引进正文。
    """
    from materials import registry

    if not reason.strip():
        raise ImportError_("缺 --unused 的理由：一句「本需求为什么不用它」")
    sha = _image_for_mark(feature_root, target)
    registry.write_unused(feature_root, sha, reason.strip())
    manifest = registry.refresh(feature_root)
    return {"sha256": sha, "unused": reason.strip(), "digest": manifest.get("digest")}


def mark_used(feature_root: Path, target: Path) -> dict:
    """这张图要用了——撤掉「不用」的理由，说明留着。"""
    from materials import registry

    sha = _image_for_mark(feature_root, target)
    registry.clear_unused(feature_root, sha)
    manifest = registry.refresh(feature_root)
    return {"sha256": sha, "unused": "", "digest": manifest.get("digest")}


def register_ux(feature_root: Path, source: Path, name: str, caption: str) -> dict:
    """把一张图登记成**界面参考**：复制到 `ux-reference/` 起语义名，并写下它是什么。

    只给界面用。不是界面的图（流程图、时序图）写说明走 `--caption-image`——
    复制进 `ux-reference/` 会让视觉链路把它当成一屏去匹配，然后报它没映射到任何页面。

    图片的身份是内容，所以说明按 sha256 记，跟着这张图走；名字只是给人看的。
    登记完刷新材料清单——清单是唯一真源，作者任务包与读者审查都从它逐张读。
    """
    from materials import registry  # 延迟导入：本模块被 materials 引用，顶层互相 import 会成环

    if not source.is_file():
        raise ImportError_(_no_such_image(source))
    if source.suffix.lower() not in IMAGE_EXTS:
        raise ImportError_(f"{source.name} 不是图片（认这些后缀：{'、'.join(sorted(IMAGE_EXTS))}）")
    if not caption.strip():
        raise ImportError_(
            "缺 --caption：一句「这张图是什么」。没有它，下游拿到的只有路径与哈希，"
            "作者无从知道该在哪一章用它")

    stem = name.strip() or source.stem
    dest = feature_root / UX_IMAGE_DIR / f"{stem}{source.suffix.lower()}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    blob = source.read_bytes()
    if not dest.is_file() or dest.read_bytes() != blob:
        dest.write_bytes(blob)
    sha = registry.file_digest(dest)
    registry.write_caption(feature_root, sha, caption.strip())
    manifest = registry.refresh(feature_root)
    return {"path": dest.relative_to(feature_root).as_posix(), "sha256": sha,
            "caption": caption.strip(), "digest": manifest.get("digest")}


def cmd_import(feature_root: Path) -> dict:
    """把 inbox/ 里这一批材料整批转换并落盘。

    要么都落，要么一个字节不动：转换全部在内存里做完才开始写盘，中途失败抛
    `ImportError_`，盘上停在导入前的样子——不存在「部分导入成功」的中间态。
    """
    inbox = feature_root / "inbox"

    classify = read_classify(inbox)

    sources = scan_sources(inbox)
    validate(sources, classify)

    # ── 先全部转换到内存，全成功才写盘 ──────────────────────────────
    doc_sections, media, ux_images = convert_sources(sources, classify)
    from materials import meeting  # 延迟导入：meeting 引用本模块，顶层互相 import 会成环
    # 会议材料按版本留存：**这一版存过就原样复用**，不因转换器升级重转——
    # 旧结论引的是 raw.md 的行号，重转一次就可能全错位。
    meetings: list[tuple[Path, str, dict]] = []
    for path in (p for p in sources if classify[p.name] == "MEETING"):
        if meeting.saved(feature_root, path):
            # 这一版留过：转换件缺了或被改过就按留存的原件补回来；补不成原样的明说，
            # 不重编号、也不拿另一份文本顶替——引用记的是行号。
            folder = meeting.version_dir(feature_root, path)
            if meeting.raw_lines(folder)[1]:
                failed = meeting.restore_raw(folder)
                if failed:
                    raise ImportError_(failed)
                log(f"会议材料 → {folder.relative_to(feature_root).as_posix()}/{meeting.RAW}"
                    "（按留存原件补回，摘要与登记一致）")
            continue
        text, blobs = docx_to_markdown(path, meeting.MEDIA)
        meetings.append((path, text, blobs))

    # ── 写盘 ────────────────────────────────────────────────────────
    written: list[str] = []
    for cls, rel in doc_targets().items():          # 只有有正文落点的类才写盘
        if not doc_sections[cls]:
            continue  # 该类无材料 → 目标不动（收敛语义是「不动」，不是「清空」）
        target = feature_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        saved = backup(feature_root, target)
        target.write_text(render_target(doc_sections[cls]), encoding="utf-8")
        written.append(rel.as_posix())
        log(f"{cls} → {rel.as_posix()}"
            f"（{len(doc_sections[cls])} 份材料{'，旧版已备份' if saved else ''}）")

    for stem, blobs in media.items():
        asset_dir = feature_root / "assets" / stem
        if asset_dir.exists():
            shutil.rmtree(asset_dir)  # 收敛：源文档改了，旧图不该留下
        asset_dir.mkdir(parents=True, exist_ok=True)
        for name, blob in blobs.items():
            (asset_dir / name).write_bytes(blob)
        log(f"图片 → assets/{stem}/（{len(blobs)} 张）")

    for path in ux_images:
        dest_dir = feature_root / UX_IMAGE_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)
        # 顶层平铺：框架对 ux-reference 的扫描非递归，放子目录等于隐形
        shutil.copyfile(path, dest_dir / path.name)
        written.append(f"{UX_IMAGE_DIR.as_posix()}/{path.name}")
        log(f"UX 参考图 → {UX_IMAGE_DIR.as_posix()}/{path.name}")
    for path, text, blobs in meetings:
        # 一个源版本一个目录：同名换了内容落新目录，旧版本的原文与读会产物原样留着
        folder, fresh = meeting.save_version(feature_root, path, text, blobs)
        rel = folder.relative_to(feature_root).as_posix()
        written.append(f"{rel}/{meeting.RAW}")
        log(f"会议材料 → {rel}/（{len(text.splitlines())} 行"
            + (f"，{len(blobs)} 张图" if blobs else "")
            + ("" if fresh else "；这一版已经存过，原样复用") + "）")
    return {"converted": [p.name for p in sources], "targets": written}
