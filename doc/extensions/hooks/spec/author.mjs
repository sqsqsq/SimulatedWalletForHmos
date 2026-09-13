/**
 * spec 阶段作者任务包 —— **本次要做什么**，从真源渲染。
 *
 * 与 `author.md` 的分工：那一页写原则与写法（为什么这么做、怎么写才算数），并且是
 * `context-exploration` 里 `key_inputs_read` 能逐字引用的坐标；这一份只出**这一次的数据**——
 * 你现在在哪、本轮激活几条、材料里有哪几张图、十章各答什么、哪些词不能用。
 *
 * 所以这里没有成段的说明文字：讲道理的话属于 `.md`，写在脚本字符串里既不好读也不好改。
 * 数据从三处真源来——章节合同、激活清单、材料清单与流程契约，改真源这里跟着变。
 *
 * ## 作者动笔前自己跑它
 *
 *     node doc/extensions/hooks/spec/author.mjs --feature <名>
 *
 * 宿主的作者事件只在装配 verifier 上下文时消费，从不进入作者动笔前的上下文——
 * 登记在那里，作者要到产物落盘之后才读得到。所以任务包由作者自己取，入口写在
 * SKILL、CLAUDE.md 扩展段与 `story_flow.py status` 的下一步文本里。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { featureRoot, readJsonOrNull, relDisplay } from '../shared/paths.mjs';
import { activeKnowledge } from '../shared/knowledge.mjs';
import { clientVocabulary } from '../../skills/story/scripts/core/story/language.mjs';
import { originalArSource } from '../../skills/story/scripts/core/flow-check.mjs';
import { FLOW_SCRIPT, queryFlowStatus }
  from '../../skills/story/scripts/core/flow/client.mjs';
import { shellArg } from '../../skills/story/scripts/core/story/drafts.mjs';
import { diagramsOf, diagramTopic }
  from '../../skills/story/scripts/core/story/images.mjs';
import { relFromStory } from '../../skills/story/scripts/core/story/sources.mjs';
import { DECISION_FIELDS } from '../../skills/story/scripts/core/story/review.mjs';

const SELF = 'doc/extensions/hooks/spec/author.md';
const SKILL_ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'skills', 'story');

/**
 * 位置从 `story_flow.py status` 来，本文件不自己算一遍。
 *
 * 算两遍就会有两个答案——流程往前走一步，谁先过期都说不准。查询走共用客户端
 * （`flow/client.mjs`），工程根显式传给它：Python 没有 `--project-root` 时按脚本自身位置
 * 解析工程，只设 cwd 的话，同一份任务包里位置读的是机制仓、材料与知识读的是目标工作区。
 * 问不到就如实说问不到并给出可复跑的命令，不退回自己判断。
 */
function positionSection(projectRoot, feature) {
  const { data: status, error } = queryFlowStatus(projectRoot, feature, { timeoutMs: 20000 });
  // 照抄这一行就要能原样跑：脚本取客户端真正调的那一个，参数按 shell 规则引起来
  // （路径带空格或 `$` 时，裸拼会被拆开或被展开）。
  const command = `python ${shellArg(FLOW_SCRIPT)} status`
    + ` --feature ${shellArg(feature)} --project-root ${shellArg(projectRoot)}`;
  if (error) {
    return ['## 1. 你现在在哪', '',
      `**位置没取到：${error}**`, '',
      '它答不出来，这一步的下一动作就没有真源。先让这条命令在本工程跑通（PowerShell'
      + '里路径带空格要引起来）：', '', '```powershell', command, '```'];
  }
  if (!status || status.exists === false) {
    return ['## 1. 你现在在哪', '',
      '这个需求还没走过 `/story` 的 S1–S3：先按 SKILL 走材料与范围，收口后再回来。',
      '', '```powershell', command, '```'];
  }
  const rows = ['## 1. 你现在在哪', '', `**下一步**：${status.action}`];
  const state = status.material_state;
  if (state && (state.pending.length || state.changed)) {
    // 材料事实与位置同源：作者按同一句话处置，不必自己再判一次「料齐没齐」。
    rows.push('', state.pending.length
      ? `**收件箱里还有 ${state.pending.length} 份原件没并入正文**`
        + `（${state.pending.slice(0, 3).join('、')}）——先导入，它们并进正文之前不起稿。`
      : '**材料与本轮登记的基准不一致**——按上面那一步登记之后再动笔。');
  }
  if (status.sidecar) {
    rows.push('', '这一步要写的文件形状：', '', '```json',
      JSON.stringify(status.sidecar, null, 2), '```');
  }
  return rows;
}

