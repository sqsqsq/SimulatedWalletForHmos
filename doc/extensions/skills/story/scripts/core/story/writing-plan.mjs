/**
 * 写作设计 —— `AR/story-src/story-template.md` 的协议：空壳、读取、骨架解析与选定结构的唯一解释。
 *
 * 这份文件由作者在 Spec 与决策登记之后写，交付的是**表达设计**：第一次读的人按什么顺序理解
 * 这件事（阅读主线），正文将要有哪些小节、每节解决什么理解问题（`- 答：`/`- 依据：`/`- 待核：`），
 * 以及每处用什么形式承载（`形式：`）与这个形式要表达什么（`- 描述：`）。
 * **内容不在这里定**：表格的列、图里的节点与分支、列表的项目，都由写章的人按原文决定。
 *
 * 脚本在这里只做确定的事：建空壳、指出协议缺了什么、把骨架换成章节合同能消费的结构。
 * 骨架讲得合不合理、正文照没照它把问题答清，归回看与独立审查。
 *
 * skeleton、章提交、全篇 check 与回看清单读同一份解析结果。
 * 本模块不写盘、不输出 stdout；围栏按 document 的规则认，不另写 Markdown 解析。
 */
import { readText } from './context.mjs';
import {
  DIAGRAM_SYNTAXES, fenceRanges, normalizeHeading, placeholderProblems,
} from './document.mjs';
import { relFromFeature } from './sources.mjs';

//: 两个必需的二级标题。协议认名字，不管顺序，也不管前面有没有别的说明。
const PARTS = { story: '阅读主线', skeleton: '骨架' };
//: 上一版协议的两部分：读到就整份报一次，不双读。
const RETIRED_PARTS = ['章节安排', '结构选择'];
//: 形式协议的四个词。它们是协议词，不是业务分类；图种另从 DIAGRAM_SYNTAXES 派生。
const FORMS = {
  表格: { kind: 'table' },
  有序列表: { kind: 'list', ordered: true },
  无序列表: { kind: 'list', ordered: false },
  叙述: { kind: 'prose' },
};
//: 「形式：图」是任一种图；点名图种时写中文名或 mermaid 首个声明都认，点名了正文就只认那一种。
const ANY_DIAGRAM = '图';
const LINE = {
  note: /^-\s+(.+)$/, form: /^形式[:：]\s*(.*)$/,
  recheck: /^待核[:：]\s*(.+)$/, notApplicable: /^不涉及[:：]\s*(.+)$/,
  retired: /^(?:表头|图)[:：]/,
};

/** 形式清单那句话：四个协议词 + 图种，报错与空壳共用一处。 */
const formWords = () => `${Object.keys(FORMS).join(' / ')} / ${ANY_DIAGRAM}`
  + `（任一种图），或点名一种：${Object.values(DIAGRAM_SYNTAXES).map(v => v.name).join('、')}`;

/** 空壳：阅读主线一格、每章一个章 ID 与一行占位。占位写的是这一章的骨架怎么写。 */
export function writingPlanShell(contract) {
  const rows = ['# 写作设计', '', `## ${PARTS.story}`, '',
    '{{本需求最容易被误解的对象与关系是什么，读者先理解哪一件才能理解后文；'
    + '依据在哪、哪些未决限制后文}}', '', `## ${PARTS.skeleton}`, ''];
  for (const ch of contract.chapters ?? []) {
    rows.push(`### ${ch.id}`, `- {{正文章名：${ch.title}。这一章的主线一句；正文要有的每个小节写一行 #### 标题，`
      + '下面用 - 答： 写这一节解决读者的什么理解问题、- 依据： 写依据在哪、- 待核： 写还没形成结论的疑点；'
      + `要用某种形式承载就单起一行 形式：<${formWords()}>，再用 - 描述： 说明它表达的对象、关系与边界`
      + '（列、节点与项目在写章时按原文定，这里不预写）；不涉及就只写 - 不涉及：<理由>}}', '');
  }
  return rows.join('\n');
}

/**
 * 读当前写作设计 —— 协议立不立得住，一次报全。
 *
 * 只判协议：两部分在不在、每章有没有骨架、章 ID 与小节层级对不对、形式写法认不认得。
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
      + '写法见 story-write.md「二、动笔前：先设计表达」');
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

/** `形式：` 后面那个词认成什么：认不出返回 null。 */
function parseForm(value) {
  if (FORMS[value]) return { ...FORMS[value] };
  if (value === ANY_DIAGRAM) return { kind: 'diagram' };
  const syntax = Object.keys(DIAGRAM_SYNTAXES)
    .find(key => [DIAGRAM_SYNTAXES[key].name, ...DIAGRAM_SYNTAXES[key].heads].includes(value));
  return syntax ? { kind: 'diagram', syntax } : null;
}

