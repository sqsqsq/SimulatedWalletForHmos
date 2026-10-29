"""有效人答导出为来源版本：设计与审查按来源引用人的原话，不另开一份要人重勾的清单。

人答的真源是流程契约（`AR/story-src/story-flow.json`）里人给出、已生效的关卡记录；这里只把**当前有效**的那些
原样导出成 `sources/人工答复-v<N>/`：`answers.json`（逐条原话、所选项、关卡与时刻）与给人读的 `answers.md`。
同一关卡后来重答过，前一条就被替代、不再导出；有效人答的集合或原话变了才出新版本，其余运行状态变化不重导出。
模型建议不在这里：只收 `by == "human"` 且 `outcome == "accepted"` 的记录。

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
FIELDS = ("ask_id", "gate", "round", "options", "chosen", "no", "label", "reply", "at", "meeting", "item")


class AnswerError(Exception):
    """流程契约读不出来：说不出当前有效的人答。"""


def effective_human_records(contract: dict) -> list[dict]:
    """当前有效的人签：同一关卡（会议话题按话题分）只认最后一条人给出、已生效的记录。

    之后的轮次重新答过同一关卡（reopen 或补料后重问），前一条就被替代；没有重问的关卡沿用原记录。
    """
    latest: dict[tuple, dict] = {}
    for r in contract.get("rounds", []):
        for g in r.get("gates", []):
            if g.get("by") == "human" and g.get("outcome") == "accepted":
                latest[(g.get("gate"), g.get("meeting"), g.get("item"))] = dict(g, round=r.get("round"))
    return list(latest.values())


def _render(decisions: list[dict]) -> str:
    lines = ["# 人工答复", "", "流程里人给出、当前有效的答复，原话照录；同一关卡后来重答的只留最后一次。", ""]
    for d in decisions:
        where = f"{d.get('gate')}" + (f"（会议 {d['meeting']} · {d['item']}）" if d.get("meeting") else "")
        lines += [f"## {d.get('ask_id') or where}", "",
                  f"- 关卡：{where}；第 {d.get('round')} 轮；{d.get('at')}",
                  f"- 所选：{d.get('no')}. {d.get('label')}（{d.get('chosen')}）",
                  f"- 原话：{d.get('reply')}", ""]
    return "\n".join(lines).rstrip() + "\n"


def export(feature_root: Path, records: list[dict]) -> str | None:
    """有效人答与最新导出版本不同就写一个新版本，返回它的目录（相对需求目录）；相同或没有人答返回 None。

    `records` 是索引已读到的全部版本记录（registry.version_records），这里只找本来源的那几条。
    还没有流程契约就还没有人答；契约在而读不出来就报，不当成没有人答。
    """
    path = feature_root.joinpath(*CONTRACT)
    if not path.is_file():
        return None
    try:
        contract = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise AnswerError(f"{'/'.join(CONTRACT)} 读不出来（{exc}）：说不出当前有效的人答，修好流程契约后重跑") from exc
    decisions = [{k: g[k] for k in FIELDS if k in g} for g in effective_human_records(contract if isinstance(contract, dict) else {})]
    if not decisions:
        return None
    body = (json.dumps({"decisions": decisions}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    sha = importer.digest(body)
    mine = sorted((r for r in records if r.get("source_id") == SOURCE_ID), key=lambda r: r["version"])
    if mine and mine[-1]["original"]["sha256"] == sha:
        return None
    number = (mine[-1]["version"] if mine else 0) + 1
    name = f"{LABEL}-v{number}"
    final = feature_root / importer.SOURCES / name
    if final.exists():
        raise OSError(f"{importer.SOURCES}/{name} 已存在：版本目录不覆盖，查明它从哪来")
    staging = feature_root.joinpath(*importer.STAGING) / uuid.uuid4().hex
    staging.mkdir(parents=True)
    try:
        text = _render(decisions)
        (staging / RECORD).write_bytes(body)
        (staging / READABLE).write_text(text, encoding="utf-8", newline="\n")
        base = f"{importer.SOURCES}/{name}"
        record = {"schema": importer.VERSION_SCHEMA, "source_id": SOURCE_ID, "kind": "answer", "class": "ANSWER",
                  "origin": {"contract": "/".join(CONTRACT), "ask_ids": [d.get("ask_id") for d in decisions]},
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
