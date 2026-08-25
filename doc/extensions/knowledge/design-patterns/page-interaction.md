---
name: page-interaction
kind: patterns
applies_when: 单个页面或组件内用户交互很多，且交互之间由业务结果驱动先后顺序（做完一件事自动进入下一个交互）
not_applies_when: 页面只有两三个独立按钮，各自触发一次动作后结束；交互之间没有先后依赖
triggers_usecase_spec: true
roles: [动作表, 动作枚举, 交互封装, 上下文, 页面组件]
optional_roles: []
coordinator_role: 交互封装
---

# 页面交互编排

把一个页面内的用户交互拆成**动作表**：每个动作做一件事，**业务逻辑执行完可以返回下一个动作**，
由状态机接着执行。交互顺序因此由业务结果决定，而不是散落在各个 `onClick` 里手工串。

---

# 上篇 · 适用与选型（读者：plan）

## 1. 解决什么问题

一个页面上用户交互非常多，且它们不是彼此独立的：确认之后要拉起验证，验证通过要提交，
提交结果决定是关闭面板还是留在原地重试。写在各自的回调里，就变成「回调里调下一个回调」——
页面的交互顺序没有一处能读到，改一步要顺着调用链翻。

动作表把交互与业务逻辑关联起来：**每个动作只写自己那一件事，把「接下来做什么」作为返回值交出去**。
页面的完整交互链在动作表里一眼可读。

## 2. 什么时候不该用

- 页面只有两三个独立按钮，点完就结束——套编排是徒增间接层；
- 交互之间没有先后依赖（各自独立触发各自的业务）；
- 只是页面内的纯 UI 状态切换（展开/收起、选中态），不涉及业务推进。

## 3. 契约投影

| 模式概念 | 投影到 |
|---|---|
| 交互管理器持有者（构建动作表并触发的类） | `contracts.yaml` 的 `files` / `interfaces`；`project_knowledge.pattern_applications[].instance` |
| 动作枚举（页内执行步骤） | `contracts.yaml` 的 `interfaces`——**不进** `use-cases.yaml` |
| 用户可触发的动作与它调用的业务方法 | `use-cases.yaml` 的 `ui_bindings.user_actions[].calls` |
| 用户视角的一次完整操作序列 | `use-cases.yaml` 的 `branches[].user_sequence` |
| 页面对外可见的业务状态（加载中、已提交、失败） | `use-cases.yaml` 的 `state_model.phases` |

边界同决策树：动作枚举是实现步骤，业务状态才是对外可观察的——两者不要混。

### 3.1 plan 应用步骤

1. 以一个页面或组件为单元，列出用户动作、业务结果驱动的后继动作与纯 UI 状态；独立按钮不纳入编排。
2. 定义唯一交互实例、动作枚举、上下文所有者、页面入口与所有用户等待点。
3. 对每个动作写“输入 → 单一职责 → 返回后继/停机 → 对外状态”，明确等待用户时由哪个回调恢复。
4. 把用户动作、完整操作序列和对外业务状态投影到 use-cases，把管理器与动作接口投影到 contracts。
5. 若调用后台决策树，以显式接口或业务状态交接；页面交互不直接进入对方内部节点。
6. 回查每个可点击入口都有动作，每个自动后继都可达，每个等待点都先停机再由新动作恢复。

---

# 下篇 · 结构与落地（读者：coding、review）

## 4. SDK 行为事实

- **动作可以驱动下一个动作**：`PageOperator` 的返回类型是 `void | A | Promise<A | void>`。
  返回动作标识（`A`）时，状态机接着执行那个动作；返回 `undefined` / 无返回值时**停机**。
- **等待用户就必须停机**：需要用户参与的地方（弹出面板等输入、等待确认、等待异步回调），
  当前动作必须**不返回后继**，让状态机停下；用户动作到来后由页面再次调用 `doOperator` 续跑。
  返回了后继就会继续往下执行——用户还没输入，流程已经跑过去了。
- **触发入口是 `doOperator`**：`PageInteractionManager.doOperator(actionName, ctx?)`，
  不传 `ctx` 时用构建时传入的那个。
- **上下文必须带 `operateSequence`**：`PageInteractionContext` 要求这个字段；
  `DefaultPageInteractionContext` 提供了默认实现，业务上下文继承它即可。
  **该字段运行时不被 SDK 读取或维护**——它是留给业务记录操作轨迹的位置，写不写、怎么写由业务决定。
- **`Interaction.nextNodes` 同样是声明字段**：运行时不校验，作用是让人读得出这个动作可能去向哪里。

## 5. 角色与文件落点

