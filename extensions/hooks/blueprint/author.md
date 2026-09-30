# 部件设计 · 知识要求（设计作者）

读者：按 component-design 写蓝图的设计作者。时机：来源发现之前取一次知识任务，写设计时再取一次。

```
node doc/extensions/hooks/shared/knowledge-task.mjs --project-root <工程根> --blueprint <蓝图 id> --action discovery --audience author
node doc/extensions/hooks/shared/knowledge-task.mjs --project-root <工程根> --blueprint <蓝图 id> --action design --audience author
```

## 知识怎样进蓝图

- **项目事实**：设计用到的现有模块、能力、字段与上报渠道，按事实原文写进来源发现的事实，保留出处；缺的事实写明向谁取得。
- **规约**：与本需求相关的每条逐条判断。适用的，要求写在真正承担它的设计对象上，并写明验证去向；不适用的，写出使它不适用的需求条件；只有真实授权才写豁免，连同理由与补偿。
- **设计模式**：列出候选与取舍理由；选中的写明每个角色落在哪个设计对象或流程步骤上；定不下来的登记为未决，写明由谁、在何时定。
- **判断的来源**：你依据材料作出的判断保持推断来源；人签过的裁决引用人的原话与记录位置。
- **施工义务**：蓝图写决定与落点；每个施工单位的契约再把它承担的义务写到实体上，知识正文留在知识文件里。

来源发现阶段已成立的判断直接承接到设计，设计中出现新的对象时回到知识任务核一遍相关知识。

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

原生字段已经表达的不重复写进 `body`。前三类投进 Story 附录，专项设计由成文作者在讲它的那一章原样呈现。还没形成施工值的写明由哪个阶段定。
