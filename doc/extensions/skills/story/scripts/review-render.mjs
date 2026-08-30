/**
 * 评审记录（`AR/review.md`）的渲染 —— 机器区确定性重算，人工区逐字节保留。
 *
 * ## 形态从哪来
 *
 * 形态**从已定稿的效果定义正推**，不是从「上一版长什么样」推。那份定义说：
 * review.md 就是判断的台账——已决策的呈现结果供评审人过目，不确定、矛盾、错误的要人评估。
 * 由此定死五件事：
 *
 * - **三级分层**：一级是**状态**（待确认事项 / 已定事项 / 其他意见，固定三章，
 *   评审人先按「要我拍板的」和「给我过目的」分开读）；二级是**决策内容的类型**
 *   （业务规则、入口与开关、数据与缓存……组内有该类才立章，没有不立空章）；
 *   三级才是具体评审项。分层名一律按人写文档的方式命名，不用「需要你拍板」这类流程腔；
 * - **编号由脚本统一生成**（N. / N.M / N.M.K）：层级式编号是纯确定性变换，
 *   模型只写业务名标题——与 story 侧的 `number` 同一个道理；
 * - **标题是陈述句**（`#### 2.2.1 界面不做像素级还原`）：已定的陈述结论，待定的陈述事项。
 *   疑问句与反问句读起来像考卷，评审人得先把它翻译成「所以你们打算怎么做」；
 * - **正文用小标题分段**，不是把五个字段拼成一串 bullet。上一版渲染
 *   「问题 / 建议 / 为什么 / 影响什么 / 来源 / 请谁确认」六行——那是表单腔，
 *   实测的后果是字段被填成分类名（「来源」填成六类议题的类名）与泛词
 *   （「影响」从「单日上限口径 200 元」塌成「权限模型、接受流程」）；
 * - **人工区只有「审核结果：」一行**，评审人在它后面写具体内容。三态勾选块退场：
 *   勾一个框传不出任何信息，而「要改成什么」本来就得写字。
 *
 * ## 两条不变的机制
 *
 * - **人工区逐字节保留**：从「审核结果：」到 `<!-- decision: ID -->` 之间，build 一个字节都不动。
 *   评审人的表态是人的产物，重算它等于把做完的决定推回去一次；
 * - **计划外意见区**（成章后叫「其他意见」）：评审人常有起草方没登记过的意见，
 *   套不进任何议题。回流侧（`review_reflow.md` §1）本来就接得住这类自由意见，
 *   产出侧得给它一个地方。
 *
 * **给人的提示用可见引用块，机制锚才用 HTML 注释**：HTML 注释在预览里看不见，
 * 拿它承载「怎么填」等于没写。提示全篇只出现两处（顶部一条、其他意见处一条），
 * 不在每个议题里重复。
 */
/** 机器区与人工区的分界：这一行之前确定性重渲染，之后逐字节保留。 */
const HUMAN_ZONE_MARK = '审核结果：';

/** 计划外意见区的边界标记。 */
const FREEFORM_OPEN = '<!-- freeform-zone -->';
const FREEFORM_CLOSE = '<!-- /freeform-zone -->';

/**
 * 一级分层＝状态，固定三章。章名面向人：`待确认事项` 而不是「需要你拍板」。
 * 前两章按 `status` 分（`settled` 与其余两分），第三章是自由反馈区。
 */
const STATUS_CHAPTERS = [
  { key: 'open', title: '待确认事项' },
  { key: 'settled', title: '已定事项' },
];
const FREEFORM_CHAPTER = '其他意见';

/** 顶部提示：全篇怎么填只说这一次。 */
const DOC_HINT = '> 怎么填：第一部分还没定，等你拍板；第二部分已经定了，过目复核即可。'
  + '每条末尾有一行「审核结果：」，把你的意见写在它后面——同意就写「同意」；'
  + '有不同意见，写清楚要改成什么；需要暂缓，写原因。';

