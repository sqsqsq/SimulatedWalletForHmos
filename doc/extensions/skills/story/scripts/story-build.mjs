/**
 * story 的登记、核对与校验 —— 四个命令，围绕**一份文档写成**这件事。
 *
 * ## 与 1.0 逐章生产线的区别
 *
 * 1.0 的做法是先生成逐章任务书（每章一份取材路标 + 逐章必答），各章分别写完再装配，守恒判「每章把取材节的每行表格/数值/反引号写全」。后果是**同一个事实
 * 被四个章节合同各指一次，于是被强制写四遍**。
 *
 * 这里没有逐章任务书、没有逐章文件、没有装配。成文分三步：**先分配、后逐章渲染、最后统稿**——
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
 * | `check` | 章标题与顺序、整篇 token 守恒、章节与附录形态、图与 diagram 落点、决策字段齐 |
 * | `build` | 由 `decisions.json` 渲染 `review.md`（机器区重算、人工区逐字节保留） |
 * | `number`| 给 `story.md` 重编号：章序按合同、小节序按出现顺序、图题按全篇顺序 |
 *
 * `audit.json` 只认三态，**没有自由文本理由**——只判非空的自由文本理由字段，
 * 大半单元会填同一句套话，等于给漏写开了一个合法出口。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { decisionUnits, enumerateUnits, knowledgeUnits, linkDuplicates } from './source-units.mjs';
import { normalizeHeading, renumberStory } from './headings.mjs';
import {
  baseLayerIds, formatHits, proseBlocks, scanBannedTerms, scanBrokenImages, scanDanglingRefs,
  scanImageForm, scanLanguageRedline, scanLocalPaths, scanMaterialList, scanReadability,
  tableHeadersOf,
} from './lint-rules.mjs';
import { activeKnowledge } from '../../../hooks/shared/knowledge.mjs';
import {
  FREEFORM_CLOSE, FREEFORM_OPEN, HUMAN_ZONE_MARK, renderReview,
} from './review-render.mjs';

const COMMANDS = ['init', 'audit', 'check', 'build', 'number'];

/** 裁决的取值与引文下限——同 verifier-report 的 evidenceVerified 口径。 */
const VERDICT_WORDS = ['讲清', '未讲清'];
/**
 * 引文的最短长度 —— **数在合同里**（`verdicts.min_quote_chars`），这里只读。
 *
 * 它有两个消费者：本文件的 check 与 hooks 侧的裁决核对。各写一份 12 时，
 * 改一处忘一处两边就不一致，而且**两边都是绿的**——那种不一致没人看得见。
 * 合同读不到时回落到 12 并照判：判据不能因为配置缺一项就整条失效。
 */
function minQuoteChars(contract) {
  return contract?.verdicts?.min_quote_chars ?? 12;
}

/** 统稿留痕的行数：作业书的自查清单有几项，这里就是几行。 */
const COPYEDIT_ROWS = 6;

/**
 * 能标 `material_only`（留在材料、不进 story）的单元 —— **只有图片**。
 *
 * 图片与文字事实不对称：一张图片不引用时，读者还能顺材料清单里的原文链接去看原件；
 * 一条文字事实不进 story 就是丢了，没有第二条路。所以「不进 story」对图片是合法状态。
 *
 * **流程图不在这里。** 开这一态是为了「PRD 里 30 张界面图不必都进 story」那个场景，
 * 而流程图在材料里通常只有三五张，从来没有塞不下的压力。流程图的合法出路只有
 * `at`（画出来）与 `covered_by`（story 自绘一张覆盖它）。
 */
const IMAGE_KINDS = new Set(['image']);

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
 * 没有单元清单、没有核对记录，正常的 check 连门都进不去。
 *
 * 走的是**同一个 `cmdCheck`**，不是另写一套：另写一套就会与生产链漂移，
 * 到那时「拿它跑过了」什么也证明不了。单元清单与核对记录给空，
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
    unitsPath: '', auditPath: '', decisionsPath: '', verdictsPath: '',
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
    unitsPath: path.join(srcDir, 'source-units.json'),
    auditPath: path.join(srcDir, 'audit.json'),
    decisionsPath: path.join(srcDir, 'decisions.json'),
    verdictsPath: path.join(srcDir, 'story-verdicts.md'),
    copyeditPath: path.join(srcDir, 'copyedit.md'),
    storyPath: path.join(featureRoot, 'AR', 'story.md'),
    reviewPath: path.join(featureRoot, 'AR', 'review.md'),
    flowPath: path.join(featureRoot, 'AR', 'story-flow.json'),
  };
}

/**
 * 随稿冻结的五件台账 —— 这里存的是 ctx 上的路径字段名，**不另列一份文件名**。
 *
 * 文件名的真源在 `story_flow.py` 的 `STORY_SRC_FROZEN`：那五件是登记时要算指纹、
 * 登记后拒绝重算、归档时随稿走的同一批。清理、冻结、存在性三处说的必须是同一批文件，
 * 各写一份就会改一处忘一处。
 */
const STORY_SRC_LEDGERS = [
  ['unitsPath', 'init'], ['auditPath', 'audit'], ['decisionsPath', 'init'],
  ['verdictsPath', '裁决'], ['copyeditPath', '统稿'],
];

/**
 * 五件台账在不在 —— **缺任一即 BLOCKER**，check 到此为止。
 *
 * 冻结只挡「登记之后改台账」，挡不住登记之前把台账删掉。而删掉是有动力的：
 * 实跑里裁决台账错到 1000+ 之后被整份删除，删完 check 的报错数确实下去了。
 * 原先五件里只有三件缺失拦得住——裁决件**只在存在 `by: author` 记录时**才被要求，
 * 机器恰好定得了全部落点时删掉它一声不吭。
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
    + '  这五件是这份 story 据以成文的全部依据，随稿冻结、随稿归档，缺一件产物就没有依据。\n'
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
    + '  定稿是一个时点的快照：那一刻的来源单元、落点账、裁决与决策登记，'
    + '就是这份 story 据以成文的全部依据。\n'
    + '  重算它们等于换掉已定稿产物的依据，而 story.md 不会跟着变——'
    + '实测过一次，登记时的台账被二十分钟后的一次重跑冲掉。\n'
    + '  材料在定稿之后继续演化是正常的，与这份 story 无关：它讲的是定稿那一刻的事。');
}

/**
 * 材料文件：合同 `sources` 声明的那几份，存在即读。
 *
 * 两种写法都认：`"PRD": "RR/prd.md"`（人写的材料，整篇都是事实），
 * 或 `{ path, notes: [...] }`——`notes` 是「按生成它的模板约定，这几类单元不是事实」，
 * 比如 spec.md 里的 `>` 块只承载登记项与作业说明。判据来自模板约定，不来自样本形状。
 */
/** 材料指纹：换行差异不算改动（同一份文件在两台机器上可能行尾不同）。 */
function digestOf(text) {
  return crypto.createHash('sha256')
    .update(String(text ?? '').replace(/\r\n/g, '\n'), 'utf-8')
    .digest('hex').slice(0, 16);
}

function sourceDocs(ctx) {
  return scanSources(ctx).docs;
}

/**
 * 合同声明的每个来源，读到了没有 —— **读不到的也要带回来**。
 *
 * 上一版这里是 `if (text !== null) out.push(...)`：读不到就静默跳过。
 * 后果是守恒面能凭空缩掉一整类而零信号：某一份来源没被产出时，那一类枚举出 0 个单元，
 * 从 init 到 check 没有一条报错提过这件事。
 *
 * 这与 ⓪ 的立意是同一件事（它防「枚举之后材料变了，守恒面悄悄小一圈」），
 * 但 ⓪ 管的是**变了**，管不了**压根不在**。
 *
 * 缺失分两档，由合同数据定，本文件不写死任何路径：
 *
 * - **`warn_if_siblings` 指的那个目录有别的文件、偏偏没有这一份 → BLOCKER。**
 *   图片在而索引不在，说明导入做了一半，不是「本需求没有界面」。
 *   这一档**没有误伤面**：目录里有文件是客观事实，索引缺席是客观缺陷。
 * - **其余缺失 → 记一笔**（`required` 只决定措辞轻重，不决定拦不拦）。
 *
 * **为什么必备来源缺失也不拦**：这条判据是新增的正向义务，按「放宽前先写命中面」
 * 的同一把尺子，新增义务也要先量误伤面。实测：把「必备来源缺失」判成 BLOCKER，
 * 114 个单测与 23 条失效形态当场变红——它们全是最小夹具，一份材料测一条判据，
 * 要求每份都备齐四类材料只会让夹具更假，不会让判据更准。
 *
 * 而根因本来就不是「没拦」，是**零信号**：守恒面缩掉一整类而没有一处提过。
 * 让它一律可见（init 的来源账 + check 的记一笔）就解决了根因；
 * 真正该拦的那一种由上面那一档拦，且拦得准。
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
        // 它只守业务编号，工程细节的家是它自己——见 enumerateUnits 的 idTokensOnly。
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
    missing.push({
      doc, rel,
      required: obj.required === true,
      siblings,
      siblingDir: obj.warn_if_siblings ?? null,
      // 只有「兄弟文件在而索引不在」才拦——那一档没有误伤面。见本函数注释。
      blocking: siblings > 0,
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
 * 一章里画了几张图 / 引了几张图片 / 有没有表。
 *
 * **图与图片数个数，表判有无**：表行不是一行一张表，一章一张表就够，所以表只问有无。
 */
function chapterForms(sections) {
  return new Map(sections.map(s => [s.title, {
    diagram: (s.text.match(DIAGRAM_FENCE) ?? []).length,
    image: (s.text.match(/!\[[^\]]*\]\(/g) ?? []).length,
    table: /^\s*\|/m.test(s.text),
    text: s.text,
  }]));
}

