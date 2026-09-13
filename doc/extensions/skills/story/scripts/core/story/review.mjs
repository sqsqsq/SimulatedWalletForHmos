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
import { normalizeHeading } from './document.mjs';
import {
  FREEFORM_CLOSE, FREEFORM_OPEN, HUMAN_ZONE_MARK, ProjectionConflict, renderReview,
} from '../review-render.mjs';

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
 * | 人工区（`审核结果：` 之后到该议题的结束标记） | 那是**人的表态**：「不同意，文案回退为上一版」是他在说要改成什么，不是产品要交付回退能力 |
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
