/**
 * 读者审查的落盘核对 —— 语义审查做了没有，看它有没有留下报告。
 *
 * ## 报告在哪、谁写的
 *
 * harness 生成 verifier request 时就把本轮报告的落点写进 `<phase>/reports/summary.json`
 * 的 `verifier_report`（仓内相对路径）。派 verifier 的那个 agent 把子代理的回复**原样全文**
 * 写到那里——写报告的是调用方，不是 verifier 自己，也没有钩子代它发布。
 *
 * 报告落盘之后才核它：`reportCheck` 由本文件的命令出口、交付门（`delivery.mjs`）与 update 收口调用，
 * 审前门禁（post_check）不读报告——它跑在派审之前，把自己的报告拉回那里就成了反向依赖。
 * 身份归框架：报告在不在、终态块回显的 subject 对不对、verdict 与 blocker 数一致不一致，由 `check-receipt` 判。
 * 这里只判报告形态、判据全不全、一对象一结论、处置记录，与**读者审查这一项的形态**。
 *
 * ## 判的是形态，不是内容
 *
 * 上游的输出契约是：汇总表每个检查项一行（PASS 也列，证据一行），YAML 明细列 status ≠ PASS 的项。
 * 扩展的 `story_reader_review` 另有局部明细合同，无论结论都写：
 *
 *   ① 汇总表里有 `story_reader_review` 一行，且证据格不为空——空证据与没审同形；
 *   ② 明细里四个键（`DETAIL_KEYS`），覆盖声明对着任务书的必审集合核，结论与阻断项自洽。
 * Plan 的义务审查（`COVERED_CHECKS` 登记的判据）走同一份局部明细合同。
 *
 * 声明全核而实际没读懂，脚本识别不了：审查能不能区分好坏稿，从真实运行的原报告对照产物判。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { extensionRoot, featureRoot, phaseReportsDir, readJsonOrNull, readTextOrNull, relDisplay } from './paths.mjs';
import { parseYaml } from './yaml.mjs';
import { fenceRanges, tableCells } from '../../skills/story/scripts/core/story/document.mjs';
import { COVERED_CHECKS, DETAIL_KEYS, detailProblems, reviewInputs } from './review-inputs.mjs';

/**
 * 本阶段 overlay 的全部语义判据 —— 审查请求与报告核对读同一份，不在代码里另存判据清单。
 *
 * @returns {{checks: Record<string, {description?: string, severity?: string}>, error: string|null}}
 */
export function overlayChecks(projectRoot, phase) {
  const file = path.join(extensionRoot(projectRoot), 'rules', `${phase}-rules.overlay.yaml`);
  const text = readTextOrNull(file);
  if (text === null) return { checks: {}, error: `读不到 rules/${phase}-rules.overlay.yaml——本阶段审查判据从它的 semantic_checks 读` };
  let checks;
  try {
    checks = parseYaml(text)?.semantic_checks;
  } catch (e) {
    return { checks: {}, error: `rules/${phase}-rules.overlay.yaml 解析失败（${String(e.message).split(/\r?\n/)[0]}）——本阶段审查判据从它的 semantic_checks 读` };
  }
  if (!checks || typeof checks !== 'object' || !Object.keys(checks).length) {
    return { checks: {}, error: `rules/${phase}-rules.overlay.yaml 的 semantic_checks 解析出零条判据——审查请求与报告核对都按这里的判据逐条出结论` };
  }
  return { checks, error: null };
}

