"""流程侧读 Framework 原生能力：经 `hooks/shared/framework-access.mjs` 起一次 node，取回它的 JSON。

退出 0/1 都是原生给出的结果（1 带 issues）；2 与起不来是工具故障，报读取失败，不推定成「还没有」。
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from flow.state import SKILL_ROOT, FlowError

ACCESS = SKILL_ROOT.parents[1] / "hooks" / "shared" / "framework-access.mjs"


def project_root_of(feature_root: Path) -> Path:
    """需求目录所在的工程根：往上找第一个带 framework.config.json 的目录。"""
    for parent in Path(feature_root).resolve().parents:
        if (parent / "framework.config.json").is_file():
            return parent
    raise FlowError(f"{feature_root} 往上找不到 framework.config.json：需求目录要在接入了 Framework 的工程里")


def call(project_root: Path, action: str, *args: str, stdin: dict | list | None = None) -> dict:
    node = shutil.which("node")
    if node is None:
        raise FlowError("找不到 node：读 Framework 原生对象要用它")
    proc = subprocess.run([node, str(ACCESS), "--project-root", str(project_root), "--action", action, *args],
                          input=json.dumps(stdin, ensure_ascii=False) if stdin is not None else None,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode not in (0, 1) or not proc.stdout.strip():
        raise FlowError(f"读 Framework 原生对象失败（{action}）：{(proc.stderr or proc.stdout).strip()[:800]}")
    return json.loads(proc.stdout)


_PATHS: dict[tuple[str, str, tuple[str, ...]], dict] = {}


def feature_paths(project_root: Path, feature: str, phases: tuple[str, ...] = ()) -> dict:
    """逻辑 Feature 的原生物理目录与阶段报告目录（都是工程根下的绝对路径）：只读原生 `featureIdentity` /
    `featurePhaseReportsDir`，不进阶段能力解析，阶段还没开始也取得到。身份认不出、目录解析失败照原生报错。
    同一进程按（工程根、Feature、阶段集合）只取一次：这些都是配置与身份的派生，一条命令之内不变。"""
    key = (str(Path(project_root).resolve()), feature, tuple(phases))
    if key in _PATHS:
        return _PATHS[key]
    args = ["--feature", feature, *(["--report-phases", ",".join(phases)] if phases else [])]
    got = call(project_root, "feature-identity", *args)
    if got.get("status") != "ok" or not got.get("dir"):
        raise FlowError(f"Feature {feature} 的原生身份认不出：{issues_text(got)}")
    reports = {}
    for row in got.get("phase_reports") or []:
        if not row.get("dir"):
            raise FlowError(f"Feature {feature} 的 {row.get('phase')} 阶段报告目录按原生配置解析失败：{row.get('error')}")
        reports[row["phase"]] = Path(project_root) / row["dir"]
    _PATHS[key] = {"dir": Path(project_root) / got["dir"], "reports": reports, "kind": got.get("kind")}
    return _PATHS[key]


def issues_text(result: dict) -> str:
    return "；".join(f"{i.get('code') or i.get('id')} {i.get('message', '')}".strip() for i in result.get("issues", [])[:8])
