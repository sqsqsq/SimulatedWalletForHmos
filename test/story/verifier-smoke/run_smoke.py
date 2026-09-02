# -*- coding: utf-8 -*-
"""OpenCode verifier 专用 Spec smoke 驱动（批次 5 步骤 2）。

**要证明什么**：一个真实 CLI 需求跑到 spec 闭环时，verifier 的那条链是不是真的通了——
request 生成 → 独立只读子 agent 执行 → 结论按身份绑定发布 → receipt/closure 采信。
**不证明什么**：Story 成文能力、Extension 的 spec 要求、其它宿主或模型。

三条边界，都是有代价换来的，改之前先看理由：

1. **合成最小工程，不挂 Extension**。本仓 Extension 的 spec post_check 即使在 story flow 缺席时
   跳过 story 判据，§9/§10/§11 三章仍无条件强制——挂上就等于顺带测了 Extension 的 spec 要求，
   而那些失败归不到 D1。工程用 `generic` profile：coding/ut/testing 禁用、UI/视觉能力全 SKIP。
2. **物化走真正的 init**（`init-orchestrate.ts`），不自己再写一个物化器。少写的那份代码不是
   重点，重点是「smoke 里的 .opencode/ 与真实消费仓拿到的完全同源」。
3. **确认按 registry 的 portable 菜单文案匹配，不按轮次序号**。序号一漂移后面全错位且没有信号；
   portable 文案由 `confirmation-registry.yaml` 单点维护，是稳定锚。没有条目命中就**停等**，
   绝不盲答——不然「确认发生在正确时机」这条判据就是摆设。

`harness-runner.ts` **没有** `--project-root`：它按自身位置解析工程根。所以阶段门禁由被测模型
在 workspace 内自己跑，本驱动不代跑，也就不会把报告写进主工程。

命令与产物位置只在 `test/story/TEST.md` 的 verifier smoke 专节维护，本文件不复述。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FIXTURE = HERE / "fixture"
FEATURE = "hide-balance-toggle"
PHASE = "spec"

sys.path.insert(0, str(REPO))

COPY_IGNORE = shutil.ignore_patterns(
    "node_modules", "__pycache__", ".pytest_cache", "dist", "reports",
)
# 阶段状态不能带进新 workspace，否则起跑点不干净；但发布清单声明的占位文件必须留，
# 丢了会被判 framework 漂移。
STATE_KEEP = {".gitkeep"}
# glossary seed 的内容要由 Skill S2 注入，smoke 不需要它——显式 skip，别让它以失败收场。
INIT_SKIP_TASKS = {"ensure-glossary-seed"}
# `run-global-phases` **不允许 skip**（init 的 decision 校验只放行 action=run），而它必然失败：
# catalog/glossary 这两个全局阶段的完成回执要人来填，退出码非零。CLAUDE.md §5 明确四个全局阶段
# 豁免闭环，spec 也不依赖它们的回执，只依赖磁盘上的 catalog/glossary 文件本身。
# 所以这一条按**已知失败**放行；其余任何任务失败一律让 build 失败——不做笼统忽略。
INIT_TOLERATED_FAILURES = {"run-global-phases"}


# ---------------------------------------------------------------------------
# build：造一个可重复的隔离 workspace
# ---------------------------------------------------------------------------

def _copy_framework(ws: Path) -> None:
    shutil.copytree(REPO / "framework", ws / "framework", ignore=COPY_IGNORE)
    state = ws / "framework" / "harness" / "state"
    if state.is_dir():
        for p in state.iterdir():
            if p.name not in STATE_KEEP:
                p.unlink() if p.is_file() else shutil.rmtree(p)


def _exe(name: str) -> str:
    """Windows 上 npx/opencode 都是 .cmd 包装，不走 shell 时裸名解析不到。

    这一条曾表现为 build 直接抛 WinError 2，看不出是「命令找不到」还是「工程有问题」。
    """
    return shutil.which(name) or (f"{name}.cmd" if sys.platform == "win32" else name)


def _run_ts(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    """在**主仓** framework/harness 下跑 ts-node（那里有 node_modules），目标由参数指定。"""
    return subprocess.run(
        [_exe("npx"), "ts-node", script, *args],
        cwd=str(REPO / "framework" / "harness"),
        capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL,
    )


def _init_failures(ws: Path) -> list[str]:
    """从 init 的 run-log 读失败任务名——按任务判，不按整体退出码判。

    整体退出码把「必然失败的那一个」和「真出问题的那些」压成同一个信号；build 的成功判据
    要能区分两者，否则一次真实的物化缺失会被当成已知失败放过去。
    """
    root = ws / "framework" / "harness" / "reports" / "_global" / "init-orchestrate"
    logs = sorted(root.glob("*/run-log.json")) if root.is_dir() else []
    if not logs:
        return []
    doc = _read_json(logs[-1]) or {}
    tasks = doc.get("tasks") or doc.get("results") or []
    return [str(t.get("task_id")) for t in tasks
            if isinstance(t, dict) and str(t.get("status", "")).lower() == "failed"]


def build(ws: Path, *, force: bool = False) -> dict[str, Any]:
    if ws.exists():
        if not force:
            raise SystemExit(f"workspace 已存在：{ws}（要重建请加 --force）")
        shutil.rmtree(ws)
    ws.mkdir(parents=True)

    _copy_framework(ws)
    shutil.copy2(FIXTURE / "framework.config.json", ws / "framework.config.json")
    # 夹具里叫 .seed：`framework.local.json` 被 .gitignore 吞（它本是个人 setup 产物），
    # 直接用真名会让这份夹具进不了版本库，新克隆造不出 workspace 且毫无提示。
    shutil.copy2(FIXTURE / "framework.local.json.seed", ws / "framework.local.json")
    shutil.copytree(FIXTURE / "doc", ws / "doc")
    feature_dir = ws / "doc" / "features" / FEATURE
    feature_dir.mkdir(parents=True)
    # full track 由夹具冻结，不靠模型在 feature.track 关卡上选对。
    (feature_dir / "feature.yaml").write_text("track: full\n", encoding="utf-8")

    staging = _run_ts(
        "scripts/init-orchestrate.ts",
        "--project-root", str(ws), "--harness-root", str(ws / "framework" / "harness"),
        "--adapter", "opencode", "--emit-staging-template",
        "--materialized-adapters", "opencode",
    )
    if staging.returncode != 0:
        raise SystemExit(f"init 计划生成失败：\n{staging.stderr[-2000:]}")
    doc = json.loads(staging.stdout[staging.stdout.index("{"):])
    for task in doc["decision"]["tasks"]:
        if task["task_id"] in INIT_SKIP_TASKS:
            task["action"] = "skip"
    decision_file = ws / ".smoke-init-decision.json"
    context_file = ws / ".smoke-init-context.json"
    decision_file.write_text(json.dumps(doc["decision"], ensure_ascii=False, indent=2), encoding="utf-8")
    context_file.write_text(json.dumps(doc["context"], ensure_ascii=False, indent=2), encoding="utf-8")

    executed = _run_ts(
        "scripts/init-orchestrate.ts",
        "--project-root", str(ws), "--harness-root", str(ws / "framework" / "harness"),
        "--adapter", "opencode", "--execute",
        "--decision-file", str(decision_file), "--context-file", str(context_file),
    )
    unexpected = sorted(set(_init_failures(ws)) - INIT_TOLERATED_FAILURES)
    if unexpected:
        raise SystemExit(f"init 物化失败（任务 {unexpected}）：\n{executed.stdout[-3000:]}")

    # 物化到位才算 build 成功：这两份是 verifier 闭环的两个必要件，缺任一后面全是空跑。
    required = [
        ws / ".opencode" / "agent" / "verifier.md",
        ws / ".opencode" / "plugin" / "record-verifier-report.js",
        ws / ".opencode" / "skill" / "spec" / "SKILL.md",
        ws / "AGENTS.md",
    ]
    missing = [str(p.relative_to(ws)) for p in required if not p.exists()]
    if missing:
        raise SystemExit(f"init 跑完了但产物不全：{missing}")
    return {"workspace": str(ws), "feature": FEATURE, "materialized": [str(p.relative_to(ws)) for p in required]}


# ---------------------------------------------------------------------------
# 固定回复表
# ---------------------------------------------------------------------------

@dataclass
class ReplyRule:
    id: str
    match: str
    reply: str
    reason: str
    expect_phase: str = ""
    fixture_failure: bool = False


def load_replies(path: Path | None = None) -> list[ReplyRule]:
    doc = yaml.safe_load((path or FIXTURE / "replies.yaml").read_text(encoding="utf-8"))
    rules = [ReplyRule(id=r["id"], match=r["match"], reply=str(r["reply"]),
                       reason=r["reason"], expect_phase=r.get("expect_phase", ""))
             for r in doc.get("replies", [])]
    rules += [ReplyRule(id=r["id"], match=r["match"], reply="", reason=r["reason"],
                        fixture_failure=True)
              for r in doc.get("fixture_failures", [])]
    return rules


def match_reply(text: str, rules: list[ReplyRule]) -> ReplyRule | None:
    """按 portable 菜单文案定位确认点。多条命中时取**最先声明**的那条并如实记录。"""
    for rule in rules:
        if rule.match and rule.match in text:
            return rule
    return None


def looks_like_question(text: str) -> bool:
    """是不是在等人拍板：portable 编号菜单是 interaction-renderer 的硬性要求，用它判。"""
    return "1=" in text and "2=" in text


# ---------------------------------------------------------------------------
# run：驱动真实 CLI
# ---------------------------------------------------------------------------

@dataclass
class Turn:
    index: int
    started_at: float
    ended_at: float
    session_id: str | None
    model_text: str
    reply_kind: str          # planned | neutral | none
    reply_id: str | None
    reply_text: str | None
    status: str

    def to_dict(self) -> dict[str, Any]:
        d = dict(self.__dict__)
        d["wall_sec"] = round(self.ended_at - self.started_at, 2)
        return d


@dataclass
class RunOutcome:
    stop_reason: str
    turns: list[Turn] = field(default_factory=list)
    session_id: str | None = None
    cli_config_id: str = ""
    started_at: str = ""
    finished_at: str = ""


def _cli_config(config_id: str) -> dict[str, str]:
    cfg = yaml.safe_load((REPO / "test" / "story" / "config" / "test.yaml").read_text(encoding="utf-8"))
    for entry in cfg["cli"]["configurations"]:
        if entry["id"] == config_id:
            return entry
    raise SystemExit(f"config/test.yaml 里没有 cli_config_id={config_id}")


def run(ws: Path, *, config_id: str, no_progress_limit: int = 8) -> RunOutcome:
    from tools.cli.api import CliClient
    from tools.cli.models import CliRunRequest

    entry = _cli_config(config_id)
    rules = load_replies()
    client = CliClient(runtime_root=ws / ".smoke-cli")
    outcome = RunOutcome(stop_reason="", cli_config_id=config_id,
                         started_at=time.strftime("%Y-%m-%dT%H:%M:%S"))

    prompt = (FIXTURE / "prompt.md").read_text(encoding="utf-8")
    session_id: str | None = None
    no_progress = 0
    index = 0

    while True:
        index += 1
        started = time.time()
        result = client.run(CliRunRequest(
            cli=entry["name"], model=entry["model"], profile=entry.get("profile"),
            prompt=prompt, cwd=ws, session_id=session_id,
        ))
        ended = time.time()
        session_id = getattr(result, "session_id", None) or session_id
        text = _last_text(result)

        if getattr(result, "status", "") not in ("succeeded", "completed"):
            outcome.turns.append(Turn(index, started, ended, session_id, text,
                                      "none", None, None, "cli_failed"))
            outcome.stop_reason = "cli_failed"
            break

        chain = verify(ws, quiet=True)
        if chain["verdict"] == "PASS":
            outcome.turns.append(Turn(index, started, ended, session_id, text,
                                      "none", None, None, "closure_reached"))
            outcome.stop_reason = "closure_reached"
            break

        rule = match_reply(text, rules)
        if rule and rule.fixture_failure:
            outcome.turns.append(Turn(index, started, ended, session_id, text,
                                      "none", rule.id, None, "fixture_failure"))
            outcome.stop_reason = "environment_or_fixture_failed"
            break
        if rule:
            prompt = rule.reply
            outcome.turns.append(Turn(index, started, ended, session_id, text,
                                      "planned", rule.id, rule.reply, "replied"))
            no_progress = 0
            continue
        if looks_like_question(text):
            # 有编号菜单却没有对应条目 = 出现了夹具没预备的确认点。停等，交给维护者。
            outcome.turns.append(Turn(index, started, ended, session_id, text,
                                      "none", None, None, "unknown_question"))
            outcome.stop_reason = "unknown_question"
            break

        # 模型只是在自述推进：给一句中性推进，**不注入任何做法**。
        no_progress += 1
        if no_progress >= no_progress_limit:
            outcome.turns.append(Turn(index, started, ended, session_id, text,
                                      "none", None, None, "no_progress"))
            outcome.stop_reason = "no_progress"
            break
        prompt = "我这边没有要补充的，你按你的判断继续。"
        outcome.turns.append(Turn(index, started, ended, session_id, text,
                                  "neutral", None, prompt, "replied"))

    outcome.session_id = session_id
    outcome.finished_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    return outcome


def _last_text(result: Any) -> str:
    for attr in ("final_text", "output_text", "text"):
        value = getattr(result, attr, None)
        if isinstance(value, str) and value.strip():
            return value
    events = getattr(result, "events", None) or []
    texts = [e.get("content", "") for e in events
             if isinstance(e, dict) and e.get("type") == "text" and e.get("content")]
    return texts[-1] if texts else ""


# ---------------------------------------------------------------------------
# verify：只从磁盘原件重建链路，不看控制台结论
# ---------------------------------------------------------------------------

def verify(ws: Path, *, quiet: bool = False) -> dict[str, Any]:
    reports = ws / "doc" / "features" / FEATURE / PHASE / "reports"
    checks: list[dict[str, Any]] = []

    def add(cid: str, ok: bool, detail: str) -> None:
        checks.append({"id": cid, "status": "PASS" if ok else "FAIL", "detail": detail})

    summary = _read_json(reports / "summary.json")
    subject = (summary or {}).get("verifier_subject_id")
    add("request_generated", bool(subject),
        f"summary.verifier_subject_id={subject}" if subject
        else "summary.json 无 verifier_subject_id——runner 没生成调用凭证（能力未启用或 request 生成失败）")
    if not subject:
        return _finish(checks, quiet)

    # 用 is not None 而不是真值判断：空对象也是「文件在且能解析」，只有缺失/损坏才算 FAIL。
    request = _read_json(reports / f"verifier.request.{subject}.json")
    add("request_on_disk", request is not None, f"verifier.request.{subject}.json")

    report = _read_json(reports / f"verifier.report.{subject}.json")
    add("report_published", bool(report) and report.get("state") == "published",
        f"state={(report or {}).get('state')}")
    if report:
        subs = {report.get("subject_id"), report.get("invocation_subject"), report.get("result_subject"), subject}
        add("subject_bound", len(subs) == 1, f"仓内三值与 summary 现值：{sorted(s for s in subs if s)}")
        agent_id = report.get("agent_id") or ""
        parent = ((report.get("audit") or {}).get("parent_session_id")) or ""
        add("verifier_independent", bool(agent_id) and agent_id != parent,
            f"子会话={agent_id} 主会话={parent}")
        add("published_by_plugin",
            ((report.get("audit") or {}).get("recorded_by")) == "opencode/plugin/record-verifier-report.js",
            f"recorded_by={(report.get('audit') or {}).get('recorded_by')}")

    bedside = _read_json(ws / "framework" / "harness" / "state" / "last-verifier-report.json")
    if bedside:
        checks.append({"id": "bedside_present", "status": "INFO",
                       "detail": f"reason={bedside.get('reason')}（绑定失败过；不一定是本轮）"})

    receipt = _run_ts_in_ws(ws, "scripts/check-receipt.ts", "--feature", FEATURE, "--phase", PHASE)
    add("receipt_closed", receipt.returncode == 0,
        (receipt.stdout or receipt.stderr or "").strip().splitlines()[-1] if (receipt.stdout or receipt.stderr) else "")

    return _finish(checks, quiet)


def _finish(checks: list[dict[str, Any]], quiet: bool) -> dict[str, Any]:
    failed = [c for c in checks if c["status"] == "FAIL"]
    out = {"verdict": "FAIL" if failed else "PASS", "checks": checks}
    if not quiet:
        for c in checks:
            print(f"  [{c['status']:4}] {c['id']}: {c['detail']}")
        print(f"  Verdict: {out['verdict']}")
    return out


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _run_ts_in_ws(ws: Path, script: str, *args: str) -> subprocess.CompletedProcess[str]:
    """闭环判定必须用 workspace 自己的 harness——它按自身位置解析工程根。

    harness 不在或起不来时**如实返回失败**，不抛栈：workspace 坏了是一条要被记录的
    观察结果，让它把整个 verify 打断，现场就只剩一段与判据无关的 traceback。
    """
    harness = ws / "framework" / "harness"
    if not harness.is_dir():
        return subprocess.CompletedProcess(
            args=[script], returncode=2, stdout="",
            stderr=f"workspace 没有 framework/harness（{harness}）——闭环判不了",
        )
    try:
        return subprocess.run(
            [_exe("npx"), "ts-node", script, *args],
            cwd=str(harness),
            capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL,
        )
    except OSError as exc:
        return subprocess.CompletedProcess(args=[script], returncode=2, stdout="", stderr=str(exc))


def export_verifier_session(ws: Path, child_session_id: str) -> dict[str, Any]:
    """把子 agent 会话导出来，用来核「它到底调了哪些工具」——只读约束不靠模型自述。"""
    proc = subprocess.run(
        [_exe("opencode"), "export", child_session_id],
        cwd=str(ws), capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        return {"ok": False, "error": (proc.stderr or "")[-600:]}
    try:
        return {"ok": True, "session": json.loads(proc.stdout)}
    except Exception as exc:
        return {"ok": False, "error": f"导出内容不是 JSON：{exc}"}


# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OpenCode verifier 专用 Spec smoke")
    parser.add_argument("command", choices=["build", "run", "verify", "all"])
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--cli-config", default="bailian-deepseek")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--evidence", help="把运行留痕写到这个 JSON")
    args = parser.parse_args(argv)

    ws = Path(args.workspace).resolve()
    if args.command in ("build", "all"):
        print(json.dumps(build(ws, force=args.force), ensure_ascii=False, indent=2))
    if args.command in ("run", "all"):
        outcome = run(ws, config_id=args.cli_config)
        payload = {
            "cli_config_id": outcome.cli_config_id,
            "stop_reason": outcome.stop_reason,
            "session_id": outcome.session_id,
            "started_at": outcome.started_at,
            "finished_at": outcome.finished_at,
            "turns": [t.to_dict() for t in outcome.turns],
        }
        if args.evidence:
            Path(args.evidence).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in payload.items() if k != "turns"}, ensure_ascii=False, indent=2))
    if args.command in ("verify", "all"):
        result = verify(ws)
        return 0 if result["verdict"] == "PASS" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
