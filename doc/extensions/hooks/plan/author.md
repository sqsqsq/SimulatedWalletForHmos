# plan 阶段 · 扩展要求（写之前读这一页）

> **推进不逐段问**：门禁报错怎么修、check 过了下一步做什么、进 harness 还是进 verifier——这些是义务不是选择题。停等点与两层授权边界的唯一定义，见[story SKILL.md「推进契约」](../../skills/story/SKILL.md#推进契约)。

本阶段是设计模式**唯一的选型点**，也是规约义务**唯一的落点**：coding / review / ut / testing
不读知识目录，它们读的是**你挂在契约实体上的 `must`**。挂错地方或没挂，下游就零注入。

## 一、读哪几个文件

| 文件 | 拿什么 |
|---|---|
| `doc/extensions/skills/story/templates/plan-sections.md` | 「知识决策（设计输入）」章骨架 + `must` 的写法与一个中性示例 |
| 上游 `spec/spec.md` 的 §10、§11 | §10 每条命中条目在本阶段都要有实体扛着；§11 的候选是选型的出发点 |
| `doc/extensions/manifest.yaml` 的 `provides.knowledge` 里**命中**的那几个文件 | 条目的处置列、落法附注与**探针列**；候选模式的选型篇。未命中的域不必读 |

## 二、产出形态

**① `plan.md` 里必须有一章「知识决策（设计输入）」，且排在第一个设计章之前。**

位置就是语义：排在设计之前，后面每一章才可能按它展开（数据模型因此多一个字段、接口因此多一个方法）；排在设计之后就只是事后声明。

**② 每条命中的规约，在 `contracts.yaml` 里挂一条 `must` 到扛着它的那个实体上：**

```yaml
components:
  - name: <组件名>
    must:
      - text: <这条规约在本需求里具体要求这个实体做什么>
        rule: <条目编号>
        verify: probe
```

- `must` **只能**挂在五处：`data_models[].fields[]`、`interfaces[].methods[]`、
  `components[]` 及其 `state[]`、`resource_keys[]`、`files[]`；挂在实体顶层或别的集合上都会被拦。
  `text` 写**本次要落实成什么**，不是复述规约原文——那样等于没做设计。
- `verify` 封闭取值：`ut` / `device` / `both` / `review` / `probe`。取 `probe` 时，
  该条目的规约表**必须有探针**（探针表达式在规约里，不写在契约里）。
- 采用的设计模式：给每个角色文件标 `files[].pattern` + `files[].role`，`role` 取值须是
  该模式 frontmatter 里声明过的角色名。

**判据一句话：义务要挂在下游真的会读的那个实体上**——挂在别处就是又造了一本没人读的账本。

## 三、跑哪条命令

```
cd framework/harness && npx ts-node harness-runner.ts --phase plan --feature <需求名>
```

## 四、门禁会拦什么

- 缺「知识决策（设计输入）」章，或它排在第一个设计章之后。
- `must` 挂在实体顶层（如 `data_models.X` 而不是它的 `fields[]`），或挂在允许之外的集合上。
- **两边对不上**：§10 判了命中而契约里没有实体扛着（知识在设计阶段就丢了），
  或契约里的 `must.rule` 不在 §10 的命中集内（评审者会看到互相矛盾的结论）。
- `must.rule` 不在激活清单里（编号写错，或那条规约已下架）；`must.text` 缺失或是原文复制。
- `verify` 不是封闭取值之一；标了 `probe` 但该条目的规约表没有探针（coding 执行不了）。
- `files[].pattern` 不在册；标了 pattern 却没写 role；role 不是该模式声明过的角色。
- verifier 报告里没有逐行裁决表。

spec 全部单元都写「无候选」时，本阶段不应凭空选出一个模式——那说明选型依据不是从需求来的。
