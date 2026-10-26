/**
 * 蓝图独立质询的任务投影 —— 主执行者把候选交给宿主的隔离子代理质询，原样留下被评候选、任务与回复，
 * 设计负责方处理后写原生 `review_summary.questioning`。候选与回复的绑定和资格由原生执行合同定义，本模块给范围、原件位置
 * 与首读载体。
 *
 * 质询是同一个隔离执行体先首读再核源：首读载体只给当前人读稿、原生八问、阅读规则与之后要读的任务路径；
 * 来源、作者判断与原生质询范围都在任务里，答完八问才读。
 */
import * as crypto from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';

/** 这一轮交什么、原件建议放哪：范围取原生 requiredQuestioningScopes（`native` 是工程自己的 Framework），轮次取当前候选原始字节的摘要。 */
export function questioningRound(projectRoot, read, native) {
  const bytes = fs.readFileSync(path.join(projectRoot, ...read.canonical_path.split('/')));
  const dir = `${path.posix.dirname(read.canonical_path)}/questioning/${crypto.createHash('sha256').update(bytes).digest('hex').slice(0, 16)}`;
  const scopes = native.module('scripts/utils/blueprint-questioning.ts').requiredQuestioningScopes(read.blueprint);
  return { candidate: `${dir}/candidate.yaml`, reply: `${dir}/reply.md`, task: `${dir}/task.md`, scopes: [...scopes] };
}

//: 原生 P1 工作流里独立读者八问的出处：首读载体照它的原文转达，扩展不另存一份
const WORKFLOW = ['skills', 'reference', 'app-component-blueprint-workflow.md'];

/** 原生独立读者八问（工程自己的 Framework 的原文）；读不出八条按包坏了报。 */
export function nativeEightQuestions(native) {
  const file = path.join(native.frameworkRoot, ...WORKFLOW);
  const lines = fs.readFileSync(file, 'utf8').split(/\r?\n/);
  const at = lines.findIndex(l => l.includes('回答下列八问'));
  const questions = [];
  for (const line of lines.slice(at + 1)) {
    const hit = /^(\d+)\.\s+(.+)$/.exec(line.trim());
    if (hit) questions.push(hit[2]);
    else if (questions.length && line.trim()) break;
  }
  if (at < 0 || questions.length !== 8) {
    throw new Error(`Framework ${WORKFLOW.join('/')} 里读不出独立读者八问（读到 ${questions.length} 条）：首读载体照它转达，原文变了要先核原生质询流程`);
  }
  return questions;
}

/** 首读载体：主执行者原样作为隔离子代理的任务；只给人读稿、八问、阅读规则与之后读的任务路径。 */
export function firstReadCarrier({ draft, task, reply, questions }) {
  return ['# 蓝图独立质询 · 派审', '',
    `- 当前人读稿：\`${draft}\``,
    `- 答完八问之后读的质询任务：\`${task}\``, '',
    '你是与设计作者隔离的质询者，只读，不写任何文件；你的最终回复原样存到'
      + ` \`${reply}\`。不继承派你的会话里的 YAML、设计摘要或结论。`, '',
    '## 先首读', '',
    `先以不了解项目代码的评审人视角只读 \`${draft}\` 的首屏，复述现状、变化、结果与范围；再只看正文回答下面八问，`
      + '逐项指出答案所在章节和仍看不懂的位置。正文止于「技术与追溯参考」入口：八问答完之前不读同文档的参考区、YAML、需求原文或质询任务，'
      + '不用框架经验或作者口头解释替正文补全含义。', '',
    ...questions.map((q, i) => `${i + 1}. ${q}`), '',
    '## 再核源', '',
    `八问答完后读 \`${task}\`：按它列的来源、人签与原生质询范围，对照 canonical 蓝图与原件逐项核，回复要求见任务第 3 块。`
      + '八问的回答与核源结果写在同一份回复里。', ''].join('\n');
}
