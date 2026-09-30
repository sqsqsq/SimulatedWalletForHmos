/**
 * 图片的身份与去处 —— 引到的每一张是不是材料里登记过的那一张，登记的每一张有没有去处。
 *
 * 按**内容**认图不按文件名认：只比文件名时，同名复制进一个新目录的拦不住。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { joinPosix, readManifest, relFromFeature, upstreamDocs } from './sources.mjs';
import { normalizeHeading, parseDocument } from './document.mjs';


/**
 * 一份文档里的每张图 —— 身份由**位置**给，来源由**围栏第一行**自报。
 *
 * 身份 `§<节> #<该节内第几张>`：图不需要作者起名，位置就是它的名字。
 * 来源标记 `%% 图源 <文档> §<节> #<序>` 指向**直接上游**那一张；只有围栏第一行算标记，
 * 所以一张图从 SR 经 spec 到 story，每一环换一次标记，上一环的那行随围栏带过去也无妨。
 *
 * 节取标题的前导编号（`### 5.2 异常回收` → `5.2`）；没有编号就用业务名——
 * 编号是给人对位用的，取不到时身份仍要唯一。
 */
export function diagramsOf(text) {
  const doc = parseDocument(text);
  const seq = new Map();
  const out = [];
  for (const fence of doc.fences.filter(f => f.lang === 'mermaid')) {
    const heading = doc.headings.filter(h => h.level >= 2 && h.level <= 4 && h.at < fence.from).pop();
    const title = heading?.raw ?? '';
    const num = title.match(/^(\d+(?:[.．]\d+)*)[.．]?\s*/);
    const section = num ? num[1].replace(/．/g, '.') : normalizeHeading(title);
    const body = doc.lines.slice(fence.from + 1, fence.closed ? fence.to : fence.to + 1);
    const index = (seq.get(section) ?? 0) + 1;
    seq.set(section, index);
    // 围栏开头**连续的**几行 `%% 图源` 都算标记：同一张图常常两份上游都画过
    // （系统设计画一遍，spec 的业务流程图就是它），story 里只该有一张——
    // 两行标记写在同一个围栏里，两处的登记各自成立。只认开头那几行：
    // 图正文里再出现的 `%%` 是注释，不是登记。
    const marks = [];
    for (const line of body) {
      const m = line.trim().match(/^%%\s*图源\s+(.+?)\s*$/);
      if (!m) break;
      marks.push(m[1]);
    }
    out.push({
      section, index, title,
      id: `§${section} #${index}`,
      sources: marks,
      //: 围栏在原件里的行范围（**1 起，含首尾标记行**）——作者据它去读原件，
      //: 而不是读一份被复制进任务包的副本：副本一旦与原件不同步，他改的是副本。
      at: { from: fence.from + 1, to: fence.to + 1 },
      //: 按**行**给，不拼成字符串——拼了下游就要再切一遍，而切法一旦与这里不同，
      //: CRLF 的文件每行尾会挂个 `\r`，行尾判据从此静默零命中。
      lines: body,
    });
  }
  return out;
}

/** 这张图讲的是什么 —— 小节标题 + 首层节点，给的是**主题**，不是「少了一张图」。 */
export function diagramTopic(d) {
  const nodes = [...d.lines.join('\n').matchAll(/[[({]([^\])}|]{1,20})[\])}]/g)]
    .map(m => m[1].trim()).filter(Boolean);
  const uniq = [...new Set(nodes)].slice(0, 4);
  return uniq.length ? `${d.title}：${uniq.join(' → ')}` : d.title;
}

/**
 * 上游每张图，下游有没有一个围栏带着它的来源标记。
 *
 * 只核登记对应：图搬没搬对、周围文字写没写好由语义审查判。
 * 缺了指向的是**功能**不是图——图漏了先找它讲的那件事在下游哪里。
 */
function diagramsNotCarried(upstreamText, upstreamLabel, downstreamText) {
  const carried = new Set(diagramsOf(downstreamText).flatMap(d => d.sources));
  return diagramsOf(upstreamText).filter(d => !carried.has(`${upstreamLabel} ${d.id}`));
}

