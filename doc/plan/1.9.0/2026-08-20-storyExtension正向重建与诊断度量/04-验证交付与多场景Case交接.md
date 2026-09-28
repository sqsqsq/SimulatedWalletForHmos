# 验证交付、多场景 Case 与后续交接

> 状态：多场景 Case 已构造并通过静态验证；全部 Story CLI 实跑与多 Case CLI 仍待交接  
> 本文件定义当前执行者怎样验证 01、02、03，怎样构造覆盖 Story 功能的多场景需求 Case，以及实施完成后怎样向下一模型交接。  
> 当前执行者不构建 Demo Logger/VOC/Chart，不实现多 Case CLI，也不执行任何 Story CLI 测试。

## 1. 两类工作不能混在一起

本轮同时需要“生产能力正确”和“测试输入充分”，但二者职责不同：

- Story、Knowledge、ADAPTATION、Hook 和 overlay 是生产交付；
- `test/story/cases`、mock-data、workspace 和评价材料是测试资产；
- Case 用来暴露生产问题，不能把 Case 的标题、关键词、文件顺序或期望正文写回生产规则；
- 当前执行者构造 Case 并用离线检查验证它们可独立装载，但不调用现有单 Case runner 的任何测试命令；
- 下一模型先执行现有单 Case 正式实跑，再构建多 Case CLI 并执行全部 Case，不另造 Story 生产协议。

## 2. 当前执行者的验证范围

### 2.1 必须完成

1. Story 全量输入、目标结构、写作、装配、Review 和迁移的确定性回归；
2. Knowledge 三类目录、Manifest 激活、ADAPTATION 和阶段消费回归；
3. 诊断与业务度量的 Knowledge、Spec/Plan 合同、Coding/Review 消费规则回归；
4. 多场景需求 Case 的构造、静态装载、路径和测试隔离检查；
5. Framework `extensions` gate 和当前实际执行 phase 的正式闭环；
6. clean tracked snapshot；
7. 当前范围报告和实施后新建的 07 交接文档。

### 2.2 明确留给下一模型

1. Demo 工程 `Logger.debug`、`VocReporter`、`ChartReporter` 的代码、导出、lint、编译与故障测试；
2. 多 Case CLI 的调度、隔离、并发控制、聚合和命令界面；
3. 全部 Story CLI 测试：现有单 Case 正式实跑、多 Case CLI 执行、逐 Case 语义评价与汇总报告。

当前执行者不得用桩 API、文档声明或跳过 Coding/Review 证明 Demo 能力已经完成。

## 3. 多场景 Case 构造原则

### 3.1 构造的是需求输入，不是期望 Story 答案

每个 Case 只提供正常用户会给出的需求材料、起止阶段、必要交互和证据目标。不得预写一份“正确 Story”让模型照抄，也不得把测试判据、章节答案、模式采用结论或评价标准放进 prompt。

同一事实的叙述变体只改变表达，不改变语义。必须先固定一份事实并集，再分别改写文件名、标题、顺序和叙述形态；任何变体新增或删掉事实都不算反过拟合对照。

### 3.2 复用现有 Case 结构

继续使用现有：

- `test/story/cases/<case-id>/case.yaml`；
- `test/story/mock-data/`；
- Case 自己的 `workspace/`；
- `start_phase`、`end_phase`、`interactive`、`evidence_targets` 和 `suggested_reply`；
- `run_case.py` 的单 Case 生命周期和不可变运行目录。

不新增 Case schema、第二份运行状态、预期 Story 文件或生产侧 Case registry。覆盖关系写在本文件和最终报告，不成为被测输入。

### 3.3 先复用，缺口才新增

实施时先逐个核对现有 Case。一个现有 Case 已经自然覆盖某场景时，只修正失效材料或 evidence target；只有场景确实无载体时才新增 Case。不得为每个小检查复制一整套 RR/SR/AR。

## 4. Story 场景覆盖矩阵

下表覆盖 Story 的有效输入、范围收敛、成文内容、决定与 Review、图片和生命周期。`载体` 是实施时的优先复用对象；最终 Case ID 以交付报告为准。

