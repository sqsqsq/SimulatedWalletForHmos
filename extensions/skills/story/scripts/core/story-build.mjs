/**
 * story 的登记、核对与校验 —— 七个命令，围绕**一份文档写成**这件事。
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
 * 语言红线、决策登记字段、材料清单形态、登记之后改过没有。凡是要读懂内容才判得了的
 * ——讲清没讲清、贴不贴合、图题说的是不是这张图——都不在这里，归 verifier 的
 * 语义判据与真实结果观察。用字符串近似语义，模型只会照着字符串改。
 *
 * ## 七个命令
 *
 * | 命令 | 做什么 |
 * |------|--------|
 * | `skeleton` | 预检流程与材料；建决策登记骨架、写作设计空壳、十章骨架（每章一个稳定章锚 + 一个待写 marker）与章草稿，给出当前输入 |
 * | `chapter` | 把一章的内容原子替换进 story.md，其余字节不动 |
 * | `project` | 附录机器区按当前真源（spec 扩展章、knowledge-use.yaml）重投 |
 * | `check` | 上面那几条确定性不变量 |
 * | `build` | 由 `decisions.json` 渲染 `review.md`（机器区重算、人工区逐字节保留） |
 * | `number`| 给 `story.md` 重编号：章序按合同、小节序按出现顺序、图题按全篇顺序 |
 * | `view` | 图的两种形态：`--mode prepare` 给未管理的 Mermaid 图加管理标记并首次建源（`--id` 从源重建一块），`mermaid` 按源重铺，`svg` 切到合格的阅读图，`toggle` 一键切换；`status` 列本地阅读工作，`review-request` / `review-check` 生成与核对局部阅读验收 |
 * | `archive` | 唯一的归档入口：交付门 → 对接层上传与读回 → 核回执 → 登记归档态 |
 *
 * 除 `view` 外的命令都由最外层一次持有视图：动手前切回 Mermaid（正式的编号、登记、核对、交付与上传只认它），
 * 结束或失败后恢复可用的阅读图；被它调起的子命令（环境变量 `STORY_VIEW_OWNER`）不各自恢复。
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
  CommandFailure, createContext, fail, isSystemRequirement, readJson, readText, specText,
} from './story/context.mjs';
import { materialSubsectionName, projectAppendix, specGaps, specTerms } from './story/appendix.mjs';
import {
  materialListSkeleton, materialsNotReady, missingSourceLine, relFromFeature, sourceStatus,
} from './story/sources.mjs';
import { cmdBuild, registrationGap } from './story/review.mjs';
import { cmdChapter, nextSteps } from './story/chapter.mjs';
import { cmdCheck } from './story/check.mjs';
import { readWritingPlan, writingPlanShell } from './story/writing-plan.mjs';
import { storyInputs } from '../../../../hooks/spec/author.mjs';
import {
  ensureMermaid, readingWork, reviewRequest, switchView, VIEW_MODES, writeLauncher,
} from './story/figure-view.mjs';
import { readingState } from './story/figure-reading.mjs';
import { runPython, VIEW_OWNER, viewOwnerKey } from './flow/client.mjs';
import { extensionRoot } from '../../../../hooks/shared/paths.mjs';

const COMMANDS = ['check', 'build', 'number', 'skeleton', 'chapter', 'project', 'view', 'archive'];

function parseArgs(argv) {
  const args = { command: argv[2] && !argv[2].startsWith('--') ? argv[2] : '' };
  for (let i = 3; i < argv.length; i++) {
    if (argv[i] === '--feature') args.feature = argv[++i];
    else if (argv[i] === '--project-root') args.projectRoot = argv[++i];
    else if (argv[i] === '--chapter') args.chapter = argv[++i];
    else if (argv[i] === '--from') args.from = argv[++i];
    else if (argv[i] === '--deliver') args.deliver = true;
    else if (argv[i] === '--mode') args.mode = argv[++i];
    else if (argv[i] === '--id') args.id = argv[++i];
    else if (argv[i] === '--render') args.render = argv[++i];
    else if (argv[i] === '--mcp-token') args.token = argv[++i];
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
 * 附录机器区按当前真源重投。登记之后 spec 改了，直接重跑 `story_flow.py story`：
 * 它先重投再登记，一步跟上。
 */
function cmdProject(ctx) {
  const story = readText(ctx.storyPath);
  if (story === null) fail('AR/story.md：不在——骨架由 skeleton 建，附录机器区投在它的附录章里');
  const { text, zones } = projectAppendix(ctx, story);
  if (text !== story) fs.writeFileSync(ctx.storyPath, text, 'utf-8');
  process.stdout.write(`[story-build project] 附录机器区按当前真源重投 ${zones} 节`
    + '（spec 扩展章 / knowledge-use.yaml）；材料清单归你，不动\n');
}

