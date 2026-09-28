"""Derive Story test phase state from structured workspace evidence."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


PHASE_ORDER = ("spec", "plan", "coding", "review", "ut", "testing")
ALL_PHASES = ("story", *PHASE_ORDER)


def _rank(phase: object) -> int:
    try:
        return ALL_PHASES.index(str(phase))
    except ValueError:
        return -1


def _phase_artifact_reached(feature_root: Path, phase: str) -> bool:
    root = feature_root / phase
    return root.is_dir() and any(path.name != "reports" for path in root.iterdir())


def _framework_phase(workspace: Path, feature: str) -> tuple[str | None, str | None]:
    path = workspace / "framework/harness/state/.current-phase.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None, None
    phase = str(payload.get("phase") or "")
    if str(payload.get("feature") or "") != feature or phase not in PHASE_ORDER:
        return None, None
    return phase, str(payload.get("updated_at") or payload.get("last_run_at") or "") or None


def derive_phase_state(workspace: Path, feature: str, state: dict[str, Any],
                       *, observed_at: str | None = None) -> dict[str, Any]:
    """Return a compatible phase update without inspecting model prose."""
    observed = observed_at or time.strftime("%Y-%m-%d %H:%M:%S")
    previous_current = str(state.get("current_phase") or state.get("last_phase") or "")
    requested_start = str(state.get("requested_start_phase") or "story")
    baseline = previous_current if _rank(previous_current) >= 0 else requested_start
    if _rank(baseline) < 0:
        baseline = "story"

    framework_phase, framework_at = _framework_phase(workspace, feature)
    feature_root = workspace / "doc/features" / feature
    artifact_phases: list[str] = []
    for phase in PHASE_ORDER:
        if _phase_artifact_reached(feature_root, phase):
            artifact_phases.append(phase)
    artifact_phase = max(artifact_phases, key=_rank) if artifact_phases else None

    current = baseline
    source = str(state.get("phase_source") or "state")
    evidence_at = str(state.get("phase_observed_at") or observed)
    phase = framework_phase or artifact_phase
    candidate_source = "framework_current_phase" if framework_phase else "phase_artifact"
    candidate_at = framework_at if framework_phase else None
    if phase:
        if _rank(phase) >= _rank(current):
            same_evidence = phase == current and candidate_source == source
            current = phase
            source = candidate_source
            evidence_at = candidate_at or (evidence_at if same_evidence else observed)

    previous_highest = str(state.get("highest_phase_reached") or baseline)
    highest_candidates = [previous_highest, current]
    if artifact_phase:
        highest_candidates.append(artifact_phase)
    highest = max(highest_candidates, key=_rank)
    result: dict[str, Any] = {
        "current_phase": current,
        "highest_phase_reached": highest,
        "phase_source": source,
        "phase_observed_at": evidence_at,
        "last_phase": current,
    }
    if _rank(highest) >= _rank("spec"):
        result["spec_entered_at"] = state.get("spec_entered_at") or evidence_at or observed
    elif state.get("spec_entered_at"):
        result["spec_entered_at"] = state["spec_entered_at"]
    return result
