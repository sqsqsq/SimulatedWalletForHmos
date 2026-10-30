"""有效人答导出为来源版本：设计、质询与审查按来源读人的原话，不另开一份要人重勾的清单。

人答的真源是流程契约（`AR/story-src/story-flow.json`）与 update 轮次记录里人给出的真实答复；这里把它们按适用性
分两组原样导出成 `sources/人工答复-v<N>/`：`answers.json`（问法、选项、所选、原话、时刻与出处）与给人读的 `answers.md`。

- **当前有效**：起手与会议关卡里人答且已生效的记录，同一关卡（会议按话题）只认最后一次；范围重开后还没重答的
  范围/承载答复不再当前；最后定的是整体承载时，之前的承载答复只是历史，切分时只认本轮定案那一次。update 期间人定的事按
  同一议题同一问法后答替代前答。
- **需结合上下文**：撤回那一轮的文件不撤销人的业务决定，问题版本已经变了的答复也不自动失效——这两类照录出处，
  由作者与审查按语义判它现在是否适用。

两组都是必读。已被替代或失效的原话只留在契约与轮次记录里追溯，不进导出。有效集合或原话变了才出新版本。
每条记录的必需字段（问法、选项或议题、原话、时刻）缺一项就是本版生产缺陷，报出来，不补默认值继续。

只用标准库，stdout 无输出。
"""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from materials import importer

CONTRACT = ("AR", "story-src", "story-flow.json")
SOURCE_ID = "answers"
LABEL = "人工答复"
RECORD, READABLE = "answers.json", "answers.md"
GATE_FIELDS = ("ask_id", "gate", "round", "question", "options", "chosen", "no", "label", "reply", "at",
               "meeting", "item", "context")
GATE_REQUIRED = ("ask_id", "gate", "question", "options", "chosen", "reply", "at")
UPDATE_FIELDS = ("update", "item", "issue", "asked", "question", "reply", "at")
UPDATE_REQUIRED = ("item", "issue", "asked", "question", "reply", "at")
SCOPE_GATES = ("scope_decision", "split_carrier")


class AnswerError(Exception):
    """人答读不出来或记录不完整：说不出当前有效的人答。"""


def _missing(record: dict, required: tuple[str, ...]) -> list[str]:
    return [k for k in required if record.get(k) in (None, "", [])]


def gate_answers(contract: dict) -> tuple[list[dict], list[str]]:
    """关卡里当前有效的人答与记录缺口。"""
    from flow.state import CARRY_ALL  # noqa: PLC0415 —— 契约常量的唯一真源
    rounds = contract.get("rounds") or []
    latest: dict[tuple, dict] = {}
    for r in rounds:
        for g in r.get("gates") or []:
            if g.get("by") == "human" and g.get("outcome") == "accepted":
                latest[(g.get("gate"), g.get("meeting"), g.get("item"))] = dict(g, round=r.get("round"))
    last = rounds[-1] if rounds else {}
    reopened = bool(last.get("reopened")) and not any(
        g.get("gate") == "scope_decision" and g.get("by") == "human" for g in last.get("gates") or [])
    scope = latest.get(("scope_decision", None, None))
    split = contract.get("split") or {}
    out, problems = [], []
    for (gate, _, _), g in latest.items():
        if gate in SCOPE_GATES and reopened:
            continue        # 范围重开了还没重答：旧的范围与承载答复不替重拍授权
        if gate == "split_carrier" and not (scope and scope.get("chosen") != CARRY_ALL
                                            and split.get("decided") == "split" and split.get("settled_round") == g["round"]):
            continue        # 整体承载了，或不是这一次定案的份表：承载答复只是历史
        gaps = _missing(g, GATE_REQUIRED)
        if gaps:
            problems.append(f"第 {g.get('round')} 轮 {gate} 的人答（{g.get('ask_id') or '无问法编号'}）缺 {'、'.join(gaps)}")
            continue
        out.append({k: g[k] for k in GATE_FIELDS if k in g})
    return out, problems


def update_answers(feature_root: Path, contract: dict) -> tuple[list[dict], list[dict], list[str]]:
    """update 期间人定的事：(当前有效, 需结合上下文, 记录缺口)。开着的一轮在契约里，收口或撤回的在轮次记录里。"""
    from flow.phase_facts import update_records  # noqa: PLC0415 —— 轮次记录的唯一枚举
    from flow.state import FlowError  # noqa: PLC0415
    try:
        records = update_records(feature_root)
    except FlowError as exc:
        raise AnswerError(str(exc)) from exc
    events: list[tuple[str, str, dict]] = []
    for rid, rec in records:
        for d in rec.get("decisions") or []:
            events.append((rid, str(rec.get("status") or ""), d))
    state = contract.get("update") or {}
    if state.get("open"):
        events += [(str(state["open"]), "open", d) for d in state.get("decisions") or []]
    seen, problems = {}, []
    for rid, status, d in events:
        gaps = _missing(d, UPDATE_REQUIRED)
        if gaps:
            problems.append(f"update {rid} 的人答（议题 {d.get('issue') or '?'}，{d.get('at') or '无时刻'}）缺 {'、'.join(gaps)}")
            continue
        key = (d["at"], d["issue"], d["reply"])
        if key not in seen or status == "open":
            seen[key] = (rid, status, d)
    latest: dict[tuple, tuple[str, str, dict]] = {}
    for rid, status, d in sorted(seen.values(), key=lambda x: x[2]["at"]):
        latest[(d["issue"], d["asked"])] = (rid, status, d)
    current, context = [], []
    for rid, status, d in latest.values():
        entry = {"update": rid, **{k: d[k] for k in UPDATE_FIELDS if k in d and k != "update"}}
        if status == "restored":
            context.append({**entry, "why": f"update {rid} 本地撤回了那一轮的文件；人的业务决定没有撤销，按语义核它现在是否仍适用"})
        elif _asked_now(feature_root, d["issue"]) != d["asked"]:
            context.append({**entry, "why": f"议题 {d['issue']} 的问法在评审记录里已经变了（答复时 {d['asked'][:12]}）：按语义核它是否仍适用"})
        else:
            current.append(entry)
    return current, context, problems


