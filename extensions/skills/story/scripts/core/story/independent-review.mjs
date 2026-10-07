/**
 * Story 的独立审查 —— 准备这一次的审查对象与任务，核审查者原样落盘的 Story 业务报告。
 *
 * - **准备**：写审查任务，按审查对象算材料键（这一次 Story 的身份），定这一份回复的位置，生成派审载体 `dispatch.md`
 *   （材料键、任务、回复位置与返修上下文，主执行者原样交给隔离审查者）。报告目录随材料键在首次准备时
 *   定下，同一份材料沿用它，另指目录报冲突。
 *   这份材料在报告目录里的结论与核结果同一份读取：有效通过（pass / warn）就复用那份回复，材料改走又改回来也一样；
 *   其余情况另起下一个编号的回复位置，旧回复保留。
 * - **核结果**：显式 check、登记、交付门与状态共用这一份判定，只读：审的是不是现在这份、报告合不合合同、结论是什么。
 *
 * | 结果 | 含义 |
 * |---|---|
 * | pass / warn | 可以登记交付；warn 带非阻断建议 |
 * | fail | 报告有 BLOCKER / MAJOR 发现，或总体结论不通过 |
 * | unreviewed | 宿主没有独立审查能力，人明确授权这一版不经审查交付；授权记在流程契约，披露写进 Story 与 Review |
 * | report_missing | 还没准备，或回复不在 |
 * | report_invalid | 回复不合报告合同：格式、判据覆盖、材料引用或结论自相矛盾 |
 * | subject_stale | 当前材料与准备时不同，或报告回显的材料键不是这一份 |
 * | input_invalid | 审查对象不全 |
 *
 * 报告合同通过只证明结构、身份与引用成立，不证明审查独立、业务无遗漏；那两件在真实运行里核。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { hostReviewer } from '../../../../../hooks/shared/framework-access.mjs';
import { readerCheckIds, readerReviewTask } from '../../../../../hooks/shared/reader-review-task.mjs';
import { readJson, readText, replaceFile } from './context.mjs';
import { chapterSpan, tableCells, zoneBlock, zoneSpan } from './document.mjs';
import { TASK, materialKey, reviewObject } from './review-object.mjs';
import {
  CHECK_HEADER, CHECK_RESULTS, FINDING_HEADER, REPORT_HEADINGS, SEVERITIES,
} from './review-report-contract.mjs';

const reply = n => `review-original.${n}.md`;
const sha256 = data => crypto.createHash('sha256').update(data).digest('hex');

function places(ctx) {
  const dir = path.join(ctx.featureRoot, ...TASK.slice(0, -1));
  return { dir, prepared: path.join(dir, 'prepared.json'), dispatch: path.join(dir, 'dispatch.md') };
}


const abs = (ctx, rel) => path.join(ctx.projectRoot, ...String(rel).split('/'));

/**
 * 准备这一次的审查。审查对象要先成最终版：调用方已重投附录、编号、渲染 Review（含审查状态披露）并过了结构检查。
 *
 * @returns {{error?: string, material_key?: string, task?: string, rows?: object[], report_dir?: string,
 *   report_file?: string, reused?: boolean}}
 */
