/**
 * Markdown 链接的完整目标读法 —— 只依赖字符串，导入、来源展开、图片核对与 Story 检查共用这一份。
 */

/**
 * 一行里的 markdown 链接：`[文字](目标)` 与 `![文字](目标)`。
 *
 * 目标有两种合法写法：`<…>` 包起来的（可含空格与括号），或不含空白、括号成对的。
 * 真实文件名常带空格、中文与括号，只认 `[^)\s]+` 会把它们切断或漏掉——那一份材料就从核对里消失。
 * 看得见 `](` 却解析不出目标的，作为 `bad` 带位置交回，由调用方报「写法解析不了」，不猜。
 * 表格里的 `\|` 是转义竖线，目标里还原成 `|`。
 *
 * @returns {{links: {start:number, end:number, text:string, target:string, image:boolean}[], bad: {start:number, text:string}[]}}
 */
export function markdownLinks(line) {
  const s = String(line ?? '');
  const links = [], bad = [];
  let i = 0;
  while ((i = s.indexOf('](', i)) >= 0) {
    const open = s.lastIndexOf('[', i);
    let j = i + 2, target = null;
    if (s[j] === '<') {
      const close = s.indexOf('>', j);
      if (close > j && s[close + 1] === ')') { target = s.slice(j + 1, close); j = close + 2; }
    } else {
      let depth = 0, k = j;
      for (; k < s.length; k++) {
        const c = s[k];
        if (c === '\\') { k++; continue; }
        if (/\s/.test(c)) break;
        if (c === '(') depth++;
        else if (c === ')') { if (!depth) break; depth--; }
      }
      if (s[k] === ')' && k > j) { target = s.slice(j, k); j = k + 1; }
    }
    const from = open >= 0 && s[open - 1] === '!' ? open - 1 : Math.max(open, 0);
    if (target === null) {
      bad.push({ start: from, text: s.slice(from, i + 30) });
      i += 2;
      continue;
    }
    links.push({ start: from, end: j, text: s.slice(open + 1, i), target: target.replace(/\\([|()])/g, '$1'),
      image: s[from] === '!' });
    i = j;
  }
  return { links, bad };
}
