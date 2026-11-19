/**
 * 审查的必审输入与局部明细合同 —— 任务书、报告核对与交付出口共用这一份。
 *
 * 必审集合按阶段用途、章节合同、材料登记与 update 记录**推导应有的输入**，再逐项读：
 * 文件在不在只决定 `missing`，不改变它是不是必审。缺件、不适用与宿主读不了是三件事，
 * 前两者在这里分开，最后一件由审查者写进 `unreviewed`；Framework 裁定看不了图时，
 * 登记图片的图面未核按能力缺口算（`visualDeferral`），其余读不了的仍是没审完。
 *
 * 明细合同只覆盖登记在 `COVERED_CHECKS` 里的扩展判据：它们无论结论都在 YAML 明细里写四个键，
 * 脚本核声明与集合、结论与阻断项是否自洽；声明读全而实际没读懂，脚本识别不了。
 *
 * 必审集合里的每一项有一个核查标识 `key`：原生选中的输入用它的 `input_id`（值在原生审查主 prompt 的
 * `(resolved input <id>)` 块里，这里不另写一份），文件用工程相对路径。明细按标识声明，两种标识各核各的对象。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { featureRoot, readJsonOrNull, relDisplay } from './paths.mjs';
import { loadNative, readFeature } from './framework-access.mjs';
import { knowledgeTaskData } from './knowledge-task.mjs';
import { comparisonContext } from '../../skills/story/scripts/core/story/review-object.mjs';

/** 走局部明细合同的判据 → 它的必审集合用途。 */
export const COVERED_CHECKS = { knowledge_obligation_substance: 'plan' };

/** 明细的四个键：无论结论都写。 */
export const DETAIL_KEYS = ['blocking_findings', 'advisories', 'examined_inputs', 'unreviewed'];

/** 判据结论的合法取值；只有 PASS 与 WARN 算审完。 */
const REVIEW_STATUSES = ['PASS', 'WARN', 'FAIL', 'UNKNOWN', 'SKIP'];

const sha12 = bytes => crypto.createHash('sha256').update(bytes).digest('hex').slice(0, 12);

/** 一笔原话记录里作证据的部分：问题、候选、原话、时刻与出处；不含目标/版本（那是原生反馈的事）。 */
const answerFacts = a => ({ ask_id: a?.ask_id, item_id: a?.item_id, question: a?.question,
  options: (Array.isArray(a?.options) ? a.options : []).map(o => (typeof o === 'string' ? o : o?.label ?? '')),
  reply: a?.reply, at: a?.at, source_ref: a?.source_ref });

/** story-flow 里与人的原话有关的稳定部分：材料确认与设计问答；时间、排版序号与登记标记不进来。 */
function flowProjection(flow) {
  const rounds = (flow?.rounds ?? []).map(r => ({
    materials: r?.materials?.digest ?? null,
    positioning: r?.positioning ?? null,
    material: (Array.isArray(r?.gates) ? r.gates : [])
      .filter(g => g?.gate === 'material_scope')
      .map(g => ({ gate: 'material_scope', chosen: g?.chosen, label: g?.label,
        options: (Array.isArray(g?.options) ? g.options : []).map(o => (typeof o === 'string' ? o : o?.label ?? '')),
        reply: g?.reply, by: g?.by, outcome: g?.outcome })),
    answers: (Array.isArray(r?.answers) ? r.answers : []).map(answerFacts),
  }));
  return JSON.stringify({ rounds });
}

/**
 * 人的原话记录：当前轮的材料确认，与设计后必要问答里逐题记下的问法与回答。
 *
 * **这里只在 Plan 的必审输入摘要里用**（`flowProjection`）：Story 读者审查不再从这里拼一份同义投影，
 * 它直接读审查对象里的必读人答原件（init 与 update 的完整原话都在导出里）。
 * 按时间陈列当时的问法与原话，不预判现在哪一句有效；效力由读者据来源、权限与当前蓝图判。
 *
 * 这里只陈列证据：记录里的 `chosen` 是材料事实的登记项，不是业务裁决；不写「所选 = 人的裁决」。
 */

