"""Validated Story test CLI configuration groups.

This module contains no credentials.  It only validates the ordered CLI/model
selectors that the unified ``tools.cli`` registry consumes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def load_cli_group(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cli = config.get("cli") or {}
    raw = cli.get("configurations")
    if not isinstance(raw, list) or not raw:
        raise SystemExit("[runner] cli.configurations 必须是非空有序列表")
    configurations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise SystemExit(f"[runner] cli.configurations[{index}] 必须是映射")
        value: dict[str, Any] = {key: str(item.get(key) or "").strip()
                                 for key in ("id", "name", "model", "profile")}
        missing = [key for key, field in value.items() if not field]
        if missing:
            raise SystemExit(
                f"[runner] cli.configurations[{index}] 缺少: {', '.join(missing)}")
        if value["id"] in seen:
            raise SystemExit(f"[runner] CLI 配置 id 重复: {value['id']}")
        seen.add(value["id"])
        options = load_options(item.get("options"), f"cli.configurations[{index}].options")
        if options:
            value["options"] = options
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


def load_options(raw: Any, label: str) -> dict[str, list[str]]:
    """启动选项：选项名 → 相对 Case 工作区的文件路径列表（如 dsh 的 ``patch`` 配置层）。

    选项名要由中央注册表里该宿主的条目声明，展开方式归中央；这里只核形状。
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict) or not raw:
        raise SystemExit(f"[runner] {label} 必须是非空映射")
    options: dict[str, list[str]] = {}
    for name, values in raw.items():
        if (not isinstance(values, list) or not values
                or not all(isinstance(v, str) and v.strip() for v in values)):
            raise SystemExit(f"[runner] {label}.{name} 必须是非空的路径字符串列表")
        options[str(name)] = [v.strip() for v in values]
    return options


def resolve_cli_options(cli_config: dict[str, Any], workspace: Path) -> dict[str, list[str]]:
    """把启动选项解析成 Case 工作区里的绝对路径，交中央 runtime 展开。

    文件不在就在启动 CLI 之前停下：缺的多半是 demo 没物化对应的宿主件，跑起来要到阶段末尾才会发现。
    """
    resolved: dict[str, list[str]] = {}
    for name, values in (cli_config.get("options") or {}).items():
        paths = [(workspace / value).resolve() for value in values]
        missing = [str(path) for path in paths if not path.is_file()]
        if missing:
            raise SystemExit(f"[runner] CLI 配置 {cli_config['id']} 的启动选项 {name} 指向的文件不在："
                             f"{'；'.join(missing)}")
        resolved[name] = [str(path) for path in paths]
    return resolved


def select_cli(configurations: list[dict[str, Any]], config_id: str | None) -> dict[str, Any]:
    selected = config_id or configurations[0]["id"]
    for item in configurations:
        if item["id"] == selected:
            return dict(item)
    raise SystemExit(f"[runner] 未知 CLI 配置: {selected}")
