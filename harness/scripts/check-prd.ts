// ============================================================================
// PRD 阶段脚本 Harness — check-prd.ts
// ============================================================================
// 读取 specs/phase-rules/prd-rules.yaml + doc/features/{feature}/PRD.md
// 执行确定性的结构 / 追溯验证。
//
// 检查项（与 prd-rules.yaml 对应）：
//   Structure:     required_chapters, feature_table_format, priority_values,
//                  at_least_one_p0, acceptance_criteria_format, mermaid_flowchart,
//                  exception_table_format, minimum_exception_scenarios,
//                  nfr_quantified, page_description_completeness, metadata_header
//   Traceability:  feature_to_acceptance, acceptance_to_feature
//
// 语义级检查由 AI Harness (verify-prd.md) 完成，不在本脚本范围内。
// ============================================================================

import {
  PhaseChecker,
  CheckContext,
  CheckResult,
} from './utils/types';
import { SpecLoader } from './utils/spec-loader';
import {
  extractHeadings,
  getSectionContent,
  getSubsectionHeadings,
  extractTables,
  extractCodeBlocks,
  extractMetadata,
  tableHasColumns,
  getColumnValues,
} from './utils/markdown-parser';

// --------------------------------------------------------------------------
// Helpers
// --------------------------------------------------------------------------

function ruleDesc(
  ctx: CheckContext,
  section: 'structure_checks' | 'semantic_checks' | 'traceability_checks',
  id: string,
): string {
  const checks = ctx.phaseRule[section] as Record<string, { description: string }>;
  return checks?.[id]?.description?.trim() ?? id;
}

function loadPrd(ctx: CheckContext): string | null {
  return new SpecLoader(ctx.projectRoot)
    .loadFeatureDoc(ctx.projectRoot, ctx.feature, 'PRD.md');
}

// --------------------------------------------------------------------------
// Structure Checks
// --------------------------------------------------------------------------

function checkRequiredChapters(ctx: CheckContext, prd: string): CheckResult[] {
  const expected = [
    '功能概述', '目标用户与使用场景', '功能清单', '页面/界面描述',
    '业务流程图', '异常/边界场景处理', '非功能性需求', '验收标准',
  ];

  const headingTexts = extractHeadings(prd).map(h => h.text);
  const missing = expected.filter(e => !headingTexts.some(t => t.includes(e)));

  if (missing.length === 0) {
    return [{ id: 'required_chapters', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'required_chapters'), severity: 'BLOCKER', status: 'PASS', details: `全部 ${expected.length} 个必需章节均存在。` }];
  }
  return [{
    id: 'required_chapters', category: 'structure',
    description: ruleDesc(ctx, 'structure_checks', 'required_chapters'),
    severity: 'BLOCKER', status: 'FAIL',
    details: `缺少 ${missing.length} 个必需章节：${missing.join('、')}`,
    suggestion: '请补充缺失的 PRD 章节。',
  }];
}

function checkFeatureTableFormat(ctx: CheckContext, prd: string): CheckResult[] {
  const section = getSectionContent(prd, '功能清单');
  if (!section) {
    return [{ id: 'feature_table_format', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'feature_table_format'), severity: 'BLOCKER', status: 'FAIL', details: '未找到「功能清单」章节。' }];
  }

  const tables = extractTables(section);
  if (tables.length === 0) {
    return [{ id: 'feature_table_format', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'feature_table_format'), severity: 'BLOCKER', status: 'FAIL', details: '「功能清单」中未找到 Markdown 表格。' }];
  }

  const { hasAll, missing } = tableHasColumns(tables[0], ['编号', '功能名称', '优先级', '描述']);
  if (!hasAll) {
    return [{ id: 'feature_table_format', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'feature_table_format'), severity: 'BLOCKER', status: 'FAIL', details: `功能清单表格缺少列：${missing.join('、')}。实际表头：${tables[0].headers.join('、')}` }];
  }

  return [{ id: 'feature_table_format', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'feature_table_format'), severity: 'BLOCKER', status: 'PASS', details: `功能清单表格包含 ${tables[0].rows.length} 行，表头列齐全。` }];
}

