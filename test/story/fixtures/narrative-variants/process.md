# 从交易详情保存凭证

1. 调用 `GET /wallet/transactions/{transactionId}` 读取交易；只有 `COMPLETED` 继续，`PENDING` 和 `FAILED` 结束。
2. 用户选择 `PDF` 或 `PNG`，用 `maskCounterparty` 决定是否隐藏对方账号。
3. 客户端端侧渲染，不采用服务端生成；状态从 `IDLE` 到 `RENDERING`，成功进入 `READY`。
4. 失败进入 `ERROR`，离开进入 `CANCELLED`；两者删除 `wallet_receipt_temp` 且不显示分享。
5. 成功文件在分享完成或离开页面后删除。
6. 记录 `receipt_render_start`、`receipt_render_success`、`receipt_render_fail`，只带不可逆交易摘要、格式和失败分类；上报失败不影响结果。

本功能不新增远程开关，沿用详情页兼容范围和中英文资源。端侧渲染让用户在离线时完成，也避免额外上传交易副本。

`RECEIPT-001` 要求完成交易可选两种格式且内容一致；`RECEIPT-002` 要求隐藏选项生效；
`RECEIPT-003` 要求非完成交易无入口，失败或离开不留下文件和分享动作。
