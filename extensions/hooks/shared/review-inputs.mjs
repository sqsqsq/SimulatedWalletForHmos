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
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { extensionRoot, featureRoot, readJsonOrNull, relDisplay } from './paths.mjs';
import { knowledgeFiles } from './knowledge.mjs';
import { imagesIn } from '../../skills/story/scripts/core/story/images.mjs';
import { sourceStatus } from '../../skills/story/scripts/core/story/sources.mjs';

/** 走局部明细合同的判据 → 它的必审集合用途。 */
export const COVERED_CHECKS = { story_reader_review: 'story', knowledge_obligation_substance: 'plan' };

/** 明细的四个键：无论结论都写。 */
export const DETAIL_KEYS = ['blocking_findings', 'advisories', 'examined_inputs', 'unreviewed'];

/** 判据结论的合法取值；只有 PASS 与 WARN 算审完。 */
const REVIEW_STATUSES = ['PASS', 'WARN', 'FAIL', 'UNKNOWN', 'SKIP'];

const sha12 = bytes => crypto.createHash('sha256').update(bytes).digest('hex').slice(0, 12);

/** 登记里的相对路径是否落在需求目录内：字符串、相对、规范化后不出界。 */
const ownRel = rel => typeof rel === 'string' && rel.trim() && !path.isAbsolute(rel) && !/^[\\/]/.test(rel)
  && !rel.split(/[\\/]/).includes('..');

