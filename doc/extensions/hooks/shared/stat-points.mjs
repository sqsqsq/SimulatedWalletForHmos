/**
 * 统计点 —— spec「埋点」一节与 plan「埋点」小节的读取，任务包、门禁与审查共用这一份。
 *
 * 只认模板结构：spec 的埋点一节下每个 `####` 是一个指标，表的第一列是统计点名；plan 的埋点小节里
 * 表头含「统计点」的那一列是统计点、含「责任方法」的那一列是它的责任方法。
 * 不认任何知识文件名、渠道名、结果枚举或编码——那些只在项目知识里。
 */
import { headingEnd, parseDocument, tablesWithin } from '../../skills/story/scripts/core/story/document.mjs';

const NA = /^(本需求)?不涉及[:：]?\s*\S/;
const clean = (s) => String(s ?? '').replace(/[`*]/g, '').trim();
//: 「接口.方法」形态的引用：plan 表里责任方法这么写，契约里按 `interfaces.<接口>.<方法>` 找。
const METHOD_REF = /[A-Za-z_$][\w$]*\.[A-Za-z_$][\w$]*/g;

/** 某一级标题名含「埋点」的那一节：`{ doc, from, to }`；没有返回 null。 */
function section(text, level) {
  const doc = parseDocument(String(text ?? ''));
  const h = doc.headings.find(x => x.level === level && /埋点/.test(x.raw));
  return h ? { doc, h, from: h.at + 1, to: headingEnd(doc, h) } : null;
}

/** 一节正文里写出来的「不涉及：<依据>」（写在任何小标题之前）；没有返回 null。 */
function notApplicable(doc, from, to) {
  for (let i = from; i < to; i += 1) {
    const l = doc.lines[i].trim();
    if (!l || l.startsWith('<!--')) continue;
    return NA.test(l) ? l : null;
  }
  return null;
}

/**
 * spec 的埋点一节：`{ na, text, groups: [{ title, points, rows }] }`，没有这一节返回 null。
 * `text` 是这一节的原文（给任务包与审查照列），`points` 是各指标表第一列的统计点名，`rows` 是对应的整行。
 */
export function specStatPoints(specText) {
  const s = section(specText, 3);
  if (!s) return null;
  const { doc, from, to } = s;
  const h4s = doc.headings.filter(x => x.level === 4 && x.at > s.h.at && x.at < to);
  const groups = h4s.map((h, k) => {
    const end = h4s[k + 1]?.at ?? to;
    const rows = tablesWithin(doc, h.at + 1, end).flatMap(t => t.rows).filter(r => clean(r[0]));
    return { title: h.raw, points: rows.map(r => clean(r[0])), rows };
  });
  return { na: notApplicable(doc, from, to), text: doc.lines.slice(s.h.at, to).join('\n'), groups };
}

/**
 * plan 的埋点小节：`{ na, rows: [{ point, methods, cells }] }`，没有这一节返回 null。
 * 小节可以是 `###` 或 `####`（挂在服务层接口定义章下）。
 */
export function planStatRows(planText) {
  const s = section(planText, 3) ?? section(planText, 4);
  if (!s) return null;
  const { doc, from, to } = s;
  const rows = [];
  for (const t of tablesWithin(doc, from, to)) {
    const at = (word) => t.header.findIndex(h => clean(h).includes(word));
    const [p, m] = [at('统计点'), at('责任方法')];
    if (p < 0) continue;
    for (const r of t.rows) {
      const point = clean(r[p]);
      if (point) rows.push({ point, methods: m < 0 ? [] : clean(r[m]).match(METHOD_REF) ?? [], cells: r });
    }
  }
  return { na: notApplicable(doc, from, to), rows };
}

/** 统计点名比较用的形态：去空白与标记。 */
export const pointKey = (name) => clean(name).replace(/\s+/g, '');
