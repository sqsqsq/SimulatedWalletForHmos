/**
 * 附录 —— spec 契约与规约判定的投影、手改保护，以及附录自己的结构判据。
 *
 * 附录是全篇唯一允许出现工程标识的地方，于是它天然最容易变成倾倒区。这里管两件事：
 * 机器区**从真源重算**（不读旧 story，读旧的就成了真源加一份会漂的副本），
 * 以及作者区与机器区的分界——有人在机器区写过字就停下，不静默盖掉。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { renderTable } from './chapter-contract.mjs';
import {
  chapterSpan, norm, normalizeHeading, sectionBody, sectionNames, zoneBlock,
  zoneHandEdited, zoneSpan, ZONE_BEGIN,
} from './document.mjs';
import { fail, activeKnowledgeEntries, readJson, readText, specText } from './context.mjs';
import { readUse, UseError } from '../../../../../hooks/shared/knowledge-use.mjs';

/** 规约判定表的取值封闭；整域不适用时该域内条目不必逐条列。 */
const DOMAIN_NA = '整域不适用';

/**
 * spec 侧那份判断里，每条规约命中与否 —— `{ 编号 → 是否命中 }`。
 *
 * 读不到那份 YAML 时返回 null：走 `/story` 之外的路径、或者 spec 还没写到那一步，
 * 都是正常形态，此时这一条不判（**不是判过了**）。
 */
function knowledgeUseVerdicts(ctx, entries = []) {
  if (ctx.offline) return null;
  const reviewActions = new Map(entries.filter(e => e.reviewAction)
    .map(e => [e.id, e.handling ?? '']));
  try {
    const use = readUse(ctx.projectRoot, ctx.args.feature);
    const rows = new Map();
    for (const row of use.constraints) {
      const id = String(row?.id ?? '').trim();
      // 依据也一起带回来：判断已经写在那份 YAML 里（命中写 requirement、
      // 不命中写 reason），让作者对着它再抄一遍，抄出来的只会更短。
      // requirement 是列表（一条要求一句）：**全部带上**，同一格里分号隔开——
      // 只取第一条的话，附录 D 就成了 §10 的一个截断视图。
      if (id) {
        const req = Array.isArray(row.requirement) ? row.requirement : [row.requirement];
        // 评审动作条目命中时没有 requirement——它的结果是一次跨团队的动作。
        // 依据取 reason，前面带上处置原文：评审者看这一行要知道命中之后做了什么。
        const action = reviewActions.get(id);
        const reason = String(row.reason ?? '').trim();
        rows.set(id, { applicable: row.applicable === true,
          basis: (row.applicable === true
            ? (action !== undefined ? [action, reason].filter(Boolean).join('：')
              : req.map(x => String(x ?? '').trim()).filter(Boolean).join('；'))
            : reason) });
      }
    }
    // 整域不适用是那份 YAML 允许的另一种登记：一个域一行，域内条目不必逐条写。
    // 不认它的话，作者按规矩写完，投影反倒说他缺依据。
    const naDomains = new Map();
    for (const row of use.domains ?? []) {
      const prefix = String(row?.prefix ?? '').trim();
      if (prefix) naDomains.set(prefix, String(row?.reason ?? '').trim());
    }
    return { rows, naDomains };
  } catch (e) {
    if (e instanceof UseError) return null;
    throw e;
  }
}

/** 附录那一章（合同里标了 `appendix` 的那个）。没有就返回 null。 */
export function appendixChapter(contract) {
  return (contract.chapters ?? []).find(c => c.appendix) ?? null;
}

/**
 * 从一章的正文里切出某个 `###` 小节的辅助已迁至 story/chapter-contract.mjs；
 * 入口仍有消费者的按需 import 同一导出，不在这里保留第二份实现。
 */

