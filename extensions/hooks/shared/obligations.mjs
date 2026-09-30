/**
 * 从契约实体派生义务索引 —— 义务写在下游本来就读的实体上，机器索引一律派生。
 *
 * 规约能不能落地，取决于它挂没挂在编码者本来就要读的那个契约字段上（framework 的 coding
 * 输入是 contracts 的各实体集合），所以义务挂在实体上，索引由这里运行期派生，**不维护第二份清单**。
 */

/**
 * `must` 允许挂载的实体位置是**封闭集合**：`data_models[].fields[]`、
 * `interfaces[].methods[]`、`components[]`、`components[].state[]`、
 * `resource_keys.<模块>.<分类>[]`。多一处就是给「随便找个地方声明一下」开口子。
 * `files` 是原生的授权文件清单（字符串），不承载义务；文件级职责由真正承担它的实体表达。
 *
 * 以下面的遍历代码为准；另设一个导出的常量重列一遍只会多一处失同步点——。
 */

/**
 * `verify` 的封闭取值：这处落点的证据由谁取。`ut / device / both` 是实机，`review` 只由 verifier 判。
 * 探针不在其中——它随规约走，coding 对形态匹配的每处落点自动跑，不是作者为某处落点做的选择。
 */
import { entityId, resourceEntries } from './contracts.mjs';

const VERIFY_KINDS = ['ut', 'device', 'both', 'review'];

/** 规约声明的执行体 → 它的每处落点允许的 `verify`。没列的执行体（模型、构建）不限定；人工条目不挂 must。 */
const VERIFY_BY_EXECUTOR = { 实机: ['ut', 'device', 'both'] };

/**
 * 一处落点的 `verify` 与它指向的规约声明对不对得上。一条 must 就是一处落点，多处落点各自照此判。
 * @returns {string|null} 对不上时的说明
 */
export function verifyProblem(entry, verify) {
  if (!VERIFY_KINDS.includes(verify)) return `verify「${verify || '(空)'}」不是 ${VERIFY_KINDS.join(' / ')} 之一——verify 取值封闭，定这处落点的证据由谁取，ut / device / both 是实机，review 只由 verifier 判`;
  const [executor, allowed] = Object.entries(VERIFY_BY_EXECUTOR)
    .find(([x]) => (entry?.executors ?? []).includes(x)) ?? [];
  return allowed && !allowed.includes(verify)
    ? `标了 verify: ${verify}，而该规约声明要「${executor}」证据——声明要「${executor}」证据的规约，每处落点的 verify 取 ${allowed.join(' / ')}`
    : null;
}

const arr = (v) => (Array.isArray(v) ? v : []);
/** 成员（字段、方法、状态）的原生名；实体本身的身份按 `entityId` 取。 */
const name = (it) => String(it?.name ?? '').trim();

function mustOf(node) {
  return arr(node?.must).filter(m => m && typeof m === 'object');
}

/**
 * 遍历五类实体收集 `must`。
 *
 * @returns {{rule, text, verify, decisionId, entityPath, entityKind, file}[]}
 *   `entityPath` 是可回查的实体引用（`components.X.state.y` 形态），`decisionId` 是这条义务出自的知识应用决定，
 *   `file` 是该实体所属的实现文件（实体写了 `file` 才有，由 coding 侧按契约定位）。
 */
export function obligationsFromContracts(contracts) {
  const out = [];
  const push = (node, entityKind, entityPath, file) => {
    for (const m of mustOf(node)) {
      out.push({
        rule: String(m.rule ?? '').trim(),
        text: String(m.text ?? '').trim(),
        verify: String(m.verify ?? '').trim().toLowerCase(),
        decisionId: String(m.decision_id ?? '').trim(),
        entityKind,
        entityPath,
        file: file ?? null,
      });
    }
  };

  const fileOf = it => (it?.file ? String(it.file).replace(/\\/g, '/') : null);
  // 缺原生身份的实体不拼地址，由 unidentifiedCarriers 点名
  for (const dm of arr(contracts?.data_models).filter(x => entityId('data_models', x))) {
    for (const f of arr(dm.fields)) {
      push(f, 'data_models', `data_models.${entityId('data_models', dm)}.${name(f)}`, fileOf(dm));
    }
  }
  for (const itf of arr(contracts?.interfaces).filter(x => entityId('interfaces', x))) {
    for (const me of arr(itf.methods)) {
      push(me, 'interfaces', `interfaces.${entityId('interfaces', itf)}.${name(me)}`, fileOf(itf));
    }
  }
  for (const c of arr(contracts?.components).filter(x => entityId('components', x))) {
    push(c, 'components', `components.${entityId('components', c)}`, fileOf(c));
    for (const st of arr(c.state)) {
      push(st, 'components', `components.${entityId('components', c)}.state.${name(st)}`, fileOf(c));
    }
  }
  for (const e of resourceEntries(contracts).entries) {
    push(e.node, 'resource_keys', e.ref, null);
  }
  return out;
}