/** 报告里的表格行：`[{id, status}]`，id 是第一格、status 是第二格。 */
function tableRows(text) {
  return String(text ?? '').split(/\r?\n/).map(l => l.trim()).filter(l => l.startsWith('|'))
    .map(l => tableCells(l).map(c => c.replace(/`|\*/g, '').trim()))
    .filter(c => c[0]).map(c => ({ id: c[0], status: String(c[1] ?? '').toUpperCase() }));
}

/**
 * 当前审查报告立不立得住 —— 格式、判据全不全、同一对象是不是只有一个结论、WARN 行有没有处置记录。
 *
 * 报告由调用方原样落盘在 `summary.verifier_report`。格式不合或缺判据的回复每次运行都报，不计作结论；
 * 合规的第一份登记进 `verifier.conclusions.json`，同一对象之后换了内容的回复被拒——对象没变，结论就不换。
 * 写盘只有这一处登记。报告不在由 `reportCheck` 分情形报。
 *
 * @returns {string[]}
 */
function reportProblems(projectRoot, feature, phase) {
  const { summaryFound, abs, summary } = reportLocation(projectRoot, feature, phase);
  if (!summaryFound || !abs) return [];
  const text = readTextOrNull(abs);
  if (text === null) return [];
  const block = resultBlock(text);
  const rows = tableRows(text);
  const ids = new Set(rows.map(r => r.id));
  if (!block || !ids.size) {
    return [`${summary.verifier_report}：审查回复格式不合（${!block ? '终态块不是恰好一个' : '没有汇总表'}），不计作结论。${INVALID_EVIDENCE}`];
  }
  const problems = [];
  const { checks } = overlayChecks(projectRoot, phase);
  for (const id of Object.keys(checks)) {
    if (!ids.has(id)) problems.push(`${summary.verifier_report} 的汇总表缺判据：${id}——汇总表逐条对 rules/${phase}-rules.overlay.yaml 的 semantic_checks，缺一条的报告按阻断处理。${INVALID_EVIDENCE}`);
  }
  // 读者审查的明细不成立也是坏稿：先核，坏稿不占这个对象的首份合规结论
  for (const [id, purpose] of Object.entries(COVERED_CHECKS)) {
    if (!checks[id]) continue;
    problems.push(...judgeReport(text, summary.verifier_report, id,
      reviewInputs(projectRoot, feature, purpose), Object.keys(checks)).problems);
  }
  const failed = rows.filter(r => r.status === 'FAIL').map(r => r.id);
  if (block.verdict === 'PASS' && failed.length) {
    problems.push(`${summary.verifier_report}：汇总表 ${failed.join('、')} 判 FAIL，终态块却是 PASS——结论自相矛盾，不计作结论。${INVALID_EVIDENCE}`);
  }
  const subject = block.subject;
  const ledgerPath = path.join(path.dirname(abs), 'verifier.conclusions.json');
  const ledger = readJsonOrNull(ledgerPath) ?? {};
  const digest = crypto.createHash('sha256').update(text.replace(/\r\n/g, '\n')).digest('hex').slice(0, 16);
  if (subject && ledger[subject] && ledger[subject] !== digest) {
    problems.push(`${summary.verifier_report}：审查对象 ${String(subject).slice(0, 12)}… 已经有过一份合规结论，这份是换了内容的重投——`
      + '同一审查对象只登记第一份合规结论（同目录 verifier.conclusions.json）；审查对象随材料变化，材料改过之后 harness 给出新的请求与对象');
  } else if (subject && !ledger[subject] && !problems.length) {
    fs.writeFileSync(ledgerPath, `${JSON.stringify({ ...ledger, [subject]: digest }, null, 2)}\n`, 'utf-8');
  }
  // 处置要指向这一份报告：同一行里有判据编号与报告对象的前 8 位。旧报告的同号处置不替新报告豁免；
  // 处置写得对不对、问题是不是真解决了，归审查与作者的说明，这里只核引用在、指向当前报告。
  const notes = (readTextOrNull(path.join(featureRoot(projectRoot, feature), phase, 'notes.md')) ?? '').split(/\r?\n/);
  const tag = String(subject ?? '').slice(0, 8);
  const undisposed = rows.filter(r => /^(WARN|FAIL)$/.test(r.status)
    && !notes.some(l => l.includes(r.id) && (!tag || l.includes(tag))));
  if (undisposed.length) {
    problems.push(`${phase}/notes.md：审查结论 ${undisposed.map(r => `${r.id}（${r.status}）`).join('、')}没有指向这份报告的处置记录`
      + `——同一行写判据编号与报告对象前 8 位（${tag || '终态块里的 verifier_subject_id'}）再写处置；`
      + '处置的几类（返修、只改表达已重验、改了业务已再审、留给哪一阶段）在 phases/spec.md「闭环」');
  }
  return problems;
}

/**
 * 当前报告核得过吗 —— 命令出口、交付门与 update 收口共用这一份判定。
 *
 * - summary 不在：harness 还没给出请求与落点，判不了，按失败报；
 * - summary 里审查字段全都没有：本宿主未启用 verifier，如实是「未审」，不说成 PASS；
 * - 有审查对象或请求而没有报告落点：summary 不完整，判不了，按核对没执行完报；
 * - 落点上没有报告：只有修正重验沿用了有效的历史 PASS 才放行并写明未独立重审，其余按缺报告报；
 * - 报告在：格式、判据、一对象一结论与处置记录逐项核，问题一次列全。
 *
 * @returns {{status: 'PASS'|'FAIL'|'NOT_REVIEWED'|'ERROR', problems: string[], notes: string[]}}
 */
export function reportCheck(projectRoot, feature, phase) {
  const { summaryFound, abs, summary, where, unreadable } = reportLocation(projectRoot, feature, phase);
  if (unreadable) return { status: 'ERROR', notes: [], problems: [`${unreadable}：本阶段审没审过判不了，不拿别处的报告顶——重跑 harness 让它重写`] };
  if (!summaryFound) {
    return { status: 'FAIL', notes: [], problems: [`${where} 不在：报告落点与审查请求由 harness 写进 summary——`
      + `先完整跑一次 \`harness-runner.ts --phase ${phase} --feature ${feature}\`，按它末尾的 NEXT 派审`] };
  }
  if (!abs) {
    const broken = incompleteSummary(summary, phase, feature);
    if (broken) return { status: 'ERROR', notes: [], problems: [broken] };
    return { status: 'NOT_REVIEWED', problems: [], notes: ['summary 里没有任何审查字段：本宿主未启用 verifier，本阶段没有独立审查，不是 PASS'] };
  }
  if (readTextOrNull(abs) === null) {
    const prior = withoutCurrentReport(summary, abs, phase === 'spec');
    return prior.status === 'PASS' ? { status: 'PASS', problems: [], notes: prior.notes ?? [] }
      : { status: 'FAIL', problems: prior.problems, notes: [] };
  }
  const { error } = overlayChecks(projectRoot, phase);
  if (error) return { status: 'ERROR', problems: [`${error}；判据读不出就核不了报告——归扩展维护者处理`], notes: [] };
  const problems = reportProblems(projectRoot, feature, phase);
  return { status: problems.length ? 'FAIL' : 'PASS', problems, notes: [] };
}

