/**
 * 附录的读取器：一份已准入蓝图的记录（原生读取所得）→ 某一节机器区的行。
 *
 * 每个读取器把蓝图字段排成表或段，不补、不改写、不推断不适用。字段值是标量就照写；是对象时按章节合同为这一节
 * 登记的子字段标签写「标签：值」，合同没给人读写法的结构（没登记标签的子字段、更深一层的嵌套）报成投影缺口，
 * 交设计在蓝图里写成文字或写进精确明细（`story_details`），不摊平成键值串，也不静默略过。
 * 来历与核对字段（provenance、各类 refs、source_ref、摘要）不进正文。表头与标签由章节合同登记，本文件不写业务词。
 * 投影与核对共用这一份计算（`appendix.mjs` 调用）。
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
  ctx.gaps.push(`附录「${ctx.where}」：蓝图 ${field} 没有人读写法`
    + '（章节合同没登记它的标签，或它是更深一层的结构）——由设计在蓝图里写成文字，或把它的人读说明写进精确明细 story_details；'
    + '附录不摊平、也不略过');
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

/** 「编码 → 含义」这类条目（错误、非功能要求）：键是业务编码，值写成文字；值是结构的报缺口。 */
function entries(items, ctx, field) {
  if (items === null || items === undefined || Array.isArray(items) || scalar(items)) return readable({}, items, ctx, field);
  return Object.entries(items).map(([k, v]) => (scalar(v) ? `${k}：${v ?? ''}` : gapAt(ctx, `${field}.${k}`)))
    .filter(Boolean).join('；');
}

/** 契约语义段（errors / idempotency / nfr）里读的那一个字段；段里还有别的业务字段就报缺口。 */
function sectionField(section, key, ctx, field) {
  for (const k of Object.keys(section ?? {})) if (k !== key && !TRACE_KEYS.has(k)) gapAt(ctx, `${field}.${k}`);
  return section?.[key];
}

/** 端云接口：每个契约的 operation、请求与响应字段、字段映射，以及错误语义、幂等与非功能要求。 */
function contractRows(blueprint, def, ctx) {
  const out = [];
  for (const c of blueprint.contracts ?? []) {
    const op = c.operation ?? {};
    const at = `contracts.${c.contract_id}`;
    if (out.length) out.push('');
    out.push(`**${c.contract_id}**：${op.operation_id ?? '—'}（${op.direction ?? '—'}，${label(def, 'version')} ${op.version ?? '—'}）`);
    const fields = [['request', c.request_dto], ['response', c.response_dto]].flatMap(([side, dto]) =>
      (dto?.fields ?? []).map(f => [`${label(def, side)} ${dto.dto_id ?? ''}`.trim(), f.field_id ?? f.name,
        readable(def, f.type, ctx, `${at}.${side}_dto.${f.field_id ?? f.name}.type`),
        readable(def, f.semantics, ctx, `${at}.${side}_dto.${f.field_id ?? f.name}.semantics`),
        f.nullable === true ? label(def, 'nullable') : label(def, 'required')].map(cell)));
    if (fields.length) out.push('', ...renderTable(header(def, 'fields', ctx.where), fields));
    const maps = (c.mappings ?? []).map(m => [m.mapping_id, m.target_field, m.kind ?? 'direct',
      readable(def, m.source_fields, ctx, `${at}.mappings.${m.mapping_id}.source_fields`),
      readable(def, m.rule, ctx, `${at}.mappings.${m.mapping_id}.rule`)].map(cell));
    if (maps.length) out.push('', ...renderTable(header(def, 'mappings', ctx.where), maps));
    const semantics = { errors: entries(sectionField(c.errors, 'items', ctx, `${at}.errors`), ctx, `${at}.errors.items`),
      idempotency: readable(def, sectionField(c.idempotency, 'rule', ctx, `${at}.idempotency`), ctx, `${at}.idempotency.rule`),
      nfr: entries(sectionField(c.nfr, 'requirements', ctx, `${at}.nfr`), ctx, `${at}.nfr.requirements`) };
    out.push('', ...Object.entries(semantics).map(([k, v]) => `- ${label(def, k)}：${v || '—'}`));
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
function dataRows(blueprint, def, ctx) {
  const runtime = (blueprint.design_views ?? []).find(v => v?.view_id === 'runtime');
  const rows = (runtime?.runtime_data_flows ?? []).map((f) => {
    const at = `runtime_data_flows.${f.flow_id}`;
    return [f.flow_id, readable(def, f.data_domain_refs, ctx, `${at}.data_domain_refs`),
      ...['source_of_truth', 'state_owner', 'failure_recovery'].map(k => readable(def, f[k], ctx, `${at}.${k}`))].map(cell);
  });
  const out = rows.length ? renderTable(header(def, 'flows', ctx.where), rows) : [];
  const details = detailBlocks(blueprint, def.detail_kind);
  return details.length ? [...out, ...(out.length ? [''] : []), ...details] : out;
}

/** 规约：蓝图里的知识应用决定，逐条写知识单元、判定、要求与理由（豁免带补偿）、落点。 */
function knowledgeRows(blueprint, def, ctx) {
  const rows = (blueprint.decisions_and_gaps?.decisions ?? []).filter(d => d?.kind === 'knowledge_application')
    .map((d) => {
      const k = d.knowledge ?? {};
      const waiver = k.waiver && `豁免：${k.waiver.reason}；补偿：${k.waiver.compensation}`;
      return [k.unit, k.outcome, [k.requirement, d.rationale, waiver].filter(Boolean).join('；'),
        (k.target_refs ?? []).join('、') || '—'].map(cell);
    });
  return rows.length ? renderTable(header(def, 'rows', ctx.where), rows) : [];
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

/** 每个读取器：`rows(source, def, where, gaps)`，没有人读写法的结构记进 `gaps`。 */
export const READERS = {
  contracts: { rows: (s, def, where, gaps) => contractRows(s.blueprint, def, { where, gaps }), source: '蓝图 contracts' },
  data_flows: { rows: (s, def, where, gaps) => dataRows(s.blueprint, def, { where, gaps }), source: '蓝图运行视图与数据策略明细' },
  details: { rows: (s, def) => detailBlocks(s.blueprint, def.detail_kind), source: '蓝图 story_details' },
  knowledge_applications: { rows: (s, def, where, gaps) => knowledgeRows(s.blueprint, def, { where, gaps }), source: '蓝图知识应用决定' },
  change_boundary: { rows: (s, def, where, gaps) => boundaryRows(s.blueprint, def, { where, gaps }), source: '蓝图开发视图与架构影响决定' },
};

