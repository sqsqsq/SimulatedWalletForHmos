/**
 * 文档的**一次解析** —— 围栏、标题、表各扫一遍，全链的判据与投影从结果里读。
 *
 * 解析与判断分开：判据自己切文的话，同一份文档在一次 check 里会被切上七八遍，而每一处
 * 对「围栏里的东西算不算」「小节到哪里结束」「哪一行是表头」都有自己的一份答案。
 * story 的章、spec 的节、需求分析的初筛表、上游文档里的图，都走这里：`parseDocument`
 * 给围栏、标题与表，`findByName` 是唯一的按名定位规则，`headingEnd` 是唯一的节尾规则。
 * 只解析**当前判据真正要的那几样**，不建通用 Markdown 语法树，不落盘，不跨命令缓存。
 *
 * 边界：只认结构，不判对错。哪些小节必需、表要有哪几列、图算不算总览，都在章节合同
 * 与语义审查那一侧。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';

/** 规范化：去空白与标点——「点了提交、但没收到回执」与原文只差标点时仍算同一句。 */
export function norm(s) {
  return String(s ?? '').replace(/[\s，。、；：!?！？（）()「」【】]/g, '');
}

//: 画图语言的围栏才是图。`json` / `yaml` / `text` 围栏是数据与摘抄，算成图的话，
//: 「这一章有没有图」就会被一段贴进来的示例顶掉。
export const DIAGRAM_LANGS = new Set(['mermaid', 'plantuml', 'puml', 'dot', 'graphviz']);

//: 写作设计能点名的图种：`heads` 是 mermaid 首个声明的写法，`name` 是读者看到的名字。
//: 用哪种图由作者按要解释的关系定，这里只列认得出的写法，不偏向哪一种；不点名的图照旧认任何画图语言。
//: 类型只证明语法类别，图里关系画得对不对归语义审查。
export const DIAGRAM_SYNTAXES = Object.fromEntries([
  ['flowchart', '流程图', 'graph'], ['sequenceDiagram', '时序图'], ['stateDiagram', '状态图', 'stateDiagram-v2'],
  ['classDiagram', '类图'], ['erDiagram', '实体关系图'], ['journey', '旅程图'], ['gantt', '甘特图'], ['mindmap', '思维导图'],
].map(([key, name, ...alias]) => [key, { name, heads: [key, ...alias] }]));

//: 关闭行：一串围栏标记之后除了空格与 tab 什么都没有。
const CLOSING = /^[ \t]*(?:`{3,}|~{3,})[ \t]*$/;

/**
 * 表格一行的单元格：去掉首尾竖线，在未转义的竖线处切，单元格去首尾空白。
 * 转义竖线 `\|` 原样留在格子里——投影会把格子再渲染回表，解转义就会多切出一列。
 */
export function tableCells(line) {
  return String(line ?? '').trim().replace(/^\|/, '').replace(/(?<!\\)\|$/, '')
    .split(/(?<!\\)\|/).map(c => c.trim());
}

/** 按列名取单元格——列序会随编辑漂移，列名才是契约。去掉强调与代码标记后比。 */
export function cellByHeader(cells, headers, keyword) {
  const i = (headers ?? []).findIndex(h => h.includes(keyword));
  return i >= 0 && i < cells.length ? cells[i].replace(/[`*]/g, '').trim() : '';
}

/** 分隔行（`|---|:--:|`）：以竖线起头，每一格都只有横线与对齐冒号。 */
function isSeparatorRow(line) {
  const t = String(line ?? '').trim();
  return t.startsWith('|') && tableCells(t).every(c => /^:?-+:?$/.test(c));
}

/**
 * 围栏范围 —— **开闭判断只有这一处**。
 *
 * 切章、区间定位、重编号都要判围栏；各写一份，改一个边界条件就要改几处。这里出范围，
 * 别处一律从范围派生——要行标记的拿 `fencedLines`，要语言与闭合状态的读这几个字段。
 *
 * **合法关闭行有三个条件**：同种标记、不短于开启标记，且标记之后到行末只有空白。
 * 开启行与关闭行不是同一种语法：`` ```markdown `` 带语言信息，那是又开一段样例，
 * 不是关上外层。少了这一条，样例里的标题与表会被当成本章的正文结构，
 * 而真正的关闭符又被当成开启——泄漏与丢正文同时发生。
 *
 * 关不上的围栏也照样给出来（`closed: false`，`to` 到末行）：吞掉后半章这件事要看得见。
 *
 * @param {string[]} lines 已经按 `\r?\n` 切好的行
 * @returns {{lang: string, mark: string, from: number, to: number, closed: boolean}[]}
 */
