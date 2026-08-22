"""Base event adapter and shared extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AdapterEvent:
    type: str
    content: str | None = None
    session_id: str | None = None
    message_id: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    tool_status: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_output: str | None = None
    usage: dict[str, Any] | None = None


def session_id(event: dict[str, Any]) -> str | None:
    for obj in (event, event.get("message"), event.get("part")):
        if not isinstance(obj, dict):
            continue
        for key in ("session_id", "sessionID", "sessionId"):
            value = obj.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def part_input(part: dict[str, Any]) -> dict[str, Any]:
    state = part.get("state") if isinstance(part.get("state"), dict) else {}
    value = state.get("input")
    if isinstance(value, dict):
        return value
    value = part.get("input")
    return value if isinstance(value, dict) else {}


class BaseAdapter:
    def parse(self, event: dict[str, Any]) -> list[AdapterEvent]:
        values: list[AdapterEvent] = []
        sid = session_id(event)
        if sid:
            values.append(AdapterEvent("session", session_id=sid))
        event_type = str(event.get("type") or "")
        if event_type in {"error", "turn.failed"}:
            message = event.get("message") or event.get("error") or event
            values.append(AdapterEvent("error", content=str(message)))
        elif event.get("text"):
            values.append(AdapterEvent("text", content=str(event["text"])))
        return values
