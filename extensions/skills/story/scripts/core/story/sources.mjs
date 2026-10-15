/**
 * 正文的来源与材料贡献清单 —— 这份 story 据哪几份材料写成，哪一份还没在手里。
 *
 * 必需性只在这里判一次：起手预检与交付前的 check 读同一份结果。两处各判一次的话，
 * 同一份缺件会在一处说「本地单缺它正常」、在另一处说「它是必备来源」。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { isSystemRequirement, readText } from './context.mjs';
import { queryFlowStatus } from '../flow/client.mjs';
import { markdownLinks } from './language.mjs';
import { appendixChapter, materialSubsectionName } from './appendix.mjs';
import { normalizeHeading, parseDocument, subsectionSpan } from './document.mjs';
import { decisionList } from './review.mjs';

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
//: 作者除了造一份假的没有别的路。本轮自己派生的产物（Spec、AR 提取稿）两种单都必需：
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

/**
 * 本轮实际采用的输入原件 —— `materials.json` 的 `origins`（registry 按磁盘现状派生）。
 *
 * 作者表不定义这个集合：漏写一行不能让那份原件从核对与审查里消失。集合三种来源：
 * 远端直接给的正文（`direct`）、已确定性并入正文的收件箱原件（`converted-source`，只抽图的原件也在内，
 * 阅读稿是它自己、`image_paths` 列抽出的图）、留存的会议版本（`meeting`）。
 * 图片本身跟着图片说明与取舍走，不逐张进来；没并入的原件走待导入。
 *
 * @returns {{origins: object[], pending: string[]} | null | {gap: string}}
 *   null = 还没有清单（没跑过 round）；gap = 清单在但读不出来源关系
 */
function originSet(ctx) {
  const data = readManifest(ctx);
  if (data === null) return null;
  const fix = '——这份清单由 `story_flow.py round` 按磁盘现状生成';
  if (data === 'broken') return { gap: `AR/story-src/materials.json：读不出材料清单${fix}` };
  if (!Array.isArray(data.origins)) {
    return { gap: 'AR/story-src/materials.json：没有来源关系 `origins`（本版材料清单 schema 2）'
      + `${fix}；旧版做到一半的单按升级演进记录在旧版收口或从 init 重起` };
  }
  const pending = (Array.isArray(data.sources) ? data.sources : [])
    .filter(s => s?.file && !s.ingested).map(s => `inbox/${s.file}`);
  return { origins: data.origins, pending };
}

/** 相对 story 的 markdown 链接串：带空格或括号的路径用 `<…>` 包起来，照抄即可。 */
function mdLink(rel) {
  const to = relFromStory(rel);
  const name = String(rel).split('/').pop();
  return `[${name}](${/[\s()]/.test(to) ? `<${to}>` : to})`;
}

/**
 * 来源集合按阅读稿分组渲染 —— 作者任务包与读者审查任务读同一份。
 *
 * 一组是作者表的一行候选：一份阅读稿，列齐合成它的全部原件与各自的内容摘要；
 * 版本有版号或会议版本时作者写那个，没有就写摘要。链接串相对 story，可以直接粘。
 */
