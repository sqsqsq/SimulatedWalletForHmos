# 实现 → 功能 逐内容归属（第二包候选稿）

> **候选状态**与**基线**同 [FEATURES.md](FEATURES.md)：`77314387`，2026-09-13，按符号定位。
> 正向（功能 → 实现）在 [FEATURE-MAP.md](FEATURE-MAP.md)。
>
> **覆盖口径**：`doc/extensions/` 下每个文件的每个顶层内容单元都要在这里出现一次以上——
> 代码是顶层函数、类与常量；提示词与规则页是二级标题（其下的三级标题随父节，另有归属才单列）；
> 合同与配置是顶层键。可多归属，不可遗漏。
>
> 路径相对 `doc/extensions/`。`__pycache__` 与 `node_modules` 不是交付内容，不登记。

## hooks/ —— 六阶段钩子与共用件

### `hooks/coding/author.md` — coding 作者原则页

| 功能 | 内容单元 |
|---|---|
| F5.1 · F4.6 | 「一、读哪几个文件」·「二、产出形态」·「三、跑哪条命令」·「四、门禁会拦什么」 |

### `hooks/coding/post_check.mjs`

| 功能 | 内容单元 |
|---|---|
| F4.6 | `tailIdentifier` · `findIdentifier` · `AUTHOR_DOC` · `FIX` |

### `hooks/plan/author.md` — plan 作者原则页

| 功能 | 内容单元 |
|---|---|
| F5.1 · F4.5 | 「一、读哪几个文件」·「二、产出形态」·「三、跑哪条命令」·「四、门禁会拦什么」 |

### `hooks/plan/post_check.mjs`

| 功能 | 内容单元 |
|---|---|
| F4.5 | `specHitIds` · `SECTIONS_DOC` · `FIX` |
| F4.4 | `specPatternHits` · `planPatternChoices` · `DESIGN_HEADING_RE` · `DECISION_HEADING_RE` |
| F7.1 | `findHeadings` · `tableRows` · `chapterAt`（该文件内的 Markdown 定位支撑） |

### `hooks/review/author.md` — review 作者原则页

| 功能 | 内容单元 |
|---|---|
| F5.1 · F4.7 | 四节同上 |

### `hooks/review/post_check.mjs`

| 功能 | 内容单元 |
|---|---|
| F4.7 | `reviewTable` · `cellOf` · `SECTION_TITLE` · `VERDICTS` |

### `hooks/testing/author.md` / `hooks/testing/post_check.mjs`

| 功能 | 内容单元 |
|---|---|
| F5.1 · F4.9 | author.md 四节 |
| F4.9 · F2.4.3 | `referencedAcceptanceIds` |

### `hooks/ut/author.md` / `hooks/ut/post_check.mjs`

| 功能 | 内容单元 |
|---|---|
| F5.1 · F4.8 | author.md 四节 |
| F4.8 · F2.4.3 | `coveredAcceptanceIds` |

### `hooks/spec/author.md` — spec 作者原则页

| 功能 | 内容单元 |
|---|---|
| F5.1 | 「先分清你在哪一组」·「跑哪条命令」 |
| F4.3 | 「知识判断怎么填」 |
| F2.4 | 「写字的三条」 |

### `hooks/spec/author.mjs` — spec 本次任务包

| 功能 | 内容单元 |
|---|---|
| F2.1 | `taskPackage` · `positionSection` · `docText` · `SELF` · `SKILL_ROOT` · `USAGE` · `main` |
| F2.3 | `knowledgeSection` · `decisionSection` · `vocabularySection` · `acceptanceKeys` · `acceptancePath` |
| F2.3 · F1.3 | `imageSection`（一图一任务） |
| F2.3 · F1.7 | `originalArSection`（留存的上游原件） |
| F2.3 · F2.4.2 | `diagramSection`（源图身份、主题、路径与行区间） |

### `hooks/spec/post_check.mjs` — spec 阶段扩展门禁

| 功能 | 内容单元 |
|---|---|
| F5.3 | `SPEC_EXT_SECTIONS` · `sectionBody` · `sectionFilled` · `sectionRange` · `findHeading` · `isSeparatorRow` · `rowCells` · `hasTemplatePlaceholder` · `SECTIONS_DOC` · `EVIDENCE_DOC` |
| F5.3 · F5.7 | `scanDocCoords` · `scanNumericSources` · `strayProse` · `DOC_COORD_RE` · `NUMERIC_RE` · `SOURCE_TAG_RE` |
| F4.3 | `knowledgeExitProblems` |
| F2.4.3 | `acceptanceCoverage` |

### `hooks/shared/contracts.mjs`

