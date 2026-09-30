# plan 阶段 · 扩展要求（写之前读这一页）

> 读者：plan 阶段的作者。时机：动笔前读一遍，这一次的数据看知识任务（story-knowledge Skill，`--action plan`）；
> 门禁报错时回到「门禁会拦什么」。

设计里的知识判断（CU 的蓝图知识应用决定；非 CU 维护 Feature 契约里的 `knowledge_applications`）由你落到契约实体上：
下游不重做适用性与选型，它们读**实体上的 `must`** 与**实体上的 `pattern_roles`**——挂错或没挂，下游零注入。

## 一、读哪几样

| 来源 | 拿什么 |
|---|---|
| 知识任务 | 知识原文、本施工单位承接的适用判断与选型决定、设计引用的对象、缺口 |
| 本施工单位的 spec 与 `acceptance.yaml`（有才读） | 要履行的业务条件、验收与验证责任 |
| 蓝图里本单位承担的设计对象与 `story_details` | 专项设计与精确明细（配置、埋点、数据策略）——落到承担它的方法与实体上；埋点明细（`kind: event`）在 plan.md 用一张逐点表落实：表头含「统计点」「责任方法」，每个统计点每种结果一行，责任方法写契约里的「接口.方法」；这一次没有 plan.md 时，统计点、适用结果与验证方式写进承担它的方法 `description` 与相关验收条目 |

## 二、设计要证明它履行得了需求

从每条实际业务关系出发定实体、接口、状态与验证方式，然后自核：前一步的输出够不够后一步用；恢复路径能不能找回它需要的输入；
展示用的值与业务身份能不能各自履职；所有约束能不能同时成立。反向再看一遍：已经适用的业务步骤有没有漏掉该挂的义务。
改了共同边界、外部契约或设计取舍的，回 component-design 修订，不在 plan 里自行改写共同设计。

## 三、契约里怎么挂

**适用判断落成 `must`**，挂在真正做这件事的实体上，带出自的决定：

```yaml
interfaces:
  - name: RecordStore
    file: src/main/ets/data/RecordStore.ets
    methods:
      - name: finishProcess
        must:
          - rule: RET-01
            decision_id: knowledge-ret-01
            text: 处理完成时清除本次写入的临时记录
            verify: ut
```

- `must` 只挂五处：`data_models[].fields[]`、`interfaces[].methods[]`、`components[]` 及其 `state[]`、`resource_keys.<模块>.<分类>[]` 的资源条目。`files` 是原生授权文件清单（路径字符串），不承载义务。
- `text` 写本次要落实成什么，不复述规约原文；不是某条规约要求的业务规则写在实体自己的描述里，不挂 `must`。
- `verify` 按规约声明的执行体定：含「实机」写 `ut` / `device` / `both`；只有「模型」（或加「构建」）写 `review`；「人工」不挂 `must`。
- **选中模式的角色**写在真实承担它的 `components` / `interfaces` / `data_models` 实体上：`pattern_roles: [{pattern, role, decision_id}]`，
  `role` 取选型决定里的角色，实现文件取实体自己的 `file`。
- 设计用到的每个方法都在 `interfaces[].methods[]` 声明；`use-cases.yaml` 只引用契约里声明过的方法与 `acceptance.yaml` 里存在的验收编号。

## 四、跑哪条命令

`cd framework/harness && npx ts-node harness-runner.ts --phase plan --feature <Feature id>`。写完通读 `plan.md` 与契约，找错字、乱码与两处不一致。
报告回来之后按 [phase-closure.md](../../skills/story/reference/phase-closure.md)「闭环」那张表处置，改动属于哪一类写进 `plan/notes.md`。

## 五、门禁会拦什么

- `must` 挂在实体顶层、允许之外的集合或 `files` 上；`resource_keys` 不是「模块 → 分类 → 资源列表」的两层结构。
- `must.rule` 不在激活知识里；`must.text` 缺失；`verify` 不是四个取值之一或与执行体不符；`must.decision_id` 缺失、不是本单位承接的适用判断，或判断的单元与 `rule` 不同。
- 本单位承接的适用判断在契约里没有实体扛着。
- `pattern_roles` 指向的不是本单位承接的选型决定、模式与决定不符、角色不在选定角色里；选定的角色没有实体承担。
- 设计里的知识判断本身有缺口（漏判、原文已变、落点失效）：交设计负责方。
- 蓝图埋点明细里的统计点在逐点表里没有行；结果行没写责任方法，或它不是契约声明的方法。
- `use-cases.yaml` 引了 `acceptance.yaml` 里没有的验收编号；verifier 报告里没有本阶段判据的结论。