function knowledgeSection(projectRoot, feature) {
  const useFile = path.join(featureRoot(projectRoot, feature), 'spec', 'knowledge-use.yaml');
  const knowledge = activeKnowledge(projectRoot);
  // 清单为空 = 这个仓还没配置知识。说这一句，不要渲染出「激活 0 条约束（域：）」——
  // 那种句子看起来像派生坏了，作者会去翻机制找原因，而事实是这里本来就没东西可判。
  if (!knowledge.entries.length && !knowledge.facts.length && !knowledge.patterns.length) {
    return ['## 2. 本轮的知识判断（`spec/knowledge-use.yaml`）',
      '',
      '**本仓未配置知识**——激活清单里没有登记任何规约、项目事实或模式，'
      + '没有要判的东西。这一节不用写，`knowledge-use.yaml` 也不用建。',
      ''];
  }
  return ['## 2. 本轮的知识判断（`spec/knowledge-use.yaml`）',
    '',
    `激活 **${knowledge.entries.length} 条**约束（域：${knowledge.prefixes.join('、')}）、`
    + `**${knowledge.facts.length} 份**项目事实；在册模式候选：`
    + `${knowledge.patternIds.join(' / ') || '（无）'}。`,
    '',
    // 事实文件逐份列路径与它讲什么：规则里说「见部件画像」，画像在哪只有这里说得出来
    //（清单是目标仓的，机制不写死任何一个文件名）。
    '项目事实这几份，规则里提到「画像」「工程事实」时来这里找：',
    ...knowledge.facts.map(f => `- \`doc/extensions/${f.file}\`——${f.facets.join('、')}`),
    '',
    fs.existsSync(useFile)
      ? '骨架已在磁盘上，逐条填 `applicable` 与依据；填完跑 `knowledge-use.mjs render --feature <名>`。'
      : `先跑 \`node doc/extensions/hooks/shared/knowledge-use.mjs init --feature ${feature}\` 生成骨架`
        + '（激活条目一条不落，你只填判断），填完跑 `render`。',
    '',
    ...acceptanceKeys(useFile, projectRoot, feature),
    '怎么填、什么算依据，见 `author.md`。'];
}

/**
 * 判为 applicable 的规约，各要在需求根目录的 `acceptance.yaml` 接回一条验收。
 *
 * **路径按框架解析的那一个给**：它读 `<features_dir>/<feature>/acceptance.yaml`，
 * 不是 `spec/` 下面。写错一个层级，作者会为了确认到底在哪去翻框架源码。
 *
 * 漏接是 harness 的常见首红：判了 applicable 却没有对应的 `knowledge_rule`。
 * 编号列出来，作者照着接；骨架还没填时给规则本身。
 *
 * **条目长什么样也一并给**：`acceptance.schema.yaml` 只约束顶层 `criteria`，
 * 不定义条目字段，渲染不出形状；作者于是去 grep 框架的 `check-acceptance.ts`
 * 与本扩展的 `post_check.mjs`，为的只是搞清 `knowledge_rule` 放哪一层。
 */
function acceptanceKeys(useFile, projectRoot, feature) {
  const text = fs.existsSync(useFile) ? fs.readFileSync(useFile, 'utf-8') : '';
  const ids = [...text.matchAll(/^\s*-?\s*id:\s*(\S+)[\s\S]*?applicable:\s*true/gm)].map(m => m[1]);
  return [ids.length
    ? `判 \`applicable: true\` 的每一条，都要在 \`${acceptancePath(projectRoot, feature)}\` 有一条带 `
      + `\`knowledge_rule: <编号>\` 的 criteria。本轮已判 applicable：${ids.join('、')}。`
    : `判 \`applicable: true\` 的每一条，都要在 \`${acceptancePath(projectRoot, feature)}\` 有一条带 `
      + '`knowledge_rule: <编号>` 的 criteria——填完骨架再回头对一遍。',
  '',
  '一条最小的长这样（`knowledge_rule` 与 `id` 平级，都在 `criteria` 的条目下）：',
  '',
  '```yaml',
  'criteria:',
  '  - id: AC-1',
  '    priority: P2',
  '    description: {{这条规约在本需求上要保证什么，用可观察的话写}}',
  '    testable: true',
  '    verification_steps:',
  '      - {{怎么验}}',
  '    expected_result: {{看到什么算过}}',
  '    knowledge_rule: {{规约编号}}',
  '```',
  ''];
}

