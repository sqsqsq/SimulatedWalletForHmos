"""有效人答导出为来源版本：设计、质询与审查按来源读人的原话，不另开一份要人重勾的清单。

人答的真源是流程契约里人给出的真实答复：当前轮的材料确认（`gates` 里的 `material_scope`）与
设计后必要问答的原话记录（`rounds[].answers`）。这里把它们原样导出成
`AR/story-src/answers/人工答复-v<N>.json` 与给人读的同名 `.md`。

- **只陈列证据**：问法、原话、出处与时刻。阅读稿不写「所选 = 人的裁决」，也不把整份答复
  升为业务批准；所选那一项在材料确认里只作材料事实登记。
- **原话记录只存证据**：`ask_id, item_id, question, options, reply, at, source_ref`；
  目标与版本只由原生反馈条目承担，不在这里复制。
- 已被替代的原话只留在契约里追溯，不进导出；有效集合或原话变了才出新版本。
- 每条记录的必需字段缺一项就是本版生产缺陷，报出来，不补默认值继续。

只用标准库，stdout 无输出。
"""
from __future__ import annotations

import json
from pathlib import Path

from materials import importer

CONTRACT = ("AR", "story-src", "story-flow.json")
ANSWERS = ("AR", "story-src", "answers")
SOURCE_ID = "answers"
LABEL = "人工答复"
GATE_FIELDS = ("ask_id", "gate", "round", "question", "options", "chosen", "no", "label", "reply", "at")
GATE_REQUIRED = ("ask_id", "gate", "question", "options", "chosen", "reply", "at")
ANSWER_FIELDS = ("ask_id", "item_id", "question", "options", "reply", "at", "source_ref")
ANSWER_REQUIRED = ("ask_id", "item_id", "question", "options", "reply", "at", "source_ref")
#: 原话记录不持有的字段：目标与版本只在原生 feedback 条目上。
ANSWER_FORBIDDEN = ("target_ref", "source_revision", "mapped_by")
MATERIAL_GATE = "material_scope"


class AnswerError(Exception):
    """人答读不出来或记录不完整：说不出当前有效的人答。"""


def _missing(record: dict, required: tuple[str, ...]) -> list[str]:
    return [k for k in required if record.get(k) in (None, "", [])]


def _answer_gaps(a: dict) -> list[str]:
    """原话记录的缺口：候选可为空数组，其余每项要有真实内容。"""
    gaps = [k for k in ANSWER_REQUIRED if k != "options" and not str(a.get(k) or "").strip()]
    if not isinstance(a.get("options"), list):
        gaps.append("options")
    return gaps


def gate_answers(contract: dict) -> tuple[list[dict], list[str]]:
    """当前轮材料确认的人答与记录缺口：只认当前轮最后一次生效的材料关卡。"""
    rounds = contract.get("rounds") or []
    if not rounds:
        return [], []
    current = rounds[-1]
    gate = next((g for g in reversed(current.get("gates") or [])
                 if g.get("gate") == MATERIAL_GATE and g.get("outcome") == "accepted"
                 and g.get("by") == "human"), None)
    if gate is None:
        return [], []
    gaps = _missing(gate, GATE_REQUIRED)
    if gaps:
        return [], [f"第 {current.get('round')} 轮材料确认（{gate.get('ask_id') or '无问法编号'}）"
                    f"缺 {'、'.join(gaps)}"]
    record = {"round": current.get("round"), **{k: gate[k] for k in GATE_FIELDS if k in gate}}
    return [record], []


def answer_records(contract: dict) -> tuple[list[dict], list[str]]:
    """设计后必要问答的原话记录与缺口：记录只作证据，不产生已批准状态。"""
    out, problems = [], []
    for r in contract.get("rounds") or []:
        for a in r.get("answers") or []:
            gaps = _answer_gaps(a)
            if gaps:
                problems.append(f"第 {r.get('round')} 轮设计问答（{a.get('ask_id') or '无问法编号'}）"
                                f"缺 {'、'.join(gaps)}")
                continue
            carried = [k for k in ANSWER_FORBIDDEN if k in a]
            if carried:
                problems.append(f"第 {r.get('round')} 轮设计问答 {a.get('ask_id')}/{a.get('item_id')} "
                                f"带着 {'、'.join(carried)}：原话记录只存问法、原话与出处")
                continue
            out.append(dict(a, round=r.get("round")))
    return out, problems


def collect(feature_root: Path) -> dict | None:
    """按当前契约算出要导出的人答；还没有流程契约为 None。记录不完整或读不出来报 AnswerError。"""
    path = feature_root.joinpath(*CONTRACT)
    if not path.is_file():
        return None
    try:
        contract = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise AnswerError(f"{'/'.join(CONTRACT)} 读不出来（{exc}）：说不出当前有效的人答，修好流程契约后重跑") from exc
    if not isinstance(contract, dict):
        raise AnswerError(f"{'/'.join(CONTRACT)} 不是对象：说不出当前有效的人答")
    gates, problems = gate_answers(contract)
    answers, more = answer_records(contract)
    problems += more
    if problems:
        raise AnswerError("人答记录不完整（本版生产的记录必须带问法、选项或原话与时刻）：" + "；".join(problems))
    return {"current": gates + answers, "context": []}


