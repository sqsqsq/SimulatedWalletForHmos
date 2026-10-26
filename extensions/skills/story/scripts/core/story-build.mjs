/**
 * story 的登记、核对与校验 —— 十个命令，围绕**一份文档写成**这件事。
 *
 * ## 成文怎么走
 *
 * 设计输入交出、蓝图准入且评审投影有效之后，`skeleton` 给出成文要用的当前输入并建写作设计空壳与章草稿；
 * 作者先写本需求的写作设计骨架，再照骨架一次写一章、经 `chapter` 原子替换落盘，
 * 十章写完再按回看清单逐条处置。每步输出有界、写完即落盘、断了能续——整篇一次重出是全有或全无，
 * 中途断了磁盘上什么都没有。
 *
 * ## 判据的边界
 *
 * 这里只判**确定性不变量**：章标题与顺序、编号、附录结构、图片身份与落点、
 * 语言红线、决策登记字段、材料清单形态、登记之后改过没有。凡是要读懂内容才判得了的
 * ——讲清没讲清、贴不贴合、图题说的是不是这张图——都不在这里，归 verifier 的
 * 语义判据与真实结果观察。用字符串近似语义，模型只会照着字符串改。
 *
 * ## 十个命令
 *
 * | 命令 | 做什么 |
 * |------|--------|
 * | `skeleton` | 预检流程与材料；建决策登记骨架、写作设计空壳、十章骨架（每章一个稳定章锚 + 一个待写 marker）与章草稿，给出当前输入 |
 * | `chapter` | 把一章的内容原子替换进 story.md，其余字节不动 |
 * | `project` | 附录机器区按当前真源（当前蓝图、冻结的设计输入）重投 |
 * | `check` | 上面那几条确定性不变量 |
 * | `build` | 由 `decisions.json` 渲染 `review.md`（机器区重算、人工区逐字节保留） |
 * | `number`| 给 `story.md` 重编号：章序按合同、小节序按出现顺序、图题按全篇顺序 |
 * | `basis` | 输出这一刻的成文依据（设计引用、冻结输入、知识摘要），登记与路由用它 |
 * | `review`| 独立人读审查：`--action prepare` 定稿并准备原生审查请求，`--action check` 核这一次的审查结果 |
 * | `view` | 正式图的两种形态：`--mode prepare` 给未管理的 Mermaid 图建源（`--id` 从源重建一块），`mermaid` 按源重铺，`svg` 把验收成立的图换成同 ID 的增强 SVG，`toggle` 一键切换；`status` 列每张图的增强进度，`review-request` / `review-check` 生成与核对 SVG 验收 |
 * | `archive` | 唯一的归档入口：交付门 → 取外部当前内容 → 发布前核 → 对接层上传与读回 → 核回执 → 登记归档态 |
 *
 * 除 `view` 外的命令都由最外层一次持有视图：动手前回到正式形态（正式的编号、登记、核对、交付与上传只认它），
 * 结束或失败后恢复可用的增强 SVG；被它调起的子命令（环境变量 `STORY_VIEW_OWNER`）不各自恢复。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { flowProblems } from './flow/check.mjs';
import {
  normalizeHeading, pendingChapters, pendingMark, renumberStory, storySections,
} from './story/document.mjs';
import { writeDrafts } from './story/drafts.mjs';
import {
  CommandFailure, createContext, fail, isSystemRequirement, readJson, readText,
} from './story/context.mjs';
import { attachDesignReview, designGaps, projectAppendix } from './story/appendix.mjs';
import { currentBasis, designSource, termFacts } from './story/design-source.mjs';
import {
  discloseInStory, pendingDisclosure, preparedRecord, prepareReview, reviewResult, waiverCheck,
} from './story/independent-review.mjs';
import {
  materialsNotReady, missingSourceLine, relFromFeature, sourceStatus,
} from './story/sources.mjs';
import { cmdBuild, manualContent, registrationGap } from './story/review.mjs';
import { cmdChapter, nextSteps } from './story/chapter.mjs';
import { cmdCheck, storyCheck } from './story/check.mjs';
import { readWritingPlan, writingPlanShell } from './story/writing-plan.mjs';
import { storyInputs } from './story/story-inputs.mjs';
import {
  ensureMermaid, readingWork, reviewCheck, reviewRequest, switchView, VIEW_MODES, writeLauncher,
} from './story/figure-view.mjs';
import { runPython, VIEW_OWNER, viewOwnerKey } from './flow/client.mjs';
import { extensionRoot } from '../../../../hooks/shared/paths.mjs';

const REVIEW_ACTIONS = ['prepare', 'check', 'waiver-check', 'manual'];
/** 命令与它做什么、要哪些命令参数（必需的写在 need）；解析与帮助读同一张表。无原型：只认表里自己的键。 */
const COMMANDS = Object.assign(Object.create(null), {
  skeleton: { what: '预检流程、材料、设计来源与决策登记，全过才建写作设计空壳、十章骨架与章草稿，并给出当前输入与下一步' },
  chapter: { what: '把草稿里的一章原子替换进 AR/story.md，其余章一个字节不动', need: ['--chapter', '--from'] },
  project: { what: '附录机器区按当前真源（蓝图、冻结的设计输入）重投' },
  number: { what: '给 AR/story.md 重编号：章序按合同，小节与图题按出现顺序' },
  check: { what: '只读核对确定性不变量；加 --deliver 判能不能交付，加 --registering 按登记前口径核', opts: ['--deliver', '--registering'] },
  build: { what: '由 decisions.json 渲染 AR/review.md（人工区逐字节保留）' },
  basis: { what: '输出这一刻的成文依据（一行 JSON），登记与路由用它' },
  review: { what: `独立人读审查（--action ${REVIEW_ACTIONS.join('|')}）`, need: ['--action'], opts: ['--report-dir'] },
  view: { what: `切换、准备、查看或验收图的形态（--mode ${VIEW_MODES.join('|')}）`, need: ['--mode'], opts: ['--id'] },
  archive: { what: '交付门 → 取外部当前内容 → 发布前核 → 对接层上传与读回 → 核回执 → 登记归档态（只用于需求系统单）',
    need: ['--mcp-token'], opts: ['--reply'] },
});
/** 选项：值的写法与作用；值以 -- 开头时写成 `--选项=值`。 */
const OPTIONS = Object.assign(Object.create(null), {
  '--feature': ['<需求名>', '需求目录名（doc/features/<需求名>）'],
  '--project-root': ['<路径>', '工程根，不给时按入口所在工程'],
  '--chapter': ['<章名>', '要替换的章，按章节合同的章名'],
  '--from': ['<文件>', '这一章的正文文件（草稿）'],
  '--deliver': [null, '交付门：在 check 之上再核登记、依据与独立审查结果'],
  '--registering': [null, '登记前核：story_flow.py story 登记时用'],
  '--action': ['<动作>', '审查动作'],
  '--report-dir': ['<项目相对路径>', '审查报告写到哪个目录（不给时按宿主约定）'],
  '--mode': ['<模式>', '图的形态或动作'],
  '--id': ['<图块 ID>', '只作用于这一块图'],
  '--mcp-token': ['<token>', '对接层访问需求系统用，不打印'],
  '--reply': ['<原话>', '人看过外部改动、确认仍要覆盖时的原话，逐字'],
});
const KEY = { '--project-root': 'projectRoot', '--mcp-token': 'token', '--report-dir': 'reportDir' };
const SCRIPT = 'node doc/extensions/skills/story/scripts/core/story-build.mjs';

