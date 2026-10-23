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
 * | `view` | 正式图与阅读图：`--mode prepare` 给未管理的 Mermaid 图建源（`--id` 从源重建一块）并按写作设计同步阅读槽，`mermaid` 按源重铺、清空阅读槽，`svg` 展开验收成立的阅读图，`toggle` 一键显隐；`status` 列本地阅读工作，`review-request` / `review-check` 生成与核对阅读图验收 |
 * | `archive` | 唯一的归档入口：交付门 → 对接层上传与读回 → 核回执 → 登记归档态 |
 *
 * 除 `view` 外的命令都由最外层一次持有视图：动手前回到正式形态（正式的编号、登记、核对、交付与上传只认它），
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
import { appendixChapter, materialSubsectionName, projectAppendix, specGaps, specTerms } from './story/appendix.mjs';
import {
  materialListSkeleton, materialsNotReady, missingSourceLine, relFromFeature, sourceStatus,
} from './story/sources.mjs';
import { cmdBuild, registrationGap } from './story/review.mjs';
import { cmdChapter, nextSteps } from './story/chapter.mjs';
import { cmdCheck } from './story/check.mjs';
import { readWritingPlan, writingPlanShell } from './story/writing-plan.mjs';
import { storyInputs } from '../../../../hooks/spec/author.mjs';
import {
  ensureMermaid, readingWork, reviewCheck, reviewRequest, switchView, VIEW_MODES, writeLauncher,
} from './story/figure-view.mjs';
import { runPython, VIEW_OWNER, viewOwnerKey } from './flow/client.mjs';
import { extensionRoot } from '../../../../hooks/shared/paths.mjs';

/** 命令与它做什么、要哪些命令参数（必需的写在 need）；解析与帮助读同一张表。无原型：只认表里自己的键。 */
const COMMANDS = Object.assign(Object.create(null), {
  skeleton: { what: '预检流程、材料、Spec 与决策登记，全过才建写作设计空壳、十章骨架与章草稿，并给出当前输入与下一步' },
  chapter: { what: '把草稿里的一章原子替换进 AR/story.md，其余章一个字节不动', need: ['--chapter', '--from'] },
  project: { what: '附录机器区按当前真源（spec 扩展章、knowledge-use.yaml）重投' },
  number: { what: '给 AR/story.md 重编号：章序按合同，小节与图题按出现顺序' },
  check: { what: '只读核对确定性不变量；加 --deliver 判能不能交付', opts: ['--deliver'] },
  build: { what: '由 decisions.json 渲染 AR/review.md（人工区逐字节保留）' },
  view: { what: `切换、准备、查看或验收图的形态（--mode ${VIEW_MODES.join('|')}）`, need: ['--mode'], opts: ['--id'] },
  archive: { what: '交付门 → 对接层上传与读回 → 核回执 → 登记归档态（只用于需求系统单）', need: ['--mcp-token'] },
});
/** 选项：值的写法与作用；值以 -- 开头时写成 `--选项=值`。 */
const OPTIONS = Object.assign(Object.create(null), {
  '--feature': ['<需求名>', '需求目录名（doc/features/<需求名>）'],
  '--project-root': ['<路径>', '工程根，不给时按入口所在工程'],
  '--chapter': ['<章名>', '要替换的章，按章节合同的章名'],
  '--from': ['<文件>', '这一章的正文文件（草稿）'],
  '--deliver': [null, '交付门：在 check 之上再核回执与读者审查'],
  '--mode': ['<模式>', '图的形态或动作'],
  '--id': ['<图块 ID>', '只作用于这一块图'],
  '--mcp-token': ['<token>', '对接层访问需求系统用，不打印'],
});
const KEY = { '--project-root': 'projectRoot', '--mcp-token': 'token' };
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
  // ④ Spec 可读、非空，本步要消费的那几节都在
  const spec = specText(ctx);
  if (spec === null) skipped.push('Spec 的章节、术语与附录派生（spec/spec.md 读不到）');
  else if (!spec.trim()) problems.push('spec/spec.md：是空的——story 骨架从 spec 的术语映射表与扩展章各节派生');
  else {
    const gaps = specGaps(ctx.contract, spec);
    if (gaps.length) {
      problems.push(`spec/spec.md：缺起手要读的这几节：\n  · ${gaps.join('\n  · ')}\n`
        + '  不涉及的节写「不涉及：<依据>」一行也算有内容——'
        + '起手按这一节有没有正文判，写出来的结论评审者读得到');
    }
  }
  // ⑤ 决策登记起手前就有议题，或写明本单无待决（只读）
  const gap = registrationGap(ctx);
  if (gap) problems.push(gap);
  if (problems.length) {
    fail(`起手预检没过，骨架没起，Story、草稿与写作设计都没写：\n${problems.map((p, i) => `${i + 1}. ${p}`).join('\n')}`
      + (skipped.length ? `\n没判（依赖上面的缺口，补齐后重跑 skeleton 再核）：\n${skipped.map(s => `  · ${s}`).join('\n')}` : ''));
  }
  return { docs, missing, spec };
}

