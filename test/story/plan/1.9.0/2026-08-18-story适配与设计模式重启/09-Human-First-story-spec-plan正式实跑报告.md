# Human-First Story / Spec / Plan 正式实跑报告

> 实跑日期：2026-08-18 ～ 2026-08-19  
> 用例：`cross-component-rich`、`cross-component-rich-plan-coding`  
> Feature：`AR90004`  
> 本报告只记录结论与后续正向设计，**未据此修改实现、规则、模板或测试脚本**。

## 0. 结论先行

本轮不能判定“Human-First、应用域规约和设计模式都已完整生效”。准确结论是：

1. **Story 的人类叙述骨架明显改善，但终稿仍不合格。**
   导读→全景→范围→场景→体验→风险→上线的阅读顺序成立；全局→本部件→本 AR 的漏斗也成立。
   但无编号事实仍有遗漏，跨章重复仍多，决策值渲染存在明显机器拼接，review 没有形成决策全景。
2. **Spec 阶段闭环成功，且正确登记了两个模式信号。**
   `decision-tree` 与 `page-interaction` 都出现在 spec §10，Scope 也正确区分了业务主责与
   `WalletMain + Phone` 的物理改动范围。
3. **Plan 的普通结构/架构门禁闭环成功，但本轮最关心的模式与规约观测失败。**
   plan、contracts、use-cases 中没有模式应用表，没有两个 `pattern_id`，也没有按适用矩阵形成系统化的
   应用域约束处置。
4. **现有 PASS 存在假阳性。**
   verifier prompt 已包含 `plan_constraint_coverage` 和 `plan_pattern_selection_projected`，
   但 verifier 实际执行的固定 14 项漏掉二者，仍给出 14/14 PASS。
5. **当前设计模式文档与适配指南的主要问题不是内容表达，而是运行链没有消费它们。**
   本轮不能据此否定文档质量，但也绝不能据此宣称文档已真正指导 plan。
6. **Plan 还存在数个会直接传导到 coding 的契约问题。**
   包括状态查询归属、实名能力被默认 true 的模拟门替代、运行期开关被降成静态常量、敏感数据语义冲突、
   幂等边界走样等。内网不宜直接按当前 plan 编码。

因此，本轮总判定为：

| 目标 | 判定 |
|---|---|
| Story 给人读 | **骨架达标，终稿不达标** |
| Spec 正式闭环 | **达标** |
| Spec 规约/模式信号出现 | **达标** |
| Plan 普通结构与架构闭环 | **达标** |
| 应用域规约真正被 plan 系统消费 | **未证明 / 不达标** |
| 两个设计模式真正指导 plan 与契约 | **不达标** |
| 可直接进入 coding | **不建议** |

## 1. 实跑边界与可信度

### 1.1 执行方式

- 直接在当前工作区运行 CLI；**未使用沙箱、未复制临时仓**。
- 观测间隔为 60 秒。
- 第一段只跑 story→spec；第二段复用已闭环 spec，只跑 plan。
- coding 未启动，外层报告明确为 `next_phase_status=not_started_by_scope`。
- 正式 CLI 启动后冻结实现；本报告之前没有按测试发现回改代码或文档实现。

### 1.2 测试件指纹

两段使用同一扩展测试件：

```text
sha256: 46ad0c6e98888f91640430569f670eea96a31cf21ee6c920b94e6046d678fa1f
file_count: 51
root: doc/extensions
```

plan-only 复用上游指纹：

```text
sha256: 88befdadda5a7e7fb0b5de09def858b861102a06c37e776c1b22a8b81a8b71d1
file_count: 37
```

### 1.3 测试有效性限制

本轮不是干净盲测，原因有三：

1. 被测模型读取了 `test/story/AGENTS.md` 与 `test/story/TEST.md`，看到了评测流程和 S/R 判据。
2. 被测模型读取了旧 `output/story` 中的 acceptance、trace 和 plan 样本。
3. 观察者完整看过运行过程，最终 Story 回执虽独立于被测文档作者，但不是盲评。

因此，本轮可用于定位真实断链和评价产物，不能作为“无提示条件下能力已经自然生效”的独立证明。

