/**
 * 交付门 —— 真实审查的回执、交付前的判据与通过之后的两条路。
 *
 * 按**动作**分而不按文件在不在推断阶段：登记前跑的是普通 check，那时读者审查还没发生。
 */
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { readJson, readText } from './context.mjs';
import { storyReviewProblems } from '../../../../../hooks/shared/verifier-report.mjs';

/**
 * 框架回执的入口 —— 直接用 node 起 framework 自己那份 ts-node，不经 shell。
 *
 * `npx` 在 Windows 上是 `npx.cmd`，而 Node 从 18.20 / 20.12 起拒绝不带 shell 地起 `.cmd`
 * （`EINVAL`）；带 shell 又要为参数里的空格与引号操心。装 ts-node 的是 framework/harness
 * 自己，路径解析得到就直接把它当普通 js 跑，两边都不用碰。
 */
function receiptRunner(harness) {
  try {
    const require = createRequire(import.meta.url);
    return require.resolve('ts-node/dist/bin.js', { paths: [harness] });
  } catch {
    return null;
  }
}

/**
 * 交付门通过之后往哪走 —— 打印选项，**不替人选**。
 *
 * 远程单可以先归档送审再进 plan，也可以两边同时开始；本地单没有归档，只剩 plan。
 * 这是脚本给的确定性文本，与 `story_flow.py status` 同一口径。
 */
export function deliveryNextSteps(ctx) {
  const remote = readJson(ctx.flowPath, null) !== null
    && !/^local[-_]/i.test(String(ctx.args.feature ?? ''));
  const rows = remote
    ? ['  1  归档送审：`/story archive <AR>`',
      '  2  进入 plan：按 framework 的 `phase.next_step` 走',
      '  3  先归档，再进 plan', '',
      '两条互不阻塞，可以并行开始；评审回流改了 spec 之后，'
      + '已经开工的 plan 产物按 framework 的修正流程更新，不是不管。']
    : ['  本地单没有归档：进入 plan，按 framework 的 `phase.next_step` 走。'];
  return ['', '[story-build check] 交付门通过。下一步由你选：', '',
    ...rows, ''].join('\n');
}

/**
 * 交付门 —— 阶段闭环成立了吗，读者审查这一项写成形态了吗。
 *
 * **闭环由框架判，扩展不重判**：报告在不在、终态块回显的 subject 对不对、
 * verdict 与 blocker 数一致不一致、verifier 派没派，都是 `check-receipt` 的判断。
 * 这里只跑它一次，退出码非 0 就把它的话原样带出来。
 *
 * 回执通过之后才轮到形态：读者审查那一项在汇总表里有没有一行、证据空不空、
 * 非 PASS 时两类结论齐不齐。**回执通过而这一项 FAIL 是不该出现的**——它是 BLOCKER 级，
 * FAIL 时 verdict 必为 FAIL、回执必然过不去；真出现了，交付照样拦。
 *
 * 跑不起来不算通过：找不到框架、起不了 ts-node 都如实报出来，让人自己跑一次。
 * 本宿主没登记审查员时读者审查这一项判不了——那不是失败，但**要出声**：
 * 静默通过的话，没经过审查的 story 就这么交出去了，事后没人看得出来。
 *
 * @returns {{problems: string[], notes: string[]}}
 */
export function deliveryProblems(ctx) {
  const harness = path.join(ctx.projectRoot, 'framework', 'harness');
  const receipt = path.join(harness, 'scripts', 'check-receipt.ts');
  const manual = 'cd framework/harness && npx ts-node scripts/check-receipt.ts '
    + `--feature ${ctx.args.feature} --phase spec`;
  const fail = (msg) => ({ problems: [msg], notes: [] });
  if (!fs.existsSync(receipt)) {
    return fail('交付门跑不了：找不到 framework/harness/scripts/check-receipt.ts——'
      + '闭环判定归框架，这个仓里没有框架就判不了交付，别把它当通过');
  }
  const runner = receiptRunner(harness);
  if (!runner) {
    return fail('交付门跑不了：framework/harness 里没有 ts-node——'
      + `先在那个目录装依赖，再自己跑一次 \`${manual}\`；跑不了不等于过了`);
  }
  const r = spawnSync(process.execPath,
    [runner, path.join('scripts', 'check-receipt.ts'),
      '--feature', ctx.args.feature, '--phase', 'spec'],
    { cwd: harness, encoding: 'utf-8', timeout: 300000, windowsHide: true });
  if (r.error) {
    return fail(`交付门跑不了：${r.error.message}——自己跑一次 \`${manual}\`，`
      + '过了再来；跑不了不等于过了');
  }
  if (r.status !== 0) {
    const say = `${r.stdout ?? ''}${r.stderr ?? ''}`.trim().split(/\r?\n/)
      .filter(Boolean).slice(-12).join(' / ');
    return fail(`spec 阶段还没闭环，不能交付——check-receipt 说：${say || `退出码 ${r.status}`}`);
  }

  const review = storyReviewProblems(ctx.projectRoot, ctx.args.feature, 'spec');
  return {
    problems: review.problems,
    notes: review.status === 'NOT_APPLICABLE'
      ? [`story 未经读者审查即交付：${review.detail}`]
      : [],
  };
}

// --------------------------------------------------------------------------
// number：给 story 重编号（章 / 小节 / 图题）
// --------------------------------------------------------------------------

