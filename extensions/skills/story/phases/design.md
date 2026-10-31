# `/story` 链 · 交给设计、成文与交付

> 读者：走 `/story` 链的主 agent。时机：本轮材料与范围确认之后，一直到交付选择。每一步做什么由
> `story_flow.py status` 的 `next` 与 `action` 给出，本页讲这些步骤为什么这样走、各自交什么。

## 一、顺序

```
材料与范围确认
  → component-design 按 sources/ 的材料版本完成可评审设计与独立质询，生成评审投影
  → story-build skeleton → 写作设计 → 逐章 chapter → 回看 → check
  → 独立审查（story-build review：定稿、准备派审载体 → 原样派审 → 核结果）→ story_flow.py story 登记
  → check --deliver 交付门 → 交付选择
```

`/story` 做到交付门；已有明确授权就按其范围继续，还没指定后续目标时问一次交付选择（授权定义在 SKILL「推进契约」）。业务审批与实施授权分开对待。

## 二、交给设计

范围定了，`status` 给出 `design_blueprint`，就进原生 component-design。没有单独的交接命令：材料已经按版本导在 `sources/`（会议在 `AR/story-src/meetings/`），人的答复在生效时就导出在 `sources/人工答复-v<N>/`，设计直接读它们。

- **当前有效人答是必读**：问法与原话都在里面，分「当前有效」与「需结合上下文」两组。它不取决于你有没有把它写进需求条目或设计引用；答复确实规定了目标或边界时，原生范围要反映那条约束。
- **范围与兄弟单**：`status` 里本轮的定位（本单承载什么、同一系统设计下的兄弟单承载什么、协作方与不做项）和范围答复，写进原生范围与边界，再由 Story 讲给评审人。

1. **蓝图与需求同根**：蓝图标识就是需求标识，canonical 蓝图在 `<需求目录>/blueprint/`。组件由原生设计按工程上下文认定，写在蓝图里。已有蓝图按原生规则继续，不重复创建。
2. **需求条目只写真实义务**：需求条目（原生 `current_scope_items`）只写真实的需求、目标、约束与风险，并在设计里追溯。把它们的身份、类别、来源文件与权威写进一个 JSON 文件，跑 `import_sources.py --feature <需求> --scope <条目文件>`：

   ```json
   [
     {"item_id": "request-main", "kind": "requirement", "source": "sources/RR-<产品需求单号>-v1/RR-prd.md",
      "authority": {"owner": "需求负责人", "formality": "formal_requirement"}},
     {"item_id": "carry-boundary", "kind": "invariant", "source": "sources/人工答复-v<N>/answers.md",
      "authority": {"owner": "需求负责人", "formality": "formal_requirement"}}
   ]
   ```

   - `source` 是需求相对路径，可带 `#片段`；只能引材料索引登记的文件（材料版本的原件、阅读正文与图，人工答复，会议原件、raw、纠偏与阅读件）。
   - 例子里第二条是人工答复规定了承载边界才写的；人答本身不需要每条都成为条目。
   - `kind` 取 requirement / goal / invariant / high_risk。来源没分类的 `formality` 写 `unspecified`，由人在设计入口确认。
   - 脚本按材料索引补工程相对路径、原始字节摘要与 provenance，输出原生需求条目 `current_scope_items`，蓝图的 `discovery.inputs.current_scope_items` 按它写。
   - 条目来自需求系统取得的来源时，脚本同时写原生来源物化信封 `blueprint/requirement-source-materialization.json` 并过原生来源检查；蓝图还没建立时用 `--component <组件>` 给出原生设计认定的组件。本地来源只输出条目。
   - 失败时什么都不写，按报错补齐后重跑。
3. **支撑材料按真实引用**：背景说明、系统设计里的约束来源、界面图、会议纪要等支撑材料，在用到它的事实、设计对象、决定或合同的 provenance / `source_ref` 里引用工程相对路径，不为它造需求条目。需求条目与这些引用命中的登记版本，就是设计采用的版本；没被引用的材料只能说「设计未见引用」，是有据不用还是漏了依据由质询与审查核。
4. 之后取得的新版本不自动进入设计：要不要采用由 update 判断，采用就改相应的条目或引用。Story 材料表在同一来源行写清「取得 v2、设计引证 v1」与原因。
5. 要重拍范围先 `story_flow.py reopen`，范围重新定了再按新范围同步需求条目与边界。

## 三、设计

蓝图由 Framework 的 component-design 建立、质询与调和。请求 `/component-design <蓝图>` 时写明「完成可评审设计与独立质询，本次不做施工单位准备」，做到生成评审投影为止；准入由原生判定，草稿也可以成文与业务送审，准入状态与原生问题照实披露：

