# 步骤 4：Plan 工程知识生效设计

> 前置：[扩展生命周期与配置设计](03-扩展生命周期与配置设计.md)  
> 本步交付：Plan 对模式候选和规约事实作出需求化判断，形成真实设计与下游可消费的机器契约。

## 1. Plan 的职责

Spec 回答“需要实现什么、观察到哪些模式信号”；Plan 回答“本需求采用什么设计、为什么、怎样落到契约”。Plan 必须完成：

1. 逐项处置 Spec §10 的模式候选；
2. 按路由表粒度复核适用单元，必要时补充 Spec 未观察到的设计事实；
3. 对采用的模式完成实例化设计；
4. 按 constraints 适用矩阵 Plan 列，逐个非“—”域判断本需求是否命中具体规则并形成设计处置；
5. 把结构性结论投影到 contracts，把可观察行为投影到 use-cases 或 acceptance；
6. 为 Coding、Review、UT、Testing 冻结明确的消费锚点。

Plan 可以拒绝 Spec 候选，但必须给出需求事实和选型理由。Plan 也可以基于深入设计补充候选，补充项遵循同一套登记、投影和验证规则。

## 2. 阶段输入

- `spec/spec.md` 的实现要求、技术契约和 §10 设计模式信号；
- `knowledge/design-patterns/README.md` 的适用单元、路由信号和 `pattern_id`；
- 实际候选模式文档的选型、契约投影、SDK 行为与使用约定；
- `knowledge/constraints/README.md` 的阶段适用矩阵及实际相关域文件；
- 代码库事实、组件画像、架构 DSL 和既有业务实现；
- framework 原生 Plan 要求的 scope、files、interfaces、acceptance 和 use-case 输入。

作者只读取实际进入判断分支的模式和规约正文。路由表未命中的模式不加载，规约矩阵中 Plan 列为“—”的域不消费。

## 3. plan.md 的 AI 工程知识消费契约

`plan.md` 使用以下固定标题和稳定字段，作为 Plan 作者、Plan verifier 以及 Coding、Review、UT、Testing AI 的统一定位入口：

```markdown
## 工程知识应用契约

### 设计模式应用
### 应用域约束处置
```

该区域优先保证 AI 能稳定发现候选处置、选型理由、规约命中和设计锚点，不以面向人的叙述优化为目标。共享 hook 直接指向以上标题，阶段模型无需从任意章节中猜测工程知识落点。

### 3.1 设计模式应用

| 适用单元 | Spec 候选信号 | Plan 结论 | pattern_id | 实例名 | 选型理由 | 设计/契约锚点 |
|---|---|---|---|---|---|---|

规则：

- 每个 Spec 候选都有一行“采用”或“不采用”结论；
- 采用项必须指向真实文件、接口、组件、角色、状态或行为设计；
- 不采用项保留候选 `pattern_id` 和拒绝理由，不进入机器交接；
- Plan 补充的候选标明新增信号来源，并按同样方式处置；
- 完全没有适用单元时，在固定表格中写一行“无适用单元”及需求事实，其余字段使用 `—`，不创建伪实例。

### 3.2 应用域约束处置

| 约束域 | 本需求事实 | 实际命中 rule_id | 设计处置 | 实现锚点 | 验证锚点 |
|---|---|---|---|---|---|

规则：

- 覆盖适用矩阵 Plan 列所有非“—”域；
- `rule_id` 只填写该需求真正命中的条目；
- 域相关但没有具体条目命中时写“—”，同时保留判断事实；
- 命中项必须改变设计，且能指向实现与验证对象；
- 表格是 AI 的稳定消费索引；详细接口、状态、文件和行为仍进入 Plan 主体设计及正式契约，AI 通过锚点继续读取对应设计。

## 4. 最小机器交接

`contracts.yaml` 使用一个扁平、稳定的扩展命名空间：

```yaml
project_knowledge:
  pattern_applications:
    - unit: <适用单元>
      pattern_id: <受控 ID>
      instance: <实例名>
      knowledge_ref: <模式知识文件>
      contract_anchors: [<contracts 内的文件/接口/组件/角色/状态锚点>]
      behavior_anchors: [<acceptance/use-case 中的可观察行为锚点>]

  constraint_obligations:
    - domain: <约束域>
      rule_ids: [<实际命中的受控 ID>]
      decision: <需求化设计处置>
      implementation_anchors: [<contracts 内的文件/接口/资源/配置锚点>]
      verification_anchors: [<AC/BD/UseCase/Branch 锚点>]
```

边界：

