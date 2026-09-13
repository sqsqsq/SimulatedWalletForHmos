/**
 * 图片的身份与去处 —— 引到的每一张是不是材料里登记过的那一张，登记的每一张有没有去处。
 *
 * 按**内容**认图不按文件名认：只比文件名时，同名复制进一个新目录的拦不住，
 * 而那正是「全树五份同一张图」的来路。
 */
import * as path from 'node:path';
import {
  joinPosix, readManifest, relFromFeature, relFromStory, upstreamDocs,
} from './sources.mjs';
import { appendixChapter } from './appendix.mjs';
import { normalizeHeading } from './document.mjs';


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
  const lines = String(text ?? '').split(/\r?\n/);
  const seq = new Map();
  const out = [];
  let section = '';
  let title = '';
  for (let i = 0; i < lines.length; i += 1) {
    const h = lines[i].trim().match(/^#{2,4}\s+(.+?)\s*$/);
    if (h) {
      title = h[1].trim();
      const num = title.match(/^(\d+(?:[.．]\d+)*)[.．]?\s*/);
      section = num ? num[1].replace(/．/g, '.') : normalizeHeading(title);
      continue;
    }
    if (!/^[ \t]*```[ \t]*mermaid\b/.test(lines[i])) continue;
    const body = [];
    let j = i + 1;
    for (; j < lines.length && !/^[ \t]*```/.test(lines[j]); j += 1) body.push(lines[j]);
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
      at: { from: i + 1, to: Math.min(j, lines.length - 1) + 1 },
      //: 按**行**给，不拼成字符串——拼了下游就要再切一遍，而切法一旦与这里不同，
      //: CRLF 的文件每行尾会挂个 `\r`，行尾判据从此静默零命中。
      lines: lines.slice(i + 1, j),
    });
    i = j;
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
export function diagramsNotCarried(upstreamText, upstreamLabel, downstreamText) {
  const carried = new Set(diagramsOf(downstreamText).flatMap(d => d.sources));
  return diagramsOf(upstreamText).filter(d => !carried.has(`${upstreamLabel} ${d.id}`));
}

/**
 * 图有没有被正文接住 —— 两件机械可见的事，不判「这句话说的是不是这张图」。
 *
 * 引一张图的正常写法是：先一句话说它画的是什么，再是图，图后接着讲。
 * 两种形态不用读懂任何一句话就能看出不对：
 *
 * - **图连图**：两张图挨在一起，中间没有一句话。读者不知道该看哪张、看什么。
 * - **图前没有承接句**：上一非空行是标题、是另一张图，或者图就在节首。
 *   那说明这张图是被贴进来的，不是被讲到的——「按清单把图都引上」正是这个形态。
 *
 * 附录不看：图本来就不该在那里，由「附录里不放图」那条判。
 */
export function danglingFigures(storyText, contract) {
  const appendix = appendixChapter(contract);
  const out = [];
  const lines = String(storyText ?? '').split(/\r?\n/);
  const isImage = (l) => /^\s*!\[[^\]]*\]\(/.test(l);
  let inAppendix = false;
  let prev = null;                                   // 上一非空行
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const h = line.trim().match(/^##\s+(.+?)\s*$/);
    if (h) {
      inAppendix = appendix ? normalizeHeading(h[1]) === normalizeHeading(appendix.title) : false;
      prev = line;
      continue;
    }
    if (!line.trim()) continue;
    if (isImage(line) && !inAppendix) {
      const why = prev === null || /^#{1,6}\s/.test(prev.trim()) ? '它就在小节开头'
        : isImage(prev) ? '它紧挨着上一张图'
          : null;
      if (why) {
        out.push(`第 ${i + 1} 行的图前面没有一句话（${why}）`
          + '——引一张图先说它画的是什么，再是图，图后接着讲。'
          + '接不上一句话的图，说明它是被贴进来的，不是被讲到的：'
          + '本需求用不上就别引，跑 `import_sources.py --feature <名> '
          + '--caption-image <这张图> --unused "<为什么不用它>"` 登记它的去向');
      }
    }
    prev = line;
  }
  return out;
}

