"""材料索引（`AR/story-src/materials.json`）：来源库存与版本身份的唯一索引，也是它的唯一写入者。

索引回答：这个需求手里有哪些**来源**、每个来源取得过哪些**版本**（原件、阅读稿与图的完整摘要）、
收件箱里还有哪些件没导入、每张图是什么、本需求用不用它。它**不回答**设计采用了哪个版本——那由原生蓝图的
范围条目记录；最新取得的版本不等于设计已采用。

## 从哪里来

- 材料版本 `sources/<标签>-v<N>/.version.json`：导入时写下，之后不改（`materials/importer.py`）；
- 会议版本 `AR/story-src/meetings/<主名>/<sha8>/`：版本目录里还有读会产物，身份取原件（`materials/meeting.py`）；
- 有效人答 `sources/人工答复-v<N>/`：从流程契约导出（`materials/answers.py`），刷新索引时有变化才出新版本；
- 收件箱 `sources/inbox/` 里还在的件就是待导入；
- 图片说明与取舍记在索引自己的 `notes` 里，按图的内容摘要键：说明可以改，图还是那张；刷新时原样带过去。

除 `notes` 外都按磁盘现状重算，所以重算多少次结果相同。已引用版本的字节被改是损坏：逐份核摘要，对不上报出原路径。

## 派生视图

- `materials`：各来源最新版本的正文与图（图按内容合并成一条，`paths` 列全部落点，带 `caption`/`unused`）；
- `origins`：各来源最新版本的原件与它的阅读稿——作者材料表、审查任务与独立审查对象读同一份；人答不在其中；
- `digest`：**材料版本**，按最新版本的原件、阅读稿与图的内容算。人答、说明与取舍不进摘要：答一句话或改一句说明不是材料变了。
- `files`：全部登记文件（各来源的每个版本，含人答与会议的原件、raw、纠偏与阅读件）→ 来源、版本、角色与完整摘要。
  需求条目补来源、设计采用与审查核源都按它认文件，不各自扫目录、猜角色；会议的纠偏与阅读件核过同源才列。

只用标准库。stdout 无输出：本模块是库，不是命令。
"""
from __future__ import annotations

import json
import os
import re
import uuid
from hashlib import sha256
from pathlib import Path, PurePosixPath

from materials import answers, importer, meeting

SCHEMA = 3
KINDS = ("system", "local", "meeting", "answer")
MANIFEST = ("AR", "story-src", "materials.json")
README = (importer.SOURCES, "README.md")
NOTE_FIELDS = ("caption", "unused")
KIND_LABEL = {"system": "需求系统取得", "local": "本地提供", "meeting": "会议留存", "answer": "流程人答导出"}


class MaterialError(Exception):
    """可预期的失败：材料索引算不出来。带可执行的补救动作，直接呈给人。"""


def file_digest(path: Path) -> str | None:
    """完整 SHA-256；不存在记 None——「没有」和「没查」是两件事。"""
    if not path.is_file():
        return None
    return sha256(path.read_bytes()).hexdigest()


def version_records(feature_root: Path) -> list[dict]:
    """盘上全部材料版本的记录（`.version.json`），带 `dir`（相对需求目录）。问题一次列全。

    记录里登记的每份文件都按摘要核：缺了或字节变了是损坏，报原路径与真实不一致，不重填摘要放行。
    """
    root = feature_root / importer.SOURCES
    out: list[dict] = []
    problems: list[str] = []
    for path in sorted(root.glob(f"*/{importer.VERSION_FILE}")) if root.is_dir() else []:
        name = path.parent.name
        if name.startswith(".") or name == importer.INBOX[-1]:
            continue
        rel = f"{importer.SOURCES}/{name}"
        try:
            rec = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            problems.append(f"{rel}/{importer.VERSION_FILE} 读不出来（{exc}）")
            continue
        shape = _version_shape(rec)
        if shape:
            problems.append(f"{rel}/{importer.VERSION_FILE}：{shape}")
            continue
        if not re.fullmatch(rf".+-v{rec['version']}", name):
            problems.append(f"{rel}：目录名与版本号 {rec['version']} 对不上")
        for f in [rec["original"], *([rec["readable"]] if rec["readable"] else []), *rec["images"]]:
            have = file_digest(feature_root / f["path"])
            if have is None:
                problems.append(f"{f['path']} 不在了：它是已登记版本 {rel} 的文件")
            elif have != f["sha256"]:
                problems.append(f"{f['path']} 的字节与版本登记不一致（登记 {f['sha256'][:12]}…，现在 {have[:12]}…）："
                                "材料版本导入后不改，内容变了要作为新原件重新导入")
        out.append({**rec, "dir": rel})
    if problems:
        raise MaterialError("材料版本有问题，索引算不出来：\n" + "\n".join(problems))
    seen: dict[tuple, str] = {}
    for rec in out:
        key = (rec["source_id"], rec["version"])
        if key in seen:
            raise MaterialError(f"来源 {rec['source_id']} 的第 {rec['version']} 版有两个目录（{seen[key]}、{rec['dir']}）：留下正确的一份")
        seen[key] = rec["dir"]
    return out


