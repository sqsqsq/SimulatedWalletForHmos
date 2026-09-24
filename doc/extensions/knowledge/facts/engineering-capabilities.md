---
name: engineering-capabilities
kind: facts
applies_when: always（凡要写某项工程能力的现状、或新增能力前先找可复用的实现时）
protocol: 1
capabilities:
  - id: engineering-capabilities
    revision: 1
    covers: [对外暴露面, 端云接口, 数据存储, 配置项, 本地日志, 敏感数据处理, 资源, 依赖变更]
---

# 工程已有能力

设计里要用到一类工程能力——对外入口、网络、存储、开关、日志、脱敏、资源、依赖——时读这份。它告诉你本仓现在怎么做这件事、入口在哪、照什么约定写，以及哪些能力本仓没有、要新建。写技术契约里的「代码现状」和决定复用还是新建，都从这里起步；这里没登记的能力到仓里实扫，与这里不符时按实际代码改这份知识并在产物里写明矛盾。

本仓是 HarmonyOS 应用（ArkTS / ArkUI，hvigor 构建，模块依赖写在各模块的 `oh-package.json5`）。公共能力在 `CommFunc` 模块（`05-SystemBase/CommFunc`），对外符号一律从它的 `src/main/ets/index.ets` 导出，业务模块只从这里引用。以下都是当前实现，依据是所列代码位置。

## 1. 对外暴露面 — `confirmed: 已确认`

需求新增页面、入口或被外部拉起时看这一面。对外能力由应用清单 `src/main/module.json5` 的 `abilities[]` 声明，是否可被外部拉起看 `exported` 与 `skills`；页面路由登记在 `src/main/resources/base/profile/main_pages.json` 与 `route_map.json`。模块之间跳页统一走 `NavPathContext.stack().pushPath(...)`，导航栈由 `CommFunc` 的 `NavPathContext` 持有（`attach` / `stack`），业务代码不自建导航栈。新增对外入口要同时改清单与路由登记。

## 2. 端云接口 — `confirmed: 已确认`

需求要调用云侧服务时看这一面。本仓**没有**网络封装：`@ohos.net.http`、`http.createHttp`、`rcp`、`axios` 在源码里都零命中，数据来自本地仓储层。需求要真实的端云调用时，网络层是建设差距，要在设计里给出接口与责任，不当作已有能力复用。

## 3. 数据存储 — `confirmed: 已确认`

需求要持久化业务数据时看这一面。关系型持久化用 `relationalStore`（`@kit.ArkData`），每个 Feature 模块在 `src/main/ets/data/local/*RdbHelper.ets` 封装，持有单例 `RdbStore`，`StoreConfig` 带 `securityLevel`——新表照这个形态加在本模块的 Helper 里。只在内存里共享的状态用 `AppStorage`，放在 domain / service 层。本仓**没有**使用 `preferences` 与 `distributedKVStore`，要用它们是新引入，需写明理由。

## 4. 配置项 — `confirmed: 已确认`

需求要加开关或业务常量时看这一面。开关写在各模块 `src/main/ets/shared/constant/*Constants.ets`，形态是 `static readonly <NAME>: boolean`；同目录的非布尔业务常量按类型区分。本仓**没有**远程配置：没有管理台或云侧下发开关的封装，需求要「远程可关」时是建设差距。

## 5. 本地日志 — `confirmed: 已确认`

写本地日志用 `Logger`（`CommFunc` 的 `shared/log/Logger.ets`，封装 `hilog`，提供 `debug` / `info` / `error`），不直接调 `hilog`。日志里带个人数据时先按下一面脱敏；上报用另一份上报知识，不是日志。

## 6. 敏感数据处理 — `confirmed: 已确认`

展示或记录手机号、账号这类个人数据时看这一面。通用脱敏用 `MaskUtil`（`CommFunc` 的 `shared/utils/MaskUtil.ets`）：`maskPhone` / `maskAccount`。某个业务专属的脱敏写在该业务模块的 `shared/utils/`（例如 `FinancialCard` 的 `CardNumberMaskUtil`），不上提到公共层。

## 7. 资源 — `confirmed: 已确认`

需求有界面文案、颜色、尺寸时看这一面。它们在各模块 `src/main/resources/base/element/` 下的 `string.json` / `color.json` / `float.json`，多语言与深色的同名文件放在 `zh_CN/element/`、`dark/element/`；代码用 `$r('app.string.<key>')` 引用，不写死字符串。新增或改动资源键时，改到的资源文件与代码文件一样算作本次要改的文件。

## 8. 依赖变更（SDK / 组件 / TA） — `confirmed: 已确认`

需求要引入或升级依赖时看这一面。模块依赖声明在各模块根 `oh-package.json5` 的 `dependencies`（`CommFunc` 为空），模块清单在根 `build-profile.json5`。编排 SDK 以 `framework`（`libs/framework-1.0.0.har`）声明在用到它的模块的依赖里，与仓库根目录下的 `framework/` 目录无关。新增依赖要写明体积与兼容影响。
