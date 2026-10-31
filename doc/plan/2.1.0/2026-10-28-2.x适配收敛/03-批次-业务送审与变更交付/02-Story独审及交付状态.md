# 步骤02：Story独审及交付状态

本步使业务表达得到真实独立审查，并让缺少Story审查员的组合自动、诚实披露未审；不增加人工免审批准。本步待实施，不把当前方案自查称独立评审。

## 1. 输入和职责接口

必读[批次方案](00-批次方案.md)、[目标接口与状态](../参考/01-目标接口与状态.md)、步骤01、主Spec R6—R8及AC5—AC8、TEST§6.5和本版标准。输入为当前Story/Review、实际原件及转换/图片、有效人答、当前蓝图及其原生人读稿、事实与实体义务、实际宿主能力/独审配置、已存在原报告及当前对象摘要。

蓝图原生质询负责共同设计的完备、冲突、契约与准入；Story独审负责业务叙事完整、原件理解与表达、页面体验、图文阅读、跨稿一致性和Review真实裁决。Story审查可发现设计缺口并指回承担者，但不重复全套技术论证，更不能以业务PASS替代蓝图准入。source核真实原件，不能只读作者冻结摘要。设计参考按步骤01直接读原生投影，不强制额外副本再过一次独审。

## 2. 状态与决策

| 当前事实 | 业务交付处理 | 后续责任 |
|---|---|---|
| 当前对象真实独审PASS | 记录真实结论及对象；按原授权交付 | 不扩大施工/发布授权 |
| 当前对象有非阻断建议 | 作者采纳，或说明保留依据与影响；按合法处置继续 | 不为清WARN固定返修轮数，不另造Review审批 |
| 当前对象已知FAIL/必修未复核 | 交付门保留缺陷和待核，不能被未审声明覆盖 | 修责任真源，对变更对象作必要复核 |
| 宿主未声明可用Story独审且没有被遮蔽的必修 | 自动未审，Story/Review、登记、交付/更新一致披露 | 不问waiver，不冒称DSH通过；真实行为验收仍未覆盖 |
| 声明独审可用但调用/报告/对象绑定失败 | 说明调用故障或报告无效，不猜成PASS或免审 | 沿原调用恢复，保原错误和报告 |
| 蓝图未准入但业务草稿诚实 | 可按已有权限业务送审，列真实限制 | 施工准备仍服从原生质询/准入 |

未审是审查事实，不是业务完成、设计准入或发布质量结论。对象变化使旧结论不再代表当前稿；仅登记/时刻变化不触发内容返修或重复计时。历史FAIL原件保护，当前有效发现的去向和复验结果明确，不按“最新一条文字”或历史closed覆盖。

## 3. 文件动作与顺序

1. `scripts/core/story/review-object.mjs`的`reviewObject`/`contractSources`收敛对象：待审Story与Review，原生设计参考及其实际source_ref、`materials.json`列出的真实原件/阅读件/图片和会议版本作为对照。材料选用不缩掉核源集合；二进制原件可字节绑定，文本/图面按实际能力阅读。去掉`readFrozenInputs`、冻结副本alias优先及固定`AR/design-review.md`必存在分支；同一原件的转换关联沿来源索引取得，内容不同不得当alias。
2. `hooks/shared/reader-review-task.mjs`、`review-inputs.mjs`与`scripts/core/story/independent-review.mjs`的`prepareReview`/`dispatchFor`用同一对象清单生成任务、原生请求、摘要绑定及覆盖要求。任务先交业务完整性和阅读责任，再列必要核源；不要求复审全部蓝图技术决定。图面未取得就明确未覆盖，不用图文件存在替代图义审查。
3. `independent-review.mjs`的`hostReviewer`相关调用、`reviewResult`、`pendingDisclosure`、`discloseInStory`和`reviewStatusBlock`改为实际能力自动披露；撤下`disclosedWaiver`、`waiverCheck`及`review_waiver`、`waiver_at`、授权原话匹配职责。保留`preparedRecord`、对象绑定、原报告字节保护、`alteredReplies`和报告故障诊断。`review-report-contract.mjs`及其实际调用处同步，不把历史报告改签成新状态。
4. `scripts/core/flow/lifecycle.py`、`story_flow.py`及`flow/state.py`撤下免审命令、参数、状态和路由提示，`flow/routing.py`、`phase_facts.py`、`phase-closure.md`不再引导逐版批准；保既有Story登记时刻、真实`story_written_at`和usage完成语义。`phases/design.md`、`phases/update.md`及SKILL入口同步问法，原同范围授权继续，不重问交付选择。
5. `story/delivery.mjs`的`deliveryProblems`只组合当前来源/设计依据、Story审查事实和当前必修；`deliveryNextSteps`按已有授权直接指向实际后续，未指定才问一次。`appendix.mjs`的设计副本门由当前原生投影引用/摘要核对替代。`review.mjs`渲染机器区状态并逐字保护人工区；`flow/publish.py`、`flow/update.py`和`flow/lifecycle.py`登记直接消费同一结果，不再从独审目录存在或`review_waiver`推断资格。

本节路径前缀除hooks外均为`extensions/skills/story/`；跨批已改接口以共享合同为准。本步不改Framework通用质询规则，不删除必要本地宿主独审Preset，不把原生`deepseek-harness`改名当作本地DSH独审已接替。

## 4. 退出、验证与完成

整体退出免审批准的生产者、CLI、状态、模板问法、交付/更新/归档读取和专用回归；新承担者是宿主实际能力与当前对象的审查事实。保独立审查、原件核源、图义、人工意见、对象新鲜度、报告不可篡改及已知缺陷修复。通用知识应用账本的覆盖要求由facts/实体义务与真实产物语义核对接替，不删知识链责任。

后续实施在`test/tests/test_review_modes.py`、`test_review_task_boundary.py`、`test_review_closure.py`、`test_story_build.py`和`test_spec_story_gate.py`定向覆盖：无审查员自动未审且无waiver问话；声明可用却失败保故障；已知FAIL后能力消失仍不放过必修；对象改动需必要复核，流程时刻变化不伪造内容变化；非阻断建议有据保留不强迫循环；业务送审不代准入；人工区和原报告字节保持。采用真实prepare→请求/报告消费→交付门的测试入口，不预填通过状态。

独立语义核任务是否真按业务/设计分责、核源有没有只剩摘要、建议是否掩盖缺陷、未审披露是否让读者正确判断。正常DSH组合需后续按实际入口证明作者输入、独审调用/缺口、修正与交付登记一致；无审查员的离线结果不计DSH通过。

完成须所有实际消费者同口径，已知FAIL不被覆盖，免审整条退出且保持项成立。预计G260/X420，沿[共享预算](../参考/03-预算与计量.md)和AGENTS§5；每步写增量交回并提交，前置成立继续步骤03。

## C批复评后的有效补正（2026-10-31）

D00§3统一无审查员的prepare结果、dispatch和终端下一步，直接check/登记而不指派不存在的审查者；已知必修原件及摘要沿首读后的既有context送达恢复审查者，按实际处置复验，不建新批准或问题账本。D00§5的单动作ctx/来源复用与组合登记保持本步所有检查、原报告保护及写入边界，不跨命令缓存。
