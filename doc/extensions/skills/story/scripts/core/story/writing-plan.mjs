/**
 * 写作设计 —— `AR/story-src/story-template.md` 的协议：空壳、读取、骨架解析与选定结构的唯一解释。
 *
 * 这份文件由作者在 Spec 与决策登记之后写：第一次读的人按什么顺序理解这件事（阅读主线），
 * 以及正文将要有的骨架——每章一个 `### <章 ID>`，下面是 `####`/`#####` 小节、每节要答什么
 * （`- ` 说明行，`待核：` 留给回看）、要一张什么表（`表头：`）或图（`图：`）。
 * 脚本在这里只做确定的事：建空壳、指出协议缺了什么、把骨架换成章节合同能消费的结构。
 * 骨架讲得合不合理、正文照没照它把问题答清，归回看与独立审查。
 *
 * skeleton、章提交、全篇 check 与回看清单读同一份解析结果。
 * 本模块不写盘、不输出 stdout；围栏按 document 的规则认，不另写 Markdown 解析。
 */
import { readText } from './context.mjs';
import {
  DIAGRAM_SYNTAXES, fenceRanges, norm, normalizeHeading, placeholderProblems,
} from './document.mjs';
import { relFromFeature } from './sources.mjs';

//: 两个必需的二级标题。协议认名字，不管顺序，也不管前面有没有别的说明。
const PARTS = { story: '阅读主线', skeleton: '骨架' };
//: 上一版协议的两部分：读到就整份报一次，不双读。
const RETIRED_PARTS = ['章节安排', '结构选择'];
//: 「图：图」是任一种图；其余只认合同能核的具名类型（写键名或中文名都认）。
const ANY_DIAGRAM = '图';
const LINE = {
  note: /^-\s+(.+)$/, table: /^表头[:：]\s*(.*)$/, diagram: /^图[:：]\s*(.*)$/,
  recheck: /^待核[:：]\s*(.+)$/, notApplicable: /^不涉及[:：]\s*(.+)$/,
};

/** 空壳：阅读主线一格、每章一个章 ID 与一行占位。占位写的是这一章的骨架怎么写。 */
export function writingPlanShell(contract) {
  const rows = ['# 写作设计', '', `## ${PARTS.story}`, '',
    '{{第一次读这份需求的人按什么顺序理解它：哪些参与方、对象与关系要先讲，'
    + '已定决定的依据在哪，哪些未决限制后面的叙述}}', '', `## ${PARTS.skeleton}`, ''];
  for (const ch of contract.chapters ?? []) {
    rows.push(`### ${ch.id}`, `- {{「${ch.title}」的主线一句；正文要有的每个小节写一行 #### 标题，`
      + '下面用 - 答：/ - 依据：/ - 待核：写这一节要回答什么，要表写 表头：列 | 列，'
      + `要图写 图：${ANY_DIAGRAM} 或 图：时序图；不涉及就只写 - 不涉及：<理由>}}`, '');
  }
  return rows.join('\n');
}

/**
 * 读当前写作设计 —— 协议立不立得住，一次报全。
 *
 * 只判协议：两部分在不在、每章有没有骨架、章 ID 与小节层级对不对、表头与图的写法。
 * 不设骨架的深度、小节数或字数门槛：按字面门槛判，作者只会照着门槛凑。
 *
 * @returns {{text: string|null, chapters: object[], skeletons: Map<string, object>,
 *   structures: object[], rechecks: {chapter, at, text}[], problems: string[]}}
 */
