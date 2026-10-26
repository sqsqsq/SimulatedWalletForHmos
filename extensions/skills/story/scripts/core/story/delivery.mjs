/**
 * 交付门 —— 交付前核成文依据与独立审查，以及通过之后的交付选择。
 *
 * 按**动作**分而不按文件在不在推断阶段：登记前跑的是普通 check，那时独立审查还没发生。
 */
import { isSystemRequirement, readJson } from './context.mjs';
import { basisDriftProblems, designSource, designStatusLines } from './design-source.mjs';
import { reviewResult } from './independent-review.mjs';
import { designReviewProblems } from './appendix.mjs';
import { readingWork } from './figure-view.mjs';

/**
 * 交付门通过之后往哪走 —— 已有明确授权按其范围继续，没指定后续目标才问；打印这一问的选项，**不替人选**。
 *
 * 系统需求可以送审（归档）或先送审再继续；本地单没有送审，只有本地交付。已有授权覆盖的直接用，
 * 业务审批与普通实施授权分开。评审人的表态之后由 `/story update` 承接。
 * 这是脚本给的确定性文本，与 `story_flow.py status` 同一口径。
 */
export function deliveryNextSteps(ctx) {
  // 已开始的同图增强没做完：交付门照样通过，下一步先把本轮这份工作做完，做完再问人
  const work = readingWork(ctx.featureRoot);
  if (!work.complete) {
    return ['', `[story-build check] 交付门通过。已开始的同图增强还没做完，这是本轮工作，先做完：${work.next}`,
      '做完后再跑一次交付门，按它给的停等问人。', ''].join('\n');
  }
  const remote = readJson(ctx.flowPath, null) !== null && isSystemRequirement(ctx.args.feature);
  const rows = [
    ...(remote ? ['  - 送审：把这份需求送到需求系统，评审人在那里表态'] : []),
    '  - 完整设计交接：把已准入的设计准备成可施工的施工单位，不开始施工',
    '  - 实现方案：设计准备之后为每个施工单位完成 Spec 与 Plan，止于 Plan、不进入 Coding',
    '  - 完整实现：在授权范围内从设计准备一直推进到开发完成',
    '  - 暂不推进：停在这里，之后可以接着做',
  ];
  return ['', '[story-build check] 交付门通过。已有明确授权就按其范围继续，还没指定后续目标时问一次交付选择（停等表）：', '',
    ...rows, ...(remote ? [] : ['  （本地单没有送审）']),
    '  选定之后怎么执行见 phases/design.md「五、独立审查、登记与交付」第 6 步。', ''].join('\n');
}

/**
 * 交付门 —— 成文依据还是登记时那一份吗，这一份的独立审查给出可消费的结论了吗。
 *
 * 设计来源不成立、登记之后蓝图 / 输入 / 知识 / 被审文件变了、设计附件不是当前原生投影，都拦：登记说的已经不是现在这份。
 * 审查结论只读当前对象的 Story 报告：pass 放行，warn 放行并列出建议，人授权的未审查交付放行并披露，其余照结果拦。
 *
 * @returns {Promise<{problems: string[], notes: string[]}>}
 */
export async function deliveryProblems(ctx) {
  const flow = readJson(ctx.flowPath, null);
  if (flow?.status !== 'story_written') {
    return { problems: ['还没登记成文——交付的是登记过的那一份，先跑 `story_flow.py story` 登记'], notes: [] };
  }
  const source = designSource(ctx);
  const drift = source.problems.length ? source.problems : [...basisDriftProblems(ctx), ...designReviewProblems(ctx)];
  if (drift.length) return { problems: drift, notes: [] };
  // 草稿可以业务送审；准入状态与原生问题照实写进交付说明，施工准备前由设计职责走到准入
  const design = source.admitted ? [] : [`设计状态：${designStatusLines(source).join('\n')}——业务送审照常，施工准备前由设计职责走到准入`];
  const review = reviewResult(ctx);
  if (review.result === 'pass') return { problems: [], notes: design };
  if (review.result === 'warn') {
    return { problems: [], notes: [`独立审查带非阻断建议通过，建议照录：${review.advisories.join('；')}`, ...design] };
  }
  if (review.result === 'unreviewed') return { problems: [], notes: [`${review.detail}——已写进 Story 交付章与 Review 题头的审查状态`, ...design] };
  return { problems: [`独立审查结果 ${review.result}：${review.detail}`], notes: design };
}
