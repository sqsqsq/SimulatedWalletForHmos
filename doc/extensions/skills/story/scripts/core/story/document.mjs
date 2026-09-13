/**
 * 一章的**一次解析** —— 围栏、小节、表头各扫一遍，判据从结果里读。
 *
 * 解析与判断分开：判据自己切文的话，同一章在一次 check 里会被切上七八遍，而每一处
 * 对「围栏里的东西算不算」「小节到哪里结束」都有自己的一份答案。这里只解析**当前判据
 * 真正要的那几样**：原文、去围栏正文、围栏范围与语言、H3 小节名与范围、正文表头及
 * 它所在的小节。不建通用 Markdown 语法树，不落盘，不跨命令缓存。
 *
 * 边界：只认结构，不判对错。哪些小节必需、表要有哪几列、图算不算总览，都在章节合同
 * 与语义审查那一侧。
 */
import { normalizeHeading } from '../headings.mjs';

/** 规范化：去空白与标点——「点了提交、但没收到回执」与原文只差标点时仍算同一句。 */
export function norm(s) {
  return String(s ?? '').replace(/[\s，。、；：!?！？（）()「」【】]/g, '');
}

//: 画图语言的围栏才是图。`json` / `yaml` / `text` 围栏是数据与摘抄，算成图的话，
//: 「这一章有没有图」就会被一段贴进来的示例顶掉。
const DIAGRAM_LANGS = new Set(['mermaid', 'plantuml', 'puml', 'dot', 'graphviz']);

//: 关闭行：一串围栏标记之后除了空格与 tab 什么都没有。
const CLOSING = /^[ \t]*(?:`{3,}|~{3,})[ \t]*$/;

/** 表头行的下一行是不是分隔行（`|---|---|`）。 */
const SEPARATOR = /^\|[-: |]+\|$/;

/**
 * 扫一遍，给出这一章的结构。
 *
 * @param {string} text 一章的正文（不含 `## ` 标题行）
 * @returns {{text: string,
 *   fences: {lang: string, mark: string, from: number, to: number}[],
 *   sections: {raw: string, name: string, from: number, to: number, body: string[]}[],
 *   tables: {header: string[], line: number}[]}}
 *   行号都是原文的 0 起下标；小节的 `[from, to)` 与表的 `line` 一起定「这张表在哪一节」——
 *   同名小节可以有两个，按名字记归属会把后一节的表算给前一节。
 */
export function parseChapter(text) {
  const lines = String(text ?? '').split(/\r?\n/);
  const fences = [], sections = [], tables = [];
  let open = null;                       // 当前未闭合的围栏
  let current = null;                    // 当前 H3
  lines.forEach((line, i) => {
    const fence = line.match(/^[ \t]*(`{3,}|~{3,})[ \t]*(\w*)/);
    if (fence) {
      const mark = fence[1];
      if (!open) {
        open = { lang: fence[2].toLowerCase(), mark, from: i, to: lines.length - 1 };
        return;
      }
      // **合法关闭行有三个条件**：同种标记、不短于开启标记，且标记之后到行末只有空白。
      // 开启行与关闭行不是同一种语法：`` ```markdown `` 带语言信息，那是又开一段样例，
      // 不是关上外层。少了这一条，样例里的标题与表会被当成本章的正文结构，
      // 而真正的关闭符又被当成开启——泄漏与丢正文同时发生。
      if (mark[0] === open.mark[0] && mark.length >= open.mark.length
        && CLOSING.test(line)) {
        open.to = i;
        fences.push(open);
        open = null;
      }
      return;                            // 关不上的那一行仍是围栏里的内容
    }
    if (open) return;                    // 围栏里的东西不进正文视图
    const h3 = line.trim().match(/^###\s+(.+)$/);
    if (h3) {
      if (current) current.to = i;
      current = { raw: h3[1].trim(), name: normalizeHeading(h3[1]),
        from: i, to: lines.length, body: [] };
      sections.push(current);
      return;
    }
    if (current) current.body.push(line);
    if (!line.trim().startsWith('|')) return;
    const sep = (lines[i + 1] ?? '').trim();
    if (!SEPARATOR.test(sep)) return;
    tables.push({
      header: line.trim().replace(/^\||\|$/g, '').split('|')
        .map(c => norm(c.replace(/[`*]/g, ''))),
      line: i,
    });
  });
  if (open) fences.push(open);           // 没闭合的围栏也要看得见，别把后半章吞掉
  return { text: String(text ?? ''), fences, sections, tables };
}

/** 这一章的小节名（围栏里的 `###` 是被引用的样例，不在其中）。 */
export function sectionNames(view) {
  return (view?.sections ?? []).map(s => ({ raw: s.raw, name: s.name }));
}

/**
 * 按名字取一个小节的正文 —— **先精确，再包含**；没有这一节返回 null。
 *
 * 合同给的是这一节要讲什么，作者按业务命名（「与上游单的交接约定」）；只认精确名
 * 会把后者判成缺这一节。给的是**去围栏正文**：判「有没有表、有没有行」时，
 * 围栏里的样例不该顶替真内容。
 */
export function sectionBody(view, name) {
  const hit = matchSection(view, name);
  return hit ? hit.body.join('\n') : null;
}

/** 作用域内的表头：`name` 为空取全章，否则只取那一节里的。 */
export function tablesIn(view, name) {
  if (!name) return (view?.tables ?? []).map(t => t.header);
  const hit = matchSection(view, name);
  if (!hit) return null;                 // 那一节缺席，与「有节但没表」不是一回事
  // 正文与表取**同一个节**：按名字过滤的话，第二个同名小节里的表会被算给第一个，
  // 于是缺表的那一节通过了，而别的消费者读到的还是缺表的那一份。
  return (view.tables ?? []).filter(t => t.line > hit.from && t.line < hit.to)
    .map(t => t.header);
}

/** 这一章有没有真正的图围栏（画图语言的那种）。 */
export function hasDiagram(view) {
  return (view?.fences ?? []).some(f => DIAGRAM_LANGS.has(f.lang));
}

function matchSection(view, name) {
  const want = normalizeHeading(name);
  const list = view?.sections ?? [];
  return list.find(s => s.name === want) ?? list.find(s => s.name.includes(want)) ?? null;
}
