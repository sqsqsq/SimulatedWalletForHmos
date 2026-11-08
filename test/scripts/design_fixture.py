"""范围已定、蓝图准入的需求工作区怎样准备——测试夹具与失效形态运行器共用这一份。

- **接 Framework**：临时工程接 demo 的 Framework（整目录链接，或在已有替身旁逐层补缺）；
- **准入蓝图**：取 `test/fixtures/blueprint/wallet-balance-refresh` 那份真实准入的 canonical，放到需求目录的 `blueprint/`
  （与需求同根，蓝图标识就是需求标识），按需插入知识应用决定、精确明细与术语事实；评审投影在真实流程里
  由设计职责按原生 renderer 生成，这里代它生成同一份字节——Extension 只读、不写它；
- **设计采用本需求的来源**：蓝图的需求条目换成按材料索引补齐来源的原生条目（`import_sources.py --scope` 同一算法），
  来源指纹按原生算法重算——真实流程里这是设计职责在 component-design 里做的；
- **走关卡**：用真实流程命令走材料关卡与范围关卡，人签与真实运行留下的记录同形。
"""
from __future__ import annotations

import hashlib
import json
import re
import os
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[2]


def framework_under_test() -> Path:
    """单测接的被测 Framework：`test/config/framework-under-test.json` 登记的固定发布树，应用同一文件登记的本地宿主补丁；
    harness 依赖借 demo 已装的 `node_modules`（依赖声明与发布树一致才借，不一致就停，不联网装）。

    按固定输入与补丁摘要在系统临时目录建一次，造好再改名，各进程与之后各轮共用；demo 不动。
    """
    import tempfile  # noqa: PLC0415
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import run_multi_case as rmc  # noqa: PLC0415
    cfg = rmc.load_framework_under_test()
    key = hashlib.sha256(f"{cfg['release_commit']}:{cfg['tree_oid']}:{cfg['patch_sha256']}".encode()).hexdigest()[:20]
    base = Path(tempfile.gettempdir()) / "story-framework-under-test"
    final = base / key
    if (final / "framework" / "RELEASE-MANIFEST.json").is_file():
        return final / "framework"
    demo_harness = REPO_ROOT / "demo" / "framework" / "harness"
    pkg = rmc._git_out("cat-file", "blob", f"{cfg['release_commit']}:{cfg['framework_path']}/harness/package.json")
    if rmc._harness_dependencies(pkg.stdout) != rmc._harness_dependencies((demo_harness / "package.json").read_bytes()):
        raise RuntimeError("被测 Framework 的 harness 依赖声明与 demo 已装的不同：先按维护环境准备装好它的依赖")
    building = base / f"{key}.building-{os.getpid()}"
    shutil.rmtree(building, ignore_errors=True)
    framework = building / "framework"
    framework.mkdir(parents=True)
    rmc._write_framework_release(framework, cfg)
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(building.parent)}
    applied = rmc._git_out("apply", "--directory=framework", str(cfg["patch_path"]), cwd=building, env=env)
    if applied.returncode != 0:
        raise RuntimeError(f"本地宿主补丁不适用于被测 Framework：{applied.stderr.decode('utf-8', 'replace')[:600]}")
    _link_dir(demo_harness / "node_modules", framework / "harness" / "node_modules")
    try:
        building.rename(final)
    except OSError:
        if not (final / "framework" / "RELEASE-MANIFEST.json").is_file():
            raise
        shutil.rmtree(building, ignore_errors=True)
    return final / "framework"


def link_framework(root: Path) -> Path:
    """让临时工程根接入被测 Framework（`framework_under_test`）：复制 demo 的 `framework.config.json`（物化哪些宿主由它定），
    `framework/` 整个目录接一条指向它的 junction（Windows）或符号链接。安装与宿主入口物化只读它、
    写在工程根；链接在临时目录清理时被删，demo 不动。已存在的都不动。"""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    config = root / "framework.config.json"
    if not config.exists():
        shutil.copy2(REPO_ROOT / "demo" / "framework.config.json", config)
    target = root / "framework"
    if not target.exists():
        source = framework_under_test()
        if sys.platform == "win32":
            import _winapi
            _winapi.CreateJunction(str(source), str(target))
        else:
            os.symlink(source, target, target_is_directory=True)
    return target


