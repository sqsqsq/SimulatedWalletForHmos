/**
 * testing 阶段 post_check（实例扩展）—— 知识义务的实机验证覆盖。
 *
 * 与 UT 对称：框架原生的验收↔用例追溯门禁判「AC 有没有被用例引用」，本 hook 只补
 * 「哪些 AC 是知识义务派生的」，并按 `ut_layer` 把「本阶段不适用」显式说出来。
 *
 * `device`/`both` 归实机，`unit` 归 UT——标 `unit` 就是说「实机不适用于这一条」。
 *
 * **本阶段是这些约束的最后一道关**：「已验证」三个字不构成结论，
 * 但那是语义判断（归 overlay 的语义判据），机械层只查引用在不在。
 *
 * 契约：stdin JSON ctx → stdout JSON result。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { featureRoot, readTextOrNull } from '../shared/paths.mjs';
import { knowledgeCriteria, readAcceptance, readContracts } from '../shared/freeze.mjs';
import { obligationsFromContracts } from '../shared/obligations.mjs';
import { guard, gate } from '../shared/gate.mjs';

/**
 * 实机侧的覆盖证据：测试计划与报告里引用到的 AC。
 *
 * 同时回报**产物有没有建**——两者要分开：产物没建是「本阶段还没开始」（交框架原生门禁），
 * 产物建了却一个 AC 都没引用是「验了个寂寞」，那正是本 hook 要抓的。
 * 把二者混成一个「空集就放过」，后一种情况会静默溜走。
 */
function referencedAcceptanceIds(projectRoot, feature) {
  const root = path.join(featureRoot(projectRoot, feature), 'testing');
  const ids = new Set();
  let artifactCount = 0;
  const stack = [root];
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
      if (!/\.(md|json|yaml)$/.test(e.name)) continue;
      const text = readTextOrNull(p);
      if (text === null) continue;
      artifactCount++;
      for (const m of text.matchAll(/\b(?:AC|BD)-(?:G\d+|\d+)\b/g)) ids.add(m[0]);
    }
  }
  return { ids, artifactCount };
}

export default guard('testing', async (ctx) => {
  const { contracts, error, exists } = readContracts(ctx.projectRoot, ctx.feature);
  if (error) return gate(ctx, { problems: [error] });
  if (!exists) {
    return gate(ctx, { skipped: [{ what: '验收条目实机覆盖', why: '契约还没建（或读不到）' }] });
  }
  const obligations = obligationsFromContracts(contracts);
  if (!obligations.length) {
    return gate(ctx, { skipped: [{ what: '验收条目实机覆盖', why: '契约里没有 must' }] });
  }

  const { ids: referenced, artifactCount } = referencedAcceptanceIds(ctx.projectRoot, ctx.feature);
  if (!artifactCount) {
    return gate(ctx, { skipped: [{ what: '验收条目实机覆盖', why: '测试产物还没建' }] });
  }

  // 桥接：acceptance.yaml 的 knowledge_rule 把验收条目认回规约条目（framework 原生追溯链）
  const { acceptance } = readAcceptance(ctx.projectRoot, ctx.feature);
  const criteria = knowledgeCriteria(acceptance);
  const problems = [];
  const notApplicable = [];

  for (const ob of obligations) {
    const rule = String(ob.rule ?? '?');
    // verify 是四阶段分派的单源：本阶段只管 device 与 both，其余是显式不适用
    if (ob.verify !== 'device' && ob.verify !== 'both') {
      notApplicable.push(`${rule}（verify: ${ob.verify || '未标'}，不由实机验）`);
      continue;
    }
    const c = criteria.get(rule);
    if (!c) {
      problems.push(`义务 ${rule} 标了 verify: ${ob.verify}，但 acceptance.yaml 里没有`
        + `knowledge_rule: ${rule} 的验收条目——本阶段无从知道该走查什么`);
      continue;
    }
    const id = String(c.id ?? '').trim();
    if (id && !referenced.has(id)) {
      problems.push(`义务 ${rule} 的验收条目 ${id} 在实机测试产物里没有被引用`
        + '——本阶段是这些约束的最后一道关，漏了就再没有人验');
    }
  }

  return gate(ctx, {
    problems,
    checks: notApplicable.length
      ? [{ id: 'ext_testing_not_applicable', status: 'NOT_APPLICABLE',
          detail: `按 must.verify 显式分派：${notApplicable.join('、')}` }]
      : undefined,
    fix: '处置：在测试计划与报告里覆盖这些验收条目，或回 plan 修正 must.verify 后重跑。',
  });
});
