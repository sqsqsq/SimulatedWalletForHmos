"""会议转写：docx → `transcript.json`（公共解析），以及读会产物的结构自检。

**输出合同**（`AR/story-src/meetings/<docx 主名>/<sha8>/transcript.json`，一个源版本一个目录）::

    {"source": {"file": "xxx.docx", "sha256": "<64 位>"},
     "meeting": {"title": "…", "date": "…", "attendees": ["张三", "李四"]},
     "preamble": ["第一条发言之前、认不出是会议信息的段落，原样保留"],
     "sections": [{"title": "议题一 …",
                   "speeches": [{"id": "S1", "speaker": "张三", "time": "10:02", "text": "…"}]}]}

认的形态：Word 标题段是议题，最上层只出现一次的标题是会名；「姓名 时间：发言」是一条发言，
全场从 S1 连续编号；第一条发言之前的「会议时间：」「参会人：」是会议信息。
认不出形态的段落接进最近一条发言（换行分隔），一个字都不丢。

同名 docx 换了内容就是新版本、新目录：旧目录里的原文与证据原样留着，旧结论引的发言编号永远查得回。

自检只核结构与留痕，不判意思：纠偏改没改意思、话题漏没漏、结论写没写出会上没说的，归独立审查。
只用标准库，stdout 无输出。
"""
from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path

from materials import importer

MEETINGS = ("AR", "story-src", "meetings")
NOTES = ("AR", "story-src", "meeting-notes.json")
TRANSCRIPT, EVIDENCE, TOPICS = "transcript.json", "evidence.json", "topics.json"
OWNERSHIP = ("ours", "not_ours", "unclear")

SPEECH = re.compile(r"^(?P<speaker>[^\s:：|#]{1,20})\s+(?P<time>\d{1,2}:\d{2}(?::\d{2})?)\s*[:：]\s*(?P<text>.*)$")
DATE = re.compile(r"^(?:会议)?(?:时间|日期)\s*[:：]\s*(.+)$")
ATTENDEES = re.compile(r"^(?:参会|与会)(?:人员|人)\s*[:：]\s*(.+)$")


def transcript_path(feature_root: Path, docx: Path) -> Path:
    """这份 docx 这一版的解析件落点：主名 + 内容指纹前 8 位。"""
    return feature_root.joinpath(*MEETINGS, docx.stem,
                                 sha256(docx.read_bytes()).hexdigest()[:8], TRANSCRIPT)


def parse(docx: Path) -> dict:
    """按 D3 的形态把会议 docx 读成发言结构。与导入同一个 docx 解析器。"""
    markdown, _ = importer.docx_to_markdown(docx, ".")
    blocks = [re.sub(r"\*{1,2}([^*]*)\*{1,2}", r"\1", b.strip())
              for b in markdown.split("\n\n") if b.strip()]
    levels = [len(b) - len(b.lstrip("#")) for b in blocks if b.startswith("#")]
    top = min(levels) if levels else 0
    titled = len(set(levels)) > 1 and levels.count(top) == 1
    meeting = {"title": "", "date": "", "attendees": []}
    preamble: list[str] = []
    sections: list[dict] = []
    last: dict | None = None
    for block in blocks:
        if block.startswith("#"):
            title = block.lstrip("#").strip()
            if titled and len(block) - len(block.lstrip("#")) == top:
                meeting["title"] = title
            else:
                sections.append({"title": title, "speeches": []})
            continue
        m = SPEECH.match(block)
        if m:
            if not sections:
                sections.append({"title": "", "speeches": []})
            last = {"id": f"S{sum(len(s['speeches']) for s in sections) + 1}", **m.groupdict()}
            sections[-1]["speeches"].append(last)
        elif last is None and (d := DATE.match(block)):
            meeting["date"] = d.group(1).strip()
        elif last is None and (a := ATTENDEES.match(block)):
            meeting["attendees"] = [x for x in re.split(r"[、,，;；\s]+", a.group(1)) if x]
        elif last is not None:
            last["text"] += "\n" + block
        else:
            preamble.append(block)
    return {"source": {"file": docx.name, "sha256": sha256(docx.read_bytes()).hexdigest()},
            "meeting": meeting, "preamble": preamble, "sections": sections}


def write_transcript(feature_root: Path, docx: Path, parsed: dict) -> Path:
    path = transcript_path(feature_root, docx)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def versions(feature_root: Path) -> dict[str, Path]:
    """盘上每个会议版本：`<主名>@<sha8>` → 版本目录。"""
    base = feature_root.joinpath(*MEETINGS)
    return {f"{p.parent.parent.name}@{p.parent.name}": p.parent
            for p in sorted(base.glob(f"*/*/{TRANSCRIPT}"))}


def _read(path: Path, problems: list[str]):
    """读一份 JSON：不在返回 None；坏了记一条问题也返回 None——坏的不当成没写。"""
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError:
        return None
    except ValueError as exc:
        problems.append(f"{path.name}（{path.parent.name}）不是合法 JSON：{exc}")
        return None


def _speeches(doc) -> list[dict]:
    return [s for sec in (doc or {}).get("sections") or [] for s in sec.get("speeches") or []
            if isinstance(s, dict)]


def read_notes(feature_root: Path, problems: list[str]) -> dict[str, dict]:
    """会议结论按版本分节：`<主名>@<sha8>` → 那一节。"""
    data = _read(feature_root.joinpath(*NOTES), problems)
    sections = data.get("meetings") if isinstance(data, dict) else None
    if data is not None and not isinstance(sections, list):
        problems.append("meeting-notes.json 要写成 {\"meetings\": [每场会每个版本一节]}")
    return {f"{Path(str(s.get('source', ''))).stem}@{str(s.get('source_sha', ''))[:8]}": s
            for s in sections or [] if isinstance(s, dict)}


