# 步骤 4 上游交接：interactive 作者上下文入口

## 这份补丁做什么

`on_context_load` 钩子一直能产出 promptFragments（`hooks-dispatcher.ts`），但全仓**唯一**的调用点
在 `harness-runner.ts` 的 verifier 装配处——**通道存在、接错了对象**。那些「写之前该知道什么」
只进了 verifier 的上下文，作者一次也看不到。

本补丁把同一条通道接到作者一侧：新增只读入口 `harness/scripts/author-context.ts`，执行者在
**进入 phase、动笔之前**跑一次。**不新增生命周期、hook、状态或 adapter 能力**。

## 实证（改之前的现场）

消费仓 8 月 30 日以来 25 次实跑，作者读到 `hooks/<phase>/author.md` 的时刻 vs 主产物首次落盘：

| 阶段 | 到达次数 | 写之前读到 | 写之后才读到 |
|---|---|---|---|
| spec | 16 | 14 | 2 |
| plan | 3 | 0 | 3（晚 2～70 分钟） |
| coding | 1 | 0 | 1 |

spec 之所以正常，是因为实例的 `/story` 链自己指向了 spec 的 author.md——**不是机制在起作用**。
其余五个阶段没有任何在写产物前送达作者的通道。内网反馈「仅 spec 生效」与此一致。

## 基线与应用

| 项 | 值 |
|---|---|
| 补丁文件 | `04-framework-author-context.patch` |
| 基线 | `RELEASE-MANIFEST.json` 的 `source_commit` = `7401f221daf1bca082176bc87f61ea94506b4955`（3.0.0） |
| 路径基准 | Framework 仓根（已剥掉消费仓的 `framework/` 前缀） |
| 验证 | 纯净 framework 树上 `git apply` 通过，结果与消费仓逐字节一致（行尾归一） |

## 十二个文件

| 文件 | 改动 |
|---|---|
| `harness/scripts/author-context.ts` | **新增**。只读入口：`--phase` / `--feature` / `--json`；复用 `loadResolvedProfile` + `dispatchLifecycleHooks` |
| `harness/hooks-dispatcher.ts` | 片段来源标识由**文件名**改为**仓内相对路径** |
| `harness/harness-runner.ts` | 删掉 verifier 装配处的 `emitLifecycle('on_context_load')` |
| `skills/reference/agent-behavioral-principles.md` | 原则 1 增「约束 0：动笔前跑作者起手入口」——六阶段共用一处 |
| `skills/feature/device-testing/SKILL.md` | 补上缺失的行为规约引用（其余五个 Skill 本就有） |
| `skills/feature/spec/SKILL.md`、四份 profile spec/plan 模板 | 时序订正：不再暗示由 harness 后置注入 |
| `specs/lifecycle-hooks-schema.yaml`、`docs/concepts/phase-terminology.md` | 同上，事件描述改为作者起手消费 |

## 两处值得单独说明的裁决

**1. 来源标识必须是仓内相对路径，不能是文件名。**
六个阶段的实例扩展钩子都叫 `author.md`；只写 basename 时六个片段的标识一模一样——既指不出是
哪一阶段的，也没法被 `context-exploration.md` 的 `key_inputs_read` 逐字覆盖（那条既有门禁做
子串匹配，`author.md` 会命中任何阶段，等于不设防）。改成相对路径后，标识本身就是唯一坐标。
越出工程根时退回绝对路径的 posix 形态，如实指出它在树外。

**2. 留痕借用既有门禁，不新增门禁。**
`context_exploration_inputs_coverage` 已要求 `key_inputs_read` 覆盖本阶段最低输入，必需片段来自
`resolvePhaseInputSnippets`，其中 `phase_input_snippets_extra` 由 phase rule overlay 合入。
实例只需在自己的 overlay 里声明「本阶段 author 钩子的仓内相对路径」，作者没读没登记就在这条
既有门禁上 FAIL。**Framework 侧对此零改动**，只保证入口输出的标识与 overlay 声明是同一个字符串。

## 消费者验证情况

- 13 条行为回归：六阶段各取到自己那一份、标识是相对路径而非文件名、互不串台、
  无扩展→空且零失败、钩子抛错→明确失败不降级为空、入口无写操作、
  `harness-runner` 不再发 `on_context_load`；
- 五个受 context-exploration 门禁的阶段声明的字符串与入口输出的标识逐字一致；`testing` 无该门禁、
  如实不声明；
- 离线全绿：story 551（含 1 条已登记的 expectedFailure）、cli 18、失效形态 73/73、
  `framework_integrity` / `framework_foreign_file` / manifest 自校验；
- 未运行真实 Story（按步骤边界，只用最小 phase 夹具）。

## 交付边界

**消费仓验证通过 ≠ 内网已获得该能力。** 本地改动靠 `framework.config.json` 的
`integrity.drift_allowlist` 具名放行，下一次 `framework-init UPDATE` 会把它冲掉。
上游合入并发布前，内网仍是「只有 spec 生效」的老样子。

**allowlist 失效条件**：上游补丁经 framework-init UPDATE 回到消费仓后，本步的 12 条 allowlist
条目即失效，**必须删除**——留着会掩盖真实漂移。条目的 `rationale` 里已写明。
