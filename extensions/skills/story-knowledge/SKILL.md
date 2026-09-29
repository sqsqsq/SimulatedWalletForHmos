---
name: story-knowledge
description: 进入一个 Feature 阶段或蓝图设计动作之前，取当前动作的知识任务——激活知识原文、已成立的知识判断与义务、本次完成条件与缺口。
---

# story-knowledge — 动作前取知识任务

读者：进入 Feature 阶段或蓝图设计动作的主 agent。时机：阶段作业开始之前（Framework 按 manifest 的 phase_bindings 在每个 Feature 阶段前调用本 Skill）；蓝图的来源发现、设计与质询之前由发起设计的一方调用。

| 场景 | 命令 |
|---|---|
| Feature 阶段（spec / plan / coding / review / ut / testing） | `node doc/extensions/hooks/shared/knowledge-task.mjs --project-root <工程根> --feature <当前 Feature id> --action <当前阶段> --audience author` |
| 蓝图来源发现与设计 | `node doc/extensions/hooks/shared/knowledge-task.mjs --project-root <工程根> --blueprint <蓝图 id> --action discovery --audience author`（写设计时 `--action design`） |
| 蓝图独立质询 | `node doc/extensions/hooks/shared/knowledge-task.mjs --project-root <工程根> --blueprint <蓝图 id> --action questioning --audience reviewer` |

Feature id 与阶段取当前阶段上下文里 Framework 给出的原生值，蓝图 id 取本次设计请求里的值。

输出分六块。完整读完再动手：第 2 块是知识原文，第 3、4 块是已成立的判断与义务，第 5 块是本次完成条件，第 6 块的缺口交给其中写明的责任方。

退出 1 时 stderr 写明对象、缺口与责任，按它交给责任方或向人说明；退出 2 是参数或依赖问题，修正调用后重取。命令只读，判断与落点写在本动作自己的产物里。
