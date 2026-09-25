# spec 入口前置 story 流程：诉求与可行性分析

> 状态：仅分析，未实施  
> 日期：2026-08-13  
> 范围：只分析实例侧现有 spec hooks 的编排方式；不新增命令，不修改 `framework/`，不运行 story/spec/plan
>
> **§8 是移入本轮设计目录时补的复核结论**（原文 §1–§7 未改动）：方案主体成立，
> 但有两处必须先解决才能实施。

## 1. 用户诉求

保持现有 `/spec` 命令与 Framework 不变。当执行：

```text
/spec AR90006
```

spec 通过实例侧已有 hook 自动完成：

```text
/spec AR90006
  → on_context_load 检查 story-flow
  → 未就绪：当前 spec 分支把续接权交给 /story init AR90006
  → story 完成既有 S1–S4，由 S4 作为唯一所有者进入 spec
  → 新进入的 spec 看到 story-flow=complete，跳过 story，执行原有 Step 1 及后续流程
```

最终效果应与先执行 `/story init AR90006`、再进入 spec 一致，但用户只需调用一次 `/spec AR90006`。

## 2. 结论

### 2.1 能否基于现有 Framework 能力实现

**可以。无需新增命令，也无需修改 `framework/`。推荐组合使用当前已经注册的两个 spec hook：**

1. `hooks/spec/on_context_load.md`：负责给当前 spec agent 注入“AR 参数先执行 story init”的强制前置 SOP；
2. `hooks/spec/post_check.mjs`：负责 fail-closed 校验，确保 AR feature 没有跳过 story 或带着未收口契约完成 spec。

这里的“hook 自动拉起 story”不是 MJS 子进程直接调用另一个 AI Skill，而是：

- Framework/Spec 上下文加载机制把 Markdown hook 交给当前 agent；
- hook 要求同一个 agent 先读取并执行现有 story Skill 的 init 流程；
- story S4 是 story→spec 的唯一续接所有者，外层 spec 不再独立继续一次；
- post-check 对最终状态做机械兜底。

这符合当前实例扩展模型：Markdown hook 负责 prompt/SOP 注入，MJS hook 负责结构检查。

### 2.2 当前为什么还没有这个效果

Framework 能力已经存在，但实例 hook 尚未声明这条前置路由：

- 当前 `on_context_load.md` 从“上游输入必读清单”开始，只规定 spec 如何消费 `AR/design.md`、PRD、SE 等材料，没有规定 `/spec <AR>` 必须先跑 story init；
- 当前 `post_check.mjs` 仅在 `AR/story-flow.json` **已经存在**时检查它是否收口；文件不存在时直接放行；
- 所以直接 `/spec AR90006` 可以在完全没走 story 的情况下继续，hook 目前只做内容扩展和条件校验，没有建立“AR → story init”的闭环。

## 3. 现有能力与职责分工

| 能力 | 当前职责 | 本诉求中的职责 |
|---|---|---|
| `on_context_load.md` | 注入 spec 的上游输入、三份产物、技术契约与合规 SOP | 在文件最前增加 AR 前置 story init 编排 |
| `post_check.mjs` | 检查三份产物、§9、红线；存在 story-flow 时检查收口 | 对 AR feature 强制要求 story-flow 存在且 complete |
| `story/SKILL.md` | token、init S1–S4、材料/范围关卡、生成 `AR/design.md` | 完全复用，不复制 story 逻辑到 spec hook |
| `manifest.yaml` | 注册 spec 的 `on_context_load` 与 `post_check` | 已满足，无需新增注册项 |
| Framework lifecycle hooks | 加载 Markdown prompt、执行 MJS 检查 | 原样使用，不改协议和 runner |

事实依据：

