---
description: 需求开发流程编排（story init / archive / restore / update / adapt / help）
argument-hint: <init|archive|restore|update|adapt|help> [AR|目标工程]
---

# /story — 需求开发流程编排

**用户输入**：$ARGUMENTS

## 命令转化

按用户指令**只读 [SKILL.md](../../doc/extensions/skills/story/SKILL.md) 的所需章节**，不必通读全文：

| 指令 | 阅读章节 |
|---|---|
| `init <编号>` | 「初始化」（`AR` 开头的还需先读「需求系统 Token」；非 `AR` 开头走本地起手，不需要 token） |
| `archive <AR>` | 「需求系统 Token」+「归档」 |
| `restore <AR>` | 「需求系统 Token」+「恢复」 |
| `update <编号>` | 「更新」（要从需求系统取新内容时还需先读「需求系统 Token」） |
| `adapt [<目标工程>]` | **改读** [story-adaptation/SKILL.md](../../doc/extensions/skills/story-adaptation/SKILL.md)（不读 story 的 SKILL）——把本扩展装到／升级到另一个工程，与需求流程无关 |
| `help` | 「链条」与「命令入口」——据它说明各命令做什么、按什么顺序用 |

`init` 的编号可以是 AR 单号，也可以是问题单号／工单号——按前缀自动分派，详见「初始化」章。
