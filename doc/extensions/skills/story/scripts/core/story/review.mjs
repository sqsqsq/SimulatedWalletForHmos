/**
 * 决策登记与评审记录 —— 登记表怎么读、review.md 怎么渲染、人工区怎么保住。
 *
 * 评审记录是判断的台账，而判断在成文过程中还会长出来：顺序（先成文再渲染）本身
 * 就是一条判据，写在这里。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fail, readJson, readText } from './context.mjs';
import { ProjectionConflict, projectionDigest, recordedDigest } from './document.mjs';

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
export function decisionList(raw) {
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
 * | 人工区（`方案选择：` 或 `审核结果：` 之后到该议题的结束标记） | 那是**人的表态**：「不同意，先灰度一周」是他在说要改成什么，不是产品要交付灰度能力 |
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
    if (HUMAN_ZONE_MARKS.some(mark => line.startsWith(mark))) inHuman = true;
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
  const notes = [];
  try {
    out = renderReview(list, old, ctx.contract.decision_categories ?? [], notes,
                       carriedOver(ctx.flowPath));
  } catch (e) {
    if (e instanceof ProjectionConflict) fail(e.message);
    throw e;
  }

  fs.mkdirSync(path.dirname(ctx.reviewPath), { recursive: true });
  fs.writeFileSync(ctx.reviewPath, out, 'utf-8');
  process.stdout.write(`[story-build build] 已渲染 ${list.length} 个议题；人工填写内容逐字节保留
`);
  for (const note of notes) process.stdout.write(`[story-build build] ${note}\n`);
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
      // 人要做的事只收两种取值；选方案的，选项得是真正的列表——人按编号选。
      // 选项合不合理、推荐有没有依据归作者与审查，这里不判选项个数。
      const mode = dec?.review_mode;
      if (mode !== undefined && !Object.hasOwn(REVIEW_MODES, mode)) {
        problems.push(`决策 ${dec?.id ?? '（无编号）'} 的 review_mode「${mode}」不认识——`
          + '人要从几个方案里选一个写 choice，复核一个已有结论写 confirm');
      } else if (mode === 'choice') {
        problems.push(...choiceListProblems(dec));
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

//: 澄清正文的段首：加粗小标题（`**依据**：…`）。一段从它起，到下一个段首止。
const SEGMENT_HEAD = /^\s*\*\*([^*]+)\*\*\s*[:：]?/;
//: 澄清正文的第一段：这一条在问什么。变义判定只看它。
const NL = String.fromCharCode(10);
const DECISION_SEGMENT = '决策点';
const OPTIONS_SEGMENT = '可选的做法';
const SUGGESTION_SEGMENT = '建议';
//: 一个选项里「做法」与「选它会怎样」之间的分隔：后面写后果。
const OPTION_CONSEQUENCE = '——';
//: 选项编号：行首或空白、标点之后的「数字＋. 、 ) ）」，数字后不再接数字（版本号、小数不算）；圈码同理。
const OPTION_NO = /(?:^|[\s；;，,。：:（(])(?:(\d+)[.、)）](?!\d)|([①-⑳]))/g;

/** 一行里接连出现 n 与 n+1 两个选项编号（行首列表号也算）：几个选项挤在了同一行。 */
function optionsSqueezed(line) {
  const nums = [...line.matchAll(OPTION_NO)]
    .map(m => (m[1] ? Number(m[1]) : m[2].charCodeAt(0) - 0x2460 + 1));
  return nums.some((n, i) => nums.slice(i + 1).includes(n + 1));
}

/**
 * 选方案的议题：「可选的做法」那一段是真正的有序列表，一个选项一项。
 *
 * 只看那一段——决策点、依据、建议里的编号是正常的说明，不是让人选的方案。
 * 只判形状，不判选项个数，也不判选项与建议合不合理。
 */
