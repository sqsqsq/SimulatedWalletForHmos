/**
 * 正文的来源 —— 这份 story 据哪几份材料写成，哪一份还没在手里；附录材料清单里的链接点不点得开。
 *
 * 必需性只在这里判一次：起手预检与交付前的 check 读同一份结果。两处各判一次的话，
 * 同一份缺件会在一处说「本地单缺它正常」、在另一处说「它是必备来源」。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { isSystemRequirement, readJson, readText } from './context.mjs';
import { queryFlowStatus } from '../flow/client.mjs';
import { appendixChapter, materialSubsectionName } from './appendix.mjs';
import { designSource } from './design-source.mjs';
import { parseDocument, subsectionSpan } from './document.mjs';

/**
 * 合同声明的每个来源，读到了没有 —— **读不到的也要带回来**。
 *
 * 读不到就静默跳过的话，一整类材料会凭空缺席而零信号：那一份的内容从头到尾
 * 没进过任何一条判据的视野，从起手到交付没有一处提过。
 *
 * 这里只**读合同声明**：谁读到了、谁没读到。这一轮各自必不必需（远程单/本地单）
 * 由 `sourceStatus` 判，起手与交付前的 check 共用它，不在两处各写一份。
 *
 * 索引文件缺席**不是缺陷**：图片的身份与落点在 `materials.json`，那是唯一登记处。
 * 拿「目录里有图而索引不在」当阻断，等于要求作者为一份不承载登记的说明文件停下来。
 *
 * @returns {{docs: object[], missing: object[]}}
 */
function scanSources(ctx) {
  const docs = [], missing = [];
  for (const [doc, decl] of Object.entries(ctx.contract.sources ?? {})) {
    const rel = typeof decl === 'string' ? decl : decl?.path;
    if (!rel) continue;
    const obj = typeof decl === 'object' && decl ? decl : {};
    const abs = path.join(ctx.featureRoot, rel);
    const text = readText(abs);
    if (text !== null) {
      docs.push({ doc, rel, text });
      continue;
    }
    // 读不到的带回来，必需性交给 sourceStatus。
    missing.push({ doc, rel, required: obj.required === true });
  }
  return { docs, missing };
}

/** 缺失来源报成一句话。必备与可选两种措辞，降级的那几份带上「为什么不算缺」。 */
export function missingSourceLine(m) {
  return `${m.rel}：合同声明的来源 ${m.doc} 不存在`
    + (m.required
      ? '——它是必备来源，缺了这一轮的材料就不完整'
      : `（${m.why ?? '可选来源'}，缺了是正常的）`);
}

//: 需求系统给的单才有的那两份。本地单没有它们是正常的——把本地单的 PRD 判成缺件，
//: 作者除了造一份假的没有别的路。本轮自己派生的产物（AR 提取稿）两种单都必需：
//: 跳过它等于拿不全的输入成文。
const REMOTE_ONLY_SOURCES = ['PRD', 'SE'];

/**
 * 合同声明的来源这一轮各自必不必需 —— **起手与交付前的 check 问的是同一份判定**。
 *
 * 两处各判一次，同一份缺件就会被说成两件事：起手说「本地单缺 PRD 正常」，
 * 交付前的 check 说「它是必备来源」。系统需求按编号认（`isSystemRequirement`）。
 *
 * @returns {{docs: object[], missing: object[], blocking: object[]}}
 */
export function sourceStatus(ctx) {
  const { docs, missing } = scanSources(ctx);
  const remote = isSystemRequirement(path.basename(ctx.featureRoot));
  const adjusted = missing.map(m => (remote || !REMOTE_ONLY_SOURCES.includes(m.doc)
    ? m
    : { ...m, required: false, why: '本地单没有需求系统给的这一份' }));
  return { docs, missing: adjusted, blocking: adjusted.filter(m => m.required) };
}

// --------------------------------------------------------------------------
// 正文定位：章、小节与附录机器区
// --------------------------------------------------------------------------

/**
 * 材料里的图片登记 —— 唯一来源是材料清单（`AR/story-src/materials.json`）。
 *
 * 登记的唯一来源是清单：它枚举磁盘上真实存在的图片文件，与谁给它写没写过
 * markdown 链接无关——按链接枚举的话，界面参考目录里只写了名字的那几张就不算数。
 *
 * 清单枚举的是磁盘上真实存在的图片文件，与谁给它写没写链接无关；同一张图复制到第二个
 * 落点时它按内容合并成一条，`paths` 列出全部落点——**图片的身份是它的内容，不是路径**。
 *
 * @returns {{kind:string,sha256:string,paths:string[]}[] | null | 'broken'}
 *   null = 没有清单（还没跑过 round）；'broken' = 清单坏了，两者不能混为一谈
 */
