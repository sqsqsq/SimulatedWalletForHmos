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
 * 输出只读；唯一副作用：作者取 Feature 阶段的正式任务（范围已冻结）就是开始这一阶段的工作，命令入口记一笔使用记录的
 * begin（被导入的渲染函数与审查者、预览、蓝图动作都不记）。记不上只在 stderr 说明，任务照常给出。
 * 退出 0 输出完整任务；1 为坏身份、坏知识登记或所需来源缺失（stdout 不给半份，stderr 写对象、缺口、责任）；
 * 2 为参数或依赖错误。空清单合法，明示零项。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { activation, blueprintKnowledge, entryOf, featureKnowledge, knowledgeContext, knowledgeSource, rolesOf, unitContext,
  unitDuties } from './knowledge-application.mjs';
import { loadNative, readBlueprint, readFeature, readSourceFiles } from './framework-access.mjs';
import { activeKnowledge, HALVES, knowledgeRegistrations, selfCheck } from './knowledge.mjs';
import { obligationsFromContracts, patternRolesFromContracts, verifyChoices } from './obligations.mjs';
import { firstReadBoundary, firstReadCarrier, nativeEightQuestions, questioningRound } from './questioning.mjs';
import { statDelivery } from './stat-points.mjs';
import { extensionRoot, featureRoot, relDisplay } from './paths.mjs';
import { recordUsage } from './usage.mjs';
import { requiredAnswers, unitSources } from '../../skills/story/scripts/core/story/design-source.mjs';
import { requirementContext } from '../../skills/story/scripts/core/story/context.mjs';
import { normalizeHeading, storySpan } from '../../skills/story/scripts/core/story/document.mjs';
import { basisSections, useEffectiveChapters } from '../../skills/story/scripts/core/story/writing-plan.mjs';

const BLUEPRINT_ACTIONS = ['discovery', 'design', 'questioning'];
const FEATURE_ACTIONS = ['spec', 'plan', 'coding', 'review', 'ut', 'testing'];
const AUDIENCES = ['author', 'reviewer'];
/** 蓝图的设计动作：判断全局适用性，正文全部送。 */
const DESIGN_SIDE = new Set(['discovery', 'design', 'questioning']);
/** 上下篇知识送哪一篇：上篇给设计与行为验收（蓝图动作与 spec），下篇给实现侧。 */
const UPPER_HALF = new Set([...DESIGN_SIDE, 'spec']);

class TaskError extends Error {}
const stop = (object, gap, owner) => { throw new TaskError(`对象：${object}\n缺口：${gap}\n责任：${owner}`); };

/**
 * 这一登记在本动作送不送。Feature 阶段按 manifest 的受众语义：字符串登记给全部 Feature 阶段，对象登记给
 * `global` 或列出的阶段；蓝图的设计动作要看全局，登记的都送，相关与否由模型按「何时读」判断。
 */
const reaches = (registration, action) => !FEATURE_ACTIONS.includes(action) || registration.audience === null
  || registration.audience === 'global' || (Array.isArray(registration.audience) && registration.audience.includes(action));

/** 激活知识：读不出按知识维护者的缺口报。 */
function loadKnowledge(root) {
  try {
    return activeKnowledge(root);
  } catch (e) {
    return stop('扩展 manifest 的知识激活清单', e.message, '目标工程的知识维护者（按 skills/story/reference/knowledge/protocol.md 修正登记或文件）');
  }
}

/**
 * Feature 本动作直接送正文的知识文件（扩展根相对路径）：本单位承担或判过的规约与模式、本单位设计引用的事实、
 * 需求级的评审动作与归属未定的判断，以及本阶段契约与验收实际引用的知识。蓝图动作返回 null（全部送）。
 * 平铺维护 Feature 没有承接范围，送它判过的全部；它还一条判断都没有时由作者起步判断，同样返回 null。
 */
function relatedFiles(root, action, judged, spec, kind) {
  if (DESIGN_SIDE.has(action)) return null;
  if (kind !== 'cu' && judged && !judged.rows.length && !judged.facts.length) return null;
  const files = new Set();
  if (!judged) return files;
  const active = activation(root);
  const add = ref => { const source = ref ? knowledgeSource(active, ref) : null; if (source) files.add(source.file); };
  const context = unitContext(judged);
  for (const d of context.mine) files.add(d.file);
  for (const d of context.common) {
    if (d.outcome === 'pending' || (d.kind === 'constraints' && d.outcome === 'applied' && d.reviewAction)) files.add(d.file);
  }
  for (const f of context.facts) add(f.provenance?.source_ref);
  for (const m of obligationsFromContracts(spec?.contracts ?? null)) add(m.sourceRef);
  for (const r of patternRolesFromContracts(spec?.contracts ?? null)) add(r.patternRef);
  const acceptance = spec?.acceptance ?? null;
  for (const c of [...(acceptance?.criteria ?? []), ...(acceptance?.boundaries ?? [])]) {
    for (const ref of Array.isArray(c?.knowledge_refs) ? c.knowledge_refs : []) add(ref);
  }
  return files;
}

