---
schema_version: "1.0.0"
feature: "home-page"
phase: "coding"
ready_to_produce: true
has_blocker_coverage_risk: false
key_inputs_read:
  - "doc/features/home-page/design.md — WalletMain Scope、F4/F5 Toast 语义、AC-G1 布局"
  - "doc/features/home-page/contracts.yaml — 组件、visual_parity、模块依赖 CommUI"
  - "doc/features/home-page/acceptance.yaml — AC-2/AC-7/AC-8/AC-9、AC-G1"
  - "doc/architecture.md + framework.config.json architecture — 层依赖与 cross_module_exports"
  - "framework/profiles/hmos-app/skills/3-coding/profile-addendum.md — ArkTS、资源、页面注册"
  - "02-Feature/WalletMain oh-package.json5 / module.json5 / resources/base/element/string.json — 依赖与字符串表"
  - "02-Feature/WalletMain HomeTabPage / ServiceGridSwiper / PromoSwiper — 现有实现与缺口"
subagents_used: "not_available"
searches_performed_estimate: 4
files_inspected_count: 12
---

## 探索预算与检索

- `contracts.yaml` + `design.md`：确认仅改 `WalletMain`；宫格用「暂不支持」类、活动卡用「暂无详情」类 Toast。
- `grep showToast|not_supported`：定位 `PromoSwiper` 误用通用 `not_supported`。
- `HomeTabPage`：标题栏 `+` 为硬编码，需迁 `string.json`。

## 已检视文件与原因

| 路径（相对仓库根） | 为何读 |
|-------------------|--------|
| doc/features/home-page/design.md | F4/F5、路由表 |
| doc/features/home-page/contracts.yaml | 契约与可测项 |
| doc/features/home-page/acceptance.yaml | 验收与 AC-G1 |
| 02-Feature/WalletMain/.../HomeTabPage.ets | 标题栏与 Scroll 结构 |
| 02-Feature/WalletMain/.../PromoSwiper.ets | F5 Toast |
| 02-Feature/WalletMain/.../ServiceGridSwiper.ets | F4 Toast（保持 not_supported） |
| 02-Feature/WalletMain/.../resources/base/element/string.json | 新增活动卡文案键 |

## 关键结论（支撑本阶段产出）

- `ServiceGridSwiper` 已使用 `app.string.not_supported`（「暂不支持」），符合 PRD F4。
- `PromoSwiper` 须改为独立资源键「暂无详情」，与 PRD F5 / design v1.3 区分宫格与活动卡语义。
- `HomeTabPage` 加号字符迁入 `string.json`，消除 UI 硬编码。

## 覆盖风险（诚实声明）

| 风险 | 处理 |
|------|------|
| 未改 Phone 壳层导航 | design Scope 外，本需求不要求 |

## 进入产出

`ready_to_produce: true`，开始修改 `WalletMain` 资源与 `.ets`。
