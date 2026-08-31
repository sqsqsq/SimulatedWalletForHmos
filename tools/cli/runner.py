"""Foreground execution engine used by both direct and detached runs."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from typing import Any

from .adapters import AdapterEvent, get_adapter
from .models import EventCallback, FailureKind, RunResult, RunStatus
from .process_control import (
    WindowsProcessJob,
    force_kill_tree,
    popen_group_options,
    stop_popen,
)
from .registry import CliConfigurationError, CliNotFoundError, CliRegistry
from .run_store import RunStore, now_iso


AUTH_PATTERNS = (
    "authentication required",
    "auth required",
    "not logged in",
    "please log in",
    "please login",
    "unauthorized",
    "invalid api key",
    # Providers spell the same failure several ways.  Alibaba Model Studio answers
    # `{"code":"invalid_api_key","message":"Incorrect API key provided."}` — neither
    # spelling matches the spaced form above, so without these two the run is
    # classified as a plain command failure and the config group never trips.
    "invalid_api_key",
    "incorrect api key",
    "status 401",
    "<401>",
)
CONTENT_POLICY_PATTERNS = (
    "internalerror.algo.datainspectionfailed",
    "output data may contain inappropriate content",
    "data inspection failed",
)
SUBSCRIPTION_PATTERNS = (
    "subscription",
    "quota exceeded",
    "insufficient credits",
    "payment required",
    "billing",
    "usage limit",
    "credit balance",
)
MODEL_PATTERNS = (
    "model unavailable",
    "model is unavailable",
    "model access denied",
    "unknown model",
    "model not found",
)


def classify_failure(text: str) -> FailureKind:
    lowered = text.lower()
    # A bare HTTP 400 is not enough: malformed requests are configuration
    # failures, while these provider messages specifically mean content review.
    if any(pattern in lowered for pattern in CONTENT_POLICY_PATTERNS):
        return FailureKind.CONTENT_POLICY_REJECTED
    if any(pattern in lowered for pattern in SUBSCRIPTION_PATTERNS):
        return FailureKind.SUBSCRIPTION_UNAVAILABLE
    if any(pattern in lowered for pattern in AUTH_PATTERNS):
        return FailureKind.AUTH_REQUIRED
    if any(pattern in lowered for pattern in MODEL_PATTERNS):
        return FailureKind.MODEL_UNAVAILABLE
    return FailureKind.COMMAND_FAILED


class CliRunner:
    def __init__(self, registry: CliRegistry) -> None:
        self.registry = registry

    def execute(
        self,
        store: RunStore,
        *,
        on_event: EventCallback | None = None,
    ) -> RunResult:
        request = store.request()
        started = time.monotonic()
        text_parts: list[str] = []
        observed_output: list[str] = []
        captured_session = request.session_id
        timed_out = False
        stopped = False
        stop_failed = False
        event_stream_failed = False
        forced = False
        proc: subprocess.Popen[str] | None = None
        process_job: WindowsProcessJob | None = None
        reader_failures: list[BaseException] = []
        reader_error_text = ""

        def emit(adapter_event: AdapterEvent | None = None, **values: Any) -> None:
            nonlocal captured_session
            if adapter_event is not None:
                values = {
                    "event_type": adapter_event.type,
                    "content": adapter_event.content,
                    "session_id": adapter_event.session_id,
                    "message_id": adapter_event.message_id,
                    "tool_call_id": adapter_event.tool_call_id,
                    "tool_name": adapter_event.tool_name,
                    "tool_status": adapter_event.tool_status,
                    "tool_input": adapter_event.tool_input,
                    "tool_output": adapter_event.tool_output,
                    "usage": adapter_event.usage,
                }
            event_type = str(values.pop("event_type"))
            sid = values.get("session_id")
            if sid:
                if sid == captured_session and event_type == "session":
                    return
                captured_session = str(sid)
                store.update(session_id=captured_session)
            content = values.get("content")
            if content:
                observed_output.append(str(content))
                if event_type == "text":
                    text_parts.append(str(content))
            event = store.append_event(event_type, **values)
            if on_event:
                try:
                    on_event(event)
                except Exception:
                    # A consumer callback must not invalidate a completed CLI call.
                    pass

        try:
            store.update(
                status=RunStatus.STARTING.value,
                runner_pid=os.getpid(),
                started_at=now_iso(),
            )
            resolved = self.registry.build(request)
            adapter = get_adapter(resolved.adapter)
            env = {
                **os.environ,
                **resolved.env,
                # Stable identity for child tools during this CLI execution.
                # It is runtime metadata and is never added to the model prompt.
                "AIDH_CLI_RUN_ID": store.run_id,
            }
            command = [resolved.executable, *resolved.argv]
            store.update(
                cli=resolved.cli,
                profile=resolved.profile,
                command=command,
                effective_cwd=str(resolved.cwd) if resolved.cwd else "",
                soft_timeout_sec=resolved.soft_timeout_sec,
                hard_timeout_sec=resolved.hard_timeout_sec,
                stop_grace_sec=resolved.stop_grace_sec,
            )
            proc = subprocess.Popen(
                command,
                shell=False,
                cwd=str(resolved.cwd) if resolved.cwd else None,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env,
                **popen_group_options(),
            )
            if os.name == "nt":
                process_job = WindowsProcessJob.create(store.run_id, proc)
            store.update(
                status=RunStatus.RUNNING.value,
                child_pid=proc.pid,
                process_job=process_job.name if process_job else "",
            )
            emit(
                event_type="lifecycle",
                content="running",
            )

            def reader() -> None:
                if proc is None or proc.stdout is None:
                    return
                try:
                    for raw_line in iter(proc.stdout.readline, ""):
                        line = raw_line.rstrip("\r\n")
                        if not line:
                            continue
                        store.append_raw(line)
                        parsed = False
                        if line.lstrip().startswith("{"):
                            try:
                                value = json.loads(line)
                            except json.JSONDecodeError:
                                pass
                            else:
                                if isinstance(value, dict):
                                    try:
                                        items = list(adapter.parse(value))
                                    except Exception as exc:
                                        emit(
                                            event_type="error",
                                            content=(
                                                "adapter error: "
                                                f"{type(exc).__name__}: {exc}"
                                            ),
                                        )
                                    else:
                                        for item in items:
                                            emit(item)
                                    # Storage/emit failures deliberately escape
                                    # this block and are handled by the reader
                                    # watchdog, rather than recursively trying
                                    # to report through the failed event path.
                                    parsed = True
                        if not parsed:
                            emit(event_type="cli_output", content=line)
                except BaseException as exc:
                    reader_failures.append(exc)
                finally:
                    try:
                        proc.stdout.close()
                    except OSError:
                        pass

            reader_thread = threading.Thread(
                target=reader,
                name=f"cli-reader-{store.run_id}",
                daemon=True,
            )
            reader_thread.start()
            soft_notified = False
            while proc.poll() is None:
                elapsed = time.monotonic() - started
                if reader_failures:
                    event_stream_failed = True
                    reader_error = reader_failures[0]
                    reader_error_text = (
                        f"{type(reader_error).__name__}: {reader_error}"
                    )
                    store.update(
                        status=RunStatus.STOPPING.value,
                        reader_error=reader_error_text,
                    )
                    forced, stopped_ok = stop_popen(
                        proc,
                        resolved.stop_grace_sec,
                        force=True,
                        job=process_job,
                    )
                    stop_failed = not stopped_ok
                    break
                stop_request = store.stop_request()
                if stop_request is not None:
                    stopped = True
                    store.update(status=RunStatus.STOPPING.value)
                    emit(event_type="lifecycle", content="stop requested")
                    forced, stopped_ok = stop_popen(
                        proc,
                        resolved.stop_grace_sec,
                        force=bool(stop_request.get("force", False)),
                        job=process_job,
                    )
                    stop_failed = not stopped_ok
                    break
                if (resolved.soft_timeout_sec > 0 and not soft_notified
                        and elapsed > resolved.soft_timeout_sec):
                    soft_notified = True
                    store.update(status=RunStatus.OVERTIME.value, overtime_at=now_iso())
                    emit(
                        event_type="lifecycle",
                        content="soft timeout reached; continuing",
                    )
                if resolved.hard_timeout_sec > 0 and elapsed > resolved.hard_timeout_sec:
                    timed_out = True
                    store.update(status=RunStatus.STOPPING.value, hard_timeout_at=now_iso())
                    emit(
                        event_type="lifecycle",
                        content="hard timeout reached; force stopping",
                    )
                    forced, stopped_ok = stop_popen(
                        proc,
                        resolved.stop_grace_sec,
                        force=True,
                        job=process_job,
                    )
                    stop_failed = not stopped_ok
                    break
                time.sleep(0.05)

            if proc.poll() is None:
                try:
                    proc.wait(timeout=max(1.0, resolved.stop_grace_sec + 1.0))
                except subprocess.TimeoutExpired:
                    killed = force_kill_tree(
                        proc.pid,
                        process_job.name if process_job else "",
                    )
                    forced = True
                    stop_failed = not killed
            reader_thread.join(timeout=10)
            if reader_failures:
                event_stream_failed = True
                if not reader_error_text:
                    reader_error = reader_failures[0]
                    reader_error_text = (
                        f"{type(reader_error).__name__}: {reader_error}"
                    )
            exit_code = proc.returncode
            if stop_failed:
                status = RunStatus.STOP_FAILED
                failure_kind = FailureKind.STOP_FAILED
            elif event_stream_failed:
                status = RunStatus.FAILED
                failure_kind = FailureKind.EVENT_STREAM_FAILED
            elif timed_out:
                status = RunStatus.TIMED_OUT
                failure_kind = FailureKind.TIMED_OUT
                exit_code = 124
            elif stopped:
                status = RunStatus.STOPPED
                failure_kind = FailureKind.STOPPED
            elif exit_code == 0:
                status = RunStatus.SUCCEEDED
                failure_kind = FailureKind.NONE
            else:
                status = RunStatus.FAILED
                failure_kind = classify_failure("\n".join(observed_output))
        except CliNotFoundError as exc:
            exit_code = None
            status = RunStatus.FAILED
            failure_kind = FailureKind.CLI_UNAVAILABLE
            emit(event_type="error", content=str(exc))
        except CliConfigurationError as exc:
            exit_code = None
            status = RunStatus.FAILED
            failure_kind = FailureKind.CONFIGURATION_ERROR
            emit(event_type="error", content=str(exc))
        except Exception as exc:
            exit_code = proc.returncode if proc and proc.returncode is not None else None
            status = RunStatus.FAILED
            failure_kind = FailureKind.INTERNAL_ERROR
            try:
                emit(
                    event_type="error",
                    content=f"{type(exc).__name__}: {exc}",
                )
            except Exception:
                pass
            if proc and proc.poll() is None:
                killed = force_kill_tree(
                    proc.pid,
                    process_job.name if process_job else "",
                )
                forced = True
                if not killed:
                    status = RunStatus.STOP_FAILED
                    failure_kind = FailureKind.STOP_FAILED

        process_job_name = process_job.name if process_job else ""
        if process_job:
            process_job.close()

        duration_ms = int((time.monotonic() - started) * 1000)
        final_text = "\n".join(text_parts).strip() or None
        try:
            emit(
                event_type="lifecycle",
                content=status.value,
            )
        except Exception:
            pass
        state = store.update(
            status=status.value,
            finished_at=now_iso(),
            exit_code=exit_code,
            duration_ms=duration_ms,
            timed_out=timed_out,
            forced=forced,
            failure_kind=failure_kind.value,
            session_id=captured_session or "",
            final_text=final_text or "",
            reader_error=reader_error_text,
            child_pid=0 if status != RunStatus.STOP_FAILED else (proc.pid if proc else 0),
            process_job="" if status != RunStatus.STOP_FAILED else process_job_name,
        )
        return RunResult.from_state(state, store.run_dir)
