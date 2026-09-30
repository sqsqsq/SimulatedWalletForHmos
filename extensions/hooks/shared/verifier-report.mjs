/**
 * 阶段审查报告的落盘核对 —— spec / plan 阶段的 post_check 用它核本轮审查回复立不立得住。
 *
 * harness 生成 verifier request 时就把本轮报告的落点写进 `<phase>/reports/summary.json`
 * 的 `verifier_report`（仓内相对路径）。派 verifier 的那个 agent 把子代理的回复**原样全文**
 * 写到那里——写报告的是调用方，不是 verifier 自己，也没有钩子代它发布。
 *
 * 身份归框架：报告在不在、终态块回显的 subject 对不对、verdict 与 blocker 数一致不一致，由 `check-receipt` 判。
 * 这里核的是本阶段 overlay 的每条判据在汇总表里都有一行、同一对象只登记第一份合规结论、WARN/FAIL 有处置记录。
 * Story 的独立人读审查不在这里：判据在 `rules/story-reader-rules.yaml`，任务由 `reader-review-task.mjs` 生成。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { extensionRoot, featureRoot, readJsonOrNull, readTextOrNull } from './paths.mjs';
import { parseYaml } from './yaml.mjs';
import { tableCells } from '../../skills/story/scripts/core/story/document.mjs';

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
 * 门禁写盘只有这一处登记。
 * 还没派审（报告不在）不在这里报：派不派由 framework 的 NEXT 行说。
 *
 * @returns {string[]}
 */
export function reportProblems(projectRoot, feature, phase) {
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
  const notes = readTextOrNull(path.join(featureRoot(projectRoot, feature), phase, 'notes.md')) ?? '';
  const undisposed = rows.filter(r => /^(WARN|FAIL)$/.test(r.status) && !notes.includes(r.id));
  if (undisposed.length) {
    problems.push(`${phase}/notes.md：审查结论 ${undisposed.map(r => `${r.id}（${r.status}）`).join('、')}没有处置记录`
      + '——门禁按判据编号在 notes.md 里找它的处置；处置的几类（返修、只改表达已重验、改了业务已再审、留给哪一阶段）'
      + '在 phases/spec.md「闭环」');
  }
  return problems;
}

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
 * 返回 null 有两种含义，调用方按 `summary` 在不在区分：summary 都没有 = harness
 * 还没跑；summary 在而这个字段没有 = 本宿主没有审查员（verifier plan disabled），
 * 那是如实披露的状态，不是缺件。
 */
function reportLocation(projectRoot, feature, phase) {
  const dir = path.join(featureRoot(projectRoot, feature), phase, 'reports');
  const summary = readJsonOrNull(path.join(dir, 'summary.json'));
  if (!summary) return { summaryFound: false, abs: null, summary: null };
  const rel = typeof summary.verifier_report === 'string' ? summary.verifier_report.trim() : '';
  return { summaryFound: true, abs: rel ? path.resolve(projectRoot, rel) : null, summary };
}

const RESULT_BLOCK = /<!-- maison-verifier-result:v1 -->([\s\S]*?)<!-- \/maison-verifier-result:v1 -->/g;

/** 报告的终态块（恰好一个完整块才算）：审的是哪个对象、判了什么。 */
function resultBlock(text) {
  const blocks = [...String(text ?? '').matchAll(RESULT_BLOCK)];
  if (blocks.length !== 1) return null;
  const field = key => new RegExp(`^\\s*${key}\\s*:\\s*(\\S+)\\s*$`, 'm').exec(blocks[0][1])?.[1] ?? null;
  return { subject: field('verifier_subject_id'), verdict: field('verdict') };
}

