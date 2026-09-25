# 子批 R · CLI 实跑报告 · `story-suite-20260828-191953`

> 2026-08-28 19:20 起跑，22:35 finalize。两 Case 并行，隔离 workspace。
> 宿主在实跑期间的身份是**需求方 / 评审人**（TEST.md §0.2），只回业务、不指路。
> 本报告是 02-交付报告的**行为栏**；离线栏见那一份。

## 一、跑了什么

| Case | feature | 起点 → 终点 | 交互 | 终态 |
|---|---|---|---|---|
| `pattern-image-review` | AR90004 | story → review（含 coding） | 无脚本，宿主实时回 0 次 | `cli_failed` |
| `source-conflict-review` | ISSUE-410 | story → review（含 coding） | 脚本 1 条 + 宿主实时回 6 次 | `target_not_reached` |

**为什么挑这两个**：R 改的判据（S5 裁决核实、规约判定表、术语守恒、四红线、归档链门禁）
只在 spec 闭环之后触发。四个 Case 里只有这两个走到 review，另两个（到 spec / 到 plan）碰不到。

**两个都没到「绿」**，但原因完全不同，且都指向真问题——见 §三。

## 二、R 的机制在真实产物上成立（正面证据）

### 2.1 S5 全链走通（AR90004，304 个来源单元）

| 项 | 实测 |
|---|---|
| `story.md` | 37,100 字节、348 行、**14 章**（= 合同章数） |
| 三态分布 | `at`+`machine` **247**（81%）／`at`+`author` **40**（13%）／`covered_by` **14**／`machine_facing` **3**／**三态皆空 0** |
| `story-verdicts.md` | **43 条裁决**，表头与 `phases/story-verify.md` 规定一致，引文取自 story 正文 |
| 合规章判定表 | **15 条**（命中 12 / 不命中 3），与本仓激活规约条目数一致，每条带依据 |
| `story-flow.json` | `status = story_written` |
| 门禁 | `story_build_check` **pass** |

**这条最有分量**：`story_flow.py story` 的登记门禁先重跑一次 `story-build check`，通过才写
`story_written`。状态既然写了，说明 **check 九项在 304 单元的真实产物上全过**——含 R1 的
⑥ 裁决核实、R2 的 ⑦ 判定表、R4 并进来的 ⑧ 术语守恒与 ⑨ 四红线。

评审 U1 说的「130/306 靠作者手填、check 不核」，新形态下降到 **40/304，且每条都有引文可核**。

### 2.2 引文核实在真实运行里拦住一次（子批 B）

AR90004 20:07:58：`gate 用 evidenceVerified 校验，证据列必须是 spec.md 里可检索的连续原文，
而报告里证据列混入了「spec §10：」「——落点…」等非原文前后缀，归一化后不是 spec.md 的子串。`
模型据报错自行重写为纯原句后通过。**这是行为证据，不是夹具证据。**

### 2.3 义务上实体被下游消费（子批 B）

- coding 闭环自检：`must 义务对应实体（CertificateCacheStore / shareInProgress / 资源键）均真实存在并承担其责`
- review 报告：`6 章 + 知识义务复核 表（10 条 must 逐条落实 + 模式 0 采用）`

### 2.4 两个 Case 的阶段闭环都真实发生过

各阶段 harness + verifier + `check-receipt` 四条件齐、`trace.json` 四份齐。
ISSUE-410 的 `harness_spec|plan|coding|review` **终检时仍全 pass**。

## 三、实跑抓出的缺陷（按严重度）

### D1（BLOCKER，**已修** `b589302e`）· 「已收口」被写成一个值，S5 之后门禁反噬自己

- 现象：AR90004 走完 S5 后，终检重跑 spec harness → `post_check` FAIL
  「story 前置流程未收口（status=**story_written**）」→ spec verdict FAIL →
  `upstream_verdict_gate` 级联把 coding、review 一并判 FAIL → run `cli_failed`。
  **四个先前合法闭环的阶段集体翻红。**
- 根因：契约状态机是 `complete` →（spec）→ `story_written` →`archived`，
  而 `flow-check.mjs` 写的是 `status !== 'complete'`。
- 为什么两个 Case 表现相反：ISSUE-410 **没走 S5**，状态停在 `complete`，反而没中招；
  走对流程的那个中招了。**做对事的被罚，做漏事的没事**——这是最坏的一种判据错误。
