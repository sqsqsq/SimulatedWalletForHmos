/**
 * 契约访问器 —— 读 contracts / acceptance，解析实体引用。
 *
 * 义务本身不在这里：它挂在契约实体上，由 `obligations.mjs` 运行期派生。
 * 本模块只负责**读取与解析**，判据在各阶段的 post_check。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { featureRoot, readTextOrNull } from './paths.mjs';
import { parseYaml } from './yaml.mjs';

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
  // resource_keys 是两层对象不是列表：先按两层读法摊成条目，再判空
  const bucket = kind === 'resource_keys' ? resourceEntries(contracts).entries : asArray(contracts?.[kind]);
  if (!bucket.length) {
    return { ok: false, reason: `契约里没有 ${kind} 这一节或它是空的`, tail };
  }

  // resource_keys 是两层对象，引用只认完整的 `resource_keys.<模块>.<分类>.<key>`：
  // key 本身可以带点，所以按整串比，不按段比
  if (kind === 'resource_keys') {
    const hit = bucket.find(e => e.ref === raw);
    return hit
      ? { ok: true, reason: '', tail: hit.key }
      : { ok: false,
          reason: `resource_keys 里没有「${parts.slice(1).join('.')}」（引用写完整的 resource_keys.<模块>.<分类>.<key>）`,
          tail };
  }
  // files 的实体名是路径，整体匹配
  if (kind === 'files') {
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

/**
 * `resource_keys` 按 framework 的合同读：两层对象 `resource_keys.<模块>.<分类>` 下是资源条目列表
 * （`framework/harness/scripts/utils/types.ts` 的 `Record<string, Record<string, ResourceEntry[]>>`）。
 * 每条资源的引用是完整的 `resource_keys.<模块>.<分类>.<key>`；模块与分类名来自实际键，不硬编码。
 *
 * 缺这一节返回空；形状不是两层对象时报到具体模块或分类——按平铺列表读它，会把每条资源当成
 * 模块名，作者按报错改成两层后，义务反而挂不上。
 *
 * @returns {{entries: {module: string, category: string, key: string, node: object, ref: string}[], problems: string[]}}
 */
export function resourceEntries(contracts) {
  const entries = [];
  const problems = [];
  const rk = contracts?.resource_keys;
  if (rk === undefined || rk === null || rk === '') return { entries, problems };
  const shape = '——形态是 `resource_keys:` → `<模块>:` → `<分类>:` → `- key: …`（与 framework 合同一致）';
  if (typeof rk !== 'object' || Array.isArray(rk)) {
    problems.push(`resource_keys 不是「模块 → 分类 → 资源列表」的两层对象（读到${Array.isArray(rk) ? '列表' : typeof rk}）${shape}`);
    return { entries, problems };
  }
  for (const [module, cats] of Object.entries(rk)) {
    if (!cats || typeof cats !== 'object' || Array.isArray(cats)) {
      problems.push(`resource_keys.${module} 下应是「分类 → 资源列表」（读到${Array.isArray(cats) ? '列表' : typeof cats}）${shape}`);
      continue;
    }
    for (const [category, list] of Object.entries(cats)) {
      if (!Array.isArray(list)) {
        problems.push(`resource_keys.${module}.${category} 应是资源条目列表（读到 ${typeof list}）${shape}`);
        continue;
      }
      list.forEach((node, i) => {
        const key = entityName(node);
        if (!key) {
          problems.push(`resource_keys.${module}.${category} 第 ${i + 1} 条没有 key`);
          return;
        }
        entries.push({ module, category, key, node, ref: `resource_keys.${module}.${category}.${key}` });
      });
    }
  }
  return { entries, problems };
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
/** 验收编号的形态：唯一定义在章节合同 `id_shapes.acceptance`。 */
const STORY_CONTRACT = new URL('../../skills/story/contracts/story-chapters.json', import.meta.url);

const idShape = kind => new RegExp(`\\b(?:${JSON.parse(fs.readFileSync(STORY_CONTRACT, 'utf-8')
  .replace(/^\uFEFF/, '')).id_shapes[kind].join('|')})\\b`, 'g');
export const acceptanceIdRe = () => idShape('acceptance');
/** 上游材料里读者要对照的原始验收编号形态（`id_shapes.keep`）。 */
export const keptIdRe = () => idShape('keep');

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
 * 规约编号 → 该编号下**全部**验收条目 —— 各阶段桥接前的唯一入口。
 *
 * **一条验收条目可以只对应一条规约，一条规约常有多个验收条目**：同一条规约在不同场景
 * 下验收（正常路径、边界、异常恢复），下游要逐条覆盖。按 `Map.set(rule, 单条)` 收的话，
 * 同 rule 多条 AC 会静默只留最后一条——作者桥接了两条，下游只验一条。
 *
 * 校验与分组在**同一次遍历**里做完：先摊成 `{section, criterion}` 再分组的话，那份中间
 * 数组没有自己的下游（Spec 只要编号集合，UT/testing 只要 byRule），却要维护两个接口与
 * 两次遍历。只读解析结果，不改输入对象，不落盘。
 *
 * @param {object|null} acceptance readAcceptance 解析出的 acceptance
 * @param {string[]} [sections] 桥接所在的集合名，默认 `ACCEPTANCE_SECTIONS`
 * @returns {{byRule: Map<string, object[]>, problems: string[]}}
 *   缺集合视为空；非数组集合或非对象成员报明集合与序号；`knowledge_rule` 缺省的条目属
 *   普通业务验收（绝大多数验收点与规约无关，为它们各报一条会淹掉真正缺的），存在时须为
 *   非空字符串——写成列表的「一条 criteria 桥一串编号」下游分派不了。
 *   消费者先处理 `problems` 再查 `byRule`，不能过滤非法行后以「剩余为空」放行。
 */
/** 验收里能桥接规约的集合：spec 核桥接、UT/testing 按桥接分派，读的是同一组。 */
const ACCEPTANCE_SECTIONS = ['criteria', 'boundaries'];

export function knowledgeCriteria(acceptance, sections = ACCEPTANCE_SECTIONS) {
  const problems = [];
  const byRule = new Map();
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
      const key = rule.trim();
      const list = byRule.get(key) ?? [];
      list.push(row);
      byRule.set(key, list);
    });
  }
  return { byRule, problems };
}
