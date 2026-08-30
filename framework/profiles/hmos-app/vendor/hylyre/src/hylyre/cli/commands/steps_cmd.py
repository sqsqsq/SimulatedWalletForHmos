"""Batch execution of planned JSON steps (CLI / session daemon / MCP)."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from hylyre.api.agent import HylyreAgent
from hylyre.api.exceptions import CapabilityUnsupported, classify_exception
from hylyre.api.failure_diag import capture_step_failure
from hylyre.cli.commands.loop_cmd import _session_ipc, _with_hypium_agent
from hylyre.scenario.ledger import (
    blocked_step_result,
    execute_ledger_step,
    planned_step_kind,
    planned_step_role,
    step_result_to_batch_row,
    toast_assertion_on_unsupported,
)
from hylyre.scenario.results import StepResult, result_from_exception


def _normalize_on_fail(raw: str) -> str:
    s = raw.strip().lower()
    if s in ("abort", "skip"):
        return s
    raise ValueError("on_fail must be abort or skip")


async def run_steps_on_agent(
    agent: HylyreAgent,
    steps: list[dict[str, Any]],
    on_fail: str = "abort",
    *,
    failure_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Execute planned JSON dicts sequentially; return structured per-step results."""
    mode = _normalize_on_fail(on_fail)
    results: list[dict[str, Any]] = []
    total = len(steps)
    t0_all = time.perf_counter()
    pending_toast_skip: str | None = None
    executed_count = 0

    if total == 0:
        return {
            "total": 0,
            "executed": 0,
            "results": [],
            "on_fail": mode,
            "total_elapsed_ms": 0.0,
        }

    for idx, raw in enumerate(steps):
        if not isinstance(raw, dict):
            raise TypeError(f"steps[{idx}] must be object, got {type(raw).__name__}")
        operation_attempted = False

        if pending_toast_skip is not None:
            if toast_assertion_on_unsupported(raw) == "skip":
                step_result = StepResult(
                    index=idx,
                    kind=planned_step_kind(raw),
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
                pending_toast_skip = None
            else:
                pending_toast_skip = None
                operation_attempted = True
                step_result = await execute_ledger_step(
                    agent, raw, index=idx, case_id=f"step-{idx}"
                )
        elif _batch_step_triggers_toast(steps, idx):
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
                    toast_assertion_on_unsupported(steps[idx + 1]) == "skip"
                    and classify_exception(exc)[1] == "capability_unsupported"
                ):
                    operation_attempted = True
                    step_result = await execute_ledger_step(
                        agent, raw, index=idx, case_id=f"step-{idx}"
                    )
                    if step_result.status == "passed":
                        pending_toast_skip = str(exc)
                        step_result = replace(
                            step_result,
                            evidence={
                                **(step_result.evidence or {}),
                                "toast_listener": {
                                    "listener_started": False,
                                    "result": "unsupported",
                                    "reason": str(exc),
                                },
                            },
                        )
                else:
                    step_result = result_from_exception(
                        exc=exc,
                        index=idx,
                        kind=planned_step_kind(raw),
                        role=planned_step_role(raw),  # type: ignore[arg-type]
                        duration_ms=0.0,
                    )
            else:
                operation_attempted = True
                step_result = await execute_ledger_step(
                    agent, raw, index=idx, case_id=f"step-{idx}"
                )
        else:
            operation_attempted = True
            step_result = await execute_ledger_step(
                agent, raw, index=idx, case_id=f"step-{idx}"
            )
        if operation_attempted:
            executed_count += 1
        if step_result.status in ("failed", "blocked"):
            diag = await capture_step_failure(
                agent, failure_dir=failure_dir, step_label=f"step-{idx}"
            )
            if diag:
                names = [
                    item.split("=", 1)[1]
                    for item in diag.removeprefix(" failure_artifacts: ").split(", ")
                    if "=" in item
                ]
                step_result = replace(
                    step_result,
                    evidence={
                        **(step_result.evidence or {}),
                        "failure_artifacts": names,
                    },
                    error=((step_result.error or "") + diag)[:4000],
                )
        results.append(step_result_to_batch_row(step_result, raw))
        if step_result.status in ("failed", "blocked") and mode == "abort":
            for blocked_idx in range(idx + 1, total):
                blocked = blocked_step_result(
                    steps[blocked_idx],
                    index=blocked_idx,
                    reason=f"step {idx} status={step_result.status}",
                    root_failure=step_result,
                )
                results.append(
                    step_result_to_batch_row(blocked, steps[blocked_idx])
                )
            return {
                "total": total,
                "executed": executed_count,
                "results": results,
                "on_fail": mode,
                "total_elapsed_ms": round(
                    (time.perf_counter() - t0_all) * 1000.0, 3
                ),
            }

    return {
        "total": total,
        "executed": executed_count,
        "results": results,
        "on_fail": mode,
        "total_elapsed_ms": round((time.perf_counter() - t0_all) * 1000.0, 3),
    }


def _batch_step_triggers_toast(
    steps: list[dict[str, Any]], index: int
) -> bool:
    if index + 1 >= len(steps):
        return False
    next_step = steps[index + 1]
    if "assert_toast" in next_step:
        return True
    action = next_step.get("action")
    return isinstance(action, dict) and action.get("type") == "assert_toast"


def load_steps_json_array(path: Path) -> list[dict[str, Any]]:
    raw = Path(path).read_text(encoding="utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError("--steps-file must contain a JSON array of step objects")
    return [dict(x) for x in parsed]  # type: ignore[arg-type]


def parse_steps_inline(json_str: str) -> list[dict[str, Any]]:
    parsed = json.loads(json_str)
    if not isinstance(parsed, list):
        raise ValueError("--steps must be a JSON array of step objects")
    return [dict(x) for x in parsed]  # type: ignore[arg-type]


def execute_run_steps(
    steps: list[dict[str, Any]],
    *,
    device_sn: str | None = None,
    mock_port: int | None = None,
    lyrebird_url: str | None = None,
    session_file: Path | None = None,
    on_fail: str = "abort",
    bundle: str | None = None,
    page_name: str | None = None,
    wait_time: float = 1.0,
    params: str = "",
    failure_dir: str | Path | None = None,
) -> dict[str, Any]:
    """CLI/sync entry: IPC session daemon or ephemeral Hypium agent."""
    if session_file is not None:
        ipc_params: dict[str, Any] = {
            "steps": steps,
            "on_fail": on_fail,
            "bundle": bundle,
            "page_name": page_name,
            "wait_time": wait_time,
            "params": params,
        }
        if failure_dir is not None:
            ipc_params["failure_dir"] = str(Path(failure_dir).resolve())
        return _session_ipc(session_file, "run_steps", ipc_params)

    async def _go(agent: HylyreAgent) -> dict[str, Any]:
        if bundle:
            await agent.start_app(
                bundle,
                page_name=page_name,
                params=params or "",
                wait_time=wait_time,
            )
        return await run_steps_on_agent(
            agent, steps, on_fail=on_fail, failure_dir=failure_dir
        )

    return asyncio.run(
        _with_hypium_agent(
            device_sn=device_sn,
            mock_port=mock_port,
            lyrebird_url=lyrebird_url,
            fn=_go,
        )
    )
