"""金样 AR90004 的 2.0 装配：用同一真实设计事实建立原生蓝图，迁移正本的旧元数据，逐项核映射表。

只在测试隔离副本里做，不改正本 `test/golden/story-金样-AR90004.md` 与输入夹具，不维护第二份可编辑金样
（2.0.0 步骤 2 实施评审 §3、步骤 4 阶段评审 §4）。

- 蓝图：`test/fixtures/golden/AR90004-design/component-blueprint.yaml` 写着 AR90004 自己的设计事实（文字取自
  SR、spec 与 AR 原文）与知识应用决定；这里补上与设计内容无关的骨架（质询记录、供给方、应用视角）、精确明细（原文照录）、
  知识来源指纹（按工程里激活的知识重算）与本次冻结输入推出的需求条目，按原生算法重算来源指纹并生成投影。
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
    """独立设计质询的记录骨架：每个视图、关系、运行数据流、应用视角与需求术语各一问，证据指向系统设计原文。"""
    scopes = [("view", f"view:{v['view_id']}") for v in blueprint["design_views"] if v.get("applicability") == "applicable"]
    scopes += [("relation", f"relation:{r['relation_id']}") for r in blueprint["relations"]]
    scopes += [("flow", f"flow:{fl['flow_id']}") for v in blueprint["design_views"]
               for fl in v.get("runtime_data_flows") or []]
    scopes += [("app_lens", f"app_lens:{k}") for k in _LENS]
    scopes += [("terminology", "terminology:current_scope_items")]
    return [{"question_id": f"q-{ref.replace(':', '-').replace('_', '-')}", "scope_kind": kind, "scope_ref": ref,
             "question": f"Is {ref} closed?", "frontier_fingerprint": f"ff-{ref}", "owner": "architecture-owner",
             "disposition": "answered_with_evidence", "answer": "Evidence-backed.", "evidence_refs": [SR],
             "verification_refs": [f"verify:{ref}"], "provenance": blueprint["provenance"]} for kind, ref in scopes]


#: 蓝图工作区里接口转写与映射的位置（工程根起）
CONTRACTS_DIR = f"doc/features/{BLUEPRINT_ID}/blueprint/contracts"
#: 契约 → (operation, 请求 DTO, 响应 DTO, 映射标识前缀)
CONTRACTS = {
    "query-loss-eligibility-v1": ("queryLossEligibility", "QueryLossEligibilityRequestV1", "QueryLossEligibilityResponseV1", "eligibility-"),
    "create-or-reuse-loss-application-v1": ("createOrReuseLossApplication", "CreateOrReuseLossApplicationRequestV1",
                                            "CreateOrReuseLossApplicationResponseV1", "submit-"),
    "query-freeze-result-v1": ("queryFreezeResult", "QueryFreezeResultRequestV1", "QueryFreezeResultResponseV1", "result-"),
}


def _contracts() -> list[dict]:
    """蓝图契约按转写与映射逐段组装：各段内容与 source_ref 指向的段落逐项一致（原生逐段比对）。"""
    se = yaml.safe_load((DESIGN / "contracts" / "se-interfaces.yaml").read_text(encoding="utf-8"))
    maps = yaml.safe_load((DESIGN / "contracts" / "mappings.yaml").read_text(encoding="utf-8"))["mappings"]
    se_ref = f"{CONTRACTS_DIR}/se-interfaces.yaml"
    map_ref = f"{CONTRACTS_DIR}/mappings.yaml"
    prov = {"source_kind": "interface", "source_ref": se_ref, "observed_at": "2026-08-30T10:00:00+08:00",
            "evidence_strength": "observed", "extraction_method": "transcribed-from-se-design"}
    mprov = {**prov, "source_ref": map_ref, "extraction_method": "component-design-decision"}
    out = []
    for cid, (op, req, resp, prefix) in CONTRACTS.items():
        def dto(name: str) -> dict:
            fields = se["dtos"][name]["fields"]
            return {"dto_id": name, "source_ref": f"{se_ref}#/dtos/{name}", "verification_refs": [f"verify:{cid}-{name}"],
                    "fields": [{**f, "source_ref": f"{se_ref}#/dtos/{name}/fields/{i}", "provenance": prov}
                               for i, f in enumerate(fields)]}

        def part(kind: str) -> dict:
            return {**se[kind][op], "source_ref": f"{se_ref}#/{kind}/{op}", "verification_refs": [f"verify:{cid}-{kind}"]}

        out.append({
            "contract_id": cid,
            "operation": {**{k: v for k, v in se["operations"][op].items() if k != "provenance"},
                          "source_ref": f"{se_ref}#/operations/{op}", "verification_refs": [f"verify:{cid}-operation"]},
            "request_dto": dto(req), "response_dto": dto(resp),
            "mappings": [{**m, "source_ref": f"{map_ref}#/mappings/{mid}", "provenance": mprov,
                          "verification_refs": [f"verify:mapping-{mid}"]} for mid, m in maps.items() if mid.startswith(prefix)],
            "errors": part("errors"), "idempotency": part("idempotency"), "nfr": part("nfr"),
            "owner": "wallet-team", "needed_by": "cu-emergency-loss", "provenance": prov})
    return out


def place_contract_sources(root: Path, frozen_sr: str) -> None:
    """接口转写与映射放进蓝图工作区；转写里的原文出处换成本次冻结的 SR 副本。"""
    target = root / CONTRACTS_DIR
    target.mkdir(parents=True, exist_ok=True)
    text = (DESIGN / "contracts" / "se-interfaces.yaml").read_text(encoding="utf-8").replace("{frozen_sr}", frozen_sr)
    (target / "se-interfaces.yaml").write_bytes(text.encode("utf-8"))
    (target / "mappings.yaml").write_bytes((DESIGN / "contracts" / "mappings.yaml").read_bytes())


def assemble(items: list[dict], knowledge_root: Path) -> str:
    """组装 canonical 文本：模板 + 骨架 + 精确明细 + 知识应用决定 + 需求条目 + 契约。返回 YAML 文本（来源指纹待重算）。"""
    blueprint = yaml.safe_load((DESIGN / "component-blueprint.yaml").read_text(encoding="utf-8"))
    blueprint["contracts"] = _contracts()
    plan = mapping()
    fixture = yaml.safe_load(_PROVIDERS_FROM.read_text(encoding="utf-8"))
    blueprint["providers"] = fixture["providers"]
    blueprint["app_lens"] = {**{k: {"disposition": "answered_with_evidence", "evidence_refs": [SR]} for k in _LENS},
                             **blueprint.get("app_lens", {})}
    blueprint["review_summary"]["questioning"]["items"] = _questioning(blueprint)
    # 精确明细：正文照录金样原机器区（映射表登记了出处）
    blueprint["story_details"] = [{"id": d["id"], "kind": d["kind"], "title": d["title"], "body": d["body"].strip() + "\n",
                                   "evidence_refs": d["evidence_refs"]} for d in plan["story_details"]]
    # 知识应用决定写在夹具里；来源指纹按工程里激活的那份知识重算
    for decision in blueprint["decisions_and_gaps"]["decisions"]:
        if decision.get("kind") == "knowledge_application":
            source = knowledge_root / decision["provenance"]["source_ref"].removeprefix("doc/extensions/knowledge/")
            decision["knowledge"]["source_sha256"] = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
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
    flow = json.loads((root / "doc" / "features" / "AR90004" / "AR" / "story-src" / "story-flow.json").read_text(encoding="utf-8"))
    place_contract_sources(root, f"{flow['input']['snapshot_ref'].rsplit('/', 1)[0]}/files/SR/design.md")
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
        for fact in zone.get("facts", []):
            if fact not in story:
                missing.append(f"{zone['zone']}：{fact}")
    return missing
