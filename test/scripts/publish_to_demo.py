"""把一份 Story Extension 源装进消费工程：测试装一次性 template，发布时装 demo。

    python test/scripts/publish_to_demo.py --source <扩展源码目录> --target <消费工程目录> [--dry-run]

2.0.6 目录布局：`extensions/base/` 为外网交付机制包（含 `package-manifest.yaml`、`.gitignore`、`examples/knowledge/`），
测试用 demo 示范知识与替身 adapters 位于 `test/fixtures/demo-extension/`（不进外网 `base/` 包）。
消费工程安装后形成：
  doc/extensions/base/              通用机制包
  doc/extensions/knowledge/         业务/demo 知识（来自 overlay 或源内已有目录）
  doc/extensions/adapters/          业务/demo 对接层（story.js、token.js）
  doc/extensions/adaptation.yaml    目标适配状态
  doc/extensions/manifest.yaml      运行时唯一清单（由 base/package-manifest.yaml + 身份 + 业务知识合成）

宿主入口由 `base/skills/story-adaptation/scripts/entries.mjs`（亦挂接 framework-init 的 docs.post_check）按
`base/package-manifest.yaml > provides.skills` 调 Framework 原生桥生成器物化。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_OVERLAY = REPO_ROOT / "test" / "fixtures" / "demo-extension"
EXTENSION_DIR = "doc/extensions"
BASE_ENTRIES_SCRIPT = "base/skills/story-adaptation/scripts/entries.mjs"
LEGACY_ENTRIES_SCRIPT = "skills/story-adaptation/scripts/entries.mjs"
ENTRIES_SCRIPT = BASE_ENTRIES_SCRIPT
KNOWLEDGE_SKILL_ENTRY = "base/skills/story-knowledge/SKILL.md"

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
    warnings: list[str] = field(default_factory=list)


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


def package_base_dir(source: Path) -> Path | None:
    """识别 2.0.6 `base/` 布局，返回包内 `base/` 目录；旧扁平源返回 None。"""
    source = Path(source)
    if (source / "base" / "package-manifest.yaml").is_file():
        return source / "base"
    if (source / "package-manifest.yaml").is_file():
        return source
    return None


def _lf_sha256(path: Path) -> str:
    import hashlib
    return "sha256:" + hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def verify_external_base_examples(base: Path) -> dict[str, str]:
    """核验外网 base 包内可追踪的样例清单与字节摘要，以及 .gitignore 和零替身边界。"""
    problems: list[str] = []
    gitignore = base / ".gitignore"
    if not gitignore.is_file() or "/examples/" not in gitignore.read_text(encoding="utf-8"):
        problems.append(f"机制包缺少保护 /examples/ 的 .gitignore：{base}")
    if (base / "knowledge").exists():
        problems.append(f"外网 base 包顶层不应含业务/demo knowledge/：{base / 'knowledge'}")
    for rel in enumerate_source(base):
        if "adapters/" in rel:
            problems.append(f"外网 base 包不应含替身 adapters：{rel}")
    examples = base / "examples"
    mf_path = examples / ".manifest.json"
    if not mf_path.is_file():
        problems.append(f"外网 base 包缺少可追踪样例清单 examples/.manifest.json：{base}")
        raise InputError(problems)
    try:
        manifest = json.loads(mf_path.read_text(encoding="utf-8"))
        expected = manifest.get("files") if isinstance(manifest, dict) else None
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError([*problems, f"examples/.manifest.json 读取失败：{exc}"]) from exc
    if not isinstance(expected, dict) or not expected:
        raise InputError([*problems, "examples/.manifest.json 缺少有效的 files 映射"])
    for kind in ("knowledge/facts/", "knowledge/constraints/", "knowledge/design-patterns/"):
        if not any(k.startswith(kind) for k in expected):
            problems.append(f"examples/.manifest.json 缺少 {kind} 样例")
    actual = sorted(
        p.relative_to(examples).as_posix()
        for p in examples.rglob("*")
        if p.is_file() and p.name != ".manifest.json"
    )
    missing = [k for k in expected if k not in actual]
    extra = [p for p in actual if p not in expected]
    if missing:
        problems.append(f"外网 base 包缺少约定样例文件（共 {len(missing)} 份）：{', '.join(missing[:5])}")
    if extra:
        problems.append(f"examples/ 含未登记文件：{', '.join(extra[:5])}")
    for rel, want in expected.items():
        f = examples / rel
        if f.is_file() and _lf_sha256(f) != want:
            problems.append(f"样例文件字节摘要与 .manifest.json 不符：{rel}")
    if problems:
        raise InputError(problems)
    return dict(expected)


def pack_external_base(source: Path, dest_root: Path) -> list[str]:
    """显式按外网发行范围导出 `base/` 目录（含 `.gitignore` 与受清点核验的 `examples/knowledge/`，不含 demo 知识或替身 adapters）。"""
    base = package_base_dir(source)
    if base is None:
        raise InputError([f"源缺少 base/package-manifest.yaml：{source}"])
    verify_external_base_examples(base)
    dest_base = Path(dest_root) / "base"
    if dest_base.exists():
        shutil.rmtree(dest_base)
    files = enumerate_source(base)
    for rel in files:
        dst = dest_base / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(base / rel, dst)
    return files


def import_external_base(source: Path, target: Path, *, prepare_init: bool = True) -> dict:
    """发行导入入口：先在隔离暂存区核新包与目标写面/旧清单/桥归属（零写入），全过后再解包 base/ 并预置根清单。"""
    target = Path(target).resolve()
    cfg_path = target / "framework.config.json"
    if not cfg_path.is_file():
        return {"files": [], "prepared": False, "returncode": 2, "stdout": "",
                "stderr": f"[import] 找不到 {cfg_path}：空仓首次接入请先执行 framework-init CREATE 或按最小根清单登记 docs.post_check"}
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    ext_dir = (cfg.get("paths") or {}).get("extension_dir") or EXTENSION_DIR
    ext_root = target / ext_dir
    with tempfile.TemporaryDirectory(prefix="story-import-stage-") as td:
        stage_root = Path(td)
        try:
            files = pack_external_base(source, stage_root)
        except InputError as exc:
            return {"files": [], "prepared": False, "returncode": 2, "stdout": "", "stderr": f"[import] {exc}"}
        staged_base = stage_root / "base"
        # 1) 目标已有 base/ 时，先核其未提交/未跟踪改动与 examples/ 人工文件（写前阻断，零字节改写）
        existing_base = ext_root / "base"
        if existing_base.is_dir():
            st = subprocess.run(["git", "-C", str(target), "-c", "core.quotepath=false",
                                 "status", "--porcelain", "-uall", "--", f"{ext_dir}/base"],
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
            if st.returncode == 0 and st.stdout.strip():
                return {"files": [], "prepared": False, "returncode": 2, "stdout": "",
                        "stderr": f"[import] 停：目标 {ext_dir}/base/ 存在未提交或未跟踪改动，导入前请先处理：\n{st.stdout.strip()}"}
            ex_dir = existing_base / "examples"
            if ex_dir.is_dir():
                mf_file = ex_dir / ".manifest.json"
                expected = (json.loads(mf_file.read_text(encoding="utf-8")).get("files") if mf_file.is_file() else None) or {}
                kept = []
                for f in sorted(p for p in ex_dir.rglob("*") if p.is_file() and p.name != ".manifest.json"):
                    rel = f.relative_to(ex_dir).as_posix()
                    if rel not in expected or _lf_sha256(f) != expected[rel]:
                        kept.append(f"{ext_dir}/base/examples/{rel}")
                if kept:
                    return {"files": [], "prepared": False, "returncode": 2, "stdout": "",
                            "stderr": f"[import] 停：目标 {ext_dir}/base/examples/ 含未归属或已改动文件，拒绝覆盖：{', '.join(kept)}"}
        # 2) 用隔离暂存区中的新版 adapt-scan.mjs 在写入前跑完整 --prepare-init --dry-run 预检
        if prepare_init:
            shutil.copy2(cfg_path, stage_root / "framework.config.json")
            fw_src = target / "framework"
            fw_dst = stage_root / "framework"
            if fw_src.is_dir() and not fw_dst.exists():
                import os
                if os.name == "nt":
                    subprocess.run(["cmd", "/c", "mklink", "/J", str(fw_dst), str(fw_src)], check=True, capture_output=True)
                else:
                    fw_dst.symlink_to(fw_src, target_is_directory=True)
            staged_scan = staged_base / "skills" / "story-adaptation" / "scripts" / "adapt-scan.mjs"
            pre = subprocess.run(
                ["node", str(staged_scan), "--prepare-init", "--target", str(target),
                 "--source-base", str(staged_base), "--dry-run"],
                cwd=str(target), capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            if pre.returncode != 0:
                return {"files": [], "prepared": False, "returncode": pre.returncode,
                        "stdout": pre.stdout, "stderr": pre.stderr}
        # 3) 写前核全部通过后再写入目标 base/ 与原位根清单
        pack_external_base(stage_root, ext_root)
    if not prepare_init:
        return {"files": files, "prepared": False, "returncode": 0, "stdout": "", "stderr": ""}
    scan = ext_root / "base" / "skills" / "story-adaptation" / "scripts" / "adapt-scan.mjs"
    proc = subprocess.run(["node", str(scan), "--prepare-init"], cwd=str(target),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    return {"files": files, "prepared": proc.returncode == 0, "returncode": proc.returncode,
            "stdout": proc.stdout, "stderr": proc.stderr}


def _yaml_str(value: str) -> str:
    import re
    s = str(value)
    return s if re.fullmatch(r"[A-Za-z0-9_./-]+", s) and s not in {"true", "false", "null"} else json.dumps(s, ensure_ascii=False)


def compose_root_manifest(pkg_manifest_text: str, *, name: str, description: str, knowledge_items: list) -> str:
    """与 `adapt-scan.mjs::composeManifest` 同构：把 `base/package-manifest.yaml` 合成为运行时唯一根 `manifest.yaml`。"""
    pkg = yaml.safe_load(pkg_manifest_text) or {}
    provides = pkg.get("provides") or {}
    entry = provides.get("knowledge_entry") or {}
    biz = []
    for item in knowledge_items:
        p = item.strip() if isinstance(item, str) else str((item or {}).get("path", "")).strip()
        if p and p != KNOWLEDGE_SKILL_ENTRY:
            biz.append(item)
    out = [
        f'schema_version: {json.dumps(str(pkg.get("schema_version", "1.1")), ensure_ascii=False)}',
        f"name: {name}",
        f'version: {json.dumps(str(pkg.get("version", "")), ensure_ascii=False)}',
        f"description: {description}",
        "provides:",
    ]
    if provides.get("skill_assets"):
        out.append("  skill_assets:")
        for sid, assets in provides["skill_assets"].items():
            out.append(f"    {sid}:")
            for k, v in (assets or {}).items():
                out.append(f"      {k}: {v}")
    out.append("  knowledge:")
    if entry.get("path"):
        out.append(f"    - path: {entry['path']}")
        out.append(f"      summary: {entry['summary']}")
        out.append(f"      audience: [{', '.join(entry.get('audience') or [])}]")
    for item in biz:
        if isinstance(item, str):
            out.append(f"    - {item.strip()}")
        elif isinstance(item, dict):
            out.append(f"    - path: {str(item['path']).strip()}")
            if "summary" in item:
                out.append(f"      summary: {_yaml_str(item['summary'])}")
            aud = item.get("audience")
            if isinstance(aud, list):
                out.append(f"      audience: [{', '.join(aud)}]")
            elif aud:
                out.append(f"      audience: {aud}")
    if provides.get("hooks"):
        out.append("  hooks:")
        for phase, events in provides["hooks"].items():
            out.append(f"    {phase}:")
            for ev, paths in (events or {}).items():
                out.append(f"      {ev}:")
                for p in paths or []:
                    out.append(f"        - {p}")
    if provides.get("phase_rules_overlays"):
        out.append("  phase_rules_overlays:")
        for phase, p in provides["phase_rules_overlays"].items():
            out.append(f"    {phase}: {p}")
    if pkg.get("phase_bindings"):
        out.append("phase_bindings:")
        for phase, slots in pkg["phase_bindings"].items():
            out.append(f"  {phase}:")
            for slot, items in (slots or {}).items():
                out.append(f"    {slot}:")
                for b in items or []:
                    out.append(f"      - {{kind: {b['kind']}, ref: {b['ref']}}}")
    return "\n".join(out) + "\n"


def _entries(script: Path, target: Path, *args: str) -> tuple[int, dict]:
    proc = subprocess.run(["node", str(script), "--project-root", str(target), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.returncode, {"error": proc.stderr.strip() or f"entries.mjs 退出 {proc.returncode}、无输出"}


def compose_extension_files(
    source: Path,
    *,
    overlay: Path | None = None,
    identity: tuple[str, str] = ("wallet-sdk-demo", "实例扩展包（story 需求流程 + 三类知识 + 生命周期钩子）"),
) -> tuple[dict[str, bytes], str | None, list[str], Path]:
    """把 `extensions/base/` + 业务/demo overlay 组装成目标 `doc/extensions/` 的完整文件映射（相对扩展根）。"""
    source = Path(source).resolve()
    base = package_base_dir(source)
    if base is None:
        # 兼容旧扁平夹具源
        files = enumerate_source(source)
        manifest = yaml.safe_load((source / "manifest.yaml").read_text(encoding="utf-8")) or {}
        version = str(manifest.get("version")) if manifest.get("version") is not None else None
        skills = [s for s in (manifest.get("provides") or {}).get("skills") or [] if isinstance(s, str)]
        return {rel: (source / rel).read_bytes() for rel in files}, version, skills, source / LEGACY_ENTRIES_SCRIPT

    pkg_text = (base / "package-manifest.yaml").read_text(encoding="utf-8")
    pkg = yaml.safe_load(pkg_text) or {}
    version = str(pkg.get("version")) if pkg.get("version") is not None else None
    skills = [s for s in (pkg.get("provides") or {}).get("skills") or [] if isinstance(s, str)]
    mapped: dict[str, bytes] = {}
    for rel in enumerate_source(base):
        mapped[f"base/{rel}"] = (base / rel).read_bytes()

    ov = Path(overlay).resolve() if overlay is not None else (DEMO_OVERLAY if DEMO_OVERLAY.is_dir() else None)
    # 源内自带非 base 文件（如测试改写的根 manifest/knowledge）优先，其余从 demo overlay 补齐
    if source != base:
        for rel in enumerate_source(source):
            if not rel.startswith("base/"):
                mapped[rel] = (source / rel).read_bytes()
    if ov and ov.is_dir():
        for rel in enumerate_source(ov):
            if rel not in mapped:
                mapped[rel] = (ov / rel).read_bytes()

    if "manifest.yaml" not in mapped:
        knowledge_items = sorted(p for p in mapped if p.startswith("knowledge/") and p.endswith(".md"))
        mapped["manifest.yaml"] = compose_root_manifest(
            pkg_text, name=identity[0], description=identity[1], knowledge_items=knowledge_items
        ).encode("utf-8")
    return mapped, version, skills, base / "skills/story-adaptation/scripts/entries.mjs"


def _plan(source: Path, target: Path, *, overlay: Path | None = None) -> tuple[list[tuple[str, bytes]], str | None, list[str], str]:
    problems: list[str] = []
    if not source.is_dir() or not target.is_dir():
        raise InputError([f"扩展源或目标不是目录：{source} / {target}"])
    mapped: dict[str, bytes] = {}
    version, skills, entries_script = None, [], source / BASE_ENTRIES_SCRIPT
    try:
        mapped, version, skills, entries_script = compose_extension_files(source, overlay=overlay)
    except (InputError, OSError, yaml.YAMLError) as exc:
        problems += exc.problems if isinstance(exc, InputError) else [f"扩展源读不出：{exc}"]
    writes = [(f"{EXTENSION_DIR}/{rel}", data) for rel, data in sorted(mapped.items())]
    installed_entries_rel = BASE_ENTRIES_SCRIPT if f"base/skills/story-adaptation/scripts/entries.mjs" in mapped else LEGACY_ENTRIES_SCRIPT
    if not problems:
        with tempfile.TemporaryDirectory(prefix="story-stage-") as tmp:
            stage = Path(tmp)
            for rel, data in mapped.items():
                dst = stage / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(data)
            code, plan = _entries(entries_script, target, "--action", "plan", "--skills", ",".join(skills),
                                  "--candidate", str(stage))
        if "error" in plan:
            problems.append(f"宿主入口核不了：{plan['error']}")
        problems += plan.get("problems", [])
        problems += [f"宿主入口冲突：{c}" for c in plan.get("conflicts", [])]
        retire = plan.get("retire", [])
    else:
        retire = []
    if problems:
        raise InputError(problems)
    return writes, version, retire, installed_entries_rel


def install_extension(source: Path, target: Path, *, overlay: Path | None = None, dry_run: bool = False) -> InstallResult:
    """入口写前核通过后，删掉整个目标扩展目录、写组装后的全部文件，再交 Framework 物化宿主入口。"""
    source, target = Path(source).resolve(), Path(target).resolve()
    try:
        writes, version, retire, entries_rel = _plan(source, target, overlay=overlay)
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
    code, result = _entries(target / EXTENSION_DIR / entries_rel, target,
                            "--action", "materialize", "--retire", ",".join(retire))
    completed += result.get("written", []) + [f"remove {rel}" for rel in result.get("removed", [])]
    problems = ([result["error"]] if "error" in result else []) + result.get("problems", [])
    if code != 0 or problems:
        return InstallResult("write_failed", version, str(target), planned, completed,
                             ["materialize host entries"], problems, result.get("warnings", []))
    return InstallResult("installed", version, str(target), planned, completed, warnings=result.get("warnings", []))


def git_dirty(target: Path) -> list[str]:
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
    ap.add_argument("--overlay", default=None, help="可选业务/demo 知识与 adapters 覆盖目录")
    ap.add_argument("--dry-run", action="store_true", help="只输出计划，不写目标")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    target = Path(args.target).resolve()
    try:
        dirty = git_dirty(target)
        if dirty:
            raise InputError(["目标有没提交的改动，先核对、提交或处理后再装：" + "；".join(dirty[:10])])
        result = install_extension(Path(args.source), target,
                                   overlay=Path(args.overlay) if args.overlay else None,
                                   dry_run=args.dry_run)
    except (InputError, OSError, yaml.YAMLError) as exc:
        problems = exc.problems if isinstance(exc, InputError) else [f"扩展源读不出：{exc}"]
        result = InstallResult("preflight_failed", None, str(target), problems=problems)
    for problem in result.problems:
        print(f"[publish] {problem}", file=sys.stderr)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=1))
    return {"planned": 0, "installed": 0, "preflight_failed": 2}.get(result.status, 1)


if __name__ == "__main__":
    sys.exit(main())
