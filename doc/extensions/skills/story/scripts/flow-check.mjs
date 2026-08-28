/**
 * story 前置流程契约的门禁（`AR/story-flow.json`）。
 *
 * 从 hooks/spec/post_check.mjs 搬出来独立成件：这套判据校验的是 /story 链自己的产物
 * ——三级关卡问了没、决策留痕齐不齐、范围收口没有——与 spec 章节结构无关。
 * 混在 spec hook 里，读的人得先翻过两百行 spec 章节判据才看得到它。
 *
 * 消费者：hooks/spec/post_check.mjs。契约是纯函数：给 featureRoot，回问题串数组（空 = 通过）。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';

/**
 * story 前置流程契约（`AR/story-flow.json`，见 SKILL.md「初析与流程契约」章）。
 *
 * 契约存在即表示该 feature 走了 /story：材料导入、拆分裁决、进入 spec 的授权都记在里面。
 * 未收口就进 spec，说明这些决策没走完：诊断出 PRD 缺料却径直进 /spec，人工补录的整份 PRD
 * 就全程没被读过。这里是该跳步的机械拦截点。
 *
 * 没走 /story 的 feature 没有这个文件，**不受本检查影响**。
 */
const FLOW_FILE = ['AR', 'story-flow.json'];
const FLOW_SCHEMA = 3;
// 三级关卡，每级只问一件事：材料够不够 → 范围怎么定 → 承载哪一份
const FLOW_GATES = new Set(['material_scope', 'scope_decision', 'split_carrier']);
// 只有第一级的值域是闭合的；第二级除固定的 carry_all 外是具名维度、第三级是份序号，
// 都由「chosen 必须在 options 里」把关——它们是本次分析的产物，枚举不了
const FLOW_MATERIAL_CHOICES = new Set(['supplement', 'confirm_scope']);
const FLOW_CARRY_ALL = 'carry_all';
const FLOW_OUTCOMES = new Set(['accepted', 'rejected']);
const FLOW_FIX = "处置：回 /story 走完三级关卡（材料够不够 → 范围怎么定 → 承载哪份）把范围定下来后再进本阶段。";
/**
 * 「已收口」是**一段区间**，不是一个值。
 *
 * 契约的状态机是 `complete` →（spec 阶段）→ `story_written`（S5 成文登记）→ `archived`。
 * 本判据问的是「进 spec 之前范围定了没有」，`complete` 之后的每一个状态都满足这个前提。
 * 写成 `status !== 'complete'` 会在 S5 之后反过来拦住自己的产物：spec harness 一重跑就
 * FAIL，`upstream_verdict_gate` 再把 coding、review 一起判 FAIL——四个已合法闭环的阶段
 * 集体翻红。这不是假想：一次端到端实跑真的撞上了，回归形态见测试域台账。
 */
const FLOW_CLOSED_STATES = new Set(['complete', 'story_written', 'archived']);
const DESIGN_FILE = ['AR', 'design.md'];

