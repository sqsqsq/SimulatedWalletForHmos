/**
 * 契约访问器 —— 读 contracts / acceptance，解析实体引用。
 *
 * 义务本身不在这里：它挂在契约实体上，由 `obligations.mjs` 运行期派生。
 * 本模块只负责**读取与解析**，判据在各阶段的 post_check。
 */
import * as path from 'node:path';
import { featureRoot, readTextOrNull } from './paths.mjs';
import { parseYaml } from './yaml-lite.mjs';

/**
 * 实体引用语法：`<集合>.<实体>[.<成员>]`。
 * 集合名对齐 contracts.yaml 既有章节——**不自造平行命名空间**。
 */
const ENTITY_KINDS = [
  'data_models',
  'interfaces',
  'components',
  'state_management',
  'navigation',
  'resource_keys',
  'files',
];

/**
 * 契约的路径——**与 framework 同一份**（`spec-loader.ts` 读 feature 根下这一份）。
 *
 * 读 plan 子目录下的另一份，会让同一份契约在仓里有两个物理位置：framework 读
 * feature 根、扩展读子目录。那时执行者只能复制一份去同步，而义务（实体上的 `must`）
 * 就挂在那份副本上——「每类数据一份真源」被绕开了。
 */
export function contractsPath(projectRoot, feature) {
  return path.join(featureRoot(projectRoot, feature), 'contracts.yaml');
}

/**
 * 读 contracts.yaml。
 * @returns {{contracts: object|null, error: string|null, exists: boolean}}
 *   解析失败**不返回空对象**——空契约会让所有实体解析恒假、所有集合判据恒真。
 */
export function readContracts(projectRoot, feature) {
  const p = contractsPath(projectRoot, feature);
  const raw = readTextOrNull(p);
  if (raw === null) return { contracts: null, error: null, exists: false };
  try {
    return { contracts: parseYaml(raw), error: null, exists: true };
  } catch (e) {
    return { contracts: null, error: `contracts.yaml 解析失败：${e.message}`, exists: true };
  }
}


function asArray(v) {
  if (Array.isArray(v)) return v;
  if (v === null || v === undefined || v === '') return [];
  return [v];
}

/** 契约条目的名字：不同集合的命名字段不同，逐个试。 */
function entityName(item) {
  if (typeof item === 'string') return item;
  if (!item || typeof item !== 'object') return '';
  return String(item.name ?? item.class ?? item.key ?? item.path ?? item.file ?? item.id ?? '');
}

/** 条目的成员名集合（字段 / 方法 / 状态 / 属性）。 */
function memberNames(item) {
  if (!item || typeof item !== 'object') return [];
  const out = [];
  for (const key of ['fields', 'methods', 'state', 'props', 'events', 'children', 'keys']) {
    for (const m of asArray(item[key])) {
      const n = entityName(m);
      if (n) out.push(n);
    }
  }
  return out;
}

/**
 * 解析一个实体引用。
 *
 * @returns {{ok: boolean, reason: string, tail: string}}
 *   `tail` 是引用的末段标识符，coding 阶段拿它去源码里找。
 */
export function resolveEntityRef(contracts, ref) {
  const raw = String(ref ?? '').trim();
  if (!raw) return { ok: false, reason: '空引用', tail: '' };
  const parts = raw.split('.');
  const kind = parts[0];
  const tail = parts[parts.length - 1];
  if (!ENTITY_KINDS.includes(kind)) {
    return {
      ok: false,
      reason: `集合名「${kind}」不在契约章节里（可用：${ENTITY_KINDS.join(' / ')}）`,
      tail,
    };
  }
  if (parts.length < 2) {
    return { ok: false, reason: `引用只写了集合名，没指到具体实体`, tail };
  }
  const bucket = asArray(contracts?.[kind]);
  if (!bucket.length) {
    return { ok: false, reason: `契约里没有 ${kind} 这一节或它是空的`, tail };
  }

  // files / resource_keys 的实体名本身可能带点号（路径、键名），整体匹配
  if (kind === 'files' || kind === 'resource_keys') {
    const target = parts.slice(1).join('.');
    const hit = bucket.some(it => {
      const n = entityName(it).replace(/\\/g, '/');
      return n === target || n.endsWith('/' + target) || n.includes(target);
    });
    return hit
      ? { ok: true, reason: '', tail: target.split('/').pop() }
      : { ok: false, reason: `${kind} 里没有「${target}」`, tail: target.split('/').pop() };
  }

  const entity = parts[1];
  const item = bucket.find(it => entityName(it) === entity);
  if (!item) {
    return { ok: false, reason: `${kind} 里没有「${entity}」`, tail };
  }
  if (parts.length === 2) return { ok: true, reason: '', tail: entity };

  const member = parts.slice(2).join('.');
  const members = memberNames(item);
  if (!members.includes(member)) {
    return {
      ok: false,
      reason: `${kind}.${entity} 里没有成员「${member}」`
        + (members.length ? `（现有：${members.slice(0, 6).join('、')}）` : '（该实体没登记任何成员）'),
      tail: member,
    };
  }
  return { ok: true, reason: '', tail: member };
}

