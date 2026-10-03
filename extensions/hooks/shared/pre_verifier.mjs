/**
 * pre_verifier —— 告诉 verifier **本阶段的知识判断在哪份文件里、按什么判**。
 *
 * ## 只指路，不派活
 *
 * **不注入必答清单**。把判定全集拆成一张表要求逐行裁、门禁再逐行核对键与引文，
 * 会有三件事：裁决量随材料条数涨而判断不增加；证据列退化成把清单里的字抄一遍；
 * 判据从「这条要求是不是本需求的设计」滑向「这行有没有被裁过」——后者是格式，前者才是判断。
 *
 * 只给三样：判断的真源在哪、按什么判、结论写成什么。裁多少行由 verifier 按需要定，
 * 机械层不数行数、不核引文、不排相似度——那些都是拿字符串近似语义。
 *
 * ## 注入不等于执行
 *
 * 本阶段审查报告的形态由 post_check 核（`verifier-report.mjs`：结果块在不在、判据齐不齐），
 * 身份与结论由原生 `check-receipt` 核。审查得对不对由人抽查。
 *
 * 契约：stdin JSON ctx → stdout JSON { promptFragments: string[] }。
 */
import * as path from 'node:path';
import { phaseArtifacts } from './contracts.mjs';
import { activeKnowledge, knowledgeGuide } from './knowledge.mjs';
import { carriedBy, entryOf, featureKnowledge } from './knowledge-application.mjs';
import { knowledgeTask } from './knowledge-task.mjs';
import { obligationsFromContracts } from './obligations.mjs';
import { extensionRoot, readTextOrNull, relDisplay } from './paths.mjs';
import { designStatPoints, planStatRows, pointKey, statDelivery } from './stat-points.mjs';
import { overlayChecks } from './verifier-report.mjs';

/** 知识类判据的命名前缀 —— 只用来决定这一段要不要讲「知识判断在哪份文件里」。 */
const KNOWLEDGE_CHECK_PREFIX = 'knowledge_';

/** 本阶段被审的知识判断在哪。spec 自己判，plan 冻结成契约上的 must，之后各阶段按它落实与取证。 */
const SOURCE_OF_TRUTH = {
  spec: { file: 'acceptance.yaml', what: '本施工单位承接的适用判断（设计里的知识应用决定）有没有验收条目承接（`knowledge_rule` 与 `knowledge_decision_id`）' },
  plan: { file: 'contracts.yaml', what: '每条承接的适用判断挂在哪个实体上（`must`，带 `decision_id`）、选中模式的角色由哪个实体承担（`pattern_roles`）' },
  coding: { file: 'contracts.yaml', what: '契约实体上的每条 `must`，代码里有没有落实' },
  review: { file: 'contracts.yaml', what: '契约实体上的每条 `must`，复核表里一处落点一行的结论' },
  ut: { file: 'contracts.yaml', what: '要单测证据的 `must`（`verify: ut / both`）与 `acceptance.yaml` 里桥到规约的验收条目' },
  testing: { file: 'contracts.yaml', what: '要实机证据的 `must`（`verify: device / both`）与 `acceptance.yaml` 里桥到规约的验收条目' },
};

/** 审查先走通的产物与它交给下游的东西：spec 交 plan 设计，plan 交编码实现与验证。 */
const WALK = {
  spec: { what: '本施工单位的行为、边界与验收', handoff: 'plan 能据以设计：业务对象与动作、条件与结果、依据与具体的未决；'
    + '关键结论有源材料、已准入设计或已定决定支持；适用规约要求的行为与验证责任在验收里有条目承接' },
  plan: { what: '设计、`contracts.yaml` 与 `use-cases.yaml`',
    handoff: '编码能据以实现与验证：按每个业务结果走通接口的输入、返回、状态与调用，返回类型在本次契约或可定位的现有类型里存在，'
      + '选中模式要的角色由真实实体承担，用户动作与业务状态在 use-cases 里实际存在；'
      + '设计里的专项明细（如统计点、数据策略）落到了承担它的方法与实体上；'
      + 'use-cases 引的验收与方法在 acceptance 与 contracts（或已核的外部接口）里找得到，找不到是实现断链' },
};

