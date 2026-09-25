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
 * 读者审查的报告有没有落盘由交付门核（`verifier-report.mjs`，调用方是 `delivery.mjs`），
 * 核的是形态：结果块在不在、结论分类齐不齐。审查得对不对由人抽查。
 *
 * 契约：stdin JSON ctx → stdout JSON { promptFragments: string[] }。
 */
import * as path from 'node:path';
import { readContracts } from './contracts.mjs';
import { activeKnowledge, knowledgeGuide } from './knowledge.mjs';
import { readUse, requirements, UseError } from './knowledge-use/document.mjs';
import { obligationsFromContracts } from './obligations.mjs';
import { extensionRoot, featureRoot, readTextOrNull, relDisplay } from './paths.mjs';
import { readerReviewTask } from './reader-review-task.mjs';
import { overlayChecks } from './verifier-report.mjs';
import { planStatRows, pointKey, specStatPoints, statDesignState } from './stat-points.mjs';
import { isStoryFeature } from '../../skills/story/scripts/core/flow/check.mjs';

/** 知识类判据的命名前缀 —— 只用来决定这一段要不要讲「知识判断在哪份文件里」。 */
const KNOWLEDGE_CHECK_PREFIX = 'knowledge_';

/** 读者审查那一项。它要的输入与问题清单与知识判据不同，单独成段。 */
const READER_REVIEW_ID = 'story_reader_review';

/** 本阶段被审的知识判断在哪。spec 自己判，plan 冻结成契约上的 must，之后各阶段按它落实与取证。 */
const SOURCE_OF_TRUTH = {
  spec: { file: 'spec/knowledge-use.yaml', what: '每条规约命中与否、命中的要求做什么、模式有哪些候选' },
  plan: { file: 'contracts.yaml', what: '每条命中的规约挂在哪个实体上（`must`）、模式选了哪几个（`files[].pattern`）' },
  coding: { file: 'contracts.yaml', what: '契约实体上的每条 `must`，代码里有没有落实' },
  review: { file: 'contracts.yaml', what: '契约实体上的每条 `must`，复核表里一处落点一行的结论' },
  ut: { file: 'contracts.yaml', what: '要单测证据的 `must`（`verify: ut / both`）与 `acceptance.yaml` 里桥到规约的验收条目' },
  testing: { file: 'contracts.yaml', what: '要实机证据的 `must`（`verify: device / both`）与 `acceptance.yaml` 里桥到规约的验收条目' },
};

/** 审查先走通的产物与它交给下游的东西：spec 交 plan 设计，plan 交编码实现与验证。 */
const WALK = {
  spec: { what: '业务章与承载专项的那一章', handoff: 'plan 能据以设计：业务对象与动作、条件与结果、依据与具体的未决；'
    + '关键结论有源材料或已定决定支持，`decisions.json` 里仍 open 的选择没有写成无条件的行为或验收；'
    + '统计设计的指标小节标题是指标名、有定义段与带统计点的表，按读者含 spec 的那一篇知识核，判不过的写出是哪一处；'
    + '命中的规约要求讲清某项专项时，按那份知识核承载章里的相应设计' },
  plan: { what: '设计章、`contracts.yaml` 与 `use-cases.yaml`',
    handoff: '编码能据以实现与验证：按每个业务结果走通接口的输入、返回、状态与调用，返回类型在本次契约或可定位的现有类型里存在，'
      + '选中交互模式要的用户动作与业务状态在 use-cases 里实际存在；'
      + '每个统计点的每种结果有责任方法，读者含 plan 的那一篇知识要求的字段有实际值或按其规则得出的值及来源，指标口径引用 spec；'
      + 'use-cases 引的验收与方法在 acceptance 与 contracts（或已核的外部接口）里找得到，找不到是实现断链' },
};

/**
 * plan：spec §9.1.4 的每个统计点与 plan 埋点小节里同名的全部结果行并列，对不上的两边各自单列。
 * 同一统计点被几个指标共用时，每个指标下都列出同一组 plan 行。spec 没给统计设计时如实说缺在哪。
 */
