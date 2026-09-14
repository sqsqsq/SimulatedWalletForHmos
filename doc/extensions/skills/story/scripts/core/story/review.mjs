/**
 * 决策登记与评审记录 —— 登记表怎么读、review.md 怎么渲染、人工区怎么保住。
 *
 * 评审记录是判断的台账，而判断在成文过程中还会长出来：顺序（先成文再渲染）本身
 * 就是一条判据，写在这里。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fail, readJson, readText } from './context.mjs';
import { appendixChapter } from './appendix.mjs';
import {
  normalizeHeading, ProjectionConflict, projectionDigest, recordedDigest,
} from './document.mjs';

/**
 * 一条决策登记要写满的字段，与「缺了会怎样」。
 *
 * 导出，因为作者任务包要照它列——字段名在校验里写一遍、在提示词里再写一遍，
 * 就是两份真源，改了一处另一处静默过期。
 */
export const DECISION_FIELDS = [
  ['title', '陈述句标题（已定的陈述结论，待定的陈述事项）'],
  ['clarification', '带小标题分段的澄清正文'],
  ['decider', '请谁确认'],
];

/**
 * 评审记录里不该出现的行 —— 每一样都被裁掉过，每一样都以「更规范」的名义长回来。
 *
 * 判的是**行首形态**而不是词：`确认人：` 是签署字段，而评审人在自己的意见里写
 * 「这条要找确认人」是正常的话。只判机器渲染出来的那种独立字段行。
 */
const REVIEW_BANNED_LINES = [
  { name: '如何填写', re: /^#{1,6}?\s*\**\s*(?:如何填写|填写说明|使用说明)/ },
  { name: '确认人', re: /^[-*]?\s*\**确认人\**\s*[:：]/ },
  { name: '确认日期', re: /^[-*]?\s*\**确认日期\**\s*[:：]/ },
  { name: '确认依据', re: /^[-*]?\s*\**确认依据\**\s*[:：]/ },
  { name: '状态行', re: /^[-*]?\s*\**状态\**\s*[:：]/ },
  { name: '下一步', re: /^#{1,6}?\s*\**\s*下一步\**\s*[:：]?\s*$/ },
];

/**
 * 登记表里的条目 —— **两种写法都收，认不出来返回 null**。
 *
 * `{"decisions": [ … ]}` 是骨架给的形状；顶层直接写 `[ … ]` 是把它当一个列表，
 * JSON 里那是同样自然的直觉。两种都能无歧义读出同一批条目，认它不算纵容。
 *
 * **认不出来时不返回空数组**：空数组与「一条都没登记」同形，而后者是合法状态
 * （骨架刚建完就是零条）。混成一件的代价是整类失效没有声音——渲染器照常跑完、
 * 打印「已渲染 0 个议题」、退出码 0，而评审人打开的是一份空模板。
 *
 * 宽进有边界：单数 `decision`、空壳 `{}` 这类不猜，交给调用方报错说清形状。
 */
function decisionList(raw) {
  if (Array.isArray(raw)) return raw;
  if (raw && typeof raw === 'object' && Array.isArray(raw.decisions)) return raw.decisions;
  return null;
}

//: 登记表形状不对时说什么 —— 五个读点同一句，形状只在这里描述一次。
const DECISION_SHAPE = '读不出条目：顶层要么是 `{"decisions": [ … ]}`，要么直接是 `[ … ]`'
  + '——`skeleton` 起手时不存在就建一份空骨架，照它的形状填';

/**
 * 归档件禁用词在 `review.md` 上的**作用域**：把不判的那几段抹成空行。
 *
 * 抹而不是跳过，是为了让行号不变——报错要指得回原文的那一行。
 *
 * 红线管的是**这份文档对产品的承诺**。review 里有两片地方不是承诺：
 *
 * | 不判的 | 为什么 |
 * |---|---|
 * | 人工区（`审核结果：` 之后到该议题的结束标记） | 那是**人的表态**：「不同意，先灰度一周」是他在说要改成什么，不是产品要交付灰度能力 |
 * | 「其他意见」章（`freeform-zone` 之内） | 同上，整章都是人写的 |
 * | 必答内容就是上线动作 / 开关管控的那几类议题 | 与 story 的章级豁免逐字同一条判据：讲开关放量与上线顺序是这一类议题的本职，把它判成违规等于要求作者删掉评审人最要看的那一段 |
 *
 * **豁免类别由合同数据给**（`decision_categories[].banned_terms_exempt`），
 * 脚本不写死类别名——写死名字换个工程就静默失效。
 *
 * **其余机器区照拦**：议题澄清正文里真的在承诺一种发布方式时，它仍该被拦住。
 */
export function redactReviewExemptZones(reviewText, ctx) {
  const text = String(reviewText ?? '');
  if (!text) return text;
  const exemptCats = new Set((ctx.contract.decision_categories ?? [])
    .filter(c => c?.banned_terms_exempt).map(c => c.key));
  const catOf = new Map();
  for (const dec of decisionList(readJson(ctx.decisionsPath, null)) ?? []) {
    if (dec?.id) catOf.set(String(dec.id), String(dec.category ?? ''));
  }
  // CRLF 安全：这里只喂给禁用词扫描，它自己也按同样的切法，行号对得上就行。
  const lines = text.split(/\r?\n/);
  // 先把每一行归到它所属的议题：结束标记在块尾，所以从标记往回划。
  const owner = new Array(lines.length).fill(null);
  let from = 0;
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/<!--\s*decision:\s*([^\s>-]+)\s*-->/);
    if (!m) continue;
    for (let k = from; k <= i; k++) owner[k] = m[1];
    from = i + 1;
  }
  const keep = new Array(lines.length).fill(true);
  let inFreeform = false;
  let inHuman = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.includes(FREEFORM_OPEN)) inFreeform = true;
    if (inFreeform) { keep[i] = false; if (line.includes(FREEFORM_CLOSE)) inFreeform = false; continue; }
    if (line.startsWith(HUMAN_ZONE_MARK)) inHuman = true;
    if (/<!--\s*decision:/.test(line)) inHuman = false;
    if (inHuman) { keep[i] = false; continue; }
    if (owner[i] && exemptCats.has(catOf.get(owner[i]) ?? '')) keep[i] = false;
  }
  return lines.map((l, i) => (keep[i] ? l : '')).join('\n');
}

