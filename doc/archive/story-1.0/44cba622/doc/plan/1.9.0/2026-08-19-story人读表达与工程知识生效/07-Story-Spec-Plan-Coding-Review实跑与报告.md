# 步骤 7：Story→Spec→Plan→Coding→Review 实跑与报告

> 前置：[安全实施与离线验证](06-安全实施与离线验证.md) 全部通过  
> 本步交付：Story 人读质量、Spec 稳定性、Plan 工程知识冻结、Coding 落地与 Review 审查的正式证据报告。

## 1. 执行边界

- 使用 `test/story/TEST.md` 的后台 `start/poll/status/stop` 接口；
- 直接在当前真实工作区运行，不使用沙箱、临时副本或隔离工作树；
- 普通观察批次按 `next_poll_after_sec=60` 每分钟轮询一次，`has_more`、人工关卡和终态立即处理；
- 被测模型只获得正常 Skill 请求和业务材料，不读取 `test/story/`、评价结论或历史 run；
- 正式流程推进到 Coding 与 Review；UT、Testing 留给内网按步骤 5 验证；
- Coding 实跑置于受控源码事务中：先保存当前源码状态，再建立干净基线，取证后恢复实跑前字节状态；
- 测试结束只形成报告，不依据报告自动修改实现。

## 2. 运行前有效性检查

1. 冻结当前被测版本指纹；
2. 清理会污染业务输入的旧 feature 与测试需求术语，保留工程基础术语；
3. 创建新的 run-id，确认 `active.json` 指向本轮；
4. 核对被测 prompt 不含测试判据、历史分析或旧产物；
5. 记录 framework 快照和当前无关工作树状态；
6. 确认 `start_phase/end_phase` 只覆盖本轮需要的阶段。

若模型轨迹读取 `test/story/` 或历史 `output/story/runs`，报告将该轮标为污染；产物仍可用于定位问题，但不能作为无提示条件下能力成立的证据。

## 3. 三段式运行

### 3.1 Story→Spec

1. 以新 run-id 启动目标用例；
2. 完成 Story 流程与 Spec 阶段；
3. 取得 Story、Review、Spec、trace、门禁和模型行为流；
4. 按当前 truth/rubric 完成独立 Story/Review 语义评价；
5. 确认 Spec 四件套闭环及 §9/§10 内容。

### 3.2 Plan-only

1. 复用上一段已闭环的 Spec 和上游指纹；
2. `start_phase=plan`、`end_phase=plan`，不重跑 Story 或 Spec；
3. 取得 Plan、contracts、acceptance/use-cases、post-check、verifier 和模型行为流；
4. Plan 终态后冻结 `plan.md`、`contracts.yaml` 和上游指纹，作为 Coding 的唯一输入基线。

### 3.3 Coding→Review

1. 复用上一段已闭环的 Plan 和上游指纹；
2. `start_phase=coding`、`end_phase=review`，不重跑 Story、Spec 或 Plan；
3. 在源码事务中完成 Coding，保存源码 diff、变更清单、编译/lint 与阶段 closure 证据；
4. Review 继续读取同一轮真实 diff，逐项审查模式实例与规约义务；
5. Review 终态后停止，确认 UT 未启动；
6. 将所有源码证据归档到 run 目录，然后恢复实跑前源码状态并验证恢复指纹。

## 4. Story / Review 评价

评价者完整通读最终产物，再按当前判据逐项取证：

- 只读 Story 即可理解问题、价值、范围、整体方案、场景、体验、系统边界、风险和验收；
- H3/H4 按真实对象形成，标题树能够复述章节逻辑；
- 段落、列表、表格、流程图、状态图、时序图、图片和强调按信息关系使用；
- 同一事实只有一个完整叙述位置，附录提供查询而不复制主文；
- Story 不承担会议议程，也没有待确认汇总或机器拼接；
- Review 覆盖实际决策全景，人工表态结构可用，并能回到 Story 唯一上下文；
- truth/rubric 的全部必过观测点通过，且没有标准外实质缺陷。

机械门禁结果直接采纳其机械项，不用它替代语义结论。

## 5. Spec 评价

- 现有 Spec 结构、Scope、术语和正式 closure 无回归；
- §9 技术契约完整且不存在 owner、幂等、配置、数据和跨 AR 边界矛盾；
- §10 按实际适用单元登记候选信号，零命中合法；
- Spec 只登记候选，不替 Plan 做模式选型；
- Story 条件编排没有污染普通 Spec。

