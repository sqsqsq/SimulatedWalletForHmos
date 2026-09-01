/**
 * pre_verifier —— 把本阶段的知识判定**全集**注入 verifier 的必答清单。
 *
 * ## 为什么是收窄后的全集
 *
 * 机械层只判得了「有没有」和「是不是照抄」。「这句话是不是本需求的设计」是语义判断，
 * 只有 verifier 能下——所以每一行都要送去裁决。
 *
 * 曾经的做法是只把**风险标记命中**的行送去裁（相似度高、没有专名），结果是
 * 「可信专名 + 低相似改写」整类逃逸：加一个自造名词、把原文换个说法，两个标记都不命中，
 * 于是那一行根本没人裁。所以本模块的判据定死为：
 *
 * > **风险标记只决定排序，不决定谁受裁决。**
 *
 * 全集：spec 阶段是 §10 表的每一行 + §11 候选表的每一行；plan 之后是契约实体上的每条 `must`
 * 与每个模式投影——一行不落。这个阶段的判定只有这一份，所以裁一次就够。
 * 集合的派生在 `verdict-set.mjs`，与门禁核对用同一份口径——两边各存一份就会「注入 14 行、
 * 只核 11 行」。
 *
 * ## 注入不等于执行
 *
 * 只注入清单、不校验 verifier 是否照做会漏：清单里的条目一条没裁，harness 照收 PASS。
 * 所以清单里显式要求把裁决表写进**报告文件**，闭环回填那次运行由各阶段
 * post_check 核对——框架的 post_verifier 钩子在 verifier **之前**触发，读不到它的报告。
 *
 * 契约：stdin JSON ctx → stdout JSON { promptFragments: string[] }。
 */
import * as path from 'node:path';
import { adjudicationSet } from './verdict-set.mjs';
import { activeKnowledge, paraphraseSources } from './knowledge.mjs';
import { classify } from './paraphrase.mjs';
import { extensionRoot, featureRoot, lines, readTextOrNull } from './paths.mjs';
import { readContracts } from './contracts.mjs';

/**
 * 知识类语义判据的命名前缀。
 *
 * 用**命名约定**而不是一份 id 清单来认它们：清单要跟着 overlay 改，改漏了就静默失效；
 * 前缀是数据形态，新增一条知识判据自动被认。同一份 overlay 里的其它判据
 * （叙述质量、上游覆盖等）不是逐行裁决类，不进本清单。
 */
const KNOWLEDGE_CHECK_PREFIX = 'knowledge_';

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
    if (!/^\s/.test(line)) break;                       // 回到顶层键，本块结束
    const m = line.match(/^ {2}([A-Za-z_][\w]*)\s*:\s*$/);
    if (m) ids.push(m[1]);
  }
  if (!ids.length) return { ids: [], error: `${phase} overlay 的 semantic_checks 解析出零条判据` };
  const known = ids.filter(id => id.startsWith(KNOWLEDGE_CHECK_PREFIX));
  if (!known.length) {
    // 本阶段 overlay 没有知识类判据——不是错误，是这一阶段不做逐行裁决
    return { ids: [], error: null, skip: true };
  }
  return { ids: known, error: null };
}

