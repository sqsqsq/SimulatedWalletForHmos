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

/** 引文的最短长度。太短的片段在任何产物里都能碰巧命中，证明不了读过。 */
const MIN_QUOTE = 12;

/** 规范化：去空白、markdown 强调与反引号——引文与原文的差别不该卡在排版上。 */
function normalizeQuote(s) {
  return String(s ?? '').replace(/[`*_]/g, '').replace(/\s+/g, '').trim();
}

/**
 * 引文核实 —— 裁决附的引文，必须真的来自目标产物。
 *
 * 实测的失效形态：verifier 报告 272 行证据只有 14 种字符串，全是被检文本的**回声**——
 * 把清单里给的那句话抄进证据列，零条「落点错/漏了」。同行含键 + 有裁决词就放行的判据，
 * 对这种回声完全没有区分力。
 *
 * 所以这里核三件事：引文非空且够长、是目标产物的子串、一行只裁一个对象。
 * 任一不成立 → 该对象记「未裁」（不是 FAIL——它可能真的没问题，但这次没有证据说它被裁过）。
 *
 * @param {string[]} keys 待裁对象
 * @param {string[]} reportLines verifier 报告的行
 * @param {string[]} targetTexts 目标产物全文（引文须出自其中之一）
 * @returns {{unadjudicated: {key: string, why: string}[], verified: number}}
 */
export function evidenceVerified(keys, reportLines, targetTexts) {
  const targets = targetTexts.map(normalizeQuote).filter(Boolean);
  const unadjudicated = [];
  let verified = 0;

  for (const key of keys) {
    const rows = reportLines.filter(l => l.includes(key) && VERDICT_RE.test(l));
    if (!rows.length) {
      unadjudicated.push({ key, why: '报告里没有既含它又含裁决词的行' });
      continue;
    }
    // 一行列全部键 + 一个「成立」即全过，是实测出现过的逃逸；一行只能裁一个对象
    const row = rows.find(l => keys.filter(k => l.includes(k)).length === 1);
    if (!row) {
      unadjudicated.push({ key, why: '它所在的那一行同时列了多个对象——一行只能裁一个' });
      continue;
    }
    const cells = row.split('|').map(c => c.trim()).filter(Boolean);
    const quote = cells.slice(1).sort((a, b) => b.length - a.length)[0] ?? '';
    const norm = normalizeQuote(quote);
    if (norm.length < MIN_QUOTE) {
      unadjudicated.push({ key, why: `引文只有 ${norm.length} 字（要求 ≥${MIN_QUOTE}）——太短的片段证明不了读过产物` });
      continue;
    }
    if (!targets.some(t => t.includes(norm))) {
      unadjudicated.push({ key, why: '引文在目标产物里检索不到——把清单里的字抄一遍不算裁决，那只是回声' });
      continue;
    }
    verified++;
  }
  return { unadjudicated, verified };
}

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
 * @param {string[]} [targetPaths] 目标产物的绝对路径——引文须出自其中之一。
 *   不传就退回旧口径（只查裁决词），并在 detail 里声明「引文未核实」：
 *   静默降级会让本判据恒真，那正是它要防的事。
 * @returns {{status: string, problems: string[], detail: string}}
 *   status: PASS / FAIL / NOT_APPLICABLE；problems 非空即 BLOCKER 级问题。
 */
export function adjudicationProblems(ctx, knowledge, targetPaths) {
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

  // 引文核实：光有裁决词不算裁过，引文得真的来自目标产物（否则就是回声）
  const targets = (targetPaths ?? []).map(p => readTextOrNull(p) ?? '').filter(Boolean);
  if (!targets.length) {
    // 没有可比对的目标就只能退回旧口径，并**说出来**——静默降级会让本判据恒真
    const missing = keys.filter(key => !lines.some(l => l.includes(key) && VERDICT_RE.test(l)));
    return missing.length
      ? { status: 'FAIL', detail: `漏 ${missing.length}/${keys.length}`,
          problems: [`verifier 报告未逐行裁决：漏 ${missing.join('、')}`
            + '——裁决表要写进报告文件本身，固定表头「| 编号 | 裁决 | 引文 |」，一行一条'] }
      : { status: 'PASS', problems: [],
          detail: `逐行裁决齐备（${keys.length} 行）；**引文未核实**——读不到目标产物` };
  }

  const { unadjudicated, verified } = evidenceVerified(keys, lines, targets);
  if (unadjudicated.length) {
    const shown = unadjudicated.slice(0, 5).map(u => `${u.key}（${u.why}）`);
    return {
      status: 'FAIL',
      problems: [
        `verifier 报告有 ${unadjudicated.length}/${keys.length} 个对象未裁：${shown.join('；')}`
        + (unadjudicated.length > 5 ? `……另 ${unadjudicated.length - 5} 个` : '')
        + '——裁决表写进报告文件本身，固定表头「| 编号 | 裁决 | 引文 |」，一行一条；'
        + '引文抄目标产物里的原话，不是把清单里的字复制一遍',
      ],
      detail: `未裁 ${unadjudicated.length}/${keys.length}`,
    };
  }
  return { status: 'PASS', problems: [], detail: `逐行裁决齐备且引文可核实（${verified} 行）` };
}