/**
 * 决策登记**严格读取** —— 坏 JSON、错误形状都当场报错，绝不静默覆盖。
 *
 * @returns {boolean} 要不要建一份空骨架（不存在才建；空数组是合法状态，不逼着造议题）
 */
export function decisionsMissing(ctx) {
  const raw = readText(ctx.decisionsPath);
  if (raw === null) return true;
  let parsed = null;
  try {
    parsed = JSON.parse(raw.replace(/^\uFEFF/, ''));
  } catch {
    fail(`${path.basename(ctx.decisionsPath)} 不是合法 JSON：它只应由脚本写入；`
      + '修好或删掉这份坏件再起骨架——直接覆盖会把里面已登记的判断抹掉');
  }
  if (decisionList(parsed) === null) {
    fail(`${path.basename(ctx.decisionsPath)} ${DECISION_SHAPE}`);
  }
  return false;
}

/**
 * review 只能在 story 成文之后渲染 —— 顺序本身就是一条判据。
 *
 * review 是**判断的台账**，而判断在成文过程中还会长出来：写到某一章才发现材料两处打架、
 * 才发现某个取舍得由人拍板。先渲染 review 等于把台账定在「只读过 spec」那个时点上，
 * 之后新登记的议题要么被忘掉，要么得靠人记得回来重跑一次。
 *
 * 「story 还没写完，review 先出来了」不是模型跑偏，是作业顺序把它排在了前面。
 *
 * 判据取「story 里有没有章」而不是「文件在不在」：`init` 会先落一份空骨架，
 * 文件存在证明不了成文发生过。
 */
