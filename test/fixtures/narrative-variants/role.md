# 关于交易凭证的问答

## 用户为什么需要它

“没有网络，或者不想为了生成凭证再上传交易信息时，我也想保存已经完成的交易。”入口在交易详情页，
`COMPLETED` 可以继续，`PENDING` 和 `FAILED` 不能下载。

## 用户能选择什么

格式是 `PDF` 或 `PNG`，`maskCounterparty` 决定是否隐藏对方账号。内容来自
`GET /wallet/transactions/{transactionId}`，客户端端侧渲染，不采用服务端生成。

## 客户端怎样收尾

任务从 `IDLE` 进入 `RENDERING`，成功为 `READY`，失败为 `ERROR`，离开为 `CANCELLED`。后两者删除
`wallet_receipt_temp` 且不显示分享；成功文件在分享结束或离开页面后删除。

诊断只记录 `receipt_render_start`、`receipt_render_success`、`receipt_render_fail`，携带不可逆交易摘要、格式和失败分类；
上报失败不影响下载。不新增远程开关，沿用详情页兼容范围和中英文资源。

| 编号 | 通过条件 |
|---|---|
| `RECEIPT-001` | 完成交易可选 PDF 或 PNG，凭证与详情一致。 |
| `RECEIPT-002` | `maskCounterparty` 生效，不泄露完整账号。 |
| `RECEIPT-003` | 非完成交易无入口，失败或离开不留下文件和分享动作。 |
