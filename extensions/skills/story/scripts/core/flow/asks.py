"""停等的问法：选项、顺序、推荐与缺口由脚本从契约生成，模型原样转述给人。

`status` 到了停等点就生成问法并写侧车 `AR/story-src/.ask.json`；`decide` 只收带同一个
`ask_id` 的人签，把人的原话映射到选项。问法在问人之前就在盘上，所以「先签后问」写不进契约；
选项块由脚本排好，所以人看到的与契约记下的是同一套选项、同一个顺序。

模型自己的判断用 `decide --propose` 记为提议（`by: model`），不推进流程；下一次停等时，
脚本把还没被人确认的提议列进问法，请人确认。
"""
from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path

from materials import meeting

from flow.state import FlowError
from flow.inputs import (
    GAPS, MATERIAL_REQUEST_KEYS, material_options, read_gaps, read_sidecar,
    split_carrier_options)
from flow.meetings import pending_asks, topic_options

ASK = ("AR", "story-src", ".ask.json")
#: 选项标签里的占位，生成问法时换成本单编号。
FEATURE_MARK = "<单>"


def _numbered(options: list[dict]) -> list[dict]:
    return [{"no": i + 1, "key": str(o["key"]), "label": str(o.get("label") or "")}
            for i, o in enumerate(options)]


def _recommend(options: list[dict], key: str | None, why: str | None) -> dict | None:
    hit = next((o for o in options if o["key"] == key), None)
    return {"no": hit["no"], "key": hit["key"], "why": why or ""} if hit else None


def _material(feature_root: Path) -> dict:
    gaps = read_gaps(feature_root)
    if gaps is None:
        raise FlowError(f"还没写 {'/'.join(GAPS)}：先盘点材料再问")
    feature = feature_root.name
    options = _numbered([{"key": o["key"], "label": str(o["label"]).replace(FEATURE_MARK, feature)}
                         for o in material_options()])
    request = next(o["key"] for o in options if o["key"] in MATERIAL_REQUEST_KEYS)
    other = next(o["key"] for o in options if o["key"] != request)
    return {"options": options,
            "recommend": _recommend(options, request if gaps["missing"] else other, gaps["why"]),
            "missing": gaps["missing"], "why": gaps["why"]}


def _scope(contract: dict) -> dict:
    current = contract["rounds"][-1]
    raw = current.get("scope_options") or []
    options = _numbered(raw)
    pick = next((o for o in raw if str(o.get("recommend") or "").strip()), None)
    return {"options": options,
            "recommend": _recommend(options, pick and str(pick["key"]),
                                    pick and str(pick["recommend"]))}


def _split(contract: dict) -> dict:
    parts = split_carrier_options(contract["rounds"][-1])
    options = _numbered([{"key": p["key"], "label": p["scope"]} for p in parts])
    return {"options": options, "recommend": None}


def _meeting(feature_root: Path, contract: dict) -> dict:
    items = []
    for ref in pending_asks(meeting.read_notes(feature_root, []), contract):
        version, item = ref.rsplit("/", 1)
        section = meeting.read_notes(feature_root, []).get(version) or {}
        topic = next(t for t in meeting.topics_of(section) if str(t.get("id")) == item)
        options = _numbered(topic_options(feature_root, version, item))
        items.append({"meeting": version, "item": item, "question": str(topic.get("question")),
                      "options": options,
                      "recommend": _recommend(options, topic.get("recommend"),
                                              topic.get("recommend_why"))})
    return {"items": items}


def _proposals(contract: dict, gate: str, options: list[dict]) -> list[dict]:
    """还没被人确认的提议，带上它指的那一项的标签。"""
    out = []
    for p in contract.get("proposals") or []:
        if p.get("gate") != gate or p.get("resolved"):
            continue
        hit = next((o for o in options if p.get("chosen") in (o["key"], str(o["no"]))), None)
        out.append({"chosen": p.get("chosen"), "label": hit["label"] if hit else "",
                    "why": p.get("why", ""), **({"item": p["item"]} if p.get("item") else {})})
    return out


def block(ask: dict) -> str:
    """停等消息里原样照抄的选项块：每项一行，推荐单独一行。"""
    def lines(options: list[dict], recommend: dict | None) -> list[str]:
        out = [f"{o['no']}. {o['label']}" for o in options]
        if recommend:
            out.append(f"推荐：{recommend['no']}" + (f"（{recommend['why']}）" if recommend["why"] else ""))
        return out

    if ask["gate"] == "meeting":
        rows: list[str] = []
        for it in ask["items"]:
            rows.append(f"【{it['item']}】{it['question']}")
            rows.extend(lines(it["options"], it["recommend"]))
        body = rows
    else:
        body = lines(ask["options"], ask["recommend"])
    for p in ask.get("proposals") or []:
        body.append(f"待你确认的提议：{p['label'] or p['chosen']}（{p['why']}）")
    return "\n".join(body)


