# Framework 与评测资产问题交接

> 状态：已定界；本轮不修改 Framework

## 一、Framework 缺陷

### 1. Extension 语义检查未被可靠执行

AR90005 的 Spec `ai-prompt.md` 已含以下 Extension 检查：

- `story_content_conservation`；
- `story_human_reading`；
- `split_relationship_complete`；
- `active_knowledge_candidate_boundary`；
- `observability_intent_only`。

但 `framework/harness/prompts/verify-spec.md` 的核心任务仍枚举固定检查项，实际 `verifier.report.md` 没有返回上述 ID。Framework 需要让 verifier 动态执行 merged phase rules，并校验报告覆盖全部适用 ID。

Extension 本轮不复制一份 verifier，也不靠 lifecycle hook 重新实现语义评价。

### 2. 无来源场景下强制量化 NFR

`framework/specs/phase-rules/spec-rules.yaml > nfr_quantified` 与 `check-spec.ts` 要求非功能需求包含数字。AR90005 因而出现明确标注“无上游依据”的 1500 ms、2000 ms。

Framework 应允许“当前无已确认量化指标”这一合法状态，或要求量化项同时具有来源。Extension 不为门禁全绿编造数字。

## 二、Extension 缺陷

- `story-build.mjs` 生成 `story.md#decision-...`，`merge-story.mjs` 又将该仓内路径判为悬空引用；
- `hooks/spec/post_check.mjs` 把这类 Story 归档失败按 MAJOR 返回，导致 Spec harness 仍可给 PASS；
- 开放决定与已定决定使用同一种 Story 当前处置投影。

这些在阶段一直接修复，不归咎于 Framework。

## 三、评测资产缺陷

现有 15 个 Case 主要按单一场景拆分：docx 补料、三种叙述风格、本地单号、交互拆分、预先声明拆分、Review 回流分别起跑。它既重复消耗完整 Story/Spec 链路，也没有验证这些条件共同出现时能否同时守恒。

处理方式：

- 只保留 4 个组合 Case，每个 Case 同时承载多种真实条件；
- 同事实不同标题和组织方式改为离线变形夹具，不占正式 Case；
- 原专项 Case 的唯一能力点和事实并入组合 Case 的 workspace、交互脚本、evidence targets 与 truth；
- `--all` 现在就是这 4 个 feature 唯一的组合 Case，可直接交给已完成的隔离并行 CLI；
- 不执行 CLI，也不修改已完成的并行调度器。

## 四、交接完成条件

本轮报告分别列出 Framework、Extension、评测资产和被测模型责任，不再用 Plan 产物质量代替 Story 主目标。Framework 两项缺陷留待上游修复；修复前的独立人工评审只能作为当轮验证手段，不能宣称 Framework 覆盖已完善。
