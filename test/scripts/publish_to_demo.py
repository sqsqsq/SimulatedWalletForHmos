"""把一份 Story Extension 源装进消费工程：测试装一次性 template，发布时装 demo。

    python test/scripts/publish_to_demo.py --source <扩展源码目录> --target <消费工程目录> [--dry-run]

顺序固定：枚举源 → 整体替换目标 doc/extensions（含源的示范知识，源里没有的旧文件退出）→ 按 manifest
登记的 target/source 对写宿主入口 → 用源的扩展段更新 AGENTS.md / CLAUDE.md 的 story-ext 标记区（区外不动）。

目标在 git 里时（发布 demo），非忽略状态必须干净、git 查询要成功，否则不装：出错由维护者用 git 看改动、还原。
一次性 template 失败就丢掉重建。本脚本不回滚、不留安装日志。

退出码：0 已规划 / 已安装；2 输入读取或解析失败（目标没写）；1 写入失败（结果里列出实际完成项）。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

EXTENSION_DIR = "doc/extensions"
SECTION = "skills/story/AGENTS.section.md"
ENTRIES = ("AGENTS.md", "CLAUDE.md")
BEGIN, END = "<!-- story-ext:begin -->", "<!-- story-ext:end -->"

#: 源集合的排除清单（唯一一处）：源根的 adapt/；名称以 .adapt- 起头的；任意层级的这些目录；这些后缀。
EXCLUDED_ROOT_NAMES = frozenset({"adapt"})
EXCLUDED_PREFIX = ".adapt-"
EXCLUDED_DIR_NAMES = frozenset({".git", "node_modules", "__pycache__", ".pytest_cache"})
EXCLUDED_SUFFIXES = frozenset({".pyc", ".pyo"})


@dataclass(frozen=True)
class BridgeFile:
    """一份宿主入口：source 是源文件，target 是它在消费工程里的相对路径。"""
    source: Path
    target: str


@dataclass
class InstallResult:
    status: str
    source_version: str | None
    target: str
    planned: list[str] = field(default_factory=list)
    completed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


class InputError(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("；".join(problems))
        self.problems = problems


def _excluded(parts: tuple[str, ...], is_dir: bool) -> bool:
    name = parts[-1]
    if name.startswith(EXCLUDED_PREFIX) or (len(parts) == 1 and name in EXCLUDED_ROOT_NAMES):
        return True
    return name in EXCLUDED_DIR_NAMES if is_dir else Path(name).suffix in EXCLUDED_SUFFIXES


def _walk(root: Path, problems: list[str]) -> list[str]:
    """按排除清单遍历实际目录（相对 POSIX 路径、排序）；链接与重解析点报告、不跟随。"""
    out: list[str] = []

    def visit(folder: Path, parts: tuple[str, ...]) -> None:
        for child in sorted(folder.iterdir(), key=lambda p: p.name):
            rel = parts + (child.name,)
            if child.is_symlink() or child.is_junction():
                problems.append(f"源里有链接或重解析点，不跟随：{'/'.join(rel)}")
            elif not _excluded(rel, child.is_dir()):
                if child.is_dir():
                    visit(child, rel)
                elif child.is_file():
                    out.append("/".join(rel))
    if root.is_dir():
        visit(root, ())
    return out


def enumerate_source(source: Path) -> list[str]:
    """源集合：相对源根的 POSIX 路径（排序）。已修改与未跟踪的文件都按当前字节纳入。"""
    problems: list[str] = []
    files = _walk(Path(source), problems)
    seen: dict[str, str] = {}
    for rel in files:
        if rel.casefold() in seen:
            problems.append(f"源里有只差大小写的两个路径：{seen[rel.casefold()]} / {rel}")
        seen[rel.casefold()] = rel
    if problems:
        raise InputError(problems)
    return files


def manifest_bridges(source: Path) -> list[BridgeFile]:
    """正常安装的入口来自源 manifest 的 provides.bridges（target/source 对）。"""
    doc = yaml.safe_load((Path(source) / "manifest.yaml").read_text(encoding="utf-8")) or {}
    items = (doc.get("provides") or {}).get("bridges") or []
    bad = [item for item in items if not isinstance(item, dict) or not {"source", "target"} <= item.keys()]
    if bad:
        raise InputError([f"manifest provides.bridges 每项要有 target 与 source：{bad}"])
    return [BridgeFile(source=Path(source) / item["source"], target=str(item["target"])) for item in items]


def render_zone(text: str, body: str) -> str:
    """标记区在就整段替换，不在就插到「实例扩展」一节末尾，都没有就追加到文件末尾（与 adapt 同一规则）。"""
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.replace("\r\n", "\n").split("\n")
    rows = [BEGIN, *body.split("\n"), END]
    begins = [i for i, line in enumerate(lines) if BEGIN in line]
    ends = [i for i, line in enumerate(lines) if END in line]
    if begins:
        return eol.join(lines[:begins[0]] + rows + lines[ends[0] + 1:])
    at = next((i for i, line in enumerate(lines) if re.match(r"#{2,6}\s.*实例扩展", line)), None)
    if at is not None:
        depth = len(re.match(r"#+", lines[at]).group(0))
        end = next((i for i in range(at + 1, len(lines))
                    if (m := re.match(r"(#+)\s", lines[i])) and len(m.group(1)) <= depth), len(lines))
        while end > at + 1 and not lines[end - 1].strip():
            end -= 1
        return eol.join(lines[:end] + [""] + rows + lines[end:])
    return eol.join(lines + [""] + rows + [""])


def _zone_problem(name: str, text: str) -> str | None:
    begins = text.count(BEGIN)
    ends = text.count(END)
    if begins > 1 or ends > 1:
        return f"{name} 的扩展段标记重复（begin {begins} 处、end {ends} 处）"
    if begins != ends or (begins and text.index(END) < text.index(BEGIN)):
        return f"{name} 的扩展段标记不成对"
    return None


def _plan(source: Path, target: Path, bridge_files: list[BridgeFile]) -> tuple[list[tuple], str | None]:
    """读全部输入、算出文件操作；读取或解析有问题就一起报告，目标不写。"""
    problems: list[str] = []
    if not source.is_dir() or not target.is_dir():
        raise InputError([f"扩展源或目标不是目录：{source} / {target}"])
    try:
        files = enumerate_source(source)
    except InputError as exc:
        problems += exc.problems
        files = []
    version = None
    try:
        version = str((yaml.safe_load((source / "manifest.yaml").read_text(encoding="utf-8")) or {}).get("version"))
    except (OSError, yaml.YAMLError) as exc:
        problems.append(f"源的 manifest.yaml 读不出：{exc}")
    ops: list[tuple] = []   # (操作, 目标相对路径, 内容)

    def put(rel: str, data: bytes) -> None:
        dst = target / rel
        if not (dst.is_file() and dst.read_bytes() == data):
            ops.append(("write", rel, data))

    for rel in files:
        try:
            put(f"{EXTENSION_DIR}/{rel}", (source / rel).read_bytes())
        except OSError as exc:
            problems.append(f"源文件读不出：{rel}（{exc}）")
    wanted = set(files)
    for rel in _walk(target / EXTENSION_DIR, problems):
        if rel not in wanted:
            ops.append(("delete", f"{EXTENSION_DIR}/{rel}", None))
    for bridge in bridge_files:
        try:
            put(bridge.target, Path(bridge.source).read_bytes())
        except OSError as exc:
            problems.append(f"入口源读不出：{bridge.source}（{exc}）")
    section = source / SECTION
    if section.is_file():
        raw = section.read_text(encoding="utf-8").replace("\r\n", "\n")
        body = "\n".join(line for line in raw.split("\n") if not line.strip().startswith("<!-- story-ext:")).strip()
        present = [name for name in ENTRIES if (target / name).is_file()]
        if not present:
            problems.append(f"目标没有入口文件（{' / '.join(ENTRIES)}）：扩展段无处可放")
        for name in present:
            text = (target / name).read_bytes().decode("utf-8")
            issue = _zone_problem(name, text)
            if issue:
                problems.append(issue)
            else:
                put(name, render_zone(text, body).encode("utf-8"))
    if problems:
        raise InputError(problems)
    return ops, version


def install_extension(source: Path, target: Path, bridge_files: list[BridgeFile], *,
                      dry_run: bool = False) -> InstallResult:
    source, target = Path(source).resolve(), Path(target).resolve()
    try:
        ops, version = _plan(source, target, bridge_files)
    except InputError as exc:
        return InstallResult("preflight_failed", None, str(target), problems=exc.problems)
    planned = [f"{op} {rel}" for op, rel, _ in ops]
    if dry_run:
        return InstallResult("planned", version, str(target), planned=planned)
    completed: list[str] = []
    for op, rel, data in ops:
        dst = target / rel
        try:
            if op == "delete":
                dst.unlink()
                folder = dst.parent
                while folder != target and not any(folder.iterdir()):
                    folder.rmdir()
                    folder = folder.parent
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(data)
        except OSError as exc:
            return InstallResult("write_failed", version, str(target), planned, completed,
                                 [rel], [f"{op} {rel} 失败：{exc}"])
        completed.append(rel)
    return InstallResult("installed", version, str(target), planned, completed)


def git_dirty(target: Path) -> list[str] | None:
    """目标所在 git 工作区里、目标之内的非忽略改动；目标不在 git 里返回 None，查询失败抛 InputError。"""
    inside = subprocess.run(["git", "-C", str(target), "rev-parse", "--is-inside-work-tree"],
                            capture_output=True, text=True)
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return None
    status = subprocess.run(["git", "-C", str(target), "status", "--porcelain", "-uall", "--", "."],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if status.returncode != 0:
        raise InputError([f"git 状态查询失败：{status.stderr.strip()}"])
    return [line for line in status.stdout.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="把 Story Extension 源装进消费工程（template 或 demo）")
    ap.add_argument("--source", required=True, help="扩展源码目录")
    ap.add_argument("--target", required=True, help="消费工程目录")
    ap.add_argument("--dry-run", action="store_true", help="只输出计划，不写目标")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    target = Path(args.target).resolve()
    try:
        dirty = git_dirty(target)
        if dirty:
            raise InputError(["目标有没提交的改动，先核对、提交或处理后再装：" + "；".join(dirty[:10])])
        result = install_extension(Path(args.source), target, manifest_bridges(Path(args.source)),
                                   dry_run=args.dry_run)
    except (InputError, OSError, yaml.YAMLError) as exc:
        problems = exc.problems if isinstance(exc, InputError) else [f"源的 manifest.yaml 读不出：{exc}"]
        result = InstallResult("preflight_failed", None, str(target), problems=problems)
    for problem in result.problems:
        print(f"[publish] {problem}", file=sys.stderr)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=1))
    return {"planned": 0, "installed": 0, "preflight_failed": 2}.get(result.status, 1)


if __name__ == "__main__":
    sys.exit(main())
