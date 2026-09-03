"""materials.py — 材料清单（`AR/story-src/materials.json`）的唯一算法与唯一写入者。

这份清单回答两个问题，而且**只有它**回答：

1. 这个需求现在手里有什么材料——每份正文、每张图各自的身份（路径 + 内容哈希）；
2. 收件箱里的原件哪些已经并入正文、哪些还没有。

清单的 `digest` 是**材料版本**：正文或图片任何一个字节变了，digest 就变；一个字节没变，
重算多少次都相同。轮次边界就取这个值——`story_flow.py` 不再自己算一份材料哈希。

## 谁来算

只有机制层命令算：`story_flow.py round` 每次被调用时按**磁盘现状**重算并落盘。

需求系统的对接层（各部署环境自备的 `story.js` 等）只负责把材料放到该在的位置，
不知道这份清单的存在。理由是它不随包交付：把重算挂在对接层上，等于要求每一份自备实现
都跟着改，而机制层对它们没有任何约束力。按现状重算则对来源免疫——料是谁放的、
怎么放的都不影响结果。

## 「已并入」怎么判

不靠导入时留下的回执，靠磁盘：拿 `import_sources.convert_sources` 把收件箱里那批料
重转一遍，与正文比对。转换是确定性的，所以「正文 == 这批料的转换结果」就是「已并入」，
反过来则说明还有料没导。这样一来，新放的料和被改过的同名料都算未并入，
而不需要任何一方记住曾经发生过什么。

只用标准库。stdout 无输出：本模块是库，不是命令。
"""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import import_sources

SCHEMA = 1
MANIFEST = ("AR", "story-src", "materials.json")

# 权威材料的正文源：四份文本，位置固定。不存在的记 null——「没有」和「没查」是两件事。
SOURCE_DOCS = ("RR/prd.md", "SR/design.md", "AR/design.md", "AR/upstream.md")
# 目录形态的材料源：目录下每个文件各自进清单，加一张图就是材料变了。
#
# 两个目录都是图片的落点，也都是**权威落点**：界面参考图由导入平铺进 `ux-reference/`，
# 文档内嵌图由导入抽进 `assets/<源文档名>/`。图片的登记只有这一处——早先目录里一份、
# 某个 README 的链接里又一份，两份对不上时下游只能挑一份信，而链接那份漏了谁就等于谁不存在。
SOURCE_DIRS = ("ux-reference", "assets")
INBOX = "inbox"


class MaterialError(Exception):
    """可预期的失败：材料清单算不出来。带可执行的补救动作，直接呈给人。"""


def file_digest(path: Path) -> str | None:
    """不存在的源记 null 而非省略——「没有」和「没查」是两件事。"""
    if not path.is_file():
        return None
    return "sha256:" + sha256(path.read_bytes()).hexdigest()[:16]


def kind_of(path: Path) -> str:
    return "image" if path.suffix.lower() in import_sources.IMAGE_EXTS else "doc"


def collect_materials(feature_root: Path) -> list[dict]:
    """枚举权威材料：四份正文按固定顺序在前，目录源按路径排序在后。

    每条记 `paths`（一份材料出现的全部位置）而不是单个 path，因为**图片的身份是它的内容，
    不是它的路径**：界面图按规则要从文档内嵌位置复制一份到 `ux-reference/` 起语义名，
    那不是第二张图，只是同一张图的第二个落点。逐路径各记一条的话，下游拿到的就是
    「两张一模一样的图」，于是要么重复引用，要么各引各的、说的其实是同一张。
    正文不做这种归并：两份内容相同的文档仍是两份材料。

    顺序固定 = digest 稳定。点开头的文件是控制件不是材料，不进清单。
    """
    items: list[dict] = [
        {"kind": "doc", "paths": [rel], "sha256": file_digest(feature_root / rel)}
        for rel in SOURCE_DOCS
    ]
    images: dict[str, dict] = {}
    extra: list[dict] = []
    for rel in SOURCE_DIRS:
        directory = feature_root / rel
        if not directory.is_dir():
            continue
        files = [f for f in directory.rglob("*")
                 if f.is_file() and not f.name.startswith(".")]
        for f in sorted(files, key=lambda x: x.relative_to(feature_root).as_posix()):
            rel_path = f.relative_to(feature_root).as_posix()
            kind = kind_of(f)
            sha = file_digest(f)
            if kind == "image":
                found = images.get(sha)
                if found:
                    found["paths"].append(rel_path)
                else:
                    images[sha] = {"kind": kind, "paths": [rel_path], "sha256": sha}
                    extra.append(images[sha])
            else:
                extra.append({"kind": kind, "paths": [rel_path], "sha256": sha})
    for item in extra:
        # 落点排序：同一张图在哪几处是集合不是序列，排过序才能重算即相同
        item["paths"].sort()
    return items + sorted(extra, key=lambda m: m["paths"][0])


