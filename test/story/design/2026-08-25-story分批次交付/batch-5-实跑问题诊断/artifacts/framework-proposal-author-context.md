# 提案：把 `on_context_load` 接到作者一侧

给 framework 维护者评估。本文只论**问题是否成立**与**这个解法是否最小、最合适**，
不含补丁，也不要求按本文的写法实现。

---

## 一、问题

`on_context_load` 是 framework 已有的生命周期事件。`hooks-dispatcher.ts` 会按
framework → profile → extension 三层收集该事件的钩子，`.md` 直接作为片段、`.mjs` 返回
`promptFragments`，合并成一组文本。**这条通道是完整的、能工作的。**

问题在**它被谁调用**：全仓唯一的调用点在 `harness-runner.ts` 组装 verifier 上下文的地方。
于是这些片段只出现在 verifier 的 prompt 里。

而这些片段的内容是「**动笔之前该知道什么**」——profile 与实例扩展在这里放的是本阶段的
写作要求、产物形态、字段与取值。它们的消费者是**即将写产物的那个执行者**，不是事后审查的 verifier。

**结果是时序错位**：要求送给了审查者，作者拿不到。作者只能先按自己的理解写完，
再从门禁报错里反推「原来还有这些要求」，然后返工。门禁本该是「核对既定条件」，
在这个时序下变成了「第一次告知规则」。

### 这不是推测

消费仓统计了 25 次真实实跑中，作者读到扩展的 `hooks/<phase>/author.md` 的时刻，
与该阶段主产物首次落盘的时刻：

| 阶段 | 到达次数 | 写之前读到 | 写之后才读到 |
|---|---|---|---|
| spec | 16 | 14 | 2 |
| plan | 3 | **0** | 3（晚 2～70 分钟） |
| coding | 1 | **0** | 1 |

spec 看起来正常，但原因不在机制：消费仓的实例 Skill 自己在正文里指了一句
「先读 spec 的 author.md」。**其余阶段没有任何在动笔前送达的通道，数据也就全部落在右边一列。**

## 二、为什么这件事只能由 framework 解决

扩展方能做的只有「声明我在这个事件上挂了什么」。**事件何时被触发、由谁消费，是 harness 的编排职责**，
扩展没有任何接口可以影响它。

消费方唯一的替代做法是：在自己的 Skill 正文里写一句「动笔前请去读 `<路径>`」。
这条路走不通，原因不是麻烦，是**它要求扩展复制 framework 已经做过的事**：

- 三层来源（framework / profile / extension）各自的目录解析；
- profile 解析结果（`loadResolvedProfile`）——扩展拿不到，只能猜路径；
- `.mjs` 钩子的执行、超时、失败处置与结果契约；
- 片段顺序与合并规则。

复制出来的那一份和 framework 的实现会各自演进，**下一次 framework 改了钩子解析，
扩展这份就静默过期**。而且它只能覆盖扩展自己那一层——profile 层的 `on_context_load`
仍然到不了作者手上，而那一层不归扩展管。

所以：**通道已经有了，缺的只是一个面向作者的调用时机。补上它属于 framework 的编排职责。**

## 三、这个解法为什么是最小的

提案的改动可以概括成一句：**加一个只读入口，让执行者在动笔前自己调用同一个 dispatcher。**

### 复用而非新建

| 不新增 | 复用现有的 |
|---|---|
| 生命周期事件 | 仍是 `on_context_load` |
| 钩子协议 / payload 契约 | 仍是 `hook_ctx` / `hook_script_result` |
| 三层解析逻辑 | 仍是 `loadResolvedProfile` + `dispatchLifecycleHooks` |
| adapter 能力字段 | 无 |
| 阶段状态 / 产物 / 报告 | 无（入口只读，不写任何文件） |
| 门禁 | 无（留痕借既有的 `context_exploration_inputs_coverage`，见下） |

新增的是**一个入口**，不是一项能力。

### 行为上只动了一处

verifier 装配处的那次 `on_context_load` 调用**删掉**。

这里值得说明为什么是「删」而不是「移」：如果把调用移到 harness 内部的某个更早的点，
就得回答「早到哪一步」——而 harness 的运行时机是「产物已经写完、开始检查」，
它没有一个「作者动笔前」的时点可挂。**作者动笔发生在 harness 之外**，
所以调用权必须交给执行者自己。这也是入口做成独立只读脚本、而不是 harness 的一个 flag 的原因。

删掉之后 `pre_verifier` 继续只服务 verifier，两个事件各自只有一个消费者，语义反而更清楚了。

### 留痕不新增门禁

「作者到底读没读」需要可核对，否则等于没送达。

framework 已有 `context_exploration_inputs_coverage`：它要求 `context-exploration.md` 的
`key_inputs_read` 覆盖本阶段的最低输入，必需片段来自 `resolvePhaseInputSnippets`，
其中 `phase_input_snippets_extra` 由 phase rule overlay 合入。

