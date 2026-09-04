/**
 * 读者审查的任务书 —— **从合同渲染，不手写**。
 *
 * 二跑这一项的结局是：第一次完全没做，补做格式不对，最后由主模型把文本转写成文件过的门；
 * 而它真正该发现的东西——材料里三张图一张没进 story——它没报，用户报了。
 *
 * 前一半是送达与格式，后一半是**任务定义**：合同里十章各有读者问题，却没有一条问
 * 「材料登记的每张图，用了没有；没用，理由在哪」。任务里没有的问题，审查者不会去问。
 *
 * 所以任务书从三处真源渲染：章节问题与章级维度取自 `story-chapters.json`，
 * 图片清单逐张取自 `materials.json`（含每张的说明），输入路径按本需求实际拼出。
 * 改合同或改材料，任务书跟着变。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { extensionRoot, featureRoot, readTextOrNull } from './paths.mjs';

function readJson(file) {
  const raw = readTextOrNull(file);
  if (raw === null) return null;
  try {
    return JSON.parse(raw.replace(/^﻿/, ''));
  } catch {
    return null;
  }
}

function contractOf(projectRoot) {
  return readJson(path.join(extensionRoot(projectRoot),
    'skills', 'story', 'contracts', 'story-chapters.json'));
}

/** 材料清单里的图，逐张给「路径 + 这是什么」。没有说明的照列，空着更要看见。 */
function imageRows(projectRoot, feature) {
  const manifest = readJson(path.join(featureRoot(projectRoot, feature),
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
  const storyRel = 'AR/story.md';
  const rows = [
    `## 归档件读者审查（${checkId}，BLOCKER）`,
    '',
    '**这一项要通读一份完整的归档叙事件。**它是 story 语义质量的唯一发现者——',
    '结构、编号、引用这些机器已经核过；机器判不了的是：这件事讲了没有、讲清没有、是不是编的。',
    '',
    '### 先读这些，再答',
    '',
    `- \`${storyRel}\` —— 审查对象，通读全篇；`,
    '- `AR/story-src/materials.json` —— 它据以成文的材料清单（含每张图是什么）；',
    '- `AR/story-src/decisions.json` —— 已登记的判断，哪些定了、哪些还开着；',
    '- `AR/story-flow.json` —— 已确认的本 AR 范围；',
    '- `spec/spec.md` —— 已经成立的产品约束。',
  ];

  if (!fs.existsSync(path.join(root, 'AR', 'story.md'))) {
    rows.push('', `\`${storyRel}\` 现在不在——本项 SKIP，如实写 SKIP，不要凭空作答。`);
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

  const images = imageRows(projectRoot, feature);
  rows.push('', '### 材料里的图，逐张回答', '');
  if (images.length) {
    rows.push(...images, '',
      '每一张回答两件事：**story 用了没有**；没用的话，**它给的理由成不成立**。',
      '理由可以是「参考稿与最终交互不一致」这类——那是正当的；',
      '通篇一个字没提，就是没看过它，记 blocking。',
      '',
      '这一问不是形式：两轮实跑各丢过一次图，第二次三张全丢，而上一轮的审查判了「零阻断」。');
  } else {
    rows.push('材料清单里没有图片，这一问不适用。');
  }

  rows.push('',
    '### 还要看两件机器看不出的',
    '',
    '- **关键业务事实缺没缺**：材料或已登记判断里有、而 story 通篇没交代的东西；',
    '- **有没有编**：materials 与 decisions 都不支持的确定结论。',
    '',
    '**不要做的事**：不逐条对账、不出裁决表、不为每条结论找一段够长的引文。',
    '那些做法抄的量随材料条数涨，读者拿到的判断不增加。',
    '',
    '### 结论写成什么（BLOCKER）',
    '',
    `在输出 YAML 的 \`checks:\` 里追加一条 \`id: ${checkId}\`，\`details\` 下写两个键：`,
    '',
    '```yaml',
    `    - id: ${checkId}`,
    '      status: PASS | FAIL',
    '      details:',
    '        blocking_findings: []      # 每条写：哪一章哪一句、缺的或错的是什么、对读者的影响',
    '        advisories: []             # 不影响正确与完整的表达建议，不阻止 PASS',
    '```',
    '',
    '**空列表是结论**，缺席不是：审过没发现问题，与没审是两件事。',
    '零 blocking 时在 advisories 之外说明你逐章都过了什么——只写一句「未发现问题」与没审同形。',
    '这份 YAML 由插件按你的终态发布落盘；不要另写文件，也不要用自由文本重跑——那样的输出不算证据。');

  return rows.join('\n');
}
