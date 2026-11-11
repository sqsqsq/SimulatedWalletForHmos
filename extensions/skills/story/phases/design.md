# `/story` 链 · 交给设计、成文与交付

> 读者：走 `/story` 链的主 agent。时机：本轮材料与范围确认之后，一直到交付选择。每一步做什么由
> `story_flow.py status` 的 `next` 与 `action` 给出，本页讲这些步骤为什么这样走、各自交什么。

## 一、顺序

```
材料与范围确认
  → component-design 按材料索引登记的版本完成可评审设计与独立质询，生成评审投影
  → story-build skeleton → 写作设计 → 逐章 chapter → 回看 → check
  → 独立审查（story-build review：定稿、准备派审载体 → 原样派审 → 核结果）→ story_flow.py story 登记
  → check --deliver 交付门 → 交付选择
  →（授权覆盖时）施工单位设计准备 → 各施工单位的 Spec 与 Plan → 最后交接再跑一次交付门
```

`/story` 做到交付门；已有明确授权就按其范围继续，还没指定后续目标时问一次交付选择（授权定义在 SKILL「推进契约」）。业务审批与实施授权分开对待。

## 二、交给设计

范围定了，`status` 给出 `design_blueprint`，就进原生 component-design。没有单独的交接命令：材料已经导成当前阅读稿 `RR/prd.md`、`SR/design.md`、`AR/design.md` 等，每个版本留存在 `.backups/local/` 并登记在材料索引（会议在 `AR/story-src/meetings/`），人的答复在生效时就导出在 `AR/story-src/answers/人工答复-v<N>.md`，设计直接读它们。

- **当前有效人答是必读**：问法与原话都在里面，分「当前有效」与「需结合上下文」两组。它不取决于你有没有把它写进需求条目或设计引用；答复确实规定了目标或边界时，原生范围要反映那条约束。
- **范围与兄弟单**：`status` 里本轮的定位（本单承载什么、同一系统设计下的兄弟单承载什么、协作方与不做项）和范围答复，写进原生范围与边界，再由 Story 讲给评审人。

1. **蓝图与需求同根**：蓝图标识就是需求标识，canonical 蓝图在 `<需求目录>/blueprint/`。组件由原生设计按工程上下文认定，写在蓝图里。已有蓝图按原生规则继续，不重复创建。
2. **需求条目只写真实义务**：需求条目（原生 `current_scope_items`）只写真实的需求、目标、约束与风险，并在设计里追溯。把它们的身份、类别、来源文件与权威写进一个 JSON 文件，跑 `import_sources.py --feature <需求> --scope <条目文件>`：

   ```json
   [
     {"item_id": "request-main", "kind": "requirement", "source": "RR/prd.md#<节>",
      "authority": {"owner": "需求负责人", "formality": "formal_requirement"}},
     {"item_id": "carry-boundary", "kind": "invariant", "source": "AR/story-src/answers/人工答复-v<N>.md",
      "authority": {"owner": "需求负责人", "formality": "formal_requirement"}}
   ]
   ```

   - `source` 是需求相对路径，可带 `#片段`；只能引材料索引 `files` 登记的文件（材料版本的原件、阅读正文与图，人工答复，会议原件、raw、纠偏与阅读件）。当前阅读稿 `RR/prd.md`、收件箱里的原件这类会换版的当前位置可以直接写，脚本把它换成此刻对应的稳定文件（`files` 里那一行的 `reference`），输出的条目指稳定文件，片段照旧。
   - 例子里第二条是人工答复规定了承载边界才写的；人答本身不需要每条都成为条目。
   - `kind` 取 requirement / goal / invariant / high_risk。来源没分类的 `formality` 写 `unspecified`，由人在设计入口确认。
   - 脚本按材料索引补工程相对路径、原始字节摘要与 provenance，输出原生需求条目 `current_scope_items`，蓝图的 `discovery.inputs.current_scope_items` 按它写。
   - 条目来自需求系统取得的来源时，脚本同时写原生来源物化信封 `blueprint/requirement-source-materialization.json` 并过原生来源检查；蓝图还没建立时用 `--component <组件>` 给出原生设计认定的组件。本地来源只输出条目。
   - 失败时什么都不写，按报错补齐后重跑。
