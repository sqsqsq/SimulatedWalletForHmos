#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线验证的固定入口：按场景跑，参数写在这里，调用方只选场景。

用法（仓根执行）::

    python test/scripts/verify.py affected <测试文件…> [-k <关键词>]   # 改一处：只跑直接覆盖它的测试
    python test/scripts/verify.py full                               # 全量 test/tests
    python test/scripts/verify.py failure-modes                      # 现建装好开发源的模板，跑失效形态
    python test/scripts/verify.py handback                           # 交回前：全量、失效形态、其余离线检查三条通道同时跑
    python test/scripts/verify.py cases                              # 多 Case 计划（全部 Case，并行数取 Case 数）
    python test/scripts/verify.py assembly                           # 装配专项：第二次从空目录重建同一组合（触发条件见 TEST §5）

每一步的完整输出写到 ``output/verify/<时刻>/<步骤>.log``，控制台按完成先后打印每步的结论行与耗时，
最后按固定顺序汇总一次；有一步失败，退出码非 0。场景与层次的用法见 test/TEST.md §5。

同时跑的前提是各步不写同一处：pytest 与失效形态各用自己的临时目录；跨进程共享的重夹具
（``test/tests/shared_state.py``）有锁，先在临时位置造好再改名。

handback 与 full 由这里（父进程）在计时开始之后准备一次只读的共享前态，交给各通道读，结束时由父进程清掉：

- 正式装配的模板（handback、full、failure-modes）：失效形态与全量里核装配身份的那一组读同一份；
  经 ``STORY_TEST_ASSEMBLY_ROOT`` / ``STORY_TEST_ASSEMBLY_BOUNDARY`` 交给 pytest，旁边的 ``assembly-demo.json`` 记装配前后 demo 的状态。
  第二次从空目录重建（装配专项）从不读它；
- 按原合同正式安装的包（handback、full）：经 ``STORY_TEST_INSTALLED_PACKAGE`` 交给 worker 只读，要改包的用例先复制。
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
#: 各通道的固定并发上限：全量 worker 数（full 与 handback 同一个）、失效形态进程数、cli 离线测试 worker 数。
#: 全量 8 个 worker：测试进程内的 node 宿主下 8 worker 比 4 worker 快一倍、内存仍宽裕（2.0.2 F 批实测，用户 2026-11-04 同意固定为 8）
FULL_WORKERS, FAILURE_JOBS, CLI_WORKERS = 8, 1, 1
#: 第二次从空目录重建：装配专项，只在被测 Framework 登记、本地补丁或模板装配代码变了时跑；full 不选它
SECOND_REBUILD = "test/tests/test_verifier_chain_in_workspace.py::ASecondEmptyDirectoryRebuildsTheSameCombination"


def pytest_step(name: str, targets: list[str], extra: list[str] | None = None,
                workers: int | None = None) -> tuple[str, list[str]]:
    parallel = PARALLEL if workers is None else (["-n", str(workers), "--dist", "loadscope"] if workers > 1 else ["-p", "no:xdist"])
    return name, [sys.executable, "-m", "pytest", "-q", "-rs", *targets, *parallel, *(extra or [])]


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


def full_steps(workers: int | None = None) -> list[tuple[str, list[str]]]:
    return [pytest_step("full", [str(TESTS)], ["--durations", "10", "--deselect", SECOND_REBUILD], workers)]


def assembly_steps() -> list[tuple[str, list[str]]]:
    return [pytest_step("assembly", [SECOND_REBUILD])]


def failure_mode_steps(template: str, jobs: int | None = None) -> list[tuple[str, list[str]]]:
    return [("failure-modes", [sys.executable, str(HERE / "check_failure_modes.py"), "--project-root", template,
                               *(["--jobs", str(jobs)] if jobs else [])])]


def other_offline_steps() -> list[tuple[str, list[str]]]:
    mjs = sorted(str(p) for p in (REPO / "extensions").rglob("*.mjs") if "node_modules" not in p.parts)
    return [
        pytest_step("cli-tests", [str(REPO / "test" / "tools" / "cli")], workers=CLI_WORKERS),
        ("compileall", [sys.executable, "-m", "compileall", "-q", "-j", "1", "tools/cli", "test/scripts"]),
        ("validate-clis", [sys.executable, "-m", "tools.cli.scripts.validate_clis"]),
        # 每个 .mjs 各跑一次 `node --check`，由 run() 逐个执行
        ("node-check", ["node-check", *mjs]),
    ]


def case_steps() -> list[tuple[str, list[str]]]:
    count = sum(1 for p in (REPO / "test" / "cases").iterdir() if (p / "case.yaml").is_file())
    return [("cases", [sys.executable, str(HERE / "run_multi_case.py"), "plan", "--all", "--jobs", str(count)])]


