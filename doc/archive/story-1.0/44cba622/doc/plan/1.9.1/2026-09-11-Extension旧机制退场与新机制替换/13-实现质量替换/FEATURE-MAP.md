# 功能 → 实现 映射（第二包候选稿）

> **候选状态**与**基线**同 [FEATURES.md](FEATURES.md)：`77314387`，2026-09-13，按符号定位。
> 反向（实现 → 功能）在 [FEATURE-CONTENT-MAP.md](FEATURE-CONTENT-MAP.md)。
>
> 路径一律相对 `doc/extensions/`。符号名后不带行号——本轮之后还会有返修，
> 行号漂移而符号稳定；确需行号时以本基线为准。
>
> 「承担」列写这个文件在这条功能里**做什么**，不是文件简介；一个文件出现在多条功能下是常态
> （可多归属不可遗漏），但同一个**事实/决策/判据**只能有一个权威承担者。

## F1 需求取材与范围确定

### F1.1 需求系统与本地起手

| 文件 | 承担 |
|---|---|
| `skills/story/scripts/adapters/story.js` | `cmdInit`/`readTicket`/`ticketText`/`ticketTitle`/`systemWrite`/`writeDetail`：按协议取材、落 `AR/design.md` 与单据身份（目标仓自备实现，包内为替身） |
| `skills/story/scripts/adapters/token.js` | 取 mcp token：stdout 即 token 本身 |
| `skills/story/scripts/core/flow/inputs.py` | `cmd_init`/`read_ids`/`ar_design_skeleton`：建工作区骨架，只补缺件 |
| `skills/story/scripts/core/flow/state.py` | `SKILL_ROOT`：定位 `templates/inbox-readme.md` |
| `skills/story/templates/inbox-readme.md` | 收件箱说明书，随骨架落盘 |
| `skills/story/SKILL.md` | 「初始化」「链条」：远程与本地两条路怎么分 |

### F1.2 补充正文与格式转换

| 文件 | 承担 |
|---|---|
| `skills/story/scripts/core/materials/importer.py` | 全部导入实现：`scan_sources`/`read_classify`/`is_text`/`validate`/`read_media`/`_heading_level`/`_run_text`/`_para_markdown`/`_table_markdown`/`docx_to_markdown`/`backup`/`demote_headings`/`render_target`/`preview`/`convert_sources`/`cmd_import`；落点 `DOC_TARGET`/`UX_IMAGE_DIR`/`CLASSES`/`GENERATED_MARK` |
| `skills/story/scripts/core/import_sources.py` | `main`：四种模式的参数解析、分派与顶层 JSON 输出 |
| `skills/story/rules/inbox_import.md` | 材料怎么放、归类写哪、什么时候跑脚本 |
| `skills/story/scripts/core/materials/registry.py` | `collect_sources`/`_same_text`：按磁盘判「这批料并没并进正文」 |

### F1.3 图片身份与用途

| 文件 | 承担 |
|---|---|
| `skills/story/scripts/core/materials/registry.py` | `file_digest`/`kind_of`/`collect_materials`/`read_captions`/`_write_entry`/`write_caption`/`write_unused`/`clear_unused`/`CAPTIONS`：图的内容身份与两件独立事实（是什么、为什么不用） |
| `skills/story/scripts/core/materials/importer.py` | `caption_image`/`mark_used`/`mark_unused`/`register_ux`/`resolve_image_arg`/`_image_for_mark`/`_no_such_image`：三条图片命令 |
| `skills/story/scripts/core/story/images.mjs` | `imagesIn`/`readablePaths`/`materialImages`：从清单读出作者面的图片集合，形状不对报缺口 |
| `skills/story/rules/inbox_import.md` | 「内嵌图里的界面设计图」：登记命令与两样必给的信息 |

### F1.4 来源盘点与增量变化

| 文件 | 承担 |
|---|---|
| `skills/story/scripts/core/materials/registry.py` | `build`/`compute_digest`/`digest_with`/`source_sha`/`pending`/`refresh`/`read`/`write`/`path_of`/`MANIFEST`/`SOURCE_DOCS`/`SOURCE_DIRS`/`INBOX`：材料清单的唯一算法与唯一写入者 |
| `skills/story/scripts/core/flow/routing.py` | `live_materials`/`material_state`/`pending_import_step`：一条命令一份材料事实快照 |
| `skills/story/scripts/core/flow/rounds.py` | `cmd_round`：材料 digest 判轮次边界 |
| `skills/story/scripts/core/story/sources.mjs` | `readManifest`/`scanSources`/`sourceStatus`/`missingSourceLine`/`materialsNotReady`/`REMOTE_ONLY_SOURCES`：成文侧的来源现状 |

### F1.5 需求与范围分析

