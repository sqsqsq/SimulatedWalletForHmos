"""Coordinate multiple Story cases through the existing ``run_case.py`` CLI.

This is deliberately a coordination layer, not a second Story runner.  Each
case keeps the immutable run directory, worker lease, phase gates, source
transaction, interaction channel and execution evidence owned by ``run_case.py``.

Every Case gets its own temporary Git workspace, copied from the current
project: each worker owns its feature tree, Framework state, and CLI cwd.
Running inside the repository under test is not an option — a model under test
must not be able to edit the mechanism being measured.  Immutable run evidence
still lands in the suite bundle under the main repository's output directory.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
TEST_ROOT = HERE.parent
REPO_ROOT = TEST_ROOT.parents[1]
CASES_ROOT = TEST_ROOT / "cases"
CONFIG_PATH = TEST_ROOT / "config" / "test.yaml"
CFG = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
RUN_CASE = HERE / "run_case.py"


def _configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


_configure_console()

sys.path.insert(0, str(HERE))
import run_layout  # noqa: E402
from cli_config_group import load_cli_group  # noqa: E402
from phase_state import derive_phase_state  # noqa: E402

CLI_CONFIGURATIONS, CLI_RETRY_POLICY = load_cli_group(CFG)


OUT_ROOT = Path(str(CFG.get("output", {}).get("dir", "output/story")))
# 被测 CLI 多久没吐字就报一声（只报警，处置由人授权）。
STALL_ALERT_SEC = int(
    ((CFG.get("cli") or {}).get("retry_policy") or {}).get("stall_alert_sec", 900))
if not OUT_ROOT.is_absolute():
    OUT_ROOT = REPO_ROOT / OUT_ROOT
SUITES_ROOT = OUT_ROOT
LEGACY_SUITES_ROOT = OUT_ROOT / "runs"
INTERACTION_INTERVAL_SEC = int(CFG.get("observation", {}).get(
    "interaction_interval_sec", 15))
AUTOMATION_INTERVAL_SEC = int(CFG.get("observation", {}).get(
    "automation_interval_sec", CFG.get("observation", {}).get("interval_sec", 120)))
START_MAX_ATTEMPTS = int(CFG.get("startup", {}).get("max_attempts", 3))
FEATURES_ROOT = (REPO_ROOT / str(CFG.get("target", {}).get(
    "features_dir", "doc/features"))).resolve()
FEATURE_ARCHIVE_ROOT = Path(str(CFG.get("feature_history", {}).get(
    "archive_root", r"E:\Project\bak")))
if not FEATURE_ARCHIVE_ROOT.is_absolute():
    FEATURE_ARCHIVE_ROOT = (REPO_ROOT / FEATURE_ARCHIVE_ROOT).resolve()
FEATURE_ARCHIVE_TIMESTAMP_FORMAT = str(CFG.get("feature_history", {}).get(
    "timestamp_format", "%Y%m%d-%H%M%S"))

VALID_START = {"story", "spec", "plan", "coding", "review", "ut", "testing"}
VALID_END = VALID_START | {"story-review"}
PHASE_ORDER = ("spec", "plan", "coding", "review", "ut", "testing")
TERMINAL_STATUS = {
    "finished", "timeout", "stopped", "stop_failed", "cli_failed",
    "worker_start_failed", "worker_lost", "source_restore_failed",
    "provider_rejected", "workspace_prepare_failed", "unexpected_human_decision",
    "gate_failed", "target_not_reached",
    "content_policy_rejected", "cli_config_exhausted",
}
PHASE_ACTIVE_STATUS = {"starting", "running", "stopping"}
WAITING_STATUS = "awaiting_reply"
ACTIVE_STATUS = PHASE_ACTIVE_STATUS | {WAITING_STATUS}
SAFE_CASE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*$")
OWNED_SUITE_DIR = re.compile(
    r"(?:story-suite-[A-Za-z0-9._-]+|\d{8}-\d{6}-\d+)$")
WORKSPACE_TEMPLATE_NAME = "workspace-template"
WORKSPACES_ROOT_NAME = "workspaces"
# `.opencode` 在列，是因为 **verifier 链住在那里**：`agent/verifier.md`（只读子代理）、
# `plugin/record-verifier-report.js`（结论发布器）、`skill/story/SKILL.md`（作者入口）。
# 不带它，被测侧就没有 verifier 也没有 skill——首跑实测的后果是主模型自己写了
# verifier 报告与证据 JSON（`agent_id: storiesuite-verifier-stub`），那一跑的 verifier 轴失真。
# 目录里的 `node_modules` 由 WORKSPACE_EXCLUDED_DIR_NAMES 排除，不随工作区复制。
WORKSPACE_ALLOWED_DIRS = (
    "01-Product", "02-Feature", "04-BusinessBase", "05-SystemBase",
    "AppScope", "framework", "hvigor", "libs", "doc/extensions", ".opencode",
)
WORKSPACE_ALLOWED_FILES = (
    "AGENTS.md", "CLAUDE.md", "README.md", "build-profile.json5",
    "code-linter.json5", "framework.config.json", "framework.local.json",
    "hvigorfile.ts", "oh-package.json5", "oh-package-lock.json5",
)
WORKSPACE_ALLOWED_DOC_FILES = (
    "doc/architecture.md", "doc/module-catalog.yaml", "doc/glossary.yaml",
    "doc/glossary-seed.txt", "doc/glossary-seed-allowlist.txt",
)
WORKSPACE_EXCLUDED_DIR_NAMES = {
    ".git", "output", "test", "tools", "features", "oh_modules",
    ".pytest_cache", "__pycache__", "build", "intermediates", ".hvigor",
    "node_modules", "scratch",
}
# 按**路径**排除的运行态目录：新 workspace 不能带上一轮的阶段状态，否则起跑点不干净。
# 不用裸目录名排除（曾用 "state"）——裸名会连带误伤任何叫 state 的产品源码目录，
# 而且会把该目录里**发布件声明的占位文件**一起丢掉，触发 framework_integrity「缺失」。
WORKSPACE_STATEFUL_DIRS = {"framework/harness/state"}
# 上述目录里仍须保留的文件：发布清单声明了它们，丢了就会被判 framework 漂移。
WORKSPACE_STATEFUL_KEEP = {".gitkeep"}
WORKSPACE_FORBIDDEN_RUNTIME_DIR_NAMES = {".git", "output", "test", "tools"}


@dataclass(frozen=True)
class CasePlan:
    case_id: str
    feature: str
    start_phase: str
    end_phase: str
    interactive: bool
    phases: tuple[str, ...]
    interaction_script: tuple[dict[str, Any], ...] = ()
    supplements: tuple[dict[str, Any], ...] = ()

    @property
    def contains_coding(self) -> bool:
        return "coding" in self.phases

    def as_dict(self) -> dict[str, Any]:
        return {
            "case": self.case_id,
            "feature": self.feature,
            "start_phase": self.start_phase,
            "end_phase": self.end_phase,
            "interactive": self.interactive,
            "phase_scope": list(self.phases),
            "contains_coding": self.contains_coding,
            "interaction_script": list(self.interaction_script),
            "supplements": list(self.supplements),
        }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def _copy_workspace_tree(source: Path, destination: Path) -> list[str]:
    """Copy only the explicit product/runtime allowlist into a Case workspace."""
    copied: list[str] = []

    def visit(current: Path, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        for child in sorted(current.iterdir(), key=lambda item: item.name):
            if child.is_symlink():
                raise SystemExit(f"[multi] 工作区白名单拒绝软链接: {child}")
            if child.is_dir() and child.name in WORKSPACE_EXCLUDED_DIR_NAMES:
                continue
            relative = child.relative_to(REPO_ROOT).as_posix()
            if child.is_dir() and relative in WORKSPACE_STATEFUL_DIRS:
                # 目录本身要建（发布清单声明它存在），内容不带过来，只留占位文件
                keep_target = target / child.name
                keep_target.mkdir(parents=True, exist_ok=True)
                for keeper in sorted(child.iterdir(), key=lambda item: item.name):
                    if keeper.is_file() and keeper.name in WORKSPACE_STATEFUL_KEEP:
                        shutil.copy2(keeper, keep_target / keeper.name)
                        copied.append(keeper.relative_to(REPO_ROOT).as_posix())
                continue
            if child.is_dir():
                visit(child, target / child.name)
            else:
                destination = target / child.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(child, destination)
                copied.append(relative)

    visit(source, destination)
    return copied


def create_workspace_template(suite_root: Path, suite_id: str) -> tuple[Path, Path]:
    """Create a short-path allowlisted template; no .git/test/tools are copied."""
    workspace_root = (Path(tempfile.gettempdir()) / "sw-story" / suite_id).resolve()
    template = (workspace_root / WORKSPACE_TEMPLATE_NAME).resolve()
    if not template.is_relative_to(workspace_root):
        raise SystemExit(f"[multi] workspace template 越界: {template}")
    if workspace_root.exists():
        raise SystemExit(f"[multi] workspace template 已存在，拒绝覆盖: {template}")
    workspace_root.mkdir(parents=True, exist_ok=False)
    template.mkdir(parents=True, exist_ok=False)
    copied: list[str] = []
    for relative in WORKSPACE_ALLOWED_DIRS:
        source = REPO_ROOT / relative
        if source.is_dir():
            copied.extend(_copy_workspace_tree(source, template / relative))
    for relative in (*WORKSPACE_ALLOWED_FILES, *WORKSPACE_ALLOWED_DOC_FILES):
        source = REPO_ROOT / relative
        if not source.is_file():
            continue
        destination = template / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(relative)
    (template / "doc/features").mkdir(parents=True, exist_ok=True)
    (template / "framework/harness/state").mkdir(parents=True, exist_ok=True)
    write_json(suite_root / "workspace-boundary.json", {
        "schema_version": 2,
        "copied": sorted(copied),
        "excluded": ["output/**", "test/**", "tools/**", "doc/features/**",
                     ".git/**", "other Case inputs", "historical suite data"],
        "case_seeded": {},
        "created_at": now(),
    })
    return template, workspace_root


#: 需求系统快照的存放处：**suite 树之外**的独立目录。
#:
#: 真实环境里需求系统在远端，被测模型只能经对接层访问它。两次实测各暴露一层：
#: 放 workspace 根下，模型一个 `ls` 就看见；挪到 workspace 同级（suite 根下 `.systems/`），
#: 模型 `find ..` 一步又列到了全部单据。suite 树内没有藏身处——被测模型的 cwd 在
#: suite 树里，父链枚举是它的自然动作。所以快照放 `%TEMP%/sw-sys/<suite>/<case>`：
#: 与 `sw-story` 平级，从 workspace 沿父链一步、两步都碰不到；位置只由环境变量告知对接层。
REQUIREMENT_SYSTEM_SIBLING = "sw-sys"
REQUIREMENT_SYSTEM_ENV = "STORY_REQUIREMENT_SYSTEM_DIR"
#: 没有需求系统快照的 Case 用它占位——一个保证不存在的路径。
#: 不能让变量空着：空着 story.js 会落到它的默认目录，而那里装着人手跑用的单据。
#: 指向不存在的路径时 story.js 报「需求系统不可达」，正是这类 Case 本该有的样子。
NO_REQUIREMENT_SYSTEM = "(此 Case 没有需求系统)"
#: 历史落点。只用于边界检查——防的是哪天有人又把它挪回去。
LEGACY_REQUIREMENT_SYSTEM_DIR = ".requirement-system"
LEGACY_REQUIREMENT_SYSTEM_SIBLING = ".systems"


def requirement_system_path(workspace_root: Path, case_id: str) -> Path:
    """该 Case 的需求系统在哪。锚定系统临时目录，不在 suite 树内。

    目录名 = suite 名 + workspace_root 全路径短摘要：同一 suite 的 seed 与 env
    两处推导一致，不同 workspace_root（含单测夹具）互不碰撞。
    """
    root = Path(workspace_root).resolve()
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:8]
    return (Path(tempfile.gettempdir()) / REQUIREMENT_SYSTEM_SIBLING
            / f"{root.name}-{digest}" / case_id)


def seed_requirement_system(case_id: str, workspace_root: Path) -> list[dict[str, Any]]:
    """把该 Case 的需求系统快照复制到 workspace 之外的独立位置。

    每个 Case 一套独立的系统：`archive` 会覆盖系统正文、`restore` 会回退它，
    共用一份的话两个 Case 会互相改写对方的单据，而这类互相干扰事后极难归因。
    """
    source = CASES_ROOT / case_id / "system"
    if not source.is_dir():
        return []
    destination = requirement_system_path(workspace_root, case_id)
    if destination.resolve().is_relative_to(Path(workspace_root).resolve()):
        raise SystemExit(f"[multi] 需求系统快照落进了 suite 树内: {destination}")
    seeded: list[dict[str, Any]] = []
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise SystemExit(f"[multi] 需求系统快照拒绝软链接: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        seeded.append({
            "source": f"{case_id}/system/{relative.as_posix()}",
            "target": f"{REQUIREMENT_SYSTEM_SIBLING}/{case_id}/{relative.as_posix()}",
            "size": path.stat().st_size,
        })
    return seeded


def _case_seed_manifest(case_id: str, feature: str) -> list[dict[str, Any]]:
    source_root = CASES_ROOT / case_id / "workspace"
    if not source_root.is_dir():
        return []
    seeded: list[dict[str, Any]] = []
    for source in sorted(source_root.rglob("*")):
        if source.is_symlink():
            raise SystemExit(f"[multi] Case 输入拒绝软链接: {source}")
        if not source.is_file():
            continue
        relative = source.relative_to(source_root).as_posix()
        seeded.append({
            "source": source.relative_to(REPO_ROOT).as_posix(),
            "target": f"doc/features/{feature}/{relative}",
            "size": source.stat().st_size,
        })
    return seeded


def _verify_workspace_boundary(workspace: Path, feature: str) -> dict[str, Any]:
    violations: list[str] = []
    symlinks: list[str] = []
    for path in workspace.rglob("*"):
        relative = path.relative_to(workspace).as_posix()
        if path.is_symlink():
            symlinks.append(relative)
            continue
        if path.is_dir() and path.name.casefold() in WORKSPACE_FORBIDDEN_RUNTIME_DIR_NAMES:
            violations.append(relative)
        # 需求系统在远端，被测侧的目录树里不该有它——放进来，模型一个 `ls`
        # 就看见了，「系统按单号拉取」这条链下一轮就可能被绕过去。
        if path.is_dir() and path.name == LEGACY_REQUIREMENT_SYSTEM_DIR:
            violations.append(relative)
    features = workspace / "doc/features"
    unexpected_features = []
    if features.is_dir():
        unexpected_features = sorted(
            child.name for child in features.iterdir()
            if child.name != feature
        )
    if symlinks or violations or unexpected_features:
        raise RuntimeError(
            "workspace 边界失败: "
            f"forbidden={violations}, symlinks={symlinks}, "
            f"other_features={unexpected_features}")
    return {
        "recursive_forbidden": violations,
        "symlinks": symlinks,
        "other_features": unexpected_features,
    }


def create_case_workspace(suite: dict[str, Any], case: dict[str, Any]) -> Path:
    """Copy the allowlisted template into one isolated Case workspace."""
    suite_root = Path(str(suite["bundle_root"])).resolve()
    template = Path(str(suite["workspace_template"])).resolve()
    workspace_root = Path(str(suite["workspace_root"])).resolve()
    workspace = (workspace_root / str(case["case"])).resolve()
    # **测量工具不许在被测对象的仓里跑。** 隔离是唯一形态（开关已退场），
    # 但「唯一形态」是个约定，下面两条是物理校验：工作区必须落在系统临时目录，
    # 且不得是主仓的子路径。破了这条，被测模型就能改被测机制，那一轮的读数
    # 全都要先自证「这次它没改过」——实测撞到过一次，改的正是判据所在的目录。
    temp_root = Path(tempfile.gettempdir()).resolve()
    if not workspace.is_relative_to(temp_root):
        raise SystemExit(f"[multi] Case workspace 必须在系统临时目录下: {workspace}")
    if workspace.is_relative_to(REPO_ROOT):
        raise SystemExit(f"[multi] Case workspace 落在主仓里，拒绝启动: {workspace}")
    if not template.is_dir() or not (template / "framework").is_dir():
        raise SystemExit(f"[multi] 缺少 workspace template: {template}")
    if not workspace.is_relative_to(workspace_root) or workspace == workspace_root:
        raise SystemExit(f"[multi] Case workspace 越界: {workspace}")
    if workspace.exists():
        raise SystemExit(f"[multi] Case workspace 已存在，拒绝覆盖: {workspace}")
    workspace_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(template, workspace)
    boundary_check = _verify_workspace_boundary(workspace, str(case["feature"]))
    case["workspace"] = str(workspace)
    case["workspace_status"] = "created"
    case["case_seeded"] = _case_seed_manifest(
        str(case["case"]), str(case["feature"]))
    case["system_seeded"] = seed_requirement_system(str(case["case"]), workspace_root)
    # 备着但还没投的补料：起跑时收件箱里只有说明书，这几份要等模型开口要。
    case["supplements_pending"] = [
        item["file"] for item in (case.get("supplements") or [])
        if item.get("deliver") != "start"]
    case["supplements_delivered"] = []
    boundary_path = suite_root / "workspace-boundary.json"
    boundary = read_json(boundary_path, {}) or {}
    boundary.setdefault("case_seeded", {})[str(case["case"])] = case["case_seeded"]
    boundary.setdefault("system_seeded", {})[str(case["case"])] = case["system_seeded"]
    boundary.setdefault("supplements_pending", {})[str(case["case"])] = \
        case["supplements_pending"]
    boundary.setdefault("case_checks", {})[str(case["case"])] = boundary_check
    write_json(boundary_path, boundary)
    case_root = suite_root / "cases" / str(case["case"])
    case_root.mkdir(parents=True, exist_ok=True)
    baseline = snapshot_workspace_sources(workspace)
    case["workspace_baseline"] = str(case_root / "workspace-baseline.json")
    write_json(Path(case["workspace_baseline"]), baseline)
    return workspace


def _complete_current_attempt(record: dict[str, Any], *, status: str,
                              failure_kind: str, retry_action: str) -> None:
    current = record.get("current_attempt")
    for attempt in reversed(record.get("attempts") or []):
        if attempt.get("attempt") == current:
            attempt.update({
                "status": status, "failure_kind": failure_kind,
                "retry_action": retry_action, "finished_at": now(),
            })
            return


def prepare_case_retry(suite: dict[str, Any], record: dict[str, Any]) -> None:
    """Recreate one isolated Case from the suite's immutable inputs."""
    workspace_root = Path(str(suite["workspace_root"])).resolve()
    workspace = (workspace_root / str(record["case"])).resolve()
    if workspace == workspace_root or not workspace.is_relative_to(workspace_root):
        raise RuntimeError(f"重跑 workspace 越界: {workspace}")
    if workspace.is_symlink():
        raise RuntimeError(f"重跑拒绝软链接 workspace: {workspace}")
    if workspace.exists():
        shutil.rmtree(workspace, onexc=_clear_readonly_and_retry)

    system = requirement_system_path(workspace_root, str(record["case"])).resolve()
    system_root = (Path(tempfile.gettempdir()) / REQUIREMENT_SYSTEM_SIBLING).resolve()
    if not system.is_relative_to(system_root) or system == system_root:
        raise RuntimeError(f"重跑需求系统路径越界: {system}")
    if system.is_symlink():
        raise RuntimeError(f"重跑拒绝软链接需求系统: {system}")
    if system.exists():
        shutil.rmtree(system, onexc=_clear_readonly_and_retry)

    record.update({
        "workspace": None, "workspace_status": "recreating",
        "run_id": None, "worker_pid": None, "cursor": 0, "model_cursor": 0,
        "last_phase": None, "current_phase": None,
        "highest_phase_reached": None, "phase_source": None,
        "phase_observed_at": None, "spec_entered_at": None,
        "awaiting_since": None, "execution_status": None,
        "failure_kind": None, "pipeline": None,
        "last_poll_at": None, "last_error": None, "last_awaiting": None,
        "last_reply_status": None, "last_reply_text": None,
        "last_replied_turn": None, "last_adaptive_request": None,
        "interaction_index": 0, "interaction_state": "not_started",
        "adaptive_reply_count": 0, "source_restore_status": "not_started",
        "automation_observation_state": "not_started",
        "automation_observation_started_at": None,
        "automation_observation_until": None, "next_observation_at": None,
        "observation_count": 0, "current_attempt": None,
        "retry_finalized": False,
    })
    create_case_workspace(suite, record)
    record["status"] = "pending"
    retry_state = record.setdefault("retry_state", {})
    retry_state.update({"phase": "prepared", "prepared_at": now()})


