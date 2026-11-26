---
name: engineering-capabilities
kind: facts
form: facets
applies_when: 设计与编码要用到对外入口、页面导航、共享状态、开关、日志、脱敏、资源或依赖时：本项目已有的实现与用法
---

# 工程已有能力

设计与编码用到下列能力时，用这里的项目实现。公共工具能力在 `05-SystemBase/CommFunc`（`src/main/ets/index.ets`），共享 UI 组件与主题色在 `05-SystemBase/CommUI`（`src/main/ets/index.ets` 与 `resources/base/element/color.json`，见 §6）。

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
- `MaskUtil` 只生成展示值：`maskPhone` 留前 3 后 4，`maskAccount` 留首尾各 2，中间打码，不可逆，不能当业务身份用；长度不超过 7（手机号）或 4（账号）时原样返回，短标识要另行排除或确定规则，不能当成已脱敏。
- 当前工程没有现成的受保护持久化封装；此处描述仓内可复用实现，不对目标平台能力作结论。

## 6. 资源

- 共享主题色先查 `05-SystemBase/CommUI/src/main/resources/base/element/color.json` 已有 `comm_*` 键（如 `comm_primary_blue`、`comm_text_primary`、`comm_text_secondary`、`comm_bg_page`、`comm_bg_card`、`comm_tab_unselected`）与 `CommColors`；共享 UI 组件从 `05-SystemBase/CommUI/src/main/ets/index.ets` 引入（如 `SectionCard`、`ActionListItem`、`showToast` 与 `Maison*` 系列；`02-Feature/WalletMain/oh-package.json5` 已声明 `@aspect/CommUI` 依赖，`02-Feature/WalletMain/src/main/ets/presentation/pages/AddCardEntryPage.ets` 已导入并使用 `SectionCard`）。
- 页面私有文案与模块私有色值查所属业务模块自身资源目录（如 `02-Feature/WalletMain/src/main/resources/base/element/`）。
- `01-Product/Phone` 是应用壳层入口，业务模块不依赖 `Phone`（依据：`doc/architecture.md` 分层依赖规则）；`Phone/src/main/resources/` 仅用于壳层入口资源及应用级多语言/深色目录（`resources/zh_CN/`、`resources/dark/`），业务共享色值与组件不从 `Phone` 查找。

## 7. 依赖变更（SDK / 组件 / TA）

- 编排 SDK 以 `framework`（`libs/framework-1.0.0.har`）声明在用到它的模块的 `oh-package.json5`；它是这个 har 包，与仓库根目录的 `framework/` 目录是两回事。
