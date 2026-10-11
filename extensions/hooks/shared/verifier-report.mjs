/**
 * 阶段审查报告的落盘核对 —— spec / plan 阶段的 post_check 用它核本轮审查回复立不立得住。
 *
 * harness 生成 verifier request 时就把本轮报告的落点写进原生阶段报告目录（`featurePhaseReportsDir`）下
 * `summary.json` 的 `verifier_report`（仓内相对路径）。派 verifier 的那个 agent 把子代理的回复**原样全文**
 * 写到那里——写报告的是调用方，不是 verifier 自己，也没有钩子代它发布。
 *
 * 身份归框架：报告在不在、终态块回显的 subject 对不对、verdict 与 blocker 数一致不一致，由 `check-receipt` 判。
 * 这里核的是本阶段 overlay 的每条判据在四格汇总表里恰好一行、取值合法、证据不空，WARN/FAIL 有处置记录。
 * 这是逐判据的结构核对；知识条目逐条核没核、核得对不对是审查者的语义职责，不在这里数。
 * Story 的独立人读审查不在这里：判据在 `rules/story-reader-rules.yaml`，任务由 `reader-review-task.mjs` 生成。
 */
import * as fs from 'node:fs';
import { featureDir, phaseReportsDir } from './framework-access.mjs';
import * as path from 'node:path';
import { extensionRoot, readJsonOrNull, readTextOrNull } from './paths.mjs';
import { parseYaml } from './yaml.mjs';
import { tableCells } from '../../skills/story/scripts/core/story/document.mjs';

//: 汇总表合同：与原生 verify-* 模板同一张四列表；第四列标题原生现行写法较长，两种都认
const COLUMNS = ['id', 'status', 'severity'];
const EVIDENCE_HEADERS = ['证据', '证据（一行：文件:行 / 引文 / 数值）'];
//: 原生 CheckStatus（summary.schema.json）与 Severity（harness/scripts/utils/types.ts）
const STATUSES = ['PASS', 'WARN', 'FAIL', 'SKIP'];
const SEVERITIES = ['BLOCKER', 'MAJOR', 'MINOR'];

/** 审查请求里的报告结构说明：与下面的核对同一份合同。 */
export function summaryStructure() {
  return [`**报告结构**：汇总表四格 \`${[...COLUMNS, EVIDENCE_HEADERS[0]].join(' | ')}\`，本阶段每条判据恰好一行（PASS 也列）；`
    + `status 取 ${STATUSES.join(' / ')}，severity 取 ${SEVERITIES.join(' / ')}，证据不空（SKIP 的适用理由写在证据里）；`,
  'status ≠ PASS 的在 YAML 明细 `checks:` 里各出一条，`details` 写问题、依据与改法；PASS 的核验方法写进报告说明，不另列明细；',
  '末尾恰好一个 `maison-verifier-result:v1` 终态块。缺判据、重复或取值不合的报告按阻断处理。'];
}

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

