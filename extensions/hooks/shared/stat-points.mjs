/**
 * 统计点 —— 设计里的埋点明细与 plan 的逐点落实，plan 门禁与审查共用这一份。
 *
 * 设计侧从施工单位的蓝图读：`story_details` 里 `kind: event`、依据落在本单位设计引用上的明细，正文里表头含「统计点」
 * 的表逐行是统计点。plan 侧从 plan.md 读：表头同时含「统计点」与「责任方法」的表，同一统计点可以有多行结果。
 * 只认这两个列名，不认任何知识文件名、渠道名、结果枚举或编码——那些只在项目知识里。
 */
import { parseDocument } from '../../skills/story/scripts/core/story/document.mjs';

const clean = (s) => String(s ?? '').replace(/[`*]/g, '').trim();
//: 「接口.方法」形态的引用：plan 表里责任方法这么写，契约里按 `interfaces.<接口>.<方法>` 找。
const METHOD_REF = /[A-Za-z_$][\w$]*\.[A-Za-z_$][\w$]*/g;

/** 统计点名比较用的形态：去空白与标记。 */
export const pointKey = (name) => clean(name).replace(/\s+/g, '');

/** 一段 Markdown 里表头含 `words` 全部列名的表：逐行 `{ cells, at }`，`at` 是各列名所在的列。 */
function tableRows(text, words) {
  const out = [];
  for (const t of parseDocument(String(text ?? '')).tables) {
    const at = words.map(w => t.header.findIndex(h => clean(h).includes(w)));
    if (at.some(i => i < 0)) continue;
    for (const r of t.rows) if (clean(r[at[0]])) out.push({ cells: r, at });
  }
  return out;
}

/**
 * 施工单位承接的统计设计：`{ state, why?, details: [{ id, title, rows }] }`。
 * state：`none` 没有蓝图（平铺维护 Feature）、`missing` 蓝图没有落在本单位的埋点明细、
 * `empty` 有明细而没有统计点表、`ready` 有统计点。`rows` 的第一格是统计点，其余格照原表。
 *
 * @param {{blueprint?: object, scope: Set<string>|null}} design `featureKnowledge` 的结果
 */
export function designStatPoints(design) {
  if (!design.blueprint) return { state: 'none', why: '没有蓝图，统计设计不从设计取', details: [] };
  const details = (design.blueprint.story_details ?? [])
    .filter(d => d?.kind === 'event' && (!design.scope || (d.evidence_refs ?? []).some(r => design.scope.has(r))))
    .map(d => ({ id: d.id, title: d.title ?? d.id,
      rows: tableRows(d.body, ['统计点']).map(({ cells, at }) => [cells[at[0]], ...cells.filter((_, i) => i !== at[0])]) }));
  if (!details.length) return { state: 'missing', why: `蓝图 ${design.blueprint.blueprint_id} 没有落在本施工单位的埋点明细`, details };
  return { state: details.some(d => d.rows.length) ? 'ready' : 'empty', details };
}

const list = (x) => (Array.isArray(x) ? x : []);

/**
 * 埋点在施工单位的落实处并列送到作者与审查者：蓝图的埋点明细、契约里承担它的方法说明、验收条目。
 * 没有 plan.md 时统计点、适用结果与验证方式就写在方法说明（`interfaces[].methods[].description`）与验收里；
 * 对不对得上由审查逐点判，这里只并列。没有落在本单位的埋点明细时为空。
 */
export function statDelivery(design, contracts, acceptance) {
  const want = designStatPoints(design);
  if (want.state === 'none' || want.state === 'missing') return [];
  const methods = list(contracts?.interfaces).flatMap(i => list(i?.methods).filter(m => String(m?.description ?? '').trim())
    .map(m => `- \`${i.name}.${m.name}\`：${String(m.description).trim()}`));
  const cases = [...list(acceptance?.criteria), ...list(acceptance?.boundaries)]
    .map(c => `- 验收 \`${c?.id}\`：${c?.description ?? c?.expected ?? c?.scenario ?? ''}`);
  return ['埋点明细（蓝图 story_details 里的 event，落在本施工单位）：',
    ...want.details.map(d => `- ${d.title}（${d.id}）：统计点 ${d.rows.map(r => clean(r[0])).join('、') || '（明细里没有统计点表）'}`),
    '承担统计点的契约方法说明（没有 plan.md 时，统计点、适用结果与验证方式写在这里）：',
    ...(methods.length ? methods : ['- （契约方法都没有说明）']),
    '验收条目：', ...(cases.length ? cases : ['- （没有验收条目）'])];
}

/** plan.md 里逐点落实的结果行：`[{ point, methods, cells }]`；plan.md 没有这样的表返回空数组。 */
export function planStatRows(planText) {
  return tableRows(planText, ['统计点', '责任方法']).map(({ cells, at }) => ({
    point: clean(cells[at[0]]), methods: clean(cells[at[1]]).match(METHOD_REF) ?? [], cells }));
}
