/**
 * Story 的独立审查 —— 准备这一次的审查对象与任务，接收并核独立读者原样落盘的最终回复。
 *
 * - **准备**：写审查任务，按审查对象算材料键，定这一次回复的位置，生成派审载体 `dispatch.md`（Story 路径、材料键、
 *   后读任务、最近一份原报告与回复位置）。没有原报告时请读者先读成品；有原报告时载体写明这是复核或补正。
 *   审查者的回复原样落盘后重跑准备：开头两行合格、材料键是派审时那一份，就记成最近一次可消费的回复
 *   （`last_received`：材料键、回复位置与原样字节摘要）；不合格的回复留在原处，不覆盖它，下一份回复另起位置。
 *   最近可消费的回复就是当前材料键且结论是 pass / warn 时直接复用，不再派审。
 * - **核结果**：显式 check、登记、交付门与状态共用这一份判定，只读：审的是不是现在这份、回复是不是原样、读者写的结论。
 *
 * | 结果 | 含义 |
 * |---|---|
 * | pass / warn | 可以登记交付；warn 的建议在原样报告里 |
 * | fail | 读者结论 fail；或最近一份可消费回复判了 fail，之后还没有新的可消费回复（已知必修未复核） |
 * | unreviewed | 本次准备时没有可用的独立读者：如实记为未审，准备时把审查状态写进 Story 与 Review；不是业务完成、设计准入或发布质量结论 |
 * | report_missing | 还没准备，或回复不在 |
 * | report_unreceived | 回复在，开头两行合格，还没经准备接收 |
 * | report_invalid | 回复开头两行不合格，或接收之后原件被改、不在了 |
 * | subject_stale | 当前材料与准备时不同，或回复写的材料键不是这一份 |
 * | input_invalid | 审查对象不全，或准备记录、派审载体对不上 |
 *
 * 脚本只核开头两行与原样；审查做没做够、发现与结论是否相称由独立读者负责，脚本不从正文推结论，也不判复核范围。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { readerReviewTask } from '../../../../../hooks/shared/reader-review-task.mjs';
import { readJson, readText, replaceFile } from './context.mjs';
import { chapterSpan, zoneBlock, zoneSpan } from './document.mjs';
import { TASK, materialKey, reviewObject, withTaskRow } from './review-object.mjs';
import { designSource } from './design-source.mjs';
import { CONCLUSIONS } from './review-report-contract.mjs';

const reply = n => `review-original.${n}.md`;
const sha256 = data => crypto.createHash('sha256').update(data).digest('hex');

function places(ctx) {
  const dir = path.join(ctx.featureRoot, ...TASK.slice(0, -1));
  return { dir, prepared: path.join(dir, 'prepared.json'), dispatch: path.join(dir, 'dispatch.md') };
}

const abs = (ctx, rel) => path.join(ctx.projectRoot, ...String(rel).split('/'));
const relOf = (ctx, file) => path.relative(ctx.projectRoot, file).split(path.sep).join('/');
const bytesOf = (ctx, rel) => { try { return fs.readFileSync(abs(ctx, rel)); } catch { return null; } };

const filled = v => typeof v === 'string' && v.length > 0;
//: 准备记录里 prepare 与 check 实际要用的字段
const PREPARED_FIELDS = [['material_key', filled], ['project_root', filled], ['report_dir', filled], ['report_file', filled]];
//: 旧版审查格式才有的字段：当前版本不读这种记录
const RETIRED_FIELDS = ['review_contexts', 'review_context', 'report_dirs', 'unresolved_fail', 'originals'];

/**
 * 准备记录，prepare 与 check 共用：不存在是首次（`record` 为 null）；在却读不出、不是 JSON 对象、缺必需字段或是旧版格式是输入故障，
 * 给出诊断，不当首次——它记着最近一次可消费的回复。
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
  const retired = isObject ? RETIRED_FIELDS.filter(k => k in record) : [];
  if (isObject && !missing.length && !retired.length) return { record };
  const why = text === null ? '读不出' : !isObject ? '不是合法的 JSON 对象'
    : retired.length ? `是旧版审查格式（含 ${retired.join('、')}），当前版本不读它` : `缺 ${missing.join('、')}`;
  return { error: `准备记录 ${relOf(ctx, file)} ${why}：它记着最近一次可消费的独立回复，不能当作首次准备。`
    + '现场保留未动；恢复它的合法原记录后重跑 prepare，没有可靠的原记录交维护者处理' };
}

/** 回复开头两行：`material_key: <64 位>`、`conclusion: pass|warn|fail`。不合格返回 `problem`。 */
function headOf(text) {
  const [first = '', second = ''] = String(text).replace(/^\uFEFF/, '').split(/\r?\n/);
  const key = /^material_key: *([0-9a-f]{64}) *$/.exec(first)?.[1];
  const conclusion = new RegExp(`^conclusion: *(${CONCLUSIONS.join('|')}) *$`).exec(second)?.[1];
  if (key && conclusion) return { key, conclusion };
  return { problem: `回复开头两行要是 \`material_key: <64 位材料键>\` 与 \`conclusion: ${CONCLUSIONS.join('|')}\``
    + `（现在是「${first.slice(0, 80)}」「${second.slice(0, 80)}」）` };
}

