export function activeKnowledge(projectRoot) {
  try {
    return parseManifest(projectRoot);
  } catch {
    return [];
  }
}