export function originRows(ctx) {
  const set = originSet(ctx);
  if (set === null) return ['还没有材料清单 `AR/story-src/materials.json`——先跑 `story_flow.py round`。'];
  if (set.gap) return [`**输入有缺口**：${set.gap}。`];
  const groups = new Map();
  for (const o of set.origins) {
    const key = (o.readable_paths ?? []).join('、') || o.path;
    if (!groups.has(key)) groups.set(key, { readable: o.readable_paths ?? [], items: [] });
    groups.get(key).items.push(o);
  }
  const KIND = { direct: '远端直接给的正文', 'converted-source': '收件箱原件，确定性并入', meeting: '会议留存版本' };
  const digest = o => String(o.sha256 ?? '').replace(/^sha256:/, '').slice(0, 8);
  const rows = [...groups.values()].map((g) => {
    const pictures = g.items.flatMap(o => o.image_paths ?? []);
    if (pictures.length) {
      // 只抽图的原件：一份原件一行，材料列与来源列都指它自己；图不逐张成行，说明与取舍见图片登记
      return `- 原件 ${g.items.map(o => `\`${mdLink(o.path)}\`（摘要 ${digest(o)}）`).join('、')}只取图，正文没有并入：`
        + `抽出 ${pictures.length} 张（${pictures.map(p => p.split('/').pop()).join('、')}），用了哪几张、不用的理由见图片登记；`
        + '贡献写采用了哪些视觉信息，全部不用也写理由';
    }
    return `- 阅读稿 ${g.readable.map(r => `\`${mdLink(r)}\``).join('、') || '（读不到）'}`
      + ` ← 来源 ${g.items.map(o => `\`${mdLink(o.path)}\`（${KIND[o.kind] ?? o.kind}，摘要 ${digest(o)}）`).join('、')}`;
  });
  if (!rows.length) rows.push('- （本轮没有可采用的正文来源）');
  for (const rel of set.pending) rows.push(`- **还没并入正文**：\`${rel}\`——先按 inbox 导入规则导入，作者表写一行替代不了导入`);
  return rows;
}

// --------------------------------------------------------------------------
// 依据标签：「上游约束：<材料名>」「已确认决定：<ID>」的名字与对象
// --------------------------------------------------------------------------

//: 标签之后的名字按已登记的名字整串认（名字里可以有括号、逗号、空格），名字后要接分隔或行尾，
//: 以免「产品需求说明」被当成「产品需求」。对不上时报错里引的那段到常见分隔为止。
const TAG_RE = /(上游约束|已确认决定)[:：]\s*/g;
const NAME_BOUNDARY = /^(?:$|[\s）)，,；;。、「」：:])/;
const SHOWN_RE = /^[^）)，,；;。、\n]+/;

/**
 * 本轮可引用的来源与决定 —— 作者任务包、Spec 门禁、附录投影与审查共用这一份解析。
 *
 * 对象是一份原件或阅读稿（相对需求目录的登记路径）。名字只从登记事实来：登记路径、完整文件名、
 * 去扩展名（只对上一份时成立）、合同来源显示名；会议另认留存时的原文件名（`source.json`），
 * 同名多版写 `<原名>@<版本>`。决定只认 `decisions.json` 的 id。缺件、元数据坏、会议原件与登记
 * 对不上记进 gaps，不从目录名猜。
 */