3. **支撑材料按真实引用**：背景说明、系统设计里的约束来源、界面图、会议纪要等支撑材料，在用到它的事实、设计对象、决定或合同对象的 provenance 里引用工程相对路径，不为它造需求条目。引用写稳定文件：读的是当前位置时，到 `AR/story-src/materials.json` 的 `files` 里找这个路径那一行，引它 `reference.path` 指的那一份，例如当前稿那一行是

   ```json
   {"path": "RR/prd.md", "source_id": "draft:RR/prd.md", "version": 2, "reference": {"path": ".backups/local/RR/prd-聚合-v2.md", "sha256": "…"}}
   ```

   支撑引用就写 `<需求目录>/.backups/local/RR/prd-聚合-v2.md#<节>`。需求条目与这些引用命中的登记版本，就是设计采用的版本，之后材料换版也仍指这一份；没被引用的材料只能说「设计未见引用」，是有据不用还是漏了依据由质询与审查核。
   合同各段（operation、DTO 与字段、mappings、errors、idempotency、nfr）的 `source_ref` 指你转写的接口契约（`blueprint/contracts/` 下，写法见证据规则「5. 端云接口转写成契约来源」）：它是设计产物，留在原位、不进材料索引，指针与内容由原生逐段核。别的设计对象要指某一段接口契约，就照抄那一段的 `source_ref`；接口的原始出处写在合同对象自身与转写各段的 provenance 里。
4. 之后取得的新版本不自动进入设计：要不要采用由 update 判断，采用就改相应的条目或引用。Story 材料表在同一来源行写清「取得 v2、设计引证 v1」与原因。
5. 要重拍范围先 `story_flow.py reopen`，范围重新定了再按新范围同步需求条目与边界。

## 三、设计

蓝图由 Framework 的 component-design 建立、质询与调和。请求 `/component-design <蓝图>` 时按本次授权写终点：

- 只到 Story，或还没指定后续目标：写明「完成可评审设计与独立质询，本次不做施工单位准备」，做到生成评审投影为止。
- 已有明确授权到完整设计交接、实现方案或完整实现：写明「完成可评审设计与独立质询；准入后按 change-unit-progression 设计准备段完成施工单位设计准备，不启动施工」。
  蓝图准入了就在首次定稿 Story 之前做完这一段，Story 按准备后的蓝图写；没准入先按草稿成文，施工单位设计准备在准入后按第六节做。

准入由原生判定，草稿也可以成文与业务送审，准入状态与原生问题照实披露：

