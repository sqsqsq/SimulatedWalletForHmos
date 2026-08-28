# plan 阶段 · 扩展要求（写之前读这一页）

本阶段是设计模式**唯一的选型点**，也是全链**唯一的冻结点**：coding / review / ut / testing
读的不是知识目录，而是你在这里冻结的结果。冻结缺失下游**什么都收不到**——不是回退到全量。

## 一、读哪几个文件

| 文件 | 拿什么 |
|---|---|
| `doc/extensions/skills/story/templates/plan-sections.md` | 「知识决策（设计输入）」章骨架 + 冻结块的写法与一个中性示例 |
| 上游 `spec/spec.md` 的 §10、§11 | §10 的每条命中条目在本阶段都要变成有落点的义务；§11 的候选是本阶段选型的出发点 |
| `doc/extensions/manifest.yaml` 的 `provides.knowledge` 里**命中**的那几个文件 | 条目的处置列与该域落法附注（要求的正文）、候选模式的选型篇。未命中的域不必读 |

## 二、产出形态

**① `plan.md` 里必须有一章「知识决策（设计输入）」，且排在第一个设计章之前。**

位置就是语义：排在设计之后，它只能是「我做完了，顺便声明用过哪些知识」；排在设计之前，
后面每一章才可能按它展开——数据模型因此多一个字段，接口因此多一个方法。
**这正是「应用」与「声明」的差别。** 章内三节：设计模式选型 / 规约义务 / 项目知识影响。

**② `plan/contracts.yaml` 里写 `knowledge_freeze`**，形态见 `plan-sections.md`。要点：

- 一条目一行，不要一行塞多条。
- `obligation` 写**本次要落实成什么**（可实施的设计结论），不是复述规约原文。
- `landing` 是它在契约里的承载实体，语法 `data_models.<模型>[.<字段>]` /
  `interfaces.<类>[.<方法>]` / `components.<组件>[.<状态>]` / `resource_keys.<键>` /
  `files.<路径>` 等；引用的东西必须在**同一份 contracts.yaml 里真实存在**（门禁按结构解析，不是文本包含）。
- `criterion` 指向 `acceptance.yaml` 的一条验收条目——那条目**就是**这条义务在四阶段的验证要求，
  不另建第二份分派表（coding 看 `landing`、review 看 `review_focus`、ut/testing 看 `ut_layer`）。
- 模式选了写 `instance` 与**每个角色的承载实体**；不选写理由。**不选不是缺陷，不写理由才是。**

**判据一句话：冻结结果必须能指回方案里的实际落点，而那个落点是契约里的一个实体。**
写不出承载字段的义务，到编码那里等于不存在。

## 三、跑哪条命令

```
cd framework/harness && npx ts-node harness-runner.ts --phase plan --feature <需求名>
```

## 四、门禁会拦什么

- 缺「知识决策（设计输入）」章，或它排在第一个设计章之后。
- `contracts.yaml` 缺 `knowledge_freeze`。
- spec §10 的编号集与冻结的义务编号集对不上——少一条就是知识在设计阶段丢了。
- 缺 `obligation`，或缺 `landing`（处置标「（评审动作）」的条目除外）。
- `landing` 解析不到契约实体（模型不存在、字段不存在、类里没那个方法）。
- `anchor` 在 `plan.md` 里找不到，或**指回「知识决策」章自己**——那是声明，不是落点。
- `criterion` 在 `acceptance.yaml` 里不存在，或那条的 `knowledge_rule` 与本条对不上。
- `step` 在验收条目或 use-cases 里定位不到，或 `step` 与 `criterion` 填成了同一个值
  （`step` 是业务步骤，`criterion` 是验收编号，拿验收编号当步骤等于这条义务在流程里没落点）。
- 模式不在册；`selected: true` 却缺 `instance`；`roles` 键集与该模式声明的角色集不一致；
  某个角色的值在契约里找不到对应实体。
- `obligation` 是规约原文的复制或子串。
- `plan.md` 义务表的落点与 contracts 的 `landing` 对不上——md 与 yaml 是同一份冻结的两次渲染。

报错会**一次列全**，每条都写「缺什么 / 写到哪 / 怎么写」。不需要读 `post_check.mjs` 反推判据。
另：spec 全部单元都写「无候选」时，本阶段不应凭空冻结出一个模式——那说明选型依据不是从需求来的，真需要时回 spec 补候选登记。
