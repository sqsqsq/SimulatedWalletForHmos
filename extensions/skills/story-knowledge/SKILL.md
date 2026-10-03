---
name: story-knowledge
description: 进入一个 Feature 阶段或蓝图设计动作之前，取当前动作的知识任务——激活知识原文、已成立的知识判断与义务、本次完成条件与缺口。
---

# story-knowledge — 动作前取知识任务

读者：进入 Feature 阶段或蓝图设计动作的主 agent。时机：阶段作业开始之前（manifest 的 phase_bindings 把本 Skill 登记在每个 Feature 阶段之前）；蓝图的来源发现与设计之前由设计作者调用；质询任务由主执行者取来交给隔离的质询者，由质询者完成质询。

| 场景 | 命令 |
|---|---|
| Feature 阶段（spec / plan / coding / review / ut / testing） | `node doc/extensions/hooks/shared/knowledge-task.mjs --project-root <工程根> --feature <当前 Feature id> --action <当前阶段> --audience author` |
| 蓝图来源发现与设计 | `node doc/extensions/hooks/shared/knowledge-task.mjs --project-root <工程根> --blueprint <蓝图 id> --action discovery --audience author`（写设计时 `--action design`） |
| 蓝图独立质询（主执行者取，交给隔离的质询者） | `node doc/extensions/hooks/shared/knowledge-task.mjs --project-root <工程根> --blueprint <蓝图 id> --action questioning --audience reviewer` |

Feature id 与阶段取当前阶段上下文里 Framework 给出的原生值，蓝图 id 取本次设计请求里的值。

输出分六块。完整读完再动手：第 2 块是知识原文，第 3、4 块是已成立的判断与义务，第 5 块是本次完成条件，第 6 块的缺口交给其中写明的责任方。

退出 1 时 stderr 写明对象、缺口与责任，按它交给责任方或向人说明；退出 2 是参数或依赖问题，修正调用后重取。命令只读，判断与落点写在本动作自己的产物里。

## 范围未冻结时

标题带「预览，执行范围未冻结」的任务只是预览：本阶段的原生输入还没确定，不拿它动笔。只是查看知识不等于获准开始阶段；已获准开始本阶段时按顺序做：

1. Feature 还没有范围候选：按 Framework 的 `framework/skills/reference/goal-mode-operations.md` 走原生 `goal-mode-entry --prepare-scope`，用真实需求与影响依据生成候选。
2. 候选可用：在 `framework/harness` 下用原生函数完成首阶段范围准备（机器写冻结记录，不手写）：

   ```
   node -e "require('ts-node').register({transpileOnly:true});const r=require('./scripts/utils/feature-execution-scope').ensureFeatureExecutionScopeFrozen({projectRoot:process.argv[1],frameworkRoot:process.argv[1]+'/framework',feature:process.argv[2]});console.log(JSON.stringify(r,null,1));process.exitCode=['frozen','reused'].includes(r.status)?0:1" <工程根> <Feature id>
   ```

3. 返回 `frozen` 或 `reused` 后重取本阶段任务，确认第 4 块的输入与义务再动笔。返回别的状态按其中 `checks` 的原因交回责任方，不绕过。

不为冻结提前跑整个阶段 harness。

## spec 的需求正文

无 run 的 spec 按范围候选记下的需求来源文件恢复原文并核对。候选是用 inline 需求生成的、没有来源文件时，任务退出 1 并说明缺口：带上与生成候选时同一份的原文重取，`--requirement-file <文件>` 或 `--requirement <原文>`。来源在冻结后变了会报 stale，交回范围负责方，不换一份需求顶上。
