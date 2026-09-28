# 盘点 B · `story-build.mjs` + `core/story/*.mjs` + `contracts/story-chapters.json`（只读，2026-09-16，基线 9b4637fa）

对象：14 个模块共 5116 行 + 合同 369 行。证据口径：UT＝`test/story/tests/*.py`；FM＝`test/story/regression/failure-modes.yaml`（73 条）；实跑＝两轮 suite 的 `events.jsonl`。限定：`writing-plan/chapter-contract/document` 最后改动在 `cee9bde7`（09-16），`drafts/recheck` 在 `1605003c`；0915 那一轮跑的是它们的上一版，只有 0916 一轮对这几件是现役证据。

## 1. `story-build check` 判据逐条

`cmdCheck` 在 `check.mjs:50-302`，`mark(label)` 分 17 类。编号有洞（②⑥⑦⑧不存在），打印顺序不是编号顺序。

| 判据 | 做什么 | 输入/输出 | 确定性/代理 | 现役证据 | 可疑点 |
|---|---|---|---|---|---|
| ⓪a 声明的来源都在 | required 读不到就拦，可选记一笔 | `check.mjs:78-83` → `sources.mjs:265/75` | 确定性 | UT 多条；实跑 4 次只出「UPSTREAM 不存在（可选）」 | 「远程单」由 `AR/detail.json` 存在判（`sources.mjs:77`），与 `delivery.mjs:36` 两套定义 |
| ⓪b 台账没被换 | sha256 前 16 位比对 | `check.mjs:85-86` → `context.mjs:233` | 确定性 | UT 1 条；实跑从未报 | `digestOf` 只归一 CRLF 不归一 BOM |
| ⓪c 写作设计 | 协议问题并进阻断 | `check.mjs:88-92` → `writing-plan.mjs:76` | 协议形态；离线不判 | UT；实跑 4 次协议报错全在 skeleton「记一笔」通道 | 同一判据三个入口两种强度（skeleton warning / check、chapter BLOCKER） |
| ① 章标题与顺序 | 标题串逐字比 | `check.mjs:94-106` | 确定性 | 无直接 UT；实跑从未报 | 多/缺/乱序共用一条消息 |
| ①b 大标题带需求编号 | 在线 `includes(feature)`；离线退化为「像编号」 | `check.mjs:108-125` | 离线分支形态代理 | UT 3 条；实跑从未报 | `AR9000` 被 `AR90006` 满足 |
| ③ 验收编号落在验收章 | `id_shapes.keep` 编号全集须在标题含「验收」的章 | `check.mjs:127-145` | 确定性 | 只有正则编译 UT；实跑从未报 | 验收章靠 `title.includes('验收')`；`keep` 只有 1 条 |
| ⑤ 决策登记字段齐备 | 三字段 + 无标题行 + review_mode + choice 形状 + category 在词表 | `check.mjs:147-148` → `review.mjs:200` | 确定性；「写了后果」是字面代理（`——`） | UT 多条；实跑从未报 | 离线不判；`——` 写成 `:` 即判缺后果 |
| ④ 图片身份 | 5 子判据 | `check.mjs:150-155` → `images.mjs:137` | 确定性 | UT、FM S10/S11/S17；实跑 2 次报同一条（登记的图没去处） | 其余四条两轮零命中 |
| ⑨ 归档件四红线 | 仓内路径、禁用词、悬空引用、图片断链 | `check.mjs:157-189` → `language.mjs` | 词表 + 正则 | 实跑命中最多：0915 12 处、0916 16 处，只有悬空引用与 review 侧仓内路径两种 | 禁用词与图片断链两轮零命中；review 仓内路径命中全来自「依据」里写的材料位置——一条判据要求写依据、另一条禁止写位置；story 断链在此置空改由 ⑪ 判 |
| ⑩ 语言红线 | 主叙事 8 类 | `check.mjs:194-226` → `language.mjs:237` | 形态代理为主 | 0915 12 处、0916 2 处；只有 4 类被触发 | `placeholder_heading`/`ai_heading`/`search_phrase`/`harness_artifact` 两轮零命中；`doc_coordinate` 与 ⑨ 同行双报（0915 auto 116 行实证） |
| ⑪ 章内必要项 | 围栏、占位符、待写、必要结构、小节形态、仓内编号、断链 | `check.mjs:228-238` → `chapter.mjs:143` / `chapter-contract.mjs:141` | 混合；必要表按锚列词组＝词表代理 | UT 大量；FM；check 层两轮零命中，只在 chapter 提交时 0915 报 2 次 | 章前言占位符 `split(/\n##\s/)[0]` 不过围栏掩码 |
| ⑫ 附录结构 | 五节、无多余、非空、无非 mermaid 围栏、不放图 | `check.mjs:240-241` → `appendix.mjs:478` | 确定性 | UT、FM S06/S18；实跑从未报 | `:489 materialName` 死变量；`:259-261` 承诺的「散文尾巴」判据不存在（FM S15 已 retired） |
| ⑫b 机器区与真源一致 | 附录 A–D 逐行 diff + 上游图有来源标记 | `check.mjs:243-248` → `appendix.mjs:554` + `images.mjs:273` | 确定性 | UT 8 条；0915 12 处、0916 4 处 | `carriedDiagramProblems`（上游图没搬）归错在此标签下；离线时前者 return 后者不看 offline |
| ⑫c 形态 lint | 图前承接句/图连图；材料清单行形态与集合 | `check.mjs:250-256` → `images.mjs:103` + `sources.mjs:287` | `danglingFigures` 形态代理语义（注释自认） | 0915 4 处全是 `danglingFigures`；0916 零；FM S16/S19 | FM S20 `responsibility: observed` 而代码仍硬拦；材料清单几条两轮零命中 |
| ⑬ 评审记录只含渲染语法 | 6 条行首正则 | `check.mjs:258-259` → `review.mjs:307` | 确定性，词表在脚本 | UT 1 条；实跑从未报 | 词表不在合同 |
| ⑮ AR 根只有交付文档 | 白名单 4 个 | `check.mjs:261-262` → `context.mjs:254` | 确定性 | UT 多条；实跑从未报 | — |
| ⑭ 交付门 | `--deliver`：check-receipt + 读者审查回执 | `check.mjs:264-274` → `delivery.mjs:66` | 确定性 | 实跑 4 次全过 | `--phase spec` 硬编码 |
| 起步：台账在不在 | 缺任一即 BLOCKER | `check.mjs:52` → `context.mjs:159` | 确定性 | UT | 名单真源在 Python `state.py::STORY_SRC_FROZEN` |
| 分组打印 | 按 `mark` 插入位置切 | `check.mjs:35-48` | — | — | 只按插入顺序，判据函数返回顺序变了就落到隔壁标签（⑫b 已发生） |

