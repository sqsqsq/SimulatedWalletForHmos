/**
 * 蓝图独立质询的交接与原件 —— 主执行者把候选交给宿主已有的隔离子代理质询，原样留下被评候选与回复；
 * 设计负责方处理问题后写原生 `review_summary.questioning`，每项的 `provenance.source_ref` 指向那份回复。
 *
 * 原件在蓝图工作区的 `blueprint/questioning/<轮次>/`：`candidate.yaml` 是派审那一刻的蓝图原样副本，
 * `reply.md` 是质询者的原样回复。它们是过程证据，不是第二份设计；这里只核路径，质询得对不对由评审判。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';

/** 这一轮交什么、原件放哪：范围取原生 requiredQuestioningScopes（`native` 是工程自己的 Framework），轮次取当前候选原始字节的摘要。 */
export function questioningRound(projectRoot, read, native) {
  const bytes = fs.readFileSync(path.join(projectRoot, ...read.canonical_path.split('/')));
  const dir = `${path.posix.dirname(read.canonical_path)}/questioning/${crypto.createHash('sha256').update(bytes).digest('hex').slice(0, 16)}`;
  const scopes = native.module('scripts/utils/blueprint-questioning.ts').requiredQuestioningScopes(read.blueprint);
  return { candidate: `${dir}/candidate.yaml`, reply: `${dir}/reply.md`, scopes: [...scopes] };
}

/** 记成完成的质询，每一项都要指向 `blueprint/questioning/` 下的原样回复，旁边留着被评候选。 */
export function questioningProblems(projectRoot, read) {
  const questioning = read.blueprint?.review_summary?.questioning;
  if (questioning?.status !== 'complete') return [];
  const base = `${path.posix.dirname(read.canonical_path)}/questioning/`;
  const exists = rel => fs.existsSync(path.join(projectRoot, ...rel.split('/')));
  const bad = (questioning.items ?? []).filter((item) => {
    const ref = String(item?.provenance?.source_ref ?? '');
    return !ref.startsWith(base) || !exists(ref) || !exists(`${path.posix.dirname(ref)}/candidate.yaml`);
  }).map(item => item?.question_id ?? item?.scope_ref ?? '（无编号）');
  if (!bad.length) return [];
  return [`蓝图 ${read.blueprint.blueprint_id} 的独立质询 ${bad.slice(0, 5).join('、')}${bad.length > 5 ? ` 等 ${bad.length} 项` : ''}`
    + `没有指向 \`${base}<轮次>/\` 下的原件（reply.md 及旁边的 candidate.yaml）——质询由宿主的隔离子代理执行、`
    + '主执行者原样留下回复，设计作者自己填写的记录不算质询'];
}
