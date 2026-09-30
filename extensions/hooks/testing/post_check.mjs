/**
 * testing 阶段 post_check（实例扩展）—— 知识义务的实机验证覆盖。
 *
 * 与 UT 对称：框架原生的验收↔用例追溯门禁判「AC 有没有被用例引用」，本 hook 只补
 * 「哪些 AC 是知识义务派生的」，并按义务的 `must.verify` 把「本阶段不适用」显式说出来。
 *
 * `device`/`both` 归实机，`ut` 归 UT——标 `ut` 就是说「实机不适用于这一条」。
 *
 * **本阶段是这些约束的最后一道关**：「已验证」三个字不构成结论，
 * 但那是语义判断（归 overlay 的语义判据），机械层只查引用在不在。
 *
 * 契约：stdin JSON ctx → stdout JSON result。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { readTextOrNull } from '../shared/paths.mjs';
import { acceptanceIdRe, knowledgeCriteria, phaseArtifacts } from '../shared/contracts.mjs';
import { obligationsFromContracts } from '../shared/obligations.mjs';
import { guard, gate } from '../shared/gate.mjs';

/**
 * 实机侧的覆盖证据：测试计划与报告里引用到的 AC。
 *
 * 同时回报**产物有没有建**——两者要分开：产物没建是「本阶段还没开始」（交框架原生门禁），
 * 产物建了却一个 AC 都没引用是「验了个寂寞」，那正是本 hook 要抓的。
 * 把二者混成一个「空集就放过」，后一种情况会静默溜走。
 */
function referencedAcceptanceIds(dir) {
  const root = path.join(dir, 'testing');
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
      for (const m of text.matchAll(acceptanceIdRe())) ids.add(m[0]);
    }
  }
  return { ids, artifactCount };
}

export default guard('testing', async (ctx) => {
  const inputs = phaseArtifacts(ctx.projectRoot, ctx.feature, 'testing');
  // 每个出口都带上原生对本阶段输入报的问题：输入不成立时，本判据不适用或没跑成都不能自报通过
  const done = (r) => gate(ctx, { ...r, problems: [...inputs.problems, ...(r.problems ?? [])] });
  if (!inputs.dir) return done({});
  const contracts = inputs.contracts;
  if (!contracts) return done({ skipped: [{ what: '验收条目实机覆盖', why: inputs.why }] });
  const obligations = obligationsFromContracts(contracts);
  if (!obligations.length) {
    return done({ skipped: [{ what: '验收条目实机覆盖', why: '契约里没有 must' }] });
  }

  const { ids: referenced, artifactCount } = referencedAcceptanceIds(inputs.dir);
  if (!artifactCount) {
    return done({ skipped: [{ what: '验收条目实机覆盖', why: '测试产物还没建' }] });
  }

  // 桥接：acceptance.yaml 的 knowledge_rule 把验收条目认回规约条目（framework 原生追溯链）。
  // 同一规约常有多个验收条目（不同场景），逐条核，不能只看最后一条；
  // 原生没给出验收时说出原因，不当空集合放行。
  const acceptance = inputs.acceptance;
  const accError = acceptance ? null : `验收拿不到（${inputs.why}）——义务按验收条目分派，没有验收就核不了覆盖`;
  const { byRule, problems: accProblems } = knowledgeCriteria(acceptance);
  const problems = accError ? [accError] : [...accProblems];

  for (const ob of obligations) {
    const rule = String(ob.rule ?? '?');
    // verify 是四阶段分派的单源：本阶段只管 device 与 both，其余是显式不适用
    if (ob.verify !== 'device' && ob.verify !== 'both') continue;
    // 同编号的规约可能来自不同文件：按义务出自的那条判断认验收
    const entries = (byRule.get(rule) ?? []).filter(c => String(c.knowledge_decision_id).trim() === ob.decisionId);
    if (!entries.length) {
      problems.push(`acceptance.yaml：义务 ${rule} 标了 verify: ${ob.verify}，但没有 `
        + `knowledge_rule: ${rule}、knowledge_decision_id: ${ob.decisionId} 的验收条目——门禁按这两项把验收条目认回义务出自的判断，要走查的场景从这些条目取`);
      continue;
    }
    for (const c of entries) {
      const id = String(c.id ?? '').trim();
      if (!id) {
        problems.push(`acceptance.yaml：义务 ${rule} 有一条验收条目没写 id——实机测试计划与报告按验收编号回查`);
        continue;
      }
      if (!referenced.has(id)) {
        problems.push(`testing/：义务 ${rule} 的验收条目 ${id} 在实机测试产物里没有被引用`
          + '——门禁在 testing/ 下的 .md、.json、.yaml 里找这个编号；本阶段是这些约束的最后一道关，漏了就再没有人验');
      }
    }
  }

  return done({ problems });
});
