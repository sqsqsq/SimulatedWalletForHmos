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


def _keep_replaced(feature_root: Path, previous: dict, pending: list[str], new_id: str) -> str:
    """把被替换问法里还没答的题、依据与出处原样留一份：原问题不能因为临时问法被覆写就消失。

    落在现有人答目录（`AR/story-src/answers/`），按旧 ask_id 一份；只增不改。
    『为何失效』由作者按本次真实新事实写进当前分析或本轮 notes——脚本不知道原因，不代写。
    """
    path = feature_root.joinpath("AR", "story-src", "answers", f"被替换问法-{previous['ask_id']}.json")
    if path.is_file():
        return path.relative_to(feature_root).as_posix()
    body = {"ask_id": previous["ask_id"], "replaced_by": new_id, "replaced_at": _now(),
            "items": [it for it in previous.get("items") or [] if str(it.get("item_id")) in pending]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path.relative_to(feature_root).as_posix()


def _now() -> str:
    from datetime import datetime  # noqa: PLC0415 —— 只在留档被替换问法时取时刻
    return datetime.now().astimezone().isoformat(timespec="seconds")


def build_questions(feature_root: Path, contract: dict, questions_file: str) -> dict:
    """生成一次集中问法并写侧车；同一内容重复调用幂等。

    上一组还有没答完的题时照新输入替换：被替换的**整题**（问题、候选、依据、出处）带在返回里，
    并在现有人答目录留一份原件——原问题与依据不因临时问法被覆写而消失。替换是作者看过真实新事实
    后的主动动作，脚本不悄悄覆盖；『为何失效』由作者写进当前分析或本轮 notes。
    """
    items = read_questions_file(Path(questions_file))
    previous = _read(feature_root)
    pending: list[str] = []
    if previous and previous.get("kind") == DESIGN_KIND and previous.get("ask_id"):
        answered = answered_item_ids(feature_root, contract, previous["ask_id"])
        pending = [str(it.get("item_id")) for it in previous.get("items") or []
                   if str(it.get("item_id")) not in answered]
    ask = _write(feature_root, {"kind": DESIGN_KIND,
                                "round": contract["rounds"][-1].get("round"), "items": items})
    if pending and previous.get("ask_id") != ask["ask_id"]:
        kept = _keep_replaced(feature_root, previous, pending, ask["ask_id"])
        ask["replaced_unanswered"] = [it for it in previous.get("items") or []
                                      if str(it.get("item_id")) in pending]
        ask["replaced_kept"] = kept
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
#: 分句边界：识别单位是整句选择或边界明确的选项回应，不从句中任意位置抓编号。
#: ASCII 句点不作边界：「2.5 个月」不能被拆成「2」；句首枚举仍按带句点的整句核。
CLAUSE = re.compile(r"[，。；！？,;!?\n]+")
#: 分句里否定某一项的说法：否定词直接管辖编号。否定句仍逐字留存，不替人改。
NEGATION = re.compile(
    r"(?:不选|不要选|不要|别选|别|不采用|不按|不是|排除|暂不|未选|不建议)"
    r"\s*(?:选|用|按|采用|要)?\s*(?:第\s*)?(\d+)\s*(?:项|个|条)?")


def _negated(clause: str, options: list[dict]) -> set[int]:
    """这一分句明确否掉了哪几项：只认否定词直接管辖的选项编号。"""
    nos = {o["no"] for o in options}
    return {int(m.group(1)) for m in NEGATION.finditer(clause)} & nos


def _affirmed(clause: str, options: list[dict]) -> set[int]:
    """这一分句明确点名了哪几项：整句编号、完整「第 n 项/选 n」、句首枚举（可带附言）。

    只认整句或句子开头的选项回应：「第 2 份材料还没到」「等第 2 次会议开完」「1 份 PRD 够了」
    都不是对某一项的选择；编号出现在分句中间时不从里面截出一个选择。
    """
    text = clause.strip()
    out: set[int] = set()
    for o in options:
        n = o["no"]
        if (re.fullmatch(rf"(?:第\s*)?{n}\s*(?:项|个|条)?[。．.!！]?", text)
                or re.fullmatch(rf"第\s*{n}\s*(?:项|个|条)[。．.!！]?", text)
                or re.fullmatch(rf"(?:选|选择)\s*(?:第\s*)?{n}\s*(?:项|个|条)?[。．.!！]?", text)
                or re.match(rf"^(?:第\s*)?{n}\s*(?:项|个|条)?\s*[.．、)）](?!\d)", text)):
            out.add(n)
    return out


def pick_explicit(options: list[dict], reply: str) -> dict:
    """人明确指到一项才返回值：整句选择、边界明确的选项回应，或整句照抄该项标签。

    完整标签先核（含内置标点时也按整句比）；复合选择按分句核出唯一肯定项（「不选 1，选 2」）。
    片段命中、叙述里的序号、只否定或同时指到几项都不签认——作者保留原话请人澄清，
    原话仍逐字留存。
    """
    text = str(reply or "")
    for o in options:
        if o["label"] and PUNCT.sub("", text) == PUNCT.sub("", o["label"]):
            return o
    affirmed: dict[int, dict] = {}
    negated: set[int] = set()
    for clause in CLAUSE.split(text):
        if not clause.strip():
            continue
        negated |= _negated(clause, options)
        for no in _affirmed(clause, options):
            affirmed[no] = next(o for o in options if o["no"] == no)
    hits = [affirmed[no] for no in sorted(affirmed) if no not in negated]
    listed = "、".join(f"{o['no']}={o['key']}" for o in options)
    if not hits:
        raise FlowError("原话没有明确选到任何一项：按材料门的问法请人直接选一项（选项编号或完整标签）；"
                        "只是说明材料缺口的话保留缺口，不在其中签认选择；拿不准就再问人一次。"
                        f"现有：{listed}")
    if len(hits) > 1:
        raise FlowError("原话同时指到了几项：" + "、".join(str(o["no"]) for o in hits) + "——原话只认一项")
    return hits[0]


def answered_item_ids(feature_root: Path, contract: dict, ask_id: str) -> set[str]:
    """本操作已经录过原话的题号。已答的题不再处于待答集合。

    按操作身份读：init 在材料 round 的 `answers`，开着 update 在该操作的 `record.answers`；
    不拿另一轮或另一次操作的同名题抵扣。
    """
    rid = str((contract.get("update") or {}).get("open") or "")
    if rid:
        rec = _update_record(feature_root, rid)
        answers = rec.get("answers") or []
    else:
        rounds = contract.get("rounds") or []
        answers = (rounds[-1].get("answers") if rounds else None) or []
    return {str(a.get("item_id")) for a in answers if str(a.get("ask_id")) == str(ask_id)}


def _update_record(feature_root: Path, rid: str) -> dict:
    """开着的那一轮 update 的记录；读不出按流程缺口报，不拿空记录冒充没答过。"""
    path = feature_root.joinpath("AR", "story-src", "updates", rid, "record.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise FlowError(f"{path.relative_to(feature_root).as_posix()} 读不出来（{exc}）："
                        "说不出这一轮已经答过哪些题，先按 `status` 修好这一轮的记录") from exc
    if not isinstance(payload, dict):
        raise FlowError(f"{path.relative_to(feature_root).as_posix()} 不是对象：说不出这一轮的问答记录")
    return payload


def pending_view(feature_root: Path, ask: dict, contract: dict) -> dict:
    """这一次待答状态：**同一次读取**回答已答/未答，并从**未答子集**渲染唯一展示块。

    返回的 `ask.block` 就是本次要交人的那条消息，`pending` 与它同一来源；盘上的完整问法
    不动，`decide` 仍按完整问法核对 ask_id 与题号。同一个状态不再为拼展示而重读记录。
    """
    answered = answered_item_ids(feature_root, contract, ask["ask_id"])
    pending = [str(it["item_id"]) for it in ask.get("items") or [] if str(it["item_id"]) not in answered]
    left = {**ask, "items": [it for it in ask.get("items") or [] if str(it["item_id"]) in pending]}
    return {**left, "pending": pending,
            "answered": [str(it["item_id"]) for it in ask.get("items") or [] if str(it["item_id"]) in answered],
            "block": block(left)}


def clear(feature_root: Path) -> None:
    (feature_root / Path(*ASK)).unlink(missing_ok=True)
