/**
 * story 前置流程契约的门禁（`AR/story-src/story-flow.json`）。
 *
 * 这套判据校验的是 /story 链自己的产物——材料确认了没、人的原话记录是否成证据、
 * 当前问法与材料都定了没有；成文骨架起稿前（`story-build skeleton`）按它预检。
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
 * 契约存在即表示该需求走了 /story：材料导入与确认、设计后必要问答的原话都记在里面。
 * 未确认材料就起稿成文，说明材料还没走到位：诊断出 PRD 缺料却径直往下写，人工补录的整份 PRD
 * 就全程没被读过。这里是该跳步的机械拦截点。
 *
 * 没走 /story 的 feature 没有这个文件，**不受本检查影响**。
 */
const FLOW_FILE = ['AR', 'story-src', 'story-flow.json'];
const ASK_FILE = ['AR', 'story-src', '.ask.json'];
const MATERIAL_GATE = 'material_scope';
const DESIGN_KIND = 'design_questions';

/**
 * 章节合同：流程契约的常量（`flow`：schema、关卡名）与材料关卡的合法值域
 * （`gates.material_scope.options`）都登记在它里面。`story_flow.py` 写、这里读——两边各存一份
 * 字面的话，只改一处，写进契约的选择就会在这里被判非法。
 *
 * **读不到要出声，不退化成空集**：空集会把每一条记录都判成非法，于是作者拿着一份合法契约
 * 去改它，而坏掉的是合同的读取路径。在真正要判的那一刻才读——加载期读、加载期吞掉异常，
 * 两样都做不到把原因带出来。
 *
 * @returns {{flow: {schema: number, gates: Set<string>}|null,
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
      problem: `章节合同 contracts/story-chapters.json：读不到或不是合法 JSON（${err.message}）——流程常量与材料关卡的值域登记在它的`
        + ' flow 与 gates.material_scope 里，读不到就判不了契约' };
  }
  const f = contract?.flow;
  const gates = Array.isArray(f?.gates) ? f.gates.map(g => String(g ?? '').trim()).filter(Boolean) : [];
  if (!Number.isInteger(f?.schema) || !gates.length) {
    return { flow: null, keys: null,
      problem: '章节合同 contracts/story-chapters.json 的 flow：缺 schema / gates——流程契约的常量登记在这里，'
        + '缺了判不了契约' };
  }
  const keys = (contract?.gates?.material_scope?.options ?? [])
    .map(o => String(o?.key ?? '').trim()).filter(Boolean);
  if (!keys.length) {
    return { flow: null, keys: null,
      problem: '章节合同 contracts/story-chapters.json 的 gates.material_scope.options：是空的——材料关卡的值域登记在这里，'
        + '空了判不了 chosen' };
  }
  return { flow: { schema: f.schema, gates: new Set(gates) }, keys: new Set(keys), problem: null };
}

function stripBom(text) {
  return String(text ?? '').replace(/^\uFEFF/, '');
}

const FLOW_FIX = "前置流程由 /story 的材料确认与原生设计写进契约：材料经人确认、按它进设计之后才起稿成文。";
/** 契约的状态只有两个：`gathering`（成文登记之前）与 `story_written`（成文登记）；归档是独立的记录字段。 */
const FLOW_STATES = ['gathering', 'story_written'];
/** 设计问答原话记录的必需字段与不得携带的字段：原话只作证据，目标/版本只在原生 feedback 条目上。 */
const ANSWER_REQUIRED = ['ask_id', 'item_id', 'question', 'options', 'reply', 'at', 'source_ref'];
const ANSWER_FORBIDDEN = ['target_ref', 'source_revision', 'mapped_by'];

