/**
 * spec 阶段 post_check 生命周期 hook（实例扩展 story）
 *
 * 作用：把**本阶段产物**与**宿主扩展章节**纳入 spec 阶段闭环判定。
 *   1. 本阶段三份产物：spec.md（代码要求）、AR/review.md（归档件·决策件）、
 *      AR/story.md（归档件·叙事主件，在阶段内按章写、按章落盘成文，登记态即判据）；
 *   2. §9.1 技术契约的结构完整性（core spec 模板未含，由 hooks/spec/author.md 指令驱动 AI 追加）；
 *   3. 知识判定的两个出口（§9.2 规约约束要求 / §9.3 设计模式候选登记）：独立成节、
 *      与 spec/knowledge-use.yaml 这份真源一致、命中集与 acceptance 的桥接键一致；
 *   4. 三条全文红线：禁用词 / 文档坐标 / 数值来源；
 *   5. story 前置流程契约（AR/story-src/story-flow.json）已收口且决策留痕齐备。
 *
 * 校验边界：**不校验结论真假**——文档坐标可被 AI 伪造，校验格式只给虚假的安全感。
 * 结论是否成立由 AI verifier 按名称回查源文件、以及开发的证据抽查关卡把关。
 * 数值来源也只核「标没标」这个可确定格式；标了『上游约束』的，原文所指业务量
 * 是否属实、单位换算有没有依据，由 spec overlay 的数值依据判项承担。
 *
 * 契约：stdin JSON ctx → stdout JSON result。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { CROSS_DOC_COORDINATES, scanBannedTerms, formatHits }
  from '../../skills/story/scripts/core/story/language.mjs';
import { childHeading, fenceRanges, headingEnd, parseDocument, tableCells }
  from '../../skills/story/scripts/core/story/document.mjs';
import { flowProblems, isStoryFeature, storyProduced } from '../../skills/story/scripts/core/flow/check.mjs';
import { decisionList } from '../../skills/story/scripts/core/story/review.mjs';
import { STATUS } from '../shared/evidence.mjs';
import { guard, gate } from '../shared/gate.mjs';
import { activeKnowledge, selfCheck } from '../shared/knowledge.mjs';
import { codeRequirementIds, readUse, UseError } from '../shared/knowledge-use/document.mjs';
import { coverageProblems } from '../shared/knowledge-use/validation.mjs';
import { renderZones, zoneProblems } from '../shared/knowledge-use/projection.mjs';
import { acceptanceIdRe, keptIdRe, knowledgeCriteria, readAcceptance } from '../shared/contracts.mjs';
import { reportProblems } from '../shared/verifier-report.mjs';
import { featureRoot, readJsonOrNull, readTextOrNull, relDisplay } from '../shared/paths.mjs';
import { chapterNumberProblems, chapterTemplates } from '../shared/chapters.mjs';
import { indicatorShape } from '../shared/stat-points.mjs';
import { hostAnchorProblems } from '../shared/chapters.mjs';

const SECTIONS_DOC = 'doc/extensions/skills/story/templates/spec-sections.md';
const EVIDENCE_DOC = 'doc/extensions/skills/story/reference/evidence-rules.md';

/** 提取小节正文（到下一个 ##/### 标题为止） */
//: 一份 spec 只解析一次：标题、节尾、围栏都从 `document.parseDocument` 读，不在这里另切一遍。
const parsed = new WeakMap();
function docOf(lines) {
  if (!parsed.has(lines)) parsed.set(lines, parseDocument(lines.join('\n')));
  return parsed.get(lines);
}

/** 按标题关键词定位章节（二级起任意层级；标题编号由 `normalizeHeading` 剥掉）。找不到返回 -1。 */
function findHeading(lines, titleRe) {
  const h = docOf(lines).headings.find(x => x.level >= 2 && titleRe.test(x.name));
  return h ? h.at : -1;
}

/** 在某个标题管到的范围内、它的下一级里按关键词找小节。找不到返回 -1。 */
function findChild(lines, parentIdx, titleRe) {
  const doc = docOf(lines);
  const parent = doc.headings.find(x => x.at === parentIdx);
  const h = parent && childHeading(doc, parent, titleRe);
  return h ? h.at : -1;
}

