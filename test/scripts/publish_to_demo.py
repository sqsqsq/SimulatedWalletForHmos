"""把一份 Story Extension 源装进一个消费工程：测试装隔离 template，正式发布装 demo。

    python test/scripts/publish_to_demo.py --source <扩展源码目录> --target <消费工程目录> [--dry-run]

写入面三块，全部由源决定：扩展目录整体换成源（含源的示范知识，源里没有的旧文件退出）；
manifest 登记的宿主入口按 target/source 对写到目标；AGENTS.md / CLAUDE.md 的 story-ext 标记区
换成源的扩展段，区外字节不动。

写之前全部核完（源集合、入口源、目标配置、标记区、覆盖面上有没有没提交的人工修改），有问题
一次报全、目标一个字节不写。真写时先把计划与原字节落到维护域 ``output/story/install-*/``，
再逐个文件原子替换并登记；中途失败时维护者按这份清单恢复（恢复表见 1.9.8 分册 04 §1.3）。

退出码：0 已规划 / 已安装；2 预检失败；1 写入失败。stdout 是结果 JSON，诊断走 stderr。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = REPO_ROOT / "output" / "story"
DEFAULT_EXTENSION_DIR = "doc/extensions"
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
    """一份宿主入口：source 是已存在的源文件，target 是它在消费工程里的相对路径。"""
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
    manifest_path: str | None = None
    problems: list[str] = field(default_factory=list)


class Preflight(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("；".join(problems))
        self.problems = problems


def sha256(data: bytes | None) -> str | None:
    return None if data is None else hashlib.sha256(data).hexdigest()


def _excluded(rel_parts: tuple[str, ...], is_dir: bool) -> bool:
    name = rel_parts[-1]
    if name.startswith(EXCLUDED_PREFIX):
        return True
    if len(rel_parts) == 1 and name in EXCLUDED_ROOT_NAMES:
        return True
    if is_dir:
        return name in EXCLUDED_DIR_NAMES
    return Path(name).suffix in EXCLUDED_SUFFIXES


def _walk(root: Path, problems: list[str]) -> list[str]:
    """按排除清单遍历实际目录（相对 POSIX 路径、排序）；链接与重解析点报告、不跟随。"""
    out: list[str] = []

    def visit(folder: Path, parts: tuple[str, ...]) -> None:
        try:
            children = sorted(folder.iterdir(), key=lambda p: p.name)
        except OSError as exc:
            problems.append(f"读不出目录 {folder}：{exc}")
            return
        for child in children:
            rel = parts + (child.name,)
            if child.is_symlink() or child.is_junction():
                problems.append(f"源里有链接或重解析点，不跟随：{'/'.join(rel)}")
                continue
            if _excluded(rel, child.is_dir()):
                continue
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
        key = rel.casefold()
        if key in seen:
            problems.append(f"源里有只差大小写的两个路径：{seen[key]} / {rel}")
        seen[key] = rel
    if problems:
        raise Preflight(problems)
    return files


def canonical(p: str) -> str | None:
    """相对路径的规范写法：去掉 `.` 段；`..`、绝对路径、反斜杠、空段不认。"""
    if not isinstance(p, str) or "\\" in p or p.startswith("/") or (len(p) > 1 and p[1] == ":"):
        return None
    segs = [s for s in p.split("/") if s != "."]
    if not segs or any(s in ("..", "") for s in segs):
        return None
    return "/".join(segs)


def manifest_bridges(source: Path) -> list[BridgeFile]:
    """正常安装的入口来自源 manifest 的 provides.bridges（target/source 对）。"""
    doc = yaml.safe_load((Path(source) / "manifest.yaml").read_text(encoding="utf-8")) or {}
    items = (doc.get("provides") or {}).get("bridges") or []
    problems: list[str] = []
    out: list[BridgeFile] = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict) or not canonical(item.get("source", "")) or "target" not in item:
            problems.append(f"manifest provides.bridges 第 {i} 项不是合法的 target/source 对：{item!r}")
            continue
        out.append(BridgeFile(source=Path(source) / canonical(item["source"]), target=str(item["target"])))
    if problems:
        raise Preflight(problems)
    return out


def _render_zone(text: str, body: str) -> str:
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
    lines = text.split("\n")
    begins = [i for i, line in enumerate(lines) if BEGIN in line]
    ends = [i for i, line in enumerate(lines) if END in line]
    if len(begins) > 1 or len(ends) > 1:
        return f"{name} 的扩展段标记重复（begin {len(begins)} 处、end {len(ends)} 处）"
    if bool(begins) != bool(ends) or (begins and ends[0] < begins[0]):
        return f"{name} 的扩展段标记不成对"
    return None


def _extension_dir(target: Path, problems: list[str]) -> str | None:
    config = target / "framework.config.json"
    try:
        paths = (json.loads(config.read_text(encoding="utf-8-sig")) or {}).get("paths") or {}
    except (OSError, ValueError) as exc:
        problems.append(f"目标配置读不出：{config}（{exc}）")
        return None
    rel = canonical(str(paths.get("extension_dir") or DEFAULT_EXTENSION_DIR))
    if rel is None:
        problems.append(f"目标配置的 paths.extension_dir 不是工程内相对路径：{paths.get('extension_dir')!r}")
    return rel


def _case_folds(target: Path) -> bool:
    flipped = str(target).swapcase()
    return flipped != str(target) and Path(flipped).exists()


def _dirty(target: Path) -> list[str] | None:
    """目标里没提交的路径（相对目标根）；目标不在 git 里返回 None。"""
    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(target), *args], capture_output=True)
    prefix = git("rev-parse", "--show-prefix")
    if prefix.returncode != 0:
        return None
    status = git("status", "--porcelain", "-z", "-uall", "--no-renames", "--", ".")
    if status.returncode != 0:
        return None
    base = prefix.stdout.decode("utf-8").strip()
    out = []
    for entry in status.stdout.decode("utf-8", "replace").split("\0"):
        path = entry[3:]
        if entry and path.startswith(base):
            out.append(path[len(base):])
    return out


def _plan(source: Path, target: Path, bridge_files: list[BridgeFile]) -> tuple[list[dict], dict[str, bytes], str | None]:
    """算出全部文件操作；任何问题都在这里收齐后一起抛。返回（操作, 源字节快照, 源版本）。"""
    problems: list[str] = []
    source, target = Path(source).resolve(), Path(target).resolve()
    if not source.is_dir():
        raise Preflight([f"扩展源不是目录：{source}"])
    if not target.is_dir():
        raise Preflight([f"目标不是目录：{target}"])
    ext_rel = _extension_dir(target, problems)
    try:
        files = enumerate_source(source)
    except Preflight as exc:
        problems += exc.problems
        files = []
    version = None
    try:
        version = str((yaml.safe_load((source / "manifest.yaml").read_text(encoding="utf-8")) or {}).get("version"))
    except (OSError, yaml.YAMLError) as exc:
        problems.append(f"源的 manifest.yaml 读不出：{exc}")
    fold = _case_folds(target)
    key = (lambda p: p.casefold()) if fold else (lambda p: p)
    ops: list[dict] = []
    snapshot: dict[str, bytes] = {}
    #: 本次安装负责的全部路径（不论这次变不变）——脏检查的范围
    face: set[str] = set()

    def add_op(rel: str, desired: bytes, src: Path) -> None:
        face.add(key(rel))
        dst = target / rel
        before = dst.read_bytes() if dst.is_file() else None
        if before == desired:
            return
        ops.append({"path": rel, "operation": "add" if before is None else "replace",
                    "desired": desired, "before": before, "src": src})

    if ext_rel is not None:
        ext_abs = (target / ext_rel).resolve()
        if ext_abs == source or ext_abs.is_relative_to(source) or source.is_relative_to(ext_abs):
            problems.append(f"扩展源与目标安装位互相覆盖：{source} / {ext_abs}")
        else:
            for rel in files:
                try:
                    data = (source / rel).read_bytes()
                except OSError as exc:
                    problems.append(f"源文件读不出：{rel}（{exc}）")
                    continue
                snapshot[str(source / rel)] = data
                add_op(f"{ext_rel}/{rel}", data, source / rel)
            wanted = {key(rel) for rel in files}
            walk_problems: list[str] = []
            for rel in _walk(ext_abs, walk_problems):
                if key(rel) not in wanted:
                    dst = ext_abs / rel
                    ops.append({"path": f"{ext_rel}/{rel}", "operation": "delete", "desired": None,
                                "before": dst.read_bytes(), "src": None})
            problems += walk_problems
    seen: dict[str, str] = {}
    for bridge in bridge_files:
        rel = canonical(bridge.target)
        if rel is None:
            problems.append(f"入口目标不是工程内相对路径：{bridge.target!r}")
            continue
        if key(rel) in seen:
            problems.append(f"入口目标重复：{bridge.target} 与 {seen[key(rel)]} 是同一个文件")
            continue
        seen[key(rel)] = bridge.target
        if ext_rel is not None and key(rel).startswith(key(ext_rel) + "/"):
            problems.append(f"入口目标落在扩展安装位里：{bridge.target}")
            continue
        src = Path(bridge.source)
        try:
            if not src.is_file():
                raise OSError("不是文件")
            data = src.read_bytes()
        except OSError as exc:
            problems.append(f"入口源不是读得到的文件：{src}（{exc}）")
            continue
        snapshot[str(src)] = data
        add_op(rel, data, src)
    section = source / SECTION
    if section.is_file():
        raw = section.read_bytes()
        snapshot[str(section)] = raw
        body = "\n".join(line for line in raw.decode("utf-8").replace("\r\n", "\n").split("\n")
                         if not line.strip().startswith("<!-- story-ext:")).strip()
        present = [name for name in ENTRIES if (target / name).is_file()]
        if not present:
            problems.append(f"目标没有入口文件（{' / '.join(ENTRIES)}）：扩展段无处可放")
        for name in present:
            text = (target / name).read_bytes().decode("utf-8")
            issue = _zone_problem(name, text.replace("\r\n", "\n"))
            if issue:
                problems.append(issue)
                continue
            add_op(name, _render_zone(text, body).encode("utf-8"), section)
    dirty = _dirty(target)
    if dirty:
        face.update(key(op["path"]) for op in ops)
        hits = sorted(p for p in dirty if key(p) in face)
        if hits:
            problems.append("覆盖面上有没提交的修改，本命令不替人处理：" + "、".join(hits))
    if problems:
        raise Preflight(problems)
    return ops, snapshot, version


def _write_file(path: Path, data: bytes, item: dict) -> None:
    """同目录临时文件写好再原子替换；临时路径先登记在清单项里。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.install-{uuid.uuid4().hex[:8]}")
    item["temp_path"] = str(temp)
    temp.write_bytes(data)
    os.replace(temp, path)


