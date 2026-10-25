# Step2.2 v3 独立实施复核

> 2026-09-09。审查基线 6ca48c41 → 17b6521a，包含首次实现、预算调整与 reviews/19 后的返修。本次仅审查及隔离验证，未修改生产代码、未启动真实 CLI。

## 1. 结论

主体替换成立，但尚有三处可复现的确定性缺口，不能按“全部实现问题已关闭”收口。它们修在现有函数，不需要重写方案或增加任务机制。真实模型效果仍待验。

本次独立核对了指导区写入/剥除、共用范围函数、局部检查、后继恢复、审查全文与实际判定、旧职责退出及生成命令。没有仅依据 reviews/19 的通过结论复述批准。

## 2. 必须修正的发现

### R1 [P2] 整体承载的空范围仍能生成指导区

位置：`doc/extensions/skills/story/scripts/core/flow-check.mjs:163` 的 carriedAll 分支，以及 story-build.mjs 的 guidanceInputs。

currentScope 在本轮已选择整体承载时，即使 positioning.scope_text 为空，也返回非空 scope 且没有范围问题。guidanceInputs 只判断 scope 对象存在，guidanceRows 再用“契约里的范围文字是空的”代替真实范围。因此 skeleton 的写前预检没有实现 v3 对缺范围的承诺。

隔离复现：使用现有 WritingWorkspace 最小合法夹具，仅将末轮 positioning.scope_text 改为空串；调用隔离副本的 skeleton。结果 exit0，Story 和草稿均生成，指导区包含上述空范围提示。原 flowProblems 其它位置可能在后续阶段发现定位问题，但那时作者输入已经生成，不能代替写前检查。

修法：在共用 currentScope 中核当前有效范围文本非空，向两个消费者返回同一问题；不要在渲染器补业务默认范围，也不在 guidanceInputs 再抄一份规则。补整体承载缺字段、空串和纯空白的写前拒绝用例，核现有文件及文件集合不变。

### R2 [P2] 整稿方法缺失仍会在本章已写入后返回 exit1

位置：`doc/extensions/skills/story/scripts/core/story-build.mjs:2844`，wholePassOutput 对 methodBlock 的异常调用 fail；prepareAfterWrite 无法捕获进程退出。

reviews/19 R3 返修覆盖了下一章草稿缺失和指导区错误，但没有覆盖进入整稿的分支。整稿方法标记缺失/损坏时，wholePassOutput 直接退出，绕过“已提交、后继准备失败”的处理。

隔离复现：先形成十章合法稿，仅在隔离 Extension 副本删除 whole 起始标记，再提交一章合法修订。结果 Story 已包含新正文、stdout 已报告“已落盘”，但 exit1，stderr 报整稿方法标记缺失。该失败正是已承诺的后继失败语义，不能靠作者看到两种信号后自行猜测。

修法：wholePassOutput 让 GuidanceError 回到调用方，按 prepare 与已写入后继的现有边界分别处理；同时核后继文件读写异常是否还有绕过统一出口的路径，不扩展为事务系统。验证：直接 prepare 失败为1；本章已写入后的同一错误为0，并明确下一步修方法后重试 prepare，正文不回滚。

### R3 [P2] 指导区给出的命令在含空格的工程目录中不可执行

位置：`doc/extensions/skills/story/scripts/core/story-build.mjs:2709` 及共用输出位置。

guidanceRows 直接拼接绝对 --from 路径；showPath 只替换目录分隔符，不做参数引用。把路径打印出来并不等于提供了可直接执行的命令。

隔离复现：把夹具工作区置于 `work with spaces`，用隔离 Extension 生成背景章指导区，填入合法正文，然后在 PowerShell 原样执行其中的 node chapter 命令。结果 exit1，报“读不到 .../work”，因为 --from 在空格处被截断。

修法：在现有命令展示处按所支持宿主的引用方式正确处理脚本路径、feature、章名与草稿路径，提交子进程继续使用参数数组；复用一个小的命令参数展示职责，不另建执行器。验收要执行真实生成命令，不能只断言输出包含引号；至少覆盖含空格工程目录，并核恢复输出的相同问题。

## 3. 已成立的部分与上一轮评审边界

- 独立任务文件、九类摘要、新提交参数没有进入生产实现；草稿指导区接替了旧头部，chapterSection 与 copyedit 强制链已退出。
- 指导区按 Buffer 切片保护作者区，提交先剥外层；局部检查和全篇检查共用 chapterProblems，方向符合 v3。
- 整稿三个动作正常路径与恢复路径共用输出；reviews/19 R4 已改为先 prepare 目标章，后修改提交。
- readerReviewTask 送达完整 Story，reviewVerdict 区分报告格式与实际结论。其效果不能仅凭内联全文推定模型已读完或正确判断。
- 关于“未登记审查员时记提示放行”：执行反馈 §5b、reviews/19 和最新文档记录了用户选择保持现状；本次按该记录审查，不把旧方案的严格政策重新列成缺陷。格式合格的实际 FAIL 仍不得放行。
- framework 在本次提交范围无改动。

## 4. 规模、正向替换和过拟合

当前分类实测：scripts_mjs 2826、scripts_py 1565、hooks_mjs 3016、prompts_md 1787、data 752，合计9946。相对9537净增409，在已记录签定的9950内。预算合规不等于实现已精简。

另按同一 Git 版本比较口径计算可 UTF-8 解码的交付文件字符：排除 knowledge、story-adaptation 目录和 adapt-scan.mjs，保留其余提示、注释、合同与脚本，6ca48c41 为494580，当前515208，净增20628。该口径独立于预算行数，不混用其它历史报告数字。

新增主体能够对应指导区定位、输入准备、局部提交与失败处理，未发现重新引入任务版本系统或面向已知案例的业务分支。但减少重复输出的目标仍没有转化为静态净减；“估少了保护代码”解释了偏差，不能单独证明所有新增都最简。当前应先以局部修正闭合 R1–R3，真实运行再核这些成本是否换来质量与效率收益，不为压回估算删必要检查。

过拟合审视覆盖改动脚本、注释、作者方法和生成指导区：未发现新增具体案例单号、金额、API 或业务默认值作为命中条件。已知夹具通过只能说明结构连接；此次三个复现也说明现有测试覆盖仍有边界。指导区体量的既有报告基于最小夹具，不能当成真实需求长篇关联正文的成本结论。

## 5. 本次验证与交接

相关回归实际运行：test_writing_flow.py、test_verifier_report_protocol.py、test_author_context_entry.py，结果98 passed、79 subtests passed，35.63秒。不是重新运行全量796项；上一轮全量结果属于 reviews/19 的证据。

失效形态检查亦亲自运行：70项中 FAIL 0、PASS 59、委派11，未指定新 feature，未评价历史产物；M02 的机械检查通过不替代上节语义过拟合审视。

另用现有 WritingWorkspace 在各自临时目录完成 R1–R3 隔离复现，执行实际 Extension 副本和真实 PowerShell 命令，不修改主 feature 或产品代码。三个触发结果已在本次会话输出中记录。

执行者按 R1–R3 修正原责任函数、补有区分力的回归并交回实际结果。通过后可标“实施复核通过，行为待验”；要宣布 Step2.2 优化效果完成，仍需用户启动的真实模型证据。
