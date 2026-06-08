# 业务�?UT Skill (`business-ut` · v2.1)

> **用户确认 UX**：[user-confirmation-ux.md](../../reference/user-confirmation-ux.md) · `ut.plan_confirm` / `ut.mock_plan` / `ut.src_mutation` / `ut.dag_confirm` / `ut.ok_to_testing` / `phase.next_step`�?
## 前置（依赖初始化 Skill 产物�?
本工程须先完�?[`framework-init`](../../project/framework-init/SKILL.md)：实例根下已有有效的 `framework.config.json`，且�?skill �?harness 所依赖�?**paths** �?**`architecture` �?*已由初始化写入或与之一致。未完成 `/framework-init` 前请勿执行本 skill�?
**Harness 运行时前�?*：执行本 Skill 中任�?`harness-runner` / `npx ts-node harness-runner.ts` / `check-receipt.ts`（依�?harness npm）前，须满足 [Host harness readiness · Tier_1](../../reference/host-harness-readiness.md) �?[Shell cwd 契约](../../reference/harness-cli-cwd.md)（harness 之后�?`cd framework/harness && npx ts-node scripts/check-receipt.ts`）�?
**Personal setup（BLOCKER�?*：跑 harness 前须 [personal-setup-gate](../../reference/personal-setup-gate.md)：`check-personal-setup.ts --json --ensure`；仅解析 JSON�?
### Feature 归档定位协议（本阶段是消费者）

进入�?Skill 后，必须先基�?`framework.config.json > paths.features_dir` 精确定位 `doc/features/<feature>/`。本步骤只依赖用户给出的 feature 名与文件系统状态，不依�?`.current-phase.json`、历�?reports、trace 或上一阶段缓存�?
**跨会�?Resume Gate（BLOCKER，AGENTS §5.2�?*：若 receipt 可能已存在，�?*�?*自跑 `check-receipt.ts`（或 `harness-runner --sync-closure`）。exit 0 �?�?phase 已闭环，**停等 `phase.next_step`**，禁止仅�?stale state/summary 判未闭环或重跑本阶段�?
- 只有精确目录 `doc/features/<feature>/` 是正�?feature；同�?`<feature>.rar` / `<feature>.zip` / `<feature>.7z` / `<feature>.tar*` 以及 `<feature>-old/`、`<feature>.md` 等同名前缀条目都只是旁证�?- 若精确目录不存在，必须快速失败并提示用户先创�?恢复正式 feature 目录；不得自动解压归档，不得读取归档内容补齐上下文�?- 若目录存在但本阶段输入缺失（至少 `PRD.md`、`design.md`、`contracts.yaml`、`acceptance.yaml`）：报告缺失文件并回到上游阶段补齐；不得把同名归档当作上游产物�?- 继续执行前，向用户展示本阶段输入矩阵：`PRD.md` / `design.md` / `contracts.yaml` / `acceptance.yaml` / `use-cases.yaml(可�?` 存在/缺失，旁证归�?同名前缀条目如实列出但明确忽略�?
## Step 0. 载入 `project_profile` addendum（强制）

继续下文前，完整阅读�?
`framework/profiles/<project_profile.name>/skills/business-ut/profile-addendum.md`

（未声明 `project_profile` 时由 harness 按仓库指纹回落默�?profile；若路径不存在则仅依赖本文与 profile 树下模板/示例。）

> **Agent 行为规约（BLOCKER�?*：完整阅�?[`agent-behavioral-principles.md`](../../reference/agent-behavioral-principles.md)�?*Research Sub-Phase 完成前禁止输�?UT 规划清单�?*