/** 读者审查那一项在报告里的标识 —— 判据 id 本身，不另起一个名字。 */
const STORY_REVIEW_ID = 'story_reader_review';

/** 汇总表的列数：id / status / severity / 一行证据。列序见框架的输出契约。 */
const SUMMARY_COLUMNS = 4;

/**
 * 报错说给**读报错的那个人**听 —— 他是作者，不是审查员。
 *
 * 报告必须是子代理回复的原样落盘，作者照着报错去补一行、补一个键，补出来的是
 * 伪造的审查证据。所以缺什么都不叫他写，只说审查证据认什么。
 */
const INVALID_EVIDENCE =
  '这份回复不是有效证据——审查证据只认同一份 request 再投给 verifier 得到的原样全文回复，落盘后下一次 harness 运行按它核。'
  + '**不要自己补**——补出来的不是审查结论。';

/**
 * 本轮报告落在哪 —— 唯一来源是 harness 写的 `summary.verifier_report`。
 *
 * 返回 null 有几种含义，调用方区分：summary 都没有 = harness 还没跑；summary 在而审查字段
 * 全都没有 = verifier 未启用，如实披露的状态；只缺这一项 = summary 不完整。
 */
function reportLocation(projectRoot, feature, phase) {
  let file;
  try {
    file = path.join(phaseReportsDir(projectRoot, feature, phase), 'summary.json');
  } catch (e) {
    return { summaryFound: false, abs: null, summary: null, unreadable: `${phase} 阶段报告目录判不了（framework.config.json：${e.message}）` };
  }
  const where = relDisplay(projectRoot, file);
  const text = readTextOrNull(file);
  if (text === null) return { summaryFound: false, abs: null, summary: null, where };
  const summary = readJsonOrNull(file);
  if (!summary) return { summaryFound: false, abs: null, summary: null, where, unreadable: `${where} 在却读不出（不是合法 JSON）` };
  const rel = typeof summary.verifier_report === 'string' ? summary.verifier_report.trim() : '';
  return { summaryFound: true, abs: rel ? path.resolve(projectRoot, rel) : null, summary };
}