/** 某个标题管到的行区间 `[start, end)`。 */
function sectionRange(lines, startIdx) {
  if (startIdx < 0) return null;
  const doc = docOf(lines);
  const h = doc.headings.find(x => x.at === startIdx);
  return { start: startIdx, end: h ? headingEnd(doc, h) : lines.length };
}

function sectionBody(lines, headingIdx) {
  const range = sectionRange(lines, headingIdx);
  return range ? lines.slice(range.start + 1, range.end) : [];
}

function isSeparatorRow(line) {
  return /^\|[\s:|-]+\|?\s*$/.test(line);
}

/** 模板占位残留：章节模板的待填处写作「{ … }」，出现即表示该节未填写 */
function hasTemplatePlaceholder(body) {
  return body.some(l => /\{\s*[^}]*[一-龥][^}]*\}/.test(l));
}

/** 小节是否已填：存在非空表格数据行，或存在非提示性正文行（如「不涉及：…」） */
function sectionFilled(body) {
  let sawSeparator = false;
  for (const raw of body) {
    const line = raw.trim();
    if (!line || line.startsWith('>') || line.startsWith('<!--')) continue;
    if (line.startsWith('|')) {
      if (isSeparatorRow(line)) {
        sawSeparator = true;
        continue;
      }
      if (sawSeparator && tableCells(line).some(c => c.length > 0)) return true;
      continue;
    }
    sawSeparator = false; // 离开表格块，下一张表须重新经过表头+分隔行
    return true; // 非表格、非提示的正文行（如「不涉及 + 依据」）
  }
  return false;
}

/**
 * 文档坐标扫描（evidence-rules「不写的东西」）。
 * spec 是可独立审计的文件——结论不挂 `spec §x`/`SR §x`/`RR §x`/`AR §x` 这类章节坐标，
 * 核对由 verifier 按名称回查与开发的证据抽查关卡完成。
 * 坐标是作者自己写的，指向的章节里未必有那个事实；换个文档就失效，且会一路带进不含这些源文件的归档件。
 */
function scanDocCoords(text) {
  const hits = [];
  const doc = parseDocument(text);
  doc.lines.forEach((line, i) => {
    if (doc.fenced.has(i) || line.trim().startsWith('<!--')) return;
    for (const { re } of CROSS_DOC_COORDINATES) {
      for (const m of line.matchAll(re)) {
        hits.push({ line: i + 1, coord: m[0].trim(), text: line.trim().slice(0, 80) });
      }
    }
  });
  return hits;
}

/**
 * 数值来源校验（spec-sections 红线：数值必须标来源类型）。
 * 阈值/时长一类数字必须三选一标明来源：上游约束 / 本工程设定 / 平台基线。
 * 机械层只核**标没标**；标「上游约束」的是不是真有出处、换算是否成立，
 * 由 spec overlay 的语义判据回查原文承担——字面命中不等于同一个量，
 * 未命中也不等于没有真实来源，脚本裁不了这个真假。
 */
//: 序数（第 N 次、第 N 轮）是位置不是数值，不核来源。
const NUMERIC_RE = /(?<!第\s*)(\d+(?:\.\d+)?)\s*(ms|毫秒|秒|s|分钟|min|次)(?![A-Za-z])/gi;
const SOURCE_TAG_RE = /(上游约束|本工程设定|平台基线|无上游依据)/;

function scanNumericSources(text) {
  const rows = [];
  const doc = parseDocument(text);
  const lines = doc.lines;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (doc.fenced.has(i) || line.trim().startsWith('<!--') || line.trim().startsWith('>')) continue;
    const nums = [...line.matchAll(NUMERIC_RE)];
    if (nums.length === 0) continue;
    if (!SOURCE_TAG_RE.test(line)) {
      rows.push(`第 ${i + 1} 行「${nums.map(m => m[0]).join('、')}」：${line.trim().slice(0, 60)}`);
    }
  }
  return rows.length ? [`${rows.length} 处数值未标来源类型——每处三选一写明：上游约束：<文档名> / `
    + `本工程设定，无上游依据 / 平台基线。逐处：${rows.join('；')}`] : [];
}

