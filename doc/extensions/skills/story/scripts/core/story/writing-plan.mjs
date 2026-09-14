/**
 * 写作设计 —— `AR/story-src/story-template.md` 的协议：空壳、读取、解析与选定结构的唯一解释。
 *
 * 这份文件由作者在 Spec 与决策登记之后写：第一次读的人按什么顺序理解这件事（阅读主线）、
 * 每章在本需求里要回答的实际问题与依据（章节安排）、已经选定要脚本落实的表和图（结构选择）。
 * 脚本在这里只做确定的事：建空壳、指出协议缺了什么、把选定的表图换成章节合同能消费的结构。
 * 设计讲得合不合理、正文照没照它写，归作者整稿与独立审查。
 *
 * skeleton、章提交与全篇 check 读同一份解析结果，那段 JSON 只在这里解析。
 * 本模块不写盘、不输出 stdout；围栏按 document 的规则认，不另写 Markdown 解析。
 */
import { readText } from './context.mjs';
import { fenceRanges, norm, normalizeHeading, placeholderProblems } from './document.mjs';
import { relFromFeature } from './sources.mjs';

//: 三个必需的二级标题。协议认名字，不管顺序，也不管前面有没有别的说明。
const PARTS = { story: '阅读主线', chapters: '章节安排', picks: '结构选择' };
const KINDS = ['table', 'diagram'];
const FIELDS = ['chapter', 'at', 'kind', 'columns'];

/** 空壳：三部分标题、每章一个章 ID 小节、一个空数组。占位写的是这一格要回答什么。 */
export function writingPlanShell(contract) {
  const rows = ['# 写作设计', '', `## ${PARTS.story}`, '',
    '{{第一次读这份需求的人按什么顺序理解它：哪些参与方、对象与关系要先讲，'
    + '已定决定的依据在哪，哪些未决限制后面的叙述}}', '', `## ${PARTS.chapters}`, ''];
  for (const ch of contract.chapters ?? []) {
    rows.push(`### ${ch.id}`, '', `{{「${ch.title}」在本需求里要回答的实际问题、主要依据位置、`
      + '与别的章怎么互补、拟用形式及理由；不涉及就写理由}}', '');
  }
  rows.push(`## ${PARTS.picks}`, '', '```json', '[]', '```', '');
  return rows.join('\n');
}

/**
 * 读当前写作设计 —— 协议立不立得住，一次报全。
 *
 * 只判协议：三部分在不在、每章有没有一段安排、章 ID 对不对、结构选择的形状。
 * 不设安排的深度、字数或主题词门槛：按字面门槛判，作者只会照着门槛凑字。
 *
 * @returns {{text: string|null, chapterPlans: Map<string, string>,
 *   structures: object[], problems: string[], chapters: object[]}}
 */
