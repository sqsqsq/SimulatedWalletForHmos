# Skill + Spec + Harness 全链路验证说明

## 本文档在做什么 / 不做什么

| 范围 | 说明 |
|------|------|
| **本文档覆盖** | 在已有产物（catalog、glossary、PRD、design、代码、review、UT、测试计划/报告等）的前提下，**按阶段运行脚本 Harness**：读 Spec 与文档/代码，执行 `check-*.ts`，生成 `framework/harness/reports/...` 与 `ai-prompt.md`。 |
| **本文档不覆盖** | **不是**「一键完成」Skill 0 → PRD → 设计 → 编码 → Review → UT → 真机测试的**开发流水线**。各阶段文档与代码仍需按 `framework/skills/` 中 Skill 人工或借助 AI 编写；Harness 是每步归档后的**质量门禁**。 |
| **AI Harness** | 脚本只生成 `ai-prompt.md`，**不会**自动调用任何大模型；语义审查需自行把 prompt 发给所选模型。 |

## Phase 总览（8 个脚本阶段）

| Phase | 对象 | `--feature` | 说明 |
|-------|------|-------------|------|
| `catalog` | `doc/module-catalog.yaml` | **不需要**（全局） | Skill 0 · Phase A 产物；含模块画像结构、`easily_confused_with`、`key_exports_fresh_vs_index`、`feature_scope_integrity` 等 |
| `glossary` | `doc/glossary.yaml` | **不需要**（全局） | Skill 0 · Phase B 产物；含术语结构、`seed_no_technical_words` 等 |
| `prd` | `doc/features/<feature>/PRD.md` | **必填** | 含 `terminology_mapping_table`、`scope_matches_catalog`、`terminology_modules_within_scope`、`glossary_terms_used_in_body` 等 |
| `design` | `doc/features/<feature>/design.md` | **必填** | Scope 与 PRD 继承一致性等 |
| `coding` | 代码 + contracts | **必填** | `diff_within_scope`、分层 import 等 |
| `review` | review 报告 | **必填** | |
| `ut` | UT 清单与入口 | **必填** | |
| `testing` | 测试计划/报告 | **必填** | |

全局阶段在 `harness-runner` 内使用哨兵 feature `_global`，报告目录形如：`framework/harness/reports/_global/catalog/`。

## 一次性跑全链路（仅脚本检查）

在仓库根目录下，先全局、再按 feature（PowerShell 示例，`home-page` 可替换为你的 feature 名）：

```powershell
Set-Location "framework/harness"

# Skill 0 全局产物（无 --feature）
npx ts-node harness-runner.ts --phase catalog
npx ts-node harness-runner.ts --phase glossary

# 功能需求六阶段（需 --feature）
foreach ($p in @('prd','design','coding','review','ut','testing')) {
  npx ts-node harness-runner.ts --phase $p --feature home-page
}
```

单阶段示例：

- 全局：`npx ts-node harness-runner.ts --phase catalog`
- 功能：`npx ts-node harness-runner.ts --phase prd --feature home-page`

## 各阶段与关键脚本门禁（速查）

更完整的规则定义见 `framework/specs/phase-rules/<phase>-rules.yaml`；实现见 `framework/harness/scripts/check-<phase>.ts`（若存在）。

### catalog（`check-catalog.ts`）

- 结构：schema、`modules[]` 必填字段、layer/format、唯一性等。
- 追溯：`easily_confused_with` 指向存在、无自引用/空 module（BLOCKER）、对称性（MAJOR，可 `unidirectional` 豁免）、`entry_file` 在磁盘、`layer_matches_path`。
- **U2**：`key_exports_fresh_vs_index`（MAJOR/WARN）— HAR 模块 `key_exports` 与 `Index.ets` 顶层 export 漂移时告警。
- **C3**：`feature_scope_integrity`（MAJOR/WARN）— 反向扫描 `doc/features/*/PRD.md` 与 `design.md` 的 Scope YAML，列出引用 **catalog 未建档** 模块的文档（提前暴露后续 `scope_matches_catalog` 会 BLOCKER 的漂移）。

