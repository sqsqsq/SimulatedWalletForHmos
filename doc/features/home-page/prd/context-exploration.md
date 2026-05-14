---
schema_version: "1.0.0"
feature: "home-page"
phase: "prd"
ready_to_produce: true
has_blocker_coverage_risk: false
key_inputs_read:
  - "doc/glossary.yaml — glossary SSOT，对照 PRD 术语映射与正文用词"
  - "doc/module-catalog.yaml — module-catalog，Scope / WalletMain·Phone·CommUI·CommFunc·AccountManager"
  - "doc/architecture.md — architecture，外层依赖与模块边界核对"
  - "doc/features/home-page/PRD.md — PRD v1.3+ 基线（本轮后续升至 v1.4 文档质量修订）"
  - "doc/features/home-page/ux-reference/README.md — Visual Handoff 截图索引与 ID"
subagents_used: "not_available"
searches_performed_estimate: 8
files_inspected_count: 9
---

## 探索预算与检索

- 关键词：`WalletMain`、`Phone`、`screenshot_pack`、`home-page`、`visual_handoff`
- 目录：`doc/features/home-page/`、`framework/skills/1-prd-design/`、`framework/profiles/hmos-app/skills/1-prd-design/`
- 目的：确认 PRD 重跑不与 SSOT / strict Visual Handoff 冲突；术语 Scope 一致。

## 已检视文件与原因

| 路径（相对仓库根） | 为何读 |
|-------------------|--------|
| doc/module-catalog.yaml | Scope 模块名与术语权威模块合法性 |
| doc/glossary.yaml | 术语映射与 glossary 冲突门禁 |
| doc/architecture.md | 外层与 feature / product 边界 |
| doc/features/home-page/PRD.md | v1.3→v1.4 改版（Verifier WARN 清零类修订） |
| doc/features/home-page/acceptance.yaml | 与 AC 编号对齐（脚本主要从 PRD 抽追溯） |
| doc/features/home-page/ux-reference/README.md | authoritative_refs ID ↔ 文件名 |
| framework.config.json | `prd.visual_handoff_enforcement: strict`、`paths.docs_committed` |
| framework/skills/1-prd-design/SKILL.md | Step 1.5 / Context Gate / Harness 顺位 |
| framework/profiles/hmos-app/skills/1-prd-design/profile-addendum.md | ArkUI 用词与探索补充 |

## 关键结论（支撑本阶段产出）

- **Scope**：维持 `in_scope_modules: [WalletMain]`，`Phone`/`CommUI`/`CommFunc`/`AccountManager` 仍为 out-of-scope，仅消费能力。
- **像素真源**：`ux-reference/` + README 表；PRD 内嵌图非权威。
- **本轮增量**：用户要求「重跑 PRD」——在不重扩 Scope 前提下刷新文档版本与 Context Exploration 产物，并按 Skill 1 重跑 harness + verifier。**v1.4**：收紧 §3.2 主语、F4/F5 默认交互、AC-G1 绑定 `ref_home_no_card`。

## 覆盖风险（诚实声明）

| 风险 | 处理 |
|------|------|
| 未重新实拍截图 | 接受：仍以仓库既有 `.jpg` 为 Visual Handoff 权威 |

## 进入产出

`ready_to_produce: true`，已进入 PRD.md / acceptance.yaml 更新与 Harness。
