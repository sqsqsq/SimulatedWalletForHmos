# spec 与 plan 阶段的审查闭环

> 读者：跑 spec 或 plan 阶段 harness 的作者。时机：harness 末尾给出 `NEXT:`、审查报告回来之后。

## 闭环

**下一步只看 harness 末尾的 `NEXT:` 行与 summary 的 `next_action`**，不按宿主名分叉：

| `next_action` | 你做什么 |
|---|---|
| `run_verifier_then_receipt`、`rerun_verifier_with_current_request` | 把 summary 的 `verifier_request` 整段交给原生阶段 verifier；它的回复**原样全文**写到 `verifier_report` 指向的文件，再跑 `check-receipt --phase <阶段> --feature <Feature id>` |
| `fill_receipt_then_sync_closure` | 当前审查证据已可复用，不重派：按 NEXT 跑 `check-receipt` 或 `harness-runner.ts --sync-closure` 收口 |
| `fix_verifier_findings_then_rerun_harness` | 按下面的处置表修本职责必修项，再按 NEXT 重跑 harness，取新请求复验 |
| `phase_closed_wait_user` | 本阶段已闭环；按「现在能不能完成」查当前处置，授权覆盖后续阶段时沿原生请求链继续 |

请求与报告的路径都由 summary 给：不要自己拼 subject、不复用上一轮的文件名——
拿错了 `check-receipt` 判 `report_missing`，退回沿用历史 PASS，表面闭环、实际没审。
`check-receipt` 采纳回复并收口，回执与物证由它和原生收口生成，你不写 summary、回执或物证清单；
之后读 summary 核 `verifier_subject_id` 与报告终态块对得上、`readiness_signals` 里没有 `semantic_not_reverified`。
门禁核这份报告：格式不合、判据缺行重复或取值不合的回复不计结论，按 NEXT 重投同一份 request 拿完整回复。
回复只原样落盘，不改结论、不补行；同一审查对象只认第一份合规回复（登记在报告目录的 `verifier.conclusions.json`），之后换了内容的回复被拒，材料改过才有新的请求与对象。回执是 harness 的只读投影，`check-receipt` 自己先生成再校验；
要写备注写 `<阶段>/notes.md`。

阶段原生闭环、本轮工作做完后跑 `python doc/extensions/skills/story/scripts/core/usage.py --project-root . --feature <Feature id> --finalize --phase <阶段>`，返回 ok 才算记进 `doc/usage.json`；只有原生有效闭环才收尾，失败按它报的原因处理后重跑同一条。

**报告回来之后怎么处置，全扩展只有这一张表**：

| 报告结论 | 你做什么 | 闭环方式 |
|---|---|---|
| 有阻断项 | 按阻断项返修，改最早出错的那一处（本阶段产物、验收、契约或上游设计） | 完整 harness → 取新请求再派审 |
| PASS，改动只影响表达（措辞、格式、补说明、补可回查依据） | 改完跑 `harness-runner.ts --revalidate --feature <名>` | summary 记 `completed_with_prior_review` 与 `script_revalidated`；notes 写「按 <对象> 报告的建议修改，未独立重审」 |
| PASS，改动改变业务口径、范围、验收、契约实体 | 改完完整跑 harness | 取新请求再派审 |
| PASS，建议不在本阶段修 | 不改材料 | notes 逐条记建议与去处（下一阶段或评审） |

- 改动属于哪一类由你判断，写进 `<阶段>/notes.md`；门禁核报告里每条 WARN、FAIL 在 notes 里都有指向这份报告的处置记录：同一行写判据编号与报告对象前 8 位（终态块里的 `verifier_subject_id`），旧报告的同号处置不替新报告豁免。
- 审查之后改了知识判断或决策状态，notes 写新依据——只为消掉审查意见而改判断不算处置。
- 门禁反复报同一问题而你判断改不动时，停下向人说明缺什么、需要谁提供，不靠多跑几次过关。
- `/story update` 里的重新闭环与收口按 `phases/update.md`「二、一条线」第 7–9 步。

## 现在能不能完成

summary 的闭环是历史事实，不等于此刻还能完成或发布。说「做完了」「可以交付」之前，查原生的当前处置：

```
node doc/extensions/hooks/shared/framework-access.mjs --project-root . --action disposition --feature <Feature id> --phases <本次负责的阶段，按顺序>
```

| 返回 | 含义与去处 |
|---|---|
| `completion_blocking` 非空 | 本次还不能完成：`repair` 由 `owner` 写的阶段返修，`verify` 补验，`wait` 等原生能力或外部执行；只阻相关的那部分工作 |
| `release_blocking` 非空、`completion_eligible: true` | 可以普通完成，不能说发布通过；交付说明照实披露 |
| `disclosed` | 允许披露的残差，写进交付说明，不改签原质量结论 |

完整 interactive 交付由原生同一完成协调器沿 attended run 的运行身份、范围与完成合同接续；单独的 Spec / Plan 请求只完成本阶段，不为它新建 run、不默认启动 Coding。
