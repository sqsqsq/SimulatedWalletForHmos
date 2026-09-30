/**
 * 设计里的知识应用 —— 按合同形态、激活知识、原始摘要与原生稳定地址核一遍，并核每条激活规约都有判断。
 *
 * 判断只在原生设计里：蓝图 `decisions_and_gaps.decisions[]` 的 `kind: knowledge_application`，事实用到的知识在
 * `discovery.facts[].value.knowledge`；非 CU 的维护 Feature 用它原生契约里的 `knowledge_applications[]`。
 * 形态的唯一合同是 `skills/story/contracts/knowledge-application.schema.json`（用原生 lite-json-schema 校验）；
 * 这里补合同表达不了的：来源是不是激活的知识文件、类别与形态是否与文件一致、单元在不在文件里、
 * 原始摘要是否仍是现在的原文、落点是不是这份设计里真实的稳定地址、红线有没有被豁免、激活规约有没有漏判。
 *
 * 只读；缺判断、原文变了、落点失效都作为问题交回，由设计职责修订，这里不代写判断。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { featureIdentity, loadNative, readBlueprint } from './framework-access.mjs';
import { activeKnowledge } from './knowledge.mjs';
import { extensionRoot } from './paths.mjs';

//: 本模块所在的扩展包根：形态合同属于机制，随包发布
const PACKAGE = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const SCHEMA = path.join(PACKAGE, 'skills', 'story', 'contracts', 'knowledge-application.schema.json');

/** 激活知识按工程相对路径登记：类别、形态、单元、原始摘要，规约另带每条的强制力与哪几条是评审动作，模式另带声明的角色。 */
function activation(projectRoot) {
  const knowledge = activeKnowledge(projectRoot);
  const ext = extensionRoot(projectRoot);
  const out = new Map();
  const add = (kind, file, form, units, entries = [], roles = []) => {
    const abs = path.join(ext, ...file.split('/'));
    out.set(path.relative(projectRoot, abs).split(path.sep).join('/'), {
      kind, file, form, units,
      sha256: `sha256:${crypto.createHash('sha256').update(fs.readFileSync(abs)).digest('hex')}`,
      force: new Map(entries.map(e => [e.id, e.force])),
      reviewActions: new Set(entries.filter(e => e.reviewAction).map(e => e.id)),
      roles: new Set(roles),
    });
  };
  for (const c of knowledge.constraints) add('constraints', c.file, c.form, c.units, c.entries);
  for (const p of knowledge.patterns) add('patterns', p.file, p.form, p.units, [], [...(p.roles ?? []), ...(p.optionalRoles ?? [])]);
  for (const f of knowledge.facts) add('facts', f.file, f.form, f.units);
  return out;
}

function schemaCheck(native, value, name) {
  const lite = native.module('scripts/utils/lite-json-schema.ts');
  const schema = JSON.parse(fs.readFileSync(SCHEMA, 'utf-8'));
  const unsupported = lite.auditSchemaSupport(schema);
  if (unsupported.length) throw new Error(`${SCHEMA} 用了原生校验器不支持的关键字：${JSON.stringify(unsupported)}`);
  return lite.validateLiteSchema(value, { $ref: `#/$defs/${name}` }, schema).map(v => `${v.path} ${v.message}`);
}

const where = ref => String(ref ?? '').split('#')[0].replace(/\\/g, '/');

/**
 * @param {string} projectRoot
 * @param {{decisions: object[], facts?: object[], addresses?: Set<string>|null, label: string}} design
 *   `addresses` 是这份设计的原生稳定地址（没有就不核落点）；`label` 用在报错里说是哪份设计。
 * @returns {{rows: object[], problems: string[]}} rows 是合格的知识应用决定，按激活清单里的来源与单元带上文件，
 *   评审动作（不产生代码要求，不进验收与义务）标 `reviewAction`
 */
