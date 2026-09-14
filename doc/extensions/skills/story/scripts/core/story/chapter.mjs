/**
 * 一章的写前核对、落盘与接续 —— 作者每写完一章走的那一条路。
 *
 * ## 为什么核在写之前
 *
 * 坏候选写进去之后，作者手上有两份要改的东西：草稿与已经落盘的 story。核在写之前，
 * 他只改草稿；Story 与候选文件都不动，重跑一次就是。
 *
 * ## 判据只有一份
 *
 * `chapterProblems` 是本章能确定的那几条，章提交与全篇 check 同一个实现：单章通过
 * 而全篇报同一条（或反过来）时，作者只能把两处的差别当成运气。跨章的事（章序、
 * 验收编号全集、来源图全集、材料身份）不在这里——它们要读别的章才判得了。
 *
 * ## 接续只有一处
 *
 * 首屏前三行固定 NEXT / INPUT / RESULT：当前要做的具体动作、动作要读的东西、
 * 刚才实际做了什么。skeleton 首次与恢复、chapter 成功都调它，不各写一份——
 * 各写一份的结果是恢复那一条路上的提示总比正常路径旧一轮。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { chapterStructureProblems, pickedStructureNames } from './chapter-contract.mjs';
import {
  chapterSpan, DIAGRAM_LANGS, EMPTY_SECTION_TEXT, fencedLines, norm, normalizeHeading,
  parseChapter, pendingChapters, placeholderProblems, storySections,
} from './document.mjs';
import { fail, readRaw, readText, refuseIfFrozen } from './context.mjs';
import { appendixChapter, projectAppendix } from './appendix.mjs';
import { relFromFeature, sourceStatus } from './sources.mjs';
import { draftPath, GUIDE_MARK, shellArg } from './drafts.mjs';
import { scanBrokenImages } from './language.mjs';
import { readWritingPlan, selectedStructure } from './writing-plan.mjs';

/**
 * 剥掉**草稿生产者自己写的**指导行 —— 只认 `story-draft:guide` 这一个标记。
 *
 * 它们是脚手架：作者照着写，写完该留在草稿里，不进归档件。**只剥自有的那些**：
 * 作者自己写的注释、围栏里的注释示例、机器区的首尾标记、来源标记都是正文的一部分，
 * 按「像注释」通杀的话，他写下的东西会在落盘那一刻静默消失，而他不知道。
 * 围栏里的同名行也不剥：那是被引用的样例，不是给他看的指导。
 */
function stripGuidance(body) {
  const text = String(body ?? '');
  const fenced = fencedLines(text);
  return text.split(/\r?\n/)
    .filter((l, k) => fenced.has(k) || !l.trim().startsWith(`<!-- ${GUIDE_MARK}`))
    .join('\n');
}


/**
 * 开头那几行属于本章自己的标题，剥掉 —— 命令会加回 `## <章名>`。
 *
 * 作者写章文件时很自然会带上本章标题；命令再包一层，story 里就出现两行一样的标题。
 * 只剥 **H1**（它只属于骨架）与**与本章同名的 H2**；别的章级标题不剥，由下面那条拒绝。
 */
