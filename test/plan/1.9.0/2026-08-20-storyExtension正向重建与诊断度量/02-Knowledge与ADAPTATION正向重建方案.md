# Knowledge 与 ADAPTATION 正向重建方案

> 状态：已实施并通过离线验证；本仓默认同时激活两份设计模式
> 本文件定义 Extension Knowledge 的目录、文件职责、运行激活、阶段消费和目标仓适配。  
> Story 的输入和人读成文见 [01-Story完整正向优化方案.md](01-Story完整正向优化方案.md)。

## 1. 要解决的问题

当前 Knowledge 同时通过 Manifest、README、目录扫描、静态链接和 ADAPTATION 状态被发现。文件存在、正式交付和当前工程实际启用被混成一件事；Story、Spec、Plan、Coding 又分别读取部分工程事实，导致需求叙述、工程选择和实现职责交叉。

本轮固定以下设计：

1. Knowledge 只有 Project Facts、Constraints、Patterns 三类；
2. Knowledge 文件是否正式交付，与目标仓是否激活分开；
3. Framework Manifest 是唯一运行激活清单；
4. Story 不读工程 Knowledge；
5. Spec 识别需求影响和模式候选，Plan 结合真实源码完成选择并冻结；
6. Coding 读取真实源码、冻结合同和已选模式/约束，不重新通读 Project Facts；
7. ADAPTATION 只指导目标仓改造和发布，不参与 feature 运行。

不建设通用知识平台、第二份 registry、Knowledge 状态机、候选目录或新的 Framework 协议。

## 2. 目标目录

```text
doc/extensions/
├─ manifest.yaml
├─ ADAPTATION.md
├─ scripts/
│  ├─ active-knowledge.mjs
│  └─ verify-adaptation.mjs
└─ knowledge/
   ├─ project-facts/
   │  ├─ component-boundaries.md
   │  └─ codebase-capabilities.md
   ├─ constraints/
   │  ├─ README.md
   │  ├─ security-privacy.md
   │  ├─ ux-consistency.md
   │  ├─ compatibility-checklist.md
   │  ├─ dfx-baseline.md
   │  ├─ env-exceptions.md
   │  ├─ deliverables.md
   │  └─ diagnostics-metrics.md
   └─ design-patterns/
      ├─ README.md
      ├─ decision-tree.md
      ├─ page-interaction.md
      └─ <目标仓新增的模式>.md
```

不增加根级 Knowledge README。Project Facts 只有两份文件，不需要再建索引；Constraints 和 Patterns 的 README 只服务维护与适配。

## 3. 文件职责和应用场景

### 3.1 Project Facts

Project Facts 回答“目标仓现在是什么样”，不规定单个 feature 应采用什么。

| 文件 | 作用 | 应用场景 |
|---|---|---|
| `project-facts/component-boundaries.md` | 部件职责、不负责内容、业务边界、交互对象、跨模块出口和依赖方向 | Spec 判断 Scope、术语和集成边界；Plan 判断模块责任和依赖合法性 |
| `project-facts/codebase-capabilities.md` | 真实 API、SDK、依赖、工具链、已有或明确不存在的能力、运行限制和失败语义 | Spec 判断需求依赖的能力是否存在；Plan 选择真实 API 并写入 contracts |

原 `component-profile.md` 与 `codebase-facts.md` 合并为一个 Project Facts 类别，但保留两份聚焦文件。这样不会把稳定的职责边界和易变化的 API 细节混在同一篇中。

Project Facts 不写 feature 采用结果、测试答案、Demo 猜测或阶段操作步骤。

### 3.2 Constraints

Constraints 回答“所有命中该条件的 feature 都必须遵守什么”。

| 文件 | 作用 | 典型场景 |
|---|---|---|
| `constraints/README.md` | 说明规则表格式、强制力、ID 和维护方法 | 维护与适配；不进入 Manifest，运行期不读取 |
| `security-privacy.md` | 数据保护、敏感信息、权限和对外暴露底线 | 日志、上报、存储、权限、新接口 |
| `ux-consistency.md` | 多语言、RTL、界面适配和交互一致性 | 新页面或 UI 改版 |
| `compatibility-checklist.md` | 接口、字段、错误码、缓存和升级兼容 | 修改接口、数据结构或既有行为 |
| `dfx-baseline.md` | 性能、功耗、ROM、RAM 和高频调用约束 | 新 SDK、资源、轮询、数据库或高频任务 |
| `env-exceptions.md` | 清数据、重复进入和设备环境变化后的恢复 | 本地状态、深链入口、重复提交、环境异常 |
| `deliverables.md` | 翻译、说明文档和代码之外的交付要求 | 新文案、开放接口、上线资料 |
| `diagnostics-metrics.md` | 日志、VOC、Chart 的共同底线 | 秘密字段排除、失败隔离、Chart 单次终态和低基数字段、VOC 摘要边界 |

