/**
 * plan 阶段 post_check（实例扩展）—— 义务是否**挂到了契约实体上**。
 *
 * 基线判的是一本平行账本（契约里那个与实体无关的独立块）的形态：三重锚定、anchor 自指、
 * landing 解析、criterion/step/roles 一致性，25+ 条硬判据。账本本身没人读——framework 的
 * coding SKILL 枚举 contracts 的 7 个集合作为本阶段输入，不含它；实跑里唯一完整落地的那条
 * 规约，靠的是它挂在了一个编码者本来就要读的契约字段上。
 *
 * 所以本阶段只判两件事：
 *   ① **集合一致**——spec §10 判命中的条目，在契约里都有实体扛着；反过来也不多出来；
 *   ② **挂对地方、写的是本需求的设计**——must 只能挂五类实体，text 不能是规约原文的复制。
 *
 * 「义务是不是真的被应用了」是语义判断，归 verifier（overlay 的义务实质判据）。
 * 机械层越权下语义结论，就会变成「写了字就算做了」。
 *
 * 契约：stdin JSON ctx → stdout JSON result。
 */
import * as path from 'node:path';
import { STATUS } from '../shared/evidence.mjs';
import { guard, gate } from '../shared/gate.mjs';
import { activeKnowledge, entryById, paraphraseSources } from '../shared/knowledge.mjs';
import { obligationsFromContracts, misplacedMust, patternRolesFromContracts, VERIFY_KINDS }
  from '../shared/obligations.mjs';
import { isPureCopy } from '../shared/paraphrase.mjs';
import { featureRoot, lines, readTextOrNull } from '../shared/paths.mjs';
import { adjudicationProblems } from '../shared/verifier-report.mjs';
import { contractsPath, readContracts, resolveEntityRef } from '../shared/contracts.mjs';

const AUTHOR_DOC = 'doc/extensions/hooks/plan/author.md';
const SECTIONS_DOC = 'doc/extensions/skills/story/templates/plan-sections.md';
const FIX = `处置：按 ${SECTIONS_DOC} 的形态把义务挂到契约实体上，再重跑 harness --phase plan。`;

/** 设计章的起始形态——「知识决策」必须排在它们之前。 */
const DESIGN_HEADING_RE = /^##\s*\d*[.、]?\s*(模块架构|目录|文件结构|数据模型|页面组件|状态管理|服务层|接口定义|路由|导航)/;
const DECISION_HEADING_RE = /^##\s*知识决策/;

function findHeadings(text) {
  const rows = lines(text);
  let decision = -1;
  let design = -1;
  for (let i = 0; i < rows.length; i++) {
    const s = rows[i].trim();
    if (decision < 0 && DECISION_HEADING_RE.test(s)) decision = i + 1;
    if (design < 0 && DESIGN_HEADING_RE.test(s)) design = i + 1;
  }
  return { decision, design };
}

/** spec §10「规约约束要求」章里登记的条目编号集——本阶段义务集的比对基准。 */
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

/** 逐行裁决核对：知识派生失败不静默通过——那会让本判据恒真。 */
function adjudicationLanding(ctx, knowledge, targetPaths) {
  try {
    return adjudicationProblems(ctx, knowledge, targetPaths);
  } catch (e) {
    return { status: STATUS.FAIL, problems: [`逐行裁决无从核对：${e.message}`], detail: e.message };
  }
}

