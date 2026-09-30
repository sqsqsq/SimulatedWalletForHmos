"""一次运行走到哪了 —— 从需求流程契约与驱动器发布的原生终点观测推出，不读模型的话，也不看目录出现没有。

阶段依次是 `story`（需求成文登记之前）、`design_handoff`（施工单位还没全部可施工）、各原生阶段（取所有活动施工单位里
最早还没闭环的那一个）。施工单位的事实只来自驱动器每回合发布的 `state["closure"]`（`end_target.observe` 的结果）；
终点是 story 或 blueprint 时观测不列施工单位，阶段就停在 `story`。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from end_target import PHASES

PHASE_ORDER = PHASES
ALL_PHASES = ("story", "design_handoff", *PHASE_ORDER)


def phase_rank(phase: object) -> int:
    try:
        return ALL_PHASES.index(str(phase))
    except ValueError:
        return -1


def _registered(workspace: Path, feature: str) -> bool:
    flow = workspace / "doc/features" / feature / "AR" / "story-src" / "story-flow.json"
    try:
        return json.loads(flow.read_text(encoding="utf-8")).get("status") in ("story_written", "archived")
    except (OSError, ValueError):
        return False


def _stage(workspace: Path, feature: str, closure: dict) -> str:
    units = closure.get("units") or []
    if not units:
        wants_units = str(closure.get("end_at") or "").startswith(("design_handoff", "phase"))
        return "design_handoff" if wants_units and _registered(workspace, feature) else "story"
    if any(u.get("design") != "constructable" for u in units):
        return "design_handoff"
    open_phases = [p for u in units for p, row in (u.get("phases") or {}).items() if row.get("state") == "open"]
    if open_phases:
        return min(open_phases, key=phase_rank)
    done = [p for u in units for p in (u.get("phases") or {})]
    return max(done, key=phase_rank) if done else "design_handoff"


def derive_phase_state(workspace: Path, feature: str, state: dict[str, Any],
                       *, observed_at: str | None = None) -> dict[str, Any]:
    """`current_phase` 是现在的阶段，`highest_phase_reached` 是到过的最远阶段；`story_done_at` 记成文登记首次成立的时刻。"""
    observed = observed_at or time.strftime("%Y-%m-%d %H:%M:%S")
    current = _stage(workspace, feature, state.get("closure") or {})
    previous = str(state.get("current_phase") or "")
    highest = max([str(state.get("highest_phase_reached") or "story"), current], key=phase_rank)
    result: dict[str, Any] = {
        "current_phase": current,
        "highest_phase_reached": highest,
        "phase_source": "flow_and_native_observation",
        "phase_observed_at": state.get("phase_observed_at") if previous == current and state.get("phase_observed_at") else observed,
        "last_phase": current,
    }
    if state.get("story_done_at"):
        result["story_done_at"] = state["story_done_at"]
    elif _registered(workspace, feature):
        result["story_done_at"] = observed
    return result
