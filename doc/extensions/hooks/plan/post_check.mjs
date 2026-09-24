/**
 * plan 阶段 post_check（实例扩展）—— 义务是否**挂到了契约实体上**。
 *
 * 基线判的是一本平行账本（契约里那个与实体无关的独立块）的形态：三重锚定、anchor 自指、
 * landing 解析、criterion/step/roles 一致性，25+ 条硬判据。账本本身没人读——framework 的
 * coding SKILL 枚举 contracts 的 7 个集合作为本阶段输入，不含它；能完整落地的规约，
 * 靠的都是挂在编码者本来就要读的契约字段上。
 *
 * 所以本阶段判三件事：
 *   ① **集合一致**——spec 判命中的条目，在契约里都有实体扛着；反过来也不多出来；
 *   ② **挂对地方**——must 只能挂五类实体，编号在册，verify 取值封闭，探针可执行；
 *   ③ **埋点逐统计点落实**——spec 埋点的每个统计点在 plan 有行、责任方法在契约里、落在该点的统计义务挂在它上面。
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
import { obligationsFromContracts, misplacedMust, patternRolesFromContracts, verifyProblem }
  from '../shared/obligations.mjs';
import { readUse, UseError } from '../shared/knowledge-use/document.mjs';
import { featureRoot, lines, readTextOrNull } from '../shared/paths.mjs';
import { contractsPath, readAcceptance, readContracts, resourceEntries } from '../shared/contracts.mjs';
import { chapterNumberProblems, chapterRefProblems, chapterTemplates } from '../shared/chapters.mjs';
import { parseYaml } from '../shared/yaml.mjs';
import { planStatRows, pointKey, specStatPoints, statDesignState } from '../shared/stat-points.mjs';
import { cellByHeader, tableCells } from '../../skills/story/scripts/core/story/document.mjs';
import { isStoryFeature } from '../../skills/story/scripts/core/flow/check.mjs';

const SECTIONS_DOC = 'doc/extensions/skills/story/templates/plan-sections.md';
const FIX = `处置：按 ${SECTIONS_DOC} 的形态把义务挂到契约实体上，再重跑 harness --phase plan。`;

/**
 * 设计章的起始形态——「知识决策」必须排在它们之前。
 *
 * **这些词不是数出来的**：它们是 framework 规定的 plan 法定章名（profile 的 plan 模板：
 * 不编号的 Scope 声明与继承，之后 1 模块架构图 … 8 spec 功能映射表）里「设计」那一段。
 * Scope 声明是框架要求的前置，不算设计章——所以判的是「知识决策在设计章之前」，不是「知识决策排第一」。
 * 章号以模板为准，由下面的章号核对判。
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
    // 本轮豁免的命中不落实，不进契约；它的去向是评审人表态
    if (row?.applicable !== true || row.waived) continue;
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
    if (s.startsWith('|')) pipes.push(tableCells(s));
  }
  const isSeparator = (cells) => cells.every(c => /^[-: ]*$/.test(c));
  const headers = pipes.length > 1 && isSeparator(pipes[1]) ? pipes[0] : null;
  return { headers, rows: pipes.filter((c, i) => !isSeparator(c) && !(headers && i === 0)) };
}

/** 某一章的起始行号与它的标题级别。 */
function chapterAt(rows, re) {
  const start = rows.findIndex(l => re.test(l.trim()));
  if (start < 0) return null;
  return { start, level: (rows[start].trim().match(/^(#{2,4})/) ?? ['', '##'])[1].length };
}

/**
 * spec 登记了候选的适用单元：`unit -> Map(candidate -> row)`。
 *
 * 同样读真源。同一单元允许登记多个候选，各自要给结论；同一 unit+candidate
 * 重复登记报错，不能后写覆盖前写。「无候选」是正常结论，不进这个集合——
 * 本判据核的是**登记了候选却在 plan 消失或被空手否掉**。
 *
 * @returns {{hits: Map<string, Map<string, object>>, problems: string[]} | null}
 *   读不到那份判断时 null——调用方据此记「这条没执行」
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
  const problems = [];
  for (const row of use.patterns) {
    const unit = String(row?.unit ?? '').trim();
    const candidate = String(row?.candidate ?? '').trim();
    if (!unit || !candidate || candidate.includes('无候选')) continue;
    let byPattern = hits.get(unit);
    if (!byPattern) { byPattern = new Map(); hits.set(unit, byPattern); }
    if (byPattern.has(candidate)) {
      problems.push(`spec 的 patterns 把「${unit}」的候选 ${candidate} 登记了两次——`
        + '删掉重复行；同一单元有多个候选时各写一行，选型时逐个给结论');
      continue;
    }
    byPattern.set(candidate, row);
  }
  return { hits, problems };
}

/**
 * plan 的设计模式选型表：`unit -> Map(candidate -> { 选不选, 理由 })`。
 *
 * 选型表就在「知识决策（设计输入）」章里——它是 plan 期的可见面，
 * 有 plan 门禁看、有 verifier 问，模式否决就该落在这里。
 * 候选列（第二列）是身份的另一半：同一单元有多个候选时，靠它才分得清谁被选谁被否。
 * 「无候选」是说明不是模式身份，两侧同义——说明行不进这个集合，也不进 spec 侧的候选集。
 *
 * @returns {{choices: Map<string, Map<string, object>>, problems: string[]} | null}
 *   表不存在时 null；同一 unit+pattern 重复两行报错，不后写覆盖前写。
 */
function planPatternChoices(planText) {
  const rows = lines(planText);
  const at = chapterAt(rows, /^#{2,4}\s+设计模式选型/);
  if (!at) return null;
  const out = new Map();
  const problems = [];
  const { headers, rows: body } = tableRows(rows, at.start + 1, at.level);
  for (const cells of body) {
    const [unit, candidate, choice, reason] = ['单元', '候选', '不选', '理由']
      .map(key => cellByHeader(cells, headers, key));
    if (!unit || /^\{.*\}$/.test(unit)) continue;
    const pattern = String(candidate ?? '').trim();
    if (!pattern || pattern.includes('无候选')) continue;
    let byPattern = out.get(unit);
    if (!byPattern) { byPattern = new Map(); out.set(unit, byPattern); }
    if (byPattern.has(pattern)) {
      problems.push(`plan 的设计模式选型表把「${unit}」的候选 ${pattern} 写了两行——`
        + '删掉重复行；同一单元有多个候选时各写一行，逐个给结论');
      continue;
    }
    byPattern.set(pattern, { choice: choice ?? '', reason: reason ?? '' });
  }
  return { choices: out, problems };
}

/**
 * `use-cases.yaml` 里 `linked_acceptance` 引的编号都要在 `acceptance.yaml` 里存在。
 * 验收编号取 acceptance 顶层各列表条目的 `id`，不认前缀；文件缺席或读不了与悬空引用分开报。
 */
function acceptanceRefProblems(projectRoot, feature, group) {
  const raw = readTextOrNull(path.join(featureRoot(projectRoot, feature), 'use-cases.yaml'));
  if (raw === null) return [];
  const acc = readAcceptance(projectRoot, feature);
  if (!acc.acceptance) {
    group.skipped.push({ what: '用例的验收引用', why: acc.error ?? '没有 acceptance.yaml' });
    return [];
  }
  let cases;
  try { cases = parseYaml(raw); } catch (e) { return [`use-cases.yaml 解析失败：${e.message}`]; }
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
    + 'acceptance.yaml 里没有这个编号——下游按编号取验收，引用要用 acceptance 里实际的 id');
}

/** 契约里声明的方法：`<接口>.<方法>`。 */
function declaredMethods(contracts) {
  const list = (x) => (Array.isArray(x) ? x : []);
  return list(contracts?.interfaces).flatMap(i => list(i?.methods).map(m => `${i?.name}.${m?.name}`));
}

/**
 * spec 判命中、且落点（`contract`）写的是某个统计点的规约：`统计点 → 规约编号集`。
 * 落点引的是 §9 表第一列登记的名字，统计点名正是其中之一；读不到那份判断返回空表。
 */
function statRulesByPoint(projectRoot, feature, points) {
  const out = new Map();
  const keys = new Set(points.map(pointKey));
  let use;
  try {
    use = readUse(projectRoot, feature);
  } catch (e) {
    if (e instanceof UseError) return out;
    throw e;
  }
  for (const row of use.constraints) {
    const at = pointKey(row?.contract ?? '');
    if (row?.applicable !== true || row.waived || !keys.has(at)) continue;
    if (!out.has(at)) out.set(at, new Set());
    out.get(at).add(String(row.id ?? '').trim());
  }
  return out;
}

export default guard('plan', async (ctx) => {
  const planPath = path.join(featureRoot(ctx.projectRoot, ctx.feature), 'plan', 'plan.md');
  const planText = readTextOrNull(planPath);
  if (planText === null) {
    return gate(ctx, { skipped: [{ what: '知识决策章与义务实体', why: 'plan.md 还没生成' }] });
  }

  // 按数据前置分组：章节只要 plan 可读；契约形状要契约可解析；义务与集合一致要契约与激活知识；
  // 集合一致与候选交叉核对还要 knowledge-use 可读。前置缺的组记 skipped，不让别的组因它被屏蔽。
  const chapter = { name: '知识决策章', problems: [], skipped: [] };
  const contract = { name: '契约可读与 must 挂位', problems: [], skipped: [] };
  const obligation = { name: '每条 must 自身', problems: [], skipped: [] };
  const consistency = { name: '命中集合与义务集合一致', problems: [], skipped: [] };
  const pattern = { name: '设计模式采用与候选交叉核对', problems: [], skipped: [] };
  const reference = { name: '章号、设计章引用与验收引用', problems: [], skipped: [] };
  const groups = [chapter, contract, obligation, consistency, pattern, reference];

  // ---- 0. 章号以模板为准；「承载设计章」的号与章名对得上；用例引用的验收编号存在 ----
  const chapters = chapterTemplates(ctx.projectRoot, 'plan', 'plan_template');
  reference.problems.push(...chapters.problems);
  reference.skipped.push(...chapters.skipped);
  if (chapters.templates) reference.problems.push(...chapterNumberProblems(planText, chapters.templates));
  reference.problems.push(...chapterRefProblems(planText, '承载设计章'));
  reference.problems.push(...acceptanceRefProblems(ctx.projectRoot, ctx.feature, reference));

  // ---- 1. 知识决策章的位置：位置即语义（只依赖 plan 可读）----
  const { decision, design } = findHeadings(planText);
  if (decision < 0) {
    chapter.problems.push('plan.md 缺「知识决策（设计输入）」章'
      + '——知识决策要先于它影响的设计，排在后面就只能是事后总结');
  } else if (design > 0 && decision > design) {
    chapter.problems.push(`「知识决策（设计输入）」在第 ${decision} 行，晚于第一个设计章（第 ${design} 行）`
      + '——位置就是语义：排在设计之后，它只能是「做完了顺便声明用过哪些知识」');
  }

  // ---- 2. 契约可读、must 挂位、resource_keys 形状 ----
  const read = readContracts(ctx.projectRoot, ctx.feature);
  const contracts = read.contracts;
  let noContract = null;
  if (read.error) {
    contract.problems.push(read.error);
    noContract = '契约解析失败';
  } else if (!read.exists) {
    contract.problems.push('缺 contracts.yaml——义务挂在它的实体上，没有它下游零注入');
    noContract = '契约文件还没建';
  } else {
    for (const bad of misplacedMust(contracts)) {
      contract.problems.push(`${bad}——义务要挂在下游真的会读的那个实体上，挂在别处等于又造了一本账本`);
    }
    contract.problems.push(...resourceEntries(contracts).problems);
  }

  // ---- 激活知识：义务、集合一致、模式三组的共同前置 ----
  let knowledge = null;
  try {
    knowledge = activeKnowledge(ctx.projectRoot);
  } catch (e) {
    // 派生失败必须出声，不能静默当空集通过——那会让下面每条判据都恒真（G7）
    obligation.problems.push(`激活知识派生失败：${e.message}`);
  }
  const noKnowledge = knowledge ? null : '激活知识派生失败';

  const obligations = contracts ? obligationsFromContracts(contracts) : [];

  // ---- 3. 每条 must 自身：编号在册、text 写了没有、verify 与规约声明的执行体相符 ----
  if (noContract || noKnowledge) {
    obligation.skipped.push({ what: '每条 must 的编号、text、verify', why: noContract ?? noKnowledge });
  } else {
    for (const ob of obligations) {
      const at = ob.entityPath || '(未知实体)';
      if (!ob.rule) {
        obligation.problems.push(`${at} 上有一条 must 没写 rule——义务要认回具体的规约条目`);
        continue;
      }
      const entry = entryById(knowledge, ob.rule);
      if (!entry) {
        obligation.problems.push(`${at} 的 must.rule「${ob.rule}」不在激活清单里——编号写错，或那条规约已下架`);
        continue;
      }
      if (!ob.text) {
        // text 写得对不对是语义判断（它是本需求的设计，还是规约原文换个说法）——
        // 归 verifier。机械层只问「写没写」。
        obligation.problems.push(`${at} 的 ${ob.rule} 缺 text——要写本次要落实成什么，不是只标个编号`);
      }
      const verify = verifyProblem(entry, ob.verify);
      if (verify) obligation.problems.push(`${at} 的 ${ob.rule} ${verify}`);
    }
    // 方法体探针要有方法落点，否则 coding 无处可跑：记为未执行，不阻断 plan
    for (const rule of new Set(obligations.map(o => o.rule))) {
      if (entryById(knowledge, rule)?.probe?.kind !== 'present_in_method') continue;
      if (!obligations.some(o => o.rule === rule && o.entityKind === 'interfaces')) {
        obligation.skipped.push({ what: `${rule} 的探针`, why: '探针无落点：它查方法体，而这条规约没有挂在 interfaces[].methods[] 上的 must' });
      }
    }
  }

  // ---- 4. 集合一致（双向差集）----
  const wanted = knowledge ? specHitIds(ctx.projectRoot, ctx.feature, knowledge) : null;
  if (noContract || noKnowledge) {
    consistency.skipped.push({ what: '义务集合一致', why: noContract ?? noKnowledge });
  } else if (wanted === null) {
    consistency.skipped.push({ what: '义务集合一致', why: '读不到 spec/knowledge-use.yaml' });
  } else {
    const got = new Set(obligations.map(o => o.rule).filter(Boolean));
    if (wanted.size > 0 && got.size === 0) {
      // 派生为空要出声，不能静默当「没有义务」通过（G7）
      consistency.problems.push(`spec 判了 ${wanted.size} 条命中，契约里却一条 must 都没有`
        + `——义务没有落到实体上，下游零注入。处置：按 ${SECTIONS_DOC} 把每条挂到对应实体`);
    }
    const missing = [...wanted].filter(id => !got.has(id));
    if (missing.length) {
      consistency.problems.push(`这些条目在 spec 判了命中，契约里没有任何实体扛着：${missing.join('、')}`
        + '——判了命中却没有代码要求，等于知识在设计阶段就丢了');
    }
    const unknown = [...got].filter(id => !wanted.has(id));
    if (unknown.length) {
      consistency.problems.push(`契约里的这些 must.rule 不在 spec 的命中集内：${unknown.join('、')}`
        + '——两处判定对不上，评审者会看到互相矛盾的结论；要么回 spec 补登记，要么去掉');
    }
  }

  // ---- 5. 模式采用：角色名须是该模式声明过的 ----
  if (noContract || noKnowledge) {
    pattern.skipped.push({ what: '模式角色', why: noContract ?? noKnowledge });
  } else {
    for (const pr of patternRolesFromContracts(contracts)) {
      const pat = knowledge.patterns.find(p => p.id === pr.pattern);
      if (!pat) {
        pattern.problems.push(`files「${pr.path}」标的 pattern「${pr.pattern}」不在册`
          + `（在册的：${knowledge.patternIds.join('、') || '无'}）`);
        continue;
      }
      if (!pr.role) {
        pattern.problems.push(`files「${pr.path}」标了 pattern 却没写 role——角色是模式声明过的那几个之一`);
        continue;
      }
      const roles = [...(pat.roles ?? []), ...(pat.optionalRoles ?? [])];
      if (roles.length && !roles.includes(pr.role)) {
        pattern.problems.push(`files「${pr.path}」的 role「${pr.role}」不是 ${pr.pattern} 声明的角色`
          + `（该模式的角色：${roles.join('、')}）`);
      }
    }
  }

  // ---- 5b. spec 判命中的候选，在 plan 有行、不选时有理由 ----
  //
  // 典型失效：spec 正确命中了候选（业务信号真实），plan 拿当前的临时承载形态当理由
  // 把它否了——**拿临时形态当信号输入**。否决在闭环内完成，没有任何人过目，
  // 知识文件本身一个字没错。
  //
  // 这里只判形式几件事：命中的候选按 (单元, 候选) 逐对有没有行、不选时理由列空不空、
  // plan 有没有把 spec 没提出的候选加进来。同一单元多个候选各配各的行——
  // 「理由引的是业务信号还是承载形态」是语义，归 verifier 逐问——
  // 用措辞正则去拦，拦出来的是换一种说法的同一件事。
  // 这一段只要 plan 与 knowledge-use 可读，不依赖契约。
  {
    const specHits = specPatternHits(ctx.projectRoot, ctx.feature);
    const planChoices = planPatternChoices(planText);
    if (specHits === null) {
      pattern.skipped.push({ what: '设计模式候选的交叉核对', why: '读不到 spec/knowledge-use.yaml' });
    } else {
      pattern.problems.push(...specHits.problems);
      if (planChoices === null) {
        const total = [...specHits.hits.values()].reduce((n, m) => n + m.size, 0);
        if (total) {
          pattern.problems.push(`spec 登记了 ${total} 条设计模式候选，plan.md 却没有「设计模式选型」表`
            + '——命中的候选要逐条给结论，选或不选都算');
        }
      } else {
        pattern.problems.push(...planChoices.problems);
        const choices = planChoices.choices;
        for (const [unit, byPattern] of specHits.hits) {
          for (const [candidate] of byPattern) {
            const choice = choices.get(unit)?.get(candidate);
            if (!choice) {
              pattern.problems.push(`spec 给「${unit}」登记了候选 ${candidate}，plan 的设计模式选型表里没有这一行`
                + '——命中的候选逐条给结论，漏一行它就在闭环里悄悄消失了');
              continue;
            }
            if (choice.choice.includes('不选') && !choice.reason) {
              pattern.problems.push(`「${unit}」的候选 ${candidate} 被判不选，理由列是空的`
                + '——不选是表态有后果的决策，理由要写成业务信号的反证'
                + '（那个业务过程为什么不满足该模式的信号），不能以当前是模拟或演示承载为由');
            }
          }
        }
        for (const [unit, byPattern] of choices) {
          for (const candidate of byPattern.keys()) {
            if (!specHits.hits.get(unit)?.has(candidate)) {
              pattern.problems.push(`plan 的设计模式选型表给「${unit}」写了候选 ${candidate}，spec 没有提出它`
                + '——模式选型只能从 spec 登记的候选里选，真需要时回 spec 补候选登记');
            }
          }
        }
      }
    }
  }

  // ---- 6. 埋点：spec 的每个统计点在 plan 有行，责任方法在契约里，落在该点上的统计义务挂在它上面 ----
  // 只核对应、引用与挂点；结果、来源、去重与验证写没写到位是语义，归 verifier。
  const statGroup = { name: '埋点逐统计点落实', problems: [], skipped: [] };
  groups.push(statGroup);
  {
    const spec = readTextOrNull(path.join(featureRoot(ctx.projectRoot, ctx.feature), 'spec', 'spec.md'));
    const points = spec === null ? null : specStatPoints(spec);
    const state = statDesignState(points);
    const wantPoints = state === 'ready' ? points.groups.flatMap(g => g.points) : [];
    const plan = planStatRows(planText);
    const story = isStoryFeature(featureRoot(ctx.projectRoot, ctx.feature));
    if (state === 'missing' && story) {
      statGroup.problems.push('spec 没有埋点一节，plan 的埋点无从承接——先回 spec 补上统计设计；确实不涉及也写一行「不涉及：<依据>」');
    } else if (state === 'empty') {
      statGroup.problems.push('spec 的埋点一节没有指标点位表——先回 spec 在每个指标 H4 下补上带「统计点」列的表，plan 再逐点承接');
    } else if (!wantPoints.length) {
      statGroup.skipped.push({ what: '埋点逐统计点落实', why: state === 'na' ? 'spec 的埋点一节写了不涉及' : '本需求没走 /story，spec 未提供统计设计' });
    } else if (!plan) {
      statGroup.problems.push(`spec 的埋点列了 ${wantPoints.length} 个统计点，plan.md 没有「埋点」小节`
        + '——在服务层接口定义章下每个统计点列出适用结果及责任方法，允许多行');
    } else {
      const have = new Set(plan.rows.map(r => pointKey(r.point)));
      const missing = wantPoints.filter(p => !have.has(pointKey(p)));
      if (missing.length) {
        statGroup.problems.push(`spec 埋点的这些统计点在 plan 埋点小节没有对应行：${missing.join('、')}——每个统计点列出适用结果及责任方法，允许多行`);
      }
      if (noContract) {
        statGroup.skipped.push({ what: '责任方法与统计义务', why: noContract });
      } else {
        const declared = new Set(declaredMethods(contracts));
        const rulesAt = statRulesByPoint(ctx.projectRoot, ctx.feature, wantPoints);
        const seen = new Map();
        for (const r of plan.rows) {
          const k = (seen.get(pointKey(r.point)) ?? 0) + 1;
          seen.set(pointKey(r.point), k);
          const at = `「${r.point}」第 ${k} 条结果行`;
          if (!r.methods.length) {
            statGroup.problems.push(`${at}没写责任方法——写成「接口.方法」，指向 contracts.yaml 里决定这个结果的那个方法`);
            continue;
          }
          const unknown = r.methods.filter(m => !declared.has(m));
          if (unknown.length) {
            statGroup.problems.push(`${at}的责任方法 ${unknown.join('、')} 在 contracts.yaml 的 interfaces[].methods[] 里找不到`);
          }
          for (const rule of rulesAt.get(pointKey(r.point)) ?? []) {
            if (!r.methods.some(m => obligations.some(o => o.rule === rule && o.entityPath === `interfaces.${m}`))) {
              statGroup.problems.push(`spec 把 ${rule} 落在统计点「${r.point}」上，${at}的责任方法（${r.methods.join('、')}）没挂这条 must`
                + '——决定结果的方法各自扛统计义务，上报封装只组装发送');
            }
          }
        }
      }
    }
  }

  const total = groups.reduce((n, g) => n + g.problems.length, 0);
  return gate(ctx, {
    groups,
    fix: FIX,
    checks: [
      { id: 'knowledge_obligation_on_entity', status: total ? STATUS.FAIL : STATUS.PASS,
        detail: `义务 ${obligations.length} 条；问题 ${total} 条` },
    ],
    inputs: [planPath, contractsPath(ctx.projectRoot, ctx.feature)],
  });
});