function statPointTable(projectRoot, feature) {
  const dir = featureRoot(projectRoot, feature);
  const spec = readTextOrNull(path.join(dir, 'spec', 'spec.md'));
  const points = spec === null ? null : specStatPoints(spec);
  const state = statDesignState(points);
  if (state === 'missing') {
    return [isStoryFeature(dir) ? 'spec 缺埋点一节：上游没有交出统计设计，plan 的埋点无从承接——按 spec 缺口判。'
      : '本需求没走 /story，spec 未提供统计设计：埋点这一项按本阶段原有要求审，不另立缺口。'];
  }
  if (state === 'na') return [`spec 埋点一节写的是「${points.na}」：核这条依据是否成立、plan 是否同样写了不涉及。`];
  if (state === 'empty') return ['spec 埋点一节没有指标点位表：统计设计结构待补——按 spec 缺口判，plan 行无从对齐。'];
  const plan = planStatRows(readTextOrNull(path.join(dir, 'plan', 'plan.md')) ?? '');
  const byKey = new Map();
  for (const r of plan?.rows ?? []) byKey.set(pointKey(r.point), [...(byKey.get(pointKey(r.point)) ?? []), r]);
  const consumed = new Set();
  const rows = ['| 指标 | spec 的这一行 | plan 的结果行 |', '|---|---|---|'];
  for (const g of points.groups) {
    for (const r of g.rows) {
      const key = pointKey(r[0]);
      const got = byKey.get(key) ?? [];
      consumed.add(key);
      rows.push(`| ${cell(g.title)} | ${cell(r.join(' ／ '))} | `
        + `${got.length ? got.map(x => cell(x.cells.join(' ／ '))).join('<br>') : '（plan 没有这个统计点）'} |`);
    }
  }
  for (const [key, got] of byKey) {
    if (!consumed.has(key)) for (const x of got) rows.push(`| — | （spec 没有这个统计点） | ${cell(x.cells.join(' ／ '))} |`);
  }
  rows.push('', '并列的每一行按读者含 plan 的那一篇知识核：项目规则算得出的字段是不是具体值，'
    + '那一篇要求的角色在契约里都有承载它的实体与方法。');
  return rows;
}

/** 表格一格：竖线转义、换行并成一行，空的写一横。 */
const cell = (value) => String(value ?? '').replace(/\|/g, '\\|').replace(/\s*\r?\n\s*/g, ' ').trim() || '—';

/**
 * spec 阶段：每条激活规约一行，原条目的每一栏与作者判断并列——包括不命中、整域不适用与豁免。
 * 原要求本身必须在表里：审查判「reason 说的是不是命中条件里的事实」「要求有没有偏离原义」，要对着原文判。
 */
function specJudgementTable(projectRoot, feature, knowledge) {
  let use = null;
  let gap = '';
  try {
    use = readUse(projectRoot, feature);
  } catch (e) {
    if (!(e instanceof UseError)) throw e;
    gap = e.message;
  }
  const byId = new Map((use?.constraints ?? []).map(r => [String(r?.id ?? '').trim(), r]));
  const na = new Map((use?.domains ?? []).map(r => [String(r?.prefix ?? '').trim(), r]));
  const rows = ['| 编号 | 强制力 | 约束原文 | 命中条件 | 命中后要给出 | 附注 | 作者判断 | 落点 |',
    '|---|---|---|---|---|---|---|---|'];
  for (const e of knowledge.entries) {
    const r = byId.get(e.id);
    const d = na.get(e.prefix);
    const judged = !use ? '未取得，未验证'
      : d ? `整域不适用：${d.reason ?? ''}`
        : !r ? '（没有去处）'
          : r.applicable === false ? `不命中：${r.reason ?? ''}`
            : r.applicable !== true ? `applicable 写的是「${r.applicable}」`
              : r.waived ? `命中·本轮豁免：${r.waived?.reason ?? ''}${r.waived?.compensation ? `；补偿：${r.waived.compensation}` : ''}`
                : `命中：${(e.reviewAction ? [r.reason] : requirements(r)).filter(Boolean).join('；')}`;
    const landing = !r ? '—' : r.contract ? `§9.1 · ${r.contract}` : r.impact ? `影响 · ${r.impact}`
      : r.decision ? `议题 ${r.decision}` : '—';
    rows.push(`| ${e.id} | ${cell(e.force)} | ${cell(e.constraint)} | ${cell(e.when)} | ${cell(e.handling)} `
      + `| ${cell(e.note)} | ${cell(judged)} | ${cell(landing)} |`);
  }
  return gap ? [`**作者判断读不到**：${gap}——下表的判断一栏是未验证，不替它下结论。`, '', ...rows] : rows;
}

/**
 * plan 及之后：每条出现过的规约一行，原条目与契约上挂着它的全部 `must` 并列。
 * 审查判「must 是不是这条规约要求的那件事、是否改变了规约原义」，要对着原文判。
 */
