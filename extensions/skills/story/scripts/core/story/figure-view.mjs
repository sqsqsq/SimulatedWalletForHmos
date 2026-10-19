/**
 * story.md 里由脚本管理的两类图 —— 正式图与阅读图，各有自己的成对标记。
 *
 * 正式图是业务正文的一部分：标记之间恰好一个 Mermaid 围栏，与 `AR/story-src/figures/<ID>.mmd` 逐字相同。
 * `.mmd` 一建成就是这张图唯一的语义真源，正文块按它派生：
 *
 *     <!-- story-figure:<ID>:begin -->
 *     ```mermaid
 *     …
 *     ```
 *     <!-- story-figure:<ID>:end -->
 *
 * 阅读图是写作设计「## 阅读图选择」选中的补充 SVG（`AR/figures/<ID>.svg`），可以综合多段文字、表与图。
 * 每个选择项在放置小节末尾（同级下一节之前）有一个槽，同一处多张按写作设计顺序排。正式形态槽是空的，
 * 阅读形态槽里只有一行图片引用，alt 是这张图的阅读问题；正文与 Mermaid 始终都在：
 *
 *     <!-- story-reading:<ID>:begin -->
 *     ![<阅读问题>](figures/<ID>.svg)
 *     <!-- story-reading:<ID>:end -->
 *
 * - `prepare`：给还没管理的 Mermaid 围栏加标记、首次写 `.mmd`（同 ID 的源已在且不同就停）；按当前选择同步阅读槽——
 *   移除全部合法槽，按写作设计顺序在各自放置小节末尾重建空槽。带 `--id` 时按对象类型处理：正式图从已有 `.mmd`
 *   重建这一块（从不拿正文覆盖源），阅读图同步全部阅读槽；一个 ID 同时属于两类就要求不带 id 整体执行。
 * - `mermaid`：正式块按源还原（合法块文字与源不同也按源重铺并说明）；全部阅读槽置空。正式登记、审查、update 比较与归档都先走这一步。
 * - `svg`：正式块不动；只把独立审查有效的选中图放进自己的槽，其余槽置空并说明原因。
 * - `toggle`：有任一槽展开就全部隐藏，否则展开可用的（一键入口用它）。
 *
 * 结构坏了（孤立标记、重复 ID、块里不是一个 Mermaid 围栏、源缺失、槽里有作者文字、放置小节找不到或有歧义）整次不写，
 * 点名 ID 与行号；不按相似文本猜配对，不覆盖块外正文。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { createHash } from 'node:crypto';
import { fenceRanges, FIGURE_MARK, headingPath, markPairs, readingSlots, withoutReadingSlots } from './document.mjs';
import { markdownLinks } from './language.mjs';
import { joinPosix, registeredPaths } from './sources.mjs';
import { readWritingPlan } from './writing-plan.mjs';
import { lf, mermaidBody, readOr, readingRequest, readingState, reviewTask, srcPath, svgFacts } from './figure-reading.mjs';

export const VIEW_MODES = ['prepare', 'mermaid', 'svg', 'toggle', 'status', 'review-request', 'review-check'];
const ID = /^[A-Za-z0-9][\w-]*$/;
const RECOVER = '改图义改 AR/story-src/figures/<ID>.mmd，它是唯一真源，正文管理块按它重铺；'
  + '管理块结构坏了而边界还认得出、源还在，跑 `story-build view --mode prepare --id <ID>` 从源重建这一块；'
  + '源丢了从备份或真实依据恢复 .mmd，不从正文反写。管理块是脚本管理区，不要手改';
const SYNC = '阅读槽按写作设计「## 阅读图选择」由 `story-build view --mode prepare` 同步：改了选择或放置就跑一次';
const CONTRACT = new URL('../../../contracts/story-chapters.json', import.meta.url);

const rowsOf = x => Array.from({ length: x.to - x.from + 1 }, (_, k) => x.from + k);
//: alt 里的 Markdown 特殊字符逐个转义：阅读问题原样显示，不被解析成链接或强调
const refLine = item => `![${item.question.replace(/[\\`*_[\]<>]/g, '\\$&')}](figures/${item.id}.svg)`;

/** 块现在是什么：一个完整 Mermaid 围栏、旧版的 SVG 引用（不再支持）、或别的。 */
function formOf(block) {
  const b = block.body;
  // 块内恰好一个完整围栏、从第一行到最后一行：首尾像围栏而中间已闭合、夹着正文或第二段围栏的，是结构坏了
  const fences = fenceRanges(b);
  if (b[0] === '```mermaid' && b[b.length - 1] === '```' && fences.length === 1
      && fences[0].closed && fences[0].from === 0 && fences[0].to === b.length - 1) return 'mermaid';
  if (b.length === 1 && /^!\[.*\]\(figures\/[^)]+\.svg\)$/.test(b[0].trim())) return 'old-svg';
  return null;
}

