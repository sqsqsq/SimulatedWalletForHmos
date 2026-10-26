/**
 * 成文要用的当前输入 —— 材料与来源、材料里的图（一张图一项，带引用串与登记不用的命令）、
 * 上游里的图（带写作设计登记用的图身份）、蓝图生成图（参考）。
 *
 * `story-build skeleton` 起手与恢复时打印它：上游正文取本次采用的冻结版本，缺席按合同与单据身份说。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { featureRoot, readJsonOrNull, relDisplay } from '../../../../../hooks/shared/paths.mjs';
import { SHELL, shellArg } from './drafts.mjs';
import { designSource, designStatusLines } from './design-source.mjs';
import { diagramsOf, diagramTopic, imagesIn, readablePaths } from './images.mjs';
import { markdownTarget } from './language.mjs';
import { originRows, relFromStory, upstreamDocs } from './sources.mjs';

/**
 * 材料里的图 —— **一张图一项任务**。
 *
 * 单位是**图片对象**，不是路径：同一张图在仓里有两个落点（文档内嵌位置与
 * `ux-reference/` 下的语义名副本）时，那仍是一张图。按路径逐条摆，作者会以为有两张，
 * 于是引两次、或者为「另一张」再补一句说明。
 *
 * 代表路径取**实际读得到**的那一个：登记里的路径可能指向已经不在的文件，
 * 拿它渲染出来的引用串与命令都是坏的。其余落点作为别名列出——他要认得出
 * 「我在别处见过的那张就是这张」。
 *
 * 两张不同的图不合并：它们的取舍各自独立。
 */
function imageSection(projectRoot, feature) {
  const dir = featureRoot(projectRoot, feature);
  const manifest = readJsonOrNull(path.join(dir, 'AR', 'story-src', 'materials.json'));
  const rows = ['## 4a. 材料里的图', ''];
  // **形状不对不是「没有图」**：清单不在、读不出、`materials` 不是数组、`paths` 形状不对，都是缺口。静默按零张渲染的话，
  // 作者会以为这一轮不涉及图。形状判定与全篇 check、审查任务共用 `imagesIn` 一份。
  const { images, gap } = imagesIn(manifest);
  if (gap) {
    rows.push(`${gap}，再跑一次 \`story-build skeleton\`。这一节现在给不出图。`);
    return rows;
  }
  if (!images.length) {
    rows.push('材料清单里现在没有图片。');
    return rows;
  }
  rows.push('一张图一项：引用串可以直接粘。下面的命令**按它自己写的条件跑，不是逐张都跑**：'
    + '`--unused` 会写进「本需求不用它」，`--used` 会把这条登记撤掉，两条都改状态——'
    + '取舍没变的图什么都不用跑。引用串是相对 `AR/story.md` 的，命令的路径是相对工程根的'
    + '——两个基准不一样，自己换算容易差一层。'
    + '属于本需求的图怎么引、不属于的怎么登记，见 `story-write.md`。',
    '');
  const featureDir = relDisplay(projectRoot, featureRoot(projectRoot, feature));
  images.forEach((img, at) => {
    const paths = img.paths;
    // **真读得到**才算落点：目录、坏链接、读不了的文件渲染出来的引用串与命令都是坏的。
    const readable = readablePaths(dir, paths);
    const main = readable[0] ?? null;
    const caption = String(img.caption ?? '').trim();
    if (!main) {
      rows.push(`- **${caption || `第 ${at + 1} 张图`}**：登记的落点一个都读不到`
        + `（${paths.join('、')}）——先把原件补回原位，或重跑 \`story_flow.py round\`；`
        + '这张图现在引不了，也不给可执行的命令（那条命令会指到一个读不到的路径）。', '');
      return;
    }
    const unused = String(img.unused ?? '').trim();
    const aliases = paths.filter(rel => rel !== main);
    rows.push(`- \`![${caption || '这张图是什么'}](${markdownTarget(relFromStory(main))})\``
      + (caption ? '' : ' ← **没有说明**：跑 `import_sources.py --caption-image` 补一句')
      + (unused ? ` ← **已登记不用**：${unused}` : ' ← 还没登记取舍'));
    if (aliases.length) {
      rows.push(`  同一张图的其它落点：${aliases.join('、')}（**是同一张，只引一次**）`);
    }
    rows.push('',
      // 命令写状态，所以动作的条件跟命令贴在一起：隔一段的说明管不住照抄。
      unused
        ? '  这张已经登记不用。**改主意要引用它时**才跑这条，它撤掉上面那条理由；仍然不用就不跑：'
        : '  **决定不用它时**才跑这条，把 `<…>` 换成真的理由；要用它就不跑，把上面那串引进正文：',
      `  \`\`\`${SHELL}`,
      // 整条一行，不续行：续行的反斜杠在模板串里要写两个、渲染出来是一个，
      // 数错一次 shell 就把它当字面参数，而续行不换来任何东西。
      // 围栏按宿主 shell 标注，参数按同一个 shell 的规则引。
      '  python doc/extensions/skills/story/scripts/core/import_sources.py'
        + ` --feature ${shellArg(feature)} --caption-image ${shellArg(`${featureDir}/${main}`)}`
        + (unused ? ' --used' : ' --unused "<为什么它不属于本需求>"'),
      '  ```',
      '');
  });
  return rows;
}

