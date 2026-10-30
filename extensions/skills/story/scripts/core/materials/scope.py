"""需求条目的来源补齐：条目的语义由模型给一次，来源的路径、摘要与 provenance 由脚本按材料索引补。

模型写 `[{item_id, kind, source, authority: {owner, formality}}]`：`source` 是需求相对路径（可带 `#片段`），
必须是材料索引登记过的版本文件（原件、阅读稿、图或人工答复）。脚本补工程相对的 `source_ref`、盘上字节核过的
`source_sha256` 与 provenance，得到原生 `currentScopeItem` 形状，蓝图的需求条目按它写。
条目来自需求系统的来源时，同一组条目另写成原生来源物化信封（`requirement-source-materialization@1`），
放在需求的 `blueprint/` 里并过原生来源检查；本地来源只输出条目，不落 provider 文件。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from materials import importer, registry

KINDS = ("requirement", "goal", "invariant", "high_risk")
FORMALITIES = ("formal_requirement", "non_formal_maintenance", "unspecified")
MATERIALIZATION = ("blueprint", "requirement-source-materialization.json")
CANONICAL = ("blueprint", "component-blueprint.yaml")
STABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


class ScopeError(Exception):
    """条目补不齐：带具体条目与原因，原样报给调用方。"""


def read_items(path: Path) -> list[dict]:
    """读模型写的条目文件，只核形状；语义（哪条是需求、权威是谁）由模型负责。"""
    try:
        items = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ScopeError(f"条目文件 {path.name} 读不出来（{exc}）") from exc
    if not isinstance(items, list) or not items:
        raise ScopeError("条目文件要是非空数组：[{item_id, kind, source, authority: {owner, formality}}]")
    problems = []
    for i, item in enumerate(items, 1):
        where = f"第 {i} 条"
        if not isinstance(item, dict):
            problems.append(f"{where}不是对象")
            continue
        if not STABLE_ID.match(str(item.get("item_id") or "")):
            problems.append(f"{where}的 item_id 要是稳定标识（字母数字开头，只含字母数字 . _ : -）")
        if item.get("kind") not in KINDS:
            problems.append(f"{where}的 kind 取 {' / '.join(KINDS)}")
        if not str(item.get("source") or "").strip():
            problems.append(f"{where}缺 source（需求相对路径，可带 #片段）")
        authority = item.get("authority") if isinstance(item.get("authority"), dict) else {}
        if not str(authority.get("owner") or "").strip() or authority.get("formality") not in FORMALITIES:
            problems.append(f"{where}的 authority 要有 owner 与 formality（{' / '.join(FORMALITIES)}）")
    if problems:
        raise ScopeError("；".join(problems))
    return items


def _files(feature_root: Path) -> dict[str, tuple[dict, str, str]]:
    """索引登记的每份版本文件 → (版本记录, 角色, 完整摘要)。"""
    try:
        records = registry.version_records(feature_root)
    except registry.MaterialError as exc:
        raise ScopeError(str(exc)) from exc
    out: dict[str, tuple[dict, str, str]] = {}
    for rec in records:
        out[rec["original"]["path"]] = (rec, "original", rec["original"]["sha256"])
        if rec.get("readable") and rec["readable"]["path"] != rec["original"]["path"]:
            out[rec["readable"]["path"]] = (rec, "readable", rec["readable"]["sha256"])
        for image in rec.get("images") or []:
            out[image["path"]] = (rec, "image", image["sha256"])
    return out


def fill(feature_root: Path, project_root: Path, items: list[dict]) -> list[tuple[dict, dict]]:
    """逐条补来源：返回 (原生条目, 它的版本记录)。来源不是登记的版本文件或盘上字节与登记不同，一次列全再报。"""
    known = _files(feature_root)
    base = f"{importer.features_dir(project_root)}/{feature_root.name}"
    out, problems = [], []
    for item in items:
        source = str(item["source"]).strip().replace("\\", "/")
        rel, _, fragment = source.partition("#")
        hit = known.get(rel)
        if hit is None:
            problems.append(f"{item['item_id']}：{rel} 不是材料索引登记的版本文件（原件、阅读稿、图或人工答复）——"
                            "需求条目只引已导入的材料版本，见 sources/README.md")
            continue
        rec, role, sha = hit
        if registry.file_digest(feature_root / rel) != sha:
            problems.append(f"{item['item_id']}：{rel} 盘上的字节与索引登记的不同——材料版本导入后不改，恢复原件")
            continue
        ref = f"{base}/{rel}" + (f"#{fragment}" if fragment else "")
        answer = rec.get("kind") == "answer"
        provenance = {
            "source_kind": "human_decision" if answer else "requirement_image" if role == "image" else "requirement_material",
            "source_ref": ref, "source_revision": f"{rec['source_id']}@v{rec['version']}",
            "observed_at": str(rec.get("acquired_at") or ""),
            "evidence_strength": "authoritative" if answer else "observed",
            "extraction_method": "recorded_user_reply" if answer else "imported_file_observation",
        }
        entry = {"item_id": item["item_id"], "kind": item["kind"], "source_ref": ref, "source_sha256": f"sha256:{sha}",
                 "provenance": provenance, "authority": {"owner": str(item["authority"]["owner"]).strip(),
                                                         "formality": item["authority"]["formality"]}}
        out.append((entry, rec))
    if problems:
        raise ScopeError("需求条目的来源补不齐：" + "；".join(problems))
    return out


def blueprint_component(feature_root: Path) -> str | None:
    """已有蓝图归属的组件（canonical 顶层 `component_id`）；还没有蓝图为 None。"""
    path = feature_root / Path(*CANONICAL)
    if not path.is_file():
        return None
    hit = re.search(r"^component_id:\s*[\"']?([^\"'\s#]+)", path.read_text(encoding="utf-8"), re.M)
    return hit.group(1) if hit else None


def materialize(feature_root: Path, project_root: Path, items: list[dict], component: str | None) -> dict:
    """补齐条目；有需求系统来源时写原生来源物化信封并过原生检查，检查不过不写。"""
    filled = fill(feature_root, project_root, items)
    scope = [entry for entry, _ in filled]
    out: dict = {"current_scope_items": scope}
    if not any(rec.get("kind") == "system" for _, rec in filled):
        return out
    owner = blueprint_component(feature_root)
    if owner and component and component != owner:
        raise ScopeError(f"蓝图 {feature_root.name} 归属组件 {owner}，不是 --component 给的 {component}")
    component = owner or component
    if not component:
        raise ScopeError("条目来自需求系统，要写原生来源物化信封：蓝图还没建立时用 --component 给出原生设计认定的组件标识")
    doc = {"artifact": "requirement-source-materialization@1", "blueprint_id": feature_root.name,
           "component_id": component, "items": scope}
    from flow import native  # noqa: PLC0415 —— 只有系统来源要过原生来源检查
    checked = native.call(project_root, "sources", stdin=doc)
    if checked.get("status") != "ok":
        raise ScopeError(f"原生来源检查没过，信封未写：{native.issues_text(checked)}")
    path = feature_root / Path(*MATERIALIZATION)
    text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    if not path.is_file() or path.read_text(encoding="utf-8") != text:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    out["materialization"] = f"{importer.features_dir(project_root)}/{feature_root.name}/{'/'.join(MATERIALIZATION)}"
    return out
