/**
 * story 的登记、核对与校验 —— 四个命令，围绕**一份文档写成**这件事。
 *
 * ## 与 1.0 逐章生产线的区别
 *
 * 1.0 的做法是先生成逐章任务书（每章一份取材路标 + 逐章必答），各章分别写完再装配，守恒判「每章把取材节的每行表格/数值/反引号写全」。后果是**同一个事实
 * 被四个章节合同各指一次，于是被强制写四遍**。
 *
 * 这里没有逐章任务书、没有逐章文件、没有装配。成文分两步：**先分配后渲染**——
 * 作者给每个来源单元定一个落点（`audit.json`），再按合同顺序一次写一章、追加落盘。
 * 守恒改判「材料里每个可核对 token 在 story 整篇有落点」。
 *
 * **区别不在按不按章写，在谁来分配**：1.0 由合同按关键词把材料路由给章，同一个事实
 * 被四个章节合同各指一次；这里由作者分配、机器强制「一个单元一条记录一个落点」，
 * 事实只出现一次。逐章渲染换来的是每步输出有界、写完即落盘、断了能续。
 *
 * ## 四个命令
 *
 * | 命令 | 做什么 |
 * |------|--------|
 * | `init`  | 枚举来源单元 → `source-units.json`；建 `decisions.json` 骨架 |
 * | `audit` | 三态核对：`at` / `covered_by` / `machine_facing`，写 `audit.json` |
 * | `check` | 章标题与顺序、整篇 token 守恒、编号形态、图与 diagram 落点、决策六类齐 |
 * | `build` | 由 `decisions.json` 渲染 `review.md`（机器区重算、人工区逐字节保留） |
 *
 * `audit.json` 只认三态，**没有自由文本理由**——上一版那个 `reason` 字段只判非空，
 * 实测 161/272 个单元「不进」、理由去重后只有 2 种，等于给漏写开了一个合法出口。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { enumerateUnits, knowledgeUnits, linkDuplicates } from './source-units.mjs';
import {
  baseLayerIds, formatHits, scanBannedTerms, scanBrokenImages, scanDanglingRefs,
  scanLanguageRedline, scanLocalPaths, scanReadability,
} from './lint-rules.mjs';
import { activeKnowledge } from '../../../hooks/shared/knowledge.mjs';
import {
  escapeCell, extractFreeformZone, extractHumanZone, findBlockRange,
  renderFreeformSection, renderHumanZone, renderMachineZone,
} from './review-render.mjs';

const COMMANDS = ['init', 'audit', 'check', 'build'];

/** 裁决的取值与引文下限——同 verifier-report 的 evidenceVerified 口径。 */
const VERDICT_WORDS = ['讲清', '未讲清'];
const MIN_QUOTE = 12;

/** 规约判定表的取值封闭；整域不适用时该域内条目不必逐条列。 */
const DOMAIN_NA = '整域不适用';
const KNOWLEDGE_VERDICTS = ['命中', '不命中', DOMAIN_NA];

/** 决策件必须扫过的六类议题——少扫一类不是「没有」，是「没想这件事」。 */
const SCANNED_CATEGORIES = [
  '需求与范围', '交互与界面', '技术方案与依赖', '约束规约命中项', '异常与风险', '上线与协同',
];

function fail(msg) {
  process.stderr.write(`[story-build] ${msg}\n`);
  process.exit(1);
}

function parseArgs(argv) {
  const args = { command: argv[2] && !argv[2].startsWith('--') ? argv[2] : '' };
  for (let i = 3; i < argv.length; i++) {
    if (argv[i] === '--feature') args.feature = argv[++i];
    else if (argv[i] === '--project-root') args.projectRoot = argv[++i];
  }
  return args;
}

function readText(file) {
  try { return fs.readFileSync(file, 'utf-8').replace(/^﻿/, ''); } catch { return null; }
}

function readJson(file, fallback) {
  const t = readText(file);
  if (t === null) return fallback;
  try { return JSON.parse(t); } catch { return fallback; }
}

