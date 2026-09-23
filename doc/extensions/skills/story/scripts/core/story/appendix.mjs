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
  chapterSpan, findByName, headingEnd, normalizeHeading, parseDocument, sectionBody, sectionNames, tablesWithin, zoneBlock, zoneHandEdited, zoneSpan, ZONE_BEGIN, ZONE_END,
} from './document.mjs';
import { fail, activeKnowledgeEntries, specText } from './context.mjs';
import { relFromStory } from './sources.mjs';
import { readUse, UseError } from '../../../../../hooks/shared/knowledge-use/document.mjs';

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
        // 本轮豁免的命中，依据是豁免理由与补偿——评审人要对它表态。
        const action = reviewActions.get(id);
        const reason = String(row.reason ?? '').trim();
        const w = row.waived;
        const hit = w ? `本轮豁免：${[w.reason, w.compensation].filter(Boolean).join('；补偿：')}`
          : action !== undefined ? [action, reason, String(row.decision ?? '').trim() && `议题 ${String(row.decision).trim()}`]
            .filter(Boolean).join('：')
            : req.map(x => String(x ?? '').trim()).filter(Boolean).join('；');
        rows.set(id, { applicable: row.applicable === true, waived: Boolean(w), basis: row.applicable === true ? hit : reason });
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
 * spec 里某一节：命中标题（二、三级）之下、到下一个同级或更高级标题之前。
 * 切法与定位都走 `document.parseDocument`——围栏里的样例标题与表不算。
 *
 * @returns {{title: string, text: string, tables: {header: string[], rows: string[][]}[]}}
 */
