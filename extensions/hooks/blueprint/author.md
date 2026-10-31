# 部件设计 · 知识要求（设计作者）

读者：按 component-design 写蓝图的设计作者。时机：来源发现之前取一次知识任务，写设计时再取一次。

```
node doc/extensions/hooks/shared/knowledge-task.mjs --project-root <工程根> --blueprint <蓝图 id> --action discovery --audience author
node doc/extensions/hooks/shared/knowledge-task.mjs --project-root <工程根> --blueprint <蓝图 id> --action design --audience author
```

## 知识怎样进蓝图

- **项目事实**：设计用到的现有模块、能力、字段与上报渠道，按事实原文写进来源发现的事实，保留出处；缺的事实写明向谁取得。
  现状怎么取、结论怎么写见 `doc/extensions/skills/story/reference/evidence-rules.md`，来源发现之前读。
- **工程现状核对**：材料承诺的能力在工程里有没有、依赖的接口接不接得上，在定决策之前核。已有能力不实、外部依赖缺席，或只能模拟而影响验收的，登记为承载缺口交人定；正常要新写的代码不算承载问题。
- **恢复与兜底路径**：写清谁发起、按什么身份查询、查的是哪个对象、状态以谁为准、结果给谁用，路径挂在承担它的那一方的设计对象上。
- **规约**：每份规约是一个域。与本需求相关的域逐条判断：适用的写明落在哪个设计对象上，不适用的写出使它不适用的需求条件；整域都碰不到写一条域级的不涉及与理由。有争议、要豁免或定不下来的，登记成原生决定或缺口（豁免要有真实授权、理由与补偿），条目指向它。
- **设计模式**：单元怎么切、信号从哪来按 `doc/extensions/skills/story/reference/knowledge/protocol.md`「设计模式」。只在业务单元出现了这个模式的候选信号时判断：选中写条件与理由，并在承担每个角色的设计对象上写角色；有信号却不用写反证；没有候选信号的模式不判。
- **判断的来源**：你依据材料作出的判断保持推断来源；人签过的裁决引用人的原话与记录位置。
- **施工义务**：适用的规约落到真正承担它的设计对象或契约实体上；每个施工单位的契约再把它承担的义务写到实体上，知识正文留在知识文件里。设计覆盖实际要改的每个业务与宿主模块；在宿主模块里只加一条路由或入口也是改动，写进改动边界。

来源发现阶段已成立的判断直接承接到设计，设计中出现新的对象时回到知识任务核一遍相关知识。
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
      - {unit: RET-03, outcome: pending, rationale: 保留期限等运营定, target_refs: [decision:retention-period]}
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

- 相关域的 `items` 覆盖这份规约的每条：`applied` 的 `target_refs` 列承担它的设计对象地址；`not_applicable` 的理由写本需求哪个条件不成立；`pending` 指向登记它的原生决定或缺口。`rationale` 写本需求的具体事实，不抄规约原文。
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
SE 文档里的接口设计格式不固定：读懂采用的 SR 原文，转写成 `blueprint/contracts/se-interfaces.yaml`，本部件的字段映射写同目录 `mappings.yaml`，蓝图契约用 `source_ref` 指向它们。来源包括采用的 SR 原文和接口负责方有记录的逐项确认；来源没给的登记缺口。写法见 `doc/extensions/skills/story/reference/evidence-rules.md`「5. 端云接口转写成契约来源」。候选写好后交主执行者派独立质询，按质询回复修订。