/** 一份知识送给本动作的正文：规约与分面事实整份；上下篇送文件前言与本动作的那一篇。`part` 是全文或那一篇。 */
function bodyFor(k, body, action) {
  if (k.form !== 'halves' || !k.halves) return { text: body, note: '全文', part: '全文' };
  const half = UPPER_HALF.has(action) ? HALVES[0] : HALVES[1];
  const head = body.search(new RegExp(`^#\\s+${HALVES[0]}\\s*·`, 'm'));
  const preface = head > 0 ? body.slice(0, head).trim() : '';
  return { text: [preface, k.halves[half].trim()].filter(Boolean).join('\n\n'), note: `前言与${half}（另一篇按位置读原文）`, part: half };
}

/**
 * 第 4 块：全局知识索引（激活清单的每份一行，不按受众筛）加本动作直接送的正文。正文先按登记的受众取本动作可达的，
 * `related` 为 null 时这些都送，否则只送其中的文件；相关文件被受众挡在本动作之外时报登记与消费者冲突，不静默少送。
 * `starter` 为真表示 Feature 还没有知识判断，正文供作者起步判断。
 * `documents` 是送了正文的每份知识（工程相对路径与全文 / 上篇 / 下篇），与正文同一循环得出。
 */
function knowledgeBlock(root, action, knowledge, related, starter = false) {
  const byFile = new Map([...knowledge.facts, ...knowledge.constraints, ...knowledge.patterns].map(k => [k.file, k]));
  const all = knowledgeRegistrations(root);
  const ordered = all.map(r => ({ ...byFile.get(r.file), registration: r })).filter(k => k.file);
  const rows = ['## 4. 激活知识：索引与本动作的原文', ''];
  const protocol = path.join(extensionRoot(root), 'skills', 'story', 'reference', 'knowledge', 'protocol.md');
  const gaps = [...(related ?? [])].filter(f => !all.some(r => r.file === f && reaches(r, action)))
    .map(f => `知识 \`${f}\` 是本单位判断或契约实际引用的，登记的受众里却没有 ${action}：登记与消费者冲突，交知识维护者修正激活清单`);
  if (!ordered.length) {
    return { rows: [...rows, `激活清单为空：这个工程还没有登记知识（零项）。知识怎么写、怎么登记见 \`${relDisplay(root, protocol)}\`。`], gaps, documents: [] };
  }
  const sent = ordered.filter(k => reaches(k.registration, action) && (related === null || related.has(k.file)));
  const where = k => relDisplay(root, path.join(extensionRoot(root), ...k.file.split('/')));
  rows.push(`激活 ${ordered.length} 份，按激活顺序；各列与形态怎么读见 \`${relDisplay(root, protocol)}\`。`
    + (starter ? `本 Feature 还没有知识判断：受众里有 ${action} 的 ${sent.length} 份正文都在下面，相关与否、适用与否由你判断，写进契约的 knowledge_facts。`
      : related === null ? `本动作判断全局适用性，受众里有 ${action} 的 ${sent.length} 份正文都在下面。`
        : `与本动作直接相关的 ${sent.length} 份正文在下面；其余按「何时读」判断，需要时按位置读原文。`), '');
  for (const k of ordered) {
    rows.push(`- \`${where(k)}\` · ${k.name ?? k.id}（${k.kind ?? k.file.split('/')[1] ?? ''}，${k.form}）· 单元：${k.units.join('、')}`
      + ` · 何时读：${String(k.appliesWhen ?? '').trim().split(/\s*\n\s*/).join(' ')}`
      + (k.registration.audience === null ? ''
        : ` · 登记：受众 ${JSON.stringify(k.registration.audience)}${k.registration.summary ? `，摘要「${k.registration.summary}」` : ''}`)
      + (sent.includes(k) ? '　（正文在下）' : ''));
  }
  rows.push('');
  if (related !== null && !sent.length && !gaps.length) {
    rows.push('本施工单位没有承接或判过的知识，契约与验收也没有引用知识：正文不送；按索引核有没有设计漏判的，漏判交设计负责方。', '');
  }
  const documents = [];
  for (const k of sent) {
    const file = path.join(extensionRoot(root), ...k.file.split('/'));
    const body = fs.readFileSync(file, 'utf8').replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, '').trim();
    const { text, note, part } = bodyFor(k, body, action);
    documents.push({ path: where(k), part });
    rows.push(`### ${k.name ?? k.id}（${k.file.split('/')[1] ?? ''}，${k.form}）`, '',
      `- 位置：\`${where(k)}\`（适用性事实的 provenance.source_ref；规约条目引用写 \`<位置>#<编号>\`）`,
      `- 单元：${k.units.join('、')}`, `- 何时读：${k.appliesWhen}`, `- 下面是：${note}`,
      '', '````markdown', text, '````', '');
  }
  return { rows, gaps, documents };
}

