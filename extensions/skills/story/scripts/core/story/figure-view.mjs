/**
 * story.md 里的图：Mermaid 是唯一语义真源，SVG 是同一张图在本地的阅读视图 —— 一份文档两种形态。
 *
 * 选中的图由一对管理标记包起来，标记之间只放两种内容之一：
 *
 *     <!-- story-figure:<ID>:begin -->
 *     ```mermaid            ← Mermaid 形态：与 AR/story-src/figures/<ID>.mmd 逐字相同
 *     …
 *     ```
 *     <!-- story-figure:<ID>:end -->
 *
 *     <!-- story-figure:<ID>:begin -->
 *     ![…](figures/<ID>.svg) ← SVG 形态：引用 AR/figures/<ID>.svg
 *     <!-- story-figure:<ID>:end -->
 *
 * 图前图后的正文在标记之外，切换不碰。ID 是图在文档里的身份，章节移动、重编号都不改它。
 *
 * `.mmd` 一建成就是这张图唯一的语义真源，正文管理块只是按它派生。
 *
 * - `mermaid`：把每块还原成 `.mmd` 的原文；合法的 Mermaid 块文字与源不同，也按源重铺并说明（不猜是谁改的）。
 *   正式登记、审查、update 比较与归档都先走这一步。
 * - `svg`：只把有阅读图、结构核过、来源快照与当前 `.mmd` 相同、且局部阅读验收通过的那几块切过去；其余保持 Mermaid 并说明原因。
 * - `toggle`：任何一块是 SVG 就整篇切回 Mermaid，全是 Mermaid 就切到可用的阅读图（一键入口用它）。
 * - `prepare`：给还没管理的 Mermaid 围栏加标记、首次写 `.mmd`（同 ID 的源已在且不同就停）；
 *   带 `--id` 时从已有 `.mmd` 重建这一块，从不拿正文覆盖源。
 *   不编造 SVG——阅读图由作者按六类指导重述，再过结构、渲染与对照三道核。
 *
 * 管理块结构坏了（孤立标记、重复 ID、块里既不是一个 Mermaid 围栏也不是登记的引用、源缺失）就整次不写，
 * 点名 ID 与行号；不按相似文本猜配对，也不覆盖块外正文。边界还认得出、源还在时，`prepare --id` 从源重建这一块。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { fenceRanges } from './document.mjs';
import { runPython } from '../flow/client.mjs';
import { readingRequest, readingState, reviewTask } from './figure-reading.mjs';

export const VIEW_MODES = ['prepare', 'mermaid', 'svg', 'toggle', 'status', 'review-request', 'review-check'];
const MARK = /^<!-- story-figure:([A-Za-z0-9][\w-]*):(begin|end) -->$/;
const FIGURE_CHECK = path.join(path.dirname(fileURLToPath(import.meta.url)), 'figure-check.py');
const RECOVER = '改图义改 AR/story-src/figures/<ID>.mmd，它是唯一真源，正文管理块按它重铺；'
  + '管理块结构坏了而边界还认得出、源还在，跑 `story-build view --mode prepare --id <ID>` 从源重建这一块；'
  + '源丢了从备份或真实依据恢复 .mmd，不从正文反写。管理块是脚本管理区，不要手改'

const paths = (featureRoot, id) => ({
  src: path.join(featureRoot, 'AR', 'story-src', 'figures', `${id}.mmd`),
  svg: path.join(featureRoot, 'AR', 'figures', `${id}.svg`),
});
const readOr = (file) => { try { return fs.readFileSync(file, 'utf-8'); } catch { return null; } };
//: 源与快照按内容比：行尾在不同机器上不同，不算图变了
const lf = (text) => (text === null ? null : text.replace(/\r\n/g, '\n'));
const mermaidBody = (src) => ['```mermaid', ...src.replace(/\r?\n$/, '').split(/\r?\n/), '```'];
const svgRef = (id) => new RegExp(`^!\\[[^\\]]*\\]\\(figures/${id}\\.svg\\)$`);

/** 管理块：成对的标记与之间的行。标记出问题一次列全。 */
function figureBlocks(lines) {
  const fenced = new Set(fenceRanges(lines).flatMap(f => Array.from({ length: f.to - f.from + 1 }, (_, k) => f.from + k)));
  const blocks = [];
  const problems = [];
  let open = null;
  lines.forEach((line, i) => {
    const m = !fenced.has(i) && MARK.exec(line.trim());
    if (!m) return;
    const [, id, side] = m;
    if (side === 'begin') {
      if (open) problems.push(`第 ${open.from + 1} 行的图块 ${open.id} 没有结束标记就又开了 ${id}`);
      open = { id, from: i };
    } else if (!open || open.id !== id) {
      problems.push(`第 ${i + 1} 行是图块 ${id} 的结束标记，前面没有对应的开始标记`);
    } else {
      blocks.push({ ...open, to: i, body: lines.slice(open.from + 1, i) });
      open = null;
    }
  });
  if (open) problems.push(`第 ${open.from + 1} 行的图块 ${open.id} 没有结束标记`);
  const seen = new Set();
  for (const b of blocks) {
    if (seen.has(b.id)) problems.push(`图块 ${b.id} 出现了不止一次——ID 是图在文档里的身份，一张图一个`);
    seen.add(b.id);
  }
  return { blocks, problems };
}