export function prepareReview(ctx, reportDirArg) {
  const { dir, prepared, dispatch } = places(ctx);
  fs.mkdirSync(dir, { recursive: true });
  const task = path.join(ctx.featureRoot, ...TASK);
  // 任务是审查对象的一部分，所以不嵌入由对象算出的材料键：材料键经派审载体交给审查者
  const taskText = `${readerReviewTask(ctx.projectRoot, ctx.args.feature)}\n`;
  if (readText(task) !== taskText) fs.writeFileSync(task, taskText, 'utf-8');
  const object = reviewObject(ctx.projectRoot, ctx.args.feature);
  if (object.problems.length) return { error: `审查对象不全：${object.problems.join('；')}` };
  const key = materialKey(ctx.projectRoot, object.rows);
  const was = readJson(prepared, null);
  // 报告目录随材料键定一次：同一份材料的历次回复都在这个目录里，结论按它们取
  const bound = was?.report_dirs?.[key];
  const asked = reportDirArg && String(reportDirArg).replace(/\\/g, '/').replace(/^\.\//, '').replace(/\/+$/, '');
  if (bound && asked && asked !== bound) {
    return { error: `报告目录冲突：这一份材料（材料键 ${key.slice(0, 16)}…）的报告目录在首次准备时定为 ${bound}，`
      + `这次指定的是 ${asked}。同一份材料的回复都在 ${bound}，准备记录与已有回复未改动；去掉 --report-dir 或写 ${bound} 重跑` };
  }
  const reportDir = bound ?? asked ?? `doc/reports/story/${ctx.args.feature}/${key.slice(0, 16)}`;
  const choice = replyPlace(ctx, was, key, reportDir, object.rows);
  // 授权随这一次准备沿用与否，在准备开始时判定一次（`pendingDisclosure`）；披露已写进文件，材料键里含它
  const waiver = disclosedWaiver(ctx);
  const record = { material_key: key, project_root: ctx.projectRoot.split(path.sep).join('/'), report_dir: reportDir,
    report_file: choice.reportFile,
    report_dirs: { ...was?.report_dirs, [key]: reportDir }, ...(waiver ? { waiver_at: waiver.at } : {}),
    ...(choice.reused ? { reused: true } : {}), ...(choice.context ? { review_context: choice.context } : {}),
    ...(ctx.designReviewSha256 ? { design_review_sha256: ctx.designReviewSha256 } : {}) };
  const rel = path.relative(ctx.projectRoot, task).split(path.sep).join('/');
  const dispatchText = dispatchFor(ctx, record, rel);
  // 派审载体先落盘，准备记录最后替换：两者对不上时 check 报 input_invalid，重跑 prepare 即可
  replaceFile(dispatch, dispatchText);
  replaceFile(prepared, `${JSON.stringify(record, null, 2)}\n`);
  return { material_key: key, task: rel, rows: object.rows, report_dir: reportDir, report_file: choice.reportFile,
    reused: choice.reused, dispatch_file: path.relative(ctx.projectRoot, dispatch).split(path.sep).join('/'),
    dispatch_text: dispatchText };
}

/**
 * 这一次回复写在哪、派审要带什么上下文。
 *
 * - 有可复用的 pass / warn：复用原回复，不派审；
 * - 同一份材料已准备、回复还没来：沿用这个位置与它的上下文；
 * - 当前回复不合报告合同：下一个编号，带原回复与诊断交独立格式返修；
 * - 这份材料已有有效 fail：下一个编号，带失败报告交独立复审；
 * - 其余（首审、材料变了）：下一个编号，不带上下文。
 */
function replyPlace(ctx, was, key, reportDir, rows) {
  const current = was?.material_key === key ? was.report_file : null;
  const known = materialConclusion(ctx, key, reportDir, current, rows);
  if (['pass', 'warn'].includes(known?.result)) return { reportFile: known.report_file, reused: true, context: null };
  if (current && !was.reused && !fs.existsSync(abs(ctx, current))) {
    return { reportFile: current, reused: false, context: was.review_context ?? null };
  }
  const next = `${reportDir}/${reply(Math.max(0, ...replyNumbers(ctx, reportDir)) + 1)}`;
  let context = null;
  if (known?.result === 'report_invalid') {
    // 当前回复不合合同时，check 读目录里其余回复中最新的有效结论；那里有通过结论就直接复用
    const earlier = earlierConclusion(ctx, key, reportDir, current, rows);
    if (['pass', 'warn'].includes(earlier?.result)) return { reportFile: earlier.report_file, reused: true, context: null };
    context = contextOf(ctx, 'format_repair', known);
  } else if (known?.result === 'fail') {
    context = contextOf(ctx, 'recheck', known);
  }
  return { reportFile: next, reused: false, context };
}

function contextOf(ctx, kind, known) {
  return { kind, report_file: known.report_file, report_sha256: sha256(fs.readFileSync(abs(ctx, known.report_file))),
    diagnostic: { result: known.result, detail: known.detail } };
}

/**
 * 派审载体：由准备记录确定性生成，主执行者原样作为宿主 task 的 prompt 交给隔离审查者。
 * 材料键、任务、回复位置与返修上下文都在这里，不经主执行者转述。
 */
function dispatchFor(ctx, record, task) {
  const head = ['# Story 独立人读审查 · 派审', '',
    `- 工程根：\`${record.project_root}\``,
    `- 材料键：\`${record.material_key}\``,
    `- 审查任务：\`${task}\``];
  if (record.reused) {
    return `${[...head, `- 已有通过的回复：\`${record.report_file}\``, '',
      '这份材料已有可复用的审查结论，这一次不派审，直接跑 `story-build review --action check`。'].join('\n')}\n`;
  }
  const out = [...head, `- 回复写到：\`${record.report_file}\`（工程相对路径）`, '',
    '你是与作者隔离的独立审查者。按审查任务原文执行：只读被审材料与对照材料，只写上面这一份回复，其余文件保持原样。',
    `回复第一行写 \`material_key: ${record.material_key}\`，其余格式见任务「报告怎么写」。`];
  const c = record.review_context;
  if (c?.kind === 'format_repair') {
    out.push('', '## 上一份回复不合报告合同', '',
      `原回复：\`${c.report_file}\`（SHA-256 ${c.report_sha256}），只读，保持原样。核对给出的诊断原文：`, '',
      ...String(c.diagnostic.detail).split(/\r?\n/).map(l => `> ${l}`), '',
      '按任务给一份合格的完整报告写到上面的回复位置。原回复里的每条事实与引用回材料核过再写，核不到的不写。');
  } else if (c?.kind === 'recheck') {
    out.push('', '## 这份材料上一次的审查结论是 fail', '',
      `上一次的回复：\`${c.report_file}\`（SHA-256 ${c.report_sha256}），只读。它的阻断结论：`, '',
      ...String(c.diagnostic.detail).split(/\r?\n/).map(l => `> ${l}`), '',
      '对当前材料做一次完整审查：每条阻断现在是否成立由你按材料独立判断，其余判据照常逐项核。');
  }
  return `${out.join('\n')}\n`;
}

