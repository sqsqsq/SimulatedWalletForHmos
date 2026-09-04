/**
 * coding 阶段 post_check（实例扩展）—— 义务在代码里**真的落到了那个实体上**吗。
 *
 * 本阶段的证据是代码本身。机械层只查它判得了、且对已知违规有区分力的三件事：
 *   ① 契约点名的实体，代码里在不在（文件建了但里面没有那个类/字段/枚举，义务就没有承载）；
 *   ② `verify: probe` 的义务，跑规约自带的探针；
 *   ③ 标了模式的角色文件，那个角色在定义文件之外有没有被调用。
 *
 * 基线的探针是 `\b名\b` 跨文件文本存在性——不分声明/调用/注释，末段是容器名时恒真，
 * 它会把明晃晃的违规照常放行。**本文件不含任何规则编号、域前缀或来自规约的正则字面**：
 * 探针表达式随知识走（规约表的「探针」列），换一套知识这里一个字都不用改。
 *
 * 「落得对不对」是语义判断，归 overlay。机械层越权下语义结论，就成了「写了字就算做了」。
 *
 * 契约：stdin JSON ctx → stdout JSON result。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { STATUS } from '../shared/evidence.mjs';
import { contractFiles, readContracts, resolveEntityRef } from '../shared/contracts.mjs';
import { guard, gate } from '../shared/gate.mjs';
import { activeKnowledge, entryById } from '../shared/knowledge.mjs';
import { obligationsFromContracts, patternRolesFromContracts } from '../shared/obligations.mjs';
import { filesForEntity, runProbe } from '../shared/probes.mjs';

const AUTHOR_DOC = 'doc/extensions/hooks/coding/author.md';
const FIX = `处置：补齐落点实现或修正违规写法；确实落不了的回 plan 改 must（改了要重跑 plan 阶段），`
  + `再重跑 harness --phase coding。形态见 ${AUTHOR_DOC}。`;

/** 落点末段标识符：`data_models.Ctx.flowId` → `flowId`；`files.a/b/X.ets` → `X`。 */
function tailIdentifier(entityPath) {
  const raw = String(entityPath ?? '');
  const last = raw.split('.').pop() ?? '';
  return last.includes('/') ? (last.split('/').pop() ?? '').replace(/\.[^.]+$/, '') : last;
}

/** 在契约点名的实现文件里找标识符——按契约限定范围，不全仓扫。 */
function findIdentifier(projectRoot, files, name) {
  const re = new RegExp(`\\b${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`);
  for (const rel of files) {
    let text;
    try {
      text = fs.readFileSync(path.resolve(projectRoot, rel), 'utf-8');
    } catch {
      continue;
    }
    if (re.test(text)) return true;
  }
  return false;
}

export default guard('coding', async (ctx) => {
  const { contracts, error, exists } = readContracts(ctx.projectRoot, ctx.feature);
  if (error) return gate(ctx, { problems: [error], fix: FIX });
  if (!exists) {
    return gate(ctx, { skipped: [{ what: '义务落点与探针', why: '契约还没建（或读不到）' }] });
  }

  let knowledge;
  try {
    knowledge = activeKnowledge(ctx.projectRoot);
  } catch (e) {
    return gate(ctx, { problems: [`激活知识派生失败：${e.message}`], fix: FIX });
  }

  const obligations = obligationsFromContracts(contracts);
  const roles = patternRolesFromContracts(contracts);
  if (!obligations.length && !roles.length) {
    return gate(ctx, {
      skipped: [{ what: '义务落点与探针', why: '契约里没有 must，也没有标 pattern 的文件' }],
    });
  }

  const files = contractFiles(contracts);
  const present = files.filter(rel => fs.existsSync(path.resolve(ctx.projectRoot, rel)));
  if (!present.length) {
    // 契约文件一个都还没建：框架原生的文件完整性门禁会报，这里不重复；但要留痕说明没跑成
    return gate(ctx, {
      skipped: [{ what: '义务落点与探针', why: '契约点名的实现文件一个都还没建' }],
    });
  }

  const problems = [];
  const warnings = [];

  // ---- 1. 落点实体在代码里存在 ----
  for (const ob of obligations) {
    if (ob.entityKind === 'files') continue;             // 文件级由框架原生门禁负责
    const resolved = resolveEntityRef(contracts, ob.entityPath);
    if (/[/\\]/.test(resolved.tail)) continue;            // 路径类落点同上
    const name = tailIdentifier(ob.entityPath);
    if (!name) continue;
    if (!findIdentifier(ctx.projectRoot, present, name)) {
      problems.push(`义务 ${ob.rule} 挂在「${ob.entityPath}」上，代码里找不到「${name}」`
        + '——契约说这条义务落在这个实体上，实现里却没有它');
    }
  }

  // ---- 2. verify: probe 的义务，跑规约自带的探针 ----
  for (const ob of obligations.filter(o => o.verify === 'probe')) {
    const entry = entryById(knowledge, ob.rule);
    if (!entry) {
      problems.push(`义务 ${ob.rule} 不在激活清单里——无从取探针（plan 阶段本该拦住）`);
      continue;
    }
    if (!entry.probe) {
      problems.push(`义务 ${ob.rule} 标了 verify: probe，但该条目的规约表没有探针`
        + '——回 plan 改成 ut / device / both / review');
      continue;
    }
    const r = runProbe(entry.probe, {
      projectRoot: ctx.projectRoot,
      files: present,
      entityName: tailIdentifier(ob.entityPath),
      entityKind: ob.entityKind,
    });
    if (!r.ok) {
      problems.push(`义务 ${ob.rule}（${ob.entityPath}）探针未过：${r.detail}`);
    } else if (r.scanned === 0) {
      // 0 命中要出声：探针写错了与代码没问题，在结果上完全同形（KB-11）
      warnings.push(`义务 ${ob.rule} 的探针扫描 0 个文件——形态可能不匹配本工程`);
    }
  }

  // ---- 3. 模式角色：在定义文件之外被引用 ----
  for (const pr of roles) {
    const base = path.basename(pr.path).replace(/\.[^.]+$/, '');
    const scope = filesForEntity(present, base);
    if (!scope.narrowed) {
      warnings.push(`模式 ${pr.pattern} 的角色文件「${pr.path}」还没建，引用可达性未验`);
      continue;
    }
    const r = runProbe(
      { kind: 'referenced_outside_definition', pattern: '', count: null, raw: 'referenced_outside_definition' },
      { projectRoot: ctx.projectRoot, files: present, entityName: base, entityKind: 'files' });
    if (!r.ok) {
      problems.push(`模式 ${pr.pattern} 的角色「${pr.role}」（${pr.path}）${r.detail}`
        + '——角色类建了却没有任何地方调用它，等于这个模式只落在了文件名上');
    }
  }

  return gate(ctx, {
    problems,
    fix: FIX,
    checks: [
      { id: 'knowledge_landing_in_code', status: problems.length ? STATUS.FAIL : STATUS.PASS,
        detail: `义务 ${obligations.length} 条、角色 ${roles.length} 个；问题 ${problems.length} 条`
          + (warnings.length ? `；告警 ${warnings.length} 条：${warnings.join('；')}` : '') },
    ],
    inputs: present.map(rel => path.resolve(ctx.projectRoot, rel)),
  });
});