| 文件 | 承担 |
|---|---|
| `skills/story/rules/init_analysis.md` | 初析件五节的写法、侧车形态、四条纪律 |
| `skills/story/scripts/core/flow/inputs.py` | `read_sidecar`/`consume_sidecar`/`read_positioning`/`read_scope_options`/`POSITIONING_FIELDS`/`POSITIONING`/`SCOPE_OPTIONS`：侧车读后即销毁 |
| `skills/story/scripts/core/flow/rounds.py` | `cmd_round`：把定位与选项集登记进本轮 |
| `skills/story/scripts/core/flow/state.py` | `ANALYSIS`/`SCOPE_SOURCES`：初析件落点与范围来源强度 |

### F1.6 人定材料与承载范围

| 文件 | 承担 |
|---|---|
| `skills/story/scripts/core/flow/decisions.py` | `cmd_decide`：三级关卡的唯一写入者，校验与记录同一次调用 |
| `skills/story/scripts/core/flow/inputs.py` | `material_options`/`MATERIAL_CHOICES`/`MATERIAL_REQUEST_KEYS`/`chosen_dimension`/`split_carrier_options`/`sidecar_gate`/`read_gate_options`/`read_split_parts`/`GATE_OPTIONS`/`SPLIT_PARTS`：选项集与份表 |
| `skills/story/scripts/core/flow/state.py` | `GATES`/`ACTORS`/`CARRY_ALL`/`round_gates`/`last_gate`/`STORY_CONTRACT`：关卡常量与轮次条目 |
| `skills/story/contracts/story-chapters.json` | `gates`/`gates_note`：第一级值域的真源（Python 与 JS 两侧都读它） |
| `skills/story/scripts/core/flow/check.mjs` | `FLOW_GATES`/`materialChoices`/`FLOW_CARRY_ALL`/`FLOW_OUTCOMES`/`flowProblems`：JS 侧按同一真源核关卡 |
| `skills/story/rules/scope_gate.md` | 三级各问什么、人提出自己的拆法时怎么办 |

### F1.7 形成开发需求输入

| 文件 | 承担 |
|---|---|
| `skills/story/scripts/core/flow/submission.py` | `cmd_complete`/`resolve_candidate`/`section_numbers`/`is_ar_skeleton`/`candidate_problems`/`ar_input_identities`/`prior_ar`/`S4_HEADING`：候选核对、三份输入身份、原件按轮次留存、失败可重试 |
| `skills/story/scripts/core/flow/state.py` | `DESIGN`/`DESIGN_DRAFT`/`AR_SOURCES`/`S4_STEPS`：输入件与输出件分开的落点 |
| `skills/story/rules/ar_design_init.md` | 提取稿五段结构与两把裁剪标尺 |
| `skills/story/scripts/core/story/sources.mjs` | `originalArTarget`/`materialListTargets`：把留存的上游原件列进材料清单（Q7 增量） |
| `skills/story/scripts/core/flow/check.mjs` | `originalArSource`/`DESIGN_FILE`/`readFlow`：原件定位的唯一读取 |

## F2 面向人的 Story

### F2.1 成文前原材料定位与初筛

| 文件 | 承担 |
|---|---|
| `hooks/spec/author.mjs` | `taskPackage`/`positionSection`/`docText`/`SELF`/`SKILL_ROOT`/`USAGE`/`main`：本次任务包 |
| `skills/story/scripts/core/flow/client.mjs` | `FLOW_SCRIPT`/`queryFlowStatus`/`parseStatus`/`shapeProblem`/`PYTHONS`：JS 侧唯一的流程状态查询，五类可辨结果 |
| `skills/story/scripts/core/story/sources.mjs` | `sourceStatus`/`upstreamDocs`/`scanSources`/`materialsNotReady` |
| `hooks/spec/author.md` | spec 作者动笔前的原则页 |

### F2.2 Spec 与写作设计衔接

| 文件 | 承担 |
|---|---|
| `skills/story/scripts/core/story-build.mjs` | `cmdSkeleton`/`parseArgs`/`COMMANDS`/`main`：命令入口 |
| `skills/story/scripts/core/story/drafts.mjs` | `writeDrafts`/`draftPath`/`chapterDraft`/`guideLine`/`GUIDE_MARK`/`shellArg`/`DRAFTS`：章草稿与可复跑命令 |
| `skills/story/scripts/core/story/chapter-contract.mjs` | `chapterSeedRows`/`requiredH3`/`requiredTables`/`renderTable`/`tableSeed`/`appendixSeedRows`/`tableProblem`/`chapterStructureProblems`：必要结构的打底与核对同一份定义 |
| `skills/story/scripts/core/story/context.mjs` | `createContext`/`commonInputs`/`compileIdShapes`/`createOfflineContext`/`CORE_DIR`/`AR_ROOT_FILES`：一次备齐当前输入 |
| `skills/story/contracts/story-chapters.json` | `chapters`/`skeleton_note`/`structure_note`/`id_shapes`/`pending_mark`：章节合同 |
| `skills/story/phases/spec.md` | 阶段内顺序与六步 |

