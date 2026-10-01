#!/usr/bin/env node
/**
 * 当前动作的知识任务：动笔或审查之前，把这一次要用的知识原文、已成立的判断与义务、完成条件和缺口一次交给模型。
 *
 *   node doc/extensions/hooks/shared/knowledge-task.mjs --project-root <根> --action <动作> --audience author|reviewer
 *        （--blueprint <蓝图 id> | --feature <原生 Feature id> [--requirement-file <文件> | --requirement <原文>]）
 *
 * 蓝图动作：discovery（蓝图可以还不存在）/ design / questioning（要有可读的草稿）。
 * Feature 动作：spec / plan / coding / review / ut / testing，按本阶段已有的原生输入取，不要求后继契约已经形成。
 * 执行范围未冻结时输出是预览：本阶段输入还没确定，不作为动笔依据。需求正文只在无 run 的 spec 恢复不出来源时给。
 *
 * 只读。退出 0 输出完整任务；1 为坏身份、坏知识登记或所需来源缺失（stdout 不给半份，stderr 写对象、缺口、责任）；
 * 2 为参数或依赖错误。空清单合法，明示零项。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { blueprintKnowledge, featureKnowledge } from './knowledge-application.mjs';
import { readBlueprint, readFeature } from './framework-access.mjs';
import { activeKnowledge, HALVES, knowledgeRegistrations, selfCheck } from './knowledge.mjs';
import { obligationsFromContracts } from './obligations.mjs';
import { statDelivery } from './stat-points.mjs';
import { extensionRoot, relDisplay } from './paths.mjs';

const BLUEPRINT_ACTIONS = ['discovery', 'design', 'questioning'];
const FEATURE_ACTIONS = ['spec', 'plan', 'coding', 'review', 'ut', 'testing'];
const AUDIENCES = ['author', 'reviewer'];
/** 上下篇知识：上篇给设计侧（需求与设计动作），下篇给实现侧。 */
const DESIGN_SIDE = new Set(['discovery', 'design', 'questioning']);

class TaskError extends Error {}
const stop = (object, gap, owner) => { throw new TaskError(`对象：${object}\n缺口：${gap}\n责任：${owner}`); };

/**
 * 这一登记在本动作送不送。Feature 阶段按 manifest 的受众语义：字符串登记给全部 Feature 阶段，对象登记给
 * `global` 或列出的阶段；蓝图的设计动作要看全局，登记的都送，相关与否由模型按「何时读」判断。
 */
const reaches = (registration, action) => !FEATURE_ACTIONS.includes(action) || registration.audience === null
  || registration.audience === 'global' || (Array.isArray(registration.audience) && registration.audience.includes(action));

/** 激活知识按清单顺序：路径、类别、形态、何时读，以及去掉 frontmatter 的完整原文。 */
function knowledgeBlock(root, action) {
  let knowledge;
  try {
    knowledge = activeKnowledge(root);
  } catch (e) {
    stop('扩展 manifest 的知识激活清单', e.message, '目标工程的知识维护者（按 skills/story/reference/knowledge/protocol.md 修正登记或文件）');
  }
  const byFile = new Map([...knowledge.facts, ...knowledge.constraints, ...knowledge.patterns].map(k => [k.file, k]));
  const registrations = knowledgeRegistrations(root).filter(r => reaches(r, action));
  const ordered = registrations.map(r => ({ ...byFile.get(r.file), registration: r })).filter(k => k.file);
  const rows = ['## 2. 激活知识及原文', ''];
  const protocol = path.join(extensionRoot(root), 'skills', 'story', 'reference', 'knowledge', 'protocol.md');
  if (!ordered.length) {
    const total = knowledgeRegistrations(root).length;
    return { knowledge, rows: [...rows, total ? `登记了 ${total} 份知识，受众里都没有 ${action}（零项）。`
      : `激活清单为空：这个工程还没有登记知识（零项）。知识怎么写、怎么登记见 \`${relDisplay(root, protocol)}\`。`] };
  }
  const half = DESIGN_SIDE.has(action) ? HALVES[0] : HALVES[1];
  rows.push(`共 ${ordered.length} 份，按激活顺序。先按「何时读」判断与本动作是否相关；相关的逐条判断适用与否。`
    + `各列与形态怎么读见 \`${relDisplay(root, protocol)}\`。`, '');
  for (const k of ordered) {
    const file = path.join(extensionRoot(root), ...k.file.split('/'));
    const body = fs.readFileSync(file, 'utf8').replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, '').trim();
    const digest = `sha256:${crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')}`;
    rows.push(`### ${k.name}（${k.file.split('/')[1] ?? ''}，${k.form}）`, '',
      `- 位置：\`${relDisplay(root, file)}\`（判断的 provenance.source_ref）`, `- 原文摘要：\`${digest}\`（判断的 source_sha256）`,
      `- 单元：${k.units.join('、')}`, `- 何时读：${k.appliesWhen}`,
      ...(k.registration.audience === null ? []
        : [`- 登记：受众 ${JSON.stringify(k.registration.audience)}${k.registration.summary ? `，摘要「${k.registration.summary}」` : ''}`]),
      ...(k.form === 'halves' ? [`- 本动作主要用${half}；两篇都在下面，另一篇供核对承接`] : []),
      '', '````markdown', body, '````', '');
  }
  return { knowledge, rows };
}