/**
 * §8 验收标准与 acceptance.yaml 对得上 —— 可以机械核的一致性不留给语义审查。
 *
 * §8 每一行的第一个验收编号是这一行的编号，同一行里其余形如「字母+数字」的编号是它关联的功能；
 * 编号要在 acceptance.yaml 里有、关联功能与那一条的 `prd_function` 一致；同一编号只有一种含义。
 * 走 /story 的需求另核上游材料里的原始验收编号：在 §8 或 acceptance.yaml 里有对应行，或写明不承接的理由。
 */
function acceptanceAlignment(ctx, lines, featureDir, isStory) {
  const problems = [];
  const s8 = findHeading(lines, /验收标准/);
  const { acceptance, error, exists } = readAcceptance(ctx.projectRoot, ctx.feature);
  if (s8 === -1 || !exists || error) return problems;
  const entries = ['criteria', 'boundaries'].flatMap(k => (Array.isArray(acceptance?.[k]) ? acceptance[k] : []));
  const accById = new Map();
  for (const e of entries) {
    const id = String(e?.id ?? '').trim();
    if (id) accById.set(id, [...(accById.get(id) ?? []), e]);
  }
  for (const [id, list] of accById) {
    if (list.length > 1) problems.push(`同号不同义：${id} 在 acceptance.yaml 里有 ${list.length} 条——一个编号只说一件事，另起编号`);
  }
  const rows = new Map();
  for (const raw of sectionBody(lines, s8)) {
    const line = raw.trim();
    if (!line || line.startsWith('>') || /不承接/.test(line)) continue;
    const ids = [...line.matchAll(acceptanceIdRe())].map(m => m[0]);
    if (!ids.length) continue;
    const rest = line.replace(acceptanceIdRe(), ' ');
    const codes = [...rest.matchAll(/\b[A-Z]{1,3}\d+\b/g)].map(m => m[0]);
    const said = rest.replace(/\b[A-Z]{1,3}\d+\b/g, '').replace(/[-*\[\]()（）,，:：|\sx]/g, '');
    rows.set(ids[0], [...(rows.get(ids[0]) ?? []), { codes, said }]);
  }
  for (const [id, list] of rows) {
    if (new Set(list.map(r => r.said)).size > 1) {
      problems.push(`同号不同义：§8 里 ${id} 出现在 ${list.length} 行、说的不是同一件事——一个编号只说一件事`);
    }
    const acc = accById.get(id);
    if (!acc) {
      problems.push(`§8 的 ${id} 在 acceptance.yaml 里没有——验收清单以 acceptance.yaml 为全集，补一条或改 §8 的编号`);
      continue;
    }
    const want = String(acc[0]?.prd_function ?? '').split(/[\s,，、]+/).filter(Boolean).sort().join('、');
    const got = [...new Set(list[0].codes)].sort().join('、');
    if (want && got && want !== got) {
      problems.push(`${id} 的关联功能两处不一致：§8 写 ${got}，acceptance.yaml 的 prd_function 写 ${want}——以一处为准改另一处`);
    }
  }
  if (isStory) {
    const upstream = ['RR/prd.md', 'AR/design.md']
      .map(rel => readTextOrNull(path.join(featureDir, ...rel.split('/'))) ?? '').join('\n');
    const declined = lines.filter(l => /不承接/.test(l)).join('\n');
    const kept = [...new Set([...upstream.matchAll(keptIdRe())].map(m => m[0]))];
    const lost = kept.filter(id => !rows.has(id) && !accById.has(id) && !declined.includes(id));
    if (lost.length) {
      problems.push(`上游材料的验收编号没有承接：${lost.join('、')}——原编号在 §8 与 acceptance.yaml 里各有一行`
        + '（沿用上游编号，不重新编号），或在 §8 写「不承接：<编号> <理由>」');
    }
  }
  return problems;
}


/**
 * 知识判定的两个出口（BLOCKER）——按数据前置分四组，能判的组一次全判。
 *
 * 机械层只判**结构与集合**，不判内容对错：
 *   1. 两章独立成节，且不落在技术契约章的区间内（并进去会让守恒从按名退化成按号）；
 *   2. 编号粒度到条目级、编号在册（只写域前缀会让整域漏判照样放行）；
 *   3. 命中集与 acceptance 的 knowledge_rule 集一致；
 *   4. §9.2/§9.3 投影与真源一致。
 *
 * 四组各自的前置：章节组只要 spec 可读；知识层组要激活知识可派生、knowledge-use 可读；
 * 桥接组要判断可读（约束集合可枚举），与投影无关；投影组要判断本身成立且出口章在——
 * 判断不成立时投影核了没意义，缺章时投影区根本不存在。前置缺的组记 skipped 说明缺什么，
 * 不让别的组因它被屏蔽：作者修完一类才看见下一类，是性能上最贵的一种失败。
 *
 * 「这条要求是不是本需求的设计」是语义判断，归 verifier——本函数不下这个结论。
 *
 * @returns {{name: string, problems: string[], skipped: {what: string, why: string}[]}[]}
 */
