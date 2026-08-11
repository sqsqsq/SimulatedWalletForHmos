/**
 * merge-story.mjs — 归档件 AR/story.md / AR/review.md 的门禁（确定性部分，零 AI）
 *
 * ── 一个动作 ──────────────────────────────────────────────────────────
 *   --check  门禁校验（两项：可标识事实覆盖不丢 + 归档红线）
 *
 *   --init 与 --stamp 均已退役。story 的起手与装配由 story-build.mjs 承担：
 *   scaffold 按章节合同注入源材料，build 逐章装配。整文件复制只保证初稿完整，
 *   保证不了终稿；章节粒度才能让源与终稿逐章可对照。
 *
 * ── 门禁只拦「评审者自己发现不了的伤害」 ────────────────────────────────
 * 形式好不好、叙述顺不顺、理由充不充分——评审者一眼就能看出来，那正是评审要干的事。
 * 脚本越细，模型越为门禁写作：它会转而研究检查器，而不是研究读者。
 *
 * 用法：node merge-story.mjs --feature <name> [--project-root <abs>] --check
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { scanBannedTerms, scanLocalPaths, scanDanglingRefs, formatHits } from './lint-rules.mjs';

// ---------------------------------------------------------------------------
// 基础设施

function parseArgs(argv) {
  const args = { check: false, init: false };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--feature') args.feature = argv[++i];
    else if (a === '--project-root') args.projectRoot = argv[++i];
    else if (a === '--check') args.check = true;
    else if (a === '--init') args.init = true;
  }
  return args;
}

function fail(msg) {
  console.error(`[merge-story] ${msg}`);
  process.exit(1);
}

const stripBom = s => s.replace(/^﻿/, '');

function featuresDir(projectRoot) {
  try {
    const cfg = JSON.parse(fs.readFileSync(path.join(projectRoot, 'framework.config.json'), 'utf-8'));
    if (typeof cfg?.paths?.features_dir === 'string' && cfg.paths.features_dir.trim()) {
      return cfg.paths.features_dir.trim();
    }
  } catch {
    /* 回落默认 */
  }
  return 'doc/features';
}

/**
 * 决策件的确认状态。
 * @returns {'draft'|'confirmed'|null} null 表示状态行缺失或写法不合法
 */
function parseReviewStatus(text) {
  const m = text.match(/^\*\*状态\*\*[:：]\s*(.+?)\s*$/m);
  if (!m) return null;
  const v = m[1].trim();
  if (v.startsWith('已确认')) return 'confirmed';
  if (v.startsWith('草稿')) return 'draft';
  return null;
}

/** 按标题关键词提取章节（body 不含标题行，到下一个同级或更高级标题为止；容忍编号差异） */
function extractSection(text, keywordRegex) {
  let inFence = false;
  const lines = text.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    if (/^\s*(```|~~~)/.test(lines[i])) inFence = !inFence;
    if (inFence) continue;
    const h = lines[i].match(/^(#{1,4})\s+(.*)$/);
    if (!h) continue;
    if (!keywordRegex.test(h[2].replace(/^[\d.、]+\s*/, ''))) continue;
    const level = h[1].length;
    const body = [];
    let fence = false;
    for (let j = i + 1; j < lines.length; j++) {
      if (/^\s*(```|~~~)/.test(lines[j])) fence = !fence;
      if (!fence) {
        const nh = lines[j].match(/^(#{1,6})\s/);
        if (nh && nh[1].length <= level) break;
      }
      body.push(lines[j]);
    }
    return { heading: lines[i], body: body.join('\n').trim() };
  }
  return null;
}

/** Markdown 表格行 → 单元格；分隔行与非表格行返回 null */
function tableCells(line) {
  const t = line.trim();
  if (!t.startsWith('|')) return null;
  if (/^\|[\s:|-]+\|$/.test(t)) return null;
  const cells = t.split(/(?<!\\)\|/);
  cells.shift();
  if (cells.length && cells[cells.length - 1].trim() === '') cells.pop();
  return cells.map(c => c.trim());
}

// ---------------------------------------------------------------------------
// 路径与输入

