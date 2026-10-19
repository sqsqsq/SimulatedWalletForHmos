// 迷你夹具的使用记录桥接替身：只读核 doc/usage.json 是 schema 1 的记录；真实读取由 story 记录器承担，见 test_adapt_ownership
import * as fs from 'node:fs';
import * as path from 'node:path';

export function recordUsage(root) {
  try {
    const data = JSON.parse(fs.readFileSync(path.join(root, 'doc', 'usage.json'), 'utf-8'));
    return data.schema === 1 && data.requirements ? { ok: true, changed: false, errors: [] } : { ok: false, errors: ['不是 schema 1 的使用记录'] };
  } catch (e) {
    return { ok: false, errors: [String(e.message)] };
  }
}
