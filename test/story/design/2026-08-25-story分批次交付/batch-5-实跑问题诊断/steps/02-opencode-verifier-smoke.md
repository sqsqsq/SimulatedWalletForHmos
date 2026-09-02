# 步骤 2 · OpenCode verifier 专用 Spec smoke

## 目标

用一个低成本真实 CLI 需求验证步骤 1 的 OpenCode verifier 闭环，并把“Framework 能力是否成立”与“当前语义审查是否有效”
分成两个结论。此处不测试 Story 成文能力。

## 固定需求

功能名：`隐藏余额开关`。

1. “我的”页提供“隐藏余额”开关，默认关闭；
2. 开启后首页总余额显示 `****`，关闭后立即恢复真实金额；
3. 开关状态保存在本地，应用重启后保持；
4. 清除应用数据后恢复默认关闭；
5. 不上传服务端；
6. 不改变卡片余额、交易记录和支付功能。

## 测试载体

- 建立永久的 `test/story/verifier-smoke/` 专用夹具和驱动；不放进 `cases/*`，不加入 Story `--all`。
- 预置 full track 与最小有效工程事实，直接进入 Spec；不经过 `/story`，不使用需求系统、补料、图片、范围选择或人工决策。
- 终点只有 Spec 闭环，不生成 Story/Review，不进入 Plan。
- 默认使用 `volcengine-glm-flash`，实际结论绑定最终运行的 `cli_config_id`；认证或环境失败时不静默切换配置，由维护者决定重跑配置。
- 夹具用稳定确认 ID 维护必要的回复及触发时机；未知问题停等，不按 turn 序号盲答。
- 显式命令和产物位置只写入 `TEST.md` 的 verifier smoke 专节。

## 观察点

按时间顺序保留：主 OpenCode session、Framework request、独立 verifier 身份与 session、只读工具记录、终稿事件、
`verifier.report.<subject>.json`、receipt 和 closure。报告必须能从这些原始证据重建，不只截取控制台结论。

若 verifier request 生成前出现 Research、术语、UI/视觉、track 或冻结门的 BLOCKER，结果归为 `environment_or_fixture_failed`：
修夹具或环境后重跑，不计为 D1 adapter 失败，也不在驱动中绕过 Framework 门禁。

## 两个结论

### A. Framework 能力

链路完整、身份可信、反向篡改被拒绝即可通过。若 OpenCode 无法提供步骤 1 依赖的原生事件，回开步骤 1并标记阻塞。

### B. 批次 5 继续条件

检查 verifier 是否真正阅读六条需求与 Spec，是否能给出与目标产物相关的判断。语义不足不抹掉已成立的 Framework 能力结论，
但步骤 3 以后保持暂停，先调整步骤 7 的 verifier 任务与资格门。

## 允许范围

- `test/story/verifier-smoke/**`、对应测试；
- `test/story/TEST.md`；
- 本步 STATUS 和评审报告。

Framework 或 Extension 若暴露缺陷，回到步骤 1或未来责任步骤修，不在 smoke 驱动里兼容。

## 完成条件

- 专用 smoke 可独立、重复、显式运行，且不改变现有 Story Case 发现与统计；
- 六条需求输入和 full track 均由夹具冻结，运行没有隐藏人工回答；
- 所有必要确认均有按稳定 ID 匹配的固定回复，事件记录能证明回复发生在正确时机；
- Framework 能力结论和语义观察结论分别记录；
- 合法 verifier 报告完成 Spec receipt/closure；运行前后产品源码零差异；
- 墙钟、模型、上下文、返修和等待时间均留痕，但本次时长不作为 Story 半小时 KPI。
- 报告写明实际 `cli_config_id`；该结论不外推到其他模型配置。
