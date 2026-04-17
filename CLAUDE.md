# CLAUDE.md — SimulatedWalletForHmos 项目全局指令

> 本文件是 Claude Code CLI 运行在本仓库时的**全局系统指令**。
> 每次对话开始，先读完这里的全局约束，再按当前任务跳到对应 Skill 执行。
> **这里只列清单，不复述细节**——细节以链接的文档为准，避免上下文漂移。

---

## 一、SSOT（Single Source of Truth）

| 维度 | SSOT 文件 | 说明 |
|------|----------|------|
| 架构与模块划分 | [doc/architecture.md](doc/architecture.md) | 五层模块架构 + 模块内四层结构 + 依赖矩阵。**任何与之冲突的设计一律以本文为准**。 |
| 模块画像（Catalog） | [doc/module-catalog.yaml](doc/module-catalog.yaml) | 每个模块的职责 / `NOT_responsible_for` / `easily_confused_with`。**第二波 Scope 防错源头**。 |
| 业务术语表（Glossary） | [doc/glossary.yaml](doc/glossary.yaml) | 自然语言业务名词 ↔ 权威模块映射。PRD 阶段术语消歧必读。 |
| 通用编码规范 | [skills/3-coding/templates/coding-standards.md](skills/3-coding/templates/coding-standards.md) | ArkTS 命名、目录、import、资源等编码规则 |
| ArkTS 易错点 | [skills/3-coding/reference/arkts-pitfalls.md](skills/3-coding/reference/arkts-pitfalls.md) | **弱模型必读**：15 条常见错例 vs 正例 |
| 阶段规则（机器可读） | [specs/phase-rules/](specs/phase-rules/) | prd / design / coding / review / ut / testing 六阶段 YAML 规则 |
| 自动校验脚本 | [harness/scripts/](harness/scripts/) | 对应 check-*.ts，用于 BLOCKER 级门禁 |

---

## 二、核心全局约束（无论在哪个阶段都必须遵守）

### 2.1 架构守门（BLOCKER）

1. **五层依赖方向只能自上而下**：01-Product → 02-Feature → 03-CommonBusiness → 04-BusinessBase → 05-SystemBase。反向依赖一律拒绝。
2. **模块内四层结构**：shared ← data ← domain ← presentation，禁止反向依赖。
3. **跨模块只允许通过模块根 `Index.ets` 导出的符号访问**，禁止 `import ... from '@xxx/src/main/ets/...'` 这种深路径。

### 2.2 术语守门（BLOCKER，第二波新增 — Scope 的真正入口）

> 第一波的 Scope 守门解决了"输出后校验"的问题；但**输入端**（PRD 从自然语言转换成设计语言时）仍可能把"卡中心"误映射为 `CardManager` 这类错误。
> 第二波把术语消歧强制放在 PRD 生成之前，把"隐式理解"变成"显式可审的映射表"。

1. PRD 必须以 **`## 0. 术语映射表`** 章节起始，列出原始术语 → 权威模块的映射（见 [skills/1-prd-design](skills/1-prd-design/SKILL.md) Step 1.5）。
2. **所有映射必须逐条人工确认**（用户把 `[ ]` 改成 `[x]`），不启用 auto-approve。即便置信度 `high` 也必须确认。
3. 每一条映射的 `权威模块` 必须存在于 [doc/module-catalog.yaml](doc/module-catalog.yaml)；否则 `terminology_mapping_table` BLOCKER 阻塞。
4. 术语命中其他模块的 `easily_confused_with` 时，**必须显式亮给用户看**，不允许静默忽略（这是防"卡中心 vs 卡管理"类误映射的核心约束）。
5. 用户批准的新术语 / 修正后的映射必须回写到 [doc/glossary.yaml](doc/glossary.yaml)，作为下一次复用种子。

### 2.3 Scope 守门（BLOCKER，第一波新增）