export function readWritingPlan(ctx) {
  const chapters = ctx.contract.chapters ?? [];
  const plan = { text: null, chapterPlans: new Map(), structures: [], problems: [], chapters };
  const rel = relFromFeature(ctx, ctx.templatePath);
  const say = (msg) => plan.problems.push(`写作设计 ${rel} ${msg}`);
  const text = readText(ctx.templatePath);
  if (text === null || !text.trim()) {
    say(`${text === null ? '不在' : '是空的'}——跑 skeleton 建空壳，对照原材料、需求分析里的来源初筛、`
      + 'Spec 与决策登记，把它写成本需求的整篇设计');
    return plan;
  }
  plan.text = text;
  const lines = text.split(/\r?\n/);
  const fences = fenceRanges(lines);
  const fenced = new Set(fences.flatMap(f => lines.slice(f.from, f.to + 1).map((_, k) => f.from + k)));
  const heads = (marks) => lines.flatMap((line, at) => {
    const hit = !fenced.has(at) && new RegExp(`^${marks}\\s+(.+?)\\s*$`).exec(line);
    return hit ? [{ name: hit[1].trim(), at }] : [];
  });
  const h2 = heads('##');
  const part = (name) => {
    const hits = h2.filter(h => normalizeHeading(h.name) === name);
    if (hits.length !== 1) {
      say(hits.length ? `有 ${hits.length} 个「## ${name}」——只留一个` : `缺「## ${name}」这一部分`);
      return null;
    }
    const next = h2.find(h => h.at > hits[0].at);
    return { from: hits[0].at + 1, to: next ? next.at : lines.length };
  };
  const body = (from, to) => lines.slice(from, to).join('\n').trim();

  const story = part(PARTS.story);
  if (story && !body(story.from, story.to)) say(`的「${PARTS.story}」是空的`);

  const known = new Map(chapters.map(c => [c.id, c]));
  const arrange = part(PARTS.chapters);
  if (arrange) {
    const subs = heads('###').filter(h => h.at >= arrange.from && h.at < arrange.to);
    subs.forEach((h, k) => {
      const end = k + 1 < subs.length ? subs[k + 1].at : arrange.to;
      if (!known.has(h.name)) {
        say(`的「### ${h.name}」不是章节合同里的章 ID（${[...known.keys()].join('、')}）`);
      } else if (plan.chapterPlans.has(h.name)) {
        say(`的「### ${h.name}」出现了两次——一章一段安排`);
      } else {
        plan.chapterPlans.set(h.name, body(h.at + 1, end));
        if (!plan.chapterPlans.get(h.name)) say(`的「### ${h.name}」没有安排——这一章不涉及也写一句理由`);
      }
    });
    for (const id of known.keys()) {
      if (!plan.chapterPlans.has(id)) say(`的「${PARTS.chapters}」缺「### ${id}」`);
    }
  }

  const picks = part(PARTS.picks);
  if (picks) {
    readPicks(plan, lines, fences.filter(f => f.from >= picks.from && f.from < picks.to), known, say);
  }
  plan.problems.push(...placeholderProblems(text, `写作设计 ${rel} `));
  return plan;
}

/** 结构选择那一个 json 代码块：数组，逐项核形状，合法的登记进 `structures`。 */
function readPicks(plan, lines, fences, known, say) {
  const where = `的「${PARTS.picks}」`;
  const json = fences.filter(f => f.lang === 'json');
  if (json.length !== 1) {
    say(json.length ? `${where}有 ${json.length} 个 json 代码块——只留一个数组`
      : `${where}没有 json 代码块——没有要脚本落实的表和图就写 []`);
    return;
  }
  const [fence] = json;
  if (!fence.closed) {
    say(`${where}的代码块没有闭合`);
    return;
  }
  let items;
  try {
    items = JSON.parse(lines.slice(fence.from + 1, fence.to).join('\n'));
  } catch (e) {
    say(`${where}不是合法 JSON（${e.message}）`);
    return;
  }
  if (!Array.isArray(items)) {
    say(`${where}要是一个数组`);
    return;
  }
  items.forEach((item, k) => {
    const pick = checkPick(item, `${where}第 ${k + 1} 项`, known, say);
    if (pick) addPick(plan, { ...pick, index: k + 1 }, known, say);
  });
}

/** 一项选择的形状；不合法的报出缺在哪，返回 null。 */
function checkPick(item, where, known, say) {
  if (!item || typeof item !== 'object' || Array.isArray(item)) {
    say(`${where}不是对象`);
    return null;
  }
  const bad = [];
  const extra = Object.keys(item).filter(key => !FIELDS.includes(key));
  if (extra.length) bad.push(`有协议外的字段 ${extra.join('、')}（只认 ${FIELDS.join('、')}）`);
  const ch = known.get(item.chapter);
  if (!ch) bad.push(`chapter「${item.chapter ?? ''}」不是章节合同里的章 ID`);
  if (typeof item.at !== 'string') bad.push('at 要写成字符串：本章里的小节名，章级写空字符串');
  if (!KINDS.includes(item.kind)) bad.push(`kind 只能是 ${KINDS.join(' 或 ')}`);
  const cols = item.columns;
  if (item.kind === 'table' && !(Array.isArray(cols) && cols.length
      && cols.every(c => typeof c === 'string' && c.trim() && !c.includes('|')))) {
    bad.push('表要给 columns：非空的列名数组，列名里不带「|」');
  }
  if (item.kind === 'diagram' && cols !== undefined) bad.push('图不带 columns');
  const subs = ch?.subsections ?? [];
  if (ch?.appendix && typeof item.at === 'string' && item.at.trim()
      && !subs.some(s => normalizeHeading(s) === normalizeHeading(item.at))) {
    bad.push(`附录只有合同那几节（${subs.join('、')}），at 要落在其中一节`);
  }
  if (bad.length) {
    say(`${where}：${bad.join('；')}`);
    return null;
  }
  return { chapter: item.chapter, at: item.at.trim(), kind: item.kind,
    ...(item.kind === 'table' ? { columns: cols.map(c => c.trim()) } : {}) };
}

