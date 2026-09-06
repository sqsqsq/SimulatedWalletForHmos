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
import { spawnSync } from 'node:child_process';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { featureRoot, readJsonOrNull, relDisplay } from '../shared/paths.mjs';
import { activeKnowledge } from '../shared/knowledge.mjs';
import { clientVocabulary } from '../../skills/story/scripts/lint-rules.mjs';
import { carryableBlock, DECISION_FIELDS, diagramsOf, diagramTopic, relFromStory }
  from '../../skills/story/scripts/story-build.mjs';

const SELF = 'doc/extensions/hooks/spec/author.md';
const SKILL_ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'skills', 'story');

/**
 * 位置从 `story_flow.py status` 来，本文件不自己算一遍。
 *
 * 算两遍就会有两个答案——流程往前走一步，谁先过期都说不准。调不通时如实说「跑这条命令」，
 * 而不是退回自己判断。
 */
function flowStatus(projectRoot, feature) {
  const script = path.join(SKILL_ROOT, 'scripts', 'story_flow.py');
  for (const exe of ['python', 'python3']) {
    const r = spawnSync(exe, [script, 'status', '--feature', feature],
      { cwd: projectRoot, encoding: 'utf-8', timeout: 20000, windowsHide: true });
    if (r.status === 0 && r.stdout) {
      try {
        return JSON.parse(r.stdout);
      } catch { /* 输出不是 JSON 就当没拿到 */ }
    }
  }
  return null;
}

function positionSection(projectRoot, feature) {
  const status = flowStatus(projectRoot, feature);
  if (!status || status.exists === false) {
    return ['## 1. 你现在在哪', '',
      `跑 \`python doc/extensions/skills/story/scripts/story_flow.py status --feature ${feature}\``
      + '：现在在哪、下一步跑什么、这一步要写的文件长什么样。'];
  }
  const rows = ['## 1. 你现在在哪', '', `**下一步**：${status.action}`];
  if (status.sidecar) {
    rows.push('', '这一步要写的文件形状：', '', '```json',
      JSON.stringify(status.sidecar, null, 2), '```');
  }
  return rows;
}

