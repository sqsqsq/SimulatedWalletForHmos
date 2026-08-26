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
import { readContracts, readFreeze } from './freeze.mjs';

/** 登记源：归档件的判定登记件，spec 阶段一切知识判定的唯一出处。 */
function registryPath(projectRoot, feature) {
  return path.join(featureRoot(projectRoot, feature), 'AR', 'story-src', 'knowledge.json');
}

/**
 * 读登记源。
 * @returns {{registry: object|null, error: string|null, exists: boolean}}
 *   解析失败不返回空对象——空登记会让「集合一致」类判据恒真。
 */
export function readRegistryFile(projectRoot, feature) {
  const raw = readTextOrNull(registryPath(projectRoot, feature));
  if (raw === null) return { registry: null, error: null, exists: false };
  try {
    return { registry: JSON.parse(raw.replace(/^﻿/, '')), error: null, exists: true };
  } catch (e) {
    return { registry: null, error: `knowledge.json 不是合法 JSON：${e.message}`, exists: true };
  }
}

function asArray(v) {
  return Array.isArray(v) ? v : [];
}

/**
 * 域级判定的一致性判据 —— story 装配与 spec 门禁共用这一份。
 *
 * @returns {{problems: string[], expectedIds: string[], domainRows: object[]}}
 *   `expectedIds` 是本需求该逐条判定的条目全集（always 域全部 ∪ 判适用的条件域全部）；
 *   `domainRows` 是判不适用的域，附录每域渲染一行。
 */
export function domainProblems(knowledge, registry) {
  const problems = [];
  const declared = new Map();
  for (const d of asArray(registry?.domains)) {
    const prefix = String(d?.prefix ?? '').trim();
    if (!prefix) { problems.push('knowledge.json 的 domains 有条目缺 prefix'); continue; }
    if (declared.has(prefix)) { problems.push(`knowledge.json 的 domains 中 ${prefix} 重复登记`); continue; }
    declared.set(prefix, {
      applies: d?.applies === true,
      basis: String(d?.basis ?? '').trim(),
    });
  }

  const conditional = knowledge.constraints.filter(c => !c.alwaysApplies);
  const conditionalPrefixes = new Set(conditional.map(c => c.domain));
  const allPrefixes = new Set(knowledge.constraints.map(c => c.domain));

  for (const prefix of declared.keys()) {
    if (!allPrefixes.has(prefix)) {
      problems.push(`knowledge.json 的 domains 登记了不在册的域前缀 ${prefix}`
        + `（在册的条件域：${[...conditionalPrefixes].join('、') || '无'}）`);
    } else if (!conditionalPrefixes.has(prefix)) {
      problems.push(`${prefix} 域的命中条件是 always，不做域级判定——把它的条目逐条判，`
        + 'domains 只登记有命中条件的域');
    }
  }

  const domainRows = [];
  const expectedIds = [];
  for (const c of knowledge.constraints) {
    if (c.alwaysApplies) {
      expectedIds.push(...c.entries.map(e => e.id));
      continue;
    }
    const d = declared.get(c.domain);
    if (!d) {
      problems.push(`条件域 ${c.domain}（${c.title}）未做域级判定`
        + `——该域的命中条件是「${c.appliesWhen}」，先在 knowledge.json 的 domains 里判适用与否并写 basis`);
      continue;
    }
    if (!d.basis) {
      problems.push(`${c.domain} 域的域级判定缺 basis——写清为什么${d.applies ? '适用' : '不适用'}本需求，`
        + '「不涉及」三个字不构成依据');
    }
    if (d.applies) expectedIds.push(...c.entries.map(e => e.id));
    else domainRows.push({ prefix: c.domain, title: c.title, basis: d.basis || '—' });
  }

  // 判不适用的域，域内条目不应再逐条登记：整域一行是判定记录，逐条登记是重复劳动
  const notApplicable = new Set(domainRows.map(r => r.prefix));
  for (const item of asArray(registry?.constraints)) {
    const id = String(item?.id ?? '').trim();
    const entry = knowledge.entries.find(e => e.id === id);
    if (entry && notApplicable.has(entry.prefix)) {
      problems.push(`${id} 所在的 ${entry.prefix} 域已判整域不适用，不再逐条登记`);
    }
  }

  return { problems, expectedIds, domainRows };
}

/**
 * 本阶段的必答集。
 *
 * @param {string} phase spec / plan（其它阶段沿用 plan 的冻结行）
 * @returns {{rows: object[], error: string|null}}
 *   派生失败 error 非空，调用方须出声——静默空集会让「逐行裁决」判据恒真。
 */
export function adjudicationSet(projectRoot, feature, phase, knowledge) {
  if (phase === 'spec') return specSet(projectRoot, feature, knowledge);
  return freezeSet(projectRoot, feature, knowledge);
}

function specSet(projectRoot, feature, knowledge) {
  const { registry, error, exists } = readRegistryFile(projectRoot, feature);
  if (error) return { rows: [], error };
  if (!exists) return { rows: [], error: '读不到归档件的判定登记件 AR/story-src/knowledge.json' };

  const rows = [];
  for (const item of asArray(registry?.constraints)) {
    rows.push({
      source: '规约判定',
      key: String(item?.id ?? '').trim(),
      text: String(item?.conclusion ?? '').trim(),
      hit: item?.hit === true,
    });
  }
  const { domainRows } = domainProblems(knowledge, registry);
  for (const d of domainRows) {
    rows.push({ source: '域级判定', key: d.prefix, text: d.basis, hit: false });
  }
  for (const p of asArray(registry?.patterns)) {
    const unit = String(p?.unit ?? '').trim();
    if (!unit) continue;
    rows.push({
      source: '模式候选',
      key: unit,
      text: `${String(p?.candidate ?? '').trim() || '无候选'}｜${String(p?.signal ?? '').trim()}`,
      hit: false,
    });
  }
  return { rows, error: null };
}

/** 下游各阶段的行来自冻结块——它是 plan 之后唯一的知识入口。 */
function freezeSet(projectRoot, feature) {
  const { contracts, error, exists } = readContracts(projectRoot, feature);
  if (error) return { rows: [], error };
  if (!exists) return { rows: [], error: '读不到 plan/contracts.yaml' };
  const { obligations, patterns } = readFreeze(contracts);

  const rows = [];
  for (const ob of obligations) {
    rows.push({
      source: '冻结义务',
      key: String(ob?.rule ?? '').trim(),
      text: String(ob?.obligation ?? '').trim(),
      hit: true,
    });
  }
  for (const p of patterns) {
    if (p?.selected !== true) continue;
    const roles = p.roles && typeof p.roles === 'object' ? p.roles : {};
    rows.push({
      source: '模式冻结',
      key: String(p.pattern_id ?? '').trim(),
      text: `实例 ${p.instance ?? '—'}｜角色 ${Object.entries(roles).map(([k, v]) => `${k}=${v}`).join('、') || '—'}`,
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
