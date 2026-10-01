"""金样 AR90004 的 2.0 装配：用同一真实设计事实建立原生蓝图，迁移正本的旧元数据，逐项核映射表。

只在测试隔离副本里做，不改正本 `test/golden/story-金样-AR90004.md` 与输入夹具，不维护第二份可编辑金样
（2.0.0 步骤 2 实施评审 §3、步骤 4 阶段评审 §4）。

- 蓝图：`test/fixtures/golden/AR90004-design/component-blueprint.yaml` 写着 AR90004 自己的设计事实（文字取自
  SR、spec 与 AR 原文）；这里补上与设计内容无关的骨架（质询记录、供给方、应用视角）、精确明细（原文照录）、
  知识应用决定（1.x 判断逐条转写，来源取金样知识快照）与本次冻结输入推出的需求条目，按原生算法重算来源指纹并生成投影。
- 迁移：映射表 `mapping.yaml` 逐项写旧元数据的去处。图源标记只删映射表登记过的那一行；改作者区的机器区去掉标记、
  原文保留；其余机器区由当前 renderer 重投。映射表没登记的旧标记、旧机器区一律报错，不通用删除。
- 核对：每条旧事实在新输出里逐字找得到；找不到就报错。
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGN = REPO_ROOT / "test" / "fixtures" / "golden" / "AR90004-design"
BLUEPRINT_ID = "bp-AR90004"
COMPONENT = "wallet-main"
SR = "doc/features/AR90004/SR/design.md"


class MappingError(RuntimeError):
    """映射表与旧元数据或新输出对不上。"""


def mapping() -> dict:
    return yaml.safe_load((DESIGN / "mapping.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 蓝图

_PROVIDERS_FROM = REPO_ROOT / "test" / "fixtures" / "blueprint" / "wallet-balance-refresh" / "doc" / "features" \
    / "wallet-balance-refresh" / "blueprint" / "component-blueprint.yaml"
_LENS = ("module_boundaries", "capability_seams", "feature_flags", "data_producers_consumers", "lifecycle_triggers",
         "state_owners", "initialization", "publication_subscription", "ui_refresh", "process_recovery")


def _questioning(blueprint: dict) -> list[dict]:
    """独立设计质询的记录骨架：每个视图、关系、应用视角与需求术语各一问，证据指向系统设计原文。"""
    scopes = [("view", f"view:{v['view_id']}") for v in blueprint["design_views"] if v.get("applicability") == "applicable"]
    scopes += [("relation", f"relation:{r['relation_id']}") for r in blueprint["relations"]]
    scopes += [("app_lens", f"app_lens:{k}") for k in _LENS]
    scopes += [("terminology", "terminology:current_scope_items")]
    return [{"question_id": f"q-{ref.replace(':', '-').replace('_', '-')}", "scope_kind": kind, "scope_ref": ref,
             "question": f"Is {ref} closed?", "frontier_fingerprint": f"ff-{ref}", "owner": "architecture-owner",
             "disposition": "answered_with_evidence", "answer": "Evidence-backed.", "evidence_refs": [SR],
             "verification_refs": [f"verify:{ref}"], "provenance": blueprint["provenance"]} for kind, ref in scopes]


def _decision(spec: dict, source_ref: str, source_sha: str, provenance_at: str) -> dict:
    """1.x 的一条规约判断 → 知识应用决定。要求与依据照录；命中的理由取 1.x 记下的落点，不命中的取 1.x 的依据。"""
    applied = spec["applicable"]
    requirement = "；".join(spec.get("requirement") or [])
    landing = spec.get("contract") or spec.get("impact")
    knowledge = {"kind": "constraints", "form": "entries", "unit": spec["id"], "source_sha256": source_sha,
                 "outcome": "applied" if applied else "not_applicable",
                 **({"requirement": requirement} if applied else {}),
                 "target_refs": [spec["target_ref"]] if applied else []}
    return {"decision_id": f"knowledge-{spec['id'].lower()}", "kind": "knowledge_application",
            "status": "answered_with_evidence" if applied else "not_applicable", "owner": "design-author",
            "rationale": f"落点：{landing}" if applied else spec["reason"],
            "provenance": {"source_kind": "knowledge", "source_ref": source_ref, "observed_at": provenance_at,
                           "evidence_strength": "inferred", "extraction_method": "read_and_apply"},
            "verification_refs": [spec["target_ref"]] if applied else [SR],
            "knowledge": knowledge}


def assemble(items: list[dict], knowledge_root: Path) -> str:
    """组装 canonical 文本：模板 + 骨架 + 精确明细 + 知识应用决定 + 需求条目。返回 YAML 文本（来源指纹待重算）。"""
    blueprint = yaml.safe_load((DESIGN / "component-blueprint.yaml").read_text(encoding="utf-8"))
    plan = mapping()
    fixture = yaml.safe_load(_PROVIDERS_FROM.read_text(encoding="utf-8"))
    blueprint["providers"] = fixture["providers"]
    blueprint["app_lens"] = {**{k: {"disposition": "answered_with_evidence", "evidence_refs": [SR]} for k in _LENS},
                             **blueprint.get("app_lens", {})}
    blueprint["review_summary"]["questioning"]["items"] = _questioning(blueprint)
    # 精确明细：正文照录金样原机器区（映射表登记了出处）
    blueprint["story_details"] = [{"id": d["id"], "kind": d["kind"], "title": d["title"], "body": d["body"].strip() + "\n",
                                   "evidence_refs": d["evidence_refs"]} for d in plan["story_details"]]
    # 知识应用决定：1.x 的判断逐条转写，来源取工程里激活的金样知识快照
    use = yaml.safe_load((REPO_ROOT / "test" / "fixtures" / "golden" / "AR90004" / "spec" / "knowledge-use.yaml")
                         .read_text(encoding="utf-8"))
    targets = plan["knowledge_targets"]
    decisions = []
    for spec in use["constraints"]:
        source = next(p for p in sorted((knowledge_root / "constraints").glob("*.md"))
                      if re.search(rf"^\|\s*{re.escape(spec['id'])}\s*\|", p.read_text(encoding="utf-8"), re.M))
        ref = f"doc/extensions/knowledge/constraints/{source.name}"
        sha = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
        decisions.append(_decision({**spec, "target_ref": targets.get(spec["id"])}, ref, sha, "2026-08-30T10:00:00+08:00"))
    blueprint["decisions_and_gaps"]["decisions"] = decisions + blueprint["decisions_and_gaps"]["decisions"]
    blueprint["discovery"]["inputs"]["current_scope_items"] = items
    blueprint["discovery"]["requirement_traceability"] = [
        {"item_id": i["item_id"], "blueprint_refs": ["view:logical/node:emergency-loss"]} for i in items]
    return yaml.safe_dump(blueprint, allow_unicode=True, sort_keys=False, width=1000)


REFINGERPRINT = """
import * as fs from 'node:fs';
import { pathToFileURL } from 'node:url';
const [root, access, file] = process.argv.slice(1);
const { loadNative } = await import(pathToFileURL(access).href);
const native = loadNative(root);
const YAML = native.require('yaml');
const text = fs.readFileSync(file, 'utf8');
const bp = YAML.parse(text);
const discovery = native.module('scripts/utils/blueprint-discovery.ts');
const traceability = native.module('scripts/utils/blueprint-requirement-traceability.ts');
const next = discovery.fingerprintDiscoverySources(bp.discovery.facts, traceability.currentScopeItems(bp));
fs.writeFileSync(file, text.split(bp.source_fingerprint).join(next));
"""

CHECK = """
import { pathToFileURL } from 'node:url';
const [root, access, blueprint] = process.argv.slice(1);
const fa = await import(pathToFileURL(access).href);
const read = fa.readBlueprint(root, blueprint, 'delivery');
process.stdout.write(JSON.stringify({ status: read.status, admitted: read.admitted, projection: read.projection?.status,
  issues: (read.issues ?? []).filter(i => (i.severity ?? 'BLOCKER') !== 'WARN').map(i => `${i.id ?? i.code}：${i.message}`).slice(0, 20) }));
