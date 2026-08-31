/**
 * 把句边界判打在一份**已有的实跑存档**上：那一轮交上来的引文，现在还站得住吗。
 *
 * 判据是冲着真实的病去的，所以要拿真实产物验：F4 那轮的引文是从落点章里切出来的
 * 十二字窗口，判据加上之后应当条条被点名。存档一个字不改，只读。
 *
 * 用法：node replay_quote_bounds.mjs <artifact 目录>
 *   （目录下须有 AR/story.md 与 AR/story-src/{audit.json,story-verdicts.md}）
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

function chapters(text) {
  const out = new Map();
  let cur = null;
  const buf = [];
  for (const line of String(text).split(/\r?\n/)) {
    const m = line.match(/^##\s+(.+)$/);
    if (m) {
      if (cur) out.set(cur, buf.join('\n'));
      cur = normalizeHeading(m[1].trim());
      buf.length = 0;
      continue;
    }
    if (cur) buf.push(line);
  }
  if (cur) out.set(cur, buf.join('\n'));
  return out;
}

/** 裁决产物的逐单元表：单元键 → 引文。 */
function unitQuotes(text) {
  const out = new Map();
  let mode = null;
  for (const raw of String(text).split(/\r?\n/)) {
    const s = raw.trim();
    if (!s.startsWith('|')) continue;
    const c = s.replace(/^\||\|$/g, '').split('|').map(x => x.replace(/[`*]/g, '').trim());
    if (/^[-: ]*$/.test(c[0])) continue;
    if (c[0] === '单元键') { mode = 'units'; continue; }
    if (c[0] === '章') { mode = null; continue; }
    if (mode === 'units' && c.length >= 3) out.set(c[0], { verdict: c[1], quote: c[2] });
  }
  return out;
}

const root = process.argv[2];
if (!root) { console.error('用法: replay_quote_bounds.mjs <artifact 目录>'); process.exit(2); }
const story = fs.readFileSync(path.join(root, 'AR', 'story.md'), 'utf-8');
const audit = JSON.parse(fs.readFileSync(
  path.join(root, 'AR', 'story-src', 'audit.json'), 'utf-8'));
const verdicts = unitQuotes(fs.readFileSync(
  path.join(root, 'AR', 'story-src', 'story-verdicts.md'), 'utf-8'));
const body = chapters(story);

const stat = { author_rows: 0, named: 0, passed: 0, too_short: 0, not_found: 0 };
const samples = [];
for (const rec of audit.records ?? []) {
  if (rec.by !== 'author' || !rec.at) continue;
  const row = verdicts.get(rec.key);
  if (!row || row.verdict !== '讲清') continue;
  stat.author_rows += 1;
  const chapter = body.get(rec.at) ?? '';
  const q = normQuote(row.quote);
  if (q.length < MIN_QUOTE) { stat.too_short += 1; stat.named += 1; continue; }
  const bounds = quoteBounds(chapter, row.quote);
  if (!bounds.found) { stat.not_found += 1; stat.named += 1; continue; }
  if (bounds.okStart && bounds.okEnd) { stat.passed += 1; continue; }
  stat.named += 1;
  if (samples.length < 5) {
    samples.push({ key: rec.key, at: rec.at, quote: row.quote.slice(0, 32),
                   okStart: bounds.okStart, okEnd: bounds.okEnd });
  }
}
console.log(JSON.stringify({ artifact: root, ...stat,
  named_ratio: stat.author_rows ? +(stat.named / stat.author_rows).toFixed(3) : 0,
  samples }, null, 1));
