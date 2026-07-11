/**
 * visual-rounds-ledger.ts — t1（plan f7a3d9c2）：视觉迭代轮次账本 + 指纹级 no-progress
 * 熔断的 SSOT 纯逻辑层。
 *
 * 定位：telemetry/标注侧车（非判定文件，不含 verdict/分数/签字——tamper-scan 红线外）。
 * 账本行由 harness-runner 在 check 之后追加（runner 写、check 只读判定）；goal-runner
 * 在 gate/resume 时反向对账（events.jsonl ↔ ledger 的 row_hash，运行时一致性防护——
 * events 与 ledger 均在 agent 可写工作区，本模块不宣称对协同篡改双文件的密码学防护）。
 *
 * 轮次模型（rev4/rev5/rev6 三轮 review 收敛）：
 * - base_state_hash = hash(build_fingerprint, screens_hash, defect_fingerprints,
 *   source_fail_hit_ids, fingerprintable)——source_fail_hit_ids 取**计算 fuse 之前**的
 *   base hit id 集（排除 visual_diff_no_progress_fuse 自身与派生聚合 hit，防反馈环）。
 * - round_key = (loop_id, attempt_id, base_state_hash)。goal 态 attempt_id=invocation
 *   唯一 id（跨 --resume 单调，禁 retries+1）；交互态 attempt_id=null → 收窄：同状态
 *   重跑幂等吞（不判 no_fix_attempt），fuse 只覆盖"状态变了指纹没变"（ineffective_fix）。
 * - duplicate（同 round_key 已在账本）→ 不追加、**重放该行 decision**（fuse 裁决是轮次
 *   属性而非执行副作用——agent 自跑首检 fuse 后，外层 gate 必须仍能看到并 halt）。
 * - 熔断条件：与同 loop_id 最后一有效行（fingerprintable）比较，两轮指纹集**非空**且
 *   相等 + 本轮 awaitHumanOnly=false + 存在 actionable visual residual → fused。
 * - 归因：build 不同 → ineffective_fix（修了没用）；build 相同 → no_fix_attempt（跑了没修）。
 */

import * as crypto from 'crypto';
import * as fs from 'fs';
import * as path from 'path';
import { featureDir } from '../../config';

export const VISUAL_ROUNDS_LEDGER_SCHEMA_VERSION = '1.0';

export interface VisualRoundDecision {
  fused: boolean;
  failure_kind?: 'no_progress_fuse';
  attribution?: 'no_fix_attempt' | 'ineffective_fix';
  /** 熔断时的残差指纹清单（halt 求人时的交付物） */
  residual_fingerprints?: string[];
}

export interface VisualRoundRow {
  schema_version: string;
  at: string;
  loop_id: string;
  goal_run_id?: string;
  attempt_id?: string;
  base_state_hash: string;
  build_fingerprint: string;
  screens_hash: string;
  defect_fingerprints: string[];
  source_fail_hit_ids: string[];
  fingerprintable: boolean;
  decision: VisualRoundDecision;
  row_hash: string;
}

export interface VisualRoundEvaluation {
  disposition: 'appended' | 'duplicate';
  decision: VisualRoundDecision;
  /** disposition=appended：待追加的新行（含 row_hash）；duplicate：命中的既有行 */
  row: VisualRoundRow;
  /** 读取账本时跳过的损坏行数（崩溃半行等，>0 时调用方发 WARN 注记） */
  corrupt_lines: number;
}

/** 账本路径（feature 侧车，与 critic-receipt 同目录层级） */
export function visualRoundsLedgerPath(projectRoot: string, feature: string): string {
  return path.join(featureDir(projectRoot, feature), 'device-testing', 'reports', 'visual-rounds.ledger.jsonl');
}

/**
 * canonical JSON：键按字典序递归排序、无空白——row_hash 的唯一序列化口径
 * （字段序/换行/缩进不参与 hash；数组保持语义序，语义上无序的数组由调用方先排序）。
 */
export function canonicalJson(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  const rec = value as Record<string, unknown>;
  const keys = Object.keys(rec).filter(k => rec[k] !== undefined).sort();
  return `{${keys.map(k => `${JSON.stringify(k)}:${canonicalJson(rec[k])}`).join(',')}}`;
}

/** row_hash = sha256(canonicalJson(去 row_hash 后的行)) 前 16 hex */
export function computeRowHash(row: Omit<VisualRoundRow, 'row_hash'>): string {
  return crypto.createHash('sha256').update(canonicalJson(row)).digest('hex').slice(0, 16);
}

