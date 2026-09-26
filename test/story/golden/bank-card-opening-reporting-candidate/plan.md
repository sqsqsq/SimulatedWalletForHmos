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
- **描述**：统计点上只报这一条统计事件，定位要用的原因、场景与关键状态写进描述，不另报定位事件；要本地日志时直接写日志。每种结果一句固定说法，拼本次关键值（见逐点表），不带卡号、证件、验证码或人脸资料。
- **尝试**：一次开卡关联标识与尝试序号由开卡业务控制者持有，走项目允许的扩展参数；去重键是「一次开卡＋节点与子点＋这一点的尝试序号」。
- **登记位置**：目标仓业务码登记文件，开卡与查询同一份，首用新建。

#### 9.2.2 逐点实现

| 统计点 | 结果 | 责任方法 | 字段取值 | 描述 | 去重与验证 |
|---|---|---|---|---|---|
| 卡号校验 | 通过 | BankCardOpenFlow.submitInfo | 内码 1001010100，STEP_SUCCESS | 「卡号校验通过」，拼卡 BIN 识别出的卡类型 | 每次提交一次尝试；合法卡号一条 |
| 卡号校验 | 不通过 | BankCardOpenFlow.submitInfo | 内码 1001010101，STEP_ERROR_BY_ERROR，本地校验不带外码 | 「卡号校验不通过」，拼未通过的规则（长度 / 校验位 / 不支持的卡 BIN，取自本地校验结果） | 非法卡号一条 |
| 身份校验 | 通过 | IdentityCheckService.check | 内码 1001010200，STEP_SUCCESS | 「身份校验通过」 | 卡号不通过时不发起、不记 |
| 身份校验 | 拒绝 | IdentityCheckService.check | 内码 1001010201，STEP_ERROR_BY_ERROR，外码取身份校验接口返回码 | 「身份校验被拒」，拼接口返回的拒绝原因说明 | 拒绝一条 |
| 身份校验 | 服务异常 | IdentityCheckService.check | 内码 1001010202，STEP_ERROR_BY_ERROR，外码取身份校验接口返回码 | 「身份校验服务异常」，拼异常类型（超时 / 网络 / 服务端错误，取自请求异常） | 服务异常一条 |
| 信息校验整体 | 成功 | BankCardOpenFlow.submitInfo | 内码 1001010000，STEP_SUCCESS | 「信息校验完成」，拼这是本次开卡第几次提交（取自尝试序号） | 同一提交的重复通知不重报 |
| 信息校验整体 | 失败 | BankCardOpenFlow.submitInfo | 内码 1001010001，STEP_ERROR_BY_ERROR | 「信息校验失败」，拼失败的子点（卡号校验 / 身份校验） | 更正卡号后再提交记两次尝试 |
| 信息校验整体 | 用户取消 | BankCardOpenFlow.submitInfo | 内码 1001010010，STEP_ERROR_BY_USER | 「信息校验阶段用户取消」，拼取消时所在子点 | 用户终止一条 |
| 验证码发送 | 受理 | SmsVerifyController.send | 内码 1001020100，STEP_SUCCESS | 「验证码已受理」，拼首次或第几次重发（取自发送计数） | 每次发送或重发一次尝试；重发记两条 |
| 验证码发送 | 业务拒绝 | SmsVerifyController.send | 内码 1001020101，STEP_ERROR_BY_ERROR，外码取短信接口返回码 | 「验证码发送被拒」，拼接口返回的拒绝原因说明 | 业务拒绝一条 |
| 验证码发送 | 服务失败 | SmsVerifyController.send | 内码 1001020102，STEP_ERROR_BY_ERROR，外码取短信接口返回码 | 「验证码发送服务失败」，拼异常类型 | 服务失败一条 |
| 验证码校验 | 通过 | SmsVerifyController.verify | 内码 1001020200，STEP_SUCCESS | 「验证码校验通过」，拼这是第几次输入 | 每次提交验证码一次尝试；先错后对记两条 |
| 验证码校验 | 错误 | SmsVerifyController.verify | 内码 1001020201，STEP_ERROR_BY_ERROR，外码取校验接口返回码 | 「验证码错误」，拼这是第几次输入 | 错误一条，重输是新尝试 |
| 验证码校验 | 过期 | SmsVerifyController.verify | 内码 1001020202，STEP_ERROR_BY_ERROR，外码取校验接口返回码 | 「验证码过期」，拼距发送的秒数（取自发送时刻） | 过期一条 |
| 验证码校验 | 服务失败 | SmsVerifyController.verify | 内码 1001020203，STEP_ERROR_BY_ERROR，外码取校验接口返回码 | 「验证码校验服务失败」，拼异常类型 | 服务失败一条 |
| 短信验证整体 | 成功 | SmsVerifyController.verify | 内码 1001020000，STEP_SUCCESS | 「短信验证完成」，拼共输入几次 | 可恢复的输错不结束整体；先错后对只记一条成功 |
| 短信验证整体 | 失败 | SmsVerifyController.verify | 内码 1001020001，STEP_ERROR_BY_ERROR | 「短信验证失败」，拼无法继续的原因（输错次数用尽 / 过期未重发 / 服务失败） | 无法继续时一条 |
| 短信验证整体 | 用户取消 | SmsVerifyController.verify | 内码 1001020010，STEP_ERROR_BY_USER | 「短信验证阶段用户取消」，拼已发送次数 | 用户退出一条 |
| 活体检测 | 通过 | FaceVerifyController.detect | 内码 1001030100，STEP_SUCCESS | 「活体检测通过」 | 中止后迟到的回调不改结果 |
| 活体检测 | 不通过 | FaceVerifyController.detect | 内码 1001030101，STEP_ERROR_BY_ERROR，外码取活体组件返回码 | 「活体检测不通过」，拼活体组件返回的原因说明 | 不通过一条 |
| 活体检测 | 用户中止 | FaceVerifyController.detect | 内码 1001030110，STEP_ERROR_BY_USER | 「活体检测用户中止」，拼中止时的检测阶段（取自活体组件回调） | 中止后迟到回调仍一条 |
| 身份比对 | 一致 | FaceVerifyController.compare | 内码 1001030200，STEP_SUCCESS | 「身份比对一致」 | 活体未通过不发起、不记 |
| 身份比对 | 不一致 | FaceVerifyController.compare | 内码 1001030201，STEP_ERROR_BY_ERROR，外码取比对接口返回码 | 「身份比对不一致」，拼比对接口返回的原因说明 | 不一致一条 |
| 身份比对 | 服务异常 | FaceVerifyController.compare | 内码 1001030202，STEP_ERROR_BY_ERROR，外码取比对接口返回码 | 「身份比对服务异常」，拼异常类型 | 服务异常一条 |
| 人脸核验整体 | 成功 | FaceVerifyController.compare | 内码 1001030000，STEP_SUCCESS | 「人脸核验完成」 | 检测与比对都有结果时一条 |
| 人脸核验整体 | 核验失败 | FaceVerifyController.compare | 内码 1001030001，STEP_ERROR_BY_ERROR | 「人脸核验失败」，拼失败的子点（活体检测 / 身份比对） | 核验失败一条 |
| 人脸核验整体 | 拒绝授权 | FaceVerifyController.compare | 内码 1001030002，STEP_ERROR_BY_ERROR | 「人脸核验拒绝授权」，拼被拒的权限（取自权限回调） | 拒绝授权不编子点结果；一条 |
| 人脸核验整体 | 用户取消 | FaceVerifyController.compare | 内码 1001030010，STEP_ERROR_BY_USER | 「人脸核验阶段用户取消」，拼取消时所在子点 | 用户中止一条 |
| 开卡申请 | 受理 | CardOpenService.apply | 内码 1001040100，STEP_SUCCESS | 「开卡申请已受理」 | 同一申请只记一次 |
| 开卡申请 | 业务拒绝 | CardOpenService.apply | 内码 1001040101，STEP_ERROR_BY_ERROR，外码取开卡接口错误码 | 「开卡申请被拒」，拼开卡接口返回的拒绝原因说明 | 业务拒绝一条 |
| 开卡申请 | 服务异常 | CardOpenService.apply | 内码 1001040102，STEP_ERROR_BY_ERROR，外码取开卡接口错误码 | 「开卡申请服务异常」，拼异常类型 | 服务异常一条 |
| 本地写入与激活确认 | 成功 | CardOpenService.writeCard | 内码 1001040200，STEP_SUCCESS | 「写卡与激活确认成功」，拼是否经过待确认查询 | 待确认查明后只记一次；超时待确认、查明成功一条 |
| 本地写入与激活确认 | 失败 | CardOpenService.writeCard | 内码 1001040201，STEP_ERROR_BY_ERROR，外码取写卡组件返回码 | 「写卡与激活确认失败」，拼失败环节（本地写入 / 激活确认，取自写卡组件回调） | 失败一条 |
| 写卡整体 | 成功 | CardOpenService.writeCard | 内码 1001040000，STEP_SUCCESS | 「写卡完成」 | 动画与页面生命周期不触发；动画先于确认结束时不提前记 |
| 写卡整体 | 失败 | CardOpenService.writeCard | 内码 1001040001，STEP_ERROR_BY_ERROR | 「写卡失败」，拼权威结果与本地写入各自的状态 | 权威结果与本地写入都确定时一条 |
| 结果数据获取 | 成功 | OpenResultLoader.load | 内码 1001050100，STEP_SUCCESS | 「开卡结果数据获取成功」 | 页面曝光不记 |
| 结果数据获取 | 失败 | OpenResultLoader.load | 内码 1001050101，STEP_ERROR_BY_ERROR，外码取结果接口返回码 | 「开卡结果数据获取失败」，拼异常类型 | 不改写开卡结果；获取失败而开卡成功一条 |
| 开卡全流程 | 成功 | BankCardOpenFlow.finish | 内码 1001000000，SUCCESS | 「开卡完成」 | 一次开卡只记一次；正常开卡一条 |
| 开卡全流程 | 失败 | BankCardOpenFlow.finish | 内码 1001000001，STEP_ERROR_BY_ERROR | 「开卡失败」，拼失败所在步骤（信息校验 / 短信验证 / 人脸核验 / 写卡） | 卡号失败一条 |
| 开卡全流程 | 用户取消 | BankCardOpenFlow.finish | 内码 1001000010，STEP_ERROR_BY_USER | 「开卡用户取消」，拼取消时所在步骤 | 取消一条 |
| 查询参数校验 | 通过 | OpenStatusQuery.query | 内码 1002010100，STEP_SUCCESS | 「查询参数校验通过」 | 每次查询一次尝试 |
| 查询参数校验 | 无效 | OpenStatusQuery.query | 内码 1002010101，STEP_ERROR_BY_ERROR，本地校验不带外码 | 「查询参数无效」，拼无效的参数项名 | 参数无效时不发请求 |
| 开卡状态查询 | 成功 | OpenStatusQuery.fetchStatus | 内码 1002020100，STEP_SUCCESS，另带查到的开卡状态 | 「开卡状态查询成功」，拼查到的开卡状态 | 接口重试按实际尝试分别记；查到「开卡失败」仍记成功 |
| 开卡状态查询 | 业务失败 | OpenStatusQuery.fetchStatus | 内码 1002020101，STEP_ERROR_BY_ERROR，外码取查询接口返回码 | 「开卡状态查询业务失败」，拼查询接口返回的原因说明 | 业务失败一条 |
| 开卡状态查询 | 服务失败 | OpenStatusQuery.fetchStatus | 内码 1002020102，STEP_ERROR_BY_ERROR，外码取查询接口返回码 | 「开卡状态查询服务失败」，拼异常类型 | 服务失败一条 |
| 查询整体 | 成功 | OpenStatusQuery.query | 内码 1002000000，SUCCESS | 「开卡结果查询完成」，拼查到的开卡状态 | 不触发开卡流程上报 |
| 查询整体 | 失败 | OpenStatusQuery.query | 内码 1002000001，STEP_ERROR_BY_ERROR | 「开卡结果查询失败」，拼失败的子点（参数校验 / 状态查询） | 查询失败不改开卡结果 |

逐行核实际事件的身份、内码、分类、外码、描述、次数与时机；另核统计点上没有另报定位事件、没有新增的运营上报调用，自动上报覆盖的页面与点击没有被手工重复。

#### 9.2.3 待登记与缺依据

- 模板 `BankCard`、流程号 `001` / `002`、各步骤号是候选：实现者在目标仓登记文件里按顺序取号，coding 时核冲突，冲突就改取下一个。
- 外码所在的外部接口与字段名，在真实接口契约取证后填；影响所有带外码的行。
- 关联标识与尝试序号的字段名、类型与缺席语义，在契约的数据实体里登记；影响全部行的去重。