/** 表格一格：竖线转义、换行压成空格，空值写「—」。 */
const cell = (value) => String(value ?? '').replace(/\|/g, '\\|').replace(/\s*\r?\n\s*/g, ' ').trim() || '—';

/**
 * spec：本施工单位承接的判断一条一行，原条目与判定、要求与落点并列；审查对着原文核验收是否承接了它们。
 */
function decisionTable(projectRoot, feature, knowledge, inputs) {
  const judged = featureKnowledge(projectRoot, feature, inputs.contracts);
  const rows = carriedBy(judged.rows, judged.scope);
  const gaps = judged.problems.map(p => `- **设计缺口**：${p}`);
  if (!rows.length) return [`${judged.label} 里没有本施工单位承接的知识判断。`, ...gaps];
  return ['| 决定 | 知识单元 | 原文 | 判定 | 要求与理由 | 落点 |', '|---|---|---|---|---|---|',
    ...rows.map(d => `| ${d.decision_id} | ${d.knowledge.unit} | ${cell(entryOf(knowledge, d)?.constraint ?? '（模式，见知识任务原文）')} `
      + `| ${d.knowledge.outcome} | ${cell([d.knowledge.requirement, d.rationale].filter(Boolean).join('；'))} | ${cell(d.knowledge.target_refs.join('、'))} |`),
    ...gaps];
}

/**
 * plan 及之后：每条出现过的规约一行，原条目与契约上挂着它的全部 `must` 并列。
 * 审查判「must 是不是这条规约要求的那件事、是否改变了规约原义」，要对着原文判。
 */
function obligationTable(projectRoot, feature, knowledge, inputs) {
  const contracts = inputs.contracts;
  if (!contracts) return [`**契约拿不到**：${inputs.why}——原义与 must 无从并列，未验证。`];
  const musts = obligationsFromContracts(contracts).filter(o => o.rule);
  if (!musts.length) return ['契约上一条 `must` 都没有。'];
  // 条目按义务出自的判断找（来源文件 + 单元）：不同文件同编号的规约各成一行
  const decisions = new Map(featureKnowledge(projectRoot, feature, contracts).rows.map(d => [d.decision_id, d]));
  const groups = new Map();
  for (const o of musts) {
    const key = `${o.rule}\0${o.decisionId ?? ''}`;
    groups.set(key, [...(groups.get(key) ?? []), o]);
  }
  const rows = ['| 编号 | 约束原文 | 命中后要给出 | 附注 | 契约上的 must（实体：要落实成什么 · verify · 出自的决定） |',
    '|---|---|---|---|---|'];
  for (const list of groups.values()) {
    const e = entryOf(knowledge, decisions.get(list[0].decisionId));
    const cells = list.map(o => `${o.entityPath}：${o.text || '（没写 text）'} · ${o.verify || '—'} · ${o.decisionId || '（没写 decision_id）'}`);
    rows.push(`| ${list[0].rule} | ${cell(e?.constraint ?? '（认不回判断的来源条目）')} | ${cell(e?.handling)} | ${cell(e?.note)} `
      + `| ${cells.map(cell).join('<br>')} |`);
  }
  return rows;
}

/**
 * plan：蓝图埋点明细的每个统计点与 plan.md 逐点表里同名的全部结果行并列，对不上的两边各自单列。
 * 设计没给统计设计时如实说缺在哪。
 */