function requireStoryFirst(ctx) {
  const text = readText(ctx.storyPath);
  if (text && /^##\s+\S/m.test(text)) return;
  fail('story 还没成文，review 不能先渲染。\n'
    + '  review 是判断的台账，而判断在成文过程中还会长出来——写到某一章才发现材料打架、\n'
    + '  才发现某个取舍要人拍板。台账定在「只读过 spec」那个时点上，后面新登记的议题就进不来了。\n'
    + '  顺序：先按合同逐章写完 AR/story.md，把新发现的判断登记进 decisions.json，再跑 build。');
}

export function cmdBuild(ctx) {
  const decisions = readJson(ctx.decisionsPath, null);
  if (!decisions) fail(`缺 ${ctx.decisionsPath}——先跑 init 建骨架`);
  requireStoryFirst(ctx);
  const list = decisionList(decisions);
  if (list === null) fail(`${path.basename(ctx.decisionsPath)} ${DECISION_SHAPE}`);
  // **字段校验与只读 check 是同一份**：合法才渲染。
  // 各写一份的话，build 渲得出来而 check 说不合法，作者在两条路上收到两种答案；
  // 而先渲染再由 check 报错，等于让他拿着一份半成品去猜哪一条是根因。
  const bad = decisionProblems(ctx);
  if (bad.length) {
    fail(`决策登记还有 ${bad.length} 处不合法，没有渲染 review：\n`
      + bad.map((b, k) => `  ${k + 1}. ${b}`).join('\n'));
  }
  const old = readText(ctx.reviewPath) ?? '';

  // 分层与编号都在渲染器里按登记顺序算，不进登记表：登记表里存序号，
  // 插一条就要手工重排后面全部；类别成章的名字来自合同词表，机制不认识任何一类。
  let out;
  try {
    out = renderReview(list, old, ctx.contract.decision_categories ?? []);
  } catch (e) {
    if (e instanceof ProjectionConflict) fail(e.message);
    throw e;
  }

  fs.mkdirSync(path.dirname(ctx.reviewPath), { recursive: true });
  fs.writeFileSync(ctx.reviewPath, out, 'utf-8');
  process.stdout.write(`[story-build build] 已渲染 ${list.length} 个议题；人工填写内容逐字节保留
`);
}

// --------------------------------------------------------------------------

/**
 * 决策登记的字段齐备 —— **只判形式，不判数量、不判叙述**。
 *
 * 数量下限会催生凑数议题，叙述质量的判据会催生套话。这里只核「渲染得出来」。
 */
export function decisionProblems(ctx) {
  const problems = [];
  // ⑤ 决策登记的字段齐备（离线模式没有需求目录，这一项不判）
  //
  // **只判形式，不判数量、不判叙述**。数量下限会催生凑数议题——凑数比零议题更坏，
  // 它把评审人的注意力摊薄在假议题上；叙述质量的判据会催生套话，模型总能写出
  // 一段过得去而什么也没说的话。数量塌陷与叙述质量由评审记录的效果定义、
  // verifier 的逐问、以及评审人自己接。这里只核「渲染得出来」：
  // 标题、澄清正文、请谁确认，缺一条渲出来就是半个议题。
  const decisions = ctx.offline ? null : readJson(ctx.decisionsPath, null);
  if (ctx.offline) { /* 仲裁锚只判文档本身 */ }
  else if (!decisions) problems.push('缺 decisions.json——决策登记是 review 的唯一数据源');
  else if (decisionList(decisions) === null) {
    problems.push(`${path.basename(ctx.decisionsPath)} ${DECISION_SHAPE}`);
  } else {
    const list = decisionList(decisions);
    for (const dec of list) {
      for (const [field, what] of DECISION_FIELDS) {
        if (!String(dec?.[field] ?? '').trim()) {
          problems.push(`决策 ${dec?.id ?? '（无编号）'} 缺${what}——`
            + '这一条渲染出来会是半个议题，评审人看不出要他表什么态');
        }
      }
      // 澄清正文里的小标题用**加粗段首**，不用 `#` 标题行。
      //
      // 议题在 review.md 里已经有三级层次（状态分章、类型成节、逐条成项），
      // 澄清正文里再起标题行，等于在第四级上又开一层——渲染出来层次就乱了。
      // 层级写平会让分组消失。
      if (/(^|\n)\s*#{1,6}\s/.test(String(dec?.clarification ?? ''))) {
        problems.push(`决策 ${dec?.id ?? '（无编号）'} 的澄清正文里有标题行`
          + '——小标题写成加粗段首（`**要点**：…`）；'
          + '议题的层次由状态分章、类型成节、逐条成项给出，正文里再起标题会把它压乱');
      }
      // 类别决定它成章落在哪一节。**只判在不在词表里**——不判每类有没有条目、
      // 不判数量、不判空类要不要解释：那些是配额，配额逼出来的是凑数与逃生口。
      const keys = (ctx.contract.decision_categories ?? []).map(c => c?.key);
      const category = String(dec?.category ?? '').trim();
      if (keys.length && !keys.includes(category)) {
        problems.push(`决策 ${dec?.id ?? '（无编号）'} 的类别`
          + `${category ? `「${category}」不在词表里` : '没登记'}——`
          + `从这十一类里挑一个：${keys.join(' / ')}`);
      }
    }
  }
  return problems;
}

/** 评审记录只含渲染语法：填写说明、签署字段、状态行、下一步都是表单在膨胀。 */
export function reviewFormProblems(reviewText) {
  const problems = [];
  // ⑬ 评审记录只含渲染语法：出现填写说明、签署字段、状态行、下一步就是表单在膨胀
  //
  // 判据是「需要说明书就是设计错了」。这几样每次都以「让评审更规范」的名义长回来，
  // 而它们的实际后果是评审人先读一遍字段表，再在答不上来的格子里胡填。
  // **只判机器渲染的那部分**：评审人自己写在「审核结果：」后面的内容不计。
  if (reviewText) {
    const banned = REVIEW_BANNED_LINES.filter(
      ({ re }) => reviewText.split(/\r?\n/).some(l => re.test(l.trim())));
    for (const { name } of banned) {
      problems.push(`评审记录里出现「${name}」——评审人要填的只有「审核结果：」后面那几句话；`
        + '填写说明、签署字段、状态行都被裁掉过，它们只会让人在答不上来的格子里胡填');
    }
  }
  return problems;
}

// --------------------------------------------------------------------------
// 评审记录的渲染 —— 与上面的读取、校验同属一件事：字段齐不齐、渲出来什么样、
// 人工区怎么保住，分在两个文件时对「一条议题长什么样」各有一份解释。
// --------------------------------------------------------------------------

/**
 * 评审记录（`AR/review.md`）的渲染 —— 机器区确定性重算，人工区逐字节保留。
 *
 * ## 形态从哪来
 *
 * 形态**从已定稿的效果定义正推**。那份定义说：
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
 * - **正文用小标题分段**，不是把五个字段拼成一串 bullet。拼成 bullet 时
 *   「问题 / 建议 / 为什么 / 影响什么 / 来源 / 请谁确认」六行——那是表单腔，
 *   字段会被填成分类名与泛词
 *   （「影响」从「单日上限口径 200 元」塌成「权限模型、接受流程」）；
 * - **人工区只有「审核结果：」一行**，评审人在它后面写具体内容：
 *   要改成什么本来就得写字，勾一个框传不出任何信息。
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

//: 议题正文的所有者是脚本：整段由登记表决定，每次 build 重渲染。与 story 的附录
//: 同一条纪律——重投前拿摘要与盘上的比，有人在这里写过字就停下问他，不静默盖掉。
//: 人工区（「审核结果：」那一行往后）不在其内：那一段本来就归人，逐字节保留。
const ISSUE_MARK = '<!-- story-build:begin 议题 ';

const issueMark = (id, digest) =>
  `${ISSUE_MARK}${id} · 由决策登记表生成，改它请改真源 · sha256:${digest} -->`;
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
 * 这里不设勾选框，也不设暂缓责任人、完成期限、是否阻塞执行、
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

/**
 * 从既有 review 里切出某议题的**机器区**：`#### ` 那一行起，到人工区之前。
 *
 * 范围不靠标记划——机器区永远以 `#### ` 开头，旧稿没有标记也切得出来。
 * 标记只承载摘要：它在（是上一行），就用它记的；不在就是旧稿。
 */
function machineZoneOf(reviewText, id) {
  const end = reviewText.indexOf(`<!-- decision: ${id} -->`);
  if (end < 0) return null;
  const human = humanZoneStart(reviewText, end);
  if (human < 0) return null;
  const head = reviewText.lastIndexOf('\n#### ', human);
  if (head < 0) return null;
  const prevStart = reviewText.lastIndexOf('\n', head - 1) + 1;
  const prev = reviewText.slice(prevStart, head);
  return { mark: prev.startsWith(`${ISSUE_MARK}${id} `) ? prev : null,
    body: reviewText.slice(head + 1, human) };
}

/**
 * 这一段有人动过手吗。
 *
 * 标记里带摘要：与盘上内容比，相等就是没人动过。没有摘要那是**旧稿**：
 * 只能与这一次渲染出来的比，一样就是没人动过；不一样就无从分辨「登记表变了」
 * 与「有人改了」，按改过处理——让人自己说是哪一种，比替他猜错要好。
 */
function issueHandEdited(zone, fresh) {
  const recorded = recordedDigest(zone.mark);
  const now = projectionDigest(zone.body);
  return recorded ? now !== recorded : now !== projectionDigest(fresh);
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
 * 「（暂无）」这类括号占位不放在这里：它的作用只有一个——让空的地方看起来
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
function renderReview(list, previous = '', categories = []) {
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
        const machine = renderMachineZone(dec, `${no}.${gi + 1}.${ii + 1}`);
        const was = machineZoneOf(old, dec.id);
        if (was && issueHandEdited(was, machine)) {
          // 停在这里，不盖。评审人要说的话写在「审核结果：」后面，那一段逐字节保留；
          // 写在议题正文里的，起草方要么把它接进登记表，要么明确不接——两样都比抹掉好。
          throw new ProjectionConflict(
            `议题 ${dec.id} 的正文由决策登记表生成，盘上的内容与它对不上——`
            + '要改议题怎么说，改登记表之后重跑；'
            + '要撤销这里的手改，把这一段（含它上面那行标记）删掉再跑，会重新写出来；'
            + '评审意见写在「审核结果：」后面，那一段不会被动');
        }
        const human = extractHumanZone(old, dec.id) ?? renderHumanZone(dec);
        parts.push(`${issueMark(dec.id, projectionDigest(machine))}\n${machine}\n${human}\n`);
      });
    });
    out.push(parts.join('\n'));
  });

  out.push(renderFreeformSection(extractFreeformZone(old)));
  return out.join('\n');
}
