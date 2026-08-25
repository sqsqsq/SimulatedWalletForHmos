---
name: constraints-index
kind: index
---

# 规约

各域同一张条目表，列义如下；判定边界见各域的「判定附注 / 落法附注」。

| 列 | 含义 |
|---|---|
| **编号** | `<域前缀>-<两位序号>`，全链受控标识 |
| **约束** | 要求是什么 |
| **强制力** | **红线** = 阻断，命中而未处置即驳回 / 拦截；**基线** = 可不做，但须写明理由与补偿，由评审判断；**建议** = 可不做 |
| **命中条件** | 什么需求涉及本条 |
| **处置** | 须声明什么结论；以 `（评审动作）` 开头的不产生代码要求——不进 spec 约束出口、不建验收条目，只在评审记录留痕 |
| **验证（执行体）** | 怎么确认做到，由谁执行：**模型**（撰写自查 + verifier 复核，可执行条目内的检索式）/ **构建**（编译、CodeLinter）/ **实机**（ut、testing）/ **人工**（评审动作，框架只查留痕） |

## 读条目须知

- `<待补充：…>` 是空缺登记：判定时写「基准待补充，按条目语义定性评估」，不得臆造数值。
- 条目内的检索式（正则、diff 判据、key 比对）是可操作判据，照此执行。
- 判「不命中」也要给依据——「不涉及」三个字不构成结论。
- 需要具体封装（类名、路径、API）时看项目知识，规约不写它们。

## 域清单

| 文件 | 域前缀 | applies_when |
|---|---|---|
| ux-consistency.md | UX | 需求含新页面/UI 改版 |
| security-privacy.md | SEC | always |
| dfx-baseline.md | DFX | always |
| observability.md | OBS | 需求新增业务流程，或改变既有流程的分支/终态 |
| resource-usage.md | RES | 需求涉及界面图片、图标或用户可见文案 |
| compatibility-checklist.md | COMPAT | always |
| env-exceptions.md | ENV | always |
| deliverables.md | DLV | always |