export function readWritingPlan(ctx) {
  const chapters = ctx.contract.chapters ?? [];
  const plan = { text: null, chapters, skeletons: new Map(), structures: [], rechecks: [], problems: [] };
  const rel = relFromFeature(ctx, ctx.templatePath);
  const say = (msg) => plan.problems.push(`写作设计 ${rel} ${msg}`);
  const text = readText(ctx.templatePath);
  if (text === null || !text.trim()) {
    say(`${text === null ? '不在' : '是空的'}——跑 skeleton 建空壳，对照原材料、需求分析里的来源初筛、`
      + 'Spec 与决策登记，把它写成本需求的阅读主线与每章骨架');
    return plan;
  }
  plan.text = text;
  const lines = text.split(/\r?\n/);
  const fenced = new Set(fenceRanges(lines).flatMap(f => lines.slice(f.from, f.to + 1).map((_, k) => f.from + k)));
  const h2 = lines.flatMap((line, at) => {
    const hit = !fenced.has(at) && /^##\s+(.+?)\s*$/.exec(line);
    return hit ? [{ name: normalizeHeading(hit[1]), at }] : [];
  });
  if (h2.some(h => RETIRED_PARTS.includes(h.name))) {
    say(`还是旧协议（「## ${RETIRED_PARTS.join('」「## ')}」）——按骨架协议重写：\`## ${PARTS.story}\` 写阅读主线，`
      + `\`## ${PARTS.skeleton}\` 下每章一个 \`### <章 ID>\`，正文要有的小节各写一行 \`#### 标题\`；`
      + '写法见 story-write.md「二、动笔前：先写骨架」');
    return plan;
  }
  const part = (name) => {
    const hits = h2.filter(h => h.name === name);
    if (hits.length !== 1) {
      say(hits.length ? `有 ${hits.length} 个「## ${name}」——只留一个` : `缺「## ${name}」这一部分`);
      return null;
    }
    const next = h2.find(h => h.at > hits[0].at);
    return { from: hits[0].at + 1, to: next ? next.at : lines.length };
  };
  const story = part(PARTS.story);
  if (story && !lines.slice(story.from, story.to).join('\n').trim()) say(`的「${PARTS.story}」是空的`);
  const skeleton = part(PARTS.skeleton);
  if (skeleton) readSkeleton(plan, lines, skeleton, fenced, say);
  plan.problems.push(...placeholderProblems(text, `写作设计 ${rel} `));
  return plan;
}

/** `图：` 后面那个词：任一种图返回空串，具名类型返回键名，认不出返回 undefined。 */
function diagramSyntax(value) {
  if (value === ANY_DIAGRAM) return '';
  if (Object.hasOwn(DIAGRAM_SYNTAXES, value)) return value;
  return Object.keys(DIAGRAM_SYNTAXES).find(key => DIAGRAM_SYNTAXES[key] === value);
}

