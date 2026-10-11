# `/story` 链 · 交给设计、成文与交付

> 读者：走 `/story` 链的主 agent。时机：本轮材料与范围确认之后，一直到交付选择。每一步做什么由
> `story_flow.py status` 的 `next` 与 `action` 给出，本页讲这些步骤为什么这样走、各自交什么。

## 一、顺序

```
材料与范围确认 → bind-design → complete（冻结输入、原生来源检查）
  → component-design 走到准入并生成评审投影
  → story-build skeleton → 写作设计 → 逐章 chapter → 回看 → check
  → 独立审查（story-build review：定稿、准备派审载体 → 原样派审 → 核结果）→ story_flow.py story 登记
  → check --deliver 交付门 → 交付选择
```

`/story` 做到交付门；已有明确授权就按其范围继续，还没指定后续目标时问一次交付选择（授权定义在 SKILL「推进契约」）。业务审批与实施授权分开对待。

## 二、交给设计

1. **关联设计对象**：`story_flow.py bind-design --feature <需求> --component <组件> --blueprint <蓝图>`。蓝图标识与需求标识分开（需求材料目录与蓝图工作区是两个目录）：新需求建议 `bp-<需求标识>`；已有设计给出它实际的蓝图标识，核它归属的组件。标识已被别的对象占用时照报错换一个你实际要用的，不自动搜索或改名。关联一次，之后不改绑。
2. **写设计输入** `AR/story-src/design-input.json`：

   ```json
   {
     "adopted": ["RR/prd.md", "AR/design.md", "assets/flow.svg"],
     "human_decision_ids": ["<scope_decision 等关卡记录的 ask_id>"],
     "scope_items": [
       {"item_id": "request-main", "kind": "requirement", "source_path": "RR/prd.md",
        "authority": {"owner": "需求负责人", "formality": "formal_requirement"}}
     ]
   }
   ```

   - `adopted`：本轮确认的原件与它们引用的图，逐份列；不采用的材料在提取稿里写明理由。原件里引用的本地图片要在采用集合里；作为设计依据的本地文件同样采用进来。
   - `human_decision_ids`：真实关卡记录的 `ask_id`。人的原话、所选项与时间由脚本从流程契约导出，不手填。
   - `scope_items`：需求条目的身份、类别与权威取自材料与人签。`kind` 取 requirement / goal / invariant / high_risk；来源没分类的 `formality` 写 `unspecified`，由人在设计入口确认。
3. **冻结并交给设计**：`story_flow.py complete --feature <需求> --from AR/story-src/design-draft.md --input AR/story-src/design-input.json`。
   - 采用的原件、图片、提取稿（派生分析）与人签导出，按原始字节冻结在 `AR/story-src/inputs/<版本>/`。
   - 系统需求在版本里生成 `materialization.json`，本地需求把需求条目交给蓝图作者。两者都先过原生来源检查，通过才登记。
   - 同一份输入重跑复用原版本。`AR/design.md` 是上游原件，保持原样。
   - 输出里的 `unadopted_references` 是原件链到、但没纳入本次冻结的文件：逐条判断它是不是设计依据——是就补成材料再提交，不是就在提取稿里写明不采用。没纳入的文件内容不算已取得的来源。
   - 失败时候选与诊断留在原处，已登记的输入不变。按报错补齐后重跑同一条命令。
4. 已登记一版之后要换输入，先 `story_flow.py reopen` 重新确认范围，或在 `/story update` 里重新提交。已被设计引用的版本一直保留。

## 三、设计

蓝图由 Framework 的 component-design 建立、质询、调和到准入。请求 `/component-design <蓝图>` 时写明「完成可评审设计与独立质询，本次不做施工单位准备」，做到准入并生成评审投影为止：

