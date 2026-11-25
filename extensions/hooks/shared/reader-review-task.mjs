/**
 * Story 独立人读审查的任务书 —— **判据与这一次要看的东西**，从真源渲染。
 *
 * 判据本身（审什么、什么算阻断、核的先后）只在 `rules/story-reader-rules.yaml` 的 `story_reader_review`
 * 里写一份，这里原样带上；其余是它判不出来的部分：这一次审查材料的唯一一份文件索引、读法、人的原话记录与决定的对照、
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
import { headingEnd, normalizeHeading, parseDocument, storySections, ZONE_BEGIN, ZONE_END, zonesByLine }
  from '../../skills/story/scripts/core/story/document.mjs';
import { diagramsOf, diagramTopic, imagesIn, readablePaths }
  from '../../skills/story/scripts/core/story/images.mjs';
import { originRows, sourceStatus, upstreamDocs } from '../../skills/story/scripts/core/story/sources.mjs';
import { recheckItems, recheckRows } from '../../skills/story/scripts/core/story/recheck.mjs';
import { carryTargets, useEffectiveChapters } from '../../skills/story/scripts/core/story/writing-plan.mjs';
import { readingWork } from '../../skills/story/scripts/core/story/figure-view.mjs';
import { reviewObject } from '../../skills/story/scripts/core/story/review-object.mjs';
import { reportFormat } from '../../skills/story/scripts/core/story/review-report-contract.mjs';
import { knowledgeJudgmentLines } from '../../skills/story/scripts/core/story/story-inputs.mjs';

//: 本模块所在的扩展包根：判据与章节合同都属于机制，随包发布
const PACKAGE = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..');

/**
 * 会议逐话题三栏并列：会议判断、原话（按引用的行范围从 raw.md 取，同一范围只取一次）、
 * 当前结果（doc-refresh.md 里这一话题的段落）。
 * 会议结论进蓝图，未定的进 gap；`question` 只作「还没定」的标记，不另设会议裁决关卡。
 * 取不到的一栏写「未取得，未验证」，不给空对象。
 */
