/**
 * 独立审查的对象 —— 这一次交给审查者的全部材料，只在这里定义一份。
 *
 * 审查任务列它、原生请求把它作为目标逐字节绑定、材料键由它算、覆盖声明与发现定位对着它核：几处用同一份，审的就是要交付的那一份。
 * 待审的是 Story、Review 与设计附件；其余是只读对照：写作设计、决策登记、会议记录（每版原文、纠偏留痕与阅读件）、
 * 交给设计的冻结输入（采用版本的原件、图、提取稿与人签）、材料清单登记的全部原件与阅读稿（含没采用的）和每个图片对象、
 * 当前蓝图与评审投影、蓝图契约引用的接口转写与映射、激活清单与知识原文、章节合同与判据。
 * 完整核源让审查能核作者为何采用或排除一份材料：作者的采用选择不缩小这个集合。
 * 流程契约、登记时刻、审查目录与历史报告不在其中：它们变了不改变被审内容。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { readBlueprint, readFrozenInputs } from '../../../../../hooks/shared/framework-access.mjs';
import { knowledgeRegistrations } from '../../../../../hooks/shared/knowledge.mjs';
import { extensionRoot, featureRoot, readJsonOrNull } from '../../../../../hooks/shared/paths.mjs';
import { materialSet } from './sources.mjs';

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
 * 材料清单本身），仍按字节绑定、进材料键。同一内容的几个路径（冻结副本与它的当前文件同字节、图片对象的几个落点）
 * 记进 `alias`：路径 → 规范路径（冻结副本优先），覆盖、发现定位与图面延期按它归一；内容不同的不互相顶替。
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
        add(path.join(dir, 'corrections.json'), 'source', '会议纠偏留痕', false);
        add(path.join(dir, 'evidence.md'), 'source', '会议纠偏后的阅读件', false);
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
  // 交给设计的冻结输入：采用的逻辑路径以冻结字节为设计权威，字节按快照登记的摘要核
  const frozen = new Map();             // 采用的逻辑路径（相对需求目录）→ {at: 冻结副本工程相对路径, sha256}
  const ref = flow?.input?.snapshot_ref;
  if (!ref) {
    problems.push('流程契约没有登记交给设计的输入');
  } else {
    const snapshotAbs = path.join(projectRoot, ...ref.split('/'));
    add(snapshotAbs, 'source', '交给设计的冻结输入快照');
    const read = fs.existsSync(snapshotAbs) ? readFrozenInputs(projectRoot, ref) : { snapshot: null, problems: [] };
    problems.push(...read.problems.map(p => `冻结输入：${p}`));
    for (const row of read.snapshot?.files ?? []) {
      const abs = path.join(path.dirname(snapshotAbs), 'files', ...String(row.path).split('/'));
      add(abs, 'source', `冻结输入里采用的 ${row.path}（${row.role}）`, true, { kind: row.role === 'image' ? 'image' : 'text' });
      frozen.set(String(row.path), { at: rel(abs), sha256: String(row.sha256) });
    }
  }
  // 材料清单登记的全部原件、阅读稿与图片：没采用的也在，审查要核作者为何排除它
  const set = materialSet({ srcDir: src });
  const manifest = path.join(src, 'materials.json');
  if (set === null) problems.push('AR/story-src/materials.json 不在——材料清单由 `story_flow.py round` 按磁盘现状生成');
  else {
    add(manifest, 'source', '材料清单（原件、阅读稿与图片的登记）', true, { kind: 'metadata', read: false });
    problems.push(...set.gaps);
    for (const p of set.pending) problems.push(`${p} 还没并入正文——先按 inbox 导入规则导入，再准备审查`);
  }
  const at = r => path.join(root, ...String(r).split('/'));
  const bytesOf = abs => { try { return fs.readFileSync(abs); } catch { return null; } };
  // 一份需求目录内的文件：采用过且字节与冻结版相同时是冻结副本的别名；不同就独立列作当前对照，不替代采用版
  const current = (r, label, kind) => {
    const f = frozen.get(r);
    const bytes = bytesOf(at(r));
    if (f && bytes && sha256(bytes) === f.sha256) add(at(r), 'source', `${label}（与冻结副本 ${f.at} 同字节）`, true, { kind, canonical: f.at });
    else if (f) add(at(r), 'source', `${label}：当前对照，与采用版不同，仅核取舍，不替代采用版 ${f.at}`, true, { kind });
    else add(at(r), 'source', label, true, { kind });
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
      current(r, frozen.has(r) ? `阅读稿 ${r}` : `没采用的阅读稿 ${r}（核作者为何没采用）`, 'text');
    }
  }
  for (const m of set?.images ?? []) {
    const f = m.paths.map(r => frozen.get(r)).find(x => x && sha256(bytesOf(at(m.paths[0])) ?? Buffer.alloc(0)) === x.sha256);
    const canonical = f?.at ?? rel(at(m.paths[0]));
    const unused = String(m.unused ?? '').trim();
    const label = `登记的图 ${m.caption || '（没写说明）'}${unused ? `，作者登记不用：${unused}` : ''}`;
    for (const r of m.paths) add(at(r), 'source', `${label}（${r}）`, true, { kind: 'image', canonical });
  }
  const blueprint = flow?.design_binding?.blueprint_id;
  const read = blueprint ? readBlueprint(projectRoot, blueprint, 'draft') : null;
  if (read?.status === 'ok') {
    add(path.join(projectRoot, ...read.canonical_path.split('/')), 'source',
      `蓝图 r${read.blueprint_ref.revision}（${read.admitted ? '已准入' : '草稿，未准入'}）`);
    add(path.join(projectRoot, ...read.projection.path.split('/')), 'source', '蓝图的原生评审投影');
    for (const file of contractSources(read.blueprint)) {
      add(path.join(projectRoot, ...file.split('/')), 'source', `蓝图契约引用的接口转写或映射 ${file}`);
    }
  } else {
    problems.push(`蓝图 ${blueprint ?? '（没有设计关联）'} 读不到（原生读取 ${read?.status ?? '未进行'}）`);
  }

  const ext = extensionRoot(projectRoot);
  add(path.join(ext, 'manifest.yaml'), 'source', '知识激活清单');
  for (const r of knowledgeRegistrations(projectRoot)) add(path.join(ext, ...r.file.split('/')), 'source', `激活知识 ${r.file}`);
  add(path.join(ext, 'skills', 'story', 'contracts', 'story-chapters.json'), 'source', '章节合同');
  add(path.join(ext, 'rules', 'story-reader-rules.yaml'), 'source', '审查判据');
  return { rows, problems, alias,
    design: read?.status === 'ok' ? { admitted: read.admitted === true, issues: read.issues ?? [] } : null };
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
