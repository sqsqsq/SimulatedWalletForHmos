/**
 * 用例终点的原生事实 —— 只读，给 `end_target.py` 判终点用。
 *
 * 读的是被测工程里装好的扩展（`doc/extensions/hooks/shared/framework-access.mjs`）经它加载的原生模块：
 * 蓝图读取与准入、评审投影、活动施工单位及各自的设计可施工判定，以及每个施工单位在各阶段的原生范围、输入与本阶段要产出的结果。
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
  const native = access.loadNative(root);
  const cuPath = native.module('scripts/utils/change-unit-path.ts');
  const gate = native.module('scripts/utils/change-unit-design-gate.ts');
  const { retiredChangeUnitIds } = native.module('scripts/utils/component-closure-inputs.ts');
  const identity = native.module('scripts/utils/feature-identity.js');
  let loaded = [];
  try {
    loaded = cuPath.enumerateCanonicalChangeUnits(native.root, blueprintId);
  } catch (e) {
    out.problems.push(`施工单位枚举失败：${e?.message ?? e}`);
  }
  const retired = retiredChangeUnitIds(native.root, blueprintId);
  for (const unit of loaded) {
    const id = String(unit.changeUnit.change_unit_id);
    if (retired.has(id)) continue;
    const design = gate.validateChangeUnitDesign(native.root, unit.changeUnit);
    const featureId = identity.encodeCuFeatureId(blueprintId, id);
    const dir = access.featureDir(root, featureId);
    const row = { change_unit_id: id, feature_id: featureId, feature_path: dir ? path.relative(root, dir).split(path.sep).join('/') : null,
      design: { verdict: String(design.verdict), issues: (design.issues ?? []).map(i => i.id) }, phases: {} };
    for (const phase of phases) {
      const f = access.readFeature(root, featureId, phase);
      row.phases[phase] = { status: f.status, scope: f.scope ?? null, issues: issueText(f.issues),
        required_outputs: f.required_outputs ?? null };
    }
    out.units.push(row);
  }
  out.units.sort((a, b) => (a.change_unit_id < b.change_unit_id ? -1 : 1));
}
process.stdout.write(JSON.stringify(out));
