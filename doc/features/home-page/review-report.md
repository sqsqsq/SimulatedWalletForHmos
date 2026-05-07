# Code Review 报告 — home-page

> **模块标识**: `home-page`
> **审查日期**: 2026-05-07
> **审查版本**: v1.2
> **审查人**: AI Code Reviewer
> **对应设计文档**: `doc/features/home-page/design.md`（v1.2）
> **脚本参考**: `harness-runner.ts --phase coding --feature home-page`（最近一次：0 BLOCKER，1×MAJOR WARN `index.ets` 命名）

---

## 一、审查范围

### 审查模块

| 模块名 | 所属层 | 格式 | 审查文件数 |
|--------|--------|------|------------|
| WalletMain | 02-Feature | HAR | 20 |

### 文件范围

基于 `doc/features/home-page/contracts.yaml` → `files`，共 **20** 个 `.ets` 源文件。本轮**重点走查**首页链路与本次变更：

- `02-Feature/WalletMain/src/main/ets/presentation/pages/HomeTabPage.ets`（空数据时条件渲染宫格/轮播）
- `02-Feature/WalletMain/src/main/ets/data/repository/HomeRepository.ets`（Mock 文案资源化）
- `02-Feature/WalletMain/src/main/ets/presentation/components/CardGuideSection.ets`
- `02-Feature/WalletMain/src/main/ets/presentation/components/ServiceGridSwiper.ets`
- `02-Feature/WalletMain/src/main/ets/presentation/components/PromoSwiper.ets`
- `02-Feature/WalletMain/src/main/ets/data/model/ServiceEntry.ets`、`PromoInfo.ets`

其余 `contracts.files` 条目与卡包/「我的」等页面仅做 import/分层与存在性核对，无新增业务变更。

---

## 二、审查方法

| 审查维度 | 依据文档 | 检查要点 |
|----------|----------|----------|
| 架构合规性 | `coding-rules.yaml`，`doc/architecture.md` | WalletMain 仅依赖 CommUI/CommFunc；无逆向 01-Product |
| 接口一致性 | `contracts.yaml` | `ServiceEntry`/`PromoInfo` 字段；`HomeRepository` 异步方法；组件 `@Prop`/`@State` |
| 编码规范 | `coding-rules.yaml` | `$r()` 资源、`any`、async/await、`void` on fire-and-forget |
| 业务与验收 | `design.md`，`acceptance.yaml`，`PRD.md`（§5/AC） | 标题资源 key、栅格 3×1、轮播 autoPlay+indicator；E2 空数据 |
| 自动化 | 最近 **coding** harness 报告 | 与 `diff_within_scope`、资源类 SKIP 交叉核对 |

---

## 三、问题清单

| 编号 | 严重程度 | 分类 | 问题描述 | 涉及文件 | 修复建议 |
|------|----------|------|----------|----------|----------|
| CR-001 | INFO | 命名规范 | `harness check-coding` 对 `index.ets` 报 **naming_conventions**（非 PascalCase 文件名）。HarmonyOS HAR **模块出口惯例**即为 `index.ets`，与「组件 PascalCase」字面规则存在张力，**不构成可执行缺陷**。 | `02-Feature/WalletMain/src/main/ets/index.ets` | 保持出口文件名；若要消 WARN，应在 **framework** 对 HAR `index.ets` 白名单化（对齐 `coding-rules.yaml: naming_conventions`）。 |
| CR-002 | INFO | 异常处理 | `HomeTabPage` 中 `navPathStack.pushPath`（约第 55、70 行）在宿主未注入栈时可能异常；`acceptance.yaml` 边界 **BD-3** 描述「极端无导航上下文」。当前 **Phone** 正常嵌入时无问题。 | `02-Feature/WalletMain/src/main/ets/presentation/pages/HomeTabPage.ets` | 可选：在 `pushPath` 外包一层 `try/catch` 或对栈做存在性判断失败后 `showToast`；**不修改** `Phone` 模块前提下完成。 |

**v1.0 报告已关闭项（证据复核）**：

- 原 **CR-001（Mock 中文硬编码）** 已不成立：`HomeRepository` 中展示字段均通过 `$r('app.string.*')` 引用（见该文件第 8–28 行）。
- **空列表展示**：`HomeTabPage` 已在 `services.length > 0` / `promos.length > 0` 条件下渲染 `ServiceGridSwiper`/`PromoSwiper`，与 PRD E2「宫格/轮播不展示或占位」一致。

---

## 四、问题统计

本段与「问题清单」表内计数一致：**BLOCKER 0**，**MAJOR 0**，**MINOR 0**，**INFO 2**。

| 严重程度 | 数量 |
|----------|------|
| BLOCKER | 0 |
| MAJOR | 0 |
| MINOR | 0 |
| INFO | 2 |
| **合计** | **2** |

---

## 五、修复建议摘要

### BLOCKER 级（必须修复）

无。

### MAJOR 级（建议修复）

无。

### INFO 级（可选）

- **CR-001**：框架/实例层统一 HAR `index.ets` 命名规则与 harness 告警策略即可。
- **CR-002**：若要强化边界单测或满足 BD-3 字面「可 Toast」，再加防御性导航。

---

## 六、结论

**审查结论**: 通过

本轮无架构/契约/文件缺失类 **BLOCKER**，无 **MAJOR** 级代码问题；仅剩 **INFO** 级工程约定与可选健壮性说明。

**判定依据**:

- BLOCKER 数量: **0**（> 0 则不通过）
- MAJOR 数量: **0**（= 0 且本报告将「通过」与「有条件通过」按 Skill 模板：无 MAJOR 阻断项 → **通过**）

**下一步建议**:

- 可直接进入 **Skill 5（业务级 UT）**；若需物理闭环 **review** 阶段，再补 `harness-runner --phase review`、`verifier`、`trace` 与 `review/phase-completion-receipt.md`。
- 若后续修改 `HomeTabPage`/`HomeRepository`，对本报告「重点走查」文件做增量 CR 即可。
