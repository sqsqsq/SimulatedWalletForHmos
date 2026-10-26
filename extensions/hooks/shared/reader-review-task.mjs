/**
 * Story 独立人读审查的任务书 —— **判据与这一次要看的东西**，从真源渲染。
 *
 * 判据本身（审什么、什么算阻断、核的先后）只在 `rules/story-reader-rules.yaml` 的 `story_reader_review`
 * 里写一份，这里原样带上；其余是它判不出来的部分：这一次审查材料的唯一一份文件索引、读法、关卡人签与决定的对照、
 * 按作者区标题排好的阅读段、会议逐话题、上游图与承接它的小节、这一版合同的十章问题与章级维度、材料里的图逐张、
 * 附录材料表要对照的来源集合。同一件事在两处各写一遍，改一处另一处就静默过期。
 * 唯一消费者是 `story-build review --action prepare`。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { featureRoot, readJsonOrNull, readTextOrNull } from './paths.mjs';
import { storyReviewVisual } from './framework-access.mjs';
import { parseYaml } from './yaml.mjs';
import { headingEnd, parseDocument, ZONE_BEGIN, ZONE_END, zonesByLine }
  from '../../skills/story/scripts/core/story/document.mjs';
import { diagramsOf, diagramTopic, imagesIn, readablePaths }
  from '../../skills/story/scripts/core/story/images.mjs';
import { originRows, sourceStatus, upstreamDocs } from '../../skills/story/scripts/core/story/sources.mjs';
import { recheckItems, recheckRows } from '../../skills/story/scripts/core/story/recheck.mjs';
import { signedGateRows } from './review-inputs.mjs';
import { carryTargets, readWritingPlan } from '../../skills/story/scripts/core/story/writing-plan.mjs';
import { decisionList } from '../../skills/story/scripts/core/story/review.mjs';
import { readingWork } from '../../skills/story/scripts/core/story/figure-view.mjs';
import { reviewObject } from '../../skills/story/scripts/core/story/review-object.mjs';
import { reportFormat } from '../../skills/story/scripts/core/story/review-report-contract.mjs';

//: 本模块所在的扩展包根：判据与章节合同都属于机制，随包发布
const PACKAGE = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..');

/**
 * 会议逐话题四栏并列：会议判断、原话（按引用的行范围从 raw.md 取，同一范围只取一次）、
 * 人的裁决（关卡记录里生效的人签选了哪一项、没选哪几项；原话只在「关卡人签」给一份）、
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
          + `${opts.filter(o => o.key !== g.chosen).map(o => `「${o.key}」${o.label}`).join('；') || '无'}；原话见「关卡人签」`);
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
 * 回关卡人签、问答原话、材料、会议原话与评审记录去对。
 *
 * 一条都没有时也说出来：`settled` 一条不登记同样可能是漏登记。
 */
