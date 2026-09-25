# Step2.2 v3 返修复核

> 2026-09-09；核对 17b6521a → 48cfaff1 的生产与测试 diff、执行反馈 §10，并实际运行相关回归及 PowerShell 隔离复现。未修改生产代码，未启动真实 CLI。

## 1. 结论

reviews/20 R1、R2 的具体触发条件已修复；R3 的空格路径问题已修复，但参数引用仍未覆盖当前 PowerShell 的字面量规则。还有一处 P2，修在现有 shellArg 责任点，不需要新运行器或业务特例。行为验收继续待验。

## 2. 已关闭的具体问题

| 前序项 | 本次核对 |
|---|---|
| R1 空范围 | currentScope 的共用 decided 分支拒绝空文本，范围结果为空；guidanceInputs 与 flowProblems 消费同份结果，渲染器的空范围默认文案已删除。空串、纯空白、缺字段的新增用例通过 |
| R2 整稿方法缺失 | wholePassOutput 不再直接 fail，GuidanceError 交回现有调用方；直接 prepare 返回1，已写入后的同一方法缺失返回0且保留正文，新增两例通过 |
| R3 空格路径 | 指导区及相关 NEXT 使用共用 shellArg，原样执行命令的空格路径用例通过。抽取原 helper 接到两个消费者，未复制一套实现 |

这些修复定位在原责任点，没有恢复任务文件、输入摘要或为测试业务增加分支。新增测试覆盖了真实失败结果，而非只检查代码中存在某个函数。

## 3. 尚需修正：R3 的参数引用仍会改变合法路径 [P2]

位置：`doc/extensions/skills/story/scripts/core/story-build.mjs:2735`，共用 shellArg；测试位置 `test/story/tests/test_writing_flow.py:734`。

shellArg 用双引号包装参数，只处理双引号和反斜杠。PowerShell 在双引号内仍展开 `$变量`，所以合法目录中的美元符号不能按原样传入。该 helper 从作者任务包复用过来，不代表它已经适合所有调用宿主。

本次隔离复现：创建名为 `work $story_path` 的工作区，生成指导区，填好合法正文，把其中的提交命令原样交给 `powershell -NoProfile -Command`。--from 为双引号内的 `.../work $story_path/doc/features/...`；实际报错路径变成 `.../work /doc/features/...`，退出1，提交未成功。没有执行额外命令，也没有改主工程产物。

新增测试用 subprocess.run(..., shell=True)，Windows 下使用 cmd，不能证明当前 PowerShell 的参数语义。空格用例正确，但覆盖范围应如实区分。

建议：把命令展示的支持边界写清，并按实际 shell 的字面量规则传参；优先复用已有宿主信息或明确提供相应命令形式，不根据某个业务文件名增加豁免，也不为此建设执行器。至少在实际 PowerShell 中原样执行生成命令，验证含空格、美元符号及所选引用字符的路径准确传递；其它已声明支持的 shell 保留相应验证。参数原样传递才是判据，不是“输出有引号”。

## 4. 验证证据与边界

- 本次亲自运行 test_writing_flow.py、test_author_task_package.py、test_verifier_report_protocol.py：126 passed、52 subtests passed，38.65秒。
- git diff --check 通过；本轮 framework diff 为空。
- 阅读并复核了新增生产注释、参数处理和测试夹具，未发现新增业务专名、案例答案或语义代理判据。
- 执行者报告的全量802项、失效形态与9940预算为其本轮证据，本次未重复全量或重新测量预算，不标为独立重跑。

本轮不重新讨论已批准的预算和未登记审查员政策，不把确定性修复通过当作模型已改善。R3 引用边界补齐后，再确认实施问题关闭；真实成文、统稿与审查效果仍按 v3 行为验收执行。
