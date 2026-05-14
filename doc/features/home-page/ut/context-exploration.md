---
schema_version: "1.0.0"
feature: "home-page"
phase: "ut"
ready_to_produce: true
has_blocker_coverage_risk: false
key_inputs_read:
  - "doc/features/home-page/PRD.md — F1/F6、AC 分层"
  - "doc/features/home-page/design.md — HomeRepository、无 use-cases"
  - "doc/features/home-page/contracts.yaml — HomeRepository、data_models"
  - "doc/features/home-page/acceptance.yaml — ut_layer unit/both：AC-1、AC-2；其余 device"
  - "doc/features/home-page/ut/testability-audit.md — L1 两条"
  - "doc/features/home-page/ut/mock-plan.yaml — HomeRepository presets"
  - "02-Feature/WalletMain/test/dag/home_page_ut.dag.yaml — linked_acceptance"
  - "02-Feature/WalletMain/src/ohosTest/ets/test/home_page_ut.test.ets、List.test.ets"
  - "framework/profiles/hmos-app/skills/5-business-ut/profile-addendum.md — Hypium 路径与 UI 禁入"
subagents_used: "not_available"
searches_performed_estimate: 2
files_inspected_count: 10
---

## 探索预算与检索

- 无 `use-cases.yaml` → **路径 B**：UT 仅锚定 `HomeRepository` + acceptance **AC-1**（both）、**AC-2**（unit）。
- 对照 profile：**禁止** UT import `$r` / `showToast` / ArkUI；现有 `home_page_ut.test.ets` 仅引用 `HomeRepository`。

## 已检视文件与原因

| 路径 | 为何读 |
|------|--------|
| acceptance.yaml | `ut_layer` 过滤 |
| HomeRepository.ets | 与 mock-plan / it() 一致性 |
| home_page_ut.test.ets | 断言与 AC 对齐 |

## 关键结论

- 本轮 **不修改** `src/main`：编码变更（Toast 文案键）未改变 Repository Mock 形状与条数，现有 2 个 `it()` 仍有效。
- device-only AC/BD 继续落在 **Skill 6** / `device-testing-todo.md`。

## 覆盖风险

| 风险 | 处理 |
|------|------|
| AC-1 标注 both 仅测数据层 | acceptance 已写明真机侧首次渲染归 device；UT 覆盖 ut_focus 中的 Repository 契约部分 |

## UT 规划清单（用户已口头确认「开始 ut」）

| it() | AC | 被测入口 | Spy | 核心断言 |
|------|-----|----------|-----|----------|
| [AC-1] … | AC-1 | `HomeRepository.get*` | 无（真实 Mock） | 非 null、length>0、id 存在 |
| [AC-2] … | AC-2 | 同上 | 无 | length≥1 且 =4/=2、字段齐全 |

将写入/沿用：`test/dag/home_page_ut.dag.yaml`、`src/ohosTest/ets/test/home_page_ut.test.ets`（本轮以跑通 harness 为准，不改业务源码）。