def _version_shape(rec) -> str:
    if not isinstance(rec, dict):
        return "应是对象"
    bad = []
    if not isinstance(rec.get("source_id"), str) or not rec["source_id"]:
        bad.append("缺 source_id")
    if rec.get("kind") not in KINDS:
        bad.append(f"kind 应为 {'/'.join(KINDS)}")
    if not isinstance(rec.get("version"), int) or rec["version"] < 1:
        bad.append("version 应是正整数")
    files = [rec.get("original"), *([rec.get("readable")] if rec.get("readable") is not None else []),
             *(rec.get("images") if isinstance(rec.get("images"), list) else [None])]
    if any(not (isinstance(f, dict) and isinstance(f.get("path"), str) and isinstance(f.get("sha256"), str)) for f in files):
        bad.append("original / readable / images 每项要有 path 与 sha256")
    return "；".join(bad)


def meeting_records(feature_root: Path) -> list[dict]:
    """会议版本按版本记录的形状列出：来源是同一份会议（原件主名），版本按导入先后编号。"""
    problems: list[str] = []
    by_stem: dict[str, list[tuple[str, Path, dict]]] = {}
    for key, folder in meeting.versions(feature_root, problems).items():
        meta = meeting.read_json(folder / meeting.SOURCE) or {}
        by_stem.setdefault(key.rsplit("@", 1)[0], []).append((str(meta.get("acquired_at") or ""), folder, meta))
    if problems:
        raise MaterialError("会议版本有问题，索引算不出来：\n" + "\n".join(problems))
    out: list[dict] = []
    for stem, items in by_stem.items():
        for number, (at, folder, meta) in enumerate(sorted(items, key=lambda x: (x[0], x[1].name)), start=1):
            rel = folder.relative_to(feature_root).as_posix()
            raw = folder / meeting.RAW
            out.append({"source_id": f"meeting:{stem}", "kind": "meeting", "class": "MEETING",
                        "origin": {"file": meta.get("file")}, "version": number, "acquired_at": at or None, "dir": rel,
                        "original": {"path": f"{rel}/{meeting.ORIGINAL}", "sha256": str(meta.get("sha256"))},
                        "readable": {"path": f"{rel}/{meeting.RAW}", "sha256": file_digest(raw) or ""},
                        "images": [{"path": p.relative_to(feature_root).as_posix(), "sha256": file_digest(p)}
                                   for p in sorted((folder / meeting.MEDIA).glob("*")) if p.is_file()]})
    return out


def inbox_items(feature_root: Path) -> list[dict]:
    """收件箱里还没导入的件：键（相对收件箱）、内容摘要与类（没归类为 None）。"""
    inbox = importer.inbox_of(feature_root)
    try:
        classify = importer.read_classify(inbox)
        receipts = importer.read_receipts(inbox)
        files = importer.scan_sources(inbox)
    except importer.ImportError_ as exc:
        raise MaterialError(str(exc)) from exc
    return [{"file": importer.source_key(inbox, p), "sha256": file_digest(p),
             "class": importer.class_of(importer.source_key(inbox, p), classify, receipts)} for p in files]


def catalog(records: list[dict]) -> list[dict]:
    """按来源归组：每个来源的全部版本（旧版本留着可查）与最新取得的版本号。"""
    groups: dict[str, list[dict]] = {}
    for rec in records:
        groups.setdefault(rec["source_id"], []).append(rec)
    out = []
    for sid in sorted(groups):
        versions = sorted(groups[sid], key=lambda r: r["version"])
        last = versions[-1]
        out.append({"source_id": sid, "kind": last["kind"], "class": last.get("class"), "origin": last.get("origin") or {},
                    "latest_version": last["version"],
                    "versions": [{k: v[k] for k in ("version", "dir", "acquired_at", "original", "readable", "images") if k in v}
                                 for v in versions]})
    return out


def current(sources: list[dict]) -> list[dict]:
    """各来源最新取得的版本（带来源字段）。"""
    out = []
    for s in sources:
        last = s["versions"][-1]
        out.append({**last, "source_id": s["source_id"], "kind": s["kind"], "class": s["class"], "origin": s["origin"]})
    return out