export function sourceCatalog(featureRoot, contract) {
  const names = new Map();
  const shown = new Map();
  const gaps = [];
  const add = (name, key) => { if (name) names.set(name, new Set([...(names.get(name) ?? []), key])); };
  const fileNames = (rel, key) => {
    const file = String(rel).split('/').pop();
    add(rel, key); add(file, key); add(file.replace(/\.[^.]+$/, ''), key);
  };
  const json = rel => { try { return JSON.parse(readText(path.join(featureRoot, rel)).replace(/^\ufeff/, '')); } catch { return undefined; } };
  const manifest = readManifest({ srcDir: path.join(featureRoot, 'AR', 'story-src') });
  let origins = manifest?.origins ?? [];
  if (manifest !== null && !Array.isArray(manifest?.origins)) {
    gaps.push('AR/story-src/materials.json 读不出来源关系 `origins`——这份清单由 `story_flow.py round` 生成');
    origins = [];
  }
  const readers = new Map();
  for (const o of origins) {
    fileNames(o.path, o.path);
    shown.set(o.path, String(o.path).split('/').pop());
    if (o.kind === 'meeting') {
      const dir = path.posix.dirname(o.path);
      const meta = json(`${dir}/source.json`);
      const want = String(o.sha256 ?? '').replace(/^sha256:/, '');
      if (!meta?.file || !want || !String(meta.sha256 ?? '').startsWith(want)) {
        gaps.push(`${dir}/source.json：读不出会议原文件名，或它记的原件摘要与材料清单的 ${o.sha256} 对不上——重跑 \`story_flow.py round\` 重新留存`);
      } else {
        const version = path.posix.basename(dir);
        fileNames(meta.file, o.path);
        add(`${meta.file}@${version}`, o.path);
        add(`${String(meta.file).replace(/\.[^.]+$/, '')}@${version}`, o.path);
        shown.set(o.path, meta.file);
      }
    }
    for (const r of o.readable_paths ?? []) {
      if (r === o.path) continue;
      fileNames(r, r);
      readers.set(r, [...(readers.get(r) ?? []), o.path]);
    }
  }
  const labeled = [];
  for (const decl of Object.values(contract?.sources ?? {})) {
    if (!decl?.label || !decl?.path || decl.derived || !fs.existsSync(path.join(featureRoot, decl.path))) continue;
    add(decl.label, decl.path);
    shown.set(decl.path, decl.label);
    labeled.push(decl.path);
  }
  // 同名的会议版本给人看时带上版本，读者分得出是哪一次
  const meetings = origins.filter(o => o.kind === 'meeting');
  for (const o of meetings) {
    if (meetings.filter(x => shown.get(x.path) === shown.get(o.path)).length > 1) {
      shown.set(o.path, `${shown.get(o.path)}（版本 ${path.posix.basename(path.posix.dirname(o.path))}）`);
    }
  }
  for (const [r, from] of readers) if (!shown.has(r)) shown.set(r, from.map(k => shown.get(k)).join('、'));
  const register = fs.existsSync(path.join(featureRoot, 'AR', 'story-src', 'decisions.json'))
    ? decisionList(json('AR/story-src/decisions.json')) : [];
  if (!register) gaps.push('AR/story-src/decisions.json 读不出登记列表');
  const decisions = (register ?? []).filter(d => d?.id);
  // 同一个 id 登记了几条：哪条算数说不清，引用它的标签一律不认，不让后一条盖住前一条
  const ids = decisions.map(d => String(d.id));
  const twice = [...new Set(ids.filter((id, i) => ids.indexOf(id) !== i))];
  if (twice.length) gaps.push(`AR/story-src/decisions.json 里 ${twice.join('、')} 各登记了不止一条——一个议题一条`);
  return { names, shown, gaps, registered: manifest !== null, primary: [...new Set([...origins.map(o => o.path), ...labeled])],
    decisions: new Map(decisions.filter(d => !twice.includes(String(d.id))).map(d => [String(d.id), d])) };
}

/** 这个对象给作者照抄的唯一写法：人读名、完整文件名、带版本的会议名，都不唯一时写登记路径。 */
function uniqueName(catalog, key) {
  const only = n => catalog.names.get(n)?.size === 1;
  const file = String(key).split('/').pop();
  const meeting = [...catalog.names].find(([n, k]) => k.size === 1 && k.has(key) && n.includes('@'))?.[0];
  return [catalog.shown.get(key), file, meeting].find(n => n && only(n) && catalog.names.get(n).has(key)) ?? key;
}

/**
 * 一段正文里的依据标签逐个解析：认到哪个对象或决定、显示成什么；认不到、有歧义、
 * 决定未定或依据字段不全的列进 problems（带行号）。
 */
