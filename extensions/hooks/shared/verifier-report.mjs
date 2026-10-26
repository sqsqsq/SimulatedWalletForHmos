/**
 * 阶段审查报告的落盘核对 —— spec / plan 阶段的 post_check 用它核本轮审查回复立不立得住。
 *
 * harness 生成 verifier request 时就把本轮报告的落点写进原生阶段报告目录（`featurePhaseReportsDir`）下
 * `summary.json` 的 `verifier_report`（仓内相对路径）。派 verifier 的那个 agent 把子代理的回复**原样全文**
 * 写到那里——写报告的是调用方，不是 verifier 自己，也没有钩子代它发布。
 *
 * 身份归框架：报告在不在、终态块回显的 subject 对不对、verdict 与 blocker 数一致不一致，由 `check-receipt` 判。
 * 这里核的是本阶段 overlay 的每条判据在四格汇总表里恰好一行、取值合法、证据不空，FAIL 的严重度与判据声明一致、
 * 终态不与 BLOCKER 级 FAIL 矛盾，WARN/FAIL 有指向这份报告的处置记录；
 * 走局部明细合同的判据（`COVERED_CHECKS`）另核明细四个键与必审集合。
 * 这是逐判据的结构核对；知识条目逐条核没核、核得对不对是审查者的语义职责，不在这里数。
 * Story 的独立人读审查不在这里：判据在 `rules/story-reader-rules.yaml`，任务由 `reader-review-task.mjs` 生成。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { featureDir, phaseReportsDir } from './framework-access.mjs';
import { extensionRoot, readJsonOrNull, readTextOrNull } from './paths.mjs';
import { parseYaml } from './yaml.mjs';
import { fenceRanges, tableCells } from '../../skills/story/scripts/core/story/document.mjs';
import { COVERED_CHECKS, DETAIL_KEYS, detailProblems, reviewInputs } from './review-inputs.mjs';

//: 汇总表合同：与原生 verify-* 模板同一张四列表；第四列标题原生现行写法较长，两种都认
const COLUMNS = ['id', 'status', 'severity'];
const EVIDENCE_HEADERS = ['证据', '证据（一行：文件:行 / 引文 / 数值）'];
//: 原生 CheckStatus（summary.schema.json）与 Severity（harness/scripts/utils/types.ts）
const STATUSES = ['PASS', 'WARN', 'FAIL', 'SKIP'];
const SEVERITIES = ['BLOCKER', 'MAJOR', 'MINOR'];

/** 审查请求里的报告结构说明：与下面的核对同一份合同。 */
export function summaryStructure(checkIds = []) {
  const covered = checkIds.filter(id => COVERED_CHECKS[id]);
  return [`**报告结构**：汇总表四格 \`${[...COLUMNS, EVIDENCE_HEADERS[0]].join(' | ')}\`，本阶段每条判据恰好一行（PASS 也列）；`
    + `status 取 ${STATUSES.join(' / ')}，severity 取 ${SEVERITIES.join(' / ')}（FAIL 写判据声明的那一级），证据不空（SKIP 的适用理由写在证据里）；`,
  'status ≠ PASS 的在 YAML 明细 `checks:` 里各出一条，`details` 写问题、依据与改法；PASS 的核验方法写进报告说明，不另列明细；'
    + (covered.length ? `${covered.map(id => `\`${id}\``).join('、')} 无论结论都在明细里出一条，四个键见各自的必审输入表；` : ''),
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
 * 当前审查报告立不立得住 —— 格式合同、局部明细与处置记录，问题一次列全。
 *
 * 报告由调用方原样落盘在 `summary.verifier_report`。不合合同的回复每次运行都报，不计作结论；门禁只读，不写盘、不留结论账本，
 * 重新派审拿回的新回复照同样判据核。报告的身份与有效性（对象回显、过期）由原生 `check-receipt` 判；同行的 Framework 自有判据也归原生核。
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
  const block = resultBlock(text);
  const problems = [];
  if (!block) problems.push(`${name}：终态块不是恰好一个`);
  if (!tables) problems.push(`${name}：没有表头为 \`${[...COLUMNS, EVIDENCE_HEADERS[0]].join(' | ')}\` 的汇总表`);
  const { checks } = overlayChecks(projectRoot, phase);
  const mine = new Map(Object.keys(checks).map(id => [id, rows.filter(r => r[0] === id)]));
  for (const [id, hits] of tables ? mine : []) {
    if (hits.length !== 1) {
      problems.push(`${name} 的汇总表里判据 ${id} ${hits.length ? `有 ${hits.length} 行` : '缺行'}——本阶段每条判据恰好一行`);
      continue;
    }
    const [, status, severity, evidence] = hits[0];
    const declared = String(checks[id]?.severity ?? '').toUpperCase();
    // 阻断与否取报告自己的严重度格：FAIL 的那一格与判据声明不符就判不了，不能借它绕过阻断
    const why = [hits[0].length !== 4 && `有 ${hits[0].length} 格（应为 4 格）`,
      !STATUSES.includes(status) && `status「${status ?? ''}」不是 ${STATUSES.join('/')}`,
      !SEVERITIES.includes(severity) && `severity「${severity ?? ''}」不是 ${SEVERITIES.join('/')}`,
      status === 'FAIL' && SEVERITIES.includes(severity) && declared && declared !== severity
        && `判 FAIL 的严重度 ${severity} 与 rules/${phase}-rules.overlay.yaml 声明的 ${declared} 不符`,
      !evidence && '证据为空'].filter(Boolean);
    if (why.length) problems.push(`${name} 的汇总表判据 ${id}：${why.join('；')}`);
  }
  const blocking = [...mine].filter(([, hits]) => hits.length === 1 && hits[0][1] === 'FAIL' && hits[0][2] === 'BLOCKER').map(([id]) => id);
  if (block?.verdict === 'PASS' && blocking.length) {
    problems.push(`${name}：汇总表 ${blocking.join('、')} 是 BLOCKER 级 FAIL，终态块却是 PASS——结论自相矛盾`);
  }
  // 走局部明细合同的判据：明细四个键对着当前必审集合核
  for (const id of Object.keys(checks).filter(c => COVERED_CHECKS[c])) {
    const hit = mine.get(id)?.length === 1 ? mine.get(id)[0] : null;
    if (hit) problems.push(...coveredProblems(text, name, id, hit[1], reviewInputs(projectRoot, feature, COVERED_CHECKS[id]), Object.keys(checks)));
  }
  if (problems.length) return [`${problems.join('；')}。按 rules/${phase}-rules.overlay.yaml 的 semantic_checks 逐条核，`
    + `不合合同的报告按阻断处理。${INVALID_EVIDENCE}`];

  const subject = block.subject;

  // 处置要指向这一份报告：同一行里有判据编号与报告对象的前 8 位。旧报告的同号处置不替新报告豁免；
  // 处置写得对不对、问题是不是真解决了，归审查与作者的说明，这里只核引用在、指向当前报告。
  const dir = featureDir(projectRoot, feature);
  const notes = ((dir && readTextOrNull(path.join(dir, phase, 'notes.md'))) ?? '').split(/\r?\n/);
  const tag = String(subject ?? '').slice(0, 8);
  const undisposed = [...mine].map(([id, [row]]) => ({ id, status: row[1] }))
    .filter(r => /^(WARN|FAIL)$/.test(r.status) && !notes.some(l => l.includes(r.id) && (!tag || l.includes(tag))));
  return undisposed.length ? [`${phase}/notes.md：审查结论 ${undisposed.map(r => `${r.id}（${r.status}）`).join('、')}没有指向这份报告的处置记录`
    + `——同一行写判据编号与报告对象前 8 位（${tag || '终态块里的 verifier_subject_id'}）再写处置；`
    + '处置的几类（返修、只改表达已重验、改了业务已再审、留给哪一阶段）在 skills/story/reference/phase-closure.md「闭环」'] : [];
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

