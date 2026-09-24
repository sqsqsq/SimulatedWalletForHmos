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
import { headingEnd, parseDocument } from '../../skills/story/scripts/core/story/document.mjs';
import { diagramsOf, diagramTopic, imagesIn, readablePaths }
  from '../../skills/story/scripts/core/story/images.mjs';
import { sourceStatus, upstreamDocs } from '../../skills/story/scripts/core/story/sources.mjs';
import { recheckItems, recheckRows } from '../../skills/story/scripts/core/story/recheck.mjs';
import { readWritingPlan } from '../../skills/story/scripts/core/story/writing-plan.mjs';
import { decisionList } from '../../skills/story/scripts/core/story/review.mjs';

/**
 * 会议逐话题四栏并列：会议判断、原话（按引用的行范围从 raw.md 取，同一范围只取一次）、
 * 人的裁决（选了哪一项、没选哪几项、原话）、当前结果（doc-refresh.md 里这一话题的段落）。
 * 取不到的一栏写「未取得，未验证」，不给空对象。
 */
function meetingTopicRows(src) {
  const notes = readJsonOrNull(path.join(src, 'meeting-notes.json'));
  const meetings = Array.isArray(notes?.meetings) ? notes.meetings : null;
  if (!meetings) return ['`AR/story-src/meeting-notes.json` 读不出 `meetings` 列表——逐话题核对未取得，未验证。'];
  const flow = readJsonOrNull(path.join(src, 'story-flow.json'));
  const gates = (flow?.rounds ?? []).flatMap(r => r?.gates ?? []).filter(g => g?.gate === 'meeting');
  const refresh = readOrNull(path.join(src, 'doc-refresh.md'));
  const doc = refresh === null ? null : parseDocument(refresh);
  const quoted = new Map();
  const out = [];
  for (const m of meetings) {
    const stem = String(m?.source ?? '').replace(/\.[^.]+$/, '');
    const key = `${stem}@${String(m?.source_sha ?? '').slice(0, 8)}`;
    const raw = readOrNull(path.join(src, 'meetings', stem, String(m?.source_sha ?? '').slice(0, 8), 'raw.md'));
    const rawLines = raw === null ? null : raw.split(/\r?\n/);
    for (const t of Array.isArray(m?.topics) ? m.topics : []) {
      out.push('', `#### ${key}/${t.id} ${t.title ?? ''}`, '', `- **会议判断**：${t.finding || '（没写）'}`);
      for (const ev of Array.isArray(t.evidence) ? t.evidence : []) {
        const at = `raw.md L${ev.start}–L${ev.end}`;
        const k = `${key}:${ev.start}-${ev.end}`;
        if (quoted.has(k)) { out.push(`- **原话** ${at}：同 ${quoted.get(k)}`); continue; }
        quoted.set(k, t.id);
        out.push(rawLines ? `- **原话** ${at}：` : `- **原话** ${at}：未取得，未验证`,
          ...(rawLines ? rawLines.slice(ev.start - 1, ev.end).map(l => `  > ${l}`) : []));
      }
      const g = gates.filter(x => x.meeting === key && x.item === t.id).pop();
      if (g) {
        const opts = Array.isArray(g.options) ? g.options : [];
        const chosen = opts.find(o => o.key === g.chosen);
        out.push(`- **人的裁决**：选了「${g.chosen}」${chosen?.label ?? ''}；没选：`
          + `${opts.filter(o => o.key !== g.chosen).map(o => `「${o.key}」${o.label}`).join('；') || '无'}；原话：${g.basis || '—'}`);
      } else {
        out.push(`- **人的裁决**：${t.question ? '未裁决——这个话题要问人，关卡记录里没有它' : '没有单独摆给人，随材料关卡一并确认'}`);
      }
      const h = doc?.headings.find(x => x.raw === `${key}/${t.id}` || x.raw.startsWith(`${key}/${t.id} `));
      out.push(...(!doc ? ['- **当前结果**：`AR/story-src/doc-refresh.md` 读不到，未验证']
        : !h ? ['- **当前结果**：doc-refresh.md 里没有这个话题的段落']
          : ['- **当前结果**（doc-refresh.md）：',
            ...doc.lines.slice(h.at + 1, headingEnd(doc, h)).filter(l => l.trim()).map(l => `  > ${l}`)]));
    }
  }
  return out;
}

