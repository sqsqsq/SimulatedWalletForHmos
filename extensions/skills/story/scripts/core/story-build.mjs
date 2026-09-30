/**
 * story 的登记、核对与校验 —— 八个命令，围绕**一份文档写成**这件事。
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
 * ## 八个命令
 *
 * | 命令 | 做什么 |
 * |------|--------|
 * | `skeleton` | 预检流程与材料；建决策登记骨架、写作设计空壳、十章骨架（每章一个稳定章锚 + 一个待写 marker）与章草稿，给出当前输入 |
 * | `chapter` | 把一章的内容原子替换进 story.md，其余字节不动 |
 * | `project` | 附录机器区按当前真源（已准入蓝图、冻结的设计输入）重投 |
 * | `check` | 上面那几条确定性不变量 |
 * | `build` | 由 `decisions.json` 渲染 `review.md`（机器区重算、人工区逐字节保留） |
 * | `number`| 给 `story.md` 重编号：章序按合同、小节序按出现顺序、图题按全篇顺序 |
 * | `basis` | 输出这一刻的成文依据（设计引用、冻结输入、知识摘要），登记与路由用它 |
 * | `review`| 独立人读审查：`--action prepare` 定稿并准备原生审查请求，`--action check` 核这一次的审查结果 |
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { flowProblems } from './flow/check.mjs';
import {
  normalizeHeading, pendingChapters, pendingMark, renumberStory, storySections,
} from './story/document.mjs';
import { writeDrafts } from './story/drafts.mjs';
import {
  createContext, fail, readJson, readText,
} from './story/context.mjs';
import { designGaps, materialSubsectionName, projectAppendix } from './story/appendix.mjs';
import { currentBasis, designSource, termFacts } from './story/design-source.mjs';
import { ORIGINAL, prepareReview, reviewResult } from './story/independent-review.mjs';
import {
  materialListSkeleton, materialsNotReady, missingSourceLine, relFromFeature, sourceStatus,
} from './story/sources.mjs';
import { cmdBuild, registrationGap } from './story/review.mjs';
import { cmdChapter, nextSteps } from './story/chapter.mjs';
import { cmdCheck, storyCheck } from './story/check.mjs';
import { readWritingPlan, writingPlanShell } from './story/writing-plan.mjs';
import { storyInputs } from './story/story-inputs.mjs';

const COMMANDS = ['check', 'build', 'number', 'skeleton', 'chapter', 'project', 'basis', 'review'];

function parseArgs(argv) {
  const args = { command: argv[2] && !argv[2].startsWith('--') ? argv[2] : '' };
  for (let i = 3; i < argv.length; i++) {
    if (argv[i] === '--feature') args.feature = argv[++i];
    else if (argv[i] === '--project-root') args.projectRoot = argv[++i];
    else if (argv[i] === '--chapter') args.chapter = argv[++i];
    else if (argv[i] === '--from') args.from = argv[++i];
    else if (argv[i] === '--deliver') args.deliver = true;
    else if (argv[i] === '--registering') args.registering = true;
    else if (argv[i] === '--action') args.action = argv[++i];
    else if (argv[i] === '--report-dir') args.reportDir = argv[++i];
  }
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
    + '（已准入蓝图 / 冻结的设计输入）；机器区外的说明归你，不动\n');
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
 * 独立人读审查，接 Framework 原生的无 Feature review request（`story/independent-review.mjs`）。
 *
 * - `prepare`：先把审查对象定成最终版——附录重投、编号、渲染 Review，全篇结构检查通过——再写审查任务、
 *   生成原生请求并调原生 prepare；给出派审要带的东西。
 * - `check`：核这一次的审查结果，输出一行 JSON（`result`、`detail`），pass / warn 退出 0，其余退出 1。
 *   登记与交付门消费同一个结果。
 */