/** story-flow 里与范围有关的稳定部分：拆分与各关卡的选择、原话与依据；时间与登记标记不进来。 */
function scopeProjection(flow) {
  const gates = (flow?.rounds ?? []).flatMap(r => (Array.isArray(r?.gates) ? r.gates : []))
    .map(g => ({ gate: g?.gate, item: g?.item, meeting: g?.meeting, chosen: g?.chosen, reply: g?.reply, basis: g?.basis }));
  return JSON.stringify({ scope_text: flow?.split?.scope_text ?? null, parts: flow?.split?.parts ?? [], gates });
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

/**
 * Framework 对本需求 Spec 的视觉裁定：看不了图，且保真只按语义布局尽力验收时，登记图片的图面核对可以按能力缺口延期。
 * 能力快照与保真意图都在、都对本需求的 spec、`decision_id` 一致，`vision.verdict` 为 false、
 * `effective_fidelity` 为 semantic_layout、`acceptance_strictness` 为 best_effort，才成立；缺文件、对不上或别的取值都不延期。
 *
 * @returns {{files: string[], fact: string}|null}
 */
function visualDeferral(projectRoot, feature) {
  const dir = path.join(featureRoot(projectRoot, feature), 'spec', 'reports');
  const files = ['capability-snapshot.json', 'fidelity-intent.json'].map(f => path.join(dir, f));
  const [cap, intent] = files.map(readJsonOrNull);
  const identity = `phase:${feature}:spec`;
  if (cap?.execution_identity !== identity || intent?.execution_identity !== identity
    || !cap.decision_id || cap.decision_id !== intent.decision?.decision_id) return null;
  if (cap.vision?.verdict !== false || intent.effective_fidelity !== 'semantic_layout'
    || intent.acceptance_strictness !== 'best_effort') return null;
  return { files, fact: `Framework 裁定本阶段看不了图（capability-snapshot vision=false，决定 ${cap.decision_id}），`
    + '保真按 semantic_layout / best_effort 验收' };
}

/**
 * 必审输入：`purpose` 是 `story`（Spec 阶段的读者审查）或 `plan`（Plan 阶段的义务审查）。
 * 路径一律相对工程根；同一张图的其它落点记进 `alias`，声明哪一个都算这张图。
 * `visual` 在 Framework 裁定可以延期图面核对时给出：那条能力事实与可以按能力缺口写进 unreviewed 的图片。
 *
 * @returns {{inputs: {path:string, purpose:string, required:boolean, missing:boolean, digest:string|null}[],
 *   update: string|null, gaps: string[], alias: Map<string,string>, visual: {fact: string, deferred: Set<string>}|null}}
 */
export function reviewInputs(projectRoot, feature, purpose = 'story') {
  const root = featureRoot(projectRoot, feature);
  const inputs = [];
  const gaps = [];
  const alias = new Map();
  let visual = null;
  const at = rel => path.join(root, ...rel.split('/'));
  const add = (abs, why, { identity = true, text = null, required = true } = {}) => {
    const p = relDisplay(projectRoot, abs);
    const seen = inputs.find(x => x.path === p);
    if (seen) { seen.required ||= required; return; }
    let bytes = null;
    try { bytes = fs.readFileSync(abs); } catch { bytes = null; }
    if (bytes && text !== null) bytes = Buffer.from(text);
    if (!bytes && !required) return;  // 可选且本单没有：不进表
    inputs.push({ path: p, purpose: why, required, missing: bytes === null, digest: bytes && identity ? sha12(bytes) : null });
  };
  const flow = readJsonOrNull(at('AR/story-src/story-flow.json'));
  add(at('AR/story-src/story-flow.json'), '已确认的范围与关卡选择（摘要按范围与选择的稳定投影算）', { text: scopeProjection(flow) });
  add(at('AR/story-src/decisions.json'), '已登记的决定：哪些定了、哪些开着');
  add(at('AR/review.md'), '决策与评审记录：人的原话与表态');
  add(at('spec/spec.md'), purpose === 'plan' ? '有效 Spec：要履行的业务条件与验收' : '已经成立的产品约束');
  add(at('acceptance.yaml'), '验收条目');
  if (purpose === 'plan') {
    add(at('plan/plan.md'), '审查对象：设计章');
    add(at('contracts.yaml'), '审查对象：契约实体与挂着的义务');
    add(at('use-cases.yaml'), '审查对象：用例与调用绑定');
    try {
      for (const rel of knowledgeFiles(projectRoot)) add(path.join(extensionRoot(projectRoot), ...rel.split('/')), '激活知识原文');
    } catch (e) {
      gaps.push(`激活知识清单读不出（${e.message}）——知识依据未取得`);
    }
  } else {
    add(at('AR/story.md'), '审查对象', { identity: false });
    add(at('AR/story-src/story-template.md'), '作者的写作设计');
    add(at('AR/story-src/materials.json'), '材料清单与图片登记');
    const contract = readJsonOrNull(path.join(extensionRoot(projectRoot), 'skills', 'story', 'contracts', 'story-chapters.json'));
    const sources = sourceStatus({ contract: contract ?? {}, featureRoot: root });
    for (const d of sources.docs) add(at(d.rel), contract?.sources?.[d.doc]?.label ?? '合同来源');
    for (const m of sources.missing) add(at(m.rel), contract?.sources?.[m.doc]?.label ?? '合同来源', { required: m.required });
    const manifest = readJsonOrNull(at('AR/story-src/materials.json'));
    const origins = manifest?.origins;
    if (manifest && !Array.isArray(origins)) gaps.push('AR/story-src/materials.json 读不出 `origins`——原材料集合未取得，重跑 `story_flow.py round`');
    const meetings = [];
    for (const o of Array.isArray(origins) ? origins : []) {
      if (!o || !ownRel(o.path) || !Array.isArray(o.readable_paths) || !o.readable_paths.every(ownRel)) {
        gaps.push(`AR/story-src/materials.json 有一条 origin 形状不对或路径出了需求目录：${JSON.stringify(o)}`);
        continue;
      }
      // 只取图的原件：正文没有采用，原件本身不作语义阅读稿（取的图由图片登记逐张审）；原件在不在照核
      const picturesOnly = (o.image_paths ?? []).length > 0;
      if (picturesOnly && !fs.existsSync(at(o.path))) gaps.push(`只取图的原件 ${o.path} 不在盘上：取图的来源无从核对`);
      for (const r of o.readable_paths) if (!(picturesOnly && r === o.path)) add(at(r), `原材料阅读稿（来源 ${o.path}）`);
      if (o.kind === 'meeting') meetings.push(path.posix.dirname(o.path));
    }
    for (const dir of meetings) add(at(`${dir}/corrections.json`), '会议纠偏留痕');
    if (meetings.length) {
      add(at('AR/story-src/meeting-notes.json'), '会议判断');
      add(at('AR/story-src/doc-refresh.md'), '会议与材料刷新后的当前结果');
    }
    if (manifest) {
      const { images, gap } = imagesIn(manifest);
      if (gap) gaps.push(gap);
      for (const img of images) {
        if (!img.paths.every(ownRel)) { gaps.push(`AR/story-src/materials.json 有图片路径出了需求目录：${img.paths.join('、')}`); continue; }
        const main = relDisplay(projectRoot, at(img.paths[0]));
        add(at(img.paths[0]), `原材料图：${String(img.caption ?? '').trim() || '（没写说明）'}`);
        for (const other of img.paths.slice(1)) alias.set(relDisplay(projectRoot, at(other)), main);
      }
    }
    // 只延期盘上在的图：图不在是取材问题，照缺件处理
    const pictures = inputs.filter(x => x.purpose.startsWith('原材料图：'));
    const deferral = pictures.length ? visualDeferral(projectRoot, feature) : null;
    if (deferral) {
      for (const f of deferral.files) add(f, '视觉能力事实：Framework 对本阶段看图能力与保真验收的裁定');
      visual = { fact: deferral.fact, deferred: new Set(pictures.filter(x => !x.missing).map(x => x.path)) };
    }
    add(at('ux-reference/README.md'), '界面交互说明', { required: fs.existsSync(at('ux-reference/README.md')) });
  }
  const update = updateInputs(root, flow, add, gaps);
  return { inputs, update, gaps, alias, visual };
}

/** 任务书里的「读这些」表：路径、摘要、用途，读不到的点名。 */
export function inputRows(basis) {
  return [...basis.inputs.map(x => `- \`${x.path}\`${x.digest ? `（摘要 ${x.digest}）` : ''} —— ${x.purpose}`
    + (x.missing ? '　**读不到**：它是必审输入，缺了不能判 PASS，写进 unreviewed 并作为阻断原因' : '')),
  ...basis.gaps.map(g => `- **输入有缺口**：${g}`)];
}

/** 明细里写的路径规范成表里的写法：去反引号、反斜杠换正斜杠、去开头的 `./`。 */
const inputPath = v => String(v ?? '').replace(/`/g, '').replace(/\\/g, '/').replace(/^\.\//, '').trim();

/** unreviewed 一项：`{path|check, reason}` 或 `<路径或判据>：<原因>`。 */
function skippedItem(u) {
  if (typeof u === 'string') {
    const [head, ...rest] = u.split(/[：:]/);
    return { key: inputPath(head), reason: rest.join('：').trim() };
  }
  return { key: inputPath(u?.path ?? u?.check ?? u?.item), reason: String(u?.reason ?? '').trim() };
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
  const table = new Map(basis.inputs.map(x => [x.path, x]));
  const canon = p => basis.alias?.get(p) ?? p;
  if (status === 'SKIP' && basis.inputs.some(x => x.purpose.startsWith('审查对象') && !x.missing)) {
    out.push('判了 SKIP，审查对象却在盘上——SKIP 只用于审查对象不存在');
  }
  const seen = new Set();
  for (const raw of details.examined_inputs) {
    const p = canon(inputPath(typeof raw === 'string' ? raw : raw?.path));
    if (!p || !table.has(p)) out.push(`examined_inputs 里的「${p || JSON.stringify(raw)}」不在「读这些」表里——照抄表里的路径`);
    else if (seen.has(p)) out.push(`examined_inputs 里「${p}」写了两次`);
    else if (table.get(p).missing) out.push(`examined_inputs 声明读过「${p}」，它在盘上读不到`);
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
  const silent = basis.inputs.filter(x => x.required && !seen.has(x.path) && !skipped.has(x.path)).map(x => x.path);
  if (silent.length) out.push(`必审输入既没出现在 examined_inputs 也没列进 unreviewed：${silent.join('、')}`);
  // Framework 裁定看不了图时，登记图片的图面未核是能力缺口：允许 WARN，不允许 PASS；其余没核完的照旧不能判 PASS 或 WARN
  const deferred = basis.visual?.deferred ?? new Set();
  const open = basis.inputs.filter(x => x.required && skipped.has(x.path)).map(x => x.path);
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
