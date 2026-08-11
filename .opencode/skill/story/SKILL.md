---
name: story
description: 需求开发流程编排——story init / archive / restore / help（完整定义见仓库 doc/extensions/skills/story/SKILL.md）
---

用法：`/story <init|archive|restore|help> [AR]`

## 命令转化

按用户指令**只读所需章节**（doc/extensions/skills/story/SKILL.md），不必通读全文。除 `help` 外，先读「MCP Token」章节获取 token：

| 指令 | 阅读章节 |
|---|---|
| `init <AR>` | 「MCP Token」+「初始化」 |
| `archive <AR>` | 「MCP Token」+「归档」（决策件未确认时另读 SKILL 的决策件定稿 Step 4） |
| `restore <AR>` | 「MCP Token」+「恢复」 |
| `help` | **勿读 SKILL**——直接输出下方「工作流程」 |

# 跳板文件

完整 Skill 定义：**[doc/extensions/skills/story/SKILL.md](../../../doc/extensions/skills/story/SKILL.md)**

## 工作流程（/story help 直接输出本节）

按预期开发顺序：

| 顺序 | 命令 | 功能 |
|---|---|---|
| 1 | `/story init <AR>` | 拉取 AR/SR/RR 需求资料并生成 AR/design.md（未存在时生成空模板，触发 AI 部件视角提取） |
| 2 | `/spec` | 需求规格（非 story 实现，流程必经）：一次 pass 产出三份——spec.md（代码要求，含 §9 技术契约）+ AR/story.md（评审叙事件，由 story-build scaffold → 逐章转写 → build 装配）+ AR/review.md（决策全景首版草稿，由 decisions.json 渲染）；闭环门禁校验三份齐备。人工审核与定稿属后续 `/story review` 职责，不在本阶段 |
| 3 | `/story archive <AR>` | AR/story.md 作正文、AR/review.md 作附件，**两份**一并归档上传（自动备份；任一缺失或未过门禁即拒绝，不写工作区 AR/design.md） |
| 4 | `/story restore <AR>` | （可选）用备份回退 archive 的覆盖 |
| — | `/story help` | 输出本流程说明 |
