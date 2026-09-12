/**
 * 章节合同的最小必要结构 —— 必要 H3、必要表、章首图与起始种子的唯一解释。
 *
 * 合同（story-chapters.json）每章给 `structure`：`h3` 是必须存在的小节（每项
 * `{title, when?}`），`tables` 是必须出现的表（`header` 全列供打底、`anchors` 最低锚列、
 * `at` 所属小节、`when` 条件），`diagram: "chapter-start"` 表示章首要有一张图。
 * 哪些章要什么全部是合同数据，这里不写死任何章名或表头——加一条必要结构改合同，代码不动。
 *
 * 同一份解释供三处用：`chapterSeedRows` 打底、`chapterStructureProblems` 核对、
 * 条件判定共用 `applies`。**打底与核对必须同位置**：否则作者第一次知道「这一章要有
 * 哪个小节」是在报错里。
 *
 * 边界：只核机械结构与渲染种子。源图对应、全局编号、投影完整性、图片身份、
 * 冻结、语义质量都不在这里；输入是已解析的数据（`facts`），本模块不读磁盘、
 * 不写文件、不输出 stdout、也不导入 story-build 入口。
 */
import { normalizeHeading } from '../headings.mjs';

/** 规范化：去空白与标点——「点了提交、但没收到回执」与原文只差标点时仍算同一句。 */
export function norm(s) {
  return String(s ?? '').replace(/[\s，。、；：!?！？（）()「」【】]/g, '');
}

