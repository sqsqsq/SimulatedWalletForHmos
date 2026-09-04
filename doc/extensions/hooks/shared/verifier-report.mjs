/**
 * verifier 报告落盘核对 —— 语义审查做了没有，看它有没有留下报告。
 *
 * ## 为什么这条判据挂在 post_check 上
 *
 * 阶段闭环是框架定义的三步：harness 第一次运行 → verifier 子 agent 语义审查 → **主 agent 重跑 harness 回填凭证**。
 * post_check 在每次 harness 运行时执行，所以回填那一次运行必然看得到 verifier 的报告。
 * 第一次运行时报告还不存在，本判据记 `NOT_APPLICABLE`——那不是通过，是「还轮不到判」。
 *
 * ## 判的是形态，不是内容
 *
 * 只问「结果块在不在、两类结论齐不齐、有没有退回逐条对账表」。审查得对不对由人抽查——
 * 不核逐行裁决表、不核引文长度：那类要求逼出的是把清单里的字抄进证据列，
 * 而不是判断。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { extensionRoot, featureRoot, readTextOrNull } from './paths.mjs';

/**
 * verifier 报告落在哪 —— **只认发布器按 subject 落盘的那一份**。
 *
 * 宿主 adapter 声明了 `verifier_capability`（`publisher: subagent_stop` 或插件）时，
 * 报告不由 verifier 自己写，而是钩子从子 agent 的**终态消息**生成，按 subject 分区落盘
 * `verifier.report.<64位subject>.json`（＋同名 .md 人读投影，机器侧不解析）。
 *
 * 早先这里还认执行方自己写的几种文件名，理由是「没有发布器的宿主也得能用」。
 * 那条路的代价是：主模型可以自己把一段文本写成报告文件，门照收。
 * **主模型写得出来的东西，作不了它被独立审查过的证据**——收下它，判据就成了自证。
 *
 * 收紧的代价如实说：没有发布器的宿主上，这一项从此记 NOT_APPLICABLE。
 * 「这台宿主证明不了」比「收一份可伪造的证明」诚实。
 */
const REPORT_JSON_RE = /^verifier\.report\.[0-9a-f]{64}\.json$/i;

/** JSON 里承载 verifier 结论正文的字段（record-verifier-report.mjs 的 `report_text`）。 */
const REPORT_TEXT_FIELD = 'report_text';

/** story 审查那一项在报告里的块标记 —— 判据 id 本身，不另起一个名字。 */
const STORY_REVIEW_ID = 'story_reader_review';

/** 结果块里必须有的两个小节。可以是空列表，但不能缺席。 */
const STORY_REVIEW_SECTIONS = ['blocking_findings', 'advisories'];

/**
 * 逐单元裁决表的表头特征 —— 新审查任务明说不出这张表，出了就是**做成了另一件事**。
 *
 * 认表头不认内容：表头是明确记号，判它不需要读懂任何一句话。
 */
const PER_UNIT_TABLE_RE = /\|\s*单元键\s*\|/;

/** 报告目录下发布器落盘的那些 verifier 报告。 */
function verifierReportFiles(projectRoot, feature, phase) {
  const dir = path.join(featureRoot(projectRoot, feature), phase, 'reports');
  // 目录不存在 = verifier 还没执行，是合法状态；目录在却读不动是异常，
  // 让它抛出去由调用方判 FAIL——吞掉的话「读失败」会伪装成「还没跑」。
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter(n => REPORT_JSON_RE.test(n))
    .map(n => path.join(dir, n));
}

/**
 * 取出各报告的结论正文 —— 发布器 JSON 的 `report_text` 字段。
 *
 * 一个阶段可能有多份报告（换代、并发、多 subject），全收集合并判——
 * 少收一份就可能把「审过了」判成「没审」。
 *
 * 解析不动或没有正文字段的文件**记名单独报出**，不静默跳过：
 * 那与「verifier 没跑」是两回事，混在一起就没法查。
 */