/** 其他意见处的提示：它与顶部那条职责不同——那条说怎么表态，这条说怎么补充。 */
const FREEFORM_HINT = '> 以上议题之外你认为该说的事写在这里——缺的分支、该复用的既有能力、'
  + '遗漏的埋点都算。按 1. 2. 3. 编号列举，每条写清是什么、影响哪里。';

/** 归档件的头部：大标题 + 一条可见提示。 */
function renderDocHeader() {
  return `# 评审记录\n\n${DOC_HINT}\n`;
}

/**
 * 议题块的**机器区**：完全由登记表决定，每次 build 确定性重渲染。
 *
 * 已定决策（`status: settled`）也照样成块——评审人要先看到「有哪些决策、结论是什么」，
 * 才谈得上反馈对不对；已定不等于不必过目。
 *
 * `clarification` 是**带小标题分段的正文**，登记时怎么写这里就怎么出：
 * 已定的三段（要定的事 / 根据 / 结论与影响），待定的三段（要定的事 / 可选的做法 / 建议）。
 * 渲染器不拆不拼——拼是表单腔的来源。
 *
 * @param {{id, title, clarification, decider}} dec
 * @param {string} number 三级编号（`1.1.1`），由渲染顺序生成
 */
function renderMachineZone(dec, number) {
  return [
    `#### ${number} ${String(dec.title ?? '').trim()}`,
    '',
    String(dec.clarification ?? '').trim(),
    '',
    `请${String(dec.decider ?? '').trim()}确认。`,
    '',
  ].join('\n');
}

/**
 * 议题块的**人工区**：首版只有「审核结果：」一行，此后 build 一个字节都不动它。
 *
 * 曾经这里是三个勾选框加两行说明，再往前还有暂缓责任人、完成期限、是否阻塞执行、
 * 后续动作、确认人、确认日期、确认依据七个字段。判据是「需要说明书就是设计错了」：
 * 评审人打开它先要读一遍字段表，而那些格子他多半答不上来，答不上来的格子只会被
 * 跳过或胡填。勾选框是同一个问题的轻量版——勾「需要修改」而不写改成什么，
 * 那一勾传不出任何信息；既然要写字，框就是多余的。
 */
function renderHumanZone(dec) {
  return [
    HUMAN_ZONE_MARK,
    '',
    `<!-- decision: ${dec.id} -->`,
  ].join('\n');
}

/**
 * 人工区的起点：`end` 之前最近的一处**行首**「审核结果：」。
 *
 * 必须限定行首：顶部那条给评审人的提示里也写着「审核结果：」四个字（它在教人往哪写），
 * 裸 `lastIndexOf` 会在某个议题的人工区被整段删掉时一路退到那条提示上，
 * 把提示连同前面几个议题当成这一条的人工内容保留下来。
 */
function humanZoneStart(reviewText, end) {
  let at = reviewText.lastIndexOf(HUMAN_ZONE_MARK, end);
  while (at > 0 && reviewText[at - 1] !== '\n') {
    at = reviewText.lastIndexOf(HUMAN_ZONE_MARK, at - 1);
  }
  return at;
}

/** 从既有 review 里切出某议题的人工区（人工填写内容的唯一真源） */
function extractHumanZone(reviewText, id) {
  const mark = `<!-- decision: ${id} -->`;
  const end = reviewText.indexOf(mark);
  if (end < 0) return null;
  const zoneStart = humanZoneStart(reviewText, end);
  if (zoneStart < 0) return null;
  return reviewText.slice(zoneStart, end + mark.length);
}

/**
 * 计划外意见区：整段逐字节保留，与议题人工区同等待遇。
 *
 * 评审人常有起草方没登记过的意见——缺的分支、该复用的既有能力、遗漏的埋点。
 * 它们套不进任何议题（没有对应的决策），
 * 而 `review_reflow.md` §1 已经规定了怎么处置这类「登记之外的自由意见」：
 * 判需求类还是叙述类、落台账带 `freeform#<序>` 与原话摘录。
 * 也就是说**回流侧接得住，产出侧却一直没给人写的地方**——本区补的就是那个地方。
 */
