/**
 * 附录 —— spec 技术契约、规约与埋点的投影、手改保护，以及附录自己的结构判据。
 *
 * 附录是全篇唯一允许出现工程标识的地方，于是它天然最容易变成倾倒区。这里管两件事：
 * 机器区**从真源重算**（不读旧 story，读旧的就成了真源加一份会漂的副本），
 * 以及作者区与机器区的分界——有人在机器区写过字就停下，不静默盖掉。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { renderTable } from './chapter-contract.mjs';
import {
  chapterSpan, childHeading, findByName, headingEnd, normalizeHeading, parseDocument, sectionBody, sectionNames, tablesWithin, zoneBlock,
  zoneHandEdited, zoneLine, zoneSpan, ZONE_BEGIN, ZONE_END,
} from './document.mjs';
import { fail, activeKnowledgeEntries, specText } from './context.mjs';
import { relFromStory } from './sources.mjs';
import { readUse, UseError } from '../../../../../hooks/shared/knowledge-use/document.mjs';

/** 附录·规约那张表的判定取值封闭；整域不适用时该域内条目不必逐条列。 */
const DOMAIN_NA = '整域不适用';

/**
 * spec 侧那份判断里，每条规约命中与否 —— `{ 编号 → 是否命中 }`。
 *
 * 读不到那份 YAML 时返回 null：走 `/story` 之外的路径、或者 spec 还没写到那一步，
 * 都是正常形态，此时这一条不判（**不是判过了**）。
 */
