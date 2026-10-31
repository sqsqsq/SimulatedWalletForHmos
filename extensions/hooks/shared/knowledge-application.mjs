/**
 * 设计里的知识应用 —— 蓝图带一份工具生成的知识输入身份，适用性写在原生事实里，义务与模式角色写在真正承担的实体上。
 *
 * - 输入身份：蓝图 `discovery.inputs.knowledge_context`（`knowledgeContext` 生成，作者原样写入），记这一版设计收到的
 *   激活知识与原文摘要；知识换了按它比出增删改，由设计修订承接，不证明已经理解。
 * - 适用性：原生事实 `discovery.facts[]`，`provenance.source_ref` 指知识文件。规约一域一条：整域无关写
 *   `{knowledge_kind: constraints, outcome: not_applicable, rationale}`，相关域逐条 `items: [{unit, outcome, rationale, target_refs}]`；
 *   模式只在出现候选信号时写 `{knowledge_kind: patterns, outcome: selected|rejected, rationale}`；项目事实引用事实文件（可带 `#单元`）。
 * - 义务与角色：承担它的实体上的 `must: [{text, source_ref, verify}]`（source_ref 指规约条目 `<文件>#<编号>`）与
 *   `pattern_roles: [{pattern_ref, role}]`（pattern_ref 指模式文件）。蓝图里在稳定地址对象上，施工契约里在实体上。
 * - 没有蓝图的平铺维护 Feature：同一形态的适用性事实写在它原生契约的 `knowledge_facts` 里（原生按文件路径读契约里的
 *   `files`，输入身份不放进契约）。
 *
 * 形态的唯一合同是 `skills/story/contracts/knowledge-application.schema.json`（原生 lite-json-schema 校验）；这里补合同表达不了的：
 * 来源是不是这一轮激活的知识文件、单元在不在文件里、相关域的条目逐条且不重复、落点是不是这份设计的真实稳定地址、
 * 角色是不是模式声明的、选中的模式有没有实体承担。理由对不对、有没有漏判相关域、义务是否曲解，归独立审查。
 *
 * 只读；问题交回设计职责修订，这里不代写判断。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { featureIdentity, loadNative, readBlueprint } from './framework-access.mjs';
import { activeKnowledge } from './knowledge.mjs';
import { verifyProblem } from './obligations.mjs';
import { extensionRoot } from './paths.mjs';

//: 本模块所在的扩展包根：形态合同属于机制，随包发布
const PACKAGE = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const SCHEMA = path.join(PACKAGE, 'skills', 'story', 'contracts', 'knowledge-application.schema.json');

const posix = p => p.split(path.sep).join('/');
const sha = bytes => `sha256:${crypto.createHash('sha256').update(bytes).digest('hex')}`;
const where = ref => String(ref ?? '').split('#')[0].replace(/\\/g, '/');
const unitOf = ref => { const at = String(ref ?? '').indexOf('#'); return at >= 0 ? String(ref).slice(at + 1) : ''; };

/**
 * 激活知识按工程相对路径登记：扩展根相对的文件、类别、形态、单元、原始摘要；规约另带每条的强制力与哪几条是评审动作，
 * 模式另带声明的角色。工程相对路径就是事实、义务与验收里写的 `source_ref`。
 */
export function activation(projectRoot, knowledge = activeKnowledge(projectRoot)) {
  const ext = extensionRoot(projectRoot);
  const out = new Map();
  const add = (kind, k, entries = [], roles = []) => {
    const abs = path.join(ext, ...k.file.split('/'));
    out.set(posix(path.relative(projectRoot, abs)), {
      kind, file: k.file, form: k.form, units: k.units, sha256: sha(fs.readFileSync(abs)),
      force: new Map(entries.map(e => [e.id, e.force])),
      reviewActions: new Set(entries.filter(e => e.reviewAction).map(e => e.id)),
      roles: new Set(roles), id: k.id ?? null,
    });
  };
  for (const c of knowledge.constraints) add('constraints', c, c.entries);
  for (const p of knowledge.patterns) add('patterns', p, [], [...(p.roles ?? []), ...(p.optionalRoles ?? [])]);
  for (const f of knowledge.facts) add('facts', f);
  return out;
}

/**
 * 这一轮的知识输入身份：激活清单里每份知识的工程相对路径、类别、形态与原字节摘要，按路径排序；`digest` 是它们的摘要。
 * 设计作者原样写进蓝图 `discovery.inputs.knowledge_context`。
 */