function statPointTable(projectRoot, feature, inputs) {
  const judged = featureKnowledge(projectRoot, feature, inputs.contracts);
  const design = designStatPoints(judged);
  if (design.state === 'none' || design.state === 'missing') return [`${design.why}：埋点这一项按本阶段原有要求审，不另立缺口。`];
  if (design.state === 'empty') return ['蓝图的埋点明细里没有统计点表：统计设计结构待补——按设计缺口判，plan 行无从对齐。'];
  const planText = inputs.dir && readTextOrNull(path.join(inputs.dir, 'plan', 'plan.md'));
  if (planText === null || planText === undefined || planText === '') {
    // 没有 plan.md：逐点表的一致性不适用，埋点义务照样逐点审——对着契约方法说明与验收
    return [...statDelivery(judged, inputs.contracts, inputs.acceptance), '',
      '这一次没有 plan.md：逐点核每个统计点在契约方法说明与验收里有没有写出适用结果与验证方式，缺哪个点名哪个。'];
  }
  const plan = planStatRows(planText);
  const byKey = new Map();
  for (const r of plan) byKey.set(pointKey(r.point), [...(byKey.get(pointKey(r.point)) ?? []), r]);
  const consumed = new Set();
  const rows = ['| 埋点明细 | 设计的这一行 | plan 的结果行 |', '|---|---|---|'];
  for (const d of design.details) {
    for (const r of d.rows) {
      const key = pointKey(r[0]);
      const got = byKey.get(key) ?? [];
      consumed.add(key);
      rows.push(`| ${cell(d.title)} | ${cell(r.join(' ／ '))} | `
        + `${got.length ? got.map(x => cell(x.cells.join(' ／ '))).join('<br>') : '（plan 没有这个统计点）'} |`);
    }
  }
  for (const [key, got] of byKey) {
    if (!consumed.has(key)) for (const x of got) rows.push(`| — | （设计没有这个统计点） | ${cell(x.cells.join(' ／ '))} |`);
  }
  rows.push('', '并列的每一行按读者含 plan 的那一篇知识核：项目规则算得出的字段是不是具体值，'
    + '那一篇要求的角色在契约里都有承载它的实体与方法。');
  return rows;
}

/**
 * 本阶段全部判据与报告结构 —— overlay 里的每一条都进请求，逐条出结论。
 *
 * framework 的任务清单只列它自己的判据，overlay-only 的项不由它送；这里不送的那一条就不是任务。
 * 报告结构写在请求里：格式不合的回复不计结论。
 */
function allChecksFragment(checks) {
  const rows = Object.entries(checks).map(([id, c]) => {
    const first = String(c?.description ?? '').replace(/\s+/g, ' ').trim().split(/(?<=[。；])/)[0];
    return `- \`${id}\`（${c?.severity ?? '未定级'}）：${first}`;
  });
  return ['## 本阶段全部判据（逐条出结论）', '', ...rows, '',
    '**报告结构**：汇总表每条判据一行，四格 `id | status | severity | 证据`，PASS 也列、证据不空；',
    'status ≠ PASS 的在 YAML 明细 `checks:` 里各出一条，`details` 写问题、依据与改法；',
    '末尾恰好一个 `maison-verifier-result:v1` 终态块。缺一条判据的报告按阻断处理。'].join('\n');
}

/**
 * 审查者的知识任务：与作者动笔前取的是同一个加载器，受众换成审查者。
 * 取不到时写明缺口与责任，审查按未验证处理依赖知识的部分。
 */
function reviewerKnowledge(ctx) {
  try {
    return knowledgeTask(ctx.projectRoot, { action: ctx.phase, audience: 'reviewer', feature: ctx.feature });
  } catch (e) {
    return ['## 知识任务（取不到）', '', String(e?.message ?? e),
      '', '依赖知识的判断写未验证，并在结论里点名上面的缺口。'].join('\n');
  }
}