/** 验收落在哪 —— 框架解析的是需求根目录那一份，不是 `spec/` 下面。 */
function acceptancePath(projectRoot, feature) {
  return `${relDisplay(projectRoot, path.join(featureRoot(projectRoot, feature),
    'acceptance.yaml'))}`;
}

function decisionSection(contract) {
  const categories = (contract.decision_categories ?? []).map(c => c.key).filter(Boolean);
  const fields = DECISION_FIELDS.map(([name, what]) => `\`${name}\`（${what}）`).join('、');
  return ['## 3. 决策登记（`AR/story-src/decisions.json`）',
    '',
    `每条要写满：\`id\`、\`status\`（\`settled\` / \`open\`）、\`category\`、${fields}。`,
    '',
    `\`category\` 取自合同：${categories.join('、')}。`,
    '',
    '澄清正文怎么分段，见 `story-write.md` 的「决策登记」。'];
}

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
  if (manifest === null) {
    // **读不出来不是「没有图」**：静默按零张渲染，作者会以为这一轮不涉及图。
    rows.push('材料清单（`AR/story-src/materials.json`）读不出来——它只应由脚本写入；'
      + '删掉后重跑 `story_flow.py round` 再取这份任务包。这一节现在给不出图。');
    return rows;
  }
  // 只认当前合同：`materials` 与每条的 `paths`。旧的 `items`/`path` 不再兼容——
  // 两种形状都收的话，写入侧改了形状，读出来的是空清单而没有人知道。
  const images = (Array.isArray(manifest.materials) ? manifest.materials : [])
    .filter(m => String(m?.kind ?? '').includes('image'));
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
    const paths = (Array.isArray(img.paths) ? img.paths : []).filter(Boolean);
    const readable = paths.filter(rel => fs.existsSync(path.join(dir, ...rel.split('/'))));
    const main = readable[0] ?? paths[0];
    if (!main) {
      rows.push(`- **第 ${at + 1} 张图**：登记里没有落点——`
        + '跑 `story_flow.py round` 重算材料清单再取这份任务包。', '');
      return;
    }
    const caption = String(img.caption ?? '').trim();
    const unused = String(img.unused ?? '').trim();
    const aliases = paths.filter(rel => rel !== main);
    rows.push(`- \`![${caption || '这张图是什么'}](${relFromStory(main)})\``
      + (caption ? '' : ' ← **没有说明**：跑 `import_sources.py --caption-image` 补一句')
      + (unused ? ` ← **已登记不用**：${unused}` : ' ← 还没登记取舍'));
    if (!readable.length) {
      rows.push(`  登记的落点在盘上读不到（${paths.join('、')}）——`
        + '先把原件补回原位，或重跑 `story_flow.py round`；这张图现在引不了。');
    }
    if (aliases.length) {
      rows.push(`  同一张图的其它落点：${aliases.join('、')}（**是同一张，只引一次**）`);
    }
    rows.push('',
      // 命令写状态，所以动作的条件跟命令贴在一起：隔一段的说明管不住照抄。
      unused
        ? '  这张已经登记不用。**改主意要引用它时**才跑这条，它撤掉上面那条理由；仍然不用就不跑：'
        : '  **决定不用它时**才跑这条，把 `<…>` 换成真的理由；要用它就不跑，把上面那串引进正文：',
      '  ```powershell',
      // 整条一行，不续行：续行的反斜杠在模板串里要写两个、渲染出来是一个，
      // 数错一次 shell 就把它当字面参数，而续行不换来任何东西。
      // 围栏标 powershell：参数按本工程命令行的规则引，换 shell 要自己核。
      '  python doc/extensions/skills/story/scripts/core/import_sources.py'
        + ` --feature ${shellArg(feature)} --caption-image ${shellArg(`${featureDir}/${main}`)}`
        + (unused ? ' --used' : ' --unused "<为什么它不属于本需求>"'),
      '  ```',
      '');
  });
  return rows;
}