于是 profile / 扩展只要在自己的 overlay 里声明「本阶段 author 钩子的坐标」，
作者没读没登记就会在这条既有门禁上 FAIL。**framework 侧对此零改动**，
只需保证入口输出的来源标识与 overlay 声明的是同一个字符串——这引出下面唯一的一处附带修正。

### 一处必要的附带修正：来源标识

现在片段的来源标识用的是文件名（`author.md`）。六个阶段的扩展钩子都叫 `author.md`，
标识因此完全相同：既指不出是哪一阶段的，也没法被 `key_inputs_read` 逐字覆盖
（那条门禁做子串匹配，`author.md` 会命中任何一个阶段，等于不设防）。

改成**仓内相对路径**后标识本身就是唯一坐标。这不是新增功能，
是让上面那条既有门禁在多阶段场景下能真正生效。

## 四、改了哪些文件、各自在做什么

12 个文件，按角色分三组。

### 1. 新增（1 个）

**`harness/scripts/author-context.ts`** — 作者起手内容的只读入口。

- 入参：`--phase`、`--feature`，可选 `--json`；
- 做的事：解析 profile → 调 `dispatchLifecycleHooks('on_context_load')` → 把片段按序打印到 stdout；
- 边界：**不写任何文件、不改任何状态、不产报告**；
- 退出码语义：零片段 = 本阶段确实没有额外要求（正常退出）；钩子执行失败 = **非零退出**，
  不把「取不全」降级成「没有」。

### 2. 行为改动（2 个）

**`harness/harness-runner.ts`** — 删去 verifier 装配处的 `emitLifecycle('on_context_load')`。
理由见 §3：这个事件的消费者不是 verifier；删掉后两个事件各自单一消费者。

**`harness/hooks-dispatcher.ts`** — 片段来源标识由文件名改为仓内相对路径。
理由见 §3 末：让 `key_inputs_read` 的覆盖判据在六个阶段上都能逐字对上。
越出工程根时退回绝对路径的 posix 形态，如实指出它在树外。

### 3. 契约与文档订正（9 个）

这一组不改行为，只是把「这个事件是给谁的、什么时候取」写对——
原来的描述都基于「由 harness 在组装 ai-prompt 时注入」，与新的时序不符。

| 文件 | 改的内容 |
|---|---|
| `specs/lifecycle-hooks-schema.yaml` | `on_context_load` 的事件描述：由「组装 ai-prompt 时」改为「作者阶段起手内容，由 `author-context.ts` 消费，执行者在写主产物前跑；片段不进 verifier prompt」 |
| `docs/concepts/phase-terminology.md` | 同上，叠加机制那一节的时序描述 |
| `skills/reference/agent-behavioral-principles.md` | 增「约束 0：进入 phase、动笔之前跑一次作者起手入口」，**六个阶段共用一条**，含命令、退出码语义、以及「把输出里的坐标写进 `key_inputs_read`」 |
| `skills/feature/spec/SKILL.md` | 一句话订正：扩展叠加的 `on_context_load` 由执行者动笔前主动取得，不再暗示 harness 后置注入 |
| `skills/feature/device-testing/SKILL.md` | 补上对行为规约的引用（其余五个阶段的 SKILL 本来就有，只有它缺） |
| `profiles/{generic,hmos-app}/skills/{spec,plan}/templates/*-template.md`（4 份） | 同样的一句时序订正 |

## 五、请评估的几点

1. **问题是否成立**：`on_context_load` 的片段内容面向作者，而唯一消费点在 verifier——
   这个错位在你们的设计意图里是不是本来就该如此？如果 profile 层从未打算用它送作者要求，
   那本提案的前提就不成立。
2. **入口形态**：独立只读脚本（本提案）vs `harness-runner` 加一个 flag。
   本提案选前者的理由是「作者动笔在 harness 之外」，但如果你们已有面向执行者的入口约定，
   应当并入那里。
3. **来源标识**：改成仓内相对路径是否会影响其它已依赖 basename 形态的消费者。
4. **留痕方式**：借用 `context_exploration_inputs_coverage` 是否恰当。它原本的语义是
   「探索输入覆盖」，本提案把「读没读作者要求」也挂了进去——若你们认为语义不该扩张，
   这条留痕可以换成别的形式，本提案的主体不依赖它。
5. **`device-testing` 的行为规约引用缺失**是既有的不一致，与本提案无关，可单独处理。

## 附：基线

改动基于 3.0.0。截至提交本文时，上游 `Br_release_3.0.0` 尚未包含这几项，
`harness-runner.ts` 里的 `on_context_load` 仍挂在 verifier 装配处。
消费仓侧已在两轮真实需求上运行过这套改动，作者读到要求的时刻与产物落盘的先后关系符合预期。
