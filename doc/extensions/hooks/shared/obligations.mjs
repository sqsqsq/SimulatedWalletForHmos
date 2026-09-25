/**
 * 从契约实体派生义务索引 —— 义务写在下游本来就读的实体上，机器索引一律派生。
 *
 * 规约能不能落地，取决于它挂没挂在编码者本来就要读的那个契约字段上（framework 的 coding
 * 输入是 contracts 的各实体集合），所以义务挂在实体上，索引由这里运行期派生，**不维护第二份清单**。
 */

/**
 * `must` 允许挂载的实体位置是**封闭集合**：`data_models[].fields[]`、
 * `interfaces[].methods[]`、`components[]`、`components[].state[]`、
 * `resource_keys.<模块>.<分类>[]`、`files[]`。多一处就是给「随便找个地方声明一下」开口子。
 *
 * 以下面的遍历代码为准；另设一个导出的常量重列一遍只会多一处失同步点——。
 */

/**
 * `verify` 的封闭取值：这处落点的证据由谁取。`ut / device / both` 是实机，`review` 只由 verifier 判。
 * 探针不在其中——它随规约走，coding 对形态匹配的每处落点自动跑，不是作者为某处落点做的选择。
 */
import { resourceEntries } from './contracts.mjs';

const VERIFY_KINDS = ['ut', 'device', 'both', 'review'];

/** 规约声明的执行体 → 它的每处落点允许的 `verify`。没列的执行体（模型、构建）不限定；人工条目不挂 must。 */
const VERIFY_BY_EXECUTOR = { 实机: ['ut', 'device', 'both'] };

/**
 * 一处落点的 `verify` 与它指向的规约声明对不对得上。一条 must 就是一处落点，多处落点各自照此判。
 * @returns {string|null} 对不上时的说明
 */
export function verifyProblem(entry, verify) {
  if (!VERIFY_KINDS.includes(verify)) return `verify「${verify || '(空)'}」不是 ${VERIFY_KINDS.join(' / ')} 之一`;
  const [executor, allowed] = Object.entries(VERIFY_BY_EXECUTOR)
    .find(([x]) => (entry?.executors ?? []).includes(x)) ?? [];
  return allowed && !allowed.includes(verify)
    ? `标了 verify: ${verify}，而该规约声明要「${executor}」证据——这处落点改成 ${allowed.join(' / ')} 之一`
    : null;
}

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
  for (const e of resourceEntries(contracts).entries) {
    push(e.node, 'resource_keys', e.ref, null);
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
  const rk = contracts?.resource_keys;
  if (rk && typeof rk === 'object' && !Array.isArray(rk)) {
    for (const [module, cats] of Object.entries(rk)) {
      if (mustOf(cats).length) bad.push(`resource_keys.${module} 模块层挂了 must——应挂在它某个分类下的资源条目上`);
      if (!cats || typeof cats !== 'object' || Array.isArray(cats)) continue;
      for (const [category, list] of Object.entries(cats)) {
        if (!Array.isArray(list) && mustOf(list).length) {
          bad.push(`resource_keys.${module}.${category} 分类层挂了 must——应挂在这个分类下的资源条目上`);
        }
      }
    }
  }
  if (mustOf(contracts).length) bad.push('contracts 顶层挂了 must——义务要挂在具体实体上');
  return bad;
}

/**
 * 模式采用的结构投影：`files[].pattern` + `files[].role`。
 *
 * 角色实体就是文件里的类，不另写「角色 → 类名」映射表——那只会与 `files[]` 漂移。
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
