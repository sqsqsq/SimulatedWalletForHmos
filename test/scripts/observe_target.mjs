/**
 * 用例终点的原生事实 —— 只读，给 `end_target.py` 判终点用。
 *
 * 读的是被测工程里装好的扩展（`doc/extensions/hooks/shared/framework-access.mjs`）：蓝图读取与准入、评审投影、活动施工单位，
 * 再经它加载原生模块逐施工单位取设计可施工判定与当前权威执行范围：
 * - 逐 CU 复用原生 `readFeatureFrozenScope → currentFeatureScopeTransfer → resolveEffectiveScopeSource` 取当前权威，
 *   不从 `goal-runs/` 目录名猜最新，也不用进程级全局 `MAISON_GOAL_RUN_ID` 覆盖已冻结或其他 CU；
 * - 阶段在有效 `phase_chain` 里或该权威 run 已有真实 `phase_verdict`（本次执行）：核原生报告目录里的同身份 summary
 *   （feature、phase 及 run_id 与本次权威一致）、closure_status=closed 与回执完整，综合真实 `phase_verdict` 判 verdict；
 *   `--settle` 时按 `recomputePhaseEvidenceStaleness` 核阶段物证仍当前有效；
 * - 无本次执行时：本阶段拥有的义务——必需义务由 `satisfied_by` 承接时，用 `executionScopeEvidenceIssues` 核承接证据仍成立；
 *   全部不适用时如实记为不适用。
 * 不调会写文件的原生入口（如 `deriveDesignPreparationReadiness` 会先原位升版施工单位的蓝图引用、check-receipt 会写回执）。
 *
 * 用法：node observe_target.mjs <工程根> <蓝图 id> <逗号分隔的阶段，可为空> [--settle]
 */
import * as fs from 'node:fs';
import { pathToFileURL } from 'node:url';
import * as path from 'node:path';

const [root, blueprintId, phaseList = '', flag] = process.argv.slice(2);
const settle = flag === '--settle';
const phases = phaseList.split(',').map(s => s.trim()).filter(Boolean);
const access = await import(pathToFileURL(path.join(root, 'doc', 'extensions', 'hooks', 'shared', 'framework-access.mjs')).href);

const issueText = (issues) => (issues ?? []).map(i => `${i.code ?? i.id ?? '问题'}：${i.message ?? ''}`);
const out = { blueprint_id: blueprintId, blueprint: null, units: [], problems: [] };

const read = access.readBlueprint(root, blueprintId, 'draft');
out.blueprint = { status: read.status, admitted: Boolean(read.admitted), projection: read.projection?.status ?? null,
  canonical_path: read.canonical_path ?? null, issues: issueText(read.issues) };

/**
 * 一个阶段的收口证据（只读，fail-safe）：沿 900c `check-receipt.ts` 与 `phase-closure-finalizer.ts` 核当前机器提交——
 * 原生报告目录里的 summary 身份显式吻合（feature、phase、run_id）、closure_status=closed 且机器回执状态未失败
 * （receipt_status 缺省或为 passed）；phase-completion-receipt.md 是提交后的尽力人读投影，不作为 closure 开关。
 * verdict 只记录，完成不等于通过。半写入、旧 run 串用或读不出按未完成。
 */
function completionEvidence(featureId, phase, runId) {
  const res = { summary: false, closure: false, verdict: null };
  try {
    const dir = access.phaseReportsDir(root, featureId, phase);
    const file = dir.dir ? path.join(dir.dir, 'summary.json') : null;
    if (file && fs.existsSync(file)) {
      const doc = JSON.parse(fs.readFileSync(file, 'utf-8'));
      const runMatches = runId ? doc.run_id === runId : !doc.run_id;
      res.summary = doc.phase === phase && doc.feature === featureId && runMatches;
      if (typeof doc.verdict === 'string') res.verdict = doc.verdict;
      const receiptOk = doc.receipt_status === undefined || doc.receipt_status === 'passed';
      res.closure = doc.closure_status === 'closed' && receiptOk;
    }
  } catch {
    res.summary = false; res.closure = false; res.verdict = null;
  }
  return { ...res, missing: [...(res.summary ? [] : ['summary']), ...(res.closure ? [] : ['closure_status'])] };
}

/** 逐 CU 确定用于 `resolveEffectiveScopeSource` 的 runId：优先本 CU 转交权威，不拿全局 ID 覆盖别的 CU。 */
function resolveUnitRunId(native, featureId, record, envRunId) {
  if (record) return native.currentFeatureScopeTransfer(record)?.run_id || undefined;
  if (!envRunId) return undefined;
  const runDir = path.join(access.featureDir(root, featureId), 'goal-runs', envRunId);
  return fs.existsSync(runDir) ? envRunId : undefined;
}

