/**
 * 使用记录的 MJS 桥接：默认导出是 Framework 六阶段的 pre_phase 钩子，具名 `recordUsage` 给已有 MJS 入口
 * （spec/plan 作者任务包、story-build 写作入口、adapt 建立与检查记录文件的 ensure / inspect）调用；都经 stdin JSON 调 story 记录器（scripts/core/usage.py），
 * 不读写第二份 usage。
 *
 * 钩子只登记「确实进入了这一阶段检查」并对账本需求已有步骤：检查时刻不是开工时刻，不写起点。
 * 正常返回 ok，不往 promptFragments 放计数或时间——审查对象不因统计写入而变；
 * 记录失败与名称待补都按 MINOR 检查项报出：看得见、FAIL 与 PASS 都进报告，但不改阶段结论；
 * 修好后任一正式入口重试即补记。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { runPython } from '../../skills/story/scripts/core/flow/client.mjs';
import { featureRoot, relDisplay } from './paths.mjs';

const STORY = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'skills', 'story');
const CONTRACT = JSON.parse(fs.readFileSync(path.join(STORY, 'contracts', 'usage.json'), 'utf-8'));
const PHASES = ['spec', 'plan', 'coding', 'review', 'ut', 'testing'];

/** 调记录器执行一个动作；返回它的结果 `{ok, changed, errors, requirement, pending_init}`，起不来也给同形结果。 */
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
  const r = recordUsage(ctx.projectRoot, 'observe', { feature: ctx.feature, step: ctx.phase });
  if (!r.ok) {
    return { ok: false, severityOverride: 'MINOR',
      message: `使用记录没写成（本阶段检查照常进行）：${(r.errors ?? []).join('；')}——修好后重跑本阶段检查或任一 story 命令即可补记` };
  }
  // 待补初始化走检查项（MINOR，不改阶段结论；FAIL 与 PASS 都写进报告），不进审查提示片段
  return r.pending_init ? { ok: false, severityOverride: 'MINOR', message: pendingInitNote(ctx.projectRoot, ctx.feature, r.requirement) }
    : { ok: true };
}

/** 使用记录还在等首份名称与业务版本时给模型的一句话：输入文件位置与字段合同。 */
function pendingInitNote(projectRoot, feature, key) {
  const input = relDisplay(projectRoot, path.join(featureRoot(projectRoot, feature), CONTRACT.input_file));
  return `使用记录待补（不影响本阶段结论）：需求 ${key} 还没有名称与业务版本——在 ${input} 写 `
    + `{"requirement": "${key}", "name": <需求名称>, "version": <业务版本，判断为未知写 null>}（可选 agent、model），`
    + '下次本阶段检查或 story 命令自动接收';
}