function knowledgeSection(projectRoot, feature) {
  const useFile = path.join(featureRoot(projectRoot, feature), 'spec', 'knowledge-use.yaml');
  const knowledge = activeKnowledge(projectRoot);
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
 */
function acceptanceKeys(useFile, projectRoot, feature) {
  const text = fs.existsSync(useFile) ? fs.readFileSync(useFile, 'utf-8') : '';
  const ids = [...text.matchAll(/^\s*-?\s*id:\s*(\S+)[\s\S]*?applicable:\s*true/gm)].map(m => m[1]);
  return [ids.length
    ? `判 \`applicable: true\` 的每一条，都要在 \`${acceptancePath(projectRoot, feature)}\` 有一条带 `
      + `\`knowledge_rule: <编号>\` 的 criteria。本轮已判 applicable：${ids.join('、')}。`
    : `判 \`applicable: true\` 的每一条，都要在 \`${acceptancePath(projectRoot, feature)}\` 有一条带 `
      + '`knowledge_rule: <编号>` 的 criteria——填完骨架再回头对一遍。',
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

function imageSection(projectRoot, feature) {
  const materials = readJsonOrNull(path.join(featureRoot(projectRoot, feature),
    'AR', 'story-src', 'materials.json'));
  const images = (materials?.materials ?? materials?.items ?? [])
    .filter(m => String(m?.kind ?? '').includes('image'));
  const rows = ['## 4. 材料里的图', ''];
  if (!images.length) {
    rows.push('材料清单里现在没有图片。');
    return rows;
  }
  rows.push('**单向**：属于本需求的图才进正文，先一句话说它画的是什么，再是图，图后接着讲；'
    + '**不属于本需求的不进正文**（旧版页面、同页面的另一张截图、同类产品的参考稿、'
    + '别的部件或别的单的页面），只在附录材料清单那一行写「未引用：<为什么不属于本需求>」。'
    + '引进正文再在图题里解释不算——读者要在归档件里读到不属于这个需求的页面。',
    '**引用串原样粘**——路径是相对 `AR/story.md` 的，自己拼容易少一层 `../`：', '');
  for (const img of images) {
    const paths = Array.isArray(img.paths) ? img.paths : [img.path].filter(Boolean);
    const caption = img.caption || '';
    for (const p of paths) {
      rows.push(`- \`![${caption || '这张图是什么'}](${relFromStory(p)})\``
        + (caption ? '' : ' ← **没有说明**：跑 `import_sources.py --caption-image` 补一句'));
    }
  }
  return rows;
}

/**
 * 上游某一份文档里的图 —— 逐张给主题与可粘贴的围栏，**不指定放哪一节**。
 *
 * 图属于哪块内容，内容在下游落在哪，图就该在哪。所以这里只把「有哪几张、
 * 各讲什么、原文长什么样」摆出来，归位由作者按内容判。
 * 文字不搬：每一环讲的事情不同，spec 讲给下游的是契约，story 讲给评审者的是来龙去脉。
 *
 * 上游两份各一节，同一个渲染。**下游都是 story**：spec 的内容归框架管，
 * 扩展不往那边搬图；系统设计与 spec 画过的图，作者按内容归位进 story。
 */
function diagramSection(heading, label, source, downstream) {
  const list = diagramsOf(source);
  const rows = [heading, ''];
  if (!list.length) {
    rows.push(`${label} 里现在没有图。`);
    return rows;
  }
  rows.push(`每一张都要在 ${downstream} 里出现一次，放哪一节按它讲的内容定——`
    + '**开头那行来源标记原样保留**，机器核的就是它。周围的文字自己写。',
    '两节列的是同一张图时（系统设计画过、spec 的流程图就是它），'
    + `${downstream} 里只放一张，两行标记都写在这个围栏开头。`, '');
  for (const d of list) {
    rows.push(`- **${label} ${d.id}**（${diagramTopic(d)}）`, '',
      carryableBlock(d, label), '');
  }
  return rows;
}

/** 上游与本阶段产物的正文；读不到就是空，不猜。 */
function docText(projectRoot, feature, ...rel) {
  const abs = path.join(featureRoot(projectRoot, feature), ...rel);
  return fs.existsSync(abs) ? fs.readFileSync(abs, 'utf-8') : '';
}

function chapterSection(contract) {
  const rows = ['## 5. 十章各回答读者什么', ''];
  for (const c of contract.chapters ?? []) {
    rows.push(`- **${c.title}**：${(c.questions ?? []).join('；')}`);
    if (c.form?.note) rows.push(`  - 主要用什么写：${c.form.note}`);
    for (const [at, cols] of Object.entries(c.form?.tables ?? {})) {
      const where = at === '' ? '这一章' : at === '*' ? '每个小节' : `「${at}」`;
      for (const one of String(cols).split(';')) {
        rows.push(`  - 机器核：${where}要有一张表`
          + (one ? `，表头含「${one.split('|').join('」「')}」` : ''));
      }
    }
  }
  rows.push('', '**在章草稿上写**：`AR/story-src/drafts/NN-<章名>.md`，'
    + '形态说明、槽位表头、术语起始行、spec §5 的图都已经在里面；'
    + '写完 `story-build chapter --chapter <章名> --from <草稿>` 落盘。',
    '附录的接口、数据·配置·事件、改动边界、规约判定四节不用你写——'
    + '它们是 spec §9 与 knowledge-use.yaml 的投影，要改改真源。');
  return rows;
}

/**
 * 禁用词：词表 + **在哪不算**。
 *
 * 词表一直在这里；缺的是作用域——哪几章整章豁免、review 的哪几类议题豁免、
 * 哪几种语境下同一个词不算。这三样此前只写在脚本注释与合同 note 里，
 * 于是作者为了确认「我这句算不算」去读判定脚本。豁免从合同渲染，不另立一份。
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
    ...diagramSection('## 4b. 系统设计里的图（搬进 story）', 'SR',
      docText(projectRoot, feature, 'SR', 'design.md'), 'story'),
    '',
    ...diagramSection('## 4c. spec 里的图（搬进 story）', 'spec',
      docText(projectRoot, feature, 'spec', 'spec.md'), 'story'),
    '',
    ...chapterSection(contract),
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
