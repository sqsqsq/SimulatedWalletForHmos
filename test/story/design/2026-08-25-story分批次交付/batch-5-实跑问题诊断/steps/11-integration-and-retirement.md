# 步骤 11 · 集成实跑、73 条收口与旧发现者退场

## 目标

在新作者任务、确定性生成、Knowledge 链、独立 verifier 和测试观测全部集成后，运行一次现有真实 Story，确认新产物没有相对
金样和历史期望退化；通过后才删除旧回归发现者和无消费者资产。

## 实跑选择

默认只运行 `auto-topup` 到 Spec：它同时覆盖需求系统、按需 docx 补料、图片、范围/承载、Story/Review、Knowledge 和 verifier，
且终点早于 `car-key-sharing` 的 Plan，能以较低成本覆盖本批主要风险。若步骤 1～10 出现它不覆盖的高风险事实，由用户决定是否增加
第二个 Case；机制不写死数量。

实跑配置只能从步骤 7 的通过集合选择，并在开始前冻结 `cli_config_id`；优先使用与可比较历史轮次相同且资格通过的配置。

正式命令、观察和收工方式只按 `TEST.md`。实跑前冻结当前提交、CLI/模型配置、Case 输入和旧发现者状态。

## 实跑验收

### 产物质量

- Story 十章齐备且核心章内容与实际材料复杂度相称，不以空泛短句占位；
- 与金样比较信息架构、详略、表达形态、主叙事/附录分工、图文位置和评审可用性；
- 不要求字数、表格数、图片数或小节数相等；
- Review 来自 Story 后的最终 decisions，未决与已定清楚；
- 范围内关键事实、关系、流程、异常、验收和交付没有明显遗漏或编造。

### Agent 行为

- 作者在动笔前收到任务包，不读 `test/story`、历史方案或 checker 源码；
- 确定性检查不教授首次规则；verifier 来自独立上下文；
- blocker/advisory 分开，返修问题总体收敛；
- Knowledge 三类在正确时机进入并传递；
- 记录作者、脚本、verifier、返修、人工等待、总墙钟和上下文增长。半小时是期望指标，超出不自动失败，但须解释主要耗时。
- 结果只支持所用 `cli_config_id`，不外推到未通过资格门的宿主/模型。

## 73 条与清理

实跑通过后：

1. 对 `failure-modes.yaml` 73 条逐项登记现行责任：deterministic、verifier、generated_by_construction、behavior_test 或 retired；
2. 42 条长期不变量全部有发现者；27 条用新目标重写 form/checker/applicable_when；
3. M08、M12、M15、R04 只有在旧消费者确实消失后，提交 reason 并取得用户批准再标 retired；
4. 删除旧回归 checker、夹具、配置和产品 helper 前再次扫描消费者；
5. 按步骤 7 已作出的消费者决定执行 `baseline_coverage.py` 清理；本步不再重新讨论它是否属于新质量口径；
6. 全树检查死代码、静默空集、TODO、悬空引用、双入口和测试特征。

若实跑失败，步骤 11 不修产品：按责任重新打开步骤 5～10，写明最早失效点。修复步骤重新评审并提交后，再重跑本步骤。

## 允许范围

- 实跑证据、度量与本步骤评审报告；
- `failure-modes.yaml`、`check_failure_modes.py`、旧夹具/历史诊断工具的最终清理；
- 仅由清理造成的悬空引用和测试索引修正。

不得在本步改变 Story、Knowledge 或 Framework 业务行为；发现行为问题必须回开原步骤。

## 完成条件

- 真实 Story 的产物质量、Agent 行为、Knowledge 链和 Framework verifier 均通过独立评审；
- 73 条数量对账仍为 73，所有非 retired 条目有能区分 good/bad 的现行发现者；
- 纯旧实现条目得到用户批准后才 retired；
- 正式路径不存在 source-units/audit/paraphrase 语义代理、旧入口、长期兼容或无消费者代码；
- 全量离线测试、金样测试、Extension 机制扫描和 Git 范围检查通过；
- 最终报告如实记录未运行的 Case、性能偏差与剩余风险。
- STATUS 明确本仓 D1 验证与上游/内网发布是两个状态；上游尚未合入时不得宣称内网 P3 已解决。