def build(feature_root: Path, contract: dict, step: str) -> dict | None:
    """`step` 是停等点时生成问法并写侧车；不是停等点返回 None。"""
    if not step.startswith("await_gate:"):
        return None
    gate = step.split(":", 1)[1]
    if gate == "material_scope":
        body = _material(feature_root)
    elif gate == "scope_decision":
        body = _scope(contract)
    elif gate == "split_carrier":
        body = _split(contract)
    else:
        body = _meeting(feature_root, contract)
    options = body.get("options") or [o for it in body.get("items", []) for o in it["options"]]
    ask = {"gate": gate, "round": contract["rounds"][-1].get("round"), **body,
           "proposals": _proposals(contract, gate, options)}
    ask["ask_id"] = sha256(json.dumps(ask, ensure_ascii=False, sort_keys=True)
                           .encode("utf-8")).hexdigest()[:8]
    ask["block"] = block(ask)
    path = feature_root / Path(*ASK)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ask, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return ask


def current(feature_root: Path, ask_id: str, gate: str) -> dict:
    """`decide` 取本次的问法：侧车在、`ask_id` 对得上、问的就是这一级。"""
    ask = read_sidecar(feature_root, ASK)
    if not isinstance(ask, dict):
        raise FlowError("没有待回答的问法：先跑 `story_flow.py status`，把它给出的选项块原样摆给人，"
                        "人回话之后再记。人签只能记在问过之后")
    if str(ask.get("ask_id")) != str(ask_id or "").strip():
        raise FlowError(f"--ask「{ask_id}」不是当前问法（{ask.get('ask_id')}）：问法换过了，"
                        "按 `status` 给出的当前选项重新问人")
    if ask.get("gate") != gate:
        raise FlowError(f"当前问法是 {ask.get('gate')} 级，这一笔记的是 {gate}")
    return ask


#: 比对原话与标签时去掉的标点与空白
PUNCT = re.compile(r"[\s，。、；：！？,.;:!?「」“”\"'（）()]+")


def _number_forms(no: int) -> list[str]:
    """编号的说法：第 n、n.、n）、选 n，或整句就是 n。日常话里的数（「1 份」「等 1 天」）不算。"""
    n = rf"(?<![\d.]){no}"
    return [rf"^\s*{no}\s*[.。．、)）]?\s*$", rf"第\s*{no}(?!\d)", rf"{n}[.．](?!\d)",
            rf"{n}\s*[)）]", rf"选\s*{no}(?!\d)"]


def _marks(option: dict, reply: str) -> bool:
    """原话里有没有指到这一项：编号的说法、整句标签，或者原话就是标签里的一句话。键是机器名，不参与。"""
    if any(re.search(form, reply) for form in _number_forms(option["no"])):
        return True
    if option["label"] and option["label"] in reply:
        return True
    core = PUNCT.sub("", reply)
    return len(core) >= 4 and core in PUNCT.sub("", option["label"])


def map_reply(options: list[dict], reply: str, chosen: str | None,
              recommend: dict | None) -> tuple[dict, str]:
    """把人的原话映射到一项，返回 (选项, 映射来源)。

    原话里恰好指到一项（编号的说法、标签，或说「按推荐」）就按原话定，来源记 `reply`；
    原话是自己的话、没指到任何一项时，由 `--chosen` 指明，来源记 `model`；
    `--chosen` 与原话指到的那一项对不上时拒绝——记的必须是人说的那一项。
    """
    hits = [o for o in options if _marks(o, reply)]
    if recommend and "推荐" in reply and not hits:
        hits = [o for o in options if o["key"] == recommend["key"]]
    pick = None
    if chosen:
        pick = next((o for o in options if chosen in (o["key"], str(o["no"]))), None)
        if pick is None:
            raise FlowError(f"--chosen「{chosen}」不在本次选项里（现有："
                            + "、".join(f"{o['no']}={o['key']}" for o in options) + "）")
    if len(hits) == 1:
        if pick and pick is not hits[0]:
            raise FlowError(f"人的原话指的是第 {hits[0]['no']} 项（{hits[0]['label']}），"
                            f"--chosen 却是第 {pick['no']} 项：记人说的那一项")
        return hits[0], "reply"
    if pick is None:
        raise FlowError("原话" + ("同时指到了几项" if hits else "没指到任何一项")
                        + "：用 --chosen 写明人选的是哪一项；拿不准就再问人一次")
    if hits and pick not in hits:
        raise FlowError(f"原话指到的是 {'、'.join(str(o['no']) for o in hits)}，--chosen 不在其中")
    return pick, "model"


def clear(feature_root: Path) -> None:
    (feature_root / Path(*ASK)).unlink(missing_ok=True)