/** 派审载体与准备记录、返修上下文里的原回复还对不对得上：对不上返回原因。 */
function dispatchProblem(ctx, was) {
  const { dispatch } = places(ctx);
  const task = path.relative(ctx.projectRoot, path.join(ctx.featureRoot, ...TASK)).split(path.sep).join('/');
  if (readText(dispatch) !== dispatchFor(ctx, was, task)) {
    return '派审载体 AR/story-src/review/dispatch.md 不在，或与准备记录对不上';
  }
  const c = was.review_context;
  if (c?.report_file) {
    let bytes = null;
    try { bytes = fs.readFileSync(abs(ctx, c.report_file)); } catch { bytes = null; }
    if (bytes === null || sha256(bytes) !== c.report_sha256) {
      return `派审带着的原回复 ${c.report_file} ${bytes === null ? '不在' : '字节变了'}：它是独立审查者的原件，恢复宿主保存的原样；`
        + '恢复不了就保留现场，重新 prepare 做一次完整独立审查';
    }
  }
  return null;
}

/**
 * 准备开始时判一次：流程契约里人授权的未审查交付，这一次准备沿不沿用。
 * 授权给在上一次准备的那一版上，或已随它沿用过；且那之后被审材料没再变、宿主仍没有独立审查能力。
 * 结论存进 `ctx.disclosure`，Review 题头与 Story 交付章按同一个结论写披露。
 */
export function pendingDisclosure(ctx) {
  const waiver = readJson(ctx.flowPath, null)?.review_waiver;
  const was = readJson(places(ctx).prepared, null);
  let applies = Boolean(waiver?.at && was?.material_key)
    && (waiver.material_key === was.material_key || was.waiver_at === waiver.at);
  if (applies) {
    const object = reviewObject(ctx.projectRoot, ctx.args.feature);
    applies = !object.problems.length && materialKey(ctx.projectRoot, object.rows) === was.material_key
      && !hostReviewer(ctx.projectRoot).declared;
  }
  ctx.disclosure = applies ? waiver : null;
  return ctx.disclosure;
}