/**
 * 没有报告落点时，是「未启用审查员」还是还轮不到审、或 summary 不完整。
 *
 * harness-runner 只在 verifier 启用**且**本轮脚本 verdict 为 PASS 时写出审查对象、请求、报告落点三项
 * （装配失败会把 verdict 改成 FAIL）。所以三项全缺只在 verdict 为 PASS 时才说明未启用；
 * verdict 不是 PASS 时是脚本还没过、没派审，能力有没有判不了。只缺落点而对象或请求在，是 summary 不完整。
 * 返回要报的问题；确属未启用返回 null。
 */
function incompleteSummary(summary, phase, feature) {
  const rerun = `重新完整跑一次 \`harness-runner.ts --phase ${phase} --feature ${feature}\``;
  const present = ['verifier_subject_id', 'verifier_request'].filter(k => typeof summary?.[k] === 'string' && summary[k].trim());
  if (present.length) {
    return `${phase}/reports/summary.json 有 ${present.join('、')} 却没有 verifier_report：summary 不完整，判不了本阶段审没审过`
      + `——这三项由 harness 同时写出，${rerun}，不要手补字段`;
  }
  if (summary?.verdict !== 'PASS') {
    return `${phase}/reports/summary.json 的脚本结论是 ${summary?.verdict ?? '（缺）'}：脚本门禁没过时 harness 不派审，`
      + `本阶段还轮不到审查，也看不出宿主有没有审查员——按 harness 报的问题返修后${rerun}`;
  }
  return null;
}

/**
 * 当前对象没有报告时说什么 —— 只说盘上的事实和真实的去处。
 *
 * 缺文件推不出「回复存在、只是没写」：当前对象可能根本没被审过。所以先说有匹配当前请求的
 * 原始回复才原样写回，否则取当前请求派审；闭环沿用了历史审查时，把这件事照 summary 说出来。
 * 当前审查只认对当前请求的原样回复。
 */
function missingReport(summary, abs) {
  const request = typeof summary.verifier_request === 'string' ? summary.verifier_request : '（summary 没写）';
  const prior = summary.verifier_closure;
  const facts = prior?.mode
    ? `本阶段按 ${prior.mode} 收口：当前对象 ${String(prior.current_subject_id ?? summary.verifier_subject_id ?? '').slice(0, 12)}… `
      + `没有独立审查，沿用的是 ${String(prior.reviewed_subject_id ?? '').slice(0, 12)}… 的审查`
      + `（未重审：${(prior.current_material_not_reverified ?? []).join('、') || '未列'}）。`
    : '当前审查对象还没有报告。';
  return `${facts}报告落点是 ${abs}（harness 登记在 summary.verifier_report）——落点只认 verifier 对当前请求 ${request} 的原样全文回复，`
    + '写入后下一次完整的 harness 运行才读到它；请求与审查对象随本轮材料生成。'
    + '当前审查只认对当前请求的原样回复';
}

/**
 * 汇总表里 `story_reader_review` 那一行，原样返回它的格子。
 *
 * 认的是「以 | 分格、第一格是这个 id」的行，不认散落在正文里的同名字样——
 * 后者在讲这一项，不是这一项的结论。**不在这里判够不够格**：格子少了是一种
 * 具体的写法问题，要能与「压根没这一行」分开报。
 */
