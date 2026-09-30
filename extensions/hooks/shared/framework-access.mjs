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
 *   node framework-access.mjs --project-root <根> --action feature --feature <原生 id> --phase <阶段>
 *        [--requirement-file <文件> | --requirement <原文>]（无 run 的 spec 恢复不出需求来源时给）
 *   node framework-access.mjs --project-root <根> --action binding --component <组件 id> --blueprint <蓝图 id>
 *   node framework-access.mjs --project-root <根> --action sources  < 来源物化 JSON（stdin）
 *   node framework-access.mjs --project-root <根> --action feedback --blueprint <id>  < blueprint-review-feedback@1（stdin）
 * 输出 JSON；退出 0 正常，1 对象缺失、坏身份、过期或未准入（带原生 issues），2 参数或依赖错误。
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

/**
 * 读蓝图：draft 可返回未准入草稿与原生 issues，delivery 要求已准入。
 * 前后两次读到的字节不同（期间被改写）报 stale，不消费混合对象。
 * 给了冻结快照时一并回答 `consumption`：这一版蓝图消费了本次交给设计的条目没有。
 */
export function readBlueprint(projectRoot, blueprintId, purpose = 'draft', snapshotRef = null) {
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
    projection: readProjection(native, checked),
    ...(snapshotRef ? { consumption: scopeConsumption(native, checked.blueprint, snapshotRef) } : {}),
  };
  if (purpose === 'delivery' && !admitted) out.status = 'not_admitted';
  return out;
}

/** 蓝图旁的原生评审投影：没有、与这一版 canonical 的确定性派生对不上（stale）、有效。 */
function readProjection(native, checked) {
  const file = path.join(path.dirname(checked.canonicalPath), 'component-blueprint.review.md');
  const out = { path: rel(native.root, file) };
  if (!fs.existsSync(file)) return { ...out, status: 'missing', issues: [] };
  const issues = native.module('scripts/utils/blueprint-host-seams.ts')
    .validateBlueprintReviewPublication(fs.readFileSync(file, 'utf8'), checked.blueprint, checked.artifactSha256);
  return { ...out, status: issues.length ? 'stale' : 'valid', issues };
}

/**
 * 原生无 Feature 专项请求（`request-phase.ts` 的 `runExplicitRequest`，参数键与 `npm run check` 的命令行相同）。
 * 在本进程里调用同一份发布件，接住它写到标准输出的那一段 JSON：prepare 给请求身份与缺口，
 * 正式检查给 `{subject, request_sha256, verdict, report}`。原生抛错原样交回，不猜结果。
 *
 * @returns {Promise<{code: number, output: object|null, text: string}>}
 */
