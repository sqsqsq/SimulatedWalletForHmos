/**
 * story 的登记、核对与校验 —— 四个命令，围绕**一份文档写成**这件事。
 *
 * ## 与 1.0 逐章生产线的区别
 *
 * 1.0 的做法是先生成 14 份逐章任务书（每章一份取材路标 + 逐章必答），各章分别写完再装配，守恒判「每章把取材节的每行表格/数值/反引号写全」。后果是**同一个事实
 * 被四个章节合同各指一次，于是被强制写四遍**。
 *
 * 这里没有逐章任务书、没有逐章文件、没有装配：作者读完全部材料**一份写成**，
 * 守恒改判「材料里每个可核对 token 在 story 整篇有落点」——事实只需出现一次，
 * 在哪一章由叙述需要决定。
 *
 * ## 四个命令
 *
 * | 命令 | 做什么 |
 * |------|--------|
 * | `init`  | 枚举来源单元 → `source-units.json`；建 `decisions.json` 骨架 |
 * | `audit` | 三态核对：`at` / `covered_by` / `machine_facing`，写 `audit.json` |
 * | `check` | 14 标题、整篇 token 守恒、编号形态、图与 diagram 落点、决策六类齐 |
 * | `build` | 由 `decisions.json` 渲染 `review.md`（机器区重算、人工区逐字节保留） |
 *
 * `audit.json` 只认三态，**没有自由文本理由**——上一版那个 `reason` 字段只判非空，
 * 实测 161/272 个单元「不进」、理由去重后只有 2 种，等于给漏写开了一个合法出口。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { enumerateUnits, linkDuplicates } from './source-units.mjs';
import {
  escapeCell, extractFreeformZone, extractHumanZone, findBlockRange,
  renderFreeformSection, renderHumanZone, renderMachineZone,
} from './review-render.mjs';

const COMMANDS = ['init', 'audit', 'check', 'build'];

/** S5 裁决的取值与引文下限——同 verifier-report 的 evidenceVerified 口径。 */
const VERDICT_WORDS = ['讲清', '未讲清'];
const MIN_QUOTE = 12;

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

/** 材料文件：合同 `sources` 声明的那几份，存在即读。 */
function sourceDocs(ctx) {
  const out = [];
  for (const [doc, rel] of Object.entries(ctx.contract.sources ?? {})) {
    const abs = path.join(ctx.featureRoot, rel);
    const text = readText(abs);
    if (text !== null) out.push({ doc, rel, text });
  }
  return out;
}

// --------------------------------------------------------------------------
// init：枚举来源单元 + 建决策骨架
// --------------------------------------------------------------------------

/**
 * 组装 token 排除函数——**规则全部来自合同数据**，本文件不写任何具体词。
 *
 * 为什么要排除：`WalletMain` 这类模块目录名会被标识符正则取成 token，于是守恒要求它出现在
 * story 里；而归档件红线第 1 条不许写模块名。两条一起生效时作者只能违反其一。
 * 模块名从 spec 的 Scope 块现取——换个工程、换个需求都不用改这里。
 */
