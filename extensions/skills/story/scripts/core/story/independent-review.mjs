/**
 * Story 的独立审查 —— 准备这一次的审查对象与任务，核审查者原样落盘的 Story 业务报告。
 *
 * - **准备**：写审查任务，按审查对象算材料键（这一次 Story 的身份），定这一份回复的位置，生成派审载体 `dispatch.md`
 *   （Story 路径、首读问题、材料键、任务与回复位置，主执行者原样交给隔离审查者）；有前轮报告时另写前轮上下文
 *   `context.md`（原回复、诊断或结论），审查者首读之后才读。报告目录随材料键在首次准备时定下，同一份材料沿用它，另指目录报冲突。
 * - **接收**：审查者的回复原样落盘后重跑准备：它读这份回复、记下原样字节的摘要（`originals`），再按结论定下一步。
 *   没接收过的回复不作可消费的结论；接收之后字节变了的回复不再读出结论。摘要只能发现接收之后的改动。
 *   这份材料在报告目录里的结论与核结果同一份读取：有效通过（pass / warn）就复用那份回复，材料改走又改回来也一样；
 *   其余情况另起下一个编号的回复位置，旧回复保留。材料换了新键时，紧前一次准备的原报告随派审交出作待核参考，结论只对新材料。
 * - **核结果**：显式 check、登记、交付门与状态共用这一份判定，只读：审的是不是现在这份、报告合不合合同、结论是什么。
 *
 * | 结果 | 含义 |
 * |---|---|
 * | pass / warn | 可以登记交付；warn 带非阻断建议 |
 * | fail | 报告有 BLOCKER / MAJOR 发现，或总体结论不通过；宿主没有审查员时，上一版的阻断改过之后没人复核也记为它（已知必修未复核） |
 * | unreviewed | 当前宿主没有声明 Story 独立审查能力：这一版如实记为未审，准备时把审查状态写进 Story 与 Review；不是业务完成、设计准入或发布质量结论 |
 * | report_missing | 还没准备，或回复不在 |
 * | report_unreceived | 回复在，还没经准备接收（没记原件摘要） |
 * | report_invalid | 回复不合报告合同：格式、判据覆盖、材料引用或结论自相矛盾；或接收之后被改过 |
 * | subject_stale | 当前材料与准备时不同，或报告回显的材料键不是这一份 |
 * | input_invalid | 审查对象不全 |
 *
 * 报告合同通过只证明结构、身份与引用成立，不证明审查独立、业务无遗漏；那两件在真实运行里核。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { hostReviewer, storyReviewVisual } from '../../../../../hooks/shared/framework-access.mjs';
import { detailProblems, inputPath } from '../../../../../hooks/shared/review-inputs.mjs';
import { parseYaml } from '../../../../../hooks/shared/yaml.mjs';
import { readerCheckIds, readerReviewTask } from '../../../../../hooks/shared/reader-review-task.mjs';
import { readJson, readText, replaceFile } from './context.mjs';
import { chapterSpan, fenceRanges, tableCells, zoneBlock, zoneSpan } from './document.mjs';
import { TASK, materialKey, reviewObject, withTaskRow } from './review-object.mjs';
import { designSource } from './design-source.mjs';
import {
  CHECK_HEADER, CHECK_RESULTS, COVERAGE_KEY, COVERAGE_KEYS, FINDING_HEADER, REPORT_HEADINGS, SEVERITIES,
} from './review-report-contract.mjs';

const reply = n => `review-original.${n}.md`;
const sha256 = data => crypto.createHash('sha256').update(data).digest('hex');

function places(ctx) {
  const dir = path.join(ctx.featureRoot, ...TASK.slice(0, -1));
  return { dir, prepared: path.join(dir, 'prepared.json'), dispatch: path.join(dir, 'dispatch.md'),
    context: path.join(dir, 'context.md') };
}


const abs = (ctx, rel) => path.join(ctx.projectRoot, ...String(rel).split('/'));

const filled = v => typeof v === 'string' && v.length > 0;
//: 准备记录里 prepare 与 check 实际要用的字段
const PREPARED_FIELDS = [['material_key', filled], ['project_root', filled], ['report_dir', filled], ['report_file', filled],
  ['report_dirs', v => Boolean(v) && typeof v === 'object' && !Array.isArray(v)]];

/**
 * 准备记录，prepare 与 check 共用：不存在是首次（`record` 为 null）；在却读不出、不是 JSON 对象或缺必需字段是输入故障，
 * 给出诊断，不当首次——它记着各份材料的报告目录与派审带出过的原件。
 *
 * @returns {{record: object|null}|{error: string}}
 */