const factLine = f => `- 事实 \`${f.fact_id}\`（${f.provenance?.source_ref}）：${JSON.stringify(f.value)}`;
/** 一条规约或模式判断：哪份知识的哪一条、判定、理由与落点。 */
const judgedLine = d => `- \`${d.source_ref}\`（${d.kind === 'patterns' ? '模式' : d.domain ? '整域' : d.unit}，事实 ${d.fact_id}）`
  + ` → ${d.outcome}：${d.rationale ?? ''}${d.target_refs.length ? `；落在 ${d.target_refs.join('、')}` : ''}`
  + `${d.roles?.length ? `；角色 ${d.roles.map(r => `${r.role} → ${r.target_ref}`).join('、')}` : ''}`;

/** 蓝图里与知识相关的判断与事实：按知识应用的读法列出，判断归模型。 */
function judgedOf(checked) {
  return [...checked.rows.map(judgedLine), ...checked.facts.map(factLine)];
}

/**
 * spec / plan 第 2 块：本单位相关而不产生义务的判断、需求级公共依据与本单位引用的事实，宿主扩展章写不适用、不选与复用时
 * 引用其理由。作用域未确定的判断与指不到的引用另进缺口，交设计负责方，不当成已成立的全局要求。
 */
function unitLines(judged) {
  const context = unitContext(judged);
  const { applied, selected } = unitDuties(judged);
  const own = context.mine.filter(d => !applied.includes(d) && !selected.includes(d));
  const reviews = context.common.filter(d => d.kind === 'constraints' && d.outcome === 'applied' && d.reviewAction);
  const basis = context.common.filter(d => ['not_applicable', 'rejected'].includes(d.outcome));
  const other = context.common.filter(d => d.outcome !== 'pending' && !reviews.includes(d) && !basis.includes(d));
  const unowned = context.common.filter(d => d.outcome === 'pending');
  const lines = [
    ...(own.length ? ['本单位相关、不产生义务的判断（宿主扩展章引用其理由，不重判）：', ...own.map(judgedLine)] : []),
    ...(reviews.length ? ['需求级评审动作（适用，指向原生决定或需求级对象，由评审承接执行；不产生代码 must 或验收条目，'
      + '本阶段核它要的评审材料与执行是否齐备）：', ...reviews.map(judgedLine)] : []),
    ...(basis.length ? ['需求级公共依据（不适用或拒绝，没有落点，不产生本单位义务）：', ...basis.map(judgedLine)] : []),
    ...(other.length ? ['需求级判断（没有落点，按各行的判定读）：', ...other.map(judgedLine)] : []),
    ...(unowned.length ? ['归属待核的公共知识缺口（待定，只登记了原生决定或缺口，还没定由哪个设计对象承担）：核它是否落在本单位；'
      + '落在本单位的按决定此刻的效力处理，未决的照原生决定或缺口的负责方等待或回报，不当作已生效的义务，也不当作豁免：',
    ...unowned.map(judgedLine)] : []),
    ...context.facts.map(factLine),
    ...(context.located.length ? [`需求里另有知识事实，与本单位的关联未明，只给定位：${context.located
      .map(f => `\`${f.fact_id}\`（${f.subject ?? ''}）`).join('、')}`] : []),
  ];
  return { lines, gaps: [] };
}

/**
 * 候选这一版实际采用的来源：每条声明（原引用、片段与声明摘要）按原生规则核过原字节，声明落在需求材料版本里的，
 * 再按版本展开成完整的采用文件（原件、阅读正文、图、人工答复，摘要取材料索引）。任一份读不到、摘要不符或版本没登记，
 * 不交半份任务。
 */
/**
 * 当前有效人答：独立必读，蓝图还没建立时设计作者也取得；导出落后于流程记录时不交任务，不拿旧导出顶替。
 * 需求目录里还没有流程契约（不是 Story 需求）时为空。
 */
function answerRows(root, id) {
  const dir = featureRoot(root, id);
  if (!fs.existsSync(path.join(dir, 'AR', 'story-src', 'story-flow.json'))) return [];
  const answers = requiredAnswers(requirementContext(root, dir));
  if (answers.problems.length) {
    stop(`需求 ${id} 的当前有效人答`, answers.problems.join('；'), '需求负责方按提示重试派生，答复本身不用重答');
  }
  const read = readSourceFiles(root, answers.files);
  if (read.problems.length) stop(`需求 ${id} 的当前有效人答`, read.problems.join('；'), '需求负责方恢复人答导出');
  return answers.files.length
    ? ['当前有效人答（必读，不取决于需求条目或设计引用有没有写它）：', ...answers.files.map(f => `- \`${f.path}\`（${f.role}），${f.sha256}`)]
    : [];
}

