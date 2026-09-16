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
import { parseYaml } from './yaml.mjs';

/** 读者审查那一项在报告里的标识 —— 判据 id 本身，不另起一个名字。 */
const STORY_REVIEW_ID = 'story_reader_review';

/** 非 PASS 时明细里必须有的两个键。可以是空列表，但不能缺席。 */
const DETAIL_KEYS = ['blocking_findings', 'advisories'];

/** 汇总表的列数：id / status / severity / 一行证据。列序见框架的输出契约。 */
const SUMMARY_COLUMNS = 4;

/**
 * 报错说给**读报错的那个人**听 —— 他是作者，不是审查员。
 *
 * 报告必须是子代理回复的原样落盘，作者照着报错去补一行、补一个键，补出来的是
 * 伪造的审查证据。所以缺什么都不叫他写，叫他把同一份 request 再投一次。
 */
const INVALID_EVIDENCE =
  '这份回复不是有效证据：把同一份 request 再投给 verifier，拿到完整回复后原样全文落盘。'
  + '**不要自己补**——补出来的不是审查结论。';

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
 * 汇总表里 `story_reader_review` 那一行，原样返回它的格子。
 *
 * 认的是「以 | 分格、第一格是这个 id」的行，不认散落在正文里的同名字样——
 * 后者在讲这一项，不是这一项的结论。**不在这里判够不够格**：格子少了是一种
 * 具体的写法问题，要能与「压根没这一行」分开报。
 */
function summaryRow(text) {
  for (const line of text.split(/\r?\n/)) {
    const raw = line.trim();
    if (!raw.startsWith('|')) continue;
    const cells = raw.split('|').slice(1, -1).map(c => c.trim());
    if (cells.length && cells[0].replace(/`/g, '') === STORY_REVIEW_ID) return cells;
  }
  return null;
}

/** 文档里的 YAML 围栏，一个不落地取出来——报告的结构就写在里面。 */
function yamlBlocks(text) {
  const out = [];
  const fence = /^[ \t]*```[^\n]*\n([\s\S]*?)^[ \t]*```/gm;
  for (let m = fence.exec(text); m; m = fence.exec(text)) out.push(m[1]);
  return out;
}

/**
 * 结构里那一串 check —— 顶层直接是 `checks`，或者包在结果对象里（各认一层）。
 *
 * **只认这个键名，不按形状搜**：形状搜（「任何一个带 id 的数组」）会撞上报告里
 * 别的列表——findings、items 都长这样——撞上了就静默读到另一批东西，而判据全绿。
 */
function checksIn(doc) {
  if (Array.isArray(doc?.checks)) return doc.checks;
  for (const value of Object.values(doc ?? {})) {
    if (Array.isArray(value?.checks)) return value.checks;
  }
  return null;
}

/**
 * 明细里 `story_reader_review` 那一条的 `details` —— **整段解析，按 id 取项**。
 *
 * 整段读、按 id 取，不划文本范围。划范围要靠「到下一条 `- id:` 或围栏结束」这类
 * 启发式，而报告里每条 check 的 `details` 都可能是块标量，块里出现什么字样都是正文——
 * 边界一旦被块里的内容带偏，读出来的就是另一条的结论，判据却照样给出答案。
 *
 * **能读出结构不等于这一条写全了**：`details` 是一段文本（`details: |`）时它下面
 * 没有任何键，照样按缺键报——那正是「没有这两类结论」。
 *
 * @returns {{details: object|null, unreadable: string|null}}
 *   `unreadable` 非空 = 这份 YAML 读不出结构，与「缺键」是两回事，要分开报。
 */
function readerReviewDetails(text) {
  let unreadable = null;
  for (const body of yamlBlocks(text)) {
    let doc;
    try {
      doc = parseYaml(body);
    } catch (e) {
      unreadable = unreadable ?? String(e?.message ?? e);
      continue;
    }
    const checks = checksIn(doc);
    if (!checks) continue;
    const entry = checks.find(c => c
      && String(c.id ?? '').replace(/`/g, '').trim() === STORY_REVIEW_ID);
    if (!entry) continue;
    const details = entry.details;
    return {
      details: details && typeof details === 'object' && !Array.isArray(details) ? details : {},
      unreadable: null,
    };
  }
  return { details: null, unreadable };
}