| 场景 | 必须证明什么 | 优先载体 |
|---|---|---|
| 标准单特性 | 单 AR、材料齐全、无兄弟特性时可直接成文；不生成空的相关特性内容 | `narrative-brief`、`narrative-role`、`narrative-process` |
| 跨部件完整需求 | Story 能说明完整业务、当前范围、参与方协作、接口、数据、配置、事件、质量、风险、验收和上线 | `cross-component-rich` / `pattern-image-review` 的需求材料 |
| 一个 SR 拆成兄弟 AR | 说明拆分原因、各自职责、交接结果、依赖顺序、共享状态生命周期和阻塞关系，不复制兄弟内部实现 | `split-two-ar` |
| 单 AR 在范围关卡拆分 | 人在关卡提出拆分后，当前特性和剩余范围都能落清；事先说明与现场口述两种入口均成立 | `split-interactive`，`split-by-feature` 作为对照 |
| 补充材料与任意文件名 | docx、Markdown、图片等材料经现有导入链进入同一版本上下文，不因文件名和标题变化漏读 | `docx-supplement` |
| 同轮来源冲突 | 互斥事实进入 decisions/Review，模型不自行选版本，Story 可保留未受影响草稿但不能定稿或归档 | `source-conflict-review`；解决意见仅放人工回话，不进入初始 prompt |
| 图片与原型 | 所有最终图片有非空 alt；本地图片可打开且不越界；remote/data 不联网也不误报缺失 | 扩充跨部件 Case 的测试材料和确定性正反例 |
| 决定与人工评审 | settled/open 决定各有正确投影，Review 可表态、回流和处置，且不是第二份 Story | `review-reflow` |
| 归档与恢复 | Story/Review 同组归档，失败不破坏工作区；restore 使用既有真实契约恢复平台侧版本 | 复用现有归档材料，补一个最小 archive/restore Case 或在既有生命周期 Case 中覆盖 |
| 非 AR 本地起手 | 问题单或工单按现有本地起手进入同一 Story 生产链，不错误要求需求系统 token | `local-ticket-start` |
| 同事实不同叙述风格 | 段落式、表格/清单式、按流程叙述和按角色叙述等合法材料都能完整取材，最终内容守恒 | `narrative-brief`、`narrative-role`、`narrative-process`；三者事实 token 相同，标题与组织不同 |
| 条件内容 | 无术语、无兄弟特性、无上线动作时不造空内容；存在状态、规则、异常、质量或上线要求时有自然落点 | 标准单特性与跨部件 Case 互为正反例 |

`help` 只输出固定流程，不生成 Story，用确定性测试覆盖即可，不为它单建需求 Case。

## 5. Case 内容覆盖

至少有一个富场景 Case 同时覆盖以下内容，防止新结构以“去重复”为名删除唯一事实：

- 背景、术语、范围、业务方案、完整流程和当前特性功能；
- 主路径及全部有效分支；
- 状态、业务规则、协作、等待、失败和恢复；
- 被否方案、采用方案和理由；
- 接口请求/响应、错误语义、数据、配置和事件；
- 兼容、数据保护、界面适配、翻译、质量、风险和上线；
- 产品、当前特性、跨特性和质量验收；
- 每个原始编号、表行、限定/否定条件、数值、图片和来源。

同一内容可由一个 Case 同时覆盖多个场景。覆盖矩阵要求场景有证据，不要求 Case 数量最大化。

## 6. Case 构造验收

每个 Case 在交付给下一模型前必须满足：

1. `case.yaml` 能被现有 loader 读取，字段和阶段合法；
2. feature、mock-data、workspace 和图片路径存在且不越根；
3. 不读取其他 Case 的 workspace，不写仓库共享真实路径；
4. 自动与交互 Case 的回答方式符合 `TEST.md`；
5. 交互回答使用自然语言，不照抄内部选项 key；
6. 测试判据、预期正文和维护文档不进入 prompt；
7. 同事实变体经过逐项对照，事实集合一致；
8. 覆盖矩阵中每个场景至少有一个明确载体；
9. 新增 Case 只修改 `test/story` 测试域，不引入生产规则；
10. 当前执行者不以“Case 文件存在”声称模型行为已通过。

## 7. 当前执行者的证据层次

### 7.1 Extension 确定性回归

使用现有测试覆盖：

- Story 全量材料枚举和纯输出章节合同；
- 06 的二级顺序、条件内容和模板占位清理；
- scaffold/build 失败不破坏旧有效产物；
- decisions v2、ids v1、Review 人工区、图片和每个原始验收编号；
- selector/primary/Spec 形态镜像、README 扫描和 Story Knowledge 静态直链已经删除；
- Manifest 精确激活、正式交付与运行激活分离、零 pattern、零命中、候选、采用和不采用；
- ADAPTATION 自包含，本仓默认激活两份模式；其他目标仓未激活的默认模式不要求适配，Extension 不读取 `test/story`；
- `project_knowledge` 和 `observability` 精确引用；
- Coding 读取真实源码和冻结合同，不重新通读 Project Facts；
- 诊断与业务度量合同不依赖尚不存在的 Demo Reporter。

### 7.2 下一模型执行的 Story 语义评价

Story CLI 运行由下一模型执行。每个 Case 的确定性检查通过后，独立评价者完整阅读 `AR/story.md` 和 `AR/review.md`，再对照同一轮 RR、SR、AR、UX、补充材料、Spec、Acceptance 和 decisions 取证：