export function knowledgeContext(projectRoot, active = activation(projectRoot)) {
  const files = [...active].map(([ref, s]) => ({ source_ref: ref, kind: s.kind, form: s.form, sha256: s.sha256 }))
    .sort((a, b) => (a.source_ref < b.source_ref ? -1 : a.source_ref > b.source_ref ? 1 : 0));
  return { digest: sha(JSON.stringify(files.map(f => [f.source_ref, f.kind, f.form, f.sha256]))), files };
}

function schemaCheck(native, value, name) {
  const lite = native.module('scripts/utils/lite-json-schema.ts');
  const schema = JSON.parse(fs.readFileSync(SCHEMA, 'utf-8'));
  const unsupported = lite.auditSchemaSupport(schema);
  if (unsupported.length) throw new Error(`${SCHEMA} 用了原生校验器不支持的关键字：${JSON.stringify(unsupported)}`);
  return lite.validateLiteSchema(value, { $ref: `#/$defs/${name}` }, schema).map(v => `${v.path} ${v.message}`);
}

/**
 * 一处知识引用（`<工程相对路径>[#<单元>]`）认回激活知识：来源文件、类别与单元；不是激活的知识文件为 null。
 */
export function knowledgeSource(active, sourceRef) {
  const source = active.get(where(sourceRef));
  return source ? { ...source, ref: where(sourceRef), unit: unitOf(sourceRef) } : null;
}

/** 蓝图的原生稳定地址集合（`contract:<id>`、`view:<视图>/node:<id>`、`decision:<id>` 等）。 */
export function blueprintAddresses(projectRoot, blueprint) {
  const addressing = loadNative(projectRoot).module('scripts/utils/blueprint-addressing.ts');
  return new Set(addressing.stableAddressIndex(blueprint).keys());
}

/** 蓝图记的知识输入身份与这一轮的比：缺了、坏了，或哪些知识增删改了。 */
function contextProblems(native, declared, current, label) {
  if (declared === undefined || declared === null) {
    return current.files.length
      ? [`${label} 没有记知识输入身份（discovery.inputs.knowledge_context）——设计作者把知识任务给出的那一段原样写进去`]
      : [];
  }
  const shape = schemaCheck(native, declared, 'knowledgeContext');
  if (shape.length) return [`${label} 的 knowledge_context 形态不合：${shape.slice(0, 4).join('；')}——原样用知识任务给出的那一段`];
  if (declared.digest === current.digest) return [];
  const was = new Map(declared.files.map(f => [f.source_ref, f.sha256]));
  const now = new Map(current.files.map(f => [f.source_ref, f.sha256]));
  const added = [...now.keys()].filter(k => !was.has(k));
  const removed = [...was.keys()].filter(k => !now.has(k));
  const changed = [...now.keys()].filter(k => was.has(k) && was.get(k) !== now.get(k));
  const what = [added.length ? `新增 ${added.join('、')}` : '', removed.length ? `撤下 ${removed.join('、')}` : '',
    changed.length ? `原文变了 ${changed.join('、')}` : ''].filter(Boolean).join('；') || '摘要与文件清单对不上';
  return [`${label} 的知识输入不是这一轮的（${what}）——按新知识核受影响的事实与实体，原生修订后换成知识任务给出的 knowledge_context`];
}

/**
 * 适用性事实与输入身份：来源是激活知识、形态合合同、一份知识一条事实、相关域逐条不重复、待定指原生决定或缺口；
 * `real` 给了就核落点是这份设计的稳定地址，`context` 为 false 时不核输入身份（平铺维护 Feature 两者都没有）。
 */
