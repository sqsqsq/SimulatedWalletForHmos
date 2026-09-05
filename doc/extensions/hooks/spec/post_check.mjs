/**
 * spec 阶段 post_check 生命周期 hook（实例扩展 story）
 *
 * 作用：把**本阶段产物**与**宿主扩展章节**纳入 spec 阶段闭环判定。
 *   1. 本阶段三份产物：spec.md（代码要求）、AR/review.md（归档件·决策件）、
 *      AR/story.md（归档件·叙事主件，在阶段内按章写、按章落盘成文，登记态即判据）；
 *   2. §9 技术契约的结构完整性（core spec 模板未含，由 hooks/spec/author.md 指令驱动 AI 追加）；
 *   3. 知识判定的两个出口（§10 规约约束要求 / §11 设计模式候选登记）：独立成节、
 *      与 spec/knowledge-use.yaml 这份真源一致、命中集与 acceptance 的桥接键一致；
 *   4. 三条全文红线：禁用词 / 文档坐标 / 数值来源；
 *   5. story 前置流程契约（AR/story-flow.json）已收口且决策留痕齐备。
 *
 * 校验边界：**不校验结论真假**——文档坐标可被 AI 伪造，校验格式只给虚假的安全感。
 * 结论是否成立由 AI verifier 按名称回查源文件、以及开发的证据抽查关卡把关。
 * 唯一能机器验真假的是「数值来源」：标『上游约束』时读 SR/RR 原文核对该数值是否真实存在。
 *
 * 契约：stdin JSON ctx → stdout JSON result（同 hooks/coding/pre_check.mjs 演示）。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { scanBannedTerms, formatHits } from '../../skills/story/scripts/lint-rules.mjs';
import { flowProblems, isStoryFeature, storyProduced } from '../../skills/story/scripts/flow-check.mjs';
import { STATUS } from '../shared/evidence.mjs';
import { guard, gate } from '../shared/gate.mjs';
import { activeKnowledge, selfCheck } from '../shared/knowledge.mjs';
import {
  coverageProblems, readUse, renderZones, UseError, zoneProblems,
} from '../shared/knowledge-use.mjs';

const SECTIONS_DOC = 'doc/extensions/skills/story/templates/spec-sections.md';
const EVIDENCE_DOC = 'doc/extensions/skills/story/reference/evidence-rules.md';

function featuresDir(projectRoot) {
  try {
    const cfg = JSON.parse(fs.readFileSync(path.join(projectRoot, 'framework.config.json'), 'utf-8'));
    if (typeof cfg?.paths?.features_dir === 'string' && cfg.paths.features_dir.trim()) {
      return cfg.paths.features_dir.trim();
    }
  } catch {
    // 配置缺失/损坏时回落默认；不在 hook 里升级为错误
  }
  return 'doc/features';
}

/** 提取小节正文（到下一个 ##/### 标题为止） */
function sectionBody(lines, headingIdx) {
  const body = [];
  for (let i = headingIdx + 1; i < lines.length; i++) {
    if (/^#{2,3}\s/.test(lines[i])) break;
    body.push(lines[i]);
  }
  return body;
}

function isSeparatorRow(line) {
  return /^\|[\s:|-]+\|?\s*$/.test(line);
}

function rowCells(line) {
  // 不在转义竖线（\|）处切列
  return line.split(/(?<!\\)\|/).map(c => c.replace(/\\\|/g, '|').trim());
}

/** 模板占位残留：章节模板的待填处写作「{ … }」，出现即表示该节未填写 */
function hasTemplatePlaceholder(body) {
  return body.some(l => /\{\s*[^}]*[一-龥][^}]*\}/.test(l));
}

/** 小节是否已填：存在非空表格数据行，或存在非提示性正文行（如「不涉及：…」） */
function sectionFilled(body) {
  let sawSeparator = false;
  for (const raw of body) {
    const line = raw.trim();
    if (!line || line.startsWith('>') || line.startsWith('<!--')) continue;
    if (line.startsWith('|')) {
      if (isSeparatorRow(line)) {
        sawSeparator = true;
        continue;
      }
      if (sawSeparator && rowCells(line).some(c => c.length > 0)) return true;
      continue;
    }
    sawSeparator = false; // 离开表格块，下一张表须重新经过表头+分隔行
    return true; // 非表格、非提示的正文行（如「不涉及 + 依据」）
  }
  return false;
}