| 功能 | 内容单元 |
|---|---|
| F2.4.3 | `readAcceptance` · `contractFiles` · `contractsPath` · `readContracts` |
| F4.5 | `knowledgeCriteria` · `resolveEntityRef` · `entityName` · `memberNames` · `ENTITY_KINDS` |
| F7.1 | `asArray` |

### `hooks/shared/evidence.mjs`

| 功能 | 内容单元 |
|---|---|
| F5.7 | `writePostCheckEvidence` · `STATUS` · `EVIDENCE_FILE` · `sha256` |

### `hooks/shared/gate.mjs`

| 功能 | 内容单元 |
|---|---|
| F5.7 | `guard` · `gate` |
| F5.1 | `authorDoc` |

### `hooks/shared/knowledge.mjs`

| 功能 | 内容单元 |
|---|---|
| F4.1 | `knowledgeFiles` · `activeKnowledge` · `entryById` · `selfCheck` · `KnowledgeError` · `fail` · `parseIndexFile` · `KNOWLEDGE_KINDS` · `INDEX_KIND` · `MANIFEST_NAME` · `ENTRY_ID_RE` |
| F4.3 | `parseConstraintFile` · `REVIEW_ACTION_MARK` |
| F4.4 | `parsePatternFile` |
| F4.2 | `parseFactFile` |
| F4.6 | `parseProbe` · `PROBE_COLUMN` · `PROBE_KINDS` |
| F7.1 | `splitFrontmatter` · `frontmatterPairs` · `fmList` · `splitCells` · `markdownTable` · `pick` |

### `hooks/shared/knowledge-use.mjs` — 两条命令的入口

| 功能 | 内容单元 |
|---|---|
| F4.3 | `main` · `cmdInit` · `parseArgs` |

### `hooks/shared/knowledge-use/document.mjs`

| 功能 | 内容单元 |
|---|---|
| F4.3 | `readUse` · `usePath` · `manifestDigest` · `renderSkeleton` · `UseError` · `fail` · `SCHEMA` · `USE_FILE` |
| F4.3 · F4.4 | `text` · `asList` · `requirements`（验证与渲染共用的规范化） · `NO_CANDIDATE` |

### `hooks/shared/knowledge-use/validation.mjs`

| 功能 | 内容单元 |
|---|---|
| F4.3 | `coverageProblems` · `isEmptyReason` · `contractNames` |
| F4.4 | `coverageProblems` 里的候选在册与「不写 chosen」两条 |

### `hooks/shared/knowledge-use/projection.mjs`

| 功能 | 内容单元 |
|---|---|
| F4.3 | `renderZones` · `renderConstraints` · `applyZones` · `zoneProblems` · `zoneOf` · `zoneBlock` · `chapterSpan` · `cell` · `BEGIN` · `END` · `ZONES` |
| F4.4 | `renderPatterns` |

### `hooks/shared/obligations.mjs`

| 功能 | 内容单元 |
|---|---|
| F4.5 | `obligationsFromContracts` · `misplacedMust` · `patternRolesFromContracts` · `mustOf` · `VERIFY_KINDS` · `arr` · `name` |

### `hooks/shared/paths.mjs`

| 功能 | 内容单元 |
|---|---|
| F7.1 | `readConfig` · `extensionRoot` · `featuresDir` · `featureRoot` · `relDisplay` · `readTextOrNull` · `readJsonOrNull` · `lines` |

### `hooks/shared/pre_verifier.mjs`

| 功能 | 内容单元 |
|---|---|
| F5.5 | `overlayCheckIds` · `KNOWLEDGE_CHECK_PREFIX` · `READER_REVIEW_ID` · `SOURCE_OF_TRUTH` |

### `hooks/shared/probes.mjs`

| 功能 | 内容单元 |
|---|---|
| F4.6 | `runProbe` · `filesForEntity` · `methodBody` · `blankComments` · `readOrNull` |

### `hooks/shared/reader-review-task.mjs`

| 功能 | 内容单元 |
|---|---|
| F5.5 | `readerReviewTask` · `reviewMethod` · `longestFence` · `contractOf` · `readOrNull` |
| F5.5 · F1.3 | `imageRows`（图片清单，形状不对报缺口） |

### `hooks/shared/verifier-report.mjs`

| 功能 | 内容单元 |
|---|---|
| F5.5 | `storyReviewProblems` · `summaryRow` · `readerReviewDetails` · `checksIn` · `yamlBlocks` · `reportLocation` · `STORY_REVIEW_ID` · `DETAIL_KEYS` · `SUMMARY_COLUMNS` · `INVALID_EVIDENCE` · `PER_UNIT_TABLE_RE` |
| F5.6 | `storyReviewProblems` 归一化出的 `reviewVerdict`（交付门据它放行） |

### `hooks/shared/yaml-lite.mjs`

