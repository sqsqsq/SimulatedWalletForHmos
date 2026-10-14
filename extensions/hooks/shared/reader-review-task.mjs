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
  const out = ['', '### 仍开着的选择：受影响的行为有没有被写成已定', '',
    open.length
      ? '**每一条都写一句结论**，写在读者审查这一条的证据格：依赖这个选择的行为在 Spec、Story 与 `acceptance.yaml` 的哪几处，'
        + '那几处只写了共同要求与条件，还是已经替人选了一边。各选项（含保持待定）都会有的行为才是共同要求；'
        + '只属于某一个选项的做法或数值出现在正文与验收里，就是替人选了一边，同时记进 blocking_findings。判的是后果，不是正文里有没有「待定」二字。'
      : '本轮没有仍开着的条目。'];
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
    '逐条回材料、会议原话与评审记录核：这个结论有没有人真的表过态。'
    + '`decider` 有名字只说明该谁定；依据要指得到那个人表态的位置，转述与计划都不是表态。'];
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
 * 读者审查必读的输入 —— **从登记事实派生，任务书与报告核对共用这一份**。
 *
 * 审查对象与写作设计、范围与登记、Spec 与验收、材料清单 `origins` 的每份阅读稿（只取图的原件由图片登记一节核，
 * 不进这张表）、会议判断与刷新结果、界面说明，以及 update 开着时这一轮的 `before/` 与 update-notes。
 * `digest` 是这一刻的内容摘要，进入审查片段：依据变了片段跟着变；story 按作者区另算、流程状态与 notes 不算身份。
 *
 * @returns {{inputs: {path:string, purpose:string, digest:string|null, missing:boolean}[], update: string|null, gaps: string[]}}
 */
export function reviewInputs(projectRoot, feature) {
  const root = featureRoot(projectRoot, feature);
  const inputs = [];
  const gaps = [];
  const add = (rel, purpose, { identity = true, optional = false } = {}) => {
    if (inputs.some(x => x.path === rel)) return;
    let bytes = null;
    try { bytes = fs.readFileSync(path.join(root, rel)); } catch { bytes = null; }
    if (bytes === null && optional) return;
    inputs.push({ path: rel, purpose, missing: bytes === null,
      digest: bytes && identity ? crypto.createHash('sha256').update(bytes).digest('hex').slice(0, 12) : null });
  };
  add('AR/story.md', '审查对象', { identity: false });
  add('AR/story-src/story-template.md', '作者的写作设计');
  add('AR/story-src/story-flow.json', '已确认的本 AR 范围', { identity: false });
  add('AR/story-src/decisions.json', '已登记的决定：哪些定了、哪些开着');
  add('AR/story-src/materials.json', '材料清单与图片登记');
  add('spec/spec.md', '已经成立的产品约束');
  add('acceptance.yaml', '验收条目');
  const manifest = readJsonOrNull(path.join(root, 'AR', 'story-src', 'materials.json'));
  if (manifest && !Array.isArray(manifest.origins)) gaps.push('AR/story-src/materials.json 读不出 `origins`，原材料集合未取得');
  for (const o of manifest?.origins ?? []) {
    if ((o.image_paths ?? []).length) continue;
    for (const r of o.readable_paths ?? []) add(r, `原材料阅读稿（来源 ${o.path}）`);
  }
  const contract = contractOf(projectRoot);
  for (const decl of Object.values(contract?.sources ?? {})) {
    if (decl?.path && !decl.derived) add(decl.path, decl.label ?? '合同来源', { optional: true });
  }
  add('AR/story-src/meeting-notes.json', '会议判断', { optional: true });
  add('AR/story-src/doc-refresh.md', '会议与材料刷新后的当前结果', { optional: true });
  add('ux-reference/README.md', '界面交互说明', { optional: true });
  const flow = readJsonOrNull(path.join(root, 'AR', 'story-src', 'story-flow.json'));
  const rid = flow?.update?.open ?? null;
  if (rid) {
    const base = `AR/story-src/updates/${rid}`;
    if (!fs.existsSync(path.join(root, base, 'before'))) {
      gaps.push(`update ${rid} 开着，却没有 \`${base}/before/\`——这一轮缺比较基准，不是没有变化`);
    }
    for (const rel of ['AR/story.md', 'AR/review.md', 'spec/spec.md', 'plan/plan.md', 'acceptance.yaml', 'AR/story-src/decisions.json']) {
      add(`${base}/before/${rel}`, `update 前的 ${rel}`, { optional: true });
    }
    add(`${base}/update-notes.md`, '作者对这一轮变化与影响的判断（待核，不是依据）', { identity: false, optional: true });
  }
  // notes 是可读的作者判断，不是必审依据：审查之后再写它不让一份有效报告失效
  for (const x of inputs) x.required = !x.missing && !x.path.endsWith('/update-notes.md');
  return { inputs, update: rid, gaps };
}

