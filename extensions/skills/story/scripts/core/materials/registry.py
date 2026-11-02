"""材料索引（`AR/story-src/materials.json`）：来源版本关系的唯一登记，也是它的唯一写入者。

索引回答：这个需求手里有哪些**来源**、每个来源取得过哪些**版本**（原件、阅读稿与图的完整摘要）、
收件箱里还有哪些件没导入、当前阅读稿由哪几份原件合成、每张图是什么、本需求用不用它。它**不回答**设计采用了哪个版本——
那由原生蓝图的范围条目记录；最新取得的版本不等于设计已采用。

## 登记什么，从哪里来

- 导入的版本（`materials/importer.py` 写进来）：原件按 1.9.9 留在 `inbox/`，每个版本的原件字节另存一份在
  `.backups/local/inbox/<原相对目录>/<主名>.<内容摘要><后缀>`，转换出的阅读稿存 `.backups/local/<类>/<标签>-v<N>.md`，
  图按内容身份存 `assets/`；版本登记只在这里，之后不改；
- 直接给在 `RR/prd.md`、`SR/design.md`、`AR/design.md` 的原文（不是导入生成的）：第一次见到时登记原字节，之后改了算待导入，
  由导入登记成新版本——刷新不替人把改过的内容记成「没变」；
- 当前阅读稿（`drafts`）：导入按各类来源的最新版本拼成，登记合成它的版本；
- 会议版本 `AR/story-src/meetings/<主名>/<sha8>/`：版本目录里还有读会产物，身份取原件（`materials/meeting.py`），按磁盘现状算；
- 有效人答：从流程契约导出成 `AR/story-src/answers/人工答复-v<N>.*`（`materials/answers.py`），有变化才出新版本；
- 图片说明与取舍记在 `notes` 里，按图的内容摘要键。

已登记的每份文件逐份核摘要：缺了或字节变了是损坏，报出原路径。收件箱里的原件可以被人换掉——那是待导入，不是损坏。

## 派生视图

- `materials`：各来源最新版本的正文与图（图按内容合并成一条，`paths` 列全部落点，带 `caption`/`unused`）；
- `origins`：各来源最新版本的原件与它的阅读稿——作者材料表、审查任务与独立审查对象读同一份；人答不在其中；
- `digest`：**材料版本**，按最新版本的原件、阅读稿与图的内容算。人答、说明与取舍不进摘要；
- `files`：全部登记文件（各来源的每个版本、当前阅读稿与仍是最新版本的收件箱原件）→ 来源、版本、角色与完整摘要；
  当前阅读稿带 `components`（合成它的版本）。需求条目补来源、设计采用与审查核源都按它认文件。

只用标准库。stdout 无输出：本模块是库，不是命令。
"""
from __future__ import annotations

import json
import os
import uuid
from hashlib import sha256
from pathlib import Path, PurePosixPath

from materials import answers, importer, meeting

SCHEMA = 4
KINDS = ("system", "local", "direct", "meeting", "answer")
MANIFEST = ("AR", "story-src", "materials.json")
NOTE_FIELDS = ("caption", "unused")


class MaterialError(Exception):
    """可预期的失败：材料索引算不出来。带可执行的补救动作，直接呈给人。"""


def file_digest(path: Path) -> str | None:
    """完整 SHA-256；不存在记 None——「没有」和「没查」是两件事。"""
    if not path.is_file():
        return None
    return sha256(path.read_bytes()).hexdigest()


def path_of(feature_root: Path) -> Path:
    return feature_root / Path(*MANIFEST)


def refuse_old(data) -> None:
    """旧版生成的索引：本版不接续、不借刷新改写成新结构，这个需求目录原样保留。"""
    if isinstance(data, dict) and isinstance(data.get("schema"), int) and data["schema"] != SCHEMA:
        raise MaterialError(
            f"{'/'.join(MANIFEST)} 的 schema 为 {data['schema']}，本版要求 {SCHEMA}：这是别的版本生成的需求，本版不接续它。"
            "本版只从新需求初始化：另建一个新需求，这个目录原样保留")