### F2.3 按需材料送达

| 文件 | 承担 |
|---|---|
| `hooks/spec/author.mjs` | `knowledgeSection`/`acceptanceKeys`/`acceptancePath`/`decisionSection`/`imageSection`/`originalArSection`/`diagramSection`/`vocabularySection`：逐类材料成节，一图一任务 |
| `skills/story/scripts/core/story/images.mjs` | `imagesIn`/`readablePaths`/`diagramsOf`/`diagramTopic`：图片集合与源图坐标 |
| `skills/story/scripts/core/story/language.mjs` | `clientVocabulary`/`CONTRACT_PATH`/`vocabularyCache`：客户端语境用词送达作者 |

### F2.4 正文表达与可靠落盘

| 文件 | 承担 |
|---|---|
| `skills/story/scripts/core/story/chapter.mjs` | `cmdChapter`/`chapterProblems`/`stripGuidance`/`stripOwnHeading`/`strayHeadings`/`placeholderProblems`/`withoutDiagramBodies`/`chapterAnchors`/`chapterBodyIn`/`nextSteps`：写前核、原子落盘、接续三行 |
| `skills/story/scripts/core/story/document.mjs` | `fenceRanges`/`fencedLines`/`maskOf`/`parseChapter`/`sectionNames`/`sectionBody`/`tablesIn`/`matchSection`/`storySections`/`chapterSpan`/`subsectionSpan`/`CLOSING`/`SEPARATOR`/`norm`：唯一的围栏扫描与章节定位 |
| `skills/story/scripts/core/story/context.mjs` | `readRaw`/`readText`/`refuseIfFrozen`/`storyFrozen`：字节保真读取与冻结守卫 |
| `skills/story/phases/story-write.md` | 十章各自怎么组织、写一章的动作 |

#### F2.4.1 读者问题与章节职责

| 文件 | 承担 |
|---|---|
| `skills/story/contracts/story-chapters.json` | `chapters[].reader_questions`/必要结构/`heading_counters`/`note` |
| `skills/story/scripts/core/story/chapter-contract.mjs` | `chapterStructureProblems`/`requiredH3`/`requiredTables`：按位置指名缺什么 |
| `skills/story/phases/story-write.md` | 「五、十章各自怎么组织」十节 |

#### F2.4.2 图表与正文协作

| 文件 | 承担 |
|---|---|
| `skills/story/scripts/core/story/images.mjs` | `diagramsOf`/`diagramTopic`/`diagramsNotCarried`/`danglingFigures`/`carriedDiagramProblems`/`imageProblems` |
| `skills/story/scripts/core/story/document.mjs` | `hasDiagram`/`DIAGRAM_LANGS`/`FIGURE_PREFIX` |
| `skills/story/scripts/core/story/language.mjs` | `scanBrokenImages`/`IMAGE_HINTS`/`DANGLING_REF_PATTERNS`/`scanDanglingRefs` |

#### F2.4.3 验收与交付可操作

| 文件 | 承担 |
|---|---|
| `hooks/shared/contracts.mjs` | `readAcceptance`/`knowledgeCriteria`/`contractFiles`/`contractsPath`/`readContracts`/`resolveEntityRef`/`entityName`/`memberNames`/`asArray`/`ENTITY_KINDS`：验收与契约一次验证并分组 |
| `hooks/testing/post_check.mjs` | `referencedAcceptanceIds`：实机阶段引用的验收编号 |
| `skills/story/contracts/story-chapters.json` | 验收章与交付章的必要结构 |

### F2.5 契约查阅附录

| 文件 | 承担 |
|---|---|
| `skills/story/scripts/core/story/appendix.mjs` | `appendixProjection`/`projectAppendix`/`appendixChapter`/`appendixTables`/`appendixTableHeader`/`APPENDIX_FROM_SPEC`/`DROP_COLUMNS`/`specSection`/`specTerms`/`scopeList`/`scopeBoundaryRows`/`scopeRationale`/`pipeTables`/`isPlaceholderRow`/`specNotApplicable`/`knowledgeUseVerdicts`/`verdictSkeleton`/`DOMAIN_NA`/`materialSubsectionName`/`KNOWLEDGE_USE_SOURCE`：五节投影 |
| 同上 | `specGaps`/`appendixSpecGaps`/`appendixSourceProblems`/`appendixStructureProblems`/`appendixZoneProblems`/`zonesOnDisk`/`cut`/`firstDiff`：写前拦与读时核共用同一结论 |
| `skills/story/scripts/core/story/document.mjs` | `ZONE_BEGIN`/`ZONE_END`/`zoneBlock`/`zoneSpan`/`zoneHandEdited`/`projectionDigest`/`recordedDigest`/`DIGEST_IN_MARK`/`ProjectionConflict`：机器区标记与摘要口径 |
| `hooks/shared/knowledge-use/document.mjs` | `readUse`/`UseError`：附录 D/E 的真源读取 |
| `skills/story/templates/spec-sections.md` | §9 五小节的模板（投影的上游） |

