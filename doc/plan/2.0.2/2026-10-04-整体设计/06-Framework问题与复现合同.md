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

## 4. FW-05：Spec→Plan 事实基线，先复现再定责

现象：车钥匙 Spec 有真实审查与闭环，Plan 发生 facts 范围指纹/established_by 失败；作者后来手改 facts 并重验，最终现场已污染。不能据此直接要求 Framework 改逻辑。

复现合同：按 04 中性 CU 正常路径，冻结同一 requirement，记录 Spec 完成前后及 Plan 首次调用的 execution-scope、resolvedInputs、facts、evidence manifest。首阶段只用原生实际身份；不人工填修哈希、不复用被改坏的事实。

- 正常路径通过：本仓修错误调用/续行说明，FW-05 关闭为非上游缺陷，留下原生正确恢复示例。
- 正常 acceptance/contracts 派生使原生建立事实不能承接：上游修实际 baseline 绑定/失效恢复，给准确公共调用和回归。旧值重放被拒仍保留；不禁用 facts 检查、不把错误变 WARN。
- 输入或证据不全：补齐最早缺失的实际输入，不基于错误提示猜调用身份。

上游交付前不签相应施工路径，但不阻止独立的人读整改。无需新增事实恢复器或外部状态系统。

## 5. 上游交回与接入

上游交回必须给已发布版本/source_commit、实际函数/CLI 及必填输入、成功/失败示例、影响范围和运行测试。设计者核实际发布件与本文件一致；按 AGENTS §6 接入 demo 后再核扩展接缝，不在本仓 vendored 临时完成产品交付。

报告格式、派审缺 key、作者改报告、来源清单、SEC 样板、Phone 范围矛盾和宿主请求变形属于本仓先修责任。API 超限先核实际配置/重复送达，不因一次错误申请新调度框架。