function checkPriorityValues(ctx: CheckContext, prd: string): CheckResult[] {
  const section = getSectionContent(prd, '功能清单');
  const tables = section ? extractTables(section) : [];
  if (tables.length === 0) {
    return [{ id: 'priority_values', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'priority_values'), severity: 'BLOCKER', status: 'SKIP', details: '功能清单无表格可分析。' }];
  }

  const priorities = getColumnValues(tables[0], '优先级');
  const allowed = new Set(['P0', 'P1', 'P2', 'P3']);
  const invalid = priorities.filter(p => !allowed.has(p));

  if (invalid.length === 0) {
    return [{ id: 'priority_values', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'priority_values'), severity: 'BLOCKER', status: 'PASS', details: `全部 ${priorities.length} 行的优先级值合法。` }];
  }
  return [{
    id: 'priority_values', category: 'structure',
    description: ruleDesc(ctx, 'structure_checks', 'priority_values'),
    severity: 'BLOCKER', status: 'FAIL',
    details: `${invalid.length} 个无效的优先级值：${[...new Set(invalid)].join('、')}。允许值：P0/P1/P2/P3`,
  }];
}

function checkAtLeastOneP0(ctx: CheckContext, prd: string): CheckResult[] {
  const section = getSectionContent(prd, '功能清单');
  const tables = section ? extractTables(section) : [];
  if (tables.length === 0) {
    return [{ id: 'at_least_one_p0', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'at_least_one_p0'), severity: 'BLOCKER', status: 'SKIP', details: '功能清单无表格。' }];
  }

  const p0Count = getColumnValues(tables[0], '优先级').filter(p => p === 'P0').length;
  if (p0Count > 0) {
    return [{ id: 'at_least_one_p0', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'at_least_one_p0'), severity: 'BLOCKER', status: 'PASS', details: `共 ${p0Count} 个 P0 功能项。` }];
  }
  return [{ id: 'at_least_one_p0', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'at_least_one_p0'), severity: 'BLOCKER', status: 'FAIL', details: '功能清单中没有任何 P0 功能项。' }];
}

function checkAcceptanceCriteriaFormat(ctx: CheckContext, prd: string): CheckResult[] {
  const section = getSectionContent(prd, '验收标准');
  if (!section) {
    return [{ id: 'acceptance_criteria_format', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'acceptance_criteria_format'), severity: 'BLOCKER', status: 'FAIL', details: '未找到「验收标准」章节。' }];
  }

  const acPattern = /\*\*(AC-[\w]+)\*\*/g;
  const ids = [...section.matchAll(acPattern)].map(m => m[1]);

  if (ids.length === 0) {
    return [{ id: 'acceptance_criteria_format', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'acceptance_criteria_format'), severity: 'BLOCKER', status: 'FAIL', details: '「验收标准」中未找到 AC-N 格式编号。' }];
  }

  const duplicates = ids.filter((id, i) => ids.indexOf(id) !== i);
  if (duplicates.length > 0) {
    return [{ id: 'acceptance_criteria_format', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'acceptance_criteria_format'), severity: 'BLOCKER', status: 'WARN', details: `${ids.length} 条 AC，存在重复编号：${[...new Set(duplicates)].join('、')}` }];
  }

  return [{ id: 'acceptance_criteria_format', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'acceptance_criteria_format'), severity: 'BLOCKER', status: 'PASS', details: `验收标准包含 ${ids.length} 条唯一 AC 项。` }];
}

function checkMermaidFlowchart(ctx: CheckContext, prd: string): CheckResult[] {
  const section = getSectionContent(prd, '业务流程图');
  if (!section) {
    return [{ id: 'mermaid_flowchart', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'mermaid_flowchart'), severity: 'BLOCKER', status: 'FAIL', details: '未找到「业务流程图」章节。' }];
  }

  const mermaidBlocks = extractCodeBlocks(section, 'mermaid');
  if (mermaidBlocks.length === 0) {
    return [{ id: 'mermaid_flowchart', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'mermaid_flowchart'), severity: 'BLOCKER', status: 'FAIL', details: '「业务流程图」中未找到 Mermaid 代码块。' }];
  }

  const hasFlowchart = mermaidBlocks.some(b =>
    /flowchart|graph\s+(TD|LR|RL|BT)/i.test(b.content),
  );

  if (!hasFlowchart) {
    return [{ id: 'mermaid_flowchart', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'mermaid_flowchart'), severity: 'BLOCKER', status: 'WARN', details: `${mermaidBlocks.length} 个 Mermaid 代码块，但未检测到 flowchart 语法。` }];
  }

  return [{ id: 'mermaid_flowchart', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'mermaid_flowchart'), severity: 'BLOCKER', status: 'PASS', details: `找到 ${mermaidBlocks.length} 个 Mermaid 流程图。` }];
}