function summaryRow(text, id) {
  for (const line of text.split(/\r?\n/)) {
    const raw = line.trim();
    if (!raw.startsWith('|')) continue;
    const cells = tableCells(raw);
    if (cells.length && cells[0].replace(/`/g, '') === id) return cells;
  }
  return null;
}

/** 文档里的 YAML 围栏，一个不落地取出来——报告的结构就写在里面。 */
function yamlBlocks(text) {
  const lines = String(text ?? '').split(/\r?\n/);
  return fenceRanges(lines).map(f => lines.slice(f.from + 1, f.closed ? f.to : f.to + 1).join('\n'));
}

/**
 * 结构里那一串 check —— 顶层直接是 `checks`，或者包在结果对象里（各认一层）。
 *
 * **只认这个键名，不按形状搜**：形状搜（「任何一个带 id 的数组」）会撞上报告里
 * 别的列表——findings、items 都长这样——撞上了就静默读到另一批东西，而判据全绿。
 */
function checksIn(doc) {
  if (Array.isArray(doc?.checks)) return doc.checks;
  for (const value of Object.values(doc ?? {})) {
    if (Array.isArray(value?.checks)) return value.checks;
  }
  return null;
}

/**
 * 明细里 `story_reader_review` 那一条的 `details` —— **整段解析，按 id 取项**。
 *
 * 整段读、按 id 取，不划文本范围。划范围要靠「到下一条 `- id:` 或围栏结束」这类
 * 启发式，而报告里每条 check 的 `details` 都可能是块标量，块里出现什么字样都是正文——
 * 边界一旦被块里的内容带偏，读出来的就是另一条的结论，判据却照样给出答案。
 *
 * **能读出结构不等于这一条写全了**：`details` 要是映射。它是一段文本（`details: |`）、列表或缺席时，
 * 按 `shape` 说清它实际是什么——说成「缺四个键」的话，作者会去补已经写在文字里的键。
 *
 * @returns {{details: object|null, shape: string|null, unreadable: string|null}}
 *   `unreadable` 非空 = 这份 YAML 读不出结构；`shape` 非空 = 找到了这一条，`details` 却不是映射。
 */
function readerReviewDetails(text, id) {
  let unreadable = null;
  for (const body of yamlBlocks(text)) {
    let doc;
    try {
      doc = parseYaml(body);
    } catch (e) {
      unreadable = unreadable ?? String(e?.message ?? e);
      continue;
    }
    const checks = checksIn(doc);
    if (!checks) continue;
    const entry = checks.find(c => c
      && String(c.id ?? '').replace(/`/g, '').trim() === id);
    if (!entry) continue;
    const details = entry.details;
    const mapping = details && typeof details === 'object' && !Array.isArray(details);
    const shape = mapping ? null : typeof details === 'string' ? '是一段文字（YAML 块字符串）'
      : Array.isArray(details) ? '是一个列表' : details === undefined ? '没有写' : `是 ${JSON.stringify(details)}`;
    return { details: mapping ? details : null, shape, unreadable: null };
  }
  return { details: null, shape: null, unreadable };
}

/**
 * 读者审查这一项做了没有、写成什么形态。
 *
 * @returns {{status: string, problems: string[], detail: string}}
 */
export function storyReviewProblems(projectRoot, feature, phase) {
  const { summaryFound, abs, summary, unreadable } = reportLocation(projectRoot, feature, phase);
  if (unreadable) return { status: 'FAIL', problems: [unreadable], reviewVerdict: null, detail: unreadable };
  if (!summaryFound) {
    return { status: 'NOT_APPLICABLE', problems: [], reviewVerdict: null,
      detail: 'harness 尚未运行，本项还轮不到判' };
  }
  if (!abs) {
    const broken = incompleteSummary(summary, phase, feature);
    if (broken) return { status: 'FAIL', problems: [broken], reviewVerdict: null, detail: broken };
    return {
      status: 'NOT_APPLICABLE',
      problems: [],
      reviewVerdict: null,
      detail: 'summary 里没有任何审查字段：本宿主未启用 verifier，本轮没有报告可核',
    };
  }
  const text = readTextOrNull(abs);
  return text === null ? withoutCurrentReport(summary, abs)
    : judgeReport(text, summary.verifier_report, STORY_REVIEW_ID, reviewInputs(projectRoot, feature, 'story'),
      Object.keys(overlayChecks(projectRoot, phase).checks));
}

const RESULT_BLOCK = /<!-- maison-verifier-result:v1 -->([\s\S]*?)<!-- \/maison-verifier-result:v1 -->/g;

