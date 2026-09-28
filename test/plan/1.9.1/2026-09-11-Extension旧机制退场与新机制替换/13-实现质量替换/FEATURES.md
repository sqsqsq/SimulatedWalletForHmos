# Extension 功能全集（第二包候选稿）

> **候选状态**：本文件暂存本轮方案目录，按 [11-集成验收与本轮交付](11-集成验收与本轮交付.md) §4，
> 最终验收与 G2 之后才正式迁入 `test/story/` 并更新 AGENTS 入口。当前不是已生效的长期清单。
>
> **基线**：`77314387`（2026-09-13，第二包 Q9/Q10/Q11 静态部分落地后）。定位以**符号名**为准
> （函数、常量、章节标题、合同键），不写行号——行号会随返修漂移，符号在返修中稳定；
> 确需行号时以本基线为准并注明。验收有返修时只更新受影响条目。
>
> **上一版**：[2026-09-11 的三稿](../../2026-09-11-Extension功能全集与机制归属/FEATURES.md)
> 基线 `d36edb70`，其坐标已失效（`story_flow.py`、`materials.py`、`import_sources.py`、
> `lint-rules.mjs`、`headings.mjs`、`review-render.mjs`、`flow-check.mjs`、`knowledge-use.mjs`
> 的位置在本轮全部变了）。功能 ID 沿用，便于逐条对照。

## 怎么用这三份

| 文件 | 回答 |
|---|---|
| 本文件 | **有哪些功能**：每个叶子的目的、输入、现行实现、消费者、失败出口、证据 |
| [FEATURE-MAP.md](FEATURE-MAP.md) | **功能 → 实现**：每个功能落在哪些文件的哪些符号上；本轮的退出项也在这里 |
| [FEATURE-CONTENT-MAP.md](FEATURE-CONTENT-MAP.md) | **实现 → 功能**：每个文件的每个内容单元归哪个功能，可多归属不可遗漏 |

「唯一实现」指同一事实、决策或判据只有一个权威承担者，不是只能有一个文件或只出现一次：
作者指引、确定性脚本、语义审查可以共同承担一个功能，各自新增的作用要说清。

本轮沿用功能ID，职责搬迁、判据修正及能力增量在既有功能项下标注。树的粒度依据真实职责，不以证明“没有加功能”为目标；后续出现独立能力再调整粒度。

## 功能树

- **F1 需求取材与范围确定** — F1.1 需求系统与本地起手 · F1.2 补充正文与格式转换 ·
  F1.3 图片身份与用途 · F1.4 来源盘点与增量变化 · F1.5 需求与范围分析 ·
  F1.6 人定材料与承载范围 · F1.7 形成开发需求输入
- **F2 面向人的 Story** — F2.1 成文前原材料定位与初筛 · F2.2 Spec 与写作设计衔接 ·
  F2.3 按需材料送达 · F2.4 正文表达与可靠落盘（F2.4.1 读者问题与章节职责 ·
  F2.4.2 图表与正文协作 · F2.4.3 验收与交付可操作）· F2.5 契约查阅附录 ·
  F2.6 标题引用与可读整理 · F2.7 写后整篇核对
- **F3 决策与评审回流** — F3.1 发现并解释判断 · F3.2 生成评审件并保护人工区 ·
  F3.3 归档与远程恢复 · F3.4 获取并处置评审反馈
- **F4 知识应用与维护解耦** — F4.1 知识登记与读取 · F4.2 项目事实与部件画像 ·
  F4.3 规约适用与具体要求 · F4.4 设计模式候选与选择 · F4.5 Plan 知识设计与义务传递 ·
  F4.6 Coding 落实与可执行检查 · F4.7 Review 知识复核 · F4.8 UT 义务验证 ·
  F4.9 实机及其他验证分派
- **F5 推进恢复与交付保障** — F5.1 阶段作者任务送达 · F5.2 进度与中断恢复 ·
  F5.3 确定性校验与登记 · F5.4 返修与错误恢复 · F5.5 独立审查与 Framework 闭环 ·
  F5.6 交付选择与能力披露 · F5.7 必要运行证据与诊断
- **F6 跨仓安装升级** — F6.1 首次接入与画像 · F6.2 机制升级与文件退出 ·
  F6.3 业务对接所有权 · F6.4 安装结果与配置边界
- **F7 共同支撑（不直接面向用户）** — F7.1 配置路径与数据解析 · F7.2 材料与输出操作支撑

---

## F1 需求取材与范围确定

**目的**：把外部需求变成经确认的本部件开发输入。**输入**：需求单或本地材料、用户决定。
**分工**：模型判范围与充分性；脚本取材、导入、保存身份与人的决定。**组合**：F1.1→F1.7 顺序协作，
父级不另建实现层。

