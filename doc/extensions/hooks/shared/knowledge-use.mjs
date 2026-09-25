/**
 * knowledge-use —— spec 阶段知识判断的两条命令。
 *
 *     node knowledge-use.mjs init   --feature <名> [--project-root <路径>]
 *     node knowledge-use.mjs render --feature <名> [--project-root <路径>]
 *
 * `init` 按激活清单生成判断骨架（条目一条不落，判断留空），`render` 在判断填完之后
 * 把 spec 的 §9.2/§9.3 生成出来。
 *
 * ## 为什么是这个形状
 *
 * 判断「哪条规约命中、本需求要求做什么」「哪些模式是候选」的真源是
 * `spec/knowledge-use.yaml`，§9.2/§9.3 两章是它的投影。作者只编辑 YAML，投影由本命令写：
 * 机械判据读结构，不解析人写的表；投影与真源对不上时错的一定是投影。
 *
 * ## 三类知识各自的生命周期（合同）
 *
 * - **facts**：激活即事实，不判命中与否。只记「用它做了什么」，供评审者回查。
 * - **constraints**：spec 判命中，命中的写清**本需求要求做什么**；不命中的给可回查依据。
 *   落点（哪个接口、哪个存储键）与验证方式由 plan 定，不在这里。
 * - **patterns**：spec **只登记候选，不选型**。选型缺方案上下文，那是 plan 的事。
 *
 * ## 实现在哪
 *
 * 本文件只做参数解析、分派与顶层输出。真源文件的读取、规范化与骨架在
 * `knowledge-use/document.mjs`；判全了没有在 `knowledge-use/validation.mjs`；
 * 生成区的渲染、写入与只读保护在 `knowledge-use/projection.mjs`。
 * 库调用方直接 import 那三个模块——这里不转发。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { activeKnowledge } from './knowledge.mjs';
import { featureRoot, readTextOrNull, relDisplay } from './paths.mjs';
import { readUse, renderSkeleton, usePath } from './knowledge-use/document.mjs';
import { coverageProblems } from './knowledge-use/validation.mjs';
import { applyZones, renderZones } from './knowledge-use/projection.mjs';

/** 骨架只在开头生成一次：已经有判断在里面时不许覆盖。 */
function cmdInit(projectRoot, feature) {
  const target = usePath(projectRoot, feature);
  if (fs.existsSync(target)) {
    process.stderr.write(`${relDisplay(projectRoot, target)} 已经在了`
      + '——骨架只在开头生成一次，重来会盖掉已经做过的判断\n');
    process.exit(1);
  }
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, renderSkeleton(projectRoot, activeKnowledge(projectRoot)), 'utf-8');
  process.stdout.write(`[knowledge-use] 骨架已写入 ${relDisplay(projectRoot, target)}`
    + '：逐条填 applicable 与依据，填完跑 render\n');
}

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a.startsWith('--')) out[a.slice(2).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = argv[++i];
  }
  return out;
}

function main(argv) {
  const [command, ...rest] = argv;
  if (command !== 'render' && command !== 'init') {
    process.stderr.write('用法：knowledge-use.mjs <init|render> --feature <名> [--project-root <路径>]\n'
      + '  init   —— 按激活清单生成骨架（条目一条不落，判断留空）\n'
      + '  render —— 判断填完之后，把 spec 的 §9.2/§9.3 生成出来\n');
    process.exit(2);
  }
  const args = parseArgs(rest);
  if (!args.feature) {
    process.stderr.write('缺 --feature <需求名>\n');
    process.exit(2);
  }
  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  const projectRoot = path.resolve(args.projectRoot ?? path.join(scriptDir, '..', '..', '..', '..'));
  try {
    if (command === 'init') { cmdInit(projectRoot, args.feature); return; }
    const knowledge = activeKnowledge(projectRoot);
    const use = readUse(projectRoot, args.feature);
    const specPath = path.join(featureRoot(projectRoot, args.feature), 'spec', 'spec.md');
    const specText = readTextOrNull(specPath);
    if (specText === null) {
      process.stderr.write(`读不到 ${relDisplay(projectRoot, specPath)}\n`);
      process.exit(1);
    }
    const problems = coverageProblems(projectRoot, knowledge, use, specText);
    if (problems.length) {
      process.stderr.write(`knowledge-use.yaml 还不能生成，先修这 ${problems.length} 处：\n`);
      for (const p of problems) process.stderr.write(`  · ${p}\n`);
      process.exit(1);
    }
    const next = applyZones(specText, renderZones(knowledge, use));
    fs.writeFileSync(specPath, next, 'utf-8');
    process.stdout.write(`[knowledge-use] 生成区已写入 ${relDisplay(projectRoot, specPath)}\n`);
  } catch (e) {
    process.stderr.write(`${e.message}\n`);
    process.exit(1);
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  main(process.argv.slice(2));
}
