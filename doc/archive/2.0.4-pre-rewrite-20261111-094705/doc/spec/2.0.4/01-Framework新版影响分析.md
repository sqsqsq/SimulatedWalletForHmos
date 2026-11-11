# Framework 新版（main 900c508d）影响分析

2026-11-10，维护设计者（Claude Opus）。对象：本仓 `origin/main` 从 ff111909 到 900c508d 的 7 个提交（10-27 至 11-09），`framework/` 下 220 个文件、+14351/−14680 行；发布清单版本仍为 3.1.0，source_commit 从 `879f1e8b` 变为 `bd06421c`。只读新树，没有改 demo、Extension 或测试。证据在 `output/evidence/2.0.4-framework-main/20261110/`（提交清单、改动面、新旧迁移说明、消费面对照、补丁检查）。对照依据：[2.x 适配根因诊断](../../diagnosis/2026-11-09-104441-2.x适配根因诊断.md)、[C02 预跑效果评审](../../plan/2.0.3/2026-11-06-机制集中收敛/03-批次-观测与效果/评审意见/2026-11-09-092702-C02预跑效果评审.md) §8。

- **上游解决了什么**：
  - F1（已解决的 gap 无法被引用）已解决；
  - 蓝图作者在**受管初始设计**里能一次拿到 schema 路径、字段职责、当前切片与精确命令，F3 在这条路上有缓解；
  - 切片与准入改由机器维护，带未决需求有了合法出路：未决部分切到远期切片；
  - 预算与轮次上限取消，按阶段停等也取消了。
- **仍未解决**：
  - CU 门禁对当前切片的 `open_decision`、`blocker`、`unknown` 照旧拦截；
  - 受管初始设计**不注入 Extension 知识**；
  - Story 与蓝图的关系、评审投影的组织（F2）、平铺 Feature 的地位都没变；
  - 上游自己声明这批“不代表已发布或 P4 宿主验收通过”。
- **对 2.0.4 的影响**：
  - 推进授权规则被重写，Story 的推进契约与设计页第六节必须改；
  - S4 继续由 Extension 以“直接设计请求”驱动，正式完整交付暂不交给受管初始设计，同时向上游提扩展点；
  - CU 认领语义改了，作者指引要改；
  - 本地补丁 21 个文件里有 2 个要重做；
  - 其余诊断与 C02 整改项照旧要做。

## 1. 新版的主要变化

| 变化 | 依据（新 main） | 与 Extension 的关系 |
|---|---|---|
| 正式完整请求从原始需求进入同一 Goal runtime：初始设计、独立质询、准入、CU 接受、施工连续推进；会话用 `prepare-run / next / report`，后台用 `goal-runner --detach` | `MIGRATION.md` 第 24–34 行；`skills/reference/app-component-blueprint-workflow.md` 第 13 行；`harness/scripts/utils/initial-design-delivery.ts` | Extension 的 S4 是“交给设计、止于 readiness、再成文 Story”，与“一路推进到施工”的受管路线不同（§3.2） |
| spec/plan/coding 等不再是冷启动的阶段，而是“方法和检查族”；每个 root、CU、request 有专用作者；标注为当前开发、未经 P4 宿主验收 | `MIGRATION.md` 第 1–13 行 | 只影响受管完整交付；专项请求保留原终点 |
| 推进授权重写：`manual`、`batch_authorized`、`goal_mode` 三种策略和 `phase.next_step`、`*.ok_to_*` 闸门退出，改为“明确授权的完整交付由同一完成协调器持续推进，专项请求止于原终点” | `skills/reference/user-confirmation-ux.md` §8（第 209–213 行） | Story `SKILL.md:79` 引用的 §8.1、§8.2 已不存在（§3.1） |
| CU 认领语义：`design_refs` 只写作者选择承担的交付目标；整批活动 CU 要认领全部必需设计义务；闭包由机器派生，不回写 | `harness/scripts/utils/change-unit-design-gate.ts` 第 31–67 行（`readChangeUnitDesignOwnership`）、第 248–264 行；`docs/concepts/blueprint-design-inputs.md` 第 20 行；`skills/project/component-design/SKILL.md` 第 17 行 | 设计页和蓝图作者页里 CU 候选的写法要改（§3.3） |
| 准入整块（含当前切片编号）由 runtime 写回，作者只在 `gap.needed_by` 引用切片；远期切片的 `open_decision` 可以停放 | `blueprint-admission.ts` 第 53、96–103 行；`blueprint-discovery.ts` 第 271–281 行；`app-component-blueprint-workflow.md` 第 352 行起 | 给“带未决需求到不了 Plan”提供了合法出路（§2） |
| 取消默认调用次数、返修次数与总墙钟配额，改用 `no_progress_guard` 与用户截止时间 | `MIGRATION.md` 第 8 行、第 16–20 行 | 降低“预算耗尽中止”的风险，不改变耗时本身 |
| dsh 适配：输出改为 streaming，声明阶段上下文隔离、可恢复、双向交接 | `agents/deepseek-harness/adapter.yaml` | 本地补丁与测试配置要按新声明重核（§3.4） |