export function readManifest(ctx) {
  if (!ctx.srcDir) return null;
  const text = readText(path.join(ctx.srcDir, 'materials.json'));
  if (text === null) return null;
  try { return JSON.parse(text.replace(/^\ufeff/, '')); } catch { return 'broken'; }
}

export function relFromFeature(ctx, target) {
  return path.relative(ctx.featureRoot, target).split(path.sep).join('/');
}

/** posix 风格拼接并规范化（`..` 逐段回退），跨平台一致。 */
export function joinPosix(base, ref) {
  const parts = String(base ?? '').split('/').filter(p => p && p !== '.');
  for (const seg of String(ref ?? '').split(/[\\/]/)) {
    if (seg === '..') { parts.pop(); continue; }
    if (!seg || seg === '.') continue;
    parts.push(seg);
  }
  return parts.join('/');
}

// --------------------------------------------------------------------------
// 上游带图的文档：图由作者按内容搬进 story
// --------------------------------------------------------------------------

/**
 * 需求目录里一份上游文件在本次采用的版本：交给设计后读冻结输入里的原始字节，当前工作区的新版本不改变已采用的来源；
 * 还没交给设计时读当前文件。返回正文与它的位置（冻结副本给工程内路径，当前文件给需求目录内路径），读不到返回 null。
 *
 * @param {{projectRoot: string, featureRoot: string}} ctx
 */
function adoptedText(ctx, rel) {
  const flow = readJson(path.join(ctx.featureRoot, 'AR', 'story-src', 'story-flow.json'), null);
  const ref = flow?.input?.snapshot_ref;
  const at = ref ? `${path.posix.dirname(String(ref))}/files/${rel}` : null;
  const file = at && ctx.projectRoot ? path.join(ctx.projectRoot, ...at.split('/')) : path.join(ctx.featureRoot, rel);
  const text = readText(file);
  if (text === null) return null;
  return { text, at: at && ctx.projectRoot ? at : rel };
}

/**
 * 本次采用的上游原件正文（产品需求、系统设计、开发需求）：交给设计后取冻结副本，之前取当前文件。
 * 判一个编号是不是上游自己的编号时用它。
 */
export function adoptedUpstreamTexts(ctx) {
  return ['PRD', 'SE', 'DESIGN'].map(key => ctx.contract.sources?.[key]?.path)
    .filter(Boolean).map(rel => adoptedText(ctx, rel)?.text).filter(t => typeof t === 'string');
}

/**
 * 把材料清单那一节里的 markdown 链接换成一个占位词，再交给仓内路径与文档坐标扫描。
 *
 * **原文链接是仓内路径唯一允许出现的位置**：归档件的读者打不开这个仓，但他要能
 *据这一行把那份材料找出来——链接是「据哪几份材料写成」这件事唯一可核的形态。
 * 豁免范围只到这一节的链接语法：同一行链接之外的文字照扫，别的章节照扫。
 */
export function redactMaterialLinks(storyText, ctx) {
  const appendix = appendixChapter(ctx.contract);
  const name = materialSubsectionName(ctx.contract);
  if (!appendix || !name) return storyText;
  const span = subsectionSpan(storyText, appendix.title, name);
  if (!span) return storyText;
  const lines = String(storyText).split(/\r?\n/);
  for (let i = span.start; i < span.end && i < lines.length; i++) {
    lines[i] = lines[i].replace(/\[[^\]]*\]\([^)\s]*\)/g, '原文链接');
  }
  return lines.join('\n');
}

/**
 * 材料现在能不能起稿 —— **事实由 story_flow 的材料链给，这里只消费**。
 *
 * 两件事都要看：`pending` 是收件箱里还没并入正文的原件，`changed` 是磁盘与本轮登记的
 * 基准不同。只认后者的话，`round` 一登记新基准它就归假，而那份原件仍躺在收件箱里——
 * 起手照过，而成文据以写的材料少一份，此后没有任何判据会提到它。
 *
 * 拦的理由用 status 给的那句话：处置写在流程那一侧，这里再写一遍迟早与它分叉。
 *
 * @returns {string|null} 不能起手的原因（含处置）；null = 材料就位
 */