function checkExceptionTableFormat(ctx: CheckContext, prd: string): CheckResult[] {
  const section = getSectionContent(prd, '异常/边界场景处理') ?? getSectionContent(prd, '异常');
  if (!section) {
    return [{ id: 'exception_table_format', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'exception_table_format'), severity: 'MAJOR', status: 'FAIL', details: '未找到「异常/边界场景处理」章节。' }];
  }

  const tables = extractTables(section);
  if (tables.length === 0) {
    return [{ id: 'exception_table_format', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'exception_table_format'), severity: 'MAJOR', status: 'FAIL', details: '「异常/边界场景处理」中未找到表格。' }];
  }

  const { hasAll, missing } = tableHasColumns(tables[0], ['编号', '异常场景', '处理方式']);
  if (!hasAll) {
    return [{ id: 'exception_table_format', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'exception_table_format'), severity: 'MAJOR', status: 'FAIL', details: `异常场景表格缺少列：${missing.join('、')}。实际表头：${tables[0].headers.join('、')}` }];
  }

  return [{ id: 'exception_table_format', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'exception_table_format'), severity: 'MAJOR', status: 'PASS', details: `异常场景表格包含 ${tables[0].rows.length} 行，表头列齐全。` }];
}

function checkMinimumExceptionScenarios(ctx: CheckContext, prd: string): CheckResult[] {
  const section = getSectionContent(prd, '异常/边界场景处理') ?? getSectionContent(prd, '异常');
  const tables = section ? extractTables(section) : [];
  if (tables.length === 0) {
    return [{ id: 'minimum_exception_scenarios', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'minimum_exception_scenarios'), severity: 'MAJOR', status: 'SKIP', details: '异常场景章节无表格。' }];
  }

  const rowCount = tables[0].rows.length;
  if (rowCount >= 3) {
    return [{ id: 'minimum_exception_scenarios', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'minimum_exception_scenarios'), severity: 'MAJOR', status: 'PASS', details: `异常场景共 ${rowCount} 种（≥ 3）。` }];
  }
  return [{ id: 'minimum_exception_scenarios', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'minimum_exception_scenarios'), severity: 'MAJOR', status: 'FAIL', details: `异常场景仅 ${rowCount} 种，不满足最低 3 种要求。` }];
}

function checkNfrQuantified(ctx: CheckContext, prd: string): CheckResult[] {
  const section = getSectionContent(prd, '非功能性需求');
  if (!section) {
    return [{ id: 'nfr_quantified', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'nfr_quantified'), severity: 'MAJOR', status: 'FAIL', details: '未找到「非功能性需求」章节。' }];
  }

  const numericPattern = /[≤≥<>]\s*\d+|\d+\s*(秒|ms|FPS|fps|MB|KB|dp|%)/;
  if (numericPattern.test(section)) {
    return [{ id: 'nfr_quantified', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'nfr_quantified'), severity: 'MAJOR', status: 'PASS', details: '非功能性需求包含量化数值指标。' }];
  }

  return [{ id: 'nfr_quantified', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'nfr_quantified'), severity: 'MAJOR', status: 'FAIL', details: '「非功能性需求」未包含量化数值指标（如 ≤ 1.5 秒、≥ 54 FPS）。' }];
}

function checkPageDescriptionCompleteness(ctx: CheckContext, prd: string): CheckResult[] {
  const section = getSectionContent(prd, '页面/界面描述') ?? getSectionContent(prd, '页面');
  if (!section) {
    return [{ id: 'page_description_completeness', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'page_description_completeness'), severity: 'MAJOR', status: 'FAIL', details: '未找到「页面/界面描述」章节。' }];
  }

  const subsections = (
    getSubsectionHeadings(prd, '页面/界面描述').length > 0
      ? getSubsectionHeadings(prd, '页面/界面描述')
      : getSubsectionHeadings(prd, '页面')
  ).filter(h => !h.text.includes('总览') && !h.text.includes('汇总') && !h.text.includes('概述'));

  if (subsections.length === 0) {
    return [{ id: 'page_description_completeness', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'page_description_completeness'), severity: 'MAJOR', status: 'WARN', details: '未找到页面子章节。' }];
  }

  const requiredCols = ['组件', '类型', '交互行为'];
  const pagesWithoutTable: string[] = [];

  for (const sub of subsections) {
    const subContent = getSectionContent(prd, sub.text);
    if (!subContent) { pagesWithoutTable.push(sub.text); continue; }

    const tables = extractTables(subContent);
    const hasValidTable = tables.some(t => tableHasColumns(t, requiredCols).hasAll);
    if (!hasValidTable) pagesWithoutTable.push(sub.text);
  }

  if (pagesWithoutTable.length === 0) {
    return [{ id: 'page_description_completeness', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'page_description_completeness'), severity: 'MAJOR', status: 'PASS', details: `全部 ${subsections.length} 个页面均有组件表格。` }];
  }

  return [{
    id: 'page_description_completeness', category: 'structure',
    description: ruleDesc(ctx, 'structure_checks', 'page_description_completeness'),
    severity: 'MAJOR', status: 'WARN',
    details: `${pagesWithoutTable.length} 个页面缺少组件表格：${pagesWithoutTable.join('、')}`,
    suggestion: '每个页面子章节应包含组件表格（至少含"组件、类型、交互行为"三列）。',
  }];
}

