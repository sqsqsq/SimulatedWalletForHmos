import {
  extractDerivedPlanCases,
  parsePlannedStepsFromCell,
} from './derived-hylyre-plan';
import type {
  HylyreStepResult,
  HylyreTrace,
} from '../../../profiles/hmos-app/harness/providers/device-test-run';
import type { UiSpecDoc } from './ui-spec-shared';
import {
  buildCanonicalSelectorIndex,
  canonicalSelectorCandidates,
  inferScreenIdsFromText,
  normalizePlannedStep,
  type NormalizedPlannedStep,
} from './planned-step-normalizer';

export interface RuntimeSelectorViolation {
  caseId: string;
  stepIndex: number;
  code: 'selector_not_found' | 'selector_ambiguous' | 'inline_target_unresolvable';
  message: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value));
}

function selectorCount(step: HylyreStepResult): number | null {
  return step.selector && Number.isInteger(step.selector.candidate_count)
    ? step.selector.candidate_count
    : null;
}

function isAbsenceSuccess(step: HylyreStepResult, plannedKindValue: string): boolean {
  const evidence = step.evidence;
  return plannedKindValue === 'wait_gone' &&
    step.role === 'assertion' &&
    step.status === 'passed' &&
    isRecord(evidence) &&
    evidence.assertion === 'absence' &&
    evidence.observed_present === false &&
    selectorCount(step) === 0;
}

/**
 * Runtime gate for the native selector evidence. It deliberately ignores
 * dump/cache contents and only reads StepResult selector evidence plus the
 * already-authoritative derived plan for disambiguation intent.
 */
export function evaluateRuntimeSelectorGate(
  trace: HylyreTrace | null,
  derivedMd: string,
  uiSpec?: UiSpecDoc | null,
): RuntimeSelectorViolation[] {
  if (!trace || trace.schema_version !== '0.3-p0') return [];
  const plannedByCase = new Map<string, { steps: NormalizedPlannedStep[]; screenIds: string[] }>();
  for (const row of extractDerivedPlanCases(derivedMd)) {
    const parsed = parsePlannedStepsFromCell(row.steps_raw);
    if (parsed.ok) {
      plannedByCase.set(row.tc_id.toUpperCase(), {
        steps: parsed.steps.map((step, index) => normalizePlannedStep(step, index)),
        screenIds: uiSpec ? inferScreenIdsFromText(row.precondition, uiSpec) : [],
      });
    }
  }
  const canonical = uiSpec ? buildCanonicalSelectorIndex(uiSpec) : null;
  const violations: RuntimeSelectorViolation[] = [];
  for (const traceCase of trace.cases ?? []) {
    const caseId = traceCase.id.toUpperCase();
    const plannedCase = plannedByCase.get(caseId);
    const planned = plannedCase?.steps ?? [];
    for (const step of traceCase.steps ?? []) {
      if (!step.selector) continue;
      const plannedStep = planned[step.index];
      const kind = plannedStep?.kind ?? step.kind;
      if (isAbsenceSuccess(step, kind)) continue;
      const selector = plannedStep?.selector ?? null;
      const count = selectorCount(step);
      if (count === null) {
        violations.push({
          caseId,
          stepIndex: step.index,
          code: 'selector_not_found',
          message: 'StepResult.selector.candidate_count 缺失，运行时 selector 证据拒绝通过',
        });
        continue;
      }
      if (selector?.kind === 'by_text' && selector.match && step.selector.effective_match !== selector.match) {
        violations.push({
          caseId,
          stepIndex: step.index,
          code: 'selector_not_found',
          message: `requested match=${selector.match} 未在运行时保持 effective_match=${String(step.selector.effective_match)}；禁止 exact→contains fallback`,
        });
        continue;
      }
      if (selector?.kind === 'by_text' && step.failure_code === 'inline_target_unresolvable') {
        violations.push({
          caseId,
          stepIndex: step.index,
          code: 'inline_target_unresolvable',
          message: '富文本 inline target 未解析；不得点击父 Text/Row 中心或估算坐标',
        });
        continue;
      }
      if (count === 0) {
        violations.push({
          caseId,
          stepIndex: step.index,
          code: 'selector_not_found',
          message: '运行时 selector candidate_count=0，未找到目标',
        });
        continue;
      }
      const canonicalIds = canonical && selector
        ? canonicalSelectorCandidates(
            selector,
            canonical,
            plannedCase?.screenIds.length === 1 ? plannedCase.screenIds[0] : undefined,
          ).map(node => node.id)
        : [];
      const canonicalComparable = selector?.kind === 'by_id' || selector?.kind === 'by_text';
      if (selector && canonical && canonicalComparable && canonicalIds.length === 0) {
        violations.push({
          caseId,
          stepIndex: step.index,
          code: 'selector_not_found',
          message: 'StepResult selector 未映射到计划声明的 canonical ui-spec target',
        });
        continue;
      }
      if (count > 1 && !(plannedStep?.disambiguated === true)) {
        violations.push({
          caseId,
          stepIndex: step.index,
          code: 'selector_ambiguous',
          message: `运行时 selector candidate_count=${count}>1 且计划无 index/scope/within/all 消歧`,
        });
        continue;
      }
      if (typeof step.selector.selected_id !== 'string' || !step.selector.selected_id.trim()) {
        violations.push({
          caseId,
          stepIndex: step.index,
          code: 'selector_not_found',
          message: 'StepResult.selector.selected_id 缺失，无法证明实际选中的计划 target',
        });
        continue;
      }
      if (canonical && canonicalIds.length > 0 && !canonicalIds.includes(step.selector.selected_id)) {
        violations.push({
          caseId,
          stepIndex: step.index,
          code: 'selector_not_found',
          message: `StepResult.selected_id=${step.selector.selected_id} 不属于计划 target 的 canonical IDs=[${canonicalIds.join(', ')}]`,
        });
        continue;
      }
      if (
        count === 1 &&
        selector?.kind === 'by_id' &&
        step.selector.selected_id !== selector.value
      ) {
        violations.push({
          caseId,
          stepIndex: step.index,
          code: 'selector_not_found',
          message: `计划 by_id=${selector.value} 与 StepResult.selected_id=${String(step.selector.selected_id)} 不一致`,
        });
        continue;
      }
      if (count > 1) {
        const disambiguated = Boolean(
          selector && plannedStep?.disambiguated &&
          typeof step.selector.selected_id === 'string' && step.selector.selected_id.trim() &&
          typeof step.selector.bounds === 'string' && step.selector.bounds.trim() &&
          (!canonical || canonicalIds.includes(step.selector.selected_id)),
        );
        if (!disambiguated) {
          violations.push({
            caseId,
            stepIndex: step.index,
            code: 'selector_ambiguous',
            message: `运行时 selector candidate_count=${count}>1 且无真实生效的 index/scope/within/all 消歧`,
          });
        }
      }
    }
  }
  return violations;
}
