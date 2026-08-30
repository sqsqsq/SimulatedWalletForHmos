"""Single planned-step execution ledger used by plan and steps-file paths."""

from __future__ import annotations

import json
import time
from typing import Any

from hylyre.api.agent import HylyreAgent
from hylyre.api.exceptions import StepSkipped
from hylyre.api.step_dispatch import dispatch_planned_step
from hylyre.scenario.results import StepResult, redact_evidence, redact_text, result_from_exception
from hylyre.scenario.step_text import (
    json_step_syntax_error,
    looks_like_planned_json,
    non_json_step_error,
    normalize_planned_step_text,
)

_ASSERTION_ROOTS = frozenset({"wait_for", "wait_gone", "assert_toast"})
_ASSERTION_ACTION_TYPES = frozenset({"wait_for", "wait_gone", "assert_toast"})


def _parse_step_object(step: Any) -> dict[str, Any] | None:
    if isinstance(step, dict):
        return step
    if not isinstance(step, str):
        return None
    normalized = normalize_planned_step_text(step)
    if not looks_like_planned_json(step):
        return None
    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def toast_assertion_on_unsupported(step: Any) -> str | None:
    """Return a planned Toast assertion's explicit unsupported policy."""

    parsed = _parse_step_object(step)
    if not isinstance(parsed, dict):
        return None
    block: Any = parsed.get("assert_toast")
    if block is None and isinstance(parsed.get("action"), dict):
        action = parsed["action"]
        if action.get("type") == "assert_toast":
            block = action
    if not isinstance(block, dict):
        return None
    return str(block.get("on_unsupported") or "error").strip().lower()


def blocked_step_result(
    step: Any,
    *,
    index: int,
    reason: str,
    root_failure: StepResult | None = None,
) -> StepResult:
    """Create the ledger row for a planned step that was not executed."""

    failure_kind = (
        root_failure.failure_kind
        if root_failure is not None and root_failure.failure_kind is not None
        else "infrastructure"
    )
    failure_code = (
        root_failure.failure_code
        if root_failure is not None and root_failure.failure_code is not None
        else "driver_failure"
    )
    return StepResult(
        index=index,
        kind=planned_step_kind(step),
        role=planned_step_role(step),  # type: ignore[arg-type]
        status="blocked",
        failure_kind=failure_kind,  # type: ignore[arg-type]
        failure_code=failure_code,
        duration_ms=0.0,
        evidence={"executed": False, "blocked_by": reason},
        error=f"planned step blocked: {reason}",
    )


def planned_step_kind(step: Any) -> str:
    if isinstance(step, str):
        normalized = normalize_planned_step_text(step)
        if looks_like_planned_json(step):
            try:
                parsed = json.loads(normalized)
            except json.JSONDecodeError:
                return "planned_json"
            if isinstance(parsed, dict):
                return planned_step_kind(parsed)
        return "ai_action"
    if isinstance(step, dict):
        roots = [str(k) for k in step if k in {
            "action", "touch", "input", "swipe", "scroll", "scroll_to",
            "back", "home", "stop_app", "clear_app", "wait", "wait_for",
            "wait_gone", "wait_idle", "assert_toast", "start_app",
        }]
        if len(roots) == 1:
            root = roots[0]
            if root == "action" and isinstance(step.get(root), dict):
                return str(step[root].get("type") or root)
            return root
        return "planned_step"
    return "planned_step"


def planned_step_role(step: Any) -> str:
    if isinstance(step, str):
        normalized = normalize_planned_step_text(step)
        if looks_like_planned_json(step):
            try:
                parsed = json.loads(normalized)
            except json.JSONDecodeError:
                return "action"
            if isinstance(parsed, dict):
                return planned_step_role(parsed)
        return "action"
    if isinstance(step, dict):
        if "action" in step and isinstance(step.get("action"), dict):
            kind = str(step["action"].get("type") or "")
        else:
            kind = next((str(k) for k in _ASSERTION_ROOTS if k in step), "")
        return "assertion" if kind in _ASSERTION_ROOTS or kind in _ASSERTION_ACTION_TYPES else "action"
    return "action"


