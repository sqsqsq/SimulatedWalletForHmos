---
name: reporting
kind: facts
applies_when: 需求涉及业务定位、运维统计或独立运营采集时
---

# 上报

## 1. 渠道与已有能力 — `confirmed: 已确认`

| 渠道 | 用途 | 项目入口/能力 |
|---|---|---|
| VOC | 过程问题定位 | `WalletHAManager.vocBuilder(eventID, desc)`；`logAndReport` / `logErrorAndReport` / `logDebugAndReport` |
| Chart | 运维统计 | `WalletHAManager.chartBuilder(eventID, funcID, subFuncID)` |
| BI | 明确需求的独立运营采集 | `BIBuilder` |
| 自动运维上报 | 页面进入、点击等交互记录 | 工程自动采集，业务无需重复手工记录这些交互 |

业务步骤执行结果由业务调用产生，自动页面/点击记录不能表达校验是否通过等业务结论。VOC 与 Chart 在同一统计终态处二选一，过程关键点用 VOC；BI 与二者分别服务不同目的。

VOC 与 Chart 的封装位于 `CommFunc/src/main/ets/shared/ha/`，经 `CommFunc/src/main/ets/index.ets` 导出；发送非阻塞，失败记本地日志。SDK 不负责业务去重。

## 2. 身份与 SDK 映射 — `confirmed: 已确认`

Chart 与 BI 共用业务步骤身份：模板 `eventID`、流程 `funcID`、步骤 `subFuncID`。例如 `BankCard_001_002` 表示银行卡模板下某流程的一步，同一步骤的不同结果共用身份；同语义运营和运维点位引用同组常量。

Chart 中模板作为 hiAppEvent 的事件名，流程/步骤写入 `FuncID` / `SubFuncID`；Builder 生成的 `WalletEventID` 是 `FuncID_SubFuncID`，与事件名共同定位完整身份。平台类型为 STATISTIC。BI 的业务身份相同，具体传参采用项目 BI 接口，不从 Chart 封装推定其传输格式。

VOC 使用自己的标识：类型 BEHAVIOR，`WalletEventID` 为调用方事件标识，`FuncID` 固定为 `VOC`。三个日志门面先记相应级别的本地日志再发一条 VOC；仅上报使用 `vocBuilder(...).report()`。

## 3. 结果与字段映射 — `confirmed: 已确认`

运维内码是十位数字字符串，五段各两位：业务模块、业务流程、节点/事件、子节点/子事件、具体结果，前导零保留。内码定位具体结果，分类表达结果类别，两者独立；事件身份表达步骤，不随成功/失败改名。

| 数据 | 项目语义与用法 |
|---|---|
| 结果分类 | `setWalletFuncResult`：`SUCCESS` 全流程成功；`STEP_SUCCESS` 步骤成功；`STEP_ERROR_BY_ERROR` 普通失败；`STEP_ERROR_BY_USER` 主动取消。拒绝授权归普通失败 |
| 内码 | `setWalletEventInCode(string)`；Chart 结果采用已登记编码，子点可由子节点段区分 |
| 外码 | `setWalletEventExtCode(string)`；仅带该结果实际取得的外部错误码，无则不设置 |
| 耗时 | `setDuration(number)`，毫秒；有统计需要、明确起止且实际测量时带 |
| 描述 | `setWalletEventDesc(string)`，点位可读描述；按项目协议及场景填写 |

BI 按明确运营需求选择参数，不默认携带运维内码、外码或结果分类。项目约定借用内外码表达相近业务含义时，采用对应的运营定义和取值来源。自定义维度经 `setReportParam(name, value)`，值为 string / number / boolean；已有标准字段使用其专用入口。

## 4. 业务扩展字段 — `confirmed: 未确认`

`WalletHAReportBaseCBuilder.ets` 提供 `setChannel`、`setSource`、`setIssueID`、`setIssueName`、`setOperationType`、`setSrcPassType`、`setOrderNumber`、`setTransactionId`（string）及 `setHappenedTime`（string | number）。以上名称和类型已核；业务含义按项目参数规范核实。

需要核实的具体内容：Channel/Source 的区分与取值；IssueID/IssueName 所指主体；OperationType/SrcPassType 取值集合；OrderNumber/TransactionId 的区别；HappenedTime 格式，以及本需求实际使用字段的必需条件、来源和隐私处理。只核本需求需要的字段，不要求填满全部参数。

## 5. 登记与复用 — `confirmed: 已确认`

模板枚举位于 `CommFunc/src/main/ets/shared/ha/WalletHAEventID.ets`，当前有 `Wallet_COMMON`。当前仓尚无业务流程、步骤和内码登记，分配按下面的规则：

- 流程、步骤身份与内码登记在特性自己的登记文件里：放该特性的 shared 层，文件名以 `ChartCodes` 结尾，首次使用时新建。
- 流程号、步骤号按登记文件里的顺序取下一个三位数。
- 内码的业务模块段与业务流程段沿登记文件，节点段按步骤序，子节点段按子点序；结果段 `00` 成功、`01` 起为各类失败、`10` 主动取消。
- 实现设计按此写出候选值并标「待登记：<登记文件>」；编码时建登记文件并核冲突。示例值不是已分配值。

身份定义不是一次执行的流水号。已有定义按语义复用，新的具体结果扩展内码，不为同一步骤的不同结果复制身份常量。

## 6. 使用参考

先从指标反推要算它需要哪些结果，再定统计点。以一项「开通服务」的运维指标（开通成功率）说明上报能力怎样对应到业务：指标对应一条开通流程，流程里需要统计的步骤各有一组步骤身份，
可重试的短信验证下有两个子点，共用步骤身份，由内码子节点段区分。步骤划分与粒度随具体业务，下表只是关系示例。

| 统计对象（子节点段） | 实际会发生的结果与分类 | 本端从哪得知 |
|---|---|---|
| 身份校验步骤 | 通过：STEP_SUCCESS；不通过：普通失败 | 校验请求的返回 |
| 短信验证步骤（00） | 验证通过：STEP_SUCCESS；明确终止验证：主动取消；无法继续：普通失败 | 校验子点的结果与用户操作 |
| 发送验证码（01） | 发送成功：STEP_SUCCESS；发送失败：普通失败 | 发送请求的返回 |
| 校验验证码（02） | 校验通过：STEP_SUCCESS；未通过：普通失败 | 校验请求的返回 |
| 开通流程整体 | 开通成功：SUCCESS；开通失败：普通失败 | 开通结果的回调或查询；结果在远端产生时，写明本端在哪个时机取得 |

实现设计里同一个统计点要连成一行：「校验验证码」这一点的身份是开通流程下短信验证步骤的一组 `funcID`/`subFuncID`，内码在短信验证步骤的节点段下用子节点段 `02`，结果段取 `00`（通过）或 `01`（未通过），外码取校验接口返回的错误码（没有则不带），由执行校验的那个方法在校验请求返回时报告；同一次校验的重复回调按请求标识只报一次，耗时取请求发出到返回。

校验失败后重新输入是新尝试，父步骤可以最终成功。终止验证不取消已经发出的发送请求，各对象记录自身结果；同一尝试的重复回调仅报告一次。子点也可以按项目粒度采用独立步骤身份，不能仅按共用事件名去重。

```ts
WalletHAManager.chartBuilder(WalletHAEventID.Wallet_COMMON, funcID, subFuncID)
  .setWalletEventInCode(inCode)
  .setWalletFuncResult(result)
  .report();
```
