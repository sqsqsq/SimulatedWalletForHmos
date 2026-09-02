# 步骤 4 · Framework interactive 作者上下文入口

## 授权门

本步骤涉及 Framework。用户只授权了步骤 1；开始步骤 4 前必须重新取得是否允许在本工程修改 `framework/` 的明确决定。
未获授权时状态为 `阻塞`，不得用 Extension wrapper、根 AGENTS 加长或上游产物注入替代。

## 目标

让 interactive 执行者在进入 phase、写主产物之前，取得 Framework → profile → Extension 的 `on_context_load` 内容。
复用现有 extension loader、hook dispatcher 和 `promptFragments`，不建立新生命周期或上下文状态。

## Framework 实施内容

1. 提供一个只读的 phase 作者入口：接收 project root、feature 和 phase，调用现有 dispatcher 的 `on_context_load`；
2. 将片段直接输出给当前 interactive 作者，缺席返回空，执行错误明确失败；
3. 共享行为规约要求六个 feature Skill 在动笔前调用该入口；五个已有入口保持，补齐 device-testing 缺失引用；
4. 从 harness 后置 verifier 装配处删除 `on_context_load`，`pre_verifier` 继续只服务 verifier；
5. 不写 summary、receipt、hash、phase 状态或业务产物。

## 允许范围

- 现有 loader、dispatcher 的薄调用入口及其测试；
- `harness-runner` 中错误的后置消费点；
- 共享 agent 行为规约与 device-testing 的缺失指针；
- lifecycle schema/概念文档中与实际时序直接相关的内容；
- 仍把 `hooks/<phase>/on_context_load.md` 描述成模板叠加来源的 profile spec/plan 模板及同类直接引用；
- `TEST.md` 对应测试入口。

不修改 Extension 内容、adapter、closure、track、headless/goal 或其它 phase 业务规则。

## 完成条件

- 无 Extension / 无 hook → 空结果且原行为不变；
- Framework、profile、Extension 三层 → 顺序与 dispatcher 一致；
- Markdown 与 MJS → 内容都能在作者动作前到达；
- hook 失败 → 明确失败，不降级为空；
- correction、跨会话恢复和直接 phase 入口 → 都经过同一作者入口；
- verifier prompt → 不再包含 `on_context_load`；
- profile 模板和概念文档 → 描述新的作者起手消费时序，不再暗示 harness 后置注入；
- 六个 phase → 共享同一规则，不在六份 Skill 复制实现说明。

本步只用最小 phase 夹具，不运行真实 Story。