- 用冻结的输入作为来源：系统需求交物化件，本地需求交需求条目；冻结文件直接交给设计作者。提取稿是索引与分析，业务的条件、行为与责任从冻结的原件与有效人签取，人签以冻结版本里的导出为准。把读过的材料逐份记为已消费。
- 设计动手前取作者的知识任务，入口见 story-knowledge Skill 与 `hooks/blueprint/author.md`。知识应用的判断写成蓝图里的 `knowledge_application` 决定。
- 原生字段表达不了的精确内容写进 `story_details`，写法见 `hooks/blueprint/author.md`。
- **独立质询**由你（主执行者）派给宿主的隔离子代理：
  1. 候选写好后取质询任务（`--action questioning --audience reviewer`），它给出原生质询范围、回复要求与原件的建议位置；
  2. 把任务交给子代理；它只读材料、逐项回复，不改蓝图；
  3. 派审时的候选与回复原样留存，一字不改；
  4. 设计负责方逐项处理质询提出的问题（要人定的问人），再写原生 `review_summary.questioning`，`provider_id` 写这次子代理调用的身份。
  宿主没有隔离子代理时，停在质询这一步：向人说明需要一个隔离的质询者，质询完成后蓝图才准入。
- 准入之后由设计职责按原生 renderer 生成评审投影 `component-blueprint.review.md`。

蓝图没准入或投影与当前 revision 对不上时，`status` 停在等设计，成文不起手。只查看、重入或改表达不产生新的设计 revision。
单独核蓝图状态用 `node doc/extensions/hooks/shared/framework-access.mjs --project-root <根> --action blueprint --blueprint <蓝图> --purpose delivery --snapshot <冻结快照> --summary`：
同一次完整读取与校验，返回准入、引用、问题、投影与消费结果，不带蓝图正文；设计内容读 canonical 蓝图或评审投影。

## 四、成文

成文方法见 [`phases/story-write.md`](story-write.md)。Story 按已准入的蓝图写：

- 附录的配置、埋点与改动边界由 `story-build project` 从蓝图投影，要改投影内容就回蓝图修订。
- 附录的端云接口、数据存储与规约由你按蓝图写业务摘要（写法见 `story-write.md` 的附录一行）；写作设计骨架里给这几节写
  `- 依据：`，注明蓝图 revision 与原生地址（如 `contract:<id>`），附录提交时核这些地址指得到当前蓝图的对象。
- 完整技术契约随设计附件 `AR/design-review.md` 交付：定稿时从原生评审投影逐字节复制，你不写它，设计要改回蓝图。
- 蓝图里没有的类别由你在那一节写「不涉及：<依据>」。术语起始行是蓝图里确认过的术语，解释由你从材料写。
- 材料清单由你写成一张「材料｜来源｜贡献」表：每份外部原件一行，写它贡献了什么，没采纳的新值写裁决依据。
- 蓝图 `story_details` 里的专项设计写在讲它的那一章，内容逐字呈现，表达由你组织。专项内容本身有错或含混，回蓝图修订，不在 Story 补一段相反的解释，也不留给施工单位改共同设计。

## 五、独立审查、登记与交付

1. **定稿并准备审查**：`story-build check` 通过之后，跑 `story-build review --action prepare`。它先把审查对象定成最终版
   （附录重投、编号、渲染 `AR/review.md`、复制设计附件 `AR/design-review.md`、全篇结构检查），再写审查任务 `AR/story-src/review/task.md`，
   定下这一次的材料键、报告目录（默认 `doc/reports/story/<需求>/<材料键前 16 位>/`，与需求目录分开；可用 `--report-dir` 指定，
   首次准备定下后同一份材料一直沿用）与这一份回复的位置，生成派审载体 `AR/story-src/review/dispatch.md`（输出里的 `dispatch_text`）。
   同一份材料已有通过的报告时输出 `reused`，直接核结果。之后改了任何被审材料，重新 prepare、重新审。
2. **派审**：把 `dispatch_text` 原样作为宿主隔离子代理的任务交给审查者，不增删、不改写——材料键、任务、回复位置，以及返修、复审或上一版报告参考都在里面。
   审查者按载体说明的范围读材料（格式返修只补诊断点到的核验，其余情形完整读），把 Story 报告直接写到载体给的回复位置；那份文件就是审查原件，你只读它。向人可以概述审查结论，概述不写回原件。之前的回复保留。
   宿主的子代理只能返回文本时，用宿主现有的、把工具输出正文原样存盘的动作写到回复位置，外层协议包装与报告正文分开保留；
   没有这样的动作就停下向人说明原件交接的缺口——你手写或缩写的回复不是审查原件，也不适用下面「没有可派的审查子代理」的授权。