def _operation_parts(value: Any) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not isinstance(value, dict):
        return None, None
    selector = value.get("selector")
    evidence = value.get("evidence")
    if isinstance(selector, dict) or isinstance(evidence, dict):
        return (
            selector if isinstance(selector, dict) else None,
            evidence if isinstance(evidence, dict) else None,
        )
    return None, value


async def _execute_step_value(agent: HylyreAgent, step: Any, *, case_id: str) -> Any:
    if isinstance(step, dict):
        return await dispatch_planned_step(agent, step, case_id=case_id)
    if not isinstance(step, str):
        raise TypeError(f"{case_id}: planned step must be a JSON object or text")
    normalized = normalize_planned_step_text(step)
    if not normalized:
        return {"evidence": {"operation": "empty"}}
    if looks_like_planned_json(step):
        try:
            payload = json.loads(normalized)
        except json.JSONDecodeError as e:
            raise ValueError(json_step_syntax_error(case_id, e, step)) from e
        if not isinstance(payload, dict):
            raise ValueError(f"{case_id}: planned JSON step must be an object")
        return await dispatch_planned_step(agent, payload, case_id=case_id)
    if agent.vlm is None:
        raise ValueError(non_json_step_error(case_id))
    return await agent.ai_action(normalized)


async def execute_ledger_step(
    agent: HylyreAgent,
    step: Any,
    *,
    index: int,
    case_id: str,
) -> StepResult:
    """Execute one step and always return one finalized StepResult."""

    kind = planned_step_kind(step)
    role = planned_step_role(step)
    t0 = time.perf_counter()
    try:
        value = await _execute_step_value(agent, step, case_id=case_id)
    except Exception as exc:
        return result_from_exception(
            exc=exc,
            index=index,
            kind=kind,
            role=role,  # type: ignore[arg-type]
            duration_ms=(time.perf_counter() - t0) * 1000.0,
        )
    selector, evidence = _operation_parts(value)
    if role == "assertion" and value is None:
        return StepResult(
            index=index,
            kind=kind,
            role=role,  # type: ignore[arg-type]
            status="passed",
            duration_ms=(time.perf_counter() - t0) * 1000.0,
            selector=selector,
            evidence=None,
        )
    if evidence is None:
        evidence = {"operation": kind, "result": True}
    return StepResult(
        index=index,
        kind=kind,
        role=role,  # type: ignore[arg-type]
        status="passed",
        duration_ms=(time.perf_counter() - t0) * 1000.0,
        selector=selector,
        evidence=evidence,
    )


async def execute_expected_assertion(
    agent: HylyreAgent,
    instruction: str,
    *,
    index: int,
    case_id: str,
) -> StepResult:
    """Run the expected-result VLM check as a normal assertion ledger row."""

    t0 = time.perf_counter()
    try:
        value = await agent.ai_assert(instruction)
    except Exception as exc:
        return result_from_exception(
            exc=exc,
            index=index,
            kind="expected_check",
            role="assertion",
            duration_ms=(time.perf_counter() - t0) * 1000.0,
        )
    _selector, evidence = _operation_parts(value)
    if evidence is None:
        evidence = {"channel": "vlm", "instruction_checked": True, "result": True}
    return StepResult(
        index=index,
        kind="expected_check",
        role="assertion",
        status="passed",
        duration_ms=(time.perf_counter() - t0) * 1000.0,
        evidence=evidence,
    )


def step_result_to_batch_row(step: StepResult, raw_step: Any) -> dict[str, Any]:
    """Compatibility projection for the existing steps-file CLI response."""

    status = "ok" if step.status == "passed" else (
        "skipped" if step.status == "skipped" else "error"
    )
    row: dict[str, Any] = {
        "index": step.index,
        "step": (
            redact_evidence(raw_step)
            if isinstance(raw_step, (dict, list, tuple))
            else redact_text(str(raw_step))
        ),
        "status": status,
        "elapsed_ms": step.duration_ms,
        "step_result": step.to_dict(),
    }
    if step.error:
        row["error"] = redact_text(step.error)
    if step.evidence and step.evidence.get("failure_artifacts"):
        row["diagnostics"] = step.evidence["failure_artifacts"]
    return row


__all__ = [
    "blocked_step_result",
    "execute_expected_assertion",
    "execute_ledger_step",
    "planned_step_kind",
    "planned_step_role",
    "step_result_to_batch_row",
    "toast_assertion_on_unsupported",
]
