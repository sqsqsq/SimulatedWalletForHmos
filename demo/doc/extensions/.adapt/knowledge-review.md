# 独立知识审查报告（复审更新版）

- **目标工程根**：`e:\Project\SimulatedWalletForHmos\demo`
- **当前知识摘要（`knowledge.digest`）**：`sha256:8819050b79d94279`
- **审查执行体**：独立只读子代理（`71614c3c-2bcf-4369-9b2c-4ba8ca1a76da`）
- **检查需求**：
  - **正常需求**：在 `WalletMain` 新增一个异地卡管理入口页（需复用共享主题色与卡片容器组件、按规范记录日志/脱敏与埋点评估，并判断是否适用流程编排/页面交互模式）
  - **邻近条件变化需求**：仅在页面内加一个简单静态提示按钮
- **总体结论**：**接收（无 `FAIL`，`blocking: []`，`unreviewed: []`）**。本次复审已核对作者修订的三份知识文件（`event-tracking.md`、`page-interaction.md`、`decision-tree.md`），两项原 `blocking` 实质错误及 `decision-tree.md` 的 `WARN` 项均已按源码与规范修正；其余 10 份未改动知识保留原有审查结论（其中 4 份含非阻断 `WARN` 提示）。

---

## 一、独立判断（直接基于目标仓源码与架构文档）

### 1.1 正常需求独立判断

1. **模块归属与路由装配**：
   - 新增「异地卡管理入口页」属于钱包卡包业务功能页，应落在 `02-Feature/WalletMain`（`src/main/ets/presentation/pages/`），不得放入 `05-SystemBase/CommUI` 或 `01-Product/Phone`（依据：`demo/doc/architecture.md` 外层架构表与 `demo/doc/module-catalog.yaml`）。
   - **三处联动登记**：`02-Feature/WalletMain/src/main/module.json5` 未引用 `route_map.json`，实际路由由 `01-Product/Phone/src/main/ets/pages/index.ets` 的 `Navigation` + `navDestinationMap(name, _param)` 分发。因此新增页面必须完成：页面文件导出 `@Builder`、`02-Feature/WalletMain/src/main/ets/index.ets` 导出该 builder、`Phone/src/main/ets/pages/index.ets` 的 `navDestinationMap` 增加分支。二级 `NavDestination` 内通过 `@aspect/CommFunc` 的 `NavPathContext.stack()` 执行 `pushPath`/`pop()`（参见 `AddCardEntryPage.ets:88-90`、`CardPackPage.ets:38,51`、`NavPathContext.ets:8-21`）。
2. **共享主题色与卡片容器复用**：
   - `02-Feature/WalletMain/oh-package.json5` 已声明 `@aspect/CommUI`（`file:../../05-SystemBase/CommUI`）和 `@aspect/CommFunc`（`file:../../05-SystemBase/CommFunc`），严禁依赖 `01-Product/Phone`（`doc/architecture.md` 层间依赖表）。
   - **卡片容器**：从 `@aspect/CommUI`（`05-SystemBase/CommUI/src/main/ets/index.ets`）复用 `SectionCard`（`AddCardEntryPage.ets:2,36`、`CardPackPage.ets:2,58` 已采用）或 `MaisonListCard`（当前 `CommUI` 已导出但仓内尚无业务调用）。
   - **主题色**：`CommUI/src/main/resources/base/element/color.json` 定义了 `comm_primary_blue`、`comm_text_primary`、`comm_text_secondary`、`comm_bg_page`、`comm_bg_card`、`comm_tab_unselected`（供 `CommUI` 自身组件 `$r('app.color.comm_*')` 使用），`CommUI/src/main/ets/index.ets` 另导出静态 hex 常量 `CommColors`（仅含 `PRIMARY_BLUE`、`TEXT_PRIMARY` 两个常量，当前业务代码未调用）；`WalletMain` 当前页面（如 `AddCardEntryPage.ets:40,80`）使用模块自身 `02-Feature/WalletMain/src/main/resources/base/element/color.json` 的 `brand_primary`、`text_primary`、`bg_page` 等键。
   - **文案资源**：`02-Feature/WalletMain/src/main/resources/base/element/string.json` 已有 `manage_non_local`（"管理非本机卡片"）、`non_local_cards`（"非本机卡片"）、`manage_sheet_empty_text`（"暂无非本机卡片"）；当前 `WalletMain` 仅存在 `base/` 资源目录，无 `en_US/` 或 `zh_CN/` 目录。