function checkFacts(projectRoot, native, active, { facts: list, context, real, label }) {
  const problems = context === false ? [] : contextProblems(native, context, knowledgeContext(projectRoot, active), label);
  const extRef = posix(path.relative(projectRoot, extensionRoot(projectRoot)));
  const rows = [];
  const facts = [];
  const judged = new Map();
  const say = (id, text) => problems.push(`${label} 的事实 ${id}：${text}`);
  for (const f of list) {
    const id = f?.fact_id ?? '（无编号）';
    const ref = where(f?.provenance?.source_ref);
    const source = active.get(ref);
    if (!source) {
      if (ref.startsWith(`${extRef}/`)) say(id, `来源 ${f.provenance.source_ref} 不是这一轮激活的知识文件`);
      continue;
    }
    if (source.kind === 'facts') {
      const unit = unitOf(f.provenance.source_ref);
      if (unit && !source.units.includes(unit)) say(id, `单元 ${unit} 不在 ${source.file} 里`);
      else facts.push(f);
      continue;
    }
    const shape = schemaCheck(native, f.value, source.kind === 'constraints' ? 'constraintsFact' : 'patternsFact');
    if (shape.length) { say(id, `${source.kind === 'constraints' ? '规约' : '模式'}适用性的形态不合：${shape.slice(0, 4).join('；')}`); continue; }
    if (judged.has(ref)) { say(id, `与事实 ${judged.get(ref)} 判的是同一份知识（${source.file}）——一份知识一条适用性事实`); continue; }
    judged.set(ref, id);
    if (source.kind === 'patterns') {
      rows.push({ kind: 'patterns', file: source.file, ref, source_ref: ref, outcome: f.value.outcome, rationale: f.value.rationale,
        roles: [], target_refs: [], fact_id: id });
      continue;
    }
    if (!f.value.items) {
      rows.push({ kind: 'constraints', file: source.file, ref, unit: null, source_ref: ref, domain: true, outcome: 'not_applicable',
        rationale: f.value.rationale, target_refs: [], fact_id: id });
      continue;
    }
    const seen = new Set();
    for (const it of f.value.items) {
      if (!source.units.includes(it.unit)) { say(id, `条目 ${it.unit} 不在 ${source.file} 里`); continue; }
      if (seen.has(it.unit)) { say(id, `条目 ${it.unit} 写了两次——一条一判`); continue; }
      seen.add(it.unit);
      const dangling = real ? it.target_refs.filter(r => !real(r)) : [];
      if (dangling.length) say(id, `条目 ${it.unit} 的落点不是这份设计里的稳定地址：${[...new Set(dangling)].join('、')}`);
      if (it.outcome === 'pending' && !it.target_refs.some(r => /^(decision|gap):/.test(r))) {
        say(id, `条目 ${it.unit} 待定，却没指向原生的决定或缺口——争议、豁免与待定登记成原生 decision / gap，在 target_refs 里引它`);
      }
      rows.push({ kind: 'constraints', file: source.file, ref, unit: it.unit, source_ref: `${ref}#${it.unit}`, outcome: it.outcome,
        rationale: it.rationale, target_refs: it.target_refs, fact_id: id, reviewAction: source.reviewActions.has(it.unit) });
    }
    const missing = source.units.filter(u => !seen.has(u));
    if (missing.length) {
      say(id, `相关域没有逐条判断 ${missing.join('、')}（${source.file}）——相关域每条写适用、不适用或待定；整域无关写一条域级 not_applicable`);
    }
  }
  return { rows, facts, problems };
}

/**
 * 蓝图里的知识应用：输入身份、适用性事实、实体上的义务与模式角色，按激活知识与原生稳定地址核。
 *
 * @returns {{rows: object[], facts: object[], problems: string[]}}
 *   `rows` 是规约与模式的判断，一条一行：规约条目 `{kind: 'constraints', file, ref, unit, source_ref, outcome, rationale,
 *   target_refs, fact_id, reviewAction}`（整域无关 `domain: true`、`unit` 为 null）；模式 `{kind: 'patterns', file, ref,
 *   source_ref, outcome, rationale, roles: [{role, target_ref}], target_refs, fact_id}`。`facts` 是引用了激活项目事实的原生事实。
 */
