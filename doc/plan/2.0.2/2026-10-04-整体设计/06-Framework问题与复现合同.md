# Framework 协作合同与真实依赖

本文件是 2.0.2 对上游的集中请求与本仓消费合同，供用户审核/转交，未对外发送。实际观察发布件：`demo/framework/RELEASE-MANIFEST.json`，3.1.0 / `074a4c3c4a0591c8ed2162e2a0d048a1fdec081f`。未核远端最新版本，不声称上游今天仍未修复。

## 1. 已有能力直接复用

| 用途 | 已核本地入口 |
|---|---|
| 需求物化校验 | `check:component-blueprint --materialization` |
| 设计/质询/修订 | `/component-design` 与原生 blueprint workflow |
| 原生检查结果 | `scripts/check-component-blueprint.ts::checkCanonicalComponentBlueprint(projectRoot, blueprintId)` |
| 原生评审投影 | `blueprint-review-projection.ts::renderBlueprintReviewMarkdown(blueprint, artifactSha256)`、host-seams 的 validateBlueprintReviewPublication |
| 反馈候选资格 | `check:component-blueprint --feedback`；接受仍由 write owner 决定 |
| CU 准备/readiness | change-unit-design-preparation 的 evaluateDesignPreparationEntry、acceptChangeUnitDecomposition、deriveDesignPreparationReadiness |
| CU 施工输入 | `prepare-blueprint-design.ts --feature C` |
| 范围候选/交互施工 | `goal-mode-entry --prepare-scope`、原生 Skill、harness-runner；参数见 04 |

这些入口的实现不复制进 Extension。以下新返回字段是**提议给上游的定案合同，当前不可调用**；上游未接受/发布就标依赖未就绪，实施者不得自行发明名称或临时降级。

## 2. FW-04：可评审设计与可施工设计分开表达

### 已确认事实

当前 `blueprint-admission.ts` 的 blockerIds 来自 upstreamIssues，一般 gap 即使 status=blocker 且 needed_by=current 也不加入集合；只有 component-assets 有特判。自动充值完整产物含三个当前 blocker，却 admission pass/空 blocker_refs/contracts_ready=true。已调用该 helper 的中性例，结果为空 issue 列表，详见分析 00/08。这只直接证明 helper 的局部缺口，不直接证明任意 CU 均可施工；CU gate 还有实际对象 unresolved 与 authoritative 校验。

### 目标语义

1. **可评审**：身份、来源、结构、设计引用、真实质询和内部一致性成立；业务未决真实记录、责任和影响明确，足以交人裁决。可评审不等于契约已确定或 CU 可施工。
2. **可施工**：当前 CU 实际依赖的设计/契约/决定成立；与它无关的远期 gap 不阻止。当前依赖未解除时 readiness 阻断，不能以改 needed_by 避免。
3. 数据坏、来源冲突、过期投影、质询缺失不是普通业务未决；继续返回可定位原生问题。

### 提议的最小公开返回合同

扩展现有 `checkCanonicalComponentBlueprint` 返回值，保留 loaded/blueprint/issues 等既有字段，增加只读派生的：

```typescript
review_readiness: {
  status: 'ready' | 'blocked';
  issues: BlueprintIssue[];  // 阻止形成可信评审件的问题
  unresolved: BlueprintRecord[]; // 当前实际未决对象的原生记录，不另造登记
}
```

该值不写 canonical 为第二状态，也不由 Extension 计算。现有 admission/设计 gate/readiness 保持施工权威，并纠正一般当前阻断的派生。上游决定如何在原生 validator 内组织检查，但公开结果不能靠 Extension 的 issue 白名单反推。

`ready` 的机械结果仅说明原生可检查条件与已登记的设计审查处置成立；模型仍负责语义一致性，实际独立质询须有宿主调用证据。不得把新增返回值解释为脚本已经证明业务无矛盾，或以 `questioning.status=complete` 单字段替代真实质询。

原生 renderer/validateBlueprintReviewPublication 支持 `review_readiness=ready` 对象的指定 revision 评审投影，即使对应施工尚阻断；投影明确区分评审可用、当前施工结果、未决范围，零新增设计事实。身份/摘要按既有 derived_from 绑定。`--projection` 仍走原生校验；不要求新的 provider/phase/模式档位。

这个返回合同由维护设计者提交上游核对；若上游已有等价已发布能力，先提供实际路径/字段/行为测试，再由设计者修本文件为真实绑定，不能让实施者猜。上游拒绝上述语义时是产品合同待裁定，不可在本仓补旁路。

### 本仓明确消费者

上游接入后，`framework-access.mjs::readBlueprint` 增加 `purpose='review'`，直接消费上述原生字段及投影校验：ready 为 status=ok；blocked 为 not_reviewable 并带原生 issues/unresolved。现有 draft 仅供设计作者读草稿，delivery 保持已有严格用途。没有 review_readiness 字段时返回依赖缺失，不 fallback 到 admitted 或 draft。