- 来源是登记的材料与当前有效人答：业务的条件、行为与责任从原件与人答取，人签以 `sources/人工答复-v<N>/` 的导出为准。用到哪份就在相应的条目或 provenance 里引用它。
- 设计动手前取作者的知识任务，入口见 story-knowledge Skill 与 `hooks/blueprint/author.md`。任务给的知识输入身份写进蓝图，知识的适用性写成蓝图事实，适用规约的义务与模式角色写在承担它的设计对象上。
- 原生字段表达不了的精确内容写进 `story_details`，写法见 `hooks/blueprint/author.md`。
- **独立质询**由你（主执行者）派给宿主的隔离子代理，同一个子代理先首读人读稿、再核源：
  1. 候选、图与说明写好后，设计职责先跑原生 `check:component-blueprint --write-review --json` 渲染人读稿 `component-blueprint.review.md`；
  2. 取质询任务（`--action questioning --audience reviewer`），把任务全文与被评候选按它第 7 块给的位置原样存好；
  3. 把第 7 块的首读载体原样交给子代理——只有人读稿、原生八问、阅读规则和之后读的任务路径，不附任务正文、来源或作者判断；
     子代理答完八问再读任务、canonical 蓝图、原件与人签核原生质询范围，只读、不改蓝图，回复原样留存；
  4. 设计负责方逐项处理质询提出的问题（要人定的问人），再写原生 `review_summary.questioning`，`provider_id` 写这次子代理调用的身份；
     修订后按原生规则重渲人读稿，该轮质询方从头通读当前正文复核。
  宿主没有隔离子代理时，停在质询这一步：向人说明需要一个隔离的质询者，质询完成后才进入成文。

蓝图读不出、需求条目与设计依据都没有引用本需求登记的材料、引用了没登记的文件，或投影与当前 revision 对不上时，`status` 停在等设计，成文不起手。蓝图是草稿、未准入不挡成文：准入状态与原生问题由 `skeleton`、独立审查任务与交付门照实带出。只查看、重入或改表达不产生新的设计 revision。
单独核蓝图状态用 `node doc/extensions/hooks/shared/framework-access.mjs --project-root <根> --action blueprint --blueprint <需求> --purpose draft --consume <需求> --summary`：
同一次完整读取与校验，返回准入、引用、问题、投影与消费结果，不带蓝图正文；设计内容读 canonical 蓝图或评审投影。

## 四、成文

成文方法见 [`phases/story-write.md`](story-write.md)。Story 按当前蓝图写：草稿的原生问题涉及的业务事实写成待定或限制，不写成已定。

- 附录的配置与埋点由 `story-build project` 从蓝图投影，要改投影内容就回蓝图修订。
- 附录的端云接口、数据存储与规约由你按蓝图写业务摘要（写法见 `story-write.md` 的附录一行）；写作设计骨架里给这几节写
  `- 依据：`，注明蓝图 revision 与原生地址（如 `contract:<id>`），附录提交时核这些地址指得到当前蓝图的对象。
- 完整技术契约在设计参考——同根蓝图的原生评审投影 `blueprint/component-blueprint.review.md`：你不写它、不复制它，设计要改回蓝图。
- 蓝图里没有的类别由你在那一节写「不涉及：<依据>」。术语起始行是蓝图里确认过的术语，解释由你从材料写。
- 材料清单由你写成一张「材料 | 来源 | 贡献」表：一行一份阅读稿，来源列列齐合成它的原件与采用版本，写它贡献了什么，没采纳的写原因（写法见 `story-write.md` 的附录一行）。
- 蓝图 `story_details` 里的专项设计写在讲它的那一章，表达由你组织，精确值、引用与来源与蓝图一致。专项内容本身有错或含混，回蓝图修订，不在 Story 补一段相反的解释，也不留给施工单位改共同设计。

## 五、独立审查、登记与交付

1. **定稿并准备审查**：`story-build check` 通过之后，跑 `story-build review --action prepare`。它先把审查对象定成最终版
   （附录重投、编号、渲染 `AR/review.md`、全篇结构检查），再写审查任务 `AR/story-src/review/task.md`，
   定下这一次的材料键、报告目录（默认 `doc/reports/story/<需求>/<材料键前 16 位>/`，与需求目录分开；可用 `--report-dir` 指定，
   首次准备定下后同一份材料一直沿用）与这一份回复的位置，生成派审载体 `AR/story-src/review/dispatch.md`（输出里的 `dispatch_text`）。
   同一份材料已有通过的报告时输出 `reused`，直接核结果。之后改了任何被审材料，重新 prepare、重新审。
