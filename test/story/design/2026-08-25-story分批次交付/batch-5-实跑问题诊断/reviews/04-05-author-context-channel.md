# 步骤 4 + 5 · 作者上下文入口与 Extension 接入 · 实施记录（待评审）

## 0. 状态与前提

- 状态：**已实施，等待评审**（本轮 4、5 一起做，按用户 2026-09-03 指示）
- 审查基线：`80f5cc3e`（工作区起始干净）
- Framework 修改授权：用户 2026-09-03 明确授权，范围 = `steps/04` 允许范围
- **仍挂在整批账上的前提**：步骤 2 的真实 CLI smoke 未跑，结论 A/B 均未取得（见 `reviews/02` §0）。
  本两步不依赖 D1 结论，但「作者真的在写之前读到了」这件事，只有真实实跑能证明——
  本轮交付的是**通道**与**机械留痕**，不是行为证据。

本文件是实施记录，不是评审结论；评审请按 `reviews/README.md` 从实际 diff 重建行为。

## 1. 行为重建

**改之前**：`on_context_load` 能产出片段（`hooks-dispatcher.ts`），全仓唯一调用点在
`harness-runner.ts` 的 verifier 装配处——**通道存在、接错了对象**。片段只进 verifier 的上下文，
作者一次也看不到。`steps/04` 的实证：25 次实跑里，plan 到达 3 次全部先写完 `plan.md` 再读作者要求
（晚 2～70 分钟），coding 到达 1 次先改代码后读；spec 之所以正常是 `/story` 链自己指向了它，
不是机制在起作用。

**改之后**：

| 环节 | 谁负责 |
|---|---|
| 取内容 | `harness/scripts/author-context.ts`（只读；复用 `loadResolvedProfile` + `dispatchLifecycleHooks`，顺序 framework → profile → extension 与 harness 内部一致） |
| 何时取 | 六个 feature Skill 共用 `agent-behavioral-principles.md` 的**约束 0**：进入 phase、动笔之前 |
| 内容从哪来 | `doc/extensions/manifest.yaml` 六个 phase 的 `on_context_load` → 现有六份 `author.md`（一份真源，未复制） |
| 读没读过 | 既有门禁 `context_exploration_inputs_coverage`：overlay 声明 author 钩子路径为必需片段，没写进 `key_inputs_read` 即 FAIL |
| verifier | 只收 `pre_verifier`；`harness-runner` 的 `on_context_load` 调用已删除 |

**新增机制：零**。没有新生命周期、新 hook 事件、新状态文件、新门禁、新 adapter 能力。

## 2. 两处需要评审重点看的裁决

**① 来源标识由文件名改为仓内相对路径**（`hooks-dispatcher.ts`）。
六个阶段的钩子都叫 `author.md`；只写 basename 时六份标识一模一样——既指不出阶段，也没法被
`key_inputs_read` 逐字覆盖（那条门禁做子串匹配，`author.md` 会命中任何阶段，等于不设防）。
这是**全局**改动：`pre_verifier` 等其它事件的标识形态也随之变化。已确认全仓没有任何程序解析该标识
（只有两份历史设计文档提到过它的旧形态）。

**② 留痕借用既有门禁，不新增门禁**。`phase_input_snippets_extra` 经 phase rule overlay 合入
`resolvePhaseInputSnippets`，是既有链路；实例只在自己的 overlay 里声明一个字符串。
实证链路已逐段验过：overlay → 合入 phase rule → 进 required snippets（见 §3）。

## 3. 已取得的证据

