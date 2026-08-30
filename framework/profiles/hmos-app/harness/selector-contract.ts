// ============================================================================
// selector-contract.ts — 测试计划 selector 的 ui-spec 来源契约（SELECTOR-SPEC-001）
// ----------------------------------------------------------------------------
// 规则不变：运行时 dump / snapshot cache 只能**发现候选**，不能成为 selector 真值。
// 静态门只消费 canonical ui-spec；运行时 candidate_count 由 native StepResult 证明。
//
// plan e6b3f8d2 t3（撤销强制 Maison UI kit）：本模块**不再读 kit 的 block 清单**、
// 不再生成 `maison:` canonical anchor 与 child suffix 契约——那是随 kit 一并删除的
// framework 侧组件实现约定，不是宿主产品的 selector 真值。查询回归**普通 ui-spec
// node.id / text**：合法 selector = 声明在 ui-spec 里的裸 node id，或与节点 text 等值。
// 存量带 `maison:` 前缀的测试计划产物须重新生成（见 MIGRATION.md）。
// ============================================================================

import type {
  UiSpecComponentNode,
  UiSpecDoc,
  UiSpecScreen,
} from '../../../harness/scripts/utils/ui-spec-shared';
import { parsePlannedStepsFromCell, extractDerivedPlanCases } from '../../../harness/scripts/utils/derived-hylyre-plan';
import {
  buildCanonicalSelectorIndex,
  canonicalSelectorCandidates,
  inferScreenIdsFromText,
  normalizePlannedStep,
  type NormalizedPlannedSelector,
} from '../../../harness/scripts/utils/planned-step-normalizer';

export const SELECTOR_SPEC_RULE_ID = 'SELECTOR-SPEC-001';

export interface SelectorContractEntry {
  screen_id: string;
  node_id: string;
  text?: string;
  /** 同屏同 id 出现多次=repeated（纯 ui-spec 事实，供测试作者判断需不需要 scope 限定）。 */
  cardinality: 'singleton' | 'repeated';
  has_children?: boolean;
}

export interface SelectorContractViolation {
  rule_id: typeof SELECTOR_SPEC_RULE_ID;
  severity: 'BLOCKER' | 'WARN';
  tc_id: string;
  step_index: number;
  selector_kind: 'by_id' | 'by_text';
  selector: string;
  match?: 'exact' | 'contains';
  canonical_ids?: string[];
  message: string;
}

function walk(node: UiSpecComponentNode | undefined, visit: (node: UiSpecComponentNode) => void): void {
  if (!node || typeof node !== 'object') return;
  visit(node);
  for (const child of node.children ?? []) walk(child, visit);
}

function nodesOf(screen: UiSpecScreen): UiSpecComponentNode[] {
  const nodes: UiSpecComponentNode[] = [];
  walk(screen.root, node => nodes.push(node));
  return nodes;
}

export function buildSelectorContractQuery(doc: UiSpecDoc, _feature?: string): SelectorContractEntry[] {
  const entries: SelectorContractEntry[] = [];
  for (const screen of doc.screens ?? []) {
    const nodes = nodesOf(screen);
    const counts = new Map<string, number>();
    for (const node of nodes) {
      if (typeof node.id === 'string' && node.id) counts.set(node.id, (counts.get(node.id) ?? 0) + 1);
    }
    for (const node of nodes) {
      if (typeof node.id !== 'string' || !node.id) continue;
      entries.push({
        screen_id: screen.id,
        node_id: node.id,
        ...(typeof node.text === 'string' && node.text ? { text: node.text } : {}),
        cardinality: (counts.get(node.id) ?? 0) > 1 ? 'repeated' : 'singleton',
        ...(node.children && node.children.length > 0 ? { has_children: true } : {}),
      });
    }
  }
  return entries;
}

