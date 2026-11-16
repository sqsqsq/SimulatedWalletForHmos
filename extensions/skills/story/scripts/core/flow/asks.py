"""停等的问法：脚本排版、脚本绑定，模型原样转述给人。

两类问法共用同一个侧车 `AR/story-src/.ask.json`：

- **材料确认**：`status` 到了材料关卡就生成，选项来自章节合同，推荐按缺口文件算；
- **设计后必要问答**：首次原生质询的真实回复到达后，作者把本轮已知、符合必要问人三条件的问题
  写成一份文件交给 `status --questions-file`，脚本校形状后生成**一次集中 ask**。问法内容与
  `ask_id` 一起落盘，`decide` 只按 `--ask/--item` 读取这份问法，不让人在记录时重填问题。

`ask_id` 由完整规范化问法内容派生（不含派生出来的 id、展示块与待答状态）；读回时按同一算法
重算身份，字段被改却沿用旧 id 的拒绝。问法在问人之前就在盘上，所以「先签后问」写不进契约。
"""
from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path

from flow.state import FlowError
from flow.inputs import GAPS, MATERIAL_REQUEST_KEYS, material_options, read_gaps

ASK = ("AR", "story-src", ".ask.json")
#: 选项标签里的占位，生成问法时换成本单编号。
FEATURE_MARK = "<单>"
#: 设计后必要问答的 ask 种类：与材料问法区分，不写进 flow.gates，也不产生 accepted 业务状态。
DESIGN_KIND = "design_questions"
MATERIAL_KIND = "material_scope"
#: 设计问答文件里每项的字段：问题、候选、建议、为何现在问、出处。
QUESTION_FIELDS = ("item_id", "question", "options", "recommend", "reason", "source_ref")
#: 派生的展示与状态字段：不参与 ask_id 的内容身份。
DERIVED = ("ask_id", "block", "pending", "answered", "replaced_unanswered")


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


def _identity(ask: dict) -> str:
    """问法的内容身份：完整规范化内容去掉派生字段后的摘要。"""
    body = {k: v for k, v in ask.items() if k not in DERIVED}
    text = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(text.encode("utf-8")).hexdigest()[:8]


def _write(feature_root: Path, ask: dict) -> dict:
    ask = {k: v for k, v in ask.items() if k not in DERIVED}
    ask["ask_id"] = _identity(ask)
    ask["block"] = block(ask)
    path = feature_root / Path(*ASK)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ask, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return ask


def block(ask: dict) -> str:
    """停等消息里原样照抄的展示块：每项一行，推荐与出处单独成行。"""
    if ask.get("kind") == DESIGN_KIND:
        rows: list[str] = []
        for item in ask["items"]:
            rows.append(f"【{item['item_id']}】{item['question']}")
            rows.extend(f"{i}. {label}" for i, label in enumerate(item["options"], 1))
            if item.get("recommend"):
                rows.append(f"建议：{item['recommend']}")
            rows.append(f"为什么现在问：{item['reason']}")
            rows.append(f"出处：{item['source_ref']}")
        return "\n".join(rows)

    def lines(options: list[dict], recommend: dict | None) -> list[str]:
        out = [f"{o['no']}. {o['label']}" for o in options]
        if recommend:
            out.append(f"推荐：{recommend['no']}" + (f"（{recommend['why']}）" if recommend["why"] else ""))
        return out

    return "\n".join(lines(ask["options"], ask["recommend"]))


def build_material(feature_root: Path, contract: dict) -> dict:
    """材料关卡：选项来自章节合同，推荐按缺口算，写侧车交给 `decide` 核对。"""
    return _write(feature_root, {"kind": MATERIAL_KIND, "gate": MATERIAL_KIND,
                                 "round": contract["rounds"][-1].get("round"), **_material(feature_root)})