| 判据 | 证据 | 结果 |
|---|---|---|
| 无 Extension / 无 hook → 空结果且原行为不变 | 合成工程去掉 `extension_dir` → 零片段、零失败 | PASS |
| 三层顺序与 dispatcher 一致 | 入口直接调 `dispatchLifecycleHooks`，未另写收集逻辑 | PASS |
| Markdown 与 MJS 都能在作者动作前到达 | md 走 `runMarkdownHook`、mjs 走 `runMjsHook`，同一 dispatcher；mjs 抛错用例已覆盖 | PASS |
| hook 失败 → 明确失败，不降级为空 | 注入抛错的 `boom.mjs` → `failures` 非空、`fragments` 为空；CLI 退出码 1 并打印「不要当作没有额外要求」 | PASS |
| verifier prompt 不再包含 `on_context_load` | 机械断言 `harness-runner.ts` 无 `emitLifecycle('on_context_load')`，且 `pre_verifier` 仍在 | PASS |
| profile 模板与概念文档描述新时序 | 四份 profile 模板 + `spec/SKILL.md` + lifecycle schema + phase-terminology 全部订正 | PASS |
| 六个 phase 共享同一规则，不在六份 Skill 复制 | 规则只写在 `agent-behavioral-principles.md`；device-testing 补上缺失引用（原本 6 缺 1） | PASS |
| 每个片段带来源标识，标识可被 `key_inputs_read` 逐字覆盖 | 六阶段实跑入口，标识均为 `doc/extensions/hooks/<phase>/author.md`；与 overlay 声明逐字一致 | PASS |
| 六个 phase 各只有一份作者内容，manifest 引用可达 | manifest 六条 `on_context_load` 全部指向现有文件；`git grep` 每份 author 首个标题行在全仓只有一处 | PASS |
| 缺失 hook 为空、损坏抛错 | 同上两条 | PASS |
| 根 AGENTS / 生成入口不再逐阶段传输 | `CLAUDE.md`、`AGENTS.md`、`AGENTS.section.md` 三处同步改为指向入口 | PASS |
| overlay 未声明的阶段行为不变 | `testing` 无 context-exploration 门禁 → 不声明，`exploration_thresholds` 为空 | PASS |
| 上游补丁可复现 | 纯净 framework 树 `git apply` 通过，七个受检文件逐字节一致 | PASS |
| 离线回归 | story 551（含 1 条已登记 expectedFailure）、cli 18、失效形态 73/73、完整性四项 | PASS |

**A05 抓到了一次真实疏漏**：我先只改了 `CLAUDE.md`，仓根给 codex/opencode 用的 `AGENTS.md` 没同步，
`A05-entry-misses-section` 立刻 FAIL。这条形态正是为「交付了入口段但入口文件没带上」而设的——
它按设计工作了，值得记一笔。

## 4. 问题

**blocker**：无。

**advisory**：

- **R10 · 「作者真的在写之前读到了」仍是未证事项**。本轮证明的是通道通、内容对、留痕有门禁守。
  但执行者会不会**真的**在动笔前跑那一条，只有真实实跑能看到——这正是 `measure_run` 第 2/3 项
  与 `context_exploration_inputs_coverage` 到步骤 11 要读的数。在那之前不要说「A03/A05 已解决」。
- **R11 · 标识形态是全局改动**。`pre_verifier` 等事件的片段标识也从文件名变成了相对路径。
  已确认无程序消费者，但下游若有人按旧形态肉眼匹配，会看到形态变化。
- **R12 · `agent-behavioral-principles.md` 的约束 0 写了具体命令**。命令形态一旦变（比如入口改名），
  这份规约要同步。放在这里是因为六阶段共用一处胜过六处复制，但它确实是一个坐标耦合点。
- **R13 · 未跑 `--json` 形态的消费者验证**。入口提供了 `--json`，但目前没有任何消费者用它；
  若长期无人用，下一轮应删掉而不是留着。

## 5. 范围与回归

**步骤 4 允许范围**内：`harness/scripts/author-context.ts`（新增）、`hooks-dispatcher.ts`、
`harness-runner.ts`、`agent-behavioral-principles.md`、`device-testing/SKILL.md`、`spec/SKILL.md`、
四份 profile spec/plan 模板、`lifecycle-hooks-schema.yaml`、`phase-terminology.md`、
`framework.config.json`（12 条具名 allowlist）、`TEST.md`、`artifacts/04-*`。

**步骤 5 允许范围**内：`doc/extensions/manifest.yaml`、五份 `rules/*-rules.overlay.yaml`
（只加 `exploration_thresholds.phase_input_snippets_extra`）、`AGENTS.section.md` 与两份生成入口
（`CLAUDE.md`、`AGENTS.md`）、行为测试 `test_author_context_entry.py`、`TEST.md`。

**六份 `author.md` 一字未动**——本步只修通道，不改业务要求，这样问题才能归因到「是否送达」。

**保护区差异：零**。产品源码、`test/story/golden/`、两个真实 Story Case 的输入与脚本、
`RELEASE-MANIFEST*`、adapter、closure、track、headless/goal、post_check/pre_verifier/Story build/
Knowledge 正文一字未动。

**未运行的高成本测试**：真实 Story（按步骤边界只用最小 phase 夹具）；步骤 2 的 CLI smoke（授权暂缓）。

## 6. 后续

