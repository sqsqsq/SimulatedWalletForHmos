/**
 * 归档件红线与语言红线的判定形态 —— 词与类别在章节合同（`language_redline`），形态在这里。
 *
 * 读者是 story-build check（story.md 与 review.md）、章提交与 hooks/spec/post_check.mjs（spec.md 的文档坐标）。
 * 合同给：红线有哪几类及各自作用域、来源括注的词；本文件给：行内代码、
 * 驼峰与下划线标识、文档坐标、仓内路径这几种**形态本身**。围栏与标题的切法走 `document.mjs`，
 * 本文件不自己认围栏。
 *
 * **工程形态一律运行时推导，不硬编码**：模块目录形态取自 `framework.config.json` 的分层声明，
 * 规约编号与知识文件名取自激活清单。硬编码的快照会在换工程时静默失效。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { activeKnowledge } from '../../../../../hooks/shared/knowledge.mjs';
import { headingEnd, normalizeHeading, parseDocument } from './document.mjs';

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
  hint: '文档坐标指向不随归档的文件或会随重编号漂移的章节号，评审人拿到的只有归档件，打不开它' };

//: 框架产物的文件名：随工程不变。知识文件名随激活清单变，运行时取。
const FRAMEWORK_ARTIFACT_NAMES = ['acceptance', 'spec', 'impact', 'review'];

/**
 * 文档坐标的全部形态。文件名只认**文档**：任意 `.md`，加上知识文件与框架产物的名字——
 * 资源与代码文件名（`string.json`）是工程标识，附录里是它们的正当落点，不在这里拦。
 */
/** 指到别的文档的章节 —— spec 门禁也按这一种判（spec 可以写自己的文件名与 §）。 */
export const CROSS_DOC_COORDINATES = [
  DOC_COORDINATE_HEAD,
];

function docCoordinateForms(projectRoot) {
  const names = [...new Set([...knowledgeFileNames(projectRoot), ...FRAMEWORK_ARTIFACT_NAMES])];
  return [
    ...CROSS_DOC_COORDINATES,
    { re: /\b[a-z][a-z0-9-]*:[A-Z]{2,10}-\d{2}\b/g,
      hint: '按仓内文件名加编号判：编号只在附录的规约表里合法，正文用中文规约名' },
    { re: new RegExp(String.raw`\b(?:[\w-]+\.md|(?:${names.map(escapeRe).join('|')})\.(?:ya?ml|json))\b`, 'g'),
      hint: '按文档文件名判：这些文件不随归档，评审人拿到的只有归档件，打不开它' },
    { re: /§\s*\d[\d.]*/g, hint: '按章节号判：章节号随重编号漂移，归档件里指不回原处' },
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
  repo_identifier: { label: '工程标识',
    hint: '主叙事给评审人读，工程标识只在附录合法：反引号里的文字、驼峰与多段下划线形态的词都按工程标识判' },
  rule_id: { label: '规约编号', hint: '主叙事给评审人读，规约编号只在附录的规约表里合法' },
  doc_coordinate: { label: '文档坐标', hint: DOC_COORDINATE_HEAD.hint },
  source_tag: { label: '来源括注', hint: '以合同登记词起头的括号按来源括注判：它打断主叙事的阅读，这条只在附录之外判' },
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
 * @returns {{line:number, kind:string, label:string, hits:string[], hint:string, why:string, text:string}[]}
 *   `why` 是这一行按什么形态判中的（如「写在反引号里」），没有专门形态时为空
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
    const add = (kind, hit, hint = FORMS[kind].hint, why = '') => {
      const scope = scopes.get(kind);
      if (!scope || (inAppendix && scope !== 'all')) return;
      const f = found.get(kind) ?? { hits: [], hint, whys: new Set() };
      if (!f.hits.some(x => x.includes(hit))) f.hits.push(hit);   // `spec §5.1` 已报就不再单列 `§5.1`
      if (why) f.whys.add(why);
      found.set(kind, f);
    };
    for (const m of raw.matchAll(INLINE_CODE_RE)) add('repo_identifier', m[1], undefined, '写在反引号里');
    const outsideCode = raw.replace(INLINE_CODE_RE, ' ');
    for (const re of [CAMEL_CASE_RE, SNAKE_CASE_RE]) {
      for (const m of outsideCode.matchAll(re)) add('repo_identifier', m[0], undefined, '驼峰或下划线形态');
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
        why: [...f.whys].join('、'), text: raw.trim().slice(0, 100) });
    }
  });
  return out;
}

