"""Public standard interface for business tools."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import (
    CliRunRequest,
    EventCallback,
    EventPage,
    FailureKind,
    RunHandle,
    RunResult,
    RunStatus,
    TERMINAL_STATUSES,
)
from .process_control import force_kill_tree, pid_alive, popen_group_options
from .registry import DEFAULT_CONFIG_PATH, CliRegistry
from .run_store import RunStore, now_iso
from .runner import CliRunner


# 仓库根：tools/cli/api.py → parents[2]。start() 给子进程传的 cwd 用的是同一个值，
# 挪动本文件的层级时两处一起改，否则 worker 起不来且只表现为超时。
REPO_ROOT = Path(__file__).resolve().parents[2]
WORKER_MODULE = "tools.cli.worker"
DEFAULT_RUNTIME_ROOT = REPO_ROOT / "output" / "cli"
PRIVATE_STATE_FIELDS = {
    "runner_pid",
    "child_pid",
    "process_job",
    "command",
    "effective_cwd",
    "profile",
}


class CliClient:
    def __init__(
        self,
        *,
        runtime_root: str | Path,
        registry_path: str | Path = DEFAULT_CONFIG_PATH,
    ) -> None:
        self.registry = CliRegistry(registry_path)
        self.registry_path = self.registry.path
        self.runtime_root = Path(runtime_root).resolve()
        self._workers: dict[str, subprocess.Popen[Any]] = {}

    def run(
        self,
        request: CliRunRequest,
        *,
        on_event: EventCallback | None = None,
        parent_run_id: str | None = None,
    ) -> RunResult:
        run_id = self._new_run_id()
        store = RunStore(self.runtime_root, run_id)
        store.create(request, parent_run_id)
        return CliRunner(self.registry).execute(store, on_event=on_event)

    def resume(
        self,
        request: CliRunRequest,
        *,
        on_event: EventCallback | None = None,
        parent_run_id: str | None = None,
    ) -> RunResult:
        if not request.session_id:
            raise ValueError("resume requires request.session_id")
        return self.run(request, on_event=on_event, parent_run_id=parent_run_id)

    def start(
        self,
        request: CliRunRequest,
        *,
        parent_run_id: str | None = None,
    ) -> RunHandle:
        run_id = self._new_run_id()
        store = RunStore(self.runtime_root, run_id)
        store.create(request, parent_run_id)
        command = [
            sys.executable,
            "-m",
            WORKER_MODULE,
            "--registry",
            str(self.registry_path),
            "--runtime-root",
            str(self.runtime_root),
            "--run-id",
            run_id,
        ]
        handle = store.worker_log_path.open("w", encoding="utf-8")
        kwargs: dict[str, Any] = {
            "cwd": str(REPO_ROOT),
            "stdin": subprocess.DEVNULL,
            "stdout": handle,
            "stderr": subprocess.STDOUT,
            "close_fds": True,
            **popen_group_options(),
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = int(kwargs.get("creationflags", 0)) | int(
                subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
            )
        try:
            proc = subprocess.Popen(command, **kwargs)
        except Exception as exc:
            store.update(
                status=RunStatus.FAILED.value,
                finished_at=now_iso(),
                failure_kind=FailureKind.INTERNAL_ERROR.value,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        finally:
            handle.close()
        self._workers[run_id] = proc
        return RunHandle(run_id=run_id, status=RunStatus.STARTING.value)

    def poll(
        self,
        run_id: str,
        *,
        cursor: int = 0,
        wait_sec: float = 0,
        max_events: int = 100,
        max_chars: int = 12000,
    ) -> EventPage:
        if cursor < 0 or max_events <= 0 or max_chars <= 0:
            raise ValueError("cursor must be >= 0; max_events and max_chars must be > 0")
        store = self._store(run_id)
        deadline = time.monotonic() + max(0.0, min(float(wait_sec), 60.0))
        while True:
            page = store.page(cursor, max_events, max_chars)
            if page.events or page.run.get("status") in TERMINAL_STATUSES:
                if page.run.get("status") in TERMINAL_STATUSES:
                    self._reap_worker(run_id)
                return EventPage(
                    run_id=page.run_id,
                    cursor=page.cursor,
                    next_cursor=page.next_cursor,
                    has_more=page.has_more,
                    events=page.events,
                    run=self._public_state(page.run),
                )
            if time.monotonic() >= deadline:
                return EventPage(
                    run_id=page.run_id,
                    cursor=page.cursor,
                    next_cursor=page.next_cursor,
                    has_more=page.has_more,
                    events=page.events,
                    run=self._public_state(page.run),
                )
            time.sleep(0.05)

    def status(self, run_id: str) -> dict[str, Any]:
        state = self._store(run_id).state()
        if state.get("status") in TERMINAL_STATUSES:
            self._reap_worker(run_id)
        return self._public_state(state)

    def stop(self, run_id: str, *, force: bool = False) -> RunResult:
        store = self._store(run_id)
        state = store.state()
        if state.get("status") in TERMINAL_STATUSES:
            self._reap_worker(run_id)
            return RunResult.from_state(state, store.run_dir)
        store.request_stop(force)
        grace = float(state.get("stop_grace_sec", 0) or 0)
        deadline = time.monotonic() + max(5.0, grace + 5.0)
        while time.monotonic() < deadline:
            state = store.state()
            if state.get("status") in TERMINAL_STATUSES:
                self._reap_worker(run_id)
                return RunResult.from_state(state, store.run_dir)
            time.sleep(0.05)

        # Recovery path for a crashed or unresponsive worker.
        child_pid = int(state.get("child_pid", 0) or 0)
        runner_pid = int(state.get("runner_pid", 0) or 0)
        process_job = str(state.get("process_job", "") or "")
        forced = force
        for pid, job_name in ((child_pid, process_job), (runner_pid, "")):
            if pid and pid != os.getpid() and pid_alive(pid):
                force_kill_tree(pid, job_name)
                forced = True
        child_alive = bool(child_pid and pid_alive(child_pid))
        runner_alive = bool(runner_pid and runner_pid != os.getpid() and pid_alive(runner_pid))
        stopped = not child_alive and not runner_alive
        state = store.update(
            status=(RunStatus.STOPPED if stopped else RunStatus.STOP_FAILED).value,
            finished_at=now_iso(),
            forced=forced,
            failure_kind=(
                FailureKind.STOPPED if stopped else FailureKind.STOP_FAILED
            ).value,
            child_pid=0 if stopped else child_pid,
            runner_pid=0 if stopped else runner_pid,
            process_job="" if stopped else process_job,
        )
        self._reap_worker(run_id)
        return RunResult.from_state(state, store.run_dir)

    def describe(self, request: CliRunRequest) -> dict[str, Any]:
        resolved = self.registry.build(request, check_executable=False)
        value = asdict(resolved)
        value["cwd"] = str(resolved.cwd) if resolved.cwd else None
        return value

    def _store(self, run_id: str) -> RunStore:
        if not run_id or Path(run_id).name != run_id:
            raise ValueError("Invalid run_id")
        return RunStore(self.runtime_root, run_id)

    def _new_run_id(self) -> str:
        while True:
            run_id = uuid.uuid4().hex[:16]
            if not (self.runtime_root / run_id).exists():
                return run_id

    @staticmethod
    def _public_state(state: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in state.items()
            if key not in PRIVATE_STATE_FIELDS
        }

    def _reap_worker(self, run_id: str) -> None:
        proc = self._workers.get(run_id)
        if proc is None:
            return
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            return
        self._workers.pop(run_id, None)
