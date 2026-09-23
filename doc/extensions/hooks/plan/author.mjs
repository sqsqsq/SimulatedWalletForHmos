/**
 * plan 阶段作者任务包 —— **本次要做什么**，从真源渲染。
 *
 * 与 `author.md` 的分工：那一页写原则与写法，这一份只出这一次的数据——命中哪几条规约、
 * 原文在哪、项目事实在哪、spec §9.4 写了什么、每个统计点要回答哪几问。
 * 数据来源与 spec 任务包相同：激活清单、`spec/knowledge-use.yaml` 与 spec 本身。
 *
 *     node doc/extensions/hooks/plan/author.mjs --feature <名>
 */
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { activeKnowledge } from '../shared/knowledge.mjs';
import { readUse, UseError } from '../shared/knowledge-use/document.mjs';
import { extensionRoot, featureRoot, readTextOrNull, relDisplay } from '../shared/paths.mjs';
import { specStatPoints } from '../shared/stat-points.mjs';

const SELF = 'doc/extensions/hooks/plan/author.md';
const TEMPLATE = 'doc/extensions/skills/story/templates/plan-sections.md';
//: 每个统计点要回答的几问：前五问与项目知识无关，最后一问只在项目知识定义了协议字段时才有。
const QUESTIONS = ['责任方法（决定这个结果的那个方法，写成契约里的「接口.方法」）', '本端取得结果的调用或查询',
  '去重（什么算同一次）与耗时起止', '验证：正常、失败及各实际结果各怎么核', '与 spec 这一行的结果逐一对应'];
const PROTOCOL = '项目知识定义的身份、编码、分类、外部错误码：给实际值，或写清缺哪一段、由谁按什么规则定';

function knowledgeSection(projectRoot, feature) {
  const knowledge = activeKnowledge(projectRoot);
  const where = f => `\`${relDisplay(projectRoot, path.join(extensionRoot(projectRoot), f.file))}\``;
  let hits = [];
  try {
    hits = readUse(projectRoot, feature).constraints.filter(r => r?.applicable === true && !r.waived)
      .map(r => String(r.id ?? '').trim());
  } catch (e) {
    if (!(e instanceof UseError)) throw e;
    return ['## 1. 命中的规约与项目事实', '', `读不到 spec 的知识判断：${e.message}——先回 spec 把它补上。`];
  }
  const files = knowledge.constraints.filter(c => c.entries.some(e => hits.includes(e.id)));
  return ['## 1. 命中的规约与项目事实', '',
    hits.length ? `spec 判命中 ${hits.length} 条：${hits.join('、')}。原文（含落法附注）在：` : 'spec 没有判命中的规约。',
    ...files.map(c => `- ${where(c)}——${c.title}`), '',
    knowledge.facts.length ? '项目事实（已有能力、登记位置、协议字段在这里找）：' : '激活清单里没有项目事实。',
    ...knowledge.facts.map(f => `- ${where(f)}`)];
}

function statPointSection(projectRoot, feature) {
  const spec = readTextOrNull(path.join(featureRoot(projectRoot, feature), 'spec', 'spec.md'));
  const points = spec === null ? null : specStatPoints(spec);
  const rows = ['## 2. 埋点：spec §9.4 与要逐点回答的几问', ''];
  if (!points) return [...rows, 'spec 没有埋点一节——先回 spec 补上，不涉及也要写一行「不涉及：<依据>」。'];
  rows.push('spec 原文：', '', '````markdown', points.text, '````', '');
  if (points.na || !points.groups.some(g => g.points.length)) {
    return [...rows, 'spec 写的是不涉及：plan 的埋点小节写一行「本需求不涉及：<依据>」。'];
  }
  rows.push(`形状见 \`${TEMPLATE}\` 的「埋点」小节。每个统计点回答：`, '');
  for (const g of points.groups) {
    rows.push(`**${g.title}**`, '');
    for (const p of g.points) rows.push(`- ${p}：${QUESTIONS.join('；')}；${PROTOCOL}`);
    rows.push('');
  }
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