def _link_dir(source: Path, target: Path) -> None:
    if sys.platform == "win32":
        import _winapi
        _winapi.CreateJunction(str(source), str(target))
    else:
        os.symlink(source, target, target_is_directory=True)


def overlay_framework(root: Path) -> None:
    """`framework/` 已经在（只接了 yaml 包、或放了替身）的临时工程补接被测 Framework 缺的部分：
    `framework/`、`harness/`、`node_modules/` 三层逐项只补缺的——目录接链接、文件复制，已有的一律不动。"""
    def fill(source: Path, target: Path, depth: int) -> None:
        target.mkdir(parents=True, exist_ok=True)
        for item in source.iterdir():
            dest = target / item.name
            if dest.exists() or dest.is_symlink():
                if depth and item.is_dir() and dest.is_dir() and not os.path.islink(dest) and not _is_junction(dest):
                    fill(item, dest, depth - 1)
            elif item.is_dir():
                _link_dir(item, dest)
            else:
                shutil.copy2(item, dest)
    fill(framework_under_test(), Path(root) / "framework", 2)


def _is_junction(path: Path) -> bool:
    return bool(getattr(os.path, "isjunction", lambda p: False)(path))


def project_root_of(feature_root: Path) -> Path:
    """需求目录所在的工程根：有 framework.config.json 的那一层；没有就按默认需求目录 doc/features 往上两层。"""
    for parent in feature_root.resolve().parents:
        if (parent / "framework.config.json").is_file():
            return parent
    return feature_root.resolve().parents[2]


def ensure_framework(root: Path) -> None:
    """交给设计要读 Framework 原生对象：工程没接入的，照 demo 的配置接上它的 Framework。"""
    if not (root / "framework.config.json").is_file():
        shutil.copy2(REPO_ROOT / "demo" / "framework.config.json", root / "framework.config.json")
    if not (root / "framework").exists():
        link_framework(root)
    elif not (root / "framework" / "harness" / "package.json").is_file():
        overlay_framework(root)


BLUEPRINT_FIXTURE = REPO_ROOT / "test" / "fixtures" / "blueprint" / "wallet-balance-refresh"
#: 夹具蓝图设计对象的 provenance 引的那份 demo 源码
BLUEPRINT_CODE = "02-Feature/WalletMain/src/main/ets/data/repository/HomeRepository.ets"
COMPONENT = "wallet-main"

RENDER = """
import { pathToFileURL } from 'node:url';
const [root, access, blueprint] = process.argv.slice(1);
const { loadNative } = await import(pathToFileURL(access).href);
const native = loadNative(root);
const r = native.module('scripts/utils/blueprint-review-materialization.ts').materializeBlueprintReview(native.root, blueprint);
if (r.status === 'failed') { process.stderr.write(`评审投影原生物化失败：${r.reason ?? ''}`); process.exit(1); }
"""


def features_dir(root: Path) -> str:
    config = json.loads((root / "framework.config.json").read_text(encoding="utf-8"))
    return (config.get("paths") or {}).get("features_dir") or "doc/features"


def render_projection(root: Path, blueprint: str, access: Path) -> None:
    proc = subprocess.run(["node", "--input-type=module", "-e", RENDER, str(root), str(access), blueprint],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"评审投影生成失败：{proc.stderr[-600:]}")


#: 蓝图里真实存在、夹具的知识落点用的稳定地址
TARGET = "view:logical/node:wallet-balance"


def rule_judgement(unit: str, outcome: str, rationale: str, target_refs: list[str] | None = None) -> dict:
    """一条规约条目的适用性判断：`outcome` 取 applied / not_applicable / pending；适用的落点默认是夹具的设计对象，
    待定的 `target_refs` 指原生决定或缺口。放进蓝图时按条目所在的激活规约文件归成那一域的事实（`knowledge_facts`）。"""
    return {"unit": unit, "outcome": outcome, "rationale": rationale,
            "target_refs": list(target_refs) if target_refs is not None else ([TARGET] if outcome == "applied" else [])}