`diagnostics-metrics.md` 不保存某个 feature 的事件名、字段表和调用位置。具体观测设计仍由 Spec 表达业务意图，Plan 写入现有 `contracts.yaml > observability`。

每个 Constraint 文件的 frontmatter `name` 与文件 stem 一致，作为 `constraint_id`。文件内每个 `rule_id` 在全部 active Constraints 中全局唯一，并能唯一解析为所属 domain。重复、错 owner 或无法解析均失败。

README 可以说明交付的规则域和维护方法，但不得维护 active 状态、阶段命中矩阵或另一份规则清单。阶段用法属于 Hook/overlay。

### 3.3 Patterns

Patterns 回答“什么形状的问题适合用哪种结构，以及采用后怎样设计和落地”。

| 文件 | 作用 | 典型场景 |
|---|---|---|
| `design-patterns/README.md` | 说明模式文件结构、维护方法和 Manifest 激活方式 | 维护与适配；不作为模式，不进入 Manifest |
| `decision-tree.md` | 复杂分支流程的识别、契约投影和实现指导 | 多个复杂业务分支、补偿或恢复路径 |
| `page-interaction.md` | 多交互页面的动作编排、等待和恢复指导 | 页面动作多，后续交互由业务结果驱动 |
| `<其他模式>.md` | 目标仓正式增加的其他模式 | 完成真实取证和复核后使用 |

两份默认模式始终是 Extension 的正式交付内容，本仓 Manifest 默认同时激活 `decision-tree` 和 `page-interaction`。只有适配到其他工程时，才根据目标仓的真实需要改为零模式、只启用其中一种、继续启用两种，或启用其他模式。

每个模式文件的 frontmatter `name` 与文件 stem 一致，作为 `pattern_id`。文件自身完整包含：

- 适用意图、适用单元和不适用边界；
- 角色、状态、生命周期和失败收敛；
- 向 contracts/use-cases 的投影；
- 目标仓真实 SDK/API、工程落点和使用约定；
- 编译、审查和测试指导；
- 真实主案例与边界案例的依据。

当前 README 中的路由信号迁回各模式文件；多模式组合的通用责任、上下文所有权、交接、等待和失败收敛要求进入 Plan overlay。运行期不再读取 README，因此不会丢失选型和组合能力，也不会让 README 成为第二个激活入口。

## 4. 正式交付与运行激活

### 4.1 Manifest 是唯一 active 清单

继续使用 Framework 现有字符串数组，不修改 schema：

```yaml
provides:
  knowledge:
    - knowledge/project-facts/component-boundaries.md
    - knowledge/project-facts/codebase-capabilities.md
    - knowledge/constraints/security-privacy.md
    - knowledge/design-patterns/decision-tree.md
    - knowledge/design-patterns/page-interaction.md
```

规则固定为：

1. 只有 `provides.knowledge` 精确列出的文件进入运行期；
2. README、未列文件、ADAPTATION、测试夹具和历史材料均不生效；
3. 文件存在和随 Extension 交付都不能替代 Manifest 激活；
4. 同一路径只出现一次；缺失、越根、非法类别、重复或解析失败立即失败；
5. 本仓 active Patterns 默认为两份；其他目标仓完成适配后可以为零，正式交付的两份默认模式文件仍保留；
6. 只有完成目标仓取证和人工复核的 item 才能加入 Manifest。

README 不带 Knowledge item 的 frontmatter `name`，避免被误识别成第三个模式或规则域。

### 4.2 三种模式适配

| 目标仓情况 | 适配动作 | 运行结果 |
|---|---|---|
| 本仓默认 | Manifest 同时列出 `decision-tree.md` 和 `page-interaction.md` | 两份模式都进入 Spec 候选范围，但只在当前需求真实命中时进入 Plan 选型 |
| 不需要任何模式 | Manifest 不列 pattern 文件；默认两份文件不改也不删除 | Spec/Plan 模式集合为 `[]`，下游模式义务全部 SKIP |
| 复用默认模式 | 只校准所用文件中的目标仓 SDK/API、案例、工程落点和失败语义，复核后加入 Manifest | 只激活实际复用的一种或两种 |
| 使用其他模式 | 按同一文件合同新增模式文档，取证复核后加入 Manifest | 默认模式可继续保持未激活 |

不创建 candidates、examples 或复制流程。适配者直接维护正式模式文件，Manifest 决定当前目标仓是否使用。

