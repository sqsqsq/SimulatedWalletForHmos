"""把 AR90004 金样放进一个需求工作区，经生产入口 `story-build check --feature` 判。

金样是判据的仲裁锚：任何判据拦金样，错的是判据。它要在与真实需求同一条路径上被判，
所以这里搭的是一份完整的需求工作区，而不是给机制开一个只读单文件的旁路：

- 输入夹具（上游材料、提取稿、原件）用真实流程命令走材料关卡、范围关卡、关联设计对象并冻结输入；
- 设计按这份输入准入 AR90004 自己的蓝图（`golden_design.install`，设计事实取自同一批上游原文）；
- 金样正文按映射表迁移旧元数据（`golden_design.migrate`）后放进去，附录机器区由当前 renderer 从蓝图重投，
  再逐项核映射表登记的旧事实在新输出里都在（`golden_design.verify`）。

正本 `test/golden/story-金样-AR90004.md` 与输入夹具都不改；1.x 的 spec 不进工作区，只作迁移的出处。
知识用夹具自带的快照（`fixtures/golden/knowledge/`）：金样附录·规约那张表是那一刻知识的投影，
Demo 知识随后怎么演进都不该挪动这个锚。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "test" / "tests"))
sys.path.insert(0, str(REPO_ROOT / "test" / "scripts"))
from ext_workspace import link_harness_yaml  # noqa: E402
import design_fixture  # noqa: E402
import golden_design  # noqa: E402

FEATURE = "AR90004"
EXT = REPO_ROOT / "extensions"
GOLDEN = REPO_ROOT / "test" / "golden"
GOLDEN_STORY = GOLDEN / "story-金样-AR90004.md"
INPUT = REPO_ROOT / "test" / "fixtures" / "golden" / FEATURE
KNOWLEDGE = REPO_ROOT / "test" / "fixtures" / "golden" / "knowledge"
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


def _hand_to_design(root: Path, ext: Path, src: Path) -> None:
    """真实流程命令走到交给设计：材料关卡、范围关卡、关联 bp-AR90004、按提取稿 AR/design.md 冻结输入。"""
    script = ext / "skills" / "story" / "scripts" / "core" / "story_flow.py"

    def flow(*args: str) -> dict:
        proc = subprocess.run([sys.executable, str(script), *args, "--feature", FEATURE, "--project-root", str(root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(f"{args}: {proc.stdout}\n{proc.stderr}")
        return json.loads(proc.stdout[proc.stdout.index("{"):])

    flow("init")
    # 收件箱里的界面原型说明归 UX，由导入入口转换并接进本轮（与真实使用时 AI 按人的说明归类同一条路）
    inbox = src.parents[1] / "inbox"
    (inbox / ".classify.json").write_text(json.dumps({"紧急挂失界面原型说明.docx": "UX"}, ensure_ascii=False),
                                          encoding="utf-8")
    proc = subprocess.run([sys.executable, str(script.parent / "import_sources.py"), "--feature", FEATURE,
                           "--project-root", str(root)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"import_sources: {proc.stdout}\n{proc.stderr}")
    flow("round")
    design_fixture.write_gaps(src)
    design_fixture.answer(flow, "material_scope", "金样：现有材料就是全部", "--chosen", "confirm_scope")
    (src / ".positioning.json").write_text(json.dumps(
        {"scope_text": "本 AR 承载交通卡紧急挂失（钱包端）", "sr_related_ars": []}, ensure_ascii=False), encoding="utf-8")
    (src / ".scope-options.json").write_text(json.dumps(
        [{"key": "carry_all", "label": "按当前范围整体承载"}], ensure_ascii=False), encoding="utf-8")
    flow("round")
    design_fixture.answer(flow, "scope_decision", "金样：整体承载", "--chosen", "carry_all")
    flow("bind-design", "--component", golden_design.COMPONENT, "--blueprint", golden_design.BLUEPRINT_ID)
    (src / "design-input.json").write_text(json.dumps(design_fixture.design_input(src), ensure_ascii=False),
                                           encoding="utf-8")
    flow("complete", "--from", "AR/design.md", "--input", "AR/story-src/design-input.json")


def build(root: Path, story: str | None = None, extensions: Path = EXT) -> Path:
    """在 `root` 下搭工作区，返回需求目录。`story` 给了就用它代替金样正文（同样按映射表迁移）。"""
    ext = root / "doc" / "extensions"
    shutil.copytree(extensions, ext, ignore=shutil.ignore_patterns("node_modules", "__pycache__"))
    _use_snapshot(ext)
    link_harness_yaml(root)
    design_fixture.ensure_framework(root)
    catalog = root / "doc" / "module-catalog.yaml"
    if not catalog.exists():
        shutil.copy2(REPO_ROOT / "demo" / "doc" / "module-catalog.yaml", catalog)
    feature = root / "doc" / "features" / FEATURE
    shutil.copytree(INPUT, feature, ignore=lambda d, names: ["spec"] if Path(d) == INPUT else [])
    src = feature / "AR" / "story-src"
    _hand_to_design(root, ext, src)
    access = ext / "hooks" / "shared" / "framework-access.mjs"
    items = design_fixture.handed_items(root, FEATURE, access)
    golden_design.install(root, items, access, ext / "knowledge")
    (feature / "AR" / "story.md").write_bytes(golden_design.migrate(
        GOLDEN_STORY.read_text(encoding="utf-8") if story is None else story).encode("utf-8"))
    # 附录机器区按蓝图重投；蓝图没准入时投不出来，旧机器区原样留着，由 check 照实报
    story_build(root, "project")
    return feature


def story_build(root: Path, command: str) -> tuple[int, str]:
    build_script = root / "doc" / "extensions" / "skills" / "story" / "scripts" / "core" / "story-build.mjs"
    proc = subprocess.run(
        ["node", str(build_script), command, "--feature", FEATURE, "--project-root", str(root)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def check(root: Path) -> tuple[int, str]:
    return story_build(root, "check")


def story(root: Path) -> str:
    return (root / "doc" / "features" / FEATURE / "AR" / "story.md").read_text(encoding="utf-8")