/**
 * S4 提交时留存下来的上游原 AR —— 唯一的原件定位读取（flow-check.originalArSource）。
 *
 * 它与当前的提取稿是两份文件：`AR/design.md` 在收口后是提取稿，上游原话只在
 * 留存的那一份里。没有可留存原件时如实说「没有」；指针坏了要披露问题，
 * 不能静默当作没有原件，也不能拿提取稿顶替上游原话。人工补录仍看 upstream.md。
 */
function originalArSection(projectRoot, feature) {
  const { path: abs, problem } = originalArSource(featureRoot(projectRoot, feature));
  const rows = ['## 4a. 上游原 AR（提交时留存的原件）', ''];
  if (problem) {
    rows.push(`**原输入定位出了问题：${problem}**——动笔前先把这份原件找回来，`
      + '不能拿当前的提取稿当上游原话。');
    return rows;
  }
  if (!abs) {
    rows.push('本轮没有可留存的上游原 AR（init 的空骨架不是上游给的东西）——'
      + '按 RR/SR 与人工补录材料提取即可。');
    return rows;
  }
  rows.push(`上游原话在 \`${relDisplay(projectRoot, abs)}\`（提交时留存的原件）。`
    + '当前的 `AR/design.md` 是收口时提交的提取稿——两者是两份文件，'
    + '读上游原话去前一份，不要拿提取稿自证。', '');
  return rows;
}

/**
 * 上游某一份文档里的图 —— **给坐标，不给副本**。
 *
 * 从前把每张图的围栏整段复制进任务包。那份副本一旦与原件不同步，作者改的是副本；
 * 任务包也因此长到一次读不完。现在给的是**身份、主题、原件路径与围栏行范围**，
 * 他按坐标去读原件——原件是唯一的那一份。
 *
 * **不指定放哪一节**：图属于哪块内容，内容在下游落在哪，图就该在哪。
 * 文字不搬：每一环讲的事情不同，spec 讲给下游的是契约，story 讲给评审者的是来龙去脉。
 *
 * 原件读不到时**报问题**，不静默给一节空的——那会让作者以为这一轮上游没画过图。
 */
function diagramSection(heading, label, rel, source, downstream) {
  const rows = [heading, ''];
  if (source === null) {
    rows.push(`读不到 \`${rel}\`——${label} 里有没有图、各讲什么，现在给不出来。`
      + '先把这份上游正文找回来，再取一次这份任务包。');
    return rows;
  }
  const list = diagramsOf(source);
  if (!list.length) {
    rows.push(`${label} 里现在没有图。`);
    return rows;
  }
  rows.push(`原件在 \`${rel}\`——**按行号去读它**，这里不复制一份副本（副本会与原件不同步）。`,
    `每一张都要在 ${downstream} 里对应一张，放哪一节按它讲的内容定——`
    + '搬的时候**围栏第一行写来源标记**（`%% 图源 ' + label + ' §<节> #<第几张>`），'
    + '机器核的就是它。周围的文字自己写。',
    '**对应的含义是标记指向它，不是照抄**：把上游的流程改画成时序、'
    + '按本需求补上它没画的分支，都算对应，改的是画法、讲的是同一件事。',
    '两节列的是同一张图时（系统设计画过、spec 的流程图就是它），'
    + `${downstream} 里只放一张，两行标记都写在这个围栏开头；`
    + '章首那张同时承接上游某张时，标记就写在它的围栏里。', '');
  for (const d of list) {
    rows.push(`- **${label} ${d.id}**（${diagramTopic(d)}）`
      + `——原件 \`${rel}\` 第 ${d.at.from}–${d.at.to} 行；`
      + `标记写 \`%% 图源 ${label} ${d.id}\``);
  }
  rows.push('');
  return rows;
}