function knowledgeExitGroups(ctx, lines) {
  const chapter = { name: '知识出口章节', problems: [], skipped: [] };
  const layer = { name: '知识层自检与 knowledge-use 判断', problems: [], skipped: [] };
  const bridge = { name: '命中集合与 acceptance 桥接', problems: [], skipped: [] };
  const projection = { name: '§9.2/§9.3 投影与真源一致', problems: [], skipped: [] };

  // ---- 组 1：章节，只依赖 spec 可读 ----
  const exitIdx = findHeading(lines, /规约约束要求/);
  const patternIdx = findHeading(lines, /设计模式候选/);
  const contractIdx = findHeading(lines, /技术契约/);
  const contractRange = sectionRange(lines, contractIdx);
  if (exitIdx === -1) {
    chapter.problems.push('缺「规约约束要求」章——判定产生的代码要求没有落点，到编码那里就等于不存在。'
      + `形态见 ${SECTIONS_DOC}：这一章的正文由 spec/knowledge-use.yaml 生成，不手写。`);
  }
  if (patternIdx === -1) {
    chapter.problems.push('缺「设计模式候选登记」章——零候选是正常结论，但要显式登记适用单元与理由，'
      + '空着分不清「判过了不需要」与「压根没想这件事」');
  }
  // 独立成节：不得落在技术契约章的区间内
  for (const [idx, name] of [[exitIdx, '规约约束要求'], [patternIdx, '设计模式候选登记']]) {
    if (idx >= 0 && contractRange && idx > contractRange.start && idx < contractRange.end) {
      chapter.problems.push(`「${name}」并进了技术契约章——三章各回答一个问题，须独立成节：`
        + '契约章登记「有什么」，要求章说「必须满足什么」，候选章说「可选什么」。');
    }
  }

  // ---- 组 2：知识层可派生、判断可读 ----
  // 知识层自身的职责边界（规约不携带实现事实、知识不维护阶段路由）放在这里跑：
  // spec 是知识判定的起点，知识层坏了后面每个阶段都建在坏地基上。
  let knowledge = null;
  let use = null;
  try {
    knowledge = activeKnowledge(ctx.projectRoot);
  } catch (e) {
    layer.problems.push(`激活知识派生失败：${e.message}`);
  }
  if (knowledge) {
    layer.problems.push(...selfCheck(ctx.projectRoot, knowledge));
    // 判断的真源是 knowledge-use.yaml；§9.2/§9.3 是它的投影。作者只编辑 YAML，投影由生成器写。
    try {
      use = readUse(ctx.projectRoot, ctx.feature);
    } catch (e) {
      if (e instanceof UseError) layer.problems.push(e.message);
      else throw e;
    }
  }
  const specText = lines.join(String.fromCharCode(10));
  const coverage = knowledge && use ? coverageProblems(ctx.projectRoot, knowledge, use, specText) : null;
  if (coverage) layer.problems.push(...coverage);
  const noJudgement = !knowledge ? '激活知识派生失败' : !use ? '读不到 spec/knowledge-use.yaml' : null;

  // ---- 组 3：命中集合 → acceptance 桥，只要判断可读就核 ----
  if (noJudgement) {
    bridge.skipped.push({ what: '命中集合与 acceptance 桥接', why: noJudgement });
  } else {
    // 命中并落实、产生代码要求的那些，要在 acceptance 里有对应验收条目（本轮豁免的不落实，不建）
    const byId = new Map(knowledge.entries.map(e => [e.id, e]));
    const specIds = new Set(codeRequirementIds(use, knowledge));
    bridge.problems.push(...acceptanceCoverage(ctx, specIds));
    bridge.problems.push(...reviewActionLandings(ctx, byId, use));
  }

  // ---- 组 4：投影一致性，前置是判断本身成立且出口章在 ----
  if (noJudgement) {
    projection.skipped.push({ what: '§9.2/§9.3 投影与真源一致', why: noJudgement });
  } else if (coverage.length) {
    projection.skipped.push({ what: '§9.2/§9.3 投影与真源一致',
      why: `knowledge-use.yaml 的判断有 ${coverage.length} 处不成立，先修它们再核投影` });
  } else if (exitIdx === -1) {
    projection.skipped.push({ what: '§9.2/§9.3 投影与真源一致', why: '缺「规约约束要求」章，投影区不存在' });
  } else {
    // 判据核投影与真源一致，对不上时错的一定是投影。
    projection.problems.push(...zoneProblems(ctx.projectRoot, specText, renderZones(knowledge, use)));
  }
  return [chapter, layer, bridge, projection];
}