## 2. 现有问题是否解决

| 问题 | 判定 | 依据 |
|---|---|---|
| F1：闭包要求显式引用已解决的 gap，而 gap 无法被引用 | **已解决** | 显式闭包核对被删（旧版约 223–234 行），改为整批 CU 认领义务；`completeChangeUnitDesignRefs` 退出 |
| 结构问题一：当前切片带未决就到不了 Plan | **原则未变，出现合法出路** | `dispositionBlocks`（第 137–143 行）与 `change_unit_current_design_unresolved`（第 266–275 行）原样保留。但切片由机器维护，未决能力可以切到远期切片、当前切片写成已定的保守行为（金样 auto 对 D4 就是这样写的）；当前切片里的 `blocker` 仍然绕不过（car 的草稿持久化缺口属于这一类） |
| F3：蓝图载体要靠读校验器源码学 | **部分缓解** | 只在受管初始设计里，作者提示会给出三份 schema 的路径、字段职责、当前切片与检查命令（`initial-design-delivery.ts` 第 458–520 行）；直接设计请求走 component-design 技能本身，指纹仍要先写占位、再跑检查回填，没有独立的计算入口 |
| F2：评审投影把人读主文与全量参考混在一起 | **未变** | `blueprint-review-projection.ts` 只新增“独立质询处理结果”一节 |
| 结构问题二：Story 能否写全业务行为与验收 | **未回答** | component-design §5 仍是“投影供宿主装配 Story Document，零新设计事实”（第 136 行）；行为与验收仍在 CU Spec 层 |
| 结构问题三：新需求能否用平铺 Feature | **未变** | 仍称“存量平铺 Feature”；正式需求要先过 component-design |
| 蓝图阶段成本（约 48 分钟） | **未见直接改善** | 取消了配额，没有减轻载体；受管路线给了 schema 与命令，效果要实测 |
| 模型自建 Goal、术语记成 `headless_assumed` | **上游无变化**，属本仓测试配置 | `blueprint-discovery.ts` 第 281 行仍要求交互态当场确认；dsh 原版本来就声明 goal 能力，Goal 工具来自 dsh 本身 |
| 新问题：受管初始设计不注入 Extension 知识 | **新出现** | 初始设计作者提示由 `initialDesignAuthorInstruction` 生成（`goal-phase-runtime.ts` 第 4906 行），没有调用 `extensionInputsForPhase`；后者只用于 CU 工作单元（第 7712 行） |
| 蓝图设计期验收（11-10 补查） | **原生早已要求，Extension 没有用** | 原生方法要求被 CU 引用的目标在设计期写 acceptance、boundaries、errors/idempotency、quality_attributes，评审投影有验收与失败恢复小节（`app-component-blueprint-workflow.md` 第 66、83–85、248 行，旧版已有）；2.0.3 两份蓝图验收条目为 0，Extension 设计指引从未要求。详见[效果可达性与退场审计](02-1.x效果可达性与存量退场审计.md) §1.2 |
| 独立质询结果登记（11-10 补查） | **新版有原生写回** | `blueprint-questioning.ts` 新增 `parseIndependentQuestioningOutput`、`applyIndependentQuestioningOutput`（第 100–146 行），目前只在受管运行与无人值守修复中调用；Extension 仍让模型手写 `review_summary.questioning` |

C02 评审 §8 的 11 条整改候选，没有一条被上游取代：Goal 工具在本仓测试配置里；写操作语义、统计空投影、DFX-02、持久化表述、`task.md` 写入、首读落盘、复核触发、度量、Story 收缩都属于 Extension、知识样板或测试域。只有第 9 条（读校验器学蓝图载体）在受管路线上有缓解，在直接设计路线上没有。

## 3. Extension 适配要怎样调整

### 3.1 推进授权

`extensions/skills/story/SKILL.md:79` 按旧 §8.1 第 2 条、§8.2 的“batch 多阶段声明”定义推进授权。新 §8 不再有这些条款：完整交付由同一协调器持续推进；专项请求止于原终点；检查通过不扩大授权。

调整：Story 的推进契约改为引用新 §8 的两类请求。

- `/story init` 到交付门，是专项（只做设计与 Story）；
- 交付选择里的“实现方案”“完整实现”，是新的请求：前者是只要 Spec/Plan 的专项，后者是完整交付。