async function cmdReview(ctx) {
  if (!['prepare', 'check'].includes(ctx.args.action)) {
    fail('用法: story-build.mjs review --action prepare|check --feature <需求名> [--project-root <路径>] [--report-dir <项目相对路径>]');
  }
  if (ctx.args.action === 'check') {
    const out = await reviewResult(ctx);
    process.stdout.write(`${JSON.stringify(out)}\n`);
    process.exitCode = ['pass', 'warn'].includes(out.result) ? 0 : 1;
    return;
  }
  cmdProject(ctx);
  cmdNumber(ctx);
  cmdBuild(ctx);
  const { problems } = storyCheck(ctx, { registration: false });
  if (problems.length) fail(`结构检查没过，审查对象还没成形——先按 \`story-build check\` 的报错改：\n  · ${problems.join('\n  · ')}`);
  const out = await prepareReview(ctx, ctx.args.reportDir);
  if (out.error) fail(out.error);
  process.stdout.write([
    `[story-build review] 审查已准备：对象 ${out.rows.length} 份，请求 request_sha256 ${out.request_sha256}`,
    `  任务：${relFromFeature(ctx, path.join(ctx.srcDir, 'review', 'task.md'))}（待审与只读对照材料在里面分列）`,
    `  报告目录：${out.reportDir}`,
    '派审：用宿主与作者隔离的独立执行能力（子代理）交给审查者，带上任务文件、request_sha256 与报告目录。审查者按任务读全部材料，',
    `  在 ${out.reportDir}/context/facts.md 写原生事实记录，回复一份原生 review 报告（格式见任务「报告怎么写」）。`,
    `回复原样写到 ${out.reportDir}/${ORIGINAL}（一字不改），再跑 story-build review --action check；`
      + '派审与结果的处置见 phases/design.md「五、独立审查、登记与交付」。', '',
  ].join('\n'));
}

/**
 * 起手：十章骨架 + 每章一份草稿。
 *
 * **预检全部读完、判完、算完，才开始写盘**。顺序不是风格问题：一边建决策骨架一边
 * 才发现设计还没准入的话，盘上留下的是半份起手，而作者拿到的报错说的是另一件事——
 * 他要先弄清哪些已经建了，才知道重跑安不安全。
 */