/**
 * 登记表的两问：仍开着的选择有没有被正文替人选了一边（按选项后果对照行为与验收判）；
 * 登记成已定的那几条连同澄清正文一起摆出来 —— **判的是「这个结论谁给的」**。
 *
 * 只给 id 与标题（回看清单已有）判不了这件事：`settled` 的问题从来不在形态，
 * 在于结论没有来源——例如 `decider` 写「开发侧，确认归档动作已安排」、
 * 而需求方从没说过这句话，标题还写着「待评审确认」。要判它，审查手上得有
 * 作者写的依据原文，再回材料、会议原话与评审记录去对。
 *
 * 一条都没有时也说出来：`settled` 一条不登记同样可能是漏登记。
 */
function decisionRows(decisionsPath) {
  const all = decisionList(readJsonOrNull(decisionsPath));
  if (!all) return ['', '### 登记成已定的那几条', '', '`AR/story-src/decisions.json` 读不出登记列表——这一节未取得，未验证。'];
  const open = all.filter(d => d?.status === 'open');
  const settled = all.filter(d => d?.status === 'settled');
  const out = ['', '### 仍开着的选择：受影响的行为有没有被写成已定', '',
    open.length
      ? '逐条按各选项的实际后果，对照 Spec、Story 与 `acceptance.yaml` 里的功能、流程、异常与验收：'
        + '依赖这个选择的行为只写了共同要求与条件，还是已经替人选了一边。判的是后果，不是正文里有没有「待定」二字。'
      : '本轮没有仍开着的条目。',
    ...(open.length ? [''] : []), ...open.map(d => `- **${d.id ?? '（无编号）'}** ${String(d.title ?? '').trim()}`
      + `（该谁定：${String(d.decider ?? '').trim() || '没写'}）`)];
  return [...out, ...settledDetail(settled)];
}

function settledDetail(settled) {
  const out = ['', '### 登记成已定的那几条：结论是谁给的', '',
    '逐条回材料、会议原话与评审记录核：这个结论有没有人真的表过态。'
    + '`decider` 有名字只说明该谁定；「已安排」「某某侧确认」是转述或计划，不是表态。'];
  if (!settled.length) {
    out.push('', '本轮没有登记成已定的条目。');
    return out;
  }
  for (const d of settled) {
    out.push('', `#### ${d.id ?? '（无编号）'} ${String(d.title ?? '').trim()}`, '',
      `- **该谁定**：${String(d.decider ?? '').trim() || '（没写）'}`,
      `- **评审时要人做什么**：${String(d.review_mode ?? '').trim() || '（没写）'}`,
      '- **作者写的澄清正文**：',
      ...String(d.clarification ?? '（没写）').split(/\r?\n/).map(l => `  > ${l}`));
  }
  return out;
}

/** 围栏包一段行：外层比里面最长的围栏多一个反引号。 */
function fenced(rows, lang) {
  const mark = '`'.repeat(longestFence(rows.join('\n')) + 1);
  return [`${mark}${lang}`, ...rows, mark];
}

/**
 * 上游每张图与 story 里带同一图源标记的图并排：源图内容、承接图内容逐张给，多源合一时列全来源。
 * 判的是关系保没保持，不是节点同不同名——并排才看得出来。
 */