/**
 * 文档坐标扫描（evidence-rules §0 独立审计原则）。
 * spec 是可独立审计的文件——结论不挂 `spec §x`/`SR §x`/`RR §x`/`AR §x` 这类章节坐标，
 * 小节之间也不用「见 A5」互指；核对由 verifier 按名称回查与开发的证据抽查关卡完成。
 * 坐标是 AI 自己写的、可以伪造（写「≤1500 ms（SR §3.1）」而该章节根本没有时延数字），
 * 换个文档就失效，且会一路带进不含这些源文件的归档件。
 */
const DOC_COORD_RE = /(?:\bspec\s*§|\bSR\s*§|\bRR\s*§|\bAR\s*§|(?:见|指回|来源)\s*A[1-8]\b)/g;

function scanDocCoords(text) {
  const hits = [];
  const lines = text.split(/\r?\n/);
  let inFence = false;
  for (let i = 0; i < lines.length; i++) {
    if (/^\s*(```|~~~)/.test(lines[i])) {
      inFence = !inFence;
      continue;
    }
    if (inFence || lines[i].trim().startsWith('<!--')) continue;
    for (const m of lines[i].matchAll(DOC_COORD_RE)) {
      hits.push({ line: i + 1, coord: m[0].trim(), text: lines[i].trim().slice(0, 80) });
    }
  }
  return hits;
}

/**
 * 数值来源校验（spec-sections 红线：数值必须标来源类型）。
 * 阈值/时长一类数字必须三选一标明来源：上游约束 / 本工程设定 / 平台基线。
 * 标「上游约束」时读上游原文验证该数值真实存在——这是唯一能机器验真假的一环，
 * 也是唯一能抓住「造数字 + 挂假出处」的门禁。
 */
const NUMERIC_RE = /(\d+(?:\.\d+)?)\s*(ms|毫秒|秒|s|分钟|min|次)\b/gi;
const SOURCE_TAG_RE = /(上游约束|本工程设定|平台基线|无上游依据)/;
/** 单位同义词：回查上游时逐个试（上游可能写「30 分钟」而 spec 写「30 min」） */
const UNIT_ALIASES = {
  ms: ['ms', '毫秒'],
  毫秒: ['ms', '毫秒'],
  s: ['s', '秒'],
  秒: ['s', '秒'],
  min: ['min', '分钟'],
  分钟: ['min', '分钟'],
  次: ['次'],
};

function scanNumericSources(text, upstreamTexts) {
  const problems = [];
  const lines = text.split(/\r?\n/);
  let inFence = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (/^\s*(```|~~~)/.test(line)) {
      inFence = !inFence;
      continue;
    }
    if (inFence || line.trim().startsWith('<!--') || line.trim().startsWith('>')) continue;
    const nums = [...line.matchAll(NUMERIC_RE)];
    if (nums.length === 0) continue;
    if (!SOURCE_TAG_RE.test(line)) {
      problems.push(
        `第 ${i + 1} 行的数值「${nums.map(m => m[0]).join('、')}」未标来源类型` +
          `（须三选一：上游约束：<文档名> / 本工程设定，无上游依据 / 平台基线）：${line.trim().slice(0, 60)}`
      );
      continue;
    }
    if (/上游约束/.test(line)) {
      for (const m of nums) {
        const numeral = m[1];
        // 必须**带单位**回查：裸数字（`2`、`30`）会在上游任意位置碰巧命中
        // （`§2`、`2 个场景`、日期），带上单位才是在找同一个量
        const units = UNIT_ALIASES[m[2].toLowerCase()] ?? [m[2]];
        const found = upstreamTexts.some(t =>
          units.some(u => t.includes(`${numeral}${u}`) || t.includes(`${numeral} ${u}`))
        );
        if (!found) {
          problems.push(
            `第 ${i + 1} 行声称「上游约束」，但上游文档（SR/RR）中不存在数值「${numeral}」` +
              `——伪造出处，须改标「本工程设定，无上游依据」或回源核实：${line.trim().slice(0, 60)}`
          );
        }
      }
    }
  }
  return problems;
}


