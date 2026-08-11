/**
 * story-build.mjs — story/review 的装配器（确定性部分，零 AI，零语义判断）
 *
 * ── 装配模型 ────────────────────────────────────────────────────────────
 * story 是**装配产物**，不是一次写成的文档。流程里不存在「写一份完整 story」这个动作：
 *
 *   scaffold  按章节合同把源材料原样注入每个章节文件（章节粒度的完整起手）
 *   build     把章节装配成 story.md，并从决策登记表渲染 review.md
 *   check     重新装配并与磁盘对比，发现对产物的直接手改
 *
 * ── 不变量 ──────────────────────────────────────────────────────────────
 *   源材料只读   注入的 source-material 区块是章节的对照基准，永久留在章节源文件里；
 *                作者只在区块之后写转写正文，build 装配时剔除区块，归档件不含它。
 *                章节完成的判据是「区块之外有正文」，不是「区块已删」。
 *   形态守恒     源材料以图/表表达的内容，终稿保持同类形态且数量不少于源。
 *   决策单源     决策的问题、结论、理由、责任人只存在于 decisions.json；
 *                story 正文只能引用，review 的机器区由它确定性渲染。
 *   产物可验     story.md 带装配指纹，任何直接手改都能被 check 逐字发现。
 *
 * ── 职责边界 ────────────────────────────────────────────────────────────
 * 本脚本只做复制、拼接、计数与渲染，**不判断内容好坏**：
 *   - 注入是整节字节复制，不做语义剥离——脚本一旦判断「该删什么」就会误删无编号事实；
 *   - 形态检查只数 mermaid 围栏与表格数量，不看图画得对不对（那是 S5 的语义判断）；
 *   - 失败模式只有「装配失败」，不会静默改写作者内容。
 *
 * 用法：
 *   node story-build.mjs scaffold --feature <name> [--project-root <abs>] [--force]
 *   node story-build.mjs build    --feature <name> [--project-root <abs>]
 *   node story-build.mjs check    --feature <name> [--project-root <abs>]
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const SRC_OPEN = '<!-- source-material';
const SRC_CLOSE = '<!-- /source-material -->';
const FINGERPRINT_PREFIX = '<!-- assembled-by: story-build.mjs | fingerprint: ';
// review 的机器区与人工区分界：分界线之前由登记表确定性重渲染，之后逐字节保留人工填写。
const HUMAN_ZONE_MARK = '#### 审核结果（由评审人填写）';

// ---------------------------------------------------------------------------
// 基础设施

function parseArgs(argv) {
  const args = { force: false };
  args.command = argv[2] && !argv[2].startsWith('--') ? argv[2] : '';
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--feature') args.feature = argv[++i];
    else if (a === '--project-root') args.projectRoot = argv[++i];
    else if (a === '--force') args.force = true;
  }
  return args;
}

function fail(problems) {
  const list = Array.isArray(problems) ? problems : [problems];
  console.error(`[story-build] 装配未通过（${list.length} 项）：`);
  for (const p of list) console.error(`  - ${p}`);
  process.exit(1);
}

const stripBom = s => s.replace(/^﻿/, '');

function featuresDir(projectRoot) {
  try {
    const cfg = JSON.parse(fs.readFileSync(path.join(projectRoot, 'framework.config.json'), 'utf-8'));
    const dir = cfg?.paths?.features_dir;
    if (typeof dir === 'string' && dir.trim()) return dir.trim();
  } catch {
    /* 回落默认 */
  }
  return 'doc/features';
}

