// ============================================================================
// Spec 文件加载器
// ============================================================================
// 读取 specs/ 目录下的 YAML 规约文件，返回类型安全的对象。
// 支持两类 Spec：
//   1. 阶段级规约 (phase-rules/*.yaml)
//   2. 功能级规约 (features/*/{contracts,acceptance}.yaml)
// ============================================================================

import * as fs from 'fs';
import * as path from 'path';
import * as YAML from 'yaml';
import {
  Phase,
  PhaseRuleSpec,
  ContractsSpec,
  AcceptanceSpec,
  FeatureSpec,
} from './types';

const PHASE_RULE_FILENAMES: Record<Phase, string> = {
  prd: 'prd-rules.yaml',
  design: 'design-rules.yaml',
  coding: 'coding-rules.yaml',
  review: 'review-rules.yaml',
  ut: 'ut-rules.yaml',
  testing: 'testing-rules.yaml',
};

export class SpecLoader {
  private specsRoot: string;

  constructor(projectRoot: string) {
    this.specsRoot = path.join(projectRoot, 'specs');
  }

  // --------------------------------------------------------------------------
  // 阶段级规约
  // --------------------------------------------------------------------------

  loadPhaseRule(phase: Phase): PhaseRuleSpec {
    const filename = PHASE_RULE_FILENAMES[phase];
    if (!filename) {
      throw new Error(`Unknown phase: ${phase}`);
    }
    const filePath = path.join(this.specsRoot, 'phase-rules', filename);
    return this.loadYaml<PhaseRuleSpec>(filePath);
  }

  listAvailablePhaseRules(): Phase[] {
    const dir = path.join(this.specsRoot, 'phase-rules');
    if (!fs.existsSync(dir)) return [];

    const phases: Phase[] = [];
    for (const [phase, filename] of Object.entries(PHASE_RULE_FILENAMES)) {
      if (fs.existsSync(path.join(dir, filename))) {
        phases.push(phase as Phase);
      }
    }
    return phases;
  }

  // --------------------------------------------------------------------------
  // 功能级规约
  // --------------------------------------------------------------------------

  loadFeatureSpec(feature: string): FeatureSpec {
    const featureDir = path.join(this.specsRoot, 'features', feature);

    const spec: FeatureSpec = { feature };

    const contractsPath = path.join(featureDir, 'contracts.yaml');
    if (fs.existsSync(contractsPath)) {
      spec.contracts = this.loadYaml<ContractsSpec>(contractsPath);
    }

    const acceptancePath = path.join(featureDir, 'acceptance.yaml');
    if (fs.existsSync(acceptancePath)) {
      spec.acceptance = this.loadYaml<AcceptanceSpec>(acceptancePath);
    }

    return spec;
  }

  listAvailableFeatures(): string[] {
    const dir = path.join(this.specsRoot, 'features');
    if (!fs.existsSync(dir)) return [];

    return fs.readdirSync(dir, { withFileTypes: true })
      .filter(entry => entry.isDirectory())
      .map(entry => entry.name);
  }

  // --------------------------------------------------------------------------
  // 文档加载辅助
  // --------------------------------------------------------------------------

  /**
   * 加载功能模块的过程文档 (PRD.md, design.md 等)
   * @param feature 功能模块名 (如 'home-page')
   * @param docName 文档名 (如 'PRD.md', 'design.md')
   */
  loadFeatureDoc(projectRoot: string, feature: string, docName: string): string | null {
    const docPath = path.join(projectRoot, 'doc', 'features', feature, docName);
    if (!fs.existsSync(docPath)) return null;
    return fs.readFileSync(docPath, 'utf-8');
  }

  /**
   * 收集功能模块下的源代码文件内容（从 contracts.yaml 的 files 列表中）
   * @returns 文件路径→内容的映射
   */
  collectSourceFiles(
    projectRoot: string,
    contracts: ContractsSpec | undefined,
    filterExt?: string
  ): Map<string, string> {
    const result = new Map<string, string>();
    if (!contracts?.files) return result;

    for (const relativePath of contracts.files) {
      if (filterExt && !relativePath.endsWith(filterExt)) continue;

      const fullPath = path.join(projectRoot, relativePath);
      if (fs.existsSync(fullPath)) {
        result.set(relativePath, fs.readFileSync(fullPath, 'utf-8'));
      }
    }
    return result;
  }

  // --------------------------------------------------------------------------
  // 内部方法
  // --------------------------------------------------------------------------

  private loadYaml<T>(filePath: string): T {
    if (!fs.existsSync(filePath)) {
      throw new Error(`Spec file not found: ${filePath}`);
    }
    const content = fs.readFileSync(filePath, 'utf-8');
    return YAML.parse(content) as T;
  }
}
