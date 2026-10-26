/**
 * 附录的读取器：蓝图的记录（原生读取所得）→ 某一节机器区的行。
 *
 * 机器区只投精确明细（配置、埋点）；接口、数据与规约由作者按蓝图写业务摘要，完整技术契约在设计附件。
 * 读取器把明细排成段，不补、不改写、不推断不适用；来历与核对字段不进正文。
 * 投影与核对共用这一份计算（`appendix.mjs` 调用）。
 */

/** 某一类精确明细（`story_details`）：标题、完整正文、依据。合同给了 `title_level` 的，标题出成那一级的小节，否则加粗。 */
function detailBlocks(blueprint, kind, level) {
  const out = [];
  for (const d of (blueprint.story_details ?? []).filter(x => x?.kind === kind)) {
    if (out.length) out.push('');
    out.push(level ? `${'#'.repeat(level)} ${d.title ?? d.id}` : `**${d.title ?? d.id}**`, '', ...String(d.body ?? '').trim().split(/\r?\n/),
      '', `（${d.id}；${(d.evidence_refs ?? []).join('、') || '—'}）`);
  }
  return out;
}

/** 每个读取器：`rows(source, def, where, gaps, ctx)`。 */
export const READERS = {
  details: { rows: (s, def) => detailBlocks(s.blueprint, def.detail_kind, def.title_level), source: '蓝图 story_details' },
};
