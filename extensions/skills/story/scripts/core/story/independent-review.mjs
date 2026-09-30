/**
 * Story 的独立审查 —— 接 Framework 原生的无 Feature review request，准备请求、消费结果。
 *
 * - **准备**：写审查任务，按审查对象生成原生请求（目标逐字节绑定，基线 WORKTREE，不带 Feature/Goal 身份），
 *   调原生 prepare 取请求身份与缺口，记下这一次的材料键、报告目录与 request_sha256。
 * - **结果**：审查者的回复原样在 `<报告目录>/review-original.md`；每次核对先把它逐字复制成原生检查用的工作报告
 *   `review-report.md`（原生检查可能回写统计表，原回复只此一份、不被改写），再跑原生正式检查，
 *   核 summary 的身份与证据摘要，按原生检查结果与报告内容归成下面几类。
 *
 * | 结果 | 含义 |
 * |---|---|
 * | pass / warn | 可以登记交付；warn 带非阻断建议 |
 * | fail | 审查结论阻断（不通过，或有未关闭 MAJOR 的有条件通过） |
 * | report_missing / report_invalid | 回复不在，或不合原生报告格式 |
 * | subject_stale | 审的不是现在这份（材料或请求身份变了） |
 * | input_invalid / tool_error | 请求准备不了，或原生检查没给出当前合法结果（含没有声明不适用的阻断项未执行） |
 *
 * 原生 summary 通过只证明报告的结构与绑定，不证明审查独立、业务无遗漏；那两件在真实运行里核。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { explicitRequest, loadNative } from '../../../../../hooks/shared/framework-access.mjs';
import { readerReviewTask } from '../../../../../hooks/shared/reader-review-task.mjs';
import { readJson } from './context.mjs';
import { TASK, materialKey, reviewObject } from './review-object.mjs';

export const ORIGINAL = 'review-original.md';
const WORKING = 'review-report.md';
const sha = data => crypto.createHash('sha256').update(data).digest('hex');
/** 原生检查里说「审的对象变了」的那几项 */
const STALE = new Set(['request_input_changed', 'request_execution_inputs_changed', 'request_binding_stale']);
/** 审查结论本身阻断：不通过；有条件通过而 MAJOR 未关闭 */
const BUSINESS = new Set(['negative_verdict_closure', 'conditional_pass_closure']);
/** 回复不合原生报告格式、事实记录或范围 */
const FORMAT = new Set(['required_chapters', 'issue_table_format', 'severity_values', 'statistics_summary',
  'conclusion_with_verdict', 'review_request_scope', 'review_report_exists', 'request_input_unresolved', 'issue_to_file']);

function places(ctx) {
  const dir = path.join(ctx.featureRoot, ...TASK.slice(0, -1));
  const rel = abs => path.relative(ctx.projectRoot, abs).split(path.sep).join('/');
  return { dir, request: rel(path.join(dir, 'request.json')), prepared: path.join(dir, 'prepared.json') };
}

const args = (request, reportDir, prepare) => ({
  phase: 'review', 'request-file': request, 'report-dir': reportDir, ...(prepare ? { 'prepare-request': true } : {}),
});

/** 原生 prepare：请求被拒（路径保护、目标读不到等）照原话交回。 */
async function nativePrepare(ctx, request, reportDir) {
  try {
    const out = await explicitRequest(ctx.projectRoot, args(request, reportDir, true));
    if (out.code !== 0 || !out.output?.request_sha256) return { error: out.text.slice(0, 800) || '原生 prepare 没有给出请求身份' };
    return { prepared: out.output };
  } catch (e) {
    return { error: String(e?.message ?? e) };
  }
}

/**
 * 准备这一次的审查。审查对象要先成最终版：调用方已重投附录、编号、渲染 Review 并过了结构检查。
 *
 * @returns {Promise<{error?: string, key?: string, reportDir?: string, request_sha256?: string, rows?: object[]}>}
 */
export async function prepareReview(ctx, reportDirArg) {
  const { dir, request, prepared } = places(ctx);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(ctx.featureRoot, ...TASK), `${readerReviewTask(ctx.projectRoot, ctx.args.feature)}\n`, 'utf-8');
  const object = reviewObject(ctx.projectRoot, ctx.args.feature);
  if (object.problems.length) return { error: `审查对象不全：${object.problems.join('；')}` };
  const key = materialKey(ctx.projectRoot, object.rows);
  const reportDir = reportDirArg ?? `doc/reports/story/${ctx.args.feature}/${key.slice(0, 16)}`;
  const body = {
    schema_version: '1.0', phase: 'review',
    requested_result: '按任务文件独立审查当前 Story/Review 的业务完整性、来源、人签及知识应用',
    targets: { files: object.rows.map(r => r.path).sort(), tests: [] },
    baseline: { head: 'WORKTREE' },
    inputs: { review_report: `${reportDir}/${WORKING}` },
    allowed_test_writes: [],
  };
  fs.writeFileSync(path.join(dir, 'request.json'), `${JSON.stringify(body, null, 2)}\n`, 'utf-8');
  const native = await nativePrepare(ctx, request, reportDir);
  if (native.error) return { error: `原生请求准备不了：${native.error}` };
  const expected = new Set([`${reportDir}/context/facts.md`, `${reportDir}/${WORKING}`]);
  const gaps = (native.prepared.gaps ?? []).filter(g => !expected.has(String(g).replace(/\\/g, '/')));
  if (gaps.length) return { error: `原生请求报了缺口：${gaps.join('；')}` };
  fs.writeFileSync(prepared, `${JSON.stringify({ material_key: key, report_dir: reportDir,
    request_sha256: native.prepared.request_sha256 }, null, 2)}\n`, 'utf-8');
  return { key, reportDir, request_sha256: native.prepared.request_sha256, rows: object.rows };
}