/** 按标题关键词定位章节（容忍编号差异：`## 9. 技术契约` / `## 技术契约` 均可） */
function findHeading(lines, titleRe) {
  return lines.findIndex(l => {
    const h = l.trim().match(/^(#{2,4})\s+(.*)$/);
    return h ? titleRe.test(h[2].replace(/^[\d.、\s]+/, '')) : false;
  });
}

/** 从某个二级标题起到下一个同级标题为止的行区间。 */
function sectionRange(lines, startIdx) {
  if (startIdx < 0) return null;
  const level = (lines[startIdx].trim().match(/^(#{2,4})/) ?? ['', '##'])[1].length;
  for (let i = startIdx + 1; i < lines.length; i++) {
    const h = lines[i].trim().match(/^(#{2,4})\s+/);
    if (h && h[1].length <= level) return { start: startIdx, end: i };
  }
  return { start: startIdx, end: lines.length };
}

/**
 * 知识判定的两个出口（BLOCKER）。
 *
 * 机械层只判**结构与集合**，不判内容对错：
 *   1. 两章独立成节，且不落在技术契约章的区间内（并进去会让守恒从按名退化成按号）；
 *   2. 编号粒度到条目级、编号在册（只写域前缀会让整域漏判照样放行）；
 *   3. 命中集与 acceptance 的 knowledge_rule 集一致。
 *
 * 「这条要求是不是本需求的设计」是语义判断，归 verifier——本函数不下这个结论。
 */
function knowledgeExitProblems(ctx, lines) {
  const problems = [];
  let knowledge;
  try {
    knowledge = activeKnowledge(ctx.projectRoot);
  } catch (e) {
    return [`激活知识派生失败：${e.message}`];
  }

  // 知识层自身的职责边界（规约不携带实现事实、知识不维护阶段路由）。
  // 放在这里跑：spec 是知识判定的起点，知识层坏了后面每个阶段都建在坏地基上。
  problems.push(...selfCheck(ctx.projectRoot, knowledge));

  const exitIdx = findHeading(lines, /规约约束要求/);
  const patternIdx = findHeading(lines, /设计模式候选/);
  const contractIdx = findHeading(lines, /技术契约/);
  const contractRange = sectionRange(lines, contractIdx);

  if (exitIdx === -1) {
    return [
      '缺「规约约束要求」章——判定产生的代码要求没有落点，到编码那里就等于不存在。'
      + `形态见 ${SECTIONS_DOC}：这一章的正文由 spec/knowledge-use.yaml 生成，不手写。`,
    ];
  }
  if (patternIdx === -1) {
    problems.push('缺「设计模式候选登记」章——零候选是正常结论，但要显式登记适用单元与理由，'
      + '空着分不清「判过了不需要」与「压根没想这件事」');
  }
  // 独立成节：不得落在技术契约章的区间内
  for (const [idx, name] of [[exitIdx, '规约约束要求'], [patternIdx, '设计模式候选登记']]) {
    if (idx >= 0 && contractRange && idx > contractRange.start && idx < contractRange.end) {
      problems.push(`「${name}」并进了技术契约章——三章各回答一个问题，须独立成节：`
        + '契约章登记「有什么」，要求章说「必须满足什么」，候选章说「可选什么」。');
    }
  }

  // 判断的真源是 knowledge-use.yaml；§10/§11 是它的投影。
  //
  // 此前两章的 markdown 表既是给人读的，也是机器要解析回结构的真源，于是每条判据
  // 都先要「解析得动人写的表」——表头找列、单元格剥装饰、编号抽正则，而作者每次手填
  // 都可能把表写歪一点点。现在作者只编辑 YAML，投影由生成器写；投影与 YAML 对不上时，
  // 错的一定是投影。
  let use;
  try {
    use = readUse(ctx.projectRoot, ctx.feature);
  } catch (e) {
    if (e instanceof UseError) return [...problems, e.message];
    throw e;
  }
  const specText = lines.join(String.fromCharCode(10));
  problems.push(...coverageProblems(ctx.projectRoot, knowledge, use, specText));
  if (problems.length) return problems;      // 判断本身不成立时，投影核了也没有意义

  problems.push(...zoneProblems(ctx.projectRoot, specText, renderZones(knowledge, use)));

  // 命中且产生代码要求的那些，要在 acceptance 里有对应验收条目
  const byId = new Map(knowledge.entries.map(e => [e.id, e]));
  const specIds = new Set(use.constraints
    .filter(r => r.applicable === true && !byId.get(String(r.id ?? '').trim())?.reviewAction)
    .map(r => String(r.id ?? '').trim()));
  problems.push(...acceptanceCoverage(ctx, specIds));
  return problems;
}

/**
 * 命中条目在 acceptance 里有没有对应验收条目（机械收口）。
 *
 * **这是集合一致性，不是「知识已被应用」**——后者是语义判断，机械层越权下语义结论，
 * 就会变成「写了字就算做了」。
 */
function acceptanceCoverage(ctx, specIds) {
  const problems = [];
  const featureDir = path.join(ctx.projectRoot, featuresDir(ctx.projectRoot), ctx.feature);

  // **不和第二份登记表比对**：spec 阶段的判定结论只有 knowledge-use.yaml 一份。
  // 另设一份独立的判定记录文件，会让同一条结论有两处写法、两处判定，
  // 评审者看到互相矛盾的结论时无从知道哪个是准的。归档件的符合性附录由 writer 直接写。

  // acceptance 侧：知识义务的验证要求单源（下游 ut/testing 靠它分派）
  const accPath = path.join(featureDir, 'acceptance.yaml');
  if (fs.existsSync(accPath)) {
    const raw = fs.readFileSync(accPath, 'utf-8');
    const accIds = new Set([...raw.matchAll(/knowledge_rule\s*:\s*["']?([A-Z][A-Z0-9]{1,7}-\d{2})/g)].map(m => m[1]));
    if (accIds.size || specIds.size) {
      const missing = [...specIds].filter(id => !accIds.has(id));
      if (missing.length) {
        problems.push(`这些条目有代码要求但 acceptance.yaml 没有对应验收条目：${missing.join('、')}`
          + '——每条要求要有一条带 knowledge_rule 的 criteria，'
          + '它是 ut/testing 找到「该覆盖哪个场景」的桥（分派本身由 contracts 里 must.verify 定），'
          + '缺了下游就无从覆盖');
      }
      const unknown = [...accIds].filter(id => !specIds.has(id));
      if (unknown.length) {
        problems.push(`acceptance.yaml 的 knowledge_rule 指向了 spec 里没有要求的条目：${unknown.join('、')}`);
      }
    }
  }
  return problems;
}

/**
 * spec 宿主扩展章节（core 模板未含，由 hooks/spec/author.md 指令驱动 AI 追加）：
 *   §9 技术契约 —— 给下游 AI：plan 据此编码、test-plan 据此出用例
 * 模板见 skills/story/templates/spec-sections.md。
 *
 * 判定结论（命中/不命中）不在 spec：它零条代码要求，纯粹是给评审者的完备性回显，
 * 与「spec 只装与最终代码有关的内容」相悖——它落在归档件「影响面与合规」章的判定表里，
 * 由叙事件承载、`story-build check` 核。
 * spec 只收判定**产生的代码要求**（§10）与**模式候选登记**（§11），两者独立成章。
 * 结论是不是本需求的设计，由 verifier 对着真源与材料判——那是判断，脚本判不了。
 */
/**
 * §9 某一节里表外的第一段正文，没有就返回 null。
 *
 * 这一节是给下游 AI 的技术契约：plan 据它编码、test-plan 据它出用例。
 * 表外那几段承载的通常是实现取舍与待定项——它们有自己的去处，进了契约
 * 只会让下游读到一句「由 plan 决定」。
 * 「不涉及：<依据>」独行豁免：那是空节规则的既有形态。
 */
function strayProse(body) {
  for (const raw of String(body ?? '').split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('|') || line.startsWith('#')) continue;
    if (/^不涉及[:：]\s*\S/.test(line)) continue;
    if (/^[-*+]\s/.test(line) || /^\d+[.、)]\s/.test(line)) continue;   // 列表另说
    if (line.startsWith('<!--')) continue;
    return line.replace(/^>\s*/, '');
  }
  return null;
}

const SPEC_EXT_SECTIONS = [
  { ch: '9 技术契约', title: /技术契约/, subs: [['端云接口', /端云接口/], ['数据存储', /数据存储/], ['配置项', /配置项/], ['埋点', /埋点/], ['依赖变更', /依赖变更/]] },
];

export default guard('spec', async (ctx) => {
  const featureRoot = path.join(ctx.projectRoot, featuresDir(ctx.projectRoot), ctx.feature);
  const rel = path.join(featuresDir(ctx.projectRoot), ctx.feature, 'spec', 'spec.md');
  const specPath = path.join(featureRoot, 'spec', 'spec.md');
  const fix = `处置：按 ${SECTIONS_DOC} 补齐 spec 宿主扩展章节（结论写法见 ${EVIDENCE_DOC}），然后重跑 harness --phase spec。`;

  // spec 本身缺失由 framework 的 check-spec 负责，本 hook 只管宿主扩展部分。
  // 但扩展判据一条都没跑成，要留痕说明——「没报错」不等于「查过了」。
  if (!fs.existsSync(specPath)) {
    return gate(ctx, { skipped: [{ what: 'spec 宿主扩展章节与知识出口', why: 'spec.md 还没生成' }] });
  }

  const text = fs.readFileSync(specPath, 'utf-8').replace(/^﻿/, '');
  const lines = text.split(/\r?\n/);
  const problems = [];
  const skipped = [];

  // 场景探针：走过 /story 的 feature 才有流程契约。
  // 本 hook 的检查分两类——**扩展新增的结构要求**（三份产物、§9 技术契约、术语解释列、
  // 归档件红线）只在 story 场景成立，对「口述一个需求直接跑 spec」的用法是凭空多出来的
  // 硬阻断；**知识判定的两个出口**（约束要求章、模式候选登记）与 story 无关，对所有人生效
  // ——判定产生的代码要求不进 spec，编码那里就拿不到。
  const isStory = isStoryFeature(featureRoot);

  // ---- story 前置流程契约已收口 ----
  problems.push(...flowProblems(featureRoot));

  // ---- 三份产物齐备：第三份是叙事件（story 专属）----
  // spec 是一次 pass 产出 spec.md / AR/review.md / AR/story.md，三者事实同源。
  // 前两份由本文件的章节判据与 decisions 渲染管，第三份查登记态——
  // 登记前会重跑 story-build check，登记成功即九项判据都过了。
  problems.push(...storyProduced(featureRoot));

  // ---- 两章的结构完整性：章在、小节齐、非空、无模板占位（story 专属）----
  // 这两章是扩展在 core 模板之上新增的，只跑原生 spec 的使用者从没被要求写过。
  if (isStory) {
    for (const { ch, title, subs } of SPEC_EXT_SECTIONS) {
      const chIdx = findHeading(lines, title);
      if (chIdx === -1) {
        problems.push(`缺少宿主扩展章节「§${ch}」（core spec 模板未含，须在验收标准之后追加）`);
        continue;
      }
      for (const [name, subRe] of subs) {
        const subIdx = findHeading(lines, subRe);
        if (subIdx === -1 || subIdx < chIdx) {
          problems.push(`§${ch} 缺少小节「${name}」（小节不得删；不涉及也须写「不涉及 + 一句依据」）`);
          continue;
        }
        const body = sectionBody(lines, subIdx);
        if (!sectionFilled(body)) {
          problems.push(`§${ch}「${name}」未填写（须给出事实或「不涉及 + 一句依据」）`);
        } else if (hasTemplatePlaceholder(body)) {
          problems.push(`§${ch}「${name}」残留模板占位「{ … }」——须替换为实际结论`);
        } else {
          const stray = strayProse(body);
          if (stray) {
            problems.push(`§${ch}「${name}」表外有段落（「${stray.slice(0, 20)}…」）`
              + '——这一节要么是一张表，要么是一行「不涉及：<依据>」。'
              + '约定进表格；实现取舍写 spec/notes.md；要人拍板的写决策件');
          }
        }
      }
    }
  }

  // ---- 知识判定的两个出口 ----
  // 出口按**命中条目**派生，不为任何域预留固定小节——预留小节就是把域清单硬编码换个地方存在。
  problems.push(...knowledgeExitProblems(ctx, lines));

  // ---- 术语映射表：业务名词须有解释（story 专属）----
  // 「解释」列是扩展在 core 模板的 §0 之上追加的，附录 A 只留一句索引。
  // 判据不用白名单——**权威模块落在 in_scope_modules 里的行就是本需求的业务词汇**，
  // 评审者必须能查到；权威模块是被消费的基础能力（账号 / 通用 UI / 工具）时可留「—」。
  // 数据全在 spec 自己里，加约束文件或改架构都不会让这条判据失效。
  if (isStory) {
    const scopeBlock = text.match(/in_scope_modules:\s*\n((?:\s*-\s*.+\n)+)/);
    const inScope = new Set(
      (scopeBlock?.[1] ?? '')
        .split(/\r?\n/)
        .map(l => l.match(/^\s*-\s*(.+?)\s*$/)?.[1])
        .filter(Boolean)
    );
    const mapIdx = findHeading(lines, /术语映射表/);
    if (mapIdx !== -1 && inScope.size > 0) {
      const rows = [];
      let sawSep = false;
      let headerCells = null;
      for (let i = mapIdx + 1; i < lines.length; i++) {
        const l = lines[i].trim();
        if (/^#{2,3}\s/.test(l)) break;
        if (!l.startsWith('|')) { sawSep = false; continue; }
        if (isSeparatorRow(l)) { sawSep = true; continue; }
        const cells = rowCells(l);
        if (!sawSep) { headerCells = cells; continue; }
        rows.push(cells);
      }
      // rowCells 对带行尾竖线的行会多出末位空串，故「解释」列须按表头定位而非按末位索引。
      // 框架 parser（markdown-parser.parsePipeRow）要求数据行带行尾竖线才能解析，两者必须兼容。
      // 表头与数据行同为「行首空串 + 各列 +（行尾空串）」结构，表头索引可直接用于数据行。
      const explainIdx = headerCells
        ? headerCells.findIndex(h => h.trim().includes('解释'))
        : -1;
      const moduleIdx = headerCells
        ? headerCells.findIndex(h => h.trim().includes('权威模块'))
        : 2;
      const business = rows.filter(c => inScope.has((c[moduleIdx] ?? '').trim()));
      const noExplain = business.filter(c => {
        const last = (c[explainIdx] ?? '').trim();
        return !last || last === '—' || /^\[[ x]\]$/.test(last);
      });
      if (rows.length > 0 && noExplain.length > 0) {
        problems.push(
          `术语映射表有 ${noExplain.length} 个业务名词没写「解释」：${noExplain.map(c => (c[1] ?? c[0] ?? '').trim()).join('、')}` +
            '——它们的权威模块在本需求 Scope 内，是本需求的业务词汇；评审叙事件的术语表从这里抄，' +
            '漏了评审者在归档件里就查不到这个词。基础能力类术语可留「—」'
        );
      }
    }
  }

  // ---- 三条全文红线（词表 SSOT：skills/story/scripts/lint-rules.mjs · story 专属）----
  // 这三条的作业指导随 story 专属注入件下发；未走 /story 的使用者只在通用注入件里读到
  // 建议形态，不该在这里被硬阻断——**注入指导与硬阻断是两件事**。
  if (isStory) {
    // 客户端语境：spec 是编码与评审件的共同上游，源头不放行才不会一路带下去
    const bannedHits = scanBannedTerms(text);
    if (bannedHits.length > 0) {
      problems.push(
        `含客户端语境禁用词 ${bannedHits.length} 处（服务器侧词汇，单独使用也算）：${formatHits(bannedHits.slice(0, 3), 'banned').join('；')}` +
          (bannedHits.length > 3 ? `；…另 ${bannedHits.length - 3} 处` : '')
      );
    }

    // 独立审计：不写文档坐标（详见 evidence-rules 独立审计原则）
    const coordHits = scanDocCoords(text);
    if (coordHits.length > 0) {
      problems.push(
        `含文档坐标 ${coordHits.length} 处（spec 须可独立审计；改用事物的名字，如「见管理台功能开关 feature_entry_enabled」）：` +
          coordHits.slice(0, 3).map(h => `第 ${h.line} 行「${h.coord}」`).join('、') +
          (coordHits.length > 3 ? `…另 ${coordHits.length - 3} 处` : '')
      );
    }

    // 数值来源：读 SR/RR/AR 原文验证「上游约束」类数值真实存在（唯一能机器验真假的一环）。
    // **排除已被 archive 覆盖的 AR/design.md**——archive 会用 story.md 覆盖它，覆盖后它不再是
    // 上游输入件而是本需求自己的产物；拿它回查等于让产物给自己背书——SR/RR 里没有的数值，
    // 会因为被覆盖的 AR 里有（那些值本就是从 spec 合成来的）而逃过校验。
    const upstreamTexts = ['SR/design.md', 'RR/prd.md', 'AR/design.md']
      .map(p => path.join(featureRoot, p))
      .filter(p => fs.existsSync(p))
      .map(p => fs.readFileSync(p, 'utf-8'))
      .filter(t => !/^>\s*源摘要：/m.test(t)); // story.md 的特征行；AR 提取件不会有
    const numericProblems = scanNumericSources(text, upstreamTexts);
    numericProblems.slice(0, 5).forEach(p => problems.push(p));
    if (numericProblems.length > 5) problems.push(`另有 ${numericProblems.length - 5} 处数值来源问题`);
  }

  return gate(ctx, {
    problems,
    skipped,
    checks: [
      { id: 'knowledge_exit_structure', status: problems.length ? STATUS.FAIL : STATUS.PASS, detail: `问题 ${problems.length} 条` },
    ],
    inputs: [specPath],
    fix: `产物：spec.md（${rel}）。${fix}`,
  });
});

