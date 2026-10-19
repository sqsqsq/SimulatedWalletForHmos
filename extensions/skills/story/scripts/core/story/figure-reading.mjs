/**
 * 阅读图验收 —— 写作设计选中的一张补充 SVG 是否真经过渲染与独立审查：请求绑定输入，报告绑定请求。
 *
 * 证据放在 `AR/story-src/figures/<ID>.reading/`：`render.png`（宿主渲染当前 SVG 的完整图像）、
 * `request.json`（本模块按当前选择、依据实际内容、放置小节、SVG、本地资源与渲染图生成）、
 * `report.json`（独立执行体返回、作者原样留存）。它们是派生阅读证据：不进材料原件、成文登记、正式业务审查与上传。
 *
 * 依据由 `sources.mjs::basisFiles` 逐条解析（真实位置、允许来源、登记身份、原件到阅读稿与原图），这里按类型绑定：
 * 文本整份绑定全文、选定章节绑定那一节（含全部子节），Story 取去掉阅读槽的正式文本；图片与其它二进制按原始字节；
 * 同组的原件、阅读稿与原图各按字节绑定。依据里的正式图块与它的 `.mmd` 不一致就是依据未同步，不出请求。
 * 脚本只核文件、绑定与结论自洽；图对不对、有没有增益、看不看得清由独立审查者判断，
 * 报告里的执行引用证明不了一段对话真的发生——那由宿主事件与会话证据核。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { runPython } from '../flow/client.mjs';
import { FIGURE_MARK, headingPath, markPairs, normalizeHeading, parseDocument } from './document.mjs';
import { basisFiles } from './sources.mjs';

/** 每张阅读图必核的四件：事实与关系忠实、阅读增益、实际渲染可读、与放置位置相称。 */
const READING_CHECKS = ['semantic_fidelity', 'reading_gain', 'visual_readability', 'placement'];
const METHOD = 'story-reading-review/2';
const VERDICTS = ['PASS', 'WARN', 'FAIL', 'UNKNOWN', 'SKIP'];
const FIGURE_CHECK = path.join(path.dirname(fileURLToPath(import.meta.url)), 'figure-check.py');
const PNG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
const STORY = 'AR/story.md';

const readingDir = (featureRoot, id) => path.join(featureRoot, 'AR', 'story-src', 'figures', `${id}.reading`);
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
export const readOr = (file) => { try { return fs.readFileSync(file, 'utf-8'); } catch { return null; } };
//: 内容按 LF 比：行尾在不同机器上不同，不算依据或图源变了
export const lf = (text) => (text === null ? null : text.replace(/\r\n/g, '\n'));
export const srcPath = (featureRoot, id) => path.join(featureRoot, 'AR', 'story-src', 'figures', `${id}.mmd`);
const entry = (featureRoot, rel) => {
  try { return { path: rel, sha256: sha(fs.readFileSync(path.join(featureRoot, ...rel.split('/')))) }; } catch { return null; }
};
const readJson = (file) => { try { return JSON.parse(fs.readFileSync(file, 'utf-8')); } catch { return undefined; } };

/** 正式图块的正文形态：与 `.mmd` 逐字相同的一个 Mermaid 围栏。视图重铺与依据同步核共用这一份。 */
export const mermaidBody = (src) => ['```mermaid', ...src.replace(/\r?\n$/, '').split(/\r?\n/), '```'];

//: 同一次命令里同一份 SVG 只核一次：按内容记，内容变了就重核；进程结束即失效，不跨命令留存
const checked = new Map();