function knowledgeUseVerdicts(ctx, entries = []) {
  const reviewActions = new Map(entries.filter(e => e.reviewAction)
    .map(e => [e.id, e.handling ?? '']));
  try {
    const use = readUse(ctx.projectRoot, ctx.args.feature);
    const rows = new Map();
    for (const row of use.constraints) {
      const id = String(row?.id ?? '').trim();
      // 依据也一起带回来：判断已经写在那份 YAML 里（命中写 requirement、
      // 不命中写 reason），让作者对着它再抄一遍，抄出来的只会更短。
      // requirement 是列表（一条要求一句）：**全部带上，一条一项**——判定表一条要求一行，
      // 只取第一条的话附录就成了 spec「规约」的截断视图，拼进一格又成了读不完的长格。
      if (id) {
        const req = Array.isArray(row.requirement) ? row.requirement : [row.requirement];
        // 评审动作条目命中时没有 requirement——它的结果是一次跨团队的动作。
        // 依据取 reason，前面带上处置原文：评审者看这一行要知道命中之后做了什么。
        // 本轮豁免的命中，依据是豁免理由与补偿——评审人要对它表态。
        const action = reviewActions.get(id);
        const reason = String(row.reason ?? '').trim();
        const w = row.waived;
        const hit = w ? [`本轮豁免：${[w.reason, w.compensation].filter(Boolean).join('；补偿：')}`]
          : action !== undefined ? [[action, reason, String(row.decision ?? '').trim() && `议题 ${String(row.decision).trim()}`]
            .filter(Boolean).join('：')]
            : req.map(x => String(x ?? '').trim()).filter(Boolean);
        const basis = row.applicable === true ? hit : [reason].filter(Boolean);
        rows.set(id, { applicable: row.applicable === true, waived: Boolean(w), basis });
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
  return sectionOf(doc, doc.headings.find(x => x.level >= 2 && re.test(`${'#'.repeat(x.level)} ${x.raw}`)));
}

function sectionOf(doc, h) {
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
function scopeList(text, key) {
  const block = String(text ?? '').match(new RegExp(key + String.raw`:\s*\n((?:\s*-\s*.+\n)+)`));
  return (block?.[1] ?? '').split(/\r?\n/)
    .map(l => l.match(/^\s*-\s*(.+?)\s*$/)?.[1]).filter(Boolean);
}

/**
 * 附录的投影登记（合同 `projection`）：哪几节有机器区、各从哪来、丢哪几列。
 *
 * 节名、来源小节号与列映射都是合同数据：本文件不写任何一节的名字或来源，
 * 改附录的组织只改合同。
 */
function projectionOf(contract) {
  const p = appendixChapter(contract)?.projection ?? {};
  return { drop: p.drop_columns ?? [], sections: p.sections ?? {} };
}

const escapeRe = (x) => String(x).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/**
 * spec 里按节名一路往下的那一节（合同 `from`，如 `["宿主扩展治理项", "技术契约", "端云接口"]`）：
 * 第一个名字是二级标题，之后逐级找下一级小节；标题按名字开头认，号不参与——spec 的节号变了合同不用动。
 */
function specHeadingAt(doc, names) {
  let h = null;
  for (const name of names ?? []) {
    const re = new RegExp(`^${escapeRe(normalizeHeading(name))}`);
    h = h ? childHeading(doc, h, re) : doc.headings.find(x => x.level === 2 && re.test(x.name));
    if (!h) return null;
  }
  return h;
}

function specSectionAt(spec, names) {
  const doc = parseDocument(spec);
  return sectionOf(doc, specHeadingAt(doc, names));
}

/** 合同里来源小节的名字，报错与机器区标记里给人看。 */
const sourceName = (names) => `「${(names ?? []).join(' › ')}」`;

/**
 * 一张 spec 表投进附录的样子：去掉不投的列与模板占位行，列名按合同换成读者用的名字。
 * 只丢列、改列名，不造新列。没有行返回 null。
 */
function projectedTable(t, drop, rename = {}) {
  const keep = t.header.map((h, i) => [h, i])
    .filter(([h]) => !drop.some(d => h.includes(d)));
  const rows = t.rows.filter(r => !isPlaceholderRow(r))
    .map(r => keep.map(([, i]) => r[i] ?? ''));
  return rows.length ? { header: keep.map(([h]) => rename[h] ?? h), rows } : null;
}

/** 一节正文里写出来的「不涉及」结论（以「不涉及」起头的一行）——它也是结论，评审者要看到；没有返回 null。 */
function notApplicableLine(text) {
  return String(text ?? '').split(/\r?\n/).map(l => l.trim())
    .find(l => /^不涉及\S/.test(l)) ?? null;
}

/**
 * 附录·改动边界 —— 这次需求在工程上动到哪些模块、哪些相关模块保证不动：**一个模块一行**，
 * 值只有「改动」「不改」。来源是 spec 的 Scope 声明：`in_scope_modules` 改动，`out_of_scope_modules` 不改
 * （复用其已有出口也是不改）。新引入的依赖在技术契约·依赖变更一节。
 * Scope 的切分理由留在 spec：它是写给 plan 与工程的说明；归档件讲为什么这么切，
 * 归「范围」「业务方案」两章，用业务语言。
 */
function scopeBoundary(ctx, spec, section) {
  const rows = [
    ...scopeList(spec, 'in_scope_modules').map(m => [m, '改动']),
    ...scopeList(spec, 'out_of_scope_modules').map(m => [m, '不改']),
  ];
  return rows.length ? renderTable(appendixTableHeader(ctx, section), rows) : [];
}

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

/**
 * 整节投影：正文、小标题、列表与表**按原次序**搬进附录，表按合同丢列、改列名。
 *
 * 用在「这一节是某项设计的唯一完整说明」的来源上（埋点）：只搬表，指标怎么定、
 * 各点为什么统计、结果有哪些就全丢了。这一节自己的标题归附录的 H4（作者区），
 * 里面的小标题按相对源节的深度排在它之下，去掉源小节号下的局部编号。HTML 注释（模板说明）不搬。
 * 除了标题什么都没有时返回空：那是真的空，由调用方报空节。
 */
function wholeSection(spec, names, drop, rename, level) {
  const doc = parseDocument(spec);
  const h = specHeadingAt(doc, names);
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
        const got = projectedTable(t, drop, rename);
        if (got) body.push(...renderTable(got.header, got.rows.map(r => r.map(rebaseLinks))));
        i = t.line + 1 + t.rows.length;          // 表头、分隔行、各行
        continue;
      }
      const sub = /^(#{1,6})\s+(.+?)\s*$/.exec(line.trim());
      if (sub) {
        body.push(`${'#'.repeat(Math.min(6, level + sub[1].length - h.level))} ${local ? sub[2].replace(local, '') : sub[2]}`);
        continue;
      }
      body.push(rebaseLinks(line));
      continue;
    }
    body.push(line);
  }
  const text = body.join('\n').replace(/\n{3,}/g, '\n\n').trim();
  return text ? text.split(/\r?\n/) : [];
}

/** 附录里承载材料清单的那一节的名字（合同数据，本文件不写业务词）。 */
export function materialSubsectionName(contract) {
  const appendix = appendixChapter(contract);
  return (appendix?.subsections ?? []).find(n => n.includes('材料')) ?? null;
}

//: 附录·规约那一节的真源名字——报错与投影标记共用一处字面。
const KNOWLEDGE_USE_SOURCE = 'spec/knowledge-use.yaml';

/** 附录里由脚本合成的那张表的表头 —— 登记在合同，脚本不留字面。 */
function appendixTableHeader(ctx, name) {
  const want = normalizeHeading(name);
  const table = Object.entries(appendixChapter(ctx.contract)?.subsection_tables ?? {})
    .find(([k]) => normalizeHeading(k) === want)?.[1];
  if (!table) fail(`章节合同附录章的 subsection_tables：没登记「${name}」这一节的表头——脚本合成的附录表按合同登记的表头出，脚本不留字面`);
  return String(table).split('|').map(h => h.trim());
}

/**
 * spec 某一小节投进附录的行：整节、若干张表，或者它写出来的「不涉及」。
 * `level` 是附录里承载它的标题层级（H3 的节或 H4 的小节）：整节投影的小标题按相对源节的深度排在它之下。
 */
function specRows(spec, def, drop, level) {
  if (def.whole) return wholeSection(spec, def.from, drop, def.rename, level);
  const section = specSectionAt(spec, def.from);
  const tables = section.tables.map(t => projectedTable(t, drop, def.rename)).filter(Boolean);
  // 多张表之间空一行：连着写 markdown 会把它们并成一张错表
  if (tables.length) return tables.flatMap((t, i) => [...(i ? [''] : []), ...renderTable(t.header, t.rows)]);
  const na = notApplicableLine(section.text);
  return na ? [na] : [];
}

/**
 * 附录的全部机器区 —— **投影与只读核对的唯一一份计算**。
 *
 * 每一项：`zone`（机器区名）、`section`（所在的 H3）、`h4`（所在的 H4，没有就挂在 H3 末尾）、
 * `source`（真源）、`rows`（投出来的行）。**不含任何占位**：机器区里出现「作者要填的格子」，
 * 作者填了会被下一次投影打回。材料清单不在这里——那一节的「贡献了什么」只有作者知道。
 */
function appendixZones(ctx, spec) {
  const { drop, sections } = projectionOf(ctx.contract);
  const out = [];
  for (const [section, def] of Object.entries(sections)) {
    if (def.kind === 'scope') {
      out.push({ zone: section, section, source: 'spec 的 Scope 声明', rows: scopeBoundary(ctx, spec, section) });
    } else if (def.kind === 'knowledge_use') {
      out.push({ zone: section, section, source: KNOWLEDGE_USE_SOURCE, rows: verdictSkeleton(ctx, section) });
    } else if (def.from) {
      out.push({ zone: section, section, source: `spec ${sourceName(def.from)}`, rows: specRows(spec, def, drop, 3) });
    } else {
      for (const h4 of def.h4 ?? []) {
        out.push({ zone: `${section}·${h4.title}`, section, h4: h4.title, source: `spec ${sourceName(h4.from)}`,
          rows: specRows(spec, h4, drop, 4) });
      }
    }
  }
  return out;
}

/**
 * 把附录的机器区投影进 story —— **投影的唯一入口**，两个时点都走它。
 *
 * ① `chapter` 落盘附录章之后：作者的草稿里只有目的句、H4 标题与材料清单，机器区由这里投出来，
 *    他登记前跑 `check` 才不会因为机器区是空的而红；
 * ② `story_flow.py story` 登记时：真源在成文期间还会变（补一条规约判断、改一个接口），
 *    以登记这一次为准。
 *
 * 每次都从当前真源重算，不读旧 story：读旧的就成了「真源 + 一份会漂移的副本」。
 * 机器区紧跟在它的 H4 标题下（没有 H4 的挂在该节末尾）；H4 标题与区后的说明归作者，这里不碰。
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
  const zones = appendixZones(ctx, spec);
  let lines = storyText.slice(span.start, span.end).split(/\r?\n/);
  let count = 0;
  // 集合对账：合同里有的按真源重投，合同里没有的区块删掉——某一节从合同去掉或改名之后，
  // 旧区会一直挂着，而它指的真源已经没人维护了。
  const want = new Set(zones.map(z => z.zone));
  for (const line of [...lines]) {
    if (!line.startsWith(ZONE_BEGIN)) continue;
    const name = line.slice(ZONE_BEGIN.length).split(' · ')[0].trim();
    const at = want.has(name) ? null : zoneSpan(lines, name);
    if (at) lines = [...lines.slice(0, at.start), ...lines.slice(at.end)];
  }
  for (const z of zones) {
    const at0 = zoneSpan(lines, z.zone);
    // 真源那一节现在什么都没有了（规约全退出激活清单、spec 那一节被删或改空）：
    // 旧区要删，不能留着上一版冒充现状。删完那一节由 `check ⑫` 报空节——
    // 那是正确的告警，它指向真源，不指向作者。
    if (!z.rows.length) {
      if (at0) lines = [...lines.slice(0, at0.start), ...lines.slice(at0.end)];
      continue;
    }
    const block = zoneBlock(z.zone, z.source, z.rows);
    if (at0 && zoneHandEdited(lines, at0)) {
      // 停在这里，不盖。他写的那几行是他花时间想出来的；静默盖掉的话，
      // 东西没了而他不知道，下一次还会再写一遍。
      fail(`附录「${z.zone}」的机器区：盘上内容与起始标记记下的摘要对不上，有人手改过——`
        + `机器区由 \`story-build project\` 从 ${z.source} 投影，发现手改就停下不盖；`
        + '内容以真源为准，这一段连同首尾两行标记不在时投影重新写出');
    }
    count += 1;
    if (at0) { lines = [...lines.slice(0, at0.start), ...block, ...lines.slice(at0.end)]; continue; }
    // 还没有机器区：放到它的 H4 标题下；H4 还没有就连标题一起补在该节末尾。
    // 节都没有（或名字有歧义）就跳过，由 check ⑫ 报。
    const doc = parseDocument(lines.join('\n'));
    const { hit } = findByName(doc.headings.filter(h => h.level === 3), z.section);
    if (!hit) { count -= 1; continue; }
    const end = headingEnd(doc, hit);
    const h4 = z.h4 ? findByName(doc.headings.filter(h => h.level === 4 && h.at > hit.at && h.at < end), z.h4).hit : null;
    if (h4) lines = [...lines.slice(0, h4.at + 1), '', ...block, ...lines.slice(h4.at + 1)];
    else lines = [...lines.slice(0, end), ...(z.h4 ? [`#### ${z.h4}`, ''] : []), ...block, '', ...lines.slice(end)];
  }
  return { text: storyText.slice(0, span.start) + lines.join('\n') + storyText.slice(span.end),
    zones: count };
}

/**
 * 附录·规约的整张表 —— **依据也取真源，一条要求一行**。
 *
 * 判断已经写在 `spec/knowledge-use.yaml` 里：不命中写的是为什么不适用，
 * 命中写的是这一轮要满足的要求。编号每行都写，读者从任一行都认得出是哪条规约；
 * 规约域与判定只写在该条的第一行。
 */
function verdictSkeleton(ctx, section) {
  const entries = activeKnowledgeEntries(ctx);
  if (!entries.length) return [];
  const use = knowledgeUseVerdicts(ctx, entries);
  // 判断骨架还没生成（knowledge-use.yaml 不在）：投不出来就不投，
  // 那一节保持原样，缺表由 check ⑫b 报。这一步不代替它下结论。
  // 文件在却读不出判断，那是它写坏了——停下把话说清，别静默跳过。
  if (!use) {
    if (!fs.existsSync(path.join(ctx.featureRoot, 'spec', 'knowledge-use.yaml'))) return [];
    fail(`spec/knowledge-use.yaml：文件在而读不出判断——附录「${section}」的判定表由它投影，读不出就投不出`);
  }
  // 机器区里不写占位：作者改不了它（下一次投影会盖回来），挂着又永远不会被填。
  // 骨架在而某一条没依据，就在这里停下把话说清——判断本来就该先写进那份 YAML，
  // 它自己的门禁也要求每条有 requirement 或 reason。
  const covered = (e) => use.naDomains.has(e.prefix);
  const missing = entries.filter(e => !covered(e) && !use.rows.get(e.id)?.basis.length);
  if (missing.length) {
    fail(`spec/knowledge-use.yaml：${missing.length} 条激活规约没有判断依据（`
      + `${missing.slice(0, 4).map(e => e.id).join('、')}${missing.length > 4 ? '…' : ''}）`
      + '——依据的写法是命中写 requirement、不命中写 reason，整域不适用登记在 constraint_domains；'
      + `附录「${section}」的表逐条搬这里的依据，没有依据的条目投不出来`);
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
    const verdict = row.applicable ? (row.waived ? '命中·本轮豁免' : '命中') : '不命中';
    row.basis.forEach((b, k) => rows.push(k ? ['', e.id, '', b] : [e.domainTitle ?? '', e.id, verdict, b]));
  }
  return renderTable(appendixTableHeader(ctx, section), rows);
}

/**
 * 投影输入还成不成立 —— **写入侧与只读侧同一份结论**。
 *
 * 文件在、而必需那一节被删掉或清空时，投影出来是空数组，只读侧会按「没有期望也没有机器区」
 * 放行——文档有字不等于技术契约已明确不涉及。**「不涉及」要写出来**，写出来才是结论。
 *
 * 起手预检（`skeleton`）用的就是 `specGaps` 那一份逐节要求，这里复用它，不另立清单。
 *
 * @returns {string[]} 空表示输入成立；非空时投影不该被当成「期望为空」
 */
function appendixSourceProblems(ctx, spec) {
  if (!appendixSpecSources(ctx.contract).length) return [];
  if (spec === null) {
    return ['读不到 spec/spec.md'
      + '——附录的机器区由 spec 扩展章各节投影，spec 读不到时无从投影也无从核对'];
  }
  // 「不涉及：<依据>」是**写出来的结论**，`specSection` 读得到正文，不算缺节。
  return appendixSpecGaps(ctx.contract, spec).map(g => `${g}；`
    + '不涉及的节写「不涉及：<依据>」一行也算有内容，投影把这一行搬进附录，评审者读得到');
}

/** 附录要从 spec 投影的小节：`[{from, to}]`，`to` 是附录里的落点名。 */
function appendixSpecSources(contract) {
  const out = [];
  for (const [section, def] of Object.entries(projectionOf(contract).sections)) {
    if (def.from && def.kind !== 'scope') out.push({ from: def.from, to: section });
    for (const h4 of def.h4 ?? []) out.push({ from: h4.from, to: `${section}·${h4.title}` });
  }
  return out;
}

/**
 * 附录各机器区要的 spec 小节在不在 —— 起手预检与只读核对共用这一份。
 *
 * **逐节核**：一节投一节的内容，几份输入不能互相替代。用「任意一节有正文」放过，
 * 只要数据存储在，配置项与埋点缺了也不会有人提——而附录的那几段正是从它们投出来的。
 */
function appendixSpecGaps(contract, spec) {
  return appendixSpecSources(contract)
    .filter(src => !specSectionAt(spec, src.from).text.trim())
    .map(src => `spec/spec.md${sourceName(src.from)}：定位不到这一节或它没有正文——附录「${src.to}」由它投影，`
      + '按节名从「宿主扩展治理项」逐级往下一级小节找');
}

/**
 * 本步要消费的 Spec 章节在不在 —— **起手的必需输入**，缺了回 Spec。
 *
 * skeleton 自己消费术语映射表（术语那一章的起始行）；`project` 之后要 spec 扩展章的那几节投
 * 附录。**「没有这一节」与「这件事不涉及」不是一回事**：后者是 Spec 里写出来的
 * 结论（`不涉及：<依据>`），评审者读得到；前者只是没写到那儿，而起手一路往下走的话，
 * 作者会在十章都写完之后才发现附录没有可投的东西。
 *
 * 判的只是**本步真要读的那几节在不在**：不重跑 spec 阶段的语义判据，不替这份需求
 * 判断它有没有接口，也不要求为了过门禁补一张空表。
 *
 * @returns {string[]} 缺口；空数组 = 可以起手
 */
export function specGaps(contract, spec) {
  const gaps = [];
  if (!specSection(spec, /术语映射表/).text.trim()) {
    gaps.push('spec/spec.md「术语映射表」：定位不到这一节或它没有正文——术语那一章的起始行由它派生');
  }
  // 附录那几节的要求与只读核对共用一份（`appendixSpecGaps`）：起手放过而交付前才报，
  // 或者反过来，作者都只能在两条路之间猜。
  return gaps.concat(appendixSpecGaps(contract, spec));
}

/**
 * 附录结构：只有合同约定的那几节，节内有内容，不放图不放围栏。
 *
 * 判的是结构不是内容：机器区之外的说明写得好不好归语义审查。
 */
export function appendixStructureProblems(ctx, sections, viewOf) {
  const problems = [];
  const appendixDef = appendixChapter(ctx.contract);
  const appendixSection = appendixDef
    ? sections.find(sec => sec.title === appendixDef.title) : null;
  const wantSubs = (appendixDef?.subsections ?? []).map(normalizeHeading);
  if (appendixSection && wantSubs.length) {
    for (const sub of sectionNames(viewOf(appendixSection.title))) {
      if (!wantSubs.includes(sub.name)) {
        problems.push(`「${appendixDef.title}·${sub.raw}」：不是合同约定的节`
          + `——${appendixDef.title}的节由章节合同登记：${wantSubs.join('、')}；`
          + '工程细节各有落点，叙述归正文章');
      }
    }
    for (const want of wantSubs) {
      const body = sectionBody(viewOf(appendixSection.title), want);
      if (body === null) {
        problems.push(`「${appendixDef.title}」：缺「${want}」这一节`
          + '——附录按合同逐节核，不涉及的节留标题并写「不涉及：<依据>」一行');
        continue;
      }
      const all = body.split(/\r?\n/).map(l => l.trim());
      const rows = all.filter(l => l.startsWith('|') || /^[-*+]\s/.test(l) || /^\d+[.)]\s/.test(l));
      if (!rows.length && !/不涉及[:：]\s*\S/.test(body)) {
        problems.push(`「${appendixDef.title}·${want}」：没有表行、列表行，也没有「不涉及：<依据>」`
          + '——附录每节的内容按表、列表或一行不涉及结论判');
      }
      // 有小节登记的节（技术契约）：小节按合同的节名认，机器区投在同名小节下
      const def = Object.entries(projectionOf(ctx.contract).sections).find(([k]) => normalizeHeading(k) === want)?.[1];
      const h4 = (def?.h4 ?? []).map(h => h.title);
      const have = all.filter(l => /^####\s/.test(l)).map(l => normalizeHeading(l.replace(/^####\s+/, '')));
      for (const name of h4.filter(n => !have.includes(n))) {
        problems.push(`「${appendixDef.title}·${want}」：下面缺「${name}」小节`
          + (have.length ? `（现在的小节是「${have.join('」「')}」）` : '')
          + `——这一节的小节按章节合同登记的节名认：${h4.join('、')}，机器区投在同名小节下`);
      }
    }
    const dump = viewOf(appendixSection.title).fences.find(f => f.lang && f.lang !== 'mermaid');
    if (dump) {
      problems.push(`「${appendixDef.title}」：有 ${dump.lang} 围栏块`
        + `——${appendixDef.title}按登记处判，mermaid 之外的围栏块都不收`);
    }

    // 附录里不放图。图若整批迁进附录，正文各章写着「下图是…」，
    // 读者读到那句话时手边没有图，要翻到最后再翻回来。
    //
    // 与集合一致那一条合起来看：登记的图要有去处，而附录不是去处。用它就放在讲它的那一章，
    // 不用它就在材料清单那一行写明理由——理由是文字，不是把图挪到附录充数。
    const inAppendix = [...appendixSection.text.matchAll(/!\[[^\]]*\]\(([^)\s]+)/g)]
      .map(m => m[1]);
    if (inAppendix.length) {
      problems.push(`「${appendixDef.title}」：有 ${inAppendix.length} 张图`
        + `（${inAppendix.slice(0, 3).join('、')}${inAppendix.length > 3 ? '…' : ''}）`
        + '——图放在讲它的那句话所在的章；'
        + `${appendixDef.title}是查阅件，不放图`);
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
 * 对每一区，按 `appendixZones` 算出**期望行**，与盘上那一段机器区**逐行逐格**比。
 * 作者说明在机器标记之外，不参加比较、也不被生成器重写。
 * 只归一 CRLF/LF、行尾空白与标题序号（保存时删掉的行尾空格、重编号铺上的序号都不是改动），
 * 不丢重复行、不只比首列、不忽略行序。
 *
 * 报错要指到**区与它的责任真源**：作者能改的是真源，不是机器区。
 * 这一步只读：算的是 `appendixZones`，不调会写盘的 `cmdProject`。
 */
export function appendixZoneProblems(ctx, storyText) {
  const problems = [];
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
  const zones = appendixZones(ctx, spec);
  for (const z of zones) {
    const at = onDisk.get(z.zone);
    // **真源读不出来不等于「期望是空的」**——与上面 spec 那一条同一个道理。
    // 附录·规约的真源是 `spec/knowledge-use.yaml`：激活清单里有条目而投影是空的，
    // 说明那份判断件不在或读不出，而它恰恰是「哪几条规约要逐条判」的唯一依据。
    if (!z.rows.length && z.source === KNOWLEDGE_USE_SOURCE) {
      const active = activeKnowledgeEntries(ctx);
      if (active.length) {
        problems.push(`${z.source}：读不出，「${appendix.title}·${z.zone}」无从核对`
          + `——这一轮激活了 ${active.length} 条规约，判定表由它投影；`
          + '判断件骨架由 `knowledge-use.mjs init` 生成，投影由 `story-build project` 写入');
        continue;
      }
    }
    if (!z.rows.length) {
      // 真源那一节现在什么都没有：机器区也该不在。留着就是上一版冒充现状。
      if (at) {
        problems.push(`「${appendix.title}·${z.zone}」：还留着机器区，而${z.source}那一节已经没有内容`
          + '——机器区由 `story-build project` 从真源投影，真源为空时投影删掉这一区');
      }
      continue;
    }
    if (!at) {
      problems.push(`「${appendix.title}·${z.zone}」：缺机器区`
        + `——机器区由 \`story-build project\` 从 ${z.source} 投影；`
        + '机器标记之外的目的句与说明归作者，投影不碰');
      continue;
    }
    const have = lines.slice(at.start + 1, at.end - 1);
    const diff = firstDiff(have, z.rows);
    if (!diff) continue;
    problems.push(`「${appendix.title}·${z.zone}」的机器区与${z.source}对不上（${diff.why}`
      + `${diff.at === null ? '' : `，第 ${diff.at + 1} 行`}）：`
      + `${diff.have === null ? '' : `盘上是「${cut(diff.have)}」，`}`
      + `${diff.want === null ? '' : `${z.source}投出来是「${cut(diff.want)}」`}`
      + `——机器区由 \`story-build project\` 从 ${z.source} 投影，内容以真源为准，手改会被下一次投影覆盖`);
  }
  // **集合两向都核**：上面走的是合同要的那几区；盘上多出来的名字在这里报。
  // 合同里没有它，就没有真源与它比——既不受投影约束，也不是作者说明，它会长期冒充现行投影。
  const known = new Set(zones.map(z => z.zone));
  for (const name of onDisk.keys()) {
    if (known.has(name)) continue;
    problems.push(`「${appendix.title}」：机器区「${name}」不在合同的投影登记里`
      + `（登记的是 ${zones.map(z => z.zone).join('、')}）`
      + '——机器区按合同登记的名字对应真源，这一段没有真源可比，也不随投影更新；'
      + '机器标记之外是作者区');
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
        problems.push(`「${chapterTitle}」第 ${i + 1} 行：又开了一个机器区（${name}），`
          + `而第 ${open.start + 1} 行的（${open.name}）还没关上`
          + '——机器区按起始、结束标记成对认，嵌套的里层认不成区；机器区的内容由 `story-build project` 从真源投影');
        return;
      }
      open = { name, start: i };
      return;
    }
    if (line.trim() !== ZONE_END) return;
    if (!open) {
      problems.push(`「${chapterTitle}」第 ${i + 1} 行：结束标记前面没有起始标记`
        + '——机器区按起始、结束标记成对认，孤立的结束标记指不到任何一段投影');
      return;
    }
    if (out.has(open.name)) {
      problems.push(`「${chapterTitle}·${open.name}」：在盘上有两段机器区`
        + '——投影只认第一段，第二段不随真源更新');
    } else {
      out.set(open.name, { start: open.start, end: i + 1 });
    }
    open = null;
  });
  if (open) {
    problems.push(`「${chapterTitle}·${open.name}」：机器区只有起始标记，没有结束标记`
      + '——首尾两行标记是投影的定位点，缺一行整段认不出来；'
      + '机器区的内容由 `story-build project` 从真源投影');
  }
  return out;
}

/**
 * 第一处对不上在哪 —— 逐行逐格，**行序算在内、重复行算在内**。
 *
 * 只归一行尾空白与标题序号（`zoneLine`）：保存时顺手删掉的行尾空格、重编号铺上的序号都不是改动。别的一概算改动，
 * 包括非首列改了一个字、两行换了顺序、少一行、多一行。
 */
function firstDiff(have, want) {
  const a = have.map(zoneLine);
  const b = want.map(zoneLine);
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    if (i >= a.length) return { why: '少了行', at: i, have: null, want: b[i] };
    if (i >= b.length) return { why: '多了行', at: i, have: a[i], want: null };
    if (a[i] !== b[i]) return { why: '这一行不一样', at: i, have: a[i], want: b[i] };
  }
  return null;
}
