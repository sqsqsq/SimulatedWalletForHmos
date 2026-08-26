/**
 * 扩展门禁留痕 —— **通过也写**。
 *
 * 框架的 hooks-dispatcher 只在 hook 返回 `ok:false` 时把结果记进 harness 报告；
 * 通过的那次什么都不留。于是「判据跑了并且通过」与「判据根本没跑」在产物上完全同形，
 * 事后无从分辨——批次验收要证明某条判据在真实链路上生效过，就没有任何证据可举。
 *
 * 所以每个 post_check 在返回前写一份运行留痕：判据 id、结果、被检产物的指纹。
 * 它**不是** verifier 报告，也不参与阻断——阻断的唯一正规出口仍是 `ok:false`。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { featureRoot, readTextOrNull, relDisplay } from './paths.mjs';

/** 留痕文件名（各阶段 reports 目录下一份，覆盖写）。 */
const EVIDENCE_FILE = 'ext-post-check.json';

/** 判据结果的封闭取值。 */
export const STATUS = {
  PASS: 'PASS',
  FAIL: 'FAIL',
  NOT_APPLICABLE: 'NOT_APPLICABLE',
};

function sha256(text) {
  return crypto.createHash('sha256').update(text, 'utf-8').digest('hex').slice(0, 16);
}

/**
 * 写一次运行留痕。
 *
 * @param {{projectRoot: string, feature: string, phase: string}} ctx
 * @param {{checks: {id: string, status: string, detail?: string}[], inputs?: string[]}} payload
 *   `inputs` 是被检产物的绝对路径列表，读得到的取内容指纹，读不到记 `missing`。
 *
 * 写失败不改判据结论（留痕是证据，不是判据本身），但要**出声**到 stderr——
 * 悄悄失败的话，验收时会把「留痕写不出来」误当成「判据没跑」。
 */
export function writePostCheckEvidence(ctx, payload) {
  const dir = path.join(featureRoot(ctx.projectRoot, ctx.feature), ctx.phase, 'reports');
  const file = path.join(dir, EVIDENCE_FILE);
  const record = {
    phase: ctx.phase,
    feature: ctx.feature,
    at: new Date().toISOString(),
    checks: (payload?.checks ?? []).map(c => ({
      id: String(c?.id ?? ''),
      status: String(c?.status ?? ''),
      detail: String(c?.detail ?? ''),
    })),
    inputs: (payload?.inputs ?? []).map(abs => {
      const text = readTextOrNull(abs);
      return {
        path: relDisplay(ctx.projectRoot, abs),
        sha256: text === null ? 'missing' : sha256(text),
      };
    }),
  };
  try {
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(file, JSON.stringify(record, null, 2) + '\n', 'utf-8');
  } catch (e) {
    process.stderr.write(
      `[ext] 门禁留痕写不出来（${relDisplay(ctx.projectRoot, file)}）：${e.message}\n`);
  }
}