`design-source`、成文路由、review-object、附录/附件定稿统一用 review；施工入口仍读原生 CU/readiness，不用 review 结果放行。flow 不保存平行的 review_ready 布尔值，每次从原生读取。当前输入消费、component/blueprint 身份、revision 和投影摘要核对保持。

### 上游验收

真实当前契约缺口：评审可用时完整展示未知，相关 CU 不可施工；真正远期缺口：无关 CU 可按原生规则继续；解除后：原生修订/引用/派生一致；受控 fake：实际获授权且范围明确才按原生能力允许；坏身份/坏来源/无质询：不可评审。不要用专名例外或仅把 BLOCKER 改 WARN 通过。

本仓 P1/P2 可先做无依赖部分；该发布件未接入，带未决送审与完整施工边界组合不签收。

## 3. FW-01/02：直接设计资产与实际独立质询

保持已有 skill_assets 的 `extension_author_requirements`、`extension_review_requirements`：发现前交作者页，派独立质询时交审查页、当前候选、真实来源/知识及原生 required scopes；无登记保持原生，登记不可读明确输入缺口。直接 `/component-design` 与 Story 转入同路，不新增任意脚本执行机制。

主执行者派隔离执行者，原始回复留过程目录，设计负责方处理再更新 questioning；provider 名称/文件存在不能证明实际执行。候选与回复绑定，不能要求增加 questioning 之后全文摘要还等于候选。上游给实际入口/示例与有无登记、缺文件、直接/转入的运行证据。

本轮 Story 路径已真实质询，不重复声称无宿主能力。未交付的责任是直接入口的统一送达和原生执行合同。用途物化增强 FW-03 保持非阻塞，命令入口成功不证明自然语言发现成功。

## 4. FW-05：无 run 的范围修订后 facts 增量承接（已复现）

本仓已核定特定上游问题：[返修复核](评审意见/2026-10-07-集中返修复核.md) §2。观察发布件仍为本文件开头的 3.1.0 / 074a4c3c；不声明远端后续版本是否已修复。

**进入条件**：来源完整、蓝图合法准入的中性 CU，设计层验收/施工契约由 Spec/Plan 细化；同一 requirement 经原生 prepare-scope 得到 `[spec, plan]`，采用无 run 的 feature 载体。不是已完成结果的合法复用。

**实际序列**：原生冻结范围→Spec 建立 facts→Spec 脚本检查通过、原生形成 scope_revision_input 并修订有效范围→离线构造且明确标识的 verifier 回复→原生 Spec `PASS/closed` 并建议 Plan→仅追加 `phase_delta: plan`→Plan 报 facts 范围指纹不匹配。

**证据位置**：`output/story/2.0.2-fw05-repro-20261007/` 的 `fw05_repro.py`、`fw05_variant.py`、`fw05_spec.py`、`fw05_close.py`，以及 `execution-scope.json`、`facts-spec-original.md`、`4-receipt-spec.log`、`3-runner-plan-a.log`。复现工程位于 `output/scratch/2.0.2/fw05/p`；冻结记录含绝对路径，重跑应按脚本重新建立范围，不照搬冻结记录。所有 harness 调用必须显式传 `--project-root`，不能让 vendored 路径推导为 demo。

**最早冲突**：`capability-resolution-entry-input.ts` 给 feature facts 的 frozen_scope_fingerprint 来自当前有效范围；`context-facts.ts` 的身份匹配不因 baseline 成立而豁免，而 factsBaselineFingerprint 包含原 frontmatter。原生正常修订后旧指纹失败；作者改成新指纹又改变建立基线。本仓要求的恢复是实际原生增量承接，不是让 Plan 重做一次全量探索或手改 established_by。

**上游交付合同**：同一 feature 的合法范围修订后，验证仍有效的原来源和阶段证据，允许后继通过 phase_delta 承接；新增目标/来源变化按实际依赖重验；身份不符、篡改基线及旧结果重放仍拒绝。由上游确定身份稳定性或原生重绑的具体实现，并提供准确入口与回归，不在 Extension 新建恢复器、不改 receipt、不降检查等级。

**验收**：新执行 Spec→Plan、相同输入重入、合法复用、真实来源变化、旧身份/被改基线拒绝；验证先前阶段仍有效且新阶段责任可履行。复现中的人工构造 verifier 只证明机械接缝，不证明业务语义或设备效果。

影响限定于上述无 run、发生原生范围修订的增量承接。原车钥匙另有用 Story 正文作为 requirement 的错误调用，已由本仓修正；本报告不豁免该错误、不扩大为所有 Plan 或所有运行载体都失败。上游发布件接入并通过此合同前不签该施工路径；其他独立整改可继续。

## 5. 上游交回与接入

上游交回必须给已发布版本/source_commit、实际函数/CLI 及必填输入、成功/失败示例、影响范围和运行测试。设计者核实际发布件与本文件一致；按 AGENTS §6 接入 demo 后再核扩展接缝，不在本仓 vendored 临时完成产品交付。

报告格式、派审缺 key、作者改报告、来源清单、SEC 样板、Phone 范围矛盾和宿主请求变形属于本仓先修责任。API 超限先核实际配置/重复送达，不因一次错误申请新调度框架。