- 来源是登记的材料与当前有效人答：业务的条件、行为与责任从原件与人答取，人签以 `AR/story-src/answers/人工答复-v<N>.*` 的导出为准。用到哪份就在相应的条目或 provenance 里引用它。
- 设计动手前取作者的知识任务，入口见 story-knowledge Skill 与 `hooks/blueprint/author.md`。任务给的知识输入身份写进蓝图，知识的适用性写成蓝图事实，适用规约的义务与模式角色写在承担它的设计对象上。
- 原生字段表达不了的精确内容写进 `story_details`，写法见 `hooks/blueprint/author.md`。
- 工程缺项与外部依赖按 `hooks/blueprint/author.md`「工程现状与外部依赖」定责任；端云接口的外部协议转写只收原件或负责方逐项确认的内容，规则见证据规则「5. 端云接口转写成契约来源」。
- **独立质询**由你（主执行者）派给宿主的隔离子代理。每次派发都先渲染当前人读稿（设计职责跑原生 `check:component-blueprint --write-review --json`，
  得到 `component-blueprint.review.md`），再取质询任务（`--action questioning --audience reviewer`），把任务全文与被评候选按它第 7 块给的位置原样存好；
  然后按本次的真实情形派发：
  - **首次质询**：把第 7 块的首读载体原样交给子代理——只有人读稿、原生八问、阅读规则和之后读的任务路径，不附任务正文、来源或作者判断；
    子代理答完八问再读任务、canonical 蓝图、原件与人签核原生质询范围。
  - **同一读者复核修订**：设计负责方按原生规则改完设计并重渲人读稿后，用前次真实调用返回的会话 ID 与前次原回复路径，经宿主的续话工具
    （例如 DSH 的 `send_message({agent_id, message})`）向原读者发下面的复核消息，尖括号换成本次真实路径，末行取第 7 块给的正文行范围；不发首读载体：

    > 请你作为参与过本蓝图上一轮质询的独立读者，复核当前修订。当前被评候选：〈本次 candidate〉；当前人读稿：〈人读稿〉，正文为现工具确定的第 1—〈末行〉行；当前核源任务：〈本次 task〉；你的前次原回复：〈原 reply〉；本次最终回复保存位置：〈本次 reply〉。
    > 先通读当前正文，核原报告的问题和修订行为在导读、流程、恢复及待决等处是否一致；未修改且本轮已读的正文不重复读。随后只对原发现及实际受影响要求回查原件、有效人答、事实和精确验收，不重做完整八问、全需求/全源码或整套架构评审。
    > 当前任务的原生 scope 是结果覆盖范围，不是要求重新全文阅读每份来源。未受影响项由你确认原结论/证据仍适用，按原生必需格式给出当前结果；受影响项给实际核查后的回答、依据和处置。沿原生要求引用真实事实及当前不变声明的依据，原报告可说明复核来龙去脉，不能替代原生要求的证据。原报告的实际位置可引用，不编造锚点；作者不能代你把旧结果改签给新对象。只读、不写文件、不改蓝图；最后返回你本次完整的最终回复，不以进度通知或摘要替代。
  - **当前设计、依据与正文都没变且本轮已核**：沿用已有的有效结果，它仍须符合原生当前性；读取状态、保存质询登记或文件哈希本身的变化不另起质询。
  - **原读者不能续话或原回复取不到**：先用宿主已有的能力取回会话与原回复；仍取不到时，对当前修订对象按首次质询另请隔离读者，
    首读前不交旧结论或作者摘要，回复如实说明原读者与原报告的情况；原报告留作追溯，已知缺口照列，不宣称继承旧复核。

  子代理只读、不改蓝图。最终回复先 UTF-8 原样存到当次的 reply 并读回；设计负责方再逐项处理质询提出的问题（要人定的问人），
  写原生 `review_summary.questioning`，`provider_id` 写这次子代理调用的身份，跑原生校验。各项的 `answer` 与 `evidence_refs`
  照质询者对所审候选的原回答登记；你为它改了什么写进设计对象与修订说明，修后对象的结论来自复核回复；只改表达不产生新的设计 revision。
  蓝图回复按原生质询合同登记，Story 的 review prepare/check 只接收 Story 审查。
  接口转写与蓝图对不上时先回原文判哪一侧错，改法见证据规则「5. 端云接口转写成契约来源」的「对不上时改谁」。
  宿主没有隔离子代理时，停在质询这一步：向人说明需要一个隔离的质询者，质询完成后才进入成文。

蓝图读不出、需求条目与设计依据都没有引用本需求登记的材料、引用了没登记的文件，或投影与当前 revision 对不上时，`status` 停在等设计，成文不起手。蓝图是草稿、未准入不挡成文：准入状态与原生问题由 `skeleton`、独立审查任务与交付门照实带出。只查看、重入或改表达不产生新的设计 revision。
单独核蓝图状态用 `node doc/extensions/hooks/shared/framework-access.mjs --project-root <根> --action blueprint --blueprint <需求> --purpose draft --consume <需求> --summary`：
同一次完整读取与校验，返回准入、引用、问题、投影与消费结果，不带蓝图正文；设计内容读 canonical 蓝图或评审投影。

## 四、成文

成文方法见 [`phases/story-write.md`](story-write.md)。Story 按当前蓝图写：草稿的原生问题涉及的业务事实写成待定或限制，不写成已定。

- 附录的配置与埋点由 `story-build project` 从蓝图投影，要改投影内容就回蓝图修订。
- 附录的端云接口、数据存储与规约由你按蓝图写业务摘要（写法见 `story-write.md` 的附录一行）；写作设计骨架里给这几节写
  `- 依据：`，注明蓝图 revision 与原生地址（如 `contract:<id>`），附录提交时核这些地址指得到当前蓝图的对象。
