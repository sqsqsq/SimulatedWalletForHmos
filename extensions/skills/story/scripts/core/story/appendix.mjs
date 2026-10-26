/**
 * 附录 —— 当前蓝图与冻结输入的投影、手改保护、附录自己的结构判据，以及设计附件。
 *
 * 附录是全篇唯一允许出现工程标识的地方，于是它天然最容易变成倾倒区。这里管三件事：
 * 机器区**从真源重算**（不读旧 story，读旧的就成了真源加一份会漂的副本），
 * 作者区与机器区的分界——有人在机器区写过字就停下，不静默盖掉——以及设计附件 `AR/design-review.md`。
 *
 * 机器区的真源是原生读取、消费了本次输入且评审投影对得上的当前蓝图（开发视图与架构影响、精确明细 `story_details` 里的
 * 配置与埋点）。接口、数据与规约由作者按蓝图写业务摘要，完整技术契约在设计附件。
 * 每个机器区由章节合同登记的具名读取器算出，生成与核对共用同一份计算；表头与文字标签登记在合同，本文件不写业务词。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import {
  chapterSpan, findByName, headingEnd, nativeAddresses, normalizeHeading, parseDocument, sectionBody, sectionNames,
  separateMarks, zoneBlock, zoneBody, zoneHandEdited, zoneLine, zoneSpan, ZONE_BEGIN, ZONE_END,
} from './document.mjs';
import { fail, readJson, replaceFile } from './context.mjs';
import { imageLinks } from './language.mjs';
import { blueprintAddresses, blueprintKnowledge } from '../../../../../hooks/shared/knowledge-application.mjs';
import { designSource } from './design-source.mjs';
import { READERS } from './appendix-readers.mjs';

//: 设计附件：本次蓝图原生评审投影的逐字节副本，随 Story 与 Review 一起交付
const DESIGN_REVIEW = ['AR', 'design-review.md'];
const sha256 = data => crypto.createHash('sha256').update(data).digest('hex');

/** 附录那一章（合同里标了 `appendix` 的那个）。没有就返回 null。 */
export function appendixChapter(contract) {
  return (contract.chapters ?? []).find(c => c.appendix) ?? null;
}

/**
 * 附录的投影登记（合同 `projection.sections`）：哪几节有机器区、各由哪个读取器算、表头与标签。
 * 节名、读取器与表头都是合同数据：改附录的组织只改合同。
 */
function projectionOf(contract) {
  return appendixChapter(contract)?.projection?.sections ?? {};
}

/** 一节正文里写出来的「不涉及」结论（以「不涉及」起头的一行）——它也是结论，评审者要看到；没有返回 null。 */
function notApplicableLine(text) {
  return String(text ?? '').split(/\r?\n/).map(l => l.trim())
    .find(l => /^不涉及\S/.test(l)) ?? null;
}

/** 附录里承载材料清单的那一节的名字（合同数据，本文件不写业务词）。 */
export function materialSubsectionName(contract) {
  return (appendixChapter(contract)?.subsections ?? []).find(n => n.includes('材料')) ?? null;
}

/**
 * 附录的全部机器区 —— **投影与只读核对的唯一一份计算**。
 *
 * 每一项：`zone`（机器区名）、`section`（所在的 H3）、`h4`（所在的 H4，没有就挂在 H3 末尾）、
 * `source`（真源，带蓝图的 revision）、`rows`（投出来的行）。**不含任何占位**：机器区里出现「作者要填的格子」，
 * 作者填了会被下一次投影打回。
 */
function appendixZones(ctx, source, gaps = []) {
  const revision = source.ref ? `${source.ref.blueprint_id} r${source.ref.revision}` : '';
  const out = [];
  const add = (zone, section, h4, def) => {
    const reader = READERS[def.reader];
    if (!reader) fail(`章节合同附录章 projection：「${zone}」登记的读取器 ${def.reader} 不存在（可用：${Object.keys(READERS).join('、')}）`);
    out.push({ zone, section, h4, source: `${reader.source}（${revision}）`, rows: reader.rows(source, def, zone, gaps, ctx) });
  };
  for (const [section, def] of Object.entries(projectionOf(ctx.contract))) {
    if (def.reader) add(section, section, null, def);
    for (const h4 of (def.h4 ?? []).filter(h => h.reader)) add(h4.zone ?? `${section}·${h4.title}`, section, h4.title, h4);
  }
  return out;
}