export default async function preVerifier(ctx) {
  const phase = ctx?.phase;
  if (!phase || !ctx?.feature || !ctx?.projectRoot) return {};
  const source = SOURCE_OF_TRUTH[phase];
  if (!source) throw new Error(`hooks/shared/pre_verifier.mjs 的 SOURCE_OF_TRUTH 没有阶段「${phase}」——manifest 给哪些阶段登记了 pre_verifier，这张表就按阶段写明被审的知识判断在哪份文件`);
  const { checks, error } = overlayChecks(ctx.projectRoot, phase);
  const checkIds = Object.keys(checks);
  if (error) {
    return {
      promptFragments: [[
        '## 实例扩展知识判据（清单读取失败，须人工确认）',
        '',
        `无法确定本阶段该产出哪些判据结论：${error}。`,
        '',
        '**这不是「本阶段没有扩展判据」**——请打开本阶段的 overlay 自行确认判据清单，',
        `再按 \`${source.file}\` 里的判断逐项审查。`,
      ].join('\n')],
    };
  }

  const knowledgeIds = checkIds.filter(id => id.startsWith(KNOWLEDGE_CHECK_PREFIX));
  const inputs = phaseArtifacts(ctx.projectRoot, ctx.feature, phase);
  const fragments = [];
  let knowledge = null;
  let knowledgeGap = '';
  try {
    knowledge = activeKnowledge(ctx.projectRoot);
  } catch (e) {
    knowledgeGap = e.message;
  }
  const table = !knowledge ? [`**激活知识派生失败**：${knowledgeGap}——原义无从并列，按规约文件逐条读，结论写未验证的部分。`]
    : !knowledge.entries.length ? ['激活清单里没有规约条目。']
      : phase === 'spec' ? decisionTable(ctx.projectRoot, ctx.feature, knowledge, inputs)
        : obligationTable(ctx.projectRoot, ctx.feature, knowledge, inputs);

  fragments.push(allChecksFragment(checks));
  fragments.push(reviewerKnowledge(ctx));
  if (!knowledgeIds.length) return { promptFragments: fragments };

  const fragment = [
    '## 实例扩展知识判据（BLOCKER）',
    '',
    `本阶段被审的知识判断在 **\`${source.file}\`**：${source.what}。`,
    '**材料、原知识与仓内事实是审查依据，本阶段产物与这份判断是被审的对象**——下表把每条规约的原条目与当前判断并列，',
    '对着原文判，不拿判断自证。',
    '',
    ...(knowledge ? knowledgeGuide(ctx.projectRoot, knowledge)
      : [`知识没能加载：${knowledgeGap}——依赖知识的检查写未验证，不当作没有知识。`]),
    '',
    ...(knowledge?.constraints?.length
      ? ['下表只有主表一行；规约的落法附注同样是要求，原文在：'
        + knowledge.constraints.map(c => '`' + relDisplay(ctx.projectRoot,
          path.join(extensionRoot(ctx.projectRoot), c.file)) + '`').join('、')]
      : []),
    '',
    ...table,
    '',
    ...(phase === 'plan' ? [
      '埋点逐统计点并列（按统计点名对齐）：', '', ...statPointTable(ctx.projectRoot, ctx.feature, inputs), '',
      knowledge?.facts.length ? '要用到的已有能力、字段与取值规则，按上面列出的项目事实核。'
        : '激活清单里没有项目事实：取值不对照项目规则核，只核与知识无关的几件事。', ''] : []),
    '**先走业务，再核交接**（登记齐不齐、编号在不在册，机械层已经核过）：',
    '',
    `1. **按业务流程走通${(WALK[phase] ?? { what: '本阶段产物' }).what}**：实际会发生的正常、异常与未执行路径各走到哪，`
      + '结果由谁、凭什么得到。走不通的地方点名断在哪一步。',
    `2. **核本阶段交付够不够下游用**：${(WALK[phase] ?? { handoff: '下游能据以继续' }).handoff}。未知要具体而真实。`,
    '   缺口按对下游的影响定级：下游要重新决定接口结构、核心业务行为或必要取值的，相关条目 FAIL；'
      + '措辞与局部优化才是 advisory / WARN。概述写得长不等于交付够用。',
    '3. **核知识判断落到了本阶段产物**，上表是追溯入口：适用的要求在本阶段产物里落地了吗，落点是不是真的做这件事的实体（借挂、夹带点名）；',
    '   判断本身有问题（不适用的依据回查不到事实、豁免缺理由或补偿）时，指出来交设计负责方，不在本阶段改判；',
    '   项目事实登记的能力复用了吗；选中模式的角色由真实的分支、步骤与实体承担吗。',
    '   通用措辞也可以准确，专门措辞也可能错，按内容判。',
    '',
    '**审查方式**：本阶段判据逐项核，按上面的报告结构给汇总；知识应用的判断逐条核到，有问题的那几条讲清问题与依据，',
    '没问题的写一句结论，不必复述原文。',
    '',
    '### 输出要求（BLOCKER）',
    '',
    `在输出 YAML 的 \`checks:\` 中，为 ${knowledgeIds.map(id => `\`${id}\``).join(' 与 ')} 各追加一条，`,
    '`details` 写你判出问题的那几条：是哪一条、问题是什么、依据是产物或材料里的什么事实。',
    '判不出问题就写清你按什么看过、看了哪几条。相应调整 `summary.total` 与计数。',
  ].join('\n');

  fragments.push(fragment);
  return { promptFragments: fragments };
}
