/**
 * Story 的独立审查 —— 准备这一次的审查对象与任务，核审查者原样落盘的 Story 业务报告。
 *
 * - **准备**：写审查任务，按审查对象算材料键（这一次 Story 的身份），定报告目录与这一份回复的位置。
 *   同一份材料已有有效通过的报告就复用；还没写回复的位置复用；之前的回复坏了或不通过，另起一份，旧回复保留。
 * - **核结果**：显式 check、登记、交付门与状态共用这一份判定，只读：审的是不是现在这份、报告合不合合同、结论是什么。
 *
 * | 结果 | 含义 |
 * |---|---|
 * | pass / warn | 可以登记交付；warn 带非阻断建议 |
 * | fail | 报告有 BLOCKER / MAJOR 发现，或总体结论不通过 |
 * | unreviewed | 宿主没有独立审查能力，人明确授权这一版不经审查交付；披露随结果给出 |
 * | report_missing | 还没准备，或回复不在 |
 * | report_invalid | 回复不合报告合同：格式、判据覆盖、材料引用或结论自相矛盾 |
 * | subject_stale | 当前材料与准备时不同，或报告回显的材料键不是这一份 |
 * | input_invalid | 审查对象不全 |
 *
 * 报告合同通过只证明结构、身份与引用成立，不证明审查独立、业务无遗漏；那两件在真实运行里核。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { readerCheckIds, readerReviewTask } from '../../../../../hooks/shared/reader-review-task.mjs';
import { readJson } from './context.mjs';
import { tableCells } from './document.mjs';
import { TASK, materialKey, reviewObject } from './review-object.mjs';

const REPORT_HEADINGS = ['判据核对', '发现', '总体结论'];
const CHECK_HEADER = ['判据 ID', '结果', '依据'];
const FINDING_HEADER = ['编号', '严重程度', '判据 ID', '材料位置', '问题与依据', '修正责任'];
const SEVERITIES = ['BLOCKER', 'MAJOR', 'MINOR', 'INFO'];
const reply = n => `review-original.${n}.md`;

function places(ctx) {
  const dir = path.join(ctx.featureRoot, ...TASK.slice(0, -1));
  return { dir, prepared: path.join(dir, 'prepared.json') };
}

const abs = (ctx, rel) => path.join(ctx.projectRoot, ...String(rel).split('/'));

/**
 * 准备这一次的审查。审查对象要先成最终版：调用方已重投附录、编号、渲染 Review 并过了结构检查。
 *
 * @returns {{error?: string, material_key?: string, task?: string, rows?: object[], report_dir?: string,
 *   report_file?: string, reused?: boolean}}
 */
export function prepareReview(ctx, reportDirArg) {
  const { dir, prepared } = places(ctx);
  fs.mkdirSync(dir, { recursive: true });
  const task = path.join(ctx.featureRoot, ...TASK);
  // 任务是审查对象的一部分，所以不嵌入由对象算出的材料键：材料键由准备输出交给派审方
  fs.writeFileSync(task, `${readerReviewTask(ctx.projectRoot, ctx.args.feature)}\n`, 'utf-8');
  const object = reviewObject(ctx.projectRoot, ctx.args.feature);
  if (object.problems.length) return { error: `审查对象不全：${object.problems.join('；')}` };
  const key = materialKey(ctx.projectRoot, object.rows);
  const reportDir = reportDirArg ?? `doc/reports/story/${ctx.args.feature}/${key.slice(0, 16)}`;
  const was = readJson(prepared, null);
  let reportFile = null;
  let reused = false;
  if (was?.material_key === key && was.report_file) {
    const last = judge(ctx, was, object.rows);
    if (['pass', 'warn'].includes(last.result)) reused = true;
    if (reused || last.result === 'report_missing') reportFile = was.report_file;
  }
  if (!reportFile) {
    const taken = fs.existsSync(abs(ctx, reportDir)) ? fs.readdirSync(abs(ctx, reportDir))
      .map(f => /^review-original\.(\d+)\.md$/.exec(f)?.[1]).filter(Boolean).map(Number) : [];
    reportFile = `${reportDir}/${reply(Math.max(0, ...taken) + 1)}`;
  }
  const unreviewed = was?.material_key === key ? was.unreviewed : undefined;
  fs.writeFileSync(prepared, `${JSON.stringify({ material_key: key, report_dir: reportDir, report_file: reportFile,
    ...(unreviewed ? { unreviewed } : {}) }, null, 2)}\n`, 'utf-8');
  const rel = path.relative(ctx.projectRoot, task).split(path.sep).join('/');
  return { material_key: key, task: rel, rows: object.rows, report_dir: reportDir, report_file: reportFile, reused };
}