/**
 * 命中的评审动作落到了哪里 —— 走 `/story` 的落到议题（`decision` 在决策登记里），不走的写 `impact`。
 *
 * 只核落点在不在、指不指得到：`impact` 写的人与产物对不对、议题是不是真在问这件事，归 verifier。
 * 不走 /story 的需求没有决策登记，写 `decision` 指不到任何东西。
 */
function reviewActionLandings(ctx, byId, use) {
  const problems = [];
  const hits = use.constraints.filter(r => r.applicable === true && !r.waived
    && byId.get(String(r.id ?? '').trim())?.reviewAction);
  if (!hits.length) return problems;
  const root = featureRoot(ctx.projectRoot, ctx.feature);
  const story = isStoryFeature(root);
  const list = story ? decisionList(readJsonOrNull(path.join(root, 'AR', 'story-src', 'decisions.json'))) : null;
  const ids = list ? new Set(list.map(d => String(d?.id ?? '').trim()).filter(Boolean)) : null;
  for (const row of hits) {
    const id = String(row.id ?? '').trim();
    const decision = String(row.decision ?? '').trim();
    const impact = String(row.impact ?? '').trim();
    if (!story) {
      if (decision) problems.push(`${id} 写了 decision「${decision}」，而这个需求没走 /story、没有议题登记——改写 impact：谁、在哪份产物里表态`);
      else if (!impact) problems.push(`${id} 是命中的评审动作，没写 impact——写清谁、在哪份产物里对这件事表态`);
      continue;
    }
    if (!decision) {
      problems.push(`${id} 是命中的评审动作，没写 decision——先在 AR/story-src/decisions.json 登记这件事的议题，`
        + '再把议题 id 写进来；成文登记之后才判到的，先 reopen');
    } else if (ids === null) {
      problems.push(`${id} 的 decision「${decision}」核不了：AR/story-src/decisions.json 读不出议题列表`);
    } else if (!ids.has(decision)) {
      problems.push(`${id} 的 decision「${decision}」在 AR/story-src/decisions.json 里没有这个议题`
        + `（现有：${[...ids].slice(0, 8).join('、') || '无'}）`);
    }
  }
  return problems;
}

/**
 * 命中条目在 acceptance 里有没有对应验收条目（机械收口）。
 *
 * **这是集合一致性，不是「知识已被应用」**——后者是语义判断，机械层越权下语义结论，
 * 就会变成「写了字就算做了」。
 */