/**
 * 起手：十章骨架 + 每章一份草稿。
 *
 * **预检全部读完、判完、算完，才开始写盘**。顺序不是风格问题：一边建决策骨架一边
 * 才发现 Spec 缺了的话，盘上留下的是半份起手，而作者拿到的报错说的是另一件事——
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

  // ---- 预检 ④：Spec 可读、非空，本步要消费的那几节都在 ----
  const spec = specText(ctx);
  if (spec !== null && !spec.trim()) {
    fail('spec/spec.md：是空的——story 骨架从 spec 的术语映射表与扩展章各节派生');
  }
  const gaps = spec === null ? [] : specGaps(ctx.contract, spec);
  if (gaps.length) {
    fail(`spec/spec.md：缺起手要读的这几节，骨架没起：\n  · ${gaps.join('\n  · ')}\n`
      + '  不涉及的节写「不涉及：<依据>」一行也算有内容——'
      + '起手按这一节有没有正文判，写出来的结论评审者读得到');
  }

  // ---- 预检 ⑤：决策登记起手前就有议题，或写明本单无待决（只读，不写） ----
  const gap = registrationGap(ctx);
  if (gap) fail(gap);

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
  // 成文要用的当前输入在这一刻取：Spec 刚写完，它的图这时才列得出来。
  process.stdout.write(`\n${storyInputs(ctx, { docs, missing }).join('\n')}\n`);
}

/** `view`：切换、准备、查看或验收图的形态，结果与缺口原样报出。 */
function cmdView(ctx) {
  const { mode, id = '' } = ctx.args;
  if (!VIEW_MODES.includes(mode)) fail(`view 要 --mode ${VIEW_MODES.join('|')}`);
  if (mode === 'status') {
    process.stdout.write(`${JSON.stringify(readingWork(ctx.featureRoot), null, 2)}\n`);
    return;
  }
  if (mode === 'review-request' || mode === 'review-check') {
    if (!id) fail(`view --mode ${mode} 要 --id <图块 ID>`);
    if (mode === 'review-check') {
      const r = readingState(ctx.featureRoot, id);
      if (r.state !== 'ready') fail(`图 ${id} 的局部阅读验收没有成立（${r.state}）：${r.reason}`);
      process.stdout.write(`[story-build view] 图 ${id} 的局部阅读验收成立：当前 SVG 可作本地阅读图\n`);
      return;
    }
    const r = reviewRequest(ctx.projectRoot, ctx.featureRoot, id, ctx.args.render ?? '');
    if (r.problems.length) fail(`图 ${id} 的验收请求没有生成：\n  ${r.problems.join('\n  ')}`);
    process.stdout.write(`[story-build view] 验收请求 ${r.request.request_id}${r.written ? '已写入' : '没有变化'}\n${r.task.join('\n')}\n`);
    return;
  }
  const r = switchView(ctx.featureRoot, mode, { id });
  if (r.problems.length) fail(`view --mode ${mode} 没有写任何东西：\n  ${r.problems.join('\n  ')}`);
  const launcher = mode === 'prepare' ? writeLauncher(ctx.featureRoot, ctx.contract.local_reading_entry) : null;
  process.stdout.write(`[story-build view] ${mode}：${r.changed ? '已改写 AR/story.md' : 'AR/story.md 没有变化'}；`
    + `图块 Mermaid ${r.counts.mermaid} 个、SVG ${r.counts.svg} 个\n`
    + [...r.notes, ...(launcher ? [launcher] : [])].map(n => `  - ${n}\n`).join(''));
}

/** 跑本入口的另一个命令或另一个脚本：参数数组传递、不经 shell，两路输出原样带回。 */
function child(args) {
  const r = spawnSync(process.execPath, args, { encoding: 'utf-8', windowsHide: true });
  return { status: r.status, error: r.error, out: [r.stdout, r.stderr].map(x => String(x ?? '').trim()).filter(Boolean).join('\n') };
}

/**
 * 归档：交付门 → 对接层上传并读回 → 核回执 → 登记归档态。交付门不过零系统调用；回执不全不登记；
 * 远端已成功而本地登记失败时说清已发生的副作用与补登记入口，不自动重传。token 只作参数传给对接层，不打印。
 */
