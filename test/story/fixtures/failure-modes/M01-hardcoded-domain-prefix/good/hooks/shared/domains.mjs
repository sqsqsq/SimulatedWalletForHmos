// 正例：条目清单运行期从激活知识派生，代码里没有任何域字面
import { activeKnowledge } from './knowledge.mjs';
export function coverage(projectRoot, rows) {
  const entries = activeKnowledge(projectRoot).constraints.flatMap((c) => c.entries);
  if (!entries.length) throw new Error('派生为空：激活清单没有解析出任何条目');
  return entries.map((e) => e.id).filter((id) => !rows.includes(id));
}
