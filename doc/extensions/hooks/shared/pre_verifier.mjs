/**
 * pre_verifier —— 告诉 verifier **本阶段的知识判断在哪份文件里、按什么判**。
 *
 * ## 从「逐行必答清单」改成「指路」
 *
 * 上一版把本阶段的判定全集拆成一张表注入，要求 verifier 逐行裁「设计 / 复述 / 不适用」
 * 并把裁决表写进报告，门禁再逐行核对键与引文。三件事因此发生：
 *
 * - 裁决量随材料条数涨，而读者拿到的判断不增加；
 * - 证据列退化成回声——注入的清单里有什么字，证据列就抄什么字，于是加了「引文要 12 字
 *   以上、要能在产物里检索到」，那又变成一道找字符串的题；
 * - 判据从「这条要求是不是本需求的设计」滑向「这行有没有被裁过」，后者是格式，前者才是判断。
 *
 * 现在只给三样：判断的真源在哪、按什么判、结论写成什么。裁多少行由 verifier 按需要定，
 * 机械层不数行数、不核引文、不排相似度——那些都是拿字符串近似语义。
 *
 * ## 注入不等于执行
 *
 * 报告有没有落盘仍由各阶段 post_check 核（`verifier-report.mjs`），核的是形态：
 * 结果块在不在、结论分类齐不齐。审查得对不对由人抽查。
 *
 * 契约：stdin JSON ctx → stdout JSON { promptFragments: string[] }。
 */
import * as path from 'node:path';
import { extensionRoot, lines, readTextOrNull } from './paths.mjs';

/**
 * 知识类语义判据的命名前缀。
 *
 * 用**命名约定**而不是一份 id 清单来认它们：清单要跟着 overlay 改，改漏了就静默失效；
 * 前缀是数据形态，新增一条知识判据自动被认。同一份 overlay 里的其它判据
 * （叙述质量、上游覆盖等）不是知识类，不进本清单。
 */
const KNOWLEDGE_CHECK_PREFIX = 'knowledge_';

/** 本阶段知识判断的真源。spec 自己写，之后各阶段读 plan 冻结的结果。 */
const SOURCE_OF_TRUTH = {
  spec: {
    file: 'spec/knowledge-use.yaml',
    what: '每条规约命中与否、命中的要求做什么、模式有哪些候选',
  },
  plan: {
    file: 'plan/contracts.yaml',
    what: '每条命中的规约挂在哪个实体上（`must`）、模式选了哪几个（`files[].pattern`）',
  },
};

/**
 * 本阶段该产出哪些知识判据结论 —— **从 overlay 现取**，不在这里维护第二份清单。
 *
 * overlay 是这些判据的真源；把 id 抄一份到代码里，改了 overlay 就会两边对不上，
 * 而且是静默的（框架侧 overlay 解析失败本身也不出声）。所以这里解析不出来就响亮报出，
 * 让人看见「判据清单没生效」，而不是悄悄注入一份空要求。
 */
function overlayCheckIds(projectRoot, phase) {
  const p = path.join(extensionRoot(projectRoot), 'rules', `${phase}-rules.overlay.yaml`);
  const text = readTextOrNull(p);
  if (text === null) return { ids: [], error: `读不到 rules/${phase}-rules.overlay.yaml` };
  const rows = lines(text);
  const start = rows.findIndex(l => /^semantic_checks\s*:/.test(l));
  if (start < 0) return { ids: [], error: `${phase} overlay 里没有 semantic_checks` };
  const ids = [];
  for (let i = start + 1; i < rows.length; i++) {
    const line = rows[i];
    if (!line.trim() || line.trim().startsWith('#')) continue;
    if (!/^\s/.test(line)) break;                      // 回到顶层键，本段结束
    const m = line.match(/^ {2}([A-Za-z_][\w]*)\s*:\s*$/);
    if (m) ids.push(m[1]);
  }
  if (!ids.length) return { ids: [], error: `${phase} overlay 的 semantic_checks 解析出零条判据` };
  const known = ids.filter(id => id.startsWith(KNOWLEDGE_CHECK_PREFIX));
  // 本阶段 overlay 没有知识类判据 —— 不是错误，是这一阶段不判知识
  if (!known.length) return { ids: [], error: null, skip: true };
  return { ids: known, error: null };
}

export default async function preVerifier(ctx) {
  const phase = ctx?.phase;
  if (!phase || !ctx?.feature || !ctx?.projectRoot) return {};
  const source = SOURCE_OF_TRUTH[phase] ?? SOURCE_OF_TRUTH.plan;
  const { ids: checkIds, error, skip } = overlayCheckIds(ctx.projectRoot, phase);
  if (skip) return {};
  if (error) {
    return {
      promptFragments: [[
        '## 实例扩展知识判据（清单读取失败，须人工确认）',
        '',
        `无法确定本阶段该产出哪些判据结论：${error}。`,
        '',
        '**这不是「本阶段没有扩展判据」**——请打开本阶段的 overlay 自行确认判据清单，',
        `再按 \`${source.file}\` 里的判断逐项审查。`,
      ].join('\n')],
    };
  }

  const fragment = [
    '## 实例扩展知识判据（BLOCKER）',
    '',
    `本阶段的知识判断写在 **\`${source.file}\`**：${source.what}。`,
    '它是唯一真源——产物里的表是它的投影，两者按构造一致，读哪个都行。',
    '',
    '**判的是判断本身，不是它有没有被登记**（登记齐不齐、编号在不在册，机械层已经核过）：',
    '',
    '- **要求是不是本需求自己的设计**——把编号遮住，这句话还能指导编码吗？',
    '  它说清了落在哪个接口、存储键、字段或业务步骤上吗？换一个需求照样成立就是复述。',
    '- **不适用的依据站不站得住**——依据要能回查到本需求的事实，',
    '  「本需求无新增对外开放页面或接口」是依据，「不涉及」不是。',
    '- **模式候选的单元切分与信号**——单元粒度按模式索引的定义；',
    '  信号与反证要指向本需求真实存在的分支、步骤或交互，逐条拿材料核。',
    '  材料明写着的东西而反证说没有，点名那一条。',
    '',
    '**不要做的事**：不逐条对账、不出裁决表、不为每条结论找一段够长的引文。',
    '那些做法的产物是把真源里的字抄一遍，抄的量随材料条数涨，读者得到的判断不增加。',
    '有问题的那几条讲清楚为什么，没问题的不必逐条复述。',
    '',
    '### 输出要求（BLOCKER）',
    '',
    `在输出 YAML 的 \`checks:\` 中，为 ${checkIds.map(id => `\`${id}\``).join(' 与 ')} 各追加一条，`,
    '`details` 写你判出问题的那几条：是哪一条、问题是什么、依据是产物或材料里的什么事实。',
    '判不出问题就写清你按什么看过、看了哪几条。相应调整 `summary.total` 与计数。',
  ].join('\n');

  return { promptFragments: [fragment] };
}