/**
 * 候选这一版实际依据的来源（读取结果的 `source_index`）：需求条目的声明按原生规则核原字节，设计依据（事实、设计对象、合同的 provenance）
 * 命中本需求登记文件的按版本展开成完整的采用文件；契约段引的权威文件由原生逐段核过，整份交读；冲突一方单列供核；当前有效人答独立必读。
 * 任一份读不到、摘要不符、引用不是登记文件或契约权威不完整，不交半份任务。
 */
function sourceIndex(root, id, bp) {
  const declared = bp.source_index;
  const read = readSourceFiles(root, [...declared.sources, ...declared.projectFiles]);
  const packs = declared.requirements.map(r => ({ ...r, ...readSourceFiles(root, [...r.files, ...r.conflictFiles]) }));
  const problems = [...declared.problems, ...read.problems, ...packs.flatMap(p => p.problems.map(x => `需求 ${p.requirement}：${x}`))];
  if (problems.length) {
    stop(`蓝图 ${id} 候选采用的来源`, problems.join('；'),
      '材料版本坏了由需求负责方恢复原件；设计记录、工程文件或引用变了由设计负责方按原生修订同步');
  }
  return [`候选声明 ${declared.sources.length} 条需求条目，原字节都与声明摘要一致：`,
    ...declared.sources.map(s => `- \`${s.item_id}\`（${s.kind}，${s.provenance?.evidence_strength ?? '未声明证据强度'}）：\`${s.path}\`，${s.sha256}`),
    ...(declared.support.length ? [`设计依据引用 ${declared.support.length} 处：`,
      ...declared.support.map(s => `- ${s.where}：\`${s.path}\``)] : []),
    ...(declared.projectFiles.length ? ['设计依据与冲突依据引用的工程文件与设计记录，逐份读：',
      ...declared.projectFiles.map(f => `- \`${f.path}\`（${f.role === 'design_file' ? '设计记录，' : ''}${f.use === 'conflict' ? '冲突依据' : '支撑依据'}，${f.where}），${f.sha256}`)] : []),
    ...(declared.authorityFiles.length ? ['契约段引用的权威文件（接口转写或映射；指针与内容由原生逐段核对），逐份读：',
      ...declared.authorityFiles.map(f => `- \`${f.path}\`，${f.sha256}，被 ${f.refs.length} 处引用（${f.refs.slice(0, 3).map(r => r.where).join('、')}${f.refs.length > 3 ? ' 等' : ''}）`)] : []),
    ...packs.flatMap(p => [`需求 \`${p.requirement}\` 采用的材料版本 ${p.versions.join('、') || '（没有）'}，共 ${p.files.length} 份，逐份读：`,
      ...p.files.map(f => `- \`${f.path}\`（${f.role}），${f.sha256}`),
      ...(p.conflictFiles.length ? ['冲突依据（蓝图登记的冲突一方，没被采用，核取舍）：', ...p.conflictFiles.map(f => `- \`${f.path}\`（${f.role}），${f.sha256}`)] : [])]),
    ...answerRows(root, id)];
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
  const sources = bp ? sourceIndex(root, id, bp)
    : ['蓝图尚未建立，还没有候选采用的来源：需求的当前阅读稿（`RR/prd.md`、`SR/design.md` 等）与登记的材料版本见材料索引 `AR/story-src/materials.json`，从那里起手。', ...answerRows(root, id)];
  const checked = bp ? blueprintKnowledge(root, bp.blueprint) : null;
  const decided = checked ? judgedOf(checked) : [];
  if (checked) gaps.push(...checked.problems.map(p => `${p}——设计作者处理。`));
  const duties = ['设计阶段还没有施工契约；知识的适用性写成蓝图的原生事实，适用规约的义务与模式角色写在承担它的设计对象上，'
    + '施工义务在施工单位的契约中承接。'];
  if (action !== 'questioning') {
    duties.push('这一轮的知识输入身份，原样写进蓝图 `discovery.inputs.knowledge_context`（知识换了重取本任务、按新的一份替换）：', '',
      '```json', JSON.stringify(knowledgeContext(root), null, 2), '```');
  }
  const dispatch = [];
  if (action === 'questioning') {
    const round = questioningRound(root, bp, loadNative(root));
    duties.push('被评候选是上面这一版。你只读材料、逐项回复；蓝图由设计负责方按回复修订。',
    `原生质询范围，逐项唯一覆盖：${round.scopes.map(([ref, kind]) => `\`${ref}\`（${kind}）`).join('、')}。`,
    '每项回：问题、回答、证据、处置（answered_with_evidence / decided_with_authority / open_decision / blocker / not_applicable）、'
      + '责任方、验证去向，以及未决项与处置建议。');
    // 首读之后才读本任务：派给子代理的是只含人读稿、八问与阅读规则的载体，不是本任务
    dispatch.push(`把本任务全文原样存到 \`${round.task}\`，被评候选的原始字节存到 \`${round.candidate}\`；`
      + `子代理的最终回复原样存到 \`${round.reply}\`。三份都一字不改。`);
    if (bp.projection?.status === 'valid') {
      const boundary = firstReadBoundary(root, bp.projection.path);
      if (boundary.problem) {
        gaps.push(`${boundary.problem}：首读不成立，技术质询照本任务继续，回复披露这一点；原生投影的形状变了，交设计者核原生变更。`);
      }
      dispatch.push('下面的首读载体原样作为宿主隔离子代理的任务交出，不增删、不附本任务正文、来源或作者判断：', '',
        '````markdown', firstReadCarrier({ draft: bp.projection.path, task: round.task, reply: round.reply,
          questions: nativeEightQuestions(loadNative(root)), boundary }), '````');
    } else {
      gaps.push(`人读稿 \`${bp.projection?.path ?? 'component-blueprint.review.md'}\` ${bp.projection?.status === 'missing' ? '还没生成' : '与当前 revision 对不上'}：`
        + '质询先读人读稿——设计负责方先跑原生 `check:component-blueprint --write-review --json` 渲染，再重取本任务派审。');
    }
  }
  return {
    object,
    sources,
    facts: decided.length ? decided : [bp ? '蓝图里还没有知识的适用性事实。' : '蓝图尚未建立，没有已成立的判断。'],
    duties,
    dispatch,
    gaps,
    page: `hooks/blueprint/${action === 'questioning' ? 'reviewer' : 'author'}.md`,
  };
}