- 归属：状态 `story_written` 是子批 C 加的（`119ae04b`），门禁没同步；
  R4 把这段代码原样搬进 `flow-check.mjs` 时没有发现。**R 的判据 KR-4b 只核了「拆前拆后一致」
  ——一致地错，也是一致。**
- 处置：改判为区间 `{complete, story_written, archived}`；台账加 **R04**（夹具取自这次实跑的
  真实契约，去掉单号字面）：bad = `init` 必须报，good = `story_written` 不许报。
  再有人收紧回精确相等，good 侧当场红。

### D2（BLOCKER 级作业书歧义，**未修**）· 本地单跳过 S5，门禁如实拦下

- 现象：ISSUE-410 终态 `target_not_reached`，四个阶段 harness 全 pass，
  唯一失败项是 `story_build_check`：`读不到 ...\ISSUE-410\AR\story.md`。
- 事实：它 spec 闭环后直接进 plan，**S5 整段没做**；AR90004 却自己走了 S5。
- **门禁是对的**：四阶段全绿不代表 story 链交付完整，这是唯一报出「交付件缺一件」的那道。
- **作业书有歧义**：`SKILL.md` 成文节写「spec 闭环之后、**归档之前**」，初始化节又写
  「本地单没有归档环节」。两句合起来，本地单**没有「归档之前」这个时点**，S5 就落空了。
  「本地单交付终点含 `AR/story.md`」那句在初始化节、不在成文节，模型按成文节的时序条件判断时读不到。
- 建议（交维护者定，本轮未动）：成文节触发条件改为「spec 阶段闭环之后」，归档作为后续动作；
  并在该节点名本地单同样要成文。

### D3（**已修** `bfedb22e`）· `measure_run.py` 量到的是一轮，不是一次运行

- run 目录下有两层 `events.jsonl`：run 级汇总在本目录直下，每轮的在 `cli-runtime/<turn>/`。
  原实现 `rglob` 后按字符串排序取第一份，`cli-runtime/…` 恰好排在前面。
- 后果：同一次运行，汇总 1399 条事件、被选中的那一轮 164 条。
  **「读 checker 源码」因此从 19 次被报成 0 次——而目标恰好是 0。**
  会把未达标读成达标的数字，比没有数字更坏（G8 的反面）。

### D4（未修，测试域）· Case 名从 workspace 路径泄漏给被测模型

- `source-conflict-review` 19:28:10 原话：`This suite is named "source-conflict-review".
  ... I suspect they conflict.`
- 隔离 workspace 路径是 `%TEMP%\sw-story\<suite>\source-conflict-review\...`，case id 在路径里。
- 后果：这个 Case 要观测的正是「材料冲突能不能被自己发现」。名字先把答案说了，
  **它找到冲突不再构成能力证据**。
- 建议：workspace 目录名改用无语义标识。

### D5（未修，测试域）· 到达 end_phase 后 run 不转终态

- ISSUE-410 review 已闭环、模型明确回「无进一步待办」，`state.json` 仍是 `awaiting_reply`。
  每次回话它答一句「已结束」，再次进 `awaiting_reply`——**回话不会让它终止**。
- 缺的是：驱动器算不出下一个未闭环阶段时，没有对应的终态动作，把「没话可说」当成了「在等人回话」。
- 宿主处置：停止回话，让 1 小时 `reply_wait_sec` 自然超时（未调 `stop`——TEST.md 规定只响应用户明确要求）。
- 代价：一个完整超时周期 + finalize 推迟。

### D6（未修，契约双源）· 被测模型被迫用 `cp` 维护两份 contracts

- ISSUE-410 收尾总结原话：`framework harness 读 feature 根 contracts.yaml，story 扩展
  post_check 读 plan/contracts.yaml——需要两份同步维护（cp）；只放一处会有一侧报"缺契约"。`
- 为什么要紧：子批 B 的核心是**义务挂在契约实体上**。契约有两份物理文件，义务就有两个落点——
  「同一份契约两处各存各的」正是 B 要消灭的平行账本形态，换了个位置复发。

### D7（未修）· 引文核实把散文行误判成表格行

- ISSUE-410 原话：`散文行里若含 key（如"…+facts_reuse。"）会被误当表格行（毒到 0 字）`
- 形态：`verifier.report.md` 侧的解析按「行内含键」认表格行，一段散文里出现某个 check id
  就被当成该条裁决行，取到空引文判「未裁」。
