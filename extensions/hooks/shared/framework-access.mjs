#!/usr/bin/env node
/**
 * 读 Framework 原生能力的唯一入口：从显式工程根的 `framework/harness` 加载它安装的 ts-node，
 * 再 require 原生 TypeScript 模块。不复制框架实现、不另装运行器、不从维护源码导入。
 *
 * 同一进程对同一工程根只注册一次；harness 或其依赖缺失时抛错，错误里写明缺什么、怎么装。
 *
 * 命令行只读取、不写盘：
 *   node framework-access.mjs --project-root <根> --action blueprint --blueprint <id> --purpose draft|delivery
 *   node framework-access.mjs --project-root <根> --action feature --feature <原生 id> --phase <阶段>
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

/**
 * 读蓝图：draft 可返回未准入草稿与原生 issues，delivery 要求已准入。
 * 前后两次读到的字节不同（期间被改写）报 stale，不消费混合对象。
 */
export function readBlueprint(projectRoot, blueprintId, purpose = 'draft') {
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
  };
  if (purpose === 'delivery' && !admitted) out.status = 'not_admitted';
  return out;
}

/**
 * 读一个原生 Feature（CU 或平铺维护 Feature）在某阶段的输入：身份与蓝图引用，加上当前阶段的原生只读解析结果。
 *
 * 范围已冻结时，按原生阶段调用的同一顺序组装入口参数、跑阶段解析器：用哪份输入、复用、过期与 invalid 全由原生定，
 * 结果原样交出（值经 SpecLoader 规范化）。范围还没冻结时不解析、不代为冻结，只报 `scope: not_frozen`。
 * 只读：不写范围、报告与回执。
 */
export function readFeature(projectRoot, feature, phase) {
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
  try {
    const { resolveEffectiveScopeSource } = native.module('scripts/utils/goal-run-creation.ts');
    const { SpecLoader } = native.module('scripts/utils/spec-loader.ts');
    if (!resolveEffectiveScopeSource(native.root, feature)) {
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
    const entry = resolveCapabilityResolutionEntryInput({
      frameworkRoot: native.frameworkRoot, projectRoot: native.root, feature, phase, featuresDir,
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
    const usage = '用法：--project-root <根> --action blueprint --blueprint <id> --purpose draft|delivery | --action feature --feature <id> --phase <阶段>';
    if (!root || !['blueprint', 'feature'].includes(action)) throw new Error(usage);
    if (action === 'blueprint' && (!opt('--blueprint') || !['draft', 'delivery'].includes(opt('--purpose') ?? 'draft'))) throw new Error(usage);
    if (action === 'feature' && (!opt('--feature') || !opt('--phase'))) throw new Error(usage);
    const out = action === 'blueprint'
      ? readBlueprint(root, opt('--blueprint'), opt('--purpose') ?? 'draft')
      : readFeature(root, opt('--feature'), opt('--phase'));
    process.stdout.write(`${JSON.stringify(out, null, 1)}\n`);
    process.exitCode = out.status === 'ok' ? 0 : 1;
  } catch (e) {
    process.stderr.write(`[framework-access] ${e?.message ?? e}\n`);
    process.exitCode = 2;
  }
}
