"""Cross-platform child-process lifecycle helpers."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import ctypes
from ctypes import wintypes
from typing import Any


def popen_group_options() -> dict[str, object]:
    if sys.platform == "win32":
        # Unified CLI runs are non-interactive automation. Keep a distinct
        # process group for lifecycle control without creating a visible
        # console window for .cmd/.exe providers.
        return {
            "creationflags": (
                subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.CREATE_NO_WINDOW
            )
        }
    return {"start_new_session": True}


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # access denied means it still exists
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def request_interrupt(pid: int) -> bool:
    if not pid_alive(pid):
        return True
    try:
        if sys.platform == "win32":
            os.kill(pid, signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(os.getpgid(pid), signal.SIGINT)
        return True
    except (AttributeError, OSError, ProcessLookupError):
        return False


class WindowsProcessJob:
    """Own a Windows process tree and kill descendants if the worker exits."""

    KILL_ON_CLOSE = 0x00002000
    EXTENDED_LIMIT_INFORMATION = 9
    TERMINATE_ACCESS = 0x0008

    class _BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class _ExtendedLimitInformation(ctypes.Structure):
        pass

    _ExtendedLimitInformation._fields_ = [
        ("BasicLimitInformation", _BasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]

    def __init__(self, name: str, handle: int) -> None:
        self.name = name
        self.handle = handle

    @staticmethod
    def _kernel32():
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.OpenJobObjectW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
        kernel32.OpenJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = (
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        )
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
        kernel32.TerminateJobObject.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        return kernel32

    @classmethod
    def create(cls, run_id: str, proc: subprocess.Popen[Any]) -> "WindowsProcessJob":
        if sys.platform != "win32":
            raise OSError("Windows Job Objects are only available on Windows")
        name = f"Local\\AIDefectHelperCli-{run_id}"
        kernel32 = cls._kernel32()
        handle = kernel32.CreateJobObjectW(None, name)
        if not handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
        job = cls(name, handle)
        info = cls._ExtendedLimitInformation()
        info.BasicLimitInformation.LimitFlags = cls.KILL_ON_CLOSE
        if not kernel32.SetInformationJobObject(
            handle,
            cls.EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(info),
            ctypes.sizeof(info),
        ):
            error = ctypes.get_last_error()
            job.close()
            raise OSError(error, "SetInformationJobObject failed")
        process_handle = wintypes.HANDLE(int(getattr(proc, "_handle")))
        if not kernel32.AssignProcessToJobObject(handle, process_handle):
            error = ctypes.get_last_error()
            job.close()
            raise OSError(error, "AssignProcessToJobObject failed")
        return job

    @classmethod
    def terminate_named(cls, name: str) -> bool:
        if sys.platform != "win32" or not name:
            return False
        kernel32 = cls._kernel32()
        handle = kernel32.OpenJobObjectW(cls.TERMINATE_ACCESS, False, name)
        if not handle:
            return False
        try:
            return bool(kernel32.TerminateJobObject(handle, 1))
        finally:
            kernel32.CloseHandle(handle)

    def terminate(self) -> bool:
        return bool(self._kernel32().TerminateJobObject(self.handle, 1))

    def close(self) -> None:
        if self.handle:
            self._kernel32().CloseHandle(self.handle)
            self.handle = 0


def _wait_dead(pid: int, timeout_sec: float = 5.0) -> bool:
    deadline = time.monotonic() + max(0.0, timeout_sec)
    while pid_alive(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    return not pid_alive(pid)


def force_kill_tree(pid: int, job_name: str = "") -> bool:
    if not pid_alive(pid):
        return True
    if sys.platform == "win32":
        if job_name and WindowsProcessJob.terminate_named(job_name):
            return True
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(pid)],
            capture_output=True,
            timeout=30,
            check=False,
        )
        return _wait_dead(pid)
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except ProcessLookupError:
        return True
    return _wait_dead(pid)


def stop_process(
    pid: int,
    grace_sec: float,
    *,
    force: bool = False,
    job_name: str = "",
) -> tuple[bool, bool]:
    """Stop a process tree and return ``(forced, stopped)``."""
    if not pid_alive(pid):
        return False, True
    if force:
        return True, force_kill_tree(pid, job_name)
    request_interrupt(pid)
    deadline = time.monotonic() + max(0.0, grace_sec)
    while pid_alive(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    if not pid_alive(pid):
        return False, True
    return True, force_kill_tree(pid, job_name)


def stop_popen(
    proc: subprocess.Popen[Any],
    grace_sec: float,
    *,
    force: bool = False,
    job: WindowsProcessJob | None = None,
) -> tuple[bool, bool]:
    """Stop and reap a Popen-owned process tree, returning ``(forced, stopped)``."""
    if proc.poll() is not None:
        proc.wait()
        return False, True
    forced = force
    if not force:
        try:
            if sys.platform == "win32":
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGINT)
        except (AttributeError, OSError, ProcessLookupError):
            pass
        deadline = time.monotonic() + max(0.0, grace_sec)
        while proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        forced = proc.poll() is None
    if proc.poll() is None:
        if job:
            job.terminate()
        force_kill_tree(proc.pid, job.name if job else "")
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if job:
            job.terminate()
        force_kill_tree(proc.pid, job.name if job else "")
        forced = True
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            return forced, False
    # Popen is the authoritative handle for the direct child. On Windows,
    # os.kill(pid, 0) can report a stale/reused PID after wait() has reaped it;
    # descendants are covered by the Job Object.
    return forced, proc.poll() is not None