def load(feature_root: Path) -> dict:
    """已登记的部分：来源版本（会议除外）、当前阅读稿与图片说明。还没有索引是空的；坏了报出来——
    版本关系只登记在这里，当成空的会把已有版本当成没取得过。"""
    path = path_of(feature_root)
    if not path.is_file():
        return {"sources": [], "drafts": {}, "notes": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise MaterialError(f"{'/'.join(MANIFEST)} 不是合法 JSON（{exc}）：材料版本关系只登记在它里面，"
                            "按 Git 或备份找回上一版再继续，不要删掉它重建") from exc
    refuse_old(data)
    problems = _shape_problems(data, stored=True)
    if problems:
        raise MaterialError(f"{'/'.join(MANIFEST)} 结构不对（{'；'.join(problems)}）：它只应由脚本写入，按 Git 或备份找回上一版")
    notes = data.get("notes") if isinstance(data.get("notes"), dict) else {}
    return {"sources": [s for s in data["sources"] if s.get("kind") != "meeting"],
            "drafts": data.get("drafts") if isinstance(data.get("drafts"), dict) else {},
            "notes": {str(k): {f: v[f] for f in NOTE_FIELDS if isinstance(v.get(f), str) and v[f].strip()}
                      for k, v in notes.items() if isinstance(v, dict)
                      and any(isinstance(v.get(f), str) and v[f].strip() for f in NOTE_FIELDS)}}


def read_notes(feature_root: Path) -> dict[str, dict]:
    return load(feature_root)["notes"]


def records(stored: dict) -> list[dict]:
    """已登记版本平铺成记录（带来源字段），按来源与版本排序。"""
    return [{**v, "source_id": s["source_id"], "kind": s["kind"], "class": s.get("class"), "origin": s.get("origin") or {}}
            for s in stored["sources"] for v in s["versions"]]


def verify(feature_root: Path, stored: dict) -> None:
    """登记的每份文件都按摘要核：缺了或字节变了是损坏，问题一次列全，不重填摘要放行。"""
    problems: list[str] = []
    for rec in records(stored):
        for f in [rec["original"], *([rec["readable"]] if rec.get("readable") else []), *(rec.get("images") or [])]:
            have = file_digest(feature_root / f["path"])
            if have is None:
                problems.append(f"{f['path']} 不在了：它是已登记版本 {rec['source_id']} v{rec['version']} 的文件")
            elif have != f["sha256"]:
                problems.append(f"{f['path']} 的字节与版本登记不一致（登记 {f['sha256'][:12]}…，现在 {have[:12]}…）："
                                "已登记版本的留存不改，内容变了要作为新原件重新导入")
    if problems:
        raise MaterialError("材料版本有问题，索引算不出来：\n" + "\n".join(problems))


def add_version(stored: dict, ident: dict, version: dict) -> None:
    """登记一个新版本（导入与直接原文首登调它）；来源第一次出现时一并登记来源。"""
    source = next((s for s in stored["sources"] if s["source_id"] == ident["source_id"]), None)
    if source is None:
        source = {"source_id": ident["source_id"], "kind": ident["kind"], "class": ident.get("class"),
                  "origin": ident.get("origin") or {}, "label": ident["label"], "versions": []}
        stored["sources"].append(source)
    else:
        source["origin"] = ident.get("origin") or source.get("origin") or {}
        source["class"] = ident.get("class") or source.get("class")
    source["versions"].append(version)
    stored["sources"].sort(key=lambda s: s["source_id"])


def latest(stored: dict, source_id: str) -> dict | None:
    source = next((s for s in stored["sources"] if s["source_id"] == source_id), None)
    return source["versions"][-1] if source and source["versions"] else None


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


def imported(stored: dict, key: str, cls: str | None, sha: str, source_id: str) -> bool:
    """收件箱里这份件已经并入了没有：本地件看它来源的最新版本是不是这份字节、这个类；
    取材批次里的件看它是不是最新版本的字节，或者有没有哪个版本就是从这个位置取得的这份字节
    （批次各占一个目录，旧批次留着不算新料；系统上改回了旧内容，最新一次取得的就是新版本）。"""
    if source_id.startswith("local:"):
        last = latest(stored, source_id)
        source = next((s for s in stored["sources"] if s["source_id"] == source_id), None)
        return bool(last and last["original"]["sha256"] == sha and (source or {}).get("class") == cls)
    last = latest(stored, source_id)
    return bool(last and last["original"]["sha256"] == sha) or any(
        v.get("inbox_path") == key and v["original"]["sha256"] == sha
        for s in stored["sources"] if s["source_id"] == source_id for v in s["versions"])


def inbox_items(feature_root: Path, stored: dict) -> list[dict]:
    """还没导入的件：收件箱里没并入的原件，与直接改过的当前阅读稿或原文。只比摘要，不转换。"""
    inbox = importer.inbox_of(feature_root)
    try:
        receipts = importer.read_receipts(inbox)
        files = importer.scan_sources(inbox)
        classify = {**importer.known_classes(stored, inbox, files), **importer.read_classify(inbox)}
    except importer.ImportError_ as exc:
        raise MaterialError(str(exc)) from exc
    out = []
    for p in files:
        key = importer.source_key(inbox, p)
        cls = importer.class_of(key, classify, receipts)
        sha = file_digest(p)
        if cls == "MEETING":
            if meeting.saved(feature_root, p):
                continue
        elif cls is not None and imported(stored, key, cls, sha, importer.identify(inbox, p, cls, receipts)["source_id"]):
            continue
        out.append({"file": key, "path": f"{importer.INBOX[-1]}/{key}", "sha256": sha, "class": cls})
    for rel, sha, why in direct_changes(feature_root, stored):
        out.append({"file": rel, "path": rel, "sha256": sha, "class": importer.DIRECT[rel], "direct": why})
    return out


def direct_changes(feature_root: Path, stored: dict) -> list[tuple[str, str, str]]:
    """直接改过的当前稿：(路径, 现在的摘要, 原因)。生成后被人改过的阅读稿、登记过又改了的直接原文都算；
    还没登记过的直接原文不算——它在刷新时首次登记。"""
    out = []
    for rel in importer.DIRECT:
        sha = file_digest(feature_root / rel)
        if sha is None:
            continue
        draft = stored["drafts"].get(rel)
        last = latest(stored, f"direct:{rel}")
        if (draft and draft["sha256"] == sha) or (last and last["original"]["sha256"] == sha):
            continue
        if draft or last:
            out.append((rel, sha, "生成后被直接改过" if draft and not last else "直接原文改过"))
    return out


def catalog(recs: list[dict], stored_sources: list[dict]) -> list[dict]:
    """按来源归组：每个来源的全部版本（旧版本留着可查）与最新取得的版本号。"""
    labels = {s["source_id"]: s.get("label") for s in stored_sources}
    groups: dict[str, list[dict]] = {}
    for rec in recs:
        groups.setdefault(rec["source_id"], []).append(rec)
    out = []
    for sid in sorted(groups):
        versions = sorted(groups[sid], key=lambda r: r["version"])
        last = versions[-1]
        row = {"source_id": sid, "kind": last["kind"], "class": last.get("class"), "origin": last.get("origin") or {},
               "latest_version": last["version"],
               "versions": [{k: v[k] for k in ("version", "dir", "acquired_at", "inbox_path", "original", "readable", "images")
                             if k in v} for v in versions]}
        if labels.get(sid):
            row["label"] = labels[sid]
        out.append(row)
    return out


def current(sources: list[dict]) -> list[dict]:
    """各来源最新取得的版本（带来源字段）。"""
    return [{**s["versions"][-1], "source_id": s["source_id"], "kind": s["kind"], "class": s["class"], "origin": s["origin"]}
            for s in sources]


def _here(feature_root: Path, v: dict) -> str | None:
    """这一版的原件此刻还原样在原处（收件箱里的原件、直接给的原文）：给人读时指它，不指留存副本。"""
    rel = (f"{importer.INBOX[-1]}/{v['inbox_path']}" if v.get("inbox_path")
           else (v.get("origin") or {}).get("file") if v.get("kind") == "direct" else None)
    return rel if rel and file_digest(feature_root / rel) == v["original"]["sha256"] else None


def derive(latest_versions: list[dict], drafts: dict, notes: dict[str, dict], feature_root: Path
           ) -> tuple[list[dict], list[dict], str]:
    """派生 `materials`、`origins` 与材料版本摘要。人答不进这三样。

    `origins` 一行一份原件：原件此刻还在收件箱原样就指它，否则指留存；阅读稿是它所在的当前阅读稿（合成它的那一份），
    没有当前阅读稿时是它自己的阅读稿。
    """
    in_draft = {c: rel for rel, d in drafts.items() if file_digest(feature_root / rel) == d["sha256"]
                for c in d.get("components") or []}
    materials: list[dict] = []
    images: dict[str, dict] = {}
    origins: list[dict] = []
    payload = []
    for v in (x for x in latest_versions if x["kind"] != "answer"):
        original, readable = v["original"], v.get("readable")
        pictures = list(v.get("images") or [])
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
        here = _here(feature_root, v)
        shown = here or original["path"]
        draft = in_draft.get(f"{v['source_id']}@{v['version']}")
        if readable or v["class"] == "IMAGES":
            # 读的是合成它的当前阅读稿；没有就是它自己的阅读稿（原件本身就是阅读稿、又还在原处时指原处）
            reading = ([draft] if draft else [] if not readable
                       else [here] if here and (readable["path"] == original["path"] or v["kind"] == "direct")
                       else [readable["path"]]) or [shown]
            materials.append({"kind": "doc", "paths": sorted({original["path"], *([readable["path"]] if readable else [])}),
                              "sha256": (readable or original)["sha256"], "source_id": v["source_id"]})
            row = {"path": shown, "sha256": original["sha256"], "kind": v["kind"], "class": v["class"],
                   "readable_paths": reading, "source_id": v["source_id"], "version": v["version"]}
            if v["class"] == "IMAGES":
                row["image_paths"] = [p["path"] for p in v.get("images") or []]
            origins.append(row)
        for p in pictures:
            found = images.get(p["sha256"])
            if found:
                if p["path"] not in found["paths"]:
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


def files_view(feature_root: Path, recs: list[dict], meetings: list[dict], drafts: dict) -> list[dict]:
    """全部登记文件 → 来源身份、版本、角色与完整摘要（路径相对需求目录）。

    角色：`text` 可读的正文（文本原件或转换/阅读投影）、`original` 另有阅读稿的原件、`image` 图、
    人答的 `answer`（answers.md）与 `answer_record`（answers.json）、会议的 `raw`、`corrections`、`evidence`。
    最新版本的原件还原样在收件箱（或直接原文还在原处）时，那个位置也是这一版的文件；当前阅读稿与合成它的版本一致时列出，
    带 `components`。会议的纠偏与阅读件核过同源才列。
    """
    rows: list[dict] = []
    latest_of = {}
    for rec in recs:
        if rec["version"] >= latest_of.get(rec["source_id"], 0):
            latest_of[rec["source_id"]] = rec["version"]

    def add(path: str, rec: dict, role: str, sha: str) -> None:
        rows.append({"path": path, "source_id": rec["source_id"], "version": rec["version"], "kind": rec["kind"],
                     "role": role, "sha256": sha, "dir": rec["dir"]})

    for rec in recs:
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
        if rec["version"] == latest_of[rec["source_id"]]:
            here = _here(feature_root, rec)
            if here and here != original["path"]:
                add(here, rec, role, original["sha256"])
    for rel, d in sorted(drafts.items()):
        if file_digest(feature_root / rel) == d["sha256"]:
            rows.append({"path": rel, "source_id": f"draft:{rel}", "version": 1, "kind": "draft", "role": "text",
                         "sha256": d["sha256"], "dir": rel, "components": list(d.get("components") or [])})
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
    return sorted(rows, key=lambda r: (r["path"], r["source_id"]))


def build(feature_root: Path, stored: dict | None = None) -> dict:
    """按登记与磁盘现状算出完整索引。不写盘。"""
    if stored is None:
        stored = load(feature_root)
    verify(feature_root, stored)
    recs = records(stored)
    meetings = meeting_records(feature_root)
    sources = catalog(recs + meetings, stored["sources"])
    materials, origins, digest = derive(current(sources), stored["drafts"], stored["notes"], feature_root)
    return {"schema": SCHEMA, "feature": feature_root.name, "digest": digest, "sources": sources,
            "drafts": {k: stored["drafts"][k] for k in sorted(stored["drafts"])},
            "inbox": inbox_items(feature_root, stored), "materials": materials, "origins": origins,
            "files": files_view(feature_root, recs, meetings, stored["drafts"]),
            "notes": {k: stored["notes"][k] for k in sorted(stored["notes"])}}


def write_note(feature_root: Path, sha: str, field: str, value: str | None) -> None:
    """只动一张图的一个字段，另一个原样留着：改说明不抹掉「为什么不用」，标记不用也不抹掉说明。"""
    stored = load(feature_root)
    entry = dict(stored["notes"].get(sha, {}))
    if value is None:
        entry.pop(field, None)
    else:
        entry[field] = value
    if entry:
        stored["notes"][sha] = entry
    else:
        stored["notes"].pop(sha, None)
    write(feature_root, build(feature_root, stored))


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def write(feature_root: Path, manifest: dict) -> Path:
    path = path_of(feature_root)
    atomic_write(path, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return path


def refresh(feature_root: Path) -> dict:
    """算一遍并落盘 —— 机制层命令唯一该调的入口。有效人答有变化时先导出新版本；直接给在 RR/SR/AR 的原文第一次见到时登记。"""
    stored = load(feature_root)
    verify(feature_root, stored)
    try:
        importer.register_direct(feature_root, stored)
        answers.export(feature_root, stored)
    except OSError as exc:
        raise MaterialError(f"材料登记写入失败（{exc}）：排除写入故障后重跑") from exc
    except answers.AnswerError as exc:
        raise MaterialError(str(exc)) from exc
    except importer.ImportError_ as exc:
        raise MaterialError(str(exc)) from exc
    manifest = build(feature_root, stored)
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
        raise MaterialError(f"{name} 不是合法 JSON（{exc}）：它只应由脚本写入，按 Git 或备份找回上一版") from exc
    refuse_old(data)
    problems = _shape_problems(data)
    if problems:
        raise MaterialError(f"{name} 结构不对（{'；'.join(problems)}）：它只应由脚本写入，按 Git 或备份找回上一版")
    return data


def _shape_problems(data, stored: bool = False) -> list[str]:
    """当前 schema 的索引缺了或写坏了哪些字段。一次列全，不在第一处就停。`stored` 只核登记部分。"""
    if not isinstance(data, dict):
        return ["顶层应是对象"]
    problems = [] if data.get("schema") == SCHEMA else [f"schema 为 {data.get('schema')}，本版是 {SCHEMA}"]
    for field in ("sources",) if stored else ("sources", "inbox", "materials", "origins", "files"):
        if not isinstance(data.get(field), list):
            problems.append(f"缺 {field} 列表")
    for i, s in enumerate(data.get("sources") if isinstance(data.get("sources"), list) else []):
        versions = s.get("versions") if isinstance(s, dict) else None
        if not (isinstance(s, dict) and isinstance(s.get("source_id"), str) and s.get("kind") in KINDS
                and isinstance(versions, list) and all(_version_ok(v) for v in versions)):
            problems.append(f"sources 第 {i + 1} 项应有 source_id、kind（{'/'.join(KINDS)}）与每项带 version、original 的 versions")
    if not stored:
        for i, o in enumerate(data.get("origins") if isinstance(data.get("origins"), list) else []):
            if not (isinstance(o, dict) and isinstance(o.get("path"), str)
                    and o.get("kind") in KINDS and isinstance(o.get("readable_paths"), list)):
                problems.append(f"origins 第 {i + 1} 项应有 path、kind（{'/'.join(KINDS)}）与 readable_paths")
    return problems


def _version_ok(v) -> bool:
    files = [v.get("original"), *([v.get("readable")] if isinstance(v, dict) and v.get("readable") is not None else []),
             *(v.get("images") if isinstance(v, dict) and isinstance(v.get("images"), list) else [])] if isinstance(v, dict) else [None]
    return (isinstance(v, dict) and isinstance(v.get("version"), int) and v["version"] >= 1
            and all(isinstance(f, dict) and isinstance(f.get("path"), str) and isinstance(f.get("sha256"), str) for f in files))


def pending(manifest: dict) -> list[str]:
    """还没导入的件（相对需求目录的位置）。空表示没有新料。"""
    return [i["path"] for i in manifest.get("inbox", [])]


def latest_of(manifest: dict, cls: str, kind: str | None = None) -> list[dict]:
    """某一类来源各自最新取得的版本（如系统取得的 RR 正文）；给按角色找正文的读者用。"""
    return [{**s["versions"][-1], "source_id": s["source_id"], "kind": s["kind"], "origin": s["origin"]}
            for s in manifest.get("sources", []) if s.get("class") == cls and (kind is None or s["kind"] == kind)]
