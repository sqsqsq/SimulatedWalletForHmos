/**
 * post_check 的统一出口 —— 六个阶段共用：入口守卫、报错文案、留痕调用。
 *
 * ## 1. 顶层异常自报 BLOCKER
 * framework 的 dispatcher 对 hook 崩栈或超时按 MAJOR 处理，「门禁自己坏了」与「门禁判它没问题」
 * 对闭环的影响就相同。这里兜住异常并显式声明 BLOCKER。
 *
 * ## 2. 报错一次列全，包括**被跳过的那些**
 * 判据之间有依赖：产物不存在就没法校验产物内容。调用方把跳过的判据连同**为什么跳过**
 * 一起交出来，随报错一并列出——作者一眼看到后面还有几关。
 *
 * ## 3. 每条问题自带在哪、什么问题、机制
 * 判出问题的那条检查把它写成「<在哪>：<问题>——<机制>」，怎么修由作者按规则与机制判断；
 * 出口只负责编号列全，不加统一的开头与结尾。
 */
import { STATUS, writePostCheckEvidence } from './evidence.mjs';

/**
 * 包住 post_check 主体：入口守卫 + 顶层 try/catch。
 *
 * @param {string} phase 本 hook 服务的阶段
 * @param {(ctx: any) => Promise<any>|any} body 判据主体，返回 `gate()` 的结果
 */
export function guard(phase, body) {
  return async function postCheckHook(ctx) {
    if (ctx?.phase !== phase || !ctx?.feature || !ctx?.projectRoot) {
      return { ok: true };
    }
    try {
      return await body(ctx);
    } catch (e) {
      // 崩栈不是「通过」，也不该被降级成 MAJOR 悄悄放行。
      return {
        ok: false,
        severityOverride: 'BLOCKER',
        message: `扩展门禁自身异常（${phase} post_check）：${e?.message ?? e}`
          + `——异常出在门禁代码，本阶段的扩展判据没有跑完，这次 harness 结果不代表产物通过；`
          + `门禁代码由扩展维护者修。`,
      };
    }
  };
}

/**
 * 组装出口：写留痕（通过也写）→ 全绿返回 ok，否则一次列全。
 *
 * @param {{projectRoot: string, feature: string, phase: string}} ctx
 * @param {{
 *   problems?: string[],
 *   skipped?: {what: string, why: string}[],
 *   groups?: {name: string, problems?: string[], skipped?: {what: string, why: string}[]}[],
 *   checks?: {id: string, status: string, detail?: string}[],
 *   inputs?: string[],
 * }} r
 *   `problems` 逐条是「<在哪>：<问题>——<机制>」；`skipped` 是因前置缺失而没能执行的判据，
 *   即使本次没有 problems 也要报出来——「没报错」不等于「都查过了」。
 *   `groups` 是按数据前置分的组：每组自己决定能否执行，能执行的全部执行，报错按组分节，
 *   作者一眼看到每一类各有几处、还有哪一组等前置——而不是修完一类才看见下一类。
 */
export function gate(ctx, r) {
  const groups = (r?.groups ?? []).map(g => ({
    name: g.name,
    problems: (g.problems ?? []).filter(Boolean),
    skipped: (g.skipped ?? []).filter(s => s && s.what),
  }));
  const problems = [...(r?.problems ?? []).filter(Boolean), ...groups.flatMap(g => g.problems)];
  const skipped = [...(r?.skipped ?? []).filter(s => s && s.what), ...groups.flatMap(g => g.skipped)];

  const checks = r?.checks?.length
    ? r.checks
    : [{
        id: `ext_${ctx.phase}_gate`,
        status: problems.length ? STATUS.FAIL : STATUS.PASS,
        detail: `问题 ${problems.length} 条；未执行判据 ${skipped.length} 条`,
      }];
  // 跳过的判据本身就是留痕的一部分：事后要能分辨「查过且通过」与「压根没查」。
  for (const s of skipped) {
    checks.push({ id: s.id ?? `skipped:${s.what}`, status: STATUS.NOT_APPLICABLE, detail: s.why });
  }
  writePostCheckEvidence(ctx, { checks, inputs: r?.inputs ?? [] });

  if (!problems.length && !skipped.length) return { ok: true };
  if (!problems.length) {
    // 没有问题、但有判据没跑成：不阻断（没有证据说产物有错），但要让人看见缺口。
    return {
      ok: true,
      message: `扩展门禁有 ${skipped.length} 条判据未执行：`
        + skipped.map(s => `${s.what}（${s.why}）`).join('；'),
    };
  }

  const parts = [`以下 ${problems.length} 处需要修正（一次列全，不必逐轮试）：`];
  let n = 0;
  const ungrouped = (r?.problems ?? []).filter(Boolean);
  ungrouped.forEach(p => parts.push(`${++n}. ${p}`));
  for (const g of groups) {
    if (!g.problems.length) continue;
    parts.push(`【${g.name}】${g.problems.length} 处`);
    g.problems.forEach(p => parts.push(`${++n}. ${p}`));
  }
  if (skipped.length) {
    parts.push(`另有 ${skipped.length} 条判据因前置缺失未能执行，补齐后会继续检查：`
      + skipped.map(s => `${s.what}（${s.why}）`).join('；'));
  }

  return { ok: false, severityOverride: 'BLOCKER', message: parts.join('\n') };
}