### F1.1 需求系统与本地起手

- **目的**：远程单从需求系统取材，本地单从仓内材料起手，两条路都能开工。
- **输入**：AR 编号或本地单号、mcp token、工程根。
- **现行实现**：`adapters/story.js`（`cmdInit`/`readTicket`/`systemWrite`，目标仓自备，包内是替身）；
  `flow/inputs.py::cmd_init`（建工作区骨架，落 `inbox/README.md`）；
  `flow/state.py::SKILL_ROOT` 定位模板；`SKILL.md` 初始化一节给编排。
- **消费者**：后续所有步骤的 feature 目录。
- **失败出口**：适配层非 0 退出且 JSON 带 `success:false`；`cmd_init` 只建缺件，已有文件不覆盖。
- **证据**：`test_flow_module_layout::…template_is_found_from_another_cwd`（模板落地字节与
  Skill 自带那份一致）、`test_multi_case_cli`、`test_requirement_system`。
- **本轮变化**：模板定位从各处数目录层数收敛到 `SKILL_ROOT` 一处（Q9）。

### F1.2 补充正文与格式转换

- **目的**：人工放进 `inbox/` 的 docx / 文本被转成上游正文，图片抽出并保留引用。
- **输入**：`inbox/` 下的文件与 AI 写的 `.classify.json`。
- **现行实现**：`materials/importer.py`（`scan_sources`/`read_classify`/`validate`/
  `docx_to_markdown`/`convert_sources`/`render_target`/`backup`/`cmd_import`）；
  入口 `core/import_sources.py::main`；规则页 `rules/inbox_import.md`。
- **消费者**：`RR/prd.md`、`SR/design.md`、`AR/story-src/upstream.md`、`ux-reference/README.md`。
- **失败出口**：`ImportError_` → 整批不落盘（没有「部分导入成功」）；没归类的文件显式报错。
- **证据**：`test_material_rounds`、`test_material_delivery`、`test_image_registration`。
- **本轮变化**：导入正文从入口 `main` 搬进 `importer.cmd_import`，入口只留分派（Q9）；
  规则页里的登记命令去掉 PowerShell 下会当字面参数的续行反斜杠（Q10）。

### F1.3 图片身份与用途

- **目的**：一张图有确定身份，能被引用、能解释为什么不用，换名换落点不变成两张图。
- **输入**：原图文件、图意说明、采用与否的决定。
- **现行实现**：`materials/registry.py`（`collect_materials`/`file_digest`/`read_captions`/
  `write_caption`/`write_unused`/`clear_unused`）；`materials/importer.py`
  （`caption_image`/`mark_used`/`mark_unused`/`register_ux`/`resolve_image_arg`）；
  `story/images.mjs::imagesIn` 读清单形成作者面的图片集合。
- **消费者**：作者任务包的逐图任务、附录材料清单、图引用检查。
- **失败出口**：图片路径解析不到时报出可跑的命令；清单形状不对报**缺口**而不是「没有图」。
- **证据**：`test_image_registration`、`test_author_task_package::…images_in_the_material_list…`。
- **本轮变化**（Q7/第一包 R1）：退掉「`AR/assets/` 归档副本区未登记也按字节认」的特权，
  身份一律按登记判；清单形状不对与零图分开报。

### F1.4 来源盘点与增量变化

- **目的**：知道手上有什么材料、还缺什么、什么时候该重新判断。
- **输入**：磁盘现状（上游正文、收件箱原件、图片）。
- **现行实现**：`materials/registry.py`（`build`/`compute_digest`/`collect_sources`/`pending`/
  `refresh`/`read`/`digest_with`/`source_sha`）；`flow/routing.py`
  （`live_materials`/`material_state`/`pending_import_step`）一次命令取一份快照。
- **消费者**：轮次判定、关卡提示、作者包的材料现状、`status` 输出。
- **失败出口**：算不出清单时沿 `FlowError` 退出，不伪造 `false`。
- **证据**：`test_s4_commit::TheMaterialFactIsTakenOncePerTimepoint`、`test_material_rounds`。
- **本轮变化**：材料事实在一条命令里只取一次（Q1）；`material_state` 等搬进 `flow/routing.py`（Q9）。

### F1.5 需求与范围分析

- **目的**：形成需求概览、本部件视角、本 AR 定位与待实现功能清单，供关卡决定。
- **输入**：上游材料、部件画像。
- **现行实现**：规则页 `rules/init_analysis.md`（模型产出 `init-analysis.md` 与两份侧车）；
  `flow/inputs.py`（`read_positioning`/`read_scope_options`/`POSITIONING_FIELDS`）读侧车并登记；
  `flow/rounds.py::cmd_round` 把它们并进本轮契约。