- 完整技术契约在设计参考——同根蓝图的原生评审投影 `blueprint/component-blueprint.review.md`：你不写它、不搬运全文，设计要改回蓝图。它只在系统要求或本单已请求时随交付，本单读者核对与施工要用的精确事实写在附录，读者手上只有 Story 与 Review 也查得到。
- 蓝图里没有的类别，先按业务材料与适用知识判断本需求涉不涉及：涉及而蓝图没设计的，回蓝图补设计；确实不涉及的在那一节写「不涉及：<依据>」，依据是本需求的具体条件。术语起始行是蓝图里确认过的术语，解释由你从材料写。
- 材料清单由你写成一张「材料 | 来源 | 贡献」表：一行一份阅读稿，来源列列齐合成它的原件与采用版本，写它贡献了什么，没采纳的写原因（写法见 `story-write.md` 的附录一行）。
- 蓝图 `story_details` 里的专项设计写在讲它的那一章，表达由你组织，精确值、引用与来源与蓝图一致。专项内容本身有错或含混，回蓝图修订，不在 Story 补一段相反的解释，也不留给施工单位改共同设计。

## 五、独立审查、登记与交付

1. **定稿并准备审查**：`story-build check` 通过之后，先按宿主实际可用的工具说明核有没有能接收自足只读任务的隔离读者
   （DSH 与已物化的宿主模板里的本地只读审查入口可以；只收阶段 JSON 请求的阶段 verifier 不行），再按核到的情况跑
   `story-build review --action prepare`：有可用读者带 `--reader task`，没有带 `--reader unavailable --reader-reason "<实际缺什么>"`。
   它先把审查对象定成最终版（附录重投、编号、渲染 `AR/review.md`、全篇结构检查），再写审查任务 `AR/story-src/review/task.md`，
   定下这一次的材料键、报告目录（默认 `doc/reports/story/<需求>/<材料键前 16 位>/`，与需求目录分开；可用 `--report-dir` 指定，
   首次准备定下后同一份材料一直沿用）与这一份回复的位置，生成派审载体 `AR/story-src/review/dispatch.md`（输出里的 `dispatch_text`）。
   最近一份可消费的回复正是当前材料且是 pass / warn 时输出 `reused`，直接核结果。之后改了任何被审材料，重新 prepare。
2. **派审**：把 `dispatch_text` 原样作为隔离读者的任务交出，不增删、不改写。首次派审载体请读者先只读 Story 做首读，再读审查任务核源；
   已有原报告时载体写明这是复核（复核优先交给原读者，按原报告的问题与这一版改动的实际影响核），上一份回复不能接收时写明是补正。
   你不预置结论，也不替读者决定只核哪一部分。读者只读，它这次的最终回复就是 Story 报告。
   等这次派审的完成回复（启动确认与中途进度不是报告），把回复正文用文件写入动作原样存到载体给的回复位置：UTF-8，不加前后文字、不改换行，宿主的外层包装不进文件；
   存完读回一遍，与回复正文逐字相同。那份文件就是审查原件，之后你只读它；向人可以概述审查结论，概述不写回原件。之前的回复保留。
   回复不合格由读者按新载体补正，你只搬运。拿不到完整的最终回复、或存不成原样时，停下向人说明原件交接的缺口——你手写或缩写的回复不是审查原件。
   给了 `--reader task` 而工具拒收这份任务时，不改投只收阶段请求的工具：保留拒收的返回，以 `--reader unavailable` 写明这个事实重新 prepare，或交给已有的可用独立会话。
