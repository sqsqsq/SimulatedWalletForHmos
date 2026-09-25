# design-patterns 交付 · 方案（已实施）

**交付物**：两份可以直接拿去做需求开发的设计模式文档——`decision-tree.md`（业务流程编排）
与 `page-interaction.md`（页面/组件内交互编排）。正文写满，不留占位，不含写作指引。

内容准确性由内网模型参照真实代码校正；本方案定的是形制。

## 一、内容依据：framework 的契约槽位

模式文档的骨架来自 `use-cases.yaml`——它由 plan 阶段按复杂度条件产出
（`framework/skills/feature/plan/SKILL.md:65`，schema 见
`framework/profiles/hmos-app/skills/business-ut/templates/use-cases-schema.md`），
每个字段都挂着 harness 规则：

| 字段 | 是什么 | 谁核 |
|---|---|---|
| `coordinator` / `coordinator_file` | 业务编排的承载对象与文件 | `check-coding : named_business_handler` |
| `state_model.phases` | 对外发布的阶段枚举（首元素 `Idle`） | `check-ut : usecase_spec_schema` |
| `branches[].user_sequence` / `expected_phase_seq` | 每条分支怎么走、经过哪些阶段 | `check-ut : branch_coverage_full` |
| `ui_bindings.user_actions[].calls` | UI 事件 → 业务入口，**必须是命名函数** | `check-coding : named_business_handler` |
| `data_boundaries[]` | 编排依赖的外部数据源 | `check-ut : boundary_matches_contracts` |
| `branches[].linked_acceptance` | 这条分支为什么存在 | `check-ut` AC 覆盖 |

**模式文档要做的事，是把自己的概念钉到这些槽位上。** 这部分不需要 SDK 知识，
也是内网校正内容时不会动的部分——类名会变，「决策点枚举就是 `state_model.phases`」不会变。

## 二、形制

三条硬性质：

| # | 性质 |
|---|---|
| 1 | 每一节都有一个具名的阶段消费者（plan 或 coding） |
| 2 | 每条主张落到一个已有载体：`use-cases.yaml` 字段、某条 harness 规则、或代码里一个看得见的位置 |
| 3 | 不留 `<待补充>`，不留写作指引块 |

两份文档同构，七节：

```
---
name: <id>
applies_when:          <编排单元的结构特征信号，能从 spec.md / acceptance.yaml 的语句直接判断>
not_applies_when:      <反信号，与 applies_when 同等权重>
triggers_usecase_spec: [<本模式的典型 UseCase 复杂度条件编号；允许与另一模式交集>]
---

# 上篇 · 适用与选型     （读者：plan）
1. 它解决什么问题        力量冲突一段 + 「不用它会烂成什么形状」的具体描述
2. 什么时候不该用        反信号清单
3. 契约投影              概念 ↔ use-cases.yaml 字段对照表

# 下篇 · 结构与落地     （读者：coding）
4. 角色与文件落点        表：角色 / 一句话职责 / 文件位置与命名
5. 结构骨架              ArkTS 骨架，扩展点空着，标「示意非模板」
6. 不变量                表：不变量 / 违反时的表现 / 在哪看
7. 反模式                形状级，每条配「为什么会这么写」与「改成什么」
```

plan 只读上篇、coding 只读下篇：选与用分离，编码期不重做选型。

`applies_when` / `not_applies_when` 描述的是**编排单元的结构特征**（分支形态、等待形态、
共享状态形态），禁止业务类别式写法（「支付类需求用决策树」）——文档是可复用的模式知识，
实例化只发生在具体需求的 use_case 条目里；正文一切示例标「示意非模板」。

### 2.1 选型单位与路由：按编排单元，不按需求

**模式是设计模式，不是需求本身。** 选型不发生在「这个需求用什么模式」上——
一个需求里可能只有部分功能适用某模式，也可能命中多个模式。选型单位是**编排单元**：
framework 里现成的单元就是 `use-cases.yaml > use_cases[]` 的条目，一个条目一个
`coordinator`。由此：

- 一个需求 **0..n 个模式实例**；零命中正常（模式是工具，不是过关项）；
- 同一模式可以**多实例**——两条独立流程就是两棵树、两个 use_case 条目；
- 同一单元可以**两模式叠加**：决策树管流程走向（`coordinator` / `state_model` /
  `branches`），页面交互管该流程的 UI 侧触发与等待（`ui_bindings`），
  投影到**同一个 use_case 条目的不同字段组**；衔接点是
  `ui_bindings.user_actions[].calls` 指向交互门面、门面的某个交互项驱动流程入口。

路由信号取自 UseCase 复杂度四条件（`framework/skills/reference/plan-workflow-detail.md:44`）：

| framework 条件 | 典型信号指向 |
|---|---|
| ② 多步云侧调用（一个动作触发 ≥2 次独立请求且顺序受前次结果影响） | decision-tree |
| ③ 存在回滚 / 补偿分支 | decision-tree |
| ① 多 UI 节点共享状态（≥2 页面/组件订阅同一业务状态且互相渲染依赖） | page-interaction |
| ④ 多路人机交互（≥2 次真实用户输入） | page-interaction |

