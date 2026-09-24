/**
 * 章节合同的最小必要结构 —— 必要 H3、必要表、图与起始种子的唯一解释。
 *
 * 合同（story-chapters.json）每章给 `structure`：`h3` 是机器要定位的小节（给表定范围的
 * 那种与附录各节），`tables` 是必须出现的表（`header` 全列供打底、`anchors` 最低锚列、
 * `at` 所属小节），`diagram: true` 表示这一章要有一张真正的图。
 * 哪些章要什么全部是合同数据，这里不写死任何章名或表头——加一条必要结构改合同，代码不动。
 * 写作设计骨架里的小节、形式与图由 `writing-plan.selectedStructure` 并进同一个 `structure`
 * （小节带 `selected`，图在 `diagrams`，表与列表的存在性要求在 `forms`），这里按同一套解释
 * 打底与核对。**表的列不由模板定**：固定合同那几张按锚列核，模板选的表只核那个位置真有一张表。
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
import {
  ambiguousSection, DIAGRAM_SYNTAXES, EMPTY_SECTION_TEXT, hasDiagram, hasList, hasTable, norm,
  normalizeHeading, scopeSpan, sectionBody, subsectionNames, tablesIn,
} from './document.mjs';

//: 骨架里定的表图缺了时，报错多说这一句：它不是合同要求，改主意就改骨架。
const PICKED = '——这是写作设计骨架里定的结构；改主意就同时改骨架';
//: 骨架里列的小节缺了时的两个出口。
const SKELETON_EXITS = '——写作设计骨架里有它：补上它，或者先删掉骨架里那一行再提交';

/** 一处选定形式叫什么：给人看的那半句。 */
const formName = (form) => (form.kind === 'table' ? '一张表'
  : `${form.ordered ? '有序' : '无序'}列表`);

/** 形式落在哪个范围：章级、某一节，或某一节下的子节。 */
const formWhere = (ch, form) => `「${ch.title}${form.at ? `·${form.at}` : ''}`
  + `${form.under ? `·${form.under}` : ''}」`;

/**
 * 选定的形式在不在 —— **只核存在，不核内容**。
 *
 * 表格核那个范围里真有一张表，不比列名：列由写章的人按原文定。
 * 列表核范围里有真的列表项，不数条目。叙述不进这里——它没有可机械核的形态。
 * 同一范围固定合同已经要求一张表时，由合同那条报（它连锚列一起核），这里不重复。
 */
function contractCovers(ch, form) {
  return form.kind === 'table' && !form.under && requiredTables(ch)
    .some(t => normalizeHeading(t.at ?? '') === normalizeHeading(form.at ?? ''));
}

function formProblem(ch, view, form) {
  const span = scopeSpan(view, form.at ?? '', form.under ?? '');
  if (!span) return null;                 // 那一节/子节缺席由必要 H3、H4 那条报
  if (contractCovers(ch, form)) return null;   // 同范围合同已经要一张表：由它那条连锚列一起报
  if (form.kind === 'table') {
    return hasTable(view, span) ? null
      : `${formWhere(ch, form)}缺${formName(form)}——写作设计在这里选了表格${PICKED}`;
  }
  return hasList(view, span, form.ordered) ? null
    : `${formWhere(ch, form)}缺${formName(form)}——写作设计在这里选了它${PICKED}`;
}

/** 一个图槽位叫什么：点名了类型的说类型，没点名的是任何一种图。 */
const diagramName = (slot) => (slot.syntax
  ? `${DIAGRAM_SYNTAXES[slot.syntax].name}（mermaid 围栏里首个声明是 `
    + `${DIAGRAM_SYNTAXES[slot.syntax].heads.join(' 或 ')}，别的图不能顶替）`
  : '图（画图语言的围栏）');

/** 渲染一张 markdown 表：表头 + 分隔行 + 数据行。 */
export function renderTable(header, rows) {
  return [`| ${header.join(' | ')} |`, `|${header.map(() => '---').join('|')}|`,
    ...rows.map(r => `| ${r.join(' | ')} |`)];
}