def request_case_retry(suite: dict[str, Any], record: dict[str, Any], *,
                       config_index: int, reason: str, failure_kind: str) -> None:
    _complete_current_attempt(record, status="failed", failure_kind=failure_kind,
                              retry_action=reason)
    record["cli_config_index"] = config_index
    record["cli_config_id"] = suite_cli_configurations(suite)[config_index]["id"]
    record["retry_state"] = {
        "phase": "preparing", "reason": reason,
        "failure_kind": failure_kind, "planned_at": now(),
        "next_cli_config_id": record["cli_config_id"],
    }
    record["status"] = "retry_preparing"
    save_suite(Path(str(suite["bundle_root"])) / "suite.json", suite)
    prepare_case_retry(suite, record)
    append_event(suite, "case_retry_prepared", case=record["case"],
                 reason=reason, cli_config_id=record["cli_config_id"])
    append_case_observation(suite, str(record["case"]), {
        "kind": "retry", "reason": reason, "failure_kind": failure_kind,
        "next_cli_config_id": record["cli_config_id"],
    })


def process_retryable_failures(suite: dict[str, Any]) -> None:
    records = list(suite.get("case_states", {}).values())
    health = suite_cli_health(suite)

    for record in records:
        if record.get("status") == "retry_preparing":
            try:
                prepare_case_retry(suite, record)
            except (OSError, RuntimeError, SystemExit) as exc:
                record.update(status="workspace_prepare_failed", retry_finalized=True,
                              last_error={"reason": str(exc)})
                append_event(suite, "case_retry_prepare_failed",
                             case=record.get("case"), error=str(exc))

    # Authentication is configuration-wide.  Trip every observed 401 first so
    # content retries in the same poll cannot select a now-invalid credential.
    for record in records:
        refresh_record(record)
        if record.get("status") == "cli_failed" \
                and record.get("failure_kind") == "auth_required":
            config_id = str(record.get("cli_config_id") or "")
            item = health.get(config_id)
            if item and item.get("status") == "available":
                item.update({
                    "status": "unavailable_auth", "tripped_at": now(),
                    "tripped_by_case": record.get("case"),
                    "tripped_by_run": record.get("run_id"),
                })
                append_event(suite, "cli_configuration_tripped",
                             cli_config_id=config_id, case=record.get("case"),
                             run_id=record.get("run_id"), reason="auth_required")

    retry_limit = int((suite.get("cli_configuration_group") or {})
                      .get("retry_policy", CLI_RETRY_POLICY)
                      .get("content_rejection_retries_per_config", 1))
    for record in records:
        if record.get("status") != "cli_failed":
            continue
        failure_kind = str(record.get("failure_kind") or "")
        current_index = int(record.get("cli_config_index") or 0)
        config_id = str(record.get("cli_config_id") or "")
        if failure_kind == "auth_required":
            selected = select_healthy_cli(suite, current_index + 1)
            if selected is None:
                _complete_current_attempt(
                    record, status="cli_config_exhausted", failure_kind=failure_kind,
                    retry_action="no_healthy_cli_configuration")
                record.update(status="cli_config_exhausted", retry_finalized=True,
                              last_error={"failure_kind": failure_kind,
                                          "reason": "no_healthy_cli_configuration"})
                record["retry_state"] = {"phase": "exhausted",
                                         "reason": "no_healthy_cli_configuration",
                                         "at": now()}
                append_event(suite, "case_retry_exhausted", case=record.get("case"),
                             reason="no_healthy_cli_configuration")
                continue
            request_case_retry(suite, record, config_index=selected[0],
                               reason="switch_after_auth_failure",
                               failure_kind=failure_kind)
        elif failure_kind == "content_policy_rejected":
            counts = record.setdefault("content_rejection_counts", {})
            counts[config_id] = int(counts.get(config_id) or 0) + 1
            if counts[config_id] > retry_limit:
                _complete_current_attempt(
                    record, status="content_policy_rejected", failure_kind=failure_kind,
                    retry_action="content_retry_exhausted")
                record.update(status="content_policy_rejected", retry_finalized=True,
                              last_error={"failure_kind": failure_kind,
                                          "reason": "content_retry_exhausted"})
                record["retry_state"] = {"phase": "exhausted",
                                         "reason": "content_retry_exhausted",
                                         "at": now()}
                append_event(suite, "case_retry_exhausted", case=record.get("case"),
                             reason="content_retry_exhausted")
                continue
            selected = select_healthy_cli(suite, current_index)
            if selected is None:
                _complete_current_attempt(
                    record, status="cli_config_exhausted",
                    failure_kind="auth_required",
                    retry_action="no_healthy_cli_configuration")
                record.update(status="cli_config_exhausted", retry_finalized=True,
                              last_error={"failure_kind": "auth_required",
                                          "reason": "no_healthy_cli_configuration"})
                record["retry_state"] = {"phase": "exhausted",
                                         "reason": "no_healthy_cli_configuration",
                                         "at": now()}
                append_event(suite, "case_retry_exhausted", case=record.get("case"),
                             reason="no_healthy_cli_configuration")
                continue
            request_case_retry(suite, record, config_index=selected[0],
                               reason="retry_after_content_rejection",
                               failure_kind=failure_kind)


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return default


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def safe_case_id(value: str) -> bool:
    return bool(SAFE_CASE_ID.fullmatch(value))


