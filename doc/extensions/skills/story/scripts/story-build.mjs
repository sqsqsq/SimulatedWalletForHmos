/**
 * story 的登记、核对与校验 —— 六个命令，围绕**一份文档写成**这件事。
 *
 * ## 成文怎么走
 *
 * 材料齐备之后，作者拿到一次给全的任务包（材料、知识、合同、样式），按合同顺序
 * 一次写一章、经 `chapter` 原子替换落盘，十章写完再统稿。每步输出有界、写完即落盘、
 * 断了能续——整篇一次重出是全有或全无，中途断了磁盘上什么都没有。
 *
 * ## 判据的边界
 *
 * 这里只判**确定性不变量**：章标题与顺序、编号、附录结构、图片身份与落点、
 * 语言红线、决策登记字段、材料清单形态、台账随稿冻结。凡是要读懂内容才判得了的
 * ——讲清没讲清、贴不贴合、图题说的是不是这张图——都不在这里，归 verifier 的
 * 语义判据与真实结果观察。用字符串近似语义，模型只会照着字符串改。
 *
 * ## 六个命令
 *
 * | 命令 | 做什么 |
 * |------|--------|
 * | `init`  | 检查材料齐备；建 `decisions.json` 骨架 |
 * | `skeleton` | 建十章骨架：每章一个稳定章锚 + 一个待写 marker |
 * | `chapter` | 把一章的内容原子替换进 story.md，其余字节不动 |
 * | `check` | 上面那几条确定性不变量 |
 * | `build` | 由 `decisions.json` 渲染 `review.md`（机器区重算、人工区逐字节保留） |
 * | `number`| 给 `story.md` 重编号：章序按合同、小节序按出现顺序、图题按全篇顺序 |
 */
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { normalizeHeading, renumberStory } from './headings.mjs';
import { readerReviewTask } from '../../../hooks/shared/reader-review-task.mjs';
import { readUse, UseError } from '../../../hooks/shared/knowledge-use.mjs';
import {
  baseLayerIds, formatHits, proseBlocks, scanBannedTerms, scanBrokenImages, scanDanglingRefs,
  scanLanguageRedline, scanLocalPaths, scanMaterialList,
} from './lint-rules.mjs';
import { activeKnowledge } from '../../../hooks/shared/knowledge.mjs';
import {
  FREEFORM_CLOSE, FREEFORM_OPEN, HUMAN_ZONE_MARK, renderReview,
} from './review-render.mjs';

import { storyReviewProblems } from '../../../hooks/shared/verifier-report.mjs';

const COMMANDS = ['init', 'check', 'build', 'number', 'skeleton', 'chapter',
  'project', 'review-task'];

/**
 * 一条决策登记要写满的字段，与「缺了会怎样」。
 *
 * 导出，因为作者任务包要照它列——字段名在校验里写一遍、在提示词里再写一遍，
 * 就是两份真源，改了一处另一处静默过期。
 */
export const DECISION_FIELDS = [
  ['title', '陈述句标题（已定的陈述结论，待定的陈述事项）'],
  ['clarification', '带小标题分段的澄清正文'],
  ['decider', '请谁确认'],
];

/** 统稿留痕的行数：作业书的自查清单有几项，这里就是几行。 */
const COPYEDIT_ROWS = 7;

/** 规约判定表的取值封闭；整域不适用时该域内条目不必逐条列。 */
const DOMAIN_NA = '整域不适用';

/**
 * 评审记录里不该出现的行 —— 每一样都被裁掉过，每一样都以「更规范」的名义长回来。
 *
 * 判的是**行首形态**而不是词：`确认人：` 是签署字段，而评审人在自己的意见里写
 * 「这条要找确认人」是正常的话。只判机器渲染出来的那种独立字段行。
 */
