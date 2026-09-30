# `/story` 链 · 交给设计、成文与交付

> 读者：走 `/story` 链的主 agent。时机：本轮材料与范围确认之后，一直到交付选择。每一步做什么由
> `story_flow.py status` 的 `next` 与 `action` 给出，本页讲这些步骤为什么这样走、各自交什么。

## 一、顺序

```
材料与范围确认 → bind-design → complete（冻结输入、原生来源检查）
  → component-design 走到准入并生成评审投影
  → story-build skeleton → 写作设计 → 逐章 chapter → 回看 → check
  → 独立审查（story-build review）→ story_flow.py story 登记 → check --deliver 交付门 → 交付选择
```

`/story` 默认做到交付门并问一次交付选择。已有明确授权覆盖后续时照授权接续；业务审批与实施授权分开对待。

## 二、交给设计

1. **关联设计对象**：`story_flow.py bind-design --feature <需求> --component <组件> --blueprint <蓝图>`。新需求的蓝图标识通常就是需求标识，照实给出；已有蓝图时核它实际归属的组件。关联一次，之后不改绑。
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

   - `adopted`：本轮确认的原件与它们引用的图，逐份列；不采用的材料在提取稿里写明理由。原件里引用的本地图片与链接都要在采用集合里。
   - `human_decision_ids`：真实关卡记录的 `ask_id`。人的原话、所选项与时间由脚本从流程契约导出，不手填。
   - `scope_items`：需求条目的身份、类别与权威取自材料与人签。`kind` 取 requirement / goal / invariant / high_risk；来源没分类的 `formality` 写 `unspecified`，由人在设计入口确认。
3. **冻结并交给设计**：`story_flow.py complete --feature <需求> --from AR/story-src/design-draft.md --input AR/story-src/design-input.json`。
   - 采用的原件、图片、提取稿（派生分析）与人签导出，按原始字节冻结在 `AR/story-src/inputs/<版本>/`。
   - 系统需求在版本里生成 `materialization.json`，本地需求把需求条目交给蓝图作者。两者都先过原生来源检查，通过才登记。
   - 同一份输入重跑复用原版本。`AR/design.md` 是上游原件，保持原样。
   - 失败时候选与诊断留在原处，已登记的输入不变。按报错补齐后重跑同一条命令。
4. 已登记一版之后要换输入，先 `story_flow.py reopen` 重新确认范围，或在 `/story update` 里重新提交。已被设计引用的版本一直保留。

## 三、设计

蓝图由 Framework 的 component-design 建立、质询、调和到准入：

- 用冻结的输入作为来源：系统需求交物化件，本地需求交需求条目。
- 设计动手前与质询前各取一次知识任务，入口见 story-knowledge Skill 与 `hooks/blueprint/author.md`。知识应用的判断写成蓝图里的 `knowledge_application` 决定。
- 原生字段表达不了的精确内容写进 `story_details`，写法见 `hooks/blueprint/author.md`。
- 准入之后由设计职责按原生 renderer 生成评审投影 `component-blueprint.review.md`。

蓝图没准入或投影与当前 revision 对不上时，`status` 停在等设计，成文不起手。只查看、重入或改表达不产生新的设计 revision。

## 四、成文

成文方法见 [`phases/story-write.md`](story-write.md)。Story 按已准入的蓝图写：

- 附录的技术契约、规约、埋点、改动边界由 `story-build project` 从蓝图投影，要改投影内容就回蓝图修订。蓝图里没有的类别不投，由你在那一节写「不涉及：<依据>」。
- 术语起始行是蓝图里确认过的术语，解释由你从材料写。
- 材料清单的起始行标出每份材料的采用版本，并另列派生分析与人签记录；每份贡献了什么由你写。
- 蓝图 `story_details` 里的专项设计写在讲它的那一章，内容逐字呈现，表达由你组织。

## 五、独立审查、登记与交付

1. **审查**：`story-build check` 通过之后，跑 `story-build review --action prepare`。它生成审查任务 `AR/story-src/review/task.md`，内含判据原文与这一次的输入，交给独立审查者。审查结论由 `story-build review --action check` 取：

   | 结论 | 你做什么 |
   |---|---|
   | 通过，结构检查也通过 | 登记，交付 |
   | 有建议、没有阻断项 | 带建议交付，不因建议反复重审 |
   | 有阻断项 | 回到最早出错的那一处（材料、决策登记、写作设计、章草稿或设计）修，改完重审 |
   | 报告缺失、无效或对象已变 | 保留原回复，重新准备或修真实输入，不改审查结论 |
   | 审查者不可用 | 照实说这份 Story 未经独立审查；有既有明确授权按授权交付，没有就请人选择 |
   | 输入无效或工具出错 | 停下，报告实际的工具或来源缺口 |

   独立审查的原生调用接通之前，`check` 给出的是「审查者不可用」。
2. **登记**：`story_flow.py story`。它从蓝图重投附录、编号、渲染 review、全篇 check，记下成文依据（蓝图引用、输入版本、知识摘要与文件指纹）。登记之后任何一样变了，改完重跑就是重新登记。
3. **交付门**：`story-build check --deliver`。它核交付的是登记的那一份，依据没有变。
4. **交付选择**：交付门通过后问一次，并按停等表记下人的选择：
   - 送审：仅系统需求；
   - 完整设计交接；
   - 完整实现；
   - 暂不推进。

   `AR/review.md` 是首版，评审人在人工区表态。你不代填，评审回来由 `/story update` 承接。
