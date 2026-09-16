/**
 * 归档件红线与语言红线的判定形态 —— 词与类别在章节合同（`language_redline`），形态在这里。
 *
 * 读者是 story-build check（story.md 与 review.md）与 hooks/spec/post_check.mjs（spec.md 的客户端词）。
 * 合同给：红线有哪几类及各自作用域、来源括注的词、客户端禁用词与改法；本文件给：行内代码、
 * 驼峰与下划线标识、文档坐标、仓内路径这几种**形态本身**。围栏与标题的切法走 `document.mjs`，
 * 本文件不自己认围栏。
 *
 * **工程形态一律运行时推导，不硬编码**：模块目录形态取自 `framework.config.json` 的分层声明，
 * 规约编号与知识文件名取自激活清单。硬编码的快照会在换工程时静默失效。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { activeKnowledge } from '../../../../../hooks/shared/knowledge.mjs';
import { headingEnd, normalizeHeading, parseDocument } from './document.mjs';

const CONTRACT_PATH = path.join(
  path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..', 'contracts', 'story-chapters.json');

let vocabularyCache = null;

/**
 * 客户端语境禁用词，取自章节合同。已读好合同的调用方把它传进来，不再读第二遍。
 *
 * 合同缺这一段就是漏交付：判据默默不判比报错更坏——归档件里的服务端词会一路带到编码。
 */
export function clientVocabulary(contract) {
  if (!contract && vocabularyCache) return vocabularyCache;
  const raw = contract ?? JSON.parse(fs.readFileSync(CONTRACT_PATH, 'utf-8'));
  const list = raw?.language_redline?.client_vocabulary;
  if (!Array.isArray(list) || list.length === 0) {
    throw new Error('章节合同缺 language_redline.client_vocabulary：客户端语境词表是合同数据，脚本里不留副本');
  }
  const out = list.map(x => ({ term: String(x.term), hint: String(x.hint ?? '') }));
  if (!contract) vocabularyCache = out;
  return out;
}

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
    console.error(`[language] framework.config.json 解析失败：${e.message}`
      + '——所有从它派生的形态判据将退回通用段');
    return {};
  }
}

/**
 * 仓内路径模式：归档件自包含红线——上传后独立存在，不得含本地路径。
 *
 * 通用段是 framework 结构（跨工程不变）：`doc/extensions|features/`、`framework/`，
 * 以及 feature 工作区内的 `RR/` `SR/` `AR/`——评审者同样打不开。
 * 业务模块目录形态**因工程而异**，故从配置的分层声明现取，取不到就只用通用段。
 */
const GENERIC_PATH_ALTS = [
  String.raw`\bdoc\/(?:extensions|features)\/[\w./-]+`,
  String.raw`\bframework\/[\w./-]+`,
  String.raw`\b(?:RR|SR|AR)\/[\w.-]+\.\w+`,
];

function localPathRe(projectRoot) {
  const layers = readConfig(projectRoot)?.architecture?.outer_layers;
  const ids = Array.isArray(layers) ? layers.map(l => l?.id).filter(id => typeof id === 'string' && id.trim()) : [];
  const alts = [...GENERIC_PATH_ALTS];
  if (ids.length) alts.unshift(String.raw`\b(?:${ids.map(escapeRe).join('|')})\/[\w./-]+`);
  return new RegExp(`(?:${alts.join('|')})`, 'g');
}

/**
 * 扫描禁用词：客户端语境里只可能指服务器侧动作的词。围栏里的不判。
 *
 * **章级豁免**（`opts.exemptChapters`，取值来自合同数据）：某些章天然在讲发布与开关动作，
 * 那几个词在那一章是业务事实——收缩的是作用域，不是词表。
 *
 * @param {string} text
 * @param {{exemptChapters?: string[], contract?: object}} [opts]
 * @returns {{line:number, term:string, hint:string, text:string}[]}
 */
export function scanBannedTerms(text, opts = {}) {
  const exempt = new Set((opts.exemptChapters ?? []).map(normalizeHeading).filter(Boolean));
  const vocabulary = clientVocabulary(opts.contract);
  const doc = parseDocument(text);
  const chapterAt = new Map(doc.headings.filter(h => h.level === 2).map(h => [h.at, h.name]));
  const hits = [];
  let inExemptChapter = false;
  doc.lines.forEach((line, i) => {
    if (chapterAt.has(i)) inExemptChapter = exempt.has(chapterAt.get(i));
    if (doc.fenced.has(i) || inExemptChapter) return;
    for (const { term, hint } of vocabulary) {
      if (line.includes(term)) hits.push({ line: i + 1, term, hint, text: line.trim().slice(0, 100) });
    }
  });
  return hits;
}

// ---------------------------------------------------------------------------
// 语言红线：四类，逐类带作用域（合同 `language_redline.kinds`）
//
// 接口名、字段名、规约编号这些工程标识不是不该出现在归档件里——评审者要查的时候得查得到。
// 问题在于**它们不能打断面向人的主叙述**，所以它们的落点是附录。文档坐标与之不同：
// 指向不随归档的文件，放在哪里读者都打不开，作用域是全篇。

