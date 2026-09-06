"""import_sources.py — 把人工放进 inbox/ 的上游材料转成流程能消费的形态。

需求系统里 PRD/SE 有时没及时归档，现场只能人工拿到文档或设计图。本脚本负责把它们
接进既有流程：docx 转 md 覆盖对应上游正文（图片抽出保留引用），设计图分发到框架的
UX 参考落点。下游（AR/design 生成、章节装配、spec）消费的是那几个权威文件，
感知不到材料来源。

    python import_sources.py --feature <AR> [--project-root <abs>]

归类读 `inbox/.classify.json`，内容是 `{"文件名": "RR|SR|AR|UX"}`。**归类判断不是脚本的活**：
它需要读文件名、内容语义与人在关卡上的说明，属语义判断，由 AI 做出后写进该文件；
脚本只负责执行与收敛。没给归类的文件不会被默默忽略——那等于人以为导了、实际没导。

**归类为什么走文件而不是命令行参数**：JSON 全是引号，而任何 shell 都要对参数再解析一遍
——同一条命令 bash 下原样送达，Windows PowerShell 下双引号被吞、这里收到 `{a:b}`。
宿主是变量，所以约束落在接口上：结构化数据走文件（AI 写文件不过 shell），参数只放标量。

核心不变量：

    某类材料的目标文件全文 = 该类 inbox 文件集合（按文件名排序拼接）的转换结果。

由此重跑幂等、改了重放即重转、某类清空则该类目标不再被本脚本改写（不是清空——
「不动」才是收敛语义）。覆盖前旧内容进 `.backup/`。

只用标准库：docx 是 zip + OOXML，图片抽取本就要走 `zipfile` + XML；再引第三方解析器
等于结构走一套、图片走另一套，还给交付件添一项部署依赖。

stdout 单行 JSON；人类可读日志走 stderr。任何失败都不写盘——整批要么都落，要么一个
字节不动，不存在「部分导入成功」的中间态。

stdout 是**本次事件**的摘要，不是持久事实。材料现在是什么、哪些原件已经并入正文，一律去
`materials.py` 的清单里按磁盘现状问。导入不另留一份回执：同一事实两处写，其中一处过期
或被清掉时，两边都还理直气壮。
"""
from __future__ import annotations

import argparse
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
CLASSES = ("RR", "SR", "AR", "UX", "IMAGES")

# 各类正文的落点。UX 分两路：图片进框架既有的参考图目录，文档并入其 README。
# `IMAGES` 不在这里——它没有正文落点，那正是它与别的类的区别。
DOC_TARGET = {
    "RR": Path("RR/prd.md"),
    "SR": Path("SR/design.md"),
    # AR 类不落 design.md —— 那是会被重生成的草稿，材料写进去就丢了
    "AR": Path("AR/upstream.md"),
    "UX": Path("ux-reference/README.md"),
}
UX_IMAGE_DIR = Path("ux-reference")

GENERATED_MARK = "<!-- 本文件由 import_sources.py 从 inbox/ 生成，直接编辑会在下次导入时丢失 -->"


class ImportError_(Exception):
    """可预期的导入失败：带可执行的补救动作，直接呈给人。"""


def log(msg: str) -> None:
    print(f"[import_sources] {msg}", file=sys.stderr)


def features_dir(project_root: Path) -> str:
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
                f"「{path.name}」未给出归类：请指明它属 RR（产品需求）/ SR（系统设计）/ "
                "AR（本部件补充）/ UX（界面设计）中的哪一类")
        if classify[path.name] not in CLASSES:
            raise ImportError_(
                f"「{path.name}」的归类「{classify[path.name]}」非法，须为 {'/'.join(CLASSES)}")


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


def _run_text(run: ET.Element) -> str:
    text = "".join(node.text or "" for node in run.iter(f"{W}t"))
    if not text:
        return ""
    rpr = run.find(f"{W}rPr")
    if rpr is not None:
        if rpr.find(f"{W}b") is not None:
            text = f"**{text}**"
        if rpr.find(f"{W}i") is not None:
            text = f"*{text}*"
    return text


def _para_markdown(para: ET.Element, style_names: dict[str, str],
                   rel_map: dict[str, str], asset_ref: str) -> str:
    pieces: list[str] = []
    for run in para.findall(f"{W}r"):
        pieces.append(_run_text(run))
        for blip in run.iter(f"{A}blip"):
            embed = blip.get(f"{R}embed", "")
            name = rel_map.get(embed)
            if name:
                pieces.append(f"![{name}]({asset_ref}/{name})")
    for link in para.findall(f"{W}hyperlink"):
        inner = "".join(_run_text(r) for r in link.findall(f"{W}r"))
        if inner:
            pieces.append(inner)

    text = "".join(pieces).strip()
    if not text:
        return ""

    level = _heading_level(para, style_names)
    if level:
        return f"{'#' * level} {text}"

    ppr = para.find(f"{W}pPr")
    if ppr is not None and ppr.find(f"{W}numPr") is not None:
        ilvl = ppr.find(f"{W}numPr/{W}ilvl")
        depth = int(ilvl.get(f"{W}val", "0")) if ilvl is not None else 0
        return f"{'  ' * depth}- {text}"
    return text


