/**
 * 会话归属证据 —— 「这份 state 是不是本会话写的」按**一手记录**判，不按时间窗猜。
 *
 * ## 为什么需要它
 *
 * framework 的 runner 写 state 时不写 session_id（vendored，不改）。实例 hook 原来的补法是：
 * state 没盖章且在 grace 窗口内，就把**第一个触发 Stop 的会话**盖成所有者。
 * 同一个仓开两个会话时这必然串台——A 会话在跑 harness，B 会话恰好结束一条消息，
 * B 被盖成所有者：A 从此被当成「跨会话陈旧」（只 advisory），B 被反复拦在自己没跑过的阶段上。
 * 实测发生过 3 次，其中一次还把已经迁走的 feature 目录写活了。
 *
 * 会话自己的 transcript 是一手记录：**跑过那条 harness 命令的会话，才是这份 state 的所有者。**
 * grace 窗口保留，但只用来容忍「记录还没落盘」，不再单独构成所有权。
 */
import * as fs from 'node:fs';

/** transcript 里逐行 JSON，取出所有工具调用的输入对象。 */
function toolUseInputs(transcriptPath) {
  if (typeof transcriptPath !== 'string' || !transcriptPath.trim()) return [];
  let raw;
  try {
    raw = fs.readFileSync(transcriptPath, 'utf-8');
  } catch {
    return [];   // 读不到就是没有证据；调用方据此判「不是本会话」
  }
  const out = [];
  for (const line of raw.split(/\r?\n/)) {
    const s = line.trim();
    if (!s.startsWith('{')) continue;
    let obj;
    try {
      obj = JSON.parse(s);
    } catch {
      continue;
    }
    const content = obj?.message?.content;
    for (const part of Array.isArray(content) ? content : []) {
      if (part?.type === 'tool_use' && part.input && typeof part.input === 'object') {
        out.push({ name: String(part.name ?? ''), input: part.input });
      }
    }
  }
  return out;
}

/** 一次工具调用里出现过的命令行文本（不同工具的字段名不同，逐个取）。 */
function commandTexts(entry) {
  const i = entry.input;
  return [i.command, i.script, i.prompt]
    .filter(v => typeof v === 'string' && v)
    .join('\n');
}

/**
 * 本会话是否为 `<feature>/<phase>` 跑过 harness。
 *
 * 判据：transcript 里存在一次工具调用，其命令文本同时含 harness 的 runner 名与
 * `--feature <feature>`、`--phase <phase>`。三者同时出现才算——只含 runner 名的
 * 那次可能是别的 feature。
 */
export function sessionRanHarness(transcriptPath, feature, phase) {
  if (!feature || !phase) return false;
  const featureRe = new RegExp(`--feature[\\s=]+["']?${escapeRe(feature)}\\b`);
  const phaseRe = new RegExp(`--phase[\\s=]+["']?${escapeRe(phase)}\\b`);
  return toolUseInputs(transcriptPath).some(e => {
    const text = commandTexts(e);
    return /harness-runner/.test(text) && featureRe.test(text) && phaseRe.test(text);
  });
}

/** 本会话是否调起过 verifier 子 agent（报告归属的另一半证据）。 */
export function sessionSpawnedVerifier(transcriptPath) {
  return toolUseInputs(transcriptPath).some(e =>
    /^(Task|Agent)$/.test(e.name) && String(e.input?.subagent_type ?? '') === 'verifier');
}

function escapeRe(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
