"""会议这一段的确定性部分：摆给人的话题、人的裁决记录，以及当前会议结果的输入绑定与引用核对。

**业务结果由模型写**：人裁决之后，`AR/story-src/doc-refresh.md` 由读会的模型按原话与真实裁决
写成——它是下游唯一的当前会议结果。脚本不再把变化、遗留与选项效果编译成文稿：那套中间协议
（C/O 编号、effect、替代图）已经退出，脚本合成不出「这件事最后怎么算」，只会让模型多维护一层。

脚本在这里只做三件确定的事：

- 摆出还要问人的话题（`pending_asks`）与人能选的那几项（`topic_options`）；
- 记下人选了哪一项（`decide` 写进契约，本模块只读）；
- 给当前结果一个**输入绑定**（`meeting_basis`）并核它引用的原文行真实存在（`refresh_problems`）。

绑定只证明这份结果声明的是当前这版输入，**不证明模型理解得对**——那归独立审查。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from materials import meeting

from flow.state import FlowError

REFRESH = ("AR", "story-src", "doc-refresh.md")
#: 当前结果的输入绑定：摘要由 `meeting_basis` 算，模型原样抄进文件开头
BASIS_MARK = re.compile(r"<!--\s*meeting-basis:([0-9a-f]{8,64})\s*-->")
#: 结果里的话题标题：`### <版本>/<话题 id> <标题>`
HEADING = re.compile(r"^###\s+(\S+@[0-9a-f]{8}/\S+)\s*(.*)$")
#: 结果里显式写出的原话引用
CITE = re.compile(r"(AR/story-src/meetings/[^\s:：]+/raw\.md):L(\d+)(?:-L(\d+))?")
#: 人的裁决记录里留下的字段：证据是人选了什么、依据是什么，不含任何业务合成
GATE_FIELDS = ("gate", "meeting", "item", "options", "chosen", "basis", "at", "meetings")


def _accepted(contract: dict, gate: str) -> list[dict]:
    return [g for r in contract.get("rounds") or [] for g in r.get("gates") or []
            if g.get("gate") == gate and g.get("outcome") == "accepted"]


def presented(contract: dict) -> set[str]:
    """在第一级材料关卡上摆给人看过、人已表态的会议版本。"""
    return {k for g in _accepted(contract, "material_scope") for k in g.get("meetings") or []}


def unconfirmed(notes: dict, contract: dict) -> list[str]:
    """有了会议判断、还没在第一级摆给人的版本。"""
    return sorted(set(notes) - presented(contract))


def pending_asks(notes: dict, contract: dict) -> list[str]:
    """要问人而还没签的话题：`<主名>@<sha8>/<话题>`。问不问由 `question` 说了算。"""
    signed = {(g.get("meeting"), g.get("item")) for g in _accepted(contract, "meeting")}
    return [f"{key}/{t.get('id')}" for key, section in sorted(notes.items())
            for t in meeting.topics_of(section)
            if str(t.get("question", "")).strip() and (key, str(t.get("id"))) not in signed]


def topic_options(feature_root: Path, version: str, item: str) -> list[dict]:
    """`decide --gate meeting` 的选项集：取自那个话题的 options，脚本只认 key。"""
    section = meeting.read_notes(feature_root, []).get(version) or {}
    topic = next((t for t in meeting.topics_of(section) if str(t.get("id")) == item), None)
    if not topic or not str(topic.get("question", "")).strip():
        raise FlowError(f"会议判断「{version}」里没有要问人的话题「{item}」——--meeting 写 <主名>@<sha8>，"
                        "--item 写话题 id；待裁决的条目列在 `status` 的 meetings 里")
    return [{"key": o.get("key"), "label": o.get("label", "")}
            for o in topic.get("options") or [] if isinstance(o, dict)]


def topic_digest(feature_root: Path, notes: dict, contract: dict) -> list[dict]:
    """摆给人看的全部话题：每个版本、每个话题一条，机械枚举，不替模型判断。

    包括不属于本需求的与归属判不准的——漏摆的那几条，人就没有机会说「这条其实归我们」。
    """
    folders = meeting.versions(feature_root)
    signed = {(g.get("meeting"), g.get("item")): g for g in _accepted(contract, "meeting")}
    shown = presented(contract)
    rows: list[dict] = []
    for key, section in sorted(notes.items()):
        folder = folders.get(key)
        for topic in meeting.topics_of(section):
            tid = str(topic.get("id"))
            gate = signed.get((key, tid))
            row = {
                "version": key, "topic": tid, "title": topic.get("title", ""),
                "ownership": topic.get("ownership"), "finding": topic.get("finding", ""),
                "settled": gate.get("chosen") if gate else None,
                "version_confirmed": key in shown,
            }
            if folder is not None:
                row["evidence"] = [meeting.line_ref(feature_root, folder, r)
                                   for r in meeting.ranges(topic.get("evidence"))]
            if str(topic.get("question", "")).strip() and not gate:
                row["question"] = topic["question"]
                row["recommend"] = topic.get("recommend")
                row["options"] = [{"key": o.get("key"), "label": o.get("label", "")}
                                  for o in topic.get("options") or [] if isinstance(o, dict)]
            rows.append(row)
    return rows


def meeting_basis(notes: dict, contract: dict) -> str:
    """当前会议结果声明的输入版本：会议判断 + 人真实签下的那几笔。

    只取确定性事实——判断本身与关卡记录的固定字段，键排序、列表按原顺序。
    新会议、改判断或人又签了一笔，摘要就变；一个字节没动时它稳定，所以旧结果不会被误判成陈旧。
    它**不证明模型理解得对**，只证明这份结果是照着这版输入写的。
    """
    gates = [{k: g.get(k) for k in GATE_FIELDS if k in g}
             for gate in ("meeting", "material_scope") for g in _accepted(contract, gate)]
    payload = json.dumps({"notes": notes, "gates": gates},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return meeting.digest(payload.encode("utf-8"))[:16]


def refresh_problems(feature_root: Path, notes: dict, contract: dict) -> list[str]:
    """当前会议结果立不立得住 —— 只核**能确定的四件事**。

    文件在不在、声明的输入是不是当前这版、每个话题有没有去向、写出来的原话引用指不指得到。
    结论对不对、未决有没有被替人定，读的是自然语言，归独立审查；这里不按关键词判业务，
    也不要求最短引文。
    """
    path = feature_root.joinpath(*REFRESH)
    where = "/".join(REFRESH)
    if not notes:
        return []
    basis = meeting_basis(notes, contract)
    try:
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    except OSError:
        return [f"{where} 还没写：人的裁决已经齐了，按原话与裁决写出当前的会议结果，"
                f"开头写一行 <!-- meeting-basis:{basis} -->"]
    problems: list[str] = []
    marks = BASIS_MARK.findall(text)
    if len(marks) != 1:
        problems.append(f"{where} 里要恰好有一行 <!-- meeting-basis:… -->（现在有 {len(marks)} 行）")
    elif marks[0] != basis:
        problems.append(f"{where} 声明的输入是 {marks[0]}，当前输入是 {basis}："
                        "会议判断或人的裁决之后变过，按当前输入重新核一遍整份结果再换上这个标记")
    refs, seen = [], set()
    for line in text.split("\n"):
        hit = HEADING.match(line.strip())
        if not hit:
            continue
        if hit[1] in seen:
            problems.append(f"{where} 里「{hit[1]}」有两个标题：一个话题讲一处")
        seen.add(hit[1])
        refs.append(hit[1])
    want = {f"{key}/{t.get('id')}" for key, section in notes.items()
            for t in meeting.topics_of(section)}
    lost = sorted(want - set(refs))
    if lost:
        problems.append(f"{where} 缺这几个话题的去向：{'、'.join(lost)}"
                        "——不属于本需求或已被后续决定替代的，也写一句去向，别静默删掉")
    extra = sorted(set(refs) - want)
    if extra:
        problems.append(f"{where} 里「{'、'.join(extra)}」不在会议判断里：标题写 <版本>/<话题 id>")
    folders = meeting.versions(feature_root)
    for rel, start, end in CITE.findall(text):
        folder = feature_root / rel
        key = f"{folder.parent.parent.name}@{folder.parent.name}"
        total = len(meeting.raw_lines(folders[key])[0]) if key in folders else 0
        if key not in folders or not 1 <= int(start) <= int(end or start) <= total:
            problems.append(f"{where} 引的 {rel}:L{start} 指不到真实的原文行")
    return problems


def cmd_meeting_refresh(feature_root: Path, version: str) -> dict:
    """按 `corrections.json` 生成阅读件 `evidence.md`：确定性动作，问题一次报全。

    模型不直接写 evidence.md——它与 raw.md 行号一一对应，手写就没人保证这件事还成立。
    """
    folders = meeting.versions(feature_root)
    folder = folders.get(version)
    if folder is None:
        raise FlowError(f"没有会议版本「{version}」——`--meeting` 写 <主名>@<sha8>，"
                        f"现有：{'、'.join(sorted(folders)) or '（还没有导入会议材料）'}")
    lines, broken = meeting.raw_lines(folder)
    if broken:
        raise FlowError(broken)
    corrections = meeting.read_json(folder / meeting.CORRECTIONS)
    fixed, problems = meeting.apply_corrections(lines, corrections)
    if problems:
        raise FlowError(f"{version} 的纠偏还立不住，先改 {meeting.CORRECTIONS}（原件与行号不动）："
                        + "；".join(problems))
    path = folder / meeting.EVIDENCE
    path.write_text(meeting.evidence_text(fixed), encoding="utf-8", newline="\n")
    return {"meeting": version, "lines": len(fixed),
            "corrections": len(corrections or []),
            "evidence": path.relative_to(feature_root).as_posix()}
