"""已交给设计、蓝图准入的需求工作区怎样准备——测试夹具与失效形态运行器共用这一份。

- **接 Framework**：临时工程接 demo 的 Framework（整目录链接，或在已有替身旁逐层补缺）；
- **准入蓝图**：取 `test/fixtures/blueprint/wallet-balance-refresh` 那份真实准入的 canonical，蓝图标识换成需求关联的那一个
  （新需求建议 `bp-<需求标识>`，蓝图工作区与需求目录分开），按需插入知识应用决定、精确明细与术语事实；评审投影在真实流程里
  由设计职责按原生 renderer 生成，这里代它生成同一份字节——Extension 只读、不写它；
- **设计消费本次输入**：需求已交给设计时，蓝图的需求条目换成这次冻结输入推出的原生条目（与原生 builder 从
  物化件取条目同形），来源指纹按原生算法重算——真实流程里这是设计职责在 component-design 里做的；
- **交给设计**：用真实流程命令走材料关卡、范围关卡、关联设计对象与冻结输入，人签与真实运行留下的记录同形。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[2]


def link_framework(root: Path) -> Path:
    """让临时工程根接入 demo 的 Framework：复制 demo 的 `framework.config.json`（物化哪些宿主由它定），
    `framework/` 整个目录接一条指向 demo 的 junction（Windows）或符号链接。安装与宿主入口物化只读它、
    写在工程根；链接在临时目录清理时被删，demo 不动。已存在的都不动。"""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    config = root / "framework.config.json"
    if not config.exists():
        shutil.copy2(REPO_ROOT / "demo" / "framework.config.json", config)
    target = root / "framework"
    if not target.exists():
        source = REPO_ROOT / "demo" / "framework"
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
    """`framework/` 已经在（只接了 yaml 包、或放了替身）的临时工程补接 demo Framework 缺的部分：
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
    fill(REPO_ROOT / "demo" / "framework", Path(root) / "framework", 2)


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
COMPONENT = "wallet-main"

