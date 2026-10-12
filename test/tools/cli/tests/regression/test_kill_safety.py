"""进程终止安全：绝不误杀宿主 CLI 会话。

事故背景：在终端内 AI CLI 宿主中跑全量 pytest 时，宿主会话被 `taskkill /T /F` 杀掉。
根因是终止逻辑缺少所有权证明——只凭"磁盘上记的 PID 还活着"就杀整棵进程树。
详见 test/tools/cli/reports/20260813-host-kill-safety.md。

**本文件的所有用例都不终止任何真实进程**：终止手段被 monkeypatch 拦截，
断言的是"该不该调用"，而不是"杀没杀成"。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.cli import process_control  # noqa: E402


@pytest.fixture
def kill_spy(monkeypatch):
    """拦截一切实际终止手段，记录是否被触发。"""
    calls: dict[str, list] = {"taskkill": [], "job": [], "killpg": []}

    def fake_run(cmd, *args, **kwargs):
        calls["taskkill"].append(list(cmd))
        raise AssertionError(f"意外执行了外部终止命令：{cmd}")

    def fake_terminate_named(cls, name):
        calls["job"].append(name)
        return True

    monkeypatch.setattr(process_control.subprocess, "run", fake_run)
    monkeypatch.setattr(
        process_control.WindowsProcessJob,
        "terminate_named",
        classmethod(fake_terminate_named),
    )
    if hasattr(os, "killpg"):
        monkeypatch.setattr(
            process_control.os,
            "killpg",
            lambda pgid, sig: calls["killpg"].append((pgid, sig)),
        )
    monkeypatch.setattr(process_control, "_wait_dead", lambda pid, timeout_sec=5.0: True)
    return calls


# ── 祖先保护：这条直接封死"杀宿主"事故 ────────────────────────


def test_refuses_to_kill_self(kill_spy) -> None:
    reasons: list[str] = []
    assert process_control.force_kill_tree(os.getpid(), "job", reason=reasons) is False
    assert any("ancestor" in item for item in reasons)
    assert not kill_spy["taskkill"] and not kill_spy["job"]


def test_refuses_to_kill_parent(kill_spy) -> None:
    parent = os.getppid()
    if parent <= 0:
        pytest.skip("no parent pid available")
    reasons: list[str] = []
    assert process_control.force_kill_tree(parent, "job", reason=reasons) is False
    assert not kill_spy["taskkill"] and not kill_spy["job"]


def test_refuses_any_ancestor_including_host_session(kill_spy, monkeypatch) -> None:
    """宿主 CLI 会话通常是调用方的远祖——祖先链上任何一个都不可终止。"""
    host_pid = 424242
    monkeypatch.setattr(
        process_control, "ancestor_pids", lambda pid=None: {os.getpid(), 999, host_pid}
    )
    reasons: list[str] = []
    assert process_control.force_kill_tree(host_pid, "job", reason=reasons) is False
    assert any("ancestor" in item for item in reasons)
    assert not kill_spy["job"]


# ── 身份校验：防 PID 复用 ──────────────────────────────────────


def test_refuses_when_identity_mismatches(kill_spy, monkeypatch) -> None:
    """PID 相同但创建时刻不同 = 号被复用给了别人，必须拒绝。"""
    target = 4321
    monkeypatch.setattr(process_control, "ancestor_pids", lambda pid=None: {os.getpid()})
    monkeypatch.setattr(process_control, "pid_alive", lambda pid: True)
    monkeypatch.setattr(
        process_control,
        "process_identity",
        lambda pid: {"pid": target, "created_at": 222, "image": "other.exe"},
    )
    reasons: list[str] = []
    recorded = {"pid": target, "created_at": 111, "image": "mine.exe"}
    assert (
        process_control.force_kill_tree(target, "job", identity=recorded, reason=reasons) is False
    )
    assert any("identity mismatch" in item for item in reasons)
    assert not kill_spy["job"]


def test_identity_requires_recorded_proof() -> None:
    """没有留存身份证明的旧记录一律判为不匹配（fail closed）。"""
    assert process_control.identity_matches(os.getpid(), None) is False
    assert process_control.identity_matches(os.getpid(), {}) is False


def test_identity_matches_self() -> None:
    identity = process_control.process_identity(os.getpid())
    assert identity is not None
    assert process_control.identity_matches(os.getpid(), identity) is True


def test_refuses_without_recorded_identity(kill_spy, monkeypatch) -> None:
    """三重证明缺一不可：只凭"这个 PID 还活着"不构成所有权（审查 P2-3）。"""
    target = 4321
    monkeypatch.setattr(process_control, "ancestor_pids", lambda pid=None: {os.getpid()})
    monkeypatch.setattr(process_control, "pid_alive", lambda pid: True)
    reasons: list[str] = []
    assert process_control.force_kill_tree(target, "job", reason=reasons) is False
    assert any("cannot prove ownership" in item for item in reasons), reasons
    assert not kill_spy["job"] and not kill_spy["taskkill"]


# ── fail closed：无 Job Object 不得退化为裸 taskkill ──────────


@pytest.mark.skipif(sys.platform != "win32", reason="Job Object 是 Windows 语义")
def test_refuses_without_job_object(kill_spy, monkeypatch) -> None:
    """事故的直接触发点：过去无 job_name 就退化成 taskkill /T /F。"""
    target = 4321
    identity = {"pid": target, "created_at": 1, "image": "mine.exe"}
    monkeypatch.setattr(process_control, "ancestor_pids", lambda pid=None: {os.getpid()})
    monkeypatch.setattr(process_control, "pid_alive", lambda pid: True)
    monkeypatch.setattr(process_control, "process_identity", lambda pid: dict(identity))
    reasons: list[str] = []
    assert process_control.force_kill_tree(target, "", identity=identity, reason=reasons) is False
    assert any("bare taskkill is not allowed" in item for item in reasons)
    assert not kill_spy["taskkill"], "绝不允许执行 taskkill"


@pytest.mark.skipif(sys.platform != "win32", reason="Job Object 是 Windows 语义")
def test_refuses_when_job_object_unavailable(kill_spy, monkeypatch) -> None:
    target = 4321
    identity = {"pid": target, "created_at": 1, "image": "mine.exe"}
    monkeypatch.setattr(process_control, "ancestor_pids", lambda pid=None: {os.getpid()})
    monkeypatch.setattr(process_control, "pid_alive", lambda pid: True)
    monkeypatch.setattr(process_control, "process_identity", lambda pid: dict(identity))
    monkeypatch.setattr(
        process_control.WindowsProcessJob,
        "terminate_named",
        classmethod(lambda cls, name: False),
    )
    reasons: list[str] = []
    assert process_control.force_kill_tree(
        target, "missing-job", identity=identity, reason=reasons
    ) is False
    assert any("unavailable" in item for item in reasons)
    assert not kill_spy["taskkill"]


@pytest.mark.skipif(sys.platform != "win32", reason="Job Object 是 Windows 语义")
def test_allows_kill_with_full_proof(kill_spy, monkeypatch) -> None:
    """所有权齐备（非祖先 + 身份匹配 + 持有 Job）才允许终止。"""
    target = 4321
    identity = {"pid": target, "created_at": 111, "image": "mine.exe"}
    monkeypatch.setattr(process_control, "ancestor_pids", lambda pid=None: {os.getpid()})
    monkeypatch.setattr(process_control, "pid_alive", lambda pid: True)
    monkeypatch.setattr(process_control, "process_identity", lambda pid: dict(identity))
    assert process_control.force_kill_tree(target, "job-a", identity=identity) is True
    assert kill_spy["job"] == ["job-a"], "只应终止自己那个 Job"


@pytest.mark.skipif(sys.platform != "win32", reason="Job Object 是 Windows 语义")
def test_parallel_runs_only_terminate_own_job(kill_spy, monkeypatch) -> None:
    """并行 run 各自只碰自己的 Job，互不越界。"""
    monkeypatch.setattr(process_control, "ancestor_pids", lambda pid=None: {os.getpid()})
    monkeypatch.setattr(process_control, "pid_alive", lambda pid: True)
    monkeypatch.setattr(
        process_control, "process_identity",
        lambda pid: {"pid": pid, "created_at": 1, "image": ""},
    )
    for pid, job in ((1111, "job-run-a"), (2222, "job-run-b")):
        process_control.force_kill_tree(
            pid, job, identity={"pid": pid, "created_at": 1, "image": ""}
        )
    assert kill_spy["job"] == ["job-run-a", "job-run-b"]


# ── 陈旧记录：切断自我强化循环 ────────────────────────────────


def test_boot_id_is_stable_within_process() -> None:
    assert process_control.boot_id() == process_control.boot_id()


def test_stale_record_detection(monkeypatch) -> None:
    from tools.cli import api

    monkeypatch.setattr(api, "same_boot", lambda recorded: recorded == "boot-current")
    assert api._is_stale_record({"boot_id": "boot-previous"}) is True
    assert api._is_stale_record({}) is True, "缺 boot_id 的旧记录必须判 stale"
    assert api._is_stale_record({"boot_id": "boot-current"}) is False


def test_boot_id_comparison_tolerates_sampling_jitter() -> None:
    """不同进程各自算开机时刻会有秒级偏差——不得因此把合法记录误判为 stale。

    审查 P2-3：拒绝过度会留下孤儿进程，虽不如误杀严重，仍是可用性缺陷。
    """
    current = process_control.boot_id()
    assert process_control.same_boot(current, current) is True
    try:
        nearby = str(int(current) + 30)
    except ValueError:
        return  # 退化标识（拿不到开机时刻）本就要求严格相等
    assert process_control.same_boot(nearby, current) is True, "秒级抖动必须被吸收"
    far = str(int(current) + 100000)
    assert process_control.same_boot(far, current) is False, "跨重启必须判 stale"


# ── 结构性看护：防止改回旧设计 ────────────────────────────────


def test_runner_pid_is_never_a_kill_target() -> None:
    """前台运行时 runner_pid 就是调用方自己——它从来不该出现在终止目标里。"""
    source = (REPO_ROOT / "tools" / "cli" / "api.py").read_text(encoding="utf-8")
    stop_body = source[source.index("def stop(self") : source.index("def describe(self")]
    targets = stop_body[stop_body.index("targets = (") : stop_body.index("for pid, job_name")]
    assert "runner_pid" not in targets, "runner_pid 不得作为终止目标"


def test_access_denied_is_not_treated_as_killable() -> None:
    """无权查询的进程不归我们管，按 fail-closed 视为不可终止。"""
    source = (REPO_ROOT / "tools" / "cli" / "process_control.py").read_text(encoding="utf-8")
    assert "return ctypes.get_last_error() == 5" not in source, (
        "ACCESS_DENIED 不得再被当成「存活且可杀」"
    )


# ── 二次复盘：终止面是"进程组/控制台"时，逐 PID 的祖先检查够不着 ──


def test_ancestry_enumeration_failure_fails_closed(monkeypatch) -> None:
    """枚举不出祖先链时必须当作"目标可能是祖先"，绝不退化成只保护自己。

    旧实现在 Windows 快照失败时落进 POSIX 分支，`/proc` 必然读不到 → parent=0 → break，
    `ancestor_pids()` 静默塌缩成 `{os.getpid()}`，祖先保护整个消失（审查 §6.2）。
    """
    monkeypatch.setattr(process_control, "_windows_parent_map", lambda: None)
    monkeypatch.setattr(process_control, "_read_proc_stat", lambda pid: None)
    with pytest.raises(process_control.AncestryUnavailable):
        process_control.ancestor_pids()
    assert process_control.is_protected_target(4321) is True, "证明不了就当它是祖先"


def test_group_signal_is_refused_when_group_covers_caller(monkeypatch) -> None:
    """进程组覆盖调用方时不得投递组级信号——那会打到宿主控制台上。"""
    monkeypatch.setattr(
        process_control, "ancestor_pids", lambda pid=None: {os.getpid(), 4321}
    )
    assert process_control.group_covers_caller(4321) is True
    assert process_control.group_covers_caller(0) is True, "非法组号按 fail-closed"


def test_group_check_fails_closed_when_ancestry_unavailable(monkeypatch) -> None:
    def _boom(pid=None):
        raise process_control.AncestryUnavailable("snapshot failed")

    monkeypatch.setattr(process_control, "ancestor_pids", _boom)
    assert process_control.group_covers_caller(4321) is True


def test_graceful_stop_checks_group_before_signalling() -> None:
    """`stop_popen` 的优雅路径必须先过组校验——它才是全量跑真正走的主路径。

    上一轮把祖先保护做进了 `force_kill_tree`，但 `stop_popen` 的
    CTRL_BREAK_EVENT / killpg 三处信号完全没有对应的闸，回归覆盖为零。
    """
    source = (REPO_ROOT / "tools" / "cli" / "process_control.py").read_text(encoding="utf-8")
    body = source[source.index("def stop_popen(") : source.index("def force_kill_tree(")
                  ] if "def force_kill_tree(" in source[source.index("def stop_popen("):] else source[source.index("def stop_popen("):]
    assert "group_covers_caller" in body, "stop_popen 的信号路径必须有进程组闸"
    for signal_call in ("send_signal(signal.CTRL_BREAK_EVENT)", "os.killpg(group, signal.SIGINT)"):
        assert signal_call in body
        guard = body.index("group_covers_caller")
        assert guard < body.index(signal_call), f"{signal_call} 必须在组校验之后"


# ── 二次复盘：进程只创建不回收 ──────────────────────────────────


def test_worker_job_is_written_not_only_read() -> None:
    """`worker_job` 曾是只读不写的幽灵字段 → Windows detached worker 永远杀不掉。"""
    source = (REPO_ROOT / "tools" / "cli" / "api.py").read_text(encoding="utf-8")
    assert "worker_job=" in source, "start() 必须落盘 worker_job，否则 stop 必被 fail-closed 拒绝"
    assert "kill_on_close=False" in source, (
        "detached worker 的 Job 不得设 KILL_ON_CLOSE——那会打碎 start() 活过调用方的语义"
    )


def test_client_exposes_reaping_close() -> None:
    """调用方需要一个收口 API，否则 fixture 只能 rmtree 目录、放任进程。"""
    from tools.cli import CliClient

    assert callable(getattr(CliClient, "close", None))
    assert callable(getattr(CliClient, "__enter__", None))
    assert callable(getattr(CliClient, "__exit__", None))


def test_reap_worker_actually_terminates() -> None:
    """终态后 worker 没有存在理由；旧实现 wait 超时就 return，进程只增不减。"""
    source = (REPO_ROOT / "tools" / "cli" / "api.py").read_text(encoding="utf-8")
    body = source[source.index("def _reap_worker(") : source.index("def _release_worker_job(")]
    assert "force_kill_tree" in body, "_reap_worker 超时后必须真回收，不能静默放过"


def test_descendant_enumeration_is_read_only() -> None:
    """`descendant_pids` 是泄漏检测的数据视图，不得成为终止目标来源。

    "是我的后代"不等于"我持有它的所有权凭证"。
    """
    import ast

    assert os.getpid() not in process_control.descendant_pids()
    source = (REPO_ROOT / "tools" / "cli" / "process_control.py").read_text(encoding="utf-8")
    func = next(
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.FunctionDef) and node.name == "descendant_pids"
    )
    # 只看真正的调用，文档串里提到 force_kill_tree 是说明，不是调用
    called = {
        ast.unparse(node.func)
        for node in ast.walk(func)
        if isinstance(node, ast.Call)
    }
    forbidden = {"force_kill_tree", "os.kill", "os.killpg", "proc.kill", "TerminateProcess"}
    assert not (called & forbidden), f"descendant_pids 不得触碰终止手段：{called & forbidden}"


def test_no_bare_taskkill_remains_in_production_code() -> None:
    """生产代码不得再出现执行 taskkill 的语句（注释与文档串不算）。

    用 AST 找真正的调用实参，避免把说明文字误判为调用。
    """
    import ast

    for name in ("process_control.py", "api.py", "runner.py"):
        path = REPO_ROOT / "tools" / "cli" / name
        tree = ast.parse(path.read_text(encoding="utf-8"))
        literals = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        # 文档串是 Expr 语句，不参与执行；这里只看会成为实参的字面量
        docstrings = {
            child.value.value
            for child in ast.walk(tree)
            if isinstance(child, ast.Expr)
            and isinstance(child.value, ast.Constant)
            and isinstance(child.value.value, str)
        }
        executable = [item for item in literals if item not in docstrings]
        offenders = [
            item for item in executable
            if item.strip().lower() == "taskkill"
        ]
        assert not offenders, f"{name} 仍以 taskkill 作为调用实参：{offenders}"