3. **接收并核结果**：回复落盘后先重跑同样参数的 `story-build review --action prepare` 接收它（开头两行合格就记下原样字节的摘要，之后的改动由此识别），
   再跑 `story-build review --action check`，它只读核审的是不是现在这份、回复是不是原样、读者写的结论是什么：

   | 结果 | 你做什么 |
   |---|---|
   | pass | 登记，交付 |
   | warn（只有非阻断建议） | 读原样报告里的建议作一次处置：指出事实或范围问题的，回它的责任方改；不影响正确与完整的表达偏好可以保留，写一句理由。决定采纳的按实际影响面一次改完，重新 prepare 交读者复核。处置写进交付说明（update 时写 update-notes），登记交付；不为清空建议再改再审 |
   | fail | 读原样报告里的发现，按牵涉的业务决定修：决定来源（材料、人签、决策登记）→ 蓝图里承接它的设计对象（由设计职责按原生规则修订、交原质询者复核）→ Story、Review 与验收，凡写着这项决定的地方一并改到同一结论；只是表达问题的改章草稿。同一轮的修改集中改完再重新 prepare，按新载体交读者复核 |
   | report_missing | 按派审载体派审 |
   | report_unreceived | 回复在、还没接收：重跑 prepare 接收，再 check |
   | report_invalid | 回复开头两行不合格时原回复留在原处，你不补字、不改字；重新 prepare，新载体带着原回复与原因交读者补正。最近接收的原件被改或不在时，恢复宿主保存的原样，恢复不了就重新 prepare 交读者给新回复 |
   | subject_stale | 准备之后被审材料变了：重新 prepare，按新载体再派审 |
   | input_invalid | 派审载体缺失或与准备记录对不上时重跑 prepare；准备记录本身读不出时按诊断恢复原记录，不删掉它重来；审查对象缺来源时停下，向人报告缺哪份、向谁取得 |
   | unreviewed | 本次准备时没有可用的独立读者：prepare 已把未审披露写进 Story 交付章与 Review 题头，可以登记与交付；不问人要免审授权，交付说明照实写本版未审 |

   最近一份可消费的回复判了 fail、之后还没有新的可消费回复时，结果是 fail（已知必修未复核）：改稿、补正失败或改成 `--reader unavailable` 都不会把它变成未审，
   要等读者复核给出新的结论。最近一份可消费的 pass / warn 正是当前材料时直接复用，换了宿主也不必重审。
4. **登记**：`story_flow.py story`。它核结构检查、这一份的审查结果（pass、warn，或宿主没有审查能力时的 unreviewed）与成文依据
   （蓝图引用、设计采用的来源、知识摘要、材料索引摘要，以及 Story、Review、决策登记与写作设计的原始字节指纹），通过后记下新依据。
5. **交付门**：`story-build check --deliver`，核交付的是登记的那一份、依据（含蓝图）没变、审查结果仍可消费。登记或交付门报错时，按报错回到对应步骤。
6. **交付选择**：交付门通过后，已有明确授权就按其范围继续，还没指定后续目标时问一次交付选择，并按停等表记下人的选择：
   - 送审：仅系统需求，走 `/story archive <AR>`，Story 作正文、Review 作附件；系统要求设计参考（取材回执 `delivery_requirements.design_reference`）或本单已有交付请求时，再加设计参考（蓝图的原生评审投影原字节）附件；交付集合里的各件都读回一致才登记；
   - 完整设计交接：按第六节第 1 步完成施工单位设计准备，不启动施工，再做第 4 步最后交接；
   - 实现方案：按第六节第 1—4 步，为每个施工单位完成适用的 Spec 与 Plan，止于 Plan（只授权 Spec 或只授权 Plan 的按第六节的表）；
   - 完整实现：在授权范围内接续设计准备，再按 `framework/docs/operations/project-entry.md` 的完整交付入口以本次真实请求接续，由同一完成协调器推进；
     原生没有支持或本扩展没验证过的组合，按原生返回如实说明边界；
   - 暂不推进：停在这里，之后从 `story_flow.py status` 续上。

   `AR/review.md` 是首版，评审人在人工区表态。你不代填，评审回来由 `/story update` 承接。

## 六、交付门之后：施工单位设计准备与 Spec/Plan

只在授权覆盖施工单位设计、Spec 或 Plan 时做；只要 Story 的不建施工单位。命令都在 `framework/harness` 下执行，`<根>` 是消费工程根。

| 已有授权 | 做哪几步 | 第 2 步的 `--requested-phases` |
|---|---|---|
| 完整设计交接 | 第 1、4 步，不声明阶段请求 | — |
| 只要 Spec | 第 1—4 步 | `spec` |
| 只要 Plan | 第 1—4 步 | `plan` |
| 实现方案（到 Plan） | 第 1—4 步 | `spec,plan` |