/**
 * 形态欠账：分了落点章、那一章却没有同类形态的那些单元。
 *
 * **同一个函数在两个时刻跑**——`audit`（写完一章就报）与 `check ④`（收口时拦）。
 * 判定逻辑只有这一份：两处各写一份的话，只要有一处认得不一样，作者就会在
 * 「audit 说没事、check 说不行」之间打转（D4 的教训推广到这里）。
 *
 * 为什么要前移：图是 token 守恒链上最薄的一环——图片单元的 token 只有文件
 * basename，画了才有、没画就没有；流程图的 token 近乎空。所以文字事实丢了会被
 * 整篇 token 守恒在任意位置捞回来，**图丢了只有这一条形态判**。而它原先只在
 * `check` 跑，也就是全篇写完之后——图分了落点章却一张没画时，作者要一路写到最后
 * 才被告知。
 *
 * **只判已渲染的章**：还没写的章当然没有图，那不是欠账。
 *
 * **判的是「分了几张画了几张」，不是「这一章有没有图」。** 只问有无时，一章分到多张
 * 只画一张也算过关：其余几张被压成箭头散文，一条都不会报。
 *
 * **它不会退回「材料有几张就得塞几张」**：分母是**作者自己给的 `at` 数**，不是材料总数。
 * 不该进 story 的图片标 `material_only`、被自绘图覆盖的标 `covered_by`，两者都不进分母，
 * 分配数当场降下来。30 张界面图给 2 张 `at` + 28 张 `material_only`，这里一条都不报。
 *
 * @returns {{at: string, kind: 'image'|'diagram'|'table_row', units: object[],
 *            want?: number, drawn?: number}[]}
 */
function formShortfall(units, recByKey, sections) {
  const forms = chapterForms(sections);
  const rendered = new Set(sections.map(s => s.title));
  const bucket = new Map();                 // `${at} ${kind}` → {at, kind, units}
  const rows = new Map();                   // at → table_row units
  for (const u of units) {
    const at = recByKey.get(u.key)?.at;
    if (!at || !rendered.has(at)) continue;
    if (!forms.has(at)) continue;
    if (u.kind === 'diagram' || u.kind === 'image') {
      const k = `${at} ${u.kind}`;
      if (!bucket.has(k)) bucket.set(k, { at, kind: u.kind, units: [] });
      bucket.get(k).units.push(u);
    } else if (u.kind === 'table_row') {
      pushInto(rows, at, u);
    }
  }
  const out = [];
  for (const item of bucket.values()) {
    // **图片的身份是文件**：两个单元指向同一个文件时，story 引一次就够——引两次
    // 另有判据拦（「同一张图被两个路径引用」）。所以图片按文件名去重后比数，否则
    // 同一张图登记两次就凭空欠一张。流程图没有文件，逐单元算。
    const want = item.kind === 'image'
      ? new Set(item.units.map(u => (u.tokens ?? [])[0] ?? u.key)).size
      : item.units.length;
    const drawn = forms.get(item.at)?.[item.kind] ?? 0;
    if (want > drawn) out.push({ ...item, want, drawn });
  }
  // 表行：**该章分到 ≥2 条时**才要求成表——只有一行的不构成表（一行的表读起来
  // 比一句话更费劲），那时只要求这一行的内容在该章出现，由整篇 token 守恒管。
  for (const [at, list] of rows) {
    if (list.length >= 2 && !forms.get(at)?.table) {
      out.push({ at, kind: 'table_row', units: list });
    }
  }
  return out;
}

function pushInto(map, key, value) {
  if (!map.has(key)) map.set(key, []);
  map.get(key).push(value);
}

/**
 * 形态欠账报成一句话——`audit` 与 `check` 共用这一份措辞。
 *
 * **一张都没画**时逐单元报，指到来源行，作者好回去看那是什么图；
 * **画了但不够**时报两个数，作者要知道还差几张，逐单元列反而看不出差额。
 */
function formShortfallLine(item) {
  const where = `落在「${item.at}」，但那一章`;
  if (item.kind === 'diagram') {
    if (item.drawn > 0) {
      return [`材料里分到「${item.at}」的图有 ${item.want} 张，那一章只画了 ${item.drawn} 张`
        + '——把流程图压成箭头文字算降级，读者要的是一眼看出的结构；'
        + 'story 自己画的那张已经覆盖了其中几张，就给那几条标 covered_by'];
    }
    return item.units.map(u => `来源材料里的图（${u.doc}:${u.line}）${where}没有图`
      + '——把流程图压成箭头文字算降级，读者要的是一眼看出的结构');
  }
  if (item.kind === 'image') {
    if (item.drawn > 0) {
      return [`材料里分到「${item.at}」的图片有 ${item.want} 张，那一章只引了 ${item.drawn} 张`
        + '——图片承载的信息，文字复述替代不了；'
        + '确实不必进正文的那几张标 material_only 并各写一句理由'];
    }
    return item.units.map(u => `来源材料里的图片（${u.doc}:${u.line}）${where}没有图片引用`
      + '——图片承载的信息，文字复述替代不了');
  }
  return [`材料里的表有 ${item.units.length} 行${where}没有表`
    + '——把表压成散文，逐项比对的那几列就没了（最先丢的是触发条件与编号）'];
}

/**
 * 工程标识的形态判定 —— **check ⑩ 与 token 守恒共用这一个判定式**。
 *
 * 两处必须是同一个真源：⑩ 判「主叙事里不许出现工程标识」，守恒判「这个 token 要在
 * 落点核得到」。各写一份时，只要有一个 token 被一边认成标识符、另一边不认，
 * 同一个单元就被两条判据夹死——写进正文违反⑩，不写违反守恒，作者怎么写都是错的
 * （内网问题 6 就是这个）。
 */
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

/** 这个 token 是不是工程标识形态（本需求自己的编号除外）。 */
function isEngineeringIdentifier(token, own) {
  return !own.has(token) && IDENTIFIER_SHAPE.test(token);
}

/**
 * 一段正文里被围栏包住的部分。
 *
 * 语言红线只管围栏之外（`lint-rules.mjs` 的 `inFence` 分支直接跳过）：围栏里是图与代码，
 * 不是面向人的叙述。守恒要跟它同一个作用域——图的类型词（`flowchart` 这类）本来就只在
 * 围栏里出现，把它按「主叙事不许有工程标识」赶去附录，是拿一条不管这里的判据管这里。
 */