2. **派审**：把 `dispatch_text` 原样作为宿主隔离子代理的任务交给审查者，不增删、不改写——它只给 Story、首读问题、材料键、回复位置与首读之后读的文件；
   返修、复审或上一版报告参考写在前轮上下文 `AR/story-src/review/context.md`，审查者首读之后才读。
   审查者按载体说明的范围读材料（格式返修只补诊断点到的核验，其余情形完整读），把 Story 报告直接写到载体给的回复位置；那份文件就是审查原件，你只读它。向人可以概述审查结论，概述不写回原件。之前的回复保留。
   宿主的子代理只能返回文本时，用宿主现有的、把工具输出正文原样存盘的动作写到回复位置，外层协议包装与报告正文分开保留；
   没有这样的动作就停下向人说明原件交接的缺口——你手写或缩写的回复不是审查原件，也不适用下面「没有可派的审查子代理」的授权。
3. **接收并核结果**：回复落盘后先重跑 `story-build review --action prepare` 接收它（记下原样字节的摘要，之后的改动由此识别），
   再跑 `story-build review --action check`，它只读核审的是不是现在这份、报告合不合格式与引用、结论是什么：

   | 结果 | 你做什么 |
   |---|---|
   | pass | 登记，交付 |
   | warn（只有 MINOR / INFO 建议） | 对这组建议作一次处置：指出事实或范围问题的，回它的责任方改；不影响正确与完整的表达偏好可以保留，写一句理由。决定采纳的按实际影响面一次改完，重新 prepare，新载体带这份报告作参考、结论只对新材料。处置写进交付说明（update 时写 update-notes），登记交付；不为清空建议再改再审 |
   | fail（有 BLOCKER / MAJOR 发现） | 按发现牵涉的业务决定修：决定来源（材料、人签、决策登记）→ 蓝图里承接它的设计对象（由设计职责修订、重新准入）→ Story、Review 与验收，凡写着这项决定的地方一并改到同一结论；只是表达问题的改章草稿。改完重新 prepare，按新载体交独立审查者完整复核 |
   | report_missing | 按派审载体派审 |
   | report_unreceived | 回复在、还没接收：重跑 prepare 接收，再 check |
   | report_invalid | 原回复留在原处，你不补表、不改字；重新 prepare，新载体带着原回复与诊断，原样交独立审查者重给一份 |
   | subject_stale | 准备之后被审材料变了：重新 prepare，按新载体再派审 |
   | input_invalid | 派审载体缺失或与准备记录对不上时重跑 prepare；准备记录本身读不出时按诊断恢复原记录，不删掉它重来；审查对象缺来源时停下，向人报告缺哪份、向谁取得 |
   | unreviewed | 当前宿主没有声明 Story 独立审查能力：prepare 已把未审披露写进 Story 交付章与 Review 题头，可以登记与交付；不问人要免审授权，交付说明照实写本版未审 |

   宿主没有可派的审查子代理（当前 adapter 没有声明）时不派审：prepare 自动写未审披露，结果是 unreviewed。
   之前的审查判过阻断、改过之后还没人复核时，结果是 fail（已知必修未复核），要在能派审的宿主上复核。
   宿主能力在 prepare 之后变了，结果是 subject_stale，重新 prepare。
4. **登记**：`story_flow.py story`。它核结构检查、这一份的审查结果（pass、warn，或宿主没有审查能力时的 unreviewed）与成文依据
   （蓝图引用、设计采用的来源、知识摘要、材料索引摘要，以及 Story、Review、决策登记与写作设计的原始字节指纹），通过后记下新依据。
5. **交付门**：`story-build check --deliver`，核交付的是登记的那一份、依据（含蓝图）没变、审查结果仍可消费。登记或交付门报错时，按报错回到对应步骤。
6. **交付选择**：交付门通过后，已有明确授权就按其范围继续，还没指定后续目标时问一次交付选择，并按停等表记下人的选择：
   - 送审：仅系统需求，走 `/story archive <AR>`，Story 作正文、Review 与设计参考（蓝图的原生评审投影原字节）作附件，三件都读回一致才登记；
   - 完整设计交接：在已准入蓝图上按 Framework change-unit-progression 完成施工单位设计准备，不启动施工；
   - 实现方案：完成施工单位设计准备，再沿 Framework 交互路径为每个施工单位准备范围，请求终点写到 Plan
     （`--completion-target request --requested-phases spec,plan`）；完成适用的 Spec/Plan，Framework 判可复用的沿用，止于 Plan。
     施工单位的 Feature 标识由 Framework 的身份解析给出；`--requirement-file` 用蓝图需求条目里 `kind` 为 requirement 的来源文件
     （去掉 `#片段`），范围候选、首个阶段与之后的运行都用这一份；

   - 完整实现：在授权范围内接续设计准备与 Framework 交互式开发，按 Framework 结果推进；
   - 暂不推进：停在这里，之后从 `story_flow.py status` 续上。

   `AR/review.md` 是首版，评审人在人工区表态。你不代填，评审回来由 `/story update` 承接。
