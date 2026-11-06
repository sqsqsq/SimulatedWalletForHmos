/**
 * Story 独立审查的报告合同 —— 审查任务告诉审查者怎么写、`review --action check` 按它核，两处共用这一份。
 */

export const REPORT_HEADINGS = ['审查范围与依据', '发现', '总体结论'];
export const FINDING_HEADER = ['编号', '严重程度', '材料位置', '问题与依据', '修正责任'];
export const SEVERITIES = ['BLOCKER', 'MAJOR', 'MINOR', 'INFO'];
//: 「审查范围与依据」节末尾恰好一个 YAML 块：顶层键与它的四个键
export const SCOPE_KEY = 'review_scope';
export const SCOPE_KEYS = ['kind', 'basis_report', 'unreviewed', 'additional_inputs'];
//: full 承担完整业务核查范围；focused 只在有可信前轮报告作依据的复核里用
export const SCOPE_KINDS = ['full', 'focused'];

/** 审查任务里的「报告怎么写」。 */
export function reportFormat() {
  return [
    '', '### 报告怎么写', '',
    '这份 Markdown 报告就是你的最终回复：主执行者把它原样写到派审载体给的回复位置，它是审查原件；你只读材料，不写任何文件。'
      + '回复从 `material_key` 那一行开始、到「总体结论」的理由结束，整篇不包代码围栏，前后不加说明。格式不合的回复不计结论，原件保留，另给一份新回复。',
    '',
    '1. 第一行写 `material_key: <派审时给的材料键，64 位>`，全文只这一行。',
    `2. 二级标题依次是${REPORT_HEADINGS.map(h => `「${h}」`).join('')}，各恰好一个，标题字照写。`,
    `3. 「${REPORT_HEADINGS[0]}」先用自然段写：首读结论（只读 Story 时读出了什么、哪里读不懂、要回头找或前后说法不一），`
      + '这次实际做的工作（首次完整审查、集中复核或报告补正；复核写明依据的前轮报告、核了哪些受影响的关系），'
      + '有效人答与仍开着的选择对行为判断的影响（每条仍开着的选择一句有据结论），会议话题的去向，回查了哪些设计与知识、为什么。'
      + '不重抄材料库存与判据。',
    `   本节最后放恰好一个 YAML 围栏块，顶层键 \`${SCOPE_KEY}:\`，下面四个键都要写：`
      + '`kind` 写 full（这份报告承担完整业务核查）或 focused（复核时只核受影响的范围）；'
      + '`basis_report` focused 时写前轮上下文给出的那份报告路径，full 写 null；'
      + '`unreviewed` 列这次判断需要却没核到的输入或职责，每项 `{path: <路径>, reason: <原因>}` 或 `{check: <没核的职责>, reason: <原因>}`，'
      + '用不着的技术参考不列；`additional_inputs` 列材料表之外为核实实际读过的文件，每项 `{path: <路径>, purpose: <用途>}`。没有内容的键写 `[]`。',
    '   首次审查与派审载体没有前轮上下文时写 full。前轮上下文给了可作依据的报告、而这次只需核受影响的部分时可以写 focused；'
      + '依据读不清、覆盖不了这次的变化或影响界限说不清时写 full，按完整业务核查做。报告补正沿被补报告原来的 kind 与 basis_report。',
    `4. 「${REPORT_HEADINGS[1]}」一张表，表头 \`${FINDING_HEADER.join(' | ')}\`：严重程度按判据写 ${SEVERITIES.join(' / ')}；`,
    '   材料位置写「本次审查的材料」或 additional_inputs 里那份文件的路径，可加 `#章节` 或 `:行`：只引一份文件时整格写这条路径，路径含空格照写；',
    '   引多份文件或夹带说明时，每条路径用反引号括起，这一列的反引号只用来括路径。修正责任写该回哪一处改、由谁定。'
      + '每条发现只写这一次，编号不在别处重抄。没有发现保留表头与分隔行、不写行。',
    `5. 「${REPORT_HEADINGS[2]}」第一行写 pass、warn 或 fail 之一，再写理由：有 BLOCKER / MAJOR，或 unreviewed 里有图面延期之外的项，是 fail；`,
    '   只有 MINOR / INFO，或只有任务允许延期的图面未核，是 warn；其余 pass。审查中某份必要材料读不到：写进 unreviewed 并说明哪些判断因此未核，其余能核的照常核。',
  ];
}