/** 块现在是哪种形态：mermaid / svg / 其它。 */
function formOf(block) {
  const b = block.body;
  // 块内恰好一个完整围栏、从第一行到最后一行：首尾像围栏而中间已闭合、夹着正文或第二段围栏的，是结构坏了
  const fences = fenceRanges(b);
  if (b[0] === '```mermaid' && b[b.length - 1] === '```' && fences.length === 1
      && fences[0].closed && fences[0].from === 0 && fences[0].to === b.length - 1) return 'mermaid';
  if (b.length === 1 && svgRef(block.id).test(b[0])) return 'svg';
  return null;
}

/** 视图记下的来源快照：`<metadata>` 里的 Mermaid 原文（可包在 CDATA 里）。 */
function snapshotOf(svgText) {
  const m = /<metadata[^>]*>([\s\S]*?)<\/metadata>/.exec(svgText ?? '');
  if (!m) return null;
  const inner = m[1].trim();
  const cdata = /^<!\[CDATA\[([\s\S]*?)\]\]>$/.exec(inner);
  return lf(cdata ? cdata[1] : inner).trim();
}

/** 阅读图的题目：块所在的那一节，让读者知道这是哪一处的图。 */
function titleAt(lines, at) {
  for (let i = at; i >= 0; i -= 1) {
    const h = /^#{2,6}\s+(.+?)\s*$/.exec(lines[i]);
    if (h) return `${h[1].replace(/^[\d.]+\s+/, '')}（阅读图）`;
  }
  return '阅读图';
}

/**
 * 按模式切换或准备。问题非空时一个字节都不写。
 *
 * @param {string} featureRoot 需求目录
 * @param {'prepare'|'mermaid'|'svg'} mode
 * @param {{id?: string}} [opts]
 * @returns {{changed: boolean, problems: string[], notes: string[], counts: Record<string, number>}}
 */
