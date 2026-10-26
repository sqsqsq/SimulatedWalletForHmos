#!/usr/bin/env node
/**
 * 读 Framework 原生能力的唯一入口：从显式工程根的 `framework/harness` 加载它安装的 ts-node，
 * 再 require 原生 TypeScript 模块。不复制框架实现、不另装运行器、不从维护源码导入。
 *
 * 同一进程对同一工程根只注册一次；harness 或其依赖缺失时抛错，错误里写明缺什么、怎么装。
 *
 * 命令行只读取、不写盘：
 *   node framework-access.mjs --project-root <根> --action blueprint --blueprint <id> --purpose draft|delivery
 *        [--snapshot <冻结快照的项目相对路径>]（给了就核蓝图消费了这次交给设计的条目）
 *        [--summary]（只核状态：同一读取与校验，输出省掉蓝图正文 blueprint，其余字段照旧）
 *        [--report-phases <阶段,阶段>]（给了就在每个施工单位上附原生阶段报告目录 phase_reports）
 *   node framework-access.mjs --project-root <根> --action feature --feature <原生 id> --phase <阶段>
 *        [--requirement-file <文件> | --requirement <原文>]（无 run 的 spec 恢复不出需求来源时给）
 *   node framework-access.mjs --project-root <根> --action binding --component <组件 id> --blueprint <蓝图 id>
 *   node framework-access.mjs --project-root <根> --action sources  < 来源物化 JSON（stdin）
 *   node framework-access.mjs --project-root <根> --action feedback --blueprint <id>  < blueprint-review-feedback@1（stdin）
 *   node framework-access.mjs --project-root <根> --action feedback-related --blueprint <id> --ref <反馈文件工程相对路径>  < feedback_id 列表（stdin）
 *   node framework-access.mjs --project-root <根> --action feature-identity --feature <逻辑 id> [--report-phases <阶段,阶段>]
 *   node framework-access.mjs --project-root <根> --action phase-evidence --feature <逻辑 id> --phases <有序阶段,阶段>
 *   node framework-access.mjs --project-root <根> --action story-review-visual --feature <逻辑需求 id>
 * 写动作（显式调用，只走原生接口）：
 *   node framework-access.mjs --project-root <根> --action change-unit-readiness --blueprint <id>
 *   node framework-access.mjs --project-root <根> --action change-unit-revise --blueprint <id>  < 原生 revisions 数组（stdin）
 * 输出 JSON；退出 0 正常，1 对象缺失、坏身份、过期、未准入、业务未就绪或忙（带原生 issues 与结果），2 参数、依赖或工具故障。
 */
import * as fs from 'node:fs';
import { createRequire } from 'node:module';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

const loaded = new Map();

/**
 * @param {string} projectRoot 消费工程根（含 framework.config.json 与 framework/）
 * @returns {{ root: string, frameworkRoot: string, harness: string, require: (id: string) => any, module: (rel: string) => any }}
 */
export function loadNative(projectRoot) {
  const root = path.resolve(projectRoot);
  if (loaded.has(root)) return loaded.get(root);
  const frameworkRoot = path.join(root, 'framework');
  const harness = path.join(frameworkRoot, 'harness');
  const pkg = path.join(harness, 'package.json');
  if (!fs.existsSync(pkg)) throw new Error(`${root} 没有接入 Framework（缺 framework/harness/package.json）`);
  const req = createRequire(pkg);
  try {
    req('ts-node').register({ project: path.join(harness, 'tsconfig.json'), transpileOnly: true });
  } catch (e) {
    throw new Error(`Framework harness 的依赖不可用（${e?.code ?? e?.message ?? e}）：先在 ${harness} 下跑 npm install`);
  }
  const api = {
    root, frameworkRoot, harness,
    require: req,
    module: rel => req(path.join(harness, ...rel.split('/'))),
  };
  loaded.set(root, api);
  return api;
}

const rel = (root, p) => path.relative(root, p).split(path.sep).join('/');
const failure = (status, error) => ({ status, issues: [{ code: error?.code ?? 'error', message: String(error?.message ?? error) }] });

/** 蓝图的原生完整引用：整蓝图为目标，指向读到的那一版字节。 */
function blueprintRef(loaded, blueprintId) {
  const b = loaded.blueprint;
  return {
    artifact: 'component-blueprint@1', component_id: b.component_id, blueprint_id: blueprintId,
    revision: b.revision, source_fingerprint: b.source_fingerprint, artifact_sha256: loaded.artifactSha256,
    target: { kind: 'blueprint', id: blueprintId },
  };
}

/** 证据强度的高低：蓝图声明的不能高于交给设计时的。 */
const STRENGTH = { unknown: 0, inferred: 1, observed: 2, authoritative: 3 };

/**
 * 这一版蓝图有没有消费本次交给设计的条目。
 *
 * 预期条目由冻结快照推出：身份与类别取语义条目，来源是冻结目录里的那份文件、摘要是它的原始字节。
 * 每条都要在原生 `currentScopeItems` 里有同一 item_id，类别、来源路径（按原生规则规范化，锚点不计）与摘要一致，
 * 声明的证据强度不高于交给设计时。蓝图另有其他有据条目不算问题；需求内容是否被设计落实由独立审查判断。
 */
function scopeConsumption(native, blueprint, snapshotRef) {
  let snapshot;
  try {
    snapshot = JSON.parse(fs.readFileSync(path.join(native.root, ...String(snapshotRef).split('/')), 'utf8'));
  } catch (e) {
    return failure('invalid', e);
  }
  const guard = native.module('scripts/utils/project-relative-path.ts');
  const normal = (ref) => {
    try {
      return path.posix.normalize(guard.validateProjectRelativePath(native.root, String(ref ?? '').split('#')[0], 'source_ref'));
    } catch {
      return null;
    }
  };
  const dir = path.posix.dirname(String(snapshotRef));
  const rows = new Map((snapshot.files ?? []).map(r => [r.path, r]));
  const have = new Map(native.module('scripts/utils/blueprint-requirement-traceability.ts')
    .currentScopeItems(blueprint).map(i => [String(i.item_id), i]));
  const issues = [];
  for (const item of snapshot.scope_items ?? []) {
    const row = rows.get(item.source_path);
    const expected = { ref: normal(`${dir}/files/${item.source_path}`), sha: `sha256:${row?.sha256}` };
    const got = have.get(String(item.item_id));
    const say = (message) => issues.push({ code: 'scope_item_not_consumed', item_id: item.item_id, message });
    if (!got) {
      say(`蓝图没有条目 ${item.item_id}`);
    } else if (got.kind !== item.kind) {
      say(`条目 ${item.item_id} 在蓝图里是 ${got.kind}，交给设计的是 ${item.kind}`);
    } else if (normal(got.source_ref) !== expected.ref || got.source_sha256 !== expected.sha) {
      say(`条目 ${item.item_id} 在蓝图里的来源是 ${got.source_ref}（${got.source_sha256}），不是本次冻结的 ${expected.ref}`);
    } else if ((STRENGTH[got.provenance?.evidence_strength] ?? 0) > (STRENGTH[row?.provenance?.evidence_strength] ?? 0)) {
      say(`条目 ${item.item_id} 在蓝图里声明为 ${got.provenance?.evidence_strength}，交给设计时只是 ${row?.provenance?.evidence_strength}`);
    }
  }
  return { status: issues.length ? 'unconsumed' : 'ok', issues };
}

