/**
 * story.md 里由脚本管理的正式图 —— 一张图一个 ID，`AR/story-src/figures/<ID>.mmd` 是唯一语义真源。
 *
 * 图块里一次只放一种形态：与源逐字相同的一个 Mermaid 围栏（正式形态），或同 ID 增强阅读 SVG 的一行引用（阅读形态）：
 *
 *     <!-- story-figure:<ID>:begin -->
 *
 *     ```mermaid                      或      ![<ID>](figures/<ID>.svg)
 *     …
 *     ```
 *
 *     <!-- story-figure:<ID>:end -->
 *
 * SVG 是同一张图的增强阅读形态：同样的事实，布局、分组、层次与标注更清楚，不追加业务关系；
 * 它过了独立文本审查（`figure-reading.mjs`）才显示。标记与两侧内容的分隔空行由 `separateMarks` 统一铺。
 *
 * - `prepare`：给还没管理的 Mermaid 围栏加标记、首次写 `.mmd`（同 ID 的源已在且不同就停）；带 `--id` 从已有 `.mmd`
 *   重建这一块（从不拿正文覆盖源）。
 * - `mermaid`：全部图块按源还原 Mermaid（合法块文字与源不同也按源重铺并说明）。正式登记、审查、update 比较与归档都先走这一步。
 * - `svg`：审查成立的图换成 SVG 引用，其余保持 Mermaid 并说明原因。
 * - `toggle`：有任一块在 SVG 就全部还原，否则显示可用的（一键入口用它）。
 *
 * 结构坏了（孤立标记、重复 ID、块里既不是一个 Mermaid 围栏也不是本图的 SVG 引用、源缺失）整次不写，点名 ID 与行号；
 * 不按相似文本猜配对，不覆盖块外正文。旧版的补充阅读槽（`story-reading`）本版不认：旧版收口或从 init 重起。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { createHash } from 'node:crypto';
import { fenceRanges, FIGURE_MARK, markPairs, separateMarks } from './document.mjs';
import { markdownLinks } from './language.mjs';
import { joinPosix, registeredPaths } from './sources.mjs';
import { enhanced, lf, mermaidBody, readOr, readingRequest, readingState, reviewTask, srcPath, svgFacts } from './figure-reading.mjs';

export const VIEW_MODES = ['prepare', 'mermaid', 'svg', 'toggle', 'status', 'review-request', 'review-check'];
const ID = /^[A-Za-z0-9][\w-]*$/;
const OLD_SLOT = /^<!-- story-reading:[A-Za-z0-9][\w-]*:(begin|end) -->$/;
const RECOVER = '改图义改 AR/story-src/figures/<ID>.mmd，它是唯一真源，正文管理块按它重铺；'
  + '管理块结构坏了而边界还认得出、源还在，跑 `story-build view --mode prepare --id <ID>` 从源重建这一块；'
  + '源丢了从备份或真实依据恢复 .mmd，不从正文反写。管理块是脚本管理区，不要手改';

const rowsOf = x => Array.from({ length: x.to - x.from + 1 }, (_, k) => x.from + k);
const refLine = id => `![${id}](figures/${id}.svg)`;

/** 块现在是什么：一个完整 Mermaid 围栏、本图 SVG 的一行引用、或别的。 */
function formOf(block) {
  const b = block.body;
  // 块内恰好一个完整围栏、从第一行到最后一行：首尾像围栏而中间已闭合、夹着正文或第二段围栏的，是结构坏了
  const fences = fenceRanges(b);
  if (b[0] === '```mermaid' && b[b.length - 1] === '```' && fences.length === 1
      && fences[0].closed && fences[0].from === 0 && fences[0].to === b.length - 1) return 'mermaid';
  if (b.length === 1 && b[0].trim() === refLine(block.id)) return 'svg';
  return null;
}

