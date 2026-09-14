/**
 * 章节合同的最小必要结构 —— 必要 H3、必要表、图与起始种子的唯一解释。
 *
 * 合同（story-chapters.json）每章给 `structure`：`h3` 是机器要定位的小节（给表定范围的
 * 那种与附录五节），`tables` 是必须出现的表（`header` 全列供打底、`anchors` 最低锚列、
 * `at` 所属小节），`diagram: true` 表示这一章要有一张真正的图。
 * 哪些章要什么全部是合同数据，这里不写死任何章名或表头——加一条必要结构改合同，代码不动。
 * 写作设计选定的表图由 `writing-plan.selectedStructure` 并进同一个 `structure`（带 `selected`，
 * 图记在 `diagrams`），这里按同一套解释打底与核对。
 *
 * **标题名不是内容判据**：分工讲没讲清、回退措施有没有依据，读的是内容，由读者问题、
 * 章级维度与独立语义审查判；按标题名判会把「用业务名起了另一个标题」说成缺了这件事。
 *
 * 同一份解释供三处用：`chapterSeedRows` 打底、`chapterStructureProblems` 核对、
 * `missingPickedSeeds` 给已有草稿补起点。**打底与核对必须同位置**：否则作者第一次知道
 * 「这一章要有哪个小节」是在报错里。
 *
 * 边界：**只判，不切文**。围栏、小节、表头由 `document.parseChapter` 解析一次，
 * 这里读它的结果；源图对应、全局编号、投影完整性、图片身份、冻结、语义质量都不在这里。
 * 本模块不读磁盘、不写文件、不输出 stdout，也不导入 story-build 入口。
 */
import { hasDiagram, norm, normalizeHeading, sectionBody, tablesIn } from './document.mjs';

//: 写作设计选定的结构缺了时，报错多说这一句：它不是合同要求，改主意要回写作设计改。
const PICKED = '——这是写作设计里选定的结构；改主意就同时改写作设计的结构选择';

/** 渲染一张 markdown 表：表头 + 分隔行 + 数据行。 */
export function renderTable(header, rows) {
  return [`| ${header.join(' | ')} |`, `|${header.map(() => '---').join('|')}|`,
    ...rows.map(r => `| ${r.join(' | ')} |`)];
}

/** 这一章要定位的必要 H3（给表定范围的那种、附录五节，与写作设计选定的小节）。 */
function requiredH3(ch) {
  return ch?.structure?.h3 ?? [];
}

/** 这一章的必要表。 */
function requiredTables(ch) {
  return ch?.structure?.tables ?? [];
}

/**
 * 这张必要表在不在 —— **作用域内任意一张满足全部锚列就算**。
 *
 * `anchors` 第一组是这张表的主语（认出「他打算用这张表答这件事」），其余各组是这张表
 * 必须有的列；每组内任一说法命中即可，列名换措辞不算缺，加列合法。判的是**同一张表**
 * 满足全部锚列：把凭据散在几张表里，读者要自己拼，那不是凭据。
 *
 * 只认第一张同主语的表就会拦住合法产物：验收章前面先放一张「编号／说明」的对照表、
 * 后面才是完整的验收表，那一章其实是齐的。所以遍历作用域内的全部候选，
 * 一张都不满足时才按最像的那张报缺了哪几列。
 */
function tableProblem(ch, view, slot) {
  const scope = tablesIn(view, slot.at);
  if (scope === null) return null;             // 那一节缺席由必要 H3 那条报，这里不重复
  const groups = (slot.anchors ?? []).map(g => (Array.isArray(g) ? g : [g]));
  if (!groups.length) return null;
  const has = (cols, group) => group.some(a => cols.some(c => c.includes(norm(a))));
  const where = slot.at ? `「${ch.title}·${slot.at}」` : `「${ch.title}」`;
  const tail = slot.selected ? PICKED : '';
  const candidates = scope.filter(cols => has(cols, groups[0]));
  if (candidates.some(cols => groups.every(g => has(cols, g)))) return null;
  if (!candidates.length) {
    return `${where}缺一张表（表头含「${groups[0][0]}」，`
      + `另外这几列也要有：${groups.slice(1).map(g => g[0]).join('、') || '无'}）${tail}`;
  }
  // 有同主语的表但没有一张齐的：按缺得最少的那张说，作者改它就够了
  const best = candidates
    .map(cols => groups.slice(1).filter(g => !has(cols, g)))
    .sort((a, b) => a.length - b.length)[0];
  return `${where}「${groups[0][0]}」那张表缺 ${best.map(g => `「${g[0]}」`).join('、')}`
    + `这几列——列名可以按本需求换说法，但这几件事读者要在同一张表里看到${tail}`;
}

