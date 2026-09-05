// ============================================================================
// author-context.ts — interactive 作者的阶段起手入口（只读）
// ============================================================================
// 解决的问题：`on_context_load` 钩子从来就能产出 promptFragments（hooks-dispatcher），
// 但全仓**唯一**的调用点在 harness-runner 的 verifier 装配处——通道存在、接错了对象。
// 结果是那些「写之前该知道什么」的内容只出现在 verifier 的上下文里：作者在动笔前看不到它，
// 只能在门禁报错之后补读，而那时产物已经按错的要求写出来了。
//
// 本入口把同一条通道接到作者一侧：**进入 phase、动笔之前**跑一次，把
// framework → profile → extension 三层的 `on_context_load` 内容直接交给当前执行者。
//
// ─── 边界（都是有代价换来的，改之前先看理由）─────────────────────────────────
//   · **只读**：不写 summary / receipt / hash / phase 状态 / 业务产物，不落任何盘。
//     它是「把已经存在的文本读出来给你」，不是一个新的生命周期或状态位。
//   · **不新建机制**：复用 `loadResolvedProfile` 与 `dispatchLifecycleHooks`，
//     顺序（framework → profile → extension）与 harness 内部完全一致，不另写一套。
//   · **缺席返回空，失败明确报错**：没有钩子就是没有，退出码 0、零输出；钩子抛错或
//     声明失败则退出码 1 并打印原因——**不降级成空**。静默的空和真正的空长得一样，
//     而这条链路一旦静默失效，现场只表现为「作者又没按要求写」。
//   · **每个片段带来源标识行**（`<!-- hook:on_context_load:<层>:<仓内相对路径> -->`）。
//     那行里的路径就是执行者要写进 `context-exploration.md` 的 `key_inputs_read` 的坐标：
//     读没读过由既有的 `context_exploration_inputs_coverage` 门禁判，本入口不另设门禁。
//
// 用法（在 framework/harness 下）：
//   npx ts-node scripts/author-context.ts --phase spec --feature <feature>
//   npx ts-node scripts/author-context.ts --phase spec --feature <feature> --json
// ============================================================================

import * as path from 'path';
import minimist from 'minimist';

import { dispatchLifecycleHooks } from '../hooks-dispatcher';
import type { HookDispatchPayload } from '../hooks-dispatcher';
import { loadFrameworkConfig } from '../config';
import { detectRepoLayout } from '../repo-layout';
import { loadResolvedProfile } from '../profile-loader';
import type { CheckResult } from './utils/types';
import type { Phase } from './utils/types';

export interface AuthorContextResult {
  phase: string;
  feature: string;
  /** 三层钩子按 dispatcher 顺序产出的片段，每段首行是来源标识。 */
  fragments: string[];
  /** 钩子自报失败或执行异常；非空即整体失败，绝不当成「没有内容」。 */
  failures: CheckResult[];
}

/**
 * 取本阶段的作者起手内容。纯读：不落盘、不改状态。
 *
 * @param harnessRoot framework/harness 的绝对路径（入口自锚，调用方一般不用传）
 */
export async function loadAuthorContext(
  harnessRoot: string,
  phase: string,
  feature: string,
): Promise<AuthorContextResult> {
  const layout = detectRepoLayout(harnessRoot);
  const cfg = loadFrameworkConfig(layout.projectRoot);
  const resolved = loadResolvedProfile(layout.projectRoot, cfg);

  const payload: HookDispatchPayload = {
    projectRoot: layout.projectRoot,
    phase: phase as Phase,
    feature,
    resolvedProfileName: resolved.name,
    hookEvent: 'on_context_load',
  };

  const { promptFragments, hookCheckResults } = await dispatchLifecycleHooks(
    harnessRoot,
    'on_context_load',
    payload,
    resolved,
    // 与 harness 同一开关：实例关掉生命周期钩子时，这里也一并静默——但那是**声明**的
    // 关闭，不是执行失败，两者的处置完全不同。
    { enabled: cfg.lifecycle_hooks_enabled !== false, timeoutMs: 30000 },
  );

  return {
    phase,
    feature,
    fragments: promptFragments,
    failures: hookCheckResults.filter(r => r.status === 'FAIL'),
  };
}

function render(result: AuthorContextResult): string {
  if (result.fragments.length === 0) {
    return '';
  }
  return result.fragments.join('\n\n');
}

async function main(): Promise<number> {
  const args = minimist(process.argv.slice(2), {
    string: ['phase', 'feature'],
    boolean: ['json', 'help'],
    alias: { p: 'phase', f: 'feature', h: 'help' },
  });

  if (args.help || !args.phase) {
    console.log(
      '用法：npx ts-node scripts/author-context.ts --phase <phase> [--feature <feature>] [--json]\n' +
      '在进入该 phase、动笔写主产物**之前**跑一次；输出即本阶段作者起手要读的内容。\n' +
      '无钩子时零输出、退出 0；钩子失败时打印原因、退出 1（不降级为空）。',
    );
    return args.phase ? 0 : 2;
  }

  const harnessRoot = path.resolve(__dirname, '..');
  const result = await loadAuthorContext(harnessRoot, String(args.phase), String(args.feature ?? ''));

  if (args.json) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    const body = render(result);
    if (body) console.log(body);
  }

  if (result.failures.length > 0) {
    for (const f of result.failures) {
      console.error(`[author-context] ${f.id}: ${f.details}`);
    }
    console.error(
      '[author-context] 作者起手内容未能完整取得——**不要**当作「本阶段没有额外要求」继续写。' +
      '先修好上面这个钩子再重跑。',
    );
    return 1;
  }
  return 0;
}

if (require.main === module) {
  main()
    .then(code => process.exit(code))
    .catch(err => {
      console.error(`[author-context] 内部错误：${(err as Error).message}`);
      process.exit(1);
    });
}
