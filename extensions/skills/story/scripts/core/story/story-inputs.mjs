/**
 * 成文要用的当前输入 —— 材料里的图（一张图一项，带引用串与登记不用的命令）、本次采用来源与蓝图里的图（带可粘的图源标记）、
 * 附录材料清单要列的外部原件。
 *
 * `story-build skeleton` 起手与恢复时打印它：上游正文从调用方已取得的来源状态取，缺席按合同与单据身份说。
 */
import * as path from 'node:path';
import { featureRoot, readJsonOrNull, relDisplay } from '../../../../../hooks/shared/paths.mjs';
import { SHELL, shellArg } from './drafts.mjs';
import { adoptedInputs, designSource } from './design-source.mjs';
import { diagramBody, diagramsOf, diagramTopic, imagesIn, readablePaths } from './images.mjs';
import { externalOriginals, relFromStory } from './sources.mjs';

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
  const rows = ['## 4. 材料里的图', ''];
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
    rows.push(`- \`![${caption || '这张图是什么'}](${relFromStory(main)})\``
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

/** 一张可用的来源图：身份、主题、位置、可粘的标记与图体。 */
function diagramRow(title, where, mark, lines) {
  return [`- **${title}**——${where}；标记：\`%% 图源 ${JSON.stringify(mark)}\``, '', '````mermaid', ...lines, '````', ''];
}

/**
 * 本次采用来源里的图与蓝图生成图 —— 身份、主题、原件位置，附原件内容与可直接粘的来源标记。
 *
 * **不指定放哪一节、不要求每张都用**：图属于哪块内容，内容在 story 落在哪，图就在哪；
 * 原样适用的 reuse，要补局部关系的 refine，不适用的在材料取舍说明里写去向，没有适用来源的按设计新绘、不写标记。
 */
function diagramSection(ctx) {
  const rows = ['## 4a. 采用来源与蓝图里的图', ''];
  const docs = [...adoptedInputs(ctx).documents].map(([at, text]) => [at, diagramsOf(text)]).filter(([, list]) => list.length);
  const source = designSource(ctx);
  const graphs = (Array.isArray(source.blueprint?.generated_graphs) ? source.blueprint.generated_graphs : [])
    .filter(g => g?.graph_id && typeof g.content === 'string');
  if (!docs.length && !graphs.length) {
    rows.push('本次冻结的采用来源与蓝图里都没有可解析的 Mermaid 图（还没交给设计时没有冻结来源）；'
      + '图片、PlantUML 等其他格式没有作结构解析，读原件自己对照。需要图时按设计新绘，不写图源标记。');
    return rows;
  }
  rows.push('每张图怎么用按它讲的内容定：',
    '- **原样适用**（同一范围、同一粒度）：整张搬进来，围栏开头粘下面给的标记（`mode` 是 `reuse`），图体逐行不改；',
    '- **要补本需求的局部关系**：在它上面改，标记里的 `mode` 换成 `refine`，增量写进写作设计这一节的依据；',
    '- **不适用**：不搬，在材料取舍说明里写它的去向；没有适用来源的图按设计新绘，不写标记。',
    '一张图承接几张来源时，围栏开头一行写一个来源；周围的文字自己写。', '');
  for (const [at, list] of docs) {
    for (const d of list) {
      rows.push(...diagramRow(`${d.id}（${diagramTopic(d)}）`, `原件 \`${at}\` 第 ${d.at.from}–${d.at.to} 行`,
        { kind: 'document', path: at, diagram: d.id, mode: 'reuse' }, diagramBody(d)));
    }
  }
  if (graphs.length) rows.push('蓝图生成图只画视图里的节点与关系，不是完整业务流程：', '');
  for (const g of graphs) {
    const lines = g.content.split(/\r?\n/);
    while (lines.length && !lines[lines.length - 1].trim()) lines.pop();
    rows.push(...diagramRow(g.graph_id, `蓝图 r${source.ref.revision}`,
      { kind: 'blueprint', blueprint_ref: source.ref, graph_id: g.graph_id, mode: 'reuse' }, lines));
  }
  return rows;
}

/** 附录材料清单要列的外部原件：每份一行、材料列用给的链接；转换稿归回原件。与清单检查同一份集合。 */
function materialSection(ctx) {
  const set = externalOriginals(ctx);
  const rows = ['## 4b. 材料清单要列的原件', ''];
  if (!set) return [...rows, '还没交给设计，没有冻结快照：原件集合在交给设计之后定。'];
  rows.push('附录材料清单每份原件一行，材料列用下面的链接；转换稿与抽出的图归回原件，提取稿、人签导出、图片不列：', '',
    ...[...set.originals].map(([o, via]) => `- \`[${path.posix.basename(o)}](${relFromStory(o)})\`${via ? `——经收件箱导入，转换稿是 ${via}` : ''}`));
  return set.gap ? [...rows, '', `缺口：${set.gap}`] : rows;
}

/**
 * 成文要用的当前输入 —— 材料里的图、采用来源与蓝图里的图、材料清单要列的原件。
 *
 * `story-build skeleton` 起手与恢复时打印它。
 *
 * @param {{projectRoot: string, contract: object, args: {feature: string}}} ctx
 */
export function storyInputs(ctx) {
  return [...imageSection(ctx.projectRoot, ctx.args.feature), '', ...diagramSection(ctx), '', ...materialSection(ctx)];
}