### F2.6 标题引用与可读整理

| 文件 | 承担 |
|---|---|
| `skills/story/scripts/core/story/document.mjs` | `normalizeHeading`/`takeAuthorNumber`/`renumberStory`/`NUMBER_PREFIX`/`BARE_NUMBER_PREFIX`/`LETTER_PREFIX`/`FIGURE_PREFIX`/`pendingMark`/`pendingChapters`/`PENDING_MARK`/`PENDING_RE`/`EMPTY_SECTION_TEXT` |
| `skills/story/scripts/core/story-build.mjs` | `cmdNumber` |
| `skills/story/contracts/story-chapters.json` | `heading_counters`/`heading_counters_note`/`pending_mark_note` |

### F2.7 写后整篇核对

| 文件 | 承担 |
|---|---|
| `skills/story/scripts/core/story/check.mjs` | `cmdCheck`/`groupedProblems`：全局章序、H1、完成态；按类分组 |
| `skills/story/scripts/core/story/language.mjs` | `scanBannedTerms`/`scanLanguageRedline`/`scanLocalPaths`/`scanMaterialList`/`formatHits`/`narrativeLines`/`redlineScopes`/`EXEMPT_LINE_PATTERNS`/`moduleLayerIds`/`localPathRe`/`GENERIC_PATH_ALTS`/`SEARCH_PHRASE_RE`/`SOURCE_TAG_RE`/`DOC_COORDINATE_RE`/`CAMEL_CASE_RE`/`SNAKE_CASE_RE`/`INLINE_CODE_RE`/`AI_HEADING_TERMS`/`REDLINE_HINTS`/`FRAMEWORK_ARTIFACT_NAMES`/`constraintNames`/`bareFileNameRule`/`firstSegment`/`escapeRe`/`readConfig`：语言与路径作用域判据 |
| `skills/story/scripts/core/story/sources.mjs` | `sourceProblems`/`materialListProblems`/`materialListSkeleton`/`materialLinkTargets`/`redactMaterialLinks` |
| `skills/story/contracts/story-chapters.json` | `language_redline`/`id_shapes`/`sources`/`material_dirs`/`verdicts` |
| `skills/story/phases/story-write.md` | 「四、写后核对」三个动作 |

## F3 决策与评审回流

### F3.1 发现并解释判断

| 文件 | 承担 |
|---|---|
| `skills/story/scripts/core/story/review.mjs` | `DECISION_FIELDS`/`DECISION_SHAPE`/`decisionList`/`decisionsMissing`/`decisionProblems`/`requireStoryFirst`/`sectionNameOf`/`STATUS_CHAPTERS` |
| `skills/story/contracts/story-chapters.json` | `decision_categories`/`decision_categories_note` |
| `skills/story/phases/story-write.md` | 「决策登记」一节 |

### F3.2 生成评审件并保护人工区

| 文件 | 承担 |
|---|---|
| `skills/story/scripts/core/story/review.mjs` | `cmdBuild`/`renderReview`/`renderDocHeader`/`renderMachineZone`/`renderHumanZone`/`humanZoneStart`/`machineZoneOf`/`issueHandEdited`/`extractHumanZone`/`extractFreeformZone`/`renderFreeformSection`/`groupByCategory`/`issueMark`/`ISSUE_MARK`/`HUMAN_ZONE_MARK`/`FREEFORM_OPEN`/`FREEFORM_CLOSE`/`FREEFORM_CHAPTER`/`DOC_HINT`/`FREEFORM_HINT`/`reviewFormProblems`/`REVIEW_BANNED_LINES`/`redactReviewExemptZones` |
| `skills/story/scripts/core/story/document.mjs` | `projectionDigest`/`recordedDigest`/`ProjectionConflict`：与附录同一套摘要口径 |

### F3.3 归档与远程恢复

| 文件 | 承担 |
|---|---|
| `skills/story/scripts/adapters/story.js` | `cmdArchive`/`cmdRestore`/`systemWrite`/`systemRoot`/`writeIfAbsent`/`ts`/`emit`/`fail`/`log`/`USAGE`/`CMDS`/`cmd`/`ar`/`mcpToken`/`projectRootArg`/`argError`/`localAr`/`system`/`DEFAULT_SYSTEM_DIR`/`SYSTEM_DIR_ENV` |
| `skills/story/scripts/core/flow/lifecycle.py` | `cmd_archived`：归档态登记 |
| `skills/story/scripts/core/flow/state.py` | `STORY`/`REVIEW`：两份交付件的落点 |
| `skills/story/SKILL.md` | 「归档」「恢复」两节 |

### F3.4 获取并处置评审反馈

| 文件 | 承担 |
|---|---|
| `skills/story/scripts/adapters/review.js` | `fetchReview`/`FEEDBACK_FILE` |
| `skills/story/rules/review_reflow.md` | 逐项处置、处置台账、走 framework correction 闭环、归档后的边界 |
| `skills/story/SKILL.md` | 「检视」一节 |

