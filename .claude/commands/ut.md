---
description: 进入业务级 UT 阶段（Skill 5）
argument-hint: <feature-name>
---

# /ut — 业务级 UT / DAG

你现在进入 **Skill 5 — 业务级 UT**。

## 必读文档

1. [CLAUDE.md](../../CLAUDE.md)
2. [skills/5-business-ut/SKILL.md](../../skills/5-business-ut/SKILL.md)
3. [doc/features/$ARGUMENTS/design.md](../../doc/features) + `acceptance.yaml`
4. [doc/业务级UT策划.md](../../doc/业务级UT策划.md)

## 用户输入

feature = $ARGUMENTS

## 行动

1. 按 SKILL.md 从 `acceptance.yaml` 的场景和边界生成业务级 UT / DAG。
2. UT 产物遵循 SKILL.md 规定的目录与命名。
3. 运行 `harness/scripts/check-ut.ts`；用 `verifier` 子 agent 跑 `harness/prompts/verify-ut.md`。
4. 产出 `harness/reports/<feature>/<timestamp>/<model>-ut/trace.json`。

## 完成标准

- [ ] `acceptance.yaml` 的每个场景和边界都有对应 UT 覆盖
- [ ] `check-ut.ts` 零 BLOCKER
- [ ] trace.json 已产出