ACTIVE_CONSTRAINTS = """
import { pathToFileURL } from 'node:url';
const [root, module, obligations] = process.argv.slice(1);
const { activeKnowledge } = await import(pathToFileURL(module).href);
const { verifyChoices } = await import(pathToFileURL(obligations).href);
const k = activeKnowledge(root);
// 作者任务给作者的同一份：每条规约允许的 verify 与是不是评审动作
const entry = (file, id) => k.entries.find(e => e.file === file && e.id === id);
process.stdout.write(JSON.stringify([...k.constraints.map(c => ({ kind: 'constraints', file: c.file, units: c.units,
    verify: Object.fromEntries(c.units.map(u => [u, verifyChoices(entry(c.file, u)).allowed[0]])),
    review: c.units.filter(u => entry(c.file, u)?.reviewAction) })),
  ...k.patterns.map(p => ({ kind: 'patterns', file: p.file, units: [p.units[0]], roles: p.roles ?? [] }))]));
"""


def active_constraints(root: Path, access: Path) -> list[dict]:
    """工程激活的规约与模式（扩展根相对路径、类别、单元）；没有激活清单就没有。"""
    if not (root / "doc" / "extensions" / "manifest.yaml").is_file():
        return []
    proc = subprocess.run(["node", "--input-type=module", "-e", ACTIVE_CONSTRAINTS, str(root),
                           str(Path(access).parent / "knowledge.mjs"), str(Path(access).parent / "obligations.mjs")],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"激活知识读不出来：{proc.stderr[-600:]}")
    return json.loads(proc.stdout)


def pattern_judgement(file: str, outcome: str, rationale: str, roles: list[dict] | None = None) -> dict:
    """一个出现了候选信号的模式的判断：`file` 是扩展根相对路径，`outcome` 取 selected / rejected；
    选中时 `roles: [{role, target_ref}]` 写到承担角色的设计对象上（`pattern_roles`）。"""
    return {"file": file, "outcome": outcome, "rationale": rationale, "roles": list(roles or [])}


KNOWLEDGE_CONTEXT = """
import { pathToFileURL } from 'node:url';
const [root, module] = process.argv.slice(1);
const { knowledgeContext } = await import(pathToFileURL(module).href);
process.stdout.write(JSON.stringify(knowledgeContext(root)));
"""


def knowledge_context(root: Path, access: Path) -> dict:
    """这一轮的知识输入身份——由产品的 `knowledgeContext` 生成，设计作者原样写进蓝图。"""
    proc = subprocess.run(["node", "--input-type=module", "-e", KNOWLEDGE_CONTEXT, str(root),
                           str(Path(access).parent / "knowledge-application.mjs")],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"知识输入身份生成失败：{proc.stderr[-600:]}")
    return json.loads(proc.stdout)


