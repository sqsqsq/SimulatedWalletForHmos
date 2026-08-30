import type {
  HylyreFailureCode,
  HylyreFailureKind,
  HylyreStepResult,
  HylyreTrace,
} from '../../../profiles/hmos-app/harness/providers/device-test-run';
import type { UiSpecDoc } from './ui-spec-shared';
import {
  buildCanonicalSelectorIndex,
  canonicalSelectorCandidates,
  inferScreenIdsFromText,
  normalizePlannedStep,
} from './planned-step-normalizer';
import { extractDerivedPlanCases, parsePlannedStepsFromCell } from './derived-hylyre-plan';

export type HylyreFailureOwner = 'coding' | 'testing' | 'capability' | 'external' | 'spec_plan';
export type HylyreRepairCategory = 'coding' | 'spec' | 'plan';

export interface HylyreFailureRoute {
  caseId: string;
  stepIndex: number | null;
  failureKind: HylyreFailureKind | null;
  failureCode: HylyreFailureCode | null;
  owner: HylyreFailureOwner;
  codingCandidate: boolean;
  repairCategory?: HylyreRepairCategory;
  reason: string;
}

export interface HylyreFailureRouteContext {
  derivedMd?: string | null;
  uiSpec?: UiSpecDoc | null;
}

function evidenceRecord(step: HylyreStepResult): Record<string, unknown> | null {
  return step.evidence && typeof step.evidence === 'object' && !Array.isArray(step.evidence)
    ? step.evidence
    : null;
}

function plannedSelectorForStep(
  context: HylyreFailureRouteContext | undefined,
  caseId: string,
  stepIndex: number,
) : { selector: ReturnType<typeof normalizePlannedStep>['selector']; screenIds: string[] } | null {
  if (!context?.derivedMd) return null;
  const row = extractDerivedPlanCases(context.derivedMd)
    .find(candidate => candidate.tc_id.toUpperCase() === caseId.toUpperCase());
  if (!row) return null;
  const parsed = parsePlannedStepsFromCell(row.steps_raw);
  if (!parsed.ok || !parsed.steps[stepIndex]) return null;
  return {
    selector: normalizePlannedStep(parsed.steps[stepIndex], stepIndex).selector,
    screenIds: context.uiSpec ? inferScreenIdsFromText(row.precondition, context.uiSpec) : [],
  };
}

function inlineTargetDeclared(
  step: HylyreStepResult,
  caseId: string,
  context?: HylyreFailureRouteContext,
): boolean | null {
  const planned = plannedSelectorForStep(context, caseId, step.index);
  const selector = planned?.selector ?? null;
  if (selector && context?.uiSpec) {
    const canonical = buildCanonicalSelectorIndex(context.uiSpec);
    const candidates = canonicalSelectorCandidates(
      selector,
      canonical,
      planned?.screenIds.length === 1 ? planned.screenIds[0] : undefined,
    );
    if (selector.kind === 'by_id') return candidates.some(candidate => candidate.id === selector.value);
    if (selector.kind === 'by_text') {
      // A containing parent Text is not an interaction target. Only an
      // independently declared exact text node can authorize the coding route.
      return candidates.some(candidate => candidate.text === selector.value && candidate.hasChildren !== true);
    }
    return false;
  }
  return null;
}

function inlineTargetOwner(
  step: HylyreStepResult,
  caseId: string,
  context?: HylyreFailureRouteContext,
): { owner: HylyreFailureOwner; repairCategory?: HylyreRepairCategory } {
  const evidence = evidenceRecord(step);
  if (evidence?.dump_unavailable === true || evidence?.dump_readable === false) {
    return { owner: 'external' };
  }
  const declared = inlineTargetDeclared(step, caseId, context);
  if (declared === true || (declared === null && (evidence?.target_declared === true || evidence?.interaction_target_declared === true))) {
    return { owner: 'coding', repairCategory: 'coding' };
  }
  return { owner: 'spec_plan', repairCategory: 'spec' };
}