const REVIEW_BANNED_LINES = [
  { name: '如何填写', re: /^#{1,6}?\s*\**\s*(?:如何填写|填写说明|使用说明)/ },
  { name: '确认人', re: /^[-*]?\s*\**确认人\**\s*[:：]/ },
  { name: '确认日期', re: /^[-*]?\s*\**确认日期\**\s*[:：]/ },
  { name: '确认依据', re: /^[-*]?\s*\**确认依据\**\s*[:：]/ },
  { name: '状态行', re: /^[-*]?\s*\**状态\**\s*[:：]/ },
  { name: '下一步', re: /^#{1,6}?\s*\**\s*下一步\**\s*[:：]?\s*$/ },
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
    else if (argv[i] === '--story') args.story = argv[++i];
    else if (argv[i] === '--chapter') args.chapter = argv[++i];
    else if (argv[i] === '--from') args.from = argv[++i];
    else if (argv[i] === '--offline') args.offline = true;
    else if (argv[i] === '--deliver') args.deliver = true;
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

/**
 * 只读一份 story 的上下文 —— `check --offline --story <路径>`。
 *
 * **为什么要有它**：判据得有个仲裁锚。理想产物冻结在夹具里，任何一条判据改动
 * 都先拿它跑一遍——拦住理想产物的判据，错的是判据。而理想产物没有需求目录、
 * 没有台账，正常的 check 连门都进不去。
 *
 * 走的是**同一个 `cmdCheck`**，不是另写一套：另写一套就会与生产链漂移，
 * 到那时「拿它跑过了」什么也证明不了。需求目录侧的输入给空，
 * 依赖它们的判项自然一条不判；不依赖的照跑。
 */
function createOfflineContext(args) {
  if (!args.story) fail('缺 --story <story.md 路径>');
  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  const projectRoot = path.resolve(
    args.projectRoot ?? path.join(scriptDir, '..', '..', '..', '..', '..'));
  const contract = readJson(path.join(scriptDir, '..', 'contracts', 'story-chapters.json'), null);
  if (!contract) fail('章节合同缺失：contracts/story-chapters.json');
  const storyPath = path.resolve(args.story);
  if (readText(storyPath) === null) fail(`读不到 ${storyPath}`);
  return {
    args, projectRoot, contract, offline: true,
    featureRoot: path.dirname(path.dirname(storyPath)),
    storyPath,
    decisionsPath: '',
    copyeditPath: '', reviewPath: '',
  };
}

function createContext(args) {
  if (args.offline) return createOfflineContext(args);
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
    decisionsPath: path.join(srcDir, 'decisions.json'),
    copyeditPath: path.join(srcDir, 'copyedit.md'),
    storyPath: path.join(featureRoot, 'AR', 'story.md'),
    reviewPath: path.join(featureRoot, 'AR', 'review.md'),
    flowPath: path.join(featureRoot, 'AR', 'story-flow.json'),
  };
}

/**
 * 随稿冻结的台账 —— 这里存的是 ctx 上的路径字段名，**不另列一份文件名**。
 *
 * 文件名的真源在 `story_flow.py` 的 `STORY_SRC_FROZEN`：那两件是登记时要算指纹、
 * 登记后拒绝重算、归档时随稿走的同一批。清理、冻结、存在性三处说的必须是同一批文件，
 * 各写一份就会改一处忘一处。
 */
const STORY_SRC_LEDGERS = [
  ['decisionsPath', 'init'], ['copyeditPath', '统稿'],
];

/**
 * 台账在不在 —— **缺任一即 BLOCKER**，check 到此为止。
 *
 * 冻结只挡「登记之后改台账」，挡不住登记之前把台账删掉。而删掉是有动力的：
 * 台账错到成百上千条时，整份删掉能让 check 的报错数当场归零。
 *
 * 报错文案要把这条路直接堵死：缺的那件是**补产出**，不是删同伴文件。
 */
function requireLedgers(ctx) {
  if (ctx.offline) return;                 // 仲裁锚只有一份 story，没有台账目录
  const missing = STORY_SRC_LEDGERS
    .filter(([key]) => ctx[key] && readText(ctx[key]) === null)
    .map(([key, how]) => `${path.basename(ctx[key])}（跑 ${how} 产出）`);
  if (!missing.length) return;
  fail(`台账缺 ${missing.length} 件：${missing.join('、')}\n`
    + '  这两件是这份 story 据以成文的全部依据，随稿冻结、随稿归档，缺一件产物就没有依据。\n'
    + '  **缺的那件要补产出，不是把同伴文件删掉。** 报错多的时候删台账能让报错数下去，'
    + '但那是把依据删了，不是把问题解决了——被删的那些事实，评审者再也看不到有人核过。');
}

/**
 * 成文态登记了没有——登记那一刻 story 与它的台账一起定稿。
 *
 * @returns {{written:boolean, digests:Record<string,string|null>}}
 */
function storyFrozen(ctx) {
  const flow = ctx.offline ? null : readJson(ctx.flowPath, null);
  return {
    written: flow?.status === 'story_written',
    digests: flow?.story_src_digests ?? {},
  };
}

/** 台账冻结之后，重算它的两个命令一律拒绝执行。 */
function refuseIfFrozen(ctx, command) {
  if (!storyFrozen(ctx).written) return;
  fail(`story 已定稿登记（story_written），台账随稿冻结，${command} 不再执行。\n`
    + '  定稿是一个时点的快照：那一刻的决策登记与统稿留痕，'
    + '就是这份 story 据以成文的全部依据。\n'
    + '  重算它们等于换掉已定稿产物的依据，而 story.md 不会跟着变——'
    + '重算等于换掉已定稿产物的依据，而 story.md 不会跟着变。\n'
    + '  材料在定稿之后继续演化是正常的，与这份 story 无关：它讲的是定稿那一刻的事。');
}

/** 材料指纹：换行差异不算改动（同一份文件在两台机器上可能行尾不同）。 */
function digestOf(text) {
  return crypto.createHash('sha256')
    .update(String(text ?? '').replace(/\r\n/g, '\n'), 'utf-8')
    .digest('hex').slice(0, 16);
}

/**
 * 激活规约条目 —— 派生失败要出声，不能当作「本需求没有规约」。
 *
 * 离线仲裁只有一份 story，没有工程上下文，此时给空数组：依赖它的判项自然不判，
 * 而不是拿一份空清单去判「一条规约都没判到」。
 */
function activeKnowledgeEntries(ctx) {
  if (ctx.offline) return [];
  try {
    return activeKnowledge(ctx.projectRoot).entries ?? [];
  } catch (e) {
    fail(`激活知识派生失败：${e.message}——规约判定表无从核对，不能当作「没有规约」通过`);
    return [];
  }
}

/**
 * spec 侧那份判断里，每条规约命中与否 —— `{ 编号 → 是否命中 }`。
 *
 * 读不到那份 YAML 时返回 null：走 `/story` 之外的路径、或者 spec 还没写到那一步，
 * 都是正常形态，此时这一条不判（**不是判过了**）。
 */
function knowledgeUseVerdicts(ctx) {
  if (ctx.offline) return null;
  try {
    const use = readUse(ctx.projectRoot, ctx.args.feature);
    const rows = new Map();
    for (const row of use.constraints) {
      const id = String(row?.id ?? '').trim();
      // 依据也一起带回来：判断已经写在那份 YAML 里（命中写 requirement、
      // 不命中写 reason），让作者对着它再抄一遍，抄出来的只会更短。
      // requirement 是列表（一条要求一句）：**全部带上**，同一格里分号隔开——
      // 只取第一条的话，附录 D 就成了 §10 的一个截断视图。
      if (id) {
        const req = Array.isArray(row.requirement) ? row.requirement : [row.requirement];
        rows.set(id, { applicable: row.applicable === true,
          basis: (row.applicable === true
            ? req.map(x => String(x ?? '').trim()).filter(Boolean).join('；')
            : String(row.reason ?? '').trim()) });
      }
    }
    // 整域不适用是那份 YAML 允许的另一种登记：一个域一行，域内条目不必逐条写。
    // 不认它的话，作者按规矩写完，投影反倒说他缺依据。
    const naDomains = new Map();
    for (const row of use.domains ?? []) {
      const prefix = String(row?.prefix ?? '').trim();
      if (prefix) naDomains.set(prefix, String(row?.reason ?? '').trim());
    }
    return { rows, naDomains };
  } catch (e) {
    if (e instanceof UseError) return null;
    throw e;
  }
}

/**
 * 合同声明的每个来源，读到了没有 —— **读不到的也要带回来**。
 *
 * 读不到就静默跳过的话，一整类材料会凭空缺席而零信号：那一份的内容从头到尾
 * 没进过任何一条判据的视野，从 init 到 check 没有一处提过。
 *
 * **一律记一笔，不拦**（`required` 只决定措辞轻重）。
 *
 * 索引文件缺席**不是缺陷**：图片的身份与落点在 `materials.json`，那是唯一登记处。
 * 拿「目录里有图而索引不在」当阻断，等于要求作者为一份不承载登记的说明文件停下来。
 *
 * **为什么必备来源缺失也不拦**：最小夹具天然只备一类材料——一份材料测一条判据。
 * 把缺失判成 BLOCKER，逼出来的是更假的夹具，不是更准的判据。
 * 而要解决的问题本来就不是「没拦」，是**零信号**：一整类材料缺席而没有一处提过。
 * 让它一律可见就够了。
 *
 * @returns {{docs: object[], missing: object[]}}
 */
function scanSources(ctx) {
  const docs = [], missing = [];
  for (const [doc, decl] of Object.entries(ctx.contract.sources ?? {})) {
    const rel = typeof decl === 'string' ? decl : decl?.path;
    if (!rel) continue;
    const obj = typeof decl === 'object' && decl ? decl : {};
    const abs = path.join(ctx.featureRoot, rel);
    const text = readText(abs);
    if (text !== null) {
      docs.push({
        doc, rel, text,
        notes: obj.notes ?? [],
        // `derived`＝这一份是本轮流程自己生成的中间产物，不是上游给的材料。
        // 它只守业务编号，工程细节的家是它自己。
        derived: obj.derived === true,
      });
      continue;
    }
    // 缺来源一律不拦（一律记一笔）。图片的登记在 materials.json，不在这些索引文件里。
    missing.push({ doc, rel, required: obj.required === true });
  }
  return { docs, missing };
}

/**
 * 什么算一张图：**只有画图语言的围栏块**。
 *
 * `json` / `yaml` / `text` 围栏是数据与摘抄，不是图。把它们算成图，「这一章画了几张」
 * 就会凭空多出来，欠画的反而判成够了——仓里就有这样的产物（附录倾倒那份夹具里
 * 有一个 `text` 围栏）。
 */
const DIAGRAM_FENCE = /^[ \t]*(?:```|~~~)[ \t]*(?:mermaid|plantuml|puml|dot|graphviz)\b/gmi;

/**
/** 工程标识的形态判定 —— check ⑩ 判「主叙事里不许出现工程标识」时用它。 */
const IDENTIFIER_SHAPE = /^[A-Za-z][A-Za-z0-9_]{3,}$/;

/**
 * 本需求自己的编号不是工程标识。
 *
 * ①b 要求大标题带着它，材料清单也要写清这份文档出自哪张单——它是归档件与需求系统
 * 之间唯一的绳子。编号里带连字符时（`XXX-123` 这种），逐段也放行。
 */
function ownIdentifiers(feature) {
  const f = String(feature ?? '').trim();
  return new Set(f.split(/[^A-Za-z0-9]+/).concat(f).map(s => s.trim()).filter(Boolean));
}

/** 缺失来源报成一句话。都是「记一笔」，措辞按是不是必备分两种。 */
function missingSourceLine(m) {
  return `合同声明的来源 ${m.doc} 不存在：${m.rel}`
    + (m.required
      ? '——它是必备来源，缺了这一轮的材料就不完整'
      : '（可选来源，缺了是正常的）');
}

// --------------------------------------------------------------------------
// init：材料齐备检查 + 建决策骨架
// --------------------------------------------------------------------------

function cmdInit(ctx) {
  refuseIfFrozen(ctx, 'init');
  const { docs, missing } = scanSources(ctx);
  if (!docs.length) {
    fail(`一份材料都读不到（合同 sources 指向 ${Object.values(ctx.contract.sources ?? {}).join('、')}）`);
  }


  // 决策登记的骨架：没有它，取舍在 story 里就没有来源。
  //
  // 骨架只有一个空数组。预置分类空槽是无效机制：判据只核得了「零条目时写了没写
  // none_reason」——那是个逃生口，一句「本轮扫过，无开放议题」就能过。
  const registered = readJson(ctx.decisionsPath, null);
  if (!registered) writeJson(ctx.decisionsPath, { decisions: [] });
  else if (!(registered.decisions ?? []).length) {
    process.stdout.write('[story-build init] 决策登记里一条都没有——'
      + '取舍在 story 里就没有来源。是还没登记，还是这个需求真的一个判断都没做过？\n');
  }

  process.stdout.write(`[story-build init] 材料齐备（${docs.length} 份）；决策登记骨架就位。`
    + '接着跑 skeleton 建十章骨架\n');
  for (const m of missing) {
    process.stdout.write(`  记一笔：${missingSourceLine(m)}\n`);
  }
}

/**
 * story 正文按 `## ` 标题切节。
 *
 * `title` 是**规范化后的业务名**（`## 1. 背景` → `背景`），`raw` 保留原样给报错用。
 * 全链的标题比较——章序、落点归章、附录定位——都用 `title`，于是「作者按阅读习惯
 * 加章序编号」与「合同存业务名」两件事同时成立，不必在每处判据各放宽一次。
 */
function storySections(storyText) {
  const out = [];
  let cur = null;
  for (const line of String(storyText ?? '').split(/\r?\n/)) {
    const m = line.trim().match(/^##\s+(.+)$/);
    if (m) {
      cur = { raw: m[1].trim(), body: [] };
      out.push(cur);
      continue;
    }
    if (cur) cur.body.push(line);
  }
  return out.map(s => ({ title: normalizeHeading(s.raw), raw: s.raw, text: s.body.join('\n') }));
}

/** 附录那一章（合同里标了 `appendix` 的那个）。没有就返回 null。 */
function appendixChapter(contract) {
  return (contract.chapters ?? []).find(c => c.appendix) ?? null;
}

/**
 * 从一章的正文里切出某个 `###` 小节。
 *
 * 附录一章里并排放着接口表、数据表、改动边界表、规约判定表——它们列数相近，
 * 在整章正文里找「四列表行」会把接口行也当成判定行读进来。所以按小节切。
 */
function subsectionText(sectionText, name) {
  const want = normalizeHeading(name);
  const lines = String(sectionText ?? '').split(/\r?\n/);
  const body = [];
  let hit = false;
  for (const line of lines) {
    const m = line.trim().match(/^###\s+(.+)$/);
    if (m) {
      if (hit) break;
      hit = normalizeHeading(m[1]) === want;      // `### A. 接口` 与合同的 `接口` 是同一节
      continue;
    }
    if (hit) body.push(line);
  }
  return hit ? body.join('\n') : null;
}

/**
 * 某个 `###` 小节在**全篇**里的行区间（正文部分，0 起）。
 *
 * `subsectionText` 只给正文，报错就指不回原文行号；而材料清单那一节的形态判据
 * 与仓内路径豁免都要按行说话。
 *
 * @returns {{start:number, end:number}|null}
 */
function subsectionSpan(storyText, chapterTitle, name) {
  const lines = String(storyText ?? '').split(/\r?\n/);
  const wantChapter = normalizeHeading(chapterTitle);
  const wantSub = normalizeHeading(name);
  let inChapter = false;
  let start = -1;
  for (let i = 0; i < lines.length; i++) {
    const s = lines[i].trim();
    const h2 = s.match(/^##\s+(.+)$/);
    if (h2) {
      if (start >= 0) return { start, end: i };
      inChapter = normalizeHeading(h2[1]) === wantChapter;
      continue;
    }
    const h3 = s.match(/^###\s+(.+)$/);
    if (h3) {
      if (start >= 0) return { start, end: i };
      if (inChapter && normalizeHeading(h3[1]) === wantSub) start = i + 1;
    }
  }
  return start >= 0 ? { start, end: lines.length } : null;
}

/**
 * 材料里的图片登记 —— 唯一来源是材料清单（`AR/story-src/materials.json`）。
 *
 * 登记的唯一来源是清单：它枚举磁盘上真实存在的图片文件，与谁给它写没写过
 * markdown 链接无关——按链接枚举的话，界面参考目录里只写了名字的那几张就不算数。
 *
 * 清单枚举的是磁盘上真实存在的图片文件，与谁给它写没写链接无关；同一张图复制到第二个
 * 落点时它按内容合并成一条，`paths` 列出全部落点——**图片的身份是它的内容，不是路径**。
 *
 * @returns {{kind:string,sha256:string,paths:string[]}[] | null | 'broken'}
 *   null = 没有清单（offline 或还没跑过 round）；'broken' = 清单坏了，两者不能混为一谈
 */
/** 路径的最后一段。判「正文提没提到这张图」用它——作者写文件名比写全路径自然。 */
function basename(rel) {
  const parts = String(rel).split('/');
  return parts[parts.length - 1];
}

function readManifest(ctx) {
  if (ctx.offline || !ctx.srcDir) return null;
  const text = readText(path.join(ctx.srcDir, 'materials.json'));
  if (text === null) return null;
  try { return JSON.parse(text.replace(/^\ufeff/, '')); } catch { return 'broken'; }
}

function materialImages(ctx) {
  const data = readManifest(ctx);
  if (data === null || data === 'broken') return data;
  if (!Array.isArray(data.materials)) return 'broken';
  return data.materials.filter(m => m?.kind === 'image'
    && Array.isArray(m.paths) && m.paths.length);
}

/**
 * 材料清单那一节**应当**列到的材料 —— 同样出自 `materials.json`。
 *
 * 这一节回答的是「据哪几份材料写成」。谁来定这个集合，决定了它是账还是倾倒区：
 * 由作者自由罗列时，容易把本轮自己生成的规格链进去，
 * 也出现过漏掉一整份的形态——读者据这一节把材料找出来，漏一份等于那份材料没人知道。
 *
 * 集合 = **这一轮拿到的初始资料**：流程正在消费的那几份正文（清单里 `kind: doc`
 * 且真的在盘上的），加收件箱里的原件——那份是人另外给的、没走需求系统，
 * 读者要知道有它。中间产物不在其中：本轮自己生成的规格与记录不是材料，
 * 它们压根不进清单。
 *
 * **图不在这一节**。图的去向是「引了没有、不引为什么」，那是每张图自己的属性，
 * 跟着内容走（同一张图换个名字、复制到第二个落点，判断还是那个）——所以登记在
 * 材料清单的说明库里（`--caption-image … --unused`），由 ④ 逐张核。
 * 写进这一节的话，读者要在「据哪几份材料写成」里读到十行图，
 * 而其中一半是别的需求的页面。
 *
 * **一份材料一行**：`paths` 有几个是它落了几处，不是几份材料。所以 `must` 的每一项
 * 是一组等价路径，列到其中任意一个就算数。
 *
 * @returns {{must: string[][]} | null | 'broken'}
 */
function materialListTargets(ctx) {
  const data = readManifest(ctx);
  if (data === null || data === 'broken') return data;
  if (!Array.isArray(data.materials)) return 'broken';
  const must = data.materials
    .filter(m => m?.kind === 'doc' && m.sha256 && Array.isArray(m.paths) && m.paths.length)
    .map(m => m.paths);
  for (const src of (Array.isArray(data.sources) ? data.sources : [])) {
    if (src?.file) must.push([`inbox/${src.file}`]);
  }
  return { must };
}

/**
 * 需求目录下的相对路径 → **相对 story.md** 的路径。
 *
 * story.md 在 `AR/` 下，而清单记的是相对需求目录的路径（`RR/prd.md`、
 * `assets/x.png`）。差这一层，链接就点不开、图就断链——落盘后 `check` 会逐条报，
 * 而那几条本可以不发生：串是脚本给作者的，算对是脚本的事。
 */
export function relFromStory(rel) {
  return path.posix.relative('AR', String(rel ?? '').split(path.sep).join('/'));
}

/** 两份文件是不是同一份字节。读不到就不是——断链另有判据报。 */
function sameBytes(a, b) {
  try { return fs.readFileSync(a).equals(fs.readFileSync(b)); } catch { return false; }
}

function relFromFeature(ctx, target) {
  return path.relative(ctx.featureRoot, target).split(path.sep).join('/');
}

/** posix 风格拼接并规范化（`..` 逐段回退），跨平台一致。 */
function joinPosix(base, ref) {
  const parts = String(base ?? '').split('/').filter(p => p && p !== '.');
  for (const seg of String(ref ?? '').split(/[\\/]/)) {
    if (seg === '..') { parts.pop(); continue; }
    if (!seg || seg === '.') continue;
    parts.push(seg);
  }
  return parts.join('/');
}

function subsectionNames(sectionText) {
  const out = [];
  let inFence = false;
  for (const line of String(sectionText ?? '').split(/\r?\n/)) {
    if (/^\s*(```|~~~)/.test(line)) { inFence = !inFence; continue; }
    if (inFence) continue;
    const m = line.trim().match(/^###\s+(.+)$/);
    if (m) out.push({ raw: m[1].trim(), name: normalizeHeading(m[1]) });
  }
  return out;
}

/** 规范化：去空白与标点——「点了提交、但没收到回执」与原文只差标点时仍算同一句。 */
function norm(s) {
  return String(s ?? '').replace(/[\s，。、；：!?！？（）()「」【】]/g, '');
}

/**
 * markdown 表的表头列 —— 分隔行上面那一行就是表头。
 *
 * 返回每张表一组列名（规范化过），check ⑪ 拿它核必有列。列名剥掉行内标记：
 * 作者给表头加粗是常事，`**编号**` 与 `编号` 不该判成两列。
 */
function tableHeaders(text) {
  const lines = String(text ?? '').split(/\r?\n/);
  const out = [];
  for (let i = 0; i + 1 < lines.length; i += 1) {
    const head = lines[i].trim();
    const sep = lines[i + 1].trim();
    if (!head.startsWith('|') || !/^\|[-: |]+\|$/.test(sep)) continue;
    out.push(head.replace(/^\||\|$/g, '').split('|').map(c => norm(c.replace(/[`*]/g, ''))));
  }
  return out;
}

/**
 * 按名字找一个小节的正文 —— 先精确，再包含。
 *
 * 合同给的是这一节要讲什么（「交接约定」），作者按业务命名（「与上游单的交接约定」）。
 * 精确匹配会把后者判成「缺这一节」，而后者恰恰更好。
 */
function findSubsection(text, name) {
  const exact = subsectionText(text, name);
  if (exact !== null) return exact;
  const want = normalizeHeading(name);
  const hit = subsectionNames(text).find(x => x.name.includes(want));
  return hit ? subsectionText(text, hit.name) : null;
}

/**
 * 条件槽位成不成立。条件只取已经在盘上的数据，不另立一份声明。
 *
 * `siblings` 看流程契约里的份表有没有兄弟单据——单特性的分工是叙述不是对照表，
 * 硬核一张表只会逼出一张一列的表。`ui_images` 看材料清单里有没有界面图——
 * 没有界面图就没有页面状态可言。读不到就是不成立：判据宁可不响，不可空响。
 */
function slotApplies(ctx, when) {
  return slotCondition(ctx, when) !== false;
}

/**
 * 条件成不成立：`true` 成立、`false` 确证不成立、`null` **拿不准**。
 *
 * 拿不准与不成立必须分开：离线的仲裁锚读不到流程契约，`siblings` 若一律算不成立，
 * 带兄弟单据的那一节就会被判成「不该有」。条件用来拦一节存在时，只认确证的 `false`。
 */
function slotCondition(ctx, when) {
  if (!when) return true;
  if (when === 'siblings') {
    if (ctx.offline || !ctx.featureRoot) return null;
    const flow = readJson(path.join(ctx.featureRoot, 'AR', 'story-flow.json'), null);
    if (!flow) return null;
    return (flow.split?.parts ?? []).length > 1;
  }
  if (when === 'decisions') {
    const decided = readJson(path.join(ctx.srcDir ?? '', 'decisions.json'), null);
    if (!Array.isArray(decided)) return null;
    return decided.some(x => String(x?.status ?? '') === 'settled');
  }
  if (when === 'ui_images') {
    const imgs = materialImages(ctx);
    if (imgs === null || imgs === 'broken') return null;
    return imgs.length > 0;
  }
  return true;
}

// --------------------------------------------------------------------------
// 从 spec 派生：story 相对 spec 只能增加，不能减少
// --------------------------------------------------------------------------

/**
 * spec.md 全文。路径取自合同声明的来源，不写死。
 *
 * 读不到就返回 null——骨架照建，只是少了打底的那几行；spec 缺失另有判据报。
 */
function specText(ctx) {
  const rel = ctx.contract?.sources?.SPEC?.path;
  if (!rel || ctx.offline || !ctx.featureRoot) return null;
  const text = readText(path.join(ctx.featureRoot, ...rel.split('/')));
  // 行尾在这里归一，不在下游各处正则里补 `\r?`：真实的 spec.md 由宿主在 Windows 上写，
  // 是 CRLF；补正则要每加一处派生就记得补一次，漏一处就是一次静默为空的派生。
  return text === null ? null : text.replace(/\r\n/g, '\n');
}

/** spec 里某一节的正文：从命中标题的那一行到下一个同级或更高级标题之前。 */
function specSection(text, re) {
  const lines = String(text ?? '').split(/\r?\n/);
  const start = lines.findIndex(l => /^#{2,3}\s/.test(l.trim()) && re.test(l));
  if (start < 0) return '';
  const level = (lines[start].trim().match(/^#+/) ?? ['##'])[0].length;
  const body = [];
  for (let i = start + 1; i < lines.length; i += 1) {
    const head = lines[i].trim().match(/^(#+)\s/);
    if (head && head[1].length <= level) break;
    body.push(lines[i]);
  }
  return body.join('\n');
}

/** 一段文本里的表：每张给 {header, rows}，单元格已去掉首尾空串与行内标记。 */
function pipeTables(text) {
  const out = [];
  let cur = null;
  for (const line of String(text ?? '').split(/\r?\n/)) {
    const t = line.trim();
    if (!t.startsWith('|')) { cur = null; continue; }
    const cells = t.replace(/^\||\|$/g, '').split('|').map(c => c.trim());
    if (/^[-: ]+$/.test(cells.join(''))) continue;
    if (!cur) { cur = { header: cells, rows: [] }; out.push(cur); continue; }
    cur.rows.push(cells);
  }
  return out;
}

/** 模板占位单元格（`{ 接口名 }` 这种）——spec 没填时不该派生进 story。 */
function isPlaceholderRow(cells) {
  return cells.every(c => !c || /^\{.*\}$/.test(c) || /^[-—]$/.test(c));
}

/**
 * spec §0 里属于本需求的业务术语 → `[[术语, 解释]]`。
 *
 * 只取权威模块落在 `in_scope_modules` 里的行：那几行才是本需求的业务词汇，
 * 也是 spec 的 post_check 要求写「解释」的那几行。基础能力与模块名不进来——
 * story 是给业务评审者看的读物，模块名对他没有意义。
 */
function specTerms(text) {
  const scope = new Set(scopeList(text, 'in_scope_modules'));
  const table = pipeTables(specSection(text, /术语映射表/))[0];
  if (!table || !scope.size) return [];
  const at = (needle) => table.header.findIndex(h => h.includes(needle));
  const [term, mod, why] = [0, at('权威模块'), at('解释')];
  if (mod < 0 || why < 0) return [];
  return table.rows
    .filter(r => scope.has((r[mod] ?? '').trim()) && !isPlaceholderRow(r))
    .map(r => [(r[term] ?? '').trim(), (r[why] ?? '').trim()])
    .filter(([t, w]) => t && w && w !== '—');
}

/** spec 头部声明的模块清单（`in_scope_modules` / `out_of_scope_modules`）。 */
function scopeList(text, key) {
  const block = String(text ?? '').match(new RegExp(key + String.raw`:\s*\n((?:\s*-\s*.+\n)+)`));
  return (block?.[1] ?? '').split(/\r?\n/)
    .map(l => l.match(/^\s*-\s*(.+?)\s*$/)?.[1]).filter(Boolean);
}

/**
 * 附录·改动边界的两行 —— 「这次改了哪里、哪里保证不动」就是 Scope 的两份清单。
 *
 * 「对评审意味着什么」那一列留给作者：清单说的是范围，影响面要他判断。
 */
function scopeBoundaryRows(spec) {
  const rows = [];
  const inScope = scopeList(spec, 'in_scope_modules');
  const outScope = scopeList(spec, 'out_of_scope_modules');
  if (inScope.length) rows.push(['改动', inScope.join('、'), '{{对评审意味着什么}}']);
  if (outScope.length) rows.push(['只复用', outScope.join('、'), '{{对评审意味着什么}}']);
  return rows;
}

/**
 * 一份文档里的每张图 —— 身份由**位置**给，来源由**围栏第一行**自报。
 *
 * 身份 `§<节> #<该节内第几张>`：图不需要作者起名，位置就是它的名字。
 * 来源标记 `%% 图源 <文档> §<节> #<序>` 指向**直接上游**那一张；只有围栏第一行算标记，
 * 所以一张图从 SR 经 spec 到 story，每一环换一次标记，上一环的那行随围栏带过去也无妨。
 *
 * 节取标题的前导编号（`### 5.2 异常回收` → `5.2`）；没有编号就用业务名——
 * 编号是给人对位用的，取不到时身份仍要唯一。
 */
export function diagramsOf(text) {
  const lines = String(text ?? '').split(/\r?\n/);
  const seq = new Map();
  const out = [];
  let section = '';
  let title = '';
  for (let i = 0; i < lines.length; i += 1) {
    const h = lines[i].trim().match(/^#{2,4}\s+(.+?)\s*$/);
    if (h) {
      title = h[1].trim();
      const num = title.match(/^(\d+(?:[.．]\d+)*)[.．]?\s*/);
      section = num ? num[1].replace(/．/g, '.') : normalizeHeading(title);
      continue;
    }
    if (!/^[ \t]*```[ \t]*mermaid\b/.test(lines[i])) continue;
    const body = [];
    let j = i + 1;
    for (; j < lines.length && !/^[ \t]*```/.test(lines[j]); j += 1) body.push(lines[j]);
    const index = (seq.get(section) ?? 0) + 1;
    seq.set(section, index);
    // 围栏开头**连续的**几行 `%% 图源` 都算标记：同一张图常常两份上游都画过
    // （系统设计画一遍，spec 的业务流程图就是它），story 里只该有一张——
    // 两行标记写在同一个围栏里，两处的登记各自成立。只认开头那几行：
    // 图正文里再出现的 `%%` 是注释，不是登记。
    const marks = [];
    for (const line of body) {
      const m = line.trim().match(/^%%\s*图源\s+(.+?)\s*$/);
      if (!m) break;
      marks.push(m[1]);
    }
    out.push({
      section, index, title,
      id: `§${section} #${index}`,
      sources: marks,
      //: 按**行**给，不拼成字符串——拼了下游就要再切一遍，而切法一旦与这里不同，
      //: CRLF 的文件每行尾会挂个 `\r`，行尾判据从此静默零命中。
      lines: lines.slice(i + 1, j),
    });
    i = j;
  }
  return out;
}

/** 这张图讲的是什么 —— 小节标题 + 首层节点，给的是**主题**，不是「少了一张图」。 */
export function diagramTopic(d) {
  const nodes = [...d.lines.join('\n').matchAll(/[[({]([^\])}|]{1,20})[\])}]/g)]
    .map(m => m[1].trim()).filter(Boolean);
  const uniq = [...new Set(nodes)].slice(0, 4);
  return uniq.length ? `${d.title}：${uniq.join(' → ')}` : d.title;
}

/**
 * 上游每张图，下游有没有一个围栏带着它的来源标记。
 *
 * 只核登记对应：图搬没搬对、周围文字写没写好由语义审查判。
 * 缺了指向的是**功能**不是图——图漏了先找它讲的那件事在下游哪里。
 */
export function diagramsNotCarried(upstreamText, upstreamLabel, downstreamText) {
  const carried = new Set(diagramsOf(downstreamText).flatMap(d => d.sources));
  return diagramsOf(upstreamText).filter(d => !carried.has(`${upstreamLabel} ${d.id}`));
}

/** 把上游那张图变成可以直接粘贴的围栏：首行换成指向它的来源标记。 */
export function carryableBlock(d, upstreamLabel) {
  return ['```mermaid', `%% 图源 ${upstreamLabel} ${d.id}`,
    ...diagramBody(d), '```'].join('\n');
}

/** 围栏正文：去掉开头那几行来源标记，换标记时不叠加。 */
function diagramBody(d) {
  return d.lines.slice(d.sources.length);
}

/**
 * story 的上游有哪几份 —— 系统设计与 spec，读不到的那份不算，不猜。
 *
 * 上游只列到这两份：产品需求文档里一般不画 `mermaid`，为它留一条通道是空的；
 * 真出现了，作者按内容搬进 story 就是，机器不为一份没有图的文档立判据。
 */
function upstreamDocs(ctx) {
  const out = [];
  for (const [label, ...rel] of [['SR', 'SR', 'design.md'], ['spec', 'spec', 'spec.md']]) {
    const text = readText(path.join(ctx.featureRoot, ...rel));
    if (text !== null) out.push([label, text]);
  }
  return out;
}

//: 不投进归档件的列。「代码现状」是 spec 写给下游 AI 的——仓内路径或检索结论，
//: 读者打不开也用不上，进了归档件还会撞上「不写仓内路径」「不写检索措辞」两条红线，
//: 而机器区作者改不了。投影策略只有这一条，不在合同里逐表登记列白名单：
//: 那会与 spec 模板形成第二真源。
const DROP_COLUMNS = ['代码现状'];

//: 附录三节各从 spec §9 的哪几个小节生成。附录的读者要「拿着回查」，
//: 所以行必须齐——集合核（⑫）盯的就是这里。
const APPENDIX_FROM_SPEC = [
  ['接口', [/^###\s*9\.1/]],
  ['数据、配置与事件', [/^###\s*9\.2/, /^###\s*9\.3/, /^###\s*9\.4/]],
  ['改动边界', [/^###\s*9\.5/]],
];

/** 某个附录小节该有的表：spec 对应几节就给几张，表头按原顺序带过来（去掉不投的列）。 */
function appendixTables(spec, name) {
  const from = APPENDIX_FROM_SPEC.find(x => normalizeHeading(x[0]) === normalizeHeading(name));
  if (!spec || !from) return [];
  const out = [];
  for (const re of from[1]) {
    for (const t of pipeTables(specSection(spec, re))) {
      const keep = t.header.map((h, i) => [h, i])
        .filter(([h]) => !DROP_COLUMNS.some(d => h.includes(d)));
      const rows = t.rows.filter(r => !isPlaceholderRow(r))
        .map(r => keep.map(([, i]) => r[i] ?? ''));
      if (rows.length) out.push({ header: keep.map(([h]) => h), rows });
    }
  }
  return out;
}

/** 一张表渲染成 markdown 行。 */
function renderTable(header, rows) {
  return [`| ${header.join(' | ')} |`, `|${header.map(() => '---').join('|')}|`,
    ...rows.map(r => `| ${r.join(' | ')} |`)];
}

//: 生成区的标记。**这段的所有者是脚本**：内容从真源投影而来，`chapter` 落盘时
//: 原样保留，`skeleton` 可以重渲染。作者要改它，改的是真源（spec §9、
//: knowledge-use.yaml、materials.json），不是这里。
//:
//: 与作者区的分界就是所有权：术语的措辞、流程图的节点文字是**一次性种子**——
//: 种在作者区，之后归作者，脚本不再碰；附录的这几张表是**可重复投影**，
//: 每次都能从真源重算出同样的东西，让作者重打一遍只会打得更少。
const ZONE_BEGIN = '<!-- story-build:begin ';
const ZONE_END = '<!-- story-build:end -->';

const zoneBlock = (name, source, rows) =>
  [`${ZONE_BEGIN}${name} · 由${source}生成，改它请改真源 -->`, ...rows, ZONE_END];

/**
 * 一段正文里某个生成区的行区间（含首尾标记），没有就返回 null。
 */
function zoneSpan(lines, name) {
  const at = lines.findIndex(l => l.startsWith(`${ZONE_BEGIN}${name} `));
  if (at < 0) return null;
  const end = lines.findIndex((l, i) => i > at && l.trim() === ZONE_END);
  return end < 0 ? null : { start: at, end: end + 1 };
}

// --------------------------------------------------------------------------
// check：整篇守恒与形态
// --------------------------------------------------------------------------

const EMPTY_SECTION_TEXT = '本需求不涉及。';

/** 附录里承载材料清单的那一节的名字（合同数据，本文件不写业务词）。 */
function materialSubsectionName(contract) {
  const appendix = appendixChapter(contract);
  return (appendix?.subsections ?? []).find(n => n.includes('材料')) ?? null;
}

/**
 * 材料清单那一节里的全部链接目标，带行号。
 *
 * 与 `scanMaterialList` 的行形态判分开：那条判「这一行有没有链接、链到的目录允不允许」，
 * 这里只把目标取出来，交给调用方判它在不在。两件事分开，报错才说得清是哪一件不成立。
 *
 * @returns {[number, string][]} `[行号, 链接目标]`
 */
function materialLinkTargets(body, baseLine = 0) {
  const out = [];
  const lines = String(body ?? '').split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    for (const m of lines[i].matchAll(/\[[^\]]*\]\(([^)\s]+)\)/g)) out.push([baseLine + i, m[1]]);
  }
  return out;
}

/**
 * 归档件禁用词在 `review.md` 上的**作用域**：把不判的那几段抹成空行。
 *
 * 抹而不是跳过，是为了让行号不变——报错要指得回原文的那一行。
 *
 * 红线管的是**这份文档对产品的承诺**。review 里有两片地方不是承诺：
 *
 * | 不判的 | 为什么 |
 * |---|---|
 * | 人工区（`审核结果：` 之后到该议题的结束标记） | 那是**人的表态**：「不同意，文案回退为上一版」是他在说要改成什么，不是产品要交付回退能力 |
 * | 「其他意见」章（`freeform-zone` 之内） | 同上，整章都是人写的 |
 * | 必答内容就是上线动作 / 开关管控的那几类议题 | 与 story 的章级豁免逐字同一条判据：讲开关放量与上线顺序是这一类议题的本职，把它判成违规等于要求作者删掉评审人最要看的那一段 |
 *
 * **豁免类别由合同数据给**（`decision_categories[].banned_terms_exempt`），
 * 脚本不写死类别名——写死名字换个工程就静默失效。
 *
 * **其余机器区照拦**：议题澄清正文里真的在承诺一种发布方式时，它仍该被拦住。
 */
function redactReviewExemptZones(reviewText, ctx) {
  const text = String(reviewText ?? '');
  if (!text) return text;
  const exemptCats = new Set((ctx.contract.decision_categories ?? [])
    .filter(c => c?.banned_terms_exempt).map(c => c.key));
  const catOf = new Map();
  for (const dec of (readJson(ctx.decisionsPath, null)?.decisions ?? [])) {
    if (dec?.id) catOf.set(String(dec.id), String(dec.category ?? ''));
  }
  // CRLF 安全：这里只喂给禁用词扫描，它自己也按同样的切法，行号对得上就行。
  const lines = text.split(/\r?\n/);
  // 先把每一行归到它所属的议题：结束标记在块尾，所以从标记往回划。
  const owner = new Array(lines.length).fill(null);
  let from = 0;
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/<!--\s*decision:\s*([^\s>-]+)\s*-->/);
    if (!m) continue;
    for (let k = from; k <= i; k++) owner[k] = m[1];
    from = i + 1;
  }
  const keep = new Array(lines.length).fill(true);
  let inFreeform = false;
  let inHuman = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.includes(FREEFORM_OPEN)) inFreeform = true;
    if (inFreeform) { keep[i] = false; if (line.includes(FREEFORM_CLOSE)) inFreeform = false; continue; }
    if (line.startsWith(HUMAN_ZONE_MARK)) inHuman = true;
    if (/<!--\s*decision:/.test(line)) inHuman = false;
    if (inHuman) { keep[i] = false; continue; }
    if (owner[i] && exemptCats.has(catOf.get(owner[i]) ?? '')) keep[i] = false;
  }
  return lines.map((l, i) => (keep[i] ? l : '')).join('\n');
}

/**
 * 把材料清单那一节里的 markdown 链接换成一个占位词，再交给仓内路径与悬空引用扫描。
 *
 * **原文链接是仓内路径唯一允许出现的位置**：归档件的读者打不开这个仓，但他要能
 *据这一行把那份材料找出来——链接是「据哪几份材料写成」这件事唯一可核的形态。
 * 豁免范围只到这一节的链接语法：同一行链接之外的文字照扫，别的章节照扫。
 */
function redactMaterialLinks(storyText, ctx) {
  const appendix = appendixChapter(ctx.contract);
  const name = materialSubsectionName(ctx.contract);
  if (!appendix || !name) return storyText;
  const span = subsectionSpan(storyText, appendix.title, name);
  if (!span) return storyText;
  const lines = String(storyText).split(/\r?\n/);
  for (let i = span.start; i < span.end && i < lines.length; i++) {
    lines[i] = lines[i].replace(/\[[^\]]*\]\([^)\s]*\)/g, '原文链接');
  }
  return lines.join('\n');
}

/**
 * 报错按判据类分组输出。
 *
 * 判定逻辑一个字节不改——各判项照旧 `problems.push(一句话)`，这里只是在每个判据类
 * 开头记一个戳（`mark(...)`），输出时按戳把连续的那一段归到一类。
 *
 * **为什么要分组**：一次报八十几条平铺下来，翻不到头也看不出错在哪一类，
 * 而「报错太多」本身就是删台账的动力——删掉一件依据，报错数当场下去一片。
 * 先给每类一行计数，人（和模型）就知道该从哪一类下手。
 *
 * **不封顶、不截断、不写第二个文件**：封顶要凭空定一个阈值；把明细挪进另一个文件
 * 要求读者多走一步去开它，而人只修看得见的那些，多一步就多一次可能不做。
 * 难读的成因是平铺，分组加计数正面解决它；行数是另一件事，没人提过。
 *
 * @param {string[]} problems
 * @param {{from: number, label: string}[]} marks
 */
function groupedProblems(problems, marks) {
  // 第一个戳之前也可能有报错（判据类之外的前置校验），给它一个兜底类，
  // 这样下面一个循环就覆盖全部，不会有谁掉出去。
  const bounds = [{ from: 0, label: '其它' }]
    .concat(marks.filter(m => m.from < problems.length));
  const out = [];
  for (let i = 0; i < bounds.length; i += 1) {
    const from = bounds[i].from;
    const to = i + 1 < bounds.length ? bounds[i + 1].from : problems.length;
    if (to <= from) continue;                       // 这一类这次没报错
    out.push({ label: bounds[i].label, items: problems.slice(from, to) });
  }
  return out;
}

function cmdCheck(ctx) {
  // 起步先判台账在不在：删掉一件再跑，后面每一条判据都只是「依据不全」的余波。
  requireLedgers(ctx);
  const problems = [];
  // 判据类的分组戳：只影响输出怎么排，不影响判定。
  const marks = [];
  const mark = (label) => marks.push({ from: problems.length, label });
  // 记一笔但不拦：定稿之后材料继续演化是正常的，读者该知道，但它不是错。
  const notes = [];
  // 离线模式（仲裁锚）：没有工程上下文，依赖材料与清单的判项一条不判，
  // 不依赖的照跑——同一个函数，不是另写一套。
  const storyText = readText(ctx.storyPath);
  if (storyText === null) fail(`读不到 ${ctx.storyPath}`);

  const sections = storySections(storyText);
  // 章正文按标题索引：非占位那条按章取正文。
  const sectionText = new Map(sections.map(s2 => [s2.title, s2.text]));
  // 本需求自己的编号不算工程标识——归档件里它是读者回到需求系统的绳子。
  const ownIds = ownIdentifiers(ctx.args.feature);
  const titles = sections.map(s2 => s2.title);
  const want = ctx.contract.chapters.map(c => c.title);

  mark('⓪a 声明的来源都在');
  // ⓪a 合同声明的来源都在
  //
  // 声明的来源压根不在是隐蔽的：那一份材料的内容从头到尾没进过任何一条判据的视野，
  // 门禁却全绿。所以缺一份就各记一笔——必备来源缺了拦，可选来源缺了只记。
  if (!ctx.offline) {
    const { missing } = scanSources(ctx);
    for (const m of missing) {
      notes.push(missingSourceLine(m));
    }
  }

  mark('⓪b 台账没在登记之后被换过');
  // ⓪b 台账没在登记之后被换过
  //
  // story 定稿于登记那一刻，台账记的是它据以成文的依据，于是两者一起冻。
  // 拒绝 init 挡的是命令，挡不住有人直接改文件——指纹核对补上那一面。
  if (!ctx.offline) {
    for (const [name, want2] of Object.entries(storyFrozen(ctx).digests)) {
      const now = digestOf(readText(path.join(ctx.srcDir, name)));
      if (want2 === null && !fs.existsSync(path.join(ctx.srcDir, name))) continue;
      if (want2 !== now) {
        problems.push(`${name} 与成文登记时的台账对不上——`
          + 'story 定稿之后台账随稿冻结，它记的是这份 story 据以成文的依据；'
          + '改了它，产物与依据就对不上了');
      }
    }
  }

  mark('① 章标题与顺序');
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

  mark('①b 大标题带需求编号');
  // ①b 大标题带需求编号：归档件离开这个仓库之后，编号是它与需求系统之间唯一的绳子。
  //
  // 在线时比对的是本 feature 的编号（知道答案就核答案）；离线只有一份 story，
  // 此时退一格核**形态**——首个词是编号形态即可。两条路都拦得住「标题只有需求名」。
  const h1 = String(storyText).split(/\r?\n/).find(l => /^#\s+\S/.test(l.trim()));
  const h1Text = h1 ? h1.trim().replace(/^#\s+/, '') : '';
  if (!h1Text) {
    problems.push('没有大标题——归档件的第一行是 `# <需求编号> <需求名称>`');
  } else if (ctx.args.feature) {
    if (!h1Text.includes(ctx.args.feature)) {
      problems.push(`大标题缺需求编号：写成 \`# ${ctx.args.feature} <需求名称>\``
        + '——归档件流转出去之后，读者靠这个编号回到需求系统');
    }
  } else if (!/^[A-Za-z][A-Za-z0-9-]*\d[A-Za-z0-9-]*(\s|$)/.test(h1Text)) {
    problems.push(`大标题缺需求编号：「${h1Text.slice(0, 30)}」`
      + '——第一行写成 `# <需求编号> <需求名称>`');
  }

  mark('③ 编号形态');
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

  mark('⑤ 决策登记字段齐备');
  // ⑤ 决策登记的字段齐备（离线模式没有需求目录，这一项不判）
  //
  // **只判形式，不判数量、不判叙述**。数量下限会催生凑数议题——凑数比零议题更坏，
  // 它把评审人的注意力摊薄在假议题上；叙述质量的判据会催生套话，模型总能写出
  // 一段过得去而什么也没说的话。数量塌陷与叙述质量由评审记录的效果定义、
  // verifier 的逐问、以及评审人自己接。这里只核「渲染得出来」：
  // 标题、澄清正文、请谁确认，缺一条渲出来就是半个议题。
  const decisions = ctx.offline ? null : readJson(ctx.decisionsPath, null);
  if (ctx.offline) { /* 仲裁锚只判文档本身 */ }
  else if (!decisions) problems.push('缺 decisions.json——决策登记是 review 的唯一数据源');
  else {
    const list = Array.isArray(decisions.decisions) ? decisions.decisions : [];
    for (const dec of list) {
      for (const [field, what] of DECISION_FIELDS) {
        if (!String(dec?.[field] ?? '').trim()) {
          problems.push(`决策 ${dec?.id ?? '（无编号）'} 缺${what}——`
            + '这一条渲染出来会是半个议题，评审人看不出要他表什么态');
        }
      }
      // 澄清正文里的小标题用**加粗段首**，不用 `#` 标题行。
      //
      // 议题在 review.md 里已经有三级层次（状态分章、类型成节、逐条成项），
      // 澄清正文里再起标题行，等于在第四级上又开一层——渲染出来层次就乱了。
      // 层级写平会让分组消失。
      if (/(^|\n)\s*#{1,6}\s/.test(String(dec?.clarification ?? ''))) {
        problems.push(`决策 ${dec?.id ?? '（无编号）'} 的澄清正文里有标题行`
          + '——小标题写成加粗段首（`**要点**：…`）；'
          + '议题的层次由状态分章、类型成节、逐条成项给出，正文里再起标题会把它压乱');
      }
      // 类别决定它成章落在哪一节。**只判在不在词表里**——不判每类有没有条目、
      // 不判数量、不判空类要不要解释：那些是配额，配额逼出来的是凑数与逃生口。
      const keys = (ctx.contract.decision_categories ?? []).map(c => c?.key);
      const category = String(dec?.category ?? '').trim();
      if (keys.length && !keys.includes(category)) {
        problems.push(`决策 ${dec?.id ?? '（无编号）'} 的类别`
          + `${category ? `「${category}」不在词表里` : '没登记'}——`
          + `从这十一类里挑一个：${keys.join(' / ')}`);
      }
    }
  }

  mark('⑦ 规约判定表');
  // ⑦ 规约判定表：激活清单的每个条目在附录的「规约判定」小节有一行，
  //    或其整域一行「整域不适用」
  //
  // 判定写在 story 里：评审者据这一节回显完备性——激活了几条、各自命中与否、依据是什么。
  //
  // 落点在**附录**而不是主叙事的某一章：规约编号是工程标识，读者对不上，
  // 写进主叙事就是在打断阅读；附录给了它一个不打断阅读、机器又核得到的位置。
  // 激活规约的编号**直接取激活清单**：经「材料单元」那一层只是把同一份数据换个形状，
  // 而多一层就多一处会与清单失同步的地方——判定表少判一条规约是静默的。
  //
  // **这张表是 `spec/knowledge-use.yaml` 的投影**（`story-build project` 投的），
  // 所以判定的值域、依据非空、与 YAML 一致三件事在投影那一步就成立了：
  // 投影只写命中/不命中，缺依据时它响亮失败。这里只剩一条——**每条规约有行**：
  // 作者手改 story.md 删掉一行，下一次投影才会补回来，这中间要有人看见。
  const kEntries = activeKnowledgeEntries(ctx);
  if (kEntries.length) {
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
      for (const e of kEntries) {
        const id = e.id;
        const domain = e.domainTitle ?? '';
        const row = rows.get(id);
        if (!row) {
          if (domainRows.has(domain)) continue;   // 整域不适用，覆盖域内全部条目
          problems.push(`规约 ${id}（${domain}）在附录·${verdictName}的判定表里没有行`
            + `——判「不命中」也要有一行；整域不适用就给该域一行「${DOMAIN_NA}」`);
          continue;
        }
      }
    }
  }

  mark('④ 图片身份');
  // ④ 图片身份：story 引了哪些图、每一张是不是材料清单里登记过的那一张。
  //
  // 这两条是确定性的链接与图片检查，单独成块：判的是「引用可不可解析、
  // 在不在登记里」，与作者画了几张无关，所以不跟形态守恒放一起。
  const imgs = [...storyText.matchAll(/!\[([^\]]*)\]\(([^)\s]+)/g)];
  const seen = new Set();
  for (const [, alt, src] of imgs) {
    if (!alt.trim()) problems.push(`图片 ${src} 没有 alt 文本`);
    if (seen.has(src)) problems.push(`图片 ${src} 在 story 里出现了不止一次`);
    seen.add(src);
  }

  {
    // 图片身份：引到的每一张都要是材料里登记过的那一张，按**内容**认，不按文件名认。
    //
    // 只比文件名时，改名的拦得住、同名复制进一个新目录的拦不住——那种形态是自建
    // 一个图片目录，全树因此有五份同一张图。归档件自己的图片目录是允许的副本区，
    // 但放进去的必须真的是材料里那张图的副本，而不是另一张图顶着这个名字。
    const registered = materialImages(ctx);
    if (registered === 'broken') {
      problems.push('AR/story-src/materials.json 读不出材料清单——图片引用无从核对身份。'
        + '它只应由脚本写入，若曾手工编辑，删掉后重跑 `story_flow.py round`');
    } else if (!registered) {
      notes.push('没有材料清单（AR/story-src/materials.json），图片身份与落点判据未执行'
        + '——跑 `story_flow.py round` 生成它之后这条才判得了');
    } else if (registered.length) {
      const storyDir = path.dirname(relFromFeature(ctx, ctx.storyPath));
      const byPath = new Map();
      registered.forEach((m, i) => m.paths.forEach(rel => byPath.set(rel, i)));
      const archiveDir = ctx.contract.story_image_dir
        ? joinPosix(storyDir, ctx.contract.story_image_dir) : null;
      const usedBy = new Map();            // 登记序号 → story 里引到它的那些路径
      for (const src of seen) {
        if (/^(https?:|data:)/i.test(src)) continue;
        const rel = joinPosix(storyDir, src);
        let idx = byPath.has(rel) ? byPath.get(rel) : -1;
        const inArchive = archiveDir && (rel === archiveDir || rel.startsWith(`${archiveDir}/`));
        if (idx < 0 && inArchive) {
          // 归档副本区：按字节找出它是材料里的哪一张
          const here = path.join(ctx.featureRoot, ...rel.split('/'));
          idx = registered.findIndex(m => m.paths.some(
            p2 => sameBytes(here, path.join(ctx.featureRoot, ...p2.split('/')))));
          if (idx < 0) {
            problems.push(`归档目录里的图片「${src}」不是材料里任何一张图的副本`
              + '——归档目录只放材料里那些图的副本，放别的等于凭空多出一张没有出处的图');
            continue;
          }
        }
        if (idx < 0) {
          problems.push(`story 引用的图片「${src}」不在材料的图片登记里`
            + '——引它在仓里的既有落盘位置，不要复制一份到别处再改名；'
            + '副本没人维护，改了名读者也认不出它就是原来那张');
          continue;
        }
        if (!usedBy.has(idx)) usedBy.set(idx, []);
        usedBy.get(idx).push(src);
      }
      for (const [idx, srcs] of usedBy) {
        if (srcs.length < 2) continue;
        problems.push(`同一张图被两个路径引用：${srcs.join('、')}`
          + `（材料里登记为 ${registered[idx].paths.join('、')}）`
          + '——同一张图只引一次，一处说清它画的是什么');
      }

      // 每张图都有去处：要么正文引了，要么在材料清单里登记了为什么不用。
      //
      // 判的是**去处**不是义务：图可以不用——参考稿废弃了、那是友商的、
      // 那是别的单据的页面，都是正当理由。不正当的是它在材料里而去向没人说过，
      // 读者无从知道你看没看过它。理由成不成立由读者审查判，这里只报缺口。
      const mark = rel => '`import_sources.py --feature <名> --caption-image ' + rel;
      for (const [i, m] of registered.map((m2, i2) => [i2, m2])) {
        const declined = String(m.unused ?? '').trim();
        if (usedBy.has(i) && declined) {
          problems.push(`「${m.paths[0]}」登记着不用的理由（${declined}），正文却引了它——`
            + '二者取其一：属于本需求就 ' + mark(m.paths[0]) + ' --used` 清掉理由，'
            + '不属于本需求就把正文里那处删掉');
        } else if (!usedBy.has(i) && !declined) {
          problems.push(`材料里登记的图「${m.paths[0]}」${m.caption ? `（${m.caption}）` : ''}`
            + '在 story 里没被引用，也没登记为什么不用——'
            + '属于本需求就在讲它的那一章引用（图前一句说清它画的是什么），'
            + '不属于本需求就跑 ' + mark(m.paths[0]) + ' --unused "<为什么不用它>"`；'
            + '归档件不为一张不用的图留正文');
        }
      }
    }
  }

  mark('⑨ 归档件四红线');
  // ⑨ 归档件四红线：仓内路径 / 客户端禁用词 / 悬空引用 / 图片断链
  //
  // 归档件随需求上传，评审者手上没有这个仓：点不开的引用他不知道是坏的。
  // 词表与判定在 lint-rules.mjs（SSOT），这里只调。
  const reviewText = readText(ctx.reviewPath) ?? '';
  // 章级豁免由合同数据给（`banned_terms_exempt`）：讲发布动作的那一章里，
  // 「灰度」「回退」是业务事实不是客户端文案——收缩的是作用域，不是词表。
  const bannedExempt = ctx.contract.chapters.filter(c => c.banned_terms_exempt).map(c => c.title);
  // 材料清单里的**原文链接是唯一允许仓内路径出现的位置**：读者据它把那份材料找出来，
  // 不给链接他只知道「有一份产品需求文档」。豁免只到这一节的链接语法为止——
  // 正文里的仓内路径照拦，这一节里链接之外的文字也照拦。
  const storyForPaths = redactMaterialLinks(storyText, ctx);
  // review 的禁用词作用域比别的判据窄：人工区与「上线/管控」类议题不判，
  // 见 `redactReviewExemptZones`。词表一个字没削，收的是作用域。
  const reviewForBanned = redactReviewExemptZones(reviewText, ctx);
  for (const [label, text, bannedText] of [
    ['story', storyForPaths, storyForPaths],
    ['review', reviewText, reviewForBanned],
  ]) {
    if (!text) continue;
    for (const [what, kind, hits] of [
      ['仓内路径', 'local', scanLocalPaths(text, ctx.projectRoot)],
      ['客户端语境禁用词', 'banned',
        scanBannedTerms(bannedText, { exemptChapters: bannedExempt })],
      ['悬空引用', 'dangling', scanDanglingRefs(text, ctx.projectRoot)],
      ['图片断链', 'image',
        scanBrokenImages(label === 'story' ? storyText : text,
                         path.dirname(ctx.storyPath), fs, path)],
    ]) {
      if (hits.length) problems.push(`${label} 出现${what} ${hits.length} 处：${formatHits(hits, kind)}`);
    }
  }

  mark('⑩ 语言红线');
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
    const hits = scanLanguageRedline(storyText, {
      appendixTitle: appendix?.title,
      ruleIds: kEntries.map(e => e.id),
      kinds: redlineKinds,
      harnessTerms: ctx.contract.language_redline?.harness_terms ?? [],
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

  mark('⑪ 形态守恒');
  // ⑪ 形态守恒：合同 `form` 说这一章要有哪几个槽位，就核它们在不在。
  //
  // **一条判据读数据**，不为每个槽位各写一条：加一个槽位改合同，这段代码不动。
  // 核的只有存在与必有列——不核行数、不核表的总数、不核槽位之外有没有表。
  // 形态来自内容的关系；把「这个需求适合有」写成「每个需求都要有」，
  // 判据就开始替作者编内容，而那正是形态判据上一次失败的地方。
  //
  // 报错带上合同里那句形态说明：作者看到的是「这一章该怎么写」，不是「第几条判据红了」。
  for (const ch of ctx.contract.chapters) {
    const form = ch.form;
    const text = sectionText.get(ch.title);
    if (!form || text === undefined) continue;        // 章缺失由 ① 报，这里不重复
    if (text.trim() === EMPTY_SECTION_TEXT) continue;  // 空节已明说不涉及，没有形态可言
    const subs = subsectionNames(text);
    if (form.sections === 'none' && subs.length) {
      problems.push(`「${ch.title}」不该拆小节（有「${subs[0].raw}」）——${form.note ?? ''}`);
    }
    if (form.sections === 'named') {
      for (const want of ch.subsections ?? []) {
        if (findSubsection(text, want) === null) {
          problems.push(`「${ch.title}」缺「${want}」这一节——${ch.subsections_note ?? form.note ?? ''}`);
        }
      }
    }
    for (const [at, slot] of Object.entries(form.slots ?? {})) {
      // `*` 指按业务命名的那些小节：合同点名的固定节各有自己的槽位，不套这一份。
      const named = (ch.subsections ?? []).map(normalizeHeading);
      const targets = at === '*'
        ? subs.filter(x => !named.some(n => x.name.includes(n)))
          .map(x => [`${ch.title}·${x.raw}`, subsectionText(text, x.name)])
        : at === ''
          ? [[ch.title, text]]
          : [[`${ch.title}·${at}`, findSubsection(text, at)]];
      if (slotCondition(ctx, slot.when) === false) {
        // 条件不成立的节不该存在：没有兄弟单据却写了「交接约定」，那一节填进去的
        // 只能是别的东西——常见的是把端云约定塞进来充数。
        for (const [label, body] of targets) {
          if (at && at !== '*' && body !== null) {
            problems.push(`「${label}」这一节不该有`
              + `（${slot.when === 'siblings' ? '本需求没有兄弟单据' : '条件不成立'}）`
              + `——${form.note ?? ''}`);
          }
        }
        continue;
      }
      for (const [label, body] of targets) {
        if (body === null) continue;                  // 小节在不在由 sections 档与语义审查管
        if (slot.table && !slot.table_draft_only && slotApplies(ctx, slot.table_when)) {
          const first = slot.table_anchor || String(slot.table).split('|')[0];
          const anchor = norm(first);
          // 按子串比：锚说的是这张表的主语，作者用「受限状态」还是「受限情形」是措辞。
          if (anchor && !tableHeaders(body).some(h => h.some(c => c.includes(anchor)))) {
            problems.push(`「${label}」缺一张表（第一列是「${first}」）——${form.note ?? ''}`);
          }
        }
        if (slot.ordered && !/^[ \t]*\d+[.、)]\s/m.test(body)) {
          problems.push(`「${label}」要写成有序列表，一步一句——${form.note ?? ''}`);
        }
        for (const lb of slot.labels ?? []) {
          if (!body.includes(lb)) problems.push(`「${label}」缺「${lb}」这一段——${form.note ?? ''}`);
        }
        if (slot.diagram) {
          DIAGRAM_FENCE.lastIndex = 0;          // 正则带 /g，每次用前把游标归零
          if (!DIAGRAM_FENCE.test(body)) {
            problems.push(`「${label}」一张图都没有——${form.note ?? ''}`);
          }
        }
      }
    }
  }

  mark('⑫ 附录结构');
  // ⑫ 附录结构：只有合同约定的那几节，节内是表和列表，每节都有内容
  //
  // 附录是全篇唯一允许出现工程标识的地方，于是它天然最容易变成倾倒区——
  // 常见形态是多长出一个「机器核对索引」之类的小节，把原文整段搬进去，占掉全篇大半。
  // 判的是结构不是内容：约定之外的小节、原文围栏块、空节，三样都不该有。
  const appendixDef = appendixChapter(ctx.contract);
  const appendixSection = appendixDef
    ? sections.find(sec => sec.title === appendixDef.title) : null;
  const wantSubs = (appendixDef?.subsections ?? []).map(normalizeHeading);
  const materialName = materialSubsectionName(ctx.contract);
  if (appendixSection && wantSubs.length) {
    for (const sub of subsectionNames(appendixSection.text)) {
      if (!wantSubs.includes(sub.name)) {
        problems.push(`「${appendixDef.title}」多了一节「${sub.raw}」`
          + `——${appendixDef.title}只有约定的这几节：${wantSubs.join('、')}；`
          + '工程细节各有落点表，叙述归正文章');
      }
    }
    for (const want of wantSubs) {
      const body = subsectionText(appendixSection.text, want);
      if (body === null) {
        problems.push(`「${appendixDef.title}」缺「${want}」这一节`
          + '——确实不涉及也要留标题，写「不涉及：<依据>」一行');
        continue;
      }
      const rows = body.split(/\r?\n/).map(l => l.trim())
        .filter(l => l.startsWith('|') || /^[-*+]\s/.test(l) || /^\d+[.)]\s/.test(l));
      if (!rows.length && !/不涉及[:：]\s*\S/.test(body)) {
        problems.push(`「${appendixDef.title}·${want}」是空的`
          + '——成表或成列表，确实不涉及就写「不涉及：<依据>」一行');
        continue;
      }
      // 表外零散文：一句目的句 + 表格行（材料清单是列表行），其余正文段逐段点名。
      // 散文尾巴是倾倒区的最后一种形态——附录五节被锁死之后，没地方去的工程细节
      // 就挤到表后面成段。
      // 「不涉及：<依据>」独行豁免：那是空节规则的既有形态，不算散文段。
      if (appendixDef.subsection_form) {
        // 判的是**尾巴**：开头那一句是目的句（该有的），跟在表或列表后面的那些，
        // 是没地方去的工程细节挤出来的。
        //
        // **材料清单那一节例外，逐块判**：它成的是列表不是表，只看「列表之后」的话，
        // 列表**之前**就成了不设防区——图连同
        // 四段说明全塞在那里，判据一条都没响。这一节的形态是「一句目的句 + 列表行」，
        // 那就按它判：目的句之外的散文块，在前在后一样点名。
        const wholeSection = want === normalizeHeading(materialName ?? '');
        const blocks = proseBlocks(body)
          .filter(p => !/不涉及[:：]\s*\S/.test(p.text));
        const tail = wholeSection ? blocks.slice(1) : blocks.filter(p => p.afterRows);
        for (const p of tail) {
          problems.push(`「${appendixDef.title}·${want}」${wholeSection ? '目的句之外还有' : '表后还有'}一段正文`
            + `（「${p.text.slice(0, 18)}…」）`
            + `——${appendixDef.subsection_form.note ?? '该进表的内容进表成行'}`);
        }
      }
    }
    for (const line of appendixSection.text.split(/\r?\n/)) {
      const fence = line.trim().match(/^(?:```|~~~)\s*(\w*)/);
      if (fence && fence[1] && fence[1] !== 'mermaid') {
        problems.push(`「${appendixDef.title}」里有 ${fence[1]} 围栏块`
          + `——${appendixDef.title}是表和列表，不是原文存放处`);
        break;
      }
    }

    // 附录里不放图。反复出现的形态是：正文各章写着「下图是…」，图却整批迁进附录，
    // 读者读到那句话时手边没有图，要翻到最后再翻回来。
    //
    // 与集合一致那一条合起来看：登记的图要有去处，而附录不是去处。用它就放在讲它的那一章，
    // 不用它就在材料清单那一行写明理由——理由是文字，不是把图挪到附录充数。
    const inAppendix = [...appendixSection.text.matchAll(/!\[[^\]]*\]\(([^)\s]+)/g)]
      .map(m => m[1]);
    if (inAppendix.length) {
      problems.push(`「${appendixDef.title}」里有 ${inAppendix.length} 张图`
        + `（${inAppendix.slice(0, 3).join('、')}${inAppendix.length > 3 ? '…' : ''}）`
        + '——图片放它讲的那一章，跟着讲它的那句话走；'
        + `${appendixDef.title}是查阅件，读者不会为了看一张图翻到这里来`);
    }
  }

  mark('⑫b spec 契约不丢行');
  // ⑫b 附录 A/B/C 的行 ⊇ spec §9 对应表的行（按第一列的标识对齐）。
  //
  // 成文顺序里 spec 先于 story，附录三节是它的投影而不是重写。手抄一遍必然更少：
  // 接口丢掉入参出参与错误码、几个埋点合成一行都是见过的形态，
  // 而评审者正是拿着附录回查契约的。
  // 只核标识在不在：措辞、列的增减、行的顺序都由作者定。
  const specForRows = specText(ctx);
  if (specForRows && appendixSection) {
    for (const [name] of APPENDIX_FROM_SPEC) {
      const want = appendixTables(specForRows, name).flatMap(t => t.rows.map(r => r[0]));
      if (!want.length) continue;
      const body = subsectionText(appendixSection.text, name) ?? '';
      const have = new Set(pipeTables(body).flatMap(t => t.rows.map(r => norm(r[0]))));
      const missing = want.filter(id => !have.has(norm(id)));
      if (missing.length) {
        problems.push(`「${appendixDef?.title ?? '附录'}·${name}」少了 spec §9 里的 `
          + `${missing.length} 行：${missing.slice(0, 4).join('、')}`
          + `${missing.length > 4 ? '…' : ''}`
          + '——附录是 spec 契约的投影，评审者拿着它回查；可以改措辞、可以加列，不能少行');
      }
    }
  }

  // 上游每张图，story 里各有一个围栏带着它的来源标记。
  //
  // story 的上游有两份：系统设计（SR）与 spec。图属于哪块内容，内容在 story 落在哪，
  // 图就该在哪——不是「上游有几张图，story 就派生几节」。所以这里不判位置、不判张数，
  // **只判登记对应**：标记在，说明这张图被登记着搬过来了；它搬得对不对、
  // 周围那句话说的是不是它，要读上下文，归独立审查。
  // 缺了报的是**这张图讲的那件事**，作者据此去找内容，而不是去补一张图。
  for (const [label, upstream] of upstreamDocs(ctx)) {
    for (const d of diagramsNotCarried(upstream, label, storyText)) {
      problems.push(`${label} ${d.id} 的图（${diagramTopic(d)}）在 story 里没有。`
        + '先看它讲的那件事在 story 哪一章：讲了而图漏了，把图搬到那一节；'
        + '没讲，是内容丢了，先补内容再搬图。'
        + `搬的时候围栏第一行写 \`%% 图源 ${label} ${d.id}\`——周围的文字自己写，`
        + 'story 讲给评审者的是来龙去脉，上游那份讲的是别的事');
    }
  }

  mark('⑫a 非占位');
  // ⑫a 非占位：章有正文、模板占位符已经换掉。**只有这两件事**。
  //
  // 「这一章写没写」是可以机械判的，「写得够不够」不是。所以这里不设字数、行数、
  // 表格数、图片数与条目数的下限——一句合法内容的章照样通过。凡是设了下限的判据，
  // 逼出来的都是凑数：给一个不涉及表格的章设「至少一张表」，作者只会造一张空表。
  // 写得够不够、讲清没讲清由独立审查判，那是它能判而脚本判不了的事。
  for (const chapter of ctx.contract.chapters ?? []) {
    const body = sectionText.get(chapter.title);
    if (body === undefined) continue;               // 章缺失由 ① 报，这里不重复
    if (!norm(body)) {
      problems.push(`「${chapter.title}」只有标题没有正文`
        + `——本需求真的不涉及它时写「${EMPTY_SECTION_TEXT}」，那是明说过的结论；`
        + '空着分不清「判过了不涉及」与「还没写」');
    }
  }
  {
    // 待写 marker：骨架给每章留的那个记号，写完一章就该被那一章的内容顶掉。
    // 它还在，说明这一章还没写——骨架被当成品交出去是常见形态。
    const left = pendingChapters(storyText);
    if (left.length) {
      problems.push(`还有 ${left.length} 章带着待写 marker：${left.join('、')}`
        + '——每章写完用 `story-build chapter --chapter <章名> --from <文件>` 落盘，'
        + '那条命令会把 marker 连同占位一起换掉');
    }
  }
  {
    // 模板占位符：`{{…}}` 是模板留给作者替换的位置，留在成品里就是没写完。
    // 判的是这个明确记号本身，不是「这段像不像占位」——后者是猜。
    const lines = storyText.split(/\r?\n/);
    for (let i = 0; i < lines.length; i++) {
      const hit = /\{\{[^}]*\}\}/.exec(lines[i]);
      if (!hit) continue;
      problems.push(`第 ${i + 1} 行还留着模板占位符「${hit[0]}」`
        + '——它是模板留给你替换的位置，换成这一节真正要写的内容');
    }
  }

  mark('⑫c 形态 lint');
  // ⑫c 形态 lint：图的承接、材料清单的行形态
  //
  // 材料清单的行形态：判的是形态不是内容——
  // 只问「这一行能不能把材料定位到原件」。图题编号与小节编号已归 `number` 机器铺，不再判。
  // **「这句话指的是不是这张图」仍不在这里判**：那要读上下文，归独立审查。
  // 这里只判两件不用读懂任何一句话就能看见的事——图前面有没有一句话、两张图挨着没有。
  problems.push(...danglingFigures(storyText, ctx.contract));
  {
    const appendix = appendixChapter(ctx.contract);
    const name = materialSubsectionName(ctx.contract);
    const span = appendix && name ? subsectionSpan(storyText, appendix.title, name) : null;
    if (span) {
      const body = storyText.split(/\r?\n/).slice(span.start, span.end).join('\n');
      const want = materialListTargets(ctx);
      const haveManifest = want && want !== 'broken';
      // 行形态（有没有链接、是不是写成了表格）一直判；**链到的地方允不允许**分两条路：
      // 有材料清单时按清单逐份对（下面那段），没有清单才退回按目录白名单粗判。
      // 两条同时开会对同一行报两遍——同一件事报两次，读的人以为是两个问题。
      for (const h of scanMaterialList(body, span.start + 1,
        { allowDirs: haveManifest ? [] : (ctx.contract.material_dirs ?? []) })) {
        problems.push(`「${appendix.title}·${name}」第 ${h.line} 行——${h.hint}`);
      }
      // 链接得能点开 —— 只在线上判，因为只有线上才知道那份文件在不在。
      //
      // 典型写法 `[RR/prd.md](RR/prd.md)` 解析不到：story.md 在 AR/ 下，
      // 这个裸相对路径解析出来是 `AR/RR/prd.md`——**不存在**。上面那条范围判
      // 抓不到它：它只看链接落在需求目录的哪一段，`RR` 在允许集里就放行，
      // 而「RR 这一段允许链」与「这个链接能不能点开」是两件事。
      //
      // 离线不判存在性：那时没有 feature 上下文，基准目录只能靠猜，而判据一旦
      // 开始猜就没法解释也没法回归。离线拿到的往往是一份脱离需求目录的独立文件，
      // 它身边本就没有 RR/ 与 AR/——形态判照跑，存在性留给线上。
      if (!ctx.offline) {
        const fromDir = path.dirname(ctx.storyPath);
        for (const [line, target] of materialLinkTargets(body, span.start + 1)) {
          if (/^(https?:|mailto:)/i.test(target)) continue;
          if (!fs.existsSync(path.resolve(fromDir, target))) {
            problems.push(`「${appendix.title}·${name}」第 ${line} 行的链接点不开：`
              + `${target} —— 从归档件所在的位置解析不到这份文件。`
              + '读者打不开这个仓，链接是「据哪几份材料写成」唯一可核的形态，'
              + '指错了等于没指');
          }
        }
      }
      // 集合面：列到的与真正在手里的那几份材料对得上
      if (want === 'broken') {
        problems.push('AR/story-src/materials.json 读不出材料清单——'
          + `「${appendix.title}·${name}」列得全不全无从核对。`
          + '它只应由脚本写入，若曾手工编辑，删掉后重跑 `story_flow.py round`');
      } else if (!want) {
        notes.push(`没有材料清单（AR/story-src/materials.json），`
          + `「${appendix.title}·${name}」的集合判据未执行`
          + '——跑 `story_flow.py round` 生成它之后这条才判得了');
      } else {
        const storyDir = path.dirname(relFromFeature(ctx, ctx.storyPath));
        const listed = new Set();
        for (const [, target] of materialLinkTargets(body, span.start + 1)) {
          if (/^(https?:|mailto:)/i.test(target)) continue;
          listed.add(joinPosix(storyDir, target));
        }
        const allowed = new Set(want.must.flat());
        for (const group of want.must) {
          if (!group.some(rel => listed.has(rel))) {
            problems.push(`「${appendix.title}·${name}」少了一份材料：${group[0]}`
              + '——它在这一轮的材料里，读者据这一节把材料找出来，漏一份等于那份材料没人知道');
          }
        }
        for (const rel of listed) {
          if (allowed.has(rel)) continue;
          problems.push(`「${appendix.title}·${name}」列了不是初始资料的东西：${rel}`
            + '——这一节回答「据哪几份材料写成」：上游那几份正文与收件箱原件，'
            + '各一行。本轮自己生成的规格与记录不是材料；'
            + '图的去向登记在材料清单里（`--caption-image … --unused`），不写在这一节');
        }
      }
    }
  }
  // 小节编号不在这里判：它由 `number` 命令统一铺（D1）。机器保证的形态再设一条
  // 判据，判的是自己的输出——真正会漏的是机器不做的那部分。

  mark('⑫d 统稿留痕');
  // ⑫d 统稿留痕：`copyedit.md` 恰好七行，一项自查一行
  //
  // 统稿（通读全篇、收重复收承接收样式）是唯一一步没有任何产物的动作，于是跳过它
  // 零成本——「同一件事讲三遍」「图题一章一个样」这类只有通读才看得见
  // 的毛病，而门禁全绿。留痕不是为了核内容（写没写到位由语义审查与抽样人核），
  // 是为了让「没做」这件事留下痕迹。
  //
  // **只写七行，写多不奖励**：把它写成检查报告，下一轮就有人为了显得认真而灌水。
  if (!ctx.offline) {
    const copyedit = readText(ctx.copyeditPath);
    if (copyedit === null) {
      problems.push(`缺 ${path.basename(ctx.copyeditPath)}`
        + '——统稿完成后在这里写七行，七项自查各一行「查了什么／改了几处或无」');
    } else {
      const rows = copyedit.split(/\r?\n/).map(l => l.trim()).filter(Boolean).length;
      if (rows !== COPYEDIT_ROWS) {
        problems.push(`${path.basename(ctx.copyeditPath)} 有 ${rows} 行`
          + `（要求恰好 ${COPYEDIT_ROWS} 行，空行不计）`
          + '——六项自查各一行；写成检查报告不加分，下一轮只会有人为了显得认真而灌水');
      }
    }
  }

  mark('⑬ 评审记录只含渲染语法');
  // ⑬ 评审记录只含渲染语法：出现填写说明、签署字段、状态行、下一步就是表单在膨胀
  //
  // 判据是「需要说明书就是设计错了」。这几样每次都以「让评审更规范」的名义长回来，
  // 而它们的实际后果是评审人先读一遍字段表，再在答不上来的格子里胡填。
  // **只判机器渲染的那部分**：评审人自己写在「审核结果：」后面的内容不计。
  if (reviewText) {
    const banned = REVIEW_BANNED_LINES.filter(
      ({ re }) => reviewText.split(/\r?\n/).some(l => re.test(l.trim())));
    for (const { name } of banned) {
      problems.push(`评审记录里出现「${name}」——评审人要填的只有「审核结果：」后面那几句话；`
        + '填写说明、签署字段、状态行都被裁掉过，它们只会让人在答不上来的格子里胡填');
    }
  }

  mark('⑭ 交付门');
  // ⑭ 交付门：只有 `check --deliver` 判，普通 check 恒不判。
  //
  // 两个入口同一实现，按**动作**分而不按文件在不在推断阶段：登记前与返修中跑的是
  // 普通 check，那时读者审查还没发生，判它只会得到一个恒定的「不适用」；
  // 交付（远程单上传前、本地单闭环后）跑的是 `--deliver`，那时闭环该已经成立。
  if (ctx.args.deliver) {
    const delivery = deliveryProblems(ctx);
    problems.push(...delivery.problems);
    notes.push(...delivery.notes);
  }

  if (notes.length) {
    process.stdout.write('[story-build check] 记一笔（不拦）：\n');
    notes.forEach(n => process.stdout.write(`  · ${n}\n`));
  }
  if (problems.length) {
    const groups = groupedProblems(problems, marks);
    process.stderr.write(`[story-build check] ${problems.length} 处未通过，`
      + `分属 ${groups.length} 类：\n`);
    for (const g of groups) {
      process.stderr.write(`  [${g.label}] ${g.items.length} 处\n`);
    }
    process.stderr.write('\n');
    let n = 0;
    for (const g of groups) {
      process.stderr.write(`  [${g.label}]\n`);
      for (const item of g.items) {
        n += 1;
        process.stderr.write(`  ${n}. ${item}\n`);
      }
    }
    process.exit(1);
  }
  process.stdout.write(`[story-build check] 通过：${sections.length} 章\n`);
  // 交付门通过 = 这份 story 可以交出去了。往下有两条路，**由人选**——
  // 归档送审与进入 plan 都是正当的下一步，谁先谁后取决于这个需求的排期。
  if (ctx.args.deliver) process.stdout.write(deliveryNextSteps(ctx));
}

/**
 * 框架回执的入口 —— 直接用 node 起 framework 自己那份 ts-node，不经 shell。
 *
 * `npx` 在 Windows 上是 `npx.cmd`，而 Node 从 18.20 / 20.12 起拒绝不带 shell 地起 `.cmd`
 * （`EINVAL`）；带 shell 又要为参数里的空格与引号操心。装 ts-node 的是 framework/harness
 * 自己，路径解析得到就直接把它当普通 js 跑，两边都不用碰。
 */
function receiptRunner(harness) {
  try {
    const require = createRequire(import.meta.url);
    return require.resolve('ts-node/dist/bin.js', { paths: [harness] });
  } catch {
    return null;
  }
}

/**
 * 图有没有被正文接住 —— 两件机械可见的事，不判「这句话说的是不是这张图」。
 *
 * 引一张图的正常写法是：先一句话说它画的是什么，再是图，图后接着讲。
 * 两种形态不用读懂任何一句话就能看出不对：
 *
 * - **图连图**：两张图挨在一起，中间没有一句话。读者不知道该看哪张、看什么。
 * - **图前没有承接句**：上一非空行是标题、是另一张图，或者图就在节首。
 *   那说明这张图是被贴进来的，不是被讲到的——「按清单把图都引上」正是这个形态。
 *
 * 附录不看：图本来就不该在那里，由「附录里不放图」那条判。
 */
function danglingFigures(storyText, contract) {
  const appendix = appendixChapter(contract);
  const out = [];
  const lines = String(storyText ?? '').split(/\r?\n/);
  const isImage = (l) => /^\s*!\[[^\]]*\]\(/.test(l);
  let inAppendix = false;
  let prev = null;                                   // 上一非空行
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const h = line.trim().match(/^##\s+(.+?)\s*$/);
    if (h) {
      inAppendix = appendix ? normalizeHeading(h[1]) === normalizeHeading(appendix.title) : false;
      prev = line;
      continue;
    }
    if (!line.trim()) continue;
    if (isImage(line) && !inAppendix) {
      const why = prev === null || /^#{1,6}\s/.test(prev.trim()) ? '它就在小节开头'
        : isImage(prev) ? '它紧挨着上一张图'
          : null;
      if (why) {
        out.push(`第 ${i + 1} 行的图前面没有一句话（${why}）`
          + '——引一张图先说它画的是什么，再是图，图后接着讲。'
          + '接不上一句话的图，说明它是被贴进来的，不是被讲到的：'
          + '本需求用不上就别引，跑 `import_sources.py --feature <名> '
          + '--caption-image <这张图> --unused "<为什么不用它>"` 登记它的去向');
      }
    }
    prev = line;
  }
  return out;
}

/**
 * 交付门通过之后往哪走 —— 打印选项，**不替人选**。
 *
 * 远程单可以先归档送审再进 plan，也可以两边同时开始；本地单没有归档，只剩 plan。
 * 这是脚本给的确定性文本，与 `story_flow.py status` 同一口径。
 */
function deliveryNextSteps(ctx) {
  const remote = readJson(ctx.flowPath, null) !== null
    && !/^local[-_]/i.test(String(ctx.args.feature ?? ''));
  const rows = remote
    ? ['  1  归档送审：`/story archive <AR>`',
      '  2  进入 plan：按 framework 的 `phase.next_step` 走',
      '  3  先归档，再进 plan', '',
      '两条互不阻塞，可以并行开始；评审回流改了 spec 之后，'
      + '已经开工的 plan 产物按 framework 的修正流程更新，不是不管。']
    : ['  本地单没有归档：进入 plan，按 framework 的 `phase.next_step` 走。'];
  return ['', '[story-build check] 交付门通过。下一步由你选：', '',
    ...rows, ''].join('\n');
}

/**
 * 交付门 —— 阶段闭环成立了吗，读者审查这一项写成形态了吗。
 *
 * **闭环由框架判，扩展不重判**：报告在不在、终态块回显的 subject 对不对、
 * verdict 与 blocker 数一致不一致、verifier 派没派，都是 `check-receipt` 的判断。
 * 这里只跑它一次，退出码非 0 就把它的话原样带出来。
 *
 * 回执通过之后才轮到形态：读者审查那一项在汇总表里有没有一行、证据空不空、
 * 非 PASS 时两类结论齐不齐。**回执通过而这一项 FAIL 是不该出现的**——它是 BLOCKER 级，
 * FAIL 时 verdict 必为 FAIL、回执必然过不去；真出现了，交付照样拦。
 *
 * 跑不起来不算通过：找不到框架、起不了 ts-node 都如实报出来，让人自己跑一次。
 * 本宿主没登记审查员时读者审查这一项判不了——那不是失败，但**要出声**：
 * 静默通过的话，没经过审查的 story 就这么交出去了，事后没人看得出来。
 *
 * @returns {{problems: string[], notes: string[]}}
 */
function deliveryProblems(ctx) {
  const harness = path.join(ctx.projectRoot, 'framework', 'harness');
  const receipt = path.join(harness, 'scripts', 'check-receipt.ts');
  const manual = 'cd framework/harness && npx ts-node scripts/check-receipt.ts '
    + `--feature ${ctx.args.feature} --phase spec`;
  const fail = (msg) => ({ problems: [msg], notes: [] });
  if (!fs.existsSync(receipt)) {
    return fail('交付门跑不了：找不到 framework/harness/scripts/check-receipt.ts——'
      + '闭环判定归框架，这个仓里没有框架就判不了交付，别把它当通过');
  }
  const runner = receiptRunner(harness);
  if (!runner) {
    return fail('交付门跑不了：framework/harness 里没有 ts-node——'
      + `先在那个目录装依赖，再自己跑一次 \`${manual}\`；跑不了不等于过了`);
  }
  const r = spawnSync(process.execPath,
    [runner, path.join('scripts', 'check-receipt.ts'),
      '--feature', ctx.args.feature, '--phase', 'spec'],
    { cwd: harness, encoding: 'utf-8', timeout: 300000, windowsHide: true });
  if (r.error) {
    return fail(`交付门跑不了：${r.error.message}——自己跑一次 \`${manual}\`，`
      + '过了再来；跑不了不等于过了');
  }
  if (r.status !== 0) {
    const say = `${r.stdout ?? ''}${r.stderr ?? ''}`.trim().split(/\r?\n/)
      .filter(Boolean).slice(-12).join(' / ');
    return fail(`spec 阶段还没闭环，不能交付——check-receipt 说：${say || `退出码 ${r.status}`}`);
  }

  const review = storyReviewProblems(ctx.projectRoot, ctx.args.feature, 'spec');
  return {
    problems: review.problems,
    notes: review.status === 'NOT_APPLICABLE'
      ? [`story 未经读者审查即交付：${review.detail}`]
      : [],
  };
}

// --------------------------------------------------------------------------
// number：给 story 重编号（章 / 小节 / 图题）
// --------------------------------------------------------------------------

/**
 * 编号由机器铺，作者只写业务名标题与图题。
 *
 * 幂等：已经对的文件重跑一个字节都不改，所以放在登记步跑第二遍也无副作用。
 */
function cmdNumber(ctx) {
  const before = readText(ctx.storyPath);
  if (before === null) fail(`没有 AR/story.md 可编号（${ctx.storyPath}）`);
  const after = renumberStory(before, ctx.contract.chapters ?? [],
                              ctx.contract.heading_counters ?? []);
  if (after === before) {
    process.stdout.write('[story-build number] 编号已经是对的，未改动\n');
    return;
  }
  fs.writeFileSync(ctx.storyPath, after, 'utf-8');
  const was = before.split(/\r?\n/);
  const changed = after.split(/\r?\n/).filter((l, i) => l !== was[i]).length;
  process.stdout.write(`[story-build number] 重编号 ${changed} 行（章序按合同，节序按出现顺序，图序按全篇顺序）\n`);
}

// --------------------------------------------------------------------------
// skeleton / chapter：骨架与逐章原子落盘
// --------------------------------------------------------------------------

/**
 * 待写块的 marker —— **明确记号**，不是「看起来像没写完」。
 *
 * 判它不需要读懂任何一句话：在就是没写完，不在就是写过了。中断恢复据它决定还剩哪几章，
 * check 据它拦住「骨架当成品交」。
 */
const PENDING_MARK = '待写';
const PENDING_RE = /<!--\s*待写[:：]\s*([^>]*?)\s*-->/g;

function pendingMark(title) {
  return `<!-- ${PENDING_MARK}：${title} -->`;
}

/** story 里还带着待写 marker 的章名。 */
function pendingChapters(storyText) {
  const out = [];
  for (const m of String(storyText ?? '').matchAll(PENDING_RE)) out.push(m[1]);
  return out;
}

/**
 * 一章在全文里的字节区间 —— 从它的 `## ` 那一行，到下一个 `## ` 之前。
 *
 * 按行找而不是正则整篇匹配：正文里可能有代码块，块里出现 `## ` 时整篇正则会切错，
 * 而切错的后果是替换一章时吃掉了别的章。
 *
 * @returns {{start:number, end:number}|null} 字符下标区间
 */
function chapterSpan(storyText, title) {
  const text = String(storyText ?? '');
  // CRLF 安全：按 `\r?\n` 切，回推下标时把真实分隔符长度还回去——
  // 少还一个字节，替换区间就整体错位一位，吃掉相邻章的第一个字符。
  const lines = text.split(/\r?\n/);
  let start = -1;
  let offset = 0;
  let inFence = false;
  const offsets = [];
  for (const line of lines) {
    offsets.push(offset);
    offset += line.length + (text.startsWith('\r\n', offset + line.length) ? 2 : 1);
  }
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (/^\s*```/.test(line)) inFence = !inFence;
    if (inFence || !line.startsWith('## ')) continue;
    if (start < 0) {
      if (normalizeHeading(line.slice(3).trim()) === normalizeHeading(title)) start = i;
      continue;
    }
    return { start: offsets[start], end: offsets[i] };
  }
  if (start < 0) return null;
  return { start: offsets[start], end: text.length };
}

/**
 * 一章的**草稿**：形态说明 + 已经搭好的槽位表 + 从真源打的底。
 *
 * 作者拿到的不该是一张白纸加一句「这一章要有表」。搭表、抄术语、复制流程图都是
 * 确定性工作，脚本在他动笔前做完；他填的是语义——每一格写什么、每一步为什么。
 *
 * 草稿是**作者区**：他在草稿里改，`chapter --from` 消费草稿原子落盘。
 * 附录的 A–D 不在这里——那四节归机器区，由 `project` 从真源投影，作者改的是真源。
 */
function chapterDraft(ctx, ch, spec) {
  const rows = [`## ${ch.title}`, ''];
  if (ch.form?.note) rows.push(`<!-- 形态：${ch.form.note} -->`, '');
  const seeded = chapterSeed(ctx, ch, spec);   // 打完就归作者
  for (const [at, slot] of Object.entries(ch.form?.slots ?? {})) {
    if (!slotApplies(ctx, slot.when)) continue;
    if (at === '*') rows.push('<!-- 每个小节（节名按业务取）都照下面这样写 -->', '');
    else if (at) rows.push(`### ${at}`, '');
    rows.push(...renderSlot(ctx, slot, at === '' && seeded.length > 0));
  }
  if (seeded.length) rows.push(...seeded, '');
  rows.push('<!-- 写完这一章跑：story-build chapter --feature <名> --chapter '
    + `${ch.title} --from <本文件> -->`);
  return rows;
}

/**
 * 一个槽位渲染成什么 —— 六种形态各一段，搭好给作者填。
 *
 * 搭表、列步骤、摆标签都是确定性工作。让模型自己搭、脚本事后挑错，就是把确定性
 * 工作交给了模型，而它每次搭出来的都不一样，判据再多也只是在追。
 * `seeded` 为真时这一章由真源打了底（术语表、流程图），不再摆空的。
 */
function renderSlot(ctx, slot, seeded) {
  const rows = [];
  for (let i = 1; i <= (slot.prose ?? 0); i += 1) {
    rows.push(`<!-- 第 ${i} 段 -->`, '{{这一段写什么}}', '');
  }
  if (slot.ordered) rows.push('1. {{第一步}}', '2. {{第二步}}', '');
  if (Array.isArray(slot.list)) {
    rows.push(...slot.list.map(x => `- **${x}**：{{一句}}`), '');
  } else if (slot.list) {
    rows.push('- {{一项一句}}', '');
  }
  for (const label of slot.labels ?? []) rows.push(`**${label}**：{{一句}}`, '');
  if (slot.image) {
    rows.push('<!-- 材料里的界面图：引用串见任务包第 4 节，引完接一句说清它画的是什么 -->', '');
  }
  if (slot.table && !seeded && slotApplies(ctx, slot.table_when)) {
    const cells = String(slot.table).split('|');
    rows.push('<!-- 表头如下，第一列是锚；其余列按本需求增减，行数按内容定 -->',
      ...renderTable(cells, [cells.map(c => `{{${c || '　'}}}`)]), '');
  }
  return rows;
}

/**
 * 这一章从真源打的底 —— **打完就归作者**。
 *
 * 术语的措辞、流程图的节点文字、材料贡献那一句，都是他要改的东西；
 * 脚本种一次，此后不再碰。附录 A–D 不在这里：那四节每次都能从真源算出同样的东西，
 * 归机器区。
 */
function chapterSeed(ctx, ch, spec) {
  if (ch.id === '02-terms') {
    const terms = specTerms(spec);
    return terms.length ? renderTable(['术语', '在本需求里的意思'], terms) : [];
  }
  if (ch.appendix) {
    const out = [];
    for (const name of ch.subsections ?? []) {
      out.push(`### ${name}`, '', '{{一句这一节给评审者看什么}}', '');
      // 材料清单是作者种子：类别与链接由清单给，「贡献了什么」只有他知道。
      // 其余四节由 `project` 投影，草稿里不放——放了他就要在两处维护同一张表。
      if (normalizeHeading(name) === normalizeHeading(materialSubsectionName(ctx.contract) ?? '')) {
        out.push(...materialListSkeleton(ctx), '');
      }
    }
    return out;
  }
  return [];
}

/**
 * 附录某一节的投影：这一节从哪个真源来、投出来是哪几行。
 *
 * **不含任何占位**：机器区里出现「作者要填的格子」，作者填了会被下一次投影打回，
 * 不填就一直挂着。要作者写的东西全在草稿的作者区。
 * 材料清单不在这里——那一节的「贡献了什么」只有作者知道，它归作者。
 * 多张表之间空一行：连着写 markdown 会把它们并成一张错表。
 */
function appendixProjection(ctx, spec, name) {
  const want = normalizeHeading(name);
  if (want === normalizeHeading('改动边界')) {
    const rows = scopeBoundaryRows(spec);
    const out = rows.length ? renderTable(['', '范围'], rows.map(r => r.slice(0, 2))) : [];
    const tables = appendixTables(spec, name);
    for (const t of tables) out.push('', ...renderTable(t.header, t.rows));
    // §9.5 写「不涉及：…」时把那一句投过来：依赖没有变更也是结论，
    // 丢了它，story 相对 spec 就减了一条。
    if (!tables.length) {
      const na = specNotApplicable(spec, name);
      if (na) out.push('', na);
    }
    return ['Scope 模块清单与 spec §9.5', out];
  }
  if (want.includes(normalizeHeading('规约判定'))) {
    return ['spec/knowledge-use.yaml', verdictSkeleton(ctx)];
  }
  const tables = appendixTables(spec, name);
  const rows = tables.flatMap((t, i) => i ? ['', ...renderTable(t.header, t.rows)]
    : renderTable(t.header, t.rows));
  if (!rows.length) {
    const na = specNotApplicable(spec, name);
    return ['spec §9', na ? [na] : []];
  }
  return ['spec §9', rows];
}

/**
 * 把附录的机器区投影进 story —— **投影的唯一入口**，两个时点都走它。
 *
 * ① `chapter` 落盘附录章之后：作者的草稿里只有目的句与材料清单，A–D 由这里投出来，
 *    他登记前跑 `check` 才不会因为那四节是空的而红；
 * ② `story_flow.py story` 登记时：真源在成文期间还会变（补一条规约判定、改一个接口），
 *    以登记这一次为准。
 *
 * 每次都从当前真源重算，不读旧 story：读旧的就成了「真源 + 一份会漂移的副本」。
 */
/**
 * spec 那一节写的「不涉及：<依据>」——它也是结论，评审者要看到。
 *
 * 读不出这样一行就返回 null：那时那一节是真的空，旧机器区该删掉，
 * 由 `check ⑫` 报空节，而不是让上一版的内容留在归档件里冒充现状。
 */
function specNotApplicable(spec, name) {
  const from = APPENDIX_FROM_SPEC.find(x => normalizeHeading(x[0]) === normalizeHeading(name));
  if (!spec || !from) return null;
  for (const re of from[1]) {
    const hit = specSection(spec, re).split(/\r?\n/)
      .map(l => l.trim()).find(l => /^不涉及[:：]\s*\S/.test(l));
    if (hit) return hit;
  }
  return null;
}

function projectAppendix(ctx, storyText) {
  const appendix = appendixChapter(ctx.contract);
  if (!appendix) return { text: storyText, zones: 0 };
  const span = chapterSpan(storyText, appendix.title);
  if (!span) return { text: storyText, zones: 0 };
  const spec = specText(ctx);
  const materialName = normalizeHeading(materialSubsectionName(ctx.contract) ?? '');
  let lines = storyText.slice(span.start, span.end).split(/\r?\n/);
  let zones = 0;
  // 集合对账：合同里有的按真源重投，合同里没有的区块删掉——某一节从合同去掉或改名之后，
  // 旧区会一直挂着，而它指的真源已经没人维护了。
  const want = new Set((appendix.subsections ?? []).map(normalizeHeading));
  for (const line of [...lines]) {
    if (!line.startsWith(ZONE_BEGIN)) continue;
    const name = line.slice(ZONE_BEGIN.length).split(' · ')[0].trim();
    const at = want.has(normalizeHeading(name)) ? null : zoneSpan(lines, name);
    if (at) lines = [...lines.slice(0, at.start), ...lines.slice(at.end)];
  }
  for (const name of appendix.subsections ?? []) {
    if (normalizeHeading(name) === materialName) continue;    // 材料清单归作者
    const [source, rows] = appendixProjection(ctx, spec, name);
    const at0 = zoneSpan(lines, name);
    // 真源那一节现在什么都没有了（规约全退出激活清单、spec 那一节被删或改空）：
    // 旧区要删，不能留着上一版冒充现状。删完那一节由 `check ⑫` 报空节——
    // 那是正确的告警，它指向真源，不指向作者。
    if (!rows.length) {
      if (at0) lines = [...lines.slice(0, at0.start), ...lines.slice(at0.end)];
      continue;
    }
    const block = zoneBlock(name, source, rows);
    zones += 1;
    if (at0) { lines = [...lines.slice(0, at0.start), ...block, ...lines.slice(at0.end)]; continue; }
    // 作者那一节还没有机器区：插到该节末尾。节都没有就说明附录章还没落盘，跳过。
    const want = normalizeHeading(name);
    const head = lines.findIndex(l => /^###\s+/.test(l.trim())
      && normalizeHeading(l.trim().slice(3)).includes(want));
    if (head < 0) { zones -= 1; continue; }
    let end = lines.findIndex((l, i) => i > head && /^###\s+/.test(l.trim()));
    if (end < 0) end = lines.length;
    lines = [...lines.slice(0, end), ...block, '', ...lines.slice(end)];
  }
  return { text: storyText.slice(0, span.start) + lines.join('\n') + storyText.slice(span.end),
    zones };
}

function cmdProject(ctx) {
  refuseIfFrozen(ctx, 'project');
  const story = readText(ctx.storyPath);
  if (story === null) fail('AR/story.md 不在：先跑 skeleton 建骨架');
  const { text, zones } = projectAppendix(ctx, story);
  if (text !== story) fs.writeFileSync(ctx.storyPath, text, 'utf-8');
  process.stdout.write(`[story-build project] 附录机器区按当前真源重投 ${zones} 节`
    + '（spec §9 / knowledge-use.yaml）；材料清单归你，不动\n');
}

/**
 * 附录·规约判定的整张表 —— **依据也取真源**。
 *
 * 判断已经写在 `spec/knowledge-use.yaml` 里：不命中写的是为什么不适用，
 * 命中写的是这一轮要满足的要求。让作者对着那份 YAML 再抄一遍依据，
 * 抄出来的只会更短。他要改的是措辞，改在这里，改完由 ⑫b 核集合。
 */
function verdictSkeleton(ctx) {
  const entries = activeKnowledgeEntries(ctx);
  if (!entries.length) return [];
  const use = knowledgeUseVerdicts(ctx);
  // 判断骨架还没生成（离线、或 knowledge-use.yaml 不在）：投不出来就不投，
  // 那一节保持原样，缺表由 check ⑦ 报。这一步不代替它下结论。
  // 文件在却读不出判断，那是它写坏了——停下把话说清，别静默跳过。
  if (!use) {
    if (ctx.offline || !fs.existsSync(path.join(ctx.featureRoot, 'spec', 'knowledge-use.yaml'))) return [];
    fail('spec/knowledge-use.yaml 读不出判断：附录的判定表是它的投影，先把那份 YAML 修好');
  }
  // 机器区里不写占位：作者改不了它（下一次投影会盖回来），挂着又永远不会被填。
  // 骨架在而某一条没依据，就在这里停下把话说清——判断本来就该先写进那份 YAML，
  // 它自己的门禁也要求每条有 requirement 或 reason。
  const covered = (e) => use.naDomains.has(e.prefix);
  const missing = entries.filter(e => !covered(e) && !use.rows.get(e.id)?.basis);
  if (missing.length) {
    fail(`spec/knowledge-use.yaml 里这 ${missing.length} 条还没有判断依据：`
      + `${missing.slice(0, 4).map(e => e.id).join('、')}${missing.length > 4 ? '…' : ''}`
      + '——命中写 requirement、不命中写 reason，整域不适用写进 constraint_domains，'
      + '填完再投影。附录的判定表是它的投影，投影不替你编依据');
  }
  // 整域不适用的域投一行域级结论；域内条目不再逐条出现——那正是那份 YAML 的写法，
  // `check ⑦` 也认这一行覆盖全域。
  const seenDomain = new Set();
  const rows = [];
  for (const e of entries) {
    if (covered(e)) {
      if (seenDomain.has(e.prefix)) continue;
      seenDomain.add(e.prefix);
      rows.push([e.domainTitle ?? '', e.prefix, DOMAIN_NA, use.naDomains.get(e.prefix)]);
      continue;
    }
    const row = use.rows.get(e.id);
    rows.push([e.domainTitle ?? '', e.id, row.applicable ? '命中' : '不命中', row.basis]);
  }
  return renderTable(['规约域', '编号', '判定', '依据'], rows);
}

/** 附录·材料清单的每一行：类别、文件名与链接由清单给，贡献由作者写。 */
function materialListSkeleton(ctx) {
  const targets = materialListTargets(ctx);
  if (!targets || targets === 'broken') return [];
  // 类别取合同的 `sources[*].label`，按路径反查——它在那里已经有答案。
  // 收件箱原件不在合同的来源表里（它是人另外给的），落到「原件」。
  const kinds = new Map(Object.values(ctx.contract?.sources ?? {})
    .filter(x => x?.path && x?.label).map(x => [x.path, x.label]));
  return targets.must.map(([rel]) =>
    `- ${kinds.get(rel) ?? (rel.startsWith('inbox/') ? '原件' : '材料')}：`
    + `[${basename(rel)}](${relFromStory(rel)})——{{这份材料贡献了什么}}`);
}

//: 章草稿目录。作者在这里写，`chapter --from` 从这里读；登记成功后由
//: `story_flow.py story` 删掉——story 冻结了，草稿就失去用途，也不进冻结台账。
const DRAFTS = 'drafts';

function draftPath(ctx, index, title) {
  return path.join(ctx.srcDir, DRAFTS,
    `${String(index + 1).padStart(2, '0')}-${title}.md`);
}

/**
 * 缺哪章补哪章，**已存在的绝不覆盖** —— 草稿里可能有作者还没落盘的内容。
 *
 * 两种补法，按这一章写没写分：
 *
 * - **还带着待写标记**：补一份起点草稿（形态说明、槽位表头、术语行、spec 的图都在里面）；
 * - **已经写完**：补一份**现稿正文**。它不是起点——用起点会把成品换掉，而下一次落盘
 *   就把成品覆盖了。用现稿则是恒等：不落盘什么也不变，落盘也只是把原文写回去。
 *
 * 为什么已写的章也要补：成文登记会删掉整个草稿目录（story 冻结了，草稿没有用途）。
 * 之后审查报了阻断问题，`reopen` 撤销登记，作者要改的正是某一章——那时他手上
 * 没有可改的东西。补回来，返修就有落点。
 *
 * @returns {string[]} 这次新建的草稿文件名
 */
function writeDrafts(ctx, spec, storyText) {
  const made = [];
  const pending = storyText && new Set(pendingChapters(storyText).map(normalizeHeading));
  const written = storyText
    ? new Map(storySections(storyText).map(s2 => [normalizeHeading(s2.title), s2.text]))
    : new Map();
  fs.mkdirSync(path.join(ctx.srcDir, DRAFTS), { recursive: true });
  ctx.contract.chapters.forEach((ch, i) => {
    const file = draftPath(ctx, i, ch.title);
    if (fs.existsSync(file)) return;
    const key = normalizeHeading(ch.title);
    const done = pending && !pending.has(key);
    const body = done ? written.get(key) : null;
    if (done && body === undefined) return;         // 章缺失由 check ① 报，这里不猜
    const text = done ? body : chapterDraft(ctx, ch, spec).join('\n');
    fs.writeFileSync(file, `${text.trimEnd()}\n`, 'utf-8');
    made.push(path.basename(file));
  });
  return made;
}

function cmdSkeleton(ctx) {
  refuseIfFrozen(ctx, 'skeleton');
  const spec = specText(ctx);
  const existing = readText(ctx.storyPath);
  if (existing !== null) {
    // story 已经在了也要补草稿：中断恢复时缺的往往正是还没写的那几章。
    const made = writeDrafts(ctx, spec, existing);
    const left = pendingChapters(existing);
    process.stdout.write(`[story-build skeleton] AR/story.md 已存在，未改动`
      + `（还有 ${left.length} 章待写${left.length ? '：' + left.join('、') : ''}）；`
      + `${made.length ? `补建草稿 ${made.length} 份（已写完的章按现稿补回，可直接改）`
        : '草稿齐备，一份未覆盖'}\n`);
    return;
  }
  const titles = ctx.contract.chapters.map(c => c.title);
  const body = [`# ${path.basename(ctx.featureRoot)}`, ''];
  for (const ch of ctx.contract.chapters) {
    body.push(`## ${ch.title}`, '', pendingMark(ch.title), '');
  }
  fs.mkdirSync(path.dirname(ctx.storyPath), { recursive: true });
  fs.writeFileSync(ctx.storyPath, `${body.join('\n').trimEnd()}\n`, 'utf-8');
  const made = writeDrafts(ctx, spec, null);
  process.stdout.write(`[story-build skeleton] ${titles.length} 章骨架 + `
    + `${made.length} 份章草稿（\`AR/story-src/${DRAFTS}/\`）：`
    + `形态说明、槽位表头${spec ? '、术语起始行、spec §5 的图' : ''}都在草稿里，`
    + `你在草稿上写，写完一章跑 chapter --from 落盘。`
    + `附录的接口/数据/边界/判定四节由 project 从真源投影，不用你写\n`);
}

/**
 * 把一章的内容原子替换进 story.md —— **落盘只有这一条路**。
 *
 * 作者拿编辑工具直接改整篇时，「已完成的章一个字节没动」只是期望；经这条命令落盘，
 * 它是机械事实：替换的区间就是那一章，别处一个字节都碰不到。统稿也走它——
 * 统稿要改第五章就替换第五章，不重新输出整篇。整篇重出是全有或全无，
 * 中途断了磁盘上什么都没有。
 */
/**
 * 章文件开头的标题行剥掉——命令自己会加 `## <章名>`。
 *
 * 作者写章文件时很自然会带上本章标题；命令再包一层，story 里就出现两行一样的标题。
 * 看见重复，作者多半会删掉 story.md 重建骨架、十章重灌——十次落盘白做。
 *
 * 只剥两种：**H1**（它只属于骨架，章文件里出现就是错位）与**与本章同名的 H2**。
 * 章内的小节标题（`### 3.1 …`）是正文，一个字不动。
 */
/**
 * 剥掉写给作者的指引 —— 草稿里的形态说明、读者问题、命令提示与待写标记。
 *
 * 它们是脚手架：作者照着写，写完就该留在草稿里。原样落盘的话，形态说明里的
 * 「spec §0」会被语言红线判成工程坐标，待写标记会让已经写完的章仍被数成待写。
 * **归档件里不该有 HTML 注释**——机器区的首尾标记除外，那两行是投影的定位点。
 */
function stripGuidance(body) {
  const keep = (l) => l.startsWith(ZONE_BEGIN) || l === ZONE_END
    || !(l.startsWith('<!--') && l.endsWith('-->'));
  return String(body ?? '').split(/\r?\n/).filter(l => keep(l.trim()))
    .join('\n').replace(/\n{3,}/g, '\n\n');
}

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
 * 读者审查的任务书 —— 注入给 verifier 的就是这一份，这里只是让人也看得见。
 *
 * 任务定义是这一项成不成的关键：任务里没有的问题，审查者不会去问。
 * 所以任务书该是可读、可评审的东西，不该只存在于某一次 prompt 里。
 */
function cmdReviewTask(ctx) {
  process.stdout.write(
    readerReviewTask(ctx.projectRoot, ctx.args.feature, 'story_reader_review') + '\n');
}

function cmdChapter(ctx) {
  refuseIfFrozen(ctx, 'chapter');
  const title = String(ctx.args.chapter ?? '').trim();
  if (!title) fail('缺 --chapter <章名>：要替换哪一章');
  const from = ctx.args.from;
  if (!from) fail('缺 --from <文件>：这一章的内容写在文件里，不走命令行参数——'
    + '正文里有换行、引号与 markdown，任何 shell 都会再解析一遍');
  const body = readText(path.resolve(from));
  if (body === null) fail(`读不到 ${from}`);
  if (!body.trim()) fail(`${from} 是空的：空正文不是一章，本需求真的不涉及时写「${EMPTY_SECTION_TEXT}」`);

  const story = readText(ctx.storyPath);
  if (story === null) fail('AR/story.md 不在：先跑 skeleton 建骨架，再一章一章落盘');
  const known = ctx.contract.chapters.map(c => c.title);
  if (!known.some(t => normalizeHeading(t) === normalizeHeading(title))) {
    fail(`合同里没有「${title}」这一章。章名取自章节合同：${known.join('、')}`);
  }
  const span = chapterSpan(story, title);
  if (!span) fail(`story 里找不到「${title}」的章锚——骨架被改过或章名写错了。`
    + '章锚是逐章落盘的定位点，别手工改动它');

  const trimmed = stripGuidance(stripOwnHeading(body, title)).replace(/\s+$/, '');
  if (!trimmed) fail(`${from} 除了章标题没有别的内容：这一章的正文写在标题之后`);
  const replaced = `## ${title}\n\n${trimmed}\n\n`;
  let next = story.slice(0, span.start) + replaced + story.slice(span.end);
  // 落盘附录章 = 作者区 + 当前真源投影出的机器区，一次写完。
  // 作者的附录草稿里只有目的句与材料清单，A–D 在这里投出来——不投的话他登记前
  // 跑 check 会因为那四节是空的而红，而那四节本来就不该由他写。
  if (normalizeHeading(title) === normalizeHeading(appendixChapter(ctx.contract)?.title ?? '')) {
    next = projectAppendix(ctx, next).text;
  }
  fs.writeFileSync(ctx.storyPath, next, 'utf-8');

  const left = pendingChapters(next);
  process.stdout.write(`[story-build chapter] 「${title}」已落盘`
    + `（其余 ${known.length - 1} 章一个字节未动）；`
    + (left.length ? `还剩 ${left.length} 章待写：${left.join('、')}\n`
                   : '十章都写完了，接着做统稿\n'));
}

// --------------------------------------------------------------------------
// build：渲染 review.md（机器区重算、人工区逐字节保留）
// --------------------------------------------------------------------------

/**
 * review 只能在 story 成文之后渲染 —— 顺序本身就是一条判据。
 *
 * review 是**判断的台账**，而判断在成文过程中还会长出来：写到某一章才发现材料两处打架、
 * 才发现某个取舍得由人拍板。先渲染 review 等于把台账定在「只读过 spec」那个时点上，
 * 之后新登记的议题要么被忘掉，要么得靠人记得回来重跑一次。
 *
 * 「story 还没写完，review 先出来了」不是模型跑偏，是作业顺序把它排在了前面。
 *
 * 判据取「story 里有没有章」而不是「文件在不在」：`init` 会先落一份空骨架，
 * 文件存在证明不了成文发生过。
 */
function requireStoryFirst(ctx) {
  const text = readText(ctx.storyPath);
  if (text && /^##\s+\S/m.test(text)) return;
  fail('story 还没成文，review 不能先渲染。\n'
    + '  review 是判断的台账，而判断在成文过程中还会长出来——写到某一章才发现材料打架、\n'
    + '  才发现某个取舍要人拍板。台账定在「只读过 spec」那个时点上，后面新登记的议题就进不来了。\n'
    + '  顺序：先按合同逐章写完 AR/story.md，把新发现的判断登记进 decisions.json，再跑 build。');
}

function cmdBuild(ctx) {
  const decisions = readJson(ctx.decisionsPath, null);
  if (!decisions) fail(`缺 ${ctx.decisionsPath}——先跑 init 建骨架`);
  requireStoryFirst(ctx);
  const list = Array.isArray(decisions.decisions) ? decisions.decisions : [];
  const old = readText(ctx.reviewPath) ?? '';

  // 分层与编号都在渲染器里按登记顺序算，不进登记表：登记表里存序号，
  // 插一条就要手工重排后面全部；类别成章的名字来自合同词表，机制不认识任何一类。
  const out = renderReview(list, old, ctx.contract.decision_categories ?? []);

  fs.mkdirSync(path.dirname(ctx.reviewPath), { recursive: true });
  fs.writeFileSync(ctx.reviewPath, out, 'utf-8');
  process.stdout.write(`[story-build build] 已渲染 ${list.length} 个议题；人工填写内容逐字节保留
`);
}

// --------------------------------------------------------------------------

function main() {
  const args = parseArgs(process.argv);
  if (!COMMANDS.includes(args.command)) {
    fail(`用法: story-build.mjs <${COMMANDS.join('|')}> --feature <需求名> [--project-root <路径>]
`
      + '      story-build.mjs check --offline --story <story.md 路径>');
  }
  if (args.offline && args.command !== 'check') {
    fail('--offline 只用于 check：它只读一份文档，登记与渲染都需要需求目录');
  }
  if (args.deliver && args.command !== 'check') {
    fail('--deliver 只用于 check：它判的是这份 story 能不能交付');
  }
  if (args.deliver && args.offline) {
    fail('--deliver 与 --offline 互斥：交付门要读需求目录里的闭环产物');
  }
  const ctx = createContext(args);
  if (args.command === 'init') cmdInit(ctx);
  else if (args.command === 'skeleton') cmdSkeleton(ctx);
  else if (args.command === 'chapter') cmdChapter(ctx);
  else if (args.command === 'project') cmdProject(ctx);
  else if (args.command === 'review-task') cmdReviewTask(ctx);
  else if (args.command === 'check') cmdCheck(ctx);
  else if (args.command === 'number') cmdNumber(ctx);
  else cmdBuild(ctx);
}

// 直接跑才执行命令；被 import 时只导出判定函数（正面校准要拿句边界判把一份文档
// 逐句灌一遍，那件事不该经由一个需要完整需求目录的命令行去做）。
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}