RENDER = """
import * as fs from 'node:fs';
import * as path from 'node:path';
import { pathToFileURL } from 'node:url';
const [root, access, blueprint] = process.argv.slice(1);
const { loadNative } = await import(pathToFileURL(access).href);
const native = loadNative(root);
const loaded = native.module('scripts/utils/component-blueprint-path.ts').loadCanonicalBlueprint(root, blueprint);
const text = native.module('scripts/utils/blueprint-review-projection.ts').renderBlueprintReviewMarkdown(loaded.blueprint, loaded.artifactSha256);
fs.writeFileSync(path.join(path.dirname(loaded.canonicalPath), 'component-blueprint.review.md'), text);
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


def knowledge_decision(decision_id: str, unit: str, outcome: str, rationale: str,
                       requirement: str | None = None) -> dict:
    """一条规约的知识应用决定：来源文件与原文摘要在放进蓝图时按工程里激活的知识算（`decision_text`）。"""
    return {"decision_id": decision_id, "unit": unit, "outcome": outcome, "rationale": rationale,
            **({"requirement": requirement} if requirement else {})}


ACTIVE_CONSTRAINTS = """
import { pathToFileURL } from 'node:url';
const [root, module] = process.argv.slice(1);
const { activeKnowledge } = await import(pathToFileURL(module).href);
process.stdout.write(JSON.stringify(activeKnowledge(root).constraints.map(c => ({ file: c.file, units: c.units }))));
"""


def active_constraints(root: Path, access: Path) -> list[dict]:
    """工程激活的规约文件与各自的单元（扩展根相对路径）；没有激活清单就没有。"""
    if not (root / "doc" / "extensions" / "manifest.yaml").is_file():
        return []
    proc = subprocess.run(["node", "--input-type=module", "-e", ACTIVE_CONSTRAINTS, str(root),
                           str(Path(access).parent / "knowledge.mjs")],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"激活知识读不出来：{proc.stderr[-600:]}")
    return json.loads(proc.stdout)


def decision_text(root: Path, spec: dict, active: list[dict]) -> str:
    """一条知识应用决定的 canonical 文本（缩进对齐顶层 decisions 列表）：来源与摘要取激活的那份规约文件。"""
    source = next((c for c in active if spec["unit"] in c["units"]), None)
    if source is None:
        raise AssertionError(f"夹具要判的 {spec['unit']} 不在工程激活的规约里")
    ref = f"doc/extensions/{source['file']}"
    applied = spec["outcome"] == "applied"
    knowledge = {"kind": "constraints", "form": "entries", "unit": spec["unit"],
                 "source_sha256": "sha256:" + hashlib.sha256((root / ref).read_bytes()).hexdigest(),
                 "outcome": spec["outcome"], **({"requirement": spec["requirement"]} if applied else {}),
                 "target_refs": [TARGET] if applied else []}
    provenance = {"source_kind": "knowledge", "source_ref": ref, "observed_at": "2026-09-30T00:00:00Z",
                  "evidence_strength": "inferred", "extraction_method": "read_and_apply"}
    status = "not_applicable" if spec["outcome"] == "not_applicable" else "answered_with_evidence"
    return (f"    - decision_id: {spec['decision_id']}\n"
            "      kind: knowledge_application\n"
            f"      status: {status}\n"
            "      owner: design-author\n"
            f"      rationale: {json.dumps(spec['rationale'], ensure_ascii=False)}\n"
            f"      provenance: {json.dumps(provenance, ensure_ascii=False)}\n"
            f"      verification_refs: [{TARGET}]\n"
            f"      knowledge: {json.dumps(knowledge, ensure_ascii=False)}\n")


def judged_rules(active: list[dict], given: list[dict] | None, exact: bool) -> list[dict]:
    """设计对激活规约的判断：`exact` 时就是给的这几条（反例用，可以漏判）；否则给的里面激活了的照用，
    其余逐条判定本需求不涉及（夹具默认）。"""
    if exact:
        return list(given or [])
    units = {u for c in active for u in c["units"]}
    chosen = [d for d in (given or []) if d["unit"] in units]
    done = {d["unit"] for d in chosen}
    return chosen + [knowledge_decision(f"knowledge-{u.lower()}", u, "not_applicable", "夹具：本需求不涉及这条规约")
                     for c in active for u in c["units"] if u not in done]


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
    """需求关联的蓝图标识：流程契约里关联了就用它，还没关联用新需求的建议标识 `bp-<需求标识>`。"""
    flow = root / features_dir(root) / feature / "AR" / "story-src" / "story-flow.json"
    contract = json.loads(flow.read_text(encoding="utf-8")) if flow.is_file() else {}
    return (contract.get("design_binding") or {}).get("blueprint_id") or f"bp-{feature}"


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
    """需求登记的冻结输入推出的原生需求条目：用那份扩展的冻结模块算物化件，去掉 authority（原生
    `materializedScopeItems` 的形状）。需求还没交给设计时返回 None。"""
    flow = root / features_dir(root) / feature / "AR" / "story-src" / "story-flow.json"
    contract = json.loads(flow.read_text(encoding="utf-8")) if flow.is_file() else {}
    ref = (contract.get("input") or {}).get("snapshot_ref")
    if not ref:
        return None
    core = Path(access).resolve().parents[2] / "skills" / "story" / "scripts" / "core"
    if str(core) not in sys.path:
        sys.path.insert(0, str(core))
    from materials import frozen  # noqa: PLC0415
    snapshot = json.loads((root / ref).read_text(encoding="utf-8"))
    doc = frozen.materialization({"snapshot": snapshot}, ref.rsplit("/", 1)[0], contract["design_binding"])
    return [{k: v for k, v in item.items() if k != "authority"} for item in doc["items"]]


def consume_items(text: str, items: list[dict]) -> str:
    """canonical 的需求条目与追溯换成给定条目：每条追溯到蓝图的余额刷新节点。"""
    head, rest = text.split("    current_scope_items:\n", 1)
    tail = rest[rest.index("\napp_lens:"):]
    trace = [{"item_id": i["item_id"], "blueprint_refs": ["view:logical/node:wallet-balance"]} for i in items]
    return (head + "    current_scope_items: " + json.dumps(items, ensure_ascii=False)
            + "\n  requirement_traceability: " + json.dumps(trace, ensure_ascii=False) + tail)


def install_blueprint(root: Path, feature: str, access: Path, *, projection: bool = True,
                      decisions: list[dict] | None = None, details: list[str] | None = None,
                      terms: list[str] | None = None, consume: bool = True, exact_decisions: bool = False,
                      items: list[dict] | None = None) -> Path:
    """把需求关联的准入蓝图放到 `<features_dir>/<蓝图标识>/blueprint/`（与需求目录分开），返回 canonical 路径。

    `decisions` 是 `knowledge_decision` 给出的判断：激活了的照用，其余激活规约逐条判定不涉及；
    `exact_decisions` 为真时蓝图里就只有给的这几条（反例用：可以漏判，空列表就一条不判）；
    `details` 是 `story_detail` 生成的 canonical 片段，按原文插进去；
    `projection` 为假时不生成评审投影。需求已交给设计且 `consume` 为真时，蓝图消费登记的冻结输入；
    `consume` 为假时保留夹具原来那份需求（另一个需求）的条目——反例用；`items` 直接给出要消费的条目
    （流程契约还没落盘时用）。
    """
    ensure_framework(root)
    blueprint = blueprint_of(root, feature)
    source = BLUEPRINT_FIXTURE / "doc" / "features" / "wallet-balance-refresh" / "blueprint" / "component-blueprint.yaml"
    target = root / features_dir(root) / blueprint / "blueprint" / "component-blueprint.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    text = source.read_text(encoding="utf-8").replace("blueprint_id: wallet-balance-refresh\n", f"blueprint_id: {blueprint}\n", 1)
    # 质询原件随蓝图一起放到新工作区，质询项指向它的路径跟着换
    text = text.replace("doc/features/wallet-balance-refresh/blueprint/questioning/",
                        f"{features_dir(root)}/{blueprint}/blueprint/questioning/")
    shutil.copytree(source.parent / "questioning", target.parent / "questioning", dirs_exist_ok=True)
    active = active_constraints(root, access)
    judged = judged_rules(active, decisions, exact_decisions)
    if judged:
        text = text.replace("decisions_and_gaps:\n  decisions:\n", "decisions_and_gaps:\n  decisions:\n"
                            + "".join(decision_text(root, d, active) for d in judged), 1)
    if details:
        text = text.rstrip("\n") + "\nstory_details:\n" + "".join(details)
    if terms:
        text = text.replace("  facts:\n", "  facts:\n" + "".join(terms), 1)
    items = items if items is not None else handed_items(root, feature, access) if consume else None
    if items:
        text = consume_items(text, items)
    target.write_bytes(text.encode("utf-8"))
    if terms or items:
        # 事实或需求条目变了，来源指纹按原生算法重算：它由 discovery 的事实与当前范围条目确定性得出
        proc = subprocess.run(["node", "--input-type=module", "-e", REFINGERPRINT, str(root), str(access), blueprint, str(target)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(f"来源指纹重算失败：{proc.stderr[-600:]}")
    shutil.copytree(BLUEPRINT_FIXTURE / "doc" / "requirements", root / "doc" / "requirements", dirs_exist_ok=True)
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


def design_input(src: Path) -> dict:
    """本轮确认的材料全部采用，人签取范围关卡那一条，需求条目指向第一份正文。"""
    manifest = json.loads((src / "materials.json").read_text(encoding="utf-8"))
    adopted = [p for m in manifest["materials"] if m.get("sha256") for p in m["paths"]]
    contract = json.loads((src / "story-flow.json").read_text(encoding="utf-8"))
    asks = [g["ask_id"] for g in contract["rounds"][-1]["gates"]
            if g["gate"] == "scope_decision" and g["outcome"] == "accepted"]
    main = next(p for m in manifest["materials"] if m["kind"] == "doc" and m.get("sha256") for p in m["paths"])
    return {"adopted": adopted, "human_decision_ids": asks[-1:],
            "scope_items": [{"item_id": "request-main", "kind": "requirement", "source_path": main,
                             "authority": {"owner": "需求负责人", "formality": "formal_requirement"}}]}


def hand_to_design(flow: Callable[..., dict], src: Path, access: Path) -> None:
    """关联设计对象、写设计输入，提交冻结；再由设计按这份输入走到准入。蓝图标识取需求标识；
    `access` 是用来调原生的 framework-access。"""
    feature_root = src.parents[1]
    root = project_root_of(feature_root)
    ensure_framework(root)
    blueprint = f"bp-{feature_root.name}"
    flow("bind-design", "--component", COMPONENT, "--blueprint", blueprint)
    (src / "design-input.json").write_text(json.dumps(design_input(src), ensure_ascii=False), encoding="utf-8")
    flow("complete", "--from", "AR/story-src/design-draft.md", "--input", "AR/story-src/design-input.json")
    # 设计由原生 component-design 完成：放一份消费了这次输入、已准入的蓝图（带一条知识应用决定），成文按它写
    if not (feature_root.parent / blueprint / "blueprint" / "component-blueprint.yaml").is_file():
        install_blueprint(root, feature_root.name, access)


def walk_to_design(flow: Callable[..., dict], src: Path, draft_text: str, access: Path,
                   scope_text: str = "本 AR 承载自动充值签约与管理") -> None:
    """用真实流程命令走完 S1–S3 并交给设计：材料关卡、需求分析、范围关卡、关联设计对象、冻结输入。

    工程里同时放好一份已准入的蓝图——走完即「可以成文」。"""
    src.mkdir(parents=True, exist_ok=True)
    (src / "design-draft.md").write_text(draft_text, encoding="utf-8")
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
    hand_to_design(flow, src, access)


def prepare_designed(root: Path, feature: str, *, flow_script: Path, build_script: Path, access: Path,
                     draft: str, decisions: list[dict] | None = None, design: dict | None = None,
                     project_must_pass: bool = True) -> None:
    """就地把一份需求工作区准备成「交给设计、蓝图已准入」：接 Framework、放准入蓝图、用真实流程命令走到交给设计，
    再把 init 为没拉到的上游补的占位件删掉登记（与夹具原有材料一致），附录机器区按蓝图重投。

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
        before = {p for p in feature_root.rglob("*") if p.is_file()}
        walk_to_design(flow, src, draft, access)
        placeholders = [feature_root / rel for rel in ("RR/prd.md", "SR/design.md")
                        if feature_root / rel not in before and (feature_root / rel).is_file()]
        for path in placeholders:
            path.unlink()
        if placeholders:
            flow("round")
    # 设计按登记的输入走到准入：蓝图消费这次冻结输入，带本夹具要的知识应用决定与设计内容
    install_blueprint(root, feature, access, decisions=decisions, **(design or {}))
    if (feature_root / "AR" / "story.md").is_file():
        proc = subprocess.run(["node", str(build_script), "project", "--feature", feature, "--project-root", str(root)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        if proc.returncode != 0 and project_must_pass:
            raise RuntimeError(f"附录按蓝图重投失败：{proc.stdout}{proc.stderr}")


def install_review_mechanism(root: Path, extension: Path) -> None:
    """审查对象里的章节合同与判据取工程里装的那份扩展：只装了部分扩展的测试工程从 `extension` 补这两份。"""
    for rel in ("skills/story/contracts/story-chapters.json", "rules/story-reader-rules.yaml"):
        target = root / "doc" / "extensions" / rel
        if not target.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(extension / rel, target)


#: 夹具审查者的问题清单：每种结论一份（编号、严重程度、分类、问题描述、修复建议）
REVIEW_ISSUES = {
    "pass": [],
    "advice": [("CR-001", "MINOR", "其他", "背景一章的结论先于依据出现，读者要回读", "把依据移到结论之前")],
    "major": [("CR-001", "MAJOR", "其他", "流程一章没说受理失败之后谁通知用户", "补写失败之后的去向")],
    "block": [("CR-001", "BLOCKER", "逻辑错误", "材料要求的超时释放在正文里没有落点", "在业务方案一章补写超时释放由谁发起")],
}


def write_review(root: Path, feature: str, kind: str = "pass") -> Path:
    """夹具审查者：按原生格式写事实记录，并把一份原生 review 报告作为回复原样存到 `review-original.md`。

    只验证协议——准备出的请求、原生检查与结果归类接得上——不是真实的独立审查。返回原回复的路径。
    """
    review = root / features_dir(root) / feature / "AR" / "story-src" / "review"
    prepared = json.loads((review / "prepared.json").read_text(encoding="utf-8"))
    files = sorted(json.loads((review / "request.json").read_text(encoding="utf-8"))["targets"]["files"])
    out = root / prepared["report_dir"]
    (out / "context").mkdir(parents=True, exist_ok=True)
    (out / "context" / "facts.md").write_text("\n".join([
        "---", 'schema_version: "1.1"', f"request_sha256: {prepared['request_sha256']}", "established_by: review",
        "ready_to_produce: true", "has_blocker_coverage_risk: false", "exploration_mode: subagent", "subagents_used: yes",
        f"files_inspected_count: {len(files)}", f"searches_performed_estimate: {max(3, len(files))}",
        "source_code_paths:", *[f"  - {p}" for p in files], "decisions_unlocked:", "  - 审查结论", "---", "",
        "## Code Facts", "", "| # | 事实 | 路径 | 证据 |", "|---|---|---|---|",
        *[f"| {i + 1} | 读了全文 | `{p}` | 全文 |" for i, p in enumerate(files)], ""]), encoding="utf-8")
    story = f"{features_dir(root)}/{feature}/AR/story.md"
    issues = REVIEW_ISSUES[kind]
    count = {s: sum(1 for i in issues if i[1] == s) for s in ("BLOCKER", "MAJOR", "MINOR", "INFO")}
    verdict = "不通过" if count["BLOCKER"] else "有条件通过" if count["MAJOR"] else "通过"
    table = ["| 编号 | 严重程度 | 分类 | 问题描述 | 涉及文件 | 修复建议 |", "|---|---|---|---|---|---|",
             *[f"| {a} | {b} | {c} | {d} | `{story}` | {e} |" for a, b, c, d, e in issues]]
    text = "\n".join([
        f"# Story 审查报告 — {feature}", "", "## 一、审查范围", "", *[f"- `{p}`" for p in files], "",
        "## 二、审查方法", "", "按任务里的判据逐章对着来源读。", "",
        "## 三、问题清单", "", *(table if issues else ["无问题。"]), "",
        "## 四、问题统计", "", "| 严重程度 | 数量 |", "|---|---|", *[f"| {s} | {n} |" for s, n in count.items()],
        f"| **合计** | **{len(issues)}** |", "",
        "## 五、修复建议摘要", "", "见问题清单。" if issues else "无。", "",
        "## 六、结论", "", f"**审查结论**: {verdict}", "", "**判定依据**:",
        f"- BLOCKER 数量: {count['BLOCKER']}", f"- MAJOR 数量: {count['MAJOR']}", ""])
    original = out / "review-original.md"
    original.write_text(text, encoding="utf-8")
    return original