## F4 知识应用与维护解耦

### F4.1 知识登记与读取

| 文件 | 承担 |
|---|---|
| `hooks/shared/knowledge.mjs` | `knowledgeFiles`/`activeKnowledge`/`entryById`/`selfCheck`/`KnowledgeError`/`fail`/`splitFrontmatter`/`frontmatterPairs`/`fmList`/`splitCells`/`markdownTable`/`pick`/`parseConstraintFile`/`parsePatternFile`/`parseIndexFile`/`parseFactFile`/`parseProbe`/`ENTRY_ID_RE`/`PROBE_COLUMN`/`PROBE_KINDS`/`KNOWLEDGE_KINDS`/`INDEX_KIND`/`MANIFEST_NAME`/`REVIEW_ACTION_MARK` |
| `manifest.yaml` | `provides.knowledge`：激活清单（归目标工程） |
| `knowledge/README.md` | 知识目录的定位说明（归目标工程） |

### F4.2 项目事实与部件画像

| 文件 | 承担 |
|---|---|
| `knowledge/facts/*.md` | 事实内容（归目标工程） |
| `hooks/shared/knowledge.mjs` | `parseFactFile` |
| `hooks/spec/author.mjs` | `knowledgeSection`：把事实送到作者面 |

### F4.3 规约适用与具体要求

| 文件 | 承担 |
|---|---|
| `hooks/shared/knowledge-use/document.mjs` | `readUse`/`usePath`/`manifestDigest`/`renderSkeleton`/`text`/`asList`/`requirements`/`fail`/`UseError`/`SCHEMA`/`USE_FILE`/`NO_CANDIDATE`：真源的定位、读取、规范化与骨架 |
| `hooks/shared/knowledge-use/validation.mjs` | `coverageProblems`/`contractNames`/`isEmptyReason`：判全了没有、编号在不在册、落点引不引得到 |
| `hooks/shared/knowledge-use/projection.mjs` | `renderZones`/`renderConstraints`/`applyZones`/`zoneProblems`/`zoneOf`/`zoneBlock`/`chapterSpan`/`cell`/`BEGIN`/`END`/`ZONES`：§10 投影与只读保护 |
| `hooks/shared/knowledge-use.mjs` | `main`/`cmdInit`/`parseArgs`：`init` 与 `render` 两条命令 |
| `knowledge/constraints/*.md` | 规约内容（归目标工程） |
| `rules/spec-rules.overlay.yaml` | `knowledge_spec_exit_substance`：判断本身是不是本需求的设计 |
| `hooks/spec/post_check.mjs` | `knowledgeExitProblems`：spec 侧的机械核 |

### F4.4 设计模式候选与选择

| 文件 | 承担 |
|---|---|
| `hooks/shared/knowledge-use/projection.mjs` | `renderPatterns`：§11 投影 |
| `hooks/shared/knowledge-use/validation.mjs` | 候选在册、不写 `chosen` 的校验 |
| `hooks/plan/post_check.mjs` | `specPatternHits`/`planPatternChoices`/`chapterAt`/`tableRows`/`findHeadings`/`DESIGN_HEADING_RE`/`DECISION_HEADING_RE`/`SECTIONS_DOC`/`FIX`：plan 选型与 spec 候选的交叉核 |
| `knowledge/design-patterns/*.md` | 模式内容（归目标工程） |
| `rules/spec-rules.overlay.yaml` | `knowledge_candidates_registered` |

### F4.5 Plan 知识设计与义务传递

| 文件 | 承担 |
|---|---|
| `hooks/shared/obligations.mjs` | `obligationsFromContracts`/`misplacedMust`/`patternRolesFromContracts`/`mustOf`/`arr`/`name`/`VERIFY_KINDS` |
| `hooks/plan/post_check.mjs` | `specHitIds` 等：义务与命中集合对账 |
| `skills/story/templates/plan-sections.md` | `must` 只能挂在哪五处、三个字段各写什么 |
| `rules/plan-rules.overlay.yaml` | `knowledge_obligation_substance`/`knowledge_facts_reuse`/`review_gate_acknowledged` |
| `hooks/plan/author.md` | plan 作者原则页 |

### F4.6 Coding 落实与可执行检查

| 文件 | 承担 |
|---|---|
| `hooks/coding/post_check.mjs` | `tailIdentifier`/`findIdentifier`/`AUTHOR_DOC`/`FIX` |
| `hooks/shared/probes.mjs` | `filesForEntity`/`runProbe`/`methodBody`/`blankComments`/`readOrNull` |
| `rules/coding-rules.overlay.yaml` | `knowledge_landing_in_code` |
| `hooks/coding/author.md` | coding 作者原则页 |

### F4.7 Review 知识复核