## 2. 运行结果

### 2.1 离线回归（正式 CLI 前）

| 检查 | 结果 |
|---|---|
| `test/story` 全量 | 503 / 503 PASS |
| harness focused | 67 / 67 PASS |
| CLI runtime | 16 / 16 PASS |
| extensions harness | 6 / 6 PASS，0 FAIL / WARN |
| adaptation | 16 PASS |
| story-build | 36 PASS |
| template consistency | 91 PASS |
| design-pattern | 18 PASS |
| AR scope | 18 PASS |

这组结果证明实现的局部合同自洽，但不能替代真实模型运行。

### 2.2 story→spec

| 维度 | 结果 |
|---|---|
| 时间 | 2026-08-18 23:20:54 ～ 2026-08-19 00:03:00 |
| 耗时 | 2518 秒 |
| 目标边界 | `story` → `spec`，已到达 |
| Story build / merge / post check | PASS |
| Spec harness | PASS |
| Spec phase | quality PASS、semantic verified、closure closed |
| Story mechanical | FAIL（S6） |
| Story semantic | FAIL（独立回执合并后） |
| 总判定 | FAIL |

Story rubric v5 共 35 点：

```text
pass=26, fail=8, na=1, pass_rate=0.765
blocking_failed=
  S1-4, S2-1, S3-5, S5-3, S7-1, S6-1, R1-4
```

逐点证据见：

- `output/story/evaluation/cross-component-rich.json`
- `output/story/cross-component-rich/report_data.json`

### 2.3 plan-only

| 维度 | 结果 |
|---|---|
| 时间 | 2026-08-19 00:06:48 ～ 00:28:19 |
| 耗时 | 1286.6 秒 |
| resume | `start_phase=plan`、`previous_closed=spec` |
| 上游指纹 | PASS |
| Plan harness | PASS |
| Plan 内部 verifier | 14 / 14 PASS |
| Plan phase | quality PASS、semantic verified、closure closed |
| 外层 case | overall PASS |
| Coding | 未启动 |

`plan/reports/summary.json` 同时声明：

- functional PASS；
- visual PASS；
- asset UNVERIFIED / needs_human；
- `release_readiness=BLOCKED`；
- `completion_status=FUNCTIONALLY_COMPLETE_VISUAL_PENDING`。

所以“plan phase closed”不等于“产品已具备发布视觉证据”。本需求没有设计稿，当前只是
`semantic_layout` 盲档。

## 3. Story：对人是否合格

### 3.1 已经做对的部分

1. **阅读顺序对人友好。**
   不再按 spec 章节机械搬运，而是先解释为什么做，再讲全局旅程、本 AR 范围、页面流程、风险和上线。
2. **三层视角成立。**
   先讲完整挂失补卡旅程，再讲钱包处于发起/展示位置，最后收敛 AR90004 与 AR90005 的边界和依赖。
3. **关键取舍讲清了。**
   “不采用端侧先标记已挂失”同时给出所选方案、被否方案和理由。
4. **主要信息形态基本合理。**
   流程保留 Mermaid，参与方、异常、接口等并列事实使用表格，术语速查有 10 条实质内容。
5. **review 的单条表态结构可用。**
   每项都有当前建议、理由、影响、来源、责任人和同意/修改/暂缓三态。

这说明 Human-First 的结构方向是正确的，不需要退回“spec 摘要式 Story”。

### 3.2 仍不合格的部分

#### A. 内容守恒仍有缺口

缺失的典型上游事实：

- 仅“已绑定且状态为正常或疑似遗失”的实体卡可发起；
- 支付中断后保留未过期申请与支付意图，可从进度页继续；
- 通知失败后用户仍能主动查看进度；
- 用户确认支付前不得扣费。

Story 写出了全局参与方，却没有把这些用户可见约束完整保留下来。

#### B. 决策渲染出现机器拼接

例如：

```text
依赖 mock，不影响流程形态 本工程以模拟数据承载……
本工程设定基线 首屏加载 ≤2 秒……
```

同一决策值又在导读、范围、风险、技术附录和数值说明中多次整句重放。问题不是篇幅长，而是同一内容
没有唯一主叙述。