/** 代码标识符的两种形态——它们几乎不会是产品名，可以无条件判。 */
const CAMEL_CASE_RE = /\b[a-z][a-z0-9]*(?:[A-Z][a-zA-Z0-9]*)+\b/g;
const SNAKE_CASE_RE = /\b[a-z][a-z0-9]*(?:_[a-z0-9]+){2,}\b/g;

/** 行内代码：主叙事里出现反引号，包的多半就是标识符。 */
const INLINE_CODE_RE = /`([^`\n]+)`/g;

/**
 * 文档坐标：指向**不随归档**的文件或会随重编号漂移的位置。一行命中几种也只报一条。
 * 随归档的只有叙事件与《决策与评审记录》两份；spec、系统设计、产品需求稿、知识文件都留在仓内。
 */
const DOC_COORDINATE_HEAD = { re: /\b(?:spec|SR|RR|PRD|AR)\s*§\s*[\d.]*/g,
  hint: '这份文档不随归档，读者打不开——把那一处的结论直接写进来，或改用本文章节名' };

//: 框架产物的文件名：随工程不变。知识文件名随激活清单变，运行时取。
const FRAMEWORK_ARTIFACT_NAMES = ['acceptance', 'spec', 'impact', 'review'];

/**
 * 文档坐标的全部形态。文件名只认**文档**：任意 `.md`，加上知识文件与框架产物的名字——
 * 资源与代码文件名（`string.json`）是工程标识，附录里是它们的正当落点，不在这里拦。
 */
function docCoordinateForms(projectRoot) {
  const names = [...new Set([...knowledgeFileNames(projectRoot), ...FRAMEWORK_ARTIFACT_NAMES])];
  return [
    DOC_COORDINATE_HEAD,
    { re: /(?:见|指回|来源|源：)\s*A[1-8]\b/g, hint: '这个编号在本文里不存在——改用事物的名字' },
    { re: /\b[a-z][a-z0-9-]*:[A-Z]{2,10}-\d{2}\b/g,
      hint: '这是仓内文件名加编号——改写为中文规约名（编号进附录的规约判定表）' },
    { re: new RegExp(String.raw`\b(?:[\w-]+\.md|(?:${names.map(escapeRe).join('|')})\.(?:ya?ml|json))\b`, 'g'),
      hint: '仓内文件名不随归档——知识文件写它的中文名，产物文件改述为本文章节名' },
    { re: /§\s*\d[\d.]*/g, hint: '章节号会随重编号变——改用本文章节名' },
  ];
}

function knowledgeFileNames(projectRoot) {
  if (!projectRoot) return [];
  try {
    const k = activeKnowledge(projectRoot);
    return [...k.constraints, ...k.patterns, ...k.facts].map(x => x.file.split('/').pop().replace(/\.md$/, ''));
  } catch (e) {
    // 派生不到不静默：降级只影响「知识文件名」这一种形态，但必须让人看见
    console.error(`[language] 知识文件名派生失败，文件名形态退回为任意 .md 与框架产物名：${e.message}`);
    return [];
  }
}

const FORMS = {
  repo_identifier: { label: '工程标识', hint: '工程标识进附录的那几张表，主叙事写中文业务名' },
  rule_id: { label: '规约编号', hint: '主叙事写中文规约名；编号进附录的规约判定表' },
  doc_coordinate: { label: '文档坐标', hint: DOC_COORDINATE_HEAD.hint },
  source_tag: { label: '来源括注', hint: '「谁定的」进附录的材料清单，不打断正文' },
};

/** 合同里写字符串 = 默认作用域（附录之外），写 `{kind, scope}` = 按它说的。 */
function redlineScopes(decls) {
  const out = new Map();
  for (const decl of decls ?? []) {
    const kind = typeof decl === 'string' ? decl : decl?.kind;
    if (!FORMS[kind]) throw new Error(`章节合同 language_redline.kinds 里的「${kind}」不是认得的红线类别`
      + `（${Object.keys(FORMS).join(' / ')}）`);
    out.set(kind, (typeof decl === 'object' && decl.scope) || 'non_appendix');
  }
  return out;
}

/** HTML 注释里的行（含起止行）：模板指引、待写记号、投影区标记，不是给读者的正文。 */
function commentLines(lines) {
  const out = new Set();
  let open = false;
  lines.forEach((line, i) => {
    if (open || line.includes('<!--')) out.add(i);
    if (line.includes('<!--')) open = !line.slice(line.lastIndexOf('<!--')).includes('-->');
    else if (open && line.includes('-->')) open = false;
  });
  return out;
}

/**
 * 扫描语言红线。一行一类只报一条，命中的几处词一起列出。
 *
 * **规则全部是数据或形态**：类别与作用域来自合同，规约编号来自激活清单，来源括注的词来自合同；
 * 驼峰、下划线、行内代码、文档坐标是形态本身——不从材料里切词表去猜。
 *
 * @param {string} text 全文
 * @param {object} [opts]
 * @param {(string|{kind:string, scope?:string})[]} opts.kinds 合同登记的类别与作用域
 * @param {string} [opts.appendixTitle] 附录章标题（作用域边界）
 * @param {string[]} [opts.ruleIds] 激活清单里的规约编号
 * @param {string[]} [opts.sourceTags] 来源括注的词（合同数据）
 * @param {string} [opts.projectRoot] 工程根：给出则把激活知识的文件名纳入文档坐标
 * @returns {{line:number, kind:string, label:string, hits:string[], hint:string, text:string}[]}
 */
export function scanLanguageRedline(text, opts = {}) {
  const scopes = redlineScopes(opts.kinds);
  const ruleIds = (opts.ruleIds ?? []).filter(id => typeof id === 'string' && id.trim());
  const tags = (opts.sourceTags ?? []).filter(t => typeof t === 'string' && t.trim());
  // 来源括注只认括号里以登记词起头的那种：插在句子中间打断阅读的是它
  const sourceTagRe = tags.length ? new RegExp(`（\\s*(?:${tags.map(escapeRe).join('|')})[^）]*）`, 'g') : null;
  const coordinateForms = scopes.has('doc_coordinate') ? docCoordinateForms(opts.projectRoot) : [];
  const doc = parseDocument(text);
  const appendix = opts.appendixTitle
    ? doc.headings.find(h => h.level === 2 && h.name === normalizeHeading(opts.appendixTitle)) : null;
  const appendixEnd = appendix ? headingEnd(doc, appendix) : -1;
  const comments = commentLines(doc.lines);
  const out = [];
  doc.lines.forEach((raw, i) => {
    if (doc.fenced.has(i) || comments.has(i)) return;
    const inAppendix = !!appendix && i > appendix.at && i < appendixEnd;
    const found = new Map();
    const add = (kind, hit, hint = FORMS[kind].hint) => {
      const scope = scopes.get(kind);
      if (!scope || (inAppendix && scope !== 'all')) return;
      const f = found.get(kind) ?? { hits: [], hint };
      if (!f.hits.some(x => x.includes(hit))) f.hits.push(hit);   // `spec §5.1` 已报就不再单列 `§5.1`
      found.set(kind, f);
    };
    for (const m of raw.matchAll(INLINE_CODE_RE)) add('repo_identifier', m[1]);
    const outsideCode = raw.replace(INLINE_CODE_RE, ' ');
    for (const re of [CAMEL_CASE_RE, SNAKE_CASE_RE]) {
      for (const m of outsideCode.matchAll(re)) add('repo_identifier', m[0]);
    }
    for (const id of ruleIds) if (raw.includes(id)) add('rule_id', id);
    // 来源括注在**表格里不判**：表格的一格里「谁定的」是结构化事实，不构成打断。
    if (sourceTagRe && !raw.trim().startsWith('|')) {
      for (const m of raw.matchAll(sourceTagRe)) add('source_tag', m[0]);
    }
    for (const { re, hint } of coordinateForms) {
      for (const m of raw.matchAll(re)) add('doc_coordinate', m[0].trim(), hint);
    }
    for (const [kind, f] of found) {
      out.push({ line: i + 1, kind, label: FORMS[kind].label, hits: f.hits, hint: f.hint,
        text: raw.trim().slice(0, 100) });
    }
  });
  return out;
}

/** 材料清单那一节的行形态修法。 */
const MATERIAL_LIST_HINTS = {
  material_row: '材料清单用列表不用表：读者只需要知道本文据哪几份材料写成、各自贡献了什么',
  material_link: '每份材料给一条原文链接——读者据此自己把那份材料找出来；'
    + '光写「产品需求文档」他不知道该找谁要哪一份',
};

/**
 * 材料清单那一节的行形态：成列表、每行给得出原文链接。
 *
 * @param {string} body 该小节正文
 * @param {number} baseLine 该小节正文首行在全篇里的行号（报错要指得回去）
 */
export function scanMaterialList(body, baseLine = 0) {
  const hits = [];
  const lines = String(body ?? '').split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const s = lines[i].trim();
    const line = baseLine + i;
    if (s.startsWith('|')) {
      hits.push({ line, kind: 'material_row', hit: s.slice(0, 40),
                  hint: MATERIAL_LIST_HINTS.material_row, text: s.slice(0, 100) });
      continue;
    }
    if (!/^[-*+]\s/.test(s)) continue;
    if (![...s.matchAll(/\[[^\]]*\]\(([^)\s]+)\)/g)].length) {
      hits.push({ line, kind: 'material_link', hit: s.slice(0, 40),
                  hint: MATERIAL_LIST_HINTS.material_link, text: s.slice(0, 100) });
    }
  }
  return hits;
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

/** 把扫描结果渲染成人可读的问题列表 */
export function formatHits(hits, kind) {
  return hits.map(h => {
    if (kind === 'banned') return `第 ${h.line} 行禁用词「${h.term}」（${h.hint}）：${h.text}`;
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
