/**
 * 用例终点的原生事实 —— 只读，给 `end_target.py` 判终点用。
 *
 * 读的是被测工程里装好的扩展（`doc/extensions/hooks/shared/framework-access.mjs`）：蓝图读取与准入、评审投影、活动施工单位，
 * 再经它加载原生模块取各施工单位的设计可施工判定与执行范围，逐阶段给出原生事实：
 * - 阶段在冻结范围的 `phase_chain` 里（要执行）：`collectCompletionEvidence`——summary 的 feature/phase 与本施工单位一致、
 *   已正式收口，质量结论 verdict 另列；`--settle` 时再按 `recomputePhaseEvidenceStaleness` 核阶段物证仍当前有效；
 * - 不在链上：本阶段拥有的义务——必需义务由 `satisfied_by` 承接时，用 `executionScopeEvidenceIssues` 核承接证据仍成立；
 *   全部不适用时如实记为不适用。
 * 不调会写文件的原生入口（如 `deriveDesignPreparationReadiness` 会先原位升版施工单位的蓝图引用、check-receipt 会写回执）。
 *
 * 用法：node observe_target.mjs <工程根> <蓝图 id> <逗号分隔的阶段，可为空> [--settle]
 */
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

/** 一个施工单位一个阶段的原生事实。 */
function phaseFacts(native, featureId, scope, phase) {
  if (scope.phase_chain.includes(phase)) {
    const { collectCompletionEvidence } = native.module('scripts/utils/phase-completion-probe.ts');
    const ev = collectCompletionEvidence(native.root, featureId, phase);
    const entry = { kind: 'executed', completion: { summary: ev.summary, closure: ev.closure, verdict: ev.verdict ?? null,
      missing: ev.missing ?? [] } };
    if (settle && ev.summary && ev.closure) {
      const { recomputePhaseEvidenceStaleness } = native.module('scripts/utils/phase-evidence-manifest.ts');
      const { computeRunRequirementSha } = native.module('scripts/utils/fidelity-shared.ts');
      const [fresh] = recomputePhaseEvidenceStaleness(native.root, featureId, [phase], { frameworkRoot: native.frameworkRoot,
        currentRequirementSha: computeRunRequirementSha(native.root, featureId, process.env.MAISON_GOAL_RUN_ID || undefined) });
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
    issues: executionScopeEvidenceIssues(native.root, featureId, scope, ids) };
}

if (read.status === 'ok' && read.admitted) {
  // 活动施工单位由扩展读蓝图时给出（原生枚举、去掉退役的）；这里补原生设计判定与执行范围上的阶段事实
  const native = access.loadNative(root);
  const cuPath = native.module('scripts/utils/change-unit-path.ts');
  const gate = native.module('scripts/utils/change-unit-design-gate.ts');
  const { resolveEffectiveScopeSource } = native.module('scripts/utils/goal-run-creation.ts');
  for (const unit of read.units ?? []) {
    const loaded = cuPath.loadCanonicalChangeUnit(native.root, blueprintId, unit.change_unit_id);
    const design = gate.validateChangeUnitDesign(native.root, loaded.changeUnit);
    const row = { change_unit_id: unit.change_unit_id, feature_id: unit.feature_id, feature_path: unit.path,
      design: { verdict: String(design.verdict), issues: (design.issues ?? []).map(i => i.id) }, scope: null, phases: {} };
    if (phases.length) {
      let source;
      try {
        source = resolveEffectiveScopeSource(native.root, unit.feature_id, process.env.MAISON_GOAL_RUN_ID || undefined);
      } catch (e) {
        row.scope = { status: 'invalid', detail: String(e?.message ?? e) };
      }
      if (source) {
        row.scope = { status: 'frozen', source: source.source, phase_chain: source.scope.phase_chain };
        for (const phase of phases) row.phases[phase] = phaseFacts(native, unit.feature_id, source.scope, phase);
      } else if (!row.scope) {
        row.scope = { status: 'not_frozen' };
      }
    }
    out.units.push(row);
  }
}
process.stdout.write(JSON.stringify(out));