/**
 * 上游文档里的图 —— 身份、主题、原件位置，附本次采用版本的原件内容。
 *
 * 作者按身份在写作设计里登记承接的小节、按行范围回原件核对。**不指定放哪一节**：图讲的事属于哪块内容，
 * 内容在 story 落在哪，承接就在哪；换载体可以，关系不能丢。
 */
function upstreamSection(ctx) {
  const rows = ['## 4b. 上游里的图（在 story 里的去向）', ''];
  const rel = ctx.contract.sources?.SE?.path;
  const docs = upstreamDocs(ctx);
  if (!docs.length) {
    rows.push(rel ? `读不到 \`${rel}\`——上游里有没有图、各讲什么，现在给不出来。先把这份上游正文找回来，再跑一次 \`story-build skeleton\`。`
      : '章节合同没有登记带图的上游文档，这一节没有要承接的图。');
    return rows;
  }
  for (const [label, text] of docs) {
    const list = diagramsOf(text);
    if (!list.length) {
      rows.push(`${label}（\`${rel}\`）里现在没有图。`);
      continue;
    }
    rows.push(`原件在 \`${rel}\`，每张图的内容附在下面（取自本次采用的版本）。`,
      '每一张讲的关系在 story 里由讲这件事的小节承接，在写作设计那一节下写 `- 承接上游图：<身份>` 登记；'
      + '怎样换载体而不丢关系见 `story-write.md` 第三节「换图种可以，丢关系不行」。', '');
    for (const d of list) {
      rows.push(`- **${label} ${d.id}**（${diagramTopic(d)}）——原件 \`${rel}\` 第 ${d.at.from}–${d.at.to} 行；`
        + `登记写 \`- 承接上游图：${label} ${d.id}\``, '', '````mermaid', ...d.lines, '````', '');
    }
  }
  return rows;
}

/** 蓝图生成图：只画视图里的节点与关系，作理解设计的参考；story 的图按读者要判断的事画。 */
function blueprintSection(ctx) {
  const source = designSource(ctx);
  const graphs = (Array.isArray(source.blueprint?.generated_graphs) ? source.blueprint.generated_graphs : [])
    .filter(g => g?.graph_id && typeof g.content === 'string');
  if (!graphs.length) return [];
  const rows = ['## 4c. 蓝图生成图（参考）', '',
    `蓝图 r${source.ref?.revision} 的生成图只画视图里的节点与关系，不是完整业务流程；读它理解设计，story 里的图按读者要判断的事画。`, ''];
  for (const g of graphs) {
    const body = g.content.split(/\r?\n/);
    while (body.length && !body[body.length - 1].trim()) body.pop();
    rows.push(`- **${g.graph_id}**`, '', '````mermaid', ...body, '````', '');
  }
  return rows;
}

/**
 * 成文要用的当前输入 —— 材料与来源、材料里的图、上游里的图、蓝图生成图。
 *
 * `story-build skeleton` 起手与恢复时打印它。
 *
 * @param {{projectRoot: string, featureRoot: string, contract: object, args: {feature: string}}} ctx
 */
export function storyInputs(ctx) {
  const ux = path.join(ctx.featureRoot, 'ux-reference', 'README.md');
  const status = designStatusLines(designSource(ctx));
  return [
    ...(status.length ? ['## 设计状态', '',
      ...status, '',
      '草稿可以成文：原生问题里涉及的业务事实按问题写成待定或限制，不写成已定；准入与施工准备由设计职责推进。', ''] : []),
    '## 4. 材料与来源', '',
    '附录材料清单那张「材料 | 来源 | 贡献」表照这里写：一组一行，来源列列齐这一组的全部原件与采用版本'
    + '（有版号或会议版本写它，没有写下面的摘要）；集合由材料清单派生，漏写一行不会让那份原件免于审查。',
    ...originRows({ ...ctx, srcDir: ctx.srcDir ?? path.join(ctx.featureRoot, 'AR', 'story-src') }), '',
    ...(fs.existsSync(ux)
      ? ['界面交互说明在 `ux-reference/README.md`：业务流程章有人机交互的小节以它与下面的界面原图为依据，'
        + '写作设计在那一节的「依据」里写明用哪一段、哪几张图；页面流转图与表照它写，它没覆盖的普通交互在已定业务内补齐。', ''] : []),
    ...imageSection(ctx.projectRoot, ctx.args.feature), '',
    ...upstreamSection(ctx), '',
    ...blueprintSection(ctx),
  ];
}