/** `## 骨架` 这一部分：逐行归到章与小节，缺口一次报全，再把表图交给 `addPick`。 */
function readSkeleton(plan, lines, range, fenced, say) {
  const known = new Map(plan.chapters.map(c => [c.id, c]));
  const blank = () => ({ notes: [], tables: [], diagrams: [], sections: [] });
  const same = (list, title) => list.some(s => normalizeHeading(s.title) === normalizeHeading(title));
  let ch = null, parent = null, node = null, started = false;
  const where = () => `「### ${ch.id}${node ? `·${node.title}` : ''}」`;
  for (let at = range.from; at < range.to; at++) {
    const line = fenced.has(at) ? '' : lines[at].trim();
    if (!line) continue;
    const head = /^(#{3,5})\s+(.+?)\s*$/.exec(line);
    if (head?.[1].length === 3) {
      const id = head[2];
      started = true;
      ch = null; parent = null; node = null;
      if (!known.has(id)) say(`的「### ${id}」不是章节合同里的章 ID（${[...known.keys()].join('、')}）`);
      else if (plan.skeletons.has(id)) say(`的「### ${id}」出现了两次——一章一段骨架`);
      else plan.skeletons.set(id, (ch = { id, ...blank(), notApplicable: null }));
      continue;
    }
    if (!ch) {
      if (!started) say(`的「## ${PARTS.skeleton}」要从一行 \`### <章 ID>\` 开始`);
      started = true;
      continue;
    }
    if (head) {
      const section = { title: head[2], ...blank() };
      const peers = head[1].length === 4 ? ch.sections : ch.sections.flatMap(s => s.sections);
      if (head[1].length === 5 && !parent) {
        say(`的「### ${ch.id}」里「##### ${section.title}」前面没有 #### 小节——##### 写在某个 #### 下面`);
        node = null;
        continue;
      }
      if (same(peers, section.title)) {
        say(`的「### ${ch.id}」里「${section.title}」重复——同一级小节一个名字只用一次`);
      }
      (head[1].length === 4 ? ch.sections : parent.sections).push(section);
      if (head[1].length === 4) parent = section;
      node = section;
      continue;
    }
    const target = node ?? ch;
    let m;
    if ((m = LINE.note.exec(line))) {
      const note = m[1].trim();
      target.notes.push(note);
      const open = LINE.recheck.exec(note);
      if (open) plan.rechecks.push({ chapter: ch.id, at: node?.title ?? '', text: open[1].trim() });
      const skip = !node && LINE.notApplicable.exec(note);
      if (skip) ch.notApplicable = skip[1].trim();
    } else if ((m = LINE.table.exec(line))) {
      const cols = m[1].split('|').map(c => c.trim());
      if (cols.some(c => !c)) say(`${where()}的「表头：」要写成 列 | 列，列名不能空`);
      else target.tables.push(cols);
    } else if ((m = LINE.diagram.exec(line))) {
      const syntax = diagramSyntax(m[1].trim());
      if (syntax === undefined) {
        say(`${where()}的「图：${m[1].trim()}」不认识——写 图：${ANY_DIAGRAM}（任一种图）`
          + `${Object.values(DIAGRAM_SYNTAXES).map(v => `或 图：${v}`).join('')}`);
      } else target.diagrams.push(syntax);
    } else {
      say(`${where()}有一行不是骨架写法：「${line.slice(0, 30)}」——骨架里只写 - 说明行、表头：、图： 与 ####、##### 标题`);
    }
  }
  for (const id of known.keys()) {
    if (!plan.skeletons.has(id)) say(`的「## ${PARTS.skeleton}」缺「### ${id}」`);
  }
  for (const sk of plan.skeletons.values()) {
    const listed = sk.sections.length + sk.tables.length + sk.diagrams.length;
    if (!listed && !sk.notes.length) say(`的「### ${sk.id}」没有骨架——本章不涉及也写一行 - 不涉及：<理由>`);
    if (sk.notApplicable !== null && listed) say(`的「### ${sk.id}」写了不涉及，却还留着小节或表图——二选一`);
    const contractCh = known.get(sk.id);
    const subs = contractCh.subsections ?? [];
    for (const s of contractCh.appendix ? sk.sections : []) {
      if (!same(subs.map(title => ({ title })), s.title)) {
        say(`的「### ${sk.id}」里「#### ${s.title}」不在附录里——附录只有合同那几节（${subs.join('、')}）`);
      }
    }
    const add = (at, under, kind, value) => addPick(plan, {
      chapter: sk.id, at, ...(under ? { under } : {}), kind,
      ...(kind === 'table' ? { columns: value } : value ? { syntax: value } : {}),
    }, contractCh, say);
    const each = (n, at, under) => {
      n.tables.forEach(cols => add(at, under, 'table', cols));
      n.diagrams.forEach(syntax => add(at, under, 'diagram', syntax));
    };
    each(sk, '', '');
    for (const s of sk.sections) {
      each(s, s.title, '');
      s.sections.forEach(c => each(c, s.title, c.title));
    }
  }
}

/**
 * 登记一项表或图：同位置同主语的重复合并；同主语写了两种列、或与合同必要表对不上的，报出位置。
 * 挂在 `#####` 小节下的表图记在它的 `####` 里（`at`），`under` 只管打底放在哪。
 */
function addPick(plan, pick, ch, say) {
  const where = `「${pick.chapter}·${pick.at || '章级'}」`;
  const twin = plan.structures.find(s => s.chapter === pick.chapter
    && normalizeHeading(s.at) === normalizeHeading(pick.at) && (s.under ?? '') === (pick.under ?? '')
    && s.kind === pick.kind
    && (pick.kind === 'diagram' ? (s.syntax ?? '') === (pick.syntax ?? '')
      : norm(s.columns[0]) === norm(pick.columns[0])));
  if (twin) {
    if (pick.kind === 'table' && twin.columns.map(norm).join('|') !== pick.columns.map(norm).join('|')) {
      say(`${where}给「${pick.columns[0]}」写了两种列——留一种`);
    }
    return;
  }
  if (pick.kind === 'table') {
    const lost = (contractTwin(ch, pick)?.anchors ?? []).slice(1)
      .map(g => [].concat(g))
      .filter(g => !g.some(a => pick.columns.some(c => norm(c).includes(norm(a)))));
    if (lost.length) {
      say(`${where}的表头与章节合同要求的表冲突：这张表还要有 ${lost.map(g => `「${g[0]}」`).join('、')}`);
      return;
    }
  }
  plan.structures.push(pick);
}

/** 合同里同位置、同主语的那张必要表——骨架写了列的话，由作者的列替它打底。 */
function contractTwin(ch, pick) {
  return (ch?.structure?.tables ?? []).find(t =>
    normalizeHeading(t.at ?? '') === normalizeHeading(pick.at)
    && [].concat(t.anchors?.[0] ?? []).some(a => norm(pick.columns[0]).includes(norm(a))));
}

/**
 * 这一章要核、要打底的结构 = 合同的最小必要结构 ∪ 写作设计骨架。
 *
 * 骨架的 `####` 小节进 `h3`、`#####` 进 `h4`（都要在正文里），`skeleton` 原样带上给草稿铺说明行。
 * 骨架的表按列生成：每一列是一组锚，第一列是主语。与合同同位置同主语的必要表是**同一张表**，
 * 合成一个槽位——合同的锚列在前、作者多出来的列补在后，表头用作者的列——只核一次、只打一次底。
 * 骨架的图记位置与点名的类型；与合同那张章级图重合时记 `alsoRequired`，有没有图由合同那条核，
 * 不重复报。同一位置既有不点名的图又有点名类型的图，只留点名的那项——它更具体，缺口只报一次。
 * **重合不等于没列**：骨架来的项一律带 `selected`，报错、补结构起点与「不涉及」冲突都据它
 * 认出「这是作者在骨架里定的」。
 */
export function selectedStructure(plan, chapterId) {
  const ch = (plan?.chapters ?? []).find(c => c.id === chapterId);
  const base = ch?.structure ?? {};
  const skeleton = plan?.skeletons?.get(chapterId);
  const picks = (plan?.structures ?? []).filter(s => s.chapter === chapterId);
  if (!skeleton && !picks.length) return base;
  const h3 = [...(base.h3 ?? [])];
  const addH3 = (title) => {
    if (title && !h3.some(h => normalizeHeading(h.title) === normalizeHeading(title))) {
      h3.push({ title, selected: true });
    }
  };
  (skeleton?.sections ?? []).forEach(s => addH3(s.title));
  const h4 = (skeleton?.sections ?? []).flatMap(s => s.sections.map(c => ({ title: c.title, parent: s.title })));
  const tables = (base.tables ?? []).map(t => ({ ...t }));
  const diagrams = [];
  for (const pick of picks) {
    addH3(pick.at);
    const place = { at: pick.at, ...(pick.under ? { under: pick.under } : {}) };
    if (pick.kind === 'diagram') {
      diagrams.push({ ...place, selected: true, ...(pick.syntax ? { syntax: pick.syntax } : {}),
        ...(!pick.at && base.diagram ? { alsoRequired: true } : {}) });
      continue;
    }
    const twin = contractTwin(ch, pick);
    const own = twin && tables.find(t => !t.selected && t.header === twin.header && t.at === twin.at);
    const slot = { header: pick.columns.join('|'), ...place, at: pick.at || undefined, seed: 'table',
      selected: true };
    if (!own) {
      tables.push({ ...slot, anchors: pick.columns.map(c => [c]) });
      continue;
    }
    const groups = (own.anchors ?? []).map(g => [].concat(g));
    const extra = pick.columns.filter(c => !groups.some(g => g.some(a => norm(c).includes(norm(a)))));
    Object.assign(own, slot, { anchors: [...groups, ...extra.map(c => [c])] });
  }
  const key = (d) => `${normalizeHeading(d.at)}|${normalizeHeading(d.under ?? '')}`;
  const typed = new Set(diagrams.filter(d => d.syntax).map(key));
  return { ...base, h3, h4, tables, skeleton,
    diagrams: diagrams.filter(d => d.syntax || !typed.has(key(d))) };
}
