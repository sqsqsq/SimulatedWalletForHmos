"""会议的有效结果：模型的判断（`meeting-notes.json`）加人的裁决（契约里的关卡记录），才是人最终接受的。

派生只有一处（`effective_meeting_results`）：`status` 的路由与 `AR/story-src/doc-refresh.md`
的渲染都调它——提取稿的会议输入与给人的文档刷新清单是同一份渲染件。

生效规则：

- 要问人的话题（`ask`）只按人签的那个选项的 `effect` 生效，没签不生效；
- 不问人的话题，要等它所在的会议版本在第一级材料关卡上摆给人、人表了态才生效——
  第一级 accepted 的记录里带着当时摆出的版本（`meetings`），人对摆出的整体表态就是确认；
- 归属最终不是本需求的，只记不消费；
- 旧决定只被某个已签选项的 `supersedes` 指到才失效，新版本到了、推翻未签都不撤销它。

只读契约与会议结论，写的只有 `doc-refresh.md`；不建会议状态机：版本靠目录与指纹，生效靠派生。
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
            for t in section.get("topics") or [] if t.get("ask") and (key, t.get("id")) not in signed]


def effective_meeting_results(notes: dict, contract: dict) -> list[dict]:
    """每个生效话题一项：会上定的变化（带原话编号）、人补定的变化（带人的原话）、结论与它替代的旧决定。"""
    shown = presented(contract)
    signed = {(g.get("meeting"), g.get("item")): g for g in _accepted(contract, "meeting")}
    out: list[dict] = []
    for key, section in sorted(notes.items()):
        for t in section.get("topics") or []:
            changes = {str(c.get("id")): c for c in t.get("changes") or []}
            if t.get("ask"):
                g = signed.get((key, t.get("id")))
                effect = next((o.get("effect") or {} for o in t.get("options") or []
                               if g and o.get("key") == g.get("chosen")), None)
                if effect is None:
                    continue
                owner = effect.get("ownership", t.get("ownership"))
                picked = [changes[c] for c in effect.get("apply_changes") or [] if c in changes]
                added = [{**c, "basis": g.get("basis", "")} for c in effect.get("add_changes") or []]
                supersedes = effect.get("supersedes") or []
            elif key in shown:
                owner, picked, added, supersedes = t.get("ownership"), list(changes.values()), [], []
            else:
                continue
            if owner == "ours":
                out.append({"ref": f"{key}/{t.get('id')}", "version": key, "conclusion": t.get("conclusion"),
                            "changes": picked, "added": added, "supersedes": supersedes})
    gone = {s for e in out for s in e["supersedes"]}
    return [e for e in out if e["ref"] not in gone]


def render(results: list[dict]) -> str:
    """`doc-refresh.md`：每条生效的变化一节，讨论收敛而原文不变的结论单列。"""
    rows = ["# 会议有效结果与文档刷新清单", "",
            "<!-- 由 story_flow.py 从 meeting-notes.json 与关卡裁决派生；改判断回会议结论或重新裁决，手改无效 -->", "",
            "## 生效的变化", ""]
    changed = [(e, c, "") for e in results for c in e["changes"]] + \
        [(e, c, c.get("basis", "")) for e in results for c in e["added"]]
    for e, c, basis in changed:
        source = (f"人工补定，原话「{basis}」" + (f"；落定遗留 {c.get('resolves')}" if c.get("resolves") else "")
                  if basis else f"会上定的，原话 {e['version']} {'、'.join(c.get('evidence') or [])}")
        rows += [f"### {c.get('doc', '')} {c.get('section', '')}（{e['ref']}）", "",
                 f"- 类型：{c.get('kind', '')}", f"- 改前：{c.get('before', '')}", f"- 改后：{c.get('after', '')}",
                 f"- 影响：{c.get('impact', '')}", f"- 来源：{source}", ""]
    rows += ([] if changed else ["（没有生效的变化）", ""]) + ["## 原文已确认", ""]
    kept = [e for e in results if e["conclusion"] and not e["changes"] and not e["added"]]
    rows += [f"- {e['ref']}：{e['conclusion'].get('text', '')}（适用：{e['conclusion'].get('scope', '')}；"
             f"原话 {'、'.join(e['conclusion'].get('evidence') or [])}）" for e in kept] or ["（没有）"]
    return "\n".join(rows) + "\n"


def refresh_stale(feature_root: Path, notes: dict, contract: dict) -> bool:
    """`doc-refresh.md` 跟不跟得上现在的会议结论与裁决。还没有任何生效结果时不要求它在。"""
    path = feature_root.joinpath(*REFRESH)
    results = effective_meeting_results(notes, contract)
    if not path.is_file():
        return bool(results)
    return path.read_text(encoding="utf-8").replace("\r\n", "\n") != render(results)


def write_refresh(feature_root: Path, contract: dict) -> None:
    """按现在的结论与裁决重写 `doc-refresh.md`；没有会议结论也没写过它时不落文件。"""
    notes = meeting.read_notes(feature_root, [])
    path = feature_root.joinpath(*REFRESH)
    if notes or path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(effective_meeting_results(notes, contract)), encoding="utf-8")


def topic_options(feature_root: Path, version: str, item: str) -> list[dict]:
    """`decide --gate meeting` 的选项集：取自会议结论里那个话题的 options，脚本只认 key。"""
    section = meeting.read_notes(feature_root, []).get(version) or {}
    topic = next((t for t in section.get("topics") or [] if str(t.get("id")) == item), None)
    if not topic or not topic.get("ask"):
        raise FlowError(f"会议结论「{version}」里没有要问人的话题「{item}」——--meeting 写 <主名>@<sha8>，"
                        "--item 写话题 id；待裁决的条目列在 `status` 的 action 里")
    return [{"key": o.get("key"), "label": o.get("label", "")} for o in topic.get("options") or []]