### 4.3 模式运行三态

| 仓库状态 | Spec/Plan 形态 | 下游行为 |
|---|---|---|
| active Patterns 为空 | 不生成模式候选子节，机器集合为 `[]` | 模式 Hook/overlay SKIP |
| active Patterns 非空，但当前需求零命中 | 按真实适用单元记录“无候选”，集合为 `[]` | 不虚构采用或实现义务 |
| 存在候选 | Spec 登记 active `pattern_id` 和需求证据；Plan 采用或不采用 | 只有采用项进入 `project_knowledge` |

## 5. 唯一解析实现

新增 Extension 内部纯模块 `doc/extensions/scripts/active-knowledge.mjs`，供动态 Hook 与专用校验共用。它只负责：

1. 读取 `manifest.yaml > provides.knowledge`；
2. 解析安全的 Extension 相对路径；
3. 按三个物理目录分类；
4. 读取 item `name`、constraint `rule_id` 和 pattern `pattern_id`；
5. 检查路径、类别和 ID 唯一性；
6. 返回调用阶段需要的精确 active 集。

它不扫描目录、不读取 README、不解析 ADAPTATION 状态、不判断业务是否适用，也不替代 Framework extension-loader。解析失败是错误，不解释为空集。

动态 `on_context_load`、`post_check` 和 `pre_verifier` 共用这个模块。静态 overlay 只保留阶段通用义务，不列具体文件、ID、SDK 或业务名；现有静态 Markdown Hook 无法调用解析器的，改成 Manifest 已支持的动态 Hook 形态。

## 6. 阶段消费

### 6.1 Story

Story 只读需求材料和 Review，不读取 Project Facts、Constraints 或 Patterns。Story Skill、rules、reference 和 Story 成文注入中的工程 Knowledge 静态直链全部退出。

### 6.2 Spec

Spec 的动态 Hook 只注入 active Knowledge：

- Project Facts：核对 Scope、已有能力和集成边界；
- Constraints：把确实改变需求、体验、边界或验收的命中项写入 Spec/Acceptance；
- Patterns：按需求事实识别候选，不决定采用；
- 诊断与业务度量：只表达需要定位或统计的业务意图。

### 6.3 Plan

Plan 读取 Spec 候选、active Knowledge 和当前真实源码，独立完成：

1. 选择实际模块、API、文件和接口；
2. 对模式候选采用或不采用；
3. 将命中 Constraints 转成设计和验证义务；
4. 把选定 API 写入现有 contracts 的 modules、interfaces、files 和 observability；
5. 把采用模式和命中规则冻结到 `contracts.yaml > project_knowledge`。

`project_knowledge` 只保留当前 feature 的应用结果：

- `pattern_applications`：实际采用的模式及 `knowledge_ref`；
- `constraint_obligations`：实际命中的规则、处置和实现/验证锚点。

引用必须精确命中 active 文件、`pattern_id`、`rule_id`、正式 Acceptance/Use Cases ID、现有 contract 对象或安全项目相对路径。不引入 typed-reference DSL 或文件级 action 合同。

### 6.4 Coding

Coding 必须读取真实源码、依赖声明和类型定义，但不重新通读 Project Facts。它只消费：

- Plan 冻结的 modules、interfaces、files、observability 和 use-cases；
- `project_knowledge` 中实际采用模式的 `knowledge_ref`；
- `constraint_obligations` 实际命中的规则。

真实源码与冻结合同不一致时，停止并回 Plan；目标仓能力事实本身错误时，再由 Plan/ADAPTATION 修正 Project Facts。Coding 不静默换 API、重选模式或重扫 Knowledge。

### 6.5 Review、UT、Testing

Review 针对同一冻结合同和真实 diff 检查模式实例、规则义务、编译和测试证据。UT 只验证分配给 UT 的可观察行为，Testing 只验证设备和环境相关行为；纯结构模式允许按 Plan 证据 SKIP。

知识引用退出 active 集、ID 无法解析或事实陈旧时直接失败，回 Plan/ADAPTATION 修正。下游不得静默裁剪。

## 7. ADAPTATION

`ADAPTATION.md` 随 Extension 交付，只服务“把 Extension 接入真实目标仓”的人或 agent。正常 Story、Spec、Plan、Coding、Review、UT、Testing 不读取它。

适配顺序固定为：

1. 读取目标仓 architecture、catalog、glossary、真实源码、依赖和工具链；
2. 重写两份 Project Facts；
3. 复核并启用目标仓适用的 Constraints；
4. 按第 4.2 节选择零模式、复用默认模式或新增模式；
5. 运行专用检查和人工复核；
6. 将确认可用的文件精确加入 Manifest；
7. 运行 Framework `extensions` gate。

