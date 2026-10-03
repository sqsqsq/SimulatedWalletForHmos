"""设计输入的冻结：本次交给设计的采用集合、路径、摘要与复用，只在这一处定义。

选集 = 模型给的采用原件（含图片）+ 候选提取稿（派生分析）+ 脚本从流程契约导出的真实人签。
原件里的本地相对引用（图片、链接）必须落在选集内；外部链接不复制。

冻结目录 `AR/story-src/inputs/<64 位 hex>/`：`files/<需求相对路径>` 按原始字节保存，`snapshot.json`
写排序的文件行、语义条目、人签编号与冻结时刻。目录名 = 除 `observed_at` 之外完整快照的规范 JSON 的 SHA-256，
所以同一候选、同一采用集合、同一批人签总得到同一个版本；已有的同名目录全部核对后复用，冻结时刻沿用。
先在临时目录写全、复核，再改名为最终版本——中断只留下临时目录，不留半个版本。

设计输入 `AR/story-src/design-input.json` 由模型写：

    {"adopted": [需求相对路径...], "human_decision_ids": [ask_id...],
     "scope_items": [{"item_id", "kind", "source_path", "authority": {"owner", "formality"}}...]}

语义身份（item_id、kind、authority）来自材料与人签，由模型给；路径、摘要与 provenance 由本模块生成。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from hashlib import sha256
from pathlib import Path, PurePosixPath

from materials import importer

INPUTS = ("AR", "story-src", "inputs")
SNAPSHOT = "snapshot.json"
MATERIALIZATION = "materialization.json"
#: 人签导出在冻结集合里的名字；工作区里没有这份文件，它只存在于冻结版本中
HUMAN_RECORD = "AR/story-src/human-decisions.json"
IMAGE_SUFFIXES = importer.IMAGE_EXTS | {".svg", ".gif"}
#: 原生 currentScopeItem 的类别
KINDS = ("requirement", "goal", "invariant", "high_risk")
FORMALITIES = ("formal_requirement", "non_formal_maintenance", "unspecified")
#: 每类文件能证明的来源性质。原件与图片只证明冻结时读到了这些字节（observed），其中哪句话是正式授权结论
#: 由设计与审查按内容判；人签是人的原话（authoritative）；提取稿是分析（inferred）。
PROVENANCE = {
    "original": {"source_kind": "requirement_material", "extraction_method": "frozen_file_observation", "evidence_strength": "observed"},
    "image": {"source_kind": "requirement_image", "extraction_method": "frozen_file_observation", "evidence_strength": "observed"},
    "human_record": {"source_kind": "human_decision", "extraction_method": "recorded_user_reply", "evidence_strength": "authoritative"},
    "extracted_analysis": {"source_kind": "extracted_analysis", "extraction_method": "extracted_analysis", "evidence_strength": "inferred"},
}
#: Markdown 链接与图片、HTML img 的目标
REFERENCE = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)|<img\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I)


class FrozenError(Exception):
    """冻结不成立：带具体路径与缘由，交给调用方原样报出。"""


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def need_relative(raw: object, what: str) -> str:
    """需求相对 POSIX 路径：不许绝对路径、不许走出需求目录。"""
    text = str(raw or "").strip().replace("\\", "/")
    path = PurePosixPath(text)
    if not text or path.is_absolute() or re.match(r"^[A-Za-z]:", text) or ".." in path.parts:
        raise FrozenError(f"{what} 不是需求目录内的相对路径：{raw!r}")
    return path.as_posix()


def read_input(feature_root: Path, rel: str) -> dict:
    path = feature_root / rel
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise FrozenError(f"设计输入 {rel} 读不到（{exc}）：按 phases/design.md 写好采用集合再提交") from exc
    except ValueError as exc:
        raise FrozenError(f"设计输入 {rel} 不是合法 JSON（{exc}）") from exc
    if not isinstance(data, dict) or not isinstance(data.get("adopted"), list) \
            or not isinstance(data.get("human_decision_ids"), list) or not isinstance(data.get("scope_items"), list):
        raise FrozenError(f"设计输入 {rel} 要有 adopted、human_decision_ids、scope_items 三个数组")
    return data


def adopted_files(feature_root: Path, adopted: list, manifest: dict) -> list[str]:
    """采用的原件：每份都是本轮确认的材料（材料清单里登记着），字节仍是确认时那一份由调用方先核。"""
    registered = {p for m in manifest.get("materials", []) for p in m.get("paths", [])}
    out: list[str] = []
    for raw in adopted:
        rel = need_relative(raw, "adopted 里的一项")
        if rel not in registered:
            raise FrozenError(f"adopted 里的 {rel} 不是本轮确认的材料（不在材料清单里）")
        if rel not in out:
            out.append(rel)
    if not out:
        raise FrozenError("adopted 是空的：至少采用一份本轮确认的原件")
    return out


def effective_human_records(contract: dict) -> list[dict]:
    """当前有效的人签：同一关卡（会议话题按话题分）只认最后一条人给出、已生效的记录。

    之后的轮次重新答过同一关卡（reopen 或补料后重问），前一条就被替代；没有重问的关卡沿用原记录。
    """
    latest: dict[tuple, dict] = {}
    for r in contract.get("rounds", []):
        for g in r.get("gates", []):
            if g.get("by") == "human" and g.get("outcome") == "accepted":
                latest[(g.get("gate"), g.get("meeting"), g.get("item"))] = dict(g, round=r.get("round"))
    return list(latest.values())


def human_records(contract: dict, ids: list) -> list[dict]:
    """人签导出：每个编号都要对得上一条当前有效的人签，原话、所选项与各自的时刻照录。"""
    records = effective_human_records(contract)
    superseded = {g.get("ask_id") for r in contract.get("rounds", []) for g in r.get("gates", [])
                  if g.get("by") == "human" and g.get("outcome") == "accepted"}
    out: list[dict] = []
    for raw in ids:
        ask_id = str(raw or "").strip()
        hits = [g for g in records if g.get("ask_id") == ask_id]
        if not hits:
            raise FrozenError(f"human_decision_ids 里的 {ask_id!r} "
                              + ("已被之后同一关卡的人签替代，不是当前有效的决定" if ask_id in superseded
                                 else "在流程契约里找不到人给出、已生效的关卡记录"))
        out.extend({k: g[k] for k in ("ask_id", "gate", "round", "chosen", "no", "label", "reply", "at", "meeting", "item")
                    if k in g} for g in hits)
    return out


def references(text: str) -> list[tuple[str, bool]]:
    """正文里的本地引用目标（去掉锚点与查询串）与它是不是图；外部地址、页内锚点不算。"""
    out: list[tuple[str, bool]] = []
    for m in REFERENCE.finditer(text):
        target = (m.group(1) or m.group(2) or "").strip()
        if not target or target.startswith("#") or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
            continue
        target = re.split(r"[#?]", target, maxsplit=1)[0]
        if target:
            image = m.group(0).startswith("!") or m.group(2) is not None or PurePosixPath(target).suffix.lower() in IMAGE_SUFFIXES
            out.append((target, image))
    return out


def closure_problems(feature_root: Path, originals: list[str], chosen: set[str]) -> tuple[list[str], list[str]]:
    """原件里的本地引用：图要在采用集合里，缺的报出具体路径，不按同名去找；普通链接指向没采用的文件，
    列为没纳入本次冻结的参考，由模型判断要不要补成材料——参考链接不是采用义务，不拦冻结。"""
    problems: list[str] = []
    notes: list[str] = []
    for rel in originals:
        if PurePosixPath(rel).suffix.lower() in IMAGE_SUFFIXES:
            continue
        text = (feature_root / rel).read_bytes().decode("utf-8", errors="replace")
        for target, image in references(text):
            joined = os.path.normpath(os.path.join(os.path.dirname(rel), target)).replace("\\", "/")
            if joined in chosen:
                continue
            outside = joined.startswith("../") or joined == ".."
            if image:
                problems.append(f"{rel} 引用图 {target}，" + ("指到了需求目录外——图先经导入入口进入需求材料"
                                                             if outside else f"（{joined}）它不在采用集合里"))
            else:
                notes.append(f"{rel} 链接 {target}" + ("（需求目录外）" if outside else f"（{joined}）")
                             + "：没纳入本次冻结，它的内容不算已取得的来源")
    return problems, notes


def scope_items(raw: list, chosen: set[str]) -> list[dict]:
    """语义条目：身份、类别、权威由模型从材料与人签取，这里只核形状与来源落在选集里。"""
    out: list[dict] = []
    for i, item in enumerate(raw):
        where = f"scope_items[{i}]"
        if not isinstance(item, dict):
            raise FrozenError(f"{where} 不是对象")
        if not str(item.get("item_id") or "").strip():
            raise FrozenError(f"{where} 缺 item_id")
        if item.get("kind") not in KINDS:
            raise FrozenError(f"{where}.kind 要是 {'/'.join(KINDS)} 之一")
        source = need_relative(item.get("source_path"), f"{where}.source_path")
        if source not in chosen:
            raise FrozenError(f"{where}.source_path {source} 不在采用集合里")
        authority = item.get("authority") or {}
        if not str(authority.get("owner") or "").strip() or authority.get("formality") not in FORMALITIES:
            raise FrozenError(f"{where}.authority 要有 owner 与 formality（{'/'.join(FORMALITIES)}）")
        out.append({**item, "source_path": source})
    if not out:
        raise FrozenError("scope_items 是空的：设计至少要一项有来源的需求条目")
    return out


def selection(feature_root: Path, contract: dict, design_input: dict, manifest: dict,
              candidate_rel: str) -> tuple[dict[str, bytes], dict[str, str], dict]:
    """选集的字节、各文件角色，以及不含冻结时刻的快照主体。"""
    originals = adopted_files(feature_root, design_input["adopted"], manifest)
    decisions = human_records(contract, design_input["human_decision_ids"])
    files: dict[str, bytes] = {rel: (feature_root / rel).read_bytes() for rel in originals}
    roles = {rel: ("image" if PurePosixPath(rel).suffix.lower() in IMAGE_SUFFIXES else "original") for rel in originals}
    candidate = need_relative(candidate_rel, "候选提取稿")
    files[candidate], roles[candidate] = (feature_root / candidate).read_bytes(), "extracted_analysis"
    if decisions:
        files[HUMAN_RECORD] = json.dumps({"decisions": decisions}, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
        roles[HUMAN_RECORD] = "human_record"
    problems, notes = closure_problems(feature_root, originals, set(files))
    if problems:
        raise FrozenError("原件引用的图没有闭合在采用集合里：" + "；".join(problems))
    body = {
        "files": [{"path": rel, "sha256": digest(files[rel]), "role": roles[rel], "provenance": PROVENANCE[roles[rel]]}
                  for rel in sorted(files)],
        "scope_items": scope_items(design_input["scope_items"], set(files)),
        "human_decision_ids": [str(x).strip() for x in design_input["human_decision_ids"]],
    }
    return files, roles, body, notes


def verify(directory: Path, body: dict) -> dict:
    """已有版本：快照主体与每份文件的原始字节都要对得上。返回盘上的快照。"""
    try:
        snapshot = json.loads((directory / SNAPSHOT).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise FrozenError(f"冻结版本 {directory.name} 的 {SNAPSHOT} 读不出来（{exc}）：版本已损坏") from exc
    if {k: v for k, v in snapshot.items() if k != "observed_at"} != body:
        raise FrozenError(f"冻结版本 {directory.name} 的快照与目录名对不上：版本已损坏")
    for row in body["files"]:
        path = directory / "files" / Path(*row["path"].split("/"))
        if not path.is_file() or digest(path.read_bytes()) != row["sha256"]:
            raise FrozenError(f"冻结版本 {directory.name} 里的 {row['path']} 缺失或字节变了：版本已损坏")
    return snapshot


def current_version(feature_root: Path, contract: dict, design_input: dict, manifest: dict, candidate_rel: str) -> str:
    """按当前设计输入（采用集合、需求条目、有效人签）、提取稿与采用文件的字节，算出现在冻结会得到的版本号。只读。"""
    _, _, body, _ = selection(feature_root, contract, design_input, manifest, candidate_rel)
    return digest(canonical(body))


def freeze(feature_root: Path, contract: dict, design_input: dict, manifest: dict, candidate_rel: str,
           observed_at: str) -> dict:
    """冻结一版设计输入，返回版本号、目录与快照。同一内容复用已有版本（版本号与 `current_version` 同一算法）。"""
    files, _, body, notes = selection(feature_root, contract, design_input, manifest, candidate_rel)
    version = digest(canonical(body))
    root = feature_root / Path(*INPUTS)
    final = root / version
    if final.exists():
        snapshot = verify(final, body)
    else:
        staging = root / f".staging-{uuid.uuid4().hex}"
        try:
            for rel, data in files.items():
                target = staging / "files" / Path(*rel.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            snapshot = {**body, "observed_at": observed_at}
            (staging / SNAPSHOT).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            verify(staging, body)
            staging.rename(final)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    return {"version": version, "dir": final, "snapshot": snapshot,
            "snapshot_sha256": digest((final / SNAPSHOT).read_bytes()), "unadopted_references": notes}


def materialization(frozen: dict, project_rel_dir: str, binding: dict) -> dict:
    """冻结版本的来源物化（requirement-source-materialization@1）：source_ref 指冻结目录里的最终文件。

    来源时刻都是首次冻结时读到（导出）这份文件的时刻，重复导出沿用：原件与图片按 `frozen_file_observation`
    标明是本次文件观察，不冒充原取得时间；人签合并文件记导出时刻，每条原话的时刻留在文件里各自的 `at`。
    """
    snapshot = frozen["snapshot"]
    rows = {row["path"]: row for row in snapshot["files"]}
    items = []
    for item in snapshot["scope_items"]:
        row = rows[item["source_path"]]
        ref = f"{project_rel_dir}/files/{row['path']}"
        provenance = {**row["provenance"], "source_ref": ref, "observed_at": snapshot["observed_at"]}
        entry = {"item_id": item["item_id"], "kind": item["kind"], "source_ref": ref,
                 "source_sha256": "sha256:" + row["sha256"], "provenance": provenance, "authority": item["authority"]}
        if item.get("source_revision"):
            entry["source_revision"] = provenance["source_revision"] = str(item["source_revision"])
        items.append(entry)
    return {"artifact": "requirement-source-materialization@1", "component_id": binding["component_id"],
            "blueprint_id": binding["blueprint_id"], "items": items}