| 文件 | 承担 |
|---|---|
| `hooks/review/post_check.mjs` | `reviewTable`/`cellOf`/`SECTION_TITLE`/`VERDICTS` |
| `rules/review-rules.overlay.yaml` | `knowledge_obligation_reviewed` |
| `hooks/review/author.md` | review 作者原则页 |

### F4.8 UT 义务验证

| 文件 | 承担 |
|---|---|
| `hooks/ut/post_check.mjs` | UT 侧义务核 |
| `rules/ut-rules.overlay.yaml` | `knowledge_obligation_verified` |
| `hooks/ut/author.md` | ut 作者原则页 |

### F4.9 实机及其他验证分派

| 文件 | 承担 |
|---|---|
| `hooks/testing/post_check.mjs` | `referencedAcceptanceIds` |
| `rules/testing-rules.overlay.yaml` | `knowledge_obligation_verified`（实机侧） |
| `hooks/testing/author.md` | testing 作者原则页 |

## F5 推进恢复与交付保障

### F5.1 阶段作者任务送达

| 文件 | 承担 |
|---|---|
| `hooks/<phase>/author.md`（六份） | 各阶段动笔前的原则页 |
| `hooks/spec/author.mjs` | `taskPackage`/`main`/`USAGE`：spec 的动态任务包 |
| `hooks/shared/gate.mjs` | `authorDoc`/`guard`/`gate`：把原则页接进门禁报错 |

### F5.2 进度与中断恢复

| 文件 | 承担 |
|---|---|
| `skills/story/scripts/core/flow/lifecycle.py` | `cmd_status` |
| `skills/story/scripts/core/flow/routing.py` | `next_step`/`scope_step`/`spec_stage_step`/`sidecar_shape`/`frozen_tail`/`frozen_inbox_note`/`material_gate_state`/`settled_this_round`/`pending_chapters`/`SPEC_STAGE_AUTHORIZATION`/`SPEC_STAGE_ORDER` |
| `skills/story/scripts/core/flow/state.py` | `load`/`save`/`require`/`after_complete`/`SCHEMA`/`CONTRACT` |
| `skills/story/scripts/core/flow/client.mjs` | JS 侧同一口径 |
| `skills/story/scripts/core/story_flow.py` | `main`：八条命令的解析与分派 |

### F5.3 确定性校验与登记

| 文件 | 承担 |
|---|---|
| `skills/story/scripts/core/flow/lifecycle.py` | `cmd_story`：project → number → build → check → 记 |
| `skills/story/scripts/core/flow/state.py` | `CORE_DIR`（定位 `story-build.mjs`）/`STORY_SRC_FROZEN`/`ledger_digest` |
| `skills/story/scripts/core/story/context.mjs` | `STORY_SRC_LEDGERS`/`requireLedgers`/`ledgerDigestProblems`/`strayFileProblems`/`digestOf`/`storyFrozen`/`refuseIfFrozen` |
| `skills/story/scripts/core/flow/check.mjs` | `flowProblems`/`isStoryFeature`/`storyProduced`/`FLOW_FILE`/`FLOW_SCHEMA`/`FLOW_STATES`/`FLOW_FIX`/`reached`/`readFlow`：spec 阶段门禁 |
| `hooks/spec/post_check.mjs` | `SPEC_EXT_SECTIONS`/`sectionBody`/`sectionFilled`/`sectionRange`/`findHeading`/`isSeparatorRow`/`rowCells`/`hasTemplatePlaceholder`/`scanDocCoords`/`scanNumericSources`/`strayProse`/`acceptanceCoverage`/`DOC_COORD_RE`/`NUMERIC_RE`/`SOURCE_TAG_RE`/`SECTIONS_DOC`/`EVIDENCE_DOC` |

### F5.4 返修与错误恢复

| 文件 | 承担 |
|---|---|
| `skills/story/scripts/core/flow/rounds.py` | `cmd_reopen` |
| `skills/story/scripts/core/story/drafts.mjs` | 草稿登记后不删，返修有可改的东西 |
| `skills/story/phases/spec.md` | 「verifier 报了阻断问题怎么办」 |

### F5.5 独立审查与 Framework 闭环

| 文件 | 承担 |
|---|---|
| `hooks/shared/reader-review-task.mjs` | `readerReviewTask`/`imageRows`/`reviewMethod`/`longestFence`/`contractOf`/`readOrNull`：全文一次给全 + 依据位置 |
| `rules/spec-rules.overlay.yaml` | `story_reader_review`：审查方法与输出契约的唯一落点 |
| `hooks/shared/verifier-report.mjs` | `storyReviewProblems`/`summaryRow`/`readerReviewDetails`/`checksIn`/`yamlBlocks`/`reportLocation`/`STORY_REVIEW_ID`/`DETAIL_KEYS`/`SUMMARY_COLUMNS`/`INVALID_EVIDENCE`/`PER_UNIT_TABLE_RE` |
| `hooks/shared/pre_verifier.mjs` | `overlayCheckIds`/`KNOWLEDGE_CHECK_PREFIX`/`READER_REVIEW_ID`/`SOURCE_OF_TRUTH` |
| `skills/story/scripts/core/story-build.mjs` | `cmdReviewTask`：正式的审查任务命令 |
| `skills/story/phases/spec.md` | 第 ⑤ 步：什么时候派、只派一次 |

