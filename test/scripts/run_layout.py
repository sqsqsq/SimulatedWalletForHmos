"""Immutable run-directory layout for the Story CLI harness.

The command-line surface stays case based.  ``active.json`` and ``latest.json``
translate that stable case name to one immutable run directory; historical runs
are never deleted or reused.  A multi-case suite may set
``STORY_RUN_BUNDLE_ROOT`` so all of its case runs live below one scenario/time
directory.  A suite may also set ``STORY_RUN_CONTROL_ROOT`` so the active/latest
pointers live inside that same suite instead of the legacy output root.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any


RUN_BUNDLE_ENV = "STORY_RUN_BUNDLE_ROOT"
BUNDLE_ALLOWED_ROOT_ENV = "STORY_RUN_BUNDLE_ALLOWED_ROOT"
RUN_CONTROL_ENV = "STORY_RUN_CONTROL_ROOT"


def _safe_child(parent: Path, name: str, *, label: str) -> Path:
    value = str(name or "").strip()
    if not value or value in {".", ".."} or Path(value).name != value:
        raise ValueError(f"非法{label}: {name!r}")
    child = (parent / value).resolve()
    if child.parent != parent.resolve():
        raise ValueError(f"{label}越界: {name!r}")
    return child


def control_dir(out_root: Path, case_id: str) -> Path:
    configured = os.environ.get(RUN_CONTROL_ENV, "").strip()
    parent = Path(configured).resolve() if configured else out_root.resolve()
    allowed_root = _allowed_root(out_root)
    if not parent.is_relative_to(allowed_root):
        raise ValueError(f"运行控制根越出输出根: {parent}")
    return _safe_child(parent, case_id, label="case-id")


def _bundle_cases_root(out_root: Path) -> Path:
    configured = os.environ.get(RUN_BUNDLE_ENV, "").strip()
    if not configured:
        return out_root.resolve() / "runs"
    root = Path(configured).resolve()
    output_root = out_root.resolve()
    allowed_root = _allowed_root(out_root)
    if not root.is_relative_to(allowed_root):
        raise ValueError(f"运行 bundle 根越出输出根: {root}")
    return root / "cases"


def _allowed_root(out_root: Path) -> Path:
    configured = os.environ.get(BUNDLE_ALLOWED_ROOT_ENV, "").strip()
    return Path(configured).resolve() if configured else out_root.resolve()


def runs_dir(out_root: Path, case_id: str) -> Path:
    return _safe_child(_bundle_cases_root(out_root), case_id, label="case-id")


def run_dir(out_root: Path, case_id: str, run_id: str) -> Path:
    return _safe_child(runs_dir(out_root, case_id), run_id, label="run-id")


def new_run_id() -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{os.getpid()}-{uuid.uuid4().hex[:8]}"


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.{os.getpid()}.tmp"
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    tmp.write_text(encoded, encoding="utf-8")
    os.replace(tmp, path)


def _pointer_payload(out_root: Path, case_id: str, run_id: str,
                     *, status: str, at: str | None = None) -> dict[str, Any]:
    path = _path_for_run(out_root, case_id, run_id)
    return {
        "schema_version": 1,
        "case": case_id,
        "run_id": run_id,
        "path": path.relative_to(_allowed_root(out_root)).as_posix(),
        "status": status,
        "updated_at": at or time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _path_for_run(out_root: Path, case_id: str, run_id: str) -> Path:
    for name in ("active", "latest"):
        pointer = _read_pointer(out_root, case_id, name)
        if pointer and str(pointer.get("run_id")) == run_id:
            return Path(str(pointer["_resolved_path"]))
    return run_dir(out_root, case_id, run_id)


def _read_pointer(out_root: Path, case_id: str, name: str) -> dict[str, Any] | None:
    path = control_dir(out_root, case_id) / f"{name}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"运行指针不可读: {path} ({exc})") from exc
    if payload.get("case") != case_id or not payload.get("run_id"):
        raise ValueError(f"运行指针内容非法: {path}")
    allowed_root = _allowed_root(out_root)
    declared = (allowed_root / str(payload.get("path") or "")).resolve()
    if not declared.is_relative_to(allowed_root):
        raise ValueError(f"运行指针路径越出输出根: {path}")
    if declared.name != str(payload["run_id"]):
        raise ValueError(f"运行指针 run-id 与路径不一致: {path}")
    payload["_resolved_path"] = str(declared)
    return payload


def read_pointer(out_root: Path, case_id: str, name: str) -> dict[str, Any] | None:
    if name not in {"active", "latest"}:
        raise ValueError(f"未知指针: {name}")
    return _read_pointer(out_root, case_id, name)


def resolve_run(out_root: Path, case_id: str, run_id: str | None = None,
                *, allow_legacy: bool = True) -> tuple[Path, str | None]:
    """Resolve an explicit run, otherwise active then latest.

    ``allow_legacy`` keeps read-only access to runs produced before the immutable
    layout migration.  New multi-case runs are created below their suite bundle;
    single-case runs retain the legacy ``runs/`` default.
    """
    if run_id:
        for name in ("active", "latest"):
            pointer = read_pointer(out_root, case_id, name)
            if pointer and str(pointer.get("run_id")) == run_id:
                return Path(str(pointer["_resolved_path"])), run_id
        return run_dir(out_root, case_id, run_id), run_id
    for name in ("active", "latest"):
        pointer = read_pointer(out_root, case_id, name)
        if pointer:
            rid = str(pointer["run_id"])
            return Path(str(pointer["_resolved_path"])), rid
    legacy = control_dir(out_root, case_id)
    if allow_legacy:
        return legacy, None
    raise FileNotFoundError(f"用例 {case_id} 尚无运行")


def create_run(out_root: Path, case_id: str, run_id: str | None = None) -> tuple[Path, str]:
    rid = run_id or new_run_id()
    target = run_dir(out_root, case_id, rid)
    target.mkdir(parents=True, exist_ok=False)
    payload = _pointer_payload(out_root, case_id, rid, status="active")
    _atomic_json(control_dir(out_root, case_id) / "active.json", payload)
    return target, rid


def publish_latest(out_root: Path, case_id: str, run_id: str, status: str) -> None:
    """Publish terminal lookup atomically, then retire the matching active pointer."""
    control = control_dir(out_root, case_id)
    payload = _pointer_payload(out_root, case_id, run_id, status=status)
    _atomic_json(control / "latest.json", payload)
    active = read_pointer(out_root, case_id, "active")
    if active and str(active.get("run_id")) == run_id:
        (control / "active.json").unlink(missing_ok=True)