def knowledge_facts(judgements: list[dict] | None, active: list[dict], exact: bool) -> tuple[str, dict[str, dict]]:
    """设计对激活知识的适用性事实（缩进对齐 discovery.facts）与要写到设计对象上的东西：`{地址: {"must": [...], "pattern_roles": [...]}}`。

    规约一域一条事实：给了条目判断的域逐条写（`exact` 为假时其余条目补「不涉及」），没给的域写一条域级不涉及
    （`exact` 时不写，反例用：可以漏判）；适用的条目（评审动作除外）在每个落点写出自它的 must，verify 取这条允许的第一种；
    模式只写给了判断的那些——没有候选信号的模式不判。
    """
    given = list(judgements or [])
    facts, attach = [], {}
    put = lambda address, key, value: attach.setdefault(address, {}).setdefault(key, []).append(value)  # noqa: E731
    for c in (x for x in active if x["kind"] == "constraints"):
        mine = [j for j in given if "unit" in j and j["unit"] in c["units"]]
        if mine:
            items = mine + ([] if exact else [rule_judgement(u, "not_applicable", "夹具：本需求不涉及这条规约")
                                              for u in c["units"] if u not in {j["unit"] for j in mine}])
            value = {"knowledge_kind": "constraints", "items": items}
        elif exact:
            continue
        else:
            value = {"knowledge_kind": "constraints", "outcome": "not_applicable", "rationale": "夹具：本需求不涉及这一域的规约"}
        facts.append((c["file"], value))
        for j in mine:
            if j["outcome"] != "applied" or j["unit"] in c.get("review", []):
                continue
            for t in (x for x in j["target_refs"] if not x.startswith(("decision:", "gap:"))):
                put(t, "must", {"text": f"夹具：{j['rationale']}", "source_ref": f"doc/extensions/{c['file']}#{j['unit']}",
                                "verify": c["verify"][j["unit"]]})
    known = {c["file"] for c in active if c["kind"] == "patterns"}
    for j in (x for x in given if "file" in x):
        if j["file"] not in known:
            raise AssertionError(f"夹具要判的模式 {j['file']} 不在工程激活的知识里")
        facts.append((j["file"], {"knowledge_kind": "patterns", "outcome": j["outcome"], "rationale": j["rationale"]}))
        for r in j["roles"]:
            put(r["target_ref"], "pattern_roles", {"pattern_ref": f"doc/extensions/{j['file']}", "role": r["role"]})
    unknown = [j["unit"] for j in given if "unit" in j and not any(j["unit"] in c["units"] for c in active if c["kind"] == "constraints")]
    if unknown:
        raise AssertionError(f"夹具要判的 {'、'.join(unknown)} 不在工程激活的规约里")
    text = "".join(
        f"    - fact_id: knowledge-{Path(file).stem}\n"
        f"      subject: {json.dumps('knowledge:' + Path(file).stem, ensure_ascii=False)}\n"
        f"      value: {json.dumps(value, ensure_ascii=False)}\n"
        "      provenance: " + json.dumps({"source_kind": "knowledge", "source_ref": f"doc/extensions/{file}",
                                          "observed_at": "2026-10-30T00:00:00Z", "evidence_strength": "inferred",
                                          "extraction_method": "read_and_apply"}, ensure_ascii=False) + "\n"
        for file, value in facts)
    return text, attach


def with_entities(text: str, attach: dict[str, dict]) -> str:
    """把义务与模式角色写到承担它的设计对象上（`must`、`pattern_roles`），地址按原生稳定地址的写法认。"""
    import yaml  # noqa: PLC0415
    doc = yaml.safe_load(text)

    def find(address: str) -> dict:
        kind, _, rest = address.partition(":")
        if kind == "view":
            view_id, _, tail = rest.partition("/")
            view = next(v for v in doc["design_views"] if v["view_id"] == view_id)
            if not tail:
                return view
            sub, _, sid = tail.partition(":")
            key, id_key = ("nodes", "node_id") if sub == "node" else ("runtime_data_flows", "flow_id")
            return next(x for x in view[key] if x[id_key] == sid)
        table = {"contract": ("contracts", "contract_id"), "relation": ("relations", "relation_id")}[kind]
        return next(x for x in doc[table[0]] if x[table[1]] == rest)

    for address, fields in attach.items():
        for key, list_ in fields.items():
            find(address).setdefault(key, []).extend(list_)
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=1000)


def story_detail(detail_id: str, kind: str, title: str, body: str) -> str:
    """一条精确明细（`story_details`）的 canonical 文本。"""
    lines = "".join(f"      {line}\n" for line in body.strip().split("\n"))
    return (f"  - id: {detail_id}\n"
            f"    kind: {kind}\n"
            f"    title: {json.dumps(title, ensure_ascii=False)}\n"
            "    body: |\n" + lines +
            "    evidence_refs:\n"
            "      - view:logical/node:wallet-balance\n")


def blueprint_of(root: Path, feature: str) -> str:
    """需求的蓝图标识：蓝图与需求同根，标识就是需求标识。"""
    return feature


