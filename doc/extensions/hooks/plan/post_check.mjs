/**
 * plan 阶段 post_check（实例扩展）—— 义务是否**挂到了契约实体上**。
 *
 * 基线判的是一本平行账本（契约里那个与实体无关的独立块）的形态：三重锚定、anchor 自指、
 * landing 解析、criterion/step/roles 一致性，25+ 条硬判据。账本本身没人读——framework 的
 * coding SKILL 枚举 contracts 的 7 个集合作为本阶段输入，不含它；能完整落地的规约，
 * 靠的都是挂在编码者本来就要读的契约字段上。
 *
 * 所以本阶段只判两件事：
 *   ① **集合一致**——spec 判命中的条目，在契约里都有实体扛着；反过来也不多出来；
 *   ② **挂对地方**——must 只能挂五类实体，编号在册，verify 取值封闭，探针可执行。
 *
 * **真源是 `spec/knowledge-use.yaml`**，不是 spec.md 里那两张表：那两张表是它的投影，
 * 解析投影等于让判据依赖渲染格式。
 *
 * 「义务是不是真的被应用了」「text 写的是不是本需求的设计」都是语义判断，
 * 归 verifier（overlay 的义务实质判据）。机械层越权下语义结论，
 * 就会变成「写了字就算做了」。
 *
 * 契约：stdin JSON ctx → stdout JSON result。
 */
import * as path from 'node:path';
import { STATUS } from '../shared/evidence.mjs';
import { guard, gate } from '../shared/gate.mjs';
import { activeKnowledge, entryById } from '../shared/knowledge.mjs';
import { obligationsFromContracts, misplacedMust, patternRolesFromContracts, VERIFY_KINDS }
  from '../shared/obligations.mjs';
import { readUse, UseError } from '../shared/knowledge-use.mjs';
import { featureRoot, lines, readTextOrNull } from '../shared/paths.mjs';
import { contractsPath, readContracts, resolveEntityRef } from '../shared/contracts.mjs';

const AUTHOR_DOC = 'doc/extensions/hooks/plan/author.md';
const SECTIONS_DOC = 'doc/extensions/skills/story/templates/plan-sections.md';
const FIX = `处置：按 ${SECTIONS_DOC} 的形态把义务挂到契约实体上，再重跑 harness --phase plan。`;

/**
 * 设计章的起始形态——「知识决策」必须排在它们之前。
 *
 * **这些词不是数出来的**：它们是 framework 规定的 plan 法定章名（`skills/feature/plan/SKILL.md`
 * 的九章：1 Scope 声明与继承 / 2 模块架构图 / 3 目录文件结构规划 / 4 数据模型定义 /
 * 5 页面组件树 / 6 状态管理方案 / 7 服务层接口定义 / 8 路由导航设计 / 9 spec 功能映射表）
 * 里第 2–8 章那几个，也就是「设计」那一段。第 1 章 Scope 声明是框架要求的前置，
 * 不算设计章——所以判的是「知识决策在设计章之前」，不是「知识决策排第一」。
 *
 * **真正的风险是它与 framework 的 `check-plan.ts > required_chapters` 是两份抄本**：
 * 那边改了章名，这边不会跟着改，本判据就会静默失灵而没有任何信号。
 * `test_plan_pattern_crosscheck.py` 锁两边一致——framework 改章名时测试先红。
 */
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

/**
 * spec 判命中、且产生代码要求的条目编号集 —— 本阶段义务集的比对基准。
 *
 * 读的是 `spec/knowledge-use.yaml` 这份**真源**，不是 spec.md 里那张投影表：
 * 解析投影，判据就依赖渲染格式，改一次表头就静默失灵。
 *
 * @returns {Set<string>|null} 读不到那份判断时 null——调用方据此记「这条没执行」
 */
function specHitIds(projectRoot, feature, knowledge) {
  let use;
  try {
    use = readUse(projectRoot, feature);
  } catch (e) {
    if (e instanceof UseError) return null;
    throw e;
  }
  const ids = new Set();
  for (const row of use.constraints) {
    if (row?.applicable !== true) continue;
    const id = String(row.id ?? '').trim();
    // 处置标「（评审动作）」的条目是纯流程动作，不产生代码要求，不进契约
    if (id && !entryById(knowledge, id)?.reviewAction) ids.add(id);
  }
  return ids;
}

/**
 * 从一张 markdown 表里逐行取**数据行**的格子。
 *
 * 表头行按位置认：紧跟着 `|---|` 分隔行的那一行就是表头。按内容认（比对列名）
 * 会在列名改一个字时静默把表头当数据读进来，那种错没人看得见。
 */
