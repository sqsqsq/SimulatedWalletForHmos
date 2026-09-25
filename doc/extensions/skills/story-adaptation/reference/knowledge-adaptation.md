# 知识适配方法

> 读者：执行 `/story adapt` 的维护模型。时机：首次安装、升级或单独整理知识时，装完机制后按这里做知识部分。

## 目标

让目标仓的模型在各阶段拿到本项目该用的知识：写哪些、怎么写，从目标仓自己的代码、规范与业务出发决定，按 `skills/story/reference/knowledge/protocol.md` 写成模型能直接用的样子，并如实交回。安装脚本只写机制，知识由你写；目标有哪些知识、叫什么、分几份都归目标。

## 输入

| 读什么 | 拿什么 |
|---|---|
| 包的 `skills/story/reference/knowledge/protocol.md` | 三类知识怎样描述自己、共同写法与各类写法 |
| 目标的 `manifest.yaml > provides.knowledge` 与其中每个文件 | 已有知识 |
| 目标的代码、架构配置、模块画像、编码规范与业务说明 | 取证来源；已由它们承担的内容不进知识 |
| 安装脚本的输出 | 机制装没装成 |

## 步骤

1. **装机制**：跑 `adapt-scan --apply`，失败按它点名的原因处理。版本相同、没有机制要写时脚本退出 0，知识仍按下面核一遍。
2. **定读者要作的决定**：按各阶段看哪些决定离不开本项目知识——初析判断上游内容归不归本部件；spec 判规约命中、找可复用的已有能力、做专项设计（如统计设计）；plan 选模式、定实现与取值；coding 照项目约定落地；review 与测试核义务。挑一个正常需求作检查对象。加载器报出的问题一并列上。据此列出本次要新写或要重写的知识、各自回答什么，摆给人定一次范围；已有且可用的不动。
3. **取证并写**：
   - 查定义、实际调用、配置与业务协议，分清当前实现、已定规范、依据在别人手里的（写明向谁取得什么）；
   - 按 protocol 写：frontmatter 的 `applies_when` 写清何时读、回答什么；正文正向陈述有什么、怎么用；多步推导的照设计模式的篇与节写；
   - 同一内容只在一份里写；编码规范、架构配置已经写的不再写；包内示例知识只参考组织方式，内容以本仓为准；
   - 新文件写完整再加进 `provides.knowledge`；拆分、合并、改名时同步激活清单与引用，旧文件退出。
   - 遇到新的业务决定、事实冲突或超出已定范围，停下问具体问题。
4. **走查**：拿第 2 步的正常需求走一遍——读者能否据知识作出那些决定、给出下一步要的设计。缺依据补依据，缺用法补叙述或例子，真缺决定写待决。
5. **确认与交回**：跑 `adapt-scan --check`；再在目标工程根执行下面这段只读检查（交给 `node --input-type=module`），它按目标的 `paths.extension_dir` 加载激活知识并做结构自检，不需要需求编号、不写任何文件。两者分开报告；PASS 只证明能加载、结构成立。

   ```js
   import fs from 'node:fs';
   import path from 'node:path';
   import { pathToFileURL } from 'node:url';
   const root = process.cwd();
   const config = JSON.parse(fs.readFileSync(path.join(root, 'framework.config.json'), 'utf8'));
   const ext = path.resolve(root, config.paths?.extension_dir ?? 'doc/extensions');
   const api = await import(pathToFileURL(path.join(ext, 'hooks/shared/knowledge.mjs')).href);
   const k = api.activeKnowledge(root);
   const problems = api.selfCheck(root, k);
   if (problems.length) throw new Error(problems.join('\n'));
   console.log(JSON.stringify({ status: 'PASS', facts: k.facts.length, constraints: k.constraints.length, patterns: k.patterns.length }));
   ```

   出错时非零退出并带文件与原因；缺运行依赖按依赖提示处理，不算知识缺失。

## 完成条件

- 机制 `--check` 通过；激活知识全部能加载，每份都有说清问题的 `applies_when`。
- 人定范围内的知识写完，走查结论写明；依据在别人手里的写明向谁取得。

## 失败与中断

- 机制没装成：按脚本报错修机制，不动知识。
- 机制成功、知识部分完成：分开交回，不回滚机制，不笼统称升级完成。
- 中断后再做：从当前文件重新看，已完成的保留；优先恢复激活清单的可读性。
- 你的编辑与目标在途修改冲突：给出具体差异让人定。

## 交回

分别写：机制安装结果；每份新写或重写的知识回答什么、证据位置、走查结论、待向他人取得的依据；未做的及其影响到哪些阶段；剩余动作。

## 示例：后台任务通知（中性题材，路径与值均为示意）

目标是一个后台服务仓。它有一份 `knowledge/facts/services.md`，`applies_when` 只写了「always」，正文列着通知封装 `Notifier.send` 与重试策略。

- **定决定**：设计「发生某事后通知用户」的需求时，读者要写出调用入口、成功失败怎么判、失败后是否重试。
- **取证**：读 `Notifier.send` 定义与两处调用：返回投递回执，重试由封装按回执状态发起；取消后是否还通知，代码与需求都没有依据，需求负责人决定。
- **写**：`applies_when` 改为「需求要通知用户时：用哪个封装、怎样判成功与重试」；正文按「发送 → 判回执 → 重试」写用法，各带定义位置；取消一句写「取消后是否通知由需求负责人决定，设计时向其确认」。
- **走查**：拿「注册成功发通知」走一遍，读者写得出调用、判结果与重试；取消的处理在设计里列为待决。
- **交回**：`--check` 与只读检查 PASS；这份知识的改动、证据位置与走查结论；取消一项待负责人决定。