#### C. Story 与 review 的职责没有真正分开

- Story 顶部仍含待确认议题和“需运营确认”等议程措辞，机械 S6 失败。
- decisions.json 只登记 3 个工程设定；AR 承载/拆分、上线与协同、约束处置等实质决策仍直接写在 Story。

#### D. Review 不是决策全景

当前 review 只有：

1. 300ms；
2. mock 接口；
3. 2s/5s。

它没有覆盖产品规则、SE 技术约定、适用约束、上线协同、AR 拆分与承载。评审者无法只拿 review
逐项完成整场决策。

#### E. 表达仍有过度结构化

- 三种角色各建一张只有 1～2 行的小表；
- 应用域概览后又逐条重复同一结论，再紧接验收映射；
- 多个附录重新投影主文已经说过的内容。

因此当前 Story 的人读定性是：**可读的评审草案，不是可直接发布的评审终稿**。

## 4. Spec：规约与模式信号

### 4.1 正向结果

1. Spec 正式四件套闭环，外层 harness 也确认 closed。
2. Scope 明确：
   - 业务主责：AR90004 负责挂失申请与冻结前半段；
   - 物理修改：`WalletMain` + `Phone`；
   - `AccountManager` / `CommUI` / `CommFunc` 只消费不修改。
3. §10 正确登记：
   - 挂失申请流程 → `decision-tree`；
   - 申请/结果页交互 → `page-interaction`。
4. Story 附录中确实出现了 UX、安全、DFX、兼容、环境异常和交付域的命中判断。

### 4.2 仍需注意

Spec 闭环不等于内容没有契约歧义：

- F6 要求回前台恢复/刷新冻结状态，但技术契约只声明资格与创建；上游 `getReplacementProgress`
  又明确归 AR90005。
- SE 说重复创建由云端返回既有 `applicationNo`，spec §9.1 却写“幂等语义由端侧单例/申请上下文承载”。

这两个歧义后来直接导致 plan 自造 `getFreezeStatus`，并把服务端幂等降成了本地上下文短路。

## 5. Plan：模式/规约为什么没有真正生效

### 5.1 产物证据

以下文件全部搜索不到模式应用登记：

- `plan/plan.md`
- `contracts.yaml`
- `use-cases.yaml`

缺失项包括：

- 模式应用表；
- `decision-tree`；
- `page-interaction`；
- 实例名；
- 知识文件；
- 模式契约锚点；
- 按适用矩阵逐域给出的 plan 处置证据。

这不是只缺一个表头。模式文档要求：

- 决策树内部节点进 contracts，不进入 use-cases 的业务状态；
- 页面交互动作枚举进 contracts；
- use-cases 只保留用户可触发动作、完整业务序列和对外可观察状态。

当前 plan 直接设计了手写 `LossReportFlow`，use-cases 的 `state_model.phases` 混入 Idle、Loading、
Submitting、Failed 等编排状态，也没有决策树节点/页面动作管理器的契约投影。这证明缺失的不只是“观测标签”，
而是模式结构确实没有进入设计。

### 5.2 运行链双断点

#### 断点 1：作者阶段未消费 on_context_load

`doc/extensions/manifest.yaml` 已声明 plan 的两个 hook：

- `hooks/constraint-application.md`
- `hooks/design-pattern-application.md`

但 plan 作者在写 plan 前没有读取 hook、路由表、模式正文或 ADAPTATION。模型大量读取了 framework
门禁源码、parser 与 verifier prompt，却没有消费实例知识。

#### 断点 2：Verifier 固定清单漏投影 overlay 语义项

生成的 `plan/reports/ai-prompt.md` 已包含：

- `plan_constraint_coverage`；
- `plan_pattern_selection_projected`；
- 两段 lifecycle hook 原文。

实际 `verifier.report.md` 只执行固定 14 项，不含上述两项，仍返回 PASS。

结论：**规则进入了大上下文，却没有进入实际任务清单和闭环条件。**

### 5.3 设计模式文档与适配指南本身

就结构而言，当前两份模式文档已经能指导 plan/coding/review：

