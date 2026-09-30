/**
 * 成文这一次的输入、落点与登记核对 —— 每条命令起手都从这里拿 `ctx`。
 *
 * 它只回答「这一次在哪个需求、读哪几份文件、登记之后改过没有」，不判内容：判据在各职责模块。
 * 台账与登记放在一起，因为它们是同一件事的两面——登记那一刻记下 story 与它的依据的指纹，
 * 之后改了任何一份，重跑 `story` 重新登记。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { activeKnowledge } from '../../../../../hooks/shared/knowledge.mjs';
import { featureRoot } from '../../../../../hooks/shared/paths.mjs';

/**
 * `AR/` 根下允许的独立文件 —— 三份交付文档，加一份单据身份。
 *
 * `detail.json` 不是本机制的产物（写它的是目标仓自己实现的对接脚本），但它是这一层的
 * 正当住户：单号、类型、父单号是这份需求与需求系统之间的绳子，跟交付文档同级。
 *
 * 白名单而不是黑名单：黑名单挡不住下一个往根下写的新文件，而这里要成立的是一个
 * 持续的性质——机制不往交付层散辅助件。
 */
const AR_ROOT_FILES = ['design.md', 'story.md', 'review.md', 'detail.json'];

export function fail(msg) {
  process.stderr.write(`[story-build] ${msg}\n`);
  process.exit(1);
}

export function readText(file) {
  try { return fs.readFileSync(file, 'utf-8').replace(/^﻿/, ''); } catch { return null; }
}

/** 本项目只有 AR 开头的需求挂在需求系统上，其余（问题单、自定义名、local 开头…）都是本地需求。来源由编号决定，与 `flow/state.py::system_requirement` 同一规则。 */
export function isSystemRequirement(feature) {
  return String(feature ?? '').startsWith('AR');
}

export function readJson(file, fallback) {
  const t = readText(file);
  if (t === null) return fallback;
  try { return JSON.parse(t); } catch { return fallback; }
}

/**
 * **原样读** —— 不剥 BOM、不动行尾。要按原文坐标替换的地方读它。
 *
 * `readText` 为了让判据不必处理 BOM 而剥掉它，那对「读一份文档来判」是对的；
 * 但章提交是**按区间把原文拼回去**，读进来少一个字节，写回去就少一个字节，
 * 而「其余章一个字节未动」这句话就不成立了。两种读法各有其用，不合成一个。
 */
export function readRaw(file) {
  try { return fs.readFileSync(file, 'utf-8'); } catch { return null; }
}

/**
 * 合同里的编号形态 —— **一条命令编译一次**，结果挂在 ctx 上给所有消费者用。
 *
 * 各消费处自己编译、`catch` 掉就跳过的话，合同里写错一条正则，那一条判据静默不判而门禁全绿。
 * 编译放建上下文这一刻：坏配置这时就知道，报给人看由消费者决定（章内判据不该为
 * 「合同写错了」拦住作者的这一章）。
 *
 * @returns {{drop: RegExp[], keep: RegExp[], problems: string[]}}
 */
function compileIdShapes(contract) {
  const out = { drop: [], keep: [], problems: [] };
  for (const kind of ['drop', 'keep']) {
    for (const shape of contract?.id_shapes?.[kind] ?? []) {
      try { out[kind].push(new RegExp(shape, 'g')); } catch {
        out.problems.push(`章节合同的 id_shapes.${kind}：「${shape}」不是合法正则`
          + '——编号形态在建上下文时编译，编译不了的这一条判不了');
      }
    }
  }
  return out;
}

//: 本模块在 `core/story/` 下，对外入口在 `core/`：两处路径都从这一个常量退回去算，
//: 各写一串 `..` 的话，模块再挪一层就得挨个数。
const CORE_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');

/** 工程根与章节合同。合同读不出来当场失败，不降级成空。 */
function commonInputs(args) {
  const projectRoot = path.resolve(
    args.projectRoot ?? path.join(CORE_DIR, '..', '..', '..', '..', '..', '..'));
  const contract = readJson(
    path.join(CORE_DIR, '..', '..', 'contracts', 'story-chapters.json'), null);
  if (!contract) fail('contracts/story-chapters.json：章节合同读不到或不是合法 JSON——每条命令起手读它，读不出不降级成空');
  return { projectRoot, contract, idShapes: compileIdShapes(contract) };
}

export function createContext(args) {
  if (!args.feature) fail('缺 --feature');
  const { projectRoot, contract, idShapes } = commonInputs(args);
  if (!Array.isArray(contract.chapters) || contract.chapters.length === 0) {
    // 派生为空要出声，不能当作「没有章节要求」通过
    fail('contracts/story-chapters.json：chapters 为空或不是数组——章节是所有判据的前提，派生为空按合同损坏报');
  }
  const featureDir = featureRoot(projectRoot, args.feature);
  const srcDir = path.join(featureDir, 'AR', 'story-src');
  return {
    args, projectRoot, contract, idShapes, featureRoot: featureDir, srcDir,
    scriptPath: path.join(CORE_DIR, 'story-build.mjs'),
    decisionsPath: path.join(srcDir, 'decisions.json'),
    templatePath: path.join(srcDir, 'story-template.md'),
    storyPath: path.join(featureDir, 'AR', 'story.md'),
    reviewPath: path.join(featureDir, 'AR', 'review.md'),
    flowPath: path.join(featureDir, 'AR', 'story-src', 'story-flow.json'),
  };
}