function stripOwnHeading(body, title) {
  const want = normalizeHeading(title);
  const lines = body.split(/\r?\n/);
  let i = 0;
  while (i < lines.length) {
    const line = lines[i].trim();
    if (!line) { i += 1; continue; }
    const head = /^(#{1,2})\s+(.+)$/.exec(line);
    if (!head) break;
    if (head[1] === '##' && normalizeHeading(head[2]) !== want) break;
    i += 1;
  }
  return lines.slice(i).join('\n');
}

/**
 * 候选里**围栏外**还剩的章级标题（H1/H2）—— 一个文件只放一章。
 *
 * 只看开头不够：H2 写在正文后半段时，重新切出来的「这一章」只到它为止，
 * 写前核对看不到后半段，而整段仍然落了盘——story 里于是多出一个章锚，
 * 下一次按章锚替换就切错。围栏里的标题是样例，不算。
 */
function strayHeadings(text) {
  const fenced = fencedLines(text);
  const out = [];
  text.split(/\r?\n/).forEach((line, i) => {
    if (fenced.has(i)) return;
    const head = /^(#{1,2})\s+(.+)$/.exec(line.trim());
    if (head) out.push(head[2].trim());
  });
  return out;
}

/**
 * 画图围栏内部挖空之后的正文 —— 上游那张图是原样搬来的，里头的节点名不是作者写的字。
 *
 * 仓内工作编号那一条判的是「读者对不上这个标识」，而图里的标识连同图一起来自上游：
 * 让作者去改，他只能改坏那张图，或者干脆不搬。
 */
function withoutDiagramBodies(view) {
  const lines = view.text.split(/\r?\n/);
  for (const f of view.fences ?? []) {
    if (!DIAGRAM_LANGS.has(f.lang)) continue;
    for (let i = f.from; i <= f.to && i < lines.length; i++) lines[i] = '';
  }
  return lines.join('\n');
}

/**
 * 这一章自己能确定的那几条 —— 章提交与全篇 check 共用。
 *
 * 别的章写没写、验收编号全集齐不齐、上游每张图有没有落点，都要读别的章，不在这里。
 *
 * @param {object} ctx 当前上下文
 * @param {object} chapter 章节合同里的这一章
 * @param {string} candidateBody 要落盘的这一章正文（已剥指导、附录已投影）
 * @param {Function} [getView] 取这一章的解析结果——全篇 check 传它自己那份记忆化的
 *   取法，**要用时才算**：空章根本不解析，十章的 check 不会为九个空章各切一遍文。
 *   章提交只有一章，不传，自己解析。
 * @returns {string[]}
 */
export function chapterProblems(ctx, chapter, candidateBody, getView = null) {
  const out = [];
  const body = String(candidateBody ?? '');
  if (!norm(body)) {
    out.push(`「${chapter.title}」只有标题没有正文`
      + `——本需求真的不涉及它时写「${EMPTY_SECTION_TEXT}」，那是明说过的结论；`
      + '空着分不清「判过了不涉及」与「还没写」');
    return out;
  }
  // 明说过「不涉及」的章到此为止：它没有结构可言，也没有解析的必要——
  // 空章照样解析的话，一次 check 会为九个空章各切一遍文。
  // 例外只有一种：写作设计还为这一章选着表或图，两个明确声明冲突，交作者二选一。
  if (norm(body) === norm(EMPTY_SECTION_TEXT)) {
    const picked = pickedStructureNames(chapter);
    if (picked.length) {
      out.push(`「${chapter.title}」写的是「${EMPTY_SECTION_TEXT}」，写作设计却还为它选着`
        + `${picked.join('、')}——两处说法冲突：确实不涉及，就在写作设计的结构选择里撤掉这几项；`
        + '否则按设计把这一章写出来');
    }
    return out;
  }
  const view = getView ? getView() : parseChapter(body);
  // 围栏没闭合：这一行之后的正文全被当成围栏里的东西——判据看不见它，
  // 读者那边整段变成代码块。
  for (const f of view.fences ?? []) {
    if (f.closed) continue;
    out.push(`「${chapter.title}」第 ${f.from + 1} 行的围栏没有闭合`
      + '——同种标记、不短于开启标记、标记之后到行末只有空白，才算关上');
  }
  out.push(...placeholderProblems(body, `「${chapter.title}」`));
  if (pendingChapters(body).length) {
    out.push(`「${chapter.title}」还带着待写 marker`
      + '——它是骨架给这一章留的记号，这一章的正文该把它顶掉');
  }
  out.push(...chapterStructureProblems(chapter, view));
  for (const re of ctx.idShapes?.drop ?? []) {
    const hits = [...withoutDiagramBodies(view).matchAll(re)].map(m => m[0]);
    if (!hits.length) continue;
    out.push(`「${chapter.title}」里出现了仓内工作编号：`
      + `${[...new Set(hits)].slice(0, 6).join('、')}`
      + '——读者对不上这些标识，改写成事物本身的名字');
  }
  // 图片断链：评审者手上没有这个仓，点不开的引用他不知道是坏的。
  const hits = scanBrokenImages(body, path.dirname(ctx.storyPath), fs, path);
  if (hits.length) {
    out.push(`「${chapter.title}」有 ${hits.length} 处图片断链：`
      + `${hits.slice(0, 3).map(h => h.hit ?? h.target ?? h).join('、')}`
      + '——引它在仓里的既有落盘位置，副本与改名读者都认不出来');
  }
  return out;
}

/** 同名章锚有几处 —— 两处都替不对：替前一处，后一处仍是旧的。 */
function chapterAnchors(storyText, title) {
  return storySections(storyText)
    .filter(s => normalizeHeading(s.raw) === normalizeHeading(title)).length;
}

/** 这一章在给定全文里的正文。 */
function chapterBodyIn(storyText, title) {
  const hit = storySections(storyText)
    .find(s => normalizeHeading(s.raw) === normalizeHeading(title));
  return hit ? hit.text : '';
}

/**
 * 首屏接续 —— 前三行固定 NEXT / INPUT / RESULT，长统计与记一笔放后面。
 *
 * 作者读的是第一屏：当前要做的具体动作、这个动作要读的东西、刚才实际做了什么，
 * 三样各占一行。skeleton 与 chapter 都调它，**RESULT 只写真做过的事**——
 * skeleton 不能说提交过一章。
 *
 * 写作设计还读不了时，当前动作就是写它：章是照设计写的，设计还是空壳时去写章，
 * 各章的分工只能靠上下文记忆。
 *
 * @param {{warnings?: string[], plan?: object, docs?: object[]}} [options]
 *   `plan` 是调用方这一刻读到的写作设计；`docs` 是已经取得的来源（没给就按合同现读）
 */
export function nextSteps(ctx, storyText, result, { warnings = [], plan = null, docs = null } = {}) {
  const left = pendingChapters(storyText);
  const storyRel = relFromFeature(ctx, ctx.storyPath);
  const planRel = relFromFeature(ctx, ctx.templatePath);
  const guide = 'doc/extensions/skills/story/phases/story-write.md';
  const originals = (docs ?? sourceStatus(ctx).docs).map(d => d.rel).join('、');
  const rows = [];
  if (plan?.problems.length) {
    rows.push(`NEXT: 先写整篇写作设计 ${planRel}——对照原材料、需求分析里的来源初筛、Spec 与决策登记，`
      + '写阅读主线、十章安排与结构选择；写完重跑'
      + ` node ${shellArg(ctx.scriptPath)} skeleton --feature ${shellArg(ctx.args.feature)}`
      + ` --project-root ${shellArg(ctx.projectRoot)}`);
    rows.push(`INPUT: ${planRel}；来源 ${originals}；需求分析 `
      + `${relFromFeature(ctx, path.join(ctx.srcDir, 'init-analysis.md'))}；决策登记 `
      + `${relFromFeature(ctx, ctx.decisionsPath)}；方法见 ${guide} 的「二、动笔前：先有整篇写作设计」`);
  } else if (left.length) {
    const title = left[0];
    const at = (ctx.contract.chapters ?? [])
      .findIndex(c => normalizeHeading(c.title) === normalizeHeading(title));
    const draft = draftPath(ctx, at < 0 ? 0 : at, title);
    rows.push(`NEXT: 写「${title}」（还剩 ${left.length} 章待写）`
      + '——先读写作设计里本章那一段、它的草稿头与当前已写的章，只补这一章独有的信息；'
      + `改完草稿跑 node ${shellArg(ctx.scriptPath)} chapter`
      + ` --feature ${shellArg(ctx.args.feature)} --chapter ${shellArg(title)}`
      + ` --from ${shellArg(draft)} --project-root ${shellArg(ctx.projectRoot)}`);
    rows.push(`INPUT: 本章草稿 ${relFromFeature(ctx, draft)}；${planRel} 里`
      + `「${ctx.contract.chapters[at]?.id ?? title}」那一段；当前 ${storyRel} 里已写的章；`
      + `来源 ${originals}；方法见 ${guide} 的「五、十章各自怎么组织」`);
  } else {
    rows.push('NEXT: 十章齐了——从来源核实际全文：对照原材料与来源初筛核覆盖、推演关键路径与决定、'
      + '再核组织与表达；业务结论错了改 Spec 或决策登记，解释安排改写作设计，正文改草稿再跑 chapter 提交；'
      + '全篇收口后跑 python doc/extensions/skills/story/scripts/core/story_flow.py story'
      + ` --feature ${shellArg(ctx.args.feature)} --project-root ${shellArg(ctx.projectRoot)}`);
    rows.push(`INPUT: 当前 ${storyRel} 全文；写作设计 ${planRel}；决策登记 `
      + `${relFromFeature(ctx, ctx.decisionsPath)}；来源初筛 `
      + `${relFromFeature(ctx, path.join(ctx.srcDir, 'init-analysis.md'))}；来源 ${originals}；草稿目录 `
      + `${relFromFeature(ctx, path.dirname(draftPath(ctx, 0, 'x')))}；`
      + `方法见 ${guide} 的「四、写后核对」`);
  }
  rows.push(`RESULT: ${result}`);
  for (const w of warnings) rows.push(`  记一笔：${w}`);
  return `${rows.join('\n')}\n`;
}

/**
 * 把一章的内容原子替换进 story.md —— **落盘只有这一条路**。
 *
 * 作者拿编辑工具直接改整篇时，「已完成的章一个字节没动」只是期望；经这条命令落盘，
 * 它是机械事实：替换的区间就是那一章，别处一个字节都碰不到。统稿也走它——
 * 要改第五章就替换第五章，不重新输出整篇：整篇重出是全有或全无，
 * 中途断了磁盘上什么都没有。
 *
 * 顺序：冻结守卫 → 读候选与 Story → 唯一章锚 → 剥指导 → 剥自己的标题 →
 * 附录候选在内存投影 → 写前核对 → 替换目标区 → 接续。**核对在写盘之前**：
 * 判不过时 Story 与候选文件都不变，作者改草稿重跑就是。
 */
export function cmdChapter(ctx) {
  refuseIfFrozen(ctx, 'chapter');
  const title = String(ctx.args.chapter ?? '').trim();
  if (!title) fail('缺 --chapter <章名>：要替换哪一章');
  const from = ctx.args.from;
  if (!from) fail('缺 --from <文件>：这一章的内容写在文件里，不走命令行参数——'
    + '正文里有换行、引号与 markdown，任何 shell 都会再解析一遍');
  const body = readText(path.resolve(from));
  if (body === null) fail(`读不到 ${from}`);
  if (!body.trim()) {
    fail(`${from} 是空的：空正文不是一章，本需求真的不涉及时写「${EMPTY_SECTION_TEXT}」`);
  }

  // **原样读**：这一步是按区间把原文拼回去，读进来少一个 BOM，写回去就少一个 BOM，
  // 「其余章一个字节未动」这句话随之不成立。判据那一侧仍用剥过 BOM 的读法。
  const story = readRaw(ctx.storyPath);
  if (story === null) fail('AR/story.md 不在：先跑 skeleton 建骨架，再一章一章落盘');
  const chapters = ctx.contract.chapters ?? [];
  const chapter = chapters.find(c => normalizeHeading(c.title) === normalizeHeading(title));
  if (!chapter) {
    fail(`合同里没有「${title}」这一章。章名取自章节合同：`
      + `${chapters.map(c => c.title).join('、')}`);
  }
  // 章是照写作设计写的：设计读不了就先不落盘——空壳时写下的章没有可核的依据，
  // 选定的表图也无从核对。报错把设计缺在哪一次列全，改完再提交。
  const plan = readWritingPlan(ctx);
  if (plan.problems.length) {
    fail(`写作设计还读不了，「${title}」先不落盘（${path.basename(ctx.storyPath)} 没动）：\n`
      + `${plan.problems.map(p => `  · ${p}`).join('\n')}\n`
      + `  写好它再提交；当前输入与下一步跑 node ${shellArg(ctx.scriptPath)} skeleton`
      + ` --feature ${shellArg(ctx.args.feature)} --project-root ${shellArg(ctx.projectRoot)}`);
  }
  const planned = { ...chapter, structure: selectedStructure(plan, chapter.id) };
  const anchors = chapterAnchors(story, title);
  if (!anchors) {
    fail(`story 里找不到「${title}」的章锚——骨架被改过或章名写错了。`
      + '章锚是逐章落盘的定位点，别手工改动它');
  }
  if (anchors > 1) {
    fail(`story 里有 ${anchors} 处「${title}」章锚——替换按章锚定位，只会替掉第一处，`
      + '另一处仍是旧的，而读者会读到两遍。先把重复的那一处删掉再提交');
  }
  const span = chapterSpan(story, title);
  // 先剥写给作者的说明（章头指引），再剥开头属于本章自己的 H1/同名 H2——
  // 章草稿的章头是注释行，混在任何顺序里都必须先剥干净，标题比对才认得出开头。
  const trimmed = stripOwnHeading(stripGuidance(body), title).replace(/\s+$/, '');
  if (!trimmed) fail(`${from} 除了章标题没有别的内容：这一章的正文写在标题之后`);
  // 剥完还剩章级标题，说明这个文件放了不止一章。**整份候选都要看**：
  // 只看开头的话，写在正文后半段的那个 H2 会连同它下面的正文一起落盘，
  // story 里多出一个章锚，而写前核对只看得见被重新切出来的前半章。
  const stray = strayHeadings(trimmed);
  if (stray.length) {
    fail(`${from} 里还有 ${stray.length} 个章级标题（${stray.slice(0, 3).join('、')}`
      + `${stray.length > 3 ? '…' : ''}）——一个文件只放一章：`
      + '别的章的标题落进来会多出一个章锚，下一次按章锚替换就切错了。'
      + '章内的小节用 `###`；要举带标题的例子就放进代码围栏');
  }
  let next = `${story.slice(0, span.start)}## ${title}\n\n${trimmed}\n\n${story.slice(span.end)}`;
  // 附录章 = 作者区 + 当前真源投影出的机器区。**投在写前核对之前**：那四节本就
  // 不该由他写，不投的话写前核对会因为它们空着而拦下一份合法的附录。
  if (normalizeHeading(title) === normalizeHeading(appendixChapter(ctx.contract)?.title ?? '')) {
    next = projectAppendix(ctx, next).text;
  }

  const bad = chapterProblems(ctx, planned, chapterBodyIn(next, title));
  if (bad.length) {
    process.stderr.write(`[story-build chapter] 「${title}」${bad.length} 处未通过，`
      + `${path.basename(ctx.storyPath)} 与候选文件都没动：\n`);
    bad.forEach((b, i) => process.stderr.write(`  ${i + 1}. ${b}\n`));
    process.stderr.write('  在草稿上改完，重跑这条命令。\n');
    process.exit(1);
  }
  fs.writeFileSync(ctx.storyPath, next, 'utf-8');
  // **写入到此成立。** 往下只是算接续（下一章是哪一章、草稿在哪），
  // 算不出来也不能反过来说提交失败——说失败他会把这一章重写一遍，而盘上已经是新的了。
  // 所以这一段单独兜住：只说清「已落盘」与怎么取回定位，不回滚、不诱导重交。
  try {
    process.stdout.write(nextSteps(ctx, next,
      `「${title}」已落盘（其余章一个字节未动）`, { plan }));
  } catch (e) {
    try {
      process.stderr.write(`[story-build chapter] 「${title}」**已落盘**，`
        + `接续算不出来（${e?.message ?? e}）——**不要重交这一章**。`
        + `跑 node ${shellArg(ctx.scriptPath)} skeleton`
        + ` --feature ${shellArg(ctx.args.feature)}`
        + ` --project-root ${shellArg(ctx.projectRoot)} 取回定位与草稿。
`);
    } catch { /* 输出通道全关时给不出提示；退出码仍是 0，因为写入确实成立 */ }
  }
}
