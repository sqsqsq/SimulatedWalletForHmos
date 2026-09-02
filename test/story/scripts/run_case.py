"""驱动被测 CLI 按 story 流程跑一遍，并把过程与产物落盘供观测。

    python run_case.py <case-id> start                     # 后台跑，标准入口
    python run_case.py <case-id> poll --cursor 0 --model-cursor 0 --wait-sec 120
    python run_case.py <case-id> status
    python run_case.py <case-id> reply --text "…"          # 以用户身份回一句话
    python run_case.py <case-id> stop [--force]
    python run_case.py <case-id> run                       # 前台跑，调试用

所有命令 stdout 输出整块 JSON。

**关卡上谁来回话，分两种模式**（用例的 `interactive` 声明）：自动模式由驱动器替人回
一句「按你推荐的走」；交互模式停下来等真人 `reply`。关卡呈现质量、用户口述新诉求、
拆分讨论这些行为只有交互模式测得到——自动模式替人给的永远是同一句话。

**harness 的目标只有一个：观测被测 CLI 按 story 跑出来的效果。**
不驱动多轮对话、不中途截停、不生成报告——那些是从 walletkit / dag 抄来的场景，
本项目的测试目标不需要，实测也从未触发（12 条预置应答命中 0、截停规则命中 0，
而 `是否` 那条提问启发式反倒把完成报告误判成未答提问）。分析由评价者按
AGENTS.md §5 自己做。

被测会话只收到用例 prompt；本脚本不注入达标判据或任何测试信息（参考规范 §1.1）。
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import signal
import shutil
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
HOST_ROOT = HERE.parents[2]
WORKSPACE_ENV = "STORY_WORKSPACE_ROOT"
REPO_ROOT = Path(os.environ.get(WORKSPACE_ENV, str(HOST_ROOT))).resolve()
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HOST_ROOT))

import run_layout
from cli_config_group import load_cli_group, select_cli
from phase_state import derive_phase_state


def _configure_console() -> None:
    """Windows 控制台默认非 UTF-8，中文会变乱码，审计输出等于不可读。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


_configure_console()

CFG = yaml.safe_load((HERE.parent / "config" / "test.yaml").read_text(encoding="utf-8"))
TARGET = (REPO_ROOT / CFG["target"]["path"]).resolve()
FEATURES_DIR = str(CFG["target"]["features_dir"])
OUT_ROOT = Path(CFG["output"]["dir"])
if not OUT_ROOT.is_absolute():
    # 结果和测试脚本属于宿主侧；被测工程可以位于独立临时 workspace。
    OUT_ROOT = HOST_ROOT / OUT_ROOT

CLI_CONFIGURATIONS, CLI_RETRY_POLICY = load_cli_group(CFG)
if "turn_timeout" in CFG["cli"] or "idle_timeout" in CFG["cli"]:
    raise SystemExit("[runner] turn_timeout/idle_timeout 已废弃：静默不是失败条件")
# **本域不设运行时限**（用户裁定 2026-08-31）。时限保护的是「进程失控」，
# 而这里的观测者逐轮驱动、随时可以 stop——一个跑得久的阶段不是失控，是它本来就长。
# 实测两次：`end_phase` 靠前时时限反而先到，把正在推进的会话从中间切断，
# 留下一堆半成品产物，观测到的既不是能力也不是缺陷。传 0 = 不限制。
NO_TIME_LIMIT = 0
STOP_GRACE = int(CFG["cli"].get("stop_grace", 60))
OBSERVATION_INTERVAL_SEC = int(CFG.get("observation", {}).get("interval_sec", 120))
HEARTBEAT_INTERVAL_SEC = int(CFG.get("observation", {}).get("heartbeat_sec", 10))
WORKER_LEASE_SEC = int(CFG.get("observation", {}).get("lease_sec", 180))
FEATURE_HISTORY_CFG = CFG.get("feature_history", {})
FEATURE_HISTORY_ACTION = str(FEATURE_HISTORY_CFG.get("action_on_new_chain", "move")).strip()
FEATURE_HISTORY_ROOT = Path(os.environ.get(
    "STORY_FEATURE_ARCHIVE_ROOT",
    str(FEATURE_HISTORY_CFG.get("archive_root", r"E:\Project\bak"))))
if not FEATURE_HISTORY_ROOT.is_absolute():
    FEATURE_HISTORY_ROOT = (REPO_ROOT / FEATURE_HISTORY_ROOT).resolve()
FEATURE_HISTORY_TIMESTAMP_FORMAT = str(
    FEATURE_HISTORY_CFG.get("timestamp_format", "%Y%m%d-%H%M%S"))
if STOP_GRACE < 0:
    raise SystemExit("[runner] stop_grace 不能为负")
for gone in ("soft_timeout", "hard_timeout", "phase_hard_timeout", "max_turns",
             "reply_wait_sec"):
    if gone in CFG["cli"]:
        raise SystemExit(
            f"[runner] cli.{gone} 已停用：本域不设运行时限、续话轮次上限，"
            "等宿主回话也不设上限。目标由 end_phase 判定，何时收工由宿主 conclude。"
            "把这一项从配置里删掉")
if OBSERVATION_INTERVAL_SEC <= 0:
    raise SystemExit("[runner] observation.interval_sec 必须大于 0")
if HEARTBEAT_INTERVAL_SEC <= 0 or WORKER_LEASE_SEC <= HEARTBEAT_INTERVAL_SEC:
    raise SystemExit("[runner] worker 租约须满足 0 < heartbeat_sec < lease_sec")
if FEATURE_HISTORY_ACTION != "move":
    raise SystemExit("[runner] feature_history.action_on_new_chain 只支持 move")

if not (HOST_ROOT / "tools" / "cli").is_dir():
    raise SystemExit(f"[runner] 找不到 CLI runtime: {HOST_ROOT / 'tools' / 'cli'}")

from tools.cli import CliClient, CliRunRequest  # noqa: E402
import observe  # noqa: E402

ACTIVE_STATUS = {"starting", "running", "awaiting_reply", "stopping"}
TERMINAL_STATUS = {"finished", "stopped", "stop_failed", "cli_failed",
                   "gate_failed", "target_not_reached", "worker_start_failed",
                   "worker_lost", "source_restore_failed",
                   # 宿主判定本轮到此为止：门禁照跑、产物照出，**不是失败**。
                   # 目标闭没闭环由 target_reached / closure.target_missing 单独说。
                   "concluded_by_host",
                   # CLI 回了 succeeded 却没给 session id，无法续话——adapter 的账，
                   # 不是模型没做完。上一版它被折叠进 target_not_reached。
                   "cli_session_lost",
                   # 装置自己漏跑了 gate。gate 判红是被测对象的账，没跑是装置的账。
                   "harness_incomplete"}
TERMINAL_CLI_STATUS = {"succeeded", "failed", "timed_out", "stopped", "stop_failed"}

# story 的业务关卡会停下来等人选。**两种模式，按用例声明选**：
#
#   自动（缺省）  驱动器用 GATE_REPLY 替人回一句「按你推荐的走」。
#                 它模拟的是**全自动用户**——只覆盖这一种人。
#   交互          驱动器停下来等真人回话（`run_case.py <case> reply --text "…"`）。
#
# 为什么必须有交互模式：关卡呈现质量、用户口述新诉求、拆分讨论这些行为，
# 自动模式**结构上测不到**——它替人给出的永远是同一句话，模型永远只走「照推荐走」
# 那条路。曾为了测「用户要求拆分」把答案预塞进初始 prompt，逼出的是记忆衰减问题，
# 与真实交互无关（实测：模型在几十步后概括任务描述，把那句话整句丢了）。
GATE_REPLY = "按你推荐的选项继续，不用再问我；每个决策照常写明选了哪一项、依据是什么。"
# **等宿主回话不设上限**（见 wait_for_human_reply）。等久了每这么多秒出一次声——
# 一直等不等于没人知道它在等。这是提醒，不是时限。
REPLY_NUDGE = int(CFG["cli"].get("reply_nudge_sec", 300))
REPLY_FILE = "reply.json"
# 宿主判定「本轮到此为止」。与 reply 同构的单槽文件：写它不杀任何进程，
# worker 读到就退出续话循环、照常跑完门禁与收尾。
CONCLUDE_FILE = "conclude.json"
# 交给宿主的模型原话截断长度——够他判断，又不至于把 poll 响应撑爆。
PROMPT_LIMIT = 4000


def driver_prompt(prompt: str, interactive: bool) -> str:
    # 交互协议由宿主侧 interaction-script 驱动，不能把测试控制语句拼进业务 prompt。
    del interactive
    return prompt

# 阶段序列（framework 的 feature full 轨）。end_phase 用它定位「跑到哪为止」。
PHASE_ORDER = ("spec", "plan", "coding", "review", "ut", "testing")
# **不设续话轮次上限**（用户裁定 2026-08-31）。上一版按 end_phase 求和分配预算，
# 而 story 流程自己的关卡（取材、补料、范围、成文前确认）不在 PHASE_ORDER 里、
# 一轮都分不到——`end_phase=spec` 时全程只有 6 轮，光走关卡就用光，模型刚在 spec
# 抛出术语映射表等人确认就被判「目标未达成」。终点由 end_phase 判定，
# 空转由观测者看着 stop，不由一个与关卡数无关的计数器代管。
# 产品源码目录。coding 阶段会写这里，跑完必须复位，否则第二轮起跑点就不是干净的。
# **精确列举而不是「除 doc/test 之外」**：漏掉一个目录只是少复位一处，
# 而多算一个目录会把被测件（doc/extensions）或 harness 自己（test/story）删掉。
SOURCE_DIRS = ("01-Product", "02-Feature", "04-BusinessBase", "05-SystemBase")


def is_interactive(case: dict) -> bool:
    """用例是否要真人在回路。缺省 False——既有用例行为逐字节不变。"""
    return bool(case.get("interactive"))


def pop_pending_reply(out_dir: Path) -> str | None:
    """取走人写下的那句话（取走即删，一句话只用一次）。

    读失败当作没有：半写状态下一轮就完整了，把破文件当成回话反而会把
    残缺内容送进被测会话。
    """
    path = out_dir / REPLY_FILE
    try:
        text = str(json.loads(path.read_text(encoding="utf-8")).get("text") or "").strip()
    except Exception:  # noqa: BLE001
        return None
    if not text:
        return None
    path.unlink(missing_ok=True)
    return text


def pop_conclude_request(out_dir: Path) -> dict | None:
    """取走宿主的收工判定（取走即删，同 `pop_pending_reply`）。

    返回的是那条判定本身（含 `reason`），不是布尔——理由要写进终态回执，
    事后才看得出这一轮为什么停在这里。
    """
    path = out_dir / CONCLUDE_FILE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(payload, dict):
        return None
    path.unlink(missing_ok=True)
    return payload


def wait_for_human_reply(out_dir: Path, feed, runlog, state: dict, *,
                         turn: int, prompt: str = "") -> str | None:
    """交互模式：停下来等宿主回话。**无限等，不设上限。**

    上一版等 `REPLY_WAIT`（1 小时）就 break，结果被折叠成 `target_not_reached`——
    与「模型真没做完」同一个桶，报告上完全看不出是没人回话。而它等的不是人的键盘，
    是**宿主**（一个模型）有没有把回复放进来；宿主会被别的事打断、会跨会话。
    实测两个 Case 分别空等 45 分钟与 33 分钟，距那道线只差 15 分钟。

    所以时限退场：等不到就一直等，每 `REPLY_NUDGE` 秒出一次声。循环里照常续租，
    无限等**不会**触发 lease 失联。出口有两个——宿主回话，或宿主 conclude。

    `prompt` 是模型本轮最后说的那段话，随停等一起交给宿主：他据它当轮就能回，
    不必再去 events.jsonl 尾部捞。

    @returns 宿主的回话；`None` 表示宿主判定本轮到此为止（conclude）。
    """
    state.update(status="awaiting_reply", awaiting_since=time.strftime("%Y-%m-%d %H:%M:%S"),
                 awaiting_turn=turn, awaiting_kind="story_gate",
                 awaiting_prompt=(prompt or "")[:PROMPT_LIMIT],
                 awaiting_prompt_source="cli_text_event" if prompt else "unavailable")
    refresh_worker_lease(out_dir, state, force=True, event="awaiting_reply")
    feed.emit("awaiting_reply", turn=turn)
    runlog.event("等待回话", f"第 {turn} 轮结束，等宿主回话："
                             f"run_case.py <case> reply --text \"…\"")
    print(f"[live] awaiting reply (turn={turn}) —— "
          f"用 run_case.py <case> reply --text \"…\" 回话", file=sys.stderr, flush=True)
    waited = 0.0
    nudged = 0
    while True:
        refresh_worker_lease(out_dir, state)
        text = pop_pending_reply(out_dir)
        if text:
            # 人工等待单独累计：它与模型耗时性质完全不同，混进总墙钟就再也分不出
            # 「跑得慢」和「没人回话」。度量侧只读这两个字段，不自己去重建等待区间。
            state["human_wait_sec"] = round(float(state.get("human_wait_sec") or 0.0) + waited, 1)
            state["human_wait_events"] = int(state.get("human_wait_events") or 0) + 1
            state.update(status="running", awaiting_since=None,
                         awaiting_prompt=None, awaiting_prompt_source=None)
            refresh_worker_lease(out_dir, state, force=True, event="human_reply")
            feed.emit("human_reply", turn=turn, text=observe.shorten(text, 300))
            runlog.event("人回话", text[:200])
            return text
        if pop_conclude_request(out_dir) is not None:
            return None
        time.sleep(1.0)
        waited += 1.0
        # 等久了要出声——「一直等」不等于「没人知道它在等」。
        if REPLY_NUDGE and waited >= REPLY_NUDGE * (nudged + 1):
            nudged += 1
            state["awaiting_stale_sec"] = int(waited)
            refresh_worker_lease(out_dir, state, force=True, event="awaiting_reply_stale")
            feed.emit("awaiting_reply_stale", turn=turn, waited_sec=int(waited))