- [`doc/extensions/manifest.yaml`](../../../doc/extensions/manifest.yaml)：两个 spec hook 已注册。
- [`doc/extensions/hooks/spec/on_context_load.md`](../../../doc/extensions/hooks/spec/on_context_load.md)：当前 spec 上下文注入内容。
- [`doc/extensions/hooks/spec/post_check.mjs`](../../../doc/extensions/hooks/spec/post_check.mjs)：当前 story-flow 的“存在才检查”逻辑。
- [`doc/extensions/skills/story/SKILL.md`](../../../doc/extensions/skills/story/SKILL.md)：story init 的 S1–S4 与 S4 进入 spec 语义。
- [`framework/specs/lifecycle-hooks-schema.yaml`](../../../framework/specs/lifecycle-hooks-schema.yaml)：Markdown/MJS lifecycle hook 协议。
- [`framework/skills/reference/agents-entry-detail.md`](../../../framework/skills/reference/agents-entry-detail.md)：实例可在不改 Framework 的前提下挂载 phase 前后 hook。

## 4. 推荐的 hook 设计

### 4.1 `on_context_load.md`：前置编排

在现有文件顶部增加 BLOCKER 级“AR 前置 story ready gate”章节。它不是每次无条件重跑，而是按唯一状态 `AR/story-flow.json` 分流：

```text
触发条件：本次 /spec 的 feature 参数完整匹配 ^AR\d+$。

1. 非 AR 参数：不触发，继续现有 spec 流程。
2. story-flow 合法且 status=complete：story 已就绪，禁止再次执行 init，直接进入 spec Step 1。
3. story-flow 不存在或 status=in_progress：在写任何 spec 产物前，把控制权交给 story init/恢复；
   当前外层 spec 分支到此结束，不得在 story 之外再独立继续一次 spec。
4. story init 必须完整执行 token 获取与 S1–S4；不得只跑 story.js init S1。
5. S3 的人工/授权关卡、补料循环、拆分决策与 story-flow 留痕完全沿用 story Skill。
6. story S4 写 complete 后，由 S4 作为唯一入口进入 spec；新 spec 再加载本 gate 时因 complete 而放行。
7. story-flow 损坏或 complete 但已有完整性字段不满足：停止并修复/恢复 story，禁止 spec。
8. story 失败或停等时，spec 同步停止/停等，不得降级绕过。
```

关键点：hook **只负责调用既有 story 规约**，不能复制 S1–S4 的实现正文。否则 story Skill 与 spec hook 会形成两份流程真源并漂移。

这使两个入口具有不同但互补的语义：

| 入口 | 语义 | 完成后的 spec 入口所有者 |
|---|---|---|
| `/story init AR90006` | 显式执行/重新执行 story init | story S4 |
| `/spec AR90006` | ensure：story 未就绪才执行，已 complete 则复用 | 未就绪时由 story S4；已就绪时为当前 spec |

若把 `/spec` 也定义成“即使 complete 仍强制 init”，就无法只靠持久化状态区分“用户新调用”与“story S4 回入 spec”，容易形成无限递归。为了同时满足共存、无冲突、无重复，隐式入口必须采用 `ensure`，显式 `/story init` 保留 `force` 语义。

### 4.2 `post_check.mjs`：闭环兜底

当前逻辑是：

```text
story-flow.json 不存在 → 返回 []，不检查
```

建议调整为：

```text
feature 匹配 ^AR\d+$ 且 story-flow.json 不存在
  → BLOCKER：必须先按 spec on_context_load 执行 story init

story-flow.json 存在
  → 沿用已有 status、round、decision、split、design_generated_at 检查

非 AR feature 且 story-flow.json 不存在
  → 维持当前放行，兼容普通 spec
```

这样 `on_context_load` 负责“应该怎么做”，`post_check` 负责“没有做就不能闭环”。即使 agent 漏读或误解 prompt，也不会静默交付一份绕过 story 的 AR spec。

### 4.3 两个入口共用一个状态机

只使用现有 `AR/story-flow.json`，不新增第二份 continuation：

| story-flow 状态 | `/spec AR90006` 行为 | 是否允许写 spec |
|---|---|---|
| 不存在 | 交给 story init；当前 spec 分支结束 | 否 |
| `in_progress` | 恢复 story；当前 spec 分支结束 | 否 |
| `complete` 且现有完整性条件通过 | 跳过 story，执行 spec | 是 |
| JSON 损坏或 complete 自相矛盾 | 停止，按 story 契约修复 | 否 |

