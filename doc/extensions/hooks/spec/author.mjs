/**
 * spec 阶段作者任务包 —— **生成，不索引**。
 *
 * 两轮实跑里，作者在这一段做的事有一半不是写需求：为弄清 `knowledge-use.yaml` 有哪些字段、
 * 「无候选」写成什么、决策登记要哪几个键、门禁会判什么，它切片读了 `story-build.mjs` 34 次、
 * `knowledge-use.mjs` 17 次、`story_flow.py` 9 次。这些答案全是确定的，而且早就在磁盘上——
 * 在合同里、在激活清单里、在流程契约里。缺的不是判据，是**送达**：作者动笔之前手上没有它们。
 *
 * 所以这一份不是又一页说明，是从那些真源渲染出来的任务包：位置从流程契约来，
 * 章节问题与词表从合同来，图片清单从材料真源来，条目从激活清单来。改真源，这里跟着变。
 *
 * 与 `author.md` 的分工：那一页写**原则**（为什么这么做、边界在哪），并且是
 * `context-exploration` 里 `key_inputs_read` 能逐字引用的那个坐标；这一份写**这一次要做什么**。
 */
import { spawnSync } from 'node:child_process';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { activeKnowledge } from '../shared/knowledge.mjs';
import { clientVocabulary } from '../../skills/story/scripts/lint-rules.mjs';

const SELF = 'doc/extensions/hooks/spec/author.md';
const SKILL_ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'skills', 'story');

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf-8'));
  } catch {
    return null;
  }
}

function featureRoot(projectRoot, feature) {
  const cfg = readJson(path.join(projectRoot, 'framework.config.json'));
  const dir = String(cfg?.paths?.features_dir ?? 'doc/features').trim() || 'doc/features';
  return path.join(projectRoot, ...dir.split('/').filter(Boolean), feature);
}

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
    return ['## 1. 你现在在哪',
      '',
      `跑 \`python ${path.posix.join('doc/extensions/skills/story/scripts', 'story_flow.py')} status --feature ${feature}\``
      + '，它回答三件事：现在在哪、下一步跑什么、这一步要写的侧车长什么样。'];
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
  const has = fs.existsSync(useFile);
  const knowledge = activeKnowledge(projectRoot);
  return ['## 2. 知识判断（`spec/knowledge-use.yaml`）',
    '',
    has
      ? '骨架已经在磁盘上了，逐条填 `applicable` 与依据即可。'
      : `第一步跑 \`node doc/extensions/hooks/shared/knowledge-use.mjs init --feature ${feature}\``
        + '——它按激活清单生成骨架，激活条目一条不落，你只填判断。',
    '',
    `本轮激活 **${knowledge.entries.length} 条**约束（域：${knowledge.prefixes.join('、')}）、`
    + `**${knowledge.facts.length} 份**项目知识、在册候选 ${knowledge.patternIds.join(' / ') || '（无）'}。`,
    '',
    '- 命中：写 `requirement`（本需求要做什么，写得下一个人照着能编码）+ `contract`（引 spec §9 登记的名字，没有留空串）；',
    '- 不命中：写 `reason`，要**可回查**——「本需求界面沿用现有样式，不新增控件类型」是依据，「不涉及」不是；',
    '- 整域都不命中：登记到 `constraint_domains`，域里只要有一条命中就改逐条登记；',
    '- `patterns` 只登记不选型（选型是 plan 的事）；这个单元没有合适候选时 `candidate` 写「无候选」四个字。',
    '',
    '填完跑 `knowledge-use.mjs render --feature <名>` —— spec 的 §10/§11 由它写，**那两章不手写**。'];
}

function decisionSection(contract) {
  const categories = (contract.decision_categories ?? []).map(c => c.key).filter(Boolean);
  return ['## 3. 决策登记（`AR/story-src/decisions.json`）',
    '',
    '每条六个键：`id`（D1、D2…）、`status`（`settled` 已定 / `open` 待定）、`category`、'
    + '`title`（一句话结论，不是议题名）、`clarification`、`decider`（谁拍的板）。',
    '',
    `\`category\` 取自合同：${categories.join('、')}。`,
    '',
    '`clarification` 三段式：**要定的事** → **根据** → **结论与影响**（`open` 的写**可选的做法**与**建议**）。',
    '根据要能回查到材料或人的原话；结论要写清对交付的影响。'];
}

