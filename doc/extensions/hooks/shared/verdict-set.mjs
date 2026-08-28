/**
 * 必答集派生 —— 本阶段 verifier 必须逐行裁决的集合，**一处派生、多处消费**。
 *
 * 消费者：pre_verifier（注入清单）、spec/plan 的 post_check（核对报告有没有逐行裁）。
 * 两边各存一份口径，改一处忘另一处就是「注入了 14 行、门禁只核 11 行」这类静默漏裁。
 *
 * ## 为什么是收窄后的全集
 *
 * 同一条结论在归档件附录、spec 出口章、契约冻结里各出现一次，那是**同一份结论的三次渲染**：
 * 附录由登记源渲染、出口章与登记源同文（各自有机械门禁保证），裁一次就够。
 * 全集指的是**登记源的每一行**：命中的条目、判不适用的整域、模式候选——一行不落。
 *
 * ## 域级判定
 *
 * 规约域的 frontmatter 有 `applies_when`：写 `always` 的域每条都要逐条判；
 * 条件域先判「这个域适不适用本需求」，判不适用就整域一行带依据，域内条目不再逐条登记。
 * 时机由规约自己承担，模型不必对着不相干的域逐条写「不涉及」。
 */
import * as path from 'node:path';
import { featureRoot, readTextOrNull } from './paths.mjs';
import { readContracts } from './contracts.mjs';
import { obligationsFromContracts, patternRolesFromContracts } from './obligations.mjs';

/**
 * 域级判定（条件域先判域）的**记录落点在归档件的符合性附录**，由 writer 写。
 *
 * 上一版另有一份判定登记件承载它，spec post_check 据此校验。
 * 那份登记件与 spec §10 表是同一批结论的两处写法——两处判定对不上时，
 * 评审者无从知道哪个是准的。它退场后，spec 阶段没有可校验的数据源：
 * 域级判定的完备性由 writer 的附录与 verifier 的语义判据管，机械层不假装判得了。
 */

function asArray(v) {
  return Array.isArray(v) ? v : [];
}


/**
 * 本阶段的必答集。
 *
 * @param {string} phase spec / plan（其它阶段沿用 plan 的冻结行）
 * @returns {{rows: object[], error: string|null}}
 *   派生失败 error 非空，调用方须出声——静默空集会让「逐行裁决」判据恒真。
 */
export function adjudicationSet(projectRoot, feature, phase) {
  if (phase === 'spec') return specSet(projectRoot, feature);
  return freezeSet(projectRoot, feature);
}

function specSet(projectRoot, feature) {
  // **数据源是 spec §10 表本身**，不是第二份登记件。
  // 上一版读另一份判定登记件：同一条结论有两处写法、两处判定，
  // 评审者看到互相矛盾的结论时无从知道哪个是准的。判定登记就是 §10 那张表。
  const specPath = path.join(featureRoot(projectRoot, feature), 'spec', 'spec.md');
  const text = readTextOrNull(specPath);
  if (text === null) return { rows: [], error: '读不到 spec/spec.md' };

  const rows = [];
  const all = text.split(/\r?\n/);
  const start = all.findIndex(l => /^#{2,4}\s+.*规约约束要求/.test(l.trim()));
  if (start < 0) {
    return { rows: [], error: 'spec.md 里找不到「规约约束要求」章——判定登记就是那张表' };
  }
  const level = (all[start].trim().match(/^(#{2,4})/) ?? ['', '##'])[1].length;
  let headers = null;
  for (let i = start + 1; i < all.length; i++) {
    const h = all[i].trim().match(/^(#{2,4})\s+/);
    if (h && h[1].length <= level) break;
    const line = all[i].trim();
    if (!line.startsWith('|')) continue;
    const cells = line.replace(/^\||\|$/g, '').split('|').map(c => c.trim());
    if (cells.every(c => /^[-: ]*$/.test(c))) continue;
    if (!headers) { headers = cells; continue; }
    const id = (cells[0] ?? '').replace(/[`*]/g, '').trim();
    if (!/^[A-Z][A-Z0-9]{1,7}-\d{2}$/.test(id)) continue;
    const at = headers.findIndex(x => x.includes('要求'));
    rows.push({ source: '规约要求', key: id, text: (cells[at >= 0 ? at : 1] ?? '').trim(), hit: true });
  }
  if (!rows.length) {
    return { rows: [], error: '「规约约束要求」章里一行条目都没有——判定登记为空，不是「没有命中」' };
  }
  return { rows, error: null };
}

/** 下游各阶段的行来自契约实体上的 `must`——它是 plan 之后唯一的知识入口。 */
function freezeSet(projectRoot, feature) {
  const { contracts, error, exists } = readContracts(projectRoot, feature);
  if (error) return { rows: [], error };
  if (!exists) return { rows: [], error: '读不到 plan/contracts.yaml' };

  const rows = [];
  for (const ob of obligationsFromContracts(contracts)) {
    rows.push({
      source: '实体义务',
      key: String(ob.rule ?? '').trim(),
      text: `${ob.entityPath}｜${ob.text}`,
      hit: true,
    });
  }
  for (const pattern of new Set(patternRolesFromContracts(contracts).map(r => r.pattern).filter(Boolean))) {
    const roles = patternRolesFromContracts(contracts)
      .filter(r => r.pattern === pattern)
      .map(r => `${r.role}=${r.path}`);
    rows.push({
      source: '模式投影',
      key: pattern,
      text: `角色 ${roles.join('、') || '—'}`,
      hit: true,
    });
  }
  // 项目知识不逐面裁——只裁「本方案新增的能力有没有先复用登记的入口」这一件事
  rows.push({
    source: '项目知识复用',
    key: FACTS_REUSE_KEY,
    text: '方案新增的能力是否先复用了项目知识登记的入口',
    hit: true,
  });
  return { rows, error: null };
}

/** 项目知识复用行的固定标识——报告核对时按它找那一行。 */
const FACTS_REUSE_KEY = 'facts_reuse';

/** 必答集的核对键（去重、去空）。 */
export function adjudicationKeys(rows) {
  return [...new Set(rows.map(r => String(r?.key ?? '').trim()).filter(Boolean))];
}