function buildTokenExclusion(ctx) {
  const conf = ctx.contract.token_exclusions ?? {};
  const res = [];
  for (const p of conf.patterns ?? []) {
    try { res.push(new RegExp(p)); } catch { /* 形态写错不该让枚举崩掉 */ }
  }
  const modules = new Set();
  if (conf.spec_scope_modules) {
    const spec = readText(path.join(ctx.featureRoot, 'spec', 'spec.md')) ?? '';
    // `:[ \t]*\n` 不能写成 `:\s*\n`——`\s*` 会贪婪吃掉换行，后面那个 `\n` 就永远匹配不上
    for (const m of spec.matchAll(/(?:in_scope_modules|out_of_scope_modules):[ \t]*\r?\n((?:[ \t]*-[ \t]*.+\r?\n)+)/g)) {
      for (const line of m[1].split(/\r?\n/)) {
        const name = line.replace(/^\s*-\s*/, '').replace(/[`"']/g, '').split(/[\s#]/)[0].trim();
        if (name) modules.add(name.split('/').pop());
      }
    }
  }
  if (!res.length && !modules.size) return null;
  return (t) => modules.has(t) || res.some(re => re.test(t));
}

function cmdInit(ctx) {
  const docs = sourceDocs(ctx);
  if (!docs.length) {
    fail(`一份材料都读不到（合同 sources 指向 ${Object.values(ctx.contract.sources ?? {}).join('、')}）`);
  }
  const idShapes = [...(ctx.contract.id_shapes?.keep ?? []), ...(ctx.contract.id_shapes?.drop ?? [])];
  const excludeToken = buildTokenExclusion(ctx);
  const units = [];
  for (const d of docs) {
    units.push(...enumerateUnits(d.text, d.doc, {
      idShapes,
      excludeToken,
      machineFacing: ctx.contract.machine_facing ?? {},
    }));
  }
  if (!units.length) fail('材料切不出任何来源单元——枚举器或材料有问题，不是「材料是空的」');
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
    + `无 token ${noToken} 个——它们的落点靠正文片段核，核不住的交 S5 裁决者逐条裁）\n`);
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
  const storyText = readText(ctx.storyPath);
  if (storyText === null) fail(`读不到 ${ctx.storyPath}——先写 story 再核对`);
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
    // 机器定不了：保留作者上次填的章名（`by: author`），由 S5 裁决者逐条裁「讲清没讲清」。
    // **不沿用机器上次的结果**——`by` 标记就是为了让这两种来源不再混成一个 `at`。
    if (old?.at && old.by === 'author') {
      records.push({ key: u.key, at: old.at, by: 'author' });
      continue;
    }
    records.push({ key: u.key });                       // 三态皆空 → check 会报它
  }
  writeJson(ctx.auditPath, { records });

  const open = records.filter(r => !r.at && !r.covered_by && !r.machine_facing);
  process.stdout.write(
    `[story-build audit] ${records.length} 条；待处理 ${open.length} 条`
    + `（给它们补写正文，或标 covered_by 指向已进正文的另一条）\n`);
  for (const r of open.slice(0, 10)) {
    const u = doc.units.find(x => x.key === r.key);
    process.stdout.write(`  - ${r.key}｜${(u?.text ?? '').slice(0, 60)}\n`);
  }
}

// --------------------------------------------------------------------------
// check：整篇守恒与形态
// --------------------------------------------------------------------------

const EMPTY_SECTION_TEXT = '本需求不涉及。';

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

  // ① 14 个标题与顺序 = 合同；空节恰为「本需求不涉及。」
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
  const authorPlaced = [];      // 机器定不了、由 S5 裁决者裁的那些

  for (const u of doc.units) {
    if (u.machine_facing) continue;
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
      // 机器定不了的，交给 S5 裁决者；这里只核标题在册，讲没讲清由 ⑥ 核
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

  // ④ 图片与 diagram：可解析、全篇唯一、有落点
  const imgs = [...storyText.matchAll(/!\[([^\]]*)\]\(([^)\s]+)/g)];
  const seen = new Set();
  for (const [, alt, src] of imgs) {
    if (!alt.trim()) problems.push(`图片 ${src} 没有 alt 文本`);
    if (seen.has(src)) problems.push(`图片 ${src} 在 story 里出现了不止一次`);
    seen.add(src);
  }
  for (const u of doc.units.filter(x => x.kind === 'diagram')) {
    const rec = recByKey.get(u.key);
    if (!rec?.at && !rec?.covered_by) {
      problems.push(`来源材料里的图（${u.doc}:${u.line}）在 story 里没有落点`
        + '——图是读者最依赖的那部分，不能只在材料里有');
    }
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

  // ⑥ 裁决核实：机器定不了落点的那些，S5 裁决者要逐条裁并附引文
  //
  // 这一条替代上一版的「靠语义判据守恒」那个空计数——说了「有 N 条机器管不了」，
  // 却没人真去管它们，等于把漏写记了个数就放行。
  if (authorPlaced.length) {
    const vtext = readText(ctx.verdictsPath);
    if (vtext === null) {
      problems.push(`${authorPlaced.length} 个单元的落点机器定不了，需要 S5 裁决者逐条裁，`
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

  if (problems.length) {
    process.stderr.write(`[story-build check] ${problems.length} 处未通过：\n`);
    problems.forEach((p, i) => process.stderr.write(`  ${i + 1}. ${p}\n`));
    process.exit(1);
  }
  process.stdout.write(
    `[story-build check] 通过：${sections.length} 章、${doc.units.length} 个来源单元`
    + `（机器核实 ${doc.units.length - authorPlaced.length} 条、S5 裁决 ${authorPlaced.length} 条）\n`);
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

export { SCANNED_CATEGORIES, storySections, autoPlace, escapeCell };