function decisionRows(decisionsPath) {
  const all = decisionList(readJsonOrNull(decisionsPath));
  if (!all) return ['', '### 登记成已定的那几条', '', '`AR/story-src/decisions.json` 读不出登记列表——这一节未取得，未验证。'];
  const open = all.filter(d => d?.status === 'open');
  const settled = all.filter(d => d?.status === 'settled');
  const out = ['', '### 先核：仍开着的选择与正文的冲突（逐章核查之前做）', '',
    open.length ? '按判据「核的先后」①逐条给结论，写在「判据核对」表后的审查方法里；替人选了一边的同时在「发现」表记一条。'
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
    '按判据「核的先后」①回关卡人签、澄清正文里引用的问答原话、材料与评审记录核；引用的原话与作者的解释分开看。'];
  if (!settled.length) {
    out.push('', '本轮没有登记成已定的条目。');
    return out;
  }
  for (const d of settled) {
    out.push('', `#### ${d.id ?? '（无编号）'} ${String(d.title ?? '').trim()}`, '',
      `- **该谁定**：${String(d.decider ?? '').trim() || '（没写）'}`,
      `- **评审时要人做什么**：${String(d.review_mode ?? '').trim() || '（没写）'}`,
      '- **澄清正文**（引用的问答原话是依据，其余是作者的解释）：',
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
  return out.length ? out : ['', '本次采用的上游原件里没有图。'];
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

/** 章节合同：与本模块同一个包里的那一份（判据与合同都属于机制，随包发布）。 */
function contractOf() {
  return readJsonOrNull(path.join(PACKAGE, 'skills', 'story', 'contracts', 'story-chapters.json'));
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
 * 判据原文：与本模块同一个包里 `rules/story-reader-rules.yaml` 的 `semantic_checks`，按登记顺序全部取出。
 * 任务逐项发送、报告逐项核对都用这一份；读不到或某项没有说明是包坏了，照实停下。
 *
 * @returns {[string, {description: string, severity?: string, ai_prompt_hint?: string}][]}
 */
function readerChecks() {
  const text = readTextOrNull(path.join(PACKAGE, 'rules', 'story-reader-rules.yaml'));
  const checks = Object.entries((text === null ? null : parseYaml(text)?.semantic_checks) ?? {});
  const broken = checks.filter(([, c]) => !c?.description).map(([id]) => id);
  if (!checks.length || broken.length) {
    throw new Error(`rules/story-reader-rules.yaml 的 semantic_checks ${checks.length ? `里 ${broken.join('、')} 没有说明` : '读不出判据'}`
      + '：Story 读者审查的判据只写在那里');
  }
  return checks;
}

/** 报告「判据核对」要逐项写的判据 ID：与任务发送的是同一份判据。 */
export function readerCheckIds() {
  return readerChecks().map(([id]) => id);
}

/** 这一次审查对象的全部材料：待审的与只读对照的分列；任务自己不列（它就是这份）。 */
function objectRows(projectRoot, feature, contract, { rows, problems }) {
  const { blocking } = sourceStatus({ contract, featureRoot: featureRoot(projectRoot, feature) });
  const line = r => `- \`${r.path}\` —— ${r.label}`;
  return ['', '### 本次审查的材料（材料键按它们的原始字节算）', '',
    '待审（结论针对它们）：', ...rows.filter(r => r.role === 'object').map(line), '',
    '只读对照（据以判断，不在这次改）：', ...rows.filter(r => r.role === 'source').map(line),
    ...problems.map(p => `- **读不到**：${p}——与它有关的判断按「报告怎么写」第 5 条记进「发现」`),
    ...blocking.map(m => `- **读不到 \`${m.rel}\`**——它是必备来源；与它有关的判断按「报告怎么写」第 5 条记进「发现」`)];
}

/** 设计附件与蓝图的原生评审投影字节相同时给出两者路径：同一份内容在两个位置。 */
function sharedProjection(projectRoot, rows) {
  const attachment = rows.find(r => r.role === 'object' && r.path.endsWith('/AR/design-review.md'))?.path;
  const projection = rows.find(r => r.role === 'source' && r.path.endsWith('/component-blueprint.review.md'))?.path;
  const bytes = p => { try { return fs.readFileSync(path.join(projectRoot, ...p.split('/'))); } catch { return null; } };
  const a = attachment && bytes(attachment);
  const b = projection && bytes(projection);
  return a && b && a.equals(b) ? { attachment, projection } : null;
}

/**
 * 读法：先按派审载体说的情形定范围——首审、实质复审与上一版报告参考完整读，格式返修照用原回复已充分的判断、只补诊断点到的核验；
 * 完整读时先来源与设计，再通读待审的三件；附件与投影同字节时只读附件一次。
 */
const reading = shared => ['', '### 怎么读', '',
  '读到这份任务时，你已按派审载体只读 `AR/story.md` 做完首读，首读结论写在报告「判据核对」表后；下面是核源。',
  '先看派审载体说的是哪种情形。首审、上一份结论是 fail 的复审、带上一版材料报告参考的审查，按下面的顺序完整读。'
  + '格式返修只修上一份回复的报告形态：原回复的实质判断与判据覆盖充分就照用，只回材料核诊断点到的那部分；'
  + '诊断是缺判据、引用找不到、依据不足或结论矛盾，或者看不出原审查是否完整时，同样按下面的顺序完整读。', '',
  '1. 先读来源与人签（冻结输入里的原件、会议原文与人的裁决、决策登记），'
  + (shared
    ? '再读整体设计（蓝图），然后通读待审的 Story、Review 与设计附件；'
      + `设计附件 \`${shared.attachment}\` 与蓝图的原生评审投影 \`${shared.projection}\` 字节相同，完整读设计附件一次即可。`
    : '再读整体设计（蓝图与它的原生评审投影），然后通读待审的 Story、Review 与设计附件。')
  + '写作设计是作者的安排，作参考。',
  '2. 冻结输入里的提取稿是派生分析：回查上游看原件。',
  '3. 一份文件一次读不完时按范围接着读到末尾；读不到的按「报告怎么写」第 5 条处理。',
  '4. 发现整体业务矛盾时追到它的权威对象（决定、蓝图、来源），按它对这次交付的影响定严重程度。'];

/**
 * 任务书正文：判据原文，加这一次的输入与要回答的问题。
 *
 * @param {string} projectRoot
 * @param {string} feature
 */
export function readerReviewTask(projectRoot, feature) {
  const contract = contractOf();
  const root = featureRoot(projectRoot, feature);
  const checks = readerChecks();
  const object = reviewObject(projectRoot, feature, { withTask: false });
  const rows = [
    `## Story 独立人读审查（判据 ${checks.map(([id]) => id).join('、')}）`,
    '',
    ...checks.flatMap(([id, check]) => [
      `### 判据 ${id}（${check.severity ?? 'BLOCKER'}）`,
      '',
      String(check.description).trim(),
      '',
      `### 怎么审、结论写什么（${id}）`,
      '',
      String(check.ai_prompt_hint ?? '').trim(),
      '',
    ]),
    ...reading(sharedProjection(projectRoot, object.rows)),
    ...objectRows(projectRoot, feature, contract, object),
    ...(object.design ? ['', '### 设计状态（原生读取）', '',
      `蓝图${object.design.admitted ? '已准入' : '是草稿、未准入'}；原生问题 ${object.design.issues.length} 条`
        + `${object.design.issues.length ? '（下列）' : ''}。草稿可以送审，问题涉及的业务事实在人读件里是不是写成了待定或限制，按判据核。`,
      ...object.design.issues.map(i => `- ${i.code ?? i.id ?? 'issue'}${i.path ? ` @${i.path}` : ''}：${i.message ?? ''}`)] : []),
  ];
  const src = path.join(root, 'AR', 'story-src');
  const rid = readJsonOrNull(path.join(src, 'story-flow.json'))?.update?.open;
  if (rid) {
    rows.push('', `### 本轮 update ${rid}：新稿对照有效旧依据`, '',
      `\`AR/story-src/updates/${rid}/before/\` 是这一轮动手前的现场。逐处核：新稿改掉的旧约束、旧决定与旧验收，改动依据是谁给的、他有没有这个权限；`
      + '与仍有效的旧约束冲突而没经有权人裁定的，在「发现」表记阻断。update-notes 是作者的判断，按原件与 before 核，不当依据。');
  }

  // 人答先于逐章：关卡人签是来源之一，对话里答过的问题由登记条目的澄清正文引用原话，二者都拿原话核
  rows.push('', '### 关卡人签：流程关卡上人看到的选项与回答（人答的来源之一）', '', ...signedGateRows(root));
  rows.push(...decisionRows(path.join(src, 'decisions.json')));

  // **有序阅读入口，不搬全文**：审查者分段读盘上原文，任务里给文件、内容摘要与按作者区标题排好的阅读段。
  // 摘要只算作者区（机器区整段换成区名）：投影刷新不换审查对象，作者改一个字就换。准备审查时 story 已回到
  // 正式形态（正式图块都是按源的 Mermaid），盘上读到的就是被审的那一份。
  const storyPath = path.join(root, 'AR', 'story.md');
  const story = readOrNull(storyPath) ?? '';
  rows.push('', '### 审查对象：当前 `AR/story.md`（按下面的段落顺序读盘上原文）', '',
    ...(story.trim() ? readingRows('AR/story.md', authorZone(story)) : ['`AR/story.md` 读不到或是空的：按「报告怎么写」第 5 条记。']));
  // 已有的同图增强只给机械事实（哪几张、文件在哪、核到哪一步）；值不值得做、做得好不好按判据看图与 SVG 源码
  const work = readingWork(root);
  rows.push('', '### 已有的同图增强（机械事实）', '', ...(work.items.length
    ? work.items.map(i => `- ${i.id}：\`AR/figures/${i.id}.svg\`，图审工作 \`AR/story-src/figures/${i.id}.reading/\`——${i.state}${i.reason ? `（${i.reason}）` : ''}`)
    : ['没有已开始的同图增强：所有正式图都是 Mermaid。']));

  // 写作设计：作者这一版的阅读主线与骨架，是待核的作者判断
  const planText = readOrNull(path.join(src, 'story-template.md'));
  rows.push('', '### 作者的写作设计：`AR/story-src/story-template.md`', '',
    ...(planText === null || !planText.trim()
      ? ['**写作设计缺口**：`AR/story-src/story-template.md` 读不到或是空的。照原材料与范围审正文，'
        + '在「发现」表记一条：没有可核的写作设计。']
      : ['（作者对本需求的阅读主线与每章骨架，是待核的作者判断，不是审查标准）', '',
        ...readingRows('AR/story-src/story-template.md', planText)]));

  // 回看清单：作者十章齐后逐条处置的同一张清单，这里核每一条的去向成不成立。
  const planCtx = { contract, projectRoot, featureRoot: root, srcDir: src, storyPath,
    decisionsPath: path.join(src, 'decisions.json'), templatePath: path.join(src, 'story-template.md') };
  const plan = contract ? readWritingPlan(planCtx) : null;
  rows.push('', '### 回看清单：作者逐条处置的对象，去向由你核', '',
    ...recheckRows(recheckItems(planCtx, plan, story)));

  // 来源集合与作者任务包同一份渲染：附录材料表对着它核，不拿作者表自证完整。
  rows.push('', '### 材料与来源（附录材料表对着它核）', '',
    '逐行对着原件核「贡献」：写的是这份材料实际给了什么；没采纳的新值或冲突版本写了对比作用与裁决依据。', '',
    ...originRows(planCtx));

  // 会议逐话题把会议判断、原话、人的裁决与当前结果并排：审查要对着原话判，不只读模型写的结果。
  // 位置逐版列实际存在的那些，纠偏留痕仍回原件看。
  if (fs.existsSync(path.join(src, 'meeting-notes.json'))) {
    rows.push('', '### 会议材料：逐话题并列', '',
      '每个话题按「原话 → 人选的那一项 → 当前结果」核：回 `raw.md` 与 `corrections.json` 看原文，纠偏有没有改了意思、'
      + '引用的行范围指的是不是那句话；话题有没有漏，会议判断与当前结果有没有写出会上没说的；'
      + '原话里哪些是确定的，没收敛的有没有被替人定成结论；人选了什么、没选什么'
      + '（没选的那一项的做法出现在结果里，算问题）；当前结果里每个确定的行为有没有依据，仍未决的有没有传到产物里。');
    for (const dir of meetingVersions(src)) {
      rows.push(`- \`${dir}/raw.md\` —— 原文，行号指它；`
        + `\`${dir}/corrections.json\` 是纠偏留痕，\`${dir}/evidence.md\` 是纠偏后的阅读件`);
    }
    rows.push(...meetingTopicRows(src));
  }

  rows.push('', '### 上游图与 story 里承接它的小节', '', ...diagramPairRows(planCtx, plan, story));

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

  // 图**是什么、用没用、不用的理由**是这一次的数据；「怎么判」在上面的判据原文里。
  const images = imageRows(projectRoot, feature);
  rows.push('', '### 材料里的图（这一次有哪几张）', '');
  if (images.gap) {
    rows.push(`**输入有缺口**：${images.gap}。`
      + '「图用没用、取舍成不成立」这一项未核：在「发现」表按相关判据记一条 BLOCKER，写明这处缺口与未核的范围。');
  } else {
    rows.push(...(images.rows.length ? images.rows : ['材料清单里没有图片。']));
  }
  // 有要核的图才做视觉裁定：原生纯函数按冻结来源与当前蓝图算，事实写在这里，结论只认这一份
  const pictures = images.rows?.length || object.rows.some(r => r.label.endsWith('（image）'));
  if (pictures) rows.push('', ...visualRows(storyReviewVisual(projectRoot, feature)));

  rows.push(...reportFormat());
  return rows.join('\n');
}

/** 看图能力裁定的任务行：允许图面延期、不允许延期、取不到三种照实写。 */
function visualRows(v) {
  if (v.status !== 'ok') {
    return [`**本次看图能力裁定取不到**（${(v.issues ?? []).map(i => i.message ?? i.code).join('；') || v.status}）：`
      + '看不了图就是没读完，按「报告怎么写」第 5 条记。'];
  }
  return [`**本次看图能力**：${v.fact}。`, v.deferral
    ? '**图面核对可以按能力缺口延期**：按判据里「图面核对可以按能力缺口延期」那一款处理。'
    : v.capability.has_vision ? '能看图：图面照常核。' : '图面核对不能延期：看不了图就是没读完，按「报告怎么写」第 5 条记。'];
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