/** 要写进交付件的未审查授权：准备过程中用开头判定的结论，其余时候只认已随准备记录沿用的那一条。 */
function disclosedWaiver(ctx) {
  if (ctx.disclosure !== undefined) return ctx.disclosure;
  const waiver = readJson(ctx.flowPath, null)?.review_waiver;
  const was = readJson(places(ctx).prepared, null);
  return waiver?.at && was?.waiver_at === waiver.at && !hostReviewer(ctx.projectRoot).declared ? waiver : null;
}

/** 审查状态的机器区：Story 交付章与 Review 题头共用这一份，区名取章节合同；没有适用的授权返回空。 */
export function reviewStatusBlock(ctx) {
  const name = (ctx.contract.chapters ?? []).find(c => c.review_status)?.review_status;
  const rows = reviewStatusLines(disclosedWaiver(ctx));
  return name && rows.length ? zoneBlock(name, '人授权的未审查交付记录', rows) : [];
}

function reviewStatusLines(waiver) {
  return waiver ? [`本版未经独立审查。原因：${waiver.reason}。人授权不经审查交付的原话：「${waiver.reply}」（${waiver.at}）。`
    + '授权只适用于这一版，材料再变需要重新审查或重新授权。'] : [];
}

/**
 * 记授权之前的核对（`story_flow.py unreviewed` 调用）：宿主有没有独立审查能力、这一版现在的审查结果。
 * 授权的前提：当前 adapter 没声明审查子代理，且这一版的结果是 report_missing。
 */
export function waiverCheck(ctx) {
  const host = hostReviewer(ctx.projectRoot);
  const was = readJson(places(ctx).prepared, null);
  const now = reviewResult(ctx);
  return { host_reviewer: host.declared, adapter: host.adapter, result: now.result, detail: now.detail,
    material_key: was?.material_key ?? null };
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
    return { result: 'subject_stale', detail: '准备审查之后审查对象变了：重跑 prepare，按新任务与材料键再派审' };
  }
  const broken = dispatchProblem(ctx, was);
  if (broken) return { result: 'input_invalid', detail: `${broken}——重跑 \`story-build review --action prepare\`，按新生成的派审载体派审` };
  const at = { report_file: was.report_file };
  // 这一份还没回复时，同一份材料之前已有的有效结论仍在：重新准备不撤销已知的阻断
  const known = materialConclusion(ctx, was.material_key, was.report_dir, was.report_file, object.rows);
  if (known) return known;
  const waiver = readJson(ctx.flowPath, null)?.review_waiver;
  if (waiver?.at && was.waiver_at === waiver.at && !hostReviewer(ctx.projectRoot).declared) {
    return { result: 'unreviewed', detail: `本版未经独立审查：${waiver.reason}；人授权原话「${waiver.reply}」（${waiver.at}）`, ...at };
  }
  return { result: 'report_missing', detail: `审查者的回复不在 ${was.report_file}——把独立审查者的回复原样写到那里`, ...at };
}

/**
 * 这一份材料在它的报告目录里的结论，prepare 与 check 共用：当前回复位置有回复就判它；
 * 没有就从目录里其余回复取最新的有效结论；都没有返回 null。
 */
function materialConclusion(ctx, key, reportDir, reportFile, materials) {
  if (reportFile && fs.existsSync(abs(ctx, reportFile))) {
    return { ...judge(fs.readFileSync(abs(ctx, reportFile), 'utf-8'), key, materials), report_file: reportFile };
  }
  return earlierConclusion(ctx, key, reportDir, reportFile, materials);
}

/** 报告目录里已有回复的编号。 */
function replyNumbers(ctx, reportDir) {
  const dir = abs(ctx, reportDir);
  return fs.existsSync(dir) ? fs.readdirSync(dir).map(f => Number(/^review-original\.(\d+)\.md$/.exec(f)?.[1])).filter(Boolean) : [];
}

/** 报告目录里除 `skip` 之外的回复，从新到旧取第一份有效结论（pass / warn / fail）；没有返回 null。 */
function earlierConclusion(ctx, key, reportDir, skip, materials) {
  const files = replyNumbers(ctx, reportDir).sort((a, b) => b - a).map(n => `${reportDir}/${reply(n)}`);
  for (const rel of files.filter(f => f !== skip)) {
    const out = judge(fs.readFileSync(abs(ctx, rel), 'utf-8'), key, materials);
    if (['pass', 'warn', 'fail'].includes(out.result)) return { ...out, report_file: rel };
  }
  return null;
}