/**
 * base_state_hash——评估状态身份。输入数组在此排序（顺序无关）；
 * source_fail_hit_ids 由调用方保证为 fuse 计算之前的 base 集（排除 fuse 自身/派生聚合 hit）。
 */
export function computeBaseStateHash(input: {
  buildFingerprint: string;
  screensHash: string;
  defectFingerprints: string[];
  sourceFailHitIds: string[];
  fingerprintable: boolean;
}): string {
  const key = canonicalJson({
    build: input.buildFingerprint,
    screens: input.screensHash,
    fingerprints: [...input.defectFingerprints].sort(),
    fail_hits: [...input.sourceFailHitIds].sort(),
    fingerprintable: input.fingerprintable,
  });
  return crypto.createHash('sha256').update(key).digest('hex').slice(0, 16);
}

/** 读账本：逐行 JSON.parse，损坏行（崩溃半行等）计数跳过、绝不中断 */
export function readVisualRoundsLedger(ledgerPath: string): { rows: VisualRoundRow[]; corruptLines: number } {
  if (!fs.existsSync(ledgerPath)) return { rows: [], corruptLines: 0 };
  const rows: VisualRoundRow[] = [];
  let corruptLines = 0;
  const raw = fs.readFileSync(ledgerPath, 'utf-8');
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      const parsed = JSON.parse(trimmed) as VisualRoundRow;
      if (
        parsed && typeof parsed === 'object' &&
        typeof parsed.loop_id === 'string' &&
        typeof parsed.base_state_hash === 'string' &&
        Array.isArray(parsed.defect_fingerprints) &&
        typeof parsed.fingerprintable === 'boolean' &&
        parsed.decision && typeof parsed.decision.fused === 'boolean'
      ) {
        rows.push(parsed);
      } else {
        corruptLines++;
      }
    } catch {
      corruptLines++;
    }
  }
  return { rows, corruptLines };
}

export interface VisualRoundInput {
  loopId: string;
  /** goal 态=invocation 唯一 id（跨 resume 单调）；交互态=null（收窄语义） */
  attemptId: string | null;
  goalRunId: string | null;
  /** 当前构建指纹；不可算时传空串（仍参与状态身份） */
  buildFingerprint: string;
  screensHash: string;
  defectFingerprints: string[];
  sourceFailHitIds: string[];
  fingerprintable: boolean;
  /** rev5：仅 awaitHumanOnly=false 才计算 fuse（candidate-pass/求人路径优先） */
  awaitHumanOnly: boolean;
  /** rev5：结构化 actionable visual residual 谓词结果（非前缀判断，调用方计算） */
  actionableResidual: boolean;
  now?: () => string;
}

/**
 * 评估当前轮：只读账本 → duplicate 重放 / 新轮算 decision。**不写盘**——追加由
 * harness-runner 在 check 后调用 appendVisualRound（disposition=appended 时）。
 */
export function evaluateVisualRound(ledgerPath: string, input: VisualRoundInput): VisualRoundEvaluation {
  const { rows, corruptLines } = readVisualRoundsLedger(ledgerPath);
  const loopRows = rows.filter(r => r.loop_id === input.loopId);
  const baseStateHash = computeBaseStateHash({
    buildFingerprint: input.buildFingerprint,
    screensHash: input.screensHash,
    defectFingerprints: input.defectFingerprints,
    sourceFailHitIds: input.sourceFailHitIds,
    fingerprintable: input.fingerprintable,
  });

  // duplicate 判定：goal 态=同 (loop, attempt, state)；交互态（attempt 缺失）=同 (loop, state)。
  // 取**最后一个**命中行重放（同 round 可能被多次执行，decision 恒一致）。
  const isDuplicateOf = (r: VisualRoundRow): boolean => {
    if (r.base_state_hash !== baseStateHash) return false;
    if (input.attemptId !== null) return r.attempt_id === input.attemptId;
    return true;
  };
  const dupRow = [...loopRows].reverse().find(isDuplicateOf);
  if (dupRow) {
    return { disposition: 'duplicate', decision: dupRow.decision, row: dupRow, corrupt_lines: corruptLines };
  }

  // 新轮：与同 loop 最后一有效行（fingerprintable）比较，算 decision。
  const prevEligible = [...loopRows].reverse().find(r => r.fingerprintable);
  const currentSorted = [...input.defectFingerprints].sort();
  let decision: VisualRoundDecision = { fused: false };
  if (
    prevEligible &&
    input.fingerprintable &&
    !input.awaitHumanOnly &&
    input.actionableResidual &&
    currentSorted.length > 0 &&
    prevEligible.defect_fingerprints.length === currentSorted.length &&
    [...prevEligible.defect_fingerprints].sort().every((v, i) => v === currentSorted[i])
  ) {
    decision = {
      fused: true,
      failure_kind: 'no_progress_fuse',
      attribution:
        prevEligible.build_fingerprint !== input.buildFingerprint ? 'ineffective_fix' : 'no_fix_attempt',
      residual_fingerprints: currentSorted,
    };
  }

  const rowBase: Omit<VisualRoundRow, 'row_hash'> = {
    schema_version: VISUAL_ROUNDS_LEDGER_SCHEMA_VERSION,
    at: (input.now ?? (() => new Date().toISOString()))(),
    loop_id: input.loopId,
    ...(input.goalRunId ? { goal_run_id: input.goalRunId } : {}),
    ...(input.attemptId !== null ? { attempt_id: input.attemptId } : {}),
    base_state_hash: baseStateHash,
    build_fingerprint: input.buildFingerprint,
    screens_hash: input.screensHash,
    defect_fingerprints: currentSorted,
    source_fail_hit_ids: [...input.sourceFailHitIds].sort(),
    fingerprintable: input.fingerprintable,
    decision,
  };
  const row: VisualRoundRow = { ...rowBase, row_hash: computeRowHash(rowBase) };
  return { disposition: 'appended', decision, row, corrupt_lines: corruptLines };
}

