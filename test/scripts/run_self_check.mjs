/**
 * 对指定工程根跑真实的知识层自检（`extensions/hooks/shared/knowledge.mjs > selfCheck`）。
 *
 * **调用真实模块**，不在测试侧重实现——重实现出来的是「测试对测试」，判据一改两边就分叉。
 * 夹具是一个自带 `framework.config.json`（`paths.extension_dir: "."`）的迷你扩展根，
 * 把它当工程根传进来即可。
 *
 * 执行器是消费工程里装好的扩展（开发源不在任何工程里，它的 YAML 读取原地跑不起来）。
 *
 * 用法：node test/scripts/run_self_check.mjs <projectRoot> <执行器扩展目录>
 * 输出：stdout 每行一个问题。退出码：0 无问题；1 有问题；2 知识派生失败（清单/文件/kind 出错）。
 */
import * as path from 'node:path';
import { pathToFileURL } from 'node:url';

if (process.argv.length < 4) {
  console.error('用法：node run_self_check.mjs <projectRoot> <执行器扩展目录>');
  process.exit(2);
}
const projectRoot = path.resolve(process.argv[2]);
const modulePath = path.join(path.resolve(process.argv[3]), 'hooks', 'shared', 'knowledge.mjs');

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
