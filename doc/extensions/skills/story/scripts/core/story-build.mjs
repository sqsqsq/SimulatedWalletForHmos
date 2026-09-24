/**
 * story 的登记、核对与校验 —— 六个命令，围绕**一份文档写成**这件事。
 *
 * ## 成文怎么走
 *
 * 材料与 Spec 齐备之后，`skeleton` 给出成文要用的当前输入并建写作设计空壳与章草稿；
 * 作者先写本需求的写作设计骨架，再照骨架一次写一章、经 `chapter` 原子替换落盘，
 * 十章写完再按回看清单逐条处置。每步输出有界、写完即落盘、断了能续——整篇一次重出是全有或全无，
 * 中途断了磁盘上什么都没有。
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
 * | `skeleton` | 预检流程与材料；建决策登记骨架、写作设计空壳、十章骨架（每章一个稳定章锚 + 一个待写 marker）与章草稿，给出当前输入 |
 * | `chapter` | 把一章的内容原子替换进 story.md，其余字节不动 |
 * | `project` | 附录机器区按当前真源（spec §9、knowledge-use.yaml）重投 |
 * | `check` | 上面那几条确定性不变量 |
 * | `build` | 由 `decisions.json` 渲染 `review.md`（机器区重算、人工区逐字节保留） |
 * | `number`| 给 `story.md` 重编号：章序按合同、小节序按出现顺序、图题按全篇顺序 |
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
  createContext, fail, readJson, readText, refuseIfFrozen, specText, writeJson,
} from './story/context.mjs';
import { materialSubsectionName, projectAppendix, specGaps, specTerms } from './story/appendix.mjs';
import {
  materialListSkeleton, materialsNotReady, missingSourceLine, relFromFeature, sourceStatus,
} from './story/sources.mjs';
import { cmdBuild, decisionsMissing } from './story/review.mjs';
import { cmdChapter, nextSteps } from './story/chapter.mjs';
import { cmdCheck } from './story/check.mjs';
import { readWritingPlan, writingPlanShell } from './story/writing-plan.mjs';
import { storyInputs } from '../../../../hooks/spec/author.mjs';

const COMMANDS = ['check', 'build', 'number', 'skeleton', 'chapter', 'project'];

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
 * 起手：十章骨架 + 每章一份草稿。
 *
 * **预检全部读完、判完、算完，才开始写盘**。顺序不是风格问题：一边建决策骨架一边
 * 才发现 Spec 缺了的话，盘上留下的是半份起手，而作者拿到的报错说的是另一件事——
 * 他要先弄清哪些已经建了，才知道重跑安不安全。
 */
function cmdSkeleton(ctx) {
  refuseIfFrozen(ctx, 'skeleton');

  // ---- 预检 ①：流程走到位了没有 ----
  const flow = readJson(path.join(ctx.featureRoot, 'AR', 'story-src', 'story-flow.json'), null);
  if (!flow) {
    fail('AR/story-src/story-flow.json 不存在：本 feature 还没走过 /story 的 S1–S3。'
      + '先跑 `story_flow.py init` 按关卡走完范围，收口后再起 story 骨架');
  }
  const flowGaps = flowProblems(ctx.featureRoot);
  if (flowGaps.length) fail(flowGaps.join('\n'));
  if (flow.status !== 'complete') {
    fail(`本轮还没有收口（status: ${flow.status}）：按 status 的下一步走完 S3/S4，再起 story 骨架`);
  }

  // ---- 预检 ②：材料 —— 清单在、与本轮基准一致、且磁盘现状仍是这批料 ----
  const manifest = readJson(path.join(ctx.srcDir, 'materials.json'), null);
  const base = (flow.rounds?.[flow.rounds.length - 1]?.materials) ?? {};
  if (!manifest) {
    fail('材料清单不存在：materials.json 由 `story_flow.py round` 生成，先跑它');
  }
  if (manifest.digest !== base.digest) {
    fail('材料清单与本轮登记的基准对不上：重跑 `story_flow.py round` 归位后再起骨架');
  }
  const notReady = materialsNotReady(ctx);
  if (notReady) fail(`材料还不能起稿：${notReady}`);

  // ---- 预检 ③：来源必需性（与交付前的 check 同一份判定） ----
  const { docs, missing, blocking } = sourceStatus(ctx);
  if (!docs.length) {
    fail(`一份材料都读不到（合同 sources 指向 ${Object.values(ctx.contract.sources ?? {})
      .map(x => (typeof x === 'string' ? x : x?.path)).filter(Boolean).join('、')}）`);
  }
  if (blocking.length) {
    fail('必备来源缺失，先补齐再起骨架：'
      + blocking.map(m => missingSourceLine(m)).join('；'));
  }

  // ---- 预检 ④：Spec 可读、非空，本步要消费的那几节都在 ----
  const spec = specText(ctx);
  if (spec !== null && !spec.trim()) {
    fail('spec/spec.md 是空的——先完成 spec 阶段的规格件，再起 story 骨架');
  }
  const gaps = spec === null ? [] : specGaps(ctx.contract, spec);
  if (gaps.length) {
    fail(`spec.md 还缺起手要读的这几节，先回 spec 补齐再起骨架：\n  · ${gaps.join('\n  · ')}\n`
      + '  这件事确实不涉及，就在那一节里写「不涉及：<依据>」一行——'
      + '写出来的结论评审者读得到，没写到那儿的，起手这一步分不出是哪一种');
  }

  // ---- 预检 ⑤：决策登记形状合法（只读，不写） ----
  const makeDecisions = decisionsMissing(ctx);

  // ---- 内容计算：也在写盘之前 ----
  const facts = {
    terms: specTerms(spec),
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
  if (makeDecisions) writeJson(ctx.decisionsPath, { decisions: [] });
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
    const body = [`# ${path.basename(ctx.featureRoot)}`, ''];
    for (const ch of ctx.contract.chapters) {
      body.push(`## ${ch.title}`, '', pendingMark(ch.title), '');
    }
    fs.mkdirSync(path.dirname(ctx.storyPath), { recursive: true });
    fs.writeFileSync(ctx.storyPath, `${body.join('\n').trimEnd()}\n`, 'utf-8');
    result = `${ctx.contract.chapters.length} 章骨架 + ${made.length} 份章草稿`
      + '（`AR/story-src/drafts/`，每份开头是读者读完这一章要能回答的问题与必要种子）；'
      + '附录的接口/数据·配置·事件/改动边界/规约判定四节由 project 从真源投影，不用你写';
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
  // 成文要用的当前输入在这一刻取：Spec 刚写完，它的图这时才列得出来。
  process.stdout.write(`\n${storyInputs(ctx, { docs, missing }).join('\n')}\n`);
}

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
  if (args.command === 'skeleton') cmdSkeleton(ctx);
  else if (args.command === 'chapter') cmdChapter(ctx);
  else if (args.command === 'project') cmdProject(ctx);
  else if (args.command === 'check') cmdCheck(ctx);
  else if (args.command === 'number') cmdNumber(ctx);
  else cmdBuild(ctx);
}

// 直接跑才执行命令；被 import 时只导出判定函数（正面校准要拿句边界判把一份文档
// 逐句灌一遍，那件事不该经由一个需要完整需求目录的命令行去做）。
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}