export async function explicitRequest(projectRoot, args) {
  const native = loadNative(projectRoot);
  const { runExplicitRequest } = native.module('scripts/utils/request-phase.ts');
  const printed = [];
  const log = console.log;
  console.log = (...parts) => printed.push(parts.join(' '));
  let code;
  try {
    code = await runExplicitRequest({ projectRoot: native.root, frameworkRoot: native.frameworkRoot, args });
  } finally {
    console.log = log;
  }
  const text = printed.join('\n');
  const json = text.slice(text.search(/^\{/m));
  let output = null;
  try {
    output = JSON.parse(args['prepare-request'] ? json : json.split(/\r?\n/).filter(l => l.startsWith('{')).pop());
  } catch {
    output = null;
  }
  return { code, output, text };
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
 * 核一份设计评审反馈（blueprint-review-feedback@1）：原生只判每条够不够格进入调和（授权、证据、版本、目标地址），
 * 不判接受与否。处理结果从蓝图读：某条决定的来源指向 `<反馈文件>#<feedback_id>` 才算有了可读的处理，否则待处理。
 */
function checkFeedback(projectRoot, blueprintId, doc) {
  const native = loadNative(projectRoot);
  const read = readBlueprint(projectRoot, blueprintId, 'draft');
  if (read.status !== 'ok') return { status: read.status, issues: read.issues ?? [], candidates: null, handled: {} };
  const intake = native.module('scripts/utils/blueprint-host-seams.ts').validateBlueprintReviewFeedback(doc, read.blueprint);
  const handled = {};
  for (const d of read.blueprint.decisions_and_gaps?.decisions ?? []) {
    const at = String(d?.provenance?.source_ref ?? '').split('#')[1];
    if (at) handled[at] = { decision_id: d.decision_id, status: d.status, revision: read.blueprint.revision };
  }
  return {
    status: intake.issues.some(i => i.severity === 'BLOCKER') ? 'invalid' : 'ok', issues: intake.issues,
    candidates: { rulings: intake.authoritativeRulingCandidateIds, facts: intake.factSupplementCandidateIds },
    revision: read.blueprint.revision, handled,
  };
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

/** 本阶段产物所在的目录：原生身份认不出时按目录名拼，由调用方照常报「文件不在」。 */
export function featureDir(projectRoot, feature) {
  const who = featureIdentity(projectRoot, feature);
  return who.dir ?? path.join(projectRoot, 'doc', 'features', String(feature));
}

/**
 * 读一个原生 Feature（CU 或平铺维护 Feature）在某阶段的输入：身份与蓝图引用，加上当前阶段的原生只读解析结果。
 *
 * 范围已冻结时，按原生阶段调用的同一顺序组装入口参数、跑阶段解析器：用哪份输入、复用、过期与 invalid 全由原生定，
 * 结果原样交出（值经 SpecLoader 规范化）。无 run 的 spec 先按原生恢复并核对原始需求；有 run（`MAISON_GOAL_RUN_ID`）
 * 时范围与需求都以 run 为准，不收调用方给的需求。范围还没冻结时不解析、不代为冻结，只报 `scope: not_frozen`。
 * 只读：不写范围、报告与回执。
 *
 * @param {{ requirement?: string, requirementFile?: string }} [supplied] 调用方手里的原始需求正文或文件，只在无 run 的 spec 用
 */
export function readFeature(projectRoot, feature, phase, supplied = {}) {
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
    const usage = '用法：--project-root <根> --action blueprint --blueprint <id> --purpose draft|delivery [--snapshot <快照>]'
      + ' | --action feature --feature <id> --phase <阶段> [--requirement-file <文件> | --requirement <原文>]'
      + ' | --action binding --component <id> --blueprint <id> | --action sources（stdin 给来源物化 JSON）'
      + ' | --action feedback --blueprint <id>（stdin 给设计评审反馈 JSON）';
    if (!root || !['blueprint', 'feature', 'binding', 'sources', 'feedback'].includes(action)) throw new Error(usage);
    if (action === 'feedback' && !opt('--blueprint')) throw new Error(usage);
    if (action === 'blueprint' && (!opt('--blueprint') || !['draft', 'delivery'].includes(opt('--purpose') ?? 'draft'))) throw new Error(usage);
    if (action === 'feature' && (!opt('--feature') || !opt('--phase'))) throw new Error(usage);
    if (action === 'binding' && (!opt('--component') || !opt('--blueprint'))) throw new Error(usage);
    let doc;
    if (action === 'sources' || action === 'feedback') {
      try {
        doc = JSON.parse(fs.readFileSync(0, 'utf8'));
      } catch (e) {
        throw new Error(`stdin 不是 JSON（${e?.message ?? e}）`);
      }
    }
    const out = action === 'blueprint' ? readBlueprint(root, opt('--blueprint'), opt('--purpose') ?? 'draft', opt('--snapshot'))
      : action === 'binding' ? checkBinding(root, opt('--component'), opt('--blueprint'))
        : action === 'sources' ? checkSources(root, doc)
          : action === 'feedback' ? checkFeedback(root, opt('--blueprint'), doc)
          : readFeature(root, opt('--feature'), opt('--phase'), { requirement: opt('--requirement'), requirementFile: opt('--requirement-file') });
    process.stdout.write(`${JSON.stringify(out, null, 1)}\n`);
    process.exitCode = out.status === 'ok' ? 0 : 1;
  } catch (e) {
    process.stderr.write(`[framework-access] ${e?.message ?? e}\n`);
    process.exitCode = 2;
  }
}