function checkMetadataHeader(ctx: CheckContext, prd: string): CheckResult[] {
  const metadata = extractMetadata(prd);
  const required = ['模块标识', '版本', '创建日期', '状态'];
  const missing = required.filter(f => !metadata[f]);

  if (missing.length === 0) {
    return [{ id: 'metadata_header', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'metadata_header'), severity: 'MINOR', status: 'PASS', details: `元数据齐全：${Object.keys(metadata).join('、')}` }];
  }
  return [{ id: 'metadata_header', category: 'structure', description: ruleDesc(ctx, 'structure_checks', 'metadata_header'), severity: 'MINOR', status: 'WARN', details: `元数据缺少字段：${missing.join('、')}` }];
}

// --------------------------------------------------------------------------
// Traceability Checks
// --------------------------------------------------------------------------

function checkFeatureToAcceptance(ctx: CheckContext, prd: string): CheckResult[] {
  const featureSection = getSectionContent(prd, '功能清单');
  const featureTables = featureSection ? extractTables(featureSection) : [];
  if (featureTables.length === 0) {
    return [{ id: 'feature_to_acceptance', category: 'traceability', description: ruleDesc(ctx, 'traceability_checks', 'feature_to_acceptance'), severity: 'BLOCKER', status: 'SKIP', details: '功能清单无表格。' }];
  }

  const featureIds = getColumnValues(featureTables[0], '编号');
  const priorities = getColumnValues(featureTables[0], '优先级');
  const p0p1: string[] = [];
  for (let i = 0; i < featureIds.length; i++) {
    if (priorities[i] === 'P0' || priorities[i] === 'P1') p0p1.push(featureIds[i]);
  }

  const acSection = getSectionContent(prd, '验收标准');
  if (!acSection) {
    return [{ id: 'feature_to_acceptance', category: 'traceability', description: ruleDesc(ctx, 'traceability_checks', 'feature_to_acceptance'), severity: 'BLOCKER', status: 'FAIL', details: '未找到验收标准章节。' }];
  }

  const refPattern = /\*\*AC-[\w]+\*\*\s*\(([^)]+)\)/g;
  const referencedFeatures = new Set<string>();
  let m: RegExpExecArray | null;
  while ((m = refPattern.exec(acSection)) !== null) {
    m[1].split(/[,，]/).map(r => r.trim()).forEach(r => referencedFeatures.add(r));
  }

  const uncovered = p0p1.filter(f => !referencedFeatures.has(f));

  if (uncovered.length === 0) {
    return [{ id: 'feature_to_acceptance', category: 'traceability', description: ruleDesc(ctx, 'traceability_checks', 'feature_to_acceptance'), severity: 'BLOCKER', status: 'PASS', details: `全部 ${p0p1.length} 个 P0/P1 功能均有验收标准。` }];
  }
  return [{
    id: 'feature_to_acceptance', category: 'traceability',
    description: ruleDesc(ctx, 'traceability_checks', 'feature_to_acceptance'),
    severity: 'BLOCKER', status: 'FAIL',
    details: `${uncovered.length}/${p0p1.length} 个 P0/P1 功能缺少 AC：${uncovered.join('、')}`,
    suggestion: '请为每个 P0/P1 功能添加至少一条验收标准。',
  }];
}

