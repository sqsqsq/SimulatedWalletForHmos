/**
 * 章草稿 —— 路径、章头渲染与缺稿补建的唯一归属。
 *
 * 草稿是**作者区**：作者在草稿里改，`chapter --from` 消费草稿原子落盘。
 * 章头（读者问题、主要职责、提交命令）与必要种子由这里渲染；形态解释不在这份
 * 文件——必要结构归 chapter-contract，本模块只组合。输入是入口已解析好的数据
 * （`facts`）与现有上下文字段（`ctx`），这里不读 Spec、不扫材料、不判形态。
 *
 * 不保存「已读」「已规划」之类的状态：草稿就是盘上那份文件，缺了就补，
 * 已有的一个字节不覆盖。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { normalizeHeading } from './document.mjs';
import { chapterSeedRows } from './chapter-contract.mjs';

// 章草稿目录。作者在这里写，`chapter --from` 从这里读；登记之后也留着——
// 它是「这份 story 怎么写出来的」唯一的现场，不进冻结台账，也走不漏到读者手上。
const DRAFTS = 'drafts';

export function draftPath(ctx, index, title) {
  return path.join(ctx.srcDir, DRAFTS,
    `${String(index + 1).padStart(2, '0')}-${title}.md`);
}

/**
 * 一个参数交给 shell 之前包起来 —— **本工程的命令行是 PowerShell**。
 *
 * 单引号里 PowerShell 不做任何展开：`$`、反引号、双引号都是字面；参数自身的单引号
 * 写两遍就是一个字面单引号。双引号不行——`$name` 与反引号会在双引号里被展开，
 * 而反斜杠在 PowerShell 里根本不是转义符，靠它去转义只会把反斜杠本身留在参数里。
 * 不包也不行：图名带空格是常事（`page one.png`），裸拼会被拆成两个参数，
 * 作者复制过去得到 `unrecognized arguments: one.png`。
 */
export function shellArg(value) {
  return `'${String(value).replace(/'/g, "''")}'`;
}

/**
 * 合同文字折成一行行内说明：换行折为空格，`-->` 转义，
 * 不让说明逃出注释、也不让注释在渲染器里提前闭合。
 */
function guideLine(text, label = '') {
  const one = String(text ?? '').replace(/\r?\n/g, ' ').replace(/-->/g, '--\\>').trim();
  return `<!-- story-draft:guide ${label ? `${label}：` : ''}${one} -->`;
}

/**
 * 一章的草稿：章头（读者问题、主要职责、提交命令）+ 必要种子。
 *
 * 作者拿到的不该是一张白纸：本章要回答什么、写前对照什么、写完怎么提交，
 * 都在他动笔前进草稿；必要种子（术语起始行、验收/交付表头、附录投影入口）
 * 是确定性工作，脚本做完。他填的是语义——正文怎么组织、每一格写什么。
 */
function chapterDraft(ctx, ch, facts) {
  const index = ctx.contract.chapters.indexOf(ch);
  const file = draftPath(ctx, index, ch.title);
  const rows = [
    guideLine((ch.questions ?? []).join('；'), '读者问题'),
    guideLine(ch.boundary, '主要职责'),
    guideLine('写前对照当前 Story 已写内容，本章补独有信息；'
      + '形式方法见 story-write.md「十章各自怎么组织」'),
    guideLine(`node ${shellArg(ctx.scriptPath)} chapter`
      + ` --feature ${shellArg(ctx.args.feature)}`
      + ` --chapter ${shellArg(ch.title)}`
      + ` --from ${shellArg(file)}`
      + ` --project-root ${shellArg(ctx.projectRoot)}`, '提交'),
    '',
    `## ${ch.title}`,
    '',
    ...chapterSeedRows(ch, facts),
  ];
  return rows;
}

/**
 * 缺哪章补哪章，**已存在的绝不覆盖** —— 草稿里可能有作者还没落盘的内容。
 *
 * 两种补法，按这一章写没写分：
 *
 * - **还带着待写标记**：补一份起点草稿（章头与必要种子在里面）；
 * - **已经写完**：补一份**现稿正文**。用起点会把成品换掉；用现稿则是恒等——
 *   不落盘什么也不变，落盘也只是把原文写回去。章在 Story 里缺失时不凭空
 *   重建该章，交原有的结构检查报告。
 *
 * 补回来的只有成稿正文，拿不回作者写到一半的思路——所以这是兜底，不是常态：
 * 常态下草稿一直在，成文登记也不删它。
 *
 * @param {object} ctx 现有上下文
 * @param {object} facts 入口解析好的当前输入
 * @param {object} chapterState 入口的 Story 解析结果：
 *   `{written: Map<规范章名, 正文>, pending: Set<规范章名>, hasStory: boolean}`；
 *   没有 Story 时两者均空且 hasStory 为 false。
 * @returns {string[]} 这次新建的草稿文件名
 */
export function writeDrafts(ctx, facts, chapterState) {
  const made = [];
  const written = chapterState?.written ?? new Map();
  const pending = chapterState?.pending ?? new Set();
  fs.mkdirSync(path.join(ctx.srcDir, DRAFTS), { recursive: true });
  ctx.contract.chapters.forEach((ch, i) => {
    const file = draftPath(ctx, i, ch.title);
    if (fs.existsSync(file)) return;
    const key = normalizeHeading(ch.title);
    const done = chapterState?.hasStory && !pending.has(key);
    const body = done ? written.get(key) : null;
    if (done && body === undefined) return;         // 章缺失由结构检查报，这里不猜
    const text = done ? body : chapterDraft(ctx, ch, facts).join('\n');
    fs.writeFileSync(file, `${text.trimEnd()}\n`, 'utf-8');
    made.push(path.basename(file));
  });
  return made;
}
