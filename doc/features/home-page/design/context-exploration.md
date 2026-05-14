---
schema_version: "1.0.0"
feature: "home-page"
phase: "design"
ready_to_produce: true
has_blocker_coverage_risk: false
key_inputs_read:
  - "doc/features/home-page/PRD.md — PRD v1.4（Scope、F4/F5、AC-G1）"
  - "doc/features/home-page/acceptance.yaml — AC/BD 与 PRD 对齐"
  - "doc/architecture.md — WalletMain 外层与依赖"
  - "doc/module-catalog.yaml — WalletMain / Phone / CommUI 边界"
  - "framework.config.json — architecture 段、cross_module_exports_file"
  - "doc/features/home-page/design.md — 既有技术设计 v1.3 改版（对齐 PRD v1.4）"
  - "doc/features/home-page/contracts.yaml — 契约与 visual_parity_contract"
  - "build-profile.json5 — Phone / WalletMain srcPath"
subagents_used: "not_available"
searches_performed_estimate: 6
files_inspected_count: 8
---

## 探索预算与检索

- 关键词：`WalletMain`、`HomeTabPage`、`visual_parity`、`AC-G1`、`ref_home_no_card`
- 目录：`doc/features/home-page/`、`02-Feature/WalletMain/`（仅核对 design 已列路径是否与仓库一致）
- 目的：将 PRD v1.4 的交互与布局锚点沉淀进 design/contracts，不重扩 Scope。

## 已检视文件与原因

| 路径（相对仓库根） | 为何读 |
|-------------------|--------|
| doc/features/home-page/PRD.md | SSOT 需求与 Scope |
| doc/features/home-page/acceptance.yaml | 验收与 AC-G1 |
| doc/architecture.md | 模块与分层 |
| doc/module-catalog.yaml | 模块职责与易混点 |
| framework.config.json | DSL 依赖规则 |
| doc/features/home-page/design.md | 本轮 design **v1.3** 改版（对齐 PRD v1.4） |
| doc/features/home-page/contracts.yaml | 契约同步 |
| build-profile.json5 | 模块 srcPath 摘录核对 |

## 关键结论（支撑本阶段产出）

- **Scope**：继承 PRD，仍为仅 `WalletMain` in-scope；不发起扩展提议。
- **复杂度**：首页加载 + 占位交互，**不**新增 `use-cases.yaml`（不满足 Step 6.1 阈值）。
- **PRD v1.4 → design**：补充 F4/F5 默认 Toast/占位策略说明；`contracts.yaml` 的 `visual_parity_contract` 显式绑定 **AC-G1 + ref_home_no_card**。

## 覆盖风险（诚实声明）

| 风险 | 处理 |
|------|------|
| 未复核全部 `.ets` 字节级与设计一字不差 | 接受：设计描述与既有实现一致；若有漂移由 coding/review 捕获 |

## 进入产出

已更新 `design.md`、`contracts.yaml` 并将跑 `harness-runner --phase design --feature home-page`。
