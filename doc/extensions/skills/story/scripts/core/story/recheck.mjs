/**
 * 回看清单 —— 十章齐后作者逐条处置的对象：脚本只枚举与定位，不判去向。
 *
 * 五类各有确定的来源：需求分析 ⑥ 来源初筛里「还要核实」那一格非空的行、决策登记的未决与已定、
 * 写作设计骨架里的 `待核：` 行、正文里每张图所在的节。作者对每一条问撞法两问，处置回它的真源；
 * 独立审查拿同一张清单核去向。不落台账：处置的痕迹就是真源里的改动。
 */
import * as path from 'node:path';
import { readJson, readText } from './context.mjs';
import { DIAGRAM_LANGS, headingEnd, parseChapter, parseDocument, storySections, tablesWithin } from './document.mjs';
import { decisionList } from './review.mjs';

const RECHECK_ASK = '先拿有效的原材料与当前决定核关键关系：条件、行为、责任、结果、例外与未决，在受影响的位置是不是一致；核的是当前的 spec.md、story.md（含附录投影区）、review.md 与 decisions.json，有会议材料时还有 doc-refresh.md 与它引的原话。'
  + '再用这张清单定位疑点——它帮你找问题，不是只审这几条：每一条问这句话材料里有吗、材料给的靠得住吗（拿它去撞更晚的输入、材料之间、工程事实、规约与材料自己声明的目标）；有问题回它的真源改，没问题不改，不写「已核对」';
//: 初筛表里「没有疑点」的写法：空着、一道横线，或写「无」。
const EMPTY_CELL = /^(?:[-—–]+|无)?$/;

/** 需求分析 ⑥ 节那张表里「还要核实」非空的行：`{where: 来源位置, doubt}`。 */
function screeningDoubts(text) {
  const doc = parseDocument(text);
  const at = doc.headings.find(h => h.level >= 2 && h.level <= 4 && h.raw.startsWith('⑥'));
  if (!at) return [];
  return tablesWithin(doc, at.at + 1, headingEnd(doc, at)).flatMap((t) => {
    const col = t.header.findIndex(c => c.includes('还要核实'));
    return col < 0 ? [] : t.rows.filter(r => !EMPTY_CELL.test(r[col] ?? ''))
      .map(r => ({ where: r[0], doubt: r[col] }));
  });
}

/** 正文里每张图所在的位置：`章` 或 `章·小节`。 */
function storyDiagrams(storyText) {
  return storySections(storyText).flatMap((sec) => {
    const view = parseChapter(sec.text);
    return view.fences.filter(f => DIAGRAM_LANGS.has(f.lang)).map((f) => {
      const at = view.sections.find(s => f.from > s.from && f.from < s.to);
      return at ? `${sec.title}·${at.name}` : sec.title;
    });
  });
}

/**
 * 清单条目 `{kind, where, text, hint}`。
 *
 * @param {object} ctx 需要 `srcDir`、`decisionsPath`
 * @param {object|null} plan `readWritingPlan` 的结果（取 `rechecks`）
 * @param {string} storyText 当前 story 全文
 */
export function recheckItems(ctx, plan, storyText) {
  const item = (kind, where, text, hint) => ({ kind, where, text, hint });
  const decisions = decisionList(readJson(ctx.decisionsPath, null)) ?? [];
  return [
    ...screeningDoubts(readText(path.join(ctx.srcDir, 'init-analysis.md')))
      .map(d => item('初筛疑点', d.where, d.doubt, '讲清、登记 open，或有依据地判不适用')),
    ...decisions.filter(d => d?.status !== 'settled')
      .map(d => item('未决', String(d?.id ?? '（无编号）'), String(d?.title ?? ''), '正文里依赖它的行为不能写成已定')),
    ...decisions.filter(d => d?.status === 'settled')
      .map(d => item('已定取舍', String(d?.id ?? '（无编号）'), String(d?.title ?? ''), '取舍落在哪一章，依据写了没有')),
    ...(plan?.rechecks ?? [])
      .map(r => item('骨架待核', r.at ? `${r.chapter}·${r.at}` : r.chapter, r.text, '在正文或决策登记里有去向')),
    ...storyDiagrams(storyText).map(where => item('图', where, '', '图前声称覆盖的去向，图里有没有')),
  ];
}

/** 清单的文本：先一句撞法两问，再逐条编号。 */
export function recheckRows(items) {
  return [`回看清单（${RECHECK_ASK}）：`,
    ...(items.length
      ? items.map((it, k) => `${k + 1}. [${it.kind}] ${it.where}${it.text ? `：${it.text}` : ''}——${it.hint}`)
      : ['（没有初筛疑点、决策登记、骨架待核与图，这一张是空的）'])];
}