def change_blueprint(root: Path, feature: str, access: Path, old: str, new: str) -> None:
    """设计职责修订了需求关联的蓝图：canonical 里换一段原文，再按原生 renderer 重新生成评审投影。"""
    blueprint = blueprint_of(root, feature)
    canonical = root / features_dir(root) / blueprint / "blueprint" / "component-blueprint.yaml"
    text = canonical.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise AssertionError(f"蓝图里「{old}」出现 {text.count(old)} 次，夹具变了")
    canonical.write_bytes(text.replace(old, new).encode("utf-8"))
    render_projection(root, blueprint, access)


def term_fact(term: str, module: str = "WalletMain") -> str:
    """一条经人确认的术语事实（`subject: term:<术语>`）的 canonical 文本：模块取 demo 模块目录里的获准模块。"""
    fact_id = "term-" + hashlib.sha256(term.encode("utf-8")).hexdigest()[:8]
    return (f"    - fact_id: {fact_id}\n"
            f"      subject: {json.dumps('term:' + term, ensure_ascii=False)}\n"
            f"      value: {{canonical_module: {module}, confidence: medium, easily_confused_with: []}}\n"
            "      provenance:\n"
            "        source_kind: catalog\n"
            "        source_ref: doc/module-catalog.yaml\n"
            "        observed_at: 2026-09-01T00:00:00Z\n"
            "        evidence_strength: observed\n"
            "        extraction_method: user_confirmed\n")