/**
 * 这一章的必要结构在不在 —— 返回问题串；正文合法的新形式不因本模块受限。
 *
 * 必要 H3 按名字找（先精确再包含）；必要表按锚列认，位置按 `at`；`diagram` 只核这一章
 * 真有一张图。**合同那张图在章里的位置不判**：总览可以在章首那段，也可以在一个「总览」
 * 小节里，按位置推断它是不是总览会拦住合法产物；它讲没讲清整条业务、局部图接不接得回
 * 总览，归语义审查。写作设计选定到某一节的图，只核那一节里有图。
 * 报错带实际 H3/表头与所在章，不只说「形态不对」。
 *
 * @param {object} ch 合同章（可已并入写作设计选定的结构）
 * @param {object} view `document.parseChapter` 的结果（一次解析，各判据共用）
 */
export function chapterStructureProblems(ch, view) {
  const problems = [];
  for (const want of requiredH3(ch)) {
    if (sectionBody(view, want.title) === null) {
      problems.push(`「${ch.title}」缺「${want.title}」这一节${want.selected ? PICKED : ''}`);
    }
  }
  for (const slot of requiredTables(ch)) {
    const problem = tableProblem(ch, view, slot);
    if (problem) problems.push(problem);
  }
  if (ch?.structure?.diagram && !hasDiagram(view)) {
    problems.push(`「${ch.title}」没有图——这一章要一张覆盖主路径与全部分支去向的总览图；`
      + '放在章首那段或一个总览小节里都行，代码围栏不算');
  }
  for (const slot of ch?.structure?.diagrams ?? []) {
    if (hasDiagram(view, slot.at) !== false) continue;   // null＝那一节缺席，由必要 H3 那条报
    problems.push(`「${ch.title}${slot.at ? `·${slot.at}` : ''}」没有图（画图语言的围栏）${PICKED}`);
  }
  return problems;
}

/**
 * 这一章从真源打的底 —— **打完就归作者**，位置与核对处同一份解释。
 *
 * 只保留三类：必要小节的标题、术语起始行与必要表的表头、附录五节与材料清单的贡献行。
 * 表头及小节名从合同与写作设计取；术语行/材料清单行来自输入（facts 已解析），这里
 * 不重读源文件。附录 A–D 不预填机器正文——那四节归投影，作者改的是真源。
 * 图不生成节点：选定的图只留一行作图提示（`diagramHint` 由草稿生产者给出它的指引行格式）。
 *
 * @param {object} ch 合同章（可已并入写作设计选定的结构）
 * @param {object} facts 入口解析好的当前输入：terms、materialListRows、materialListName
 * @param {{diagramHint?: (at: string) => string}} [options]
 * @returns {string[]} markdown 行
 */
export function chapterSeedRows(ch, facts, { diagramHint } = {}) {
  if (ch.appendix) return appendixSeedRows(ch, facts);
  const rows = [];
  const hint = (at) => ((ch.structure?.diagrams ?? [])
    .some(d => normalizeHeading(d.at) === normalizeHeading(at)) && diagramHint
    ? [diagramHint(at), ''] : []);
  const tables = requiredTables(ch).filter(t => t.seed);
  rows.push(...hint(''));
  for (const t of tables.filter(t => !t.at)) rows.push(...tableSeed(t, facts), '');
  for (const h of requiredH3(ch)) {
    rows.push(`### ${h.title}`, '', ...hint(h.title));
    for (const t of tables.filter(t => normalizeHeading(t.at ?? '') === normalizeHeading(h.title))) {
      rows.push(...tableSeed(t, facts), '');
    }
  }
  return rows;
}

/**
 * 已有草稿里还没有的**选定**结构 —— 给作者按需贴进去的起点，不改他的草稿。
 *
 * 只看写作设计选定的那几项：合同的必要结构缺了，提交时的核对会报。
 *
 * @returns {string[]} markdown 行；什么都不缺时为空
 */
export function missingPickedSeeds(ch, view, { diagramHint } = {}) {
  const rows = [];
  const named = new Set();
  const heading = (at) => {
    const key = normalizeHeading(at);
    if (!at || named.has(key)) return [];
    named.add(key);
    return sectionBody(view, at) === null ? [`### ${at}`, ''] : [];
  };
  for (const t of requiredTables(ch).filter(x => x.selected)) {
    if (tablesIn(view, t.at) !== null && !tableProblem(ch, view, t)) continue;
    rows.push(...heading(t.at ?? ''), ...tableSeed(t, {}), '');
  }
  for (const d of (ch.structure?.diagrams ?? []).filter(x => x.selected)) {
    if (hasDiagram(view, d.at) === true) continue;
    rows.push(...heading(d.at), ...(diagramHint ? [diagramHint(d.at), ''] : []));
  }
  for (const h of requiredH3(ch).filter(x => x.selected)) rows.push(...heading(h.title));
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
