# 部件设计 · 知识要求（设计作者）

读者：按 component-design 写蓝图的设计作者。时机：来源发现之前取一次知识任务，写设计时再取一次。

```
node doc/extensions/hooks/shared/knowledge-task.mjs --project-root <工程根> --blueprint <蓝图 id> --action discovery --audience author
node doc/extensions/hooks/shared/knowledge-task.mjs --project-root <工程根> --blueprint <蓝图 id> --action design --audience author
```

## 知识怎样进蓝图

- **项目事实**：设计用到的现有模块、能力、字段与上报渠道，按事实原文写进来源发现的事实，保留出处；缺的事实写明向谁取得。
  现状怎么取、结论怎么写见 `doc/extensions/skills/story/reference/evidence-rules.md`，来源发现之前读。
- **规约**：与本需求相关的每条逐条判断。适用的，要求写在真正承担它的设计对象上，并写明验证去向；不适用的，写出使它不适用的需求条件；只有真实授权才写豁免，连同理由与补偿。
- **设计模式**：单元怎么切、信号从哪来按 `doc/extensions/skills/story/reference/knowledge/protocol.md`「设计模式」；列出候选与取舍理由；选中的写明每个角色落在哪个设计对象或流程步骤上；定不下来的登记为未决，写明由谁、在何时定。
- **判断的来源**：你依据材料作出的判断保持推断来源；人签过的裁决引用人的原话与记录位置。
- **施工义务**：蓝图写决定与落点；每个施工单位的契约再把它承担的义务写到实体上，知识正文留在知识文件里。

来源发现阶段已成立的判断直接承接到设计，设计中出现新的对象时回到知识任务核一遍相关知识。

## 知识应用决定的写法

每条激活规约一条决定，模式一个单元一条，写在 `decisions_and_gaps.decisions`，形态以
`doc/extensions/skills/story/contracts/knowledge-application.schema.json` 为准：

```yaml
- decision_id: knowledge-ret-01
  kind: knowledge_application
  status: answered_with_evidence
  owner: design-author
  rationale: 本需求在处理过程中保存临时记录
  provenance: {source_kind: knowledge, source_ref: doc/extensions/knowledge/constraints/<规约文件>.md, observed_at: 2026-09-30T08:00:00Z, evidence_strength: inferred, extraction_method: read_and_apply}
  verification_refs: [view:logical/node:record-store]
  knowledge: {kind: constraints, form: entries, unit: RET-01, source_sha256: "sha256:3f5e0b8c9d1a2e4f6071829304a5b6c7d8e9f0a1b2c3d4e5f60718293a4b5c6d", outcome: applied, requirement: 处理完成后清除临时记录, target_refs: [view:logical/node:record-store]}
```

- `source_ref`、`source_sha256`、`unit` 照抄知识任务第 2 块；原文之后变了按新原文重判。
- 规约：适用 `applied` 写 `requirement` 与承担它的设计对象地址；不适用 `not_applicable`（`status` 同为 `not_applicable`，理由写哪个条件不成立）；豁免 `waived` 带 `waiver: {reason, compensation, authority_ref}` 指真实授权，红线不能豁免。
- 模式：`selected` / `adjusted` 写 `roles: [{role, target_ref}]`，`rejected` 写反证；定不下来写 `pending`，`status` 为 `open_decision` 或 `blocker` 并登记原生缺口。
- 事实用到的知识单元写在事实的 `value.knowledge: {unit, form, source_sha256}`，读到的内容与用途写 `value.observation`。

## 原生字段放不下的精确内容

已形成的设计对象（节点、运行数据流、契约）里，原生字段表达不了的精确内容——数据的有效期与清理、配置项取值、埋点统计点、专项设计——写进蓝图顶层的 `story_details`，经原生修订生效：

```yaml
story_details:
  - id: detail-balance-cache      # 稳定标识
    kind: data_policy             # data_policy | configuration | event | special_design
    title: 余额缓存有效期
    body: |                       # 完整 Markdown，Story 逐字呈现
      余额缓存 5 分钟，切换账号时清空。
    evidence_refs:                # 它所属的设计对象地址与依据
      - view:runtime/flow:balance-cache
```

原生字段已经表达的不重复写进 `body`。埋点（`event`）的统计点写成表头含「统计点」的表，施工单位的 plan 按统计点名逐点落实。前三类投进 Story 附录，专项设计由成文作者在讲它的那一章原样呈现。还没形成施工值的写明由哪个阶段定。

## 端云接口的转写
SE 文档里的接口设计格式不固定：读懂冻结的 SR 原文，转写成 `blueprint/contracts/se-interfaces.yaml`，本部件的字段映射写同目录 `mappings.yaml`，蓝图契约用 `source_ref` 指向它们。原文没给的不补，登记缺口。写法见 `doc/extensions/skills/story/reference/evidence-rules.md`「5. 端云接口转写成契约来源」。
