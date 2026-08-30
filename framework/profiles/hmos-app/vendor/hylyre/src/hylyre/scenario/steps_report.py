"""Synthesize ScenarioRunResult from ``run --steps-file`` batch output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hylyre.scenario.ledger import planned_step_kind, planned_step_role
from hylyre.scenario.plan_parse import ParsedPlan, TestCase
from hylyre.scenario.results import CaseResult, StepResult, case_verdict, redact_text
from hylyre.scenario.runner import ScenarioRunResult


def steps_batch_to_scenario_result(
    *,
    feature: str,
    steps_path: Path,
    batch: dict[str, Any],
    bundle: str | None = None,
    page_name: str | None = None,
) -> ScenarioRunResult:
    """Map per-step batch results to plan-shaped ``ScenarioRunResult`` for report/trace emit."""
    cases: list[TestCase] = []
    case_results: list[CaseResult] = []
    _ = (bundle, page_name)

    for row in batch.get("results", []):
        if not isinstance(row, dict):
            continue
        idx = int(row.get("index", len(cases)))
        step_obj = row.get("step", {})
        case_id = f"STEP-{idx:03d}"
        name = json.dumps(step_obj, ensure_ascii=False)[:120]
        tc = TestCase(
            case_id=case_id,
            name=name,
            preconditions="-",
            steps=name,
            expected="-",
            priority="P2",
            ac_ref=f"AC-{idx:03d}",
        )
        cases.append(tc)
        raw_result = row.get("step_result")
        if isinstance(raw_result, dict):
            step_result = StepResult(
                index=int(raw_result.get("index", idx)),
                kind=str(raw_result.get("kind", planned_step_kind(step_obj))),
                role=str(raw_result.get("role", planned_step_role(step_obj))),  # type: ignore[arg-type]
                status=str(
                    raw_result.get(
                        "status",
                        "passed"
                        if row.get("status") == "ok"
                        else "skipped"
                        if row.get("status") == "skipped"
                        else "failed",
                    )
                ),  # type: ignore[arg-type]
                failure_kind=raw_result.get("failure_kind"),  # type: ignore[arg-type]
                failure_code=raw_result.get("failure_code"),
                duration_ms=float(raw_result.get("duration_ms", row.get("elapsed_ms", 0))),
                selector=raw_result.get("selector"),
                evidence=raw_result.get("evidence"),
                error=raw_result.get("error") or row.get("error"),
            )
        else:
            row_status = row.get("status")
            step_status = (
                "passed" if row_status == "ok" else
                "skipped" if row_status == "skipped" else "failed"
            )
            step_result = StepResult(
                index=idx,
                kind=planned_step_kind(step_obj),
                role=planned_step_role(step_obj),  # type: ignore[arg-type]
                status=step_status,  # type: ignore[arg-type]
                failure_kind=(
                    "capability"
                    if row_status == "skipped"
                    else None
                    if row_status == "ok"
                    else "infrastructure"
                ),  # type: ignore[arg-type]
                failure_code=(
                    "capability_unsupported"
                    if row_status == "skipped"
                    else None if row_status == "ok" else "driver_failure"
                ),
                duration_ms=float(row.get("elapsed_ms", 0)),
                evidence={"channel": "legacy_batch", "result": row_status == "ok"},
                error=str(row.get("error", ""))[:4000] or None,
            )
        execution = (
            "infrastructure_failed"
            if step_result.failure_kind == "infrastructure"
            and step_result.status == "blocked"
            else "aborted"
            if step_result.status in ("failed", "blocked")
            else "completed"
        )
        verification, evidence, legacy_status = case_verdict(
            (step_result,), expected_check_mode="empty", execution=execution
        )
        notes = redact_text(str(row.get("error", ""))[:2000]) or ""
        case_results.append(
            CaseResult(
                case=tc,
                status=legacy_status,
                notes=notes,
                execution=execution,  # type: ignore[arg-type]
                verification=verification,
                evidence=evidence,
                expected_check_mode="empty",
                steps=(step_result,),
            )
        )

    plan = ParsedPlan(path=Path(steps_path), cases=tuple(cases))
    return ScenarioRunResult(
        feature=feature,
        plan=plan,
        case_results=tuple(case_results),
        use_fakes=False,
    )
