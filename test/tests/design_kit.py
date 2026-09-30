"""测试侧的设计来源夹具：做法在 `test/scripts/design_fixture.py`（与失效形态运行器共用），这里给定开发版扩展的
framework-access 作 ACCESS。"""
from __future__ import annotations

import json
from pathlib import Path

from design_fixture import *  # noqa: F401,F403
from design_fixture import COMPONENT, GENERIC_DECISION  # noqa: F401
from ext_workspace import DEV_EXT

#: 装在临时消费工程里的开发版 framework-access：夹具用它调原生
ACCESS = DEV_EXT / "hooks" / "shared" / "framework-access.mjs"

CORE = DEV_EXT / "skills" / "story" / "scripts" / "core"


def _core_modules():
    import sys
    if str(CORE) not in sys.path:
        sys.path.insert(0, str(CORE))
    from materials import frozen, registry  # noqa: PLC0415
    from flow.state import STORY_REGISTERED, file_sha256  # noqa: PLC0415
    return frozen, registry, STORY_REGISTERED, file_sha256


#: 冻结设计输入时提交的最小提取稿：五段结构齐全
MIN_DRAFT = ("# 需求 — 开发需求（AR）\n\n## 1 简介\n\nx\n\n## 2 需求分析\n\nx\n\n"
             "## 3 SE 方案摘要（本部件相关）\n\nx\n\n## 4 上游索引\n\nx\n\n## 5 上游已声明线索\n\n无。\n")


def hand_over_state(root: Path, feature: str, contract: dict, *, with_blueprint: bool = True) -> dict:
    """把一份手写的收口态契约补成真实的交给设计状态并返回：准入蓝图，加上用产品的冻结模块把本轮材料全部采用、
    冻结出的设计输入。用于只测收口之后某一件事、不重演整条关卡链的用例。"""
    frozen, registry, _, _ = _core_modules()
    feature_root = root / features_dir(root) / feature
    manifest_file = root / "doc" / "extensions" / "manifest.yaml"
    if not manifest_file.is_file():
        # 成文依据要算激活知识的摘要：没装扩展的测试工程放一份空的激活清单
        manifest_file.parent.mkdir(parents=True, exist_ok=True)
        manifest_file.write_text("provides:\n  knowledge: []\n", encoding="utf-8")
    draft = feature_root / "AR" / "story-src" / "design-draft.md"
    if not draft.is_file():
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text(MIN_DRAFT, encoding="utf-8")
    manifest = registry.build(feature_root)
    if not any(m["kind"] == "doc" and m.get("sha256") for m in manifest["materials"]):
        # 冻结至少要采用一份原件：没有正文材料的测试工程放一份最小的需求正文，本轮材料基准随之更新
        (feature_root / "RR").mkdir(parents=True, exist_ok=True)
        (feature_root / "RR" / "prd.md").write_text("# 产品需求\n\n夹具。\n", encoding="utf-8")
        manifest = registry.refresh(feature_root)
        contract = {**contract, "rounds": [*contract["rounds"][:-1],
                                           {**contract["rounds"][-1], "materials": {"digest": manifest["digest"]}}]}
    adopted = [p for m in manifest["materials"] if m.get("sha256") for p in m["paths"]]
    main = next(p for m in manifest["materials"] if m["kind"] == "doc" and m.get("sha256") for p in m["paths"])
    version = frozen.freeze(feature_root, contract, {
        "adopted": adopted, "human_decision_ids": [],
        "scope_items": [{"item_id": "request-main", "kind": "requirement", "source_path": main,
                         "authority": {"owner": "需求负责人", "formality": "formal_requirement"}}],
    }, manifest, "AR/story-src/design-draft.md", "2026-09-30T00:00:00+00:00")
    ref = f"{features_dir(root)}/{feature}/AR/story-src/inputs/{version['version']}/snapshot.json"
    binding = {"component_id": COMPONENT, "blueprint_id": feature}
    if with_blueprint and not (feature_root / "blueprint" / "component-blueprint.yaml").is_file():
        items = frozen.materialization(version, ref.rsplit("/", 1)[0], binding)["items"]
        install_blueprint(root, feature, ACCESS, decisions=[GENERIC_DECISION],
                          items=[{k: v for k, v in i.items() if k != "authority"} for i in items])
    return {**contract, "design_binding": binding,
            "input": {"snapshot_ref": ref, "snapshot_sha256": version["snapshot_sha256"],
                      "materials_digest": manifest["digest"], "candidate_sha256": frozen.digest(draft.read_bytes())}}


def registered_basis(root: Path, feature: str) -> dict:
    """这一刻真实的成文依据（与 `story_flow.py story` 登记时写的同形）：流程契约里的设计关联与输入要先在盘上。"""
    import subprocess  # noqa: PLC0415
    _, _, registered, file_sha256 = _core_modules()
    proc = subprocess.run(["node", str(CORE / "story-build.mjs"), "basis", "--feature", feature, "--project-root", str(root)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"成文依据取不到：{proc.stderr[:800]}")
    feature_root = root / features_dir(root) / feature
    return {**json.loads(proc.stdout),
            "files": {rel: file_sha256(feature_root / Path(*rel.split("/"))) for rel in registered}}