/** 宿主能不能派独立审查子代理：原生按当前 adapter 的 `verifier_subagent` 声明判（`agents/<adapter>/adapter.yaml`）。 */
export function hostReviewer(projectRoot) {
  const native = loadNative(projectRoot);
  const adapter = native.module('config.ts').loadFrameworkConfig(projectRoot)?.agent_adapter ?? null;
  return { adapter, declared: native.module('scripts/utils/adapter-catalog.ts')
    .resolveVerifierSubagentDeclared(native.frameworkRoot, adapter) };
}

/**
 * 读蓝图：draft 可返回未准入草稿与原生 issues，delivery 要求已准入。
 * 前后两次读到的字节不同（期间被改写）报 stale，不消费混合对象。
 * 给了冻结快照时一并回答 `consumption`：这一版蓝图消费了本次交给设计的条目没有。
 * 已准入时列出活动施工单位 `units`（原生枚举、去掉已被取代的）：身份、Feature 标识与原生目录（工程相对）；
 * 给了 `reportPhases` 时每个单位另带 `phase_reports: [{phase, dir}|{phase, error}]`（phaseReportsDir 的原生结果）。
 */
export function readBlueprint(projectRoot, blueprintId, purpose = 'draft', snapshotRef = null, reportPhases = null) {
  const native = loadNative(projectRoot);
  const paths = native.module('scripts/utils/component-blueprint-path.ts');
  const check = native.module('scripts/check-component-blueprint.ts');
  const prep = native.module('scripts/utils/change-unit-design-preparation.ts');
  let first;
  let checked;
  try {
    first = paths.loadCanonicalBlueprint(native.root, blueprintId);
    checked = check.checkCanonicalComponentBlueprint(native.root, blueprintId);
  } catch (e) {
    return failure(e?.code === 'component_blueprint_missing' ? 'missing' : 'invalid', e);
  }
  if (checked.artifactSha256 !== first.artifactSha256) {
    return { status: 'stale', issues: [{ code: 'blueprint_changed_while_reading', message: '读取期间蓝图被改写，重新读取' }] };
  }
  const admitted = prep.evaluateDesignPreparationEntry(native.root, blueprintId).blueprintAdmitted;
  let last;
  try {
    last = paths.loadCanonicalBlueprint(native.root, blueprintId);
  } catch (e) {
    return failure('stale', e);
  }
  if (last.artifactSha256 !== first.artifactSha256) {
    return { status: 'stale', issues: [{ code: 'blueprint_changed_while_reading', message: '读取期间蓝图被改写，重新读取' }] };
  }
  const out = {
    status: 'ok', canonical_path: rel(native.root, checked.canonicalPath), blueprint: checked.blueprint,
    blueprint_ref: blueprintRef(checked, blueprintId), admitted, issues: checked.issues ?? [],
    projection: readProjection(native, checked, blueprintId), units: admitted ? activeUnits(native, projectRoot, blueprintId, reportPhases) : [],
    ...(snapshotRef ? { consumption: scopeConsumption(native, checked.blueprint, snapshotRef) } : {}),
  };
  if (purpose === 'delivery' && !admitted) out.status = 'not_admitted';
  return out;
}

/** 蓝图的活动施工单位：原生枚举，去掉被精确取代而退役的；目录取原生身份给出的位置。 */
function activeUnits(native, projectRoot, blueprintId, reportPhases) {
  const retired = native.module('scripts/utils/component-closure-inputs.ts').retiredChangeUnitIds(native.root, blueprintId);
  const encode = native.module('scripts/utils/feature-identity.js').encodeCuFeatureId;
  return native.module('scripts/utils/change-unit-path.ts').enumerateCanonicalChangeUnits(native.root, blueprintId)
    .map(u => String(u.changeUnit.change_unit_id)).filter(id => !retired.has(id)).sort()
    .map(id => {
      const featureId = encode(blueprintId, id);
      const dir = featureDir(projectRoot, featureId);
      return { change_unit_id: id, feature_id: featureId, path: dir ? rel(native.root, dir) : null,
        ...(reportPhases ? { phase_reports: reportPhases.map(phase => ({ phase, ...phaseReportsDir(projectRoot, featureId, phase) })) } : {}) };
    });
}

/** 蓝图旁的原生评审投影：没有、与这一版 canonical 的确定性派生对不上（stale）、有效。 */
function readProjection(native, checked, blueprintId) {
  const file = path.join(path.dirname(checked.canonicalPath), 'component-blueprint.review.md');
  const out = { path: rel(native.root, file) };
  if (!fs.existsSync(file)) return { ...out, status: 'missing', issues: [] };
  const issues = native.module('scripts/utils/blueprint-host-seams.ts')
    .validateBlueprintReviewPublication(fs.readFileSync(file, 'utf8'), native.root, String(blueprintId));
  return { ...out, status: issues.length ? 'stale' : 'valid', issues };
}

/**
 * 需求要关联的设计对象：组件与蓝图标识按原生规则核；蓝图已在时核它实际归属的组件，不按名称猜。
 * 蓝图还不存在是合法的新对象。
 */
