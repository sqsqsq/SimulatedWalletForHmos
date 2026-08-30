"""Serializable scenario result contract shared by runner and reporters."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Literal

from hylyre.api.exceptions import StepSkipped, classify_exception
from hylyre.api.selector_contract import selector_evidence
from hylyre.scenario.plan_parse import TestCase

Execution = Literal["completed", "aborted", "infrastructure_failed"]
Verification = Literal["passed", "failed", "inconclusive"]
EvidenceStatus = Literal["complete", "incomplete"]
ExpectedCheckMode = Literal[
    "checked_vlm", "disabled_by_flag", "unavailable_no_vlm", "empty"
]
StepRole = Literal["action", "assertion"]
StepStatus = Literal["passed", "failed", "blocked", "skipped"]
FailureKind = Literal["assertion", "selector", "capability", "infrastructure"]

FAILURE_CODES = frozenset(
    {
        "assertion_mismatch",
        "selector_not_found",
        "selector_ambiguous",
        "inline_target_unresolvable",
        "capability_unsupported",
        "device_unavailable",
        "driver_failure",
    }
)

_SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "account",
    "amount",
    "phone",
    "card",
    "id_number",
    "expected_text",
    "actual_text",
    "event_text",
    "input_value",
    "by_text",
    "by_value",
    "error",
    "notes",
)

_SENSITIVE_TEXT_PATTERNS = (
    re.compile(
        r"(?i)(?:account|账号|amount|金额|余额|phone|手机号|card|卡号|token|secret|password)"
        r"\s*[:=：]\s*[^,;，；\s)]+"
    ),
    re.compile(r"(?i)(?:by_text|text|value|instruction|expected|actual)\s*[:=：]\s*(['\"])(.*?)\1"),
    re.compile(
        r"(?i)(['\"])(?:by_text|text|value|instruction|expected|actual)\1"
        r"\s*:\s*(['\"])(.*?)\2"
    ),
    re.compile(r"(?<![\w])(?:¥|￥|\$)\s*[0-9][0-9,]*(?:\.[0-9]+)?"),
    re.compile(r"(?<![\w])[0-9][0-9,]{5,}(?![\w])"),
)

# These are structured selector association keys.  Their values identify a
# canonical UI target and must remain comparable in serialized evidence.
_SELECTOR_VALUE_KEYS = frozenset({"by_id", "by_key", "id", "key", "selected_id"})
# Bounds are machine evidence too, not user-facing text.
_STRUCTURED_SCALAR_KEYS = frozenset({"bounds"})
_STRUCTURED_VALUE_KEYS = _SELECTOR_VALUE_KEYS | _STRUCTURED_SCALAR_KEYS
_SENSITIVE_VALUE_KEYS = frozenset(
    {
        "text",
        "value",
        "instruction",
        "answer",
        "expected",
        "actual",
        "by_text",
        "by_value",
    }
)


def redact_text(value: str | None) -> str | None:
    """Mask sensitive human-facing text while retaining structured evidence."""

    if value is None:
        return None
    text = str(value)
    for pattern in _SENSITIVE_TEXT_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def redact_evidence(value: Any, *, key: str = "") -> Any:
    """Redact likely sensitive evidence before it reaches a trace/report."""

    lowered = key.lower()
    if lowered in _STRUCTURED_VALUE_KEYS and (
        value is None or isinstance(value, str)
    ):
        # Structured selector fields are machine evidence, not user text.
        # Unexpected containers fall through to recursive handling below so
        # nested text/value fields still redact.
        return value
    if lowered in _SENSITIVE_VALUE_KEYS or any(
        part in lowered for part in _SENSITIVE_KEY_PARTS
    ):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(k): redact_evidence(v, key=str(k))
            for k, v in value.items()
        }
    if isinstance(value, list):
        child_key = "" if lowered in _STRUCTURED_VALUE_KEYS else key
        return [redact_evidence(v, key=child_key) for v in value]
    if isinstance(value, tuple):
        child_key = "" if lowered in _STRUCTURED_VALUE_KEYS else key
        return [redact_evidence(v, key=child_key) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


@dataclass(frozen=True)
class StepResult:
    index: int
    kind: str
    role: StepRole
    status: StepStatus
    failure_kind: FailureKind | None = None
    failure_code: str | None = None
    duration_ms: float = 0.0
    selector: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": int(self.index),
            "kind": self.kind,
            "role": self.role,
            "status": self.status,
            "failure_kind": self.failure_kind,
            "failure_code": self.failure_code,
            "duration_ms": round(float(self.duration_ms), 3),
            "selector": redact_evidence(self.selector),
            "evidence": redact_evidence(self.evidence),
            "error": redact_text(self.error),
        }


def _project_legacy_status(
    *,
    execution: str,
    verification: str,
    steps: tuple[StepResult, ...],
) -> str:
    if execution == "infrastructure_failed":
        return "阻塞"
    if verification == "passed":
        return "通过"
    if any(s.status == "failed" for s in steps):
        return "失败"
    if any(s.status == "blocked" for s in steps):
        return "阻塞"
    if steps and all(s.status == "skipped" for s in steps):
        return "跳过"
    # Inconclusive execution must never retain the historical false-pass label.
    return "跳过"


@dataclass(frozen=True)
class CaseResult:
    """Case identity plus the single authoritative per-step result ledger."""

    case: TestCase
    status: str = ""
    notes: str = ""
    execution: Execution = "completed"
    verification: Verification = "inconclusive"
    evidence: EvidenceStatus = "complete"
    expected_check_mode: ExpectedCheckMode = "empty"
    steps: tuple[StepResult, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.status:
            return
        object.__setattr__(
            self,
            "status",
            _project_legacy_status(
                execution=self.execution,
                verification=self.verification,
                steps=self.steps,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.case.case_id,
            "name": self.case.name,
            "priority": self.case.priority,
            "ac_ref": self.case.ac_ref,
            "status": self.status,
            "notes": redact_text(self.notes) or "",
            "execution": self.execution,
            "verification": self.verification,
            "evidence": self.evidence,
            "expected_check_mode": self.expected_check_mode,
            "steps": [step.to_dict() for step in self.steps],
        }


def result_from_exception(
    *,
    exc: BaseException,
    index: int,
    kind: str,
    role: StepRole,
    duration_ms: float,
    selector: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
) -> StepResult:
    failure_kind, failure_code = classify_exception(exc)
    if failure_kind not in {"assertion", "selector", "capability", "infrastructure"}:
        failure_kind, failure_code = "infrastructure", "driver_failure"
    if failure_code not in FAILURE_CODES:
        failure_code = {
            "assertion": "assertion_mismatch",
            "selector": "selector_not_found",
            "capability": "capability_unsupported",
            "infrastructure": "driver_failure",
        }[failure_kind]
    exc_evidence = getattr(exc, "evidence", None)
    if isinstance(exc_evidence, dict):
        evidence = {**(evidence or {}), **exc_evidence}
    if isinstance(exc, StepSkipped):
        status: StepStatus = "skipped"
    elif failure_kind == "capability":
        # A capability limitation blocks a required operation; it is never a
        # normal assertion failure.  Optional Toast handling can convert it to
        # StepSkipped before this function is called.
        status = "blocked"
    elif failure_kind == "infrastructure" and failure_code == "device_unavailable":
        status = "blocked"
    else:
        status = "failed"
    serialized_selector = selector
    if serialized_selector is None:
        serialized_selector = getattr(exc, "selector", None)
    if isinstance(serialized_selector, dict):
        required_selector_keys = {
            "engine",
            "requested_match",
            "effective_match",
            "candidate_count",
        }
        if not required_selector_keys.issubset(serialized_selector):
            candidate_count = 0
            if isinstance(evidence, dict) and isinstance(
                evidence.get("candidate_count"), int
            ):
                candidate_count = int(evidence["candidate_count"])
            serialized_selector = selector_evidence(
                serialized_selector,
                engine=str(serialized_selector.get("engine") or "resolver"),
                candidate_count=candidate_count,
                selected_id=(
                    str(serialized_selector["selected_id"])
                    if serialized_selector.get("selected_id") is not None
                    else None
                ),
                bounds=(
                    str(serialized_selector["bounds"])
                    if serialized_selector.get("bounds") is not None
                    else None
                ),
            )
    return StepResult(
        index=index,
        kind=kind,
        role=role,
        status=status,
        failure_kind=failure_kind,  # type: ignore[arg-type]
        failure_code=failure_code,
        duration_ms=duration_ms,
        selector=serialized_selector,
        evidence=evidence,
        error=redact_text(str(exc)[:4000]),
    )


def _has_evidence(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


def _toast_window_covered(step: StepResult) -> bool:
    if step.kind != "assert_toast":
        return True
    return (
        isinstance(step.evidence, dict)
        and step.evidence.get("trigger_window_covered") is True
    )


def required_assertion_steps(
    steps: tuple[StepResult, ...],
    *,
    expected_check_mode: ExpectedCheckMode,
) -> tuple[StepResult, ...]:
    """Return assertions that participate in the case verification gate."""

    return tuple(
        step
        for step in steps
        if step.role == "assertion"
        and not (
            step.kind == "expected_check"
            and expected_check_mode in {"disabled_by_flag", "unavailable_no_vlm"}
        )
    )


def case_verdict(
    steps: tuple[StepResult, ...],
    *,
    expected_check_mode: ExpectedCheckMode,
    execution: Execution = "completed",
) -> tuple[Verification, EvidenceStatus, str]:
    """Compute verification/evidence/legacy status from steps only."""

    assertion_steps = list(
        required_assertion_steps(
            steps,
            expected_check_mode=expected_check_mode,
        )
    )
    failed_assertions = [s for s in assertion_steps if s.status == "failed"]
    blocked_assertions = [s for s in assertion_steps if s.status == "blocked"]
    skipped_assertions = [s for s in assertion_steps if s.status == "skipped"]
    failed_steps = [s for s in steps if s.status == "failed"]
    blocked_steps = [s for s in steps if s.status == "blocked"]

    if execution != "completed":
        # An aborted/infrastructure-failed execution can never be verified,
        # even when an earlier assertion happened to pass.
        verification: Verification = "failed"
    elif failed_steps or failed_assertions:
        verification = "failed"
    elif blocked_steps or blocked_assertions:
        verification = "failed"
    elif skipped_assertions:
        verification = "inconclusive"
    else:
        expected_rows = [s for s in steps if s.kind == "expected_check"]
        expected_ok = expected_check_mode != "checked_vlm" or (
            len(expected_rows) == 1
            and expected_rows[0].status == "passed"
            and _has_evidence(expected_rows[0].evidence)
        )
        all_required_assertions_pass = bool(assertion_steps) and all(
            s.status == "passed"
            and _has_evidence(s.evidence)
            and _toast_window_covered(s)
            for s in assertion_steps
        )
        if all_required_assertions_pass and expected_ok:
            verification = "passed"
        else:
            verification = "inconclusive"

    required_ids = {id(step) for step in assertion_steps}
    evidence_complete = all(
        _has_evidence(step.evidence)
        if step.status == "passed"
        or (step.role == "assertion" and id(step) in required_ids)
        else True
        for step in steps
    )
    if any(
        step.role == "assertion"
        and id(step) in required_ids
        and step.status == "passed"
        and (
            not _has_evidence(step.evidence)
            or not _toast_window_covered(step)
        )
        for step in steps
    ):
        evidence_complete = False
    evidence_status: EvidenceStatus = "complete" if evidence_complete else "incomplete"
    if verification == "passed" and evidence_status != "complete":
        verification = "inconclusive"
    legacy = _project_legacy_status(
        execution=execution,
        verification=verification,
        steps=steps,
    )
    return verification, evidence_status, legacy


def outcome_from_case_results(case_results: Any) -> str:
    """Project cases to the historical run outcome using the same rule everywhere."""

    cases = list(case_results)
    if not cases:
        return "aborted"
    if all(
        case.execution == "completed"
        and case.verification == "passed"
        and case.evidence == "complete"
        for case in cases
    ):
        return "success"

    has_blocked = any(
        case.execution == "infrastructure_failed"
        or case.status == "阻塞"
        or any(step.status == "blocked" for step in case.steps)
        for case in cases
    )
    has_failed = any(
        case.verification == "failed" or case.status == "失败"
        for case in cases
    )
    has_passed = any(
        case.execution == "completed"
        and case.verification == "passed"
        and case.evidence == "complete"
        for case in cases
    )
    if has_blocked:
        return "failed"
    if has_failed and has_passed:
        return "partial"
    if has_failed:
        return "failed"
    return "partial"


__all__ = [
    "CaseResult",
    "ExpectedCheckMode",
    "FAILURE_CODES",
    "StepResult",
    "case_verdict",
    "redact_evidence",
    "redact_text",
    "result_from_exception",
    "outcome_from_case_results",
    "required_assertion_steps",
]
