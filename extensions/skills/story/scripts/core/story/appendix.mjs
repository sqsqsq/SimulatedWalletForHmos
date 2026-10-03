/**
 * 附录 —— 已准入蓝图与冻结输入的投影、手改保护，以及附录自己的结构判据。
 *
 * 附录是全篇唯一允许出现工程标识的地方，于是它天然最容易变成倾倒区。这里管两件事：
 * 机器区**从真源重算**（不读旧 story，读旧的就成了真源加一份会漂的副本），
 * 以及作者区与机器区的分界——有人在机器区写过字就停下，不静默盖掉。
 *
 * 真源是原生读取、已准入且评审投影对得上的蓝图（契约、运行数据流、知识应用决定、开发视图与架构影响、
 * 精确明细 `story_details`），以及登记的冻结设计输入。每一节由章节合同登记的具名读取器算出，
 * 生成与核对共用同一份计算；表头与文字标签登记在合同，本文件不写业务词。
 */
import * as path from 'node:path';
import {
  chapterSpan, findByName, headingEnd, normalizeHeading, parseDocument, sectionBody, sectionNames,
  zoneBlock, zoneHandEdited, zoneLine, zoneSpan, ZONE_BEGIN, ZONE_END,
} from './document.mjs';
import { fail } from './context.mjs';
import { blueprintKnowledge } from '../../../../../hooks/shared/knowledge-application.mjs';
import { designSource } from './design-source.mjs';
import { READERS } from './appendix-readers.mjs';

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
    out.push({ zone, section, h4, source: `${reader.source}（${revision}）`, rows: reader.rows(source, def, zone, gaps) });
  };
  for (const [section, def] of Object.entries(projectionOf(ctx.contract))) {
    if (def.reader) add(section, section, null, def);
    for (const h4 of def.h4 ?? []) add(`${section}·${h4.title}`, section, h4.title, h4);
  }
  return out;
}

/**
 * 投影输入还成不成立 —— **写入侧与只读侧同一份结论**：设计来源不成立（没关联、未准入、投影对不上、
 * 冻结输入读不到）时不投也不按「期望为空」放行；蓝图里的知识应用缺判断、原文已变或落点失效，是设计待同步；
 * 蓝图有、附录却没有人读写法的结构是投影缺口，同样交设计。
 */
function appendixSourceProblems(ctx) {
  const source = designSource(ctx);
  if (source.problems.length) return source.problems;
  const { problems } = blueprintKnowledge(ctx.projectRoot, source.blueprint);
  // 投影缺口：蓝图里有、附录却没有人读写法的结构——不写空、不略过，交设计
  const gaps = [];
  appendixZones(ctx, source, gaps);
  return [...problems.map(p => `${p}——判断在设计时写进蓝图（knowledge_application），附录·规约按它投影；由设计职责在 component-design 里修订`),
    ...gaps];
}

/** 起手（`skeleton`）要的设计来源缺口：与投影、核对同一份结论。 */
export function designGaps(ctx) {
  return appendixSourceProblems(ctx);
}

/**
 * 精确明细里的专项设计（`special_design`）写在正文：逐字出现在 story 里，不在附录重复。
 */
function specialDesignProblems(ctx, storyText) {
  const source = designSource(ctx);
  const text = String(storyText ?? '').replace(/\r\n/g, '\n');
  return (source.blueprint?.story_details ?? []).filter(d => d?.kind === 'special_design')
    .filter(d => !text.includes(String(d.body ?? '').replace(/\r\n/g, '\n').trim()))
    .map(d => `蓝图精确明细 ${d.id}（${d.title ?? '专项设计'}）的正文没有逐字写进 story——专项设计在讲它的那一章原样呈现，`
      + '表达可以组织，内容不改写、不删减');
}

/**
 * 把附录的机器区投影进 story —— **投影的唯一入口**，两个时点都走它。
 *
 * ① `chapter` 落盘附录章之后：作者的草稿里只有目的句、H4 标题与材料清单，机器区由这里投出来，
 *    他登记前跑 `check` 才不会因为机器区是空的而红；
 * ② `story_flow.py story` 登记时：真源在成文期间还会变（补一条规约判断、改一个接口），
 *    以登记这一次为准。
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
  // 集合对账：合同里有的按真源重投，合同里没有的区块删掉——某一节从合同去掉或改名之后，
  // 旧区会一直挂着，而它指的真源已经没人维护了。
  const want = new Set(zones.map(z => z.zone));
  for (const line of [...lines]) {
    if (!line.startsWith(ZONE_BEGIN)) continue;
    const name = line.slice(ZONE_BEGIN.length).split(' · ')[0].trim();
    const at = want.has(name) ? null : zoneSpan(lines, name);
    if (at) lines = [...lines.slice(0, at.start), ...lines.slice(at.end)];
  }
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
  return { text: storyText.slice(0, span.start) + lines.join('\n') + storyText.slice(span.end),
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
      const rows = all.filter(l => l.startsWith('|') || /^[-*+]\s/.test(l) || /^\d+[.)]\s/.test(l));
      if (!rows.length && !notApplicableLine(body) && !all.some(l => l.startsWith(ZONE_BEGIN))) {
        problems.push(`「${appendixDef.title}·${want}」：没有表行、列表行、机器区，也没有「不涉及」结论`
          + '——附录每节的内容按表、列表、从蓝图投影的机器区或一行以「不涉及」起头的结论判');
      }
      // 有小节登记的节（技术契约）：小节按合同的节名认，机器区投在同名小节下
      const def = Object.entries(projectionOf(ctx.contract)).find(([k]) => normalizeHeading(k) === want)?.[1];
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
    const inAppendix = [...appendixSection.text.matchAll(/!\[[^\]]*\]\(([^)\s]+)/g)]
      .map(m => m[1]);
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
    const have = lines.slice(at.start + 1, at.end - 1);
    const diff = firstDiff(have, z.rows);
    if (!diff) continue;
    problems.push(`「${appendix.title}·${z.zone}」的机器区与${z.source}对不上（${diff.why}`
      + `${diff.at === null ? '' : `，第 ${diff.at + 1} 行`}）：`
      + `${diff.have === null ? '' : `盘上是「${cut(diff.have)}」，`}`
      + `${diff.want === null ? '' : `${z.source}投出来是「${cut(diff.want)}」`}`
      + `——机器区由 \`story-build project\` 从 ${z.source} 投影，内容以真源为准，手改会被下一次投影覆盖`);
  }
  problems.push(...specialDesignProblems(ctx, storyText));
  // **集合两向都核**：上面走的是合同要的那几区；盘上多出来的名字在这里报。
  // 合同里没有它，就没有真源与它比——既不受投影约束，也不是作者说明，它会长期冒充现行投影。
  const known = new Set(zones.map(z => z.zone));
  for (const name of onDisk.keys()) {
    if (known.has(name)) continue;
    problems.push(`「${appendix.title}」：机器区「${name}」不在合同的投影登记里`
      + `（登记的是 ${zones.map(z => z.zone).join('、')}）`
      + '——机器区按合同登记的名字对应真源，这一段没有真源可比，也不随投影更新；'
      + '机器标记之外是作者区');
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
