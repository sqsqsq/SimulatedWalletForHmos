# 银行卡开卡与结果查询 — 实现计划（Plan 节选）

> 只摘宿主扩展的埋点小节；编码、责任方法都是候选值，假设与候选地位见[候选说明](README.md)。

## 9. 宿主扩展

### 9.2 埋点

本节实现 Spec 9.1.4 的开卡成功率与查询成功率，指标定义与口径以 Spec 为准。页面、点击的自动运维上报继续复用；没有明确的运营需求，不分配运营事件、不加运营上报调用。

#### 9.2.1 共同约定

- **身份**：`模板_流程_步骤` 三段，同一步骤的子点与步骤整体共用。开卡办理：信息校验 `BankCard_001_001`、短信验证 `BankCard_001_002`、人脸核验 `BankCard_001_003`、写卡 `BankCard_001_004`、结果展示 `BankCard_001_005`、开卡全流程 `BankCard_001_000`。开卡结果查询：参数校验 `BankCard_002_001`、状态查询 `BankCard_002_002`、查询整体 `BankCard_002_000`。
- **内码**：十位 `10`（银行卡）`01|02`（流程）`NN`（节点）`SS`（子点）`RR`（结果：`00` 成功、`01` 起失败、`10` 主动取消），按字符串保留前导零；子点 `00` 表示步骤整体，节点 `00` 表示流程整体。
- **分类**：开卡全流程与查询整体成功 SUCCESS，其余成功 STEP_SUCCESS；失败 STEP_ERROR_BY_ERROR；主动取消 STEP_ERROR_BY_USER。
- **失败原因**：外码取失败那一步的外部返回码，没有就不带，内码不充当外码；步骤整体与全流程取失败子点的外码。
- **尝试**：一次开卡关联标识与尝试序号由开卡业务控制者持有，走项目允许的扩展参数；去重键是「一次开卡＋节点与子点＋这一点的尝试序号」。
- **登记位置**：目标仓业务码登记文件，开卡与查询同一份，首用新建。

#### 9.2.2 逐点实现

