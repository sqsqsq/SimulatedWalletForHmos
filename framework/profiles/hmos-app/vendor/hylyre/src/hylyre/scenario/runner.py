"""Run scenarios from a test plan with one authoritative step ledger."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from hylyre.api.agent import HylyreAgent
from hylyre.api.exceptions import CapabilityUnsupported, classify_exception
from hylyre.api.failure_diag import capture_step_failure
from hylyre.scenario.ledger import (
    _execute_step_value,
    blocked_step_result,
    execute_expected_assertion,
    execute_ledger_step,
    planned_step_kind,
    planned_step_role,
    toast_assertion_on_unsupported,
)
from hylyre.scenario.plan_parse import ParsedPlan, TestCase, parse_test_plan
from hylyre.scenario.results import (
    CaseResult,
    StepResult,
    case_verdict,
    outcome_from_case_results,
    redact_text,
    result_from_exception,
)
from hylyre.scenario.step_text import normalize_planned_step_text


def resolved_outcome(result: "ScenarioRunResult") -> str:
    """Project case axes to the historical trace outcome enum.

    A run with only skipped/inconclusive cases is deliberately not ``success``.
    """

    return outcome_from_case_results(result.case_results)


@dataclass(frozen=True)
class ScenarioRunResult:
    feature: str
    plan: ParsedPlan
    case_results: tuple[CaseResult, ...]
    use_fakes: bool
    environment: dict[str, str] | None = None

    @property
    def tool_calls(self) -> tuple[dict[str, Any], ...]:
        """Compatibility projection derived exclusively from ``cases[].steps[]``."""

        calls: list[dict[str, Any]] = []
        for case_result in self.case_results:
            for step in case_result.steps:
                calls.append(
                    {
                        "case": case_result.case.case_id,
                        "index": step.index,
                        "kind": step.kind,
                        "role": step.role,
                        "status": step.status,
                        "failure_kind": step.failure_kind,
                        "failure_code": step.failure_code,
                    }
                )
        return tuple(calls)


def _expected_is_empty(expected: str) -> bool:
    return not expected.strip() or expected.strip() == "-"


def _diagnostic_evidence(note: str) -> dict[str, Any] | None:
    names = re.findall(r"(?:ui_dump|screenshot)=([^,\s]+)", note)
    if not names:
        return None
    return {"failure_artifacts": names}


def _with_diagnostics(step: StepResult, note: str) -> StepResult:
    extra = _diagnostic_evidence(note)
    if not extra:
        return step
    merged = {**(step.evidence or {}), **extra}
    return replace(step, evidence=merged)


def _make_case_result(
    case: TestCase,
    steps: list[StepResult],
    *,
    expected_check_mode: str,
    execution: str = "completed",
    notes: str = "",
) -> CaseResult:
    frozen_steps = tuple(steps)
    if not frozen_steps:
        frozen_steps = (
            StepResult(
                index=0,
                kind="empty_case",
                role="assertion",
                status="skipped",
                failure_kind="capability",
                failure_code="capability_unsupported",
                duration_ms=0.0,
                evidence={"reason": "no planned steps"},
                error="case contains no executable planned step",
            ),
        )
    verification, evidence, legacy = case_verdict(
        frozen_steps,
        expected_check_mode=expected_check_mode,  # type: ignore[arg-type]
        execution=execution,  # type: ignore[arg-type]
    )
    return CaseResult(
        case=case,
        status=legacy,
        notes=redact_text(notes[:4000]) or "",
        execution=execution,  # type: ignore[arg-type]
        verification=verification,
        evidence=evidence,
        expected_check_mode=expected_check_mode,  # type: ignore[arg-type]
        steps=frozen_steps,
    )


class ScenarioRunner:
    """Execute plan rows; fake mode is deterministic without devices."""

    def __init__(self, *, use_fakes: bool = False) -> None:
        self._use_fakes = use_fakes

    def run_plan_file(
        self,
        plan_path: Path | str,
        *,
        feature: str,
        check_expected: bool = True,
    ) -> ScenarioRunResult:
        if not self._use_fakes:
            raise ValueError(
                "Real-device runs use run_plan_on_agent(); "
                "pass use_fakes=True for run_plan_file()."
            )
        plan = parse_test_plan(plan_path)
        results: list[CaseResult] = []
        for case in plan.cases:
            results.append(self._fake_case_result(case, check_expected=check_expected))
        return ScenarioRunResult(
            feature=feature,
            plan=plan,
            case_results=tuple(results),
            use_fakes=True,
            environment={"ui_driver": "fake", "hypium_version": "unavailable"},
        )

    @staticmethod
    def _fake_case_result(
        case: TestCase, *, check_expected: bool = True
    ) -> CaseResult:
        raw_steps = _iter_steps(case.steps)
        step_results: list[StepResult] = []
        for idx, raw in enumerate(raw_steps):
            kind = "ai_action"
            role = "action"
            normalized = normalize_planned_step_text(raw)
            if normalized.startswith("{"):
                try:
                    payload = json.loads(normalized)
                    if isinstance(payload, dict):
                        root = next(iter(payload), "planned_step")
                        kind = str(root)
                        if root in {"wait_for", "wait_gone", "assert_toast"}:
                            role = "assertion"
                except json.JSONDecodeError:
                    step_results.append(
                        StepResult(
                            index=idx,
                            kind="planned_json",
                            role="action",
                            status="failed",
                            failure_kind="infrastructure",
                            failure_code="driver_failure",
                            duration_ms=0.0,
                            evidence={"channel": "fake", "parsed": False},
                            error="fake mode: invalid planned JSON",
                        )
                    )
                    continue
            if "跳过" in raw or case.case_id.upper().endswith("-SKIP"):
                step_results.append(
                    StepResult(
                        index=idx,
                        kind=kind,
                        role=role,  # type: ignore[arg-type]
                        status="skipped",
                        failure_kind="capability",
                        failure_code="capability_unsupported",
                        duration_ms=0.0,
                        evidence={"channel": "fake", "result": "skipped"},
                        error="fake mode: skipped by fixture",
                    )
                )
                continue
            if case.case_id.upper().endswith("-FAIL"):
                step_results.append(
                    StepResult(
                        index=idx,
                        kind=kind,
                        role=role,  # type: ignore[arg-type]
                        status="failed",
                        failure_kind="assertion",
                        failure_code="assertion_mismatch",
                        duration_ms=0.0,
                        evidence={"channel": "fake", "result": False},
                        error="fake mode: case id suffix -FAIL forces failure",
                    )
                )
                continue
            if case.case_id.upper().endswith("-BLOCK"):
                step_results.append(
                    StepResult(
                        index=idx,
                        kind=kind,
                        role=role,  # type: ignore[arg-type]
                        status="blocked",
                        failure_kind="infrastructure",
                        failure_code="device_unavailable",
                        duration_ms=0.0,
                        evidence={"channel": "fake", "result": "blocked"},
                        error="fake mode: blocked by fixture",
                    )
                )
                continue
            if role == "assertion":
                step_results.append(
                    StepResult(
                        index=idx,
                        kind=kind,
                        role="assertion",
                        status="skipped",
                        failure_kind="capability",
                        failure_code="capability_unsupported",
                        duration_ms=0.0,
                        evidence={
                            "channel": "fake",
                            "assertion_executed": False,
                            "result": "skipped",
                        },
                        error="fake mode: assertion was not executed",
                    )
                )
                continue
            step_results.append(
                StepResult(
                    index=idx,
                    kind=kind,
                    role=role,  # type: ignore[arg-type]
                    status="passed",
                    duration_ms=0.0,
                    evidence={"channel": "fake", "operation": kind, "result": True},
                )
            )
        expected_mode = "empty"
        if not _expected_is_empty(case.expected):
            expected_mode = (
                "disabled_by_flag" if not check_expected else "unavailable_no_vlm"
            )
            step_results.append(
                StepResult(
                    index=len(step_results),
                    kind="expected_check",
                    role="assertion",
                    status="skipped",
                    failure_kind="capability",
                    failure_code="capability_unsupported",
                    duration_ms=0.0,
                    evidence={
                        "channel": "vlm",
                        "assertion_executed": False,
                        "result": "disabled" if not check_expected else "unavailable",
                    },
                    error=(
                        "fake mode: expected check disabled"
                        if not check_expected
                        else "fake mode: no VLM configured"
                    ),
                )
            )
        execution = "completed"
        if any(step.status in ("failed", "blocked") for step in step_results):
            execution = (
                "infrastructure_failed"
                if any(
                    step.failure_kind == "infrastructure"
                    for step in step_results
                    if step.status in ("failed", "blocked")
                )
                else "aborted"
            )
        notes = "fake mode: deterministic stub; expected result not checked"
        return _make_case_result(
            case,
            step_results,
            expected_check_mode=expected_mode,
            execution=execution,
            notes=notes,
        )

    async def run_plan_on_agent(
        self,
        agent: HylyreAgent,
        plan_path: Path | str,
        *,
        feature: str,
        bundle: str | None = None,
        page_name: str | None = None,
        wait_time: float = 1.0,
        params: str = "",
        mock_group: str | None = None,
        check_expected: bool = True,
        failure_dir: Path | str | None = None,
    ) -> ScenarioRunResult:
        """Drive ``HylyreAgent`` from plan rows and retain every step result."""

        if self._use_fakes:
            raise ValueError("run_plan_on_agent requires ScenarioRunner(use_fakes=False)")
        plan = parse_test_plan(plan_path)
        if agent.mock_controller is not None and mock_group:
            await agent.mock_activate_group(mock_group)
        if bundle:
            await agent.start_app(
                bundle,
                page_name=page_name,
                params=params or "",
                wait_time=wait_time,
            )
        results: list[CaseResult] = []
        for case in plan.cases:
            results.append(
                await self._run_case_on_agent(
                    agent,
                    case,
                    check_expected=check_expected,
                    failure_dir=failure_dir,
                )
            )
        return ScenarioRunResult(
            feature=feature,
            plan=plan,
            case_results=tuple(results),
            use_fakes=False,
            environment={
                "ui_driver": type(agent.ui).__name__,
                "hypium_version": str(
                    getattr(agent.ui, "hypium_version", "unavailable")
                    or "unavailable"
                ),
            },
        )

    async def _run_case_on_agent(
        self,
        agent: HylyreAgent,
        case: TestCase,
        *,
        check_expected: bool,
        failure_dir: Path | str | None = None,
    ) -> CaseResult:
        step_results: list[StepResult] = []
        notes: list[str] = []
        execution = "completed"
        raw_steps = _iter_steps(case.steps)
        pending_toast_skip: str | None = None

        def block_suffix(
            start: int, reason: str, root_failure: StepResult | None = None
        ) -> None:
            for blocked_idx in range(start, len(raw_steps)):
                step_results.append(
                    blocked_step_result(
                        raw_steps[blocked_idx],
                        index=blocked_idx,
                        reason=reason,
                        root_failure=root_failure,
                    )
                )

        def append_expected_not_run(
            mode: str, reason: str, root_failure: StepResult | None = None
        ) -> None:
            failure_kind = "capability"
            failure_code = "capability_unsupported"
            status = "skipped"
            if mode == "checked_vlm":
                failure_kind = (
                    root_failure.failure_kind
                    if root_failure is not None
                    and root_failure.failure_kind is not None
                    else "infrastructure"
                )
                failure_code = (
                    root_failure.failure_code
                    if root_failure is not None
                    and root_failure.failure_code is not None
                    else "driver_failure"
                )
                status = "blocked"
            step_results.append(
                StepResult(
                    index=len(step_results),
                    kind="expected_check",
                    role="assertion",
                    status=status,
                    failure_kind=failure_kind,  # type: ignore[arg-type]
                    failure_code=failure_code,
                    duration_ms=0.0,
                    evidence={
                        "channel": "vlm",
                        "assertion_executed": False,
                        "result": "disabled" if mode == "disabled_by_flag" else (
                            "unavailable" if mode == "unavailable_no_vlm" else "blocked"
                        ),
                        "reason": reason,
                    },
                    error=reason,
                )
            )

        for step_idx, step in enumerate(raw_steps):
            toast_skip_reason: str | None = None
            if pending_toast_skip is not None:
                if toast_assertion_on_unsupported(step) == "skip":
                    step_results.append(
                        StepResult(
                            index=step_idx,
                            kind=planned_step_kind(step),
                            role="assertion",
                            status="skipped",
                            failure_kind="capability",
                            failure_code="capability_unsupported",
                            duration_ms=0.0,
                            evidence={
                                "channel": "toast",
                                "listener_started": False,
                                "assertion_executed": False,
                                "result": "skipped",
                                "reason": pending_toast_skip,
                            },
                            error="Toast assertion skipped: capability unsupported",
                        )
                    )
                    notes.append("Toast assertion skipped: capability unsupported")
                    pending_toast_skip = None
                    continue
                pending_toast_skip = None

            if _step_triggers_toast_assertion(raw_steps, step_idx):
                try:
                    listener = await agent.start_toast_listening()
                    if isinstance(listener, dict) and listener.get("listener_started") is False:
                        raise CapabilityUnsupported(
                            "Toast listener capability unavailable",
                            evidence={
                                "channel": listener.get("channel", "toast"),
                                "listener_started": False,
                            },
                        )
                except Exception as exc:
                    if (
                        toast_assertion_on_unsupported(raw_steps[step_idx + 1]) == "skip"
                        and classify_exception(exc)[1] == "capability_unsupported"
                    ):
                        toast_skip_reason = str(exc)
                    else:
                        current = result_from_exception(
                            exc=exc,
                            index=step_idx,
                            kind=planned_step_kind(step),
                            role=planned_step_role(step),  # type: ignore[arg-type]
                            duration_ms=0.0,
                        )
                        if current.error:
                            notes.append(current.error)
                        step_results.append(current)
                        execution = (
                            "infrastructure_failed"
                            if current.failure_kind == "infrastructure"
                            else "aborted"
                        )
                        block_suffix(
                            step_idx + 1,
                            f"step {step_idx} failed before Toast trigger",
                            current,
                        )
                        break

            current = await execute_ledger_step(
                agent, step, index=step_idx, case_id=case.case_id
            )
            if toast_skip_reason is not None and current.status == "passed":
                current = replace(
                    current,
                    evidence={
                        **(current.evidence or {}),
                        "toast_listener": {
                            "listener_started": False,
                            "result": "unsupported",
                            "reason": toast_skip_reason,
                        },
                    },
                )
                pending_toast_skip = toast_skip_reason
            if current.status in ("failed", "blocked"):
                if current.error:
                    notes.append(current.error)
                diag = await capture_step_failure(
                    agent,
                    failure_dir=failure_dir,
                    step_label=f"{case.case_id}-step-{step_idx}",
                )
                if diag:
                    notes.append(diag)
                    current = _with_diagnostics(current, diag)
                step_results.append(current)
                if current.failure_kind == "infrastructure":
                    execution = "infrastructure_failed"
                else:
                    execution = "aborted"
                block_suffix(
                    step_idx + 1,
                    f"step {step_idx} status={current.status}",
                    current,
                )
                break
            step_results.append(current)
            if current.status == "skipped":
                notes.append(current.error or "step skipped")

        expected_mode = "empty"
        expected = case.expected.strip()
        if not _expected_is_empty(case.expected):
            if not check_expected:
                expected_mode = "disabled_by_flag"
                append_expected_not_run(
                    expected_mode, "expected check disabled by flag"
                )
            elif agent.vlm is None:
                expected_mode = "unavailable_no_vlm"
                append_expected_not_run(
                    expected_mode, "expected check unavailable: no VLM"
                )
            elif execution == "completed":
                expected_mode = "checked_vlm"
                expected_result = await execute_expected_assertion(
                    agent,
                    expected,
                    index=len(step_results),
                    case_id=case.case_id,
                )
                step_results.append(expected_result)
                if expected_result.status in ("failed", "blocked"):
                    notes.append(expected_result.error or "expected assertion failed")
                    execution = (
                        "infrastructure_failed"
                        if expected_result.failure_kind == "infrastructure"
                        else "aborted"
                    )
            else:
                expected_mode = "checked_vlm"
                root_failure = next(
                    (
                        step
                        for step in reversed(step_results)
                        if step.status in ("failed", "blocked")
                    ),
                    None,
                )
                append_expected_not_run(
                    expected_mode,
                    f"expected check blocked by case execution={execution}",
                    root_failure,
                )
        return _make_case_result(
            case,
            step_results,
            expected_check_mode=expected_mode,
            execution=execution,
            notes="; ".join(notes),
        )


def _step_triggers_toast_assertion(steps: list[str], index: int) -> bool:
    if index + 1 >= len(steps):
        return False
    next_step = normalize_planned_step_text(steps[index + 1])
    try:
        parsed = json.loads(next_step)
    except (TypeError, json.JSONDecodeError):
        return False
    return isinstance(parsed, dict) and (
        "assert_toast" in parsed
        or (
            isinstance(parsed.get("action"), dict)
            and parsed["action"].get("type") == "assert_toast"
        )
    )


def _iter_steps(text: str) -> list[str]:
    normalized = text.replace("；", "\n").replace(";", "\n")
    return [ln.strip() for ln in normalized.splitlines() if ln.strip()]


async def _execute_one_step(
    agent: HylyreAgent,
    case_id: str,
    step: str,
    tool_log: list[dict[str, Any]],
    *,
    step_idx: int = 0,
) -> Any:
    """Backward-compatible helper without maintaining a second tool log."""

    _ = (tool_log, step_idx)
    value = await _execute_step_value(agent, step, case_id=case_id)
    return value


__all__ = [
    "CaseResult",
    "ScenarioRunResult",
    "ScenarioRunner",
    "StepResult",
    "resolved_outcome",
]