1. PRD 必须声明 `in_scope_modules` / `out_of_scope_modules` / `rationale`（见 [skills/1-prd-design](skills/1-prd-design/SKILL.md)）。
2. `in_scope_modules` / `out_of_scope_modules` 的每个模块名都**必须在 `doc/module-catalog.yaml` 中存在**（`scope_matches_catalog` BLOCKER），禁止自造模块名。
3. design.md 必须**继承** PRD 的 scope；如需扩展，**停下来**向用户发起「Scope 扩展提议」，获得用户明确批准后写入 `expansions_with_user_approval` 才可继续（见 [skills/2-requirement-design](skills/2-requirement-design/SKILL.md) Step 2.5）。
4. 编码阶段 `git diff` 涉及的所有文件必须落在 design 的 `in_scope_modules` 内（`doc/`、`specs/`、`harness/` 等框架目录除外）。
5. **严禁静默扩展**：任何"顺手改一下"都必须回到 design 阶段走扩展提议流程。

### 2.4 ArkTS 正确性守门（BLOCKER，第一波新增）

1. 写 `.ets` 文件**前**先扫一眼 [arkts-pitfalls.md](skills/3-coding/reference/arkts-pitfalls.md) 相关条目。
2. **逐文件闭环**：写一个文件 → 立刻 `ReadLints` → 零 error 才能写下一个。**严禁批量生成多文件后再统一 lint**。
3. 不允许出现 `any`、硬编码字符串、未定义资源 key、未导出的 Index.ets 符号。

### 2.5 文档与代码同步

- design.md 的 `contracts.yaml`（文件路径 / 接口签名 / 数据模型 / 组件 Props / 资源 key）是编码阶段的强契约，实现必须与之一致。
- 需求交付完成后，如模块边界有变更，必须同步更新 `doc/architecture.md`。

---

## 三、工作流与 Skill 路由

每个阶段都有对应 Skill 文档，Claude Code CLI 通过 `.claude/commands/` 的 slash command 进入。

| 阶段 | Skill | Slash Command |
|------|-------|--------------|
| 1. PRD 撰写 | [skills/1-prd-design/SKILL.md](skills/1-prd-design/SKILL.md) | `/prd` |
| 2. 技术设计 | [skills/2-requirement-design/SKILL.md](skills/2-requirement-design/SKILL.md) | `/design` |
| 3. 编码落地 | [skills/3-coding/SKILL.md](skills/3-coding/SKILL.md) | `/code` |
| 4. 代码审查 | [skills/4-code-review/SKILL.md](skills/4-code-review/SKILL.md) | `/review` |
| 5. 业务级 UT | [skills/5-business-ut/SKILL.md](skills/5-business-ut/SKILL.md) | `/ut` |
| 6. 真机测试 | [skills/6-device-testing/SKILL.md](skills/6-device-testing/SKILL.md) | `/devtest` |

**规则**：
- 进入某阶段前，**必须完整读一遍对应 SKILL.md**，不要只看摘要就开始动手。
- Skill 中引用到的 template / reference / checklist 也是强制阅读（弱模型尤其不要跳读）。
- 每个阶段产物**必须通过对应的 `harness/scripts/check-*.ts`**（结构 + 规则级）以及 `harness/prompts/verify-*.md`（语义级，由 `verifier` 子 agent 执行）。

---

## 四、交付凭证与 Trace（第一波 WP4 约定）

Claude Code CLI 每次完成某个阶段任务，**必须**在以下路径产出一份 `trace.json`：

```
harness/reports/<feature>/<timestamp>/<model>-<phase>/trace.json
```

字段见 [harness/trace/trace.schema.json](harness/trace/trace.schema.json)；痛点回填结构见 [harness/trace/gap-notes.template.md](harness/trace/gap-notes.template.md)。**这是内网弱模型回传问题的唯一渠道**，不要省略。

---

## 五、与用户交互的硬性规则

1. **最小改动原则**：任何不在用户原始诉求内的修改，**先问再做**。
2. **遇到 scope 越界、架构违规、lint 持续失败**：停下来报告，不要"硬着头皮继续"。
3. **不确定 → 用工具验证**：不要凭记忆写 import / 资源 key / 模块路径，用 `Read` / `Grep` 主动查。
4. **产物即契约**：写完 PRD/design 即被后续阶段当作 SSOT 使用，不允许"先写个草稿，后面再改"心态。

---

## 六、快速索引

- 历史需求示例：`doc/features/home-page/`（PRD + design + contracts + acceptance + review/test 报告齐全，可作为样板参考）
- 全链路验证说明：[doc/Harness全链路验证说明.md](doc/Harness全链路验证说明.md)