export function flowProblems(featureRoot) {
  const { exists, flow, error } = readFlow(featureRoot);
  if (!exists) return [];
  if (error) {
    // 坏 JSON 不能当「没有契约」放过去——那等于跳步免费
    return [`AR/story-src/story-flow.json：不是合法 JSON（${error}）——流程契约无法校验，读不出按没走完计；${FLOW_FIX}`];
  }

  const contract = readChapterContract();
  if (contract.problem) return [contract.problem];
  const { schema, gates: GATES } = contract.flow;

  // 契约由 story_flow.py 写；下面保留的判据是「模型手改契约时仍有保护作用」的那些：
  // 坏文件、错状态、chosen 不在摆出的选项里、原话记录缺字段与旧字段残留。
  if (flow?.schema !== schema) {
    return [
      `AR/story-src/story-flow.json：schema 是 ${flow?.schema ?? '缺失'}，当前流程契约是 ${schema}——` +
        '本版不接续旧版现场，也不自动迁移；要按旧版收口就留在原版，要用本版就为新需求另跑 init',
    ];
  }

  const problems = [];
  const rounds = Array.isArray(flow?.rounds) ? flow.rounds : [];

  if (rounds.length === 0) {
    problems.push(`AR/story-src/story-flow.json：没有任何轮次记录，契约在而流程没走过——${FLOW_FIX}`);
  }

  // 契约级旧字段：范围切分与份表随退出一起离场；留着说明这是旧机制的残留，不按新契约判。
  if (flow?.split !== undefined) {
    problems.push('AR/story-src/story-flow.json：还带着 split（范围切分与份表）——本版不再维护范围裁决与份表，'
      + '范围由蓝图承载；旧现场不接续');
  }

  rounds.forEach((r, i) => {
    const where = `AR/story-src/story-flow.json 第 ${i + 1} 轮`;
    // 一轮 = 一次材料状态：轮次由材料清单的 digest 划界。设计开始之后材料变化只登记进本轮。
    //
    // 这里**不查初析件哈希**。初析在同一轮内会从盘点版改到完整版，拿它划轮次，
    // 等于「材料没动、重写一遍分析」也能造出一轮，而真正补了料却在分析之前跑 round 的
    // 那一轮反倒被判成伪造。材料变没变是磁盘上的事实，由 `materials/registry.py` 按现状算。
    const digest = String(r?.materials?.digest ?? '');
    if (!digest) {
      problems.push(`${where}：缺 materials.digest——轮次按材料版本划界，`
        + 'digest 由 `scripts/core/story_flow.py round` 按磁盘现状算出写入。' + FLOW_FIX);
    }

    // 本 AR 定位是整条范围链的起点：没有它，「本 AR 承载什么」就没有依据，
    // 下游只能默默按上游全量走，SR 全量就会被写成本 AR 范围。
    //
    // 只查**最后一轮**：材料盘点阶段（补料被拒的那些轮次）本来就还没做需求分析，
    // 要求每一轮都有定位，等于逼着人在材料没确认时先写完整分析。
    if (i === rounds.length - 1) {
      const pos = r?.positioning;
      if (!pos || !String(pos?.scope_text ?? '').trim()) {
        problems.push(`${where}缺 positioning.scope_text——本轮范围链从本 AR 定位起，本 AR 当前范围没定下来就进了设计`);
      } else if (!Array.isArray(pos?.sr_related_ars)) {
        problems.push(`${where}的 positioning.sr_related_ars 不是数组（同 SR 其它 AR；没有给空数组）`);
      } else if (pos.sr_related_ars.some(x => String(x?.ar ?? '').trim() === path.basename(featureRoot))) {
        problems.push(`${where}的 sr_related_ars 含本 AR 自己——该字段只列同一 SR 下的**其它** AR`);
      }
    }

    if (r?.scope_options !== undefined) {
      problems.push(`${where}还带着 scope_options（范围定法选项集）——本版不再有范围裁决关卡，旧现场不接续`);
    }
    const gates = Array.isArray(r?.gates) ? r.gates : null;
    if (!gates) {
      problems.push(`${where}缺 gates 数组（一轮可含多条记录，含未生效的那次）`);
      return;
    }
    gates.forEach((d, j) => {
      const at = `${where}第 ${j + 1} 条记录`;
      const gate = d?.gate;
      if (!GATES.has(gate)) {
        problems.push(`${at}的 gate 非法（须为 ${[...GATES].join(' / ')}）——关卡名按章节合同 flow.gates 认`);
      }
      // 只记选中项的话，「看过选项后选了不补料」与「压根没摆过材料选项」事后完全同形
      const options = Array.isArray(d?.options) ? d.options : null;
      if (!options || options.length === 0) {
        problems.push(`${at}缺 options——摆了哪些选项没留痕，事后分不清人是否看见过其它选择`);
      } else if (!options.some(o => String(o?.key ?? '').trim() === String(d?.chosen ?? '').trim())) {
        problems.push(`${at}的 chosen「${d?.chosen}」不在 options 里——选的必须是摆出来的`);
      }
      // 人签只能记在问过之后：问法编号与人的原话缺一，这一笔就说不清是谁在什么问题下选的
      if (d?.by !== 'human' || !String(d?.ask_id ?? '').trim() || !String(d?.reply ?? '').trim()) {
        problems.push(`${at}不是一笔完整的人签（缺 by: human、ask_id 或原话 reply）`
          + '——记录只由 `story_flow.py decide` 在问过之后写');
      }
      if (gate === MATERIAL_GATE && !contract.keys.has(d?.chosen)) {
        problems.push(`${at}的 chosen 非法（material_scope 须为 `
          + `${[...contract.keys].join(' / ')} 之一）——值域按章节合同 gates.material_scope.options 认`);
      }
    });

    // 设计问答原话：只存问法、原话与出处；旧字段（目标/版本/映射来源）不得混进记录。
    const answers = Array.isArray(r?.answers) ? r.answers : [];
    answers.forEach((a, j) => {
      const at = `${where}第 ${j + 1} 条设计问答记录`;
      const missing = ANSWER_REQUIRED.filter(k => (k === 'options'
        ? !Array.isArray(a?.options)
        : !String(a?.[k] ?? '').trim()));
      if (missing.length) {
        problems.push(`${at}缺 ${missing.join('、')}——原话记录要有问法、题号、问题、当时候选、原话、时刻与出处`);
      }
      const carried = ANSWER_FORBIDDEN.filter(k => a?.[k] !== undefined);
      if (carried.length) {
        problems.push(`${at}带着 ${carried.join('、')}——原话记录只存证据，目标/版本只由原生 feedback 条目承担`);
      }
    });
    const seen = new Set();
    answers.forEach((a, j) => {
      const key = `${a?.ask_id ?? ''}/${a?.item_id ?? ''}`;
      if (seen.has(key)) problems.push(`${where}第 ${j + 1} 条设计问答记录与前面重复：${key}——同一题只记一次原话`);
      seen.add(key);
    });
  });

  if (!FLOW_STATES.includes(String(flow?.status ?? ''))) {
    problems.push(`AR/story-src/story-flow.json：status 是 ${flow?.status ?? '缺失'}，不是 ${FLOW_STATES.join(' / ')} 之一——契约只由 story_flow.py 写入`);
  }
  // 成文的前置是**本轮材料已确认**：范围与设计由原生蓝图承载，本地只核材料这一道关。
  const lastRound = rounds[rounds.length - 1];
  const lastGates = Array.isArray(lastRound?.gates) ? lastRound.gates : [];
  const confirmed = lastGates.some(d => d?.gate === MATERIAL_GATE && d?.outcome === 'accepted');
  if (!confirmed) {
    problems.push(
      `AR/story-src/story-flow.json：本轮材料还没确认（没有生效的 material_scope 记录），材料没走完就开始成文——${FLOW_FIX}`
    );
  }

  // 当前问法：材料问法沿用原协议；设计问法要有题号与问题，且不写进 gates。
  const askPath = path.join(featureRoot, ...ASK_FILE);
  const ask = readJsonOrNull(askPath);
  if (!ask && fs.existsSync(askPath)) {
    problems.push('AR/story-src/.ask.json：读不出或不是合法 JSON——当前问法无法核对，重新跑 `status` 生成');
  }
  if (ask) {
    const kind = ask?.kind ?? ask?.gate;
    if (kind !== MATERIAL_GATE && kind !== DESIGN_KIND) {
      problems.push(`AR/story-src/.ask.json：问法种类是 ${kind ?? '缺失'}，不是 ${MATERIAL_GATE} 与 ${DESIGN_KIND} 之一`);
    } else if (kind === DESIGN_KIND) {
      const items = Array.isArray(ask?.items) ? ask.items : [];
      if (!items.length) {
        problems.push('AR/story-src/.ask.json：设计问答缺 items——没有题就没有问法');
      }
      const seen = new Set();
      items.forEach((it, i) => {
        const id = String(it?.item_id ?? '').trim();
        if (!id) problems.push(`AR/story-src/.ask.json 第 ${i + 1} 题缺 item_id`);
        else if (seen.has(id)) problems.push(`AR/story-src/.ask.json 里题号 ${id} 重复`);
        seen.add(id);
        if (!String(it?.question ?? '').trim()) problems.push(`AR/story-src/.ask.json 第 ${i + 1} 题缺 question`);
      });
    }
  }
  return problems;
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

/** 读一份 JSON；读不到或坏了都返回 null——这里的用途只判「有没有当前问法」。 */
function readJsonOrNull(file) {
  try { return JSON.parse(stripBom(fs.readFileSync(file, 'utf-8'))); } catch { return null; }
}