export default guard('plan', async (ctx) => {
  const planPath = path.join(featureRoot(ctx.projectRoot, ctx.feature), 'plan', 'plan.md');
  const planText = readTextOrNull(planPath);
  if (planText === null) {
    return gate(ctx, { skipped: [{ what: '知识决策章与义务实体', why: 'plan.md 还没生成' }] });
  }

  let knowledge;
  try {
    knowledge = activeKnowledge(ctx.projectRoot);
  } catch (e) {
    // 派生失败必须出声，不能静默当空集通过——那会让下面每条判据都恒真（G7）
    return gate(ctx, { problems: [`激活知识派生失败：${e.message}`], fix: FIX });
  }

  const problems = [];
  const skipped = [];

  // ---- 1. 知识决策章的位置：位置即语义 ----
  const { decision, design } = findHeadings(planText);
  if (decision < 0) {
    problems.push('plan.md 缺「知识决策（设计输入）」章'
      + '——知识决策要先于它影响的设计，排在后面就只能是事后总结');
  } else if (design > 0 && decision > design) {
    problems.push(`「知识决策（设计输入）」在第 ${decision} 行，晚于第一个设计章（第 ${design} 行）`
      + '——位置就是语义：排在设计之后，它只能是「做完了顺便声明用过哪些知识」');
  }

  // ---- 2. 契约可读 ----
  const { contracts, error, exists } = readContracts(ctx.projectRoot, ctx.feature);
  if (error) return gate(ctx, { problems: [...problems, error], fix: FIX });
  if (!exists) {
    problems.push('缺 contracts.yaml——义务挂在它的实体上，没有它下游零注入');
    return gate(ctx, {
      problems,
      skipped: [{ what: '义务集合一致 / must 挂位 / 探针可执行', why: '契约文件还没建' }],
      fix: FIX,
    });
  }

  // ---- 3. must 挂在允许的实体上 ----
  for (const bad of misplacedMust(contracts)) {
    problems.push(`${bad}——义务要挂在下游真的会读的那个实体上，挂在别处等于又造了一本账本`);
  }

  const obligations = obligationsFromContracts(contracts);
  const specIds = specExitIds(ctx.projectRoot, ctx.feature);

  // ---- 4. 集合一致（双向差集）----
  if (specIds === null) {
    skipped.push({ what: '义务集合一致', why: 'spec.md 里找不到「规约约束要求」章' });
  } else {
    // 处置标「（评审动作）」的条目不产生代码要求，不进契约
    const wanted = new Set([...specIds].filter(id => !entryById(knowledge, id)?.reviewAction));
    const got = new Set(obligations.map(o => o.rule).filter(Boolean));

    if (wanted.size > 0 && got.size === 0) {
      // 派生为空要出声，不能静默当「没有义务」通过（G7）
      problems.push(`spec §10 判了 ${wanted.size} 条命中，契约里却一条 must 都没有`
        + `——义务没有落到实体上，下游零注入。处置：按 ${SECTIONS_DOC} 把每条挂到对应实体`);
    }
    const missing = [...wanted].filter(id => !got.has(id));
    if (missing.length) {
      problems.push(`这些条目在 spec §10 判了命中，契约里没有任何实体扛着：${missing.join('、')}`
        + '——判了命中却没有代码要求，等于知识在设计阶段就丢了');
    }
    const unknown = [...got].filter(id => !wanted.has(id));
    if (unknown.length) {
      problems.push(`契约里的这些 must.rule 不在 spec §10 的命中集内：${unknown.join('、')}`
        + '——两处判定对不上，评审者会看到互相矛盾的结论；要么回 spec 补登记，要么去掉');
    }
  }

  // ---- 5. 每条 must 自身：编号在册、text 不是原文复制、verify 封闭、探针可执行 ----
  for (const ob of obligations) {
    const at = ob.entityPath || '(未知实体)';
    if (!ob.rule) {
      problems.push(`${at} 上有一条 must 没写 rule——义务要认回具体的规约条目`);
      continue;
    }
    const entry = entryById(knowledge, ob.rule);
    if (!entry) {
      problems.push(`${at} 的 must.rule「${ob.rule}」不在激活清单里——编号写错，或那条规约已下架`);
      continue;
    }
    if (!ob.text) {
      problems.push(`${at} 的 ${ob.rule} 缺 text——要写本次要落实成什么，不是只标个编号`);
    } else {
      const { copied, source } = isPureCopy(ob.text, paraphraseSources(knowledge, ob.rule));
      if (copied) {
        problems.push(`${at} 的 ${ob.rule} text 是规约原文的复制或子串（来源「${source}…」）`
          + '——写本需求的设计：它在这个实体上具体要求做什么');
      }
    }
    if (!VERIFY_KINDS.includes(ob.verify)) {
      problems.push(`${at} 的 ${ob.rule} verify「${ob.verify || '(空)'}」不是封闭取值之一`
        + `（${VERIFY_KINDS.join(' / ')}）`);
    } else if (ob.verify === 'probe' && !entry.probe) {
      problems.push(`${at} 的 ${ob.rule} 标了 verify: probe，但该条目的规约表没有探针`
        + '——没有探针表达式，coding 阶段执行不了；改用 ut / device / both / review');
    }
  }

  // ---- 6. 模式采用：角色名须是该模式声明过的 ----
  for (const pr of patternRolesFromContracts(contracts)) {
    const pat = knowledge.patterns.find(p => p.id === pr.pattern);
    if (!pat) {
      problems.push(`files「${pr.path}」标的 pattern「${pr.pattern}」不在册`
        + `（在册的：${knowledge.patternIds.join('、') || '无'}）`);
      continue;
    }
    if (!pr.role) {
      problems.push(`files「${pr.path}」标了 pattern 却没写 role——角色是模式声明过的那几个之一`);
      continue;
    }
    const roles = [...(pat.roles ?? []), ...(pat.optionalRoles ?? [])];
    if (roles.length && !roles.includes(pr.role)) {
      problems.push(`files「${pr.path}」的 role「${pr.role}」不是 ${pr.pattern} 声明的角色`
        + `（该模式的角色：${roles.join('、')}）`);
    }
  }

  // ---- 7. 逐行裁决落盘 ----
  const adj = adjudicationLanding(ctx, knowledge, [planPath, contractsPath(ctx.projectRoot, ctx.feature)]);
  problems.push(...adj.problems);

  return gate(ctx, {
    problems,
    skipped,
    fix: FIX,
    checks: [
      { id: 'knowledge_obligation_on_entity', status: problems.length ? STATUS.FAIL : STATUS.PASS,
        detail: `义务 ${obligations.length} 条；问题 ${problems.length} 条` },
      { id: 'knowledge_adjudication_persisted', status: adj.status, detail: adj.detail },
    ],
    inputs: [planPath, contractsPath(ctx.projectRoot, ctx.feature)],
  });
});