function meetingTopicRows(src) {
  const notes = readJsonOrNull(path.join(src, 'meeting-notes.json'));
  const meetings = Array.isArray(notes?.meetings) ? notes.meetings : null;
  if (!meetings) return ['`AR/story-src/meeting-notes.json` 读不出 `meetings` 列表——逐话题核对未取得，未验证。'];
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
      if (String(t.question ?? '').trim()) {
        out.push('- **会上提出的问题**：' + String(t.question).trim()
          + '——这是会议当时的未定；对照前面「人的原话原件」里的后续答复、当前蓝图与 Story，判它现在解决了没有：'
          + '已有有权答复解决的，核 Story 有没有按答复写；仍未解决的，核 Story 有没有保留为待定边界。');
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

/** 围栏包一段行：外层比里面最长的围栏多一个反引号。 */
function fenced(rows, lang) {
  const mark = '`'.repeat(longestFence(rows.join('\n')) + 1);
  return [`${mark}${lang}`, ...rows, mark];
}

/**
 * 上游每张图与作者选定承接它的小节并排：原图，加每一节的正文、表与图。
 * 判的是关系保没保持，不是节点同不同名；登记了却定不到、空着的位置列成缺口；没登记的图标明未指定位置，
 * 由审查者结合本需求范围判有没有相关关系漏讲。审查仍从全部原件反查，不受登记集合限制。
 */
function diagramPairRows(planCtx, plan, story) {
  const out = [];
  const targets = plan ? carryTargets(plan, story) : [];
  for (const [label, text] of upstreamDocs(planCtx)) {
    for (const d of diagramsOf(text)) {
      const tag = `${label} ${d.id}`;
      out.push('', `#### ${tag}（${diagramTopic(d)}）`, '', '上游原图：', '', ...fenced(d.lines, 'mermaid'));
      const hits = targets.filter(c => c.source === tag);
      if (!hits.length) out.push('', '作者没有指定承接位置：结合本需求范围，核这张图讲的相关业务关系在 Story 里有没有漏讲；'
        + '与本需求无关、或只供精确技术查阅的关系可以留在蓝图与来源里。');
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

/**
 * 这一次审查对象的全部材料：待审的与只读对照的分列；任务自己不列（它就是这份）。
 * 只核在场与来源摘要的行注明不必通读；同字节的别名注明与哪一份是同一内容，覆盖声明写哪个路径都算那一份。
 */
function objectRows(projectRoot, feature, contract, { rows, problems, alias }) {
  const { blocking } = sourceStatus({ contract, featureRoot: featureRoot(projectRoot, feature) });
  const line = r => `- \`${r.path}\` —— ${r.label}`
    + (r.required_read !== false ? '' : r.kind === 'metadata' ? '　（核在场与来源摘要，不必通读）' : '　（按问题回查）')
    + (alias.has(r.path) ? `　（与 \`${alias.get(r.path)}\` 同一内容）` : '');
  return ['', '### 本次审查的材料（材料键按它们的原始字节算）', '',
    '这张表绑定本轮全部固定材料（只读；你只写派审载体分配的本次报告文件）：'
    + '未标注项为本稿必读（待审 Story、有效人答原话、当轮评审输入、会议与必要承诺依据）；'
    + '标「按问题回查」的未采用库存阅读稿、蓝图/接口转写与知识原文仅保留固定版本绑定，正文存在具体疑点或实质冲突时回查，不逐份证明设计为何不用；'
    + '标「核在场」的只核在场与来源摘要。必读项读不到须在回复写明未核与影响。', '',
    '待审（结论针对它们）：', ...rows.filter(r => r.role === 'object').map(line), '',
    '只读对照（据以判断，不在这次改）：', ...rows.filter(r => r.role === 'source').map(line),
    ...problems.map(p => `- **读不到**：${p}——与它有关的判断在回复里写明未核`),
    ...blocking.map(m => `- **读不到${m.label}（${m.doc}）**——它是必备来源，材料索引里没有这一类；与它有关的判断在回复里写明未核`)];
}

/**
 * 读法：按派审载体写的情形——首次阅读先只读 Story，再核必要依据；复核按原报告与改动的实际影响核；补正只补原回复缺的部分。
 * 任务不随每一轮的原报告变化，情形与原报告路径由派审载体给出。
 */
const reading = () => ['', '### 怎么读', '',
  '派审载体写的是哪种情形，就按哪种读：',
  '- **首次阅读**（载体写「先首读」）：先只读 `AR/story.md` 写下首读结论，再按下面步骤核它与有效事实、授权和目标的一致性。',
  '- **复核**（载体写「复核」并给原报告）：通读当前 `AR/story.md`，核原报告的每条问题与本版改动实际涉及的行为和引用，'
  + '仅回查受影响的必读来源与固定原件；未经手原报告或影响扩大（新材料/全局改动）时补足必要核查。',
  '- **补正**（载体写「补正上一份回复」）：原报告判断充分则照用，只补缺的部分；看不出原审查范围时按首次阅读补足。', '',
  '1. 先读业务来源与人签：有效人答原件、当轮评审输入/改稿原件、会议原文与本稿直接涉及的必要承诺依据（含设计采用版本与冲突依据）。',
  '2. 通读待审 Story，核写作逻辑、业务可读性与对已定事实、授权和目标的忠实度；写作设计作作者安排参考。',
  '3. 标「按问题回查」的未采用库存阅读稿、蓝图与它的原生评审投影、接口转写、知识原文和工程文件，仅在正文存在疑点、缺口或明确矛盾时回查固定版本：'
  + '全面核源归蓝图独立质询，这里不例行重开已审设计取舍；偶遇设计自身与有效承诺的明确实质冲突时，回查固定版本并指出出处、影响与设计负责方。',
  '4. 文件一次读不完时分段读全；必读项读不到在回复写明未核与影响。'];

/**
 * 任务书正文：判据原文，加这一次的输入与要回答的问题。
 *
 * @param {string} projectRoot
 * @param {string} feature
 */
export function readerReviewTask(projectRoot, feature, object = null) {
  const contract = contractOf();
  const root = featureRoot(projectRoot, feature);
  const checks = readerChecks();
  // 调用方这一次已组装好的对象（不含任务）就直接用，不再组装一遍
  object ??= reviewObject(projectRoot, feature, { withTask: false });
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
    ...reading(),
    ...objectRows(projectRoot, feature, contract, object),
    ...knowledgeRows(projectRoot, object.read),
    ...(object.design ? ['', '### 设计状态（原生读取）', '',
      `蓝图${object.design.admitted ? '已准入' : '是草稿、未准入'}；原生问题 ${object.design.issues.length} 条`
        + `${object.design.issues.length ? '（下列）' : ''}。草稿可以送审，问题涉及的业务事实在人读件里是不是写成了待定或限制，按判据核。`,
      ...object.design.issues.map(i => `- ${i.code ?? i.id ?? 'issue'}${i.path ? ` @${i.path}` : ''}：${i.message ?? ''}`)] : []),
  ];
  const src = path.join(root, 'AR', 'story-src');
  // 比较依据由审查对象给一次：这里不另看流程契约的 update 状态，同一轮在收口前后取到同一份
  const comparison = object.comparison;
  if (comparison?.rid) {
    rows.push('', `### 有效变更 update ${comparison.rid}：这一版对照有效旧依据`, '',
      `\`${comparison.before}/\` 是 update ${comparison.rid} 动手前的现场。逐处核：当前稿改掉的旧约束、旧决定与旧验收，改动依据是谁给的、他有没有这个权限；`
      + '与仍有效的旧约束冲突而没经有权人裁定的，记一条阻断发现。update-notes 是作者的判断，按原件与 before 核，不当依据。');
  }

  // 人答原件是必读来源：任务只指向材料表里的原件入口（init 与 update 的完整原话都在导出里），不另拼同义投影
  const answerFiles = Array.isArray(object.answers?.files) ? object.answers.files : [];
  rows.push('', '### 人的原话原件（必读）', '',
    '材料表里标「人答原件（必读：当时的问法与原话）」的几份就是人的原话入口：材料确认与设计问答按时间记在导出原件里，'
    + 'update 同一轮的答复随同一份导出出现。逐份读完整原话，当时的问法、候选与出处都在文件内；'
    + '对话里另行答过的由本轮评审输入的原件引用原话。效力由你据来源、权限与当前蓝图判。',
    ...(answerFiles.length ? answerFiles.map(f => `- \`${f.path}\`${f.role === 'answer' ? '（可读原件）' : '（记录）'}`)
      : ['**人答原件没有导出**：读流程里记录的原话，并在回复里写明这一处未取得。']));

  // **有序阅读入口，不搬全文**：审查者分段读盘上原文，任务里给文件、内容摘要与按作者区标题排好的阅读段。
  // 摘要只算作者区（机器区整段换成区名）：投影刷新不换审查对象，作者改一个字就换。准备审查时 story 已回到
  // 正式形态（正式图块都是按源的 Mermaid），盘上读到的就是被审的那一份。
  const storyPath = path.join(root, 'AR', 'story.md');
  const story = readOrNull(storyPath) ?? '';
  rows.push('', '### 审查对象：当前 `AR/story.md`（按下面的段落顺序读盘上原文）', '',
    ...(story.trim() ? readingRows('AR/story.md', authorZone(story)) : ['`AR/story.md` 读不到或是空的：在回复里写明没有可审的 Story，结论 fail。']));
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
        + '记一条发现：没有可核的写作设计。']
      : ['（作者对本需求的阅读主线与每章骨架，是待核的作者判断，不是审查标准）', '',
        ...readingRows('AR/story-src/story-template.md', planText)]));

  // 回看清单：作者各章写完后逐条处置的同一张清单，这里核每一条的去向成不成立。
  const planCtx = { contract, projectRoot, args: { feature }, featureRoot: root, srcDir: src, storyPath,
    templatePath: path.join(src, 'story-template.md') };
  // 章节合同固定十章，逐章问题按合同顺序给
  const plan = contract ? useEffectiveChapters(planCtx) : null;
  rows.push('', '### 回看清单：作者逐条处置的对象，去向由你核', '',
    ...recheckRows(recheckItems(planCtx, plan, story)));

  // 来源集合按读者视角渲染：采用版本核对正文贡献，普通未采用新版/库存保留固定位置、按本稿疑点或冲突回查。
  rows.push('', '### 材料与来源（附录材料表对着它核）', '',
    '核采用版本的「贡献」与正文一致；普通未采用新版或库存不例行重开设计取舍，仅在正文存在具体疑点或实质冲突时回查固定版本。', '',
    ...originRows(planCtx, { audience: 'reader' }));

  // 会议逐话题把会议判断、原话、人的裁决与当前结果并排：审查要对着原话判，不只读模型写的结果。
  // 位置逐版列实际存在的那些，纠偏留痕仍回原件看。
  if (fs.existsSync(path.join(src, 'meeting-notes.json'))) {
    rows.push('', '### 会议材料：逐话题并列', '',
      '每个话题按「原话 → 判断 → 会上提出的问题 → 当前结果」核：回 `raw.md` 与 `corrections.json` 看原文，纠偏有没有改了意思、'
      + '引用的行范围指的是不是那句话；话题有没有漏，会议判断与当前结果有没有写出会上没说的；'
      + '原话里哪些是确定的，没收敛的有没有被替人定成结论；当前结果里每个确定的行为有没有依据，'
      + '仍未决的有没有作为 gap / 未决传到产物里。会上提出的问题要与前面的人答、当前蓝图和 Story 并列着判：'
      + '后续已有有权答复的，核有没有按答复落实；没有答复的，核有没有写成待定而不是默认方案。');
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
  for (const chapter of planCtx.contract?.chapters ?? []) {
    const note = chapter.reason ? `（骨架标不涉及：${chapter.reason}；核理由是否成立，不删章）` : '';
    rows.push(`- **${chapter.title}**${note}：${(chapter.questions ?? []).join('；')}`);
  }

  const dimensions = contract?.verdicts?.chapter_dimensions;
  if (Array.isArray(dimensions) && dimensions.length) {
    rows.push('', `章级维度：${dimensions.join('、')}。`);
  }

  // 图**是什么、用没用、不用的理由**是这一次的数据；「怎么判」在上面的判据原文里。
  const images = imageRows(projectRoot, feature);
  rows.push('', '### 材料里的图（这一次有哪几张）', '',
    '核正文已采用的图与图文配合是否成立；未用图保留位置，仅在本稿存在具体疑点、缺图或实质冲突时回查。', '');
  if (images.gap) {
    rows.push(`**输入有缺口**：${images.gap}。已用图核对未核：在回复里写明这处缺口与未核的范围。`);
  } else {
    rows.push(...(images.rows.length ? images.rows : ['材料清单里没有图片。']));
  }
  // 有要核的图才做视觉裁定：原生纯函数按设计采用的来源与当前蓝图算，事实写在这里，结论只认这一份
  const pictures = images.rows?.length || object.rows.some(r => r.kind === 'image');
  if (pictures) rows.push('', ...visualRows(storyReviewVisual(projectRoot, feature, object.read)));

  rows.push(...reportFormat());
  return rows.join('\n');
}

/**
 * 蓝图里的知识判断，给审查者定位用：适用与不适用的结论、理由与承担对象，与作者写附录「规约」用的是同一份。
 * 它是待核的设计判断；结合当前业务结果核影响，要核条款时回知识原文。
 */
function knowledgeRows(projectRoot, read) {
  if (read?.status !== 'ok' || !read.blueprint) return [];
  const judged = knowledgeJudgmentLines(projectRoot, read.blueprint);
  return ['', '### 蓝图里的知识判断（定位用，待核）', '',
    '下面是设计对每份知识的判断与承担对象，适用与不适用都在。核读者应取得的义务与结果在 Story 里有没有落点、不适用的理由与本需求的事实合不合；'
    + '有疑点回对应的知识原文，不逐份重审全部知识。', '',
    ...(judged.rows.length ? judged.rows : ['蓝图里还没有知识判断。']),
    ...judged.problems.map(p => `- **设计缺口**：${p}`)];
}

/** 看图能力裁定的任务行：允许图面延期、不允许延期、取不到三种照实写。 */
function visualRows(v) {
  if (v.status !== 'ok') {
    return [`**本次看图能力裁定取不到**（${(v.issues ?? []).map(i => i.message ?? i.code).join('；') || v.status}）：`
      + '看不了图就是没读完，在回复里写明未核。'];
  }
  return [`**本次看图能力**：${v.fact}。`, v.deferral
    ? '**图面核对可以按能力缺口延期**：按判据里「图面核对可以按能力缺口延期」那一款处理。'
    : v.capability.has_vision ? '能看图：图面照常核。' : '图面核对不能延期：看不了图就是没读完，在回复里写明未核。'];
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

