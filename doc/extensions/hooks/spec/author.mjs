/**
 * spec 阶段作者任务包 —— **本次要做什么**，从真源渲染。
 *
 * 与 `author.md` 的分工：那一页写原则与写法（为什么这么做、怎么写才算数），并且是
 * `context-exploration` 里 `key_inputs_read` 能逐字引用的坐标；这一份只出**这一次的数据**——
 * 你现在在哪、本轮的知识判断、决策登记、材料与上游里的图、统计设计要交什么、哪些词不能用。
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
import { extensionRoot, featureRoot, readJsonOrNull, readTextOrNull, relDisplay } from '../shared/paths.mjs';
import { specStatPoints, statDesignState } from '../shared/stat-points.mjs';
import { isStoryFeature } from '../../skills/story/scripts/core/flow/check.mjs';
import { activeKnowledge, knowledgeGuide } from '../shared/knowledge.mjs';
import { codeRequirementIds, readUse, UseError } from '../shared/knowledge-use/document.mjs';
import { clientVocabulary } from '../../skills/story/scripts/core/story/language.mjs';
import { FLOW_SCRIPT, queryFlowStatus }
  from '../../skills/story/scripts/core/flow/client.mjs';
import { shellArg } from '../../skills/story/scripts/core/story/drafts.mjs';
import { diagramsOf, diagramTopic, imagesIn, readablePaths }
  from '../../skills/story/scripts/core/story/images.mjs';
import { relFromStory, sourceStatus } from '../../skills/story/scripts/core/story/sources.mjs';
import { DECISION_FIELDS, decisionList } from '../../skills/story/scripts/core/story/review.mjs';

const SELF = 'doc/extensions/hooks/spec/author.md';
const TEMPLATE = 'doc/extensions/skills/story/templates/spec-sections.md';
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
  // 路径按实际扩展根给（`paths.extension_dir`），与知识加载读的是同一处——写死默认目录，
  // 目标仓换了目录时规则照常加载，作者拿到的却是一条不存在的路径。
  const where = f => relDisplay(projectRoot, path.join(extensionRoot(projectRoot), f.file));
  // 清单为空 = 这个仓还没配置知识。说这一句，不要渲染出「激活 0 条约束（域：）」——
  // 那种句子看起来像派生坏了，作者会去翻机制找原因，而事实是这里本来就没东西可判。
  if (!knowledge.entries.length && !knowledge.facts.length && !knowledge.patterns.length) {
    return ['## 2. 本轮的知识判断（`spec/knowledge-use.yaml`）',
      '',
      '**本仓未配置知识**——激活清单里没有登记任何规约、项目事实或模式，'
      + '没有要判的东西。这一节不用写，`knowledge-use.yaml` 也不用建。',
      '本需求要用到的项目能力从代码与材料取证，仍缺的列为未决。',
      ...knowledgeGuide(projectRoot, knowledge),
      ''];
  }
  return ['## 2. 本轮的知识判断（`spec/knowledge-use.yaml`）',
    '',
    `激活 **${knowledge.entries.length} 条**约束（域：${knowledge.prefixes.join('、')}）、`
    + `**${knowledge.facts.length} 份**项目事实；在册模式候选：`
    + `${knowledge.patternIds.join(' / ') || '（无）'}。`,
    '',
    ...knowledgeGuide(projectRoot, knowledge),
    '',
    // 项目事实逐份列面名：知识使用登记的 facet 取这里的名字（清单是目标仓的，机制不写死任何一个文件名）。
    '项目事实的面（登记 `facts[].used` 时 facet 取这些名字）：',
    ...knowledge.facts.map(f => `- \`${where(f)}\`——${f.facets.join('、')}`),
    '',
    // 规约的原文入口：判断前读命中域的整份文件——主表是索引，落法附注里的要求同样有效。
    '规约原文在这几份（判命中之前读该域整份，落法附注同样有效）：',
    ...knowledge.constraints.map(c => `- \`${where(c)}\`——${c.domain}：${c.title}`),
    '',
    fs.existsSync(useFile)
      ? '骨架已在磁盘上：判断先于承载章的设计，设计定下的落点同步回这里；填完跑 `knowledge-use.mjs render --feature <名>`。'
      : `先跑 \`node doc/extensions/hooks/shared/knowledge-use.mjs init --feature ${feature}\` 生成骨架`
        + '（激活条目一条不落，你只填判断），填完跑 `render`。',
    '',
    ...acceptanceKeys(projectRoot, feature, knowledge),
    '怎么填、什么算依据，见 `author.md`。'];
}

/**
 * 判为 applicable 的规约，各要在需求根目录的 `acceptance.yaml` 接回一条验收。
 *
 * **路径按框架解析的那一个给**：它读 `<features_dir>/<feature>/acceptance.yaml`，
 * 不是 `spec/` 下面。写错一个层级，作者会为了确认到底在哪去翻框架源码。
 *
 * 命中集合与 spec 门禁同一份定义；骨架还没填或读不出时给规则本身。
 *
 * **条目长什么样也一并给**：`acceptance.schema.yaml` 只约束顶层 `criteria`，不定义条目字段，
 * 这里给一条满足 framework 必填项的最小条目。
 */
