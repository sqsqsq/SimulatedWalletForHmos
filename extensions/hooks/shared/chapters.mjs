/**
 * 本文的章节编号与带号引用 —— 只核文档自己写的号与自己的标题对不对得上，不定一套固定章号。
 *
 * 不要求每个标题都编号，也不要求序号连续或从 1 开始；无号的章（Scope、宿主扩展章、附录）不替它造号。
 * 父节按实际 Markdown 层级取，围栏里的标题不算（`parseDocument` 已排除）。
 */
import { normalizeHeading, parseDocument } from '../../skills/story/scripts/core/story/document.mjs';

const NUMBER = /^(\d+(?:\.\d+)*)\.?\s+/;

/**
 * 带号子节以它所属的带号父节号开头；同一父节下两个标题同号是歧义（带号引用指不清是哪一个）。
 * 父节无号时不按它核子节号。
 *
 * @param {string} text 被核的文档
 * @returns {string[]} 问题，每条说清哪一节、挂在哪、号是什么
 */
export function chapterNumberProblems(text) {
  const problems = [];
  const open = [];                     // 按层级：当前打开的那个标题
  const used = new Map();              // 父节位置 + 号 → 先出现的那个标题
  for (const h of parseDocument(text).headings.filter(x => x.level >= 2)) {
    open.length = h.level;
    const parent = open.slice(2, h.level).filter(Boolean).pop() ?? null;
    open[h.level] = h;
    const got = NUMBER.exec(h.raw)?.[1];
    if (!got) continue;
    const up = parent && NUMBER.exec(parent.raw)?.[1];
    if (up && !got.startsWith(`${up}.`)) {
      problems.push(`「${'#'.repeat(h.level)} ${h.raw}」挂在「${'#'.repeat(parent.level)} ${parent.raw}」下，号却是 ${got}——带号子节以父节号开头`);
    }
    const key = `${parent?.at ?? -1}:${got}`;
    if (used.has(key)) {
      problems.push(`「${'#'.repeat(h.level)} ${h.raw}」与第 ${used.get(key).at + 1} 行的「${used.get(key).raw}」同号——同一层下号要唯一，带号引用才指得清`);
    } else used.set(key, h);
  }
  return problems;
}

/**
 * 表里某一列写「号. 章名」引用本文的章时，号与章名指本文同一个二级标题（章名按 `normalizeHeading` 规范化后相等）。
 * 只核带号的引用；只写章名、写链接的格子不在这里判。表头没有这一列就没有这项引用。
 *
 * @param {string} text 本文
 * @param {string} column 表头里含这个词的那一列
 */
export function chapterRefProblems(text, column) {
  const doc = parseDocument(text);
  const chapters = doc.headings.filter(h => h.level === 2).map(h => ({ number: NUMBER.exec(h.raw)?.[1] ?? null, name: h.name }));
  const problems = [];
  for (const t of doc.tables) {
    const i = t.header.findIndex(h => h.includes(column));
    if (i < 0) continue;
    for (const row of t.rows) {
      const m = /^(\d+)[.、]\s*([^（(|]+)/.exec(String(row[i] ?? '').replace(/[`*]/g, '').trim());
      if (!m) continue;
      const name = normalizeHeading(m[2]);
      const actual = chapters.find(c => c.number === m[1]);
      if (actual?.name === name) continue;
      const real = chapters.find(c => c.name === name);
      problems.push(`「${column}」列的「${m[1]}. ${name}」对不上本文的章：`
        + (real ? `「${name}」在本文是${real.number ? `第 ${real.number} 章` : '无号的章'}` : `本文第 ${m[1]} 章是「${actual?.name ?? '（没有）'}」`)
        + '——带号引用的号与章名指本文同一个二级标题');
    }
  }
  return [...new Set(problems)];
}
