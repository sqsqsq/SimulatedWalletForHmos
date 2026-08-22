"""Adapters that normalize provider-specific JSONL into common events."""

from __future__ import annotations

from typing import Any

from .base import AdapterEvent, BaseAdapter, part_input, session_id


def _message_id(event: dict[str, Any]) -> str | None:
    part = event.get("part") if isinstance(event.get("part"), dict) else {}
    message = event.get("message") if isinstance(event.get("message"), dict) else {}
    value = (
        part.get("messageID")
        or part.get("message_id")
        or message.get("id")
        or event.get("messageID")
        or event.get("message_id")
    )
    return str(value) if value else None


def _tool_call_id(value: dict[str, Any], state: dict[str, Any] | None = None) -> str | None:
    state = state or {}
    result = (
        value.get("id")
        or value.get("callID")
        or value.get("call_id")
        or value.get("tool_use_id")
        or state.get("id")
        or state.get("callID")
        or state.get("call_id")
    )
    return str(result) if result else None


def _usage(value: Any) -> dict[str, Any]:
    raw = dict(value) if isinstance(value, dict) else {}
    cache = raw.get("cache") if isinstance(raw.get("cache"), dict) else {}
    normalized = {
        "input": int(raw.get("input", raw.get("input_tokens", 0)) or 0),
        "output": int(raw.get("output", raw.get("output_tokens", 0)) or 0),
        "reasoning": int(raw.get("reasoning", raw.get("reasoning_tokens", 0)) or 0),
        "cache_read": int(
            raw.get("cache_read", raw.get("cache_read_input_tokens", cache.get("read", 0))) or 0
        ),
        "cache_write": int(
            raw.get("cache_write", raw.get("cache_creation_input_tokens", cache.get("write", 0))) or 0
        ),
    }
    normalized["context_total"] = int(
        raw.get("context_total", raw.get("total", normalized["input"] + normalized["output"])) or 0
    )
    if raw.get("cost") is not None:
        normalized["cost"] = float(raw["cost"] or 0)
    return normalized


def _content_items(message: Any, event: dict[str, Any]) -> list[AdapterEvent]:
    if isinstance(message, str) and message.strip():
        return [AdapterEvent("text", content=message, message_id=_message_id(event))]
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return [AdapterEvent("text", content=content, message_id=_message_id(event))]
    if not isinstance(content, list):
        return []
    values: list[AdapterEvent] = []
    message_id = str(message.get("id") or _message_id(event) or "") or None
    for item in content:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type") or "")
        if kind == "text" and item.get("text"):
            values.append(AdapterEvent("text", content=str(item["text"]), message_id=message_id))
        elif kind in {"thinking", "reasoning"}:
            text = item.get("thinking") or item.get("text")
            if text:
                values.append(AdapterEvent("reasoning", content=str(text), message_id=message_id))
        elif kind in {"tool_use", "tool_call"}:
            name = str(item.get("name") or item.get("tool") or "")
            values.append(
                AdapterEvent(
                    "tool",
                    content=name,
                    message_id=message_id,
                    tool_call_id=_tool_call_id(item),
                    tool_name=name,
                    tool_status=str(item.get("status") or "started"),
                    tool_input=item.get("input") if isinstance(item.get("input"), dict) else {},
                )
            )
        elif kind == "tool_result":
            output = str(item.get("content") or "")
            values.append(
                AdapterEvent(
                    "tool",
                    content=output,
                    message_id=message_id,
                    tool_call_id=_tool_call_id(item),
                    tool_status="completed",
                    tool_output=output,
                )
            )
    return values


class OpenCodeAdapter(BaseAdapter):
    def parse(self, event: dict[str, Any]) -> list[AdapterEvent]:
        values: list[AdapterEvent] = []
        sid = session_id(event)
        message_id = _message_id(event)
        if sid:
            values.append(AdapterEvent("session", session_id=sid, message_id=message_id))
        part = event.get("part")
        if not isinstance(part, dict):
            return values + super().parse(event)
        kind = str(part.get("type") or "")
        if kind == "text" and part.get("text"):
            values.append(AdapterEvent("text", content=str(part["text"]), message_id=message_id))
        elif kind in {"reasoning", "thinking"}:
            text = part.get("text") or part.get("thinking")
            if text:
                values.append(AdapterEvent("reasoning", content=str(text), message_id=message_id))
        elif kind in {"tool", "tool_use", "tool_call"}:
            tool = str(part.get("tool") or part.get("name") or "")
            state = part.get("state") if isinstance(part.get("state"), dict) else {}
            output = str(state["output"]) if state.get("output") is not None else None
            status = str(state.get("status") or "started")
            values.append(
                AdapterEvent(
                    "tool",
                    content=tool,
                    message_id=message_id,
                    tool_call_id=_tool_call_id(part, state),
                    tool_name=tool,
                    tool_status=status,
                    tool_input=part_input(part),
                    tool_output=output,
                )
            )
            if status == "error":
                values.append(AdapterEvent("error", content=str(state.get("error") or "")))
        elif kind == "step-finish":
            usage = _usage(part.get("tokens"))
            if part.get("cost") is not None:
                usage["cost"] = float(part["cost"] or 0)
            values.append(AdapterEvent("usage", message_id=message_id, usage=usage))
        return values