/** 最近一次可消费回复的原件还是接收时那份字节：不是时给出原因。 */
function lastProblem(ctx, last) {
  const bytes = last ? bytesOf(ctx, last.report_file) : null;
  if (!last || (bytes && sha256(bytes) === last.report_sha256)) return null;
  return `最近接收的原回复 ${last.report_file} ${bytes ? '接收之后被改过' : '不在了'}：它是独立读者的原件，恢复宿主保存的原样；`
    + '恢复不了就保留现场，重新 prepare 交独立读者给一份新回复';
}

/** 最近一次可消费回复的结论；原件不是接收时那份时为 null。 */
function lastConclusion(ctx, last) {
  if (!last || lastProblem(ctx, last)) return null;
  return headOf(bytesOf(ctx, last.report_file).toString('utf-8')).conclusion;
}

/**
 * 接收上一次准备给出的回复：开头两行合格、材料键是派审时那一份，就成为最近一次可消费的回复；不合格的留在原处、
 * 不更新最近回复，原因随下一次派审交回读者。
 */
function receive(ctx, was) {
  const last = was?.last_received ?? null;
  if (!was || was.reused || last?.report_file === was.report_file) return { last, invalid: null };
  const bytes = bytesOf(ctx, was.report_file);
  if (bytes === null) return { last, invalid: null };
  const head = headOf(bytes.toString('utf-8'));
  const problem = head.problem
    ?? (head.key !== was.material_key ? `回复写的材料键 ${head.key.slice(0, 16)}… 不是派审时的 ${was.material_key.slice(0, 16)}…` : null);
  if (problem) return { last, invalid: { material_key: was.material_key, report_file: was.report_file, problem } };
  return { last: { material_key: was.material_key, report_file: was.report_file, report_sha256: sha256(bytes) }, invalid: null };
}

/** 审查对象与它的材料键：任务先按对象生成并落盘（任务也是对象的一部分），再补上任务那一行算键。 */
function stageObject(ctx) {
  const base = reviewObject(ctx.projectRoot, ctx.args.feature, { withTask: false, source: designSource(ctx) });
  const task = path.join(ctx.featureRoot, ...TASK);
  const taskText = `${readerReviewTask(ctx.projectRoot, ctx.args.feature, base)}\n`;
  if (readText(task) !== taskText) fs.writeFileSync(task, taskText, 'utf-8');
  const object = withTaskRow(ctx.projectRoot, ctx.args.feature, base);
  return { object, key: object.problems.length ? null : materialKey(ctx.projectRoot, object.rows) };
}

/** 报告目录里已有回复的编号。 */
function replyNumbers(ctx, reportDir) {
  const dir = abs(ctx, reportDir);
  return fs.existsSync(dir) ? fs.readdirSync(dir).map(f => Number(/^review-original\.(\d+)\.md$/.exec(f)?.[1])).filter(Boolean) : [];
}