| 统计点 | 结果 | 责任方法 | 字段取值 | 去重与验证 |
|---|---|---|---|---|
| 卡号校验 | 通过 | BankCardOpenFlow.submitInfo | 内码 1001010100，STEP_SUCCESS | 每次提交一次尝试；合法卡号一条 |
| 卡号校验 | 不通过 | BankCardOpenFlow.submitInfo | 内码 1001010101，STEP_ERROR_BY_ERROR，本地校验不带外码 | 非法卡号一条 |
| 身份校验 | 通过 | IdentityCheckService.check | 内码 1001010200，STEP_SUCCESS | 卡号不通过时不发起、不记 |
| 身份校验 | 拒绝 | IdentityCheckService.check | 内码 1001010201，STEP_ERROR_BY_ERROR，外码取身份校验接口返回码 | 拒绝一条 |
| 身份校验 | 服务异常 | IdentityCheckService.check | 内码 1001010202，STEP_ERROR_BY_ERROR，外码取身份校验接口返回码 | 服务异常一条 |
| 信息校验整体 | 成功 | BankCardOpenFlow.submitInfo | 内码 1001010000，STEP_SUCCESS | 同一提交的重复通知不重报 |
| 信息校验整体 | 失败 | BankCardOpenFlow.submitInfo | 内码 1001010001，STEP_ERROR_BY_ERROR | 更正卡号后再提交记两次尝试 |
| 信息校验整体 | 用户取消 | BankCardOpenFlow.submitInfo | 内码 1001010010，STEP_ERROR_BY_USER | 用户终止一条 |
| 验证码发送 | 受理 | SmsVerifyController.send | 内码 1001020100，STEP_SUCCESS | 每次发送或重发一次尝试；重发记两条 |
| 验证码发送 | 业务拒绝 | SmsVerifyController.send | 内码 1001020101，STEP_ERROR_BY_ERROR，外码取短信接口返回码 | 业务拒绝一条 |
| 验证码发送 | 服务失败 | SmsVerifyController.send | 内码 1001020102，STEP_ERROR_BY_ERROR，外码取短信接口返回码 | 服务失败一条 |
| 验证码校验 | 通过 | SmsVerifyController.verify | 内码 1001020200，STEP_SUCCESS | 每次提交验证码一次尝试；先错后对记两条 |
| 验证码校验 | 错误 | SmsVerifyController.verify | 内码 1001020201，STEP_ERROR_BY_ERROR，外码取校验接口返回码 | 错误一条，重输是新尝试 |
| 验证码校验 | 过期 | SmsVerifyController.verify | 内码 1001020202，STEP_ERROR_BY_ERROR，外码取校验接口返回码 | 过期一条 |
| 验证码校验 | 服务失败 | SmsVerifyController.verify | 内码 1001020203，STEP_ERROR_BY_ERROR，外码取校验接口返回码 | 服务失败一条 |
| 短信验证整体 | 成功 | SmsVerifyController.verify | 内码 1001020000，STEP_SUCCESS | 可恢复的输错不结束整体；先错后对只记一条成功 |
| 短信验证整体 | 失败 | SmsVerifyController.verify | 内码 1001020001，STEP_ERROR_BY_ERROR | 无法继续时一条 |
| 短信验证整体 | 用户取消 | SmsVerifyController.verify | 内码 1001020010，STEP_ERROR_BY_USER | 用户退出一条 |
| 活体检测 | 通过 | FaceVerifyController.detect | 内码 1001030100，STEP_SUCCESS | 中止后迟到的回调不改结果 |
| 活体检测 | 不通过 | FaceVerifyController.detect | 内码 1001030101，STEP_ERROR_BY_ERROR，外码取活体组件返回码 | 不通过一条 |
| 活体检测 | 用户中止 | FaceVerifyController.detect | 内码 1001030110，STEP_ERROR_BY_USER | 中止后迟到回调仍一条 |
| 身份比对 | 一致 | FaceVerifyController.compare | 内码 1001030200，STEP_SUCCESS | 活体未通过不发起、不记 |
| 身份比对 | 不一致 | FaceVerifyController.compare | 内码 1001030201，STEP_ERROR_BY_ERROR，外码取比对接口返回码 | 不一致一条 |
| 身份比对 | 服务异常 | FaceVerifyController.compare | 内码 1001030202，STEP_ERROR_BY_ERROR，外码取比对接口返回码 | 服务异常一条 |
| 人脸核验整体 | 成功 | FaceVerifyController.compare | 内码 1001030000，STEP_SUCCESS | 检测与比对都有结果时一条 |
| 人脸核验整体 | 核验失败 | FaceVerifyController.compare | 内码 1001030001，STEP_ERROR_BY_ERROR | 核验失败一条 |
| 人脸核验整体 | 拒绝授权 | FaceVerifyController.compare | 内码 1001030002，STEP_ERROR_BY_ERROR | 拒绝授权不编子点结果；一条 |
| 人脸核验整体 | 用户取消 | FaceVerifyController.compare | 内码 1001030010，STEP_ERROR_BY_USER | 用户中止一条 |
| 开卡申请 | 受理 | CardOpenService.apply | 内码 1001040100，STEP_SUCCESS | 同一申请只记一次 |
| 开卡申请 | 业务拒绝 | CardOpenService.apply | 内码 1001040101，STEP_ERROR_BY_ERROR，外码取开卡接口错误码 | 业务拒绝一条 |
| 开卡申请 | 服务异常 | CardOpenService.apply | 内码 1001040102，STEP_ERROR_BY_ERROR，外码取开卡接口错误码 | 服务异常一条 |
| 本地写入与激活确认 | 成功 | CardOpenService.writeCard | 内码 1001040200，STEP_SUCCESS | 待确认查明后只记一次；超时待确认、查明成功一条 |
| 本地写入与激活确认 | 失败 | CardOpenService.writeCard | 内码 1001040201，STEP_ERROR_BY_ERROR，外码取写卡组件返回码 | 失败一条 |
| 写卡整体 | 成功 | CardOpenService.writeCard | 内码 1001040000，STEP_SUCCESS | 动画与页面生命周期不触发；动画先于确认结束时不提前记 |
| 写卡整体 | 失败 | CardOpenService.writeCard | 内码 1001040001，STEP_ERROR_BY_ERROR | 权威结果与本地写入都确定时一条 |
| 结果数据获取 | 成功 | OpenResultLoader.load | 内码 1001050100，STEP_SUCCESS | 页面曝光不记 |
| 结果数据获取 | 失败 | OpenResultLoader.load | 内码 1001050101，STEP_ERROR_BY_ERROR，外码取结果接口返回码 | 不改写开卡结果；获取失败而开卡成功一条 |
| 开卡全流程 | 成功 | BankCardOpenFlow.finish | 内码 1001000000，SUCCESS | 一次开卡只记一次；正常开卡一条 |
| 开卡全流程 | 失败 | BankCardOpenFlow.finish | 内码 1001000001，STEP_ERROR_BY_ERROR | 卡号失败一条 |
| 开卡全流程 | 用户取消 | BankCardOpenFlow.finish | 内码 1001000010，STEP_ERROR_BY_USER | 取消一条 |
| 查询参数校验 | 通过 | OpenStatusQuery.query | 内码 1002010100，STEP_SUCCESS | 每次查询一次尝试 |
| 查询参数校验 | 无效 | OpenStatusQuery.query | 内码 1002010101，STEP_ERROR_BY_ERROR，本地校验不带外码 | 参数无效时不发请求 |
| 开卡状态查询 | 成功 | OpenStatusQuery.fetchStatus | 内码 1002020100，STEP_SUCCESS，另带查到的开卡状态 | 接口重试按实际尝试分别记；查到「开卡失败」仍记成功 |
| 开卡状态查询 | 业务失败 | OpenStatusQuery.fetchStatus | 内码 1002020101，STEP_ERROR_BY_ERROR，外码取查询接口返回码 | 业务失败一条 |
| 开卡状态查询 | 服务失败 | OpenStatusQuery.fetchStatus | 内码 1002020102，STEP_ERROR_BY_ERROR，外码取查询接口返回码 | 服务失败一条 |
| 查询整体 | 成功 | OpenStatusQuery.query | 内码 1002000000，SUCCESS | 不触发开卡流程上报 |
| 查询整体 | 失败 | OpenStatusQuery.query | 内码 1002000001，STEP_ERROR_BY_ERROR | 查询失败不改开卡结果 |

逐行核实际事件的身份、内码、分类、外码、次数与时机；另核没有新增的运营上报调用，自动上报覆盖的页面与点击没有被手工重复。

#### 9.2.3 待登记与缺依据

- 模板 `BankCard`、流程号 `001` / `002`、各步骤号是候选：实现者在目标仓登记文件里按顺序取号，coding 时核冲突，冲突就改取下一个。
- 外码所在的外部接口与字段名，在真实接口契约取证后填；影响所有带外码的行。
- 关联标识与尝试序号的字段名、类型与缺席语义，在契约的数据实体里登记；影响全部行的去重。
