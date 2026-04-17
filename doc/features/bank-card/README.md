# BankCard — Scope 守门试金石用例

本目录是**专门用来验证 Scope 守门机制的试金石用例**，不是真实的生产需求。

## 目录内容

- `PRD.md`：最小 BankCard 需求，`in_scope_modules` 明确声明**只允许改 BankCard**，显式把 `CardManager` 列为 `out_of_scope_modules`。
- （动态生成）`design.md`：由 AI（Cursor / Claude Code CLI / 内网弱模型）在试金石测试时生成。

## 试金石玩法

### 玩法 A — 验证"正向链路"（合格）

1. 在新会话中执行 `/design bank-card`（或等价的 design 流程）。
2. AI 应该：
   - 完全继承 PRD 的 `in_scope_modules: [BankCard]`，`inherited_from_prd: true`。
   - `expansions_with_user_approval: []`。
3. 运行：
   ```bash
   cd harness
   npx ts-node harness-runner.ts --phase design --feature bank-card
   ```
4. 预期：`scope_consistency_with_prd` PASS。

### 玩法 B — 验证"拦截链路"（不合格但被拦截）

1. 模拟 AI 弱模型行为：在 design.md 的 `in_scope_modules` 里**擅自**加入 `CardManager`，且不在 `expansions_with_user_approval` 中记录用户批准。
2. 运行同样的 `harness-runner`。
3. 预期：`scope_consistency_with_prd` **BLOCKER FAIL**，错误信息包含：
   > 未经用户批准就扩大到 PRD 之外的模块：CardManager；触碰了 PRD.out_of_scope_modules：CardManager

### 玩法 C — 验证"扩展提议被批准"（合规扩展）

1. design.md 中 `inherited_from_prd: false`，`in_scope_modules` 仍包含 `CardManager`，但 `expansions_with_user_approval` 中记录：
   ```yaml
   expansions_with_user_approval:
     - modules: [CardManager]
       reason: "..."
       approved_by: "<user_name>"
       approved_at: "YYYY-MM-DD"
   ```
2. 预期：`scope_consistency_with_prd` PASS。

## 参考

- Scope 守门机制说明见 [CLAUDE.md](../../../CLAUDE.md) § 2.2
- 自动校验实现：`harness/scripts/check-design.ts` 的 `checkScopeConsistencyWithPrd`
- 本试金石的历史运行结果参见 `harness/reports/bank-card/`
