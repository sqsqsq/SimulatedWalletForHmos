# Code Review 报告 — home-page

> **模块标识**: `home-page`
> **审查日期**: 2026-04-23
> **审查版本**: v1.0
> **审查人**: AI Code Reviewer
> **对应设计文档**: `doc/features/home-page/design.md`

---

## 一、审查范围

### 审查模块

| 模块名 | 所属层 | 格式 | 审查文件数 |
|--------|--------|------|------------|
| WalletMain | 02-Feature | HAR | 20 |

### 文件范围

基于 `doc/features/home-page/contracts.yaml` → `files` 列表，共 **20** 个 `.ets` 源文件（WalletMain 全量清单，含首页链路及同 HAR 内卡包/我的等页面，本次业务聚焦首页与 `HomeRepository`）。主要审阅路径：

- `02-Feature/WalletMain/src/main/ets/presentation/pages/HomeTabPage.ets`
- `02-Feature/WalletMain/src/main/ets/data/repository/HomeRepository.ets`
- `02-Feature/WalletMain/src/main/ets/presentation/components/CardGuideSection.ets`
- `02-Feature/WalletMain/src/main/ets/presentation/components/ServiceGridSwiper.ets`
- `02-Feature/WalletMain/src/main/ets/presentation/components/PromoSwiper.ets`
- `02-Feature/WalletMain/src/main/ets/data/model/ServiceEntry.ets`
- `02-Feature/WalletMain/src/main/ets/data/model/PromoInfo.ets`

完整列表与 `contracts.yaml` 一致，不重复粘贴。

---

## 二、审查方法

本次审查基于以下 Spec 与工程文档，按 Skill 4 维度执行：

| 审查维度 | 依据文档 | 检查要点 |
|----------|----------|----------|
| 架构合规性 | `framework/specs/phase-rules/coding-rules.yaml`，`doc/architecture.md` | 五层依赖、WalletMain 内 shared→data→presentation |
| 接口一致性 | `doc/features/home-page/contracts.yaml` | 模型字段、`HomeRepository` 方法、组件状态与事件 |
| 编码规范 | `coding-rules.yaml` | 硬编码、any、async/await |
| 业务与验收 | `doc/features/home-page/design.md`，`doc/features/home-page/acceptance.yaml` | 路由名、AC/边界、降级与 Toast |
| 自动化参考 | 最近一次 `harness-runner.ts --phase coding --feature home-page` 结果（0 BLOCKER） | 与脚本结论交叉核对 |

**人工阅读说明**：对 `HomeRepository` 中 Mock 文案、以及 `navPathStack` 使用处做走查，对照 PRD/acceptance 的「可观察反馈」「无导航上下文」等描述。

---

## 三、问题清单

| 编号 | 严重程度 | 分类 | 问题描述 | 涉及文件 | 修复建议 |
|------|----------|------|----------|----------|----------|
| CR-001 | MAJOR | 硬编码 | `HomeRepository` 中 Mock 的 `name`/`title`/`description` 等**用户可见**中文为字面量（如第 8–10、18–25 行附近），与 `coding-rules` 中「展示文案走资源」的 MAJOR 级期望不一致；后续多语言或换皮成本高。 | `02-Feature/WalletMain/src/main/ets/data/repository/HomeRepository.ets` | 将可展示串迁入 `WalletMain` 的 `string.json`（或 `shared/constant` 仅作 key 与 `$r` 组合），由 Repository 返回资源引用或经 `ResourceManager` 解析；至少保证与 `ServiceEntry.name` 等对外契约一致的展示路径。 |
| CR-002 | MINOR | 异常处理 | `HomeTabPage` 在标题栏与 `CardGuideSection` 回调中直接 `this.navPathStack.pushPath({ name: '...' })`，未对「无 `navPathStack` / 非预期宿主」做防御。acceptance `BD-3` 期望极端场景下不崩溃、可 Toast。 | `02-Feature/WalletMain/src/main/ets/presentation/pages/HomeTabPage.ets` | 在 `pushPath` 前增加轻量保护（如判断栈对象存在、或 `try/catch` 内 `showToast` 提示），与 `msg_center`/`home_data_unavailable` 同级的错误提示串；保持不改变 Phone 模块。 |

---

## 四、问题统计

本段与「问题清单」表内计数一致：BLOCKER **0** 项，MAJOR **1** 项，MINOR **1** 项，INFO **0** 项。

| 严重程度 | 数量 |
|----------|------|
| BLOCKER | 0 |
| MAJOR | 1 |
| MINOR | 1 |
| INFO | 0 |
| **合计** | **2** |

---

## 五、修复建议摘要

### BLOCKER 级

无。

### MAJOR 级

- **CR-001**：优先完成 `HomeRepository` 展示用字符串资源化（或等价的可配置 Mock），再进入 **Skill 5 UT** 的文案断言约定。

### MINOR 级

- **CR-002**：在 `HomeTabPage` 内为 `pushPath` 增加防护，满足 `BD-3` 的可测试性与健壮性，避免仅在开发自查阶段依赖「必在 Tab 内嵌」的隐含前提。

---

## 六、结论

**审查结论**: 有条件通过

**说明**: 无架构分层、接口签名或文件缺失等 BLOCKER；代码与 `harness` 编码阶段 **0 BLOCKER** 一致。存在 **1** 条 **MAJOR**（Mock 层硬编码可展示文案），按 Skill 4 规约为「有条件通过」；修复或经团队豁免后可视为完全通过。

**判定依据**:

- BLOCKER 数量: **0**（>0 则须为「不通过」）
- MAJOR 数量: **1**（BLOCKER=0 且 MAJOR>0 → **有条件通过**）

**下一步建议**:

- 若接受 MAJOR 技术债：可并行进入 **Skill 5（业务级 UT）**，但需在测试计划中注明「首页 Mock 文案」的维护策略。
- 若追求「结论：通过」：先落 CR-001（及可选 CR-002），再复跑本审查或仅走增量 CR。

---
