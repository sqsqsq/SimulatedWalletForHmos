"""会议材料：版本留存、原文定位、纠偏差异应用与读会产物自检。

**内容由模型理解，脚本不猜语义单元**：谁在发言、哪一段是议题、哪句话是结论，由读会的模型
判断并写进自己的产物。脚本只做确定的四件事——按版本留住原件与转换文本、把模型给的逐行
差异应用成阅读件、核对引用是否指得到真实的行、核对结构立不立得住。

**一个源版本一个目录**（`AR/story-src/meetings/<docx 主名>/<原件 sha8>/`）::

    original.docx      导入时复制的原件；收件箱里同名被换掉，旧引用仍查得回原文
    source.json        {"file": 原文件名, "sha256": 原件完整摘要, "text_sha256": raw.md 摘要}
    raw.md             未纠偏的转换文本，引用的基底
    corrections.json   模型写：逐行字面纠偏 [{"line", "original", "corrected", "basis"}]
    evidence.md        脚本按差异生成的阅读件，行号与 raw.md 一一对应
    topics.json        模型写：话题索引 [{"id", "title", "evidence": [{"start", "end"}]}]

材料身份是**原件**：同名换了内容就是新版本、新目录；已经存过的版本原样复用，转换器升级
不重算旧版——旧结论引的那几行永远指得回同一段字。

引用一律是 raw.md 的行范围 `{"start": 12, "end": 15}`（1 起、首尾包含），给人看时渲成
`AR/story-src/meetings/<主名>/<sha8>/raw.md:L12-L15`。不另编发言号：编号等于脚本替模型
划语义单元。

会议结论 `AR/story-src/meeting-notes.json` 按 `<主名>@<sha8>` 分节，形状见
`phases/meeting-read.md`。自检只核结构、引用与留痕，不判意思：纠偏改没改意思、话题漏没漏、
结论有没有写出会上没说的，归独立审查。

只用标准库，stdout 无输出。
"""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from materials import importer

MEETINGS = ("AR", "story-src", "meetings")
NOTES = ("AR", "story-src", "meeting-notes.json")
ORIGINAL, SOURCE, RAW = "original.docx", "source.json", "raw.md"
CORRECTIONS, EVIDENCE, TOPICS = "corrections.json", "evidence.md", "topics.json"
#: 文档内嵌图跟着版本走，raw.md 里按 `media/<名>` 引用
MEDIA = "media"
OWNERSHIP = ("ours", "not_ours", "unclear")
#: 值得问人的原因：归属判不准、没收敛、转写存疑、高影响修正、推翻已确认的决定
ASK_REASONS = ("unclear_ownership", "unresolved", "transcript_doubt", "high_impact", "overturns")


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def version_dir(feature_root: Path, docx: Path) -> Path:
    """这份 docx 这一版的落点：主名 + 原件内容指纹前 8 位。"""
    return feature_root.joinpath(*MEETINGS, docx.stem, digest(docx.read_bytes())[:8])


def versions(feature_root: Path) -> dict[str, Path]:
    """盘上每个会议版本：`<主名>@<sha8>` → 版本目录。"""
    base = feature_root.joinpath(*MEETINGS)
    return {f"{p.parent.parent.name}@{p.parent.name}": p.parent
            for p in sorted(base.glob(f"*/*/{SOURCE}"))}