/** 追加账本行（disposition=appended 时由 harness-runner 调用）。 */
export function appendVisualRound(ledgerPath: string, row: VisualRoundRow): void {
  fs.mkdirSync(path.dirname(ledgerPath), { recursive: true });
  fs.appendFileSync(ledgerPath, `${JSON.stringify(row)}\n`, 'utf-8');
}

// ---------------------------------------------------------------------------
// rev6：events ↔ ledger 反向对账（goal gate / resume 启动时调用）
// ---------------------------------------------------------------------------

export interface LedgerIntegrityIssue {
  kind: 'missing_row' | 'modified_row' | 'orphan_pending_stale';
  detail: string;
}

/**
 * goal 态一致性对账：events.jsonl 中记录的期望 row_hash 集 vs ledger 中同 loop_id 行。
 * - events 有、ledger 无 → missing_row（删账本行=绕 fuse，integrity FAIL）；
 * - ledger 行 row_hash 重算不符 → modified_row（改行/改 decision）；
 * - ledger 有、events 无 → pending 行：仅当其 attempt_id ∈ pendingAttemptIds（当前/
 *   最近一次 invocation，外层尚未提交 events）才可收养；否则 orphan_pending_stale。
 * ledger 文件缺失但 events 期望非空 → 全部 missing_row（损坏≠空历史）。
 */
export function reconcileLedgerWithEvents(input: {
  ledgerPath: string;
  loopId: string;
  expectedRowHashes: string[];
  pendingAttemptIds: string[];
}): { ok: boolean; issues: LedgerIntegrityIssue[] } {
  const issues: LedgerIntegrityIssue[] = [];
  const { rows } = readVisualRoundsLedger(input.ledgerPath);
  const loopRows = rows.filter(r => r.loop_id === input.loopId);
  const ledgerHashes = new Set(loopRows.map(r => r.row_hash));
  for (const expected of input.expectedRowHashes) {
    if (!ledgerHashes.has(expected)) {
      issues.push({
        kind: 'missing_row',
        detail: `events 期望 row_hash=${expected} 在账本缺失（删行/损坏不解释成空历史）`,
      });
    }
  }
  const expectedSet = new Set(input.expectedRowHashes);
  for (const r of loopRows) {
    const { row_hash: declared, ...rest } = r;
    const actual = computeRowHash(rest);
    if (actual !== declared) {
      issues.push({
        kind: 'modified_row',
        detail: `账本行 ${declared} 重算 hash=${actual} 不符（行内容/decision 被改）`,
      });
      continue;
    }
    if (!expectedSet.has(declared)) {
      const pendingOk = r.attempt_id !== undefined && input.pendingAttemptIds.includes(r.attempt_id);
      if (!pendingOk) {
        issues.push({
          kind: 'orphan_pending_stale',
          detail: `账本行 ${declared}（attempt=${r.attempt_id ?? 'n/a'}）不在 events 期望集且非当前 invocation 的 pending 行`,
        });
      }
    }
  }
  return { ok: issues.length === 0, issues };
}
