/**
 * story 前置流程契约的门禁（`AR/story-src/story-flow.json`）。
 *
 * 这套判据校验的是 /story 链自己的产物——三级关卡问了没、决策留痕齐不齐、
 * 范围收口没有——与 spec 章节结构无关，所以不放在 spec hook 里。
 *
 * 契约的写入侧在同目录的 Python 流程模块；本文件是 JS 侧的只读消费者。
 * 导出都是纯函数：给 featureRoot，回问题串数组（空 = 通过）。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * story 前置流程契约（`AR/story-src/story-flow.json`，规则见 rules/init_analysis.md）。
 *
 * 契约存在即表示该 feature 走了 /story：材料导入、拆分裁决、进入 spec 的授权都记在里面。
 * 未收口就进 spec，说明这些决策没走完：诊断出 PRD 缺料却径直进 /spec，人工补录的整份 PRD
 * 就全程没被读过。这里是该跳步的机械拦截点。
 *
 * 没走 /story 的 feature 没有这个文件，**不受本检查影响**。
 */
const FLOW_FILE = ['AR', 'story-src', 'story-flow.json'];

/**
 * 章节合同：流程契约的常量（`flow`：schema、关卡名、整体承载键）与第一级关卡的合法值域
 * （`gates.material_scope.options`）都登记在它里面。`story_flow.py` 写、这里读——两边各存一份
 * 字面的话，只改一处，写进契约的选择就会在这里被判非法。
 *
 * **读不到要出声，不退化成空集**：空集会把每一条记录都判成非法，于是作者拿着一份合法契约
 * 去改它，而坏掉的是合同的读取路径。在真正要判的那一刻才读——加载期读、加载期吞掉异常，
 * 两样都做不到把原因带出来。
 *
 * @returns {{flow: {schema: number, gates: Set<string>, carryAll: string}|null,
 *            keys: Set<string>|null, problem: string|null}}
 */
function readChapterContract() {
  const file = path.join(path.dirname(fileURLToPath(import.meta.url)),
    '..', '..', '..', 'contracts', 'story-chapters.json');
  let contract = null;
  try {
    contract = JSON.parse(stripBom(fs.readFileSync(file, 'utf-8')));
  } catch (err) {
    return { flow: null, keys: null,
      problem: `章节合同读不到或不是合法 JSON（${err.message}）：流程常量与第一级关卡的值域登记在它的`
        + ' flow 与 gates.material_scope 里，读不到就判不了契约——先修 contracts/story-chapters.json' };
  }
  const f = contract?.flow;
  const gates = Array.isArray(f?.gates) ? f.gates.map(g => String(g ?? '').trim()).filter(Boolean) : [];
  if (!Number.isInteger(f?.schema) || !gates.length || !String(f?.carry_all ?? '').trim()) {
    return { flow: null, keys: null,
      problem: '章节合同的 flow 缺 schema / gates / carry_all：流程契约的常量没了，'
        + '判不了契约——先修 contracts/story-chapters.json' };
  }
  const keys = (contract?.gates?.material_scope?.options ?? [])
    .map(o => String(o?.key ?? '').trim()).filter(Boolean);
  if (!keys.length) {
    return { flow: null, keys: null,
      problem: '章节合同的 gates.material_scope.options 是空的：第一级关卡的值域没了，'
        + '判不了 chosen——先修 contracts/story-chapters.json' };
  }
  return { flow: { schema: f.schema, gates: new Set(gates), carryAll: String(f.carry_all).trim() },
    keys: new Set(keys), problem: null };
}

function stripBom(text) {
  return String(text ?? '').replace(/^\uFEFF/, '');
}

const FLOW_FIX = "处置：回 /story 走完三级关卡（材料 → 范围怎么定 → 承载哪份）把范围定下来后再进本阶段。";
/**
 * 契约状态机：`complete`（范围收口）→ `story_written`（成文登记）。
 *
 * **每道判据问的都是「到没到某个点」，答案是一段区间，不是一个值。**
 * 写成等于某个值，会在流程往前走之后反过来拦住自己的产物：「须 complete」写成
 * `status !== 'complete'`，成文登记后 spec harness 一重跑就 FAIL，`upstream_verdict_gate`
 * 再把 coding、review 一并判红——四个已合法闭环的阶段集体翻红。
 *
 * `archived` 不是流程状态：归档是契约里独立的记录字段（`contract.archived`），
 * 登记归档要求流程已在 `story_written`，状态本身不再前进——流程状态只写实际走到过的值。
 */