def _table_markdown(tbl: ET.Element, style_names: dict[str, str],
                    rel_map: dict[str, str], asset_ref: str) -> str:
    rows: list[list[str]] = []
    for tr in tbl.findall(f"{W}tr"):
        cells = []
        for tc in tr.findall(f"{W}tc"):
            cell = " ".join(
                _para_markdown(p, style_names, rel_map, asset_ref).lstrip("# -")
                for p in tc.findall(f"{W}p")
            ).strip()
            cells.append(cell)
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |",
           "|" + "---|" * width]
    out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(out)


def docx_to_markdown(path: Path, asset_ref: str) -> tuple[str, dict[str, bytes]]:
    """返回 (markdown, 需落盘的媒体)。媒体只返回文档实际引用到的那些。"""
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

    blocks: list[str] = []
    for node in body:
        if node.tag == f"{W}p":
            md = _para_markdown(node, style_names, rel_map, asset_ref)
            if md:
                blocks.append(md)
        elif node.tag == f"{W}tbl":
            md = _table_markdown(node, style_names, rel_map, asset_ref)
            if md:
                blocks.append(md)

    used = {name for rid, name in rel_map.items() if name in blobs}
    return "\n\n".join(blocks), {n: blobs[n] for n in sorted(used)}


# ---------------------------------------------------------------------------
# 写盘（零依赖层）