function extractFreeformZone(reviewText) {
  const start = reviewText.indexOf(FREEFORM_OPEN);
  if (start < 0) return null;
  const end = reviewText.indexOf(FREEFORM_CLOSE, start);
  if (end < 0) return null;
  return reviewText.slice(start + FREEFORM_OPEN.length, end);
}

/**
 * 首版的空区：标题不带括号说明，区内不放占位。
 *
 * 「（暂无）」这类括号占位曾经放在这里，它的作用只有一个——让空的地方看起来
 * 像是填过了。评审人要写的时候还得先把它删掉。
 *
 * @param {string|null} inner 既有内容（逐字节保留）
 * @param {number} no 章序（固定三章里的第三章）
 */
function renderFreeformSection(inner, no = STATUS_CHAPTERS.length + 1) {
  const body = inner === null || inner === undefined ? '\n\n' : inner;
  return `## ${no}. ${FREEFORM_CHAPTER}\n\n${FREEFORM_HINT}\n\n`
    + `${FREEFORM_OPEN}${body}${FREEFORM_CLOSE}\n`;
}

/**
 * 类型 → 成章的自然名。
 *
 * 十一类词表有两个形态：扫描指引用原名（`安全隐私与合规落地`，带触发特征与问句），
 * 成章用自然名（`安全与隐私`）。映射是合同数据，渲染器不认识任何一个具体类别。
 * 词表里没有的类别原样成章——那是 `check` 要点名的事，渲染不替它遮掩。
 */
function sectionNameOf(category, categories) {
  const hit = (categories ?? []).find(c => c && c.key === category);
  return (hit && hit.section) || String(category ?? '').trim();
}

/**
 * 按「状态 → 类型」分组。
 *
 * 组内类型的顺序＝该类型在登记表里第一次出现的顺序：登记表是作者的作业顺序，
 * 按它排，作者读得出自己写的东西在哪。**有才立章**——空类别不立，也不解释为什么空。
 */
function groupByCategory(list, categories) {
  const groups = [];
  const index = new Map();
  for (const dec of list) {
    const name = sectionNameOf(dec.category, categories);
    if (!index.has(name)) {
      index.set(name, groups.length);
      groups.push({ name, items: [] });
    }
    groups[index.get(name)].items.push(dec);
  }
  return groups;
}

/**
 * 渲染整篇 review。
 *
 * @param {{id, title, clarification, decider, status, category}[]} list 登记表
 * @param {string} previous 既有 review 全文（人工区从这里逐字节取回）
 * @param {{key:string, section:string}[]} categories 合同的类型词表
 * @returns {string}
 */
export function renderReview(list, previous = '', categories = []) {
  const old = String(previous ?? '');
  const decisions = Array.isArray(list) ? list.filter(Boolean) : [];
  const out = [renderDocHeader()];

  STATUS_CHAPTERS.forEach((chapter, ci) => {
    const no = ci + 1;
    const mine = decisions.filter(d => (
      chapter.key === 'settled' ? d.status === 'settled' : d.status !== 'settled'));
    const parts = [`## ${no}. ${chapter.title}\n`];
    groupByCategory(mine, categories).forEach((group, gi) => {
      parts.push(`### ${no}.${gi + 1} ${group.name}\n`);
      group.items.forEach((dec, ii) => {
        const human = extractHumanZone(old, dec.id) ?? renderHumanZone(dec);
        parts.push(`${renderMachineZone(dec, `${no}.${gi + 1}.${ii + 1}`)}\n${human}\n`);
      });
    });
    out.push(parts.join('\n'));
  });

  out.push(renderFreeformSection(extractFreeformZone(old)));
  return out.join('\n');
}
