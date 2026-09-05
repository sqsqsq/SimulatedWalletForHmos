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

function contractOf(projectRoot) {
  return readJsonOrNull(path.join(extensionRoot(projectRoot),
    'skills', 'story', 'contracts', 'story-chapters.json'));
}

/** 材料清单里的图，逐张给「路径 + 这是什么」。没有说明的照列，空着更要看见。 */
function imageRows(projectRoot, feature) {
  const manifest = readJsonOrNull(path.join(featureRoot(projectRoot, feature),
    'AR', 'story-src', 'materials.json'));
  const images = (manifest?.materials ?? []).filter(m => m?.kind === 'image');
  return images.map(m => {
    const where = Array.isArray(m.paths) ? m.paths.join('、') : '';
    return `- \`${where}\`：${m.caption || '（登记时没写说明）'}`;
  });
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
    '- `AR/story.md` —— 审查对象，通读全篇；',
    '- `AR/story-src/materials.json` —— 据以成文的材料清单（含每张图是什么）；',
    '- `AR/story-src/decisions.json` —— 已登记的判断，哪些定了、哪些还开着；',
    '- `AR/story-flow.json` —— 已确认的本 AR 范围；',
    '- `spec/spec.md` —— 已经成立的产品约束。',
  ];

  if (!fs.existsSync(path.join(root, 'AR', 'story.md'))) {
    rows.push('', '`AR/story.md` 现在不在——本项 SKIP，如实写 SKIP，不要凭空作答。');
    return rows.join('\n');
  }

  rows.push('', '### 逐章过读者会问的问题', '');
  for (const chapter of contract?.chapters ?? []) {
    rows.push(`- **${chapter.title}**：${(chapter.questions ?? []).join('；')}`);
  }

  const dimensions = contract?.verdicts?.chapter_dimensions;
  if (Array.isArray(dimensions) && dimensions.length) {
    rows.push('', `章级维度：${dimensions.join('、')}。`);
  }

  // 逐章问答看不到横跨两章的矛盾——五跑那次「未实名」在流程里引导去认证、
  // 在验收里看不到入口，两章各自都说得通。跨章比对要说成一个显式动作。
  rows.push('', '### 跨章对着读，这四问', '',
    '1. **同一个条件，各章说法一致吗**：挑关键条件（未登录、未实名、开关关闭、'
    + '余额不足这类），把流程、功能说明、异常与恢复、验收四处对着读——'
    + '同一种情况下用户看到什么、系统怎么处理，四处说的是不是同一件事；',
    '2. **图里每条路径有后续吗**：分支画出去之后要么走到终态，要么接回某个节点，'
    + '不能断在那里；',
    '3. **材料自己打架的地方，作者定了口径吗**：定了的该在决策件里是 `settled`，'
    + '定不了的该是 `open`——两样都没有，就是替需求方做了决定而他不知道；',
    '4. **附录 §10 那些非实体落点写的是实际影响对象吗**：'
    + '「页面」「资源」这种泛称等于没写落点。');

  const images = imageRows(projectRoot, feature);
  rows.push('', '### 材料里的图，逐张回答', '');
  if (images.length) {
    rows.push(...images, '',
      '每一张两问：**story 用了没有**；没用的话，**它给的理由成不成立**。');
  } else {
    rows.push('材料清单里没有图片，这一问不适用。');
  }

  rows.push('',
    '### 结论写成什么（BLOCKER）',
    '',
    `在输出 YAML 的 \`checks:\` 里追加一条 \`id: ${checkId}\`，\`details\` 下两个键：`,
    '',
    '```yaml',
    `    - id: ${checkId}`,
    '      status: PASS | FAIL',
    '      details:',
    '        blocking_findings: []      # 哪一章哪一句、缺的或错的是什么、对读者的影响',
    '        advisories: []             # 不影响正确与完整的表达建议，不阻止 PASS',
    '```',
    '',
    '**空列表是结论**，缺席不是。结论由插件按你的终态发布落盘；不要另写文件，',
    '也不要用自由文本重跑——那样的输出不算证据。');

  return rows.join('\n');
}
