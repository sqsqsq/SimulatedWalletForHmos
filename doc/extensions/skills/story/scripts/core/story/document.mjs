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
import * as crypto from 'node:crypto';

/** 规范化：去空白与标点——「点了提交、但没收到回执」与原文只差标点时仍算同一句。 */
export function norm(s) {
  return String(s ?? '').replace(/[\s，。、；：!?！？（）()「」【】]/g, '');
}

//: 画图语言的围栏才是图。`json` / `yaml` / `text` 围栏是数据与摘抄，算成图的话，
//: 「这一章有没有图」就会被一段贴进来的示例顶掉。
export const DIAGRAM_LANGS = new Set(['mermaid', 'plantuml', 'puml', 'dot', 'graphviz']);

//: 关闭行：一串围栏标记之后除了空格与 tab 什么都没有。
const CLOSING = /^[ \t]*(?:`{3,}|~{3,})[ \t]*$/;

/** 表头行的下一行是不是分隔行（`|---|---|`）。 */
const SEPARATOR = /^\|[-: |]+\|$/;

/**
 * 围栏范围 —— **开闭判断只有这一处**。
 *
 * 从前三个地方各写一份（切章、区间定位、重编号），后来收成两份（`parseChapter` 与掩码）。
 * 两份仍然是两份：改一个边界条件要改两处，而它们只在样例上一致。这里出范围，
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

/** 同上，但调用方已经有行与范围时不重扫。 */
function maskOf(lines, ranges) {
  const mask = new Set();
  for (const f of ranges) {
    for (let i = f.from; i <= f.to && i < lines.length; i++) mask.add(i);
  }
  return mask;
}

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
  const fences = fenceRanges(lines);
  const fenced = maskOf(lines, fences);
  const sections = [], tables = [];
  let current = null;                    // 当前 H3
  lines.forEach((line, i) => {
    if (fenced.has(i)) return;           // 围栏里的东西不进正文视图
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

/**
 * 有没有真正的图围栏（画图语言的那种）：`name` 为空看全章，否则只看那一节里的。
 *
 * 那一节缺席返回 null——与「有节但没图」不是一回事，缺节由必要 H3 那条报。
 */
export function hasDiagram(view, name = '') {
  const drawn = (view?.fences ?? []).filter(f => DIAGRAM_LANGS.has(f.lang));
  if (!name) return drawn.length > 0;
  const hit = matchSection(view, name);
  if (!hit) return null;
  return drawn.some(f => f.from > hit.from && f.from < hit.to);
}

function matchSection(view, name) {
  const want = normalizeHeading(name);
  const list = view?.sections ?? [];
  return list.find(s => s.name === want) ?? list.find(s => s.name.includes(want)) ?? null;
}

// --------------------------------------------------------------------------
// 标题归一与重编号 —— 与切文、定位同属「这份文档长什么样」，所以在同一个文件里：
// 分开放的话，每个消费者都要同时 import 两处，而它们读的是同一份行。
// --------------------------------------------------------------------------
/**
 * 标题规范化 —— **全链唯一通道**。
 *
 * 归档件的标题带编号（`## 1. 背景`、`### 4.1 参与方与分工`、`### A. 接口`），
 * 而合同里存的是业务名（`背景`、`接口`）。编号是表达形式，不是标识：作者按阅读
 * 习惯加编号是对的，合同不该跟着存两套名字。
 *
 * 所以**每一处拿标题做比较的地方都过这个函数**：章标题与顺序、附录定位、
 * 附录小节名、语言红线的作用域边界、落点归章。逐处各自放宽的话，漏掉任何一处
 * 都会让整个附录被当成主叙事扫，报出大量本该允许的标识。
 *
 * 剥两种前缀，都要求**后面跟空白**，且数字形态必须带点或分级：
 *   - `1. ` / `10. ` / `4.1 ` / `8.2.1 `
 *   - `A. ` / `B、`
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

/** `A. ` `B、` —— 附录小节的字母序号。 */
const LETTER_PREFIX = /^[A-Z][.、]\s*/;

/**
 * 剥掉标题的序号前缀，返回业务名。
 *
 * @param {string} title 标题原文（不含 `#` 与首尾空白）
 * @returns {string}
 */
export function normalizeHeading(title) {
  let s = String(title ?? '').trim();
  s = s.replace(NUMBER_PREFIX, '');
  s = s.replace(LETTER_PREFIX, '');
  return s.trim();
}

/** 图题的序号前缀：`图 3 · ` `图 3・` `图 3`——剥掉重编，作者只写题名。 */
const FIGURE_PREFIX = /^图\s*\d+\s*(?:[·・]\s*)?/;

/**
 * 给一篇 story 重编号 —— 章序取合同，节序取出现顺序，图序取全篇顺序。
 *
 * **为什么由机器做**：编号是纯确定性变换，合同定死章序、附录固定 A–E，作者写业务名
 * 就够了。编号只写进模板而没有判据接住时，顺境的产物做了、逆境的整章丢光——
 * 无判据的形态必丢，而这件事根本不需要人来做。
 *
 * **幂等**：先剥旧号再编，已经对的文件重跑逐字节不变；乱号、缺号、半带号一并归位。
 * 附录小节的字母序号不重编——那是合同的附录小节判据管的地方，这里不插手。
 *
 * @param {string} text story 全文
 * @param {{title:string, appendix?:boolean}[]} chapters 合同章序
 * @param {string[]} counters 合同 `heading_counters`——裸序号判定的第二道
 * @returns {string}
 */
export function renumberStory(text, chapters = [], counters = []) {
  const order = new Map();
  const appendix = new Set();
  (chapters ?? []).forEach((c, i) => {
    const name = normalizeHeading(c?.title ?? '');
    if (!name) return;
    order.set(name, i + 1);
    if (c?.appendix) appendix.add(name);
  });

  let chapterNo = 0;              // 0＝当前不在合同认得的章里，那一段不编
  let inAppendix = false;
  let sub = 0;
  let subsub = 0;
  let figure = 0;
  // 作者自己编到第几个了。每章重置；H4 的序列在每个新 H3 处重置。
  let authorSub = 0;
  let authorSubsub = 0;

  // 分行按 CRLF 安全的通道走；回写统一 LF——重编号本来就是重写整篇，
  // 顺手把行尾统一掉，比留着两种行尾在同一份文件里好。
  const lines = String(text ?? '').split(/\r?\n/);
  const fenced = maskOf(lines, fenceRanges(lines));
  return lines.map((raw, at) => {
    if (fenced.has(at)) return raw;          // 围栏里的标题是样例，不编号

    const head = /^(#{2,4})\s+(.+?)\s*$/.exec(raw);
    if (head) {
      const level = head[1].length;
      const name = normalizeHeading(head[2]);
      if (level === 2) {
        chapterNo = order.get(name) ?? 0;
        inAppendix = appendix.has(name);
        sub = 0; subsub = 0;
        authorSub = 0; authorSubsub = 0;
        // 合同里没有的章原样留着：那是 check ① 要点名的事，不是编号该悄悄接受的
        return chapterNo ? `## ${chapterNo}. ${name}` : raw;
      }
      if (!chapterNo) return raw;
      if (inAppendix) {
        // 附录的小节用字母：A.–E. 是合同定的形态，读者按「附录 C」回找。
        // 序号由这里统一铺，草稿与投影都不带——同章序、节序一条幂等规则。
        if (level !== 3) return raw;
        sub += 1;
        return `### ${String.fromCharCode(64 + sub)}. ${name}`;
      }
      if (level === 3) {
        sub += 1; subsub = 0; authorSubsub = 0;
        const stripped = takeAuthorNumber(name, authorSub + 1, counters);
        if (stripped !== null) authorSub += 1;
        return `### ${chapterNo}.${sub} ${stripped ?? name}`;
      }
      if (!sub) return raw;       // 没有上级小节的 H4 编不出号，留给判据说话
      subsub += 1;
      const strippedSub = takeAuthorNumber(name, authorSubsub + 1, counters);
      if (strippedSub !== null) authorSubsub += 1;
      return `#### ${chapterNo}.${sub}.${subsub} ${strippedSub ?? name}`;
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
  const lines = String(storyText ?? '').split(/\r?\n/);
  const fenced = maskOf(lines, fenceRanges(lines));
  const out = [];
  let cur = null;
  lines.forEach((line, i) => {
    const m = fenced.has(i) ? null : line.trim().match(/^##\s+(.+)$/);
    if (m) {
      cur = { raw: m[1].trim(), body: [] };
      out.push(cur);
      return;
    }
    if (cur) cur.body.push(line);
  });
  return out.map(s => ({ title: normalizeHeading(s.raw), raw: s.raw,
    text: s.body.join('\n') }));
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
  const lines = String(storyText ?? '').split(/\r?\n/);
  const wantChapter = normalizeHeading(chapterTitle);
  const wantSub = normalizeHeading(name);
  let inChapter = false;
  let start = -1;
  for (let i = 0; i < lines.length; i++) {
    const s = lines[i].trim();
    const h2 = s.match(/^##\s+(.+)$/);
    if (h2) {
      if (start >= 0) return { start, end: i };
      inChapter = normalizeHeading(h2[1]) === wantChapter;
      continue;
    }
    const h3 = s.match(/^###\s+(.+)$/);
    if (h3) {
      if (start >= 0) return { start, end: i };
      if (inChapter && normalizeHeading(h3[1]) === wantSub) start = i + 1;
    }
  }
  return start >= 0 ? { start, end: lines.length } : null;
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
  const fenced = maskOf(lines, fenceRanges(lines));
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (fenced.has(i) || !line.startsWith('## ')) continue;
    if (start < 0) {
      if (normalizeHeading(line.slice(3).trim()) === normalizeHeading(title)) start = i;
      continue;
    }
    return { start: offsets[start], end: offsets[i] };
  }
  if (start < 0) return null;
  return { start: offsets[start], end: text.length };
}

/**
 * 待写块的 marker —— **明确记号**，不是「看起来像没写完」。
 *
 * 判它不需要读懂任何一句话：在就是没写完，不在就是写过了。中断恢复据它决定还剩哪几章，
 * check 据它拦住「骨架当成品交」。
 */
//: 记号的真源是章节合同的 `pending_mark`；这里与 Python 侧各按它写一份字面，
//: 改合同要同时改这两处——document 不读业务合同，读了它就成了第二个合同解释者。
const PENDING_MARK = '待写';
const PENDING_RE = /<!--\s*待写[:：]\s*([^>]*?)\s*-->/g;

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
//: 原样保留，`skeleton` 可以重渲染。作者要改它，改的是真源（spec §9、
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
 * 忽略每行尾部空白与末尾空行：编辑器保存时顺手删掉一个行尾空格，不是改动。
 */
export const projectionDigest = (text) => crypto.createHash('sha256')
  .update((Array.isArray(text) ? text.join('\n') : String(text))
    .replace(/\s+$/, '').split(/\r?\n/).map(l => l.replace(/\s+$/, '')).join('\n'))
  .digest('hex').slice(0, 16);

/** 起始标记里记着的摘要；旧稿的标记没有它，返回 null。 */
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
 * 标记里带摘要：与盘上内容比，相等就是没人动过（真源变没变不影响这个判断，
 * 那是下一步的事）。
 *
 * 标记里没有摘要，那是**旧稿**：只能与这一次投出来的比，一样就是没人动过、
 * 补上摘要即可；不一样就无从分辨「真源变了」与「有人改了」，按改过处理——
 * 让人自己说哪一种，比替他猜错要好。
 */
export function zoneHandEdited(lines, at, freshRows) {
  const body = lines.slice(at.start + 1, at.end - 1);
  const recorded = recordedDigest(lines[at.start]);
  const now = projectionDigest(body);
  if (recorded) return now === recorded ? null : body;
  return now === projectionDigest(freshRows) ? null : body;
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

// --------------------------------------------------------------------------
// check：整篇守恒与形态
// --------------------------------------------------------------------------

