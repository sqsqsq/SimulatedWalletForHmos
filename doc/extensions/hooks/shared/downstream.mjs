/**
 * 下游阶段（coding / review / ut / testing）的共同基座。
 *
 * 下游只读 plan 的冻结结果，**不读知识目录**：冻结缺失就零注入——不是「回退到全量」，
 * 是什么都收不到，然后阻断并指路回 plan。让下游自己回去重读知识、重新解释一遍，
 * 等于把「已经定下来的事」重新打开，那正是知识在链路上走样的方式。
 */
import { readAcceptance, readContracts, readFreeze, knowledgeCriteria } from './freeze.mjs';

const PLAN_INJECTION_DOC = 'doc/extensions/hooks/plan/author.md';

/**
 * 取本阶段要消费的账本。
 *
 * @returns {{ok: boolean, blocked: object|null, book: object|null}}
 *   `blocked` 非空时调用方直接返回它（冻结缺失/契约坏了，本阶段无从判起）。
 */
export function loadLedger(ctx, phase) {
  const { contracts, error, exists } = readContracts(ctx.projectRoot, ctx.feature);
  if (error) {
    return { ok: false, blocked: blocker(phase, [error]), book: null };
  }
  if (!exists) {
    // 契约本身缺失由框架的 check-<phase> 负责，这里不重复报
    return { ok: false, blocked: null, book: null };
  }
  const { freeze, obligations, patterns } = readFreeze(contracts);
  if (!freeze) {
    return {
      ok: false,
      book: null,
      blocked: blocker(phase, [
        'plan 未冻结知识结果（contracts.yaml 缺 knowledge_freeze）——'
        + '下游读的是冻结结果，不是知识目录；没有它本阶段零注入，也无从留证。'
        + `处置：回 plan 按 ${PLAN_INJECTION_DOC} 补齐冻结，重跑 plan 阶段后再回本阶段`,
      ]),
    };
  }
  const { acceptance } = readAcceptance(ctx.projectRoot, ctx.feature);
  return {
    ok: true,
    blocked: null,
    book: {
      contracts,
      obligations,
      patterns: patterns.filter(p => p.selected === true),
      criteria: knowledgeCriteria(acceptance),
      acceptance,
    },
  };
}

/**
 * 某条义务对应的验收条目的 ut_layer —— 四阶段分派的单源。
 * `unit` = 只由 UT 验；`device` = 只由实机验；`both` = 两边都要。
 * 这同时是「显式不适用」的载体：不适用的阶段照样要说话，只是说「不适用 + 层级」。
 */
export function utLayerOf(book, obligation) {
  const criterion = String(obligation?.criterion ?? '').trim();
  if (!criterion) return null;
  for (const c of book.criteria.values()) {
    if (String(c.id ?? '') === criterion) {
      const layer = String(c.ut_layer ?? '').trim().toLowerCase();
      return layer || null;
    }
  }
  return null;
}

export function blocker(phase, problems) {
  return {
    ok: false,
    severityOverride: 'BLOCKER',
    message: `${phase} 阶段知识账本核对未通过：${problems.join('；')}。`,
  };
}

export { PLAN_INJECTION_DOC };
