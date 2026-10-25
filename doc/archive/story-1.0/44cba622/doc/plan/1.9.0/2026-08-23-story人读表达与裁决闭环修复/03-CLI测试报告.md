# 03 CLI 测试报告(人读表达与裁决闭环修复轮)

> 状态:**验证中**(2 Case 实跑完成;结论仅覆盖已到达的阶段)
> suite:`story-suite-20260824-091443`,隔离 workspace,2 Case 并行,09:15 起跑 ~10:56 收束
> 实施对象:提交 `6bf074a7`(17 项修复);对照基线:上一轮 suite `story-suite-20260823-172448`

## 1. 本轮实跑事实

| Case | feature | 目标终点 | 实际到达 | 结果 |
|---|---|---|---|---|
| split-interactive | AR90006 | plan | **plan(达成)** | spec 闭环 + plan.md/contracts.yaml 产出;plan verifier 未及产出(被 stop 打断) |
| pattern-image-review | AR90004 | review | **spec(未达成)** | spec 实质闭环(verdict=PASS/receipt=passed/closure=closed),但被测试驱动器死锁拦在 spec,未进 plan |

两 Case 的 `doc/features/<AR>` 均已回灌主工程,观测记录已生成。

## 2. 修复项验证结论

### 2.1 需求 1/2(内容守恒与人读表达)——**明显改善,仍有缺口**

| 判据 | 上一轮 | 本轮 AR90006 | 本轮 AR90004 | 判定 |
|---|---|---|---|---|
| 流程图(story/spec) | **0** / 1~2 | **1** / 2 | **1** / 1 | ✅ 从全丢到保持图示形态 |
| >200 字长段 | 5 段(AR90006) | **1 段**/41 | 4 段/35 | ✅ 显著收敛 |
| 决策引用问句式坏句 | 多处(撑断句子) | **0** | **0** | ✅ 带值渲染生效 |
| 正文规约编号 / 附录 | 0 / 23 | 0 / 30 | 0 / 42 | ✅ 保持 |
| 引用块使用 | 0 | 0 | **2 行** | ◐ 部分 palette 开始使用 |
| 有序列表使用 | 0 | **0** | **0** | ❌ 仍未使用 |
| 厚度(story 正文/spec) | — | 0.67 | 0.60 | ❌ 仍薄于 spec |

**仍未解决**:有序列表零使用、厚度基准未达成。写作指引已把两者写进 palette 与自查项,但被测模型未采纳——说明**注入件里"写了"到模型"照做"之间仍有落差**,下一轮需要更强的手段(如 check 层给出观测 WARN,或在范例里加一个"该用有序列表却写成长段"的对照)。

### 2.2 需求 3(知识应用)——**plan 段首次拿到行为证据,质量高**

**冻结结果(AR90006 `plan/contracts.yaml`)**:
- **设计模式**:`decision-tree` 被选中并冻结,带 `unit`(签约流程)、`anchor`(指回 plan.md 小节)、`rationale`(说清多分支驱动的适用理由)——不是只写模式名;`page-interaction` 未选,符合「不选也是合法结论」。
- **规约义务 6 条**逐条给 `obligation` + `anchor`,覆盖 UX-01、SEC-01、DFX-01、DM(4 条)、COMPAT-01、**ENV-01/ENV-02**。
- **ENV 域本轮判为命中**——上一轮同一 Case 正是把 ENV-02 漏判成「不涉及」(新增入口+可重复写操作却判否)。**同一 Case 同一域,上轮漏判、本轮判对**。

**机械门禁实测**:

| 检查 | 结果 |
|---|---|
| `plan/post_check`(冻结一致性) | ✅ PASS——pattern_id 在册、锚点可解析、规约编号可回查 |
| `post_verifier`(plan) | ✅ **正确拦截**:「找不到 plan 阶段 verifier 产物,无法证明 2 条扩展判据被裁决」——Case 被 stop 打断未产出报告,机制如实报错而非静默放行 |
| 冻结后 coding 注入收窄 | ✅ 只送冻结命中的 6 个规约域 + `decision-tree`;未冻结的 `page-interaction` 不注入 |