function checkBinding(projectRoot, componentId, blueprintId) {
  const native = loadNative(projectRoot);
  const paths = native.module('scripts/utils/component-blueprint-path.ts');
  try {
    paths.assertComponentId(componentId);
    paths.assertBlueprintId(blueprintId);
  } catch (e) {
    return failure('invalid', e);
  }
  let loaded;
  try {
    loaded = paths.loadCanonicalBlueprint(native.root, blueprintId);
  } catch (e) {
    return e?.code === 'component_blueprint_missing' ? { status: 'ok', exists: false, issues: [] } : failure('invalid', e);
  }
  const actual = loaded.blueprint?.component_id;
  return actual === componentId ? { status: 'ok', exists: true, issues: [] }
    : { status: 'mismatch', exists: true, issues: [{ code: 'blueprint_component_mismatch', message: `蓝图 ${blueprintId} 归属组件 ${actual}，不是 ${componentId}` }] };
}

/**
 * 核一份来源物化（requirement-source-materialization@1 形状）：原生校验信封、项目内 source_ref、原始字节摘要、
 * provenance 与 authority。系统单的物化件落在冻结目录里；本地单同一形状只在内存里核，不另造 provider manifest。
 */
function checkSources(projectRoot, doc) {
  const native = loadNative(projectRoot);
  const issues = native.module('scripts/utils/blueprint-host-seams.ts').validateRequirementSourceMaterialization(doc, {
    projectRoot: native.root, blueprintId: doc?.blueprint_id, componentId: doc?.component_id,
  });
  return { status: issues.length ? 'invalid' : 'ok', issues };
}

/**
 * 核一份设计评审反馈（blueprint-review-feedback@1）的候选资格：原生只判每条够不够格进入调和（授权、证据、版本、目标地址），
 * 不判接受与否，也不说处理了没有。
 */
function checkFeedback(projectRoot, blueprintId, doc) {
  const native = loadNative(projectRoot);
  const read = readBlueprint(projectRoot, blueprintId, 'draft');
  if (read.status !== 'ok') return { status: read.status, issues: read.issues ?? [], candidates: null };
  const intake = native.module('scripts/utils/blueprint-host-seams.ts').validateBlueprintReviewFeedback(doc, read.blueprint);
  return {
    status: intake.issues.some(i => i.severity === 'BLOCKER') ? 'invalid' : 'ok', issues: intake.issues,
    candidates: { rulings: intake.authoritativeRulingCandidateIds, facts: intake.factSupplementCandidateIds },
    revision: read.blueprint.revision,
  };
}

/**
 * 当前蓝图里与某份反馈精确相关的决定：来源 `provenance.source_ref` 恰好是「反馈文件的工程相对路径#feedback_id」的那些，
 * 带原生 status 与当前 revision。只是观察：有相关决定不等于反馈被接受，是否接受看负责方的实际回复与当前设计。
 */
function feedbackRelated(projectRoot, blueprintId, ref, ids) {
  const read = readBlueprint(projectRoot, blueprintId, 'draft');
  if (read.status !== 'ok') return { status: read.status, issues: read.issues ?? [], related: {} };
  const related = Object.fromEntries(ids.map(id => [id, (read.blueprint.decisions_and_gaps?.decisions ?? [])
    .filter(d => d?.provenance?.source_ref === `${ref}#${id}`)
    .map(d => ({ decision_id: d.decision_id, status: d.status }))]));
  return { status: 'ok', issues: [], revision: read.blueprint.revision, related };
}

/** 需求正文要调用方给：原生恢复不出，或给的与冻结绑定对不上。 */
const requirementGap = message => Object.assign(new Error(message), { code: 'requirement_text_needed' });

/**
 * 无 run 的 spec 按原生阶段调用恢复并核对原始需求：冻结候选的需求绑定指向来源文件时按原路径读回，
 * inline 或旧候选没存正文时用调用方给的原文；两种都按冻结绑定核一遍，来源变了照原生报 stale。
 */
function runlessRequirement(native, feature, supplied) {
  const { featureRequirementBinding } = native.module('scripts/utils/feature-track.ts');
  const { inferLegacyProjectRoot, resolveDependencyPath } = native.module('scripts/utils/project-relative-path.ts');
  const { resolveRequirementInput } = native.module('scripts/utils/goal-manifest.ts');
  const { readBoundInput } = native.module('scripts/utils/capability-resolution.ts');
  const binding = featureRequirementBinding(native.root, feature);
  const legacyRoot = inferLegacyProjectRoot(native.root, binding);
  let requirement;
  if (supplied.requirement !== undefined || supplied.requirementFile !== undefined) {
    requirement = resolveRequirementInput({ requirement: supplied.requirement, requirementFile: supplied.requirementFile, projectRoot: native.root });
  } else {
    const sources = binding.dependencies.filter(dep => dep.exists).map(dep => resolveDependencyPath(native.root, dep.path, legacyRoot));
    if (sources.length !== 1) throw requirementGap('范围候选没有保存可恢复的需求来源文件（inline 或旧候选）：调用方用 --requirement-file 或 --requirement 给出原始需求正文');
    requirement = resolveRequirementInput({ requirementFile: sources[0], projectRoot: native.root });
  }
  if (!requirement.text?.trim()) throw requirementGap('spec 阶段缺少原始需求正文');
  try {
    readBoundInput({
      frameworkRoot: native.frameworkRoot, projectRoot: native.root, feature, phase: 'spec', track: 'full',
      requirement: requirement.text, requirementSourceFiles: binding.dependencies.length ? requirement.sources : [],
      inputContext: { schema_version: '1.1', subject: { feature }, obligations: {}, required_outputs: [] },
    }, binding, legacyRoot);
  } catch (e) {
    throw Object.assign(e, { code: 'requirement_stale' });
  }
  return { requirement: requirement.text, requirementSourceFiles: requirement.sources };
}

/**
 * 原生 Feature 的身份与目录：CU 在 `<蓝图>/<施工单位>/`，平铺维护 Feature 在它自己的目录；CU 另带设计引用。
 * 阶段钩子按它找本阶段产物，不按需求名拼路径。
 *
 * @returns {{status: string, kind?: string, blueprintId?: string, changeUnitId?: string, dir?: string,
 *            design_refs?: object[], blueprint_ref?: object|null, issues: object[]}}
 */
