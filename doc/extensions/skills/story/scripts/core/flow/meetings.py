"""会议的有效结果：模型的判断（`meeting-notes.json`）加人的裁决（契约里的关卡记录），
才是人最终接受的。

派生只有一处（`effective_meeting_results`）：`status` 的路由与 `AR/story-src/doc-refresh.md`
的渲染都调它——提取稿的会议输入与给人的文档刷新清单是同一份派生件。

生效规则：

- 要问人的话题（`ask`）只按人签的那个选项的 `effect` 生效，没签不生效；
- 不问人的话题，要等它所在的会议版本在第一级材料关卡上摆给人、人表了态才生效——
  第一级 accepted 的记录里带着当时摆出的版本（`meetings`），人对摆出的整体表态就是确认；
- 归属最终不是本需求的，只记不消费；
- 旧决定只被某个已签选项的 `supersedes` 指到才失效，新版本到了、推翻未签都不撤销它；
- **未决跟着话题一起生效**：选项落定了哪几个遗留就减掉哪几个，其余原样保留。
  没有变化不等于业务已收敛——那句话只能由会上的结论自己说。

只读契约与会议结论，写的只有 `doc-refresh.md` 与阅读件 `evidence.md`；不建会议状态机：
版本靠目录与指纹，生效靠派生。
"""
from __future__ import annotations

from pathlib import Path

from materials import meeting

from flow.state import FlowError

REFRESH = ("AR", "story-src", "doc-refresh.md")


def _accepted(contract: dict, gate: str) -> list[dict]:
    return [g for r in contract.get("rounds") or [] for g in r.get("gates") or []
            if g.get("gate") == gate and g.get("outcome") == "accepted"]


def presented(contract: dict) -> set[str]:
    """在第一级材料关卡上摆给人看过、人已表态的会议版本。"""
    return {k for g in _accepted(contract, "material_scope") for k in g.get("meetings") or []}


def unconfirmed(notes: dict, contract: dict) -> list[str]:
    """有了会议结论、还没在第一级摆给人的版本。"""
    return sorted(set(notes) - presented(contract))


def pending_asks(notes: dict, contract: dict) -> list[str]:
    """要问人而还没签的话题：`<主名>@<sha8>/<话题>`。"""
    signed = {(g.get("meeting"), g.get("item")) for g in _accepted(contract, "meeting")}
    return [f"{key}/{t.get('id')}" for key, section in sorted(notes.items())
            for t in section.get("topics") or []
            if t.get("ask") and (key, str(t.get("id"))) not in signed]


def effective_meeting_results(notes: dict, contract: dict) -> list[dict]:
    """每个生效话题一项：会上定的变化、人补定的变化、会议原结论、剩下的未决与替代关系。"""
    shown = presented(contract)
    signed = {(g.get("meeting"), g.get("item")): g for g in _accepted(contract, "meeting")}
    out: list[dict] = []
    for key, section in sorted(notes.items()):
        for topic in section.get("topics") or []:
            if not isinstance(topic, dict):
                continue
            tid = str(topic.get("id"))
            changes = {str(c.get("id")): c for c in topic.get("changes") or [] if isinstance(c, dict)}
            opens = [o for o in topic.get("open_points") or [] if isinstance(o, dict)]
            chosen: dict | None = None
            if topic.get("ask"):
                gate = signed.get((key, tid))
                option = next((o for o in topic.get("options") or []
                               if gate and isinstance(o, dict) and o.get("key") == gate.get("chosen")), None)
                if option is None:
                    continue                      # 没签不生效
                effect = option.get("effect") or {}
                owner = effect.get("ownership", topic.get("ownership"))
                picked = [changes[c] for c in effect.get("apply_changes") or [] if c in changes]
                added = [{**c, "basis": gate.get("basis", "")}
                         for c in effect.get("add_changes") or [] if isinstance(c, dict)]
                supersedes = [str(s) for s in effect.get("supersedes") or []]
                resolved = {str(c.get("resolves")) for c in added if c.get("resolves")}
                chosen = {"key": option.get("key"), "label": str(option.get("label", ""))}
            elif key in shown:
                owner, picked, added, supersedes, resolved = (
                    topic.get("ownership"), list(changes.values()), [], [], set())
            else:
                continue
            if owner != "ours":
                continue
            out.append({"ref": f"{key}/{tid}", "version": key, "conclusion": topic.get("conclusion"),
                        "changes": picked, "added": added, "supersedes": supersedes,
                        "open_points": [o for o in opens if str(o.get("id")) not in resolved],
                        "chosen": chosen})
    gone = {s for e in out for s in e["supersedes"]}
    return [e for e in out if e["ref"] not in gone]