### F5.6 交付选择与能力披露

| 文件 | 承担 |
|---|---|
| `skills/story/scripts/core/story/delivery.mjs` | `deliveryProblems`/`deliveryNextSteps`/`receiptRunner` |
| `skills/story/scripts/core/story-build.mjs` | `check --deliver` 的参数互斥与分派 |
| `skills/story/SKILL.md` | 「归档」三步里的交付门 |
| `skills/story/phases/spec.md` | 第 ⑥ 步 |

### F5.7 必要运行证据与诊断

| 文件 | 承担 |
|---|---|
| `hooks/shared/evidence.mjs` | `writePostCheckEvidence`/`STATUS`/`EVIDENCE_FILE`/`sha256` |
| `hooks/shared/gate.mjs` | `guard`/`gate`：六份 post_check 共用的入口守卫与报错拼装 |
| `skills/story/reference/evidence-rules.md` | spec 取证规则（作者面） |

## F6 跨仓安装升级

### F6.1 首次接入与画像

| 文件 | 承担 |
|---|---|
| `skills/story-adaptation/scripts/adapt-scan.mjs` | `skeletonKnowledge`/`knowledgeBlock`/`freshIdentity`/`composeManifest`/`STATE`/`findRoot`/`config`/`extDir`/`featuresDir` |
| `skills/story-adaptation/SKILL.md` | 四件事与两种来源 |

### F6.2 机制升级与文件退出

| 文件 | 承担 |
|---|---|
| `skills/story-adaptation/scripts/adapt-scan.mjs` | `CORE`/`SCRIPTS_DIR`/`walk`/`coveredFiles`/`inWriteFace`/`dirtyPaths`/`git`/`isRepo`/`read`/`rel`/`sha`/`TARGET`/`PKG`/`PDIR`/`TDIR`/`SAME_TREE`/`mode`/`opt`/`argv`/`die`/`MODES` |

### F6.3 业务对接所有权

| 文件 | 承担 |
|---|---|
| `skills/story-adaptation/scripts/adapt-scan.mjs` | `ADAPTERS`/`WITH_ADAPTERS`/`MOCK_ADAPTER_PACKAGE`/`PKG_NAME`/`pkgManifest`/`PKG_MANIFEST_TEXT`/`tgtManifest`/`manifestValue` |
| `skills/story/scripts/README.md` | 三个对接件的输出合同（目标实现自己那份的唯一依据） |
| `skills/story-adaptation/SKILL.md` | 「两种来源」表 |

### F6.4 安装结果与配置边界

| 文件 | 承担 |
|---|---|
| `skills/story-adaptation/scripts/adapt-scan.mjs` | `TARGET_OWNED_KEYS`/`versionNotes`/`withVersionNotes`/`KNOWLEDGE`/`bridgesOf`/`BRIDGES`/`missingGitignoreLines`/`EXT_BEGIN`/`EXT_END`/`SECTION`/`ENTRIES`/`stripMarks`/`replaceZone`/`extensionSectionEnd`/`bad` |
| `manifest.yaml` | `schema_version`/`name`/`version`/`description`/`provides`：机制登记归包，身份与知识归目标 |
| `skills/story/AGENTS.section.md` | 宿主入口的扩展段 |

## F7 共同支撑

### F7.1 配置路径与数据解析

| 文件 | 承担 |
|---|---|
| `hooks/shared/paths.mjs` | `readConfig`/`extensionRoot`/`featuresDir`/`featureRoot`/`relDisplay`/`readTextOrNull`/`readJsonOrNull`/`lines` |
| `hooks/shared/yaml-lite.mjs` | `parseYaml`/`scalar`/`blockScalar`/`inlineSeq`/`parseBlock`/`parseSeqItemMap`/`indentOf`/`isBlank`/`isSeqAt`/`nextMeaningfulIndent`/`KV_RE`/`ITEM_RE`/`BLOCK_RE` |
| `skills/story/scripts/core/materials/importer.py` | `features_dir`/`DEFAULT_PROJECT_ROOT`：Python 侧两个入口共用的一处 |
| `skills/story/scripts/core/flow/state.py` | `SKILL_ROOT`/`CORE_DIR`：Skill 内资源的一条定位规则 |

### F7.2 材料与输出操作支撑