export function blueprintKnowledge(projectRoot, blueprint) {
  const native = loadNative(projectRoot);
  const knowledge = activeKnowledge(projectRoot);
  const active = activation(projectRoot, knowledge);
  const label = `蓝图 ${blueprint?.blueprint_id}`;
  const index = native.module('scripts/utils/blueprint-addressing.ts').stableAddressIndex(blueprint);
  const { rows, facts, problems } = checkFacts(projectRoot, native, active, { facts: blueprint?.discovery?.facts ?? [],
    context: blueprint?.discovery?.inputs?.knowledge_context ?? null, real: a => index.has(a), label });
  const say = (id, text) => problems.push(`${label} 的事实 ${id}：${text}`);
  // 实体上的义务与模式角色：蓝图里挂在稳定地址对象上
  for (const [address, node] of index) {
    if (node?.must !== undefined) {
      const shape = schemaCheck(native, node.must, 'must');
      if (shape.length) problems.push(`${label} 的 ${address}：must 形态不合：${shape.slice(0, 4).join('；')}`);
      else for (const m of node.must) problems.push(...mustProblems(knowledge, active, m, rows, `${label} 的 ${address}`));
    }
    if (node?.pattern_roles !== undefined) {
      const shape = schemaCheck(native, node.pattern_roles, 'patternRoles');
      if (shape.length) { problems.push(`${label} 的 ${address}：pattern_roles 形态不合：${shape.slice(0, 4).join('；')}`); continue; }
      for (const r of node.pattern_roles) {
        const source = knowledgeSource(active, r.pattern_ref);
        const row = rows.find(x => x.kind === 'patterns' && x.ref === where(r.pattern_ref));
        if (!source || source.kind !== 'patterns') problems.push(`${label} 的 ${address}：pattern_ref ${r.pattern_ref} 不是这一轮激活的模式`);
        else if (!source.roles.has(r.role)) problems.push(`${label} 的 ${address}：角色「${r.role}」不是 ${source.file} 声明的角色（${[...source.roles].join('、')}）`);
        else if (row?.outcome !== 'selected') problems.push(`${label} 的 ${address}：承担 ${source.file} 的角色，这个模式却没有选中的适用性事实——选中写一条 outcome: selected 的事实，讲为什么用它`);
        else { row.roles.push({ role: r.role, target_ref: address }); row.target_refs.push(address); }
      }
    }
  }
  for (const row of rows.filter(r => r.kind === 'patterns' && r.outcome === 'selected' && !r.roles.length)) {
    say(row.fact_id, `选中了 ${row.file}，却没有实体承担它的角色——在真正承担的设计对象上写 pattern_roles`);
  }
  return { rows, facts, problems };
}

/** 一条 must 自身：形态之外，来源是激活规约的一条，verify 合这条规约的执行体，出自的条目在适用性事实里是适用。 */
function mustProblems(knowledge, active, m, rows, at) {
  const source = knowledgeSource(active, m.source_ref);
  if (!source || source.kind !== 'constraints') return [`${at}：must 的 source_ref ${m.source_ref} 不是这一轮激活规约的条目`];
  const entry = entryOf(knowledge, source);
  if (!entry) return [`${at}：must 的 source_ref ${m.source_ref} 指的条目 ${source.unit || '（没写 #编号）'} 不在 ${source.file} 里`];
  const out = [];
  const verify = verifyProblem(entry, m.verify);
  if (verify) out.push(`${at} 的 ${entry.id} ${verify}`);
  const row = rows.find(r => r.source_ref === `${source.ref}#${source.unit}`);
  if (row?.outcome !== 'applied') {
    out.push(`${at}：must 出自 ${entry.id}，它在适用性事实里${row ? `是 ${row.outcome}` : '没有判断'}——义务只出自判定适用的条目`);
  }
  return out;
}

/**
 * 一个施工 Feature 的知识判断：CU 取它蓝图里的知识应用（按原生地址核），并把它的设计引用换成稳定地址作承接范围；
 * 非 CU 的维护 Feature 取它原生契约里的 `knowledge_facts`（同一形态，没有稳定地址与输入身份可核），全部由它承接。
 *
 * @returns {{rows: object[], facts: object[], problems: string[], scope: object|null, label: string, blueprint?: object}}
 *   scope 为 null 时判断全部由它承接；CU 带上读到的蓝图，专项明细（如埋点）从它取
 */
export function featureKnowledge(projectRoot, feature, contracts = null) {
  const who = featureIdentity(projectRoot, feature);
  if (who.status !== 'ok') {
    // 原生身份认不出（不存在的 CU、坏编号）：原样交回，不当成另一种对象去核
    const label = `Feature ${feature}`;
    return { rows: [], facts: [], problems: (who.issues ?? []).map(i => `${label}：原生 ${i.code ?? '问题'} ${i.message ?? ''}`), scope: NOTHING, label };
  }
  if (who.kind !== 'cu') {
    const label = `Feature ${feature} 的契约`;
    const active = activation(projectRoot);
    return { ...checkFacts(projectRoot, loadNative(projectRoot), active, { facts: contracts?.knowledge_facts ?? [],
      context: false, real: null, label }), scope: null, label };
  }
  const label = `蓝图 ${who.blueprintId}`;
  const read = readBlueprint(projectRoot, who.blueprintId, 'draft');
  if (read.status !== 'ok') return { rows: [], facts: [], problems: [`${label} 原生读不过（${read.status}）——设计负责方处理`], scope: NOTHING, label };
  const problems = [];
  const scope = unitScope(loadNative(projectRoot).module('scripts/utils/blueprint-addressing.ts'), read.blueprint, who.design_refs,
    ref => problems.push(`${label}：施工单位的设计引用 ${JSON.stringify(ref.target)} 在蓝图里解析不了——交设计负责方`));
  const checked = blueprintKnowledge(projectRoot, read.blueprint);
  return { ...checked, problems: [...problems, ...checked.problems], scope, label, blueprint: read.blueprint };
}