/**
 * `must` 出现在了不该出现的地方。
 *
 * 只查**能明确判定为越位**的位置（实体的顶层，而非其成员），不做全树扫描。
 */
export function misplacedMust(contracts) {
  const bad = [];
  for (const dm of arr(contracts?.data_models)) {
    if (mustOf(dm).length) bad.push(`contracts.yaml 的 data_models.${entityId('data_models', dm)} 顶层挂了 must，data_models 的 must 位置是 fields[]`);
  }
  for (const itf of arr(contracts?.interfaces)) {
    if (mustOf(itf).length) bad.push(`contracts.yaml 的 interfaces.${entityId('interfaces', itf)} 顶层挂了 must，interfaces 的 must 位置是 methods[]`);
  }
  for (const key of ['modules', 'navigation', 'state_management', 'integration_points']) {
    for (const it of arr(contracts?.[key])) {
      if (mustOf(it).length) bad.push(`contracts.yaml 的 ${key}.${entityId(key, it)} 挂了 must，${key} 不在允许挂 must 的实体里`);
    }
  }
  const rk = contracts?.resource_keys;
  if (rk && typeof rk === 'object' && !Array.isArray(rk)) {
    for (const [module, cats] of Object.entries(rk)) {
      if (mustOf(cats).length) bad.push(`contracts.yaml 的 resource_keys.${module} 模块层挂了 must，resource_keys 的 must 位置是分类下的资源条目`);
      if (!cats || typeof cats !== 'object' || Array.isArray(cats)) continue;
      for (const [category, list] of Object.entries(cats)) {
        if (!Array.isArray(list) && mustOf(list).length) {
          bad.push(`contracts.yaml 的 resource_keys.${module}.${category} 分类层挂了 must，resource_keys 的 must 位置是分类下的资源条目`);
        }
      }
    }
  }
  if (mustOf(contracts).length) bad.push('contracts.yaml 顶层挂了 must，must 的位置是具体实体');
  return bad;
}

/**
 * 挂着 `must` 或 `pattern_roles` 却缺原生身份的实体：接口缺 `class`，数据模型、组件缺 `name`。
 * 义务与角色的地址由身份拼出，这些实体上的义务与角色不进 `obligationsFromContracts` / `patternRolesFromContracts`，在这里点名。
 */
export function unidentifiedCarriers(contracts) {
  const bad = [];
  for (const [kind, members] of [['data_models', ['fields']], ['interfaces', ['methods']], ['components', ['state']]]) {
    arr(contracts?.[kind]).forEach((it, i) => {
      const carries = mustOf(it).length || arr(it?.pattern_roles).length || members.some(k => arr(it?.[k]).some(m => mustOf(m).length));
      const field = kind === 'interfaces' ? 'class' : 'name';
      if (carries && !entityId(kind, it)) {
        bad.push(`contracts.yaml 的 ${kind} 第 ${i + 1} 项没有 ${field}，却挂着 must 或 pattern_roles——原生按 ${field} 认这个实体，义务与角色的地址由它拼出`);
      }
    });
  }
  return bad;
}

/**
 * 模式采用的结构投影：真实承担角色的 `components` / `interfaces` / `data_models` 实体上的
 * `pattern_roles: [{pattern, role, decision_id}]`，以实体的原生名定位，实现文件取实体自己的 `file`。
 *
 * @returns {{pattern, role, decisionId, entity, entityPath, path}[]}
 */
export function patternRolesFromContracts(contracts) {
  const out = [];
  for (const kind of ['components', 'interfaces', 'data_models']) {
    for (const it of arr(contracts?.[kind]).filter(x => entityId(kind, x))) {
      for (const pr of arr(it?.pattern_roles)) {
        out.push({
          pattern: String(pr?.pattern ?? '').trim(),
          role: String(pr?.role ?? '').trim(),
          decisionId: String(pr?.decision_id ?? '').trim(),
          entity: entityId(kind, it),
          entityPath: `${kind}.${entityId(kind, it)}`,
          path: it?.file ? String(it.file).replace(/\\/g, '/') : null,
        });
      }
    }
  }
  return out;
}