/**
 * 上游与本阶段产物的正文。
 *
 * **读不到返回 null，不是空串**：空串与「这份文档里没有图」同形，而前者要报出来——
 * 静默给一节空的，作者会以为这一轮上游没画过图。
 */
function docText(projectRoot, feature, ...rel) {
  const abs = path.join(featureRoot(projectRoot, feature), ...rel);
  try { return fs.readFileSync(abs, 'utf-8'); } catch { return null; }
}

/**
 * 禁用词：词表 + **在哪不算**。
 *
 * 词表、作用域、豁免三样都在这一节：哪几章整章豁免、review 的哪几类议题豁免、
 * 哪几种语境下同一个词不算，都从合同渲染，判定按同一份数据走。
 */
function vocabularySection(contract) {
  const rows = ['## 6. 这些词不能用（服务器侧词汇，单独使用也算）', ''];
  for (const { term, hint } of clientVocabulary()) rows.push(`- 「${term}」→ ${hint}`);

  const chapters = (contract.chapters ?? [])
    .filter(c => c?.banned_terms_exempt).map(c => c.title);
  const categories = (contract.decision_categories ?? [])
    .filter(c => c?.banned_terms_exempt).map(c => c.key);
  rows.push('', '**在哪不算**：', '',
    chapters.length
      ? `- 整章豁免：「${chapters.join('」「')}」——这几章讲的就是发布与回退动作本身；`
      : '- 没有整章豁免的章；',
    categories.length
      ? `- 决策议题豁免：类别为「${categories.join('」「')}」的那几条，`
        + 'review 里它们照原样写；'
      : '- 没有豁免的决策类别；',
    '- 同一个词的另一种语义不算：数据或状态层面的「回退」（缓存缺失回退云侧查询、'
    + '事务回滚）说的不是发布动作；',
    '- 引用上游规约的章节名不算——那是在指路，不是在用这个词；',
    '- 讲禁用词本身的地方不算（比如这一节）。');
  rows.push('', '数值怎么标来源、验收怎么接回规约，见 `author.md`。');
  return rows;
}

/**
 * 任务包正文。合同读不到就抛——任务包是它的投影，缺了没有可降级的形态，
 * 静默出一份少了五章要求的任务包比报错更贵。
 */
function taskPackage(projectRoot, feature) {
  const contract = readJsonOrNull(path.join(SKILL_ROOT, 'contracts', 'story-chapters.json'));
  if (!contract) {
    throw new Error('章节合同读不到：任务包是它的投影，缺了就没有任务包');
  }

  const rows = [
    `# spec 阶段 · 本次任务包（${feature}）`,
    '',
    '`context-exploration` 的 `key_inputs_read` 要含 '
    + `\`${SELF}\`——本任务包是它的展开。`,
    '',
    ...positionSection(projectRoot, feature),
    '',
    ...knowledgeSection(projectRoot, feature),
    '',
    ...decisionSection(contract),
    '',
    ...imageSection(projectRoot, feature),
    '',
    ...originalArSection(projectRoot, feature),
    '',
    ...diagramSection('## 4b. 系统设计里的图（搬进 story）', 'SR', 'SR/design.md',
      docText(projectRoot, feature, 'SR', 'design.md'), 'story'),
    '',
    ...diagramSection('## 4c. spec 里的图（搬进 story）', 'spec', 'spec/spec.md',
      docText(projectRoot, feature, 'spec', 'spec.md'), 'story'),
    '',
    ...vocabularySection(contract),
  ];
  return rows.join('\n');
}

const USAGE = '用法：node doc/extensions/hooks/spec/author.mjs --feature <名>';

function main(argv) {
  const at = argv.indexOf('--feature');
  const feature = at >= 0 ? String(argv[at + 1] ?? '').trim() : '';
  if (!feature) {
    process.stderr.write(USAGE + '\n');
    return 2;
  }
  process.stdout.write(taskPackage(process.cwd(), feature) + '\n');
  return 0;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  try {
    process.exit(main(process.argv.slice(2)));
  } catch (err) {
    process.stderr.write(`${err?.message ?? err}\n`);
    process.exit(1);
  }
}