| 功能 | 内容单元 |
|---|---|
| F7.1 | `parseYaml` · `scalar` · `blockScalar` · `inlineSeq` · `parseBlock` · `parseSeqItemMap` · `indentOf` · `isBlank` · `isSeqAt` · `nextMeaningfulIndent` · `KV_RE` · `ITEM_RE` · `BLOCK_RE` |

## rules/ —— 阶段规则 overlay（语义判据，AI verifier 消费）

| 文件 | 功能 | 内容单元 |
|---|---|---|
| `rules/spec-rules.overlay.yaml` | F4.3 | `knowledge_spec_exit_substance` |
| 同上 | F4.4 | `knowledge_candidates_registered` |
| 同上 | F5.3 | `spec_ext_conclusion_validity` · `upstream_inputs_coverage` · `split_boundary_consistency` |
| 同上 | F5.5 | `story_reader_review`（审查方法与输出契约的唯一落点） |
| 同上 | F5.1 | `phase_input_snippets_extra` · `phase` · `version` |
| `rules/plan-rules.overlay.yaml` | F4.5 | `knowledge_obligation_substance` · `knowledge_facts_reuse` · `review_gate_acknowledged` · `phase` · `version` · `phase_input_snippets_extra` · `exploration_thresholds` |
| `rules/coding-rules.overlay.yaml` | F4.6 | `knowledge_landing_in_code` · `phase` · `version` · `phase_input_snippets_extra` · `exploration_thresholds` |
| `rules/review-rules.overlay.yaml` | F4.7 | `knowledge_obligation_reviewed` · `phase` · `version` · `phase_input_snippets_extra` · `exploration_thresholds` |
| `rules/ut-rules.overlay.yaml` | F4.8 | `knowledge_obligation_verified` · `phase` · `version` · `phase_input_snippets_extra` · `exploration_thresholds` |
| `rules/testing-rules.overlay.yaml` | F4.9 | `knowledge_obligation_verified` · `phase` · `version` |

`spec-rules.overlay.yaml` 的 `exploration_thresholds` 归 F5.1（阶段输入门槛）。

## manifest.yaml

| 功能 | 内容单元 |
|---|---|
| F6.4 | `schema_version` · `version`（归包） |
| F6.4 · F6.1 | `name` · `description`（归目标，首次按目标生成） |
| F4.1 · F6.4 | `provides`（机制登记归包，`provides.knowledge` 归目标） |

## knowledge/ —— 三类知识（内容归目标工程，按文件与内容类别登记功能和消费者）

| 文件 | 功能 | 说明 |
|---|---|---|
| `knowledge/README.md` | F4.1 | 知识目录定位 |
| `knowledge/facts/README.md` · `facts/component-profile.md` · `facts/codebase-facts.md`（8 节取证事实 + 标题节） | F4.2 | 部件画像与工程取证事实；被 `parseFactFile` 读 |
| `knowledge/constraints/README.md` 及 `compatibility-checklist` · `deliverables` · `dfx-baseline` · `env-exceptions` · `observability` · `resource-usage` · `security-privacy` · `ux-consistency` 八份（各自的条目表与处置节） | F4.3 | 规约条目；被 `parseConstraintFile` 读 |
| `knowledge/design-patterns/README.md`（适用单元 · 模式清单 · 候选登记规则 · 多模式组合） | F4.4 | 候选在册的真源 |
| `knowledge/design-patterns/decision-tree.md` · `page-interaction.md`（各 13 节：上篇选型 1–3.1、下篇落地 4–9） | F4.4（上篇）· F4.6/F4.7（下篇） | 模式正文；被 `parsePatternFile` 读 |

## skills/story/ —— 需求流程 Skill

### `skills/story/SKILL.md`

| 功能 | 内容单元 |
|---|---|
| F1.1 | 「初始化」 |
| F1.6 | 「交互关卡语义」·「推进契约」下的「停等点：只有两处」「既有确认点」 |
| F5.2 | 「链条」·「各步的规则在哪」·「产物定位」 |
| F5.3 | 「成文到闭环的衔接链」 |
| F5.4 | 「失败出口（不是确认点）」 |
| F5.6 · F3.3 | 「归档」 |
| F3.3 | 「恢复」 |
| F3.4 | 「检视」 |
| F6.3 | 「需求系统 Token」 |
| F5.1 | 「授权分两层」·「停等消息怎么写」 |

### `skills/story/AGENTS.section.md`

| 功能 | 内容单元 |
|---|---|
| F6.4 | 宿主入口的扩展段全文（由 adapt 写进目标的 CLAUDE.md 标记区） |

### `skills/story/phases/spec.md`