/** story 里两类管理区的结构事实，一次读出。切换、阅读状态与正式入口都消费这一份。 */
function inspect(featureRoot) {
  const raw = readOr(path.join(featureRoot, 'AR', 'story.md'));
  if (raw === null) return { raw };
  const lines = raw.split(/\r?\n/);
  const { spans: blocks, problems } = markPairs(lines, FIGURE_MARK, '图块');
  for (const b of blocks) {
    b.form = formOf(b);
    b.src = lf(readOr(srcPath(featureRoot, b.id)));
    const at = `图块 ${b.id}（第 ${b.from + 1}–${b.to + 1} 行）`;
    b.problem = b.form === 'old-svg' ? `${at} 是旧版阅读形态（SVG 引用替换了 Mermaid），本版不再读它：`
        + '用旧版切回 Mermaid，或从 init 重起；源还在时 `prepare --id` 从源重建这一块'
      : b.src === null ? `${at} 的源 AR/story-src/figures/${b.id}.mmd 不在：从备份或真实依据恢复源，不从正文反写`
        : b.form ? null : `${at} 里不是一个 Mermaid 围栏`;
  }
  const { slots, problems: slotProblems } = readingSlots(lines);
  return { raw, lines, blocks, problems, slots, slotProblems };
}

/** 写作设计里的阅读图选择：候选、每项放置小节的完整标题路径、选择本身的问题。 */
function selection(featureRoot) {
  let contract;
  try { contract = JSON.parse(fs.readFileSync(CONTRACT, 'utf-8')); } catch { contract = null; }
  if (!contract) return { declared: false, none: null, items: [], problems: ['contracts/story-chapters.json 读不出：阅读图的选择与放置定不了'] };
  const srcDir = path.join(featureRoot, 'AR', 'story-src');
  const ctx = { contract, featureRoot, srcDir, storyPath: path.join(featureRoot, 'AR', 'story.md'),
    decisionsPath: path.join(srcDir, 'decisions.json'), templatePath: path.join(srcDir, 'story-template.md') };
  const plan = readWritingPlan(ctx);
  const r = plan.reading;
  const items = r.items.filter(x => ID.test(x.id)).map((x) => {
    const [chapter, ...names] = x.placement.split('>').map(s => s.trim()).filter(Boolean);
    const title = plan.chapters.find(c => c.id === chapter)?.title;
    // ctx 随候选带给验收：依据按同一份上下文解析
    return { ...x, where: title ? [title, ...names] : null, ctx };
  });
  return { declared: r.declared, none: r.noneReason, items, problems: [...r.problems] };
}

/**
 * 槽的规范布局：去掉全部合法槽（连同紧挨在前的一个空行），再把 `items` 的槽按写作设计顺序放回各自放置小节末尾——
 * 最后一行非空内容之后、同级下一节之前。`body(id)` 给槽里的内容。重排同一份文本得到同一结果。
 *
 * @returns {{lines: string[], problems: string[], order: Map<string, string[]>}}
 */