const FLOW_STATES = ['complete', 'story_written'];

/**
 * 「流程走到了 `atLeast` 这一步没有」——两条 spec 判据共用这一个函数。
 *
 * @param {object|null} flow 已解析的契约
 * @param {string} atLeast 状态机里的最低要求
 * @returns {boolean} 没有契约时返回 false，由调用方决定「没走 /story」怎么算
 */
function reached(flow, atLeast) {
  const at = FLOW_STATES.indexOf(String(flow?.status ?? ''));
  const need = FLOW_STATES.indexOf(atLeast);
  return at >= 0 && need >= 0 && at >= need;
}
const DESIGN_FILE = ['AR', 'design.md'];

export function flowProblems(featureRoot) {
  const { exists, flow, error } = readFlow(featureRoot);
  if (!exists) return [];
  if (error) {
    // 坏 JSON 不能当「没有契约」放过去——那等于跳步免费
    return [`AR/story-src/story-flow.json 不是合法 JSON（${error}）：流程契约无法校验。${FLOW_FIX}`];
  }

  const contract = readChapterContract();
  if (contract.problem) return [contract.problem];
  const { schema, gates: GATES, carryAll } = contract.flow;

  // 契约由 story_flow.py 写；下面保留的判据是「模型手改契约时仍有保护作用」的那些：
  // 坏文件、错状态、chosen 不在摆出的选项里、第二级现编选项、份表与定位——它们直接决定后续流程。
  // 写入侧已保证的形状（outcome 值域、时间戳、签名人）手改成错形状也不改变流程走向，不在这里重判。
  if (flow?.schema !== schema) {
    return [
      `AR/story-src/story-flow.json 的 schema 为 ${flow?.schema ?? '缺失'}，本阶段要求 ${schema}。` +
        `契约应由 scripts/core/story_flow.py 写入，请勿手工维护。${FLOW_FIX}`,
    ];
  }

  const problems = [];
  const rounds = Array.isArray(flow?.rounds) ? flow.rounds : [];

  if (rounds.length === 0) {
    problems.push(`AR/story-src/story-flow.json 没有任何轮次记录——契约在但流程没走过。${FLOW_FIX}`);
  }

  rounds.forEach((r, i) => {
    const where = `AR/story-src/story-flow.json 第 ${i + 1} 轮`;
    // 一轮 = 一次材料状态：轮次只由材料清单的 digest 划界。
    //
    // 这里**不查初析件哈希**。初析在同一轮内会从盘点版改到完整版，拿它划轮次，
    // 等于「材料没动、重写一遍分析」也能造出一轮，而真正补了料却在分析之前跑 round 的
    // 那一轮反倒被判成伪造。材料变没变是磁盘上的事实，由 `materials/registry.py` 按现状算。
    const digest = String(r?.materials?.digest ?? '');
    if (!digest) {
      problems.push(`${where}缺 materials.digest——轮次没有材料版本可依，`
        + '重跑 `scripts/core/story_flow.py round` 让它按磁盘现状重算。' + FLOW_FIX);
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
    }

    const gates = Array.isArray(r?.gates) ? r.gates : null;
    if (!gates) {
      problems.push(`${where}缺 gates 数组（一轮可含多条关卡记录，含未生效的那次）`);
      return;
    }
    gates.forEach((d, j) => {
      const at = `${where}第 ${j + 1} 条关卡记录`;
      const gate = d?.gate;
      if (!GATES.has(gate)) {
        problems.push(`${at}的 gate 非法（须为 ${[...GATES].join(' / ')}）`);
      }
      // 只记选中项的话，「看过选项后选了不拆」与「压根没摆过拆分选项」事后完全同形
      const options = Array.isArray(d?.options) ? d.options : null;
      if (!options || options.length === 0) {
        problems.push(`${at}缺 options——摆了哪些选项没留痕，事后分不清人是否看见过其它选择`);
      } else if (!options.some(o => String(o?.key ?? '').trim() === String(d?.chosen ?? '').trim())) {
        problems.push(`${at}的 chosen「${d?.chosen}」不在 options 里——选的必须是摆出来的`);
      }
      if (gate === 'material_scope' && !contract.keys.has(d?.chosen)) {
        problems.push(`${at}的 chosen 非法（material_scope 须为 `
          + `${[...contract.keys].join(' / ')} 之一）`);
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
    d => d?.gate === 'scope_decision' && d?.chosen !== carryAll && d?.outcome === 'accepted'
  );
  if (choseDimension && !splitSettledThisRound) {
    problems.push(
      'AR/story-src/story-flow.json 本轮第二级选了切分维度，但份表未在本轮定案——' +
        '第三级「本 AR 承载哪份」没走完，范围实际未切'
    );
  }
  // 反过来：定了案却没有第二级的维度选择，说明份表来路不明
  if (splitSettledThisRound && !choseDimension) {
    problems.push(
      'AR/story-src/story-flow.json 本轮定案了切分，但第二级没有选过任何切分维度——' +
        '份表按哪个维度切的没有留痕'
    );
  }

  if (flow?.split?.decided === 'split') {
    // 两级子菜单的留痕查定案那一轮：split 记的是哪一轮定的，就去哪一轮找记录
    const settledRound = rounds.find(r => r?.round === flow.split.settled_round);
    const settledGates = Array.isArray(settledRound?.gates) ? settledRound.gates : lastGates;
    for (const gate of ['scope_decision', 'split_carrier']) {
      if (!settledGates.some(d => d?.gate === gate)) {
        problems.push(`AR/story-src/story-flow.json 已定案切分但缺 ${gate} 关卡记录——那一级的选择没留痕`);
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
          `AR/story-src/story-flow.json 的 split.parts 里 carrier 为「${feature}」的有 ${mine.length} 份，` +
            '应恰好一份——本 AR 承载哪一份是拆分的核心结论'
        );
      }
    }
  }

  if (!reached(flow, 'complete')) {
    problems.push(
      `story 前置流程未收口（status=${flow?.status ?? '缺失'}）：材料与拆分决策没走完就进了 spec。${FLOW_FIX}`
    );
  } else {
    // 收口的前置是**本轮范围已定**：第二级选了整体承载，或第三级完成定案。
    // 范围一定就直接进 S4，收口不依赖最后一条决策是什么。
    const carriedAll = lastGates.some(
      d => d?.gate === 'scope_decision' && d?.chosen === carryAll && d?.outcome === 'accepted'
    );
    if (!carriedAll && !splitSettledThisRound) {
      problems.push(
        'AR/story-src/story-flow.json 标了 complete，但本轮既没选整体承载、也没定案切分——' +
          '范围没定下来，收口与决策记录自相矛盾'
      );
    }
    if (!flow?.design_generated_at) {
      problems.push('AR/story-src/story-flow.json 标了 complete，但 design_generated_at 为空——提取件生成未留痕');
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

/**
 * 叙事件成文了没有——spec 阶段三份产物里的第三份。
 *
 * spec 一次 pass 产出 `spec.md` / `AR/review.md` / `AR/story.md`，三者事实同源。
 * 判据不查文件在不在：只查存在的话，**手写一份简版照样过**。
 * 查的是登记态——`story_flow.py story` 登记前会重跑 `story-build check`，
 * 登记成功即等于九项判据都过了。一处判定，一处真源。
 *
 * 把成文挪到 spec 之后当独立一步、触发条件写「归档之前」的话：本地单没有归档，
 * 这个时点不存在，于是四个阶段全绿而 story 从来没被写出来。成文回到 spec 阶段内，
 * 它就有阶段边界守着了。
 */
export function storyProduced(featureRoot) {
  const { exists, flow, error } = readFlow(featureRoot);
  if (!exists) return [];                // 没走 /story，本判据不适用
  if (error) {
    // 读不出状态就判不了成文态。**不当作「没成文」也不当作「成文了」**——说出读不了这件事。
    return [`AR/story-src/story-flow.json 不是合法 JSON（${error}）：成文态无从判定。${FLOW_FIX}`];
  }
  if (reached(flow, 'story_written')) return [];
  return [
    'spec 三份产物缺叙事件（AR/story.md 未登记成文）：spec 是一次 pass 产出 '
    + 'spec.md / AR/review.md / AR/story.md 三份。处置：跑 `story_flow.py status --feature <feature>`，'
    + '按它给的下一步走到 `story_flow.py story` 登记。',
  ];
}

/** 读契约。三种结果各自可辨：没有文件 / 读出来了 / 解析失败并带原因。 */
function readFlow(featureRoot) {
  const flowPath = path.join(featureRoot, ...FLOW_FILE);
  if (!fs.existsSync(flowPath)) return { exists: false, flow: null, error: null };
  try {
    return { exists: true, error: null, flow: JSON.parse(stripBom(fs.readFileSync(flowPath, 'utf-8'))) };
  } catch (err) {
    return { exists: true, flow: null, error: err.message };
  }
}