/** 围栏外的图源标记行（1 起）：标记只在图的围栏第一行算数。 */
export function strayMarks(text) {
  const doc = parseDocument(text);
  return doc.lines.flatMap((line, i) => (!doc.fenced.has(i) && /^\s*%%\s*图源/.test(line) ? [i + 1] : []));
}

/**
 * 本章的图源标记指得到吗 —— 指向的图在直接上游里存在、不是指向 story 自己，且写在围栏第一行。
 *
 * 只看本章就判得了，所以在提交本章时判（章提交与整篇检查的 ⑪ 共用）。
 * 只核引用本身：图是不是承接了那张图的关系，要读内容，归读者审查的图文一致判据。
 *
 * @param {string} text 本章正文，第一行是本章标题（图的节号按标题认）
 * @param {(line:number) => string} where 正文行号（1 起，含标题行）→ 作者要改的位置
 */
export function chapterSourceMarkProblems(ctx, text, where) {
  const problems = [];
  const known = new Set();
  const labels = new Set();
  for (const [label, upstream] of upstreamDocs(ctx)) {
    labels.add(label);
    for (const d of diagramsOf(upstream)) known.add(`${label} ${d.id}`);
  }
  for (const d of diagramsOf(text)) {
    for (const mark of d.sources) {
      if (known.has(mark)) continue;
      const label = mark.split(/\s+/)[0];
      problems.push(`${where(d.at.from)}：图源标记「${mark}」` + (labels.has(label)
        ? `指向的图在 ${label} 里没有——标记按上游文档的节号与该节内第几张认，${label} 现有的图见 skeleton 输出`
        : `指向的不是直接上游（上游是 ${[...labels].join('、') || '无'}）——标记登记的是 story 这张图承接了上游哪一张`));
    }
  }
  for (const line of strayMarks(text)) {
    problems.push(`${where(line)}：图源标记写在了围栏外——只有图的围栏里开头那几行 \`%% 图源\` 算登记`);
  }
  return problems;
}

/**
 * 本章引的每一张图：有 alt、是材料里登记过的那一张、没有同时登记成不用。
 *
 * 只看本章就判得了，在提交本章时判；全篇才判得了的（同一张图引了两次、两个路径指同一张、
 * 登记的图全篇都没去处）留在整篇检查的 `imageProblems`。材料清单读不出时这里不判，缺口由整篇检查报。
 *
 * @param {string} text 本章正文（行号与 `where` 同一口径）
 */