## 6. Plan 评价

### 6.1 设计模式

- 每个 Spec 候选有采用/不采用结论和需求化理由；
- 采用项同时出现在 `plan.md > 工程知识应用契约` 与 `project_knowledge.pattern_applications`；
- 每个实例改变真实文件、接口、组件、角色、状态或行为设计；
- 内部结构进入 contracts，可观察行为进入 acceptance/use-cases；
- 结构锚点和行为锚点足以供 Coding、Review、UT、Testing 消费；
- 零命中时没有伪实例。

### 6.2 应用域规约

- 适用矩阵 Plan 列每个非“—”域都有本需求事实和处置；
- 只有实际命中项登记 `rule_id`；
- 命中项改变设计并形成实现、审查和验证锚点；
- 域相关但规则零命中时有事实依据，不编造编号或义务。

### 6.3 闭环

- Plan post-check 对候选、ID、表/契约同步和锚点给出确定性结论；
- verifier 明确输出 `plan_constraint_coverage` 与 `plan_pattern_selection_projected`；
- 表格和 ID 仅作为追溯，语义评价确认设计本身确实变化；
- Plan 产物及上游指纹在 Coding/Review 续跑期间保持不变。

## 7. Coding / Review 评价

### 7.1 Coding

- 每个 `project_knowledge.pattern_applications` 实例在真实 diff 中有对应结构、角色或协作边界；
- 每个 `constraint_obligations` 义务在声明的实现锚点落地，未命中的域不产生伪实现；
- 实现保持 contracts 与可观察行为，不在 Coding 阶段重新选型或静默改变 Plan；
- 编译、lint、阶段 harness、verifier 与 receipt 均有可复核凭证；
- 源码 patch 与变更文件完整归档，事务恢复后工作区与实跑前指纹一致。

### 7.2 Review

- `review/review-report.md` 逐实例审查设计模式使用约定及其真实 diff；
- 逐义务审查实际命中的规约落点，并引用文件、符号或配置证据；
- 能区分 Coding 偏差、Plan 设计错误与 Spec 契约错误，给出正确 correction layer；
- 未命中项、纯结构模式和无法验证项按事实说明，不用登记或措辞冒充通过；
- Review closure 完成，UT 未启动。

## 8. 业务语义探针

评价者使用本轮真实需求中的问题验证知识是否改变设计，包括但不限于：

- 状态查询接口及 owner；
- 真实能力缺失时的处置，而不是默认成功模拟；
- 功能开关的运行时 provider、来源和失败语义；
- 敏感数据在传输、展示、日志和持久化各面的边界；
- 服务端幂等事实源与本地恢复的分工；
- 内部编排状态与外部可观察状态分离；
- 跨 AR 清理、通知或事件契约；
- 埋点 provider 与失败边界；
- 动态业务内容、固定客户端文案和错误本地化分层。

这些探针只属于评价材料，不写入通用 hook。应用表存在而上述设计仍错误时，结论是“观测信号出现，工程知识未生效”。

## 9. 正式报告

报告写入本方案目录的下一编号文件，至少包含：

- 被测版本指纹、case、run-id 和执行时间；
- 执行、机械、语义、阶段 closure 和总体结论；
- Story/Review 的逐项人读证据；
- Spec 技术契约、候选信号和稳定性结论；
- Plan 候选处置、设计投影、机器交接和 verifier 证据；
- Coding 的真实 diff、模式/规约落地、编译/lint 和源码事务恢复证据；
- Review 对模式实例、规约义务和 correction layer 的逐项审查证据；
- 正向命中、部分命中、零命中和业务探针结果；
- 被测模型的知识读取与修订轨迹；
- 污染检查、测试可信度和任何阻塞；
- 每个问题的最早责任层与正向优化建议；
- 明确声明 UT、Testing 本轮未实跑，不能用离线合同冒充内网验证结果。

报告落盘即结束本轮。报告中的建议不触发自动实现。

## 10. 完成条件

- Story、Spec、Plan、Coding、Review 均有可复核的正式证据；
- 能明确回答规约和设计模式是否在当前实际需求中生效；
- 能区分“信号/登记出现”与“设计真实改变”；
- 运行没有测试判据或历史产物污染，或已明确标记污染限制；
- Review 结束后没有启动 UT；
- Coding 源码证据已归档，当前工作区源码恢复为实跑前字节状态；
- 报告完成后运行期文件保持测试开始时的版本指纹。
