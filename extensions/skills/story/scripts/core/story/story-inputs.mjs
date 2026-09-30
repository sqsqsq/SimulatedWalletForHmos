/**
 * 成文要用的当前输入 —— 材料里的图（一张图一项，带引用串与登记不用的命令）、系统设计里的图（搬进 story）。
 *
 * `story-build skeleton` 起手与恢复时打印它：上游正文从调用方已取得的来源状态取，缺席按合同与单据身份说。
 */
import * as path from 'node:path';
import { featureRoot, readJsonOrNull, relDisplay } from '../../../../../hooks/shared/paths.mjs';
import { SHELL, shellArg } from './drafts.mjs';
import { diagramsOf, diagramTopic, imagesIn, readablePaths } from './images.mjs';
import { relFromStory } from './sources.mjs';

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

/**
 * 上游某一份文档里的图 —— 身份、主题、原件路径与围栏行范围，附这一刻的原件内容。
 *
 * 作者按身份写来源标记、按行范围回原件核对；附上的内容取自原件，改图改的是下游自己的那一张。
 *
 * **不指定放哪一节**：图属于哪块内容，内容在下游落在哪，图就该在哪。文字不搬，story 讲给评审者的是来龙去脉。
 *
 * 读不到分三种说：本轮自己产出的那一份还没写成、本需求本来没有这一份（可选来源）、
 * 该有却读不到——只有最后一种要找回来。都说成读不到，作者会去找一份本来就不该在的文件；
 * 静默给一节空的，他会以为这一轮上游没画过图。
 *
 * @param {{rel: string, text?: string, required?: boolean, why?: string}} src 来源状态里的这一份
 * @param {boolean} derived 合同声明它是本轮流程自己生成的
 */
function diagramSection(heading, label, src, derived) {
  const rows = [heading, ''];
  const rel = src.rel;
  if (typeof src.text !== 'string') {
    rows.push(derived
      ? `\`${rel}\` 还没写成——写成之后跑 \`story-build skeleton\`，它的输出里这一节列出其中的图。`
      : src.required
        ? `读不到 \`${rel}\`——${label} 里有没有图、各讲什么，现在给不出来。先把这份上游正文找回来，再取一次。`
        : `本需求没有 \`${rel}\`（${src.why ?? '可选来源'}），这一节没有要搬的图。`);
    return rows;
  }
  const list = diagramsOf(src.text);
  if (!list.length) {
    rows.push(`${label} 里现在没有图。`);
    return rows;
  }
  const downstream = 'story';
  rows.push(`原件在 \`${rel}\`，每张图的内容附在下面（取自这一刻的原件）。`,
    `每一张都要在 ${downstream} 里对应一张，放哪一节按它讲的内容定——`
    + '搬的时候**围栏第一行写来源标记**（`%% 图源 ' + label + ' §<节> #<第几张>`），'
    + '机器核的就是它。周围的文字自己写。',
    '**对应的含义是标记指向它，不是照抄**：把上游的流程改画成时序、'
    + '按本需求补上它没画的分支，都算对应，改的是画法、讲的是同一件事。',
    '章首那张同时承接上游某张时，标记就写在它的围栏里。', '');
  for (const d of list) {
    rows.push(`- **${label} ${d.id}**（${diagramTopic(d)}）`
      + `——原件 \`${rel}\` 第 ${d.at.from}–${d.at.to} 行；`
      + `标记写 \`%% 图源 ${label} ${d.id}\``, '', '````mermaid', ...d.lines, '````', '');
  }
  rows.push('');
  return rows;
}

/**
 * 成文要用的当前输入 —— 材料里的图、系统设计里的图。
 *
 * `story-build skeleton` 起手与恢复时打印它。`sources` 是调用方这一刻已经取得的来源状态（`sourceStatus`）：上游正文从它取，不再读一遍；
 * 缺席按合同与单据身份说。
 *
 * @param {{projectRoot: string, contract: object, args: {feature: string}}} ctx
 * @param {{docs: object[], missing: object[]}} sources
 */
export function storyInputs(ctx, sources) {
  const feature = ctx.args.feature;
  const of = (key) => sources.docs.find(d => d.doc === key)
    ?? sources.missing.find(m => m.doc === key)
    ?? { rel: ctx.contract.sources?.[key]?.path ?? key };
  const derived = (key) => ctx.contract.sources?.[key]?.derived === true;
  return [
    ...imageSection(ctx.projectRoot, feature), '',
    ...diagramSection('## 4a. 系统设计里的图（搬进 story）', 'SR', of('SE'), derived('SE')),
  ];
}
