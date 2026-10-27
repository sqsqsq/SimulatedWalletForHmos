"""Framework 阶段与 update 轮次的原生事实（只读）：usage 记录据它结算阶段与 update 轮次，update 据它读历史轮次。

读的是 harness 自己写的 `<阶段报告目录>/summary.json` 与 update 自己落盘的 record.json——
它们是**只读投影**，不是我们的账。自己另记一份的话，两边迟早对不上，而人会信错的那一份。
读不出来就说读不出来：闭没闭环这件事不许猜，猜错的方向是「以为闭了」。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from flow import native
from flow.state import FlowError

PHASES = ("spec", "plan", "coding", "review", "ut", "testing")
UPDATES = ("AR", "story-src", "updates")


def summary(project_root: Path, feature: str, phase: str) -> dict:
    """逻辑 Feature 这个阶段的 summary：`state` 为 missing（没有文件）/ unreadable（在却坏了）/ open（有效未闭环）/ closed。
    报告目录取原生解析（CU 的物理目录与逻辑标识不同），不按目录名反推。"""
    reports = native.feature_paths(project_root, feature, PHASES)["reports"][phase]
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


def evidence(project_root: Path, feature: str, phase: str) -> str:
    """这个阶段的原生证据此刻是否仍有效：按阶段顺序到它为止重算（上游不新鲜会传染下游），返回原生 verdict
    （fresh / stale / missing / tampered）。只读，不传 run 与 pending owner；读不出照原生报错。"""
    chain = list(PHASES[:PHASES.index(phase) + 1])
    got = native.call(project_root, "phase-evidence", "--feature", feature, "--phases", ",".join(chain))
    if got.get("status") != "ok":
        raise FlowError(f"{feature} 的 {phase} 阶段证据有效性读不出：{native.issues_text(got)}")
    row = next((r for r in got.get("results") or [] if r.get("phase") == phase), None)
    return str((row or {}).get("verdict") or "missing")


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