- **消费者**：第二级关卡的选项集、Story 范围章。
- **失败出口**：侧车形状不对时 `FlowError` 指名缺哪个字段；侧车读后即销毁，不留半份。
- **证据**：`test_s4_commit`、`test_material_rounds`、`test_spec_story_gate`。

### F1.6 人定材料与承载范围

- **目的**：三级关卡各问一件事，人的每次选择连同摆过的选项一起留痕。
- **输入**：`.gate-options.json`/`.scope-options.json`/`.split-parts.json` 侧车与人的回答。
- **现行实现**：`flow/decisions.py::cmd_decide`；值域真源在
  `contracts/story-chapters.json::gates`，Python 侧 `flow/inputs.py::MATERIAL_CHOICES` 与
  JS 侧 `flow/check.mjs::materialChoices` 都从那里读；规则页 `rules/scope_gate.md`。
- **消费者**：流程契约 `story-flow.json` 的 `gates`；spec 阶段门禁。
- **失败出口**：`decide` 退出码 2 = 选择已记录但校验不过、不得前进；只认人签（`ACTORS`）。
- **证据**：`test_flow_module_layout::…gate_values_come_from_the_chapter_contract`（侧车说合法
  也不算，值域以合同为准）、`test_s4_commit`、`test_material_rounds`。

### F1.7 形成开发需求输入

- **目的**：把提取稿提交成 `AR/design.md`，并留下可回查的上游原件。
- **输入**：`AR/story-src/design-draft.md`（或 `--from` 指定）、当前轮次与范围。
- **现行实现**：`flow/submission.py`（`resolve_candidate`/`section_numbers`/`is_ar_skeleton`/
  `candidate_problems`/`ar_input_identities`/`prior_ar`/`cmd_complete`）；
  骨架生成 `flow/inputs.py::ar_design_skeleton`（与空骨架判定共用同一函数）；
  规则页 `rules/ar_design_init.md`。
- **消费者**：spec 阶段、Story 的范围与方案章、附录材料清单里的「上游原件」。
- **失败出口**：五段结构对不上、候选还是空骨架、章号不连续都在写盘前拒绝；
  保存失败可重试且不丢原件。
- **证据**：`test_s4_commit`（三身份 × 保存失败恢复）。
- **本轮变化**（Q7）：被覆盖的上游 AR 按轮次留存后**进入材料清单与来源检查**，
  成为一份有身份的独立材料，不再只是一份备份。

---

## F2 面向人的 Story

**目的**：给评审者一篇能读懂整件事的叙事。**分工**：AI 按章写；脚本管落盘、结构、投影与核对。

### F2.1 成文前原材料定位与初筛

- **目的**：动笔前知道材料在哪、够不够、哪些必须读。
- **输入**：材料清单、上游正文、流程契约。
- **现行实现**：`hooks/spec/author.mjs::taskPackage`（本次任务包）；
  `story/sources.mjs`（`scanSources`/`sourceStatus`/`upstreamDocs`/`materialsNotReady`）；
  `flow/client.mjs::queryFlowStatus`（JS 侧唯一的流程状态查询）。
- **消费者**：作者（模型）动笔前的输入。
- **失败出口**：`queryFlowStatus` 把「没走过 /story」「业务失败」「输出不是 JSON」「形状不对」
  「没跑完」分成五种可辨结果，不混成一句「取不到」。
- **证据**：`test_flow_status_client`、`test_author_context_entry`、`test_author_task_package`。

### F2.2 Spec 与写作设计衔接

- **目的**：Story 的章骨架、术语起始行、必要小节与表头从 spec 与合同派生，作者不猜格式。
- **输入**：`spec/spec.md`、`contracts/story-chapters.json`、知识判断件。
- **现行实现**：`story-build.mjs::cmdSkeleton` → `story/drafts.mjs::writeDrafts`；
  `story/chapter-contract.mjs`（`chapterSeedRows`/`requiredH3`/`requiredTables`/`renderTable`）；
  `story/context.mjs::createContext` 一次备齐当前输入。
- **消费者**：`AR/story-src/drafts/NN-<章名>.md`。
- **失败出口**：起手预检不过不写盘（缺 spec、缺决策登记、流程未收口都指名）。
- **证据**：`test_story_build`、`test_writing_flow`。

### F2.3 按需材料送达

- **目的**：作者要用的东西在动笔前一次给齐：位置、知识判断、验收键、决策、图、上游原件。
- **输入**：feature 目录现状。
- **现行实现**：`hooks/spec/author.mjs`（`positionSection`/`knowledgeSection`/`acceptanceKeys`/
  `decisionSection`/`imageSection`/`originalArSection`/`diagramSection`/`vocabularySection`）；
  原则页 `hooks/spec/author.md`。
