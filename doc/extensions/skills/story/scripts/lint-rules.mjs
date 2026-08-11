/**
 * lint-rules.mjs — story 扩展的共享文本校验规则（词表 SSOT）
 *
 * 两组规则，供 hooks/spec/post_check.mjs（校验 spec.md）与 merge-story.mjs（校验 story.md）共用，
 * 避免两处各维护一份词表而漂移。
 *
 * 词表与 skills/story/SKILL.md「概念红线（客户端语境）」及 rules/rules.md story 第 7 条逐字对齐；
 * 修改任一处须同步另两处。
 */

/** 客户端语境禁用词：服务器侧词汇，单独使用也算 */
export const BANNED_TERMS = [
  { term: '灰度', hint: '改说「功能开关管控」/「市场·管理台放量」' },
  { term: '回滚', hint: '改说「功能开关关闭」' },
  { term: '回退', hint: '改说「功能开关关闭」/「恢复旧版本表现」（数据/状态层面的回退不在此列，见豁免）' },
  { term: '部署', hint: '客户端无部署概念，改说「随版本发布」' },
  { term: '集群', hint: '服务器侧概念，端侧不涉及' },
  { term: 'QPS', hint: '改说「端云接口请求量与触发频次」' },
  { term: 'TPS', hint: '同 QPS' },
  { term: '熔断', hint: '服务器侧概念' },
  { term: '限流', hint: '服务器侧概念；端侧防重入请写「防抖/幂等」' },
];

/**
 * 豁免语境：命中这些模式的行不判违规。
 * - 规则文件自身在定义/引用禁用词（含本文件、SKILL、rules）
 * - 引用上游规约原章节名（规约 §7.1.1.3 标题即含 QPS，删了就对不上溯源）
 * - 「回退」用于数据/状态语义而非版本发布语义
 */
const EXEMPT_LINE_PATTERNS = [
  /禁用|红线|改说|违规|banned|BANNED/i,
  /规约\s*§|上游规约|story-template-hmos-v1/,
  /状态可恢复或明确回退|数据回退|事务回退/,
];

/**
 * 仓内路径模式：归档件自包含红线——上传后独立存在，不得含本地路径。
 * `RR/` `SR/` `AR/` 是 feature 工作区内的目录，评审者同样打不开；
 * 归档件的「相关文档」表只写单号与需求系统链接。
 */
const LOCAL_PATH_RE =
  /(?:\b0\d-[A-Za-z][\w-]*\/[\w./-]+|\bdoc\/(?:extensions|features)\/[\w./-]+|\bframework\/[\w./-]+|\b(?:RR|SR|AR)\/[\w.-]+\.\w+)/g;

/**
 * 扫描禁用词。
 * @returns {{line:number, term:string, hint:string, text:string}[]}
 */