const args = parseArgs(process.argv);
if (!args.feature) fail('缺少 --feature <name>');
if (args.init) {
  fail('--init 已退役：story 改为逐章装配。请用 '
    + 'story-build.mjs scaffold --feature <name> 起手，逐章转写后 build。');
}
if (!args.check) fail('须指定模式：--check（门禁校验）');

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
// scripts → story → skills → extensions → doc → 实例根
const projectRoot = path.resolve(args.projectRoot ?? path.join(scriptDir, '..', '..', '..', '..', '..'));
const featureRoot = path.join(projectRoot, featuresDir(projectRoot), args.feature);
const specDir = path.join(featureRoot, 'spec');
const specPath = path.join(specDir, 'spec.md');
const reviewPath = path.join(featureRoot, 'AR', 'review.md');
const storyPath = path.join(featureRoot, 'AR', 'story.md');

if (!fs.existsSync(specPath)) fail(`需求规格不存在：${specPath}`);
const specText = stripBom(fs.readFileSync(specPath, 'utf-8'));

// ---------------------------------------------------------------------------
// --check 的共同输入

if (!fs.existsSync(reviewPath)) {
  fail(`AR/review.md 不存在：${reviewPath}（人的决策件，与 spec.md / story.md 同批产出）`);
}
if (!fs.existsSync(storyPath)) {
  fail(`AR/story.md 不存在：${storyPath}（先用 story-build.mjs scaffold 起手，逐章转写后 build）`);
}

const reviewText = stripBom(fs.readFileSync(reviewPath, 'utf-8'));
const storyRaw = stripBom(fs.readFileSync(storyPath, 'utf-8'));
const status = parseReviewStatus(reviewText) ?? '(状态行缺失)';

// ---------------------------------------------------------------------------
// --check：只拦「评审者发现不了的伤害」——覆盖不丢 + 归档红线。

const story = storyRaw;
const problems = [];

// ── 1. 覆盖不丢 —— 少了什么，评审者不知道 ───────────────────────────────
// 判据是**覆盖**不是**逐字一致**：每个可标识事实在 story 全文任意位置有落点即可。
{
  const missing = [];
  const check = (label, items) => {
    const lost = [...new Set(items)].filter(x => x && !story.includes(x));
    if (lost.length > 0) missing.push(`${label}缺 ${lost.join('、')}`);
  };

  check('编号', specText.match(/\b(?:S\d+|F\d+|E\d+|AC-[\w]*\d+|BD-\d+|NFR-\d+)\b/g) ?? []);

  const gloss = extractSection(specText, /术语映射表/);
  check(
    '术语',
    [...(gloss?.body ?? '').split(/\r?\n/)]
      .map(tableCells)
      .filter(c => c && c.length >= 2 && !/^原始术语$|^术语$/.test(c[0]))
      .map(c => c[0].replace(/\*\*|`/g, '').trim())
  );

  // 技术契约五节各表首列：接口名 / 存储键 / 配置项 / 事件 / 依赖
  const contract = extractSection(specText, /技术契约/);
  const lines = (contract?.body ?? '').split(/\r?\n/);
  const keys = [];
  for (let i = 0; i < lines.length; i++) {
    const cells = tableCells(lines[i]);
    if (!cells || cells.length < 2) continue;
    if (/^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1] ?? '')) continue; // 表头行
    const key = cells[0].replace(/\*\*|`/g, '').replace(/[（(][^（()）]*[）)]\s*$/, '').trim();
    if (key && !/^(—|-|不涉及)$/.test(key)) keys.push(key);
  }
  check('技术契约标识', keys);

  for (const m of missing) {
    problems.push(
      `共有区未全量落入 story：${m}` +
        '（判据是「在 story 全文任意位置有落点」，可整合、可改序、可换措辞，但不能少）'
    );
  }
}

// ── 2. 归档件红线 —— 点不开的引用，评审者不知道是坏的 ────────────────────
for (const [label, text] of [
  ['story', story],
  ['review', reviewText],
]) {
  for (const [what, kind, hits] of [
    ['仓内路径', 'local', scanLocalPaths(text)],
    ['客户端语境禁用词', 'banned', scanBannedTerms(text)],
    ['悬空引用', 'dangling', scanDanglingRefs(text)],
  ]) {
    if (hits.length > 0) problems.push(`${label} 出现${what} ${hits.length} 处：${formatHits(hits, kind)}`);
  }
}

// ---------------------------------------------------------------------------

if (problems.length > 0) {
  console.error(`[merge-story] 校验未通过（${problems.length} 项）：`);
  for (const p of problems) console.error(`  - ${p}`);
  process.exit(1);
}
console.log(`[merge-story] ✅ 校验通过：${storyPath}`);
console.log(`[merge-story] status=${status}`);