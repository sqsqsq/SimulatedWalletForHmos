export function activeKnowledge(projectRoot) {
  const bundle = parseManifest(projectRoot);
  if (!bundle.constraints.length) {
    throw new Error('派生为空：激活清单未解析出任何规约条目——检查 manifest 与条目表表头');
  }
  return bundle;
}