/** 报告的终态块（恰好一个完整块才算）：审的是哪个对象、判了什么。 */
function resultBlock(text) {
  const blocks = [...String(text ?? '').matchAll(RESULT_BLOCK)];
  if (blocks.length !== 1) return null;
  const field = key => new RegExp(`^\\s*${key}\\s*:\\s*(\\S+)\\s*$`, 'm').exec(blocks[0][1])?.[1] ?? null;
  return { subject: field('verifier_subject_id'), verdict: field('verdict') };
}

/**
 * 当前对象没有报告时能不能交付：`phases/spec.md`「闭环」表里「PASS 之后只改表达」那一类——
 * framework 修正重验（summary 带 `script_revalidated`）、本阶段闭环 PASS 并沿用历史审查，
 * 且那份历史报告就是 `reviewed_subject_id` 的有效 PASS 时，按沿用交付并留一笔说明。
 * update 收口怎么核见 `phases/update.md`「二、一条线」第 9 步（flow/update.py 读 summary 实现）。
 */
function withoutCurrentReport(summary, abs, judgeStory = true) {
  const prior = summary.verifier_closure;
  const fail = (detail, extra = '') => ({ status: 'FAIL', problems: [missingReport(summary, abs) + extra], reviewVerdict: null, detail });
  const signals = (summary.readiness_signals ?? []).map(s => s?.id ?? s);
  if (prior?.mode !== 'completed_with_prior_review' || !signals.includes('script_revalidated')
    || summary.closure_status !== 'closed' || summary.verdict !== 'PASS') {
    return fail(prior?.mode ? '当前对象未独立审查' : '报告缺席');
  }
  const history = readTextOrNull(path.join(path.dirname(abs), `verifier.report.${prior.reviewed_subject_id}.md`));
  const block = resultBlock(history);
  const judged = history === null || !judgeStory ? null : judgeReport(history, undefined, STORY_REVIEW_ID);
  if (block?.subject !== prior.reviewed_subject_id || block?.verdict !== 'PASS'
    || (judged && (judged.problems.length || judged.reviewVerdict !== 'PASS'))) {
    return fail('沿用的历史审查无效', `；修正重验沿用的 ${String(prior.reviewed_subject_id).slice(0, 12)}… 报告（同目录 verifier.report.<对象>.md）缺席或不是有效的 PASS——沿用只在那份历史报告是 reviewed_subject_id 的有效 PASS 时成立`);
  }
  return { status: 'PASS', problems: [], reviewVerdict: 'PASS', detail: '修正重验沿用历史审查',
    notes: [`当前材料未独立重审：当前对象 ${String(summary.verifier_subject_id).slice(0, 12)}… 沿用 `
      + `${String(prior.reviewed_subject_id).slice(0, 12)}… 的审查（未重审：${(prior.current_material_not_reverified ?? []).join('、') || '未列'}）`] };
}