/**
 * 本施工单位要履行的知识判断：承接的适用规约（带要求、落点与这条允许的 verify）与选中模式在本单位的角色，
 * 先于知识原文交给作者。判断不在这里重做，原文按条目在第 4 块。
 */
function carriedDuties(judged, action, knowledge) {
  const { applied, selected } = unitDuties(judged);
  const out = [`本施工单位承接 ${applied.length} 条适用规约条目、${selected.length} 个选中模式（原文在第 4 块，按来源文件与单元找）：`];
  for (const d of applied) {
    const { executor, allowed } = verifyChoices(entryOf(knowledge, d));
    out.push(`- \`${d.source_ref}\`（事实 ${d.fact_id}）：${d.rationale ?? ''}；落在 ${d.target_refs.join('、')}`
      + (action === 'plan' ? `；承担它的实体写 must（source_ref 照抄这条），verify 取 ${allowed.join(' / ')}${executor ? `（规约声明要「${executor}」证据）` : ''}` : '')
      + (action === 'spec' ? '；验收写出它要求的可观察行为与验证责任，knowledge_refs 列这条' : ''));
  }
  for (const d of selected) {
    out.push(`- 模式 \`${d.ref}\`（事实 ${d.fact_id}）：本单位承担的角色 ${rolesOf(d, judged.scope).map(r => `${r.role} → ${r.target_ref}`).join('、') || '（无）'}`
      + (action === 'plan' ? '；承担角色的实体写 pattern_roles（pattern_ref 照抄这个模式）' : ''));
  }
  return { duties: applied.length || selected.length ? out : ['本施工单位没有承接的适用规约与选中模式。'], gaps: judged.problems };
}

//: 独立 spec / plan 入口要物化的本阶段投影：阶段 → 本地文件与原生规格里的那一份
const STAGE_OUTPUT = { spec: ['acceptance.yaml', 'acceptance'], plan: ['contracts.yaml', 'contracts'] };

/**
 * 施工单位独立进入 spec / plan、范围还没冻结、本阶段的投影还没物化到本地时：冻结之前先用原生
 * `prepare-blueprint-design --phase <阶段>` 只物化本阶段的那一份。冻结记下的是当时的输入身份，冻结后再物化会让它过期，
 * 所以冻结之后（含 runtime 的 run）一律直接消费原生解析的输入，不再准备。原生物化不覆盖已有合法产物，冲突时报出。
 */
function stagePreparation(f, feature, action) {
  const [file, part] = STAGE_OUTPUT[action] ?? [];
  if (f.identity.kind !== 'cu' || !file || f.scope !== 'not_frozen' || process.env.MAISON_GOAL_RUN_ID?.trim() || f.spec?.[part]) return null;
  return `冻结之前先物化本阶段的投影 ${file}：在 \`framework/harness\` 下跑`
    + ` \`npx ts-node scripts/prepare-blueprint-design.ts --feature ${feature} --phase ${action} --project-root <工程根>\`（只写本阶段这一份，不覆盖已有合法产物）；`;
}