export function materialsNotReady(ctx) {
  const { data, error } = queryFlowStatus(ctx.projectRoot, ctx.args.feature,
    { timeoutMs: 120000, materialsOnly: true });
  if (error) {
    return `\`story_flow.py status\` 跑不通（${error}）——原件导没导、材料变没变由 story_flow 的材料链`
      + '按磁盘现状答，起骨架前读它的结论'
      + '（`story_flow.py status --feature <名> --project-root <工程根>`）';
  }
  const state = data?.material_state ?? null;
  if (!state) return null;        // 没有轮次：基准不符由上面的清单判据报
  if (!state.pending.length && !state.changed) return null;
  return String(data.action ?? '').trim()
    || '材料与本轮登记的不是同一批——当前该做的动作由 `story_flow.py status` 按材料链给出';
}

/**
 * 合同声明的来源在不在 —— 必备缺了拦，可选缺了记一笔。
 *
 * 声明的来源压根不在是隐蔽的：那一份材料的内容从头到尾没进过任何一条判据的视野，
 * 门禁却全绿。
 */
export function sourceProblems(ctx) {
  const problems = [];
  const notes = [];
  // ⓪a 合同声明的来源都在
  //
  // 声明的来源压根不在是隐蔽的：那一份材料的内容从头到尾没进过任何一条判据的视野，
  // 门禁却全绿。必需性与起手用**同一份判定**（`sourceStatus`：远程单/本地单、可选来源
  // 都按那里分）——两处各判一次的话，同一份缺件在起手说「本地单缺它正常」、
  // 在这里说「它是必备来源」，作者只能挑一句信。
  // **必备缺了拦**：归档件的依据缺了一块，评审者无从复核；可选缺了记一笔。
  const { missing, blocking } = sourceStatus(ctx);
  for (const m of blocking) {
    problems.push(`${missingSourceLine(m)}；`
      + '必需性按合同 sources 的 required 与单据来源判（本地单不要求需求系统给的 PRD、SE）');
  }
  for (const m of missing.filter(x => !x.required)) notes.push(missingSourceLine(m));
  return { problems, notes };
}

//: 图片按扩展名认：同一张图的另一处落点不在快照里，也不是外部原件
const IMAGE = /\.(png|jpe?g|gif|webp|svg|bmp)$/i;

/**
 * 这份 Story 据以写成的外部原件 —— 材料清单的检查、作者包与审查任务共用这一份。
 *
 * 按冻结快照取：快照的 `origins` 记着每份采用文件的外部来源——收件箱导入的转换稿记它的全部原件（路径与采用时的摘要），
 * init 落的空骨架记空列表；没记的采用原件就是外部原件本身。快照里的图片、提取稿与人签导出是过程件（`internal`）。
 * 本轮 update 记下了评审人原话的，评审记录也是一份来源。收件箱里的原件与采用时的摘要不同、或快照没记来源
 * （旧版本冻结），记进 `gaps`，不猜。没有冻结快照（还没交给设计）返回 null。
 *
 * @returns {{originals: Map<string, string[]>, derived: Map<string, string[]>, internal: Set<string>, gaps: string[]}|null}
 *   `originals` 是原件 → 它的转换稿，`derived` 是转换稿 → 它的原件
 */
export function externalOriginals(ctx) {
  const snapshot = designSource(ctx).snapshot;
  if (!snapshot) return null;
  const originals = new Map(), derived = new Map(), internal = new Set();
  const gaps = snapshot.origins ? [] : ['冻结输入没有记下采用文件的外部来源（旧版本冻结），原件与转换稿分不清——重新 complete 冻结一版'];
  for (const f of snapshot.files ?? []) {
    const from = snapshot.origins?.[f.path];
    if (f.role !== 'original' || (from && !from.length)) { internal.add(f.path); continue; }
    if (!from) { originals.set(f.path, originals.get(f.path) ?? []); continue; }
    derived.set(f.path, from.map(o => o.path));
    for (const o of from) {
      originals.set(o.path, [...(originals.get(o.path) ?? []), f.path]);
      const bytes = readBytes(path.join(ctx.featureRoot, o.path));
      if (!bytes || `sha256:${crypto.createHash('sha256').update(bytes).digest('hex').slice(0, 16)}` !== o.sha256) {
        gaps.push(`${o.path} 不是本次采用的那一版（采用时 ${o.sha256}${bytes ? '，现在内容变了' : '，现在读不到'}）——换了版要重新导入、round 并 complete`);
      }
    }
  }
  if ((readJson(ctx.flowPath, null)?.update?.decisions ?? []).length) originals.set('AR/review.md', []);
  return { originals, derived, internal, gaps };
}

