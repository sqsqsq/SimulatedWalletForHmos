# Framework 阶段 verifier 的接替与上游确认

**结论（2026-11-25）。** Story 采用蓝图以后，只有部分任务需要独立审查，宿主也不一定通过名为 verifier 的工具派审。今天本项目正式 pin 的阶段检查仍依赖本地宿主补齐；上游后续源码已经实现统一的阶段独核，接入带该变更的正式分发后应让旧定制退场。上次在 S37 用 DSH overlay 的“工具有无”解释了运行配置，却不足以判断蓝图和 Story 实际调用了什么。

## 三个消费者

| 消费者 | 被核对象与实际调度 | 对本地专用 verifier 的依赖 |
|---|---|---|
| 蓝图设计质询 | 固定分发的 component-design 对完整设计要求渲染候选后派独立质询；小型走短设计时可免独立质询。Story 接原生质询，将材料交给隔离子代理，复核可续原读者。 | 需要质询的场景依赖独立上下文和真正回复。11-23 两例的实际父会话用 `subagent` 派 questioner（auto 事件 323、car 事件 116）。无需据此保一个名为 verifier 的宿主角色。 |
| Framework 的 Spec/Plan 等阶段 | 阶段是否签 request、谁执行独核、报告与当前 subject 如何绑定，均归 Framework。f894 的 resolver 在 policy=required 且 adapter 未声明 verifier_subagent 时仍返回 disabled/adapter_has_no_reviewer；声明后为 enabled。 | **当前 pin 有依赖**：原版 f894 仅 Claude、CodeAgent、Codex 声明 true；OpenCode 和 deepseek-harness 均未登记该项。本仓用本地 OpenCode 角色及独立的 dsh adapter/preset 补齐，因此现在直接撤掉这组配置会改变阶段核验的覆盖。 |
| Extension 的 Story 读稿、知识独审及适用的阅读图核验 | Story 要独立读取固定业务材料、只写指定报告、返回同一份完整正文；适配知识交独立读者或按原合同披露未审。图验收消费自足任务。所需输入、输出各归自己的业务协议。 | Story 两例的实际父会话同样通过 `subagent` 派读者（auto 346、car 454），后续有 send_message；没有由此证明 OpenCode 的这条路线，亦不能推论所有后续阶段均无需 verifier。就地适配、图验收和其他宿主按是否需要相应读写及回复能力分流。 |

业务读面见[蓝图与 Story 派审](../../../../extensions/base/skills/story/phases/design.md:74)、[读者接收合同](../../../../extensions/base/skills/story/phases/design.md:131)、[知识独审](../../../../extensions/base/skills/story-adaptation/reference/knowledge-review.md)。历史事件只作实际调用方式依据，不替两例签审查质量。[当轮运行目录](../../../../output/story/story-suite-20261123-184800/cases/)

## 已经由谁实现

- 本项目远端 main 及当前被测分发为 `f8946531`，Framework 源 `fd5adea9`。用原分发的 resolveVerifierPlan 对同一 Plan 输入只换宿主能力，阶段门从 disabled 变 enabled。DSH 用同一 profile 只换 overlay 的 dump-config，两边模型相同，有 overlay 才有命名工具和 maison-verifier preset。这是适用性与工具登记的证据。[两版 resolver 读数](../../../../output/evidence/2.0.6-host-directory-review/verifier-plan-comparison.json) · [DSH 配置对照](../../../../output/evidence/2.0.6-host-directory-review/dsh-comparison.json)
- Maison 作者仓在 11-23 的 `db29eb82` 改为按 profile、workflow、evidence policy 决定是否独核，运行时派发。单阶段根据 NEXT 走 `--execute-verifier`，绑定本轮模型、request/subject 和报告；缺模型或运输时保留待核义务。该变更在已查的上游 main `f9c41f63` 中，未进入本项目固定分发。实际运行未打补丁的新旧 resolver，新版在上述两种输入下均 enabled。源码的模型绑定表已列 OpenCode 和 deepseek-harness；本次未在两宿主跑新版完整 request/报告闭环。[上游变更](https://github.com/sqsqsq/agent-maison/commit/db29eb822c88f93fe748ff265dcfaa0eba14c27c) · [阶段执行合同](https://github.com/sqsqsq/agent-maison/blob/f9c41f63/skills/reference/agents-entry-detail.md#独立阶段核验) · [前台模型来源](https://github.com/sqsqsq/agent-maison/blob/f9c41f63/skills/reference/stage-verifier-model.md)
- 上游针对已退役的 Claude／CodeAgent／Codex 受管 verifier 有 UPDATE 清理。项目自行引入的 OpenCode、dsh 定制仍要由本项目核所有权并撤掉，不能假设上游会替项目删除所有本地文件。通用阶段独核、宿主运输与模型绑定应由 Framework 维护；本仓承担 Story 任务与验收语义。

## 给 Framework 作者的确认内容（供用户转交）

> 我们在 OpenCode 和 DSH interactive 上集成 Story Extension。现用分发对应源码 fd5adea9，以前要本地补 verifier 角色和 DSH overlay 才能执行阶段独核。我看到 db29eb82 已把阶段独核收回运行时。请确认哪个正式发行件已含此变更，以及 OpenCode、DSH interactive 单独进入 Spec/Plan 时，推荐用哪个 adapter 和公开入口取得独立结果；我们想移除本地 verifier 补丁。另有自定义的独立读稿任务，需要隔离上下文、读取指定材料、只写指定报告并返回完整回复。若已有推荐的宿主原生或 Framework 公共接法，请指到现有合同；阶段接口只收已签 request 也请说明，我们会沿宿主独立读者通路。Story 的审稿内容、业务键和收件规则由 Extension 自己维护。

## 清理触发与验收

**本轮**按 [S37](05-批次-统一候选与交付验收/S37-退出维护仓根OpenCode副本.md) 清根镜像；保 f894 候选已验证的阶段审查覆盖。**下次接入含新原生独核的正式 Framework 时**，执行者在同一份无旧 verifier 定制的隔离候选按以下顺序处理：

1. 用 OpenCode、DSH interactive 各走一个真实需独核的阶段，核前台 provider/model、首次 request、独立绑定的完整报告/收据，以及中断后续等；合法无需独核的阶段保正常结果。不能以没有 request 或缺能力时跳过冒充已审。复用上游已验证原件与本仓实际输入；真实模型运行按既有授权。
2. 分开复验蓝图质询与 Story 读者：主作者用宿主独立上下文派发，读者对象、来源和完整回复均对得上，Story 报告仅写指定位置。适配知识和图验收按各自合同复用。旧的 2.0.5 subagent 调用记录是迁移线索，不代替去掉补丁后的宿主验收。
3. 哪一侧走通就在哪一侧缩补丁并从正式源重物化：阶段专用角色／登记、专用 verifier 调用与旧回执文字、DSH preset 与 tool 实例、仅因该工具引入的 start/resume --patch 及其产物／专用测试逐项退出。先盘 DSH overlay 的其他有效设置（含交互模式的 tool-goal 约束）、adapter 的 Story 桥和宿主选择；有独立消费者的按正式能力保留。通用 read-only/独立性和回执真实性回归用新入口验证。OpenCode 其他插件、规则和 Story 桥继续由宿主物化。
4. 当前正式 main 未变时，这个上游接入不阻塞 S34–S37、S12 准备或本轮已批准路线；若切到新正式分发，按既有规则对齐 main、demo、pin 与宿主补丁后重新核同一候选，不混用旧结果。正式供给和本机运行实证分别记录。
