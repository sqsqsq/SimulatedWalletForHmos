/**
 * 图片的身份与去处 —— 引到的每一张是不是材料里登记过的那一张，登记的每一张有没有去处。
 *
 * 按**内容**认图不按文件名认：只比文件名时，同名复制进一个新目录的拦不住。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { joinPosix, readManifest, relFromFeature } from './sources.mjs';
import { normalizeHeading, parseDocument } from './document.mjs';
import { imageLinks } from './language.mjs';


/**
 * 一份文档里的每张图 —— 身份由**位置**给：`§<节> #<该节内第几张>`，图不需要作者起名。
 * 下游哪一节承接它讲的关系，登记在写作设计里（`- 承接上游图：<来源> <身份>`），不写在图里。
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
    out.push({
      section, index, title,
      id: `§${section} #${index}`,
      //: 围栏在原件里的行范围（**1 起，含首尾标记行**）——作者据它去读原件，
      //: 而不是读一份被复制进任务包的副本：副本一旦与原件不同步，他改的是副本。
      at: { from: fence.from + 1, to: fence.to + 1 },
      //: 按**行**给，不拼成字符串：CRLF 的文件拼了再切，每行尾会挂个 `\r`
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
    const { images, bad } = imageLinks(line);
    for (const b of bad) {
      problems.push(`${where(i + 1)}：图片链接写法解析不了（${b.text}）——带空格或括号的路径写成 \`![说明](<路径>)\``);
    }
    for (const { alt, target: src, external, path: ref } of images) {
      if (!alt.trim()) problems.push(`${where(i + 1)}：图片 ${src} 没有 alt 文本——alt 是评审人看不到图时读到的那句话`);
      if (!usable || external || ref === null) continue;
      const idx = byPath.get(joinPosix(storyDir, ref));
      if (idx === undefined) {
        const name = path.posix.basename(ref);
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
  const seen = new Map();              // 引用写法 → 那一张
  for (const img of String(storyText).split(/\r?\n/).flatMap(line => imageLinks(line).images)) {
    if (seen.has(img.target)) problems.push(`story.md：图片 ${img.target} 被引用了不止一次——同一张图只在一处引，那一处说清它画的是什么`);
    seen.set(img.target, img);
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
  for (const { target: src, external, path: ref } of seen.values()) {
    if (external || ref === null) continue;
    const idx = byPath.get(joinPosix(storyDir, ref));
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


function materialImages(ctx) {
  const data = readManifest(ctx);
  if (data === null) return null;                 // 没有清单：由调用方记一笔
  const { images, gap } = imagesIn(data === 'broken' ? null : data);
  return gap ? { gap } : images;
}
