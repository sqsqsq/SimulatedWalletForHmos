/**
 * 使用记录的 MJS 桥接：默认导出是 Framework 六阶段的 pre_phase 钩子，具名 `recordUsage` 给 adapt 建立与检查记录文件
 * （ensure / inspect）调用；都经 stdin JSON 调 story 记录器（scripts/core/usage.py），不读写第二份 usage。
 *
 * 钩子是阶段的刷新点：先按原生事实结算已有轮次，已完成过的阶段再跑一轮时登记这一轮的起点（同一轮重复进入保留原起点）。
 * 具名 `recordUsage` 也给 Story 交付门做阶段收尾（finalize）。
 * 正常返回 ok，不往 promptFragments 放计数或时间——审查对象不因统计写入而变；
 * 记录失败与自报身份待补都按 MINOR 检查项报出：看得见、FAIL 与 PASS 都进报告，但不改阶段结论；
 * 修好后任一正式入口重试即补记。
 */
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { runPython } from '../../skills/story/scripts/core/flow/client.mjs';

const STORY = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'skills', 'story');
const PHASES = ['spec', 'plan', 'coding', 'review', 'ut', 'testing'];

/** 调记录器执行一个动作；返回它的结果 `{ok, changed, errors, requirement, pending_identity, note}`，起不来也给同形结果。 */
export function recordUsage(projectRoot, action, { feature, step } = {}) {
  const r = runPython(path.join(STORY, 'scripts', 'core', 'usage.py'), ['--project-root', projectRoot],
    { timeoutMs: 60000, input: JSON.stringify({ action, feature, step }) });
  if (r.error) return { ok: false, errors: [r.error] };
  try {
    return JSON.parse(String(r.stdout ?? '').trim().split(/\r?\n/).pop());
  } catch {
    return { ok: false, errors: [`使用记录器没给出结果（退出码 ${r.status}）：${r.output.slice(0, 300)}`] };
  }
}

export default async function usageHook(ctx) {
  if (!ctx?.feature || !ctx?.projectRoot || !PHASES.includes(ctx.phase)) return { ok: true };
  const r = recordUsage(ctx.projectRoot, 'phase', { feature: ctx.feature, step: ctx.phase });
  if (!r.ok) {
    return { ok: false, severityOverride: 'MINOR',
      message: `使用记录没写成（本阶段检查照常进行）：${(r.errors ?? []).join('；')}——修好原因后，阶段闭环后的收尾命令按原生事实补记，本阶段不用为它重跑` };
  }
  // 待补自报身份走检查项（MINOR，不改阶段结论；FAIL 与 PASS 都写进报告），不进审查提示片段
  return r.pending_identity ? { ok: false, severityOverride: 'MINOR', message: `${r.note}（不影响本阶段结论）` } : { ok: true };
}
