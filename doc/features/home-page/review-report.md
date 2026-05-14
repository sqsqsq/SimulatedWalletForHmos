# Code Review 报告 — home-page

> **模块标识**: `home-page`
> **审查日期**: 2026-05-14
> **审查版本**: v1.3
> **审查人**: AI Code Reviewer
> **对应设计文档**: `doc/features/home-page/design.md`（**v1.3**，对齐 PRD v1.4）
> **脚本参考**: `harness-runner.ts --phase coding --feature home-page`（最近一次：零 BLOCKER，`coding_compile` PASS）

---

## 一、审查范围

### 审查模块

| 模块名 | 所属层 | 格式 | 审查文件数 |
|--------|--------|------|------------|
| WalletMain | 02-Feature | HAR | 20 |

### 文件范围

基于 `doc/features/home-page/contracts.yaml` → `files`，共 **20** 个 `.ets` 源文件。本轮在 v1.2 基础上 **增量核对 Skill 3**（PRD F4/F5 Toast 分流、标题栏加号资源化），**精读**：

- `02-Feature/WalletMain/src/main/resources/base/element/string.json`（`home_promo_no_detail`、`home_title_add_action`）
- `02-Feature/WalletMain/src/main/ets/presentation/pages/HomeTabPage.ets`（`home_title_add_action`、布局顺序）
- `02-Feature/WalletMain/src/main/ets/presentation/components/PromoSwiper.ets`（活动卡 Toast → `home_promo_no_detail`）
- `02-Feature/WalletMain/src/main/ets/presentation/components/ServiceGridSwiper.ets`（宫格 Toast → `not_supported`）
- `02-Feature/WalletMain/src/main/ets/data/repository/HomeRepository.ets`、`ServiceEntry.ets`、`PromoInfo.ets`

其余 `contracts.files`（卡包 / 我的 Tab 等）维持 **存在性 + import 分层** 抽查，无新增业务变更需求。

---

## 二、审查方法

| 审查维度 | 依据文档 | 检查要点 |
|----------|----------|----------|
| 架构合规性 | `coding-rules.yaml`，`doc/architecture.md` | WalletMain → CommUI/CommFunc；禁止逆向依赖产品壳 |
| 接口一致性 | `contracts.yaml` | `ServiceEntry`/`PromoInfo`；`HomeRepository`；`@Prop`/`@State` |
| 编码规范 | `coding-rules.yaml` | `$r()`、`any`、async/await；**禁止 presentation 硬编码 UI 文案** |
| 业务与验收 | `design.md` v1.3，`acceptance.yaml`，PRD v1.4 | **F4/F5** Toast 语义分流；**AC-G1** 纵向顺序；栅格 3 列；轮播 autoPlay+indicator |
| 自动化 | 最近 **coding** harness | 与 `diff_within_scope`、编译结果交叉核对 |

---

## 三、问题清单

| 编号 | 严重程度 | 分类 | 问题描述 | 涉及文件 | 修复建议 |
|------|----------|------|----------|----------|----------|
| CR-001 | INFO | 命名规范 | `check-coding` 历史上对 HAR 出口 `index.ets` 曾报 **naming_conventions**（文件名非 PascalCase）。HarmonyOS **HAR main 惯例**即为 `index.ets`（或配置对齐之 exports），与字面「组件文件 PascalCase」存在张力，**非功能缺陷**。证据：`contracts.yaml` 声明 `index.ets`，工程 `oh-package.json5` `main` 与之对齐。 | `02-Feature/WalletMain/src/main/ets/index.ets` | 保持出口文件名；若需消脚本告警，应在 **framework** 侧对 HAR 出口文件白名单化（对应 `coding-rules.yaml: naming_conventions`）。 |
| CR-002 | INFO | 异常处理 | `HomeTabPage` 中 `navPathStack.pushPath`（约第 57、72 行）在宿主未注入有效 `NavPathStack` 时理论上可能异常；`acceptance.yaml` 边界 **BD-3** 描述极端无导航上下文。当前 **Phone** 嵌入路径下正常。 | `02-Feature/WalletMain/src/main/ets/presentation/pages/HomeTabPage.ets` | 可选：`pushPath` 外包 `try/catch` 失败则 `showToast`；**不调** `Phone` 模块前提下完成。 |

**v1.3 复核结论（原 CR 关闭 / 不升格）**：

- **F4/F5**：`ServiceGridSwiper` 使用 `$r('app.string.not_supported')`（「暂不支持」）；`PromoSwiper` 使用 `$r('app.string.home_promo_no_detail')`（「暂无详情」），与 `design.md` 路由/导航表（L190–191）及 PRD v1.4 一致，**不构成**硬编码或逻辑错误。
- **加号**：`HomeTabPage` 已改为 `$r('app.string.home_title_add_action')`，`string.json` 已定义，满足 **no_hardcoded_strings** 对标题区文案的要求。
- **Mock 资源化**：`HomeRepository` 展示字段仍以 `$r('app.string.*')` 引用，与 v1.2 审查结论一致。

---

## 四、问题统计

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

- **CR-001**：框架/实例统一 HAR 出口文件命名与 harness 策略。
- **CR-002**：若产品要强约束 BD-3「可 Toast」，可加固 `pushPath` 调用。

---

## 六、结论

**审查结论**: 通过

本轮 **零 BLOCKER / 零 MAJOR**；Skill 3 增量已与 **design v1.3 / PRD v1.4**（F4/F5 Toast 分流、标题栏资源化）对齐。剩余 2 条 **INFO** 为工程约定与可选健壮性，不阻断进入 UT。

**判定依据**:

- BLOCKER 数量: **0**
- MAJOR 数量: **0**

**下一步建议**:

- 可进入 **Skill 5（业务级 UT）**；若后续修改首页链路，对本报告「精读」文件做增量 CR 即可。