def backup(feature_root: Path, target: Path) -> Path | None:
    """覆盖前留一份：被抹掉的内容必须有退路。沿用 archive 的 .backup/ 约定。"""
    if not target.exists():
        return None
    dest_dir = feature_root / ".backup"
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem = str(target.relative_to(feature_root)).replace("/", "-").replace("\\", "-")
    dest = dest_dir / f"{stem}-{time.strftime('%Y%m%d%H%M%S')}.md"
    shutil.copyfile(target, dest)
    return dest


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

    返回的就是「这批料落盘后该长成什么样」。`materials.py` 反过来拿它问磁盘：正文是不是
    这批料的转换结果——判「已并入」与真正写进去的东西必须出自同一个算法，否则两边会分叉。
    """
    doc_sections: dict[str, list[tuple[str, str]]] = {c: [] for c in CLASSES}
    media: dict[str, dict[str, bytes]] = {}
    ux_images: list[Path] = []

    for path in sources:
        cls = classify[path.name]
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


def caption_image(feature_root: Path, target: Path, caption: str) -> dict:
    """给材料里的一张图写下「它是什么」。**不复制、不改名、不动文件**。

    不是界面的图也要有说明——流程图、时序图、状态机都算。成文时作者面上关于一张图的
    全部信息就是路径与这句话；没有它，作者无从知道该在哪一章用它。
    """
    import materials  # 延迟导入：本模块被 materials 引用，顶层互相 import 会成环

    if not target.is_file():
        raise ImportError_(f"读不到 {target}——要写说明的图得先在磁盘上")
    if target.suffix.lower() not in IMAGE_EXTS:
        raise ImportError_(f"{target.name} 不是图片（认这些后缀：{'、'.join(sorted(IMAGE_EXTS))}）")
    if not caption.strip():
        raise ImportError_("缺 --caption：一句「这张图是什么」")
    # 身份由清单模块算——两处各算一份，差一位截断就会静默挂不上
    sha = materials.file_digest(target)
    materials.write_caption(feature_root, sha, caption.strip())
    manifest = materials.refresh(feature_root)
    return {"sha256": sha, "caption": caption.strip(), "digest": manifest.get("digest")}


def register_ux(feature_root: Path, source: Path, name: str, caption: str) -> dict:
    """把一张图登记成**界面参考**：复制到 `ux-reference/` 起语义名，并写下它是什么。

    只给界面用。不是界面的图（流程图、时序图）写说明走 `--caption-image`——
    复制进 `ux-reference/` 会让视觉链路把它当成一屏去匹配，然后报它没映射到任何页面。

    图片的身份是内容，所以说明按 sha256 记，跟着这张图走；名字只是给人看的。
    登记完刷新材料清单——清单是唯一真源，作者任务包与读者审查都从它逐张读。
    """
    import materials  # 延迟导入：本模块被 materials 引用，顶层互相 import 会成环

    if not source.is_file():
        raise ImportError_(f"读不到 {source}——要登记的图得先在磁盘上")
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
    sha = materials.file_digest(dest)
    materials.write_caption(feature_root, sha, caption.strip())
    manifest = materials.refresh(feature_root)
    return {"path": dest.relative_to(feature_root).as_posix(), "sha256": sha,
            "caption": caption.strip(), "digest": manifest.get("digest")}


def main() -> int:
    ap = argparse.ArgumentParser(description="把 inbox/ 里的人工材料导入上游正文")
    ap.add_argument("--feature", required=False,
                    help="导入模式必填；--preview 只读单份材料时可不填")
    ap.add_argument("--project-root", default=None)
    ap.add_argument("--preview", default=None, metavar="PATH",
                    help="只读预览一份材料的正文与图清单，不落盘（归类判断的输入）")
    ap.add_argument("--register-ux", default=None, metavar="PATH",
                    help="把这张图登记成界面参考：复制到 ux-reference/ 起名，并记下它是什么")
    ap.add_argument("--caption-image", default=None, metavar="PATH",
                    help="给材料里的一张图写说明，不复制不改名（流程图这类走它）")
    ap.add_argument("--name", default="", help="--register-ux 的语义名（不带后缀）")
    ap.add_argument("--caption", default="", help="一句「这张图是什么」")
    args = ap.parse_args()

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    if args.preview:
        # 只读分支：不碰 feature 目录、不写任何文件，走完就退出。
        try:
            out = preview(Path(args.preview))
        except ImportError_ as exc:
            payload = {"mode": "preview", "ok": False, "error": str(exc)}
            sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
            return 1
        log(f"预览 {out['file']}：正文 {len(out['text'])} 字，图 {len(out['images'])} 张")
        payload = {"mode": "preview", "ok": True, **out}
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return 0

    if args.caption_image:
        if not args.feature:
            sys.stdout.write(json.dumps(
                {"mode": "caption-image", "ok": False, "error": "写图片说明需要 --feature"},
                ensure_ascii=False) + "\n")
            return 1
        project_root = Path(args.project_root).resolve() if args.project_root else \
            Path(__file__).resolve().parents[5]
        feature_root = project_root / features_dir(project_root) / args.feature
        target = Path(args.caption_image)
        if not target.is_absolute():
            target = feature_root / target
        try:
            out = caption_image(feature_root, target, args.caption)
        except (ImportError_, OSError) as exc:
            sys.stdout.write(json.dumps({"mode": "caption-image", "ok": False, "error": str(exc)},
                                        ensure_ascii=False) + "\n")
            return 1
        log(f"图片说明已记下：{args.caption_image}——{out['caption']}")
        sys.stdout.write(json.dumps({"mode": "caption-image", "ok": True, **out},
                                    ensure_ascii=False) + "\n")
        return 0

    if args.register_ux:
        if not args.feature:
            sys.stdout.write(json.dumps(
                {"mode": "register-ux", "ok": False, "error": "登记界面图需要 --feature"},
                ensure_ascii=False) + "\n")
            return 1
        project_root = Path(args.project_root).resolve() if args.project_root else \
            Path(__file__).resolve().parents[5]
        feature_root = project_root / features_dir(project_root) / args.feature
        try:
            out = register_ux(feature_root, Path(args.register_ux), args.name, args.caption)
        except (ImportError_, OSError) as exc:
            sys.stdout.write(json.dumps({"mode": "register-ux", "ok": False, "error": str(exc)},
                                        ensure_ascii=False) + "\n")
            return 1
        log(f"界面图已登记：{out['path']}——{out['caption']}")
        sys.stdout.write(json.dumps({"mode": "register-ux", "ok": True, **out},
                                    ensure_ascii=False) + "\n")
        return 0

    if not args.feature:
        payload = {"mode": "import", "ok": False, "error": "导入模式需要 --feature"}
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return 1

    ar = args.feature
    result: dict = {"mode": "import", "reqNo": ar}
    try:
        project_root = Path(args.project_root).resolve() if args.project_root else \
            Path(__file__).resolve().parents[5]
        feature_root = project_root / features_dir(project_root) / ar
        inbox = feature_root / "inbox"

        classify = read_classify(inbox)

        sources = scan_sources(inbox)
        validate(sources, classify)

        # ── 先全部转换到内存，全成功才写盘 ──────────────────────────────
        doc_sections, media, ux_images = convert_sources(sources, classify)

        # ── 写盘 ────────────────────────────────────────────────────────
        written: list[str] = []
        for cls in DOC_TARGET:          # 只有有正文落点的类才写盘
            if not doc_sections[cls]:
                continue  # 该类无材料 → 目标不动（收敛语义是「不动」，不是「清空」）
            target = feature_root / DOC_TARGET[cls]
            target.parent.mkdir(parents=True, exist_ok=True)
            saved = backup(feature_root, target)
            target.write_text(render_target(doc_sections[cls]), encoding="utf-8")
            written.append(str(DOC_TARGET[cls]).replace("\\", "/"))
            log(f"{cls} → {DOC_TARGET[cls]}"
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

        result.update(success=True,
                      converted=[p.name for p in sources],
                      targets=written)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    except ImportError_ as exc:
        log(str(exc))
        result.update(success=False, error=str(exc))
        print(json.dumps(result, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
