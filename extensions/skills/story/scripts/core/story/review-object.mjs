/**
 * 独立审查的对象 —— 这一次交给审查者的全部材料，只在这里定义一份。
 *
 * 审查任务列它、原生请求把它作为目标逐字节绑定、材料键由它算、覆盖声明与发现定位对着它核：几处用同一份，审的就是要交付的那一份。
 * 待审的是 Story、Review 与设计附件；其余是只读对照：写作设计、决策登记、会议记录（每版原文、纠偏留痕与阅读件）、
 * 设计采用的材料版本（蓝图需求条目与设计依据引用的本需求版本：原件、阅读正文、图、会议纠偏与阅读件）、冲突依据、
 * 当前有效人答（独立必读，不取决于设计有没有引用）、材料清单登记的全部原件与阅读稿（含设计未见引用的）和每个图片对象、
 * 当前蓝图与评审投影、蓝图契约引用的接口转写与映射、激活清单与知识原文、章节合同与判据。
 * 完整核源让审查能核作者为何采用或排除一份材料：作者的采用选择不缩小这个集合。
 * 流程契约、登记时刻、审查目录与历史报告不在其中：它们变了不改变被审内容。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { adoptedSources, readBlueprint } from '../../../../../hooks/shared/framework-access.mjs';
import { knowledgeRegistrations } from '../../../../../hooks/shared/knowledge.mjs';
import { extensionRoot, featureRoot, readJsonOrNull } from '../../../../../hooks/shared/paths.mjs';
import { materialSet } from './sources.mjs';
import { requiredAnswers } from './design-source.mjs';
import { requirementContext } from './context.mjs';

const sha256 = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

/** 蓝图契约各段 `source_ref` 实际引用的文件（去掉 `#` 之后的指针），按出现顺序去重。 */
function contractSources(blueprint) {
  const refs = [];
  for (const c of blueprint?.contracts ?? []) {
    const parts = [c.operation, c.request_dto, c.response_dto, ...(c.request_dto?.fields ?? []),
      ...(c.response_dto?.fields ?? []), ...(c.mappings ?? []), c.errors, c.idempotency, c.nfr];
    for (const part of parts) {
      const file = String(part?.source_ref ?? '').split('#')[0];
      if (file && !refs.includes(file)) refs.push(file);
    }
  }
  return refs;
}

/** 审查任务在需求目录里的位置：它也是审查对象的一部分。 */
export const TASK = ['AR', 'story-src', 'review', 'task.md'];

/**
 * `withTask` 为假时不含审查任务本身（生成任务时列材料用）。
 *
 * 每行带 `kind`（`text` / `image` / `metadata`）与 `required_read`：为假的行只核在场与来源摘要（二进制原件、只取图的原件、
 * 材料清单本身），仍按字节绑定、进材料键。同一内容的几个路径（图片对象的几个落点）
 * 记进 `alias`：路径 → 规范路径（第一个落点），覆盖、发现定位与图面延期按它归一；内容不同的不互相顶替。
 *
 * @returns {{rows: {path: string, role: 'object'|'source', label: string, kind: string, required_read: boolean}[],
 *   problems: string[], design: {admitted: boolean, issues: object[]}|null, alias: Map<string, string>}}
 *   路径相对工程根；缺了该有的材料写进 problems，不当作没有。`design` 是蓝图的原生准入结论与问题（草稿也审）。
 */
