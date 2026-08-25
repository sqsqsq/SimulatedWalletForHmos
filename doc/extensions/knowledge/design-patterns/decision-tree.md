---
name: decision-tree
kind: patterns
applies_when: 业务流程有多个分支，且每个分支自身是一段复杂功能（多步云侧调用、回滚或补偿分支），用 if/else 串会难以维护
not_applies_when: 单一线性流程；分支只有一两步；分支条件是纯数据校验而非业务阶段推进
triggers_usecase_spec: true
roles: [节点表, 步骤枚举, 上下文, 构建与启动]
optional_roles: [页面跳转]
coordinator_role: 构建与启动
---

# 流程分支编排（决策树）

把一段复杂业务流程拆成**节点表**：每个节点做一件事，并返回下一个要执行的节点。
分支不再写成嵌套 if/else，而是节点各自决定去向；状态机负责按返回值连续推进，直到某个节点不再返回后继。

---

# 上篇 · 适用与选型（读者：plan）

## 1. 解决什么问题

一段流程有多个分支，每个分支自身是复杂功能（要调云侧、要落库、要处理失败与补偿）。
写成 if/else 时，分支条件、分支内的多步逻辑、失败回退三者缠在同一个方法里：加一个分支要读懂全部，
改一步要担心影响别的分支。

节点表把它们拆开：**一个节点一件事，节点之间只通过「返回哪个节点」和「共享的上下文对象」耦合**。
读一个节点不需要读别的节点；加一条分支是加一个节点加一条返回，不动既有节点。

## 2. 什么时候不该用

- 流程是线性的（第一步、第二步、第三步，没有分叉）——直接写方法更好读；
- 分支只有一两步（判断完就返回结果）——套节点表是给读者增加跳转成本；
- 分支条件是纯数据校验（字段为空、格式不对）——那属于校验，不是流程分支。

## 3. 契约投影

选型结论要落到 plan 的既有契约字段里，不自造字段：

| 模式概念 | 投影到 |
|---|---|
| 树的持有者（构建并启动树的类） | `contracts.yaml` 的 `files` / `interfaces`；`project_knowledge.pattern_applications[].instance` |
| 节点枚举（内部执行步骤） | `contracts.yaml` 的 `interfaces`——**不进** `use-cases.yaml` |
| 用户或 UI 能观察到的业务状态 | `use-cases.yaml` 的 `state_model.phases` |
| 一条完整路径（用户视角的一次业务往返） | `use-cases.yaml` 的 `branches[].user_sequence` |
| 节点里取数、落库的边界 | `use-cases.yaml` 的 `data_boundaries[]` |

**边界判据**：`state_model.phases` 是对外业务状态——UI 订阅它、业务用例断言它。
决策树的内部节点（如「构造指令」「校验写入」）不是业务状态，投影进去会让业务用例断言实现细节，
之后重构树结构就被误判成业务行为变化。只有某个节点本来就是对外发布的状态时，两处才同时出现。

### 3.1 plan 应用步骤

1. 以一个有独立业务目标和明确起止的流程段为单位，逐条写出命中信号与反证；不适用就登记零命中。
2. 为每个命中单元定义唯一实例名、树持有者、上下文所有者、入口节点和所有终点。
3. 把每条业务分支写成“前置 → 节点序列 → 对外状态/结果 → 失败处置”，先证明分支完整，再规划文件。
4. 将内部节点与对外业务状态分开投影到 contracts/use-cases，避免测试锁死实现步骤。
5. 若与页面交互编排组合，按 README 的组合合同声明交接接口、用户等待点与失败收敛者。
6. 回查每个 P0/P1 场景都能进入一条路径，每个节点都有可达入口，每条路径都有明确终点。

---

# 下篇 · 结构与落地（读者：coding、review）

## 4. SDK 行为事实

以下逐条是编排 SDK 的**实际运行时行为**（依据其类型声明与实现），不是使用建议：

- **状态机连续推进**：`BaseStateMachine.fireEvents` 是循环——节点返回下一个事件，它就接着执行下一个节点，
  直到某次返回 `undefined` / `null` 才停机返回。
- **三类节点，由字段决定**：`DecisionTreeNode` 有 `root` / `nonLeaf` / `leaf` 三个可选字段，
  运行时按 `root` → `nonLeaf` → `leaf` 的顺序取第一个存在的来执行。`root` 与 `nonLeaf` 是
  `NoLeafNode`（返回下一个节点），`leaf` 是 `LeafNode`（返回 `void`，执行完流程停机）。
- **入口靠 `root` 找**：`DecisionTree.start(ctx)` 遍历节点表，取第一个带 `root` 字段的节点作起点。
  节点表里应当**只有一个** `root`。
- **`nextNodes` 是声明字段，运行时不读**：`DecisionTreeNode.nextNodes` 存在于类型里，
  但状态机推进只看节点函数的返回值，不校验返回值是否在 `nextNodes` 中。
  它的作用是**给人和工具看的可达性声明**，一致性靠约定（§7）维持，不是 SDK 保证。
- **上下文是唯一跨节点通道**：节点签名是 `(ctx, preNode?)`，`ctx` 由 `start` 传入并贯穿整棵树；
  `preNode` 是上一个节点的标识，可用于失败时说明「停在哪一步」。

## 5. 角色与文件落点

一个决策树实例通常由这几个角色组成，按职责分文件：