/** 契约点名的实现文件（coding 阶段据此限定检索范围，不全仓扫）。 */
export function contractFiles(contracts) {
  const out = new Set();
  for (const it of asArray(contracts?.files)) {
    const n = entityName(it);
    if (n) out.add(n.replace(/\\/g, '/'));
  }
  for (const kind of ['data_models', 'interfaces', 'components']) {
    for (const it of asArray(contracts?.[kind])) {
      const f = it && typeof it === 'object' ? it.file : null;
      if (f) out.add(String(f).replace(/\\/g, '/'));
    }
  }
  return [...out];
}

/** acceptance.yaml 读取（知识义务的验证要求单源）。 */
export function readAcceptance(projectRoot, feature) {
  const p = path.join(featureRoot(projectRoot, feature), 'acceptance.yaml');
  const raw = readTextOrNull(p);
  if (raw === null) return { acceptance: null, error: null, exists: false };
  try {
    return { acceptance: parseYaml(raw), error: null, exists: true };
  } catch (e) {
    return { acceptance: null, error: `acceptance.yaml 解析失败：${e.message}`, exists: true };
  }
}

/**
 * acceptance 条目的规范化读取 —— 各阶段按自己的集合策略桥接前的唯一入口。
 *
 * **一条验收条目可以只对应一条规约，一条规约常有多个验收条目**：同一条规约在
 * 不同场景下验收（正常路径、边界、异常恢复），下游要逐条覆盖，不能只看最后一条。
 * 这里把「哪个集合、第几条、knowledge_rule 是什么」一次读清，各阶段只做集合选择
 * 与差集判断，不再各写一遍逐行解析。
 *
 * 只读解析结果，不改输入对象，不落盘。
 *
 * @param {object|null} acceptance readAcceptance 解析出的 acceptance
 * @param {string[]} sections 调用方显式传入的集合名（如 ['criteria'] 或 ['criteria','boundaries']）
 * @returns {{entries: {section: string, criterion: object}[], problems: string[]}}
 *   缺集合视为空；非数组集合或非对象成员报明集合与序号；`knowledge_rule` 缺省的条目
 *   属普通业务验收（绝大多数验收点与规约无关，为它们各报一条会淹掉真正缺的），
 *   存在时须为非空字符串——写成列表的「一条 criteria 桥一串编号」下游分派不了。
 */
export function acceptanceEntries(acceptance, sections) {
  const problems = [];
  const entries = [];
  for (const section of sections) {
    const value = acceptance?.[section];
    if (value === undefined || value === null || value === '') continue;
    if (!Array.isArray(value)) {
      problems.push(`acceptance.yaml 的 ${section} 不是列表（读到 ${typeof value}）——`
        + '桥接按条目逐条读，读不出结构就核不了');
      continue;
    }
    value.forEach((row, i) => {
      if (!row || typeof row !== 'object' || Array.isArray(row)) {
        problems.push(`acceptance.yaml 的 ${section} 第 ${i + 1} 条不是键值对象——`
          + '验收条目要写成「id / 场景 / 通过条件」的映射，裸值桥不到知识条目');
        return;
      }
      if (!('knowledge_rule' in row)) return;
      const rule = row.knowledge_rule;
      if (typeof rule !== 'string' || !rule.trim()) {
        problems.push(`${section}「${String(row.id ?? '（没写 id）')}」的 knowledge_rule 不是一个编号——`
          + '一条 criteria 一个 `knowledge_rule: <编号>`，多条规约各写一条 criteria；'
          + '写成列表或留空的话，下游按编号分派时对不到场景（形状见任务包 §2）');
        return;
      }
      entries.push({ section, criterion: row });
    });
  }
  return { entries, problems };
}

/**
 * 规约编号 → 该编号下**全部**验收条目。
 *
 * 旧实现 `Map.set(rule, 单条)` 会在同 rule 多条 AC 时静默只留最后一条——
 * 作者桥接了两条，下游只验一条，剩下的场景没有任何人看。这里按数组收，
 * 消费者先处理 `problems` 再查 `byRule`，不能过滤非法行后以「剩余为空」放行。
 *
 * @returns {{byRule: Map<string, object[]>, problems: string[]}}
 */
export function knowledgeCriteria(acceptance, sections) {
  const { entries, problems } = acceptanceEntries(acceptance, sections);
  const byRule = new Map();
  for (const { criterion } of entries) {
    const rule = String(criterion.knowledge_rule).trim();
    const list = byRule.get(rule) ?? [];
    list.push(criterion);
    byRule.set(rule, list);
  }
  return { byRule, problems };
}