export function featureIdentity(projectRoot, feature) {
  const native = loadNative(projectRoot);
  const identity = native.module('scripts/utils/feature-identity.js');
  const { loadFrameworkConfig } = native.module('config.ts');
  let kind;
  let relPath;
  try {
    kind = identity.classifyFeatureId(feature);
    relPath = identity.featureRelativePath(feature);
  } catch (e) {
    return failure('invalid', e);
  }
  const featuresDir = loadFrameworkConfig(native.root).paths?.features_dir ?? 'doc/features';
  const out = { status: 'ok', ...kind, dir: path.join(native.root, ...featuresDir.split('/'), ...String(relPath).split('/')),
    design_refs: [], blueprint_ref: null, issues: [] };
  if (kind.kind !== 'cu') return out;
  try {
    const unit = native.module('scripts/utils/change-unit-path.ts').loadCanonicalChangeUnit(native.root, kind.blueprintId, kind.changeUnitId).changeUnit;
    return { ...out, design_refs: unit.design_refs ?? [], blueprint_ref: unit.component_blueprint_ref };
  } catch (e) {
    return { ...out, ...failure('invalid', e) };
  }
}

/**
 * 逻辑 Feature 的原生身份、物理目录与（给了阶段时）各阶段报告目录：只复用 `featureIdentity` 与 `phaseReportsDir`，
 * 不进入阶段能力解析、不冻结范围，阶段还没开始时也取得到路径。
 */
function featureIdentityReport(projectRoot, feature, phases) {
  const id = featureIdentity(projectRoot, feature);
  const { dir, ...rest } = id;
  const native = loadNative(projectRoot);
  return { ...rest, dir: dir ? rel(native.root, dir) : null,
    ...(phases ? { phase_reports: phases.map(phase => {
      const r = phaseReportsDir(projectRoot, feature, phase);
      return { phase, ...(r.dir ? { dir: rel(native.root, r.dir) } : r) };
    }) } : {}) };
}

/**
 * 阶段证据当前有效性：原生 `recomputePhaseEvidenceStaleness` 的逐阶段结论原样返回（verdict、changed_paths、
 * integrity_errors、propagated_from）。不传 run 与 pending owner，不自建失效账本。
 */
function phaseEvidence(projectRoot, feature, chain) {
  const native = loadNative(projectRoot);
  try {
    const results = native.module('scripts/utils/phase-evidence-manifest.ts')
      .recomputePhaseEvidenceStaleness(native.root, feature, chain, { frameworkRoot: native.frameworkRoot });
    return { status: 'ok', results, issues: [] };
  } catch (e) {
    return failure('invalid', e);
  }
}

/**
 * 独立 Story 审查的视觉裁定：从这份需求当前的流程契约取已绑定的蓝图与冻结输入，按原生纯函数算看图能力与保真路由。
 *
 * - 需求原文取冻结包里采用的阅读原文（`original`，图片不算）与有效人签（`human_record`），提取稿、Story、写作设计不进；
 *   取不到时说明来源不足，不拿作者摘要补。
 * - 执行身份是 `story:<需求>:<蓝图>:<revision>:<artifact_sha256>`，需求摘要用冻结快照的登记摘要；
 *   能力取原生当前 adapter 的图像输入解析与 profile 的 OCR 就绪，审查者与作者同一执行能力（`reviewVision = hasVision`）。
 * - `deferral` 只在明确看不了图、原生 effective 是 semantic_layout、strictness 是 best_effort 且 defer=false 时为真：
 *   这时登记图片的图面未核可以按能力缺口记 WARN；其余情况看不了图就是没读完。
 * 只读，不调模型、不探测、不写裁定文件。
 */
export function storyReviewVisual(projectRoot, feature) {
  const native = loadNative(projectRoot);
  const id = featureIdentity(projectRoot, feature);
  if (id.status !== 'ok' || !id.dir) return { status: 'invalid', issues: id.issues ?? [] };
  let flow;
  try {
    flow = JSON.parse(fs.readFileSync(path.join(id.dir, 'AR', 'story-src', 'story-flow.json'), 'utf8'));
  } catch (e) {
    return failure('invalid', e);
  }
  const blueprintId = flow?.design_binding?.blueprint_id;
  const snapshotRef = flow?.input?.snapshot_ref;
  if (!blueprintId || !snapshotRef) {
    return { status: 'invalid', issues: [{ code: 'story_design_input_missing', message: '流程契约没有已绑定的蓝图或冻结输入：视觉裁定无从取来源' }] };
  }
  const read = readBlueprint(projectRoot, blueprintId, 'draft');
  if (read.status !== 'ok') return { status: read.status, issues: read.issues ?? [] };
  const frozen = readFrozenInputs(projectRoot, snapshotRef);
  if (frozen.problems.length) return { status: 'invalid', issues: frozen.problems.map(message => ({ code: 'frozen_input_invalid', message })) };
  const texts = frozen.files.filter(f => ['original', 'human_record'].includes(f.role))
    .map(f => `<<${f.path}>>
${Buffer.from(f.bytes).toString('utf8')}`);
  if (!frozen.files.some(f => f.role === 'original')) {
    return { status: 'invalid', issues: [{ code: 'requirement_text_missing', message: '冻结输入里没有采用的需求阅读原文：来源不足，视觉裁定不做' }] };
  }
  const ref = read.blueprint_ref;
  const executionIdentity = `story:${feature}:${blueprintId}:${ref.revision}:${ref.artifact_sha256}`;
  const cfg = native.module('config.ts').loadFrameworkConfig(native.root);
  const adapter = cfg?.agent_adapter ?? undefined;
  let probe;
  let ocrAvailable;
  try {
    probe = native.module('scripts/utils/multimodal-probe.ts').resolveContextAdapterImageInput(native.root, native.frameworkRoot, adapter);
    const profileDir = native.module('profile-loader.ts').loadResolvedProfile(native.root, cfg, native.frameworkRoot).profileDir;
    ocrAvailable = native.module('scripts/utils/fidelity-shared.ts').resolveOcrAvailableForRun(native.root, profileDir, adapter) === true;
  } catch (e) {
    return failure('invalid', e);
  }
  const hasVision = probe?.supported === true;
  const routing = native.module('scripts/utils/fidelity-shared.ts').resolveFidelityRoutingDecision({
    requirementText: texts.join('\n\n'), requirementSha: String(flow.input.snapshot_sha256 ?? ''), executionIdentity,
    capability: { hasVision, ocrAvailable, reviewVision: hasVision },
  });
  const deferral = !hasVision && routing.effective === 'semantic_layout' && routing.strictness === 'best_effort' && routing.defer === false;
  const fact = `看图能力：${hasVision ? '能看图' : '看不了图'}（adapter ${probe?.adapter ?? adapter ?? '未配置'}，${probe?.reason ?? '无说明'}；OCR ${ocrAvailable ? '就绪' : '不可用'}）；`
    + `原生保真路由 effective=${routing.effective}、strictness=${routing.strictness}、defer=${routing.defer}（决定 ${routing.decision?.decision_id ?? '—'}）`;
  return { status: 'ok', issues: [], blueprint_ref: ref, snapshot_ref: snapshotRef, snapshot_sha256: flow.input.snapshot_sha256 ?? null,
    execution_identity: executionIdentity, adapter: adapter ?? null, model_pin: null,
    capability: { has_vision: hasVision, image_input: probe?.imageInput ?? null, source: probe?.reason ?? null, ocr_available: ocrAvailable },
    routing, deferral, fact };
}

