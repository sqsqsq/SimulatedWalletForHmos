"""把一份 Story Extension 源装进消费工程：测试装一次性 template，发布时装 demo。

    python test/scripts/publish_to_demo.py --source <扩展源码目录> --target <消费工程目录> [--dry-run]

顺序固定：枚举源 → 宿主入口写前核（原生渲染比对、旧入口归属，只读）→ 整体替换目标 doc/extensions（含源的
示范知识，源里没有的旧文件退出）→ 退出已核的旧入口、Framework 原生物化宿主入口并写后核。入口的核与物化只有
一份实现：扩展里的 skills/story-adaptation/scripts/entries.mjs，对外 adapt 用的也是它。

命令行用于发布 demo：git 查询必须成功、非忽略状态必须干净，否则不装；出错由维护者用 git 看改动、还原。
一次性 template 由装配直接调 install_extension，失败就丢掉重建。本脚本不回滚、不留安装日志。

退出码：0 已规划 / 已安装；2 输入读取、解析或入口写前核失败（目标没写）；1 写入或物化失败（结果里列出实际完成项）。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

EXTENSION_DIR = "doc/extensions"
ENTRIES_SCRIPT = "skills/story-adaptation/scripts/entries.mjs"

#: 源集合的排除清单（唯一一处）：源根的 adapt/；名称以 .adapt- 起头的；任意层级的这些目录；这些后缀。
EXCLUDED_ROOT_NAMES = frozenset({"adapt"})
EXCLUDED_PREFIX = ".adapt-"
EXCLUDED_DIR_NAMES = frozenset({".git", "node_modules", "__pycache__", ".pytest_cache"})
EXCLUDED_SUFFIXES = frozenset({".pyc", ".pyo"})


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


def _entries(script: Path, target: Path, *args: str) -> tuple[int, dict]:
    """跑一次 entries.mjs，返回（退出码，JSON 结果）。退出 2 或输出读不出时结果里带 error。"""
    proc = subprocess.run(["node", str(script), "--project-root", str(target), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.returncode, {"error": proc.stderr.strip() or f"entries.mjs 退出 {proc.returncode}、无输出"}


def _plan(source: Path, target: Path) -> tuple[list[tuple], str | None, list[str]]:
    """读全部输入、备好要写的内容并做宿主入口写前核；有问题就一起报告，目标不写。

    返回（写入项, 版本, 要退出的旧入口）：写入项是 (目标相对路径, 内容)。
    """
    problems: list[str] = []
    if not source.is_dir() or not target.is_dir():
        raise InputError([f"扩展源或目标不是目录：{source} / {target}"])
    try:
        files = enumerate_source(source)
    except InputError as exc:
        problems += exc.problems
        files = []
    version, skills = None, []
    try:
        manifest = yaml.safe_load((source / "manifest.yaml").read_text(encoding="utf-8")) or {}
        version = str(manifest.get("version"))
        skills = [s for s in (manifest.get("provides") or {}).get("skills") or [] if isinstance(s, str)]
    except (OSError, yaml.YAMLError) as exc:
        problems.append(f"源的 manifest.yaml 读不出：{exc}")
    writes: list[tuple] = []
    for rel in files:
        try:
            writes.append((f"{EXTENSION_DIR}/{rel}", (source / rel).read_bytes()))
        except OSError as exc:
            problems.append(f"源文件读不出：{rel}（{exc}）")
    code, plan = _entries(source / ENTRIES_SCRIPT, target, "--action", "plan", "--skills", ",".join(skills))
    if "error" in plan:
        problems.append(f"宿主入口核不了：{plan['error']}")
    problems += [f"宿主入口冲突：{c}" for c in plan.get("conflicts", [])]
    if problems:
        raise InputError(problems)
    return writes, version, plan.get("retire", [])


def install_extension(source: Path, target: Path, *, dry_run: bool = False) -> InstallResult:
    """入口写前核通过后，删掉整个目标扩展目录、写源的全部文件，再交 Framework 物化宿主入口。"""
    source, target = Path(source).resolve(), Path(target).resolve()
    try:
        writes, version, retire = _plan(source, target)
    except InputError as exc:
        return InstallResult("preflight_failed", None, str(target), problems=exc.problems)
    planned = [f"replace {EXTENSION_DIR}/", *(rel for rel, _ in writes),
               *(f"retire {rel}" for rel in retire), "materialize host entries"]
    if dry_run:
        return InstallResult("planned", version, str(target), planned=planned)
    completed: list[str] = []
    try:
        if (target / EXTENSION_DIR).exists():
            shutil.rmtree(target / EXTENSION_DIR)
    except OSError as exc:
        return InstallResult("write_failed", version, str(target), planned, completed,
                             [f"{EXTENSION_DIR}/"], [f"删除旧的 {EXTENSION_DIR} 失败：{exc}"])
    completed.append(f"{EXTENSION_DIR}/")
    for rel, data in writes:
        dst = target / rel
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
        except OSError as exc:
            return InstallResult("write_failed", version, str(target), planned, completed,
                                 [rel], [f"写 {rel} 失败：{exc}"])
        completed.append(rel)
    code, result = _entries(target / EXTENSION_DIR / ENTRIES_SCRIPT, target,
                            "--action", "materialize", "--retire", ",".join(retire))
    completed += [f"retire {rel}" for rel in result.get("removed", [])] + result.get("written", [])
    problems = ([result["error"]] if "error" in result else []) + result.get("problems", [])
    if code != 0 or problems:
        return InstallResult("write_failed", version, str(target), planned, completed,
                             ["materialize host entries"], problems)
    return InstallResult("installed", version, str(target), planned, completed)


def git_dirty(target: Path) -> list[str]:
    """发布目标（demo）在 git 里、目标之内的非忽略改动。查询失败或不在 git 里都抛 InputError——
    demo 必须拿到确定的干净结果才能发布；一次性 template 由装配直接调安装函数，不走这里。"""
    inside = subprocess.run(["git", "-C", str(target), "rev-parse", "--is-inside-work-tree"],
                            capture_output=True, text=True)
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        raise InputError([f"查不到目标的 git 状态（rev-parse 退出 {inside.returncode}）：{inside.stderr.strip()}"])
    status = subprocess.run(["git", "-C", str(target), "status", "--porcelain", "-uall", "--", "."],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if status.returncode != 0:
        raise InputError([f"git 状态查询失败：{status.stderr.strip()}"])
    return [line for line in status.stdout.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="发布：把 Story Extension 源装进 git 里的 demo（template 由装配直接调安装函数）")
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
        result = install_extension(Path(args.source), target, dry_run=args.dry_run)
    except (InputError, OSError, yaml.YAMLError) as exc:
        problems = exc.problems if isinstance(exc, InputError) else [f"源的 manifest.yaml 读不出：{exc}"]
        result = InstallResult("preflight_failed", None, str(target), problems=problems)
    for problem in result.problems:
        print(f"[publish] {problem}", file=sys.stderr)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=1))
    return {"planned": 0, "installed": 0, "preflight_failed": 2}.get(result.status, 1)


if __name__ == "__main__":
    sys.exit(main())