function layout(lines, slots, items, body) {
  const drop = new Set(slots.flatMap(s => [...rowsOf(s), ...(s.from > 0 && !lines[s.from - 1].trim() ? [s.from - 1] : [])]));
  const base = lines.filter((_, i) => !drop.has(i));
  const text = base.join('\n');
  const [groups, order, problems] = [new Map(), new Map(), []];
  for (const x of items) {
    if (!x.where) continue;                 // 章 ID 认不出：写作设计那条已报
    const hit = headingPath(text, x.where);
    if (hit.problem) {
      problems.push(`阅读图 ${x.id} 的放置「${x.placement}」在 AR/story.md 里${hit.problem}——放置写正文里实际的章名与小节名`);
      continue;
    }
    let at = hit.to - 1;
    while (at >= hit.from && !base[at].trim()) at -= 1;
    groups.set(at, [...(groups.get(at) ?? []), x.id]);
  }
  const out = [...base];
  for (const at of [...groups.keys()].sort((a, b) => b - a)) {
    const ids = groups.get(at);
    ids.forEach(id => order.set(id, ids));
    out.splice(at + 1, 0, ...ids.flatMap(id => ['', `<!-- story-reading:${id}:begin -->`, ...body(id), `<!-- story-reading:${id}:end -->`]));
  }
  return { lines: out, problems, order };
}

/** 当前槽与选择对不对得上：放置问题、孤立槽、缺槽、错位，与每项在同一处的顺序。槽结构坏了不调。 */
function syncOf(v, sel) {
  const byId = new Map(v.slots.map(s => [s.id, s]));
  const chosen = new Set(sel.items.map(x => x.id));
  const canon = layout(v.lines, v.slots, sel.items, id => byId.get(id)?.body ?? []);
  const orphans = v.slots.filter(s => !chosen.has(s.id));
  const missing = new Set(sel.items.filter(x => x.where && !byId.has(x.id)).map(x => x.id));
  // 槽齐全、位置都定得到时才比位置：规范布局里它该在的行与现在不同，就是错位
  const at = new Map(readingSlots(canon.lines).slots.map(s => [s.id, s.from]));
  const misplaced = new Set(orphans.length || missing.size || canon.problems.length ? []
    : v.slots.filter(s => at.get(s.id) !== s.from).map(s => s.id));
  const problems = [...canon.problems, ...orphans.map(s => `阅读槽 ${s.id}（第 ${s.from + 1} 行）不在当前选择里——${SYNC}；`
    + '它的 SVG 与验收证据留在原处、不参与完成判定，不再用由作者清理')];
  if (misplaced.size) problems.push(`阅读槽 ${[...misplaced].join('、')} 不在写作设计指定的位置或顺序上——${SYNC}`);
  return { problems, missing, misplaced, order: canon.order };
}

/** 交给验收的对象：候选、去掉阅读槽的正式 Story、放置小节路径、同一处的顺序。 */
const subjectOf = (v, item, sync) => ({ item, formal: withoutReadingSlots(v.raw), where: item.where ?? [],
  order: sync?.order.get(item.id) ?? [item.id] });

/** SVG 本身立不立得住：在不在、结构检查过没过。没有缺口返回 null。 */
function svgGap(featureRoot, id) {
  const facts = svgFacts(featureRoot, id);
  if (facts.missing) return { state: 'no-svg', reason: `还没有阅读图 AR/figures/${id}.svg：按 reference/svg.md 依据所选内容画` };
  return facts.error || facts.problems.length ? { state: 'svg-invalid',
    reason: facts.error ? `结构检查跑不起来（${facts.error}）` : `结构检查没过：${facts.problems.join('；')}` } : null;
}

