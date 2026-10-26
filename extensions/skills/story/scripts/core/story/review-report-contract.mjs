/**
 * Story 独立审查的报告合同 —— 审查任务告诉审查者怎么写、`review --action check` 按它核，两处共用这一份。
 */

export const REPORT_HEADINGS = ['判据核对', '发现', '总体结论'];
export const CHECK_HEADER = ['判据 ID', '结果', '依据'];
export const CHECK_RESULTS = ['pass', 'warn', 'fail', 'not_applicable'];
export const FINDING_HEADER = ['编号', '严重程度', '判据 ID', '材料位置', '问题与依据', '修正责任'];
export const SEVERITIES = ['BLOCKER', 'MAJOR', 'MINOR', 'INFO'];
//: 「判据核对」节末尾的输入覆盖声明：恰好一个 YAML 块，顶层键与四个列表键
export const COVERAGE_KEY = 'review_coverage';
export const COVERAGE_KEYS = ['blocking_findings', 'advisories', 'examined_inputs', 'unreviewed'];

/** 审查任务里的「报告怎么写」。 */
export function reportFormat() {
  return [
    '', '### 报告怎么写', '',
    '这份 Markdown 报告就是你的最终回复：主执行者把它原样写到派审载体给的回复位置，它是审查原件；你只读材料，不写任何文件。'
      + '格式不合的回复不计结论，原件保留，另给一份新回复。',
    '',
    '1. 第一行写 `material_key: <派审时给的材料键，64 位>`，全文只这一行。',
    `2. 二级标题依次是${REPORT_HEADINGS.map(h => `「${h}」`).join('')}，各恰好一个，标题字照写。`,
    `3. 「${REPORT_HEADINGS[0]}」一张表，表头 \`${CHECK_HEADER.join(' | ')}\`：判据逐项一行，ID 照本任务「判据」各节标题里的写，`
      + `结果写 ${CHECK_RESULTS.join(' / ')}，`,
    '   依据写你据以判断的事实；不适用写业务理由。表后先写首读结论（只读 Story 时读者读出了什么、哪里读不懂、要回头找或前后说法不一），'
      + '再写审查方法：逐章过了什么、仍开着的议题逐条结论、会议话题的去向。',
    `   本节最后放恰好一个 YAML 围栏块，顶层键 \`${COVERAGE_KEY}:\`，下面四个键都是列表：\`blocking_findings\` 列「${'发现'}」表里`
      + ' BLOCKER / MAJOR 的编号，`advisories` 列 MINOR / INFO 的编号——只写编号，不重复事实；`examined_inputs` 逐份写你实际读过的'
      + '「本次审查的材料」里的路径（照抄写法，为核实额外读过的文件也可以列）；`unreviewed` 写没读到、没读完或判不了的，'
      + '每项 `{path: <路径>, reason: <原因>}` 或 `{check: <判据 ID>, reason: <原因>}`。材料表的每一份要么在 examined_inputs、要么在 unreviewed；'
      + '必审没核完不能写 pass 或 warn。没有内容的键写 `[]`。',
    `4. 「${REPORT_HEADINGS[1]}」一张表，表头 \`${FINDING_HEADER.join(' | ')}\`：严重程度按判据写 ${SEVERITIES.join(' / ')}；`,
    '   材料位置写「本次审查的材料」里那份文件的路径，可加 `#章节` 或 `:行`：只引一份文件时整格写这条路径，路径含空格照写；',
    '   引多份文件或夹带说明时，每条路径用反引号括起，这一列的反引号只用来括路径。修正责任写该回哪一处改、由谁定。没有发现保留表头、不写行。',
    `5. 「${REPORT_HEADINGS[2]}」第一行写 pass、warn 或 fail 之一，再写理由：有 BLOCKER / MAJOR 或判据 fail 是 fail，只有 MINOR / INFO 或判据 warn 是 warn，`,
    '   其余 pass；判据写 fail 时，「发现」表里要有阻断它的 BLOCKER / MAJOR。审查中某份材料读不到：在「发现」表按相关判据记一条 BLOCKER，写明读不到哪份、哪些判断因此未核；其余能核的照常核。',
  ];
}