/** story 里正式图块的结构事实，一次读出。切换、阅读状态与正式入口都消费这一份。 */
function inspect(featureRoot) {
  const raw = readOr(path.join(featureRoot, 'AR', 'story.md'));
  if (raw === null) return { raw };
  const lines = raw.split(/\r?\n/);
  const { spans: blocks, problems } = markPairs(lines, FIGURE_MARK, '图块');
  const fenced = new Set(fenceRanges(lines).flatMap(rowsOf));
  const old = lines.findIndex((l, i) => !fenced.has(i) && OLD_SLOT.test(l.trim()));
  if (old >= 0) {
    problems.push(`第 ${old + 1} 行是旧版的补充阅读槽：本版的增强阅读是正式图的同图 SVG，不再有阅读槽——`
      + '用旧版 `view --mode mermaid` 收起后在旧版收口，或从 init 重起');
  }
  for (const b of blocks) {
    b.form = formOf(b);
    b.src = lf(readOr(srcPath(featureRoot, b.id)));
    const at = `图块 ${b.id}（第 ${b.from + 1}–${b.to + 1} 行）`;
    b.problem = b.src === null ? `${at} 的源 AR/story-src/figures/${b.id}.mmd 不在：从备份或真实依据恢复源，不从正文反写`
      : b.form ? null : `${at} 里不是一个 Mermaid 围栏，也不是 ${refLine(b.id)} 这一行`;
  }
  return { raw, lines, blocks, problems };
}

/** SVG 本身立不立得住：在不在、结构检查过没过。没有缺口返回 null。 */
function svgGap(featureRoot, id) {
  const facts = svgFacts(featureRoot, id);
  if (facts.missing) return { state: 'no-svg', reason: `还没有增强阅读图 AR/figures/${id}.svg：按 reference/svg.md 依 ${id}.mmd 制作` };
  return facts.error || facts.problems.length ? { state: 'svg-invalid',
    reason: facts.error ? `结构检查跑不起来（${facts.error}）` : `结构检查没过：${facts.problems.join('；')}` } : null;
}

/** 这张图的证据缺口：SVG 立得住、验收绑定当前图源与 SVG 且结论成立。没有缺口返回 null。 */
function evidenceGap(featureRoot, id) {
  const r = svgGap(featureRoot, id) ?? readingState(featureRoot, id);
  return r.state === 'ready' ? null : r;
}

/**
 * 按模式切换或准备。问题非空时一个字节都不写。
 *
 * @param {string} featureRoot 需求目录
 * @param {'prepare'|'mermaid'|'svg'|'toggle'} mode
 * @param {{id?: string}} [opts]
 * @returns {{changed: boolean, problems: string[], notes: string[], kept: {id, reason}[], counts: {mermaid: number, svg: number}}}
 */