const NOTHING = { has: () => false, refs: () => [] };
//: 设计对象里承担引用职责的字段：证据与验证引用逐项按完整标识认；理由、说明等正文不算引用
const REF_FIELDS = ['evidence_refs', 'verification_refs'];

/**
 * 施工单位的设计责任范围：按原生目标关系判一个稳定地址在不在里面——它就是设计引用指向的对象、在其中，或包含它，
 * 不按地址字符串前缀猜。解析不了的设计引用交给 `bad` 报出来，不静默少算。
 */
function unitScope(addressing, blueprint, refs, bad) {
  const index = addressing.stableAddressIndex(blueprint);
  const roots = [];
  for (const ref of refs) {
    try {
      roots.push(addressing.resolveBlueprintTarget(blueprint, ref.target));
    } catch {
      bad(ref);
    }
  }
  const inside = new Set();
  const walk = (node) => {
    if (!node || typeof node !== 'object' || inside.has(node)) return;
    inside.add(node);
    for (const v of Object.values(node)) walk(v);
  };
  roots.forEach(walk);
  const holds = (node, seen = new Set()) => {
    if (!node || typeof node !== 'object' || seen.has(node)) return false;
    if (roots.includes(node)) return true;
    seen.add(node);
    return Object.values(node).some(v => holds(v, seen));
  };
  let cited = null;
  return { has: address => index.has(address) && (inside.has(index.get(address)) || holds(index.get(address))),
    // 设计责任内的对象在引用字段里写下的完整标识（事实没有原生地址，按 fact_id 整项比对）
    refs: () => (cited ??= [...new Set([...inside].flatMap(n => REF_FIELDS
      .flatMap(k => (Array.isArray(n[k]) ? n[k].filter(r => typeof r === 'string') : []))))]) };
}

/** 这个施工单位要承接的判断：落点（含模式角色落点）在它的设计责任内的；scope 为 null 时全部。 */
function carriedBy(rows, scope) {
  return rows.filter(d => !scope || d.target_refs.some(t => scope.has(t)));
}

/** 本施工单位要履行的判断：承接的适用规约条目（评审动作不产生代码要求，除外）与选中模式；spec、plan 门禁与知识任务共用。 */
export function unitDuties(judged) {
  const carried = carriedBy(judged.rows, judged.scope);
  return {
    applied: carried.filter(d => d.kind === 'constraints' && d.outcome === 'applied' && !d.reviewAction),
    selected: carried.filter(d => d.kind === 'patterns' && d.outcome === 'selected'),
  };
}

/**
 * 本单位人读章能引用的判断与事实，作者任务与审查任务共用这一份。判断：
 * `mine` 落点或角色在设计责任内的（含不适用、待定）；没有落点的不适用（整域无关、条目不适用）与拒绝是需求级公共依据
 * （`common`）；落点全在别的施工单位的不给。事实：本单位设计的引用字段里按 fact_id 整项引到的在 `facts`，
 * 其余关联未明、只给定位（`located`）。scope 为 null（平铺维护 Feature）时全部是本单位的。
 */
export function unitContext(judged) {
  const mine = carriedBy(judged.rows, judged.scope);
  const common = judged.rows.filter(d => !mine.includes(d) && !d.target_refs.length);
  const refs = judged.scope ? judged.scope.refs() : null;
  const cited = f => !refs || refs.includes(f.fact_id);
  return { mine, common, facts: judged.facts.filter(cited), located: judged.facts.filter(f => !cited(f)) };
}

/** 选中模式里由这个施工单位承担的角色：角色所在的对象在它的设计责任内；整体角色齐不齐在蓝图层核。 */
export function rolesOf(row, scope) {
  return (row.roles ?? []).filter(r => !scope || scope.has(r.target_ref));
}

/** 一条判断或义务对应的规约条目：按来源文件与单元找——不同文件可以有同编号的条目，不按裸编号取。 */
export function entryOf(knowledge, x) {
  return x?.file && x?.unit ? knowledge.entries.find(e => e.file === x.file && e.id === x.unit) ?? null : null;
}
