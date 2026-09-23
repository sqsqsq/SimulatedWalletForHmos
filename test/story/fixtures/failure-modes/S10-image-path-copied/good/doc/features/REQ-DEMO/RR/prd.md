# 甲需求 PRD

用户提交申请后要能看到回执，接口 createBusinessOrder 超时阈值 3 秒。

| 状态 | 触发条件 |
|---|---|
| 待提交 | 用户点了提交但未收到回执 |
| 已回执 | 云侧返回 applicationId |

参考图见下：

![入口页面布局](../assets/入口原型说明/image1.png)
