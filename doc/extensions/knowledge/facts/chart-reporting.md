---
name: chart-reporting
kind: facts
applies_when: 需求涉及统计指标或改动已有上报时
---

# Chart 上报

## 1. 入口 — `confirmed: 已确认`

`WalletHAManager.chartBuilder(eventID, funcID, subFuncID)`（`CommFunc` `shared/ha/WalletHAManager.ets`）返回
`WalletHAReportForChartCBuilder`；设置方法在 `shared/ha/WalletHAReportBaseCBuilder.ets`，都从 `index.ets` 导出。

## 2. 标识 — `confirmed: 已确认`

`eventID` 取 `WalletHAEventID`（只有 `Wallet_COMMON`），写入 hiAppEvent 的 `WalletHA` 域、类型 STATISTIC（VOC 是 BEHAVIOR）。
`WalletEventID` 在 `report()` 时由 `FuncID_SubFuncID` 自动拼出：它不是业务内码，也不是一次执行的唯一标识。业务内码走 `setWalletEventInCode`。

## 3. 字段 — `confirmed: 已确认`

结果分类 `setWalletFuncResult(WalletFuncResult)`：`SUCCESS` 全程成功、`STEP_SUCCESS` 中间成功、`STEP_ERROR_BY_ERROR` 普通失败、
`STEP_ERROR_BY_USER` 主动取消。外码、描述、耗时（毫秒）、渠道、来源、订单号等各有专用设置方法，签名以源码为准。
自定义维度用 `setReportParam(name, value)`，值为 string / number / boolean。

## 4. `report()` 的边界 — `confirmed: 已确认`

只补 `WalletEventID`，不补没设置的字段；非阻塞，发送失败只记 `Logger.error`；不去重——同一节点同一次执行的终态只报一次，由业务保证；不同节点、新的一次执行各自报。

## 5. 内码登记（无） — `confirmed: 已确认`

仓里还没有十位内码的登记位置，也没有业务侧调用样例（已核对：`setWalletEventInCode`、`chartBuilder` 只命中封装自身）。
首次新增编码时在方案里定唯一登记位置。

## 6. 从需求到上报的顺序（参考）

1. 从业务目标选统计节点，写清为什么统计它；
2. 推每个节点的适用结果：成功、失败、主动取消里业务上真会发生的那些；
3. 查已有编码与字段，决定复用还是新增；
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
