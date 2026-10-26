"""Validated Story test CLI configuration groups.

This module contains no credentials.  It only validates the ordered CLI/model
selectors that the unified ``tools.cli`` registry consumes.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

#: Framework 的 dsh adapter 把独立审查员物化成工程里的配置层；dsh 不扫描工程目录，
#: 启动与续跑都要显式 ``--patch`` 装载它。
DSH_VERIFIER_OVERLAY = ".dsh/framework-verifier.patch.yml"
#: suite 生成的调用配置快照；只收需要改调用参数的宿主，其余宿主照用中央注册表。
CLI_REGISTRY_ENV = "STORY_CLI_REGISTRY"


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
        limit = item.get("limit")
        if limit is not None:
            # 启动时交给 opencode 的模型上限：它按层校验，context、input、output 三项都要给
            keys = ("context", "input", "output")
            if value["name"] != "opencode" or not isinstance(limit, dict) or set(limit) != set(keys) \
                    or not all(isinstance(limit[k], int) and limit[k] > 0 for k in keys) or limit["input"] > limit["context"]:
                raise SystemExit(f"[runner] cli.configurations[{index}].limit 只给 opencode，"
                                 "要有正整数 context、input、output 三项且 input 不大于 context")
            value["limit"] = {k: limit[k] for k in keys}
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


def registry_snapshot(configurations: list[dict[str, str]],
                      central: dict[str, Any]) -> dict[str, Any] | None:
    """本组用到 dsh 时，给出只含 dsh 一项、启动与续跑都装载审查员配置层的调用配置。"""
    if not any(item["name"] == "dsh" for item in configurations):
        return None
    entry = copy.deepcopy((central.get("clis") or {}).get("dsh") or {})
    if not entry.get("profiles"):
        raise SystemExit("[runner] 中央注册表没有 dsh 条目，无法生成 suite 调用配置")
    for name, profile in entry["profiles"].items():
        for key in ("args", "resume_args"):
            argv = list(profile.get(key) or [])
            if "--profile" not in argv:
                raise SystemExit(f"[runner] dsh 档位 {name}.{key} 没有 --profile，找不到配置层插入位置")
            at = argv.index("--profile") + 2
            profile[key] = argv[:at] + ["--patch", "{cwd}/" + DSH_VERIFIER_OVERLAY] + argv[at:]
    return {**{key: value for key, value in central.items() if key != "clis"},
            "clis": {"dsh": entry}}


def registry_for(cli_name: str, environ: dict[str, str] | None = None) -> Path | None:
    """suite 快照里有这个宿主就用快照，否则返回 None（照用中央注册表）。"""
    snapshot = (environ if environ is not None else os.environ).get(CLI_REGISTRY_ENV, "").strip()
    if not snapshot:
        return None
    path = Path(snapshot)
    clis = json.loads(path.read_text(encoding="utf-8")).get("clis") or {}
    return path if cli_name in clis else None