def derive(latest: list[dict], notes: dict[str, dict], feature_root: Path) -> tuple[list[dict], list[dict], str]:
    """派生 `materials`、`origins` 与材料版本摘要。人答不进这三样。"""
    materials: list[dict] = []
    images: dict[str, dict] = {}
    origins: list[dict] = []
    payload = []
    for v in (x for x in latest if x["kind"] != "answer"):
        original, readable = v["original"], v["readable"]
        pictures = list(v["images"])
        if PurePosixPath(original["path"]).suffix.lower() in importer.IMAGE_EXTS:
            pictures.insert(0, original)
        if v["kind"] == "meeting":
            # 会议的身份只认原件：转换件、阅读件与结论都是读会的产物，算进来的话读一次会就开一轮
            payload.append([v["source_id"], original["sha256"]])
            materials.append({"kind": "meeting", "paths": [original["path"]], "sha256": original["sha256"],
                              "source_id": v["source_id"]})
            folder = PurePosixPath(original["path"]).parent
            readable_paths = [f"{folder}/{n}" for n in (meeting.RAW, meeting.EVIDENCE) if (feature_root / folder / n).is_file()]
            origins.append({"path": original["path"], "sha256": original["sha256"], "kind": "meeting",
                            "readable_paths": readable_paths, "source_id": v["source_id"], "version": v["version"]})
            continue
        payload.append([v["source_id"], original["sha256"], (readable or {}).get("sha256"),
                        sorted(p["sha256"] for p in pictures)])
        if readable or v["class"] == "IMAGES":
            materials.append({"kind": "doc", "paths": sorted({original["path"], *([readable["path"]] if readable else [])}),
                              "sha256": (readable or original)["sha256"], "source_id": v["source_id"]})
            row = {"path": original["path"], "sha256": original["sha256"], "kind": v["kind"], "class": v["class"],
                   "readable_paths": [readable["path"]] if readable else [original["path"]],
                   "source_id": v["source_id"], "version": v["version"]}
            if v["class"] == "IMAGES":
                row["image_paths"] = [p["path"] for p in v["images"]]
            origins.append(row)
        for p in pictures:
            found = images.get(p["sha256"])
            if found:
                found["paths"].append(p["path"])
            else:
                note = notes.get(p["sha256"], {})
                images[p["sha256"]] = {"kind": "image", "paths": [p["path"]], "sha256": p["sha256"],
                                       "caption": note.get("caption", ""), "unused": note.get("unused", "")}
    for img in images.values():
        img["paths"].sort()
    materials = sorted(materials, key=lambda m: m["paths"][0]) + sorted(images.values(), key=lambda m: m["paths"][0])
    body = json.dumps(sorted(payload, key=lambda r: r[0]), ensure_ascii=False)
    return materials, sorted(origins, key=lambda o: o["path"]), "sha256:" + sha256(body.encode("utf-8")).hexdigest()[:16]


def build(feature_root: Path, notes: dict[str, dict] | None = None, records: list[dict] | None = None) -> dict:
    """按磁盘现状算出完整索引。不写盘。"""
    if notes is None:
        notes = read_notes(feature_root)
    if records is None:
        records = version_records(feature_root)
    meetings = meeting_records(feature_root)
    sources = catalog(records + meetings)
    materials, origins, digest = derive(current(sources), notes, feature_root)
    return {"schema": SCHEMA, "feature": feature_root.name, "digest": digest, "sources": sources,
            "inbox": inbox_items(feature_root), "materials": materials, "origins": origins,
            "files": files_view(feature_root, records, meetings), "notes": {k: notes[k] for k in sorted(notes)}}