export function lintDerivedPlanSelectorContract(
  derivedMd: string,
  doc: UiSpecDoc,
  feature?: string,
): SelectorContractViolation[] {
  const query = buildSelectorContractQuery(doc, feature);
  const canonical = buildCanonicalSelectorIndex(doc);
  const violations: SelectorContractViolation[] = [];
  for (const row of extractDerivedPlanCases(derivedMd)) {
    const parsed = parsePlannedStepsFromCell(row.steps_raw);
    if (!parsed.ok) continue;
    const currentScreenIds = inferScreenIdsFromText(row.precondition, doc);
    parsed.steps.forEach((step, stepIndex) => {
      const normalized = normalizePlannedStep(step, stepIndex);
      const comparableSelectors = normalized.selectors.filter(
        (item): item is NormalizedPlannedSelector & { kind: 'by_id' | 'by_text' } =>
          item.kind === 'by_id' || item.kind === 'by_text',
      );
      for (const selector of comparableSelectors) {
        if (selector.kind === 'by_id') {
          const candidates = query.filter(entry => entry.node_id === selector.value);
          const canonicalCandidates = canonicalSelectorCandidates(
            selector,
            canonical,
            currentScreenIds.length === 1 ? currentScreenIds[0] : undefined,
          );
          const screenCount = new Set(canonicalCandidates.map(entry => entry.screenId)).size;
          if (canonicalCandidates.length === 0 || ((canonicalCandidates.length > 1 || screenCount > 1) && !normalized.disambiguated)) {
            violations.push({
              rule_id: SELECTOR_SPEC_RULE_ID,
              severity: 'BLOCKER',
              tc_id: row.tc_id,
              step_index: stepIndex,
              selector_kind: selector.kind,
              selector: selector.value,
              canonical_ids: canonicalCandidates.map(entry => entry.id),
              message: canonicalCandidates.length === 0
                ? 'by_id 不是当前 feature ui-spec 声明的组件节点 id；dump/cache 不能授权 selector'
                : 'by_id 在当前 screen/canonical ui-spec 中多映射且无 index/scope/within/all 消歧',
            });
          }
          continue;
        }

        const rawMatch = selector.match;
        if (rawMatch !== 'exact' && rawMatch !== 'contains') {
          violations.push({
            rule_id: SELECTOR_SPEC_RULE_ID,
            severity: 'BLOCKER',
            tc_id: row.tc_id,
            step_index: stepIndex,
            selector_kind: selector.kind,
            selector: selector.value,
            message: '正式 by_text selector 必须显式声明 match=exact|contains；不能使用 Hylyre 默认值或运行时放宽',
          });
          continue;
        }

        let candidates = canonicalSelectorCandidates(
          selector,
          canonical,
          currentScreenIds.length === 1 ? currentScreenIds[0] : undefined,
        );
        if (rawMatch === 'contains' && candidates.length > 1) {
          const independentTargets = candidates.filter(entry => entry.hasChildren !== true);
          if (independentTargets.length === 1) candidates = independentTargets;
        }
        const candidateIds = [...new Set(candidates.map(entry => entry.id))];
        const screenCount = new Set(candidates.map(entry => entry.screenId)).size;
        const ambiguous = (candidateIds.length > 1 || screenCount > 1) && !normalized.disambiguated;
        const aggregateParent = rawMatch === 'contains' && candidates.some(
          entry => entry.hasChildren === true && entry.text !== selector.value,
        );
        if (candidateIds.length === 0 || ambiguous || aggregateParent) {
          violations.push({
            rule_id: SELECTOR_SPEC_RULE_ID,
            severity: 'BLOCKER',
            tc_id: row.tc_id,
            step_index: stepIndex,
            selector_kind: selector.kind,
            selector: selector.value,
            match: rawMatch,
            canonical_ids: candidateIds,
            message: candidateIds.length === 0
              ? 'by_text 未映射到 canonical ui-spec text；dump/cache 只能提供建议'
              : aggregateParent
                ? '富文本聚合 Text/Row 仅包含该片段但未声明独立 interaction target；禁止点击父节点中心'
                : 'by_text 在 canonical ui-spec 中多映射且无 index/scope/within/all 消歧',
          });
        }
      }
    });
  }
  return violations;
}