/** 读者审查明细的四个键 —— 无论结论都写，任务书与报告核对共用这一份定义。 */
export const READER_DETAIL_KEYS = ['blocking_findings', 'advisories', 'examined_inputs', 'unreviewed'];

/** 明细里写的路径规范成表里的写法：去反引号、反斜杠换正斜杠、去开头的 `./`。 */
const inputPath = v => String(v ?? '').replace(/`/g, '').replace(/\\/g, '/').replace(/^\.\//, '').trim();

/**
 * 明细与必审集合、结论自洽吗 —— 机器核声明与集合，读懂了没有它判不了。
 *
 * 核：四个键都在且是列表；examined_inputs 不重复、每份都在表里；必审输入要么读过要么列进 unreviewed；
 * PASS 不带阻断项、不带未核的必审输入；FAIL 要列出阻断项。`basis` 缺席（核历史报告）时不核覆盖。
 */
export function readerDetailProblems(details, status, basis) {
  const missing = READER_DETAIL_KEYS.filter(k => !(k in (details ?? {})));
  if (missing.length) return [`判了 ${status}，明细缺 ${missing.join('、')}——四个键无论结论都写，没有内容的写空列表`];
  const wrong = READER_DETAIL_KEYS.filter(k => !Array.isArray(details[k]));
  if (wrong.length) return [`明细的 ${wrong.join('、')} 不是列表`];
  const out = [];
  const blocking = details.blocking_findings;
  if (status === 'PASS' && blocking.length) out.push(`判了 PASS 却列了 ${blocking.length} 条阻断项，结论与明细矛盾`);
  if (status === 'FAIL' && !blocking.length) out.push('判了 FAIL 却没有阻断项，说不出拦在哪');
  if (!basis) return out;
  const table = new Map(basis.inputs.map(x => [x.path, x]));
  const seen = new Set();
  for (const raw of details.examined_inputs) {
    const p = inputPath(typeof raw === 'string' ? raw : raw?.path);
    if (!p || !table.has(p)) out.push(`examined_inputs 里的「${p || JSON.stringify(raw)}」不在「读这些」表里——照抄表里的路径`);
    else if (seen.has(p)) out.push(`examined_inputs 里「${p}」写了两次`);
    seen.add(p);
  }
  const skipped = new Set(details.unreviewed.map(u => inputPath(typeof u === 'string' ? u.split(/[：:]/)[0] : (u?.path ?? u?.item))));
  const silent = basis.inputs.filter(x => x.required && !seen.has(x.path) && !skipped.has(x.path)).map(x => x.path);
  if (silent.length) out.push(`必审输入既没出现在 examined_inputs 也没列进 unreviewed：${silent.join('、')}`);
  const open = basis.inputs.filter(x => x.required && skipped.has(x.path)).map(x => x.path);
  if (status === 'PASS' && open.length) out.push(`判了 PASS，必审输入却有没核完的：${open.join('、')}——读完再判，或如实不判 PASS`);
  return out;
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
  const basis = reviewInputs(projectRoot, feature);
  rows.push(...basis.inputs.map(x => `- \`${x.path}\`${x.digest ? `（摘要 ${x.digest}）` : ''} —— ${x.purpose}`
    + (x.missing ? '　**读不到**：与它有关的判断写未验证' : '')),
  ...basis.gaps.map(g => `- **输入有缺口**：${g}`));
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

  // **有序阅读入口，不搬全文**：审查者分段读盘上原文，任务里给文件、内容摘要与按作者区标题排好的阅读段。
  // 摘要只算作者区（机器区整段换成区名）：投影刷新不换审查对象，作者改一个字就换。正式审查前 pre_phase
  // 已把阅读图切回 Mermaid，盘上读到的就是被审的那一份。
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
  rows.push('', '### 回看清单：作者逐条处置的对象，去向由你核', '',
    ...recheckRows(recheckItems(planCtx, contract ? readWritingPlan(planCtx) : null, story)));

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
    rows.push('', '### 会议材料：逐话题并列', '',
      '每个话题核三句：原话里哪些是确定的；人选了什么、没选什么；当前结果里每个确定的行为有没有依据'
      + '（没选的那一项的做法出现在结果里，算问题）。');
    for (const x of basis.inputs.filter(i => /\/meetings\/.+\/raw\.md$/.test(i.path))) {
      const dir = path.posix.dirname(x.path);
      rows.push(`- \`${x.path}\` —— 原文，行号指它；`
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