状态转换只有一条：`不存在/in_progress → story S1–S4 → complete → spec`。两个入口只是从不同位置进入这条状态机，不各自维护流程。

### 4.4 单一所有权规则

为避免双写与重复执行，职责必须钉死：

- story 是 `story-flow.json`、`AR/init-analysis.md`、`AR/design.md` 的唯一流程所有者；spec hook 只读状态，不代写、不补写；
- spec 是 `spec/spec.md`、`acceptance.yaml` 及 spec 阶段三份产物的所有者；story 不提前写 spec；
- story 未就绪时，**story S4 是唯一的 spec 续接点**；外层 `/spec` 不再续跑第二遍；
- `post_check.mjs` 只判定，不启动 story、不修复产物；
- S3 停等时只保留 story 分支，不得同时留下一个继续生成 spec 的分支。

## 5. 方案边界

### 5.1 能保证什么

- 用户入口仍是 `/spec AR90006`；
- story 未就绪时自动执行完整 story init，而不只是材料拉取脚本；
- story 成功后继续 spec 原流程；
- 显式 `/story init` 与隐式 `/spec AR` 汇入同一个 story-flow 状态机；
- AR 模式下不能跳过 story 后仍通过 spec post-check；
- 普通非 AR spec 保持兼容；
- 不修改 Framework，不新增命令或 Skill。

### 5.2 需要明确的实现语义

这是 **prompt 编排 + 机械兜底**，不是 hook dispatcher 原生提供的“调用另一个 Skill”返回类型。也就是说：

- `on_context_load.md` 指挥当前 agent 执行 story；
- `post_check.mjs` 验证执行结果；
- MJS hook 本身不启动第二个 agent，也不承担 S3 人机交互。

这正好适合当前 story：S2–S4 包含语义分析和人工关卡，不能由一个 30 秒 MJS 子进程替代。

### 5.3 plan 边界

story S3 的“进入 spec”只授权继续本次 spec，不授权 spec 闭环后自动进入 plan。进入 plan 仍服从现有 `manual` / `batch_authorized` / `goal_mode` 规则。

## 6. 后续实施验收条件（本次不执行）

1. 干净工作区执行 `/spec AR90006` 时，第一个业务动作是 story token/init，而不是创建 spec 产物。
2. `/spec AR90006` 与 `/story init AR90006` 走同一套 S1–S4，产物与交互语义一致。
3. story-flow 已 complete 时再次执行 `/spec AR90006`，不得重跑 story；只执行一次 spec。
4. 显式再次执行 `/story init AR90006` 时仍可重新进入 story，完成后只进入一次 spec。
5. 只执行 `story.js init`、未完成 S2–S4 时，spec 不得继续闭环。
6. story S3 停等、补料、拆分和授权代答均保持原行为，且不存在并行 spec 分支。
7. story S4 后只进入一次 spec，不产生递归或外层 spec 二次续跑。
8. AR feature 缺 `AR/story-flow.json` 时 post-check 必须 BLOCKER。
9. AR story-flow 未 complete、末轮非 proceed、拆分缺 scope 或 design 时间缺失时继续 BLOCKER。
10. 非 AR feature 缺 story-flow 时仍可直接执行普通 spec。
11. story 失败时不得留下可被误判为完成的 spec。
12. spec 闭环后不自动越权进入 plan。

测试应同时覆盖正反例：`/story init` 入口、`/spec AR` 首次入口、`/spec AR` complete 复用、in_progress 恢复、AR 缺契约被拦、AR 未收口被拦、非 AR 无契约可过、S4 后无递归且 spec 只执行一次。

## 7. 最终建议

按用户限定，正式方案就是：**只修改实例侧现有 `on_context_load.md` 与 `post_check.mjs`，使用既有 `story-flow.json` 做 ready/re-entry gate；显式 `/story init` 为 force，隐式 `/spec AR` 为 ensure，story S4 是需要 story 时唯一的 spec 续接点。`manifest.yaml`、story Skill、spec 命令和整个 `framework/` 均不改。**