def resolve_start_phase(case: dict, override: str | None = None) -> str:
    """从哪个阶段起跑。缺省 `story` = 从头，既有用例行为逐字节不变。"""
    value = str(override or case.get("start_phase") or "story").strip()
    if value != "story":
        phase_index(value)      # 校验合法性，写错当场报
    return value


def should_migrate_feature_history(start_phase: str) -> bool:
    """只有新 Story 链迁移同一 feature 的历史产物；阶段续跑原样保留输入。"""
    return start_phase == "story"


def phase_before(phase: str) -> str | None:
    """前一个阶段。续跑前要校验它已闭环——在半成品上跑下游，失败了也无法归因。"""
    if phase == "story":
        return None
    idx = phase_index(phase)
    return "story" if idx == 0 else PHASE_ORDER[idx - 1]


VERIFIER_REPORT_PATTERNS = (
    # 现协议：报告由 SubagentStop 钩子从 verifier 的终态消息生成，按 subject 分区落盘。
    # 这两条不加，闭环判定会把**已经闭环**的阶段判成未闭环——驱动器于是反复下发
    # 同一条推进指令，模型按规则拒绝重跑，空转到没人叫停为止（旧协议下实测过 27 轮）。
    "verifier.report.*.json",
    "verifier.report.*.md",
    # 以下是历史命名。这里与扩展机制层**不同**：机器裁决的真源只能有一个（扩展只认
    # 上面那份 JSON），而这里判的是「报告文件在不在」，认一组名字才不会被换名字打断。
    "verifier.report.md",
    "verifier-report.yaml",
    "verifier-report.yml",
    "verifier-*-result.yaml",
    "verifier-*.md",
    "verify-*.md",
)


def verifier_report(feature: str, phase: str):
    """本阶段的 verifier 产物——认一组文件名，不认单一文件名。

    命名由被测流程决定且历史上变过；驱动器把某一个名字当契约，等于把
    「换了个文件名」变成「阶段永远不闭环」。
    """
    reports = REPO_ROOT / FEATURES_DIR / feature / phase / "reports"
    if not reports.is_dir():
        return None
    for pattern in VERIFIER_REPORT_PATTERNS:
        for hit in sorted(reports.glob(pattern)):
            if hit.is_file():
                return hit
    return None


def phase_evidence_complete(feature: str, phase: str) -> tuple[bool, list[str]]:
    """前序阶段是否已经闭环——续跑与目标终点的共同判据。

    **不用 `check-receipt` 的退出码**：它还会比对 `summary.source_commit_sha` 与当前
    HEAD，HEAD 一推进就判「summary 属旧工作状态」。那条判据对**继续开发**是对的
    （代码变了，旧结论可能不成立），但对**续跑测试**是错的——我们要确认的是
    「上游确实跑完并闭环过」，不是「自那以后没人提交过」。拿它当阻断条件，
    等于要求测试期间全仓静止。

    所以不重跑 check-receipt，而读取它已经定稿进 summary 的 `receipt_status/closure_status`；
    同时仍要求 trace、summary、verifier 与回执四件物理凭证存在。这样 HEAD 后续移动不会
    抹掉“当时已闭环”的历史事实，未填写或未通过的回执也不会因文件占位而被误算成 closed。
    """
    root = REPO_ROOT / FEATURES_DIR / feature / phase
    checks = {
        "trace.json": root / "reports" / "trace.json",
        "summary.json": root / "reports" / "summary.json",
        "完成回执": root / "phase-completion-receipt.md",
    }
    missing = [name for name, path in checks.items() if not path.is_file()]
    # verifier 报告的**文件名不是契约**：同一份内容曾落成 verifier.report.md 与
    # verifier-report.yaml 两种命名。驱动器按单一文件名判闭环时，另一种命名会被判成
    # 「未闭环」→ 反复下发同一条推进指令 → 模型按规则拒绝重跑 → 空转到预算耗尽
    # （实测一次 27 轮）。所以这里认一组名字，任一存在即算。
    if not verifier_report(feature, phase):
        missing.append("verifier 报告")
    if missing:
        return False, missing
    try:
        summary = json.loads(checks["summary.json"].read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError) as exc:
        return False, [f"summary.json 不可读（{exc}）"]
    verdict = str(summary.get("verdict", "")).upper()
    if verdict != "PASS":
        return False, [f"summary.verdict={verdict or '<缺失>'}（须 PASS）"]
    receipt_status = str(summary.get("receipt_status", "")).lower()
    closure_status = str(summary.get("closure_status", "")).lower()
    if receipt_status != "passed" or closure_status != "closed":
        return False, [
            f"formal closure 未完成（receipt_status={receipt_status or '<缺失>'}, "
            f"closure_status={closure_status or '<缺失>'}）"
        ]
    return True, []


def phase_was_reached(feature_root: Path, phase: str) -> bool:
    """该阶段是否真的执行过——判据是**有没有 reports 之外的产物**。

    只有 `reports/` 说明这个阶段只被 harness 空跑过（那正是缺陷 2 留下的痕迹：
    为没执行过的阶段跑 harness，产出一份 FAIL summary）。
    对这种阶段再跑一次 harness，得到的 FAIL 不含任何信息——它只说明「没跑过」，
    而这件事本来就知道；代价却是污染 framework 的全局阶段槽。
    """
    root = feature_root / phase
    if not root.is_dir():
        return False
    return any(p.name != "reports" for p in root.iterdir())


def resume_prompt(feature: str, start_phase: str, end_phase: str) -> str:
    """续跑的起手指令。

    **不能复用「执行 /story init …」那句**——上游已经跑完并闭环，再说一遍
    只会让模型重跑一遍已完成的阶段，既浪费又会把已闭环的产物覆盖掉。
    """
    tail = (f"一路走到 {end_phase} 阶段闭环为止"
            if start_phase != end_phase else f"完成 {start_phase} 阶段并闭环")
    return (
        f"需求 {feature} 的上游阶段已完成并通过闭环判定，产物都在 "
        f"doc/features/{feature}/ 下。现在从 **{start_phase} 阶段**继续，"
        f"按该阶段 Skill 的规则产出物料并通过它自己的门禁与闭环判定，{tail}。\n\n"
        "执行要求：\n"
        "- 不要重跑已完成的上游阶段，直接读它们的产物作为输入；\n"
        "- 各确认关卡与阶段推进按你的判断取默认/推荐选项，无需逐一找我确认；\n"
        "- 不修改 story 技能本身（doc/extensions/）、不修改 framework/。\n\n"
        "结束时在最终回复中总结执行过程中遇到的规则、脚本或上下文问题。"
    )


def continuation_reply(feature: str, *, artifacts_done: bool, next_phase: str | None) -> str:
    """续话文案——按**卡在哪一层**分流。

    一句通用回话应付不了两种关卡。实测教训：spec 闭环后模型给的推荐链路是
    「评审 → 归档」，「进 plan」被排在其后并注明"建议先完成评审与归档"。
    驱动器回"按你推荐的选项继续"，模型照办执行了归档、宣布"全链已交付"，
    此后空转 5 次——`plan/` 目录从未建立。

    材料关卡要的是"按推荐走"（那里的推荐项就是「进入 /spec」）；
    **阶段边界要的是指名道姓的推进指令**。
    """
    if not artifacts_done or not next_phase:
        return GATE_REPLY
    return (
        f"上游阶段已闭环，现在执行 **{next_phase} 阶段**：按该阶段 Skill 的规则产出物料，"
        f"跑它自己的 harness 与 verifier，填完成回执，直到 {next_phase} 阶段闭环。\n"
        "评审与归档不是现在要做的事，先把阶段流水线走完。\n"
        "各确认关卡按你的判断取默认/推荐选项，不用再问我；每个决策照常写明依据。"
    )


def next_unclosed_phase(feature: str, end_phase: str) -> str | None:
    """目标之前第一个未闭环的阶段——推进指令要指名它，不能笼统说「继续」。

    判据与前置校验一致，都用 `phase_evidence_complete`（四件凭证 + summary formal closure）而不是
    `check-receipt` 的退出码：后者还比对 summary 的 commit sha 与当前 HEAD，
    测试期间只要有人提交，已闭环的阶段就会被重新算成「未闭环」，
    于是驱动器会一遍遍指挥模型回去重跑早就做完的阶段。
    """
    for phase in PHASE_ORDER[:phase_index(end_phase) + 1]:
        ok, _ = phase_evidence_complete(feature, phase)
        if not ok:
            return phase
    return None


# story 侧终点：归档送审 → 评审人表态 → `/story review` 回流处置。
# 它不在 framework 阶段链上（PHASE_ORDER 是 framework 的），却在 spec 闭环**之后**——
# 用 end_phase=spec 跑，驱动器在三产物齐备时就停了，续不到回流那一步。
STORY_REVIEW = "story-review"


def phase_index(phase: str) -> int:
    if phase == STORY_REVIEW:
        return 0                         # 走 spec 那条产物判据，再叠回流凭证
    try:
        return PHASE_ORDER.index(phase)
    except ValueError:
        raise SystemExit(
            f"[runner] 未知 end_phase「{phase}」，"
            f"可用：{' / '.join((*PHASE_ORDER, STORY_REVIEW))}") from None


# 注：曾用 `check-receipt.ts` 的退出码判闭环（那是 framework 自己的判据，不自造，
# 本来更正确）。但它额外比对 summary.source_commit_sha 与当前 HEAD——这对
# **继续开发**是对的（代码变了旧结论可能不成立），对**跑测试**却是错的：
# 测试期间只要有人提交，已闭环的阶段就会被重新算成未闭环，驱动器会一遍遍
# 指挥模型回去重跑早已做完的阶段。改用 `phase_evidence_complete` 读取已定稿的闭环事实。


def target_reached(feature: str, end_phase: str) -> bool:
    """跑到目标阶段了没有——续话与否只看它。

    Story 本身没有 framework receipt；但 end_phase=spec 表示 spec 必须完成四件套闭环，
    不能在三份阅读产物刚出现时提前停下。
    """
    if not artifacts_ready(feature):
        return False
    if end_phase == STORY_REVIEW:
        # 回流的凭证是处置台账：评审意见逐条有了去向，这一趟才算走完。
        return (REPO_ROOT / FEATURES_DIR / feature / "AR" / "review-disposition.json").is_file()
    ok, _ = phase_evidence_complete(feature, end_phase)
    return ok


def closure_facts(feature: str, start_phase: str, end_phase: str) -> dict:
    """本轮的闭环事实——**只报事实，不下结论**。

    「这一轮该不该结束」由宿主判断：他要同时看见「目标阶段的凭证齐没齐」和
    「模型嘴上说了什么」。装置把前者算清楚交出去，后者随 `awaiting_prompt` 走；
    **装置不据模型的散文改阶段、也不据它自动收工**——那又回到了机械判定。

    `beyond_target` 是把「模型说要进 plan」落成事实的那一半：它嘴上说时这里是空的，
    它真建了下一阶段的产物时才非空。两者摆在一起，宿主才判得准。
    """
    ok, missing = (True, []) if end_phase == STORY_REVIEW \
        else phase_evidence_complete(feature, end_phase)
    feature_root = REPO_ROOT / FEATURES_DIR / feature
    beyond = [phase for phase in PHASE_ORDER[phase_index(end_phase) + 1:]
              if phase_was_reached(feature_root, phase)]
    return {
        "target_phase": end_phase,
        "target_closed": target_reached(feature, end_phase),
        "target_missing": [] if ok else list(missing),
        "artifacts_ready": artifacts_ready(feature),
        "next_unclosed_phase": next_unclosed_phase(feature, end_phase),
        "beyond_target_evidence": beyond,
        "applicable_phases": list(applicable_phases(start_phase, end_phase)),
    }


def publish_closure(out_dir: Path, state: dict, feature: str,
                    start_phase: str, end_phase: str) -> dict:
    """把闭环事实刷进 state，让 poll 期间的宿主看得到（此前只在终态算一次）。"""
    facts = closure_facts(feature, start_phase, end_phase)
    state["closure"] = facts
    refresh_worker_lease(out_dir, state)
    return facts


#: 一次运行为什么停在这里 → 记成什么终态、退出码是几。
#:
#: 上一版把「模型真没做完」「没人回话超时」「CLI 没回 session id」统统记成
#: `target_not_reached`，事后完全分不出来——而其中两种压根不是被测对象的账。
#: 退出码表达的是「**这次运行有没有装置或 CLI 层面的失败**」：宿主判定收工是
#: 正常收场（0），哪怕目标没闭环——目标闭没闭环由 `target_reached` 与
#: `target_missing` 单独说，评测看那两个。
TERMINAL_BY_STOP_REASON = {
    "target_reached": ("finished", 0),
    "cli_cannot_continue": ("cli_failed", 1),
    "no_session_id": ("cli_session_lost", 2),
}