def _evidence_problems(key: str, transcript: dict, evidence: dict, problems: list[str]) -> set[str]:
    """纠偏只改字面：编号与顺序守恒，每一处文本差异都由 corrections 解释。"""
    raw = {s.get("id"): str(s.get("text", "")) for s in _speeches(transcript)}
    got = _speeches(evidence)
    if [s.get("id") for s in got] != list(raw):
        problems.append(f"{key} 的 evidence.json 发言编号与转写对不上（缺、增、改号或调了顺序）"
                        "——纠偏不删、不合并、不调顺序，编号照转写原样")
    fixes: dict[str, list[dict]] = {}
    for c in evidence.get("corrections") or []:
        fixes.setdefault(c.get("speech"), []).append(c)
    for s in got:
        text = raw.get(s.get("id"))
        if text is None:
            continue
        for c in fixes.get(s.get("id"), []):
            before = str(c.get("original", ""))
            if not before or before not in text or not str(c.get("basis", "")).strip():
                problems.append(f"{key} 的纠偏留痕说 {s.get('id')} 里有「{before}」，转写原文里没有，或没写依据")
                continue
            text = text.replace(before, str(c.get("corrected", "")), 1)
        if text != str(s.get("text", "")):
            problems.append(f"{key} 的 {s.get('id')} 有没登记进 corrections 的改动"
                            "——每一处改动都要留痕：发言编号 / 原文片段 / 改成 / 依据")
    return set(raw)


def _notes_problems(key: str, section: dict, ids: set[str], registered: list[str],
                    problems: list[str]) -> None:
    topics = {str(t.get("id")): t for t in section.get("topics") or [] if isinstance(t, dict)}
    lost = [t for t in registered if t not in topics]
    if lost:
        problems.append(f"{key}：topics.json 登记的话题 {'、'.join(lost)} 在会议结论里没有去向"
                        "——每个话题都要有判断（变化、结论、遗留，或不属于本需求）")
    for tid, t in topics.items():
        def say(msg: str, at: str = f"{key}/{tid}") -> None:
            problems.append(f"{at} {msg}")
        if t.get("ownership") not in OWNERSHIP:
            say(f"的 ownership 要写 {' / '.join(OWNERSHIP)} 之一")
        changes = {str(c.get("id")): c for c in t.get("changes") or [] if isinstance(c, dict)}
        cited = [("结论", (t.get("conclusion") or {}).get("evidence"))] if t.get("conclusion") else []
        for what, evidence in cited + [(f"变化 {cid}", c.get("evidence")) for cid, c in changes.items()]:
            if not evidence or not set(evidence) <= ids:
                say(f"的{what}没有指回本版本 evidence.json 里的发言编号")
        if not t.get("ask"):
            if t.get("ownership") == "unclear" or t.get("overturns"):
                say("归属判不准或推翻了旧决定，要 ask: true 摆给人")
            continue
        options = [o for o in t.get("options") or [] if isinstance(o, dict)]
        if len(options) < 2 or t.get("recommend") not in [o.get("key") for o in options]:
            say("要问人：至少两个 options，recommend 是其中一个 key")
        opens = {str(o.get("id")) for o in t.get("open_points") or [] if isinstance(o, dict)}
        for o in options:
            effect = o.get("effect")
            if not isinstance(effect, dict):
                say(f"的选项「{o.get('key')}」缺 effect——选了它归属定成什么、哪些变化生效、替代哪些旧决定")
                continue
            if t.get("ownership") == "unclear" and effect.get("ownership") not in ("ours", "not_ours"):
                say(f"归属判不准，选项「{o.get('key')}」的 effect.ownership 要定成 ours 或 not_ours")
            if t.get("overturns") and not isinstance(effect.get("supersedes"), list):
                say(f"推翻了旧决定，选项「{o.get('key')}」要写 supersedes（可以为空列表）")
            if not {str(c) for c in effect.get("apply_changes") or []} <= set(changes):
                say(f"的选项「{o.get('key')}」apply_changes 引了本话题没有的变化")
            if any(str(a.get("resolves")) not in opens for a in effect.get("add_changes") or []):
                say(f"的选项「{o.get('key')}」add_changes 的 resolves 要指向本话题的 open_points")


def inspect(feature_root: Path) -> dict:
    """读会进行到哪、立不立得住：`missing` 是还没读完的版本，`problems` 是自检不过的地方。"""
    problems: list[str] = []
    notes = read_notes(feature_root, problems)
    missing: list[str] = []
    found = versions(feature_root)
    for key in sorted(set(notes) - set(found)):
        problems.append(f"meeting-notes.json 的「{key}」对不上任何转写版本——source 与 source_sha 取自那一版的 transcript.json")
    for key, folder in found.items():
        evidence = _read(folder / EVIDENCE, problems)
        topics = _read(folder / TOPICS, problems)
        if evidence is None or topics is None or key not in notes:
            missing.append(key)
            continue
        ids = _evidence_problems(key, _read(folder / TRANSCRIPT, problems) or {}, evidence, problems)
        registered = [str(t.get("id")) for t in topics if isinstance(t, dict)] if isinstance(topics, list) else []
        _notes_problems(key, notes[key], ids, registered, problems)
    return {"notes": notes, "missing": missing, "problems": problems}