/**
 * 最近有效变更轮的评审输入：record 固定下来的 before 原件、update-notes 与本轮 review_inputs。
 *
 * 轮次、before 原件与摘要、notes 的轮态义务都由 `review-object` 的 `comparisonContext` 一次给出、一次核完——
 * **与 Story 独审同一份结论**：收口只改记录状态，不把这些已承接的原件移出同一审查上下文；缺件或字节不符
 * 的问题已经在那份结果里（进 `gaps`），这里只把还在的件与 notes 列进必审集合，不再按目录现状另拼一遍。
 * 只认本层已有的事实，不另扫一轮 update 目录、不复制第二个状态源。
 */
function updateInputs(projectRoot, feature, root, flow, add, gaps) {
  const basis = comparisonContext(projectRoot, feature, flow);
  gaps.push(...basis.problems);
  if (!basis.rid) return null;
  for (const entry of basis.inputs) {
    add(path.join(root, ...basis.before.split('/'), ...entry.path.split('/')),
      `update ${basis.rid} 的评审输入原件 ${entry.path}`);
  }
  add(path.join(root, ...basis.notes.split('/')),
    `update ${basis.rid} 变化的依据、影响、决定与不变项（作者在送审前写好）`);
  return basis.rid;
}

/** 原生输入来源的一句话：artifact 写产物名，派生写 provider。 */
const sourceText = s => (s ? `${s.kind}${s.artifact ? ` ${s.artifact}` : s.provider_id ? ` ${s.provider_id}` : ''}` : '来源未知');

/**
 * 必审输入：`purpose` 是 `plan`（施工单位 Plan 阶段的义务审查）。Story 的独立审查按审查对象（review-object）核覆盖，不走这里。
 *
 * 集合由同一次原生阶段解析（`readFeature(plan)`）与同一份审查者知识任务（`knowledgeTaskData`）给出：
 * 原生选中的输入按 `input_id` 必审；本阶段原生要求交出的产物（`required_outputs`）按实际路径必审，缺了就是缺；
 * 盘上已有的 plan.md 与 use-cases.yaml 是审查对象；知识只取任务第 4 块送了正文的那几份（文件与篇），
 * 本单位相关却被登记受众挡住的知识（任务的 `unreachable`）记成缺口；知识自检的问题归知识维护者，只留在任务正文里。
 * 本阶段产物的位置一律取原生 `resolveFeatureArtifact`。
 * 原生没选中的本地 spec.md、acceptance.yaml 不进必审集合，需要时作回查。原生解析不成立时原问题进 `gaps`。
 * 文件路径一律相对工程根；`alias` 与 `visual` 保留同一明细合同的形状，这里不产生图面延期。
 * `native` 与 `knowledgeTask` 是这两份结果本身，审查请求用同一份知识任务正文。
 *
 * @returns {{inputs: {key:string, path:string|null, input_id?:string, purpose:string, required:boolean, missing:boolean,
 *   digest:string|null, output?:boolean}[], update: string|null, gaps: string[], alias: Map<string,string>,
 *   visual: {fact: string, deferred: Set<string>}|null, native: object|null, knowledgeTask: object|null}}
 */