function checkKnowledgeApplications(projectRoot, { decisions, facts = [], addresses = null, label }) {
  const native = loadNative(projectRoot);
  const active = activation(projectRoot);
  const problems = [];
  const rows = [];
  const judged = new Map();
  const say = (id, text) => problems.push(`${label} 的知识应用 ${id}：${text}`);
  for (const d of decisions.filter(x => x?.kind === 'knowledge_application')) {
    const id = d.decision_id ?? '（无编号）';
    const shape = schemaCheck(native, d, 'decision');
    if (shape.length) { say(id, `形态不合 knowledge-application.schema.json：${shape.slice(0, 4).join('；')}`); continue; }
    const k = d.knowledge;
    const source = active.get(where(d.provenance.source_ref));
    if (!source) { say(id, `来源 ${d.provenance.source_ref} 不是这一轮激活的知识文件`); continue; }
    if (source.kind !== k.kind || source.form !== k.form) { say(id, `写的是 ${k.kind}/${k.form}，来源文件是 ${source.kind}/${source.form}`); continue; }
    if (!source.units.includes(k.unit)) { say(id, `单元 ${k.unit} 不在 ${source.file} 里`); continue; }
    if (k.source_sha256 !== source.sha256) {
      say(id, `判断时的原文摘要 ${k.source_sha256} 与 ${source.file} 现在的 ${source.sha256} 不同——知识原文变了，按新原文重判`);
    }
    if (k.outcome === 'waived' && source.force.get(k.unit) === '红线') say(id, `${k.unit} 是红线，不能豁免`);
    const undeclared = (k.roles ?? []).map(r => r.role).filter(role => !source.roles.has(role));
    if (undeclared.length) say(id, `角色 ${undeclared.join('、')} 不是 ${source.file} 声明的角色（${[...source.roles].join('、')}）`);
    if (addresses) {
      const refs = [...k.target_refs, ...(k.roles ?? []).map(r => r.target_ref)];
      const dangling = refs.filter(r => !addresses.has(r));
      if (dangling.length) say(id, `落点不是这份设计里的稳定地址：${[...new Set(dangling)].join('、')}`);
    }
    const key = `${source.file}#${k.unit}`;
    if (judged.has(key)) say(id, `与 ${judged.get(key)} 判的是同一条（${key}），一条知识只判一次`);
    judged.set(key, id);
    rows.push({ ...d, file: source.file, reviewAction: source.reviewActions.has(k.unit) });
  }
  for (const [ref, source] of active) {
    if (source.kind !== 'constraints') continue;
    const missing = source.units.filter(u => !judged.has(`${source.file}#${u}`));
    if (missing.length) {
      problems.push(`${label} 没有判断激活规约 ${missing.join('、')}（${ref}）——规约逐条判断，不适用也要写明本需求哪个条件不成立`);
    }
  }
  for (const f of facts.filter(x => x?.value?.knowledge)) {
    const id = f.fact_id ?? '（无编号）';
    const shape = schemaCheck(native, f.value.knowledge, 'factKnowledge');
    const source = active.get(where(f.provenance?.source_ref));
    if (shape.length) problems.push(`${label} 的事实 ${id}：知识引用形态不合：${shape.slice(0, 4).join('；')}`);
    else if (!source || source.kind !== 'facts') problems.push(`${label} 的事实 ${id}：来源 ${f.provenance?.source_ref} 不是激活的项目事实`);
    else if (!source.units.includes(f.value.knowledge.unit)) problems.push(`${label} 的事实 ${id}：单元 ${f.value.knowledge.unit} 不在 ${source.file} 里`);
    else if (f.value.knowledge.source_sha256 !== source.sha256) problems.push(`${label} 的事实 ${id}：${source.file} 原文在记录之后变了，按新原文重核`);
  }
  return { rows, problems };
}

/** 蓝图里的知识应用：决定、事实，落点按原生稳定地址核。 */
export function blueprintKnowledge(projectRoot, blueprint) {
  const addressing = loadNative(projectRoot).module('scripts/utils/blueprint-addressing.ts');
  return checkKnowledgeApplications(projectRoot, {
    decisions: blueprint.decisions_and_gaps?.decisions ?? [],
    facts: blueprint.discovery?.facts ?? [],
    addresses: new Set(addressing.stableAddressIndex(blueprint).keys()),
    label: `蓝图 ${blueprint.blueprint_id}`,
  });
}

/**
 * 一个施工 Feature 的知识判断：CU 取它蓝图里的知识应用（按原生地址核），并把它的设计引用换成稳定地址作承接范围；
 * 非 CU 的维护 Feature 取它原生契约里的 `knowledge_applications`，没有蓝图也不去猜 Story。
 *
 * @returns {{rows: object[], problems: string[], scope: Set<string>|null, label: string, blueprint?: object}}
 *   scope 为 null 时判断全部由它承接；CU 带上读到的蓝图，专项明细（如埋点）从它取
 */
export function featureKnowledge(projectRoot, feature, contracts) {
  const who = featureIdentity(projectRoot, feature);
  if (who.status !== 'ok') {
    // 原生身份认不出（不存在的 CU、坏编号）：原样交回，不当成另一种对象去核
    const label = `Feature ${feature}`;
    return { rows: [], problems: (who.issues ?? []).map(i => `${label}：原生 ${i.code ?? '问题'} ${i.message ?? ''}`), scope: NOTHING, label };
  }
  if (who.kind !== 'cu') {
    return { ...checkKnowledgeApplications(projectRoot, {
      decisions: contracts?.knowledge_applications ?? [], label: `Feature ${feature} 的契约` }), scope: null, label: `Feature ${feature} 的契约` };
  }
  const label = `蓝图 ${who.blueprintId}`;
  const read = readBlueprint(projectRoot, who.blueprintId, 'draft');
  if (read.status !== 'ok') return { rows: [], problems: [`${label} 原生读不过（${read.status}）——设计负责方处理`], scope: NOTHING, label };
  const problems = [];
  const scope = unitScope(loadNative(projectRoot).module('scripts/utils/blueprint-addressing.ts'), read.blueprint, who.design_refs,
    ref => problems.push(`${label}：施工单位的设计引用 ${JSON.stringify(ref.target)} 在蓝图里解析不了——交设计负责方`));
  const checked = blueprintKnowledge(projectRoot, read.blueprint);
  return { ...checked, problems: [...problems, ...checked.problems], scope, label, blueprint: read.blueprint };
}

const NOTHING = { has: () => false };

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
  return { has: address => index.has(address) && (inside.has(index.get(address)) || holds(index.get(address))) };
}

/** 这个施工单位要承接的判断：落点（含模式角色落点）在它的设计责任内的；scope 为 null 时全部。 */
export function carriedBy(rows, scope) {
  return rows.filter(d => !scope || [...(d.knowledge.target_refs ?? []), ...(d.knowledge.roles ?? []).map(r => r.target_ref)]
    .some(t => scope.has(t)));
}

/** 选型决定里由这个施工单位承担的角色：角色自己的落点在它的设计责任内；整体角色齐不齐在蓝图层核。 */
export function rolesOf(decision, scope) {
  return (decision.knowledge.roles ?? []).filter(r => !scope || scope.has(r.target_ref));
}

/** 一条判断对应的规约条目：按判断的来源文件与单元找——不同文件可以有同编号的条目，不按裸编号取。 */
export function entryOf(knowledge, decision) {
  return decision?.file ? knowledge.entries.find(e => e.file === decision.file && e.id === decision.knowledge?.unit) ?? null : null;
}
