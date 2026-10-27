# 02 · design-patterns 重启方案（决策树 + 页面交互管理）

> 读者：本方案的评审者与实施者。历史失败的完整归因见 `test/story/EVOLUTION.md:32-55` 与
> `plan/2026-08-13-修正与能力增强/` 的交付与盲测记录。
> 已吸收 [06-Codex-方案检视意见](06-Codex-方案检视意见.md) 的 B3/B7/M4（裁决记录见 00 §6）。

## 1. 历史教训 → 本轮解法

| 当年教训 | 本轮解法 |
|---|---|
| ⑴ 载体 SDK 在工程里不存在，盲测全是必然失败的假洞 | SDK 以 **har 包**引入 story 工程（用户裁决），编译通过本身成为验收项 |
| ⑵ 按口述编了一套接口，编造物反噬设计 | demo 仓现有**真实 SDK**（API 与当年口述形态一致），一切接口照 `Index.ets` 导出面写;**运行时行为照源码写**（§3），不许再编 |
| ⑶ 没想清「模式知识由什么构成」就写正文 | 沿用已裁决的三层构成：**识别 + 分解 + 落位**，SDK 实现细节不进知识正文 |
| ⑷ 连续三轮补一处不停 | 方案先行 + 盲测重演设计前置，验收标准与交付对象一致 |

盲测已验证的资产直接继承：**plan 侧「契约投影」有效**（投影边界本轮精确化，见 §4）；
检查名沿用当年拟定的 `plan_pattern_selection_projected` / `coding_pattern_invariants_held`。

## 2. 载体：编排 SDK 的 HAR 集成契约

**源**：`E:\Project\AIDefectHelpler\demo\sdk\Framework`（hvigor 静态库模块，包名 `framework`，
`Index.ets` 导出三组符号：StateMachine / DecisionTree / PageInteraction 系）。

实施前一次性锁定（本表即契约，实施不再自行决定）：

| 项 | 契约 |
|---|---|
| 构建 | 在 demo/sdk 工程执行 hvigor 模块构建产出 `framework.har`（构建命令与工具链版本随构建记录留档） |
| 仓内落位 | story 工程根 `libs/framework-1.0.0.har`（新建 `libs/` 目录，版本号随 SDK `oh-package.json5` 的 version） |
| 首个消费模块 | 实施「命中决策树」案例的业务模块（按案例需求单落点定，如 `02-Feature/FinancialCard`）；其 `oh-package.json5` dependencies 写 `"framework": "file:../../libs/framework-1.0.0.har"`（相对深度按模块层级） |
| 来源追溯 | 记录源仓（AIDefectHelpler demo）提交标识与 har 的 SHA-256，随 05 维护协议（ADAPTATION §6）登记 |
| 二进制入库 | 入库（样板载体，评测环境不依赖跨仓构建；体积小） |
| 更新流程 | SDK 源变更 → 重构建 har → 更新 libs 与 SHA 记录 → 模式知识同步核对 |
| 授权 | demo 与本仓同属用户，内部复制由用户确认（SDK license 字段为空，不自行推断） |
| 命名消歧 | oh 包名保持 `framework`（改名会使样板与 demo/内网实例的 `import from 'framework'` 失真）；文档层统一称「编排 SDK」，两份模式文档头注一句声明与仓库根 `framework/`（工作流框架）无关 |

**连带回灌**（同批完成，不留窗口期）：`knowledge/codebase-facts.md` §6 依赖变更面登记该依赖；
har 是依赖不是模块，**不进 `architecture.outer_layers`**。

## 3. 知识载体与形制

`doc/extensions/knowledge/design-patterns/`：`README.md`（路由表，信号 → `pattern_id`）+
两份模式文档。`pattern_id` = frontmatter `name`（`decision-tree` / `page-interaction`），
全链（信号登记、应用表、overlay）引用同一 id。frontmatter 四字段：
`name` / `applies_when` / `not_applies_when` / `triggers_usecase_spec`。

**适用场景以用户口述为基准**（写进 `applies_when`，不自行推断）：

- **决策树**：复杂业务**分支流程**——每个分支都是复杂功能，if/else 难以维护时，用决策树做流程分支编排；
- **页面交互管理**：页面上用户交互非常多时，提供编排能力，把**页面交互与业务逻辑关联**，业务逻辑可驱动下一个交互（demo 佐证：`PayDecisionOperates` 业务节点内调 `PageInteraction.doOperator` 驱动下一交互；ctx 统一继承 `DefaultPageInteractionContext`）。

**正文形制（上下篇 + 行为事实）**：

```
# 上篇 · 适用与选型（读者：plan）
1 解决什么问题（applies_when 展开 + demo 实例指认）
2 什么时候不该用（not_applies_when）
3 契约投影（边界见 §4：对外状态 → use-cases；内部结构 → contracts + 应用表）
# 下篇 · 结构与落地（读者：coding）
4 SDK 行为事实（只写源码可证的运行时行为，见下）
5 角色与文件落点（XxxDecisionOperates / XxxPageOperates / XxxPageInteraction 包装器 /
  XxxJumpManager / XxxEventBus / XxxEntry —— 照 demo 五个实例域的惯例）
6 结构骨架（照 SDK 真实 API：节点表实现 DecisionTreeNodeOperates，Builder 构建，
  ctx 继承 DefaultPageInteractionContext；业务节点内经 doOperator 驱动下一交互）
7 使用约定（人为纪律，非 SDK 强制——review 核查对象，见 §4）
8 反模式（真实反例指认：存量 OpenCardFlow 手写形态——phase 赋值散落 8 方法、
  编排对象直接持仓储、编排里做页面跳转）
```

