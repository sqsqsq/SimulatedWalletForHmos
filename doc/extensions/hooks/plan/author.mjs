/**
 * plan 阶段作者任务包 —— **本次要做什么**，从真源渲染。
 *
 * 与 `author.md` 的分工：那一页写原则与写法，这一份只出这一次的数据——命中哪几条规约、
 * 原文在哪、项目事实在哪、spec §9.4 写了什么、有哪些统计点；逐结果落实的作业只在 `author.md`。
 * 数据来源与 spec 任务包相同：激活清单、`spec/knowledge-use.yaml` 与 spec 本身。
 *
 *     node doc/extensions/hooks/plan/author.mjs --feature <名>
 */
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { activeKnowledge, knowledgeGuide } from '../shared/knowledge.mjs';
import { codeRequirementIds, readUse, UseError } from '../shared/knowledge-use/document.mjs';
import { extensionRoot, featureRoot, readTextOrNull, relDisplay } from '../shared/paths.mjs';
import { specStatPoints, statDesignState } from '../shared/stat-points.mjs';
import { isStoryFeature } from '../../skills/story/scripts/core/flow/check.mjs';

const SELF = 'doc/extensions/hooks/plan/author.md';
const TEMPLATE = 'doc/extensions/skills/story/templates/plan-sections.md';

function knowledgeSection(projectRoot, feature) {
  const knowledge = activeKnowledge(projectRoot);
  const where = f => `\`${relDisplay(projectRoot, path.join(extensionRoot(projectRoot), f.file))}\``;
  let hits = [];
  try {
    hits = codeRequirementIds(readUse(projectRoot, feature), knowledge);
  } catch (e) {
    if (!(e instanceof UseError)) throw e;
    return ['## 1. 命中的规约与项目事实', '', `读不到 spec 的知识判断：${e.message}——先回 spec 把它补上。`];
  }
  const files = knowledge.constraints.filter(c => c.entries.some(e => hits.includes(e.id)));
  return ['## 1. 命中的规约与项目事实', '',
    hits.length ? `spec 判命中 ${hits.length} 条：${hits.join('、')}。原文（含落法附注）在：` : 'spec 没有判命中的规约。',
    ...files.map(c => `- ${where(c)}——${c.title}`), '',
    ...knowledgeGuide(projectRoot, knowledge), '',
    '承接 spec 已判定的业务义务，按实现要的字段读相应知识；值仍缺依据时写清缺哪一项、影响哪几处设计。'];
}

function statPointSection(projectRoot, feature) {
  const dir = featureRoot(projectRoot, feature);
  const spec = readTextOrNull(path.join(dir, 'spec', 'spec.md'));
  const points = spec === null ? null : specStatPoints(spec);
  const state = statDesignState(points);
  const rows = ['## 2. 埋点：spec §9.4 的统计设计与逐结果落实', ''];
  if (state === 'missing') {
    return [...rows, isStoryFeature(dir) ? 'spec 没有埋点一节：上游没交出统计设计——先回 spec 补上，不涉及也要写一行「不涉及：<依据>」。'
      : '本需求没走 /story，spec 未提供统计设计：按本阶段原有要求设计，不另起埋点小节。'];
  }
  rows.push('spec 原文（指标、流程、步骤与业务结果都在这里，先通读）：', '', '````markdown', points.text, '````', '');
  if (state === 'na') return [...rows, 'spec 写的是不涉及：核这条依据站得住，plan 的埋点小节写一行「本需求不涉及：<依据>」。'];
  if (state === 'empty') return [...rows, 'spec 的埋点一节没有指标点位表：统计设计结构待补——先回 spec 在每个指标下补上带「统计点」列的表。'];
  rows.push(`按 \`${SELF}\`「四、埋点」的作业逐个业务结果落实，形状见 \`${TEMPLATE}\` 的「埋点」小节。各指标的统计点：`, '');
  for (const g of points.groups) rows.push(`- **${g.title}**：${g.points.join('、')}`);
  rows.push('', '动笔前：重读第 1 节知识清单里用途写到统计设计与上报的那份，读者含 plan 的下篇；不凭 spec 阶段的记忆写。',
    '每写完一行：按那一篇的使用约定与完成判断自查——项目规则算得出的字段都写成具体值，项目知识点名的角色在契约里都有承载它的实体与方法。',
    '项目规则算不出值的行才进「缺依据」，写明缺哪一项、影响哪几行；「xx」「待定」这类占位不是值。');
  return rows;
}

function main(argv) {
  const at = argv.indexOf('--feature');
  const feature = at >= 0 ? String(argv[at + 1] ?? '').trim() : '';
  if (!feature) {
    process.stderr.write('用法：node doc/extensions/hooks/plan/author.mjs --feature <名>\n');
    return 2;
  }
  const root = process.cwd();
  process.stdout.write([`# plan 阶段 · 本次任务包（${feature}）`, '',
    `\`context-exploration\` 的 \`key_inputs_read\` 要含 \`${SELF}\`——本任务包是它的展开。`, '',
    ...knowledgeSection(root, feature), '', ...statPointSection(root, feature), '',
    `契约挂法与「知识决策」章骨架见 \`${TEMPLATE}\`。`].join('\n') + '\n');
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
