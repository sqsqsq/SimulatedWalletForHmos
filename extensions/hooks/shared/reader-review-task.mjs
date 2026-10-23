/**
 * 读者审查的任务书 —— **这一次要看的东西**，从真源渲染。
 *
 * 判据本身（审什么、什么算 blocking、什么不做）只在 overlay 的 `story_reader_review` 里写一份；
 * 这里出的是它判不出来的部分：本需求的输入路径、这一版合同的十章问题与章级维度、
 * 材料清单里现有的图逐张。同一件事在两处各写一遍，改一处另一处就静默过期。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { extensionRoot, featureRoot, readJsonOrNull } from './paths.mjs';
import { headingEnd, parseDocument, ZONE_BEGIN, ZONE_END, zonesByLine }
  from '../../skills/story/scripts/core/story/document.mjs';
import { diagramsOf, diagramTopic, imagesIn, readablePaths }
  from '../../skills/story/scripts/core/story/images.mjs';
import { originRows, sourceStatus, upstreamDocs } from '../../skills/story/scripts/core/story/sources.mjs';
import { recheckItems, recheckRows } from '../../skills/story/scripts/core/story/recheck.mjs';
import { inputRows, reviewInputs, signedGateRows } from './review-inputs.mjs';
import { carryTargets, readWritingPlan } from '../../skills/story/scripts/core/story/writing-plan.mjs';
import { decisionList } from '../../skills/story/scripts/core/story/review.mjs';

/**
 * 会议逐话题四栏并列：会议判断、原话（按引用的行范围从 raw.md 取，同一范围只取一次）、
 * 人的裁决（关卡记录里生效的人签选了哪一项、没选哪几项；原话只在「人签原文」给一份）、
 * 当前结果（doc-refresh.md 里这一话题的段落）。
 * 取不到的一栏写「未取得，未验证」，不给空对象。
 */
function meetingTopicRows(src) {
  const notes = readJsonOrNull(path.join(src, 'meeting-notes.json'));
  const meetings = Array.isArray(notes?.meetings) ? notes.meetings : null;
  if (!meetings) return ['`AR/story-src/meeting-notes.json` 读不出 `meetings` 列表——逐话题核对未取得，未验证。'];
  const flow = readJsonOrNull(path.join(src, 'story-flow.json'));
  const gates = (flow?.rounds ?? []).flatMap(r => r?.gates ?? [])
    .filter(g => g?.gate === 'meeting' && g?.by === 'human' && g?.outcome === 'accepted');
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
          + `${opts.filter(o => o.key !== g.chosen).map(o => `「${o.key}」${o.label}`).join('；') || '无'}；原话见「人签原文」`);
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
 * 登记表的两问，两类条目都连同作者写的澄清正文原样摆出来：
 * 仍开着的选择有没有被正文替人选了一边——**逐条给结论**，对照的是各选项的实际后果；
 * 登记成已定的那几条 —— **判的是「这个结论谁给的」**。
 *
 * 只给 id 与标题判不了这两件事：替人选边要拿选项原文去对正文，已定的结论要拿依据原文
 * 回材料、会议原话与评审记录去对。
 *
 * 一条都没有时也说出来：`settled` 一条不登记同样可能是漏登记。
 */
function decisionRows(decisionsPath) {
  const all = decisionList(readJsonOrNull(decisionsPath));
  if (!all) return ['', '### 登记成已定的那几条', '', '`AR/story-src/decisions.json` 读不出登记列表——这一节未取得，未验证。'];
  const open = all.filter(d => d?.status === 'open');
  const settled = all.filter(d => d?.status === 'settled');
  const out = ['', '### 先核：仍开着的选择与正文的冲突（逐章核查之前做）', '',
    open.length ? '按规则「核的先后」①逐条给结论，写在读者审查这一条的证据格。' : '本轮没有仍开着的条目。'];
  for (const d of open) {
    out.push('', `#### ${d.id ?? '（无编号）'} ${String(d.title ?? '').trim()}`, '',
      `- **该谁定**：${String(d.decider ?? '').trim() || '（没写）'}`,
      '- **作者写的澄清正文**（选项与各自的后果在这里）：',
      ...String(d.clarification ?? '（没写）').split(/\r?\n/).map(l => `  > ${l}`));
  }
  return [...out, ...settledDetail(settled)];
}