- **消费者**：作者（模型）。
- **失败出口**：读不到的材料按缺口报出；代表路径一张都不可读时不给「可跑的命令」。
- **证据**：`test_author_task_package`（一图一任务、别名、坏形状 ×4、坏路径 ×4）。
- **本轮变化**（Q7/第一包 R1）：**一张图一个任务单元**（含别名与代表路径），
  清单形状不对报缺口；上游原件单独成节。

### F2.4 正文表达与可靠落盘

- **目的**：一次写一章、原子落盘，章外字节不受影响。
- **输入**：章草稿。
- **现行实现**：`story/chapter.mjs`（`cmdChapter`/`chapterProblems`/`stripGuidance`/
  `stripOwnHeading`/`strayHeadings`/`nextSteps`）；`story/document.mjs`
  （`fenceRanges`/`parseChapter`/`storySections`/`chapterSpan`）。
- **消费者**：`AR/story.md`。
- **失败出口**：写前核不过不落盘；落盘成功后即使后续输出出错也**不报成失败**；
  冻结之后拒绝写入并指出 `reopen`。
- **证据**：`test_story_build`（`TheChapterIsCheckedBeforeItLands` 13 例、
  `TheBytesOutsideTheChapterAreBytes`、`AWriteThatLandedIsNeverReportedAsFailed`）、
  `test_chapter_view::OneFenceScannerForEveryConsumer`。
- **本轮变化**（Q5）：先核后写；单章与全篇同一份判据实现；接续信息收成前三行。

#### F2.4.1 读者问题与章节职责

- **目的**：每章回答确定的读者问题，形式按内容关系选，不套固定排版。
- **现行实现**：`contracts/story-chapters.json::chapters`（读者问题、必要结构、形态）；
  写作页 `phases/story-write.md` 十章各自怎么组织；`story/chapter-contract.mjs` 核必要结构。
- **失败出口**：必要 H3 或必需表缺失时按位置指名（不是只说「结构不对」）。
- **证据**：`test_story_build::TestRequiredStructureIsMinimalButReal`、`test_narrative_variants`。

#### F2.4.2 图表与正文协作

- **目的**：图讲的事在正文里有承接，正文引的图存在，源图有对应。
- **现行实现**：`story/images.mjs`（`diagramsOf`/`diagramTopic`/`diagramsNotCarried`/
  `danglingFigures`/`carriedDiagramProblems`/`imageProblems`）；`story/document.mjs::hasDiagram`。
- **失败出口**：图连图、图前无承接句、引用不存在的图都按行报。
- **证据**：`test_story_build`、`test_golden_sample`、失效形态 S01/S20。
- **本轮变化**（Q7）：源图给**坐标**（`at:{from,to}`，1 起、含围栏行）而不是复制围栏。

#### F2.4.3 验收与交付可操作

- **目的**：验收条目独立可执行，交付章讲清控制对象与时机。
- **现行实现**：`hooks/shared/contracts.mjs::readAcceptance` 一次验证并分组；
  `hooks/testing/post_check.mjs::referencedAcceptanceIds`；合同的验收章必要结构。
- **失败出口**：验收键在 spec 与 story 之间对不上时指名编号。
- **证据**：`test_contracts_single_source`、`test_spec_contract_section`。
- **本轮变化**（Q3）：验收条目一次验证并分组，各阶段只选集合，不再各自转换。

### F2.5 契约查阅附录

- **目的**：附录里的接口、数据、边界、判定是 spec 与知识判断的精确投影，作者解释与投影共存。
- **输入**：`spec/spec.md` §9、`spec/knowledge-use.yaml`。
- **现行实现**：`story/appendix.mjs`（`appendixProjection`/`projectAppendix`/`specGaps`/
  `appendixSpecGaps`/`appendixSourceProblems`/`appendixStructureProblems`/`appendixZoneProblems`/
  `zonesOnDisk`/`firstDiff`）；机器区标记与摘要在 `story/document.mjs`
  （`ZONE_BEGIN`/`ZONE_END`/`zoneBlock`/`projectionDigest`/`recordedDigest`/`ProjectionConflict`）。
- **消费者**：`AR/story.md` 附录 A–E。
- **失败出口**：投影与盘上不一致时**报出差在哪一行**并给重新生成的出口；
  必需来源缺失报缺口，不当成合法的空投影；离线模式没有真源，比真源的判据早退。
- **证据**：`test_story_build::TheMachineZoneIsCheckedAgainstItsSource`（12 例）、金样 AR90004。
- **本轮变化**（Q6）：机器区集合两向核（未知区名也报）、标记归属唯一、必需来源缺失不再放行。

### F2.6 标题引用与可读整理