/** 图片身份：引到的每一张是不是材料里登记过的那一张，登记的每一张有没有去处。 */
export function imageProblems(ctx, storyText) {
  const problems = [];
  const notes = [];
  // ④ 图片身份：story 引了哪些图、每一张是不是材料清单里登记过的那一张。
  //
  // 这两条是确定性的链接与图片检查，单独成块：判的是「引用可不可解析、
  // 在不在登记里」，与作者画了几张无关，所以不跟形态守恒放一起。
  const imgs = [...storyText.matchAll(/!\[([^\]]*)\]\(([^)\s]+)/g)];
  const seen = new Set();
  for (const [, alt, src] of imgs) {
    if (!alt.trim()) problems.push(`图片 ${src} 没有 alt 文本`);
    if (seen.has(src)) problems.push(`图片 ${src} 在 story 里出现了不止一次`);
    seen.add(src);
  }

  {
    // 图片身份：引到的每一张都要是材料里**登记过**的那一张。
    //
    // 判据只有这一条：路径在登记的落点集合里。**没有「归档副本区按字节认」这条特权**——
    // 它从前允许 `AR/assets/` 下未登记的文件靠字节相同混过去，而那正是「自建一个图片目录、
    // 全树五份同一张图」的入口：登记里没有它，谁也说不出它是哪一轮、哪一份材料来的。
    // 已经登记进材料的 assets 路径照样合法（它在登记集合里）。
    const registered = materialImages(ctx);
    if (registered === 'broken') {
      problems.push('AR/story-src/materials.json 读不出材料清单——图片引用无从核对身份。'
        + '它只应由脚本写入，若曾手工编辑，删掉后重跑 `story_flow.py round`');
    } else if (!registered) {
      notes.push('没有材料清单（AR/story-src/materials.json），图片身份与落点判据未执行'
        + '——跑 `story_flow.py round` 生成它之后这条才判得了');
    } else if (registered.length) {
      const storyDir = path.dirname(relFromFeature(ctx, ctx.storyPath));
      const byPath = new Map();
      registered.forEach((m, i) => m.paths.forEach(rel => byPath.set(rel, i)));
      const usedBy = new Map();            // 登记序号 → story 里引到它的那些路径
      for (const src of seen) {
        if (/^(https?:|data:)/i.test(src)) continue;
        const rel = joinPosix(storyDir, src);
        const idx = byPath.has(rel) ? byPath.get(rel) : -1;
        if (idx < 0) {
          problems.push(`story 引用的图片「${src}」不在材料的图片登记里`
            + '——引它在仓里的既有落盘位置，不要复制一份到别处再改名；'
            + '副本没人维护，改了名读者也认不出它就是原来那张');
          continue;
        }
        if (!usedBy.has(idx)) usedBy.set(idx, []);
        usedBy.get(idx).push(src);
      }
      for (const [idx, srcs] of usedBy) {
        if (srcs.length < 2) continue;
        problems.push(`同一张图被两个路径引用：${srcs.join('、')}`
          + `（材料里登记为 ${registered[idx].paths.join('、')}）`
          + '——同一张图只引一次，一处说清它画的是什么');
      }

      // 每张图都有去处：要么正文引了，要么在材料清单里登记了为什么不用。
      //
      // 判的是**去处**不是义务：图可以不用——参考稿废弃了、那是友商的、
      // 那是别的单据的页面，都是正当理由。不正当的是它在材料里而去向没人说过，
      // 读者无从知道你看没看过它。理由成不成立由读者审查判，这里只报缺口。
      const mark = rel => '`import_sources.py --feature <名> --caption-image ' + rel;
      for (const [i, m] of registered.map((m2, i2) => [i2, m2])) {
        const declined = String(m.unused ?? '').trim();
        if (usedBy.has(i) && declined) {
          problems.push(`「${m.paths[0]}」登记着不用的理由（${declined}），正文却引了它——`
            + '二者取其一：属于本需求就 ' + mark(m.paths[0]) + ' --used` 清掉理由，'
            + '不属于本需求就把正文里那处删掉');
        } else if (!usedBy.has(i) && !declined) {
          problems.push(`材料里登记的图「${m.paths[0]}」${m.caption ? `（${m.caption}）` : ''}`
            + '在 story 里没被引用，也没登记为什么不用——'
            + '属于本需求就在讲它的那一章引用（图前一句说清它画的是什么），'
            + '不属于本需求就跑 ' + mark(m.paths[0]) + ' --unused "<为什么不用它>"`；'
            + '归档件不为一张不用的图留正文');
        }
      }
    }
  }
  return { problems, notes };
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
  for (const [label, upstream] of upstreamDocs(ctx)) {
    for (const d of diagramsNotCarried(upstream, label, storyText)) {
      problems.push(`${label} ${d.id} 的图（${diagramTopic(d)}）在 story 里没有。`
        + '先看它讲的那件事在 story 哪一章：讲了而图漏了，把图搬到那一节；'
        + '没讲，是内容丢了，先补内容再搬图。'
        + `搬的时候围栏第一行写 \`%% 图源 ${label} ${d.id}\`——周围的文字自己写，`
        + 'story 讲给评审者的是来龙去脉，上游那份讲的是别的事');
    }
  }
  return problems;
}


function materialImages(ctx) {
  const data = readManifest(ctx);
  if (data === null || data === 'broken') return data;
  if (!Array.isArray(data.materials)) return 'broken';
  return data.materials.filter(m => m?.kind === 'image'
    && Array.isArray(m.paths) && m.paths.length);
}