export function preparedRecord(ctx) {
  const file = places(ctx).prepared;
  if (!fs.existsSync(file)) return { record: null };
  const text = readText(file);
  let record = null;
  try { record = text === null ? null : JSON.parse(text); } catch { record = null; }
  const isObject = Boolean(record) && typeof record === 'object' && !Array.isArray(record);
  const missing = isObject ? PREPARED_FIELDS.filter(([k, ok]) => !ok(record[k])).map(([k]) => k) : [];
  if (isObject && !missing.length) return { record };
  const rel = path.relative(ctx.projectRoot, file).split(path.sep).join('/');
  const why = text === null ? '读不出' : !isObject ? '不是合法的 JSON 对象' : `缺 ${missing.join('、')}`;
  return { error: `准备记录 ${rel} ${why}：它记着各份材料的报告目录与派审带出过的原件，不能当作首次准备。`
    + '现场保留未动；恢复它的合法原记录后重跑 prepare，没有可靠的原记录交维护者处理' };
}

/**
 * 准备这一次的审查。审查对象要先成最终版：调用方已重投附录、编号、渲染 Review（含审查状态披露）并过了结构检查。
 *
 * @returns {{error?: string, material_key?: string, task?: string, rows?: object[], report_dir?: string,
 *   report_file?: string, reused?: boolean}}
 */