/**
 * 准备这一次的审查。调用方已重投附录、编号、渲染 Review 并过了结构检查。
 * 最近可消费的 pass / warn 正是当前对象时直接复用，不改动审查状态；否则调 `restage` 按本次读者情况重写审查状态并重新定稿，
 * 再给回复位置：同一份材料的回复还没来就沿用原位置，其余另起下一个编号。
 *
 * @param {{reportDir?: string|null, restage: () => void}} opts
 */
export function prepareReview(ctx, { reportDir: asked = null, restage }) {
  const { dir, prepared, dispatch } = places(ctx);
  const before = preparedRecord(ctx);
  if (before.error) return { error: before.error };
  const was = before.record;
  fs.mkdirSync(dir, { recursive: true });
  const { last, invalid } = receive(ctx, was);
  let { object, key } = stageObject(ctx);
  const reusable = Boolean(key) && last?.material_key === key && ['pass', 'warn'].includes(lastConclusion(ctx, last));
  if (!reusable) {
    restage();
    ({ object, key } = stageObject(ctx));
  }
  if (object.problems.length) return { error: `审查对象不全：${object.problems.join('；')}` };
  const same = was?.material_key === key;
  const want = asked && String(asked).replace(/\\/g, '/').replace(/^\.\//, '').replace(/\/+$/, '');
  if (same && want && want !== was.report_dir) {
    return { error: `报告目录冲突：这一份材料（材料键 ${key.slice(0, 16)}…）的报告目录在首次准备时定为 ${was.report_dir}，`
      + `这次指定的是 ${want}。准备记录与已有回复未改动；去掉 --report-dir 或写 ${was.report_dir} 重跑` };
  }
  const reportDir = same ? was.report_dir : want || `doc/reports/story/${ctx.args.feature}/${key.slice(0, 16)}`;
  const waiting = same && !was.reused && !fs.existsSync(abs(ctx, was.report_file));
  const reportFile = reusable ? last.report_file
    : waiting ? was.report_file : `${reportDir}/${reply(Math.max(0, ...replyNumbers(ctx, reportDir)) + 1)}`;
  // 派审要带的原报告：同一份材料上一份回复不能接收时请读者补正它；否则是最近一次可消费的回复
  const prior = reusable ? null : waiting ? { report: was.prior_report ?? null, problem: was.prior_problem ?? null }
    : invalid?.material_key === key ? { report: invalid.report_file, problem: invalid.problem }
      : { report: last && !lastProblem(ctx, last) ? last.report_file : null, problem: null };
  const shown = disclosure(ctx);
  const record = { material_key: key, project_root: ctx.projectRoot.split(path.sep).join('/'), report_dir: reportDir,
    report_file: reportFile, ...(reusable ? { reused: true } : {}),
    ...(prior?.report ? { prior_report: prior.report } : {}), ...(prior?.problem ? { prior_problem: prior.problem } : {}),
    ...(shown ? { disclosure: shown.reason } : {}), ...(last ? { last_received: last } : {}) };
  const task = relOf(ctx, path.join(ctx.featureRoot, ...TASK));
  const dispatchText = dispatchFor(ctx, record, task);
  // 派审载体先落盘，准备记录最后替换：对不上时 check 报 input_invalid，重跑 prepare 即可
  replaceFile(dispatch, dispatchText);
  replaceFile(prepared, `${JSON.stringify(record, null, 2)}\n`);
  return { material_key: key, task, rows: object.rows, report_dir: reportDir, report_file: reportFile, reused: reusable,
    disclosure: record.disclosure ?? null, known_fail: lastConclusion(ctx, last) === 'fail' ? last.report_file : null,
    dispatch_file: relOf(ctx, dispatch), dispatch_text: dispatchText };
}

/**
 * 派审载体：由准备记录确定性生成，主执行者原样作为隔离读者的任务交出。首次只给 Story、材料键、后读任务与回复位置，
 * 请读者先读成品；有原报告时写明是复核（或补正上一份回复）并给原报告路径。审查者只读，最终回复由主执行者原样保存。
 */
function dispatchFor(ctx, record, task) {
  const story = relOf(ctx, ctx.storyPath);
  const head = ['# Story 独立人读审查 · 派审', '',
    `- 工程根：\`${record.project_root}\``,
    `- 材料键：\`${record.material_key}\``];
  if (record.reused) {
    return `${[...head, `- 审查任务：\`${task}\``, `- 已有通过的回复：\`${record.report_file}\``, '',
      '这份材料已有可复用的审查结论，这一次不派审，直接跑 `story-build review --action check`。'].join('\n')}\n`;
  }
  const last = record.last_received;
  if (record.disclosure) {
    return `${[...head, '', `本版不派审：${record.disclosure}。`, '', ...(lastConclusion(ctx, last) === 'fail'
      ? [`最近一份可消费的独立回复判了 fail（\`${last.report_file}\`），之后还没有新的可消费回复：`
        + '`story-build review --action check` 的结果是 fail（已知必修未复核），不能登记交付；'
        + '有可用的独立读者时以 `--reader task` 重新 `story-build review --action prepare`，按那时生成的载体复核。']
      : ['未审披露已写进 Story 交付章与 Review 题头。直接跑 `story-build review --action check`（结果是 unreviewed），'
        + '再按已有授权登记与交付；交付说明照实写本版未审。'])].join('\n')}\n`;
  }
  const out = [...head, `- 被审的 Story：\`${story}\``, `- 审查任务：\`${task}\``,
    ...(record.prior_report ? [`- 原报告：\`${record.prior_report}\`（只读）`] : []), '',
    '你是与作者隔离的独立读者，只读，不写任何文件；你的最终回复就是审查报告，主执行者把它原样写到'
      + ` \`${record.report_file}\`（工程相对路径）。`, ''];
  if (record.prior_problem) {
    out.push('## 补正上一份回复', '',
      `上一份回复 \`${record.prior_report}\` 不能接收：${record.prior_problem}。它留在原处。`
        + '原来的判断充分就照用，按审查任务「报告怎么写」给一份完整的最终回复；判断不足的部分回材料补核，并在回复里写明这次补了什么。');
  } else if (record.prior_report) {
    out.push('## 复核', '',
      `这是复核。通读当前 \`${story}\`，按审查任务核原报告的每条问题现在是否成立、这一版改动涉及的行为与引用，必要时回查来源；`
        + '你没有经手原报告那一轮、或改动的影响说不清时，补足业务核查。回复里写明这次实际核了什么，以及没有重做首次阅读。');
  } else {
    out.push('## 先首读', '',
      `先只读 \`${story}\` 一遍，像第一次拿到它的评审者：读完能不能说出这个需求要做什么、为什么、用户怎么走、`
        + '正常与异常各到哪、怎样判定完成；哪里读不懂、要回头找、前后说法不一。记下首读结论之前不读别的文件；'
        + '之后读审查任务，按它核源与逐项判据。');
  }
  out.push('', `回复开头两行写 \`material_key: ${record.material_key}\` 与 \`conclusion: pass|warn|fail\`，其余见任务「报告怎么写」。`);
  return `${out.join('\n')}\n`;
}