function acceptanceKeys(projectRoot, feature, knowledge) {
  let ids = [];
  try {
    ids = codeRequirementIds(readUse(projectRoot, feature), knowledge);
  } catch (e) {
    if (!(e instanceof UseError)) throw e;
  }
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
  '    ut_layer: unit',
  '    knowledge_rule: {{规约编号}}',
  '```',
  ''];
}

/** 验收落在哪 —— 框架解析的是需求根目录那一份，不是 `spec/` 下面。 */
function acceptancePath(projectRoot, feature) {
  return `${relDisplay(projectRoot, path.join(featureRoot(projectRoot, feature),
    'acceptance.yaml'))}`;
}

/**
 * 当前登记的原文：按 open / settled 分组，每项的 id、状态、标题、该谁定与澄清正文照抄。
 * 哪段正文受哪条影响由作者按原文判断——登记表里没有这份结构，脚本不从自然语言里推。
 * 文件在而读不出条目是缺口，不当成零条。
 */
function currentDecisions(projectRoot, feature) {
  const file = path.join(featureRoot(projectRoot, feature), 'AR', 'story-src', 'decisions.json');
  const rel = relDisplay(projectRoot, file);
  if (!fs.existsSync(file)) return ['**本次尚无登记**：按业务流程走的时候认出要人定的事，照上面的字段登记。'];
  const list = decisionList(readJsonOrNull(file));
  if (!list) {
    return [`**\`${rel}\` 读不出条目**：文件不是合法 JSON，或顶层既不是 \`[ … ]\` 也不是 \`{"decisions": [ … ]}\`——`
      + '先修好它再动笔，读不出不等于没有议题。'];
  }
  if (!list.length) return ['**当前登记为空**：按业务流程走的时候认出要人定的事，照上面的字段登记。'];
  const rows = ['当前登记（原文照列；仍 open 的选择只写共同要求与受影响的条件，不写成确定的行为或验收）：', ''];
  for (const status of ['open', 'settled']) {
    const items = list.filter(d => String(d?.status ?? '') === status);
    if (!items.length) continue;
    rows.push(`### ${status}`, '');
    for (const d of items) {
      rows.push(`#### ${d.id ?? '（无 id）'}：${d.title ?? ''}`, '', `该谁定：${d.decider ?? '—'}`, '',
        String(d.clarification ?? '').trim() || '（澄清正文空）', '');
    }
  }
  const other = list.filter(d => !['open', 'settled'].includes(String(d?.status ?? '')));
  if (other.length) rows.push(`状态不是 open / settled 的：${other.map(d => d?.id ?? '（无 id）').join('、')}——按字段要求改正。`, '');
  rows.push('写完正文后按当时的登记再对一遍：新增或改过的议题，影响有没有写回功能、流程与验收处。');
  return rows;
}

function decisionSection(projectRoot, feature, contract) {
  const categories = (contract.decision_categories ?? []).map(c => c.key).filter(Boolean);
  const fields = DECISION_FIELDS.map(([name, what]) => `\`${name}\`（${what}）`).join('、');
  return ['## 3. 决策登记（`AR/story-src/decisions.json`）',
    '',
    `每条要写满：\`id\`、\`status\`（\`settled\` / \`open\`）、\`category\`、${fields}。`,
    '',
    '`review_mode` 按人在评审时实际要做的事填：从几个方案里选一个写 `choice`，复核一个已有结论写 `confirm`；'
    + '它只决定评审记录给什么填写位，与 `status` 各管各的。',
    '',
    `\`category\` 取自合同：${categories.join('、')}。`,
    '',
    '**`settled` 要指得出结论是谁给的**：要人表态才成立的事（业务口径、对外承诺、'
    + '规约里处置标「（评审动作）」的那几条），依据里写明那个人在哪说过——'
    + '材料的哪一节、会议的哪个话题、评审记录里谁的哪一条。指不出来就是 `open`，'
    + '`decider` 写该谁定。`decider` 有名字只说明该谁定，不说明他定过。',
    '',
    '澄清正文怎么分段，见 `story-write.md` 的「决策登记」。',
    '',
    ...currentDecisions(projectRoot, feature)];
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
  // **形状不对不是「没有图」**：清单不在、读不出、`materials` 不是数组、`paths` 形状不对，都是缺口。静默按零张渲染的话，
  // 作者会以为这一轮不涉及图。形状判定与全篇 check、审查任务共用 `imagesIn` 一份。
  const { images, gap } = imagesIn(manifest);
  if (gap) {
    rows.push(`${gap}，再取这份任务包。这一节现在给不出图。`);
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
 * 上游某一份文档里的图 —— 身份、主题、原件路径与围栏行范围，附这一刻的原件内容。
 *
 * 作者按身份写来源标记、按行范围回原件核对；附上的内容取自原件，改图改的是下游自己的那一张。
 *
 * **不指定放哪一节**：图属于哪块内容，内容在下游落在哪，图就该在哪。
 * 文字不搬：每一环讲的事情不同，spec 讲给下游的是契约，story 讲给评审者的是来龙去脉。
 *
 * 读不到分三种说：本轮自己产出的那一份（Spec）还没写成、本需求本来没有这一份（可选来源）、
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
    '两节列的是同一张图时（系统设计画过、spec 的流程图就是它），'
    + `${downstream} 里只放一张，两行标记都写在这个围栏开头；`
    + '章首那张同时承接上游某张时，标记就写在它的围栏里。', '');
  for (const d of list) {
    rows.push(`- **${label} ${d.id}**（${diagramTopic(d)}）`
      + `——原件 \`${rel}\` 第 ${d.at.from}–${d.at.to} 行；`
      + `标记写 \`%% 图源 ${label} ${d.id}\``, '', '````mermaid', ...d.lines, '````', '');
  }
  rows.push('');
  return rows;
}

