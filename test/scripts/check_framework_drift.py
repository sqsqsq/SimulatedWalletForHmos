"""framework 发布件漂移自查：main 分支与 demo 各自接入的是哪一版。

    python test/scripts/check_framework_drift.py [--ref main] [--demo <demo 的 RELEASE-MANIFEST.json>]

比 ``version``，两侧的 ``source_commit`` 照实列出；同版本不同构建只作为事实展示，不声称两侧文件一致。
版本不同时指向根 AGENTS.md 的 framework 接入协议——本脚本不升级、不重装 Extension。

退出码：0 版本相同；1 版本不同；2 读取失败（git、文件、JSON 或字段）。stdout 是结果 JSON。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = "framework/RELEASE-MANIFEST.json"
DEMO_MANIFEST = REPO_ROOT / "demo" / MANIFEST
GUIDE = "按根 AGENTS.md 的 framework 接入协议，用实际发布件在 demo 执行 framework-init UPDATE 后验证并登记"


class ReadError(Exception):
    pass


def _identity(text: str, where: str) -> dict:
    try:
        doc = json.loads(text)
    except ValueError as exc:
        raise ReadError(f"{where} 不是合法 JSON：{exc}") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("version"), str) or not doc["version"]:
        raise ReadError(f"{where} 缺 version 字段")
    return {"version": doc["version"], "source_commit": doc.get("source_commit")}


def read_ref(ref: str, repo: Path = REPO_ROOT) -> dict:
    proc = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{MANIFEST}"], capture_output=True)
    if proc.returncode != 0:
        raise ReadError(f"读不出 {ref}:{MANIFEST}：{proc.stderr.decode('utf-8', 'replace').strip()}")
    return _identity(proc.stdout.decode("utf-8"), f"{ref}:{MANIFEST}")


def read_file(path: Path) -> dict:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ReadError(f"读不出 {path}：{exc}") from exc
    return _identity(text, str(path))


def compare(main: dict, demo: dict) -> tuple[int, dict]:
    same = main["version"] == demo["version"]
    result = {"status": "same_version" if same else "version_differs", "main": main, "demo": demo}
    if same and main.get("source_commit") != demo.get("source_commit"):
        result["note"] = "版本相同但构建来源不同（source_commit 不一致）；只报事实，不代表两侧文件一致"
    if not same:
        result["guide"] = GUIDE
    return (0 if same else 1), result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="比较 main 与 demo 接入的 framework 发布件版本")
    ap.add_argument("--ref", default="main", help="对照的分支或提交（缺省 main）")
    ap.add_argument("--demo", default=str(DEMO_MANIFEST), help="demo 的 RELEASE-MANIFEST.json")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        code, result = compare(read_ref(args.ref), read_file(Path(args.demo)))
    except ReadError as exc:
        code, result = 2, {"status": "read_failed", "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return code


if __name__ == "__main__":
    sys.exit(main())
