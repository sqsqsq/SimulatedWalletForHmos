"""Shared selector match contract, independent of Hypium."""

from __future__ import annotations

from typing import Any

from hylyre.api.exceptions import SelectorContractError

SUPPORTED_MATCHES = frozenset({"exact", "contains"})
DEFAULT_MATCH = "contains"


def normalize_match(
    requested: Any,
    *,
    selector: dict[str, Any] | None = None,
) -> tuple[str | None, str]:
    """Return ``requested_match`` and the validated effective match."""

    if requested is None:
        return None, DEFAULT_MATCH
    if not isinstance(requested, str):
        raise SelectorContractError(
            f"match must be one of exact or contains; got {requested!r}",
            selector=selector,
        )
    value = requested.strip().lower()
    if value not in SUPPORTED_MATCHES:
        raise SelectorContractError(
            f"unsupported match {requested!r}; supported values are exact and contains",
            selector=selector,
        )
    return requested, value


def text_matches(text: str, pattern: str, match: Any = None) -> bool:
    """Apply the same exact/contains semantics in resolver and fake paths."""

    _requested, effective = normalize_match(match)
    return text == pattern if effective == "exact" else pattern in text


def selector_evidence(
    pred: dict[str, Any] | None,
    *,
    engine: str,
    candidate_count: int,
    selected_id: str | None = None,
    bounds: str | None = None,
    selected_center: tuple[int, int] | None = None,
) -> dict[str, Any]:
    requested, effective = normalize_match(
        (pred or {}).get("match"), selector=pred
    )
    return {
        "engine": engine,
        "requested_match": requested,
        "effective_match": effective,
        "candidate_count": int(candidate_count),
        "selected_id": selected_id,
        "bounds": bounds,
        "selected_center": list(selected_center) if selected_center else None,
    }


__all__ = [
    "DEFAULT_MATCH",
    "SUPPORTED_MATCHES",
    "normalize_match",
    "selector_evidence",
    "text_matches",
]
