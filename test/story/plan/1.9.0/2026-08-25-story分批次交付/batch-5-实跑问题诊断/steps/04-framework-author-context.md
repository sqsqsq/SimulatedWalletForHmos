# 步骤 4 · Framework interactive 作者上下文入口

## 授权门

本步骤涉及 Framework。**用户 2026-09-03 已授权本步在当前工程直接修改 vendored `framework/`**（记录见 STATUS 事件日志），
授权范围 = 本文「允许范围」；与步骤 1 同样的纪律：`framework.config.json` 只为本步实际修改的文件加真人具名 drift allowlist，
条目写明「上游合入后即失效」；产出以 `RELEASE-MANIFEST.json.source_commit` 为基线的上游补丁与交接件（`artifacts/04-*`）。
不得用 Extension wrapper、根 AGENTS 加长或上游产物注入替代。

## 为什么要改 Framework（实证）

8 月 30 日以来 25 次实跑里，作者读到 `hooks/<phase>/author.md` 的时间与主产物首次落盘的时间对照：
spec 阶段 16 次里 14 次在写之前读到——因为 `/story` 链自己指向 spec 的 author.md；
到达 plan 的 3 次全部先写 `plan.md` 再读 author.md，晚 2～70 分钟；到达 coding 的 1 次先改代码后读。
内网反馈「仅 spec 生效」与此一致。根 AGENTS 的远距离提醒只在有 `/story` 链牵着的那一段生效，其余五个阶段没有任何
在写产物前送达作者的通道；Framework 侧 `hooks-dispatcher.ts:162` 已能把 md/mjs 钩子产出 promptFragments，
但全仓唯一调用点 `harness-runner.ts:1069` 在 verifier 装配处——通道存在、接错了对象。本步只把它接到作者一侧。

## 目标

让 interactive 执行者在进入 phase、写主产物之前，取得 Framework → profile → Extension 的 `on_context_load` 内容。
复用现有 extension loader、hook dispatcher 和 `promptFragments`，不建立新生命周期或上下文状态。

## Framework 实施内容

1. 提供一个只读的 phase 作者入口：接收 project root、feature 和 phase，调用现有 dispatcher 的 `on_context_load`；
2. 将片段直接输出给当前 interactive 作者，缺席返回空，执行错误明确失败；输出保留 dispatcher 已有的来源标识行
   （`<!-- hook:on_context_load:<source>:<文件名> -->`），作者据此把读过的钩子源路径写进 `context-exploration.md` 的
   `key_inputs_read`——这是它被读过的唯一留痕，不另建状态；
3. 共享行为规约要求六个 feature Skill 在动笔前调用该入口；五个已有入口保持，补齐 device-testing 缺失引用；
4. 从 harness 后置 verifier 装配处删除 `on_context_load`，`pre_verifier` 继续只服务 verifier；
5. 不写 summary、receipt、hash、phase 状态或业务产物。

**留痕借用既有门禁，不新增门禁**：`context-exploration.ts:512` 的 `context_exploration_inputs_coverage` 已要求
`key_inputs_read` 覆盖本阶段最低输入，必需片段来自 `resolvePhaseInputSnippets(...)`，其中
`phaseRule.exploration_thresholds.phase_input_snippets_extra` 由 phase rule overlay 合入（`profile-loader.ts:96-99` 浅合并）。
Extension 在步骤 5 用自己的 overlay 声明「本阶段的 author 钩子源路径」为必需片段即可；作者没读、没登记，就在这条既有门禁上 FAIL。
本步 Framework 侧对此**零改动**，只需保证入口输出里的来源标识与 overlay 将声明的片段是同一个字符串（钩子的仓内相对路径）。

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
- 六个 phase → 共享同一规则，不在六份 Skill 复制实现说明；
- 入口输出的每个片段都带来源标识行，标识即钩子的仓内相对路径，可被 `key_inputs_read` 逐字覆盖；
- 上游补丁 `artifacts/04-framework-author-context.patch` 在 `source_commit` 基线上 `git apply --check` 通过，
  与本仓逐字节一致；allowlist 条目带失效条件。

本步只用最小 phase 夹具，不运行真实 Story。