/**
 * 投影输入还成不成立 —— **写入侧与只读侧同一份结论**：设计来源不成立（没关联、未准入、投影对不上、
 * 冻结输入读不到）时不投也不按「期望为空」放行；蓝图里的知识应用缺判断、原文已变或落点失效，是设计待同步；
 * 蓝图有、章节合同却没有人读写法的结构是投影适配缺口，交扩展维护。
 */
function appendixSourceProblems(ctx) {
  const source = designSource(ctx);
  if (source.problems.length) return source.problems;
  const { problems } = blueprintKnowledge(ctx.projectRoot, source.blueprint);
  // 投影适配缺口：蓝图里有、章节合同还没有人读写法的结构，并入这份结论
  const gaps = [];
  appendixZones(ctx, source, gaps);
  return [...problems.map(p => `${p}——判断在设计时写进蓝图（knowledge_application），附录·规约按它写；由设计职责在 component-design 里修订`),
    ...gaps];
}


/**
 * 附录作者写的几节（接口、数据、规约、材料取舍）在写作设计骨架里的「依据」：引用的原生地址要在当前蓝图里。
 * 摘要是否覆盖真实影响、有没有遗漏由独立审查判；这里只核写下的地址指得到对象。
 */
export function appendixBasisProblems(ctx, plan) {
  const appendix = appendixChapter(ctx.contract);
  const skeleton = appendix ? plan?.skeletons?.get(appendix.id) : null;
  const source = designSource(ctx);
  if (!skeleton || !source.blueprint) return [];
  const known = blueprintAddresses(ctx.projectRoot, source.blueprint);
  const nodes = [skeleton, ...skeleton.sections.flatMap(s => [s, ...s.sections])];
  const cited = nodes.flatMap(n => n.notes.filter(note => /^依据[:：]/.test(note))
    .flatMap(note => nativeAddresses(note).map(ref => ({ at: n.title ?? appendix.id, ref }))));
  return cited.filter(c => !known.has(c.ref)).map(c => `写作设计「${c.at}」的依据引用了 ${c.ref}，`
    + `当前蓝图 ${source.ref?.blueprint_id} r${source.ref?.revision} 里没有这个对象——依据写当前蓝图里实际的原生地址`);
}

/** 起手（`skeleton`）要的设计来源缺口：与投影、核对同一份结论。 */
export function designGaps(ctx) {
  return appendixSourceProblems(ctx);
}

/**
 * 把附录的机器区投影进 story —— **投影的唯一入口**，两个时点都走它。
 *
 * ① `chapter` 落盘附录章之后：作者的草稿里只有目的句、H4 标题与作者写的几节，机器区由这里投出来，
 *    他登记前跑 `check` 才不会因为机器区是空的而红；
 * ② `story-build review --action prepare` 定稿时：真源在成文期间还会变（补一条配置明细、蓝图换版），
 *    以定稿这一次为准。
 *
 * 每次都从当前真源重算，不读旧 story：读旧的就成了「真源 + 一份会漂移的副本」。
 * 机器区紧跟在它的 H4 标题下（没有 H4 的挂在该节末尾）；H4 标题与区后的说明归作者，这里不碰。
 */