| 判据 | 本轮重点 |
|---|---|
| S1 | Story 独立可读，无需外查才能理解 |
| S2 | 编号事实和无编号事实都未丢失或走样 |
| S3 | 顺序按人的理解推进，不搬运 Spec 目录 |
| S4 | 关键选择包含采用、否定和理由 |
| S5 | 段落、表格和图回答不同问题，形态贴合内容 |
| S6 | 开放问题和人工议程只进入 Review |
| S7 | 每个事实只有一个完整主叙述，没有无价值重复 |
| R1～R4 | Review 可开会、逐项可答、有表态位且不是第二份 Story |

S2/S7 以固定输入快照全量核对编号、表行、规则、限定/否定条件、数值、图片和全部有效业务分支。每项在报告中给出来源、Story/Review 唯一主落点和最终证据；缺失、走样或多个完整主叙述均失败。

### 7.3 Framework 正式入口

按影响范围使用现有入口：

1. Extension 专用检查验证领域合同；
2. Framework `extensions` gate 检查 Manifest、Hook、overlay 和文件协议；
3. 当前执行者只运行不启动 Story Case 的 Extension/Framework gate；
4. Story、Spec、Plan 的 active workflow Harness、独立 Verifier、`trace.json` 和完成回执随 CLI 实跑交给下一模型。

Extension 专用检查不能签发 phase PASS，Framework gate 也不能替代独立 Verifier 或回执。

### 7.4 Clean tracked snapshot

在只包含拟交付 tracked 内容和明确依赖的干净快照中验证：

- Extension 可以加载；
- Story、Knowledge、ADAPTATION 和 Case 静态测试可以运行；
- 后续正式 Case 所需配置不依赖本地未提交文件；
- `test/story`、历史输出和实例私有路径不是生产运行时隐含依赖；
- 未构建 Demo Reporter 被明确标为后续项，不通过未跟踪 SDK 假装存在。

### 7.5 下一模型执行全部 Story CLI 测试

当前执行者不调用以下任何命令：

- `run_case.py ... run/start/poll/status/reply/stop`；
- 后续多 Case CLI 的任何命令；
- 通过这些入口间接启动的 Story/Spec/Plan/Coding/Review Case。

下一模型先用现有 runner 运行一个代表性单 Case，再用新多 Case CLI 执行全部 Case。所有 CLI 实跑共同遵守：

- 开始前冻结被测版本和工作区状态；
- 被测模型不得读取 `test/story/AGENTS.md`、`TEST.md`、`EVOLUTION.md`、本目录方案、测试答案或旧报告；
- 运行期间不产生提交、不修改评分标准；
- 每个已执行 phase 保存产物、日志、Harness、Verifier、Trace 和回执；
- 最终 state、last phase、execution status、报告和源码事务一致；
- 失败保留原始证据，不通过修改输入标题或关键词补跑成 PASS。

当前交付报告必须把这些行为证据标为“未执行，已交接”，不得用离线测试代替。

## 8. 当前范围交付报告

当前执行结束后提交一份报告，至少包含：

1. 修改文件和责任层；
2. 旧机制删除清单；
3. 00 中当前范围守恒项的逐项证据；
4. Extension、Framework phase 和 clean snapshot 结果；
5. 多场景 Case 清单、复用/新增情况和覆盖矩阵；
6. 每个 Case 的材料位置、交互方式、起止阶段和静态验证结果；
7. 明确未构建 Demo Reporter、未实现多 Case CLI、未执行任何 Story CLI 测试；
9. 已知失败、阻塞和是否影响下一模型；
10. 07 的路径和使用方式。

## 9. 实施完成后新建 07

`07-剩余能力构建与测试交接.md` 只能在当前实施和报告完成后创建，因为它必须引用真实最终状态。至少写清：

1. 当前交付的 commit/工作区指纹和通过的检查；
2. Demo Logger/VOC/Chart 的准确代码边界、已冻结合同、目标 API、数据边界和测试命令；
3. 多 Case CLI 必须复用的现有 runner 能力和不得重复建设的部分；
4. 可并行条件：不同 feature 的 Story/Spec/Plan；不可并行条件：同 feature、共享阶段状态、任何包含 Coding 的源码事务；
5. 全部 Case 清单、覆盖场景、交互要求、起止阶段和预计输出；
6. 执行顺序：先执行现有单 Case基线，再完成并验证 Demo 能力，再实现 CLI，最后执行多 Case；
7. 逐 Case 机械/语义评价、汇总报告和失败保留要求；
8. 下一模型禁止修改的生产合同、Framework 边界和评测判据；
9. 从哪里继续、怎样判断最终整轮 PASS。

07 是执行交接，不重复抄写 00～06 的设计论证，也不预填未执行测试为 PASS。

## 10. 当前执行者停止条件

当前执行者完成以下动作后停止：

1. 当前范围代码、文档和 Case 资产完成；
2. 当前范围离线、静态、Framework 非 Case 验证和 Case 构造报告完成；
3. 07 按实际状态完成；
4. 明确列出三项后续工作仍未实施；
5. 停止等待用户把 07 交给下一模型。

不提前实现多 Case CLI，也不执行任何现有或新增 Story CLI 测试。