function fencedText(text) {
  const out = [];
  let inFence = false;
  for (const line of String(text ?? '').split(/\r?\n/)) {
    if (/^\s*(?:```|~~~)/.test(line)) { inFence = !inFence; out.push(line); continue; }
    if (inFence) out.push(line);
  }
  return out.join('\n');
}

/**
 * 附录里承载这个单元的那一行。
 *
 * 技术契约类单元在附录的表里各占一行。守恒核工程标识时**只看那一行**——
 * 只要「附录里任何位置出现过」就算核到的话，附录是个大草垛，
 * 与「这个单元的事实在附录有落点」不是一回事。
 *
 * 怎么认那一行：拿单元自己的 token 去附录逐行找，命中最多的那一行就是它的行。
 * 找不到就返回空串（守恒随之报「核不住」，这是对的——它确实没落点）。
 */
function appendixRowFor(unit, appendixText) {
  const tokens = unit.tokens ?? [];
  if (!tokens.length || !appendixText) return '';
  let best = '', hit = 0;
  for (const line of String(appendixText).split(/\r?\n/)) {
    const n = tokens.filter(tk => line.includes(tk)).length;
    if (n > hit) { hit = n; best = line; }
  }
  return best;
}

/** 缺失来源报成一句话——BLOCKER 与「记一笔」共用这一份措辞。 */
function missingSourceLine(m) {
  if (m.siblings > 0) {
    return `合同声明的来源 ${m.doc} 不存在：${m.rel}`
      + `——但 ${m.siblingDir}/ 里有 ${m.siblings} 个文件。`
      + '图片在而索引不在，是导入做了一半：把它们登记进索引，'
      + '否则这一类材料一个单元都枚举不出来，守恒面会悄悄小一圈';
  }
  return `合同声明的来源 ${m.doc} 不存在：${m.rel}`
    + (m.required
      ? '——它是必备来源，缺了这一轮的守恒面就不完整'
      : '（可选来源，缺了是正常的）');
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
 * 模块名写进附录的改动边界表，守恒在那里核得到，语言红线只管附录之外的主叙事。
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
  refuseIfFrozen(ctx, 'init');
  const { docs, missing } = scanSources(ctx);
  if (!docs.length) {
    fail(`一份材料都读不到（合同 sources 指向 ${Object.values(ctx.contract.sources ?? {}).join('、')}）`);
  }
  // 导入做了一半要在**枚举之前**拦住：枚举完再说，作者已经拿着残缺的守恒面往下走了。
  const blocking = missing.filter(m => m.blocking);
  if (blocking.length) {
    fail(blocking.map(missingSourceLine).join('\n  ') + '\n'
      + '  补齐它再跑 init。这一类材料缺席时枚举不出任何单元，'
      + '而后面每一条判据都只在「枚举出来的那些」上跑——'
      + '守恒面小了一圈，门禁全绿也证明不了什么。');
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
      idTokensOnly: d.derived,
      docPath: d.rel,
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

  // 决策登记也是来源单元：取舍理由在材料里本来就没有，它是起草时判出来的。
  // 不给它落点义务，守恒链永远不会要求它出现——实测两份产物一份一条取舍、一份零条。
  const registered = readJson(ctx.decisionsPath, null);
  const decisions = decisionUnits(registered?.decisions);
  units.push(...decisions);
  if (!decisions.length) {
    process.stdout.write('[story-build init] 决策登记里一条都没有——'
      + '取舍在 story 里就没有来源。是还没登记，还是这个需求真的一个判断都没做过？\n');
  }

  linkDuplicates(units);

  writeJson(ctx.unitsPath, {
    generated_from: docs.map(d => d.rel),
    // 枚举时各份材料的指纹。check 拿它比对当前值——材料在枚举之后还在长，
    // 后长出来的那些永远不会成为单元，守恒面就悄悄小了一圈。
    source_digests: Object.fromEntries(docs.map(d => [d.rel, digestOf(d.text)])),
    unit_count: units.length,
    token_count: units.reduce((n, u) => n + u.tokens.length, 0),
    units,
  });

  // 骨架只有一个空数组：曾经这里还预置六类议题的空槽，判据只核「零条目时写了没写
  // none_reason」——那是个逃生口，一句「本轮扫过，无开放议题」就能过，而同一批
  // 工程决策在别的轮次实打实登记了十条。类型词表作为扫描地图留在作业书里，
  // 骨架义务删掉：扫描地图是给人的，空槽是给机器数的。
  if (!registered) writeJson(ctx.decisionsPath, { decisions: [] });

  const noToken = units.filter(u => !u.machine_facing && u.tokens.length === 0).length;
  process.stdout.write(
    `[story-build init] ${units.length} 个单元、${units.reduce((n, u) => n + u.tokens.length, 0)} 个 token`
    + `（机器面 ${units.filter(u => u.machine_facing).length} 个；`
    + `无 token ${noToken} 个——纯中文叙事，机器不判落点，由你分配、由裁决者逐条裁）\n`);

  // 来源账：哪一类贡献了多少单元。**缺席的那些显示为 0 并写明原因**——
  // 只报总数时，「少了一整类」和「这一类本来就少」长得一模一样。
  const perDoc = new Map();
  for (const u of units) {
    const d = String(u.key ?? '').split(':')[0];
    perDoc.set(d, (perDoc.get(d) ?? 0) + 1);
  }
  const line = [];
  for (const d of docs) line.push(`${d.doc} ${perDoc.get(d.doc) ?? 0}`);
  for (const m of missing) {
    line.push(`${m.doc} 0（${m.rel} 不存在${m.required ? '，必备' : '，可选'}）`);
  }
  process.stdout.write(`  来源：${line.join('、')}\n`);
  for (const m of missing) {
    process.stdout.write(`  记一笔：${missingSourceLine(m)}\n`);
  }
}

// --------------------------------------------------------------------------
// audit：三态核对
// --------------------------------------------------------------------------

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

/**
 * 切出裁决产物里的三张表。
 *
 * **按表头认，不按标题认**：标题是给人读的，作者改一个字表就找不着了；
 * 表头是契约里定死的那几列。三表分开是因为任务不同——逐单元问「材料里这件事讲了没有」，
 * 逐问问「读者这一章想知道的答了没有」，逐章问「这一章读起来对不对」。
 *
 * @returns {{units: Map, questions: {chapter,question,verdict,quote}[],
 *            chapters: {chapter,dimension,verdict,basis}[]}}
 */
function parseVerdictTables(text) {
  const out = { units: new Map(), questions: [], chapters: [] };
  if (text === null || text === undefined) return out;
  let mode = null;
  for (const line of String(text).split(/\r?\n/)) {
    const s = line.trim();
    if (!s.startsWith('|')) continue;
    const c = s.replace(/^\||\|$/g, '').split('|').map(x => x.replace(/[`*]/g, '').trim());
    if (/^[-: ]*$/.test(c[0])) continue;             // 分隔行
    if (c[0] === '单元键') { mode = 'units'; continue; }
    if (c[0] === '章' && c[1] === '问题') { mode = 'questions'; continue; }
    if (c[0] === '章' && c[1] === '维度') { mode = 'chapters'; continue; }
    if (mode === 'units' && c.length >= 3) {
      out.units.set(c[0], { verdict: c[1], quote: c[2] });
    } else if (mode === 'questions' && c.length >= 4) {
      out.questions.push({ chapter: c[0], question: c[1], verdict: c[2], quote: c[3] });
    } else if (mode === 'chapters' && c.length >= 4) {
      out.chapters.push({ chapter: c[0], dimension: c[1], verdict: c[2], basis: c[3] });
    }
  }
  return out;
}

/** 附录那一章（合同里标了 `appendix` 的那个）。没有就返回 null。 */
function appendixChapter(contract) {
  return (contract.chapters ?? []).find(c => c.appendix) ?? null;
}

/**
 * 核不住的落点，报错该说什么 —— **按 token 的类别指路，不裸列字面**。
 *
 * 上一版报的是「落点标在某章，那一章里核不到」外加一串裸 token。
 * 模型逐轮照做：把那串字面一个个抄进附录。倾倒区不是模型自己想出来的，
 * 是门禁一条一条教出来的（失败数 35→11→9→1→6→18，修一轴破另一轴）。
 *
 * 所以报错只说**这一类事实的落点长什么样**。字面仍然出现——不点名作者不知道说的是哪一条
 * ——但它出现在一句指路的话里，而不是一张待抄清单里。
 * 类别与落点名全部来自合同数据，本函数不认识任何具体业务词。
 */
function lostHint(unit, lost, contract, at) {
  const token = lost[0];
  const appendix = appendixChapter(contract);
  const subs = appendix?.subsections ?? [];
  const keep = (contract.id_shapes?.keep ?? []).some(p => {
    try { return new RegExp(`^(?:${p})$`).test(token); } catch { return false; }
  });
  if (keep) {
    return `验收编号 ${token} 要在验收那一章有独立一行，并写出可观察的通过条件`
      + '——合并进别人那一行，读者就对不上上游这条到底做没做';
  }
  if (/^\d/.test(token)) {
    return `阈值「${token}」要随它所属的那句叙述或验收行一起讲`
      + '——单独摆着的数字，读者不知道它约束的是哪一步';
  }
  if (appendix && (appendixBound(unit, contract) || /^[A-Za-z_]/.test(token))) {
    const where = subs.slice(0, 2).map(s => `「${appendix.title}·${s}」`).join('或');
    return `接口、字段、键名这一类的落点是${where}表`
      + `——「${token}」在那张表里有一行吗？主叙事里写它的中文业务名`;
  }
  return `这条事实要在「${at}」那一章讲出来：${unit.text.slice(0, 30)}`;
}

/**
 * 这个单元是不是**机器直接归附录**的那一类（合同 `allocation.appendix_bound`）。
 *
 * 技术契约小节的表行——接口、字段、存储键、配置项、事件、交接——落点只可能是
 * 附录的那两张表。让模型逐条去想「这一行读者在哪一章想知道」纯属苦役：
 * 答案对每一行都一样，而模型每轮都要重答一遍。规则来自合同数据，本文件不认识
 * 任何具体小节号。
 */
