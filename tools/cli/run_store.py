"""Durable, replayable storage for CLI runs."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import CliEvent, CliRunRequest, EventPage, RunStatus


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def atomic_json(
    path: Path,
    value: Any,
    *,
    attempts: int = 100,
    retry_delay_sec: float = 0.01,
) -> None:
    """Atomically publish JSON, tolerating transient Windows sharing violations."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(
        f"{path.name}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"
    )
    last_error: OSError | None = None
    try:
        temp.write_text(
            json.dumps(value, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        for attempt in range(max(1, attempts)):
            try:
                os.replace(temp, path)
                return
            except OSError as exc:
                last_error = exc
                if attempt + 1 < max(1, attempts):
                    time.sleep(max(0.0, retry_delay_sec))
        assert last_error is not None
        raise last_error
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def read_text_retry(path: Path, *, attempts: int = 50) -> str:
    """Tolerate the short Windows replace/AV sharing window around state files."""
    last_error: OSError | None = None
    for _ in range(attempts):
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            last_error = exc
            time.sleep(0.01)
    assert last_error is not None
    raise last_error


class RunStore:
    def __init__(self, runtime_root: str | Path, run_id: str) -> None:
        self.runtime_root = Path(runtime_root).resolve()
        self.run_id = run_id
        self.run_dir = self.runtime_root / run_id
        self.state_path = self.run_dir / "run.json"
        self.request_path = self.run_dir / "request.json"
        self.events_path = self.run_dir / "events.jsonl"
        self.raw_path = self.run_dir / "raw.jsonl"
        self.stop_path = self.run_dir / "stop.json"
        self.worker_log_path = self.run_dir / "worker.log"
        self._lock = threading.Lock()
        self._seq = 0

    def create(self, request: CliRunRequest, parent_run_id: str | None = None) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.events_path.write_text("", encoding="utf-8")
        self.raw_path.write_text("", encoding="utf-8")
        atomic_json(self.request_path, request.to_dict())
        atomic_json(
            self.state_path,
            {
                "schema_version": 1,
                "run_id": self.run_id,
                "parent_run_id": parent_run_id,
                "status": RunStatus.CREATED.value,
                "cli": request.cli,
                "profile": request.profile,
                "model": request.model,
                "session_id": request.session_id or "",
                "runner_pid": 0,
                "child_pid": 0,
                "process_job": "",
                "created_at": now_iso(),
                "started_at": "",
                "last_activity_at": "",
                "last_event_seq": 0,
                "finished_at": "",
                "exit_code": None,
                "duration_ms": 0,
                "timed_out": False,
                "forced": False,
                "failure_kind": "none",
                "final_text": "",
                "metadata": request.metadata,
            },
        )

    def request(self) -> CliRunRequest:
        value = json.loads(read_text_retry(self.request_path))
        return CliRunRequest.from_dict(value)

    def state(self) -> dict[str, Any]:
        if not self.state_path.is_file():
            raise FileNotFoundError(f"Unknown run_id: {self.run_id}")
        return json.loads(read_text_retry(self.state_path))

    def update(self, **values: Any) -> dict[str, Any]:
        with self._lock:
            state = self.state()
            state.update(values)
            atomic_json(self.state_path, state)
            return state

    def append_raw(self, line: str) -> None:
        row = {"ts": now_iso(), "line": line}
        with self._lock:
            with self.raw_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    def append_event(
        self,
        event_type: str,
        *,
        content: str | None = None,
        session_id: str | None = None,
        message_id: str | None = None,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
        tool_status: str | None = None,
        tool_input: dict[str, Any] | None = None,
        tool_output: str | None = None,
        usage: dict[str, Any] | None = None,
    ) -> CliEvent:
        with self._lock:
            if self._seq == 0 and self.events_path.is_file():
                self._seq = self._last_seq()
            self._seq += 1
            event = CliEvent(
                seq=self._seq,
                timestamp=now_iso(),
                run_id=self.run_id,
                type=event_type,
                content=content,
                session_id=session_id,
                message_id=message_id,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                tool_status=tool_status,
                tool_input=tool_input,
                tool_output=tool_output,
                usage=usage,
            )
            with self.events_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n"
                )
            state = self.state()
            state.update(
                last_activity_at=event.timestamp,
                last_event_seq=event.seq,
            )
            atomic_json(self.state_path, state)
            return event

    def _last_seq(self) -> int:
        result = 0
        for line in read_text_retry(self.events_path).splitlines():
            try:
                result = max(result, int(json.loads(line).get("seq", 0) or 0))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        return result

    def page(self, cursor: int, max_events: int, max_chars: int) -> EventPage:
        events: list[CliEvent] = []
        size = 0
        has_more = False
        next_cursor = cursor
        if self.events_path.is_file():
            for line in read_text_retry(self.events_path).splitlines():
                try:
                    value = json.loads(line)
                    seq = int(value.get("seq", 0) or 0)
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
                if seq <= cursor:
                    continue
                event_size = len(str(value.get("content") or ""))
                if events and (len(events) >= max_events or size + event_size > max_chars):
                    has_more = True
                    break
                events.append(CliEvent.from_dict(value))
                size += event_size
                next_cursor = seq
        run = self.state()
        # The event file and run state are separate durable files. An event
        # can be appended after this page's file snapshot but before terminal
        # state is read. last_event_seq prevents callers from treating that
        # mixed snapshot as a fully drained terminal page.
        if int(run.get("last_event_seq", 0) or 0) > next_cursor:
            has_more = True
        return EventPage(
            run_id=self.run_id,
            cursor=cursor,
            next_cursor=next_cursor,
            has_more=has_more,
            events=events,
            run=run,
        )

    def request_stop(self, force: bool) -> None:
        atomic_json(self.stop_path, {"requested_at": now_iso(), "force": force})

    def stop_request(self) -> dict[str, Any] | None:
        if not self.stop_path.is_file():
            return None
        try:
            return json.loads(read_text_retry(self.stop_path))
        except (OSError, json.JSONDecodeError):
            return {"force": False}