- 上篇讲适用与选型；
- 契约投影区分 contracts 与 use-cases；
- 下篇讲 SDK 行为、角色、文件、骨架、纪律和验证；
- ADAPTATION 明确目标内网应按“目标 Skill → 真实 SDK → 多个真实业务案例 → demo 仅结构参考”适配。

本轮失败不能归因于“文档写得不好”，因为被测 plan 根本没有读它们。准确说法是：

> 文档结构可用；准确性须由内网真实 Skill/SDK/业务仓完成适配；运行期消费链尚未证明有效。

## 6. 当前 Plan 的业务/技术缺陷

以下问题都应在进入 coding 前回到契约层收敛，不能让 coding 用局部补丁兜底。

### P0-1 状态查询接口越过上游边界

- Story 明确 `getReplacementProgress` 归 AR90005，本 AR 不落地。
- Plan 新造 `getFreezeStatus(applicationNo)` 并把刷新、降级、上下文恢复都建立在它上面。

需要先决定：AR90004 只展示 `createLossReport` 的即时冻结结果，还是确实拥有一个冻结查询接口。
若需要后者，必须回写权威契约、所有者和跨 AR 边界；不能仅在 plan 中自造同义接口。

### P0-2 既有实名要求被默认 true 的模拟门替代

Spec 要求进入既有实名引导；Plan 因 AccountManager 没有实名 API，改成 WalletMain
`SIMULATE_REAL_NAME_VERIFIED` 默认通过。

这不是同一需求。正向处置应是：

- 找到真实既有实名能力并消费；或
- 发起 Scope/契约提议；或
- 明确本轮无法验收实名分支并把它列为阻塞依赖。

不能用默认 true 模拟门宣称 AC-3 已完成。

### P0-3 运行期开关被降成静态常量

Story 说开关由运营/管理台控制放量；Plan 把它设计成 `LossReportConstants` 静态字段，并把“开关关”与
“无绑定卡”都压成 repository 返回 null。

这既失去运行时放量能力，也无法区分配置失败、关闭和无卡。应建立明确的配置 provider、来源、缓存和
失败策略；mock 只替换 provider，不改变开关语义。

### P0-4 敏感数据语义自相矛盾

- 接口签名正确要求 `createLossReport(cardNo, ...)`；
- use-case 又写“创建入参仅脱敏信息”。

正确边界应是：完整卡号可在内存中作为受控端云入参，禁止展示、日志、埋点和持久化；不能把脱敏串发给
需要真实卡号的云接口。

### P0-5 幂等语义从服务端走样为本地短路

SE 要求调用创建接口时，云端对同卡在途申请返回已有 `applicationNo`。当前 use-case 的
`in_progress_idempotent` 只在本地 context 存在时跳过创建，没有覆盖本地 context 丢失而云端仍有在途申请的情形，
也没有独立的 `APPLICATION_IN_PROGRESS` 返回分支。

正向模型应同时保留：

- 服务端幂等为事实真源；
- 本地 context 仅用于快速恢复，不替代服务端幂等。

### P1-1 状态模型混层

Plan 的状态图混合：

- 页面/流程内部状态：Idle、Loading、Submitting；
- 用户可见状态：已提交、已冻结、失败；
- 未完整声明的 Failed、LOADING_RESULT。

创建被拒且没有 `applicationNo` 时，又设计了 refreshStatus 路径。应用设计模式后，应把内部节点/动作与
业务可观察状态分开建模。

### P1-2 跨 AR 清理契约缺失

上下文声称在支付完成后清理，但支付由 AR90005 承担；Plan 没有定义 AR90005 如何通知或调用清理。
需要显式的跨 AR 事件/接口，或把本 AR 能负责的清理条件与后续 AR 的责任分开。

### P1-3 埋点只有名称，没有执行边界

Spec 已确认仓库没有埋点封装。Plan 只列 `loss_report_entry_click` / `loss_report_apply_result`，没有 provider、
调用接口、失败策略或 mock 边界。不能把“列出事件名”当成 F7 已设计。

### P1-4 动态文案与资源规则未统一