| 文件 | 承担 |
|---|---|
| `skills/story/scripts/core/story/context.mjs` | `fail`/`readText`/`readRaw`/`readJson`/`writeJson`/`activeKnowledgeEntries`/`specText` |
| `skills/story/scripts/core/story/sources.mjs` | `relFromFeature`/`relFromStory`/`joinPosix`/`basename`/`readManifest` |
| `skills/story/scripts/core/flow/state.py` | `log`/`now`/`load`/`save`/`require`/`FlowError` |
| `skills/story/scripts/core/materials/importer.py` | `log`/`ImportError_` |
| `skills/story/scripts/core/materials/registry.py` | `MaterialError`/`file_digest` |

---

## 本轮退出项（唯一记录处）

退出分两类记，不混在一起：**结构搬迁**是同一份实现换了位置（能力不变），
**业务能力变化**才是功能层面的增减。交付准备件不再另存一份清单，以本节为准。

### A 结构搬迁（能力不变，旧路径退出）

| 旧位置 | 新唯一落点 | 消费者已切 | 旧位置 |
|---|---|---|---|
| `core/story_flow.py` 的全部实现（1123 行） | `core/flow/{state,inputs,routing,decisions,rounds,submission,lifecycle}.py` | 入口 + 测试直接 import 所属模块 | 只剩 68 行入口 |
| `core/materials.py` | `core/materials/registry.py` | JS/Python/测试全切 | 文件已删 |
| `core/import_sources.py` 的实现主体 | `core/materials/importer.py`（导入正文成 `cmd_import`） | 入口 + 测试 | 入口只剩 91 行 |
| `core/flow-check.mjs` | `core/flow/check.mjs` | 3 个 hooks + 2 个 story 模块 + 2 份测试 + 失效形态脚本 | 文件已删 |
| `hooks/shared/knowledge-use.mjs` 的库 API | `knowledge-use/{document,validation,projection}.mjs` | plan/spec 两个 post_check、`story/appendix.mjs`、3 份测试 | 入口导出为空，**不转发** |
| `core/lint-rules.mjs`（Q7） | `core/story/language.mjs` | 作者包、spec post_check、check/chapter/sources、失效形态脚本 | 文件已删；合同里两处指向已改 |
| `core/headings.mjs`（Q5） | `core/story/document.mjs` | 全部 story 模块 | 文件已删；合同里一处指向已改 |
| `core/review-render.mjs`（Q6） | `core/story/review.mjs` | `story-build` 入口 | 文件已删，无转发壳 |

### B 业务能力变化（有增有减，各有承接者）

| 退出的 | 承接的 |
|---|---|
| `copyedit` 的**自证载体**：`COPYEDIT_ROWS`、check ⑫d、台账冻结项、作者七行自证（Q5） | 整稿职责仍在：跨章与全篇核对 `story/check.mjs`，写前核 `chapter.mjs::chapterProblems`（单章与全篇同一实现），整稿方法在 `phases/story-write.md` 与任务包 |
| `AR/assets/` 归档副本区「未登记也按字节认」的特权，含合同字段 `story_image_dir` 与 `sameBytes`（Q7） | 收敛到**登记身份规则**：身份按 `materials.json` 的内容哈希与登记路径判；已登记的 assets 路径照样合法 |
| `proseBlocks`（段数配额）、`carryableBlock`/`diagramBody`/`DIAGRAM_FENCE`（围栏副本）（Q7） | 源图给**坐标**（`images.mjs::diagramsOf` 的 `at:{from,to}`），不复制围栏 |
| `MATERIALS_STALE_STEP`（只认某个 `next` 字面值的代理）（Q1） | `material_state` 的事实字段（`pending`/`changed`），消费者按事实判 |
| `story-build.staleMaterials` 的解释器循环、`author.flowStatus` 的同套胶水（Q1） | `core/flow/client.mjs`：一份带形状校验与五类失败的共用客户端 |
| 审查方法在 fragment 与 overlay 各存一份（第一包 R1） | `rules/spec-rules.overlay.yaml::story_reader_review` 一处 |
| 参与方**人数**门槛（第一包 R1） | 「协作次序按实际关系判，不按参与方个数」 |
| manifest 里的版本演进注释（用户 2026-09-13） | `test/story/release/` 的发布说明；`version:` 上面那一段按 adapt 的所有权规则归目标 |

### C 新增能力（本轮，落在既有叶子里）

| 新增 | 落在 | 替代了什么 |
|---|---|---|
| 上游原件按轮次留存后**进入材料清单与来源检查** | F1.7 | 不替代任何一项，是增量 |
| 作者任务里**一张图一个任务单元**（别名、代表路径、形状缺口） | F2.3 / F1.3 | 替代「整份清单一段话」的旧渲染 |
| 审查任务带**当前 Story 全文一次** | F5.5 | 替代只给标题与要点的旧任务 |
| 交付门按 **`reviewVerdict` 实际结论**放行 | F5.6 | 替代只核报告形态的旧判据 |

### D 有意保留的同名物

`story/drafts.mjs::chapterDraft` 与 story-build 里退场的那个同名不同物（前者是章草稿渲染，
后者是已删的入口函数）。全量搜旧名字时只剩这一处命中。
