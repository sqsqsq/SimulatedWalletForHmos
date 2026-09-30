/**
 * 成文的设计来源：流程契约关联的蓝图（原生读取、已准入、评审投影对得上这一版）与登记的冻结输入。
 *
 * 附录机器区、术语起始行与材料清单都从这里取，Story 不再读 Spec。来源不成立时给出缺口与责任方，
 * 调用方按它停下——不拿空来源当「这一节不涉及」。同一条命令只读一次。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { readBlueprint } from '../../../../../hooks/shared/framework-access.mjs';
import { knowledgeRegistrations } from '../../../../../hooks/shared/knowledge.mjs';
import { extensionRoot } from '../../../../../hooks/shared/paths.mjs';
import { readJson } from './context.mjs';

const sha256 = (data) => crypto.createHash('sha256').update(data).digest('hex');

const cache = new WeakMap();

/** 冻结快照：按登记的路径读，原始字节摘要要等于登记值。 */
function readSnapshot(ctx, input, problems) {
  const file = path.join(ctx.projectRoot, ...String(input.snapshot_ref).split('/'));
  let bytes;
  try {
    bytes = fs.readFileSync(file);
  } catch {
    problems.push(`冻结输入 ${input.snapshot_ref} 读不到——设计输入由 \`story_flow.py complete\` 冻结，已登记的版本不能删`);
    return null;
  }
  if (crypto.createHash('sha256').update(bytes).digest('hex') !== input.snapshot_sha256) {
    problems.push(`冻结输入 ${input.snapshot_ref} 的字节与登记的摘要对不上——冻结版本不改，换输入走 reopen 或 update 后重新 complete`);
    return null;
  }
  return { ...JSON.parse(bytes.toString('utf-8')), dir: path.dirname(file) };
}

/**
 * @returns {{blueprint: object|null, ref: object|null, snapshot: object|null, problems: string[]}}
 */
export function designSource(ctx) {
  if (cache.has(ctx)) return cache.get(ctx);
  const problems = [];
  const flow = readJson(ctx.flowPath, null);
  const binding = flow?.design_binding;
  const input = flow?.input;
  const out = { blueprint: null, ref: null, snapshot: null, problems };
  if (!binding?.blueprint_id || !input?.snapshot_ref) {
    problems.push('AR/story-src/story-flow.json：没有设计关联或登记的设计输入——成文按已准入的蓝图写，'
      + '先 `story_flow.py bind-design` 与 `complete` 把需求交给设计');
  } else {
    out.snapshot = readSnapshot(ctx, input, problems);
    const read = readBlueprint(ctx.projectRoot, binding.blueprint_id, 'delivery');
    if (read.status !== 'ok') {
      problems.push(`蓝图 ${binding.blueprint_id}：${read.status === 'not_admitted' ? '还没准入' : `原生读取 ${read.status}`}`
        + `${read.issues?.length ? `（${read.issues.slice(0, 3).map(i => i.code ?? i.id).join('、')}）` : ''}`
        + '——成文按已准入的蓝图写，由设计职责在 component-design 里走到准入');
    } else if (read.blueprint?.component_id !== binding.component_id) {
      problems.push(`蓝图 ${binding.blueprint_id} 归属组件 ${read.blueprint?.component_id}，不是本需求关联的 ${binding.component_id}`);
    } else if (read.projection?.status !== 'valid') {
      problems.push(`蓝图 ${binding.blueprint_id} 的评审投影 ${read.projection?.path}`
        + `${read.projection?.status === 'missing' ? '还没生成' : '与当前 revision 对不上'}——由设计职责按原生 renderer 生成，Extension 不手改`);
    } else {
      out.blueprint = read.blueprint;
      out.ref = read.blueprint_ref;
    }
  }
  cache.set(ctx, out);
  return out;
}

/** 激活知识的确定性摘要：有序的激活登记（路径、受众、摘要）与每份知识文件的原始字节。 */
function knowledgeDigest(ctx) {
  const rows = knowledgeRegistrations(ctx.projectRoot).map((r) => {
    let bytes = null;
    try {
      bytes = fs.readFileSync(path.join(extensionRoot(ctx.projectRoot), ...r.file.split('/')));
    } catch {
      bytes = null;
    }
    return { file: r.file, audience: r.audience, summary: r.summary, sha256: bytes === null ? null : sha256(bytes) };
  });
  return sha256(JSON.stringify(rows));
}

/**
 * 这一刻的成文依据：设计引用（原生完整 blueprint_ref）、登记的冻结输入、激活知识。
 * 登记（`story_flow.py story` 经 `story-build basis`）与核对（check、交付门）用同一份计算。
 */
export function currentBasis(ctx) {
  const source = designSource(ctx);
  const flow = readJson(ctx.flowPath, null);
  return {
    problems: source.problems, blueprint_ref: source.ref,
    input_sha256: flow?.input?.snapshot_sha256 ?? null, knowledge_sha256: knowledgeDigest(ctx),
  };
}

/** 成文登记之后，设计、输入或知识换了没有——换了的，登记说的就不是现在这份。文件的改动由登记指纹另核。 */
export function basisDriftProblems(ctx) {
  const flow = readJson(ctx.flowPath, null);
  if (flow?.status !== 'story_written') return [];
  const basis = flow.story_basis;
  if (!basis) {
    return ['AR/story-src/story-flow.json：记着已成文登记，却没有成文依据 story_basis，契约不完整'
      + '——跑 `story_flow.py story --feature <名>` 按当前内容重新登记'];
  }
  const now = currentBasis(ctx);
  if (now.problems.length) return now.problems;
  const again = '——改完跑 `story_flow.py story` 重投附录并重新登记，重新审查';
  const out = [];
  const was = basis.blueprint_ref ?? {};
  if (was.artifact_sha256 !== now.blueprint_ref?.artifact_sha256 || was.revision !== now.blueprint_ref?.revision) {
    out.push(`登记之后蓝图变了（登记时 r${was.revision}，现在 r${now.blueprint_ref?.revision}）${again}`);
  }
  if (basis.input_sha256 !== now.input_sha256) out.push(`登记之后交给设计的输入换了版本${again}`);
  if (basis.knowledge_sha256 !== now.knowledge_sha256) out.push(`登记之后激活知识或知识原文变了${again}`);
  return out;
}

/** 蓝图里确认过的术语（`subject: term:<术语>` 的事实）：只给术语，解释由作者从来源写，不拿模块名代替。 */
export function termFacts(blueprint) {
  return (blueprint?.discovery?.facts ?? [])
    .filter(f => String(f?.subject ?? '').startsWith('term:'))
    .map(f => [String(f.subject).slice('term:'.length).trim(), ''])
    .filter(([term]) => term);
}