function choiceListProblems(dec) {
  const id = dec?.id ?? '（无编号）';
  const lines = String(dec?.clarification ?? '').split(/\r?\n/);
  const segment = (name) => {
    const at = lines.findIndex(l => SEGMENT_HEAD.exec(l)?.[1].trim() === name);
    const next = lines.findIndex((l, i) => at >= 0 && i > at && SEGMENT_HEAD.test(l));
    return at < 0 ? null
      : [lines[at].replace(SEGMENT_HEAD, ''), ...lines.slice(at + 1, next < 0 ? lines.length : next)];
  };
  // 建议段：人从几个方案里选，要先看到起草方推荐哪一个；推荐不出来也要写明缺哪个事实。
  const suggestion = segment(SUGGESTION_SEGMENT);
  const noSuggestion = !suggestion?.some(l => l.trim())
    ? [`决策 ${id} 是选方案的议题，缺「**${SUGGESTION_SEGMENT}**」这一段（或它是空的）——先写选择方案几、再写理由；`
      + '信息不够推荐不出来时，写明缺哪个事实']
    : [];
  const area = segment(OPTIONS_SEGMENT) ?? [];
  const list = choiceOptionProblems(id, area);
  return [...list, ...noSuggestion];
}

/** 「可选的做法」那一段的形状：有序列表、一项一个、每项写后果。 */
function choiceOptionProblems(id, area) {
  if (area.some(optionsSqueezed)) {
    return [`决策 ${id} 把几个选项写在了同一段——「${OPTIONS_SEGMENT}」写成有序列表，`
      + '一个选项一项（`1. …` 换行 `2. …`），评审人填的就是这个编号'];
  }
  const options = area.filter(l => /^\s*\d+[.)]\s+\S/.test(l));
  if (!options.length) {
    return [`决策 ${id} 是选方案的议题（review_mode: choice），「**${OPTIONS_SEGMENT}**」这一段却没有有序列表——`
      + '在这个加粗段首下一个选项一项列出，评审人按编号选；其实只是请人复核已有结论的，改成 confirm'];
  }
  // 每个选项都要说选它会怎样：写不出后果差别的，不是真取舍。只判字面，不判后果写得好不好。
  const bare = options.flatMap((line, k) => {
    const cut = line.indexOf(OPTION_CONSEQUENCE);
    return cut < 0 || !line.slice(cut + OPTION_CONSEQUENCE.length).trim() ? [k + 1] : [];
  });
  if (bare.length) {
    return [`决策 ${id} 的「${OPTIONS_SEGMENT}」第 ${bare.join('、')} 项没写选它会怎样——每项写成`
      + `「做法${OPTION_CONSEQUENCE}选它会怎样」，说清范围、行为、验收或交付哪一项会变；`
      + '写不出后果差别的不是真取舍，改成 confirm'];
  }
  return [];
}