3. **日志、脱敏、权限与数据源现状**：
   - `01-Product/Phone/src/main/module.json5` 仅注册 `PhoneAbility`（`exported: true`）与 `PhoneBackupAbility`（`type: "backup"`, `exported: false`），**无任何 `requestPermissions` 声明**；仓内无网络/HTTP/NFC/蓝牙/穿戴远程管理真实代码，`CardRepository.getNonLocalCardCount()` 当前仅返回静态 `0`（`CardRepository.ets:46-48`），`ManageNonLocalSheet.ets` 为空态占位半模态。
   - `05-SystemBase/CommFunc/src/main/ets/index.ets` 导出 `Logger`（封装 `hilog`、`DOMAIN = 0xD001000`）与 `MaskUtil`（`maskPhone` 长度 `<=7` 原样返回、`maskAccount` 长度 `<=4` 原样返回），但当前 `WalletMain` 中尚无调用方（`PhoneAbility.ets` 直接调 `hilog`，`AccountService.ets:50` 硬编码脱敏串 `'*****6790@**.com'`）。若异地卡管理入口页涉及卡号/账号等敏感字段的展示或日志输出，须在进入日志/UI 前用 `MaskUtil`（短标识另行处理）；若需求需真实远端协议、持久化或系统权限，仓内无现成受保护持久化与权限声明，须先核对需求真源并列明缺口。
4. **埋点评估**：
   - `05-SystemBase/CommFunc/src/main/ets/shared/ha/` 导出 `WalletHAManager`、`WalletHAEventID`（当前仅 `Wallet_COMMON`）、`WalletFuncResult`、`WalletHAReportForChartCBuilder`、`WalletHAReportForVOCBuilder`，仓内尚无流程/步骤/内码登记文件，业务代码无任何 `WalletHAManager` 调用。
   - **源码关键事实**：`WalletHAReportForChartCBuilder.ets:13-25` 中，`eventID`（`Wallet_COMMON`）传入 `hiAppEvent.write({ name: this.eventID })`，而上报参数 `WalletEventID` 拼装为 `` `${this.funcIDValue}_${this.subFuncIDValue}` ``（即 `FuncID_SubFuncID`，如 `001_002`，**不含 `Wallet_COMMON_` 前缀**）。
   - 若新增入口页仅承接静态入口跳转/展示既为空态的本地占位，不产生新的可度量业务结果，则不强行新增 Chart 埋点，仅按需使用 `Logger`；若包含具体业务操作并要求指标统计，则须按项目渠道定义补齐事件/内码常量。
5. **模式适用性（源码现状与信号）**：
   - 经全局检索，`01-Product`、`02-Feature`、`04-BusinessBase`、`05-SystemBase` 中**没有任何文件 import `'framework'` 或使用 `DecisionTree` / `PageInteraction`**（仅 `WalletMain/oh-package.json5` 与 `Phone/oh-package.json5` 声明了 `framework` HAR 依赖）。
   - 单纯新增一个「异地卡管理入口页」（展示入口、拉起 `ManageNonLocalSheet` 或返回），既无多分支多步骤且各分支独立失败恢复的后台流程（不适用 `decision-tree`），也无业务结果驱动连续后继交互的复杂页内状态机（不适用 `page-interaction`）。

### 1.2 邻近条件变化需求独立判断（「仅在页面内加一个简单静态提示按钮」）

