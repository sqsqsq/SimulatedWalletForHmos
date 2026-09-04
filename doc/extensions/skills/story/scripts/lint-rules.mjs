/**
 * lint-rules.mjs — story 扩展的共享文本校验规则（词表 SSOT）
 *
 * 两组规则，供 hooks/spec/post_check.mjs（校验 spec.md）与 story-build.mjs check（校验 story.md）共用，
 * 避免两处各维护一份词表而漂移。
 *
 * **词表本身在章节合同里**（`language_redline.client_vocabulary`）：作者要在动笔前看到
 * 「哪些词不能用、改说什么」，门禁要按同一份判。词留在脚本里，作者就只能撞了门禁才知道，
 * 或者去读脚本。本文件保留的是**判定形态**：作用域、豁免语境、
 * 代码块与整章豁免——它们是形态不是词，写成数据反而说不清。
 *
 * **工程形态一律运行时推导，不硬编码**：模块目录形态取自 `framework.config.json` 的分层声明，
 * 知识文件名取自激活清单（不扫目录——目录里躺着的未启用文件不参与判定）。硬编码的快照会过期：
 * 本文件曾内置一份约束文件名清单，其中三个文件早已退役而清单没跟上；换工程时它更是直接失效
 * （模块目录形态一变，仓内路径就扫不到，归档件自包含红线**静默**失效）。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { activeKnowledge } from '../../../hooks/shared/knowledge.mjs';
import { normalizeHeading } from './headings.mjs';

const CONTRACT_PATH = path.join(
  path.dirname(fileURLToPath(import.meta.url)), '..', 'contracts', 'story-chapters.json');

let vocabularyCache = null;

/**
 * 客户端语境禁用词，取自章节合同。
 *
 * 合同缺这一段就是漏交付：判据默默不判比报错更坏——归档件里的服务端词会一路带到编码。
 */
export function clientVocabulary() {
  if (vocabularyCache) return vocabularyCache;
  const raw = JSON.parse(fs.readFileSync(CONTRACT_PATH, 'utf-8'));
  const list = raw?.language_redline?.client_vocabulary;
  if (!Array.isArray(list) || list.length === 0) {
    throw new Error('章节合同缺 language_redline.client_vocabulary：客户端语境词表是合同数据，脚本里不留副本');
  }
  vocabularyCache = list.map(x => ({ term: String(x.term), hint: String(x.hint ?? '') }));
  return vocabularyCache;
}

/**
 * 豁免语境：命中这些模式的行不判违规。
 * - 规则文件自身在定义/引用禁用词（含本文件、SKILL、rules）
 * - 引用上游规约原章节名（规约 §7.1.1.3 标题即含 QPS，删了就对不上溯源）
 * - 「回退」用于数据/状态语义而非版本发布语义
 */
const EXEMPT_LINE_PATTERNS = [
  /禁用|红线|改说|违规|banned|BANNED/i,
  /规约\s*§|上游规约/,
  /状态可恢复或明确回退|数据回退|事务回退/,
];

const escapeRe = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/**
 * 读 framework 配置。推导不出来时各处自行退回通用形态。
 *
 * **配置不存在**与**配置坏了**要分开：前者在换工程或裸跑时是正常的，后者是事故——
 * 一份坏掉的配置会让所有从它派生的判据一起悄悄失效，那正是最该被看见的时刻。
 */
function readConfig(projectRoot) {
  if (!projectRoot) return {};
  const configPath = path.join(projectRoot, 'framework.config.json');
  if (!fs.existsSync(configPath)) return {};
  try {
    return JSON.parse(fs.readFileSync(configPath, 'utf-8'));
  } catch (e) {
    console.error(`[lint-rules] framework.config.json 解析失败：${e.message}`
      + '——所有从它派生的形态判据将退回通用段');
    return {};
  }
}

/**
 * 仓内路径模式：归档件自包含红线——上传后独立存在，不得含本地路径。
 *
 * 通用段是 framework 结构（跨工程不变）：`doc/extensions|features/`、`framework/`，
 * 以及 feature 工作区内的 `RR/` `SR/` `AR/`——评审者同样打不开。
 * 业务模块目录形态**因工程而异**（有的工程用带序号的分层目录，有的是扁平的
 * `app/`、`feature-xxx/`），故从配置的分层声明现取，取不到就只用通用段。
 */