- **目的**：章序、小节序、图序由脚本统一铺；作者写业务名。
- **现行实现**：`story/document.mjs`（`normalizeHeading`/`takeAuthorNumber`/`renumberStory`/
  `NUMBER_PREFIX`/`LETTER_PREFIX`/`FIGURE_PREFIX`）；入口 `story-build.mjs::cmdNumber`。
- **失败出口**：编号幂等，已经对的文件一个字节不改；剥错编号会让小节定位失败，故以位置为主判据。
- **证据**：`test_story_build`、`test_chapter_view`。
- **本轮变化**（Q5）：`headings.mjs` 并入 `document.mjs`——切文、定位与编号同属一件事。

### F2.7 写后整篇核对

- **目的**：十章齐了做一次全篇核对，问题按类分组给作者。
- **现行实现**：`story/check.mjs`（`cmdCheck`/`groupedProblems`）调用各领域的问题函数；
  全局章序、H1、完成态归它，领域判据回所属模块。
- **失败出口**：非 0 退出并按类分组；「未执行」与「通过」分开报（缺材料清单时记一笔不拦）。
- **证据**：金样 AR90004 离线通过、`test_story_build`、`check_failure_modes` 64 条。
- **本轮变化**（Q5/Q8）：入口只组合，不再逐域重实现。

---

## F3 决策与评审回流

### F3.1 发现并解释判断

- **目的**：成文过程中定下的与仍待定的判断都登记，带依据、建议与影响。
- **现行实现**：`story/review.mjs`（`DECISION_FIELDS`/`decisionList`/`decisionsMissing`/
  `decisionProblems`/`DECISION_SHAPE`）；类别与豁免在 `contracts/story-chapters.json::decision_categories`。
- **失败出口**：字段缺失或类别非法时指名议题；登记不合法时 `cmdBuild` **拒绝渲染**。
- **证据**：`test_review_golden`、`test_story_build`。

### F3.2 生成评审件并保护人工区

- **目的**：`AR/review.md` 的机器区确定性重算，评审人写的内容一个字节不动。
- **现行实现**：`story/review.mjs`（`renderReview`/`renderMachineZone`/`renderHumanZone`/
  `machineZoneOf`/`extractHumanZone`/`extractFreeformZone`/`issueHandEdited`/`groupByCategory`/
  `reviewFormProblems`）。
- **失败出口**：机器区被人动过时**拒绝重新渲染**并说明怎么撤销（`ProjectionConflict`）；
  与附录不同，这里不做全文逐行比对——它比的是区块摘要。
- **证据**：`test_review_golden`、`test_story_build`、失效形态 R01。
- **本轮变化**（Q6）：`review-render.mjs` 并入 `review.mjs`，读取、校验与渲染同一处；
  `cmdBuild` 在登记不合法时不渲染。

### F3.3 归档与远程恢复

- **目的**：把 story 与 review 送进需求系统，备份被覆盖的正文，可恢复上一版。
- **现行实现**：`adapters/story.js`（`cmdArchive`/`cmdRestore`/`systemWrite`，目标仓自备）；
  `flow/lifecycle.py::cmd_archived` 登记归档态；交付门 `story/delivery.mjs`。
- **失败出口**：归档前交付门不过就不上传；登记前重跑 `story-build check`，不过不登记。
- **证据**：`test_requirement_system`、`test_s4_commit::RegistrationRunsTheRealChecker`。

### F3.4 获取并处置评审反馈

- **目的**：拉回评审意见，逐条处置并修订 spec，处置留台账。
- **现行实现**：`adapters/review.js::fetchReview`；规则页 `rules/review_reflow.md`；
  台账 `AR/review-disposition.json`。
- **失败出口**：拉不到意见时非 0 退出并说明；已归档的 review 只备份不重建。
- **证据**：`test_requirement_system`、`test_conclude`。

---

## F4 知识应用与维护解耦

### F4.1 知识登记与读取

- **目的**：项目知识按清单激活，读不到就报，不静默当成「没有知识」。
- **现行实现**：`hooks/shared/knowledge.mjs`（`knowledgeFiles`/`activeKnowledge`/`entryById`/
  `selfCheck`/`parseConstraintFile`/`parsePatternFile`/`parseFactFile`/`parseIndexFile`）；
  清单在 `manifest.yaml::provides.knowledge`（归目标工程）。
- **失败出口**：`KnowledgeError` throw——登记了读不到必须出声；清单为空是合法状态（本仓未配置知识）。
- **证据**：`test_empty_knowledge_repo`、`test_neutral_knowledge`、失效形态 M06。

### F4.2 项目事实与部件画像

- **目的**：事实类知识只记事实，供各阶段引用。
- **现行实现**：`knowledge/facts/*`（内容归目标工程）；`knowledge.mjs::parseFactFile`；
  作者面经 `hooks/spec/author.mjs::knowledgeSection` 送达。