/**
 * 读者审查这一项做了没有、写成什么形态。
 *
 * @returns {{status: string, problems: string[], detail: string}}
 */
export function storyReviewProblems(projectRoot, feature, phase) {
  const { summaryFound, abs } = reportLocation(projectRoot, feature, phase);
  if (!summaryFound) {
    return { status: 'NOT_APPLICABLE', problems: [], reviewVerdict: null,
      detail: 'harness 尚未运行，本项还轮不到判' };
  }
  if (!abs) {
    return {
      status: 'NOT_APPLICABLE',
      problems: [],
      reviewVerdict: null,
      detail: '本宿主没有登记审查员（verifier 未启用），本轮没有报告可核',
    };
  }
  const text = readTextOrNull(abs);
  if (text === null) {
    return {
      status: 'FAIL',
      problems: [`verifier 报告不在落点上：${abs}——`
        + '把 verifier 的回复**原样全文**重新写到 `summary.verifier_report` 指向的那份文件；'
        + '没有它，读者审查有没有执行无从核对'],
      reviewVerdict: null,
      detail: '报告缺席',
    };
  }

  const row = summaryRow(text);
  if (!row) {
    return {
      status: 'FAIL',
      problems: [`verifier 报告的汇总表里没有 ${STORY_REVIEW_ID} 这一行——`
        + '这一项是 story 语义质量的发现者，汇总表里找不到它就等于这一轮没审。'
        + INVALID_EVIDENCE],
      reviewVerdict: null,
      detail: '汇总表缺行',
    };
  }
  // 汇总表四列（id / status / severity / 证据），列序见框架的输出契约。
  // 证据取第 4 格：格数不够就是这一行少了证据列，与「压根没这一行」分开报。
  if (row.length < SUMMARY_COLUMNS) {
    return {
      status: 'FAIL',
      problems: [`${STORY_REVIEW_ID} 那一行只有 ${row.length} 格，少了证据列——`
        + '汇总表是 id、status、severity、一行证据四格。' + INVALID_EVIDENCE],
      reviewVerdict: null,
      detail: `汇总表只有 ${row.length} 列`,
    };
  }
  const status = row[1].replace(/`|\*/g, '').toUpperCase();
  // **审查自己的结论**：从汇总行那一格规范化取来，不从 detail 的措辞倒猜。
  // 结构完整而审查判了 FAIL 时，这个函数的 `status` 仍是 PASS（报告的结构没问题），
  // 两件事因此要分开返回——交付门看的是 `reviewVerdict`，作者看的是 `problems`。
  const reviewVerdict = status || null;
  const evidence = row[SUMMARY_COLUMNS - 1];
  if (!evidence || /^[-—–]+$/.test(evidence)) {
    return {
      status: 'FAIL',
      problems: [`${STORY_REVIEW_ID} 那一行的证据格是空的——`
        + '空证据与没审长得一样。' + INVALID_EVIDENCE],
      reviewVerdict,
      detail: '证据格为空',
    };
  }

  if (status !== 'PASS') {
    const { details, unreadable } = readerReviewDetails(text);
    if (unreadable) {
      // 读不出结构与「缺这两个键」是两回事：说成缺键的话，作者会去补两个已经写着的键，
      // 补完还报，他只能去翻这个脚本。
      return {
        status: 'FAIL',
        problems: [`verifier 报告里的结构块读不出来（${unreadable}）——`
          + `${STORY_REVIEW_ID} 的两类结论在那份结构里，读不出就核不了。`
          + '把 verifier 的回复原样重写一遍，结构块写成合法 YAML。' + INVALID_EVIDENCE],
        reviewVerdict,
      detail: '结构块读不出来',
      };
    }
    const missing = DETAIL_KEYS.filter(k => !(k in (details ?? {})));
    if (missing.length) {
      return {
        status: 'FAIL',
        problems: [`${STORY_REVIEW_ID} 判了 ${status}，它自己的明细里缺 ${missing.join('、')}——`
          + '两类结论都要在这一条的 `details` 下：阻断问题与提醒各归各的键，'
          + '没有就写成空列表；缺席分不清它是没发现还是没审。' + INVALID_EVIDENCE],
        reviewVerdict,
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
      reviewVerdict,
      detail: '形态不对：逐单元表',
    };
  }
  return { status: 'PASS', problems: [], reviewVerdict,
    detail: `读者审查已落报告（${status}）` };
}
