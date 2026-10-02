# spec 与 plan 阶段的审查闭环

> 读者：跑 spec 或 plan 阶段 harness 的作者。时机：harness 末尾给出 `NEXT:`、审查报告回来之后。

## 闭环

**派不派只看 harness 末尾的 `NEXT:` 行**，不按宿主名分叉：它说要派就派一次；说本宿主没有审查员就直接看回执。
请求与报告的路径都由 summary 的 `verifier_request`、`verifier_report` 给：不要自己拼 subject、不复用上一轮的文件名——
拿错了 `check-receipt` 判 `report_missing`，退回沿用历史 PASS，表面闭环、实际没审。
调用只带 request JSON；verifier 的回复由你**原样全文**写到 `summary.verifier_report` 指向的那份文件，
再完整跑一次 harness 采纳它（不用 `--sync-closure`：它对已闭环的阶段不改写）。读 summary 确认
`verifier_subject_id` 与报告终态块对得上、`readiness_signals` 里没有 `semantic_not_reverified`。
门禁核这份报告：格式不合或缺判据的回复每次运行都报、不计结论，重投同一份 request 拿完整回复。
回复只原样落盘，不改结论、不补行；重新派审得到的新回复按同样判据核。回执是 harness 的只读投影，`check-receipt` 自己先生成再校验；
要写备注写 `<阶段>/notes.md`。

**报告回来之后怎么处置，全扩展只有这一张表**：

| 报告结论 | 你做什么 | 闭环方式 |
|---|---|---|
| 有阻断项 | 按阻断项返修，改最早出错的那一处（本阶段产物、验收、契约或上游设计） | 完整 harness → 取新请求再派审 |
| PASS，改动只影响表达（措辞、格式、补说明、补可回查依据） | 改完跑 `harness-runner.ts --revalidate --feature <名>` | summary 记 `completed_with_prior_review` 与 `script_revalidated`；notes 写「按 <对象> 报告的建议修改，未独立重审」 |
| PASS，改动改变业务口径、范围、验收、契约实体 | 改完完整跑 harness | 取新请求再派审 |
| PASS，建议不在本阶段修 | 不改材料 | notes 逐条记建议与去处（下一阶段或评审） |

- 改动属于哪一类由你判断，写进 `<阶段>/notes.md`；门禁核报告里每条 WARN、FAIL 在 notes 里都有处置记录。
- 审查之后改了知识判断或决策状态，notes 写新依据——只为消掉审查意见而改判断不算处置。
- 门禁反复报同一问题而你判断改不动时，停下向人说明缺什么、需要谁提供，不靠多跑几次过关。
- `/story update` 里的重新闭环与收口按 `phases/update.md`「二、一条线」第 7–9 步。
