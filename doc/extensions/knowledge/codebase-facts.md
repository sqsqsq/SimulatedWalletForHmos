---
name: codebase-facts
applies_when: always（凡需给出「代码库现状」这一半事实时）
---

# 工程取证事实登记

**这个工程各类能力的现状：有没有、长什么样、怎么认出来。** 工程级事实，
不属于任何单个流程阶段。取证公式「事实 = 变更意图 × **代码库现状**」的现状那一半，
第一落点就是本文件。

> **本文件只登记事实。** 怎么判、结论往哪写、取不到怎么降级，全在
> [evidence-rules](../skills/story/reference/evidence-rules.md)；某条约束该怎么落地，
> 在该约束的「落法附注」。三者不互相复述。

## 怎么维护

- **一面一行式的特征，不列实例**：写这类能力用什么 API、什么命名、在哪层目录。
  真实工程里同类实例成百上千，列清单既维护不动，也会随一次重构全部过期；特征稳定得多。
- **首版必须实扫生成**，不许照抄别的工程或凭平台常识填——本文件的前身
  `codebase-probes.md` 就是通用猜测的平移，与本仓实际对不上（写了本仓根本不用的埋点 API，
  漏了实际存在的日志封装）。
- 每面标 `confirmed`：`已确认` = 有人（或掌握真实仓的模型）实扫核对过；
  换工程重写后初始为 `未确认`，待确认者过一遍。
- **「没有」必须是核对过的结论**，不是没查到——写明「无此封装（已核对）」及零命中的检索项。
- **回灌**：取证时发现与代码不符（重构、换封装），当场修订本面并退回 `未确认`。
- **换工程复用**：由模型实扫目标仓重写全篇，再由人确认——与 `component-profile.md`
  同款画像，evidence-rules 与脚本不动。

**本工程技术栈**：HarmonyOS 应用（ArkTS / ArkUI，hvigor 构建，模块级 `oh-package.json5`）。

---

## 1. 对外暴露面 — `confirmed: 已确认`

应用清单 `src/main/module.json5` 的 `abilities[]`（看 `exported` 与 `skills`）；页面路由注册表
`src/main/resources/base/profile/main_pages.json` 与 `route_map.json`；跨模块跳转统一走
`pushPath`，导航栈由 `CommFunc` 的 `NavPathContext` 持有（`attach` / `stack`）。

## 2. 端云接口 — `confirmed: 已确认`

**无端云封装（已核对）**：`@ohos.net.http` / `http.createHttp` / `rcp` / `axios` 源码内均零命中，
数据来自本地仓储层，无网络出口。

## 3. 数据存储 — `confirmed: 已确认`

关系型持久化用 `relationalStore`（`@kit.ArkData`），封装在 Feature 模块的
`src/main/ets/data/local/*RdbHelper.ets`（持有单例 `RdbStore`，`StoreConfig` 带 `securityLevel`）；
内存态用 `AppStorage`，出现在 domain/service 层。**未使用** `preferences` 与
`distributedKVStore`；源码内无备份配置（构建产物目录下的是合成物）。

## 4. 配置项 — `confirmed: 已确认`

常量开关在各模块 `src/main/ets/shared/constant/*Constants.ets` 中，形态为
`static readonly <NAME>: boolean`（现存的均默认 `false`）；同目录另有非布尔的业务常量类，
按类型区分，别一并当开关。**无远程配置封装（已核对）**：源码内无管理台/云侧下发开关。

## 5. 可观测性 — `confirmed: 已确认`

**三条渠道齐备，都从 `CommFunc` 的公开出口导出**（`05-SystemBase/CommFunc/src/main/ets/index.ets`）：

