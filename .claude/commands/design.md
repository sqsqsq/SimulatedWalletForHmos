---
description: 进入技术设计阶段（Skill 2）
argument-hint: <feature-name>
---

# /design — 技术设计

你现在进入 **Skill 2 — 技术设计**。

## 必读文档（按顺序完整阅读）

1. [CLAUDE.md](../../CLAUDE.md) — 复核全局约束
2. [skills/2-requirement-design/SKILL.md](../../skills/2-requirement-design/SKILL.md) — 本阶段完整流程（注意 **Step 2.5 Scope 继承与提议**）
3. [skills/2-requirement-design/templates/design-template.md](../../skills/2-requirement-design/templates/design-template.md)
4. [doc/architecture.md](../../doc/architecture.md) — 架构 SSOT
5. [doc/features/$ARGUMENTS/PRD.md](../../doc/features) — 对应 PRD，特别注意 PRD 中的 **Scope 声明** 章节

## 用户输入

feature = $ARGUMENTS

## 行动

1. **先完整读 PRD**，提取 `in_scope_modules` / `out_of_scope_modules` / `rationale`。
2. 按 SKILL.md 的 Step 1 ~ Step 2 推进架构分析。
3. **Step 2.5（Scope 守门核心）**：
   - 默认**继承 PRD 的 scope**，填入 design.md 的「Scope 声明与继承」章节，`inherited_from_prd: true`。
   - 若真的需要扩展 scope，**停下来发起扩展提议**（格式见 SKILL.md Step 2.5），等用户明确批准后再写入 `expansions_with_user_approval`。**禁止静默扩展**。
4. Step 3 功能拆分时，涉及的模块必须全部落在冻结后的 `in_scope_modules` 内。
5. 产出 `design.md` + `contracts.yaml` + `acceptance.yaml` 到 `doc/features/<feature>/`。
6. 运行 `harness/scripts/check-design.ts` 做结构与 scope 一致性校验；再用 `verifier` 子 agent 跑 `harness/prompts/verify-design.md`。
7. 产出 `harness/reports/<feature>/<timestamp>/<model>-design/trace.json`。

## 完成标准

- [ ] design.md / contracts.yaml / acceptance.yaml 齐全
- [ ] `check-design.ts` 零 BLOCKER（含 scope_consistency_with_prd）
- [ ] 所有扩展 scope 都有用户明确批准记录
- [ ] trace.json 已产出