export function switchView(featureRoot, mode, { id = '' } = {}) {
  const storyPath = path.join(featureRoot, 'AR', 'story.md');
  const raw = readOr(storyPath);
  const out = { changed: false, problems: [], notes: [], counts: { mermaid: 0, svg: 0 } };
  if (raw === null) {
    if (mode !== 'mermaid') out.problems.push('AR/story.md 不在：视图作用在成文的 story 上');
    return out;
  }
  const eol = raw.includes('\r\n') ? '\r\n' : '\n';
  const lines = raw.split(/\r?\n/);
  const { blocks, problems } = figureBlocks(lines);
  out.problems.push(...problems);
  if (id && !/^[A-Za-z0-9][\w-]*$/.test(id)) out.problems.push(`--id ${id} 不是合法的图块 ID（字母或数字开头，只含字母、数字、-、_）`);
  const sources = new Map();
  for (const b of blocks) {
    const form = formOf(b);
    const src = lf(readOr(paths(featureRoot, b.id).src));
    const at = `图块 ${b.id}（第 ${b.from + 1}–${b.to + 1} 行）`;
    if (src === null) out.problems.push(`${at} 的源 AR/story-src/figures/${b.id}.mmd 不在：从备份或真实依据恢复源，不从正文反写`);
    // 显式重建这一块时，块里是什么都按源重铺；其余入口只认两种合法形态
    else if (!form && !(mode === 'prepare' && id === b.id)) {
      out.problems.push(`${at} 里既不是一个 Mermaid 围栏，也不是 figures/${b.id}.svg 的引用`);
    }
    sources.set(b.id, src);
  }
  if (mode === 'prepare' && id && !blocks.some(b => b.id === id)) out.problems.push(`没有 ID 为 ${id} 的图块`);
  if (out.problems.length) {
    out.problems = out.problems.map(p => `AR/story.md：${p}——${RECOVER}`);
    return out;
  }
  if (mode === 'toggle') {
    if (!blocks.length) return { ...out, notes: ['这份 story 还没有管理的图：先跑 `story-build view --mode prepare` 给图建源'] };
    return switchView(featureRoot, blocks.some(b => formOf(b) === 'svg') ? 'mermaid' : 'svg');
  }

  const next = [...lines];
  const replace = [];
  const writes = [];
  //: 合法的 Mermaid 块与源文字不同：不猜是谁改的，按源重铺并说出来，不静默丢掉差异
  const differs = (b, done) => out.notes.push(`${b.id}：正文里的图与源 ${b.id}.mmd 不同，${done}——正文块里的改动没有保留，改图义改 .mmd`);
  const refresh = (b) => {
    replace.push({ from: b.from + 1, to: b.to - 1, rows: mermaidBody(sources.get(b.id)) });
    differs(b, '已按源刷新');
  };
  const stale = (b) => formOf(b) === 'mermaid' && mermaidBody(sources.get(b.id)).join('\n') !== b.body.join('\n');
  if (mode === 'prepare') {
    if (id) {
      const b = blocks.find(x => x.id === id);
      replace.push({ from: b.from + 1, to: b.to - 1, rows: mermaidBody(sources.get(id)) });
      out.notes.push(`${id}：已从源 ${id}.mmd 重建这一块`);
    } else {
      const managed = new Set(blocks.flatMap(x => Array.from({ length: x.to - x.from + 1 }, (_, k) => x.from + k)));
      const used = new Set(blocks.map(x => x.id));
      for (const f of fenceRanges(lines)) {
        if (f.lang !== 'mermaid' || !f.closed || managed.has(f.from)) continue;
        const inner = lines.slice(f.from + 1, f.to).join('\n');
        let fid = `fig-${createHash('sha256').update(inner).digest('hex').slice(0, 8)}`;
        for (let k = 2; used.has(fid); k += 1) fid = `${fid.replace(/-\d+$/, '')}-${k}`;
        used.add(fid);
        const have = lf(readOr(paths(featureRoot, fid).src));
        if (have !== null && have !== `${inner}\n`) {
          out.problems.push(`AR/story.md：第 ${f.from + 1} 行的图要建的源 ${fid}.mmd 已在且内容不同——不覆盖已有的源，先查明它属于哪张图`);
          continue;
        }
        replace.push({ from: f.from, to: f.to, rows: [`<!-- story-figure:${fid}:begin -->`, ...mermaidBody(`${inner}\n`), `<!-- story-figure:${fid}:end -->`] });
        writes.push([paths(featureRoot, fid).src, `${inner}\n`]);
      }
      if (out.problems.length) return { ...out, changed: false };
      if (!replace.length) out.notes.push('没有还没管理的 Mermaid 围栏');
    }
  } else {
    for (const b of blocks) {
      const src = sources.get(b.id);
      const form = formOf(b);
      if (mode === 'mermaid') {
        if (form === 'svg') replace.push({ from: b.from + 1, to: b.to - 1, rows: mermaidBody(src) });
        else if (stale(b)) refresh(b);
        continue;
      }
      // 已经显示着的阅读图也过同一道前置：快照相同只说明来源版本相同，图本身可能已被改坏
      const why = viewGap(featureRoot, b.id, src)?.reason;
      if (form === 'svg') {
        if (why) {
          replace.push({ from: b.from + 1, to: b.to - 1, rows: mermaidBody(src) });
          out.notes.push(`${b.id}：${why}，已切回 Mermaid——修好阅读图并过局部阅读验收后再切`);
        }
        continue;
      }
      if (why) {
        if (stale(b)) refresh(b);
        out.notes.push(`${b.id}：${why}，保持 Mermaid`);
        continue;
      }
      if (stale(b)) differs(b, '已切到按当前源重述的阅读图');
      replace.push({ from: b.from + 1, to: b.to - 1, rows: [`![${titleAt(lines, b.from)}](figures/${b.id}.svg)`] });
    }
  }
  for (const r of replace.sort((a, b) => b.from - a.from)) next.splice(r.from, r.to - r.from + 1, ...r.rows);
  for (const [file, text] of writes) {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    if (readOr(file) !== text) fs.writeFileSync(file, text, 'utf-8');
  }
  const after = next.join(eol);
  if (after !== raw) {
    fs.writeFileSync(storyPath, after, 'utf-8');
    out.changed = true;
  }
  const { blocks: now } = figureBlocks(next);
  for (const b of now) out.counts[formOf(b) ?? 'mermaid'] += 1;
  return out;
}