def _save(manifest_path: Path, record: dict) -> None:
    manifest_path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")


def install_extension(source: Path, target: Path, bridge_files: list[BridgeFile], *,
                      dry_run: bool = False, evidence_root: Path = EVIDENCE_ROOT) -> InstallResult:
    source, target = Path(source).resolve(), Path(target).resolve()
    try:
        ops, snapshot, version = _plan(source, target, bridge_files)
    except Preflight as exc:
        return InstallResult("preflight_failed", None, str(target), problems=exc.problems)
    planned = [f"{op['operation']} {op['path']}" for op in ops]
    if dry_run:
        return InstallResult("planned", version, str(target), planned=planned)

    evidence_root.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="install-", dir=evidence_root))
    manifest_path = folder / "manifest.json"
    items = []
    for op in ops:
        before_path = None
        if op["before"] is not None:
            backup = folder / "before" / op["path"]
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(op["before"])
            before_path = str(backup)
        items.append({"path": op["path"], "operation": op["operation"],
                      "before_sha256": sha256(op["before"]), "before_path": before_path,
                      "desired_sha256": sha256(op["desired"]), "result": "pending", "error": None})
    record = {"source": str(source), "source_version": version, "target": str(target), "items": items}
    _save(manifest_path, record)

    completed, failed = [], []
    for op, item in zip(ops, items):
        dst = target / op["path"]
        try:
            src = op["src"]
            if src is not None and Path(src).read_bytes() != snapshot[str(src)]:
                raise RuntimeError(f"源在安装过程中变了：{src}")
            if op["operation"] == "delete":
                dst.unlink()
            else:
                _write_file(dst, op["desired"], item)
            item["result"] = "done"
            completed.append(op["path"])
        except Exception as exc:  # noqa: BLE001 —— 失败面落进清单，交维护者按恢复表处理
            item["result"], item["error"] = "failed", f"{type(exc).__name__}: {exc}"
            failed.append(op["path"])
            _save(manifest_path, record)
            return InstallResult("write_failed", version, str(target), planned, completed, failed,
                                 str(manifest_path))
        _save(manifest_path, record)
    for op in ops:
        if op["operation"] == "delete":
            folder_path = (target / op["path"]).parent
            while folder_path != target and folder_path.is_dir() and not any(folder_path.iterdir()):
                folder_path.rmdir()
                folder_path = folder_path.parent
    return InstallResult("installed", version, str(target), planned, completed, failed, str(manifest_path))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="把 Story Extension 源装进消费工程（template 或 demo）")
    ap.add_argument("--source", required=True, help="扩展源码目录")
    ap.add_argument("--target", required=True, help="消费工程目录")
    ap.add_argument("--dry-run", action="store_true", help="只输出计划，不写目标、不落清单")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    source = Path(args.source)
    try:
        bridges = manifest_bridges(source)
    except (Preflight, OSError, yaml.YAMLError) as exc:
        problems = exc.problems if isinstance(exc, Preflight) else [f"源的 manifest.yaml 读不出：{exc}"]
        result = InstallResult("preflight_failed", None, str(Path(args.target).resolve()), problems=problems)
    else:
        result = install_extension(source, Path(args.target), bridges, dry_run=args.dry_run)
    for problem in result.problems:
        print(f"[publish] {problem}", file=sys.stderr)
    if result.status == "write_failed":
        print(f"[publish] 写入中途失败：按 {result.manifest_path} 与恢复表处理后再重新预检", file=sys.stderr)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=1))
    return {"planned": 0, "installed": 0, "preflight_failed": 2}.get(result.status, 1)


if __name__ == "__main__":
    sys.exit(main())