/**
 * 阅读图的确定性事实：结构问题与它实际用到的本地资源，由 figure-check 一次给出。视图切换与验收共用这一份。
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

/** Story 内容的稳定形态：标题序号与图序号只是排版，重编号不算内容变了。 */
function stable(text) {
  const doc = parseDocument(text);
  const byLine = new Map(doc.headings.map(h => [h.at, h]));
  return doc.lines.map((l, k) => {
    const h = byLine.get(k);
    return h ? `${'#'.repeat(h.level)} ${h.name}` : l.replace(/!\[图 \d+(?: · )?/g, '![');
  }).join('\n');
}

/** 一段 Story 文本里与权威 `.mmd` 不一致（或源不在）的正式图块。 */
function unsynced(featureRoot, text) {
  return markPairs(text.split(/\r?\n/), FIGURE_MARK, '图块').spans.filter((b) => {
    const src = lf(readOr(srcPath(featureRoot, b.id)));
    return src === null || b.body.join('\n') !== mermaidBody(src).join('\n');
  }).map(b => b.id);
}
const driftProblem = (featureRoot, text, what) => {
  const ids = unsynced(featureRoot, text);
  return ids.length ? `${what}里的正式图 ${ids.join('、')} 与它的 .mmd 不一致（依据未同步）：`
    + '跑 `story-build view --mode mermaid` 按源重铺正文，再重新生成请求' : null;
};

/**
 * 这张图实际依据的内容：写作设计逐条取，同一路径与标题路径只绑定一次、保留它对应的全部依据写法。
 * `subject.formal` 是去掉阅读槽的正式 Story 文本。`text` 为 null 的是图片或其它二进制，审查者自己打开看。
 */
function basisOf(featureRoot, subject) {
  const problems = [];
  const found = new Map();
  for (const b of subject.item.basis.filter(Boolean)) {
    const r = basisFiles(subject.item.ctx, b);
    if (r.problem) { problems.push(`依据「${b}」${r.problem}`); continue; }
    const key = [r.rel, ...r.names.map(normalizeHeading)].join(' > ');
    if (found.has(key)) { found.get(key).entry.from.push(b); continue; }
    const { primary } = r;
    const story = primary.rel === STORY;
    const whole = story ? subject.formal : primary.text ? lf(primary.bytes.toString('utf-8')) : null;
    const hit = r.names.length ? headingPath(whole, r.names) : { body: whole };
    if (hit.problem) { problems.push(`依据「${b}」${hit.problem}`); continue; }
    const drift = story ? driftProblem(featureRoot, hit.body, `依据「${b}」`) : null;
    if (drift) { problems.push(drift); continue; }
    found.set(key, { text: hit.body, entry: { path: r.rel, read: primary.rel, section: r.names.join(' › ') || null,
      sha256: hit.body === null ? sha(primary.bytes) : sha(story ? stable(hit.body) : hit.body), from: [b],
      related: r.files.filter(f => f !== primary).map(f => ({ path: f.rel, role: f.role, sha256: sha(f.bytes) })) } });
  }
  return { basis: [...found.values()], problems };
}

/**
 * 这张图此刻的验收输入：选择本身、依据实际内容、放置小节、SVG、它引用的本地资源（递归）、渲染图。缺什么列进 problems。
 *
 * @param {{item: object, formal: string, where: string[], order: string[]}} subject figure-view 给出的候选与正式 Story
 */
function currentInputs(featureRoot, subject) {
  const { item } = subject;
  const problems = [];
  const { basis, problems: basisGaps } = basisOf(featureRoot, subject);
  problems.push(...basisGaps);
  const place = headingPath(subject.formal, subject.where);
  const section = subject.where.join(' › ');
  let context = null;
  if (place.problem) problems.push(`放置小节「${section}」在 AR/story.md 里${place.problem}`);
  else {
    const drift = driftProblem(featureRoot, place.body, `放置小节「${section}」`);
    if (drift) problems.push(drift);
    context = { story: STORY, section, sha256: sha(stable(place.body)), order: subject.order };
  }
  const svg = entry(featureRoot, `AR/figures/${item.id}.svg`);
  const render = entry(featureRoot, `AR/story-src/figures/${item.id}.reading/render.png`);
  if (!svg) problems.push(`阅读图 AR/figures/${item.id}.svg 不在`);
  if (!render) problems.push(`渲染图 ${item.id}.reading/render.png 不在：用宿主的浏览器或渲染工具实际打开当前 SVG，存完整图像`);
  let resources = [];
  if (svg) {
    const facts = svgFacts(featureRoot, item.id);
    if (facts.error) problems.push(`本地资源枚举不了（${facts.error}）：依赖确定不了就不发请求`);
    else {
      problems.push(...facts.problems);
      resources = facts.deps.map(d => entry(featureRoot, `AR/${d}`)).filter(Boolean);
    }
  }
  const selection = { question: item.question, gain: item.gain, placement: item.placement, basis: item.basis };
  return { inputs: { selection, basis: basis.map(b => b.entry), context, svg, resources, render },
    contents: { basis, context: place.body ?? '' }, problems };
}

const requestBody = (id, inputs) => ({ version: 2, id, method: METHOD, inputs, checks: READING_CHECKS });
const requestId = body => sha(JSON.stringify(body)).slice(0, 16);

/**
 * 生成这张图的验收请求。`renderFrom` 给了就把那份渲染图存进证据目录（必须是 PNG）。
 * 请求只由输入决定：同样的输入得到同一个请求，不重写文件。`contents` 是交给审查者的依据原文。
 *
 * @returns {{problems: string[], request?: object, written?: boolean, contents?: object}}
 */
export function readingRequest(featureRoot, subject, renderFrom = '') {
  const { id } = subject.item;
  const dir = readingDir(featureRoot, id);
  if (renderFrom) {
    let bytes = null;
    try { bytes = fs.readFileSync(path.resolve(renderFrom)); } catch { bytes = null; }
    if (!bytes || !bytes.subarray(0, 8).equals(PNG)) return { problems: [`--render ${renderFrom} 读不到或不是 PNG 图像`] };
    fs.mkdirSync(dir, { recursive: true });
    const target = path.join(dir, 'render.png');
    if (!fs.existsSync(target) || !fs.readFileSync(target).equals(bytes)) fs.writeFileSync(target, bytes);
  }
  const { inputs, contents, problems } = currentInputs(featureRoot, subject);
  if (problems.length) return { problems };
  const body = requestBody(id, inputs);
  const request = { ...body, request_id: requestId(body) };
  const text = `${JSON.stringify(request, null, 2)}\n`;
  const file = path.join(dir, 'request.json');
  const written = !fs.existsSync(file) || fs.readFileSync(file, 'utf-8') !== text;
  if (written) fs.writeFileSync(file, text, 'utf-8');
  return { problems: [], request, written, contents };
}

/**
 * 这张图的验收到哪一步了（只读）：`ready` 才能当可用的阅读图。
 *
 * @returns {{state: 'no-request'|'invalid'|'stale'|'no-report'|'incomplete'|'failed'|'ready', reason: string}}
 */
export function readingState(featureRoot, subject) {
  const { id } = subject.item;
  const dir = readingDir(featureRoot, id);
  const request = readJson(path.join(dir, 'request.json'));
  if (request === undefined) return { state: 'no-request', reason: '还没有验收请求：渲染当前 SVG 后跑 view --mode review-request' };
  if (request?.version !== 2 || request?.method !== METHOD) {
    return { state: 'invalid', reason: `request.json 是 ${request?.method ?? '认不出的'} 合同，当前验收方法是 ${METHOD}`
      + '（按写作设计的选择与多依据绑定）：按当前选择重新生成请求并交独立审查' };
  }
  const { request_id: claimed, ...body } = request;
  if (claimed !== requestId(body)) {
    return { state: 'invalid', reason: 'request.json 的内容与它自己的 request_id 对不上（请求被改过）：重新生成请求' };
  }
  const { inputs, problems } = currentInputs(featureRoot, subject);
  const expected = requestBody(id, inputs);
  if (problems.length || claimed !== requestId(expected)) {
    return { state: 'stale', reason: `请求绑定的输入已经变了${problems.length ? `（${problems.join('；')}）` : ''}：重新渲染、生成请求并交独立审查` };
  }
  const report = readJson(path.join(dir, 'report.json'));
  if (report === undefined) return { state: 'no-report', reason: `请求 ${request.request_id} 还没有独立审查报告 report.json` };
  const bad = reportProblems(report, request.request_id);
  if (bad.invalid.length) return { state: 'invalid', reason: `report.json 不成立：${bad.invalid.join('；')}` };
  if (bad.failed.length) {
    return { state: 'failed', reason: `独立审查判了不通过：${bad.failed.join('；')}——改图或依据后重新渲染与审查；`
      + '没有阅读增益就回写作设计取消这张图，再走正式内容审查' };
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

/** 原文放进围栏：围栏比原文里最长的反引号串多一个，Mermaid 围栏照原样可读。 */
const fenced = (text) => {
  const tick = '`'.repeat(Math.max(3, ...[...text.matchAll(/`+/g)].map(m => m[0].length + 1)));
  return [`${tick}text`, text.trim(), tick];
};

/**
 * 交给独立审查者的任务：工程根、请求与输入的真实路径、阅读问题与增益、依据原文、放置小节正文、必核项与报告形状。
 * 作者的「已正确」结论不进来；路径是这一次运行时的实际位置，不写进任何模板。
 */
export function reviewTask(projectRoot, featureRoot, { request, contents }) {
  const fromRoot = p => path.relative(projectRoot, path.join(featureRoot, ...p.split('/'))).split(path.sep).join('/');
  const { inputs, id } = request;
  const { selection, context } = inputs;
  const order = context.order.length > 1 ? `（这一处有 ${context.order.length} 张，顺序 ${context.order.join('、')}）` : '';
  return [
    `阅读图验收请求 ${request.request_id}（阅读图 ${id}）：交给不是作者的独立执行体，只传这份任务，不传你的结论。`,
    `工程根：${projectRoot}；下面的路径都相对工程根。请求文件：${fromRoot(`AR/story-src/figures/${id}.reading/request.json`)}`,
    `这张图要回答的阅读问题：${selection.question}；作者说的增益：${selection.gain}`,
    `它放在 ${fromRoot(context.story)} 的「${context.section}」一节末尾的阅读槽里${order}。`,
    `审查者自己打开：${[inputs.svg, inputs.render, ...inputs.resources].map(x => fromRoot(x.path)).join('、')}`,
    '依据（脚本按写作设计当前实际读到的内容；一张图可以综合多段文字、表与图）：',
    ...contents.basis.flatMap(b => [
      `- ${fromRoot(b.entry.read)}${b.entry.read === b.entry.path ? '' : `（${fromRoot(b.entry.path)} 的阅读稿）`}`
        + (b.entry.section ? `「${b.entry.section}」：` : b.text === null ? '（图片，自己打开看）' : '（全文，自己打开读）'),
      ...(b.entry.section ? fenced(b.text) : []),
      ...b.entry.related.map(f => `  - 同组${f.role}：${fromRoot(f.path)}${f.role === '原件' ? '（只作身份，正文以阅读稿为准）' : '（自己打开看）'}`)]),
    `放置小节「${context.section}」的正文（含正式 Mermaid）：`, ...fenced(contents.context),
    '逐项给结论（PASS / WARN / FAIL / UNKNOWN / SKIP）与证据：',
    '- semantic_fidelity：相对全部依据，责任、条件、时序、结果、数量与未决是否准确；可以补出依据里已有的关系，'
      + '不须与哪张单图逐节点相同，不得编造依据里没有的规则；',
    '- reading_gain：是否回答上面的阅读问题；与这一节已有的文字、表与 Mermaid 比，是否把隐含或分散的关系讲清。'
      + '只换颜色或方向不算增益——没有增益判 FAIL，建议作者回写作设计取消这张图；',
    '- visual_readability：亲自打开渲染图，核标签、箭头、布局与裁切；看不了图判 UNKNOWN 并写进 unreviewed，不拿 XML 结构代替；',
    '- placement：图在这一节是否服务叙述，不替代必要正文，不与别处规则矛盾。',
    `报告原样存为 ${fromRoot(`AR/story-src/figures/${id}.reading/report.json`)}：`
      + '{"request_id", "executor": "<宿主返回的执行或会话引用>", "checks": [{"id","verdict","evidence"}], '
      + '"blocking_findings": [], "advisories": [], "unreviewed": []}。',
    `存好后跑 story-build view --mode review-check --id ${id} 核对。`,
  ];
}
