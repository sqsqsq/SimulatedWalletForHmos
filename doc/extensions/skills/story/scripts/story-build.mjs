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
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { normalizeHeading, renumberStory } from './headings.mjs';
import { readUse, UseError } from '../../../hooks/shared/knowledge-use.mjs';
import {
  baseLayerIds, formatHits, proseBlocks, scanBannedTerms, scanBrokenImages, scanDanglingRefs,
  scanLanguageRedline, scanLocalPaths, scanMaterialList,
} from './lint-rules.mjs';
import { activeKnowledge } from '../../../hooks/shared/knowledge.mjs';
import {
  FREEFORM_CLOSE, FREEFORM_OPEN, HUMAN_ZONE_MARK, renderReview,
} from './review-render.mjs';

const COMMANDS = ['init', 'check', 'build', 'number', 'skeleton', 'chapter'];

/** 统稿留痕的行数：作业书的自查清单有几项，这里就是几行。 */
const COPYEDIT_ROWS = 6;

/** 规约判定表的取值封闭；整域不适用时该域内条目不必逐条列。 */
const DOMAIN_NA = '整域不适用';
const KNOWLEDGE_VERDICTS = ['命中', '不命中', DOMAIN_NA];

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
 * 实跑里台账错到 1000+ 之后被整份删除，删完 check 的报错数确实下去了。
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
    const out = new Map();
    for (const row of use.constraints) {
      const id = String(row?.id ?? '').trim();
      if (id) out.set(id, row.applicable === true);
    }
    return out;
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
    // 兄弟文件在而这一份不在：导入做了一半
    let siblings = 0;
    const dir = obj.warn_if_siblings
      ? path.join(ctx.featureRoot, obj.warn_if_siblings) : null;
    if (dir) {
      try { siblings = fs.readdirSync(dir).length; } catch { siblings = 0; }
    }
    // 缺来源一律不拦（一律记一笔）。图片的登记在 materials.json，不在这些索引文件里。
    missing.push({
      doc, rel,
      required: obj.required === true,
      siblings,
      siblingDir: obj.warn_if_siblings ?? null,
    });
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

