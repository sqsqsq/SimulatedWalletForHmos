---
description: 目标模式 goal-runner 薄入口
argument-hint: <feature-name> [requirement]
---

# /goal-mode

**用户输入**：$ARGUMENTS

> **BLOCKER — 用户交互**：任何用户选择必须先调 **AskUserQuestion**（选项文案从
> `framework/skills/reference/confirmation-registry.yaml` 的 `options` 逐字引用）。
> 完整协议：[interaction-renderer](../rules/interaction-renderer.md)。

> **BLOCKER — Personal setup**：跑 harness 前先 `cd framework/harness && npx ts-node scripts/check-personal-setup.ts --json --ensure --project-root <repo-root>`；仅解析 JSON（见 [personal-setup-gate](../../framework/skills/reference/personal-setup-gate.md)）。

按 [goal-mode Skill](../../framework/skills/project/goal-mode/SKILL.md) 执行：**agent 自跑** goal-runner，勿让用户手动执行 harness 命令。

完整 Skill：**[framework/skills/project/goal-mode/SKILL.md](../../framework/skills/project/goal-mode/SKILL.md)**