- 与 R1 的关系：`story-build check ⑥` 是**另一套解析**（固定表头逐行取 cell），
  本轮 43 条裁决没出这个形态。**两侧解析口径不同，本身也该收敛。**

## 四、七项效率度量（G8：只报数，不判 PASS/FAIL）

用修好的 `measure_run.py` 重取。**这些是诊断信息，达标与否由人看数字判断。**

| # | 指标 | 目标 | AR90004 | ISSUE-410 | 批次 3 之前基线 |
|---|---|---|---|---|---|
| 1 | 门禁回环时间占比 | <15% | 脚本未实现该项 | 同左 | 49.3% |
| 2 | 读机制文本（framework/ + doc/extensions/） | ≤20/阶段 | **96 次** | **115 次** | 60 + 40 |
| 3 | **读 checker 源码** | **0** | **19 次** | **22 次** | 9 次 |
| 4 | 同一 check id FAIL 次数 | ≤2 | 1（`knowledge_obligation_substance`） | 未识别到 | 5 |
| 5 | 上下文增量 | ≤150K（**spec 阶段单取**） | 全程 +803K | 全程 +607K | spec +397K |
| 6 | verifier 扩展注入 | ≤15KB/阶段 | 本轮未取 | 本轮未取 | spec 占 prompt 44.3% |
| 7 | `doc/extensions` 非知识层行数 | ≤7500 | **9603**（未达成） | 同左 | 10358 |

**口径警告**：第 5 项脚本读的是整个 run，不是 spec 阶段单取，**不能拿这个数字对 150K 的目标**；
第 1、6 项脚本未产出。三项都要等度量脚本补齐后再取，本轮不下结论。

**第 3 项是最直接的信号，且明确未达成**：19 / 22 次去读 checker 源码，比基线的 9 次更多。
O3 有直接原话佐证（`检查 check-spec 的 scope 校验逻辑`）。作者面通道建起来了，
但**这些形态判据没走通道**——ISSUE-410 自述有七条是「写完才被门禁告知」的：

| 阶段 | 事先不知道的形态 |
|---|---|
| spec | P0 交互 AC 须带 `flows` + 结构化 `checkpoint` + `requirement_ref` |
| spec | `facts.md` 的 `key_inputs_read` 须覆盖 profile 声明的输入 |
| plan | 目录结构须是 `### <模块名>` + 树形代码块 |
| plan | 功能映射表关键文件列必须半角逗号，中文顿号不识别 |
| review | 问题清单表头必须是 `问题描述`；结论须机器可读；`保证等级` 须与 summary 一致 |
| coding | `$r('app.color.*')` 依赖的 `color.json` 须登记进 `contracts.files` |
| coding | presentation 层的 VOC 埋点描述（非 UI 文本）也被算硬编码中文 |

第 2 项（96 / 115 次）与第 3 项是同一件事的两面：通道没覆盖到，就只能自己去翻。

## 五、回灌

| Case | 结果 |
|---|---|
| `pattern-image-review` | `promoted`——源码差异已写入主工程 |
| `source-conflict-review` | `partial_promotion_conflict`——两个 Case 都改了 WalletMain，第二个撞上三方检查的真实冲突，按协议保留双方并记录 |

两个 feature 目录都已回到 `doc/features/`。**回灌的源码改动留在工作区未提交**——
它们是被测模型的产出，是否入库由维护者定。

## 六、结论

**R 的机制成立，判据有一处漏。**

- 正面：S5 的 writer + 裁决者链在 304 单元的真实材料上跑通，三态守恒、裁决核实、
  规约判定表、术语守恒、四红线九项判据全过；引文核实与义务上实体在真实运行里各拦/各用了一次。
- 负面：**D1 是 R 自己的洞**——`flow-check.mjs` 把「已收口」写成一个值，
  导致走对流程的 Case 被罚、漏做的 Case 反而没事。已修并加机械回归（台账 R04）。
  KR-4b 的「拆前拆后逐字节一致」证明不了正确性，只证明了搬运无损：**一致地错，也是一致**。
- 另有五条（D2、D4–D7）不属 R 改动面但由这次实跑暴露，逐条记在 §三，未擅自处置。

**离线基线（修复后）**：台账 **48/48**（新增 R04）、单测 **164 passed + 7 subtests**、
`--phase extensions` PASS 6/6、`node --check` / `compileall` 通过。