| 功能 | 内容单元 |
|---|---|
| F2.1 | 「一、上游输入必读」 |
| F2.2 · F2.4 | 「二、本阶段产出三份文档」与「阶段内顺序」①②②b |
| F5.3 | ④ 跑 harness |
| F5.5 | ⑤ 派 verifier（只一次、在最后） |
| F5.6 | ⑥ check-receipt → 交付门 → archive |
| F5.4 | 「verifier 报了阻断问题怎么办」 |
| F2.5 | 「三、§9 技术契约怎么写」 |
| F5.2 | 「四、闭环后的下一步」 |

### `skills/story/phases/story-write.md`

| 功能 | 内容单元 |
|---|---|
| F2.4.1 | 「一、写给这样的读者」·「形式按内容的关系选」·「五、十章各自怎么组织」下十节（背景/术语/范围/业务方案/业务流程/功能说明/异常与恢复/验收/交付与上线/附录） |
| F2.4 | 「二、动笔前：先有整篇理解」·「三、写一章」 |
| F3.1 | 「决策登记」 |
| F2.7 | 「四、写后核对：十章齐了做一次」·「交回前自检（两条，只有你看）」 |
| F5.6 | 「六、归档件自包含与交回前」 |

### `skills/story/reference/evidence-rules.md`

| 功能 | 内容单元 |
|---|---|
| F5.7 | 「1. 核心公式」·「2. 信息源总表」（变更意图 / 代码库现状）·「4. 结论写法」（4.1/4.2/4.3） |
| F2.5 · F5.3 | 「3. 各节取证」（端云接口 / 数据存储 / 配置项 / 埋点 / 依赖变更） |

### `skills/story/rules/inbox_import.md`

| 功能 | 内容单元 |
|---|---|
| F1.2 | 「材料怎么放」·「归类：这份内容将来被哪一章按哪个源读取」·「落盘：先写判断，再跑脚本」 |
| F1.3 | 「内嵌图里的界面设计图」 |

### `skills/story/rules/init_analysis.md`

| 功能 | 内容单元 |
|---|---|
| F1.5 | 「0. 分两段做」·「1. init-analysis.md」下五节（需求概览 / 本部件视角 / 本 AR 定位 / 待实现功能清单 / 材料现状与范围定法） |
| F1.6 | 「2. story-flow.json — 流程契约」·「侧车文件」·「四条纪律」 |

### `skills/story/rules/scope_gate.md`

| 功能 | 内容单元 |
|---|---|
| F1.6 | 「三级，每级只问一件事」·「第一级：材料」（含「人回答之后」「导入之后什么时候再停」）·「第二级：范围定法选项集」（含「人提出自己的拆分诉求时」）·「第三级：本 AR 承载哪一份」·「用户明说『别逐个问』时，这两级照停」 |

### `skills/story/rules/ar_design_init.md`

| 功能 | 内容单元 |
|---|---|
| F1.7 | 「1. 两把裁剪标尺」·「2. 提取原则」·「3. 生成规则（五段结构）」下的五段模板（1 简介含 1.1/1.2/1.3、2 需求分析含 2.1/2.2、3 SE 方案摘要含 3.1/3.2、4 上游索引、5 上游已声明线索）·「4. 不做的事」 |

### `skills/story/rules/review_reflow.md`

| 功能 | 内容单元 |
|---|---|
| F3.4 | 「1. 逐项处置」·「2. 处置台账」·「3. spec 改动走 framework correction 闭环」·「4. 归档后的边界」（含「回传意见写到哪」）·「5. 已知限制」·「已经开工的 plan 怎么办」 |

### `skills/story/templates/inbox-readme.md`

| 功能 | 内容单元 |
|---|---|
| F1.1 · F1.2 | 「放什么」·「几条约定」（随 `cmd_init` 落盘） |

### `skills/story/templates/spec-sections.md`

| 功能 | 内容单元 |
|---|---|
| F5.3 · F2.5 | 「9. 技术契约」及 9.1–9.5 五小节 |
| F4.3 | 「10. 规约约束要求」 |
| F4.4 | 「11. 设计模式候选登记」 |

### `skills/story/templates/plan-sections.md`

| 功能 | 内容单元 |
|---|---|
| F4.5 | 「知识决策（设计输入）」下三节（设计模式选型 / 规约义务 / 项目知识影响）·「contracts.yaml：义务挂在实体上」下三节（`must` 只能挂在这五处 / 三个字段各写什么 / 有落点 vs 没落点） |

### `skills/story/contracts/story-chapters.json`

| 功能 | 内容单元 |
|---|---|
| F2.4.1 | `chapters` · `structure_note` · `note` |
| F2.2 | `skeleton_note` |
| F2.7 | `language_redline` · `id_shapes` · `verdicts` |
| F2.6 | `heading_counters` · `heading_counters_note` · `pending_mark` · `pending_mark_note` |
| F1.6 | `gates` · `gates_note` |
| F3.1 | `decision_categories` · `decision_categories_note` |
| F1.4 · F2.7 | `sources` · `sources_note` · `material_dirs` · `material_dirs_note` |
| F6.4 | `version` |

