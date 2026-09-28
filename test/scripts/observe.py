"""观察通道：让控制端能实时看见被测 CLI 在干什么。

三样东西，各有分工：

| 载体 | 给谁 | 怎么读 |
|---|---|---|
| `live.jsonl` | 控制端 | 按 `seq` 游标增量拉（harness 自己的阶段事件） |
| `events.jsonl` | 控制端 | 按序号游标增量拉（**被测模型的推理与发言**） |
| `runlog.md` | 人 | 直接打开看，实时 flush |

最重要的是第二条：**模型的行为无法靠脚本准确观察，评价者要自己读**。
只统计工具次数、产物大小这类机械量，看不出它为什么这么做、卡在哪、怎么绕过去的。
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

TOOL_OUTPUT_LIMIT = 600


def shorten(value: Any, limit: int = TOOL_OUTPUT_LIMIT) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        text = str(value)
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + f"\n... [truncated, total={len(text)} chars]"


class LiveFeed:
    """Harness 自己的阶段事件流：只追加，按 seq 游标寻址。"""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._seq = 0
        self._lock = threading.Lock()

    def emit(self, etype: str, **payload: Any) -> None:
        with self._lock:
            self._seq += 1
            line = json.dumps(
                {"seq": self._seq, "ts": time.strftime("%H:%M:%S"), "type": etype, **payload},
                ensure_ascii=False)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
                fh.flush()


class RunLog:
    """人类可读的实时运行日志；单向落盘，不向被测会话回灌任何内容。"""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open("w", encoding="utf-8")
        self._lock = threading.Lock()

    def header(self, metadata: dict[str, Any]) -> None:
        lines = ["# story 被测会话运行日志", ""]
        lines.extend(f"- {k}: `{v}`" for k, v in metadata.items())
        self._write("\n".join(lines) + "\n")

    def event(self, label: str, content: str) -> None:
        self._write(f"\n## {label} · {datetime.now():%H:%M:%S}\n\n{content.strip()}\n")

    def footer(self, metadata: dict[str, Any]) -> None:
        lines = ["", "## Run Result", ""]
        lines.extend(f"- {k}: `{v}`" for k, v in metadata.items())
        self._write("\n".join(lines) + "\n")

    def _write(self, text: str) -> None:
        with self._lock:
            if self._file.closed:
                return
            self._file.write(text if text.endswith("\n") else text + "\n")
            self._file.flush()

    def close(self) -> None:
        with self._lock:
            if not self._file.closed:
                self._file.close()


def tool_summary(event) -> str:
    tool = str(event.tool_name or "?")
    ti = event.tool_input or {}
    lower = tool.lower()
    if lower in {"read", "write", "edit"}:
        detail: Any = ti.get("filePath") or ti.get("file_path") or ti.get("path") or ""
    elif lower in {"bash", "shell", "shell_command"}:
        detail = ti.get("command") or ""
    elif lower in {"grep", "search"}:
        detail = {"pattern": ti.get("pattern"), "path": ti.get("path")}
    else:
        detail = ti
    parts = [f"Tool `{tool}`", shorten(detail)]
    if event.tool_status:
        parts.append(f"status={event.tool_status}")
    if event.tool_output:
        parts.append("result=" + shorten(event.tool_output))
    return "\n".join(parts)


def describe(event) -> tuple[str, str] | None:
    """归一化事件 → runlog 的 (标题, 正文)；None 表示不进日志。"""
    if event.type in {"text", "reasoning"} and event.content:
        return ("Model" if event.type == "text" else "Reasoning"), event.content
    if event.type == "tool":
        return "Tool", tool_summary(event)
    if event.type == "session" and event.session_id:
        return "Session", event.session_id
    if event.type in {"error", "cli_output", "lifecycle"} and event.content:
        return {"error": "CLI Error", "cli_output": "CLI", "lifecycle": "Runner"}[event.type], event.content
    return None


def read_feed(path: Path, cursor: int, max_chars: int) -> tuple[list[dict], int, bool]:
    """读 live.jsonl 里 seq > cursor 的事件。读到半行不推进游标。"""
    out: list[dict] = []
    next_cursor, has_more, total = cursor, False, 0
    if not path.is_file():
        return out, next_cursor, has_more
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            break
        seq = int(item.get("seq", 0))
        if seq <= cursor:
            continue
        if out and total + len(line) > max_chars:
            has_more = True
            break
        out.append(item)
        next_cursor, total = seq, total + len(line)
    return out, next_cursor, has_more


def read_model(path: Path, cursor: int, max_chars: int) -> tuple[list[dict], int, bool]:
    """读 events.jsonl 里被测模型的**增量推理与发言**。

    工具事件压成一行摘要（名字 + 关键入参），避免整页原始输出淹没推理。
    """
    out: list[dict] = []
    next_cursor, has_more, total, idx = cursor, False, 0, 0
    if not path.is_file():
        return out, next_cursor, has_more
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            break
        if e.get("type") not in {"text", "reasoning", "tool", "error"}:
            continue
        idx += 1
        if idx <= cursor:
            continue
        if e["type"] == "tool":
            ti = e.get("tool_input") or {}
            detail = (ti.get("command") or ti.get("filePath") or ti.get("file_path")
                      or ti.get("path") or ti.get("pattern") or "")
            item = {"seq": idx, "type": "tool", "tool": e.get("tool_name"),
                    "detail": str(detail)[:200], "status": e.get("tool_status")}
        else:
            item = {"seq": idx, "type": e["type"], "content": (e.get("content") or "")[:4000]}
        chunk = len(json.dumps(item, ensure_ascii=False))
        if out and total + chunk > max_chars:
            has_more = True
            break
        out.append(item)
        next_cursor, total = idx, total + chunk
    return out, next_cursor, has_more


def _stat(path: Path) -> dict[str, Any]:
    try:
        st = path.stat()
        return {"exists": True, "size": st.st_size, "mtime": round(st.st_mtime, 3)}
    except OSError:
        return {"exists": False}


def snapshot(out_dir: Path, feature_root: Path) -> dict[str, Any]:
    """独立于事件流的观察信号：产物变化也能唤醒 poll。

    `activity_age_sec` 每次读取都会增长，**必须排除在 revision 之外**，
    否则没有任何真实变化也会不停唤醒，变成忙轮询。
    """
    payload: dict[str, Any] = {
        "runlog": _stat(out_dir / "runlog.md"),
        "events": _stat(out_dir / "events.jsonl"),
        "spec": _stat(feature_root / "spec" / "spec.md"),
        "story": _stat(feature_root / "AR" / "story.md"),
        "review": _stat(feature_root / "AR" / "review.md"),
        "acceptance": _stat(feature_root / "acceptance.yaml"),
    }
    newest = max((v.get("mtime", 0) for v in payload.values() if v.get("exists")), default=0)
    payload["activity_age_sec"] = round(time.time() - newest, 1) if newest else None
    fingerprint = {k: v for k, v in payload.items() if k != "activity_age_sec"}
    payload["revision"] = hashlib.sha256(
        json.dumps(fingerprint, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:12]
    return payload
