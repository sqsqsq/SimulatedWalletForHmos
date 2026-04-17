---
description: 进入代码审查阶段（Skill 4）
argument-hint: <feature-name>
---

# /review — 代码审查

你现在进入 **Skill 4 — 代码审查**。

## 必读文档

1. [CLAUDE.md](../../CLAUDE.md)
2. [skills/4-code-review/SKILL.md](../../skills/4-code-review/SKILL.md)
3. [doc/features/$ARGUMENTS/design.md](../../doc/features) + `contracts.yaml`
4. [doc/architecture.md](../../doc/architecture.md)

## 用户输入

feature = $ARGUMENTS

## 行动

1. 按 SKILL.md 的 checklist 逐条审查（架构合规 / contracts 一致性 / ArkTS 正确性 / Scope 守门 / 资源规范 等）。
2. 审查产物：`doc/features/<feature>/review-report.md`。
3. 运行 `harness/scripts/check-review.ts`；用 `verifier` 子 agent 跑 `harness/prompts/verify-review.md`。
4. 产出 `harness/reports/<feature>/<timestamp>/<model>-review/trace.json`。

## 完成标准

- [ ] review-report.md 覆盖 SKILL 中全部 checklist 项
- [ ] 所有 BLOCKER 级问题已明确标注并给出修复建议
- [ ] trace.json 已产出
