"""Cross-platform child-process lifecycle helpers.

**终止的授权模型（安全红线）**：只终止能证明"是我创建的"进程。证明由三件事组成——
Job Object 所有权、进程身份三元组（pid + 创建时间 + 映像路径）、祖先保护。
任何一环无法确证一律 **fail closed**（拒绝终止并返回 False），绝不退化为凭 PID 猜测。

背景：裸 `taskkill /T /F /PID` 会杀掉以该 PID 为根的整棵树。PID 会被系统复用，
磁盘上的陈旧记录可能指向任意无关进程——包括调用方所在的宿主 CLI 会话。
见 test/tools/cli/reports/20260813-host-kill-safety.md。
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import ctypes
from ctypes import wintypes
from pathlib import Path
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


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259
ERROR_ACCESS_DENIED = 5


def pid_alive(pid: int) -> bool:
    """进程是否存活。

    注意：存活 ≠ 是我们要找的那个进程（PID 会被复用）。判断能否终止必须用
    :func:`identity_matches`，本函数只回答"这个号还被占着吗"。

    访问被拒时返回 False：那意味着该进程不归我们管（更高权限或他用户），
    按 fail-closed 原则不纳入可终止集合。
    """
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
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# 进程身份：防 PID 复用
# ---------------------------------------------------------------------------


def process_identity(pid: int) -> dict[str, Any] | None:
    """返回 ``{"pid", "created_at", "image"}``；进程不存在或无法确证时返回 None。

    ``created_at`` 是进程创建时刻——PID 可以复用，但"同一个 PID 且同一创建时刻"
    实际上唯一。落盘保存后，终止前重新采样比对即可识破 PID 复用。
    """
    if pid <= 0:
        return None
    if sys.platform == "win32":
        return _windows_identity(pid)
    return _posix_identity(pid)


def _windows_identity(pid: int) -> dict[str, Any] | None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    )
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        creation, exit_time, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
        if not kernel32.GetProcessTimes(
            handle, ctypes.byref(creation), ctypes.byref(exit_time),
            ctypes.byref(kernel_time), ctypes.byref(user_time),
        ):
            return None
        created_at = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        image = ""
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            image = buffer.value
        return {"pid": pid, "created_at": created_at, "image": image}
    finally:
        kernel32.CloseHandle(handle)


def _posix_identity(pid: int) -> dict[str, Any] | None:
    try:
        stat = _read_proc_stat(pid)
        if stat is None:
            return None
        try:
            image = os.readlink(f"/proc/{pid}/exe")
        except OSError:
            image = ""
        return {"pid": pid, "created_at": stat["starttime"], "image": image}
    except OSError:
        return None


def _read_proc_stat(pid: int) -> dict[str, Any] | None:
    """解析 /proc/<pid>/stat 的 ppid 与 starttime（进程名含空格，需从右括号后切）。"""
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8", errors="ignore") as handle:
            content = handle.read()
    except OSError:
        return None
    close = content.rfind(")")
    if close < 0:
        return None
    fields = content[close + 2:].split()
    if len(fields) < 20:
        return None
    return {"ppid": int(fields[1]), "starttime": int(fields[19])}


def identity_matches(pid: int, expected: dict[str, Any] | None) -> bool:
    """当前占用该 PID 的进程是否就是当初记录的那一个。

    ``expected`` 缺失（旧记录、跨版本）时返回 False——**无证明即拒绝**。
    """
    if not expected:
        return False
    actual = process_identity(pid)
    if actual is None:
        return False
    if int(expected.get("pid", -1)) != actual["pid"]:
        return False
    if int(expected.get("created_at", -1)) != actual["created_at"]:
        return False
    expected_image = str(expected.get("image") or "")
    if expected_image and expected_image != actual["image"]:
        return False
    return True


# ---------------------------------------------------------------------------
# 祖先保护：绝不终止调用方自身或其任何祖先（含宿主 CLI 会话）
# ---------------------------------------------------------------------------


class AncestryUnavailable(Exception):
    """祖先链无法枚举。调用方必须按 fail-closed 处理，**不得**当作"没有祖先"。"""


def ancestor_pids(pid: int | None = None) -> set[int]:
    """给定进程的完整祖先链（含自身）。

    枚举失败时抛 :class:`AncestryUnavailable`，**绝不返回 ``{自己}``**——
    那是最不安全的集合，不是"最小安全集合"。曾经的实现在 Windows 快照失败时
    静默落进 POSIX 分支（``/proc`` 在 Windows 上必然读不到）→ ``parent=0`` → 立刻 break，
    祖先保护就此塌缩成"只保护自己"，与本模块 fail-closed 的契约自相矛盾。
    """
    start = os.getpid() if pid is None else pid
    chain = {start}
    if sys.platform == "win32":
        parents = _windows_parent_map()
        if parents is None:
            raise AncestryUnavailable("进程快照不可用，无法证明目标不是祖先")
    else:
        parents = None
        if _read_proc_stat(start) is None:
            raise AncestryUnavailable(f"读不到 /proc/{start}/stat，无法枚举祖先链")
    current = start
    for _ in range(64):  # 防御环形/异常父链
        if parents is not None:
            parent = parents.get(current, 0)
        else:
            stat = _read_proc_stat(current)
            parent = stat["ppid"] if stat else 0
        if not parent or parent in chain:
            break
        chain.add(parent)
        current = parent
    return chain


def _windows_parent_map() -> dict[int, int] | None:
    """用进程快照建 pid → ppid 表；失败返回 None（调用方按 fail-closed 处理）。"""
    TH32CS_SNAPPROCESS = 0x00000002
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_char * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32First.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32))
    kernel32.Process32First.restype = wintypes.BOOL
    kernel32.Process32Next.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32))
    kernel32.Process32Next.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL

    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == INVALID_HANDLE_VALUE:
        return None
    try:
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        parents: dict[int, int] = {}
        if not kernel32.Process32First(snapshot, ctypes.byref(entry)):
            return None
        while True:
            parents[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
            if not kernel32.Process32Next(snapshot, ctypes.byref(entry)):
                break
        return parents
    finally:
        kernel32.CloseHandle(snapshot)


def descendant_pids(pid: int | None = None) -> set[int]:
    """枚举某进程的全部后代（不含自身）。

    只读的数据视图原语，供泄漏检测使用——**不是**终止目标的来源：
    "是我的后代"不等于"我持有它的所有权凭证"，终止仍必须走
    :func:`force_kill_tree` 的 identity + Job 三重证明。
    枚举不出来时返回空集：泄漏检测宁可漏报，也不要制造假失败。
    """
    root = os.getpid() if pid is None else pid
    if sys.platform == "win32":
        parents = _windows_parent_map()
        if parents is None:
            return set()
    else:
        parents = {}
        proc_dir = Path("/proc")
        if not proc_dir.is_dir():
            return set()
        for entry in proc_dir.iterdir():
            if not entry.name.isdigit():
                continue
            stat = _read_proc_stat(int(entry.name))
            if stat:
                parents[int(entry.name)] = stat["ppid"]

    children: dict[int, list[int]] = {}
    for child, parent in parents.items():
        children.setdefault(parent, []).append(child)

    found: set[int] = set()
    frontier = list(children.get(root, []))
    while frontier:  # 广度优先；parents 表本身无环，found 兜底防御异常数据
        current = frontier.pop()
        if current in found or current == root:
            continue
        found.add(current)
        frontier.extend(children.get(current, []))
    return found


def group_covers_caller(group: int) -> bool:
    """进程组是否覆盖调用方自身或其祖先。

    终止面是**进程组/控制台**而非单个 PID 时，逐 PID 的祖先检查够不着——
    这正是宿主误杀事故的形状。枚举失败时返回 ``True``（fail-closed）。
    """
    if group <= 0:
        return True
    try:
        chain = ancestor_pids()
    except AncestryUnavailable:
        return True
    if group in chain:
        return True
    # 调用方自己所在的组也不能碰：信号会回到自己身上。
    try:
        return group == os.getpgid(0)
    except (AttributeError, OSError):
        return False


def is_protected_target(pid: int) -> bool:
    """目标是否属于"绝不可终止"集合：调用方自身或其任意祖先（含宿主 CLI）。

    祖先链枚举不出来时返回 ``True``——证明不了"它不是我的祖先"，就当它是。
    宁可留下孤儿进程，也不能再杀一次宿主会话。
    """
    try:
        return pid in ancestor_pids()
    except AncestryUnavailable:
        return True


_BOOT_ID: str | None = None


BOOT_ID_TOLERANCE_SEC = 120


def same_boot(recorded: str, current: str | None = None) -> bool:
    """两个 boot_id 是否指向同一次系统启动。

    不同进程各自计算开机时刻会有秒级偏差，直接字符串比较会把合法记录误判为 stale。
    数值可比时用容差，否则退回严格相等（退化标识本就要求严格一致）。
    """
    now = boot_id() if current is None else current
    if not recorded:
        return False
    try:
        return abs(int(recorded) - int(now)) <= BOOT_ID_TOLERANCE_SEC
    except ValueError:
        return recorded == now


def boot_id() -> str:
    """本次系统启动的标识。

    跨重启后 PID 全部失效，旧记录里的 PID 必然属于别人。落盘该值即可让
    ``stop()`` 一眼识破陈旧记录，避免对无关进程发信号。
    比较请用 :func:`same_boot`，不要直接字符串相等。
    """
    global _BOOT_ID
    if _BOOT_ID is not None:
        return _BOOT_ID
    value = ""
    if sys.platform == "win32":
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetTickCount64.restype = ctypes.c_ulonglong
            uptime_ms = int(kernel32.GetTickCount64())
            # 开机时刻 = 当前时刻 - 运行时长；按秒取整以吸收采样抖动
            # 按 60 秒量化：两个进程各自采样会有秒级偏差，量化 + 下面的容差比较
            # 一起吸收掉，避免把合法记录误判为 stale（拒绝过度会留下孤儿进程）。
            boot_epoch = int(time.time()) - uptime_ms // 1000
            value = str((boot_epoch // 60) * 60)
        except Exception:  # noqa: BLE001 - 拿不到就退化为进程级标识
            value = ""
    else:
        try:
            with open("/proc/stat", encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("btime "):
                        value = line.split()[1]
                        break
        except OSError:
            value = ""
    if not value:
        # 无法确定开机时刻：退化为"本进程唯一"，效果是所有跨进程记录都判 stale（fail closed）
        value = f"pid-{os.getpid()}"
    _BOOT_ID = value
    return value


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
    def create(
        cls,
        run_id: str,
        proc: subprocess.Popen[Any],
        *,
        kill_on_close: bool = True,
    ) -> "WindowsProcessJob":
        """把 ``proc`` 装进一个以 ``run_id`` 命名的 Job，返回持有句柄的所有权凭证。

        ``kill_on_close``：句柄关闭时是否连坐终止成员。
        前台 run 用 ``True``——调用方退出就不该留下子进程。
        detached worker 必须用 ``False``——``start()`` 承诺 worker 活过调用方，
        连坐会把这个语义打碎；此时 Job 仅作为**可按名终止的所有权凭证**存在，
        句柄由创建方持有，进程随之可被 :func:`force_kill_tree` 精确回收。
        """
        if sys.platform != "win32":
            raise OSError("Windows Job Objects are only available on Windows")
        name = f"Local\\AIDefectHelperCli-{run_id}"
        kernel32 = cls._kernel32()
        handle = kernel32.CreateJobObjectW(None, name)
        if not handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
        job = cls(name, handle)
        info = cls._ExtendedLimitInformation()
        info.BasicLimitInformation.LimitFlags = cls.KILL_ON_CLOSE if kill_on_close else 0
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


class KillRefused(Exception):
    """终止请求因缺少所有权证明被拒绝。"""


def force_kill_tree(
    pid: int,
    job_name: str = "",
    *,
    identity: dict[str, Any] | None = None,
    reason: list[str] | None = None,
) -> bool:
    """终止一棵进程树；**无所有权证明即拒绝**。

    通过条件（缺一不可）：
      1. 目标不是调用方自身或其任意祖先（杜绝杀宿主）；
      2. ``identity`` 存在且与目标当前身份一致（杜绝 PID 复用误伤）；
      3. Windows 上必须持有该 run 的 Job Object——**不再退化为 taskkill /T**。

    第 2 条要求 identity **必须提供**：缺省即拒绝。只凭"这个 PID 还活着"就动手，
    正是宿主被误杀的成因（见 test/tools/cli/reports/20260813-host-kill-safety.md）。
    持有 Popen 句柄的调用方应改用 :func:`stop_popen`，不必走本函数。

    拒绝时返回 False（调用方应置 ``stop_failed``），并把原因追加进 ``reason``。
    """
    notes = reason if reason is not None else []

    if pid <= 0:
        notes.append("invalid pid")
        return False
    if is_protected_target(pid):
        notes.append(f"refused: pid {pid} is the caller or one of its ancestors")
        return False
    if not pid_alive(pid):
        return True
    if not identity:
        notes.append(
            f"refused: no recorded identity for pid {pid}; "
            "cannot prove ownership (pid alone is not proof)"
        )
        return False
    if not identity_matches(pid, identity):
        notes.append(f"refused: pid {pid} identity mismatch (likely reused)")
        return False

    if sys.platform == "win32":
        if not job_name:
            notes.append(f"refused: no job object for pid {pid}; bare taskkill is not allowed")
            return False
        if not WindowsProcessJob.terminate_named(job_name):
            notes.append(f"refused: job object {job_name!r} unavailable")
            return False
        return _wait_dead(pid)

    try:
        group = os.getpgid(pid)
    except (OSError, ProcessLookupError):
        return True
    if group_covers_caller(group):
        notes.append(f"refused: process group {group} covers the caller")
        return False
    try:
        os.killpg(group, signal.SIGKILL)
    except ProcessLookupError:
        return True
    return _wait_dead(pid)


def stop_popen(
    proc: subprocess.Popen[Any],
    grace_sec: float,
    *,
    force: bool = False,
    job: WindowsProcessJob | None = None,
) -> tuple[bool, bool]:
    """Stop and reap a Popen-owned process tree, returning ``(forced, stopped)``.

    这里持有 Popen 句柄——**内核级所有权证明**，不受 PID 复用影响，
    因此可以直接终止直接子进程；后代由 Job Object（Windows）或进程组（POSIX）覆盖。
    """
    if proc.poll() is not None:
        proc.wait()
        return False, True
    forced = force
    if not force:
        # 优雅停止走的是**进程组/控制台**语义，不是单个 PID：
        #   Windows 的 CTRL_BREAK_EVENT 底层是 GenerateConsoleCtrlEvent，按进程组投递，
        #   且会送达与调用方共享同一控制台的全部组成员；POSIX 的 killpg 同理。
        # 因此逐 PID 的祖先检查在这里够不着，必须先证明"这个组不覆盖我自己"。
        # 子进程由 popen_group_options() 建独立组时才成立；一旦创建标志被覆盖，
        # 组就退化成调用方所在的组——信号会打到宿主控制台上。
        try:
            group = proc.pid if sys.platform == "win32" else os.getpgid(proc.pid)
        except (AttributeError, OSError, ProcessLookupError):
            group = 0
        if group and not group_covers_caller(group):
            try:
                if sys.platform == "win32":
                    proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    os.killpg(group, signal.SIGINT)
            except (AttributeError, OSError, ProcessLookupError):
                pass
        deadline = time.monotonic() + max(0.0, grace_sec)
        while proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        forced = proc.poll() is None

    def _terminate_owned() -> None:
        """先杀后代（Job/进程组），再用句柄杀直接子进程。"""
        if job:
            job.terminate()
        elif sys.platform != "win32":
            try:
                group = os.getpgid(proc.pid)
            except (OSError, ProcessLookupError):
                group = 0
            # SIGKILL 打到覆盖调用方的组＝自杀 + 杀宿主。宁可只杀直接子进程留下孤儿。
            if group and not group_covers_caller(group):
                try:
                    os.killpg(group, signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    pass
        try:
            proc.kill()
        except OSError:
            pass

    if proc.poll() is None:
        _terminate_owned()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _terminate_owned()
        forced = True
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            return forced, False
    # Popen is the authoritative handle for the direct child. On Windows,
    # os.kill(pid, 0) can report a stale/reused PID after wait() has reaped it;
    # descendants are covered by the Job Object.
    return forced, proc.poll() is not None
