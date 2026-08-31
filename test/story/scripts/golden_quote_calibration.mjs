/**
 * 金样双向校准：句边界判会不会误拦「尽职裁决者本来就会抄的那些引文」。
 *
 * 判据从病反推，容易只顾拦住坏形态而拦掉好形态。所以正面也要有一次全量灌注：
 * 把金样每一章里**每一句完整的话**与**每一个表格整格**当成引文送进判定，
 * 一条都不该被点名。拦金样即判据错——这个脚本就是那条线的执行体。
 *
 * 用法：node golden_quote_calibration.mjs <story.md 路径>
 * 输出：JSON { candidates, rejected: [{ chapter, kind, quote, okStart, okEnd }] }
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BUILD = path.join(HERE, '..', '..', '..', 'doc', 'extensions', 'skills',
  'story', 'scripts', 'story-build.mjs');
const { normQuote, quoteBounds } = await import(`file://${BUILD.split(path.sep).join('/')}`);
const HEADINGS = path.join(path.dirname(BUILD), 'headings.mjs');
const { normalizeHeading } = await import(`file://${HEADINGS.split(path.sep).join('/')}`);

const MIN_QUOTE = 12;

/** 按 `##` 切章——判据也是按章取正文的，校准要用同一个切法。 */
function chapters(text) {
  const out = [];
  let cur = null;
  for (const line of String(text).split(/\r?\n/)) {
    const m = line.match(/^##\s+(.+)$/);
    if (m) { cur = { title: normalizeHeading(m[1].trim()), lines: [] }; out.push(cur); continue; }
    if (cur) cur.lines.push(line);
  }
  return out.map(c => ({ title: c.title, body: c.lines.join('\n') }));
}

/** 一章里裁决者能合法抄到的引文：整句 + 整格。 */
function candidates(body) {
  const out = [];
  let inFence = false;
  for (const raw of body.split(/\r?\n/)) {
    const line = raw.trim();
    if (/^(```|~~~)/.test(line)) { inFence = !inFence; continue; }
    // 图片引用整行是 markdown 语法，不是可抄的话——裁决者引的是承接它的那一句
    if (inFence || !line || line.startsWith('#') || line.startsWith('![')) continue;
    if (line.startsWith('|')) {
      for (const cell of line.replace(/^\||\|$/g, '').split('|')) {
        const s = cell.replace(/[`*]/g, '').trim();
        if (!s || /^[-: ]*$/.test(s)) continue;
        if (normQuote(s).length >= MIN_QUOTE) out.push({ kind: 'cell', quote: s });
      }
      continue;
    }
    // 列表标记与段首粗体导语都剥掉：它们不是句子的一部分，裁决者抄的是那句话
    const prose = line.replace(/^[-*+]\s+/, '').replace(/^\d+[.)]\s+/, '');
    for (const piece of prose.split(/(?<=[。？！；])/)) {
      const s = piece.replace(/[`*]/g, '').trim();
      if (!s) continue;
      const bare = s.replace(/[。？！；]$/, '');
      if (normQuote(bare).length >= MIN_QUOTE) out.push({ kind: 'sentence', quote: bare });
    }
  }
  return out;
}

const storyPath = process.argv[2];
if (!storyPath) { console.error('用法: golden_quote_calibration.mjs <story.md>'); process.exit(2); }
const text = fs.readFileSync(storyPath, 'utf-8');

let total = 0;
const rejected = [];
for (const chapter of chapters(text)) {
  for (const cand of candidates(chapter.body)) {
    total += 1;
    const bounds = quoteBounds(chapter.body, cand.quote);
    if (!bounds.found || !bounds.okStart || !bounds.okEnd) {
      rejected.push({
        chapter: chapter.title, kind: cand.kind,
        quote: cand.quote.slice(0, 40),
        found: bounds.found, okStart: bounds.okStart, okEnd: bounds.okEnd,
      });
    }
  }
}
console.log(JSON.stringify({ candidates: total, rejected }, null, 1));
