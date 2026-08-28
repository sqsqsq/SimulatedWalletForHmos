/**
 * post_check 的统一出口 —— 一处定义，六个阶段共用。
 *
 * 它替代了六份 post_check 里各写一遍的三段样板：入口守卫、报错文案拼装、留痕调用。
 * 同时补上三件基线态没有的事：
 *
 * ## 1. 顶层异常自报 BLOCKER
 * framework 的 dispatcher 在 hook 崩栈或超时时**退回 MAJOR**
 * （`hooks-dispatcher.ts:190-200`），于是「门禁自己坏了」与「门禁判它没问题」
 * 对闭环的影响相同——判据形同虚设却没人知道。这里兜住异常并显式声明 BLOCKER。
 *
 * ## 2. 报错一次列全，包括**被跳过的那些**
 * 判据之间有本质依赖：产物不存在就没法校验产物内容。基线态遇到这种依赖直接静默跳过，
 * 于是作者补完一层、下一层才浮出来，同一个 check id 洋葱式 FAIL 五次
 * （实测 spec 阶段一次运行里 5 轮）。这里要求调用方把跳过的判据连同**为什么跳过**
 * 一起交出来，随报错一并列出——作者一眼看到后面还有几关，而不是修一层撞一层。
 *
 * ## 3. 首行指向 author.md
 * 报错的第一句永远是「先读 <本阶段的 author.md>」。作者不必从判据文案反推要求，
 * 更不必去读脚本源码——那是基线态耗掉大半门禁回环时间的动作。
 */
import { STATUS, writePostCheckEvidence } from './evidence.mjs';

/** 每个阶段的作者须知位置（本文件不含任何业务字面，只有路径模板）。 */
export function authorDoc(phase) {
  return `doc/extensions/hooks/${phase}/author.md`;
}

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
          + `——本阶段的扩展判据一条都没跑完，结论不可用。`
          + `处置：把这条异常连同 ${authorDoc(phase)} 一起反馈给扩展维护者；`
          + `在修好之前不要把本次 harness 结果当作通过。`,
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
 *   checks?: {id: string, status: string, detail?: string}[],
 *   inputs?: string[],
 *   fix?: string,
 * }} r
 *   `problems` 逐条是「哪里不对 + 该怎么写」；`skipped` 是因前置缺失而没能执行的判据，
 *   即使本次没有 problems 也要报出来——「没报错」不等于「都查过了」。
 */
export function gate(ctx, r) {
  const problems = (r?.problems ?? []).filter(Boolean);
  const skipped = (r?.skipped ?? []).filter(s => s && s.what);
  const doc = authorDoc(ctx.phase);

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

  const parts = [`先读 ${doc}——本阶段扩展要求的全部内容都在那一页。`];
  parts.push(`以下 ${problems.length} 处需要修正（一次列全，不必逐轮试）：`);
  problems.forEach((p, i) => parts.push(`${i + 1}. ${p}`));
  if (skipped.length) {
    parts.push(`另有 ${skipped.length} 条判据因前置缺失未能执行，补齐后会继续检查：`
      + skipped.map(s => `${s.what}（${s.why}）`).join('；'));
  }
  if (r?.fix) parts.push(r.fix);

  return { ok: false, severityOverride: 'BLOCKER', message: parts.join('\n') };
}
