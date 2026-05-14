---
schema_version: "1.0.0"
feature: "home-page"
phase: "review"
ready_to_produce: true
has_blocker_coverage_risk: false
key_inputs_read:
  - "doc/features/home-page/contracts.yaml — WalletMain files、组件与 visual_parity"
  - "doc/features/home-page/acceptance.yaml — AC-G1、F4/F5、边界 BD"
  - "framework/specs/phase-rules/coding-rules.yaml — 分层、硬编码、资源（coding-rule）"
  - "doc/features/home-page/design.md — v1.3 路由表 F4/F5 Toast、组件树、Scope"
  - "doc/architecture.md — WalletMain 所在层与依赖"
  - "doc/features/home-page/review-report.md — 上一轮 CR 基线"
  - "02-Feature/WalletMain：HomeTabPage、PromoSwiper、ServiceGridSwiper、string.json（Skill 3 增量）"
subagents_used: "not_available"
searches_performed_estimate: 3
files_inspected_count: 18
---

## 探索预算与检索

- `contracts.yaml > files`：核对 20 个 `.ets` 存在性（脚本层已检）。
- 关键字：`home_promo_no_detail`、`not_supported`、`home_title_add_action`、`pushPath`。

## 已检视文件与原因

| 路径 | 为何读 |
|------|--------|
| doc/features/home-page/design.md | F4/F5、AC-G1、组件树 |
| framework/specs/phase-rules/coding-rules.yaml | 审查维度依据 |
| HomeTabPage.ets / PromoSwiper.ets / ServiceGridSwiper.ets | Skill 3 落地核对 |
| string.json | 新增文案键与 `$r` 一致性 |

## 关键结论

- 宫格 Toast 仍为 `not_supported`（暂不支持）；活动卡为 `home_promo_no_detail`（暂无详情），与 design L190–191 一致。
- 标题栏加号已资源化 `home_title_add_action`。
- 继承 v1.2 审查：`index.ets` 命名与 harness 张力、BD-3 `pushPath` 可选防御仍为 INFO 级观察。

## 覆盖风险

| 风险 | 处理 |
|------|------|
| 未逐行复读全部 20 个 `.ets` | contracts 非首页文件仅做分层/import 抽查；首页链路精读 |

## 进入产出

`ready_to_produce: true`，更新 `review-report.md` v1.3。
