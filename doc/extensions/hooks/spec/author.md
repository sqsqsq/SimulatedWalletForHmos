# spec 阶段 · 扩展要求（写之前读这一页）

> **推进不逐段问**：门禁报错怎么修、check 过了下一步做什么、进 harness 还是进 verifier——这些是义务不是选择题。停等点与两层授权边界的唯一定义，见[story SKILL.md「推进契约」](../../skills/story/SKILL.md#推进契约)。

**这一页只写原则**。这一次具体要做什么——你现在在哪、条目有哪几条、字段怎么填、十章各答什么、
门禁判什么——由同一个钩子生成的**任务包**给出，跟这一页一起送到你手上，不必再去翻文件。

## 先分清你在哪一组

这个需求走了 `/story` 链吗（需求目录里有 `AR/story-flow.json`）？

| | 走 `/story` | 直接跑 spec |
|---|---|---|
| 要写 | `spec/knowledge-use.yaml`、§9 技术契约 + §0 术语解释列 | **只有 `spec/knowledge-use.yaml`** |
| 还要 | 三份产物齐备（`spec.md` / `AR/review.md` / `AR/story.md`） | 无 |

这是**判据本身的分组**，不是建议：§9 与术语解释列是扩展新增的，对只跑原生 spec 的人
是凭空多出来的硬阻断；知识判定与 story 无关——它产生的代码要求不进 spec，编码那里就拿不到。

## 三条原则

**§10 与 §11 不手写**。它们是 `spec/knowledge-use.yaml` 的投影，由生成命令写进 spec.md。
判断只在 YAML 里做一次；同一个结论不在两处各写一遍，就不会有两处对不上的那一天。

**依据要可回查，不要过程**。判定的推演与决策论证是工作底稿，**不进 spec**——它是交给代码的
要求说明书。规约条目的完整逐条回显在归档件附录，也不进 spec。

**知识只读激活清单里的那些**。`manifest.yaml` 的 `provides.knowledge` 是本阶段生效的全部，
不扫 `knowledge/` 目录——目录里躺着的未启用文件不参与判定。

## 跑哪条命令

```
cd framework/harness && npx ts-node harness-runner.ts --phase spec --feature <需求名>
```

走 `/story` 链时，这一段的顺序由 `story_flow.py status` 逐步打印（它也给出这一步要写的
文件长什么样），照它给的敲即可。**harness 放在三份产物齐备之后**——之前跑它一定红。

取证怎么做、结论怎么写才能按名回查，见 [`skills/story/reference/evidence-rules.md`](../../skills/story/reference/evidence-rules.md)。
