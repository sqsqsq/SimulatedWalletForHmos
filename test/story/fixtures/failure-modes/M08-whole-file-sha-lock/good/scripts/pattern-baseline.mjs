// 正例：正文与元数据分开守——正文守 SHA，frontmatter 守键值
import { createHash } from 'node:crypto';
export function verifyPattern(text, baseline) {
  const [, frontmatter, body] = text.split(/\r?\n---\r?\n/, 3);
  const bodySha256 = createHash('sha256').update(body).digest('hex');
  const keysConserved = baseline.keys.every((k) => frontmatter.includes(k));
  return bodySha256 === baseline.body_sha256 && keysConserved;   // design-patterns
}
