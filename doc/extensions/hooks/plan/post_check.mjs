/**
 * plan 阶段 post_check（实例扩展）—— 知识冻结的结构级门禁。
 *
 * 本阶段是全链唯一的冻结点。这里只判**结构与可解析性**：
 *   1. 知识决策章在第一个设计章之前（位置即语义——排在后面只能是事后总结）；
 *   2. 冻结块存在，义务集与 spec 约束要求集一致；
 *   3. 每条义务三重锚定：落点实体可解析、业务步骤可定位、anchor 指向真实设计章且非自指；
 *   4. 验证要求挂在验收条目上（四阶段分派的单源）；
 *   5. 模式角色完备、实体存在、coordinator 一致；
 *   6. obligation 不是规约原文的复制。
 *
 * **不判**「这条义务是不是真的解决了本需求」——那是语义判断，归 verifier 全集逐行裁决。
 * 机械层越权下语义结论，「写了字」就会变成「做到了」。
 *
 * 契约：stdin JSON ctx → stdout JSON result。
 */
import * as path from 'node:path';
import { activeKnowledge, entryById, paraphraseSources } from '../shared/knowledge.mjs';
import { isPureCopy } from '../shared/paraphrase.mjs';
import { featureRoot, lines, readTextOrNull } from '../shared/paths.mjs';
import {
  contractsPath,
  knowledgeCriteria,
  landingRefs,
  readAcceptance,
  readContracts,
  readFreeze,
  resolveEntityRef,
} from '../shared/freeze.mjs';

const INJECTION_DOC = 'doc/extensions/hooks/plan/on_context_load.md';

/** 第一个设计章：这些是 plan 模板里承载方案的章，知识决策必须排在它们之前。 */
const DESIGN_HEADING_RE = /^##\s*\d*[.、]?\s*(模块架构|目录|文件结构|数据模型|页面组件|状态管理|服务层|接口定义|路由|导航)/;
const DECISION_HEADING_RE = /^##\s*知识决策/;