function writeJson(file, data) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(data, null, 2)}\n`, 'utf-8');
}

function featuresDir(projectRoot) {
  const cfg = readJson(path.join(projectRoot, 'framework.config.json'), null);
  const dir = cfg?.paths?.features_dir;
  return typeof dir === 'string' && dir.trim() ? dir.trim() : 'doc/features';
}

function createContext(args) {
  if (!args.feature) fail('缺 --feature');
  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  const projectRoot = path.resolve(
    args.projectRoot ?? path.join(scriptDir, '..', '..', '..', '..', '..'));
  const skillRoot = path.join(scriptDir, '..');
  const contract = readJson(path.join(skillRoot, 'contracts', 'story-chapters.json'), null);
  if (!contract) fail('章节合同缺失：contracts/story-chapters.json');
  if (!Array.isArray(contract.chapters) || contract.chapters.length === 0) {
    // 派生为空要出声，不能当作「没有章节要求」通过（G7）
    fail('章节合同解析不出任何章节——合同坏了，不是「本需求没有章节」');
  }
  const featureRoot = path.join(projectRoot, featuresDir(projectRoot), args.feature);
  const srcDir = path.join(featureRoot, 'AR', 'story-src');
  return {
    args, projectRoot, contract, featureRoot, srcDir,
    unitsPath: path.join(srcDir, 'source-units.json'),
    auditPath: path.join(srcDir, 'audit.json'),
    decisionsPath: path.join(srcDir, 'decisions.json'),
    verdictsPath: path.join(srcDir, 'story-verdicts.md'),
    storyPath: path.join(featureRoot, 'AR', 'story.md'),
    reviewPath: path.join(featureRoot, 'AR', 'review.md'),
  };
}

/**
 * 材料文件：合同 `sources` 声明的那几份，存在即读。
 *
 * 两种写法都认：`"PRD": "RR/prd.md"`（人写的材料，整篇都是事实），
 * 或 `{ path, notes: [...] }`——`notes` 是「按生成它的模板约定，这几类单元不是事实」，
 * 比如 spec.md 里的 `>` 块只承载登记项与作业说明。判据来自模板约定，不来自样本形状。
 */
function sourceDocs(ctx) {
  const out = [];
  for (const [doc, decl] of Object.entries(ctx.contract.sources ?? {})) {
    const rel = typeof decl === 'string' ? decl : decl?.path;
    if (!rel) continue;
    const abs = path.join(ctx.featureRoot, rel);
    const text = readText(abs);
    if (text !== null) {
      out.push({ doc, rel, text, notes: typeof decl === 'string' ? [] : (decl.notes ?? []) });
    }
  }
  return out;
}

// --------------------------------------------------------------------------
// init：枚举来源单元 + 建决策骨架
// --------------------------------------------------------------------------

/**
 * 组装 token 排除函数——**规则全部来自合同数据**，本文件不写任何具体词。
 *
 * 只排除 `id_shapes.drop`（`F1` / `S2` / `DEC-3` 这类仓内工作编号）：check ③ 明令它们
 * 不许出现在 story 里，那它们就不能同时是守恒要求出现的 token。两条判据要求相反时，
 * 作者怎么写都是错的。
 *
 * **模块名与单据号不再排除。** 上一版把它们排掉，是因为守恒要求 token 出现在 story，
 * 而红线不许写模块名——两条相斥，只能让守恒让步。现在附录成了工程标识的唯一落点：
 * 模块名写进附录的工程范围表，守恒在那里核得到，语言红线只管附录之外的主叙事。
 * 相斥消失了，排除也就没必要了——**排除掉的东西是不受任何判据保护的**，
 * 那正是「模块名从 story 里整个消失也没人发现」的成因。
 */
function buildTokenExclusion(ctx) {
  const res = [];
  for (const p of ctx.contract.id_shapes?.drop ?? []) {
    try { res.push(new RegExp(p)); } catch { /* 形态写错不该让枚举崩掉 */ }
  }
  if (!res.length) return null;
  return (t) => res.some(re => re.test(t));
}

function cmdInit(ctx) {
  const docs = sourceDocs(ctx);
  if (!docs.length) {
    fail(`一份材料都读不到（合同 sources 指向 ${Object.values(ctx.contract.sources ?? {}).join('、')}）`);
  }
  // 只把 `keep` 的编号形态交给枚举器：`drop` 的那些不该进 story，也就不该成为守恒对象
  const idShapes = [...(ctx.contract.id_shapes?.keep ?? [])];
  const excludeToken = buildTokenExclusion(ctx);
  const units = [];
  for (const d of docs) {
    units.push(...enumerateUnits(d.text, d.doc, {
      idShapes,
      excludeToken,
      machineFacing: ctx.contract.machine_facing ?? {},
      templateNotes: d.notes,
    }));
  }
  if (!units.length) fail('材料切不出任何来源单元——枚举器或材料有问题，不是「材料是空的」');

  // 激活规约条目也是来源单元：逐条判定要和材料里的事实走同一条守恒链
  try {
    const k = activeKnowledge(ctx.projectRoot);
    const ku = knowledgeUnits(k.entries);
    if (!ku.length) fail('激活清单派生不出规约条目——不是「本需求没有规约」，是派生坏了');
    units.push(...ku);
  } catch (e) {
    fail(`激活知识派生失败：${e.message}——判定表无从核对，不能当作「没有规约」通过`);
  }
  linkDuplicates(units);

  writeJson(ctx.unitsPath, {
    generated_from: docs.map(d => d.rel),
    unit_count: units.length,
    token_count: units.reduce((n, u) => n + u.tokens.length, 0),
    units,
  });

  const decisions = readJson(ctx.decisionsPath, null);
  if (!decisions) {
    writeJson(ctx.decisionsPath, {
      scanned_categories: Object.fromEntries(
        SCANNED_CATEGORIES.map(c => [c, { entries: [], none_reason: '' }])),
      decisions: [],
    });
  }

  const noToken = units.filter(u => !u.machine_facing && u.tokens.length === 0).length;
  process.stdout.write(
    `[story-build init] ${units.length} 个单元、${units.reduce((n, u) => n + u.tokens.length, 0)} 个 token`
    + `（机器面 ${units.filter(u => u.machine_facing).length} 个；`
    + `无 token ${noToken} 个——它们的落点靠正文片段核，核不住的交裁决者逐条裁）\n`);
}

// --------------------------------------------------------------------------
// audit：三态核对
// --------------------------------------------------------------------------

/** story 正文按 `## ` 标题切节。 */
function storySections(storyText) {
  const out = [];
  let cur = null;
  for (const line of String(storyText ?? '').split(/\r?\n/)) {
    const m = line.trim().match(/^##\s+(.+)$/);
    if (m) {
      cur = { title: m[1].trim(), body: [] };
      out.push(cur);
      continue;
    }
    if (cur) cur.body.push(line);
  }
  return out.map(s => ({ title: s.title, text: s.body.join('\n') }));
}

/** 附录那一章（合同里标了 `appendix` 的那个）。没有就返回 null。 */
function appendixChapter(contract) {
  return (contract.chapters ?? []).find(c => c.appendix) ?? null;
}

/**
 * 从一章的正文里切出某个 `###` 小节。
 *
 * 附录一章里并排放着接口表、数据表、规约判定表、追溯表——它们列数相近，
 * 在整章正文里找「四列表行」会把接口行也当成判定行读进来。所以按小节切。
 */
function subsectionText(sectionText, name) {
  const lines = String(sectionText ?? '').split(/\r?\n/);
  const body = [];
  let hit = false;
  for (const line of lines) {
    const m = line.trim().match(/^###\s+(.+)$/);
    if (m) {
      if (hit) break;
      hit = m[1].trim() === name;
      continue;
    }
    if (hit) body.push(line);
  }
  return hit ? body.join('\n') : null;
}

/**
 * 机器给落点：单元的 token 在哪一节命中得最多，`at` 就填哪一节。
 *
 * **不要求全部 token 同节**——上一版正是这么判的，于是「把一件事分两处讲清楚」
 * 被判成无落点，作者只好把它们硬塞进同一段。
 */
function autoPlace(unit, sections) {
  if (unit.tokens.length) {
    let best = null;
    for (const sec of sections) {
      const hit = unit.tokens.filter(t => sec.text.includes(t)).length;
      if (hit > 0 && (!best || hit > best.hit)) best = { title: sec.title, hit };
    }
    if (best) return best;
  }
  // 无 token 的单元（纯中文的表格行、引用句）：拿正文片段做**精确子串**匹配兜底。
  // 不是相似度——相似度会把「差不多的话」判成同一件事，那正是守恒最怕的。
  // 匹配不到仍然三态皆空，由作者显式交代：机器把能判的判了，判不了的不假装判了。
  for (const frag of contentFragments(unit.text)) {
    for (const sec of sections) {
      if (norm(sec.text).includes(frag)) return { title: sec.title, hit: 0, by: 'text' };
    }
  }
  return null;
}

/** 规范化：去空白与标点——「点了提交、但没收到回执」与原文只差标点时仍算同一句。 */
function norm(s) {
  return String(s ?? '').replace(/[\s，。、；：!?！？（）()「」【】]/g, '');
}

/** 单元正文里够长的片段（表格行按单元格切），≥8 字才用——短片段碰巧命中太多。 */
function contentFragments(text) {
  return String(text ?? '')
    .split('｜')
    .map(norm)
    .filter(f => f.length >= 8)
    .sort((a, b) => b.length - a.length);
}

function cmdAudit(ctx) {
  const doc = readJson(ctx.unitsPath, null);
  if (!doc) fail(`还没有来源单元清单，先跑 init：${ctx.unitsPath}`);
  // story.md 还不存在 = **一章都没渲染**，不是错误：分配先于正文，
  // 这一步正是用来核「每个单元都分到了地方」的。渲染过程中它是「渲染了几章」的中间态。
  const storyText = readText(ctx.storyPath) ?? '';
  const sections = storySections(storyText);
  const prev = readJson(ctx.auditPath, { records: [] });
  const prevByKey = new Map((prev.records ?? []).map(r => [r.key, r]));

  const records = [];
  for (const u of doc.units) {
    if (u.machine_facing) {
      records.push({ key: u.key, machine_facing: true });
      continue;
    }
    const old = prevByKey.get(u.key);
    // 作者填的 covered_by 保留——它是作者的判断，机器只核不重算
    if (old?.covered_by) {
      records.push({ key: u.key, covered_by: old.covered_by });
      continue;
    }
    // 机器每次重算：story 改了落点就该跟着变。**不沿用上一次的机器结果**，
    // 否则 story 删了一段、落点还留在那儿，守恒就成了历史快照。
    const placed = autoPlace(u, sections);
    if (placed) {
      records.push({ key: u.key, at: placed.title, by: 'machine' });
      continue;
    }
    // 机器定不了：保留作者填的章名，由裁决者逐条裁「讲清没讲清」。
    // **不沿用机器上次的结果**——`by` 标记就是为了让这两种来源不再混成一个 `at`。
    //
    // `by` 缺省即作者：它是**机器写的来源标记**，分配时作者只写 `at`，
    // 机器核实通过才盖上 `by: machine`。要求作者自己填 `by: author` 等于把
    // 内部记账字段摊给他记，漏填一次那条就悄悄变成「无落点」。
    if (old?.at && old.by !== 'machine') {
      records.push({ key: u.key, at: old.at, by: 'author' });
      continue;
    }
    records.push({ key: u.key });                       // 三态皆空 → check 会报它
  }
  writeJson(ctx.auditPath, { records });

  const open = records.filter(r => !r.at && !r.covered_by && !r.machine_facing);
  process.stdout.write(
    `[story-build audit] ${records.length} 条；待处理 ${open.length} 条`
    + `（给它们分配落点 at，或标 covered_by 指向已分配的另一条）\n`);
  for (const r of open.slice(0, 10)) {
    const u = doc.units.find(x => x.key === r.key);
    process.stdout.write(`  - ${r.key}｜${(u?.text ?? '').slice(0, 60)}\n`);
  }

  // 渲染进度：哪几章还没写、每章还有多少条落点机器核不住。
  // 成文是**逐章追加**的，中途断了要知道从哪一章续——这两行就是那个位置。
  const rendered = new Set(sections.map(s => s.title));
  const pending = ctx.contract.chapters.map(c => c.title).filter(t => !rendered.has(t));
  const byChapter = new Map();
  for (const r of records) {
    if (r.by === 'author' && r.at) byChapter.set(r.at, (byChapter.get(r.at) ?? 0) + 1);
  }
  process.stdout.write(
    `  未渲染章 ${pending.length}/${ctx.contract.chapters.length}`
    + `${pending.length ? '：' + pending.join('、') : '（全部已渲染）'}\n`);
  process.stdout.write(
    `  各章待核单元（机器核不住、交裁决者）：`
    + `${byChapter.size ? [...byChapter].map(([t, n]) => `${t} ${n}`).join('、') : '无'}\n`);
}

// --------------------------------------------------------------------------
// check：整篇守恒与形态
// --------------------------------------------------------------------------

const EMPTY_SECTION_TEXT = '本需求不涉及。';

/**
 * spec §0 术语映射表里、应当出现在 story 的业务实体词，哪些没出现。
 *
 * 层身份按依赖方向从架构 DSL 派生（`can_depend_on` 为空者是平台能力层），不写层名字面——
 * 写死名字换个工程就静默失效。无该列或派生不到时不过滤，保持向后兼容。
 */
function missingGlossaryTerms(specText, storyText, projectRoot) {
  const rows = [];
  let inTable = false;
  for (const line of specText.split(/\r?\n/)) {
    const s = line.trim();
    if (/^#{1,4}\s/.test(s)) { inTable = /术语映射表/.test(s); continue; }
    if (!inTable || !s.startsWith('|')) continue;
    const cells = s.replace(/^\||\|$/g, '').split('|').map(c => c.replace(/[`*]/g, '').trim());
    if (cells.every(c => /^[-: ]*$/.test(c))) continue;
    rows.push(cells);
  }
  if (!rows.length) return [];
  const header = rows.find(c => /^原始术语$|^术语$/.test(c[0]));
  const layerIdx = header ? header.findIndex(h => /所属层/.test(h)) : -1;
  const baseLayers = baseLayerIds(projectRoot);
  return rows
    .filter(c => c.length >= 2 && !/^原始术语$|^术语$/.test(c[0]))
    .filter(c => layerIdx < 0 || !baseLayers.length
      || !baseLayers.some(id => (c[layerIdx] ?? '').includes(id)))
    .map(c => c[0])
    .filter(t => t && !storyText.includes(t));
}

function cmdCheck(ctx) {
  const problems = [];
  const doc = readJson(ctx.unitsPath, null);
  if (!doc) fail(`还没有来源单元清单，先跑 init：${ctx.unitsPath}`);
  const storyText = readText(ctx.storyPath);
  if (storyText === null) fail(`读不到 ${ctx.storyPath}`);
  const audit = readJson(ctx.auditPath, null);
  if (!audit) fail(`还没有核对记录，先跑 audit：${ctx.auditPath}`);

  const sections = storySections(storyText);
  const titles = sections.map(s => s.title);
  const want = ctx.contract.chapters.map(c => c.title);

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

  // ② 落点守恒：三态每一种都过一遍机器。
  //
  // **落点域只有 story.md**。上一版把 decisions.json 也拼进来当草垛，于是任何 token 塞进
  // 决策件就算落点——那是个逃生口。开放议题要在 story 里有一句交代，那一句才是落点。
  //
  // **`at` 要核到章**，不是核整篇：上一版只看 `at` 这个键在不在、token 在不在整篇里，
  // 于是作者填任何章名都过——旧的自由文本理由换成了不核的 `at`，形态变了效果没变。
  const sectionText = new Map(sections.map(s => [s.title, s.text]));
  const titleSet = new Set(titles);
  const byKey = new Map(doc.units.map(u => [u.key, u]));
  const recByKey = new Map((audit.records ?? []).map(r => [r.key, r]));
  const missingTokens = [];
  const stateless = [];
  const authorPlaced = [];      // 机器定不了、由裁决者裁的那些

  for (const u of doc.units) {
    if (u.machine_facing) continue;
    if (u.kind === 'knowledge') continue;   // 规约条目走 ⑦ 判定表，不走章节落点
    const rec = recByKey.get(u.key);
    const states = ['at', 'covered_by', 'machine_facing'].filter(k => rec?.[k]);
    if (states.length === 0) { stateless.push(u); continue; }
    if (states.length > 1) {
      problems.push(`${u.key} 同时标了 ${states.join(' 与 ')}——三态互斥，一条只能是其中一个`);
    }
    if (rec.machine_facing) {
      problems.push(`${u.key} 被标成 machine_facing，但枚举器没这么判`
        + '——这一态只能由枚举器按合同打标，作者改它就是给漏写开后门');
    }
    if (rec.covered_by) {
      const target = byKey.get(rec.covered_by);
      const trec = recByKey.get(rec.covered_by);
      if (!target) problems.push(`${u.key} 的 covered_by 指向不存在的单元 ${rec.covered_by}`);
      else if (rec.covered_by === u.key) problems.push(`${u.key} 的 covered_by 指向了自己`);
      else if (!trec?.at) problems.push(`${u.key} 的 covered_by 指向 ${rec.covered_by}，但那一条自己也没进正文`);
      else {
        const shared = u.tokens.filter(t => target.tokens.includes(t)).length;
        const sameGroup = (u.also_in ?? []).includes(rec.covered_by);
        // 都没 token 时看正文：两者规范化后一方是另一方的子串，才算讲的是同一件事
        const a = norm(u.text), b = norm(target.text);
        const nested = a.length >= 8 && b.length >= 8 && (a.includes(b) || b.includes(a));
        if (!shared && !sameGroup && !nested) {
          problems.push(`${u.key} 说被 ${rec.covered_by} 承载，但两者没有共享 token、`
            + '不是同一条跨材料重复、正文也互不包含');
        }
      }
      continue;
    }

    // 到这里只剩 at 一态
    if (!titleSet.has(rec.at)) {
      problems.push(`${u.key} 的 at「${rec.at}」不是合同里的章节标题`);
      continue;
    }
    const chapter = sectionText.get(rec.at) ?? '';
    if (rec.by === 'author') {
      // 机器定不了的，交给裁决者；这里只核标题在册，讲没讲清由 ⑥ 核
      authorPlaced.push(u);
      continue;
    }
    // by: machine —— 机器给的落点，必须在**那一章**里核得住
    if (u.tokens.length) {
      const lost = u.tokens.filter(t => !chapter.includes(t));
      if (lost.length) {
        missingTokens.push({ key: u.key, lost, at: rec.at, text: u.text.slice(0, 50) });
      }
      continue;
    }
    const frags = contentFragments(u.text);
    if (!frags.some(f => norm(chapter).includes(f))) {
      missingTokens.push({ key: u.key, lost: ['正文片段'], at: rec.at, text: u.text.slice(0, 50) });
    }
  }

  if (stateless.length) {
    problems.push(`${stateless.length} 个单元没有任何落点（三态皆空）：`
      + stateless.slice(0, 5).map(u => `${u.key}「${u.text.slice(0, 30)}」`).join('；')
      + (stateless.length > 5 ? `……另 ${stateless.length - 5} 个` : '')
      + '——补写正文，或标 covered_by 指向已进正文的另一条');
  }
  for (const m of missingTokens.slice(0, 8)) {
    problems.push(`${m.key}「${m.text}」落点标在「${m.at}」，但那一章里找不到：${m.lost.join('、')}`);
  }
  if (missingTokens.length > 8) {
    problems.push(`另有 ${missingTokens.length - 8} 个单元的落点核不住（跑 audit 看全量）`);
  }

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

  // ④ 形态守恒：图片与 diagram 可解析、全篇唯一、**以同类形态落点**
  //
  // 上一版只判「有落点」——于是把流程图压成「A → B → C」这样的箭头文字、
  // 把表压成散文都能通过。读者要的是那张图一眼看出的结构，文字复述它做不到。
  // 判的是**形态不是语义**：语义归裁决者，这里只管「源里是图的，到这儿还是不是图」。
  const imgs = [...storyText.matchAll(/!\[([^\]]*)\]\(([^)\s]+)/g)];
  const seen = new Set();
  for (const [, alt, src] of imgs) {
    if (!alt.trim()) problems.push(`图片 ${src} 没有 alt 文本`);
    if (seen.has(src)) problems.push(`图片 ${src} 在 story 里出现了不止一次`);
    seen.add(src);
  }

  /** 一章里有没有围栏图 / 图片 / 表——形态判据只问这三件事。 */
  const chapterForm = new Map(sections.map(s => [s.title, {
    diagram: /^\s*(?:```|~~~)\s*\w+/m.test(s.text),
    image: /!\[[^\]]*\]\(/.test(s.text),
    table: /^\s*\|/m.test(s.text),
    text: s.text,
  }]));
  const placedAt = (u) => recByKey.get(u.key)?.at;
  const tableRowsByChapter = new Map();

  for (const u of doc.units) {
    const rec = recByKey.get(u.key);
    const at = placedAt(u);
    if (u.kind === 'diagram') {
      if (!at && !rec?.covered_by) {
        problems.push(`来源材料里的图（${u.doc}:${u.line}）在 story 里没有落点`
          + '——图是读者最依赖的那部分，不能只在材料里有');
      } else if (at && chapterForm.get(at) && !chapterForm.get(at).diagram) {
        problems.push(`来源材料里的图（${u.doc}:${u.line}）落在「${at}」，但那一章没有图`
          + '——把流程图压成箭头文字算降级，读者要的是一眼看出的结构');
      }
    } else if (u.kind === 'image') {
      if (at && chapterForm.get(at) && !chapterForm.get(at).image) {
        problems.push(`来源材料里的图片（${u.doc}:${u.line}）落在「${at}」，但那一章没有图片引用`
          + '——图片承载的信息，文字复述替代不了');
      }
    } else if (u.kind === 'table_row' && at) {
      if (!tableRowsByChapter.has(at)) tableRowsByChapter.set(at, []);
      tableRowsByChapter.get(at).push(u);
    }
  }

  // 表行：**该章分到 ≥2 条时**才要求成表——只有一行的不构成表（一行的表读起来
  // 比一句话更费劲），那时只要求这一行的内容在该章出现，由整篇 token 守恒管。
  for (const [at, rows] of tableRowsByChapter) {
    const form = chapterForm.get(at);
    if (!form || rows.length < 2) continue;
    if (!form.table) {
      problems.push(`材料里的表有 ${rows.length} 行落在「${at}」，但那一章没有表`
        + '——把表压成散文，逐项比对的那几列就没了（最先丢的是触发条件与编号）');
    }
  }

  // 整篇形态数不降级：源里有几张图，story 里就不该更少
  const sourceForm = { diagram: 0, image: 0 };
  for (const u of doc.units) {
    if (u.kind === 'diagram') sourceForm.diagram += 1;
    if (u.kind === 'image') sourceForm.image += 1;
  }
  const storyDiagrams = (storyText.match(/^\s*(?:```|~~~)\s*\w+/gm) ?? []).length;
  if (sourceForm.diagram && storyDiagrams < sourceForm.diagram) {
    problems.push(`材料里有 ${sourceForm.diagram} 张图，story 里只有 ${storyDiagrams} 张`
      + '——数量不该少于源');
  }
  if (sourceForm.image && imgs.length < sourceForm.image) {
    problems.push(`材料里有 ${sourceForm.image} 张图片，story 里只引用了 ${imgs.length} 张`);
  }

  // ⑤ 决策件六类都扫过
  const decisions = readJson(ctx.decisionsPath, null);
  if (!decisions) problems.push('缺 decisions.json——决策登记是 review 的唯一数据源');
  else {
    const scanned = decisions.scanned_categories ?? {};
    for (const cat of SCANNED_CATEGORIES) {
      const c = scanned[cat];
      if (!c) { problems.push(`决策件没扫「${cat}」这一类——少扫一类不是「没有」，是「没想这件事」`); continue; }
      const n = Array.isArray(c.entries) ? c.entries.length : 0;
      if (n === 0 && !String(c.none_reason ?? '').trim()) {
        problems.push(`决策件「${cat}」零条目又没写 none_reason——空着分不清「判过了没有」与「压根没想」`);
      }
    }
  }

  // ⑥ 裁决核实：机器定不了落点的那些，裁决者要逐条裁并附引文
  //
  // 这一条替代上一版的「靠语义判据守恒」那个空计数——说了「有 N 条机器管不了」，
  // 却没人真去管它们，等于把漏写记了个数就放行。
  if (authorPlaced.length) {
    const vtext = readText(ctx.verdictsPath);
    if (vtext === null) {
      problems.push(`${authorPlaced.length} 个单元的落点机器定不了，需要裁决者逐条裁，`
        + `但 ${path.basename(ctx.verdictsPath)} 不存在`);
    } else {
      const rows = new Map();
      for (const line of vtext.split(/\r?\n/)) {
        const s = line.trim();
        if (!s.startsWith('|')) continue;
        const c = s.replace(/^\||\|$/g, '').split('|').map(x => x.trim());
        if (c.length < 3 || /^[-: ]*$/.test(c[0])) continue;
        rows.set(c[0].replace(/[`*]/g, ''), { verdict: c[1], quote: c[2] });
      }
      for (const u of authorPlaced) {
        const row = rows.get(u.key);
        if (!row) { problems.push(`裁决表里没有 ${u.key}「${u.text.slice(0, 30)}」这一行`); continue; }
        if (!VERDICT_WORDS.includes(row.verdict)) {
          problems.push(`${u.key} 的裁决「${row.verdict}」不是 ${VERDICT_WORDS.join(' / ')} 之一`);
          continue;
        }
        if (row.verdict === '未讲清') {
          problems.push(`${u.key}「${u.text.slice(0, 30)}」被裁「未讲清」——补写那一章`);
          continue;
        }
        const q = norm(row.quote);
        const chapter = norm(sectionText.get(recByKey.get(u.key)?.at) ?? '');
        if (q.length < MIN_QUOTE) {
          problems.push(`${u.key} 的引文只有 ${q.length} 字（要求 ≥${MIN_QUOTE}）`);
        } else if (!chapter.includes(q)) {
          problems.push(`${u.key} 的引文在它落点那一章里检索不到——引文要从 story 抄`);
        } else if (norm(u.text).includes(q)) {
          // 把材料原话抄回来是回声：它证明的是「材料这么说」，不是「story 讲清了」
          problems.push(`${u.key} 的引文是来源单元原文的子串——那是回声，抄 story 里你据以判断的那句`);
        }
      }
    }
  }

  // ⑦ 规约判定表：激活清单的每个条目在附录的「规约判定」小节有一行，
  //    或其整域一行「整域不适用」
  //
  // 逐条判定原先落在一份独立的判定记录文件里，那份文件退场后既无作业指引也无门禁——
  // 批次 1 的「知识应用」在 story 侧就这么丢了。判定回到 story 里，评审者才拿得到完备性回显。
  //
  // 落点在**附录**而不是主叙事的某一章：规约编号是工程标识，读者对不上，
  // 写进主叙事就是在打断阅读；附录给了它一个不打断阅读、机器又核得到的位置。
  const kUnits = doc.units.filter(u => u.kind === 'knowledge');
  if (kUnits.length) {
    const appendix = appendixChapter(ctx.contract);
    const appendixSec = appendix ? sections.find(s => s.title === appendix.title) : null;
    const verdictName = (appendix?.subsections ?? []).find(n => n.includes('规约')) ?? '规约判定';
    const verdictText = appendixSec ? subsectionText(appendixSec.text, verdictName) : null;
    if (verdictText === null) {
      problems.push(`缺${appendix ? `「${appendix.title}」章的` : ''}「${verdictName}」小节`
        + '——激活规约的逐条判定表落在那里');
    } else {
      const rows = new Map();          // 编号 → {判定, 依据}
      const domainRows = new Map();    // 中文域名 → 判定
      for (const line of verdictText.split(/\r?\n/)) {
        const s = line.trim();
        if (!s.startsWith('|')) continue;
        const c = s.replace(/^\||\|$/g, '').split('|').map(x => x.replace(/[`*]/g, '').trim());
        if (c.length < 4 || /^[-: ]*$/.test(c[0])) continue;
        const [domain, id, verdict, basis] = c;
        if (id) rows.set(id, { verdict, basis });
        if (verdict === DOMAIN_NA) domainRows.set(domain, true);
      }
      for (const u of kUnits) {
        const id = u.tokens[0];
        const row = rows.get(id);
        if (!row) {
          if (domainRows.has(u.domain)) continue;   // 整域不适用，覆盖域内全部条目
          problems.push(`规约 ${id}（${u.domain}）在附录·${verdictName}的判定表里没有行`
            + `——判「不命中」也要有一行；整域不适用就给该域一行「${DOMAIN_NA}」`);
          continue;
        }
        if (!KNOWLEDGE_VERDICTS.includes(row.verdict)) {
          problems.push(`规约 ${id} 的判定「${row.verdict}」不是 ${KNOWLEDGE_VERDICTS.join(' / ')} 之一`);
        } else if (!row.basis) {
          problems.push(`规约 ${id} 的判定没写依据——「不涉及」三个字不是依据`);
        }
      }
    }
  }

  // ⑧ 术语表实体词守恒：spec §0 术语映射表里、权威模块落在 in_scope 的那些词须在 story 出现
  //
  // 术语表混着两类词：**需求实体**（业务对象的名字，story 就该出现）与**工程消歧用词**
  // （主题色、脱敏这类——spec 拿它们把自然语言映到权威模块，story 用业务语言表达同一事实
  // 才是对的）。一视同仁地要求逐词出现，会让 story 越写人话越容易被判「丢了事实」。
  // 分流键取表内的「所属层」列：归属平台能力层的属工程消歧用词，不要求出现。
  const specText = readText(path.join(ctx.featureRoot, 'spec', 'spec.md'));
  if (specText !== null) {
    const lost = missingGlossaryTerms(specText, storyText, ctx.projectRoot);
    if (lost.length) {
      problems.push(`spec 术语映射表里的这些业务实体词在 story 里找不到：${lost.join('、')}`
        + '——可整合、可改序、可换措辞，但不能少');
    }
  }

  // ⑨ 归档件四红线：仓内路径 / 客户端禁用词 / 悬空引用 / 图片断链
  //
  // 归档件随需求上传，评审者手上没有这个仓：点不开的引用他不知道是坏的。
  // 词表与判定在 lint-rules.mjs（SSOT），这里只调。
  const reviewText = readText(ctx.reviewPath) ?? '';
  for (const [label, text] of [['story', storyText], ['review', reviewText]]) {
    if (!text) continue;
    for (const [what, kind, hits] of [
      ['仓内路径', 'local', scanLocalPaths(text, ctx.projectRoot)],
      ['客户端语境禁用词', 'banned', scanBannedTerms(text)],
      ['悬空引用', 'dangling', scanDanglingRefs(text, ctx.projectRoot)],
      ['图片断链', 'image', scanBrokenImages(text, path.dirname(ctx.storyPath), fs, path)],
    ]) {
      if (hits.length) problems.push(`${label} 出现${what} ${hits.length} 处：${formatHits(hits, kind)}`);
    }
  }

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
    const identifiers = [];
    for (const u of doc.units) {
      for (const t of u.tokens ?? []) {
        if (/^[A-Za-z][A-Za-z0-9_]{3,}$/.test(t)) identifiers.push(t);
      }
    }
    const hits = scanLanguageRedline(storyText, {
      appendixTitle: appendix?.title,
      ruleIds: doc.units.filter(u => u.kind === 'knowledge').map(u => u.tokens[0]),
      identifiers,
      kinds: redlineKinds,
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

  // ⑪ 可读性：长段、长章、过长步骤清单、重复段
  //
  // 四条都满足同一个条件——**拆了一定更可读**，所以机械判它们不会被换皮受益。
  // 没有句长判据：为凑短而在逗号处断开只会写出半截话，那比长句更难读，
  // 而那正是最省力的过关方式。句子啰嗦不啰嗦归裁决者。
  const readability = ctx.contract.readability ?? {};
  if (storyText && Object.keys(readability).some(k => !k.startsWith('_'))) {
    const byKind = new Map();
    for (const h of scanReadability(storyText, readability)) {
      if (!byKind.has(h.kind)) byKind.set(h.kind, []);
      byKind.get(h.kind).push(h);
    }
    const label = {
      long_paragraph: '过长的段落', long_chapter: '一整章没有停顿',
      long_ordered_list: '过长的步骤清单', duplicate_paragraph: '重复的段落',
    };
    for (const [kind, list] of byKind) {
      const sample = list.slice(0, 3).map(h => `${h.line} 行 ${h.detail}`).join('，');
      problems.push(`${label[kind] ?? kind} ${list.length} 处（${sample}`
        + `${list.length > 3 ? ' …' : ''}）——${list[0].hint}`);
    }
  }

  if (problems.length) {
    process.stderr.write(`[story-build check] ${problems.length} 处未通过：\n`);
    problems.forEach((p, i) => process.stderr.write(`  ${i + 1}. ${p}\n`));
    process.exit(1);
  }
  process.stdout.write(
    `[story-build check] 通过：${sections.length} 章、${doc.units.length} 个来源单元`
    + `（机器核实 ${doc.units.length - authorPlaced.length} 条、模型裁决 ${authorPlaced.length} 条）\n`);
}

// --------------------------------------------------------------------------
// build：渲染 review.md（机器区重算、人工区逐字节保留）
// --------------------------------------------------------------------------

function cmdBuild(ctx) {
  const decisions = readJson(ctx.decisionsPath, null);
  if (!decisions) fail(`缺 ${ctx.decisionsPath}——先跑 init 建骨架`);
  const list = Array.isArray(decisions.decisions) ? decisions.decisions : [];
  const old = readText(ctx.reviewPath) ?? '';

  const blocks = list.map(dec => {
    const human = extractHumanZone(old, dec.id) ?? renderHumanZone(dec);
    return `${renderMachineZone(dec)}\n${human}\n`;
  });
  const freeform = renderFreeformSection(extractFreeformZone(old));

  const out = [
    '# 评审记录',
    '',
    ...(blocks.length ? blocks : ['（本轮没有登记开放议题。）\n']),
    freeform,
    '**状态**：草稿（待开发确认）',
    '',
  ].join('\n');

  fs.mkdirSync(path.dirname(ctx.reviewPath), { recursive: true });
  fs.writeFileSync(ctx.reviewPath, out, 'utf-8');
  process.stdout.write(`[story-build build] 已渲染 ${list.length} 个议题；人工填写内容逐字节保留\n`);
}

// --------------------------------------------------------------------------

function main() {
  const args = parseArgs(process.argv);
  if (!COMMANDS.includes(args.command)) {
    fail(`用法: story-build.mjs <${COMMANDS.join('|')}> --feature <需求名> [--project-root <路径>]`);
  }
  const ctx = createContext(args);
  if (args.command === 'init') cmdInit(ctx);
  else if (args.command === 'audit') cmdAudit(ctx);
  else if (args.command === 'check') cmdCheck(ctx);
  else cmdBuild(ctx);
}

main();