> **动态资产引�?*：正文中�?`` `profile-skill-asset:<skill>/<asset_key>` `` 须按 [Profile skill asset protocol](../../../README.md#profile-skill-asset-protocol) 解析�?
---

## 概述

你是资深**宿主侧业务级 UT** 工程师。UT 运行框架、测试文件扩展名、编译与执行链路以当�?`project_profile` addendum �?`ut.compile` / `ut.run` capabilities 为准；其�?profile（如文档�?generic）可能在 harness 层禁用编�?装机规则，勿把宿主特例硬编码为全局真理�?
你的任务是作�?*既有代码的消费�?*：读懂业务编排源码（�?coding 自选形态…�?
�?Skill 是项目全生命周期流水线的**第五�?*。上游输入来�?requirement-design（`use-cases.yaml`�?*条件�?*）、coding（业务编排源代码 + UI）与 code-review（Code Review），输出（UT + DAG + 可�?`ut/reports/ac-coverage.json`）将流入 device-testing（真机测试；消费 `acceptance.yaml` > `device_focus`）�?
## 触发条件

当用户的请求包含以下意图时激活本 Skill�?- "生成 UT"�?生成单元测试"�?�?UT"�?业务�?UT"
- "端到端测�?�?UseCase 测试"�?分支覆盖 UT"
- "生成 SpyPort / 生成打桩�?
- "存量 UT"�?回归�?�?characterization 测试"�?基于日志生成 UT"�?给现有流程补测试"

### 三路径路由（同触发词「生�?UT」）

| 条件 | 路径 | 细则 |
|------|------|------|
| �?`use-cases.yaml` | path-a | 本文 Step 1~3（UseCase 驱动�?|
| �?use-cases，有 `acceptance.yaml` | path-b | �?AC/BD + DAG |
| 均无且提供脱敏日志切�?| path-c | [`paths/path-c-characterization.md`](paths/path-c-characterization.md) |
| 否则 | �?| 提示先运�?prd-design/2 |

**模块�?seam/mock**：feature �?audit/mock-plan 优先引用 `doc/modules/<module>/ut-registry/`（见 `` `profile-skill-asset:business-ut/module_seam_registry_schema` ``）�?
## 核心理念（v2.1�?
**UT 是既有代码的消费者，不驱动架�?*�?
- 🟢 **复杂 feature（有 `use-cases.yaml`�?*：按 `ui_bindings[].user_actions[].calls` 声明�?*命名函数**直接调用；在 `data_boundaries` 处打桩；断言 state 序列 + 调用序列 + 持久化数据�?- 🟢 **简�?feature（无 `use-cases.yaml`�?*：按 `acceptance.yaml` + `dag.yaml`，直接针�?data 层函�?/ Repository / 导出工具函数�?UT，覆盖数据契约与边界异常即可，不要硬�?UseCase 架构�?- 🔴 **UI 层绝对禁�?UT**：不 import profile addendum 声明�?UI/资源/页面运行时符号；�?harness 对应 BLOCKER 拦截�?- 🔴 **不要为了 UT 反过来改架构**：不要求新建特定目录或接口形态；若代码可测性差（如业务嵌在 inline lambda 中），反�?coding 抽出命名方法，不要在 UT 里实例化 UI 组件�?
### v2 �?v2.1 的关键澄�?
| 维度 | v2 老表�?| v2.1 新表�?|
|------|-----------|-------------|
| 被测单元 | **UseCase �?*（必须在 domain/usecase/�?| **命名业务入口**（Page 方法 / 普�?Flow �?/ 导出函数，由 coding 自选） |
| 外部依赖抽象 | `ports[]`（必须新�?Port 接口�?| `data_boundaries[]`（引�?contracts.yaml 中既�?data 层类�?|
| UseCase 代码 | 强制产物 | **不存�?*；`use-cases.yaml` 只是文档规约 |
| use-cases.yaml | �?`unit/both` AC 就必须产�?| 仅复�?feature（多 UI 共享状�?/ 多步云调�?/ 含回滚分支）产出 |
| Stub 形式 | `SpyXxxPort`（实�?Port 接口�?| `SpyXxx / FakeXxx / StubXxx`�?*子类化既有类**）或 **原型方法替换** |
| DAG use_case | 指向 UseCase class �?| 指向 `use-cases.yaml > use_cases[].id`（无 use-cases.yaml 则可省） |

### 与其他阶段的边界

| 维度 | v1 老做�?| v2.1 做法 |
|------|-----------|-----------|
| 用例粒度 | 一�?`it()` 验一条数据接�?| **一�?`it()` 端到端驱动一�?branch**（或�?use-cases.yaml 时覆盖一�?AC/BD�?|
| 断言粒度 | 仅数�?| state 序列 + data_boundary 调用序列 + 数据 |
| UI 交互 | 部分�?UT 里走 | �?�?device-testing（`acceptance.yaml` > `device_focus`�?|
| AC 过滤 | 全部�?UT 覆盖 | `ut_layer in [unit, both]` �?UT；`device` �?device-testing |

### Harness：`ut.compile` / `ut.run` capability

- **默认命令**由当�?profile provider 实现；中�?Skill 只要求通过 harness 触发，避�?agent 手拼宿主命令�?- **产物路径**、装�?运行方式、日志格式由 profile addendum �?provider 定义�?- **失败归因**：若 `check-ut` 报命令形态不匹配，应优先核对 profile provider 命令形态，**不要**未经对齐就按依赖缺失处理或进�?device-testing�?
## 输入

| 输入�?| 必需 | 说明 |
|--------|------|------|
| **`doc/features/{feature}/use-cases.yaml`** | ⚠️（仅复杂 feature�?| requirement-design 产出（仅当满足复杂度阈值）；含 `coordinator / ui_bindings / data_boundaries / state_model / branches`，business-ut �?*主规划来�?* |
| 业务编排源代�?| �?| coding 产出；代码形态由 coding 自选（Page 命名方法 / `Flow` �?/ 导出函数）。UT �?`ui_bindings.user_actions.calls` �?acceptance.yaml 指向的函数直接调�?|
| data 层源代码 | �?| `data/repository/*.<ext>`、`shared/client/*.<ext>` 等；UT �?profile 允许的边界上打桩 |
| `doc/features/{feature}/contracts.yaml` | �?| 接口契约 Spec，`data_boundaries[].type` 必须来自这里�?`interfaces[].class` |
| `doc/features/{feature}/acceptance.yaml` | �?| 验收标准 Spec，含 `ut_layer`；简�?feature 时是主规划来�?|
| `doc/features/{feature}/ut/testability-audit.md` | �?| Step 1.5 可测性预检（覆盖全�?unit/both AC/BD�?|
| `doc/features/{feature}/ut/mock-plan.yaml` | ⚠️ | Step 1.6 Test Double Plan；存�?L0/L1/L2 可测项时 **必填** |
| `doc/features/{feature}/design/design.md` | �?| 状态机 Mermaid、UseCase 清单章节（若有） |
| `doc/features/{feature}/prd/PRD.md` | �?| 业务流程图和异常场景 |
| `doc/architecture.md` | �?| 模块架构全貌 |
| `review-report.md` | �?| 可选，用于确认代码已通过 Review |

**若缺�?`use-cases.yaml`**：不阻塞�?Skill。按 acceptance.yaml + dag.yaml 直接针对 data �?/ 导出函数�?UT；harness 会以 WARN 提示而非 BLOCKER�?*严禁**为此回过头去要求 requirement-design �?use-cases.yaml 以套入架构（除非确实符合复杂度阈值）�?
**若缺�?`acceptance.yaml`**：提示用户先运行 prd-design�?
## 规约参�?
| 规约 | 路径 |
|------|------|
| UseCase 规范 Schema | `` `profile-skill-asset:business-ut/use_cases_schema` `` |
| DAG Schema（v2�?| `` `profile-skill-asset:business-ut/dag_schema` `` |
| UT 模板 + Spy 模板（子类化既有�?/ 原型替换�?| `` `profile-skill-asset:business-ut/ut_template` `` |
| 打桩策略 | `` `profile-skill-asset:business-ut/mock_strategy` `` |
| 可测性预检模板 | `` `profile-skill-asset:business-ut/testability_audit_template` `` |
| mock-plan Schema | `` `profile-skill-asset:business-ut/mock_plan_schema` `` |
| 规范级样例（中性多步流程） | `` `profile-skill-asset:business-ut/sample_flow_dir` `` |

## UT 可测�?/ mock-plan 策略决议（v2.3�?
以下结论按本仓库计划书落地，作为 business-ut �?**SSOT** 口径�?
1. **存量 feature 迁移**：已在历史版本通过 UT harness �?feature�?*仅当再次进入 business-ut 并变�?UT 相关产物�?* 回补 `ut/testability-audit.md` �?`ut/mock-plan.yaml`�?*�?feature �?v2.3 规则生效起一律强�?*（与 `ut-rules.yaml` �?BLOCKER 一致）�?2. **L3 + option_b 接缝白名�?*：仅允许 **构造注入、包�?wrapper、提取命名方法、setter 注入** 等显式接缝；**禁止**「换一种全局单例」式改造敷�?UT�?3. **可测性预检的独立切�?*：如只想完成 Step 1.5/1.6（产�?`testability-audit.md` / `mock-plan.yaml`）后暂停，请�?`/business-ut`（Cursor �?`business-ut` 跳板）入口中明确告知 agent�?*�?*再提供独�?`/ut-audit` slash 或跳板；完整 UT 闭环仍由 `/business-ut` 收尾�?
## 工作流程（v2.1�?
### Step 1：规�?DAG �?UT（按是否�?`use-cases.yaml` 分两条路径）

#### Lite Mode 判定（Step 1 之前�?
满足**全部**条件时可启用 **UT Lite**（减确认点，**�?*�?DAG�?*�?*降级 harness 规则）：

- `acceptance.yaml` �?`ut_layer �?{unit, both}` �?AC/BD **�?7** �?- `testability-audit.md` 结论**全部�?L0/L1**
- **�?* `use-cases.yaml`

Lite 时：

1. 可选产出辅助文�?`doc/features/{feature}/ut/quick-plan.yaml`（模板：`` `profile-skill-asset:business-ut/quick_plan_template` ``�?2. harness **仍强�?* `testability-audit.md` + `mock-plan.yaml`
3. 允许单个 flat DAG（仅 entry + assertion），**跳过** Mermaid 展示确认（`ut.dag_confirm`�?4. 确认点减�?**2 �?*：`ut.plan_confirm` + `ok_to_testing`（仍保留 mock-plan 写前自检，无单独 `ut.mock_plan` gate�?
#### Step 1.0: Research Sub-Phase（Context Exploration Gate · BLOCKER�?
在输出下�?**「UT 规划清单�?* 之前，必须完成本 Step 并落�?**`doc/features/<feature>/ut/context-exploration.md`**�?*`schema_version: "1.1.0"`**）�?
**上下文摘取（BLOCKER�?*：禁止通读大模块源文件。按 `` `profile-skill-asset:business-ut/context_extraction_protocol` `` 执行 rg 签名摘取；总上下文 **�?300 �?*。`source_code_paths` 只列被测入口�?UT 目标，不列整模块目录�?
1. **必读**：`PRD.md`、`design.md`、`contracts.yaml`、`acceptance.yaml`、`use-cases.yaml`（若有）、被测命名入口源码（`source_code_paths` �?3�?*签名�?*摘取）�?2. **复合评分触发**：填�?frontmatter 变更信号；评�?�?60 �?L4 �?MUST explore �?agent；无 subagent 时用 sequential + 倍率阈值�?3. Code Facts 须覆�?`data_boundaries` 与被�?handler/Flow�?
先读取全部上游输入：

- `doc/features/{feature}/use-cases.yaml`�?*若存�?*�?- `doc/features/{feature}/acceptance.yaml`（只关注 `ut_layer in [unit, both]` �?AC/BD�?- `doc/features/{feature}/prd/PRD.md` / `design/design.md`
- `doc/features/{feature}/contracts.yaml`（data_boundary type 必须�?`interfaces[].class` 中）
- 业务编排源代码（coding 自选了 Page 方法 / `Flow` �?/ 导出函数�?
> **HARD STOP �?规划确认�?*（`ut.plan_confirm` · user-confirmation-ux §3.1）：Step 1 结束后必须先向用户展示「UT 规划清单」�?*gate**：`1=确认清单` / `2=调整清单`。禁止直接进�?Step 2/3 �?DAG �?UT。清单必须包含：
> - 本轮覆盖�?`AC/BD/branch`，以及不覆盖项和原因（如 `device` �?device-testing）；
> - 每个 `it()` 的名称、被测入口、Spy/Stub 边界、核心断言（状�?/ 返回�?/ callLog / 持久化）�?> - 将要新增或修改的 DAG / **profile 规定的测试源文件** / 套件注册入口路径�?> - 明确声明「本轮不改业务源码」。若确需�?`src/main`，必须先走文末约�?#12 的单独授权流程，不能把它混在规划确认里�?>
> 用户未确认前，agent 只能继续补充说明或调整规划，不得写文件�?
#### 路径 A：存�?`use-cases.yaml` —�?�?branches × ui_bindings 规划

为每�?use_case 列一�?**Branch × DAG × UT × AC 清单**�?
```markdown
📋 UT 规划清单（use_case: `task_handoff`，coordinator: `HandoffCoordinator`�?
ui_bindings 入口（来�?use-cases.yaml�?
- TaskComposerPage.role=entry, user_actions[].calls = "coord.submitDraft"
- ConfirmDialog.role=dialog, user_actions[].calls = "coord.confirm"

| # | branch id       | DAG 文件                           | it() 用例                              | linked_acceptance |
|---|-----------------|-------------------------------------|----------------------------------------|-------------------|
| 1 | happy_path      | task_handoff_happy.dag.yaml         | [BRANCH-happy_path][AC-1] 成功          | AC-1              |
| 2 | enqueue_fail    | task_handoff_enqueue_fail.dag.yaml  | [BRANCH-enqueue_fail][AC-2] 远端拒绝    | AC-2              |

unit/both AC 覆盖�? 100%
device-only AC: （在 acceptance.yaml 填写 device_focus�?```

#### 路径 B：无 `use-cases.yaml` —�?�?acceptance.yaml 直接规划

�?`ut_layer �?{unit, both}` �?AC/BD 逐条列清单，指向具体�?**被测 data 层函�?* �?**导出业务函数**�?
```markdown
📋 UT 规划清单（feature: demo-dashboard，无 use-cases.yaml�?
| # | AC/BD id | 被测单元                         | DAG 文件             | it() 用例                     |
|---|----------|----------------------------------|----------------------|-------------------------------|
| 1 | AC-1     | DashboardRepository.fetchWidgets | dashboard_ut.dag.yaml | [AC-1] 列表契约完整 |
| 2 | AC-2     | DashboardRepository.fetchSummary | dashboard_ut.dag.yaml | [AC-2] 摘要契约完整 |
| 3 | BD-1     | DashboardRepository.fetchSummary(empty) | dashboard_ut.dag.yaml | [AC-2][BD-1] 空列表回�?|
```

**等待用户确认清单后进�?Step 1.5（可测性预检）；不得跳过 Step 1.5/1.6 直接进入 Step 2�?*

#### Step 1 输出格式（必须使用）

```markdown
## UT 规划清单（等待确认）

覆盖范围�?- unit/both：AC-1、AC-2、BD-1
- device-only：AC-3（acceptance.device_focus，不�?UT�?
用例矩阵�?| it() | AC/BD/branch | 被测入口 | Spy/Stub 边界 | 核心断言 |
|------|--------------|----------|---------------|----------|
| [AC-1] xxx | AC-1 | Flow.submitDraft | SpyTaskRemoteApi | phase=Success；callLog=[enqueue,finalize] |

将写入文件：
- `<layer>/<Module>/test/dag/xxx.dag.yaml`
- `<layer>/<Module>/src/<profile-test-root>/...`（目录名�?addendum 为准�?
业务源码�?- 不修�?`src/main`�?```

### Step 1.5：可测性预检（testability-audit.md）【HARD STOP�?
#### 写入前自检（必须逐条核对后再写文件）

- [ ] 已读 `` `profile-skill-asset:business-ut/format_contract` ``
- [ ] `testability-audit.md`：内容是 fenced ` ```yaml ... ``` ` 块或�?YAML�?*不是** Markdown 表格�?- [ ] `acceptance_id` 严格来自 `acceptance.yaml` 已有 ID（无子编号如 `-a`/`-b`�?- [ ] 写完后运行（`<path>` 用相对工程根路径，如 `doc/features/{feature}/ut/testability-audit.md`）：
  `cd framework/harness && npm run validate:ut-artifact -- --type testability-audit --file doc/features/{feature}/ut/testability-audit.md`

在生�?DAG / mock-plan / **profile 定义的单测源文件**之前，必须为 **acceptance.yaml 内每�?`ut_layer �?{unit, both}` �?AC/BD** 写一条可测性结论，归档�?
`doc/features/{feature}/ut/testability-audit.md`

1. **按模板撰�?*：`` `profile-skill-asset:business-ut/testability_audit_template` ``（L0–L3 定义、依�?kind/seam、YAML 形态）�?2. **对每�?unit/both 项给�?*�?   - `testability_level`（L0/L1/L2/L3�?   - 关键 `dependencies`（含 `global_singleton` / `inline_lambda` 等，以便 harness 与人工审阅）
   - `verdict`：`testable` | `downgrade_device` | `needs_seam`
3. **若为 L3（不可测或只能高成本测）**�?*必须 STOP**，向用户展示 `recommendation.option_a`（降�?device-only）与 `option_b`（源码改�?+ gap-notes 授权），迫使用户选择并在文档中填�?`selected: option_a | option_b`�?   - **option_a**：在 `acceptance.yaml` 对应条目填写 `device_focus`（真机要点；harness 校验非空�?   - **option_b**�?*不得**�?gap-notes 登记前改 `src/main`；登�?`approved_src_mutations[]` 后按约束 #12 执行接缝改造（仅此路径可解�?L3 �?UT 层的硬阻塞）

> 用户未对 **全部 L3 �?* 做完 a/b 选择前，禁止进入 Step 1.6 / Step 2 / Step 3�?
### Step 1.6：Test Double Plan（mock-plan.yaml）【HARD STOP�?
#### 写入前自检

- [ ] 已读 `` `profile-skill-asset:business-ut/format_contract` ``
- [ ] `mock-plan.yaml`：纯 YAML（无 Markdown 标题 / 围栏�?- [ ] `ts_expr` 包含 `as TypeName` �?`new ClassName(`
- [ ] 写完后运行（`<path>` 用相对工程根路径，如 `doc/features/{feature}/ut/mock-plan.yaml`）：
  `cd framework/harness && npm run validate:ut-artifact -- --type mock-plan --file doc/features/{feature}/ut/mock-plan.yaml`

�?Step 2 之前产出类型骨架，路径：

`doc/features/{feature}/ut/mock-plan.yaml`

1. **规格**：`` `profile-skill-asset:business-ut/mock_plan_schema` ``（imports、`spies[]` �?`doubles[]`、每�?`strategy: spy | mockkit | fake | prototype_patch`、methods、presets；`ts_expr` **必须**�?`as Type` �?`new ...(`）�?2. **权威对齐**：`target_class` / `methods[].name` 必须可在 `contracts.yaml > interfaces[]` 中找到；**禁止**�?Spy/MockKit 实现里脱�?plan 自由发挥字段或方法签名�?3. **策略选型**：可注入 + 要调用序追溯 �?**Spy**；难注入外部边界 �?**mockkit**（须 `@ohos/hypium` �?`MockKit`/`when` �?plan preset 对齐）；轻量替身 �?**fake**�?4. **�?Step 3 的关�?*：Spy/Fake **1:1 翻译** mock-plan；MockKit 路线�?UT 中用 `when(...)` 落实 plan �?`presets[].id`，避免在 `it()` 内手写无类型字面量�?4. **用户确认**（`ut.mock_plan`：`1=确认 mock-plan` / `2=调整`）：展示计划中的 spy 边界�?preset 列表，明确本轮是否仅文档�?mock-plan（不改业务源码）；若需 option_b 接缝，仍走约�?#12�?
> �?L0/L1/L2 可测项（例如全部�?L3 且�?option_a）时，mock-plan �?harness `ut_mock_plan_present` SKIP�?*一旦出现可测等级为 L0/L1/L2 �?AC/BD，mock-plan 强制**�?
### Step 2：生�?DAG 文件（flow DAG · 默认 ephemeral�?
对每�?branch 生成一�?DAG（或合并成同一�?use_case 的多分支 DAG，只�?branches[] 交集为空、并集覆盖即可）�?
**默认写入 ephemeral 位置**（不归档进模�?`test/dag/`，除非用户明确要求归档，或触�?Code Graph `core` 节点——见 `code-graph-core-closure-gate`）：

- `doc/features/{feature}/ut/reports/flow-dag/{flow_id}.dag.yaml`

**显式归档**（可选）才写入：

- `{module}/test/dag/{flow_id}.dag.yaml`

完成 UT 阶段前，当存�?**ut_layer �?{unit, both} �?priority �?{P0, P1}** �?AC/BD 时，须由 business-ut 产出机器可读 **`doc/features/{feature}/ut/reports/coverage-evidence.json`**，且 **`mappings[]` 须覆盖每条上�?P0/P1 scope**（见 `` `profile-skill-asset:business-ut/coverage_evidence_schema` ``）。harness 只校验、不自�?mapping�?
1. **必填顶层字段**（由 harness `dag_schema_compliance` BLOCKER 强制）：
   - `flow_id` / `flow_name` / `module` / `version`
   - `entry_point` / `nodes`
   - **�?`use-cases.yaml` 存在**：另需 `use_case`�? `use-cases.yaml > use_cases[].id`�? `branches[]`�? �?DAG 覆盖的分�?id 列表�?   - `linked_acceptance`
2. **节点构建**�?   - `user_trigger`：对应业务入口命名函数调用（ui_bindings.user_actions.calls�?   - `port_call_cloud` / `port_call_local`：对应调用的 data_boundary（节点字�?`boundary` = `data_boundaries[].name`；旧字段 `port` 兼容）；**推荐**在此类节点与 `async_call` 上声�?`spy_preset`（引�?`mock-plan.yaml` �?`presets[].id`）。旧字段 `mock_data` **仍可读但�?deprecated**（过渡期�?`spy_preset` 共存）�?   - `state_transition`：对�?`state_model.phases` 迁移
   - `assertion`：必须声�?`linked_branch` �?`linked_acceptance`（两者之一�?   - `ui_subscription`（v2.1 新）�?*仅用于文档化 UI �?state 的订�?*，UT 忽略；真机要点写�?acceptance `device_focus`
3. **UI 副作用不�?UT 断言**：`NavPathStack.push` / `showToast` 只能作为 `ui_subscription` 节点记录，或�?prd-design �?`acceptance.yaml` > `device_focus` 中声明，不要画成 `port_call_*` �?`assertion` 节点
4. **验证 DAG**：无环、source 存在、`boundary` 名回�?`use-cases.yaml > data_boundaries[].name`（若存在 use-cases.yaml�?5. **展示 Mermaid** 给用户确认（`ut.dag_confirm`：`1=确认DAG` / `2=修改DAG`；按节点类型着色）
6. **写入** 默认 `doc/features/{feature}/ut/reports/flow-dag/{flow_id}.dag.yaml`（仅用户要求归档或触�?core 节点时写 `{module}/test/dag/`�?
### Step 3.0 写入路径 Gate（BLOCKER�?
继续 Step 3 写文件前�?
- `<repo-root>` = �?`framework.config.json` 的实例工程根�?*不是** `framework/harness`�?- UT / Spy / DAG 路径 = `{repo-root}/{contracts.modules[].package_path}/...`（测试源树见 profile addendum，如 `src/ohosTest/ets/test/`�?- 若上一�?shell �?`cd framework/harness && ...`，Write �?**必须** `cd <repo-root>` 或使用绝对路径（�?[harness-cli-cwd.md §2.5](../../reference/harness-cli-cwd.md)�?- **禁止** Write �?`framework/harness/` 下宿主源码（profile 规定的测试源树、`test/dag/`、`{package_path}/` 整树）；harness 内仅允许 reports/state 等运行产�?
### Step 3：生�?UT 代码（按 branch �?AC 生成 `it()`�?
#### 写入前自检

- [ ] `it()` 名称�?`[AC-]` �?`[BRANCH-]` **开�?*；BD �?**`[AC-x][BD-y]` 组合**（禁止单�?`[BD-1]` �?`[BD-1-a]`�?- [ ] audit / mock-plan 已通过 `validate:ut-artifact` CLI

**mock-plan 优先**：若已产�?`ut/mock-plan.yaml`，Spy 类与 preset 行为必须与其一致；DAG 节点上的 `spy_preset` 仅做追溯，UT 内切换预设时仍以 plan 为真源�?
#### 3.1 UT 骨架（路�?A：有 use-cases.yaml�?
按照 `` `profile-skill-asset:business-ut/ut_template` `` 提供的骨架生成�?*直接调用 `ui_bindings.user_actions.calls` 声明的命名函�?*�?*�?new `@Component struct`**�?
```typescript
import { describe, it, expect, beforeEach } from '@ohos/hypium'
import { HandoffCoordinator, Phase } from '../../../main/ets/domain/flow/HandoffCoordinator'
import { SpyTaskRemoteApi } from './spy/SpyTaskRemoteApi'
import { SpyTaskLocalStore } from './spy/SpyTaskLocalStore'

export default function taskHandoffFlowTest() {
  describe('HandoffCoordinator', () => {
    let api: SpyTaskRemoteApi
    let store: SpyTaskLocalStore
    let coord: HandoffCoordinator

    beforeEach((): void => {
      api = new SpyTaskRemoteApi()
      store = new SpyTaskLocalStore()
      coord = new HandoffCoordinator(api, store)
    })

    it('[BRANCH-happy_path][AC-1] 提交流程成功', 0, async () => {
      api.whenEnqueue.returns({ ok: true, jobId: 'j1' })
      api.whenAck.returns({ ok: true })
      await coord.submitDraft({ title: 'demo' })
      expect(coord.state.phase).assertEqual(Phase.Pending)
      await coord.confirm({ token: 't1' })
      expect(coord.state.phase).assertEqual(Phase.Success)
      expect(api.callLog).assertDeepEquals(['enqueue', 'ack'])
      expect(store.callLog).assertDeepEquals(['savePending', 'finalize'])
    })
  })
}
```

#### 3.1B UT 骨架（路�?B：无 use-cases.yaml�?
简�?feature 直接针对 data 层或导出函数�?UT�?
```typescript
import { describe, it, expect, beforeEach } from '@ohos/hypium'
import { DashboardRepository } from '../../../main/ets/data/repository/DashboardRepository'

export default function dashboardRepoTest() {
  describe('demo-dashboard', () => {
    let repo: DashboardRepository
    beforeEach((): void => { repo = new DashboardRepository() })

    it('[AC-1] DashboardRepository 契约完整', 0, async () => {
      const widgets = await repo.fetchWidgets()
      expect(widgets).not.assertNull()
      expect(widgets.length).assertLarger(0)
      expect(widgets[0].id).not.assertUndefined()
    })
  })
}
```

#### 3.2 打桩代码（v2.1 · 不再强制 Port 接口�?
v2.1 的打桩针�?**`use-cases.yaml > data_boundaries[].type` 所指的既有 data 层类**，有三种合法形式（任选其一）：

- **形式 1：子类化** �?`class SpyTaskRemoteApi extends TaskRemoteApi { ... }`，override 实际方法；暴�?`callLog: string[]` 和每个方法一�?`whenXxx.{returns, fails, throws}` preset
- **形式 2：原型方法替�?* �?`TaskRemoteApi.prototype.enqueue = (...)`（`afterEach` 必须恢复�?- **形式 3：若 data 层已�?DI 注入的接�?抽象�?* �?直接提供该接口的 Spy 实现

**统一约束**�?- **禁止**为打桩方便额外创�?`XxxPort` 接口
- **禁止**�?Spy 内部写业务判断（业务判断必须留在 coordinator / 命名业务函数里）
- 若采用形�?2，`afterEach` 必须恢复原型，避免跨用例污染

参考模板见 `` `profile-skill-asset:business-ut/ut_template` `` 的打桩章节�?
#### 3.3 每个 `it()` 的必备断言

v2.1 约束（`it_drives_flow` MAJOR 检查）�?
**路径 A（有 use-cases.yaml�?*�?1. **命名入口驱动**（调�?`ui_bindings.user_actions.calls` 声明的函数）
2. **调用序列断言**（`assertDeepEquals(spy.callLog, [...])` 至少 1 次）
3. **状态多阶段断言**（对 `phase` / `errorCode` 等字�?�? �?expect，覆盖中间态与终态）

**路径 B（无 use-cases.yaml�?*�?- 每个 `it()` 至少 2 �?`expect`，覆盖数据契约字段与边界情形

#### 3.4 用例命名（强约束�?
`it()` 必须�?`[BRANCH-<id>]` �?`[AC-<id>]` **开�?*（两者可组合，如 `[BRANCH-happy_path][AC-1]`）�?
**Boundary（BD）标�?*：harness 正则只认 `[AC-]` / `[BRANCH-]` 开头；BD 必须作为**组合标签**�?
| �?合法 | �?非法 |
|---------|---------|
| `[AC-1][BD-1] getData 空列表回落` | `[BD-1] ...`（正则不�?BD 开头） |
| `[BRANCH-main][AC-2][BD-1] ...` | `[BD-1-a] ...`（子 ID 不存在） |
| `[AC-2] �?AC` | 无标签开�?|

#### 3.5 import 白名单（BLOCKER · `ut_import_whitelist`�?
**允许�?import 类别**（细则与**测试框架包名**�?profile addendum）：测试框架、被测命名业务入口、data 层与被允�?Spy/Fake、同目录替身�?
**禁止的符号清�?*�?**profile** 实现（`harness/ut-ui-import-ban.ts` + addendum），脚本仅在�?phase-rules 声明一致时启用�?
#### 3.6 生成流程

1. 为每�?data_boundary（或路径 B 的直接依赖）�?**profile 规定的测试源码树** 下生�?`spy/`（或等价目录）替身（已存在则复用�?2. 为每�?use_case（路�?A）或每组 AC（路�?B）生成一�?**profile 规定的测试文�?*（扩展名与命名模式见 addendum，如 `*.test.<ext>`），每个 branch / AC 一�?`it()`
3. 展示给用户确�?4. 写入文件

### Step 4：测试注册与配置

1. 确保 **测试套件注册入口**（由 profile 约定文件名，�?`<suite_registry>.<ext>`）登记了所有新增用�?2. 确认测试框架依赖�?**profile 声明的测试模块包描述** 中声明（常见为宿主侧的包清单文件�?3. 若模块尚无测试源码目录，�?**profile 标准目录** 创建（路径见 addendum，如 `<module>/<profile-test-root>/...`�?
```
{module}/src/<profile-test-root>/
├── ...
�?  └── <suite_registry>.<ext>        # 测试入口聚合
�?  └── <feature>.test.<ext>          # 分文件用�?�?  └── spy/                          # Spy / Fake
└── module.json5（若需要）
```

### Step 5：质量门禁自检（v2.1�?
```
[ ] 1.  use-cases.yaml（若存在）通过 schema 校验：含 coordinator / ui_bindings / data_boundaries / state_model / branches
[ ] 2.  named_business_handler（若�?use-cases.yaml）：ui_bindings[].user_actions[].calls 每个符号在代码中都能找到**命名符号**——传统函�?/ 类方�?/ 类字段函数（`handler = () => {}`�? 顶层命名 const 赋�?均合�?[ ] 3.  boundary_matches_contracts（若�?use-cases.yaml）：data_boundaries[].type 都能�?contracts.yaml > interfaces[].class 中找�?[ ] 4.  DAG 合规：顶层含 flow_id / flow_name / entry_point / nodes；若�?use-cases.yaml 则另�?use_case�? id）和 branches[]
[ ] 5.  DAG 分工：同 use_case 所�?DAG �?branches[] 交集为空、并集覆盖所有非 device_only 分支
[ ] 6.  ut_import_whitelist（BLOCKER）：UT �?import profile 禁止清单中的 UI / 资源运行时符号（完整表见 addendum + `ut-ui-import-ban`�?[ ] 7.  boundaries_all_stubbed：每�?data_boundary 都有 Spy/Fake/Stub 子类化或原型替换的证�?[ ] 8.  it() 命名：每�?it() �?[AC-X] �?[BRANCH-X] 起始；BD �?[AC-x][BD-y] 组合，禁止单�?[BD-] 开�?[ ] 9.  it() 驱动力：
         - 路径 A：每�?it() 调用命名入口 + �? �?callLog 断言 + �? �?state/phase 断言
         - 路径 B：每�?it() �? �?expect，覆盖数据契�?[ ] 10. AC 覆盖（单元层）：ut_layer in [unit, both] �?P0/P1 �?AC 100% 对应 it()
[ ] 11. 分支覆盖（若�?use-cases.yaml）：每个�?device_only 分支都有对应 it()
[ ] 12. device �?AC：prd-design �?acceptance.yaml 已为 ut_layer∈{device,both} 填写 device_focus；DAG �?ui_subscription 要点�?device_focus 一�?[ ] 13. 测试注册：所�?UT 文件�?**profile 声明的套件入�?* 中注�?[ ] 14. 用例独立性：beforeEach 重建替身；若用原型替换方案，afterEach 还原
```

**不通过�?*：定位具体问题，自动修复后重新检查，直到全部通过�?
### Step 6：UT 机器回执（与 device-testing 衔接�?
**不再**产出 `device-testing-todo.md`（已废弃）。真机要点由 prd-design 写入 `acceptance.yaml` > `device_focus`。本步在 harness PASS 后由脚本写出�?
`doc/features/{feature}/ut/reports/ac-coverage.json`（unit 层覆盖摘要，**�?* acceptance SSOT）�?
若发�?device/both AC �?`device_focus`，应回到 prd-design 补全，而非新建平行 todo 文件�?
### Step 7：输出交付摘�?
```markdown
## 业务�?UT 交付摘要（v2�?
### UseCase 清单（来�?use-cases.yaml�?| UseCase | branches �?| UT 文件 | DAG �?|
|---------|-------------|---------|--------|
| TaskHandoff | 2 | task_handoff.test.<ext> | 2 |

### DAG 文件清单
| flow_id | use_case | branches | 关联 AC |
|---------|----------|----------|---------|
| task_handoff_happy | TaskHandoff | [happy_path] | AC-1 |
| ... |

### UT 文件清单
| 文件 | 测试函数 | 用例数（= branches 数） |
|------|---------|-------------------------|
| task_handoff.test.<ext> | taskHandoffFlowTest | 2 |

### 覆盖率统�?| 指标 | 数�?|
|------|------|
| unit/both P0 AC 覆盖�?| X/N (100%) |
| unit/both P1 AC 覆盖�?| X/N (YY%) |
| BD 覆盖率（unit/both�?| X/N (ZZ%) |
| 分支覆盖率（branches�?| M/M (100%) |
| �?device-testing �?device AC | K 条（�?acceptance.yaml device_focus�?|

### 下一�?- 运行 Harness 验证（Step 8�?- 四件�?PASS �?**`ut.ok_to_testing` / `phase.next_step` 停等**（user-confirmation-ux §8）；真机 test-plan 须在用户授权 device-testing 后再派生
```

### Step 7.5：UT 编译闭环（必要出口）

> v2.2 新增�?*UT 编译/宿主静态检查是 business-ut 的必要出口条�?*。光"写完"不算，必须让当前 profile �?`ut.compile` capability 实际通过；本步骤要求 agent 自己跑闭环�?
#### 7.5.1 静�?tsc 自检（TypeScript Compiler API�?
> 这一�?harness �?`ut_tsc_compiles` 中自动跑；agent 不用手敲，但要看 harness 报告：若 FAIL，按 details 中的 `file:line:col TSxxxx message` 直接定位修�?
#### 7.5.2 profile UT 编译

**首选方式（v2.3 起推荐）**：通过 harness 触发，由 profile provider 处理底层命令拼装、环境变量注入与平台路径转义�?
```bash
cd framework/harness && npx ts-node harness-runner.ts --phase ut --feature <feature-name>
```

> **不要**�?agent 自己手敲宿主 UT 编译命令。目�?task / 模块定位 / env 注入�?harness �?profile provider 封装，日志会落到 `doc/features/<feature>/ut/reports/` 便于排错�?
#### 7.5.3 自闭环修复策�?
1. `ut.compile` 对应规则 FAIL �?进入修复�?2. 完整 Read `doc/features/<feature>/ut/reports/` 下的失败日志�?3. 按错误类型分类：
   - UT 调用的被测函数签名不�?�?�?UT�?   - UT import 路径错误 �?�?UT�?   - 类型注解与被测实际类型不匹配 �?�?UT�?   - `project_dependency_missing` / `Cannot find module 'yaml'` / `ts-node` �?**�?*�?[Host harness readiness · Tier_1](../../reference/host-harness-readiness.md) �?**`framework/harness`** 执行 `npm install`�?*禁止**�?`framework/package.json` 根依赖（�?[consumer-framework-boundary.md](../../reference/consumer-framework-boundary.md)）；
   - TS2614 `MockKit`/`when` 无导�?�?�?mock-plan �?`strategy: mockkit`，或升级 framework 发版�?*禁止**改消费�?`framework/` �?`ts-compile.ts`�?   - **若错误根因在业务源码** �?进入 Step 7.5.4 严格流程�?*禁止**自行动手�?4. 修完再跑直到 exit code = 0�?
#### 7.5.4 触及业务源码时的 HARD STOP

只要错误根因落在 **`UT_SRC_PROTECTED_PREFIXES`** 所覆盖的业务源码树（前缀�?`framework/harness/scripts/check-ut.ts` 结合实例 DSL/profile 推导，而非写死单层名）�?
1. **立即停手**，向用户输出请求�?   - 拟变更文件路径；
   - 拟修�?/ 抽取的函数签名；
   - 为何 UT/Spy/Stub 层不能规避；
   - 影响面（会触�?coding 的哪�?BLOCKER 重跑）�?2. 用户**书面同意**前不得修改任何源码文件；
3. 同意后把授权登记�?`doc/features/<feature>/ut/reports/gap-notes.md > approved_src_mutations[]`（含时间戳、文件、变更摘要、用户原话）�?4. 否则触发 harness `ut_no_src_mutation` BLOCKER FAIL�?
### Step 7.6：UT 装机运行闭环（必要出口）

> v2.2 新增：UT 必须**实际跑�?*，不是只�?看起来对"。当�?profile �?`ut.run` BLOCKER 会强制此步；�?profile 声明 SKIP，则�?harness verdict 为准�?
#### 7.6.1 探测设备

按当�?profile addendum 声明的方式探测可运行目标�?
输出非空才能�?7.6.2；输�?`[Empty]` 或为空：

- **不允�?*继续往下跑后宣�?PASS�?- **不允�?*�?本地无设�?为由�?harness 标绿�?- 必须先：准备当前 profile 要求的设�?运行环境，重新探测；
- 只有探测到设备后才能继续�?
#### 7.6.2 装机执行

**首选方式（v2.3 起推荐）**：通过 harness 触发，由当前 profile �?`ut.run` provider 执行安装/运行/结果解析链路�?
```bash
cd framework/harness && npx ts-node harness-runner.ts --phase ut --feature <feature-name>
```

一�?`--phase ut` 可同时触�?`ut.compile` + `ut.run`；日志与 summary 落到 `doc/features/<feature>/ut/reports/`，运行报�?details 会包�?provider 声明的失败阶段标签，方便定位�?
> **不要**�?agent 自己手敲宿主测试命令；必须通过 harness �?profile provider�?
#### 7.6.3 自闭环修复策�?
1. 解析 `ut.run` 报告中的测试统计�?2. failed > 0�?   - �?`doc/features/<feature>/ut/reports/hdc-test.log` 完整内容�?   - 找到 failure 用例�?`OHOS_REPORT_STATUS: stack=...` 堆栈�?   - 按堆栈定位：�?UT 逻辑错？Spy 预设值错？还是被测业务真�?bug�?   - **业务真有 bug �?*：仍�?7.5.4 �?HARD STOP 流程，先报告再改�?3. total = 0：报告会�?`失败阶段：no_pass` �?`run`——通常是测试入口没启动�?profile 测试配置不匹配；�?profile addendum 核对测试入口配置�?4. 失败阶段�?`metadata` / `artifact_not_found` / `install` �?�?7.5（先�?build 跑过）或检查当�?profile �?toolchain 配置�?5. 修完再跑直到 failed = 0 �?total > 0�?
#### 7.6.4 设备失败分类决策�?
读取 `doc/features/<feature>/ut/reports/ut-install-diag.json`（harness 装机前写入）�?`ut_hvigor_test` 报告�?
| blockingKind | 条件 | agent 动作 |
|--------------|------|------------|
| **selfHealable** | 版本降级且未�?`HARNESS_DEVICE_TEST_UNINSTALL_BEFORE_INSTALL` | 设置 env 后重�?harness |
| **needsConfirmation** | 降级 + 需用户确认卸载/�?versionCode | HARD STOP，列出诊断，等用户选择 |
| **externalBlocked** | 无设�?/ hdc 缺失 | **不循环改 UT**；告知用户准备设备；`summary.verdict=INCOMPLETE` |
| **clear** | 预检通过 | 继续 7.6.2 装机执行 |

#### 7.6.5 绝不允许

- �?无设�?标成 SKIP / PASS 上交�?- 用环境变量跳�?`ut.run` BLOCKER（harness 会转�?FAIL）；
- "我修�?UT 了，但没跑就�?——必须真的装机跑过且全部 PASS�?- 因为找不�?profile toolchain 就把规则状态写�?SKIP；必须按 profile addendum 补齐工具链配置后重跑�?
### Step 8：Harness 验证门禁（agent 必须自跑�?
> **全局入口 §4.1 明示授权**：本步骤�?harness �?verifier 调用都由�?agent 自己执行�?> **严禁**�?告知用户可运�?然后结束对话——属软幻觉，由物理拦截层兜底�?
UT 交付后，agent **必须自己**完成下列验证，再宣布 UT 阶段完成�?
#### 8.1 脚本 Harness（确定性检查，agent 通过 Shell 工具自跑�?
```bash
cd framework/harness && npx ts-node harness-runner.ts --phase ut --feature {feature} --summary --failures-only
```

agent 执行后必�?Read 退出码与报告文件；BLOCKER 必须修复后重跑�?优先读取 `doc/features/<feature>/ut/reports/summary.json`，禁止用 `grep` 解析完整控制台日志�?
�?`summary.next_action = rerun_with_HARNESS_DIFF_BASE_REF_working` �?`ut_no_src_mutation` �?`stale_diff_base`，agent 必须自动重跑一次：

```bash
HARNESS_DIFF_BASE_REF=working npx ts-node harness-runner.ts --phase ut --feature {feature} --summary --failures-only
```

重跑后如果仍�?working 侧业务源码改动，才进�?Step 7.5.4 / 约束 #12 �?HARD STOP 授权流程；禁止要求用�?批量授权历史变更"�?
**baseline 判定原则**：以 UT 阶段开始时�?working 增量为准。`stale_diff_base` �?committed 变更远大�?working 时，agent 必须自动�?`HARNESS_DIFF_BASE_REF=working` 重跑；仅 working 侧未授权业务源码变更才走 HARD STOP�?
#### 8.3 闭环条件�?INCOMPLETE

- `summary.verdict=PASS` 且零 BLOCKER �?可进�?verifier + 完成回执
- `summary.verdict=INCOMPLETE`（`partial_readiness: compile_passed_device_blocked`）→ **不满足闭�?*；不得写完成回执；`next_action=device_ready_then_rerun_ut`
- `summary.verdict=FAIL` �?修复 BLOCKER 后重�?
�?`summary.next_action = resolve_project_dependencies_then_rerun` �?`ut_compile`（及兼容别名 `ut_hvigor_build`）报 `project_dependency_missing`，按 Step 7.5.3 的依赖缺失分支处理，不得只要求用户手工执行宿�?IDE / 包管理器操作而不给出 harness 侧可复现路径�?
每次 harness 运行后，agent 必须�?`ut_run_status` 的状态面板完整贴给用户；禁止只用 `grep` 展示局�?PASS/FAIL。尤其当 `ut_compile` 失败导致 `ut_run`（及兼容别名 `ut_hvigor_test`）短路时，必须明确说�?
> 当前不能宣称 UT 通过�?*宿主测试模块未在真机/模拟器上实际执行**（详�?profile �?`ut.run` 能力说明）�?
状态面板格式：

```text
UT 阶段状态：
- 静�?结构规则：PASS/FAIL
- tsc 静态编译：PASS/FAIL
- 宿主测试模块编译�?*profile 声明的测试编译能�?/ 等价命令**）：PASS/FAIL
- 真机/模拟器执行：PASS/FAIL/未执�?- 源码改动检查：PASS/FAIL
- 当前是否可以宣称 UT 完成：是/�?```

脚本读取以下 Spec 文件执行自动化检查：
- `framework/specs/phase-rules/ut-rules.yaml`
- `doc/features/{feature}/use-cases.yaml`（v2 新增�?- `doc/features/{feature}/contracts.yaml`
- `doc/features/{feature}/acceptance.yaml`

**v2.1 检查覆盖项**�?
| 检查类�?| 检查内�?| 严重级别 |
|----------|---------|---------|
| usecase_spec_recommended | 复杂度达阈值时建议产出 use-cases.yaml | WARN |
| usecase_spec_schema | use-cases.yaml schema 合规（coordinator / ui_bindings / data_boundaries�?| BLOCKER |
| usecase_ui_bindings_nonempty | 每个 use_case �?ui_bindings & user_actions 非空 | BLOCKER |
| boundary_matches_contracts | data_boundaries[].type �?contracts.yaml > interfaces[].class �?| MAJOR |
| named_business_handler | ui_bindings.user_actions.calls 所列每个符号是命名符号（函�?类方�?类字段函�?命名 const）而非匿名 inline lambda | BLOCKER |
| dag_linked_usecase | DAG.use_case 回指 use-cases.yaml > use_cases[].id | BLOCKER |
| dag_boundary_matches_spec | port_call_* 节点 boundary = data_boundaries[].name | MAJOR |
| dag_node_type_valid | 节点类型合法（含 v2.1 新增 ui_subscription；user_intervention/ui_navigation �?deprecated�?| BLOCKER |
| ut_import_whitelist | UT 文件 import 仅限白名单（�?UI 符号�?| BLOCKER |
| ut_tsc_compiles | UT 文件 tsc --noEmit �?Error（v2.2 新增，方�?A 静态编译护城河�?| BLOCKER |
| boundaries_all_stubbed | 每个 data_boundary 都有 Spy/Fake/Stub 或原型替�?| BLOCKER |
| it_name_has_ac_or_branch_tag | 用例名带 [AC-X] / [BRANCH-X] 标签 | BLOCKER |
| it_drives_flow | 路径 A 严格判；路径 B 退化为 �? expect | MAJOR |
| branch_coverage_full | 每个 branch 都有对应 it() | BLOCKER |
| ut_case_per_unit_ac | 每条 unit/both �?P0/P1 AC 都有 it() | BLOCKER |
| acceptance_coverage | 分母只计 ut_layer �?{unit, both} | BLOCKER |
| boundary_coverage | 每条 unit/both �?BD 都有覆盖 | MAJOR |

**若报告中存在 BLOCKER**：必须修正（回到 Step 2 / 3），直到�?BLOCKER�?
### Step 8.0：Core 节点闭环闸门（需求收尾）

�?harness 全绿后，评估本次改动是否触及模块 **Code Graph** �?`core: true` 节点（路�?`paths.module_graphs_dir`，默�?`<module>/code-graph.yaml`）：

1. 读取相关模块 Code Graph；对�?`contracts.yaml` / diff 触及的源码文件与 `core` 节点 anchor�?2. **触及 core** �?启动可行性探测；更新/增删图谱节点；同�?characterization �?spec-driven UT�?*flow DAG 可归�?*�?`{module}/test/dag/`�?3. **未触�?core** �?flow DAG 保持 ephemeral（`ut/reports/flow-dag/`），用完即弃�?
#### 8.2 AI Harness（语义级检查，agent 主动通过 Task 工具触发 verifier �?agent�?
agent 必须主动通过 Task 工具调用 `subagent_type: verifier`（不�?告诉用户去跑"），�?feature / phase / 脚本报告路径传入�?
- **Prompt 模板**：`framework/harness/prompts/verify-ut.md`（由 verifier �?agent 自行读取�?- **触发方式**：Task 工具，subagent_type=verifier，prompt 中给�?feature/phase/脚本报告路径
- **v2.1 语义检�?*�?  1. `state_model_completeness` �?state_model 是否足以表达所有分支（若有 use-cases.yaml�?  2. `ui_bindings_completeness` �?ui_bindings 是否覆盖所�?UI 节点、命名语义是否清晰（若有 use-cases.yaml�?  3. `end_to_end_driving`（BLOCKER）�?每个 it() 是否端到端驱动（命名入口 + callLog + state 多断言，或退化判断）
  4. `branch_coverage_semantic` �?branches 是否涵盖 PRD 中所有异常路径（若有 use-cases.yaml�?  5. `device_ac_delegation` �?device/both �?AC 是否已声�?device_focus
  6. `stub_reasonableness` �?替身预设值是否与 data/model 一致、跨用例无污�?  7. `test_isolation` �?beforeEach / afterEach 是否正确隔离

**�?AI 报告中存�?BLOCKER �?FAIL**：修正后重新验证�?
#### 8.3 阶段闭环判定（全局入口 §5.1 �?SSOT，四条件缺一不可�?
> 下文「物理拦截层」：**部分 adapter** �?framework-init 在实例根下发 **Stop hook**，在消息结束前读�?state 并阻断「假完成」（Layer 3 行为与路径见 [framework/agents/README.md](../../../agents/README.md)）�?*�?*配置该能力的 adapter 不设物理层豁免，仍须满足 Layer 1（全局入口 §6.5「反假设条款」）+ Layer 2（完成回�?+ `check-receipt.ts`）—�?*没有 Stop hook �?豁免 BLOCKER**，少跑一项即任务失败�?
UT 阶段宣布"完成"前必�?*同时**满足�?
1. `doc/features/<feature>/ut/reports/trace.json` 真实存在�?2. 脚本 harness 退出码 0、零 BLOCKER�?3. verifier �?agent 报告 verdict = PASS�?4. 完成回执 `doc/features/<feature>/ut/phase-completion-receipt.md` 已填写并通过 `cd framework/harness && npx ts-node scripts/check-receipt.ts --feature <feature> --phase ut` 校验�?
| 验证�?| 通过条件 |
|--------|---------|
| 脚本 Harness | �?BLOCKER（agent 自跑�?|
| AI Harness | verdict = PASS（agent 通过 Task 触发 verifier�?|
| 完成回执 | check-receipt.ts 退出码 0 |
| trace.json | 文件存在�?schema 合法 |

四项全部通过后，业务�?UT 阶段完成�?*具备**进入 device-testing（真机测试）�?*资格**�?*不授�?*自动开 device-testing�?
**闭环停等（BLOCKER，user-confirmation-ux §8�?*：须 **`ut.ok_to_testing`** �?**`phase.next_step`** 停等（除�?batch 授权 §8.2）。物理拦截层会读 `framework/harness/state/.current-phase.json` 与上述四份凭证决定能否放行�?
## 关联文件

- 上游输入:
  - `doc/features/{feature}/use-cases.yaml`（requirement-design v2.1 产出，仅复杂 feature�?  - 业务编排源代码（coding v2.1 产出，代码形态由 coding 自选：Page 命名方法 / `Flow`/`Coordinator` 普通类 / 导出函数�?*不强�?* `domain/usecase/` 目录�?  - data 层源代码（`data/repository/*.<ext>` / `shared/client/*.<ext>` 等）
  - `doc/features/{feature}/design/design.md` / `prd/PRD.md` / `contracts.yaml` / `acceptance.yaml`
- 阶段级规�? `framework/specs/phase-rules/ut-rules.yaml`
- UseCase Schema: `` `profile-skill-asset:business-ut/use_cases_schema` ``
- DAG Schema: `` `profile-skill-asset:business-ut/dag_schema` ``
- UT / Spy 模板: `` `profile-skill-asset:business-ut/ut_template` ``
- 打桩策略: `` `profile-skill-asset:business-ut/mock_strategy` ``
- 规范级样�? `` `profile-skill-asset:business-ut/sample_flow_dir` ``
- 脚本 Harness: `framework/harness/scripts/check-ut.ts`
- AI Harness Prompt: `framework/harness/prompts/verify-ut.md`
- 下游消费�?

| 消费�?| 消费的产�?| 用�?|
|--------|-----------|------|
| **device-testing (真机测试)** | `acceptance.yaml`（device_focus�? UT + DAG | 真机 test-plan 与追�?|
| **Harness (验证�?** | use-cases.yaml + DAG + UT | 脚本/AI 验证 UT 质量 |
| **开发�?* | DAG + 业务编排源码 | 理解业务流程，维�?UT |

## 约束与注意事�?
1. **UT 是消费者，不驱动架�?*�?*绝对禁止**为了 UT 反向要求 requirement-design/3 新增特定目录下的 `XxxUseCase` 类或 Port 接口。若业务嵌在 `onClick = () => {}` 内，应反�?coding 抽出命名方法，而不是在 UT 里实例化 **UI 组件**�?2. **use-cases.yaml 非必需**：仅复杂 feature（多 UI 共享状�?/ 多步云调�?/ 含回滚分支）才有该文件；简�?feature 直接�?acceptance.yaml + dag.yaml 针对 data 层写 UT，不要硬凑�?3. **分支 1:1 映射**（路�?A）：`use-cases.yaml > branches[]` �?DAG branches �?UT `it()` 严格 1:1（允�?1 �?DAG 覆盖多个 branch，但总并集需覆盖全部�?4. **AC 分层**：只�?`ut_layer in [unit, both]` �?AC/BD；`device` �?AC 须在 acceptance `device_focus` 中声明，绝不�?UT �?硬凑"覆盖
5. **Mock 不真�?*：UT 中严禁发起真实网络请求、真实系�?API 调用或真�?IO 操作
6. **用例隔离**：每�?`it()` 用例独立运行，在 `beforeEach` 中重建替身；原型替换方案必须�?`afterEach` 还原
7. **替身类型契合**：`SpyXxx` 子类化或 `XxxPort.prototype.method = ...` 必须�?contracts.yaml 中的既有类签名一�?8. **ut_import_whitelist 强约�?*：UT 仅允�?profile addendum �?`ut-ui-import-ban` 定义的白名单 import
9. **P0 优先**：先�?P0 AC / 高危 branch 生成 UT，再扩展 P1 / P2
10. **中文注释**：DAG / UT �?description 使用中文，便于业务理�?11. **Harness 验证闭环**：UT 完成�?agent **必须自己运行** Harness 验证（Step 8），并主动通过 Task 工具触发 `subagent_type: verifier`；确保零 BLOCKER + verifier PASS + 完成回执通过校验后才进入下一阶段（物理拦截层兜底�?    - �?`ut_no_src_mutation` 报告 committed 历史变更多、working tree 变更少，优先怀�?diff 基线过旧；可设置 `HARNESS_DIFF_BASE_REF=working` 只检查当前工作区�?*禁止**要求用户"批量授权所有历史变�?�?12. **【HARD STOP �?不可绕过】禁止擅自修改业务源�?*：business-ut 阶段 agent �?**受保护业务源码前缀**（定义见 `check-ut.ts` �?profile，不再写�?`02-Feature` 等目录名）下、且**�?profile 声明的测�?夹具源目�?*内任何文件的修改�?*必须**满足以下全部条件�?    1. **动手�?*显式向用户提出请求（`ut.src_mutation` · freeform + portable�?*须先展示完整变更描述**）：

       ```text
       1. 授权改源�?       2. 拒绝
       3. 先看 diff
       ```

       请求中必须包含：
       - 拟变更的文件路径�?       - 拟抽�?新增的函数签名（或修�?diff 摘要）；
       - **为何不能通过只修�?UT / DAG / use-cases.yaml 规避**该变更的技术理由；
       - 预估影响面（会触�?coding harness 的哪些规则重跑）�?    2. 用户**书面同意**后方可动手（对话中明�?"同意" / "approved" / "OK" 等正面表述）�?    3. 动手后必须把授权纪要写入 `doc/features/<feature>/ut/reports/<timestamp>/<model>-ut/gap-notes.md > approved_src_mutations[]`：包含时间戳、文件路径、变更摘要、用户确认原�?链接�?    4. **未登记的 src/main 变更一律视为违�?*，会触发 harness `ut_no_src_mutation` BLOCKER�?    5. **特别禁止**以下常见"便利�?借口直接动手�?       - "named_business_handler 报错 �?顺手抽个函数/改成命名字段" �?必须先问�?       - "UT 无法访问私有成员 �?�?private 改成 public" �?必须先问�?       - "UT 需要某个工具函�?�?顺手新增一�? �?必须先问�?       - "导入路径不便 �?顺手�?barrel 导出" �?必须先问�?    违反 HARD STOP 的行为会被后�?code-review（Code Review）追溯并标记为质量事件�?    > 推荐替代路径：优先在 UT/Spy 侧用原型替换、`as unknown as T` 注入等方式绕过可测性障碍；确需源码变更时优先选择"抽出命名方法 / 导出函数 / 普�?class"而非新�?Port / UseCase 类�?
---

## Slash / 快捷入口触发时的 trace 约定

当本 Skill 通过适配器下发的 slash（如 `/business-ut`）或其它等价快捷入口触发时，**必须**在阶段结束时产出一�?trace 凭证�?
- **路径约定**：`doc/features/<feature>/ut/reports/<timestamp>/<model>-ut/trace.json`
- **Schema**：[framework/harness/trace/trace.schema.json](../../../harness/trace/trace.schema.json)，`phase` 字段�?`ut`�?- **痛点回填**：同目录 `gap-notes.md`，模板见 [framework/harness/trace/gap-notes.template.md](../../../harness/trace/gap-notes.template.md)�?
---

## 运行时交付约定（内网 / 弱模型）

```
doc/features/<feature>/ut/reports/<timestamp>/<model>-ut/
├── trace.json             # phase = "ut"
├── gap-notes.md
├── check-ut.report.md
└── verifier.report.md     # verifier �?verify-ut.md（可选）
```