function obligationTable(projectRoot, feature, knowledge) {
  const { contracts, error, exists } = readContracts(projectRoot, feature);
  if (error || !exists) return [`**契约读不到**：${error ?? '缺 contracts.yaml'}——原义与 must 无从并列，未验证。`];
  const musts = obligationsFromContracts(contracts);
  const ruleIds = [...new Set(musts.map(o => o.rule).filter(Boolean))];
  if (!ruleIds.length) return ['契约上一条 `must` 都没有。'];
  const byId = new Map(knowledge.entries.map(e => [e.id, e]));
  const rows = ['| 编号 | 约束原文 | 命中后要给出 | 附注 | 契约上的 must（实体：要落实成什么 · verify） |',
    '|---|---|---|---|---|'];
  for (const id of ruleIds) {
    const e = byId.get(id);
    const list = musts.filter(o => o.rule === id).map(o => `${o.entityPath}：${o.text || '（没写 text）'} · ${o.verify || '—'}`);
    rows.push(`| ${id} | ${cell(e?.constraint ?? '（不在激活清单）')} | ${cell(e?.handling)} | ${cell(e?.note)} `
      + `| ${list.map(cell).join('<br>')} |`);
  }
  return rows;
}

/**
 * 本阶段全部判据与报告结构 —— overlay 里的每一条都进请求，逐条出结论。
 *
 * framework 的任务清单只列它自己的判据，overlay-only 的项不由它送；这里不送的那一条就不是任务。
 * 报告结构写在请求里：格式不合的回复会被存为被拒回复，不计结论。
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

export default async function preVerifier(ctx) {
  const phase = ctx?.phase;
  if (!phase || !ctx?.feature || !ctx?.projectRoot) return {};
  const source = SOURCE_OF_TRUTH[phase];
  if (!source) throw new Error(`pre_verifier 不认识阶段「${phase}」：manifest 登记它的阶段要在 SOURCE_OF_TRUTH 里有一项`);
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
      : phase === 'spec' ? specJudgementTable(ctx.projectRoot, ctx.feature, knowledge)
        : obligationTable(ctx.projectRoot, ctx.feature, knowledge);

  fragments.push(allChecksFragment(checks));
  // 读者审查放在判据清单之后：它要通读整份归档件与全部材料，是这批判据里最重的一项。
  if (checkIds.includes(READER_REVIEW_ID)) {
    fragments.push(readerReviewTask(ctx.projectRoot, ctx.feature, READER_REVIEW_ID));
  }
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
      '埋点逐统计点并列（按统计点名对齐）：', '', ...statPointTable(ctx.projectRoot, ctx.feature), '',
      knowledge?.facts.length ? '要用到的已有能力、字段与取值规则，按上面列出的项目事实核。'
        : '激活清单里没有项目事实：取值不对照项目规则核，只核与知识无关的几件事。', ''] : []),
    '**先走业务，再核交接**（登记齐不齐、编号在不在册，机械层已经核过）：',
    '',
    `1. **按业务流程走通${(WALK[phase] ?? { what: '本阶段产物' }).what}**：实际会发生的正常、异常与未执行路径各走到哪，`
      + '结果由谁、凭什么得到。走不通的地方点名断在哪一步。',
    `2. **核本阶段交付够不够下游用**：${(WALK[phase] ?? { handoff: '下游能据以继续' }).handoff}。未知要具体而真实。`,
    '   缺口按对下游的影响定级：下游要重新决定接口结构、核心业务行为或必要取值的，相关条目 FAIL；'
      + '措辞与局部优化才是 advisory / WARN。概述写得长不等于交付够用。',
    '3. **核知识判断与设计一致**，上表是追溯入口：命中的要求在设计里落地了吗，落点是不是真的做这件事的实体（借挂、夹带点名）；',
    '   不适用的依据能回查到命中条件里的事实吗（「不涉及」不是依据）；豁免有没有理由、影响与补偿；',
    '   项目事实登记的能力复用了吗；模式候选的单元与信号、采用模式的角色投影指向真实的分支、步骤与实体吗。',
    '   通用措辞也可以准确，专门措辞也可能错，按内容判。',
    '',
    '**不要做的事**：不逐条对账、不出裁决表、不为每条结论找一段够长的引文。',
    '那些做法的产物是把真源里的字抄一遍，抄的量随材料条数涨，读者得到的判断不增加。',
    '有问题的那几条讲清楚为什么，没问题的不必逐条复述。',
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