**裁决闭环(需求 3 的核心缺口)**:AR90006 的 spec verifier 报告**逐条含全部 8 条扩展判据**
(`spec_constraint_echo` / `spec_ext_conclusion_validity` / `story_reader_fitness` / `story_decision_substance` /
`upstream_inputs_coverage` / `split_boundary_consistency` / `upstream_semantic_coverage` / `spec_knowledge_disposal`)。
**上一轮同一 Case 是 0/8 且 harness 照收 PASS**——闭环修复见效。

## 3. 本轮发现的缺陷

### D1(测试基础设施,高):驱动器的闭环判据文件名过窄,导致死锁空转

`run_case.py` 的 `phase_evidence_complete` 要求四件凭证之一是 `reports/verifier.report.md`。
AR90004 的 verifier 报告实际落成 `reports/verifier-report.yaml`(同一份内容,不同命名),
于是驱动器判「spec 未闭环」→ 续话指令一直是「现在执行 spec 阶段」→ 模型正确地拒绝重跑
(`check-receipt` exit 0,AGENTS §5.2 明令已闭环不得重跑)→ **死锁空转 27 轮**(spec 上限本是 6),
最终耗尽本轮时间,未能进入 plan/coding/review。

- 证据:AR90004 `summary.json` 的 `verdict=PASS / receipt_status=passed / closure_status=closed`;
  `reports/` 下有 `verifier-report.yaml`、无 `verifier.report.md`;对照 AR90006 落的是 `.md`,未空转。
- 影响:本轮 review 阶段目标未达成;这不是被测扩展的缺陷。
- 修法(下一轮先做):`phase_evidence_complete` 的 verifier 凭证判据改为**匹配一组文件名**
  (`verifier.report.md` / `verifier-report.yaml` / `verifier-*-result.yaml`),任一存在即算;
  另外续话超过该阶段上限时应中止并报错,而不是无限续。

### D2(观测协调,中):`awaiting` 出现后未即时响应

split-interactive 于 10:23:56 进入等待,我按 120 秒节奏连轮 4 次仅看状态、未读等待内容,
10:34 才回复——**空等约 10 分钟**。协调纪律应为:`awaiting_reply` 一出现立即读 runlog 并回复,
不等下一个轮询周期。

### D3(被测扩展,低):写作 palette 采纳不全

见 2.1——有序列表零使用、厚度未达标。属"指引已写、模型未照做",非机制缺陷,但需要更强的落地手段。

## 4. 与 02-行为验证计划的对照

| 判据 | 结论 |
|---|---|
| B4 图示形态 | ✅ 通过(两 Case 各 1 个流程图,上轮为 0) |
| B5 段落纪律 | ◐ 部分(AR90006 1 段超长;AR90004 4 段) |
| B6 形式 palette | ❌ 未通过(有序列表 0) |
| B7 厚度 | ❌ 未通过(0.60/0.67) |
| B9 决策引用可读 | ✅ 通过(坏句 0) |
| B10 裁决闭环 | ✅ 通过(spec 8/8 被裁决;plan 缺报告时正确拦截) |
| B11 plan 冻结实质应用 | ✅ 通过(anchor/rationale 齐备,不选项有结论) |
| B12 冻结后收窄注入 | ✅ 通过(6 域 + 1 模式,未冻结的不注入) |
| B13 三渠道点名 | 未取证(需读 spec §7.5 细节,本轮未展开) |
| B14 规约判定不搪塞 | ✅ 通过(ENV 域上轮漏判、本轮判对) |
| B15 适配演练 | ✅ 通过(离线:新增规约域零改码生效) |

## 5. 结论

- **裁决闭环(本轮最高优先级)已验证有效**:8/8 逐条裁决、缺报告时正确拦截,上一轮 0/8 的漏放不再可能。
- **知识应用的 plan 段首次拿到证据且质量高**:模式冻结带落点与理由、规约义务逐条带 anchor、
  上轮漏判的 ENV 域本轮判对、冻结后注入正确收窄。
- **人读表达明显改善但未达标**:流程图、长段、决策引用三项修复见效;有序列表与厚度两项未采纳。
- **review 阶段目标未达成**,根因是测试驱动器的 D1 死锁(非被测扩展);修掉 D1 后应重跑一个 Case 到 review。
