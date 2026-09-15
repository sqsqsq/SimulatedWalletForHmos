/**
 * coding 阶段 post_check（实例扩展）—— 义务在代码里**真的落到了那个实体上**吗。
 *
 * 本阶段的证据是代码本身。机械层只查它判得了、且对已知违规有区分力的几件事：
 *   ① 契约点名的实体，代码里在不在（抹掉注释再找：只在注释里出现不算）；
 *   ② 规约自带探针的，对形态匹配的每处落点自动跑——带「阻断：」的形态就是要求，
 *      不过即这处未落实、后果按强制力；不带的只是取证线索，不过记证据缺口；
 *   ③ 标了模式的角色文件，那个角色在定义文件之外有没有被调用；
 *   ④ 注释里不写激活清单里的规约编号——追踪链在契约与验收里，注释只写代码意图。
 *
 * **本文件不含任何规则编号、域前缀或来自规约的正则字面**：探针表达式随知识走
 * （规约表的「探针」列），换一套知识这里一个字都不用改。
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
import { blankComments, filesForEntity, runProbe } from '../shared/probes.mjs';

const AUTHOR_DOC = 'doc/extensions/hooks/coding/author.md';
const FIX = `处置：补齐落点实现或修正违规写法；确实落不了的回 plan 改 must（改了要重跑 plan 阶段），`
  + `再重跑 harness --phase coding。形态见 ${AUTHOR_DOC}。`;

/** 落点末段标识符：`data_models.Ctx.flowId` → `flowId`；`files.a/b/X.ets` → `X`。 */
function tailIdentifier(entityPath) {
  const raw = String(entityPath ?? '');
  const last = raw.split('.').pop() ?? '';
  return last.includes('/') ? (last.split('/').pop() ?? '').replace(/\.[^.]+$/, '') : last;
}

/** 契约点名的实现文件原文；读不到的不列。 */
function sources(projectRoot, files) {
  return files.map(rel => {
    try {
      return { rel, text: fs.readFileSync(path.resolve(projectRoot, rel), 'utf-8') };
    } catch {
      return null;
    }
  }).filter(Boolean);
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
  const code = sources(ctx.projectRoot, present).map(s => ({ ...s, blank: blankComments(s.text) }));

  // ---- 1. 落点实体在代码里存在（注释抹掉之后）----
  for (const ob of obligations) {
    if (ob.entityKind === 'files') continue;             // 文件级由框架原生门禁负责
    const resolved = resolveEntityRef(contracts, ob.entityPath);
    if (/[/\\]/.test(resolved.tail)) continue;            // 路径类落点同上
    const name = tailIdentifier(ob.entityPath);
    if (!name) continue;
    const re = new RegExp(`\\b${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`);
    if (!code.some(s => re.test(s.blank))) {
      problems.push(`义务 ${ob.rule} 挂在「${ob.entityPath}」上，代码里找不到「${name}」`
        + '——契约说这条义务落在这个实体上，实现里却没有它（只写在注释里不算）');
    }
  }

  // ---- 2. 规约自带的探针：对形态匹配的每处落点跑，结果按「阻断」声明与强制力处置 ----
  for (const ob of obligations) {
    const entry = entryById(knowledge, ob.rule);
    const probe = entry?.probe;
    if (!probe || (probe.kind === 'present_in_method' && ob.entityKind !== 'interfaces')) continue;
    const r = runProbe(probe, {
      projectRoot: ctx.projectRoot,
      files: present,
      entityName: tailIdentifier(ob.entityPath),
      entityKind: ob.entityKind,
    });
    const where = `义务 ${ob.rule}（${ob.entityPath}）的探针`;
    if (!r.scanned) {
      // 0 命中要出声：探针写错了与代码没问题，在结果上完全同形（KB-11）
      warnings.push(`${where}扫描 0 个文件——形态可能不匹配本工程：${r.detail}`);
    } else if (r.ok) {
      continue;
    } else if (!probe.blocking) {
      warnings.push(`${where}没认出要找的形态（证据缺口，落没落实交 verifier 与实机判）：${r.detail}`);
    } else if (entry.force === '红线') {
      problems.push(`${where}未过：${r.detail}——知识声明这个形态本身就是要求，而这条规约是红线`);
    } else {
      warnings.push(`${where}未过，这一处记未落实（${entry.force}，review 复核表要写依据）：${r.detail}`);
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

  // ---- 4. 注释里的规约编号：只扫注释，只认激活清单里的编号；它治习惯，不是落实证明 ----
  const ids = new Set(knowledge.entries.map(e => e.id));
  for (const s of code) {
    const blank = s.blank.split(/\r?\n/);
    s.text.split(/\r?\n/).forEach((line, i) => {
      let note = '';
      for (let k = 0; k < line.length; k++) if (blank[i][k] !== line[k]) note += line[k];
      for (const m of note.matchAll(/\b[A-Z][A-Z0-9]{1,7}-\d{2}\b/g)) {
        if (ids.has(m[0])) {
          problems.push(`${s.rel}:${i + 1} 注释里写了规约编号 ${m[0]}——编号留在契约与验收里，注释只写这段代码的意图`);
        }
      }
    });
  }

  return gate(ctx, {
    problems,
    fix: FIX,
    checks: [
      { id: 'knowledge_landing_in_code', status: problems.length ? STATUS.FAIL : STATUS.PASS,
        // 这一条判的是**契约实体标识在不在、探针形态**，不是「义务落实了没有」——
        // 后者是语义判断，由 overlay 的同名 semantic_check 交给 verifier，告警里的证据缺口是它的输入。
        // 名字沿用是因为它已经进了 trace 与回执；措辞在这里说清，免得被当成落实的证明。
        detail: `契约实体标识存在：义务 ${obligations.length} 条、角色 ${roles.length} 个；`
          + `问题 ${problems.length} 条`
          + (warnings.length ? `；告警 ${warnings.length} 条：${warnings.join('；')}` : '') },
    ],
    inputs: present.map(rel => path.resolve(ctx.projectRoot, rel)),
  });
});
