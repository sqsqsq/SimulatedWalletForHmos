"""Midscene-style ``HylyreAgent``: structured UI ops + optional VLM for natural language."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from hylyre.api.exceptions import (
    AssertionMismatch,
    CapabilityUnsupported,
    StepSkipped,
)
from hylyre.api.selector_ops import (
    scroll_until_visible,
    tree_from_dump,
    uses_native_only,
    uses_resolver,
    wait_rich_selector,
)
from hylyre.api.selector_resolve import has_rich_selector_fields, resolve_action_one
from hylyre.api.selector_contract import normalize_match, selector_evidence
from hylyre.api.selectors import require_selector
from hylyre.diagnostic_log import diagnostic_log
from hylyre.drivers.base import MockControllerBase, UiDriverBase, VlmClientBase
from hylyre.ui_dump_hints import augment_ui_dump_payload, parse_bounds_rect


def _start_app_failure_hint(bundle: str, page_name: str | None) -> str:
    parts = [
        f"original error above; bundle={bundle!r}",
    ]
    if not page_name:
        parts.append(
            "try --page-name <Ability> or "
            '{"start_app":{"bundle":"…","page_name":"…"}} in the plan'
        )
    parts.append(
        f"or pre-start: hdc shell aa start -a <Ability> -b {bundle}"
    )
    return " ".join(parts)


class HylyreAgent:
    """High-level facade: uses only ``UiDriverBase`` / ``MockControllerBase`` / ``VlmClientBase``."""

    def __init__(
        self,
        *,
        ui: UiDriverBase,
        mock: MockControllerBase | None = None,
        vlm: VlmClientBase | None = None,
    ) -> None:
        self._ui = ui
        self._mock = mock
        self._vlm = vlm
        self._ui_connected = False
        self._toast_listener_started = False

    @property
    def ui(self) -> UiDriverBase:
        return self._ui

    @property
    def mock_controller(self) -> MockControllerBase | None:
        return self._mock

    @property
    def vlm(self) -> VlmClientBase | None:
        return self._vlm

    def _require_vlm(self) -> VlmClientBase:
        if self._vlm is None:
            raise ValueError(
                "Natural-language step requires a VLM client (pass vlm= to HylyreAgent, "
                "use structured ai_tap / ai_input with by_id/by_text/coordinates only, "
                "or run_planned_* with JSON from an external planner)."
            )
        return self._vlm

    async def _ensure_ui(self) -> None:
        if not self._ui_connected:
            await self._ui.connect()
            self._ui_connected = True

    async def ensure_connected(self) -> None:
        """Connect Hypium once; safe for session daemons and MCP ``open_session``."""
        await self._ensure_ui()

    async def aclose(self) -> None:
        if self._ui_connected:
            await self._ui.close()
            self._ui_connected = False

    async def start_app(
        self,
        bundle: str,
        *,
        page_name: str | None = None,
        params: str = "",
        wait_time: float = 1.0,
    ) -> None:
        await self._ensure_ui()
        try:
            await self._ui.start_app(
                bundle, page_name=page_name, params=params, wait_time=wait_time
            )
        except Exception as e:
            hint = _start_app_failure_hint(bundle, page_name)
            raise RuntimeError(f"start_app failed for {bundle!r}: {hint}") from e


    async def dump_ui(self) -> dict[str, Any]:
        """Return structured UI tree for external agents (no VLM)."""
        await self._ensure_ui()
        raw = await self._ui.dump_ui()
        if isinstance(raw, dict):
            return augment_ui_dump_payload(raw)
        return raw

    async def start_toast_listening(self) -> dict[str, Any]:
        """Prepare Toast observation before a planned trigger action."""

        await self._ensure_ui()
        fn = getattr(self._ui, "start_toast_listening", None)
        if not callable(fn):
            raise CapabilityUnsupported(
                "Toast listener capability is unavailable",
                evidence={"channel": "unavailable", "listener_started": False},
            )
        try:
            result = await fn()
        except NotImplementedError:
            raise CapabilityUnsupported(
                "Toast listener capability is unavailable",
                evidence={"channel": "unavailable", "listener_started": False},
            )
        if isinstance(result, dict):
            self._toast_listener_started = bool(
                result.get("listener_started", True)
            )
            return result
        self._toast_listener_started = True
        return {"channel": type(self._ui).__name__, "listener_started": True}

    async def mock_activate_group(self, group_id: str) -> None:
        if self._mock is None:
            raise ValueError("No mock controller configured on this HylyreAgent")
        await self._mock.activate_group(group_id)

    async def mock_deactivate_all(self) -> None:
        if self._mock is None:
            raise ValueError("No mock controller configured on this HylyreAgent")
        await self._mock.deactivate_all()

    @staticmethod
    def _touch_from_payload(t: dict[str, Any]) -> dict[str, Any]:
        if "x" in t and "y" in t:
            return {"x": int(t["x"]), "y": int(t["y"])}
        if "by_text" in t:
            out: dict[str, Any] = {"by_text": str(t["by_text"])}
            if t.get("match") is not None:
                out["match"] = str(t["match"])
            return out
        if "by_id" in t:
            return {"by_id": str(t["by_id"])}
        raise ValueError(f"Unsupported touch payload: {t!r}")

    async def _apply_touch_block(
        self, touch: dict[str, Any], *, wait_time: float
    ) -> dict[str, Any]:
        has_x = touch.get("x") is not None
        has_y = touch.get("y") is not None
        if has_x != has_y:
            raise ValueError("touch coordinates require both x and y")
        selector_keys = [
            key
            for key in ("by_text", "by_id", "by_type", "by_key")
            if touch.get(key) is not None
        ]
        if touch.get("all") is not None:
            selector_keys.append("all")
        if (has_x and has_y) + len(selector_keys) != 1:
            raise ValueError(
                "touch requires exactly one of (x and y), by_text, by_id, by_type, or by_key"
            )
        normalize_match(touch.get("match"), selector=touch)
        wt = float(touch.get("wait_time", wait_time))
        scroll_into = touch.get("scroll_into_view")
        if isinstance(scroll_into, dict):
            pred = {
                k: touch[k]
                for k in (
                    "by_text", "by_id", "by_type", "by_key", "match", "scope",
                    "within", "below", "above", "after", "before", "all", "index",
                    "visible", "clickable", "enabled",
                )
                if touch.get(k) is not None
            }
            await scroll_until_visible(
                self,
                target_pred=pred,
                container=scroll_into,
            )

        if uses_native_only(touch):
            kwargs = self._touch_from_payload(touch)
            kwargs["wait_time"] = wt
            await self._ui.touch(**kwargs)
            return {
                "selector": selector_evidence(
                    touch,
                    engine="native",
                    candidate_count=1,
                    selected_id=str(touch.get("by_id")) if touch.get("by_id") else None,
                ),
                "evidence": {"operation": "touch", "coordinates": None},
            }

        if uses_resolver(touch):
            from hylyre.api.selector_ops import resolve_touch_hit

            hit = await resolve_touch_hit(self, touch)
            await self._ui.touch(x=hit.center[0], y=hit.center[1], wait_time=wt)
            return {
                "selector": {
                    "engine": hit.engine,
                    "requested_match": hit.requested_match,
                    "effective_match": hit.effective_match,
                    "candidate_count": hit.candidate_count,
                    "selected_id": hit.id or None,
                    "bounds": hit.tap_bounds,
                },
                "evidence": {
                    "operation": "touch",
                    "center": list(hit.center),
                    "resolution_kind": hit.resolution_kind,
                    "fragment_bounds": hit.fragment_bounds,
                },
            }

        kwargs = self._touch_from_payload(touch)
        kwargs["wait_time"] = wt
        await self._ui.touch(**kwargs)
        return {
            "selector": selector_evidence(touch, engine="native", candidate_count=1),
            "evidence": {"operation": "touch"},
        }

    async def _apply_input_block(
        self,
        block: dict[str, Any],
        *,
        value: str | None,
        by_text: str | None,
        by_id: str | None,
    ) -> dict[str, Any]:
        from hylyre.api.selector_ops import (
            resolve_input_hit,
            uses_native_input_only,
            uses_resolver_for_input,
        )

        text = value if value is not None else block.get("text")
        normalize_match(block.get("match"), selector=block)
        if text is None:
            raise ValueError("VLM input payload missing text and no value= provided")
        mode = block.get("mode")
        if uses_native_input_only(block):
            bt = block.get("by_text", by_text)
            bid = block.get("by_id", by_id)
            await self._ui.input_text(
                str(text), by_text=bt, by_id=bid, match=block.get("match"), mode=mode
            )
            return {
                "selector": selector_evidence(
                    block, engine="native", candidate_count=1,
                    selected_id=str(bid) if bid else None,
                ),
                "evidence": {"operation": "input", "text_supplied": True},
            }
        if uses_resolver_for_input(block):
            hit = await resolve_input_hit(self, block)
            focus_wait = float(block.get("focus_wait", 0.15))
            await self._ui.touch(
                x=hit.center[0], y=hit.center[1], wait_time=focus_wait
            )
            await self._ui.input_text(str(text), mode=mode)
            return {
                "selector": {
                    "engine": hit.engine,
                    "requested_match": hit.requested_match,
                    "effective_match": hit.effective_match,
                    "candidate_count": hit.candidate_count,
                    "selected_id": hit.id or None,
                    "bounds": hit.tap_bounds,
                },
                "evidence": {"operation": "input", "text_supplied": True},
            }
        bt = block.get("by_text", by_text)
        bid = block.get("by_id", by_id)
        await self._ui.input_text(
            str(text), by_text=bt, by_id=bid, match=block.get("match"), mode=mode
        )
        return {
            "selector": selector_evidence(
                block, engine="native", candidate_count=1,
                selected_id=str(bid) if bid else None,
            ),
            "evidence": {"operation": "input", "text_supplied": True},
        }

    async def _apply_action_block(self, act: dict[str, Any]) -> dict[str, Any]:
        t = act.get("type")
        if t == "touch":
            block = {k: v for k, v in act.items() if k != "type"}
            return await self._apply_touch_block(
                block, wait_time=float(act.get("wait_time", 0.1))
            )
        elif t == "input":
            block = {k: v for k, v in act.items() if k != "type"}
            return await self._apply_input_block(
                block, value=None, by_text=None, by_id=None
            )
        elif t == "swipe":
            block = {k: v for k, v in act.items() if k != "type"}
            return await self._apply_swipe_block(block)
        elif t == "scroll":
            block = {k: v for k, v in act.items() if k != "type"}
            return await self._apply_scroll_block(block)
        elif t == "back":
            block = {k: v for k, v in act.items() if k != "type"}
            return await self._apply_back_block(block)
        elif t == "home":
            return await self._apply_home_block({})
        elif t == "stop_app":
            block = {k: v for k, v in act.items() if k != "type"}
            return await self._apply_stop_app_block(block)
        elif t == "clear_app":
            block = {k: v for k, v in act.items() if k != "type"}
            return await self._apply_clear_app_block(block)
        elif t == "wait":
            block = {k: v for k, v in act.items() if k != "type"}
            return await self._apply_wait_block(block)
        elif t == "wait_for":
            block = {k: v for k, v in act.items() if k != "type"}
            return await self._apply_wait_for_block(block)
        elif t == "wait_gone":
            block = {k: v for k, v in act.items() if k != "type"}
            return await self._apply_wait_gone_block(block)
        elif t == "wait_idle":
            block = {k: v for k, v in act.items() if k != "type"}
            return await self._apply_wait_idle_block(block)
        elif t == "assert_toast":
            block = {k: v for k, v in act.items() if k != "type"}
            return await self._apply_assert_toast_block(block)
        elif t == "start_app":
            block = {k: v for k, v in act.items() if k != "type"}
            return await self._apply_start_app_block(block)
        else:
            raise ValueError(f"Unsupported action type: {t!r}")

    @staticmethod
    def interpret_query_payload(
        raw: dict[str, Any],
        *,
        schema: type | None = None,
    ) -> Any:
        """Coerce ``answer`` / ``dtype`` from a VLM-shaped query JSON (no UI)."""
        answer = raw.get("answer")
        dtype = str(raw.get("dtype", "string"))
        if schema is None:
            if dtype == "number":
                return float(answer) if isinstance(answer, str) else answer
            if dtype == "boolean":
                return bool(answer)
            return answer
        if schema is float:
            return float(answer)
        if schema is int:
            return int(answer)
        if schema is bool:
            return bool(answer)
        if schema is str:
            return str(answer)
        return answer

    @staticmethod
    def interpret_assert_payload(raw: dict[str, Any]) -> dict[str, Any]:
        """Raise ``AssertionError`` unless ``ok`` is true (VLM-shaped assert JSON)."""
        if not raw.get("ok", False):
            raise AssertionMismatch(
                str(raw.get("reason", "assertion failed")),
                evidence={
                    "channel": "vlm",
                    "result": False,
                    "reason": str(raw.get("reason", "assertion failed")),
                },
            )
        return {"channel": "vlm", "result": True, "checked": True}

    async def run_planned_action(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply one UI step from external JSON matching ``response_schema="action"`` (no VLM)."""
        await self._ensure_ui()
        act = payload.get("action")
        if not isinstance(act, dict):
            raise ValueError(f"planned action payload missing action dict: {payload!r}")
        return await self._apply_action_block(act)

    async def run_planned_tap(
        self, payload: dict[str, Any], *, wait_time: float = 0.1
    ) -> dict[str, Any]:
        """Apply one touch from external JSON matching ``response_schema="tap"`` (no VLM)."""
        await self._ensure_ui()
        touch = payload.get("touch")
        if not isinstance(touch, dict):
            raise ValueError(f"planned tap payload missing touch dict: {payload!r}")
        return await self._apply_touch_block(touch, wait_time=wait_time)

    async def run_planned_input(
        self,
        payload: dict[str, Any],
        *,
        value: str | None = None,
        by_text: str | None = None,
        by_id: str | None = None,
    ) -> dict[str, Any]:
        """Apply one input from external JSON matching ``response_schema="input"`` (no VLM)."""
        await self._ensure_ui()
        block = payload.get("input")
        if not isinstance(block, dict):
            raise ValueError(f"planned input payload missing input dict: {payload!r}")
        return await self._apply_input_block(
            block, value=value, by_text=by_text, by_id=by_id
        )

    @staticmethod
    def _swipe_area_kwargs(area: dict[str, Any] | None) -> dict[str, Any]:
        blank: dict[str, Any] = {
            "area_by_text": None,
            "area_by_id": None,
            "area_by_type": None,
            "area_by_key": None,
            "area_match": None,
            "area_scrollable": None,
        }
        if area is None:
            return blank
        if not isinstance(area, dict):
            raise ValueError("swipe.area must be an object or omitted")
        found = [
            k
            for k in ("by_text", "by_id", "by_type", "by_key")
            if area.get(k) is not None
        ]
        if len(found) > 1 and area.get("all") is None:
            raise ValueError(
                "swipe.area allows at most one of by_text, by_id, by_type, by_key"
            )
        out = dict(blank)
        if len(found) == 1:
            k = found[0]
            out[f"area_{k}"] = str(area[k])
        if area.get("match") is not None:
            normalize_match(area.get("match"), selector=area)
            out["area_match"] = str(area["match"])
        if area.get("scrollable") is True:
            out["area_scrollable"] = True
        return out

    @staticmethod
    def _selector_predicate(value: dict[str, Any]) -> dict[str, Any]:
        """Keep only selector fields for resolver preflight/evidence."""

        keys = (
            "by_text", "by_id", "by_type", "by_key", "match", "scope", "within",
            "below", "above", "after", "before", "all", "index", "visible",
            "clickable", "enabled", "scrollable",
        )
        return {
            key: value[key]
            for key in keys
            if value.get(key) is not None
        }

    async def _resolve_unique_action_selector(
        self, selector: dict[str, Any]
    ) -> Any:
        payload = await self.dump_ui()
        tree = tree_from_dump(payload)
        return resolve_action_one(tree, selector)

    async def _apply_swipe_block(self, block: dict[str, Any]) -> dict[str, Any]:
        direction = block.get("direction")
        if not isinstance(direction, str) or not direction.strip():
            raise ValueError("swipe requires non-empty string direction")
        area = block.get("area")
        area_hit = None
        area_pred = None
        if isinstance(area, dict):
            area_pred = self._selector_predicate(area)
            if area_pred:
                area_hit = await self._resolve_unique_action_selector(area_pred)
        area_kw = self._swipe_area_kwargs(area if isinstance(area, dict) else None)
        sp_raw = block.get("start_point")
        sp: tuple[float, float] | None = None
        if sp_raw is not None:
            if (
                not isinstance(sp_raw, (list, tuple))
                or len(sp_raw) != 2
            ):
                raise ValueError("swipe start_point must be a pair [x, y]")
            sp = (float(sp_raw[0]), float(sp_raw[1]))
        if area_hit is not None and (
            area_pred is not None
            and any(
                area_pred.get(k) is not None
                for k in (
                    "all", "scope", "within", "below", "above", "after", "before",
                    "index", "visible", "clickable", "enabled",
                )
            )
        ):
            # Hypium has no equivalent for the rich conjunction.  Execute at
            # the already-resolved unique center rather than passing a weaker
            # selector that could choose a different first hit.
            area_kw = self._swipe_area_kwargs(None)
            if sp is None:
                sp = area_hit.center
        speed_raw = block.get("speed")
        speed_i = None if speed_raw is None else int(speed_raw)
        side_raw = block.get("side")
        await self._ui.swipe(
            direction=direction,
            distance=int(block.get("distance", 60)),
            side=str(side_raw) if side_raw is not None else None,
            start_point=sp,
            swipe_time=float(block.get("swipe_time", 0.3)),
            speed=speed_i,
            **area_kw,
        )
        selector = (
            {
                "engine": area_hit.engine,
                "requested_match": area_hit.requested_match,
                "effective_match": area_hit.effective_match,
                "candidate_count": area_hit.candidate_count,
                "selected_id": area_hit.id or None,
                "bounds": area_hit.tap_bounds,
            }
            if area_hit is not None
            else None
        )
        return {
            "selector": selector,
            "evidence": {"operation": "swipe", "result": True},
        }

    @staticmethod
    def _scroll_xy_or_none(
        *, at: dict[str, Any] | None, block: dict[str, Any]
    ) -> tuple[int | None, int | None]:
        bx = block.get("x")
        by = block.get("y")
        if bx is not None or by is not None:
            if at is not None:
                raise ValueError(
                    "scroll: use top-level x/y or scroll.at, not both"
                )
            if bx is None or by is None:
                raise ValueError("scroll x and y must be provided together")
            return int(bx), int(by)
        if at is None:
            return None, None
        if not isinstance(at, dict):
            raise ValueError("scroll.at must be an object or omitted")
        if at.get("x") is not None or at.get("y") is not None:
            if at.get("x") is None or at.get("y") is None:
                raise ValueError("scroll.at x and y must be provided together")
            sel_keys = [
                k
                for k in ("by_text", "by_id", "by_type", "by_key")
                if at.get(k) is not None
            ]
            if sel_keys:
                raise ValueError("scroll.at cannot mix x/y with selector keys")
            return int(at["x"]), int(at["y"])
        return None, None

    @staticmethod
    def _scroll_selector_kwargs(at: dict[str, Any] | None) -> dict[str, Any]:
        blank: dict[str, Any] = {
            "at_by_text": None,
            "at_by_id": None,
            "at_by_type": None,
            "at_by_key": None,
            "at_match": None,
            "at_scrollable": None,
        }
        if at is None:
            return blank
        if not isinstance(at, dict):
            raise ValueError("scroll.at must be an object or omitted")
        if at.get("x") is not None or at.get("y") is not None:
            return blank
        found = [
            k
            for k in ("by_text", "by_id", "by_type", "by_key")
            if at.get(k) is not None
        ]
        if len(found) > 1:
            raise ValueError(
                "scroll.at allows at most one of by_text, by_id, by_type, by_key"
            )
        out = dict(blank)
        if len(found) == 1:
            k = found[0]
            out[f"at_{k}"] = str(at[k])
        if at.get("match") is not None:
            normalize_match(at.get("match"), selector=at)
            out["at_match"] = str(at["match"])
        if at.get("scrollable") is True:
            out["at_scrollable"] = True
        return out

    async def _apply_scroll_block(self, block: dict[str, Any]) -> dict[str, Any]:
        direction = block.get("direction")
        if not isinstance(direction, str) or not direction.strip():
            raise ValueError("scroll requires non-empty string direction")
        steps_raw = block.get("steps")
        if steps_raw is None:
            raise ValueError("scroll requires steps")
        steps = int(steps_raw)
        at = block.get("at")
        if at is not None and not isinstance(at, dict):
            raise ValueError("scroll.at must be an object or omitted")
        xy = self._scroll_xy_or_none(at=at, block=block)
        sel_kw = self._scroll_selector_kwargs(at)
        at_hit = None
        at_pred = None
        if isinstance(at, dict):
            at_pred = self._selector_predicate(at)
            if at_pred:
                at_hit = await self._resolve_unique_action_selector(at_pred)
                if any(
                    at_pred.get(k) is not None
                    for k in (
                        "all", "scope", "within", "below", "above", "after", "before",
                        "index", "visible", "clickable", "enabled",
                    )
                ):
                    sel_kw = self._scroll_selector_kwargs(None)
                    if xy[0] is None and xy[1] is None:
                        xy = at_hit.center
        if (
            at is None
            and xy[0] is None
            and xy[1] is None
            and not any(
                sel_kw.get(k)
                for k in (
                    "at_by_text",
                    "at_by_id",
                    "at_by_type",
                    "at_by_key",
                )
            )
        ):
            xy = await self._auto_scroll_center()
        k1 = block.get("key1")
        k2 = block.get("key2")
        await self._ui.mouse_scroll(
            direction=direction,
            steps=steps,
            x=xy[0],
            y=xy[1],
            key1=None if k1 is None else int(k1),
            key2=None if k2 is None else int(k2),
            **sel_kw,
        )
        selector = (
            {
                "engine": at_hit.engine,
                "requested_match": at_hit.requested_match,
                "effective_match": at_hit.effective_match,
                "candidate_count": at_hit.candidate_count,
                "selected_id": at_hit.id or None,
                "bounds": at_hit.tap_bounds,
            }
            if at_hit is not None
            else None
        )
        return {
            "selector": selector,
            "evidence": {"operation": "scroll", "result": True},
        }

    async def _auto_scroll_center(self) -> tuple[int | None, int | None]:
        """Pick center of first scrollable container from dump hints."""
        try:
            payload = await self.dump_ui()
            hints = payload.get("_hylyre_hints") or {}
            containers = hints.get("scrollable_containers") or []
            if containers and isinstance(containers[0], dict):
                bounds = str(containers[0].get("bounds") or "")
                rect = parse_bounds_rect(bounds)
                if rect:
                    x1, y1, x2, y2 = rect
                    return ((x1 + x2) // 2, (y1 + y2) // 2)
        except Exception as e:
            diagnostic_log(f"auto_scroll_center fallback: {e!r}")
        return (None, None)

    async def _apply_scroll_to_block(self, block: dict[str, Any]) -> dict[str, Any]:
        container = block.get("in")
        if container is not None and not isinstance(container, dict):
            raise ValueError("scroll_to.in must be an object or omitted")
        pred = {
            k: block[k]
            for k in (
                "by_text",
                "by_id",
                "by_type",
                "by_key",
                "match",
                "scope",
                "within",
                "all",
                "index",
            )
            if block.get(k) is not None
        }
        if not pred:
            raise ValueError("scroll_to requires a target selector")
        if pred.get("by_text") is not None and not has_rich_selector_fields(pred):
            pred.setdefault("visible", True)
        hit = await scroll_until_visible(
            self,
            target_pred=pred,
            container=container if isinstance(container, dict) else None,
            max_scrolls=int(block.get("max_scrolls") or 15),
            swipe_distance=int(block.get("swipe_distance") or 60),
        )
        if block.get("tap") is True:
            await self._ui.touch(x=hit.center[0], y=hit.center[1], wait_time=0.1)
        return {
            "selector": {
                "engine": hit.engine,
                "requested_match": hit.requested_match,
                "effective_match": hit.effective_match,
                "candidate_count": hit.candidate_count,
                "selected_id": hit.id or None,
                "bounds": hit.tap_bounds,
            },
            "evidence": {
                "operation": "scroll_to",
                "tap": block.get("tap") is True,
                "center": list(hit.center),
                "resolution_kind": hit.resolution_kind,
                "fragment_bounds": hit.fragment_bounds,
            },
        }

    async def run_planned_swipe(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply ``swipe`` block (Hypium directional swipe; no VLM)."""
        await self._ensure_ui()
        block = payload.get("swipe")
        if not isinstance(block, dict):
            raise ValueError(f"planned swipe payload missing swipe dict: {payload!r}")
        return await self._apply_swipe_block(block)

    async def run_planned_scroll(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply ``scroll`` block (Hypium mouse_scroll; vertical wheel; no VLM)."""
        await self._ensure_ui()
        block = payload.get("scroll")
        if not isinstance(block, dict):
            raise ValueError(f"planned scroll payload missing scroll dict: {payload!r}")
        return await self._apply_scroll_block(block)

    async def run_planned_scroll_to(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Scroll until target visible; optional tap (no VLM)."""
        await self._ensure_ui()
        block = payload.get("scroll_to")
        if not isinstance(block, dict):
            raise ValueError(f"planned scroll_to missing dict: {payload!r}")
        return await self._apply_scroll_to_block(block)

    async def _apply_back_block(self, block: dict[str, Any]) -> dict[str, Any]:
        await self._ui.press_back(
            times=int(block.get("times", 1)),
            mode=str(block.get("mode", "key")),
            side=str(block.get("side", "RIGHT")),
            height=float(block.get("height", 0.5)),
        )
        return {"evidence": {"operation": "back", "result": True}}

    async def _apply_home_block(self, block: dict[str, Any]) -> dict[str, Any]:
        _ = block
        await self._ui.press_home()
        return {"evidence": {"operation": "home", "result": True}}

    async def _apply_stop_app_block(self, block: dict[str, Any]) -> dict[str, Any]:
        bundle = block.get("bundle")
        if not bundle:
            raise ValueError("stop_app requires bundle")
        await self._ui.stop_app(
            str(bundle),
            wait_time=float(block.get("wait_time", 0.5)),
        )
        return {"evidence": {"operation": "stop_app", "result": True}}

    async def _apply_clear_app_block(self, block: dict[str, Any]) -> dict[str, Any]:
        bundle = block.get("bundle")
        if not bundle:
            raise ValueError("clear_app requires bundle")
        await self._ui.clear_app_data(str(bundle))
        return {"evidence": {"operation": "clear_app", "result": True}}

    async def _apply_wait_block(self, block: dict[str, Any]) -> dict[str, Any]:
        sec = block.get("seconds")
        if sec is None:
            raise ValueError("wait requires seconds")
        await self._ui.wait_seconds(float(sec))
        return {"evidence": {"operation": "wait", "seconds": float(sec)}}

    async def _apply_wait_for_block(self, block: dict[str, Any]) -> dict[str, Any]:
        if has_rich_selector_fields(block) or block.get("scope") is not None:
            return await wait_rich_selector(
                self, block, timeout=float(block.get("timeout", 10.0)), want_gone=False
            )
        sel = require_selector(block, step="wait_for")
        return await self._ui.wait_for_selector(
            **sel,
            match=block.get("match"),
            timeout=float(block.get("timeout", 10.0)),
        )

    async def _apply_wait_gone_block(self, block: dict[str, Any]) -> dict[str, Any]:
        if has_rich_selector_fields(block) or block.get("scope") is not None:
            return await wait_rich_selector(
                self, block, timeout=float(block.get("timeout", 10.0)), want_gone=True
            )
        sel = require_selector(block, step="wait_gone")
        return await self._ui.wait_for_selector_gone(
            **sel,
            match=block.get("match"),
            timeout=float(block.get("timeout", 10.0)),
        )

    async def _apply_wait_idle_block(self, block: dict[str, Any]) -> dict[str, Any]:
        await self._ui.wait_for_idle(
            idle_time=float(block.get("idle_time", 0.7)),
            timeout=float(block.get("timeout", 10.0)),
        )
        return {"evidence": {"operation": "wait_idle", "result": True}}

    async def _apply_assert_toast_block(self, block: dict[str, Any]) -> dict[str, Any]:
        text = block.get("text")
        if text is None:
            raise ValueError("assert_toast requires text")
        on_unsupported = str(block.get("on_unsupported") or "error").strip().lower()
        listener_was_prestarted = self._toast_listener_started
        try:
            result = await self._ui.assert_toast(
                str(text),
                timeout=float(block.get("timeout", 3.0)),
                fuzzy=str(block.get("fuzzy", "equal")),
                poll_interval=float(block.get("poll_interval", 0.3)),
                on_unsupported=on_unsupported,
            )
        except StepSkipped:
            if on_unsupported == "skip":
                raise
            raise RuntimeError("toast assertion skipped but on_unsupported is not skip")
        except AssertionMismatch as exc:
            raise AssertionMismatch(
                str(exc),
                evidence={
                    **(getattr(exc, "evidence", None) or {}),
                    "trigger_window": (
                        "pre_action" if listener_was_prestarted else "assertion_only"
                    ),
                    "trigger_window_covered": listener_was_prestarted,
                },
                selector=getattr(exc, "selector", None),
            ) from exc
        except CapabilityUnsupported as exc:
            if on_unsupported == "skip":
                raise StepSkipped(
                    str(exc),
                    evidence=getattr(exc, "evidence", None),
                ) from exc
            raise
        finally:
            self._toast_listener_started = False
        trigger_window = "pre_action" if listener_was_prestarted else "assertion_only"
        if result is False or (
            isinstance(result, dict) and result.get("result") is False
        ):
            raise AssertionMismatch(
                f"toast assertion mismatch for {text!r}",
                evidence={
                    **(result if isinstance(result, dict) else {"result": False}),
                    "trigger_window": trigger_window,
                    "trigger_window_covered": listener_was_prestarted,
                },
            )
        if isinstance(result, dict):
            return {
                "evidence": {
                    **result,
                    "trigger_window": trigger_window,
                    "trigger_window_covered": listener_was_prestarted,
                }
            }
        if result is True:
            return {
                "evidence": {
                    "channel": "driver",
                    "result": True,
                    "boolean_return": True,
                    "trigger_window": trigger_window,
                    "trigger_window_covered": listener_was_prestarted,
                }
            }
        raise RuntimeError(
            "assert_toast driver returned no boolean result; assertion evidence is incomplete"
        )

    async def _apply_start_app_block(self, block: dict[str, Any]) -> dict[str, Any]:
        bundle = block.get("bundle")
        if not bundle:
            raise ValueError("start_app requires bundle")
        await self._ui.start_app(
            str(bundle),
            page_name=block.get("page_name"),
            params=str(block.get("params") or ""),
            wait_time=float(block.get("wait_time", 1.0)),
        )
        return {"evidence": {"operation": "start_app", "result": True}}

    async def run_planned_back(self, payload: dict[str, Any]) -> dict[str, Any]:
        await self._ensure_ui()
        block = payload.get("back")
        if block is None:
            block = {}
        if not isinstance(block, dict):
            raise ValueError(f"planned back payload must be object: {payload!r}")
        return await self._apply_back_block(block)

    async def run_planned_home(self, payload: dict[str, Any]) -> dict[str, Any]:
        await self._ensure_ui()
        block = payload.get("home")
        if block is None:
            block = {}
        if not isinstance(block, dict):
            raise ValueError(f"planned home payload must be object: {payload!r}")
        return await self._apply_home_block(block)

    async def run_planned_stop_app(self, payload: dict[str, Any]) -> dict[str, Any]:
        await self._ensure_ui()
        block = payload.get("stop_app")
        if not isinstance(block, dict):
            raise ValueError(f"planned stop_app missing dict: {payload!r}")
        return await self._apply_stop_app_block(block)

    async def run_planned_clear_app(self, payload: dict[str, Any]) -> dict[str, Any]:
        await self._ensure_ui()
        block = payload.get("clear_app")
        if not isinstance(block, dict):
            raise ValueError(f"planned clear_app missing dict: {payload!r}")
        return await self._apply_clear_app_block(block)

    async def run_planned_wait(self, payload: dict[str, Any]) -> dict[str, Any]:
        await self._ensure_ui()
        block = payload.get("wait")
        if not isinstance(block, dict):
            raise ValueError(f"planned wait missing dict: {payload!r}")
        return await self._apply_wait_block(block)

    async def run_planned_wait_for(self, payload: dict[str, Any]) -> dict[str, Any]:
        await self._ensure_ui()
        block = payload.get("wait_for")
        if not isinstance(block, dict):
            raise ValueError(f"planned wait_for missing dict: {payload!r}")
        return await self._apply_wait_for_block(block)

    async def run_planned_wait_gone(self, payload: dict[str, Any]) -> dict[str, Any]:
        await self._ensure_ui()
        block = payload.get("wait_gone")
        if not isinstance(block, dict):
            raise ValueError(f"planned wait_gone missing dict: {payload!r}")
        return await self._apply_wait_gone_block(block)

    async def run_planned_wait_idle(self, payload: dict[str, Any]) -> dict[str, Any]:
        await self._ensure_ui()
        block = payload.get("wait_idle")
        if block is None:
            block = {}
        if not isinstance(block, dict):
            raise ValueError(f"planned wait_idle must be object: {payload!r}")
        return await self._apply_wait_idle_block(block)

    async def run_planned_assert_toast(self, payload: dict[str, Any]) -> dict[str, Any]:
        await self._ensure_ui()
        block = payload.get("assert_toast")
        if not isinstance(block, dict):
            raise ValueError(f"planned assert_toast missing dict: {payload!r}")
        return await self._apply_assert_toast_block(block)

    async def run_planned_start_app_step(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Planned JSON ``start_app`` root (distinct from runner-level ``--bundle``)."""
        await self._ensure_ui()
        block = payload.get("start_app")
        if not isinstance(block, dict):
            raise ValueError(f"planned start_app missing dict: {payload!r}")
        return await self._apply_start_app_block(block)

    async def ai_tap(
        self,
        *,
        instruction: str | None = None,
        x: int | None = None,
        y: int | None = None,
        by_text: str | None = None,
        by_id: str | None = None,
        wait_time: float = 0.1,
    ) -> dict[str, Any]:
        await self._ensure_ui()
        if instruction is None:
            await self._ui.touch(
                x=x,
                y=y,
                by_text=by_text,
                by_id=by_id,
                wait_time=wait_time,
            )
            return {
                "selector": selector_evidence(
                    {"by_text": by_text, "by_id": by_id},
                    engine="native",
                    candidate_count=1,
                    selected_id=str(by_id) if by_id else None,
                ),
                "evidence": {"operation": "ai_tap", "result": True},
            }
        vlm = self._require_vlm()
        png = await self._ui.screenshot()
        raw = await vlm.vision_json(
            instruction=instruction,
            screenshot_png=png,
            response_schema="tap",
        )
        touch = raw.get("touch")
        if not isinstance(touch, dict):
            raise ValueError(f"VLM tap response missing touch dict: {raw!r}")
        return await self._apply_touch_block(touch, wait_time=wait_time)

    async def ai_input(
        self,
        value: str | None = None,
        *,
        instruction: str | None = None,
        by_text: str | None = None,
        by_id: str | None = None,
    ) -> dict[str, Any]:
        await self._ensure_ui()
        if instruction is None:
            if value is None:
                raise ValueError("ai_input requires value= when instruction is omitted")
            await self._ui.input_text(value, by_text=by_text, by_id=by_id)
            return {
                "selector": selector_evidence(
                    {"by_text": by_text, "by_id": by_id},
                    engine="native",
                    candidate_count=1,
                    selected_id=str(by_id) if by_id else None,
                ),
                "evidence": {"operation": "ai_input", "result": True},
            }
        vlm = self._require_vlm()
        png = await self._ui.screenshot()
        raw = await vlm.vision_json(
            instruction=instruction,
            screenshot_png=png,
            response_schema="input",
        )
        block = raw.get("input")
        if not isinstance(block, dict):
            raise ValueError(f"VLM input response missing input dict: {raw!r}")
        return await self._apply_input_block(
            block, value=value, by_text=by_text, by_id=by_id
        )

    async def ai_action(self, instruction: str) -> dict[str, Any]:
        await self._ensure_ui()
        vlm = self._require_vlm()
        png = await self._ui.screenshot()
        raw = await vlm.vision_json(
            instruction=instruction,
            screenshot_png=png,
            response_schema="action",
        )
        act = raw.get("action")
        if not isinstance(act, dict):
            raise ValueError(f"VLM action response missing action dict: {raw!r}")
        return await self._apply_action_block(act)

    async def ai_query(
        self,
        instruction: str,
        *,
        schema: type | None = None,
    ) -> Any:
        await self._ensure_ui()
        vlm = self._require_vlm()
        png = await self._ui.screenshot()
        raw = await vlm.vision_json(
            instruction=instruction,
            screenshot_png=png,
            response_schema="query",
        )
        return self.interpret_query_payload(raw, schema=schema)

    async def ai_string(self, instruction: str) -> str:
        out = await self.ai_query(instruction, schema=str)
        return str(out)

    async def ai_number(self, instruction: str) -> float:
        out = await self.ai_query(instruction, schema=float)
        return float(out)

    async def ai_boolean(self, instruction: str) -> bool:
        out = await self.ai_query(instruction, schema=bool)
        return bool(out)

    async def ai_assert(self, instruction: str) -> dict[str, Any]:
        await self._ensure_ui()
        vlm = self._require_vlm()
        png = await self._ui.screenshot()
        raw = await vlm.vision_json(
            instruction=instruction,
            screenshot_png=png,
            response_schema="assert",
        )
        return self.interpret_assert_payload(raw)

    async def ai_wait_for(
        self,
        instruction: str,
        *,
        timeout: float = 10.0,
        interval: float = 0.5,
    ) -> None:
        deadline = time.monotonic() + timeout
        last_err: AssertionError | None = None
        while time.monotonic() < deadline:
            try:
                await self.ai_assert(instruction)
                return
            except AssertionError as e:
                last_err = e
                await asyncio.sleep(interval)
        raise TimeoutError(
            last_err.args[0] if last_err else f"wait_for timeout: {instruction!r}"
        )

    async def ai_locate(self, instruction: str) -> dict[str, Any]:
        await self._ensure_ui()
        vlm = self._require_vlm()
        png = await self._ui.screenshot()
        return await vlm.vision_json(
            instruction=instruction,
            screenshot_png=png,
            response_schema="locate",
        )