/** 本需求自己的名字：spec 技术契约表首列 + 契约实体名。只作排序信号，不作判定。 */
function ownTerms(projectRoot, feature, contracts) {
  const terms = new Set();
  const specText = readTextOrNull(path.join(featureRoot(projectRoot, feature), 'spec', 'spec.md'));
  if (specText !== null) {
    const rows = lines(specText);
    const start = rows.findIndex(l => /^#{2,4}\s+.*技术契约/.test(l.trim()));
    if (start >= 0) {
      for (let i = start + 1; i < rows.length; i++) {
        const s = rows[i].trim();
        if (/^#{2}\s/.test(s)) break;
        if (!s.startsWith('|')) continue;
        const first = s.replace(/^\||\|$/g, '').split('|')[0]?.trim() ?? '';
        const name = first.replace(/[`*]/g, '').replace(/[（(][^）)]*[）)]\s*$/, '').trim();
        if (name && !/^[-—:| ]*$/.test(name) && name.length >= 2) terms.add(name);
      }
    }
  }
  for (const kind of ['data_models', 'interfaces', 'components', 'resource_keys']) {
    for (const it of Array.isArray(contracts?.[kind]) ? contracts[kind] : []) {
      const n = typeof it === 'string' ? it : String(it?.name ?? it?.class ?? it?.key ?? '');
      if (n) terms.add(n);
      for (const f of Array.isArray(it?.fields) ? it.fields : []) {
        const fn = typeof f === 'string' ? f : String(f?.name ?? '');
        if (fn) terms.add(fn);
      }
    }
  }
  return [...terms];
}

/**
 * 必答集的行 → 带排序信号的行。
 *
 * 排序信号只对「有规约原文可比」的行算得出来（条目判定与冻结义务）；
 * 域级判定、模式候选、项目知识复用没有可比原文，标 CLEAN——**它们照样要裁**。
 */
function withSignals(rows, knowledge, terms) {
  const comparable = new Set(['规约判定', '冻结义务']);
  return rows.map(r => {
    if (!comparable.has(r.source)) {
      return { ...r, verdict: 'CLEAN', reasons: [], similarity: 0 };
    }
    const c = classify(r.text, paraphraseSources(knowledge, r.key), terms);
    return {
      ...r,
      key: r.source === '规约判定' ? `${r.key}（${r.hit ? '命中' : '不命中'}）` : r.key,
      verdict: c.verdict,
      reasons: c.reasons,
      similarity: c.similarity,
    };
  });
}

export default async function preVerifier(ctx) {
  const phase = ctx?.phase;
  if (!phase || !ctx?.feature || !ctx?.projectRoot) return {};
  const { ids: checkIds, error: overlayError, skip } = overlayCheckIds(ctx.projectRoot, phase);
  if (skip) return {};
  if (overlayError) {
    return {
      promptFragments: [[
        '## 实例扩展语义判据（清单读取失败，须人工全量裁决）',
        '',
        `无法确定本阶段该产出哪些判据结论：${overlayError}。`,
        '',
        '**这不是「本阶段没有扩展判据」**——请打开本阶段的 overlay 自行确认判据清单，',
        '并对本阶段产物里的每条知识判定结论逐行裁「设计 / 复述 / 不适用」。',
      ].join('\n')],
    };
  }

  let knowledge;
  try {
    knowledge = activeKnowledge(ctx.projectRoot);
  } catch (e) {
    return {
      promptFragments: [[
        '## 实例扩展必答清单（生成失败，须人工全量裁决）',
        '',
        `无法从激活清单派生知识条目：${e.message}`,
        '',
        '**不要因为清单生成失败就跳过裁决**：请自己打开激活的规约与本阶段产物，',
        '逐条判断每个判定结论是本需求的设计还是规约原文的复述，并逐条输出结论。',
      ].join('\n')],
    };
  }

  const { contracts } = readContracts(ctx.projectRoot, ctx.feature);
  const terms = ownTerms(ctx.projectRoot, ctx.feature, contracts);

  const set = adjudicationSet(ctx.projectRoot, ctx.feature, phase, knowledge);
  if (set.error) {
    return {
      promptFragments: [[
        '## 实例扩展必答清单（生成失败，须人工全量裁决）',
        '',
        `无法派生本阶段的必答集：${set.error}`,
        '',
        '**不要因为清单生成失败就跳过裁决**：请自己打开本阶段产物里的知识判定登记，',
        '逐条判断每个结论是本需求的设计还是规约原文的复述，并把裁决表写进报告文件。',
      ].join('\n')],
    };
  }
  const rows = withSignals(set.rows, knowledge, terms);

  if (!rows.length) {
    return {
      promptFragments: [[
        '## 实例扩展必答清单',
        '',
        '本阶段没有派生出任何知识判定行。**这本身就是一个要裁决的结论**：',
        '请确认是「本需求确实没有命中任何规约条目」（那么归档件与 spec 里应有显式的不命中依据），',
        '还是「判定漏做了」。把结论写进 checks。',
      ].join('\n')],
    };
  }

  // 排序：复述嫌疑高的排前面，方便先看最可能有问题的。
  // **排序不改变覆盖面**——下面每一行都要裁。
  const order = { PURE_COPY: 0, SUSPECT: 1, CLEAN: 2 };
  rows.sort((a, b) => (order[a.verdict] - order[b.verdict]) || (b.similarity - a.similarity));

  // **不注入被检文本**：文本一旦在提示词里，裁决就会退化成把它抄进证据列——
  // 实测整份清单的证据只有十几种字符串、全是被检文本的回声，零条「落点错/漏了」。
  // 这里只给「裁哪一行」，原文让 verifier 自己去产物里读：读过才可能给出真引文。
  const table = [
    '| # | 来源 | 条目 | 机械信号 | 你的裁决（设计 / 复述 / 不适用）+ 引文 |',
    '|---|---|---|---|---|',
    ...rows.map((r, i) =>
      `| ${i + 1} | ${r.source} | ${r.key || '—'} | ${signal(r)} | |`),
  ];

  const fragment = [
    '## 实例扩展必答清单（逐行裁决，BLOCKER）',
    '',
    `本阶段共 **${rows.length}** 行知识判定结论。**每一行都要裁决**，包括机械信号为「无」的那些。`,
    '',
    '**机械信号只是排序提示，不是筛选条件**：',
    '「原文子串」是机械可判的复制；「相似度」「无专名」只说明这一行值得先看。',
    '信号为「无」不代表这行没问题——「加个自造名词 + 换个说法」正好两个信号都不命中，',
    '而那恰恰是最需要人判断的情况。',
    '',
    '**判据**：这句话是不是**本需求自己的设计**？',
    '',
    '- **设计** —— 它说清了这条要求在本需求里落到哪个接口、存储键、字段或业务步骤上，',
    '  把编号遮住也能指导编码；',
    '- **复述** —— 它只是规约原文的改写或同义转述，换一个需求这句话照样成立；',
    '- **不适用** —— 该条目在本需求下确实不涉及，且给出了具体依据（「不涉及」三个字不算依据）。',
    '',
    ...table,
    '',
    '### 输出要求（BLOCKER）',
    '',
    `在输出 YAML 的 \`checks:\` 中，为 ${checkIds.map(id => `\`${id}\``).join(' 与 ')} 各追加一条，`,
    '`details` 里**逐行**给出「行号 → 裁决 → 引文」，行数与上表一致；',
    '有任一行判「复述」即该条 `status: FAIL`。相应调整 `summary.total` 与计数。',
    '',
    '**引文要求（BLOCKER）**：引文须是**目标产物里的原话**，连续 12 字以上，能在产物里检索到。',
    '上表故意不给被检文本——把清单里的字抄进引文列不算裁决，那只是回声。',
    '打开产物、找到那一行、把你据以判断的原文抄下来；找不到落点就是判「复述」的依据。',
    '',
    '**裁决表必须落进本阶段 `reports/` 下的 verifier 报告**，固定表头 `| 编号 | 裁决 | 证据 |`，',
    '一行一条，编号照上表原样写。落盘方式看你的宿主，两种都要照顾到：',
    '报告若由你自己写文件，就写成 `reports/verifier.report.md`；',
    '若你的宿主由钩子代写（钩子取的是子 agent 的**终态消息**），',
    '就把整张表放在最后一条回复里——不要分段发、不要放在中间某条消息里、不要说「见上文」。',
    '两种情形下门禁读的都是那份报告的正文：没落进去的表等于不存在，缺行即 BLOCKER。',
    '只写在 YAML 输出里不算——那份输出不落盘。',
    '',
    '**漏裁与判 PASS 是两回事**：没裁的行不要留空、不要合并成一句「整体符合」——',
    '实测出现过整份清单一条没裁而门禁照收 PASS，那之后这条收口就成了硬要求。',
  ].join('\n');

  return { promptFragments: [fragment] };
}

function signal(row) {
  if (row.verdict === 'PURE_COPY') return '**原文子串**';
  if (!row.reasons.length) return '无';
  return row.reasons.join('；');
}