export function projectAppendix(ctx, storyText) {
  const appendix = appendixChapter(ctx.contract);
  if (!appendix) return { text: storyText, zones: 0 };
  const span = chapterSpan(storyText, appendix.title);
  if (!span) return { text: storyText, zones: 0 };
  // **输入不成立就一个字节都不写**：投影会按「这一节现在没内容」把旧机器区删掉，
  // 而真源不成立时那不是「没内容」——删完盘上看起来合法，读者与评审者都看不出少了什么。
  // 与只读侧同一份结论（`appendixSourceProblems`），不各判一次。
  const badSource = appendixSourceProblems(ctx);
  if (badSource.length) {
    fail(`附录的机器区投不出来，${path.basename(ctx.storyPath)} 未改动：\n`
      + badSource.map((b, k) => `  ${k + 1}. ${b}`).join('\n'));
  }
  const zones = appendixZones(ctx, designSource(ctx));
  let lines = storyText.slice(span.start, span.end).split(/\r?\n/);
  let count = 0;
  // 合同里没有的机器区来自旧版本的章合同：这份 Story 属于旧版在途单，不在这里删改
  const want = new Set(zones.map(z => z.zone));
  const stale = [...new Set(lines.filter(l => l.startsWith(ZONE_BEGIN))
    .map(l => l.slice(ZONE_BEGIN.length).split(' · ')[0].trim()).filter(name => !want.has(name)))];
  if (stale.length) fail(`附录里有本版章节合同不再投影的机器区（${stale.join('、')}），${path.basename(ctx.storyPath)} 未改动：`
    + '这份 Story 来自旧版本，在旧版本里收口，或用本版重新 `/story init` 起单');
  for (const z of zones) {
    const at0 = zoneSpan(lines, z.zone);
    // 真源那一节现在什么都没有了（蓝图里这类对象没有了）：
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
  return { text: storyText.slice(0, span.start) + separateMarks(lines).join('\n') + storyText.slice(span.end),
    zones: count };
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
      const def = Object.entries(projectionOf(ctx.contract)).find(([k]) => normalizeHeading(k) === want)?.[1];
      // 作者写的节（合同里这一节或它的某个小节没有读取器）收自然段、表与列表；只有机器区的节按投影或「不涉及」判
      const authored = !def || !def.reader && (!(def.h4 ?? []).length || (def.h4 ?? []).some(h => !h.reader));
      const zoned = all.some(l => l.startsWith(ZONE_BEGIN));
      const written = all.some(l => l && !l.startsWith('#') && !l.startsWith(ZONE_BEGIN) && l !== ZONE_END);
      const rows = all.some(l => l.startsWith('|') || /^[-*+]\s/.test(l) || /^\d+[.)]\s/.test(l));
      if (authored ? !written && !zoned : !zoned && !rows && !notApplicableLine(body)) {
        problems.push(`「${appendixDef.title}·${want}」：${authored ? '没有内容' : '没有机器区，也没有「不涉及」结论'}`
          + (authored ? '——这一节由作者按蓝图写，段落、表或列表都可以；本需求不涉及时写一行「不涉及：<依据>」'
            : '——这一节由 `story-build project` 从真源投影；真源里没有这类对象时写一行以「不涉及」起头的结论'));
      }
      // 有小节登记的节（技术契约）：小节按合同的节名认，机器区投在同名小节下
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
    const inAppendix = appendixSection.text.split(/\r?\n/).flatMap(line => imageLinks(line).images)
      .map(img => img.target);
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
  // **投影输入不成立时不往下比**：那时「期望是空的」与「真源不成立」同形，
  // 按空期望放行会让缺一整节的附录静默通过。写入侧拒绝的也是这同一份结论。
  const badSource = appendixSourceProblems(ctx);
  if (badSource.length) {
    problems.push(...badSource);
    return problems;
  }
  const onDisk = zonesOnDisk(lines, problems, appendix.title);
  const zones = appendixZones(ctx, designSource(ctx));
  for (const z of zones) {
    const at = onDisk.get(z.zone);
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
    const have = zoneBody(lines, at);
    const diff = firstDiff(have, z.rows);
    if (!diff) continue;
    problems.push(`「${appendix.title}·${z.zone}」的机器区与${z.source}对不上（${diff.why}`
      + `${diff.at === null ? '' : `，第 ${diff.at + 1} 行`}）：`
      + `${diff.have === null ? '' : `盘上是「${cut(diff.have)}」，`}`
      + `${diff.want === null ? '' : `${z.source}投出来是「${cut(diff.want)}」`}`
      + `——机器区从 ${z.source} 投影，内容以真源为准，手改会被下一次投影覆盖：改真源后跑 \`story_flow.py story\` 登记（它重投附录并全篇检查）；只想先看投影结果用 \`story-build project\``);
  }
  // **集合两向都核**：上面走的是合同要的那几区；盘上多出来的名字在这里报。
  // 合同里没有它，就没有真源与它比：它来自旧版本的章合同，或是手写的标记。
  const known = new Set(zones.map(z => z.zone));
  for (const name of onDisk.keys()) {
    if (known.has(name)) continue;
    problems.push(`「${appendix.title}」：机器区「${name}」不在本版章节合同的投影登记里`
      + `（登记的是 ${zones.map(z => z.zone).join('、')}）`
      + '——旧版本的 Story 在旧版本里收口，或用本版重新 `/story init` 起单；手写的标记删掉，内容写在机器标记之外');
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

/**
 * 盘上的设计附件是不是本扩展上次生成的那一份：准备记录、当前 update 的完成点与成文登记里记过的摘要。
 * 三处都是既有的所有权记录；与其中任一相符就是机器产物，可以按当前投影重写。
 */
function knownDesignReview(ctx) {
  const rel = DESIGN_REVIEW.join('/');
  const known = new Set();
  const prepared = readJson(path.join(ctx.srcDir, 'review', 'prepared.json'), null);
  if (prepared?.design_review_sha256) known.add(prepared.design_review_sha256);
  const flow = readJson(ctx.flowPath, null);
  if (flow?.story_basis?.files?.[rel]) known.add(flow.story_basis.files[rel]);
  const open = flow?.update?.open;
  const record = open ? readJson(path.join(ctx.srcDir, 'updates', open, 'record.json'), null) : null;
  if (record?.owned_after?.[rel]) known.add(record.owned_after[rel]);
  return known;
}

/**
 * 定稿时写设计附件 `AR/design-review.md`：复制当前蓝图的原生评审投影，字节相同。
 *
 * 设计来源不成立时不写（调用方在这之前已经按同一份结论停下）。盘上已有的附件与当前投影不同、
 * 又不是上次生成的那一份，就是有人改过：停下不盖，修改回蓝图。成功后把写下的摘要记进 `ctx`，准备记录据它认所有权。
 */
export function attachDesignReview(ctx) {
  const source = designSource(ctx);
  if (source.problems.length || !source.projection) {
    fail(`设计附件写不出来：\n  · ${source.problems.join('\n  · ') || '原生评审投影的位置读不到'}`);
  }
  const bytes = fs.readFileSync(path.join(ctx.projectRoot, ...source.projection.split('/')));
  const target = path.join(ctx.featureRoot, ...DESIGN_REVIEW);
  const now = fs.existsSync(target) ? fs.readFileSync(target) : null;
  if (now && !now.equals(bytes)) {
    if (!knownDesignReview(ctx).has(sha256(now))) {
      fail(`${DESIGN_REVIEW.join('/')} 与当前原生评审投影 ${source.projection} 不同，也不是上次生成的那一份：盘上这份被改过，未覆盖。`
        + '它是原生投影的副本，设计要改回蓝图修订；把这份里的改动交回它的责任处之后删掉它，再跑 prepare 重新生成');
    }
  }
  if (!now || !now.equals(bytes)) replaceFile(target, bytes);
  ctx.designReviewSha256 = sha256(bytes);
}

/** 交付前核设计附件：等于当前蓝图的原生评审投影。 */
export function designReviewProblems(ctx) {
  const source = designSource(ctx);
  if (source.problems.length || !source.projection) return [];
  const target = path.join(ctx.featureRoot, ...DESIGN_REVIEW);
  const want = fs.readFileSync(path.join(ctx.projectRoot, ...source.projection.split('/')));
  const have = fs.existsSync(target) ? fs.readFileSync(target) : null;
  if (have?.equals(want)) return [];
  return [`${DESIGN_REVIEW.join('/')} ${have ? '与' : '不在，'}当前蓝图的原生评审投影 ${source.projection}${have ? ' 不同' : ''}`
    + '——设计附件在 `story-build review --action prepare` 定稿时按当前投影生成，重新 prepare、审查并登记'];
}