### glossary（`check-glossary.ts`）

- 结构：`terms[]`、字段完整性、term/alias 不重复。
- **P0-2**：`seed_no_technical_words`（BLOCKER）— `glossary-seed.txt` 中 CamelCase 或与模块名重名等；`doc/glossary-seed-allowlist.txt` 可豁免。
- 追溯：`canonical_module` 在 catalog 存在、`owner_layer` 与 catalog 一致等。

### prd（`check-prd.ts`）

- 结构：必需章节、`## 0. 术语映射表` 表格列与用户确认 `[x]`、`Scope 声明` 内 YAML 等。
- `terminology_mapping_table`：权威模块须在 catalog；与 `glossary.yaml` 无冲突。
- `scope_matches_catalog`：`in_scope_modules` / `out_of_scope_modules` 每项须在 catalog 建档。
- **C1a**：`terminology_modules_within_scope`（BLOCKER）— 术语映射表「权威模块」须出现在 **in_scope 或 out_of_scope** 之一，避免「写了消歧却未声明 Scope」。
- **C1b**：`glossary_terms_used_in_body`（MAJOR/WARN）— glossary 术语（含 aliases）在 PRD **正文**（去掉术语映射表段落后）出现但未进映射表时告警。

### design / coding / review / ut / testing

行为与 `framework/specs/phase-rules` 及对应 `check-*.ts` 一致；feature 级规约与文档同目录扁平归档在实例工程根的 `doc/features/<feature>/`（阶段 9 起合并，`framework.config.json` 仅保留单字段 `paths.features_dir`，默认 `doc/features`）。

## 与 Slash / Skill 的对应关系

- 全局阶段对应：`/catalog-bootstrap`、`/glossary-bootstrap`（详见 `framework/skills/0-catalog-bootstrap/SKILL.md`）。
- 功能阶段对应：`/prd-design`、`/requirement-design`、`/coding`、`/code-review`、`/business-ut`、`/device-testing`（详见 `framework/skills/1-prd-design` … `framework/skills/6-device-testing` 及 `CLAUDE.md` 工作流表）。

## 报告输出路径

- 全局：`framework/harness/reports/_global/{catalog|glossary}/`
- 功能：`framework/harness/reports/<feature>/{prd|design|coding|review|ut|testing}/`

每阶段可生成 `merged-report.md`、`ai-prompt.md`；trace 路径约定见 `CLAUDE.md` 与 `framework/harness/trace/trace.schema.json`。

## 历史注记（home-page 打通链路时的工程要点）

以下条目来自早期为 `home-page` 打通链路时的修复，仍对 Windows / 沙盒样本有用：

1. **Markdown CRLF**：`framework/harness/scripts/utils/markdown-parser.ts` 对 `split(/\r?\n/)` 统一处理，避免 Windows 下标题解析失败。
2. **contracts 快照**：`doc/features/home-page/contracts.yaml` 与当前工程对齐（实例路径，不进 framework/）。
3. **测试计划 AC-G 编号**：`check-testing.ts` 中关联 AC 的正则支持 `AC-G1` 等形式。
4. **Hypium 入口**：`check-ut.ts` 跳过仅导出 `testsuite()`、无 `describe` 的入口 shim。
5. **真机测试文档**：`doc/features/home-page/test-plan.md`、`test-report.md` 覆盖 acceptance 中 P0/P1 的 AC 追溯。
6. **Cursor 跳板**：`.cursor/skills/*/SKILL.md` 指向 `framework/skills/` 下正文。

## 累计改造与自检

框架多波改造的历史自检报告已归档至 `doc/archives/wave-1-2-framework-refactor/`。**合并视角**见：[框架改造-沙盒自检报告-累计篇.md](./archives/wave-1-2-framework-refactor/框架改造-沙盒自检报告-累计篇.md)。分卷报告（第一波、第二三波）同目录保留作详细附录。