/**
 * 宿主没有独立审查能力时，人明确授权这一版不经审查交付：原话与缺什么记在这一次的准备记录里，绑定当前材料键。
 * 材料一变授权就不再适用。坏报告、没派审、工具失败不归这一类。
 */
export function authorizeUnreviewed(ctx, reason, words) {
  const { prepared } = places(ctx);
  const was = readJson(prepared, null);
  const object = reviewObject(ctx.projectRoot, ctx.args.feature);
  if (object.problems.length) return { error: `审查对象不全：${object.problems.join('；')}` };
  if (!was?.material_key || was.material_key !== materialKey(ctx.projectRoot, object.rows)) {
    return { error: '先 `story-build review --action prepare` 把这一版定稿；授权绑定的是定稿的这一份材料' };
  }
  if (!String(reason ?? '').trim() || !String(words ?? '').trim()) {
    return { error: '要写明宿主缺什么（--reason）和人授权的原话（--reply）' };
  }
  const unreviewed = { reason: reason.trim(), reply: words.trim(), at: new Date().toISOString() };
  fs.writeFileSync(prepared, `${JSON.stringify({ ...was, unreviewed }, null, 2)}\n`, 'utf-8');
  return { unreviewed };
}

/** 这一次审查的结果，只读。显式 check、登记、交付门与状态共用。 */
export function reviewResult(ctx) {
  const was = readJson(places(ctx).prepared, null);
  if (!was?.material_key) {
    return { result: 'report_missing', detail: '还没准备这一次的审查——先跑 `story-build review --action prepare`' };
  }
  const object = reviewObject(ctx.projectRoot, ctx.args.feature);
  if (object.problems.length) return { result: 'input_invalid', detail: `审查对象不全：${object.problems.join('；')}` };
  if (materialKey(ctx.projectRoot, object.rows) !== was.material_key) {
    return { result: 'subject_stale', detail: '准备审查之后审查对象变了——审的不是现在这份，重新 prepare，按新材料再审' };
  }
  return judge(ctx, was, object.rows);
}