const plain = c => c.replace(/`|\*/g, '').trim();

/**
 * 报告里表头合乎汇总表合同的那几张表，取表头之后的数据行：`[{cells}]`。
 * 表头核前三列与第四列的两种写法，第二行要是分隔行；正文提到的 ID、其它表的引用列不算结论。
 */
function summaryRows(text) {
  const lines = String(text ?? '').split(/\r?\n/).map(l => l.trim());
  const rows = [];
  let tables = 0;
  for (let i = 0; i < lines.length; i += 1) {
    if (!lines[i].startsWith('|') || (i > 0 && lines[i - 1].startsWith('|'))) continue;
    const header = tableCells(lines[i]).map(plain);
    const rule = tableCells(lines[i + 1] ?? '');
    const isSummary = header.length === 4 && COLUMNS.every((c, k) => header[k] === c) && EVIDENCE_HEADERS.includes(header[3])
      && rule.length === 4 && rule.every(c => /^:?-{3,}:?$/.test(c.trim()));
    if (!isSummary) continue;
    tables += 1;
    for (let k = i + 2; k < lines.length && lines[k].startsWith('|'); k += 1) rows.push(tableCells(lines[k]).map(plain));
  }
  return { tables, rows };
}

/**
 * 当前审查报告立不立得住 —— 终态块、本阶段每条判据在汇总表里恰好一行且取值合法、WARN/FAIL 有处置记录。
 *
 * 报告由调用方原样落盘在 `summary.verifier_report`。不合合同的回复每次运行都报、一次报全，不计作结论，原文件不写。
 * 报告的身份与有效性（对象回显、过期）由原生 `check-receipt` 判；同行的 Framework 自有判据也归原生核。
 * 还没派审（summary 或报告不在）不在这里报：派不派由 framework 的 NEXT 行说。
 *
 * @returns {string[]}
 */
export function reportProblems(projectRoot, feature, phase) {
  const where = reportLocation(projectRoot, feature, phase);
  if (where.problem) return [where.problem];
  if (!where.abs) return [];
  const text = readTextOrNull(where.abs);
  if (text === null) return [];
  const name = where.summary.verifier_report;
  const { tables, rows } = summaryRows(text);
  const problems = [];
  if (!resultBlock(text)) problems.push(`${name}：终态块不是恰好一个`);
  if (!tables) problems.push(`${name}：没有表头为 \`${[...COLUMNS, EVIDENCE_HEADERS[0]].join(' | ')}\` 的汇总表`);
  const { checks } = overlayChecks(projectRoot, phase);
  const mine = new Map(Object.keys(checks).map(id => [id, rows.filter(r => r[0] === id)]));
  for (const [id, hits] of tables ? mine : []) {
    if (hits.length !== 1) {
      problems.push(`${name} 的汇总表里判据 ${id} ${hits.length ? `有 ${hits.length} 行` : '缺行'}——本阶段每条判据恰好一行`);
      continue;
    }
    const [, status, severity, evidence] = hits[0];
    const why = [hits[0].length !== 4 && `有 ${hits[0].length} 格（应为 4 格）`,
      !STATUSES.includes(status) && `status「${status ?? ''}」不是 ${STATUSES.join('/')}`,
      !SEVERITIES.includes(severity) && `severity「${severity ?? ''}」不是 ${SEVERITIES.join('/')}`,
      !evidence && '证据为空'].filter(Boolean);
    if (why.length) problems.push(`${name} 的汇总表判据 ${id}：${why.join('；')}`);
  }
  if (problems.length) return [`${problems.join('；')}。按 rules/${phase}-rules.overlay.yaml 的 semantic_checks 逐条核，`
    + `不合合同的报告按阻断处理。${INVALID_EVIDENCE}`];
  const notes = readTextOrNull(path.join(featureDir(projectRoot, feature), phase, 'notes.md')) ?? '';
  const undisposed = [...mine].map(([id, [row]]) => ({ id, status: row[1] }))
    .filter(r => /^(WARN|FAIL)$/.test(r.status) && !notes.includes(r.id));
  return undisposed.length ? [`${phase}/notes.md：审查结论 ${undisposed.map(r => `${r.id}（${r.status}）`).join('、')}没有处置记录`
    + '——门禁按判据编号在 notes.md 里找它的处置；处置的几类（返修、只改表达已重验、改了业务已再审、留给哪一阶段）'
    + '在 skills/story/reference/phase-closure.md「闭环」'] : [];
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
 * 本轮报告落在哪 —— 原生阶段报告目录下 harness 写的 `summary.verifier_report`。
 *
 * - 目录解析失败、summary 在却读不出：输入故障，`problem` 写明，不当作还没派审；
 * - summary 不在：harness 还没跑，派审由原生调度；
 * - summary 在而没有 `verifier_report`：本宿主没有审查员（verifier plan disabled），如实披露的状态，不是缺件。
 */
function reportLocation(projectRoot, feature, phase) {
  const dir = phaseReportsDir(projectRoot, feature, phase);
  if (dir.error) {
    return { problem: `${phase} 阶段的报告目录按原生配置解析失败（${dir.error}）——报告位置由 Framework 的 featurePhaseReportsDir 决定，`
      + '解析不出就核不了这一阶段的审查' };
  }
  const file = path.join(dir.dir, 'summary.json');
  if (!fs.existsSync(file)) return { abs: null };
  const summary = readJsonOrNull(file);
  if (!summary || typeof summary !== 'object' || Array.isArray(summary)) {
    return { problem: `${path.relative(projectRoot, file).split(path.sep).join('/')} 在但读不出或不是 JSON 对象——`
      + '它是 harness 写的本阶段报告登记，坏了就不知道报告落在哪，不当作还没派审' };
  }
  const rel = typeof summary.verifier_report === 'string' ? summary.verifier_report.trim() : '';
  return { abs: rel ? path.resolve(projectRoot, rel) : null, summary };
}

const RESULT_BLOCK = /<!-- maison-verifier-result:v1 -->([\s\S]*?)<!-- \/maison-verifier-result:v1 -->/g;

/** 报告的终态块恰好一个才算格式合规；块里的身份与结论由原生 `check-receipt` 核。 */
function resultBlock(text) {
  return [...String(text ?? '').matchAll(RESULT_BLOCK)].length === 1;
}