/** 这张阅读图的证据缺口：SVG 立得住、验收绑定当前输入且结论成立。没有缺口返回 null。 */
function evidenceGap(featureRoot, v, item, sync) {
  const r = svgGap(featureRoot, item.id) ?? readingState(featureRoot, subjectOf(v, item, sync));
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
  const sel = mode === 'mermaid' ? null : selection(featureRoot);
  const formalId = Boolean(id) && v.blocks.some(b => b.id === id);
  const readingId = Boolean(id) && ((sel?.items.some(x => x.id === id) ?? false) || v.slots.some(s => s.id === id));
  if (id && formalId && readingId) out.problems.push(`${id} 同时是正式图块与阅读图的 ID：不带 --id 跑整体 prepare`);
  if (id && !formalId && !readingId) out.problems.push(`没有 ID 为 ${id} 的${mode === 'prepare' ? '图块或' : ''}阅读图`);
  if (id && formalId && mode !== 'prepare') out.problems.push(`${id} 是正式图块：--id 只在 prepare 里用于从源重建它，切换按阅读图 ID 操作`);
  // 显式重建这一块时，块里是什么都按源重铺；其余入口只认合法形态
  const formal = [...v.problems, ...v.blocks.filter(b => b.problem && !(mode === 'prepare' && id === b.id && b.src !== null)).map(b => b.problem)];
  out.problems.push(...formal.map(p => `AR/story.md：${p}——${RECOVER}`), ...v.slotProblems.map(p => `AR/story.md：${p}——${SYNC}`));
  const sync = sel && !v.slotProblems.length ? syncOf(v, sel) : null;
  if (sel && (mode !== 'prepare' || !formalId)) {
    out.problems.push(...sel.problems);
    // prepare 本身就是同步入口：孤立与错位由它修；svg 只往自己的槽里放
    if (sync && mode !== 'prepare') out.problems.push(...sync.problems);
  }
  if (out.problems.length) return out;
  if (mode === 'toggle') {
    if (!sel.items.length && !v.slots.length) return { ...out, notes: ['写作设计没有选阅读图：这份 story 不需要 SVG'] };
    return switchView(featureRoot, v.slots.some(s => s.shown && (!id || s.id === id)) ? 'mermaid' : 'svg', { id });
  }

  let next = [...v.lines];
  const replace = [];
  const writes = [];
  const sources = new Map(v.blocks.map(b => [b.id, b.src]));
  //: 合法的 Mermaid 块与源文字不同：不猜是谁改的，按源重铺并说出来，不静默丢掉差异
  const refresh = (b) => {
    replace.push({ from: b.from + 1, to: b.to - 1, rows: mermaidBody(sources.get(b.id)) });
    out.notes.push(`${b.id}：正文里的图与源 ${b.id}.mmd 不同，已按源刷新——正文块里的改动没有保留，改图义改 .mmd`);
  };
  if (mode === 'prepare' && formalId) {
    replace.push({ from: v.blocks.find(x => x.id === id).from + 1, to: v.blocks.find(x => x.id === id).to - 1, rows: mermaidBody(sources.get(id)) });
    out.notes.push(`${id}：已从源 ${id}.mmd 重建这一块`);
  } else if (mode === 'prepare' && !id) {
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
  } else if (mode === 'mermaid' && !id) {
    for (const b of v.blocks) if (mermaidBody(sources.get(b.id)).join('\n') !== b.body.join('\n')) refresh(b);
  }
  for (const r of replace.sort((a, b) => b.from - a.from)) next.splice(r.from, r.to - r.from + 1, ...r.rows);

  if (mode === 'prepare' && !formalId) {
    // 正式块的替换可能挪了行号：在替换后的文本上重读槽，再按选择整体重排成空槽
    const placed = layout(next, readingSlots(next).slots, sel.items, () => []);
    if (placed.problems.length) return { ...out, problems: placed.problems };
    next = placed.lines;
    const now = new Set(sel.items.map(x => x.id));
    const gone = v.slots.filter(s => !now.has(s.id)).map(s => s.id);
    if (gone.length) out.notes.push(`已移除不在当前选择里的阅读槽 ${gone.join('、')}；它们的 SVG 与验收证据留在原处，不再用由作者清理`);
    if (!sel.items.length && !sel.problems.length && sel.none === null) out.notes.push('写作设计还没有阅读图选择的结论');
  } else if (mode === 'mermaid' || mode === 'svg') {
    const items = new Map((sel?.items ?? []).map(x => [x.id, x]));
    const rows = new Map();
    for (const s of v.slots) {
      if (id && s.id !== id) continue;
      if (mode === 'mermaid') { rows.set(s.id, []); continue; }
      const item = items.get(s.id);
      const gap = evidenceGap(featureRoot, v, item, sync);
      if (gap) {
        out.kept.push({ id: s.id, reason: gap.reason });
        out.notes.push(`${s.id}：${gap.reason}${s.shown ? '，已收起这张图' : '，槽保持空'}`);
        rows.set(s.id, []);
      } else rows.set(s.id, [refLine(item)]);
    }
    const unslotted = mode === 'svg' ? sel.items.filter(x => (!id || x.id === id) && sync.missing.has(x.id)) : [];
    out.kept.push(...unslotted.map(x => ({ id: x.id, reason: `Story 里还没有它的阅读槽——${SYNC}` })));
    // 从下往上换：槽内行数变化不影响上面的行号
    for (const s of [...v.slots].sort((a, b) => b.from - a.from)) {
      if (rows.has(s.id)) next.splice(s.from + 1, s.to - s.from - 1, ...rows.get(s.id));
    }
  }
  for (const [file, text] of writes) {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    if (readOr(file) !== text) fs.writeFileSync(file, text, 'utf-8');
  }
  const after = next.join(eol);
  if (after !== v.raw) {
    fs.writeFileSync(storyPath, after, 'utf-8');
    out.changed = true;
  }
  out.counts = { mermaid: markPairs(next, FIGURE_MARK, '图块').spans.length, svg: readingSlots(next).slots.filter(s => s.shown).length };
  return out;
}

