/**
 * plan 阶段 post_check（实例扩展）—— 设计里的知识判断是否**落到了契约实体上**。
 *
 * 判断只在原生设计里（CU 的蓝图知识应用决定；非 CU 维护 Feature 契约里的 knowledge_applications）。
 * 本阶段核四件事：
 *   ① **挂对地方**——must 只挂五类实体，`files` 只是授权文件清单；编号在册，text 写了，verify 取值封闭；
 *   ② **判断与义务一致**——本施工单位承接的每条适用判断至少有一处 must（带它的 decision_id），
 *      每条 must 都认得回一条承接的适用判断；
 *   ③ **模式角色**——承担角色的实体带 `pattern_roles`，角色取选型决定与模式声明，选中的角色都有实体承担；
 *   ④ **引用**——用例引的验收编号存在；
 *   ⑤ **埋点逐点落实**——蓝图里落在本单位的每个统计点，plan.md 的逐点表里有行，责任方法是契约声明的方法。
 *
 * 「义务是不是真的被应用了」「text 写的是不是本需求的设计」是语义判断，归独立审查。
 *
 * 契约：stdin JSON ctx → stdout JSON result。
 */
import * as path from 'node:path';
import { guard, gate } from '../shared/gate.mjs';
import { activeKnowledge, entryById } from '../shared/knowledge.mjs';
import { carriedBy, featureKnowledge } from '../shared/knowledge-application.mjs';
import { obligationsFromContracts, misplacedMust, patternRolesFromContracts, verifyProblem }
  from '../shared/obligations.mjs';
import { readTextOrNull } from '../shared/paths.mjs';
import { designStatPoints, planStatRows, pointKey } from '../shared/stat-points.mjs';
import { featureDir } from '../shared/framework-access.mjs';
import { readAcceptance, readContracts, resourceEntries } from '../shared/contracts.mjs';
import { parseYaml } from '../shared/yaml.mjs';
import { reportProblems } from '../shared/verifier-report.mjs';

/**
 * `use-cases.yaml` 里 `linked_acceptance` 引的编号都要在 `acceptance.yaml` 里存在。
 * 验收编号取 acceptance 顶层各列表条目的 `id`，不认前缀；文件缺席或读不了与悬空引用分开报。
 */
function acceptanceRefProblems(projectRoot, feature, group) {
  const raw = readTextOrNull(path.join(featureDir(projectRoot, feature), 'use-cases.yaml'));
  if (raw === null) return [];
  const acc = readAcceptance(projectRoot, feature);
  if (!acc.acceptance) {
    group.skipped.push({ what: '用例的验收引用', why: acc.error ?? '没有 acceptance.yaml' });
    return [];
  }
  let cases;
  try { cases = parseYaml(raw); } catch (e) { return [`use-cases.yaml：解析失败（${e.message}）——linked_acceptance 的验收引用从这份 YAML 读，解析不了就核不了`]; }
  const ids = new Set(Object.values(acc.acceptance).filter(Array.isArray).flat()
    .map(c => c?.id).filter(Boolean).map(String));
  const dangling = new Map();
  const walk = (node, at) => {
    if (Array.isArray(node)) { node.forEach(n => walk(n, at)); return; }
    if (!node || typeof node !== 'object') return;
    const here = node.id ? String(node.id) : at;
    for (const ref of Array.isArray(node.linked_acceptance) ? node.linked_acceptance : []) {
      if (!ids.has(String(ref))) dangling.set(String(ref), [...(dangling.get(String(ref)) ?? []), here]);
    }
    Object.values(node).forEach(v => walk(v, here));
  };
  walk(cases, '');
  return [...dangling].map(([ref, at]) => `use-cases.yaml 引了验收 ${ref}（${[...new Set(at)].join('、')}），`
    + 'acceptance.yaml 里没有这个编号——验收编号取 acceptance.yaml 各列表条目的 id，下游按编号取验收');
}

/**
 * 埋点逐点落实：蓝图落在本单位的每个统计点在 plan.md 的逐点表里有行，每行的责任方法是契约声明的方法。
 * 只核对应与引用；结果、来源、去重与验证写没写到位是语义，归独立审查。
 */