- **失败出口**：事实文件读不到按 F4.1 报。
- **证据**：`test_knowledge_use`、`test_author_task_package`。

### F4.3 规约适用与具体要求

- **目的**：每条激活的规约都要有去处：命中写本需求要做什么，不命中写可回查的依据。
- **现行实现**：真源 `spec/knowledge-use.yaml`；
  `hooks/shared/knowledge-use/document.mjs`（`readUse`/`manifestDigest`/`renderSkeleton`/
  `text`/`requirements`）、`validation.mjs`（`coverageProblems`/`contractNames`/`isEmptyReason`）、
  `projection.mjs`（`renderZones`/`applyZones`/`zoneProblems`）；
  语义判据 `rules/spec-rules.overlay.yaml::knowledge_spec_exit_substance`。
- **消费者**：spec §10、plan 义务、后续阶段检查。
- **失败出口**：`UseError` throw；覆盖不全、编号不在册、落点引不到都按条报；
  投影与真源对不上时报出并给重新生成的命令。
- **证据**：`test_knowledge_use`、`test_neutral_knowledge`、`test_plan_pattern_crosscheck`。
- **本轮变化**（Q10）：读取、校验、投影拆成三个模块，规范化只在 `document.mjs` 维护一份。

### F4.4 设计模式候选与选择

- **目的**：spec 只登记候选不选型，plan 才选。
- **现行实现**：`knowledge-use/projection.mjs::renderPatterns`、`validation.mjs` 里的候选在册校验；
  `hooks/plan/post_check.mjs`（`specPatternHits`/`planPatternChoices`）核 plan 的选型；
  `rules/spec-rules.overlay.yaml::knowledge_candidates_registered`。
- **失败出口**：spec 里写了 `chosen` 直接报；plan 选了不在候选里的模式报。
- **证据**：`test_plan_pattern_crosscheck`（含多候选、无候选、拆分采纳）。

### F4.5 Plan 知识设计与义务传递

- **目的**：命中的规约在 plan 变成挂在实体上的义务。
- **现行实现**：`hooks/shared/obligations.mjs`（`obligationsFromContracts`/`misplacedMust`/
  `patternRolesFromContracts`/`VERIFY_KINDS`）；`hooks/plan/post_check.mjs`；
  模板 `templates/plan-sections.md`；`rules/plan-rules.overlay.yaml`。
- **失败出口**：`must` 挂错位置、义务不在命中集合里都指名。
- **证据**：`test_neutral_knowledge::ThePlanSideReadsTheSameSource`。

### F4.6 Coding 落实与可执行检查

- **目的**：编码阶段能查到本需求要落实的规约要求，并给出可执行的检查。
- **现行实现**：`hooks/coding/post_check.mjs`（`tailIdentifier`/`findIdentifier`）；
  `hooks/shared/probes.mjs`（`filesForEntity`/`runProbe`/`methodBody`）；
  `rules/coding-rules.overlay.yaml::knowledge_landing_in_code`；原则页 `hooks/coding/author.md`。
- **失败出口**：探针跑不起来如实报，不当成通过。
- **证据**：`test_hooks_session`、`test_harness`。

### F4.7 Review 知识复核

- **目的**：代码检视时按义务清单复核。
- **现行实现**：`hooks/review/post_check.mjs`（`reviewTable`/`cellOf`/`VERDICTS`）；
  `rules/review-rules.overlay.yaml::knowledge_obligation_reviewed`；原则页 `hooks/review/author.md`。
- **失败出口**：报告缺失由框架报，本判据如实记一笔「没跑成」。
- **证据**：`test_hooks_session`。

### F4.8 UT 义务验证

- **目的**：单元测试阶段验证分派到这里的义务。
- **现行实现**：`hooks/ut/post_check.mjs`；`rules/ut-rules.overlay.yaml::knowledge_obligation_verified`；
  原则页 `hooks/ut/author.md`。
- **失败出口**：义务没有对应验证时指名。
- **证据**：`test_neutral_knowledge::TheObligationReachesTheDownstream`。

### F4.9 实机及其他验证分派

- **目的**：需要实机验证的义务分派到 testing。
- **现行实现**：`hooks/testing/post_check.mjs::referencedAcceptanceIds`；
  `rules/testing-rules.overlay.yaml`；原则页 `hooks/testing/author.md`。
- **失败出口**：验收编号引不到时指名。
- **证据**：`test_neutral_knowledge`、`test_harness`。

---

## F5 推进恢复与交付保障

### F5.1 阶段作者任务送达

- **目的**：每个阶段动笔前，作者拿到本阶段的要求；spec 另有一份按当前状态算出来的任务包。
- **现行实现**：六份 `hooks/<phase>/author.md`；`hooks/spec/author.mjs::taskPackage`；
  `hooks/shared/gate.mjs::authorDoc` 把原则页接进门禁报错。
