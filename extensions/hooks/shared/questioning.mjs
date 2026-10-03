/**
 * 蓝图独立质询的任务投影 —— 主执行者把候选交给宿主的隔离子代理质询，原样留下被评候选与回复，
 * 设计负责方处理后写原生 `review_summary.questioning`。候选与回复的绑定和资格由原生执行合同定义，本模块给范围与原件位置。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';

/** 这一轮交什么、原件建议放哪：范围取原生 requiredQuestioningScopes（`native` 是工程自己的 Framework），轮次取当前候选原始字节的摘要。 */
export function questioningRound(projectRoot, read, native) {
  const bytes = fs.readFileSync(path.join(projectRoot, ...read.canonical_path.split('/')));
  const dir = `${path.posix.dirname(read.canonical_path)}/questioning/${crypto.createHash('sha256').update(bytes).digest('hex').slice(0, 16)}`;
  const scopes = native.module('scripts/utils/blueprint-questioning.ts').requiredQuestioningScopes(read.blueprint);
  return { candidate: `${dir}/candidate.yaml`, reply: `${dir}/reply.md`, scopes: [...scopes] };
}