3. **核结果**：`story-build review --action check` 只读核审的是不是现在这份、报告合不合格式与引用、结论是什么：

   | 结果 | 你做什么 |
   |---|---|
   | pass | 登记，交付 |
   | warn（只有 MINOR / INFO 建议） | 对这组建议作一次处置：指出事实或范围问题的，回它的责任方改；不影响正确与完整的表达偏好可以保留，写一句理由。决定采纳的按实际影响面一次改完，重新 prepare，新载体带这份报告作参考、结论只对新材料。处置写进交付说明（update 时写 update-notes），登记交付；不为清空建议再改再审 |
   | fail（有 BLOCKER / MAJOR 发现） | 按发现牵涉的业务决定修：决定来源（材料、人签、决策登记）→ 蓝图里承接它的设计对象（由设计职责修订、重新准入）→ Story、Review 与验收，凡写着这项决定的地方一并改到同一结论；只是表达问题的改章草稿。改完重新 prepare，按新载体交独立审查者完整复核 |
   | report_missing | 按派审载体派审 |
   | report_invalid | 原回复留在原处，你不补表、不改字；重新 prepare，新载体带着原回复与诊断，原样交独立审查者重给一份 |
   | subject_stale | 准备之后被审材料变了：重新 prepare，按新载体再派审 |
   | input_invalid | 派审载体缺失或与准备记录对不上时重跑 prepare；准备记录本身读不出时按诊断恢复原记录，不删掉它重来；审查对象缺来源时停下，向人报告缺哪份、向谁取得 |

   宿主没有可派的审查子代理（当前 adapter 没有声明）时，向人说明这一版需要独立审查，并问是否授权本版不经审查交付。
   人授权后，在 prepare 之后、结果为 report_missing 时跑 `story_flow.py unreviewed --reason "<缺什么>" --reply "<人的原话>"`，
   授权记进流程契约；再跑一次 prepare，审查状态写进 Story 交付章与 Review 题头，结果是 unreviewed，可以登记与交付。
   授权对应当时这一版材料：材料变了要重新审查或重新授权；之后宿主能派审了，用 `--withdraw` 撤回后正常派审。
4. **登记**：`story_flow.py story`。它核结构检查、这一份的审查结果（pass、warn 或人授权的 unreviewed）与成文依据
   （蓝图引用、输入版本、知识摘要，以及 Story、Review、设计附件、决策登记与写作设计的原始字节指纹），通过后记下新依据。
5. **交付门**：`story-build check --deliver`，核交付的是登记的那一份、依据没变、设计附件仍是当前原生投影、审查结果仍可消费。登记或交付门报错时，按报错回到对应步骤。
6. **交付选择**：交付门通过后，已有明确授权就按其范围继续，还没指定后续目标时问一次交付选择，并按停等表记下人的选择：
   - 送审：仅系统需求，走 `/story archive <AR>`，Story 作正文、Review 与设计附件作附件，三件都读回一致才登记；
   - 完整设计交接：在已准入蓝图上按 Framework change-unit-progression 完成施工单位设计准备，不启动施工；
   - 实现方案：完成施工单位设计准备，再沿 Framework 交互路径为每个施工单位准备范围，请求终点写到 Plan
     （`--completion-target request --requested-phases spec,plan`）；完成适用的 Spec/Plan，Framework 判可复用的沿用，止于 Plan。
     施工单位的 Feature 标识由 Framework 的身份解析给出；`--requirement-file` 用本轮冻结输入里的提取稿：读 `story-flow.json`
     的 `input.snapshot_ref`，取快照 `files` 里 `role` 为 `extracted_analysis` 的那一行，路径是快照目录下的 `files/<path>`，
     范围候选、首个阶段与之后的运行都用这一份。快照里没有这一行或有不止一行，回到 `complete` 补齐冻结输入；

   - 完整实现：在授权范围内接续设计准备与 Framework 交互式开发，按 Framework 结果推进；
   - 暂不推进：停在这里，之后从 `story_flow.py status` 续上。

   `AR/review.md` 是首版，评审人在人工区表态。你不代填，评审回来由 `/story update` 承接。