/**
 * 成文要用的当前输入 —— 材料里的图、系统设计与 Spec 里的图。
 *
 * `story-build skeleton` 起手与恢复时打印它，本任务包也列它：两处读同一份渲染。
 * `sources` 是调用方这一刻已经取得的来源状态（`sourceStatus`）：上游正文从它取，不再读一遍；
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
    ...diagramSection('## 4a. 系统设计里的图（搬进 story）', 'SR', of('SE'), derived('SE')), '',
    ...diagramSection('## 4b. spec 里的图（搬进 story）', 'spec', of('SPEC'), derived('SPEC')),
  ];
}

/**
 * 统计设计这次要交什么、动笔前读什么、写完怎么自查——在动笔那一刻送到作者面前。
 *
 * 只说阶段任务与形状，不复述知识里的定义与步骤，也不点知识的名字：哪份讲统计设计由作者按
 * 各知识的用途自述去找。已写了 §9.1.4 的，列出每个指标有没有定义段、几个统计点，返修时照着补。
 */
function statDesignSection(projectRoot, feature) {
  const dir = featureRoot(projectRoot, feature);
  const rows = ['## 5. 统计设计（§9.1.4）', ''];
  if (!isStoryFeature(dir)) return [...rows, '本需求没走 /story，不要求 §9.1.4 的统计设计：按本阶段原有要求写。'];
  rows.push('这次要交：§9.1.4 先一段总述，然后每个指标一个小节、标题写指标名；小节下先写定义段，'
    + `再放带「统计点」「所在流程」列的表，表后写边界。形状见 \`${TEMPLATE}\` 的 9.1.4。`,
  '动笔前：在第 2 节的知识清单里找用途写到统计设计的那份，重读它读者含 spec 的上篇；不凭阶段开头的记忆写。',
  '写完后：按那一篇的应用步骤逐条回查，走不通的直接改设计，不另写推演。',
  '§9.1.4 设计打点：业务结果与每次上报要带的信息写在这里；字段名、取值与登记由 plan 实现。');
  const spec = readTextOrNull(path.join(dir, 'spec', 'spec.md'));
  const points = spec === null ? null : specStatPoints(spec);
  const state = statDesignState(points);
  if (state === 'na') rows.push('', `当前 §9.1.4 写的是「${points.na}」——核这条依据站得住。`);
  if (state === 'empty' || state === 'ready') {
    rows.push('', '当前 §9.1.4 的指标：',
      ...points.groups.map(g => `- ${g.title} —— 定义段：${g.lead ? '有' : '缺'}；统计点：${g.points.length} 个`));
  }
  return rows;
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
      ? `- 整章豁免：「${chapters.join('」「')}」；`
      : '- 没有整章豁免的章；',
    categories.length
      ? `- 决策议题豁免：类别为「${categories.join('」「')}」的那几条，`
        + 'review 里它们照原样写；'
      : '- 没有豁免的决策类别；',
    '- 引用上游规约的章节名不算——那是在指路，不是在用这个词；',
    '- 讲禁用词本身的地方不算（比如这一节）。');
  rows.push('', '数值怎么标来源、验收怎么接回规约，见 `author.md`。');
  return rows;
}

/**
 * 任务包正文。合同读不到就抛——任务包是它的投影，缺了没有可降级的形态，
 * 静默出一份缺了合同投影的任务包比报错更贵。
 */
function taskPackage(projectRoot, feature) {
  const contract = readJsonOrNull(path.join(SKILL_ROOT, 'contracts', 'story-chapters.json'));
  if (!contract) {
    throw new Error('章节合同读不到：任务包是它的投影，缺了就没有任务包');
  }

  const ctx = { projectRoot, featureRoot: featureRoot(projectRoot, feature), contract,
    args: { feature } };
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
    ...decisionSection(projectRoot, feature, contract),
    '',
    ...storyInputs(ctx, sourceStatus(ctx)),
    '',
    ...statDesignSection(projectRoot, feature),
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
