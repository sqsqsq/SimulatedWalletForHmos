# 首页 feature · UX 参照索引（Visual Handoff）

> **入库说明**：本目录随 **sim-wallet 演示仓库**归档；真实工程常以 **`${UX_ROOT}`**（或 UNC / 门户链接）挂载 UX 包，且 `doc/features/` 默认 **`paths.docs_committed: false`** 不入主仓——参见 `framework/docs/visual-handoff-config-migration.md`。

本目录为 **home-page** PRD Visual Handoff 的权威引用之一：`authoritative_refs` 含本 **`README.md`** 与 **`ux-reference/` 目录**（`kind: screenshot_pack`）。单图 ID 见下表。
- **像素/走查真源**：以下 **相对路径均相对仓库根**，实现与 Code Review 应以本目录内文件为准；PRD / design 内 Markdown 插图仅供扫读。
- **命名**：建议保持 `序号.场景简述.扩展名`，新增截图时在本表追加一行。

## 归档文件一览

| ID | 文件（相对本目录） | 说明 | 与本需求关系 |
|----|-------------------|------|----------------|
| `ref_home_no_card` | `1.首页-无卡.jpg` | 首页 Tab、**无卡**/空卡引导态的全屏效果 | **主真源**：`HomeTabPage` 布局、标题栏、卡引导区、下方宫格与活动区整体关系 |
| `ref_mine_tab` | `2.我的.jpg` | 「我的」Tab 全屏效果 | **上下文参照**：底 Tab 与系统状态栏由 Phone 提供；本 feature 通常不直接改此屏，仅保持与主导航壳一致 |
| `ref_card_pack_empty` | `3.卡包-无卡.jpg` | 卡包、无卡态 | **跳转目标参照**：从首页点进卡包后的版式预期；实现以 `CardPackPage` 与现有契约为准 |
| `ref_add_card_entry` | `4.添卡入口.jpg` | 添卡入口相关界面 | **跳转目标参照**：标题栏「+」进入 `AddCardEntryPage` 的目标态 |
| `ref_manage_non_local_cards` | `5.管理非本机卡片.jpg` | 「管理非本机卡片」等相关界面 | **延伸流程参照**：是否与当前首页入口关联以 PRD AC 为准 |

## 实现与走查建议

1. **首页本体**：先对齐 `1.首页-无卡.jpg`；再对照 `contracts.yaml` 中 `visual_parity_contract`（标题资源、宫格列数、轮播行为等）。
2. **跨 Tab / 跨页面**：`2–5` 用于理解主导航与跳转结果；若 PRD scope 未包含对应页面修改，以**不破坏跳转与返回栈**为底线，版式以各页既有实现 + 截图为辅。
3. **更新流程**：新增或替换图片后，**同步更新上表**；若 Visual Handoff 需逐文件强绑定，可在 `PRD.md` 的 `authoritative_refs` 中为本目录或单文件增加独立 `id + path`（路径仍须为仓库内正斜杠）。

## 路径速查（供复制到 PRD / 脚本外说明）

```text
doc/features/home-page/ux-reference/README.md
doc/features/home-page/ux-reference/1.首页-无卡.jpg
doc/features/home-page/ux-reference/2.我的.jpg
doc/features/home-page/ux-reference/3.卡包-无卡.jpg
doc/features/home-page/ux-reference/4.添卡入口.jpg
doc/features/home-page/ux-reference/5.管理非本机卡片.jpg
```