/**
 * 随稿登记的台账 —— 这里存的是 ctx 上的路径字段名，**不另列一份文件名**。
 *
 * 文件名的真源在 `core/flow/state.py` 的 `STORY_REGISTERED`：那几件是登记时要算指纹、
 * 归档时随稿走的同一批（另加 story 本身）。登记核对与存在性两处说的必须是同一批文件，
 * 各写一份就会改一处忘一处。第二列是它由哪里产出。
 */
const STORY_SRC_LEDGERS = [
  ['decisionsPath', '由 skeleton 产出'],
  ['templatePath', '由 skeleton 建空壳，作者按本需求写成整篇设计'],
];

/**
 * 台账在不在 —— **缺任一即 BLOCKER**，check 到此为止。
 *
 * 登记核对只管「登记之后改台账」，管不到登记之前把台账删掉。而删掉是有动力的：
 * 台账错到成百上千条时，整份删掉能让 check 的报错数当场归零。
 *
 * 报错文案要把这条路直接堵死：缺的那件是**补产出**，不是删同伴文件。
 */
export function requireLedgers(ctx) {
  const missing = STORY_SRC_LEDGERS
    .filter(([key]) => ctx[key] && readText(ctx[key]) === null)
    .map(([key, how]) => `${path.basename(ctx[key])}（${how}）`);
  if (!missing.length) return;
  fail(`AR/story-src/ 台账缺 ${missing.length} 件：${missing.join('、')}\n`
    + '  这几件是这份 story 据以成文的依据，随稿登记、随稿归档，check 在台账齐全时才往下判。\n'
    + '  台账记着评审者要看到的已核事实：台账不在，这些事实与它们被核过的记录一起不在，'
    + '报错数随之减少而问题仍在。');
}

/**
 * 最近一次成文登记记下的指纹（键是相对需求目录的路径）；没登记过为空，登记了却没有指纹为 null。
 *
 * @returns {Record<string,string|null>|null}
 */
function registeredDigests(ctx) {
  const flow = readJson(ctx.flowPath, null);
  if (flow?.status !== 'story_written') return {};
  return flow.story_digests ?? null;
}

/** 材料指纹：换行差异不算改动（同一份文件在两台机器上可能行尾不同）。 */
function digestOf(text) {
  return crypto.createHash('sha256')
    .update(String(text ?? '').replace(/\r\n/g, '\n'), 'utf-8')
    .digest('hex').slice(0, 16);
}

/** 激活规约条目 —— 派生失败要出声，不能当作「本需求没有规约」。 */
export function activeKnowledgeEntries(ctx) {
  try {
    return activeKnowledge(ctx.projectRoot).entries ?? [];
  } catch (e) {
    fail(`激活知识派生失败（${e.message}）——附录·规约表按激活清单逐条核，派生不出时不按「没有规约」放行`);
    return [];
  }
}

/** 登记之后改过没有 —— story 与它的决策登记、写作设计对得上最近一次成文登记的指纹。 */
export function ledgerDigestProblems(ctx) {
  const problems = [];
  // ⓪b 登记之后没再改过
  //
  // 登记记下 story 与它据以成文的依据此刻的指纹；之后任一份改了，登记说的就不是现在这份。
  // 改是正常的（返修、update 修订），改完重跑 `story` 重新登记。
  // 与 `flow/state.py` 的 `registration_drift` 同一件事，指纹口径同 `ledger_digest`。
  const digests = registeredDigests(ctx);
  if (digests === null) {
    return ['AR/story-src/story-flow.json：记着已成文登记，却没有登记指纹 story_digests，契约不完整'
      + '——登记指纹由 `story_flow.py story --feature <名>` 按当前内容重新登记时写入'];
  }
  for (const [rel, want2] of Object.entries(digests)) {
    const file = path.join(ctx.featureRoot, ...rel.split('/'));
    if (want2 === null && !fs.existsSync(file)) continue;
    if (want2 !== digestOf(readRaw(file))) {
      problems.push(`${rel} 在成文登记之后改过（与登记记下的指纹不同）——登记由 \`story_flow.py story --feature <名>\` 按当前内容重新登记`
        + '（它重投附录、编号、渲染 review 并全篇 check）');
    }
  }
  return problems;
}


/** `AR/` 这一层的独立文件只有白名单那几个，辅助件进 `story-src/`；目录一律放过。 */
export function strayFileProblems(ctx) {
  const problems = [];
  // ⑮ AR 根下只有交付文档：`AR/` 这一层的独立文件只有白名单那几个，辅助件进 `story-src/`。
  //
  // **只判文件，目录一律放过**：`story-src/`、`assets/` 这类目录都是正当的
  // 落点，限制它们没有意义。判的是「这一层散没散」，不是「这一层该有什么」——白名单里
  // 的文件缺了不报，各有各的判据管。
  {
    const arDir = path.join(ctx.featureRoot, 'AR');
    const strays = fs.existsSync(arDir)
      ? fs.readdirSync(arDir, { withFileTypes: true })
        .filter(e => e.isFile() && !AR_ROOT_FILES.includes(e.name)).map(e => e.name)
      : [];
    for (const name of strays) {
      problems.push(`AR/${name} 不该在这一层——AR 根下的独立文件按白名单判，只有交付文档与单据身份`
        + `（${AR_ROOT_FILES.join('、')}），辅助件的落点是 AR/story-src/；目录不受这条限制`);
    }
  }
  return problems;
}
