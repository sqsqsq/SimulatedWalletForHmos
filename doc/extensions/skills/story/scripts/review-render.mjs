/**
 * 评审记录（`AR/review.md`）的渲染 —— 机器区确定性重算，人工区逐字节保留。
 *
 * 这套形态是上一轮验证过的、与 story 逐章生产线**无关**的能力，所以在 story-build 重写时
 * 整体移到这里，而不是跟着旧的逐章生产线一起删：
 *
 * - **自解释表单**：只渲染「问题 / 建议或结论 / 为什么 / 影响什么 / 请谁确认 / 三个勾选」，
 *   判据是「需要说明书就是设计错了」——填写说明、签署字段、状态行、编号附录都被裁掉过；
 * - **人工区逐字节保留**：从首个勾选行到 `<!-- decision: ID -->` 之间，build 一个字节都不动。
 *   评审人的表态是人的产物，重算它等于把做完的决定推回去一次；
 * - **计划外意见区**：评审人常有起草方没登记过的意见，套不进任何议题的表单。
 *   回流侧（`review_reflow.md` §1）本来就接得住这类自由意见，产出侧得给它一个地方。
 */
/** 机器区与人工区的分界：这一行之前确定性重渲染，之后逐字节保留。 */
const HUMAN_ZONE_MARK = '#### 审核结果（由评审人填写）';

/** 计划外意见区的边界标记。 */
const FREEFORM_OPEN = '<!-- freeform-zone -->';
const FREEFORM_CLOSE = '<!-- /freeform-zone -->';

/** 单元格内的 `|` 会把表撑破，转义掉；换行折成空格。 */
export function escapeCell(text) {
  return String(text ?? '').replace(/\r?\n/g, ' ').replace(/\|/g, '\|').trim() || '—';
}

/**
 * 议题块的**机器区**：完全由登记表决定，每次 build 确定性重渲染。
 * 已定决策（status=settled）也照样成块——检视人要先看到「有哪些决策、结论是什么」，
 * 才谈得上反馈对不对；已定不等于不必过目。
 */
export function renderMachineZone(dec) {
  const settled = dec.status === 'settled';
  const lines = [`### ${dec.question}`, ''];
  if (settled) {
    lines.push(`- **当前结论**：${dec.conclusion ?? dec.proposal}`);
  } else {
    lines.push(`- **当前建议**：${dec.proposal}`);
  }
  lines.push(
    `- **为什么这样${settled ? '定' : '建议'}**：${dec.rationale}`,
    `- **同意或修改后会影响什么**：${(dec.impact ?? []).join('、') || '—'}`,
    `- **结论来源**：${dec.source}`,
    `- **请谁确认**：${dec.decider}`,
    '');
  return lines.join('\n');
}

/**
 * 议题块的**人工区**：首版为空表单，此后 build 一个字节都不动它。
 *
 * **只有三态勾选与一行说明**。曾经这里还有暂缓责任人、完成期限、是否阻塞执行、
 * 后续动作、确认人、确认日期、确认依据七个字段——判据是「需要说明书就是设计错了」：
 * 评审人打开它先要读一遍字段表，而这七格里六格他答不上来（责任人和期限是排期的事，
 * 确认依据是审计的事）。答不上来的格子只会被跳过或胡填，两种都让「已确认」不可信。
 *
 * 留下的两行说明是**勾选下的人工行**：选了修改要说改什么，选了暂缓要说为什么，
 * 不然那一勾传不出任何信息。
 */
export function renderHumanZone(dec) {
  return [
    HUMAN_ZONE_MARK,
    '',
    '- [ ] **同意当前建议**',
    '- [ ] **有其他意见，需要修改**',
    '  - 修改意见：',
    '- [ ] **暂缓**',
    '  - 暂缓原因：',
    '',
    `<!-- decision: ${dec.id} -->`,
  ].join('\n');
}

/** 从既有 review 里切出某议题的人工区（人工填写内容的唯一真源） */
export function extractHumanZone(reviewText, id) {
  const mark = `<!-- decision: ${id} -->`;
    const end = reviewText.indexOf(mark);
  if (end < 0) return null;
  const zoneStart = reviewText.lastIndexOf(HUMAN_ZONE_MARK, end);
  if (zoneStart < 0) return null;
  return reviewText.slice(zoneStart, end + mark.length);
}

/**
 * 计划外意见区：整段逐字节保留，与议题人工区同等待遇。
 *
 * 评审人常有起草方没登记过的意见——缺的分支、该复用的既有能力、遗漏的埋点。
 * 它们套不进任何议题的表单（没有 `impact`、没有当前建议），
 * 而 `review_reflow.md` §1 已经规定了怎么处置这类「模板外的自由意见」：
 * 判需求类还是叙述类、落台账带 `freeform#<序>` 与原话摘录。
 * 也就是说**回流侧接得住，产出侧却一直没给人写的地方**——本区补的就是那个地方。
 */
export function extractFreeformZone(reviewText) {
  const start = reviewText.indexOf(FREEFORM_OPEN);
  if (start < 0) return null;
  const end = reviewText.indexOf(FREEFORM_CLOSE, start);
  if (end < 0) return null;
  return reviewText.slice(start + FREEFORM_OPEN.length, end);
}

/** 首版的空区：给一句怎么写，不给表单——套不进表单正是它存在的理由。 */
export function renderFreeformSection(inner) {
  return [
    '## 计划外意见（不属于以上任何议题）',
    '',
    '起草方没登记成议题、而你认为该说的事写在这里——缺的分支、该复用的既有能力、',
    '遗漏的埋点都算。一条一段，写清**是什么**与**影响哪里**；不必套用上面的表单。',
    '',
    FREEFORM_OPEN,
    inner ?? '\n（暂无）\n',
    FREEFORM_CLOSE,
    '',
  ].join('\n');
}

/** 定位某议题块的整体范围（机器区起点 → 该块的 decision 标记结尾） */
export function findBlockRange(reviewText, id) {
  const mark = `<!-- decision: ${id} -->`;
  const end = reviewText.indexOf(mark);
  if (end < 0) return null;
  const zoneStart = reviewText.lastIndexOf(HUMAN_ZONE_MARK, end);
  if (zoneStart < 0) return null;
  // 机器区起点：该人工区之前最近的 `### ` 标题
  const headStart = reviewText.lastIndexOf('\n### ', zoneStart);
  return { start: headStart < 0 ? zoneStart : headStart + 1, end: end + mark.length };
}
