/**
 * 局部阅读验收 —— 当前这张 SVG 是否真经过渲染与独立对照：请求绑定输入，报告绑定请求。
 *
 * 证据放在 `AR/story-src/figures/<ID>.reading/`：`render.png`（宿主渲染当前 SVG 的完整图像）、
 * `request.json`（本模块按当前源、SVG、本地资源与渲染图的字节生成）、`report.json`（独立执行体返回、作者原样留存）。
 * 它们是派生阅读证据：不进材料原件、成文登记、正式业务审查与上传。
 *
 * 脚本只核文件、绑定与结论自洽；图义对不对、看不看得清由独立审查者看真实渲染图判断，
 * 报告里的执行引用证明不了一段对话真的发生——那由宿主事件与会话证据核。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { runPython } from '../flow/client.mjs';

/** 每张图必核的三件：语义等值、实际渲染可读、与业务位置是否相称。 */
const READING_CHECKS = ['semantic_equivalence', 'visual_readability', 'placement'];
const METHOD = 'story-reading-review/1';
const VERDICTS = ['PASS', 'WARN', 'FAIL', 'UNKNOWN', 'SKIP'];
const FIGURE_CHECK = path.join(path.dirname(fileURLToPath(import.meta.url)), 'figure-check.py');
const PNG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

const readingDir = (featureRoot, id) => path.join(featureRoot, 'AR', 'story-src', 'figures', `${id}.reading`);
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const entry = (featureRoot, rel) => {
  try { return { path: rel, sha256: sha(fs.readFileSync(path.join(featureRoot, ...rel.split('/')))) }; } catch { return null; }
};
const readJson = (file) => { try { return JSON.parse(fs.readFileSync(file, 'utf-8')); } catch { return undefined; } };

/** 这张图此刻的验收输入：源、SVG、它引用的本地资源（递归）、渲染图。缺什么列进 problems。 */
function currentInputs(featureRoot, id) {
  const problems = [];
  const mmd = entry(featureRoot, `AR/story-src/figures/${id}.mmd`);
  const svg = entry(featureRoot, `AR/figures/${id}.svg`);
  const render = entry(featureRoot, `AR/story-src/figures/${id}.reading/render.png`);
  if (!mmd) problems.push(`源 AR/story-src/figures/${id}.mmd 不在`);
  if (!svg) problems.push(`阅读图 AR/figures/${id}.svg 不在`);
  if (!render) problems.push(`渲染图 ${id}.reading/render.png 不在：用宿主的浏览器或渲染工具实际打开当前 SVG，存完整图像`);
  let resources = [];
  if (svg) {
    const r = runPython(FIGURE_CHECK, [path.join(featureRoot, 'AR', 'figures', `${id}.svg`), '--id', id, '--deps']);
    let deps = null;
    try { deps = JSON.parse(r.stdout ?? ''); } catch { deps = null; }
    if (r.error || !deps) problems.push(`本地资源枚举不了（${r.error ?? r.output}）：依赖确定不了就不发请求`);
    else {
      problems.push(...deps.problems);
      resources = deps.deps.map(d => entry(featureRoot, `AR/${d}`)).filter(Boolean);
    }
  }
  return { inputs: { mmd, svg, resources, render }, problems };
}

const requestBody = (id, inputs) => ({ version: 1, id, method: METHOD, inputs, checks: READING_CHECKS });
const requestId = body => sha(JSON.stringify(body)).slice(0, 16);

/**
 * 生成这张图的验收请求。`renderFrom` 给了就把那份渲染图存进证据目录（必须是 PNG）。
 * 请求只由输入决定：同样的输入得到同一个请求，不重写文件。
 *
 * @returns {{problems: string[], request?: object, written?: boolean}}
 */
export function readingRequest(featureRoot, id, renderFrom = '') {
  const dir = readingDir(featureRoot, id);
  if (renderFrom) {
    let bytes = null;
    try { bytes = fs.readFileSync(path.resolve(renderFrom)); } catch { bytes = null; }
    if (!bytes || !bytes.subarray(0, 8).equals(PNG)) return { problems: [`--render ${renderFrom} 读不到或不是 PNG 图像`] };
    fs.mkdirSync(dir, { recursive: true });
    const target = path.join(dir, 'render.png');
    if (!fs.existsSync(target) || !fs.readFileSync(target).equals(bytes)) fs.writeFileSync(target, bytes);
  }
  const { inputs, problems } = currentInputs(featureRoot, id);
  if (problems.length) return { problems };
  const body = requestBody(id, inputs);
  const request = { ...body, request_id: requestId(body) };
  const text = `${JSON.stringify(request, null, 2)}\n`;
  const file = path.join(dir, 'request.json');
  const written = !fs.existsSync(file) || fs.readFileSync(file, 'utf-8') !== text;
  if (written) fs.writeFileSync(file, text, 'utf-8');
  return { problems: [], request, written };
}

/**
 * 这张图的局部验收到哪一步了（只读）：`ready` 才能当可用的阅读图。
 *
 * @returns {{state: 'no-request'|'invalid'|'stale'|'no-report'|'incomplete'|'failed'|'ready', reason: string}}
 */