export function switchView(featureRoot, mode, { id = '' } = {}) {
  const storyPath = path.join(featureRoot, 'AR', 'story.md');
  const out = { changed: false, problems: [], notes: [], kept: [], counts: { mermaid: 0, svg: 0 } };
  const v = inspect(featureRoot);
  if (v.raw === null) {
    if (mode !== 'mermaid') out.problems.push('AR/story.md 不在：视图作用在成文的 story 上');
    return out;
  }
  const eol = v.raw.includes('\r\n') ? '\r\n' : '\n';
  if (id && !ID.test(id)) out.problems.push(`--id ${id} 不是合法的 ID（字母或数字开头，只含字母、数字、-、_）`);
  else if (id && !v.blocks.some(b => b.id === id)) out.problems.push(`没有 ID 为 ${id} 的图块`);
  // 显式重建这一块时，块里是什么都按源重铺；其余入口只认合法形态
  const broken = [...v.problems, ...v.blocks.filter(b => b.problem && !(mode === 'prepare' && id === b.id && b.src !== null)).map(b => b.problem)];
  out.problems.push(...broken.map(p => `AR/story.md：${p}——${RECOVER}`));
  if (out.problems.length) return out;
  if (mode === 'toggle') {
    if (!v.blocks.length) return { ...out, notes: ['story 里没有正式图：不需要 SVG'] };
    return switchView(featureRoot, v.blocks.some(b => b.form === 'svg' && (!id || b.id === id)) ? 'mermaid' : 'svg', { id });
  }

  let next = [...v.lines];
  const replace = [];
  const writes = [];
  const body = (b, rows) => replace.push({ from: b.from + 1, to: b.to - 1, rows });
  const mine = v.blocks.filter(b => !id || b.id === id);
  if (mode === 'prepare' && id) {
    body(mine[0], mermaidBody(mine[0].src));
    out.notes.push(`${id}：已从源 ${id}.mmd 重建这一块`);
  } else if (mode === 'prepare') {
    const managed = new Set(v.blocks.flatMap(rowsOf));
    const used = new Set(v.blocks.map(x => x.id));
    for (const f of fenceRanges(v.lines)) {
      if (f.lang !== 'mermaid' || !f.closed || managed.has(f.from)) continue;
      const inner = v.lines.slice(f.from + 1, f.to).join('\n');
      let fid = `fig-${createHash('sha256').update(inner).digest('hex').slice(0, 8)}`;
      for (let k = 2; used.has(fid); k += 1) fid = `${fid.replace(/-\d+$/, '')}-${k}`;
      used.add(fid);
      const have = lf(readOr(srcPath(featureRoot, fid)));
      if (have !== null && have !== `${inner}\n`) {
        out.problems.push(`AR/story.md：第 ${f.from + 1} 行的图要建的源 ${fid}.mmd 已在且内容不同——不覆盖已有的源，先查明它属于哪张图`);
        continue;
      }
      replace.push({ from: f.from, to: f.to, rows: [`<!-- story-figure:${fid}:begin -->`, ...mermaidBody(`${inner}\n`), `<!-- story-figure:${fid}:end -->`] });
      writes.push([srcPath(featureRoot, fid), `${inner}\n`]);
    }
    if (out.problems.length) return out;
  } else if (mode === 'mermaid') {
    //: 合法的 Mermaid 块与源文字不同：不猜是谁改的，按源重铺并说出来，不静默丢掉差异
    for (const b of mine) {
      const drift = b.form === 'mermaid' && mermaidBody(b.src).join('\n') !== b.body.join('\n');
      if (b.form === 'svg' || drift) body(b, mermaidBody(b.src));
      if (drift) out.notes.push(`${b.id}：正文里的图与源 ${b.id}.mmd 不同，已按源刷新——正文块里的改动没有保留，改图义改 .mmd`);
    }
  } else if (mode === 'svg') {
    for (const b of mine) {
      if (b.form !== 'svg' && !enhanced(featureRoot, b.id)) continue;   // 没做增强的图就是 Mermaid，不是待办
      const gap = evidenceGap(featureRoot, b.id);
      if (!gap) {
        if (b.form !== 'svg') body(b, [refLine(b.id)]);
        continue;
      }
      out.kept.push({ id: b.id, reason: gap.reason });
      out.notes.push(`${b.id}：${gap.reason}${b.form === 'svg' ? '，已收回 Mermaid' : '，保持 Mermaid'}`);
      if (b.form === 'svg') body(b, mermaidBody(b.src));
    }
  }
  //: 从下往上换：哪一段行数变了，都不挪上面还没换的行号
  for (const r of replace.sort((a, b) => b.from - a.from)) next.splice(r.from, r.to - r.from + 1, ...r.rows);
  // 分隔空行只在本来就要写盘时铺：正式入口收回 Mermaid 而无可改时，只读命令一个字节都不写
  if (mode === 'prepare' || replace.length) next = separateMarks(next);
  for (const [file, text] of writes) {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    if (readOr(file) !== text) fs.writeFileSync(file, text, 'utf-8');
  }
  const after = next.join(eol);
  if (after !== v.raw) {
    fs.writeFileSync(storyPath, after, 'utf-8');
    out.changed = true;
  }
  for (const b of markPairs(next, FIGURE_MARK, '图块').spans) {
    const form = formOf(b);
    if (form) out.counts[form] += 1;
  }
  return out;
}

/**
 * 本地阅读的工作集合 —— 每次从 story 里实际的正式图与已有增强资产派生，不另存清单。
 *
 * 没有正式图：不适用、已完成。有图：只列已开始增强的那几张（已有 SVG 或图审工作目录），逐张给状态与原因；
 * 没做增强的图保持 Mermaid，不是待办。complete 只说现存增强资产没有未处理的验证缺口，不说哪些图该做、选得对不对。
 * 结构坏了（标记、源、旧版阅读槽）：没完成，problems 与 `next` 点明修复入口。没建源的内联 Mermaid 由正式登记的 prepare 管理。
 */