def terminal_status_for(execution_status: str, stop_reason: str | None,
                        reached: bool) -> tuple[str, int]:
    """终态与退出码的唯一出处——纯函数，好打表。"""
    if stop_reason == "host_concluded":
        return ("finished", 0) if reached else ("concluded_by_host", 0)
    if stop_reason in TERMINAL_BY_STOP_REASON:
        status, code = TERMINAL_BY_STOP_REASON[stop_reason]
        if stop_reason == "target_reached" and not reached:
            return "target_not_reached", 1
        return status, code
    if execution_status != "finished":
        return execution_status, 1
    return ("finished", 0) if reached else ("target_not_reached", 1)


def applicable_phases(start_phase: str, end_phase: str) -> tuple[str, ...]:
    """本轮真正负责的阶段；未进入范围的 coding/review 不产生“伪失败”。"""
    end_idx = phase_index(end_phase)
    if start_phase == "story":
        return ("story", *PHASE_ORDER[:end_idx + 1])
    start_idx = phase_index(start_phase)
    return PHASE_ORDER[start_idx:end_idx + 1]


def expected_gate_names(start_phase: str, end_phase: str) -> tuple[str, ...]:
    """由阶段区间正向派生 gate，避免用例结束后再拿无关阶段补跑。"""
    names: list[str] = []
    if start_phase == "story":
        names.append("post_check")
        if CFG.get("gates", {}).get("story_build"):
            names.append("story_build_check")
    names.extend(f"harness_{phase}" for phase in applicable_phases(start_phase, end_phase)
                 if phase != "story")
    if start_phase != "story":
        names.append("upstream_fingerprint")
    return tuple(names)


def compute_upstream_fingerprint(feature: str, start_phase: str) -> dict[str, Any] | None:
    """只指纹化续跑所依赖的上游产物，不把本轮新增下游文件算进漂移。"""
    if start_phase == "story":
        return None
    start_idx = phase_index(start_phase)
    feature_root = REPO_ROOT / FEATURES_DIR / feature
    roots = [feature_root / name for name in ("AR", "RR", "SR", "inbox", "ux-reference")]
    roots.extend(feature_root / p for p in PHASE_ORDER[:start_idx])
    # 部分阶段真源位于 feature 根而非 phase 子目录：acceptance 属 spec，
    # contracts/use-cases 属 plan。next.json 与 context/facts.md 会被下游合法推进/追加，
    # 不应纳入“不漂移”判据。
    if start_idx >= PHASE_ORDER.index("plan"):
        roots.append(feature_root / "acceptance.yaml")
    if start_idx >= PHASE_ORDER.index("coding"):
        roots.extend(feature_root / name for name in ("contracts.yaml", "use-cases.yaml"))
    digest = hashlib.sha256()
    files = 0
    for base in roots:
        if base.is_file():
            candidates = [base]
        elif base.is_dir():
            candidates = [p for p in base.rglob("*") if p.is_file()]
        else:
            continue
        for path in sorted(candidates, key=lambda p: p.as_posix()):
            rel = path.relative_to(feature_root).as_posix()
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
            files += 1
    return {"algo": "sha256", "digest": digest.hexdigest(), "file_count": files,
            "roots": [p.relative_to(feature_root).as_posix() for p in roots]}


def _phase_reached(feature_root: Path, phase: str) -> bool:
    if phase == "story":
        return all((feature_root / rel).is_file() for rel in ("AR/story.md", "AR/review.md"))
    return phase_was_reached(feature_root, phase)


def build_phase_results(feature: str, start_phase: str, end_phase: str,
                        gates: dict[str, str]) -> dict[str, dict[str, Any]]:
    """建立每个 phase 的执行、门禁与 formal closure 记录。"""
    feature_root = REPO_ROOT / FEATURES_DIR / feature
    output: dict[str, dict[str, Any]] = {}
    for phase in applicable_phases(start_phase, end_phase):
        reached = _phase_reached(feature_root, phase)
        if phase == "story":
            gate_names = tuple(name for name in
                               ("post_check", "story_build_check")
                               if name in gates)
        else:
            gate_names = (f"harness_{phase}",) if f"harness_{phase}" in gates else ()
        phase_gates = {name: gates[name] for name in gate_names}
        if phase == "story":
            closure, missing = "not_applicable", []
        elif reached:
            closed, missing = phase_evidence_complete(feature, phase)
            closure = "closed" if closed else "open"
        else:
            closure, missing = "not_reached", []
        output[phase] = {
            "phase": phase,
            "applicable": True,
            "execution_status": "completed" if reached else "not_reached",
            "closure_status": closure,
            "closure_missing": missing,
            "gates": phase_gates,
        }
    return output


def publish_phase_results(out_dir: Path,
                          phase_results: dict[str, dict[str, Any]]) -> dict[str, str]:
    """每轮每阶段只发布一次；相同内容可重入，不允许后续 stop 改写。"""
    published: dict[str, str] = {}
    for phase, payload in phase_results.items():
        path = out_dir / "phase-results" / f"{phase}.json"
        encoded = json.dumps(payload, ensure_ascii=False, indent=2)
        if path.is_file():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != payload:
                raise RuntimeError(f"阶段结果已发布，拒绝覆盖: {path}")
        else:
            _atomic_write(path, encoded)
        published[phase] = str(path.relative_to(out_dir))
    return published


def artifacts_ready(feature: str) -> bool:
    """三份交付产物是否齐备——续话与否只看它，不看菜单文本（格式一变就失效）。"""
    root = REPO_ROOT / FEATURES_DIR / feature
    return all((root / rel).is_file() for rel in
               ("spec/spec.md", "AR/story.md", "AR/review.md"))


def _rmtree_force(path: Path) -> None:
    """删审计目录时先摘只读位再重试。

    审计目录是 harness 自己的产物，清得掉是前提。但 opencode 会在里面建一个 git 快照库，
    而 git 的 object 文件在 Windows 上是**只读**的——`rmtree` 一碰就 PermissionError，
    于是同一用例的第二次 `start` 必然失败，还会被报成「上一轮 CLI/worker 未回收」，
    把人引去查根本不存在的残留进程。只读位是文件属性，不是占用，摘掉即可。
    """
    def clear_readonly(func, target, _exc):
        os.chmod(target, 0o600)
        func(target)

    shutil.rmtree(path, onexc=clear_readonly)


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    if sys.platform == "win32":
        # tasklist 在受限桌面会返回 Access denied，即使 worker 仍活着；
        # 交互回复和停止不能把这种诊断失败误判成 worker 已退出。
        access = 0x1000 | 0x0400  # QUERY_LIMITED_INFORMATION | QUERY_INFORMATION
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(access, False, int(pid))
        if handle:
            exit_code = ctypes.c_ulong()
            try:
                if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return exit_code.value == 259  # STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        try:
            os.kill(int(pid), 0)
            return True
        except PermissionError:
            return True
        except (OSError, ProcessLookupError):
            return False
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def _terminate_process_tree(pid: int | None, *, force: bool) -> str:
    """向 worker 的整个进程组发终止信号，返回可审计的动作说明。"""
    if not pid or not _pid_alive(pid):
        return "already_exited"
    if sys.platform == "win32":
        command = ["taskkill", "/PID", str(pid), "/T"]
        if force:
            command.append("/F")
        completed = subprocess.run(command, capture_output=True, text=True, errors="replace")
        if completed.returncode != 0 and _pid_alive(pid):
            raise RuntimeError((completed.stderr or completed.stdout or "taskkill 失败").strip())
        return "force_killed" if force else "terminated"
    process_group = os.getpgid(int(pid))
    os.killpg(process_group, signal.SIGKILL if force else signal.SIGTERM)
    return "force_killed" if force else "terminated"