/**
 * 这块能不能切到阅读图：有 SVG、结构核过、来源快照就是当前源、局部阅读验收通过。没有缺口返回 null。
 * 语义等值与可读不在这里判——那是独立审查对着真实渲染图的事，这里只认它的报告绑定当前输入且结论成立。
 */
function viewGap(featureRoot, id, src) {
  const svgGap = svgProblem(featureRoot, id, src);
  if (svgGap) return svgGap;
  const r = readingState(featureRoot, id);
  return r.state === 'ready' ? null : { state: r.state, reason: r.reason };
}

/** SVG 本身立不立得住：在不在、来源快照是不是当前源、结构检查过没过。 */
function svgProblem(featureRoot, id, src) {
  const { svg } = paths(featureRoot, id);
  const text = readOr(svg);
  if (text === null) return { state: 'no-svg', reason: `还没有阅读图 AR/figures/${id}.svg：按 reference/svg.md 依据当前 .mmd 重述` };
  if (snapshotOf(text) !== src.trim()) return { state: 'svg-stale', reason: `阅读图 ${id}.svg 的来源快照（<metadata> 里的 Mermaid 原文）与当前源不同，要按当前源重新重述` };
  const r = runPython(FIGURE_CHECK, [svg, '--id', id]);
  if (r.error) return { state: 'svg-invalid', reason: `结构检查跑不起来（${r.error}）` };
  if (r.status !== 0) return { state: 'svg-invalid', reason: `结构检查没过：${r.output}` };
  return null;
}

/**
 * 本地阅读的工作集合 —— 每次从 Story 实际内容派生，不另存状态：管理块逐张给状态与下一步，
 * 还没管理的 Mermaid 围栏单列（有图却零管理块是「未准备」，不是「不适用」）。没有图才不适用。
 */
export function readingWork(featureRoot) {
  const raw = readOr(path.join(featureRoot, 'AR', 'story.md'));
  if (raw === null) return { applicable: false, complete: false, items: [], unmanaged: [], problems: ['AR/story.md 不在'] };
  const lines = raw.split(/\r?\n/);
  const { blocks, problems } = figureBlocks(lines);
  const managed = new Set(blocks.flatMap(b => Array.from({ length: b.to - b.from + 1 }, (_, k) => b.from + k)));
  const unmanaged = fenceRanges(lines).filter(f => f.lang === 'mermaid' && f.closed && !managed.has(f.from)).map(f => f.from + 1);
  const items = blocks.map((b) => {
    const src = lf(readOr(paths(featureRoot, b.id).src));
    const gap = src === null ? { state: 'no-source', reason: `源 ${b.id}.mmd 不在` } : viewGap(featureRoot, b.id, src);
    return { id: b.id, line: b.from + 1, state: gap?.state ?? 'ready', reason: gap?.reason ?? '' };
  });
  return { applicable: items.length > 0 || unmanaged.length > 0,
    complete: !problems.length && !unmanaged.length && items.every(i => i.state === 'ready'), items, unmanaged, problems };
}