export function readingState(featureRoot, id) {
  const dir = readingDir(featureRoot, id);
  const request = readJson(path.join(dir, 'request.json'));
  if (request === undefined) return { state: 'no-request', reason: '还没有验收请求：渲染当前 SVG 后跑 view --mode review-request' };
  if (request?.version !== 1 || request?.method !== METHOD) {
    return { state: 'invalid', reason: 'request.json 不是当前的局部验收合同（版本或方法不认）：重新生成请求' };
  }
  const { inputs, problems } = currentInputs(featureRoot, id);
  if (problems.length || request.request_id !== requestId(requestBody(id, inputs))) {
    return { state: 'stale', reason: `请求绑定的输入已经变了${problems.length ? `（${problems.join('；')}）` : ''}：重新渲染、生成请求并交独立审查` };
  }
  const report = readJson(path.join(dir, 'report.json'));
  if (report === undefined) return { state: 'no-report', reason: `请求 ${request.request_id} 还没有独立审查报告 report.json` };
  const bad = reportProblems(report, request.request_id);
  if (bad.invalid.length) return { state: 'invalid', reason: `report.json 不成立：${bad.invalid.join('；')}` };
  if (bad.failed.length) return { state: 'failed', reason: `独立审查判了不通过：${bad.failed.join('；')}——改对应的源或图，重新渲染与审查` };
  if (bad.open.length) return { state: 'incomplete', reason: `独立审查没有核完：${bad.open.join('；')}` };
  return { state: 'ready', reason: '' };
}

/** 报告的结构与结论：invalid 是报告本身不成立，failed 是审查判了问题，open 是没核完。 */
function reportProblems(report, requestIdNow) {
  const out = { invalid: [], failed: [], open: [] };
  if (report?.request_id !== requestIdNow) out.invalid.push(`它审的是请求 ${report?.request_id ?? '（没写）'}，不是当前的 ${requestIdNow}`);
  if (!String(report?.executor ?? '').trim()) out.invalid.push('executor 没写宿主返回的独立执行或会话引用');
  for (const key of ['checks', 'blocking_findings', 'advisories', 'unreviewed']) {
    if (!Array.isArray(report?.[key])) out.invalid.push(`${key} 不是列表`);
  }
  if (out.invalid.length) return out;
  const ids = report.checks.map(c => String(c?.id ?? ''));
  const twice = [...new Set(ids.filter((x, i) => ids.indexOf(x) !== i))];
  if (twice.length) out.invalid.push(`必核项 ${twice.join('、')} 写了不止一次`);
  const extra = ids.filter(x => !READING_CHECKS.includes(x));
  if (extra.length) out.invalid.push(`有请求之外的必核项：${extra.join('、')}`);
  for (const id of READING_CHECKS) {
    const c = report.checks.find(x => String(x?.id ?? '') === id);
    const v = String(c?.verdict ?? '').toUpperCase();
    if (!c) out.open.push(`${id} 没有结论`);
    else if (!VERDICTS.includes(v)) out.invalid.push(`${id} 的结论「${c.verdict}」不在 ${VERDICTS.join(' / ')} 里`);
    else if (!String(c.evidence ?? '').trim()) out.invalid.push(`${id} 没写证据`);
    else if (v === 'FAIL') out.failed.push(id);
    else if (v !== 'PASS' && v !== 'WARN') out.open.push(`${id} 判 ${v}`);
  }
  if (report.blocking_findings.length) out.failed.push(`阻断项 ${report.blocking_findings.length} 条`);
  if (report.unreviewed.length) out.open.push(`未核 ${report.unreviewed.length} 项`);
  return out;
}

/** 交给独立审查者的任务：请求、要打开的文件、必核项与报告形状。作者的「已正确」结论不进来。 */
export function reviewTask(featureRoot, request) {
  const rel = p => `doc/…/${path.basename(featureRoot)}/${p}`;
  return [
    `局部阅读验收请求 ${request.request_id}（图 ${request.id}）：交给不是作者的独立执行体，只传这份任务，不传你的结论。`,
    `审查者自己打开：${[request.inputs.mmd, request.inputs.svg, request.inputs.render, ...request.inputs.resources].map(x => rel(x.path)).join('、')}`,
    `逐项给结论（PASS / WARN / FAIL / UNKNOWN / SKIP）与证据：semantic_equivalence 角色、关系、方向、条件、状态、去向、顺序与 Mermaid 一致；`
      + 'visual_readability 看真实渲染图有没有裁切、遮挡、连线难辨、文字看不清；placement 这张图放在业务位置上是否相称。',
    `报告原样存为 ${rel(`AR/story-src/figures/${request.id}.reading/report.json`)}：`
      + '{"request_id", "executor": "<宿主返回的执行或会话引用>", "checks": [{"id","verdict","evidence"}], '
      + '"blocking_findings": [], "advisories": [], "unreviewed": []}；看不了图就把 visual_readability 判 UNKNOWN 并写进 unreviewed。',
    `存好后跑 view --mode review-check --id ${request.id} 核对。`,
  ];
}
