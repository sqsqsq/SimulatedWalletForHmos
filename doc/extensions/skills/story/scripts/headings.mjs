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
 * **裸序号（`1 闸机前的窘境`）不在这里剥**：本函数被十几处标题匹配共用而没有位置信息，
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
 * 机器算的序位，因为作者会漏编某节（实跑里「页面状态」没编号，后面那节写 3、序位是 4）。
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

  let inFence = false;
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
  return String(text ?? '').split(/\r?\n/).map((raw) => {
    if (/^\s*(```|~~~)/.test(raw)) { inFence = !inFence; return raw; }
    if (inFence) return raw;

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
      if (!chapterNo || inAppendix) return raw;
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
