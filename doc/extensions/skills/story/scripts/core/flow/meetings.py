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
#: 看着像话题标题的形状：`<主名>@<8 位指纹>/<话题 id>`。**不拿它取值**——
#: 版本主名就是文件名，允许带空格；取值按已知的版本与话题匹配，形状只用来认出「像却对不上」。
TOPIC_SHAPE = re.compile(r"@[0-9a-f]{8}/")
#: 原话引用的尾巴。路径部分由已知版本目录反查，所以这里不猜路径里有没有空格。
CITE_TAIL = re.compile(r"raw\.md:L(\d+)(?:-L(\d+))?")
#: 围栏行：`(标记, 标记之后的部分)`。开启可以带语言标记（```markdown）；
#: **关闭要同字符、不短于开启，而且标记之后只有空白**——`​```python` 是围栏里的代码行，不是关闭。
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})(.*)$")
#: 真实的三级标题；`####` 是更深的小节，不是话题标题
H3 = re.compile(r"^###\s+(.+?)\s*$")
#: 人的裁决记录里留下的字段：证据是人选了什么、依据是什么，不含任何业务合成
GATE_FIELDS = ("gate", "meeting", "item", "options", "chosen", "basis", "at")


def _accepted(contract: dict, gate: str) -> list[dict]:
    return [g for r in contract.get("rounds") or [] for g in r.get("gates") or []
            if g.get("gate") == gate and g.get("outcome") == "accepted"]


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
    gates = [{k: g.get(k) for k in GATE_FIELDS if k in g} for g in _accepted(contract, "meeting")]
    payload = json.dumps({"notes": notes, "gates": gates},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return meeting.digest(payload.encode("utf-8"))[:16]


def _plain_lines(text: str) -> list[str]:
    """围栏之外的行：围栏里的例子不是这份结果的标题与引用。

    关闭标记要与开启的同字符、不比它短，**而且后面只有空白**——四个反引号里抄三反引号的示例、
    围栏里写一行 ```python，都是合法 Markdown；按「见到三反引号就翻转」去数，
    示例里的标题会被当成真的去向，真正的正文标题反而被跳过。
    """
    out, opened = [], ""
    for line in text.split("\n"):
        hit = FENCE.match(line)
        if opened:
            closes = (hit and hit[1][0] == opened[0]
                      and len(hit[1]) >= len(opened) and not hit[2].strip())
            if closes:
                opened = ""
            continue
        if hit:
            opened = hit[1]                      # 开启行允许带语言标记
            continue
        out.append(line)
    return out


def _headed(line: str, known: list[str]) -> str | None:
    """这一行是不是某个话题的标题：真实的 `### `，再按已知的 `<版本>/<话题>` 认，长的先试。"""
    hit = H3.match(line.strip())
    if not hit:
        return None
    rest = hit[1].strip()
    return next((ref for ref in known if rest == ref or rest.startswith(f"{ref} ")), None)


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
    want = sorted(({f"{key}/{t.get('id')}" for key, section in notes.items()
                    for t in meeting.topics_of(section)}), key=len, reverse=True)
    plain = _plain_lines(text)
    seen: set[str] = set()
    for line in plain:
        ref = _headed(line, want)
        if ref is None:
            hit = H3.match(line.strip())
            if hit and TOPIC_SHAPE.search(hit[1]):
                problems.append(f"{where} 里「{hit[1]}」不在会议判断里：标题写 <版本>/<话题 id>")
            continue
        if ref in seen:
            problems.append(f"{where} 里「{ref}」有两个标题：一个话题讲一处")
        seen.add(ref)
    lost = sorted(set(want) - seen)
    if lost:
        problems.append(f"{where} 缺这几个话题的去向：{'、'.join(lost)}"
                        "——不属于本需求或已被后续决定替代的，也写一句去向，别静默删掉")

    # 引用：路径由实际版本目录反查（主名可以带空格），只核它指不指得到真实的行
    folders = meeting.versions(feature_root)
    paths = {key: (folder / meeting.RAW).relative_to(feature_root).as_posix()
             for key, folder in folders.items()}
    totals = {key: len(meeting.raw_lines(folder)[0]) for key, folder in folders.items()}
    for line in plain:
        for hit in CITE_TAIL.finditer(line):
            cited = line[:hit.start()] + "raw.md"
            key = next((k for k, rel in paths.items() if cited.endswith(rel)), None)
            start, end = int(hit[1]), int(hit[2] or hit[1])
            if key is None or not 1 <= start <= end <= totals[key]:
                problems.append(f"{where} 引的 {hit.group(0)} 指不到真实的原文行"
                                "——路径写版本目录下的 raw.md，行号在它的行数之内")
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
