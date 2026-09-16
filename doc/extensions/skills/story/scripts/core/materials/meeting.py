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

材料身份是**原件**：同名换了内容就是新版本、新目录；已经存过的版本原样复用，转换器升级
不重算旧版——旧结论引的那几行永远指得回同一段字。

引用一律是 raw.md 的行范围 `{"start": 12, "end": 15}`（1 起、首尾包含），给人看时渲成
`AR/story-src/meetings/<主名>/<sha8>/raw.md:L12-L15`。不另编发言号：编号等于脚本替模型
划语义单元。

会议判断 `AR/story-src/meeting-notes.json` 按 `<主名>@<sha8>` 分节，一个话题一条：
归属、原话引用、`finding`（定了什么、与文档差在哪、还有什么没定）、要问人时的 `question`
与选项。形状见 `phases/meeting-read.md`。

自检只核结构、引用与留痕：**不读 finding 判业务**——纠偏改没改意思、话题漏没漏、结论有没有
写出会上没说的、未决是不是被替人定了，都要拿原话与材料对着读，归读会的模型自己与独立审查。

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
CORRECTIONS, EVIDENCE = "corrections.json", "evidence.md"
#: 文档内嵌图跟着版本走，raw.md 里按 `media/<名>` 引用
MEDIA = "media"
OWNERSHIP = ("ours", "not_ours", "unclear")


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


def line_ref(feature_root: Path, folder: Path, rng: dict) -> str:
    """给人看的引用：实际路径 + 行范围。目录形状只在这里渲一次。"""
    rel = (folder / RAW).relative_to(feature_root).as_posix()
    start, end = int(rng.get("start", 0)), int(rng.get("end", 0))
    return f"{rel}:L{start}" + (f"-L{end}" if end != start else "")


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
    """会议判断按版本分节：`<主名>@<sha8>` → 那一节。

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


def topics_of(section: dict) -> list[dict]:
    """一节里的话题，按原顺序。"""
    return [t for t in section.get("topics") or [] if isinstance(t, dict)]


def _notes_problems(key: str, section: dict, total: int, problems: list[str]) -> None:
    """一份会议判断立不立得住——**只核结构与引用，不读 finding 判业务**。

    话题漏没漏、结论对不对、未决是不是被替人定了，脚本看不出来：那要拿原话与需求材料
    对着读，归读会的模型自己与独立审查。
    """
    seen: set[str] = set()
    for topic in topics_of(section):
        tid = str(topic.get("id", "")).strip()
        if not tid:
            problems.append(f"{key} 里有话题没写 id")
            continue
        if tid in seen:
            problems.append(f"{key} 里话题 {tid} 重复：一个编号只有一条")
            continue
        seen.add(tid)

        def say(msg: str) -> None:
            problems.append(f"{key}/{tid} {msg}")

        if not str(topic.get("title", "")).strip():
            say("没写 title：给人看的一句话题名")
        if topic.get("ownership") not in OWNERSHIP:
            say(f"的 ownership 要写 {' / '.join(OWNERSHIP)} 之一")
        for problem in range_problems("的原话引用：", topic.get("evidence"), total):
            say(problem)
        if not str(topic.get("finding", "")).strip():
            say("没写 finding：这个话题定了什么、与文档差在哪、还有什么没定，一段话说清")
        question = str(topic.get("question", "")).strip()
        options = [o for o in topic.get("options") or [] if isinstance(o, dict)]
        if topic.get("ownership") == "unclear" and not question:
            say("归属判不准，要写 question 摆给人")
        if not question:
            if options:
                say("没有 question 却写了 options：不问人就不摆选项")
            continue
        keys = [str(o.get("key", "")).strip() for o in options]
        if not options or not all(keys):
            say("要问人：至少一个真实选项，每个带 key 与 label")
        if len(set(keys)) != len(keys):
            say("的选项 key 有重复：人选的 key 要唯一指到一个做法")
        recommend = str(topic.get("recommend", "")).strip()
        if recommend and recommend not in keys:
            say(f"的 recommend「{recommend}」不在选项里")


def inspect(feature_root: Path) -> dict:
    """读会进行到哪、立不立得住。

    ``missing`` 还没读的版本；``stale`` 阅读件跟不上纠偏差异的版本；``problems`` 结构与引用的缺口。
    只读，不写盘——出件归 `meeting-refresh`，会议结果归模型。
    """
    problems: list[str] = []
    notes = read_notes(feature_root, problems)
    found = versions(feature_root)
    missing: list[str] = []
    stale: list[str] = []
    for key in sorted(set(notes) - set(found)):
        problems.append(f"meeting-notes.json 的「{key}」对不上任何会议版本"
                        f"——source 与 source_sha 照抄那一版的 {SOURCE}")
    for old in sorted(feature_root.joinpath(*MEETINGS).glob("*/*/topics.json")):
        # 上一轮格式的产物：话题现在只在 meeting-notes.json 里登记一次
        problems.append(f"{old.parent.parent.name}/{old.parent.name} 还留着上一轮的 topics.json："
                        "本轮话题只登记在 meeting-notes.json 一处，删掉它再读会")
    for key, folder in sorted(found.items()):
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
        if corrections is None or key not in notes:
            missing.append(key)
            continue
        _notes_problems(key, notes[key], len(lines), problems)
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
