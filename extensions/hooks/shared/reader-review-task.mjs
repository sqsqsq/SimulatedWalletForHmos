/**
 * Story 独立人读审查的任务书 —— **判据与这一次要看的东西**，从真源渲染。
 *
 * 判据本身（审什么、什么算 blocking、什么不做）只在 `rules/story-reader-rules.yaml` 的 `story_reader_review`
 * 里写一份，这里原样带上；其余是它判不出来的部分：这一次审查材料的唯一一份文件索引、读法、决定与会议的对照、
 * 来源图与采用它的图、这一版合同的十章问题与章级维度、材料清单里现有的图逐张。同一件事在两处各写一遍，改一处另一处就静默过期。
 * 唯一消费者是 `story-build review --action prepare`。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { featureRoot, readJsonOrNull, readTextOrNull } from './paths.mjs';
import { parseYaml } from './yaml.mjs';
import { headingEnd, parseDocument } from '../../skills/story/scripts/core/story/document.mjs';
import { blueprintGraph } from './framework-access.mjs';
import { diagramBody, diagramsOf, diagramTopic, imagesIn, readablePaths }
  from '../../skills/story/scripts/core/story/images.mjs';
import { adoptedInputs } from '../../skills/story/scripts/core/story/design-source.mjs';
import { sourceStatus } from '../../skills/story/scripts/core/story/sources.mjs';
import { recheckItems, recheckRows } from '../../skills/story/scripts/core/story/recheck.mjs';
import { readWritingPlan } from '../../skills/story/scripts/core/story/writing-plan.mjs';
import { decisionList } from '../../skills/story/scripts/core/story/review.mjs';
import { reviewObject } from '../../skills/story/scripts/core/story/review-object.mjs';
import { reportFormat } from '../../skills/story/scripts/core/story/review-report-contract.mjs';

//: 本模块所在的扩展包根：判据与章节合同都属于机制，随包发布
const PACKAGE = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..');

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
      ? '**每一条都写一句结论**，写在「判据核对」表后的审查方法里：依赖这个选择的行为在 Story 正文、附录、Review 与关联蓝图的哪几处，'
        + '那几处只写了共同要求与条件，还是已经替人选了一边。各选项（含保持待定）都会有的行为才是共同要求；'
        + '只属于某一个选项的做法或数值出现在正文与验收里，就是替人选了一边，在「发现」表记一条，严重程度按所属判据。'
        + '按正文与验收实际写出的行为判。'
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
    + '要人表态才成立的事（业务口径、对外承诺、处置标「（评审动作）」的规约条目）指不出表态位置就是伪定案，它本该是 `open`。'
    + '`decider` 有名字只说明该谁定；依据要指得到那个人表态的位置，转述、计划与作者自己的推荐都不是表态。'
    + '判的是来源不是形态：`settled + confirm`（已有结论请人复核）是正常形态，评审记录里人工区空着也不证明无人表态。'];
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
 * story 里带图源标记的每张图与它的来源并排：来源图、story 的图逐张给，标明 reuse 还是 refine。
 * 判的是关系保没保持、细化有没有依据，不是节点同不同名——并排才看得出来。
 * 没被任何图引用的采用来源图单列：它的去向由材料取舍说明交代，不要求每张都搬。
 */
function diagramPairRows(projectRoot, root, story) {
  const docs = adoptedInputs({ projectRoot, flowPath: path.join(root, 'AR', 'story-src', 'story-flow.json') }).documents;
  const used = new Set();
  const out = [];
  for (const c of diagramsOf(story).filter(x => x.sources.length)) {
    out.push('', `#### story 的图（${diagramTopic(c)}）`, '', ...fenced(diagramBody(c), 'mermaid'));
    for (const s of c.sources) {
      const v = s.value ?? {};
      let lines = null;
      if (v.kind === 'document') {
        const hit = diagramsOf(docs.get(String(v.path ?? '')) ?? '').find(d => d.id === v.diagram);
        if (hit) { used.add(`${v.path} ${v.diagram}`); lines = diagramBody(hit); }
      } else if (v.kind === 'blueprint') {
        const got = blueprintGraph(projectRoot, v.blueprint_ref, v.graph_id);
        if (got.status === 'ok') lines = got.content.split(/\r?\n/);
      }
      out.push('', `来源 \`${s.raw}\`${lines ? `（${v.mode}）：` : '：指不到，机械检查已报'}`, ...(lines ? ['', ...fenced(lines, 'mermaid')] : []));
    }
  }
  const unused = [...docs].flatMap(([at, text]) => diagramsOf(text).filter(d => !used.has(`${at} ${d.id}`))
    .map(d => `- \`${at}\` ${d.id}（${diagramTopic(d)}）`));
  if (unused.length) out.push('', '没有被 story 引用的采用来源图（去向按材料取舍说明核）：', '', ...unused);
  if (out.length) return out;
  return ['', docs.size ? '采用来源里没有可解析的 Mermaid 图，story 也没有带图源标记的图；其他格式的图按原文自行对照。'
    : '本需求还没有冻结的采用来源，没有来源图要对照。'];
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

/** 读法：先来源与设计，再通读待审的三件；附件与投影同字节时只读附件一次。 */
const reading = shared => ['', '### 怎么读', '',
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
  ];

  const storyPath = path.join(root, 'AR', 'story.md');
  const story = readOrNull(storyPath) ?? '';
  // 回看清单：作者十章齐后逐条处置的同一张清单，这里核每一条的去向成不成立。
  const src = path.join(root, 'AR', 'story-src');
  const planCtx = { contract, featureRoot: root, srcDir: src, storyPath,
    decisionsPath: path.join(src, 'decisions.json'), templatePath: path.join(src, 'story-template.md') };
  rows.push('', '### 回看清单：作者逐条处置的对象，去向由你核', '',
    ...recheckRows(recheckItems(planCtx, contract ? readWritingPlan(planCtx) : null, story)));
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

  rows.push(...decisionRows(planCtx.decisionsPath));

  rows.push('', '### 来源图与 story 里采用它的图', '',
    '逐张对照参与者、请求与返回、条件分支、结果归谁、失败后的责任；节点同名、带着图源标记不等于关系还在；'
    + 'reuse 的图体机械已核，refine 核增量有没有依据、来源的关系有没有丢；没带标记的图是新绘，按设计与正文核。',
    ...diagramPairRows(projectRoot, root, story));

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

  rows.push(...reportFormat());
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