/** 二级标题下的内容，标题按原文逐字匹配。 */
function sections(text) {
  const out = new Map();
  const parts = String(text).split(/^## +(.+?)\s*$/m);
  for (let i = 1; i < parts.length; i += 2) out.set(parts[i], [...(out.get(parts[i]) ?? []), parts[i + 1]]);
  return out;
}

/** 一节里的第一张表：表头与数据行（分隔行去掉）。没有表返回 null。 */
function table(body) {
  const lines = String(body ?? '').split(/\r?\n/).map(l => l.trim());
  const start = lines.findIndex(l => l.startsWith('|'));
  if (start < 0) return null;
  const rows = [];
  for (const line of lines.slice(start)) {
    if (!line.startsWith('|')) break;
    rows.push(tableCells(line).map(c => c.replace(/[`*]/g, '').trim()));
  }
  const [header, , ...data] = rows;
  return { header, data };
}

/** 报告对准备记录与当前材料：材料键、三节、判据逐项、发现的材料引用、结论与发现一致。 */
function judge(ctx, was, materials) {
  const at = { report_file: was.report_file };
  const file = abs(ctx, was.report_file);
  if (!fs.existsSync(file)) {
    if (was.unreviewed) {
      return { result: 'unreviewed', detail: `本版未经独立审查：${was.unreviewed.reason}；人授权原话「${was.unreviewed.reply}」`, ...at };
    }
    return { result: 'report_missing', detail: `审查者的回复不在 ${was.report_file}——把独立审查者的回复原样写到那里`, ...at };
  }
  const text = fs.readFileSync(file, 'utf-8');
  const invalid = why => ({ result: 'report_invalid',
    detail: `回复不合报告合同：${why.join('；')}——保留这份回复，请审查者按任务「报告怎么写」重给，不改它的结论`, ...at });
  const keys = [...text.matchAll(/^material_key: *([0-9a-f]{64}) *$/gm)].map(m => m[1]);
  if (keys.length !== 1) return invalid([`material_key 行要恰好一行（现在 ${keys.length} 行）`]);
  if (keys[0] !== was.material_key) {
    return { result: 'subject_stale', detail: '报告回显的材料键不是这一次准备的——审的不是现在这份，按新任务重新派审', ...at };
  }
  const parts = sections(text);
  const why = REPORT_HEADINGS.filter(h => parts.get(h)?.length !== 1).map(h => `二级标题「${h}」要恰好一个`);
  if (why.length) return invalid(why);
  const ids = readerCheckIds();
  const checks = table(parts.get('判据核对')[0]);
  if (!checks || JSON.stringify(checks.header) !== JSON.stringify(CHECK_HEADER)) {
    return invalid([`「判据核对」要一张表，表头 ${CHECK_HEADER.join(' | ')}`]);
  }
  const seen = checks.data.map(r => r[0]);
  if (JSON.stringify([...seen].sort()) !== JSON.stringify([...ids].sort())) why.push(`判据要逐项各一行：应有 ${ids.join('、')}，写了 ${seen.join('、') || '（无）'}`);
  for (const [id, result, basis] of checks.data) {
    if (!['pass', 'warn', 'fail', 'not_applicable'].includes(result)) why.push(`判据 ${id} 的结果「${result}」不是 pass/warn/fail/not_applicable`);
    if (!basis) why.push(`判据 ${id} 没写依据`);
  }
  const found = table(parts.get('发现')[0]);
  if (!found || JSON.stringify(found.header) !== JSON.stringify(FINDING_HEADER)) {
    return invalid([...why, `「发现」要一张表，表头 ${FINDING_HEADER.join(' | ')}；没有发现留空表`]);
  }
  const paths = materials.map(m => m.path);
  for (const [no, severity, id, where, what, owner] of found.data) {
    if (!no || !what || !owner) why.push(`发现 ${no || '（无编号）'} 缺编号、问题与依据或修正责任`);
    if (!SEVERITIES.includes(severity)) why.push(`发现 ${no} 的严重程度「${severity}」不是 ${SEVERITIES.join('/')}`);
    if (!ids.includes(id)) why.push(`发现 ${no} 的判据 ID「${id}」不在判据里`);
    if (!paths.some(p => where.includes(p))) why.push(`发现 ${no} 的材料位置「${where}」不是这一次审查材料里的文件`);
  }
  const numbers = found.data.map(r => r[0]);
  if (new Set(numbers).size !== numbers.length) why.push('发现编号有重复');
  const stated = /^(pass|warn|fail)\b(.*)$/m.exec(String(parts.get('总体结论')[0]).trim());
  if (!stated) why.push('「总体结论」第一行写 pass、warn 或 fail 之一，再写理由');
  if (why.length) return invalid(why);
  const severe = found.data.filter(r => ['BLOCKER', 'MAJOR'].includes(r[1]));
  const derived = severe.length || checks.data.some(r => r[1] === 'fail') ? 'fail'
    : found.data.length || checks.data.some(r => r[1] === 'warn') ? 'warn' : 'pass';
  if (stated[1] !== derived) return invalid([`总体结论写 ${stated[1]}，按判据与发现应为 ${derived}`]);
  const listed = rows => rows.map(r => `${r[0]} ${r[1]} ${r[4]}`);
  if (derived === 'fail') return { result: 'fail', detail: `审查结论阻断：${listed(severe).join('；') || '判据核对有 fail'}`, ...at };
  const advisories = listed(found.data);
  return { result: derived, detail: derived === 'warn' ? `非阻断建议 ${advisories.length} 条` : '审查通过', advisories, ...at };
}