def files_view(feature_root: Path, records: list[dict], meetings: list[dict]) -> list[dict]:
    """全部登记文件 → 来源身份、版本、角色与完整摘要（路径相对需求目录）。

    角色：`text` 可读的正文（文本原件或转换/阅读投影）、`original` 另有阅读稿的原件、`image` 图、
    人答的 `answer`（answers.md）与 `answer_record`（answers.json）、会议的 `raw`、`corrections`、`evidence`。
    会议的纠偏与阅读件是读会产物：纠偏能应用到原文、阅读件与纠偏结果逐字相同才列，不对改过的阅读件重算摘要放行。
    """
    rows: list[dict] = []

    def add(path: str, rec: dict, role: str, sha: str) -> None:
        rows.append({"path": path, "source_id": rec["source_id"], "version": rec["version"], "kind": rec["kind"],
                     "role": role, "sha256": sha, "dir": rec["dir"]})

    for rec in records:
        answer = rec["kind"] == "answer"
        readable, original = rec.get("readable"), rec["original"]
        split = bool(readable) and readable["path"] != original["path"]
        role = ("answer_record" if answer else "original" if split or not readable and rec.get("class") == "IMAGES"
                else "image" if not readable else "text")
        add(original["path"], rec, role, original["sha256"])
        if split:
            add(readable["path"], rec, "answer" if answer else "text", readable["sha256"])
        for image in rec.get("images") or []:
            add(image["path"], rec, "image", image["sha256"])
    for rec in meetings:
        folder = feature_root / rec["dir"]
        add(rec["original"]["path"], rec, "original", rec["original"]["sha256"])
        lines, broken = meeting.raw_lines(folder)
        if not broken:
            add(f"{rec['dir']}/{meeting.RAW}", rec, "raw", rec["readable"]["sha256"])
            corrections = meeting.read_json(folder / meeting.CORRECTIONS) if (folder / meeting.CORRECTIONS).is_file() else None
            if corrections is not None:
                fixed, bad = meeting.apply_corrections(lines, corrections)
                if not bad:
                    add(f"{rec['dir']}/{meeting.CORRECTIONS}", rec, "corrections", file_digest(folder / meeting.CORRECTIONS))
                    if (folder / meeting.EVIDENCE).is_file() and not meeting.evidence_stale(folder, fixed):
                        add(f"{rec['dir']}/{meeting.EVIDENCE}", rec, "evidence", file_digest(folder / meeting.EVIDENCE))
        for image in rec.get("images") or []:
            add(image["path"], rec, "image", image["sha256"])
    return sorted(rows, key=lambda r: r["path"])


def path_of(feature_root: Path) -> Path:
    return feature_root / Path(*MANIFEST)


def refuse_old(data) -> None:
    """旧版生成的索引：本版不接续、不借刷新改写成新结构，这个需求目录原样保留。"""
    if isinstance(data, dict) and isinstance(data.get("schema"), int) and data["schema"] < SCHEMA:
        raise MaterialError(
            f"{'/'.join(MANIFEST)} 的 schema 为 {data['schema']}，本版要求 {SCHEMA}：这是旧版生成的需求，本版不接续它。"
            "本版只从新需求初始化：另建一个新需求，这个目录原样保留")


