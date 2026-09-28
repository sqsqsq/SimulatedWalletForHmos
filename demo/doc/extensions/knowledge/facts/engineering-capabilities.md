---
name: engineering-capabilities
kind: facts
form: facets
applies_when: 设计与编码要用到对外入口、页面导航、共享状态、开关、日志、脱敏、资源或依赖时：本项目已有的实现与用法
---

# 工程已有能力

设计与编码用到下列能力时，用这里的项目实现。公共能力在 `05-SystemBase/CommFunc`，从它的 `src/main/ets/index.ets` 引入。

## 1. 对外入口与页面导航

- 外部入口是 Ability，登记在 Phone 模块 `module.json5` 的 `abilities[]`，`exported` 控制能否被外部拉起；宿主页 Phone 的 `pages/index.ets` 是唯一 `@Entry`，持有唯一的 `Navigation`。
- 业务页是 `NavDestination`，按名字 `pushPath`；名字在宿主 `navDestinationMap` 里映射到模块 `index.ets` 导出的 `@Builder`，新增页面改这三处：页面文件导出 builder、模块 `index.ets` 导出它、宿主映射加一个名字分支。`route_map.json` 未被 `module.json5` 引用，不算登记。
- 取栈用 `CommFunc` 的 `NavPathContext`。

## 2. 数据存储

- 数据由各模块 `data/repository/*Repository.ets` 提供，业务从仓储类取数。
- 跨页共享的内存状态用 `AppStorage`，键写在所属模块的 `*Constants`（如 `AccountConstants.STORAGE_IS_LOGGED_IN`），由该模块的服务初始化（如 `AccountService`）。

## 3. 配置项

- 功能开关写成所属模块 `shared/constant/*Constants.ets` 里的 `static readonly` 布尔常量，如 `HomeConstants.SHOW_LOCAL_CARD_SECTION`。

## 4. 本地日志

- 用 `CommFunc` 的 `Logger.debug` / `info` / `error(tag, format, ...args)`，它封装 `hilog` 并统一 domain。

## 5. 敏感数据处理

- 手机号、账号脱敏用 `CommFunc` 的 `MaskUtil.maskPhone` / `maskAccount`；某个业务专属的脱敏写在该业务模块的 `shared/utils/`。

## 6. 资源

- 公共文案与颜色先用所属模块与 Phone 的 `resources/base/element/` 已有键；多语言与深色资源放 Phone 的 `resources/zh_CN/`、`resources/dark/`。

## 7. 依赖变更（SDK / 组件 / TA）

- 编排 SDK 以 `framework`（`libs/framework-1.0.0.har`）声明在用到它的模块的 `oh-package.json5`；它是这个 har 包，与仓库根目录的 `framework/` 目录是两回事。