def _asked_now(feature_root: Path, issue: str) -> str | None:
    """评审记录里这条议题此刻的机器区摘要；议题不在了为 None。"""
    from flow.state import FlowError, issue_zone  # noqa: PLC0415 —— 议题摘要只在那里算
    try:
        return issue_zone(feature_root, issue)[0]
    except FlowError:
        return None


def collect(feature_root: Path) -> dict | None:
    """按当前契约与轮次记录算出要导出的两组人答；还没有流程契约为 None。记录不完整或读不出来报 AnswerError。"""
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
    current, context, more = update_answers(feature_root, contract)
    problems += more
    if problems:
        raise AnswerError("人答记录不完整（本版生产的记录必须带问法、选项或议题、原话与时刻）：" + "；".join(problems))
    return {"current": gates + current, "context": context}


def _body(answers: dict) -> bytes:
    return (json.dumps(answers, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _render(answers: dict) -> str:
    lines = ["# 人工答复", "", "流程里人给出的真实答复，问法与原话照录。两组都是必读：", ""]
    lines += ["## 当前有效", ""]
    for d in answers["current"]:
        if d.get("gate"):
            where = d["gate"] + (f"（会议 {d['meeting']} · {d['item']}）" if d.get("meeting") else "")
            lines += [f"### {where} · 第 {d.get('round')} 轮 · {d['at']}", "", "问法：", "", *[f"> {x}" for x in str(d["question"]).splitlines()],
                      "", f"- 所选：{d.get('no')}. {d.get('label')}（{d['chosen']}）", f"- 原话：{d['reply']}",
                      *_context_rows(d.get("context") or {}), ""]
        else:
            lines += [_update_block(d)]
    if answers["context"]:
        lines += ["## 需结合上下文", ""]
        lines += [_update_block(d) for d in answers["context"]]
    return "\n".join(lines).rstrip() + "\n"


def _context_rows(context: dict) -> list[str]:
    """范围答复当时的定位与份表：本单承载什么、兄弟单各承载什么。"""
    rows = [f"- 本单承载：{context['scope_text']}"] if context.get("scope_text") else []
    rows += [f"- 同一系统设计下的兄弟单 {r.get('ar')}：{r.get('scope') or '（定位没写它承载什么）'}"
             for r in context.get("sr_related_ars") or []]
    rows += [f"- 份 {p.get('seq')}（{p.get('carrier')}）：{p.get('scope')}" for p in context.get("parts") or []]
    return rows


def _update_block(d: dict) -> str:
    rows = [f"### update {d['update']} · 议题 {d['issue']} · {d['at']}", "", f"- 定的事：{d['item']}", "", "当时的议题：", "",
            *[f"> {x}" for x in str(d["question"]).splitlines()], "", f"- 原话：{d['reply']}"]
    if d.get("why"):
        rows.append(f"- 出处：{d['why']}")
    return "\n".join(rows) + "\n"


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


def export(feature_root: Path, records: list[dict]) -> str | None:
    """有效人答与最新导出版本不同就写一个新版本，返回它的目录（相对需求目录）；相同或没有人答返回 None。

    `records` 是索引已读到的全部版本记录（registry.version_records），这里只找本来源的那几条。
    """
    answers = collect(feature_root)
    if not answers or not (answers["current"] or answers["context"]):
        return None
    body = _body(answers)
    sha = importer.digest(body)
    mine = _mine(records)
    if mine and mine[-1]["original"]["sha256"] == sha:
        return None
    number = (mine[-1]["version"] if mine else 0) + 1
    name = f"{LABEL}-v{number}"
    final = feature_root / importer.SOURCES / name
    if final.exists():
        # 上一次已经发布了这一版、只是索引没写成：同内容就沿用，不另造一版
        known = final / RECORD
        if known.is_file() and importer.digest(known.read_bytes()) == sha:
            return None
        raise OSError(f"{importer.SOURCES}/{name} 已存在且内容不同：版本目录不覆盖，查明它从哪来")
    staging = feature_root.joinpath(*importer.STAGING) / uuid.uuid4().hex
    staging.mkdir(parents=True)
    try:
        text = _render(answers)
        (staging / RECORD).write_bytes(body)
        (staging / READABLE).write_text(text, encoding="utf-8", newline="\n")
        base = f"{importer.SOURCES}/{name}"
        record = {"schema": importer.VERSION_SCHEMA, "source_id": SOURCE_ID, "kind": "answer", "class": "ANSWER",
                  "origin": {"contract": "/".join(CONTRACT)},
                  "version": number, "acquired_at": importer.now(),
                  "original": {"path": f"{base}/{RECORD}", "sha256": sha},
                  "readable": {"path": f"{base}/{READABLE}", "sha256": importer.digest(text.encode("utf-8"))},
                  "images": []}
        (staging / importer.VERSION_FILE).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                                                     encoding="utf-8", newline="\n")
        importer.publish_dir(staging, final)
    except OSError:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    finally:
        importer.clear_staging(feature_root)
    return f"{importer.SOURCES}/{name}"