/** `## 骨架` 这一部分：逐行归到章与小节，缺口一次报全，再把形式交给 `addPick`。 */
function readSkeleton(plan, lines, range, fenced, say) {
  const known = new Map(plan.chapters.map(c => [c.id, c]));
  const blank = () => ({ notes: [], forms: [], sections: [] });
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
      // 重名只在同一个父节下算重名：两个 #### 各自的 ##### 同名是两处不同的位置
      const peers = head[1].length === 4 ? ch.sections : (parent?.sections ?? []);
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
      if (LINE.form.test(note)) {
        // 写成说明行的形式声明脚本不接管：说一次，别让作者以为已经定了
        say(`${where()}的「- ${note}」：形式要单起一行写 形式：<类型>，不带「- 」`);
        continue;
      }
      target.notes.push(note);
      const open = LINE.recheck.exec(note);
      if (open) plan.rechecks.push({ chapter: ch.id, at: node?.title ?? '', text: open[1].trim() });
      const skip = !node && LINE.notApplicable.exec(note);
      if (skip) ch.notApplicable = skip[1].trim();
    } else if ((m = LINE.form.exec(line))) {
      const value = m[1].trim();
      const form = value ? parseForm(value) : null;
      if (!form) say(`${where()}的「形式：${value || '（空）'}」不认识——写 ${formWords()}`);
      else target.forms.push(form);
    } else if (LINE.retired.test(line)) {
      say(`${where()}的「${line.slice(0, 24)}」是上一版写法——改成一行 形式：<类型>`
        + `（${formWords()}），再用 - 描述： 说明它表达什么；列与节点在写章时定`);
    } else {
      say(`${where()}有一行不是骨架写法：「${line.slice(0, 30)}」——骨架里只写 - 说明行、形式： 与 ####、##### 标题`);
    }
  }
  for (const id of known.keys()) {
    if (!plan.skeletons.has(id)) say(`的「## ${PARTS.skeleton}」缺「### ${id}」`);
  }
  for (const sk of plan.skeletons.values()) {
    const listed = sk.sections.length + sk.forms.length;
    if (!listed && !sk.notes.length) say(`的「### ${sk.id}」没有骨架——本章不涉及也写一行 - 不涉及：<理由>`);
    if (sk.notApplicable !== null && listed) say(`的「### ${sk.id}」写了不涉及，却还留着小节或形式——二选一`);
    const contractCh = known.get(sk.id);
    const subs = contractCh.subsections ?? [];
    for (const s of contractCh.appendix ? sk.sections : []) {
      if (!same(subs.map(title => ({ title })), s.title)) {
        say(`的「### ${sk.id}」里「#### ${s.title}」不在附录里——附录只有合同那几节（${subs.join('、')}）`);
      }
    }
    const each = (n, at, under) => n.forms.forEach(form => addPick(plan, {
      chapter: sk.id, at, ...(under ? { under } : {}), ...form,
    }));
    each(sk, '', '');
    for (const s of sk.sections) {
      each(s, s.title, '');
      s.sections.forEach(c => each(c, s.title, c.title));
    }
  }
}

/**
 * 登记一项形式：同位置同形式合并，只留一份要求。
 *
 * 同一位置写了通用图与具名图时留具名的那项——它更具体，缺口只报一次；
 * 两种不同的具名图是两项要求，各自都要有。挂在 `#####` 小节下的形式记在它的 `####` 里（`at`），
 * `under` 说它在那一节的哪个子节。
 */
function addPick(plan, pick) {
  const same = (a, b) => normalizeHeading(a ?? '') === normalizeHeading(b ?? '');
  const twins = plan.structures.filter(s => s.chapter === pick.chapter && same(s.at, pick.at)
    && same(s.under, pick.under) && s.kind === pick.kind);
  if (pick.kind === 'diagram') {
    if (twins.some(t => (t.syntax ?? '') === (pick.syntax ?? ''))) return;
    if (!pick.syntax && twins.length) return;                    // 已有具名图，通用图被它接替
    const generic = twins.find(t => !t.syntax);
    if (generic) {
      generic.syntax = pick.syntax;                              // 具名的接替先写的通用图
      return;
    }
  } else if (twins.some(t => t.ordered === pick.ordered)) {
    return;
  }
  plan.structures.push(pick);
}

/**
 * 这一章要核、要打底的结构 = 合同的最小必要结构 ∪ 写作设计选定的形式。
 *
 * 骨架的 `####` 小节进 `h3`、`#####` 进 `h4`（都要在正文里），`skeleton` 原样带上给草稿铺说明行。
 * **表的列不再由模板定**：模板选表格只要求那个位置真有一张表，列由写章的人按原文决定；
 * 合同自带的必要表照旧按锚列核（那是既有交付合同，不是模板提前定列）。
 * 图记位置与点名的类型；与合同那张章级图重合时记 `alsoRequired`，有没有图由合同那条核。
 * 叙述只进草稿指引，不进存在性检查。
 * **重合不等于没选**：骨架来的项一律带 `selected`，报错与补结构起点据它认出「这是作者定的」。
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
  const diagrams = [];
  const forms = [];
  for (const pick of picks) {
    addH3(pick.at);
    const place = { at: pick.at, ...(pick.under ? { under: pick.under } : {}) };
    if (pick.kind === 'diagram') {
      diagrams.push({ ...place,
        selected: true,
        ...(pick.syntax ? { syntax: pick.syntax } : {}),
        ...(!pick.at && base.diagram ? { alsoRequired: true } : {}) });
    } else if (pick.kind !== 'prose') {
      forms.push({ ...place, kind: pick.kind, selected: true,
        ...(pick.kind === 'list' ? { ordered: pick.ordered } : {}) });
    }
  }
  const key = (d) => `${normalizeHeading(d.at)}|${normalizeHeading(d.under ?? '')}`;
  const typed = new Set(diagrams.filter(d => d.syntax).map(key));
  return { ...base, h3, h4, skeleton, forms,
    diagrams: diagrams.filter(d => d.syntax || !typed.has(key(d))) };
}