export function reviewInputs(projectRoot, feature, purpose = 'plan') {
  const root = featureRoot(projectRoot, feature);
  const inputs = [];
  const gaps = [];
  const alias = new Map();
  const visual = null;
  const at = rel => path.join(root, ...rel.split('/'));
  const add = (abs, why, { identity = true, text = null, required = true, output = false } = {}) => {
    const p = relDisplay(projectRoot, abs);
    const seen = inputs.find(x => x.key === p);
    if (seen) { seen.required ||= required; seen.output ||= output; return; }
    let bytes = null;
    try { bytes = fs.readFileSync(abs); } catch { bytes = null; }
    if (bytes && text !== null) bytes = Buffer.from(text);
    if (!bytes && !required) return;  // 可选且本单没有：不进表
    inputs.push({ key: p, path: p, purpose: why, required, missing: bytes === null, digest: bytes && identity ? sha12(bytes) : null,
      ...(output ? { output: true } : {}) });
  };
  // 配置读不出时需求目录只能按默认推导：整份集合与视觉裁定都可能不是这个工程的，报缺口，也不延期图面核对
  const configBroken = fs.existsSync(path.join(projectRoot, 'framework.config.json')) && !readJsonOrNull(path.join(projectRoot, 'framework.config.json'));
  if (configBroken) gaps.push('framework.config.json 读不出——需求目录判不了，必审集合按默认目录推导，不能当作这个工程的');
  // Story 与写作设计只在走 /story 的需求里必有（流程契约在即是，读坏了也是）；直接 spec→plan 没有义务生产它们
  const walked = fs.existsSync(at('AR/story-src/story-flow.json'));
  const story = walked;
  const flow = readJsonOrNull(at('AR/story-src/story-flow.json'));
  if (walked && !flow) gaps.push('AR/story-src/story-flow.json 在却读不出——材料确认与设计问答的原话未取得');
  add(at('AR/story-src/story-flow.json'), '材料确认与设计问答的原话（摘要按问法、原话与出处的稳定投影算）',
    { text: flowProjection(flow), required: story });
  add(at('AR/story.md'), '交付的 Story：业务叙事与当前设计占位', { required: story || fs.existsSync(at('AR/story.md')) });
  const native = planInputs(projectRoot, feature, inputs, gaps, add);
  let knowledgeTask = null;
  try {
    knowledgeTask = knowledgeTaskData(projectRoot, { action: 'plan', audience: 'reviewer', feature });
    for (const d of knowledgeTask.documents) {
      add(path.join(projectRoot, ...d.path.split('/')), `本单位相关知识的正文（${d.part}，在知识任务第 4 块）`);
    }
    gaps.push(...knowledgeTask.unreachable);
  } catch (e) {
    gaps.push(`审查者知识任务取不到（${String(e?.message ?? e).split(/\r?\n/)[0]}）——相关知识的正文未取得`);
  }
  const update = updateInputs(projectRoot, feature, root, flow, add, gaps);
  return { inputs, update, gaps, alias, visual, native, knowledgeTask };
}

/** Plan 阶段的原生部分：选中的输入、要交的产物与盘上已有的审查对象。原生解析不成立时原问题进缺口，不按本地文件降级。 */
function planInputs(projectRoot, feature, inputs, gaps, add) {
  let native;
  try {
    native = readFeature(projectRoot, feature, 'plan');
  } catch (e) {
    gaps.push(`原生阶段解析起不来（${String(e?.message ?? e).split(/\r?\n/)[0]}）——本阶段的输入与产物未取得`);
    return null;
  }
  if (native.status !== 'ok') {
    gaps.push(`原生阶段解析不成立（${native.status}）：${(native.issues ?? []).map(i => i.message ?? i.code).join('；') || '原生没有给出问题'}`);
  }
  if (native.scope === 'not_frozen') gaps.push('执行范围还没冻结：本阶段的原生输入未确定，审查对象不是正式的阶段对象');
  for (const [id, value] of Object.entries(native.inputs ?? {})) {
    if (value.state === 'resolved') {
      const b = value.binding ?? {};
      inputs.push({ key: b.input_id ?? id, path: null, input_id: b.input_id ?? id, required: true, missing: false,
        digest: b.content_fingerprint ? String(b.content_fingerprint).slice(0, 12) : null,
        purpose: `原生选中的输入（${sourceText(b.source)}）：值在审查主 prompt 的 \`(resolved input ${b.input_id ?? id})\` 块，来源按 source_refs 回查` });
    } else if (value.state === 'invalid') {
      inputs.push({ key: id, path: null, input_id: id, required: true, missing: true, digest: null,
        purpose: `原生判这份输入不成立：${value.detail ?? '原生没有给出原因'}` });
      gaps.push(`原生输入 ${id} 不成立：${value.detail ?? '原生没有给出原因'}`);
    }
  }
  if (!Array.isArray(native.required_outputs)) {
    gaps.push('原生没有给出本阶段要交的产物（required_outputs）——审查对象未取得');
  }
  const resolveArtifact = name => {
    try {
      return loadNative(projectRoot).module('config.ts').resolveFeatureArtifact(projectRoot, feature, name).actualPath;
    } catch (e) {
      gaps.push(`本阶段产物 ${name} 的位置原生解析不了（${String(e?.message ?? e).split(/\r?\n/)[0]}）`);
      return null;
    }
  };
  for (const name of native.required_outputs ?? []) {
    const abs = resolveArtifact(name);
    if (!abs) continue;
    add(abs, `审查对象：本阶段要交的产物（原生 required_outputs 的 ${name}）`, { output: true });
    if (!fs.existsSync(abs)) gaps.push(`本阶段要交的 ${name} 还没写出（${relDisplay(projectRoot, abs)}）`);
  }
  // 盘上已有的本阶段产物都是审查对象；原生没要求、盘上也没有的不进表。位置与上面同取原生解析
  for (const [name, why] of [['plan/plan.md', '审查对象：设计章'], ['contracts.yaml', '审查对象：契约实体与挂着的义务'],
    ['use-cases.yaml', '审查对象：用例与调用绑定']]) {
    const abs = resolveArtifact(name);
    if (abs) add(abs, why, { required: fs.existsSync(abs) });
  }
  return native;
}

