"""测试进程的三件公共设施：node 的转译缓存，进程内执行 node 产品命令的宿主，与跑完之后按类报用时的检测器。

转译缓存：测试起的每个 node 进程都带上 ts-node 转译缓存（见 ts_transpile_cache.cjs），Framework 原生模块不再每个进程重新转译。
缓存按内容取键，放系统临时目录，跨轮复用；删掉它只会让下一轮重新转译。

进程内宿主：测试起的 `node 产品脚本` 与 `node --input-type=module -e` 由本进程的一个 node 宿主在进程内执行
（`node_host_bridge.py`、`node_host.mjs`），Framework 每个测试进程只加载一次；宿主随测试进程起停。类上写 `REAL_CLI = True`
的用例照常起真实进程（进程边界本身的见证），`STORY_TEST_NODE_HOST=0` 时全部走真实进程。

用时检测：`--dist loadscope` 把一个类整个交给一个 worker，最慢的那个类决定整轮多久。每条用例记下用时与它起的子进程数，
跑完按类汇总：超过类预算的、整轮超过 2 分钟的，在末尾点名。它只报告不判失败——用时随机器负载浮动，判失败会误伤；
点名的类按 README「用时预算」处置。
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
from collections import defaultdict
from pathlib import Path

import pytest

_PRELOAD = Path(__file__).with_name("ts_transpile_cache.cjs").resolve()
os.environ.setdefault("STORY_TEST_TS_CACHE", str(Path(tempfile.gettempdir()) / "story-ts-transpile-cache"))
os.environ["NODE_OPTIONS"] = " ".join(filter(None, [os.environ.get("NODE_OPTIONS", ""), f'--require "{_PRELOAD.as_posix()}"']))

#: 整轮全量的目标用时（秒）
SUITE_BUDGET = 120
#: 一个类（loadscope 的一个调度单位）在全量并行下的汇总用时上限（秒）：超过它，这个类就开始拖整轮
CLASS_BUDGET = 45

_spawns = 0
_real_init = subprocess.Popen.__init__


def _counting_init(self, *args, **kwargs):
    global _spawns
    _spawns += 1
    _real_init(self, *args, **kwargs)


subprocess.Popen.__init__ = _counting_init
_classes: dict[str, list[float]] = defaultdict(lambda: [0.0, 0, 0, 0])
_started = time.time()

import node_host_bridge  # noqa: E402  —— NODE_OPTIONS 定好之后再起宿主：宿主与真实进程带同一份预载

_jobs_at_start = 0


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    global _spawns, _jobs_at_start
    _spawns = 0
    _jobs_at_start = node_host_bridge.jobs
    node_host_bridge.real_cli = bool(getattr(item.cls, "REAL_CLI", False) or getattr(item.module, "REAL_CLI", False))


def pytest_runtest_makereport(item, call):
    if call.when == "teardown":
        item.user_properties.append(("spawns", _spawns))
        item.user_properties.append(("host_jobs", node_host_bridge.jobs - _jobs_at_start))


def pytest_runtest_logreport(report):
    if report.when not in ("setup", "call", "teardown"):
        return
    scope = "::".join(report.nodeid.split("::")[:2])
    row = _classes[scope]
    row[0] += report.duration
    if report.when == "teardown":
        row[1] += 1
        row[2] += dict(report.user_properties).get("spawns", 0)
        row[3] += dict(report.user_properties).get("host_jobs", 0)


def pytest_terminal_summary(terminalreporter):
    if not _classes or hasattr(terminalreporter.config, "workerinput"):
        return
    wall = time.time() - _started
    dump = os.environ.get("STORY_TEST_TIMING_JSON")
    if dump:      # 给计时拆分用：全部类的用时、条数与子进程数，按用时排序
        import json  # noqa: PLC0415
        Path(dump).write_text(json.dumps({"wall": round(wall, 1), "classes": [
            {"class": k, "seconds": round(s, 1), "tests": n, "spawns": p, "host_jobs": h}
            for k, (s, n, p, h) in sorted(_classes.items(), key=lambda kv: -kv[1][0])]}, ensure_ascii=False, indent=1), encoding="utf-8")
    slow = sorted(((s, n, p, k) for k, (s, n, p, _h) in _classes.items() if s > CLASS_BUDGET), reverse=True)
    full = len(_classes) > 100
    if not slow and (wall <= SUITE_BUDGET or not full):
        return
    terminalreporter.section("用时预算（test/tests/README.md「用时预算」）")
    if full and wall > SUITE_BUDGET:
        terminalreporter.write_line(f"整轮 {wall:.0f} 秒，超过目标 {SUITE_BUDGET} 秒")
    for s, n, p, k in slow[:12]:
        terminalreporter.write_line(f"{s:6.0f}s  {n:3d} 条  子进程 {p:4d}  {k}")
