"""Validated Story test CLI configuration groups.

This module contains no credentials.  It only validates the ordered CLI/model
selectors that the unified ``tools.cli`` registry consumes.
"""
from __future__ import annotations

from typing import Any


def load_cli_group(config: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    cli = config.get("cli") or {}
    raw = cli.get("configurations")
    if not isinstance(raw, list) or not raw:
        raise SystemExit("[runner] cli.configurations 必须是非空有序列表")
    configurations: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise SystemExit(f"[runner] cli.configurations[{index}] 必须是映射")
        value = {key: str(item.get(key) or "").strip()
                 for key in ("id", "name", "model", "profile")}
        missing = [key for key, field in value.items() if not field]
        if missing:
            raise SystemExit(
                f"[runner] cli.configurations[{index}] 缺少: {', '.join(missing)}")
        if value["id"] in seen:
            raise SystemExit(f"[runner] CLI 配置 id 重复: {value['id']}")
        seen.add(value["id"])
        configurations.append(value)

    policy = cli.get("retry_policy") or {}
    retries = int(policy.get("content_rejection_retries_per_config", 1))
    if retries < 0:
        raise SystemExit("[runner] content_rejection_retries_per_config 不能为负")
    scope = str(policy.get("auth_failure_scope") or "suite")
    if scope != "suite":
        raise SystemExit("[runner] auth_failure_scope 当前只支持 suite")
    return configurations, {
        "content_rejection_retries_per_config": retries,
        "auth_failure_scope": scope,
    }


def select_cli(configurations: list[dict[str, str]], config_id: str | None) -> dict[str, str]:
    selected = config_id or configurations[0]["id"]
    for item in configurations:
        if item["id"] == selected:
            return dict(item)
    raise SystemExit(f"[runner] 未知 CLI 配置: {selected}")
