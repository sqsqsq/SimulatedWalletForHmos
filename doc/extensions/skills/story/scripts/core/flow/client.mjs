/**
 * 问 `story_flow.py status` —— **JS 侧唯一的流程状态查询客户端**。
 *
 * 两个消费者（作者任务包、成文起手预检）问的是同一件事，所以只有这一处会拼脚本路径、
 * 轮解释器、解析 JSON。各写一套的话，其中一套迟早漏掉 `--project-root`——那一次运行里
 * 位置读的是脚本所在仓，材料与知识读的是目标工作区，而两半都写在同一份输入里。
 *
 * 这里只做一件事：**把问题问出去，把答案原样带回来**。要不要阻断、下一步做什么由调用方
 * 定——起手预检要拦，作者包只要把问题说清楚。
 */
import { spawnSync } from 'node:child_process';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

//: 正式入口就在上一级。调用方不传脚本位置：传了就等于允许两个消费者问不同的脚本。
const FLOW_SCRIPT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'story_flow.py');

//: 两个候选名是现有行为。**只有解释器起不动才换下一个**：已经跑起来并报了业务失败
//: 的，换个解释器只会得到同一句话，而原因在中途被换掉了。
const PYTHONS = ['python', 'python3'];

/**
 * @param {string} projectRoot 目标工程根——**必须显式传**，cwd 替代不了它：
 *   Python 侧没有 `--project-root` 时按脚本自身位置解析工程
 * @param {string} feature 需求名
 * @param {{timeoutMs?: number}} opts 调用方自己的超时，不在这里定一套配置
 * @returns {{data: object|null, error: string|null}} 两者恰有一个非空
 */
export function queryFlowStatus(projectRoot, feature, { timeoutMs } = {}) {
  const missing = [];
  for (const exe of PYTHONS) {
    const r = spawnSync(exe, [FLOW_SCRIPT, 'status', '--feature', feature,
      '--project-root', projectRoot],
    { encoding: 'utf-8', timeout: timeoutMs, windowsHide: true });
    if (r.error) {
      // **只有「这个解释器不在」才换候选**：超时、被杀、参数太长都说明它已经跑起来了，
      // 换一个只会得到同一句话，而原因在中途被换掉。
      if (r.error.code !== 'ENOENT') {
        return { data: null, error: `${exe} status 没跑完（${r.error.message}）` };
      }
      missing.push(`${exe}：${r.error.message}`);
    }
    else if (r.status !== 0) {
      return { data: null,
        error: `${exe} status 退出码 ${r.status}：${String(r.stderr || r.stdout || '').trim()}` };
    } else return parseStatus(r.stdout);
  }
  return { data: null, error: `起不动 python（${missing.join('；')}）` };
}

/** 输出是 JSON 加可能的日志行：从第一个 `{` 起解析，形状不对要说清缺什么。 */
function parseStatus(stdout) {
  const text = String(stdout ?? '');
  const at = text.indexOf('{');
  if (at < 0) return { data: null, error: 'status 没有输出 JSON' };
  let data = null;
  try {
    data = JSON.parse(text.slice(at));
  } catch (err) {
    return { data: null, error: `status 的输出解析不了（${err.message}）` };
  }
  const problem = shapeProblem(data);
  return problem ? { data: null, error: problem } : { data, error: null };
}

/**
 * 回来的是不是本合同说的形状 —— **「没走过 /story」不是坏形状**。
 *
 * 两者混成一件的代价是消费者分不清「这个需求还没开始」与「查询链坏了」：
 * 前者照常往下走，后者必须停下。
 */
function shapeProblem(data) {
  if (!data || typeof data !== 'object') return 'status 的输出不是一个对象';
  if (data.exists === false) return null;
  if (data.exists !== true) return 'status 的输出缺 exists';
  const state = data.material_state;
  if (state === undefined) return 'status 的输出缺 material_state（材料事实）';
  if (state === null) return null;             // 没有轮次：没有基准可比，合法为空

  if (!Array.isArray(state.pending) || typeof state.changed !== 'boolean') {
    return 'status 的 material_state 形状不对：要 {pending: [...], changed: true/false}';
  }
  return null;
}
