# spec 阶段 · 扩展要求（写之前读这一页）

> **推进不逐段问**：门禁报错怎么修、check 过了下一步做什么、进 harness 还是进 verifier——这些是义务不是选择题。停等点与两层授权边界的唯一定义，见[story SKILL.md「推进契约」](../../skills/story/SKILL.md#推进契约)。

本工程的实例扩展在 spec 阶段有两组要求。这一页只做索引：读什么、写成什么、跑什么、门禁拦什么。

**先分清你在哪一组**——这个需求走了 `/story` 链吗（需求目录里有 `AR/story-flow.json`）？

| | 走 `/story` | 直接跑 spec |
|---|---|---|
| 要写 | `spec/knowledge-use.yaml`、§9 技术契约 + §0 术语解释列 | **只有 `spec/knowledge-use.yaml`** |
| 还要 | 三份产物齐备（`spec.md` / `AR/review.md` / `AR/story.md`） | 无 |

这是**判据本身的分组**，不是建议：§9 与术语解释列是扩展新增的，对只跑原生 spec 的人
是凭空多出来的硬阻断；知识判定与 story 无关——它产生的代码要求不进 spec，编码那里就拿不到。
**§10 与 §11 不手写**，它们是 `knowledge-use.yaml` 的投影，由生成命令写进 spec.md。

## 一、读哪几个文件

| 文件 | 拿什么 | 谁要读 |
|---|---|---|
| `manifest.yaml` 的 `provides.knowledge` 所列文件 | 本阶段生效的规约条目表与项目知识。**只读清单里的**，不扫 `knowledge/` 目录 | 所有需求 |
| `skills/story/templates/spec-sections.md` | §9 的表结构；§10/§11 那两节的注释写清 `knowledge-use.yaml` 各字段怎么填 | 所有需求（§9 那节只有走 `/story` 时才写） |
| `skills/story/reference/evidence-rules.md` | **§9 各节**怎么取证、结论怎么写才能按名回查 | 走 `/story` 时 |
| [`skills/story/phases/spec.md`](../../skills/story/phases/spec.md) | 本轮材料从哪来、要出几份产物 | 走 `/story` 时 |

规约条目表的「处置」列与该域落法附注是要求的正文，此处不复述——规约改了这一页不用改。

## 二、产出形态

**所有需求**：写一份 `doc/features/<需求名>/spec/knowledge-use.yaml` —— 本阶段知识判断的
唯一真源。三段各回答一件事：`facts` 用了什么、每条 `constraints` 命不命中（命中写要求，
不命中写可回查的依据）、`patterns` 有哪些候选（只登记不选型）。**激活清单里的每一条约束
都要有去处**，漏一条是「没判过」。逐字段怎么填见 `spec-sections.md` 的 §10/§11 两节注释。
写完跑 `node doc/extensions/hooks/shared/knowledge-use.mjs render --feature <需求名>`，
§10/§11 的正文由它写。

**走 `/story` 时另加**：§9 技术契约（守恒与专名的数据源）；§0 术语映射表补「解释」列
（权威模块落在 `in_scope_modules` 的行不得为空）。逐条规约判定的完整回显在归档件附录，不进 spec。

判定的推演过程与决策论证都是工作底稿，**不进 spec**——它是交给代码的要求说明书。

## 三、跑哪条命令

```
cd framework/harness && npx ts-node harness-runner.ts --phase spec --feature <需求名>
```
走 `/story` 链时，S1–S4 的命令由 `story_flow.py status` 逐步打印，照它给的敲即可。

## 四、门禁会拦什么

**对所有需求**：`knowledge-use.yaml` 缺失、有激活条目没有去处、编号或候选不在册、
命中没写要求、依据只有「不涉及」、在 spec 里给模式选了型、`manifest_digest` 与激活清单对不上；
§10/§11 缺章缺生成区、生成区与 YAML 对不上或章里还留着旧手写表；
正文出现文档坐标（`spec §x`、`见 A5` 这类）——改写事物的名字；规约写成 `<域文件名>:<编号>`
这种仓内 slug——改中文规约名 + 编号；阈值/时长/次数没标来源类型（`（上游约束：<文档名>）` /
`（本工程设定，无上游依据）` / `（平台基线）`，标「上游约束」时会读 SR/RR 原文核对）。

**只在走 `/story` 时**：§9 缺章缺小节或没填；术语映射表里 `in_scope_modules` 的业务词没解释；
三份产物不齐或叙事件没登记成文态；三级关卡没走完就进本阶段。
