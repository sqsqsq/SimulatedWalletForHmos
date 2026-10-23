/**
 * 同图增强阅读的验收 —— 一张正式图的 SVG 是否经过源码的独立文本审查：请求绑定这张图，报告绑定请求。
 *
 * 证据放在 `AR/story-src/figures/<ID>.reading/`：
 * `request.json`（本模块按同 ID 的 `.mmd`、SVG 与它引用的本地资源生成）、
 * `report.json`（独立执行体返回、作者原样留存）。它们是派生阅读证据：不进材料原件、成文登记、正式业务审查与上传。
 *
 * 只绑这张图自己：图源内容、SVG 与递归本地资源、审查方法。正文其它章节、编号、注释分隔空行与显隐不在绑定里，
 * 变了不使审查失效；源、SVG 或资源真改了才失效。位置由正式图块原位决定，脚本核，不交审查者判。
 * 脚本只核文件、绑定与结论自洽；SVG 是否忠实于源、增强后是否更好读，由独立审查者读源码判断，
 * 结论不含实际渲染外观；报告里的执行引用证明不了一段对话真的发生——那由宿主事件与会话证据核。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { runPython } from '../flow/client.mjs';
import { shellArg } from './drafts.mjs';
import { extensionRoot } from '../../../../../hooks/shared/paths.mjs';

/** 每张图必核的两件：与图源的事实与关系一致、增强后的呈现更好读。都读 SVG 源码判，不要求渲染图。 */
const CHECKS = ['semantic_fidelity', 'reading_quality'];
const METHOD = 'story-figure-svg/1';
const VERDICTS = ['PASS', 'WARN', 'FAIL', 'UNKNOWN', 'SKIP'];
const FIGURE_CHECK = path.join(path.dirname(fileURLToPath(import.meta.url)), 'figure-check.py');

const readingDir = (featureRoot, id) => path.join(featureRoot, 'AR', 'story-src', 'figures', `${id}.reading`);
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
export const readOr = (file) => { try { return fs.readFileSync(file, 'utf-8'); } catch { return null; } };
//: 内容按 LF 比：行尾在不同机器上不同，不算图源变了
export const lf = (text) => (text === null ? null : text.replace(/\r\n/g, '\n'));
export const srcPath = (featureRoot, id) => path.join(featureRoot, 'AR', 'story-src', 'figures', `${id}.mmd`);
const entry = (featureRoot, rel) => {
  try { return { path: rel, sha256: sha(fs.readFileSync(path.join(featureRoot, ...rel.split('/')))) }; } catch { return null; }
};
const readJson = (file) => { try { return JSON.parse(fs.readFileSync(file, 'utf-8')); } catch { return undefined; } };

/** 正式图块的 Mermaid 形态：与 `.mmd` 逐字相同的一个 Mermaid 围栏。视图重铺与一致性核共用这一份。 */
export const mermaidBody = (src) => ['```mermaid', ...src.replace(/\r?\n$/, '').split(/\r?\n/), '```'];

//: 同一次命令里同一份 SVG 只核一次：按内容记，内容变了就重核；进程结束即失效，不跨命令留存
const checked = new Map();

/**
 * SVG 的确定性事实：结构问题与它实际用到的本地资源，由 figure-check 一次给出。视图切换与验收共用这一份。
 *
 * @returns {{missing?: true, error?: string, problems?: string[], deps?: string[]}}
 */
export function svgFacts(featureRoot, id) {
  const file = path.join(featureRoot, 'AR', 'figures', `${id}.svg`);
  let bytes;
  try { bytes = fs.readFileSync(file); } catch { return { missing: true }; }
  const key = `${file}\0${sha(bytes)}`;
  if (!checked.has(key)) {
    const r = runPython(FIGURE_CHECK, [file, '--id', id, '--json']);
    let facts = null;
    try { facts = JSON.parse(r.stdout ?? ''); } catch { facts = null; }
    checked.set(key, r.error || !Array.isArray(facts?.problems) ? { error: r.error ?? r.output } : facts);
  }
  return checked.get(key);
}