def read_questions_file(path: Path) -> list[dict]:
    """读并校设计问答文件：只校形状与本次定位，问题内容是否该问由作者判断。

    形状是 `{items:[{item_id, question, options, recommend, reason, source_ref}]}`；
    选项与建议可为空，`source_ref` 指已取得的原件或本轮原生质询报告。
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise FlowError(f"设计问答文件 {path} 读不出来（{exc}）") from exc
    except ValueError as exc:
        raise FlowError(f"设计问答文件 {path} 不是合法 JSON（{exc}）") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list) or not payload["items"]:
        raise FlowError(f"设计问答文件 {path.name} 须是对象且 items 是非空数组："
                        f"{{items:[{{{', '.join(QUESTION_FIELDS)}}}]}}")
    out, problems, seen = [], [], set()
    for i, raw in enumerate(payload["items"], 1):
        where = f"第 {i} 项"
        if not isinstance(raw, dict):
            problems.append(f"{where}不是对象")
            continue
        item_id = str(raw.get("item_id") or "").strip()
        question = str(raw.get("question") or "").strip()
        reason = str(raw.get("reason") or "").strip()
        source_ref = str(raw.get("source_ref") or "").strip()
        options = raw.get("options")
        recommend = str(raw.get("recommend") or "").strip()
        if not item_id:
            problems.append(f"{where}缺 item_id（本次问答内的定位号）")
        elif item_id in seen:
            problems.append(f"item_id「{item_id}」重复：本次问答内每题一个定位号")
        seen.add(item_id)
        if not question:
            problems.append(f"{where}缺 question：写清要人定什么")
        if not reason:
            problems.append(f"{where}缺 reason：写明为何符合必要问人的三条件、当前用户有权回答")
        if not source_ref:
            problems.append(f"{where}缺 source_ref：指已取得原件或本轮原生质询报告，不写第二份目标/版本")
        if not isinstance(options, list) or not all(isinstance(o, str) and o.strip() for o in options):
            problems.append(f"{where}的 options 须是字符串数组（候选做法，可为空数组）")
            options = []
        else:
            options = [o.strip() for o in options]
            if len(set(options)) != len(options):
                problems.append(f"{where}的 options 有重复项")
        if recommend and options and recommend not in options:
            problems.append(f"{where}的 recommend 不在 options 里：建议只能是摆出的候选之一")
        out.append({"item_id": item_id, "question": question, "options": options,
                    "recommend": recommend, "reason": reason, "source_ref": source_ref})
    if problems:
        raise FlowError("设计问答文件立不住：" + "；".join(problems))
    return out


def build_questions(feature_root: Path, contract: dict, questions_file: str) -> dict:
    """生成一次集中问法并写侧车；同一内容重复调用幂等。

    上一组还有没答完的题时照新输入替换，并把被替换的题号带在返回里——替换是作者看过新事实后的
    主动动作，脚本不悄悄覆盖；原问题与依据仍在契约与当前分析里。
    """
    items = read_questions_file(Path(questions_file))
    previous = _read(feature_root)
    pending = pending_items(previous, contract) if previous and previous.get("kind") == DESIGN_KIND else []
    ask = _write(feature_root, {"kind": DESIGN_KIND,
                                "round": contract["rounds"][-1].get("round"), "items": items})
    if pending and previous.get("ask_id") != ask["ask_id"]:
        ask["replaced_unanswered"] = pending
    return ask


def _read(feature_root: Path) -> dict | None:
    path = feature_root / Path(*ASK)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise FlowError(f"{path.name} 不是合法 JSON（{exc}）：重跑 `status` 重新生成问法") from exc
    if not isinstance(payload, dict):
        raise FlowError(f"{path.name} 不是对象：重跑 `status` 重新生成问法")
    return payload


def current_design(feature_root: Path) -> dict | None:
    """当前设计问答的问法；没有或不是设计问答返回 None。

    读取时按生成时的同一算法重算内容身份：字段被改却沿用旧 ask_id 的拒绝，
    不能只比调用参数与文件里自报的 id。
    """
    payload = _read(feature_root)
    if payload is None or payload.get("kind") != DESIGN_KIND:
        return None
    stored = str(payload.get("ask_id") or "")
    if not stored or _identity(payload) != stored:
        raise FlowError("当前问法的内容与 ask_id 对不上（文件被改过）："
                        "重跑 `status --questions-file` 按当前输入重新绑定，不沿用旧问法记人答")
    if not isinstance(payload.get("items"), list) or not payload["items"]:
        raise FlowError("当前问法缺 items：重跑 `status --questions-file` 重新生成")
    return payload


def current_material(feature_root: Path, ask_id: str) -> dict:
    """`decide --gate material_scope` 取本次问法：侧车在、ask_id 对得上、问的就是材料。"""
    ask = _read(feature_root)
    if not isinstance(ask, dict):
        raise FlowError("没有待回答的问法：先跑 `story_flow.py status`，把它给出的问法原样摆给人，"
                        "人回话之后再记。人签只能记在问过之后")
    if str(ask.get("ask_id")) != str(ask_id or "").strip():
        raise FlowError(f"--ask「{ask_id}」不是当前问法（{ask.get('ask_id')}）：问法换过了，"
                        "按 `status` 给出的当前问法重新问人")
    if ask.get("kind") != MATERIAL_KIND or ask.get("gate") != MATERIAL_KIND:
        raise FlowError(f"当前问法是 {ask.get('kind') or ask.get('gate')}，这一笔记的是材料确认")
    if _identity(ask) != str(ask.get("ask_id") or ""):
        raise FlowError("当前问法的内容与 ask_id 对不上（文件被改过）：重跑 `status` 重新生成")
    return ask


#: 比对原话与标签时去掉的标点与空白
PUNCT = re.compile(r"[\s，。、；：！？,.;:!?「」“”\"'（）()]+")
#: 否定说法：紧随其后的编号不构成选择（「不选 1」「不要第 2 项」）。否定句仍逐字留存，不替人改。
NEGATION = (r"(?:不选|不要选|不要|别选|别|不采用|不按|不是|排除|暂不|未选|不建议)"
            r"\s*(?:选|用|按|采用|要)?\s*(?:第\s*)?")


def _negated(option: dict, reply: str) -> bool:
    """这一项被原话明确否掉了没有。"""
    return re.search(NEGATION + rf"{option['no']}(?!\d)", reply) is not None


def _number_forms(no: int) -> list[str]:
    """编号的说法：第 n、n.、n）、选 n，或整句就是 n。日常话里的数（「1 份」「等 1 天」）不算。"""
    n = rf"(?<![\d.]){no}"
    return [rf"^\s*{no}\s*[.。．、)）]?\s*$", rf"第\s*{no}(?!\d)", rf"{n}[.．](?!\d)",
            rf"{n}\s*[)）]", rf"选\s*{no}(?!\d)"]


def pick_explicit(options: list[dict], reply: str) -> dict:
    """人明确指到一项才返回值：编号的说法，或整句照抄该项标签。

    片段命中、模型替人挑一项，都不能当成人对整项内容的批准；被原话否掉的项（「不选 1」）
    也不参与选择。没有明确选择就重问，原话仍逐字留存。
    """
    hits = [o for o in options
            if not _negated(o, reply)
            and (any(re.search(form, reply) for form in _number_forms(o["no"]))
                 or (o["label"] and PUNCT.sub("", reply) == PUNCT.sub("", o["label"])))]
    if len(hits) == 1:
        return hits[0]
    listed = "、".join(f"{o['no']}={o['key']}" for o in options)
    if not hits:
        raise FlowError("原话没有明确选到任何一项：用编号（第 n / n. / 选 n）或整句照抄一项的标签；"
                        f"拿不准就再问人一次。现有：{listed}")
    raise FlowError("原话同时指到了几项：" + "、".join(str(o["no"]) for o in hits) + "——原话只认一项")


def answered_item_ids(contract: dict, ask_id: str) -> set[str]:
    """这一组问法已经录过原话的题号。已答的题不再处于待答集合。"""
    return {str(a.get("item_id")) for r in contract.get("rounds") or []
            for a in r.get("answers") or [] if str(a.get("ask_id")) == str(ask_id)}


def pending_items(ask: dict | None, contract: dict) -> list[str]:
    if not ask or ask.get("kind") != DESIGN_KIND:
        return []
    answered = answered_item_ids(contract, ask["ask_id"])
    return [str(it["item_id"]) for it in ask.get("items") or [] if str(it["item_id"]) not in answered]


def with_answered(ask: dict, contract: dict) -> dict:
    """给展示用的一份问法：带上待答与已答题号，不改盘上的问法。"""
    answered = answered_item_ids(contract, ask["ask_id"])
    return {**ask,
            "pending": pending_items(ask, contract),
            "answered": [str(it["item_id"]) for it in ask.get("items") or []
                         if str(it["item_id"]) in answered]}


def clear(feature_root: Path) -> None:
    (feature_root / Path(*ASK)).unlink(missing_ok=True)