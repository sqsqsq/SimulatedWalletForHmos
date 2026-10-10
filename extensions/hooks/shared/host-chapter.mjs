/**
 * 宿主扩展章 —— Framework 模板留给扩展的锚点章（spec「宿主扩展治理项」、plan「宿主扩展（可选）」），
 * 作者在这里讲本单位怎样落实设计里的知识判断。只在本次确有 spec.md / plan.md 时核，只核结构与引用：
 * 这一章在；本单位承接的那几类各有小节；规约小节表里写到的编号是设计判断过的单元；引用的验收编号在 acceptance.yaml 里有；
 * plan 的逐点表在「埋点」小节里。讲得对不对、够不够归独立审查。
 */
import { parseDocument } from '../../skills/story/scripts/core/story/document.mjs';
import { acceptanceIdRe, acceptanceIds } from './contracts.mjs';
import { unitDuties } from './knowledge-application.mjs';

//: 规约单元编号的形态（域前缀-序号），只在规约小节表格的第一列认
const RULE_ID = /\b[A-Z][A-Z0-9]*-\d+\b/g;
const POINT_TABLE = ['统计点', '责任方法'];

/**
 * 本单位承接适用规约、选中模式（plan 还有落在本单位的埋点明细）时要有讲它的小节，按小节名含「规约」「设计模式」「埋点」认。
 *
 * @param {string} text spec.md / plan.md 全文
 * @param {{file: string, anchor: string, judged: object, acceptance?: object|null, events?: boolean|null}} o
 *   `judged` 是 `featureKnowledge` 的结果；`events` 只有 plan 给（是否承接埋点明细），给了就核逐点表的位置
 * @returns {string[]}
 */
export function hostChapterProblems(text, { file, anchor, judged, acceptance = null, events = null }) {
  const { applied, selected } = unitDuties(judged);
  const units = new Set(judged.rows.filter(d => d.knowledge.kind === 'constraints').map(d => d.knowledge.unit));
  const need = [...(applied.length ? ['规约'] : []), ...(selected.length ? ['设计模式'] : []), ...(events ? ['埋点'] : [])];
  const doc = parseDocument(text);
  const head = doc.headings.find(h => h.level === 2 && h.name === anchor);
  if (!head) {
    return [`${file}：没有「${anchor}」章——它是 Framework 模板留给扩展的锚点，本单位怎样落实设计里的知识判断写在这一章`];
  }
  const end = doc.headings.find(h => h.level <= 2 && h.at > head.at)?.at ?? doc.lines.length;
  const subs = doc.headings.filter(h => h.level === 3 && h.at > head.at && h.at < end)
    .map((h, i, all) => ({ name: h.name, from: h.at, to: all[i + 1]?.at ?? end }));
  const within = (line, s) => Boolean(s) && line > s.from && line < s.to;
  const problems = need.filter(n => !subs.some(s => s.name.includes(n)))
    .map(n => `${file}「${anchor}」：本单位承接${n}，这一章下没有讲它的小节——小节名含「${n}」，逐项写本单位怎样落实`);
  for (const s of subs.filter(x => x.name.includes('规约'))) {
    const ids = doc.tables.filter(t => within(t.line, s)).flatMap(t => t.rows.flatMap(r => String(r[0] ?? '').match(RULE_ID) ?? []));
    for (const id of new Set(ids.filter(x => !units.has(x)))) {
      problems.push(`${file}「${anchor}·${s.name}」：${id} 不是设计判断过的规约——编号取设计里知识应用判断的单元`);
    }
  }
  if (acceptance) {
    const ids = acceptanceIds(acceptance);
    const cited = doc.lines.slice(head.at, end).join('\n').match(acceptanceIdRe()) ?? [];
    for (const id of new Set(cited.filter(x => !ids.has(x)))) {
      problems.push(`${file}「${anchor}」：引用的验收 ${id} 在 acceptance.yaml 里没有`);
    }
  }
  if (events !== null) {
    const home = subs.find(s => s.name.includes('埋点'));
    for (const t of doc.tables.filter(x => POINT_TABLE.every(w => x.header.some(h => h.includes(w)))).filter(x => !within(x.line, home))) {
      problems.push(`${file}：第 ${t.line + 1} 行的逐点表不在「${anchor}」的「埋点」小节里——埋点按指标在宿主扩展章落实`);
    }
  }
  return problems;
}
