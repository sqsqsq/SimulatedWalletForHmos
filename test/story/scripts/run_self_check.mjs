/**
 * 对指定工程根跑真实的知识层自检（`doc/extensions/hooks/shared/knowledge.mjs > selfCheck`）。
 *
 * **调用真实模块**，不在测试侧重实现——重实现出来的是「测试对测试」，判据一改两边就分叉。
 * 夹具是一个自带 `framework.config.json`（`paths.extension_dir: "."`）的迷你扩展根，
 * 把它当工程根传进来即可。
 *
 * 用法：node test/story/scripts/run_self_check.mjs [projectRoot]
 * 输出：stdout 每行一个问题。退出码：0 无问题；1 有问题；2 知识派生失败（清单/文件/kind 出错）。
 */
import * as path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, '..', '..', '..');
const projectRoot = path.resolve(process.argv[2] ?? repoRoot);
const modulePath = path.join(repoRoot, 'doc', 'extensions', 'hooks', 'shared', 'knowledge.mjs');

const { activeKnowledge, selfCheck } = await import(pathToFileURL(modulePath).href);

let knowledge;
try {
  knowledge = activeKnowledge(projectRoot);
} catch (e) {
  console.error(`派生失败：${e.message}`);
  process.exit(2);
}
const problems = selfCheck(projectRoot, knowledge);
for (const p of problems) console.log(p);
process.exit(problems.length ? 1 : 0);