def compute_digest(materials: list[dict]) -> str:
    """材料版本：逐份身份的有序摘要。

    只算权威材料，不算收件箱：料放进收件箱还没导，流程消费的仍是旧正文，材料版本不该动。
    导入之后正文变了，版本随之变——这正是「补料开出新一轮」的机械事实。
    """
    payload = json.dumps([[m["kind"], m["sha256"], m["paths"]] for m in materials],
                         ensure_ascii=False)
    return "sha256:" + sha256(payload.encode("utf-8")).hexdigest()[:16]


def _same_text(disk: str, want: str) -> bool:
    """正文比对忽略行尾差异：同一份内容在两台机器上落盘的行尾可能不同。"""
    return disk.replace("\r\n", "\n") == want.replace("\r\n", "\n")


def collect_sources(feature_root: Path) -> list[dict]:
    """收件箱里的原件：身份 + 是否已并入正文。

    未归类的原件一定未并入——没归类就没有落点。归类件本身坏了则整份清单算不出来，
    不能当成「收件箱是空的」放过去。
    """
    inbox = feature_root / INBOX
    try:
        classify = import_sources.read_classify(inbox)
    except import_sources.ImportError_ as exc:
        raise MaterialError(str(exc)) from exc

    sources = import_sources.scan_sources(inbox)
    entries = {p.name: {"file": p.name, "sha256": file_digest(p),
                        "class": classify.get(p.name) if classify.get(p.name)
                        in import_sources.CLASSES else None,
                        "ingested": False}
               for p in sources}

    grouped: dict[str, list[Path]] = {}
    for path in sources:
        cls = entries[path.name]["class"]
        if cls:
            grouped.setdefault(cls, []).append(path)

    for cls, paths in grouped.items():
        docs = [p for p in paths if p.suffix.lower() not in import_sources.IMAGE_EXTS]
        images = [p for p in paths if p.suffix.lower() in import_sources.IMAGE_EXTS]

        if docs:
            try:
                sections, _, _ = import_sources.convert_sources(
                    docs, {p.name: cls for p in docs})
            except (import_sources.ImportError_, OSError, ValueError) as exc:
                raise MaterialError(
                    f"读不出「{cls}」类材料的转换结果，无法判断它是否已并入正文：{exc}") from exc
            target = feature_root / import_sources.DOC_TARGET[cls]
            if target.is_file() and _same_text(
                    target.read_text(encoding="utf-8", errors="replace"),
                    import_sources.render_target(sections[cls])):
                for p in docs:
                    entries[p.name]["ingested"] = True

        for image in images:
            # 界面图的落点是平铺的顶层，字节相同才算并入——同名换了内容也是新料
            dest = feature_root / import_sources.UX_IMAGE_DIR / image.name
            if dest.is_file() and dest.read_bytes() == image.read_bytes():
                entries[image.name]["ingested"] = True

    return [entries[name] for name in sorted(entries)]


def build(feature_root: Path) -> dict:
    """按磁盘现状算出完整清单。不写盘。"""
    materials = collect_materials(feature_root)
    return {
        "schema": SCHEMA,
        "feature": feature_root.name,
        "digest": compute_digest(materials),
        "materials": materials,
        "sources": collect_sources(feature_root),
    }


def path_of(feature_root: Path) -> Path:
    return feature_root / Path(*MANIFEST)


def write(feature_root: Path, manifest: dict) -> Path:
    path = path_of(feature_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path


def refresh(feature_root: Path) -> dict:
    """算一遍并落盘 —— 机制层命令唯一该调的入口。"""
    manifest = build(feature_root)
    write(feature_root, manifest)
    return manifest


def read(feature_root: Path) -> dict:
    """读已落盘的清单。没有清单和清单坏了都不是「没有材料」，都要报出来。"""
    path = path_of(feature_root)
    if not path.is_file():
        raise MaterialError(
            f"{'/'.join(MANIFEST)} 不存在：材料清单由 `story_flow.py round` 生成，先跑它")
    try:
        data = json.loads(path.read_text(encoding="utf-8").lstrip("﻿"))
    except ValueError as exc:
        raise MaterialError(
            f"{'/'.join(MANIFEST)} 不是合法 JSON（{exc}）：它只应由脚本写入，"
            "若曾手工编辑，删掉后重跑 `story_flow.py round`") from exc
    if data.get("schema") != SCHEMA:
        raise MaterialError(
            f"{'/'.join(MANIFEST)} 的 schema 为 {data.get('schema')}，本版要求 {SCHEMA}")
    return data


def pending(manifest: dict) -> list[str]:
    """收件箱里还没并入正文的原件。空表示没有新料，不表示收件箱是空的。"""
    return [s["file"] for s in manifest.get("sources", []) if not s.get("ingested")]