- 属于已有 `WalletMain` 页面内的局部 UI 改动，不新增路由或能力边界；复用 `CommUI` / `WalletMain` 颜色与 `string.json` 文案；无新业务结果故不做统计埋点与流程/页内编排（`decision-tree`、`page-interaction`、`event-tracking`、`OBS-*` 均不命中）；无敏感数据、无新增 IO/网络/IPC、无多入口重入风险（`DFX-01`、`COMPAT-*`、`ENV-*`、`DLV-02` 不命中；若新增文案键则命中 `RES-02`、`DFX-02`、`DLV-01`，UI 变动检查 `UX-01`）。

---

## 二、逐份复审与审查结论

### 本次修订文件复核（3 份）

1. **`knowledge/facts/event-tracking.md`**（`granularity: PASS` / `fact_use: PASS` / `duplication: PASS` / `coding_boundary: PASS`）
   - **复核结论**：§4 已修正为「`hiAppEvent.write` 的 `name` 为 `eventID`（如 `Wallet_COMMON`），参数 `WalletEventID` = `FuncID_SubFuncID`（如 `001_002`，不含 `eventID` 前缀，见 `WalletHAReportForChartCBuilder.ets`）」，与 `05-SystemBase/CommFunc/src/main/ets/shared/ha/WalletHAReportForChartCBuilder.ets:13-25` 源码完全一致。原 `blocking` 项已消除。

2. **`knowledge/design-patterns/page-interaction.md`**（`granularity: PASS` / `fact_use: PASS` / `duplication: PASS` / `coding_boundary: PASS`）
   - **复核结论**：§5 表头已标注「命名惯例（拟定）」；§9 已补正「当前仅 `02-Feature/WalletMain` 与 `01-Product/Phone` 的 `oh-package.json5` 声明了 `framework` HAR 依赖，全仓 `.ets` 源码尚无 `PageInteraction` 采用实例；仓内既有简单独立操作页面属于 §2 不适用范围而非反模式，新增复杂多步页内交互时按上篇信号决定是否采用」。不再存在无采用证据的模式断言，与 `knowledge-adaptation.md` 及仓内实况一致。原 `blocking` 项已消除。

3. **`knowledge/design-patterns/decision-tree.md`**（`granularity: PASS` / `fact_use: PASS` / `duplication: PASS` / `coding_boundary: PASS`）
   - **复核结论**：§5 表头已标注「命名惯例（拟定）」；§9 措辞已改为「仓内尚无采用该模式的存量实现」，消除了此前「存量开卡流程实现」的歧义表述，与仓内实际模块内容一致。原 `WARN` 已消除。

### 未改动文件保留结论（10 份）

4. **`knowledge/facts/component-profile.md`**（`granularity: PASS` / `fact_use: WARN` / `duplication: PASS` / `coding_boundary: PASS`）
   - §2 区分产品约定范围与源码现状、未虚构权限；保留原有非阻断 `WARN`（§2 援引 `doc/architecture.md` 无对应交互方条目、「产品范围约定」缺具名文档/责任方，且未说明各交互方谁决定最终结果）。
5. **`knowledge/facts/engineering-capabilities.md`**（`granularity: PASS` / `fact_use: WARN` / `duplication: PASS` / `coding_boundary: PASS`）
   - §6 准确核对 `CommUI` vs 模块私有 vs `Phone` 壳层边界；保留原有非阻断 `WARN`（未说明跨 HAR 不能在 `WalletMain` 直接引用 `app.color.comm_*`，亦未标注 `CommColors`/`ActionListItem`/`Maison*`/`Logger`/`MaskUtil` 在 `WalletMain` 尚无调用方）。
6. **`knowledge/constraints/ux-consistency.md`**（`granularity: PASS` / `fact_use: WARN` / `duplication: PASS` / `coding_boundary: WARN`）
   - 保留原有非阻断 `WARN`（未交代 `Phone` 有 `dark` 资源而 `WalletMain`/`CommUI` 缺深色与字体缩放依据；落法附注偏重 ArkUI 通用 API 写法）。
