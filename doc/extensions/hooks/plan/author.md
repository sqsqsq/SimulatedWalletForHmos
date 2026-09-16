# plan 阶段 · 扩展要求（写之前读这一页）

> **推进不逐段问**：门禁报错怎么修、check 过了下一步做什么、进 harness 还是进 verifier——这些是义务不是选择题。停等点与两层授权边界的唯一定义，见[story SKILL.md「推进契约」](../../skills/story/SKILL.md#推进契约)。

本阶段是设计模式**唯一的选型点**，也是规约义务**唯一的落点**：下游不重做适用性与选型，它们读**你挂在契约实体上的 `must`** 与 `files` 的 `pattern` / `role`——挂错或没挂，下游零注入。

## 一、读哪几个文件

| 文件 | 拿什么 |
|---|---|
| 当前 `spec/spec.md`（含 §10、§11）、`AR/review.md` 与 `AR/story-src/review-disposition.json`（有才读） | 要履行的业务条件、验收与未决，人已表的态与评审回稿的处置——设计的前提，不是背景。§10 每条命中都要有实体扛着，强制力与验法两列定落点要什么证据；§11 的候选是选型的出发点 |
| `doc/extensions/skills/story/templates/plan-sections.md` | 「知识决策（设计输入）」章骨架 + `must` 的写法、`verify` 对照与借挂反例 |
| `doc/extensions/manifest.yaml` 的 `provides.knowledge` 里**命中**的那几个文件 | 条目的处置列、落法附注与**探针列**；候选模式的选型篇。未命中的域不必读 |

## 二、设计要证明它履行得了需求

从每条实际业务关系出发定实体、接口、状态与验证方式，然后自核四件事：前一步的输出够不够后一步用；
恢复路径能不能找回它需要的输入；展示用的值与业务身份能不能各自履职；所有约束能不能同时成立。
**实体名字齐全不等于做得到**。反向再看一遍：已经适用的业务步骤有没有漏掉该挂的义务。
收尾核 `plan.md` 与 `contracts.yaml` 说的是同一套设计；纯内部深化不必回填 story 细节，
改了范围、验收或关键承诺就回相应真源，再让下游取到当前依据。

## 三、产出形态

**① `plan.md` 里必须有一章「知识决策（设计输入）」，排在第一个设计章之前**——位置就是语义：排在设计之前，后面每一章才可能按它展开；排在设计之后只是事后声明。

**② 每条命中的规约，在 `contracts.yaml` 里挂一条 `must` 到扛着它的那个实体上：**
```yaml
components:
  - name: <组件名>
    must:
      - text: <这条规约在本需求里具体要求这个实体做什么>
        rule: <条目编号>
        verify: review
```
- `must` **只能**挂在五处：`data_models[].fields[]`、`interfaces[].methods[]`、
  `components[]` 及其 `state[]`、`resource_keys[]`、`files[]`；挂在实体顶层或别的集合上都会被拦。
  `text` 写**本次要落实成什么**，不复述规约原文；`rule` 只写真正要求这件事的规约。
- **不是某条规约要求的业务规则写在这里**：承载它的实体自己的 `description`，或 plan.md 对应设计章的一句，不挂 `must`。
  把「单个清单最多 50 项」挂到兼容性条目上就是借挂——编号在册、规则合法，那条规约却不要求这件事。
- 一条 `must` 就是一处落点，`verify` 说这一处的证据由谁取，按该规约验证列声明的执行体定：含「实机」写
  `ut` / `device` / `both`（这一处标 `review` 就是没证据）；只有「模型」（或加「构建」）`review` 即可；「人工」不挂 `must`（那是评审动作）。
- 采用的设计模式：给每个角色文件标 `files[].pattern` + `files[].role`，`role` 取值须是该模式 frontmatter 里声明过的角色名。

## 四、跑哪条命令

`cd framework/harness && npx ts-node harness-runner.ts --phase plan --feature <需求名>`

## 五、门禁会拦什么

- 缺「知识决策（设计输入）」章，或它排在第一个设计章之后。
- `must` 挂在实体顶层（如 `data_models.X` 而不是它的 `fields[]`），或挂在允许之外的集合上；契约用了流式写法 `- { … }`（扩展只读块式）。
- **两边对不上**：spec 判了命中而契约里没有实体扛着（知识在设计阶段就丢了），或契约里的
  `must.rule` 不在命中集内。命中集读 `spec/knowledge-use.yaml`，不是 spec.md 里那张投影表。
- `must.rule` 不在激活清单里（编号写错，或那条规约已下架）；`must.text` 缺失。
- `verify` 不是四个取值之一，或与规约声明的执行体不符（要「实机」证据的落点标了 `review`）。
- `files[].pattern` 不在册；标了 pattern 却没写 role；role 不是该模式声明过的角色。
- verifier 报告里没有本阶段判据的结论。（`must.text` 写的是不是本需求的设计由 verifier 判，门禁只问写没写。）