| 角色 | 职责 | 命名惯例 |
|---|---|---|
| 动作表 | 实现 `PageOperates<A, C>`，每个字段是一个交互动作 | `<页面>PageOperates` |
| 动作枚举 | 动作标识的字符串枚举（`A`） | 与动作表同文件，如 `<页面>Actions` |
| 交互封装 | 用 `PageInteractionBuilderV3` 构建管理器，对外暴露 `doOperator` | `<页面>PageInteraction` |
| 上下文 | 继承 `DefaultPageInteractionContext` 的业务上下文（`C`） | `<业务>Context` |
| 页面组件 | 只调交互封装的 `doOperator`，不写业务串联 | `<页面>Page` |

## 6. 结构骨架

```ets
import { Interaction, PageOperates, PageInteractionManager,
         PageInteractionBuilderV3, DefaultPageInteractionContext } from 'framework';

export class CheckoutContext extends DefaultPageInteractionContext {
  params: Map<string, string> = new Map<string, string>();
}

export enum CheckoutActions {
  CONFIRM = 'CONFIRM', VERIFY = 'VERIFY', SUBMIT = 'SUBMIT'
}

export class CheckoutPageOperates implements PageOperates<CheckoutActions, CheckoutContext> {
  [CheckoutActions.CONFIRM]: Interaction<CheckoutActions, CheckoutContext> = {
    operator: (ctx: CheckoutContext): CheckoutActions => CheckoutActions.VERIFY,
    nextNodes: [CheckoutActions.VERIFY]
  };

  [CheckoutActions.VERIFY]: Interaction<CheckoutActions, CheckoutContext> = {
    // 需要用户输入验证码：拉起面板后**不返回后继**，状态机在此停下
    operator: (ctx: CheckoutContext): void => { /* 拉起输入面板 */ },
    nextNodes: [CheckoutActions.SUBMIT]
  };

  [CheckoutActions.SUBMIT]: Interaction<CheckoutActions, CheckoutContext> = {
    operator: async (ctx: CheckoutContext): Promise<void> => { /* 提交并展示结果 */ },
    nextNodes: []
  };
}

export class CheckoutPageInteraction {
  private manager: PageInteractionManager<CheckoutActions, CheckoutContext>;

  constructor(ctx: CheckoutContext) {
    this.manager = new PageInteractionBuilderV3<CheckoutActions, CheckoutContext>()
      .interactions(new CheckoutPageOperates())
      .build(ctx);
  }

  doOperator(action: CheckoutActions): Promise<CheckoutActions> {
    return this.manager.doOperator(action);
  }
}
```

用户在面板里提交验证码后，由面板回调再次 `doOperator(CheckoutActions.SUBMIT)` 续跑。

## 7. 使用约定（人为纪律，SDK 不强制——review 逐条核查）

1. **页面动作必经 `doOperator`**：页面组件不直接调业务方法串流程，只发起动作；
   否则动作表里读到的链路与实际执行的不一致。
2. **有用户等待点的动作不返回后继**：这是最容易出错的一条——写成返回下一个动作，
   页面会在用户还没操作时跑完剩余步骤。
3. **`nextNodes` 与实际返回一致**（含等待点后由回调触发的那一个）。
4. **一个动作只做一件事**：需要「关面板 + 跳转 + 上报」的，拆成多个动作或交给对应封装，
   不在一个 operator 里串三件事。
5. **跳转交给跳转封装**：交互动作不直接操作导航栈。

## 8. 验证清单

| 阶段 | 完成判据 |
|---|---|
| plan | 知识决策表有页面单元、关键事实、采用理由与主体/契约锚点；机器交接有唯一实例名；动作与等待点已进入正式契约 |
| coding | 动作表覆盖枚举全部键；自动后继与 `nextNodes` 一致；等待用户的 operator 无返回值；最小编译通过 |
| review | 页面只通过 `doOperator` 发起业务动作；不存在回调间直接串联；跳转、上报和业务提交各有明确所有者 |
| ut | 每个用户入口、自动后继、停机点、回调恢复与失败停留有业务级用例；不对内部动作名作断言 |
| testing | 只验证分配到真机层的等待、恢复、重复点击、页面销毁与环境交互，并保留证据 |

## 9. 反模式

**在 `onClick` 里直接串多步**：点击回调里调业务、调完关面板、再跳转下一页。
本工程存量页面多是这种写法。它的代价在于：交互顺序只存在于调用链里，页面读不出完整流程；
要在中间插一步（比如加一次风险确认），得找到所有相关回调逐个改。
迁移方向是把每个回调变成一个动作、把「接下来做什么」从直接调用改成返回值。