`policyText` 被定义为“云端文案，UI 原样展示”，同时 Plan 又声明所有文案必须 `$r('app.string.*')`。
需要区分：服务端动态业务内容、客户端固定 UI 文案和错误码本地化映射，避免 coding 阶段互相矛盾。

## 7. Harness 与模型行为问题

### 7.1 过度反查门禁源码

被测模型多次读取：

- `check-spec.ts` / `check-plan.ts`；
- fidelity / visual parity 检查；
- Markdown parser；
- verifier prompt；
- capability registry。

它甚至根据 parser 行为修路径和函数签名。这说明公开正向指南不足以让模型直接完成任务，最终产物存在
“适配检查器”倾向。

### 7.2 多次用管道运行门禁

模型使用 `2>&1 | Select-Object`、`2>&1 | Out-String`。PowerShell 管道可能让退出码代表最后一个管道命令，
不能证明 harness 本体成功。本轮外层 gate 独立复跑并取得 PASS，才避免误判。

### 7.3 历史输出泄漏

Feature 目录被重置，但 `output/story` 旧样本仍在，被测模型直接搜索并读取。只清理 feature 不能形成
独立样本环境。

### 7.4 Windows 旧输出回收失败

plan-only 首次启动前，`run_case.py` 三次在旧 OpenCode snapshot 的只读 Git pack 目录报：

```text
WinError 145: 目录不是空的
```

确认旧 worker 已终态且不存活后，将旧 case 原地改名为：

```text
output/story/cross-component-rich-plan-coding.stale-20260818
```

新 run 才能启动。旧结果仍可恢复，没有删除。

## 8. 正向优化设计（本轮不执行）

约束：**不修改 framework；Story 继续以人类评审为第一读者；不把 Story 机械化。**

### 8.1 建立实例级 Phase Knowledge Resolution

不要再依赖模型“自己想起”读 hooks。由 `doc/extensions` 提供一个明确的 plan 前置能力：

1. 进入 plan 后、代码研究前，解析 manifest 的当前阶段 hooks。
2. 形成实例级 resolution：
   - 当前阶段需消费的约束域；
   - spec 已命中的适用单元与 pattern_id；
   - 每个模式的目标 Skill / SDK / 业务案例来源；
   - contracts/use-cases 需要投影的锚点。
3. resolution 只进入 `context/facts.md > phase_delta:plan` 作为读取与适用证据，不另造业务台账。
4. 项目 AGENTS/实例 Skill 把该 resolution 设为 plan 的必经入口，覆盖不支持自动 hook 注入的宿主。

内网适配时，pattern_id 应解析到内网已有的两个真实 Skill；文档只是可审计知识，Skill + SDK + 真实业务案例
才是实现权威。

### 8.2 给实例扩展建立独立的 plan 闭环

在 `doc/extensions` 范围内增加正向的 plan post-check / instance verifier：

1. 若 spec §10 有命中，plan 必须登记：适用单元、pattern_id、实例名、选型理由、知识/Skill、契约锚点。
2. contracts 必须出现模式内部结构；use-cases 只保留用户可观察状态与序列。
3. 按 constraints 适用矩阵逐域检查自然设计落点；不要求独立台账。
4. verifier 输出必须显式包含 `plan_constraint_coverage` 与 `plan_pattern_selection_projected`；缺任何一项不得
   形成 instance PASS。
5. generic verifier PASS 与 instance verifier PASS 均存在，才把“模式/规约已生效”写入测试结论。

这不是给现有 verifier 打补丁，而是在实例扩展层建立完整、可迁移的知识消费闭环。

### 8.3 Human-First Story 的编辑合同

1. Story 主文只保留：导读、全景、范围、场景/体验、风险、上线；术语/技术/质量放附录。
2. 每个事实有唯一主叙述章；其他位置只做一句指向。
3. 决策 token 必须**整段替换**，不得让作者先写同义值再拼 `display_text`。
4. Story 陈述当前建议值、理由和风险，但不写“谁确认/评审时确认”等议程；议程只在 review。
5. Review 按六类来源扫描决策全景，但只登记真正适用/实质影响实现的项，不要求所有 rule_id 每次全命中。
6. 规约回显按“域 → 本需求是否命中 → 设计落点”组织；只有命中的条目再带 rule_id 作为追溯证据。
7. 不设置表格数量、段落长度等机械配额；由信息形态决定表/图/段落。