function usage(command) {
  if (!COMMANDS[command]) {
    return [`用法: ${SCRIPT} <命令> --feature <需求名> [--project-root <路径>] [命令参数]`, '命令:',
      ...Object.entries(COMMANDS).map(([c, d]) => `  ${c.padEnd(9)}${d.what}`),
      `各命令的参数: ${SCRIPT} <命令> --help`].join('\n');
  }
  const { what, need = [], opts = [] } = COMMANDS[command];
  const line = (o, req) => `  ${o}${OPTIONS[o][0] ? ` ${OPTIONS[o][0]}` : ''}${req ? '  必需' : ''}  ${OPTIONS[o][1]}`;
  return [`用法: ${SCRIPT} ${command} --feature <需求名> ${need.map(o => `${o} ${OPTIONS[o][0]}`).join(' ')}`.trimEnd()
      + ` [--project-root <路径>]${opts.map(o => ` [${o}${OPTIONS[o][0] ? ` ${OPTIONS[o][0]}` : ''}]`).join('')}`,
    what, '参数:', line('--feature', true), ...need.map(o => line(o, true)), line('--project-root'),
    ...opts.map(o => line(o)), '值以 -- 开头时写成 --选项=值；参数含空格或引号时按所用 shell 的规则加引号'].join('\n');
}