function cmdArchive(ctx) {
  const feature = ctx.args.feature;
  if (!isSystemRequirement(feature)) fail(`${feature} 是本地需求：本地单没有归档环节，交付终点是仓内三件`);
  if (!ctx.args.token) fail('archive 要 --mcp-token <token>：上传与读回由对接层用它访问需求系统');
  const gate = child([ctx.scriptPath, 'check', '--deliver', '--feature', feature, '--project-root', ctx.projectRoot]);
  if (gate.status !== 0) fail(`交付门没过，没有调用需求系统：\n${gate.out}`);
  // 对接层入口登记在章节合同（相对扩展根），core 只按归档协议调它
  const adapter = path.join(extensionRoot(ctx.projectRoot), ...String(ctx.contract.system_archive_entry ?? '').split('/'));
  if (!ctx.contract.system_archive_entry || !fs.existsSync(adapter)) fail(`章节合同登记的归档对接入口读不到（${adapter}）：对接层由目标仓按所有权维护`);
  const up = child([adapter, 'archive', feature, ctx.args.token, '--project-root', ctx.projectRoot]);
  let receipt = null;
  try { receipt = JSON.parse(up.out.slice(up.out.indexOf('{'), up.out.lastIndexOf('}') + 1)); } catch { receipt = null; }
  const ok = up.status === 0 && receipt?.mode === 'archive' && receipt?.reqNo === feature
    && ['success', 'verified', 'archived', 'reviewArchived'].every(k => receipt?.[k] === true);
  if (!ok) {
    fail(`对接层上传或读回核验没有成立（退出码 ${up.status ?? up.error?.message}），没有登记归档态；远端状态以对接层的话为准，`
      + `核清后重跑 archive：\n${up.out.split(ctx.args.token).join('<token>')}`);
  }
  const flow = path.join(path.dirname(ctx.scriptPath), 'story_flow.py');
  const reg = runPython(flow, ['archived', '--feature', feature, '--project-root', ctx.projectRoot]);
  if (reg.error || reg.status !== 0) {
    fail('需求系统已经写入并读回核验通过，本地归档态登记失败——不要重新上传；修好原因后只补登记：'
      + `\`python doc/extensions/skills/story/scripts/core/story_flow.py archived --feature ${feature}\`\n`
      + (reg.error ?? reg.output));
  }
  process.stdout.write(`[story-build archive] 已归档并登记：${feature}（上传、读回核验、评审记录附件都成立；覆盖前的系统正文备份在 ${receipt.backupPath ?? '对接层记录处'}）\n`);
}

/**
 * 最外层持有视图：动手前切回 Mermaid，结束或失败后按当前源恢复可用的阅读图。恢复失败只补视图，
 * 附在业务结果之后报出来，不遮住原来的错误。子进程继承持有标记，不各自恢复。
 */
function withView(ctx, body) {
  const key = viewOwnerKey(ctx.featureRoot);
  const before = process.env[VIEW_OWNER];
  const owner = before !== key;
  if (owner) process.env[VIEW_OWNER] = key;
  try {
    const back = ensureMermaid(ctx.featureRoot);
    if (back.problems.length) fail(`读 story 之前要先切回 Mermaid，切不回来：\n  ${back.problems.join('\n  ')}`);
    return body();
  } finally {
    if (owner) {
      if (before === undefined) delete process.env[VIEW_OWNER];
      else process.env[VIEW_OWNER] = before;
      restoreView(ctx);
    }
  }
}

function restoreView(ctx) {
  try {
    const r = switchView(ctx.featureRoot, 'svg');
    if (r.problems.length) {
      process.stderr.write(`[story-build] 本地阅读图没有恢复，story 保持 Mermaid（业务结果不受影响）：\n  ${r.problems.join('\n  ')}\n`);
      return;
    }
    if (r.counts.svg) process.stderr.write(`[story-build] 已恢复 ${r.counts.svg} 张可用的本地阅读图\n`);
    if (r.kept.length) {
      process.stderr.write(`[story-build] 本地阅读还没完成（业务结果不受影响），${r.kept.length} 张图保持 Mermaid：\n`
        + r.kept.map(k => `  ${k.id}：${k.reason}\n`).join('')
        + '  只修图：按 reference/svg.md 重述或重新验收后跑 `story-build view --mode svg`；全部待办见 `view --mode status`\n');
    }
  } catch (e) {
    process.stderr.write(`[story-build] 本地阅读图恢复时出错（${e?.message ?? e}），story 保持 Mermaid；只补视图：\`story-build view --mode svg\`\n`);
  }
}

function main() {
  const args = parseArgs(process.argv);
  if (!COMMANDS.includes(args.command)) {
    fail(`用法: story-build.mjs <${COMMANDS.join('|')}> --feature <需求名> [--project-root <路径>]`);
  }
  if (args.deliver && args.command !== 'check') {
    fail('--deliver 只用于 check：它判的是这份 story 能不能交付');
  }
  const ctx = createContext(args);
  if (args.command === 'view') return cmdView(ctx);
  return withView(ctx, () => {
    if (args.command === 'skeleton') cmdSkeleton(ctx);
    else if (args.command === 'chapter') cmdChapter(ctx);
    else if (args.command === 'project') cmdProject(ctx);
    else if (args.command === 'check') cmdCheck(ctx);
    else if (args.command === 'number') cmdNumber(ctx);
    else if (args.command === 'archive') cmdArchive(ctx);
    else {
      cmdBuild(ctx);
      const launcher = writeLauncher(ctx.featureRoot, ctx.contract.local_reading_entry);
      if (launcher) process.stderr.write(`[story-build] ${launcher}\n`);
    }
  });
}

// 直接跑才执行命令；被 import 时只导出判定函数（正面校准要拿句边界判把一份文档
// 逐句灌一遍，那件事不该经由一个需要完整需求目录的命令行去做）。
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    main();
  } catch (e) {
    // 判定没过：原因已经写到 stderr，按 1 结束（finally 已恢复视图）
    if (e instanceof CommandFailure) process.exit(1);
    // 脚本自身的缺陷：原始异常全文带出，并说明这一步没跑完、归谁处理
    process.stderr.write(`[story-build] 脚本自身异常：${e?.stack ?? e}\n——这一步没有执行完，不是产物的问题，归扩展维护者处理\n`);
    process.exit(2);
  }
}

