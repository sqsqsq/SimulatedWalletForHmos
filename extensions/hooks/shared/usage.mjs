/**
 * 使用记录的 MJS 桥接：`recordUsage` 经 stdin JSON 调 story 记录器（scripts/core/usage.py），不读写第二份 usage。
 * 调用方：story-knowledge 作者入口（knowledge-task.mjs）在开始 Feature 阶段时 begin，adapt 建立与检查记录文件（ensure / inspect）。
 * Framework 的阶段检查不再登记起点：检查不是开始工作，起止由作者入口与收尾请求定。
 */
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { runPython } from '../../skills/story/scripts/core/flow/client.mjs';

const STORY = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'skills', 'story');

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
