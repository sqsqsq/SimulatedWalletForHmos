/**
 * 章草稿 —— 路径、章头渲染与缺稿补建的唯一归属。
 *
 * 草稿是**作者区**：作者在草稿里改，`chapter --from` 消费草稿原子落盘。
 * 章头（读者要能回答的问题、别章分工、写前读什么、提交命令）与必要种子由这里渲染；
 * 形态解释不在这份文件——必要结构归 chapter-contract，写作设计选定的结构归
 * writing-plan，本模块只组合。输入是入口已解析好的数据（`facts`、写作设计 `plan`）
 * 与现有上下文字段（`ctx`），这里不读 Spec、不扫材料、不判形态。
 *
 * 不保存「已读」「已规划」之类的状态：草稿就是盘上那份文件，缺了就补，
 * 作者动过的一个字节不覆盖。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { DIAGRAM_SYNTAXES, normalizeHeading, parseChapter } from './document.mjs';
import { chapterSeedRows, missingPickedSeeds } from './chapter-contract.mjs';
import { relFromFeature } from './sources.mjs';
import { selectedStructure } from './writing-plan.mjs';

// 章草稿目录。作者在这里写，`chapter --from` 从这里读；登记之后也留着——
// 它是「这份 story 怎么写出来的」唯一的现场，不进冻结台账，也走不漏到读者手上。
const DRAFTS = 'drafts';

export function draftPath(ctx, index, title) {
  return path.join(ctx.srcDir, DRAFTS,
    `${String(index + 1).padStart(2, '0')}-${title}.md`);
}

/**
 * 宿主的命令行，取自运行环境：有 `SHELL` 的是 POSIX shell，Windows 上没有它的是 PowerShell。
 * 命令围栏按它标注，参数按它引。
 */
export const SHELL = process.env.SHELL || process.platform !== 'win32' ? 'bash' : 'powershell';

/**
 * 一个参数交给 shell 之前包起来。两种 shell 都用单引号：里面不做任何展开，`$`、反引号、
 * 双引号都是字面。参数自身的单引号，PowerShell 写两遍，POSIX shell 先闭合再转义再打开。
 * 不包不行：图名带空格是常事（`page one.png`），裸拼会被拆成两个参数，
 * 作者复制过去得到 `unrecognized arguments: one.png`。
 */
export function shellArg(value) {
  const text = String(value);
  return SHELL === 'powershell' ? `'${text.replace(/'/g, "''")}'` : `'${text.replace(/'/g, "'\\''")}'`;
}

/**
 * 合同文字折成一行行内说明：换行折为空格，`-->` 转义，
 * 不让说明逃出注释、也不让注释在渲染器里提前闭合。
 */
export const GUIDE_MARK = 'story-draft:guide';

function guideLine(text, label = '') {
  const one = String(text ?? '').replace(/\r?\n/g, ' ').replace(/-->/g, '--\\>').trim();
  return `<!-- ${GUIDE_MARK} ${label ? `${label}：` : ''}${one} -->`;
}

/**
 * 选定的图铺三行指引（图三件套）：图前讲过程、放图、图后说明分支的条件、责任与结果。参与方与消息由作者按本需求的关系画，
 * 脚本不预放；三行都是指引，提交时剥掉。
 */
const diagramHint = (at, syntax) => [
  guideLine('先把这段过程讲一遍：谁在什么条件下做什么、结果怎样', '作图'),
  guideLine(`这里放${at ? `「${at}」这一节` : '这一章'}选定的`
    + (syntax ? `${DIAGRAM_SYNTAXES[syntax].name}——mermaid 围栏首个声明写 ${DIAGRAM_SYNTAXES[syntax].heads[0]}`
      : '图——用画图语言的围栏') + '；承接上游的图，围栏第一行写图源标记', '作图'),
  guideLine('说明各分支成立的条件、由谁处理及处理结果；单一路径用一句话说明后续去向', '作图'),
];

/**
 * 选定的表与列表：只说这里要完成什么，不预生成表头或项目。
 *
 * 形式是设计表达那一步定的，内容是现在这一步的事：先读本节的依据与要解释的关系，
 * 再决定列、行与项目。给不出有依据的内容时，改设计比硬填一张空表好——
 * 所以这一行同时说出另一个出口。
 */
const formHint = (at, form) => guideLine(`${at ? `「${at}」这一节` : '这一章'}要`
  + (form.kind === 'table' ? '一张表：按本节依据与原文决定列和行，不照搬别处的列'
    : `${form.ordered ? '一个有序列表（有先后）' : '一个无序列表'}：按依据写出各项，没有依据的不凑`)
  + '。写作设计里选的形式在这里承载不了要解释的关系时，有依据地改设计并记下原因', '完成表达');

/**
 * 一章的草稿：章头（读者要能回答的问题、别章分工、写前读什么、提交命令）+ 必要种子。
 *
 * 作者拿到的不该是一张白纸：本章要回答什么、写前对照什么、写完怎么提交，
 * 都在他动笔前进草稿；必要种子（术语起始行、必要与选定的表头、附录投影入口）
 * 是确定性工作，脚本做完。整篇设计不复制进草稿——章头只指向写作设计里本章那一段。
 *
 * @param {object} ch 合同章（可已并入写作设计选定的结构）
 */
