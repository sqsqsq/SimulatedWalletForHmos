# 步骤 3 · 测试观测与效率事实

## 目标

修复 P8/P9/P10，使后续方案只依据真实事件、真实阶段和真实材料版本评价行为。本步只改测试域，不改变 Framework 或 Extension。

## 实施内容

1. `measure_run.py` 同时读取事件的正文、`tool_input` 与 `tool_output`，按当前输出协议提取 check id、失败轮次和源码读取；
2. 用固定事件样本覆盖 Windows 编码、空输出、多次 check、失败后恢复和不同 tool 输出形态；每个指标必须有能改变结果的正反样本；
3. `highest_phase_reached` 只由 Framework 状态和真实阶段产物推进；目标阶段、runner hint、准备执行 gate 和模型口头宣告均不能升级；
4. 新增“只补图片也改变材料 manifest digest、形成新材料版本”的行为测试；不借此修改 Extension 产品行为；
5. 保留人工等待独立计时；Story/Review 作者、确定性检查、verifier、返修、总墙钟、上下文增长和 checker 源码读取分别统计；
6. 批次 5 白名单和唯一金样路径只做回归确认，不再建立第二份状态记录。

## 允许范围

- `test/story/scripts/measure_run.py`、`observe.py`、`phase_state.py`、`run_case.py`、必要的直接测试；
- `test/story/TEST.md`；
- 仅为构造固定事件样本新增的测试夹具。

若修复必须改变 Framework 阶段语义或 Extension 材料版本定义，停止并回报责任错位，不在测试域模拟产品状态。

## 完成条件

- P8 的每个缺失指标都由固定样本证明“有事件时非零、无事件时为零/未知”，乱码不影响分类；
- P10 的两个历史假阳性样本不再被记为到达 Plan，真实 Plan 产物样本仍能升级；
- 图片-only 补料测试能区分内容不变与资产改变；
- 现有 Case 计划、交互脚本和输出目录协议不变；
- 不运行真实 CLI 或 Story；全部测试命令只在 `TEST.md` 维护。