/** 围栏包一段原文：外层比里面最长的反引号串多一个，原文照录不转义。 */
function verbatim(text) {
  const mark = '`'.repeat(Math.max(3, ...[...text.matchAll(/`+/g)].map(m => m[0].length + 1)));
  return [`${mark}markdown`, text, mark];
}

/**
 * 关联 Story 里与本施工单位相关的已定表达：写作设计里某一处的依据有原生地址落在本单位的设计责任内，
 * 就照录 Story 里那一处（标题之下的正文，含同节的图与表）与它的身份（需求、文件、章节名与内容摘要）。
 * 作者复用与审查核承诺用这同一份；身份不含行号，无关段落插入不改变它。
 *
 * Story 只在按成文登记仍是当前那一份时才交（`unitSources` / `storyCurrency`）；地址按蓝图的原生稳定地址认、
 * 归属按 `judged.scope`（原生目标关系）判；指不到的地址、坏骨架、定位不到或认不开的小节报缺口，不任选一处。
 *
 * @param {{scope: {has: (a: string) => boolean}, blueprint?: object}} judged 本命令已算好的设计判断
 * @returns {{rows: string[], gaps: string[]}}
 */
function storyExpression(root, feature, judged) {
  const src = unitSources(root, feature, judged.blueprint ? { blueprint: judged.blueprint, source_index: judged.source_index } : null);
  const gaps = src.problems.map(p => `关联 Story：${p}`);
  if (src.status !== 'ok' || !src.blueprint) return { rows: [], gaps };
  if (!src.stories.length) return { rows: ['本施工单位的输入不来自 Story（原生直接入口），没有可复用的已定表达。'], gaps };
  const addresses = loadNative(root).module('scripts/utils/blueprint-addressing.ts').stableAddressIndex(src.blueprint);
  const rows = [];
  for (const s of src.stories) {
    if (s.state !== 'current') {
      rows.push(`- 需求 \`${s.requirement}\` 的 Story 不作为当前可复用的依据${s.state === 'stale' ? '，是旧表达' : ''}：${s.why.join('；')}。`);
      continue;
    }
    const plan = useEffectiveChapters(s.ctx);
    if (plan.problems.length) {
      gaps.push(`关联 Story：需求 ${s.requirement} 的写作设计读不全，片段取不了：${plan.problems.join('；')}——需求作者修正后重新登记`);
      continue;
    }
    const story = src.documents.get(s.story);
    const chapters = s.ctx.contract?.chapters ?? [];
    const taken = [];
    for (const b of basisSections(plan).filter(x => x.refs.length)) {
      const where = [chapters.find(c => c.id === b.chapter)?.title ?? b.chapter, b.at, b.under].filter(Boolean);
      const bad = b.refs.filter(r => !addresses.has(r));
      if (bad.length) gaps.push(`关联 Story：需求 ${s.requirement} 写作设计「${where.join(' / ')}」的依据 ${bad.join('、')} 在蓝图里解析不了——需求作者核对`);
      if (!b.refs.some(r => addresses.has(r) && judged.scope.has(r))) continue;
      const span = storySpan(story, where[0], b.at, b.under);
      if (!span || span.ambiguous) {
        gaps.push(`关联 Story：需求 ${s.requirement} 写作设计「${where.join(' / ')}」在 ${s.story} 里`
          + `${span ? `认不开（${span.ambiguous.join('、')}）` : '找不到对应的章节'}——需求作者让骨架与正文同名`);
        continue;
      }
      if (taken.some(x => x.start <= span.start && span.end <= x.end)) continue;
      for (let k = taken.length - 1; k >= 0; k--) if (span.start <= taken[k].start && taken[k].end <= span.end) taken.splice(k, 1);
      taken.push({ ...span, where: where.map(normalizeHeading).join(' / ') });
    }
    if (!taken.length) {
      rows.push(`- 需求 \`${s.requirement}\` 的 Story（\`${s.story}\`）里，写作设计的依据没有落在本施工单位设计责任内的蓝图地址：`
        + '该表达与本单位未形成可确定的复用关联，按原生设计输入施工。');
      continue;
    }
    const lines = story.split(/\r?\n/);
    for (const x of taken.sort((p, q) => p.start - q.start)) {
      const text = lines.slice(x.start + 1, x.end).join('\n').trim();
      rows.push(`- 需求 \`${s.requirement}\` · \`${s.story}\` · ${x.where}：内容摘要 sha256:${crypto.createHash('sha256').update(text).digest('hex')}`,
        '', ...verbatim(text), '');
    }
  }
  return { rows, gaps };
}

function featureTask(root, feature, action, supplied, knowledge) {
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
  let judged = null;
  if (f.identity.kind === 'cu') {
    // 本命令只读一次蓝图、算一次判断：设计对象、承接义务、埋点与关联 Story 都用这一份
    judged = featureKnowledge(root, feature, f.spec?.contracts ?? null);
    // spec / plan 在第 3 块逐条拿到本单位承接的判断；这里给本单位作用域里其余的判断、需求级公共依据与本单位引用的事实，
    // 其余阶段同样只列本单位的，别的施工单位的义务不作为本阶段任务
    if (judged.blueprint) {
      const own = unitLines(judged);
      facts = own.lines;
      gaps.push(...own.gaps);
      if (!['spec', 'plan'].includes(action)) {
        const { applied, selected } = unitDuties(judged);
        facts.unshift(...[...applied, ...selected].map(judgedLine));
      }
    } else gaps.push('蓝图读不到：设计负责方处理。');
    if (!facts.length) facts = ['本施工单位作用域里没有知识判断。'];
    facts.push(`本施工单位承担的设计对象：${f.design_refs.map(r => `${r?.target?.kind}:${r?.target?.id}`).join('、') || '（无）'}`);
    if (['spec', 'plan'].includes(action)) {
      const expression = storyExpression(root, feature, judged);
      facts.push('', '### 关联 Story 的已定表达', '',
        'Story 讲给需求评审人的整体表达与已交付承诺，不是施工设计权威：适用的表达可以复用，'
        + '与原生设计矛盾时按设计施工并报出来；照录的是原文，不另做摘要。', '', ...expression.rows);
      gaps.push(...expression.gaps.map(g => `${g}。`));
    }
  } else {
    judged = featureKnowledge(root, feature, f.spec?.contracts ?? null);
    facts = judgedOf(judged);
    if (!facts.length) facts = ['契约里还没有知识的适用性事实（knowledge_facts）。'];
    gaps.push(...judged.problems.map(p => `${p}——维护 Feature 的作者处理。`));
  }
  const duties = [];
  if (f.identity.kind !== 'cu' && action === 'plan') {
    duties.push('这一轮的知识输入身份，原样写进契约顶层 `knowledge_context`，与 `knowledge_facts` 并列（知识换了重取本任务、按新的一份替换）：', '',
      '```json', JSON.stringify(knowledgeContext(root), null, 2), '```');
  }
  // 本单位相关知识按本阶段实际要落实的契约与验收取：产物写出了取产物，还没写出取原生选中的输入
  let stageView = f.spec;
  if (f.scope === 'not_frozen') {
    duties.push('本阶段的原生输入还没有确定（执行范围未冻结），本任务只是预览，不作为动笔依据。');
    gaps.push(`执行范围未冻结：已获准开始本阶段的主模型按 story-knowledge Skill 的「范围未冻结时」${stagePreparation(f, feature, action) ?? ''}先准备范围`
      + '（没有候选先走原生 prepare-scope，再由原生 ensureFeatureExecutionScopeFrozen 冻结），返回 frozen 或 reused 后重取本任务再动笔；原生失败按它的报错交回责任方。');
  } else {
    // 契约与验收：本阶段的产物以原生 SpecLoader 读出的为准；产物还没写出时，按原生选中的输入列义务，并写明它还是输入
    const source = f.inputs.contracts;
    const written = f.spec?.contracts ?? null;
    const chosen = source?.state === 'resolved' ? source.value ?? null : null;
    const contracts = written ?? chosen;
    if (['spec', 'plan'].includes(action)) {
      const carried = carriedDuties(judged, action, knowledge);
      duties.push(...carried.duties);
      if (f.identity.kind === 'cu') gaps.push(...carried.gaps.map(p => `${p}——设计负责方处理。`));
    }
    if (contracts) {
      const must = obligationsFromContracts(contracts);
      const origin = source?.binding?.source;
      const from = origin ? `${origin.kind}${origin.artifact ? ` ${origin.artifact}` : origin.provider_id ? ` ${origin.provider_id}` : ''}` : '本阶段产出';
      duties.push(written ? `契约来自 ${from}。`
        : `契约来自 ${from}（原生选中的输入）；本阶段要交的 contracts.yaml 还没写出，下面的义务按选中的输入列，写出后以产物为准。`,
        ...(must.length ? must.map(m => `- \`${m.entityPath}\`：${m.sourceRef} ${m.text}（验证 ${m.verify || '未写'}）`) : ['契约里没有知识义务。']));
    } else if (action === 'plan' && source?.state === 'absent') {
      duties.push('设计没有给本施工单位的机器契约投影：在本阶段的 contracts.yaml 里按承担的设计对象写出契约，'
        + '把上面承接的适用条目落成实体上的 must、本单位的角色落成 pattern_roles；原生按设计权威核对，设计已有的权威内容照它写。');
    } else {
      duties.push(`本阶段没有可读的施工契约（${source?.state ?? '本阶段不读契约'}）${source?.detail ? `：${source.detail}` : ''}。`);
    }
    const acceptance = f.spec?.acceptance ?? (f.inputs.acceptance?.state === 'resolved' ? f.inputs.acceptance.value ?? null : null);
    stageView = { ...(f.spec ?? {}), contracts, acceptance };
    if (f.identity.kind === 'cu' && action !== 'spec') {
      duties.push(...statDelivery(judged, contracts, acceptance));
    }
    const bridged = [...(acceptance?.criteria ?? []), ...(acceptance?.boundaries ?? [])].filter(c => Array.isArray(c?.knowledge_refs));
    duties.push(...bridged.map(c => `- 验收 \`${c.id}\` 承接 ${c.knowledge_refs.map(r => `\`${r}\``).join('、')}`));
    if (f.assurance === 'degraded') gaps.push('原生阶段解析为 degraded：有能力被裁剪，按原生报告核对本阶段可用的输入。');
  }
  return {
    object: `Feature \`${feature}\`，${kind}，位置 \`${f.feature_path}\``, facts, duties, gaps, page: `hooks/${action}/author.md`,
    preview: f.scope === 'not_frozen', related: relatedFiles(root, action, judged, stageView, f.identity.kind),
    starter: f.identity.kind !== 'cu' && Boolean(judged) && !judged.rows.length && !judged.facts.length,
  };
}

export function knowledgeTask(root, args) {
  return knowledgeTaskData(root, args).text;
}

/**
 * 任务正文、是不是预览（执行范围未冻结）、第 4 块送了正文的知识（`documents`：路径与全文 / 上篇 / 下篇）与缺口。
 * `unreachable` 是本单位相关的知识被登记受众挡在本动作之外（登记与消费者冲突）的那几条，单列出来；
 * Plan 审查的必审集合按 `documents` 取知识、把 `unreachable` 记成缺口，与送进同一份审查请求的任务正文同源。
 */
export function knowledgeTaskData(root, { action, audience, blueprint, feature, requirement, requirementFile }) {
  // 激活知识先读：读不出按知识维护者的缺口报，后面核判断时不再撞同一处；本动作送哪些正文按同一次取得的判断定
  const knowledge = loadKnowledge(root);
  const task = blueprint ? blueprintTask(root, blueprint, action)
    : featureTask(root, feature, action, { requirement, requirementFile }, knowledge);
  const { rows, gaps: routing, documents } = knowledgeBlock(root, action, knowledge, blueprint ? null : task.related, task.starter === true);
  task.gaps.push(...routing);
  const problems = selfCheck(root, knowledge);
  const page = relDisplay(root, path.join(extensionRoot(root), ...task.page.split('/')));
  const done = audience !== 'author' ? null : blueprint
    ? [`按 \`${page}\` 做本动作；知识方面：按第 4 块原文判与本需求相关的每份知识：相关的规约域逐条写适用性，`
      + '适用的把要求落到承担它的设计对象上，不适用写明本需求里使它不适用的条件；出现候选信号的模式写选与不选；已成立的判断直接承接，不重判。']
    : [`按 \`${page}\` 做本动作；知识方面：履行第 2、3 块已成立的判断与本单位承接的义务，先读第 4 块送来的原文再动笔，用它理解方法与语义，`
      + '不重判适用性；要别的知识或另一篇时按第 4 块索引的位置读原文。本单位的设计对象碰到了设计里没判过的知识，交设计负责方补判，不在本阶段自定。']
  const review = [`对照第 4 块原文核被审对象：相关知识有没有被判断、判断有没有依据、落点是不是真的承担这件事；`
    + '索引里没送正文的知识也可能被漏判，有疑点按位置读原文，漏判交设计负责方。'
    + `${blueprint ? `审查要求见 \`${page}\`。` : '判据按本阶段审查清单。'}`];
  const text = [`# 知识任务：${action}（${audience === 'author' ? '作者' : '审查者'}）${task.preview ? '——预览，执行范围未冻结' : ''}`, '',
    '## 1. 当前动作与对象', '', `- 动作：${action}`, `- 对象：${task.object}`, '',
    ...(task.sources ? ['### 候选采用的来源', '', ...task.sources, ''] : []),
    '## 2. 有效事实与决定', '', ...task.facts, '',
    '## 3. 当前契约与义务', '', ...task.duties, '',
    ...rows, '',
    '## 5. 本次完成条件', '', ...(done ?? review), '',
    '## 6. 缺口与责任', '',
    ...([...task.gaps, ...problems.map(p => `知识自检：${p}——目标工程的知识维护者处理。`)].map(g => `- ${g}`)),
    ...(!task.gaps.length && !problems.length ? ['- 无。'] : []), '',
    ...(task.dispatch?.length ? ['## 7. 派审与留存（主执行者）', '', ...task.dispatch, ''] : [])].join('\n');
  return { text, preview: task.preview === true, documents, unreachable: routing,
    gaps: [...task.gaps, ...problems.map(p => `知识自检：${p}`)] };
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
    const task = knowledgeTaskData(path.resolve(root), args);
    process.stdout.write(task.text);
    // 作者取正式的阶段任务就是开始这一阶段：先有任务、再记起点；预览与审查者不算开始
    if (args.audience === 'author' && args.feature && !task.preview) {
      const begun = recordUsage(path.resolve(root), 'begin', { feature: args.feature, step: args.action });
      if (!begun.ok) {
        process.stderr.write(`[usage] ${args.action} 阶段的开始没有记上（任务照常给出）：${(begun.errors ?? []).join('；')}`
          + '——修好原因后重跑本命令补记\n');
      }
    }
  } catch (e) {
    process.stderr.write(`[knowledge-task]\n${e?.message ?? e}\n`);
    process.exit(e instanceof TaskError ? 1 : 2);
  }
}
