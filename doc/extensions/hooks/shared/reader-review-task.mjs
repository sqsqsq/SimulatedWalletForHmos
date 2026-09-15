/**
 * 读者审查的任务书 —— **这一次要看的东西**，从真源渲染。
 *
 * 判据本身（审什么、什么算 blocking、什么不做）只在 overlay 的 `story_reader_review` 里写一份；
 * 这里出的是它判不出来的部分：本需求的输入路径、这一版合同的十章问题与章级维度、
 * 材料清单里现有的图逐张。同一件事在两处各写一遍，改一处另一处就静默过期。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { extensionRoot, featureRoot, readJsonOrNull } from './paths.mjs';
import { imagesIn, readablePaths }
  from '../../skills/story/scripts/core/story/images.mjs';
import { sourceStatus } from '../../skills/story/scripts/core/story/sources.mjs';
import { recheckItems, recheckRows } from '../../skills/story/scripts/core/story/recheck.mjs';
import { readWritingPlan } from '../../skills/story/scripts/core/story/writing-plan.mjs';

function contractOf(projectRoot) {
  return readJsonOrNull(path.join(extensionRoot(projectRoot),
    'skills', 'story', 'contracts', 'story-chapters.json'));
}

/**
 * 材料清单里的图，逐张给「路径 + 这是什么 + 作者说用不用」。
 *
 * 没有说明的照列，空着更要看见；作者登记的「不用」原样带上——审查要判的正是
 * 那句理由成不成立，不给理由就只能凭空猜。
 */
function imageRows(projectRoot, feature) {
  const root = featureRoot(projectRoot, feature);
  const manifest = readJsonOrNull(path.join(root, 'AR', 'story-src', 'materials.json'));
  // **形状不对是缺口，不是「本项无图不适用」**：形状判定与作者包、全篇 check 共用
  // `imagesIn` 一份。`materials` 是字符串时直接 `.filter` 会抛——审查者拿到的
  // 会是一个没有来源说明的 TypeError，而它本该读到「清单坏了」。
  const { images, gap } = imagesIn(manifest);
  if (gap) return { gap };
  return { rows: images.map((m) => {
    const readable = readablePaths(root, m.paths);
    const unused = String(m.unused ?? '').trim();
    return `- \`${m.paths.join('、')}\`：${m.caption || '（登记时没写说明）'}`
      + (readable.length ? '' : '　**盘上读不到**（原件缺失或不可读）')
      + (unused ? `　**作者登记不用**：${unused}` : '');
  }) };
}

/**
 * 任务书正文。
 *
 * @param {string} projectRoot
 * @param {string} feature
 * @param {string} checkId 判据 id —— 结果条目用它，不另起名字
 */