REFINGERPRINT = """
import * as fs from 'node:fs';
import { pathToFileURL } from 'node:url';
const [root, access, blueprint, file] = process.argv.slice(1);
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


def handed_items(root: Path, feature: str, access: Path) -> list[dict] | None:
    """需求的材料版本推出的原生需求条目：只有真实的需求——产品需求的阅读正文（没有产品需求取第一份正文）是
    `request-main`；用那份扩展的 `materials/scope.py` 按材料索引补齐来源，去掉 authority
    （原生 `materializedScopeItems` 的形状）。其余正文是支撑材料，见 `support_refs`。需求还没有材料索引时返回 None。"""
    feature_root = root / features_dir(root) / feature
    index = feature_root / "AR" / "story-src" / "materials.json"
    if not index.is_file():
        return None
    core = Path(access).resolve().parents[2] / "skills" / "story" / "scripts" / "core"
    if str(core) not in sys.path:
        sys.path.insert(0, str(core))
    from materials import scope  # noqa: PLC0415
    manifest = json.loads(index.read_text(encoding="utf-8"))
    authority = {"owner": "需求负责人", "formality": "formal_requirement"}
    wanted = [{"item_id": "request-main", "kind": "requirement", "source": main_source(manifest), "authority": authority}]
    filled = scope.fill(feature_root, root, wanted)
    return [{k: v for k, v in entry.items() if k != "authority"} for entry, _ in filled]


def support_refs(root: Path, feature: str) -> list[str]:
    """需求条目之外的支撑正文（工程相对路径）：设计在用到它的事实的 provenance 里引用，不为它造需求条目。"""
    feature_root = root / features_dir(root) / feature
    index = feature_root / "AR" / "story-src" / "materials.json"
    if not index.is_file():
        return []
    manifest = json.loads(index.read_text(encoding="utf-8"))
    main = main_source(manifest)
    base = feature_root.relative_to(root).as_posix()
    return [f"{base}/{p}" for m in manifest["materials"] if m["kind"] == "doc" and m.get("sha256") for p in m["paths"]
            if PurePosixPath(p).suffix.lower() in (".md", ".txt") and p != main]


def support_facts(refs: list[str]) -> str:
    """每份支撑正文一条 discovery 事实，provenance 引用它：设计依据由真实引用承载。"""
    return "".join(
        f"    - fact_id: fact-support-{i}\n      subject: 支撑材料 {i}\n      value: 设计按这份材料理解系统约束\n"
        f"      provenance:\n        source_kind: system_design\n        source_ref: {ref}\n"
        "        observed_at: 2026-10-30T10:00:00+08:00\n        evidence_strength: observed\n"
        "        extraction_method: read-source\n"
        for i, ref in enumerate(refs, 1))


def consume_items(text: str, items: list[dict]) -> str:
    """canonical 的需求条目与追溯换成给定条目：每条追溯到蓝图的余额刷新节点。"""
    head, rest = text.split("    current_scope_items:\n", 1)
    tail = rest[rest.index("\napp_lens:"):]
    trace = [{"item_id": i["item_id"], "blueprint_refs": ["view:logical/node:wallet-balance"]} for i in items]
    return (head + "    current_scope_items: " + json.dumps(items, ensure_ascii=False)
            + "\n  requirement_traceability: " + json.dumps(trace, ensure_ascii=False) + tail)


def install_blueprint(root: Path, feature: str, access: Path, *, projection: bool = True,
                      judgements: list[dict] | None = None, details: list[str] | None = None,
                      terms: list[str] | None = None, consume: bool = True, exact: bool = False,
                      items: list[dict] | None = None, support: list[str] | None = None) -> Path:
    """把需求的准入蓝图放到需求目录的 `blueprint/`（与需求同根，标识就是需求标识），返回 canonical 路径。

    `judgements` 是 `rule_judgement` / `pattern_judgement` 给出的适用性判断，按 `knowledge_facts` 写成蓝图事实，
    蓝图另记产品生成的知识输入身份；`exact` 为真时蓝图里就只有给的这几条（反例用：可以漏判，空列表就一条不判）；
    `details` 是 `story_detail` 生成的 canonical 片段，按原文插进去；
    `projection` 为假时不生成评审投影。`consume` 为真时蓝图的需求条目采用需求已导入的材料版本；
    `consume` 为假时保留夹具原来那份需求（另一个需求）的条目——反例用；`items` 直接给出要采用的条目。
    `support` 是事实 provenance 引用的支撑材料（工程相对路径）；不给且 `consume` 为真时取需求条目之外的全部正文。
    """
    ensure_framework(root)
    blueprint = blueprint_of(root, feature)
    source = BLUEPRINT_FIXTURE / "doc" / "features" / "wallet-balance-refresh" / "blueprint" / "component-blueprint.yaml"
    target = root / features_dir(root) / blueprint / "blueprint" / "component-blueprint.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    text = source.read_text(encoding="utf-8").replace("blueprint_id: wallet-balance-refresh\n", f"blueprint_id: {blueprint}\n", 1)
    active = active_constraints(root, access)
    knowledge, attach = knowledge_facts(judgements, active, exact)
    if active:
        text = text.replace("  inputs:\n", "  inputs:\n    knowledge_context: "
                            + json.dumps(knowledge_context(root, access), ensure_ascii=False) + "\n", 1)
    if details:
        text = text.rstrip("\n") + "\nstory_details:\n" + "".join(details)
    support = support if support is not None else support_refs(root, feature) if consume else []
    if terms or support or knowledge:
        text = text.replace("  facts:\n", "  facts:\n" + "".join(terms or []) + support_facts(support) + knowledge, 1)
    items = items if items is not None else handed_items(root, feature, access) if consume else None
    if items:
        text = consume_items(text, items)
    if attach:
        text = with_entities(text, attach)
    target.write_bytes(text.encode("utf-8"))
    if terms or items or support or knowledge:
        # 事实或需求条目变了，来源指纹按原生算法重算：它由 discovery 的事实与当前范围条目确定性得出
        proc = subprocess.run(["node", "--input-type=module", "-e", REFINGERPRINT, str(root), str(access), blueprint, str(target)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(f"来源指纹重算失败：{proc.stderr[-600:]}")
    shutil.copytree(BLUEPRINT_FIXTURE / "doc" / "requirements", root / "doc" / "requirements", dirs_exist_ok=True)
    # 设计对象的 provenance 引的工程源码：消费工程里本来就有，从 demo 取同一份
    code = root / BLUEPRINT_CODE
    code.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / "demo" / BLUEPRINT_CODE, code)
    catalog = root / "doc" / "module-catalog.yaml"
    if not catalog.exists():
        shutil.copy2(REPO_ROOT / "demo" / "doc" / "module-catalog.yaml", catalog)
    if projection:
        render_projection(root, blueprint, access)
    return target


def write_gaps(src: Path, missing: tuple[str, ...] = (), why: str = "夹具：材料齐了") -> None:
    """材料关卡的缺口文件：`missing` 为空时推荐「现有材料就是全部」。"""
    src.mkdir(parents=True, exist_ok=True)
    (src / ".material-gaps.json").write_text(
        json.dumps({"missing": list(missing), "why": why}, ensure_ascii=False), encoding="utf-8")


def answer(flow: Callable[..., dict], gate: str, reply: str, *extra: str) -> dict:
    """按当前问法答一关：先 `status` 取 `ask_id`，再记人的原话。`flow` 返回解析后的 JSON。"""
    ask = flow("status")["ask"]
    return flow("decide", "--gate", gate, "--ask", ask["ask_id"], "--reply", reply, *extra)


def main_source(manifest: dict) -> str:
    """需求条目指向的正文：产品需求来源的阅读稿，没有产品需求时取第一份正文。"""
    requirement = {v.get("readable", {}).get("path") for s in manifest.get("sources", [])
                   if s.get("class") == "RR" for v in s.get("versions", [])}
    docs = [p for m in manifest["materials"] if m["kind"] == "doc" and m.get("sha256") for p in m["paths"]]
    return next((p for p in docs if p in requirement), docs[0])


def hand_to_design(src: Path, access: Path) -> None:
    """范围定了：设计由原生 component-design 完成——放一份与需求同根、需求条目采用本需求材料版本、已准入的蓝图
    （带一条知识应用决定），成文按它写。`access` 是用来调原生的 framework-access。"""
    feature_root = src.parents[1]
    root = project_root_of(feature_root)
    ensure_framework(root)
    if not (feature_root / "blueprint" / "component-blueprint.yaml").is_file():
        install_blueprint(root, feature_root.name, access)


def walk_to_design(flow: Callable[..., dict], src: Path, access: Path,
                   scope_text: str = "本 AR 承载自动充值签约与管理", hand: bool = True) -> None:
    """用真实流程命令走完 S1–S3 并交给设计：材料关卡、需求分析、范围关卡，再放好同根的准入蓝图。

    走完即「可以成文」。材料是夹具里已导入的 `sources/` 材料版本。`hand` 为假时只推进关卡、不放蓝图：
    调用方随后自己装唯一一份目标蓝图（`prepare_designed`），不先装一份默认蓝图再覆盖。"""
    src.mkdir(parents=True, exist_ok=True)
    flow("init")
    flow("round")
    write_gaps(src)
    answer(flow, "material_scope", "夹具：现有材料就是全部", "--chosen", "confirm_scope")
    (src / ".positioning.json").write_text(json.dumps(
        {"scope_text": scope_text, "sr_related_ars": []}, ensure_ascii=False), encoding="utf-8")
    (src / ".scope-options.json").write_text(json.dumps(
        [{"key": "carry_all", "label": "按当前范围整体承载"}], ensure_ascii=False), encoding="utf-8")
    flow("round")
    answer(flow, "scope_decision", "夹具：整体承载", "--chosen", "carry_all")
    if hand:
        hand_to_design(src, access)


def prepare_designed(root: Path, feature: str, *, flow_script: Path, build_script: Path, access: Path,
                     judgements: list[dict] | None = None, design: dict | None = None,
                     project_must_pass: bool = True) -> None:
    """就地把一份需求工作区准备成「范围已定、蓝图已准入」：接 Framework、用真实流程命令走完关卡、放准入蓝图，
    附录机器区按蓝图重投。

    `flow_script` / `build_script` / `access` 是本次要用的那份扩展里的 story_flow.py、story-build.mjs 与
    framework-access.mjs；已有流程契约的工作区不重走流程。`project_must_pass` 为假时附录重投不过不抛错——
    被测的就是这份设计，重投不过的原因由之后的检查照实报出。
    """
    ensure_framework(root)
    feature_root = root / features_dir(root) / feature
    src = feature_root / "AR" / "story-src"

    def flow(*args: str) -> dict:
        proc = subprocess.run([sys.executable, str(flow_script), *args, "--feature", feature, "--project-root", str(root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(f"{args}: {proc.stdout}\n{proc.stderr}")
        return json.loads(proc.stdout[proc.stdout.index("{"):])

    if not (src / "story-flow.json").is_file():
        walk_to_design(flow, src, access, hand=False)
    # 设计走到准入：蓝图的需求条目采用本需求的材料版本，带本夹具要的知识适用性判断与设计内容
    install_blueprint(root, feature, access, judgements=judgements, **(design or {}))
    if (feature_root / "AR" / "story.md").is_file():
        proc = subprocess.run(["node", str(build_script), "project", "--feature", feature, "--project-root", str(root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        if proc.returncode != 0 and project_must_pass:
            raise RuntimeError(f"附录按蓝图重投失败：{proc.stdout}{proc.stderr}")


EVIDENCE = """
import { pathToFileURL } from 'node:url';
const [root, access, feature, phases] = process.argv.slice(1);
const { loadNative } = await import(pathToFileURL(access).href);
const native = loadNative(root);
const m = native.module('scripts/utils/phase-evidence-manifest.ts');
for (const phase of phases.split(',')) {
  m.writePhaseEvidenceManifest(native.root,
    m.resolvePhaseEvidenceManifest({ projectRoot: native.root, feature, phase, frameworkRoot: native.frameworkRoot }));
}
"""


def write_native_evidence(root: Path, feature: str, phases: list[str], access: Path) -> None:
    """按原生 `resolvePhaseEvidenceManifest` 给 `phases` 逐个写阶段证据清单（盘上现状即被证据锁定的状态）。"""
    ensure_framework(root)
    proc = subprocess.run(["node", "--input-type=module", "-e", EVIDENCE, str(root), str(access), feature, ",".join(phases)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"阶段证据清单写不出：{proc.stderr[-600:]}")


def install_review_mechanism(root: Path, extension: Path) -> None:
    """审查对象里的章节合同与判据取工程里装的那份扩展：只装了部分扩展的测试工程从 `extension` 补这两份。"""
    for rel in ("skills/story/contracts/story-chapters.json", "rules/story-reader-rules.yaml"):
        target = root / "doc" / "extensions" / rel
        if not target.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(extension / rel, target)


#: 夹具审查者的发现：每种结论一份（编号、严重程度、问题与依据、修正责任），结论按严重程度定
REVIEW_ISSUES = {
    "pass": [],
    "advice": [("F-1", "MINOR", "背景一章的结论先于依据出现，读者要回读", "作者把依据移到结论之前")],
    "major": [("F-1", "MAJOR", "流程一章没说受理失败之后谁通知用户", "作者补写失败之后的去向")],
    "block": [("F-1", "BLOCKER", "材料要求的超时释放在正文里没有落点", "作者在业务方案一章补写超时释放由谁发起")],
}


def write_review(root: Path, feature: str, kind: str = "pass") -> Path:
    """夹具审查者：按 Story 报告合同写一份回复，原样存到准备记录给的回复位置。

    只验证协议——准备、报告合同与结果归类接得上——不是真实的独立审查。返回回复的路径。
    """
    review = root / features_dir(root) / feature / "AR" / "story-src" / "review"
    prepared = json.loads((review / "prepared.json").read_text(encoding="utf-8"))
    original = root / prepared["report_file"]
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_text(review_text(root, feature, kind, prepared["material_key"]), encoding="utf-8")
    return original


def review_text(root: Path, feature: str, kind: str, material_key: str) -> str:
    """夹具审查者的回复正文：开头两行回显 `material_key` 与结论，之后是读者自己组织的说明与发现。"""
    story = f"{features_dir(root)}/{feature}/AR/story.md"
    issues = REVIEW_ISSUES[kind]
    severe = any(i[1] in ("BLOCKER", "MAJOR") for i in issues)
    overall = "fail" if severe else "warn" if issues else "pass"
    return "\n".join([
        f"material_key: {material_key}", f"conclusion: {overall}", "",
        "首读结论：只读 Story 能读出要做什么、为什么做和怎么算对。", "",
        "这次做的是首次阅读：对着业务来源与人签通读了 Story 与 Review。", "",
        *([f"- {a}（{b}）`{story}`：{c}。修正：{d}。" for a, b, c, d in issues] or ["没有发现。"]), ""])