1. **施工单位设计准备**（成文前已做完的跳过）：蓝图准入后按 change-unit-progression 设计准备段，把分解候选按原生 `[{providerId, artifact}]` 写进
   `<需求目录>/blueprint/change-unit-candidates.json`。每个候选的 `design_refs` 写它实际承担的设计对象与采用的必需决定；整批候选合起来认领原生派生的必需设计义务，
   依赖由原生派生，别的施工单位的义务不抄进来。原生报 `change_unit_design_closure_incomplete` 时，按它点名的承载选一个真正负责的施工单位认领。
   跑 `npm run check:change-unit -- --project-root <根> --blueprint <蓝图> --accept-candidates <候选文件> --json`：接受成功后原生删除候选文件；被拒时候选保留、不写施工单位，按报错改候选再接受。
   已有施工单位、或接受后未就绪修好之后，跑同一命令的 `--readiness`（替换 `--accept-candidates <候选文件>`）。返回里各字段分开用：
   - `accepted`：这一次接受了哪些施工单位，接受已经生效；之后就绪不成立也不再重复接受。跑 `--readiness` 时它为空是正常的；
   - `inventory`：全部施工单位的身份（`feature_id`、`canonical_path`，含退役的），之后各步的 Feature 标识与目录从这里取，不按业务名拼；
   - `status`、`readiness`、`ready_ids`：只有 `ready_ids` 里、且在本次授权内的施工单位往下做。未就绪按 `readiness` 点名的问题修好再跑 `--readiness`，
     返回 busy 时等占用解除再跑；只是评审文档物化失败时按返回的 `rebuildCommand` 重建。
   停在选择施工单位之前，不启动 Goal Mode。
2. **一次声明本次请求**：对 `ready_ids` 里获准的每个施工单位跑一次
   `npx ts-node scripts/goal-mode-entry.ts --project-root <根> --framework-root <根>/framework --feature <FID> --prepare-scope --completion-target request --requested-results '<本次获准的设计结果>' --requested-phases <按上表> --requirement-file <需求文件>`。
   `<需求文件>` 是蓝图需求条目里 `kind` 为 requirement 的来源文件（去掉 `#片段`），之后各阶段都用这一份。
   请求里要了可读的 Plan 或 Spec 正文时，另加一项 `--requested-results plan.md`（Spec 是 `spec.md`）：原生只在某一项恰好是这个文件名时
   把正文列为本阶段要交的产物；只要原生阶段结果时不加。
   要执行哪些阶段、哪些由已有依据复用，照它返回的 `phase_chain` 与 `obligations`：不先单做 Spec 再换范围，不补跑复用的阶段，也不删链上的阶段。
   原生要求的阶段超出本次授权时，停下照实说明，不自行扩大请求。
3. **按 `phase_chain` 逐阶段做完**：每个阶段 P 依次
   - `npx ts-node scripts/prepare-blueprint-design.ts --feature <FID> --phase P --project-root <根> --framework-root <根>/framework`：Spec 只准备 `acceptance.yaml`，Plan 只准备 `contracts.yaml` 与 `use-cases.yaml`；
   - 按原生 Spec / Plan Skill 与 `hooks/<阶段>/author.md` 完成本阶段产物（动笔前取知识任务）。准备结果标为 absent 的由本阶段写；标为 invalid 或与共同设计冲突的交回设计负责方（第 5 步），本阶段不改共同设计；
   - `npx ts-node harness-runner.ts --project-root <根> --phase P --feature <FID>`：首次正式运行冻结执行范围，之后复用；
     审查与收口照它末尾的 `NEXT:`，按 [`reference/phase-closure.md`](../reference/phase-closure.md)「闭环」那张 `next_action` 表做。
   本阶段收口了才进下一阶段；NEXT 要求回到前一阶段时先回去做。
4. **最后交接**：授权范围内的施工单位都做完后再跑一次 `story-build check --deliver`，通过才交回结果；报依据变了按第 5 步处理。
5. **共同设计在这一段变了**：由设计负责方在 component-design 里修订、交原质询者复核、重新走到准入，施工单位按原生 `--readiness` 重新派生；
   再按新蓝图集中同步 Story 与 Review 里受影响的章节，`story-build review --action prepare` 交原读者按改动影响复核，`story_flow.py story` 重新登记，回到第 4 步。
   只是确定性的准备、没有业务变化时不另派审查。

原生报候选 `differs`、要求修订权威或 Goal 权威时，保留原失败与已有产物，把具体请求与报错交设计负责方定合法路径：不加 `--overwrite`、不手改冻结记录，不为绕过报错换运行方式。
原生因当前真实 blocker 拒绝施工时，按它点名的问题回设计负责方；问题解决后形成设计或决定，原缺口留作历史，缺口状态只取原生的 `open_decision`、`blocker`、`not_applicable`。
依赖没满足的施工单位等它的依赖，其余获准的施工单位照常推进。