function acceptanceCoverage(ctx, specIds) {
  const problems = [];

  // **不和第二份登记表比对**：spec 阶段的判定结论只有 knowledge-use.yaml 一份。
  // 另设一份独立的判定记录文件，会让同一条结论有两处写法、两处判定，
  // 评审者看到互相矛盾的结论时无从知道哪个是准的。归档件的符合性附录由 writer 直接写。

  // acceptance 侧：知识义务的验证要求单源（下游 ut/testing 靠它分派）
  const { acceptance, error, exists } = readAcceptance(ctx.projectRoot, ctx.feature);
  if (!exists) return problems;
  if (error) {
    problems.push(`${error}——知识义务的桥接在验收的 criteria 与 boundaries 里，读不出就核不了`);
    return problems;
  }
  // **按结构读，不按正则扫**：正则扫的是「文件里出现过这个编号」，
  // 它分不清编号写在哪一层，也认不出「一条 criteria 写了一串编号」这种形态——
  // 那形态下游分派不了，而作者会以为自己已经桥接过了。
  // Spec 只桥 criteria：boundaries 是边界场景，出现就代替不了 criteria 的桥。
  const { byRule, problems: shape } = knowledgeCriteria(acceptance);
  problems.push(...shape);
  const accIds = new Set(byRule.keys());
  if (accIds.size || specIds.size) {
    const missing = [...specIds].filter(id => !accIds.has(id));
    if (missing.length) {
      problems.push(`这些条目有代码要求但 acceptance.yaml 没有对应验收条目：${missing.join('、')}`
        + '——每条要求要有一条带 knowledge_rule 的 criteria，'
        + '它是 ut/testing 找到「该覆盖哪个场景」的桥（分派本身由 contracts 里 must.verify 定），'
        + '缺了下游就无从覆盖');
    }
    const unknown = [...accIds].filter(id => !specIds.has(id));
    if (unknown.length) {
      problems.push(`acceptance.yaml 的 knowledge_rule 指向了 spec 里没有要求的条目：${unknown.join('、')}`);
    }
  }
  return problems;
}

/**
 * §9.1 某一节里表外的第一段正文，没有就返回 null。
 *
 * 这一节是给下游 AI 的技术契约：plan 据它编码、test-plan 据它出用例。
 * 表外那几段承载的通常是实现取舍与待定项——它们有自己的去处，进了契约
 * 只会让下游读到一句「由 plan 决定」。
 * 「不涉及：<依据>」独行豁免：那是空节规则的既有形态。
 */
function strayProse(body) {
  // 收到的是 `sectionBody` 切出来的**行数组**，按数组逐行判。
  // 行的边界由上游给，这里不重新猜——重新切一遍就有第二种切法。
  for (const raw of Array.isArray(body) ? body : String(body ?? '').split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('|') || line.startsWith('#')) continue;
    if (/^不涉及[:：]\s*\S/.test(line)) continue;
    if (/^([-*_])\1{2,}$/.test(line)) continue;      // 分隔线：章与章之间的横线，不是段落
    if (/^[-*+]\s/.test(line) || /^\d+[.、)]\s/.test(line)) continue;   // 列表另说
    if (line.startsWith('<!--')) continue;
    return line.replace(/^>\s*/, '');
  }
  return null;
}

const SPEC_EXT_SECTIONS = [
  { ch: '9.1 技术契约', title: /技术契约/, subs: [['端云接口', /端云接口/], ['数据存储', /数据存储/], ['配置项', /配置项/], ['埋点', /埋点/, { prose: true }], ['依赖变更', /依赖变更/]] },
];