/** 二级标题下的内容，标题按原文逐字匹配。 */
function sections(text) {
  const out = new Map();
  const parts = String(text).split(/^## +(.+?)\s*$/m);
  for (let i = 1; i < parts.length; i += 2) out.set(parts[i], [...(out.get(parts[i]) ?? []), parts[i + 1]]);
  return out;
}

const plain = c => c.replace(/[`*]/g, '').trim();
const cells = line => tableCells(line).map(plain);

/**
 * 一节里的第一张表：表头、分隔行与数据行逐行核列数，读不完整就报，不丢行。没有表返回 null。
 * `data` 去掉了反引号与强调符；`raw` 是原单元格，材料位置从它取引用边界。
 */
function table(body) {
  const lines = String(body ?? '').split(/\r?\n/).map(l => l.trim());
  const start = lines.findIndex(l => l.startsWith('|'));
  if (start < 0) return null;
  const end = lines.findIndex((l, i) => i > start && !l.startsWith('|'));
  const block = lines.slice(start, end < 0 ? undefined : end);
  const header = cells(block[0]);
  const rule = tableCells(block[1] ?? '');
  if (rule.length !== header.length || !rule.every(c => /^:?-{3,}:?$/.test(c))) {
    return { header, error: '表头下一行要是分隔行（每列 ---），列数与表头相同' };
  }
  const raw = block.slice(2).map(l => tableCells(l).map(c => c.trim()));
  const bad = raw.findIndex(r => r.length !== header.length);
  if (bad >= 0) return { header, error: `第 ${bad + 1} 行数据有 ${raw[bad].length} 列，表头是 ${header.length} 列` };
  return { header, data: raw.map(r => r.map(plain)), raw };
}

/**
 * 材料位置写到的文件：有反引号时每段反引号是一条路径，没有时整格是一条路径（路径可含空格）。
 * 取得完整路径后再去掉章节定位（`#…`）与行号（`:行`）。
 */
function locations(cell) {
  const text = String(cell).trim();
  const quoted = [...text.matchAll(/`([^`]+)`/g)].map(m => m[1]);
  return (quoted.length ? quoted : [text]).map(t => t.trim().replace(/#.*$/, '').replace(/:\d+(-\d+)?$/, ''))
    .filter(Boolean);
}

/** 一份回复对这一份材料：材料键、三节、判据逐项、发现的材料引用、结论与发现一致。 */
function judge(text, key, materials) {
  const invalid = why => ({ result: 'report_invalid',
    detail: `回复不合报告合同：${why.join('；')}。这份回复留在原处；跑 \`story-build review --action prepare\` 取新的回复位置，`
      + '按它生成的派审载体交独立审查者重给一份' });
  const keys = [...text.matchAll(/^material_key: *([0-9a-f]{64}) *$/gm)].map(m => m[1]);
  if (keys.length !== 1) return invalid([`material_key 行要恰好一行（现在 ${keys.length} 行）`]);
  if (keys[0] !== key) return { result: 'subject_stale', detail: '报告回显的材料键不是这一次准备的：按这一次的任务与材料键重新派审' };
  const parts = sections(text);
  const why = REPORT_HEADINGS.filter(h => parts.get(h)?.length !== 1).map(h => `二级标题「${h}」要恰好一个`);
  if (why.length) return invalid(why);
  const ids = readerCheckIds();
  const checks = table(parts.get('判据核对')[0]);
  if (!checks || JSON.stringify(checks.header) !== JSON.stringify(CHECK_HEADER) || checks.error) {
    return invalid([`「判据核对」要一张表，表头 ${CHECK_HEADER.join(' | ')}${checks?.error ? `：${checks.error}` : ''}`]);
  }
  const found = table(parts.get('发现')[0]);
  if (!found || JSON.stringify(found.header) !== JSON.stringify(FINDING_HEADER) || found.error) {
    return invalid([`「发现」要一张表，表头 ${FINDING_HEADER.join(' | ')}；没有发现保留表头与分隔行${found?.error ? `：${found.error}` : ''}`]);
  }
  const seen = checks.data.map(r => r[0]);
  if (JSON.stringify([...seen].sort()) !== JSON.stringify([...ids].sort())) why.push(`判据要逐项各一行：应有 ${ids.join('、')}，写了 ${seen.join('、') || '（无）'}`);
  for (const [id, result, basis] of checks.data) {
    if (!CHECK_RESULTS.includes(result)) why.push(`判据 ${id} 的结果「${result}」不是 ${CHECK_RESULTS.join('/')}`);
    if (!basis) why.push(`判据 ${id} 没写依据`);
  }
  const paths = new Set(materials.map(m => m.path));
  found.data.forEach(([no, severity, id, where, what, owner], i) => {
    if (!no || !what || !owner) why.push(`发现 ${no || '（无编号）'} 缺编号、问题与依据或修正责任`);
    if (!SEVERITIES.includes(severity)) why.push(`发现 ${no} 的严重程度「${severity}」不是 ${SEVERITIES.join('/')}`);
    if (!ids.includes(id)) why.push(`发现 ${no} 的判据 ID「${id}」不在判据里`);
    const refs = locations(found.raw[i][3]);
    if (!refs.length || refs.some(r => !paths.has(r))) why.push(`发现 ${no} 的材料位置「${where}」不是这一次审查材料里的文件`);
  });
  const numbers = found.data.map(r => r[0]);
  if (new Set(numbers).size !== numbers.length) why.push('发现编号有重复');
  const lines = String(parts.get('总体结论')[0]).split(/\r?\n/).map(l => l.trim()).filter(Boolean);
  const stated = /^(pass|warn|fail)(?![A-Za-z])[\s:：,，、。]*(.*)$/.exec(lines[0] ?? '');
  if (!stated || (!stated[2] && lines.length < 2)) why.push('「总体结论」第一行写 pass、warn 或 fail 之一，再写理由');
  if (why.length) return invalid(why);
  const severe = found.data.filter(r => ['BLOCKER', 'MAJOR'].includes(r[1]));
  const derived = severe.length || checks.data.some(r => r[1] === 'fail') ? 'fail'
    : found.data.length || checks.data.some(r => r[1] === 'warn') ? 'warn' : 'pass';
  if (stated[1] !== derived) return invalid([`总体结论写 ${stated[1]}，按判据与发现应为 ${derived}`]);
  const listed = rows => rows.map(r => `${r[0]} ${r[1]} ${r[4]}`);
  if (derived === 'fail') return { result: 'fail', detail: `审查结论阻断：${listed(severe).join('；') || '判据核对有 fail'}` };
  const advisories = listed(found.data);
  return { result: derived, detail: derived === 'warn' ? `非阻断建议 ${advisories.length} 条` : '审查通过', advisories };
}

/**
 * Story 交付章里的审查状态：有适用的未审查授权就写机器区，没有就撤掉；在哪一章、区名取章节合同。
 * 准备审查时在算材料键之前调用，披露是被审、被登记的内容；同样的输入重跑不改字节。
 */
export function discloseInStory(ctx) {
  const chapter = (ctx.contract.chapters ?? []).find(c => c.review_status);
  const text = readText(ctx.storyPath);
  const span = chapter && text !== null ? chapterSpan(text, chapter.title) : null;
  if (!span) return;
  const eol = text.includes('\r\n') ? '\r\n' : '\n';
  let lines = text.slice(span.start, span.end).split(/\r?\n/);
  const at = zoneSpan(lines, chapter.review_status);
  if (at) lines = [...lines.slice(0, at.start > 0 && !lines[at.start - 1].trim() ? at.start - 1 : at.start), ...lines.slice(at.end)];
  const block = reviewStatusBlock(ctx);
  if (block.length) {
    let k = lines.length;
    while (k > 0 && !lines[k - 1].trim()) k -= 1;
    lines = [...lines.slice(0, k), '', ...block, ...lines.slice(k)];
  }
  const out = text.slice(0, span.start) + lines.join(eol) + text.slice(span.end);
  if (out !== text) fs.writeFileSync(ctx.storyPath, out, 'utf-8');
}