function diagramPairRows(root, story, contract) {
  const carried = diagramsOf(story);
  const out = [];
  for (const [label, text] of upstreamDocs({ contract, featureRoot: root })) {
    for (const d of diagramsOf(text)) {
      const tag = `${label} ${d.id}`;
      out.push('', `#### ${tag}（${diagramTopic(d)}）`, '', '上游原图：', '', ...fenced(d.lines, 'mermaid'));
      const hits = carried.filter(c => c.sources.includes(tag));
      if (!hits.length) out.push('', 'story 里没有带这个图源标记的图。');
      for (const c of hits) {
        const others = c.sources.filter(x => x !== tag);
        out.push('', `story 里承接它的图（${c.title || '章首'}${others.length ? `；同一张还承接 ${others.join('、')}` : ''}）：`,
          '', ...fenced(c.lines, 'mermaid'));
      }
    }
  }
  return out.length ? out : ['', '上游（系统设计、spec）里没有图。'];
}

// 盘上实际有哪几版会议材料：路径逐版列出，审查不必猜目录形状
function meetingVersions(srcDir) {
  const base = path.join(srcDir, 'meetings');
  if (!fs.existsSync(base)) return [];
  const out = [];
  for (const stem of fs.readdirSync(base).sort()) {
    const dir = path.join(base, stem);
    if (!fs.statSync(dir).isDirectory()) continue;
    for (const version of fs.readdirSync(dir).sort()) {
      if (fs.existsSync(path.join(dir, version, 'raw.md'))) {
        out.push(`AR/story-src/meetings/${stem}/${version}`);
      }
    }
  }
  return out;
}

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
    '- `acceptance.yaml` —— 验收条目',
    '- `spec/spec.md` —— 当前阶段已经成立的产品约束，业务条件从它与原材料一起核；',
    '- `AR/story-src/decisions.json` —— 已登记的判断：哪些定了、哪些还开着，未决的去向从它核');
  rows.push('', '### 另外这几份按需去读', '',
    '- `AR/story-src/story-flow.json` —— 已确认的本 AR 范围；',
    '- `.backups/local/` —— 收口提交覆盖 `AR/design.md` 之前的上游那一份（有才有）。'
      + '当前 `AR/design.md` 是提取稿，回查上游原话看它与 `RR`、`SR` 原文，不拿提取稿自证；',
    '- 下面那一节的图片身份目录 —— 每张图是什么、用没用、不用的理由。');
  // 会议逐话题把会议判断、原话、人的裁决与当前结果并排：审查要对着原话判，不只读模型写的结果。
  // 位置逐版列实际存在的那些，纠偏留痕仍回原件看。
  if (fs.existsSync(path.join(src, 'meeting-notes.json'))) {
    rows.push('', '### 会议材料：逐话题并列', '',
      '每个话题核三句：原话里哪些是确定的；人选了什么、没选什么；当前结果里每个确定的行为有没有依据'
      + '（没选的那一项的做法出现在结果里，算问题）。');
    for (const dir of meetingVersions(src)) {
      rows.push(`- \`${dir}/raw.md\` —— 原文，行号指它；`
        + `\`${dir}/corrections.json\` 是纠偏留痕，\`${dir}/evidence.md\` 是纠偏后的阅读件`);
    }
    rows.push(...meetingTopicRows(src));
  }

  rows.push(...decisionRows(planCtx.decisionsPath));

  rows.push('', '### 上游图与 story 里承接它的图', '',
    '逐张对照参与者、请求与返回、条件分支、结果归谁、失败后的责任；图种可以换，声称承接却丢了关系才算问题。',
    ...diagramPairRows(root, story, contract));

  // 作者对已用于写章的安排做过实质调整时才有这份：它是解释材料，不是事实真源
  if (fs.existsSync(path.join(src, 'template-adjustments.md'))) {
    rows.push('', '### 写作设计的调整记录', '',
      '- `AR/story-src/template-adjustments.md` —— 作者改掉了原来的安排与原因。'
      + '核改动之后原来要解释的关系有没有丢；理由写了不等于成立，按正文与原材料判。');
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