/** 这张图此刻的验收输入：图源、SVG、它引用的本地资源（递归）。缺什么列进 problems。 */
function currentInputs(featureRoot, id) {
  const problems = [];
  const text = lf(readOr(srcPath(featureRoot, id)));
  const src = `AR/story-src/figures/${id}.mmd`;
  if (text === null) problems.push(`图源 ${src} 不在：从备份或真实依据恢复，不从正文或 SVG 反写`);
  const svg = entry(featureRoot, `AR/figures/${id}.svg`);
  if (!svg) problems.push(`增强阅读图 AR/figures/${id}.svg 不在`);
  let resources = [];
  if (svg) {
    const facts = svgFacts(featureRoot, id);
    if (facts.error) problems.push(`本地资源枚举不了（${facts.error}）：依赖确定不了就不发请求`);
    else {
      problems.push(...facts.problems);
      resources = facts.deps.map(d => entry(featureRoot, `AR/${d}`)).filter(Boolean);
    }
  }
  const source = text === null ? null : { path: src, sha256: sha(text) };
  return { inputs: { source, svg, resources }, contents: { source: text ?? '' }, problems };
}

const requestBody = (id, inputs) => ({ version: 1, id, method: METHOD, inputs, checks: CHECKS });
const requestId = body => sha(JSON.stringify(body)).slice(0, 16);

/**
 * 生成这张图的验收请求。请求只由输入决定：同样的输入得到同一个请求，不重写文件。`contents` 是交给审查者的图源原文。
 *
 * @returns {{problems: string[], request?: object, written?: boolean, contents?: object}}
 */
export function readingRequest(featureRoot, id) {
  const dir = readingDir(featureRoot, id);
  const { inputs, contents, problems } = currentInputs(featureRoot, id);
  if (problems.length) return { problems };
  const body = requestBody(id, inputs);
  const request = { ...body, request_id: requestId(body) };
  const text = `${JSON.stringify(request, null, 2)}\n`;
  const file = path.join(dir, 'request.json');
  const written = !fs.existsSync(file) || fs.readFileSync(file, 'utf-8') !== text;
  if (written) {
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(file, text, 'utf-8');
  }
  return { problems: [], request, written, contents };
}

const REQUEST_AGAIN = id => `\`view --mode review-request --id ${id}\``;

/**
 * 这张图的验收到哪一步了（只读）：`ready` 才能显示 SVG。`reason` 给出这一状态下最小的恢复动作，
 * 与 `reference/svg.md` 一致：图源、SVG 或资源变了重发请求重审，缺报告只补同一请求的报告。
 *
 * @returns {{state: 'no-request'|'invalid'|'stale'|'no-report'|'incomplete'|'failed'|'ready', reason: string}}
 */