class CursorAgentAdapter(BaseAdapter):
    def parse(self, event: dict[str, Any]) -> list[AdapterEvent]:
        values: list[AdapterEvent] = []
        sid = session_id(event)
        message_id = _message_id(event)
        if sid:
            values.append(AdapterEvent("session", session_id=sid, message_id=message_id))
        kind = str(event.get("type") or "")
        if kind == "thinking" or event.get("thinking"):
            text = event.get("thinking") or event.get("text")
            if text:
                values.append(AdapterEvent("reasoning", content=str(text), message_id=message_id))
        elif event.get("text"):
            values.append(AdapterEvent("text", content=str(event["text"]), message_id=message_id))
        if "name" in event and isinstance(event.get("input"), dict):
            name = str(event.get("name") or "")
            values.append(
                AdapterEvent(
                    "tool",
                    content=name,
                    message_id=message_id,
                    tool_call_id=_tool_call_id(event),
                    tool_name=name,
                    tool_status=str(event.get("status") or "started"),
                    tool_input=event["input"],
                    tool_output=str(event["output"]) if event.get("output") is not None else None,
                )
            )
        values.extend(_content_items(event.get("message"), event))
        if kind == "result" and isinstance(event.get("result"), str) and event["result"].strip():
            values.append(AdapterEvent("text", content=event["result"], message_id=message_id))
        if kind == "error":
            values.append(AdapterEvent("error", content=str(event.get("message") or event)))
        usage = event.get("usage")
        if isinstance(usage, dict):
            values.append(AdapterEvent("usage", message_id=message_id, usage=_usage(usage)))
        return values


class ClaudeAdapter(CursorAgentAdapter):
    pass


class CodexAdapter(BaseAdapter):
    def parse(self, event: dict[str, Any]) -> list[AdapterEvent]:
        kind = str(event.get("type") or "")
        if kind == "thread.started":
            sid = event.get("thread_id")
            return [
                AdapterEvent(
                    "session",
                    content=str(sid or ""),
                    session_id=str(sid) if sid else None,
                )
            ]
        if kind == "turn.completed":
            return [AdapterEvent("usage", usage=_usage(event.get("usage")))]
        if kind.startswith("item."):
            item = event.get("item")
            if not isinstance(item, dict):
                return []
            item_type = str(item.get("type") or "")
            item_id = str(item.get("id") or "") or None
            if item_type == "agent_message":
                return [AdapterEvent("text", content=str(item.get("text") or ""), message_id=item_id)]
            if item_type == "reasoning":
                return [
                    AdapterEvent("reasoning", content=str(item.get("text") or ""), message_id=item_id)
                ]
            if item_type == "command_execution":
                command = str(item.get("command") or "")
                output = (
                    str(item.get("aggregated_output") or "")
                    if item.get("aggregated_output") is not None
                    else None
                )
                return [
                    AdapterEvent(
                        "tool",
                        content=command,
                        message_id=item_id,
                        tool_call_id=item_id,
                        tool_name="command_execution",
                        tool_status=str(item.get("status") or ("completed" if kind.endswith("completed") else "started")),
                        tool_input={"command": command},
                        tool_output=output,
                    )
                ]
            if item_type == "file_change":
                changes = item.get("changes")
                return [
                    AdapterEvent(
                        "tool",
                        content="file_change",
                        message_id=item_id,
                        tool_call_id=item_id,
                        tool_name="file_change",
                        tool_status="completed" if kind.endswith("completed") else "started",
                        tool_input={"changes": changes if isinstance(changes, list) else []},
                    )
                ]
            if item_type == "mcp_tool_call":
                name = str(item.get("tool") or item.get("server") or "")
                return [
                    AdapterEvent(
                        "tool",
                        content=name,
                        message_id=item_id,
                        tool_call_id=item_id,
                        tool_name=name,
                        tool_status=str(item.get("status") or ("completed" if kind.endswith("completed") else "started")),
                        tool_input=item.get("arguments")
                        if isinstance(item.get("arguments"), dict)
                        else {},
                        tool_output=str(item["result"]) if item.get("result") is not None else None,
                    )
                ]
            if item_type == "error":
                return [AdapterEvent("error", content=str(item.get("message") or ""))]
            return []
        if kind in {"error", "turn.failed"}:
            return [
                AdapterEvent(
                    "error",
                    content=str(event.get("message") or event.get("error") or event),
                )
            ]
        return []


ADAPTERS: dict[str, BaseAdapter] = {
    "opencode": OpenCodeAdapter(),
    "cursor_agent": CursorAgentAdapter(),
    "claude": ClaudeAdapter(),
    "codex": CodexAdapter(),
}


def get_adapter(name: str) -> BaseAdapter:
    try:
        return ADAPTERS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown CLI adapter: {name}") from exc