/** 生成某张图的局部验收请求：块与源在、SVG 本身立得住才发；返回请求与交给独立审查者的任务。 */
export function reviewRequest(projectRoot, featureRoot, id, render) {
  const src = lf(readOr(paths(featureRoot, id).src));
  if (src === null) return { problems: [`没有图 ${id} 的源 AR/story-src/figures/${id}.mmd`] };
  const gap = svgProblem(featureRoot, id, src);
  if (gap) return { problems: [gap.reason] };
  const r = readingRequest(featureRoot, id, render);
  return r.problems.length ? r : { ...r, task: reviewTask(projectRoot, featureRoot, r.request) };
}

/**
 * 一键切换入口：AR/ 下按合同登记的文件名生成，只覆盖带生成标记的同名文件；用户自己的同名文件保留并报冲突。
 * 入口从自身位置向上找工程配置，按 features_dir 核需求位置、extension_dir 找核心，不依赖 cwd 与绝对路径。
 */
export function writeLauncher(featureRoot, name) {
  if (!name) return null;
  const file = path.join(featureRoot, 'AR', name);
  const body = LAUNCHER.join('\r\n') + '\r\n';
  const have = readOr(file);
  if (have === body) return null;
  if (have !== null && !have.includes(LAUNCHER_MARK)) return `AR/${name} 已存在且不是本机制生成的，保留不动——一键切换入口没有写`;
  fs.writeFileSync(file, body, 'utf-8');
  return null;
}

const LAUNCHER_MARK = 'story-reading-launcher';
//: 入口脚本只用 node 内联：不拼 shell、不要求改执行策略；参数逐个传，路径带空格与特殊字符照样成立
const LAUNCHER = [
  '@echo off',
  'chcp 65001 >nul',
  `rem ${LAUNCHER_MARK}：由 story-build 生成，双击在 Mermaid 与本地阅读图之间切换`,
  'node -e "const p=require(\'path\'),fs=require(\'fs\'),cp=require(\'child_process\');'
    + 'const ar=p.resolve(process.argv[1]);let d=ar;'
    + 'while(!fs.existsSync(p.join(d,\'framework.config.json\'))){const u=p.dirname(d);if(u===d){console.error(\'找不到 framework.config.json：入口要放在接入了 framework 的工程里\');process.exit(2)}d=u}'
    + 'let c;try{c=JSON.parse(fs.readFileSync(p.join(d,\'framework.config.json\'),\'utf8\')).paths??{}}catch(e){console.error(\'framework.config.json 读不出：\'+e.message);process.exit(2)}'
    + 'const f=p.dirname(ar);if(p.resolve(d,c.features_dir??\'doc/features\')!==p.dirname(f)){console.error(\'这个需求不在工程配置的需求目录下：\'+f);process.exit(2)}'
    + 'const s=p.join(d,c.extension_dir??\'doc/extensions\',\'skills\',\'story\',\'scripts\',\'core\',\'story-build.mjs\');'
    + 'const r=cp.spawnSync(process.execPath,[s,\'view\',\'--mode\',\'toggle\',\'--feature\',p.basename(f),\'--project-root\',d],{stdio:\'inherit\'});'
    + 'process.exit(r.status??2)" "%~dp0."',
  'pause',
];

/** 正式入口用：先切回 Mermaid，坏了按原话报。 */
export function ensureMermaid(featureRoot) {
  const storyPath = path.join(featureRoot, 'AR', 'story.md');
  const raw = readOr(storyPath);
  if (raw === null || !raw.includes('<!-- story-figure:')) return { changed: false, problems: [], notes: [] };
  return switchView(featureRoot, 'mermaid');
}