| 渠道 | 出口形态 | 特征 |
|---|---|---|
| 日志 | 静态日志类（`shared/log/`） | 封装 `@kit.PerformanceAnalysisKit` 的 `hilog`，统一 `DOMAIN`，静态 `debug` / `info` / `error` |
| 用户问题反馈 | VOC 上报 Builder（`shared/ha/`） | 链式构造 + `report()`，底层 `hiAppEvent.write` |
| 业务度量 | Chart 上报 Builder（`shared/ha/`） | 同上，另带业务终态入参 |

**统一门面**：`shared/ha/` 下的 HA 管理类提供静态方法，把「记一条日志 + 发一条反馈」合成一次调用，
分 info / error / debug 三档——业务侧通常调门面而不是直接用 Builder。

**关键规则（读代码才看得出，判定时必须知道）**：

- **上报非阻塞、失败不外传**：两类 Builder 的 `report()` 内层 `hiAppEvent.write` 返回 Promise，
  被 `.catch` 与外层 `try/catch` 双重兜住，失败只记一条本地错误日志，**不抛、不改返回值**。
  这就是「观测失败不改业务」在本工程的既有实现方式。
- **业务终态是一个受控枚举**（`shared/ha/` 内），取值覆盖成功、步骤成功、用户中止、异常失败。
  设计终态集合时从这个枚举取，不自造字符串。
- **事件标识集中登记**在 `shared/ha/` 的事件 ID 定义里，不在调用点写字面量。

**核实方法**（换工程重写时照此实扫，不照抄本表）：读公共能力模块的公开出口文件，
看导出了哪些日志/上报类；再进它们的实现看失败处置与终态定义。

> 本面**不列调用点清单**：调用点成百上千且随每次重构变化，列了必然过期（本文件的维护纪律）。
> 判「本需求的观测怎么落」时，按上面的特征找到出口，再按可观测性规约的条目逐条设计。

### 5.1 更正记录

本面前身写的是「无埋点封装（已核对），`hiAnalytics` / `hiAppEvent` 零命中」——**该结论是错的**：
`hiAppEvent` 在两类上报 Builder 中真实使用。2026-08-25 实扫更正。
教训：「没有」必须是核对过的结论，而核对必须落到公开出口与实现文件，
不能只对着一两个 API 名做全仓检索就下结论。

## 5.2 敏感数据处理 — `confirmed: 已确认`

通用脱敏工具在公共能力模块（`CommFunc`）的 `shared/utils/` 下并从模块公开出口导出；
业务专属的脱敏（如卡号按业务规则留头尾）另在对应 Feature 模块的 `shared/utils/` 内，
**不上提到公共层**——业务规则会随业务变，公共层只放与业务无关的通用遮蔽。

判「某条打印是否已脱敏」时：先按上述两处找到本数据类型对应的封装，再看调用点有没有过它。

## 6. 依赖变更（SDK / 组件 / TA） — `confirmed: 已确认`

模块依赖声明在各模块根的 `oh-package.json5` 的 `dependencies`（系统侧通用能力模块为空）；
模块清单在根 `build-profile.json5`。

## 7. 编排 SDK — `confirmed: 已确认（能力在，业务案例缺）`

仓内 `libs/` 下有一个以 har 形态随仓交付的编排 SDK，通过 `oh-package.json5` 的
`file:` 依赖被产品层与业务特性层引用（根 + 两个模块共三处声明）。

**证据缺口（不虚构、不假定）**：只证实了 **SDK 随仓存在且被声明依赖**；
**未找到**多个真实业务模块使用它做流程编排的案例。因此：设计模式知识里的结构骨架
在本工程是「可用但少先例」，具体需求是否采用该模式，须由 plan 结合适用单元与本条证据
自行判断——不得因为模式文档存在就假定工程已具备成熟用法。

> 该编排 SDK 与仓库根的 `framework/`（需求开发工作流框架）是两回事，名字相近但无关。

> 新依赖边的合法性由 `framework.config.json` architecture 段的 `can_depend_on` 判定——
> 那是框架概念、不随平台变，不在本文件登记。
