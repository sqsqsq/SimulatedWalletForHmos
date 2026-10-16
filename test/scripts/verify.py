#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线验证的固定入口：按场景跑，参数写在这里，调用方只选场景。

用法（仓根执行）::

    python test/scripts/verify.py affected <测试文件…> [-k <关键词>]   # 改一处：只跑直接覆盖它的测试
    python test/scripts/verify.py full                               # 全量 test/tests
    python test/scripts/verify.py failure-modes                      # 现建装好开发源的模板，跑失效形态
    python test/scripts/verify.py handback                           # 交回前：全量、失效形态、其余离线检查三条通道同时跑
    python test/scripts/verify.py cases                              # 多 Case 计划（全部 Case，并行数取 Case 数）

每一步的完整输出写到 ``output/verify/<时刻>/<步骤>.log``，控制台按完成先后打印每步的结论行与耗时，
最后按固定顺序汇总一次；有一步失败，退出码非 0。场景与层次的用法见 test/TEST.md §5。

同时跑的前提是各步不写同一处：每次现建自己的模板，pytest 与失效形态各用自己的临时目录；
跨进程共享的重夹具（``test/tests/shared_state.py``）有锁，先在临时位置造好再改名。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TESTS = REPO / "test" / "tests"
#: pytest 的并行参数：loadscope 让同一个类的用例落在同一个 worker，类级夹具只建一次
PARALLEL = ["-n", "auto", "--dist", "loadscope"]


def pytest_step(name: str, targets: list[str], extra: list[str] | None = None) -> tuple[str, list[str]]:
    return name, [sys.executable, "-m", "pytest", "-q", *targets, *PARALLEL, *(extra or [])]


def affected_steps(targets: list[str], keyword: str | None) -> list[tuple[str, list[str]]]:
    """给的测试文件可以写仓根相对路径，也可以只写 test/tests 下的文件名。"""
    resolved = []
    for t in targets:
        path = Path(t)
        if not path.exists() and (TESTS / t).exists():
            path = TESTS / t
        if not path.exists():
            raise SystemExit(f"[verify] 找不到测试 {t}（仓根相对路径或 test/tests 下的文件名）")
        resolved.append(str(path))
    return [pytest_step("affected", resolved, ["-k", keyword] if keyword else [])]


def full_steps() -> list[tuple[str, list[str]]]:
    return [pytest_step("full", [str(TESTS)], ["--durations", "10"])]


def failure_mode_steps(template: str) -> list[tuple[str, list[str]]]:
    return [("failure-modes", [sys.executable, str(HERE / "check_failure_modes.py"), "--project-root", template])]


def other_offline_steps() -> list[tuple[str, list[str]]]:
    mjs = sorted(str(p) for p in (REPO / "extensions").rglob("*.mjs") if "node_modules" not in p.parts)
    return [
        pytest_step("cli-tests", [str(REPO / "test" / "tools" / "cli")]),
        ("compileall", [sys.executable, "-m", "compileall", "-q", "-j", "0", "tools/cli", "test/scripts"]),
        ("validate-clis", [sys.executable, "-m", "tools.cli.scripts.validate_clis"]),
        # 每个 .mjs 各跑一次 `node --check`，由 run() 逐个执行
        ("node-check", ["node-check", *mjs]),
    ]


def case_steps() -> list[tuple[str, list[str]]]:
    count = sum(1 for p in (REPO / "test" / "cases").iterdir() if (p / "case.yaml").is_file())
    return [("cases", [sys.executable, str(HERE / "run_multi_case.py"), "plan", "--all", "--jobs", str(count)])]


def build_template(log_dir: Path) -> str:
    """装好开发源的隔离模板：与 Case 起跑同一个装配函数，每次新建。"""
    sys.path.insert(0, str(HERE))
    import run_multi_case  # noqa: PLC0415

    suite_id = f"verify-{log_dir.name}"
    template, _ = run_multi_case.create_workspace_template(log_dir, suite_id)
    return str(template)


