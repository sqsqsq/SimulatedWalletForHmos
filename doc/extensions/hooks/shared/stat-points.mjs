/**
 * 统计点 —— spec「埋点」一节与 plan「埋点」小节的读取，任务包、门禁与审查共用这一份。
 *
 * 只认模板结构，层级由找到的父标题推出：spec 的埋点是「技术契约」的下一级小节，其下一级的每个标题是一个指标，
 * 表头含「统计点」的表是它的点位表；plan 的埋点是「宿主扩展」的下一级小节，表头含「统计点」的那一列是统计点、
 * 含「责任方法」的那一列是它的责任方法，同一统计点可以有多行结果。
 * 不认任何知识文件名、渠道名、结果枚举或编码——那些只在项目知识里。
 */
import { childHeading, headingEnd, parseDocument, tablesWithin } from '../../skills/story/scripts/core/story/document.mjs';

const NA = /^(本需求)?不涉及[:：]?\s*\S/;
const clean = (s) => String(s ?? '').replace(/[`*]/g, '').trim();
//: 「接口.方法」形态的引用：plan 表里责任方法这么写，契约里按 `interfaces.<接口>.<方法>` 找。
const METHOD_REF = /[A-Za-z_$][\w$]*\.[A-Za-z_$][\w$]*/g;

/** 名字匹配 `parentRe` 的标题之下、下一级里名含「埋点」的那一节：`{ doc, h, from, to }`；没有返回 null。 */
function section(text, parentRe) {
  const doc = parseDocument(String(text ?? ''));
  const parent = doc.headings.find(x => parentRe.test(x.name));
  const h = parent && childHeading(doc, parent, /埋点/);
  return h ? { doc, h, from: h.at + 1, to: headingEnd(doc, h) } : null;
}

/** 一段以埋点标题开头的正文：`{ doc, h, from, to }`；首个标题不是埋点返回 null。 */
function leadingSection(text) {
  const doc = parseDocument(String(text ?? ''));
  const h = doc.headings[0];
  return h && /埋点/.test(h.name) ? { doc, h, from: h.at + 1, to: headingEnd(doc, h) } : null;
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
 * spec 的埋点一节：`{ na, text, groups: [{ title, lead, points, rows }] }`，没有这一节返回 null。
 * `text` 是这一节的原文（给任务包与审查照列，说明表也在里面），`lead` 是指标标题与它第一张表之间
 * 第一行正文（没有为 `''`，门禁据它判「有没有定义段」，不判内容），`points` 是各指标点位表里的统计点名，
 * `rows` 是对应的整行——统计点那一格挪到首位，其余格保持原来的相对顺序。
 */
export function specStatPoints(specText) {
  return statPoints(section(specText, /技术契约/));
}

/** 同 `specStatPoints`，读一段以埋点标题开头的正文（门禁拿到的就是这一节）。 */
function statPointsOfSection(sectionText) {
  return statPoints(leadingSection(sectionText));
}

function statPoints(s) {
  if (!s) return null;
  const { doc, from, to } = s;
  const indicators = doc.headings.filter(x => x.level === s.h.level + 1 && x.at > s.h.at && x.at < to);
  const groups = indicators.map((h, k) => {
    const end = indicators[k + 1]?.at ?? to;
    const tables = tablesWithin(doc, h.at + 1, end);
    const lead = doc.lines.slice(h.at + 1, tables[0]?.line ?? end).map(l => l.trim())
      .find(l => l && !l.startsWith('<!--') && !l.startsWith('|')) ?? '';
    const rows = [];
    for (const t of tables) {
      const p = t.header.findIndex(c => clean(c).includes('统计点'));
      if (p < 0) continue;
      for (const r of t.rows) if (clean(r[p])) rows.push([r[p], ...r.slice(0, p), ...r.slice(p + 1)]);
    }
    return { title: h.raw, lead, points: rows.map(r => clean(r[0])), rows };
  });
  return { na: notApplicable(doc, from, to), text: doc.lines.slice(s.h.at, to).join('\n'), groups };
}

/**
 * spec 统计设计的状态：没有这一节 `missing`、写了不涉及 `na`、有节而没有点位表 `empty`、有点位 `ready`。
 * 三个消费者（plan 作者包、plan 门禁、审查任务）各按自己的读者说话，状态只在这里判。
 */
export function statDesignState(points) {
  if (!points) return 'missing';
  if (points.na) return 'na';
  return points.groups.some(g => g.points.length) ? 'ready' : 'empty';
}

/**
 * plan 的埋点小节（「宿主扩展」的下一级）：`{ na, rows: [{ point, methods, cells }] }`，没有这一节返回 null。
 */
export function planStatRows(planText) {
  const s = section(planText, /^宿主扩展/);
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

/**
 * 埋点一节的形状：总述在首个指标之前，表都在某个指标下，每个指标有定义段与带「统计点」列的点位表且至少一行。
 * 指标是埋点标题的下一级（`level` 是埋点标题的层级）。点位按任务包与审查同一份解析取，说明表不算点位。
 * 写「不涉及：<依据>」的整节不判。只核结构，不核指标名、统计点名、定义段与结果写法。
 */
export function indicatorShape(where, body, level, formDoc) {
  const lines = body.map(l => l.trim()).filter(l => l && !l.startsWith('<!--'));
  if (/^不涉及[:：]\s*\S/.test(lines[0] ?? '')) return [];
  const problems = [];
  const indicator = new RegExp(`^#{${level + 1}}\\s`);
  let seen = false;
  let lead = false;
  for (const l of lines) {
    if (indicator.test(l)) { seen = true; continue; }
    if (!l.startsWith('|')) { if (!seen) lead = true; continue; }
    if (!seen) { problems.push(`${where}有统计点表不在指标小节下——一个指标一个小节，表放在它下面（形态见 ${formDoc}）`); return problems; }
  }
  const groups = statPointsOfSection([`${'#'.repeat(level)} 埋点`, ...body].join('\n'))?.groups ?? [];
  if (!groups.length) problems.push(`${where}没有指标小节——一个指标一个小节，下面放它的统计点表（形态见 ${formDoc}）`);
  if (groups.length && !lead) problems.push(`${where}首个指标之前缺总述（形态见 ${formDoc}）`);
  for (const g of groups) {
    if (!g.lead) {
      problems.push(`${where}的指标「${g.title}」缺定义段——标题与表之间先写定义段，再放表`);
    }
    if (!g.points.length) {
      problems.push(`${where}的指标「${g.title}」下没有统计点——在它下面放一张带「统计点」列的表写出观察它需要的点位，或去掉这个小标题`);
    }
  }
  return problems;
}