def _body(answers: dict) -> bytes:
    return (json.dumps(answers, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _render(answers: dict) -> str:
    lines = ["# 人工答复", "",
             "流程里人给出的真实答复，问法与原话照录。这里只陈列问题、原话与出处；"
             "选项与解释的效力由实际证据与原生反馈承担，阅读稿不替人下裁决。", "",
             "## 当前有效", ""]
    for d in answers["current"]:
        if d.get("gate"):
            lines += [f"### 材料确认 · 第 {d.get('round')} 轮 · {d['at']}", "", "问法：",
                      *[f"> {x}" for x in str(d["question"]).splitlines()], "",
                      f"- 原话：{d['reply']}",
                      f"- 登记的材料事实：{d.get('no')}. {d.get('label')}（{d['chosen']}）", ""]
        else:
            lines += _answer_block(d)
    if answers.get("context"):
        lines += ["## 需结合上下文", ""]
        lines += [_answer_block(d) for d in answers["context"]]
    return "\n".join(lines).rstrip() + "\n"


def _answer_block(d: dict) -> list[str]:
    rows = [f"### 设计问答 {d.get('ask_id')} · {d.get('item_id')} · 第 {d.get('round')} 轮 · {d['at']}", "",
            f"**问题**：{d['question']}", ""]
    options = d.get("options") or []
    if options:
        rows += ["**当时摆出的候选**：", *[f"- {o}" for o in options], ""]
    rows.append(f"- 原话：{d['reply']}")
    rows.append(f"- 出处：{d.get('source_ref') or '（未记）'}")
    return rows + [""]


def _mine(records: list[dict]) -> list[dict]:
    return sorted((r for r in records if r.get("source_id") == SOURCE_ID), key=lambda r: r["version"])


def required(feature_root: Path, records: list[dict]) -> dict:
    """必读人答此刻同步了没有：期待的导出内容身份、实际最新导出的版本与文件、是否一致与问题（只读，不写盘）。"""
    out = {"expected_sha256": None, "exported": None, "in_sync": True, "problems": []}
    try:
        answers = collect(feature_root)
    except AnswerError as exc:
        return {**out, "in_sync": False, "problems": [str(exc)]}
    if answers and (answers["current"] or answers["context"]):
        out["expected_sha256"] = importer.digest(_body(answers))
    mine = _mine(records)
    if mine:
        last = mine[-1]
        out["exported"] = {"dir": last["dir"], "files": [
            {"path": last["original"]["path"], "sha256": last["original"]["sha256"], "role": "answer_record"},
            {"path": last["readable"]["path"], "sha256": last["readable"]["sha256"], "role": "answer"}]}
    exported = mine[-1]["original"]["sha256"] if mine else None
    if out["expected_sha256"] and exported != out["expected_sha256"]:
        out["in_sync"] = False
        out["problems"].append("当前有效人答还没导出成来源版本（导出落后于流程记录）："
                               "跑 `story_flow.py round` 重试派生；答复本身已经记下，不要重答")
    return out


def export(feature_root: Path, stored: dict) -> str | None:
    """有效人答与最新导出版本不同就写一个新版本并登记进 `stored`（材料索引的登记部分），返回阅读件位置（相对需求目录）；
    相同或没有人答返回 None。版本存在 `AR/story-src/answers/人工答复-v<N>.json|.md`，按内容只增不改。"""
    from materials import registry  # noqa: PLC0415 —— registry 引用本模块
    answers = collect(feature_root)
    if not answers or not (answers["current"] or answers["context"]):
        return None
    body = _body(answers)
    sha = importer.digest(body)
    last = registry.latest(stored, SOURCE_ID)
    if last and last["original"]["sha256"] == sha:
        return None
    number = (last or {}).get("version", 0) + 1
    base = f"{'/'.join(ANSWERS)}/{LABEL}-v{number}"
    text = _render(answers).encode("utf-8")
    importer.write_once(feature_root, f"{base}.json", body)
    importer.write_once(feature_root, f"{base}.md", text)
    registry.add_version(stored, {"source_id": SOURCE_ID, "kind": "answer", "class": "ANSWER",
                                  "origin": {"contract": "/".join(CONTRACT)}, "label": LABEL},
                         {"version": number, "dir": f"{LABEL}-v{number}", "acquired_at": importer.now(),
                          "original": {"path": f"{base}.json", "sha256": sha},
                          "readable": {"path": f"{base}.md", "sha256": importer.digest(text)}, "images": []})
    return f"{base}.md"