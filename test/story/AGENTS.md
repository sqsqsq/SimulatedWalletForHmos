# Story 测试域维护规则

本文件用于维护 Story 测试驱动器、Case 和运行协议。被测模型不得读取、注入或转述本文件。

## 1. 优化边界

维护 Story、Spec、Extension 及其测试能力时，当前执行者是外层优化者，相关能力是被修改对象。

- 不调用 Story、Spec、Framework 的 Skill、阶段流程、Hook、Harness、Verifier 或 Goal 来优化它们自身。
- 可以直接读取、修改和检查相关源码、配置、测试与产物。
- 真实行为验证只按 [TEST.md](TEST.md) 将能力作为被测对象运行；被测流程自身结果不能代替维护验证。
- 演进背景见 [EVOLUTION.md](EVOLUTION.md)，当前运行协议只以本文件和 TEST 为准。

## 2. 测试目标与隔离

- 正式入口只有 `scripts/run_multi_case.py`；`run_case.py` 是底层单 Case 执行器。
- 即使只选一个 Case，也必须创建隔离 suite。
- 每个 Case 只能看到自身 workspace、初始任务和已发送交互，不能看到 `test/story/`、其他 Case、历史 suite 或维护材料。
- 正式 Case 是组合业务场景；叙述变形只做离线检查。
- 被测流程执行的原生 gate 只作为运行事件、状态和诊断事实保存。

## 3. 外层观察者职责

- 按 TEST 在非沙箱环境启动外层协调器；该授权不进入被测 prompt。
- Case 严格顺序启动，前一个获得有效 run-id、worker/lease 和活动状态后再启动下一个；之后并行运行。
- 启动失败时检查指针、run、worker、lease、workspace 和原始输出，尝试恢复后再决定终态。
- 未全部稳定进入 Spec 自动阶段前，每 15 秒观察全部 Case 并处理交互；连续两轮稳定后切换到 120 秒。
- 出现等待回复、阶段回退或状态异常时立即恢复 15 秒。
- 预设脚本未覆盖的交互，依据该 Case 可见输入给出继续场景所需的最小回复，并记录依据。
- 意外行为需要继续推进并记录，不是默认停测理由。
- 观察者不得替被测模型运行 gate、修改被测产物或清理阶段状态。

## 4. 状态、证据与现场

- 权威状态来自 run 的 `state.json` 和不可变 `events.jsonl`。
- `live.jsonl`、`runlog.md`、worker/gate 日志、phase results 和 artifact 副本用于解释执行过程。
- `observations.jsonl` 保存原始观察、交互和恢复记录，不加入额外裁决。
- `observation-record.md` 汇总 Case、feature、run-id、启动、阶段、状态、观测、交互、错误、回灌和保留路径。
- 退出码只表达正常完成并到达目标阶段，或 CLI、gate、恢复和基础设施失败。
- 新一轮先创建自己的 output 控制目录，再整体预检并清理安全的历史 Story workspace/output；全部成功后才把现有 features 迁移到 `E:\Project\bak\Story-Features-<时间戳>` 并启动。
- 本轮 finalize 只回灌和生成记录；workspace/output 保留到下一轮，`finalize --cleanup` 必须报错。

## 5. 修改纪律

- 先定位最早产生问题的代码或契约，局部修复并同步直接消费者。
- 不把测试答案、维护历史或其他 Case 行为写入初始 prompt。
- 新增或修改运行规则时覆盖成功、失败和恢复路径。
- 完成前运行 Story 单测、Tools CLI 检查、Python 编译和只读 plan 演练；除非用户启动正式测试，不运行真实被测 CLI。