def snapshot_workspace_sources(workspace: Path) -> dict[str, Any]:
    """Hash only the product source allowlist for later promotion/diff evidence.

    **构建产物不是源码**：coding 阶段会跑编译，`oh_modules/`、`build/`、`.hvigor/` 随之全变。
    把它们算进「源码差异」有两个后果——差异里 572 个文件只有个位数是模型真改的，
    看不出它动了什么；而 `oh_modules/@aspect/…` 的依赖树嵌套极深，
    复制到证据目录时目标路径会超过 Windows 的 260 字符上限，回灌直接崩（实测 31 条）。

    排除清单复用 `WORKSPACE_EXCLUDED_DIR_NAMES`——workspace 复制时就是按它挑的，
    两处用同一份，不另立一份会漂移的副本。
    """
    roots = ("01-Product", "02-Feature", "04-BusinessBase", "05-SystemBase")
    files: dict[str, dict[str, Any]] = {}
    for root in roots:
        base = workspace / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(workspace)
            if any(part in WORKSPACE_EXCLUDED_DIR_NAMES for part in relative.parts[:-1]):
                continue
            relative = relative.as_posix()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            files[relative] = {"sha256": digest, "size": path.stat().st_size}
    digest = hashlib.sha256(
        json.dumps(files, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {"schema_version": 1, "digest": digest, "files": files, "captured_at": now()}


#: 补料的投放时机。`start` = 人手上本来就有、起跑前已放进需求目录；
#: `on_request` = 被测模型开口要了才投——真实场景里人不会提前把所有文档铺满。
VALID_DELIVER = frozenset({"start", "on_request"})


def load_supplements(case_id: str) -> tuple[dict[str, Any], ...]:
    """本 Case 备着的补料：文件名 + 什么时候投。

    补料放在 `cases/<id>/supplements/`，与 `workspace/` 分开：后者是起跑那一刻
    需求目录里就有的东西，前者是**要来的**。混在一起，「模型有没有发现缺料」
    就永远测不到——材料早就摆好了。
    """
    path = CASES_ROOT / case_id / "case.yaml"
    case = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    declared = case.get("supplements") or []
    if not isinstance(declared, list):
        raise SystemExit(f"[multi] case.yaml supplements 非列表: {case_id}")
    root = CASES_ROOT / case_id / "supplements"
    output: list[dict[str, Any]] = []
    for index, item in enumerate(declared, start=1):
        if not isinstance(item, dict) or not str(item.get("file") or "").strip():
            raise SystemExit(f"[multi] case.yaml supplements 第 {index} 项缺少 file: {case_id}")
        name = str(item["file"]).strip()
        deliver = str(item.get("deliver") or "on_request").strip()
        if deliver not in VALID_DELIVER:
            raise SystemExit(
                f"[multi] case.yaml supplements 第 {index} 项 deliver 非法: {case_id}: "
                f"{deliver}（可用：{'/'.join(sorted(VALID_DELIVER))}）")
        source = root / name
        if not source.is_file() or source.is_symlink():
            raise SystemExit(f"[multi] 声明的补料不存在: {case_id}: supplements/{name}")
        if source.resolve().parent != root.resolve():
            raise SystemExit(f"[multi] 补料越界: {case_id}: {name}")
        # 路径记成「相对 Case 根」：绝对路径带着本机盘符，抄进证据文件就没法跨环境读。
        output.append({"file": name, "deliver": deliver,
                       "source": f"{case_id}/supplements/{name}"})
    return tuple(output)


def load_interaction_script(case_id: str) -> tuple[dict[str, Any], ...]:
    path = CASES_ROOT / case_id / "interaction-script.yaml"
    if not path.is_file():
        return ()
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    replies = payload.get("replies") if isinstance(payload, dict) else None
    if not isinstance(replies, list):
        raise SystemExit(f"[multi] interaction-script.yaml replies 非列表: {case_id}")
    known = {item["file"] for item in load_supplements(case_id)}
    output: list[dict[str, Any]] = []
    for index, item in enumerate(replies, start=1):
        if not isinstance(item, dict) or not str(item.get("text") or "").strip():
            raise SystemExit(f"[multi] interaction-script.yaml 第 {index} 项缺少 text: {case_id}")
        expected_turn = item.get("expected_turn", index)
        expected_phase = str(item.get("expected_phase") or "").strip()
        if expected_phase and expected_phase not in VALID_EXPECTED_PHASE:
            raise SystemExit(
                f"[multi] interaction-script.yaml 第 {index} 项 expected_phase 非法: "
                f"{case_id}: {expected_phase}（可用：{'/'.join(sorted(VALID_EXPECTED_PHASE))}）")
        deliver = item.get("deliver") or []
        if isinstance(deliver, str):
            deliver = [deliver]
        if not isinstance(deliver, list):
            raise SystemExit(f"[multi] interaction-script.yaml 第 {index} 项 deliver 非列表: {case_id}")
        deliver = [str(name).strip() for name in deliver if str(name).strip()]
        unknown = [name for name in deliver if name not in known]
        if unknown:
            raise SystemExit(
                f"[multi] interaction-script.yaml 第 {index} 项要投的补料未在 case.yaml 声明: "
                f"{case_id}: {'、'.join(unknown)}")
        output.append({
            "id": str(item.get("id") or f"reply-{index}"),
            "text": str(item["text"]).strip(),
            "expected_turn": int(expected_turn),
            "expected_kind": str(item.get("expected_kind") or "story_gate"),
            "expected_phase": expected_phase,
            "deliver": deliver,
        })
    return tuple(output)


# 关卡回复的阶段前提：turn 编号只说「第几关」，说不出「这一关在哪个阶段」。
# 评审意见这类回复必须在归档之后才有意义——只按 turn 排队，模型少停一关就会把
# 后面的话提前送进前面的关卡，而且送出去了才发现对不上。
VALID_EXPECTED_PHASE = frozenset({"story", "spec", "archived"})


def gate_phase_ready(record: dict[str, Any], expected_phase: str) -> bool:
    """当前是否已满足该回复声明的阶段前提。"""
    if not expected_phase:
        return True
    if expected_phase == "archived":
        workspace_text = str(record.get("workspace") or "").strip()
        if not workspace_text:
            return False
        flow = (Path(workspace_text) / "doc" / "features"
                / str(record.get("feature") or "") / "AR" / "story-flow.json")
        try:
            return bool(json.loads(flow.read_text(encoding="utf-8")).get("archived"))
        except (OSError, ValueError):
            return False
    highest = str(record.get("highest_phase_reached") or "").strip()
    if expected_phase == "story":
        # story 关卡发生在进入 spec 之前：还没到过 spec 就是 story 阶段。
        return highest not in PHASE_ORDER
    return highest in PHASE_ORDER and (
        PHASE_ORDER.index(highest) >= PHASE_ORDER.index(expected_phase))


def phase_scope(start_phase: str, end_phase: str) -> tuple[str, ...]:
    """Return phases that can touch Framework state for a case.

    ``story-review`` is a Story-side endpoint after the regular spec closure;
    it still has a spec phase but never reaches coding.
    """
    if end_phase == "story-review":
        end_index = PHASE_ORDER.index("spec")
    else:
        end_index = PHASE_ORDER.index(end_phase)
    start_index = 0 if start_phase == "story" else PHASE_ORDER.index(start_phase)
    if start_index > end_index:
        raise ValueError(f"阶段范围反向: {start_phase} -> {end_phase}")
    return PHASE_ORDER[start_index:end_index + 1]


def load_case_plan(case_id: str) -> CasePlan:
    if not safe_case_id(case_id):
        raise SystemExit(f"[multi] 非法 case id: {case_id}")
    path = CASES_ROOT / case_id / "case.yaml"
    if not path.is_file():
        raise SystemExit(f"[multi] 找不到 case: {case_id}")
    case = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if case.get("id") != case_id:
        raise SystemExit(f"[multi] case.yaml id 不匹配: {case_id}")
    feature = str(case.get("ar") or "").strip()
    if not feature:
        raise SystemExit(f"[multi] case 未声明 ar: {case_id}")
    start_phase = str(case.get("start_phase") or "story").strip()
    end_phase = str(case.get("end_phase") or "spec").strip()
    if start_phase not in VALID_START or end_phase not in VALID_END:
        raise SystemExit(f"[multi] case 阶段非法: {case_id}: {start_phase} -> {end_phase}")
    try:
        phases = phase_scope(start_phase, end_phase)
    except ValueError as exc:
        raise SystemExit(f"[multi] {exc}") from exc
    return CasePlan(case_id, feature, start_phase, end_phase,
                    bool(case.get("interactive")), phases,
                    load_interaction_script(case_id),
                    load_supplements(case_id))


def select_cases(case_ids: list[str], all_cases: bool) -> list[CasePlan]:
    if all_cases and case_ids:
        raise SystemExit("[multi] --all 与显式 case id 不可同时使用")
    selected_ids = (
        sorted(path.name for path in CASES_ROOT.iterdir()
               if path.is_dir() and (path / "case.yaml").is_file())
        if all_cases else case_ids
    )
    if not selected_ids:
        raise SystemExit("[multi] 没有选择任何 case")
    if len(selected_ids) != len(set(selected_ids)):
        raise SystemExit("[multi] 同一 suite 不允许重复 case id")
    plans = [load_case_plan(case_id) for case_id in selected_ids]
    by_ar: dict[str, list[str]] = {}
    for plan in plans:
        by_ar.setdefault(plan.feature, []).append(plan.case_id)
    duplicates = {ar: cases for ar, cases in by_ar.items() if len(cases) > 1}
    if duplicates:
        detail = "；".join(f"{ar}: {', '.join(cases)}"
                           for ar, cases in sorted(duplicates.items()))
        raise SystemExit(
            "[multi] 一 Case 一 AR 校验失败：同一 suite 不允许重复 AR；" + detail)
    return plans


def git_snapshot() -> dict[str, Any]:
    def run_git(*args: str) -> str:
        result = subprocess.run(
            ["git", "-c", f"safe.directory={REPO_ROOT}", *args],
            cwd=str(REPO_ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=False,
        )
        if result.returncode != 0:
            raise SystemExit(f"[multi] git {' '.join(args)} 失败: {result.stderr.strip()}")
        return result.stdout

    status = run_git("status", "--porcelain=v1")
    return {
        "head": run_git("rev-parse", "HEAD").strip(),
        "status": status,
        "status_sha256": hashlib.sha256(status.encode("utf-8")).hexdigest(),
        "captured_at": now(),
        "workspace": str(REPO_ROOT),
    }


def run_pointer_state(case_id: str, run_id: str | None = None) -> dict[str, Any] | None:
    pointer_names = ("active",) if run_id else ("active", "latest")
    for pointer_name in pointer_names:
        if run_id:
            pointer = {"run_id": run_id}
        else:
            pointer = run_layout.read_pointer(OUT_ROOT, case_id, pointer_name)
        if not pointer:
            continue
        run_dir = run_layout.run_dir(OUT_ROOT, case_id, str(pointer["run_id"]))
        state = read_json(run_dir / "state.json")
        if not isinstance(state, dict):
            state = {"status": pointer.get("status")}
        state = dict(state)
        state["run_id"] = str(pointer["run_id"])
        state["run_dir"] = str(run_dir)
        return state
    return None


def source_restore_status(state: dict[str, Any]) -> str:
    source = state.get("source_transaction")
    if not isinstance(source, dict) or not source.get("required"):
        return "not_required"
    restore = source.get("restore")
    if not isinstance(restore, dict):
        return "missing"
    return str(restore.get("status") or "unknown")


def requested_end_phase(plan: CasePlan, base_end_phase: str | None,
                        continue_case: str | None,
                        continue_end_phase: str | None) -> str | None:
    if continue_case == plan.case_id:
        return continue_end_phase or base_end_phase
    return base_end_phase


def validate_phase_overrides(base_end_phase: str | None,
                             continue_case: str | None,
                             continue_end_phase: str | None,
                             plans: list[CasePlan]) -> None:
    if base_end_phase and base_end_phase not in VALID_END:
        raise SystemExit(f"[multi] 非法 --end-phase: {base_end_phase}")
    if continue_case and continue_case not in {plan.case_id for plan in plans}:
        raise SystemExit(f"[multi] --continue-case 不在选中 Case 中: {continue_case}")
    if continue_case and not continue_end_phase:
        raise SystemExit("[multi] --continue-case 必须同时提供 --continue-end-phase")
    if continue_end_phase and continue_end_phase not in VALID_END:
        raise SystemExit(f"[multi] 非法 --continue-end-phase: {continue_end_phase}")


def new_case_record(plan: CasePlan, target_end_phase: str | None = None) -> dict[str, Any]:
    target_end = target_end_phase or plan.end_phase
    target_phases = phase_scope(plan.start_phase, target_end)
    return {
        **plan.as_dict(),
        "requested_start_phase": plan.start_phase,
        "requested_end_phase": target_end_phase,
        "effective_phase_scope": list(target_phases),
        "wait_for_cases": [],
        "interaction_script": list(plan.interaction_script),
        "interaction_index": 0,
        "interaction_state": "not_started",
        "last_reply_status": None,
        "last_reply_text": None,
        # 回复的身份由**关卡编号**决定：回过哪一关，比「上一次回复被消费了没有」可靠——
        # 后者要靠 poll 恰好观测到 WAITING→ACTIVE 的跳变，而被测模型常在一个轮询周期内
        # 消费回复并抛出下一关，前后两次看到的都是 awaiting，第二关就再也不会被回复。
        "last_replied_turn": None,
        "adaptive_reply_count": 0,
        "last_adaptive_request": None,
        "last_awaiting": None,
        "status": "pending",
        "run_id": None,
        "worker_pid": None,
        "cursor": 0,
        "model_cursor": 0,
        "last_phase": None,
        "current_phase": None,
        "highest_phase_reached": None,
        "phase_source": None,
        "phase_observed_at": None,
        "spec_entered_at": None,
        "awaiting_since": None,
        "source_restore_status": "not_started",
        "execution_status": None,
        "last_poll_at": None,
        "last_error": None,
        "start_attempts": 0,
        "start_history": [],
        "last_human_reply_at": None,
        "automation_observation_state": "not_started",
        "automation_observation_started_at": None,
        "automation_observation_until": None,
        "next_observation_at": None,
        "observation_count": 0,
        "cli_config_id": CLI_CONFIGURATIONS[0]["id"],
        "cli_config_index": 0,
        "attempts": [],
        "current_attempt": None,
        "content_rejection_counts": {},
        "retry_state": None,
    }


def suite_cli_configurations(suite: dict[str, Any]) -> list[dict[str, str]]:
    group = suite.get("cli_configuration_group") or {}
    values = group.get("configurations") or CLI_CONFIGURATIONS
    return [dict(item) for item in values]


def suite_cli_health(suite: dict[str, Any]) -> dict[str, dict[str, Any]]:
    group = suite.setdefault("cli_configuration_group", {
        "configurations": [dict(item) for item in CLI_CONFIGURATIONS],
        "retry_policy": dict(CLI_RETRY_POLICY),
        "health": {},
    })
    health = group.setdefault("health", {})
    for item in suite_cli_configurations(suite):
        health.setdefault(item["id"], {
            "status": "available", "tripped_at": None,
            "tripped_by_case": None, "tripped_by_run": None,
        })
    return health


def select_healthy_cli(suite: dict[str, Any], start_index: int = 0) -> tuple[int, str] | None:
    configurations = suite_cli_configurations(suite)
    health = suite_cli_health(suite)
    for index in range(max(0, start_index), len(configurations)):
        config_id = configurations[index]["id"]
        if health[config_id].get("status") == "available":
            return index, config_id
    return None



def events_idle_sec(run_dir: str | None) -> int | None:
    """被测 CLI 有多久没吐字了。

    时限（soft/hard timeout）在 F6 被裁掉是对的——它们把正在推进的会话从中间切断。
    但裁掉之后**没有任何东西在看「CLI 多久没产出了」**：实测一次，请求发出去没回来，
    进程活着、租约健康、状态 running，从装置的每个指标看都一切正常，而它已经
    50 分钟没吐一个字。挂起与深度思考在装置眼里长得一模一样。

    所以这里只**报数**，不做任何终止判断：多久算久由看的人定，装置不替他定。
    """
    if not run_dir:
        return None
    path = Path(run_dir) / "events.jsonl"
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    return max(0, int(time.time() - mtime))

def refresh_record(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("retry_finalized") and record.get("status") in {
            "content_policy_rejected", "cli_config_exhausted",
            "workspace_prepare_failed"}:
        return record
    run_id = record.get("run_id")
    if not run_id and record.get("status") in {"pending", "coordinator_start_failed"}:
        return record
    state = run_pointer_state(str(record["case"]), run_id)
    if not state:
        return record
    record["status"] = state.get("status") or record.get("status")
    record["run_id"] = state.get("run_id")
    record["worker_pid"] = state.get("pid")
    for key in ("last_phase", "current_phase", "highest_phase_reached",
                "phase_source", "phase_observed_at", "spec_entered_at"):
        if state.get(key) is not None:
            record[key] = state.get(key)
    record["awaiting_since"] = state.get("awaiting_since")
    idle = events_idle_sec(state.get("run_dir"))
    record["events_idle_sec"] = idle
    # 停滞只打标、**不处置**：可能还在想，自动重启会丢掉正在进行的工作。
    # 处置要人授权（`retry <case>`）——装置报事实，人做决定。
    record["stalled"] = bool(
        idle is not None and idle >= STALL_ALERT_SEC
        and record.get("status") in PHASE_ACTIVE_STATUS)
    if record.get("status") == WAITING_STATUS:
        # **原话要一起带上**：漏了它，`poll_suite` 刚透传上来的那份就在这里被抹掉，
        # 宿主拿到的 `question` 于是恒为空——他只能自己去 events.jsonl 尾部捞。
        record["last_awaiting"] = {
            "turn": state.get("awaiting_turn"),
            "kind": state.get("awaiting_kind"),
            "prompt": state.get("awaiting_prompt") or None,
            "prompt_source": state.get("awaiting_prompt_source") or "unavailable",
            "waited_sec": state.get("awaiting_stale_sec"),
        }
    if state.get("closure") is not None:
        record["closure"] = state.get("closure")
    record["source_restore_status"] = source_restore_status(state)
    record["execution_status"] = state.get("execution_status") or record.get("status")
    for key in ("failure_kind", "pipeline"):
        if key in state:
            record[key] = state.get(key)
    if record.get("status") in TERMINAL_STATUS or record.get("status") == "cli_failed":
        current = record.get("current_attempt")
        for attempt in reversed(record.get("attempts") or []):
            if attempt.get("attempt") == current and not attempt.get("finished_at"):
                attempt.update({
                    "status": record.get("status"),
                    "failure_kind": record.get("failure_kind"),
                    "finished_at": now(),
                })
                break
    if record.get("status") == "cli_failed" \
            and str(record.get("failure_kind") or "").lower() in {
                "provider_rejected", "content_inspection", "rate_limited",
                "service_unavailable",
            }:
        record["status"] = "provider_rejected"
        record["failure_class"] = "provider_rejected"
    return record


def reconcile_record_phase(record: dict[str, Any]) -> dict[str, Any]:
    """Reconcile a suite record from its workspace without reading model prose."""
    workspace_text = str(record.get("workspace") or "").strip()
    if not workspace_text:
        return {}
    keys = ("current_phase", "highest_phase_reached", "phase_source",
            "phase_observed_at", "last_phase", "spec_entered_at")
    before = {key: record.get(key) for key in keys}
    record.update(derive_phase_state(Path(workspace_text),
                                     str(record.get("feature") or ""), record,
                                     observed_at=now()))
    return {key: {"before": before.get(key), "after": record.get(key)}
            for key in keys if before.get(key) != record.get(key)}


def suite_path(suite_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", suite_id):
        raise SystemExit(f"[multi] 非法 suite id: {suite_id}")
    target = (SUITES_ROOT / suite_id).resolve()
    target.relative_to(SUITES_ROOT.resolve())
    if target.exists():
        return target
    # 只为读取旧轮次保留兼容；新 suite 永远直接落在 output/story 下。
    legacy = (LEGACY_SUITES_ROOT / suite_id).resolve()
    legacy.relative_to(LEGACY_SUITES_ROOT.resolve())
    return legacy if legacy.exists() else target


def set_suite_environment(suite: dict[str, Any]) -> None:
    bundle_root = str(suite.get("bundle_root") or "").strip()
    if bundle_root:
        os.environ[run_layout.RUN_BUNDLE_ENV] = bundle_root
        os.environ[run_layout.BUNDLE_ALLOWED_ROOT_ENV] = str(OUT_ROOT.resolve())
        control_root = str(suite.get("control_root") or "").strip()
        if control_root:
            os.environ[run_layout.RUN_CONTROL_ENV] = str(Path(control_root).resolve())
        else:
            os.environ.pop(run_layout.RUN_CONTROL_ENV, None)
    else:
        os.environ.pop(run_layout.RUN_BUNDLE_ENV, None)
        os.environ.pop(run_layout.RUN_CONTROL_ENV, None)
    os.environ.pop("STORY_FEATURE_ARCHIVE_ROOT", None)


def migrate_existing_features(bundle_root: Path) -> dict[str, Any]:
    """Move all existing features into one timestamped archive outside the repo."""
    source_root = FEATURES_ROOT.resolve()
    if source_root == REPO_ROOT or not source_root.is_relative_to(REPO_ROOT):
        raise SystemExit(f"[multi] 非法 doc/features 根: {source_root}")
    archive_root = FEATURE_ARCHIVE_ROOT.resolve()
    if archive_root == Path(archive_root.anchor) or archive_root == REPO_ROOT.resolve() \
            or archive_root.is_relative_to(REPO_ROOT.resolve()):
        raise SystemExit(f"[multi] feature 归档根必须是代码仓外的安全目录: {archive_root}")
    children = sorted(source_root.iterdir()) if source_root.exists() else []
    if not children:
        return {
            "status": "no_existing_features",
            "source_root": str(source_root),
            "archive_root": str(archive_root),
            "destination_root": None,
            "moved": [],
            "moved_at": now(),
        }
    stamp = datetime.now().strftime(FEATURE_ARCHIVE_TIMESTAMP_FORMAT)
    destination_root = archive_root / f"Story-Features-{stamp}"
    if destination_root.exists():
        suffix = re.sub(r"[^A-Za-z0-9._-]", "-", bundle_root.name).strip(".-") or "suite"
        destination_root = archive_root / f"Story-Features-{stamp}-{suffix}"
    counter = 2
    base_destination = destination_root
    while destination_root.exists():
        destination_root = archive_root / f"{base_destination.name}-{counter}"
        counter += 1
    destination_root.mkdir(parents=True)
    moved: list[dict[str, Any]] = []
    for child in children:
        if child.is_symlink():
            raise SystemExit(f"[multi] 拒绝迁移 doc/features 下的软链接: {child}")
        target = destination_root / child.name
        if target.exists():
            raise SystemExit(f"[multi] 归档目标已存在，拒绝覆盖: {target}")
        file_count = sum(1 for item in child.rglob("*") if item.is_file()) \
            if child.is_dir() else 1
        shutil.move(str(child), str(target))
        moved.append({
            "name": child.name,
            "source": str(child),
            "target": str(target),
            "file_count": file_count,
        })
    return {
        "status": "completed",
        "source_root": str(source_root),
        "archive_root": str(archive_root),
        "destination_root": str(destination_root),
        "moved": moved,
        "moved_at": now(),
    }


# 进程创建时间比 state 记的启动时刻晚这么多，就不可能是同一个进程了。
# 放宽到一分钟：worker 先起、state 后写，两者相差通常在秒级。
PID_REUSE_TOLERANCE_SEC = 60.0


def _process_create_epoch(pid: int) -> float | None:
    """进程的创建时刻（epoch 秒）。拿不到返回 None —— **拿不到不等于复用**。"""
    if sys.platform == "win32":
        access = 0x1000 | 0x0400
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(access, False, int(pid))
        if not handle:
            return None
        try:
            creation = ctypes.c_ulonglong()
            exit_t = ctypes.c_ulonglong()
            kernel_t = ctypes.c_ulonglong()
            user_t = ctypes.c_ulonglong()
            ok = kernel32.GetProcessTimes(
                handle, ctypes.byref(creation), ctypes.byref(exit_t),
                ctypes.byref(kernel_t), ctypes.byref(user_t))
            if not ok or not creation.value:
                return None
            # FILETIME：100 纳秒为单位，起点 1601-01-01；转 Unix epoch
            return creation.value / 10_000_000.0 - 11_644_473_600.0
        finally:
            kernel32.CloseHandle(handle)
    try:
        with open(f"/proc/{int(pid)}/stat", encoding="utf-8") as handle:
            fields = handle.read().rsplit(")", 1)[-1].split()
        ticks = float(fields[19])                       # starttime，第 22 个字段
        with open("/proc/uptime", encoding="utf-8") as handle:
            uptime = float(handle.read().split()[0])
        hz = os.sysconf("SC_CLK_TCK")
        return time.time() - uptime + ticks / hz
    except (OSError, ValueError, IndexError, AttributeError):
        return None


def _pid_alive(pid: int | None, started_at: str | None = None) -> bool:
    """这个 pid 上跑的，还是不是当初那个进程。

    **只比 pid 号会被复用骗到**：几天前的 worker 早退出了，系统把号发给了别人，
    而那个别人活得好好的。所以拿到 `started_at` 时再比一次创建时间——
    进程比记录晚生一分钟以上，它就是另一个进程。

    `started_at` 缺失或创建时间读不出来时退回只比 pid：**宁可判成活的**，
    误判成活只是拦住清理（有人来看），误判成死会删掉正在跑的现场。
    """
    if not pid:
        return False
    running = False
    if sys.platform == "win32":
        access = 0x1000 | 0x0400
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(access, False, int(pid))
        if handle:
            exit_code = ctypes.c_ulong()
            try:
                if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    running = exit_code.value == 259
            finally:
                kernel32.CloseHandle(handle)
        else:
            try:
                os.kill(int(pid), 0)
                running = True
            except PermissionError:
                running = True
            except (OSError, ProcessLookupError):
                running = False
    else:
        try:
            os.kill(int(pid), 0)
            running = True
        except (OSError, ProcessLookupError):
            running = False
    if not running or not started_at:
        return running
    recorded = _parse_epoch(started_at)
    created = _process_create_epoch(int(pid))
    if recorded is None or created is None:
        return True
    return created <= recorded + PID_REUSE_TOLERANCE_SEC


def _parse_epoch(text: str) -> float | None:
    """state 里的时刻字符串 → epoch 秒。两种写法都认，认不出返回 None。"""
    raw = str(text or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw[:19], fmt).timestamp()
        except ValueError:
            continue
    return None


def _process_inventory() -> tuple[bool, list[dict[str, Any]], str | None]:
    """Return process command lines for fail-closed orphan ownership checks."""
    if sys.platform == "win32":
        command = [
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            "Get-CimInstance Win32_Process | Select-Object ProcessId,CommandLine "
            "| ConvertTo-Json -Compress",
        ]
    else:
        command = ["ps", "-eo", "pid=,args="]
    result = subprocess.run(command, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", check=False)
    if result.returncode != 0:
        return False, [], (result.stderr or result.stdout or "进程枚举失败").strip()
    if sys.platform == "win32":
        try:
            payload = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as exc:
            return False, [], f"进程枚举 JSON 非法: {exc}"
        rows = payload if isinstance(payload, list) else [payload]
        return True, [
            {"pid": row.get("ProcessId"), "command": row.get("CommandLine") or ""}
            for row in rows if isinstance(row, dict)
        ], None
    rows = []
    for line in result.stdout.splitlines():
        parts = line.strip().split(maxsplit=1)
        if not parts:
            continue
        rows.append({"pid": int(parts[0]), "command": parts[1] if len(parts) > 1 else ""})
    return True, rows, None


def _clear_readonly_and_retry(function: Any, path: str, _error: Any) -> None:
    os.chmod(path, 0o700)
    function(path)


def _remove_tree_with_recovery(path: Path, *, attempts: int = 4) -> list[dict[str, Any]]:
    """Remove a preflight-approved tree, recovering Windows snapshot residue."""
    evidence: list[dict[str, Any]] = []
    delays = (0.0, 0.15, 0.4, 0.8)
    for attempt in range(1, attempts + 1):
        item: dict[str, Any] = {"attempt": attempt, "at": now()}
        inventory_ok, processes, inventory_error = _process_inventory()
        matches = [row for row in processes if str(path).lower() in str(
            row.get("command") or "").lower()]
        item.update({"process_inventory_ok": inventory_ok,
                     "process_inventory_error": inventory_error,
                     "process_matches": matches})
        if not inventory_ok or matches:
            item["status"] = "blocked_process_recheck"
            evidence.append(item)
            raise OSError(f"删除前进程复核失败或仍有进程引用: {path}")
        try:
            if path.exists():
                shutil.rmtree(path, onexc=_clear_readonly_and_retry)
            item["status"] = "deleted"
            item["remaining"] = []
            evidence.append(item)
            return evidence
        except OSError as exc:
            remaining = []
            if path.exists():
                try:
                    remaining = [str(item.relative_to(path))
                                 for item in list(path.rglob("*"))[-50:]]
                except OSError:
                    remaining = ["<enumeration-failed>"]
            item.update({"status": "retry", "error": str(exc),
                         "remaining": remaining})
            evidence.append(item)
            if attempt >= attempts:
                raise
            time.sleep(delays[min(attempt, len(delays) - 1)])
    return evidence


def _state_evidence(output_path: Path) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    if not output_path.is_dir():
        return evidence
    for state_path in sorted(output_path.rglob("state.json")):
        state = read_json(state_path)
        if not isinstance(state, dict):
            continue
        pid = int(state.get("pid")) if state.get("pid") else None
        lease_expires = float(state.get("lease_expires_epoch") or 0)
        status = str(state.get("status") or "")
        alive = _pid_alive(pid, state.get("started_at"))
        lease_active = lease_expires > time.time()
        active = alive or (lease_active and status not in TERMINAL_STATUS)
        evidence.append({
            "path": str(state_path), "status": status, "pid": pid,
            "pid_alive": alive, "lease_expires_epoch": lease_expires,
            "lease_active": lease_active, "active": active,
        })
    return evidence


def cleanup_previous_test_runs(new_bundle_root: Path, new_suite_id: str) -> dict[str, Any]:
    """Delete owned historical workspace/output pairs before feature migration."""
    output_root = OUT_ROOT.resolve()
    workspace_parent = (Path(tempfile.gettempdir()) / "sw-story").resolve()
    system_parent = (Path(tempfile.gettempdir()) / REQUIREMENT_SYSTEM_SIBLING).resolve()
    new_bundle_root = new_bundle_root.resolve()
    inventory_ok, processes, inventory_error = _process_inventory()
    names: set[str] = set()
    if output_root.is_dir():
        names.update(path.name for path in output_root.iterdir()
                     if path.is_dir() and path.resolve() != new_bundle_root)
    if workspace_parent.is_dir():
        names.update(path.name for path in workspace_parent.iterdir() if path.is_dir())
    # 需求系统快照在 suite 树之外（sw-sys/<suite>-<hash>），剥掉摘要后缀按 suite 名收进来
    if system_parent.is_dir():
        names.update(path.name.rsplit("-", 1)[0]
                     for path in system_parent.iterdir() if path.is_dir())
    report: dict[str, Any] = {
        "schema_version": 1, "new_suite_id": new_suite_id,
        "output_root": str(output_root), "workspace_root": str(workspace_parent),
        "process_inventory_ok": inventory_ok,
        "process_inventory_error": inventory_error,
        "targets": [], "ignored": [], "status": "preflight", "started_at": now(),
    }
    blockers: list[str] = []
    for name in sorted(names):
        output_path = (output_root / name).resolve()
        workspace_path = (workspace_parent / name).resolve()
        output_exists = output_path.is_dir()
        workspace_exists = workspace_path.is_dir()
        suite_file = output_path / "suite.json"
        suite = read_json(suite_file)
        owned = isinstance(suite, dict) or bool(OWNED_SUITE_DIR.fullmatch(name))
        if not owned:
            report["ignored"].append({"name": name, "reason": "not_story_suite"})
            continue
        target = {
            "suite_id": name, "output": str(output_path) if output_exists else None,
            "workspace": str(workspace_path) if workspace_exists else None,
            "has_suite_json": isinstance(suite, dict), "ownership": "suite_json"
            if isinstance(suite, dict) else "orphan_name_pattern", "status": "checked",
        }
        report["targets"].append(target)
        if output_path.parent != output_root or workspace_path.parent != workspace_parent:
            target["status"] = "blocked_path_boundary"
            blockers.append(f"{name}: path boundary")
            continue
        raw_output = output_root / name
        raw_workspace = workspace_parent / name
        if (raw_output.exists() and raw_output.is_symlink()) \
                or (raw_workspace.exists() and raw_workspace.is_symlink()):
            target["status"] = "blocked_symlink"
            blockers.append(f"{name}: symlink")
            continue
        states = _state_evidence(output_path)
        target["state_evidence"] = states
        if any(item["active"] for item in states):
            target["status"] = "blocked_active_state_or_lease"
            blockers.append(f"{name}: active state, pid or lease")
            continue
        if isinstance(suite, dict):
            if str(suite.get("suite_id") or "") != name:
                target["status"] = "blocked_suite_id_mismatch"
                blockers.append(f"{name}: suite id mismatch")
                continue
            statuses = [str(item.get("status")) for item in
                        (suite.get("case_states") or {}).values()
                        if isinstance(item, dict)]
            pids = [int(item.get("worker_pid")) for item in
                    (suite.get("case_states") or {}).values()
                    if isinstance(item, dict) and item.get("worker_pid")]
            live_pids = [
                int(item["worker_pid"]) for item in
                (suite.get("case_states") or {}).values()
                if isinstance(item, dict) and item.get("worker_pid")
                and _pid_alive(int(item["worker_pid"]), item.get("started_at"))
            ]
            target.update({"suite_status": suite.get("status"),
                           "case_statuses": statuses, "worker_pids": pids,
                           "live_worker_pids": live_pids})
            terminal_suite = str(suite.get("status")) in {"finished", "failed", "stopped"}
            if not terminal_suite or live_pids:
                target["status"] = "blocked_active_suite"
                blockers.append(f"{name}: active suite or worker")
                continue
        else:
            if not inventory_ok:
                target["status"] = "blocked_process_inventory"
                blockers.append(f"{name}: process inventory unavailable")
                continue
            needles = [name.lower()]
            if output_exists:
                needles.append(str(output_path).lower())
            if workspace_exists:
                needles.append(str(workspace_path).lower())
            matches = [row for row in processes if any(
                needle in str(row.get("command") or "").lower() for needle in needles)]
            target["process_matches"] = matches
            if matches:
                target["status"] = "blocked_orphan_process"
                blockers.append(f"{name}: orphan process")
                continue
        target["status"] = "ready_to_delete"
    if blockers:
        report["status"] = "blocked"
        report["blockers"] = blockers
        report["finished_at"] = now()
        write_json(new_bundle_root / "previous-run-cleanup.json", report)
        raise SystemExit("[multi] 历史测试现场清理预检失败：" + "；".join(blockers))
    report["status"] = "deleting"
    write_json(new_bundle_root / "previous-run-cleanup.json", report)
    cleanup_warnings: list[str] = []
    for target in report["targets"]:
        removed: list[str] = []
        target["deletion_attempts"] = []
        try:
            workspace_text = target.get("workspace")
            if workspace_text and Path(workspace_text).is_dir():
                attempts = _remove_tree_with_recovery(Path(workspace_text))
                target["deletion_attempts"].append(
                    {"path": workspace_text, "attempts": attempts})
                removed.append(workspace_text)
            output_text = target.get("output")
            if output_text and Path(output_text).is_dir():
                attempts = _remove_tree_with_recovery(Path(output_text))
                target["deletion_attempts"].append(
                    {"path": output_text, "attempts": attempts})
                removed.append(output_text)
            if system_parent.is_dir():
                for system_path in sorted(system_parent.glob(
                        f"{target['suite_id']}-*")):
                    if not system_path.is_dir():
                        continue
                    attempts = _remove_tree_with_recovery(system_path)
                    target["deletion_attempts"].append(
                        {"path": str(system_path), "attempts": attempts})
                    removed.append(str(system_path))
            target["status"] = "deleted"
            target["removed"] = removed
        except OSError as exc:
            target["status"] = "retained_cleanup_warning"
            target["warning"] = str(exc)
            cleanup_warnings.append(f"{target['suite_id']}: {exc}")
        write_json(new_bundle_root / "previous-run-cleanup.json", report)
    report["status"] = "completed_with_warnings" if cleanup_warnings else "completed"
    report["warnings"] = cleanup_warnings
    report["errors"] = []
    report["finished_at"] = now()
    write_json(new_bundle_root / "previous-run-cleanup.json", report)
    return report


def append_event(suite: dict[str, Any], name: str, **details: Any) -> None:
    events = suite.setdefault("events", [])
    events.append({"at": now(), "name": name, **details})
    if len(events) > 200:
        del events[:-200]


def append_case_observation(suite: dict[str, Any], case_id: str,
                            observation: dict[str, Any]) -> None:
    """Persist an uncapped per-Case observation outside suite.json."""
    case_root = Path(str(suite["bundle_root"])) / "cases" / case_id
    path = case_root / "observations.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"at": now(), "case": case_id, **observation}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + "\n")


def save_suite(path: Path, suite: dict[str, Any]) -> None:
    suite["updated_at"] = now()
    write_json(path, suite)


def load_suite(suite_id: str) -> tuple[Path, dict[str, Any]]:
    path = suite_path(suite_id)
    suite = read_json(path / "suite.json")
    if not isinstance(suite, dict):
        raise SystemExit(f"[multi] 找不到 suite: {suite_id}")
    set_suite_environment(suite)
    return path, suite


def invoke_case(case_id: str, command: str, *args: str,
                suite: dict[str, Any] | None = None) -> tuple[int, dict[str, Any] | None, str, str]:
    """Call the existing runner without an outer timeout or a pipe.

    The runner owns soft/hard timeout behavior.  This function only waits for
    its control command, and polling concurrency is provided by the suite
    scheduler rather than by shell pipelines.
    """
    environment = (dict(os.environ) if suite is None
                   else suite_environment(suite, case_id))
    run_script = RUN_CASE
    cwd = REPO_ROOT
    if suite is not None:
        case = suite.get("case_states", {}).get(case_id) or {}
        workspace_text = str(case.get("workspace") or "").strip()
        if workspace_text:
            workspace = Path(workspace_text).resolve()
            expected_root = Path(str(suite.get("workspace_root") or workspace.parent)).resolve()
            if not workspace.is_relative_to(expected_root) or not workspace.is_dir():
                raise SystemExit(f"[multi] 非法 Case workspace: {workspace}")
            cwd = workspace
    result = subprocess.run(
        [sys.executable, str(run_script), case_id, command, *args],
        cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
        env=environment,
    )
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    payload: dict[str, Any] | None = None
    if stdout:
        try:
            value = json.loads(stdout)
            if isinstance(value, dict):
                payload = value
        except json.JSONDecodeError:
            pass
    return result.returncode, payload, stdout, stderr


def suite_environment(suite: dict[str, Any], case_id: str | None = None) -> dict[str, str]:
    environment = dict(os.environ)
    bundle_root = str(suite.get("bundle_root") or "").strip()
    if bundle_root:
        environment[run_layout.RUN_BUNDLE_ENV] = bundle_root
        environment[run_layout.BUNDLE_ALLOWED_ROOT_ENV] = str(OUT_ROOT.resolve())
        control_root = str(suite.get("control_root") or "").strip()
        if control_root:
            environment[run_layout.RUN_CONTROL_ENV] = str(Path(control_root).resolve())
        else:
            environment.pop(run_layout.RUN_CONTROL_ENV, None)
    environment.pop("STORY_FEATURE_ARCHIVE_ROOT", None)
    environment.pop(REQUIREMENT_SYSTEM_ENV, None)
    if case_id:
        case = suite.get("case_states", {}).get(case_id) or {}
        workspace = str(case.get("workspace") or "").strip()
        if workspace:
            environment["STORY_WORKSPACE_ROOT"] = str(Path(workspace).resolve())
            environment["STORY_ISOLATED_WORKSPACE"] = "1"
            # 需求系统指向本 Case 自己那份快照——它在 workspace **之外**，
            # 被测侧只能从这个环境变量知道它在哪。没有快照的 Case 不设这个变量：
            # 让 `story.js` 自己报「系统不可达」，比指向一个空目录报「查无此单」诚实。
            workspace_root = Path(str(suite.get("workspace_root")
                                      or Path(workspace).resolve().parent))
            system = requirement_system_path(workspace_root, case_id)
            if system.is_dir():
                environment[REQUIREMENT_SYSTEM_ENV] = str(system)
    else:
        environment.pop("STORY_WORKSPACE_ROOT", None)
        environment.pop("STORY_ISOLATED_WORKSPACE", None)
    # **这个变量绝不能空着交出去。** 空着 `story.js` 会落到它的默认目录
    # （`test/story/requirement-system`）——那里现在装着**人手跑用的**那套单据
    # （`bootstrap_local_story.py` 放的）。装置一旦读到它，测的就不是本 Case 的输入了，
    # 而且一声不吭。所以没有快照时显式指向一个保证不存在的路径：
    # `story.js` 照旧报「需求系统不可达」，那是原本就要的诚实失败。
    environment.setdefault(REQUIREMENT_SYSTEM_ENV, NO_REQUIREMENT_SYSTEM)
    return environment


def active_records(suite: dict[str, Any]) -> list[dict[str, Any]]:
    records = [refresh_record(record) for record in suite.get("case_states", {}).values()]
    return [record for record in records if record.get("status") in ACTIVE_STATUS]


def start_block_reason(case: dict[str, Any], suite: dict[str, Any]) -> str | None:
    for dependency in case.get("wait_for_cases", []):
        dependency_record = suite.get("case_states", {}).get(dependency)
        if dependency_record and dependency_record.get("status") not in TERMINAL_STATUS:
            return f"continuation_barrier:{dependency}"
    active = active_records(suite)
    if len(active) >= int(suite["jobs"]):
        return "jobs_limit"
    for other in active:
        if other["case"] == case["case"]:
            return "case_already_active"
        if other["feature"] == case["feature"]:
            return f"same_feature:{other['case']}"
    return None


def start_one(case: dict[str, Any], suite: dict[str, Any]) -> None:
    """Start one Case and confirm it before the scheduler advances.

    Initial starts are deliberately serial even though confirmed workers run
    concurrently.  A lost control response is recovered by adopting the
    matching active run; otherwise the bounded retry history remains evidence.
    """
    case_id = str(case["case"])
    selected = select_healthy_cli(suite, int(case.get("cli_config_index") or 0))
    if selected is None:
        case["status"] = "cli_config_exhausted"
        case["retry_finalized"] = True
        case["retry_state"] = {"phase": "exhausted",
                               "reason": "no_healthy_cli_configuration",
                               "at": now()}
        case["last_error"] = {"failure_kind": "auth_required",
                              "reason": "no_healthy_cli_configuration"}
        return
    config_index, config_id = selected
    case["cli_config_index"] = config_index
    case["cli_config_id"] = config_id
    if not case.get("workspace"):
        try:
            create_case_workspace(suite, case)
        except (OSError, SystemExit) as exc:
            case["status"] = "coordinator_start_failed"
            case["last_error"] = {"workspace": str(exc)}
            append_event(suite, "case_workspace_failed", case=case_id, error=str(exc))
            return
    override_args: list[str] = []
    if case.get("requested_start_phase") and case["requested_start_phase"] != case.get("start_phase"):
        override_args.extend(("--start-phase", str(case["requested_start_phase"])))
    if case.get("requested_end_phase"):
        override_args.extend(("--end-phase", str(case["requested_end_phase"])))
    override_args.extend(("--cli-config", config_id))
    history = case.setdefault("start_history", [])
    for attempt in range(1, START_MAX_ATTEMPTS + 1):
        case["start_attempts"] = attempt
        returncode, payload, stdout, stderr = invoke_case(
            case_id, "start", *override_args, suite=suite)
        case["last_poll_at"] = now()
        entry = {
            "attempt": attempt, "at": now(), "returncode": returncode,
            "stdout": stdout[-4000:], "stderr": stderr[-4000:],
        }
        if returncode == 0 and payload and payload.get("ok") is not False \
                and payload.get("run_id"):
            case["status"] = str(payload.get("status") or "starting")
            case["run_id"] = payload.get("run_id")
            case["worker_pid"] = payload.get("worker_pid")
            case["last_error"] = None
            attempt = {
                "attempt": len(case.setdefault("attempts", [])) + 1,
                "cli_config_id": config_id,
                "run_id": case["run_id"], "started_at": now(),
                "status": case["status"],
            }
            case["attempts"].append(attempt)
            case["current_attempt"] = attempt["attempt"]
            entry["result"] = "confirmed"
            entry["run_id"] = case["run_id"]
            history.append(entry)
            append_event(suite, "case_started", case=case_id,
                         attempt=attempt, run_id=case.get("run_id"),
                         status=case.get("status"))
            append_case_observation(suite, case_id, {
                "kind": "startup", "result": "confirmed", **entry})
            refresh_record(case)
            return

        # The worker may have started even when its control response was lost.
        adopted = run_pointer_state(case_id)
        if adopted and adopted.get("status") in ACTIVE_STATUS and adopted.get("run_id"):
            case["status"] = str(adopted["status"])
            case["run_id"] = adopted.get("run_id")
            case["worker_pid"] = adopted.get("pid")
            case["last_error"] = None
            attempt_record = {
                "attempt": len(case.setdefault("attempts", [])) + 1,
                "cli_config_id": config_id,
                "run_id": case["run_id"], "started_at": now(),
                "status": case["status"], "start_recovered": True,
            }
            case["attempts"].append(attempt_record)
            case["current_attempt"] = attempt_record["attempt"]
            entry["result"] = "adopted_active_run"
            entry["run_id"] = case["run_id"]
            history.append(entry)
            append_event(suite, "case_start_recovered", case=case_id,
                         attempt=attempt, run_id=case.get("run_id"))
            append_case_observation(suite, case_id, {
                "kind": "startup", "result": "adopted_active_run", **entry})
            return

        entry["result"] = "retry" if attempt < START_MAX_ATTEMPTS else "exhausted"
        history.append(entry)
        append_event(suite, "case_start_attempt_failed", case=case_id,
                     attempt=attempt, returncode=returncode,
                     result=entry["result"])
        append_case_observation(suite, case_id, {
            "kind": "startup", **entry})

    case["status"] = "coordinator_start_failed"
    case["last_error"] = history[-1] if history else {"error": "start_failed"}
    append_event(suite, "case_start_failed", case=case_id,
                 attempts=START_MAX_ATTEMPTS)


def is_new_gate(record: dict[str, Any]) -> bool:
    """当前等待的这一关，是不是还没回过？

    判据是关卡编号：`last_awaiting.turn` 与 `last_replied_turn` 不同即为新关卡。
    编号是被测流程自己给的，不依赖协调器是否恰好观测到状态跳变。
    """
    turn = (record.get("last_awaiting") or {}).get("turn")
    if turn is None:
        return False
    return turn != record.get("last_replied_turn")


def request_host_reply(record: dict[str, Any], suite: dict[str, Any]) -> None:
    """每一关都交给宿主回答，并把「这一关按规划本该表达什么」一并交出去。

    **脚本不再自动应答。** 上一版是「三重比对全等就自动投逐字原话，否则回落给宿主」，
    两个后果都在实跑里出现过：

      ① `expected_turn` 是绝对序号，模型多问一关，从那一关起后面**全部**条目失配，
         永久回落——设计好的话术被大面积跳过，而没有任何信号说跳了几条
         （实测一轮：五条脚本只投出三条，评审意见那条从头到尾没排上）；
      ② 回落时只给宿主「模型说了什么」，不给「这一关本该说什么」，宿主要自己去翻
         脚本才知道；翻漏了就临场发挥，观测到的于是掺进了宿主自己的话。

    现在的分工：**脚本是需求方的立场，不是应答器。** 它写明这一关需求方持什么立场、
    该把哪份材料交出去；宿主按当时的情境自然地把那个意思说出来，不逐字照抄——
    真实的需求方本来就不会两次说出一模一样的句子。

    模型没有提问、只是在自言自语地推进时，宿主给一句中性的推进回复，
    **不注入任何做法或写作指引**——那些正是要观测的东西。

    15 秒 / 120 秒的 heartbeat 正是为这件事设的：交互期让宿主及时接话，
    自动化期退回常规观测。自动应答架空的就是这个设计。
    """
    if record.get("status") != WAITING_STATUS:
        return
    script = list(record.get("interaction_script") or [])
    index = int(record.get("interaction_index") or 0)
    awaiting = record.get("last_awaiting") or {}
    prompt_text = awaiting.get("prompt") or awaiting.get("message") or ""
    planned = script[index] if index < len(script) else None
    request = {
        "case": record["case"],
        "turn": awaiting.get("turn"),
        "kind": awaiting.get("kind"),
        "model_prompt": prompt_text,
        # question 是给宿主**当轮就能回**的那份原文：只给状态、要宿主再去翻 runlog，
        # 一轮观测就变成两轮，等待时间凭空翻倍（实测一次空等约 10 分钟）。
        "question": str(prompt_text)[:1200],
        "case_inputs_hint": case_public_inputs(record),
        # 规划里下一条还没说出口的立场——宿主据它决定这一关表达什么意思。
        # 关卡编号对不对得上不再决定任何事，只作参考。
        "planned_step_id": (planned or {}).get("id"),
        "planned_intent": str((planned or {}).get("text") or "") or None,
        "planned_deliver": list((planned or {}).get("deliver") or []),
        "planned_phase": (planned or {}).get("expected_phase"),
        "planned_turn": (planned or {}).get("expected_turn"),
        "script_cursor": f"{index}/{len(script)}",
        "reply": None,
        # 「规划走完了」和「这个 Case 本来就没写规划」是两回事，分开报。
        "reason": ("host_reply_required" if planned
                   else "plan_exhausted" if script else "no_plan_for_this_case"),
        "detected_at": now(),
        "reply_status": "adaptive_reply_required",
    }
    record["last_reply_status"] = "adaptive_reply_required"
    record["last_reply_text"] = None
    record["last_adaptive_request"] = request
    record["adaptive_reply_count"] = (
        int(record.get("adaptive_reply_count") or 0) + 1)
    record["interaction_state"] = "adaptive_reply_required"
    record["automation_observation_state"] = "waiting_for_adaptive_reply"
    append_event(suite, "adaptive_reply_required", **request)
    append_case_observation(suite, str(record["case"]), {
        "kind": "interaction", **request})


def record_delivery(record: dict[str, Any], delivered: list[Any]) -> None:
    """把「哪几份补料已经投出去了」记在 Case 上——待投清单是观测项，不是配置。"""
    if not delivered:
        return
    names = [str(item) for item in delivered]
    pending = [name for name in (record.get("supplements_pending") or [])
               if name not in names]
    record["supplements_pending"] = pending
    record["supplements_delivered"] = sorted(
        {*(record.get("supplements_delivered") or []), *names})


def schedule_pending(suite: dict[str, Any]) -> None:
    """Start as many safe pending cases as the current phase slot allows."""
    for case in suite.get("case_states", {}).values():
        refresh_record(case)
    for case in suite.get("case_states", {}).values():
        if case.get("status") != "pending":
            continue
        reason = start_block_reason(case, suite)
        case["blocked_by"] = reason
        if reason:
            continue
        start_one(case, suite)


def _case_is_stably_automatic(record: dict[str, Any]) -> bool:
    status = str(record.get("status") or "")
    if not record.get("spec_entered_at"):
        return False
    if status in TERMINAL_STATUS:
        return True
    current = str(record.get("current_phase") or record.get("last_phase") or "")
    return status == "running" and current in PHASE_ORDER


def suite_automation_ready(suite: dict[str, Any]) -> bool:
    stability = suite.get("automation_stability") or {}
    return bool(stability.get("ready_at")) and all(
        _case_is_stably_automatic(record)
        for record in suite.get("case_states", {}).values()
    )


def update_automation_stability(suite: dict[str, Any],
                                results: list[dict[str, Any]]) -> None:
    """Require two complete successful 15-second rounds before 120-second mode."""
    stability = suite.setdefault("automation_stability", {
        "required_confirmations": 2, "consecutive_confirmations": 0,
        "last_confirmation_at": None, "ready_at": None, "cases": {},
    })
    required = int(stability.get("required_confirmations") or 2)
    records = list(suite.get("case_states", {}).values())
    nonterminal = [record for record in records
                   if record.get("status") not in TERMINAL_STATUS]
    result_map = {str(result.get("case")): result for result in results}
    all_polled = all(str(record["case"]) in result_map for record in nonterminal)
    all_success = all(
        result_map[str(record["case"])].get("returncode") == 0
        and result_map[str(record["case"])].get("status")
        for record in nonterminal if str(record["case"]) in result_map
    )
    stable = bool(records) and all_polled and all_success and all(
        _case_is_stably_automatic(record) for record in records)
    stability["cases"] = {
        str(record["case"]): {
            "run_id": record.get("run_id"), "status": record.get("status"),
            "last_phase": record.get("last_phase"),
            "current_phase": record.get("current_phase"),
            "highest_phase_reached": record.get("highest_phase_reached"),
            "phase_source": record.get("phase_source"),
            "spec_entered_at": record.get("spec_entered_at"),
            "stable": _case_is_stably_automatic(record),
        }
        for record in records
    }
    if stable:
        confirmation_epoch = time.time()
        previous_epoch = float(stability.get("last_confirmation_epoch") or 0)
        if previous_epoch and confirmation_epoch - previous_epoch < INTERACTION_INTERVAL_SEC:
            return
        stability["consecutive_confirmations"] = min(
            required, int(stability.get("consecutive_confirmations") or 0) + 1)
        stability["last_confirmation_at"] = now()
        stability["last_confirmation_epoch"] = confirmation_epoch
        if stability["consecutive_confirmations"] >= required \
                and not stability.get("ready_at"):
            stability["ready_at"] = now()
            append_event(suite, "automation_stability_ready",
                         confirmations=stability["consecutive_confirmations"])
    else:
        was_ready = bool(stability.get("ready_at"))
        stability["consecutive_confirmations"] = 0
        stability["last_confirmation_at"] = None
        stability["last_confirmation_epoch"] = None
        stability["ready_at"] = None
        if was_ready:
            append_event(suite, "automation_stability_lost")


def poll_one(record: dict[str, Any], wait_sec: int, max_chars: int,
             suite: dict[str, Any]) -> dict[str, Any]:
    case_id = str(record["case"])
    automation_phase = suite_automation_ready(suite)
    cadence = AUTOMATION_INTERVAL_SEC if automation_phase else INTERACTION_INTERVAL_SEC
    requested_wait = 0 if record.get("status") == WAITING_STATUS or wait_sec == 0 \
        else cadence
    returncode, payload, stdout, stderr = invoke_case(
        case_id, "poll", "--cursor", str(record.get("cursor", 0)),
        "--model-cursor", str(record.get("model_cursor", 0)),
        "--wait-sec", str(requested_wait), "--max-chars", str(max_chars),
        suite=suite,
    )
    result: dict[str, Any] = {"case": case_id, "returncode": returncode}
    if payload:
        run = payload.get("run") or {}
        result.update({
            "status": run.get("status"),
            "last_phase": run.get("last_phase"),
            "current_phase": run.get("current_phase"),
            "highest_phase_reached": run.get("highest_phase_reached"),
            "phase_source": run.get("phase_source"),
            "phase_observed_at": run.get("phase_observed_at"),
            "spec_entered_at": run.get("spec_entered_at"),
            "next_cursor": payload.get("next_cursor"),
            "next_model_cursor": payload.get("next_model_cursor"),
            "awaiting_reply": payload.get("awaiting_reply"),
            "event_count": len(payload.get("events") or []),
            "model_count": len(payload.get("model") or []),
            "has_more": bool(payload.get("has_more")),
            "observation_cadence_sec": cadence,
            "observation_mode": "automation" if automation_phase else "interaction",
        })
    else:
        result["error"] = {"stdout": stdout[-4000:], "stderr": stderr[-4000:]}
    return result


def poll_suite(suite: dict[str, Any], wait_sec: int, max_chars: int,
               *, wait_for_due: bool = False,
               stability_confirmation: bool = True) -> list[dict[str, Any]]:
    process_retryable_failures(suite)
    records = active_records(suite)
    if not records:
        schedule_pending(suite)
        records = active_records(suite)
    records = [record for record in records
               if record.get("status") == WAITING_STATUS
               or record.get("next_observation_at") is None
               or float(record.get("next_observation_at", 0)) <= time.time()]
    if not records and wait_for_due:
        active = active_records(suite)
        deadlines = [float(record["next_observation_at"])
                     for record in active if record.get("next_observation_at") is not None]
        if deadlines:
            time.sleep(min(60, max(1, min(deadlines) - time.time())))
        return []
    if records:
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(int(suite["jobs"]), len(records))) as pool:
            futures = [pool.submit(poll_one, record, wait_sec, max_chars, suite)
                       for record in records]
            results = [future.result() for future in futures]
        for result in results:
            record = suite["case_states"][result["case"]]
            previous_status = record.get("status")
            if result.get("next_cursor") is not None:
                record["cursor"] = result["next_cursor"]
            if result.get("next_model_cursor") is not None:
                record["model_cursor"] = result["next_model_cursor"]
            if result.get("status"):
                record["status"] = result["status"]
            for key in ("last_phase", "current_phase", "highest_phase_reached",
                        "phase_source", "phase_observed_at", "spec_entered_at"):
                if result.get(key) is not None:
                    record[key] = result[key]
            phase_correction = reconcile_record_phase(record)
            record["last_poll_at"] = now()
            record["last_poll"] = {
                key: value for key, value in result.items()
                if key not in {"case"}
            }
            record["last_awaiting"] = result.get("awaiting_reply")
            if result.get("returncode") not in (0, None):
                record["last_error"] = result.get("error") or {
                    "returncode": result.get("returncode")
                }
            current_status = record.get("status")
            record["observation_count"] = int(record.get("observation_count") or 0) + 1
            append_case_observation(suite, str(record["case"]), {
                "kind": "poll",
                "sequence": record["observation_count"],
                "mode": result.get("observation_mode"),
                "cadence_sec": result.get("observation_cadence_sec"),
                "status_before": previous_status,
                "status_after": current_status,
                "last_phase": result.get("last_phase"),
                "current_phase": record.get("current_phase"),
                "highest_phase_reached": record.get("highest_phase_reached"),
                "phase_source": record.get("phase_source"),
                "phase_correction": phase_correction or None,
                "event_count": result.get("event_count"),
                "model_count": result.get("model_count"),
                "has_more": result.get("has_more"),
                "error": result.get("error"),
            })
            if current_status == WAITING_STATUS:
                record["automation_observation_state"] = "waiting_for_human"
                record["next_observation_at"] = None
            elif current_status in TERMINAL_STATUS:
                record["automation_observation_state"] = "completed"
                record["next_observation_at"] = None
            elif previous_status == WAITING_STATUS and current_status in PHASE_ACTIVE_STATUS:
                started = time.time()
                record["automation_observation_state"] = "observing"
                record["automation_observation_started_at"] = now()
                record["automation_observation_until"] = datetime.fromtimestamp(
                    started + AUTOMATION_INTERVAL_SEC).astimezone().isoformat(timespec="seconds")
                record["next_observation_at"] = started
                append_event(suite, "automation_observation_started",
                             case=record["case"], interval_sec=AUTOMATION_INTERVAL_SEC)
            elif current_status in PHASE_ACTIVE_STATUS:
                cadence = (AUTOMATION_INTERVAL_SEC if suite_automation_ready(suite)
                           else INTERACTION_INTERVAL_SEC)
                record["next_observation_at"] = (
                    time.time() if result.get("has_more")
                    else time.time() + cadence)
            refresh_record(record)
            post_refresh_correction = reconcile_record_phase(record)
            if phase_correction or post_refresh_correction:
                append_case_observation(suite, str(record["case"]), {
                    "kind": "phase_corrected",
                    "changes": post_refresh_correction or phase_correction,
                    "source": record.get("phase_source"),
                })
            # **每一关都叫宿主**，有没有规划都叫。带 `interaction_script` 这个前置的是
            # 上一版——那时没有脚本就没人应答，于是没写规划的 Case 会静默挂在
            # awaiting_reply 上，谁也不知道它在等谁。
            if record.get("status") == WAITING_STATUS and is_new_gate(record):
                request_host_reply(record, suite)
        append_event(suite, "poll_completed",
                     cases=[result["case"] for result in results],
                     statuses={result["case"]: result.get("status") for result in results})
        if stability_confirmation:
            update_automation_stability(suite, results)
        process_retryable_failures(suite)
    schedule_pending(suite)
    return [
        {
            "case": record["case"], "feature": record["feature"],
            "requested_start_phase": record.get("requested_start_phase"),
            "requested_end_phase": record.get("requested_end_phase"),
            "effective_phase_scope": record.get("effective_phase_scope"),
            "status": record.get("status"), "run_id": record.get("run_id"),
            "last_phase": record.get("last_phase"),
            "current_phase": record.get("current_phase"),
            "highest_phase_reached": record.get("highest_phase_reached"),
            "phase_source": record.get("phase_source"),
            "awaiting_since": record.get("awaiting_since"),
            "events_idle_sec": record.get("events_idle_sec"),
            "stalled": record.get("stalled"),
            "execution_status": record.get("execution_status"),
            "source_restore_status": record.get("source_restore_status"),
            "blocked_by": record.get("blocked_by"),
        }
        for record in suite["case_states"].values()
    ]


def mechanism_contamination() -> dict[str, Any]:
    """机制层有没有在本轮被改过 —— **哨兵，不是拦截器**。

    隔离已经是唯一形态，被测模型按设计够不着主仓。但「够不着」是设计意图，
    这里核的是事实：主仓 `doc/extensions/` 一旦有未提交改动，本轮读数就不再是
    「那个机制」的读数——它可能是被测方自己改过之后的机制。

    拦不住也不该拦（改动可能来自维护者自己）：它的职责是让这件事**永远不会
    悄悄混进读数**。实测撞到过一次：非隔离那一轮，被测模型改了判据所在目录，
    如果不是 `git status` 恰好露了出来，那一轮的结论会被当成干净的。
    """
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--", "doc/extensions"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(REPO_ROOT))
        dirty = (proc.stdout or "").strip()
    except Exception as exc:  # noqa: BLE001
        return {"checked": False, "reason": str(exc)}
    if not dirty:
        return {"checked": True, "clean": True}
    try:
        diff = subprocess.run(
            ["git", "diff", "--", "doc/extensions"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(REPO_ROOT)).stdout or ""
    except Exception:  # noqa: BLE001
        diff = ""
    return {"checked": True, "clean": False, "status": dirty, "diff": diff}


def finalize_suite_status(suite: dict[str, Any]) -> str:
    for record in suite["case_states"].values():
        refresh_record(record)
    statuses = [str(record.get("status")) for record in suite["case_states"].values()]
    if any(status in ACTIVE_STATUS or status == "pending" for status in statuses):
        return "awaiting_reply" if any(status == WAITING_STATUS for status in statuses) \
            else "running"
    if any(status == "coordinator_start_failed" for status in statuses):
        return "failed"
    if any(record.get("source_restore_status") in {"missing", "failed", "source_restore_failed"}
           for record in suite["case_states"].values()):
        return "failed"
    if any(status not in TERMINAL_STATUS for status in statuses):
        return "failed"
    contamination = mechanism_contamination()
    suite["mechanism_contamination"] = contamination
    if contamination.get("checked") and not contamination.get("clean"):
        return "harness_contaminated"
    return "finished"


def summary(suite: dict[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for record in suite["case_states"].values():
        status = str(record.get("status"))
        counts[status] = counts.get(status, 0) + 1
    return {
        "suite_id": suite["suite_id"],
        "selected_case_count": len(suite.get("case_states", {})),
        "status": suite.get("status"),
        "jobs": suite["jobs"],
        "workspace": str(REPO_ROOT),
        "bundle_root": suite.get("bundle_root"),
        "workspace_template": suite.get("workspace_template"),
        "workspace_root": suite.get("workspace_root"),
        "execution_authorization": suite.get("execution_authorization"),
        "feature_migration": suite.get("feature_migration"),
        "previous_run_cleanup": suite.get("previous_run_cleanup"),
        "workspace_retention": suite.get("workspace_retention"),
        "output_retention": suite.get("output_retention"),
        "automation_stability": suite.get("automation_stability"),
        "phase_policy": suite["scheduler"],
        "counts": counts,
        "cases": [
            {
                "case": record["case"], "feature": record["feature"],
                "workspace": record.get("workspace"),
                "requested_start_phase": record.get("requested_start_phase"),
                "requested_end_phase": record.get("requested_end_phase"),
                "effective_phase_scope": record.get("effective_phase_scope"),
                "status": record.get("status"), "run_id": record.get("run_id"),
                "last_phase": record.get("last_phase"),
                "current_phase": record.get("current_phase"),
                "highest_phase_reached": record.get("highest_phase_reached"),
                "phase_source": record.get("phase_source"),
                "phase_observed_at": record.get("phase_observed_at"),
                "spec_entered_at": record.get("spec_entered_at"),
                "awaiting_since": record.get("awaiting_since"),
            "events_idle_sec": record.get("events_idle_sec"),
            "stalled": record.get("stalled"),
                "execution_status": record.get("execution_status"),
                "source_restore_status": record.get("source_restore_status"),
                "automation_observation_state": record.get("automation_observation_state"),
                "automation_observation_started_at": record.get(
                    "automation_observation_started_at"),
                "automation_observation_until": record.get("automation_observation_until"),
                "blocked_by": record.get("blocked_by"),
            }
            for record in suite["case_states"].values()
        ],
        "updated_at": suite.get("updated_at"),
    }


def ensure_no_external_active(plans: list[CasePlan]) -> None:
    selected = {plan.case_id for plan in plans}
    for case_dir in CASES_ROOT.iterdir():
        if not case_dir.is_dir() or not (case_dir / "case.yaml").is_file():
            continue
        case_id = case_dir.name
        state = run_pointer_state(case_id)
        if not state or state.get("status") in TERMINAL_STATUS:
            continue
        scope = "selected" if case_id in selected else "other"
        raise SystemExit(
            f"[multi] 检测到已有活动 Case：{case_id} ({scope}) "
            f"status={state.get('status')} run_id={state.get('run_id')}；"
            "先用对应 run_case status/stop 处理，拒绝混入当前 suite。")


def create_suite(plans: list[CasePlan], suite_id: str, jobs: int,
                 base_end_phase: str | None = None,
                 continue_case: str | None = None,
                 continue_end_phase: str | None = None,
                 non_sandbox_authorized: bool = False,
                 preserve_current_features: bool = False) -> tuple[Path, dict[str, Any]]:
    if jobs <= 0:
        raise SystemExit("[multi] --jobs 必须大于 0")
    if not non_sandbox_authorized:
        raise SystemExit(
            "[multi] CLI 测试必须显式提供 --authorize-non-sandbox，记录用户授权后才能启动")
    validate_phase_overrides(base_end_phase, continue_case, continue_end_phase, plans)
    if jobs < len(plans):
        raise SystemExit(
            f"[multi] 隔离并行 suite 要求 jobs >= Case 数量（{jobs} < {len(plans)}），"
            "避免把已设计的并行轮次静默降级为排队")
    path = suite_path(suite_id)
    if path.exists():
        raise SystemExit(f"[multi] suite 结果目录已存在，拒绝覆盖: {path}")
    path.mkdir(parents=True)
    if preserve_current_features:
        raise SystemExit(
            "[multi] --preserve-current-features 已停用；正式测试必须先迁移现有 doc/features")
    previous_run_cleanup = cleanup_previous_test_runs(path, suite_id)
    migration = migrate_existing_features(path)
    feature_archive_path = migration.get("destination_root")
    workspace_template, workspace_root = create_workspace_template(path, suite_id)
    plan_map = {plan.case_id: plan for plan in plans}
    suite: dict[str, Any] = {
        "schema_version": 1,
        "suite_id": suite_id,
        "status": "running",
        "started_at": now(),
        "updated_at": now(),
        "jobs": jobs,
        "workspace": str(REPO_ROOT),
        "bundle_root": str(path.resolve()),
        "control_root": str((path / "controls").resolve()),
        "feature_archive_path": feature_archive_path,
        "preserve_current_features": preserve_current_features,
        "workspace_template": str(workspace_template) if workspace_template else None,
        "workspace_root": str(workspace_root) if workspace_root else None,
        "execution_authorization": {
            "non_sandbox": True,
            "granted_by": "user",
            "granted_at": now(),
            "scope": "本轮选定的多 Case CLI 测试及其观测命令",
        },
        "feature_migration": migration,
        "previous_run_cleanup": previous_run_cleanup,
        "workspace_retention": {
            "policy": "retain_until_next_suite_start",
            "status": "active",
            "path": str(workspace_root) if workspace_root else None,
        },
        "output_retention": {
            "policy": "retain_until_next_suite_start",
            "status": "active",
            "path": str(path.resolve()),
        },
        "automation_stability": {
            "required_confirmations": 2,
            "consecutive_confirmations": 0,
            "last_confirmation_at": None,
            "last_confirmation_epoch": None,
            "ready_at": None,
            "cases": {},
        },
        "cli_configuration_group": {
            "configurations": [dict(item) for item in CLI_CONFIGURATIONS],
            "retry_policy": dict(CLI_RETRY_POLICY),
            "health": {
                item["id"]: {
                    "status": "available", "tripped_at": None,
                    "tripped_by_case": None, "tripped_by_run": None,
                }
                for item in CLI_CONFIGURATIONS
            },
        },
        "cases": [plan.case_id for plan in plans],
        "case_plans": [plan.as_dict() for plan in plans],
        "case_states": {},
        "baseline": git_snapshot(),
        "main_source_baseline": snapshot_workspace_sources(REPO_ROOT),
        "scheduler": {
            "mode": "isolated_case_workspaces",
            "shared_current_phase_slot": "isolated_per_case",
            "phase_active_parallelism": jobs,
            "awaiting_reply_parallelism": "allowed",
            "coding_parallelism": jobs,
            "reply_guard": "per_case_workspace",
            "ar_uniqueness": "one_case_one_ar_and_unique_within_suite",
            "interaction_interval_sec": INTERACTION_INTERVAL_SEC,
            "automation_interval_sec": AUTOMATION_INTERVAL_SEC,
            "start_policy": "sequential_confirmed_then_parallel_run",
            "start_max_attempts": START_MAX_ATTEMPTS,
            "post_interaction_observation": "goal_heartbeat_after_entering_spec",
            "base_end_phase_override": base_end_phase,
            "continued_case": continue_case,
            "continued_end_phase": continue_end_phase,
            "same_batch_start": False,
        },
        "events": [],
    }
    for case_id, plan in plan_map.items():
        record = new_case_record(
            plan, requested_end_phase(plan, base_end_phase,
                                      continue_case, continue_end_phase))
        suite["case_states"][case_id] = record
    set_suite_environment(suite)
    Path(suite["control_root"]).mkdir(parents=True, exist_ok=True)
    write_json(path / "feature-migration.json", migration)
    append_event(suite, "suite_created", cases=suite["cases"], jobs=jobs)
    save_suite(path / "suite.json", suite)
    return path, suite


def prepare_suite_preflight(path: Path, suite: dict[str, Any]) -> None:
    """Prepare every isolated workspace before the first model worker starts."""
    checks: dict[str, Any] = {
        "status": "running",
        "suite_id": suite["suite_id"],
        "cases": [],
        "forbidden_workspace_entries": ["output", "test", "tools", ".git",
                                        "doc/features (history)"],
        "checked_at": now(),
    }
    workspace_paths: set[str] = set()
    try:
        for record in suite["case_states"].values():
            if not record.get("workspace"):
                create_case_workspace(suite, record)
            workspace = Path(str(record["workspace"])).resolve()
            if workspace in {Path(str(item)) for item in workspace_paths}:
                raise RuntimeError(f"workspace 重复: {workspace}")
            workspace_paths.add(str(workspace))
            if len(str(workspace)) > 180:
                raise RuntimeError(f"workspace 路径过长: {workspace}")
            boundary = _verify_workspace_boundary(
                workspace, str(record["feature"]))
            record["workspace_status"] = "preflight_pass"
            checks["cases"].append({"case": record["case"], "ar": record["feature"],
                                     "workspace": str(workspace), "status": "pass",
                                     "boundary": boundary,
                                     "case_seeded": record.get("case_seeded", [])})
        checks["status"] = "pass"
        checks["checked_at"] = now()
        append_event(suite, "preflight_pass", cases=checks["cases"])
    except Exception as exc:  # noqa: BLE001 - failure itself is the preflight evidence
        checks["status"] = "fail"
        checks["error"] = str(exc)
        append_event(suite, "preflight_failed", error=str(exc))
        write_json(path / "preflight.json", checks)
        save_suite(path / "suite.json", suite)
        raise SystemExit(f"[multi] preflight 失败：{exc}") from exc
    write_json(path / "preflight.json", checks)
    save_suite(path / "suite.json", suite)


def case_public_inputs(record: dict[str, Any]) -> list[str]:
    """本 Case 的公开输入清单——宿主据此判断怎么回，不必去翻其它 Case 或历史答案。

    列的是**宿主这边备着什么**：需求系统上这张单挂了哪几份材料、手上还有哪几份
    补料没投。不列被测 workspace 里的文件——那是模型正在写的东西，
    宿主以需求方身份回话时看的不是它。
    """
    case_id = str(record.get("case") or "")
    if not case_id:
        return []
    out: list[str] = []
    system = CASES_ROOT / case_id / "system"
    if system.is_dir():
        out.extend(f"需求系统：{path.relative_to(system).as_posix()}"
                   for path in sorted(system.rglob("*.md")))
    for item in record.get("supplements") or []:
        name = str(item.get("file") or "")
        if not name:
            continue
        state = "已投放" if name in (record.get("supplements_delivered") or []) \
            else ("起跑时已在" if item.get("deliver") == "start" else "手上备着，未投")
        out.append(f"补料（{state}）：{name}")
    return out[:12]


def adaptive_requests(suite: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "case": record.get("case"), "feature": record.get("feature"),
        "run_id": record.get("run_id"), **(record.get("last_adaptive_request") or {}),
    } for record in suite.get("case_states", {}).values()
        if record.get("status") == WAITING_STATUS
        and record.get("interaction_state") == "adaptive_reply_required"]


def settle_scripted_interactions(suite: dict[str, Any], max_chars: int) -> None:
    limit = sum(len(record.get("interaction_script") or [])
                for record in suite.get("case_states", {}).values()) + len(
                    suite.get("case_states", {})) + 2
    for _ in range(max(2, limit)):
        waiting = [record for record in suite.get("case_states", {}).values()
                   if record.get("status") == WAITING_STATUS]
        if not waiting or adaptive_requests(suite):
            return
        if any(record.get("last_reply_status") == "rejected" for record in waiting):
            return
        poll_suite(suite, 0, max_chars, stability_confirmation=False)


def interaction_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names = {"scripted_reply_accepted", "scripted_reply_rejected",
             "adaptive_reply_required"}
    return [event for event in events if event.get("name") in names]


def progress_snapshot(suite: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Capture only user-visible Case progress fields for deterministic diffs."""
    return {
        str(record["case"]): {
            "status": record.get("status"),
            "last_phase": record.get("last_phase"),
            "current_phase": record.get("current_phase"),
            "highest_phase_reached": record.get("highest_phase_reached"),
            "phase_source": record.get("phase_source"),
            "interaction_state": record.get("interaction_state"),
            "reply_status": record.get("last_reply_status"),
            "last_error": record.get("last_error"),
            "spec_entered_at": record.get("spec_entered_at"),
        }
        for record in suite.get("case_states", {}).values()
    }


def progress_changes(before: dict[str, dict[str, Any]],
                     suite: dict[str, Any],
                     interactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    after = progress_snapshot(suite)
    changes: list[dict[str, Any]] = []
    for case_id in dict.fromkeys((*before.keys(), *after.keys())):
        old = before.get(case_id, {})
        new = after.get(case_id, {})
        fields = {
            key: {"before": old.get(key), "after": new.get(key)}
            for key in dict.fromkeys((*old.keys(), *new.keys()))
            if old.get(key) != new.get(key)
        }
        if fields:
            changes.append({"kind": "case_progress", "case": case_id,
                            "fields": fields})
    changes.extend({"kind": "interaction", **event} for event in interactions)
    return changes


def control_payload(suite: dict[str, Any], *,
                    interactions: list[dict[str, Any]] | None = None,
                    changes: list[dict[str, Any]] | None = None,
                    read_only: bool = False) -> dict[str, Any]:
    records = list(suite.get("case_states", {}).values())
    terminal = str(suite.get("status") or "") in {"finished", "failed", "stopped"}
    adaptive = adaptive_requests(suite)
    if terminal:
        next_action = "finalize"
    elif adaptive:
        next_action = "reply_then_poll"
    else:
        next_action = "poll_after_interval"
    # 有 Case 在等回话时一律回到最短间隔：等待期的每一秒都是白等的，
    # 而 120 秒节奏下「等待出现」与「宿主看到」之间平均差半个周期。
    any_waiting = any(record.get("status") == WAITING_STATUS for record in records)
    next_interval_sec = None if terminal else (
        INTERACTION_INTERVAL_SEC if (any_waiting or adaptive)
        else (AUTOMATION_INTERVAL_SEC if suite_automation_ready(suite)
              else INTERACTION_INTERVAL_SEC))
    stability = suite.get("automation_stability") or {}
    change_list = changes or []
    return {
        "suite_id": suite.get("suite_id"), "suite_status": suite.get("status"),
        "suite_terminal": terminal, "selected_case_count": len(records),
        "cases": [{
            "case": record.get("case"), "feature": record.get("feature"),
            "run_id": record.get("run_id"), "status": record.get("status"),
            "attempt": record.get("current_attempt"),
            "cli_config_id": record.get("cli_config_id"),
            "failure_kind": record.get("failure_kind"),
            "retry_state": record.get("retry_state"),
            "last_attempt": ((record.get("attempts") or [])[-1]
                             if record.get("attempts") else None),
            "last_phase": record.get("last_phase"),
            "current_phase": record.get("current_phase"),
            "highest_phase_reached": record.get("highest_phase_reached"),
            "phase_source": record.get("phase_source"),
            "phase_observed_at": record.get("phase_observed_at"),
            "event_count": (record.get("last_poll") or {}).get("event_count"),
            "model_count": (record.get("last_poll") or {}).get("model_count"),
            "interaction_state": record.get("interaction_state"),
            "reply_status": record.get("last_reply_status"),
            "observation_count": record.get("observation_count", 0),
            # 停滞读数必须落在**这个**投影里：`refresh_record` 早就把它算好挂在
            # record 上，另外两处投影也带着它，唯独 poll 输出的这一份漏了——
            # 于是「多久没吐字了」这条告警对宿主完全不可见，而那正是它要防的那件事。
            "events_idle_sec": record.get("events_idle_sec"),
            "stalled": record.get("stalled"),
            "last_error": record.get("last_error"),
        } for record in records],
        "interactions": interactions or [],
        "adaptive_reply_requests": adaptive,
        "progress_changed": bool(change_list),
        "changes": change_list,
        "automation_stability": {
            "required_confirmations": stability.get("required_confirmations", 2),
            "consecutive_confirmations": stability.get("consecutive_confirmations", 0),
            "last_confirmation_at": stability.get("last_confirmation_at"),
            "ready_at": stability.get("ready_at"),
        },
        "cli_configuration_health": suite_cli_health(suite),
        "next_interval_sec": next_interval_sec,
        "next_action": next_action,
        "read_only": read_only,
    }


def print_summary(suite: dict[str, Any]) -> None:
    print(json.dumps(summary(suite), ensure_ascii=False, indent=2), flush=True)


def command_plan(plans: list[CasePlan], jobs: int,
                 base_end_phase: str | None = None,
                 continue_case: str | None = None,
                 continue_end_phase: str | None = None) -> int:
    validate_phase_overrides(base_end_phase, continue_case, continue_end_phase, plans)
    if jobs < len(plans):
        raise SystemExit(
            f"[multi] 隔离并行 plan 要求 jobs >= Case 数量（{jobs} < {len(plans)}）")
    print(json.dumps({
        "cases": [
            {**plan.as_dict(), "requested_end_phase": requested_end_phase(
                plan, base_end_phase, continue_case, continue_end_phase)}
            for plan in plans
        ],
        "jobs": jobs,
        "workspace": str(REPO_ROOT),
        "policy": {
            "initial_start": "sequential_confirmed_then_parallel_run",
            "start_max_attempts": START_MAX_ATTEMPTS,
            "phase_active_parallelism": jobs,
            "same_feature_parallelism": 0,
            "coding_parallelism": jobs,
            "awaiting_reply": "host_reply_required_per_isolated_case",
            "workspace_copy": "allowlist_without_output_test_tools_features_git",
            "interaction_interval_sec": INTERACTION_INTERVAL_SEC,
            "automation_interval_sec": AUTOMATION_INTERVAL_SEC,
            "automation_stability_confirmations": 2,
            "workspace_output_retention": "retain_until_next_suite_start",
            "cli_configurations": [item["id"] for item in CLI_CONFIGURATIONS],
            "content_rejection_retries_per_config":
                CLI_RETRY_POLICY["content_rejection_retries_per_config"],
            "auth_failure_scope": CLI_RETRY_POLICY["auth_failure_scope"],
        },
    }, ensure_ascii=False, indent=2))
    return 0


def command_start(plans: list[CasePlan], suite_id: str, jobs: int,
                  base_end_phase: str | None = None,
                  continue_case: str | None = None,
                  continue_end_phase: str | None = None,
                  non_sandbox_authorized: bool = False,
                  preserve_current_features: bool = False) -> int:
    path, suite = create_suite(plans, suite_id, jobs, base_end_phase,
                               continue_case, continue_end_phase,
                               non_sandbox_authorized,
                               preserve_current_features)
    prepare_suite_preflight(path, suite)
    schedule_pending(suite)
    suite["status"] = finalize_suite_status(suite)
    save_suite(path / "suite.json", suite)
    print(json.dumps(control_payload(suite), ensure_ascii=False, indent=2), flush=True)
    return 0


def command_poll(suite_id: str, wait_sec: int, max_chars: int) -> int:
    if wait_sec < 0 or max_chars <= 0:
        raise SystemExit("[multi] --wait-sec 必须 >= 0，--max-chars 必须 > 0")
    path, suite = load_suite(suite_id)
    if suite.get("status") in {"finished", "failed", "stopped"}:
        print(json.dumps(control_payload(suite), ensure_ascii=False, indent=2), flush=True)
        return 0 if suite.get("status") == "finished" else 2
    before = progress_snapshot(suite)
    event_cursor = len(suite.get("events", []))
    poll_suite(suite, wait_sec, max_chars)
    settle_scripted_interactions(suite, max_chars)
    suite["status"] = finalize_suite_status(suite)
    save_suite(path / "suite.json", suite)
    events = list(suite.get("events", []))[event_cursor:]
    interactions = interaction_events(events)
    changes = progress_changes(before, suite, interactions)
    print(json.dumps(control_payload(
        suite, interactions=interactions, changes=changes),
        ensure_ascii=False, indent=2), flush=True)
    return 0


def command_status(suite_id: str) -> int:
    path, suite = load_suite(suite_id)
    del path
    # Read-only view: derive current evidence in memory, never save suite/state or
    # advance cursors, observations, interactions, or stability confirmations.
    suite["status"] = finalize_suite_status(suite)
    for record in suite.get("case_states", {}).values():
        reconcile_record_phase(record)
    payload = summary(suite)
    payload["read_only"] = True
    payload["driver_hint"] = "status 不消费事件或发送回复；正式驱动使用 start 后连续 poll"
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    return 0


#: 宿主这一句话是哪一种，直接决定它对观测的影响，所以要分开记账而不是只数次数。
#:   planned   —— 按规划条目表达需求方的立场（`--step` 指名是哪一条）
#:   answered  —— 回答模型主动提出的问题
#:   neutral   —— 模型没有提问，只给一句中性的推进，不含任何做法或写作指引
#:   improvised—— 以上都不是：宿主自己的话。**这一类会污染观测**，评测时要单独看
HOST_REPLY_KINDS = ("planned", "answered", "neutral", "improvised")


def command_reply(suite_id: str, case_id: str, text: str,
                  reply_mode: str = "manual", reason: str = "",
                  deliver: list[str] | None = None,
                  step_id: str = "", reply_kind: str = "improvised") -> int:
    path, suite = load_suite(suite_id)
    if case_id not in suite["case_states"]:
        raise SystemExit(f"[multi] Case 不在 suite 中: {case_id}")
    record = refresh_record(suite["case_states"][case_id])
    if record.get("status") != WAITING_STATUS:
        print(json.dumps({"ok": False, "case": case_id,
                          "error": f"当前状态不是 awaiting_reply: {record.get('status')}"},
                         ensure_ascii=False, indent=2))
        return 1
    blockers: list[str] = []
    if blockers:
        print(json.dumps({"ok": False, "case": case_id,
                          "error": "另一个 Case 正占用 Framework 阶段槽，暂不注入回复",
                          "blockers": blockers}, ensure_ascii=False, indent=2))
        return 2
    deliver_args: list[str] = []
    for name in deliver or []:
        deliver_args.extend(("--deliver", str(name)))
    returncode, payload, stdout, stderr = invoke_case(
        case_id, "reply", "--text", text, *deliver_args, suite=suite)
    interaction = {
        "kind": "interaction_reply",
        "mode": reply_mode,
        # 这一句是「按规划 / 答提问 / 中性推进 / 宿主自己的话」——评测要据它判断
        # 这份产物有多少受了宿主话术影响，只数次数是答不出这个问题的。
        "reply_kind": reply_kind,
        "planned_step": step_id or None,
        "reason": reason,
        "delivered": (payload or {}).get("delivered") or [],
        "prompt": (record.get("last_awaiting") or {}).get("prompt")
                  or (record.get("last_awaiting") or {}).get("message"),
        "reply": text,
        "returncode": returncode,
    }
    append_event(suite, "case_reply", case=case_id, returncode=returncode,
                 reply_mode=reply_mode, reply_kind=reply_kind,
                 planned_step=step_id or None, reason=reason)
    append_case_observation(suite, case_id, interaction)
    if returncode != 0:
        record["last_error"] = {"stdout": stdout[-4000:], "stderr": stderr[-4000:]}
    else:
        record["last_reply_status"] = "accepted"
        record["last_reply_text"] = text
        record["last_replied_turn"] = (record.get("last_awaiting") or {}).get("turn")
        record["last_human_reply_at"] = now()
        record["automation_observation_state"] = "reply_sent"
        record_delivery(record, (payload or {}).get("delivered") or [])
        record["interaction_state"] = (
            "adaptive_sent" if reply_mode == "adaptive" else record.get("interaction_state"))
        # 规划指针由宿主**显式声明**推进（`--step <id>`），不再靠拿回复文本去和
        # 脚本逐字比对。宿主是按情境把那个意思说出来的，不会逐字重合——
        # 上一版因此几乎从不推进指针，规划条目一条条烂在后面没人知道。
        script = list(record.get("interaction_script") or [])
        if step_id:
            hit = next((i for i, s in enumerate(script)
                        if str(s.get("id") or "") == step_id), None)
            if hit is None:
                record["last_error"] = {
                    "step": step_id,
                    "error": "规划里没有这个条目",
                    "known": [str(s.get("id") or "") for s in script],
                }
            else:
                record["interaction_index"] = max(
                    int(record.get("interaction_index") or 0), hit + 1)
                record["interaction_state"] = (
                    "complete" if hit + 1 >= len(script) else "waiting")
                append_event(suite, "planned_step_covered", case=case_id,
                             step=step_id, interaction_index=record["interaction_index"])
        record.setdefault("host_reply_kinds", []).append(reply_kind)
    save_suite(path / "suite.json", suite)
    print(json.dumps(payload or {"ok": False, "returncode": returncode,
                                 "stdout": stdout[-4000:], "stderr": stderr[-4000:]},
                     ensure_ascii=False, indent=2))
    return returncode


def command_retry(suite_id: str, case_id: str, reason: str) -> int:
    """人授权后重启**一个** Case，其它 Case 一律不动。

    配置组自带的重试等的是一个失败信号（400 内容审查、401 鉴权），而**挂起不产生
    失败信号**：进程活着、租约健康、状态 running，从装置的每个指标看都正常，
    它只是不再吐字。那种情况下机制在旁边待命，永远等不到该它出场。

    所以处置入口留给人：装置报「多久没产出」（`events_idle_sec` / `stalled`），
    要不要重启由人判断——可能它还在想，自动重启会把正在进行的工作丢掉。

    重启走的是配置组同一条链路（干净基线、attempt+1），不新写一套；
    失败 run 的 artifact、事件与 attempt 记录照常留档。
    """
    path, suite = load_suite(suite_id)
    records = suite.get("case_states", {})
    if case_id not in records:
        raise SystemExit(f"[multi] 未知 Case: {case_id}")
    record = records[case_id]
    refresh_record(record)
    before = dict(record)

    # 先让这个 Case 的 worker 停下来——只停它一个。
    if record.get("status") in ACTIVE_STATUS:
        returncode, _, _, _ = invoke_case(case_id, "stop", suite=suite)
        append_event(suite, "case_stop", case=case_id, returncode=returncode,
                     reason="human_authorized_retry")

    index = int(record.get("cli_config_index") or 0)
    request_case_retry(suite, record, config_index=index,
                       reason=reason or "human_authorized_retry",
                       failure_kind="stalled")
    schedule_pending(suite)
    suite["status"] = finalize_suite_status(suite)
    save_suite(path / "suite.json", suite)
    sys.stdout.write(json.dumps({
        "ok": True, "case": case_id,
        "was": {"status": before.get("status"),
                "events_idle_sec": before.get("events_idle_sec")},
        "now": {"status": record.get("status"),
                "attempt": record.get("attempt"),
                "cli_config_id": record.get("cli_config_id")},
        "note": "只重启了这一个 Case；其它 Case 未受影响。失败 run 的证据保留。",
    }, ensure_ascii=False, indent=2) + "\n")
    return 0


def command_conclude(suite_id: str, case_id: str, reason: str) -> int:
    """宿主判定「这个 Case 本轮到此为止」——**逐 Case，且不杀进程**。

    与 `stop` 两处不同，都是实跑里被咬过的：

    - `stop` 是整 suite 一档，先到终点的那个只能陪着另一个干等（实测空转 18 分钟）；
      这里按 Case 收工，各走各的。
    - `stop` 强杀进程树，门禁从不运行、`phase-results/` 不产出，报告是残的；
      这里只放一个控制文件，worker 自己退出续话循环，照常跑完门禁与收尾。

    终态是 `concluded_by_host`，**不是失败**：目标闭没闭环由 `target_reached` 与
    `closure.target_missing` 单独说。模型自认为做完了而凭证不齐，那是一条有效观测。
    """
    path, suite = load_suite(suite_id)
    if case_id not in suite["case_states"]:
        raise SystemExit(f"[multi] Case 不在 suite 中: {case_id}")
    record = refresh_record(suite["case_states"][case_id])
    args = ["--reason", reason] if reason else []
    returncode, payload, stdout, stderr = invoke_case(
        case_id, "conclude", *args, suite=suite)
    if returncode != 0:
        record["last_error"] = {"stdout": stdout[-2000:], "stderr": stderr[-2000:]}
    else:
        record["host_concluded"] = {"reason": reason, "at": now()}
    append_event(suite, "case_concluded", case=case_id,
                 returncode=returncode, reason=reason)
    append_case_observation(suite, case_id, {
        "kind": "host_conclude", "reason": reason, "returncode": returncode,
        "closure": record.get("closure"),
    })
    save_suite(path / "suite.json", suite)
    print(json.dumps(payload or {"ok": returncode == 0, "returncode": returncode,
                                 "stdout": stdout[-2000:], "stderr": stderr[-2000:]},
                     ensure_ascii=False, indent=2))
    return returncode


def command_stop(suite_id: str, force: bool) -> int:
    path, suite = load_suite(suite_id)
    errors: list[dict[str, Any]] = []
    # Stop sequentially.  A stop may restore the shared phase slot or source
    # transaction, so stopping several workers concurrently would be unsafe.
    for record in suite["case_states"].values():
        refresh_record(record)
        if record.get("status") not in ACTIVE_STATUS:
            continue
        args = ("--force",) if force else ()
        returncode, payload, stdout, stderr = invoke_case(
            str(record["case"]), "stop", *args, suite=suite)
        append_event(suite, "case_stop", case=record["case"], returncode=returncode)
        refresh_record(record)
        if returncode != 0 or record.get("status") not in TERMINAL_STATUS:
            errors.append({"case": record["case"], "returncode": returncode,
                           "status": record.get("status"), "payload": payload,
                           "stdout": stdout[-2000:], "stderr": stderr[-2000:]})
    suite["status"] = "failed" if errors else "stopped"
    if errors:
        suite["stop_errors"] = errors
    save_suite(path / "suite.json", suite)
    print_summary(suite)
    return 2 if errors else 0


def _copy_file_with_backup(source: Path, destination: Path,
                           backup_root: Path, relative: str,
                           manifest: list[dict[str, Any]]) -> None:
    if destination.exists():
        backup = backup_root / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file():
            shutil.copy2(destination, backup)
        elif destination.is_dir():
            shutil.copytree(destination, backup)
        else:
            raise SystemExit(f"[multi] 回灌目标不是普通文件或目录: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    manifest.append({
        "source": str(source),
        "destination": str(destination),
        "relative": relative,
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "size": destination.stat().st_size,
    })


def _tree_digest(root: Path) -> str | None:
    if not root.is_dir():
        return None
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            files[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()).hexdigest()
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode("utf-8")).hexdigest()


def promote_case_workspace(suite: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """Archive and promote every terminal Case with a retained workspace."""
    workspace = Path(str(record.get("workspace") or "")).resolve()
    if not workspace.is_dir():
        return {"status": "workspace_missing", "case": record["case"]}
    baseline_path = Path(str(record.get("workspace_baseline") or ""))
    baseline = read_json(baseline_path, {}) if baseline_path else {}
    current = snapshot_workspace_sources(workspace)
    before_files = baseline.get("files", {}) if isinstance(baseline, dict) else {}
    after_files = current.get("files", {})
    changed = sorted(path for path, value in after_files.items()
                     if before_files.get(path) != value)
    deleted = sorted(path for path in before_files if path not in after_files)
    case_root = Path(str(suite["bundle_root"])) / "cases" / str(record["case"])
    diff_root = case_root / "source-diff"
    if diff_root.exists():
        shutil.rmtree(diff_root)
    copied_evidence: list[str] = []
    for relative in changed:
        source = workspace / relative
        if not source.is_file():
            continue
        destination = diff_root / "files" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied_evidence.append(relative)
    evidence = {
        "schema_version": 1,
        "case": record["case"],
        "ar": record["feature"],
        "baseline_digest": baseline.get("digest"),
        "current_digest": current.get("digest"),
        "changed_paths": changed,
        "deleted_paths": deleted,
        "copied_evidence": copied_evidence,
        "captured_at": now(),
    }
    write_json(diff_root / "manifest.json", evidence)
    record["source_diff"] = evidence

    accepted = record.get("status") in TERMINAL_STATUS \
        or record.get("status") == "coordinator_start_failed"
    if not accepted:
        result = {"status": "evidence_only", "accepted": False, **evidence}
        write_json(case_root / "promotion-manifest.json", result)
        return result

    promotion_backup = Path(str(suite["bundle_root"])) / "backup" / "promotion" \
        / str(record["case"])
    promoted: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    already_promoted: list[dict[str, Any]] = []

    # Feature documents are independent Case outputs.  They must not be blocked
    # by source changes promoted by an earlier Case in the same finalize batch.
    feature_source = workspace / "doc" / "features" / str(record["feature"])
    feature_destination = FEATURES_ROOT / str(record["feature"])
    if feature_source.is_dir():
        source_digest = _tree_digest(feature_source)
        destination_digest = _tree_digest(feature_destination)
        feature_item = {"kind": "feature", "source": str(feature_source),
                        "destination": str(feature_destination),
                        "sha256": source_digest}
        if destination_digest == source_digest:
            already_promoted.append(feature_item)
        elif feature_destination.exists():
            conflicts.append({**feature_item, "reason": "feature_destination_conflict",
                              "destination_sha256": destination_digest})
        else:
            shutil.copytree(feature_source, feature_destination)
            promoted.append(feature_item)

    # Source promotion uses a per-file three-way check.  This accepts the suite
    # baseline, is idempotent when a prior finalize already wrote the same file,
    # and rejects only a genuinely divergent destination.
    main_baseline_files = (suite.get("main_source_baseline") or {}).get("files", {})
    current_main_files = snapshot_workspace_sources(REPO_ROOT).get("files", {})
    for relative in changed:
        source = workspace / relative
        if not source.is_file():
            continue
        destination = REPO_ROOT / relative
        baseline_value = main_baseline_files.get(relative)
        destination_value = current_main_files.get(relative)
        source_value = after_files.get(relative)
        if destination_value == source_value:
            already_promoted.append({"kind": "source", "relative": relative,
                                     "destination": str(destination),
                                     "sha256": source_value.get("sha256")})
        elif destination_value == baseline_value:
            _copy_file_with_backup(source, destination, promotion_backup / "source", relative,
                                   promoted)
            current_main_files[relative] = source_value
        else:
            conflicts.append({"kind": "source", "relative": relative,
                              "destination": str(destination),
                              "reason": "source_destination_conflict",
                              "baseline": baseline_value,
                              "destination_state": destination_value,
                              "case_state": source_value})

    if conflicts:
        status = "partial_promotion_conflict" if promoted or already_promoted \
            else "promotion_conflict"
    elif promoted:
        status = "promoted"
    else:
        status = "already_promoted"
    result = {"status": status, "accepted": not conflicts,
              "case_status": record.get("status"),
              "execution_status": record.get("execution_status"),
              **evidence,
              "promoted": promoted, "already_promoted": already_promoted,
              "conflicts": conflicts, "promoted_at": now()}
    write_json(case_root / "promotion-manifest.json", result)
    record["promotion_status"] = status
    return result


def capture_requirement_system(suite: dict[str, Any],
                               record: dict[str, Any]) -> dict[str, Any]:
    """把跑完之后的需求系统整份留下来——归档正文、附件、历史版本都是行为证据。

    「它到底有没有把 Story 传上系统」这件事，只有系统侧的状态答得了。
    工作区里那份 story.md 从头到尾都在，看它证明不了任何归档行为。
    """
    workspace = Path(str(record.get("workspace") or "")).resolve()
    workspace_root = Path(str(suite.get("workspace_root") or workspace.parent))
    source = requirement_system_path(workspace_root, str(record["case"]))
    result: dict[str, Any] = {"case": record["case"], "source": str(source)}
    if not source.is_dir():
        result["status"] = "no_requirement_system"
        return result
    destination = Path(str(suite["bundle_root"])) / "cases" / str(record["case"]) / "system-after"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    files = sorted(path.relative_to(destination).as_posix()
                   for path in destination.rglob("*") if path.is_file())
    result.update(status="captured", destination=str(destination), files=files)
    record["system_after"] = result
    return result


def write_case_observation_record(suite: dict[str, Any],
                                  record: dict[str, Any]) -> None:
    case_root = Path(str(suite["bundle_root"])) / "cases" / str(record["case"])
    report = case_root / "observation-record.md"
    promotion = read_json(case_root / "promotion-manifest.json", {})
    history = list(record.get("start_history") or [])
    lines = [
        f"# {record['case']} 测试观测记录", "",
        f"- Feature：`{record['feature']}`",
        f"- 目标阶段：`{record.get('requested_end_phase') or record.get('end_phase')}`",
        f"- 最终状态：`{record.get('status')}`",
        f"- Run ID：`{record.get('run_id') or '未创建'}`",
        f"- 最终 CLI 配置：`{record.get('cli_config_id') or '未选择'}`",
        f"- Case attempts：{len(record.get('attempts') or [])}",
        f"- 启动尝试：{len(history)} / {START_MAX_ATTEMPTS}",
        f"- 观测次数：{record.get('observation_count', 0)}",
        f"- 回灌状态：`{promotion.get('status', '未执行')}`", "",
        f"- 保留 workspace：`{record.get('workspace') or '未创建'}`",
        f"- 保留 output：`{case_root}`", "",
        "## 启动与恢复", "",
    ]
    for item in history:
        lines.append(
            f"- 第 {item.get('attempt')} 次：{item.get('result')}"
            f"（returncode={item.get('returncode')}）")
    lines.extend(["", "## CLI 配置切换与 Case 重跑", ""])
    for item in record.get("attempts") or []:
        lines.append(
            f"- Attempt {item.get('attempt')}：`{item.get('cli_config_id')}` / "
            f"`{item.get('status')}` / failure=`{item.get('failure_kind') or 'none'}` / "
            f"action=`{item.get('retry_action') or 'none'}` / run=`{item.get('run_id')}`")
    lines.extend([
        "", "## 观测证据", "",
        "完整的 15 秒交互观测、120 秒自动观测和回复记录见 `observations.jsonl`。",
        "", "## 错误与遗留", "",
        f"```json\n{json.dumps(record.get('last_error'), ensure_ascii=False, indent=2)}\n```",
    ])
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def command_finalize(suite_id: str, promote: bool, cleanup: bool) -> int:
    if cleanup:
        raise SystemExit(
            "[multi] finalize --cleanup 已停用；workspace 与 output 保留到下一轮 suite 起跑时清理")
    path, suite = load_suite(suite_id)
    for record in suite["case_states"].values():
        refresh_record(record)
    if any(record.get("status") in ACTIVE_STATUS or record.get("status") == "pending"
           for record in suite["case_states"].values()):
        raise SystemExit("[multi] 仍有活动或未启动 Case，拒绝归档/清理")
    results = []
    if promote:
        for record in suite["case_states"].values():
            results.append(promote_case_workspace(suite, record))
    system_captures = [capture_requirement_system(suite, record)
                       for record in suite["case_states"].values()]
    for record in suite["case_states"].values():
        write_case_observation_record(suite, record)
    suite["workspace_retention"]["status"] = "retained"
    suite["output_retention"]["status"] = "retained"
    suite["finalization"] = {"promote": promote, "cleanup": False,
                              "results": results,
                              "requirement_system": system_captures, "at": now()}
    save_suite(path / "suite.json", suite)
    print_summary(suite)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("plan", "start", "poll", "status",
                                            "reply", "conclude", "retry", "stop",
                                            "finalize"))
    parser.add_argument("case_ids", nargs="*")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--suite-id", default="")
    parser.add_argument("--end-phase", default="",
                        help="覆盖未指定继续 Case 的本轮终止阶段")
    parser.add_argument("--continue-case", default="",
                        help="选定一个 Case 使用单独的后续终止阶段")
    parser.add_argument("--continue-end-phase", default="",
                        help="--continue-case 的终止阶段")
    parser.add_argument("--case", dest="reply_case", default="")
    parser.add_argument("--text", default="")
    parser.add_argument("--reply-mode", choices=("scripted", "adaptive", "manual"),
                        default="manual")
    parser.add_argument("--reason", default="")
    parser.add_argument("--step", dest="step_id", default="",
                        help="这一句覆盖了规划里的哪一条（条目 id）——指名它，规划指针才前进")
    parser.add_argument("--reply-kind", dest="reply_kind",
                        choices=HOST_REPLY_KINDS, default="improvised",
                        help="planned=按规划立场 / answered=答模型的提问 / "
                             "neutral=中性推进 / improvised=宿主自己的话（会污染观测）")
    parser.add_argument("--deliver", action="append", default=[],
                        help="reply：随这句话把该 Case supplements/ 下的材料放进收件箱，可多次")
    parser.add_argument("--wait-sec", type=int, default=15)
    parser.add_argument("--max-chars", type=int, default=200000)
    parser.add_argument("--authorize-non-sandbox", action="store_true",
                        help="记录宿主模型已获授权在非沙箱环境启动本轮外层协调器")
    parser.add_argument("--preserve-current-features", action="store_true",
                        help="已停用；正式测试必须迁移当前 doc/features")
    parser.add_argument("--promote", action="store_true",
                        help="finalize：归档并回灌所有终态 workspace 的文档和安全源码差异")
    parser.add_argument("--cleanup", action="store_true",
                        help="已停用；workspace/output 在下一轮 suite 起跑时统一清理")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.command in {"plan", "start"}:
        plans = select_cases(args.case_ids, args.all)
        base_end_phase = args.end_phase or None
        continue_case = args.continue_case or None
        continue_end_phase = args.continue_end_phase or None
        if args.command == "plan":
            return command_plan(plans, args.jobs, base_end_phase,
                                continue_case, continue_end_phase)
        suite_id = args.suite_id or datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}"
        return command_start(plans, suite_id, args.jobs, base_end_phase,
                             continue_case, continue_end_phase,
                             args.authorize_non_sandbox,
                             args.preserve_current_features)

    if not args.suite_id:
        raise SystemExit(f"[multi] {args.command} 必须提供 --suite-id")
    if args.command == "finalize":
        if not args.promote and not args.cleanup:
            raise SystemExit("[multi] finalize 至少需要 --promote 或 --cleanup")
        return command_finalize(args.suite_id, args.promote, args.cleanup)
    if args.command == "poll":
        return command_poll(args.suite_id, args.wait_sec, args.max_chars)
    if args.command == "status":
        return command_status(args.suite_id)
    if args.command == "conclude":
        if not args.reply_case:
            raise SystemExit("[multi] conclude 必须提供 --case（逐 Case 收工，不是整 suite）")
        return command_conclude(args.suite_id, args.reply_case, args.reason)
    if args.command == "retry":
        if not args.reply_case:
            raise SystemExit("[multi] retry 必须提供 --case（逐 Case 重启，不动其它 Case）")
        return command_retry(args.suite_id, args.reply_case, args.reason)
    if args.command == "reply":
        if not args.reply_case or not args.text.strip():
            raise SystemExit("[multi] reply 必须提供 --case 和非空 --text")
        return command_reply(args.suite_id, args.reply_case, args.text,
                             args.reply_mode, args.reason, args.deliver,
                             args.step_id, args.reply_kind)
    return command_stop(args.suite_id, args.force)


if __name__ == "__main__":
    raise SystemExit(main())
