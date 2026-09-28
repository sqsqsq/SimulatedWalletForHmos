# 业务级 UT 实践复盘 · 单页版

> 一句话主题：**从"写更多测试"到"让业务真正可测"**——规约驱动 + 双 Harness 门禁。

## 一、痛点

| # | 痛点 | 典型表现 |
|---|---|---|
| P1 | 多机型 / 多场景 / 多入口组合爆炸 | 人工自测覆盖不过来，遗漏率高 |
| P2 | 手写 UT 成本极高 | 一条 5 步业务流 = 数十行 Arrange + 多处 mock |
| P3 | **"声明覆盖"陷阱** | `expect(repo.getList().length > 0)` 就能过，业务流根本没跑通 |
| P4 | **UI 符号入侵 UT** | 为 mock `NavPathStack` / `showToast` 造 Fake 类，SDK 升级就全红 |
| P5 | UT 与需求脱节 | 没人回答得了"AC-3 到底被哪条 UT 覆盖" |

## 二、实践效果（痛点闭环 + 关键证据）

| 痛点 | 解决手段 | 关键交付件 |
|---|---|---|
| P1 | `use-cases.yaml > branches[]` 显式列举，DAG/UT 1:1 映射 | `framework/skills/5-business-ut/examples/card-opening/use-cases.yaml`（6 分支） |
| P2 | 规约驱动 + Spy 模板，AI 从"编"变"填" | `framework/skills/5-business-ut/templates/ut-template.md` |
| P3 | `it_drives_flow` (MAJOR) + `end_to_end_driving` (BLOCKER)：≥2 次 boundary 调用 + ≥2 次 state 断言 | `framework/specs/phase-rules/ut-rules.yaml` · `verify-ut.md` |
| P4 | `ut_import_whitelist` (BLOCKER)，15+ UI 模式一律拦截 | `framework/harness/scripts/check-ut.ts` L30-72 |
| P5 | 三向追溯：`acceptance.yaml` ↔ `use-cases.yaml > branches` ↔ UT `it()` 标签 `[AC-X][BRANCH-id]` | `ut_case_per_unit_ac` / `branch_coverage_full` / `acceptance_coverage` 三条 BLOCKER |

### 量化成果

- **开卡样例**（复杂 feature）：6 分支，UT `unit/both` AC 覆盖率 **100%**，分支覆盖 **100%**
- **home-page**（简单 feature）：轻量路径，34 行 UT 直接测 `HomeRepository`，无架构包袱
- **门禁规模**：脚本 Harness 16 项确定性检查 + AI Harness 8 项语义检查
- **方法论沉淀**：`framework/skills/5-business-ut/` + `framework/specs/phase-rules/ut-rules.yaml` 构成可复用 skill

### 一句话结论

> **业务级 UT 的本质不是写更多测试，而是让业务流程"可被 UT 调用"——成本一半在代码可测性，一半在门禁与追溯。**