function reportTexts(files) {
  const texts = [];
  const unreadable = [];
  for (const file of files) {
    const raw = readTextOrNull(file);
    let doc = null;
    try {
      doc = raw === null ? null : JSON.parse(raw);
    } catch {
      doc = null;
    }
    const body = typeof doc?.[REPORT_TEXT_FIELD] === 'string' ? doc[REPORT_TEXT_FIELD] : null;
    if (body === null) unreadable.push(path.basename(file));
    else texts.push(body);
  }
  return { texts, unreadable };
}

/**
 * story 审查执行了没有 —— **只核形态，不核内容**。
 *
 * ## 为什么要有它
 *
 * 判据注入了 verifier 的上下文，不等于它被执行——注入的判据一条没答而 harness
 * 照收 PASS，是这条判据要拦的形态。story 审查在作者路径切换之后是 story 语义质量的唯一发现者，
 * 同一形态在这里重演的代价更大——没人会知道那一轮根本没审。
 *
 * ## 判什么
 *
 * 报告里要有这一项的结果块（以判据 id 为标记），块里要有 `blocking_findings` 与
 * `advisories` 两个小节。**空列表是合法结论**：审过而没发现问题，与没审是两件事，
 * 前者留得下痕迹。块里出现逐单元裁决表的表头则点名——那说明它做成了另一件事。
 *
 * 不数条数、不判内容：报几条、报得对不对，是资格门用成对样本量的事，不是门禁能判的。
 *
 * @returns {{status: string, problems: string[], detail: string}}
 */
export function storyReviewProblems(ctx, storyPath) {
  if (!storyPath || readTextOrNull(storyPath) === null) {
    return { status: 'NOT_APPLICABLE', problems: [], detail: 'AR/story.md 不在，本项不适用' };
  }
  const files = verifierReportFiles(ctx.projectRoot, ctx.feature, ctx.phase);
  if (!files.length) {
    return { status: 'NOT_APPLICABLE', problems: [], detail: 'verifier 尚未执行' };
  }
  const { texts, unreadable } = reportTexts(files);
  if (unreadable.length) {
    return {
      status: 'FAIL',
      problems: [`verifier 报告读不出结论正文：${unreadable.join('、')}——`
        + 'story 审查有没有执行因此无从核对'],
      detail: `不可解析 ${unreadable.length}/${files.length}`,
    };
  }
  const text = texts.join('\n');
  if (!text.includes(STORY_REVIEW_ID)) {
    return {
      status: 'FAIL',
      problems: [`verifier 报告里没有 ${STORY_REVIEW_ID} 的结果块——`
        + '这一项是 story 语义质量的发现者，报告里找不到它就等于这一轮没审。'
        + `把结果写成以 ${STORY_REVIEW_ID} 为标记的一块，块内两个小节：`
        + `${STORY_REVIEW_SECTIONS.join(' 与 ')}；没有发现就写成空列表，空列表是结论`],
      detail: '缺结果块',
    };
  }
  // 块的范围：从标记那一行到下一个二级以上标题，或到文末。范围判宽一点没关系——
  // 这里只找两个小节名，找宽了不会把别处的东西误认成结论。
  const from = text.indexOf(STORY_REVIEW_ID);
  const rest = text.slice(from);
  const nextHeading = rest.search(/\n#{1,3}\s/);
  const block = nextHeading > 0 ? rest.slice(0, nextHeading) : rest;

  const missing = STORY_REVIEW_SECTIONS.filter(s => !block.includes(s));
  if (missing.length) {
    return {
      status: 'FAIL',
      problems: [`${STORY_REVIEW_ID} 的结果块缺小节：${missing.join('、')}——`
        + '两类结论都要在：没有阻断问题时写成空列表，那是「审过、没发现」的痕迹；'
        + '缺席分不清它是没发现还是没审'],
      detail: `缺 ${missing.join('、')}`,
    };
  }
  if (PER_UNIT_TABLE_RE.test(block)) {
    return {
      status: 'FAIL',
      problems: [`${STORY_REVIEW_ID} 的结果块里出现了逐单元裁决表——`
        + '这一项不做逐条对账：那张表的量随材料条数涨，而读者拿到的判断不增加。'
        + '要判的是讲了没有、讲清没有、是不是编的，按两类结论写'],
      detail: '形态不对：逐单元表',
    };
  }
  return { status: 'PASS', problems: [], detail: 'story 审查已落报告，两类结论齐备' };
}
