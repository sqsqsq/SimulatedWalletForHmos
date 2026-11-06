# 步骤01：Story写作与阅读质量

本步将同根来源及共同设计送进有界成文入口，交付独立业务叙事。只按本步改写后的职责实施；当前为待实施方案。

## 1. 输入、接口与边界

必读[批次方案](00-批次方案.md)、[共享接口](../参考/01-目标接口与状态.md)、主Spec R1—R4/R9及阅读专题R1—R7、TEST§6.5和本版评价标准变更。实施对象为`extensions/skills/story/`下的`phases/story-write.md`、`phases/design.md`、章节合同及成文模块；不改金样业务或`demo/framework/`。

输入是`materials.json`可回到`sources/<材料名版本>/`的原件、转换稿和图，会议原话与纠偏、有效人答、当前蓝图canonical及原生人读稿、facts与真实契约实体义务。蓝图`current_scope_items`选用的版本与实际引用一致；材料已到但不采用仍可核理由。来源索引不变成写作逐条守恒账本，作者不再填写第二份`design-input`。

输出仍为`AR/story.md`、`AR/review.md`及有用途的`AR/story-src/`写作安排/章节草稿/图源码/必要回看记录。Story可解释共同设计但不能另造共同决定；Review仅承载真实裁决及人工区，非独审报告。必要技术摘要保状态、接口业务语义、恢复、规约、配置与埋点，不因蓝图已有就移除。

## 2. 实施顺序与直接消费者

1. 先切换`scripts/core/story/story-inputs.mjs`、`design-source.mjs`、`sources.mjs`及`scripts/core/story/context.mjs`的读取：同根原生身份→当前canonical/人读稿→采用来源版本和实际材料。删除指向旧绑定、冻结输入与五段提取稿的读取分支；来源读不到报出原件路径和缺口，不能补一份空文件继续。其返回值继续供`skeleton`、章节起手材料、独审对象与交付依据核对使用。
2. 在`writing-plan.mjs`的`writingPlanShell`、`readWritingPlan`、`selectedStructure`保留作者对阅读顺序、小节和图表用途的选择，调整`basisSections`、`carryTargets`等旧输入消费者，改为读取当前来源/设计实际事实，不要求逐来源、逐知识编号自证。作者先组织全篇主线再分章；相同事实必要重述可成立，机器只核地址/结构/保护，不用关键词或相似度判断重复。
3. `drafts.mjs`的`writeDrafts`/`chapterDraft`将已定事实、适用知识义务和本章职责直接写入实际作者输入；明确原件、采用版本和未决，不把“磁盘上已有”算送达。`chapter.mjs`的`cmdChapter`继续通过`document.mjs`的`storySpan`/`chapterSpan`定位并原子替换目标范围，写前检查歧义、保护非目标段；中断从未完成章续写，不回退一次性全文生成。标题变化同步写作安排、草稿定位、重编号和局部更新消费者。
4. 对`contracts/story-chapters.json`、`chapter-contract.mjs`、`chapter.mjs`的`chapterProblems`及`document.mjs`的编号/章节解析，保必要章节职责和精确定位，拆开“当前案例十章”与通用结构约束。既有编号和合法章节结构保持可用；不由本次引入另一套文章生成器，也不按固定章数、图数、禁词、字数或图前后严格紧邻判质量。删除旧五段输入专用匹配而保真实来源、表/图语法、未闭合标记及引用校验。
5. 更新`phases/story-write.md`、作者实际读到的`phases/design.md`及`drafts.mjs`起手文字：标题提炼业务主题，按同节场景分组；图＞表＞列表＞章节＞文字；自制业务关系图使用图前导读、图、图后有用补充，图文合起来完整。页面交互在业务流程中按角色/场景保入口、页面、操作、可见反馈、去向；系统协作图不替代页面体验。原截图不强加关系图任务，SVG可零张。
6. `story/check.mjs`、`recheck.mjs`、`review.mjs`及`story-build.mjs`最后组合当前正文、Review、图和来源。全篇回看由模型判断事实/关系/未决/验收是否一致；设计遗漏回蓝图或来源真源修正，再重新读取/生成受影响内容，表达遗漏只修作者段落。定稿交给步骤02独审和步骤03更新，不在回看时制造新审批。

源文件前缀均为`extensions/skills/story/`。`hooks/shared/story-view.mjs`、`hooks/shared/review-inputs.mjs`和`hooks/shared/reader-review-task.mjs`也消费正文/章节/来源，应在本步同步输入地址，审查语义和状态改动由步骤02完成。

## 3. 设计参考与退场

原生蓝图人读稿是设计参考真源，Story写作者与审查者直接读取当前投影。本地完整交付用同根Story、Review及实际蓝图参考即可；不再常驻复制一份`AR/design-review.md`充当设计真源。系统若确需Markdown设计附件，在步骤04上传时由当前原生投影生成确定性交付副本并绑定摘要；不因无附件样例删除此能力，也不把副本固定成额外业务必审对象。

退场涵盖作者页、章节合同、`story-inputs`/`design-source`/`appendix-readers`对旧`complete`五段稿、`design_binding`、`frozen/design-input`和通用`knowledge_application`的实际读取及其专用断言。前批已切换的直接消费者只核接口不重复建替身。`appendix.mjs`与`designReviewProblems`原复制校验由原生投影当前性核对接替。保原件、多版本、图义、会议纠偏、有效人答、独立Story、技术摘要、人工区和有界落盘；无旧在途自动迁移。

## 4. 定向验证与完成

后续实施定向调整`test/tests/test_story_build.py`、`test_story_inputs.py`、`test_review_render.py`中的真实装配输入。用同名不同子目录/版本、含页面图的合法材料证明skeleton与章节读取的是实际采用版本；标题重命名后中断续写、局部替换、重编号不触碰非目标章和人工区；缺原件、损坏引用和歧义定位应一次说明实际缺口。构造合法非十章组织及零SVG，不能因机械数量拒绝；结构合法但页面去向缺失的稿件不能由结构PASS宣布语义合格。

独立语义核首读理解、全部标题层级、同节场景组织、页面五要素、图文各有用途、必要重述与全文一致性；对照原件和当前设计判断，不把某例标题/SDK/恢复接口推广。真实成文送达与中断恢复效果需后续正常DSH证据，人工候选及离线构造不代签。

完成条件是新来源→作者输入→章节写入→全文回看→下游独审/更新接口完整，旧读取无生产消费者，保持项有证据。预计G350/X480；量化按[共享预算](../参考/03-预算与计量.md)及AGENTS§5，不以净减抵消invested。本步交回列文件、生产/消费证据、退出、未覆盖及预算后提交；前置成立继续步骤02。

## 同步成文登记集合

本步撤常驻AR/design-review.md的同一次切换，更新core/flow/state.py::STORY_REGISTERED及lifecycle.py::cmd_story的逐件摘要读取：业务正文/Review及必要写作记录保字节指纹，设计依据使用原生精确ref/摘要，不再对已退出副本强求文件。story-build/check/delivery、审查对象及update登记读者同时同步；C02只深化审查分责，不能用于补本步遗留断链。系统交付附件的实际字节摘要归C04发布记录，不当第二设计真源。
