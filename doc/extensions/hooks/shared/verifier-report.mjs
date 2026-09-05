/**
 * 读者审查的落盘核对 —— 语义审查做了没有，看它有没有留下报告。
 *
 * ## 报告在哪、谁写的
 *
 * harness 生成 verifier request 时就把本轮报告的落点写进 `<phase>/reports/summary.json`
 * 的 `verifier_report`（仓内相对路径）。派 verifier 的那个 agent 把子代理的回复**原样全文**
 * 写到那里——写报告的是调用方，不是 verifier 自己，也没有钩子代它发布。
 *
 * 身份归框架：报告在不在、终态块回显的 subject 对不对、verdict 与 blocker 数一致不一致，
 * 由 `check-receipt` 判。这里不重复核，只判**读者审查这一项的形态**。
 *
 * ## 判的是形态，不是内容
 *
 * 上游的输出契约是：汇总表每个检查项一行（PASS 也列，证据一行），YAML 明细只列
 * status ≠ PASS 的项。所以这里的三条判据顺着它：
 *
 *   ① 汇总表里有 `story_reader_review` 一行，且证据格不为空——空证据与没审同形；
 *   ② 那一行 status ≠ PASS 时，明细里有 `blocking_findings` 与 `advisories` 两个键；
 *   ③ 结果里没有逐单元裁决表——出了就是做成了另一件事。
 *
 * 报几条、报得对不对不判：那是资格门用成对样本量的事，不是门禁能判的。
 */
import * as path from 'node:path';
import { featureRoot, readJsonOrNull, readTextOrNull } from './paths.mjs';

/** 读者审查那一项在报告里的标识 —— 判据 id 本身，不另起一个名字。 */
const STORY_REVIEW_ID = 'story_reader_review';

/** 非 PASS 时明细里必须有的两个键。可以是空列表，但不能缺席。 */
const DETAIL_KEYS = ['blocking_findings', 'advisories'];

/**
 * 逐单元裁决表的表头特征 —— 审查任务明说不出这张表，出了就是**做成了另一件事**。
 *
 * 认表头不认内容：表头是明确记号，判它不需要读懂任何一句话。
 */
const PER_UNIT_TABLE_RE = /\|\s*单元键\s*\|/;

/**
 * 本轮报告落在哪 —— 唯一来源是 harness 写的 `summary.verifier_report`。
 *
 * 返回 null 有两种含义，调用方按 `summary` 在不在区分：summary 都没有 = harness
 * 还没跑；summary 在而这个字段没有 = 本宿主没有审查员（verifier plan disabled），
 * 那是如实披露的状态，不是缺件。
 */
function reportLocation(projectRoot, feature, phase) {
  const dir = path.join(featureRoot(projectRoot, feature), phase, 'reports');
  const summary = readJsonOrNull(path.join(dir, 'summary.json'));
  if (!summary) return { summaryFound: false, abs: null };
  const rel = typeof summary.verifier_report === 'string' ? summary.verifier_report.trim() : '';
  return { summaryFound: true, abs: rel ? path.resolve(projectRoot, rel) : null };
}

/**
 * 汇总表里 `story_reader_review` 那一行。
 *
 * 认的是「以 | 分格、第一格是这个 id」的行，不认散落在正文里的同名字样——
 * 后者在讲这一项，不是这一项的结论。
 */
function summaryRow(text) {
  for (const line of text.split(/\r?\n/)) {
    const raw = line.trim();
    if (!raw.startsWith('|')) continue;
    const cells = raw.split('|').slice(1, -1).map(c => c.trim());
    if (cells.length >= 2 && cells[0].replace(/`/g, '') === STORY_REVIEW_ID) return cells;
  }
  return null;
}

/**
 * 读者审查这一项做了没有、写成什么形态。
 *
 * @returns {{status: string, problems: string[], detail: string}}
 */
export function storyReviewProblems(projectRoot, feature, phase) {
  const { summaryFound, abs } = reportLocation(projectRoot, feature, phase);
  if (!summaryFound) {
    return { status: 'NOT_APPLICABLE', problems: [], detail: 'harness 尚未运行，本项还轮不到判' };
  }
  if (!abs) {
    return {
      status: 'NOT_APPLICABLE',
      problems: [],
      detail: '本宿主没有登记审查员（verifier 未启用），本轮没有报告可核',
    };
  }
  const text = readTextOrNull(abs);
  if (text === null) {
    return {
      status: 'FAIL',
      problems: [`verifier 报告不在落点上：${abs}——`
        + '报告由派 verifier 的那个 agent 把子代理回复原样写到 `summary.verifier_report`；'
        + '没有它，读者审查有没有执行无从核对'],
      detail: '报告缺席',
    };
  }

  const row = summaryRow(text);
  if (!row) {
    return {
      status: 'FAIL',
      problems: [`verifier 报告的汇总表里没有 ${STORY_REVIEW_ID} 这一行——`
        + '这一项是 story 语义质量的发现者，汇总表里找不到它就等于这一轮没审。'
        + '按输出契约补一行：id、status、severity、一行证据'],
      detail: '汇总表缺行',
    };
  }
  const status = row[1].replace(/`|\*/g, '').toUpperCase();
  const evidence = row[row.length - 1];
  if (!evidence || /^[-—–]+$/.test(evidence)) {
    return {
      status: 'FAIL',
      problems: [`${STORY_REVIEW_ID} 那一行的证据格是空的——`
        + '空证据与没审长得一样。写一行你逐章过了什么，不必长'],
      detail: '证据格为空',
    };
  }

  if (status !== 'PASS') {
    const missing = DETAIL_KEYS.filter(k => !text.includes(k));
    if (missing.length) {
      return {
        status: 'FAIL',
        problems: [`${STORY_REVIEW_ID} 判了 ${status}，明细里却缺 ${missing.join('、')}——`
          + '两类结论都要在：阻断问题与提醒各归各的键，没有就写成空列表；'
          + '缺席分不清它是没发现还是没审'],
        detail: `缺 ${missing.join('、')}`,
      };
    }
  }

  if (PER_UNIT_TABLE_RE.test(text)) {
    return {
      status: 'FAIL',
      problems: [`${STORY_REVIEW_ID} 的结果里出现了逐单元裁决表——`
        + '这一项不做逐条对账：那张表的量随材料条数涨，而读者拿到的判断不增加。'
        + '要判的是讲了没有、讲清没有、是不是编的'],
      detail: '形态不对：逐单元表',
    };
  }
  return { status: 'PASS', problems: [], detail: `读者审查已落报告（${status}）` };
}