这比新增入口路由协议更符合当前诉求，也复用了 Framework 已提供的 lifecycle hook 扩展能力。

---

## 8. 复核结论（移入设计目录时补，2026-08-13）

### 8.1 方案主体成立

- **入口语义（`ensure` vs `force`）的分析是对的**：只靠持久化状态区分「用户新调用」与
  「story S4 回入 spec」确实做不到，隐式入口必须 `ensure`，否则递归。§4.1 末段这段推理
  是本方案最关键的一处，站得住；
- **状态机复用 `story-flow.json`、不新增第二份 continuation**——正确，与本轮
  「每个事实只有一个权威落点」一致；
- **单一所有权规则（§4.4）**必要：story 拥有 `story-flow.json` / `init-analysis.md` /
  `design.md`，spec 拥有 spec 三产物，`post_check` 只判定不修复。这条防的是双写。

**并已复核过一个我先前的错误假设**：`framework/specs/lifecycle-hooks-schema.yaml` 里确有
`pre_check` / `pre_phase` 事件，看似能提供比 `post_check` 更早的机械拦截。**但它们都在
harness 运行内触发**，而 harness 是 agent 写完产物后才跑的——比 `post_check` 早不了多少。
所以 §4 选的 `on_context_load`（prompt，最早）+ `post_check`（机械，兜底）**确实是
当前协议下唯一可用的组合**。

### 8.2 必须先解决的两处

**① `^AR\d+$` 是一个全仓未定义的命名约定。**

检索 `framework.config.json`、`spec-rules.yaml`、`doc/module-catalog.yaml`——**没有任何
地方定义「feature 名匹配 `^AR\d+` 就必须走 story」**。这个判据是从演示需求的命名
（AR90003/4/6）反推出来的，等于**把「要不要走 story 流程」绑到了标识符的拼写上**。

风险：内网真实单号未必都是 `AR` + 纯数字（`AR90006-1`、带后缀的变体都会漏判）；
反过来，任何恰好以 AR 开头的非 story feature 会被误拦。

**修正方向**：把这个约定**显式化**而不是硬编码进 hook。判据本身其实是合理的——用户在
`/spec AR90006` 里传 AR 单号，这个行为就是意图声明；名字只是它的代理。所以应当把模式声明
到实例侧可改的位置（`rules/spec-rules.overlay.yaml` 是我们的 overlay，或 `manifest.yaml`），
hook 从那里读，模式变了改声明而不是改代码。**实施前需先定这个落点。**

**② 会打爆现有门禁夹具。**

`test/story/tests/test_flow_contract_gate.py` 的 `FEATURE = "AR90099"`，且第一条测试
`test_fixture_itself_is_clean` 明确断言「**无契约文件时放行**」——它是整个门禁测试的基准
（自证夹具干净，反例才有意义）。新规则下 `AR90099` 匹配 `^AR\d+$`、无契约 → BLOCKER，
**这条必然失败**。

**修正方向**：基准夹具改用非 AR 名（如 `FT90099`）验证「非 AR 无契约放行」，
另加一个 AR 名夹具验证「AR 无契约被拦」——正反例都要（永久踩坑）。

### 8.3 一处该写明的代价

`post_check` 在 **spec 闭环时**才触发。若 agent 真的漏读 prompt 跳过了 story，
拦下来时 `spec.md` / `story.md` / `review.md` 已经全部写完（且是基于缺失前置的输入写的），
**返工成本是整个 spec 阶段**。

§4.2 把它称作「fail-closed」略过誉，实际是 **fail-late**。这不是设计缺陷（§8.1 已确认
没有更早的机械点），但文档应当写明这个代价，以免读者以为有廉价兜底而放松 prompt 侧的严谨。

### 8.4 实施前置

本主线（M3）在 [00-总体执行计划.md](00-总体执行计划.md) 里排在 M1 之后：
M1 修的是 `story_flow.py` 的记录失真，M3 依赖契约作为唯一状态源，**契约先可信，再拿它做门**。

实施前需用户裁决：§8.2① 的模式声明落点（`spec-rules.overlay.yaml` / `manifest.yaml` / 其它）。