function findHeadings(text) {
  const rows = lines(text);
  let decision = -1;
  let design = -1;
  const all = [];
  rows.forEach((line, i) => {
    const s = line.trim();
    const h = s.match(/^(#{2,4})\s+(.*)$/);
    if (h) all.push({ line: i + 1, level: h[1].length, title: h[2].trim() });
    if (decision < 0 && DECISION_HEADING_RE.test(s)) decision = i + 1;
    if (design < 0 && DESIGN_HEADING_RE.test(s)) design = i + 1;
  });
  return { decision, design, all };
}

/** spec 约束要求章里登记的条目编号（冻结义务集要与它一致）。 */
function specExitIds(projectRoot, feature) {
  const p = path.join(featureRoot(projectRoot, feature), 'spec', 'spec.md');
  const text = readTextOrNull(p);
  if (text === null) return null;
  const rows = lines(text);
  const start = rows.findIndex(l => /^#{2,4}\s+.*规约约束要求/.test(l.trim()));
  if (start < 0) return null;
  const level = (rows[start].trim().match(/^(#{2,4})/) ?? ['', '##'])[1].length;
  const ids = new Set();
  for (let i = start + 1; i < rows.length; i++) {
    const h = rows[i].trim().match(/^(#{2,4})\s+/);
    if (h && h[1].length <= level) break;
    const s = rows[i].trim();
    if (!s.startsWith('|')) continue;
    const first = s.replace(/^\||\|$/g, '').split('|')[0]?.trim() ?? '';
    if (/^\{.*\}$/.test(first)) continue;
    for (const m of first.matchAll(/\b[A-Z][A-Z0-9]{1,7}-\d{2}\b/g)) ids.add(m[0]);
  }
  return ids;
}

/** use-cases.yaml 的 branch 标识与 coordinator（步骤定位与模式一致性用）。 */
function readUseCases(projectRoot, feature) {
  const p = path.join(featureRoot(projectRoot, feature), 'use-cases.yaml');
  const text = readTextOrNull(p);
  if (text === null) return { exists: false, branches: new Set(), coordinators: new Set() };
  const branches = new Set();
  const coordinators = new Set();
  for (const line of lines(text)) {
    const b = line.match(/^\s*(?:-\s*)?id\s*:\s*["']?([\w.-]+)/);
    if (b) branches.add(b[1]);
    const c = line.match(/^\s*coordinator\s*:\s*["']?([\w.$-]+)/);
    if (c) coordinators.add(c[1]);
  }
  return { exists: true, branches, coordinators };
}

export default async function planPostCheck(ctx) {
  if (ctx?.phase !== 'plan' || !ctx?.feature || !ctx?.projectRoot) return { ok: true };

  const planPath = path.join(featureRoot(ctx.projectRoot, ctx.feature), 'plan', 'plan.md');
  const planText = readTextOrNull(planPath);
  if (planText === null) return { ok: true };   // plan.md 缺失由框架的 check-plan 负责

  let knowledge;
  try {
    knowledge = activeKnowledge(ctx.projectRoot);
  } catch (e) {
    return blocker([`激活知识派生失败：${e.message}`]);
  }

  const problems = [];

  // ---- 1. 知识决策章的位置：位置即语义 ----
  const { decision, design } = findHeadings(planText);
  if (decision < 0) {
    problems.push('plan.md 缺「知识决策（设计输入）」章'
      + '——知识决策要先于它影响的设计，排在后面就只能是事后总结');
  } else if (design > 0 && decision > design) {
    problems.push(`「知识决策（设计输入）」在第 ${decision} 行，晚于第一个设计章（第 ${design} 行）`
      + '——位置就是语义：排在设计之后，它只能是「做完了顺便声明用过哪些知识」');
  }

  // ---- 2. 冻结块 ----
  const { contracts, error, exists } = readContracts(ctx.projectRoot, ctx.feature);
  if (error) return blocker([error]);
  if (!exists) {
    problems.push(`缺 ${rel(ctx.projectRoot, contractsPath(ctx.projectRoot, ctx.feature))}`
      + '——冻结结果是下游唯一的知识入口，没有它下游零注入');
    return blocker(problems);
  }
  const { freeze, obligations, patterns } = readFreeze(contracts);
  if (!freeze) {
    problems.push('contracts.yaml 缺 knowledge_freeze 块——下游读的是它，不是知识目录；'
      + `形态见 ${INJECTION_DOC}`);
    return blocker(problems);
  }

  // ---- 3. 义务集与 spec 出口集一致 ----
  const specIds = specExitIds(ctx.projectRoot, ctx.feature);
  const freezeIds = new Set(obligations.map(o => String(o.rule ?? '').trim()).filter(Boolean));
  if (specIds) {
    const missing = [...specIds].filter(id => !freezeIds.has(id));
    const extra = [...freezeIds].filter(id => !specIds.has(id));
    if (missing.length) {
      problems.push(`spec 判了这些条目有代码要求，冻结里却没有对应义务：${missing.join('、')}`
        + '——知识在设计阶段就丢了，后面编码不可能补回来');
    }
    if (extra.length) {
      problems.push(`冻结了 spec 里没有要求的条目：${extra.join('、')}`
        + '——义务应当来自 spec 的判定结论，不是这里新造的');
    }
  }

  // ---- 4. 逐条义务：三重锚定 + 验证要求 + 复述 ----
  const { acceptance } = readAcceptance(ctx.projectRoot, ctx.feature);
  const criteria = knowledgeCriteria(acceptance);
  const useCases = readUseCases(ctx.projectRoot, ctx.feature);
  const planHeadings = findHeadings(planText).all.map(h => h.title);

  for (const ob of obligations) {
    const rule = String(ob.rule ?? '').trim() || '(缺 rule)';
    const at = `义务 ${rule}`;
    if (!ob.rule) { problems.push(`${at}：缺 rule（一条目一行，不要一行塞多条）`); continue; }
    const entry = entryById(knowledge, rule);
    if (!entry) {
      problems.push(`${at}：编号不在激活清单里——写错了，或那条规约已下架`);
      continue;
    }

    const text = String(ob.obligation ?? '').trim();
    if (!text) {
      problems.push(`${at}：缺 obligation——写本次要落实成什么，不是复述规约原文`);
    } else {
      const { copied, source } = isPureCopy(text, paraphraseSources(knowledge, rule));
      if (copied) {
        problems.push(`${at}：obligation 是规约原文的复制或子串（来源「${source}…」）`
          + '——写可实施的设计结论：它落在哪个实体、哪个步骤上');
      }
    }

    // 落点实体（评审动作条目豁免）
    const refs = landingRefs(ob);
    if (!refs.length) {
      if (!entry.reviewAction) {
        problems.push(`${at}：landing 为空——没有承载它的契约实体，到编码那里这条义务等于不存在`);
      }
    } else {
      for (const ref of refs) {
        const r = resolveEntityRef(contracts, ref);
        if (!r.ok) problems.push(`${at}：落点「${ref}」解析不到契约实体——${r.reason}`);
      }
    }

    // anchor：真实设计章且非自指
    const anchor = String(ob.anchor ?? '').trim();
    if (!anchor) {
      problems.push(`${at}：缺 anchor——指出 plan.md 里承载这条设计的章`);
    } else if (DECISION_HEADING_RE.test(`## ${anchor}`) || /知识决策/.test(anchor)) {
      problems.push(`${at}：anchor 指回了「知识决策」章自己——那是声明不是落点`);
    } else if (!planHeadings.some(h => h.includes(anchor) || anchor.includes(h))) {
      problems.push(`${at}：anchor「${anchor}」在 plan.md 里找不到对应章`);
    }

    // 业务步骤
    const step = String(ob.step ?? '').trim();
    if (!step) {
      problems.push(`${at}：缺 step——这条义务落在哪个业务步骤上`);
    } else if (criteria.size || useCases.exists) {
      const inAcceptance = [...criteria.values()].some(c =>
        String(c.prd_function ?? '') === step || String(c.id ?? '') === step);
      if (!inAcceptance && !useCases.branches.has(step)) {
        problems.push(`${at}：step「${step}」在验收条目的 prd_function 与 use-cases 的 branch 里都定位不到`);
      }
    }

    // 四阶段验证要求：挂在验收条目上（单源）
    const criterion = String(ob.criterion ?? '').trim();
    if (!criterion) {
      if (!entry.reviewAction) {
        problems.push(`${at}：缺 criterion——四阶段的验证要求挂在验收条目上，`
          + '不另建第二份分派表');
      }
    } else if (acceptance) {
      const hit = [...criteria.entries()].find(([, c]) => String(c.id ?? '') === criterion);
      if (!hit) {
        problems.push(`${at}：criterion「${criterion}」在 acceptance.yaml 里找不到`
          + '（须是带 knowledge_rule 的验收条目）');
      } else if (hit[0] !== rule) {
        problems.push(`${at}：criterion「${criterion}」的 knowledge_rule 是 ${hit[0]}，与本条 ${rule} 不一致`);
      }
    }

    if (!String(ob.review_focus ?? '').trim() && !entry.reviewAction) {
      problems.push(`${at}：缺 review_focus——review 阶段照着它核，缺了就只能靠复述规约`);
    }
  }

  // ---- 5. 模式：角色完备、实体存在、coordinator 一致 ----
  const specHasCandidate = specPatternCandidates(ctx.projectRoot, ctx.feature, knowledge);
  for (const p of patterns) {
    const id = String(p.pattern_id ?? '').trim();
    const at = `模式 ${id || '(缺 pattern_id)'}`;
    const def = knowledge.patterns.find(x => x.id === id);
    if (!def) {
      problems.push(`${at}：不在册（在册的：${knowledge.patternIds.join('、') || '无'}）`);
      continue;
    }
    if (p.selected !== true) {
      if (!String(p.rationale ?? '').trim()) {
        problems.push(`${at}：不采用也要写理由——不选不是缺陷，不写理由才是`);
      }
      continue;
    }
    if (!String(p.instance ?? '').trim()) {
      problems.push(`${at}：selected 但缺 instance（本方案里的唯一实例名）`);
    }
    const roles = p.roles && typeof p.roles === 'object' ? p.roles : {};
    const given = Object.keys(roles);
    const missingRoles = def.roles.filter(r => !given.includes(r));
    const unknownRoles = given.filter(r => !def.roles.includes(r) && !def.optionalRoles.includes(r));
    if (missingRoles.length) {
      problems.push(`${at}：缺角色 ${missingRoles.join('、')}`
        + '——冻结了这个模式，方案里就该有承载每个角色的结构');
    }
    if (unknownRoles.length) {
      problems.push(`${at}：出现该模式没有声明的角色 ${unknownRoles.join('、')}`);
    }
    for (const [role, value] of Object.entries(roles)) {
      const name = String(value ?? '').trim();
      if (!name) { problems.push(`${at}：角色「${role}」没有承载实体`); continue; }
      if (!entityExists(contracts, name)) {
        problems.push(`${at}：角色「${role}」= ${name} 在契约里找不到对应实体`);
      }
    }
    if (def.coordinatorRole && useCases.exists) {
      const coordEntity = String(roles[def.coordinatorRole] ?? '').trim();
      if (coordEntity && useCases.coordinators.size
        && ![...useCases.coordinators].some(c => c === coordEntity || c.startsWith(`${coordEntity}.`))) {
        problems.push(`${at}：use-cases 的 coordinator（${[...useCases.coordinators].join('、')}）`
          + `与模式编排入口角色「${def.coordinatorRole}」= ${coordEntity} 对不上`);
      }
    }
    if (specHasCandidate === false) {
      problems.push(`${at}：spec 的候选登记里全部单元都写「无候选」，这里却冻结了采用`
        + '——选型依据不是从需求来的；真要用就回 spec 补候选登记');
    }
  }

  if (problems.length) return blocker(problems);
  return { ok: true };
}

/** spec 候选登记里有没有非「无候选」的行；读不到 spec 时返回 null（不判）。 */
function specPatternCandidates(projectRoot, feature, knowledge) {
  const p = path.join(featureRoot(projectRoot, feature), 'spec', 'spec.md');
  const text = readTextOrNull(p);
  if (text === null) return null;
  const rows = lines(text);
  const start = rows.findIndex(l => /^#{2,4}\s+.*设计模式候选/.test(l.trim()));
  if (start < 0) return null;
  const level = (rows[start].trim().match(/^(#{2,4})/) ?? ['', '##'])[1].length;
  for (let i = start + 1; i < rows.length; i++) {
    const h = rows[i].trim().match(/^(#{2,4})\s+/);
    if (h && h[1].length <= level) break;
    const s = rows[i].trim();
    if (!s.startsWith('|')) continue;
    if (knowledge.patternIds.some(id => s.includes(id))) return true;
  }
  return false;
}

/** 实体名是否出现在契约的任一集合里（角色投影用，比引用语法宽松）。 */
function entityExists(contracts, name) {
  const buckets = ['data_models', 'interfaces', 'components', 'files', 'navigation', 'resource_keys'];
  for (const k of buckets) {
    const list = Array.isArray(contracts?.[k]) ? contracts[k] : [];
    for (const it of list) {
      const n = typeof it === 'string'
        ? it
        : String(it?.name ?? it?.class ?? it?.key ?? it?.path ?? it?.file ?? '');
      if (!n) continue;
      if (n === name || n.replace(/\\/g, '/').endsWith(`/${name}`)) return true;
    }
  }
  return false;
}

function rel(projectRoot, abs) {
  return path.relative(projectRoot, abs).replace(/\\/g, '/');
}

function blocker(problems) {
  return {
    ok: false,
    severityOverride: 'BLOCKER',
    message: `plan 阶段知识冻结未通过：${problems.join('；')}。`
      + `处置：按 ${INJECTION_DOC} 的形态补齐冻结结果，再重跑 harness --phase plan。`,
  };
}

export { findHeadings, specExitIds, entityExists };
