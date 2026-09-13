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
import { chapterProblems, placeholderProblems } from './chapter.mjs';
import {
  appendixChapter, appendixStructureProblems, specRowProblems, verdictTableProblems,
} from './appendix.mjs';
import {
  activeKnowledgeEntries, fail, ledgerDigestProblems, readText, requireLedgers,
  strayFileProblems,
} from './context.mjs';
import { deliveryNextSteps, deliveryProblems } from './delivery.mjs';
import {
  EMPTY_SECTION_TEXT, normalizeHeading, parseChapter, storySections,
} from './document.mjs';
import { carriedDiagramProblems, danglingFigures, imageProblems } from './images.mjs';
import { decisionProblems, redactReviewExemptZones, reviewFormProblems } from './review.mjs';
import { materialListProblems, redactMaterialLinks, sourceProblems } from './sources.mjs';
import {
  formatHits, scanBannedTerms, scanBrokenImages, scanDanglingRefs,
  scanLanguageRedline, scanLocalPaths,
} from '../lint-rules.mjs';

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
  // 在线时比对的是本 feature 的编号（知道答案就核答案）；离线只有一份 story，
  // 此时退一格核**形态**——首个词是编号形态即可。两条路都拦得住「标题只有需求名」。
  const h1 = String(storyText).split(/\r?\n/).find(l => /^#\s+\S/.test(l.trim()));
  const h1Text = h1 ? h1.trim().replace(/^#\s+/, '') : '';
  if (!h1Text) {
    problems.push('没有大标题——归档件的第一行是 `# <需求编号> <需求名称>`');
  } else if (ctx.args.feature) {
    if (!h1Text.includes(ctx.args.feature)) {
      problems.push(`大标题缺需求编号：写成 \`# ${ctx.args.feature} <需求名称>\``
        + '——归档件流转出去之后，读者靠这个编号回到需求系统');
    }
  } else if (!/^[A-Za-z][A-Za-z0-9-]*\d[A-Za-z0-9-]*(\s|$)/.test(h1Text)) {
    problems.push(`大标题缺需求编号：「${h1Text.slice(0, 30)}」`
      + '——第一行写成 `# <需求编号> <需求名称>`');
  }

  mark('③ 验收编号落在验收章');
  // ③ 编号形态
  for (const shape of ctx.contract.id_shapes?.drop ?? []) {
    let re;
    try { re = new RegExp(shape, 'g'); } catch { problems.push(`编号形态不是合法正则：${shape}`); continue; }
    const hits = [...storyText.matchAll(re)].map(m => m[0]);
    if (hits.length) {
      problems.push(`story 里出现了仓内工作编号：${[...new Set(hits)].slice(0, 6).join('、')}`
        + '——读者对不上这些标识，改写成事物本身的名字');
    }
  }
  const acceptanceSec = sections.find(s => s.title.includes('验收'));
  for (const shape of ctx.contract.id_shapes?.keep ?? []) {
    let re;
    try { re = new RegExp(shape, 'g'); } catch { continue; }
    const inStory = new Set([...storyText.matchAll(re)].map(m => m[0]));
    if (!inStory.size) continue;
    if (!acceptanceSec) { problems.push('story 里有验收编号，却没有「质量与验收」章'); continue; }
    const missed = [...inStory].filter(id => !acceptanceSec.text.includes(id));
    if (missed.length) {
      problems.push(`这些验收编号没有出现在「${acceptanceSec.title}」章：${missed.join('、')}`);
    }
  }

  mark('⑤ 决策登记字段齐备');
  if (!ctx.offline) problems.push(...decisionProblems(ctx));

  mark('⑦ 规约判定表');
  problems.push(...verdictTableProblems(ctx, sections, viewOf));

  mark('④ 图片身份');
  {
    const out = imageProblems(ctx, storyText);
    problems.push(...out.problems);
    notes.push(...out.notes);
  }

  mark('⑨ 归档件四红线');
  // ⑨ 归档件四红线：仓内路径 / 客户端禁用词 / 悬空引用 / 图片断链
  //
  // 归档件随需求上传，评审者手上没有这个仓：点不开的引用他不知道是坏的。
  // 词表与判定在 lint-rules.mjs（SSOT），这里只调。
  const reviewText = readText(ctx.reviewPath) ?? '';
  // 章级豁免由合同数据给（`banned_terms_exempt`）：讲发布动作的那一章里，
  // 「灰度」「回退」是业务事实不是客户端文案——收缩的是作用域，不是词表。
  const bannedExempt = ctx.contract.chapters.filter(c => c.banned_terms_exempt).map(c => c.title);
  // 材料清单里的**原文链接是唯一允许仓内路径出现的位置**：读者据它把那份材料找出来，
  // 不给链接他只知道「有一份产品需求文档」。豁免只到这一节的链接语法为止——
  // 正文里的仓内路径照拦，这一节里链接之外的文字也照拦。
  const storyForPaths = redactMaterialLinks(storyText, ctx);
  // review 的禁用词作用域比别的判据窄：人工区与「上线/管控」类议题不判，
  // 见 `redactReviewExemptZones`。词表一个字没削，收的是作用域。
  const reviewForBanned = redactReviewExemptZones(reviewText, ctx);
  for (const [label, text, bannedText] of [
    ['story', storyForPaths, storyForPaths],
    ['review', reviewText, reviewForBanned],
  ]) {
    if (!text) continue;
    for (const [what, kind, hits] of [
      ['仓内路径', 'local', scanLocalPaths(text, ctx.projectRoot)],
      ['客户端语境禁用词', 'banned',
        scanBannedTerms(bannedText, { exemptChapters: bannedExempt })],
      ['悬空引用', 'dangling', scanDanglingRefs(text, ctx.projectRoot)],
      // story 的图片断链逐章判（见 ⑪，与章提交同一处）；这里只剩 review 那一份
      ['图片断链', 'image', label === 'story' ? []
        : scanBrokenImages(text, path.dirname(ctx.storyPath), fs, path)],
    ]) {
      if (hits.length) problems.push(`${label} 出现${what} ${hits.length} 处：${formatHits(hits, kind)}`);
    }
  }

  // 规约编号取激活清单：判据全部是数据，不猜。
  const kEntries = activeKnowledgeEntries(ctx);

  mark('⑩ 语言红线');
  // ⑩ 语言红线：主叙事（附录之外）不出现工程标识、规约编号、检索措辞、
  //    来源括注、文档坐标、占位标题、AI 腔标题
  //
  // 这些东西不是不该在归档件里——接口名、规约编号评审者要查的时候得查得到。
  // 问题在于**它们不能打断面向人的主叙述**：读者顺着九章读下来，每隔两行撞见一个
  // camelCase 就得停下来判断「这是我要懂的东西吗」。附录是它们的落点。
  //
  // 判据全部是数据：作用域边界取合同里标了 appendix 的那一章，规约编号取激活清单，
  // PascalCase 标识符取材料里实际出现过的 token——**不猜**。猜的代价是把产品名
  // 判成工程标识，而作者除了删掉正确的词之外无路可走。
  const redlineKinds = ctx.contract.language_redline?.kinds;
  if (storyText && Array.isArray(redlineKinds) && redlineKinds.length) {
    const appendix = appendixChapter(ctx.contract);
    const hits = scanLanguageRedline(storyText, {
      appendixTitle: appendix?.title,
      ruleIds: kEntries.map(e => e.id),
      kinds: redlineKinds,
      harnessTerms: ctx.contract.language_redline?.harness_terms ?? [],
    });
    if (hits.length) {
      const byKind = new Map();
      for (const h of hits) {
        if (!byKind.has(h.kind)) byKind.set(h.kind, []);
        byKind.get(h.kind).push(h);
      }
      for (const [kind, list] of byKind) {
        const sample = list.slice(0, 3).map(h => `${h.line} 行「${h.hit}」`).join('，');
        problems.push(`主叙事出现${kind === 'repo_identifier' ? '工程标识' : kind} ${list.length} 处`
          + `（${sample}${list.length > 3 ? ' …' : ''}）——${list[0].hint}`);
      }
    }
  }

  mark('⑪ 章内必要项');
  // 与章提交同一个实现：单章通过而全篇报同一条（或反过来）时，
  // 作者只能把两处的差别当成运气。
  for (const ch of ctx.contract.chapters ?? []) {
    const text = sectionText.get(ch.title);
    if (text === undefined) continue;             // 章缺失由 ① 报，这里不重复
    problems.push(...chapterProblems(ctx, ch, text, () => viewOf(ch.title)));
  }
  // 章之外那一段（大标题与前言）的占位符：逐章判覆盖不到它。
  problems.push(...placeholderProblems(storyText.split(/\n##\s/)[0]));

  mark('⑫ 附录结构');
  problems.push(...appendixStructureProblems(ctx, sections, viewOf));

  mark('⑫b spec 契约不丢行');
  problems.push(...specRowProblems(ctx, sections, viewOf));
  problems.push(...carriedDiagramProblems(ctx, storyText));

  mark('⑫c 形态 lint');
  problems.push(...danglingFigures(storyText, ctx.contract));
  {
    const out = materialListProblems(ctx, storyText);
    problems.push(...out.problems);
    notes.push(...out.notes);
  }

  mark('⑬ 评审记录只含渲染语法');
  problems.push(...reviewFormProblems(reviewText));

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

/**
 * 编号由机器铺，作者只写业务名标题与图题。
 *
 * 幂等：已经对的文件重跑一个字节都不改，所以放在登记步跑第二遍也无副作用。
 */