export function readingWork(featureRoot) {
  const v = inspect(featureRoot);
  if (v.raw === null) {
    return { applicable: false, complete: true, items: [], problems: [], next: null };   // 还没有 story：没有图，也就没有增强
  }
  const problems = [...v.problems, ...v.blocks.filter(b => b.problem).map(b => b.problem)];
  if (!v.blocks.length && !problems.length) return { applicable: false, complete: true, items: [], problems: [], next: null };
  const items = v.blocks.filter(b => enhanced(featureRoot, b.id)).map((b) => {
    const gap = b.problem ? { state: 'blocked', reason: '图块结构或源有问题，先修（见 problems）' } : evidenceGap(featureRoot, b.id);
    return { id: b.id, line: b.from + 1, state: gap?.state ?? 'ready', reason: gap?.reason ?? '' };
  });
  const complete = !problems.length && items.every(i => i.state === 'ready');
  const rows = [...problems, ...items.filter(i => i.state !== 'ready').map(i => `${i.id}：${i.reason}`)];
  return { applicable: true, complete, items, problems,
    next: complete ? null : `做完已开始的同图增强：${rows.join('；')}`
      + '——按上面给的动作做（缺件的按 `reference/svg.md` 依同 ID 的 .mmd 补齐、交独立审查，改过的按它的恢复表），'
      + '`view --mode review-check` 通过后 `view --mode svg`' };
}

/** 验收对象：只认 story 里现有的正式图块，结构有问题先报。 */
function figureOf(featureRoot, id) {
  const v = inspect(featureRoot);
  if (v.raw === null) return { problems: ['AR/story.md 不在'] };
  const b = v.blocks.find(x => x.id === id);
  if (!b) return { problems: [`story 里没有 ID 为 ${id} 的正式图块——增强阅读只做已有正式图的同图 SVG`] };
  const problems = [...v.problems, ...(b.problem ? [b.problem] : [])];
  return { problems };
}

/** 生成某张图的验收请求：SVG 本身立得住、图源在才发；返回请求与交给独立审查者的任务。 */
export function reviewRequest(projectRoot, featureRoot, id) {
  const c = figureOf(featureRoot, id);
  if (c.problems.length) return c;
  const gap = svgGap(featureRoot, id);
  if (gap) return { problems: [gap.reason] };
  const r = readingRequest(featureRoot, id);
  return r.problems.length ? r : { ...r, task: reviewTask(projectRoot, featureRoot, r) };
}

/** 某张图的验收是否成立（只读）：不是 story 里正式图的 ID 不算。 */
export function reviewCheck(featureRoot, id) {
  const c = figureOf(featureRoot, id);
  return c.problems.length ? { state: 'invalid', reason: c.problems.join('；') }
    : evidenceGap(featureRoot, id) ?? { state: 'ready', reason: '' };
}

/**
 * 正式稿里不能有本地阅读图：正式图块之外指向 `AR/figures/` 的链接、图片引用或引用式定义逐处点名。
 * 登记过的原始材料图片走材料合同，不在这条里判。脚本不替作者删块外内容。
 */
export function strayReadingLinks(ctx, storyText) {
  const lines = String(storyText ?? '').split(/\r?\n/);
  const skip = new Set([...fenceRanges(lines).flatMap(rowsOf), ...markPairs(lines, FIGURE_MARK, '图块').spans.flatMap(rowsOf)]);
  const registered = new Set(registeredPaths(ctx));
  const problems = [];
  lines.forEach((line, i) => {
    if (skip.has(i)) return;
    const def = /^\s*\[[^\]]+\]:\s*<?([^\s>]+)>?/.exec(line);
    const targets = [...markdownLinks(line).links.map(l => l.target), ...(def ? [def[1]] : [])];
    for (const t of targets) {
      const rel = joinPosix('AR', t.split(/[#?]/)[0]);
      if (rel.startsWith('AR/figures/') && !registered.has(rel)) {
        problems.push(`story.md 第 ${i + 1} 行在正式图块之外引用了本地阅读资产 ${rel}——增强阅读 SVG 只在同 ID 的正式图块里`
          + '由视图切换显示，上传只交正式 Markdown');
      }
    }
  });
  return problems;
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
  //: 这一行只用 ASCII：chcp 65001 下 cmd 按字节数续读批处理，前面行里的多字节字会让后面的行从半截开始执行
  `rem ${LAUNCHER_MARK}: generated by story-build; double-click to switch figures between Mermaid and reviewed SVG`,
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

/**
 * 正式入口用：正式图块按源还原 Mermaid，坏了按原话报。没有管理标记就不动；旧版阅读槽也在这里报出来。
 */
export function ensureMermaid(featureRoot) {
  const raw = readOr(path.join(featureRoot, 'AR', 'story.md'));
  if (raw === null || !/<!-- story-(figure|reading):/.test(raw)) return { changed: false, problems: [], notes: [] };
  return switchView(featureRoot, 'mermaid');
}
