/**
 * 标题规范化 —— **全链唯一通道**。
 *
 * 归档件的标题带编号（`## 1. 背景`、`### 4.1 参与方与分工`、`### A. 接口`），
 * 而合同里存的是业务名（`背景`、`接口`）。编号是表达形式，不是标识：作者按阅读
 * 习惯加编号是对的，合同不该跟着存两套名字。
 *
 * 所以**每一处拿标题做比较的地方都过这个函数**：章标题与顺序、附录定位、
 * 附录小节名、语言红线的作用域边界、落点归章。逐处放宽是上一版的做法——
 * 放宽了三处、漏了第四处，结果整个附录被当成主叙事扫，报出几十条本该允许的标识。
 *
 * 剥两种前缀，都要求**后面跟空白**，且数字形态必须带点或分级：
 *   - `1. ` / `10. ` / `4.1 ` / `8.2.1 `
 *   - `A. ` / `B、`
 * 「2026 年改版」这种以数字开头的正常标题不被误剥（无点且非分级）。
 */

/** `1. ` `10. ` `4.1 ` `8.2.1 ` —— 单级须带点，分级可省略尾点。 */
const NUMBER_PREFIX = /^(?:\d+(?:\.\d+)+|\d+\.)\s*/;

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
 * 就够了。写在模板里的编号要求两轮实测：顺境的那份做了，逆境的那份整章丢光——
 * 无判据的形态必丢，而这件事根本不需要人来做。
 *
 * **幂等**：先剥旧号再编，已经对的文件重跑逐字节不变；乱号、缺号、半带号一并归位。
 * 附录小节的字母序号不重编——那是合同的附录小节判据管的地方，这里不插手。
 *
 * @param {string} text story 全文
 * @param {{title:string, appendix?:boolean}[]} chapters 合同章序
 * @returns {string}
 */
export function renumberStory(text, chapters = []) {
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
        // 合同里没有的章原样留着：那是 check ① 要点名的事，不是编号该悄悄接受的
        return chapterNo ? `## ${chapterNo}. ${name}` : raw;
      }
      if (!chapterNo || inAppendix) return raw;
      if (level === 3) { sub += 1; subsub = 0; return `### ${chapterNo}.${sub} ${name}`; }
      if (!sub) return raw;       // 没有上级小节的 H4 编不出号，留给判据说话
      subsub += 1;
      return `#### ${chapterNo}.${sub}.${subsub} ${name}`;
    }

    return raw.replace(/!\[([^\]]*)\]/g, (whole, alt) => {
      figure += 1;
      const title = String(alt).replace(FIGURE_PREFIX, '').trim();
      return `![${title ? `图 ${figure} · ${title}` : `图 ${figure}`}]`;
    });
  }).join('\n');
}
