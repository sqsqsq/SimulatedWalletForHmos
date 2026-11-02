#!/usr/bin/env node
/**
 * 读 Framework 原生能力的唯一入口：从显式工程根的 `framework/harness` 加载它安装的 ts-node，
 * 再 require 原生 TypeScript 模块。不复制框架实现、不另装运行器、不从维护源码导入。
 *
 * 同一进程对同一工程根只注册一次；harness 或其依赖缺失时抛错，错误里写明缺什么、怎么装。
 *
 * 命令行只读取、不写盘：
 *   node framework-access.mjs --project-root <根> --action blueprint --blueprint <id> --purpose draft|delivery
 *        [--consume <需求 id>]（给了就核蓝图的需求条目与设计依据引用了这个需求登记的材料）
 *        [--summary]（只核状态：同一读取与校验，输出省掉蓝图正文 blueprint，其余字段照旧）
 *        [--report-phases <阶段,阶段>]（给了就在每个施工单位上附原生阶段报告目录 phase_reports）
 *   node framework-access.mjs --project-root <根> --action feature --feature <原生 id> --phase <阶段>
 *        [--requirement-file <文件> | --requirement <原文>]（无 run 的 spec 恢复不出需求来源时给）
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
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import { createRequire } from 'node:module';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { markdownLinks } from '../../skills/story/scripts/core/story/markdown-links.mjs';

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

/** 证据强度的高低：蓝图声明的不能高于来源本身能证明的（人工答复是人的原话，其余材料只证明读到了这些字节）。 */
const STRENGTH = { unknown: 0, inferred: 1, observed: 2, authoritative: 3 };

/**
 * 这一版蓝图采用了这个需求的来源没有：需求条目或设计依据至少引了一份本需求登记的材料，引用落在需求目录里的都是登记文件，
 * 声明来源的原字节与声明摘要一致、采用版本的文件与登记摘要一致，条目声明的证据强度不高于来源能证明的。
 * 支撑材料不必成为需求条目；需求内容是否被设计落实、没引的材料是不是漏了，由独立质询与审查判断。
 */
