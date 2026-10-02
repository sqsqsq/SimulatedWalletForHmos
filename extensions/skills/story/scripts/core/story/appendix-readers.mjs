/**
 * 附录的读取器：一份已准入蓝图的记录（原生读取所得）→ 某一节机器区的行。
 *
 * 每个读取器只把原生对象的字段原样排成表或段，不补、不改写、不推断不适用；表头与文字标签由章节合同登记，
 * 本文件不写业务词。投影与核对共用这一份计算（`appendix.mjs` 调用）。
 */
import { renderTable } from './chapter-contract.mjs';
import { fail } from './context.mjs';

/** 登记在合同里的表头；读取器要的表没登记是合同坏了，照实停下。 */
function header(def, key, where) {
  const text = def.tables?.[key];
  if (!text) fail(`章节合同附录章 projection：「${where}」没登记 tables.${key} 表头——脚本合成的附录表按合同登记的表头出，脚本不留字面`);
  return String(text).split('|').map(h => h.trim());
}

const label = (def, key) => def.labels?.[key] ?? key;

/** 表格单元：管道符转义、换行并成一行，空值写破折号。 */
function cell(value) {
  const text = describe(value).replace(/\|/g, '\\|').replace(/\s*\r?\n\s*/g, ' ');
  return text || '—';
}

//: 原生对象里描述来历的字段不进正文：它们是仓内路径与核对记号，归档件的读者手上没有这个仓
const TRACE_KEYS = new Set(['provenance', 'verification_refs', 'evidence_refs', 'source_ref', 'source_sha256']);

/** 原生字段的值原样写出：对象按字段逐一写、数组逐项写。 */
function describe(value) {
  if (value === null || value === undefined || value === '') return '';
  if (typeof value !== 'object') return String(value);
  if (Array.isArray(value)) return value.map(describe).filter(Boolean).join('；');
  const parts = Object.entries(value).filter(([k]) => !TRACE_KEYS.has(k)).map(([k, v]) => `${k}：${describe(v)}`);
  return parts.join('；');
}

/** 端云接口：每个契约的 operation、请求与响应字段、字段映射，以及错误语义、幂等与非功能要求。 */
function contractRows(blueprint, def, where) {
  const out = [];
  for (const c of blueprint.contracts ?? []) {
    const op = c.operation ?? {};
    if (out.length) out.push('');
    out.push(`**${c.contract_id}**：${op.operation_id ?? '—'}（${op.direction ?? '—'}，${label(def, 'version')} ${op.version ?? '—'}）`);
    const fields = [['request', c.request_dto], ['response', c.response_dto]].flatMap(([side, dto]) =>
      (dto?.fields ?? []).map(f => [`${label(def, side)} ${dto.dto_id ?? ''}`.trim(), f.field_id ?? f.name, f.type,
        f.semantics, f.nullable === true ? label(def, 'nullable') : label(def, 'required')].map(cell)));
    if (fields.length) out.push('', ...renderTable(header(def, 'fields', where), fields));
    const maps = (c.mappings ?? []).map(m => [m.mapping_id, m.target_field, m.kind ?? 'direct',
      (m.source_fields ?? []).join('、'), m.rule].map(cell));
    if (maps.length) out.push('', ...renderTable(header(def, 'mappings', where), maps));
    out.push('', ...['errors', 'idempotency', 'nfr'].map(k => `- ${label(def, k)}：${describe(c[k]) || '—'}`));
  }
  return out;
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

/** 数据存储：运行视图里每条数据流的数据域、权威来源、状态归属与失败恢复，加数据策略类精确明细。 */
function dataRows(blueprint, def, where) {
  const runtime = (blueprint.design_views ?? []).find(v => v?.view_id === 'runtime');
  const rows = (runtime?.runtime_data_flows ?? []).map(f => [f.flow_id, f.data_domain_refs, f.source_of_truth,
    f.state_owner, f.failure_recovery].map(cell));
  const out = rows.length ? renderTable(header(def, 'flows', where), rows) : [];
  const details = detailBlocks(blueprint, def.detail_kind);
  return details.length ? [...out, ...(out.length ? [''] : []), ...details] : out;
}

/** 规约：蓝图里的知识应用决定，逐条写知识单元、判定、要求与理由（豁免带补偿）、落点。 */
function knowledgeRows(blueprint, def, where) {
  const rows = (blueprint.decisions_and_gaps?.decisions ?? []).filter(d => d?.kind === 'knowledge_application')
    .map((d) => {
      const k = d.knowledge ?? {};
      const waiver = k.waiver && `豁免：${k.waiver.reason}；补偿：${k.waiver.compensation}`;
      return [k.unit, k.outcome, [k.requirement, d.rationale, waiver].filter(Boolean).join('；'),
        (k.target_refs ?? []).join('、') || '—'].map(cell);
    });
  return rows.length ? renderTable(header(def, 'rows', where), rows) : [];
}

/** 改动边界：开发视图里每个节点动到的模块，与改模块、依赖边的架构影响决定。 */
function boundaryRows(blueprint, def, where) {
  const dev = (blueprint.design_views ?? []).find(v => v?.view_id === 'development');
  const rows = [];
  if (dev?.evolution_impact === 'verified_unchanged' || dev?.applicability === 'not_applicable') {
    rows.push([label(def, 'unchanged'), describe(dev.unchanged_evidence ?? dev.purpose)].map(cell));
  }
  for (const n of dev?.nodes ?? []) {
    rows.push([n.module ?? n.node_id, `${describe(n.current_state) || '—'} → ${describe(n.target_state) || '—'}`].map(cell));
  }
  for (const d of (blueprint.decisions_and_gaps?.decisions ?? []).filter(x => x?.change)) {
    const what = d.module ?? [d.from, d.to].filter(Boolean).join(' → ');
    rows.push([what, [d.change, d.direction, d.rationale].filter(Boolean).join('：')].map(cell));
  }
  return rows.length ? renderTable(header(def, 'rows', where), rows) : [];
}

export const READERS = {
  contracts: { rows: (s, def, where) => contractRows(s.blueprint, def, where), source: '蓝图 contracts' },
  data_flows: { rows: (s, def, where) => dataRows(s.blueprint, def, where), source: '蓝图运行视图与数据策略明细' },
  details: { rows: (s, def) => detailBlocks(s.blueprint, def.detail_kind), source: '蓝图 story_details' },
  knowledge_applications: { rows: (s, def, where) => knowledgeRows(s.blueprint, def, where), source: '蓝图知识应用决定' },
  change_boundary: { rows: (s, def, where) => boundaryRows(s.blueprint, def, where), source: '蓝图开发视图与架构影响决定' },
};

