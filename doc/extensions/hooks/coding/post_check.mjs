/**
 * coding 阶段 post_check（实例扩展）—— 冻结落点的**实体存在性**。
 *
 * 本阶段的证据是代码本身，而代码里落得对不对是语义判断（归 overlay 的语义判据）。
 * 机械层只查它判得了的那件事：**plan 冻结时点名的落点与角色，现在到底在不在**。
 *
 * 文件级的存在性由框架原生的 plan→code 追溯门禁负责，本 hook 不重复；
 * 这里查的是**实体级**——文件建了，但里面没有那个类、字段或枚举，
 * 于是「上下文带流程标识」这类义务在代码里没有任何承载。
 *
 * 契约：stdin JSON ctx → stdout JSON result。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { contractFiles, landingRefs, resolveEntityRef } from '../shared/freeze.mjs';
import { loadLedger } from '../shared/downstream.mjs';
import { guard, gate } from '../shared/gate.mjs';

/** 落点引用的末段标识符：`data_models.Ctx.flowId` → `flowId`。 */
function tailIdentifier(ref) {
  const parts = String(ref ?? '').split('.');
  return parts.length >= 2 ? parts[parts.length - 1] : '';
}

/** 在契约点名的实现文件里找标识符——按契约限定范围，不全仓扫。 */
function findIdentifier(projectRoot, files, name) {
  const re = new RegExp(`\\b${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`);
  for (const rel of files) {
    const abs = path.resolve(projectRoot, rel);
    let text;
    try {
      text = fs.readFileSync(abs, 'utf-8');
    } catch {
      continue;
    }
    if (re.test(text)) return true;
  }
  return false;
}

export default guard('coding', async (ctx) => {
  const { ok, problem, book } = loadLedger(ctx, 'coding');
  if (!ok) {
    return gate(ctx, problem
      ? { problems: [problem] }
      : { skipped: [{ what: '落点实体存在性', why: '契约还没建（或读不到）' }] });
  }

  const files = contractFiles(book.contracts);
  const present = files.filter(rel => fs.existsSync(path.resolve(ctx.projectRoot, rel)));
  if (!present.length) {
    // 一个契约文件都还没建：框架原生的文件完整性门禁会报，这里不重复。
    // 但要留痕说明本判据没跑成——「没报错」不等于「查过了」。
    return gate(ctx, {
      skipped: [{ what: '落点实体存在性', why: '契约点名的实现文件一个都还没建' }],
    });
  }

  const problems = [];

  for (const ob of book.obligations) {
    const rule = String(ob.rule ?? '?');
    for (const ref of landingRefs(ob)) {
      // 文件路径类落点由框架原生的文件完整性门禁负责
      const resolved = resolveEntityRef(book.contracts, ref);
      if (ref.startsWith('files.') || /[/\\]/.test(resolved.tail)) continue;
      const name = tailIdentifier(ref);
      if (!name) continue;
      if (!findIdentifier(ctx.projectRoot, present, name)) {
        problems.push(`义务 ${rule} 的落点「${ref}」在代码里找不到「${name}」`
          + '——冻结时说这条义务落在这个实体上，实现里却没有它');
      }
    }
  }

  for (const p of book.patterns) {
    const roles = p.roles && typeof p.roles === 'object' ? p.roles : {};
    for (const [role, value] of Object.entries(roles)) {
      const name = String(value ?? '').trim();
      if (!name || /[/\\]/.test(name)) continue;      // 文件路径类角色同上
      if (!findIdentifier(ctx.projectRoot, present, name)) {
        problems.push(`模式 ${p.pattern_id} 的角色「${role}」= ${name} 在代码里找不到`
          + '——冻结了这个模式，实现就该有承载该角色的结构');
      }
    }
  }

  return gate(ctx, {
    problems,
    inputs: present.map(rel => path.resolve(ctx.projectRoot, rel)),
    fix: '处置：补齐落点实现，或回 plan 修正冻结（改了冻结要重跑 plan 阶段），'
      + '再重跑 harness --phase coding。',
  });
});
