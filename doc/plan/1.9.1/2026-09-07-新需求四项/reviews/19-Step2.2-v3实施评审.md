# Step2.2 v3 实施评审

> 2026-09-09；评阅提交 `1a93fca7`（四段实施）与 `b838f06c`（预算按实签），对照 [v3 方案](../steps/02.2-v3-成文职责替换与模型执行方案.md) §2–§10 与 [执行者反馈](../98-执行者给评审的反馈.md) 下半篇。四道门本次亲自重跑；行号取自当前 HEAD；未改生产代码、未跑 CLI。

## 1. 结论

**实施评审通过，附四处返修；行为待验。** 方案 §2 表里六项替换在代码里都对得上，退出项退干净了（`copyedit` / `COPYEDIT_ROWS` / `chapterSection` / `只看上一章结尾` 在 `doc/extensions` 全零命中），reviews/18 的 D1–D3、N1–N5 全部落地，四道门与预算实测与反馈自述一致。

四处返修都是交付面或失败路径上的一致性问题，没有一处推翻设计；改完不必重开评审，按 §4 的判据自核即可。

## 2. 四道门与预算（本次重跑）

| 门 | 结果 |
|---|---|
| 离线全量 `pytest -n auto --dist loadscope` | 796 passed, 244 subtests |
| 失效形态 | 70 条 FAIL 0（PASS 59、委派 11） |
| `adapt-scan --check` | 通过 |
| `framework/` | 零改动（`git diff --stat 6ca48c41..HEAD -- framework/` 为空） |
| 预算实测 | scripts_mjs 2816 / hooks_mjs 3016 / scripts_py 1564 / prompts_md 1784 / data 752，合计 9932；与 `mechanism-budget.yaml` 三处 reason 记的数一致，用户签 9950 |

## 3. 逐项核：方案说要做的，代码里是什么

| 方案 | 现场 | 判定 |
|---|---|---|
| §2 逐章要求一份 | `author.mjs` 的 `chapterSection` 删除，换 `draftEntrySection()`（`:200-212`）只给入口；`story-build.mjs` 的 `chapterDraft`（`:2414`）不再写章头三行注释 | 成立 |
| §4.1 指导区、逐字节保持 | `bufferLines` / `guidanceSpan` / `putGuidance`（`:2468-2550`）按字节切行、容 CR、认 BOM、Buffer 切片拼接；`test_refreshing_keeps_the_author_bytes_exactly` 用 BOM + 混合行尾 + 末尾无换行的作者区核 sha256 不变 | 成立，是 D3 要求的写法 |
| §4.1 先剥指导区再 `stripGuidance` | `cmdChapter :2917-2921` 顺序正确；`test_a_quoted_machine_marker_inside_the_zone_leaves_with_it` 覆盖 N3 那一例 | 成立 |
| §4.2 `currentScope` 单一真源 | `flow-check.mjs:367-461` 导出纯函数，`flowProblems :541` 与 `guidanceInputs :593` 都消费它；旧内联 split 语义整段删除 | 成立，N1 落地 |
| §3 skeleton 写前预检 | `cmdSkeleton :2794-2798` 先 `guidanceInputs`，缺件一个字节不写；`SkeletonReadsBeforeItWrites` 四例；`write_min_flow` 共享夹具 | 成立，D1 选 ① 落地 |
| §4.3 只刷目标章 + 跳章提示 | `prepareNext :2864-2876` 只刷首个待写章，stdout 带「要先写别的章，跑 `prepare --chapter`」（`:2875`）；`OneTargetAtATime` 三例 | 成立，reviews/18 对 D2 的前提满足 |
| §5 `chapterProblems` 共用 | `:1119-1207` 一份实现；`cmdChapter :2937` 写盘前调、`cmdCheck ⑪ :1603` 逐章调；`test_the_same_bad_chapter_reads_the_same_at_both_entries` | 成立 |
| §5.3 Mermaid 节点不算工作编号 | `withoutDiagrams :1089-1103`，只挖围栏内容不动行号 | 成立 |
| §6 三个整稿动作当场送到 | `story-write.md` 的 `story-method:whole` 块（`:328-375`）；`wholePassOutput :2841` 从块读；`chapter` 最后一章与 `prepare` 输出同一段（`test_the_last_chapter_and_a_later_prepare_say_the_same_thing`） | 成立 |
| §6.3 copyedit 退场 | `STORY_SRC_LEDGERS :195` 只剩 decisions；`story_flow.py:81` `STORY_SRC_FROZEN = ("decisions.json",)`；`test_the_forward_chain_runs_through_registration` 核冻结清单只剩一件 | 成立 |
| §7 Story 全文送 verifier、PASS 可写明细 | `reader-review-task.mjs:52-65` 附全文一次并要求报截断缺口；`:130-134` 改判 PASS 可附短句 | 成立 |
| §7 `reviewVerdict` | `verifier-report.mjs:206` 从汇总行第二格去格式符转大写，十个分支各给；`deliveryProblems :2033-2039` 要求 PASS；`test_a_structurally_sound_fail_does_not_deliver` | 成立，reviews/17 §4 的缺口关闭 |
| §7 `next_step` / `spec_stage_step` 文案 | `story_flow.py:867-877` 新 `story_chapters` 分支指向 prepare；`:974-976` 删「没有审查员就直接下一步」 | 成立（文案与代码有一处不一致，见 R2） |

## 4. 返修四处

### R1 · 交付面四处仍说「十章各答什么在任务包里」

