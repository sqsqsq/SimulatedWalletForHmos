# 部件设计 · 知识要求（设计作者）

读者：按 component-design 写蓝图的设计作者。时机：来源发现之前取一次知识任务，写设计时再取一次。

```
node doc/extensions/hooks/shared/knowledge-task.mjs --project-root <工程根> --blueprint <蓝图 id> --action discovery --audience author
node doc/extensions/hooks/shared/knowledge-task.mjs --project-root <工程根> --blueprint <蓝图 id> --action design --audience author
```

## 共同设计要讲清的关系

蓝图是共同设计的唯一权威，Story、Review 与施工单位都从这里取。准入之前逐类核：

- **目标与规则**：业务目标（量化指标、配额、时限）与关键规则写进承担它的设计对象或原生决定，读者不翻原件也读得到数值与条件；来源指针只说明出处。
- **身份与状态**：每个业务对象用什么身份标识、状态由谁维护、以哪一方为准。状态会被另一端或时间改变的，界面与后续操作按取得的当前状态决定去向。
- **数据的生产与消费**：页面或下游用到的每个字段，写清谁产生、经哪个接口或事件到达、谁消费；入口 → 身份 → 列表或详情 → 字段这条链在哪里接不上，就在哪里登记缺口。接口或字段的名字存在，不等于这条链成立。
- **失败、未知与恢复**：明确失败、结果未知（超时、没有有效回包）与过期状态分开设计。重试、新建与撤销写出真实合同支持的前提与请求身份：重发同一请求带原请求的身份，丢了身份的新请求是一次新请求；结果未知时按查询结果定去向。恢复路径写清谁发起、按什么身份查询、查的是哪个对象、状态以谁为准、结果给谁用，挂在承担它的那一方。
- **未定与冲突**：有效人答要求等结论的动作，设计里保持等待；各选项都有的共同功能照常设计，只属于某个选项的行为留在原生决定里。原材料之间的真实冲突登记成原生决定，写出各方来源。
- **工程现状与外部依赖**：材料承诺的能力与工程现状逐项核，按「查证工程 → 定本期承担对象与改动边界 → 写可观察的验收」推进。本次要新写的代码、页面、内部登记与取号是工程落实，写进设计对象与改动边界；工程里没有现成页面或封装时，由本部件设计新写的部分并给出验收，工程方案是设计职责，业务方提供的是业务要求。查证后外部能力确实不足、依赖方缺席，或只能模拟而影响验收的，登记为承载缺口交人定，写明负责方、受影响的路径与解除条件；平台能力没有依据的照实写未证实。外部动作由别的部件执行时，本部件受它影响的状态、展示与恢复仍写进设计。恢复能力按材料与工程里真实存在的接口设计。
- **统计设计**：统计是共同设计的一部分，在蓝图里写成。有统计需求时每个业务指标一项埋点明细（写法见下文「原生字段放不下的精确内容」），讲清指标定义、分子与分母、取数责任方、结果何时由谁获知、在哪个动作上取证，以及工程里已有覆盖还是新增；施工单位的 plan 只落实具体事件编号、登记文件与上报方法。
- **人读图**：时序与角色图由原生按蓝图的步骤与同名派生结论生成。写完重新渲染评审投影并读成品：图里该有的参与方、先后与责任边看得到；看不到的回蓝图补步骤与派生结论，投影只由原生生成。

## 知识怎样进蓝图

- **项目事实**：设计用到的现有模块、能力、字段与上报渠道，按事实原文写进来源发现的事实，保留出处；缺的事实写明向谁取得。
  现状怎么取、结论怎么写见 `doc/extensions/skills/story/reference/evidence-rules.md`，来源发现之前读。