def summary(name: str, text: str) -> str:
    """每步的结论行：失效形态取「形态 N 条」那一行，compileall 与 validate_clis、Case 计划各给一句，其余（pytest 的计数行等）取最后一行非空输出。"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if name == "failure-modes":
        return next((l for l in reversed(lines) if l.startswith("形态 ")), lines[-1] if lines else "")
    if name == "compileall":
        return "无编译错误" if not lines else lines[-1]
    if name == "validate-clis":
        try:
            report = json.loads(text)
        except ValueError:
            return lines[-1] if lines else ""
        return f"ok={report.get('ok')}，CLI：{'、'.join(report.get('clis', []))}"
    if name == "cases":
        try:
            plan = json.loads(text)
        except ValueError:
            return lines[-1] if lines else ""
        return f"{len(plan.get('cases', []))} 个 Case 的计划：" + "、".join(c.get("case", "?") for c in plan.get("cases", []))
    return lines[-1] if lines else ""


_PRINT = threading.Lock()


def run(name: str, argv: list[str], log_dir: Path) -> tuple[str, bool, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    started = time.monotonic()
    if argv[0] == "node-check":
        problems = []
        for path in argv[1:]:
            proc = subprocess.run(["node", "--check", path], cwd=REPO, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", env=env)
            if proc.returncode:
                problems.append(f"{path}\n{proc.stderr}")
        text = "\n".join(problems) or f"{len(argv) - 1} 个 .mjs 语法通过"
        ok = not problems
    else:
        proc = subprocess.run(argv, cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        text = proc.stdout + proc.stderr
        ok = proc.returncode == 0
    (log_dir / f"{name}.log").write_text(text, encoding="utf-8")
    line = f"[{'通过' if ok else '失败'}] {name}（{time.monotonic() - started:.0f} 秒）：{summary(name, text)}"
    with _PRINT:
        print(line, flush=True)
    return name, ok, line


def scenario(args: argparse.Namespace) -> list[list]:
    """场景 → 通道：不同通道同时跑，同一通道里的步骤组先后跑。

    每组拿日志目录、返回步骤列表，轮到它才求值：失效形态的模板在它那条通道开跑时才建。
    """
    template_steps = lambda d: failure_mode_steps(build_template(d))  # noqa: E731
    return {
        "affected": [[lambda _: affected_steps(args.targets, args.keyword)]],
        "full": [[lambda _: full_steps()]],
        "failure-modes": [[template_steps]],
        "cases": [[lambda _: case_steps()]],
        "handback": [[lambda _: full_steps()], [template_steps], [lambda _: other_offline_steps()]],
    }[args.scenario]


def run_lane(lane: list, log_dir: Path) -> list[tuple[str, bool, str]]:
    return [run(name, cmd, log_dir) for group in lane for name, cmd in group(log_dir)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="离线验证的固定入口")
    sub = parser.add_subparsers(dest="scenario", required=True)
    affected = sub.add_parser("affected")
    affected.add_argument("targets", nargs="+")
    affected.add_argument("-k", dest="keyword")
    for name in ("full", "failure-modes", "handback", "cases"):
        sub.add_parser(name)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    if args.scenario == "affected":
        affected_steps(args.targets, args.keyword)   # 找不到的测试先报，不建日志目录
    log_dir = REPO / "output" / "verify" / f"{datetime.now():%Y%m%d-%H%M%S}-{args.scenario}"
    log_dir.mkdir(parents=True, exist_ok=True)
    print(f"[verify] {args.scenario}，日志在 {log_dir.relative_to(REPO).as_posix()}", flush=True)
    lanes = scenario(args)
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=len(lanes)) as pool:
        results = [r for lane in pool.map(lambda lane: run_lane(lane, log_dir), lanes) for r in lane]
    if len(results) > 1:
        print(f"[verify] 汇总（墙钟 {time.monotonic() - started:.0f} 秒）：", flush=True)
        for _, _, line in results:
            print(f"  {line}", flush=True)
    return 0 if all(ok for _, ok, _ in results) else 1

if __name__ == "__main__":
    raise SystemExit(main())
