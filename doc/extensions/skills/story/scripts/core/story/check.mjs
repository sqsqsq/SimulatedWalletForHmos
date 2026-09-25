/**
 * 全篇 check 的调度与归组 —— 这一份 story 能不能交出去。
 *
 * 这里只做三件事：把全篇读一遍（章序、大标题、验收编号这类**跨章才判得了**的事）、
 * 按职责去各模块要问题、把问题按判据类分组打印。逐域的判据一条也不在这里实现：
 * 附录的归附录、图片的归图片、来源的归来源、章内的归 chapter——同一个错由两处判，
 * 作者会收到两条说法不同的报错。
 *
 * 离线模式（`--offline`，仲裁锚）：没有工程上下文，依赖材料与清单的判项一条不判，
 * 不依赖的照跑。走的是**同一个函数**，不是另写一套——另写一套就会与生产链漂移。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { chapterProblems } from './chapter.mjs';
import { readWritingPlan, selectedStructure } from './writing-plan.mjs';
import {
  appendixChapter, appendixStructureProblems, appendixZoneProblems,
} from './appendix.mjs';
import {
  activeKnowledgeEntries, fail, ledgerDigestProblems, readText, requireLedgers,
  strayFileProblems,
} from './context.mjs';
import { deliveryNextSteps, deliveryProblems } from './delivery.mjs';
import {
  EMPTY_SECTION_TEXT, parseChapter, placeholderProblems, storySections, tableCells, zonesByLine,
} from './document.mjs';
import { carriedDiagramProblems, imageProblems } from './images.mjs';
import { decisionProblems, redactReviewExemptZones, reviewFormProblems } from './review.mjs';
import { materialListProblems, redactMaterialLinks, sourceProblems } from './sources.mjs';
import {
  formatHits, scanBannedTerms, scanBrokenImages, scanLanguageRedline, scanLocalPaths,
} from './language.mjs';

function groupedProblems(problems, marks) {
  // 第一个戳之前也可能有报错（判据类之外的前置校验），给它一个兜底类，
  // 这样下面一个循环就覆盖全部，不会有谁掉出去。
  const bounds = [{ from: 0, label: '其它' }]
    .concat(marks.filter(m => m.from < problems.length));
  const out = [];
  for (let i = 0; i < bounds.length; i += 1) {
    const from = bounds[i].from;
    const to = i + 1 < bounds.length ? bounds[i + 1].from : problems.length;
    if (to <= from) continue;                       // 这一类这次没报错
    out.push({ label: bounds[i].label, items: problems.slice(from, to) });
  }
  return out;
}

export function cmdCheck(ctx) {
  // 起步先判台账在不在：删掉一件再跑，后面每一条判据都只是「依据不全」的余波。
  requireLedgers(ctx);
  const problems = [];
  // 判据类的分组戳：只影响输出怎么排，不影响判定。
  const marks = [];
  const mark = (label) => marks.push({ from: problems.length, label });
  // 记一笔但不拦：定稿之后材料继续演化是正常的，读者该知道，但它不是错。
  const notes = [];
  // 离线模式（仲裁锚）：没有工程上下文，依赖材料与清单的判项一条不判，
  // 不依赖的照跑——同一个函数，不是另写一套。
  const storyText = readText(ctx.storyPath);
  if (storyText === null) fail(`读不到 ${ctx.storyPath}`);

  const sections = storySections(storyText);
  // 章正文按标题索引：非占位那条按章取正文。
  const sectionText = new Map(sections.map(s2 => [s2.title, s2.text]));
  // **一章解析一次**：围栏、小节、表头由 document 扫一遍，下面的判据读同一份结果。
  // 各判据自己切文的话，同一章在一次 check 里会被切上七八遍，而每一处对
  // 「围栏里的算不算」「小节到哪结束」都有自己的一份答案。
  const parsed = new Map();
  const viewOf = (title) => {
    if (!parsed.has(title)) parsed.set(title, parseChapter(sectionText.get(title) ?? ''));
    return parsed.get(title);
  };
  const titles = sections.map(s2 => s2.title);
  const want = ctx.contract.chapters.map(c => c.title);

  mark('⓪a 声明的来源都在');
  if (!ctx.offline) {
    const out = sourceProblems(ctx);
    problems.push(...out.problems);
    notes.push(...out.notes);
  }

  mark('⓪b 台账没在登记之后被换过');
  if (!ctx.offline) problems.push(...ledgerDigestProblems(ctx));

  mark('⓪c 写作设计');
  // 章是照写作设计写的：设计读不了，下面按章核的选定结构也就无从谈起。
  // 离线仲裁锚只有一份文档，没有需求工作区——不假造设计，也不以它缺席拒绝那份文档。
  const plan = ctx.offline ? null : readWritingPlan(ctx);
  if (plan) problems.push(...plan.problems);

  mark('① 章标题与顺序');
  // ① 章标题与顺序 = 合同（章数由合同定，这里不写死）；空节恰为「本需求不涉及。」
  if (titles.join(String.fromCharCode(10)) !== want.join(String.fromCharCode(10))) {
    const missing = want.filter(t => !titles.includes(t));
    const extra = titles.filter(t => !want.includes(t));
    problems.push(`章节标题与合同不一致：${missing.length ? `缺 ${missing.join('、')}` : ''}`
      + `${extra.length ? ` 多 ${extra.join('、')}` : ''}`
      + `${!missing.length && !extra.length ? '（顺序不对）' : ''}`);
  }
  for (const sec of sections) {
    const body = sec.text.trim();
    if (!body) problems.push(`「${sec.title}」是空节——确实不涉及就写「${EMPTY_SECTION_TEXT}」一句`);
  }

  mark('①b 大标题带需求编号');
  // ①b 大标题带需求编号：归档件离开这个仓库之后，编号是它与需求系统之间唯一的绳子。
  //
  // 在线时比对的是本 feature 的编号；离线只有一份 story、不知道编号，这一类不判。
  const h1 = String(storyText).split(/\r?\n/).find(l => /^#\s+\S/.test(l.trim()));
  const h1Text = h1 ? h1.trim().replace(/^#\s+/, '') : '';
  if (!h1Text) {
    problems.push('没有大标题——归档件的第一行是 `# <需求编号> <需求名称>`');
  } else if (ctx.args.feature) {
    if (!h1Text.includes(ctx.args.feature)) {
      problems.push(`大标题缺需求编号：写成 \`# ${ctx.args.feature} <需求名称>\``
        + '——归档件流转出去之后，读者靠这个编号回到需求系统');
    }
  }

  mark('③ 验收编号落在验收章');
  // ③ 验收编号的**全集**：哪个编号出现过、它在不在验收章。这一条要读全篇，
  //    留在这里；**仓内工作编号那一条不在这里判**——它是章内的事，由 chapterProblems
  //    一处判（⑪），那边还会把画图围栏内部挖掉。两处各扫一遍的话，搬来的图会被这里报出来，
  //    而作者在那边刚被告知不用改。
  //
  // 合同里的形态正则编译一次，坏的当场报出来：写错一条就静默不判的话，门禁全绿。
  problems.push(...(ctx.idShapes?.problems ?? []));
  const acceptanceSec = sections.find(s => s.title.includes('验收'));
  for (const re of ctx.idShapes?.keep ?? []) {
    const inStory = new Set([...storyText.matchAll(re)].map(m => m[0]));
    if (!inStory.size) continue;
    if (!acceptanceSec) { problems.push('story 里有验收编号，却没有「验收」章'); continue; }
    const missed = [...inStory].filter(id => !acceptanceSec.text.includes(id));
    if (missed.length) {
      problems.push(`这些验收编号没有出现在「${acceptanceSec.title}」章：${missed.join('、')}`);
    }
  }

  mark('⑤ 决策登记字段齐备');
  if (!ctx.offline) problems.push(...decisionProblems(ctx));

  mark('④ 图片身份');
  {
    const out = imageProblems(ctx, storyText);
    problems.push(...out.problems);
    notes.push(...out.notes);
  }

  mark('⑨ 归档件红线');
  // ⑨ 归档件红线：仓内路径 / 客户端禁用词 / 图片断链
  //
  // 归档件随需求上传，评审者手上没有这个仓：点不开的引用他不知道是坏的。
  // 词表在合同、判定形态在 language.mjs，这里只调。附录里由真源投影的机器区不在这里报：
  // 它没有作者，报在这里作者删掉、下一次投影又写回来——那些问题收到 ⑩b 报到真源。
  const reviewText = readText(ctx.reviewPath) ?? '';
  // 章级豁免由合同数据给（`banned_terms_exempt`）：讲发布动作的那一章里，
  // 那几个词是业务事实不是客户端文案——收缩的是作用域，不是词表。
  const bannedExempt = ctx.contract.chapters.filter(c => c.banned_terms_exempt).map(c => c.title);
  // 材料清单里的**原文链接是唯一允许仓内路径出现的位置**：读者据它把那份材料找出来。
  // 豁免只到这一节的链接语法为止——正文里的仓内路径照拦，这一节里链接之外的文字也照拦。
  const storyForPaths = redactMaterialLinks(storyText, ctx);
  // review 的禁用词作用域比别的判据窄：人工区与「上线/管控」类议题不判，
  // 见 `redactReviewExemptZones`。词表一个字没削，收的是作用域。
  const reviewForBanned = redactReviewExemptZones(reviewText, ctx);
  const storyLines = storyText.split(/\r?\n/);
  const zones = zonesByLine(storyLines);
  const zoneHits = [];
  // story 的命中按行分到投影区与作者区：投影区的留给 ⑩b，作者区的就地报
  const authored = (label, hits, what, hitOf) => (label !== 'story' ? hits : hits.filter((h) => {
    const zone = zones.get(h.line - 1);
    if (zone) zoneHits.push({ zone, line: h.line, what, hit: hitOf(h) });
    return !zone;
  }));
  for (const [label, text, bannedText] of [
    ['story', storyForPaths, storyForPaths],
    ['review', reviewText, reviewForBanned],
  ]) {
    if (!text) continue;
    for (const [what, kind, hits, hitOf] of [
      ['仓内路径', 'local', scanLocalPaths(text, ctx.projectRoot), h => h.path],
      ['客户端语境禁用词', 'banned',
        scanBannedTerms(bannedText, { exemptChapters: bannedExempt, contract: ctx.contract }), h => h.term],
      // story 的图片断链逐章判（见 ⑪，与章提交同一处）；这里只剩 review 那一份
      ['图片断链', 'image', label === 'story' ? []
        : scanBrokenImages(text, path.dirname(ctx.storyPath), fs, path), h => h.path],
    ]) {
      const own = authored(label, hits, what, hitOf);
      if (own.length) problems.push(`${label} 出现${what} ${own.length} 处：${formatHits(own, kind)}`);
    }
  }

  // 规约编号取激活清单：判据全部是数据，不猜。
  const kEntries = activeKnowledgeEntries(ctx);

  mark('⑩ 语言红线');
  // ⑩ 语言红线：工程标识、规约编号、来源括注只在主叙事（附录之外）判，文档坐标全篇判；
  //    review 只判文档坐标。类别与作用域、来源括注的词都是合同数据。
  //
  // 接口名、规约编号不是不该在归档件里——评审者要查的时候得查得到，它们的落点是附录。
  // 文档坐标不一样：指向不随归档的文件，放在哪里读者都打不开。一行一类只报一条。
  const redline = ctx.contract.language_redline ?? {};
  if (Array.isArray(redline.kinds) && redline.kinds.length) {
    const appendix = appendixChapter(ctx.contract);
    const kindOf = k => (typeof k === 'string' ? k : k?.kind);
    for (const [label, text, opts] of [
      ['story', storyForPaths, { kinds: redline.kinds, appendixTitle: appendix?.title,
        ruleIds: kEntries.map(e => e.id), sourceTags: redline.source_tags, projectRoot: ctx.projectRoot }],
      ['review', reviewText, { kinds: redline.kinds.filter(k => kindOf(k) === 'doc_coordinate'),
        projectRoot: ctx.projectRoot }],
    ]) {
      if (!text) continue;
      const own = authored(label, scanLanguageRedline(text, opts), '', h => h);
      const groups = new Map();
      for (const h of own) {
        const key = `${h.kind}|${h.hint}`;
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(h);
      }
      for (const list of groups.values()) {
        const sample = list.slice(0, 3).map(h => `${h.line} 行「${h.hits.join('」「')}」`).join('，');
        problems.push(`${label} 出现${list[0].label} ${list.length} 处（${sample}${list.length > 3 ? ' …' : ''}）`
          + `——${list[0].hint}`);
      }
    }
  }

  mark('⑩b 机器区里的红线（改真源）');
  // 机器区的内容是从真源投影来的：问题报到真源那一行，改真源、重投，作者不碰机器区。
  const byZone = new Map();
  for (const z of zoneHits) {
    const hit = typeof z.hit === 'string' ? { what: z.what, words: [z.hit] }
      : { what: z.hit.label, words: z.hit.hits };
    const raw = storyLines[z.line - 1] ?? '';
    const row = raw.trim().startsWith('|') ? tableCells(raw)[0] : raw.trim().slice(0, 30);
    if (!byZone.has(z.zone.name)) byZone.set(z.zone.name, { source: z.zone.source, items: [] });
    byZone.get(z.zone.name).items.push(`${z.line} 行${hit.what}「${hit.words.join('」「')}」（那一行：${row}）`);
  }
  for (const [name, { source, items }] of byZone) {
    problems.push(`附录「${name}」的机器区从${source}投影而来，里面有 ${items.length} 处红线：`
      + `${items.slice(0, 5).join('；')}${items.length > 5 ? ' …' : ''}`
      + `——机器区不手改：到${source}里改这几行对应的原文，再跑 \`story-build.mjs project\` 让它重投`);
  }

  mark('⑪ 章内必要项');
  // 与章提交同一个实现：单章通过而全篇报同一条（或反过来）时，
  // 作者只能把两处的差别当成运气。
  for (const ch of ctx.contract.chapters ?? []) {
    const text = sectionText.get(ch.title);
    if (text === undefined) continue;             // 章缺失由 ① 报，这里不重复
    const planned = plan ? { ...ch, structure: selectedStructure(plan, ch.id) } : ch;
    problems.push(...chapterProblems(ctx, planned, text, () => viewOf(ch.title)));
  }
  // 章之外那一段（大标题与前言）的占位符：逐章判覆盖不到它。
  problems.push(...placeholderProblems(storyText.split(/\n##\s/)[0]));

  mark('⑫ 附录结构');
  problems.push(...appendixStructureProblems(ctx, sections, viewOf));

  mark('⑫b 机器区与真源一致');
  // 附录的机器区与真源逐区逐行比——**与 project 写进去的是同一份计算**。
  // 「每条规约有行」「spec 的行不丢」都在其内：少一行就是一处差异，不必再各写一条
  // 反着解析回去的判据。
  problems.push(...appendixZoneProblems(ctx, storyText));

  mark('⑫c 材料清单');
  {
    const out = materialListProblems(ctx, storyText);
    problems.push(...out.problems);
    notes.push(...out.notes);
  }

  mark('⑫d 上游图承接');
  // 上游每张图在 story 里各有一个围栏带着它的来源标记——一图一行报缺的那张讲的是什么。
  // 离线仲裁锚没有上游文档，整类不判。
  if (!ctx.offline) problems.push(...carriedDiagramProblems(ctx, storyText));

  mark('⑬ 评审记录只含渲染语法');
  problems.push(...reviewFormProblems(reviewText, ctx.contract));

  mark('⑮ AR 根下只有交付文档');
  if (!ctx.offline) problems.push(...strayFileProblems(ctx));

  mark('⑭ 交付门');
  // ⑭ 交付门：只有 `check --deliver` 判，普通 check 恒不判。
  //
  // 两个入口同一实现，按**动作**分而不按文件在不在推断阶段：登记前与返修中跑的是
  // 普通 check，那时读者审查还没发生，判它只会得到一个恒定的「不适用」；
  // 交付（远程单上传前、本地单闭环后）跑的是 `--deliver`，那时闭环该已经成立。
  if (ctx.args.deliver) {
    const delivery = deliveryProblems(ctx);
    problems.push(...delivery.problems);
    notes.push(...delivery.notes);
  }

  if (notes.length) {
    process.stdout.write('[story-build check] 记一笔（不拦）：\n');
    notes.forEach(n => process.stdout.write(`  · ${n}\n`));
  }
  if (problems.length) {
    const groups = groupedProblems(problems, marks);
    process.stderr.write(`[story-build check] ${problems.length} 处未通过，`
      + `分属 ${groups.length} 类：\n`);
    for (const g of groups) {
      process.stderr.write(`  [${g.label}] ${g.items.length} 处\n`);
    }
    process.stderr.write('\n');
    let n = 0;
    for (const g of groups) {
      process.stderr.write(`  [${g.label}]\n`);
      for (const item of g.items) {
        n += 1;
        process.stderr.write(`  ${n}. ${item}\n`);
      }
    }
    process.exit(1);
  }
  process.stdout.write(`[story-build check] 通过：${sections.length} 章\n`);
  // 交付门通过 = 这份 story 可以交出去了。往下有两条路，**由人选**——
  // 归档送审与进入 plan 都是正当的下一步，谁先谁后取决于这个需求的排期。
  if (ctx.args.deliver) process.stdout.write(deliveryNextSteps(ctx));
}