export function chapterImageProblems(ctx, text, where) {
  const problems = [];
  const registered = materialImages(ctx);
  // 登记为零张时不核身份（与整篇检查同一口径：没有登记集合可比）
  const usable = Array.isArray(registered) && registered.length ? registered : null;
  const storyDir = usable ? path.dirname(relFromFeature(ctx, ctx.storyPath)) : '';
  const byPath = new Map();
  (usable ?? []).forEach((m, i) => m.paths.forEach(rel => byPath.set(rel, i)));
  String(text ?? '').split(/\r?\n/).forEach((line, i) => {
    for (const [, alt, src] of line.matchAll(/!\[([^\]]*)\]\(([^)\s]+)/g)) {
      if (!alt.trim()) problems.push(`${where(i + 1)}：图片 ${src} 没有 alt 文本——alt 是评审人看不到图时读到的那句话`);
      if (!usable || /^(https?:|data:)/i.test(src)) continue;
      const idx = byPath.get(joinPosix(storyDir, src));
      if (idx === undefined) {
        const name = path.posix.basename(src);
        const same = [...byPath.keys()].filter(rel => path.posix.basename(rel) === name)
          .map(rel => path.posix.relative(storyDir, rel));
        problems.push(`${where(i + 1)}：图片「${src}」不在材料的图片登记里——story 里的图按登记的引用认`
          + `（相对 ${storyDir}/ 解析）${same.length ? `，同名的登记引用是 \`${same.join('`、`')}\`` : ''}`
          + '；副本与改名后的文件没有登记，说不出是哪一轮、哪一份材料');
        continue;
      }
      const declined = String(usable[idx].unused ?? '').trim();
      if (declined) {
        problems.push(`${where(i + 1)}：图片「${src}」在材料里登记着不用的理由（${declined}）——`
          + '登记的去向与正文的引用说的是两件事，图的去向以材料清单里的登记为准'
          + '（登记由 `import_sources.py --caption-image <路径> --used / --unused` 写入）');
      }
    }
  });
  return problems;
}

/**
 * 图片身份里要读全篇才判得了的那几条：同一张图引了不止一次、两个路径指同一张、
 * 登记的每一张在全篇有没有去处。本章能判的（alt、在不在登记、登记成不用却引了）在提交本章时判。
 */
export function imageProblems(ctx, storyText) {
  const problems = [];
  const notes = [];
  const imgs = [...storyText.matchAll(/!\[([^\]]*)\]\(([^)\s]+)/g)];
  const seen = new Set();
  for (const [, , src] of imgs) {
    if (seen.has(src)) problems.push(`story.md：图片 ${src} 被引用了不止一次——同一张图只在一处引，那一处说清它画的是什么`);
    seen.add(src);
  }
  const registered = materialImages(ctx);
  if (registered?.gap) {
    problems.push(`${registered.gap}；图片引用无从核对身份`);
    return { problems, notes };
  }
  if (!registered) {
    notes.push('AR/story-src/materials.json：不在，图片身份与落点判据未执行'
      + '——这份清单由 `story_flow.py round` 生成');
    return { problems, notes };
  }
  const storyDir = path.dirname(relFromFeature(ctx, ctx.storyPath));
  const byPath = new Map();
  registered.forEach((m, i) => m.paths.forEach(rel => byPath.set(rel, i)));
  const usedBy = new Map();            // 登记序号 → story 里引到它的那些路径
  for (const src of seen) {
    if (/^(https?:|data:)/i.test(src)) continue;
    const idx = byPath.get(joinPosix(storyDir, src));
    if (idx === undefined) continue;   // 不在登记里的由本章判据报
    if (!usedBy.has(idx)) usedBy.set(idx, []);
    usedBy.get(idx).push(src);
  }
  for (const [idx, srcs] of usedBy) {
    if (srcs.length < 2) continue;
    problems.push(`story.md：同一张图被两个路径引用：${srcs.join('、')}`
      + `（材料里登记为 ${registered[idx].paths.join('、')}）——图按材料登记的内容认，同一张图只在一处引`);
  }
  // 每张图都有去处：要么正文引了，要么在材料清单里登记了为什么不用。判的是**去处**不是义务：
  // 图可以不用；不正当的是它在材料里而去向没人说过。理由成不成立由读者审查判，这里只报缺口。
  for (const [i, m] of registered.map((m2, i2) => [i2, m2])) {
    if (usedBy.has(i) || String(m.unused ?? '').trim()) continue;
    problems.push(`AR/story-src/materials.json 登记的图「${m.paths[0]}」${m.caption ? `（${m.caption}）` : ''}`
      + '：在 story 里没被引用，也没登记为什么不用——每张登记的图按有没有去处判：'
      + '讲它的那一章有引用，或材料清单里有不用的理由'
      + '（登记由 `import_sources.py --feature <名> --caption-image '
      + path.relative(ctx.projectRoot, path.join(ctx.featureRoot, m.paths[0])).split(path.sep).join('/')
      + ' --unused "<理由>"` 写入，图的路径相对工程根）');
  }
  return { problems, notes };
}

/**
 * 材料清单里的图片对象 —— **一份形状判定，三个消费者**（全篇 check、作者包、审查任务）。
 *
 * 「没有图」只有一种：`materials` 是数组而里面没有图片记录。别的都是**缺口**：
 * 清单不在、读不出、`materials` 不是数组、图片记录的 `paths` 不是非空字符串数组。
 * 当成零图放过的话，作者会以为这一轮不涉及图、审查会写「本项不适用」，而实际是清单坏了。
 *
 * @param {object|null} manifest 已读出的清单对象；null = 读不出或不在
 * @returns {{images: object[], gap: string|null}}
 */
export function imagesIn(manifest) {
  const fix = '——这份清单由 `story_flow.py round` 按磁盘现状生成';
  if (manifest === null || typeof manifest !== 'object') {
    return { images: [], gap: `AR/story-src/materials.json：读不出材料清单${fix}` };
  }
  if (!Array.isArray(manifest.materials)) {
    return { images: [],
      gap: `AR/story-src/materials.json：没有 \`materials\` 数组${fix}` };
  }
  const images = manifest.materials.filter(m => String(m?.kind ?? '').includes('image'));
  const bad = images.filter(m => !Array.isArray(m.paths) || !m.paths.length
    || m.paths.some(rel => typeof rel !== 'string' || !rel.trim()));
  if (bad.length) {
    return { images: [],
      gap: `AR/story-src/materials.json：有 ${bad.length} 条图片记录的 \`paths\` 形状不对`
        + `（要一个非空的字符串数组）${fix}` };
  }
  return { images, gap: null };
}

/**
 * 这几个落点里**真读得到**的那些 —— 目录、坏链接、读不了的文件都不算。
 *
 * `existsSync` 为真不等于它能当一张图：指到目录时渲染出来的引用串与命令都是坏的，
 * 而作者照着跑只会拿到一个费解的错误。
 */
export function readablePaths(featureRoot, paths) {
  return (Array.isArray(paths) ? paths : []).filter((rel) => {
    if (typeof rel !== 'string' || !rel.trim()) return false;
    const abs = path.join(featureRoot, ...rel.split('/'));
    try {
      if (!fs.statSync(abs).isFile()) return false;
      fs.accessSync(abs, fs.constants.R_OK);
      return true;
    } catch (err) {
      // **只吞文件系统的错**：不在、不可读、是目录都当读不到。别的（比如漏了一个
      // import）是这份代码自己的错，吞掉它会让「所有图都读不到」看起来像数据问题。
      if (err?.code) return false;
      throw err;
    }
  });
}

/** 上游每张图，story 里各有一个围栏带着它的来源标记。 */
export function carriedDiagramProblems(ctx, storyText) {
  const problems = [];
  // 上游每张图，story 里各有一个围栏带着它的来源标记。
  //
  // story 的上游有两份：系统设计（SR）与 spec。图属于哪块内容，内容在 story 落在哪，
  // 图就该在哪——不是「上游有几张图，story 就派生几节」。所以这里不判位置、不判张数，
  // **只判登记对应**：标记在，说明这张图被登记着搬过来了；它搬得对不对、
  // 周围那句话说的是不是它，要读上下文，归独立审查。
  // 缺了报的是**这张图讲的那件事**，作者据此去找内容，而不是去补一张图。
  // 一张图一行：来源位置、它讲的那件事、去向。怎么搬（围栏第一行写 `%% 图源 <来源> <编号>`、
  // 周围文字自己写）是整类共同的写法，不逐张重复。
  for (const [label, upstream] of upstreamDocs(ctx)) {
    for (const d of diagramsNotCarried(upstream, label, storyText)) {
      problems.push(`${label} ${d.id}（${diagramTopic(d)}）在 story 里没有——没有围栏带着它的图源标记；`
        + '上游每张图按 story 围栏开头的 `%% 图源 ' + `${label} ${d.id}` + '` 认承接；这张图讲的那件事落在 story 哪一章，图就在那一章');
    }
  }
  return problems;
}


function materialImages(ctx) {
  const data = readManifest(ctx);
  if (data === null) return null;                 // 没有清单：由调用方记一笔
  const { images, gap } = imagesIn(data === 'broken' ? null : data);
  return gap ? { gap } : images;
}