- 允许提交：待评审裁定
- 下一步：步骤 6（材料版本与流程状态 SSOT）。它同时是步骤 3 外送的 P9 缺口的责任方——
  `test_run_measurement.py` 里那条 `expectedFailure` 会在 manifest 落地后意外通过并报错。

## 7. 独立评审（Claude，2026-09-03）

- 状态：**不通过（仅一项，交付面文案；改完即通过，无需重做）**。审查基线 `80f5cc3e`，对象为工作区全部差异（12 个 framework 文件 + 8 个扩展/入口/配置文件 + 2 个测试域文件）。
- 亲自复跑：`test_author_context_entry.py` 13 条、story 551（1 expectedFailure = P9 钉子）、cli 18、失效形态 73；
  `author-context.ts --phase plan` 在主仓实跑，输出恰一个片段、标识为 `doc/extensions/hooks/plan/author.md`；
  `harness-runner.ts` 已无 `emitLifecycle('on_context_load')`；`artifacts/04-*.patch` 在 HEAD 干净树 `git apply --check --directory=framework` 通过、12 文件逐字节一致。
- 与方案逐条对上：入口只读且复用 dispatcher；标识改仓内相对路径（`hooks-dispatcher.ts:113-116`，与 overlay 声明逐字一致）；行为规约约束 0 一处覆盖六阶段，device-testing 补引用；四份模板与 schema 同步；五份 overlay 声明 `phase_input_snippets_extra`，testing 如实不声明；author.md 一字未动、全仓唯一；旧远距离提醒从三份入口文件删除；allowlist 12 条具名且带失效条件。

**blocker（1）· 交付面写进了本仓的实跑读数**，违反 AGENTS §5.3「注释不包含某次运行数字、维护故事」，且其中两处随上游补丁交付：

| 位置 | 原文 | 改法 |
|---|---|---|
| `framework/harness/harness-runner.ts:1071` | 「实跑里 plan 阶段三次全是先写完 plan.md 再去读作者要求」 | 去主语与数字，留失效形态：「挂在这里时作者在动笔前看不到它，只能在门禁报错后补读」 |
| `framework/harness/scripts/author-context.ts:7` | 「实跑里 plan 阶段三次……晚 2～70 分钟」 | 同上 |
| `doc/extensions/manifest.yaml`（新增注释） | 「实跑里除了有 /story 链牵着的 spec，其余阶段都是先写完产物再读到要求」 | 「不登记在这里的作者要求只能靠执行者自己去翻，通常在产物落盘之后才读到」 |

改完重新生成 `artifacts/04-framework-author-context.patch`，再按步骤各提交一次（4 = framework + config + TEST §7.0.2；5 = 扩展 + 入口文件 + 测试）。

**advisory**：R10～R13 同意。另加：`TEST.md §7.2` 第五条扫描只认「实测」，这三处写的是「实跑」，机械扫描漏了；把词表扩成「实测|实跑|实证」归步骤 11 的最终扫描。

## 8. blocker 处置（实施者，2026-09-03）

§7 的唯一 blocker 已改，未重做任何设计：

| 位置 | 现文案 |
|---|---|
| `harness-runner.ts` | 「挂在这一行时……作者在动笔前看不到它，只能在门禁报错之后补读」 |
| `author-context.ts` | 「作者在动笔前看不到它，只能在门禁报错之后补读，而那时产物已经按错的要求写出来了」 |
| `manifest.yaml` | 「不登记在这里的作者要求，只能靠执行者自己去翻，通常在产物落盘之后才读到」 |

三处都只留失效形态，不留主语、轮次与时长。`artifacts/04-framework-author-context.patch` 已重新生成，
在 HEAD 干净树上 apply 后 12 个文件逐字节一致。

**advisory 中 §7 末条的处置有一处偏离，理由如下**：评审建议把 `TEST.md §7.2` 扫描词表扩成
`实测|实跑|实证`（归步骤 11）。我先按扩词试扫，捞出一条**既有**命中——
`doc/extensions/skills/story/phases/story-verify.md:106`「两轮实证，「2 秒」与「10KB」」。
它不在步骤 4/5 允许范围内，且该文件属步骤 9 的退场目标。因此**本步不改词表**：
现在扩词只会让每次提交都显示一条本步无权修的命中，反而把这条扫描训练成噪声。
词表扩展与这条既有命中一并留给步骤 9/11，此处登记发现，不静默略过。

R10～R13 保持开启（均非本步可关闭）。