/** 报告正文里一条局部明细判据：汇总行、证据与明细（`basis` 是当前必审集合，核历史报告时不传）。 */
function judgeReport(text, at = 'verifier 报告', id = STORY_REVIEW_ID, basis = null, checkIds = []) {
  const row = summaryRow(text, id);
  if (!row) {
    return {
      status: 'FAIL',
      problems: [`${at} 的汇总表里没有 ${id} 这一行——门禁按第一格等于这个 id 的表格行认它；`
        + '这一项是 story 语义质量的发现者，汇总表里找不到它就等于这一轮没审。'
        + INVALID_EVIDENCE],
      reviewVerdict: null,
      detail: '汇总表缺行',
    };
  }
  // 汇总表四列（id / status / severity / 证据），列序见框架的输出契约。
  // 证据取第 4 格：格数不够就是这一行少了证据列，与「压根没这一行」分开报。
  if (row.length < SUMMARY_COLUMNS) {
    return {
      status: 'FAIL',
      problems: [`${at} 的汇总表：${id} 那一行只有 ${row.length} 格，少了证据列——`
        + '汇总表每行四格（id、status、severity、一行证据），证据取第 4 格。' + INVALID_EVIDENCE],
      reviewVerdict: null,
      detail: `汇总表只有 ${row.length} 列`,
    };
  }
  const status = row[1].replace(/`|\*/g, '').toUpperCase();
  // **审查自己的结论**：从汇总行那一格规范化取来，不从 detail 的措辞倒猜。
  // 结构完整而审查判了 FAIL 时，这个函数的 `status` 仍是 PASS（报告的结构没问题），
  // 两件事因此要分开返回——交付门看的是 `reviewVerdict`，作者看的是 `problems`。
  const reviewVerdict = status || null;
  const evidence = row[SUMMARY_COLUMNS - 1];
  if (!evidence || /^[-—–]+$/.test(evidence)) {
    return {
      status: 'FAIL',
      problems: [`${at} 的汇总表：${id} 那一行的证据格是空的——`
        + '证据取第 4 格，空或只有横线都算空；空证据与没审长得一样。' + INVALID_EVIDENCE],
      reviewVerdict,
      detail: '证据格为空',
    };
  }

  const { details, shape, unreadable } = readerReviewDetails(text, id);
  // 读不出结构、details 不是映射与「缺键」是三回事：说成缺键的话，作者会去补已经写着的键，补完还报
  const bad = unreadable ? [`里的结构块读不出来（${unreadable}）——${id} 的明细在 YAML 围栏里，读不出就核不了`]
    : shape ? [`：${id} 的 details ${shape}，不是映射——details 下写 ${DETAIL_KEYS.join('、')} 四个键，值都是列表`]
      : !details ? [`的 YAML 明细里没有 ${id} 这一条——它无论结论都在明细里写 ${DETAIL_KEYS.join('、')}`]
        : detailProblems(details, status, basis, checkIds).map(p => `：${id} ${p}`);
  if (bad.length) {
    return { status: 'FAIL', problems: bad.map(p => `${at}${p}。${INVALID_EVIDENCE}`), reviewVerdict, detail: '明细不成立' };
  }
  return { status: 'PASS', problems: [], reviewVerdict, blocking: details.blocking_findings, advisories: details.advisories,
    detail: `读者审查已落报告（${status}）` };
}

const USAGE = '用法：node <ext>/hooks/shared/verifier-report.mjs --feature <名> --phase <阶段> [--project-root <工程根>]';

/** 命令出口：审查回复原样落盘之后、check-receipt 与收口之前跑。0 通过（含未启用审查员时的「未审」）/ 1 有问题 / 2 参数或前置错误。 */
function main(argv) {
  const arg = k => { const i = argv.indexOf(k); return i >= 0 ? String(argv[i + 1] ?? '').trim() : ''; };
  const feature = arg('--feature');
  const phase = arg('--phase');
  if (!feature || !phase) {
    process.stderr.write(`${USAGE}\n`);
    return 2;
  }
  const r = reportCheck(arg('--project-root') || process.cwd(), feature, phase);
  const head = {
    PASS: `[verifier-report] ${phase} 阶段审查报告核对通过`,
    NOT_REVIEWED: `[verifier-report] ${phase} 阶段没有独立审查（未审，不是 PASS）`,
    FAIL: `[verifier-report] ${phase} 阶段审查报告未通过，${r.problems.length} 处。恢复：格式不合或缺判据——同一份 request 交审查者重投、原样落盘，作者不改报告；`
      + `缺处置记录——在 ${phase}/notes.md 按 phases/spec.md「闭环」写处置；缺报告或 summary——按下面写的入口补跑；改完重跑本命令`,
    ERROR: `[verifier-report] ${phase} 阶段报告核对没有执行完`,
  }[r.status];
  const out = [head, ...r.problems.map((p, i) => `${i + 1}. ${p}`), ...r.notes.map(n => `- ${n}`)].join('\n');
  (r.status === 'PASS' || r.status === 'NOT_REVIEWED' ? process.stdout : process.stderr).write(`${out}\n`);
  return { PASS: 0, NOT_REVIEWED: 0, FAIL: 1, ERROR: 2 }[r.status];
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  try {
    process.exit(main(process.argv.slice(2)));
  } catch (e) {
    process.stderr.write(`[verifier-report] 报告核对自身异常（${e?.stack ?? e}）：没有核完，这不是报告的问题——归扩展维护者处理\n`);
    process.exit(2);
  }
}