def _citer(feature_root: Path):
    """引用渲染器：实际路径 + 行范围 + 纠偏后的原话，同一范围只引一次全文。"""
    folders = meeting.versions(feature_root)
    lines: dict[str, list[str]] = {}
    seen: set[str] = set()

    def cite(version: str, value) -> str:
        folder = folders.get(version)
        rngs = meeting.ranges(value)
        if folder is None or not rngs:
            return ""
        if version not in lines:
            lines[version] = meeting.evidence_lines(folder)
        text = lines[version]
        parts = []
        for rng in rngs:
            ref = meeting.line_ref(feature_root, folder, rng)
            if ref in seen:
                parts.append(f"{ref}（同上）")
            else:
                seen.add(ref)
                parts.append(f"{ref}「{meeting.quote(text, rng)}」")
        return "；".join(parts)

    return cite


def render(feature_root: Path, results: list[dict]) -> str:
    """`doc-refresh.md`：采纳的变化、仍未决、会议原结论及采纳情况，三段固定。

    未决与原结论都在同一份里：提取作者只读这一份就拿得到「定了什么」和「还没定什么」。
    """
    cite = _citer(feature_root)
    rows = ["# 会议有效结果与文档刷新清单", "",
            "<!-- 由 story_flow.py 从 meeting-notes.json 与关卡裁决派生；"
            "改判断回会议结论或重新裁决，手改无效 -->",
            "<!-- 引文取纠偏后的 evidence.md，行号与 raw.md 一致；纠偏依据在同目录 corrections.json -->",
            "", "## 采纳的变化", ""]
    changed = [(e, c, "") for e in results for c in e["changes"]] + \
        [(e, c, c.get("basis", "")) for e in results for c in e["added"]]
    for entry, change, basis in changed:
        source = (f"人工补定，原话「{basis}」"
                  + (f"；落定遗留 {change.get('resolves')}" if change.get("resolves") else "")
                  if basis else "会上定的 —— " + (cite(entry["version"], change.get("evidence")) or "（未给原话）"))
        rows += [f"### {change.get('doc', '')} {change.get('section', '')}（{entry['ref']}）", "",
                 f"- 类型：{change.get('kind', '')}", f"- 改前：{change.get('before', '')}",
                 f"- 改后：{change.get('after', '')}", f"- 影响：{change.get('impact', '')}",
                 f"- 来源：{source}", ""]
    if not changed:
        rows += ["（没有采纳的变化）", ""]

    rows += ["## 仍未决", ""]
    pending = [(e, o) for e in results for o in e["open_points"]]
    for entry, point in pending:
        rows += [f"### {entry['ref']} · {point.get('what', '')}", "",
                 f"- 影响：{point.get('impact', '')}", f"- 谁来定：{point.get('needs', '')}"]
        if point.get("suggestion"):
            rows.append(f"- 建议（仅建议，未经裁决）：{point['suggestion']}")
        quoted = cite(entry["version"], point.get("evidence"))
        rows += ([f"- 原话：{quoted}"] if quoted else []) + [""]
    if not pending:
        rows += ["（没有仍未决的事项）", ""]

    rows += ["## 会议原结论及采纳情况", ""]
    for entry in results:
        conclusion = entry.get("conclusion") or {}
        said = (f"{conclusion.get('text', '')}（适用：{conclusion.get('scope', '')}"
                + (f"；原话 {q}" if (q := cite(entry["version"], conclusion.get("evidence"))) else "") + "）"
                ) if conclusion else "会上没有收口结论"
        taken = []
        if entry["chosen"]:
            taken.append(f"人选「{entry['chosen']['label'] or entry['chosen']['key']}」"
                         f"（{entry['chosen']['key']}）")
        counts = len(entry["changes"]) + len(entry["added"])
        taken.append(f"采纳 {counts} 条变化" if counts else "没有引出文档变化，相关段落保持原文")
        if entry["open_points"]:
            taken.append(f"保留 {len(entry['open_points'])} 项未决")
        rows.append(f"- {entry['ref']}：{said}——{'；'.join(taken)}")
    if not results:
        rows.append("（没有生效的会议话题）")
    return "\n".join(rows) + "\n"