/** 施工单位设计准备是否就绪：原生 `deriveDesignPreparationReadiness`；忙或未就绪退出 1，结果原样保留。 */
function changeUnitReadiness(projectRoot, blueprintId) {
  const native = loadNative(projectRoot);
  try {
    const r = native.module('scripts/utils/change-unit-design-preparation.ts').deriveDesignPreparationReadiness(native.root, blueprintId);
    return { status: r.blueprintRefs?.busy ? 'busy' : r.ready ? 'ok' : 'not_ready', readiness: r, issues: [] };
  } catch (e) {
    return failure(e?.code ? 'rejected' : 'invalid', e);
  }
}

/** 施工单位内容修订：stdin 给原生 revisions 数组，原样交 `reviseChangeUnitContent`；被拒或忙退出 1 并带原生代码。 */
function changeUnitRevise(projectRoot, blueprintId, revisions) {
  const native = loadNative(projectRoot);
  if (!Array.isArray(revisions)) return { status: 'invalid', issues: [{ code: 'revisions_not_array', message: 'stdin 要是原生 revisions 数组' }] };
  try {
    const r = native.module('scripts/utils/change-unit-design-preparation.ts').reviseChangeUnitContent(native.root, blueprintId, revisions);
    if (r.busy) return { status: 'busy', busy: r.busy, issues: [{ code: 'busy', message: r.busy }] };
    return { status: 'ok', revised: r.revised.map(u => String(u.changeUnit?.change_unit_id ?? '')), unchanged: r.unchanged,
      review: r.reviewDocument ?? null, issues: [] };
  } catch (e) {
    return failure(e?.code ? 'rejected' : 'invalid', e);
  }
}

/**
 * 阶段审查报告目录：原生 `featurePhaseReportsDir` 给出的绝对路径（含工程配置的 reports_dir_pattern）。
 * 唯一消费者是阶段报告核对；解析失败返回原生的错误，不回落默认目录。
 *
 * @returns {{dir: string}|{error: string}}
 */
export function phaseReportsDir(projectRoot, feature, phase) {
  try {
    const native = loadNative(projectRoot);
    return { dir: native.module('config.ts').featurePhaseReportsDir(native.root, feature, phase, native.frameworkRoot) };
  } catch (e) {
    return { error: String(e?.message ?? e).split(/\r?\n/)[0] };
  }
}

/** 本阶段产物所在的目录，取原生身份给出的位置；身份认不出时为 null，由调用方报原生给的问题，不自拼目录。 */
export function featureDir(projectRoot, feature) {
  return featureIdentity(projectRoot, feature).dir ?? null;
}

/**
 * 候选蓝图采用的来源：原生 `currentScopeItems` 的每条声明（原引用连同片段、声明摘要、条目身份与 provenance），
 * 以及其中落在需求冻结输入布局（`<需求目录>/<需求>/AR/story-src/inputs/<版本>/files/…`）里的需求——按需求根去重，
 * 核需求关联的设计对象就是这份蓝图，带出蓝图采用的那一版与它的快照位置。不读来源正文、不算摘要；不枚举需求目录、不按名称猜。
 * 来源不在这一布局的条目是原生直接输入，不产生需求。
 *
 * @returns {{status: string, sources: {path: string, sha256: string, item_id: string, kind: string, provenance: object|null}[],
 *   requirements: {requirement: string, root: string, version: string, snapshot_ref: string}[], problems: string[]}}
 */
export function blueprintSources(projectRoot, blueprint) {
  const native = loadNative(projectRoot);
  const out = { status: 'ok', sources: [], requirements: [], problems: [] };
  const featuresDir = native.module('config.ts').loadFrameworkConfig(native.root).paths?.features_dir ?? 'doc/features';
  const guard = native.module('scripts/utils/project-relative-path.ts');
  const prefix = `${path.posix.normalize(featuresDir)}/`;
  const byRequirement = new Map();
  for (const item of native.module('scripts/utils/blueprint-requirement-traceability.ts').currentScopeItems(blueprint)) {
    let file;
    try {
      file = path.posix.normalize(guard.validateProjectRelativePath(native.root, String(item.source_ref ?? '').split('#')[0], 'source_ref'));
    } catch (e) {
      out.problems.push(`蓝图条目 ${item.item_id} 的来源 ${item.source_ref} 不是工程内路径（${e?.message ?? e}）——设计负责方处理`);
      continue;
    }
    out.sources.push({ path: String(item.source_ref), sha256: String(item.source_sha256 ?? ''), item_id: String(item.item_id),
      kind: item.kind, provenance: item.provenance ?? null });
    const parts = file.startsWith(prefix) ? file.slice(prefix.length).split('/') : [];
    if (parts.length < 7 || parts.slice(1, 4).join('/') !== 'AR/story-src/inputs' || parts[5] !== 'files') continue;
    byRequirement.set(parts[0], new Set([...(byRequirement.get(parts[0]) ?? []), parts[4]]));
  }
  for (const [requirement, versions] of byRequirement) {
    const root = `${prefix}${requirement}`;
    if (versions.size > 1) {
      out.problems.push(`需求 ${requirement}：蓝图同时消费了它 ${versions.size} 版冻结输入（${[...versions].join('、')}）——认不出当前是哪一版，设计负责方按一版同步`);
      continue;
    }
    let bound = null;
    try {
      bound = JSON.parse(fs.readFileSync(path.join(native.root, ...root.split('/'), 'AR', 'story-src', 'story-flow.json'), 'utf8'))?.design_binding;
    } catch {
      bound = null;
    }
    if (bound?.blueprint_id !== blueprint.blueprint_id || bound?.component_id !== blueprint.component_id) {
      out.problems.push(`需求 ${requirement} 关联的设计对象是 ${bound ? `${bound.component_id}/${bound.blueprint_id}` : '（读不到）'}，`
        + `不是 ${blueprint.component_id}/${blueprint.blueprint_id}——需求负责方核对`);
      continue;
    }
    const [version] = versions;
    out.requirements.push({ requirement, root, version, snapshot_ref: `${root}/AR/story-src/inputs/${version}/snapshot.json` });
  }
  return out;
}