/** 评审记录只含渲染语法：填写说明、签署字段、状态行、下一步都是表单在膨胀。 */
export function reviewFormProblems(reviewText, contract) {
  const problems = [];
  // ⑬ 评审记录只含渲染语法：出现填写说明、签署字段、状态行、下一步就是表单在膨胀
  //
  // 判据是「需要说明书就是设计错了」。这几样每次都以「让评审更规范」的名义长回来，
  // 而它们的实际后果是评审人先读一遍字段表，再在答不上来的格子里胡填。
  if (reviewText) {
    const lines = reviewText.split(/\r?\n/).map(l => l.trim());
    const banned = (contract?.review_form_banned_lines ?? [])
      .filter(({ pattern }) => lines.some(l => new RegExp(pattern).test(l)));
    for (const { name } of banned) {
      problems.push(`评审记录里出现「${name}」——评审人要填的只有每条议题末尾那处填写位；`
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
 * - **人工区按人要做的事给**（`REVIEW_MODES`）：选方案的填编号或另写方案，复核结论的勾确认或
 *   不同意并写原因与调整结论。没有字段表：要改成什么本来就得写字，框只让「确认」一眼可见。
 *
 * ## 两条不变的机制
 *
 * - **人工区逐字节保留**：从填写位首行到 `<!-- decision: ID -->` 之间，build 一个字节都不动。
 *   评审人的表态是人的产物，重算它等于把做完的决定推回去一次；
 * - **计划外意见区**（成章后叫「其他意见」）：评审人常有起草方没登记过的意见，
 *   套不进任何议题。产出侧得给它一个地方——不然人只能写进议题正文里，
 *   而那是机器区，下一次 build 会把它冲掉。
 *
 * **给人的提示用可见引用块，机制锚才用 HTML 注释**：HTML 注释在预览里看不见，
 * 拿它承载「怎么填」等于没写。全篇的提示只在两处（顶部一条、其他意见处一条）；
 * 选方案的填写位首版多一行按编号填的话，它属于人工区，人填的时候可以删。
 */

/**
 * 议题要人做的事（登记表可选的 `review_mode`）→ 人工区首版的样子。
 *
 * 与 `status` 无关：status 说决定成立没有，review_mode 说人在这里是从方案里选，还是复核一个结论。
 * 两种填写位都留自由文字：勾框只是让「确认」一眼可见，不同意时要改成什么照样得写字。
 * 没写 review_mode 的条目仍是一行「审核结果：」，人写在后面。
 * 每种形态的第一行就是机器区与人工区的分界：它之前确定性重渲染，之后逐字节保留。
 */
const REVIEW_MODES = {
  choice: ['方案选择：', '请填写上方选项编号；另有方案时写明具体结论与理由。'],
  confirm: ['审核结果：', '- [ ] 确认', '- [ ] 不同意', '不同意原因：', '调整结论：'],
};
const PLAIN_ZONE = ['审核结果：'];
const HUMAN_ZONE_MARKS = [...new Set(Object.values(REVIEW_MODES).map(z => z[0]))];
const zoneOf = (dec) => REVIEW_MODES[dec?.review_mode] ?? PLAIN_ZONE;

//: 议题正文的所有者是脚本：整段由登记表决定，每次 build 重渲染。与 story 的附录
//: 同一条纪律——重投前拿摘要与盘上的比，有人在这里写过字就停下问他，不静默盖掉。
//: 人工区（填写位首行往后）不在其内：那一段本来就归人，逐字节保留。
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

/** 顶部提示：全篇怎么填只说这一次；这一份里有哪几种填写位，就说哪几种。 */
const DOC_HINT = '> 怎么填：第一部分还没定，等你拍板；第二部分已经定了，过目复核即可。';
const ZONE_HINTS = [
  [REVIEW_MODES.choice, '选方案的议题填「方案选择：」——写上方选项的编号；都不合适就写明你的方案和理由。'],
  [REVIEW_MODES.confirm, '复核结论的议题在「审核结果：」下勾「确认」或「不同意」，不同意时写原因与调整后的结论。'],
  [PLAIN_ZONE, '，把你的意见写在它后面——同意就写「同意」；有不同意见，写清楚要改成什么；需要暂缓，写原因。'],
];

/** 其他意见处的提示：它与顶部那条职责不同——那条说怎么表态，这条说怎么补充。 */
const FREEFORM_HINT = '> 以上议题之外你认为该说的事写在这里——缺的分支、该复用的既有能力、'
  + '遗漏的埋点都算。按 1. 2. 3. 编号列举，每条写清是什么、影响哪里。';

/** 归档件的头部：大标题 + 一条可见提示。 */
function renderDocHeader(list) {
  const zones = new Set(list.map(zoneOf));
  if (!zones.size) zones.add(PLAIN_ZONE);
  const lines = ZONE_HINTS.filter(([zone]) => zones.has(zone)).map(([zone, hint]) => (zone !== PLAIN_ZONE ? hint
    : `${zones.size > 1 ? '只有一行「审核结果：」的议题' : '每条末尾有一行「审核结果：」'}${hint}`));
  return `# 评审记录\n\n${DOC_HINT}${lines.join('')}\n`;
}

/**
 * 议题块的**机器区**：完全由登记表决定，每次 build 确定性重渲染。
 *
 * 已定决策（`status: settled`）也照样成块——评审人要先看到「有哪些决策、结论是什么」，
 * 才谈得上反馈对不对；已定不等于不必过目。
 *
 * `clarification` 是**带小标题分段的正文**，登记时怎么写这里就怎么出，换行、空行与有序列表原样保留：
 * 选方案的（决策点 / 依据 / 可选的做法 / 建议 / 理由），复核结论的（决策点 / 依据 / 结论与影响）。
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
 * 议题块的**人工区**首版：按 `review_mode` 给填写位，此后 build 一个字节都不动它。
 *
 * 不设暂缓责任人、完成期限、是否阻塞执行、后续动作、确认人、确认日期、确认依据这类字段。
 * 判据是「需要说明书就是设计错了」：那些格子评审人多半答不上来，只会被跳过或胡填。
 * 填写位不预选任何一项——推荐不是人的选择。
 */
function renderHumanZone(dec) {
  return [...zoneOf(dec), '', `<!-- decision: ${dec.id} -->`].join('\n');
}

/**
 * 从既有 review 里切出某议题的**机器区**与**人工区**。
 *
 * 范围是这一条议题：上一个议题的结束标记之后，到本议题的 `<!-- decision: ID -->`。
 * 机器区从 `#### ` 那一行起；人工区从某一行行首的填写位标签（`方案选择：` / `审核结果：`）起。
 * 人在意见里引用这两个标签是正常的，所以**不取最后一处**：从前往后找第一个让它之前的机器区
 * 与标记里记的摘要（旧稿没有标记时与这次渲染出来的）对得上的标签。一个都对不上说明机器区
 * 真被改过，这时取第一处，由调用方停下；`ambiguous` 标出范围里不止一处标签，报错时说明边界可能认不准。
 *
 * @returns {{machine: {mark, body}|null, human: string|null, ambiguous: boolean}|null}
 */
function issueZones(reviewText, id, fresh) {
  const anchor = `<!-- decision: ${id} -->`;
  const end = reviewText.indexOf(anchor);
  if (end < 0) return null;
  const prev = reviewText.lastIndexOf('<!-- decision:', end - 1);
  const from = prev < 0 ? 0 : reviewText.indexOf('-->', prev) + 3;
  const heading = reviewText.indexOf('\n#### ', from);
  const head = heading >= 0 && heading < end ? heading : -1;
  const starts = [];
  for (let at = head < 0 ? from : head + 1; at < end;) {
    if ((at === 0 || reviewText[at - 1] === '\n')
        && HUMAN_ZONE_MARKS.some(mark => reviewText.startsWith(mark, at))) starts.push(at);
    const nl = reviewText.indexOf('\n', at);
    if (nl < 0) break;
    at = nl + 1;
  }
  if (!starts.length) return { machine: null, human: null, ambiguous: false };
  if (head < 0) return { machine: null, human: reviewText.slice(starts[0], end + anchor.length), ambiguous: false };
  const markLine = reviewText.slice(reviewText.lastIndexOf('\n', head - 1) + 1, head);
  const mark = markLine.startsWith(`${ISSUE_MARK}${id} `) ? markLine : null;
  const want = recordedDigest(mark) ?? projectionDigest(fresh);
  const at = starts.find(s => projectionDigest(reviewText.slice(head + 1, s)) === want) ?? starts[0];
  return { machine: { mark, body: reviewText.slice(head + 1, at) },
    human: reviewText.slice(at, end + anchor.length), ambiguous: starts.length > 1 };
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

/**
 * 人工区里有没有人真写过字 —— 与**任何一种首版**逐字节相同就是没写过。
 *
 * 与 `keptHumanZone` 的判据共用一处：那边判「要不要原样保留」，这边判「丢了会不会丢掉人的话」，
 * 两处各写一份的话，迟早出现「保留了但不算数」或「算数了却没保留」。
 */
function hasHumanWords(zone, id) {
  if (zone === null) return false;
  const anchor = `<!-- decision: ${id} -->`;
  return ![...Object.values(REVIEW_MODES), PLAIN_ZONE]
    .some(z => zone === [...z, '', anchor].join('\n'));
}

/**
 * 旧稿里有、这次登记表里没有的议题 —— **人写过字的那些，不许静默消失**。
 *
 * `renderReview` 只按当前登记表里的 id 重建，旧文里多出来的那几条压根不进新文，
 * 而 `build` 是整份覆盖。于是「作者把一条议题删了」与「评审人在那条上写的意见」
 * 一起没了，没有任何信号。
 *
 * 判的只是**在不在**，不判该不该删：删得对不对是业务判断，归人与模型。
 */
function orphanOpinions(old, ids) {
  const out = [];
  const seen = new Set(ids);
  const re = /<!-- decision: ([^>]+?) -->/g;
  for (let m = re.exec(old); m; m = re.exec(old)) {
    const id = m[1].trim();
    if (seen.has(id)) continue;
    const zones = issueZones(old, id, '');
    if (hasHumanWords(zones?.human ?? null, id)) out.push(id);
  }
  return out;
}

/**
 * 这条议题的问题**换过了吗** —— 拿人表态那一刻的机器区摘要，与这次要写的比。
 *
 * 标记里记的摘要说的是「人是在哪一版问题下写的字」。登记表改了标题或澄清正文，
 * 新摘要就与它不同——**那一刻旧的勾选还挂在新问题下面**，而它回答的是另一个问题。
 * 脚本只判这一件确定的事；「只是改了措辞」还是「换成了另一个问题」是语义判断，归模型。
 */
function issueRewritten(zones, fresh) {
  const was = zones?.machine?.body ?? null;
  if (was === null) return 'no';
  const before = decisionPoint(was);
  const after = decisionPoint(fresh);
  // **判不出来就不拦**：早先的稿子里这一段可能叫别的名字，
  // 拿整段正文去比的话，改个标题错字也会停手，而真正换问题的那一次淹在噪声里。
  // 判不出不等于没事——调用方出一声，让人自己看一眼。
  if (before === null || after === null) return 'unknown';
  return before === after ? 'no' : 'yes';
}

/**
 * 这一轮里人明确说了「沿用上一版表态」的那几条议题 —— **解锁变义判据的唯一路径**。
 *
 * 变义时停手是对的，但停手必须有出路：模型判定「只是改了措辞」时，人用
 * `story_flow.py decide --update <议题 id> --basis <原话>` 记一笔，这里据它带回。
 * 没有这一段的话，报错让人去记一笔、记完重跑却还是同样的报错——那是个死胡同。
 *
 * **只认这条命令记下的原话**：`update-notes` 里写「已确认」不算，那是模型的转述。
 * 契约读不出来就当没有：宁可多停一次，也不能因为读不到就默认放行。
 */
function carriedOver(flowPath) {
  const flow = flowPath ? readJson(flowPath, null) : null;
  const rows = flow?.update?.decisions;
  if (!Array.isArray(rows)) return new Set();
  return new Set(rows.map(r => String(r?.item ?? '').trim()).filter(Boolean));
}

/**
 * 机器区里的**决策点**那一段 —— 「这一条到底在问什么」。
 *
 * 比的只有它，不是整段机器区：
 *   编号由渲染顺序算，插一条、换个分类，后面每条的编号都会变——**重排不是改问题**；
 *   标题补一句「（复议）」、依据里补一条材料、建议改个说法，问的还是同一件事；
 *   而「决策点」换了，那就是另一个问题了，人上次的回答答的不是它。
 * 决策点是澄清正文的固定第一段（作业书「决策登记」定的形态，choice 与 confirm 都有）。
 * 找不到这一段就返回 null：这一条判不出来，交给调用方出声，不假装判过。
 */
function decisionPoint(text) {
  const lines = String(text).split(NL);
  const at = lines.findIndex(l => SEGMENT_HEAD.exec(l)?.[1].trim() === DECISION_SEGMENT);
  if (at < 0) return null;
  const next = lines.findIndex((l, i) => i > at && SEGMENT_HEAD.test(l));
  return projectionDigest(lines.slice(at, next < 0 ? lines.length : next).join(NL));
}

/**
 * 这条议题要保留的人工区（人工填写内容的唯一真源）；返回 null 表示按当前 `review_mode` 给首版。
 *
 * 与某种首版逐字节相同的人工区里没有人的字，跟着当前交互方式重生成不丢任何东西。
 * 人写过的一律原样保留——交互方式后来改了也不换形式，只在 `notes` 里说一声，由人决定怎么继续。
 */
function keptHumanZone(zones, dec, notes) {
  const zone = zones?.human ?? null;
  if (!hasHumanWords(zone, dec.id)) return null;
  const label = HUMAN_ZONE_MARKS.find(mark => zone.startsWith(mark));
  const want = zoneOf(dec)[0];
  if (label !== want) {
    notes.push(`议题 ${dec.id} 的「${label}」里已经有人写过，这次没有换成「${want}」`
      + '——人写的内容原样保留；要改成新的填写方式，先和评审人确认');
  }
  return zone;
}

/**
 * 计划外意见区：整段逐字节保留，与议题人工区同等待遇。
 *
 * 评审人常有起草方没登记过的意见——缺的分支、该复用的既有能力、遗漏的埋点。
 * 它们套不进任何议题（没有对应的决策），而人总得有地方写。
 * 没有这一区的话，这类意见只能写进议题正文——那是机器区，下一次 build 就把它冲掉了。
 * 读它的是 `/story update`：它把这里的意见与其它输入一起当本轮的变化来源。
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
function renderReview(list, previous = '', categories = [], notes = [], carried = new Set()) {
  const old = String(previous ?? '');
  const decisions = Array.isArray(list) ? list.filter(Boolean) : [];
  // **整份覆盖之前先看一眼旧文里多出来的那几条**：登记表里没有了，而人在上面写过字。
  // 不看的话，这一次 build 就是那条意见最后存在的时刻，而且没有任何信号。
  const orphans = orphanOpinions(old, decisions.map(d => d?.id));
  if (orphans.length) {
    throw new ProjectionConflict(
      `旧的评审记录里有 ${orphans.length} 条议题不在这次的登记表里，而评审人在上面写过意见`
      + `（${orphans.join('、')}）——这次没有写盘，那几条意见还在 AR/review.md 里。`
      + '这几条是真的要撤销，就先把它们的人工区连同 `<!-- decision: … -->` 标记一起删掉再跑；'
      + '是登记表漏了，就把它们补回 decisions.json。**不要直接重跑一遍指望它自己过去**——'
      + '过去了就等于把人的话删了。');
  }
  const out = [renderDocHeader(decisions)];

  STATUS_CHAPTERS.forEach((chapter, ci) => {
    const no = ci + 1;
    const mine = decisions.filter(d => (
      chapter.key === 'settled' ? d.status === 'settled' : d.status !== 'settled'));
    const parts = [`## ${no}. ${chapter.title}\n`];
    groupByCategory(mine, categories).forEach((group, gi) => {
      parts.push(`### ${no}.${gi + 1} ${group.name}\n`);
      group.items.forEach((dec, ii) => {
        const machine = renderMachineZone(dec, `${no}.${gi + 1}.${ii + 1}`);
        const zones = issueZones(old, dec.id, machine);
        if (zones?.machine && issueHandEdited(zones.machine, machine)) {
          // 停在这里，不盖，文件不动。评审人要说的话在填写位里，那一段逐字节保留；
          // 写在议题正文里的，起草方要么把它接进登记表，要么明确不接——两样都比抹掉好。
          throw new ProjectionConflict(
            `议题 ${dec.id} 的正文由决策登记表生成，盘上的内容与它对不上，这次没有写盘——`
            + '要改议题怎么说，改登记表之后重跑；'
            + '要撤销正文里的手改，只删「#### 标题」到「请…确认。」这一段（含它上面那行标记）再跑，会重新写出来；'
            + '填写位里人写的内容不要删'
            + (zones.ambiguous ? '。这条议题里有不止一处行首「方案选择：」或「审核结果：」，'
              + '填写位从哪一行开始也可能认不准，先请人看一眼这一条' : ''));
        }
        const rewritten = hasHumanWords(zones?.human ?? null, dec.id)
          ? issueRewritten(zones, machine) : 'no';
        if (rewritten === 'unknown') {
          notes.push(`议题 ${dec.id} 的正文这次改了，而评审人已经在它下面写过意见；`
            + '它没有「**决策点**」那一段，脚本判不出问的还是不是同一件事——'
            + '人写的内容原样保留了，问的事要是变了，请评审人重新看一眼这一条');
        }
        if (rewritten === 'yes' && carried.has(String(dec.id))) {
          // 人说了沿用：把上一版的表态带过来，标记里的摘要换成这一版——
          // 不换的话下一次 build 还会判成「问题换了」，同一件事要人记第二遍。
          notes.push(`议题 ${dec.id} 的正文改了，按 decide --update 记下的原话沿用上一版的表态`);
        } else if (rewritten === 'yes') {
          // 人是在**上一版问题**下写的字。问题换了还把勾选带过去，等于替他回答了一个
          // 他没看过的问题。这里只判摘要变没变；「只是改了措辞」还是「换了个问题」是语义判断，
          // 归模型——它判定意义未变时，用 `story_flow.py decide --update` 把人的原话记一笔，
          // 再把这条的人工区照原样留着重跑。
          throw new ProjectionConflict(
            `议题 ${dec.id} 的正文这次改了，而评审人已经在它下面写过意见——这次没有写盘，`
            + '盘上那一份还是人看过的那一版。'
            + '意思没变（只是措辞）：`story_flow.py decide --update` 记一笔沿用谁在哪一版的表态，再重跑；'
            + '意思变了：这是一个新问题，先把旧的人工区内容移走或让评审人重新表态，再重跑。');
        }
        const human = keptHumanZone(zones, dec, notes) ?? renderHumanZone(dec);
        parts.push(`${issueMark(dec.id, projectionDigest(machine))}\n${machine}\n${human}\n`);
      });
    });
    out.push(parts.join('\n'));
  });

  out.push(renderFreeformSection(extractFreeformZone(old)));
  return out.join('\n');
}
