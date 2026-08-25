/**
 * 复述判定的逐分支冻结预期。
 *
 * **调用真实模块**（`doc/extensions/hooks/shared/paraphrase.mjs`），不在测试侧重实现一份——
 * 重实现出来的是「测试对测试」，判据一改两边就分叉。
 *
 * **逐条比对，不合并计数**：多分支合并成一个通过率时，单个分支全灭也能凑数通过。
 *
 * 用法：node test/story/scripts/check_paraphrase_branches.mjs
 * 退出码：0 全部符合预期；1 有分支偏离。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, '..', '..', '..');
const fixturePath = path.join(repoRoot, 'test', 'story', 'fixtures', 'knowledge', 'adversarial.json');
const modulePath = path.join(repoRoot, 'doc', 'extensions', 'hooks', 'shared', 'paraphrase.mjs');

const { classify, SIMILARITY_HINT_THRESHOLD } = await import(
  new URL(`file://${modulePath.replace(/\\/g, '/')}`).href
);

const fixture = JSON.parse(fs.readFileSync(fixturePath, 'utf-8'));
const { source, own_terms: ownTerms, cases } = fixture;

let failed = 0;
console.log('复述判定 · 逐分支冻结预期');
console.log(`来源：「${source}」`);
console.log(`相似度提示阈值：${SIMILARITY_HINT_THRESHOLD}（只影响排序，不参与判定）`);
console.log('─'.repeat(78));

for (const c of cases) {
  const got = classify(c.text, [source], ownTerms);
  const problems = [];
  if (c.expect_verdict && got.verdict !== c.expect_verdict) {
    problems.push(`verdict 期望 ${c.expect_verdict}，实际 ${got.verdict}`);
  }
  if (c.expect_not_verdict && got.verdict === c.expect_not_verdict) {
    problems.push(`verdict 不应为 ${c.expect_not_verdict}`);
  }
  if (typeof c.expect_similarity_at_least === 'number'
    && got.similarity < c.expect_similarity_at_least) {
    problems.push(`相似度期望 ≥${c.expect_similarity_at_least}，实际 ${got.similarity.toFixed(2)}`);
  }
  const status = problems.length ? 'FAIL' : 'PASS';
  if (problems.length) failed++;
  console.log(`[${status}] ${c.id}`);
  console.log(`        判定 ${got.verdict}  相似度 ${got.similarity.toFixed(2)}  信号：${got.reasons.join('；') || '无'}`);
  if (problems.length) console.log(`        ✗ ${problems.join('；')}`);
}

console.log('─'.repeat(78));
console.log(`分支 ${cases.length} 条：PASS ${cases.length - failed}，FAIL ${failed}`);
process.exit(failed ? 1 : 0);
