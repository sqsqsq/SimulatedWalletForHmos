# 交易凭证下载简报

用户要在无网络或不愿额外上传交易信息时，从交易详情保存已经完成的交易凭证。只有 `COMPLETED` 交易展示入口，
`PENDING` 和 `FAILED` 不展示。用户选择 `PDF` 或 `PNG`，并通过 `maskCounterparty` 决定是否隐藏对方账号。

客户端调用 `GET /wallet/transactions/{transactionId}` 取得内容真源，在端侧渲染，不采用服务端生成。任务状态为
`IDLE → RENDERING → READY`，失败进入 `ERROR`，离开页面进入 `CANCELLED`。失败和取消都删除
`wallet_receipt_temp`，不显示分享入口；成功文件分享完成或离开后删除。

记录 `receipt_render_start`、`receipt_render_success`、`receipt_render_fail`，只带不可逆交易摘要、格式和失败分类；
上报失败不影响业务结果。不新增远程开关，沿用详情页兼容范围和中英文资源。

- `RECEIPT-001`：完成交易可选择 PDF 或 PNG，凭证与详情一致。
- `RECEIPT-002`：隐藏选项生效，不泄露完整账号。
- `RECEIPT-003`：非完成交易无入口，失败或离开不留下文件和分享动作。
