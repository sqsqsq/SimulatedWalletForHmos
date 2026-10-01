"""用例终点 `end_at` —— 形态、解析，以及按原生对象观测到没到。

终点只有这一个真源：Case 配置的 `end_at: {kind, phase?}`，命令行的 `--end-at` 覆盖它（同一套写法）。

| kind | 到达的判据 |
|---|---|
| story | 需求已登记成文，只读交付门 `story-build check --deliver` 通过（原生设计有效、依据当前、独立审查可消费） |
| blueprint | 蓝图已准入，评审投影与这一版有效；不要求 Story 或施工单位 |
| design_handoff | 蓝图已准入，至少一个活动施工单位，且每个都被原生判为可施工；不要求施工 |
| phase | 在 design_handoff 之上，每个活动施工单位在终点及之前各阶段：冻结范围要执行的，原生完成证据身份相符、已收口、质量结论 PASS，
认定到达时阶段物证仍新鲜；不执行的，本阶段必需义务由原生承接证据满足（合法复用），或义务全部不适用 |

蓝图身份取需求流程契约里的设计关联（`design_binding.blueprint_id`）；直接走 Framework 的 Case 在配置里显式写 `blueprint_id`。
驱动器不从目录名猜。原生事实由 `observe_target.mjs` 只读取得；本模块把它们与磁盘上的完成回执合成结论，只报事实与缺口。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from run_layout import bound_blueprint

HERE = Path(__file__).resolve().parent
KINDS = ("story", "blueprint", "design_handoff", "phase")
PHASES = ("spec", "plan", "coding", "review", "ut", "testing")


class EndAtError(ValueError):
    """终点写错：说清在哪、错在什么。"""


def parse_end_at(value: Any, *, where: str) -> dict:
    """配置里的映射或命令行的字符串（`story` / `blueprint` / `design_handoff` / `phase:<阶段>`）→ `{kind, phase?}`。"""
    if isinstance(value, str):
        kind, _, phase = value.strip().partition(":")
        value = {"kind": kind, **({"phase": phase} if phase else {})}
    if not isinstance(value, dict):
        raise EndAtError(f"{where}：end_at 要写成 {{kind, phase?}}，读到 {type(value).__name__}")
    extra = sorted(set(value) - {"kind", "phase"})
    if extra:
        raise EndAtError(f"{where}：end_at 只认 kind 与 phase，多了 {'、'.join(extra)}")
    kind = str(value.get("kind") or "").strip()
    if kind not in KINDS:
        raise EndAtError(f"{where}：end_at.kind「{kind}」不在 {' / '.join(KINDS)} 里")
    phase = value.get("phase")
    if kind == "phase":
        if phase not in PHASES:
            raise EndAtError(f"{where}：kind 为 phase 时 phase 必填，取 {' / '.join(PHASES)}，读到「{phase}」")
        return {"kind": "phase", "phase": phase}
    if phase is not None:
        raise EndAtError(f"{where}：kind 为 {kind} 时不带 phase")
    return {"kind": kind}


def label(end_at: dict) -> str:
    """命令行与记录里的写法：`story`、`phase:plan`。"""
    return f"phase:{end_at['phase']}" if end_at["kind"] == "phase" else end_at["kind"]


def responsible_phases(end_at: dict, start_phase: str = "story") -> tuple[str, ...]:
    """本轮负责走到的原生阶段（每个施工单位都要走）；非 phase 终点没有。"""
    if end_at["kind"] != "phase":
        return ()
    end = PHASES.index(end_at["phase"]) + 1
    start = 0 if start_phase == "story" else PHASES.index(start_phase)
    if start >= end:
        raise EndAtError(f"起点 {start_phase} 在终点 {label(end_at)} 之后")
    return PHASES[start:end]


def observe_native(root: Path, blueprint: str, phases: tuple[str, ...], settle: bool = False) -> dict:
    """蓝图、活动施工单位与各阶段的原生事实（只读）。`settle` 时另核执行过的阶段物证仍新鲜（认定到达用，较重）。
    起不来时如实报，不伪造「没有施工单位」。"""
    proc = subprocess.run(["node", str(HERE / "observe_target.mjs"), str(root), blueprint, ",".join(phases),
                           *(["--settle"] if settle else [])],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    if proc.returncode != 0:
        return {"blueprint_id": blueprint, "blueprint": None, "units": [],
                "problems": [f"原生观测没跑成（退出码 {proc.returncode}）：{proc.stderr.strip()[-600:]}"]}
    return json.loads(proc.stdout)


def blueprint_of(root: Path, features_dir: str, feature: str, case: dict | None = None) -> str | None:
    """需求关联的蓝图：Case 显式给的优先，其次是需求流程契约里的设计关联。"""
    explicit = str((case or {}).get("blueprint_id") or "").strip()
    return explicit or bound_blueprint(root / features_dir, feature)


def story_delivery(root: Path, features_dir: str, feature: str, story_build: str) -> tuple[bool, list[str]]:
    """需求交付：登记过成文，且只读交付门通过。门禁的原话就是缺口。"""
    flow = root / features_dir / feature / "AR" / "story-src" / "story-flow.json"
    try:
        status = json.loads(flow.read_text(encoding="utf-8")).get("status")
    except (OSError, ValueError):
        return False, ["需求流程契约还没有或读不出（AR/story-src/story-flow.json）"]
    if status not in ("story_written", "archived"):
        return False, [f"需求还没登记成文（流程状态 {status or '未知'}）"]
    proc = subprocess.run(["node", str(root / story_build), "check", "--deliver", "--feature", feature,
                           "--project-root", str(root)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600, cwd=str(root))
    if proc.returncode == 0:
        return True, []
    said = [line.strip() for line in (proc.stdout + proc.stderr).splitlines() if line.strip()]
    return False, said[:8] or [f"交付门没通过（退出码 {proc.returncode}）"]


#: 阶段结论：closed（执行并收口）、reused（不执行，义务由原生承接证据满足）、not_applicable（义务全部不适用）、
#: not_in_scope（范围里本阶段没有义务）都算到了；open 是还没到
DONE = ("closed", "reused", "not_applicable", "not_in_scope")


def phase_state(phase: str, native: dict) -> tuple[str, list[str]]:
    """一个施工单位一个阶段的原生事实 → `(结论, 缺口)`。质量结论与是否收口分开看：终点要求收口且通过。"""
    kind = native.get("kind")
    if kind == "executed":
        done = native.get("completion") or {}
        if not done.get("summary"):
            return "open", [f"{phase} 没有身份相符的原生完成证据（summary 的 feature/phase 要与本施工单位一致）"]
        if not done.get("closure"):
            return "open", [f"{phase} 还没正式收口（closure_status 不是 closed）"]
        if done.get("verdict") != "PASS":
            return "open", [f"{phase} 已收口但质量结论是 {done.get('verdict') or '缺失'}"]
        fresh = native.get("freshness")
        if fresh is not None and fresh.get("verdict") != "fresh":
            changed = "、".join(fresh.get("changed_paths") or []) or "无物证清单"
            return "open", [f"{phase} 的阶段物证不再新鲜（{fresh.get('verdict')}：{changed}），旧结论不能沿用"]
        return "closed", []
    if kind == "satisfied":
        why = [f"必需义务 {o} 不在执行链上，也没有承接证据" for o in native.get("unsatisfied") or []]
        why += list(native.get("issues") or [])
        return ("open", why) if why else ("reused", [])
    if kind in ("not_applicable", "not_in_scope"):
        return kind, []
    return "open", [f"{phase} 没有原生事实（{kind or '未知'}）"]


def observe(root: Path, features_dir: str, feature: str, end_at: dict, *, case: dict | None,
            story_build: str, start_phase: str = "story", settle: bool = True) -> dict:
    """终点到了没有：`{end_at, reached, missing, blueprint_id, blueprint, units, delivery?}`。

    `units` 逐个施工单位列身份、设计判定与各阶段结论；有一个没到，整单就没到——不拿其中一个的 PASS 当整单终点。
    阶段终点先用轻量原生事实判；都到了且 `settle` 时再核执行过的阶段物证仍新鲜，才认定到达。
    """
    facts: dict[str, Any] = {"end_at": end_at, "reached": False, "missing": [], "blueprint_id": None,
                             "blueprint": None, "units": []}
    if end_at["kind"] == "story":
        ok, missing = story_delivery(root, features_dir, feature, story_build)
        facts.update(reached=ok, missing=missing, delivery={"ok": ok})
        return facts
    blueprint = blueprint_of(root, features_dir, feature, case)
    facts["blueprint_id"] = blueprint
    if not blueprint:
        facts["missing"] = ["需求还没有设计关联的蓝图（流程契约 design_binding.blueprint_id），Case 也没显式给 blueprint_id"]
        return facts
    phases = responsible_phases(end_at, start_phase) if end_at["kind"] == "phase" else ()
    native = observe_native(root, blueprint, phases)
    if settle and phases and _all_done(native, phases):
        native = observe_native(root, blueprint, phases, settle=True)
    facts["blueprint"] = native.get("blueprint")
    missing: list[str] = list(native.get("problems") or [])
    bp = native.get("blueprint") or {}
    if bp.get("status") != "ok":
        missing.append(f"蓝图 {blueprint} 原生读不过（{bp.get('status')}）：{'；'.join(bp.get('issues') or [])}")
    elif not bp.get("admitted"):
        missing.append(f"蓝图 {blueprint} 还没准入")
    elif end_at["kind"] == "blueprint" and bp.get("projection") != "valid":
        missing.append(f"蓝图 {blueprint} 的评审投影{'还没生成' if bp.get('projection') == 'missing' else '与当前这一版对不上'}")
    if end_at["kind"] != "blueprint" and bp.get("admitted"):
        if not native.get("units"):
            missing.append(f"蓝图 {blueprint} 还没有活动施工单位：设计准备没做完")
        for unit in native.get("units") or []:
            row = {"change_unit_id": unit["change_unit_id"], "feature_id": unit["feature_id"],
                   "feature_path": unit.get("feature_path"), "design": unit["design"]["verdict"], "phases": {}}
            if unit["design"]["verdict"] != "constructable":
                missing.append(f"施工单位 {unit['change_unit_id']} 设计判定为 {unit['design']['verdict']}"
                               f"（{'、'.join(unit['design']['issues']) or '无细项'}）")
            scope = unit.get("scope") or {}
            if phases and scope.get("status") != "frozen":
                missing.append(f"施工单位 {unit['change_unit_id']} 的执行范围"
                               f"{'还没冻结' if scope.get('status') == 'not_frozen' else '读不出：' + str(scope.get('detail'))}")
            for phase in phases if scope.get("status") == "frozen" else ():
                state, why = phase_state(phase, unit["phases"].get(phase) or {})
                row["phases"][phase] = {"state": state, "missing": why, "native": unit["phases"].get(phase)}
                if state == "open":
                    missing.append(f"施工单位 {unit['change_unit_id']} 的 {'；'.join(why)}")
            facts["units"].append(row)
    facts.update(reached=not missing, missing=missing)
    return facts


def _all_done(native: dict, phases: tuple[str, ...]) -> bool:
    units = native.get("units") or []
    return bool(units) and all((u.get("scope") or {}).get("status") == "frozen"
                               and all(phase_state(p, u["phases"].get(p) or {})[0] in DONE for p in phases) for u in units)


def first_open(facts: dict) -> tuple[str, str] | None:
    """第一个还没闭环的「施工单位, 阶段」——续话要指名它。"""
    for unit in facts.get("units") or []:
        for phase, row in unit["phases"].items():
            if row["state"] == "open":
                return unit["change_unit_id"], phase
    return None