/**
 * 登记一项选择：同位置同主语的重复合并；同主语选了两种列、或与合同必要表对不上的，报出位置。
 */
function addPick(plan, pick, known, say) {
  const where = `「${pick.chapter}·${pick.at || '章级'}」`;
  const twin = plan.structures.find(s => s.chapter === pick.chapter
    && normalizeHeading(s.at) === normalizeHeading(pick.at) && s.kind === pick.kind
    && (pick.kind === 'diagram' || norm(s.columns[0]) === norm(pick.columns[0])));
  if (twin) {
    if (pick.kind === 'table' && twin.columns.map(norm).join('|') !== pick.columns.map(norm).join('|')) {
      say(`的「${PARTS.picks}」第 ${twin.index} 项与第 ${pick.index} 项在${where}`
        + `给「${pick.columns[0]}」选了两种列——留一种`);
    }
    return;
  }
  if (pick.kind === 'table') {
    const lost = (contractTwin(known.get(pick.chapter), pick)?.anchors ?? []).slice(1)
      .map(g => [].concat(g))
      .filter(g => !g.some(a => pick.columns.some(c => norm(c).includes(norm(a)))));
    if (lost.length) {
      say(`的「${PARTS.picks}」第 ${pick.index} 项与章节合同在${where}要求的表冲突：`
        + `这张表还要有 ${lost.map(g => `「${g[0]}」`).join('、')}`);
      return;
    }
  }
  plan.structures.push(pick);
}

/** 合同里同位置、同主语的那张必要表——作者选了列的话，由作者的列替它打底。 */
function contractTwin(ch, pick) {
  return (ch?.structure?.tables ?? []).find(t =>
    normalizeHeading(t.at ?? '') === normalizeHeading(pick.at)
    && [].concat(t.anchors?.[0] ?? []).some(a => norm(pick.columns[0]).includes(norm(a))));
}

/**
 * 这一章要核、要打底的结构 = 合同的最小必要结构 ∪ 写作设计里选定的表图。
 *
 * 选定的表按列生成：每一列是一组锚，第一列是主语。与合同同位置同主语的必要表是**同一张表**，
 * 合成一个槽位——合同的锚列在前、作者多出来的列补在后，表头用作者的列——只核一次、只打一次底。
 * 选定的图记位置；与合同那张章级图重合时记 `alsoRequired`，由合同那条核，不重复报。
 * **重合不等于没选**：选出来的项一律带 `selected`，报错、补结构起点与「不涉及」冲突都据它
 * 认出「这是作者在写作设计里定的」。
 */
export function selectedStructure(plan, chapterId) {
  const ch = (plan?.chapters ?? []).find(c => c.id === chapterId);
  const base = ch?.structure ?? {};
  const picks = (plan?.structures ?? []).filter(s => s.chapter === chapterId);
  if (!picks.length) return base;
  const h3 = [...(base.h3 ?? [])];
  const tables = (base.tables ?? []).map(t => ({ ...t }));
  const diagrams = [];
  for (const pick of picks) {
    if (pick.at && !h3.some(h => normalizeHeading(h.title) === normalizeHeading(pick.at))) {
      h3.push({ title: pick.at, selected: true });
    }
    if (pick.kind === 'diagram') {
      diagrams.push({ at: pick.at, selected: true,
        ...(!pick.at && base.diagram ? { alsoRequired: true } : {}) });
      continue;
    }
    const twin = contractTwin(ch, pick);
    const own = twin && tables.find(t => !t.selected && t.header === twin.header && t.at === twin.at);
    const slot = { header: pick.columns.join('|'), at: pick.at || undefined, seed: 'table',
      selected: true };
    if (!own) {
      tables.push({ ...slot, anchors: pick.columns.map(c => [c]) });
      continue;
    }
    const groups = (own.anchors ?? []).map(g => [].concat(g));
    const extra = pick.columns.filter(c => !groups.some(g => g.some(a => norm(c).includes(norm(a)))));
    Object.assign(own, slot, { anchors: [...groups, ...extra.map(c => [c])] });
  }
  return { ...base, h3, tables, diagrams };
}
