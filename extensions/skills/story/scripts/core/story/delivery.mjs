/**
 * 交付门 —— 交付前核成文依据与独立审查，以及通过之后的交付选择。
 *
 * 按**动作**分而不按文件在不在推断阶段：登记前跑的是普通 check，那时独立审查还没发生。
 */
import { isSystemRequirement, readJson } from './context.mjs';
import { basisDriftProblems, designSource } from './design-source.mjs';

/**
 * 交付门通过之后往哪走 —— 打印这一问的选项，**不替人选**。
 *
 * 系统需求可以送审（归档）或先送审再继续；本地单没有送审，只有本地交付。已有授权覆盖的直接用，
 * 业务审批与普通实施授权分开。评审人的表态之后由 `/story update` 承接。
 * 这是脚本给的确定性文本，与 `story_flow.py status` 同一口径。
 */
export function deliveryNextSteps(ctx) {
  const remote = readJson(ctx.flowPath, null) !== null && isSystemRequirement(ctx.args.feature);
  const rows = [
    ...(remote ? ['  - 送审：`/story archive <AR>`，归档后评审人在需求系统表态'] : []),
    '  - 完整设计交接：在已准入蓝图上按原生 change-unit-progression 完成施工单位设计准备，不启动施工',
    '  - 完整实现：在授权范围内接续设计准备与原生交互式开发，按原生结果推进',
    '  - 暂不推进：停在这里，之后从 `story_flow.py status` 续上',
  ];
  return ['', '[story-build check] 交付门通过。按停等表问人一次交付选择：', '',
    ...rows, ...(remote ? [] : ['  （本地单没有送审）']), ''].join('\n');
}

/**
 * 交付门 —— 成文依据还是登记时那一份吗，独立审查给出可消费的结论了吗。
 *
 * 设计来源不成立、登记之后蓝图 / 输入 / 知识变了，都拦：登记说的已经不是现在这份。
 * 独立人读审查的原生调用接通之前，审查结论取不到——那不是失败，但**要出声**：静默通过的话，
 * 没经过审查的 story 就这么交出去了，事后没人看得出来。有既有明确授权按授权交付，没有就请人选。
 *
 * @returns {{problems: string[], notes: string[]}}
 */
export function deliveryProblems(ctx) {
  const flow = readJson(ctx.flowPath, null);
  if (flow?.status !== 'story_written') {
    return { problems: ['还没登记成文——交付的是登记过的那一份，先跑 `story_flow.py story` 登记'], notes: [] };
  }
  const source = designSource(ctx);
  const drift = source.problems.length ? source.problems : basisDriftProblems(ctx);
  if (drift.length) return { problems: drift, notes: [] };
  return {
    problems: [],
    notes: ['这份 Story 未经独立人读审查：独立审查的原生调用尚未接通，审查结论取不到。'
      + '有既有明确授权就按授权交付并如实说明未审；没有就请人选择，不写成审查通过'],
  };
}