- **规约**：每份规约是一个域。与本需求相关的域逐条判断：适用的写明落在哪个设计对象上，不适用的写出使它不适用的需求条件；整域都碰不到写一条域级的不涉及与理由。有争议、要豁免或定不下来的，登记成原生决定或缺口（豁免要有真实授权、理由与补偿），条目指向它。
- **设计模式**：单元怎么切、信号从哪来按 `doc/extensions/skills/story/reference/knowledge/protocol.md`「设计模式」。只在业务单元出现了这个模式的候选信号时判断：选中写条件与理由，并在承担每个角色的设计对象上写角色；有信号却不用写反证；没有候选信号的模式不判。
- **判断的来源**：你依据材料作出的判断保持推断来源；人签过的裁决引用人的原话与记录位置。
- **设计对象的出处**：设计对象的 `provenance.source_ref` 指它所依据的登记材料、有效人答或工程文件；本次授权内形成的设计记录放在蓝图目录（`blueprint/`）下，设计对象可以引它。承载 typed 内容、被原生要求设计权威的那个对象，按真实依据声明 `evidence_strength`，其余对象保持原来的来源与强度；设计对象之间的关系写成原生的 design_refs、关系与决定。外部接口与上游保证仍以原件和负责方确认为准。
- **施工义务**：适用的规约落到真正承担它的设计对象或契约实体上；每个施工单位的契约再把它承担的义务写到实体上，知识正文留在知识文件里。设计覆盖实际要改的每个业务与宿主模块；在宿主模块里只加一条路由或入口也是改动，写进改动边界。

来源发现阶段已成立的判断直接承接到设计，设计中出现新的对象时回到知识任务核一遍相关知识。
蓝图里某类对象（埋点、配置、数据策略）还空着，要按业务材料与适用知识判断：本需求涉及就在蓝图设计它，确实不涉及写出本需求的具体条件。登记了缺口的义务仍要在设计里表达受影响的路径，缺口说明的是外部未决，当前阶段能设计的部分照常设计。
准入之前双向核来源（知识任务第 1 块列出候选采用的每份原件）：先逐份读原件，条件、行为、边界、异常与责任各找到承担它的设计对象，没有承担者的落实成对象或登记原生缺口，没有验收编号不是略过的理由；再逐个设计对象回原件、工程事实与人签核出处，材料事实、人签与你的推断分开，仍未决的写成未决、不写成定案。init-analysis 只作定位索引。

## 知识在蓝图里的写法

形态以 `doc/extensions/skills/story/contracts/knowledge-application.schema.json` 为准。

**知识输入身份**：知识任务第 3 块给出这一轮的 `knowledge_context`，原样写进 `discovery.inputs.knowledge_context`。它记设计收到的是哪一版知识；知识之后增删或改了，重取任务，核受影响的事实与设计对象，原生修订后换成新的一份。

**适用性写成原生事实**（`discovery.facts`），一份知识一条，`provenance.source_ref` 指知识文件：

```yaml
- fact_id: knowledge-retention
  subject: knowledge:retention
  value:
    knowledge_kind: constraints
    items:
      - {unit: RET-01, outcome: applied, rationale: 本需求在处理过程中保存临时记录，处理完成后清除, target_refs: [view:logical/node:record-store]}
      - {unit: RET-02, outcome: not_applicable, rationale: 本需求不导出记录, target_refs: []}
      - {unit: RET-03, outcome: pending, rationale: 保留期限等运营定, target_refs: [view:logical/node:record-store, decision:retention-period]}
  provenance: {source_kind: knowledge, source_ref: doc/extensions/knowledge/constraints/<规约文件>.md, observed_at: 2026-10-30T08:00:00Z, evidence_strength: inferred, extraction_method: read_and_apply}
- fact_id: knowledge-export
  subject: knowledge:export
  value: {knowledge_kind: constraints, outcome: not_applicable, rationale: 本需求没有任何对外导出}
  provenance: {source_kind: knowledge, source_ref: doc/extensions/knowledge/constraints/<另一份规约>.md, observed_at: 2026-10-30T08:00:00Z, evidence_strength: inferred, extraction_method: read_and_apply}
- fact_id: knowledge-branching
  subject: knowledge:branching
  value: {knowledge_kind: patterns, outcome: selected, rationale: 刷新有三条以上互斥分支，各分支的前置检查不同}
  provenance: {source_kind: knowledge, source_ref: doc/extensions/knowledge/design-patterns/<模式文件>.md, observed_at: 2026-10-30T08:00:00Z, evidence_strength: inferred, extraction_method: read_and_apply}
```

- 相关域的 `items` 覆盖这份规约的每条：`applied` 的 `target_refs` 列承担它的设计对象地址；`not_applicable` 的理由写本需求哪个条件不成立；`pending` 指向登记它的原生决定或缺口，已知受影响的设计对象一并列上——施工单位按设计对象接收它；只列决定或缺口表示承担对象还没定，每个施工单位都收到它去核。`rationale` 写本需求的具体事实，不抄规约原文。
- 用到的项目事实照常写成事实，`provenance.source_ref` 指事实文件（用到某一面或某一篇写 `#<面名>`）。