function cmdSkeleton(ctx) {
  // ---- 预检 ①：流程走到位了没有 ----
  const flow = readJson(path.join(ctx.featureRoot, 'AR', 'story-src', 'story-flow.json'), null);
  if (!flow) {
    fail('AR/story-src/story-flow.json：不存在，本需求还没走过 /story 的 S1–S3'
      + '——流程契约由 `story_flow.py init` 起单、按关卡收口时写成，story 骨架在范围收口之后起');
  }
  const flowGaps = flowProblems(ctx.featureRoot);
  if (flowGaps.length) fail(flowGaps.join('\n'));
  if (flow.status !== 'complete' && flow.status !== 'story_written') {
    fail(`AR/story-src/story-flow.json：status 是 ${flow.status}，本轮还没有收口——story 骨架在 complete 或 story_written 时起，当前动作由 \`story_flow.py status\` 给出`);
  }

  // ---- 预检 ②：材料 —— 清单在、与本轮基准一致、且磁盘现状仍是这批料 ----
  const manifest = readJson(path.join(ctx.srcDir, 'materials.json'), null);
  const base = (flow.rounds?.[flow.rounds.length - 1]?.materials) ?? {};
  if (!manifest) {
    fail('AR/story-src/materials.json：不存在——材料清单由 `story_flow.py round` 生成');
  }
  if (manifest.digest !== base.digest) {
    fail('AR/story-src/materials.json：digest 与 story-flow.json 本轮登记的材料基准对不上——两者都由 `story_flow.py round` 按磁盘现状写入，骨架按本轮基准起');
  }
  const notReady = materialsNotReady(ctx);
  if (notReady) fail(`材料还不能起稿：${notReady}`);

  // ---- 预检 ③：来源必需性（与交付前的 check 同一份判定） ----
  const { docs, missing, blocking } = sourceStatus(ctx);
  if (!docs.length) {
    fail(`一份材料都读不到（合同 sources 指向 ${Object.values(ctx.contract.sources ?? {})
      .map(x => (typeof x === 'string' ? x : x?.path)).filter(Boolean).join('、')}）——骨架据合同 sources 声明的材料起`);
  }
  if (blocking.length) {
    fail('必备来源缺失，骨架没起：'
      + blocking.map(m => missingSourceLine(m)).join('；'));
  }

  // ---- 预检 ④：设计来源成立：已准入的蓝图、有效的评审投影、登记的冻结输入 ----
  const gaps = designGaps(ctx);
  if (gaps.length) fail(`设计来源还不成立，骨架没起：\n  · ${gaps.join('\n  · ')}`);

  // ---- 预检 ⑤：决策登记起手前就有议题，或写明本单无待决（只读，不写） ----
  const gap = registrationGap(ctx);
  if (gap) fail(gap);

  // ---- 内容计算：也在写盘之前 ----
  const facts = {
    terms: termFacts(designSource(ctx).blueprint),
    materialListName: materialSubsectionName(ctx.contract),
    materialListRows: materialListSkeleton(ctx),
  };
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
    // 大标题「编号 需求名」：名称取自需求详情；本地单没有详情，作者照 check 的提示补上名称
    const title = String(readJson(path.join(ctx.featureRoot, 'AR', 'detail.json'), {})?.title ?? '').trim();
    const body = [`# ${path.basename(ctx.featureRoot)}${title ? ` ${title}` : ''}`, ''];
    for (const ch of ctx.contract.chapters) {
      body.push(`## ${ch.title}`, '', pendingMark(ch.title), '');
    }
    fs.mkdirSync(path.dirname(ctx.storyPath), { recursive: true });
    fs.writeFileSync(ctx.storyPath, `${body.join('\n').trimEnd()}\n`, 'utf-8');
    result = `${ctx.contract.chapters.length} 章骨架 + ${made.length} 份章草稿`
      + '（`AR/story-src/drafts/`，每份开头是读者读完这一章要能回答的问题与必要种子）；'
      + '附录的技术契约、规约、埋点、改动边界四节由 project 从真源投影，不用你写';
  }
  if (!hadPlan) result += `；写作设计空壳 ${relFromFeature(ctx, ctx.templatePath)}`;
  if (seeded.length) result += `；按写作设计骨架给 ${seeded.length} 份没动过的草稿铺好小节与表图`;
  // 首屏接续与 chapter 共用一处：各写一份的话，恢复那条路上的提示总比正常路径旧一轮。
  // 刚建的空壳不逐条报占位——下一步就是写它；已有的设计读不了才把缺在哪列出来。
  process.stdout.write(nextSteps(ctx, readText(ctx.storyPath) ?? '', result, {
    warnings: [...missing.map(m => missingSourceLine(m)), ...(hadPlan ? plan.problems : [])],
    plan, docs,
  }));
  for (const { file, rows } of starts) {
    process.stdout.write(`\n结构起点：${relFromFeature(ctx, file)} 已经动过，没有自动改；`
      + `写作设计选定、它里面还没有的结构如下，按需贴进去：\n${rows.join('\n')}\n`);
  }
  // 成文要用的当前输入在这一刻取：材料与系统设计里的图此刻列得出来。
  process.stdout.write(`\n${storyInputs(ctx, { docs, missing }).join('\n')}\n`);
}

async function main() {
  const args = parseArgs(process.argv);
  if (!COMMANDS.includes(args.command)) {
    fail(`用法: story-build.mjs <${COMMANDS.join('|')}> --feature <需求名> [--project-root <路径>]`);
  }
  if (args.deliver && args.command !== 'check') {
    fail('--deliver 只用于 check：它判的是这份 story 能不能交付');
  }
  const ctx = createContext(args);
  if (args.command === 'skeleton') cmdSkeleton(ctx);
  else if (args.command === 'chapter') cmdChapter(ctx);
  else if (args.command === 'project') cmdProject(ctx);
  else if (args.command === 'basis') cmdBasis(ctx);
  else if (args.command === 'review') await cmdReview(ctx);
  else if (args.command === 'check') await cmdCheck(ctx);
  else if (args.command === 'number') cmdNumber(ctx);
  else cmdBuild(ctx);
}

// 直接跑才执行命令；被 import 时只导出判定函数（正面校准要拿句边界判把一份文档
// 逐句灌一遍，那件事不该经由一个需要完整需求目录的命令行去做）。
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((e) => fail(e?.stack ?? String(e)));
}