/** 派审载体与准备记录还对不对得上：对不上返回原因。 */
function dispatchProblem(ctx, was) {
  const task = relOf(ctx, path.join(ctx.featureRoot, ...TASK));
  if (readText(places(ctx).dispatch) !== dispatchFor(ctx, was, task)) {
    return '派审载体 AR/story-src/review/dispatch.md 不在，或与准备记录对不上';
  }
  return null;
}

/**
 * 本次准备时有没有可用的独立读者，由主执行者按实际工具说明核过后给出（`--reader task|unavailable`）：
 * 没有就如实披露未审，原因写实际缺什么。结论存进 `ctx.disclosure`，Review 题头与 Story 交付章按同一个结论写披露。
 *
 * @param {{kind: 'task'|'unavailable', reason?: string}} reader
 */
export function setReader(ctx, reader) {
  ctx.disclosure = reader.kind === 'unavailable' ? { reason: `没有可用的独立读者：${reader.reason}` } : null;
  return ctx.disclosure;
}

/** 要写进交付件的未审披露：准备过程中用本次给出的读者情况，其余时候认准备记录里记下的那一条。 */
function disclosure(ctx) {
  if (ctx.disclosure !== undefined) return ctx.disclosure;
  const reason = readJson(places(ctx).prepared, null)?.disclosure;
  return reason ? { reason } : null;
}

