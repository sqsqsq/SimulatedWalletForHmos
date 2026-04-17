---
description: 进入编码阶段（Skill 3）
argument-hint: <feature-name>
---

# /code — 编码落地

你现在进入 **Skill 3 — 编码**。

## 必读文档（按顺序完整阅读，不要跳读）

1. [CLAUDE.md](../../CLAUDE.md) — 复核全局约束
2. [skills/3-coding/SKILL.md](../../skills/3-coding/SKILL.md) — 本阶段完整流程
3. [skills/3-coding/reference/arkts-pitfalls.md](../../skills/3-coding/reference/arkts-pitfalls.md) — **⚠️ 弱模型必读：15 条 ArkTS 易错点**
4. [skills/3-coding/templates/coding-standards.md](../../skills/3-coding/templates/coding-standards.md)
5. [doc/features/$ARGUMENTS/design.md](../../doc/features) + `contracts.yaml` + `acceptance.yaml`

## 用户输入

feature = $ARGUMENTS

## 行动（强制单文件闭环）

对每个待实现文件严格按以下循环，**禁止批量生成多个文件后再统一验证**：

1. 确认当前文件路径在 design 的 `in_scope_modules` 内；若不在，停下来报告。
2. 写一个文件 → 立即 `ReadLints` → 零 error 才能继续。
3. 对照 `arkts-pitfalls.md` 自校对，命中错例立即修复重跑 lint。
4. 验证 import 未违反四层 / 五层依赖。
5. 展示给用户 → 等待确认 → 进入下一个文件。

## 后置校验

- 运行 `harness/scripts/check-coding.ts`，重点看 `diff_within_scope` BLOCKER。
- 用 `verifier` 子 agent 跑 `harness/prompts/verify-coding.md`。
- 产出 `harness/reports/<feature>/<timestamp>/<model>-code/trace.json`。

## 完成标准

- [ ] 所有 .ets 文件逐个通过 `ReadLints`（零 error）
- [ ] `check-coding.ts` 零 BLOCKER（含 diff_within_scope）
- [ ] 与 `contracts.yaml` 的文件路径 / 接口签名 / 数据模型 / 资源 key 严格一致
- [ ] trace.json 已产出