### `skills/story/scripts/README.md`

| 功能 | 内容单元 |
|---|---|
| F6.3 | 「`scripts/` 的两层：谁写的，谁维护」·「`adapters/` 里那三个的输出合同」·「换实现时要守住的两件」 |

### `skills/story/scripts/adapters/story.js`（目标仓自备；包内为替身）

| 功能 | 内容单元 |
|---|---|
| F1.1 | `cmdInit` · `readTicket` · `ticketText` · `ticketTitle` · `writeDetail` |
| F3.3 | `cmdArchive` · `cmdRestore` · `systemWrite` · `systemRoot` · `writeIfAbsent` · `DEFAULT_SYSTEM_DIR` · `SYSTEM_DIR_ENV` · `system` |
| F3.4 | `cmdReview` |
| F6.3 | `cmdHelp` · `USAGE` · `CMDS` · `cmd` · `ar` · `mcpToken` · `projectRootArg` · `argError` · `log` · `emit` · `fail` · `ts` |
| F7.1 | `featuresDir` · `projectRoot` · `featureRoot` · `localAr` · `fs` · `path` |

### `skills/story/scripts/adapters/review.js`

| 功能 | 内容单元 |
|---|---|
| F3.4 | `fetchReview` · `FEEDBACK_FILE` |
| F7.1 | `fs` · `path` |

### `skills/story/scripts/adapters/token.js`

| 功能 | 内容单元 |
|---|---|
| F6.3 · F1.1 | 整份（无顶层符号）：取 token，stdout 即 token 本身 |

### `skills/story/scripts/core/story_flow.py` — 流程 CLI 入口

| 功能 | 内容单元 |
|---|---|
| F5.2 | `main`（八条命令的参数解析、分派与顶层 JSON 输出） |

### `skills/story/scripts/core/import_sources.py` — 导入 CLI 入口

| 功能 | 内容单元 |
|---|---|
| F1.2 · F1.3 | `main`（四种模式的分派与输出） |

### `skills/story/scripts/core/flow/__init__.py` 与 `skills/story/scripts/core/materials/__init__.py`

| 功能 | 内容单元 |
|---|---|
| F7.2 | 空包标识（只有一行说明，不转发、不导出） |

### `skills/story/scripts/core/flow/state.py`

| 功能 | 内容单元 |
|---|---|
| F7.1 | `SKILL_ROOT` · `CORE_DIR` |
| F5.2 | `SCHEMA` · `CONTRACT` · `load` · `save` · `require` · `after_complete` |
| F1.5 | `ANALYSIS` · `SCOPE_SOURCES` |
| F1.6 | `GATES` · `ACTORS` · `CARRY_ALL` · `STORY_CONTRACT` · `round_gates` · `last_gate` |
| F1.7 | `DESIGN` · `DESIGN_DRAFT` · `AR_SOURCES` · `S4_STEPS` |
| F5.3 | `STORY_SRC_FROZEN` · `ledger_digest` |
| F3.3 | `STORY` · `REVIEW` |
| F7.2 | `FlowError` · `log` · `now` |

### `skills/story/scripts/core/flow/inputs.py`

| 功能 | 内容单元 |
|---|---|
| F1.5 | `read_sidecar` · `consume_sidecar` · `read_positioning` · `read_scope_options` · `POSITIONING` · `POSITIONING_FIELDS` · `SCOPE_OPTIONS` |
| F1.6 | `material_options` · `_MATERIAL_OPTIONS` · `MATERIAL_CHOICES` · `MATERIAL_REQUEST_KEYS` · `chosen_dimension` · `split_carrier_options` · `sidecar_gate` · `read_gate_options` · `read_split_parts` · `GATE_OPTIONS` · `SPLIT_PARTS` |
| F1.1 | `cmd_init` · `read_ids` |
| F1.1 · F1.7 | `ar_design_skeleton`（建骨架与判空骨架同一函数） |

### `skills/story/scripts/core/flow/routing.py`

| 功能 | 内容单元 |
|---|---|
| F1.4 | `live_materials` · `material_state` · `pending_import_step` |
| F5.2 | `next_step` · `scope_step` · `spec_stage_step` · `sidecar_shape` · `frozen_tail` · `frozen_inbox_note` · `material_gate_state` · `settled_this_round` · `SPEC_STAGE_AUTHORIZATION` · `SPEC_STAGE_ORDER` |
| F2.2 · F5.2 | `pending_chapters`（还剩几章带待写标记） |

### `skills/story/scripts/core/flow/decisions.py`