两轮合计：报过错 5 类（④ 1 子判据、⑨ 2、⑩ 4/8、⑫b 2 来源、⑫c 1）；从未报错 12 类。

## 2. `language.mjs`（483 行）

| 机制 | 事实 | 可疑点 |
|---|---|---|
| `clientVocabulary` | 读合同 `client_vocabulary`，自己 `readFileSync` 合同（`:23,33-42`） | 词表 7 条；第二个合同读取者 |
| `scanBannedTerms` | 逐行子串，跳围栏/豁免章/豁免语境行（`:116-138`） | `EXEMPT_LINE_PATTERNS`（`:51-54`）含 `/禁用\|红线\|改说\|违规\|banned/i`：任何含「红线」的业务句整行免检；无词边界；`灰度` hint 写死本工程业务词 |
| `repo_identifier` | 行内代码 + 驼峰 + 双下划线（`:160-164`） | 纯形态；注释自认曾用材料派生词表因误伤退回 |
| `rule_id` | 激活清单编号（`:286-288`） | 数据来源真实 |
| `search_phrase` | `检索…(零命中…)`（`:151`） | 零命中；固定句式 |
| `source_tag` | 5 个固定括注词（`:154`） | 实跑命中 3 处；词是「这一轮见过的那几个」 |
| `doc_coordinate` | `*.md` 或 `§数字`（`:157`） | 与 ⑨ 悬空引用同行重复报 |
| `placeholder_heading` | H3/H4 含 `{{`/`<…>`（`:264-266`） | 零命中；与 `placeholderProblems` 重叠 |
| `ai_heading` | 问号结尾或 5 个口头禅（`:167`） | 零命中；词表硬编码 |
| `harness_artifact` | 合同 `harness_terms` 21 词，scope all（`:302-306`） | 零命中；含 `post_check/收件箱/台账/门禁/守恒/关卡/回写/夹具/人话/lint/mock`，无词边界 |
| `scanLocalPaths` | 通用段 + 从 `framework.config.json` 现取业务模块段（`:359`） | 配置不存在时静默退回通用段 |
| `scanDanglingRefs` | 7 条固定正则 + 裸文件名（`:379-411`） | 实跑命中最多；`ar_design_init|SKILL.md` 内部文件名硬编码 |
| `scanBrokenImages` | `existsSync`（`:471`） | 不处理围栏 |
| 围栏判定 | 三处各写 `inFence` 前缀翻转（`:124/255/430`） | 不认标记种类与长度；与 `document.mjs:38-41`「只有这一处」不符 |
| 模块自述 `:3-5` | 「供 post_check 与 story-build 共用」 | `post_check.mjs:23` 只 import `scanBannedTerms/formatHits` |