function scopeConsumption(projectRoot, blueprint, requirement) {
  const adopted = adoptedSources(projectRoot, blueprint, { requirement });
  const issues = adopted.problems.map(message => ({ code: 'scope_source_invalid', message }));
  issues.push(...readSourceFiles(projectRoot, adopted.sources).problems.map(message => ({ code: 'scope_source_unreadable', message })));
  const own = adopted.requirements[0];
  issues.push(...readSourceFiles(projectRoot, [...(own?.files ?? []), ...adopted.projectFiles]).problems
    .map(message => ({ code: 'adopted_source_unreadable', message })));
  if (!own?.versions.length) {
    issues.push({ code: 'scope_item_not_consumed', message: `蓝图的需求条目与设计依据没有引用需求 ${requirement} 登记的材料` });
  } else {
    const roles = new Map(own.files.map(f => [f.path, f.role]));
    const guard = loadNative(projectRoot).module('scripts/utils/project-relative-path.ts');
    for (const s of adopted.sources) {
      let file;
      try {
        file = path.posix.normalize(guard.validateProjectRelativePath(loadNative(projectRoot).root, s.path.split('#')[0], 'source_ref'));
      } catch {
        continue;
      }
      if (!roles.has(file)) continue;
      const most = roles.get(file) === 'answer' ? 'authoritative' : 'observed';
      if ((STRENGTH[s.provenance?.evidence_strength] ?? 0) > STRENGTH[most]) {
        issues.push({ code: 'scope_item_not_consumed', item_id: s.item_id,
          message: `条目 ${s.item_id} 声明为 ${s.provenance?.evidence_strength}，来源 ${file} 只能证明 ${most}` });
      }
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
 * 同一进程里同一次读取只真做一次：按参数与输入文件的状态（蓝图目录逐个文件、材料索引）记下结果，状态没变就给一份副本，
 * 进程里写过它们状态就变、重新读取。只在内存，进程结束即无；返回副本，调用方改了也不影响别处。
 */
const readMemo = new Map();

function inputsStamp(projectRoot, requirement) {
  const native = loadNative(projectRoot);
  const dir = native.module('config.ts').loadFrameworkConfig(native.root).paths?.features_dir ?? 'doc/features';
  const root = path.join(native.root, ...String(dir).split(/[\\/]/).filter(Boolean), String(requirement));
  const files = [];
  const walk = (d) => {
    let entries = [];
    try { entries = fs.readdirSync(d, { withFileTypes: true }); } catch { return; }
    for (const e of entries) (e.isDirectory() ? walk(path.join(d, e.name)) : files.push(path.join(d, e.name)));
  };
  walk(path.join(root, 'blueprint'));
  files.push(path.join(root, 'AR', 'story-src', 'materials.json'));
  return files.sort().map((f) => {
    try { const s = fs.statSync(f); return `${f}:${s.size}:${s.mtimeMs}`; } catch { return `${f}:-`; }
  }).join('|');
}

function memoized(key, stamp, read) {
  const hit = readMemo.get(key);
  if (hit && hit.stamp === stamp) return structuredClone(hit.value);
  const value = read();
  readMemo.set(key, { stamp, value });
  return structuredClone(value);
}

/**
 * 读蓝图：draft 可返回未准入草稿与原生 issues，delivery 要求已准入。
 * 前后两次读到的字节不同（期间被改写）报 stale，不消费混合对象。
 * 给了需求 id 时一并回答 `consumption`：这一版蓝图的需求条目与设计依据引用了这个需求登记的材料没有。
 * 已准入时列出活动施工单位 `units`（原生枚举、去掉已被取代的）：身份、Feature 标识与原生目录（工程相对）；
 * 给了 `reportPhases` 时每个单位另带 `phase_reports: [{phase, dir}|{phase, error}]`（phaseReportsDir 的原生结果）。
 */
export function readBlueprint(projectRoot, blueprintId, purpose = 'draft', consume = null, reportPhases = null) {
  return memoized(JSON.stringify(['blueprint', path.resolve(projectRoot), blueprintId, purpose, consume, reportPhases]),
    inputsStamp(projectRoot, blueprintId), () => readBlueprintNow(projectRoot, blueprintId, purpose, consume, reportPhases));
}

function readBlueprintNow(projectRoot, blueprintId, purpose, consume, reportPhases) {
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
    ...(consume ? { consumption: scopeConsumption(projectRoot, checked.blueprint, consume) } : {}),
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
 * 核一份来源物化（requirement-source-materialization@1 形状）：原生校验信封、项目内 source_ref、原始字节摘要、
 * provenance 与 authority。系统来源的物化信封落在需求的 `blueprint/` 里；本地来源不另造 provider manifest。
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
 * Feature 此刻的当前处置（只读）：原生 `readCurrentDispositionInput` 组装本次责任链的当前事实（summary、检查、必需缺口、
 * 证据新鲜度、债务与已登记发现），`resolveCurrentDisposition` 分成阻断完成、阻断发布与可披露三类，并给出普通完成与发布资格。
 * `chain` 只放本次要问的阶段，不固定六阶段；不传 run，不写任何东西、不启动 readiness 之类有副作用的动作。
 * 历史闭环（summary 的 closure）由调用方另列，这里只答「现在」。
 */
function currentDisposition(projectRoot, feature, chain) {
  const native = loadNative(projectRoot);
  try {
    const input = native.module('scripts/utils/verify-feature-completion.ts')
      .readCurrentDispositionInput({ projectRoot: native.root, frameworkRoot: native.frameworkRoot, feature, chain });
    const got = native.module('scripts/utils/check-disposition.ts').resolveCurrentDisposition(input);
    const row = x => ({ phase: x.phase, id: x.id, action: x.action, affects: x.affects, severity: x.severity,
      owner: x.owner ?? x.phase, detail: x.detail });
    return { status: 'ok', feature, chain, completion_eligible: got.completionEligible, release_ready: got.releaseReady,
      completion_blocking: got.completionBlocking.map(row), release_blocking: got.releaseBlocking.map(row),
      disclosed: got.disclosed.map(row), reasons: got.reasons, issues: [] };
  } catch (e) {
    return failure('invalid', e);
  }
}

/**
 * 独立 Story 审查的视觉裁定：取与需求同根的蓝图（标识就是需求标识）与它采用的本需求来源，按原生纯函数算看图能力与保真路由。
 *
 * - 需求原文取采用版本里的阅读正文（`text`、会议阅读件 `evidence`，图片与二进制原件不算）与必读人答（`answer`），Story、写作设计不进；
 *   取不到时说明来源不足，不拿作者摘要补。
 * - 执行身份是 `story:<需求>:<蓝图>:<revision>:<artifact_sha256>`，需求摘要用采用来源的身份 `sourcesIdentity`；
 *   能力取原生当前 adapter 的图像输入解析与 profile 的 OCR 就绪，审查者与作者同一执行能力（`reviewVision = hasVision`）。
 * - `deferral` 只在明确看不了图、原生 effective 是 semantic_layout、strictness 是 best_effort 且 defer=false 时为真：
 *   这时登记图片的图面未核可以按能力缺口记 WARN；其余情况看不了图就是没读完。
 * 只读，不调模型、不探测、不写裁定文件。
 */
export function storyReviewVisual(projectRoot, feature) {
  const native = loadNative(projectRoot);
  const id = featureIdentity(projectRoot, feature);
  if (id.status !== 'ok' || !id.dir) return { status: 'invalid', issues: id.issues ?? [] };
  const blueprintId = feature;
  const read = readBlueprint(projectRoot, blueprintId, 'draft');
  if (read.status !== 'ok') return { status: read.status, issues: read.issues ?? [] };
  const adopted = adoptedSources(projectRoot, read.blueprint, { requirement: feature });
  const own = adopted.requirements[0];
  if (adopted.problems.length) return { status: 'invalid', issues: adopted.problems.map(message => ({ code: 'adopted_source_invalid', message })) };
  if (!own?.versions.length) {
    return { status: 'invalid', issues: [{ code: 'story_design_input_missing', message: '蓝图没有引用本需求的来源：视觉裁定无从取来源' }] };
  }
  const files = readSourceFiles(projectRoot, [...own.files, ...own.answers].filter(f => ['text', 'evidence', 'answer'].includes(f.role)));
  if (files.problems.length) return { status: 'invalid', issues: files.problems.map(message => ({ code: 'adopted_source_invalid', message })) };
  const texts = files.files.map(f => `<<${f.path}>>
${Buffer.from(f.bytes).toString('utf8')}`);
  if (!files.files.some(f => f.role === 'text')) {
    return { status: 'invalid', issues: [{ code: 'requirement_text_missing', message: '采用的来源里没有需求阅读原文：来源不足，视觉裁定不做' }] };
  }
  const sourcesSha = sourcesIdentity([...adopted.sources, ...own.files, ...adopted.projectFiles, ...own.answers]);
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
    requirementText: texts.join('\n\n'), requirementSha: sourcesSha, executionIdentity,
    capability: { hasVision, ocrAvailable, reviewVision: hasVision },
  });
  const deferral = !hasVision && routing.effective === 'semantic_layout' && routing.strictness === 'best_effort' && routing.defer === false;
  const fact = `看图能力：${hasVision ? '能看图' : '看不了图'}（adapter ${probe?.adapter ?? adapter ?? '未配置'}，${probe?.reason ?? '无说明'}；OCR ${ocrAvailable ? '就绪' : '不可用'}）；`
    + `原生保真路由 effective=${routing.effective}、strictness=${routing.strictness}、defer=${routing.defer}（决定 ${routing.decision?.decision_id ?? '—'}）`;
  return { status: 'ok', issues: [], blueprint_ref: ref, sources_sha256: sourcesSha,
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

/** 需求材料索引：`files` 视图（相对需求目录的路径 → 来源、版本、角色、完整摘要）与来源版本。读不出为 null。 */
function requirementIndex(native, root) {
  let index;
  try {
    index = JSON.parse(fs.readFileSync(path.join(native.root, ...root.split('/'), 'AR', 'story-src', 'materials.json'), 'utf8'));
  } catch {
    return null;
  }
  if (!Array.isArray(index?.files) || !Array.isArray(index?.sources)) return null;
  return index;
}

/** 一行登记文件换成工程相对路径与 `sha256:<64 位>`。 */
const fileOf = (root, row) => ({ path: `${root}/${row.path}`, sha256: `sha256:${row.sha256}`, role: row.role,
  source_id: row.source_id, version: row.version, kind: row.kind, dir: row.dir });

/** Markdown 正文里的本地链接与图片目标（相对它自己），按 `markdownLinks` 的完整目标读法；外部链接与文内锚点不算。 */
function localTargets(text, fromDir) {
  const out = [];
  for (const line of String(text).split(/\r?\n/)) {
    for (const { target } of markdownLinks(line).links) {
      if (!target || /^[a-z][a-z0-9+.-]*:/i.test(target) || /^[#/]/.test(target)) continue;
      let file;
      try { file = decodeURIComponent(target.split(/[?#]/)[0]); } catch { continue; }
      if (file) out.push(path.posix.normalize(path.posix.join(fromDir, file)));
    }
  }
  return out;
}

/** 来源引用连同它在蓝图里的位置：provenance 取 source_ref（原生 validateOwnedCollections 覆盖的各集合，含合同对象自身）；
 * 合同各段直接带 source_ref。 */
function refsOf(blueprint) {
  const support = [];
  const conflicts = [];
  const put = (list, ref, where, provenance = null) => {
    if (typeof ref === 'string' && ref.trim()) list.push({ path: ref.trim(), where, provenance });
  };
  const prov = (list, obj, where) => put(list, obj?.provenance?.source_ref, where, obj?.provenance ?? null);
  prov(support, blueprint, 'provenance');
  (blueprint?.discovery?.facts ?? []).forEach((f, i) => prov(support, f, `discovery.facts[${f?.fact_id ?? i}]`));
  (blueprint?.design_views ?? []).forEach((v, i) => {
    (v?.nodes ?? []).forEach((n, j) => prov(support, n, `design_views[${v?.view_id ?? i}].nodes[${n?.node_id ?? j}]`));
    (v?.runtime_data_flows ?? []).forEach((n, j) => prov(support, n, `design_views[${v?.view_id ?? i}].runtime_data_flows[${j}]`));
  });
  (blueprint?.relations ?? []).forEach((r, i) => prov(support, r, `relations[${r?.relation_id ?? i}]`));
  for (const key of ['decisions', 'gaps']) {
    (blueprint?.decisions_and_gaps?.[key] ?? []).forEach((d, i) =>
      prov(support, d, `decisions_and_gaps.${key}[${d?.decision_id ?? d?.gap_id ?? i}]`));
  }
  (blueprint?.contracts ?? []).forEach((c, i) => {
    const id = c?.contract_id ?? i;
    prov(support, c, `contracts[${id}]`);
    const parts = [['operation', c?.operation], ['request_dto', c?.request_dto], ['response_dto', c?.response_dto],
      ...(c?.request_dto?.fields ?? []).map((f, j) => [`request_dto.fields[${j}]`, f]),
      ...(c?.response_dto?.fields ?? []).map((f, j) => [`response_dto.fields[${j}]`, f]),
      ...(c?.mappings ?? []).map((m, j) => [`mappings[${j}]`, m]),
      ['errors', c?.errors], ['idempotency', c?.idempotency], ['nfr', c?.nfr]];
    for (const [at, part] of parts) put(support, part?.source_ref, `contracts[${id}].${at}`);
  });
  (blueprint?.discovery?.conflicts ?? []).forEach((c, i) => {
    prov(conflicts, c, `discovery.conflicts[${i}]`);
    (c?.sources ?? []).forEach((s, j) => (typeof s === 'string'
      ? put(conflicts, s, `discovery.conflicts[${i}].sources[${j}]`)
      : put(conflicts, s?.source_ref ?? s?.provenance?.source_ref, `discovery.conflicts[${i}].sources[${j}]`)));
  });
  return { support, conflicts };
}

/**
 * 蓝图实际依据的来源与本需求的采用版本 —— 真实需求条目、支撑依据、冲突核源与必读人答各自分开，不保存第二份采用清单。
 *
 * - `sources`：原生 `currentScopeItems` 的声明（原引用连同片段、声明摘要、条目身份与 provenance）——真实需求、目标、约束与风险；
 * - `support`：蓝图根、`discovery.facts`、设计视图节点与运行数据流、关系、决定与缺口的 provenance，以及合同各段的 `source_ref`；
 *   说明文字、reader_guide 指针、示例与被否方案里的同名字段不算；
 * - `conflicts`：`discovery.conflicts` 引的来源，供核源，不算已采用；
 * - 需求 `requirement`（默认蓝图标识，蓝图与需求同根）的材料索引 `files` 视图登记的稳定文件：被上面三类引用命中的来源版本
 *   就是采用的版本，按版本展开成全部文件（原件、阅读稿、图、会议的 raw/纠偏/阅读件），聚合稿按它那一版固定的组成展开，
 *   Markdown 阅读稿引的登记文件一并加入；图是资源叶子，只取被引的那一份。引用会换版的当前位置（带 `reference` 的别名行）
 *   不算依据，报出它此刻对应的稳定文件；几个版本共用的留存按 provenance 的 `source_revision` 认版本，认不出就报候选；
 *   最新一版人工答复作为独立必读（`answers`），不取决于有没有被引用。
 * - `projectFiles`：支撑与冲突依据引用的需求目录以外的工程文件，按原生来源解析（片段要在文件里）读出原始字节摘要，
 *   作为设计来源身份的一部分交给读者；引用不是工程内现存文件的（原生合法的非文件出处）按原生合同保留在 `support`，不当材料。
 * 支撑与冲突引用带片段时按原生来源解析核片段。引用落在需求目录里、却不是登记文件的（含冲突依据），逐条报出，不静默过滤。
 * 采用版本的 Markdown 阅读稿链到的登记文件，连同它所在的整个版本一起加入，沿着读下去它的图也在。
 *
 * @returns {{status: string, sources: object[], support: object[], conflicts: object[], projectFiles: object[],
 *   requirements: {requirement: string, root: string, versions: string[], files: object[], answers: object[], conflictFiles: object[]}[],
 *   problems: string[]}}
 */
export function adoptedSources(projectRoot, blueprint, { requirement = blueprint?.blueprint_id } = {}) {
  const key = JSON.stringify(['adopted', path.resolve(projectRoot), requirement, crypto.createHash('sha256').update(JSON.stringify(blueprint ?? null)).digest('hex')]);
  return memoized(key, inputsStamp(projectRoot, requirement), () => adoptedSourcesNow(projectRoot, blueprint, requirement));
}

function adoptedSourcesNow(projectRoot, blueprint, requirement) {
  const native = loadNative(projectRoot);
  const out = { status: 'ok', sources: [], support: [], conflicts: [], projectFiles: [], requirements: [], problems: [] };
  const featuresDir = native.module('config.ts').loadFrameworkConfig(native.root).paths?.features_dir ?? 'doc/features';
  const guard = native.module('scripts/utils/project-relative-path.ts');
  const root = `${path.posix.normalize(featuresDir)}/${requirement}`;
  const fileAt = (ref) => {
    try {
      return path.posix.normalize(guard.validateProjectRelativePath(native.root, String(ref ?? '').split('#')[0], 'source_ref'));
    } catch {
      return null;
    }
  };
  for (const item of native.module('scripts/utils/blueprint-requirement-traceability.ts').currentScopeItems(blueprint)) {
    if (!fileAt(item.source_ref)) {
      out.problems.push(`蓝图条目 ${item.item_id} 的来源 ${item.source_ref} 不是工程内路径——设计负责方处理`);
      continue;
    }
    out.sources.push({ path: String(item.source_ref), sha256: String(item.source_sha256 ?? ''), item_id: String(item.item_id),
      kind: item.kind, provenance: item.provenance ?? null, where: `discovery.inputs.current_scope_items[${item.item_id}]` });
  }
  const { support, conflicts } = refsOf(blueprint);
  out.support = support;
  out.conflicts = conflicts;
  const inRoot = (file) => file && file.startsWith(`${root}/`);
  // 支撑与冲突引用按原生来源解析：片段要在文件里；需求目录以外的现存工程文件读出摘要，进来源身份
  const resolve = native.module('scripts/utils/blueprint-requirement-traceability.ts').resolveCurrentScopeSource;
  const exists = (file) => { try { return fs.statSync(path.join(native.root, ...file.split('/'))).isFile(); } catch { return false; } };
  for (const [use, list] of [['support', support], ['conflict', conflicts]]) {
    for (const r of list) {
      const file = fileAt(r.path);
      if (!file || (!inRoot(file) && !exists(file))) continue;
      try {
        const got = resolve(native.root, r.path);
        if (!inRoot(file)) out.projectFiles.push({ path: file, sha256: got.source_sha256, role: 'project_file', use, where: r.where });
      } catch (e) {
        if (exists(file)) out.problems.push(`${r.where} 引用的 ${r.path} 解析不了：${String(e?.message ?? e).split(/\r?\n/)[0]}——设计负责方按原文修正片段`);
      }
    }
  }
  const index = requirementIndex(native, root);
  const cited = [...out.sources, ...support].map(r => ({ ...r, file: fileAt(r.path) }));
  if (!index) {
    if (cited.some(r => inRoot(r.file))) out.problems.push(`需求 ${requirement} 的材料索引读不出来（或不是本版带 files 视图的索引）——重跑 \`story_flow.py round\` 重建`);
    return out;
  }
  // 同一路径可以是几个来源版本共用的留存（同字节的原件、共享的图）：按路径分组，不让最后一行盖掉来源身份
  const versionKey = r => `${r.source_id}@${r.version}`;
  const rows = new Map();
  for (const r of index.files) {
    const at = `${root}/${r.path}`;
    const group = rows.get(at) ?? [];
    if (!group.some(x => versionKey(x) === versionKey(r))) group.push(r);
    rows.set(at, group);
  }
  const stable = index.files.filter(r => !r.reference);
  const isImage = group => group.every(r => r.role === 'image');
  const versionOf = r => (index.sources ?? []).find(s => s?.source_id === r.source_id)?.versions?.find(x => x?.version === r.version);
  const reading = (r) => {
    const v = versionOf(r);
    return `${root}/${(v?.readable ?? v?.original)?.path ?? r.path}`;
  };
  // 图作资源叶子：只取这份文件，不声称采用了含它的版本；单独一份界面图本身就是一个来源版本，引它就是采用它
  const leaf = group => ({ ...fileOf(root, group[0]), dir: null, ...(group.length > 1 ? { source_id: null, version: null } : {}) });
  const ownImage = group => group.length === 1 && versionOf(group[0])?.original?.path === group[0].path;
  // 一处引用落到哪个来源版本：当前位置（别名）不是依据，报出对应的稳定文件；几个版本共用的留存按 provenance 写明的版本认，
  // 认不出就列候选阅读稿；图是资源叶子，只取这份文件、不把含它的版本都算采用
  const leaves = new Map();
  const pick = (r, file, label) => {
    const group = rows.get(file);
    if (!group) {
      out.problems.push(`${r.where} 引用的${label} ${file} 不是需求 ${requirement} 材料索引登记的文件（不在或没导入）——设计负责方按材料索引 files 同步`);
      return null;
    }
    const alias = group.find(x => x.reference);
    if (alias) {
      out.problems.push(`${r.where} 引用的${label} ${file} 是会换版的当前位置，不是依据：它此刻对应 ${root}/${alias.reference.path}`
        + `（${versionKey(alias)}）——设计负责方把引用改成这份稳定文件`);
      return null;
    }
    if (isImage(group) && !ownImage(group)) {
      if (!leaves.has(file)) leaves.set(file, leaf(group));
      return null;
    }
    const named = String(r.provenance?.source_revision ?? '');
    const hit = group.length === 1 ? group[0] : group.find(x => `${x.source_id}@v${x.version}` === named);
    if (!hit) {
      out.problems.push(`${r.where} 引用的${label} ${file} 是 ${group.map(versionKey).join('、')} 共用的留存，认不出是哪一版`
        + `——设计负责方改引那一版的阅读稿：${[...new Set(group.map(reading))].join('、')}`);
      return null;
    }
    return versionKey(hit);
  };
  const adopted = new Set();
  const conflicted = new Set();
  for (const r of cited) {
    if (!inRoot(r.file)) continue;
    const key = pick(r, r.file, '');
    if (key) adopted.add(key);
  }
  for (const r of conflicts) {
    const file = fileAt(r.path);
    if (!inRoot(file)) continue;
    const key = pick(r, file, '冲突依据');
    if (key) conflicted.add(key);
  }
  // 版本展开：只取稳定行。聚合稿按它这一版固定的组成展开；阅读稿链到的登记文件连同它的整个版本加入（图只取那一份），
  // 新加入的阅读稿接着读，直到没有新版本。阅读稿链到会换版的当前位置是生产缺口，报出来
  const expand = (seed, use) => {
    const keys = new Set(seed);
    const queue = [...keys];
    const files = [];
    while (queue.length) {
      const key = queue.shift();
      for (const r of stable.filter(x => versionKey(x) === key)) {
        const f = fileOf(root, r);
        files.push(f);
        for (const c of r.components ?? []) {
          const k = String(c);
          if (!keys.has(k)) { keys.add(k); queue.push(k); }
        }
        if (f.role !== 'text' || !/\.md$/i.test(f.path)) continue;
        let text;
        try { text = fs.readFileSync(path.join(native.root, ...f.path.split('/')), 'utf8'); } catch { continue; }
        for (const target of localTargets(text, path.posix.dirname(f.path))) {
          const group = rows.get(target);
          if (!group) continue;
          if (group.some(x => x.reference)) {
            if (use) out.problems.push(`${f.path} 链到会换版的当前位置 ${target}：稳定阅读稿要链当时那一份，重跑导入改写`);
            continue;
          }
          if (isImage(group)) {
            if (!files.some(x => x.path === target) && !leaves.has(target)) leaves.set(target, leaf(group));
            continue;
          }
          for (const row of group) {
            if (!keys.has(versionKey(row))) { keys.add(versionKey(row)); queue.push(versionKey(row)); }
          }
        }
      }
    }
    return files;
  };
  const files = expand(adopted, true);
  for (const [file, f] of leaves) if (!files.some(x => x.path === file)) files.push(f);
  const answers = (() => {
    const mine = (index.sources ?? []).find(s => s?.kind === 'answer');
    const last = mine?.versions?.at(-1);
    return last ? index.files.filter(r => r.source_id === mine.source_id && r.version === last.version).map(r => fileOf(root, r)) : [];
  })();
  out.requirements.push({ requirement, root,
    versions: [...new Set(files.map(f => f.dir).filter(Boolean))].sort(), files, answers,
    conflictFiles: expand(new Set([...conflicted].filter(k => !adopted.has(k))), false) });
  return out;
}

/** 设计来源的身份：给定的 [来源, 摘要] 去重排序后的 SHA-256。成文登记与视觉裁定传「采用来源＋必读人答」，按它认依据换没换。 */
export function sourcesIdentity(sources) {
  const rows = [...new Map(sources.map(s => [`${s.path}\0${s.sha256}`, [String(s.path), String(s.sha256)]])).values()]
    .sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0));
  return crypto.createHash('sha256').update(JSON.stringify(rows)).digest('hex');
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
 * 施工单位关联的需求：先按原生身份认出 CU 与它的蓝图，再取 adoptedSources。
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
  return { ...adoptedSources(projectRoot, bp), blueprint: bp };
}

/**
 * 一个 Feature 此刻的实际实现文件：原生 `diff-scope.implementationFiles` 合并契约预测的引用与有效基线以来的实际源码变更，
 * 只取现存文件；预测只是线索，不是写授权。`baseline` 是同一输入的原生基线结论（基线可得且原生比得出实际变更）：
 * 不可得时集合只剩预测引用，
 * 缺实体、没有调用这类要靠完整实际变更才下得了的结论不能下。
 *
 * runId 只用于这个 Feature：调用方给的阶段上下文优先，其次原生 harness 给当前阶段注入的 `MAISON_GOAL_RUN_ID`；
 * 都没有按原生无 run 基线读，不去找最近的 run。
 */
export function implementationInputs(projectRoot, feature, predicted, modules = [], runId = undefined) {
  const native = loadNative(projectRoot);
  const run = runId || process.env.MAISON_GOAL_RUN_ID?.trim() || undefined;
  const git = native.module('scripts/utils/git-diff.ts');
  let baseline;
  try {
    baseline = git.resolveEffectiveDiffBaseline(native.root, feature, run);
    // 基线可得还要比得出来（不是 git 仓库、基线提交不可达时原生比不出实际变更）
    const diff = baseline.available ? git.diffChangedFilesWithStatus({ projectRoot: native.root, baseRef: baseline.baseSha }) : null;
    if (diff && !diff.executed) baseline = { available: false, reason: diff.error ?? '实际变更比不出来' };
  } catch (e) {
    baseline = { available: false, reason: e?.message ?? String(e) };
  }
  const files = native.module('scripts/utils/diff-scope.ts').implementationFiles(native.root, feature, { files: predicted, modules }, run);
  return { files, baseline: baseline.available ? { available: true, source: baseline.source ?? null }
    : { available: false, reason: baseline.reason ?? '原生没有给出原因' } };
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
    const usage = '用法：--project-root <根> --action blueprint --blueprint <id> --purpose draft|delivery [--consume <需求 id>] [--summary]'
      + ' [--report-phases <阶段,阶段>]'
      + ' | --action feature --feature <id> --phase <阶段> [--requirement-file <文件> | --requirement <原文>]'
      + ' | --action sources（stdin 给来源物化 JSON）'
      + ' | --action feedback --blueprint <id>（stdin 给设计评审反馈 JSON）'
      + ' | --action feedback-related --blueprint <id> --ref <反馈文件>（stdin 给 feedback_id 列表）'
      + ' | --action feature-identity --feature <逻辑 id> [--report-phases <阶段,阶段>]'
      + ' | --action phase-evidence --feature <逻辑 id> --phases <有序阶段,阶段>'
      + ' | --action disposition --feature <逻辑 id> --phases <有序阶段,阶段>'
      + ' | --action story-review-visual --feature <逻辑需求 id>'
      + ' | --action change-unit-readiness --blueprint <id> | --action change-unit-revise --blueprint <id>（stdin 给 revisions 数组）';
    const ACTIONS = ['blueprint', 'feature', 'sources', 'feedback', 'feedback-related',
      'feature-identity', 'phase-evidence', 'disposition', 'story-review-visual', 'change-unit-readiness', 'change-unit-revise'];
    if (!root || !ACTIONS.includes(action)) throw new Error(usage);
    if (['change-unit-readiness', 'change-unit-revise'].includes(action) && !opt('--blueprint')) throw new Error(usage);
    if (['feature-identity', 'phase-evidence', 'disposition', 'story-review-visual'].includes(action) && !opt('--feature')) throw new Error(usage);
    if (['phase-evidence', 'disposition'].includes(action) && !String(opt('--phases') ?? '').trim()) throw new Error(usage);
    if (['feedback', 'feedback-related'].includes(action) && !opt('--blueprint')) throw new Error(usage);
    if (action === 'feedback-related' && !opt('--ref')) throw new Error(usage);
    if (action === 'blueprint' && (!opt('--blueprint') || !['draft', 'delivery'].includes(opt('--purpose') ?? 'draft'))) throw new Error(usage);
    if (action === 'feature' && (!opt('--feature') || !opt('--phase'))) throw new Error(usage);
    const summary = argv.includes('--summary');
    if (summary && action !== 'blueprint') throw new Error(usage);
    const phases = opt('--report-phases') === undefined ? null : [...new Set(opt('--report-phases').split(',').map(s => s.trim()).filter(Boolean))];
    if (phases && (!['blueprint', 'feature-identity'].includes(action) || !phases.length)) throw new Error(usage);
    let doc;
    if (['sources', 'feedback', 'feedback-related', 'change-unit-revise'].includes(action)) {
      try {
        doc = JSON.parse(fs.readFileSync(0, 'utf8'));
      } catch (e) {
        throw new Error(`stdin 不是 JSON（${e?.message ?? e}）`);
      }
    }
    const out = action === 'blueprint' ? readBlueprint(root, opt('--blueprint'), opt('--purpose') ?? 'draft', opt('--consume'), phases)
        : action === 'sources' ? checkSources(root, doc)
          : action === 'feedback' ? checkFeedback(root, opt('--blueprint'), doc)
            : action === 'feedback-related' ? feedbackRelated(root, opt('--blueprint'), opt('--ref'), doc)
              : action === 'feature-identity' ? featureIdentityReport(root, opt('--feature'), phases)
                : action === 'story-review-visual' ? storyReviewVisual(root, opt('--feature'))
                : action === 'phase-evidence' ? phaseEvidence(root, opt('--feature'), opt('--phases').split(',').map(s => s.trim()).filter(Boolean))
                : action === 'disposition' ? currentDisposition(root, opt('--feature'), opt('--phases').split(',').map(s => s.trim()).filter(Boolean))
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