export function reviewObject(projectRoot, feature, { withTask = true } = {}) {
  const root = featureRoot(projectRoot, feature);
  const rel = abs => path.relative(projectRoot, abs).split(path.sep).join('/');
  const rows = [];
  const problems = [];
  const alias = new Map();
  const add = (abs, role, label, required = true, { kind = 'text', read = true, canonical = null } = {}) => {
    if (fs.existsSync(abs) && fs.statSync(abs).isFile()) {
      const p = rel(abs);
      const seen = rows.find(r => r.path === p);
      if (seen) seen.required_read ||= read;
      else rows.push({ path: p, role, label, kind, required_read: read });
      if (canonical && canonical !== p) alias.set(p, canonical);
    } else if (required) problems.push(`${rel(abs)} 读不到（${label}）`);
  };
  const src = path.join(root, 'AR', 'story-src');
  add(path.join(root, 'AR', 'story.md'), 'object', '待审的 Story');
  add(path.join(root, 'AR', 'review.md'), 'object', '待审的决策与评审记录（机器区与人工区）');
  add(path.join(root, 'AR', 'design-review.md'), 'object', '待审的设计附件（本次蓝图原生评审投影的副本）');
  if (withTask) add(path.join(root, ...TASK), 'source', '审查任务');
  add(path.join(src, 'story-template.md'), 'source', '作者的写作设计（待核的作者判断）');
  add(path.join(src, 'decisions.json'), 'source', '决策登记');
  for (const name of ['doc-refresh.md', 'template-adjustments.md', 'meeting-notes.json']) {
    add(path.join(src, name), 'source', name === 'doc-refresh.md' ? '会议之后的当前结果'
      : name === 'meeting-notes.json' ? '会议判断' : '写作设计的调整记录', false);
  }
  // 每版会议：原文、纠偏留痕与纠偏后的阅读件，核纠偏有没有改了意思
  const meetings = path.join(src, 'meetings');
  if (fs.existsSync(meetings)) {
    for (const stem of fs.readdirSync(meetings).sort()) {
      if (!fs.statSync(path.join(meetings, stem)).isDirectory()) continue;
      for (const version of fs.readdirSync(path.join(meetings, stem)).sort()) {
        const dir = path.join(meetings, stem, version);
        if (!fs.existsSync(path.join(dir, 'raw.md'))) continue;
        add(path.join(dir, 'raw.md'), 'source', '会议原文');
        add(path.join(dir, 'corrections.json'), 'source', '会议纠偏留痕（读会必写，没有纠偏也写 []）');
        add(path.join(dir, 'evidence.md'), 'source', '会议纠偏后的阅读件（`story_flow.py meeting-refresh` 按纠偏生成）');
      }
    }
  }

  const flow = readJsonOrNull(path.join(src, 'story-flow.json'));
  // update 开着：这一轮动手前的现场与本轮说明也是对照材料，新稿改掉的旧约束对着它核
  const rid = flow?.update?.open;
  if (rid) {
    const base = path.join(src, 'updates', String(rid));
    add(path.join(base, 'update-notes.md'), 'source', '本轮 update 的变化、依据与不变项（作者的判断）', false);
    const before = path.join(base, 'before');
    const walk = dir => (fs.existsSync(dir) ? fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => (a.name < b.name ? -1 : 1))
      .flatMap(e => (e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)])) : []);
    const files = walk(before);
    if (!files.length) problems.push(`update ${rid} 的 before/ 不在或是空的——这一轮缺比较基准`);
    for (const f of files) add(f, 'source', `本轮 update 前的现场 ${path.relative(before, f).split(path.sep).join('/')}`);
  }
  // 设计采用的来源：与需求同根的蓝图，它的需求条目与设计依据引用的本需求材料版本逐份展开，字节按材料索引登记的摘要核
  const adopted = new Map();            // 采用文件（相对需求目录）→ {sha256, role}
  const conflicted = new Map();         // 冲突依据（没被采用的那一方）→ {sha256, role}
  const read = readBlueprint(projectRoot, feature, 'draft');
  if (read.status !== 'ok') {
    problems.push(`蓝图 ${feature} 读不到（原生读取 ${read.status}）`);
  } else {
    const found = adoptedSources(projectRoot, read.blueprint, { requirement: feature });
    const own = found.requirements[0];
    problems.push(...found.problems);
    if (!own?.versions.length) problems.push('蓝图的需求条目与设计依据没有引用本需求登记的材料');
    const local = f => f.path.slice(own.root.length + 1);
    for (const f of own?.files ?? []) adopted.set(local(f), { sha256: f.sha256.replace(/^sha256:/, ''), role: f.role });
    for (const f of own?.conflictFiles ?? []) conflicted.set(local(f), { sha256: f.sha256.replace(/^sha256:/, ''), role: f.role });
  }
  // 当前有效人答：独立必读，导出落后于流程记录时报缺口，不拿旧导出顶替
  const answers = requiredAnswers(requirementContext(projectRoot, root));
  problems.push(...answers.problems);
  // 材料清单登记的全部原件、阅读稿与图片：没采用的也在，审查要核作者为何排除它
  const set = materialSet({ srcDir: src });
  const manifest = path.join(src, 'materials.json');
  if (set === null) problems.push('AR/story-src/materials.json 不在——材料索引由 `story_flow.py round` 按磁盘现状生成');
  else {
    add(manifest, 'source', '材料清单（原件、阅读稿与图片的登记）', true, { kind: 'metadata', read: false });
    problems.push(...set.gaps);
    for (const p of set.pending) problems.push(`${p} 还在来源收件箱、没导入——先按来源导入规则导入，再准备审查`);
  }
  const at = r => path.join(root, ...String(r).split('/'));
  const bytesOf = abs => { try { return fs.readFileSync(abs); } catch { return null; } };
  // 采用文件的字节要等于材料索引登记的那一版：材料版本导入后不改，不在或字节不同报缺口，不拿同一来源的新版本顶替
  const checkAdopted = (r) => {
    const f = adopted.get(r);
    const bytes = bytesOf(at(r));
    if (f && !(bytes && sha256(bytes) === f.sha256)) {
      problems.push(`设计采用的 ${r}（${f.sha256.slice(0, 12)}）${bytes ? '字节已与登记的那一版不同' : '不在原处'}：这一版来源核不了`);
    }
  };
  for (const o of set?.origins ?? []) {
    const bytes = bytesOf(at(o.path));
    const want = String(o.sha256 ?? '').replace(/^sha256:/, '');
    if (bytes && want && !sha256(bytes).startsWith(want)) {
      problems.push(`原件 ${o.path} 现在的字节与材料清单登记的 ${o.sha256} 不同——登记的那一版不在原处：`
        + '把原件恢复成登记的那一版，或重跑 `story_flow.py round` 按磁盘现状登记后重新准备');
    }
    const readable = Array.isArray(o.readable_paths) ? o.readable_paths : [];
    const pictureOnly = Array.isArray(o.image_paths) && o.image_paths.length;
    if (pictureOnly || !readable.includes(o.path)) {
      // 二进制原件与只取图的原件：核在场与来源摘要，阅读义务在它的阅读稿与抽出的图上
      add(at(o.path), 'source', pictureOnly ? `只取图的原件 ${o.path}（核在场，图逐张在下面）` : `原件 ${o.path}（核在场与来源摘要，正文读它的阅读稿）`,
        true, { kind: 'metadata', read: false });
    }
    if (pictureOnly) continue;
    for (const r of readable) {
      checkAdopted(r);
      add(at(r), 'source', adopted.has(r) ? `设计采用的阅读稿 ${r}`
        : `设计未见引用的阅读稿 ${r}（核是有据不用，还是漏了依据）`, true, { kind: 'text' });
    }
  }
  // 设计采用的较早版本与会议纠偏/阅读件：材料清单只列各来源最新的一版原件与阅读稿，采用的那些在这里补齐
  const listed = r => rows.some(x => x.path === rel(at(r)));
  const META = new Set(['original', 'answer_record']);
  const LABEL = { original: '设计采用版本的原件', raw: '设计采用的会议原文', corrections: '设计采用的会议纠偏记录',
    evidence: '设计采用的会议阅读件', answer: '设计引用的人工答复', answer_record: '设计引用的人工答复记录', text: '设计采用的阅读稿' };
  for (const [r, f] of adopted) {
    if (f.role === 'image' || listed(r)) continue;
    checkAdopted(r);
    add(at(r), 'source', `${LABEL[f.role] ?? '设计采用的来源'} ${r}${META.has(f.role) ? '（核在场与来源摘要，正文读它的阅读稿）' : ''}`,
      true, META.has(f.role) ? { kind: 'metadata', read: false } : { kind: 'text' });
  }
  for (const [r, f] of conflicted) {
    if (f.role === 'image' || listed(r)) continue;
    add(at(r), 'source', `冲突依据 ${r}（蓝图登记的冲突一方，没有被采用；核取舍）`, true,
      META.has(f.role) ? { kind: 'metadata', read: false } : { kind: 'text' });
  }
  for (const f of answers.files) {
    add(path.join(projectRoot, ...f.path.split('/')), 'source',
      f.role === 'answer' ? '当前有效人答（必读：问法与原话）' : '当前有效人答的记录', true,
      f.role === 'answer' ? { kind: 'text' } : { kind: 'metadata', read: false });
  }
  // 图片按对象列，逐路径按字节认同一内容：同字节的落点是别名（第一个落点作规范路径），内容不同的落点各自核读
  for (const m of set?.images ?? []) {
    const unused = String(m.unused ?? '').trim();
    const label = `登记的图 ${m.caption || '（没写说明）'}${unused ? `，作者登记不用：${unused}` : ''}`;
    const groups = new Map();           // 内容摘要 → 这份内容的落点
    for (const r of m.paths) {
      const bytes = bytesOf(at(r));
      const digest = bytes ? sha256(bytes) : `missing:${r}`;
      if (!groups.has(digest)) groups.set(digest, []);
      groups.get(digest).push(r);
    }
    [...groups].forEach(([digest, paths], i) => {
      const canonical = rel(at(paths[0]));
      const apart = i ? '；与同条登记的其它落点内容不同，单独核读' : '';
      for (const r of paths) add(at(r), 'source', `${label}（${r}${apart}）`, true, { kind: 'image', canonical });
    });
  }
  for (const [r, f] of adopted) {
    if (f.role === 'image' && !listed(r)) {
      checkAdopted(r);
      add(at(r), 'source', `设计采用的图 ${r}`, true, { kind: 'image' });
    }
  }
  if (read.status === 'ok') {
    add(path.join(projectRoot, ...read.canonical_path.split('/')), 'source',
      `蓝图 r${read.blueprint_ref.revision}（${read.admitted ? '已准入' : '草稿，未准入'}）`);
    add(path.join(projectRoot, ...read.projection.path.split('/')), 'source', '蓝图的原生评审投影');
    for (const file of contractSources(read.blueprint)) {
      add(path.join(projectRoot, ...file.split('/')), 'source', `蓝图契约引用的接口转写或映射 ${file}`);
    }
  }

  const ext = extensionRoot(projectRoot);
  add(path.join(ext, 'manifest.yaml'), 'source', '知识激活清单');
  for (const r of knowledgeRegistrations(projectRoot)) add(path.join(ext, ...r.file.split('/')), 'source', `激活知识 ${r.file}`);
  add(path.join(ext, 'skills', 'story', 'contracts', 'story-chapters.json'), 'source', '章节合同');
  add(path.join(ext, 'rules', 'story-reader-rules.yaml'), 'source', '审查判据');
  return { rows, problems, alias,
    design: read.status === 'ok' ? { admitted: read.admitted === true, issues: read.issues ?? [] } : null };
}

/**
 * 材料键：对象里每份文件的项目相对路径与原始字节 SHA-256，按路径排序后的摘要。
 * 用来选这一次的报告目录、判重入；它不是原生请求的身份（那由原生 prepare 给出）。
 */
export function materialKey(projectRoot, rows) {
  const files = rows.map(r => [r.path, crypto.createHash('sha256')
    .update(fs.readFileSync(path.join(projectRoot, ...r.path.split('/')))).digest('hex')])
    .sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  return crypto.createHash('sha256').update(JSON.stringify(files)).digest('hex');
}