/**
 * 一行里的 markdown 链接：`[文字](目标)` 与 `![文字](目标)`。
 *
 * 目标有两种合法写法：`<…>` 包起来的（可含空格与括号），或不含空白、括号成对的。
 * 真实文件名常带空格、中文与括号，只认 `[^)\s]+` 会把它们切断或漏掉——那一份材料就从核对里消失。
 * 看得见 `](` 却解析不出目标的，作为 `bad` 带位置交回，由调用方报「写法解析不了」，不猜。
 * 表格里的 `\|` 是转义竖线，目标里还原成 `|`。
 *
 * @returns {{links: {start:number, end:number, text:string, target:string, image:boolean}[], bad: {start:number, text:string}[]}}
 */
export function markdownLinks(line) {
  const s = String(line ?? '');
  const links = [], bad = [];
  let i = 0;
  while ((i = s.indexOf('](', i)) >= 0) {
    const open = s.lastIndexOf('[', i);
    let j = i + 2, target = null;
    if (s[j] === '<') {
      const close = s.indexOf('>', j);
      if (close > j && s[close + 1] === ')') { target = s.slice(j + 1, close); j = close + 2; }
    } else {
      let depth = 0, k = j;
      for (; k < s.length; k++) {
        const c = s[k];
        if (c === '\\') { k++; continue; }
        if (/\s/.test(c)) break;
        if (c === '(') depth++;
        else if (c === ')') { if (!depth) break; depth--; }
      }
      if (s[k] === ')' && k > j) { target = s.slice(j, k); j = k + 1; }
    }
    const from = open >= 0 && s[open - 1] === '!' ? open - 1 : Math.max(open, 0);
    if (target === null) {
      bad.push({ start: from, text: s.slice(from, i + 30) });
      i += 2;
      continue;
    }
    links.push({ start: from, end: j, text: s.slice(open + 1, i), target: target.replace(/\\([|()])/g, '$1'),
      image: s[from] === '!' });
    i = j;
  }
  return { links, bad };
}

/**
 * 一行里的图片引用 —— 身份、去处与断链核对都从这里取完整目标，不各写一套正则。
 *
 * `path` 把 URL 写法的 `%xx` 还原成文件名，才与登记的原名对得上；编码本身坏了为 null，由断链检查报。
 * 外链与内嵌数据 `external` 为真：不是仓内文件，不核身份与断链。
 */
export function imageLinks(line) {
  const { links, bad } = markdownLinks(line);
  const images = links.filter(l => l.image).map(l => ({ alt: l.text, target: l.target,
    external: /^(https?:|data:)/i.test(l.target), path: decodedPath(l.target) }));
  return { images, bad: bad.filter(b => b.text.startsWith('!')) };
}

function decodedPath(target) {
  try { return decodeURI(target); } catch { return null; }
}

/** 文件路径写成合法的链接目标，与 `imageLinks` 的还原互逆：`%` 与尖括号编码，含空白或括号时包进 `<…>`，原名不改。 */
export function markdownTarget(file) {
  const s = String(file ?? '').replace(/%/g, '%25').replace(/</g, '%3C').replace(/>/g, '%3E');
  return /[\s()]/.test(s) ? `<${s}>` : s;
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
    if (kind === 'image') return `第 ${h.line} 行：图片引用「${h.path}」解析不到文件——图片按归档件所在目录解析相对路径`;
    return `第 ${h.line} 行：含仓内路径「${h.path}」（${h.text}）——评审人手上没有这个仓，仓内路径在归档件里打不开`;
  });
}

/**
 * 图片断链：按归档件所在目录解析相对路径，文件不存在即命中。
 *
 * 归档件是交出去给评审者看的——引用写成裸文件名或指向源材料目录，本地打开是红叉，
 * 而正文与装配都不会因此报错：形态守恒只数图的条数，数得到「有一张图」，看不出它打不开。
 *
 * 外链（http/https）与内嵌数据不判：那不是仓内文件。`%xx` 编码坏了的同样打不开，照命中报。
 */
export function scanBrokenImages(text, baseDir, fsMod, pathMod) {
  const hits = [];
  const rows = String(text ?? '').split(/\r?\n/);
  for (let i = 0; i < rows.length; i++) {
    for (const img of imageLinks(rows[i]).images) {
      if (img.external) continue;
      if (img.path === null || !fsMod.existsSync(pathMod.resolve(baseDir, img.path))) {
        hits.push({ line: i + 1, path: img.target });
      }
    }
  }
  return hits;
}