function appendixBound(unit, contract) {
  for (const rule of contract.allocation?.appendix_bound ?? []) {
    if (rule.doc && unit.doc !== rule.doc) continue;
    if (!rule.section_re) continue;
    let re;
    try { re = new RegExp(rule.section_re); } catch { continue; }
    if (re.test(String(unit.section ?? ''))) return true;
  }
  return false;
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

/** 一章里全部 `###` 小节的业务名（序号已剥）。 */
/**
 * 表头比对：声明的列**逐列逐字相等**，其后允许附加列。
 *
 * 逐字是有意的——列头是形不是内容，模板给出表头照抄即过；判「差不多」的话，
 * 同一份文档里同类的表会长出五种列名，读者每张表都要重新认一遍。
 * 附加列放行是因为真实存在（验收表可选的「主责」列）。
 */
/** 需求目录内的相对路径（正斜杠），报错与目录比对都按它说话。 */
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

function headerMatches(actual, want) {
  return (want ?? []).every((col, i) => (actual[i] ?? '').trim() === String(col).trim());
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

/**
 * 机器给落点：单元的 token 在哪一节命中得最多，`at` 就填哪一节。
 *
 * **只认硬事实**。token 是改写时本该逐字保留的那些东西——接口名、字段名、
 * 阈值与量纲、图片名、验收编号。它们在人话改写里也不会变，所以「机器核得到」
 * 与「读者读得下去」不冲突。
 *
 * **不判纯中文叙事的落点**。上一版拿 ≥8 字的正文片段做子串兜底，于是守恒同时
 * 要求「把材料改写成人话」和「逐字保留原句」——两条互斥，把材料原文整段抄进
 * 一个倾倒区是唯一同时满足的解，而门禁会判它通过——大半单元会塌进附录那个倾倒区，
 * 机器全绿。改写后的中文归裁决者逐条裁，灵敏度由删事实对抗测试验。
 *
 * **不要求全部 token 同节**——上一版正是这么判的，于是「把一件事分两处讲清楚」
 * 被判成无落点，作者只好把它们硬塞进同一段。
 */
function autoPlace(unit, sections) {
  if (!unit.tokens.length) return null;      // 纯中文叙事：机器不定落点，交作者与裁决者
  let best = null;
  for (const sec of sections) {
    const hit = unit.tokens.filter(t => sec.text.includes(t)).length;
    if (hit > 0 && (!best || hit > best.hit)) best = { title: sec.title, hit };
  }
  return best;
}

/** 规范化：去空白与标点——「点了提交、但没收到回执」与原文只差标点时仍算同一句。 */
function norm(s) {
  return String(s ?? '').replace(/[\s，。、；：!?！？（）()「」【】]/g, '');
}

/** 引文比对面上再多剥两个字符：`` ` `` 与 `*`。
 *
 * 裁决表的格子被 `parseVerdictTables` 剥过这两个（表格里的行内代码与加粗会把
 * 格子切乱），story 正文侧却留着。两端口径不一致时，凡是抄了带行内代码或加粗的
 * 那句话，都会被判成「在这一章里检索不到」——附录表里的事实几乎条条如此。
 */
function normQuote(s) {
  return norm(s).replace(/[`*]/g, '');
}

/**
 * 规范化的同时留下每个字符在原文里的下标。
 *
 * 句边界要在**原文**上判：`norm` 把句号问号全剥了，规范化之后的串里根本没有句子。
 * 于是引文先按规范化面定位（作者抄的时候标点常有出入），再用这张表把位置换回原文。
 */
function normIndex(s) {
  const src = String(s ?? '');
  const drop = /[\s，。、；：!?！？（）()「」【】`*]/;
  let text = '';
  const idx = [];
  for (let i = 0; i < src.length; i++) {
    if (drop.test(src[i])) continue;
    text += src[i];
    idx.push(i);
  }
  return { src, text, idx };
}

// 句读：一句话可以停在这里。引文的规范化形态里没有它们，所以判的是引文之后紧跟着的原文。
// 冒号也算：「前一段是本特性，后一段由兄弟特性承载，分工如下：」是完整的一句，
// 它引出下面那张表——这种目的句成片出现，判据不认它就会把好形态拦掉。
const SENTENCE_END = /[。？！；：:]/;
// 一句话可以从这里起头：行首、上一句的句读之后、导语冒号之后、列表标记之后、表格的格子里。
const SENTENCE_START = /[\n。？！；：:|>]/;
const LIST_MARK = /[-*+]/;
// 往两边跳过的装饰：空白与包裹符号，它们既不结束一句话也不开始一句话。
const TRIM_AROUND = /[ \t`*（()）「」【】]/;

/** 这个位置是不是一行的开头（只隔着空白）。 */
function atLineHead(src, pos) {
  return /(^|\n)[ \t]*$/.test(src.slice(0, pos));
}

/**
 * 这个字符是不是一个块的起头标记——无序列表的 `-`，或有序列表的 `1.` / `1)`。
 *
 * 有序列表要单独认：流程章常写成 `1. **进入与资格**：…` 这种编号步骤，
 * 只认 `-` 的话，那一章每一步的第一句都会被判成「开头掐在半句里」。
 */
function isBlockMark(src, i) {
  if (LIST_MARK.test(src[i]) && atLineHead(src, i)) return true;
  if (src[i] !== '.' && src[i] !== ')') return false;
  let k = i - 1;
  while (k >= 0 && /\d/.test(src[k])) k--;
  return k < i - 1 && atLineHead(src, k + 1);
}

/**
 * 引文在原文的这一处，是不是**起止于句边界**。
 *
 * 这一条替代不了「引文讲的是不是这件事」，它只堵掉一种做法：从该章里切一段
 * 十来个字的窗口交上来。窗口满足「够长、是这一章的原文、不是来源原话」，
 * 却连一句话都不是——实测一轮，抽样十行里十行都是这种切片。
 *
 * 表格行里的事实按**格子**判：`|` 两侧就是这条事实的起止，整格即合法引文。
 */
function atSentenceBounds(src, start, end) {
  let i = start - 1;
  while (i >= 0 && TRIM_AROUND.test(src[i])) i--;
  const okStart = i < 0 || SENTENCE_START.test(src[i]) || isBlockMark(src, i);
  let j = end + 1;
  while (j < src.length && TRIM_AROUND.test(src[j])) j++;
  const okEnd = j >= src.length || src[j] === '\n' || src[j] === '|'
    || SENTENCE_END.test(src[j]);
  return { okStart, okEnd };
}

/**
 * 引文在这一章里的**任一处**起止于句边界，就算数。
 *
 * 同一句话在一章里出现两次是常事（表里一条、正文里一条）。要求处处都合规，
 * 等于拿另一处的排版去否掉作者抄对了的那一处。
 *
 * @returns {{found:boolean, okStart:boolean, okEnd:boolean}}
 */
function quoteBounds(chapterRaw, quote) {
  const map = normIndex(chapterRaw);
  const q = normQuote(quote);
  if (!q) return { found: false, okStart: false, okEnd: false };
  let best = null;
  for (let at = map.text.indexOf(q); at >= 0; at = map.text.indexOf(q, at + 1)) {
    const hit = atSentenceBounds(map.src, map.idx[at], map.idx[at + q.length - 1]);
    if (hit.okStart && hit.okEnd) return { found: true, ...hit };
    if (!best || (hit.okStart ? 1 : 0) + (hit.okEnd ? 1 : 0)
        > (best.okStart ? 1 : 0) + (best.okEnd ? 1 : 0)) best = hit;
  }
  return best ? { found: true, ...best } : { found: false, okStart: false, okEnd: false };
}

function cmdAudit(ctx) {
  refuseIfFrozen(ctx, 'audit');
  const doc = readJson(ctx.unitsPath, null);
  if (!doc) fail(`还没有来源单元清单，先跑 init：${ctx.unitsPath}`);
  // story.md 还不存在 = **一章都没渲染**，不是错误：分配先于正文，
  // 这一步正是用来核「每个单元都分到了地方」的。渲染过程中它是「渲染了几章」的中间态。
  const storyText = readText(ctx.storyPath) ?? '';
  const sections = storySections(storyText);
  const prev = readJson(ctx.auditPath, { records: [] });
  const prevByKey = new Map((prev.records ?? []).map(r => [r.key, r]));

  const appendixTitle = appendixChapter(ctx.contract)?.title ?? null;
  const records = [];
  for (const u of doc.units) {
    if (u.machine_facing) {
      records.push({ key: u.key, machine_facing: true });
      continue;
    }
    // 开放议题不进落点账：它还没有结论，正文里写它等于把未定的事说成定了。
    // 它在 review.md 里逐条摆给评审人——那才是它的去处。
    if (u.kind === 'decision' && u.status === 'open') continue;
    const old = prevByKey.get(u.key);
    // 作者填的 covered_by 保留——它是作者的判断，机器只核不重算
    if (old?.covered_by) {
      records.push({ key: u.key, covered_by: old.covered_by });
      continue;
    }
    // 图类的 material_only 同理：作者判定这张图不必进 story，机器不重算、只核形态
    if (old?.material_only && IMAGE_KINDS.has(u.kind)) {
      records.push({ key: u.key, material_only: old.material_only });
      continue;
    }
    // 技术契约的那些行由机器直接归附录：落点对每一行都一样，不值得让模型逐条重想
    if (appendixTitle && appendixBound(u, ctx.contract)) {
      records.push({ key: u.key, at: appendixTitle, by: 'machine' });
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
    `[story-build audit] ${records.length} 条；待你分配 ${open.length} 条`
    + `（机器已归位 ${records.length - open.length} 条：硬事实按 token 定章、`
    + `技术契约行直接进附录）\n`
    + `  待你分配的都是纯中文叙述：给每条一个正文章名 at，`
    + `或标 covered_by 指向已分配的另一条\n`);

  // 分布：两个总数不够用来定批量策略。二百条待分配时要先看它们**长什么样**——
  // 集中在哪几段来源、机器归位的那些去了哪几章——才谈得上分批。
  // 实测过一轮：这些数模型自己写脚本 Counter 了一遍，而数据本来就在这儿。
  const tri = {
    at: records.filter(r => r.at).length,
    covered_by: records.filter(r => r.covered_by).length,
    machine_facing: records.filter(r => r.machine_facing).length,
    open: open.length,
  };
  process.stdout.write(
    `  三态：at ${tri.at}｜covered_by ${tri.covered_by}`
    + `｜机器面 ${tri.machine_facing}｜待分配 ${tri.open}\n`);
  const bySource = new Map();
  for (const r of open) {
    const u = doc.units.find(x => x.key === r.key);
    const src = u?.source ?? u?.doc ?? '(未知来源)';
    bySource.set(src, (bySource.get(src) ?? 0) + 1);
  }
  if (bySource.size) {
    process.stdout.write(`  待分配按来源：`
      + `${[...bySource].sort((a, b) => b[1] - a[1]).map(([s, n]) => `${s} ${n}`).join('、')}\n`);
  }
  const landed = new Map();
  for (const r of records) {
    if (r.at) landed.set(r.at, (landed.get(r.at) ?? 0) + 1);
  }
  if (landed.size) {
    process.stdout.write(`  已分配按落点章：`
      + `${[...landed].sort((a, b) => b[1] - a[1]).map(([t, n]) => `${t} ${n}`).join('、')}\n`);
  }

  const SHOW = 10;
  for (const r of open.slice(0, SHOW)) {
    const u = doc.units.find(x => x.key === r.key);
    process.stdout.write(`  - ${r.key}｜${(u?.text ?? '').slice(0, 60)}\n`);
  }
  if (open.length > SHOW) {
    process.stdout.write(`  …另 ${open.length - SHOW} 条同形，全部明细在 `
      + `${path.basename(ctx.auditPath)}（三态皆空的那些）\n`);
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

  // 形态欠账：写完一章就说这一章欠什么，不必等到全篇写完被 check 一次性告知。
  // 与 `check ④` **同一个函数**（`formShortfall`）——判定一致，只是这里报、那里拦。
  const shortfall = formShortfall(doc.units, new Map(records.map(r => [r.key, r])), sections);
  if (shortfall.length) {
    process.stdout.write('  形态欠账（已渲染章）：\n');
    for (const item of shortfall) {
      const what = { image: '图片', diagram: '图', table_row: '表行' }[item.kind];
      const who = item.units.slice(0, 4)
        .map(u => `${u.key}「${String(u.text ?? '').replace(/\s+/g, ' ').slice(0, 24)}」`)
        .join('、');
      const short = item.want === undefined
        ? `欠${what} ${item.units.length} 个`
        : `分${what} ${item.want}、画了 ${item.drawn}，还欠 ${item.want - item.drawn}`;
      process.stdout.write(
        `    ${item.at} —— ${short}：${who}`
        + `${item.units.length > 4 ? '…' : ''}\n`);
    }
  }

  // 下一个待写章欠什么：第二步的输入表写着「分给本章的那些单元正文」，
  // **而在此之前没有任何东西产出这份清单**——作者得自己把几百条按章 join 一遍，
  // 靠记忆对，图这种只占几条的自然掉出去。这里把它交到手上。
  //
  // 只列 `pending[0]` 一章：一次给全十章就回到 1.0 逐章任务书的体量了。
  // 1.0 真正的问题是**合同按关键词把材料路由给章**，同一事实被四个章节合同各指一次；
  // 这里投影的是作者自己定的一对一分配，按构造不可能重复。
  if (pending.length) {
    const next = pending[0];
    const mine = records.filter(r => r.at === next);
    const byKind = new Map();
    const unitOf = new Map(doc.units.map(u => [u.key, u]));
    for (const r of mine) {
      const u = unitOf.get(r.key);
      if (u) pushInto(byKind, u.kind ?? 'paragraph', u);
    }
    process.stdout.write(`  下一个待写章「${next}」分到 ${mine.length} 条：\n`);
    for (const kind of ['diagram', 'image', 'table_row']) {
      const list = byKind.get(kind);
      if (!list?.length) continue;
      const what = { diagram: '图', image: '图片', table_row: '表行' }[kind];
      const who = list.map(u => `${u.key}「${String(u.text ?? '')
        .replace(/\s+/g, ' ').slice(0, 30)}」`).join('、');
      process.stdout.write(`    ${what} ${list.length} 个：${who}\n`);
    }
    const rest = [...byKind].filter(([k]) => !['diagram', 'image', 'table_row'].includes(k));
    if (rest.length) {
      process.stdout.write(`    其余：`
        + rest.map(([k, v]) => `${k} ${v.length}`).join('、') + '\n');
    }
  }
}

// --------------------------------------------------------------------------
// check：整篇守恒与形态
// --------------------------------------------------------------------------

const EMPTY_SECTION_TEXT = '本需求不涉及。';

/**
 * 术语单元格的**主名**——括注剥掉之后剩下的那部分。
 *
 * 术语表的单元格普遍写成「主名（同义提示）」或「主名（取值枚举）」：括号里是给读者的
 * 提示，不是要求 story 逐字复述的内容。拿整个单元格去 story 做子串匹配，主名明明在
 * 也会判成缺失，而术语表里带括注的行往往占大多数。
 *
 * **剥空不静默**：整格就是一个括注时按原串判，否则「（仅括注）」这种写坏的格子
 * 会因为主名为空而被无声跳过，看起来像通过了。
 */
function glossaryMainName(cell) {
  const bare = String(cell ?? '').replace(/[（(][^）)]*[）)]/g, '').trim();
  return bare || String(cell ?? '').trim();
}

/**
 * spec §0 术语映射表里、应当出现在 story 的业务实体词，哪些没出现。
 *
 * 层身份按依赖方向从架构 DSL 派生（`can_depend_on` 为空者是平台能力层），不写层名字面——
 * 写死名字换个工程就静默失效。无该列或派生不到时不过滤，保持向后兼容。
 *
 * 核的是**主名**（见 `glossaryMainName`），报的是**原单元格**——报错要让人一眼
 * 认出是术语表里的哪一行。
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
    .filter(t => t && !storyText.includes(glossaryMainName(t)));
}

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
  // 起步先判五件台账在不在：删掉一件再跑，后面每一条判据都只是「依据不全」的回声。
  requireLedgers(ctx);
  const problems = [];
  // 判据类的分组戳：只影响输出怎么排，不影响判定。
  const marks = [];
  const mark = (label) => marks.push({ from: problems.length, label });
  // 记一笔但不拦：定稿之后材料继续演化是正常的，读者该知道，但它不是错。
  const notes = [];
  // 离线模式（仲裁锚）：单元清单与核对记录给空，依赖它们的判项一条不判，
  // 不依赖的照跑——同一个函数，不是另写一套。
  const doc = ctx.offline ? { units: [] } : readJson(ctx.unitsPath, null);
  if (!doc) fail(`还没有来源单元清单，先跑 init：${ctx.unitsPath}`);
  const storyText = readText(ctx.storyPath);
  if (storyText === null) fail(`读不到 ${ctx.storyPath}`);
  const audit = ctx.offline ? { records: [] } : readJson(ctx.auditPath, null);
  if (!audit) fail(`还没有核对记录，先跑 audit：${ctx.auditPath}`);

  mark('⓪a 声明的来源都在');
  // ⓪a 合同声明的来源都在
  //
  // ⓪ 防的是「枚举之后材料变了」，防不了「声明的来源压根不在」。后者更隐蔽：
  // 那一类连一个单元都枚举不出来，而后面每一条判据都只在「枚举出来的那些」上跑，
  // 于是守恒面小了一整类，门禁却全绿：某一份声明的来源没被产出时，那一类枚举出 0 个
  // 单元，从头到尾没有一条报错提过。
  if (!ctx.offline) {
    const { missing } = scanSources(ctx);
    for (const m of missing) {
      (m.blocking ? problems : notes).push(missingSourceLine(m));
    }
  }

  mark('⓪ 材料未在枚举后变过');
  // ⓪ 材料没在枚举之后又变过
  //
  // 规格件在 story 写完之后还会继续长——评审裁定回填、遗漏补写。后长出来的内容
  // 永远不会成为来源单元，于是守恒面悄悄小了一圈：check 在登记那一刻是过的，
  // 过些时候重跑 audit 才露出一批三态皆空，来源全是后长出来的那些内容。
  // 这是**物理门禁**而不是流程约定：「记得重跑一次 init」这种话，模型会忘。
  const frozen = ctx.offline ? { written: false, digests: {} } : storyFrozen(ctx);
  if (!ctx.offline) {
    const before = readJson(ctx.unitsPath, {}).source_digests ?? null;
    if (before) {
      const drifted = sourceDocs(ctx)
        .filter(d => before[d.rel] && before[d.rel] !== digestOf(d.text))
        .map(d => d.rel);
      const added = sourceDocs(ctx).filter(d => !(d.rel in before)).map(d => d.rel);
      if (drifted.length || added.length) {
        // 登记之后这不再是问题：story 定稿于登记那一刻，是**快照**。材料继续演化
        // 与它无关——评审回稿修订规格件正是常态路径。此前这里指路「重跑 init」，
        // 而 init 在冻结之后会拒绝执行，两条一起就把人锁死在中间。
        if (frozen.written) {
          notes.push(`材料在成文登记之后变了：${[...drifted, ...added].join('、')}`
            + '——story 与台账是定稿那一刻的快照，不随材料演化；这里只记一笔，不必处置');
        } else {
          problems.push(`材料在枚举之后变了：${[...drifted, ...added].join('、')}`
            + '——重跑 init，audit 会把新增单元列进待分配（你已经分好的那些按 key 保留）');
        }
      }
    }
    // ⓪b 台账没在登记之后被换过。拒绝 init/audit 挡的是这两条命令，
    // 挡不住有人直接改文件——指纹核对补上那一面。
    for (const [name, want] of Object.entries(frozen.digests)) {
      const now = digestOf(readText(path.join(ctx.srcDir, name)));
      if (want === null && !fs.existsSync(path.join(ctx.srcDir, name))) continue;
      if (want !== now) {
        problems.push(`${name} 与成文登记时的台账对不上——`
          + 'story 定稿之后台账随稿冻结，它记的是这份 story 据以成文的依据；'
          + '改了它，产物与依据就对不上了');
      }
    }
  }

  const sections = storySections(storyText);
  const titles = sections.map(s => s.title);
  const want = ctx.contract.chapters.map(c => c.title);

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

  mark('② 落点守恒');
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
  const appendixTitle = appendixChapter(ctx.contract)?.title ?? null;
  const narrativeKinds = new Set(ctx.contract.allocation?.narrative_kinds ?? []);
  // 工程标识的守恒范围是**附录里的那一行**，不是叙事落点章——判定式与 ⑩ 共用一个。
  const ownIds = ownIdentifiers(ctx.args.feature);
  const appendixText = appendixTitle ? (sectionText.get(appendixTitle) ?? '') : '';

  for (const u of doc.units) {
    if (u.machine_facing) continue;
    if (u.kind === 'knowledge') continue;   // 规约条目走 ⑦ 判定表，不走章节落点
    if (u.kind === 'decision' && u.status === 'open') continue;   // 开放议题走评审记录
    const rec = recByKey.get(u.key);
    const states = ['at', 'covered_by', 'machine_facing', 'material_only'].filter(k => rec?.[k]);
    if (states.length === 0) { stateless.push(u); continue; }
    if (states.length > 1) {
      problems.push(`${u.key} 同时标了 ${states.join(' 与 ')}——各态互斥，一条只能是其中一个`);
    }
    if (rec.material_only) {
      // 留在材料、不进 story。**只给图类**：文字事实没有「去材料里看」这条路。
      //
      // 放宽账（它防什么 / 误伤面 / 谁来接）：
      // 这一态开的口子是「**图片**可以不进 story」，替代的是「整篇图片数不降级」——
      // 后者在 30+ 图的真实 PRD 上等价于逼作者把 PRD 复刻一遍。
      // 接的人是 `formShortfall`：分了落点章却没画够，`audit` 当场报、`check` 收口拦。
      // 已用 30 图夹具证过：给了 at 却没画的那些，audit 逐条报得出来。
      //
      // **流程图不给这一态**：开它是为了 30 张界面图那个场景，而流程图在材料里通常
      // 只有三五张，没有塞不下的压力。所以这里判 kind。
      if (!IMAGE_KINDS.has(u.kind)) {
        problems.push(`${u.key} 标了 material_only，但它不是图片（kind=${u.kind}）`
          + '——这一态只给图片：图片不引用时读者还能顺材料清单的链接去看原件；'
          + '文字事实不进 story 就是丢了，流程图请用 at 或 covered_by');
      } else if (String(rec.material_only).trim().length < 4) {
        problems.push(`${u.key} 的 material_only 没写理由`
          + '——写一句为什么这张图片不必进 story，空着分不清「判过了不需要」与「懒得引」');
      }
      continue;
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
      // 业务叙述不落附录：附录是查阅件，读者顺着正文读下来要能读懂这件事。
      // 塞进附录等于让它从阅读路径上消失，而附录判据松，大批单元会往那里塌。
      if (narrativeKinds.has(u.kind) && appendixTitle && rec.at === appendixTitle) {
        problems.push(`${u.key}「${u.text.slice(0, 30)}」被分到「${appendixTitle}」，`
          + `但${appendixTitle}是查阅件，业务叙述不落在那里`
          + `——这条讲的是${u.doc}${u.section ? `·${u.section}` : ''}的事，`
          + '读者在哪一章想知道它，就分那一章');
        continue;
      }
      // 机器定不了的，交给裁决者；这里只核标题在册，讲没讲清由 ⑥ 核
      authorPlaced.push(u);
      continue;
    }
    // by: machine —— 机器给的落点，必须在**那一章**里核得住。
    // 只核硬事实：`by: machine` 现在只可能由 token 命中产生（见 autoPlace），
    // 没有 token 的单元走不到这里。
    //
    // **工程标识按附录里的那一行核，不按叙事落点章核。**
    //
    // 放宽账：语言红线（⑩）不许主叙事出现工程标识，而守恒要求 token 在落点核得到，
    // 同一个单元被两条判据夹死——写进正文违反⑩，不写违反守恒（内网问题 6）。
    // 误伤面就是这个死锁；接的人是**附录的对应行**：技术契约类单元本来就由
    // `appendixBound` 机器直接归附录，各占一行，标识符在那一行核得住。
    //
    // 范围是**那一行**不是整个附录：只要「附录里任何位置出现过」就算核到的话，
    // 附录是个大草垛，与「这个单元的事实有落点」不是一回事——那才是真放宽。
    //
    // 作用域与 ⑩ 对齐：⑩ 跳过围栏（`lint-rules.mjs` 的 `inFence`），
    // 所以围栏里核得住的也算数——图的类型词只在围栏里出现，⑩ 本来就不管它。
    const fenced = fencedText(chapter);
    const lost = u.tokens.filter(t => {
      if (!isEngineeringIdentifier(t, ownIds)) return !chapter.includes(t);
      if (chapter.includes(t)) return false;          // 正文里写了也算（⑩ 会另判它）
      if (fenced.includes(t)) return false;           // 围栏里，⑩ 管不到
      return !appendixRowFor(u, appendixText).includes(t);
    });
    if (lost.length) {
      missingTokens.push({ key: u.key, unit: u, lost, at: rec.at });
    }
  }

  if (stateless.length) {
    problems.push(`${stateless.length} 个单元没有任何落点（三态皆空）：`
      + stateless.slice(0, 5).map(u => `${u.key}「${u.text.slice(0, 30)}」`).join('；')
      + (stateless.length > 5 ? `……另 ${stateless.length - 5} 个` : '')
      + '——补写正文，或标 covered_by 指向已进正文的另一条；'
      + '这件事读者在哪一章想知道，就分那一章');
  }
  for (const m of missingTokens.slice(0, 8)) {
    problems.push(`${m.key} 在「${m.at}」里核不住：`
      + lostHint(m.unit, m.lost, ctx.contract, m.at));
  }
  if (missingTokens.length > 8) {
    problems.push(`另有 ${missingTokens.length - 8} 个单元的落点核不住（跑 audit 看全量）`);
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

  mark('④ 形态守恒');
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

  // 图片引用的是**登记里那张图的既有落盘位置**，不是它的副本。
  //
  // 实测：模型把材料里抽出来的图复制第三份进归档目录、改个名再引用，其中两个名字
  // 指向的是同一张图（内容一致），story 里当成两张不同的图各引一次，后一张没有任何
  // 说明段。复制出来的副本谁也不会去维护，改名之后更没人看得出它就是原来那张。
  // 判据只问两件事：引的这张在登记里吗、同一张图有没有被两个名字引用。
  {
    const registered = new Map();          // 登记的图片文件名 → 它在材料里的位置与落盘目录
    for (const u of doc.units) {
      if (u.kind !== 'image') continue;
      const name = (u.tokens ?? [])[0];
      if (!name) continue;
      const ref = /!\[[^\]]*\]\(([^)\s]+)/.exec(u.text ?? '')?.[1] ?? name;
      registered.set(name, {
        at: `${u.doc}:${u.line}`,
        dir: path.posix.dirname(joinPosix(path.dirname(u.docPath ?? ''), ref)),
      });
    }
    if (registered.size) {
      // **按落盘位置判，不只按文件名**：只比文件名，改名的拦得住、同名复制进一个新目录的
      // 拦不住——实测一轮，模型自建了一个图片目录，全树因此有五份同一张图。
      // 允许的位置是「材料里那些图既有的落盘目录」加上归档件自己的图片目录（合同数据）。
      const allowDirs = new Set(registered.values().map(v => v.dir));
      const storyImageDir = ctx.contract.story_image_dir;
      if (storyImageDir) {
        allowDirs.add(joinPosix(path.dirname(relFromFeature(ctx, ctx.storyPath)), storyImageDir));
      }
      const byName = new Map();            // 文件名 → story 里引到它的那些路径
      for (const src of seen) {
        if (/^(https?:|data:)/i.test(src)) continue;
        const name = src.split(/[\\/]/).pop();
        const dir = path.posix.dirname(
          joinPosix(path.dirname(relFromFeature(ctx, ctx.storyPath)), src));
        if (!registered.has(name)) {
          problems.push(`story 引用的图片「${src}」不在材料的图片登记里`
            + '——引它在仓里的既有落盘位置，不要复制一份到归档目录再改名；'
            + '副本没人维护，改了名读者也认不出它就是原来那张');
          continue;
        }
        if (!allowDirs.has(dir)) {
          problems.push(`story 引用的图片「${src}」在一个新建的图片目录里`
            + `（登记在 ${registered.get(name).at}）——引它既有的落盘位置，别另建目录再复制一份；`
            + '同一张图散在几个目录里，改了一处其余几处就成了旧图');
          continue;
        }
        if (!byName.has(name)) byName.set(name, []);
        byName.get(name).push(src);
      }
      for (const [name, srcs] of byName) {
        if (srcs.length < 2) continue;
        problems.push(`同一张图被两个路径引用：${srcs.join('、')}`
          + `（登记在 ${registered.get(name).at}）——同一张图只引一次，一处说清它画的是什么`);
      }
    }
  }

  // 图连落点都没有：这一条与形态欠账是两件事——欠账是「分了章但那章没画」，
  // 这里是「压根没表态」。
  for (const u of doc.units) {
    if (u.kind !== 'diagram') continue;
    const rec = recByKey.get(u.key);
    if (!rec?.at && !rec?.covered_by) {
      problems.push(`来源材料里的图（${u.doc}:${u.line}）在 story 里没有落点`
        + '——图是读者最依赖的那部分，不能只在材料里有：'
        + '按叙述逻辑分个落点章画出来，或者 story 自己画了一张覆盖它就标 covered_by');
    }
  }

  // 形态欠账：与 `audit` 同一个函数、同一份措辞，只是这里拦、那里报。
  for (const item of formShortfall(doc.units, recByKey, sections)) {
    for (const line of formShortfallLine(item)) problems.push(line);
  }

  // **没有「全篇总数不降级」这类判据**，图与图片都没有。曾经有两条，形状是
  // 「材料里有 N 张，story 里少于 N 就报」。它们的分母是**材料里有几张**，作者压不下来，
  // 只能塞；30+ 图的真实 PRD 上，那等价于把 PRD 复刻一遍。
  //
  // 接手的是上面的 `formShortfall`，它比的是同一件事的另一个分母：**作者自己给了
  // 几个 `at`**。不该进 story 的图片标 `material_only`、被自绘图覆盖的标 `covered_by`，
  // 分配数当场降下来，所以它抓得住「分了 4 张只画 1 张」而不逼任何人硬塞。
  //
  // 把全篇总数那种判据加回来是走回头路，三条理由：它不看 `covered_by`（story 合并
  // 自绘会被误报）、它数的是所有带语言标签的围栏（`json` / `text` 也当成图）、
  // 它的分母不受作者支配。
  //
  // 反向的数量判据（引用率上限之类）同样不设：逼引与逼不引都是拿数量代替判断。

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
      // 实测一份产物七条议题全是 `###`。
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

  mark('⑥ 裁决核实');
  // ⑥ 裁决核实：机器定不了落点的那些，裁决者要逐条裁并附引文
  //
  // 这一条替代上一版的「靠语义判据守恒」那个空计数——说了「有 N 条机器管不了」，
  // 却没人真去管它们，等于把漏写记了个数就放行。
  const verdictConf = ctx.contract.verdicts ?? {};
  const unitWords = verdictConf.unit_words ?? VERDICT_WORDS;
  const vtextAll = readText(ctx.verdictsPath);
  const tables = parseVerdictTables(vtextAll);
  const quoteUses = new Map();        // 规范化引文 → 拿它作证的单元键
  const quoteReuseMax = Number(verdictConf.quote_reuse_max) || 0;
  if (authorPlaced.length) {
    const vtext = vtextAll;
    if (vtext === null) {
      problems.push(`${authorPlaced.length} 个单元的落点机器定不了，需要裁决者逐条裁，`
        + `但 ${path.basename(ctx.verdictsPath)} 不存在`);
    } else {
      const rows = tables.units;
      for (const u of authorPlaced) {
        const row = rows.get(u.key);
        if (!row) { problems.push(`裁决表里没有 ${u.key}「${u.text.slice(0, 30)}」这一行`); continue; }
        if (!unitWords.includes(row.verdict)) {
          problems.push(`${u.key} 的裁决「${row.verdict}」不是 ${unitWords.join(' / ')} 之一`);
          continue;
        }
        if (row.verdict === unitWords[1]) {
          problems.push(`${u.key}「${u.text.slice(0, 30)}」被裁「未讲清」——补写那一章`);
          continue;
        }
        const q = normQuote(row.quote);
        const chapterRaw = sectionText.get(recByKey.get(u.key)?.at) ?? '';
        const chapter = normQuote(chapterRaw);
        if (q.length < minQuoteChars(ctx.contract)) {
          problems.push(`${u.key} 的引文只有 ${q.length} 字（要求 ≥${minQuoteChars(ctx.contract)}）`);
        } else if (!chapter.includes(q)) {
          problems.push(`${u.key} 的引文在它落点那一章里检索不到——引文要从 story 抄`);
        } else if (normQuote(u.text).includes(q)) {
          // 把材料原话抄回来是回声：它证明的是「材料这么说」，不是「story 讲清了」
          problems.push(`${u.key} 的引文是来源单元原文的子串——那是回声，抄 story 里你据以判断的那句`);
        } else {
          // 句边界：够长、是那一章的原文、不是回声——这三条一段**任意切出来的窗口**
          // 也能同时满足。实测一轮，模型正是这么做的：从落点章里切十来个字交上来，
          // 连一句话都不是（抽样十行里十行）。所以要求引文起止于句边界：
          // 起点是句首（行首、上一句的句读之后、导语冒号之后、列表标记之后、格子里），
          // 终点是句读或行尾。表格行按格子判，`|` 两侧就是这条事实的起止。
          //
          // 到此为止是形式判能走到的头。「同一章里的完整句，但讲的仍不是这件事」
          // 只能由裁决者与抽样人核兜住——再往上就是相似度，那条路已经堵死不走。
          const bounds = quoteBounds(chapterRaw, row.quote);
          if (!bounds.okStart || !bounds.okEnd) {
            const which = !bounds.okStart && !bounds.okEnd ? '两头都不是'
              : (!bounds.okStart ? '开头掐在半句里' : '结尾停在半句里');
            problems.push(`${u.key} 的引文${which}——`
              + '引文要抄讲这件事的那句完整的话，从句子开头抄到句读或行尾；'
              + '事实写在表格里的，抄它那一格');
          }
          const seen = (quoteUses.get(q) ?? []).concat(u.key);
          quoteUses.set(q, seen);
          if (quoteReuseMax && seen.length > quoteReuseMax) {
            problems.push(`同一句引文已经给 ${seen.length} 个单元作证`
              + `（上限 ${quoteReuseMax}：${seen.slice(0, 3).join('、')}…）`
              + '——一句话不能包打全章，逐单元给出讲它的那一句');
          }
        }
      }
    }
  }

  mark('⑥b 逐问与逐章');
  // ⑥b 逐问与逐章：每章的读者问题答了没有、这一章读起来对不对
  //
  // 逐单元守的是「材料里的事实没丢」，它守不住「读者想知道的事没人回答」——
  // 材料里没写的东西不会成为单元，而读者照样会问。逐问补的是这个缺口。
  // 逐章判的是六个语义维度（合同 `verdicts.chapter_dimensions`）：业务过程与功能
  // 分没分开、正常受限与真异常分没分开、取舍有没有被否方案……这些机器判不了。
  //
  // **前提是裁决产物已经存在**。writer 交回前会自己跑一次 check，那时裁决者还没上场，
  // 拦它没有意义；裁决者一旦交了产物，三张表就都得齐——只交一张，等于把
  // 「读者的问题答了没有」和「这一章读起来对不对」两件事悄悄跳过了。
  if (storyText && vtextAll !== null && verdictConf.chapter_dimensions?.length) {
    const questionWords = verdictConf.question_words ?? [];
    const chapterWords = verdictConf.chapter_words ?? [];
    const answered = new Map(tables.questions.map(r => [`${r.chapter}｜${r.question}`, r]));
    const judged = new Map(tables.chapters.map(r => [`${r.chapter}｜${r.dimension}`, r]));
    const missingQ = [];
    const missingC = [];
    // 空章（正文恰为「本需求不涉及。」）不判：它已经明说这件事不在本需求里，
    // 读者的问题也就不存在。要求它答，只会逼出一段为了过门禁而写的空话。
    const isEmptyChapter = (title) =>
      norm(sectionText.get(title) ?? '') === norm(EMPTY_SECTION_TEXT);
    for (const chapter of ctx.contract.chapters) {
      if (isEmptyChapter(chapter.title)) continue;
      for (const q of chapter.questions ?? []) {
        const row = answered.get(`${chapter.title}｜${q}`);
        if (!row) { missingQ.push(`${chapter.title}｜${q.slice(0, 20)}`); continue; }
        if (!questionWords.includes(row.verdict)) {
          problems.push(`「${chapter.title}」的问题裁决「${row.verdict}」`
            + `不是 ${questionWords.join(' / ')} 之一`);
        } else if (row.verdict === questionWords[1]) {
          problems.push(`「${chapter.title}」没答读者的问题「${q.slice(0, 24)}」`
            + `——${row.quote || '裁决者没写缺什么'}`);
        } else if (norm(row.quote).length < minQuoteChars(ctx.contract)) {
          problems.push(`「${chapter.title}」问题「${q.slice(0, 16)}」的引文不足 ${minQuoteChars(ctx.contract)} 字`);
        } else if (!norm(sectionText.get(chapter.title) ?? '').includes(norm(row.quote))) {
          problems.push(`「${chapter.title}」问题「${q.slice(0, 16)}」的引文在该章里检索不到`);
        }
      }
      if (chapter.appendix) continue;      // 附录是查阅件，不判可读性维度
      for (const dim of verdictConf.chapter_dimensions) {
        const row = judged.get(`${chapter.title}｜${dim}`);
        if (!row) { missingC.push(`${chapter.title}｜${dim.slice(0, 14)}`); continue; }
        if (!chapterWords.includes(row.verdict)) {
          problems.push(`「${chapter.title}」的「${dim.slice(0, 14)}」裁决「${row.verdict}」`
            + `不是 ${chapterWords.join(' / ')} 之一`);
        } else if (row.verdict === chapterWords[1]) {
          problems.push(`「${chapter.title}」的「${dim.slice(0, 14)}」不达标`
            + `——${row.basis || '裁决者没写依据'}`);
        } else if (!row.basis) {
          problems.push(`「${chapter.title}」的「${dim.slice(0, 14)}」判了达标却没写依据`);
        }
      }
    }
    if (missingQ.length) {
      problems.push(`逐问表缺 ${missingQ.length} 行（${missingQ.slice(0, 3).join('、')}`
        + `${missingQ.length > 3 ? ' …' : ''}）——每章每个读者问题都要有裁决`);
    }

    // 同一句被两章共用 = 同一事实在两处都作为「答了」的证据 → 它在其中一处是重复的。
    // 「分配恰好一处」管的是来源单元，管不住作者把同一段话写进两章；
    // 段落级重复由可读性那条管，这一条管的是**同一件事被当成两章各自的答案**。
    const quoteChapters = new Map();
    for (const row of tables.questions) {
      if (row.verdict !== questionWords[0]) continue;
      const key = norm(row.quote);
      if (key.length < minQuoteChars(ctx.contract)) continue;
      if (!quoteChapters.has(key)) quoteChapters.set(key, new Set());
      quoteChapters.get(key).add(row.chapter);
    }
    for (const [key, chapters] of quoteChapters) {
      if (chapters.size < 2) continue;
      problems.push(`同一句话同时充当「${[...chapters].join('」与「')}」两章的答案`
        + `（${key.slice(0, 20)}…）——同一件事只在主位置完整表述一次，`
        + '另一处要么删掉，要么改写成只补它那一章独有的判断');
    }
    if (missingC.length) {
      problems.push(`逐章表缺 ${missingC.length} 行（${missingC.slice(0, 3).join('、')}`
        + `${missingC.length > 3 ? ' …' : ''}）——附录之外每章每个维度都要有裁决`);
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

  mark('⑧ 术语表实体词守恒');
  // ⑧ 术语表实体词守恒：spec §0 术语映射表里、权威模块落在 in_scope 的那些词须在 story 出现
  //
  // 术语表混着两类词：**需求实体**（业务对象的名字，story 就该出现）与**工程消歧用词**
  // （主题色、脱敏这类——spec 拿它们把自然语言映到权威模块，story 用业务语言表达同一事实
  // 才是对的）。一视同仁地要求逐词出现，会让 story 越写人话越容易被判「丢了事实」。
  // 分流键取表内的「所属层」列：归属平台能力层的属工程消歧用词，不要求出现。
  const specText = ctx.offline ? null : readText(path.join(ctx.featureRoot, 'spec', 'spec.md'));
  if (specText !== null) {
    const lost = missingGlossaryTerms(specText, storyText, ctx.projectRoot);
    if (lost.length) {
      problems.push(`spec 术语映射表里的这些业务实体词在 story 里找不到：${lost.join('、')}`
        + '——可整合、可改序、可换措辞，但不能少');
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
    const identifiers = [];
    for (const u of doc.units) {
      for (const t of u.tokens ?? []) {
        if (isEngineeringIdentifier(t, ownIds)) identifiers.push(t);
      }
    }
    const hits = scanLanguageRedline(storyText, {
      appendixTitle: appendix?.title,
      ruleIds: doc.units.filter(u => u.kind === 'knowledge').map(u => u.tokens[0]),
      identifiers,
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

  mark('⑪ 可读性');
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
      duplicate_table_row: '表里重复的行',
    };
    for (const [kind, list] of byKind) {
      const sample = list.slice(0, 3).map(h => `${h.line} 行 ${h.detail}`).join('，');
      problems.push(`${label[kind] ?? kind} ${list.length} 处（${sample}`
        + `${list.length > 3 ? ' …' : ''}）——${list[0].hint}`);
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
      // 就挤到表后面成段（实测一份产物 A/B/C 三节表后各挂两三段）。
      // 「不涉及：<依据>」独行豁免：那是空节规则的既有形态，不算散文段。
      if (appendixDef.subsection_form) {
        // 判的是**尾巴**：开头那一句是目的句（该有的），跟在表或列表后面的那些，
        // 是没地方去的工程细节挤出来的。
        //
        // **材料清单那一节例外，逐块判**：它成的是列表不是表，而上一版只看
        // 「列表之后」，于是列表**之前**成了不设防区——实测一轮，四张图连同
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
    // 于是只剩一个去处——它讲的那一章。落点判做不到这件事：图片单元的落点是按
    // 「在哪被引用」反推的，图放哪儿落点就跟到哪儿，那条判据对放错位置恒真。
    const inAppendix = [...appendixSection.text.matchAll(/!\[[^\]]*\]\(([^)\s]+)/g)]
      .map(m => m[1]);
    if (inAppendix.length) {
      problems.push(`「${appendixDef.title}」里有 ${inAppendix.length} 张图`
        + `（${inAppendix.slice(0, 3).join('、')}${inAppendix.length > 3 ? '…' : ''}）`
        + '——图片放它讲的那一章，跟着讲它的那句话走；'
        + `${appendixDef.title}是查阅件，读者不会为了看一张图翻到这里来`);
    }
  }

  mark('⑫b 正文章节级形态');
  // ⑫b 正文章的节级形态：必有的小节在不在、该分节的章分没分
  //
  // **为什么要有它**：两轮四份产物、零例外——有 check 判据的形态全达成，
  // 只有模板占位与注释的形态全不达成（附录五节全中、03 章三小节全中；
  // 而 04/05/09 的节级只写在注释里，两份产物全部平铺成散文）。
  // 节级正是信息架构的精华：一条恢复支线一节、关键取舍一节、回退设计一节，
  // 读者按节回找；压成一坨散文，他只能从头读到尾。
  //
  // **只有三条，不加码**：必有的小节在不在、有已定决策时取舍成没成节、
  // 该分节的章有没有分节。「每章几节」这种配额一律不设——配额逼出来的是凑数的小标题。
  for (const chapter of ctx.contract.chapters ?? []) {
    if (chapter.appendix) continue;                 // 附录的小节枚举由 ⑫ 管
    const body = sectionText.get(chapter.title);
    if (body === undefined) continue;               // 章缺失由 ① 报，这里不重复
    // 空章豁免：正文恰是那一句，它已明说这件事不在本需求里，节级形态也就无从谈起
    if (norm(body) === norm(EMPTY_SECTION_TEXT)) continue;
    const present = new Set(subsectionNames(body).map(s => s.name));
    const settled = (Array.isArray(decisions?.decisions) ? decisions.decisions : [])
      .filter(d => d?.status === 'settled').length;
    const required = [
      ...(chapter.section_required ?? []),
      ...(settled ? (chapter.section_required_with_settled_decisions ?? []) : []),
    ];
    for (const want of required) {
      if (present.has(normalizeHeading(want))) continue;
      problems.push(`「${chapter.title}」缺「${want}」这一节`
        + `——${chapter.section_note ?? '这一节是本章的必答内容'}`);
    }
    const min = Number(chapter.min_sections) || 0;
    if (min && present.size < min) {
      problems.push(`「${chapter.title}」只有 ${present.size} 个小节（至少 ${min} 个）`
        + `——${chapter.section_note ?? '这一章要分节，读者按节回找'}`);
    }
  }

  mark('⑫e 固定形式');
  // ⑫e 固定形式：该固定的那几个位置，表头由数据锁死，模型只填格子
  //
  // **为什么锁到列**：术语、关键取舍、风险、受限与异常、验收——这五处的形式是确定性的，
  // 效果定义已示范、模板已写明，两轮四份产物照样违反（取舍写成两段散文、受限与异常混成一张表、
  // 验收全 bullet、术语章整段散文）。规律与编号那件事同根：**确定性的形式写在注释里
  // 就是自由发挥区**，只有变成机器动作或判据才存在。
  //
  // **锁的是「本来就该是表的位置」，不是鼓励表格**：背景、方案叙述、流程图文、功能行为、
  // 交付路径一条表格类判据都不加——能一句话说清的仍然不建表，那一面归裁决面的贴合维。
  for (const chapter of ctx.contract.chapters ?? []) {
    const spec = chapter.section_form;
    if (!spec) continue;
    const body = sectionText.get(chapter.title);
    if (body === undefined) continue;
    if (norm(body) === norm(EMPTY_SECTION_TEXT)) continue;      // 空章豁免
    for (const [where, want] of Object.entries(spec)) {
      if (where === '__two_tables__') {
        const heads = tableHeadersOf(body);
        for (const columns of want) {
          if (!heads.some(h => headerMatches(h.columns, columns))) {
            problems.push(`「${chapter.title}」缺一张表头为「${columns.join(' / ')}」的表`
              + '——两类分开列：设计内的受限结果与真正的失败混在一张表里，'
              + '读者分不清哪些要处理、哪些本来就是这么设计的');
          }
        }
        continue;
      }
      if (where === '__each_h3__') {
        for (const sub of subsectionNames(body)) {
          const inner = subsectionText(body, sub.name);
          if (inner === null || /不涉及[:：]\s*\S/.test(inner)) continue;
          if (!tableHeadersOf(inner).some(h => headerMatches(h.columns, want.columns))) {
            problems.push(`「${chapter.title}·${sub.raw}」不是一张表头为`
              + `「${want.columns.join(' / ')}」的表——组名自拟，形态固定：`
              + '一条一行、编号独立、通过条件可观察；写成 bullet 就没法逐条比对');
          }
        }
        continue;
      }
      const scope = where === '__chapter__' ? body : subsectionText(body, where);
      if (scope === null) continue;                 // 缺节由 ⑫b 报，这里不重复
      if (/不涉及[:：]\s*\S/.test(scope)) continue;
      if (want.columns
          && !tableHeadersOf(scope).some(h => headerMatches(h.columns, want.columns))) {
        problems.push(`「${chapter.title}${where === '__chapter__' ? '' : '·' + where}」`
          + `要的是一张表头为「${want.columns.join(' / ')}」的表`
          + '——这几列是固定的，内容填进格子里；写成散文，逐项比对的那几列就没了');
      }
      const budget = Number(want.prose_budget);
      if (Number.isFinite(budget)) {
        const prose = proseBlocks(scope).filter(p => !/不涉及[:：]\s*\S/.test(p.text));
        if (prose.length > budget) {
          problems.push(`「${chapter.title}${where === '__chapter__' ? '' : '·' + where}」`
            + `表外有 ${prose.length} 段正文（至多 ${budget} 段）`
            + '——该进表的内容写进表里，别在表外另起一段');
        }
      }
    }
  }

  mark('⑫c 形态 lint');
  // ⑫c 形态 lint：图的承接、材料清单的行形态
  //
  // 两条此前都只写在模板注释里，实测一条都没达成。判的是形态不是内容：
  // 承接句写得好不好归裁决者，这里只问「图前有没有那一句、材料能不能定位」。
  // 图题编号与小节编号已归 `number` 机器铺，不再判。
  for (const h of scanImageForm(storyText)) {
    // 悬空指图点的是**那句话**，不是图——「第 N 行的图」会让人去那一行找一张不存在的图
    problems.push(h.kind === 'image_dangling'
      ? `第 ${h.line} 行写着「${h.hit}」，附近却没有图——${h.hint}`
      : `第 ${h.line} 行的图不合形态——${h.hint}`);
  }
  {
    const appendix = appendixChapter(ctx.contract);
    const name = materialSubsectionName(ctx.contract);
    const span = appendix && name ? subsectionSpan(storyText, appendix.title, name) : null;
    if (span) {
      const body = storyText.split(/\r?\n/).slice(span.start, span.end).join('\n');
      // 链接按「相对 story.md 解析后落在需求目录的哪一段」判：`../RR/prd.md` 是 RR，
      // 裸文件名是 story 自己那一层（归档件本身所在的目录），不判。
      for (const h of scanMaterialList(body, span.start + 1,
        { allowDirs: ctx.contract.material_dirs ?? [] })) {
        problems.push(`「${appendix.title}·${name}」第 ${h.line} 行——${h.hint}`);
      }
      // 链接得能点开 —— 只在线上判，因为只有线上才知道那份文件在不在。
      //
      // 实测的失效形态：E 节写 `[RR/prd.md](RR/prd.md)`。story.md 在 AR/ 下，
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
    }
  }
  // 小节编号不在这里判：它由 `number` 命令统一铺（D1）。机器保证的形态再设一条
  // 判据，判的是自己的输出——真正会漏的是机器不做的那部分。

  mark('⑫d 统稿留痕');
  // ⑫d 统稿留痕：`copyedit.md` 恰好六行，一项自查一行
  //
  // 统稿（通读全篇、收重复收承接收样式）是唯一一步没有任何产物的动作，于是跳过它
  // 零成本——实测两份产物都有「同一件事讲三遍」「图题一章一个样」这类只有通读才看得见
  // 的毛病，而门禁全绿。留痕不是为了核内容（内容真不真由裁决面与抽样人核管），
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
  process.stdout.write(
    `[story-build check] 通过：${sections.length} 章、${doc.units.length} 个来源单元`
    + `（机器核实 ${doc.units.length - authorPlaced.length} 条、模型裁决 ${authorPlaced.length} 条）\n`);
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
  const after = renumberStory(before, ctx.contract.chapters ?? []);
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
// build：渲染 review.md（机器区重算、人工区逐字节保留）
// --------------------------------------------------------------------------

function cmdBuild(ctx) {
  const decisions = readJson(ctx.decisionsPath, null);
  if (!decisions) fail(`缺 ${ctx.decisionsPath}——先跑 init 建骨架`);
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
  else if (args.command === 'audit') cmdAudit(ctx);
  else if (args.command === 'check') cmdCheck(ctx);
  else if (args.command === 'number') cmdNumber(ctx);
  else cmdBuild(ctx);
}

// 直接跑才执行命令；被 import 时只导出判定函数（正面校准要拿句边界判把一份文档
// 逐句灌一遍，那件事不该经由一个需要完整需求目录的命令行去做）。
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}

export { normQuote, quoteBounds };