function tableRows(rows, from, level) {
  const pipes = [];
  for (let i = from; i < rows.length; i++) {
    const h = rows[i].trim().match(/^(#{2,4})\s+/);
    if (h && h[1].length <= level) break;
    const s = rows[i].trim();
    if (s.startsWith('|')) pipes.push(s);
  }
  const cellsOf = (s) =>
    s.replace(/^\||\|$/g, '').split('|').map(c => c.replace(/[`*]/g, '').trim());
  const isSeparator = (s) => cellsOf(s).every(c => /^[-: ]*$/.test(c));
  const out = [];
  for (let i = 0; i < pipes.length; i++) {
    if (isSeparator(pipes[i])) continue;
    if (i + 1 < pipes.length && isSeparator(pipes[i + 1])) continue;   // 表头
    out.push(cellsOf(pipes[i]));
  }
  return out;
}

/** 某一章的起始行号与它的标题级别。 */
function chapterAt(rows, re) {
  const start = rows.findIndex(l => re.test(l.trim()));
  if (start < 0) return null;
  return { start, level: (rows[start].trim().match(/^(#{2,4})/) ?? ['', '##'])[1].length };
}

/**
 * spec 登记了候选的适用单元：`{ 适用单元 → 候选 }`。
 *
 * 同样读真源。「无候选」是正常结论，不进这个集合——本判据核的是
 * **登记了候选却在 plan 消失或被空手否掉**。
 */
function specPatternHits(projectRoot, feature) {
  let use;
  try {
    use = readUse(projectRoot, feature);
  } catch (e) {
    if (e instanceof UseError) return null;
    throw e;
  }
  const hits = new Map();
  for (const row of use.patterns) {
    const unit = String(row?.unit ?? '').trim();
    const candidate = String(row?.candidate ?? '').trim();
    if (!unit || !candidate || candidate.includes('无候选')) continue;
    hits.set(unit, candidate);
  }
  return hits;
}

/**
 * plan 的设计模式选型表：`{ 适用单元 → { 选不选, 理由 } }`。
 *
 * 选型表就在「知识决策（设计输入）」章里——它是 plan 期的可见面，
 * 有 plan 门禁看、有 verifier 问，模式否决就该落在这里。
 */
function planPatternChoices(planText) {
  const rows = lines(planText);
  const at = chapterAt(rows, /^#{2,4}\s+设计模式选型/);
  if (!at) return null;
  const out = new Map();
  for (const cells of tableRows(rows, at.start + 1, at.level)) {
    const [unit, , choice, , reason] = cells;
    if (!unit || /^\{.*\}$/.test(unit)) continue;
    out.set(unit, { choice: choice ?? '', reason: reason ?? '' });
  }
  return out;
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
  const wanted = specHitIds(ctx.projectRoot, ctx.feature, knowledge);

  // ---- 4. 集合一致（双向差集）----
  if (wanted === null) {
    skipped.push({ what: '义务集合一致', why: '读不到 spec/knowledge-use.yaml' });
  } else {
    const got = new Set(obligations.map(o => o.rule).filter(Boolean));

    if (wanted.size > 0 && got.size === 0) {
      // 派生为空要出声，不能静默当「没有义务」通过（G7）
      problems.push(`spec 判了 ${wanted.size} 条命中，契约里却一条 must 都没有`
        + `——义务没有落到实体上，下游零注入。处置：按 ${SECTIONS_DOC} 把每条挂到对应实体`);
    }
    const missing = [...wanted].filter(id => !got.has(id));
    if (missing.length) {
      problems.push(`这些条目在 spec 判了命中，契约里没有任何实体扛着：${missing.join('、')}`
        + '——判了命中却没有代码要求，等于知识在设计阶段就丢了');
    }
    const unknown = [...got].filter(id => !wanted.has(id));
    if (unknown.length) {
      problems.push(`契约里的这些 must.rule 不在 spec 的命中集内：${unknown.join('、')}`
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
      // text 写得对不对是语义判断（它是本需求的设计，还是规约原文换个说法）——
      // 归 verifier。机械层只问「写没写」。
      problems.push(`${at} 的 ${ob.rule} 缺 text——要写本次要落实成什么，不是只标个编号`);
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

  // ---- 6b. spec 判命中的候选，在 plan 有行、不选时有理由 ----
  //
  // 典型失效：spec 正确命中了候选（业务信号真实），plan 拿当前的临时承载形态当理由
  // 把它否了——**拿临时形态当信号输入**。否决在闭环内完成，没有任何人过目，
  // 知识文件本身一个字没错。
  //
  // 这里只判形式两件事：命中的候选有没有行、不选时理由列空不空。
  // 「理由引的是业务信号还是承载形态」是语义，归 verifier 逐问——
  // 用措辞正则去拦，拦出来的是换一种说法的同一件事。
  {
    const hits = specPatternHits(ctx.projectRoot, ctx.feature);
    const choices = planPatternChoices(planText);
    if (hits === null) {
      skipped.push({ what: '设计模式候选的交叉核对', why: '读不到 spec/knowledge-use.yaml' });
    } else if (choices === null) {
      if (hits.size) {
        problems.push(`spec 登记了 ${hits.size} 条设计模式候选，plan.md 却没有「设计模式选型」表`
          + '——命中的候选要逐条给结论，选或不选都算');
      }
    } else {
      for (const [unit, candidate] of hits) {
        const row = choices.get(unit);
        if (!row) {
          problems.push(`spec 给「${unit}」登记了候选 ${candidate}，plan 的设计模式选型表里没有这一行`
            + '——命中的候选逐条给结论，漏一行它就在闭环里悄悄消失了');
          continue;
        }
        if (row.choice.includes('不选') && !row.reason) {
          problems.push(`「${unit}」的候选 ${candidate} 被判不选，理由列是空的`
            + '——不选是表态有后果的决策，理由要写成业务信号的反证'
            + '（那个业务过程为什么不满足该模式的信号），不能以当前是模拟或演示承载为由');
        }
      }
    }
  }

  return gate(ctx, {
    problems,
    skipped,
    fix: FIX,
    checks: [
      { id: 'knowledge_obligation_on_entity', status: problems.length ? STATUS.FAIL : STATUS.PASS,
        detail: `义务 ${obligations.length} 条；问题 ${problems.length} 条` },
    ],
    inputs: [planPath, contractsPath(ctx.projectRoot, ctx.feature)],
  });
});
