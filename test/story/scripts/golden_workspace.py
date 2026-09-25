"""把 AR90004 金样放进一个需求工作区，经生产入口 `story-build check --feature` 判。

金样是判据的仲裁锚：任何判据拦金样，错的是判据。它要在与真实需求同一条路径上被判，
所以这里搭的是一份完整的需求工作区——输入夹具（上游材料、spec、知识判断、写作设计、
决策登记、原件）+ 金样正文与归档图片 + 当前机制——而不是给机制开一个只读单文件的旁路。

知识用夹具自带的快照（`fixtures/golden/knowledge/`）：金样的规约判定表是那一刻知识的投影，
Demo 知识随后怎么演进都不该挪动这个锚。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "test" / "story" / "tests"))
from ext_workspace import link_harness_yaml  # noqa: E402

FEATURE = "AR90004"
EXT = REPO_ROOT / "doc" / "extensions"
GOLDEN = REPO_ROOT / "test" / "story" / "golden"
GOLDEN_STORY = GOLDEN / "story-金样-AR90004.md"
GOLDEN_IMAGES = ("image1.png", "image2.png")
INPUT = REPO_ROOT / "test" / "story" / "fixtures" / "golden" / FEATURE
KNOWLEDGE = REPO_ROOT / "test" / "story" / "fixtures" / "golden" / "knowledge"
KNOWLEDGE_ORDER = ("facts", "constraints", "design-patterns")


def activation() -> list[str]:
    """快照的激活清单：按类目录、目录内按文件名，顺序固定，清单指纹才固定。"""
    return [f"knowledge/{kind}/{p.name}" for kind in KNOWLEDGE_ORDER
            for p in sorted((KNOWLEDGE / kind).glob("*.md"))]


def _use_snapshot(ext: Path) -> None:
    shutil.rmtree(ext / "knowledge")
    shutil.copytree(KNOWLEDGE, ext / "knowledge")
    manifest = ext / "manifest.yaml"
    rows = manifest.read_text(encoding="utf-8").split("\n")
    at = rows.index("  knowledge:")
    end = at + 1
    while end < len(rows) and rows[end].startswith("    - "):
        end += 1
    rows[at + 1:end] = [f"    - {rel}" for rel in activation()]
    manifest.write_text("\n".join(rows), encoding="utf-8")


def build(root: Path, story: str | None = None, extensions: Path = EXT) -> Path:
    """在 `root` 下搭工作区，返回需求目录。`story` 给了就用它代替金样正文。"""
    ext = root / "doc" / "extensions"
    shutil.copytree(extensions, ext, ignore=shutil.ignore_patterns("node_modules", "__pycache__"))
    _use_snapshot(ext)
    link_harness_yaml(root)
    feature = root / "doc" / "features" / FEATURE
    shutil.copytree(INPUT, feature)
    (feature / "AR" / "story.md").write_text(
        GOLDEN_STORY.read_text(encoding="utf-8") if story is None else story, encoding="utf-8")
    (feature / "AR" / "assets").mkdir(parents=True, exist_ok=True)
    for name in GOLDEN_IMAGES:
        shutil.copy2(GOLDEN / "assets" / name, feature / "AR" / "assets" / name)
    return feature


def story_build(root: Path, command: str) -> tuple[int, str]:
    build_script = root / "doc" / "extensions" / "skills" / "story" / "scripts" / "core" / "story-build.mjs"
    proc = subprocess.run(
        ["node", str(build_script), command, "--feature", FEATURE, "--project-root", str(root)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def check(root: Path) -> tuple[int, str]:
    return story_build(root, "check")
