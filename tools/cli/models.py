"""Public data contracts for the unified CLI runtime."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class RunStatus(str, Enum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    OVERTIME = "overtime"
    STOPPING = "stopping"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    STOPPED = "stopped"
    STOP_FAILED = "stop_failed"


TERMINAL_STATUSES = {
    RunStatus.SUCCEEDED.value,
    RunStatus.FAILED.value,
    RunStatus.TIMED_OUT.value,
    RunStatus.STOPPED.value,
    RunStatus.STOP_FAILED.value,
}


class FailureKind(str, Enum):
    NONE = "none"
    CLI_UNAVAILABLE = "cli_unavailable"
    CONFIGURATION_ERROR = "configuration_error"
    AUTH_REQUIRED = "auth_required"
    SUBSCRIPTION_UNAVAILABLE = "subscription_unavailable"
    MODEL_UNAVAILABLE = "model_unavailable"
    COMMAND_FAILED = "command_failed"
    TIMED_OUT = "timed_out"
    STOPPED = "stopped"
    STOP_FAILED = "stop_failed"
    EVENT_STREAM_FAILED = "event_stream_failed"
    PROVIDER_STALLED = "provider_stalled"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class CliRunRequest:
    cli: str
    model: str
    prompt: str
    cwd: Path
    profile: str | None = None
    session_id: str | None = None
    output_schema: Path | None = None
    soft_timeout_sec: float | None = None
    hard_timeout_sec: float | None = None
    stop_grace_sec: float | None = None
    env: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["cwd"] = str(self.cwd)
        value["output_schema"] = str(self.output_schema) if self.output_schema else None
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CliRunRequest":
        return cls(
            cli=str(value["cli"]),
            model=str(value["model"]),
            prompt=str(value["prompt"]),
            cwd=Path(value["cwd"]),
            profile=value.get("profile"),
            session_id=value.get("session_id"),
            output_schema=Path(value["output_schema"]) if value.get("output_schema") else None,
            soft_timeout_sec=value.get("soft_timeout_sec"),
            hard_timeout_sec=value.get("hard_timeout_sec"),
            stop_grace_sec=value.get("stop_grace_sec"),
            env={str(k): str(v) for k, v in (value.get("env") or {}).items()},
            metadata=dict(value.get("metadata") or {}),
        )


@dataclass(frozen=True)
class CliEvent:
    seq: int
    timestamp: str
    run_id: str
    type: str
    content: str | None = None
    session_id: str | None = None
    message_id: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    tool_status: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_output: str | None = None
    usage: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CliEvent":
        allowed = {item.name for item in fields(cls)}
        return cls(**{key: item for key, item in value.items() if key in allowed})


EventCallback = Callable[[CliEvent], None]


@dataclass(frozen=True)
class RunHandle:
    run_id: str
    status: str


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: str
    exit_code: int | None
    failure_kind: str
    session_id: str | None
    duration_ms: int
    final_text: str | None
    timed_out: bool
    forced: bool
    run_dir: Path

    @classmethod
    def from_state(cls, state: dict[str, Any], run_dir: Path) -> "RunResult":
        return cls(
            run_id=str(state.get("run_id", "")),
            status=str(state.get("status", RunStatus.FAILED.value)),
            exit_code=state.get("exit_code"),
            failure_kind=str(state.get("failure_kind", FailureKind.NONE.value)),
            session_id=state.get("session_id") or None,
            duration_ms=int(state.get("duration_ms", 0) or 0),
            final_text=state.get("final_text") or None,
            timed_out=bool(state.get("timed_out", False)),
            forced=bool(state.get("forced", False)),
            run_dir=run_dir,
        )


@dataclass(frozen=True)
class EventPage:
    run_id: str
    cursor: int
    next_cursor: int
    has_more: bool
    events: list[CliEvent]
    run: dict[str, Any]
