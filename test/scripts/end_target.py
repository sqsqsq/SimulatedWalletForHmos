"""用例终点 `end_at` —— 形态、解析，以及按原生对象观测到没到。

终点只有这一个真源：Case 配置的 `end_at: {kind, phase?}`，命令行的 `--end-at` 覆盖它（同一套写法）。

| kind | 到达的判据 |
|---|---|
| story | 需求已登记成文，只读交付门 `story-build check --deliver` 通过（原生设计有效、依据当前、独立审查可消费） |
| blueprint | 蓝图已准入，评审投影与这一版有效；不要求 Story 或施工单位 |
| design_handoff | 蓝图已准入，至少一个活动施工单位，且每个都被原生判为可施工；不要求施工 |
| phase | 在 design_handoff 之上，每个活动施工单位在终点及之前各阶段：完成回执正式收口，或原生判定该阶段无需产出（合法复用） |

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


def observe_native(root: Path, blueprint: str, phases: tuple[str, ...]) -> dict:
    """蓝图、活动施工单位与各阶段的原生事实（只读）。起不来时如实报，不伪造「没有施工单位」。"""
    proc = subprocess.run(["node", str(HERE / "observe_target.mjs"), str(root), blueprint, ",".join(phases)],
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


def phase_closed(unit_root: Path, phase: str, native: dict, receipt) -> tuple[str, list[str]]:
    """一个施工单位的一个阶段：`closed`（回执正式收口）、`reused`（原生判定无需产出）或 `open`，附缺口。

    `receipt(unit_root, phase)` 是驱动器读完成回执的判据，返回 `(ok, missing)`。
    """
    if native.get("status") != "ok" or native.get("issues"):
        return "open", [f"原生 {phase} 输入：{'；'.join(native.get('issues') or [native.get('status')])}"]
    if native.get("scope") != "frozen":
        return "open", [f"{phase} 的执行范围还没冻结"]
    ok, missing = receipt(unit_root, phase)
    if ok:
        return "closed", []
    if native.get("required_outputs") == []:
        return "reused", []
    return "open", list(missing)


def observe(root: Path, features_dir: str, feature: str, end_at: dict, *, case: dict | None,
            story_build: str, receipt, start_phase: str = "story") -> dict:
    """终点到了没有：`{end_at, reached, missing, blueprint_id, blueprint, units, delivery?}`。

    `units` 逐个施工单位列身份、设计判定与各阶段结论；有一个没到，整单就没到——不拿其中一个的 PASS 当整单终点。
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
            unit_root = root / str(unit.get("feature_path") or "")
            for phase in phases:
                state, why = phase_closed(unit_root, phase, unit["phases"].get(phase) or {}, receipt)
                row["phases"][phase] = {"state": state, "missing": why}
                if state == "open":
                    missing.append(f"施工单位 {unit['change_unit_id']} 的 {phase}：{'；'.join(why) or '未闭环'}")
            facts["units"].append(row)
    facts.update(reached=not missing, missing=missing)
    return facts


def first_open(facts: dict) -> tuple[str, str] | None:
    """第一个还没闭环的「施工单位, 阶段」——续话要指名它。"""
    for unit in facts.get("units") or []:
        for phase, row in unit["phases"].items():
            if row["state"] == "open":
                return unit["change_unit_id"], phase
    return None