function chapterDraft(ctx, ch, facts) {
  const index = ctx.contract.chapters.findIndex(c => c.id === ch.id);
  const file = draftPath(ctx, index, ch.title);
  const plan = relFromFeature(ctx, ctx.templatePath);
  return [
    guideLine(`读完这一章，读者要能回答：${(ch.questions ?? []).join('；')}（直接回答，不写本章讲什么）`),
    guideLine(`别的章负责：${ch.boundary}；这里不重复`),
    guideLine('这一步是完成表达：照骨架逐节写——先读这一节要解释什么、依据在哪，再决定列、节点与项目，'
      + '写成正文。写本章前先读已写章与本章共用的关系，再对照本章要用的原文；'
      + `设计要改回写作设计 ${plan}，并在 story-src/template-adjustments.md 记下实质调整的原因`),
    guideLine(`node ${shellArg(ctx.scriptPath)} chapter`
      + ` --feature ${shellArg(ctx.args.feature)}`
      + ` --chapter ${shellArg(ch.title)}`
      + ` --from ${shellArg(file)}`
      + ` --project-root ${shellArg(ctx.projectRoot)}`, '提交'),
    '',
    `## ${ch.title}`,
    '',
    ...chapterSeedRows(ch, facts, { diagramHint, formHint, guide: (note) => guideLine(note, '骨架') }),
  ];
}

const draftText = (ctx, ch, facts) => `${chapterDraft(ctx, ch, facts).join('\n').trimEnd()}\n`;

/**
 * 缺哪章补哪章，**作者动过的绝不覆盖** —— 草稿里可能有他还没落盘的内容。
 *
 * 缺席的草稿按这一章写没写分两种补法：
 *
 * - **还带着待写标记**：补一份起点草稿（章头、必要种子与写作设计选定的结构在里面）；
 * - **已经写完**：补一份**现稿正文**。用起点会把成品换掉；用现稿则是恒等——
 *   不落盘什么也不变，落盘也只是把原文写回去。章在 Story 里缺失时不凭空
 *   重建该章，交原有的结构检查报告。
 *
 * 写作设计给这一章选了结构时，**写没写过**与**能不能覆盖**分开看：只有还没写、且内容
 * （行尾归一后）仍是不带选定结构的那份起点的草稿，才换成带选定结构的起点；写过的、
 * 作者动过的、按现稿补回的，一个字节不改，但照样按当前设计找出缺哪些选定结构，
 * 作为起点交给入口打印，由作者按需贴。已经有的结构不重复给。
 *
 * 补回来的只有成稿正文，拿不回作者写到一半的思路——所以这是兜底，不是常态：
 * 常态下草稿一直在，成文登记也不删它。
 *
 * @param {object} ctx 现有上下文
 * @param {object} facts 入口解析好的当前输入
 * @param {object} chapterState 入口的 Story 解析结果：
 *   `{written: Map<规范章名, 正文>, pending: Set<规范章名>, hasStory: boolean}`；
 *   没有 Story 时两者均空且 hasStory 为 false。
 * @param {object} plan `writing-plan.readWritingPlan` 的结果
 * @returns {{made: string[], seeded: string[], starts: {file: string, rows: string[]}[]}}
 *   新建的草稿、换成带选定结构起点的草稿、动过的草稿还缺的选定结构起点
 */
export function writeDrafts(ctx, facts, chapterState, plan) {
  const made = [], seeded = [], starts = [];
  const written = chapterState?.written ?? new Map();
  const pending = chapterState?.pending ?? new Set();
  fs.mkdirSync(path.join(ctx.srcDir, DRAFTS), { recursive: true });
  // 设计还读不了（空壳、形状不对、缺口）就不按它铺：铺进去的占位或半截骨架会让草稿看起来被动过，
  // 设计写好之后反而换不成骨架起点。
  const usable = Boolean(plan) && !plan.problems.length;
  ctx.contract.chapters.forEach((ch, i) => {
    const file = draftPath(ctx, i, ch.title);
    const key = normalizeHeading(ch.title);
    const done = chapterState?.hasStory && !pending.has(key);
    const planned = usable ? { ...ch, structure: selectedStructure(plan, ch.id) } : ch;
    const picked = usable && plan.skeletons.has(ch.id);
    if (!fs.existsSync(file)) {
      const body = done ? written.get(key) : null;
      if (done && body === undefined) return;       // 章缺失由结构检查报，这里不猜
      fs.writeFileSync(file, done ? `${body.trimEnd()}\n` : draftText(ctx, planned, facts), 'utf-8');
      made.push(path.basename(file));
      if (!done) return;                            // 新起点已带选定结构
    } else if (picked && !done) {
      const now = fs.readFileSync(file, 'utf-8').replace(/\r\n/g, '\n');
      if (now === draftText(ctx, ch, facts)) {
        fs.writeFileSync(file, draftText(ctx, planned, facts), 'utf-8');
        seeded.push(path.basename(file));
        return;
      }
    }
    if (!picked) return;
    const rows = missingPickedSeeds(planned, parseChapter(fs.readFileSync(file, 'utf-8')),
      { diagramHint, formHint });
    if (rows.length) starts.push({ file, rows });
  });
  return { made, seeded, starts };
}