/** 蓝图里与知识相关的事实与决定：原样列出，判断归模型。 */
function decisionsOf(blueprint) {
  const facts = (blueprint?.discovery?.facts ?? []).filter(f => f?.value?.knowledge);
  const decisions = (blueprint?.decisions_and_gaps?.decisions ?? []).filter(d => d?.kind === 'knowledge_application');
  return [...facts.map(f => `- 事实 \`${f.fact_id}\`：${JSON.stringify(f.value)}`),
    ...decisions.map(d => `- 决定 \`${d.decision_id}\`（${d.status}）：${d.rationale ?? ''} ${JSON.stringify(d.knowledge ?? {})}`)];
}

function blueprintTask(root, id, action) {
  let bp = readBlueprint(root, id, 'draft');
  const gaps = [];
  if (bp.status === 'missing') {
    if (action === 'questioning') stop(`蓝图 ${id}`, '还没有可读的蓝图草稿，质询无从进行', '设计作者先写出蓝图草稿');
    gaps.push(`蓝图 ${id} 还不存在：设计作者按原生 component-design 流程建立。`);
    bp = null;
  } else if (bp.status !== 'ok') {
    stop(`蓝图 ${id}`, bp.issues.map(i => `${i.code} ${i.message}`).join('；'), '设计作者按原生报错修正蓝图或身份');
  }
  const object = bp ? `蓝图 \`${id}\`（\`${bp.canonical_path}\`，revision ${bp.blueprint_ref.revision}，${bp.admitted ? '已准入' : '草稿，未准入'}）`
    : `蓝图 \`${id}\`（尚未建立）`;
  if (bp?.issues?.length) gaps.push(`蓝图原生校验有 ${bp.issues.length} 项：${bp.issues.slice(0, 5).map(i => i.id ?? i.code).join('、')}——设计作者处理。`);
  const decided = bp ? decisionsOf(bp.blueprint) : [];
  if (bp) gaps.push(...blueprintKnowledge(root, bp.blueprint).problems.map(p => `${p}——设计作者处理。`));
  return {
    object,
    facts: decided.length ? decided : [bp ? '蓝图里还没有知识应用的事实与决定。' : '蓝图尚未建立，没有已成立的判断。'],
    duties: ['设计阶段还没有施工契约；知识判断以决定的形式落在蓝图里，施工义务在施工单位的契约中承接。'],
    gaps,
    page: `hooks/blueprint/${action === 'questioning' ? 'reviewer' : 'author'}.md`,
  };
}

function featureTask(root, feature, action, supplied) {
  const f = readFeature(root, feature, action, supplied);
  if (f.status !== 'ok') {
    stop(`Feature ${feature}（${action} 阶段）`, f.issues.map(i => `${i.code} ${i.message}`).join('；'),
      f.status === 'stale' ? '设计负责方重新准备该施工单位（蓝图已变）'
        : f.status === 'missing' ? '调用方按原生身份给出存在的 Feature'
          : f.issues.some(i => i.code === 'requirement_text_needed') ? '调用方用 --requirement-file 或 --requirement 给出与范围候选同一份的原始需求正文后重取'
            : f.issues.some(i => i.code === 'requirement_stale') ? '需求来源在范围冻结后变了：范围负责方按原生修订路径处理，不换一份需求顶上'
              : '产出这份输入的阶段或设计负责方按原生报错修正');
  }
  const gaps = [];
  const kind = f.identity.kind === 'cu'
    ? `施工单位 \`${f.identity.changeUnitId}\`（蓝图 \`${f.identity.blueprintId}\` revision ${f.blueprint_ref?.revision}）` : '平铺维护 Feature';
  let facts = [];
  if (f.identity.kind === 'cu') {
    const bp = readBlueprint(root, f.identity.blueprintId, 'draft');
    facts = bp.status === 'ok' ? decisionsOf(bp.blueprint) : [];
    if (bp.status !== 'ok') gaps.push(`蓝图读不到（${bp.status}）：设计负责方处理。`);
    if (!facts.length) facts = ['蓝图里还没有知识应用的事实与决定。'];
    facts.push(`本施工单位承担的设计对象：${f.design_refs.map(r => `${r?.target?.kind}:${r?.target?.id}`).join('、') || '（无）'}`);
  } else {
    const rows = (f.spec?.contracts?.knowledge_applications ?? []).map(d => `- 决定 \`${d.decision_id}\`（${d.status}）：${d.rationale ?? ''}`);
    facts = rows.length ? rows : ['契约里还没有知识应用的决定。'];
  }
  const duties = [];
  if (f.scope === 'not_frozen') {
    duties.push('本阶段的原生输入还没有确定（执行范围未冻结），本任务只是预览，不作为动笔依据。');
    gaps.push('执行范围未冻结：已获准开始本阶段的主模型按 story-knowledge Skill 的「范围未冻结时」先准备范围'
      + '（没有候选先走原生 prepare-scope，再由原生 ensureFeatureExecutionScopeFrozen 冻结），返回 frozen 或 reused 后重取本任务再动笔；原生失败按它的报错交回责任方。');
  } else {
    // 契约与验收取原生按阶段组装的那一份：解析器选定的输入加本阶段自己的产出
    const contracts = f.spec?.contracts ?? null;
    const source = f.inputs.contracts;
    if (contracts) {
      const must = obligationsFromContracts(contracts);
      duties.push(`契约来自 ${source?.binding?.kind ?? '本阶段产出'}${source?.binding?.artifact ? ` ${source.binding.artifact}` : ''}。`,
        ...(must.length ? must.map(m => `- \`${m.entityPath}\`：${m.rule} ${m.text}（验证 ${m.verify || '未写'}）`) : ['契约里没有知识义务。']));
    } else {
      duties.push(`本阶段没有可读的施工契约（${source?.state ?? '本阶段不读契约'}）${source?.detail ? `：${source.detail}` : ''}。`);
    }
    const acceptance = f.spec?.acceptance ?? null;
    if (f.identity.kind === 'cu' && action !== 'spec') {
      duties.push(...statDelivery(featureKnowledge(root, feature, contracts), contracts, acceptance));
    }
    const bridged = [...(acceptance?.criteria ?? []), ...(acceptance?.boundaries ?? [])].filter(c => c?.knowledge_rule);
    duties.push(...bridged.map(c => `- 验收 \`${c.id}\` 承接 \`${c.knowledge_rule}\`${c.knowledge_decision_id ? `（决定 ${c.knowledge_decision_id}）` : ''}`));
    if (f.assurance === 'degraded') gaps.push('原生阶段解析为 degraded：有能力被裁剪，按原生报告核对本阶段可用的输入。');
  }
  return {
    object: `Feature \`${feature}\`，${kind}，位置 \`${f.feature_path}\``, facts, duties, gaps, page: `hooks/${action}/author.md`,
    preview: f.scope === 'not_frozen',
  };
}

