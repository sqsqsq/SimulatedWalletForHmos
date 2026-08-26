---
name: codebase-facts
kind: facts
applies_when: always（凡需给出「代码库现状」这一半事实时）
---

# 工程取证事实登记

**这个工程各类能力的现状：有没有、长什么样、怎么认出来。** 先找下面的既有实现，照它写；
这里没有的能力再实扫仓。

**技术栈**：HarmonyOS 应用（ArkTS / ArkUI，hvigor 构建，模块级 `oh-package.json5`）。
公共能力模块 `CommFunc`（`05-SystemBase/CommFunc`）的对外符号一律从 `src/main/ets/index.ets` 导出。

## 1. 对外暴露面 — `confirmed: 已确认`

应用清单 `src/main/module.json5` 的 `abilities[]`（看 `exported` 与 `skills`）；页面路由注册表
`src/main/resources/base/profile/main_pages.json` 与 `route_map.json`；跨模块跳转统一走
`NavPathContext.stack().pushPath(...)`，导航栈由 `CommFunc` 的 `NavPathContext` 持有（`attach` / `stack`）。

## 2. 端云接口 — `confirmed: 已确认`

**无端云封装（已核对）**：`@ohos.net.http` / `http.createHttp` / `rcp` / `axios` 源码内均零命中，
数据来自本地仓储层，无网络出口。

## 3. 数据存储 — `confirmed: 已确认`

关系型持久化用 `relationalStore`（`@kit.ArkData`），封装在 Feature 模块的
`src/main/ets/data/local/*RdbHelper.ets`（持有单例 `RdbStore`，`StoreConfig` 带 `securityLevel`）；
内存态用 `AppStorage`，出现在 domain/service 层。**未使用** `preferences` 与 `distributedKVStore`。

## 4. 配置项 — `confirmed: 已确认`

常量开关在各模块 `src/main/ets/shared/constant/*Constants.ets` 中，形态为
`static readonly <NAME>: boolean`；同目录另有非布尔的业务常量，按类型区分。
**无远程配置封装（已核对）**：源码内无管理台/云侧下发开关。

## 5. 可观测性 — `confirmed: 已确认`

日志、VOC、Chart 三渠道齐备，都在 `CommFunc`，惯例如下：

- **日志** `Logger`（`shared/log/Logger.ets`，封装 `hilog`，`debug` / `info` / `error`）：本地调测与完整流程还原——
  流程每一步的进入与结果、分支走向、异常都记；不打敏感字段，确需记录先脱敏
  （哪些算敏感、脱到什么程度见安全隐私规约，脱敏入口见下面的敏感数据处理）。
- **VOC** 默认用门面 `WalletHAManager.logAndReport` / `logErrorAndReport` / `logDebugAndReport(eventID, desc)`
  （对应档日志 + 一条 VOC，一行搞定）；只在「只上报、不打日志」时用 `vocBuilder(eventID, desc).report()`，不额外 set 属性。
  记关键路径事件：关键步骤的进入与完成、重要状态标记的变更、用户中止与失败。
- **Chart** `WalletHAManager.chartBuilder(WalletHAEventID, funcID, subFuncID).report()`：成功率、时延、终态统计——
  业务步骤到达终态时每步一条，终态取 `WalletFuncResult`。
- 同一处代码 VOC 与 Chart 二选一：终态那一处发 Chart，过程关键点发 VOC。
- 三渠道共用同一次执行的流程与步骤标识（上报经 `setFuncID` / `setSubFuncID` 携带）；密度日志 > VOC > Chart，不设数量配额。
- 上报非阻塞，失败只记 `Logger.error`，不向调用方抛出。

## 6. 敏感数据处理 — `confirmed: 已确认`

通用脱敏 `MaskUtil`（`CommFunc` `shared/utils/MaskUtil.ets`）：`maskPhone` / `maskAccount`。
业务专属脱敏放本业务模块的 `shared/utils/`（如 `FinancialCard` 的 `CardNumberMaskUtil`），不上提公共层。

## 7. 资源 — `confirmed: 已确认`

字符串、颜色、尺寸在各模块 `src/main/resources/base/element/` 下的 `string.json` / `color.json` / `float.json`，
多语言与深色同名文件放 `zh_CN/element/`、`dark/element/`；代码用 `$r('app.string.<key>')` 引用。
新增或改动资源键时，改到的资源 json 与代码文件一样列进方案契约的文件清单。

## 8. 依赖变更（SDK / 组件 / TA） — `confirmed: 已确认`

模块依赖声明在各模块根 `oh-package.json5` 的 `dependencies`（`CommFunc` 为空）；模块清单在根 `build-profile.json5`。
编排 SDK 以 `framework`（`libs/framework-1.0.0.har`）声明在消费模块的依赖里，与仓库根 `framework/` 目录无关。