const readBytes = (abs) => { try { return fs.readFileSync(abs); } catch { return null; } };

/**
 * 材料清单：一张「材料｜来源｜贡献」表（列名取章节合同），一行一份外部原件，原件按材料格里的链接认；
 * 本次采用的原件每份一行，转换稿归回原件、过程件与图片不列，同一份不列两行。节里的链接都要点得开，
 * 表外的链接不算列了原件。贡献写得对不对归独立审查。
 */
export function materialListProblems(ctx, storyText) {
  const problems = [];
  const appendix = appendixChapter(ctx.contract);
  const name = materialSubsectionName(ctx.contract);
  const span = appendix && name ? subsectionSpan(storyText, appendix.title, name) : null;
  if (!span) return { problems, notes: [] };
  const at = `「${appendix.title}·${name}」`;
  const lines = storyText.split(/\r?\n/);
  const fromDir = path.dirname(ctx.storyPath);
  for (let i = span.start; i < span.end && i < lines.length; i++) {
    for (const m of lines[i].matchAll(/\[[^\]]*\]\(([^)\s]+)\)/g)) {
      if (/^(https?:|mailto:)/i.test(m[1]) || fs.existsSync(path.resolve(fromDir, m[1]))) continue;
      problems.push(`${at}第 ${i + 1} 行：链接点不开，${m[1]} 解析不到文件——材料清单的链接按 AR/story.md 所在目录解析，读者据它把材料找出来`);
    }
  }
  const cols = String(ctx.contract.chapters?.find(c => c.appendix)?.projection?.sections?.[name]?.table ?? '').split('|').filter(Boolean);
  const tables = parseDocument(lines.slice(span.start, span.end).join('\n')).tables
    .filter(tb => cols.every(c => tb.header.some(h => h.includes(c))));
  if (cols.length && tables.length !== 1) {
    problems.push(`${at}：要一张表，列为 ${cols.join('｜')}（现在有 ${tables.length} 张）——每行一份外部原件，写它的来源与实际贡献`);
  }
  const set = externalOriginals(ctx);
  if (!set || tables.length !== 1) return { problems, notes: [] };
  problems.push(...set.gaps.map(g => `${at}：${g}`));
  const cell = tables[0].header.findIndex(h => h.includes(cols[0]));
  const listed = new Map();
  tables[0].rows.forEach((row, k) => {
    const line = span.start + tables[0].line + k + 3;
    const link = /\]\(([^)\s]+)\)/.exec(row[cell] ?? '')?.[1];
    if (!link) { problems.push(`${at}第 ${line} 行：材料格里没有链接——每行链到一份原件`); return; }
    const rel = relFromFeature(ctx, path.resolve(fromDir, link));
    if (listed.has(rel)) problems.push(`${at}第 ${line} 行：${rel} 在第 ${listed.get(rel)} 行已经列过——一份原件一行`);
    listed.set(rel, listed.get(rel) ?? line);
    if (set.derived.has(rel)) problems.push(`${at}第 ${line} 行：${rel} 是 ${set.derived.get(rel).join('、')} 的转换稿——列原件，转换稿与抽出的图归回原件`);
    else if (set.internal.has(rel) || IMAGE.test(rel) || (rel.startsWith('AR/story-src/') && !set.originals.has(rel))) {
      problems.push(`${at}第 ${line} 行：${rel} 是过程件、生成件或图片，不是外部原件——清单只列需求系统原件、人工提供的文件与评审反馈`);
    }
  });
  for (const [o, via] of [...set.originals].filter(([x]) => !listed.has(x))) {
    problems.push(`${at}：本次采用的原件 ${o} 没有列${via.length ? `（转换稿是 ${via.join('、')}）` : ''}——每份外部原件一行，材料格链到它`);
  }
  return { problems, notes: [] };
}

/**
 * 需求目录下的相对路径 → **相对 story.md** 的路径。
 *
 * story.md 在 `AR/` 下，而清单记的是相对需求目录的路径（`RR/prd.md`、
 * `assets/x.png`）。差这一层，链接就点不开、图就断链——落盘后 `check` 会逐条报，
 * 而那几条本可以不发生：串是脚本给作者的，算对是脚本的事。
 */
export function relFromStory(rel) {
  return path.posix.relative('AR', String(rel ?? '').split(path.sep).join('/'));
}