export function flowProblems(featureRoot) {
  const flowPath = path.join(featureRoot, ...FLOW_FILE);
  if (!fs.existsSync(flowPath)) return [];

  let flow;
  try {
    flow = JSON.parse(fs.readFileSync(flowPath, 'utf-8').replace(/^﻿/, ''));
  } catch (err) {
    // 坏 JSON 不能当「没有契约」放过去——那等于跳步免费
    return [`AR/story-flow.json 不是合法 JSON（${err.message}）：流程契约无法校验。${FLOW_FIX}`];
  }

  // 契约由 story_flow.py 写；本函数是防手工编辑与文件损坏的最后一道防线，正常情况下不该响
  if (flow?.schema !== FLOW_SCHEMA) {
    return [
      `AR/story-flow.json 的 schema 为 ${flow?.schema ?? '缺失'}，本阶段要求 ${FLOW_SCHEMA}。` +
        `契约应由 scripts/story_flow.py 写入，请勿手工维护。${FLOW_FIX}`,
    ];
  }

  const problems = [];
  const rounds = Array.isArray(flow?.rounds) ? flow.rounds : [];

  if (rounds.length === 0) {
    problems.push(`AR/story-flow.json 没有任何轮次记录——契约在但流程没走过。${FLOW_FIX}`);
  }

  rounds.forEach((r, i) => {
    const where = `AR/story-flow.json 第 ${i + 1} 轮`;
    // 一轮 = 一次初析：轮次由初析件哈希划界，两轮哈希相同说明是伪造的轮次
    const sha = r?.analysis?.sha256;
    if (!sha) problems.push(`${where}缺 analysis.sha256——无从证明这一轮确实重新初析过`);
    else if (i > 0 && sha === rounds[i - 1]?.analysis?.sha256) {
      problems.push(`${where}与上一轮的 analysis.sha256 相同——初析没重做，不构成新一轮`);
    }

    // 本 AR 定位是整条范围链的起点：没有它，「本 AR 承载什么」就没有依据，
    // 下游只能默默按上游全量走，SR 全量就会被写成本 AR 范围。
    //
    // 只查**收口那一轮**：材料盘点阶段（补料被拒的那些轮次）本来就还没做需求分析，
    // 要求每一轮都有定位，等于逼着人在材料没确认时先写完整分析。
    const isLastRound = i === rounds.length - 1;
    const pos = r?.positioning;
    if (isLastRound) {
      if (!pos || !String(pos?.scope_text ?? '').trim()) {
        problems.push(`${where}缺 positioning.scope_text——本 AR 当前范围没定下来就收了口`);
      } else if (!Array.isArray(pos?.sr_related_ars)) {
        problems.push(`${where}的 positioning.sr_related_ars 不是数组（同 SR 其它 AR；没有给空数组）`);
      } else if (pos.sr_related_ars.some(x => String(x?.ar ?? '').trim() === path.basename(featureRoot))) {
        problems.push(`${where}的 sr_related_ars 含本 AR 自己——该字段只列同一 SR 下的**其它** AR`);
      }
      // 第二级的选项集来自需求分析，不在关卡现编：契约里没有它，关卡就无从照出
      const scopeOptions = r?.scope_options;
      if (!Array.isArray(scopeOptions) || scopeOptions.length === 0) {
        problems.push(`${where}缺 scope_options——范围定法选项集没落契约，第二级只能现编选项`);
      } else if (!scopeOptions.some(o => String(o?.key ?? '').trim() === 'carry_all')) {
        problems.push(`${where}的 scope_options 缺固定首项 carry_all（按当前范围整体承载）`);
      }
    }

    const gates = Array.isArray(r?.gates) ? r.gates : null;
    if (!gates) {
      problems.push(`${where}缺 gates 数组（一轮可含多条关卡记录，含未生效的那次）`);
      return;
    }
    gates.forEach((d, j) => {
      const at = `${where}第 ${j + 1} 条关卡记录`;
      const gate = d?.gate;
      if (!FLOW_GATES.has(gate)) {
        problems.push(`${at}的 gate 非法（须为 material_scope / scope_decision / split_carrier）`);
      }
      // 只记选中项的话，「看过选项后选了不拆」与「压根没摆过拆分选项」事后完全同形
      const options = Array.isArray(d?.options) ? d.options : null;
      if (!options || options.length === 0) {
        problems.push(`${at}缺 options——摆了哪些选项没留痕，事后分不清人是否看见过其它选择`);
      } else if (!options.some(o => String(o?.key ?? '').trim() === String(d?.chosen ?? '').trim())) {
        problems.push(`${at}的 chosen「${d?.chosen}」不在 options 里——选的必须是摆出来的`);
      }
      if (gate === 'material_scope' && !FLOW_MATERIAL_CHOICES.has(d?.chosen)) {
        problems.push(`${at}的 chosen 非法（material_scope 须为 supplement / confirm_scope 之一）`);
      }
      // 第二级摆出的选项必须就是分析定下的那些——多一项就是现编的
      if (gate === 'scope_decision' && Array.isArray(r?.scope_options) && Array.isArray(d?.options)) {
        const analysed = new Set(r.scope_options.map(o => String(o?.key ?? '').trim()));
        const invented = d.options
          .map(o => String(o?.key ?? '').trim())
          .filter(k => k && !analysed.has(k));
        if (invented.length) {
          problems.push(
            `${at}摆出了需求分析里没有的选项：${invented.join('、')}` +
              '——选项集只能照出分析定下的那几项，现编的选项没有份表也没有内容，人无从评估'
          );
        }
      }
      if (!FLOW_OUTCOMES.has(d?.outcome)) {
        problems.push(`${at}的 outcome 非法（须为 accepted / rejected）`);
      }
      if (d?.outcome === 'rejected' && !d?.reason) {
        problems.push(`${at}被拒却没写 reason——人被拦了一次，审计上必须看得见为什么`);
      }
      if (!d?.at) problems.push(`${at}缺时间戳 at`);
      if (d?.by === 'ai' && !d?.basis) {
        // 代选免掉的是等回话，不是免留依据：无依据的代选事后无从复核，也就无从推翻
        problems.push(`${at}为 AI 代选但缺 basis（用户授权时那句原话）`);
      }
    });
  });

  // 收口与拆分一律按**当前轮**判：一轮 = 一次「初析 → 关卡」循环，补料会开新一轮。
  // 展平所有轮次去判，第一轮那次 proceed 就能替补料后的新一轮授权收口。
  const lastRound = rounds[rounds.length - 1];
  const lastGates = Array.isArray(lastRound?.gates) ? lastRound.gates : [];
  // split 是契约级字段，但决策属于某一轮——靠 settled_round 挂钩，重新初析后不再算数
  const splitSettledThisRound =
    flow?.split?.decided === 'split' && flow?.split?.settled_round === lastRound?.round;

  // 第二级选了某个切分维度，却没走到第三级定案：「打算切」被当成了「切好了」，
  // 而此时范围其实还是定位出来的那个全量
  const choseDimension = lastGates.some(
    d => d?.gate === 'scope_decision' && d?.chosen !== FLOW_CARRY_ALL && d?.outcome === 'accepted'
  );
  if (choseDimension && !splitSettledThisRound) {
    problems.push(
      'AR/story-flow.json 本轮第二级选了切分维度，但份表未在本轮定案——' +
        '第三级「本 AR 承载哪份」没走完，范围实际未切'
    );
  }
  // 反过来：定了案却没有第二级的维度选择，说明份表来路不明
  if (splitSettledThisRound && !choseDimension) {
    problems.push(
      'AR/story-flow.json 本轮定案了切分，但第二级没有选过任何切分维度——' +
        '份表按哪个维度切的没有留痕'
    );
  }

  if (flow?.split?.decided === 'split') {
    if (!String(flow.split.scope_text ?? '').trim()) {
      problems.push(
        'AR/story-flow.json 已定案拆分但 split.scope_text 为空——范围文字丢了，' +
          'AR/design.md 的「本 AR 范围与拆分说明」就没有东西可写'
      );
    }
    // 两级子菜单的留痕查定案那一轮：split 记的是哪一轮定的，就去哪一轮找记录
    const settledRound = rounds.find(r => r?.round === flow.split.settled_round);
    const settledGates = Array.isArray(settledRound?.gates) ? settledRound.gates : lastGates;
    for (const gate of ['scope_decision', 'split_carrier']) {
      if (!settledGates.some(d => d?.gate === gate)) {
        problems.push(`AR/story-flow.json 已定案切分但缺 ${gate} 关卡记录——那一级的选择没留痕`);
      }
    }
    // 份表回答「拆成几份、各归谁、什么顺序、谁依赖谁」；只有一段范围文字，
    // story 05 章的必答问（兄弟各承载什么、先后依赖）就只能靠现编。
    const parts = Array.isArray(flow.split.parts) ? flow.split.parts : [];
    if (parts.length) {
      // feature 名从产物路径推导——本函数只拿得到 featureRoot，取 ctx 会在这里抛
      // ReferenceError，而它只在拆分定案时才触发，平时跑 proceed 路径根本发现不了。
      const feature = path.basename(featureRoot);
      const mine = parts.filter(p => String(p?.carrier ?? '').trim() === feature);
      if (mine.length !== 1) {
        problems.push(
          `AR/story-flow.json 的 split.parts 里 carrier 为「${feature}」的有 ${mine.length} 份，` +
            '应恰好一份——本 AR 承载哪一份是拆分的核心结论'
        );
      }
    }
  }

  if (!FLOW_CLOSED_STATES.has(flow?.status)) {
    problems.push(
      `story 前置流程未收口（status=${flow?.status ?? '缺失'}）：材料与拆分决策没走完就进了 spec。${FLOW_FIX}`
    );
  } else {
    // 收口的前置是**本轮范围已定**：第二级选了整体承载，或第三级完成定案。
    // 不再看「末条是不是 proceed」——范围一定就直接进 S4，没有回关卡收口这一步了。
    const carriedAll = lastGates.some(
      d => d?.gate === 'scope_decision' && d?.chosen === FLOW_CARRY_ALL && d?.outcome === 'accepted'
    );
    if (!carriedAll && !splitSettledThisRound) {
      problems.push(
        'AR/story-flow.json 标了 complete，但本轮既没选整体承载、也没定案切分——' +
          '范围没定下来，收口与决策记录自相矛盾'
      );
    }
    if (!flow?.design_generated_at) {
      problems.push('AR/story-flow.json 标了 complete，但 design_generated_at 为空——提取件生成未留痕');
    }
  }

  // 契约与产物的交叉核对：同 SR 还有其它 AR 时，design.md 必须点名它们。
  //
  // 查的是**该出现的有没有出现**，不是**不该出现什么措辞**：范围外内容归谁，只能靠写出
  // 单号来表达，换个说法绕不过去；而拿「承载全部需求」这类句子当违禁词，模型换句话
  // 就失效，且合法用法（真的只有本 AR 时）还会被误伤。
  const related = Array.isArray(lastRound?.positioning?.sr_related_ars)
    ? lastRound.positioning.sr_related_ars
    : [];
  if (related.length) {
    const designPath = path.join(featureRoot, ...DESIGN_FILE);
    if (fs.existsSync(designPath)) {
      const designText = fs.readFileSync(designPath, 'utf-8');
      const missing = related
        .map(x => String(x?.ar ?? '').trim())
        .filter(ar => ar && !designText.includes(ar));
      if (missing.length) {
        problems.push(
          `AR/design.md 通篇没提到同一 SR 下的 ${missing.join('、')}——` +
            '有兄弟 AR 就说明本 AR 不承载全部，范围外内容归谁必须写出来（单号或「待立项」），' +
            '否则 spec 的 out_of_scope 只能笼统写「本需求不做」，评审者分不清有人接还是没人接。' +
            '形态见 rules/ar_design_init.md §3（模板 1.2 三形态）'
        );
      }
    }
  }
  return problems;
}

/** 场景探针：走过 /story 的 feature 才有流程契约。没走的不受本套判据影响。 */
export function isStoryFeature(featureRoot) {
  return fs.existsSync(path.join(featureRoot, ...FLOW_FILE));
}