function statProblems(ctx, design, contracts, group) {
  const want = designStatPoints(design);
  if (want.state === 'none' || want.state === 'missing') { group.skipped.push({ what: '埋点逐统计点落实', why: want.why }); return; }
  if (want.state === 'empty') {
    group.skipped.push({ what: '埋点逐统计点落实', why: `蓝图的埋点明细（${want.details.map(d => d.id).join('、')}）里没有表头含「统计点」的表` });
    return;
  }
  const planText = readTextOrNull(path.join(featureDir(ctx.projectRoot, ctx.feature), 'plan', 'plan.md'));
  if (planText === null) { group.skipped.push({ what: '埋点逐统计点落实', why: '这一次没有 plan.md，逐点表无处可对' }); return; }
  const rows = planStatRows(planText);
  const points = want.details.flatMap(d => d.rows.map(r => r[0]));
  const have = new Set(rows.map(r => pointKey(r.point)));
  const missing = [...new Set(points.filter(p => !have.has(pointKey(p))))];
  if (missing.length) {
    group.problems.push(`plan.md：蓝图埋点明细的这些统计点在逐点表里没有行：${missing.join('、')}——逐点表是表头含「统计点」与「责任方法」的表，`
      + '统计点名去掉空白与标记后按名比对，每个统计点列出适用结果及责任方法，允许多行');
  }
  if (!contracts) { group.skipped.push({ what: '责任方法', why: '契约读不到' }); return; }
  const list = (x) => (Array.isArray(x) ? x : []);
  const declared = new Set(list(contracts.interfaces).flatMap(i => list(i?.methods).map(m => `${i?.name}.${m?.name}`)));
  const seen = new Map();
  for (const r of rows) {
    const k = (seen.get(pointKey(r.point)) ?? 0) + 1;
    seen.set(pointKey(r.point), k);
    const at = `plan.md 逐点表「${r.point}」第 ${k} 条结果行`;
    if (!r.methods.length) group.problems.push(`${at}没写责任方法——「责任方法」列按「接口.方法」读，指向 contracts.yaml 里决定这个结果的那个方法`);
    const unknown = r.methods.filter(m => !declared.has(m));
    if (unknown.length) {
      group.problems.push(`${at}的责任方法 ${unknown.join('、')} 在 contracts.yaml 的 interfaces[].methods[] 里找不到——责任方法按「接口.方法」与契约声明的方法比对`);
    }
  }
}

