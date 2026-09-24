---
name: reporting
kind: facts
applies_when: 需求涉及业务定位、运维统计或独立运营采集时
protocol: 1
capabilities:
  - id: reporting
    revision: 1
    covers: [统计设计, 上报实现, 编号分配与复用, 业务扩展字段]
---

# 上报

需求要观察业务质量、定位问题或明确要求运营采集时读这份。[1. 统计设计](#1-统计设计--confirmed-已确认) 用业务语言定观察什么、有哪些结果、本端何时知道；[2. 上报实现](#2-上报实现--confirmed-已确认) 把这些结果落到本仓的上报并给出核对办法；新编号见 [3](#3-编号分配与复用--confirmed-已确认)，扩展参数见 [4](#4-业务扩展字段--confirmed-未确认)（含义未核实）。**当前实现**以 `05-SystemBase/CommFunc/src/main/ets/shared/ha/` 的代码为准，**已定规范**是本仓采用、尚未实现的要求；例子里的业务类与编号都是示意。

## 1. 统计设计 — `confirmed: 已确认`

读者：写统计设计的 spec 作者与审查者。三类上报目的不同，同一业务事实服务运维又服务运营时共用一个业务步骤身份：

| 渠道 | 用途 | 现状 |
|---|---|---|
| VOC | 过程问题定位 | 当前实现，可直接用 |
| Chart | 运维统计，指标来源 | 当前实现，可直接用 |
| BI | 需求明确要求的独立运营采集 | 已定规范，仓内无封装：要用时是建设差距 |
| 交互自动记录 | 页面进入、点击 | 已定规范，仓内未实现，不算已有覆盖：要用这些数据时写明要求与建设差距 |

同一统计终态上 VOC 与 Chart 二选一，过程关键点用 VOC。按五步设计：

1. **定观察对象与范围**：分清材料里的业务目标（如「开通率提升到多少」）与为看懂流程质量要观察的指标，说明关系。指标与流程不一一对应：一个指标可汇总几条流程的同类结果，一条流程也可支撑几个指标；范围按需求与统计语义定。
2. **沿实际流程找点**：流程由步骤组成，步骤下可有子点；同一步骤的不同结果是同一个统计对象，不同流程里同名步骤按各自流程区分。步骤成功与流程成功各有结果。
3. **每点写结果与获知时机**：只写实际适用的业务结果；本端在哪个响应、回调或状态查询里知道。一次尝试从发起到这一点的终态，失败后重新输入是新尝试。远端产生、本端观察不到的，写清由谁统计或列为待决。页面进入与点击说明不了校验通过这类业务结论。
4. **核已有覆盖**：表里当前实现能表达的不新增，只是规范的写成建设差距。
5. **处理共用与运营需求**：几个指标共用同一事实时只采集一次；独立运营采集只在需求明确要求时加。

例：观察「服务开通」一次尝试的结果，短信验证步骤用来定位开通卡在哪；校验失败可重新输入，步骤失败不等于开通失败。假设开通最终结果由服务端回调告知。

| 业务点 | 业务结果 | 本端获知依据 |
|---|---|---|
| 信息校验 | 通过、条件不满足 | 校验返回 |
| 发送验证码 | 发送成功、发送失败 | 发送响应 |
| 校验验证码 | 校验通过、未通过、请求失败 | 校验响应，或请求发出后通信失败 |
| 短信验证步骤 | 验证完成、用户主动终止 | 子点结果与用户操作 |
| 开通结果 | 开通成功、开通失败 | 开通结果回调或查询 |

选这几个点，是因为开通率要能拆到「卡在哪一步」；本例没有运营诉求，不加独立运营采集。设计完成：每个点说得出结果、产生方与获知时机，指标能由这些结果算出，已有覆盖与建设差距分开。

## 2. 上报实现 — `confirmed: 已确认`

### 设计

读者：写实现设计的 plan 作者与审查者。输入是统计设计定下的点与结果，按五步落实：

1. **找责任方法**：每种结果在真实或待建接口里成立的分支、回调或用户动作，所在方法负责报；公共上报封装只组装发送。
2. **定身份**：Chart 与 BI 共用业务步骤身份——模板 `eventID`、流程 `funcID`、步骤 `subFuncID`（如 `BankCard_001_002`），同一步骤各结果共用，同语义运营与运维点位引用同组常量。Chart 里模板是 hiAppEvent 事件名，流程与步骤写进 `FuncID` / `SubFuncID`，Builder 生成 `WalletEventID` = `FuncID_SubFuncID`，平台类型 STATISTIC；BI 传参走项目 BI 接口，不从 Chart 封装推。VOC 另用标识：类型 BEHAVIOR，`WalletEventID` 由调用方给，`FuncID` 固定 `VOC`。已有身份按语义复用，新值见第 3 面。
3. **定取值**，每种结果写值或取值表达式、来源、缺席条件：
   - 结果分类 `setWalletFuncResult`：`SUCCESS` 全流程成功、`STEP_SUCCESS` 步骤成功、`STEP_ERROR_BY_ERROR` 普通失败（含拒绝授权）、`STEP_ERROR_BY_USER` 用户主动取消。
   - 内码 `setWalletEventInCode(string)`：十位，五段各两位（业务模块、业务流程、节点、子节点、具体结果），前导零保留；定位具体结果，与分类独立，身份不随结果改名。新内码见第 3 面。
   - 外码 `setWalletEventExtCode(string)`：只带实际拿到的外部错误码，没有不设。耗时 `setDuration(number)` 毫秒，有诉求且起止明确时带。描述 `setWalletEventDesc(string)`。
   - 自定义维度 `setReportParam(name, value)`，值为 string / number / boolean；标准字段用专用入口，扩展参数见第 4 面。BI 按运营需求选参，不默认带运维内码、外码或分类。
4. **定同次边界**：一次尝试只结算一次；重试建新尝试；退出界面不等于取消已发请求。尝试标识属于执行上下文，与业务幂等身份分开。
5. **列预期事件**：每种结果应看到的事件，连同下节核对的情形。

例：「校验验证码」三种结果（假设全仓尚无其他已分配值；内码段为模块 `01`、流程 `01`、节点 `02` 短信验证、子节点 `02` 校验，结果段按第 3 面首次候选提出，未占真实编号；其余点同样处理，如发送验证码由发送方法按响应报、开通结果由处理回调的方法报）：

| 业务结果 | 身份 | 内码（候选） | 结果分类 | 外码 | 何时记录 → 预期事件 |
|---|---|---|---|---|---|
| 校验通过 | `Wallet_COMMON`，流程 `001`，步骤 `002` | `0101020200` | `STEP_SUCCESS` | 不带 | 收到通过响应 → 一条 |
| 未通过 | 同上 | `0101020201` | `STEP_ERROR_BY_ERROR` | 响应里的外部错误码 | 收到未通过响应 → 一条 |
| 请求失败 | 同上 | `0101020202` | `STEP_ERROR_BY_ERROR` | 错误对象里的码 | 请求发出后通信失败 → 一条 |

### 落地与核对

读者：写代码、审查、写单测与真机测试的人。Chart 用 `WalletHAManager.chartBuilder(eventID, funcID, subFuncID)` 链式设字段后 `.report()`；VOC 用 `vocBuilder(eventID, desc).report()`，要同时记本地日志用 `logAndReport` / `logErrorAndReport` / `logDebugAndReport`。两者经 `CommFunc/src/main/ets/index.ets` 导出，发送不阻塞业务、失败只记本地日志，不做业务去重。

约定：结果在决定它的业务方法里报；发请求与结算分开，正常、失败、异常与重复到达的回调都进同一结算方法，由它判断这次尝试是否已记；重试建新尝试；已发请求按自己的最终结果记，不因退出界面改记取消。反模式：在公共封装或页面回调里统一上报（结果与责任对不上）；页面退出后屏蔽后到的结果。

```ts
// 示意：SmsVerifyService、VerifyAttempt、CheckOutcome、IN_CODE_CHECK 为待建设计，chartBuilder 与 setter 为现有接口
async checkCode(attempt: VerifyAttempt, code: string): Promise<boolean> {
  try {
    const resp = await this.smsVerifyService.check(code);
    this.settleCheck(attempt, resp.passed ? 'pass' : 'fail', resp.extCode);
    return resp.passed;
  } catch (e) {
    this.settleCheck(attempt, 'transport', (e as TransportError).code);
    return false;
  }
}

settleCheck(attempt: VerifyAttempt, outcome: CheckOutcome, extCode?: string): void {
  if (attempt.settled) {
    return;                                   // 重复回调只进这里：不发请求，不多记
  }
  attempt.settled = true;
  const builder = WalletHAManager.chartBuilder(WalletHAEventID.Wallet_COMMON, FLOW_OPEN, STEP_SMS_VERIFY)
    .setWalletEventInCode(IN_CODE_CHECK[outcome])
    .setWalletFuncResult(outcome === 'pass' ? WalletFuncResult.STEP_SUCCESS : WalletFuncResult.STEP_ERROR_BY_ERROR);
  if (outcome !== 'pass' && extCode) {
    builder.setWalletEventExtCode(extCode);
  }
  builder.report();
}
```

核对表中三种结果之外还要看：同一尝试回调重复到达，不发请求也不多出事件；重新输入（调用方新建 `VerifyAttempt`）再出一条；退出验证界面时已发出的发送请求照常按响应记录。用对了：每个结果连得成「结果 → 责任方法与分支 → 身份与字段来源 → 调用 → 预期事件」。

## 3. 编号分配与复用 — `confirmed: 已确认`

现有定义（当前实现）：模板枚举在 `CommFunc/src/main/ets/shared/ha/WalletHAEventID.ets`，只有 `Wallet_COMMON`；仓内尚无业务流程、步骤、内码登记，也没有 Chart 调用。身份按「模板 → 流程 → 步骤」分配，流程号、步骤号三位；内码按「业务模块 → 模块内流程 → 节点 → 子节点 → 具体结果」分配，每段两位；两处流程段长度不同，不互相截取。

分配规范（本仓采用，具体编号仍按规范提出并确认）：

1. 先扫全仓模板、常量与调用，同语义已有值直接复用，跨特性共用模板时先核全部已有定义；身份不是流水号，同一步骤的新结果扩展内码，不复制身份常量。
2. 新值在父范围取未用号作具体候选：首次升序从 `001` / `01` 起，节点与子节点段 `00` 留给未细分；结果段 `00` 成功、`10` 主动取消，失败取其余未用号。
3. 父范围首次使用时，父范围与子项候选及依据一起提出，经项目设计评审确认，不称作已有分配；有外部统一分配的用其结果，拿不到时列出待决项，不自行占号。
4. 登记文件放特性自己的 shared 层，以 `ChartCodes` 结尾，首次使用时新建；设计里标「待登记：<登记文件>」，写入前重核冲突，有冲突回设计调整，不自动换号。

## 4. 业务扩展字段 — `confirmed: 未确认`

`WalletHAReportBaseCBuilder.ets` 另有 `setChannel`、`setSource`、`setIssueID`、`setIssueName`、`setOperationType`、`setSrcPassType`、`setOrderNumber`、`setTransactionId`（string）与 `setHappenedTime`（string | number）；名称与类型已按代码核实，业务含义没有依据。用到时先取得项目参数规范或负责人确认，核：Channel 与 Source 的区分与取值；IssueID / IssueName 指哪个主体；OperationType / SrcPassType 取值集合；OrderNumber 与 TransactionId 的区别；HappenedTime 格式；以及本需求实际用到字段的必填条件、来源与隐私处理。只核要用的，不要求填满。