function checkAcceptanceToFeature(ctx: CheckContext, prd: string): CheckResult[] {
  const acSection = getSectionContent(prd, '验收标准');
  if (!acSection) {
    return [{ id: 'acceptance_to_feature', category: 'traceability', description: ruleDesc(ctx, 'traceability_checks', 'acceptance_to_feature'), severity: 'BLOCKER', status: 'SKIP', details: '未找到验收标准章节。' }];
  }

  const acItemPattern = /\*\*(AC-[\w]+)\*\*(?:\s*\(([^)]*)\))?/g;
  const items: Array<{ id: string; hasRef: boolean }> = [];
  let m: RegExpExecArray | null;
  while ((m = acItemPattern.exec(acSection)) !== null) {
    const isGeneral = m[1].startsWith('AC-G');
    items.push({ id: m[1], hasRef: isGeneral || (!!m[2] && m[2].trim().length > 0) });
  }

  if (items.length === 0) {
    return [{ id: 'acceptance_to_feature', category: 'traceability', description: ruleDesc(ctx, 'traceability_checks', 'acceptance_to_feature'), severity: 'BLOCKER', status: 'SKIP', details: '未找到 AC 项。' }];
  }

  const orphaned = items.filter(i => !i.hasRef);
  if (orphaned.length === 0) {
    return [{ id: 'acceptance_to_feature', category: 'traceability', description: ruleDesc(ctx, 'traceability_checks', 'acceptance_to_feature'), severity: 'BLOCKER', status: 'PASS', details: `全部 ${items.length} 条 AC 均关联到功能编号。` }];
  }
  return [{
    id: 'acceptance_to_feature', category: 'traceability',
    description: ruleDesc(ctx, 'traceability_checks', 'acceptance_to_feature'),
    severity: 'BLOCKER', status: 'FAIL',
    details: `${orphaned.length} 条 AC 未关联功能编号：${orphaned.map(o => o.id).join('、')}`,
    suggestion: '格式：**AC-1** (F1): 描述...',
  }];
}

// --------------------------------------------------------------------------
// Main Checker
// --------------------------------------------------------------------------

function safeRun(fn: () => CheckResult[], checkId: string): CheckResult[] {
  try {
    return fn();
  } catch (err) {
    return [{
      id: checkId, category: 'structure',
      description: `${checkId} 执行异常`,
      severity: 'MINOR', status: 'SKIP',
      details: `检查执行时发生错误：${(err as Error).message}`,
    }];
  }
}

const checker: PhaseChecker = {
  phase: 'prd',

  async check(ctx: CheckContext): Promise<CheckResult[]> {
    const prd = loadPrd(ctx);
    if (!prd) {
      return [{
        id: 'prd_file_exists', category: 'structure',
        description: `doc/features/${ctx.feature}/PRD.md 不存在`,
        severity: 'BLOCKER', status: 'FAIL',
        details: `PRD 文件 doc/features/${ctx.feature}/PRD.md 不存在，无法进行任何检查。`,
        affected_files: [`doc/features/${ctx.feature}/PRD.md`],
      }];
    }

    const results: CheckResult[] = [];

    results.push(...safeRun(() => checkRequiredChapters(ctx, prd), 'required_chapters'));
    results.push(...safeRun(() => checkFeatureTableFormat(ctx, prd), 'feature_table_format'));
    results.push(...safeRun(() => checkPriorityValues(ctx, prd), 'priority_values'));
    results.push(...safeRun(() => checkAtLeastOneP0(ctx, prd), 'at_least_one_p0'));
    results.push(...safeRun(() => checkAcceptanceCriteriaFormat(ctx, prd), 'acceptance_criteria_format'));
    results.push(...safeRun(() => checkMermaidFlowchart(ctx, prd), 'mermaid_flowchart'));
    results.push(...safeRun(() => checkExceptionTableFormat(ctx, prd), 'exception_table_format'));
    results.push(...safeRun(() => checkMinimumExceptionScenarios(ctx, prd), 'minimum_exception_scenarios'));
    results.push(...safeRun(() => checkNfrQuantified(ctx, prd), 'nfr_quantified'));
    results.push(...safeRun(() => checkPageDescriptionCompleteness(ctx, prd), 'page_description_completeness'));
    results.push(...safeRun(() => checkMetadataHeader(ctx, prd), 'metadata_header'));

    results.push(...safeRun(() => checkFeatureToAcceptance(ctx, prd), 'feature_to_acceptance'));
    results.push(...safeRun(() => checkAcceptanceToFeature(ctx, prd), 'acceptance_to_feature'));

    return results;
  },
};

export default checker;