/** 一个施工单位一个阶段的原生事实。 */
function phaseFacts(native, featureId, scope, phase, runId, events) {
  const verdict = events.filter(e => e.type === 'phase_verdict' && e.phase === phase).at(-1);
  if (scope.phase_chain.includes(phase) || verdict) {
    const ev = completionEvidence(featureId, phase, runId);
    if (verdict && verdict.verdict !== 'PASS') ev.verdict = verdict.verdict;
    const entry = { kind: 'executed', completion: { summary: ev.summary, closure: ev.closure, verdict: ev.verdict ?? null,
      missing: ev.missing ?? [] } };
    if (settle && ev.summary && ev.closure) {
      const { recomputePhaseEvidenceStaleness } = native.module('scripts/utils/phase-evidence-manifest.ts');
      const { computeRunRequirementSha } = native.module('scripts/utils/fidelity-shared.ts');
      const [fresh] = recomputePhaseEvidenceStaleness(native.root, featureId, [phase], { frameworkRoot: native.frameworkRoot,
        ...(runId ? { runId } : {}), currentRequirementSha: computeRunRequirementSha(native.root, featureId, runId) });
      entry.freshness = { verdict: fresh?.verdict ?? 'missing', changed_paths: fresh?.changed_paths ?? [] };
    }
    return entry;
  }
  const owned = scope.obligations.filter(o => o.owner_phase === phase);
  const reused = (scope.reused_phases ?? []).find(r => r.phase === phase);
  const required = owned.filter(o => o.applicability === 'required');
  if (!required.length && !reused) {
    return owned.length ? { kind: 'not_applicable', obligations: owned.map(o => o.id) } : { kind: 'not_in_scope' };
  }
  const ids = new Set([...required.map(o => o.id), ...(reused?.obligation_ids ?? [])]);
  const { executionScopeEvidenceIssues } = native.module('scripts/utils/verify-feature-completion.ts');
  return { kind: 'satisfied', obligations: [...ids],
    unsatisfied: required.filter(o => !o.satisfied_by?.length).map(o => o.id),
    issues: executionScopeEvidenceIssues(native.root, featureId, scope, ids, runId) };
}

if (read.status === 'ok' && read.admitted) {
  // 活动施工单位由扩展读蓝图时给出（原生枚举、去掉退役的）；这里补原生设计判定与执行范围上的阶段事实
  const native = access.loadNative(root);
  const cuPath = native.module('scripts/utils/change-unit-path.ts');
  const gate = native.module('scripts/utils/change-unit-design-gate.ts');
  const { readFeatureFrozenScope, currentFeatureScopeTransfer } = native.module('scripts/utils/feature-execution-scope.ts');
  const { resolveEffectiveScopeSource, loadAuthoritativeRunEvents } = native.module('scripts/utils/goal-run-creation.ts');
  const helper = { currentFeatureScopeTransfer };
  const envRunId = process.env.MAISON_GOAL_RUN_ID?.trim() || undefined;
  for (const unit of read.units ?? []) {
    const loaded = cuPath.loadCanonicalChangeUnit(native.root, blueprintId, unit.change_unit_id);
    const design = gate.validateChangeUnitDesign(native.root, loaded.changeUnit);
    const row = { change_unit_id: unit.change_unit_id, feature_id: unit.feature_id, feature_path: unit.path,
      design: { verdict: String(design.verdict), issues: (design.issues ?? []).map(i => i.id) }, scope: null, phases: {} };
    if (phases.length) {
      let source;
      let events = [];
      try {
        const record = readFeatureFrozenScope(native.root, unit.feature_id);
        const runId = resolveUnitRunId(helper, unit.feature_id, record, envRunId);
        source = resolveEffectiveScopeSource(native.root, unit.feature_id, runId);
        if (source?.run_id) events = loadAuthoritativeRunEvents(native.root, unit.feature_id, source.run_id);
      } catch (e) {
        row.scope = { status: 'invalid', detail: String(e?.message ?? e) };
      }
      if (source && !row.scope) {
        row.scope = { status: 'frozen', source: source.source, ...(source.run_id ? { run_id: source.run_id } : {}),
          phase_chain: source.scope.phase_chain };
        for (const phase of phases) {
          row.phases[phase] = phaseFacts(native, unit.feature_id, source.scope, phase, source.run_id ?? undefined, events);
        }
      } else if (!row.scope) {
        row.scope = { status: 'not_frozen' };
      }
    }
    out.units.push(row);
  }
}
process.stdout.write(JSON.stringify(out));