export function readingState(featureRoot, id) {
  const dir = readingDir(featureRoot, id);
  const request = readJson(path.join(dir, 'request.json'));
  if (request === undefined) return { state: 'no-request', reason: `还没有验收请求：跑 ${REQUEST_AGAIN(id)}，交独立审查` };
  if (request?.version !== 1 || request?.method !== METHOD) {
    return { state: 'invalid', reason: `request.json 是 ${request?.method ?? '认不出的'} 合同，本版是同图增强 ${METHOD}`
      + '：旧补充图的请求与报告不能当这张图的验收，按当前图源与 SVG '
      + `跑 ${REQUEST_AGAIN(id)} 重新生成请求交独立审查（旧证据留在原处）` };
  }
  const { request_id: claimed, ...body } = request;
  if (claimed !== requestId(body)) {
    return { state: 'invalid', reason: 'request.json 的内容与它自己的 request_id 对不上（请求被改过）：'
      + `跑 ${REQUEST_AGAIN(id)} 按当前输入重新生成，交独立审查` };
  }
  const { inputs, problems } = currentInputs(featureRoot, id);
  if (problems.length || claimed !== requestId(requestBody(id, inputs))) {
    return { state: 'stale', reason: `请求绑定的图源、SVG 或资源已经变了${problems.length ? `（${problems.join('；')}）` : ''}：`
      + `跑 ${REQUEST_AGAIN(id)} 生成新请求，交独立审查` };
  }
  const report = readJson(path.join(dir, 'report.json'));
  if (report === undefined) {
    return { state: 'no-report', reason: `请求 ${request.request_id} 还没有独立审查报告 report.json：输入没变，`
      + `跑 ${REQUEST_AGAIN(id)} 取任务（请求不变），交独立审查后把回复原样存下` };
  }
  const bad = reportProblems(report, request.request_id);
  if (bad.invalid.length) {
    return { state: 'invalid', reason: `report.json 不成立：${bad.invalid.join('；')}——请求还有效，向独立审查者取回`
      + '这一请求的合规原始回复原样存下，不重建输入，作者不改结论' };
  }
  if (bad.failed.length) {
    return { state: 'failed', reason: `独立审查判了不通过：${bad.failed.join('；')}——按意见改 SVG 再生成请求交独立审查；`
      + '要改的是图的意思时改 .mmd 与它的业务依据，再按新源重做 SVG' };
  }
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
  const extra = ids.filter(x => !CHECKS.includes(x));
  if (extra.length) out.invalid.push(`有请求之外的必核项：${extra.join('、')}`);
  for (const id of CHECKS) {
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

/** 原文放进围栏：围栏比原文里最长的反引号串多一个。 */
const fenced = (text) => {
  const tick = '`'.repeat(Math.max(3, ...[...text.matchAll(/`+/g)].map(m => m[0].length + 1)));
  return [`${tick}mermaid`, text.trim(), tick];
};

/**
 * 验收任务分两段：【交给审查者】是独立只读审查执行体要读的全部输入、必核项与要返回的报告形状——它只返回报告，
 * 不写文件、不跑命令；【作者收尾】是作者把返回的报告原样落盘并核对。作者的「已正确」结论不进来；
 * 路径是这一次运行时的实际位置，不写进任何模板。
 */
export function reviewTask(projectRoot, featureRoot, { request, contents }) {
  const fromRoot = p => path.relative(projectRoot, path.join(featureRoot, ...p.split('/'))).split(path.sep).join('/');
  const { inputs, id } = request;
  return [
    `增强阅读图验收请求 ${request.request_id}（正式图 ${id}）。作者：用宿主现有的专用独立只读审查入口（如 verifier 子代理）同步调用一次，`
      + '把下面【交给审查者】一段原样作为完整任务交给它，不附你的结论，取它的最终回复后按【作者收尾】做。'
      + '不走后台通用子代理、不轮询催收、不另拟报告格式；只收阶段审查请求的入口不能用，也不伪造阶段请求。'
      + '宿主没有能收这种自足任务并原样返回回复的独立入口时，如实报「独立审查入口缺失」，请求与已做的图保留。',
    '【交给审查者】',
    `工程根：${projectRoot}；下面的路径都相对工程根。请求文件：${fromRoot(`AR/story-src/figures/${id}.reading/request.json`)}`,
    `这是正式图 ${id} 的增强阅读 SVG：同一张图、同样的事实，只把布局、分组、角色或层次、标注与连线做得更清楚，不追加业务关系。`
      + '它在 Story 里与 Mermaid 同一位置切换显示，位置由脚本核，不用你判。',
    `图源（这张图唯一的语义真源）：${fromRoot(inputs.source.path)}`, ...fenced(contents.source),
    `审查者自己打开读源码：${[inputs.svg, ...inputs.resources].map(x => fromRoot(x.path)).join('、')}。`
      + '核图里实际的文字、图元与连线，不拿 title、metadata 或作者说法代替；不需要渲染图或看图能力。'
      + '必要的事实只在嵌入位图或转曲路径里的，写进 unreviewed，不猜它的内容。',
    '逐项给结论（PASS / WARN / FAIL / UNKNOWN / SKIP）与证据：',
    '- semantic_fidelity：与图源逐项对——参与方与节点、文字、连线的起止与方向、先后、条件与分支去向、等待与失败责任、'
      + '状态迁移的触发与终态。少了、多了、方向错、漏异常、把动作画成状态变化都判 FAIL；与源同义是本来要求，不以「与 Mermaid 重复」拒绝；',
    '- reading_quality：布局、分组、角色或层次区分、标注是否让这张图比源更容易读；从源码看得出的文字或连线重叠、'
      + '标签离开所属连线、读序混乱，按对阅读的影响判 WARN 或 FAIL 并写明位置。',
    `把报告作为你的最终回复返回，只返回这一个 JSON，不写文件、不跑命令：{"request_id": "${request.request_id}", "executor": "", `
      + '"checks": [{"id","verdict","evidence"}], "blocking_findings": [], "advisories": [], "unreviewed": []}',
    '【作者收尾】',
    `1. 把审查者返回的 JSON 原样存为 ${fromRoot(`AR/story-src/figures/${id}.reading/report.json`)}，只把 executor 填成宿主返回的`
      + '这次审查执行或会话引用，其余一字不改；',
    // 入口按工程配置的扩展目录取，与核心归档同一解析；参数逐个按宿主 shell 引好，照抄即可跑
    `2. 跑 \`node ${shellArg(path.join(extensionRoot(projectRoot), 'skills', 'story', 'scripts', 'core', 'story-build.mjs'))} `
      + `view --mode review-check --id ${id} --feature ${shellArg(path.basename(featureRoot))} --project-root ${shellArg(projectRoot)}\` 核对。`,
  ];
}