/** spec 里某一节的正文：从命中标题的那一行到下一个同级或更高级标题之前。 */
function specSection(text, re) {
  const lines = String(text ?? '').split(/\r?\n/);
  const start = lines.findIndex(l => /^#{2,3}\s/.test(l.trim()) && re.test(l));
  if (start < 0) return '';
  const level = (lines[start].trim().match(/^#+/) ?? ['##'])[0].length;
  const body = [];
  for (let i = start + 1; i < lines.length; i += 1) {
    const head = lines[i].trim().match(/^(#+)\s/);
    if (head && head[1].length <= level) break;
    body.push(lines[i]);
  }
  return body.join('\n');
}

/** 一段文本里的表：每张给 {header, rows}，单元格已去掉首尾空串与行内标记。 */
function pipeTables(text) {
  const out = [];
  let cur = null;
  for (const line of String(text ?? '').split(/\r?\n/)) {
    const t = line.trim();
    if (!t.startsWith('|')) { cur = null; continue; }
    const cells = t.replace(/^\||\|$/g, '').split('|').map(c => c.trim());
    if (/^[-: ]+$/.test(cells.join(''))) continue;
    if (!cur) { cur = { header: cells, rows: [] }; out.push(cur); continue; }
    cur.rows.push(cells);
  }
  return out;
}

/** 模板占位单元格（`{ 接口名 }` 这种）——spec 没填时不该派生进 story。 */
function isPlaceholderRow(cells) {
  return cells.every(c => !c || /^\{.*\}$/.test(c) || /^[-—]$/.test(c));
}

/**
 * spec §0 里属于本需求的业务术语 → `[[术语, 解释]]`。
 *
 * 只取权威模块落在 `in_scope_modules` 里的行：那几行才是本需求的业务词汇，
 * 也是 spec 的 post_check 要求写「解释」的那几行。基础能力与模块名不进来——
 * story 是给业务评审者看的读物，模块名对他没有意义。
 */
export function specTerms(text) {
  const scope = new Set(scopeList(text, 'in_scope_modules'));
  const table = pipeTables(specSection(text, /术语映射表/))[0];
  if (!table || !scope.size) return [];
  const at = (needle) => table.header.findIndex(h => h.includes(needle));
  const [term, mod, why] = [0, at('权威模块'), at('解释')];
  if (mod < 0 || why < 0) return [];
  return table.rows
    .filter(r => scope.has((r[mod] ?? '').trim()) && !isPlaceholderRow(r))
    .map(r => [(r[term] ?? '').trim(), (r[why] ?? '').trim()])
    .filter(([t, w]) => t && w && w !== '—');
}

/** spec 头部声明的模块清单（`in_scope_modules` / `out_of_scope_modules`）。 */
export function scopeList(text, key) {
  const block = String(text ?? '').match(new RegExp(key + String.raw`:\s*\n((?:\s*-\s*.+\n)+)`));
  return (block?.[1] ?? '').split(/\r?\n/)
    .map(l => l.match(/^\s*-\s*(.+?)\s*$/)?.[1]).filter(Boolean);
}

/**
 * 附录·改动边界 —— 「这次改了哪里、哪里保证不动」就是 Scope 的两份清单。
 *
 * **一个模块一行**。两份清单各挤成一格的话，评审者要在一串顿号里找自己那个模块，
 * 而「它是改还是不改」正是他打开这一节要问的第一件事。
 */
function scopeBoundaryRows(spec) {
  const rows = [];
  for (const m of scopeList(spec, 'in_scope_modules')) {
    rows.push([m, '改动']);
  }
  for (const m of scopeList(spec, 'out_of_scope_modules')) {
    rows.push([m, '不改']);
  }
  return rows;
}

/**
 * Scope 的说明段 —— **原样引一次**，不拆。
 *
 * 它是一整段，讲的是这一轮为什么这么切；脚本不猜哪一句对应哪个模块——
 * 猜错了读者会把别的模块的理由读到自己那一行上。
 */
function scopeRationale(spec) {
  const block = String(spec ?? '').match(/rationale:\s*\|\s*\n((?:[ \t]+.*\n?)+)/);
  if (!block) return null;
  const lines = block[1].replace(/\s+$/, '').split(/\r?\n/);
  const indent = Math.min(...lines.filter(l => l.trim())
    .map(l => l.match(/^[ \t]*/)[0].length));
  return lines.map(l => l.slice(indent)).join('\n').trim() || null;
}

//: 不投进归档件的列。「代码现状」是 spec 写给下游 AI 的——仓内路径或检索结论，
//: 读者打不开也用不上，进了归档件还会撞上「不写仓内路径」「不写检索措辞」两条红线，
//: 而机器区作者改不了。投影策略只有这一条，不在合同里逐表登记列白名单：
//: 那会与 spec 模板形成第二真源。
const DROP_COLUMNS = ['代码现状'];

//: 附录三节各从 spec §9 的哪几个小节生成。附录的读者要「拿着回查」，
//: 所以行必须齐——集合核（⑫）盯的就是这里。
const APPENDIX_FROM_SPEC = [
  ['接口', [{ at: '§9.1', re: /^###\s*9\.1/ }]],
  ['数据、配置与事件', [{ at: '§9.2', re: /^###\s*9\.2/ },
    { at: '§9.3', re: /^###\s*9\.3/ }, { at: '§9.4', re: /^###\s*9\.4/ }]],
  ['改动边界', [{ at: '§9.5', re: /^###\s*9\.5/ }]],
];

/** 某个附录小节该有的表：spec 对应几节就给几张，表头按原顺序带过来（去掉不投的列）。 */
function appendixTables(spec, name) {
  const from = APPENDIX_FROM_SPEC.find(x => normalizeHeading(x[0]) === normalizeHeading(name));
  if (!spec || !from) return [];
  const out = [];
  for (const { re } of from[1]) {
    for (const t of pipeTables(specSection(spec, re))) {
      const keep = t.header.map((h, i) => [h, i])
        .filter(([h]) => !DROP_COLUMNS.some(d => h.includes(d)));
      const rows = t.rows.filter(r => !isPlaceholderRow(r))
        .map(r => keep.map(([, i]) => r[i] ?? ''));
      if (rows.length) out.push({ header: keep.map(([h]) => h), rows });
    }
  }
  return out;
}

/** 一张表渲染成 markdown 行。 */
// renderTable（表格渲染）已迁至 story/chapter-contract.mjs，入口与它共用同一导出。

/** 附录里承载材料清单的那一节的名字（合同数据，本文件不写业务词）。 */
export function materialSubsectionName(contract) {
  const appendix = appendixChapter(contract);
  return (appendix?.subsections ?? []).find(n => n.includes('材料')) ?? null;
}

/** 附录里由脚本投影的那张表的表头 —— 登记在合同，脚本不留字面。 */
function appendixTableHeader(ctx, name) {
  const want = normalizeHeading(name);
  const table = Object.entries(appendixChapter(ctx.contract)?.subsection_tables ?? {})
    .find(([k]) => normalizeHeading(k) === want)?.[1];
  if (!table) fail(`合同的附录没登记「${name}」这一节的表头（subsection_tables）`);
  return String(table).split('|').map(h => h.trim());
}

/**
 * 附录某一节的投影：这一节从哪个真源来、投出来是哪几行。
 *
 * **不含任何占位**：机器区里出现「作者要填的格子」，作者填了会被下一次投影打回，
 * 不填就一直挂着。要作者写的东西全在草稿的作者区。
 * 材料清单不在这里——那一节的「贡献了什么」只有作者知道，它归作者。
 * 多张表之间空一行：连着写 markdown 会把它们并成一张错表。
 */
function appendixProjection(ctx, spec, name) {
  const want = normalizeHeading(name);
  if (want === normalizeHeading('改动边界')) {
    const rows = scopeBoundaryRows(spec);
    const tables = appendixTables(spec, name);
    // §9.5 的依赖变更并进同一张表：评审者问的是「这一轮动了什么」，
    // 模块与依赖是同一个问题的两半，分成两张形状不一的表要读两遍。
    //
    // **第一列原样搬 spec 的**：⑫b 按第一列对齐集合核「附录 ⊇ spec §9」，
    // 加个前缀这一行就对不上了——而机器区没有作者，他删不掉也改不动。
    // 「这一行讲的是依赖」放第二列说。
    for (const t of tables) {
      for (const r of t.rows) {
        if (isPlaceholderRow(r)) continue;
        rows.push([(r[0] ?? '').trim(), `依赖：${(r[1] ?? '').trim() || '变更'}`]);
      }
    }
    if (!tables.length) {
      // 依赖没有变更也是结论，丢了它 story 相对 spec 就减了一条。
      const na = specNotApplicable(spec, name);
      rows.push(['依赖', na || '不涉及']);
    }
    // 说明原文进表里成一行，不挂在表后当散文：附录的形态是「一句目的句 + 表格行」，
    // 表后的散文段由 ⑫ 判为倾倒区。机器区没有作者——挂在表后的话，
    // 他删掉、`project` 写回来，判据再报，他只能去改门禁。
    const why = scopeRationale(spec);
    rows.push(['为什么这么切', why ? why.replace(/\s*\n\s*/g, ' ')
      : '本单的范围声明里没有写']);
    const out = renderTable(appendixTableHeader(ctx, name), rows);
    return ['本单的范围声明与上游的依赖变更', out];
  }
  if (want.includes(normalizeHeading('规约判定'))) {
    return ['spec/knowledge-use.yaml', verdictSkeleton(ctx)];
  }
  const tables = appendixTables(spec, name);
  const rows = tables.flatMap((t, i) => i ? ['', ...renderTable(t.header, t.rows)]
    : renderTable(t.header, t.rows));
  if (!rows.length) {
    const na = specNotApplicable(spec, name);
    return ['上游登记的技术契约', na ? [na] : []];
  }
  return ['上游登记的技术契约', rows];
}

/**
 * 把附录的机器区投影进 story —— **投影的唯一入口**，两个时点都走它。
 *
 * ① `chapter` 落盘附录章之后：作者的草稿里只有目的句与材料清单，A–D 由这里投出来，
 *    他登记前跑 `check` 才不会因为那四节是空的而红；
 * ② `story_flow.py story` 登记时：真源在成文期间还会变（补一条规约判定、改一个接口），
 *    以登记这一次为准。
 *
 * 每次都从当前真源重算，不读旧 story：读旧的就成了「真源 + 一份会漂移的副本」。
 */
/**
 * spec 那一节写的「不涉及：<依据>」——它也是结论，评审者要看到。
 *
 * 读不出这样一行就返回 null：那时那一节是真的空，旧机器区该删掉，
 * 由 `check ⑫` 报空节，而不是让上一版的内容留在归档件里冒充现状。
 */
function specNotApplicable(spec, name) {
  const from = APPENDIX_FROM_SPEC.find(x => normalizeHeading(x[0]) === normalizeHeading(name));
  if (!spec || !from) return null;
  for (const { re } of from[1]) {
    const hit = specSection(spec, re).split(/\r?\n/)
      .map(l => l.trim()).find(l => /^不涉及[:：]\s*\S/.test(l));
    if (hit) return hit;
  }
  return null;
}

export function projectAppendix(ctx, storyText) {
  const appendix = appendixChapter(ctx.contract);
  if (!appendix) return { text: storyText, zones: 0 };
  const span = chapterSpan(storyText, appendix.title);
  if (!span) return { text: storyText, zones: 0 };
  const spec = specText(ctx);
  const materialName = normalizeHeading(materialSubsectionName(ctx.contract) ?? '');
  let lines = storyText.slice(span.start, span.end).split(/\r?\n/);
  let zones = 0;
  // 集合对账：合同里有的按真源重投，合同里没有的区块删掉——某一节从合同去掉或改名之后，
  // 旧区会一直挂着，而它指的真源已经没人维护了。
  const want = new Set((appendix.subsections ?? []).map(normalizeHeading));
  for (const line of [...lines]) {
    if (!line.startsWith(ZONE_BEGIN)) continue;
    const name = line.slice(ZONE_BEGIN.length).split(' · ')[0].trim();
    const at = want.has(normalizeHeading(name)) ? null : zoneSpan(lines, name);
    if (at) lines = [...lines.slice(0, at.start), ...lines.slice(at.end)];
  }
  for (const name of appendix.subsections ?? []) {
    if (normalizeHeading(name) === materialName) continue;    // 材料清单归作者
    const [source, rows] = appendixProjection(ctx, spec, name);
    const at0 = zoneSpan(lines, name);
    // 真源那一节现在什么都没有了（规约全退出激活清单、spec 那一节被删或改空）：
    // 旧区要删，不能留着上一版冒充现状。删完那一节由 `check ⑫` 报空节——
    // 那是正确的告警，它指向真源，不指向作者。
    if (!rows.length) {
      if (at0) lines = [...lines.slice(0, at0.start), ...lines.slice(at0.end)];
      continue;
    }
    const block = zoneBlock(name, source, rows);
    if (at0 && zoneHandEdited(lines, at0, rows)) {
      // 停在这里，不盖。他写的那几行是他花时间想出来的；静默盖掉的话，
      // 东西没了而他不知道，下一次还会再写一遍。
      fail(`「${name}」这一节由${source}投影，盘上的内容与投影对不上——`
        + '要改结论，改真源之后重跑；'
        + '要撤销这里的手改，把这一节（含首尾两行标记）删掉再跑，投影会重新写出来');
    }
    zones += 1;
    if (at0) { lines = [...lines.slice(0, at0.start), ...block, ...lines.slice(at0.end)]; continue; }
    // 作者那一节还没有机器区：插到该节末尾。节都没有就说明附录章还没落盘，跳过。
    const want = normalizeHeading(name);
    const head = lines.findIndex(l => /^###\s+/.test(l.trim())
      && normalizeHeading(l.trim().slice(3)).includes(want));
    if (head < 0) { zones -= 1; continue; }
    let end = lines.findIndex((l, i) => i > head && /^###\s+/.test(l.trim()));
    if (end < 0) end = lines.length;
    lines = [...lines.slice(0, end), ...block, '', ...lines.slice(end)];
  }
  return { text: storyText.slice(0, span.start) + lines.join('\n') + storyText.slice(span.end),
    zones };
}

/**
 * 附录·规约判定的整张表 —— **依据也取真源**。
 *
 * 判断已经写在 `spec/knowledge-use.yaml` 里：不命中写的是为什么不适用，
 * 命中写的是这一轮要满足的要求。让作者对着那份 YAML 再抄一遍依据，
 * 抄出来的只会更短。他要改的是措辞，改在这里，改完由 ⑫b 核集合。
 */
function verdictSkeleton(ctx) {
  const entries = activeKnowledgeEntries(ctx);
  if (!entries.length) return [];
  const use = knowledgeUseVerdicts(ctx, entries);
  // 判断骨架还没生成（离线、或 knowledge-use.yaml 不在）：投不出来就不投，
  // 那一节保持原样，缺表由 check ⑦ 报。这一步不代替它下结论。
  // 文件在却读不出判断，那是它写坏了——停下把话说清，别静默跳过。
  if (!use) {
    if (ctx.offline || !fs.existsSync(path.join(ctx.featureRoot, 'spec', 'knowledge-use.yaml'))) return [];
    fail('spec/knowledge-use.yaml 读不出判断：附录的判定表是它的投影，先把那份 YAML 修好');
  }
  // 机器区里不写占位：作者改不了它（下一次投影会盖回来），挂着又永远不会被填。
  // 骨架在而某一条没依据，就在这里停下把话说清——判断本来就该先写进那份 YAML，
  // 它自己的门禁也要求每条有 requirement 或 reason。
  const covered = (e) => use.naDomains.has(e.prefix);
  const missing = entries.filter(e => !covered(e) && !use.rows.get(e.id)?.basis);
  if (missing.length) {
    fail(`spec/knowledge-use.yaml 里这 ${missing.length} 条还没有判断依据：`
      + `${missing.slice(0, 4).map(e => e.id).join('、')}${missing.length > 4 ? '…' : ''}`
      + '——命中写 requirement、不命中写 reason，整域不适用写进 constraint_domains，'
      + '填完再投影。附录的判定表是它的投影，投影不替你编依据');
  }
  // 整域不适用的域投一行域级结论；域内条目不再逐条出现——那正是那份 YAML 的写法，
  // `check ⑦` 也认这一行覆盖全域。
  const seenDomain = new Set();
  const rows = [];
  for (const e of entries) {
    if (covered(e)) {
      if (seenDomain.has(e.prefix)) continue;
      seenDomain.add(e.prefix);
      rows.push([e.domainTitle ?? '', e.prefix, DOMAIN_NA, use.naDomains.get(e.prefix)]);
      continue;
    }
    const row = use.rows.get(e.id);
    rows.push([e.domainTitle ?? '', e.id, row.applicable ? '命中' : '不命中', row.basis]);
  }
  return renderTable(['规约域', '编号', '判定', '依据'], rows);
}

/**
 * 本步要消费的 Spec 章节在不在 —— **起手的必需输入**，缺了回 Spec。
 *
 * skeleton 自己消费术语映射表（术语那一章的起始行）；`project` 之后要 §9 的那几节投
 * 附录 A–C。**「没有这一节」与「这件事不涉及」不是一回事**：后者是 Spec 里写出来的
 * 结论（`不涉及：<依据>`），评审者读得到；前者只是没写到那儿，而起手一路往下走的话，
 * 作者会在十章都写完之后才发现附录三节没有可投的东西。
 *
 * 判的只是**本步真要读的那几节在不在**：不重跑 spec 阶段的语义判据，不替这份需求
 * 判断它有没有接口，也不要求为了过门禁补一张空表。
 *
 * @returns {string[]} 缺口；空数组 = 可以起手
 */
export function specGaps(spec) {
  const gaps = [];
  if (!specSection(spec, /术语映射表/).trim()) {
    gaps.push('spec 里定位不到「术语映射表」这一节：术语那一章的起始行从它派生');
  }
  // **逐节核**：一节投一节的内容，三份输入不能互相替代。用「任意一节有正文」放过，
  // 只要 §9.2 在，§9.3 与 §9.4 缺了也不会有人提——而附录那一节正是从这三节投出来的。
  for (const [name, sources] of APPENDIX_FROM_SPEC) {
    const missing = sources.filter(src => !specSection(spec, src.re).trim());
    if (missing.length) {
      gaps.push(`spec 里定位不到 ${missing.map(src => src.at).join('、')}：`
        + `附录「${name}」要从它投影`);
    }
  }
  return gaps;
}

/** 激活清单的每条规约在附录的判定表里有行，或其整域一行「整域不适用」。 */
export function verdictTableProblems(ctx, sections, viewOf) {
  const problems = [];
  // ⑦ 规约判定表：激活清单的每个条目在附录的「规约判定」小节有一行，
  //    或其整域一行「整域不适用」
  //
  // 判定写在 story 里：评审者据这一节回显完备性——激活了几条、各自命中与否、依据是什么。
  //
  // 落点在**附录**而不是主叙事的某一章：规约编号是工程标识，读者对不上，
  // 写进主叙事就是在打断阅读；附录给了它一个不打断阅读、机器又核得到的位置。
  // 激活规约的编号**直接取激活清单**：经「材料单元」那一层只是把同一份数据换个形状，
  // 而多一层就多一处会与清单失同步的地方——判定表少判一条规约是静默的。
  //
  // **这张表是 `spec/knowledge-use.yaml` 的投影**（`story-build project` 投的），
  // 所以判定的值域、依据非空、与 YAML 一致三件事在投影那一步就成立了：
  // 投影只写命中/不命中，缺依据时它响亮失败。这里只剩一条——**每条规约有行**：
  // 作者手改 story.md 删掉一行，下一次投影才会补回来，这中间要有人看见。
  const kEntries = activeKnowledgeEntries(ctx);
  if (kEntries.length) {
    const appendix = appendixChapter(ctx.contract);
    const appendixSec = appendix ? sections.find(s => s.title === appendix.title) : null;
    const verdictName = (appendix?.subsections ?? []).find(n => n.includes('规约')) ?? '规约判定';
    const verdictText = appendixSec ? sectionBody(viewOf(appendixSec.title), verdictName) : null;
    if (verdictText === null) {
      problems.push(`缺${appendix ? `「${appendix.title}」章的` : ''}「${verdictName}」小节`
        + '——激活规约的逐条判定表落在那里');
    } else {
      const rows = new Map();          // 编号 → {判定, 依据}
      const domainRows = new Map();    // 中文域名 → 判定
      for (const line of verdictText.split(/\r?\n/)) {
        const s = line.trim();
        if (!s.startsWith('|')) continue;
        const c = s.replace(/^\||\|$/g, '').split('|').map(x => x.replace(/[`*]/g, '').trim());
        if (c.length < 4 || /^[-: ]*$/.test(c[0])) continue;
        const [domain, id, verdict, basis] = c;
        if (id) rows.set(id, { verdict, basis });
        if (verdict === DOMAIN_NA) domainRows.set(domain, true);
      }
      for (const e of kEntries) {
        const id = e.id;
        const domain = e.domainTitle ?? '';
        const row = rows.get(id);
        if (!row) {
          if (domainRows.has(domain)) continue;   // 整域不适用，覆盖域内全部条目
          problems.push(`规约 ${id}（${domain}）在附录·${verdictName}的判定表里没有行`
            + `——判「不命中」也要有一行；整域不适用就给该域一行「${DOMAIN_NA}」`);
          continue;
        }
      }
    }
  }
  return problems;
}

/** 附录结构：只有合同约定的那几节，节内是表和列表，每节都有内容，不放图不放围栏。 */
export function appendixStructureProblems(ctx, sections, viewOf) {
  const problems = [];
  // ⑫ 附录结构：只有合同约定的那几节，节内是表和列表，每节都有内容
  //
  // 附录是全篇唯一允许出现工程标识的地方，于是它天然最容易变成倾倒区——
  // 常见形态是多长出一个「机器核对索引」之类的小节，把原文整段搬进去，占掉全篇大半。
  // 判的是结构不是内容：约定之外的小节、原文围栏块、空节，三样都不该有。
  const appendixDef = appendixChapter(ctx.contract);
  const appendixSection = appendixDef
    ? sections.find(sec => sec.title === appendixDef.title) : null;
  const wantSubs = (appendixDef?.subsections ?? []).map(normalizeHeading);
  const materialName = materialSubsectionName(ctx.contract);
  if (appendixSection && wantSubs.length) {
    for (const sub of sectionNames(viewOf(appendixSection.title))) {
      if (!wantSubs.includes(sub.name)) {
        problems.push(`「${appendixDef.title}」多了一节「${sub.raw}」`
          + `——${appendixDef.title}只有约定的这几节：${wantSubs.join('、')}；`
          + '工程细节各有落点表，叙述归正文章');
      }
    }
    for (const want of wantSubs) {
      const body = sectionBody(viewOf(appendixSection.title), want);
      if (body === null) {
        problems.push(`「${appendixDef.title}」缺「${want}」这一节`
          + '——确实不涉及也要留标题，写「不涉及：<依据>」一行');
        continue;
      }
      const rows = body.split(/\r?\n/).map(l => l.trim())
        .filter(l => l.startsWith('|') || /^[-*+]\s/.test(l) || /^\d+[.)]\s/.test(l));
      if (!rows.length && !/不涉及[:：]\s*\S/.test(body)) {
        problems.push(`「${appendixDef.title}·${want}」是空的`
          + '——成表或成列表，确实不涉及就写「不涉及：<依据>」一行');
        continue;
      }
    }
    for (const line of appendixSection.text.split(/\r?\n/)) {
      const fence = line.trim().match(/^(?:```|~~~)\s*(\w*)/);
      if (fence && fence[1] && fence[1] !== 'mermaid') {
        problems.push(`「${appendixDef.title}」里有 ${fence[1]} 围栏块`
          + `——${appendixDef.title}是表和列表，不是原文存放处`);
        break;
      }
    }

    // 附录里不放图。反复出现的形态是：正文各章写着「下图是…」，图却整批迁进附录，
    // 读者读到那句话时手边没有图，要翻到最后再翻回来。
    //
    // 与集合一致那一条合起来看：登记的图要有去处，而附录不是去处。用它就放在讲它的那一章，
    // 不用它就在材料清单那一行写明理由——理由是文字，不是把图挪到附录充数。
    const inAppendix = [...appendixSection.text.matchAll(/!\[[^\]]*\]\(([^)\s]+)/g)]
      .map(m => m[1]);
    if (inAppendix.length) {
      problems.push(`「${appendixDef.title}」里有 ${inAppendix.length} 张图`
        + `（${inAppendix.slice(0, 3).join('、')}${inAppendix.length > 3 ? '…' : ''}）`
        + '——图片放它讲的那一章，跟着讲它的那句话走；'
        + `${appendixDef.title}是查阅件，读者不会为了看一张图翻到这里来`);
    }
  }
  return problems;
}

/** 附录 A/B/C 的行 ⊇ spec §9 对应表的行（按第一列的标识对齐）。 */
export function specRowProblems(ctx, sections, viewOf) {
  const problems = [];
  const appendixDef = appendixChapter(ctx.contract);
  const appendixSection = appendixDef
    ? sections.find(sec => sec.title === appendixDef.title) : null;
  // ⑫b 附录 A/B/C 的行 ⊇ spec §9 对应表的行（按第一列的标识对齐）。
  //
  // 成文顺序里 spec 先于 story，附录三节是它的投影而不是重写。手抄一遍必然更少：
  // 接口丢掉入参出参与错误码、几个埋点合成一行都是见过的形态，
  // 而评审者正是拿着附录回查契约的。
  // 只核标识在不在：措辞、列的增减、行的顺序都由作者定。
  const specForRows = specText(ctx);
  if (specForRows && appendixSection) {
    for (const [name] of APPENDIX_FROM_SPEC) {
      const want = appendixTables(specForRows, name).flatMap(t => t.rows.map(r => r[0]));
      if (!want.length) continue;
      const body = sectionBody(viewOf(appendixSection.title), name) ?? '';
      const have = new Set(pipeTables(body).flatMap(t => t.rows.map(r => norm(r[0]))));
      const missing = want.filter(id => !have.has(norm(id)));
      if (missing.length) {
        problems.push(`「${appendixDef?.title ?? '附录'}·${name}」少了 spec §9 里的 `
          + `${missing.length} 行：${missing.slice(0, 4).join('、')}`
          + `${missing.length > 4 ? '…' : ''}`
          + '——附录是 spec 契约的投影，评审者拿着它回查；可以改措辞、可以加列，不能少行');
      }
    }
  }
  return problems;
}