四条件是**特征信号，不是分派表**：一个单元可以同时亮多个信号（决策树流程完全可能
同时命中④），满足条件也不等于必须套模式。保留的构造性质是**单向**的：
凡有模式实例，该单元必然满足四条件之一 → 必有 use_case 条目可承载它的契约投影
——「有模式实例却没有契约落点」按构造不存在。

### 2.2 契约投影写成概念 ↔ 字段的对照

`design-patterns/README.md:4` 立了「知识只答『模式是什么』，不答『谁在哪个阶段怎么用』」。
所以投影表写「本模式说的『决策点枚举』，就是 `state_model.phases`」，**不写阶段动词**；
谁在哪个阶段去填它，由 hook 说。判据：

- **禁止阶段坐标**——`spec §7`、story 章节号、评审环节序号，这些随流程编排变动；
- **允许契约字段坐标**——`use-cases.yaml > branches`，这是 framework 的机器契约，
  比阶段稳定，且本就是「模式是什么」的一部分。

## 三、两份文档的正文方向

命名用领域中性示意名，不含外部工程路径与演示业务专名。

### 3.1 decision-tree.md — 业务流程编排

- **解决什么**：多步流程，下一步取决于上一步的结果。力量冲突——**流程要能持续长出分支
  × 每个决策点要能被单独测试和复用**。不用它会烂成：一个几百行的 `async doXxx()`，
  五层嵌套 if，错误处理散在每层，加一条「风控拦截」要动三处，且没有任何地方回答得了
  「这次实际走了哪条路」。
- **不该用**：步数 ≤3 且无分支；分支只在末端做一次二选一；规则要由运营侧运行时下发
  （决策点在装配期固定，套它反而多一层）。
- **契约投影**：树的持有者 → `coordinator` / `coordinator_file`；决策点与终点枚举 →
  `state_model.phases`（首元素 `Idle`）；一条完整路径 → `branches[]`，其
  `expected_phase_seq` 即该路径经过的节点序列；树内取数 → `data_boundaries[]`；
  这条路径为什么存在 → `linked_acceptance`。
- **角色**：`XxxFlow`（持树、暴露入口，落 `domain/flow/`）、`XxxNodes`（每个决策点 /
  执行点一个函数）、`XxxContext`（流程内传递的数据）、`XxxPage`（只绘制与转调）。
  取数一律经 `data/repository`，节点里不 new repository。
- **不变量**：枚举值与 Operates 字段名逐字相同，否则该节点永不执行**且不报错**；
  决策点只判定不执行；节点函数 `async`、调用处必须 `await`；节点只靠返回值决定下一步、
  不直接调兄弟节点；`state_model.phases` 与枚举一一对应。
- **反模式**：手写 switch 重实现引擎；嵌套 if 假装成树；节点里直接落库；漏 `await`
  把 Promise 当节点名往下传。
- **与 page-interaction 叠加**：流程需要 UI 侧触发与等待时，两模式落同一个 use_case
  条目的不同字段组——树管 `coordinator` / `state_model` / `branches`，交互管
  `ui_bindings`；衔接点是交互门面的某个交互项驱动流程入口。

### 3.2 page-interaction.md — 页面/组件内交互编排

- **解决什么**：一个页面上多个交互彼此有先后与等待关系（点 A 要等用户输 B，
  B 成功自动触发 C）。力量冲突——**每个交互只想关心自己的上下游 × 整条链路又要能被完整看到**。
  不用它会烂成：状态由几个布尔标志组合表达，「现在处于什么状态、下一步会发生什么」
  只存在于程序员脑子里。
- **不该用**：一问一答、无等待态、无自动串联；纯展示页；页面之间的跳转（那是路由的事，
  不是交互编排）。
- **契约投影**：交互门面 → `coordinator`；交互项枚举 → `state_model.phases`；
  每个 UI 上的可触发动作 → `ui_bindings.user_actions[]`（`calls` 指门面方法）；
  页面订阅的状态 → `ui_bindings.subscribes`；一条交互序列 → `branches[].user_sequence`。
- **三角色，文件切分即职责切分**：`XxxPage` 只做绘制与初始化、`onClick` 只转调门面方法、
  零业务逻辑；`XxxInteractions` = 动作枚举 + Operates + 门面类；`XxxViewModel` 纯数据
  class 与枚举。
- **不变量**：门面方法名 = `ui_bindings.user_actions[].calls`；Page 里零 repository 调用；
  交互项只声明上下游、不直接调兄弟；枚举值 ≡ Operates 字段名；
  等待态必须是显式的一个交互项，不是一个布尔标志。
- **反模式**：编排泄漏进 `aboutToAppear`；布尔标志组合表达状态；if/else 手动分派；漏 `await`。
- **与 decision-tree 叠加**：交互背后是一条多步流程时，门面的交互项只驱动流程入口、
  不自己长成流程——流程走向归树（`state_model` / `branches`），触发与等待归交互
  （`ui_bindings`），同一个 use_case 条目内分工。