### 8.4 先收敛业务契约，再谈模式结构

下一轮 plan 前先解决五个权威问题：

1. AR90004 是否拥有冻结状态查询；若有，接口和 owner 是什么；
2. 真实实名能力从哪里消费；
3. 功能开关的运行时 provider 与运营控制链；
4. 完整卡号在端云传输、展示、日志、持久化四个面的分类；
5. 服务端幂等、本地恢复与 AR90005 清理通知的责任划分。

这些结论写入 spec/contracts 真源后，再用两个真实模式 Skill 做结构投影。这样 coding 不需要猜，也不会用
默认 true、静态常量或自造接口填洞。

### 8.5 测试环境改为“新 run 不删除旧 run”

为避免 Windows snapshot 清理和历史污染，采用 run-id 目录：

```text
output/story/runs/<case>/<run-id>/...
output/story/<case>/latest.json
```

- 每次 start 新建目录，不递归删除旧 XDG snapshot；
- XDG/CLI cache 与审计产物分离；
- latest 只指向终态 run；
- 历史归档由单独、可恢复的保留策略处理；
- 被测 prompt 明示业务执行模型不得读取 `test/story` 与历史 `output/story/runs`。

### 8.6 门禁命令与观测

1. 被测模型直接运行 harness，不接 `Select-Object` / `Out-String` 管道。
2. 外层 harness 继续记录 command、cwd、真实 returncode、stdout/stderr tail。
3. 测试报告把“被测模型自述 PASS”与“外层独立 gate PASS”永久分栏。
4. 保持 60 秒观察间隔与 heartbeat/lease 机制。

## 9. 下一轮验收条件

下一轮只有同时满足以下条件，才能宣称原始诉求解决：

### Story

- 35 点语义回执无 blocking fail；
- 决策渲染无拼接重复；
- review 覆盖适用的决策全景；
- 被测模型未读测试判据与旧产物。

### Spec

- 正式 closure 继续 PASS；
- 适用模式信号按需求命中，不要求所有模式都命中；
- 状态查询、实名、幂等、开关等契约无自相矛盾。

### Plan

- author 阶段在写 plan 前真实消费两个模式 Skill/知识；
- plan 有模式应用表，两个适用单元分别登记真实 pattern_id/实例/理由/锚点；
- contracts/use-cases 投影符合模式边界；
- 约束矩阵中 plan 非「—」域都有自然设计落点；
- generic verifier 和 instance verifier 都实际检查模式/规约项；
- coding 仍不启动。

## 10. 边界核验

- 本轮没有新增 framework 修改。
- `framework/skills/feature/spec/contract.yaml` 仍是实跑前已存在的单行 diff，SHA-256 保持：
  `3DA24DE44850266E3437247FFA2891AAFB8AE119BBF5598589D4011327B13E8F`。
- 被测 plan 会话没有写产品代码；工作树中既有的 `oh-package.json5` 修改保持原样，未回滚也未覆盖。
- 本报告落盘后未执行任何报告建议。

## 11. 证据索引

- 方案基线：`08-最新实跑结论与Human-First正向优化方案.md`
- Story 逐点回执：`output/story/evaluation/cross-component-rich.json`
- Story 运行报告：`output/story/cross-component-rich/report_data.json`
- Plan 运行报告：`output/story/cross-component-rich-plan-coding/report_data.json`
- Story：`doc/features/AR90004/AR/story.md`
- Review：`doc/features/AR90004/AR/review.md`
- Spec：`doc/features/AR90004/spec/spec.md`
- Plan：`doc/features/AR90004/plan/plan.md`
- Contracts：`doc/features/AR90004/contracts.yaml`
- Use cases：`doc/features/AR90004/use-cases.yaml`
- Plan verifier prompt：`doc/features/AR90004/plan/reports/ai-prompt.md`
- Plan verifier 结果：`doc/features/AR90004/plan/reports/verifier.report.md`