/** 按单个标题关键词提取章节正文（含标题行） */
function extractOne(text, sectionName) {
  const lines = text.split(/\r?\n/);
  let fence = false;
  for (let i = 0; i < lines.length; i++) {
    if (/^\s*(```|~~~)/.test(lines[i])) fence = !fence;
    if (fence) continue;
    const h = lines[i].match(/^(#{1,4})\s+(.*)$/);
    if (!h) continue;
    const title = h[2].replace(/^[\d.、\s]+/, '').trim();
    if (!title.includes(sectionName)) continue;
    const level = h[1].length;
    const body = [lines[i]];
    let inner = false;
    for (let j = i + 1; j < lines.length; j++) {
      if (/^\s*(```|~~~)/.test(lines[j])) inner = !inner;
      if (!inner) {
        const nh = lines[j].match(/^(#{1,6})\s/);
        if (nh && nh[1].length <= level) break;
      }
      body.push(lines[j]);
    }
    return body.join('\n').trim();
  }
  return null;
}

/**
 * 按候选标题词根依次尝试提取；空数组或全部落空时返回整篇（降级注入）。
 * 上游文档的标题措辞因团队而异，故合同声明的是一组词根而非唯一标题；
 * 宁可整篇注入让作者自己筛，也不能让某章拿到空内容。
 * @returns {{text: string, matched: string|null, fallback: boolean}}
 */
export function extractSection(text, section) {
  const candidates = Array.isArray(section) ? section : (section ? [section] : []);
  for (const name of candidates) {
    const hit = extractOne(text, name);
    if (hit != null) return { text: hit, matched: name, fallback: false };
  }
  return { text: text.trim(), matched: null, fallback: true };
}

export function countMermaid(text) {
  return (text.match(/^\s*```mermaid\b/gm) ?? []).length;
}

export function countTables(text) {
  const lines = text.split(/\r?\n/);
  let n = 0;
  for (let i = 0; i < lines.length - 1; i++) {
    if (lines[i].trim().startsWith('|') && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) n++;
  }
  return n;
}

/** 剥离 source-material 区块——它是作者的对照基准，不进归档件 */
export function stripSourceBlocks(raw) {
  const open = SRC_OPEN.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const close = SRC_CLOSE.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return raw.replace(new RegExp(`${open}[\\s\\S]*?${close}`, 'g'), '');
}

/** 去掉源材料区块与其余 HTML 注释后的作者正文 */
export function authorBody(raw) {
  return stripSourceBlocks(raw).replace(/<!--[\s\S]*?-->/g, '').replace(/\n{3,}/g, '\n\n').trim();
}

/**
 * 章内标题整体降一级。
 * 装配器为每章输出 `## 章名`，而作者在章内也习惯用 `##` 写小节（源材料注入的原文就是 `##`）。
 * 不降级则章标题与小节同级，成文里看不出章节边界——十三章结构在读者眼里就消失了。
 * 围栏内的 `#` 是内容（ASCII 图、注释），不动。
 */
export function demoteHeadings(text) {
  let fence = false;
  return text.split('\n').map(line => {
    if (/^\s*(```|~~~)/.test(line)) { fence = !fence; return line; }
    if (fence) return line;
    const m = line.match(/^(#{1,5})(\s+\S)/);
    return m ? `#${line}` : line;
  }).join('\n');
}

function sha256(text) {
  return crypto.createHash('sha256').update(text, 'utf-8').digest('hex');
}

function readJson(file, fallback) {
  if (!fs.existsSync(file)) return fallback;
  return JSON.parse(stripBom(fs.readFileSync(file, 'utf-8')));
}

// 议程措辞：谁该拍板什么归《决策与评审记录》。story 只陈述事实与方案，
// 表态语气一律不入正文——决策先登记、正文只写引用。
const AGENDA_WORDS = ['待确认', '需确认', '须确认', '待产品确认', '需产品确认', '须产品确认',
  '待拍板', '需拍板', '待定', '评审时确认', '评审者应', '有待明确'];

/**
 * spec 的可标识事实必须在 story 有落点——判据是**覆盖**不是逐字一致，
 * 可整合、可改序、可换措辞，但不能少。归档门禁也查这一条；装配时同步查，
 * 作者才能当场知道漏了哪个编号，而不是等到归档才发现。
 */
export function findMissingIdentifiers(specText, storyText) {
  const ids = specText.match(/\b(?:S\d+|F\d+|E\d+|AC-[\w]*\d+|BD-\d+|NFR-\d+)\b/g) ?? [];
  return [...new Set(ids)].filter(id => id && !storyText.includes(id));
}

/** 登记表必填字段：缺任何一项都会渲染出 undefined，产物即报废 */
export function validateDecisions(decisions) {
  const problems = [];
  const seen = new Set();
  decisions.forEach((d, i) => {
    const at = d?.id ? `decisions.json 的 ${d.id}` : `decisions.json 第 ${i + 1} 条`;
    if (!d?.id) problems.push(`${at}：缺 id`);
    else if (seen.has(d.id)) problems.push(`${at}：id 重复`);
    else seen.add(d.id);
    const settled = d?.status === 'settled';
    for (const field of ['question', 'rationale', 'source', 'decider']) {
      if (!String(d?.[field] ?? '').trim()) problems.push(`${at}：缺 ${field}`);
    }
    const valueField = settled ? 'conclusion' : 'proposal';
    if (!String(d?.[valueField] ?? '').trim()) {
      problems.push(`${at}：${settled ? '已定决策' : '开放决策'}缺 ${valueField}`);
    }
    if (d?.status && !['open', 'settled'].includes(d.status)) {
      problems.push(`${at}：status 只能是 open 或 settled，当前为 ${d.status}`);
    }
  });
  return problems;
}

// ---------------------------------------------------------------------------
// 渲染：决策引用与编号附录（story 与 review 是同一份数据的两个投影）

export function renderDecisionRefs(text, decisions) {
  const byId = new Map(decisions.map(d => [d.id, d]));
  const missing = [];
  const out = text.replace(/\{\{(DEC-[\w-]+)\}\}/g, (_m, id) => {
    const dec = byId.get(id);
    if (!dec) {
      missing.push(id);
      return `{{${id}}}`;
    }
    return `《决策与评审记录》——“${dec.question}”`;
  });
  return { text: out, missing };
}

/**
 * 编号引用按上下文渲染：表格单元格内只出 裸编号，散文里才展开「标题（编号）」。
 * 表格的编号列本就该是编号——展开成整句会把列撑垮、读者反而找不到行；
 * 含义由附录承担。作者写法不变，同一个占位符两处都能用。
 */
export function renderIdRefs(text, ids) {
  const byId = new Map(ids.map(x => [x.id, x]));
  const missing = [];
  const out = text.split('\n').map(line => {
    const inTable = line.trimStart().startsWith('|');
    return line.replace(/\{\{ID:([\w-]+)\}\}/g, (_m, id) => {
      const entry = byId.get(id);
      if (!entry) {
        missing.push(id);
        return `{{ID:${id}}}`;
      }
      return inTable ? id : `“${entry.title}（${id}）”`;
    });
  }).join('\n');
  return { text: out, missing };
}

/**
 * story 投影：编号 + 标题与含义（+ 本需求落点，可选）。
 * 落点列只在确有内容时渲染——整列「—」对读者是噪音，而编号加标题含义已足够查义。
 */
export function renderStoryAppendix(ids) {
  if (!ids.length) return '';
  const hasLanding = ids.some(x => String(x.landing ?? '').trim() && String(x.landing).trim() !== '—');
  const head = hasLanding
    ? ['| 编号 | 标题与含义 | 本需求中的结论或落点 |', '|---|---|---|']
    : ['| 编号 | 标题与含义 |', '|---|---|'];
  const rows = ids.map(x => hasLanding
    ? `| ${x.id} | ${x.title} | ${String(x.landing ?? '').trim() || '—'} |`
    : `| ${x.id} | ${x.title} |`);
  return ['## 附录：编号速查', '', ...head, ...rows].join('\n');
}

/**
 * review 投影：只有编号 + 标题与含义（两列），且只含 review 正文实际引用的编号。
 * 这是 R4 的结构性保证——review 里不可能出现第二份需求叙事，因为落点列根本不渲染。
 */
export function renderReviewAppendix(ids, reviewBody) {
  const used = ids.filter(x => new RegExp(`\\b${x.id.replace(/[-]/g, '\\-')}\\b`).test(reviewBody));
  if (!used.length) return '';
  const rows = used.map(x => `| ${x.id} | ${x.title} |`);
  return ['## 附录：编号速查', '', '| 编号 | 标题与含义 |', '|---|---|', ...rows].join('\n');
}

/**
 * 议题块的**机器区**：完全由登记表决定，每次 build 确定性重渲染。
 * 已定决策（status=settled）也照样成块——检视人要先看到「有哪些决策、结论是什么」，
 * 才谈得上反馈对不对；已定不等于不必过目。
 */
export function renderMachineZone(dec) {
  const settled = dec.status === 'settled';
  const lines = [`### ${dec.question}`, ''];
  if (settled) {
    lines.push(`- **当前结论**：${dec.conclusion ?? dec.proposal}`);
  } else {
    lines.push(`- **当前建议**：${dec.proposal}`);
  }
  lines.push(
    `- **为什么这样${settled ? '定' : '建议'}**：${dec.rationale}`,
    `- **同意或修改后会影响什么**：${(dec.impact ?? []).join('、') || '—'}`,
    `- **结论来源**：${dec.source}`,
    `- **请谁确认**：${dec.decider}`,
    '');
  return lines.join('\n');
}

/** 议题块的**人工区**：首版为空表单，此后 build 一个字节都不动它 */
export function renderHumanZone(dec) {
  return [
    HUMAN_ZONE_MARK,
    '',
    '- [ ] **同意当前建议**',
    '- [ ] **有其他意见，需要修改**',
    '  - 修改意见：',
    '- [ ] **暂缓**',
    '  - 暂缓责任人：',
    '  - 完成期限：',
    '  - 是否阻塞执行：',
    '  - 后续动作：',
    '',
    // 归档后读者必须能分辨「真人逐项确认」与「按授权代填」，否则「已确认」是不可追溯的。
    '**确认人**：',
    '',
    '**确认日期**：',
    '',
    '**确认依据**：（非本人当场确认时，写明授权来源）',
    '',
    `<!-- decision: ${dec.id} -->`,
  ].join('\n');
}

export function renderDecisionBlock(dec) {
  return `${renderMachineZone(dec)}\n${renderHumanZone(dec)}`;
}

/** 从既有 review 里切出某议题的人工区（人工填写内容的唯一真源） */
export function extractHumanZone(reviewText, id) {
  const mark = `<!-- decision: ${id} -->`;
    const end = reviewText.indexOf(mark);
  if (end < 0) return null;
  const zoneStart = reviewText.lastIndexOf(HUMAN_ZONE_MARK, end);
  if (zoneStart < 0) return null;
  return reviewText.slice(zoneStart, end + mark.length);
}

/** 定位某议题块的整体范围（机器区起点 → 该块的 decision 标记结尾） */
function findBlockRange(reviewText, id) {
  const mark = `<!-- decision: ${id} -->`;
  const end = reviewText.indexOf(mark);
  if (end < 0) return null;
  const zoneStart = reviewText.lastIndexOf(HUMAN_ZONE_MARK, end);
  if (zoneStart < 0) return null;
  // 机器区起点：该人工区之前最近的 `### ` 标题
  const headStart = reviewText.lastIndexOf('\n### ', zoneStart);
  return { start: headStart < 0 ? zoneStart : headStart + 1, end: end + mark.length };
}

// ---------------------------------------------------------------------------

export function createContext(args) {
  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  // scripts → story → skills → extensions → doc → 实例根
  const projectRoot = path.resolve(
    args.projectRoot ?? path.join(scriptDir, '..', '..', '..', '..', '..'));
  const skillRoot = path.join(scriptDir, '..');
  const contract = readJson(path.join(skillRoot, 'contracts', 'story-chapters.json'), null);
  if (!contract) fail('章节合同缺失：contracts/story-chapters.json');
  const featureRoot = path.join(projectRoot, featuresDir(projectRoot), args.feature);
  const srcDir = path.join(featureRoot, 'AR', 'story-src');
  return {
    args, projectRoot, contract, featureRoot, srcDir,
    chapterDir: path.join(srcDir, 'chapters'),
    decisionsPath: path.join(srcDir, 'decisions.json'),
    idsPath: path.join(srcDir, 'ids.json'),
    storyPath: path.join(featureRoot, 'AR', 'story.md'),
    reviewPath: path.join(featureRoot, 'AR', 'review.md'),
    chapterFile: ch => path.join(srcDir, 'chapters', `${ch.id}.md`),
  };
}

function loadSourceDocs(ctx) {
  const docs = {};
  for (const [key, rel] of Object.entries(ctx.contract.sources)) {
    const p = path.join(ctx.featureRoot, rel);
    docs[key] = fs.existsSync(p) ? stripBom(fs.readFileSync(p, 'utf-8')) : null;
  }
  return docs;
}

// ---------------------------------------------------------------------------
// scaffold：按合同注入源材料，建立章节起手文件

function scaffold(ctx) {
  const { args, projectRoot, contract, featureRoot, chapterDir, decisionsPath, idsPath,
    chapterFile } = ctx;
  if (!fs.existsSync(featureRoot)) fail(`feature 目录不存在：${featureRoot}`);
  fs.mkdirSync(chapterDir, { recursive: true });

  const docs = loadSourceDocs(ctx);
  const created = [];
  const notes = [];
  const problems = [];

  for (const ch of contract.chapters) {
    const target = chapterFile(ch);
    if (fs.existsSync(target) && !args.force) {
      notes.push(`已存在，跳过：${path.relative(projectRoot, target)}`);
      continue;
    }
    const injected = [];
    for (const input of ch.inputs ?? []) {
      const text = docs[input.doc];
      if (text == null) {
        notes.push(`${ch.id}：源文档 ${input.doc} 不存在，跳过该输入`);
        continue;
      }
      const { text: section, matched, fallback } = extractSection(text, input.section);
      const label = fallback
        ? `${input.doc} / 整篇（候选标题均未命中，已降级注入全文）`
        : `${input.doc} / ${matched}`;
      if (fallback && (input.section ?? []).length) {
        notes.push(`${ch.id}：${input.doc} 候选标题 ${JSON.stringify(input.section)} 均未命中，已降级注入整篇`);
      }
      injected.push(`${SRC_OPEN}: ${label} -->\n${section}\n${SRC_CLOSE}`);
    }
    // 声明了输入却一份都没注入 = 章节起手为空，作者将无源可转写。
    // 这类缺料必须显式失败：告警会被忽略，空章节则要到装配末端才暴露。
    if ((ch.inputs ?? []).length && !injected.length) {
      problems.push(`${ch.id}（${ch.title}）：声明了 ${ch.inputs.length} 个输入，但一个都无法注入`);
      continue;
    }
    const form = Object.entries(ch.form ?? {}).map(([k, v]) => `${k}=${v}`).join(', ') || '无强制形态';
    const header = [
      `<!-- chapter: ${ch.id} | title: ${ch.title} | form: ${form} -->`,
      '<!-- 必答（写到足以支撑这些判断为止，不设篇幅上限）：',
      ...(ch.must_answer ?? []).map(q => `- ${q}`),
      '-->',
      ...(ch.transcribe_note ? ['<!-- 本章写法：' + ch.transcribe_note + ' -->'] : []),
      '<!-- 写法：在下方 source-material 区块**之后**写转写正文；区块本身请原样保留，',
      '     它是对照基准，装配时会被自动剔除，不会进入归档件。',
      '     开放点与已定决策都不要在正文下结论——先登记 decisions.json，正文写 {{DEC-00X}} 引用。 -->',
      '',
    ].join('\n');
    fs.writeFileSync(target,
      `${header}${injected.join('\n\n')}\n\n<!-- 以下为转写正文 -->\n\n`, 'utf-8');
    created.push(path.relative(projectRoot, target));
  }

  if (problems.length) fail(problems);

  if (!fs.existsSync(decisionsPath)) {
    fs.writeFileSync(decisionsPath, JSON.stringify({ decisions: [] }, null, 2) + '\n', 'utf-8');
    created.push(path.relative(projectRoot, decisionsPath));
  }
  if (!fs.existsSync(idsPath)) {
    fs.writeFileSync(idsPath, JSON.stringify({ ids: [] }, null, 2) + '\n', 'utf-8');
    created.push(path.relative(projectRoot, idsPath));
  }

  console.log(`[story-build] ✅ scaffold 完成，${created.length} 个文件：`);
  for (const f of created) console.log(`  + ${f}`);
  for (const n of notes) console.log(`  ! ${n}`);
  console.log('[story-build] 下一步：在各章 source-material 区块之后转写 → 登记 decisions.json / ids.json → build。');
}

// ---------------------------------------------------------------------------
// build：装配 story.md，渲染 review.md

export function assemble(ctx) {
  const { args, contract, chapterFile } = ctx;
  const problems = [];
  const decisions = readJson(ctx.decisionsPath, { decisions: [] }).decisions ?? [];
  const ids = readJson(ctx.idsPath, { ids: [] }).ids ?? [];
  const parts = [];
  const formReport = [];
  const docs = loadSourceDocs(ctx);
  problems.push(...validateDecisions(decisions));

  for (const ch of contract.chapters) {
    const target = chapterFile(ch);
    if (!fs.existsSync(target)) {
      problems.push(`缺章：${ch.id}（${ch.title}）—— 先跑 scaffold 并完成转写`);
      continue;
    }
    const raw = stripBom(fs.readFileSync(target, 'utf-8'));
    const body = authorBody(raw);
    if (!body) {
      problems.push(`${ch.id}（${ch.title}）：源材料区块之外没有转写正文`);
      continue;
    }

    // 形态检查：只数数量，不看内容。
    const sourceText = (ch.inputs ?? [])
      .map(i => (docs[i.doc] ? extractSection(docs[i.doc], i.section).text : ''))
      .join('\n');
    for (const [kind, rule] of Object.entries(ch.form ?? {})) {
      const counter = kind === 'mermaid' ? countMermaid : countTables;
      const actual = counter(body);
      const sourceCount = counter(sourceText);
      let required = 0;
      // inherit = 数量守恒：源有几张图，终稿就得有几张。
      // 只要求「至少一张」等于允许静默丢图，与形态守恒不是同一回事。
      if (rule === 'inherit') required = sourceCount;
      else if (typeof rule === 'string' && rule.startsWith('>=')) required = Number(rule.slice(2));
      if (actual < required) {
        problems.push(
          `${ch.id}（${ch.title}）：${kind} 数量 ${actual} < 要求 ${required}`
          + (rule === 'inherit' ? `（源材料含 ${sourceCount} 个，形态与数量均不得降级）` : ''));
      }
      formReport.push({ chapter: ch.id, kind, actual, required, source: sourceCount });
    }

    // 裸决策编号：DEC-00X 是评审登记表的内部标识，只能以 {{DEC-00X}} 占位出现、由装配器
    // 渲染成可读指向。写成字面量就会原样漏进归档件，评审者读到一个没有定义的编号。
    const bare = [...body.replace(/\{\{DEC-[\w-]+\}\}/g, '').matchAll(/\bDEC-[\w-]+\b/g)];
    if (bare.length) {
      problems.push(
        `${ch.id}（${ch.title}）：正文出现裸决策编号 ${[...new Set(bare.map(m => m[0]))].join('、')}`
        + '——须写成 {{DEC-00X}} 占位，由装配器渲染为可读指向');
    }

    parts.push(`## ${ch.title}\n\n${demoteHeadings(body)}`);
  }

  let storyBody = parts.join('\n\n');
  const dec = renderDecisionRefs(storyBody, decisions);
  const idr = renderIdRefs(dec.text, ids);
  storyBody = idr.text;
  for (const id of new Set([...dec.missing, ...idr.missing])) {
    problems.push(`悬空引用 {{${id}}}：未在 decisions.json / ids.json 登记`);
  }

  const appendix = renderStoryAppendix(ids);
  const title = `# ${args.feature} — 需求评审叙事`;
  const bodyText = [title, '', storyBody, appendix ? `\n${appendix}` : ''].join('\n').trimEnd();

  // 以下三条都扫**最终装配结果**而非章节正文：附录、决策引用、编号速查都是装配器
  // 渲染出来的，只查章节会留下盲区。
  if (/\bundefined\b/.test(bodyText)) {
    const line = bodyText.split('\n').findIndex(l => /\bundefined\b/.test(l)) + 1;
    problems.push(`story 渲染结果含字面量 undefined（首次出现在第 ${line} 行）：某处取到了空字段`);
  }

  for (const word of AGENDA_WORDS) {
    if (!bodyText.includes(word)) continue;
    const line = bodyText.split('\n').findIndex(l => l.includes(word)) + 1;
    problems.push(
      `story 出现议程措辞「${word}」（第 ${line} 行）——表态归《决策与评审记录》。`
      + '若来自规约原文，在 ids.json 里把含义改写为中性事实陈述，把待决部分登记为决策');
  }

  const specText = docs.SPEC ?? '';
  const missingIds = specText ? findMissingIdentifiers(specText, bodyText) : [];
  if (missingIds.length) {
    problems.push(
      `需求规格的可标识事实未全部落入 story：缺 ${missingIds.join('、')}`
      + '（可整合、可改序、可换措辞，但不能少）');
  }
  const fingerprint = sha256(bodyText);
  const storyText = `${bodyText}\n\n${FINGERPRINT_PREFIX}${fingerprint} -->\n`;

  return { problems, storyText, bodyText, fingerprint, decisions, ids, formReport };
}

/**
 * review 渲染：机器区每次按登记表重算，人工区逐字节保留。
 * 单源意味着登记表变了产物就得跟着变——「已存在就跳过」会让两者各说各话。
 */
export function renderReview(ctx, decisions, ids) {
  const { args, reviewPath } = ctx;
  const header = [
    `# ${args.feature} 评审记录`,
    '',
    '## 如何填写本评审记录',
    '',
    '每个议题只勾选一个审核结果：',
    '',
    '- **同意当前建议**：接受当前结论，不需要修改。',
    '- **有其他意见，需要修改**：填写具体修改意见；修改完成后需要二次复核。',
    '- **暂缓**：填写责任人、完成期限、是否阻塞执行与后续动作。',
    '',
    '「已定决策」一节里的结论已有上游依据或已由起草方给出，仍请逐条过目——',
    '你需要先知道本需求做了哪些决策、结论是什么，才谈得上判断它们对不对。',
    '',
    '请勿删除原结论或覆盖历史意见。',
    '',
    '',
  ].join('\n');

  const existing = fs.existsSync(reviewPath) ? stripBom(fs.readFileSync(reviewPath, 'utf-8')) : null;
  const open = decisions.filter(d => d.status !== 'settled');
  const settled = decisions.filter(d => d.status === 'settled');
  const appended = [];
  const refreshed = [];

  const renderOne = d => {
    const human = existing ? extractHumanZone(existing, d.id) : null;
    if (existing && human) refreshed.push(d.id); else appended.push(d.id);
    return `${renderMachineZone(d)}\n${human ?? renderHumanZone(d)}`;
  };

  const sections = [];
  if (open.length) {
    sections.push('## 请逐项留下你的结论', '',
      open.map(renderOne).join('\n\n---\n\n'), '');
  }
  if (settled.length) {
    sections.push('## 已定决策（请逐条过目）', '',
      settled.map(renderOne).join('\n\n---\n\n'), '');
  }

  const tail = ['## 下一步', '',
    '- [ ] **进入执行**：每个议题都已勾选一项；所有「需要修改」已回写并二次复核；无阻塞暂缓。',
    '- [ ] **修改后重新评审**：列出需要修改的议题与责任人。', '',
    '**状态**：草稿（待开发确认）', ''].join('\n');

  const text = `${header}${sections.join('\n')}\n${tail}`;
  return { text: refreshAppendix(text, ids), appended, refreshed };
}

/**
 * 附录是机器渲染区：按 review 正文实际引用的编号重算，插在状态行之前。
 * 它只有「编号 / 标题与含义」两列——落点列不渲染，review 结构上不可能出现第二份需求叙事。
 */
export function refreshAppendix(text, ids) {
  const marker = '## 附录：编号速查';
  const statusIdx = text.indexOf('**状态**');
  const startIdx = text.indexOf(marker);
  const bodyForScan = startIdx >= 0
    ? text.slice(0, startIdx) + (statusIdx > startIdx ? text.slice(statusIdx) : '')
    : text;
  const appendix = renderReviewAppendix(ids, bodyForScan);
  const block = appendix ? `${appendix}\n\n` : '';

  if (startIdx >= 0) {
    const end = statusIdx > startIdx ? statusIdx : text.length;
    return text.slice(0, startIdx) + block + text.slice(end);
  }
  if (statusIdx >= 0) return text.slice(0, statusIdx) + block + text.slice(statusIdx);
  return block ? `${text.trimEnd()}\n\n${block}` : text;
}

function build(ctx) {
  const { projectRoot, contract, storyPath, reviewPath } = ctx;
  const result = assemble(ctx);
  if (result.problems.length) fail(result.problems);

  fs.mkdirSync(path.dirname(storyPath), { recursive: true });
  fs.writeFileSync(storyPath, result.storyText, 'utf-8');

  const review = renderReview(ctx, result.decisions, result.ids);
  if (/\bundefined\b/.test(review.text)) {
    fail(['review 渲染结果含字面量 undefined：某处取到了空字段']);
  }
  fs.writeFileSync(reviewPath, review.text, 'utf-8');

  const open = result.decisions.filter(d => d.status !== 'settled').length;
  console.log(`[story-build] ✅ 已装配：${path.relative(projectRoot, storyPath)}`);
  console.log(`[story-build]    章节 ${contract.chapters.length} 章｜决策 ${result.decisions.length} 条`
    + `（开放 ${open}／已定 ${result.decisions.length - open}）｜编号 ${result.ids.length} 条`);
  if (review.refreshed.length) {
    console.log(`[story-build]    review 机器区已重渲染：${review.refreshed.join('、')}（人工填写内容未改动）`);
  }
  if (review.appended.length) {
    console.log(`[story-build]    review 新增议题：${review.appended.join('、')}`);
  }
  console.log(`[story-build]    fingerprint=${result.fingerprint.slice(0, 16)}`);
}

// ---------------------------------------------------------------------------
// check：重新装配并与磁盘对比

function check(ctx) {
  const { projectRoot, storyPath, reviewPath } = ctx;
  const problems = [];
  if (!fs.existsSync(storyPath)) fail(`story.md 不存在：${storyPath}（先跑 build）`);
  const onDisk = stripBom(fs.readFileSync(storyPath, 'utf-8'));

  const result = assemble(ctx);
  problems.push(...result.problems);

  // 逐字比对指纹之前的正文本体：只认「指纹串还在」会漏掉追加在注释之后的手改。
  const idx = onDisk.indexOf(FINGERPRINT_PREFIX);
  if (idx < 0) {
    problems.push('story.md 没有装配指纹：它不是 build 的产物，或指纹被删除');
  } else {
    const bodyOnDisk = onDisk.slice(0, idx).trimEnd();
    const tail = onDisk.slice(idx).trim();
    if (!/^<!-- assembled-by: story-build\.mjs \| fingerprint: [0-9a-f]{64} -->$/.test(tail)) {
      problems.push('story.md 装配指纹之后还有内容：产物被直接追加修改');
    }
    if (bodyOnDisk !== result.bodyText) {
      problems.push('story.md 与章节源不一致：产物被直接手改，或章节改后未重新 build');
    }
  }

  if (!fs.existsSync(reviewPath)) {
    problems.push(`review.md 不存在：${reviewPath}`);
  } else {
    const review = stripBom(fs.readFileSync(reviewPath, 'utf-8'));
    for (const d of result.decisions) {
      const range = findBlockRange(review, d.id);
      if (!range) {
        problems.push(`review 缺少议题：${d.id}`);
        continue;
      }
      // 机器区必须等于登记表当前渲染结果——否则登记表改了、review 还留旧值。
      const block = review.slice(range.start, range.end);
      const machineOnDisk = block.slice(0, block.indexOf(HUMAN_ZONE_MARK)).trim();
      if (machineOnDisk !== renderMachineZone(d).trim()) {
        problems.push(`review 议题 ${d.id} 的机器区与 decisions.json 不一致：改了登记表后须重新 build`);
      }
    }
    const known = new Set(result.decisions.map(d => d.id));
    for (const m of review.matchAll(/<!-- decision: ([\w-]+) -->/g)) {
      if (!known.has(m[1])) problems.push(`review 含未登记议题：${m[1]}`);
    }
  }

  if (problems.length) fail(problems);
  console.log(`[story-build] ✅ 装配一致：${path.relative(projectRoot, storyPath)}`);
  console.log(`[story-build]    fingerprint=${result.fingerprint.slice(0, 16)}`);
}

function main() {
  const args = parseArgs(process.argv);
  if (!['scaffold', 'build', 'check'].includes(args.command)) {
    fail('用法：story-build.mjs <scaffold|build|check> --feature <name>');
  }
  if (!args.feature) fail('缺少 --feature <name>');
  const ctx = createContext(args);
  if (args.command === 'scaffold') scaffold(ctx);
  else if (args.command === 'build') build(ctx);
  else check(ctx);
}

// 只在被直接执行时跑 CLI；被测试 import 时只暴露纯函数，无副作用。
if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  main();
}