/**
 * 本地阅读的工作集合 —— 每次从写作设计的选择与 Story 实际内容派生，不另存状态。
 *
 * 明确不采用且声明、槽与正式图结构都没有问题：不适用、已完成。选了图：逐项给状态与原因，全部 ready 才完成。
 * 缺选择、坏声明、依据或放置定不了、标记或源结构坏：没完成，problems 与 `next` 点明修复入口；items 只列已能确定的候选。
 */
export function readingWork(featureRoot) {
  const v = inspect(featureRoot);
  if (v.raw === null) {
    return { applicable: true, complete: false, items: [], unmanaged: [], problems: ['AR/story.md 不在'], next: '本地阅读判不了：AR/story.md 不在' };
  }
  const sel = selection(featureRoot);
  const sync = v.slotProblems.length ? null : syncOf(v, sel);
  const problems = [...v.problems, ...v.blocks.filter(b => b.problem).map(b => b.problem), ...v.slotProblems,
    ...sel.problems, ...(sync?.problems ?? [])];
  if (!sel.declared && !sel.problems.length) {
    problems.push('写作设计「## 阅读图选择」还没有结论——没有阅读图写「不采用：<理由>」，有就逐张写候选');
  }
  if (!problems.length && sel.none !== null && !sel.items.length) {
    return { applicable: false, complete: true, items: [], unmanaged: [], problems: [], next: null };
  }
  const managed = new Set(v.blocks.flatMap(rowsOf));
  const unmanaged = sel.items.length
    ? fenceRanges(v.lines).filter(f => f.lang === 'mermaid' && f.closed && !managed.has(f.from)).map(f => f.from + 1) : [];
  const items = sel.items.map((x) => {
    const slot = v.slots.find(s => s.id === x.id);
    const gap = !sync ? { state: 'blocked', reason: 'Story 的阅读槽结构坏了，先修（见 problems）' }
      : sync.missing.has(x.id) || !x.where ? { state: 'no-slot', reason: `Story 里还没有它的阅读槽——${SYNC}` }
        : sync.misplaced.has(x.id) ? { state: 'misplaced', reason: `阅读槽不在写作设计指定的位置——${SYNC}` }
          : evidenceGap(featureRoot, v, x, sync);
    return { id: x.id, line: slot ? slot.from + 1 : null, state: gap?.state ?? 'ready', reason: gap?.reason ?? '' };
  });
  const complete = !problems.length && !unmanaged.length && items.every(i => i.state === 'ready');
  const rows = [...problems, ...unmanaged.map(n => `第 ${n} 行的 Mermaid 图还没建源（\`story-build view --mode prepare\` 一并建）`),
    ...items.filter(i => i.state !== 'ready').map(i => `${i.id}：${i.reason}`)];
  return { applicable: true, complete, items, unmanaged, problems,
    next: complete ? null : `完成本地阅读（写作设计选了 ${sel.items.length} 张阅读图）：${rows.join('；')}`
      + '——选择或依据的问题回写作设计改；图按 `reference/svg.md` 依据所选内容画、渲染、交独立审查，'
      + '`view --mode review-check` 通过后 `view --mode svg`' };
}