const GENERIC_PATH_ALTS = [
  String.raw`\bdoc\/(?:extensions|features)\/[\w./-]+`,
  String.raw`\bframework\/[\w./-]+`,
  String.raw`\b(?:RR|SR|AR)\/[\w.-]+\.\w+`,
];

function moduleLayerIds(projectRoot) {
  const layers = readConfig(projectRoot)?.architecture?.outer_layers;
  if (!Array.isArray(layers)) return [];
  return layers.map(l => l?.id).filter(id => typeof id === 'string' && id.trim());
}

/**
 * 平台能力层（依赖链最底层）的 id。
 *
 * **判据是依赖方向，不是名字**：`can_depend_on` 为空的层不依赖任何其它层，
 * 它承载的是跨业务的平台能力。写死某个层名会在换工程时静默失效（坑 #29），
 * 而依赖方向是架构 DSL 里本来就有的语义。
 *
 * @returns {string[]} 取不到声明时返回空数组并**出声告警**——调用方据此不过滤，
 *   但这属于降级而非正常路径：静默降级会让「术语分流」这条判据无声消失。
 */
export function baseLayerIds(projectRoot) {
  const layers = readConfig(projectRoot)?.architecture?.outer_layers;
  if (!Array.isArray(layers)) {
    console.error('[lint-rules] 架构 DSL 未声明外层，无法派生平台能力层：术语分流降级为不过滤');
    return [];
  }
  const ids = layers
    .filter(l => Array.isArray(l?.can_depend_on) && l.can_depend_on.length === 0)
    .map(l => l?.id)
    .filter(id => typeof id === 'string' && id.trim());
  if (!ids.length) {
    console.error('[lint-rules] 架构 DSL 里没有依赖链最底层（can_depend_on 全非空）：术语分流降级为不过滤');
  }
  return ids;
}

function localPathRe(projectRoot) {
  const ids = moduleLayerIds(projectRoot);
  const alts = [...GENERIC_PATH_ALTS];
  if (ids.length) alts.unshift(String.raw`\b(?:${ids.map(escapeRe).join('|')})\/[\w./-]+`);
  return new RegExp(`(?:${alts.join('|')})`, 'g');
}

/**
 * 扫描禁用词。
 *
 * **章级豁免**（`opts.exemptChapters`，取值来自合同数据）：某些章天然在讲发布动作，
 * 「灰度」「回退」在那里是业务事实而不是客户端文案。作用域收缩到章，与语言红线
 * 收缩到「附录之外」同形——不是给某个词开小灶，是承认这几个词在那一章有正当位置。
 * 实证：理想产物的「回退设计」小节被整节判成违规，而那一节恰是评审者最要看的。
 *
 * @param {string} text
 * @param {object} [opts]
 * @param {string[]} [opts.exemptChapters] 整章豁免的章标题（业务名，编号自动剥）
 * @returns {{line:number, term:string, hint:string, text:string}[]}
 */