export function prepareReview(ctx, reportDirArg) {
  const { dir, prepared, dispatch, context: contextFile } = places(ctx);
  const before = preparedRecord(ctx);
  if (before.error) return { error: before.error };
  const was = before.record;
  fs.mkdirSync(dir, { recursive: true });
  const task = path.join(ctx.featureRoot, ...TASK);
  // 任务是审查对象的一部分，所以不嵌入由对象算出的材料键：材料键经派审载体交给审查者。
  // 对象只组装一次：先用不含任务的那份生成任务，任务写好后补上任务那一行得到最终身份
  const base = reviewObject(ctx.projectRoot, ctx.args.feature, { withTask: false, source: designSource(ctx) });
  const taskText = `${readerReviewTask(ctx.projectRoot, ctx.args.feature, base)}\n`;
  if (readText(task) !== taskText) fs.writeFileSync(task, taskText, 'utf-8');
  const object = withTaskRow(ctx.projectRoot, ctx.args.feature, base);
  if (object.problems.length) return { error: `审查对象不全：${object.problems.join('；')}` };
  const key = materialKey(ctx.projectRoot, object.rows);
  // 报告目录随材料键定一次：同一份材料的历次回复都在这个目录里，结论按它们取
  const bound = was?.report_dirs?.[key];
  const asked = reportDirArg && String(reportDirArg).replace(/\\/g, '/').replace(/^\.\//, '').replace(/\/+$/, '');
  if (bound && asked && asked !== bound) {
    return { error: `报告目录冲突：这一份材料（材料键 ${key.slice(0, 16)}…）的报告目录在首次准备时定为 ${bound}，`
      + `这次指定的是 ${asked}。同一份材料的回复都在 ${bound}，准备记录与已有回复未改动；去掉 --report-dir 或写 ${bound} 重跑` };
  }
  const reportDir = bound ?? asked ?? `doc/reports/story/${ctx.args.feature}/${key.slice(0, 16)}`;
  const choice = replyPlace(ctx, was, key, reportDir, object);
  // 未审披露在准备开始时按宿主能力判定一次（`pendingDisclosure`），已写进文件、材料键里含它；随准备记下原因
  const shown = disclosure(ctx);
  const unresolved = unresolvedFail(ctx, was, key, object, choice);
  if (unresolved) choice.originals[unresolved.report_file] ??= unresolved.report_sha256;
  const record = { material_key: key, project_root: ctx.projectRoot.split(path.sep).join('/'), report_dir: reportDir,
    report_file: choice.reportFile,
    report_dirs: { ...was?.report_dirs, [key]: reportDir }, ...(shown ? { disclosure: shown.reason } : {}),
    ...(unresolved ? { unresolved_fail: unresolved } : {}),
    ...(choice.reused ? { reused: true } : {}), ...(choice.context ? { review_context: choice.context } : {}),
    ...(Object.keys(choice.originals).length ? { originals: choice.originals } : {}) };
  const rel = path.relative(ctx.projectRoot, task).split(path.sep).join('/');
  const dispatchText = dispatchFor(ctx, record, rel);
  const contextText = contextFor(record);
  // 派审载体与前轮上下文先落盘，准备记录最后替换：对不上时 check 报 input_invalid，重跑 prepare 即可
  if (contextText) replaceFile(contextFile, contextText);
  else fs.rmSync(contextFile, { force: true });
  replaceFile(dispatch, dispatchText);
  replaceFile(prepared, `${JSON.stringify(record, null, 2)}\n`);
  return { material_key: key, task: rel, rows: object.rows, report_dir: reportDir, report_file: choice.reportFile,
    reused: choice.reused, disclosure: record.disclosure ?? null, unresolved_fail: record.unresolved_fail ?? null, dispatch_file: path.relative(ctx.projectRoot, dispatch).split(path.sep).join('/'),
    dispatch_text: dispatchText };
}

/**
 * 这一次回复写在哪、派审要带什么上下文。按下面的顺序取，命中即停：
 *
 * 1. 这份材料的报告目录里有可复用的 pass / warn：复用原回复，不派审；
 * 2. 同一份材料已准备、回复还没来：沿用这个位置与它的上下文；上下文带的原回复字节变了，改为对当前材料的完整独立审查；
 * 3. 这份材料的当前回复（换回这份材料时是它目录里最新的原样回复）不合报告合同：下一个编号，带原回复与诊断交独立格式返修；
 *    已有有效 fail：下一个编号，带失败报告交独立复审；
 * 4. 材料换了新键，紧前一次准备的原报告还在且是原样：下一个编号，带它作待核参考（`prior_revision`），不继承它的结论；
 * 5. 其余（首审、前一份报告缺席或改过）：下一个编号，不带上下文，完整审查。
 *
 * 「前一次」只指紧前那次准备，不往更早的回复里找替代。
 * 派审带出去过的原回复记下原样字节（`originals`）；字节对不上的回复不再读出结论，恢复原样之后照常读。
 */
function replyPlace(ctx, was, key, reportDir, object) {
  const originals = originalsOf(was);
  const altered = alteredReplies(ctx, originals);
  const current = was?.material_key === key ? was.report_file : null;
  const known = materialConclusion(ctx, key, reportDir, current, object, altered);
  if (['pass', 'warn'].includes(known?.result)) return { reportFile: known.report_file, reused: true, context: null, originals: received(ctx, originals, known) };
  if (current && !was.reused && !fs.existsSync(abs(ctx, current))) {
    const c = was.review_context;
    const context = c?.report_file && altered.has(c.report_file)
      ? { kind: 'fresh_review', damaged: { report_file: c.report_file, report_sha256: c.report_sha256 } } : c ?? null;
    return { reportFile: current, reused: false, context, originals };
  }
  const next = `${reportDir}/${reply(Math.max(0, ...replyNumbers(ctx, reportDir)) + 1)}`;
  let context = null;
  if (['report_invalid', 'subject_stale'].includes(known?.result)) {
    // 当前回复不合合同时，check 读目录里其余回复中最新的有效结论；那里有通过结论就直接复用
    const earlier = earlierConclusion(ctx, key, reportDir, current, object, altered);
    if (['pass', 'warn'].includes(earlier?.result)) return { reportFile: earlier.report_file, reused: true, context: null, originals: received(ctx, originals, earlier) };
    context = contextOf(ctx, 'format_repair', known);
  } else if (known?.result === 'fail') {
    context = contextOf(ctx, 'recheck', known);
  } else if (was && was.material_key !== key) {
    // 紧前一次准备的原报告：它的回复位置有回复就是那份；接收后已换到返修或复审的新位置、新位置还空着时，是同一份材料带出去的那份
    //（上一版材料的参考不往下传）
    const own = ['format_repair', 'recheck'].includes(was.review_context?.kind) ? was.review_context.report_file : null;
    const prior = fs.existsSync(abs(ctx, was.report_file)) ? was.report_file : own;
    if (prior && fs.existsSync(abs(ctx, prior)) && !altered.has(prior)) {
      context = { kind: 'prior_revision', material_key: was.material_key, report_file: prior,
        report_sha256: sha256(fs.readFileSync(abs(ctx, prior))) };
    }
  }
  if (context) originals[context.report_file] = context.report_sha256;
  return { reportFile: next, reused: false, context, originals };
}

/** 接收一份回复：记下它此刻原样字节的摘要；已记过的不改（字节变了的已在 `altered` 里排除）。 */
function received(ctx, originals, known) {
  return originals[known.report_file] ? originals
    : { ...originals, [known.report_file]: sha256(fs.readFileSync(abs(ctx, known.report_file))) };
}

/** 派审带出去过与接收过的原回复：路径 → 原样字节的 SHA-256。 */
function originalsOf(was) {
  const out = { ...(was?.originals ?? {}) };
  const c = was?.review_context;
  if (c?.report_file && c.report_sha256) out[c.report_file] = c.report_sha256;
  return out;
}

/** 记过原样字节、现在对不上（或不在）的回复：它们已不是审查者的原话。 */
function alteredReplies(ctx, originals) {
  return new Set(Object.entries(originals).filter(([rel, digest]) => {
    try { return sha256(fs.readFileSync(abs(ctx, rel))) !== digest; } catch { return true; }
  }).map(([rel]) => rel));
}

function contextOf(ctx, kind, known) {
  return { kind, report_file: known.report_file, report_sha256: sha256(fs.readFileSync(abs(ctx, known.report_file))),
    diagnostic: { result: known.result, detail: known.detail } };
}

/**
 * 派审载体：由准备记录确定性生成，主执行者原样作为宿主 task 的 prompt 交给隔离审查者。
 * 只给 Story 路径、通用首读问题、材料键与之后要读的任务（有前轮报告时另加前轮上下文）路径：判据、来源、人签、
 * 前轮报告与诊断都在后读的文件里，首读完成后才读。审查者只读、只回最终报告；主执行者把最终回复原样写到回复位置。
 */
function dispatchFor(ctx, record, task) {
  const story = path.relative(ctx.projectRoot, ctx.storyPath).split(path.sep).join('/');
  const head = ['# Story 独立人读审查 · 派审', '',
    `- 工程根：\`${record.project_root}\``,
    `- 材料键：\`${record.material_key}\``];
  if (record.reused) {
    return `${[...head, `- 审查任务：\`${task}\``, `- 已有通过的回复：\`${record.report_file}\``, '',
      '这份材料已有可复用的审查结论，这一次不派审，直接跑 `story-build review --action check`。'].join('\n')}\n`;
  }
  if (record.disclosure) {
    return `${[...head, '', `本版不派审：${record.disclosure}。`, '', ...(record.unresolved_fail
      ? [`之前的独立审查判过阻断（\`${record.unresolved_fail.report_file}\`），这一版改过之后还没人复核：`
        + '`story-build review --action check` 的结果是 fail（已知必修未复核），不能登记交付；'
        + '在能派独立审查的宿主上重新 `story-build review --action prepare`，按那时生成的载体复核。']
      : ['未审披露已写进 Story 交付章与 Review 题头。直接跑 `story-build review --action check`（结果是 unreviewed），'
        + '再按已有授权登记与交付；交付说明照实写本版未审。'])].join('\n')}\n`;
  }
  const later = contextFor(record)
    ? `审查任务 \`${task}\`，以及前轮上下文 \`${relOf(ctx, places(ctx).context)}\`` : `审查任务 \`${task}\``;
  const out = [...head, `- 被审的 Story：\`${story}\``, `- 首读之后读的：${later}`, '',
    '你是与作者隔离的独立审查者，只读，不写任何文件；你的最终回复就是审查报告，主执行者把它原样写到'
      + ` \`${record.report_file}\`（工程相对路径）。`, '',
    '## 先首读', '',
    `先只读 \`${story}\` 一遍，像第一次拿到它的评审者：读完能不能说出这个需求要做什么、为什么、用户怎么走、`
      + '正常与异常各到哪、怎样判定完成；哪里读不懂、要回头找、前后说法不一。记下首读结论之前不读别的文件；'
      + '之后再读上面列的后读文件，按审查任务核源与逐项判据。',
    `回复第一行写 \`material_key: ${record.material_key}\`，其余格式见任务「报告怎么写」。`];
  return `${out.join('\n')}\n`;
}

