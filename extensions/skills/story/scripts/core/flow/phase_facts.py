"""Framework 阶段与 update 轮次的原生事实（只读）：update 收口、路由与 usage 记录共用这一份读取。

读的是 harness 自己写的 `<阶段报告目录>/summary.json` 与 update 自己落盘的 record.json——
它们是**只读投影**，不是我们的账。自己另记一份的话，两边迟早对不上，而人会信错的那一份。
读不出来就说读不出来：闭没闭环这件事不许猜，猜错的方向是「以为闭了」。
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from materials import importer
from flow.state import FlowError

PHASES = ("spec", "plan", "coding", "review", "ut", "testing")
UPDATES = ("AR", "story-src", "updates")
#: 审查报告的终态块（framework `verifier-subject.ts::parseResultBlock` 读的那一段）。
RESULT_BLOCK = re.compile(r"<!-- maison-verifier-result:v1 -->(.*?)<!-- /maison-verifier-result:v1 -->", re.S)


def summary(feature_root: Path, phase: str) -> dict:
    """这个阶段的 summary：`state` 为 missing（没有文件）/ unreadable（在却坏了）/ open（有效未闭环）/ closed。"""
    reports = importer.phase_reports_dir(feature_root, phase)
    path = reports / "summary.json"
    if not path.is_file():
        return {"state": "missing", "path": path, "reports": reports}
    try:
        data = json.loads(path.read_text(encoding="utf-8").lstrip("﻿"))
    except (OSError, ValueError) as exc:
        return {"state": "unreadable", "path": path, "reports": reports, "why": str(exc)}
    if not isinstance(data, dict):
        return {"state": "unreadable", "path": path, "reports": reports, "why": "不是 JSON 对象"}
    return {"state": "closed" if data.get("closure_status") == "closed" else "open",
            "path": path, "reports": reports, "data": data}


def phase_facts(feature_root: Path) -> list[dict]:
    """有 summary 的各阶段：闭环状态、结论、审查对象与「已审未采纳」。没有 summary 的阶段不列。"""
    out = []
    for phase in PHASES:
        s = summary(feature_root, phase)
        if s["state"] == "missing":
            continue
        if s["state"] == "unreadable":
            out.append({"phase": phase, "readable": False, "why": s["why"]})
            continue
        data = s["data"]
        subject = data.get("verifier_subject_id")
        mode = (data.get("verifier_closure") or {}).get("mode")
        out.append({"phase": phase, "readable": True,
                    "closure": data.get("closure_status"),
                    "verdict": data.get("verdict"),
                    "subject": subject, "closure_mode": mode,
                    "signals": [x.get("id") if isinstance(x, dict) else x
                                for x in data.get("readiness_signals") or []],
                    "unadopted": mode == "completed_with_prior_review"
                    and report_passed(s["reports"], subject)})
    return out


def report_passed(reports: Path, subject: str | None) -> bool:
    """当前 subject 的报告在盘上、终态块回显的就是它、判的是 PASS。"""
    if not subject:
        return False
    try:
        text = (reports / f"verifier.report.{subject}.md").read_text(encoding="utf-8")
    except OSError:
        return False
    blocks = RESULT_BLOCK.findall(text)
    if len(blocks) != 1:
        return False
    fields = dict(line.split(":", 1) for line in blocks[0].strip().splitlines() if ":" in line)
    return (fields.get("verifier_subject_id", "").strip() == subject
            and fields.get("verdict", "").strip() == "PASS")


def moment(value: object) -> datetime | None:
    """带时区的 ISO 时刻；没有时区或读不出返回 None（不猜时区）。"""
    if not isinstance(value, str):
        return None
    try:
        at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo else None


def update_records(feature_root: Path) -> list[tuple[str, dict]]:
    """盘上已有的 update 操作记录，按 id 排序。读不出来的那一条要出声，不静默跳过。"""
    base = feature_root / Path(*UPDATES)
    if not base.is_dir():
        return []
    out = []
    for d in sorted(base.iterdir()):
        path = d / "record.json"
        if not path.is_file():
            continue
        try:
            out.append((d.name, json.loads(path.read_text(encoding="utf-8").lstrip("﻿"))))
        except ValueError as exc:
            raise FlowError(f"{path} 不是合法 JSON（{exc}）：它由本脚本写入，"
                            "若曾手工编辑请修正语法，或把整个 "
                            f"{d.name} 目录移走再重跑") from exc
    return out
