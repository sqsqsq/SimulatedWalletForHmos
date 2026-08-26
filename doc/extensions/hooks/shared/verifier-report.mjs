/**
 * 逐行裁决落盘核对 —— 必答清单注入了，还得证明它被裁了。
 *
 * ## 为什么这条判据挂在 post_check 上
 *
 * 阶段闭环是框架定义的三步：harness 首跑 → verifier 子 agent 语义审查 → **主 agent 重跑 harness 回填凭证**。
 * post_check 在每次 harness 运行时执行，所以回填那一次运行必然看得到 verifier 的报告。
 * 首跑时报告还不存在，本判据记 `NOT_APPLICABLE`——那不是通过，是「还轮不到判」。
 *
 * ## 判据
 *
 * 必答集的每个键，都要在报告里找到**同一行**既含这个键、又含一个裁决词。
 * 只在 YAML 输出里裁不算：那份输出不落盘，事后无从复核；实测出现过整份清单一条没裁
 * 而 harness 照收 PASS。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { adjudicationKeys, adjudicationSet } from './adjudication.mjs';
import { featureRoot, readTextOrNull } from './paths.mjs';

/** verifier 报告的文件名形态（与测试域回归脚本同一组名）。 */
const REPORT_NAME_RES = [
  /^verifier\.report\.md$/i,
  /^verifier-.*\.md$/i,
  /^verify-.*\.md$/i,
  /^verifier-.*-result\.ya?ml$/i,
];

/** 裁决词：一行里出现任一个才算这条被裁过。 */
const VERDICT_RE = /(PASS|FAIL|WARN|不适用|设计|复述)/;

/** 报告目录下所有 verifier 报告的绝对路径。 */
function verifierReports(projectRoot, feature, phase) {
  const dir = path.join(featureRoot(projectRoot, feature), phase, 'reports');
  // 目录不存在 = verifier 还没执行，是合法状态；目录在却读不动是异常，
  // 让它抛出去由调用方判 FAIL——吞掉的话「读失败」会伪装成「还没跑」。
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter(n => REPORT_NAME_RES.some(re => re.test(n)))
    .map(n => path.join(dir, n));
}

/**
 * 核对逐行裁决是否落盘。
 *
 * @returns {{status: string, problems: string[], detail: string}}
 *   status: PASS / FAIL / NOT_APPLICABLE；problems 非空即 BLOCKER 级问题。
 */
export function adjudicationProblems(ctx, knowledge) {
  const { rows, error } = adjudicationSet(ctx.projectRoot, ctx.feature, ctx.phase, knowledge);
  if (error) {
    return {
      status: 'FAIL',
      problems: [`必答集派生失败：${error}——派生不出清单就无从核对逐行裁决，不能当作通过`],
      detail: error,
    };
  }
  const keys = adjudicationKeys(rows);
  if (!keys.length) {
    return {
      status: 'FAIL',
      problems: ['必答集为零行——本阶段没有任何知识判定行可裁，先确认判定是不是漏做了'],
      detail: '零行',
    };
  }

  const reports = verifierReports(ctx.projectRoot, ctx.feature, ctx.phase);
  if (!reports.length) {
    return {
      status: 'NOT_APPLICABLE',
      problems: [],
      detail: `verifier 尚未执行（${ctx.phase}/reports 下没有报告文件），必答 ${keys.length} 行`,
    };
  }

  const text = reports.map(p => readTextOrNull(p) ?? '').join('\n');
  const lines = text.split(/\r?\n/);
  const missing = keys.filter(key => !lines.some(l => l.includes(key) && VERDICT_RE.test(l)));
  if (missing.length) {
    return {
      status: 'FAIL',
      problems: [
        `verifier 报告未逐行裁决：漏 ${missing.join('、')}（必答 ${keys.length} 行，漏 ${missing.length} 行）`
        + '——裁决表要写进报告文件本身，固定表头「| 编号 | 裁决 | 证据 |」，一行一条',
      ],
      detail: `漏 ${missing.length}/${keys.length}`,
    };
  }
  return { status: 'PASS', problems: [], detail: `逐行裁决齐备（${keys.length} 行）` };
}