/** 这一章要定位的必要 H3（给表定范围的那种、附录各节，与写作设计选定的小节）。 */
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
  const candidates = scope.filter(cols => has(cols, groups[0]));
  if (candidates.some(cols => groups.every(g => has(cols, g)))) return null;
  if (!candidates.length) {
    return `${where}缺一张表（表头含「${groups[0][0]}」，`
      + `另外这几列也要有：${groups.slice(1).map(g => g[0]).join('、') || '无'}）`;
  }
  // 有同主语的表但没有一张齐的：按缺得最少的那张说，作者改它就够了
  const best = candidates
    .map(cols => groups.slice(1).filter(g => !has(cols, g)))
    .sort((a, b) => a.length - b.length)[0];
  return `${where}「${groups[0][0]}」那张表缺 ${best.map(g => `「${g[0]}」`).join('、')}`
    + '这几列——列名可以按本需求换说法，但这几件事读者要在同一张表里看到';
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
    if (sectionBody(view, want.title) !== null) continue;
    const ambiguous = ambiguousSection(view, want.title);
    problems.push(ambiguous
      ? `「${ch.title}」里「${want.title}」同时像${ambiguous.map(n => `「${n}」`).join('、')}这几节`
        + '——把这一节的标题写成它的完整名字，或给不相干的那一节换个名字'
      : `「${ch.title}」缺「${want.title}」这一节${want.selected ? SKELETON_EXITS : ''}`);
  }
  for (const want of ch?.structure?.h4 ?? []) {
    // 先定位父节：全章找同名 H4 的话，甲节缺的那一节会被乙节的同名子节顶替通过
    const subs = subsectionNames(view, want.parent);
    if (subs === null) continue;              // 父节缺席由上面那条报
    if (!subs.has(normalizeHeading(want.title))) {
      problems.push(`「${ch.title}·${want.parent}」缺「${want.title}」这一小节（####）${SKELETON_EXITS}`);
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
    // 与合同那张重合：有没有图由上面那条核；点名了类型的，章里有图之后再核是不是那一种
    if (slot.alsoRequired && (!slot.syntax || !hasDiagram(view))) continue;
    if (hasDiagram(view, slot.at, slot.syntax, slot.under ?? '') !== false) continue;
    problems.push(`「${ch.title}${slot.at ? `·${slot.at}` : ''}${slot.under ? `·${slot.under}` : ''}」`
      + `没有${diagramName(slot)}${PICKED}`);
  }
  for (const form of ch?.structure?.forms ?? []) {
    const problem = formProblem(ch, view, form);
    if (problem) problems.push(problem);
  }
  return problems;
}

/**
 * 写作设计为这一章选定的表与图，报错用的名字。
 *
 * 章正文写「不涉及」而设计还选着结构时，两个明确声明冲突：由作者撤回选择或写出正文，
 * 脚本不替他判这一章到底涉不涉及。合同自带的必要结构不在其中，空章语义照旧。
 */
export function pickedStructureNames(ch) {
  const where = (at) => (at ? `「${at}」里的` : '章级');
  return [
    ...requiredH3(ch).filter(h => h.selected).map(h => `「${h.title}」这一节`),
    ...(ch?.structure?.h4 ?? []).map(h => `「${h.title}」这一小节`),
    ...(ch?.structure?.diagrams ?? []).filter(d => d.selected)
      .map(d => `${where(d.at)}${d.syntax ? DIAGRAM_SYNTAXES[d.syntax].name : '图'}`),
    ...(ch?.structure?.forms ?? []).map(f => `${where(f.under || f.at)}${formName(f)}`),
  ];
}

/**
 * 这一章从真源打的底 —— **打完就归作者**，位置与核对处同一份解释。
 *
 * 按骨架铺：骨架的小节标题树、每节的说明行（`guide` 由草稿生产者给出它的指引行格式）、
 * 表头与作图提示放在骨架写的位置；合同另有、骨架没列的必要小节接在后面；
 * 骨架写「不涉及」的章只放那一句。术语行/材料清单行来自输入（facts 已解析），这里
 * 不重读源文件。附录不预填机器正文——机器区归投影，作者改的是真源。
 * 图不生成节点：只铺图三件套的三行指引（`diagramHint`）。
 *
 * @param {object} ch 合同章（可已并入写作设计骨架）
 * @param {object} facts 入口解析好的当前输入：terms、materialListRows、materialListName
 * @param {{diagramHint?: (at: string, syntax?: string) => string[], guide?: (note: string) => string}} [options]
 * @returns {string[]} markdown 行
 */