export default guard('plan', async (ctx) => {
  const contract = { name: '契约可读与 must 挂位', problems: [], skipped: [] };
  const design = { name: '设计里的知识判断', problems: [], skipped: [] };
  const obligation = { name: '每条 must 自身', problems: [], skipped: [] };
  const consistency = { name: '判断与义务一致', problems: [], skipped: [] };
  const pattern = { name: '模式角色', problems: [], skipped: [] };
  const reference = { name: '用例的验收引用', problems: [], skipped: [] };
  const stat = { name: '埋点逐统计点落实', problems: [], skipped: [] };
  const groups = [contract, design, obligation, consistency, pattern, reference, stat];

  reference.problems.push(...acceptanceRefProblems(ctx.projectRoot, ctx.feature, reference));

  // ---- 契约可读、must 挂位、resource_keys 形状 ----
  const read = readContracts(ctx.projectRoot, ctx.feature);
  const contracts = read.contracts;
  if (read.error) contract.problems.push(read.error);
  else if (!read.exists) {
    // 契约缺失由原生门禁判；本组判据没跑成要说出来
    contract.skipped.push({ what: '契约实体上的义务与角色', why: '契约还没建' });
  } else {
    for (const bad of misplacedMust(contracts)) {
      contract.problems.push(`${bad}——must 的挂载位置是封闭集合（data_models[].fields[]、interfaces[].methods[]、components[] 及其 state[]、resource_keys 的资源条目），coding 只从这些位置读义务`);
    }
    contract.problems.push(...resourceEntries(contracts).problems);
  }
  const noContract = contracts ? null : (read.error ? '契约解析失败' : '契约还没建');

  // ---- 设计里的知识判断：本施工单位承接的那部分 ----
  let knowledge = null;
  try {
    knowledge = activeKnowledge(ctx.projectRoot);
  } catch (e) {
    obligation.problems.push(`${e.message}——激活知识派生失败；must 的编号、verify 与判断的来源都按它核`);
  }
  const judged = knowledge ? featureKnowledge(ctx.projectRoot, ctx.feature, contracts) : null;
  if (judged) design.problems.push(...judged.problems);
  const carried = judged ? carriedBy(judged.rows, judged.scope) : [];
  const applied = carried.filter(d => d.knowledge.kind === 'constraints' && d.knowledge.outcome === 'applied' && !d.reviewAction);
  const selected = carried.filter(d => d.knowledge.kind === 'patterns' && ['selected', 'adjusted'].includes(d.knowledge.outcome));
  const why = noContract ?? (knowledge ? null : '激活知识派生失败');
  const obligations = contracts ? obligationsFromContracts(contracts) : [];

  // ---- 每条 must 自身：编号在册、text、verify、出自哪条承接的适用判断 ----
  if (why) {
    obligation.skipped.push({ what: '每条 must 的编号、text、verify 与决定', why });
  } else {
    for (const ob of obligations) {
      const at = `contracts.yaml 的 ${ob.entityPath || '(未知实体)'}`;
      if (!ob.rule) { obligation.problems.push(`${at}：有一条 must 没写 rule——must 按 rule 的编号认回激活知识里的规约条目`); continue; }
      const entry = entryById(knowledge, ob.rule);
      if (!entry) { obligation.problems.push(`${at}：must.rule「${ob.rule}」不在激活知识里`); continue; }
      if (!ob.text) obligation.problems.push(`${at}：${ob.rule} 的 must 缺 text——text 写这条规约在本需求落实成什么，coding 按它落实`);
      const verify = verifyProblem(entry, ob.verify);
      if (verify) obligation.problems.push(`${at} 的 ${ob.rule} ${verify}`);
      const decision = applied.find(d => d.decision_id === ob.decisionId);
      if (!ob.decisionId) obligation.problems.push(`${at}：${ob.rule} 的 must 没写 decision_id——义务按它认回设计里那条适用判断`);
      else if (!decision) obligation.problems.push(`${at}：${ob.rule} 的 must 指向 ${ob.decisionId}，它不是本施工单位承接的适用判断`);
      else if (decision.knowledge.unit !== ob.rule) obligation.problems.push(`${at}：must.rule 是 ${ob.rule}，它指向的判断 ${ob.decisionId} 判的是 ${decision.knowledge.unit}`);
    }
    for (const rule of new Set(obligations.map(o => o.rule))) {
      if (entryById(knowledge, rule)?.probe?.kind !== 'present_in_method') continue;
      if (!obligations.some(o => o.rule === rule && o.entityKind === 'interfaces')) {
        obligation.skipped.push({ what: `${rule} 的探针`, why: '探针无落点：它查方法体，而这条规约没有挂在 interfaces[].methods[] 上的 must' });
      }
    }
  }

  // ---- 判断与义务一致：承接的每条适用判断都有实体扛着 ----
  if (why) {
    consistency.skipped.push({ what: '判断与义务一致', why });
  } else {
    for (const d of applied) {
      if (!obligations.some(o => o.decisionId === d.decision_id)) {
        consistency.problems.push(`contracts.yaml：${judged.label} 的适用判断 ${d.decision_id}（${d.knowledge.unit}，落在 ${d.knowledge.target_refs.join('、')}）`
          + '在契约里没有实体扛着——义务以 must（带 decision_id）挂在承担它的实体上，coding 从实体读义务');
      }
    }
  }

  // ---- 模式角色：实体上的 pattern_roles 认回选型决定与模式声明，选中的角色都有实体承担 ----
  if (why) {
    pattern.skipped.push({ what: '模式角色', why });
  } else {
    const roles = patternRolesFromContracts(contracts);
    for (const pr of roles) {
      const at = `contracts.yaml 的 ${pr.entityPath}`;
      const decision = selected.find(d => d.decision_id === pr.decisionId);
      if (!decision) { pattern.problems.push(`${at}：pattern_roles 指向 ${pr.decisionId || '（没写 decision_id）'}，它不是本施工单位承接的选型决定`); continue; }
      const declared = knowledge.patterns.find(p => p.file === decision.file);
      if (declared && pr.pattern !== declared.id) pattern.problems.push(`${at}：pattern 写的是 ${pr.pattern}，决定 ${pr.decisionId} 选的是 ${declared.id}`);
      if (!(decision.knowledge.roles ?? []).some(r => r.role === pr.role)) {
        pattern.problems.push(`${at}：角色「${pr.role}」不在决定 ${pr.decisionId} 选定的角色里（${(decision.knowledge.roles ?? []).map(r => r.role).join('、')}）`);
      }
    }
    for (const d of selected) {
      for (const r of d.knowledge.roles ?? []) {
        if (!roles.some(pr => pr.decisionId === d.decision_id && pr.role === r.role)) {
          pattern.problems.push(`contracts.yaml：选型决定 ${d.decision_id} 的角色「${r.role}」（${r.target_ref}）没有实体承担——在真正承担它的 components / interfaces / data_models 上写 pattern_roles`);
        }
      }
    }
  }

  if (judged) statProblems(ctx, judged, contracts, stat);

  // ---- 本阶段审查报告：格式、判据全不全、一对象一结论、WARN 行的处置 ----
  groups.push({ name: '审查报告', problems: reportProblems(ctx.projectRoot, ctx.feature, 'plan'), skipped: [] });

  return gate(ctx, { groups });
});