def save_version(feature_root: Path, docx: Path, markdown: str,
                 media: dict[str, bytes] | None = None) -> tuple[Path, bool]:
    """留住这一版：原件、转换文本与来源登记。返回 (版本目录, 是不是这次新建的)。

    已经存过就原样复用——转换器升级不重算旧版本，否则旧结论引的行号会跟着漂。
    短摘要撞车而完整摘要不同时报错，不覆盖：两份不同的原件挤进同一个目录，
    先到的那份原文就没了。
    """
    folder = version_dir(feature_root, docx)
    sha = digest(docx.read_bytes())
    known = read_json(folder / SOURCE)
    if isinstance(known, dict) and known.get("sha256"):
        if known["sha256"] != sha:
            raise importer.ImportError_(
                f"「{docx.name}」这一版的目录 {folder.name} 里已经是另一份原件"
                f"（{known.get('file')}，摘要 {known['sha256'][:12]}…）："
                "两份内容不同的原件短摘要撞了车。把其中一份改个文件名再导")
        return folder, False
    text = markdown if markdown.endswith("\n") else markdown + "\n"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ORIGINAL).write_bytes(docx.read_bytes())
    for name, blob in (media or {}).items():
        # 文档里的图跟着这一版走：raw.md 按 `media/<名>` 引它，引用与原文同一个目录
        (folder / MEDIA).mkdir(parents=True, exist_ok=True)
        (folder / MEDIA / name).write_bytes(blob)
    (folder / RAW).write_text(text, encoding="utf-8", newline="\n")
    (folder / SOURCE).write_text(json.dumps(
        {"file": docx.name, "sha256": sha, "text_sha256": digest(text.encode("utf-8"))},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return folder, True


def saved(feature_root: Path, docx: Path) -> bool:
    """这一版留过没有——收件箱里那份原件的身份说了算。"""
    known = read_json(version_dir(feature_root, docx) / SOURCE)
    return isinstance(known, dict) and known.get("sha256") == digest(docx.read_bytes())


def read_json(path: Path, problems: list[str] | None = None):
    """读一份 JSON：不在返回 None；坏了记一条问题也返回 None——坏的不当成没写。"""
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError:
        return None
    except ValueError as exc:
        if problems is not None:
            problems.append(f"{path.parent.name}/{path.name} 不是合法 JSON：{exc}")
        return None


RECOVER = ("重跑导入 `import_sources.py --feature <名>`：它按同目录 "
           f"{ORIGINAL} 重建，只有重建结果与登记的摘要逐字相同才写回")


def raw_lines(folder: Path) -> tuple[list[str], str]:
    """这一版的原文行。读不到或与登记的摘要对不上时返回具体的恢复动作。"""
    source = read_json(folder / SOURCE) or {}
    try:
        text = (folder / RAW).read_text(encoding="utf-8")
    except OSError:
        return [], f"{folder.name} 的 {RAW} 不见了（引用都指着它的行号）：{RECOVER}"
    if source.get("text_sha256") and digest(text.encode("utf-8")) != source["text_sha256"]:
        return [], (f"{folder.name} 的 {RAW} 与 {SOURCE} 登记的摘要对不上："
                    f"它是引用的基底，改了行号就全错。{RECOVER}")
    return text.split("\n"), ""


def restore_raw(folder: Path) -> str:
    """按同目录原件重建 `raw.md`。成功返回空串，恢复不了返回该说的那句话。

    **只有重建结果与 `source.json` 登记的摘要逐字相同才写回**：引用记的是行号，
    换过的转换器重算出来的文本可能整体错位——那不是恢复，是拿另一份文本冒充原文。
    这一版恢复不了就明说，让维护者找回快照，不重编号、不静默改定位。
    """
    original = folder / ORIGINAL
    if not original.is_file():
        return (f"{folder.name} 的 {RAW} 与 {ORIGINAL} 都不在：这一版恢复不了，"
                "要维护者找回这一版的目录快照（它随需求目录进版本库）")
    text = importer.docx_to_markdown(original, MEDIA)[0]
    text = text if text.endswith("\n") else text + "\n"
    known = str((read_json(folder / SOURCE) or {}).get("text_sha256") or "")
    if known and digest(text.encode("utf-8")) != known:
        return (f"{folder.name} 按 {ORIGINAL} 重建出来的文本与 {SOURCE} 登记的摘要不同："
                "当前转换器算出的行号与这一版的旧引用对不上，不能当成恢复。"
                "要维护者找回这一版的 raw.md 快照，在那之前这一版的结论不要再用")
    (folder / RAW).write_text(text, encoding="utf-8", newline="\n")
    return ""


def apply_corrections(lines: list[str], corrections) -> tuple[list[str], list[str]]:
    """按模型给的差异算出阅读件：行数不变，没改的行逐字保留。

    问题一次报全并且**不出件**：半应用的阅读件与引用同时存在的话，同一个行号在两份文件里
    指着不同的字。
    """
    problems: list[str] = []
    if corrections is None:
        return list(lines), ["还没写 corrections.json（没有要改的就写 []）"]
    if not isinstance(corrections, list):
        return list(lines), ["corrections.json 要写成数组：[{line, original, corrected, basis}]"]
    out, seen = list(lines), {}
    for index, item in enumerate(corrections, 1):
        where = f"第 {index} 条"
        if not isinstance(item, dict):
            problems.append(f"{where}不是对象：{{line, original, corrected, basis}}")
            continue
        line = item.get("line")
        if not isinstance(line, int) or isinstance(line, bool) or not 1 <= line <= len(lines):
            problems.append(f"{where}的 line「{item.get('line')}」不是 {RAW} 里的行号"
                            f"（1–{len(lines)}）")
            continue
        if line in seen:
            problems.append(f"第 {line} 行有两条纠偏（{seen[line]}与{where}）："
                            "一行至多一条，同一行的几处字面改动写进同一条")
            continue
        seen[line] = where
        original, corrected = str(item.get("original", "")), str(item.get("corrected", ""))
        if original != lines[line - 1]:
            problems.append(f"第 {line} 行的 original 与 {RAW} 对不上——那一行是"
                            f"「{lines[line - 1][:60]}」：original 写该行全文，逐字相同")
            continue
        if "\n" in corrected or "\r" in corrected:
            problems.append(f"第 {line} 行的 corrected 里有换行：纠偏不拆行、不并行，"
                            "行数与顺序保持原样")
            continue
        if original.strip() and not corrected.strip():
            problems.append(f"第 {line} 行被改成了空行：纠偏只改字面，不删内容")
            continue
        if not str(item.get("basis", "")).strip():
            problems.append(f"第 {line} 行的纠偏没写 basis：依据只来自参会名单、本需求材料、"
                            "项目事实与术语表，拿不准就保持原样")
            continue
        out[line - 1] = corrected
    return out, problems


def evidence_text(lines: list[str]) -> str:
    return "\n".join(lines)


def evidence_stale(folder: Path, fixed: list[str]) -> bool:
    """阅读件跟不跟得上现在的差异。"""
    try:
        return (folder / EVIDENCE).read_text(encoding="utf-8").replace("\r\n", "\n") \
            != evidence_text(fixed)
    except OSError:
        return True


def evidence_lines(folder: Path) -> list[str]:
    """纠偏后的行；还没出件时退回原文——引文缺了不该让派生算不出来。"""
    try:
        return (folder / EVIDENCE).read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    except OSError:
        return raw_lines(folder)[0]


def line_ref(feature_root: Path, folder: Path, rng: dict) -> str:
    """给人看的引用：实际路径 + 行范围。目录形状只在这里渲一次。"""
    rel = (folder / RAW).relative_to(feature_root).as_posix()
    start, end = int(rng.get("start", 0)), int(rng.get("end", 0))
    return f"{rel}:L{start}" + (f"-L{end}" if end != start else "")


def quote(lines: list[str], rng: dict) -> str:
    """这一段原话。不摘要、不截断被引用的否定条件。"""
    start, end = int(rng.get("start", 0)), int(rng.get("end", 0))
    picked = [l.strip() for l in lines[max(start - 1, 0):end] if l.strip()]
    return " / ".join(picked)


def ranges(value) -> list[dict]:
    return [r for r in (value or []) if isinstance(r, dict)]


def range_problems(what: str, value, total: int) -> list[str]:
    """引用立不立得住：形状对、范围在原文之内。"""
    if not isinstance(value, list) or not value:
        return [f"{what}没有指回 {RAW} 的行范围（[{{\"start\": 12, \"end\": 15}}]，1 起、首尾包含）"]
    out: list[str] = []
    for rng in value:
        if not isinstance(rng, dict):
            out.append(f"{what}的引用不是 {{start, end}} 对象")
            continue
        start, end = rng.get("start"), rng.get("end")
        ok = all(isinstance(v, int) and not isinstance(v, bool) for v in (start, end))
        if not ok or not 1 <= start <= end <= total:
            out.append(f"{what}的行范围 {start}–{end} 不在 {RAW} 里（1–{total}）")
    return out


def read_notes(feature_root: Path, problems: list[str]) -> dict[str, dict]:
    """会议结论按版本分节：`<主名>@<sha8>` → 那一节。

    同一个版本写了两节就报出来，不让后写的盖掉先写的——版本是引用的身份，
    盖掉之后旧引用指向的是另一份判断，而两份都还在文件里。
    """
    data = read_json(feature_root.joinpath(*NOTES), problems)
    sections = data.get("meetings") if isinstance(data, dict) else None
    if data is not None and not isinstance(sections, list):
        problems.append("meeting-notes.json 要写成 {\"meetings\": [每场会每个版本一节]}")
    out: dict[str, dict] = {}
    for section in sections or []:
        if not isinstance(section, dict):
            continue
        key = f"{Path(str(section.get('source', ''))).stem}@{str(section.get('source_sha', ''))[:8]}"
        if key in out:
            problems.append(f"meeting-notes.json 里「{key}」有两节：一个版本一节，"
                            "同一场会的新版本换 source_sha")
            continue
        out[key] = section
    return out


def _topic_index(key: str, topics, total: int, problems: list[str]) -> list[str]:
    """话题索引立不立得住：编号唯一、引用指得到真实的行。返回登记了哪些话题。"""
    if not isinstance(topics, list):
        problems.append(f"{key} 的 {TOPICS} 要写成数组："
                        "[{\"id\": \"T1\", \"title\": \"话题名\", \"evidence\": [{\"start\", \"end\"}]}]")
        return []
    registered: list[str] = []
    for item in topics:
        if not isinstance(item, dict) or not str(item.get("id", "")).strip():
            problems.append(f"{key} 的 {TOPICS} 里有条目没写 id")
            continue
        tid = str(item["id"])
        if tid in registered:
            problems.append(f"{key} 的 {TOPICS} 里 {tid} 重复：一个话题一条")
            continue
        registered.append(tid)
        problems.extend(f"{key}/{tid} " + p for p in range_problems("的话题索引：", item.get("evidence"), total))
    return registered


def _effect_problems(effect, topic: dict, changes: set[str], opens: set[str]) -> list[str]:
    """一个选项选完会怎样：只核结构与引用，不判这个选择好不好。"""
    if not isinstance(effect, dict):
        return ["缺 effect——选了它归属定成什么、哪些变化生效、哪些遗留被落定或保留"]
    out: list[str] = []
    if topic.get("ownership") == "unclear" and effect.get("ownership") not in ("ours", "not_ours"):
        out.append("归属判不准，effect.ownership 要定成 ours 或 not_ours")
    if topic.get("overturns") and not isinstance(effect.get("supersedes"), list):
        out.append("推翻了旧决定，要写 supersedes（可以为空列表）")
    if not {str(c) for c in effect.get("apply_changes") or []} <= changes:
        out.append("apply_changes 引了本话题没有的变化")
    resolved = [str(a.get("resolves")) for a in effect.get("add_changes") or []
                if isinstance(a, dict) and a.get("resolves")]
    if any(r not in opens for r in resolved):
        out.append("add_changes 的 resolves 要指向本话题的 open_points")
    if len(resolved) != len(set(resolved)):
        out.append("同一个遗留被两条 add_changes 落定：一个遗留只由一处解决")
    kept = [str(k) for k in effect.get("keep_open") or []]
    if any(k not in opens for k in kept):
        out.append("keep_open 要指向本话题的 open_points")
    both = sorted(set(kept) & set(resolved))
    if both:
        out.append(f"{'、'.join(both)} 既落定又保留：同一个遗留只能二选一")
    return out


def _unique(items: list, what: str, say) -> dict:
    """按 id 建索引，重复的报出来而不是后写盖前写——id 是选择与引用的身份。"""
    out: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        ident = str(item.get("id"))
        if ident in out:
            say(f"里 {what} {ident} 重复：一个编号只能有一条")
            continue
        out[ident] = item
    return out


def _notes_problems(key: str, section: dict, registered: list[str], total: int,
                    problems: list[str], refs: dict[str, dict]) -> None:
    topics = _unique(section.get("topics") or [], "话题",
                     lambda msg: problems.append(f"{key} {msg}"))
    lost = [t for t in registered if t not in topics]
    if lost:
        problems.append(f"{key}：{TOPICS} 登记的话题 {'、'.join(lost)} 在会议结论里没有去向"
                        "——每个话题都要有判断（变化、结论、遗留，或不属于本需求）")
    unknown = [t for t in topics if t not in registered]
    if unknown:
        problems.append(f"{key}：会议结论里的 {'、'.join(unknown)} 不在 {TOPICS} 里"
                        "——话题索引与结论对同一批编号")
    for tid, topic in topics.items():
        def say(msg: str) -> None:
            problems.append(f"{key}/{tid} {msg}")

        refs[f"{key}/{tid}"] = topic
        if topic.get("ownership") not in OWNERSHIP:
            say(f"的 ownership 要写 {' / '.join(OWNERSHIP)} 之一")
        changes = _unique(topic.get("changes") or [], "变化", say)
        open_points = _unique(topic.get("open_points") or [], "遗留", say)
        cited = [("结论", (topic.get("conclusion") or {}).get("evidence"))] if topic.get("conclusion") else []
        cited += [(f"变化 {cid}", c.get("evidence")) for cid, c in changes.items()]
        # 遗留也要指得回原话：它要跟着传到下游，读的人得能自己回去看那几行
        cited += [(f"遗留 {oid}", o.get("evidence")) for oid, o in open_points.items()]
        for what, value in cited:
            for problem in range_problems(f"的{what}：", value, total):
                say(problem)
        opens = set(open_points)
        reason = topic.get("ask_reason")
        if not topic.get("ask"):
            if reason in ASK_REASONS:
                say(f"写了 ask_reason: {reason}（需要人裁决的原因），ask 却是 false")
            if topic.get("ownership") == "unclear" or topic.get("overturns"):
                say("归属判不准或推翻了旧决定，要 ask: true 摆给人")
            continue
        if reason not in ASK_REASONS:
            say(f"要问人：ask_reason 写 {' / '.join(ASK_REASONS)} 之一")
        options = [o for o in topic.get("options") or [] if isinstance(o, dict)]
        keys = [str(o.get("key")) for o in options]
        if len(options) < 2 or topic.get("recommend") not in keys:
            say("要问人：至少两个 options，recommend 是其中一个 key")
        if len(set(keys)) != len(keys):
            say("的选项 key 有重复：人选的 key 要唯一指到一个 effect")
        for option in options:
            for problem in _effect_problems(option.get("effect"), topic, set(changes), opens):
                say(f"的选项「{option.get('key')}」{problem}")


def _relation_problems(refs: dict[str, dict], problems: list[str]) -> None:
    """替代关系指得到、不自指、不成环——脚本只核声明过的那些。

    没声明的语义矛盾（两场会说了相反的话而谁也没提对方）看不出来，那归独立审查。
    """
    edges: dict[str, set[str]] = {}
    for ref, topic in refs.items():
        targets = {str(topic["overturns"])} if topic.get("overturns") else set()
        for option in topic.get("options") or []:
            effect = option.get("effect") if isinstance(option, dict) else None
            targets |= {str(t) for t in (effect or {}).get("supersedes") or []}
        for target in sorted(targets):
            if target == ref:
                problems.append(f"{ref} 的替代关系指着自己")
            elif target not in refs:
                problems.append(f"{ref} 要替代的「{target}」不存在——写 <主名>@<sha8>/<话题 id>，"
                                "指向已经读过的那一版")
        edges[ref] = {t for t in targets if t in refs and t != ref}

    def reaches(start: str, node: str, seen: set[str]) -> bool:
        return any(nxt == start or (nxt not in seen and reaches(start, nxt, seen | {nxt}))
                   for nxt in edges.get(node, ()))

    problems.extend(f"{ref} 在一条替代环里：哪个决定最终有效就说不清了"
                    for ref in sorted(edges) if reaches(ref, ref, {ref}))


def inspect(feature_root: Path) -> dict:
    """读会进行到哪、立不立得住。

    ``missing`` 还没读的版本；``stale`` 阅读件跟不上纠偏差异的版本；``problems`` 结构、
    引用与留痕的缺口。只读，不写盘——出件归 `meeting-refresh`。
    """
    problems: list[str] = []
    notes = read_notes(feature_root, problems)
    found = versions(feature_root)
    missing: list[str] = []
    stale: list[str] = []
    refs: dict[str, dict] = {}
    for key in sorted(set(notes) - set(found)):
        problems.append(f"meeting-notes.json 的「{key}」对不上任何会议版本"
                        f"——source 与 source_sha 照抄那一版的 {SOURCE}")
    for old in sorted(feature_root.joinpath(*MEETINGS).glob("*/*/transcript.json")):
        # 上一轮格式的产物：本轮按行引用，发言编号那套读法已经退出
        problems.append(f"{old.parent.parent.name}/{old.parent.name} 是上一轮格式的会议产物"
                        "（transcript.json 与发言编号），本轮不支持：把原件放回收件箱重导、"
                        "按新合同重读；旧目录留着不动，由维护者处置")
    for key, folder in found.items():
        lines, broken = raw_lines(folder)
        if broken:
            problems.append(broken)
            continue
        corrections = read_json(folder / CORRECTIONS, problems)
        if corrections is not None:
            # 阅读件先出：它与 raw.md 行号一一对应，后面的引用与摘要都从它取字
            fixed, bad = apply_corrections(lines, corrections)
            problems.extend(f"{key} 的纠偏：{b}" for b in bad)
            if not bad and evidence_stale(folder, fixed):
                stale.append(key)
        topics = read_json(folder / TOPICS, problems)
        if corrections is None or topics is None or key not in notes:
            missing.append(key)
            continue
        registered = _topic_index(key, topics, len(lines), problems)
        _notes_problems(key, notes[key], registered, len(lines), problems, refs)
    _relation_problems(refs, problems)
    return {"notes": notes, "missing": missing, "stale": stale, "problems": problems}


def material_items(feature_root: Path) -> list[dict]:
    """材料清单里的会议条目：身份取**原件**的摘要。

    转换件、阅读件与结论都是读会的产物：算进材料版本的话，读一次会就开一轮；
    转换器升级也会让旧会议看上去像换了材料。
    """
    out: list[dict] = []
    for folder in sorted(versions(feature_root).values()):
        sha = str((read_json(folder / SOURCE) or {}).get("sha256") or "")
        out.append({"kind": "meeting",
                    "paths": [(folder / ORIGINAL).relative_to(feature_root).as_posix()],
                    "sha256": f"sha256:{sha[:16]}" if sha else None})
    return out
