/**
 * spec 阶段 post_check 生命周期 hook（实例扩展 story）
 *
 * 作用：把**本阶段三份产物**与**宿主扩展章节**纳入 spec 阶段闭环判定。
 *   1. 三份产物齐备：spec.md（代码要求）/ AR/review.md（归档件·决策件）/ AR/story.md（归档件·叙事主件）；
 *   2. §9 技术契约的结构完整性（core spec 模板未含，由 on_context_load.md 指令驱动 AI 追加）；
 *   3. 合规判定落 spec 的那部分（§7 UX 适配要求）确实写了；
 *   4. 三条全文红线：禁用词 / 文档坐标 / 数值来源。
 *
 * 两份归档件自身的结构、一致性与自包含红线由 skills/story/scripts/merge-story.mjs --check 负责，本 hook 只查在不在。
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
 * 坐标是 AI 自己写的、可以伪造（实测出现过「≤1500 ms（SR §3.1）」而该章节根本没有时延数字），
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

/**
 * spec 宿主扩展章节（core 模板未含，由 hooks/spec/on_context_load.md 指令驱动 AI 追加）：
 *   §9 技术契约 —— 给下游 AI：plan 据此编码、test-plan 据此出用例
 * 模板见 skills/story/templates/spec-sections.md。
 *
 * 曾有过 §10 合规与兼容自检，已迁出：那两张判定表零条代码要求，纯粹是给评审者的完备性回显，
 * 与「spec 只装与最终代码有关的内容」相悖。现落 AR/story.md 的影响面与风险章；
 * 它的完整性由 verifier 的 spec_constraint_echo 判定——那是判断，脚本判不了。
 */
const SPEC_EXT_SECTIONS = [
  { ch: '9 技术契约', title: /技术契约/, subs: [['端云接口', /端云接口/], ['数据存储', /数据存储/], ['配置项', /配置项/], ['埋点', /埋点/], ['依赖变更', /依赖变更/]] },
];

/** 本阶段三份产物（见 hooks/spec/on_context_load.md「本阶段产出三份文档」） */
const PHASE_ARTIFACTS = [
  {
    rel: ['AR', 'review.md'],
    name: 'AR/review.md',
    why: '归档件·评审记录（自然语言问题、当前建议与可填写审核结果），由 AI 起草、人填写结果',
    fix: '把开放点登记到 AR/story-src/decisions.json，再 story-build.mjs build 渲染（末尾状态行保持「草稿（待开发确认）」）',
  },
  {
    rel: ['AR', 'story.md'],
    name: 'AR/story.md',
    why: '归档件·叙事主件（完整需求叙事 + 判断 + 合规回显），评审者以它为主线',
    fix: '先 story-build.mjs scaffold 按章节合同注入源材料，逐章转写后 build 装配，再执行 check 与 merge-story --check',
  },
];

export default async function postCheckHook(ctx) {
  if (ctx?.phase !== 'spec' || !ctx?.feature || !ctx?.projectRoot) {
    return { ok: true };
  }

  const featureRoot = path.join(ctx.projectRoot, featuresDir(ctx.projectRoot), ctx.feature);
  const rel = path.join(featuresDir(ctx.projectRoot), ctx.feature, 'spec', 'spec.md');
  const specPath = path.join(featureRoot, 'spec', 'spec.md');
  const fix = `处置：按 ${SECTIONS_DOC} 补齐 spec 宿主扩展章节（结论写法见 ${EVIDENCE_DOC}），然后重跑 harness --phase spec。`;

  // spec 本身缺失由 framework 的 check-spec 负责，本 hook 只管宿主扩展部分
  if (!fs.existsSync(specPath)) return { ok: true };

  const text = fs.readFileSync(specPath, 'utf-8').replace(/^﻿/, '');
  const lines = text.split(/\r?\n/);
  const problems = [];

  // ---- 本阶段三份产物齐备 ----
  // spec 阶段一次 pass 产出 spec.md / review.md / story.md，三者事实同源。
  // 只交 spec.md 就宣告闭环，等于把评审件推给下一次对话去补，那时上游取证上下文已经散了。
  for (const a of PHASE_ARTIFACTS) {
    if (!fs.existsSync(path.join(featureRoot, ...a.rel))) {
      problems.push(`缺少本阶段产物「${a.name}」——${a.why}；处置：${a.fix}`);
    }
  }

  // ---- 两章的结构完整性：章在、小节齐、非空、无模板占位 ----
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
      }
    }
  }

  // ---- 合规判定落 spec 的那部分：UX 适配要求 ----
  // 深色主题 / 大字体 / 多语言这类要求只在合规判定时才冒出来，spec 别处没有，
  // 漏了就到不了编码。仅当 spec 声明有 UI 变更时要求（非 UI 需求不适用）。
  if (/ui_change:\s*(new_or_changed|changed|new)/.test(text) && findHeading(lines, /UX\s*适配要求/) === -1) {
    problems.push(
      '声明了 UI 变更但 §7 缺少「UX 适配要求」小节' +
        '（深色主题色值走资源 / 关键文本容器可伸缩不截断 / 新增文案走 string 资源——' +
        '这些要求只在合规判定时产生，不写进 spec 就到不了编码）'
    );
  }

  // ---- 术语映射表：业务名词须有解释 ----
  // 两张术语表已合并为一张（§0 追加「解释」列），附录 A 退化为索引。
  // 判据不用白名单——**权威模块落在 in_scope_modules 里的行就是本需求的业务词汇**，
  // 评审者必须能查到；权威模块是被消费的基础能力（账号 / 通用 UI / 工具）时可留「—」。
  // 数据全在 spec 自己里，加约束文件或改架构都不会让这条判据失效。
  {
    const scopeBlock = text.match(/in_scope_modules:\s*\n((?:\s*-\s*.+\n)+)/);
    const inScope = new Set(
      (scopeBlock?.[1] ?? '')
        .split('\n')
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

  // ---- 三条全文红线（词表 SSOT：skills/story/scripts/lint-rules.mjs）----

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
  // 上游输入件而是本需求自己的产物；拿它回查等于让产物给自己背书（实测「≤ 2 s」曾因此逃过校验：
  // SR/RR 中并无此值，而被覆盖的 AR 里有 3 处，全是从 spec 合成来的）。
  const upstreamTexts = ['SR/design.md', 'RR/prd.md', 'AR/design.md']
    .map(p => path.join(featureRoot, p))
    .filter(p => fs.existsSync(p))
    .map(p => fs.readFileSync(p, 'utf-8'))
    .filter(t => !/^>\s*源摘要：/m.test(t)); // story.md 的特征行；AR 提取件不会有
  const numericProblems = scanNumericSources(text, upstreamTexts);
  numericProblems.slice(0, 5).forEach(p => problems.push(p));
  if (numericProblems.length > 5) problems.push(`另有 ${numericProblems.length - 5} 处数值来源问题`);

  if (problems.length > 0) {
    return {
      ok: false,
      severityOverride: 'BLOCKER',
      message: `spec.md（${rel}）未达 spec 闭环要求：${problems.join('；')}。${fix}`,
    };
  }
  return { ok: true };
}