def refresh_stale(feature_root: Path, notes: dict, contract: dict) -> bool:
    """`doc-refresh.md` 跟不跟得上现在的会议结论与裁决。还没有任何生效结果时不要求它在。"""
    path = feature_root.joinpath(*REFRESH)
    results = effective_meeting_results(notes, contract)
    if not path.is_file():
        return bool(results)
    return path.read_text(encoding="utf-8").replace("\r\n", "\n") != render(feature_root, results)


def write_refresh(feature_root: Path, contract: dict) -> None:
    """按现在的结论与裁决重写 `doc-refresh.md`；没有会议结论也没写过它时不落文件。"""
    notes = meeting.read_notes(feature_root, [])
    path = feature_root.joinpath(*REFRESH)
    if notes or path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(feature_root, effective_meeting_results(notes, contract)),
                        encoding="utf-8")


def topic_options(feature_root: Path, version: str, item: str) -> list[dict]:
    """`decide --gate meeting` 的选项集：取自会议结论里那个话题的 options，脚本只认 key。"""
    section = meeting.read_notes(feature_root, []).get(version) or {}
    topic = next((t for t in section.get("topics") or [] if str(t.get("id")) == item), None)
    if not topic or not topic.get("ask"):
        raise FlowError(f"会议结论「{version}」里没有要问人的话题「{item}」——--meeting 写 <主名>@<sha8>，"
                        "--item 写话题 id；待裁决的条目列在 `status` 的 meetings 里")
    return [{"key": o.get("key"), "label": o.get("label", "")} for o in topic.get("options") or []]


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
        for topic in section.get("topics") or []:
            if not isinstance(topic, dict):
                continue
            tid = str(topic.get("id"))
            gate = signed.get((key, tid))
            conclusion = topic.get("conclusion") or {}
            row = {
                "version": key, "topic": tid, "ownership": topic.get("ownership"),
                "changes": [f"{c.get('kind', '')} {c.get('doc', '')} {c.get('section', '')}："
                            f"{c.get('after', '')}" for c in topic.get("changes") or []
                            if isinstance(c, dict)],
                "conclusion": conclusion.get("text", ""),
                "open_points": [o.get("what", "") for o in topic.get("open_points") or []
                                if isinstance(o, dict)],
                "ask": bool(topic.get("ask")),
                "settled": gate.get("chosen") if gate else None,
                "version_confirmed": key in shown,
            }
            if folder is not None:
                row["evidence"] = [meeting.line_ref(feature_root, folder, r)
                                   for r in meeting.ranges(conclusion.get("evidence"))]
            if topic.get("ask") and not gate:
                row["ask_reason"] = topic.get("ask_reason")
                row["recommend"] = topic.get("recommend")
                row["options"] = [{"key": o.get("key"), "label": o.get("label", "")}
                                  for o in topic.get("options") or [] if isinstance(o, dict)]
            rows.append(row)
    return rows


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