const relOf = (ctx, file) => path.relative(ctx.projectRoot, file).split(path.sep).join('/');

/**
 * 前轮上下文：首读之后读，由准备记录确定性生成；没有前轮报告（首审、前一份缺席或改过之外的情形）返回 null。
 * 它不是被审材料，不进材料键：材料键定下之后才选得出用哪一份前轮报告。
 */
function contextFor(record) {
  if (record.reused || record.disclosure) return null;
  const c = record.review_context;
  const open = record.unresolved_fail?.report_file && record.unresolved_fail.report_file !== c?.report_file
    ? record.unresolved_fail : null;
  if (!c && !open) return null;
  const out = ['# Story 独立人读审查 · 前轮上下文（首读之后读）', '', `- 材料键：\`${record.material_key}\``, ''];
  if (open) {
    out.push('## 尚未复核的已知阻断（待核参考）', '',
      `之前的独立审查判过阻断：\`${open.report_file}\`（SHA-256 ${open.report_sha256}），只读。之后材料改过，还没人复核。`
      + '对它的每条阻断发现，在报告「发现」里说明现在是已修、仍在，还是因范围变化不再适用，并写依据；它的结论不适用于这一次，'
      + '回复只对应上面的材料键。', '');
  }
  if (!c) return `${out.join('\n')}\n`;
  if (c.kind === 'format_repair') {
    out.push('## 上一份回复不合报告合同', '',
      `原回复：\`${c.report_file}\`（SHA-256 ${c.report_sha256}），只读，保持原样。核对给出的诊断原文：`, '',
      ...String(c.diagnostic.detail).split(/\r?\n/).map(l => `> ${l}`), '',
      '按任务给一份合格的完整报告作为这次的最终回复，主执行者把它原样存到派审载体给的回复位置。诊断只关报告的表达、表头或字段格式时，原回复的实质判断与判据覆盖充分就照用，'
      + '不必把每条事实重核一遍；诊断是缺判据、引用找不到、依据不足或结论自相矛盾时，回材料把这部分核验补足；'
      + '看不出原审查是否完整时按完整范围审查。核不到的不写。');
  } else if (c.kind === 'recheck') {
    out.push('## 这份材料上一次的审查结论是 fail', '',
      `上一次的回复：\`${c.report_file}\`（SHA-256 ${c.report_sha256}），只读。它的阻断结论：`, '',
      ...String(c.diagnostic.detail).split(/\r?\n/).map(l => `> ${l}`), '',
      '对当前材料做一次完整审查：每条阻断现在是否成立由你按材料独立判断，其余判据照常逐项核。');
  } else if (c.kind === 'prior_revision') {
    out.push('## 上一版材料的审查报告（只作参考）', '',
      `上一版材料（材料键 \`${c.material_key}\`）的原报告：\`${c.report_file}\`（SHA-256 ${c.report_sha256}），只读。`
      + '它的发现是待核的线索与背景，结论不适用于这一次：对当前材料做一次完整审查，每条旧发现现在是否成立、'
      + '是否已改好由你按材料判断，其余判据照常逐项核；回复只对应上面的材料键。');
  } else if (c.kind === 'fresh_review') {
    out.push('## 上一份回复的原件已被改动', '',
      `\`${c.damaged.report_file}\` 派审时记下的 SHA-256 是 ${c.damaged.report_sha256}，现在的字节与它不同：`
      + '它留在原处作现场，不作审查依据。对当前材料做一次完整的独立审查，判据逐项核。');
  } else if (!open) {
    return null;
  }
  return `${out.join('\n')}\n`;
}