**义务与角色写在承担它的设计对象上**：

```yaml
nodes:
  - node_id: record-store
    must:
      - {text: 处理完成后清除临时记录, source_ref: "doc/extensions/knowledge/constraints/<规约文件>.md#RET-01", verify: ut}
    pattern_roles:
      - {pattern_ref: doc/extensions/knowledge/design-patterns/<模式文件>.md, role: 协调者}
```

`must.source_ref` 指适用的那一条规约条目，`text` 写这个对象在本需求里具体做什么，`verify` 按规约声明的执行体定；`pattern_roles.role` 取模式声明的角色。

- 适用条目与义务两头对上：条目 `target_refs` 里的每个设计对象都写出自这一条的 `must`，挂 `must` 的对象都列在那一条的 `target_refs` 里。处置以「（评审动作）」开头的条目由评审承接，不写 `must`。
- 承担者是做这件事的节点、运行数据流、关系或契约；整份蓝图、整个视图只划范围，不承担义务与角色。
- 选中的模式，它在 frontmatter `roles` 里声明的每个角色都要有承担者，`optional_roles` 按需求用；角色可以分在不同施工单位的设计对象上，各单位承接落在自己设计引用内的那些。
- **共同验收**：适用条目要求的可观察行为，在承担它的设计对象上写成原生验收（`acceptance.criteria` / `boundaries`），`knowledge_refs` 列与 `must.source_ref` 同一条目引用；统计指标、事件与资源义务一样在质询之前写成对象上的验收、`must` 与真实的事件明细。只交业务送审、不进 spec 时也在蓝图写成，施工单位的 spec 复用它、只做有据的局部细化。A 调用 B 时，B 自己的义务留在 B，A 要满足的调用条件写在 A 的 `must` 与验收上。

## 原生字段放不下的精确内容

已形成的设计对象（节点、运行数据流、契约）里，原生字段有等价位置的写在原生字段；原生字段表达不了的精确内容——数据的有效期与清理、配置项取值、埋点统计点、专项设计——写进蓝图顶层的 `story_details`，经原生修订生效：

```yaml
story_details:
  - id: detail-balance-cache      # 稳定标识
    kind: data_policy             # data_policy | configuration | event | special_design
    title: 余额缓存有效期
    body: |                       # Markdown：精确值、来源、关系与业务语义
      余额缓存 5 分钟，切换账号时清空。
    evidence_refs:                # 它所属的设计对象地址与依据
      - view:runtime/flow:balance-cache
```

原生字段已经表达的不重复写进 `body`。埋点（`event`）一项明细是一个指标：`title` 写指标名，`body` 按激活的上报知识写起止、分子与分母、观察窗口、谁获知结果、随事件带什么与去重由谁负责，本端拿不到的写由谁统计，再接表头含「统计点」的统计点表；施工单位的 plan 按统计点名逐点落实。没有统计需求、也没有适用的上报义务时不写埋点明细。配置与埋点投进 Story 附录；数据策略与专项设计由成文作者按读者要回答的问题组织进讲它的那一节，精确值、来源、关系与业务语义与这里一致，措辞与组织由成文作者定，这里不预写 Story 正文。还没形成施工值的写明由哪个阶段定。

## 端云接口的转写与独立质询
SE 文档里的接口设计格式不固定：读懂采用的 SR 原文，转写成 `blueprint/contracts/se-interfaces.yaml`，本部件的字段映射写同目录 `mappings.yaml`，蓝图契约用 `source_ref` 指向它们。来源包括采用的 SR 原文和接口负责方有记录的逐项确认；来源没给的登记缺口。转写的权威来自原文，映射是本部件的设计，蓝图是共同设计；三者对不上时先回原文判哪一侧错，再改错的那一侧。写法与改法见 `doc/extensions/skills/story/reference/evidence-rules.md`「5. 端云接口转写成契约来源」。候选写好后交主执行者派独立质询，按质询回复修订；登记质询时原回答与你的修订分开写，改了设计内容的交质询方复核修后对象。