同步检查 `phases/design.md` 第六节、`reference/phase-closure.md` 第 54 行对 attended 与收口的说法。

### 3.2 S4 走哪条路

- **保留** S4 由 Extension 以“直接设计请求”驱动（component-design 直接调用止于 readiness，新版仍支持），Extension 的知识任务、作者页与质询派审照旧送达。
- **暂不**把 `/story init` 交给受管初始设计。原因：受管路线不注入 Extension 知识（§2 最后一行），并且一路推进到施工，Story 的业务送审插不进去。
- **向上游提**：受管初始设计的作者与质询提示接入扩展输入（与 CU 工作单元相同的 `extensionInputsForPhase`），并提供“设计准入后停下、交宿主送审”的终点。到件后再评估是否改走受管路线。

### 3.3 CU 候选与切片

- 设计页与蓝图作者页里写 CU 候选的指引，改成新语义：只选承担的交付目标；整批认领全部必需义务；闭包不手写。
- 作者指引补上切片用法：材料明确待定的能力，放到远期切片，当前切片写成已定的保守行为；工程能力缺口要么在当前切片解决，要么把相关能力移出当前切片。这同时修正 C02 评审 §4 里 car 被持久化缺口卡住的处理方式，属于知识样板与作者页的事。

### 3.4 消费面与本地补丁

- **原生模块消费面**：Extension 用到的 127 处模块与函数，导出在新版都还在；唯一签名变化是 `verify-feature-completion.ts` 的 `readCurrentDispositionInput` 多接受一种参数类型，属兼容变化（`consumption-surface.md`）。关键返回字段（`busy`、`completionBlocking`、`releaseReady`、`retiredChangeUnitIds` 等）也都在。返回形状与行为是否兼容，要靠同步批次的装配加测试确认。
- **命令行入口**：`goal-mode-entry.ts` 改动最大（+389/−70），`--prepare-scope` 仍在，新增 `--execute-request`、`--observe`、`--interrupt` 与 adapter、模型参数；`check-change-unit.ts`、`prepare-blueprint-design.ts`、`check-component-blueprint.ts`、`harness-runner.ts` 文件本身未改，但它们调用的模块改了。
- **收口取值**：`phase-closure.md` 依赖的 `next_action` 取值在新版都还在。
- **本地补丁** `test/fixtures/framework-local/3.1.0-dsh.patch`：21 个文件里 19 个能在新树上应用，`agents/shared/agent-bundle/templates/rules/framework-agent-execution.mdc` 与 `skills/reference/business-ut-workflow-detail.md` 两处要在新文件上重做。dsh 适配声明变化后，要重核补丁里“去掉 goal 能力”那部分是否仍需要，测试配置同时按 C02 评审 §8 第 1 条关掉 dsh 自带的 Goal 工具。

### 3.5 继承的适配决定（诊断 §3）在新版下的判断

| 适配决定 | 新版下的判断 |
|---|---|
| Story 从蓝图派生、零新事实 | 不变，按诊断“修改”的方向做（零新**设计**事实，业务行为与验收写全）；仍需问 Framework 作者 |
| 规约验收只放 CU 层 | **推翻**：前移到蓝图设计期的原生 acceptance，Story 从蓝图照写，CU Spec 由原生复用（审计 §1.2） |
| 附录“业务摘要 + 设计参考” | 保留分工，不受影响 |
| S1–S3 由 Extension、S4 交 component-design、S5 成文 | 保留，S4 继续走直接设计（§3.2） |
| 原生质询与 Story 独审并存 | 保留；新版质询的 `question_id` 由机器给出，Extension 的质询派审载体要核是否沿用 |
| 独立 Spec/Plan 走 request 范围 | 保留（专项请求），按新 §8 改说法 |
| 交付门之后才问终点 | 修改为在范围关卡问；新版完整交付由协调器持续推进，这一点更重要 |
| 测试目标沿用 1.9.9 金样与原终点 | 修改：car 的终点要先看当前切片里有没有 `blocker`，有就止于 `design_handoff`；金样分 A/B |

## 4. 风险

- 上游明确这批是当前开发，未经 P4 宿主验收；同步后若遇到上游缺陷，按 AGENTS §6 报回，不在本仓改 vendored 文件。
- 新版改动面大（220 个文件），只靠静态对照不够，同步批次要用装配、受影响用例与一次 handback 证明兼容，2.0.3 已证的原生链用例要按新行为重核预期。
- demo 接入按 AGENTS §6 留到 2.0.4 发布时做；在那之前，被测组合与 demo 用的是两个不同的 Framework 版本。
