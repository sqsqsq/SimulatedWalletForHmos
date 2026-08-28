/**
 * 从契约实体派生义务索引 —— 义务写在下游本来就读的实体上，机器索引一律派生。
 *
 * 基线是一本平行账本（`contracts.knowledge_freeze`）：plan 往里写、下游从里读。
 * 实测没人读——framework 的 coding SKILL 枚举 contracts 的 7 个集合作为本阶段输入，
 * 不含它；实跑里唯一完整落地的那条规约，靠的是它挂在了一个编码者本来就要读的契约字段上。
 * 所以义务改挂在实体上，索引由这里运行期派生，**不维护第二份清单**。
 */

/** `must` 允许挂载的实体位置——多一处就是给「随便找个地方声明一下」开口子。 */
export const MUST_HOSTS = [
  'data_models[].fields[]',
  'interfaces[].methods[]',
  'components[]',
  'components[].state[]',
  'resource_keys[]',
  'files[]',
];

/** `verify` 的封闭取值。`both` 不能省：旧 `ut_layer` 三态里它代表两边都要验。 */
export const VERIFY_KINDS = ['ut', 'device', 'both', 'review', 'probe'];

const arr = (v) => (Array.isArray(v) ? v : []);
const name = (it) => String(it?.name ?? it?.path ?? it?.key ?? '').trim();

function mustOf(node) {
  return arr(node?.must).filter(m => m && typeof m === 'object');
}

/**
 * 遍历五类实体收集 `must`。
 *
 * @returns {{rule, text, verify, entityPath, entityKind, file}[]}
 *   `entityPath` 是可回查的实体引用（`components.X.state.y` 形态），
 *   `file` 是该实体所属的实现文件（`files[]` 上的 must 才有；其余为 null，由 coding 侧按契约定位）。
 */
export function obligationsFromContracts(contracts) {
  const out = [];
  const push = (node, entityKind, entityPath, file) => {
    for (const m of mustOf(node)) {
      out.push({
        rule: String(m.rule ?? '').trim(),
        text: String(m.text ?? '').trim(),
        verify: String(m.verify ?? '').trim().toLowerCase(),
        entityKind,
        entityPath,
        file: file ?? null,
      });
    }
  };

  for (const dm of arr(contracts?.data_models)) {
    for (const f of arr(dm.fields)) {
      push(f, 'data_models', `data_models.${name(dm)}.${name(f)}`, null);
    }
  }
  for (const itf of arr(contracts?.interfaces)) {
    for (const me of arr(itf.methods)) {
      push(me, 'interfaces', `interfaces.${name(itf)}.${name(me)}`, null);
    }
  }
  for (const c of arr(contracts?.components)) {
    push(c, 'components', `components.${name(c)}`, null);
    for (const st of arr(c.state)) {
      push(st, 'components', `components.${name(c)}.state.${name(st)}`, null);
    }
  }
  for (const rk of arr(contracts?.resource_keys)) {
    push(rk, 'resource_keys', `resource_keys.${name(rk)}`, null);
  }
  for (const fl of arr(contracts?.files)) {
    const p = name(fl);
    push(fl, 'files', `files.${p}`, p);
  }
  return out;
}

/**
 * `must` 出现在了不该出现的地方。
 *
 * 只查**能明确判定为越位**的位置（实体的顶层，而非其成员），不做全树扫描——
 * 全树扫描会把 `files[].must` 这类合法位置也一并报出来。
 */
export function misplacedMust(contracts) {
  const bad = [];
  for (const dm of arr(contracts?.data_models)) {
    if (mustOf(dm).length) bad.push(`data_models.${name(dm)} 顶层挂了 must——应挂在它的 fields[] 上`);
  }
  for (const itf of arr(contracts?.interfaces)) {
    if (mustOf(itf).length) bad.push(`interfaces.${name(itf)} 顶层挂了 must——应挂在它的 methods[] 上`);
  }
  for (const key of ['modules', 'navigation', 'state_management', 'integration_points']) {
    for (const it of arr(contracts?.[key])) {
      if (mustOf(it).length) bad.push(`${key}.${name(it)} 挂了 must——不在允许的五类实体内`);
    }
  }
  if (mustOf(contracts).length) bad.push('contracts 顶层挂了 must——义务要挂在具体实体上');
  return bad;
}

/**
 * 模式采用的结构投影：`files[].pattern` + `files[].role`。
 *
 * 替代 `knowledge_freeze.patterns[].roles: {角色: 类名}`——角色实体就是文件里的类，
 * 再写一份映射表只会与 `files[]` 漂移。
 */
export function patternRolesFromContracts(contracts) {
  const out = [];
  for (const fl of arr(contracts?.files)) {
    const pattern = String(fl?.pattern ?? '').trim();
    if (!pattern) continue;
    out.push({
      pattern,
      role: String(fl?.role ?? '').trim(),
      path: name(fl),
    });
  }
  return out;
}