/**
 * 读声明了摘要的来源：每项的原引用（可带片段）交原生 `resolveCurrentScopeSource`（工程内路径、原字节、片段定位、摘要），
 * 实际摘要要等于声明的 `sha256:<64 位十六进制>`。成功项保留输入的字段，加原生校验后的无片段工程路径 `file_path` 与原字节；
 * 失败项不给字节，按原引用记进 `excluded`（原因）与 `problems`。同一引用同一声明本次只读一次。
 *
 * @param {{path: string, sha256: string}[]} entries
 * @returns {{files: object[], excluded: Map<string,string>, problems: string[]}}
 */
export function readSourceFiles(projectRoot, entries) {
  const native = loadNative(projectRoot);
  const resolve = native.module('scripts/utils/blueprint-requirement-traceability.ts').resolveCurrentScopeSource;
  const guard = native.module('scripts/utils/project-relative-path.ts');
  const out = { files: [], excluded: new Map(), problems: [] };
  const seen = new Map();
  for (const entry of entries) {
    const key = `${entry.path}\0${entry.sha256}`;
    if (!seen.has(key)) {
      const got = {};
      if (!/^sha256:[0-9a-f]{64}$/.test(String(entry.sha256 ?? ''))) {
        got.why = `声明的摘要 ${entry.sha256 || '（空）'} 不是 sha256:<64 位十六进制>`;
      } else {
        try {
          const r = resolve(native.root, String(entry.path));
          if (r.source_sha256 === entry.sha256) {
            got.bytes = r.bytes;
            got.file = path.posix.normalize(guard.validateProjectRelativePath(native.root, String(entry.path).split('#')[0], 'source_ref'));
          } else got.why = `原始字节摘要 ${r.source_sha256} 与声明的 ${entry.sha256} 不符`;
        } catch (e) {
          got.why = String(e?.message ?? e).split(/\r?\n/)[0];
        }
      }
      seen.set(key, got);
      if (got.why) out.problems.push(`${entry.path}：${got.why}`);
    }
    const got = seen.get(key);
    if (got.bytes) out.files.push({ ...entry, file_path: got.file, bytes: got.bytes });
    else out.excluded.set(entry.path, got.why);
  }
  return out;
}

/**
 * 一版冻结输入：读显式给的快照（工程相对路径），files 每行换成 `<快照目录>/files/<行路径>` 与 `sha256:<行摘要>` 交 readSourceFiles。
 * 行路径要留在包内；快照读不到、不是 JSON 或没有 files 清单报问题，不当空包。快照本身的摘要由持有登记的调用方核，这里不自证版本。
 *
 * @returns {{snapshot: object|null, files: object[], excluded: Map<string,string>, problems: string[]}}
 */
export function readFrozenInputs(projectRoot, snapshotRef) {
  const native = loadNative(projectRoot);
  const out = { snapshot: null, files: [], excluded: new Map(), problems: [] };
  let at;
  try {
    at = native.module('scripts/utils/project-relative-path.ts').validateProjectRelativePath(native.root, String(snapshotRef), 'snapshot_ref');
    out.snapshot = JSON.parse(fs.readFileSync(path.join(native.root, ...at.split('/')), 'utf8'));
  } catch (e) {
    out.problems.push(`冻结快照 ${snapshotRef} 读不出来（${String(e?.message ?? e).split(/\r?\n/)[0]}）`);
    return out;
  }
  if (!Array.isArray(out.snapshot?.files)) {
    out.problems.push(`冻结快照 ${snapshotRef} 没有 files 清单`);
    return out;
  }
  const dir = path.posix.dirname(path.posix.normalize(at));
  const entries = [];
  for (const row of out.snapshot.files) {
    const name = typeof row?.path === 'string' ? path.posix.normalize(row.path) : '';
    if (!name || name === '..' || name.startsWith('../') || path.posix.isAbsolute(name)) {
      out.problems.push(`冻结快照 ${snapshotRef} 的文件行 ${JSON.stringify(row?.path)} 不在包内`);
      continue;
    }
    entries.push({ ...row, name, path: `${dir}/files/${name}`, sha256: `sha256:${row.sha256}` });
  }
  const read = readSourceFiles(projectRoot, entries);
  return { ...out, files: read.files, excluded: read.excluded, problems: [...out.problems, ...read.problems] };
}

/**
 * 施工单位关联的需求：先按原生身份认出 CU 与它的蓝图，再取 blueprintSources。
 * Story 现在是否当前，由 Story 侧按成文登记判（`design-source.mjs` 的 `storyCurrency`）。
 *
 * @param {object|null} blueprint 调用方已读到的蓝图，给了就不再读
 */
export function relatedStories(projectRoot, feature, blueprint = null) {
  const out = { status: 'ok', sources: [], requirements: [], problems: [] };
  const who = featureIdentity(projectRoot, feature);
  if (who.status !== 'ok') return { ...out, status: who.status, problems: (who.issues ?? []).map(i => i.message) };
  if (who.kind !== 'cu') return out;
  let bp = blueprint;
  if (!bp) {
    const read = readBlueprint(projectRoot, who.blueprintId, 'draft');
    if (read.status !== 'ok') return { ...out, status: read.status, problems: [`蓝图 ${who.blueprintId} 原生读取 ${read.status}——设计负责方处理`] };
    bp = read.blueprint;
  }
  return { ...blueprintSources(projectRoot, bp), blueprint: bp };
}