export function readerReviewTask(projectRoot, feature, checkId) {
  const contract = contractOf(projectRoot);
  const root = featureRoot(projectRoot, feature);
  const rows = [
    `## 归档件读者审查（${checkId}，BLOCKER）`,
    '',
    '判据见本阶段规则里 `story_reader_review` 的描述。下面是这一次的输入与要回答的问题。',
    '',
    '### 读这些',
    '',
    '- `AR/story.md` —— 审查对象（全文在下面「审查对象」那一节，通读它）；',
    '- `AR/story-src/materials.json` —— 据以成文的材料清单（含每张图是什么）；',
    '- `AR/story-src/decisions.json` —— 已登记的判断，哪些定了、哪些还开着；',
    '- `AR/story-src/story-flow.json` —— 已确认的本 AR 范围；',
    '- `spec/spec.md` —— 已经成立的产品约束。',
  ];

  const storyPath = path.join(root, 'AR', 'story.md');
  const story = readOrNull(storyPath);
  if (story === null || !story.trim()) {
    rows.push('', '`AR/story.md` 现在读不到或是空的——本项 SKIP，如实写 SKIP，不要凭空作答。');
    return rows.join('\n');
  }

  // **当前全文一次**：审查的是这一份，不是宿主愿意去读的那部分。让它自己去开文件时，
  // 截断、读旧稿、读不到都会变成「看起来审过了」——而三种都分不出来。
  // 外层围栏比正文里**最长的那道**再多一个反引号：固定七个的话，正文里合法地出现
  // 一道更长的示例围栏时，包装会被它提前关上——后半篇于是掉出围栏，看起来像任务书的话。
  const fence = `${'`'.repeat(longestFence(story) + 1)}markdown`;
  rows.push('', '### 审查对象：当前 `AR/story.md` 全文', '',
    `（${story.split(/\r?\n/).length} 行，下面这一段就是全文；`
    + '与盘上那一份不一致时以盘上为准，并把这件事写进结论）', '',
    fence, story.replace(/\s+$/, ''), fence.replace(/markdown$/, ''));

  // 写作设计：作者这一版的阅读主线与骨架，全文一次。读不到不能拿空设计当审过，说成缺口。
  const plan = readOrNull(path.join(root, 'AR', 'story-src', 'story-template.md'));
  rows.push('', '### 作者的写作设计：当前 `AR/story-src/story-template.md` 全文', '');
  if (plan === null || !plan.trim()) {
    rows.push('**写作设计缺口**：`AR/story-src/story-template.md` 读不到或是空的。照原材料与范围审正文，'
      + '把「没有可核的写作设计」写进结论——它是本轮的阻断问题。');
  } else {
    const planFence = `${'`'.repeat(longestFence(plan) + 1)}text`;
    rows.push('（作者对本需求的阅读主线与每章骨架，是待核的作者判断，不是审查标准）', '',
      planFence, plan.replace(/\s+$/, ''), planFence.replace(/text$/, ''));
  }

  // 回看清单：作者十章齐后逐条处置的同一张清单，这里核每一条的去向成不成立。
  const src = path.join(root, 'AR', 'story-src');
  const planCtx = { contract, featureRoot: root, srcDir: src, storyPath,
    decisionsPath: path.join(src, 'decisions.json'), templatePath: path.join(src, 'story-template.md') };
  rows.push('', '### 回看清单：作者逐条处置的对象，去向由你核', '',
    ...recheckRows(recheckItems(planCtx, contract ? readWritingPlan(planCtx) : null, story)));

  // 原材料原文逐份给位置：审查要能回到原件，不只看作者转述之后的样子。该有而读不到的说成缺口。
  const { docs, blocking } = sourceStatus({ contract, featureRoot: root });
  rows.push('', '### 原材料原文', '',
    ...docs.map(d => `- \`${d.rel}\` —— ${contract?.sources?.[d.doc]?.label ?? '材料'}`),
    ...blocking.map(m => `- **读不到 \`${m.rel}\`**——它是必备来源；与它有关的判断写未验证，不替它下结论`),
    '- `acceptance.yaml` —— 验收条目');
  rows.push('', '### 另外这几份按需去读', '',
    '- `spec/spec.md` —— 已经成立的产品约束；',
    '- `AR/story-src/decisions.json` —— 已登记的判断，哪些定了、哪些还开着；',
    '- `AR/story-src/story-flow.json` —— 已确认的本 AR 范围；',
    '- `.backup/` —— 收口提交覆盖 `AR/design.md` 之前的上游那一份（有才有）。'
      + '当前 `AR/design.md` 是提取稿，回查上游原话看它与 `RR`、`SR` 原文，不拿提取稿自证；',
    '- 下面那一节的图片身份目录 —— 每张图是什么、用没用、不用的理由。');
  // 会议材料只给位置：结论与证据各有唯一落点，复制进任务书就成了第二份
  if (fs.existsSync(path.join(src, 'meeting-notes.json'))) {
    rows.push('', '### 会议材料（逐话题核去向）', '',
      '- `AR/story-src/meeting-notes.json` —— 每场会每个版本、每个话题的判断：变化、结论、遗留与问人的选项；',
      '- `AR/story-src/meetings/<主名>/<版本>/evidence.json` —— 纠偏后的发言与纠偏留痕，发言编号的出处；',
      '- `AR/story-src/doc-refresh.md` —— 人裁决之后生效的变化与已确认的原文。');
  }

  rows.push('', '### 逐章过读者会问的问题', '');
  for (const chapter of contract?.chapters ?? []) {
    rows.push(`- **${chapter.title}**：${(chapter.questions ?? []).join('；')}`);
  }

  const dimensions = contract?.verdicts?.chapter_dimensions;
  if (Array.isArray(dimensions) && dimensions.length) {
    rows.push('', `章级维度：${dimensions.join('、')}。`);
  }

  // 图**是什么、用没用、不用的理由**是这一次的数据；「怎么判」在 overlay 的
  // `story_reader_review` 里维护一份，这里不复制。
  const images = imageRows(projectRoot, feature);
  rows.push('', '### 材料里的图（这一次有哪几张）', '');
  if (images.gap) {
    rows.push(`**输入有缺口**：${images.gap}。`
      + '在缺口修好之前，不要就「图用没用、取舍成不成立」下结论——'
      + '把这件事写进结论，它是本轮的阻断问题。');
  } else {
    rows.push(...(images.rows.length ? images.rows : ['材料清单里没有图片。']));
  }

  // 方法与结论要求只在 overlay 的 `story_reader_review` 维护一份，宿主把它装配进 verifier 的任务。
  return rows.join('\n');
}

/** 读一份文件；读不到返回 null——空串与「读不到」在这里必须分得开。 */
function readOrNull(abs) {
  try { return fs.readFileSync(abs, 'utf-8'); } catch { return null; }
}

/** 正文里最长的那道围栏有几个反引号（至少 3，让外层总比它长）。 */
function longestFence(text) {
  let most = 3;
  for (const line of String(text ?? '').split(/\r?\n/)) {
    const m = line.match(/^[ 	]*(`{3,})/);
    if (m && m[1].length > most) most = m[1].length;
  }
  return most;
}