| 功能 | 内容单元 |
|---|---|
| F1.6 | `cmd_decide` |

### `skills/story/scripts/core/flow/rounds.py`

| 功能 | 内容单元 |
|---|---|
| F1.4 · F1.5 | `cmd_round` |
| F5.4 | `cmd_reopen` |

### `skills/story/scripts/core/flow/submission.py`

| 功能 | 内容单元 |
|---|---|
| F1.7 | `cmd_complete` · `resolve_candidate` · `section_numbers` · `is_ar_skeleton` · `candidate_problems` · `ar_input_identities` · `prior_ar` · `S4_HEADING` |

### `skills/story/scripts/core/flow/lifecycle.py`

| 功能 | 内容单元 |
|---|---|
| F5.2 | `cmd_status` |
| F5.3 | `cmd_story` |
| F3.3 | `cmd_archived` |

### `skills/story/scripts/core/flow/check.mjs` — JS 侧只读消费流程契约

| 功能 | 内容单元 |
|---|---|
| F5.3 | `flowProblems` · `isStoryFeature` · `storyProduced` · `readFlow` · `FLOW_FILE` · `FLOW_SCHEMA` · `FLOW_STATES` · `FLOW_FIX` · `reached` |
| F1.6 | `FLOW_GATES` · `materialChoices` · `FLOW_CARRY_ALL` · `FLOW_OUTCOMES` |
| F1.7 | `originalArSource` · `DESIGN_FILE` |

### `skills/story/scripts/core/flow/client.mjs`

| 功能 | 内容单元 |
|---|---|
| F2.1 · F5.2 | `queryFlowStatus` · `parseStatus` · `shapeProblem` · `FLOW_SCRIPT` · `PYTHONS` |

### `skills/story/scripts/core/materials/registry.py`

| 功能 | 内容单元 |
|---|---|
| F1.4 | `build` · `compute_digest` · `digest_with` · `source_sha` · `pending` · `refresh` · `read` · `write` · `path_of` · `collect_sources` · `_same_text` · `MANIFEST` · `SCHEMA` · `SOURCE_DOCS` · `SOURCE_DIRS` · `INBOX` |
| F1.3 | `collect_materials` · `kind_of` · `read_captions` · `_write_entry` · `write_caption` · `write_unused` · `clear_unused` · `CAPTIONS` |
| F7.2 | `file_digest` · `MaterialError` |

### `skills/story/scripts/core/materials/importer.py`

| 功能 | 内容单元 |
|---|---|
| F1.2 | `cmd_import` · `scan_sources` · `read_classify` · `is_text` · `validate` · `convert_sources` · `docx_to_markdown` · `read_media` · `_heading_level` · `_run_text` · `_para_markdown` · `_table_markdown` · `render_target` · `demote_headings` · `backup` · `preview` · `DOC_EXT` · `IMAGE_EXTS` · `SKIP_NAMES` · `CLASSIFY_FILE` · `CLASSES` · `DOC_TARGET` · `GENERATED_MARK` · `W` · `R` · `A` · `REL_NS` |
| F1.3 | `caption_image` · `mark_used` · `mark_unused` · `register_ux` · `resolve_image_arg` · `_image_for_mark` · `_no_such_image` · `UX_IMAGE_DIR` |
| F7.1 | `features_dir` · `DEFAULT_PROJECT_ROOT` |
| F7.2 | `log` · `ImportError_` |

### `skills/story/scripts/core/story-build.mjs` — 成文 CLI 入口

| 功能 | 内容单元 |
|---|---|
| F2.2 | `cmdSkeleton` |
| F2.5 | `cmdProject` |
| F2.6 | `cmdNumber` |
| F5.5 | `cmdReviewTask` |
| F5.2 · F5.6 | `main` · `parseArgs` · `COMMANDS`（命令分派、`--offline`/`--deliver` 的互斥） |

### `skills/story/scripts/core/story/context.mjs`

| 功能 | 内容单元 |
|---|---|
| F2.2 | `createContext` · `createOfflineContext` · `commonInputs` · `compileIdShapes` · `CORE_DIR` · `AR_ROOT_FILES` |
| F5.3 | `STORY_SRC_LEDGERS` · `requireLedgers` · `ledgerDigestProblems` · `strayFileProblems` · `storyFrozen` · `refuseIfFrozen` · `digestOf` |
| F7.2 | `fail` · `readText` · `readRaw` · `readJson` · `writeJson` · `activeKnowledgeEntries` · `specText` |

### `skills/story/scripts/core/story/document.mjs`