**「SDK 行为事实」节的核心内容**（逐条可溯源到源码，杜绝教训 ⑵ 复发）：

- `BaseStateMachine.fireEvents` 是 while 循环：operator/节点返回下一事件就**连续执行**，
  返回 `undefined/null` 才停机（`StateMachine.ets:13-23`）；
- **等待点语义**：有用户等待（弹窗、输入、异步确认）时，当前节点必须返回 `undefined`
  让状态机停下，用户动作到来后再次 `doOperator`/`fireEvents` 续跑——否则会静默跑穿等待态
  （当年盲测 B 的失败根因，如今有了源码依据）；
- `DecisionTreeNode.nextNodes` 与 `PageInteractionContext.operateSequence` 是**声明字段**，
  运行时不读取、不校验、不维护——它们的一致性是**使用约定**（§7），不是 SDK 行为；
- demo 调用点分三类标注：**正例**（推荐照抄的形态）/ **反例**（demo 中存在但不推荐）/
  **仅证明 API 可用**（不构成形态背书）——不把 demo 全部默认成最佳实践。

## 4. 三阶段描述与契约投影边界

| 阶段 | 读什么 | 做什么 | 产物落点 |
|---|---|---|---|
| **plan** | spec 信号登记 + README 路由表 + 命中模式**上篇** | 最终选型，产出**模式应用表**（形态见 03 §3.3）+ 契约投影 | plan 产物 |
| **coding** | 应用表 + 命中模式**下篇** | 按结构骨架落码：真实 import `framework` 包，编译与 UT 必过 | 源码 + UT |
| **review** | 应用表 + 下篇**使用约定** | 按约定逐条核查（可判条目：决策逻辑越出节点表、页面动作绕过 doOperator、nextNodes 声明与节点实际返回不符、等待点未停机） | review 报告核查结论 |

**契约投影边界（当年有效结论的精确化）**：当年盲测验证的投影对象（OpenCardFlow 的
phase）本就是 `@Observed` 对外状态，投影正确；新 SDK 引入了**内部节点**这一新形态，边界随之明确：

- `use-cases.yaml` 的 `state_model.phases` 只装**对外可观察的业务状态**（UI 订阅、UT 断言面）；
- 决策树内部节点（如 `BUILD_COMMAND`）、动作枚举、Builder/Manager 类型与文件落点进
  `contracts.yaml` 的 `files/interfaces` 与 plan 应用表；
- 仅当某节点本来就是对外发布的业务状态时，才同时出现在 `phases`；
- overlay 验这条语义边界，不要求每个模式节点在 use-case 中一一出现。

## 5. 注入与门禁

与 03 方案共用一条链（03 是机制真源，此处只列本议题的挂载）：

- **首跳**：spec 宿主扩展产物的信号登记（03 §3.3）——spec 是 story 有可靠撰写期注入的唯一阶段；
- **辅通路**：共享指路件 `hooks/design-pattern-application.md`（与 `constraint-application.md` 同款「只指路」形制），manifest 挂 plan/coding/review 三阶段 `on_context_load`；
- **overlay**：`plan_pattern_selection_projected`（应用表存在且与信号/投影一致）、`coding_pattern_invariants_held`（落码违反使用约定即 FAIL）、review 核查项；均自带 SKIP 条件；
- **不重建 `hooks/coding/`**——coding 阶段的知识消费走共享指路件与 overlay（历史裁决）；「声明了消费方就必须有真实挂载」由 `test_constraint_consumption.py` 纪律看护。

## 6. 适配指南联动

ADAPTATION.md「设计模式适配」节：目标工程由适配 AI 实扫其真实 SDK（内网钱包为真实决策树/页面交互框架）**整篇重写两份模式文档的下篇与实例指认**（含「SDK 行为事实」按真实 SDK 源码重验），上篇的选型方法论与投影边界跨工程稳定；`confirmed` 协议与画像同款。规则与脚本零改。

## 7. 验收设计

- **盲测重演**（对当年三场 A/B/C 的正向复验）：A' coding 消费决策树下篇——har 载体在工程内，编译通过 + 节点表形态正确为过；B' 有等待态场景——按「等待点语义」落码，不再跑穿等待态；C' plan 消费上篇——应用表与投影齐整。
- **机械看护**（进 `test_knowledge_purity.py` 新增 `DesignPatternsTest`）：模式文档引用的 SDK 符号必须在 `Index.ets` 导出面真实存在；「SDK 行为事实」节引用的源码行为有对应源文件可查；文件落点惯例引用的 demo 路径可 glob 命中或声明为形态描述；frontmatter 四字段齐全；manifest/挂载对齐。
- **消费链评测**：在 test/story 的全流程案例承载（该域已有 `first-release` 跑到 coding/ut 的先例）;「知识消费链(constraints + design-patterns)属于本域被测对象」**显式写进 test/story 的 AGENTS/TEST 口径**,作为域文档正式修订项随本方案交用户批准——不暗改域 SSOT。