export function knowledgeTask(root, { action, audience, blueprint, feature, requirement, requirementFile }) {
  // 激活知识先读：读不出按知识维护者的缺口报，后面核判断时不再撞同一处
  const { knowledge, rows } = knowledgeBlock(root, action);
  const task = blueprint ? blueprintTask(root, blueprint, action) : featureTask(root, feature, action, { requirement, requirementFile });
  const problems = selfCheck(root, knowledge);
  const page = relDisplay(root, path.join(extensionRoot(root), ...task.page.split('/')));
  const done = audience === 'author'
    ? [`按 \`${page}\` 做本动作；知识方面：与本动作相关的每份知识都判断适用与否，适用的把要求落到第 3、4 块对应的设计对象或契约实体上，`
      + '不适用写明本需求里使它不适用的条件；已成立的判断直接承接。']
    : [`对照第 2 块原文核被审对象：相关知识有没有被判断、判断有没有依据、落点是不是真的承担这件事；${blueprint ? `审查要求见 \`${page}\`。` : '判据按本阶段审查清单。'}`];
  return [`# 知识任务：${action}（${audience === 'author' ? '作者' : '审查者'}）${task.preview ? '——预览，执行范围未冻结' : ''}`, '',
    '## 1. 当前动作与对象', '', `- 动作：${action}`, `- 对象：${task.object}`, '',
    ...rows, '',
    '## 3. 有效事实与决定', '', ...task.facts, '',
    '## 4. 当前契约与义务', '', ...task.duties, '',
    '## 5. 本次完成条件', '', ...done, '',
    '## 6. 缺口与责任', '',
    ...([...task.gaps, ...problems.map(p => `知识自检：${p}——目标工程的知识维护者处理。`)].map(g => `- ${g}`)),
    ...(!task.gaps.length && !problems.length ? ['- 无。'] : []), ''].join('\n');
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const argv = process.argv.slice(2);
  const opt = k => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : undefined; };
  const args = { action: opt('--action'), audience: opt('--audience'), blueprint: opt('--blueprint'), feature: opt('--feature'),
    requirement: opt('--requirement'), requirementFile: opt('--requirement-file') };
  const root = opt('--project-root');
  const legal = root && AUDIENCES.includes(args.audience) && !!args.blueprint !== !!args.feature
    && (args.blueprint ? BLUEPRINT_ACTIONS : FEATURE_ACTIONS).includes(args.action);
  if (!legal) {
    process.stderr.write('用法：--project-root <根> --action <动作> --audience author|reviewer'
      + '（--blueprint <id> | --feature <id> [--requirement-file <文件> | --requirement <原文>]）\n'
      + `  蓝图动作：${BLUEPRINT_ACTIONS.join(' / ')}；Feature 动作：${FEATURE_ACTIONS.join(' / ')}\n`);
    process.exit(2);
  }
  try {
    process.stdout.write(knowledgeTask(path.resolve(root), args));
  } catch (e) {
    process.stderr.write(`[knowledge-task]\n${e?.message ?? e}\n`);
    process.exit(e instanceof TaskError ? 1 : 2);
  }
}