function settledDetail(settled) {
  const out = ['', '### 登记成已定的那几条：结论是谁给的', '',
    '按规则「核的先后」①回人签原文、材料与评审记录核。'];
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
 * 上游每张图与写作设计登记承接它的全部小节并排：原图，加每一节的正文、表与图。
 * 判的是关系保没保持，不是节点同不同名；没登记、定不到、空着的位置列成缺口。审查仍从全部原件反查，不受登记集合限制。
 */
function diagramPairRows(planCtx, plan, story) {
  const out = [];
  const targets = plan ? carryTargets(plan, story) : [];
  for (const [label, text] of upstreamDocs(planCtx)) {
    for (const d of diagramsOf(text)) {
      const tag = `${label} ${d.id}`;
      out.push('', `#### ${tag}（${diagramTopic(d)}）`, '', '上游原图：', '', ...fenced(d.lines, 'mermaid'));
      const hits = targets.filter(c => c.source === tag);
      if (!hits.length) out.push('', '写作设计没有登记承接这张图的小节。');
      for (const c of hits) {
        out.push('', `承接它的「${c.where}」：`, '', ...(c.problem ? [`（${c.problem}）`] : fenced(c.body.split(/\r?\n/), 'markdown')));
      }
    }
  }
  return out.length ? out : ['', '上游（系统设计、spec）里没有图。'];
}

/** 写作设计里的阅读图选择：不采用的理由，或每个候选的问题、增益、放置与依据（依据由审查者按路径读原文）。 */
function readingChoiceRows(plan) {
  const r = plan?.reading;
  if (!r?.declared) return ['', '写作设计没有写阅读图选择。'];
  if (r.noneReason !== null) return ['', `不采用：${r.noneReason}`];
  return r.items.flatMap(x => ['', `- **${x.id}**：阅读问题「${x.question}」；增益「${x.gain}」；放置 ${x.placement}`,
    ...x.basis.map(b => `  - 依据：${b}`)]);
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
    '### 读这些（必审输入，报告的 examined_inputs 按这张表逐份声明）',
    '',
    '从原件反查成果：先读原材料与已定决定，再读作者产物；大文件分段读齐，读不到或没读完的写进 unreviewed。',
    '',
  ];
  const basis = reviewInputs(projectRoot, feature, 'story');
  rows.push(...inputRows(basis));
  if (basis.update) {
    rows.push('', `### 本轮 update ${basis.update}：新稿对照有效旧依据`, '',
      '`before/` 是这一轮动手前的现场。逐处核：新稿改掉的旧约束、旧决定与旧验收，改动依据是谁给的、他有没有这个权限；'
      + '与仍有效的旧约束冲突而没经有权人裁定的，记进 blocking_findings。update-notes 是作者的判断，按原件与 before 核，不当依据。');
  }

  const storyPath = path.join(root, 'AR', 'story.md');
  const story = readOrNull(storyPath);
  if (story === null || !story.trim()) {
    rows.push('', '`AR/story.md` 现在读不到或是空的——本项 SKIP，如实写 SKIP，不要凭空作答。');
    return rows.join('\n');
  }

  // 人签原文先于作者登记，二者都先于逐章：作者登记是对人签的解释，要拿原话核
  rows.push('', '### 人签原文：人当时看到的选项与回答', '', ...signedGateRows(root));
  rows.push(...decisionRows(path.join(root, 'AR', 'story-src', 'decisions.json')));

  // **有序阅读入口，不搬全文**：审查者分段读盘上原文，任务里给文件、内容摘要与按作者区标题排好的阅读段。
  // 摘要只算作者区（机器区整段换成区名）：投影刷新不换审查对象，作者改一个字就换。正式审查前 pre_phase
  // 已把 story 放回正式形态（阅读槽为空），盘上读到的就是被审的那一份。
  rows.push('', '### 审查对象：当前 `AR/story.md`（按下面的段落顺序读盘上原文）', '',
    ...readingRows('AR/story.md', authorZone(story)));

  // 写作设计：作者这一版的阅读主线与骨架。读不到不能拿空设计当审过，说成缺口。
  const plan = readOrNull(path.join(root, 'AR', 'story-src', 'story-template.md'));
  rows.push('', '### 作者的写作设计：`AR/story-src/story-template.md`', '');
  if (plan === null || !plan.trim()) {
    rows.push('**写作设计缺口**：`AR/story-src/story-template.md` 读不到或是空的。照原材料与范围审正文，'
      + '把「没有可核的写作设计」写进结论——它是本轮的阻断问题。');
  } else {
    rows.push('（作者对本需求的阅读主线与每章骨架，是待核的作者判断，不是审查标准）', '',
      ...readingRows('AR/story-src/story-template.md', plan));
  }

  // 回看清单：作者十章齐后逐条处置的同一张清单，这里核每一条的去向成不成立。
  const src = path.join(root, 'AR', 'story-src');
  const planCtx = { contract, featureRoot: root, srcDir: src, storyPath,
    decisionsPath: path.join(src, 'decisions.json'), templatePath: path.join(src, 'story-template.md') };
  const parsed = contract ? readWritingPlan(planCtx) : null;
  rows.push('', '### 回看清单：作者逐条处置的对象，去向由你核', '',
    ...recheckRows(recheckItems(planCtx, parsed, story)));

  // 原材料原文逐份给位置：审查要能回到原件，不只看作者转述之后的样子。该有而读不到的说成缺口。
  const { blocking } = sourceStatus({ contract, featureRoot: root });
  if (blocking.length) {
    rows.push('', '### 缺席的必备来源', '',
      ...blocking.map(m => `- **读不到 \`${m.rel}\`**——它是必备来源；与它有关的判断写未验证，不替它下结论`));
  }
  // 来源集合与作者任务包同一份渲染：附录材料表对着它核，不拿作者表自证完整。
  rows.push('', '### 材料与来源（附录材料表对着它核）', '', ...originRows(planCtx));
  rows.push('', '### 另外这几份按需去读', '',
    '- `.backups/local/` —— 收口提交覆盖 `AR/design.md` 之前的上游那一份（有才有）。'
      + '当前 `AR/design.md` 是提取稿，回查上游原话看它与 `RR`、`SR` 原文，不拿提取稿自证；',
    '- 下面那一节的图片身份目录 —— 每张图是什么、用没用、不用的理由。');
  // 会议逐话题把会议判断、原话、人的裁决与当前结果并排：审查要对着原话判，不只读模型写的结果。
  // 版本位置取必审输入里登记的会议阅读稿，纠偏留痕仍回原件看。
  if (fs.existsSync(path.join(src, 'meeting-notes.json'))) {
    rows.push('', '### 会议材料：逐话题并列', '');
    for (const x of basis.inputs.filter(i => /\/meetings\/.+\/raw\.md$/.test(i.path))) {
      const dir = path.posix.dirname(x.path);
      rows.push(`- \`${x.path}\` —— 原文，行号指它；`
        + `\`${dir}/corrections.json\` 是纠偏留痕，\`${dir}/evidence.md\` 是纠偏后的阅读件`);
    }
    rows.push(...meetingTopicRows(src));
  }

  rows.push('', '### 上游图与 story 里承接它的小节', '', ...diagramPairRows(planCtx, parsed, story));
  rows.push('', '### 阅读图选择', '', ...readingChoiceRows(parsed));

  // 作者对已用于写章的安排做过实质调整时才有这份：它是解释材料，不是事实真源
  if (fs.existsSync(path.join(src, 'template-adjustments.md'))) {
    rows.push('', '### 写作设计的调整记录', '',
      '- `AR/story-src/template-adjustments.md` —— 作者改掉了原来的安排与原因（待核的作者判断）。');
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
  if (basis.visual) rows.push('', `**本阶段看图能力**：${basis.visual.fact}。这几张图的图面核对按规则里「Framework 裁定看不了图」那一款处理。`);

  // 方法与结论要求只在 overlay 的 `story_reader_review` 维护一份，宿主把它装配进 verifier 的任务；
  // 这里只给这一条在明细里的结构——框架通用输出只列非 PASS 项、details 写成文字，本条不同
  // 示例路径取「读这些」表里真实的前两份：照抄示例就是合法写法，不留要替换的占位
  const [seen, skipped] = basis.inputs.map(x => x.path);
  rows.push('', `### ${checkId} 在 YAML 明细里的结构`, '',
    `无论结论，\`verification_result.checks\` 里都有 ${checkId} 这一条；它的 \`details\` 是映射，四个键都是列表：`, '',
    '```yaml',
    `- id: ${checkId}`,
    '  status: FAIL        # 按你的结论写 PASS、WARN 或 FAIL',
    '  details:',
    '    blocking_findings: ["5.2 节写失败后回到签约页，7.1 节写停在结果页：同一失败两处去向不同"]',
    '    advisories: []',
    `    examined_inputs: [${JSON.stringify(seen)}]`,
    `    unreviewed: [{path: ${JSON.stringify(skipped ?? seen)}, reason: "只读到第 3 节，后面没读完"}]`,
    '```',
    '`examined_inputs` 与 `unreviewed` 合起来覆盖「读这些」表里的每一份；没有内容的键写 `[]`。');
  return rows.join('\n');
}

/** story 的作者区：机器区（投影）整段换成一行区名。 */
function authorZone(story) {
  const lines = String(story).split(/\r?\n/);
  const zones = zonesByLine(lines);
  const out = [];
  lines.forEach((line, i) => {
    if (line.startsWith(ZONE_BEGIN)) out.push(`（附录机器区：${zones.get(i + 1)?.name ?? line.slice(ZONE_BEGIN.length).split(' · ')[0]}）`);
    else if (!zones.has(i) && line.trim() !== ZONE_END) out.push(line);
  });
  return out.join('\n');
}

/** 读一份文件；读不到返回 null——空串与「读不到」在这里必须分得开。 */
function readOrNull(abs) {
  try { return fs.readFileSync(abs, 'utf-8'); } catch { return null; }
}

/** 正文里最长的那道围栏有几个反引号（至少 3，让外层总比它长）。 */
function longestFence(text) {
  let most = 3;
  for (const line of String(text ?? '').split(/\r?\n/)) {
    const m = line.match(/^[ \t]*(`{3,})/);
    if (m && m[1].length > most) most = m[1].length;
  }
  return most;
}

/**
 * 一份文件的阅读入口：内容摘要与按作者区真实标题排好的阅读段（不带行号，机器区排版不影响它）。
 *
 * 摘要取 `basis`（story 取作者区）：正文变了审查对象跟着变。读取以盘上原文为准，摘要对不上时
 * 说明读到的不是这一版——停下重取当前请求，不拼接不同版本的局部判断。
 */
function readingRows(rel, basis) {
  const digest = crypto.createHash('sha256').update(String(basis).replace(/\r\n/g, '\n')).digest('hex').slice(0, 16);
  // 段落按作者区的标题给，不给行号：行号会随机器区重投的排版（多一个空行）漂移，
  // 审查对象就跟着换了，而作者内容一字未动。读的时候在盘上按标题找，标题都在作者区里。
  const doc = parseDocument(basis);
  const heads = doc.headings.filter(h => h.level <= 3);
  const rows = [`- \`${rel}\`：内容摘要 ${digest}。按下面的标题顺序分段读盘上原文，每段从这个标题读到下一个标题之前，`
    + '段与段首尾相接、连起来是全文；段名里的上级标题只说明它在哪一章。'
    + '读不到或读到的与这一版对不上，写明哪几段未审，不凭印象补'];
  if (!heads.length || doc.lines.slice(0, heads[0].at).some(l => l.trim())) rows.push('  - （第一个标题之前的开头）');
  const trail = [];
  for (const h of heads) {
    while (trail.length && trail[trail.length - 1].level >= h.level) trail.pop();
    trail.push(h);
    const label = trail.filter(t => t === h || t.level > 1);
    rows.push(`  - ${label.map(t => `${'#'.repeat(t.level)} ${t.raw}`).join(' › ')}`);
  }
  return rows;
}
