const localPathRe = /\b(doc|src)\/[A-Za-z0-9_./-]+/g;
export function scanLocalPaths(text) {
  return [...text.matchAll(localPathRe)];
}