export function chapterSeedRows(ch, facts, { diagramHint, formHint, guide } = {}) {
  const sk = ch.structure?.skeleton;
  const notes = (n) => (guide && n?.notes?.length ? [...n.notes.map(guide), ''] : []);
  if (ch.appendix) return [...notes(sk), ...appendixSeedRows(ch, facts)];
  if (sk && sk.notApplicable !== null) return [...notes(sk), EMPTY_SECTION_TEXT];
  const same = (a, b) => normalizeHeading(a ?? '') === normalizeHeading(b ?? '');
  // 一个位置可以有几种形式：图各留一行作图提示，表与列表各留一行「这里要完成什么」。
  // 两者都不生成内容——列、节点与项目由写章的人按原文定。
  const hint = (at, under = '') => [
    ...(ch.structure?.diagrams ?? []).filter(d => same(d.at, at) && same(d.under, under))
      .flatMap(d => (diagramHint ? [...diagramHint(under || at, d.syntax), ''] : [])),
    ...(ch.structure?.forms ?? []).filter(f => same(f.at, at) && same(f.under, under))
      .flatMap(f => (formHint ? [formHint(under || at, f), ''] : [])),
  ];
  // 合同没指定位置的章级表，模板在某一节选了表格时就铺在那一节：同一用途只播一张，
  // 章头与小节各铺一张的话作者要删一张，而锚列按整章核，放哪一张都过。指定了 `at` 的表留在原位。
  const picked = (ch.structure?.forms ?? []).find(f => f.kind === 'table');
  const place = (t) => (t.at || !picked ? [t.at, t.under] : [picked.at, picked.under]);
  const seeds = (at, under = '') => requiredTables(ch)
    .filter(t => t.seed && same(place(t)[0], at) && same(place(t)[1], under))
    .flatMap(t => [...tableSeed(t, facts), '']);
  const rows = [...notes(sk), ...hint(''), ...seeds('')];
  const done = new Set();
  for (const s of sk?.sections ?? []) {
    done.add(normalizeHeading(s.title));
    rows.push(`### ${s.title}`, '', ...notes(s), ...hint(s.title), ...seeds(s.title));
    for (const c of s.sections) {
      rows.push(`#### ${c.title}`, '', ...notes(c), ...hint(s.title, c.title), ...seeds(s.title, c.title));
    }
  }
  for (const h of requiredH3(ch).filter(x => !done.has(normalizeHeading(x.title)))) {
    rows.push(`### ${h.title}`, '', ...hint(h.title), ...seeds(h.title));
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
export function missingPickedSeeds(ch, view, { diagramHint, formHint } = {}) {
  //: **按小节归堆，不按种类**。一节同时要状态图与表是正常安排（状态图讲转移、表讲每个状态
  //  允许什么）；按种类排的话，图在图那一轮、表在表那一轮，中间隔着别的小节的标题——
  //  这一节的表就排在了上一节标题下面，而这段文字是给作者「按需贴进去」的。
  const groups = new Map();
  const push = (at, added) => {
    const key = normalizeHeading(at ?? '');
    if (!groups.has(key)) {
      groups.set(key, at && sectionBody(view, at) === null ? [`### ${at}`, ''] : []);
    }
    groups.get(key).push(...added);
  };
  // 合同的表：模板在同范围选了表格时给起点——那一处的形式要求由这张合同表接替
  const wanted = (t) => (ch.structure?.forms ?? []).some(f => contractCovers(ch, f)
    && normalizeHeading(f.at ?? '') === normalizeHeading(t.at ?? ''));
  for (const t of requiredTables(ch).filter(wanted)) {
    if (tablesIn(view, t.at) !== null && !tableProblem(ch, view, t)) continue;
    push(t.at ?? '', [...tableSeed(t, {}), '']);
  }
  for (const d of (ch.structure?.diagrams ?? []).filter(x => x.selected)) {
    if (hasDiagram(view, d.at, d.syntax, d.under ?? '') === true) continue;
    push(d.at, diagramHint ? [...diagramHint(d.under || d.at, d.syntax), ''] : []);
  }
  for (const f of ch.structure?.forms ?? []) {
    if (contractCovers(ch, f)) continue;         // 起点由上面那张合同表给，一处只给一次
    // 那一节还没有：起点给标题，也给这一处要完成什么——只补标题的话，作者不知道这里要做什么
    const span = scopeSpan(view, f.at ?? '', f.under ?? '');
    if (span && !formProblem(ch, view, f)) continue;
    push(f.at ?? '', formHint ? [formHint(f.under || f.at, f), ''] : []);
  }
  for (const h of requiredH3(ch).filter(x => x.selected)) push(h.title, []);
  for (const h of ch.structure?.h4 ?? []) {
    const subs = subsectionNames(view, h.parent);
    if (subs?.has(normalizeHeading(h.title))) continue;
    push(h.parent, [`#### ${h.title}`, '']);
  }
  return [...groups.values()].flat();
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

/** 附录：各节标题 + 每节一句业务定位；有 H4 的节铺出 H4 标题；材料清单那一节多给贡献行。 */
function appendixSeedRows(ch, facts) {
  const out = [];
  for (const name of ch.subsections ?? []) {
    out.push(`### ${name}`, '', '{{一句：这一节登记什么的精确名称}}', '');
    // H4 标题与机器区之后的说明归作者；机器区由 `project` 投在标题下，草稿里不放——
    // 放了他就要在两处维护同一张表。
    for (const h4 of ch.projection?.sections?.[name]?.h4 ?? []) out.push(`#### ${h4.title}`, '');
    // 材料清单是作者种子：类别与链接由清单给，「贡献了什么」只有他知道。
    if (normalizeHeading(name) === normalizeHeading(facts?.materialListName ?? '')) {
      out.push(...(facts?.materialListRows ?? []), '');
    }
  }
  return out;
}