/**
 * 读一个原生 Feature（CU 或平铺维护 Feature）在某阶段的输入：身份与蓝图引用，加上当前阶段的原生只读解析结果。
 *
 * 范围已冻结时，按原生阶段调用的同一顺序组装入口参数、跑阶段解析器：用哪份输入、复用、过期与 invalid 全由原生定，
 * 结果原样交出（值经 SpecLoader 规范化）。无 run 的 spec 先按原生恢复并核对原始需求；有 run（`MAISON_GOAL_RUN_ID`）
 * 时范围与需求都以 run 为准，不收调用方给的需求。范围还没冻结时不解析、不代为冻结，只报 `scope: not_frozen`。
 * 只读：不写范围、报告与回执。
 *
 * `spec` 是原生检查器看到的同一份规格（`SpecLoader.loadFeatureSpec`）：冻结时由解析器选定的输入加本阶段自己的产出组成
 * （本阶段的产出按产出核，不拿上游输入顶替），没冻结时是原生按本地文件读出的规格。阶段消费者只读它，不另读文件。
 *
 * @param {{ requirement?: string, requirementFile?: string }} [supplied] 调用方手里的原始需求正文或文件，只在无 run 的 spec 用
 */
export function readFeature(projectRoot, feature, phase, supplied = {}) {
  // 同一次任务里同一个 Feature 同一阶段只解析一次：几个消费者各跑一遍原生解析器，得到的也是同一份
  const key = supplied.requirement === undefined && supplied.requirementFile === undefined
    ? `${path.resolve(projectRoot)}\0${feature}\0${phase}\0${process.env.MAISON_GOAL_RUN_ID ?? ''}` : null;
  if (key && features.has(key)) return features.get(key);
  const out = resolveFeature(projectRoot, feature, phase, supplied);
  if (key) features.set(key, out);
  return out;
}

const features = new Map();

/** 原生按阶段组装的规格里，扩展消费的那几份：契约、验收与用例（没有的为 null）。 */
const specOf = spec => ({ contracts: spec.contracts ?? null, acceptance: spec.acceptance ?? null, useCases: spec.useCases ?? null });