- **失败出口**：原则页读不到时 `docText` 返回 null（不是空串），调用方报缺件。
- **证据**：`test_author_context_entry`、`test_author_task_package`、`test_hooks_session`。

### F5.2 进度与中断恢复

- **目的**：换会话也能接着做：位置由数据回答，不靠记忆。
- **现行实现**：`flow/lifecycle.py::cmd_status`；`flow/routing.py`
  （`next_step`/`scope_step`/`spec_stage_step`/`sidecar_shape`/`frozen_tail`/`material_gate_state`）；
  `flow/client.mjs` 给 JS 侧同一口径。
- **失败出口**：契约不存在时回 `exists:false` 与该走的第一步，不报错。
- **证据**：`test_flow_status_client`、`test_multi_case_cli`、`test_s4_commit`。
- **本轮变化**（Q9）：路由与命令分文件，方向单一（命令问路由，路由不问命令）。

### F5.3 确定性校验与登记

- **目的**：成文态登记之前把确定性问题清零，登记之后冻结。
- **现行实现**：`flow/lifecycle.py::cmd_story`（project → number → build → check → 记）；
  台账冻结 `flow/state.py::STORY_SRC_FROZEN` + `ledger_digest`；
  JS 侧 `story/context.mjs`（`STORY_SRC_LEDGERS`/`requireLedgers`/`ledgerDigestProblems`/
  `strayFileProblems`/`refuseIfFrozen`）。
- **失败出口**：四步任一不通过就不登记，并把 `story-build` 自己的话原样带出来。
- **证据**：`test_s4_commit::RegistrationRunsTheRealChecker`、`test_negative_guards`、
  `test_material_rounds::RegistrationReprojectsFirst`。
- **本轮变化**（Q9）：公共 CLI 由 `flow/state.py::CORE_DIR` 一处定位——定位错一层会退化成
  spawn 失败，与「没通过」同形，现在有用例区分。

### F5.4 返修与错误恢复

- **目的**：成文之后发现问题能退回改，过程件不丢。
- **现行实现**：`flow/rounds.py::cmd_reopen`（唯一的回退出口）；`story-build skeleton` 补缺席章；
  草稿目录 `story/drafts.mjs::DRAFTS` 登记后不删。
- **失败出口**：未收口时 `reopen` 拒绝并说明当前状态。
- **证据**：`test_story_build`、`test_writing_flow`、`test_s4_commit`。

### F5.5 独立审查与 Framework 闭环

- **目的**：确定性门全绿之后，把这一版产物交给独立审查，结论可机读。
- **现行实现**：`hooks/shared/reader-review-task.mjs`（`readerReviewTask`/`imageRows`/
  `reviewMethod`/`longestFence`/`contractOf`）把**当前 Story 全文一次**放进任务；
  审查方法与输出要求在 `rules/spec-rules.overlay.yaml::story_reader_review` 一处维护；
  `hooks/shared/verifier-report.mjs`（`storyReviewProblems`/`summaryRow`/`readerReviewDetails`）
  读报告并归一化出 `reviewVerdict`；`hooks/shared/pre_verifier.mjs` 登记 check id。
- **失败出口**：报告缺失或结论格不可取得时 `reviewVerdict` 为 null；汇总状态已可读而后续证据/明细结构不完整时，可保留该 verdict 并返回结构问题。交付同时核结构与真实结论，不从 detail 猜。
- **证据**：`test_verifier_report_protocol`（含四条真实命令用例）、`test_verifier_chain_in_workspace`。
- **本轮变化**（Q8/第一包 R1/R2）：全文一次给全；方法只在 overlay 一份；
  人数门槛退场，改成「协作次序按实际关系判」。

### F5.6 交付选择与能力披露

- **目的**：交付门按审查的实际结论放行，宿主没有审查员时如实披露。
- **现行实现**：`story/delivery.mjs`（`deliveryProblems`/`deliveryNextSteps`/`receiptRunner`）；
  入口 `story-build.mjs` 的 `check --deliver`。
- **失败出口**：`reviewVerdict !== 'PASS'` 时拒绝交付并说明判的是什么；
  `NOT_APPLICABLE` 时记一笔「未经读者语义审查即交付」；框架起不来如实报，不当成通过。
- **证据**：`test_verifier_report_protocol`（交付判据）、`test_verifier_smoke`。
- **本轮变化**（Q8）：从「核形态」改成「核实际结论」。

### F5.7 必要运行证据与诊断

- **目的**：门禁跑过就留痕，失败也看得出是没跑还是没过。
- **现行实现**：`hooks/shared/evidence.mjs`（`writePostCheckEvidence`/`STATUS`/`EVIDENCE_FILE`）；
  `hooks/shared/gate.mjs`（`guard`/`gate`）统一入口守卫与报错拼装。
