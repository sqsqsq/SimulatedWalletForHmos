# `/story` 链 · 交给设计、成文与交付

> 读者：走 `/story` 链的主 agent。时机：本轮材料与范围确认之后，一直到交付选择。每一步做什么由
> `story_flow.py status` 的 `next` 与 `action` 给出，本页讲这些步骤为什么这样走、各自交什么。

## 一、顺序

```
材料与范围确认 → bind-design → complete（冻结输入、原生来源检查）
  → component-design 走到准入并生成评审投影
  → story-build skeleton → 写作设计 → 逐章 chapter → 回看 → check
  → 独立审查（story-build review：定稿、准备原生请求 → 派审 → 核结果）→ story_flow.py story 登记
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

蓝图由 Framework 的 component-design 建立、质询、调和到准入，本次请求做到准入并生成评审投影为止：

- 用冻结的输入作为来源：系统需求交物化件，本地需求交需求条目；人签以冻结版本里的导出为准。把读过的材料逐份记为已消费。
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

## 四、成文

成文方法见 [`phases/story-write.md`](story-write.md)。Story 按已准入的蓝图写：

- 附录的技术契约、规约、埋点、改动边界由 `story-build project` 从蓝图投影，要改投影内容就回蓝图修订。蓝图里没有的类别不投，由你在那一节写「不涉及：<依据>」。
- 术语起始行是蓝图里确认过的术语，解释由你从材料写。
- 材料清单的起始行标出每份材料的采用版本，并另列派生分析与人签记录；每份贡献了什么由你写。
- 蓝图 `story_details` 里的专项设计写在讲它的那一章，内容逐字呈现，表达由你组织。

## 五、独立审查、登记与交付

1. **定稿并准备审查**：`story-build check` 通过之后，跑 `story-build review --action prepare`。它先把审查对象定成最终版
   （附录重投、编号、渲染 `AR/review.md`、全篇结构检查），再写审查任务 `AR/story-src/review/task.md`，输出这一次的材料键、
   报告目录（默认 `doc/reports/story/<需求>/<材料键前 16 位>/`，与需求目录分开；可用 `--report-dir` 指定，首次准备定下后同一份材料一直沿用）
   与这一份回复的位置。同一份材料已有通过的报告时
   输出 `reused`，直接核结果。之后改了任何被审材料，重新 prepare、重新审。
2. **派审**：用宿主与作者隔离的独立执行能力（子代理）把任务文件与材料键交给审查者。审查者读任务里列的全部材料，
   回复一份 Story 报告（格式在任务的「报告怎么写」）。你把回复**原样**写到准备输出的回复位置，一字不改；之前的回复保留。
3. **核结果**：`story-build review --action check` 只读核审的是不是现在这份、报告合不合格式与引用、结论是什么：

   | 结果 | 你做什么 |
   |---|---|
   | pass | 登记，交付 |
   | warn（只有 MINOR / INFO 建议） | 登记，带建议交付，不因建议反复重审 |
   | fail（有 BLOCKER / MAJOR 发现） | 回到最早出错的那一处（材料、决策登记、写作设计、章草稿或设计）修，改完重新 prepare、重审 |
   | report_missing | 把任务与材料键交审查者，回复原样写到准备给出的位置 |
   | report_invalid | 原回复留在原处；重新 prepare 取新位置，把原回复连同任务「报告怎么写」交审查者重给一份 |
   | subject_stale | 准备之后被审材料变了：重新 prepare，按新任务再派审 |
   | input_invalid | 停下，向人报告缺哪份来源、向谁取得 |

   宿主没有可派的审查子代理（当前 adapter 没有声明）时，向人说明这一版需要独立审查，并问是否授权本版不经审查交付。
   人授权后，在 prepare 之后、结果为 report_missing 时跑 `story_flow.py unreviewed --reason "<缺什么>" --reply "<人的原话>"`，
   授权记进流程契约；再跑一次 prepare，审查状态写进 Story 交付章与 Review 题头，结果是 unreviewed，可以登记与交付。
   授权对应当时这一版材料：材料变了要重新审查或重新授权；之后宿主能派审了，用 `--withdraw` 撤回后正常派审。
4. **登记**：`story_flow.py story`。它核结构检查、这一份的审查结果（pass、warn 或人授权的 unreviewed）与成文依据
   （蓝图引用、输入版本、知识摘要，以及 Story、Review、决策登记与写作设计的原始字节指纹），通过后记下新依据。
5. **交付门**：`story-build check --deliver`，核交付的是登记的那一份、依据没变、审查结果仍可消费。登记或交付门报错时，按报错回到对应步骤。
6. **交付选择**：交付门通过后，已有明确授权就按其范围继续，还没指定后续目标时问一次交付选择，并按停等表记下人的选择：
   - 送审：仅系统需求，走 `/story archive <AR>`；
   - 完整设计交接：在已准入蓝图上按 Framework change-unit-progression 完成施工单位设计准备，不启动施工；
   - 实现方案：完成施工单位设计准备，再沿 Framework 交互路径为每个施工单位准备范围，请求终点写到 Plan
     （`--completion-target request --requested-phases spec,plan`）；完成适用的 Spec/Plan，Framework 判可复用的沿用，止于 Plan；
   - 完整实现：在授权范围内接续设计准备与 Framework 交互式开发，按 Framework 结果推进；
   - 暂不推进：停在这里，之后从 `story_flow.py status` 续上。

   `AR/review.md` 是首版，评审人在人工区表态。你不代填，评审回来由 `/story update` 承接。
