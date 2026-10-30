"""测试侧的设计来源夹具：做法在 `test/scripts/design_fixture.py`（与失效形态运行器共用），这里给定开发版扩展的
framework-access 作 ACCESS。"""
from __future__ import annotations

import json
from pathlib import Path

from design_fixture import *  # noqa: F401,F403
from ext_workspace import DEV_EXT

#: 装在临时消费工程里的开发版 framework-access：夹具用它调原生
ACCESS = DEV_EXT / "hooks" / "shared" / "framework-access.mjs"

CORE = DEV_EXT / "skills" / "story" / "scripts" / "core"


def _core_modules():
    import sys
    if str(CORE) not in sys.path:
        sys.path.insert(0, str(CORE))
    from materials import importer, registry  # noqa: PLC0415
    from flow.state import STORY_REGISTERED, file_sha256  # noqa: PLC0415
    return registry, STORY_REGISTERED, file_sha256, importer


def hand_over_state(root: Path, feature: str, contract: dict, *, with_blueprint: bool = True) -> dict:
    """把一份手写的范围已定契约补成真实的设计状态并返回：需求至少有一份已导入的正文材料（没有就导入一份最小的，
    本轮材料基准随之更新），`with_blueprint` 时放好与需求同根、需求条目采用本需求材料版本的准入蓝图。
    用于只测范围定了之后某一件事、不重演整条关卡链的用例。"""
    registry, _, _, importer = _core_modules()
    feature_root = root / features_dir(root) / feature
    manifest_file = root / "doc" / "extensions" / "manifest.yaml"
    if not manifest_file.is_file():
        # 成文依据要算激活知识的摘要：没装扩展的测试工程放一份空的激活清单
        manifest_file.parent.mkdir(parents=True, exist_ok=True)
        manifest_file.write_text("provides:\n  knowledge: []\n", encoding="utf-8")
    manifest = registry.build(feature_root)
    if not any(m["kind"] == "doc" and m.get("sha256") for m in manifest["materials"]):
        # 设计至少要采用一份原件：没有正文材料的测试工程导入一份最小的需求正文，本轮材料基准随之更新
        inbox = feature_root / "sources" / "inbox"
        (inbox / "RR").mkdir(parents=True, exist_ok=True)
        (inbox / "RR" / "prd.md").write_text("# 产品需求\n\n夹具。\n", encoding="utf-8")
        (inbox / ".classify.json").write_text('{"RR/prd.md": "RR"}', encoding="utf-8")
        importer.cmd_import(feature_root, root)
        manifest = registry.refresh(feature_root)
        contract = {**contract, "rounds": [*contract["rounds"][:-1],
                                           {**contract["rounds"][-1], "materials": {"digest": manifest["digest"]}}]}
    if with_blueprint and not (feature_root / "blueprint" / "component-blueprint.yaml").is_file():
        install_blueprint(root, feature, ACCESS)
    return contract


def registered_basis(root: Path, feature: str) -> dict:
    """这一刻真实的成文依据（与 `story_flow.py story` 登记时写的同形）：同根蓝图与材料索引要先在盘上。"""
    import subprocess  # noqa: PLC0415
    registry, registered, file_sha256, _ = _core_modules()
    proc = subprocess.run(["node", str(CORE / "story-build.mjs"), "basis", "--feature", feature, "--project-root", str(root)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"成文依据取不到：{proc.stderr[:800]}")
    feature_root = root / features_dir(root) / feature
    return {**json.loads(proc.stdout), "materials_digest": registry.build(feature_root).get("digest"),
            "files": {rel: file_sha256(feature_root / Path(*rel.split("/"))) for rel in registered}}