function imageSection(projectRoot, feature) {
  const materials = readJson(path.join(featureRoot(projectRoot, feature),
    'AR', 'story-src', 'materials.json'));
  const images = (materials?.items ?? materials?.materials ?? [])
    .filter(m => String(m?.kind ?? '').includes('image'));
  const rows = ['## 4. 材料里的图', ''];
  if (!images.length) {
    rows.push('材料清单里现在没有图片。');
    return rows;
  }
  rows.push('清单里的每一张图，**要么在讲它的那一章引用，要么在附录材料清单那一行写明不引用的理由**。',
    '两轮实跑各丢过一次：一次主流程没画图，一次三张图一张没进正文。', '');
  for (const img of images) {
    const p = Array.isArray(img.paths) ? img.paths.join('、') : (img.path ?? '');
    rows.push(`- \`${p}\`：${img.caption || '**没有说明**——它是什么，登记时补一句'}`);
  }
  return rows;
}

function chapterSection(contract) {
  const rows = ['## 5. 十章各回答读者什么', '',
    '章不是填空题：这些问题是**读者会问的**，答完了这一章就成立。', ''];
  for (const c of contract.chapters ?? []) {
    rows.push(`- **${c.title}**：${(c.questions ?? []).join('；')}`);
  }
  rows.push('', '章文件**只放正文**，不带 `## 章名`、不带 H1 —— `chapter` 命令自己加标题。');
  return rows;
}

function writingSection() {
  const rows = ['## 6. 写字的三条硬规则', '',
    '**一、客户端语境**：这些是服务器侧词汇，单独使用也算——', ''];
  for (const { term, hint } of clientVocabulary()) rows.push(`- 「${term}」→ ${hint}`);
  rows.push('',
    '**二、数值要标来源**：阈值、时长、次数三选一标明——'
    + '`（上游约束：<文档名>）` / `（本工程设定，无上游依据）` / `（平台基线）`。'
    + '标「上游约束」时门禁会去 SR/RR 原文核对那个数值是否真的存在。',
    '',
    '**三、验收要接回规约**：`spec/acceptance.yaml` 里，每条命中的规约要有一条带 '
    + '`knowledge_rule: <编号>` 的验收条目——它是编码与真机测试认回规约的唯一桥。'
    + '命中集与桥接集不一致就是断链。');
  return rows;
}

function gateSection() {
  return ['## 7. 门禁会判什么', '',
    '- 三份产物齐备：`spec.md`、`AR/review.md`、`AR/story.md`，且叙事件已登记成文态；',
    '- `knowledge-use.yaml`：激活条目有没有漏判、编号与候选在不在册、命中有没有写要求、依据是不是「不涉及」、`manifest_digest` 与激活清单对不对得上；',
    '- §10/§11 的生成区在不在、与 YAML 一致不一致、章里还留没留旧手写表；',
    '- 全文三条红线：客户端语境词、文档坐标（`spec §x`、`见 A5` 这类——改写事物的名字）、数值来源；',
    '- §9 技术契约的小节齐不齐；术语映射表里 in_scope 的业务词有没有写「解释」；',
    '- story 前置流程契约收没收口、决策留没留痕。',
    '',
    '**报错会说缺什么、写到哪、怎么写**——不必去读脚本。'];
}

export default function authorContext(ctx) {
  const projectRoot = String(ctx?.projectRoot ?? process.cwd());
  const feature = String(ctx?.feature ?? '').trim();
  if (!feature) return { promptFragments: [] };

  const contract = readJson(path.join(SKILL_ROOT, 'contracts', 'story-chapters.json'));
  if (!contract) {
    return { ok: false, severityOverride: 'MAJOR', message: '章节合同读不到：任务包是它的投影，缺了就没有任务包' };
  }

  const rows = [
    '<!-- hook:on_context_load:extension:doc/extensions/hooks/spec/author.mjs -->',
    `# spec 阶段 · 本次任务包（${feature}）`,
    '',
    '**先登记这一行**：`context-exploration` 的 `key_inputs_read` 要含 '
    + `\`${SELF}\`——本任务包是它的展开，漏登记会红在覆盖度上。`,
    '',
    ...positionSection(projectRoot, feature),
    '',
    ...knowledgeSection(projectRoot, feature),
    '',
    ...decisionSection(contract),
    '',
    ...imageSection(projectRoot, feature),
    '',
    ...chapterSection(contract),
    '',
    ...writingSection(),
    '',
    ...gateSection(),
    '',
    '**verifier 只跑一次，而且在最后**：三份产物定稿、确定性门全绿之后再叫它；'
    + '之后不要再改产物——改了 subject 就换代，整份要重审。调用只带 request JSON，不用自由文本 resume。',
  ];
  return { promptFragments: [rows.join('\n')] };
}