7. **`knowledge/constraints/security-privacy.md`**（全四维 `PASS`）
8. **`knowledge/constraints/dfx-baseline.md`**（全四维 `PASS`）
9. **`knowledge/constraints/observability.md`**（全四维 `PASS` — 五项独立义务 `OBS-02/03/05/06/07` 各自成立）
10. **`knowledge/constraints/resource-usage.md`**（`granularity: PASS` / `fact_use: WARN` / `duplication: PASS` / `coding_boundary: PASS`）
    - 保留原有非阻断 `WARN`（`RES-02` 要求「中英文齐备」但 `WalletMain` 与 `Phone` 当前均无 `en_US` 目录）。
11. **`knowledge/constraints/compatibility-checklist.md`**（全四维 `PASS`）
12. **`knowledge/constraints/env-exceptions.md`**（全四维 `PASS`）
13. **`knowledge/constraints/deliverables.md`**（全四维 `PASS`）

---

## 三、机器核对块

```yaml
knowledge_review:
  digest: "sha256:8819050b79d94279"
  executor: "independent-readonly-subagent (71614c3c-2bcf-4369-9b2c-4ba8ca1a76da)"
  files:
    - path: knowledge/facts/component-profile.md
      granularity:
        verdict: PASS
        evidence: "facts x facets 结构含 1. 部件申明 与 2. 交互方清单 两个分面，边界与职责清晰"
      fact_use:
        verdict: WARN
        evidence: "§2 逐行区分产品约定范围与源码现状（01-Product/Phone/src/main/module.json5 仅 PhoneAbility/PhoneBackupAbility，无权限及网络/NFC/穿戴源码），未虚构权限；但 §2 援引 doc/architecture.md 无对应内容、'产品范围约定'缺可核出处，且未说明各交互方谁决定最终结果"
      duplication:
        verdict: PASS
        evidence: "未复述 doc/architecture.md 层间表或 doc/module-catalog.yaml 模块职责"
      coding_boundary:
        verdict: PASS
        evidence: "全文仅部件边界与交互方事实，无编码或 lint 规范"
    - path: knowledge/facts/engineering-capabilities.md
      granularity:
        verdict: PASS
        evidence: "facts x facets 结构按能力拆为 7 个分面，无类内部调度细节"
      fact_use:
        verdict: WARN
        evidence: "§1 核实 Phone/src/main/ets/pages/index.ets navDestinationMap 与 WalletMain/module.json5 未引用 route_map.json；§5 核实 MaskUtil.ets(<=7/<=4)；§6 核实 CommUI/color.json、CommUI/index.ets、WalletMain/oh-package.json5 及 AddCardEntryPage.ets 引用 SectionCard，且依据 doc/architecture.md 正确排除 Phone 壳层。WARN：未说明跨 HAR 不能在 WalletMain 直接引用 app.color.comm_*（CommColors 仅含 2 常量且业务代码未用），亦未标注 CommColors/ActionListItem/Maison*/Logger/MaskUtil 在 WalletMain 尚无调用方"
      duplication:
        verdict: PASS
        evidence: "未与 event-tracking.md 或 constraints/ 重复"
      coding_boundary:
        verdict: PASS
        evidence: "仅写入口、资源位置、依赖与边界，无语言写法或 lint 规则"
    - path: knowledge/facts/event-tracking.md
      granularity:
        verdict: PASS
        evidence: "facts x halves 结构分上篇（统计设计）与下篇（结构与落地），层次清晰"
      fact_use:
        verdict: PASS
        evidence: "复审 §4（line 54）：已明确 hiAppEvent.write 的 name 为 eventID（如 Wallet_COMMON），参数 WalletEventID = FuncID_SubFuncID（如 001_002，不含 eventID 前缀），与 05-SystemBase/CommFunc/src/main/ets/shared/ha/WalletHAReportForChartCBuilder.ets:13-25 一致；VOC/Chart 区分及仓内零登记现状准确"
      duplication:
        verdict: PASS
        evidence: "与 observability.md 规约及 engineering-capabilities.md 分工清晰"
      coding_boundary:
        verdict: PASS
        evidence: "仅写协议映射、SDK 行为、角色骨架与拟定命名惯例，无编码风格规范"
    - path: knowledge/constraints/ux-consistency.md
      granularity:
        verdict: PASS
        evidence: "constraints x entries 结构仅 UX-01 一条归纳义务，粒度合适"
      fact_use:
        verdict: WARN
        evidence: "UX-01 区分模型静态检索与 setLanguage('ar') 实机走查；但未交代 Phone/src/main/resources/dark/element/color.json 与 PhoneAbility.ets:12 setColorMode(COLOR_MODE_NOT_SET) 已存在而 WalletMain/CommUI 缺深色资源及字体缩放依据的缺口"
      duplication:
        verdict: PASS
        evidence: "未与其他规约重复"
      coding_boundary:
        verdict: WARN
        evidence: "UX-01 属多语言 RTL 体验约束，但落法附注偏重 ArkUI 通用 API 写法（Position/Edges、Column.direction、TextAlign、Canvas），且仓内既有 AddCardEntryPage.ets:61 仍用 left/right"
    - path: knowledge/constraints/security-privacy.md
      granularity:
        verdict: PASS
        evidence: "按 knowledge-topics.md §5 将敏感数据四类处置归并为一条红线 SEC-01"
      fact_use:
        verdict: PASS
        evidence: "严格区分受权业务对端可识别身份与展示/日志脱敏、跨重启存储及缺依据列缺口，脱敏封装正确引向 engineering-capabilities.md §5"
      duplication:
        verdict: PASS
        evidence: "未重复 MaskUtil 实现细节"
      coding_boundary:
        verdict: PASS
        evidence: "聚焦数据流与合规义务，无编码规范"
    - path: knowledge/constraints/dfx-baseline.md
      granularity:
        verdict: PASS
        evidence: "constraints x entries 结构分 DFX-01（高频调用）与 DFX-02（ROM 增量），基线表保留待补充"
      fact_use:
        verdict: PASS
        evidence: "基线值严禁臆造数值；DFX-02 附注准确界定新增文案键 vs 复用键与量化责任时机"
      duplication:
        verdict: PASS
        evidence: "与 resource-usage.md 复用优先级不重复"
      coding_boundary:
        verdict: PASS
        evidence: "无编码或 lint 规范"
    - path: knowledge/constraints/observability.md
      granularity:
        verdict: PASS
        evidence: "domain: OBS 五项义务（OBS-02/03/05/06/07）分别对应定位记录、指标点覆盖、协议字段来源、编码兼容与 BI 授权依据，各自独立成立"
      fact_use:
        verdict: PASS
        evidence: "与 CommFunc/shared/ha/ 及 event-tracking.md 一致，命中条件、处置与模型/实机验法可落地（仅 OBS-02 '已有自动采集' 在仓内尚无实现，已在 event-tracking.md §3 交代）"
      duplication:
        verdict: PASS
        evidence: "只写规约义务，SDK 行为与字段定义正确交由 event-tracking.md"
      coding_boundary:
        verdict: PASS
        evidence: "探针语法符合 protocol.md §六，无编码风格规范"
    - path: knowledge/constraints/resource-usage.md
      granularity:
        verdict: PASS
        evidence: "domain: RES 含 RES-01（图片优先级与 10KB 上限）与 RES-02（字符串复用），粒度合适"
      fact_use:
        verdict: WARN
        evidence: "RES-01 明确 10KB 为工程设定值；但 RES-02 要求 '中英文齐备' 而 WalletMain 与 Phone 当前均无 en_US 资源目录（仅 base 与 Phone/zh_CN），未写明仓内缺口或目录落点"
      duplication:
        verdict: PASS
        evidence: "与 deliverables.md DLV-01 及 engineering-capabilities.md §6 分工明确"
      coding_boundary:
        verdict: PASS
        evidence: "属资源复用与定义规范，非语法 lint"
    - path: knowledge/constraints/compatibility-checklist.md
      granularity:
        verdict: PASS
        evidence: "COMPAT-01（结构变更）与 COMPAT-02（错误码兼容）两条覆盖变更触发点"
      fact_use:
        verdict: PASS
        evidence: "命中须指回具体变更项并逐问结论，未虚构仓内云接口或错误码表"
      duplication:
        verdict: PASS
        evidence: "翻译完整性正确交由 deliverables.md DLV-01"
      coding_boundary:
        verdict: PASS
        evidence: "无编码或 lint 规范"
    - path: knowledge/constraints/env-exceptions.md
      granularity:
        verdict: PASS
        evidence: "ENV-01（清缓存/数据恢复）与 ENV-02（防重入）两条跨需求环境异常"
      fact_use:
        verdict: PASS
        evidence: "区分预期/非预期/环境异常三类，命中条件与实机验法对新入口与静态按钮可准确分流"
      duplication:
        verdict: PASS
        evidence: "无跨文件重复"
      coding_boundary:
        verdict: PASS
        evidence: "无编码或 lint 规范"
    - path: knowledge/constraints/deliverables.md
      granularity:
        verdict: PASS
        evidence: "DLV-01（翻译闭环）与 DLV-02（对外开放面归档）两条交付义务"
      fact_use:
        verdict: PASS
        evidence: "正确界定'对外开放'边界（内部页与调云接口不命中）、待补充流程/位置诚实留空，DLV-02 正确采用（评审动作）+ 人工验证"
      duplication:
        verdict: PASS
        evidence: "与 RES-02 边界清楚"
      coding_boundary:
        verdict: PASS
        evidence: "非代码交付流程事项，无编码规范"
    - path: knowledge/design-patterns/decision-tree.md
      granularity:
        verdict: PASS
        evidence: "patterns x halves 结构完整，roles/coordinator_role 合法，上篇选型与下篇落地分离"
      fact_use:
        verdict: PASS
        evidence: "复审 §5（line 70）与 §9（line 157）：§4 与 DecisionTree.d.ets / StateMachine.d.ets 一致；§5 已标明'命名惯例（拟定）'；§9 已精确表述为'当前 02-Feature/WalletMain/oh-package.json5 已声明 framework HAR 依赖，仓内尚无采用该模式的存量实现'，无虚假存量暗示"
      duplication:
        verdict: PASS
        evidence: "与 page-interaction.md 后台分支编排 vs 页内交互编排分工明确"
      coding_boundary:
        verdict: PASS
        evidence: "聚焦模式结构与 SDK 运行时约束，无通用编码规范"
    - path: knowledge/design-patterns/page-interaction.md
      granularity:
        verdict: PASS
        evidence: "patterns x halves 结构完整，roles/coordinator_role 合法，上篇选型与下篇落地分离"
      fact_use:
        verdict: PASS
        evidence: "复审 §5（line 65）与 §9（line 144）：§4 与 PageInteraction.d.ets 一致；§5 已标明'命名惯例（拟定）'；§9 已明确声明仅 02-Feature/WalletMain 与 01-Product/Phone 的 oh-package.json5 声明了 framework HAR 依赖、全仓 .ets 源码尚无 PageInteraction 采用实例，且仓内既有简单独立操作页面属于 §2 不适用范围而非反模式"
      duplication:
        verdict: PASS
        evidence: "与 decision-tree.md 分工明确"
      coding_boundary:
        verdict: PASS
        evidence: "聚焦模式结构与 PageInteraction.d.ets 行为事实，无通用编码规范"
  blocking: []
  unreviewed: []
```
