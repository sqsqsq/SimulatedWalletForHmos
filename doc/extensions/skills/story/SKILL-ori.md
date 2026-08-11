---
name: story
description: 拉取 Story 设计文档 / 初始化 AR Story / 归档 AR Story / 恢复并归档。当用户提到"拉取story"、"初始化story"、"归档story"、"恢复story"、"story"时使用。
allowed-tools:
  - Bash(node doc/extensions/skills/story/scripts/story.js *)
  - Read
  - Glob
  - Write
  - Edit
---

# story

拉取 Story 设计文档 / 初始化 AR Story / 归档 AR Story / 恢复并归档。

## MCP Token

脚本调用 WiseDevOps MCP 需要 Token。按以下步骤获取：

### 步骤 1：脚本获取

```bash
node doc/extensions/skills/story/scripts/token.js
```

- exit 0：stdout 即为 token，传给后续 story.js 命令的 `<mcp-token>` 参数
- exit 1：进入步骤 2

### 步骤 2：模型获取

自动从 `~/.cac.json` 或 `~/.claude.json`（Windows: `%USERPROFILE%\.cac.json`）按当前工程路径读取，位置为 `projects.<工程路径>.mcpServers.requirement-mcp.headers.X-MCP-Token`。

若读取不到，须告知用户：

> 未找到 MCP Token，请在 `%USERPROFILE%\.cac.json` 中为当前工程添加配置：
> ```json
> {
>   "projects": {
>     "<当前工程路径>": {
>       "mcpServers": {
>         "requirement-mcp": {
>           "type": "http",
>           "url": "https://mcp.wisedevops.huawei.com/requirement/mcp",
>           "headers": { "X-MCP-Token": "<你的Token>" }
>         }
>       }
>     }
>   }
> }
> ```
> Token 获取：https://wisedevops.huawei.com/app/toolhub/tokenManagement

---

## 拉取

仅限 AR。自动拉取父 SR 和根 RR 数据。

```bash
node doc/extensions/skills/story/scripts/story.js fetch <AR编号> <mcp-token>
```

**输入**：AR 编号 + MCP Token

**概要**：拉取 AR 及父 SR、根 RR 的需求详情与设计文档；检测 AR 是否尚未编写

**输出**：

| 目录 | 文件 |
|------|------|
| `doc/features/ARXXXX/AR/` | `detail.json` + `design.md` + `template.md` |
| `doc/features/ARXXXX/SR/` | `detail.json` + `design.md` |
| `doc/features/ARXXXX/RR/` | `detail.json` + `prd.md` |

stdout JSON：`{"mode":"fetch","reqNo":"...","parentNo":"SR编号","rrNo":"RR编号","initNeeded":true|false,"success":true}`

**决策**：若 `initNeeded === true` → 生成 design.md（见「生成 design.md」章节）→ 调 AskUserQuestion 提示用户下一步（见「init 完成后提示」章节）

---

## 初始化

仅限 AR。无条件触发初始化。

```bash
node doc/extensions/skills/story/scripts/story.js init <AR编号> <mcp-token>
```

**输入**：AR 编号 + MCP Token

**概要**：执行 fetch + 无条件触发初始化

**输出**：同 fetch 产出 + stdout JSON `{"mode":"init","reqNo":"...","parentNo":"SR编号","rrNo":"RR编号","initNeeded":true,"success":true}`

**决策**：`initNeeded` 始终为 true → 生成 design.md（见「生成 design.md」章节）→ 调 AskUserQuestion 提示用户下一步（见「init 完成后提示」章节）

---

## 生成 design.md

从父 SR 设计文档 + 根 RR 产品文档 + AR 模板生成 AR 设计文档。

**输入**：
- `AR/template.md` — 模板骨架
- `SR/design.md` — 父 SR 设计内容
- `RR/prd.md` — 根 RR 产品需求文档
- [reference/ar-design-init.md](reference/ar-design-init.md) — 本部件声明 + SR→AR 提取规则

**输出**：`AR/design.md`

**提取规则摘要**（详见 [reference/ar-design-init.md](reference/ar-design-init.md)）：
- **本部件参与的部分直接继承**：业务场景定义、端到端方案设计、跨部件流程与交互约定、安全隐私、兼容性、DFX 等，凡本部件参与或需感知的内容均继承；其它部件内部实现细节不继承，仅保留接口契约与交互协议
- **本部件相关场景**提取到 AR，不涉及的标注"不涉及"
- **对外依赖**只保留本部件交互的部分
- design.md 头部插入部件声明块

---

## init 完成后提示

> **BLOCKER**：当 fetch（`initNeeded=true`）或 init 模式实际生成了 design.md 后，须调 **AskUserQuestion** 提示用户选择下一步（ad-hoc 交互，interaction-renderer §fallback）。若 fetch 模式 `initNeeded=false`，则不弹出提示。

选项：

| value | label | 说明 |
|-------|-------|------|
| `enter_spec` | 进入 spec 规格化 | 以 AR 编号为 feature 名，进入 `/spec` 阶段；spec 读取 `AR/design.md` + `RR/prd.md` 作为输入 |
| `pause` | 暂停 | design.md 已生成，暂不进入 spec |
| `other` | 其它 | 用户在对话中说明意图 |

同轮消息末尾附 portable 编号：

```
1=进入 spec 规格化  2=暂停  3=其它（说明）
```

用户选择「进入 spec 规格化」后，agent 以 AR 编号为参数进入 spec Skill（读 `framework/skills/feature/spec/SKILL.md`），feature 名即 AR 编号，spec 将从 `doc/features/<AR编号>/` 目录读取 `AR/design.md` 和 `RR/prd.md` 作为输入。

---

## 归档

仅限 AR。将本地 AR/design.md 归档到平台。

```bash
node doc/extensions/skills/story/scripts/story.js archive <AR编号> <mcp-token>
```

**输入**：AR 编号 + MCP Token

**概要**：归档 design.md 到平台；若 spec/spec.md 存在则替换 design.md 后归档；已基线自动取消

**输出**：stdout JSON `{"mode":"archive","reqNo":"...","archived":true|false,"backupPath":"...","verified":true|false,"success":true|false}`

---

## 恢复

仅限 AR。从最新备份恢复平台设计文档，本地 design.md 不变。

```bash
node doc/extensions/skills/story/scripts/story.js restore <AR编号> <mcp-token>
```

**输入**：AR 编号 + MCP Token

**概要**：从最近备份恢复平台版本；本地 design.md 不变

**输出**：stdout JSON `{"mode":"restore","reqNo":"...","restored":true|false,"verified":true|false,"success":true|false}`

---