function specSection(spec, re) {
  const doc = parseDocument(spec);
  const h = doc.headings.find(x => x.level >= 2 && x.level <= 3 && re.test(`${'#'.repeat(x.level)} ${x.raw}`));
  if (!h) return { title: '', text: '', tables: [] };
  const end = headingEnd(doc, h);
  return { title: h.raw.replace(/^[\d.]+\s*/, ''), text: doc.lines.slice(h.at + 1, end).join('\n'),
    tables: tablesWithin(doc, h.at + 1, end) };
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
  const table = specSection(text, /术语映射表/).tables[0];
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
//: 读者打不开也用不上，进了归档件还会撞上「不写仓内路径」这条红线，
//: 而机器区作者改不了。投影策略只有这一条，不在合同里逐表登记列白名单：
//: 那会与 spec 模板形成第二真源。
const DROP_COLUMNS = ['代码现状'];

//: 附录三节各从 spec §9 的哪几个小节生成。附录的读者要「拿着回查」，
//: 所以行必须齐——集合核（⑫）盯的就是这里。
const APPENDIX_FROM_SPEC = [
  ['接口', [{ at: '§9.1', re: /^###\s*9\.1/ }]],
  ['数据、配置与事件', [{ at: '§9.2', re: /^###\s*9\.2/ },
    { at: '§9.3', re: /^###\s*9\.3/ }, { at: '§9.4', re: /^###\s*9\.4/, whole: true }]],
  ['改动边界', [{ at: '§9.5', re: /^###\s*9\.5/ }]],
];

/** 一张 spec 表投进附录的样子：去掉不投的列与模板占位行。没有行返回 null。 */
function projectedTable(t) {
  const keep = t.header.map((h, i) => [h, i])
    .filter(([h]) => !DROP_COLUMNS.some(d => h.includes(d)));
  const rows = t.rows.filter(r => !isPlaceholderRow(r))
    .map(r => keep.map(([, i]) => r[i] ?? ''));
  return rows.length ? { header: keep.map(([h]) => h), rows } : null;
}

/** 某个附录小节该有的表：spec 对应几节就给几张，表头按原顺序带过来（去掉不投的列）。 */
function appendixTables(spec, name) {
  const from = APPENDIX_FROM_SPEC.find(x => normalizeHeading(x[0]) === normalizeHeading(name));
  if (!spec || !from) return [];
  const out = [];
  for (const { re } of from[1]) {
    for (const t of specSection(spec, re).tables) {
      const got = projectedTable(t);
      if (got) out.push(got);
    }
  }
  return out;
}

/**
 * 整节投影：正文、小标题、列表、图与表**按原次序**搬进附录，表照样去掉不投的列。
 *
 * 用在「这一节是某项设计的唯一完整说明」的来源上（埋点）：只搬表，流程怎么分、各点位为什么统计、
 * 结果有哪些就全丢了，读者在归档件里只剩一张名目表。标题挂在「附录小节」之下：
 * 这一节的标题成 H4，它里面的小标题各降一级。HTML 注释（模板说明）不搬。
 * 除了标题什么都没有时返回空：那是真的空，由调用方回落到「不涉及」或报空节。
 */
/**
 * spec 里的相对引用换成从归档件出发的写法：spec 在 `spec/`，归档件在 `AR/`。
 *
 * 行内链接、图片与引用式定义都换；外链（带协议）、根路径与内嵌数据不动；
 * 只有锚点的指回 spec 那一处——它指的标题在归档件里并不存在。
 */
function rebase(target) {
  const t = String(target);
  if (/^[a-z][\w+.-]*:/i.test(t) || t.startsWith('/')) return t;
  if (t.startsWith('#')) return `${relFromStory('spec/spec.md')}${t}`;
  const [file, frag = ''] = t.split(/(?=#)/);
  return relFromStory(path.posix.normalize(path.posix.join('spec', file))) + frag;
}

function rebaseLinks(line) {
  return line
    .replace(/(!?\[[^\]]*\]\()\s*([^)\s]+)((?:\s+"[^"]*")?\s*\))/g, (_, open, target, close) => open + rebase(target) + close)
    .replace(/^(\s*\[[^\]]+\]:\s*)(\S+)/, (_, head, target) => head + rebase(target));
}

function wholeSection(spec, re) {
  const doc = parseDocument(spec);
  const h = doc.headings.find(x => x.level >= 2 && x.level <= 3 && re.test(`${'#'.repeat(x.level)} ${x.raw}`));
  if (!h) return [];
  const end = headingEnd(doc, h);
  const tables = new Map(tablesWithin(doc, h.at + 1, end).map(t => [t.line, t]));
  // 源小节自己的号（如 9.4）下的局部编号只在 spec 里成立，搬进附录就去掉；业务标题里的数字不动
  const own = /^(\d+(?:\.\d+)*)\s/.exec(h.raw)?.[1];
  const local = own ? new RegExp(`^${own.replace(/\./g, '\\.')}(?:\\.\\d+)+\\.?\\s+`) : null;
  const body = [];
  let comment = false;
  for (let i = h.at + 1; i < end; i += 1) {
    const line = doc.lines[i];
    if (!doc.fenced.has(i)) {
      if (comment || /^\s*<!--/.test(line)) {
        comment = !/-->\s*$/.test(line);
        continue;
      }
      const t = tables.get(i);
      if (t) {
        const got = projectedTable(t);
        if (got) body.push(...renderTable(got.header, got.rows.map(r => r.map(rebaseLinks))));
        i = t.line + 1 + t.rows.length;          // 表头、分隔行、各行
        continue;
      }
      const sub = /^(#{1,6})\s+(.+?)\s*$/.exec(line.trim());
      if (sub) {
        body.push(`${'#'.repeat(Math.min(6, sub[1].length + 1))} ${local ? sub[2].replace(local, '') : sub[2]}`);
        continue;
      }
      body.push(rebaseLinks(line));
      continue;
    }
    body.push(line);
  }
  const text = body.join('\n').replace(/\n{3,}/g, '\n\n').trim();
  return text ? [`#### ${h.raw.replace(/^[\d.]+\s*/, '')}`, '', ...text.split(/\r?\n/)] : [];
}

/** 附录里承载材料清单的那一节的名字（合同数据，本文件不写业务词）。 */
export function materialSubsectionName(contract) {
  const appendix = appendixChapter(contract);
  return (appendix?.subsections ?? []).find(n => n.includes('材料')) ?? null;
}

//: 规约判定那一节的真源名字——报错与投影标记共用一处字面。
const KNOWLEDGE_USE_SOURCE = 'spec/knowledge-use.yaml';

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
    return ['spec 的 Scope 声明与 §9.5 依赖变更', out];
  }
  if (want.includes(normalizeHeading('规约判定'))) {
    return [KNOWLEDGE_USE_SOURCE, verdictSkeleton(ctx)];
  }
  const from = APPENDIX_FROM_SPEC.find(x => normalizeHeading(x[0]) === normalizeHeading(name));
  const groups = [];
  for (const src of from?.[1] ?? []) {
    if (src.whole) {
      const lines = wholeSection(spec, src.re);
      if (lines.length) groups.push(lines);
      continue;
    }
    const section = specSection(spec, src.re);
    const tables = section.tables.map(projectedTable).filter(Boolean);
    for (const got of tables) groups.push(renderTable(got.header, got.rows));
    // 这一节没有表，它写的「不涉及：<依据>」就是它的结论，照样进附录——
    // 丢了它，读者看不出这一项是查过、不涉及，还是没写
    const na = tables.length ? null : section.text.split(/\r?\n/).map(l => l.trim())
      .find(l => /^不涉及[:：]\s*\S/.test(l));
    if (na) groups.push([`${section.title}——${na}`]);
  }
  // 多张表、多段之间空一行：连着写 markdown 会把它们并成一张错表
  const rows = groups.flatMap((g, i) => (i ? ['', ...g] : g));
  if (!rows.length) {
    const na = specNotApplicable(spec, name);
    return ['spec §9 技术契约', na ? [na] : []];
  }
  return ['spec §9 技术契约', rows];
}

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
    const hit = specSection(spec, re).text.split(/\r?\n/)
      .map(l => l.trim()).find(l => /^不涉及[:：]\s*\S/.test(l));
    if (hit) return hit;
  }
  return null;
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
export function projectAppendix(ctx, storyText) {
  const appendix = appendixChapter(ctx.contract);
  if (!appendix) return { text: storyText, zones: 0 };
  const span = chapterSpan(storyText, appendix.title);
  if (!span) return { text: storyText, zones: 0 };
  const spec = specText(ctx);
  // **输入不成立就一个字节都不写**：投影会按「这一节现在没内容」把旧机器区删掉，
  // 而真源缺的是一整节——删完盘上看起来合法，读者与评审者都看不出少了什么。
  // 与只读侧同一份结论（`appendixSourceProblems`），不各判一次。
  const badSource = appendixSourceProblems(ctx, spec);
  if (badSource.length) {
    fail(`附录的机器区投不出来，${path.basename(ctx.storyPath)} 未改动：\n`
      + badSource.map((b, k) => `  ${k + 1}. ${b}`).join('\n'));
  }
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
    // 作者那一节还没有机器区：插到该节末尾。节都没有（或名字有歧义）就跳过，由 check ⑫ 报。
    const doc = parseDocument(lines.join('\n'));
    const { hit } = findByName(doc.headings.filter(h => h.level === 3), name);
    if (!hit) { zones -= 1; continue; }
    const end = headingEnd(doc, hit);
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
  // 那一节保持原样，缺表由 check ⑫b 报。这一步不代替它下结论。
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
  // `check ⑫b` 比对的是同一份投影，也认这一行覆盖全域。
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
    rows.push([e.domainTitle ?? '', e.id, row.applicable ? (row.waived ? '命中·本轮豁免' : '命中') : '不命中', row.basis]);
  }
  return renderTable(['规约域', '编号', '判定', '依据'], rows);
}

/**
/**
 * 投影输入还成不成立 —— **写入侧与只读侧同一份结论**。
 *
 * 从前只问「spec 读不到吗」：文件在、而必需那一节被删掉或清空时，投影出来是空数组，
 * 只读侧于是按「没有期望也没有机器区」放行——文档有字不等于技术契约已明确不涉及。
 * 这与「缺节不是不涉及」是同一条：**「不涉及」要写出来**，写出来才是结论。
 *
 * 起手预检（`skeleton`）用的就是 `specGaps` 那一份逐节要求，这里复用它，不另立清单。
 *
 * @returns {string[]} 空表示输入成立；非空时投影不该被当成「期望为空」
 */
function appendixSourceProblems(ctx, spec) {
  if (ctx.offline) return [];              // 仲裁锚没有需求目录，这一层不判
  const appendix = appendixChapter(ctx.contract);
  const wanted = new Set((appendix?.subsections ?? []).map(normalizeHeading));
  const fromSpec = APPENDIX_FROM_SPEC.some(([n]) => wanted.has(normalizeHeading(n)));
  if (!fromSpec) return [];
  if (spec === null) {
    return ['读不到 spec/spec.md，附录 A–C 的机器区无从投影也无从核对'
      + '——它们是 spec §9 的投影，先让 spec 可读'];
  }
  // 「不涉及：<依据>」是**写出来的结论**，`specSection` 读得到正文，不算缺节。
  return appendixSpecGaps(spec).map(g => `${g}；`
    + '这件事确实不涉及，就在那一节里写「不涉及：<依据>」一行，写出来的结论评审者读得到');
}

/**
 * 附录 A–C 各自要的 spec 小节在不在 —— 起手预检与只读核对共用这一份。
 *
 * **逐节核**：一节投一节的内容，三份输入不能互相替代。用「任意一节有正文」放过，
 * 只要 §9.2 在，§9.3 与 §9.4 缺了也不会有人提——而附录那一节正是从这三节投出来的。
 */
function appendixSpecGaps(spec) {
  const gaps = [];
  for (const [name, sources] of APPENDIX_FROM_SPEC) {
    const missing = sources.filter(src => !specSection(spec, src.re).text.trim());
    if (missing.length) {
      gaps.push(`spec 里定位不到 ${missing.map(src => src.at).join('、')}：`
        + `附录「${name}」要从它投影`);
    }
  }
  return gaps;
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
  if (!specSection(spec, /术语映射表/).text.trim()) {
    gaps.push('spec 里定位不到「术语映射表」这一节：术语那一章的起始行从它派生');
  }
  // 附录那几节的要求与只读核对共用一份（`appendixSpecGaps`）：起手放过而交付前才报，
  // 或者反过来，作者都只能在两条路之间猜。
  return gaps.concat(appendixSpecGaps(spec));
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
    const dump = viewOf(appendixSection.title).fences.find(f => f.lang && f.lang !== 'mermaid');
    if (dump) {
      problems.push(`「${appendixDef.title}」里有 ${dump.lang} 围栏块`
        + `——${appendixDef.title}是表和列表，不是原文存放处`);
    }

    // 附录里不放图。图若整批迁进附录，正文各章写着「下图是…」，
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

/**
 * 附录的机器区与真源对不对得上 —— **与 `project` 写进去的是同一份计算**。
 *
 * 不把投影出来的表**反着解析回去**再比集合：那样只按第一列的标识比，重复行、行序与
 * 非首列的改动都看不见，而投影本身就在手边。
 *
 * 对每一节，按 `appendixProjection` 算出**期望行**，与盘上那一段机器区
 * **逐行逐格**比。作者解释区在机器标记之外，不参加比较、也不被生成器重写。
 * 只归一 CRLF/LF 与行尾空白（编辑器保存时顺手删掉一个行尾空格不是改动），
 * 不丢重复行、不只比首列、不忽略行序。
 *
 * 报错要指到**区与它的责任真源**：作者能改的是真源，不是机器区。
 *
 * 这一步只读：算的是纯函数 `appendixProjection`，不调会写盘的 `cmdProject`。
 */
export function appendixZoneProblems(ctx, storyText) {
  const problems = [];
  // 离线仲裁锚只有一份文档：spec 与激活清单都不在手里，**没有真源可比**。
  // 拿一份空真源去比，结论是「盘上多了一整段机器区」——而判据拦住理想产物时，
  // 错的是判据。形态那几条（⑫）照跑，这一条留给线上。
  if (ctx.offline) return problems;
  const appendix = appendixChapter(ctx.contract);
  if (!appendix) return problems;
  const span = chapterSpan(storyText, appendix.title);
  if (!span) return problems;              // 附录章缺失由 ① 报，这里不重复
  const lines = storyText.slice(span.start, span.end).split(/\r?\n/);
  const spec = specText(ctx);
  // **投影输入不成立时不往下比**：那时「期望是空的」与「真源缺了一节」同形，
  // 按空期望放行会让缺一整节的附录静默通过。写入侧拒绝的也是这同一份结论。
  const badSource = appendixSourceProblems(ctx, spec);
  if (badSource.length) {
    problems.push(...badSource);
    return problems;
  }
  const onDisk = zonesOnDisk(lines, problems, appendix.title);
  const materialName = normalizeHeading(materialSubsectionName(ctx.contract) ?? '');
  const checked = new Set();
  for (const name of appendix.subsections ?? []) {
    checked.add(name);
    if (normalizeHeading(name) === materialName) continue;   // 材料清单归作者
    const [source, want] = appendixProjection(ctx, spec, name);
    const at = onDisk.get(name);
    // **真源读不出来不等于「期望是空的」**——与上面 spec 那一条同一个道理。
    // 规约判定的真源是 `spec/knowledge-use.yaml`：激活清单里有条目而投影是空的，
    // 说明那份判断件不在或读不出，而它恰恰是「哪几条规约要逐条判」的唯一依据。
    // 当成空期望的话，一份一条规约都没判的附录会静默通过。
    if (!want.length && source === KNOWLEDGE_USE_SOURCE) {
      const active = activeKnowledgeEntries(ctx);
      if (active.length) {
        problems.push(`读不出 ${source}，「${appendix.title}·${name}」无从核对`
          + `——这一轮激活了 ${active.length} 条规约，判定表是它的投影；`
          + '先跑 `knowledge-use.mjs init` 把判断件补上，再跑 `story-build project`');
        continue;
      }
    }
    if (!want.length) {
      // 真源那一节现在什么都没有：机器区也该不在。留着就是上一版冒充现状。
      if (at) {
        problems.push(`「${appendix.title}·${name}」还留着机器区，而${source}那一节已经没有内容`
          + '——跑 `story-build project` 让它跟着真源去掉');
      }
      continue;
    }
    if (!at) {
      problems.push(`「${appendix.title}·${name}」缺机器区（由${source}投影）`
        + '——那几行不该由你写，跑 `story-build project` 投出来；'
        + '它旁边的目的句与解释归你，投影不碰');
      continue;
    }
    const have = lines.slice(at.start + 1, at.end - 1);
    const diff = firstDiff(have, want);
    if (!diff) continue;
    problems.push(`「${appendix.title}·${name}」的机器区与${source}对不上（${diff.why}`
      + `${diff.at === null ? '' : `，第 ${diff.at + 1} 行`}）：`
      + `${diff.have === null ? '' : `盘上是「${cut(diff.have)}」，`}`
      + `${diff.want === null ? '' : `${source}投出来是「${cut(diff.want)}」`}`
      + '——要改结论就改真源再跑 `story-build project`；机器区里手改的东西下一次投影会被打回');
  }
  // **集合两向都核**：上面走的是合同要的那几节；盘上多出来的名字在这里报。
  // 合同里没有它，就没有真源与它比——既不受投影约束，也不是作者说明，
  // 它会长期冒充现行投影。材料清单归作者，那一节本来就不该有机器区。
  for (const name of onDisk.keys()) {
    if (checked.has(name)) continue;
    problems.push(`「${appendix.title}」里有一段机器区「${name}」，而${appendix.title}的`
      + `约定小节里没有它（${(appendix.subsections ?? []).join('、')}）`
      + '——它没有真源可比，只会一直冒充现行投影；'
      + '要留这段内容就把它移到作者区（机器标记之外），否则连首尾标记一起删掉');
  }
  return problems;
}

/** 截一段给人看，长的截断——报错要读得完。 */
const cut = (s) => (String(s).length > 60 ? `${String(s).slice(0, 60)}…` : String(s));

/**
 * 盘上有哪几段机器区 —— **一遍扫完，标记的归属只有一种解释**。
 *
 * 每个结束标记只属于**当前那个**起始标记：两个起始标记都去找后面同一个结束行的话，
 * 同一段内容会被算给两个区，而其中一个区的边界是编出来的。
 *
 * 四种坏形态都要报，它们都不是「普通作者文字」：
 *
 * - **缺结束标记**：那两行是投影的定位点，缺一行整段就认不出来，下一次 `project`
 *   会在它后面再写一段；
 * - **孤立的结束标记**：前面没有起始，它指不到任何一段；
 * - **嵌套**：起始还没关上又来一个起始——里层那段永远不会被当成一个区；
 * - **重名**：投影只认第一段，第二段会一直挂着冒充现状。
 *
 * @returns {Map<string, {start:number, end:number}>} 认得出来的区；坏的进 problems
 */
function zonesOnDisk(lines, problems, chapterTitle) {
  const out = new Map();
  let open = null;                       // {name, start}
  lines.forEach((line, i) => {
    if (line.startsWith(ZONE_BEGIN)) {
      const name = line.slice(ZONE_BEGIN.length).split(' · ')[0].trim();
      if (open) {
        problems.push(`「${chapterTitle}」第 ${i + 1} 行又开了一个机器区（${name}），`
          + `而第 ${open.start + 1} 行那个（${open.name}）还没关上`
          + '——里层这一段永远不会被当成一个区；把它们（含首尾标记）删掉再跑 `story-build project`');
        return;
      }
      open = { name, start: i };
      return;
    }
    if (line.trim() !== ZONE_END) return;
    if (!open) {
      problems.push(`「${chapterTitle}」第 ${i + 1} 行是个孤立的结束标记，前面没有起始标记`
        + '——它指不到任何一段投影；删掉它再跑 `story-build project`');
      return;
    }
    if (out.has(open.name)) {
      problems.push(`「${chapterTitle}·${open.name}」在盘上有两段机器区`
        + '——投影只认第一段，第二段会一直挂在那里冒充现状；删掉多的那一段再跑 project');
    } else {
      out.set(open.name, { start: open.start, end: i + 1 });
    }
    open = null;
  });
  if (open) {
    problems.push(`「${chapterTitle}·${open.name}」的机器区只有起始标记，没有结束标记`
      + '——那两行是投影的定位点，缺一行整段就认不出来了；'
      + '把这一段（含首尾标记）删掉再跑 `story-build project`');
  }
  return out;
}

/**
 * 第一处对不上在哪 —— 逐行逐格，**行序算在内、重复行算在内**。
 *
 * 只归一行尾空白：编辑器保存时顺手删掉一个行尾空格不是改动。别的一概算改动，
 * 包括非首列改了一个字、两行换了顺序、少一行、多一行。
 */
function firstDiff(have, want) {
  const norm2 = (l) => String(l ?? '').replace(/\s+$/, '');
  const a = have.map(norm2);
  const b = want.map(norm2);
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    if (i >= a.length) return { why: '少了行', at: i, have: null, want: b[i] };
    if (i >= b.length) return { why: '多了行', at: i, have: a[i], want: null };
    if (a[i] !== b[i]) return { why: '这一行不一样', at: i, have: a[i], want: b[i] };
  }
  return null;
}