/** markdown 表的表头列 —— 分隔行上面那一行就是表头。列名剥掉行内标记。 */
function tableHeaders(text) {
  const lines = String(text ?? '').split(/\r?\n/);
  const out = [];
  for (let i = 0; i + 1 < lines.length; i += 1) {
    const head = lines[i].trim();
    const sep = lines[i + 1].trim();
    if (!head.startsWith('|') || !/^\|[-: |]+\|$/.test(sep)) continue;
    out.push(head.replace(/^\||\|$/g, '').split('|').map(c => norm(c.replace(/[`*]/g, ''))));
  }
  return out;
}

/** 渲染一张 markdown 表：表头 + 分隔行 + 数据行。 */
export function renderTable(header, rows) {
  return [`| ${header.join(' | ')} |`, `|${header.map(() => '---').join('|')}|`,
    ...rows.map(r => `| ${r.join(' | ')} |`)];
}

/**
 * 一章的两份视图：**章首**（第一个正文 H3 之前的原文）与**去围栏正文**。
 *
 * 章首是「总览图该在哪」的范围：图挂在某个局部小节下面，读者在章首看不到全过程。
 * 去围栏正文是标题与表的判定面：围栏里的标题和表是被引用的样例——把它们算进来，
 * 贴一段别处的示例就能顶掉本章真正缺的那一节。
 */
function views(text) {
  const lead = [], prose = [];
  let inFence = false, afterH3 = false;
  for (const line of String(text ?? '').split(/\r?\n/)) {
    const fence = /^[ \t]*(?:```|~~~)/.test(line);
    if (fence) inFence = !inFence;
    if (!inFence && !fence && /^###\s+/.test(line.trim())) afterH3 = true;
    if (!afterH3) lead.push(line);
    if (!inFence && !fence) prose.push(line);
  }
  return { lead: lead.join('\n'), prose: prose.join('\n') };
}

/** 全篇正文里的 `###` 小节名（围栏里的不算——那是被引用的样例）。 */
export function subsectionNames(sectionText) {
  const out = [];
  for (const line of views(sectionText).prose.split(/\r?\n/)) {
    const m = line.trim().match(/^###\s+(.+)$/);
    if (m) out.push({ raw: m[1].trim(), name: normalizeHeading(m[1]) });
  }
  return out;
}

/** 从一章的正文里切出某个 `###` 小节。 */
export function subsectionText(sectionText, name) {
  const want = normalizeHeading(name);
  const body = [];
  let hit = false;
  for (const line of views(sectionText).prose.split(/\r?\n/)) {
    const m = line.trim().match(/^###\s+(.+)$/);
    if (m) {
      if (hit) break;
      hit = normalizeHeading(m[1]) === want;      // `### A. 接口` 与合同的 `接口` 是同一节
      continue;
    }
    if (hit) body.push(line);
  }
  return hit ? body.join('\n') : null;
}

/**
 * 按名字找一个小节的正文 —— 先精确，再包含。
 *
 * 合同给的是这一节要讲什么，作者按业务命名；精确匹配会把后者判成「缺这一节」。
 */
function findSubsection(text, name) {
  const exact = subsectionText(text, name);
  if (exact !== null) return exact;
  const want = normalizeHeading(name);
  const hit = subsectionNames(text).find(x => x.name.includes(want));
  return hit ? subsectionText(text, hit.name) : null;
}

/**
 * 这一条必要结构现在适用吗。
 *
 * `when: "siblings"` 只在**确有**兄弟单据时必需：`facts.siblings` 三态里只有 `true`
 * 算成立。`null` 是拿不准（离线的仲裁锚读不到流程契约）——拿不准当成立，就会把
 * 没有兄弟单的那一份判成缺一节；当不成立，草稿里也就不打这个底。两样都不做。
 */
function applies(item, facts) {
  if (!item?.when) return true;
  if (item.when === 'siblings') return facts?.siblings === true;
  return false;
}

/** 这一章适用的必要 H3。 */
function requiredH3(ch, facts) {
  return (ch?.structure?.h3 ?? []).filter(h => applies(h, facts));
}

/** 这一章适用的必要表。 */
function requiredTables(ch, facts) {
  return (ch?.structure?.tables ?? []).filter(t => applies(t, facts));
}

const DIAGRAM_FENCE = /^[ \t]*(?:```|~~~)[ \t]*(?:mermaid|plantuml|puml|dot|graphviz)\b/mi;

/**
 * 这张必要表在不在 —— **认表看主语，核列看最低锚列**。
 *
 * `anchors` 第一组是这张表的主语（认出「他打算用这张表答这件事」），其余各组是这张表
 * 必须有的列；每组内任一说法命中即可，列名换措辞不算缺，加列合法。判的是**同一张表**
 * 满足全部锚列：任意一列、或把凭据散在几张表里，读者要自己拼，那不是凭据。
 */
function tableProblem(ch, text, slot) {
  const scope = slot.at ? findSubsection(text, slot.at) : text;
  if (scope === null) return null;             // 那一节缺席由必要 H3 那条报，这里不重复
  const groups = (slot.anchors ?? []).map(g => (Array.isArray(g) ? g : [g]));
  if (!groups.length) return null;
  const has = (cols, group) => group.some(a => cols.some(c => c.includes(norm(a))));
  const where = slot.at ? `「${ch.title}·${slot.at}」` : `「${ch.title}」`;
  const table = tableHeaders(scope).find(cols => has(cols, groups[0]));
  if (!table) {
    return `${where}缺一张表（表头含「${groups[0][0]}」，`
      + `另外这几列也要有：${groups.slice(1).map(g => g[0]).join('、') || '无'}）`;
  }
  const miss = groups.slice(1).filter(g => !has(table, g));
  if (miss.length) {
    return `${where}「${groups[0][0]}」那张表缺 ${miss.map(g => `「${g[0]}」`).join('、')}`
      + '这几列——列名可以按本需求换说法，但这几件事读者要在同一张表里看到';
  }
  return null;
}

/**
 * 这一章的必要结构在不在 —— 返回问题串；正文合法的新形式不因本模块受限。
 *
 * 必要 H3 按名字找（先精确再包含）；必要表按锚列认，位置按 `at`；章首图只看章首那段。
 * 报错带实际 H3/表头与所在章，不只说「形态不对」。
 */
export function chapterStructureProblems(ch, body, facts) {
  const problems = [];
  const { lead, prose } = views(body);
  for (const want of requiredH3(ch, facts)) {
    if (findSubsection(prose, want.title) === null) {
      problems.push(`「${ch.title}」缺「${want.title}」这一节`);
    }
  }
  for (const slot of requiredTables(ch, facts)) {
    const problem = tableProblem(ch, prose, slot);
    if (problem) problems.push(problem);
  }
  if (ch?.structure?.diagram && !DIAGRAM_FENCE.test(lead)) {
    problems.push(`「${ch.title}」章首缺一张覆盖主路径与全部分支去向的总览图`
      + '——挂在某个局部小节下面的图答不了「整条业务怎么走」');
  }
  return problems;
}

/**
 * 这一章从真源打的底 —— **打完就归作者**，位置与核对处同一份解释。
 *
 * 只保留三类：必要小节的标题、术语起始行与验收/交付的表头、附录五节与材料清单的
 * 贡献行。表头及小节名从合同取；术语行/材料清单行来自输入（facts 已解析），这里
 * 不重读源文件。附录 A–D 不预填机器正文——那四节归投影，作者改的是真源。
 * 流程图由作者按当前业务生成，源图材料不是默认的业务总览答案。
 *
 * @param {object} ch 合同章
 * @param {object} facts 入口解析好的当前输入：terms、materialListRows、siblings
 * @returns {string[]} markdown 行
 */
export function chapterSeedRows(ch, facts) {
  if (ch.appendix) return appendixSeedRows(ch, facts);
  const rows = [];
  const tables = requiredTables(ch, facts).filter(t => t.seed);
  for (const t of tables.filter(t => !t.at)) rows.push(...tableSeed(t, facts), '');
  for (const h of requiredH3(ch, facts)) {
    rows.push(`### ${h.title}`, '');
    for (const t of tables.filter(t => normalizeHeading(t.at ?? '') === normalizeHeading(h.title))) {
      rows.push(...tableSeed(t, facts), '');
    }
  }
  return rows;
}

/** 一张必要表的起始形态：术语行来自真源，其余给占位行让作者往下填。 */
function tableSeed(t, facts) {
  const cells = String(t.header).split('|');
  const terms = facts?.terms ?? [];
  if (t.seed === 'terms') {
    return terms.length ? renderTable(cells, terms) : [];
  }
  return renderTable(cells, [cells.map(c => `{{${c || '　'}}}`)]);
}

/** 附录：五节标题 + 每节一句目的；材料清单那一节多给贡献行。 */
function appendixSeedRows(ch, facts) {
  const out = [];
  for (const name of ch.subsections ?? []) {
    out.push(`### ${name}`, '', '{{一句这一节给评审者看什么}}', '');
    // 材料清单是作者种子：类别与链接由清单给，「贡献了什么」只有他知道。
    // 其余四节由 `project` 投影，草稿里不放——放了他就要在两处维护同一张表。
    if (normalizeHeading(name) === normalizeHeading(facts?.materialListName ?? '')) {
      out.push(...(facts?.materialListRows ?? []), '');
    }
  }
  return out;
}