模式取证仍按“目标仓模式 Skill → 真实 SDK → 多个既有业务案例”完成。默认模式文件的通用意图和文档结构可以复用；SDK/API、工程落点、运行时事实和案例必须以目标仓为准。

ADAPTATION 不维护运行时状态表。Manifest 变更表示目标仓决定启用，模式文件本身保存可核对事实，实施与消费证据进入正常评审和阶段报告。

## 8. 专用验证

`doc/extensions/scripts/verify-adaptation.mjs` 调用同一 active resolver，只检查 Extension 特有事实：

- active item 路径、类别、文件和 ID 合法且唯一；
- README、ADAPTATION 和未列文件没有进入 active 集；
- active Project Facts、Constraints、Patterns 不含未适配占位和目标仓外的假事实；
- active Constraint 的 `rule_id → domain` 唯一；
- active Pattern 的 SDK/API、主案例和边界案例可核对；
- 零 active Pattern 可以通过，即使两份默认模式仍正式交付；
- Story 不静态链接工程 Knowledge；
- Hook/overlay 不残留目录扫描、README 路由或具体模式专名；
- ADAPTATION 中的命令和路径位于正式交付边界。

专用检查不签发 phase PASS。通过后仍必须运行 Framework `extensions` gate、相关 phase Harness、独立 Verifier、Trace 和完成回执。

## 9. 验收

### 9.1 目录与激活

- 目标目录与第 2 节一致；
- README 存在但永不成为 active item；
- 正式模式文件存在但未列 Manifest 时不进入任何运行 prompt；
- Manifest 缺失、越根、重复、非法类别或解析失败时 fail closed；
- active resolver 是 Hook 和专用检查的唯一解析实现。

### 9.2 三类 Knowledge

- Project Facts 两份文件各自聚焦，无并列 `codebase_facts` 类别；
- 七个 Constraint 域职责不重叠，`diagnostics-metrics.md` 不保存 feature 事件设计；
- 默认两份 Pattern 正式交付，README 不再提供运行路由；
- 每个 active item 的 ID 与物理文件唯一对应。

### 9.3 模式适配与消费

- 零模式：默认文件保留、Manifest 无 pattern、Spec/Plan/下游无模式污染；
- 复用默认模式：只激活实际适配并确认的文件；
- 新增模式：不修改通用 Hook/overlay 即可进入同一候选和冻结链；
- active 模式零命中、候选后不采用、采用三种 feature 结果均能如实表达；
- Spec 候选、Plan 选择、`project_knowledge` 和下游 diff 一致。

### 9.4 阶段边界

- Story prompt 不含工程 Knowledge；
- Spec/Plan 只读取 active 集；
- Plan 将选中 API、模式和规则完整冻结；
- Coding 读取真实源码和冻结合同，不重新通读 Project Facts；
- 下游不重扫目录、不重选知识，陈旧或失活引用能正确失败。

### 9.5 ADAPTATION

- 目标仓可以用最少动作完成零模式、复用默认模式或新增模式；
- inactive 默认模式不要求目标仓适配或确认；
- active item 均有目标仓事实和人工复核；
- 不依赖 `test/story`、历史 Case、Demo SDK 或本仓绝对路径；
- 专用检查和 Framework `extensions` gate 各自通过。

## 10. 受影响范围与完成判据

实施时允许调整：

- `doc/extensions/knowledge/` 的目录和文件；
- `doc/extensions/manifest.yaml`、`scripts/active-knowledge.mjs` 和 `verify-adaptation.mjs`；
- `doc/extensions/hooks/` 与 `rules/*-overlay.yaml`；
- `doc/extensions/ADAPTATION.md`；
- Story 中需删除的工程 Knowledge 静态直链；
- `test/story` 中直接验证上述生产合同的现有测试和文档。

不允许修改 `framework/`、创建新 phase、第二份 registry、候选目录或新的通用 Knowledge schema。

本方案完成必须同时满足：

1. 三类 Knowledge、目标目录和文件职责唯一；
2. Manifest 是唯一 active 清单，正式交付与运行激活已分开；
3. 两份默认模式正式保留，零模式、复用和新增模式适配均成立；
4. Story 与工程 Knowledge 完全隔离；
5. Spec、Plan、冻结合同和下游消费只有一条交接链；
6. Coding 不重新通读 Project Facts，但真实源码核对没有减少；
7. 诊断与度量共同规则集中在 `diagnostics-metrics.md`；
8. ADAPTATION 不形成运行状态，Framework 文件零修改；
9. 04 规定的正式 gate、phase 闭环和交付报告全部通过。