- `pattern_applications` 只包含采用的模式；候选拒绝结论留在 `plan.md`；
- `constraint_obligations` 只包含实际命中的规则；逐域零命中判断留在 `plan.md`；
- 同一域的多个规则只有在处置和锚点相同时才合并，否则分项记录；
- `contract_anchors` 指向模式的内部结构与协作契约；
- `behavior_anchors` 指向该模式产生的外部可观察行为。纯结构型模式可以为空，但 `plan.md > 工程知识应用契约` 必须在固定字段中声明“纯结构型，无新增外部行为”；
- `implementation_anchors` 和 `verification_anchors` 分别供 Coding/Review 与 UT/Testing 消费；
- 完全零命中时两个数组为空，不新增 `none_reason`、`applicability` 或平行台账。

两份产物按信息类型分工：

- `plan.md > 工程知识应用契约` 是候选处置语义真源，保存采用、不采用、理由、域级零命中判断和设计锚点；
- `contracts.yaml > project_knowledge` 是下游执行真源，只保存已采用模式、实际命中规约及其结构化锚点；
- 共享 hook 要求下游 AI 先定位这两个入口：以 contracts 决定必须执行什么，以 plan 契约理解为什么这样选以及哪些候选已被明确排除；
- post-check 保证采用项、命中项和锚点一致，避免两份投影发生漂移。

## 5. 投影边界

| 信息 | 正式落点 |
|---|---|
| 模式角色、节点、动作、接口、组件和所有权 | `contracts.yaml` 既有 contracts 结构及其锚点 |
| 内部编排状态与结构性不变量 | `contracts.yaml` |
| 用户或外部系统可观察的状态、事件、失败和恢复 | `use-cases.yaml` 或 `acceptance.yaml` |
| 规约产生的实现义务 | contracts 的文件、接口、资源、配置与状态锚点 |
| 规约和模式产生的验证义务 | acceptance/use-case 的 AC、BD、UseCase、Branch 锚点 |

工程知识不会推动简单需求虚构 UseCase 架构。`use-cases.yaml` 是否生成继续遵循 framework 的原有复杂度判断；简单需求使用 acceptance 中的现有承载字段。

## 6. Plan post-check

`hooks/plan/post_check.mjs` 只检查确定性事实：

1. Plan 中存在固定的 `工程知识应用契约`，并包含 `设计模式应用` 与 `应用域约束处置` 两个 AI 消费区；
2. Spec §10 每个候选都有采用/不采用结论和理由；
3. 采用项与 `project_knowledge.pattern_applications` 一一对应；
4. `pattern_id`、`rule_id` 来自在册知识；
5. Plan 表与 contracts 中的采用项、命中项一致；
6. 适用矩阵 Plan 列每个非“—”域都有一行需求事实与处置；
7. 机器交接中的锚点非空且指向已规划的 contract、AC、BD 或 UseCase 对象；
8. 纯结构模式的空 `behavior_anchors` 在 AI 消费契约中有明确、可定位的结构化说明；
9. 正向命中、部分命中和完全零命中结构均合法。

post-check 不判断模式是否选得好、规约是否真的改变了设计，也不通过关键词判断语义。这些由 overlay 完成。

## 7. Plan 语义检查

保留现有 check ID，更新其消费结构：

- `plan_pattern_selection_projected`：逐候选审查适用性、选型理由、模式实例和真实设计投影；仅有应用表或 ID、没有结构与行为变化时 FAIL；
- `plan_constraint_coverage`：逐个 Plan 适用域审查需求事实、实际命中规则与设计处置；仅写“已考虑”或堆编号、没有设计变化时 FAIL。

两个检查都必须给出 `plan.md`、`contracts.yaml` 和 acceptance/use-cases 的具体证据。共享 pre-verifier 负责保证它们出现在 verifier 报告中。

## 8. 下游交接

| 阶段 | 从 Plan 获得什么 |
|---|---|
| Coding | 模式实例、结构锚点、行为锚点、规约实现义务 |
| Review | 同一冻结结果与实际 diff 的审查基准 |
| UT | 模式可观察行为锚点和规约验证锚点 |
| Testing | 被分配到真机层的行为/验收锚点和规约验证锚点 |

下游发现选型、契约或验证分层错误时，按 correction 回到 Plan 或 Spec 修正真源，不在本阶段静默重选。

## 9. 完成条件

- 每个 Spec 模式候选均被采用或有理据地拒绝；
- 采用的模式改变真实设计，并形成结构锚点与适用的行为锚点；
- Plan 列所有应消费规约域都有需求化判断，只有实际命中项登记 `rule_id`；
- 命中规约形成可执行的实现和验证义务；
- `project_knowledge` 只保存下游真正需要的采用项和命中项；
- post-check 的正例、反例、部分命中和零命中用例通过；
- 两个 Plan 语义检查逐项进入 verifier 报告；
- framework Plan 模板和 `framework/**` 保持不变。
