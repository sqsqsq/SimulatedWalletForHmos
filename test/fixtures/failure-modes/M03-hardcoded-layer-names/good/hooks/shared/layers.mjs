// 正例：层清单从架构 DSL 读
import { readConfig } from './paths.mjs';
export function outerLayers(projectRoot) {
  const ids = readConfig(projectRoot)?.architecture?.outer_layers?.map((l) => l.id) ?? [];
  if (!ids.length) throw new Error('派生为空：架构 DSL 未声明外层');
  return ids;
}
