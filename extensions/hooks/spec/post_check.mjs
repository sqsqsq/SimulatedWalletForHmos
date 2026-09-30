/**
 * spec 阶段 post_check（实例扩展）—— 本施工单位的验收有没有承接设计里适用的规约判断。
 *
 * 判断只在原生设计里（CU 的蓝图知识应用决定；非 CU 维护 Feature 契约里的 knowledge_applications）。
 * 本阶段机械核三件事：
 *   ① **验收承接**——本施工单位承接的每条适用判断，acceptance 里有带 `knowledge_rule` 与
 *      `knowledge_decision_id` 的条目；桥接指回的都是承接的适用判断；
 *   ② **验收标准一致**——spec.md「验收标准」里定义的编号在 acceptance.yaml 里有，关联功能一致；
 *   ③ **审查报告**——格式、判据全不全、一对象一结论、WARN 的处置。
 *
 * 验收是否真的覆盖了规约要求的行为与验证责任，是语义判断，归独立审查。
 *
 * 契约：stdin JSON ctx → stdout JSON result。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { guard, gate } from '../shared/gate.mjs';
import { activeKnowledge } from '../shared/knowledge.mjs';
import { carriedBy, featureKnowledge } from '../shared/knowledge-application.mjs';
import { acceptanceIdRe, functionIdRe, knowledgeCriteria, phaseArtifacts } from '../shared/contracts.mjs';
import { reportProblems } from '../shared/verifier-report.mjs';

/** 「验收标准」一节的正文行：标题下到下一个同级或更高级标题。 */
function acceptanceSection(lines) {
  const at = lines.findIndex(l => /^#{1,6}\s/.test(l) && /验收标准/.test(l));
  if (at === -1) return null;
  const level = lines[at].match(/^#+/)[0].length;
  const end = lines.findIndex((l, i) => i > at && /^#{1,6}\s/.test(l) && l.match(/^#+/)[0].length <= level);
  return lines.slice(at + 1, end === -1 ? lines.length : end);
}

/**
 * 「验收标准」与 acceptance.yaml 对得上：一个编号只说一件事；「验收标准」里一个编号第一次作行首的那一行是它的定义，
 * 编号要在 acceptance.yaml 里有，关联功能与 `prd_function` 一致。
 */
function acceptanceAlignment(lines, acceptance) {
  const problems = [];
  const body = acceptanceSection(lines);
  if (!body) return problems;
  const entries = ['criteria', 'boundaries'].flatMap(k => (Array.isArray(acceptance?.[k]) ? acceptance[k] : []));
  const accById = new Map();
  for (const e of entries) {
    const id = String(e?.id ?? '').trim();
    if (id) accById.set(id, [...(accById.get(id) ?? []), e]);
  }
  for (const [id, list] of accById) {
    if (list.length > 1) problems.push(`acceptance.yaml：${id} 同号不同义，在 criteria 与 boundaries 里有 ${list.length} 条——验收条目按 id 认，一个编号只说一件事，下游按编号取验收`);
  }
  const defined = new Map();
  for (const raw of body) {
    const line = raw.trim();
    if (!line || line.startsWith('>') || /不承接/.test(line)) continue;
    const ids = [...line.matchAll(acceptanceIdRe())].map(m => m[0]);
    if (ids.length && !defined.has(ids[0])) {
      defined.set(ids[0], [...line.replace(acceptanceIdRe(), ' ').matchAll(functionIdRe())].map(m => m[0]));
    }
  }
  for (const [id, codes] of defined) {
    const acc = accById.get(id);
    if (!acc) {
      problems.push(`spec.md「验收标准」：${id} 在 acceptance.yaml 里没有——验收清单以 acceptance.yaml 的 criteria 与 boundaries 为全集，「验收标准」每行的第一个验收编号按 id 在其中找`);
      continue;
    }
    const want = String(acc[0]?.prd_function ?? '').split(/[\s,，、]+/).filter(Boolean).sort().join('、');
    const got = [...new Set(codes)].sort().join('、');
    if (want && got && want !== got) {
      problems.push(`spec.md「验收标准」：${id} 的关联功能两处不一致，「验收标准」写 ${got}，acceptance.yaml 的 prd_function 写 ${want}——${id} 第一次作行首的那一行里其余的功能编号是它的关联功能，按集合与 prd_function 比对`);
    }
  }
  return problems;
}

export default guard('spec', async (ctx) => {
  const design = { name: '设计里的知识判断', problems: [], skipped: [] };
  const bridge = { name: '验收承接适用规约', problems: [], skipped: [] };
  const alignment = { name: '验收标准与 acceptance.yaml', problems: [], skipped: [] };
  const groups = [design, bridge, alignment];

  const inputs = phaseArtifacts(ctx.projectRoot, ctx.feature, 'spec');
  if (!inputs.dir) return gate(ctx, { problems: inputs.problems });
  groups.unshift({ name: '原生对本阶段输入报的问题', problems: inputs.problems, skipped: [] });
  const acceptance = inputs.acceptance;

  let knowledge = null;
  try {
    knowledge = activeKnowledge(ctx.projectRoot);
  } catch (e) {
    design.problems.push(`${e.message}——激活知识派生失败；判断的来源与验收桥都按它核`);
  }
  if (knowledge) {
    const judged = featureKnowledge(ctx.projectRoot, ctx.feature, inputs.contracts);
    design.problems.push(...judged.problems);
    const applied = carriedBy(judged.rows, judged.scope)
      .filter(d => d.knowledge.kind === 'constraints' && d.knowledge.outcome === 'applied' && !d.reviewAction);
    if (!acceptance) {
      if (applied.length) bridge.skipped.push({ what: '验收承接适用规约', why: inputs.why });
    } else {
      const { byRule, problems } = knowledgeCriteria(acceptance);
      bridge.problems.push(...problems);
      for (const d of applied) {
        const rows = (byRule.get(d.knowledge.unit) ?? []).filter(r => String(r.knowledge_decision_id).trim() === d.decision_id);
        if (!rows.length) {
          bridge.problems.push(`acceptance.yaml：${judged.label} 的适用判断 ${d.decision_id}（${d.knowledge.unit}）没有验收条目承接——`
            + `写一条 criteria，带 knowledge_rule: ${d.knowledge.unit} 与 knowledge_decision_id: ${d.decision_id}；下游 ut / testing 按它找要覆盖的场景`);
        }
      }
      const known = new Set(applied.map(d => d.decision_id));
      for (const [rule, rows] of byRule) {
        for (const r of rows.filter(x => !known.has(String(x.knowledge_decision_id).trim()))) {
          bridge.problems.push(`acceptance.yaml「${String(r.id ?? '（没写 id）')}」：knowledge_rule ${rule} 指向 ${r.knowledge_decision_id}，它不是本施工单位承接的适用判断`);
        }
      }
    }
  }

  const specPath = path.join(inputs.dir, 'spec', 'spec.md');
  if (!fs.existsSync(specPath)) alignment.skipped.push({ what: '验收标准与 acceptance.yaml', why: '这一次没有生成 spec.md' });
  else if (acceptance) {
    alignment.problems.push(...acceptanceAlignment(fs.readFileSync(specPath, 'utf-8').split(/\r?\n/), acceptance));
  }

  groups.push({ name: '审查报告', problems: reportProblems(ctx.projectRoot, ctx.feature, 'spec'), skipped: [] });
  return gate(ctx, { groups });
});