export function scanBannedTerms(text) {
  const hits = [];
  const lines = text.split(/\r?\n/);
  let inFence = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (/^\s*(```|~~~)/.test(line)) {
      inFence = !inFence;
      continue;
    }
    if (inFence) continue; // 代码块内可能是标识符，不判
    if (EXEMPT_LINE_PATTERNS.some(re => re.test(line))) continue;
    for (const { term, hint } of BANNED_TERMS) {
      if (line.includes(term)) hits.push({ line: i + 1, term, hint, text: line.trim().slice(0, 100) });
    }
  }
  return hits;
}

/**
 * 扫描仓内本地路径。
 * @returns {{line:number, path:string, text:string}[]}
 */
export function scanLocalPaths(text) {
  const hits = [];
  const lines = text.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    for (const m of lines[i].matchAll(LOCAL_PATH_RE)) {
      hits.push({ line: i + 1, path: m[0], text: lines[i].trim().slice(0, 100) });
    }
  }
  return hits;
}

/**
 * 悬空引用：指向**不随归档**的文件的坐标。
 * 随归档的只有 AR/story.md（叙事主件）与 AR/review.md（决策件）两份；
 * spec.md / SR/design.md / RR/prd.md 都留在仓内，归档后这些坐标查无此物。
 * 合法的指代只有五类：本文章节号、代码模块+文件名、中文规约名+编号、需求系统单号、
 * 随归档的兄弟件（写中文书名《决策与评审记录》——`review.md` 这个文件名仍拦，
 * 评审者拿到的是上传后的文档，不是仓内路径）。
 */
const DANGLING_REF_PATTERNS = [
  { re: /\bspec\s*§/g, hint: 'spec.md 不随归档，改用本文章节号（如「§6.2 数据存储」）' },
  { re: /\bSR\s*§/g, hint: 'SR/design.md 不随归档，首次溯源写「SE 设计文档 <单号>」，其余直接内联结论' },
  { re: /\bRR\s*§|\bPRD\s*§/g, hint: 'RR/prd.md 不随归档，首次溯源写「产品需求文档 <单号>」，其余直接内联结论' },
  { re: /\bAR\s*§/g, hint: 'AR/design.md 归档时被本文覆盖，改用本文章节号' },
  { re: /(?:见|指回|来源|源：)\s*A[1-8]\b/g, hint: '历史 impact 小节编号，本文不存在——改用事物的名字' },
  { re: /\bar_design_init\b|\bevidence-rules\b|\bstory-chapters\b|\bstory-src\b|SKILL\.md/g, hint: 'skill 内部规则文件不随归档，改述为自然语言' },
  // 裸文件名（无路径分隔符）：scanLocalPaths 只认带 "/" 的路径，覆盖不到，故在此单列。
  {
    re: /\b(?:telemetry|dfx-baseline|ux-consistency|run-modes|security-privacy|app-lifecycle-config|env-exceptions|deliverables|compatibility-checklist|acceptance|spec|impact|review)\.(?:md|yaml|yml|json)\b/g,
    hint: '仓内文件名不随归档——约束文件改写为中文规约名（如「打点规范规约」），产物文件改述为本文章节',
  },
  { re: /\b[a-z][a-z0-9-]*:[A-Z]{2,10}-\d{2}\b/g, hint: 'slug 是仓内文件名，改写为中文规约名 + 编号（如「安全隐私规约 SEC-01」）' },
  { re: /simulation_scope_awareness|ui_change\s*:|ui_spec_enforcement/g, hint: '机器校验字段名，评审者不认识——保留其自然语言说明即可' },
];

export function scanDanglingRefs(text) {
  const hits = [];
  const lines = text.split(/\r?\n/);
  let inFence = false;
  let inComment = false;
  for (let i = 0; i < lines.length; i++) {
    if (/^\s*(```|~~~)/.test(lines[i])) {
      inFence = !inFence;
      continue;
    }
    // HTML 注释块（含 ai 锚点标记与模板指引）不参与判定——它们不是给评审者读的内容
    if (inComment) {
      if (lines[i].includes('-->')) inComment = false;
      continue;
    }
    if (/<!--/.test(lines[i])) {
      if (!lines[i].includes('-->')) inComment = true;
      continue;
    }
    if (inFence) continue;
    for (const { re, hint } of DANGLING_REF_PATTERNS) {
      for (const m of lines[i].matchAll(re)) {
        hits.push({ line: i + 1, ref: m[0].trim(), hint, text: lines[i].trim().slice(0, 80) });
      }
    }
  }
  return hits;
}

/** 把扫描结果渲染成人可读的问题列表 */
export function formatHits(hits, kind) {
  return hits.map(h => {
    if (kind === 'banned') return `第 ${h.line} 行禁用词「${h.term}」（${h.hint}）：${h.text}`;
    if (kind === 'dangling') return `第 ${h.line} 行悬空引用「${h.ref}」——${h.hint}`;
    return `第 ${h.line} 行含仓内路径「${h.path}」：${h.text}`;
  });
}
