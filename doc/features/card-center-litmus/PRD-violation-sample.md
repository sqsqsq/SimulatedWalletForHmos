# 违规 PRD 样例（路径 B 使用）

> 这是一份**刻意把"卡中心"误映射为 `CardManager`** 的 PRD 样例，
> 用于验证 `check-prd.ts` 的 `terminology_mapping_table` BLOCKER 能正确拦截。
>
> 使用方式：
> 1. 把下文 `PRD.md 完整内容` 临时保存到 `doc/features/card-center-litmus/PRD.md`
> 2. 跑 `npx ts-node harness-runner.ts --phase prd --feature card-center-litmus`
> 3. 验证输出包含 `❌ FAIL [BLOCKER] terminology_mapping_table`
> 4. 验证完毕后删除临时的 PRD.md（本 litmus 不进入生产流程）

---

## PRD.md 完整内容

```markdown
# 卡中心改版 — 产品需求文档（PRD）

> **模块标识**: `card-center-litmus`
> **版本**: v0.1
> **创建日期**: 2026-04-17
> **最后更新**: 2026-04-17
> **状态**: 试金石违规样例（litmus violation）

---

## 0. 术语映射表

| 原始术语 | 权威模块 | 所属层 | 置信度 | 易混项（必读） | 用户确认 |
|---------|---------|--------|--------|---------------|---------|
| 卡中心 | CardManager | 03-CommonBusiness | high | — | [ ] |
| 我的 | WalletMain | 02-Feature | high | — | [ ] |
| 添卡入口 | WalletMain | 02-Feature | high | — | [ ] |
| 账号 | AccountManager | 04-BusinessBase | high | — | [ ] |
| Toast | CommUI | 05-SystemBase | high | — | [ ] |

---

## 1. 功能概述

... 违规样例不再往下写，因为脚本在 Step 0 就会 FAIL ...
```

---

## 预期报告输出（实测已通过）

`terminology_mapping_table` BLOCKER 的三道防线：

1. **路径 B：未人工确认** — 任意一条映射 `[ ]` 都会 FAIL。
   实测报告：
   > `1 条术语映射未获得用户确认（用户确认列不是 [x]）：卡中心`

2. **路径 C：全 [x] 但映射与 glossary 冲突** — 用户漫不经心勾 [x]，脚本交叉对比 `doc/glossary.yaml` 识别冲突。
   实测报告：
   > `1 条用户已确认的映射与 doc/glossary.yaml 冲突：「卡中心」用户确认了 CardManager，但 glossary 权威映射是 WalletMain`
   > 两种合法处理：(1) 按 glossary 修正 PRD 映射；(2) 若确认要覆盖 glossary，先显式修改 glossary 再跑 check

3. **兜底：权威模块不在 catalog** — 模块名拼错或自造，直接 FAIL。

> **结论**：三道防线合力，无论 AI 如何"自信地"误映射，用户漫不经心地勾确认，还是手动改名字拼错，整条链路都会被拦截，核心依赖是 `doc/glossary.yaml` 和 `doc/module-catalog.yaml` 的持续维护。