class Shared:
    """父进程这一轮准备的只读前态：路径交给子进程（环境变量），结束时由父进程清掉。"""

    def __init__(self) -> None:
        self.env: dict[str, str] = {}
        self.template: str | None = None
        self.cleanup: list[Path] = []

    def assembly(self, log_dir: Path) -> str:
        """正式装配的模板：与 Case 起跑同一个装配函数，这一轮只装一次；装配前后 demo 的状态记在边界记录旁边。"""
        if self.template is None:
            sys.path.insert(0, str(HERE))
            import run_multi_case  # noqa: PLC0415

            before = demo_state()
            template, workspace = run_multi_case.create_workspace_template(log_dir, f"verify-{log_dir.name}")
            (log_dir / "assembly-demo.json").write_text(json.dumps({"before": before, "after": demo_state()},
                                                                   ensure_ascii=False), encoding="utf-8")
            self.cleanup.append(workspace)
            self.template = str(template)
            self.env.update(STORY_TEST_ASSEMBLY_ROOT=self.template,
                            STORY_TEST_ASSEMBLY_BOUNDARY=str(log_dir / "workspace-boundary.json"))
        return self.template

    def installed_package(self) -> None:
        """按原合同（demo 的配置）正式安装开发源的包，worker 只读它。"""
        import tempfile  # noqa: PLC0415
        sys.path.insert(0, str(HERE))
        import publish_to_demo  # noqa: PLC0415
        from design_fixture import link_framework  # noqa: PLC0415

        root = Path(tempfile.mkdtemp(prefix="story-installed-")) / "package"
        self.cleanup.append(root.parent)
        link_framework(root)
        result = publish_to_demo.install_extension(REPO / "extensions", root)
        if result.status != "installed":
            raise RuntimeError(f"开发源装不进共享安装包：{result.status} {result.problems or result.failed}")
        self.env["STORY_TEST_INSTALLED_PACKAGE"] = str(root)

    def clear(self) -> None:
        import shutil  # noqa: PLC0415
        for path in self.cleanup:
            framework = path / "package" / "framework"
            if framework.is_junction() or framework.is_symlink():
                framework.unlink()          # 指向被测 Framework 的链接先拆掉，别顺着它删
            shutil.rmtree(path, ignore_errors=True)


def demo_state() -> list[str]:
    """demo 的提交与工作区状态：装配只应写模板。"""
    demo = REPO / "demo"
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=demo, capture_output=True, text=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain", "-uall", "--", "."], cwd=demo, capture_output=True,
                            text=True, encoding="utf-8").stdout
    return [head, status]


SHARED = Shared()


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
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", **SHARED.env}
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
    template_steps = named("failure-modes", lambda d: failure_mode_steps(SHARED.assembly(d)))
    handback_failure = named("failure-modes", lambda d: failure_mode_steps(SHARED.assembly(d), FAILURE_JOBS))
    return {
        "affected": [[lambda _: affected_steps(args.targets, args.keyword)]],
        "full": [[lambda _: full_steps(FULL_WORKERS)]],
        "failure-modes": [[template_steps]],
        "cases": [[lambda _: case_steps()]],
        "assembly": [[lambda _: assembly_steps()]],
        "handback": [[lambda _: full_steps(FULL_WORKERS)], [handback_failure], [lambda _: other_offline_steps()]],
    }[args.scenario]


def prepare_shared(scenario: str, log_dir: Path) -> None:
    """通道开跑之前由父进程准备共享前态（在总计时之内）：full 与 handback 都装一次模板与安装包——
    单独跑的全量与交回里的全量拿到同一种前态，两轮能逐条对照。"""
    if scenario in ("handback", "full"):
        SHARED.assembly(log_dir)
    if scenario in ("handback", "full"):
        SHARED.installed_package()


def named(label: str, group):
    """给要先准备的步骤组记上名字：准备失败时汇总按这个名字报。"""
    group.label = label
    return group


def run_lane(lane: list, log_dir: Path) -> list[tuple[str, bool, str]]:
    """一条通道的步骤组先后跑。某组的准备（如装模板）抛错时，这一组记为失败并写明原错误与没执行的步骤，
    同一通道后面的组照跑，别的通道的真实结果照常汇总——不让一处准备异常吞掉整份汇总、也不让退出码显得成功。"""
    out = []
    for group in lane:
        started = time.monotonic()
        try:
            steps = group(log_dir)
        except BaseException as exc:  # noqa: BLE001 —— 装配守卫用 SystemExit 中止，同样要记进汇总
            if isinstance(exc, KeyboardInterrupt):
                raise
            label = getattr(group, "label", "准备")
            text = f"{type(exc).__name__}: {exc}"
            (log_dir / f"{label}.log").write_text(f"准备失败，步骤没有执行。\n{text}\n", encoding="utf-8")
            line = f"[失败] {label}（准备，{time.monotonic() - started:.0f} 秒）：{text}——这一组没有执行"
            with _PRINT:
                print(line, flush=True)
            out.append((label, False, line))
            continue
        out.extend(run(name, cmd, log_dir) for name, cmd in steps)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="离线验证的固定入口")
    sub = parser.add_subparsers(dest="scenario", required=True)
    affected = sub.add_parser("affected")
    affected.add_argument("targets", nargs="+")
    affected.add_argument("-k", dest="keyword")
    for name in ("full", "failure-modes", "handback", "cases", "assembly"):
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
    try:
        try:
            prepare_shared(args.scenario, log_dir)
        except BaseException as exc:  # noqa: BLE001 —— 装配守卫用 SystemExit 中止，同样要记进汇总
            if isinstance(exc, KeyboardInterrupt):
                raise
            line = f"[失败] 共享前态（准备，{time.monotonic() - started:.0f} 秒）：{type(exc).__name__}: {exc}——各通道没有执行"
            (log_dir / "共享前态.log").write_text(f"{line}\n", encoding="utf-8")
            print(line, flush=True)
            return 1
        with ThreadPoolExecutor(max_workers=len(lanes)) as pool:
            results = [r for lane in pool.map(lambda lane: run_lane(lane, log_dir), lanes) for r in lane]
    finally:
        SHARED.clear()
    if len(results) > 1:
        print(f"[verify] 汇总（墙钟 {time.monotonic() - started:.0f} 秒）：", flush=True)
        for _, _, line in results:
            print(f"  {line}", flush=True)
    return 0 if all(ok for _, ok, _ in results) else 1

if __name__ == "__main__":
    raise SystemExit(main())