def read_notes(feature_root: Path) -> dict[str, dict]:
    """索引里已有的图片说明与取舍。还没有索引是空的；索引坏了报出来——当成没写过会丢掉作者已经给的说明。"""
    path = path_of(feature_root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise MaterialError(f"{'/'.join(MANIFEST)} 不是合法 JSON（{exc}）：图片说明记在它里面，"
                            "按 Git 或备份找回上一版再刷新；确认放弃说明就删掉它重跑 `story_flow.py round`") from exc
    refuse_old(data)
    notes = data.get("notes") if isinstance(data, dict) else None
    if not isinstance(notes, dict):
        return {}
    return {str(k): {f: v[f] for f in NOTE_FIELDS if isinstance(v, dict) and isinstance(v.get(f), str) and v[f].strip()}
            for k, v in notes.items() if isinstance(v, dict) and any(isinstance(v.get(f), str) and v[f].strip() for f in NOTE_FIELDS)}


def write_note(feature_root: Path, sha: str, field: str, value: str | None) -> None:
    """只动一张图的一个字段，另一个原样留着：改说明不抹掉「为什么不用」，标记不用也不抹掉说明。"""
    notes = read_notes(feature_root)
    entry = dict(notes.get(sha, {}))
    if value is None:
        entry.pop(field, None)
    else:
        entry[field] = value
    if entry:
        notes[sha] = entry
    else:
        notes.pop(sha, None)
    write(feature_root, build(feature_root, notes))


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def write(feature_root: Path, manifest: dict) -> Path:
    path = path_of(feature_root)
    _atomic_write(path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    _atomic_write(feature_root.joinpath(*README), render_readme(manifest))
    return path


def render_readme(manifest: dict) -> str:
    """来源导航：每个来源一行，链到最新版本的原件与阅读稿；旧版本与待导入件列在后面。不复制需求正文，不记采用。"""
    rel = lambda p: str(PurePosixPath(p).relative_to(importer.SOURCES)) if str(p).startswith(f"{importer.SOURCES}/") \
        else f"../{p}"
    link = lambda p: f"[{PurePosixPath(p).name}](<{rel(p)}>)"
    lines = ["# 来源材料", "",
             "这一页由导入命令按材料索引 `AR/story-src/materials.json` 生成，手改会在下次导入时被覆盖。"
             "最新版本不等于设计已采用：设计实际依据哪个版本，看蓝图的范围条目。", "",
             "| 来源 | 类 | 取得方式 | 最新版本 | 原件 | 阅读稿 | 图 |", "|---|---|---|---|---|---|---|"]
    for s in manifest.get("sources", []):
        v = s["versions"][-1]
        name = s["origin"].get("title") or s["origin"].get("ticket") or s["origin"].get("inbox_path") \
            or s["origin"].get("file") or s["source_id"]
        lines.append(f"| {name} | {s.get('class') or ''} | {KIND_LABEL.get(s['kind'], s['kind'])} | v{v['version']}"
                     f"{'（' + str(v.get('acquired_at')) + '）' if v.get('acquired_at') else ''} | {link(v['original']['path'])} | "
                     f"{link(v['readable']['path']) if v.get('readable') else '—'} | {len(v.get('images') or [])} |")
    older = [(s, v) for s in manifest.get("sources", []) for v in s["versions"][:-1]]
    if older:
        lines += ["", "## 旧版本", ""] + [f"- {s['source_id']} v{v['version']}：{link(v['original']['path'])}" for s, v in older]
    if manifest.get("inbox"):
        lines += ["", "## 待导入", ""] + [f"- `inbox/{i['file']}`" + ("" if i.get("class") else "（未归类）")
                                        for i in manifest["inbox"]]
    return "\n".join(lines) + "\n"


def refresh(feature_root: Path) -> dict:
    """算一遍并落盘 —— 机制层命令唯一该调的入口。有效人答有变化时先导出新版本。"""
    notes = read_notes(feature_root)
    records = version_records(feature_root)
    try:
        if answers.export(feature_root, records):
            records = version_records(feature_root)
    except OSError as exc:
        raise MaterialError(f"有效人答导出失败（{exc}）：排除写入故障后重跑") from exc
    except answers.AnswerError as exc:
        raise MaterialError(str(exc)) from exc
    manifest = build(feature_root, notes, records)
    write(feature_root, manifest)
    return manifest


def read(feature_root: Path) -> dict:
    """读已落盘的索引。没有索引和索引坏了都不是「没有材料」，都要报出来。"""
    path = path_of(feature_root)
    name = "/".join(MANIFEST)
    if not path.is_file():
        raise MaterialError(f"{name} 不存在：材料索引由 `story_flow.py round` 生成，先跑它")
    try:
        data = json.loads(path.read_text(encoding="utf-8").lstrip("﻿"))
    except ValueError as exc:
        raise MaterialError(f"{name} 不是合法 JSON（{exc}）：它只应由脚本写入；图片说明记在它里面，"
                            "按 Git 找回上一版，或删掉后重跑 `story_flow.py round` 重建（说明需重写）") from exc
    refuse_old(data)
    problems = _shape_problems(data)
    if problems:
        raise MaterialError(f"{name} 结构不对（{'；'.join(problems)}）：它只应由脚本写入，"
                            "删掉后重跑 `story_flow.py round` 按磁盘现状重建")
    return data


def _shape_problems(data) -> list[str]:
    """当前 schema 的索引缺了或写坏了哪些字段。一次列全，不在第一处就停。"""
    if not isinstance(data, dict):
        return ["顶层应是对象"]
    problems = [] if data.get("schema") == SCHEMA else [f"schema 为 {data.get('schema')}，本版是 {SCHEMA}"]
    for field in ("sources", "inbox", "materials", "origins", "files"):
        if not isinstance(data.get(field), list):
            problems.append(f"缺 {field} 列表")
    for i, o in enumerate(data.get("origins") if isinstance(data.get("origins"), list) else []):
        if not (isinstance(o, dict) and isinstance(o.get("path"), str)
                and o.get("kind") in KINDS and isinstance(o.get("readable_paths"), list)):
            problems.append(f"origins 第 {i + 1} 项应有 path、kind（{'/'.join(KINDS)}）与 readable_paths")
    return problems


def pending(manifest: dict) -> list[str]:
    """收件箱里还没导入的件（相对收件箱的键）。空表示没有新料。"""
    return [i["file"] for i in manifest.get("inbox", [])]


def latest_of(manifest: dict, cls: str, kind: str | None = None) -> list[dict]:
    """某一类来源各自最新取得的版本（如系统取得的 RR 正文）；给按角色找正文的读者用。"""
    return [{**s["versions"][-1], "source_id": s["source_id"], "kind": s["kind"], "origin": s["origin"]}
            for s in manifest.get("sources", []) if s.get("class") == cls and (kind is None or s["kind"] == kind)]