"""


def install(root: Path, items: list[dict], access: Path, knowledge_root: Path) -> dict:
    """写入 AR90004 的蓝图：组装、按原生算法重算来源指纹、生成评审投影，返回原生交付读取的结论
    （status / admitted / projection / issues）。没准入不在这里抛：之后的检查照实报出原生问题。"""
    import design_fixture  # noqa: PLC0415 —— 与夹具共用投影生成
    target = root / "doc" / "features" / BLUEPRINT_ID / "blueprint" / "component-blueprint.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(assemble(items, knowledge_root).encode("utf-8"))
    for script, args in ((REFINGERPRINT, [str(root), str(access), str(target)]),):
        proc = subprocess.run(["node", "--input-type=module", "-e", script, *args],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        if proc.returncode != 0:
            raise RuntimeError(f"来源指纹重算失败：{proc.stderr[-600:]}")
    design_fixture.render_projection(root, BLUEPRINT_ID, access)
    proc = subprocess.run(["node", "--input-type=module", "-e", CHECK, str(root), str(access), BLUEPRINT_ID],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    if proc.returncode != 0 or "{" not in proc.stdout:
        raise RuntimeError(f"蓝图读取失败：{proc.stderr[-600:]}")
    return json.loads(proc.stdout[proc.stdout.index("{"):])


# ---------------------------------------------------------------------------
# 迁移正本的旧元数据

MARK = re.compile(r"^%%\s*图源\s+(.+?)\s*$")
ZONE_BEGIN = re.compile(r"^<!-- story-build:begin (.+?) · ")
IMAGE = re.compile(r"(!\[[^\]]*\]\()([^)\s]+)(\))")
GOLDEN_ROOT = REPO_ROOT / "test" / "golden"
INPUT_ROOT = REPO_ROOT / "test" / "fixtures" / "golden" / "AR90004"


def _image_links(plan: dict) -> dict[str, str]:
    """图片链接的迁移：正本的归档副本与登记的原件抽图须逐字节相同，不同就是映射错了。"""
    links = {}
    for ref in plan.get("image_refs", []):
        old, new = GOLDEN_ROOT / ref["from"], (INPUT_ROOT / "AR" / ref["to"]).resolve()
        if not old.is_file() or not new.is_file() or old.read_bytes() != new.read_bytes():
            raise MappingError(f"图片「{ref['from']}」与登记的「{ref['to']}」不是同一张图")
        links[ref["from"]] = ref["to"]
    return links


def migrate(story: str) -> str:
    """按映射表迁移：删登记过的那几行图源标记，指定的机器区改作者区（去标记、留原文），图片链接改指登记的原件抽图；
    没登记的旧标记、旧机器区与图片链接报错。"""
    plan = mapping()
    drop = {m["mark"] for m in plan["diagram_marks"] if m["action"] == "drop_mark"}
    keep = {m["mark"] for m in plan["diagram_marks"] if m["action"] == "keep"}
    to_author = {z["zone"] for z in plan["zones"] if z["action"] == "to_author"}
    reproject = {z["zone"] for z in plan["zones"] if z["action"] == "reproject"}
    links = _image_links(plan)

    def relink(m: re.Match) -> str:
        if m.group(2) not in links:
            raise MappingError(f"图片链接「{m.group(2)}」映射表没登记")
        return m.group(1) + links[m.group(2)] + m.group(3)

    out: list[str] = []
    in_author_zone = False
    for line in story.split("\n"):
        line = IMAGE.sub(relink, line)
        mark = MARK.match(line.strip())
        if mark:
            if mark.group(1) in drop:
                continue
            if mark.group(1) not in keep:
                raise MappingError(f"图源标记「{mark.group(1)}」映射表没登记")
        begin = ZONE_BEGIN.match(line)
        if begin:
            zone = begin.group(1)
            if zone in to_author:
                in_author_zone = True
                continue
            if zone not in reproject:
                raise MappingError(f"机器区「{zone}」映射表没登记")
        if in_author_zone and line.startswith("<!-- story-build:end -->"):
            in_author_zone = False
            continue
        out.append(line)
    return "\n".join(out)


def verify(story: str) -> list[str]:
    """机器区都已按蓝图重投、每条旧事实在新输出里逐字找得到；返回没做到的那些（空就是全在）。

    还挂着 1.x 来源的机器区（起始标记写「由spec」）说明没重投，那一区里的旧事实不算找到。"""
    plan = mapping()
    stale = [line.split(" · ")[0].removeprefix("<!-- story-build:begin ") for line in story.split("\n")
             if ZONE_BEGIN.match(line) and " · 由spec" in line]
    missing = [f"{zone}：机器区没按蓝图重投，还是 1.x 的 spec 投影" for zone in stale]
    for zone in plan["zones"]:
        if zone["zone"] in stale:
            continue
        for fact in zone.get("facts", []) + zone.get("pending_facts", []):
            if fact not in story:
                missing.append(f"{zone['zone']}：{fact}")
    return missing