export function resolveTags(text, catalog) {
  const hits = [];
  const problems = [];
  const known = [...catalog.names.keys()].sort((a, b) => b.length - a.length);
  const ids = [...catalog.decisions.keys()].sort((a, b) => b.length - a.length);
  const lineOf = at => String(text).slice(0, at).split(/\r?\n/).length;
  for (const m of String(text).matchAll(TAG_RE)) {
    const from = m.index + m[0].length;
    const rest = String(text).slice(from);
    const where = `第 ${lineOf(m.index)} 行`;
    const pick = list => list.find(n => rest.startsWith(n) && NAME_BOUNDARY.test(rest.slice(n.length)));
    const wrote = (SHOWN_RE.exec(rest)?.[0] ?? '').trim() || '（空）';
    if (m[1] === '已确认决定') {
      const id = pick(ids);
      const d = id ? catalog.decisions.get(id) : null;
      if (!d) problems.push(`${where}「已确认决定：${wrote}」：decisions.json 里没有这个 id（现有 ${ids.join('、') || '无'}）`);
      else if (d.status !== 'settled') problems.push(`${where}「已确认决定：${id}」：这条是 ${d.status ?? '无状态'}，还没人定——正文写成条件并标议题，不当已确认的依据`);
      else if (!String(d.clarification ?? '').trim() || !String(d.decider ?? '').trim()) {
        problems.push(`${where}「已确认决定：${id}」：登记缺澄清正文或 decider，依据指不到谁在哪定的`);
      }
      if (d) hits.push({ from, to: from + id.length, display: `${id}（${String(d.title ?? '').trim()}）` });
      continue;
    }
    if (!catalog.registered) {
      problems.push(`${where}「上游约束：${wrote}」：还没有材料清单 AR/story-src/materials.json，材料名无从核——先跑 \`story_flow.py round\``);
      continue;
    }
    const name = pick(known);
    const keys = name ? catalog.names.get(name) : null;
    if (!keys) {
      problems.push(`${where}「上游约束：${wrote}」对不上本轮任何一份材料`);
    } else if (keys.size > 1) {
      problems.push(`${where}「上游约束：${name}」对上了 ${keys.size} 份，写唯一的名字：${[...keys].map(k => uniqueName(catalog, k)).join('、')}`);
    } else {
      hits.push({ from, to: from + name.length, display: catalog.shown.get([...keys][0]) ?? name });
    }
  }
  // 清单与登记的结构缺口自己就是问题：不等标签报错才顺带出现
  return { hits, problems: [...problems, ...catalog.gaps] };
}

/** 认到的标签换成读者认得的名字：会议写原文件名、合同来源写显示名，决定带上标题。 */
export function displayTags(text, catalog) {
  const { hits } = resolveTags(text, catalog);
  let out = String(text);
  for (const h of [...hits].reverse()) out = out.slice(0, h.from) + h.display + out.slice(h.to);
  return out;
}