| 角色 | 职责 | 命名惯例 |
|---|---|---|
| 节点表 | 实现 `DecisionTreeNodeOperates<E, C>`，每个字段是一个节点 | `<业务>DecisionOperates` |
| 步骤枚举 | 节点标识的字符串枚举（`E`） | 与节点表同文件，如 `<业务>Tasks` |
| 上下文 | 跨节点共享的数据载体（`C`） | `<业务>Context`；含页面交互时继承 `DefaultPageInteractionContext` |
| 构建与启动 | 用 `DecisionTreeBuilderV2` 构树并 `start` | `<业务>Entry` 或业务服务内的一个方法 |
| 页面跳转 | 与树分离的跳转封装 | `<业务>JumpManager` |

## 6. 结构骨架

```ets
import { DecisionTreeNode, DecisionTreeNodeOperates, DecisionTreeBuilderV2 } from 'framework';

export enum OrderTasks {
  START = 'START', PREPARE = 'PREPARE', SUBMIT = 'SUBMIT',
  SUCCEEDED = 'SUCCEEDED', FAILED = 'FAILED'
}

export interface OrderContext {
  prepared: boolean;
  submitSucceeded: boolean;
}

export class OrderDecisionOperates implements DecisionTreeNodeOperates<OrderTasks, OrderContext> {
  [OrderTasks.START]: DecisionTreeNode<OrderTasks, OrderContext> = {
    root: async (ctx: OrderContext): Promise<OrderTasks> => OrderTasks.PREPARE,
    nextNodes: [OrderTasks.PREPARE]
  };

  [OrderTasks.PREPARE]: DecisionTreeNode<OrderTasks, OrderContext> = {
    nonLeaf: async (ctx: OrderContext, preNode?: OrderTasks): Promise<OrderTasks> => {
      ctx.prepared = true;
      return OrderTasks.SUBMIT;
    },
    nextNodes: [OrderTasks.SUBMIT]
  };

  [OrderTasks.SUBMIT]: DecisionTreeNode<OrderTasks, OrderContext> = {
    nonLeaf: async (ctx: OrderContext, preNode?: OrderTasks): Promise<OrderTasks> => {
      return ctx.submitSucceeded ? OrderTasks.SUCCEEDED : OrderTasks.FAILED;
    },
    nextNodes: [OrderTasks.SUCCEEDED, OrderTasks.FAILED]
  };

  [OrderTasks.SUCCEEDED]: DecisionTreeNode<OrderTasks, OrderContext> = {
    leaf: async (ctx: OrderContext, preNode?: OrderTasks): Promise<void> => {
      // 成功终点：发布对外业务状态
    },
    nextNodes: []
  };

  [OrderTasks.FAILED]: DecisionTreeNode<OrderTasks, OrderContext> = {
    leaf: async (ctx: OrderContext, preNode?: OrderTasks): Promise<void> => {
      // 终点：记录失败发生在 preNode，不返回后继
    },
    nextNodes: []
  };
}

// 构建与启动
const tree = new DecisionTreeBuilderV2<OrderTasks, OrderContext>()
  .nodeOperates(new OrderDecisionOperates())
  .build();
await tree.start(ctx);
```

## 7. 使用约定（人为纪律，SDK 不强制——review 逐条核查）

1. **决策逻辑只在节点表内**：分支判断写在节点函数里，不在调用方再包一层 if/else 决定调哪个树。
2. **`nextNodes` 与实际返回一致**：节点实际可能返回的后继，都要列进它的 `nextNodes`；
   列了却永不返回的要删掉。SDK 不校验，读者与工具全靠它理解流程。
3. **每棵树只有一个 `root`**：多个 `root` 时入口取决于字段遍历顺序，等于把入口交给偶然。
4. **终点必须是 `leaf`**：流程结束用 `leaf` 节点显式收尾，不靠 `nonLeaf` 返回空绕过类型。
5. **节点不做页面跳转**：跳转交给跳转封装，节点只推进业务状态——否则同一棵树无法在不同入口复用。
6. **节点不直接持仓储单例**：数据访问从 `ctx` 或构造参数进来，便于替换与测试。

## 8. 验证清单

| 阶段 | 完成判据 |
|---|---|
| plan | 知识决策表有适用单元、关键事实、采用理由与主体/契约锚点；机器交接有唯一实例名；节点不冒充业务状态；每条 P0/P1 分支有入口和终点 |
| coding | 节点表覆盖枚举全部键；唯一 root；每个实际返回值都在 `nextNodes`；终点是 leaf；最小编译通过 |
| review | 调用方无第二套 if/else 选路；节点不直接跳页面或持有仓储单例；SDK 行为事实与工程约定没有混写 |
| ut | 主路径、每个业务分支、停止/恢复与失败结果有业务级用例；不对内部节点名和文件结构作断言 |
| testing | 只验证已分配到真机层的分支、恢复与环境交互；纯结构行为按 Plan 证据 SKIP |

## 9. 反模式

**把流程摊在一个类的多个方法里，各自赋值 phase**——本工程存量的开卡流程编排就是这种形态：
单例持有一个 `@Observed` 状态对象，八个方法各自给 `state.phase` 赋值，同时还直接持有仓储单例、
在编排对象里做页面跳转。它的问题不是「没用框架」，而是：流程的完整走向不在任何一处可读，
要把八个方法读完才知道谁接谁；任何一个方法都能改 phase，出错时无法定位是谁改的。
迁移方向是把每个方法变成一个节点、把「下一步」从赋值改成返回值。