## 3. `appendix.mjs`（702 行）

`specSection:79-91` 第 6 个定位实现（不认围栏）；`pipeTables:96-106` 与 `parseChapter` 表解析分隔行判定不同；投影 A/B 表头原样搬 spec，`DROP_COLUMNS` 只 1 项；投影 C「为什么这么切」把 spec `rationale` 整段塞进一格（`:259`，无 `|` 转义）；投影 D「依据」一列三种语义混装（`:41-51`）；`projectAppendix:304-362` 内含第 7 个定位实现（`:352-358`）；`appendixStructureProblems:478-537` 死变量 `:489`、注释承诺的判据不存在；`appendixZoneProblems:554-628` 只归一行尾空白。与正文重复：附录 C 的 rationale 原文、附录 D 的 requirement/reason 原文是上游散文进机器表。

## 4. `review.mjs`（638 行）

`decisionList:54-58` 宽进；`decisionsMissing:122-136` 严格；三字段 `:21-25`；澄清正文无标题行 `:228-232`（围栏内 `#` 也算）；`review_mode` 枚举 `:236-239`，不写落到无名的 `PLAIN_ZONE`；`choiceListProblems:278-304` 靭字面段名 `可选的做法`（`:258`）定位，改段名整条静默不判；`optionsSqueezed:265-269` 形态代理（说明性连续编号也被判挤压）；每项后果只认全角 `——`（`:294`）；`category` 在词表 `:244-250`，报错写死「这十一类」；三层豁免 `:82-115`（第一条议题之前的文档头会被划给第一条）；`reviewFormProblems:33-40,307-322` 词表在脚本；`renderReview:603-638` 三级分层；人工区逐字节保留 `:470-529`（边界猜测时置 `ambiguous`）；机器区手改抛 `ProjectionConflict`。`:431` 注释：choice 五段「决策点/依据/可选的做法/建议/理由」，只核一段。

## 5. `chapter-contract.mjs` + `document.mjs`

`parseChapter:113-142` 一次解析；`fenceRanges:54-75` 严格开闭（UT `test_chapter_view.py:430` 声称「只有一处」与事实不符）；`scopeSpan:178-189`；`matchSection:240-244` 先精确再包含（代理语义：「参与方」命中「参与方与分工」也命中「参与方不在本轮」）；`tablesIn:162-169` 无 `under`，固定合同的表定位不到 H4；`subHeadingsUnder`（`chapter-contract.mjs:34-41`）重扫已有 `subs`；`subsectionSpan:428-449` 第 2 套定位（无围栏掩码、精确匹配）；`diagramsOf` 第 5 套；`screeningDoubts` 第 6 套；必要表按锚列 `has(cols, group)` 双向子串（`编号` 命中「设备编号」），合同为一列准备 4 个同义说法（`story-chapters.json:129`）；必要 H3 按标题名判（模块自述 `:12-14` 说标题名不是内容判据）；图只核有一张、图种＝首行关键字；`forms` 只核存在；`chapterSeedRows:209-239` 与 `missingPickedSeeds:248-282`；`renumberStory:324-389` 含 `takeAuthorNumber` 29 个量词代理；`PENDING_MARK` JS 写死（`:493`）而 Python 读合同。

## 6. `writing-plan.mjs` + `drafts.mjs`

协议两部分 `PARTS:22`；旧协议识别 `RETIRED_PARTS:24`、`LINE.retired:37`；骨架逐行归属 `readSkeleton:127-217`，封闭枚举（4 形式词 + 8 图名），实跑 0916 两 Case 各报 1 次「有一行不是骨架写法」+ 1 次「形式：… 不认识」（模型写 `形式和内容：`、`形式：表格（编号 | …）`、`形式：叙述+图`）；`selectedStructure:254-287`；`draftPath/chapterDraft`（`drafts.mjs:24-101`，`boundary` 全仓唯一读者）；`shellArg` 写死 PowerShell；「动过的字节不改」`writeDrafts:130-163`：判等用重新渲染的起点逐字节比，渲染输入一变没动过的草稿也会被判「动过」；已写完章草稿补回用成稿 `:147`。

## 7. `sources.mjs` / `images.mjs` / `context.mjs`

