---
description: 进入真机测试阶段（Skill 6）
argument-hint: <feature-name>
---

# /devtest — 真机测试计划与报告

你现在进入 **Skill 6 — 真机测试**。

## 必读文档

1. [CLAUDE.md](../../CLAUDE.md)
2. [skills/6-device-testing/SKILL.md](../../skills/6-device-testing/SKILL.md)
3. [doc/features/$ARGUMENTS/design.md](../../doc/features) + `acceptance.yaml`

## 用户输入

feature = $ARGUMENTS

## 行动

1. 按 SKILL.md 生成 `test-plan.md`（用例矩阵 + 环境 + 数据准备）。
2. 执行测试后回填 `test-report.md`。
3. 运行 `harness/scripts/check-testing.ts`；用 `verifier` 子 agent 跑 `harness/prompts/verify-testing.md`。
4. 产出 `harness/reports/<feature>/<timestamp>/<model>-devtest/trace.json`。

## 完成标准

- [ ] test-plan.md / test-report.md 齐全
- [ ] 所有 `acceptance.yaml` 场景真机覆盖
- [ ] `check-testing.ts` 零 BLOCKER
- [ ] trace.json 已产出
