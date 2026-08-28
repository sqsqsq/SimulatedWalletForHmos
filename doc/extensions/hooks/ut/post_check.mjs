/**
 * ut 阶段 post_check（实例扩展）—— 知识义务的用例覆盖。
 *
 * **不重复造覆盖判据**：AC 是否被用例覆盖，框架原生的验收覆盖门禁已经在判，而且判得更细
 * （DAG 反查、断言链接）。本 hook 只补它不知道的那一层——**哪些 AC 是知识义务派生的**，
 * 并按 `ut_layer` 把「本阶段不适用」显式说出来。
 *
 * `ut_layer` 是四阶段分派的单源：`unit`/`both` 归 UT，`device` 归实机。
 * 标 `device` 就等于说「UT 不适用于这一条」——这就是「显式不适用」的载体，
 * 不另建一份豁免清单（两份清单迟早对不上）。
 *
 * 契约：stdin JSON ctx → stdout JSON result。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { featureRoot, readTextOrNull } from '../shared/paths.mjs';
import { knowledgeCriteria, readAcceptance, readContracts } from '../shared/contracts.mjs';
import { obligationsFromContracts } from '../shared/obligations.mjs';
import { guard, gate } from '../shared/gate.mjs';

/** UT 侧的覆盖证据：覆盖报告 + 用例源码里出现的 AC 标记。 */
function coveredAcceptanceIds(projectRoot, feature) {
  const root = featureRoot(projectRoot, feature);
  const ids = new Set();

  const reportPath = path.join(root, 'ut', 'reports', 'ac-coverage.json');
  const raw = readTextOrNull(reportPath);
  if (raw !== null) {
    for (const m of raw.matchAll(/\b(?:AC|BD)-(?:G\d+|\d+)\b/g)) ids.add(m[0]);
  }

  // 用例里以 [AC-N] 形态标注的（框架 UT 约定）
  const utDir = path.join(root, 'ut');
  const stack = [utDir];
  while (stack.length) {
    const dir = stack.pop();
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const e of entries) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) { stack.push(p); continue; }
      if (!/\.(ets|ts|js|md|json|yaml)$/.test(e.name)) continue;
      const text = readTextOrNull(p);
      if (text === null) continue;
      for (const m of text.matchAll(/\b(?:AC|BD)-(?:G\d+|\d+)\b/g)) ids.add(m[0]);
    }
  }
  return ids;
}

export default guard('ut', async (ctx) => {
  const { contracts, error, exists } = readContracts(ctx.projectRoot, ctx.feature);
  if (error) return gate(ctx, { problems: [error] });
  if (!exists) {
    return gate(ctx, { skipped: [{ what: '验收条目 UT 覆盖', why: '契约还没建（或读不到）' }] });
  }
  const obligations = obligationsFromContracts(contracts);
  if (!obligations.length) {
    return gate(ctx, { skipped: [{ what: '验收条目 UT 覆盖', why: '契约里没有 must' }] });
  }

  // 桥接：acceptance.yaml 的 knowledge_rule 把验收条目认回规约条目（framework 原生追溯链）
  const { acceptance } = readAcceptance(ctx.projectRoot, ctx.feature);
  const criteria = knowledgeCriteria(acceptance);
  const covered = coveredAcceptanceIds(ctx.projectRoot, ctx.feature);
  const problems = [];
  const notApplicable = [];

  for (const ob of obligations) {
    const rule = String(ob.rule ?? '?');
    // verify 是四阶段分派的单源：本阶段只管 ut 与 both，其余是显式不适用
    if (ob.verify !== 'ut' && ob.verify !== 'both') {
      notApplicable.push(`${rule}（verify: ${ob.verify || '未标'}，不由 UT 验）`);
      continue;
    }
    const c = criteria.get(rule);
    if (!c) {
      problems.push(`义务 ${rule} 标了 verify: ${ob.verify}，但 acceptance.yaml 里没有`
        + `knowledge_rule: ${rule} 的验收条目——本阶段无从知道该覆盖哪个场景`);
      continue;
    }
    const id = String(c.id ?? '').trim();
    if (id && !covered.has(id)) {
      problems.push(`义务 ${rule} 的验收条目 ${id} 在 UT 侧找不到覆盖证据`
        + `——本阶段该覆盖它却没有；确实不该由 UT 验就回 plan 把 must.verify 改成 device`);
    }
  }

  return gate(ctx, {
    problems,
    checks: notApplicable.length
      ? [{ id: 'ext_ut_not_applicable', status: 'NOT_APPLICABLE',
          detail: `按 must.verify 显式分派：${notApplicable.join('、')}` }]
      : undefined,
    fix: '处置：补齐用例覆盖，或回 plan 修正 must.verify 后重跑。',
  });
});