export function routeHylyreFailure(
  caseId: string,
  step: HylyreStepResult,
  context?: HylyreFailureRouteContext,
): HylyreFailureRoute {
  const failureKind = step.failure_kind ?? null;
  const failureCode = step.failure_code ?? null;
  const base = { caseId, stepIndex: step.index, failureKind, failureCode };
  if (
    step.status === 'failed' &&
    evidenceRecord(step)?.executed !== false &&
    step.role === 'assertion' &&
    failureKind === 'assertion' &&
    failureCode === 'assertion_mismatch'
  ) {
    return {
      ...base,
      owner: 'coding',
      codingCandidate: true,
      repairCategory: 'coding',
      reason: '已执行 assertion mismatch：进入既有 coding/product candidate 路由',
    };
  }
  if (failureKind === 'selector' && (failureCode === 'selector_not_found' || failureCode === 'selector_ambiguous')) {
    return {
      ...base,
      owner: 'testing',
      codingCandidate: false,
      reason: 'selector 失败：testing 先重派生/补消歧，不投 coding',
    };
  }
  if (failureKind === 'selector' && failureCode === 'inline_target_unresolvable') {
    const routed = inlineTargetOwner(step, caseId, context);
    return {
      ...base,
      owner: routed.owner,
      ...(routed.repairCategory ? { repairCategory: routed.repairCategory } : {}),
      codingCandidate: routed.owner === 'coding',
      reason: routed.owner === 'coding'
        ? '已声明 interaction target 但运行时未挂载：补产品 anchor'
        : routed.owner === 'external'
          ? 'dump 暂不可读：留在 testing/external'
          : '需求未定义 interaction target：回 spec/plan 补目标定义',
    };
  }
  if (failureKind === 'capability' && failureCode === 'capability_unsupported') {
    return {
      ...base,
      owner: 'capability',
      codingCandidate: false,
      reason: 'provider capability unsupported：走 capability defer，零 coding candidate',
    };
  }
  if (failureKind === 'infrastructure' && (failureCode === 'device_unavailable' || failureCode === 'driver_failure')) {
    return {
      ...base,
      owner: 'external',
      codingCandidate: false,
      reason: '设备/driver 基础设施失败：走 external/toolchain',
    };
  }
  return {
    ...base,
    owner: 'testing',
    codingCandidate: false,
    reason: 'failure_kind/failure_code 不是冻结可路由组合：testing fail-closed，不按 error 文本猜测',
  };
}

export function collectHylyreFailureRoutes(
  trace: HylyreTrace | null,
  context?: HylyreFailureRouteContext,
): HylyreFailureRoute[] {
  const out: HylyreFailureRoute[] = [];
  for (const traceCase of trace?.cases ?? []) {
    const caseId = traceCase.id.toUpperCase();
    if (!Array.isArray(traceCase.steps) || traceCase.steps.length === 0) {
      if (traceCase.status === '跳过' || traceCase.status === '阻塞') {
        out.push({
          caseId,
          stepIndex: null,
          failureKind: null,
          failureCode: null,
          owner: 'testing',
          codingCandidate: false,
          reason: 'explicit skip/unexecuted case 无 StepResult：testing-owned FAIL，零自动 coding candidate',
        });
      }
      continue;
    }
    for (const step of traceCase.steps) {
      if (step.status === 'passed') continue;
      out.push(routeHylyreFailure(caseId, step, context));
    }
  }
  return out;
}

/** Compare old telemetry only for diagnostics; it never changes the native verdict. */
export function compareNativeAndLegacyTelemetry(trace: HylyreTrace | null): string[] {
  if (!trace?.runtime_step_telemetry || trace.schema_version !== '0.3-p0') return [];
  const legacyByStep = new Map(
    trace.runtime_step_telemetry.steps.map(step => [`${step.case_id.toUpperCase()}#${step.step_index}`, step]),
  );
  const mismatches: string[] = [];
  for (const traceCase of trace.cases ?? []) {
    for (const step of traceCase.steps ?? []) {
      const legacy = legacyByStep.get(`${traceCase.id.toUpperCase()}#${step.index}`);
      if (!legacy) {
        mismatches.push(`${traceCase.id}#${step.index}：legacy telemetry 缺对应 step`);
        continue;
      }
      const nativePassed = step.status === 'passed';
      const legacyPassed = legacy.outcome === 'passed';
      if (nativePassed !== legacyPassed) {
        mismatches.push(`${traceCase.id}#${step.index}：native=${step.status}，legacy=${legacy.outcome}`);
      }
    }
  }
  return mismatches;
}
