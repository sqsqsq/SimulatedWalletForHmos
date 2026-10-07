/**
 * Story 独立审查的报告合同 —— 审查任务告诉审查者怎么写、`review --action check` 按它核，两处共用这一份。
 */

export const REPORT_HEADINGS = ['判据核对', '发现', '总体结论'];
export const CHECK_HEADER = ['判据 ID', '结果', '依据'];
export const CHECK_RESULTS = ['pass', 'warn', 'fail', 'not_applicable'];
export const FINDING_HEADER = ['编号', '严重程度', '判据 ID', '材料位置', '问题与依据', '修正责任'];
export const SEVERITIES = ['BLOCKER', 'MAJOR', 'MINOR', 'INFO'];

/** 审查任务里的「报告怎么写」。 */
export function reportFormat() {
  return [
    '', '### 报告怎么写', '',
    '回复就是这份 Markdown 报告，宿主原样存下；格式不合的回复不计结论，要重给。',
    '',
    '1. 第一行写 `material_key: <派审时给的材料键，64 位>`，全文只这一行。',
    `2. 二级标题依次是${REPORT_HEADINGS.map(h => `「${h}」`).join('')}，各恰好一个，标题字照写。`,
    `3. 「${REPORT_HEADINGS[0]}」一张表，表头 \`${CHECK_HEADER.join(' | ')}\`：判据逐项一行，ID 照本任务「判据」各节标题里的写，`
      + `结果写 ${CHECK_RESULTS.join(' / ')}，`,
    '   依据写你据以判断的事实；不适用写业务理由。表后写审查方法：逐章过了什么、仍开着的议题逐条结论、会议话题的去向。',
    `4. 「${REPORT_HEADINGS[1]}」一张表，表头 \`${FINDING_HEADER.join(' | ')}\`：严重程度按判据写 ${SEVERITIES.join(' / ')}；`,
    '   材料位置写「本次审查的材料」里那份文件的路径，可加 `#章节` 或 `:行`：只引一份文件时整格写这条路径，路径含空格照写；',
    '   引多份文件或夹带说明时，每条路径用反引号括起，这一列的反引号只用来括路径。修正责任写该回哪一处改、由谁定。没有发现保留表头、不写行。',
    `5. 「${REPORT_HEADINGS[2]}」第一行写 pass、warn 或 fail 之一，再写理由：有 BLOCKER / MAJOR 或判据 fail 是 fail，只有 MINOR / INFO 或判据 warn 是 warn，`,
    '   其余 pass。审查中某份材料读不到：在「发现」表按相关判据记一条 BLOCKER，写明读不到哪份、哪些判断因此未核；其余能核的照常核。',
  ];
}
