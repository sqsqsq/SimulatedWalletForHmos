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

/** 走局部明细合同的判据 → 它的必审集合用途。 */
export const COVERED_CHECKS = { knowledge_obligation_substance: 'plan' };

/** 明细的四个键：无论结论都写。 */
export const DETAIL_KEYS = ['blocking_findings', 'advisories', 'examined_inputs', 'unreviewed'];

/** 判据结论的合法取值；只有 PASS 与 WARN 算审完。 */
const REVIEW_STATUSES = ['PASS', 'WARN', 'FAIL', 'UNKNOWN', 'SKIP'];

const sha12 = bytes => crypto.createHash('sha256').update(bytes).digest('hex').slice(0, 12);

/** 登记里的相对路径是否落在需求目录内：字符串、相对、规范化后不出界。 */
const ownRel = rel => typeof rel === 'string' && rel.trim() && !path.isAbsolute(rel) && !/^[\\/]/.test(rel)
  && !rel.split(/[\\/]/).includes('..');

/** 一笔关卡记录里决定授权含义的部分：关卡与会议话题身份、当时摆出的选项原文、人选的、原话、谁定、是否生效。 */
const gateFacts = g => ({ gate: g?.gate, meeting: g?.meeting, item: g?.item,
  options: (Array.isArray(g?.options) ? g.options : []).map(o => ({ key: o?.key, label: o?.label })),
  chosen: g?.chosen, reply: g?.reply, by: g?.by, outcome: g?.outcome });

/** story-flow 里与范围有关的稳定部分：拆分与各关卡的授权含义；时间、排版序号与登记标记不进来。 */
function scopeProjection(flow) {
  const gates = (flow?.rounds ?? []).flatMap(r => (Array.isArray(r?.gates) ? r.gates : [])).map(gateFacts);
  return JSON.stringify({ scope_text: flow?.split?.scope_text ?? null, parts: flow?.split?.parts ?? [], gates });
}

/**
 * 关卡人签：关卡记录里人表过态且生效（`by: human`、`outcome: accepted`）的每一笔，给当时摆出的选项、人选的与原话。
 * 它是人答的来源之一，不是全集：对话里明确答过的问题由作者在登记条目的澄清正文里引用原话；模型提议与被退回的回话不在这里。
 * 没有流程契约就没有这类人签，契约读不出是缺口。
 *
 * @param {string} root 需求目录
 */
export function signedGateRows(root) {
  const file = path.join(root, 'AR', 'story-src', 'story-flow.json');
  if (!fs.existsSync(file)) return ['本需求没有走 `/story` 的关卡，没有这类人签。'];
  const flow = readJsonOrNull(file);
  if (!Array.isArray(flow?.rounds)) {
    return ['**`AR/story-src/story-flow.json` 读不出关卡记录**：人签原文未取得，涉及授权的判断写未验证。'];
  }
  const rows = [];
  for (const r of flow.rounds) {
    for (const g of Array.isArray(r?.gates) ? r.gates : []) {
      if (g?.by !== 'human' || g?.outcome !== 'accepted') continue;
      const { options, chosen, reply } = gateFacts(g);
      const label = options.find(o => o.key === chosen)?.label ?? '';
      rows.push(`- 第 ${r.round ?? '?'} 轮 \`${g.gate}\`${g.meeting ? ` · 会议 ${g.meeting} 话题 ${g.item}` : ''}`
        + `：选了「${chosen}」${label}`,
      `  - 当时摆出的选项：${options.map(o => `「${o.key}」${o.label}`).join('；') || '（记录里没有选项）'}`,
      '  - 人的原话：', ...String(reply ?? '').split(/\r?\n/).map(l => `    > ${l}`));
    }
  }
  return rows.length ? rows : ['关卡记录里还没有生效的人签。'];
}

/** update 开着时这一轮的依据：record、before 与本轮 update-notes。记录坏了明确报，不扫别的轮次。 */
function updateInputs(root, flow, add, gaps) {
  const rid = flow?.update?.open;
  if (!rid) return null;
  const base = `AR/story-src/updates/${rid}`;
  if (!/^[\w.-]+$/.test(String(rid))) { gaps.push(`story-flow.json 的 update.open「${rid}」不是合法的轮次 id`); return rid; }
  const record = readJsonOrNull(path.join(root, base, 'record.json'));
  if (!record || record.id !== rid || record.status !== 'open') {
    gaps.push(`${base}/record.json 读不出，或它记的 id/状态与 update.open 对不上——这一轮缺比较基准，不是没有变化`);
    return rid;
  }
  const mirror = String(record.mirror?.path ?? '');
  const beforeAbs = path.join(root, ...mirror.split('/'));
  if (!mirror.startsWith(`${base}/`) || mirror.split('/').includes('..')) {
    gaps.push(`${base}/record.json 的 mirror.path「${mirror}」不在这一轮自己的目录下`);
    return rid;
  }
  let entries = [];
  try { entries = fs.readdirSync(beforeAbs); } catch { entries = []; }
  if (!entries.length) gaps.push(`${mirror}/ 不在或是空的——这一轮缺比较基准，不是没有变化`);
  const files = record.files && typeof record.files === 'object' ? record.files : {};
  const expected = new Set(Object.keys(files));
  if (Object.keys(record.phases_before ?? {}).length) ['acceptance.yaml', 'AR/story-src/decisions.json'].forEach(x => expected.add(x));
  for (const rel of [...expected].sort()) {
    if (!ownRel(rel)) { gaps.push(`${base}/record.json 记的文件「${rel}」不是需求目录内的相对路径`); continue; }
    const abs = path.join(beforeAbs, ...rel.split('/'));
    add(abs, `update 前的 ${rel}`);
    let bytes = null;
    try { bytes = fs.readFileSync(abs); } catch { bytes = null; }
    const want = String(files[rel] ?? '').replace(/^sha256:/, '');
    if (bytes && want && !crypto.createHash('sha256').update(bytes).digest('hex').startsWith(want)) {
      gaps.push(`${mirror}/${rel} 与 record.json 记的摘要 ${files[rel]} 对不上——旧现场被改过`);
    }
  }
  add(path.join(root, base, 'update-notes.md'), '本轮变化的依据、影响、决定与不变项（作者在送审前写好）');
  return rid;
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
  // Story 三件只在走 /story 的需求里必有（流程契约在即是，读坏了也是）；直接 spec→plan 没有义务生产它们，
  // 但本单实际有的决定与评审记录仍是依据，在就必审
  const walked = fs.existsSync(at('AR/story-src/story-flow.json'));
  const story = walked;
  const own = rel => ({ required: story || fs.existsSync(at(rel)) });
  const flow = readJsonOrNull(at('AR/story-src/story-flow.json'));
  if (walked && !flow) gaps.push('AR/story-src/story-flow.json 在却读不出——范围与关卡人签未取得');
  add(at('AR/story-src/story-flow.json'), '已确认的范围与关卡人签（摘要按范围、选项原文与人签的稳定投影算）',
    { text: scopeProjection(flow), required: story });
  add(at('AR/story-src/decisions.json'), '登记的决定：哪些定了、哪些开着；澄清正文里引用的人答原话与作者解释分开核', own('AR/story-src/decisions.json'));
  add(at('AR/review.md'), '决策与评审记录：人的原话与表态', own('AR/review.md'));
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
  const update = updateInputs(root, flow, add, gaps);
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