/** 终态块恰好一个时取它回显的审查对象与结论；不是恰好一个为 null。身份核对归原生 `check-receipt`。 */
function resultBlock(text) {
  const blocks = [...String(text ?? '').matchAll(RESULT_BLOCK)];
  if (blocks.length !== 1) return null;
  const field = key => new RegExp(`^\\s*${key}\\s*:\\s*(\\S+)\\s*$`, 'm').exec(blocks[0][1])?.[1] ?? null;
  return { subject: field('verifier_subject_id'), verdict: field('verdict') };
}

/** 文档里的 YAML 围栏，一个不落地取出来——报告的明细就写在里面。 */
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
 * 明细里这一条的 `details` —— **整段解析，按 id 取项**，不划文本范围：块标量里出现什么字样都是正文，
 * 边界一旦被带偏，读出来的就是另一条的结论。`details` 要是映射；它是一段文字、列表或缺席时，
 * 按 `shape` 说清它实际是什么——说成「缺四个键」的话，作者会去补已经写在文字里的键。
 *
 * @returns {{details: object|null, shape: string|null, unreadable: string|null}}
 */
function checkDetails(text, id) {
  let unreadable = null;
  for (const body of yamlBlocks(text)) {
    let doc;
    try {
      doc = parseYaml(body);
    } catch (e) {
      unreadable = unreadable ?? String(e?.message ?? e);
      continue;
    }
    const entry = checksIn(doc)?.find(c => c && String(c.id ?? '').replace(/`/g, '').trim() === id);
    if (!entry) continue;
    const details = entry.details;
    const mapping = details && typeof details === 'object' && !Array.isArray(details);
    const shape = mapping ? null : typeof details === 'string' ? '是一段文字（YAML 块字符串）'
      : Array.isArray(details) ? '是一个列表' : details === undefined ? '没有写' : `是 ${JSON.stringify(details)}`;
    return { details: mapping ? details : null, shape, unreadable: null };
  }
  return { details: null, shape: null, unreadable };
}

/** 局部明细判据在明细里写成什么形态、与必审集合和结论自不自洽。 */
function coveredProblems(text, name, id, status, basis, checkIds) {
  const { details, shape, unreadable } = checkDetails(text, id);
  if (unreadable) return [`${name} 里的结构块读不出来（${unreadable}）——${id} 的明细在 YAML 围栏里，读不出就核不了`];
  if (shape) return [`${name}：${id} 的 details ${shape}，不是映射——details 下写 ${DETAIL_KEYS.join('、')} 四个键，值都是列表`];
  if (!details) return [`${name} 的 YAML 明细里没有 ${id} 这一条——它无论结论都在明细里写 ${DETAIL_KEYS.join('、')}`];
  return detailProblems(details, status, basis, checkIds).map(p => `${name}：${id} ${p}`);
}