function cmdSkeleton(ctx) {
  const { docs, missing, spec } = skeletonPreflight(ctx);

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
      + `附录的${Object.keys(appendixChapter(ctx.contract)?.projection?.sections ?? {}).join('、')}由 project 从真源投影，不用你写`;
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
  // 成文要用的当前输入在这一刻取：Spec 刚写完，它的图这时才列得出来。
  process.stdout.write(`\n${storyInputs(ctx, { docs, missing }).join('\n')}\n`);
}

/** `view`：准备、显示或隐藏阅读图，查看或验收它们，结果与缺口原样报出。 */
function cmdView(ctx) {
  const { mode, id = '' } = ctx.args;
  if (!VIEW_MODES.includes(mode)) fail(`view 要 --mode ${VIEW_MODES.join('|')}`);
  if (mode === 'status') {
    process.stdout.write(`${JSON.stringify(readingWork(ctx.featureRoot), null, 2)}\n`);
    return;
  }
  if (mode === 'review-request' || mode === 'review-check') {
    if (!id) fail(`view --mode ${mode} 要 --id <阅读图 ID>`);
    if (mode === 'review-check') {
      const r = reviewCheck(ctx.featureRoot, id);
      if (r.state !== 'ready') fail(`阅读图 ${id} 的验收没有成立（${r.state}）：${r.reason}`);
      process.stdout.write(`[story-build view] 阅读图 ${id} 的验收成立（源码语义审查完成，本结论不含渲染外观验收）：可以用 view --mode svg 显示它\n`);
      return;
    }
    const r = reviewRequest(ctx.projectRoot, ctx.featureRoot, id);
    if (r.problems.length) fail(`阅读图 ${id} 的验收请求没有生成：\n  ${r.problems.join('\n  ')}`);
    process.stdout.write(`[story-build view] 验收请求 ${r.request.request_id}${r.written ? '已写入' : '没有变化'}\n${r.task.join('\n')}\n`);
    return;
  }
  const r = switchView(ctx.featureRoot, mode, { id });
  if (r.problems.length) fail(`view --mode ${mode} 没有写任何东西：\n  ${r.problems.join('\n  ')}`);
  const launcher = mode === 'prepare' ? writeLauncher(ctx.featureRoot, ctx.contract.local_reading_entry) : null;
  process.stdout.write(`[story-build view] ${mode}：${r.changed ? '已改写 AR/story.md' : 'AR/story.md 没有变化'}；`
    + `正式图块 ${r.counts.mermaid} 个、展开的阅读图 ${r.counts.svg} 张\n`
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
 * 最外层持有视图：动手前回到正式形态（Mermaid 按源、阅读槽置空），结束或失败后恢复当前可用的阅读图。恢复失败只补视图，
 * 附在业务结果之后报出来，不遮住原来的错误。同一需求的外层已切入并持有时，子进程不再切入，也不各自恢复。
 */
function withView(ctx, body) {
  const key = viewOwnerKey(ctx.featureRoot);
  const before = process.env[VIEW_OWNER];
  const owner = before !== key;
  if (owner) process.env[VIEW_OWNER] = key;
  try {
    const back = owner ? ensureMermaid(ctx.featureRoot) : { problems: [] };
    if (back.problems.length) fail(`读 story 之前要先回到正式形态（Mermaid 按源、阅读槽置空），回不去：\n  ${back.problems.join('\n  ')}`);
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
  if (!fs.existsSync(ctx.storyPath)) return;     // 还没有 story：没有可恢复的阅读图
  try {
    const r = switchView(ctx.featureRoot, 'svg');
    if (r.problems.length) {
      process.stderr.write(`[story-build] 本地阅读图没有恢复，story 保持正式形态（业务结果不受影响）：\n  ${r.problems.join('\n  ')}\n`);
      return;
    }
    if (r.counts.svg) process.stderr.write(`[story-build] 已恢复 ${r.counts.svg} 张可用的本地阅读图\n`);
    if (r.kept.length) {
      process.stderr.write(`[story-build] 本地阅读还没完成（业务结果不受影响），${r.kept.length} 张阅读图没有显示：\n`
        + r.kept.map(k => `  ${k.id}：${k.reason}\n`).join('')
        + '  只修图：按 reference/svg.md 画图或重新验收后跑 `story-build view --mode svg`；全部待办见 `view --mode status`\n');
    }
  } catch (e) {
    process.stderr.write(`[story-build] 本地阅读图恢复时出错（${e?.message ?? e}），story 保持正式形态；只补视图：\`story-build view --mode svg\`\n`);
  }
}

function main() {
  const args = parseArgs(process.argv);
  if (args.help) {
    process.stdout.write(`${args.help}\n`);
    return;
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