/**
 * 解析在任何动作之前完成：未知选项、重复、缺值、不适用于这个命令、缺必需项都在这里报，
 * 什么都不执行——拼错 `--deliver` 不会悄悄跑成普通 check。错误只点选项名，不回显值。
 */
function parseArgs(argv) {
  const command = argv[2] ?? '';
  const rest = argv.slice(3);
  if (command === '--help' || command === '-h' || rest.includes('--help') || rest.includes('-h')) {
    return { help: usage(command) };
  }
  if (!COMMANDS[command]) fail(`不认识的命令${command ? '' : '（没给）'}——${usage('')}`);
  const { need = [], opts = [] } = COMMANDS[command];
  const allowed = new Set(['--feature', '--project-root', ...need, ...opts]);
  const args = { command };
  const seen = new Set();
  const bad = (why) => fail(`${command}：${why}——用法见 \`${SCRIPT} ${command} --help\``);
  for (let i = 0; i < rest.length; i++) {
    const [name, inline] = rest[i].startsWith('--') && rest[i].includes('=')
      ? [rest[i].slice(0, rest[i].indexOf('=')), rest[i].slice(rest[i].indexOf('=') + 1)] : [rest[i], undefined];
    if (!OPTIONS[name]) bad(name.startsWith('-') ? `不认识的选项 ${name}` : `第 ${i + 1} 个参数不属于任何选项`);
    if (!allowed.has(name)) bad(`${name} 不用于 ${command}`);
    if (seen.has(name)) bad(`${name} 给了两次`);
    seen.add(name);
    const key = KEY[name] ?? name.slice(2);
    if (OPTIONS[name][0] === null) {
      if (inline !== undefined) bad(`${name} 不带值`);
      args[key] = true;
    } else if (inline !== undefined) {
      if (!inline) bad(`${name}= 后面缺值`);
      args[key] = inline;
    } else if (i + 1 >= rest.length || rest[i + 1].startsWith('--')) {
      bad(`${name} 后面缺值（值以 -- 开头时写成 ${name}=<值>）`);
    } else {
      args[key] = rest[++i];
    }
  }
  const missing = ['--feature', ...need].filter(o => !seen.has(o));
  if (missing.length) bad(`缺 ${missing.join('、')}`);
  return args;
}

/**
 * 编号由机器铺，作者只写业务名标题与图题。
 *
 * 幂等：已经对的文件重跑一个字节都不改，所以放在登记步跑第二遍也无副作用。
 */