`scanSources:29-51` 把合同 `notes` 塞进 `docs[].notes` 无人读；`sourceStatus:64-82` 远程单判据与 `delivery.mjs:36` 两套；`materialListSkeleton:221-231` 按精确路径反查 label；`redactMaterialLinks:207-218` 依赖第 2 套定位；`upstreamDocs:174-181` 硬编码两路径不读合同；`diagramsOf:26-70` 只认 mermaid（`DIAGRAM_LANGS` 认 5 种）；`carriedDiagramProblems:273-292` 归错类、不看 offline、4 行长文重复；`danglingFigures:103-134`；`imageProblems:137-213` 两轮只报同一张「同页不同分辨率」图；`createOfflineContext` 位置猜测；`STORY_SRC_LEDGERS:146-149` 真源在 Python。「材料」在三处各算一次并硬编码第 4 份。

## 8. `story-chapters.json` 顶层键 × 读者

有读者：`sources`、`chapters`（子键全有读者）、`id_shapes`、`language_redline`、`decision_categories`、`gates`、`heading_counters`；`verdicts` 只被审查任务书读；`pending_mark` 只 Python 读。
零读者：`version`；`note`、`skeleton_note`、`sources_note`、`structure_note`、`gates_note`、`pending_mark_note`、`heading_counters_note`、`decision_categories_note`；章内 `subsections_note`、`subsection_tables_note`、`banned_terms_note`×3；`id_shapes._note`、`language_redline._note`、`language_redline.scope`（顶层）、`client_vocabulary_note`；`sources.SPEC.notes`。

## 9. `delivery.mjs` + `recheck.mjs`

`receiptRunner:20-27` 绕开 npx；`--phase spec` 硬编码 `:83`；读者审查回执分支 `:95-111`；`deliveryNextSteps:35-47` 远程单判据两套；`recheckItems:57-71` 五类只枚举不判；`screeningDoubts` 靠字面 `⑥` 与列名「还要核实」，`EMPTY_CELL` 只认单字「无」；`storyDiagrams` 用 5 种图语言与 `diagramsOf` 不一致；`RECHECK_ASK:13-14` 350 字提示词写在脚本里。

## 10. 跨机制观察

10.1 形态代理语义：锚列同义词表、`matchSection` 包含、必要 H3 标题名、`AI_HEADING_TERMS`、`SOURCE_TAG_RE`、`harness_terms`、驼峰/下划线/反引号、`danglingFigures`、`optionsSqueezed`、`——`、`takeAuthorNumber` 量词、`title.includes('验收')`、`EXEMPT_LINE_PATTERNS` 反向代理。
10.2 成对/重复：标题定位 6 套、围栏扫描 5 套、表解析 2 套、「远程单」2 套、占位符判据 2 套、同一行两判据双报、story 断链拆两处、合同读取 2 份、上游文档清单 2 份、图语言集合 2 套、`待写` 字面 2 份、`subHeadingsUnder` 重扫。
10.3 单一形态而存在：`appendixTableHeader` 只 1 张表、`DROP_COLUMNS` 1 项、`id_shapes.keep` 1 条、`structure.h3/diagram` 各 1 处、`structure.h4` 合同零处、`REMOTE_ONLY_SOURCES` 2 项、`AR_ROOT_FILES` 4 项、`REVIEW_BANNED_LINES` 6 条零命中。
10.4 承诺而不读：`structure_note`、`sources.SPEC.notes`、`verdicts`（脚本不判）、`subsections_note` 目的句、`appendix.mjs:259-261` 散文尾巴、`language.mjs:3-5` 共用自述、`document.mjs:38-41` 唯一围栏自述、`chapter-contract.mjs:12-14` 标题名自述、FM S20 observed、FM S08/S09/S12/S13/S15/S19 retired 而 checker 仍在 `check_failure_modes.py:2133-2258`。
10.5 死代码：未使用 import（`story-build.mjs:34`、`appendix.mjs:12/15`、`check.mjs:25`、`delivery.mjs:10`、`images.mjs:10`、`review.mjs:10/12`、`sources.mjs:9/13`）；死变量 `appendix.mjs:489`；孤立 JSDoc（`sources.mjs:88-99`、`appendix.mjs:73-76/204-205/410-411`）；悬空小节标题（`document.mjs:594-597`、`delivery.mjs:115-118`、`check.mjs:304-307`）；`language.mjs:232 @param opts.identifiers` 不读；`IMAGE_HINTS` 命名不符。
10.6 两轮实跑：`check` 非零退出 6 次，报错集中 5 类；`chapter` 失败 2 次均在旧版；`skeleton` 记一笔通道持续输出协议问题但不拦；4 个 case 交付门全过。