/** 作者动笔前拿到的可引用名：每个对象一行唯一写法与人读名，已定决定逐条给 ID。 */
export function citableRows(catalog) {
  const rows = [...catalog.primary].sort()
    .map(k => `- \`上游约束：${uniqueName(catalog, k)}\` —— ${catalog.shown.get(k) ?? k}（${k}）`);
  const settled = [...catalog.decisions.values()].filter(d => d.status === 'settled');
  rows.push(...settled.map(d => `- \`已确认决定：${d.id}\` —— ${String(d.title ?? '').trim()}`));
  return [...(rows.length ? rows : ['- （本轮还没有可引用的材料或已定决定）']),
    ...catalog.gaps.map(g => `- **登记有缺口**：${g}`)];
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
// 从 spec 派生：story 相对 spec 只能增加，不能减少
// --------------------------------------------------------------------------

/**
 * story 的上游有哪几份 —— 系统设计与 spec，读不到的那份不算，不猜。
 *
 * 上游只列到这两份：产品需求文档里一般不画 `mermaid`，为它留一条通道是空的；
 * 真出现了，作者按内容搬进 story 就是，机器不为一份没有图的文档立判据。
 */
export function upstreamDocs(ctx) {
  const out = [];
  // 标签是图源标记里写的那个名字；路径以合同 `sources` 为准
  for (const [label, key] of [['SR', 'SE'], ['spec', 'SPEC']]) {
    const rel = ctx.contract.sources?.[key]?.path;
    const text = rel ? readText(path.join(ctx.featureRoot, rel)) : null;
    if (text !== null) out.push([label, text]);
  }
  return out;
}

/**
 * 把材料清单那一节里的 markdown 链接换成一个占位词，再交给仓内路径与文档坐标扫描。
 *
 * **原文链接是仓内路径唯一允许出现的位置**：归档件的读者打不开这个仓，但他要能
 * 据这一行把那份材料找出来——链接是「据哪几份材料写成」这件事唯一可核的形态。
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
    const { links } = markdownLinks(lines[i]);
    for (const l of [...links].reverse()) lines[i] = lines[i].slice(0, l.start) + '原文链接' + lines[i].slice(l.end);
  }
  return lines.join('\n');
}

/** 附录·材料清单那张表的表头：合同附录章 `subsection_tables` 登记，脚本不留字面。 */
function materialTableHeader(contract) {
  const name = materialSubsectionName(contract);
  const want = normalizeHeading(name ?? '');
  const raw = Object.entries(appendixChapter(contract)?.subsection_tables ?? {})
    .find(([k]) => normalizeHeading(k) === want)?.[1];
  return raw ? String(raw).split('|').map(h => h.trim()) : null;
}

/** 附录·材料清单的骨架：只有表头，行由作者按任务包给的来源集合写。 */
export function materialListSkeleton(ctx) {
  const header = materialTableHeader(ctx.contract);
  return header ? [`| ${header.join(' | ')} |`, `|${header.map(() => '---').join('|')}|`] : [];
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
    { timeoutMs: 120000 });
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

/**
 * 材料清单那一节：一张「材料 | 来源 | 贡献」表，链接点得开，来源与 `origins` 对得上。
 *
 * 机器只核身份与覆盖：漏了哪份原件、哪份原件写了两行、列了集合外的东西（生成件、没导入的原件、图）、
 * 链接指不到文件、材料列不是这几份原件的阅读稿。贡献写得真不真、采用版本对不对、该不该采用，
 * 归独立审查——机械覆盖通过不等于忠实。问题一次列全。
 */
export function materialListProblems(ctx, storyText) {
  const problems = [];
  const notes = [];
  const appendix = appendixChapter(ctx.contract);
  const name = materialSubsectionName(ctx.contract);
  const span = appendix && name ? subsectionSpan(storyText, appendix.title, name) : null;
  if (!span) return { problems, notes };
  const where = `「${appendix.title}·${name}」`;
  const header = materialTableHeader(ctx.contract);
  if (!header) {
    problems.push(`章节合同附录章的 subsection_tables 没登记「${name}」的表头——这张表按合同登记的列核，维护者补合同`);
    return { problems, notes };
  }
  const lines = storyText.split(/\r?\n/).slice(span.start, span.end);
  const doc = parseDocument(lines.join('\n'));
  const lineNo = i => span.start + 1 + i;
  const tables = doc.tables.filter(t => t.header.map(normalizeHeading).join('|') === header.map(normalizeHeading).join('|'));
  const inTable = new Set(tables.flatMap(t => Array.from({ length: t.rows.length + 2 }, (_, k) => t.line + k)));
  if (tables.length !== 1) {
    problems.push(`${where}：要${tables.length ? '只有' : ''}一张表头为「${header.join(' | ')}」的表（现在 ${tables.length} 张）`
      + '——一行一份阅读稿：材料列写名称与阅读稿链接，来源列列齐它的全部原件链接与采用版本，贡献列写采用了什么、未采用写原因');
  }
  lines.forEach((line, i) => {
    if (inTable.has(i) || doc.fenced.has(i) || !markdownLinks(line).links.length) return;
    problems.push(`${where}第 ${lineNo(i)} 行：表外有链接——材料与来源只写在「${header.join(' | ')}」表里，列表写法已退出`);
  });

  const set = originSet(ctx);
  if (set === null) notes.push('AR/story-src/materials.json：不在，来源覆盖未核——这份清单由 `story_flow.py round` 生成');
  if (set?.gap) problems.push(`${set.gap}；${where}的来源覆盖按它核`);
  const origins = new Map((set?.origins ?? []).map(o => [o.path, o]));
  const pending = new Set(set?.pending ?? []);
  const generated = new Set([relFromFeature(ctx, ctx.storyPath),
    ...Object.values(ctx.contract.sources ?? {}).filter(d => d?.derived && d.path).map(d => d.path)]);
  const srcDir = ctx.srcDir ? `${relFromFeature(ctx, ctx.srcDir)}/` : null;
  const storyDir = path.dirname(relFromFeature(ctx, ctx.storyPath));
  const fromDir = path.dirname(ctx.storyPath);
  const rowsOf = new Map();

  const table = tables[0];
  (table?.rows ?? []).forEach((cells, r) => {
    const at = `${where}第 ${lineNo(table.line + 2 + r)} 行`;
    if (cells.length !== header.length) {
      problems.push(`${at}：${cells.length} 格，表头是 ${header.length} 列——格里的竖线写成 \`\\|\``);
      return;
    }
    const cell = k => markdownLinks(cells[k]);
    const [mat, src] = [cell(0), cell(1)];
    for (const b of [...mat.bad, ...src.bad]) {
      problems.push(`${at}：链接写法解析不了（${b.text}）——带空格或括号的路径写成 \`[名称](<路径>)\``);
    }
    if (!mat.links.length) problems.push(`${at}：材料列没有阅读稿链接`);
    if (!src.links.length) problems.push(`${at}：来源列没有原件链接`);
    if (!cells[2].replace(/\{\{[^}]*\}\}/g, '').trim()) problems.push(`${at}：贡献列是空的——写采用了什么，未采用写原因`);
    const resolve = (l) => {
      let rel;
      try { rel = joinPosix(storyDir, decodeURI(l.target)); } catch { rel = joinPosix(storyDir, l.target); }
      if (/^(https?:|mailto:)/i.test(l.target)) return null;
      if (!fs.existsSync(path.resolve(fromDir, l.target)) && !fs.existsSync(path.join(ctx.featureRoot, rel))) {
        problems.push(`${at}：链接点不开，${l.target} 解析不到文件——链接按 ${relFromFeature(ctx, ctx.storyPath)} 所在目录解析`);
        return null;
      }
      return rel;
    };
    const readable = new Set();
    for (const l of src.links) {
      const rel = resolve(l);
      if (!rel || !set || set.gap) continue;
      if (l.image || /\.(png|jpe?g|webp|bmp|gif|svg)$/i.test(rel)) {
        problems.push(`${at}：来源列放了图 ${rel}——图不进这张表，图的说明与不用的理由走图片登记`);
      } else if (origins.has(rel)) {
        if (!rowsOf.has(rel)) rowsOf.set(rel, []);
        rowsOf.get(rel).push(at);
        for (const x of origins.get(rel).readable_paths ?? []) readable.add(x);
      } else if (pending.has(rel)) {
        problems.push(`${at}：${rel} 还没并入正文——先导入，作者表写一行替代不了导入`);
      } else if (generated.has(rel) || (srcDir && rel.startsWith(srcDir))) {
        problems.push(`${at}：${rel} 是本轮生成件，不是来源——来源列只收 materials.json 的 origins`);
      } else {
        problems.push(`${at}：${rel} 不在本轮来源集合里——来源列只收 materials.json 的 origins`
          + '（远端直接给的正文、已并入正文的收件箱原件、会议留存版本）');
      }
    }
    for (const l of mat.links) {
      const rel = resolve(l);
      if (rel && readable.size && !readable.has(rel)) {
        problems.push(`${at}：材料列链到 ${rel}，不是来源列那几份原件的阅读稿（${[...readable].join('、')}）`);
      }
    }
  });
  for (const [rel, ats] of rowsOf) {
    if (ats.length > 1) problems.push(`${where}：原件 ${rel} 写在了 ${ats.length} 行（${ats.join('、')}）——一份原件只在它的阅读稿那一行出现`);
  }
  for (const o of set?.origins ?? []) {
    if (!rowsOf.has(o.path)) {
      problems.push(`${where}：少了来源 ${o.path}（阅读稿 ${(o.readable_paths ?? []).join('、')}）`
        + '——集合按 materials.json 的 origins 核，任务包「材料与来源」一节逐份列着');
    }
  }
  return { problems, notes };
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