| 功能 | 内容单元 |
|---|---|
| F2.4 | `fenceRanges` · `fencedLines` · `maskOf` · `parseChapter` · `sectionNames` · `sectionBody` · `tablesIn` · `matchSection` · `storySections` · `chapterSpan` · `subsectionSpan` · `CLOSING` · `SEPARATOR` · `norm` |
| F2.4.2 | `hasDiagram` · `DIAGRAM_LANGS` |
| F2.6 | `normalizeHeading` · `takeAuthorNumber` · `renumberStory` · `NUMBER_PREFIX` · `BARE_NUMBER_PREFIX` · `LETTER_PREFIX` · `FIGURE_PREFIX` · `pendingMark` · `pendingChapters` · `PENDING_MARK` · `PENDING_RE` · `EMPTY_SECTION_TEXT` |
| F2.5 · F3.2 | `ZONE_BEGIN` · `ZONE_END` · `zoneBlock` · `zoneSpan` · `zoneHandEdited` · `projectionDigest` · `recordedDigest` · `DIGEST_IN_MARK` · `ProjectionConflict` |

### `skills/story/scripts/core/story/drafts.mjs`

| 功能 | 内容单元 |
|---|---|
| F2.2 | `writeDrafts` · `draftPath` · `chapterDraft` · `guideLine` · `GUIDE_MARK` · `DRAFTS` |
| F5.4 | 草稿登记后不删（同上符号，返修用） |
| F7.2 | `shellArg` |

### `skills/story/scripts/core/story/chapter-contract.mjs`

| 功能 | 内容单元 |
|---|---|
| F2.4.1 | `chapterStructureProblems` · `requiredH3` · `requiredTables` · `tableProblem` |
| F2.2 | `chapterSeedRows` · `tableSeed` · `appendixSeedRows` · `renderTable` |

### `skills/story/scripts/core/story/chapter.mjs`

| 功能 | 内容单元 |
|---|---|
| F2.4 | `cmdChapter` · `chapterProblems` · `stripGuidance` · `stripOwnHeading` · `strayHeadings` · `placeholderProblems` · `withoutDiagramBodies` · `chapterAnchors` · `chapterBodyIn` |
| F5.2 · F5.4 | `nextSteps`（NEXT/INPUT/RESULT 前三行） |

### `skills/story/scripts/core/story/check.mjs`

| 功能 | 内容单元 |
|---|---|
| F2.7 | `cmdCheck` · `groupedProblems` |

### `skills/story/scripts/core/story/sources.mjs`

| 功能 | 内容单元 |
|---|---|
| F1.4 | `readManifest` · `scanSources` · `sourceStatus` · `missingSourceLine` · `materialsNotReady` · `REMOTE_ONLY_SOURCES` |
| F1.7 | `originalArTarget` · `materialListTargets` |
| F2.7 | `sourceProblems` · `materialListProblems` · `materialListSkeleton` · `materialLinkTargets` · `redactMaterialLinks` |
| F2.1 | `upstreamDocs` |
| F7.2 | `relFromFeature` · `relFromStory` · `joinPosix` · `basename` |

### `skills/story/scripts/core/story/images.mjs`

| 功能 | 内容单元 |
|---|---|
| F1.3 | `imagesIn` · `readablePaths` · `materialImages` |
| F2.4.2 | `diagramsOf` · `diagramTopic` · `diagramsNotCarried` · `danglingFigures` · `carriedDiagramProblems` · `imageProblems` |

### `skills/story/scripts/core/story/appendix.mjs`

| 功能 | 内容单元 |
|---|---|
| F2.5 | `appendixProjection` · `projectAppendix` · `appendixChapter` · `appendixTables` · `appendixTableHeader` · `APPENDIX_FROM_SPEC` · `DROP_COLUMNS` · `specSection` · `specTerms` · `scopeList` · `scopeBoundaryRows` · `scopeRationale` · `pipeTables` · `isPlaceholderRow` · `specNotApplicable` · `knowledgeUseVerdicts` · `verdictSkeleton` · `DOMAIN_NA` · `materialSubsectionName` · `KNOWLEDGE_USE_SOURCE` · `specGaps` · `appendixSpecGaps` · `appendixSourceProblems` · `appendixStructureProblems` · `appendixZoneProblems` · `zonesOnDisk` · `cut` · `firstDiff` |

### `skills/story/scripts/core/story/review.mjs`

| 功能 | 内容单元 |
|---|---|
| F3.1 | `DECISION_FIELDS` · `DECISION_SHAPE` · `decisionList` · `decisionsMissing` · `decisionProblems` · `requireStoryFirst` · `sectionNameOf` · `STATUS_CHAPTERS` |
| F3.2 | `cmdBuild` · `renderReview` · `renderDocHeader` · `renderMachineZone` · `renderHumanZone` · `humanZoneStart` · `machineZoneOf` · `issueHandEdited` · `extractHumanZone` · `extractFreeformZone` · `renderFreeformSection` · `groupByCategory` · `issueMark` · `ISSUE_MARK` · `HUMAN_ZONE_MARK` · `FREEFORM_OPEN` · `FREEFORM_CLOSE` · `FREEFORM_CHAPTER` · `DOC_HINT` · `FREEFORM_HINT` · `reviewFormProblems` · `REVIEW_BANNED_LINES` |
| F2.7 | `redactReviewExemptZones`（语言判据在评审件上的豁免区） |