export function scanBannedTerms(text, opts = {}) {
  const hits = [];
  const exempt = new Set((opts.exemptChapters ?? []).map(normalizeHeading).filter(Boolean));
  const lines = text.split(/\r?\n/);
  let inFence = false;
  let inExemptChapter = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (/^\s*(```|~~~)/.test(line)) {
      inFence = !inFence;
      continue;
    }
    if (inFence) continue; // 代码块内可能是标识符，不判
    const heading = line.trim().match(/^##\s+(.+)$/);
    if (heading) inExemptChapter = exempt.has(normalizeHeading(heading[1]));
    if (inExemptChapter) continue;
    if (EXEMPT_LINE_PATTERNS.some(re => re.test(line))) continue;
    for (const { term, hint } of clientVocabulary()) {
      if (line.includes(term)) hits.push({ line: i + 1, term, hint, text: line.trim().slice(0, 100) });
    }
  }
  return hits;
}

// ---------------------------------------------------------------------------
// 语言红线：作用域是**附录之外的主叙事**
//
// 接口名、字段名、存储键、事件 ID、规约编号这些工程标识不是不该出现在归档件里——
// 它们必须保留，评审者要查的时候得查得到。问题在于**它们不能打断面向人的主叙述**：
// 读者顺着九章读下来，每隔两行撞见一个 camelCase 就得停下来判断「这是我要懂的东西吗」。
//
// 所以附录成为它们的唯一落点：主叙事写中文业务名与中文规约名，标识在附录成表。
// 这不是排除，是给它一个不打断阅读、机器又核得到的位置——守恒 token 在附录表里照样可核。

/** 检索措辞：把「我去搜了一下没搜到」这种起草过程写进了给读者的文档。 */
const SEARCH_PHRASE_RE = /检索[^。；\n]{0,16}(?:零命中|未命中|无结果|没有命中|无命中)/g;

/** 来源括注：起草时标注「这个数是谁定的」，读者不需要，它属于附录的材料清单。 */
const SOURCE_TAG_RE = /（\s*(?:本工程设定|工程设定|上游约束|上游已定|本文设定)[^）]*）/g;

/** 文档坐标：`xxx.md`、`§3.2` 这类只有仓内读者才用得上的定位。 */
const DOC_COORDINATE_RE = /\b[\w-]+\.md\b|§\s*[\d.]+/g;

/** 代码标识符的两种形态——它们几乎不会是产品名，可以无条件判。 */
const CAMEL_CASE_RE = /\b[a-z][a-z0-9]*(?:[A-Z][a-zA-Z0-9]*)+\b/g;
const SNAKE_CASE_RE = /\b[a-z][a-z0-9]*(?:_[a-z0-9]+){2,}\b/g;

/** 行内代码：主叙事里出现反引号，包的多半就是标识符。 */
const INLINE_CODE_RE = /`([^`\n]+)`/g;

/** AI 腔标题：模型写小标题时的口头禅。章标题由 check ① 判，这里只判 H3/H4。 */
const AI_HEADING_TERMS = ['综上所述', '值得注意的是', '需要指出的是', '总的来说', '综上'];

const REDLINE_HINTS = {
  repo_identifier: '工程标识进附录的那几张表，主叙事写中文业务名',
  rule_id: '主叙事写中文规约名；编号进附录的规约判定表',
  search_phrase: '这是起草过程，不是需求事实——读者不需要知道你搜没搜到',
  source_tag: '「谁定的」进附录的材料清单，不打断正文',
  doc_coordinate: '归档件的读者手上没有这个仓库，改用本文章节名或需求系统单号',
  placeholder_heading: '标题用真实业务名，模板占位没填就是没写',
  ai_heading: '标题用真实业务名，短、自然、准确概括下文',
  harness_artifact: '这是造它的装置与流程说的话，不是需求本身——读者要的是业务事实，写它做什么、给谁用',
};

/**
 * 全篇逐行，并标出「这一行在附录里吗」。
 *
 * 多数红线的作用域是附录之外——工程标识本来就该落在附录，扫它等于自相矛盾。
 * 但有两类东西在附录里也不该有（起草时的检索措辞、装置与流程机构的词），
 * 所以边界不能在这里一刀切掉，逐类的作用域由合同数据说了算。
 *
 * **标题过规范化通道**：归档件的附录写作 `## 10. 附录`，合同里存的是 `附录`。
 * 早先这里做逐字相等比较，编号一加就认不出附录，于是整个附录被当主叙事扫，
 * 报出几十条本该允许的接口名与字段名——作者看到的是一堵无法翻越的墙。
 *
 * @returns {{line:number, text:string, inAppendix:boolean}[]} 行号是**原文行号**，报错要指得回去
 */
function narrativeLines(text, appendixTitle) {
  const out = [];
  const want = normalizeHeading(appendixTitle);
  const lines = String(text ?? '').split(/\r?\n/);
  let inAppendix = false;
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].trim().match(/^##\s+(.+)$/);
    if (m && want && normalizeHeading(m[1]) === want) inAppendix = true;
    out.push({ line: i + 1, text: lines[i], inAppendix });
  }
  return out;
}

/**
 * 逐类作用域：合同里写字符串 = 默认作用域（附录之外），写 `{kind, scope}` = 按它说的。
 *
 * @param {(string|{kind:string, scope?:string})[]} decls
 * @returns {Map<string, string>} kind → scope
 */
function redlineScopes(decls) {
  const out = new Map();
  for (const decl of decls ?? []) {
    if (typeof decl === 'string') out.set(decl, 'non_appendix');
    else if (decl && typeof decl.kind === 'string') out.set(decl.kind, decl.scope || 'non_appendix');
  }
  return out;
}

/**
 * 扫描主叙事里的语言红线。
 *
 * **规则全部是数据**：规约编号来自激活清单，PascalCase 标识符来自材料里实际出现过的
 * token——不猜。猜的代价是把 `HarmonyOS`、`WebView` 这类产品名判成工程标识，
 * 而作者除了删掉正确的词之外无路可走。
 *
 * @param {string} text story 全文
 * @param {object} [opts]
 * @param {string} [opts.appendixTitle] 附录章标题（作用域边界）
 * @param {string[]} [opts.ruleIds] 激活清单里的规约编号
 * @param {string[]} [opts.identifiers] 材料里出现过的 ASCII 标识符
 * @param {(string|{kind:string, scope?:string})[]} [opts.kinds] 只查这几类及各自作用域；不给则全查
 * @param {string[]} [opts.harnessTerms] 装置与流程机构的类别词表（合同数据）
 * @returns {{line:number, kind:string, hit:string, hint:string, text:string}[]}
 */
export function scanLanguageRedline(text, opts = {}) {
  const scopes = opts.kinds ? redlineScopes(opts.kinds)
    : new Map(Object.keys(REDLINE_HINTS).map(k => [k, 'non_appendix']));
  const ruleIds = (opts.ruleIds ?? []).filter(id => typeof id === 'string' && id.trim());
  const harnessTerms = (opts.harnessTerms ?? []).filter(t => typeof t === 'string' && t.trim());
  const hits = [];
  let inFence = false;
  let inAppendix = false;

  const push = (line, kind, hit, raw) => {
    const scope = scopes.get(kind);
    if (!scope) return;
    if (inAppendix && scope !== 'all') return;
    hits.push({ line, kind, hit, hint: REDLINE_HINTS[kind], text: raw.trim().slice(0, 100) });
  };

  for (const { line, text: raw, inAppendix: atAppendix } of narrativeLines(text, opts.appendixTitle)) {
    inAppendix = atAppendix;
    if (/^\s*(```|~~~)/.test(raw)) {
      inFence = !inFence;
      continue;
    }
    if (inFence) continue;      // 围栏里是图与代码，不是叙述

    const heading = raw.trim().match(/^#{3,4}\s+(.+)$/);
    if (heading) {
      const title = heading[1].trim();
      if (title.includes('{{') || /<[^>]*>/.test(title)) {
        push(line, 'placeholder_heading', title, raw);
      }
      if (/[？?]\s*$/.test(title)) push(line, 'ai_heading', title, raw);
      for (const term of AI_HEADING_TERMS) {
        if (title.includes(term)) push(line, 'ai_heading', term, raw);
      }
    }

    for (const m of raw.matchAll(INLINE_CODE_RE)) {
      push(line, 'repo_identifier', m[1], raw);
    }
    const outsideCode = raw.replace(INLINE_CODE_RE, ' ');
    for (const re of [CAMEL_CASE_RE, SNAKE_CASE_RE]) {
      for (const m of outsideCode.matchAll(re)) push(line, 'repo_identifier', m[0], raw);
    }
    // **不拿材料派生的词表来判**：那份词表是按标识形态从材料里切出来的，
    // `（share-setup.png）` 会切出 `share` 这种伪标识，红线于是拦下 story 里的图片引用行，
    // 与「图片一张不少」直接互斥，作者只剩「不进 story」一条出路。
    // 主叙事里某个英文词该不该出现要读上下文，那是独立审查判的事；
    // 这里只认**形态本身就是工程标识**的那几种（行内代码、驼峰、下划线、仓内路径）。

    for (const id of ruleIds) {
      if (raw.includes(id)) push(line, 'rule_id', id, raw);
    }
    // 来源括注在**表格里不判**：它之所以是病，是因为插在句子中间打断阅读；
    // 表格的一格里「谁定的」是结构化事实，读者一眼扫过去，不构成打断。
    // 关键取舍表用它标「这条已由上游定死」是正当写法，那正是评审者要看的判断。
    const isTableRow = raw.trim().startsWith('|');
    for (const [kind, re] of [['search_phrase', SEARCH_PHRASE_RE],
                              ['source_tag', SOURCE_TAG_RE],
                              ['doc_coordinate', DOC_COORDINATE_RE]]) {
      if (kind === 'source_tag' && isTableRow) continue;
      for (const m of raw.matchAll(re)) push(line, kind, m[0], raw);
    }

    // 装置词：造这份文档的工具与流程机构说的话。词表是**类别词**、由合同登记，
    // 本文件不写具体词——写了就成了「这一轮见过的那几个词」。ASCII 词不分大小写。
    for (const term of harnessTerms) {
      const ascii = /^[A-Za-z0-9_.-]+$/.test(term);
      const hit = ascii ? raw.toLowerCase().includes(term.toLowerCase()) : raw.includes(term);
      if (hit) push(line, 'harness_artifact', term, raw);
    }
  }
  // 同一行同一类只报一次：一行里三个 camelCase 报三条，读的人只会更烦
  const seen = new Set();
  return hits.filter(h => {
    const key = `${h.line}:${h.kind}:${h.hit}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/** 材料清单那一节的行形态修法。 */
const IMAGE_HINTS = {
  material_row: '材料清单用列表不用表：读者只需要知道本文据哪几份材料写成、各自贡献了什么',
  material_scope: '材料清单只列进 spec 之前的原始输入——本轮自己生成的中间产物、'
    + '参考件与图片直链不是材料（图随它所在的那份材料走，不单列）',
  material_link: '每份材料给一条原文链接——读者据此自己把那份材料找出来；'
    + '光写「产品需求文档」他不知道该找谁要哪一份',
};

/**
 * 材料清单那一节的行形态：成列表、每行给得出原文链接。
 *
 * @param {string} body 该小节正文
 * @param {number} baseLine 该小节正文首行在全篇里的行号（报错要指得回去）
 */
export function scanMaterialList(body, baseLine = 0, opts = {}) {
  const hits = [];
  const lines = String(body ?? '').split(/\r?\n/);
  const allow = opts.allowDirs ?? [];
  const from = opts.storyDir ?? '';
  for (let i = 0; i < lines.length; i++) {
    const s = lines[i].trim();
    const line = baseLine + i;
    if (s.startsWith('|')) {
      hits.push({ line, kind: 'material_row', hit: s.slice(0, 40),
                  hint: IMAGE_HINTS.material_row, text: s.slice(0, 100) });
      continue;
    }
    if (!/^[-*+]\s/.test(s)) continue;
    const links = [...s.matchAll(/\[[^\]]*\]\(([^)\s]+)\)/g)];
    if (!links.length) {
      hits.push({ line, kind: 'material_link', hit: s.slice(0, 40),
                  hint: IMAGE_HINTS.material_link, text: s.slice(0, 100) });
      continue;
    }
    if (!allow.length) continue;
    for (const [, target] of links) {
      if (/^(https?:|mailto:)/i.test(target)) continue;
      const dir = firstSegment(from, target);
      if (dir !== null && !allow.includes(dir)) {
        hits.push({ line, kind: 'material_scope', hit: target,
                    hint: IMAGE_HINTS.material_scope, text: s.slice(0, 100) });
      }
    }
  }
  return hits;
}

/**
 * 把一条相对链接解析到需求目录下的第一段目录名。
 *
 * 材料清单列的是**进 spec 之前的原始输入**。中间产物（本轮自己生成的规格、
 * 事实记录、参考件）与图片文件直链不是材料——它们混进来，清单就从「据哪几份材料写成」
 * 变成倾倒区：同一份规格被链好几次，连图片文件都单列成行。
 */
function firstSegment(fromDir, target) {
  const parts = String(fromDir ?? '').split('/').filter(Boolean);
  for (const seg of String(target).replace(/^\.\//, '').split('/')) {
    if (seg === '..') { parts.pop(); continue; }
    if (seg === '.' || !seg) continue;
    parts.push(seg);
  }
  return parts.length > 1 ? parts[0] : null;   // 只剩文件名 → 与 story 同目录
}

/**
 * 扫描仓内本地路径。
 * @param {string} text 待扫描文本
 * @param {string} [projectRoot] 工程根：给出则按其分层声明识别业务模块目录
 * @returns {{line:number, path:string, text:string}[]}
 */
export function scanLocalPaths(text, projectRoot) {
  const re = localPathRe(projectRoot);
  const hits = [];
  const lines = text.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    for (const m of lines[i].matchAll(re)) {
      hits.push({ line: i + 1, path: m[0], text: lines[i].trim().slice(0, 100) });
    }
  }
  return hits;
}

/**
 * 悬空引用：指向**不随归档**的文件的坐标。
 * 随归档的只有 AR/story.md（叙事主件）与 AR/review.md（决策件）两份；
 * spec.md / SR/design.md / RR/prd.md 都留在仓内，归档后这些坐标查无此物。
 * 合法的指代只有五类：本文章节号、代码模块+文件名、中文规约名+编号、需求系统单号、
 * 随归档的兄弟件（写中文书名《决策与评审记录》——`review.md` 这个文件名仍拦，
 * 评审者拿到的是上传后的文档，不是仓内路径）。
 */
const DANGLING_REF_PATTERNS = [
  { re: /\bspec\s*§/g, hint: 'spec.md 不随归档，改用本文章节号（如「§6.2 数据存储」）' },
  { re: /\bSR\s*§/g, hint: 'SR/design.md 不随归档，首次溯源写「SE 设计文档 <单号>」，其余直接内联结论' },
  { re: /\bRR\s*§|\bPRD\s*§/g, hint: 'RR/prd.md 不随归档，首次溯源写「产品需求文档 <单号>」，其余直接内联结论' },
  { re: /\bAR\s*§/g, hint: 'AR/design.md 归档时被本文覆盖，改用本文章节号' },
  { re: /(?:见|指回|来源|源：)\s*A[1-8]\b/g, hint: '历史 impact 小节编号，本文不存在——改用事物的名字' },
  { re: /\bar_design_init\b|\bevidence-rules\b|\bstory-chapters\b|\bstory-src\b|SKILL\.md/g, hint: 'skill 内部规则文件不随归档，改述为自然语言' },
  { re: /\b[a-z][a-z0-9-]*:[A-Z]{2,10}-\d{2}\b/g, hint: 'slug 是仓内文件名，改写为中文规约名 + 编号（形如「<中文规约名> XXX-01」）' },
];

/**
 * 裸文件名（无路径分隔符）：`scanLocalPaths` 只认带 `/` 的路径，覆盖不到，故单列一条。
 *
 * 框架产物名固定；**知识文件名从激活清单派生**——它随工程启用的知识而变，硬编码就是个
 * 会过期的快照（旧清单里三个文件早已退役却还留在正则里）。
 * 也不扫目录：阶段只认清单，目录里躺着的未启用文件不参与任何判定。
 */
const FRAMEWORK_ARTIFACT_NAMES = ['acceptance', 'spec', 'impact', 'review'];

function constraintNames(projectRoot) {
  if (!projectRoot) return [];
  try {
    const knowledge = activeKnowledge(projectRoot);
    return [...knowledge.constraints, ...knowledge.patterns, ...knowledge.facts]
      .map(k => k.file.split('/').pop().replace(/\.md$/, ''));
  } catch (e) {
    // 派生不到不静默：降级只影响裸文件名这一条规则，但必须让人看见（G7）
    console.error(`[lint-rules] 知识文件名派生失败，裸文件名规则降级为仅框架产物名：${e.message}`);
    return [];
  }
}

function bareFileNameRule(projectRoot) {
  const names = [...new Set([...constraintNames(projectRoot), ...FRAMEWORK_ARTIFACT_NAMES])];
  return {
    re: new RegExp(String.raw`\b(?:${names.map(escapeRe).join('|')})\.(?:md|yaml|yml|json)\b`, 'g'),
    hint: '仓内文件名不随归档——知识文件改写为它的中文名，产物文件改述为本文章节',
  };
}

/**
 * @param {string} text 待扫描文本
 * @param {string} [projectRoot] 工程根：给出则把该工程的约束文件名一并纳入裸文件名判定
 */
export function scanDanglingRefs(text, projectRoot) {
  const patterns = [...DANGLING_REF_PATTERNS, bareFileNameRule(projectRoot)];
  const hits = [];
  const lines = text.split(/\r?\n/);
  let inFence = false;
  let inComment = false;
  for (let i = 0; i < lines.length; i++) {
    if (/^\s*(```|~~~)/.test(lines[i])) {
      inFence = !inFence;
      continue;
    }
    // HTML 注释块（含 ai 锚点标记与模板指引）不参与判定——它们不是给评审者读的内容
    if (inComment) {
      if (lines[i].includes('-->')) inComment = false;
      continue;
    }
    if (/<!--/.test(lines[i])) {
      if (!lines[i].includes('-->')) inComment = true;
      continue;
    }
    if (inFence) continue;
    for (const { re, hint } of patterns) {
      for (const m of lines[i].matchAll(re)) {
        hits.push({ line: i + 1, ref: m[0].trim(), hint, text: lines[i].trim().slice(0, 80) });
      }
    }
  }
  return hits;
}

/** 把扫描结果渲染成人可读的问题列表 */
export function formatHits(hits, kind) {
  return hits.map(h => {
    if (kind === 'banned') return `第 ${h.line} 行禁用词「${h.term}」（${h.hint}）：${h.text}`;
    if (kind === 'dangling') return `第 ${h.line} 行悬空引用「${h.ref}」——${h.hint}`;
    if (kind === 'image') return `第 ${h.line} 行图片引用「${h.path}」解析不到文件`;
    return `第 ${h.line} 行含仓内路径「${h.path}」：${h.text}`;
  });
}

/**
 * 图片断链：按归档件所在目录解析相对路径，文件不存在即命中。
 *
 * 归档件是交出去给评审者看的——引用写成裸文件名或指向源材料目录，本地打开是红叉，
 * 而正文与装配都不会因此报错：形态守恒只数图的条数，数得到「有一张图」，看不出它打不开。
 *
 * 外链（http/https）与内嵌数据不判：那不是仓内文件。
 */
export function scanBrokenImages(text, baseDir, fsMod, pathMod) {
  const hits = [];
  const rows = String(text ?? '').split(/\r?\n/);
  for (let i = 0; i < rows.length; i++) {
    for (const m of rows[i].matchAll(/!\[[^\]]*\]\(([^)\s]+)\)/g)) {
      const ref = m[1];
      if (/^(https?:|data:)/i.test(ref)) continue;
      const abs = pathMod.resolve(baseDir, decodeURIComponent(ref.replace(/^<|>$/g, '')));
      if (!fsMod.existsSync(abs)) hits.push({ line: i + 1, path: ref });
    }
  }
  return hits;
}

/**
 * 一段文本里的**正文段**（表、列表、标题、图、围栏、引用块之外的那些）。
 *
 * 用来判「该成表的地方别写散文」与附录的「表外零散文」：附录是查阅件，
 * 每节一句目的句就够，表后再跟几段散文，那几段承载的正是没地方去的工程 token。
 *
 * `afterRows` 记它出没出现在第一行表格/列表之后——附录那条判的正是**尾巴**：
 * 开头那一句是目的句（该有的），跟在表后面的才是没地方去的东西挤出来的。
 *
 * @returns {{line:number, text:string, afterRows:boolean}[]}
 */
export function proseBlocks(text, baseLine = 0) {
  const out = [];
  const lines = String(text ?? '').split(/\r?\n/);
  let inFence = false;
  let cur = null;
  let seenRow = false;
  const flush = () => { if (cur) out.push(cur); cur = null; };
  for (let i = 0; i < lines.length; i++) {
    const s = lines[i].trim();
    if (/^(```|~~~)/.test(s)) { inFence = !inFence; flush(); continue; }
    if (inFence) continue;
    const isRow = s.startsWith('|') || /^[-*+]\s/.test(s) || /^\d+[.、)]\s/.test(s);
    if (!s || /^#{1,6}\s/.test(s) || isRow || s.startsWith('>') || /^!\[/.test(s)) {
      flush();
      if (isRow) seenRow = true;
      continue;
    }
    cur = cur
      ? { ...cur, text: `${cur.text}${s}` }
      : { line: baseLine + i + 1, text: s, afterRows: seenRow };
  }
  flush();
  return out;
}
