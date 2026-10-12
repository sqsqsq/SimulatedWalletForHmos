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
from .process_control import (
    WindowsProcessJob,
    boot_id,
    same_boot,
    force_kill_tree,
    pid_alive,
    popen_group_options,
    process_identity,
)
from .registry import DEFAULT_CONFIG_PATH, CliRegistry
from .run_store import RunStore, now_iso
from .runner import CliRunner


DEFAULT_RUNTIME_ROOT = Path(__file__).resolve().parents[2] / "output" / "cli"
PRIVATE_STATE_FIELDS = {
    "runner_pid",
    "child_pid",
    "worker_pid",
    "process_job",
    "worker_job",
    "child_identity",
    "worker_identity",
    "boot_id",
    "command",
    "effective_cwd",
    "profile",
}


def _is_stale_record(state: dict[str, Any]) -> bool:
    """记录是否来自上一次系统启动——那样的 PID 一定已被复用给别人。

    缺 ``boot_id`` 的旧记录同样判 stale：无从证明其新鲜度，按 fail-closed 处理。
    """
    recorded = str(state.get("boot_id") or "")
    return not same_boot(recorded)


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
        # detached worker 的 Job Object 所有权凭证（Windows）。不设 KILL_ON_CLOSE：
        # start() 承诺 worker 活过调用方，连坐会打碎这个语义。句柄在此保活，
        # 使 worker_job 成为可按名终止的真实凭证，而不是只读不写的幽灵字段。
        self._worker_jobs: dict[str, WindowsProcessJob] = {}

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
            "tools.cli.worker",
            "--registry",
            str(self.registry_path),
            "--runtime-root",
            str(self.runtime_root),
            "--run-id",
            run_id,
        ]
        handle = store.worker_log_path.open("w", encoding="utf-8")
        kwargs: dict[str, Any] = {
            "cwd": str(Path(__file__).resolve().parents[2]),
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
        # detached worker 的 Job Object：force_kill_tree 在 Windows 上要求持有 job，
        # 否则任何回收请求都会被 fail-closed 拒绝，worker 只能留成孤儿。
        worker_job = ""
        if sys.platform == "win32":
            try:
                job = WindowsProcessJob.create(f"worker-{run_id}", proc, kill_on_close=False)
            except OSError:
                job = None  # 拿不到 job 就如实留空，让 stop() 按 fail-closed 拒绝
            if job is not None:
                self._worker_jobs[run_id] = job
                worker_job = job.name
        # 落盘 worker 的身份证明：后续 stop() 必须凭它核对，PID 复用即拒绝终止。
        store.update(
            worker_pid=proc.pid,
            worker_identity=process_identity(proc.pid) or {},
            worker_job=worker_job,
            boot_id=boot_id(),
        )
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

        # 跨重启的记录里 PID 已无意义：同号进程必然是别人。判 stale 直接短路，
        # 不做任何终止——这是切断"陈旧 PID → 误杀 → 更多陈旧 PID"循环的关键。
        if _is_stale_record(state):
            state = store.update(
                status=RunStatus.STOP_FAILED.value,
                finished_at=now_iso(),
                failure_kind=FailureKind.STOP_FAILED.value,
                error="stale run record from a previous boot; refused to signal any pid",
                child_pid=0,
                worker_pid=0,
                process_job="",
            )
            self._reap_worker(run_id)
            return RunResult.from_state(state, store.run_dir)

        store.request_stop(force)
        grace = float(state.get("stop_grace_sec", 0) or 0)
        if grace <= 0:
            grace = float(
                ((state.get("request") or {}).get("timeout") or {}).get("stop_grace_sec", 0) or 0
            )
        deadline = time.monotonic() + max(5.0, grace + 5.0)
        while time.monotonic() < deadline:
            state = store.state()
            if state.get("status") in TERMINAL_STATUSES:
                self._reap_worker(run_id)
                return RunResult.from_state(state, store.run_dir)
            time.sleep(0.05)

        # 恢复路径：worker 崩溃或无响应。只终止**能证明归属**的进程。
        # `runner_pid` 不在此列——前台运行时它就是调用方自己，从来不是可终止目标。
        child_pid = int(state.get("child_pid", 0) or 0)
        worker_pid = int(state.get("worker_pid", 0) or 0)
        process_job = str(state.get("process_job", "") or "")
        refusals: list[str] = []
        forced = force
        targets = (
            (child_pid, process_job, state.get("child_identity")),
            (worker_pid, str(state.get("worker_job", "") or ""), state.get("worker_identity")),
        )
        for pid, job_name, identity in targets:
            if not pid or not pid_alive(pid):
                continue
            if force_kill_tree(pid, job_name, identity=identity, reason=refusals):
                forced = True

        child_alive = bool(child_pid and pid_alive(child_pid))
        worker_alive = bool(worker_pid and pid_alive(worker_pid))
        stopped = not child_alive and not worker_alive
        state = store.update(
            status=(RunStatus.STOPPED if stopped else RunStatus.STOP_FAILED).value,
            finished_at=now_iso(),
            forced=forced,
            failure_kind=(
                FailureKind.STOPPED if stopped else FailureKind.STOP_FAILED
            ).value,
            error="; ".join(refusals) if refusals and not stopped else state.get("error", ""),
            child_pid=0 if stopped else child_pid,
            worker_pid=0 if stopped else worker_pid,
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
        """回收已进入终态的 run 的 detached worker。

        run 已终态时 worker 没有任何存在理由；旧实现在 ``wait(timeout=1)`` 超时后直接
        ``return``，既不终止也不移出登记表——每次 start() 都可能留下一个常驻进程。
        一次全量测试跑下来能累积上百个，最终撑破宿主的资源信封（20260813 事故根因）。
        """
        proc = self._workers.get(run_id)
        job = self._worker_jobs.get(run_id)
        if proc is None:
            self._release_worker_job(run_id)
            return
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            # 终态后仍不退出：凭 identity + job 精确回收，证明不了归属就如实留孤儿。
            state = self._store(run_id).state()
            force_kill_tree(
                proc.pid,
                job.name if job else str(state.get("worker_job", "") or ""),
                identity=state.get("worker_identity"),
            )
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                return  # 仍在：保留登记，下次 poll/stop 再试，不静默丢弃
        self._workers.pop(run_id, None)
        self._release_worker_job(run_id)

    def _release_worker_job(self, run_id: str) -> None:
        job = self._worker_jobs.pop(run_id, None)
        if job is not None:
            job.close()

    def close(self) -> None:
        """停止并回收本客户端起过的全部 detached run。

        测试 fixture 与长驻编排器必须在收尾时调用：`shutil.rmtree` 只删工作目录，
        目录没了进程还在。见 test/tools/cli/AGENTS.md 的进程终止授权模型。
        """
        for run_id in list(self._workers):
            try:
                state = self._store(run_id).state()
                if state.get("status") not in TERMINAL_STATUSES:
                    self.stop(run_id, force=True)
                else:
                    self._reap_worker(run_id)
            except Exception:  # noqa: BLE001 - 收尾不得因单个 run 失败而中断
                self._reap_worker(run_id)
        for run_id in list(self._worker_jobs):
            self._release_worker_job(run_id)

    def __enter__(self) -> "CliClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