/** 任务书里的「核这些」表：核查标识（原生输入写 input_id，文件写路径）、摘要、用途，缺的点名；明细按标识逐项声明。 */
export function inputRows(basis) {
  return [...basis.inputs.map(x => (x.path === null
    ? `- 原生输入 \`${x.key}\`${x.digest ? `（内容指纹 ${x.digest}）` : ''} —— ${x.purpose}`
      + (x.missing ? '　**没有成立的值**：它是必审输入，写进 unreviewed 并作为阻断原因' : '')
    : `- \`${x.path}\`${x.digest ? `（摘要 ${x.digest}）` : ''} —— ${x.purpose}`
      + (x.missing ? '　**读不到**：它是必审输入，缺了不能判 PASS，写进 unreviewed 并作为阻断原因' : ''))),
  ...basis.gaps.map(g => `- **输入有缺口**：${g}`),
  '', '上面每一项照抄核查标识（原生输入写 input_id，文件写路径）写进 examined_inputs 或 unreviewed（unreviewed 也可以写判据 id），'
    + '一项一份；不用 `*` 通配，也不把几项合成一项。原生输入核审查主 prompt 里它的当前值。'
    + '为核实额外读过的相关文件也可以列进 examined_inputs，它不顶替任何一项必审。'];
}

/** 明细里写的路径规范成表里的写法：去反引号、反斜杠换正斜杠、去开头的 `./`。 */
const inputPath = v => String(v ?? '').replace(/`/g, '').replace(/\\/g, '/').replace(/^\.\//, '').trim();

/** unreviewed 一项：`{path|check, reason}` 或 `<路径或判据>：<原因>`。 */
function skippedItem(u) {
  if (typeof u === 'string') {
    const [head, ...rest] = u.split(/[：:]/);
    return { key: inputPath(head), reason: rest.join('：').trim() };
  }
  return { key: inputPath(u?.path ?? u?.input_id ?? u?.check ?? u?.item), reason: String(u?.reason ?? '').trim() };
}

/**
 * 明细与必审集合、结论自不自洽。`basis` 缺席（核历史报告）时只核结论与结构。
 *
 * @param {string[]} checkIds 当前任务里的判据 id：unreviewed 可以写判据而不是文件
 */
export function detailProblems(details, status, basis, checkIds = []) {
  // 结构问题一次列齐：结论取值、缺的键、不是列表的键
  const shape = REVIEW_STATUSES.includes(status) ? [] : [`结论「${status}」不在 ${REVIEW_STATUSES.join(' / ')} 里`];
  const missing = DETAIL_KEYS.filter(k => !(k in (details ?? {})));
  if (missing.length) shape.push(`明细缺 ${missing.join('、')}——四个键无论结论都写，没有内容的写空列表`);
  const wrong = DETAIL_KEYS.filter(k => k in (details ?? {}) && !Array.isArray(details[k]));
  if (wrong.length) shape.push(`明细的 ${wrong.join('、')} 不是列表`);
  if (shape.length) return shape;
  const out = [];
  const blocking = details.blocking_findings;
  if (status === 'UNKNOWN') out.push('判了 UNKNOWN：这一项没有审完——读完再判，判不了写清缺什么并判 FAIL');
  if ((status === 'PASS' || status === 'WARN') && blocking.length) out.push(`判了 ${status} 却列了 ${blocking.length} 条阻断项，结论与明细矛盾`);
  if (status === 'FAIL' && !blocking.length) out.push('判了 FAIL 却没有阻断项，说不出拦在哪');
  if (!basis) return out;
  const keyOf = x => x.key ?? x.path;
  const table = new Map(basis.inputs.map(x => [keyOf(x), x]));
  const canon = p => basis.alias?.get(p) ?? p;
  if (status === 'SKIP' && basis.inputs.some(x => x.output)) {
    out.push('判了 SKIP，本阶段却有原生要求交出的产物——产物在就按它审，没写出是缺件，判 FAIL 并写成阻断原因');
  } else if (status === 'SKIP' && basis.inputs.some(x => x.purpose.startsWith('审查对象') && !x.missing)) {
    out.push('判了 SKIP，审查对象却在盘上——SKIP 只用于审查对象不存在');
  }
  const seen = new Set();
  const written = new Set();
  for (const raw of details.examined_inputs) {
    const at = inputPath(typeof raw === 'string' ? raw : raw?.path ?? raw?.input_id);
    const p = canon(at);
    // 表是必审集合，不是阅读白名单：额外取证读过的相关文件可以声明，但顶替不了任何一份必审；同一内容的别名各写一次算同一份
    if (!p) out.push(`examined_inputs 里有一项没有核查标识：${JSON.stringify(raw)}`);
    else if (written.has(at)) out.push(`examined_inputs 里「${at}」写了两次`);
    else if (table.get(p)?.missing) {
      out.push(table.get(p).path === null ? `examined_inputs 声明核过原生输入「${p}」，这次原生没有给出成立的值`
        : `examined_inputs 声明读过「${p}」，它在盘上读不到`);
    }
    written.add(at);
    seen.add(p);
  }
  const skipped = new Set();
  for (const u of details.unreviewed) {
    const { key, reason } = skippedItem(u);
    const k = canon(key);
    if (!table.has(k) && !checkIds.includes(key)) out.push(`unreviewed 里的「${key || JSON.stringify(u)}」既不是表里的输入也不是本阶段判据`);
    else if (!reason) out.push(`unreviewed 里的「${key}」没写原因`);
    else if (seen.has(k)) out.push(`「${k}」同时写在 examined_inputs 与 unreviewed`);
    skipped.add(k);
  }
  const openChecks = [...skipped].filter(k => !table.has(k) && checkIds.includes(k));
  if ((status === 'PASS' || status === 'WARN') && openChecks.length) {
    out.push(`判了 ${status}，判项却没核完：${openChecks.join('、')}——判项没核完不能判 PASS 或 WARN`);
  }
  if ((status === 'PASS' || status === 'WARN') && basis.gaps.length) {
    out.push(`判了 ${status}，必审输入还有缺口没有清零：${basis.gaps.join('；')}——缺口在的时候判 FAIL 并写成阻断原因`);
  }
  const silent = basis.inputs.filter(x => x.required && !seen.has(keyOf(x)) && !skipped.has(keyOf(x))).map(keyOf);
  if (silent.length) out.push(`必审输入既没出现在 examined_inputs 也没列进 unreviewed：${silent.join('、')}`);
  // Framework 裁定看不了图时，登记图片的图面未核是能力缺口：允许 WARN，不允许 PASS；其余没核完的照旧不能判 PASS 或 WARN
  const deferred = basis.visual?.deferred ?? new Set();
  const open = basis.inputs.filter(x => x.required && skipped.has(keyOf(x))).map(keyOf);
  const unread = open.filter(p => !deferred.has(p));
  const blind = open.filter(p => deferred.has(p));
  if ((status === 'PASS' || status === 'WARN') && unread.length) {
    out.push(`判了 ${status}，必审输入却有没核完的：${unread.join('、')}——读完再判；缺件或读不了就判 FAIL 并把它写成阻断原因`);
  }
  if (status === 'PASS' && blind.length) {
    out.push(`判了 PASS，图面却没核：${blind.join('、')}——${basis.visual.fact}；图面未核时这一项最高判 WARN，写明文本已核、图面未核`);
  }
  return out;
}
