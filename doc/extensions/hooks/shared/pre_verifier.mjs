/**
 * pre_verifier —— 把本阶段的知识判定**全集**注入 verifier 的必答清单。
 *
 * ## 为什么必须是全集
 *
 * 机械层只判得了「有没有」和「是不是照抄」。「这句话是不是本需求的设计」是语义判断，
 * 只有 verifier 能下——所以每一行都要送去裁决。
 *
 * 上一轮的做法是只把**风险标记命中**的行送去裁（相似度高、没有专名），结果是
 * 「可信专名 + 低相似改写」整类逃逸：加一个自造名词、把原文换个说法，两个标记都不命中，
 * 于是那一行根本没人裁。所以本模块的判据定死为：
 *
 * > **风险标记只决定排序，不决定谁受裁决。**
 *
 * 清单里的每一行都要有裁决，包括看起来最干净的那些。
 *
 * ## 注入不等于执行
 *
 * 只注入清单、不校验 verifier 是否照做，实测会漏（曾出现整整 12 条一条没裁而 harness
 * 照收 PASS）。所以清单里显式要求逐条输出，收口由测试域的回归脚本核对 verifier 报告——
 * 框架的 post_verifier 钩子在 verifier **之前**触发，读不到它的报告，指望不上。
 *
 * 契约：stdin JSON ctx → stdout JSON { promptFragments: string[] }。
 */
import * as path from 'node:path';
import { activeKnowledge, paraphraseSources } from './knowledge.mjs';
import { classify } from './paraphrase.mjs';
import { extensionRoot, featureRoot, lines, readTextOrNull } from './paths.mjs';
import { readContracts, readFreeze } from './freeze.mjs';

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

/** spec 的两个出口 + 归档件判定登记：本阶段要裁的全集。 */
function specRows(ctx, knowledge, terms) {
  const rows = [];
  const specText = readTextOrNull(path.join(featureRoot(ctx.projectRoot, ctx.feature), 'spec', 'spec.md'));
  if (specText !== null) {
    collectTableRows(specText, /规约约束要求/, ['编号', '要求']).forEach(({ cells, headers }) => {
      const id = pick(cells, headers, '编号').replace(/[`*]/g, '').trim();
      if (!/^[A-Z][A-Z0-9]{1,7}-\d{2}$/.test(id)) return;
      rows.push(mkRow('spec 约束要求', id, pick(cells, headers, '要求'), knowledge, terms));
    });
    collectTableRows(specText, /设计模式候选/, ['适用单元', '候选']).forEach(({ cells, headers }) => {
      const unit = pick(cells, headers, '适用单元');
      if (!unit || /^\{.*\}$/.test(unit)) return;
      rows.push({
        source: '模式候选登记',
        key: unit,
        text: `${pick(cells, headers, '候选')}｜${pick(cells, headers, '信号')}`,
        verdict: 'CLEAN',
        reasons: [],
        similarity: 0,
      });
    });
  }
  const regPath = path.join(featureRoot(ctx.projectRoot, ctx.feature), 'AR', 'story-src', 'knowledge.json');
  const regRaw = readTextOrNull(regPath);
  if (regRaw !== null) {
    try {
      const reg = JSON.parse(regRaw.replace(/^﻿/, ''));
      for (const c of Array.isArray(reg.constraints) ? reg.constraints : []) {
        rows.push(mkRow('归档件判定', String(c?.id ?? ''), String(c?.conclusion ?? ''), knowledge, terms,
          c?.hit === true ? '命中' : '不命中'));
      }
    } catch { /* 解析失败由 post_check 报，这里不重复 */ }
  }
  return rows;
}

function freezeRows(obligations, patterns, knowledge, terms, label) {
  const rows = [];
  for (const ob of obligations) {
    rows.push(mkRow(label, String(ob.rule ?? ''), String(ob.obligation ?? ''), knowledge, terms));
  }
  for (const p of patterns) {
    if (p.selected !== true) continue;
    const roles = p.roles && typeof p.roles === 'object' ? p.roles : {};
    rows.push({
      source: '模式冻结',
      key: String(p.pattern_id ?? ''),
      text: `实例 ${p.instance ?? '—'}｜角色 ${Object.entries(roles).map(([k, v]) => `${k}=${v}`).join('、') || '—'}`,
      verdict: 'CLEAN',
      reasons: [],
      similarity: 0,
    });
  }
  return rows;
}

function mkRow(source, id, text, knowledge, terms, extra) {
  const c = classify(text, paraphraseSources(knowledge, id), terms);
  return {
    source,
    key: extra ? `${id}（${extra}）` : id,
    text,
    verdict: c.verdict,
    reasons: c.reasons,
    similarity: c.similarity,
  };
}

function collectTableRows(text, headingRe, headerKeywords) {
  const rows = lines(text);
  const start = rows.findIndex(l => headingRe.test(l.trim()) && /^#{2,4}\s/.test(l.trim()));
  if (start < 0) return [];
  const level = (rows[start].trim().match(/^(#{2,4})/) ?? ['', '##'])[1].length;
  let headers = null;
  const out = [];
  for (let i = start + 1; i < rows.length; i++) {
    const h = rows[i].trim().match(/^(#{2,4})\s+/);
    if (h && h[1].length <= level) break;
    const s = rows[i].trim();
    if (!s.startsWith('|')) continue;
    const cells = s.replace(/^\||\|$/g, '').split('|').map(c => c.trim());
    if (!headers) {
      if (headerKeywords.every(k => cells.some(c => c.includes(k)))) headers = cells;
      continue;
    }
    if (cells.every(c => /^[-: ]*$/.test(c))) continue;
    if (cells.some(c => /^\{.*\}$/.test(c))) continue;
    out.push({ cells, headers });
  }
  return out;
}

function pick(cells, headers, keyword) {
  const i = (headers ?? []).findIndex(h => h.includes(keyword));
  return i >= 0 && i < cells.length ? cells[i] : '';
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
  const { obligations, patterns } = readFreeze(contracts);

  let rows;
  if (phase === 'spec') {
    rows = specRows(ctx, knowledge, terms);
  } else if (phase === 'plan') {
    rows = freezeRows(obligations, patterns, knowledge, terms, '冻结义务');
  } else {
    rows = freezeRows(obligations, patterns, knowledge, terms, '冻结义务（下游留证）');
  }

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

  const table = [
    '| # | 来源 | 条目 | 被检文本 | 机械信号 | 你的裁决（设计 / 复述 / 不适用）+ 证据 |',
    '|---|---|---|---|---|---|',
    ...rows.map((r, i) =>
      `| ${i + 1} | ${r.source} | ${r.key || '—'} | ${cell(r.text)} | ${signal(r)} | |`),
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
    '`details` 里**逐行**给出「行号 → 裁决 → 证据」，行数与上表一致；',
    '有任一行判「复述」即该条 `status: FAIL`。相应调整 `summary.total` 与计数。',
    '',
    '**漏裁与判 PASS 是两回事**：没裁的行不要留空、不要合并成一句「整体符合」——',
    '实测出现过整份清单一条没裁而门禁照收 PASS，那之后这条收口就成了硬要求。',
  ].join('\n');

  return { promptFragments: [fragment] };
}

function cell(text) {
  const s = String(text ?? '').replace(/\r?\n/g, ' ').replace(/\|/g, '\\|').trim();
  return s.length > 90 ? `${s.slice(0, 90)}…` : (s || '（空）');
}

function signal(row) {
  if (row.verdict === 'PURE_COPY') return '**原文子串**';
  if (!row.reasons.length) return '无';
  return row.reasons.join('；');
}
