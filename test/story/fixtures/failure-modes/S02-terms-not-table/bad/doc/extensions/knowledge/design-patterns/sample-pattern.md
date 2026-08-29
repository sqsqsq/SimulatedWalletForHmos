---
name: sample-pattern
kind: patterns
applies_when: 业务流程有多个分支且各自多步
not_applies_when: 单一线性流程
roles: [节点表, 上下文]
coordinator_role: 节点表
sections:
  select: 上篇 · 适用与选型
  implement: 下篇 · 结构与落地
  verify: 8. 验证清单
---

# 甲模式

## 1. 解决什么问题

分支各自多步时用节点表串起来。
