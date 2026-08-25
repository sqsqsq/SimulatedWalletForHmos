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
import { blocker, loadLedger, utLayerOf } from '../shared/downstream.mjs';

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

export default async function testingPostCheck(ctx) {
  if (ctx?.phase !== 'testing' || !ctx?.feature || !ctx?.projectRoot) return { ok: true };

  const { ok, blocked, book } = loadLedger(ctx, 'testing');
  if (!ok) return blocked ?? { ok: true };
  if (!book.obligations.length) return { ok: true };

  const { ids: referenced, artifactCount } = referencedAcceptanceIds(ctx.projectRoot, ctx.feature);
  if (!artifactCount) return { ok: true };   // 测试产物还没建，交框架原生门禁

  const problems = [];
  const notApplicable = [];

  for (const ob of book.obligations) {
    const rule = String(ob.rule ?? '?');
    const criterion = String(ob.criterion ?? '').trim();
    if (!criterion) continue;
    const layer = utLayerOf(book, ob);
    if (layer === 'unit') {
      notApplicable.push(`${rule}（验收条目 ${criterion} 标 unit 层，由 UT 验）`);
      continue;
    }
    if (!layer) {
      problems.push(`义务 ${rule} 对应的验收条目 ${criterion} 没有 ut_layer`
        + '——它是四阶段分派的单源，缺了就无从判断该由谁验');
      continue;
    }
    if (!referenced.has(criterion)) {
      problems.push(`义务 ${rule} 的验收条目 ${criterion}（${layer} 层）在实机测试产物里没有被引用`
        + '——本阶段是这些约束的最后一道关，漏了就再没有人验');
    }
  }

  if (problems.length) {
    return blocker('testing', [
      ...problems,
      notApplicable.length ? `本阶段不适用（已按 ut_layer 显式分派）：${notApplicable.join('、')}` : null,
      '处置：在测试计划与报告里覆盖这些验收条目，或回 plan 修正 ut_layer 后重跑',
    ].filter(Boolean));
  }
  return { ok: true };
}
