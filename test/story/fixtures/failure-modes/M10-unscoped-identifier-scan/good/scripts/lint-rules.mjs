const localPathRe = /\b(doc|src)\/[A-Za-z0-9_./-]+/g;
// 作用域：附录外主叙事；附录内承载工程范围是合法的
const EXEMPT_SECTIONS = [/^#{1,3}\s*附录/];
export function scanLocalPaths(text) {
  const main = splitBeforeAppendix(text, EXEMPT_SECTIONS);
  return [...main.matchAll(localPathRe)];
}
