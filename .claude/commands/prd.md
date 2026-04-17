---
description: 进入 PRD 撰写阶段（Skill 1）
argument-hint: <feature-name-or-description>
---

# /prd — PRD 撰写

你现在进入 **Skill 1 — PRD 撰写**。

## 必读文档（按顺序完整阅读，不要跳读）

1. [CLAUDE.md](../../CLAUDE.md) — 复核全局约束（术语守门 / Scope 守门 / 架构守门）
2. [skills/1-prd-design/SKILL.md](../../skills/1-prd-design/SKILL.md) — 本阶段完整流程（**Step 1.5 术语消歧**不可跳过）
3. [skills/1-prd-design/templates/prd-template.md](../../skills/1-prd-design/templates/prd-template.md) — PRD 模板
4. [doc/architecture.md](../../doc/architecture.md) — 架构 SSOT
5. [doc/module-catalog.yaml](../../doc/module-catalog.yaml) — **每个模块的职责画像**（含 `NOT_responsible_for` / `easily_confused_with`）
6. [doc/glossary.yaml](../../doc/glossary.yaml) — **业务术语 ↔ 权威模块映射表**

## 用户输入

$ARGUMENTS

## 行动

1. **Step 1.5 术语消歧是 BLOCKER 之首**：
   - 从用户原始需求抽取业务名词 → 查 glossary → 未命中则去 module-catalog 找 Top-3 候选
   - 即便精确命中，若存在 `easily_confused_with`，**必须在映射表里亮出**并把置信度降为 medium
   - 生成「术语映射表」后**停下来，逐条等用户把 `[ ]` 改成 `[x]`**，本项目**不启用 auto-approve**
   - 典型陷阱：用户说「卡中心」，不要想当然映射到 `CardManager`；按 glossary 它应该是 WalletMain 里的 UI 聚合页
2. 严格按 SKILL.md 的 Step 1 ~ Step N 推进，**不要省略任何一步**。
3. **Scope 声明**是第二道 BLOCKER：必须填写 `in_scope_modules` / `out_of_scope_modules` / `rationale`；所有模块名必须存在于 `doc/module-catalog.yaml`；最小改动原则优先。
4. 产物写入 `doc/features/<feature>/PRD.md`。
5. 完成后调用 `harness/scripts/check-prd.ts` 做结构校验；若需语义校验，启动 `verifier` 子 agent 跑 `harness/prompts/verify-prd.md`。
6. 最后产出 `harness/reports/<feature>/<timestamp>/<model>-prd/trace.json`，结构见 [harness/trace/trace.schema.json](../../harness/trace/trace.schema.json)。
7. 用户批准的新术语 / 修正过的映射**必须**回写到 `doc/glossary.yaml`（带 `confidence_hint: "user-approved on YYYY-MM-DD"`）。

## 完成标准

- [ ] **术语映射表所有行 `[x]` 已确认**（`terminology_mapping_table` BLOCKER PASS）
- [ ] PRD.md 通过 `check-prd.ts` 零 BLOCKER
- [ ] Scope 声明完整、模块名对齐 catalog（`scope_matches_catalog` BLOCKER PASS）
- [ ] 新术语已回写到 `doc/glossary.yaml`
- [ ] trace.json 已产出
