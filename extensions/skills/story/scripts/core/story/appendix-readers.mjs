/**
 * 附录的读取器：已准入蓝图的记录（原生读取所得）或登记的冻结输入 → 某一节机器区的行。
 *
 * 机器区只投精确明细（配置、埋点）、改动边界与本次冻结材料；接口、数据与规约由作者按蓝图写业务摘要，
 * 完整技术契约在设计附件。每个读取器把字段排成表或段，不补、不改写、不推断不适用。字段值是标量就照写；是对象时按章节合同为这一节
 * 登记的子字段标签写「标签：值」，合同没给人读写法的结构报成投影适配缺口：
 * 蓝图保持原样，由扩展维护者按实际结构在章节合同补人读写法。
 * 来历与核对字段（provenance、各类 refs、source_ref、摘要）不进正文。表头与标签由章节合同登记，本文件不写业务词。
 * 投影与核对共用这一份计算（`appendix.mjs` 调用）。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { renderTable } from './chapter-contract.mjs';
import { fail } from './context.mjs';

/** 登记在合同里的表头；读取器要的表没登记是合同坏了，照实停下。 */
function header(def, key, where) {
  const text = def.tables?.[key];
  if (!text) fail(`章节合同附录章 projection：「${where}」缺 tables.${key} 表头，Story Extension 的章节合同不完整：停下，交 Story Extension 维护者补表头`);
  return String(text).split('|').map(h => h.trim());
}

const label = (def, key) => def.labels?.[key] ?? key;

//: 来历与核对字段：仓内路径、核对记号与摘要，归档件的读者手上没有这个仓
const TRACE_KEYS = new Set(['provenance', 'verification_refs', 'evidence_refs', 'source_ref', 'source_sha256']);

/** 表格单元：管道符转义、换行并成一行，空值写破折号。 */
function cell(text) {
  return String(text ?? '').replace(/\|/g, '\\|').replace(/\s*\r?\n\s*/g, ' ') || '—';
}

const scalar = v => v === null || typeof v !== 'object';

/**
 * 一个字段的人读文字。标量照写，标量数组用顿号连；对象按合同标签逐个子字段写「标签：值」。
 * 合同没给写法的结构记进 `gaps`（`where` 与 `field` 指明位置），这一处不写。
 */
function gapAt(ctx, field) {
  ctx.gaps.push(`附录「${ctx.where}」投影适配缺口：蓝图 ${field} 是 Story Extension 章节合同还没有人读写法的结构`
    + '（子字段没登记标签，或是更深一层的嵌套）。蓝图保持原样；这条交 Story Extension 维护者在章节合同补人读写法，'
    + '补上之前附录投影与核对停在这里');
  return '';
}

function readable(def, value, ctx, field) {
  if (value === null || value === undefined) return '';
  if (scalar(value)) return String(value);
  const gap = name => gapAt(ctx, `${field}${name ? `.${name}` : ''}`);
  if (Array.isArray(value)) return value.every(scalar) ? value.filter(v => v !== null).map(String).join('、') : gap('');
  return Object.entries(value).filter(([k]) => !TRACE_KEYS.has(k)).map(([k, v]) => {
    if (!def.labels?.[k] || !(scalar(v) || (Array.isArray(v) && v.every(scalar)))) return gap(k);
    const text = readable(def, v, ctx, `${field}.${k}`);
    return text ? `${def.labels[k]}：${text}` : '';
  }).filter(Boolean).join('；');
}

/** 某一类精确明细（`story_details`）：标题、完整正文逐字、依据。 */
function detailBlocks(blueprint, kind) {
  const out = [];
  for (const d of (blueprint.story_details ?? []).filter(x => x?.kind === kind)) {
    if (out.length) out.push('');
    out.push(`**${d.title ?? d.id}**`, '', ...String(d.body ?? '').trim().split(/\r?\n/),
      '', `（${d.id}；${(d.evidence_refs ?? []).join('、') || '—'}）`);
  }
  return out;
}

/** 改动边界：开发视图里每个节点动到的模块，与改模块、依赖边的架构影响决定。 */
function boundaryRows(blueprint, def, ctx) {
  const dev = (blueprint.design_views ?? []).find(v => v?.view_id === 'development');
  const rows = [];
  if (dev?.evolution_impact === 'verified_unchanged' || dev?.applicability === 'not_applicable') {
    rows.push([label(def, 'unchanged'), readable(def, dev.purpose, ctx, 'design_views.development.purpose')].map(cell));
  }
  for (const n of dev?.nodes ?? []) {
    const at = `design_views.development.nodes.${n.node_id}`;
    rows.push([n.module ?? n.node_id, `${readable(def, n.current_state, ctx, `${at}.current_state`) || '—'} → `
      + `${readable(def, n.target_state, ctx, `${at}.target_state`) || '—'}`].map(cell));
  }
  for (const d of (blueprint.decisions_and_gaps?.decisions ?? []).filter(x => x?.change)) {
    const what = d.module ?? [d.from, d.to].filter(Boolean).join(' → ');
    rows.push([what, [d.change, d.direction, d.rationale].filter(Boolean).join('：')].map(cell));
  }
  return rows.length ? renderTable(header(def, 'rows', ctx.where), rows) : [];
}

/**
 * 本次冻结材料：当前冻结快照里的每份文件，按路径排序一行——来源文件（链接指向快照里的那一份）、材料角色、
 * 本次版本（原始字节摘要前 16 位与快照目录）。写前逐份核原始字节与快照登记的摘要，对不上记进 `gaps`，这一次不投。
 */
function materialRows(source, def, ctx) {
  const snapshot = source.snapshot;
  if (!snapshot) return [];
  const version = path.basename(snapshot.dir);
  const from = path.dirname(ctx.storyPath);
  const rows = [...(snapshot.files ?? [])].sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0)).map((row) => {
    const file = path.join(snapshot.dir, 'files', ...String(row.path).split('/'));
    let bytes = null;
    try { bytes = fs.readFileSync(file); } catch { bytes = null; }
    if (bytes === null || crypto.createHash('sha256').update(bytes).digest('hex') !== row.sha256) {
      ctx.gaps.push(`附录「${ctx.where}」：冻结输入里的 ${row.path} ${bytes === null ? '读不到' : '原始字节与快照登记的摘要对不上'}`
        + '——冻结版本不改；恢复这份文件，恢复不了先 `story_flow.py reopen` 或开一轮 update，再重新 complete');
    }
    const link = path.relative(from, file).split(path.sep).join('/');
    return [`[${row.path}](${link})`, def.roles?.[row.role] ?? row.role, `${String(row.sha256).slice(0, 16)}（${version}）`].map(cell);
  });
  return rows.length ? renderTable(header(def, 'rows', ctx.where), rows) : [];
}

/** 每个读取器：`rows(source, def, where, gaps, ctx)`，没有人读写法的结构与读不到的输入记进 `gaps`。 */
export const READERS = {
  details: { rows: (s, def) => detailBlocks(s.blueprint, def.detail_kind), source: '蓝图 story_details' },
  change_boundary: { rows: (s, def, where, gaps) => boundaryRows(s.blueprint, def, { where, gaps }), source: '蓝图开发视图与架构影响决定' },
  materials: { rows: (s, def, where, gaps, ctx) => materialRows(s, def, { where, gaps, storyPath: ctx.storyPath }), source: '登记的冻结输入' },
};