`chapterSection` 删了，但这四句还在：`hooks/spec/author.md:6`「十章各答什么、哪些词不能用——由同一个钩子生成的任务包给出」；`hooks/spec/author.mjs:6` 文件头注释同句；`phases/story-write.md:52`「材料与图、已确认的范围、已登记的判断、十章各要回答什么——本阶段任务包一次给全」；`skills/story/SKILL.md:158` 同句。

现在范围、判断、十章问题都在草稿指导区，任务包只给入口。作者按这四句去任务包里找，找到的是「§5 成文从哪进」那一段指回草稿——不会走丢，但这是交付面在说一件已经不成立的事（`AGENTS.md` §5.3）。四处各改一句：任务包给材料、图、知识与词表；每章要答什么、范围与判断在那一章草稿的指导区。

### R2 · 未登记审查员的交付政策：代码、方案、提示三处说法不一

代码（`deliveryProblems :2033-2039`）：`status === 'NOT_APPLICABLE'` 时不加问题、只记一笔——本宿主没登记审查员照样放行。反馈 §5b 记用户 2026-09-09 批准的正是这个「保持现状」。但 v3 §7 第 205 行仍写「未启用、缺报告、缺判项、非 PASS 或结构错误均不能正式交付」；`story_flow.py:976` 的恢复提示写「它要三样：回执通过、读者审查写成了报告、那一项判的是 PASS」。

以用户批准的为准，改两处文字：v3 §7 那一句加「本宿主未登记审查员时记一笔放行」；`next_step` 那句改成「登记了审查员就要三样……没登记的记一笔出声」。不改代码。

### R3 · 本章写入之后，后继准备还有一条 exit 1 的路

方案 §5.2：本章已写入则 exit 0，后继失败走 stderr + NEXT。代码对「输入缺件」做到了（`cmdChapter :3029-3035`），但 `prepareNext :2873` 调 `refreshGuidance`，而它对「下一章草稿不在」（`:2732`）和「下一章指导区边界坏了」（`:2738`）都走 `fail()`——这时本章已经落盘，进程却以 1 退出，输出里「已落盘」与失败并列，作者按退出码判会去重写本章。

可达性低（要作者删了或改坏了下一章草稿），修法小：`cmdChapter` 里把 `prepareNext` 包一层，`GuidanceError` 与草稿缺失都按 `:3029` 那条路走——stderr 报后继错误、NEXT 给 `skeleton`（补稿）或 `prepare`（刷区）、exit 0。补一例测试：删掉下一章草稿再提交，退出码 0 且本章在 story 里。

### R4 · 统稿输出的 NEXT 与作业书说的顺序不一致

`wholePassOutput :2853` 的 NEXT 是直接 `chapter --chapter <要改的章名> --from <它的草稿>`；`story-write.md:364` 说「要动第五章就先 `prepare --chapter <第五章>` 刷一次它的指导区，在它的草稿上改，再跑 `chapter`」。两条都能跑通（已完成章的草稿没有指导区，`chapter` 不要求它有），但模型同时收到两个顺序。统一成作业书的写法：NEXT 先 `prepare --chapter`，改完再 `chapter`。

## 5. 其它核过、不需要动的

- **过程偏差**（反馈 §1，四段一次交回）：用户指令在先，且中间态确实不可交；按段的改动与判据在反馈 §2 里分得开，本评审按段核过。接受。
- **§9.3 过拟合自查**：M02 通过；对改动过的生产文件定点 grep（单号、用例名、模型名、轮次数字），三处命中全是改动前就在的产品概念「上一版」（`story-build.mjs:1032/:2286/:2322`，M02 已具名豁免）。
- **预算差额**（+365 对估 +40～+105）：五笔具名，最大两笔（字节级定位 +95、一次取齐输入 +75）都是 reviews/18 D3 与 D1 直接要求的失败路径与边界处理；用户已按实签。估算方法的老毛病（把「补一个保护能力」估成「加一段判据」）仍在，反馈自己也这么写了，不重复。
- **字节成本**（反馈 §7）：指导区 4.6–5.5KB/章，其中方法块 2.8KB 是每章固定成本。这是 §11.2 行为验收要看的数，先记着。

## 6. 行为验收仍待用户启动

反馈 §8 的四条与 v3 §9.2 一致：作者读不读指导区并按「先比较已讲过的」写、三个整稿动作在真实稿件上是否减少重复与不一致、拿到全文的读者审查报不报人找得到的缺陷、中断后靠 `prepare` 恢复。本步状态：**实施评审通过（待 R1–R4 返修），行为待验**。

## 本次核对范围

读 `git diff 6ca48c41..HEAD -- doc/extensions test/story` 全文；对照 `story-build.mjs`（`chapterProblems :1119`、`withoutDiagrams :1089`、`deliveryProblems :2033`、`chapterDraft :2414`、指导区 `:2468-2550`、`guidanceInputs :585`、`refreshGuidance :2729`、`wholePassOutput :2841`、`prepareNext :2864`、`cmdChapter :2917-3035`）、`flow-check.mjs:367-461/:541`、`story_flow.py:81/:867-877/:974-976`、`reader-review-task.mjs:52-65/:130-134`、`verifier-report.mjs:206/:256`、`author.mjs:200-212`、`story-write.md:86-112/:328-375/:364`；跑四道门与 `test_mechanism_budget.measure()`；在真实 feature AR90006 上跑 `prepare`（冻结守卫拒绝，接线正确）与 `check --deliver`（在回执那一步按预期停下）；对 `doc/extensions` grep 退出项与旧句子。