function resolveFeature(projectRoot, feature, phase, supplied) {
  const native = loadNative(projectRoot);
  const identity = native.module('scripts/utils/feature-identity.js');
  const { loadFrameworkConfig } = native.module('config.ts');
  let kind;
  let relPath;
  try {
    kind = identity.classifyFeatureId(feature);
    relPath = identity.featureRelativePath(feature);
  } catch (e) {
    return failure('invalid', e);
  }
  const featuresDir = loadFrameworkConfig(native.root).paths?.features_dir ?? 'doc/features';
  const featurePath = path.join(native.root, ...featuresDir.split('/'), ...String(relPath).split('/'));
  const out = {
    status: 'ok', identity: { feature, ...kind }, feature_path: rel(native.root, featurePath), phase,
    blueprint_ref: null, design_refs: [], scope: 'not_frozen', assurance: null, inputs: {}, issues: [],
  };
  if (!fs.existsSync(featurePath)) {
    return { ...out, status: 'missing', issues: [{ code: 'feature_missing', message: `Feature 目录不存在：${out.feature_path}` }] };
  }
  if (kind.kind === 'cu') {
    const cuPath = native.module('scripts/utils/change-unit-path.ts');
    const bpPath = native.module('scripts/utils/component-blueprint-path.ts');
    try {
      const unit = cuPath.loadCanonicalChangeUnit(native.root, kind.blueprintId, kind.changeUnitId).changeUnit;
      bpPath.resolveComponentBlueprintRef(native.root, unit.component_blueprint_ref);
      out.blueprint_ref = unit.component_blueprint_ref;
      out.design_refs = unit.design_refs ?? [];
    } catch (e) {
      return { ...out, ...failure(e?.code === 'component_blueprint_identity_mismatch' ? 'stale' : 'invalid', e) };
    }
  }
  const goalRunId = process.env.MAISON_GOAL_RUN_ID?.trim() || undefined;
  if (goalRunId && (supplied.requirement !== undefined || supplied.requirementFile !== undefined)) {
    return { ...out, status: 'invalid', issues: [{ code: 'requirement_override', message: `run ${goalRunId} 的需求以冻结 manifest 为准，不收调用方给的需求` }] };
  }
  try {
    const { resolveEffectiveScopeSource } = native.module('scripts/utils/goal-run-creation.ts');
    const { SpecLoader } = native.module('scripts/utils/spec-loader.ts');
    if (!resolveEffectiveScopeSource(native.root, feature, goalRunId)) {
      // 范围未冻结：不选本阶段输入，只核本地已有文件的形状——坏形状不能等到冻结后才报
      const local = new SpecLoader(native.root, undefined, undefined, native.frameworkRoot).loadFeatureSpec(feature);
      out.issues.push(...(local.shape_issues ?? []).map(message => ({ code: 'feature_spec_shape', message })));
      out.spec = specOf(local);
      if (out.issues.length) out.status = 'invalid';
      return out;
    }
    out.scope = 'frozen';
    const { resolveCapabilityResolutionEntryInput } = native.module('scripts/utils/capability-resolution-entry-input.ts');
    const { resolveCapabilityInputs } = native.module('scripts/utils/capability-resolution.ts');
    const { loadFeatureTrackDecl } = native.module('scripts/utils/feature-track.ts');
    const { resolveFeatureTrack } = native.module('scripts/utils/runtime-policy.ts');
    const { resolveWorkflowSpec } = native.module('workflow-loader.ts');
    const requirement = !goalRunId && phase === 'spec'
      && resolveWorkflowSpec(native.root, { frameworkRoot: native.frameworkRoot }).schema_version === '1.2'
      ? runlessRequirement(native, feature, supplied) : {};
    const entry = resolveCapabilityResolutionEntryInput({
      frameworkRoot: native.frameworkRoot, projectRoot: native.root, feature, phase, featuresDir, goalRunId, ...requirement,
    });
    const resolution = resolveCapabilityInputs({
      frameworkRoot: native.frameworkRoot, projectRoot: native.root, feature, phase,
      track: resolveFeatureTrack(loadFeatureTrackDecl(native.root, feature)), ...entry,
    });
    out.assurance = resolution.report.assurance;
    for (const c of resolution.report.capabilities.filter(item => item.state === 'blocked')) {
      const missing = c.inputs.filter(i => i.state !== 'resolved').map(i => `${i.id}=${i.state}`).join('、');
      out.issues.push({ code: 'capability_blocked', message: `${c.id} 被原生判为缺必需输入（${missing || c.applicability_detail || '见原生报告'}）` });
    }
    const spec = resolution.inputs
      ? new SpecLoader(native.root, undefined, undefined, native.frameworkRoot).loadFeatureSpec(feature, resolution.inputs) : null;
    for (const [name, value] of Object.entries(resolution.inputs?.values ?? {})) {
      if (!['acceptance', 'contracts'].includes(name)) continue;
      out.inputs[name] = value.state === 'resolved'
        ? { state: 'resolved', binding: value.binding?.source ?? null, value: spec?.[name] ?? value.value }
        : { state: value.state, detail: value.detail };
      if (value.state === 'invalid') out.issues.push({ code: `${name}_invalid`, message: value.detail });
    }
    out.issues.push(...(spec?.shape_issues ?? []).map(message => ({ code: 'feature_spec_shape', message })));
    // 本阶段选定的契约与验收以原生解析结果为准：规格加载没带出的那一份取解析器给的值
    const chosen = name => (out.inputs[name]?.state === 'resolved' ? out.inputs[name].value ?? null : null);
    out.spec = spec ? { ...specOf(spec), contracts: spec.contracts ?? chosen('contracts'), acceptance: spec.acceptance ?? chosen('acceptance') } : null;
    out.required_outputs = resolution.inputs?.context?.required_outputs ?? [];
  } catch (e) {
    return { ...out, ...failure('invalid', e) };
  }
  if (out.assurance === 'blocked' || out.issues.length) out.status = 'invalid';
  return out;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const argv = process.argv.slice(2);
  const opt = k => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : undefined; };
  const root = opt('--project-root');
  const action = opt('--action');
  try {
    const usage = '用法：--project-root <根> --action blueprint --blueprint <id> --purpose draft|delivery [--snapshot <快照>] [--summary]'
      + ' [--report-phases <阶段,阶段>]'
      + ' | --action feature --feature <id> --phase <阶段> [--requirement-file <文件> | --requirement <原文>]'
      + ' | --action binding --component <id> --blueprint <id> | --action sources（stdin 给来源物化 JSON）'
      + ' | --action feedback --blueprint <id>（stdin 给设计评审反馈 JSON）'
      + ' | --action feedback-related --blueprint <id> --ref <反馈文件>（stdin 给 feedback_id 列表）'
      + ' | --action feature-identity --feature <逻辑 id> [--report-phases <阶段,阶段>]'
      + ' | --action phase-evidence --feature <逻辑 id> --phases <有序阶段,阶段>'
      + ' | --action story-review-visual --feature <逻辑需求 id>'
      + ' | --action change-unit-readiness --blueprint <id> | --action change-unit-revise --blueprint <id>（stdin 给 revisions 数组）';
    const ACTIONS = ['blueprint', 'feature', 'binding', 'sources', 'feedback', 'feedback-related',
      'feature-identity', 'phase-evidence', 'story-review-visual', 'change-unit-readiness', 'change-unit-revise'];
    if (!root || !ACTIONS.includes(action)) throw new Error(usage);
    if (['change-unit-readiness', 'change-unit-revise'].includes(action) && !opt('--blueprint')) throw new Error(usage);
    if (['feature-identity', 'phase-evidence', 'story-review-visual'].includes(action) && !opt('--feature')) throw new Error(usage);
    if (action === 'phase-evidence' && !String(opt('--phases') ?? '').trim()) throw new Error(usage);
    if (['feedback', 'feedback-related'].includes(action) && !opt('--blueprint')) throw new Error(usage);
    if (action === 'feedback-related' && !opt('--ref')) throw new Error(usage);
    if (action === 'blueprint' && (!opt('--blueprint') || !['draft', 'delivery'].includes(opt('--purpose') ?? 'draft'))) throw new Error(usage);
    if (action === 'feature' && (!opt('--feature') || !opt('--phase'))) throw new Error(usage);
    const summary = argv.includes('--summary');
    if (summary && action !== 'blueprint') throw new Error(usage);
    const phases = opt('--report-phases') === undefined ? null : [...new Set(opt('--report-phases').split(',').map(s => s.trim()).filter(Boolean))];
    if (phases && (!['blueprint', 'feature-identity'].includes(action) || !phases.length)) throw new Error(usage);
    if (action === 'binding' && (!opt('--component') || !opt('--blueprint'))) throw new Error(usage);
    let doc;
    if (['sources', 'feedback', 'feedback-related', 'change-unit-revise'].includes(action)) {
      try {
        doc = JSON.parse(fs.readFileSync(0, 'utf8'));
      } catch (e) {
        throw new Error(`stdin 不是 JSON（${e?.message ?? e}）`);
      }
    }
    const out = action === 'blueprint' ? readBlueprint(root, opt('--blueprint'), opt('--purpose') ?? 'draft', opt('--snapshot'), phases)
      : action === 'binding' ? checkBinding(root, opt('--component'), opt('--blueprint'))
        : action === 'sources' ? checkSources(root, doc)
          : action === 'feedback' ? checkFeedback(root, opt('--blueprint'), doc)
            : action === 'feedback-related' ? feedbackRelated(root, opt('--blueprint'), opt('--ref'), doc)
              : action === 'feature-identity' ? featureIdentityReport(root, opt('--feature'), phases)
                : action === 'story-review-visual' ? storyReviewVisual(root, opt('--feature'))
                : action === 'phase-evidence' ? phaseEvidence(root, opt('--feature'), opt('--phases').split(',').map(s => s.trim()).filter(Boolean))
                  : action === 'change-unit-readiness' ? changeUnitReadiness(root, opt('--blueprint'))
                    : action === 'change-unit-revise' ? changeUnitRevise(root, opt('--blueprint'), doc)
          : readFeature(root, opt('--feature'), opt('--phase'), { requirement: opt('--requirement'), requirementFile: opt('--requirement-file') });
    const { blueprint, ...status } = out;
    process.stdout.write(`${JSON.stringify(summary ? status : out, null, 1)}\n`);
    process.exitCode = out.status === 'ok' ? 0 : 1;
  } catch (e) {
    process.stderr.write(`[framework-access] ${e?.message ?? e}\n`);
    process.exitCode = 2;
  }
}
