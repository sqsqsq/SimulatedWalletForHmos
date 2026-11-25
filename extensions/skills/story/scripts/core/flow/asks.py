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


def _path_like_item_id(item_id: str) -> bool:
    """题号本身是不是原生地址或机器路径：这类 id 不交给人读，展示层改用本组序号。"""
    return any(mark in item_id for mark in (":", "/", "\\"))


def _display_ids(items: list[dict], order: list[str] | None = None) -> dict[str, str]:
    """展示题号：**整组只做一次稳定映射**，同一个组里不会出现两种命名方式。

    全部 item_id 都适合直接展示时保留原号；只要有一个含原生地址或路径、需要改成人读序号，
    整组统一按**整组原位置**编号。`order` 是全组题号顺序（部分答复后展示只含余题时仍用它），
    只筛余题、序号不重排；记录仍取结构化 items 的原 item_id。
    """
    order = [str(x) for x in (order or [str(it["item_id"]) for it in items])]
    numbered = any(_path_like_item_id(item_id) for item_id in order)
    at = {item_id: i + 1 for i, item_id in enumerate(order)}
    return {str(it["item_id"]): f"第 {at[str(it['item_id'])]} 题" if numbered else str(it["item_id"]) for it in items}


def block(ask: dict, order: list[str] | None = None) -> str:
    """停等消息里原样照抄的展示块：设计问答只含题号、业务问题、候选与必要建议/业务理由。

    出处与机器路径留在结构字段（items 的 source_ref）与导出；`order` 是全组题号顺序，部分答复
    后展示只含余题时用它保住原序。材料问法仍按合同选项与推荐各占一行。
    """
    if ask.get("kind") == DESIGN_KIND:
        ids = _display_ids(ask["items"], order)
        rows: list[str] = []
        for item in ask["items"]:
            rows.append(f"【{ids[str(item['item_id'])]}】{item['question']}")
            rows.extend(f"{i}. {label}" for i, label in enumerate(item["options"], 1))
            if item.get("recommend"):
                rows.append(f"建议：{item['recommend']}")
            if item.get("reason"):
                rows.append(f"为什么现在问：{item['reason']}")
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


def current_material(feature_root: Path, ask_id: str, expected_round: int | None = None) -> dict:
    """`decide --gate material_scope` 取本次问法：侧车在、ask_id 对得上、属于当前轮且问的就是材料。"""
    ask = _read(feature_root)
    if not isinstance(ask, dict):
        raise FlowError("没有待回答的问法：先跑 `story_flow.py status`，把它给出的问法原样摆给人，"
                        "人回话之后再记。人签只能记在问过之后")
    if str(ask.get("ask_id")) != str(ask_id or "").strip():
        raise FlowError(f"--ask「{ask_id}」不是当前问法（{ask.get('ask_id')}）：问法换过了，"
                        "按 `status` 给出的当前问法重新问人")
    if ask.get("kind") != MATERIAL_KIND or ask.get("gate") != MATERIAL_KIND:
        raise FlowError(f"当前问法是 {ask.get('kind') or ask.get('gate')}，这一笔记的是材料确认")
    if expected_round is not None and ask.get("round") != expected_round:
        raise FlowError(f"问法 {ask.get('ask_id')} 属于第 {ask.get('round')} 轮，当前已是第 {expected_round} 轮："
                        "新轮材料须重新跑 `status` 生成本轮问法并确认，不沿用前轮问法或通过态")
    if _identity(ask) != str(ask.get("ask_id") or ""):
        raise FlowError("当前问法的内容与 ask_id 对不上（文件被改过）：重跑 `status` 重新生成")
    return ask


#: 合同标签比较时去掉的标点：只去陈述性分隔符与空白。问号与引号**不去**——它们本身说明人还在问、或在引用。
LABEL_PUNCT = re.compile(r"[\s，。、；：,.;:（）()]+")
#: 复合选择的分句边界：每一个分句都必须自己能完整成立；不认识的分句不忽略。
CLAUSE_SPLIT = re.compile(r"[，,；;。\n]+")
#: 编号后可以承接的既有简短确认格式（发布接口已测的「1）就这样」）；不据此扩出自由附言或同义词猜测。
CONFIRM = re.compile(r"^(?:就)?这样(?:吧)?$")
#: 疑问与引用语境：材料门不前进，保留原话请人只澄清这一个选择。
DOUBT = re.compile(r"[？?]")
QUOTED = re.compile(r"[「」『』“”\"']")
#: 整句的编号表达：裸编号、完整的「第 n 项／选 n」；句末只多一个陈述/枚举符。
_NUMBER_FORMS = (
    re.compile(r"^(?:选|选择)\s*(?:第\s*)?(\d+)\s*(?:项|个|条)?[。．.!！、)）]?$"),
    re.compile(r"^第\s*(\d+)\s*(?:项|个|条)[。．.!！]?$"),
    re.compile(r"^(\d+)\s*(?:项|个|条)?[。．.!！、)）]?$"),
)
#: 完整否定表达：否定词直接管辖一个编号；否定句仍逐字留存，不替人改。
_NEGATED = re.compile(r"^(?:不要|不|别|排除)\s*(?:选|选择|用|按|采用)?\s*(?:第\s*)?(\d+)\s*(?:项|个|条)?[。．.!！]?$")
#: 编号 + 同一选项完整标签的重述，或编号 + 既有确认格式。
_RESTATED = re.compile(r"^(?:选|选择)?\s*(?:第\s*)?(\d+)\s*(?:项|个|条)?\s*[.．、)）:：,，]\s*(.+?)"
                       r"[。．.!！]?$")