export function fenceRanges(lines) {
  const out = [];
  let open = null;
  lines.forEach((line, i) => {
    const fence = line.match(/^[ \t]*(`{3,}|~{3,})[ \t]*(\w*)/);
    if (!fence) return;
    const mark = fence[1];
    if (!open) {
      open = { lang: fence[2].toLowerCase(), mark, from: i, to: lines.length - 1,
        closed: false };
      return;
    }
    if (mark[0] === open.mark[0] && mark.length >= open.mark.length && CLOSING.test(line)) {
      open.to = i;
      open.closed = true;
      out.push(open);
      open = null;
    }
  });
  if (open) out.push(open);
  return out;
}

/** 由围栏范围派生的行标记：这一行在围栏里（含首尾标记行）吗。 */
export function fencedLines(text) {
  const lines = String(text ?? '').split(/\r?\n/);
  return maskOf(lines, fenceRanges(lines));
}

/** 围栏里首个有效声明：跳过空行与 `%%` 注释行（图源标记也是注释）。图类型由它认。 */
function firstStatement(lines, fence) {
  const end = fence.closed ? fence.to : fence.to + 1;
  for (let i = fence.from + 1; i < end && i < lines.length; i++) {
    const line = lines[i].trim();
    if (line && !line.startsWith('%%')) return line;
  }
  return '';
}

/** 同上，但调用方已经有行与范围时不重扫。 */
function maskOf(lines, ranges) {
  const mask = new Set();
  for (const f of ranges) {
    for (let i = f.from; i <= f.to && i < lines.length; i++) mask.add(i);
  }
  return mask;
}

/**
 * 扫一遍，给出这份文档的围栏、标题与表 —— **全链只有这一份切法**。
 *
 * 围栏里的标题与表是被引用的样例，不进结果；表只认「表头行 + 紧跟的分隔行」起头的那种，
 * 其后连续的竖线行是数据行。行号都是原文的 0 起下标。
 *
 * @param {string} text 任意一份 markdown（一章正文、整篇 story、spec、需求分析）
 * @returns {{text: string, lines: string[], fenced: Set<number>,
 *   fences: {lang: string, mark: string, from: number, to: number, closed: boolean, head: string}[],
 *   headings: {level: number, raw: string, name: string, at: number}[],
 *   tables: {header: string[], rows: string[][], line: number}[]}}
 */
export function parseDocument(text) {
  const lines = String(text ?? '').split(/\r?\n/);
  const fences = fenceRanges(lines).map(f => ({ ...f, head: firstStatement(lines, f) }));
  const fenced = maskOf(lines, fences);
  const headings = [], tables = [];
  let table = null;
  lines.forEach((line, i) => {
    if (fenced.has(i)) { table = null; return; }
    const t = line.trim();
    const h = /^(#{1,6})\s+(.+?)\s*$/.exec(t);
    if (h) {
      headings.push({ level: h[1].length, raw: h[2].trim(), name: normalizeHeading(h[2]), at: i });
      table = null;
      return;
    }
    if (!t.startsWith('|')) { table = null; return; }
    if (table) {
      if (!isSeparatorRow(t)) table.rows.push(tableCells(t));
      return;
    }
    if (!fenced.has(i + 1) && isSeparatorRow(lines[i + 1])) {
      table = { header: tableCells(t), rows: [], line: i };
      tables.push(table);
    }
  });
  return { text: String(text ?? ''), lines, fenced, fences, headings, tables };
}

/** 一个标题管到哪一行为止（不含）：下一个同级或更高级标题，没有就到文末。 */
export function headingEnd(doc, heading) {
  const next = (doc?.headings ?? []).find(h => h.at > heading.at && h.level <= heading.level);
  return next ? next.at : (doc?.lines ?? []).length;
}

/** `parent` 管到的范围里、下一级中名字匹配 `nameRe` 的第一个标题；没有返回 undefined。 */
export function childHeading(doc, parent, nameRe) {
  const end = headingEnd(doc, parent);
  return doc.headings.find(h => h.at > parent.at && h.at < end && h.level === parent.level + 1 && nameRe.test(h.name));
}

/**
 * 按名字挑一项 —— **全链唯一的按名定位规则**：先精确，再包含；包含只在唯一命中时成立。
 *
 * 合同给的是这一节要讲什么，作者按业务命名（「与上游单的交接约定」），只认精确名会把后者
 * 判成缺节。但包含命中两个以上时（「参与方」同时像「参与方与分工」与「参与方不在本轮」），
 * 取第一个就是替作者猜——那一节的表与图会被算到另一节头上。这时报歧义，让作者改名。
 *
 * @param {{name: string}[]} items 已规范化名字的候选（标题、小节）
 * @returns {{hit: object|null, ambiguous: string[]|null}}
 */
export function findByName(items, name) {
  const want = normalizeHeading(name);
  const list = items ?? [];
  const exact = list.find(x => x.name === want);
  if (exact) return { hit: exact, ambiguous: null };
  const loose = list.filter(x => x.name.includes(want));
  if (loose.length === 1) return { hit: loose[0], ambiguous: null };
  return { hit: null, ambiguous: loose.length > 1 ? loose.map(x => x.raw ?? x.name) : null };
}

/** 一张表是否落在 `[from, to)` 里。 */
export function tablesWithin(doc, from, to) {
  return (doc?.tables ?? []).filter(t => t.line >= from && t.line < to);
}

/**
 * 一章的结构 —— `parseDocument` 之上按 H3 分节，供章级判据读。
 *
 * @param {string} text 一章的正文（不含 `## ` 标题行）
 * @returns {{text: string, lines: string[], fenced: Set<number>, fences: object[],
 *   sections: {raw: string, name: string, from: number, to: number, body: string[],
 *     subs: {raw: string, name: string, at: number}[]}[],
 *   tables: {header: string[], line: number}[]}}
 *   小节的 `[from, to)` 与表的 `line` 一起定「这张表在哪一节」——同名小节可以有两个，
 *   按名字记归属会把后一节的表算给前一节。表头已去掉行内标记并规范化，供锚列比对。
 */
export function parseChapter(text) {
  const doc = parseDocument(text);
  const h3s = doc.headings.filter(h => h.level === 3);
  const sections = h3s.map((h, k) => {
    const to = h3s[k + 1]?.at ?? doc.lines.length;
    return {
      raw: h.raw, name: h.name, from: h.at, to,
      body: doc.lines.slice(h.at + 1, to).filter((_, j) => !doc.fenced.has(h.at + 1 + j)),
      subs: doc.headings.filter(x => x.level === 4 && x.at > h.at && x.at < to)
        .map(x => ({ raw: x.raw, name: x.name, at: x.at })),
    };
  });
  const tables = doc.tables.map(t => ({
    header: t.header.map(c => norm(c.replace(/[`*]/g, ''))), line: t.line }));
  return { text: doc.text, lines: doc.lines, fenced: doc.fenced, fences: doc.fences, sections, tables };
}

/** 这一章的小节名（围栏里的 `###` 是被引用的样例，不在其中）。 */
export function sectionNames(view) {
  return (view?.sections ?? []).map(s => ({ raw: s.raw, name: s.name }));
}

/**
 * 按名字取一个小节的正文（按 `findByName` 的规则）；没有这一节或名字有歧义返回 null。
 *
 * 给的是**去围栏正文**：判「有没有表、有没有行」时，围栏里的样例不该顶替真内容。
 */
export function sectionBody(view, name) {
  const span = name ? scopeSpan(view, name) : null;
  return span ? scopeLines(view, span).join('\n') : null;
}

/** 作用域内的表头：`name` 为空取全章，否则只取那一节里的。 */
export function tablesIn(view, name) {
  if (!name) return (view?.tables ?? []).map(t => t.header);
  const span = scopeSpan(view, name);
  if (!span) return null;                // 那一节缺席，与「有节但没表」不是一回事
  // 正文与表取**同一个区间**：按名字过滤的话，第二个同名小节里的表会被算给第一个，
  // 于是缺表的那一节通过了，而别的消费者读到的还是缺表的那一份。
  return tablesInSpan(view, span).map(t => t.header);
}

/**
 * 一个位置在章里的行区间 —— 形式与结构都按它定位，`[from, to)`，缺席返回 null。
 *
 * `at` 为空是整章；给了 `at` 是那个 H3 连同它的子节；再给 `under` 是该 H3 **下面**
 * 那个 H4 段。H4 必须先定位父节：全章找同名 H4 的话，甲节缺的那张表会被乙节的同名
 * 子节顶替通过。
 */
export function scopeSpan(view, at = '', under = '') {
  if (!at) return { from: 0, to: (view?.lines ?? []).length };
  const { hit } = findByName(view?.sections, at);
  if (!hit) return null;
  if (!under) return { from: hit.from + 1, to: hit.to };
  const subs = hit.subs ?? [];
  const sub = findByName(subs, under).hit;
  if (!sub) return null;
  const k = subs.indexOf(sub);
  return { from: sub.at + 1, to: subs[k + 1]?.at ?? hit.to };
}

/** 区间里的正文行（围栏里的不算）。行与掩码由 `parseChapter` 一次派生，这里不重切。 */
function scopeLines(view, span) {
  return (view?.lines ?? []).slice(span.from, span.to)
    .filter((_, k) => !view.fenced.has(span.from + k));
}

//: Markdown 的水平分隔线：三个及以上的 `*`/`-`/`_`，中间可以有空格。它一条内容都没有。
const RULE_LINE = /^(?:\*[ \t]*){3,}$|^(?:-[ \t]*){3,}$|^(?:_[ \t]*){3,}$/;

/** 这个区间里的表（表头 + 分隔行，解析时已认过）。 */
function tablesInSpan(view, span) {
  return (view?.tables ?? []).filter(t => t.line >= span.from && t.line < span.to);
}

/** 这个区间里有没有一张真的 Markdown 表。 */
export function hasTable(view, span) {
  return tablesInSpan(view, span).length > 0;
}

/**
 * 这个区间里有没有真的列表项：有序认数字加点或右括号，无序认 `-`/`+`/`*`。
 *
 * 空项与纯横线分隔不算，围栏里的示例不算；**不数条目**——几项算够是内容判断。
 */
export function hasList(view, span, ordered = false) {
  const re = ordered ? /^\s{0,3}\d+[.)]\s+(.+)$/ : /^\s{0,3}[-+*]\s+(.+)$/;
  return scopeLines(view, span).some(line => {
    if (RULE_LINE.test(line.trim())) return false;      // 水平分隔线不是列表项
    const hit = re.exec(line);
    return !!hit && /[^\s\-|]/.test(hit[1]);
  });
}

/**
 * 有没有真正的图围栏（画图语言的那种）：`name` 为空看全章，否则只看那一节里的。
 *
 * 那一节缺席返回 null——与「有节但没图」不是一回事，缺节由必要 H3 那条报。
 * 给了 `syntax`（`DIAGRAM_SYNTAXES` 里的一种）时只认首个声明是它的 mermaid 图。
 */
export function hasDiagram(view, name = '', syntax = '', under = '') {
  const drawn = (view?.fences ?? []).filter(f => DIAGRAM_LANGS.has(f.lang)
    && (!syntax || (f.lang === 'mermaid'
      && (DIAGRAM_SYNTAXES[syntax]?.heads ?? []).includes(String(f.head ?? '').split(/\s/)[0]))));
  if (!name) return drawn.length > 0;
  const span = scopeSpan(view, name, under);
  if (!span) return null;
  return drawn.some(f => f.from >= span.from && f.from < span.to);
}

/** 某一节的名字有没有歧义：命中两个以上时给出它们的原名，否则 null。 */
export function ambiguousSection(view, name) {
  return findByName(view?.sections, name).ambiguous;
}

/** 某个 H3 底下的 `####` 小节名。父节缺席（或名字有歧义）返回 null。 */
export function subsectionNames(view, parent) {
  const { hit } = findByName(view?.sections, parent);
  return hit ? new Set((hit.subs ?? []).map(x => x.name)) : null;
}

// --------------------------------------------------------------------------
// 标题归一与重编号 —— 与切文、定位同属「这份文档长什么样」，所以在同一个文件里：
// 分开放的话，每个消费者都要同时 import 两处，而它们读的是同一份行。
// --------------------------------------------------------------------------
/**
 * 标题规范化 —— **全链唯一通道**。
 *
 * 归档件的标题带编号（`## 1. 背景`、`### 4.1 参与方与分工`、`#### 10.1.1 接口`），
 * 而合同里存的是业务名（`背景`、`接口`）。编号是表达形式，不是标识：作者按阅读
 * 习惯加编号是对的，合同不该跟着存两套名字。
 *
 * 所以**每一处拿标题做比较的地方都过这个函数**：章标题与顺序、附录定位、
 * 附录小节名、语言红线的作用域边界、落点归章。逐处各自放宽的话，漏掉任何一处
 * 都会让整个附录被当成主叙事扫，报出大量本该允许的标识。
 *
 * 剥数字序号前缀，要求**后面跟空白**，且必须带点或分级：`1. ` / `10. ` / `4.1 ` / `8.2.1 `。
 * 「2026 年改版」这种以数字开头的正常标题不被误剥（无点且非分级）。
 *
 * **裸序号（`1 现状与问题`）不在这里剥**：本函数被十几处标题匹配共用而没有位置信息，
 * 剥错一个字那一节就「找不到」。它由 `renumberStory` 按位置剥，见 `takeAuthorNumber`。
 */

/** `1. ` `10. ` `4.1 ` `8.2.1 ` —— 单级须带点，分级可省略尾点。 */
const NUMBER_PREFIX = /^(?:\d+(?:\.\d+)+|\d+\.)\s*/;

/** `1 ` `12 ` —— 作者手写的裸序号。最多两位：小节不会编到 100。 */
const BARE_NUMBER_PREFIX = /^(\d{1,2})\s+(?=\S)/;

/**
 * 开头那个裸数字是不是作者写的序号？是就返回剥掉它的名字，否则 null。
 *
 * **判据是位置**：作者编号是从 1 起的递增序列，`expected` 是它的下一个。用序列而非
 * 机器算的序位，因为作者会漏编某节（漏了一节没编号，后面那节写 3、序位却是 4）。
 * 量词（合同 `heading_counters`）是第二道，挡「内容数字恰好接上序列」。
 */
function takeAuthorNumber(name, expected, counters) {
  const hit = BARE_NUMBER_PREFIX.exec(name);
  if (!hit || Number(hit[1]) !== expected) return null;
  const rest = name.slice(hit[0].length);
  return counters.some(c => rest.startsWith(c)) ? null : rest;
}

/**
 * 剥掉标题的序号前缀，返回业务名。
 *
 * @param {string} title 标题原文（不含 `#` 与首尾空白）
 * @returns {string}
 */
export function normalizeHeading(title) {
  let s = String(title ?? '').trim();
  s = s.replace(NUMBER_PREFIX, '');
  return s.trim();
}

/** 图题的序号前缀：`图 3 · ` `图 3・` `图 3`——剥掉重编，作者只写题名。 */
const FIGURE_PREFIX = /^图\s*\d+\s*(?:[·・]\s*)?/;

/**
 * 给一篇 story 重编号 —— 章序取合同，节序取出现顺序，图序取全篇顺序。
 *
 * **为什么由机器做**：编号是纯确定性变换，合同定死章序与附录各节，作者写业务名
 * 就够了。编号只写进模板而没有判据接住时，顺境的产物做了、逆境的整章丢光——
 * 无判据的形态必丢，而这件事根本不需要人来做。
 *
 * **幂等**：先剥旧号再编，已经对的文件重跑逐字节不变；乱号、缺号、半带号一并归位。
 * 全篇一条规则：合同认得的章之下，任何层级按深度编号（10.1、10.1.1、10.1.4.1 …），附录与正文相同，
 * 不设层级上限。正文引用其他小节写小节名，不写号——这里不改正文里的引用。
 *
 * @param {string} text story 全文
 * @param {{title:string}[]} chapters 合同章序
 * @param {string[]} counters 合同 `heading_counters`——裸序号判定的第二道
 * @returns {string}
 */
export function renumberStory(text, chapters = [], counters = []) {
  const order = new Map();
  (chapters ?? []).forEach((c, i) => {
    const name = normalizeHeading(c?.title ?? '');
    if (name) order.set(name, i + 1);
  });

  let chapterNo = 0;              // 0＝当前不在合同认得的章里，那一段不编
  let figure = 0;
  // 计数栈：下标 0 是三级标题，往下每一级一格。遇到某级标题，本级加一、更深的截掉。
  // `authored` 同形：作者自己编到第几个（裸序号按位置剥，见 takeAuthorNumber）。
  let seq = [];
  let authored = [];

  // 分行按 CRLF 安全的通道走；回写统一 LF——重编号本来就是重写整篇，
  // 顺手把行尾统一掉，比留着两种行尾在同一份文件里好。
  const lines = String(text ?? '').split(/\r?\n/);
  const fenced = maskOf(lines, fenceRanges(lines));
  return lines.map((raw, at) => {
    if (fenced.has(at)) return raw;          // 围栏里的标题是样例，不编号

    const head = /^(#{2,})\s+(.+?)\s*$/.exec(raw);
    if (head) {
      const depth = head[1].length - 3;      // -1 是章，0 起是章下各级
      const name = normalizeHeading(head[2]);
      if (depth < 0) {
        chapterNo = order.get(name) ?? 0;
        seq = []; authored = [];
        // 合同里没有的章原样留着：那是 check ① 要点名的事，不是编号该悄悄接受的
        return chapterNo ? `## ${chapterNo}. ${name}` : raw;
      }
      if (!chapterNo) return raw;
      if (depth > seq.length) return raw;    // 跳级（上一级还没出现）编不出号，留给判据说话
      seq = [...seq.slice(0, depth), (seq[depth] ?? 0) + 1];
      authored = authored.slice(0, depth + 1);
      const stripped = takeAuthorNumber(name, (authored[depth] ?? 0) + 1, counters);
      if (stripped !== null) authored[depth] = (authored[depth] ?? 0) + 1;
      return `${head[1]} ${[chapterNo, ...seq].join('.')} ${stripped ?? name}`;
    }

    return raw.replace(/!\[([^\]]*)\]/g, (whole, alt) => {
      figure += 1;
      const title = String(alt).replace(FIGURE_PREFIX, '').trim();
      return `![${title ? `图 ${figure} · ${title}` : `图 ${figure}`}]`;
    });
  }).join('\n');
}


// --------------------------------------------------------------------------
// 章与小节在全文里的位置
// --------------------------------------------------------------------------
/**
 * story 正文按 `## ` 标题切节。
 *
 * `title` 是**规范化后的业务名**（`## 1. 背景` → `背景`），`raw` 保留原样给报错用。
 * 全链的标题比较——章序、落点归章、附录定位——都用 `title`，于是「作者按阅读习惯
 * 加章序编号」与「合同存业务名」两件事同时成立，不必在每处判据各放宽一次。
 */
export function storySections(storyText) {
  const doc = parseDocument(storyText);
  const h2s = doc.headings.filter(h => h.level === 2);
  return h2s.map((h, k) => ({ title: h.name, raw: h.raw,
    text: doc.lines.slice(h.at + 1, h2s[k + 1]?.at ?? doc.lines.length).join('\n') }));
}

/**
 * 某个 `###` 小节在**全篇**里的行区间（正文部分，0 起）。
 *
 * `sectionBody` 只给正文，报错就指不回原文行号；而材料清单那一节的形态判据
 * 与仓内路径豁免都要按行说话。
 *
 * @returns {{start:number, end:number}|null}
 */
export function subsectionSpan(storyText, chapterTitle, name) {
  const doc = parseDocument(storyText);
  const chapter = doc.headings.find(h => h.level === 2 && h.name === normalizeHeading(chapterTitle));
  if (!chapter) return null;
  const end = headingEnd(doc, chapter);
  const { hit } = findByName(doc.headings.filter(h => h.level === 3 && h.at > chapter.at && h.at < end), name);
  return hit ? { start: hit.at + 1, end: headingEnd(doc, hit) } : null;
}

/**
 * 一章在全文里的字节区间 —— 从它的 `## ` 那一行，到下一个 `## ` 之前。
 *
 * 按行找而不是正则整篇匹配：正文里可能有代码块，块里出现 `## ` 时整篇正则会切错，
 * 而切错的后果是替换一章时吃掉了别的章。
 *
 * @returns {{start:number, end:number}|null} 字符下标区间
 */
export function chapterSpan(storyText, title) {
  const text = String(storyText ?? '');
  // CRLF 安全：按 `\r?\n` 切，回推下标时把真实分隔符长度还回去——
  // 少还一个字节，替换区间就整体错位一位，吃掉相邻章的第一个字符。
  const lines = text.split(/\r?\n/);
  let start = -1;
  let offset = 0;
  const offsets = [];
  for (const line of lines) {
    offsets.push(offset);
    offset += line.length + (text.startsWith('\r\n', offset + line.length) ? 2 : 1);
  }
  const h2s = parseDocument(text).headings.filter(h => h.level === 2);
  const k = h2s.findIndex(h => h.name === normalizeHeading(title));
  if (k < 0) return null;
  start = h2s[k].at;
  return { start: offsets[start], end: h2s[k + 1] ? offsets[h2s[k + 1].at] : text.length };
}

/**
 * 待写块的 marker —— **明确记号**，不是「看起来像没写完」。
 *
 * 判它不需要读懂任何一句话：在就是没写完，不在就是写过了。中断恢复据它决定还剩哪几章，
 * check 据它拦住「骨架当成品交」。
 */
//: 记号的真源是章节合同的 `pending_mark`，这里与 Python 侧都从它读，不各写一份字面。
const PENDING_MARK = (() => {
  const url = new URL('../../../contracts/story-chapters.json', import.meta.url);
  try {
    return String(JSON.parse(fs.readFileSync(url, 'utf-8').replace(/^\uFEFF/, '')).pending_mark);
  } catch (err) {
    throw new Error(`\u7AE0\u8282\u5408\u540C\u8BFB\u4E0D\u51FA\u6765\uFF08${err.message}\uFF09\uFF1A\u5F85\u5199\u8BB0\u53F7 pending_mark \u767B\u8BB0\u5728\u90A3\u91CC`);
  }
})();
const PENDING_RE = new RegExp(`<!--\\s*${PENDING_MARK.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`
  + '[:：]\\s*([^>]*?)\\s*-->', 'g');

export function pendingMark(title) {
  return `<!-- ${PENDING_MARK}：${title} -->`;
}

/** story 里还带着待写 marker 的章名。 */
export function pendingChapters(storyText) {
  const out = [];
  for (const m of String(storyText ?? '').matchAll(PENDING_RE)) out.push(m[1]);
  return out;
}

/** 模板占位符 `{{…}}` —— 模板留给作者替换的位置，留在成品里就是没写完。 */
export function placeholderProblems(text, where = '') {
  const out = [];
  String(text ?? '').split(/\r?\n/).forEach((line, i) => {
    const hit = /\{\{[^}]*\}\}/.exec(line);
    if (!hit) return;
    out.push(`${where}第 ${i + 1} 行还留着模板占位符「${hit[0]}」`
      + '——它是模板留给你替换的位置，换成这一节真正要写的内容');
  });
  return out;
}

export const EMPTY_SECTION_TEXT = '本需求不涉及。';


// --------------------------------------------------------------------------
// 机器区（投影区）的标记与定位
// --------------------------------------------------------------------------
//: 生成区的标记。**这段的所有者是脚本**：内容从真源投影而来，`chapter` 落盘时
//: 原样保留，`skeleton` 可以重渲染。作者要改它，改的是真源（spec §9.1、
//: knowledge-use.yaml、materials.json），不是这里。
//:
//: 与作者区的分界就是所有权：术语的措辞、流程图的节点文字是**一次性种子**——
//: 种在作者区，之后归作者，脚本不再碰；附录的这几张表是**可重复投影**，
//: 只认 `sha256:` 那一段：标记里的散文与分隔符是给人读的，改了措辞不该让摘要失效。
const DIGEST_IN_MARK = /sha256:([0-9a-f]{16})\s*-->\s*$/;

/**
 * 投影区的内容摘要 —— **story 的附录与 review 的议题共用这一份口径**。
 *
 * 两处各写一份的话，口径迟早分叉：一处忽略行尾空白、另一处不忽略，
 * 同一份产物在两条路上会判出不同的「有没有被人改过」。
 *
 * 忽略每行尾部空白、末尾空行与标题序号（`zoneLine`）：保存时顺手删掉的行尾空格、
 * 重编号铺上的序号，都不是改动。
 */
export const projectionDigest = (text) => crypto.createHash('sha256')
  .update((Array.isArray(text) ? text.join('\n') : String(text))
    .replace(/\s+$/, '').split(/\r?\n/).map(zoneLine).join('\n'))
  .digest('hex').slice(0, 16);

/**
 * 投影区里一行的比较形态：去行尾空白，标题行按 `normalizeHeading` 剥掉序号。
 *
 * 标题序号是表达形式，不是内容：story 的序号由登记时的重编号铺（投影不带），
 * review 的序号由渲染器铺。两处「有没有被人改过」都不看序号——与全链标题比较同一个通道。
 */
export function zoneLine(line) {
  const l = String(line ?? '').replace(/\s+$/, '');
  const h = /^(#{1,6})\s+(.+)$/.exec(l);
  return h ? `${h[1]} ${normalizeHeading(h[2])}` : l;
}

/** 起始标记里记着的摘要；没有返回 null。 */
export const recordedDigest = (markLine) =>
  DIGEST_IN_MARK.exec(String(markLine ?? ''))?.[1] ?? null;

/** 盘上有人动过投影区 —— 调用方停下问人，不替他决定。 */
export class ProjectionConflict extends Error {}

//: 每次都能从真源重算出同样的东西，让作者重打一遍只会打得更少。
export const ZONE_BEGIN = '<!-- story-build:begin ';
export const ZONE_END = '<!-- story-build:end -->';

//: 投影区落盘时是什么样，记在起始标记里。重投前拿它与盘上的内容比：相等说明这一段
//: 还是上次投出来的原样，覆盖它不丢任何人写的东西；不等说明有人在这里写过字。
//: 摘要口径与 review 的议题共用一份（`projectionDigest`）——两处各写一份的话，
//: 同一份产物在两条路上会判出不同的「有没有被人改过」。
export const zoneBlock = (name, source, rows) =>
  [`${ZONE_BEGIN}${name} · 由${source}生成，改它请改真源 · sha256:${projectionDigest(rows)} -->`,
    ...rows, ZONE_END];

/**
 * 盘上这一段，是不是有人动过手 —— 动过就返回它现在的样子，没动过返回 null。
 *
 * 标记里的摘要与盘上内容比，相等就是没人动过（真源变没变不影响这个判断，那是下一步的事）。
 * 标记里没有摘要就无从分辨「真源变了」与「有人改了」，按改过处理——让人自己说哪一种。
 */
export function zoneHandEdited(lines, at) {
  const body = lines.slice(at.start + 1, at.end - 1);
  const recorded = recordedDigest(lines[at.start]);
  return recorded && projectionDigest(body) === recorded ? null : body;
}

/**
 * 全文每一行落在哪个投影区里：行下标 → `{name, source}`（只含首尾标记之间的内容行）。
 *
 * 投影区没有作者：它里面的问题要报到真源，报在这里作者删掉、下一次投影又写回来。
 * 名字与真源都从起始标记读——那是 `zoneBlock` 写下的同一份字面。
 */
export function zonesByLine(lines) {
  const out = new Map();
  let zone = null;
  (lines ?? []).forEach((line, i) => {
    if (line.startsWith(ZONE_BEGIN)) {
      const [name, from] = line.slice(ZONE_BEGIN.length).split(' · ');
      zone = { name: name.trim(), source: (/^由(.+?)生成/.exec(from ?? '') ?? [])[1] ?? '真源' };
      return;
    }
    if (line.trim() === ZONE_END) { zone = null; return; }
    if (zone) out.set(i, zone);
  });
  return out;
}

/**
 * 一段正文里某个生成区的行区间（含首尾标记），没有就返回 null。
 */
export function zoneSpan(lines, name) {
  const at = lines.findIndex(l => l.startsWith(`${ZONE_BEGIN}${name} `));
  if (at < 0) return null;
  const end = lines.findIndex((l, i) => i > at && l.trim() === ZONE_END);
  return end < 0 ? null : { start: at, end: end + 1 };
}


