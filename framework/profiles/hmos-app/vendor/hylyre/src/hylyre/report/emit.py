"""Build Markdown and trace projections from one ``CaseResult`` ledger."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import hylyre
from hylyre.scenario.runner import ScenarioRunResult, resolved_outcome
from hylyre.scenario.results import redact_evidence, redact_text

TRACE_SCHEMA_VERSION = "0.3-p0"
LEGACY_TRACE_SCHEMA_VERSIONS = frozenset({"0.1-p0", "0.2-p4"})
_TIERS = ("P0", "P1", "P2")


def write_run_artifacts(
    result: ScenarioRunResult,
    *,
    report_path: Path,
    trace_path: Path,
    model_backend: str = "fake",
    schema_version: str = TRACE_SCHEMA_VERSION,
) -> None:
    """Write both projections; neither output owns runtime result state."""

    report_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        _markdown_report(result, schema_version=schema_version), encoding="utf-8"
    )
    trace_path.write_text(
        json.dumps(
            _trace_object(
                result,
                model_backend=model_backend,
                schema_version=schema_version,
            ),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _normalize_tier(priority: str) -> str:
    p = priority.upper().strip()
    if p in _TIERS:
        return p
    if p.startswith("P0"):
        return "P0"
    if p.startswith("P1"):
        return "P1"
    return "P2"


def _verdict_from_outcome(outcome: str, pass_ratio: float) -> str:
    if outcome == "success" and pass_ratio >= 1.0:
        return "达标"
    if outcome == "partial" and pass_ratio > 0:
        return "有条件达标"
    if 0 < pass_ratio < 1.0:
        return "有条件达标"
    return "不达标"


def _priority_counts(result: ScenarioRunResult) -> dict[str, dict[str, int]]:
    buckets: dict[str, dict[str, int]] = {t: {"total": 0, "passed": 0} for t in _TIERS}
    for cr in result.case_results:
        tier = _normalize_tier(cr.case.priority)
        bucket = buckets[tier]
        bucket["total"] += 1
        if cr.verification == "passed" and cr.evidence == "complete":
            bucket["passed"] += 1
    return buckets


def _safe_cell(value: Any) -> str:
    return str(value).replace("|", "/").replace("\n", " ").strip()


def _markdown_report(
    result: ScenarioRunResult,
    *,
    schema_version: str = TRACE_SCHEMA_VERSION,
) -> str:
    lines: list[str] = []
    passed = sum(
        1
        for item in result.case_results
        if item.verification == "passed" and item.evidence == "complete"
    )
    total = len(result.case_results)
    ratio = passed / total if total else 0.0
    outcome = resolved_outcome(result)
    verdict = _verdict_from_outcome(outcome, ratio)
    buckets = _priority_counts(result)

    lines.extend(
        [
            f"# 测试报告 — {result.feature}",
            "",
            "## 测试概览",
            "",
            f"- **特性**: {result.feature}",
            f"- **计划**: `{result.plan.path.as_posix()}`",
            f"- **模式**: {'fake 驱动（无真机）' if result.use_fakes else '真机'}",
            f"- **trace schema**: `{schema_version}`",
            "",
            "## 测试执行结果",
            "",
            "| 用例编号 | 用例名称 | 优先级 | 关联 AC | 状态 | execution | verification | evidence | expected_check_mode | 备注 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for cr in result.case_results:
        c = cr.case
        lines.append(
            "| "
            + " | ".join(
                [
                    _safe_cell(c.case_id),
                    _safe_cell(c.name),
                    _safe_cell(c.priority),
                    _safe_cell(c.ac_ref),
                    _safe_cell(cr.status),
                    _safe_cell(cr.execution),
                    _safe_cell(cr.verification),
                    _safe_cell(cr.evidence),
                    _safe_cell(cr.expected_check_mode),
                    _safe_cell(redact_text(cr.notes) or ""),
                ]
            )
            + " |"
        )
    lines.extend(["", "## 步骤证据", "", "| 用例编号 | index | kind | role | status | failure_kind | failure_code | evidence |", "| --- | --- | --- | --- | --- | --- | --- | --- |"])
    for cr in result.case_results:
        for step in cr.steps:
            evidence = json.dumps(
                redact_evidence(step.evidence), ensure_ascii=False, sort_keys=True
            )
            lines.append(
                "| "
                + " | ".join(
                    [
                        _safe_cell(cr.case.case_id),
                        str(step.index),
                        _safe_cell(step.kind),
                        _safe_cell(step.role),
                        _safe_cell(step.status),
                        _safe_cell(step.failure_kind),
                        _safe_cell(step.failure_code),
                        _safe_cell(evidence),
                    ]
                )
                + " |"
            )
    lines.extend(["", "## 缺陷清单", ""])
    failures = [
        cr for cr in result.case_results if cr.status in ("失败", "阻塞")
    ]
    if not failures:
        lines.append("无失败项。")
    else:
        for cr in failures:
            lines.append(
                f"- **{_safe_cell(cr.case.case_id)}** "
                f"{_safe_cell(cr.case.name)}: {cr.status} — "
                f"{_safe_cell(redact_text(cr.notes) or '')}"
            )
    lines.extend(["", "## 通过率统计", ""])
    for tier in _TIERS:
        bucket = buckets[tier]
        t, ok = bucket["total"], bucket["passed"]
        pct = f"{100.0 * ok / t:.1f}%" if t else "n/a"
        lines.append(f"- **{tier}**: {ok}/{t}（{pct}）")
    overall = f"{100.0 * passed / total:.1f}%" if total else "n/a"
    lines.append(f"- **总体**: {passed}/{total}（{overall}）")
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"{verdict}（执行结果 outcome={outcome}，通过率 {passed}/{total}）。",
            "",
        ]
    )
    return "\n".join(lines)


def _trace_environment(
    result: ScenarioRunResult, *, schema_version: str
) -> dict[str, str]:
    supplied = dict(result.environment or {})
    return {
        "hylyre_version": hylyre.__version__,
        "hypium_version": supplied.get("hypium_version", "unavailable"),
        "trace_schema_version": schema_version,
        "selector_engine": "fake" if result.use_fakes else "mixed",
    }


def _trace_object(
    result: ScenarioRunResult,
    *,
    model_backend: str,
    schema_version: str = TRACE_SCHEMA_VERSION,
) -> dict[str, Any]:
    outcome = resolved_outcome(result)
    cases = [cr.to_dict() for cr in result.case_results]
    trace: dict[str, Any] = {
        "schema_version": schema_version,
        "feature": result.feature,
        "phase": "testing",
        "outcome": outcome,
        "model_backend": model_backend,
        "tool_calls": list(result.tool_calls),
        "retries": 0,
        "artifacts": {
            "plan": result.plan.path.as_posix(),
            "use_fakes": result.use_fakes,
        },
        "cases": cases,
    }
    if schema_version == TRACE_SCHEMA_VERSION:
        environment = _trace_environment(
            result, schema_version=schema_version
        )
        trace["environment"] = environment
        # Keep flat aliases for consumers that read the older trace envelope.
        trace["hylyre_version"] = environment["hylyre_version"]
        trace["hypium_version"] = environment["hypium_version"]
        trace["selector_engine"] = environment["selector_engine"]
    return trace


__all__ = [
    "LEGACY_TRACE_SCHEMA_VERSIONS",
    "TRACE_SCHEMA_VERSION",
    "write_run_artifacts",
]