def _atomic_write(path: Path, text: str) -> None:
    """原子发布：绝不原地覆盖；Windows 共享冲突做有限次短重试。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.{os.getpid()}.tmp"
    for attempt in range(5):
        try:
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.2)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass


def write_state(out_dir: Path, state: dict) -> None:
    state = dict(state)
    state["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _atomic_write(out_dir / "state.json", json.dumps(state, ensure_ascii=False, indent=2))


def read_state(out_dir: Path) -> dict:
    path = out_dir / "state.json"
    for attempt in range(4):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError):
            if attempt == 3:
                return {}
            time.sleep(0.15)
    return {}


def _clock_text(epoch: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(epoch))


def refresh_worker_lease(out_dir: Path, state: dict, *, force: bool = False,
                         event: str | None = None, phase: str | None = None,
                         now: float | None = None) -> bool:
    """由 worker 续租；控制端只读租约，不替 worker 制造“仍活着”的假象。"""
    current = time.time() if now is None else float(now)
    if event:
        state["last_event"] = {"name": event, "at": _clock_text(current)}
    if phase:
        # `phase` 是**驱动器要去哪**，不是**模型到了哪**——三个调用点传的分别是起跑阶段、
        # 下一个未闭环阶段、以及 `end_phase`（目标）。它曾被无条件写进
        # current_phase / highest_phase_reached，于是「准备跑 plan 的门禁」被记成「到达了
        # plan」：实测两个 Case 就这样在没有任何 plan 产物时被报成到达 plan。
        # 现在它只作**意图留痕**，阶段状态一律由 derive_phase_state 从 framework 状态与
        # 真实阶段产物推导——目标阶段、runner 提示、准备执行 gate、模型口头宣告都不算数。
        state["phase_intent"] = {"phase": phase, "event": event, "at": _clock_text(current)}
    state.update(derive_phase_state(REPO_ROOT, str(state.get("feature") or ""), state,
                                    observed_at=_clock_text(current)))
    previous = float(state.get("heartbeat_epoch") or 0)
    due = force or current - previous >= HEARTBEAT_INTERVAL_SEC
    if due:
        state.update(
            heartbeat_at=_clock_text(current),
            heartbeat_epoch=current,
            lease_expires_at=_clock_text(current + WORKER_LEASE_SEC),
            lease_expires_epoch=current + WORKER_LEASE_SEC,
        )
    if due or event or phase:
        write_state(out_dir, state)
        return True
    return False


def reconcile_worker_state(out_dir: Path, state: dict | None = None, *,
                           now: float | None = None, reap_cli: bool = True) -> dict:
    """把“死 worker + 过期租约”收敛成明确终态，并尽力回收残留 CLI run。"""
    current = time.time() if now is None else float(now)
    state = dict(state or read_state(out_dir))
    status = state.get("status")
    if not state or status in TERMINAL_STATUS or status not in ACTIVE_STATUS:
        return state
    # stopping 是控制端正在收敛的短暂状态；由 cmd_stop 发布 stopped/stop_failed，
    # 不能被并发 status/poll 抢先改写为 worker_lost。
    if status == "stopping" or _pid_alive(state.get("pid")):
        return state
    lease_expires = float(state.get("lease_expires_epoch") or 0)
    if current < lease_expires:
        return state

    state.update(
        status="worker_lost",
        execution_status="worker_lost",
        worker_lost_at=_clock_text(current),
        finished_at=_clock_text(current),
        previous_status=status,
        recovery_advice=(
            "worker 已退出且租约过期；先检查 worker.log/last_event。重新执行 start 会先回收"
            "残留 CLI run，再从用例声明的 start_phase 起跑。"
        ),
    )
    write_state(out_dir, state)

    run_id = state.get("cli_run_id")
    if reap_cli and run_id:
        try:
            CliClient(runtime_root=out_dir / "cli-runtime").stop(str(run_id), force=True)
            state["orphan_cleanup"] = "cli_run_stopped"
        except Exception as exc:  # noqa: BLE001 - 丢失 worker 后必须留下残留事实
            state["orphan_cleanup"] = "failed"
            state["orphan_cleanup_error"] = str(exc)
            state["residual_cli_run_id"] = run_id
        write_state(out_dir, state)
    state = settle_terminal_source(out_dir, state)
    if state.get("case") and state.get("run_id"):
        run_layout.publish_latest(
            OUT_ROOT, str(state["case"]), str(state["run_id"]), str(state["status"]))
    return state


def _load_case_definition(case_id: str) -> tuple[dict, Path, str]:
    case = yaml.safe_load(
        (HERE.parent / "cases" / case_id / "case.yaml").read_text(encoding="utf-8"))
    expected = Path(CFG["output"]["dir"])
    if not expected.is_absolute():
        expected = HOST_ROOT / expected
    expected = expected.resolve()
    if OUT_ROOT.resolve() != expected:
        raise SystemExit(f"[runner] 拒绝使用非标准输出目录: {OUT_ROOT.resolve()}")
    try:
        control = run_layout.control_dir(expected, case_id)
    except ValueError as exc:
        raise SystemExit(f"[runner] {exc}") from exc
    return case, control, str(case["ar"])


def _load_case(case_id: str, run_id: str | None = None) -> tuple[dict, Path, str]:
    """Load the case and resolve its explicit/active/latest immutable run."""
    case, _, feature = _load_case_definition(case_id)
    try:
        out_dir, _ = run_layout.resolve_run(OUT_ROOT, case_id, run_id)
    except (ValueError, FileNotFoundError) as exc:
        raise SystemExit(f"[runner] {exc}") from exc
    return case, out_dir, feature


def build_cli_env(out_dir: Path, cli_name: str | None = None) -> dict[str, str]:
    """为被测 CLI 建立每轮独立的可写运行目录。

    OpenCode 1.18 在 Windows 会把已存在的 XDG 子目录当作 mkdir 失败；将 config/data
    放入本轮刚创建的审计目录，可避免触碰用户目录并保留其只读 provider 配置作为 custom config。
    其他 CLI 不受影响。
    """
    env = {str(k): str(v) for k, v in (CFG.get("cli", {}).get("env", {}) or {}).items()}
    # Explicit in production; the fallback keeps this small helper directly
    # testable without constructing a full request.
    cli_name = cli_name or str(CFG.get("cli", {}).get("name")
                               or CLI_CONFIGURATIONS[0]["name"])
    # 宿主的临时目录按轮隔离：实测被测模型在共享的 %TEMP%/opencode 里翻到了
    # 历史轮次的会话数据（story-ar90006-docx、handoff-story），还据此推断流程走法。
    # TMP/TEMP 指向本轮审计目录下的私有 tmp，历史数据物理隔离；对所有 CLI 生效。
    private_tmp = out_dir / "cli-tmp"
    private_tmp.mkdir(parents=True, exist_ok=True)
    env["TMP"] = env["TEMP"] = str(private_tmp)
    if cli_name != "opencode":
        return env
    env["XDG_CONFIG_HOME"] = str(out_dir / "opencode-xdg-config")
    env["XDG_DATA_HOME"] = str(out_dir / "opencode-xdg-data")
    env["XDG_CACHE_HOME"] = str(out_dir / "opencode-xdg-cache")
    env["XDG_STATE_HOME"] = str(out_dir / "opencode-xdg-state")
    configured = os.environ.get("OPENCODE_CONFIG")
    provider_config = Path(configured) if configured else Path.home() / ".config" / "opencode" / "opencode.jsonc"
    # 不在 harness 进程预读用户配置（既会越权也会暴露内容）；仅把路径交给 OpenCode 子进程。
    env["OPENCODE_CONFIG"] = str(provider_config)
    return env


PHASE_SLOT = Path("framework") / "harness" / "state" / ".current-phase.json"


def snapshot_phase_slot() -> str | None:
    """快照 framework 的全局阶段槽（运行前）。

    那是 framework 的**全局单槽**，观测者会话与被测模型共用：被测模型跑 /spec 会写它，
    观测者会话的 Stop hook 会读它、盖上观测者自己的 session_id，于是把被测模型的阶段
    误判成观测者的未闭环阶段并反复拦截。framework 是只读 vendored 目录，改不了那个 hook，
    只能由 harness 善后——运行前快照、终态还原。

    TEST.md 承诺了这个机制，但驱动器里一直没有实现；实测被拦过一次才发现。
    """
    slot = REPO_ROOT / PHASE_SLOT
    return slot.read_text(encoding="utf-8") if slot.is_file() else None


def restore_phase_slot(snapshot: str | None) -> str:
    """终态还原阶段槽。**只在终态做**——运行中删掉会破坏被测模型自己的流程。"""
    slot = REPO_ROOT / PHASE_SLOT
    if snapshot is None:
        if slot.is_file():
            slot.unlink()
            return "removed"
        return "absent"
    if slot.is_file() and slot.read_text(encoding="utf-8") == snapshot:
        return "unchanged"
    slot.parent.mkdir(parents=True, exist_ok=True)
    slot.write_text(snapshot, encoding="utf-8")
    return "restored"


def migrate_feature_history(feature: str, start_phase: str,
                            run_id: str | None = None) -> dict[str, Any]:
    """新链起跑前把同一 feature 的旧产物移出代码仓，并返回可审计记录。"""
    if not should_migrate_feature_history(start_phase):
        return {"status": "not_new_chain", "action": "none", "feature": feature}
    root = (REPO_ROOT / FEATURES_DIR).resolve()
    if root == REPO_ROOT or not root.is_relative_to(REPO_ROOT):
        raise SystemExit(f"[runner] 非法产物根，拒绝迁移: {root}")
    if root.name in {"", "doc", "src", "framework"}:
        raise SystemExit(f"[runner] 产物根指向了非产物目录，拒绝迁移: {root}")
    source = root / feature
    if source.resolve().parent != root:
        raise SystemExit(f"[runner] feature 越出产物根，拒绝迁移: {feature}")

    backup_root = FEATURE_HISTORY_ROOT.resolve()
    if backup_root == Path(backup_root.anchor) or backup_root == REPO_ROOT.resolve():
        raise SystemExit(f"[runner] 非法历史备份根，拒绝迁移: {backup_root}")
    if backup_root.is_relative_to(REPO_ROOT.resolve()) \
            and not backup_root.is_relative_to(OUT_ROOT.resolve()):
        raise SystemExit(
            f"[runner] 历史备份根必须位于代码仓外，或位于本轮输出根内: {backup_root}")
    if not source.exists():
        return {
            "status": "no_existing_feature", "action": "none", "feature": feature,
            "source": str(source), "backup_root": str(backup_root),
        }
    if not source.is_dir() or source.is_symlink():
        raise SystemExit(f"[runner] feature 历史不是普通目录，拒绝迁移: {source}")

    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime(FEATURE_HISTORY_TIMESTAMP_FORMAT)
    target = backup_root / f"{feature}-{stamp}"
    if target.exists():
        suffix = ''.join(ch for ch in str(run_id or '') if ch.isalnum() or ch in {'-', '_'})
        target = backup_root / f"{feature}-{stamp}-{suffix or '2'}"
        counter = 2
        while target.exists():
            counter += 1
            target = backup_root / f"{feature}-{stamp}-{suffix or 'run'}-{counter}"
    if target.resolve().parent != backup_root:
        raise SystemExit(f"[runner] 历史目标越出备份根，拒绝迁移: {target}")
    shutil.move(str(source), str(target))
    return {
        "status": "moved", "action": "move", "feature": feature,
        "source": str(source), "target": str(target), "moved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


SOURCE_TRANSACTION_DIR = "source-transaction"


def source_transaction_root(out_dir: Path) -> Path:
    configured = os.environ.get("STORY_SOURCE_TRANSACTION_ROOT", "").strip()
    if configured:
        return Path(configured).resolve()
    return out_dir / SOURCE_TRANSACTION_DIR


def interval_contains_coding(start_phase: str, end_phase: str) -> bool:
    return "coding" in applicable_phases(start_phase, end_phase)


def _git_bytes(args: list[str], *, input_bytes: bytes | None = None,
               check: bool = True) -> subprocess.CompletedProcess:
    completed = subprocess.run(
        ["git", "-c", "safe.directory=*", *args], cwd=str(REPO_ROOT), input=input_bytes,
        capture_output=True, text=False)
    if check and completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or b"").decode("utf-8", "replace").strip()
        raise RuntimeError(f"git {' '.join(args)} 失败: {detail}")
    return completed


def _nul_paths(payload: bytes) -> list[str]:
    return [part.decode("utf-8", "surrogateescape")
            for part in payload.split(b"\0") if part]


def _source_roots() -> list[str]:
    roots = [name for name in SOURCE_DIRS if (REPO_ROOT / name).is_dir()]
    if not roots:
        raise RuntimeError("SOURCE_DIRS 中没有存在的源码目录")
    return roots


def _source_target(rel: str, roots: list[str]) -> Path:
    candidate = (REPO_ROOT / rel).resolve()
    allowed = [(REPO_ROOT / root).resolve() for root in roots]
    if not any(candidate == root or candidate.is_relative_to(root) for root in allowed):
        raise RuntimeError(f"源码事务路径越界: {rel}")
    return candidate


def _tracked_source_paths(roots: list[str]) -> list[str]:
    index_paths = _nul_paths(_git_bytes(["ls-files", "-z", "--", *roots]).stdout)
    head = _git_bytes(["ls-tree", "-r", "--name-only", "-z", "HEAD", "--", *roots]).stdout
    return sorted(set(index_paths) | set(_nul_paths(head)))


def _untracked_source_paths(roots: list[str]) -> list[str]:
    payload = _git_bytes(
        ["ls-files", "-z", "--others", "--exclude-standard", "--", *roots]).stdout
    return sorted(set(_nul_paths(payload)))


def _remove_source_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def _snapshot_file(path: Path, destination: Path) -> dict[str, Any]:
    if path.is_symlink():
        return {"kind": "symlink", "target": os.readlink(path)}
    if path.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        return {"kind": "file", "size": path.stat().st_size}
    return {"kind": "absent"}


def _restore_snapshot_item(record: dict[str, Any], snapshot_root: Path,
                           roots: list[str]) -> None:
    rel = str(record["path"])
    target = _source_target(rel, roots)
    kind = record["kind"]
    if kind == "absent":
        _remove_source_path(target)
        return
    _remove_source_path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if kind == "symlink":
        os.symlink(str(record["target"]), target)
    elif kind == "file":
        shutil.copy2(snapshot_root / rel, target)
    else:
        raise RuntimeError(f"未知快照类型: {kind}")


def source_state_fingerprint(roots: list[str] | None = None) -> dict[str, Any]:
    """Fingerprint Git-visible source state, including index and exact file bytes."""
    roots = roots or _source_roots()
    tracked = _tracked_source_paths(roots)
    untracked = _untracked_source_paths(roots)
    status = _git_bytes(
        ["status", "--porcelain=v1", "-z", "--untracked-files=all", "--", *roots]).stdout
    cached = _git_bytes(["diff", "--binary", "--cached", "HEAD", "--", *roots]).stdout
    digest = hashlib.sha256()
    digest.update(status)
    digest.update(b"\0INDEX\0")
    digest.update(cached)
    file_count = 0
    for rel in sorted(set(tracked) | set(untracked)):
        target = _source_target(rel, roots)
        digest.update(b"\0PATH\0" + rel.encode("utf-8", "surrogateescape"))
        if target.is_symlink():
            digest.update(b"\0LINK\0" + os.readlink(target).encode("utf-8", "surrogateescape"))
        elif target.is_file():
            digest.update(b"\0FILE\0" + hashlib.sha256(target.read_bytes()).digest())
        else:
            digest.update(b"\0ABSENT\0")
        file_count += 1
    return {
        "algo": "sha256",
        "digest": digest.hexdigest(),
        "file_count": file_count,
        "tracked_count": len(tracked),
        "untracked_count": len(untracked),
        "status_sha256": hashlib.sha256(status).hexdigest(),
        "index_sha256": hashlib.sha256(cached).hexdigest(),
    }


def _write_source_manifest(tx_root: Path, payload: dict[str, Any]) -> None:
    _atomic_write(tx_root / "manifest.json", json.dumps(payload, ensure_ascii=False, indent=2))


def begin_source_transaction(out_dir: Path) -> dict[str, Any]:
    """Snapshot the user's source state, then expose a clean HEAD baseline to Coding."""
    roots = _source_roots()
    tx_root = source_transaction_root(out_dir)
    if tx_root.exists():
        raise RuntimeError(f"源码事务目录已存在，拒绝覆盖: {tx_root}")
    tracked = _tracked_source_paths(roots)
    untracked = _untracked_source_paths(roots)
    tracked_records = []
    untracked_records = []
    for rel in tracked:
        record = {"path": rel, **_snapshot_file(
            _source_target(rel, roots), tx_root / "pre-run" / "tracked" / rel)}
        tracked_records.append(record)
    for rel in untracked:
        record = {"path": rel, **_snapshot_file(
            _source_target(rel, roots), tx_root / "pre-run" / "untracked" / rel)}
        untracked_records.append(record)
    index_patch = _git_bytes(["diff", "--binary", "--cached", "HEAD", "--", *roots]).stdout
    (tx_root / "pre-run").mkdir(parents=True, exist_ok=True)
    (tx_root / "pre-run" / "index.patch").write_bytes(index_patch)
    manifest = {
        "schema_version": 1,
        "status": "snapshotted",
        "source_dirs": roots,
        "pre_fingerprint": source_state_fingerprint(roots),
        "tracked": tracked_records,
        "untracked": untracked_records,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _write_source_manifest(tx_root, manifest)
    try:
        _git_bytes(["restore", "--source=HEAD", "--staged", "--worktree", "--", *roots])
        for rel in _untracked_source_paths(roots):
            _remove_source_path(_source_target(rel, roots))
        baseline_status = _git_bytes(
            ["status", "--porcelain=v1", "-z", "--untracked-files=all", "--", *roots]).stdout
        if baseline_status:
            raise RuntimeError("建立清洁源码基线后 Git 状态仍非空")
        manifest["status"] = "baseline_ready"
        manifest["baseline_fingerprint"] = source_state_fingerprint(roots)
        _write_source_manifest(tx_root, manifest)
        return manifest
    except Exception:
        # 基线创建也是事务的一部分；中途失败不能把用户改动留在半恢复态。
        restore_source_transaction(out_dir, archive=False)
        raise


def archive_source_evidence(out_dir: Path) -> dict[str, Any]:
    """Freeze Coding/Review's real diff before the source transaction is restored."""
    tx_root = source_transaction_root(out_dir)
    evidence_root = tx_root / "evidence"
    evidence_file = evidence_root / "evidence.json"
    if evidence_file.is_file():
        return json.loads(evidence_file.read_text(encoding="utf-8"))
    manifest = json.loads((tx_root / "manifest.json").read_text(encoding="utf-8"))
    roots = list(manifest["source_dirs"])
    evidence_root.mkdir(parents=True, exist_ok=True)
    status = _git_bytes(
        ["status", "--short", "--untracked-files=all", "--", *roots]).stdout
    patch = _git_bytes(["diff", "--binary", "HEAD", "--", *roots]).stdout
    name_status = _git_bytes(["diff", "--name-status", "HEAD", "--", *roots]).stdout
    (evidence_root / "source-status.txt").write_bytes(status)
    (evidence_root / "source-change.patch").write_bytes(patch)
    (evidence_root / "source-name-status.txt").write_bytes(name_status)
    changed = _nul_paths(_git_bytes(["diff", "--name-only", "-z", "HEAD", "--", *roots]).stdout)
    untracked = _untracked_source_paths(roots)
    copied = []
    for rel in sorted(set(changed) | set(untracked)):
        source = _source_target(rel, roots)
        if not source.is_file():
            continue
        destination = evidence_root / "files" / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(rel)
    evidence = {
        "schema_version": 1,
        "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "baseline_fingerprint": manifest.get("baseline_fingerprint"),
        "changed_fingerprint": source_state_fingerprint(roots),
        "changed_paths": sorted(set(changed) | set(untracked)),
        "copied_paths": copied,
        "patch": "evidence/source-change.patch",
        "status": "evidence/source-status.txt",
        "name_status": "evidence/source-name-status.txt",
        "phase_artifacts": ["artifact/coding", "artifact/review"],
    }
    _atomic_write(evidence_file, json.dumps(evidence, ensure_ascii=False, indent=2))
    return evidence


def restore_source_transaction(out_dir: Path, *, archive: bool = True) -> dict[str, Any]:
    """Restore the exact pre-run index/worktree state; safe to call more than once."""
    tx_root = source_transaction_root(out_dir)
    manifest_path = tx_root / "manifest.json"
    if not manifest_path.is_file():
        return {"status": "not_applicable"}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    roots = list(manifest["source_dirs"])
    restore_path = tx_root / "restore.json"
    if restore_path.is_file():
        previous = json.loads(restore_path.read_text(encoding="utf-8"))
        if previous.get("status") == "restored":
            current = source_state_fingerprint(roots)
            if current.get("digest") == manifest["pre_fingerprint"]["digest"]:
                return previous
    evidence = None
    errors: list[str] = []
    try:
        if archive:
            evidence = archive_source_evidence(out_dir)
        for rel in _untracked_source_paths(roots):
            _remove_source_path(_source_target(rel, roots))
        _git_bytes(["restore", "--source=HEAD", "--staged", "--worktree", "--", *roots])
        index_patch = (tx_root / "pre-run" / "index.patch").read_bytes()
        if index_patch:
            _git_bytes(["apply", "--cached", "--whitespace=nowarn", "-"],
                       input_bytes=index_patch)
        for record in manifest["tracked"]:
            _restore_snapshot_item(record, tx_root / "pre-run" / "tracked", roots)
        for record in manifest["untracked"]:
            _restore_snapshot_item(record, tx_root / "pre-run" / "untracked", roots)
        restored = source_state_fingerprint(roots)
        if restored["digest"] != manifest["pre_fingerprint"]["digest"]:
            raise RuntimeError(
                f"恢复指纹不一致: {restored['digest'][:16]} != "
                f"{manifest['pre_fingerprint']['digest'][:16]}")
        result = {
            "status": "restored",
            "restored_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "pre_fingerprint": manifest["pre_fingerprint"],
            "restored_fingerprint": restored,
            "evidence": evidence,
        }
    except Exception as exc:  # noqa: BLE001 - 恢复失败必须变成可审计终态
        errors.append(f"{type(exc).__name__}: {exc}")
        result = {
            "status": "source_restore_failed",
            "failed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "errors": errors,
            "snapshot": "pre-run/",
            "recovery": (
                f"保留 {tx_root} 的 manifest/index.patch/文件快照；"
                "停止后续测试，核对快照后人工恢复 SOURCE_DIRS。"
            ),
        }
    _atomic_write(restore_path, json.dumps(result, ensure_ascii=False, indent=2))
    return result


def finalize_source_transaction(out_dir: Path, *, archive: bool = True,
                                max_attempts: int = 2) -> dict[str, Any]:
    """单一终态收口：完成证据归档与恢复，瞬时失败在发布终态前重试。"""
    if max_attempts < 1:
        raise ValueError("max_attempts 必须大于 0")
    attempts = []
    final: dict[str, Any] = {"status": "not_applicable"}
    for number in range(1, max_attempts + 1):
        final = restore_source_transaction(out_dir, archive=archive)
        attempts.append({
            "attempt": number,
            "status": final.get("status"),
            "errors": final.get("errors", []),
        })
        if final.get("status") in {"restored", "not_applicable"}:
            break
    return {**final, "attempts": attempts}


def settle_terminal_source(out_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    """Restore a persisted source transaction after worker loss or an external stop."""
    if not (source_transaction_root(out_dir) / "manifest.json").is_file():
        return state
    restored = finalize_source_transaction(out_dir)
    state["source_transaction"] = {"required": True, "restore": restored}
    if restored.get("status") != "restored":
        state.update(status="source_restore_failed",
                     execution_status="source_restore_failed",
                     exit_code=2)
    write_state(out_dir, state)
    return state


def seed_case_workspace(case_id: str, feature: str) -> list[str]:
    """把用例自带的工作区材料铺进 feature 目录（历史迁移之后、被测 CLI 起跑之前）。

    有些输入不来自需求系统，而是人手工放进工作区的——PRD 未归档时人工补录的文档就是。
    这类材料必须由 harness 在**每次新链迁移之后**重新铺一次：历史产物先整体移出代码仓，
    本轮夹具再按原字节进入新的 feature 目录，起点清晰且可跨轮比较。

    不变量：`cases/<case-id>/workspace/` 子树 = 被测 CLI 起跑时 feature 目录的全部内容。
    没有这个目录的用例即从空目录起跑（既有用例的行为不变）。
    """
    src = HERE.parent / "cases" / case_id / "workspace"
    dest_root = (REPO_ROOT / FEATURES_DIR / feature).resolve()
    seeded = []
    if src.is_dir():
        for path in sorted(src.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(src)
            dest = (dest_root / rel).resolve()
            if not dest.is_relative_to(dest_root):      # 用例目录里的越界软链
                raise SystemExit(f"[runner] 用例材料越界，拒绝铺设: {rel}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
            seeded.append(rel.as_posix())
    # 声明为 `deliver: start` 的补料属于「人手上本来就有、起跑前已经放好」那一类，
    # 与 workspace 材料同时到位；其余的等模型开口要（`reply --deliver`）。
    for name in start_delivered_supplements(case_id):
        seeded.extend(f"inbox/{n}" for n in
                      deliver_supplements(case_id, feature, [name]))
    return seeded


def start_delivered_supplements(case_id: str) -> list[str]:
    """case.yaml 里声明为起跑时就投放的补料。"""
    path = HERE.parent / "cases" / case_id / "case.yaml"
    if not path.is_file():
        return []
    case = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [str(item["file"]).strip()
            for item in (case.get("supplements") or [])
            if isinstance(item, dict) and str(item.get("file") or "").strip()
            and str(item.get("deliver") or "on_request").strip() == "start"]


def _run_logged_gate(command: list[str], *, cwd: Path, log_path: Path,
                     shell: bool = False) -> tuple[subprocess.CompletedProcess | None, dict[str, Any]]:
    """统一记录 gate 的命令、输出、耗时和启动异常；不重试，不抹掉偶发。"""
    started = time.time()
    try:
        completed = subprocess.run(
            command, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
            errors="replace", shell=shell)
    except Exception as exc:  # noqa: BLE001 - 异常本身就是本轮门禁证据
        elapsed = time.time() - started
        log_path.write_text(f"gate launch exception: {type(exc).__name__}: {exc}\n", encoding="utf-8")
        return None, {
            "command": command,
            "cwd": str(cwd),
            "returncode": None,
            "elapsed_sec": round(elapsed, 3),
            "log": str(log_path),
            "exception": {"type": type(exc).__name__, "message": str(exc)},
        }
    log_path.write_text((completed.stdout or "") + (completed.stderr or ""), encoding="utf-8")
    return completed, _gate_diagnosis(
        completed, command=command, cwd=cwd, elapsed_sec=time.time() - started,
        log_path=log_path)


def run_phase_harness(feature: str, phase: str,
                      out_dir: Path) -> tuple[str, dict[str, Any]]:
    """跑 framework 自己的阶段 harness；只调用发布件，不修改 framework。

    story 那两个门禁（post_check / story-build）只认识 story/spec 的产物，
    对 plan 的 contracts.yaml、coding 的源码一无所知。真正判这些的是 framework 的
    `harness-runner.ts --phase <p>`，它按 workflow 的规则集跑。
    """
    command = ["npx", "ts-node", "harness-runner.ts", "--phase", phase,
               "--feature", feature]
    cwd = REPO_ROOT / "framework" / "harness"
    log_path = out_dir / f"gate_harness_{phase}.log"
    completed, diagnosis = _run_logged_gate(
        command, cwd=cwd, log_path=log_path, shell=(os.name == "nt"))
    return ("pass" if completed is not None and completed.returncode == 0 else "fail"), diagnosis


def _gate_diagnosis(cp: subprocess.CompletedProcess, *, command: list[str] | None = None,
                    cwd: Path | None = None, elapsed_sec: float = 0,
                    log_path: Path | None = None) -> dict:
    """门禁的执行事实：判定之外，还要留下「它是怎么退出的」。

    实测遇到过一次 fail 而日志 0 字节：产物没变、手工复跑稳定通过，
    但当时的退出码与 stderr 都没记，无从判断是产物问题还是执行本身出了岔。
    这里只记录不重试——重试会把偶发抹掉，下次照样无据可查。
    """
    return {
        "command": command or cp.args,
        "cwd": str(cwd or REPO_ROOT),
        "returncode": cp.returncode,
        "elapsed_sec": round(elapsed_sec, 3),
        "log": str(log_path) if log_path else None,
        "stdout_len": len(cp.stdout or ""),
        "stderr_len": len(cp.stderr or ""),
        "stdout_tail": (cp.stdout or "")[-2000:],
        "stderr_tail": (cp.stderr or "")[-2000:],
    }


def _run_story_gates(feature: str, out_dir: Path) -> dict[str, str]:
    """运行只属于 story→spec 新生成链路的两个门禁。绿 ≠ 语义达标。

    plan-only 不调用本函数，因而不会重复解释既有 Story。
    """
    post_check = REPO_ROOT / CFG["gates"]["post_check"]
    script = (
        "import {pathToFileURL} from 'node:url';"
        f"const m=await import(pathToFileURL({json.dumps(str(post_check))}).href);"
        "console.log(JSON.stringify(await m.default({phase:'spec',"
        f"feature:{json.dumps(feature)},projectRoot:{json.dumps(str(REPO_ROOT))}}})));")
    command = ["node", "--input-type=module", "-e", script]
    post_log = out_dir / "gate_post_check.log"
    r, post_diagnosis = _run_logged_gate(command, cwd=REPO_ROOT, log_path=post_log)
    gates = {
        "post_check": ("pass" if r is not None and r.returncode == 0
                       and '"ok":true' in (r.stdout or "") else "fail"),
    }
    diagnostics = {
        "post_check": post_diagnosis,
    }
    # story.md 的九项判据：章节合同、来源单元三态守恒、裁决与判定表核实、术语守恒、四红线。
    story_build = CFG["gates"].get("story_build")
    if story_build:
        build_command = ["node", str(REPO_ROOT / story_build), "check", "--feature", feature,
                         "--project-root", str(REPO_ROOT)]
        build_log = out_dir / "gate_story_build.log"
        r3, build_diagnosis = _run_logged_gate(
            build_command, cwd=REPO_ROOT, log_path=build_log)
        gates["story_build_check"] = (
            "pass" if r3 is not None and r3.returncode == 0 else "fail")
        diagnostics["story_build_check"] = build_diagnosis
    (out_dir / "gate_diagnostics.json").write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")
    return gates


def run_gates(feature: str, out_dir: Path, end_phase: str = "spec", *,
              start_phase: str = "story",
              upstream_fingerprint: dict[str, Any] | None = None) -> dict[str, str]:
    """只运行本轮阶段区间适用的 gate，并统一发布可追溯诊断。"""
    gates: dict[str, str] = {}
    diagnostics: dict[str, Any] = {}
    diagnostics_path = out_dir / "gate_diagnostics.json"

    if start_phase == "story":
        gates.update(_run_story_gates(feature, out_dir))
        try:
            diagnostics.update(json.loads(diagnostics_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            diagnostics["story_gates"] = {"status": "diagnostics_unavailable"}

    # 只为**本轮负责且实际到达过**的阶段跑 harness。没执行过的阶段跑出来的 FAIL
    # 只说明“没跑过”，还会污染 framework 的全局阶段槽。
    feature_root = REPO_ROOT / FEATURES_DIR / feature
    for phase in (p for p in applicable_phases(start_phase, end_phase) if p != "story"):
        if not phase_was_reached(feature_root, phase):
            gates[f"harness_{phase}"] = "skipped"
            diagnostics[f"harness_{phase}"] = {
                "status": "skipped", "reason": "阶段没有 reports/ 之外的真实产物"}
            continue
        gate_status, diagnosis = run_phase_harness(feature, phase, out_dir)
        gates[f"harness_{phase}"] = gate_status
        diagnostics[f"harness_{phase}"] = diagnosis

    if start_phase != "story":
        current = compute_upstream_fingerprint(feature, start_phase)
        unchanged = bool(upstream_fingerprint and current
                         and upstream_fingerprint.get("digest") == current.get("digest"))
        gates["upstream_fingerprint"] = "pass" if unchanged else "fail"
        diagnostics["upstream_fingerprint"] = {
            "before": upstream_fingerprint,
            "after": current,
            "reason": "上游产物未漂移" if unchanged else "续跑期间上游产物发生变化",
        }

    diagnostics_path.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")
    return gates


# ---------------------------------------------------------------------------


def foreground(case_id: str, *, prepared: bool, run_id: str | None = None,
               cli_config_id: str | None = None,
               start_phase_override: str | None = None,
               end_phase_override: str | None = None) -> int:
    if run_id:
        case, out_dir, feature = _load_case(case_id, run_id)
        resolved_run_id = run_id
    elif prepared:
        case, out_dir, feature = _load_case(case_id)
        pointer = run_layout.read_pointer(OUT_ROOT, case_id, "active")
        resolved_run_id = str(pointer["run_id"]) if pointer else out_dir.name
    else:
        case, _, feature = _load_case_definition(case_id)
        active = run_layout.read_pointer(OUT_ROOT, case_id, "active")
        if active:
            raise SystemExit(
                f"[runner] 用例 {case_id} 已有活动运行 {active['run_id']}，先 stop 再启动")
        out_dir, resolved_run_id = run_layout.create_run(OUT_ROOT, case_id)
        prepared = True
    # end_phase 缺省 spec、start_phase 缺省 story——既有用例一字不改，行为逐字节一致。
    end_phase = str(end_phase_override or case.get("end_phase") or "spec").strip()
    end_idx = phase_index(end_phase)
    start_phase = resolve_start_phase(case, start_phase_override)
    if start_phase != "story" and phase_index(start_phase) > end_idx:
        raise SystemExit(f"[runner] start_phase({start_phase}) 在 end_phase({end_phase}) 之后")
    # 阶段之间还有 phase.next_step / plan.ok_to_code 这类编号确认；自动模式沿用同一条
    # 回话即可（它说的是「按你推荐的选项继续」，对关卡与阶段推进同样成立），
    # 但要在报告里显式记下这轮有多少次是驱动器替人应答的。
    gate_reply = GATE_REPLY
    interactive = is_interactive(case)
    # 单次 run 的硬上限按目标阶段放宽：coding 要写码 + 逐文件 lint，90 分钟不够。
    out_dir.mkdir(parents=True, exist_ok=True)

    cli_config = select_cli(CLI_CONFIGURATIONS, cli_config_id)
    # 上一轮没被取走的回话属于上一轮：留着会在本轮第一个关卡被当成人的回答用掉。
    (out_dir / REPLY_FILE).unlink(missing_ok=True)
    feed = observe.LiveFeed(out_dir / "live.jsonl")
    runlog = observe.RunLog(out_dir / "runlog.md")
    state = {"case": case_id, "run_id": resolved_run_id,
             "feature": feature, "pid": os.getpid(), "status": "running",
             "started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "cli_run_id": None,
             "interactive": interactive, "requested_start_phase": start_phase,
             "requested_end_phase": end_phase,
             "cli_config_id": cli_config["id"]}
    refresh_worker_lease(out_dir, state, force=True, event="run_start",
                         phase=start_phase)
    feed.emit("run_start", case=case_id, feature=feature, interactive=interactive)

    result: dict[str, Any] = {"case": case_id, "run_id": resolved_run_id, "feature": feature,
                              "start": state["started_at"], "status": "running",
                              "execution_status": "running",
                              "cli_config": cli_config}
    # 全局阶段槽是观测者与被测模型共用的单槽：运行前快照，终态还原。
    # 不还原的话，被测模型（或本驱动器的门禁调用）留下的阶段会拦住观测者会话的 Stop hook。
    phase_slot_snapshot = snapshot_phase_slot()
    phase_slot_restored = False
    result["end_phase"] = end_phase
    result["start_phase"] = start_phase
    if should_migrate_feature_history(start_phase):
        result["feature_history"] = migrate_feature_history(feature, start_phase, resolved_run_id)
        feed.emit("feature_history_migrated", **result["feature_history"])
        result["workspace_seeded"] = seed_case_workspace(case_id, feature)
        if result["workspace_seeded"]:
            feed.emit("workspace_seeded", files=result["workspace_seeded"])
    else:
        # 续跑：上一轮的产物正是本轮的输入，迁移当前 feature 就等于白续。
        # 但要先确认前序阶段真的闭环——在半成品上跑下游，失败了也无法归因。
        prev = phase_before(start_phase)
        if prev and prev != "story":
            ok, missing = phase_evidence_complete(feature, prev)
            if not ok:
                raise SystemExit(
                    f"[runner] 拒绝从 {start_phase} 续跑：前序阶段 {prev} 的闭环凭证不齐"
                    f"（缺 {'、'.join(missing)}）。先让它闭环，或改回 start_phase: story 从头跑")
        feed.emit("resume_from", start_phase=start_phase, previous_closed=prev or "-")
        runlog.event("续跑", f"从 {start_phase} 阶段起跑，沿用既有产物（前序 {prev} 凭证齐备）")

    upstream_fingerprint = compute_upstream_fingerprint(feature, start_phase)
    if upstream_fingerprint:
        result["upstream_fingerprint"] = upstream_fingerprint
        feed.emit("upstream_fingerprint", digest=upstream_fingerprint["digest"][:16],
                  file_count=upstream_fingerprint["file_count"])

    runlog.header({"case": case_id, "feature": feature, "cli": cli_config["name"],
                   "model": cli_config["model"], "target": TARGET,
                   "start": result["start"]})
    client = CliClient(runtime_root=out_dir / "cli-runtime")
    t0 = time.time()
    # 正式多 Case 使用不含 .git 的隔离 workspace；其源码基线与差异由宿主
    # run_multi_case.py 的白名单快照负责，不能再调用主工程 Git 源码事务。
    isolated_workspace = os.environ.get("STORY_ISOLATED_WORKSPACE", "").strip() == "1"
    source_transaction_required = (
        interval_contains_coding(start_phase, end_phase) and not isolated_workspace
    )
    source_transaction_restored = False
    source_transaction_finalized = False
    result["source_transaction"] = {"required": source_transaction_required}

    try:
        if source_transaction_required:
            source_manifest = begin_source_transaction(out_dir)
            result["source_transaction"].update({
                "status": "baseline_ready",
                "source_dirs": source_manifest["source_dirs"],
                "pre_fingerprint": source_manifest["pre_fingerprint"],
                "baseline_fingerprint": source_manifest["baseline_fingerprint"],
            })
            state["source_transaction"] = "baseline_ready"
            refresh_worker_lease(
                out_dir, state, force=True, event="source_baseline_ready", phase=start_phase)
            feed.emit(
                "source_baseline_ready",
                digest=source_manifest["pre_fingerprint"]["digest"][:16],
                source_dirs=source_manifest["source_dirs"])
        with (out_dir / "events.jsonl").open("w", encoding="utf-8") as fh:
            request = CliRunRequest(
                cli=cli_config["name"], model=cli_config["model"],
                profile=cli_config["profile"],
                # 续跑不能复用用例的起手 prompt——那句「执行 /story init …」会让模型
                # 重跑一遍已完成并闭环的上游阶段。
                prompt=driver_prompt(
                    case["prompt"].strip() if start_phase == "story"
                    else resume_prompt(feature, start_phase, end_phase),
                    interactive),
                cwd=TARGET, soft_timeout_sec=NO_TIME_LIMIT, hard_timeout_sec=NO_TIME_LIMIT,
                stop_grace_sec=STOP_GRACE, env=build_cli_env(out_dir, cli_config["name"]),
                metadata={"tool": "story-skill-test",
                          "cli_config_id": cli_config["id"]})
            run: dict = {}
            turns = 0
            # 同一阶段连续续话了几次——只用于报告里的可读性，不作上限
            stuck_phase, stuck_turns = None, 0

            # story 是多轮交互流程：材料确认时会停下来等待补料、拆分或进入 spec。
            # 单轮驱动会把它卡死在那儿（产物一个不产），但那不是 skill 的缺陷——
            # 真实用户就在那儿回一句。所以驱动器自己回话，而不是逼 skill 别问。
            # 判据不看菜单文本（格式一变就失效），只看**产物是否齐备**；
            # 回话也不指定编号，让模型按它自己刚给出的推荐走。
            while True:
                turns += 1
                handle = client.start(request)
                state.update(cli_run_id=handle.run_id)
                phase_hint = ("story" if start_phase == "story" and not artifacts_ready(feature)
                              else (next_unclosed_phase(feature, end_phase) or end_phase))
                refresh_worker_lease(out_dir, state, force=True, event="cli_run_started",
                                     phase=phase_hint)
                feed.emit("cli_run_started", cli_run_id=handle.run_id, turn=turns)
                print(f"[live] run={handle.run_id} turn={turns} started",
                      file=sys.stderr, flush=True)

                cursor = 0
                # 本轮模型最后说的那段话。停下来等宿主时要把它一起交出去——
                # 宿主此前只拿得到「它停了」，得自己去 events.jsonl 尾部捞原话，
                # 一轮观测因此变成两轮。这里顺手记住，零额外 IO。
                last_text = ""
                try:
                    while True:
                        page = client.poll(handle.run_id, cursor=cursor, wait_sec=1,
                                           max_events=500, max_chars=200000)
                        cursor = page.next_cursor
                        for event in page.events:
                            fh.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
                            described = observe.describe(event)
                            if described:
                                runlog.event(*described)
                            if event.type == "text" and str(event.content or "").strip():
                                last_text = str(event.content)
                            if event.type in {"lifecycle", "error"}:
                                feed.emit("cli_" + event.type,
                                          content=observe.shorten(event.content, 300))
                            state["last_event"] = {
                                "name": f"cli_{event.type}",
                                "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                            }
                        fh.flush()
                        refresh_worker_lease(out_dir, state)
                        run = page.run
                        if run.get("status") in TERMINAL_CLI_STATUS and not page.has_more:
                            break
                except BaseException:
                    # 观察通道一旦失败，不允许目标进程继续在后台跑
                    try:
                        client.stop(handle.run_id, force=True)
                    except Exception:
                        pass
                    raise

                session_id = str(run.get("session_id") or "")
                refresh_worker_lease(out_dir, state, force=True, event="cli_run_finished")
                # 每回合把闭环事实刷进 state：宿主是靠它判定「本轮到此为止」的，
                # 只在终态算一次的话，poll 期间他什么也看不到。
                publish_closure(out_dir, state, feature, start_phase, end_phase)
                # 四条出口，每条各记一个 stop_reason——上一版三种情况共用
                # `target_not_reached` 一个桶，事后分不出是模型没做完、没人回话、
                # 还是 CLI 压根没回 session id。
                concluded = pop_conclude_request(out_dir)
                if concluded is not None:
                    result["stop_reason"] = "host_concluded"
                    result["conclude_reason"] = str(concluded.get("reason") or "")
                    runlog.event("宿主收工", result["conclude_reason"] or "（未写理由）")
                    feed.emit("host_concluded", turn=turns, reason=result["conclude_reason"])
                    break
                if target_reached(feature, end_phase):
                    result["stop_reason"] = "target_reached"
                    break
                if run.get("status") != "succeeded":
                    result["stop_reason"] = "cli_cannot_continue"
                    break
                if not session_id:
                    result["stop_reason"] = "no_session_id"
                    break
                # 人先说话：交互用例等真人回话；自动用例里也允许中途插一句
                # （观察者发现模型走偏时可以当场纠正，不必重跑）。
                gate_reply = pop_pending_reply(out_dir)
                if gate_reply:
                    feed.emit("human_reply", turn=turns, text=observe.shorten(gate_reply, 300))
                    runlog.event("人回话", gate_reply[:200])
                elif interactive:
                    gate_reply = wait_for_human_reply(
                        out_dir, feed, runlog, state, turn=turns, prompt=last_text)
                    if gate_reply is None:
                        # 等待期间宿主判了收工
                        result["stop_reason"] = "host_concluded"
                        runlog.event("宿主收工", "等待回话期间收到收工判定")
                        feed.emit("host_concluded", turn=turns)
                        break
                else:
                    # 卡在哪一层，就说哪一层的话：产物没齐是材料关卡（按推荐走即可），
                    # 产物齐了但阶段没闭环是阶段边界（必须指名下一个阶段——spec 的推荐链路
                    # 是「评审→归档」，笼统说「按推荐走」会让模型去归档然后宣布全链交付）。
                    done = artifacts_ready(feature)
                    nxt = next_unclosed_phase(feature, end_phase) if done else None
                    stuck_turns = stuck_turns + 1 if nxt == stuck_phase else 1
                    stuck_phase = nxt
                    gate_reply = continuation_reply(feature, artifacts_done=done, next_phase=nxt)
                    feed.emit("gate_reply", turn=turns,
                              reason=(f"阶段边界：推进到 {nxt}（同阶段第 {stuck_turns} 次）" if nxt
                                      else f"未达 {end_phase}，按推荐继续"))
                    runlog.event("续话", f"第 {turns + 1} 轮：{gate_reply[:80]}")
                request = replace(
                    request, prompt=driver_prompt(gate_reply, interactive),
                    session_id=session_id)
                state.update(status="running", awaiting_consumed_at=time.strftime("%Y-%m-%d %H:%M:%S"))
                refresh_worker_lease(out_dir, state, force=True, event="reply_consumed")
                feed.emit("reply_consumed", turn=turns)

            result["turns"] = turns

            cli_status = str(run.get("status", "failed"))
            result["session_id"] = run.get("session_id") or ""
            result["cli_status"] = cli_status
            # `timed_out` 本域已不可达（两个时限都传 0）。真出现说明**有人把时限
            # 重新引进来了**——那正是最该看见的时刻，所以出声而不是静默归类。
            if cli_status == "timed_out":
                feed.emit("unexpected_timeout",
                          note="本域不设运行时限，出现超时说明时限被重新引入")
                runlog.event("异常超时", "本域不设运行时限，请查 clis.json 与 run_case 的传参")
                run["failure_kind"] = run.get("failure_kind") or "unexpected_timeout"
            result["status"] = {"succeeded": "finished",
                                "stopped": "stopped"}.get(cli_status, "cli_failed")
            result["execution_status"] = result["status"]
            if result["status"] == "cli_failed":
                result["failure_kind"] = run.get("failure_kind")
                result["exit_code"] = run.get("exit_code")
        result["elapsed_sec"] = round(time.time() - t0, 1)
        result["target_reached"] = target_reached(feature, end_phase)
        result["closure"] = closure_facts(feature, start_phase, end_phase)
        next_phase = (PHASE_ORDER[end_idx + 1]
                      if end_phase != STORY_REVIEW and end_idx + 1 < len(PHASE_ORDER)
                      else None)
        result["pipeline"] = {
            "requested_start_phase": start_phase,
            "requested_end_phase": end_phase,
            "status": ("completed_at_requested_end" if result["target_reached"]
                       else "requested_end_not_reached"),
            "next_phase": next_phase,
            "next_phase_status": "not_started_by_scope" if next_phase else "not_applicable",
        }
        result["phase_scope"] = {
            "phases": list(applicable_phases(start_phase, end_phase)),
            "expected_gates": list(expected_gate_names(start_phase, end_phase)),
        }

        retryable_provider_failure = result.get("failure_kind") in {
            "auth_required", "content_policy_rejected",
        }
        refresh_worker_lease(out_dir, state, force=True, event="gates_started", phase=end_phase)
        if retryable_provider_failure:
            # The coordinator will recreate this Case from its immutable baseline.
            # Running business gates over a known partial product wastes time and
            # can obscure the provider failure that caused the retry.
            result["gates"] = {}
            result["gates_skipped_reason"] = "retryable_provider_failure"
            feed.emit("gates_skipped", reason=result["gates_skipped_reason"])
        else:
            result["gates"] = run_gates(
                feature, out_dir, end_phase, start_phase=start_phase,
                upstream_fingerprint=upstream_fingerprint)
        feed.emit("gates_done", **result["gates"])

        missing_gates = sorted(set(expected_gate_names(start_phase, end_phase))
                               - set(result["gates"]))
        result["gate_scope_complete"] = not missing_gates
        if missing_gates:
            result["missing_gates"] = missing_gates
        # `warn` 也算过：非凭证文件的合法漂移要出声，但不该判整轮失败。
        gates_pass = all(v in ("pass", "skipped", "warn") for v in result["gates"].values())
        result["phase_results"] = build_phase_results(
            feature, start_phase, end_phase, result["gates"])
        result["phase_result_files"] = publish_phase_results(out_dir, result["phase_results"])
        if result["execution_status"] == "finished":
            status, code = terminal_status_for(
                result["execution_status"], result.get("stop_reason"),
                result["target_reached"])
            result["status"] = result["execution_status"] = status
            result["exit_code"] = code
            # gate 判红是被测对象的账；gate **没跑**是装置自己漏了，两件事分开记。
            if missing_gates:
                result["status"] = result["execution_status"] = "harness_incomplete"
                result["exit_code"] = 2
            elif not gates_pass:
                result["status"] = result["execution_status"] = "gate_failed"
                result["exit_code"] = 1
        else:
            result["exit_code"] = result.get("exit_code") or 1
        feed.emit("execution_checks_done", status=result["execution_status"],
                  target_reached=result["target_reached"], gates=result["gates"])

        # 归档产物副本：下一条新链会把当前 feature 移到仓外；run 目录仍保留本轮不可变审计副本。
        src = REPO_ROOT / FEATURES_DIR / feature
        if src.is_dir():
            artifact = out_dir / "artifact"
            if artifact.exists():
                shutil.rmtree(artifact)
            shutil.copytree(src, artifact)

        # Review 与所有 gate 都已读完同一份成型 diff，现在恢复
        # 用户跑前的索引/工作树字节状态。
        if source_transaction_required:
            source_restore = finalize_source_transaction(out_dir)
            source_transaction_finalized = True
            result["source_transaction"]["restore"] = source_restore
            source_transaction_restored = source_restore.get("status") == "restored"
            feed.emit("source_transaction_finished", status=source_restore.get("status"))
            if not source_transaction_restored:
                result.update(
                    status="source_restore_failed",
                    execution_status="source_restore_failed",
                    exit_code=2,
                )
                result["pipeline"]["status"] = "invalid_source_restore"

        # 先还原 framework 全局阶段槽，再发布终态。
        try:
            result["phase_state"] = restore_phase_slot(phase_slot_snapshot)
            phase_slot_restored = True
            feed.emit("phase_state_restored", action=result["phase_state"])
        except OSError as exc:
            result["phase_state"] = f"restore_failed: {exc}"

        result["end"] = time.strftime("%Y-%m-%d %H:%M:%S")
        # 终态发布顺序：确定性产物全部就绪后，才把 state 置为终态
        print(json.dumps(result, ensure_ascii=False, indent=2))
        state.update(status=result["execution_status"], finished_at=result["end"],
                     gates=result.get("gates"),
                     gates_skipped_reason=result.get("gates_skipped_reason"),
                     exit_code=result.get("exit_code"),
                     failure_kind=result.get("failure_kind"),
                     target_reached=result.get("target_reached"),
                     pipeline=result.get("pipeline"),
                     source_transaction=result.get("source_transaction"),
                     phase_results=result.get("phase_results"),
                     phase_result_files=result.get("phase_result_files"),
                     last_event={"name": "run_end", "at": result["end"]})
        state.update(derive_phase_state(REPO_ROOT, feature, state,
                                        observed_at=result["end"]))
        write_state(out_dir, state)
        feed.emit("run_end", status=result["execution_status"],
                  exit_code=result.get("exit_code"))
        run_layout.publish_latest(
            OUT_ROOT, case_id, resolved_run_id, str(result["execution_status"]))
    finally:
        if source_transaction_required and not source_transaction_finalized:
            source_restore = finalize_source_transaction(out_dir)
            source_transaction_finalized = True
            result.setdefault("source_transaction", {"required": True})["restore"] = source_restore
            source_transaction_restored = source_restore.get("status") == "restored"
            if not source_transaction_restored:
                result.update(status="source_restore_failed",
                              execution_status="source_restore_failed",
                              exit_code=2)
                state.update(status="source_restore_failed",
                             execution_status="source_restore_failed",
                             source_transaction=result["source_transaction"],
                             finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))
                write_state(out_dir, state)
                run_layout.publish_latest(
                    OUT_ROOT, case_id, resolved_run_id, "source_restore_failed")
        # 全局阶段槽还原——放 finally 是因为 stop/timeout/异常同样会留下脏槽，
        # 而那个槽会拦住观测者会话的 Stop hook。只在终态做：运行中删掉会破坏
        # 被测模型自己的流程。
        if not phase_slot_restored:
            try:
                action = restore_phase_slot(phase_slot_snapshot)
                result["phase_state"] = action
                feed.emit("phase_state_restored", action=action)
            except OSError as exc:  # 还原失败不该掩盖测试结论，但要留痕
                result["phase_state"] = f"restore_failed: {exc}"
        runlog.footer({"status": result.get("status"), "elapsed_sec": result.get("elapsed_sec", ""),
                       "gates": result.get("gates", "")})
        runlog.close()

    return int(result.get("exit_code", 2))


# ---------------------------------------------------------------------------


def cmd_start(case_id: str, start_phase_override: str | None = None,
              end_phase_override: str | None = None,
              cli_config_id: str | None = None) -> int:
    """后台跑：为每次执行创建不可变 run-id 目录，然后立即返回。"""
    _, _, feature = _load_case_definition(case_id)
    cli_config = select_cli(CLI_CONFIGURATIONS, cli_config_id)
    if start_phase_override and start_phase_override not in {"story", *PHASE_ORDER}:
        raise SystemExit(f"[runner] 未知 start_phase「{start_phase_override}」")
    if end_phase_override:
        phase_index(end_phase_override)
    if start_phase_override and start_phase_override != "story" and end_phase_override:
        if phase_index(start_phase_override) > phase_index(end_phase_override):
            raise SystemExit(
                f"[runner] start_phase({start_phase_override}) 在 end_phase({end_phase_override}) 之后")
    active = run_layout.read_pointer(OUT_ROOT, case_id, "active")
    if active:
        active_dir, _ = run_layout.resolve_run(OUT_ROOT, case_id, str(active["run_id"]))
        previous = reconcile_worker_state(active_dir, read_state(active_dir))
        if previous.get("status") in TERMINAL_STATUS:
            run_layout.publish_latest(
                OUT_ROOT, case_id, str(active["run_id"]), str(previous["status"]))
        else:
            raise SystemExit(
                f"[runner] 拒绝并发启动：运行 {active['run_id']} "
                f"(pid={previous.get('pid')}, status={previous.get('status') or '<未知>'}) "
                "仍是活动指针。先 stop 或排查该 run。")
    out_dir, run_id = run_layout.create_run(OUT_ROOT, case_id)
    state = {"case": case_id, "run_id": run_id, "feature": feature, "pid": None,
             "status": "starting", "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
             "requested_start_phase": start_phase_override,
             "requested_end_phase": end_phase_override,
             "cli_config_id": cli_config["id"]}
    refresh_worker_lease(out_dir, state, force=True, event="worker_starting")

    argv = [sys.executable, str(HERE / "run_case.py"), case_id, "run", "--prepared",
            "--run-id", run_id, "--cli-config", cli_config["id"]]
    if start_phase_override:
        argv.extend(("--start-phase", start_phase_override))
    if end_phase_override:
        argv.extend(("--end-phase", end_phase_override))
    kwargs: dict[str, Any] = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP
                               | subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW}
                              if sys.platform == "win32" else {"start_new_session": True})
    try:
        with (out_dir / "worker.log").open("w", encoding="utf-8") as log:
            proc = subprocess.Popen(argv, cwd=str(REPO_ROOT), stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT, **kwargs)
    except OSError as exc:
        write_state(out_dir, {"case": case_id, "run_id": run_id,
                              "status": "worker_start_failed", "error": str(exc)})
        run_layout.publish_latest(OUT_ROOT, case_id, run_id, "worker_start_failed")
        print(json.dumps({"ok": False, "status": "worker_start_failed", "error": str(exc)},
                         ensure_ascii=False))
        return 1

    state = read_state(out_dir) or state
    if state.get("status") == "starting" and not state.get("pid"):
        state["pid"] = proc.pid
        refresh_worker_lease(out_dir, state, force=True, event="worker_spawned")

    deadline = time.time() + 30
    while time.time() < deadline:
        state = read_state(out_dir)
        if state.get("pid") or state.get("status") in TERMINAL_STATUS:
            break
        if proc.poll() is not None:
            state.update(status="worker_start_failed", finished_at=time.strftime("%Y-%m-%d %H:%M:%S"),
                         error=f"worker 启动后立即退出，exit={proc.returncode}")
            write_state(out_dir, state)
            break
        time.sleep(0.4)
    if state.get("status") in TERMINAL_STATUS:
        run_layout.publish_latest(OUT_ROOT, case_id, run_id, str(state["status"]))
    run_dir_text = (str(out_dir.relative_to(REPO_ROOT))
                    if out_dir.is_relative_to(REPO_ROOT) else str(out_dir))
    print(json.dumps({
        "ok": True, "case": case_id, "run_id": run_id,
        "run_dir": run_dir_text,
        "feature": feature, "worker_pid": proc.pid,
        "status": state.get("status", "starting"), "cli_config_id": cli_config["id"],
        "requested_start_phase": start_phase_override,
        "requested_end_phase": end_phase_override,
        "observation_interval_sec": OBSERVATION_INTERVAL_SEC,
        "poll": f"python test/story/scripts/run_case.py {case_id} poll "
                f"--cursor 0 --model-cursor 0 --wait-sec {OBSERVATION_INTERVAL_SEC}",
    }, ensure_ascii=False, indent=2))
    return 0


def next_poll_after_sec(status: str | None, has_more: bool,
                        changed: bool, deadline_reached: bool) -> int:
    """给观测者返回下一次拉取节奏；紧急状态和积压流不做节流。"""
    if has_more or status in TERMINAL_STATUS or status == "awaiting_reply":
        return 0
    # 静默长轮询已经完整等待了一个周期，可以立即续上下一次长轮询；
    # 若本次因事件/产物变化提前返回，则至少等满正式观测间隔再拉。
    if deadline_reached and not changed:
        return 0
    return OBSERVATION_INTERVAL_SEC


def cmd_poll(case_id: str, cursor: int, model_cursor: int, wait_sec: int, max_chars: int) -> int:
    """新事件 / 新推理 / 观察信号变化 / 终态 / 超时，任一即返回。

    `model` 流是**评价者读模型行为的通道**，占响应预算的大头。
    """
    _, out_dir, feature = _load_case(case_id)
    feature_root = REPO_ROOT / FEATURES_DIR / feature
    baseline = observe.snapshot(out_dir, feature_root)["revision"]
    deadline = time.time() + max(0, wait_sec)
    model_budget, feed_budget = int(max_chars * 0.8), max(2000, int(max_chars * 0.2))
    while True:
        events, next_cursor, feed_more = observe.read_feed(
            out_dir / "live.jsonl", cursor, feed_budget)
        model, next_model, model_more = observe.read_model(
            out_dir / "events.jsonl", model_cursor, model_budget)
        state = reconcile_worker_state(out_dir, read_state(out_dir))
        obs = observe.snapshot(out_dir, feature_root)
        awaiting = state.get("status") == "awaiting_reply"
        status = state.get("status")
        changed = bool(events or model or obs["revision"] != baseline)
        deadline_reached = time.time() >= deadline
        if (changed or status in TERMINAL_STATUS or awaiting or deadline_reached):
            has_more = feed_more or model_more
            payload = {
                "ok": True,
                "run": {
                    "status": status,
                    "cli_run_id": state.get("cli_run_id"),
                    "last_phase": state.get("last_phase"),
                    "current_phase": state.get("current_phase"),
                    "highest_phase_reached": state.get("highest_phase_reached"),
                    "phase_source": state.get("phase_source"),
                    "phase_observed_at": state.get("phase_observed_at"),
                    "spec_entered_at": state.get("spec_entered_at"),
                    "last_event": state.get("last_event"),
                    "heartbeat_at": state.get("heartbeat_at"),
                    "lease_expires_at": state.get("lease_expires_at"),
                    "pipeline": state.get("pipeline"),
                },
                "cursor": cursor, "next_cursor": next_cursor,
                "model_cursor": model_cursor, "next_model_cursor": next_model,
                "has_more": has_more,
                "observation_interval_sec": OBSERVATION_INTERVAL_SEC,
                "next_poll_after_sec": next_poll_after_sec(
                    status, has_more, changed, deadline_reached),
                "events": events, "model": model, "observation": obs,
            }
            # 等人回话是**要人动手**的状态，必须显式喊出来：只发事件的话，
            # 轮询者会把它当成一次普通的静默，然后一直等下去。
            if awaiting:
                payload["awaiting_reply"] = {
                    "since": state.get("awaiting_since"),
                    "turn": state.get("awaiting_turn"),
                    "kind": state.get("awaiting_kind"),
                    # 模型本轮说了什么——宿主据它当轮就能回。取不到时给 None
                    # 而不是空串：空串与「模型没说话」同形，那是静默降级。
                    "prompt": state.get("awaiting_prompt") or None,
                    "prompt_source": state.get("awaiting_prompt_source") or "unavailable",
                    "waited_sec": state.get("awaiting_stale_sec"),
                    "how": f"python test/story/scripts/run_case.py {case_id} "
                           f"reply --text \"<以用户身份说的话>\"",
                }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        time.sleep(1.0)


def cmd_status(case_id: str) -> int:
    _, out_dir, feature = _load_case(case_id)
    state = reconcile_worker_state(out_dir, read_state(out_dir))
    print(json.dumps({
        "ok": True, "run": state, "worker_alive": _pid_alive(state.get("pid")),
        "observation": observe.snapshot(out_dir, REPO_ROOT / FEATURES_DIR / feature),
    }, ensure_ascii=False, indent=2))
    return 0


def deliver_supplements(case_id: str, feature: str, names: list[str]) -> list[str]:
    """把人手上的补料放进收件箱——**这才是「我把文档发你了」的物理动作**。

    起跑时收件箱里只有说明书。补料等模型自己发现缺料、开口要，才随那句回话一起到达；
    提前铺好，「它会不会发现材料不够」就永远测不到——材料一直都够。

    投放是幂等的：同一份重复投只是覆盖同样的字节。文件名原样保留，
    因为「文件名看不出是哪类材料」本身就是要被测的那个现实。
    """
    if not names:
        return []
    source_root = HERE.parent / "cases" / case_id / "supplements"
    inbox = (REPO_ROOT / FEATURES_DIR / feature / "inbox").resolve()
    delivered: list[str] = []
    for name in names:
        source = (source_root / name).resolve()
        if not source.is_file() or source.parent != source_root.resolve():
            raise SystemExit(f"[runner] 找不到补料或路径越界: {case_id}: {name}")
        inbox.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, inbox / source.name)
        delivered.append(source.name)
    return delivered


def cmd_reply(case_id: str, text: str, deliver: list[str] | None = None) -> int:
    """以用户身份回一句话给停等中的被测会话。

    交互用例（`interactive: true`）靠它推进；自动用例也能用它中途插话纠偏。
    **说人话**——照抄选项 key 或编号测不出「模型能不能听懂人话」，
    而那正是关卡最该被测的地方。

    `--deliver` 让这句话带上附件：先把文件放进收件箱，再把话排进队列。
    顺序不能反——话先到、文件后到，模型会照着那句话去看一个还不存在的目录。
    """
    _, out_dir, feature = _load_case(case_id)
    text = (text or "").strip()
    if not text:
        print(json.dumps({"ok": False, "error": "--text 不能为空"}, ensure_ascii=False))
        return 1
    # 没人在跑就别说 queued：那句话不会有人读，而回执写着「已入队」，
    # 人会以为说过了，然后一直等一个不会到来的下一轮。
    state = reconcile_worker_state(out_dir, read_state(out_dir))
    status = state.get("status")
    if not status:
        print(json.dumps({"ok": False, "error": "该用例没有在跑的运行，先 start"},
                         ensure_ascii=False))
        return 1
    if status in TERMINAL_STATUS:
        print(json.dumps({"ok": False, "error": f"运行已终止（{status}），无人接收"},
                         ensure_ascii=False))
        return 1
    # 只要 worker 仍处于 awaiting_reply 且 lease 未过期，就允许入队。
    # Windows 的进程查询可能被权限策略拒绝，不能把诊断失败变成“无人接收”。
    lease_expires = float(state.get("lease_expires_epoch") or 0)
    if lease_expires and lease_expires < time.time() and not _pid_alive(state.get("pid")):
        print(json.dumps({"ok": False,
                          "error": "worker lease 已过期且进程不可确认，拒绝入队"},
                         ensure_ascii=False))
        return 1
    delivered = deliver_supplements(case_id, feature, list(deliver or []))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / REPLY_FILE).write_text(
        json.dumps({"text": text, "at": time.strftime("%Y-%m-%d %H:%M:%S")},
                   ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "ok": True, "queued": text, "delivered": delivered,
        "reply_status": "accepted",
        "note": "被测会话本轮结束时取用；它仍在说话时不会被打断",
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_conclude(case_id: str, reason: str) -> int:
    """宿主判定「本轮到此为止」——**优雅收工，不杀任何进程**。

    与 `stop` 的区别就是这一条：`stop` 强杀进程树，门禁从不运行、`phase-results/`
    不产出，拿到的报告是残的；`conclude` 只放一个控制文件，worker 自己退出续话循环，
    照常跑完门禁、出阶段结果、复制产物、还原源码事务，然后正常终止。

    什么时候用它：目标阶段的凭证还没齐，但模型已经在宣告要进下一阶段——
    那是它自认为做完了。这时收工，终态记 `concluded_by_host`，
    `target_reached=false` 与 `closure.target_missing` 会如实写在报告里。
    **那是一条有效观测（模型自认完成而凭证不齐），不是装置失败。**
    """
    _, out_dir, _ = _load_case(case_id)
    state = reconcile_worker_state(out_dir, read_state(out_dir))
    status = state.get("status")
    if not status:
        print(json.dumps({"ok": False, "error": "该用例没有在跑的运行"}, ensure_ascii=False))
        return 1
    if status in TERMINAL_STATUS:
        print(json.dumps({"ok": False, "error": f"运行已终止（{status}），无需收工"},
                         ensure_ascii=False))
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / CONCLUDE_FILE).write_text(
        json.dumps({"reason": (reason or "").strip(),
                    "at": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({
        "ok": True, "case": case_id, "reason": (reason or "").strip(),
        "note": "被测会话本轮结束时收工；门禁与阶段结果照常产出，不杀进程",
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_stop(case_id: str, force: bool) -> int:
    """停止后**必须验证进程树死亡**；无法确认时发布 stop_failed，不伪装成 stopped。"""
    _, out_dir, _ = _load_case(case_id)
    state = reconcile_worker_state(out_dir, read_state(out_dir))
    if not state:
        print(json.dumps({"ok": False, "error": "没有可停止的运行"}, ensure_ascii=False))
        return 1
    if state.get("status") in TERMINAL_STATUS:
        state = settle_terminal_source(out_dir, state)
        if state.get("case") and state.get("run_id"):
            run_layout.publish_latest(
                OUT_ROOT, str(state["case"]), str(state["run_id"]), str(state["status"]))
        print(json.dumps({
            "ok": True,
            "status": state.get("status"),
            "already_terminal": True,
            "note": "运行已有终态；未改写阶段结果或质量结论",
        }, ensure_ascii=False, indent=2))
        return 0
    state.update(status="stopping", stop_requested_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    write_state(out_dir, state)

    errors: list[str] = []
    if state.get("cli_run_id"):
        try:
            CliClient(runtime_root=out_dir / "cli-runtime").stop(state["cli_run_id"], force=force)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"stop cli run 失败: {exc}")

    pid = state.get("pid")
    tree_actions: list[str] = []
    if not force:
        deadline = time.time() + STOP_GRACE
        while time.time() < deadline and _pid_alive(pid):
            time.sleep(1.0)
    if _pid_alive(pid):
        try:
            tree_actions.append(_terminate_process_tree(pid, force=force))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"终止 worker 进程树失败: {exc}")
        if not force:
            gentle_deadline = time.time() + 5
            while time.time() < gentle_deadline and _pid_alive(pid):
                time.sleep(0.5)
            if _pid_alive(pid):
                try:
                    tree_actions.append(_terminate_process_tree(pid, force=True))
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"强制终止 worker 进程树失败: {exc}")
        time.sleep(1.0)
    if _pid_alive(pid):
        errors.append(f"worker 仍存活: pid={pid}")

    latest = read_state(out_dir)
    if latest.get("status") in TERMINAL_STATUS:
        latest = settle_terminal_source(out_dir, latest)
        if latest.get("case") and latest.get("run_id"):
            run_layout.publish_latest(
                OUT_ROOT, str(latest["case"]), str(latest["run_id"]), str(latest["status"]))
        print(json.dumps({
            "ok": True,
            "status": latest.get("status"),
            "already_terminal": True,
            "tree_actions": tree_actions,
            "note": "worker 在停止期间自行发布终态；保留其阶段结果，不以 stopped 覆盖",
        }, ensure_ascii=False, indent=2))
        return 0

    final = "stop_failed" if errors else "stopped"
    state = latest or state
    state.update(status=final, execution_status=final,
                 finished_at=time.strftime("%Y-%m-%d %H:%M:%S"),
                 stop_errors=errors or None,
                  tree_actions=tree_actions,
                  residual_pid=pid if _pid_alive(pid) else None)
    write_state(out_dir, state)
    state = settle_terminal_source(out_dir, state)
    final = str(state.get("status") or final)
    if final == "source_restore_failed":
        errors.append("源码事务恢复失败，详见 source-transaction/restore.json")
    if state.get("case") and state.get("run_id"):
        run_layout.publish_latest(
            OUT_ROOT, str(state["case"]), str(state["run_id"]), final)
    print(json.dumps({"ok": not errors, "status": final, "errors": errors,
                      "tree_actions": tree_actions,
                      "phase_results_preserved": bool(state.get("phase_results"))},
                     ensure_ascii=False, indent=2))
    return 0 if not errors else 3


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("case_id")
    ap.add_argument("command", nargs="?", default="start",
                    choices=("run", "start", "poll", "status", "stop", "reply",
                             "conclude"))
    ap.add_argument("--prepared", action="store_true", help="内部：审计目录已由 start 清理")
    ap.add_argument("--run-id", default=None, help="内部：绑定 start 创建的不可变运行")
    ap.add_argument("--cli-config", default=None,
                    help="内部：本 attempt 使用的 cli.configurations id")
    ap.add_argument("--start-phase", default=None,
                    help="内部：协调器覆盖本轮起始阶段；不改变 case.yaml")
    ap.add_argument("--end-phase", default=None,
                    help="内部：协调器覆盖本轮终止阶段；不改变 case.yaml")
    ap.add_argument("--cursor", type=int, default=0)
    ap.add_argument("--model-cursor", type=int, default=0,
                    help="被测模型推理流的游标，与 --cursor 相互独立")
    ap.add_argument("--wait-sec", type=int, default=OBSERVATION_INTERVAL_SEC)
    ap.add_argument("--max-chars", type=int, default=200000)
    ap.add_argument("--force", action="store_true", help="stop：跳过宽限期直接强杀")
    ap.add_argument("--reason", default="",
                    help="conclude：本轮为什么停在这里（进终态回执）")
    ap.add_argument("--text", default="", help="reply：以用户身份回的那句话（说人话，别抄选项 key）")
    ap.add_argument("--deliver", action="append", default=[],
                    help="reply：随这句话把 cases/<id>/supplements/ 下的补料放进收件箱，可多次")
    args = ap.parse_args()

    if args.command == "run":
        return foreground(args.case_id, prepared=args.prepared, run_id=args.run_id,
                          cli_config_id=args.cli_config,
                          start_phase_override=args.start_phase,
                          end_phase_override=args.end_phase)
    if args.command == "start":
        return cmd_start(args.case_id, args.start_phase, args.end_phase,
                         args.cli_config)
    if args.command == "poll":
        return cmd_poll(args.case_id, args.cursor, args.model_cursor,
                        args.wait_sec, args.max_chars)
    if args.command == "status":
        return cmd_status(args.case_id)
    if args.command == "reply":
        return cmd_reply(args.case_id, args.text, args.deliver)
    if args.command == "conclude":
        return cmd_conclude(args.case_id, args.reason)
    return cmd_stop(args.case_id, args.force)


if __name__ == "__main__":
    sys.exit(main())