/** 审查状态的机器区：Story 交付章与 Review 题头共用这一份，区名取章节合同；没有未审披露返回空。 */
export function reviewStatusBlock(ctx) {
  const name = (ctx.contract.chapters ?? []).find(c => c.review_status)?.review_status;
  const rows = reviewStatusLines(disclosure(ctx));
  return name && rows.length ? zoneBlock(name, '未审披露（没有可用的独立读者时自动写）', rows) : [];
}

function reviewStatusLines(shown) {
  return shown ? [`本版未经独立审查。原因：${shown.reason}。这是审查事实，不是业务完成、设计准入或发布质量结论；`
    + '有可用的独立读者之后，重新准备审查走正常审查。'] : [];
}

/** 最近一次可消费回复的结论，交给登记与交付：结论原样取自读者回复，详情指向原件。 */
function conclusionOf(last, conclusion) {
  const detail = conclusion === 'pass' ? `审查通过（原报告 ${last.report_file}）`
    : conclusion === 'warn' ? `审查结论 warn：非阻断建议在原样报告 ${last.report_file} 里，交付说明如实写采纳与保留的理由`
      : `审查结论阻断：发现与修正责任在原样报告 ${last.report_file} 里`;
  return { result: conclusion, detail, report_file: last.report_file, material_key: last.material_key };
}

/** 这一次审查的结果，只读。显式 check、登记、交付门与状态共用。 */
export function reviewResult(ctx) {
  const read = preparedRecord(ctx);
  if (read.error) return { result: 'input_invalid', detail: read.error };
  const was = read.record;
  if (!was) return { result: 'report_missing', detail: '还没准备这一次的审查——先跑 `story-build review --action prepare`' };
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
  const last = was.last_received ?? null;
  const altered = lastProblem(ctx, last);
  if (altered) return { result: 'report_invalid', report_file: last.report_file, detail: altered };
  const at = { report_file: was.report_file };
  if (was.reused) return conclusionOf(last, lastConclusion(ctx, last));
  const bytes = bytesOf(ctx, was.report_file);
  if (bytes !== null) {
    if (last?.report_file === was.report_file) return conclusionOf(last, lastConclusion(ctx, last));
    const head = headOf(bytes.toString('utf-8'));
    if (head.problem) {
      return { result: 'report_invalid', ...at, detail: `${head.problem}。这份回复留在原处；重跑 prepare 取新的回复位置，`
        + '按新载体请独立读者补一份完整的最终回复' };
    }
    if (head.key !== was.material_key) return { result: 'subject_stale', ...at, detail: '回复写的材料键不是这一次准备的：按这一次的派审载体重新派审' };
    return { result: 'report_unreceived', ...at,
      detail: `${was.report_file} 里的回复还没接收：重跑 \`story-build review --action prepare\` 接收（记下原样字节的摘要），再 check` };
  }
  if (lastConclusion(ctx, last) === 'fail') {
    return { result: 'fail', ...at, detail: `已知必修未复核：最近一份可消费的独立回复（${last.report_file}）判了 fail，`
      + '之后还没有新的可消费回复——按派审载体交独立读者复核' };
  }
  if (was.prior_problem) {
    return { result: 'report_invalid', report_file: was.prior_report,
      detail: `${was.prior_problem}（新的派审载体已带原回复与原因，回复位置 ${was.report_file}：按它派审）` };
  }
  if (was.disclosure) return { result: 'unreviewed', ...at, detail: `本版未经独立审查：${was.disclosure}` };
  return { result: 'report_missing', ...at, detail: `独立读者的回复不在 ${was.report_file}——把读者的最终回复原样写到那里` };
}

/**
 * Story 交付章里的审查状态：没有可用独立读者时写未审披露，否则撤掉；在哪一章、区名取章节合同。
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