def _label_equal(text: str, label: str) -> bool:
    """整句照抄一项的完整标签：按合同标点比较，不把半句映射成整项。"""
    return bool(label) and LABEL_PUNCT.sub("", text) == LABEL_PUNCT.sub("", label)


def _clause_choice(clause: str, options: list[dict]) -> tuple[int, bool] | None:
    """**一段**完整的选择表达：编号、完整标签、完整否定，或编号 + 同一标签/既有确认格式的重述。

    整句与分句都只经这一个入口解析：不是就返回 None，不忽略也不截取。复合选择的重述因此只有一份实现，
    标点清洗不能把「选2？」当成「选2」。
    """
    text = clause.strip()
    if not text:
        return None
    for o in options:
        if _label_equal(text, o["label"]):
            return o["no"], True
    for pattern in _NUMBER_FORMS:
        m = pattern.fullmatch(text)
        if m:
            return int(m.group(1)), True
    m = _NEGATED.fullmatch(text)
    if m:
        return int(m.group(1)), False
    m = _RESTATED.fullmatch(text)
    if m:
        no, rest = int(m.group(1)), m.group(2).strip()
        if CONFIRM.fullmatch(rest):
            return no, True
        for o in options:
            if o["no"] == no and _label_equal(rest, o["label"]):
                return o["no"], True
    return None


def pick_explicit(options: list[dict], reply: str, ask_id: str | None = None) -> dict:
    """人的整句话明确指到一项才返回值：完整标签、完整编号表达，或受支持的复合选择。

    全输入协议：先认整句照抄的完整合同标签；其余必须**每一分句都是完整的选择表达**，且
    **恰有一个不同的肯定项**、肯定与否定没有交集。有问号、引用了别人的话、带条件/保留/附言或还有
    未消费的文字，一律不签认；只否定、多项肯定、同一项既肯定又否定同样不签认——保留原话、请人只
    澄清这一个选择，**不做集合相减**去签另一项。标点清洗不把「选2？」当成「选2」。
    """
    text = str(reply or "").strip()
    where = f"（ask {ask_id}）" if ask_id else ""
    listed = "、".join(f"{o['no']}={o['key']}" for o in options)

    def refuse(reason: str) -> FlowError:
        return FlowError(
            f"原话没有明确选到任何一项{where}：{reason}。按本次问法请人直接回编号或完整选项——"
            "有疑问、条件、保留、引用别人的选择，或编号后还有别的说明时，材料门不前进："
            "先处理能处理的补料或问题，再只澄清这一个选择，不从句中截一个编号当选择；"
            f"拿不准就再问人一次。现有：{listed}")

    if not text:
        raise refuse("是空白")
    if DOUBT.search(text):
        raise refuse("原话带问号，人还在问、没有表态")
    if QUOTED.search(text):
        raise refuse("原话在引用别人的说法，不是人自己的选择")
    stripped = text.rstrip("。．.!！")
    # 整句本身可能就是一个完整选择（含编号 + 同一标签/确认的重述）：是就整句算一段，不另写主函数分支。
    # 其余按分句；两处都只经 `_clause_choice` 解析，同一套「编号+附言」规则只有一份。
    clauses = [stripped] if _clause_choice(stripped, options) is not None else [c for c in CLAUSE_SPLIT.split(stripped) if c.strip()]
    if not clauses:
        raise refuse("没有认出任何一项")
    affirmed: dict[int, dict] = {}
    negated: set[int] = set()
    for clause in clauses:
        choice = _clause_choice(clause, options)
        if choice is None:
            raise refuse(f"「{clause.strip()}」不是完整的选择表达（有附言、条件或未消费的文字）")
        no, positive = choice
        hit = next((o for o in options if o["no"] == no), None)
        if hit is None:
            raise refuse(f"第 {no} 项不在这次摆出的选项里")
        if positive:
            affirmed[no] = hit
        else:
            negated.add(no)
    if both := sorted(no for no in affirmed if no in negated):
        raise refuse("第 " + "、".join(str(no) for no in both) + " 项同时被肯定又否定，原话自相矛盾")
    if len(affirmed) > 1:
        raise FlowError("原话同时指到了几项：" + "、".join(str(no) for no in sorted(affirmed))
                        + "——原话只认一项，请人明确只选一项" + where)
    if not affirmed:
        if negated:
            raise refuse("只否定了第 " + "、".join(str(n) for n in sorted(negated)) + " 项，没有肯定任何一项")
        raise refuse("没有肯定任何一项")
    return affirmed[next(iter(affirmed))]


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
            "block": block(left, [str(it["item_id"]) for it in ask.get("items") or []])}


def clear(feature_root: Path) -> None:
    (feature_root / Path(*ASK)).unlink(missing_ok=True)