- **失败出口**：留痕写不出来时出声到 stderr，但不改判据结论。
- **证据**：`test_hooks_session`、`test_harness_selfcheck`。

---

## F6 跨仓安装升级

### F6.1 首次接入与画像

- **目的**：目标工程首次装上时建知识说明骨架，不复制来源仓的业务知识。
- **现行实现**：`skills/story-adaptation/scripts/adapt-scan.mjs`
  （`skeletonKnowledge`/`freshIdentity`/`composeManifest`）；`skills/story-adaptation/SKILL.md`。
- **失败出口**：目标不是 git 仓、写入面有未提交改动时退出码 2 并停。
- **证据**：`test_adapt_ownership`、`test_adapt_source_kinds`。

### F6.2 机制升级与文件退出

- **目的**：公共机制整份换掉，包里没有的在目标那边也删掉。
- **现行实现**：`adapt-scan.mjs`（`CORE`/`walk`/`coveredFiles`/`inWriteFace`/`dirtyPaths`/`git`）。
- **失败出口**：清掉文件要报出来（静默删比不删更糟）。
- **证据**：`test_adapt_ownership::TheMechanismFollowsThePackage`
  （含本轮新增：新 python 包真被装上、同名旧平铺文件真被清掉）。

### F6.3 业务对接所有权

- **目的**：`adapters/` 归目标；**看来源**——Demo 来源不给也不覆盖，业务仓之间整份换。
- **现行实现**：`adapt-scan.mjs`（`ADAPTERS`/`WITH_ADAPTERS`/`MOCK_ADAPTER_PACKAGE`/`PKG_NAME`）；
  合同在 `skills/story/scripts/README.md`。
- **失败出口**：判来源看目标 manifest 的 `name`（归目标、升级不改），不靠仓名长相猜。
- **证据**：`test_adapt_source_kinds`（两种来源各一组）。

### F6.4 安装结果与配置边界

- **目的**：目标的身份、知识与自己的说明在升级中保住；安装完自检。
- **现行实现**：`adapt-scan.mjs`（`TARGET_OWNED_KEYS`/`versionNotes`/`withVersionNotes`/
  `knowledgeBlock`/`bridgesOf`/`missingGitignoreLines`/`extensionSectionEnd`/`replaceZone`）；
  `--check` 八条自检。
- **失败出口**：`--check` 非 0 并指名哪一条不过。
- **证据**：`test_adapt_ownership`、`test_adapt_source_kinds`、
  `test_story_build::test_the_manifest_version_covers_this_round`。
- **本轮变化**（用户 2026-09-13）：包不再在 manifest 里记演进——`version:` 上面那一段归目标，
  演进记录只在 `test/story/release/` 的发布说明里。

---

## F7 共同支撑（不直接面向用户）

### F7.1 配置路径与数据解析

- **现行实现**：`hooks/shared/paths.mjs`（`readConfig`/`extensionRoot`/`featuresDir`/`featureRoot`/
  `relDisplay`/`readTextOrNull`/`readJsonOrNull`/`lines`）；`hooks/shared/yaml-lite.mjs`（`parseYaml` 等）；
  Python 侧 `materials/importer.py::features_dir` 与 `DEFAULT_PROJECT_ROOT`（两个入口共用一处）。
- **失败出口**：读不到回 null，由调用方决定是缺件还是不适用；解析失败抛错，不当成空。
- **证据**：`test_features_dir_config`、`test_cli_config_failover`、
  `test_flow_module_layout::…default_project_root_is_defined_once`。

### F7.2 材料与输出操作支撑

- **现行实现**：`story/context.mjs`（`readText`/`readRaw`/`readJson`/`writeJson`/`fail`/
  `compileIdShapes`/`digestOf`）；`story/sources.mjs`（`relFromFeature`/`relFromStory`/`joinPosix`/
  `basename`/`readManifest`）；`flow/state.py`（`log`/`now`/`load`/`save`/`require`/`ledger_digest`）。
- **失败出口**：`readRaw` 保字节（章提交用），`readText` 去 BOM；两者不混用。
- **证据**：`test_story_build::TheBytesOutsideTheChapterAreBytes`、`test_chapter_view`。

---

## 未验证与边界

- 本文件的「证据」列指**离线确定性用例**。真实 CLI 未跑（Q11 §2 才跑），
  模型语义质量不在本稿的结论范围内。
- F1.1、F3.3、F3.4 的适配层在本仓是替身（本地目录模拟需求系统），
  真实需求系统对接由各部署环境自备实现。
- `knowledge/` 下的知识**内容**归目标工程，本稿只登记读取与应用机制，不评内容。