### `skills/story/scripts/core/story/language.mjs`

| 功能 | 内容单元 |
|---|---|
| F2.7 | `scanBannedTerms` · `scanLanguageRedline` · `scanLocalPaths` · `scanMaterialList` · `scanDanglingRefs` · `formatHits` · `narrativeLines` · `redlineScopes` · `EXEMPT_LINE_PATTERNS` · `moduleLayerIds` · `localPathRe` · `GENERIC_PATH_ALTS` · `SEARCH_PHRASE_RE` · `SOURCE_TAG_RE` · `DOC_COORDINATE_RE` · `CAMEL_CASE_RE` · `SNAKE_CASE_RE` · `INLINE_CODE_RE` · `AI_HEADING_TERMS` · `REDLINE_HINTS` · `DANGLING_REF_PATTERNS` · `FRAMEWORK_ARTIFACT_NAMES` · `constraintNames` · `bareFileNameRule` · `firstSegment` · `escapeRe` · `readConfig` |
| F2.3 | `clientVocabulary` · `CONTRACT_PATH` · `vocabularyCache` |
| F2.4.2 | `scanBrokenImages` · `IMAGE_HINTS` |

### `skills/story/scripts/core/story/delivery.mjs`

| 功能 | 内容单元 |
|---|---|
| F5.6 | `deliveryProblems` · `deliveryNextSteps` · `receiptRunner` |

## skills/story-adaptation/ —— 跨仓安装升级

### `skills/story-adaptation/SKILL.md`

| 功能 | 内容单元 |
|---|---|
| F6.2 | 「所有权由目录表达」·「3 写入」 |
| F6.3 | 「两种来源」·「对接层的输出合同」 |
| F6.1 | 「你要做的四件事」·「1 前置」·「2 判态」 |
| F6.4 | 「4 确认」·「不做的事」 |

### `skills/story-adaptation/scripts/adapt-scan.mjs`

| 功能 | 内容单元 |
|---|---|
| F6.1 | `skeletonKnowledge` · `knowledgeBlock` · `freshIdentity` · `composeManifest` · `STATE` · `findRoot` · `config` · `extDir` · `featuresDir` |
| F6.2 | `CORE` · `SCRIPTS_DIR` · `walk` · `coveredFiles` · `inWriteFace` · `dirtyPaths` · `git` · `isRepo` · `read` · `rel` · `sha` · `TARGET` · `PKG` · `PDIR` · `TDIR` · `SAME_TREE` · `MODES` · `mode` · `opt` · `argv` · `die` |
| F6.3 | `ADAPTERS` · `WITH_ADAPTERS` · `MOCK_ADAPTER_PACKAGE` · `PKG_NAME` · `pkgManifest` · `PKG_MANIFEST_TEXT` · `tgtManifest` · `manifestValue` |
| F6.4 | `TARGET_OWNED_KEYS` · `versionNotes` · `withVersionNotes` · `KNOWLEDGE` · `bridgesOf` · `BRIDGES` · `missingGitignoreLines` · `EXT_BEGIN` · `EXT_END` · `SECTION` · `ENTRIES` · `stripMarks` · `replaceZone` · `extensionSectionEnd` · `bad` |

---

## 完整性自核

本稿按「`doc/extensions/` 下每个交付文件的每个顶层单元至少出现一次」写。核对方式与结果：

- **代码文件**（`.mjs` / `.py` / `.js`）：顶层函数、类与常量逐个列出，与机械清点的符号集合逐文件比对，
  差集为空；`__init__.py` 无顶层符号，按「空包标识」登记。
- **提示词与规则页**（`.md`）：按二级标题登记，三级标题随父节，另有归属的（如 spec.md 的六步、
  story-write.md 的十章）单列。
- **合同与配置**（`.json` / `.yaml`）：顶层键逐个列出；`*_note` 说明键与它解释的键同归属。
- **不登记**：`__pycache__`、`node_modules`。

覆盖粒度：`knowledge/` 正文按下表所列文件、条目表/处置节及模式分节归入F4相应功能，并列消费者，不把每条业务知识另建机制功能ID；内容由目标工程维护不代表它不在本清单内；
`adapters/` 三个文件在本仓是替身，功能归属按它们的**输出合同**登记，不按替身的实现细节。
