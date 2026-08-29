---
description: 需求开发流程编排（story init / archive / restore / review / help）
argument-hint: <init|archive|restore|review|help> [AR]
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
| `review <AR>` | 「需求系统 Token」+「检视」 |
| `help` | **勿读 SKILL**——直接输出下方「工作流程」 |

`init` 的编号可以是 AR 单号，也可以是问题单号／工单号——按前缀自动分派，详见「初始化」章。

## 工作流程（/story help 直接输出本节）

按预期开发顺序：

| 顺序 | 命令 | 功能 |
|---|---|---|
| 1 | `/story init <编号>` | 起手：拉取／落盘 AR·SR·RR 需求资料，**随后由 SKILL 接管**，一路走到进入 `/spec` |
| 2 | `/spec` | 需求规格阶段（非 story 实现，流程必经）：一次 pass 产出三份产物并过闭环门禁 |
| 3 | `/story archive <AR>` | AR/story.md 作正文、AR/review.md 作附件，**两份**一并归档上传（自动备份；任一缺失或未过门禁即拒绝，不写工作区 AR/design.md） |
| 4 | `/story restore <AR>` | （可选）用备份回退 archive 的覆盖 |
| 5 | `/story review <AR>` | （可选）把评审人在系统上留下的反馈拉回 `AR/review.md`，据此修订 `spec/spec.md`；评审表态由人填，模型只做处置 |
| — | `/story help` | 输出本流程说明 |

`init` 之后不需要人再敲命令——中断后用
`python doc/extensions/skills/story/scripts/story_flow.py status --feature <编号>`
问「现在走到哪、下一步干什么」。
