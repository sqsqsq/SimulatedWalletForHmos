/**
 * 用例终点的原生事实 —— 只读，给 `end_target.py` 判终点用。
 *
 * 读的是被测工程里装好的扩展（`doc/extensions/hooks/shared/framework-access.mjs`）：蓝图读取与准入、评审投影、活动施工单位，
 * 再经它加载原生模块取各施工单位的设计可施工判定，以及每个施工单位在各阶段的原生范围、输入与本阶段要产出的结果。
 * 不调会写文件的原生入口（如 `deriveDesignPreparationReadiness` 会先原位升版施工单位的蓝图引用）。
 *
 * 用法：node observe_target.mjs <工程根> <蓝图 id> <逗号分隔的阶段，可为空>
 * 输出：{ blueprint: {...}, units: [{ change_unit_id, feature_id, feature_path, design, phases: {<阶段>: {...}} }], problems: [] }
 */
import { pathToFileURL } from 'node:url';
import * as path from 'node:path';

const [root, blueprintId, phaseList = ''] = process.argv.slice(2);
const phases = phaseList.split(',').map(s => s.trim()).filter(Boolean);
const access = await import(pathToFileURL(path.join(root, 'doc', 'extensions', 'hooks', 'shared', 'framework-access.mjs')).href);

const issueText = (issues) => (issues ?? []).map(i => `${i.code ?? i.id ?? '问题'}：${i.message ?? ''}`);
const out = { blueprint_id: blueprintId, blueprint: null, units: [], problems: [] };

const read = access.readBlueprint(root, blueprintId, 'draft');
out.blueprint = { status: read.status, admitted: Boolean(read.admitted), projection: read.projection?.status ?? null,
  canonical_path: read.canonical_path ?? null, issues: issueText(read.issues) };

if (read.status === 'ok' && read.admitted) {
  // 活动施工单位由扩展读蓝图时给出（原生枚举、去掉退役的）；这里补原生设计判定与各阶段的原生范围、输入
  const native = access.loadNative(root);
  const cuPath = native.module('scripts/utils/change-unit-path.ts');
  const gate = native.module('scripts/utils/change-unit-design-gate.ts');
  for (const unit of read.units ?? []) {
    const loaded = cuPath.loadCanonicalChangeUnit(native.root, blueprintId, unit.change_unit_id);
    const design = gate.validateChangeUnitDesign(native.root, loaded.changeUnit);
    const row = { change_unit_id: unit.change_unit_id, feature_id: unit.feature_id, feature_path: unit.path,
      design: { verdict: String(design.verdict), issues: (design.issues ?? []).map(i => i.id) }, phases: {} };
    for (const phase of phases) {
      const f = access.readFeature(root, unit.feature_id, phase);
      row.phases[phase] = { status: f.status, scope: f.scope ?? null, issues: issueText(f.issues),
        required_outputs: f.required_outputs ?? null };
    }
    out.units.push(row);
  }
}
process.stdout.write(JSON.stringify(out));