/** 选中候选的验收对象：不在当前选择里的 ID 明确拒绝，选择或槽结构有问题先报。 */
function candidate(featureRoot, id) {
  const v = inspect(featureRoot);
  if (v.raw === null) return { problems: ['AR/story.md 不在'] };
  const sel = selection(featureRoot);
  const item = sel.items.find(x => x.id === id);
  if (!item) return { problems: [`${id} 不在写作设计「## 阅读图选择」的候选里——验收只认当前选中的阅读图`] };
  if (v.slotProblems.length || sel.problems.length) return { problems: [...v.slotProblems, ...sel.problems] };
  return { v, item, sync: syncOf(v, sel), problems: [] };
}

/** 生成某张阅读图的验收请求：SVG 本身立得住、依据都取得到才发；返回请求与交给独立审查者的任务。 */
export function reviewRequest(projectRoot, featureRoot, id, render) {
  const c = candidate(featureRoot, id);
  if (c.problems.length) return c;
  const gap = svgGap(featureRoot, id);
  if (gap) return { problems: [gap.reason] };
  const r = readingRequest(featureRoot, subjectOf(c.v, c.item, c.sync), render);
  return r.problems.length ? r : { ...r, task: reviewTask(projectRoot, featureRoot, r) };
}

/** 某张选中阅读图的验收是否成立（只读）：不在选择里的 ID 不算。 */
export function reviewCheck(featureRoot, id) {
  const c = candidate(featureRoot, id);
  return c.problems.length ? { state: 'invalid', reason: c.problems.join('；') }
    : evidenceGap(featureRoot, c.v, c.item, c.sync) ?? { state: 'ready', reason: '' };
}

/**
 * 正式稿里不能有本地阅读图：阅读槽之外指向 `AR/figures/` 的链接、图片引用或引用式定义逐处点名。
 * 包括已取消候选留下的引用；登记过的原始材料图片走材料合同，不在这条里判。脚本不替作者删槽外内容。
 */
export function strayReadingLinks(ctx, storyText) {
  const lines = String(storyText ?? '').split(/\r?\n/);
  const skip = new Set([...fenceRanges(lines).flatMap(rowsOf), ...readingSlots(lines).slots.flatMap(rowsOf)]);
  const registered = new Set(registeredPaths(ctx));
  const problems = [];
  lines.forEach((line, i) => {
    if (skip.has(i)) return;
    const def = /^\s*\[[^\]]+\]:\s*<?([^\s>]+)>?/.exec(line);
    const targets = [...markdownLinks(line).links.map(l => l.target), ...(def ? [def[1]] : [])];
    for (const t of targets) {
      const rel = joinPosix('AR', t.split(/[#?]/)[0]);
      if (rel.startsWith('AR/figures/') && !registered.has(rel)) {
        problems.push(`story.md 第 ${i + 1} 行在阅读槽之外引用了本地阅读资产 ${rel}——正式稿不带本地阅读图，`
          + '补充图只在写作设计选中、`view --mode prepare` 建的阅读槽里由视图显隐，上传只交正式 Markdown');
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
  `rem ${LAUNCHER_MARK}：由 story-build 生成，双击显示或隐藏写作设计选中的本地阅读图`,
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
 * 正式入口用：正式块按源还原、阅读槽全部置空，坏了按原话报。两类标记都没有就不动——
 * 首次起稿时写作设计还没有阅读图选择，这里不读选择，不会被它锁住。
 */
export function ensureMermaid(featureRoot) {
  const raw = readOr(path.join(featureRoot, 'AR', 'story.md'));
  if (raw === null || !/<!-- story-(figure|reading):/.test(raw)) return { changed: false, problems: [], notes: [] };
  return switchView(featureRoot, 'mermaid');
}
