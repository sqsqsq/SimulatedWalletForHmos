# 实施状态

> 需求：`test/story/plan/2026-09-07-新需求四项/steps/02.3-Story写作流程重设计.md` 及其三份分册 `02.3-01` / `02.3-02` / `02.3-03`
>
> 工程根：`E:\Project\SimulatedWalletForHmos`
>
> 方案模式：`accepted_existing`（沿用 2.3 总方案 §5 的三分册切分；01 分册 §1/§7 自己规定 S4 单独一笔先交评审，故 01 拆成两步）
>
> 当前状态：step-01、step-02、step-03（3a）通过并已提交、step-03b 通过并已提交；step-04 已送审，等待 reviewer

## 步骤

| 顺序 | 步骤 | 结果 | 真实依赖 / 执行顺序 | 就绪程度 | 状态 | Review | Commit |
|---:|---|---|---|---|---|---|---|
| 1 | [step-01-s4-fixes](steps/step-01-s4-fixes.md) | `804db2d3` 的 S4 提交按 `reviews/25` 关闭 R1–R3，一笔提交 | 真实依赖：`804db2d3` 已在 HEAD | 可实施 | **通过** | [review](reviews/step-01-s4-fixes-review.md) | `eda9c282` |
| 2 | [step-02-source-index](steps/step-02-source-index.md) | 01 分册 §2–§7：`core/story-sources.mjs`、`story-build sources --stage before-spec`、source-index / 稀疏 selection / basis 合同、`--accept-source`、decisions 初始化前移、S4 之后进初筛的指令 | 真实依赖：step-01 的 `contract.design.origin` 与 `sources/ar/rN.md` | 可实施 | **通过** | [review](reviews/step-02-source-index-review.md) | `9b500d28` |
| 3 | [step-03-orchestration](steps/step-03-orchestration.md) | 3a：02 分册的合同与函数——after-spec、story-template 读写与两条谓词、有效取舍合并、structures 生成/检查、视图分配、related 路径解析；`skeleton`/`chapter`/`prepare` 不动，v3 仍是唯一链 | 真实依赖：step-02 | 可实施 | 实施中 | [review](reviews/step-03-orchestration-review.md) | — |
| 3b | [step-03b-entry-switch](steps/step-03b-entry-switch.md) | 3b：skeleton 唯一视图写入口、chapter 结构检查、prepare 短输出与谓词、提示词接线、删 `context_chapters`、v3 作者链退出 | 真实依赖：step-03（3a） | 可实施 | 未开始 | reviews/step-03b-entry-switch-review.md | — |
| 4 | [step-04-verify-and-retire](steps/step-04-verify-and-retire.md) | 03 分册 §1–§6、§8、§9：写后核对接线、最终 check 条件、verifier 输入重定、冻结、整体退出核对、确定性验收、过拟合自查、实施反馈 | 真实依赖：step-03b 的 template / 视图 / prepare | 可实施；§7 行为验收由用户启动 CLI，属后置检查 | 未开始 | reviews/step-04-verify-and-retire-review.md | — |

## 当前动作

- 行动角色：executor（实施前审视 → 实施 → 送审）
- 下一动作：executor 按 3a 步骤文件实施并送审；获批提交后 `advance --step-id step-03b-entry-switch --step-file steps/step-03b-entry-switch.md`
- 已核实：金样 11 件已由 `d2d7a0eb` 入库、`test_golden_sample` 10 passed，离线全量按**全绿**判，不再豁免那一条
- 停止条件：预算无数值上限（用户 2026-09-10 裁定，见 `regression/mechanism-budget.yaml` 文件头），但每步须按 `test_mechanism_budget.measure()` 如实记录前后值；`framework/` 零改动；`test/story/plan/` 在 `.gitignore`，本目录文件不入库

## 记录

- 2026-09-10：plan-review 未决 ① 已裁定——金样 11 个文件入库并登记进 `EXPECTED_CANONICAL_FILES`，提交 `d2d7a0eb`（reviewer 按用户指令提交，仅此一笔）。此后各步验收按离线全量全绿判。
- 2026-09-10：step-03 按 executor 提议、reviewer 裁决拆为 3a（合同与函数）/ 3b（入口切换与退出）；原步骤文件写的「A 改 skeleton、v3 仍在」作废——那会出现两条链。3b 步骤文件已建，顺序 3 → 3b → 4。