function cmdNumber(ctx) {
  const before = readText(ctx.storyPath);
  if (before === null) fail(`AR/story.md：不在（${ctx.storyPath}）——编号作用在 skeleton 建出的 story 上`);
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
 * 附录机器区按当前真源重投。登记之后蓝图升了 revision，直接重跑 `story_flow.py story`：
 * 它先重投再登记，一步跟上。
 */
function cmdProject(ctx) {
  const story = readText(ctx.storyPath);
  if (story === null) fail('AR/story.md：不在——骨架由 skeleton 建，附录机器区投在它的附录章里');
  const { text, zones } = projectAppendix(ctx, story);
  if (text !== story) fs.writeFileSync(ctx.storyPath, text, 'utf-8');
  process.stdout.write(`[story-build project] 附录机器区按当前真源重投 ${zones} 节`
    + '（当前蓝图 / 冻结的设计输入）；机器区外的说明归你，不动\n');
}

/**
 * 这一刻的成文依据（设计引用、冻结输入、知识摘要）输出成一行 JSON：`story_flow.py story` 登记时写进流程契约，
 * 流程路由拿它核登记之后换没换。设计来源不成立时照实失败。
 */
function cmdBasis(ctx) {
  const basis = currentBasis(ctx);
  if (basis.problems.length) fail(`设计来源不成立，成文依据取不到：\n  · ${basis.problems.join('\n  · ')}`);
  const { problems, ...rest } = basis;
  process.stdout.write(`${JSON.stringify(rest)}\n`);
}

/**
 * 独立人读审查（`story/independent-review.mjs`）。
 *
 * - `prepare`：先把审查对象定成最终版——正式图建源、附录重投、编号、渲染 Review，全篇结构检查通过——再写审查任务，
 *   给出材料键与这一份回复的位置；同一份材料已有有效通过的报告时给出原位置（reused）。
 * - `check`：只读核这一次的审查报告，输出一行 JSON（`result`、`detail`），pass / warn / unreviewed 退出 0，其余退出 1。
 *   登记与交付门消费同一个结果。
 * - `waiver-check`：只读，给 `story_flow.py unreviewed` 记授权之前核宿主能力与这一版的审查结果，一行 JSON。
 * - `manual`：评审记录里人写过的内容（写过字的议题、自由意见区），一行 JSON。
 */
function cmdReview(ctx) {
  if (!REVIEW_ACTIONS.includes(ctx.args.action)) fail(`review 要 --action ${REVIEW_ACTIONS.join('|')}`);
  if (ctx.args.action === 'manual') {
    // 评审记录里人写过的内容（update 撤回判 Review 能不能动）：一行 JSON
    process.stdout.write(`${JSON.stringify(manualContent(readText(ctx.reviewPath) ?? ''))}\n`);
    return;
  }
  if (ctx.args.action === 'check') {
    const out = reviewResult(ctx);
    process.stdout.write(`${JSON.stringify(out)}\n`);
    process.exitCode = ['pass', 'warn', 'unreviewed'].includes(out.result) ? 0 : 1;
    return;
  }
  if (ctx.args.action === 'waiver-check') {
    process.stdout.write(`${JSON.stringify(waiverCheck(ctx))}\n`);
    return;
  }
  // 准备记录坏了是输入故障：在定稿写盘之前停下，现场不动
  const before = preparedRecord(ctx);
  if (before.error) fail(before.error);
  pendingDisclosure(ctx);
  // 正式图都有图源（未管理的 Mermaid 图建 .mmd 源），审查与归档读到的是同一套图
  const figures = switchView(ctx.featureRoot, 'prepare');
  if (figures.problems.length) fail(`正式图建源没有成立，审查对象还没成形：\n  ${figures.problems.join('\n  ')}`);
  cmdProject(ctx);
  cmdNumber(ctx);
  cmdBuild(ctx);
  discloseInStory(ctx);
  attachDesignReview(ctx);
  const { problems } = storyCheck(ctx, { registration: false });
  if (problems.length) fail(`结构检查没过，审查对象还没成形——先按 \`story-build check\` 的报错改：\n  · ${problems.join('\n  · ')}`);
  const out = prepareReview(ctx, ctx.args.reportDir);
  if (out.error) fail(out.error);
  process.stdout.write(`${JSON.stringify({ material_key: out.material_key, task: out.task, report_dir: out.report_dir,
    report_file: out.report_file, reused: out.reused, materials: out.rows.length,
    dispatch_file: out.dispatch_file, dispatch_text: out.dispatch_text })}\n`);
  process.stdout.write(out.reused
    ? `[story-build review] 这份材料已有通过的报告（${out.report_file}），不用重审，直接 check。\n`
    : [`[story-build review] 审查已准备：把 ${out.dispatch_file}（即输出里的 dispatch_text）原样作为宿主隔离子代理的任务交给审查者，`,
      `  不增删、不改写；等它完成，把它的最终回复全文原样写到 ${out.report_file}（审查者只读，不自己写文件）。之后跑 story-build review --action check，`,
      '  结果的处置见 phases/design.md「五、独立审查、登记与交付」。', ''].join('\n'));
}

/**
 * 起手：十章骨架 + 每章一份草稿。
 *
 * **预检全部读完、判完、算完，才开始写盘**。顺序不是风格问题：一边建决策骨架一边
 * 才发现设计来源还不成立的话，盘上留下的是半份起手，而作者拿到的报错说的是另一件事——
 * 他要先弄清哪些已经建了，才知道重跑安不安全。
 *
 * 互不依赖的几组前置一次核完、一起报：作者补一个跑一次才知道下一个，是白跑。
 * 依赖缺口的那几组不判、明说没判，不拿缺口推出来的伪错误凑数。
 */
function skeletonPreflight(ctx) {
  const problems = [];
  const skipped = [];
  // ① 流程走到位了没有
  const flow = readJson(path.join(ctx.srcDir, 'story-flow.json'), null);
  const flowGaps = flowProblems(ctx.featureRoot);
  if (flowGaps.length) problems.push(...flowGaps);
  else if (!flow) {
    problems.push('AR/story-src/story-flow.json：不存在，本需求还没走过 /story 的 S1–S3'
      + '——流程契约由 `story_flow.py init` 起单、按关卡收口时写成，story 骨架在范围收口之后起');
  } else if (flow.status !== 'complete' && flow.status !== 'story_written') {
    problems.push(`AR/story-src/story-flow.json：status 是 ${flow.status}，本轮还没有收口——story 骨架在 complete 或 story_written 时起，当前动作由 \`story_flow.py status\` 给出`);
  }
  // ② 材料：清单在、与本轮基准一致、且磁盘现状仍是这批料（基准在流程契约里）
  const manifest = readJson(path.join(ctx.srcDir, 'materials.json'), null);
  if (!manifest) {
    problems.push('AR/story-src/materials.json：不存在或读不出——材料清单由 `story_flow.py round` 生成');
  } else if (problems.length) {
    skipped.push('材料清单与本轮基准是否一致、原件导没导、材料变没变（要先有收口的流程契约）');
  } else if (manifest.digest !== (flow.rounds?.at(-1)?.materials ?? {}).digest) {
    problems.push('AR/story-src/materials.json：digest 与 story-flow.json 本轮登记的材料基准对不上——两者都由 `story_flow.py round` 按磁盘现状写入，骨架按本轮基准起');
  } else {
    const notReady = materialsNotReady(ctx);
    if (notReady) problems.push(`材料还不能起稿：${notReady}`);
  }
  // ③ 来源必需性（与交付前的 check 同一份判定）
  const { docs, missing, blocking } = sourceStatus(ctx);
  if (!docs.length) {
    problems.push(`一份材料都读不到（合同 sources 指向 ${Object.values(ctx.contract.sources ?? {})
      .map(x => (typeof x === 'string' ? x : x?.path)).filter(Boolean).join('、')}）——骨架据合同 sources 声明的材料起`);
  } else if (blocking.length) {
    problems.push(`必备来源缺失：${blocking.map(m => missingSourceLine(m)).join('；')}`);
  }
  // ④ 设计来源成立：蓝图、有效的评审投影、登记的冻结输入
  const gaps = designGaps(ctx);
  if (gaps.length) problems.push(`设计来源或附录投影还不成立：\n  · ${gaps.join('\n  · ')}`);
  // ⑤ 决策登记起手前就有议题，或写明本单无待决（只读）
  const gap = registrationGap(ctx);
  if (gap) problems.push(gap);
  if (problems.length) {
    fail(`起手预检没过，骨架没起，Story、草稿与写作设计都没写：\n${problems.map((p, i) => `${i + 1}. ${p}`).join('\n')}`
      + (skipped.length ? `\n没判（依赖上面的缺口，补齐后重跑 skeleton 再核）：\n${skipped.map(s => `  · ${s}`).join('\n')}` : ''));
  }
  return { docs, missing };
}

function cmdSkeleton(ctx) {
  const { docs, missing } = skeletonPreflight(ctx);

  // ---- 内容计算：也在写盘之前 ----
  const facts = { terms: termFacts(designSource(ctx).blueprint) };
  const existing = readText(ctx.storyPath);
  const chapterState = existing === null
    ? { hasStory: false, written: new Map(), pending: new Set() }
    : {
        hasStory: true,
        written: new Map(storySections(existing).map(s2 => [normalizeHeading(s2.title), s2.text])),
        pending: new Set(pendingChapters(existing).map(normalizeHeading)),
      };

  // ---- 预检全过，开始写盘 ----
  // 写作设计不是预检：它还是空壳时起手照走，只是下一步变成先写它。
  const hadPlan = fs.existsSync(ctx.templatePath);
  if (!hadPlan) fs.writeFileSync(ctx.templatePath, writingPlanShell(ctx.contract), 'utf-8');
  const plan = readWritingPlan(ctx);
  const { made, seeded, starts } = writeDrafts(ctx, facts, chapterState, plan);

  let result;
  if (existing !== null) {
    // **不覆盖**：起手动作重跑是恢复，不是重置键。RESULT 只写这一次真做过的事——
    // 说成「建好了骨架」，作者会以为盘上的章没了。
    result = `AR/story.md 已存在，未改动；`
      + `${made.length ? `补建草稿 ${made.length} 份（已写完的章按现稿补回，可直接改）`
        : '草稿齐备，一份未覆盖'}`;
  } else {
    // 大标题「编号 需求名」：名称取自需求详情；本地单没有详情，只写编号，下面的接续提示作者补名称
    const title = String(readJson(path.join(ctx.featureRoot, 'AR', 'detail.json'), {})?.title ?? '').trim();
    const body = [`# ${path.basename(ctx.featureRoot)}${title ? ` ${title}` : ''}`, ''];
    for (const ch of ctx.contract.chapters) {
      body.push(`## ${ch.title}`, '', pendingMark(ch.title), '');
    }
    fs.mkdirSync(path.dirname(ctx.storyPath), { recursive: true });
    fs.writeFileSync(ctx.storyPath, `${body.join('\n').trimEnd()}\n`, 'utf-8');
    result = `${ctx.contract.chapters.length} 章骨架 + ${made.length} 份章草稿`
      + '（`AR/story-src/drafts/`，每份开头是读者读完这一章要能回答的问题与必要种子）；'
      + '附录里配置、埋点由 project 从真源投影，接口、数据、规约与材料清单由你写';
  }
  if (!hadPlan) result += `；写作设计空壳 ${relFromFeature(ctx, ctx.templatePath)}`;
  if (seeded.length) result += `；按写作设计骨架给 ${seeded.length} 份没动过的草稿铺好小节与表图`;
  // 首屏接续与 chapter 共用一处：各写一份的话，恢复那条路上的提示总比正常路径旧一轮。
  // 刚建的空壳不逐条报占位——下一步就是写它；已有的设计读不了才把缺在哪列出来。
  const current = readText(ctx.storyPath) ?? '';
  const bare = current.split(/\r?\n/, 1)[0].trim() === `# ${path.basename(ctx.featureRoot)}`;
  process.stdout.write(nextSteps(ctx, current, result, {
    warnings: [...missing.map(m => missingSourceLine(m)), ...(hadPlan ? plan.problems : []),
      ...(bare ? [`大标题只有需求编号，还缺需求名：直接改 AR/story.md 第 1 行，写成 \`# ${path.basename(ctx.featureRoot)} <需求名>\`；大标题不在任何章里，不经 chapter 提交`] : [])],
    plan, docs,
  }));
  for (const { file, rows } of starts) {
    process.stdout.write(`\n结构起点：${relFromFeature(ctx, file)} 已经动过，没有自动改；`
      + `写作设计选定、它里面还没有的结构如下，按需贴进去：\n${rows.join('\n')}\n`);
  }
  // 成文要用的当前输入在这一刻取：材料、采用来源与蓝图里的图此刻列得出来。
  process.stdout.write(`\n${storyInputs(ctx).join('\n')}\n`);
}

/** `view`：准备正式图、在 Mermaid 与增强 SVG 之间切换，查看或验收它们，结果与缺口原样报出。 */
function cmdView(ctx) {
  const { mode, id = '' } = ctx.args;
  if (!VIEW_MODES.includes(mode)) fail(`view 要 --mode ${VIEW_MODES.join('|')}`);
  if (mode === 'status') {
    process.stdout.write(`${JSON.stringify(readingWork(ctx.featureRoot), null, 2)}\n`);
    return;
  }
  if (mode === 'review-request' || mode === 'review-check') {
    if (!id) fail(`view --mode ${mode} 要 --id <正式图 ID>`);
    if (mode === 'review-check') {
      const r = reviewCheck(ctx.featureRoot, id);
      if (r.state !== 'ready') fail(`图 ${id} 的增强 SVG 验收没有成立（${r.state}）：${r.reason}`);
      process.stdout.write(`[story-build view] 图 ${id} 的增强 SVG 验收成立（源码文本审查完成，本结论不含渲染外观验收）：可以用 view --mode svg 显示它\n`);
      return;
    }
    const r = reviewRequest(ctx.projectRoot, ctx.featureRoot, id);
    if (r.problems.length) fail(`图 ${id} 的增强 SVG 验收请求没有生成：\n  ${r.problems.join('\n  ')}`);
    process.stdout.write(`[story-build view] 验收请求 ${r.request.request_id}${r.written ? '已写入' : '没有变化'}\n${r.task.join('\n')}\n`);
    return;
  }
  const r = switchView(ctx.featureRoot, mode, { id });
  if (r.problems.length) fail(`view --mode ${mode} 没有写任何东西：\n  ${r.problems.join('\n  ')}`);
  const launcher = mode === 'prepare' ? writeLauncher(ctx.featureRoot, ctx.contract.local_reading_entry) : null;
  process.stdout.write(`[story-build view] ${mode}：${r.changed ? '已改写 AR/story.md' : 'AR/story.md 没有变化'}；`
    + `正式图 ${r.counts.mermaid + r.counts.svg} 张，其中显示增强 SVG 的 ${r.counts.svg} 张\n`
    + [...r.notes, ...(launcher ? [launcher] : [])].map(n => `  - ${n}\n`).join(''));
}

/** 跑本入口的另一个命令或另一个脚本：参数数组传递、不经 shell，两路输出原样带回。 */
function child(args) {
  const r = spawnSync(process.execPath, args, { encoding: 'utf-8', windowsHide: true });
  return { status: r.status, error: r.error, out: [r.stdout, r.stderr].map(x => String(x ?? '').trim()).filter(Boolean).join('\n') };
}

/** 一段输出里的那个 JSON 对象（对接层回执、story_flow 结果）；读不出时为 null。 */
function jsonIn(text) {
  const s = String(text ?? '');
  try { return JSON.parse(s.slice(s.indexOf('{'), s.lastIndexOf('}') + 1)); } catch { return null; }
}

/**
 * 归档：交付门 → 取外部当前内容 → 发布前核 → 对接层上传并读回 → 核回执 → 登记归档态。
 * 交付门不过零系统调用；外部被别人改过时停在发布前核、不上传（人确认仍覆盖时带 `--reply` 重跑）；回执不全不登记；
 * 远端已成功而本地登记失败时说清已发生的副作用与补登记入口，不自动重传。token 只作参数传给对接层，不打印。
 */
function cmdArchive(ctx) {
  const feature = ctx.args.feature;
  const token = ctx.args.token;
  if (!isSystemRequirement(feature)) fail(`${feature} 是本地需求：本地单没有归档环节，交付终点是仓内三件`);
  const hide = (text) => String(text ?? '').split(token).join('<token>');
  const gate = child([ctx.scriptPath, 'check', '--deliver', '--feature', feature, '--project-root', ctx.projectRoot]);
  if (gate.status !== 0) fail(`交付门没过，没有调用需求系统：\n${gate.out}`);
  // 对接层入口登记在章节合同（相对扩展根），core 只按归档协议调它
  const adapter = path.join(extensionRoot(ctx.projectRoot), ...String(ctx.contract.system_archive_entry ?? '').split('/'));
  if (!ctx.contract.system_archive_entry || !fs.existsSync(adapter)) fail(`章节合同登记的归档对接入口读不到（${adapter}）：对接层由目标仓按所有权维护`);
  const got = child([adapter, 'fetch', feature, token, '--project-root', ctx.projectRoot, '--out', path.join(ctx.featureRoot, 'inbox')]);
  const fetched = jsonIn(got.out);
  if (got.status !== 0 || fetched?.mode !== 'fetch' || fetched?.success !== true) {
    fail(`取外部当前内容没有成立（退出码 ${got.status ?? got.error?.message}），没有上传：\n${hide(got.out)}`);
  }
  const flow = path.join(path.dirname(ctx.scriptPath), 'story_flow.py');
  const base = ['--feature', feature, '--project-root', ctx.projectRoot];
  const pre = runPython(flow, ['publish', ...base, ...(ctx.args.reply ? ['--reply', ctx.args.reply] : [])]);
  const plan = jsonIn(pre.stdout);
  if (pre.error || pre.status !== 0 || !plan) fail(`发布前核没有成立，没有上传：\n${pre.error ?? pre.output}`);
  if (!plan.publishable) {
    fail(`发布前核发现外部改动，没有上传：${plan.action}\n`
      + plan.items.filter(r => r.action === 'conflict').map(r => `  - ${r.item}：外部 ${r.external ?? '不存在'}，基线 ${r.baseline ?? '不存在'}，本地 ${r.local}`).join('\n'));
  }
  const up = child([adapter, 'archive', feature, token, '--project-root', ctx.projectRoot]);
  const receipt = jsonIn(up.out);
  const ok = up.status === 0 && receipt?.mode === 'archive' && receipt?.reqNo === feature
    && ['success', 'verified', 'archived'].every(k => receipt?.[k] === true);
  if (!ok) {
    fail(`对接层上传或读回核验没有成立（退出码 ${up.status ?? up.error?.message}），没有登记归档态；远端状态以对接层的话为准，`
      + `核清后重跑 archive：\n${hide(up.out)}`);
  }
  const reg = runPython(flow, ['archived', ...base]);
  if (reg.error || reg.status !== 0) {
    fail('需求系统已经写入并读回核验通过，本地归档态登记失败——不要重新上传；修好原因后只补登记：'
      + `\`python doc/extensions/skills/story/scripts/core/story_flow.py archived --feature ${feature}\`\n`
      + (reg.error ?? reg.output));
  }
  process.stdout.write(`[story-build archive] 已归档并登记：${feature}（Story、Review、设计附件三件上传并读回核验成立；`
    + `覆盖前的系统正文备份在 ${receipt.backupPath ?? '对接层记录处'}）\n`);
  if (plan.open_topics?.length) process.stdout.write(`[story-build archive] 带着未决议题送审：${plan.open_topics.join('；')}\n`);
  if (plan.unverified?.length) process.stdout.write(`[story-build archive] 未验证项：${plan.unverified.join('；')}\n`);
  // 登记返回的下一步原样带出：本轮还有没做完的工作（如已开始的同图增强）不被归档成功吞掉
  const after = jsonIn(reg.stdout);
  if (after?.next && after.next !== 'done') process.stdout.write(`[story-build archive] 下一步（${after.next}）：${after.action}\n`);
}

/**
 * 最外层持有视图：动手前回到正式形态（图块按源的 Mermaid），结束或失败后恢复当前可用的增强 SVG。恢复失败只补视图，
 * 附在业务结果之后报出来，不遮住原来的错误。同一需求的外层已切入并持有时，子进程不再切入，也不各自恢复。
 */
async function withView(ctx, body) {
  const key = viewOwnerKey(ctx.featureRoot);
  const before = process.env[VIEW_OWNER];
  const owner = before !== key;
  if (owner) process.env[VIEW_OWNER] = key;
  try {
    const back = owner ? ensureMermaid(ctx.featureRoot) : { problems: [] };
    if (back.problems.length) fail(`读 story 之前要先回到正式形态（图块按源的 Mermaid），回不去：\n  ${back.problems.join('\n  ')}`);
    return await body();
  } finally {
    if (owner) {
      if (before === undefined) delete process.env[VIEW_OWNER];
      else process.env[VIEW_OWNER] = before;
      restoreView(ctx);
    }
  }
}

function restoreView(ctx) {
  if (!fs.existsSync(ctx.storyPath)) return;     // 还没有 story：没有可恢复的增强 SVG
  try {
    const r = switchView(ctx.featureRoot, 'svg');
    if (r.problems.length) {
      process.stderr.write(`[story-build] 增强 SVG 没有恢复，story 保持 Mermaid（业务结果不受影响）：\n  ${r.problems.join('\n  ')}\n`);
      return;
    }
    if (r.counts.svg) process.stderr.write(`[story-build] 已恢复 ${r.counts.svg} 张图的增强 SVG\n`);
    if (r.kept.length) {
      process.stderr.write(`[story-build] ${r.kept.length} 张图保持 Mermaid（增强 SVG 未就绪，业务结果不受影响）：`
        + `${r.kept.map(k => k.id).join('、')}——逐张原因与动作见 \`story-build view --mode status\`\n`);
    }
  } catch (e) {
    process.stderr.write(`[story-build] 增强 SVG 恢复时出错（${e?.message ?? e}），story 保持 Mermaid；只补视图：\`story-build view --mode svg\`\n`);
  }
}

async function main() {
  const args = parseArgs(process.argv);
  if (args.help) {
    process.stdout.write(`${args.help}\n`);
    return;
  }
  const ctx = createContext(args);
  if (args.command === 'view') return cmdView(ctx);
  return withView(ctx, async () => {
    if (args.command === 'skeleton') cmdSkeleton(ctx);
    else if (args.command === 'chapter') cmdChapter(ctx);
    else if (args.command === 'project') cmdProject(ctx);
    else if (args.command === 'basis') cmdBasis(ctx);
    else if (args.command === 'review') await cmdReview(ctx);
    else if (args.command === 'check') await cmdCheck(ctx);
    else if (args.command === 'number') cmdNumber(ctx);
    else if (args.command === 'archive') cmdArchive(ctx);
    else if (args.command === 'build') {
      cmdBuild(ctx);
      const launcher = writeLauncher(ctx.featureRoot, ctx.contract.local_reading_entry);
      if (launcher) process.stderr.write(`[story-build] ${launcher}\n`);
    }
  });
}

// 直接跑才执行命令；被 import 时只导出判定函数（正面校准要拿句边界判把一份文档
// 逐句灌一遍，那件事不该经由一个需要完整需求目录的命令行去做）。
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((e) => {
    // 判定没过：原因已经写到 stderr，按 1 结束（finally 已恢复视图）
    if (e instanceof CommandFailure) process.exit(1);
    // 脚本自身的缺陷：原始异常全文带出，并说明这一步没跑完、归谁处理
    process.stderr.write(`[story-build] 脚本自身异常：${e?.stack ?? e}\n——这一步没有执行完，不是产物的问题，归扩展维护者处理\n`);
    process.exit(2);
  });
}