export default guard('spec', async (ctx) => {
  const featureDir = featureRoot(ctx.projectRoot, ctx.feature);
  const rel = relDisplay(ctx.projectRoot, path.join(featureDir, 'spec', 'spec.md'));
  const specPath = path.join(featureDir, 'spec', 'spec.md');
  const fix = `处置：按 ${SECTIONS_DOC} 补齐 spec 宿主扩展章节（结论写法见 ${EVIDENCE_DOC}），然后重跑 harness --phase spec。`;

  // spec 本身缺失由 framework 的 check-spec 负责，本 hook 只管宿主扩展部分。
  // 但扩展判据一条都没跑成，要留痕说明——「没报错」不等于「查过了」。
  if (!fs.existsSync(specPath)) {
    return gate(ctx, { skipped: [{ what: 'spec 宿主扩展章节与知识出口', why: 'spec.md 还没生成' }] });
  }

  const text = fs.readFileSync(specPath, 'utf-8').replace(/^﻿/, '');
  const lines = text.split(/\r?\n/);
  const problems = [];

  // 场景探针：走过 /story 的 feature 才有流程契约。
  // 本 hook 的检查分两类——**扩展新增的结构要求**（三份产物、§9.1 技术契约、术语解释列、
  // 归档件红线）只在 story 场景成立，对「口述一个需求直接跑 spec」的用法是凭空多出来的
  // 硬阻断；**知识判定的两个出口**（约束要求章、模式候选登记）与 story 无关，对所有人生效
  // ——判定产生的代码要求不进 spec，编码那里就拿不到。
  const isStory = isStoryFeature(featureDir);

  // ---- story 前置流程契约已收口 ----
  problems.push(...flowProblems(featureDir));

  // ---- 三份产物齐备：第三份是叙事件（story 专属）----
  // spec 是一次 pass 产出 spec.md / AR/review.md / AR/story.md，三者事实同源。
  // 前两份由本文件的章节判据与 decisions 渲染管，第三份查登记态——
  // 登记前会重跑 story-build check，登记成功即九项判据都过了。
  problems.push(...storyProduced(featureDir));

  // ---- 主章号以目标 profile 的模板为准，模板里不编号的章不计入序号 ----
  const chapters = chapterTemplates(ctx.projectRoot, 'spec', 'spec_template', 'skills/story/templates/spec-sections.md');
  problems.push(...chapters.problems);
  if (chapters.templates) problems.push(...chapterNumberProblems(text, chapters.templates));

  // ---- 两章的结构完整性：章在、小节齐、非空、无模板占位（story 专属）----
  // 这两章是扩展在 core 模板之上新增的，只跑原生 spec 的使用者从没被要求写过。
  if (isStory) {
    for (const { ch, title, subs } of SPEC_EXT_SECTIONS) {
      const chIdx = findHeading(lines, title);
      if (chIdx === -1) {
        problems.push(`缺少宿主扩展小节「§${ch}」——写在「9. 宿主扩展治理项」下（形态见 ${SECTIONS_DOC}）`);
        continue;
      }
      // 埋点是埋点设计的唯一完整说明：以指标为单位，总述、每个指标一个小节与它的统计点表，不放图与围栏（附录投影不收图）；其余小节只收表。
      for (const [name, subRe, opts = {}] of subs) {
        const subIdx = findChild(lines, chIdx, subRe);
        if (subIdx === -1) {
          problems.push(`§${ch} 缺少小节「${name}」（小节不得删；不涉及也须写「不涉及 + 一句依据」）`);
          continue;
        }
        const body = sectionBody(lines, subIdx);
        if (!sectionFilled(body)) {
          problems.push(`§${ch}「${name}」未填写（须给出事实或「不涉及 + 一句依据」）`);
        } else if (hasTemplatePlaceholder(body)) {
          problems.push(`§${ch}「${name}」残留模板占位「{ … }」——须替换为实际结论`);
        } else if (opts.prose) {
          const figure = body.find(l => /!\[[^\]]*\]\(/.test(l)) ?? body[fenceRanges(body)[0]?.from];
          if (figure) {
            problems.push(`§${ch}「${name}」里有图或围栏（「${figure.trim().slice(0, 20)}…」）`
              + '——这一节用标题、短段、表与列表写；业务需要的图放它讲的业务章，这里用文字说明或链接过去');
          }
          const level = docOf(lines).headings.find(h => h.at === subIdx).level;
          problems.push(...indicatorShape(`§${ch}「${name}」`, body, level, SECTIONS_DOC));
        } else {
          const stray = strayProse(body);
          if (stray) {
            problems.push(`§${ch}「${name}」表外有段落（「${stray.slice(0, 20)}…」）`
              + '——这一节要么是一张表，要么是一行「不涉及：<依据>」。'
              + '约定进表格；实现取舍写 spec/notes.md；要人拍板的写决策件');
          }
        }
      }
    }
  }

  // ---- 宿主扩展的位置：扩展内容挂在 framework 模板的锚点下，附录最后 ----
  problems.push(...hostAnchorProblems(lines.join('\n'), isStory, SECTIONS_DOC));

  // ---- 知识判定的两个出口（四组，各按前置判）----
  // 出口按**命中条目**派生，不为任何域预留固定小节——预留小节就是把域清单硬编码换个地方存在。
  const groups = knowledgeExitGroups(ctx, lines);

  // ---- 术语映射表：业务名词须有解释（story 专属）----
  // 「解释」列是扩展在 core 模板的 §0 之上追加的，附录 A 只留一句索引。
  // 判据不用白名单——**权威模块落在 in_scope_modules 里的行就是本需求的业务词汇**，
  // 评审者必须能查到；权威模块不在 in_scope_modules 里的行可留「—」。
  // 数据全在 spec 自己里，加约束文件或改架构都不会让这条判据失效。
  if (isStory) {
    const scopeBlock = text.match(/in_scope_modules:\s*\n((?:\s*-\s*.+\n)+)/);
    const inScope = new Set(
      (scopeBlock?.[1] ?? '')
        .split(/\r?\n/)
        .map(l => l.match(/^\s*-\s*(.+?)\s*$/)?.[1])
        .filter(Boolean)
    );
    const mapIdx = findHeading(lines, /术语映射表/);
    if (mapIdx !== -1 && inScope.size > 0) {
      const rows = [];
      let sawSep = false;
      let headerCells = null;
      for (let i = mapIdx + 1; i < lines.length; i++) {
        const l = lines[i].trim();
        if (/^#{2,3}\s/.test(l)) break;
        if (!l.startsWith('|')) { sawSep = false; continue; }
        if (isSeparatorRow(l)) { sawSep = true; continue; }
        const cells = tableCells(l);
        if (!sawSep) { headerCells = cells; continue; }
        rows.push(cells);
      }
      // 「解释」与「权威模块」列按表头定位，不按位置：列序随编辑漂移，列名才是契约。
      const explainIdx = headerCells ? headerCells.findIndex(h => h.trim().includes('解释')) : -1;
      const moduleIdx = headerCells ? headerCells.findIndex(h => h.trim().includes('权威模块')) : -1;
      const business = rows.filter(c => inScope.has((c[moduleIdx] ?? '').trim()));
      const noExplain = business.filter(c => {
        const explain = (c[explainIdx] ?? '').trim();
        return !explain || explain === '—';
      });
      if (rows.length > 0 && (explainIdx < 0 || moduleIdx < 0)) {
        problems.push('术语映射表的表头缺「权威模块」或「解释」列——按 spec 模板的 §0 表头写，判据按列名定位');
      } else if (rows.length > 0 && noExplain.length > 0) {
        problems.push(
          `术语映射表有 ${noExplain.length} 个业务名词没写「解释」：${noExplain.map(c => (c[0] ?? '').trim()).join('、')}` +
            '——它们的权威模块在本需求 Scope 内，是本需求的业务词汇；评审叙事件的术语表从这里抄，' +
            '漏了评审者在归档件里就查不到这个词。基础能力类术语可留「—」'
        );
      }
    }
  }

  // ---- 三条全文红线（客户端词表在章节合同 language_redline，判定在 story/language.mjs · story 专属）----
  // 这三条的作业指导随 story 专属注入件下发；未走 /story 的使用者只在通用注入件里读到
  // 建议形态，不该在这里被硬阻断——**注入指导与硬阻断是两件事**。
  if (isStory) {
    // 客户端语境：spec 是编码与评审件的共同上游，源头不放行才不会一路带下去
    const bannedHits = scanBannedTerms(text);
    if (bannedHits.length > 0) {
      problems.push(`含客户端语境禁用词 ${bannedHits.length} 处（服务器侧词汇，单独使用也算）：`
        + formatHits(bannedHits, 'banned').join('；'));
    }

    // 独立审计：不写文档坐标（详见 evidence-rules 独立审计原则）
    const coordHits = scanDocCoords(text);
    if (coordHits.length > 0) {
      problems.push(`含文档坐标 ${coordHits.length} 处（spec 须可独立审计；改用事物本身的名字，如接口名、配置项名）：`
        + coordHits.map(h => `第 ${h.line} 行「${h.coord}」`).join('、'));
    }

    // 数值来源：机械层只核标没标（结构门）；真假归 overlay 的数值依据判项。
    problems.push(...scanNumericSources(text));
  }

  // ---- 可机械核的一致性：§8 与 acceptance.yaml、上游原始验收编号 ----
  problems.push(...acceptanceAlignment(ctx, lines, featureDir, isStory));

  // ---- 本阶段审查报告：格式、判据全不全、一对象一结论、WARN 行的处置 ----
  problems.push(...reportProblems(ctx.projectRoot, ctx.feature, 'spec'));

  const total = problems.length + groups.reduce((n, g) => n + g.problems.length, 0);
  return gate(ctx, {
    problems,
    groups,
    skipped: chapters.skipped,
    checks: [
      { id: 'knowledge_exit_structure', status: total ? STATUS.FAIL : STATUS.PASS, detail: `问题 ${total} 条` },
    ],
    inputs: [specPath],
    fix: `产物：spec.md（${rel}）。${fix}`,
  });
});

