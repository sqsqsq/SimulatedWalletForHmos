/**
 * 独立审查的对象 —— 这一次交给审查者的全部材料，只在这里定义一份。
 *
 * 审查任务列它、原生请求把它作为目标逐字节绑定、材料键由它算：三处用同一份，审的就是要交付的那一份。
 * 待审的是 Story 与 Review；其余是只读对照：写作设计、决策登记、会议记录、交给设计的冻结输入（采用版本的原件、
 * 图、提取稿与人签）、已准入蓝图与评审投影、蓝图契约引用的接口转写与映射、激活清单与知识原文、章节合同与判据。
 * 流程契约、登记时刻、审查目录与历史报告不在其中：它们变了不改变被审内容。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { readBlueprint } from '../../../../../hooks/shared/framework-access.mjs';
import { knowledgeRegistrations } from '../../../../../hooks/shared/knowledge.mjs';
import { extensionRoot, featureRoot, readJsonOrNull } from '../../../../../hooks/shared/paths.mjs';

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
 * @returns {{rows: {path: string, role: 'object'|'source', label: string}[], problems: string[]}}
 *   路径相对工程根；缺了该有的材料写进 problems，不当作没有。
 */
export function reviewObject(projectRoot, feature, { withTask = true } = {}) {
  const root = featureRoot(projectRoot, feature);
  const rel = abs => path.relative(projectRoot, abs).split(path.sep).join('/');
  const rows = [];
  const problems = [];
  const add = (abs, role, label, required = true) => {
    if (fs.existsSync(abs) && fs.statSync(abs).isFile()) rows.push({ path: rel(abs), role, label });
    else if (required) problems.push(`${rel(abs)} 读不到（${label}）`);
  };
  const src = path.join(root, 'AR', 'story-src');
  add(path.join(root, 'AR', 'story.md'), 'object', '待审的 Story');
  add(path.join(root, 'AR', 'review.md'), 'object', '待审的决策与评审记录（机器区与人工区）');
  if (withTask) add(path.join(root, ...TASK), 'source', '审查任务');
  add(path.join(src, 'story-template.md'), 'source', '作者的写作设计（待核的作者判断）');
  add(path.join(src, 'decisions.json'), 'source', '决策登记');
  for (const name of ['doc-refresh.md', 'template-adjustments.md', 'meeting-notes.json']) {
    add(path.join(src, name), 'source', name === 'doc-refresh.md' ? '会议之后的当前结果'
      : name === 'meeting-notes.json' ? '会议判断' : '写作设计的调整记录', false);
  }
  const meetings = path.join(src, 'meetings');
  if (fs.existsSync(meetings)) {
    for (const stem of fs.readdirSync(meetings).sort()) {
      for (const version of fs.readdirSync(path.join(meetings, stem)).sort()) {
        add(path.join(meetings, stem, version, 'raw.md'), 'source', '会议原文', false);
      }
    }
  }

  const flow = readJsonOrNull(path.join(src, 'story-flow.json'));
  const ref = flow?.input?.snapshot_ref;
  if (!ref) {
    problems.push('流程契约没有登记交给设计的输入');
  } else {
    const snapshotAbs = path.join(projectRoot, ...ref.split('/'));
    add(snapshotAbs, 'source', '交给设计的冻结输入快照');
    const snapshot = readJsonOrNull(snapshotAbs);
    for (const row of snapshot?.files ?? []) {
      add(path.join(path.dirname(snapshotAbs), 'files', ...String(row.path).split('/')), 'source',
        `冻结输入里采用的 ${row.path}（${row.role}）`);
    }
  }
  const blueprint = flow?.design_binding?.blueprint_id;
  const read = blueprint ? readBlueprint(projectRoot, blueprint, 'delivery') : null;
  if (read?.status === 'ok') {
    add(path.join(projectRoot, ...read.canonical_path.split('/')), 'source', `已准入的蓝图 r${read.blueprint_ref.revision}`);
    add(path.join(projectRoot, ...read.projection.path.split('/')), 'source', '蓝图的原生评审投影');
    for (const file of contractSources(read.blueprint)) {
      add(path.join(projectRoot, ...file.split('/')), 'source', `蓝图契约引用的接口转写或映射 ${file}`);
    }
  } else {
    problems.push(`蓝图 ${blueprint ?? '（没有设计关联）'} 读不到或未准入`);
  }

  const ext = extensionRoot(projectRoot);
  add(path.join(ext, 'manifest.yaml'), 'source', '知识激活清单');
  for (const r of knowledgeRegistrations(projectRoot)) add(path.join(ext, ...r.file.split('/')), 'source', `激活知识 ${r.file}`);
  add(path.join(ext, 'skills', 'story', 'contracts', 'story-chapters.json'), 'source', '章节合同');
  add(path.join(ext, 'rules', 'story-reader-rules.yaml'), 'source', '审查判据');
  const seen = new Set();
  return { rows: rows.filter(r => !seen.has(r.path) && seen.add(r.path)), problems };
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
