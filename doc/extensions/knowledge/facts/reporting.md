---
name: reporting
kind: facts
applies_when: 需求涉及上报（VOC、Chart 或 BI）时
---

# 上报

## 1. 渠道与现状 — `confirmed: 已确认`

| 渠道 | 用途 | 本仓入口 |
|---|---|---|
| VOC | 问题定位 | `WalletHAManager.vocBuilder(eventID, desc)`；门面 `logAndReport` / `logErrorAndReport` / `logDebugAndReport(eventID, desc)` |
| Chart | 运维统计 | `WalletHAManager.chartBuilder(eventID, funcID, subFuncID)` |
| BI | 运营打点 | 无（已核对：产品目录检索 `BIBuilder` 零命中）；真实仓叫 `BIBuilder` 是用户告知的，不是本仓已有能力 |

本仓已实现的 VOC 与 Chart 都在 `CommFunc` `shared/ha/`，从 `index.ets` 导出。两个 Builder 都写 hiAppEvent 的 `WalletHA` 域，非阻塞，发送失败只记 `Logger.error`、不向调用方抛出；
`report()` 发送当前 Builder 里的参数：渠道自动设置的标识见各自小节，其余业务字段由调用方提供；不负责业务去重。

## 2. VOC — `confirmed: 已确认`

事件类型 BEHAVIOR；`WalletEventID` 就是调用方给的 `eventID`，`FuncID` 固定为 `VOC`。三个门面先按对应档记一条本地日志（事件号当 tag），
再发一条 VOC——用了门面就不必另记同一条日志。只上报不打日志用 `vocBuilder(...).report()`。

## 3. Chart — `confirmed: 已确认`

事件类型 STATISTIC；`eventID` 取 `WalletHAEventID`（只有 `Wallet_COMMON`）。`WalletEventID` 在 `report()` 时由 `FuncID_SubFuncID` 自动拼出：
它不是业务内码，也不是一次执行的唯一标识；业务内码走 `setWalletEventInCode`。
结果分类 `setWalletFuncResult(WalletFuncResult)`：`SUCCESS` 全程成功、`STEP_SUCCESS` 中间成功、`STEP_ERROR_BY_ERROR` 普通失败、
`STEP_ERROR_BY_USER` 主动取消。外码、描述、耗时（毫秒）、渠道、来源、订单号等各有专用设置方法，签名以源码为准；
自定义维度用 `setReportParam(name, value)`，值为 string / number / boolean。
同一节点同一次执行的终态只报一次，由业务保证；不同节点、新的一次执行各自报。

## 4. Chart 内码登记（无） — `confirmed: 已确认`

仓里还没有十位内码的登记位置，也没有业务侧调用样例（已核对：`setWalletEventInCode`、`chartBuilder` 只命中封装自身）。
首次新增编码时在方案里定唯一登记位置。

## 5. 从需求到上报的顺序（参考）

1. 先辨目的与渠道：定位问题用 VOC、运维统计用 Chart、运营打点用 BI；本仓没有的渠道如实写缺口；
2. 查本仓对应入口与字段规则，决定复用还是新增。

以下只对 Chart：

3. 从业务目标选统计节点，写清为什么统计它；推每个节点业务上真会发生的结果；
4. 定结果在哪里收敛成一次终态、由谁调一次 `report()`；
5. 定验证：按场景刺激捕获原始事件，核时机、字段与次数。

用户明确终止这次业务是主动取消（只是返回上一页不一定算）；支付侧拒绝授权是普通失败。节点数量、流程顺序与字段组合随业务定，上面只是顺序。

```ts
WalletHAManager.chartBuilder(WalletHAEventID.Wallet_COMMON, funcID, subFuncID)
  .setWalletEventInCode(inCode)
  .setWalletFuncResult(result)
  .setDuration(costMs)
  .report();
```
