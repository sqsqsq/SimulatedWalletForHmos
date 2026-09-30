"""跨进程共享的重夹具：同一种准备状态整轮只造一次，之后各轮在输入不变时直接复用。

全量并行时每个 worker 是独立进程，进程内缓存让同一份准入蓝图、登记好的 Story 被造了 worker 数那么多遍。
这里把造好的目录放在系统临时目录下，键是输入内容的摘要（夹具、开发版扩展、造状态的脚本与 Framework 版本）：
输入变了键就变，旧目录不再被用到，过两天自行清掉。一个进程在造时别的进程等它造完再复制，不各造一份。

造出来的目录只能含工程内相对路径：复制到别处照样成立；`framework` 是链接，复制时跳过、复制后重接。
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(tempfile.gettempdir()) / "story-test-state"
#: 等别的进程造同一份状态的上限（秒）；超过说明它死在半路，锁作废重造
WAIT = 600


def _files(path: Path):
    if path.is_file():
        yield path
        return
    for p in sorted(path.rglob("*")):
        if p.is_file() and not ({"__pycache__", "node_modules", "framework"} & set(p.relative_to(path).parts)):
            yield p


def digest(*inputs: Path | str) -> str:
    """输入的内容摘要：目录按相对路径与字节，字符串原样。"""
    h = hashlib.sha256()
    for item in inputs:
        if isinstance(item, Path):
            for p in _files(item):
                h.update(p.relative_to(item if item.is_dir() else item.parent).as_posix().encode())
                h.update(p.read_bytes())
        else:
            h.update(str(item).encode())
    return h.hexdigest()[:20]


def framework_version() -> str:
    proc = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD:demo/framework"],
                          capture_output=True, text=True, encoding="utf-8")
    return proc.stdout.strip() or "unknown"


#: 造状态时一定参与的输入：开发版扩展与造状态的脚本
COMMON = (REPO_ROOT / "extensions", REPO_ROOT / "test" / "scripts" / "design_fixture.py",
          Path(__file__).with_name("designed_fixture.py"), Path(__file__).with_name("design_kit.py"))


def _prune() -> None:
    if not ROOT.is_dir():
        return
    stale = time.time() - 2 * 86400
    for d in ROOT.iterdir():
        try:
            if d.stat().st_mtime < stale:
                shutil.rmtree(d, ignore_errors=True) if d.is_dir() else d.unlink()
        except OSError:
            pass


def shared_tree(name: str, key: str, build: Callable[[Path], None]) -> Path:
    """`name-key` 这份状态的目录：没有就由第一个到的进程在临时位置造好再改名，其余进程等它就绪。"""
    ROOT.mkdir(parents=True, exist_ok=True)
    final = ROOT / f"{name}-{key}"
    if (final / ".ready").is_file():
        return final
    lock = ROOT / f"{name}-{key}.lock"
    deadline = time.time() + WAIT
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if (final / ".ready").is_file():
                return final
            if time.time() > deadline or time.time() - lock.stat().st_mtime > WAIT:
                lock.unlink(missing_ok=True)
                deadline = time.time() + WAIT
            time.sleep(0.2)
            continue
        os.close(fd)
        break
    try:
        if not (final / ".ready").is_file():
            _prune()
            work = ROOT / f"{name}-{key}.building-{os.getpid()}"
            shutil.rmtree(work, ignore_errors=True)
            build(work)
            (work / ".ready").write_text("", encoding="utf-8")
            shutil.rmtree(final, ignore_errors=True)
            os.replace(work, final)
        return final
    finally:
        lock.unlink(missing_ok=True)


def copy_tree(base: Path, target: Path) -> None:
    """把共享状态复制到用例自己的目录：跳过 framework 链接与就绪标记，复制后由调用方重接 Framework。"""
    shutil.copytree(base, target, dirs_exist_ok=True,
                    ignore=lambda d, names: ["framework", ".ready"] if Path(d) == base else [])