/**
 * 这一次审查的结果：审的是不是现在这份、回复在不在、原生检查怎么说、报告结论是什么。
 *
 * @returns {Promise<{result: string, detail: string, advisories?: string[], report_dir?: string}>}
 */
export async function reviewResult(ctx) {
  const { request, prepared } = places(ctx);
  const was = readJson(prepared, null);
  if (!was?.material_key) {
    return { result: 'report_missing', detail: '还没准备这一次的审查——先跑 `story-build review --action prepare`' };
  }
  const object = reviewObject(ctx.projectRoot, ctx.args.feature);
  if (object.problems.length) return { result: 'input_invalid', detail: `审查对象不全：${object.problems.join('；')}` };
  if (materialKey(ctx.projectRoot, object.rows) !== was.material_key) {
    return { result: 'subject_stale', detail: '准备审查之后审查对象变了——审的不是现在这份，重新 prepare，按新材料再审' };
  }
  const dir = path.join(ctx.projectRoot, ...String(was.report_dir).split('/'));
  const original = path.join(dir, ORIGINAL);
  if (!fs.existsSync(original)) {
    return { result: 'report_missing', detail: `审查者的回复不在 ${was.report_dir}/${ORIGINAL}——把独立审查者的回复原样写到那里` };
  }
  fs.copyFileSync(original, path.join(dir, WORKING));
  const again = await nativePrepare(ctx, request, was.report_dir);
  if (again.error) return { result: 'input_invalid', detail: `原生请求准备不了：${again.error}` };
  if (again.prepared.request_sha256 !== was.request_sha256) {
    return { result: 'subject_stale', detail: '原生请求身份与准备时不同——重新 prepare，按新请求再审' };
  }
  let run;
  try {
    run = await explicitRequest(ctx.projectRoot, args(request, was.report_dir, false));
  } catch (e) {
    return { result: 'tool_error', detail: `原生检查出错：${e?.message ?? e}` };
  }
  const summary = readJson(path.join(dir, 'summary.json'), null);
  const scriptFile = path.join(dir, 'script-report.json');
  const current = run.output?.request_sha256 === was.request_sha256 && summary?.subject === 'request'
    && summary?.completion_target === 'request' && summary?.phase === 'review' && summary?.request_sha256 === was.request_sha256
    && fs.existsSync(scriptFile) && summary?.evidence?.script_report_sha256 === sha(fs.readFileSync(scriptFile));
  if (!current) return { result: 'tool_error', detail: `原生检查没有给出这一次请求的合法 summary（${run.text.slice(0, 300)}）` };

  const checks = readJson(scriptFile, {}).checks ?? [];
  // 原生判 FAIL 的，和没有声明不适用却没执行的阻断项，都不是可消费的结论
  const failing = checks.filter(c => c.status === 'FAIL' || (c.status === 'SKIP' && c.severity === 'BLOCKER'
    && c.structured?.applicability !== 'not_applicable'));
  const failed = failing.filter(c => c.status === 'FAIL');
  const listed = failing.map(c => `${c.id}：${String(c.details ?? '').split(/\r?\n/)[0]}`).join('；');
  const at = { report_dir: was.report_dir };
  if (failed.some(c => STALE.has(c.id))) return { result: 'subject_stale', detail: listed, ...at };
  if (failed.some(c => BUSINESS.has(c.id))) return { result: 'fail', detail: `审查结论阻断：${issueRows(ctx, dir).join('；') || listed}`, ...at };
  if (failed.some(c => FORMAT.has(c.id) || String(c.id).startsWith('context_exploration'))) {
    return { result: 'report_invalid', detail: `回复不合原生报告格式：${listed}——保留原回复，请审查者按格式重给，不改它的结论`, ...at };
  }
  if (failing.length) return { result: 'tool_error', detail: `原生检查没有给出可消费的结论，原样列出：${listed}`, ...at };
  const advisories = issueRows(ctx, dir);
  return { result: advisories.length ? 'warn' : 'pass', detail: advisories.length ? `非阻断建议 ${advisories.length} 条` : '审查通过', advisories, ...at };
}

/** 工作报告问题清单的每一行（编号、严重程度、问题描述），用原生报告解析器读。 */
function issueRows(ctx, dir) {
  const parser = loadNative(ctx.projectRoot).module('scripts/utils/markdown-parser.ts');
  const section = parser.getSectionContent(fs.readFileSync(path.join(dir, WORKING), 'utf-8'), '问题清单') ?? '';
  const [table] = parser.extractTables(section);
  if (!table) return [];
  const col = name => table.headers.findIndex(h => h.includes(name));
  const [id, sev, what] = [col('编号'), col('严重'), col('问题描述')];
  return table.rows.map(r => `${r[id] ?? ''} ${r[sev] ?? ''} ${r[what] ?? ''}`.trim());
}