/** 派审载体与准备记录、返修上下文里的原回复还对不对得上：对不上返回原因。 */
function dispatchProblem(ctx, was) {
  const { dispatch } = places(ctx);
  const task = path.relative(ctx.projectRoot, path.join(ctx.featureRoot, ...TASK)).split(path.sep).join('/');
  if (readText(dispatch) !== dispatchFor(ctx, was, task) || readText(places(ctx).context) !== contextFor(was)) {
    return '派审载体 AR/story-src/review/dispatch.md 或前轮上下文 context.md 不在，或与准备记录对不上';
  }
  const carried = was.disclosure ? [] : [was.review_context, was.unresolved_fail].filter(c => c?.report_file);
  for (const c of carried) {
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
 * 准备开始时判一次：当前宿主有没有声明 Story 独立审查能力。没有就如实披露未审，原因写明是哪个 adapter；
 * 结论存进 `ctx.disclosure`，Review 题头与 Story 交付章按同一个结论写披露。
 */
export function pendingDisclosure(ctx) {
  const host = hostReviewer(ctx.projectRoot);
  ctx.disclosure = host.declared ? null
    : { reason: `当前宿主（adapter ${host.adapter ?? '未配置'}）没有声明 Story 独立审查能力` };
  return ctx.disclosure;
}

/** 要写进交付件的未审披露：准备过程中用开头判定的结论，其余时候认准备记录里记下的那一条。 */
function disclosure(ctx) {
  if (ctx.disclosure !== undefined) return ctx.disclosure;
  const reason = readJson(places(ctx).prepared, null)?.disclosure;
  return reason ? { reason } : null;
}

/** 审查状态的机器区：Story 交付章与 Review 题头共用这一份，区名取章节合同；没有未审披露返回空。 */
export function reviewStatusBlock(ctx) {
  const name = (ctx.contract.chapters ?? []).find(c => c.review_status)?.review_status;
  const rows = reviewStatusLines(disclosure(ctx));
  return name && rows.length ? zoneBlock(name, '未审披露（宿主没有独立审查能力时自动写）', rows) : [];
}

function reviewStatusLines(shown) {
  return shown ? [`本版未经独立审查。原因：${shown.reason}。这是审查事实，不是业务完成、设计准入或发布质量结论；`
    + '宿主能派独立审查之后，重新准备审查走正常审查。'] : [];
}

/**
 * 已知必修：这份材料的有效阻断（回复位置换成了复审），或紧前那一版材料的阻断在这次改动之后还没人复核；
 * 前面已记的照样往下带，直到某一版有了 pass / warn。宿主没有审查员时它挡住未审放行。
 */
function unresolvedFail(ctx, was, key, object, choice) {
  if (choice.reused) return null;
  const c = choice.context;
  if (c?.kind === 'recheck') return { report_file: c.report_file, report_sha256: c.report_sha256 };
  if (was && was.material_key !== key) {
    const prior = materialConclusion(ctx, was.material_key, was.report_dir, was.report_file, object,
      alteredReplies(ctx, originalsOf(was)));
    if (prior?.result === 'fail') {
      return { report_file: prior.report_file, report_sha256: sha256(fs.readFileSync(abs(ctx, prior.report_file))) };
    }
    if (['pass', 'warn'].includes(prior?.result)) return null;
  }
  return was?.unresolved_fail ?? null;
}

/** 这一次审查的结果，只读。显式 check、登记、交付门与状态共用。 */
export function reviewResult(ctx) {
  const read = preparedRecord(ctx);
  if (read.error) return { result: 'input_invalid', detail: read.error };
  const was = read.record;
  if (!was) {
    return { result: 'report_missing', detail: '还没准备这一次的审查——先跑 `story-build review --action prepare`' };
  }
  const base = reviewObject(ctx.projectRoot, ctx.args.feature, { withTask: false, source: designSource(ctx) });
  const object = withTaskRow(ctx.projectRoot, ctx.args.feature, base);
  if (object.problems.length) return { result: 'input_invalid', detail: `审查对象不全：${object.problems.join('；')}` };
  if (materialKey(ctx.projectRoot, object.rows) !== was.material_key) {
    return { result: 'subject_stale', detail: '准备审查之后审查对象变了：重跑 prepare，按新任务与材料键再派审' };
  }
  // 任务依据的来源、视觉裁定与回看清单仍是现在这份：按同一份生成重算，变了就是旧任务
  if (readText(path.join(ctx.featureRoot, ...TASK)) !== `${readerReviewTask(ctx.projectRoot, ctx.args.feature, base)}\n`) {
    return { result: 'subject_stale', detail: '审查任务依据的输入变了（来源、视觉裁定或回看清单）：重跑 prepare，按新任务与材料键再派审' };
  }
  const broken = dispatchProblem(ctx, was);
  if (broken) return { result: 'input_invalid', detail: `${broken}——重跑 \`story-build review --action prepare\`，按新生成的派审载体派审` };
  const at = { report_file: was.report_file };
  // 这一份还没回复时，同一份材料之前已有的有效结论仍在：重新准备不撤销已知的阻断；原样字节对不上的回复不读
  const originals = originalsOf(was);
  const altered = alteredReplies(ctx, originals);
  const known = materialConclusion(ctx, was.material_key, was.report_dir, was.report_file, object, altered);
  if (known && ['pass', 'warn', 'fail'].includes(known.result) && !originals[known.report_file]) {
    return { result: 'report_unreceived', report_file: known.report_file,
      detail: `${known.report_file} 里的回复还没接收：重跑 \`story-build review --action prepare\` 接收（记下原样字节的摘要），再 check` };
  }
  if (known) return known;
  if (altered.has(was.report_file) && fs.existsSync(abs(ctx, was.report_file))) {
    return { result: 'report_invalid', report_file: was.report_file,
      detail: `${was.report_file} 接收之后被改过，已不是审查者的原话，不读它的结论——重跑 prepare 另起编号重新派审` };
  }
  // 接收时发现上一份回复不合合同，已换到下一个回复位置：结果仍是那份的诊断，新载体已带上它
  const c = was.review_context;
  if (c?.kind === 'format_repair') {
    return { result: c.diagnostic.result, report_file: c.report_file,
      detail: `${c.diagnostic.detail}（新的派审载体已带原回复与诊断，回复位置 ${was.report_file}：按它派审）` };
  }
  // 没有可消费的回复时，宿主能力与准备时写进交付件的披露要一致：不一致就是准备之后宿主变了，重新准备
  const host = hostReviewer(ctx.projectRoot);
  if (Boolean(was.disclosure) === host.declared) {
    return { result: 'subject_stale', detail: host.declared
      ? '准备时宿主没有独立审查能力、写了未审披露，现在宿主能派审了：重跑 prepare 撤掉披露，按新载体派审'
      : '准备时宿主能派审，现在没有声明独立审查能力：重跑 prepare，把未审披露写进 Story 与 Review', ...at };
  }
  if (!host.declared && was.unresolved_fail) {
    return { result: 'fail', detail: `已知必修未复核：之前的独立审查判了阻断（${was.unresolved_fail.report_file}），`
      + '这一版改过之后没有可用的独立审查员复核——未审不能放过它；在能派独立审查的宿主上重新准备并复核', ...at };
  }
  if (!host.declared) return { result: 'unreviewed', detail: `本版未经独立审查：${was.disclosure}`, ...at };
  return { result: 'report_missing', detail: `审查者的回复不在 ${was.report_file}——把独立审查者的回复原样写到那里`, ...at };
}

/**
 * 这一份材料在它的报告目录里的结论，prepare 与 check 共用：当前回复位置有回复就判它；换回这份材料、没有当前位置时，
 * 它目录里最新的原样回复就是当前回复（不合合同也照判，诊断留给格式返修）；当前位置还没回复时从其余回复取最新的有效结论；
 * 都没有返回 null。
 */
function materialConclusion(ctx, key, reportDir, reportFile, object, altered = new Set()) {
  const at = reportFile ?? replyNumbers(ctx, reportDir).sort((a, b) => b - a).map(n => `${reportDir}/${reply(n)}`)
    .find(f => !altered.has(f));
  if (at && fs.existsSync(abs(ctx, at)) && !altered.has(at)) {
    return { ...judge(fs.readFileSync(abs(ctx, at), 'utf-8'), key, object.rows, coverageBasis(ctx, object)), report_file: at };
  }
  return earlierConclusion(ctx, key, reportDir, at, object, altered);
}

/** 报告目录里已有回复的编号。 */
function replyNumbers(ctx, reportDir) {
  const dir = abs(ctx, reportDir);
  return fs.existsSync(dir) ? fs.readdirSync(dir).map(f => Number(/^review-original\.(\d+)\.md$/.exec(f)?.[1])).filter(Boolean) : [];
}

/** 报告目录里除 `skip` 之外的回复，从新到旧取第一份有效结论（pass / warn / fail）；没有返回 null。 */
function earlierConclusion(ctx, key, reportDir, skip, object, altered = new Set()) {
  const files = replyNumbers(ctx, reportDir).sort((a, b) => b - a).map(n => `${reportDir}/${reply(n)}`);
  for (const rel of files.filter(f => f !== skip && !altered.has(f))) {
    const out = judge(fs.readFileSync(abs(ctx, rel), 'utf-8'), key, object.rows, coverageBasis(ctx, object));
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

const visuals = new WeakMap();

/**
 * 覆盖声明对着核的必审集合：审查对象的每一份按规范路径归一（同字节的别名算一份，成员里有一份要读就要读；缺件已在对象里拦下；
 * 任务本身计入材料键、不在表里），只核在场与来源摘要的行不要求声明；加独立 Story 视觉裁定——
 * 只有原生裁定允许延期时，对象里的图片可以按能力缺口写进 unreviewed 而结论最高 warn。
 */
function coverageBasis(ctx, object) {
  const task = path.relative(ctx.projectRoot, path.join(ctx.featureRoot, ...TASK)).split(path.sep).join('/');
  const canon = p => object.alias.get(p) ?? p;
  const inputs = new Map();
  for (const m of object.rows.filter(r => r.path !== task)) {
    const k = canon(m.path);
    const seen = inputs.get(k);
    if (seen) { seen.required ||= m.required_read !== false; continue; }
    inputs.set(k, { path: k, purpose: m.role === 'object' ? `审查对象：${m.label}` : m.label, required: m.required_read !== false,
      missing: false, image: m.kind === 'image' });
  }
  const images = [...inputs.values()].filter(x => x.image).map(x => x.path);
  if (images.length && !visuals.has(ctx)) visuals.set(ctx, storyReviewVisual(ctx.projectRoot, ctx.args.feature, designSource(ctx).read));
  const v = images.length ? visuals.get(ctx) : null;
  return {
    inputs: [...inputs.values()], gaps: [], alias: object.alias,
    visual: v?.status === 'ok' && v.deferral ? { fact: v.fact, deferred: new Set(images) } : null,
  };
}

/** 「判据核对」节里的覆盖声明块：带顶层键的 YAML 围栏块逐个取出；读不出的围栏块记进 `broken`，不当成没写。 */
function coverageOf(body) {
  const lines = String(body ?? '').split(/\r?\n/);
  const docs = [];
  const broken = [];
  for (const f of fenceRanges(lines)) {
    const y = lines.slice(f.from + 1, f.closed ? f.to : f.to + 1).join('\n');
    let d;
    try { d = parseYaml(y); } catch (e) { broken.push(`第 ${f.from + 1} 行起的围栏块按 YAML 读不出（${String(e?.message ?? e).split(/\r?\n/)[0]}）`); continue; }
    if (d && typeof d === 'object' && COVERAGE_KEY in d) docs.push(d[COVERAGE_KEY]);
  }
  return { docs, broken };
}

/**
 * 一份回复对这一份材料：材料键、三节、判据逐项、发现的材料引用、结论与发现一致、覆盖声明对得上必审集合。
 * 发现的材料位置要落在这一次的审查对象里，或是报告 examined_inputs 声明过的额外取证（额外取证顶替不了必审）。
 */
function judge(text, key, materials, basis = null) {
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
  const declared = coverageOf(parts.get('判据核对')[0]).docs[0]?.examined_inputs;
  const paths = new Set([...materials.map(m => m.path),
    ...(Array.isArray(declared) ? declared : []).map(x => inputPath(typeof x === 'string' ? x : x?.path)).filter(Boolean)]);
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
  const { docs: covers, broken } = coverageOf(parts.get('判据核对')[0]);
  if (broken.length || covers.length !== 1 || !covers[0] || typeof covers[0] !== 'object' || Array.isArray(covers[0])) {
    return invalid([...broken, `「判据核对」节末尾要恰好一个 YAML 块，顶层键 ${COVERAGE_KEY}，下面是 ${COVERAGE_KEYS.join('、')} 四个列表（现在 ${covers.length} 个）`]);
  }
  const cover = covers[0];
  const ids2 = list => (Array.isArray(list) ? list.map(x => String(x).trim()) : null);
  const want = { blocking_findings: severe.map(r => r[0]), advisories: found.data.filter(r => !['BLOCKER', 'MAJOR'].includes(r[1])).map(r => r[0]) };
  for (const [k, expected] of Object.entries(want)) {
    const got = ids2(cover[k]);
    if (got && JSON.stringify([...got].sort()) !== JSON.stringify([...expected].sort())) {
      why.push(`${COVERAGE_KEY}.${k} 要恰好列「发现」表里${k === 'blocking_findings' ? ' BLOCKER / MAJOR' : ' MINOR / INFO'} 的编号（应为 ${expected.join('、') || '空列表'}，写了 ${got.join('、') || '空列表'}）`);
    }
  }
  why.push(...detailProblems(cover, derived.toUpperCase(), basis, ids).map(p => `${COVERAGE_KEY} ${p}`));
  if (why.length) return invalid(why);
  const listed = rows => rows.map(r => `${r[0]} ${r[1]} ${r[4]}`);
  if (derived === 'fail') return { result: 'fail', detail: `审查结论阻断：${listed(severe).join('；') || '判据核对有 fail'}` };
  const advisories = listed(found.data);
  return { result: derived, detail: derived === 'warn' ? `非阻断建议 ${advisories.length} 条` : '审查通过', advisories };
}

/**
 * Story 交付章里的审查状态：宿主没有独立审查能力时写未审披露，否则撤掉；在哪一章、区名取章节合同。
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