## 四、落地：各文件的目标态

| 文件 | 目标态 |
|---|---|
| `knowledge/design-patterns/decision-tree.md` | 按 §二 骨架的成品，正文按 §3.1 |
| `knowledge/design-patterns/page-interaction.md` | 按 §二 骨架的成品，正文按 §3.2 |
| `knowledge/design-patterns/README.md` | 路由表按 §2.1：按编排单元路由、四条件为特征信号、可多命中/零命中/叠加；阶段分工表 plan 一格指向契约投影节；不承载写作规范（成品自身即范本） |
| `hooks/plan/on_context_load.md` | 指引落到：先把需求拆成编排单元，逐单元按路由表判断；每个命中实例按契约投影填进对应 use_case 条目 |
| `hooks/coding/on_context_load.md` | 指引落到：按 `state_model` 定义枚举、按 `branches` 实现分支、逐条核对不变量表 |
| `test/story/tests/test_export_delivery_patch.py` | `keep` 列表与 `manifest.yaml` 的 knowledge 声明一致 |
| `test/story/tests/test_knowledge_purity.py` | 断言见下 |

`DesignPatternsTest` 的断言：

- 两份文档不含 `✍` / `待补充` / `写作指引`；
- frontmatter 四字段齐备（`FRONTMATTER_KEYS` 的严格相等断言只作用于 `constraints/`，
  这条差异在测试里写明）；
- `triggers_usecase_spec` 取值落在四条件集合内且非空（允许两模式交集——它是特征信号，
  不是分派表）；
- README 路由表含「按编排单元路由、可多命中 / 零命中」的说明；
- 两份文档含契约投影表，表中出现的字段名在 use-cases schema 里真实存在；
- 投影表不含阶段动词（`plan 须` / `coding 须`）与阶段坐标（沿用现有 `CONSUMER_COORDS`）；
- 不变量表每行三列齐；
- 两份文档不含外部工程路径与演示业务专名。

## 五、验证

1. `python -m unittest discover -s test/story/tests` 全绿；
2. `cd framework/harness && npx ts-node harness-runner.ts --phase extensions` PASS；
3. `python test/story/scripts/export_delivery_patch.py --verify` 交付边界自洽；
4. **可用性自检**：拿 `02-Feature/FinancialCard/` 现成的手写编排逐条比对新文档，
   每一处形态都应能被某条不变量或反模式**直接命中**；命不中说明文档还缺东西。
   只比对，不改应用代码。

   首轮比对**命中 1/6**，据此补强后 6/6：

   | 现存形态 | 补进文档的 |
   |---|---|
   | `OpenCardFlow` 的 `phase` 直接赋值散在 8 个方法，既无节点表也无 `switch` | 反模式「迁移散落在各方法里」 |
   | `OpenCardFlow` 字段直接 `BankCardRepository.getInstance()` | 不变量的「在哪看」从只看 `new` 扩到 `getInstance()` |
   | `popOpenCardStackAndNavigate` 在编排对象里做跳转 | 不变量「编排对象里不做页面跳转」+ 反模式「持树者兼管页面跳转」 |
   | `SmsVerifySheet.submitCode` 在 `onClick` 里串「调业务 → 关面板 → 跳转」 | 反模式「事件回调里串多步」（原文只抓 `aboutToAppear`） |
   | `countdownSec: number` 表达等待态 | 不变量措辞从「布尔标志」扩到「散落的标量视图态」 |
   | `BankCardListSheet` 等页面直接持有仓储 | 不变量「页面里零仓储调用」（原文已命中） |

## 六、不做

- 不新建「形制说明 / 写作标准」类文档——形制由两份成品自身承载；
- 不恢复 `state-machine.md`；
- 不改应用代码（`OpenCardFlow` 只作自检取材）；
- 不提交；
- **不补 plan/coding 阶段的门禁**（另开一条线）：两个 hook 的 `on_context_load`
  fragment 只进 `ai-prompt.md`，读者是 verifier；framework 的 plan/coding SKILL 对
  `doc/extensions/hooks` 零引用。所以 hook 里的 BLOCKER **能到达 verifier**
  （verifier verdict=PASS 是闭环四条件之一，故它不是空话），
  但**到不了撰写期**——写 plan/coding 产物的那一刻，没有任何东西提示它去读路由表。
  补法是实例侧 `phase_rules_overlays.plan/.coding`，`semantic_checks` 由 verifier 消费、
  零脚本改动、不动 `framework/`（`doc/extensions/rules/spec-rules.overlay.yaml` 是现成先例）。
  候选检查：`plan_pattern_selection_projected`（`use-cases.yaml` 的每个 use_case 条目
  须声明命中的模式实例或零命中的理由，命中的须投影字段齐备）、
  `coding_pattern_invariants_held`（对每个模式实例：枚举与 `state_model.phases` 一一对应、
  `calls` 在代码中是命名函数、不变量表逐条成立）。