/** 缺失来源报成一句话。都是「记一笔」，措辞按有没有兄弟文件、是不是必备分三种。 */
function missingSourceLine(m) {
  if (m.siblings > 0) {
    return `合同声明的来源 ${m.doc} 不存在：${m.rel}`
      + `——但 ${m.siblingDir}/ 里有 ${m.siblings} 个文件。`
      + '图片的登记在材料清单（AR/story-src/materials.json），不在这份索引里，'
      + '所以判据不受影响；要不要给这个目录写一份说明文件，由你定';
  }
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
 * 早先这份登记是从材料正文的 `![](…)` 语法枚举出来的，于是「有没有被登记」取决于
 * 有没有人给它写过一条 markdown 链接：界面参考目录里只写了名字的那几张图因此不算数，
 * 目录里四张、登记里两张，作者只能把差额标成「不进 story」。
 *
 * 清单枚举的是磁盘上真实存在的图片文件，与谁给它写没写链接无关；同一张图复制到第二个
 * 落点时它按内容合并成一条，`paths` 列出全部落点——**图片的身份是它的内容，不是路径**。
 *
 * @returns {{kind:string,sha256:string,paths:string[]}[] | null | 'broken'}
 *   null = 没有清单（offline 或还没跑过 round）；'broken' = 清单坏了，两者不能混为一谈
 */
function materialImages(ctx) {
  if (ctx.offline || !ctx.srcDir) return null;
  const text = readText(path.join(ctx.srcDir, 'materials.json'));
  if (text === null) return null;
  let data;
  try { data = JSON.parse(text.replace(/^\ufeff/, '')); } catch { return 'broken'; }
  const list = data?.materials;
  if (!Array.isArray(list)) return 'broken';
  return list.filter(m => m?.kind === 'image' && Array.isArray(m.paths) && m.paths.length);
}

/**
 * 材料清单那一节**应当**列到的材料 —— 同样出自 `materials.json`。
 *
 * 这一节回答的是「据哪几份材料写成」。谁来定这个集合，决定了它是账还是倾倒区：
 * 由作者自由罗列时，容易把本轮自己生成的规格链进去、把图片文件单列成行，
 * 也出现过漏掉一整份的形态——读者据这一节把材料找出来，漏一份等于那份材料没人知道。
 *
 * 集合按两条定：
 *
 * - **必列**：流程正在消费的那几份正文（清单里 `kind: doc` 且真的在盘上的）；
 * - **可列**：收件箱里的原件。它们的内容已经并入正文，读者顺正文也能看到；
 *   但「这份材料是人另外给的、没走需求系统」本身是信息，作者愿意指出来就允许。
 *
 * 图片不在其中：图随它所在的那份材料走，不单列成行（单列会把清单变成文件列表）。
 * 中间产物也不在其中——本轮自己生成的规格与记录不是材料，它们压根不进清单。
 *
 * @returns {{must: string[], mayAlso: string[]} | null | 'broken'}
 */
function materialListTargets(ctx) {
  if (ctx.offline || !ctx.srcDir) return null;
  const text = readText(path.join(ctx.srcDir, 'materials.json'));
  if (text === null) return null;
  let data;
  try { data = JSON.parse(text.replace(/^\ufeff/, '')); } catch { return 'broken'; }
  if (!Array.isArray(data?.materials)) return 'broken';
  const must = data.materials
    .filter(m => m?.kind === 'doc' && m.sha256 && Array.isArray(m.paths))
    .flatMap(m => m.paths);
  const mayAlso = (Array.isArray(data.sources) ? data.sources : [])
    .map(x => `inbox/${x?.file}`);
  return { must, mayAlso };
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
      for (const [field, what] of [
        ['title', '陈述句标题（已定的陈述结论，待定的陈述事项）'],
        ['clarification', '带小标题分段的澄清正文'],
        ['decider', '请谁确认'],
      ]) {
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
  // 逐条判定原先落在一份独立的判定记录文件里，那份文件退场后既无作业指引也无门禁——
  // 规约的「知识应用」在 story 侧就这么丢过一次。判定回到 story 里，评审者才拿得到完备性回显。
  //
  // 落点在**附录**而不是主叙事的某一章：规约编号是工程标识，读者对不上，
  // 写进主叙事就是在打断阅读；附录给了它一个不打断阅读、机器又核得到的位置。
  // 激活规约的编号**直接取激活清单**：经「材料单元」那一层只是把同一份数据换个形状，
  // 而多一层就多一处会与清单失同步的地方——判定表少判一条规约是静默的。
  //
  // 命中与否的**结论**另有真源：`spec/knowledge-use.yaml`。这张表是给评审者的
  // 完备性回显，写法与粒度都不同，所以不从那份 YAML 生成；但两处说的必须是同一件事，
  // 对不上就是两处判定打架，评审者无从知道哪个是准的。
  const kEntries = activeKnowledgeEntries(ctx);
  const useVerdicts = knowledgeUseVerdicts(ctx);
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
        if (!KNOWLEDGE_VERDICTS.includes(row.verdict)) {
          problems.push(`规约 ${id} 的判定「${row.verdict}」不是 ${KNOWLEDGE_VERDICTS.join(' / ')} 之一`);
        } else if (!row.basis) {
          problems.push(`规约 ${id} 的判定没写依据——「不涉及」三个字不是依据`);
        } else if (useVerdicts && useVerdicts.has(id)) {
          const want = useVerdicts.get(id) ? '命中' : '不命中';
          if (row.verdict !== DOMAIN_NA && row.verdict !== want) {
            problems.push(`规约 ${id} 在这张表里判「${row.verdict}」，`
              + `而 spec/knowledge-use.yaml 判的是「${want}」`
              + '——同一条结论有了两种说法。判断的真源是那份 YAML，改这张表跟上它');
          }
        }
      }
    }
  }

  mark('④ 图片身份');
  // ④ 图片身份：story 引了哪些图、每一张是不是材料清单里登记过的那一张。
  //
  // 它原先挂在「形态守恒」底下，而那条判的是「分了几张就要画几张」——按材料条数增长的
  // 证明表，已随逐单元系统退场。图片这两条不是那一类：它们是确定性的链接与图片检查，
  // 判据的对象是「引用可不可解析、在不在登记里」，与作者画了几张无关。
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

    // 附录里不放图。三轮复发同一种形态：正文各章写着「下图是…」，图却整批迁进附录，
    // 读者读到那句话时手边没有图，要翻到最后再翻回来。
    //
    // 这一条与「每张登记的图都必须被引用」是**合围**：图进不了附录，又不能不出现，
    // 于是只剩一个去处——它讲的那一章。
    const inAppendix = [...appendixSection.text.matchAll(/!\[[^\]]*\]\(([^)\s]+)/g)]
      .map(m => m[1]);
    if (inAppendix.length) {
      problems.push(`「${appendixDef.title}」里有 ${inAppendix.length} 张图`
        + `（${inAppendix.slice(0, 3).join('、')}${inAppendix.length > 3 ? '…' : ''}）`
        + '——图片放它讲的那一章，跟着讲它的那句话走；'
        + `${appendixDef.title}是查阅件，读者不会为了看一张图翻到这里来`);
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
  // 图的承接与图题**不在这里判**：「这句话指的是不是这张图」要读上下文，
  // 那是独立审查按效果判的事。这里只留材料清单的行形态——它是材料清单集合判据的搭档，
  // 判的是「这一行有没有链接、链到的地方在不在清单里」，是确定性的。
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
        const allowed = new Set([...want.must, ...want.mayAlso]);
        for (const rel of want.must) {
          if (!listed.has(rel)) {
            problems.push(`「${appendix.title}·${name}」少了一份材料：${rel}`
              + '——它在这一轮的材料里，读者据这一节把材料找出来，漏一份等于那份材料没人知道');
          }
        }
        for (const rel of listed) {
          if (allowed.has(rel)) continue;
          problems.push(`「${appendix.title}·${name}」列了不是材料的东西：${rel}`
            + '——这一节回答「据哪几份材料写成」，本轮自己生成的规格与记录、单张图片文件都不是材料。'
            + '图随它所在的那份材料走，不单列成行');
        }
      }
    }
  }
  // 小节编号不在这里判：它由 `number` 命令统一铺（D1）。机器保证的形态再设一条
  // 判据，判的是自己的输出——真正会漏的是机器不做的那部分。

  mark('⑫d 统稿留痕');
  // ⑫d 统稿留痕：`copyedit.md` 恰好六行，一项自查一行
  //
  // 统稿（通读全篇、收重复收承接收样式）是唯一一步没有任何产物的动作，于是跳过它
  // 零成本——「同一件事讲三遍」「图题一章一个样」这类只有通读才看得见
  // 的毛病，而门禁全绿。留痕不是为了核内容（写没写到位由语义审查与抽样人核），
  // 是为了让「没做」这件事留下痕迹。
  //
  // **只写六行，写多不奖励**：把它写成检查报告，下一轮就有人为了显得认真而灌水。
  if (!ctx.offline) {
    const copyedit = readText(ctx.copyeditPath);
    if (copyedit === null) {
      problems.push(`缺 ${path.basename(ctx.copyeditPath)}`
        + '——统稿完成后在这里写六行，六项自查各一行「查了什么／改了几处或无」');
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

function cmdSkeleton(ctx) {
  refuseIfFrozen(ctx, 'skeleton');
  const existing = readText(ctx.storyPath);
  if (existing !== null) {
    const left = pendingChapters(existing);
    process.stdout.write(`[story-build skeleton] AR/story.md 已存在，未改动`
      + `（还有 ${left.length} 章待写${left.length ? '：' + left.join('、') : ''}）\n`);
    return;
  }
  const titles = ctx.contract.chapters.map(c => c.title);
  const body = [`# ${path.basename(ctx.featureRoot)}`, ''];
  for (const title of titles) {
    body.push(`## ${title}`, '', pendingMark(title), '');
  }
  fs.mkdirSync(path.dirname(ctx.storyPath), { recursive: true });
  fs.writeFileSync(ctx.storyPath, `${body.join('\n').trimEnd()}\n`, 'utf-8');
  process.stdout.write(`[story-build skeleton] 建了 ${titles.length} 章骨架：`
    + `每章一个章锚 + 一个待写 marker。写完一章跑一次 chapter 落盘\n`);
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
 * 两跑的作者看见重复都选了同一条路：删掉 story.md、重建骨架、十章重灌。
 *
 * 只剥两种：**H1**（它只属于骨架，章文件里出现就是错位）与**与本章同名的 H2**。
 * 章内的小节标题（`### 3.1 …`）是正文，一个字不动。
 */
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

  const trimmed = stripOwnHeading(body, title).replace(/\s+$/, '');
  if (!trimmed) fail(`${from} 除了章标题没有别的内容：这一章的正文写在标题之后`);
  const replaced = `## ${title}\n\n${trimmed}\n\n`;
  const next = story.slice(0, span.start) + replaced + story.slice(span.end);
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
  const ctx = createContext(args);
  if (args.command === 'init') cmdInit(ctx);
  else if (args.command === 'skeleton') cmdSkeleton(ctx);
  else if (args.command === 'chapter') cmdChapter(ctx);
  else if (args.command === 'check') cmdCheck(ctx);
  else if (args.command === 'number') cmdNumber(ctx);
  else cmdBuild(ctx);
}

// 直接跑才执行命令；被 import 时只导出判定函数（正面校准要拿句边界判把一份文档
// 逐句灌一遍，那件事不该经由一个需要完整需求目录的命令行去做）。
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}


