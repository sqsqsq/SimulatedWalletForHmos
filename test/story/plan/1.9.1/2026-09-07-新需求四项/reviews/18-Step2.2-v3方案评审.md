# Step2.2 v3 方案评审

> 2026-09-09；评阅 [Step2.2 v3 · 成文职责替换与模型执行方案](../steps/02.2-v3-成文职责替换与模型执行方案.md)，对照 reviews/16–17、当前代码（HEAD `6ca48c41`）与真实产物 `doc/features/AR90006`。行号与数字都是本次在盘上核的；未实施、未改方案、未跑 CLI。

## 1. 结论

**可作实施依据，比 2.2-new 干净。** 用户问的"为什么不是删除加替换"在 v3 §2 的表里有了逐职责的答案：每一项新增都指着一个要退出的旧实现，版本协议整套不做，预算从 +240 行变成 −67～+94 行且不预签上限。下面 §2 逐项核过，替换关系在代码里都对得上。

开工前有**三件事要定**（§3），另有几处实施注意要进 A/C 段清单（§4）。

## 2. 替换关系逐项核

| v3 §2 的职责 | 现场证据 | 替换成立吗 |
|---|---|---|
| 逐章作者要求两份 → 留草稿指导区一份 | `story-build.mjs:2111-2140` `chapterDraft` 已往草稿写 `读者要问` / `怎么组织` / 表头 / 提交命令；`hooks/spec/author.mjs:262-290` `chapterSection` 再把十章 questions、form.note、机器核项枚举一遍 | 成立。两处渲染同一份合同，删后者不丢信息；`:289-290` 那句"在章草稿上写"的入口说明按 v3 保留 |
| 只看上一章结尾 → 相关章原文进指导区 | `story-write.md` "怎么写一章"节（`:133`）现只要求回看上一章结尾 | 成立 |
| 七行凭据退场 | `story-build.mjs:65` `COPYEDIT_ROWS`，`:1794-1804` 判行数；`story_flow.py:81` `STORY_SRC_FROZEN` 含 copyedit；`story-build.mjs:197` `STORY_SRC_LEDGERS` 也列它 | 成立，但 v3 §6.3 把 `STORY_SRC_LEDGERS` 写在 story_flow 名下——它在 story-build（见 §4） |
| 审查只给路径、PASS 不写明细 → 全文送达、可附依据 | `reader-review-task.mjs:52`、`:117` | 成立 |
| 结构 PASS ≠ 审查 PASS → `reviewVerdict` | `verifier-report.mjs:238` 对结构完整的非 PASS 判项返回 `status: 'PASS'` | 成立，与 reviews/17 §4 一致 |
| 版本协议不做 | `storyFrozen`（`:226-232`）已在登记后冻结台账指纹；材料指纹归 `story_flow.py round` | 成立，与 v3 §1"现有证据没有证明由材料版本变化造成"一致 |

## 3. 开工前先定的三件事

### D1 · skeleton 在没有流程契约时做什么，v3 没写

v3 §3 写了 `--offline` 拒绝、prepare 缺范围"失败并回原流程"（§4.2 范围行），§4.3 写 skeleton 成功后调同一准备函数——三句合起来，正式路径上 skeleton 会先写骨架与十份草稿、再因缺范围失败，而失败语义没定义。现场：`test_story_build.py` 基类 `setUp`（`:90`）不建 `story-flow.json`，只有 `:835` 一个测试建；`test_image_registration.py` 零处；三个测试文件共 35 处调 `skeleton`。

两种定法：① skeleton 在写入前核流程契约，缺件退出 1 不写（2.2-new 第 140 行的选择）——干净，但 35 处夹具要换到带最小契约的共享 helper；② 骨架与草稿已写视为成功，指导区准备失败按 §5.2 后继失败的同一语义：exit 0、stderr 报"指导区未准备（无流程契约）"、末行 NEXT 给 prepare。**建议 ②**：它与 chapter 的后继失败是同一条规则，不用为 skeleton 另立一种；夹具只在正向样例那一条链上建契约。无论选哪个，写进 §3 并加进 §9.1 的"缺稿恢复"那一行。

### D2 · 只刷新首个待写章，跳章写作时其它草稿的指导区是陈旧的

§4.3：skeleton 后与每次 chapter 成功后准备"下一待写章"，其余待写章的指导区停留在 skeleton 时的"相关章尚未成文"。作者按顺序写没问题；写到第 6 章时先去补第 8 章（真实跑里返修常这样跳），第 8 章的指导区就是旧的。`prepare --chapter` 能救，但 v3 §3 只把它说成"局部返修"用途。

**建议**：每次准备时刷新**全部**待写章的指导区——十个文件、只替换 begin/end 区、作者区不动，成本可忽略；"不得由 prepare 顺带重建所有现有草稿"那句仍成立（重建的是作者区，这里不碰）。这样指导区在任何时刻都反映当前 Story，D1 之外不再需要作者判断"要不要先 prepare"。

### D3 · "作者区逐字节保持"要写明怎么做到——现有草稿是混合行尾

`doc/features/AR90006/AR/story-src/drafts/` 里 01/02/03/04 章草稿分别含 9/16/24/41 个 CR，同一文件里 LF 与 CRLF 并存（脚本写 LF、作者的编辑器写 CRLF）。v3 §4.1 要求刷新时作者区"逐字节保持，包括换行"，又要求按行识别 begin/end——如果实现用 `split(/\r?\n/)` 再 `join('\n')`，作者区的 CR 全部丢失，逐字节承诺当场失效。

**建议**：定位按行（容 `\r`），拼接按字节偏移——只替换 begin 行首到 end 行尾那一段，其余原样。§9.1 "指导区"那一行加一例：混合行尾草稿刷新后，作者区的 sha256 不变。

## 4. 写进 A/C 段清单的实施注意

| # | 现场 | 归段 | 要做什么 |
|---|---|---|---|
| N1 | story-build 目前读 `story-flow.json` 只取 `status` 与 `story_src_digests`（`:227-231`）；"当前已确认范围"的解析语义（`split.decided` / `scope_text` / `parts` / `carrier` / `settled_round`）内联在 `flow-check.mjs:181-230` 的 `flowProblems` 里，没有导出 | A | 从 `flow-check.mjs` 导出一个只读的当前范围读取函数，story-build 引用；不在 story-build 再写一份 split 语义。§4.2 "沿用现有解析语义"指的就是它，方案里点名文件 |
| N2 | `STORY_SRC_FROZEN` 在 `story_flow.py:81`，`STORY_SRC_LEDGERS` 在 `story-build.mjs:197`（不在 story_flow） | C | 两处都要退 copyedit；§6.3 与 §8 C 段的位置写准，免得实施会话在 Python 里找不到那个常量 |
| N3 | `stripGuidance`（`:2500-2504`）按 `l.trim()` 判整行注释；指导区里引用的章原文若含 `<!-- story-build:begin … -->`，加 `> ` 前缀后不再以 `<!--` 开头，会被当正文**保留** | B | §5.2 "先剥指导区、再 stripGuidance"是硬顺序，不是风格；§9.1 "指导区边界"那一行已写"投影标记不泄漏"，点名这一例 |
| N4 | 指导区空行按 §4.1 也加 `> ` | A | 写成单独的 `>`，不留尾随空格 |
| N5 | 预算：scripts_mjs 预计 2491–2556，分类完成上限 2510 | A | v3 §10 已承认可能超分类。与 reviews/16 R1 同：A 段收口时先读数，超了具名回方案，不等 D 段 |

## 5. 不需要再讨论的

- 三份方案的关系：原 02.2 与 2.2-new 头注都已改指 v3，总方案第 5、59、69 行同步，步骤 4 的依赖已记。
- reviews/16 的 R2（体量）、R3（重复是待验假设）、L1（`story_flow.py:871/:971` 两处旧文案）、L4（PASS 附说明可解析）在 v3 §1、§7、§9、§10 各有落点，不重复列。
- 无审查不交付（§7）：政策本身仍待用户批准，机制写法与 reviews/17 一致。

## 本次核对范围

读取 v3 全文；对照 `story-build.mjs`（`chapterDraft :2111`、`stripGuidance :2500`、`cmdSkeleton :2447`、`writeDrafts :2426`、`storyFrozen :226`、`STORY_SRC_LEDGERS :197`、`COPYEDIT_ROWS :65`）、`author.mjs:262-290`、`story_flow.py:81`、`flow-check.mjs:181-230`、`reader-review-task.mjs:52/:117`、`verifier-report.mjs:238`；统计 `test_story_build.py` / `test_image_registration.py` / `test_author_task_package.py` 对 skeleton 的调用与契约夹具；对 AR90006 四份章草稿计 CR 数。

## 复核：v3 11:17 版对上述意见的处理

| 意见 | v3 落点 | 复核 |
|---|---|---|
| D1 skeleton 无契约 | §3 新增段：写入前预检，缺契约 exit 1 且已有文件逐字节不变；夹具用共享 helper | 选了 ① 而非我建议的 ②，理由成立（不为旧夹具加"无契约也成功"的生产分支）。接受 |
| D2 只刷新首个待写章 | §3 / §4.3：保持只刷目标章，跳章先 `prepare --chapter`；§9.1 加跳章用例 | **保留意见**：批量刷新待写章的指导区成本可忽略且不碰作者区；v3 的理由（不宣称始终最新、不能覆盖已完成章返修）成立但不排斥批量刷新。接受其选择，前提是"其它待写章写前先 prepare --chapter"要出现在 chapter 提交成功的 NEXT 行里——那是动作发生点，只写在方法块里等于又回到"只写在提示里" |
| D3 逐字节保持 | §4.1 新增段：Buffer 定位、LF 找行尾容 CR、BOM 留首、切片拼接；§9.1 加混合行尾 hash 不变用例 | 接受 |
| N1 范围读取器 | §4.2：从 flow-check.mjs 导出 `currentScope(flow, featureName)`，`flowProblems` 共用 | 字段核过：`rounds[].positioning.scope_text`、`split.decided/settled_round/scope_text/parts` 都在真实契约里（AR90006）。接受 |
| N2 常量位置 | §6.3 分开写 story-build 与 story_flow | 接受 |
| N3 剥除顺序用例 | §9.1 边界行点名带 `> ` 的 `story-build:begin` | 接受 |
| N4 空行 `>` | §4.1 | 接受 |
| N5 A 段读数 | §10 末段 | 接受 |

v3 另加 §9.3 过拟合自查：只在维护与验收域，不给执行模型加自证清单，与 `AGENTS.md` §8 一致。

结论不变：可进入实施。开工前剩两件归用户：批准 §7 "无独立审查不正式交付"；A 段交回时按 §10 读数决定 scripts_mjs 分类上限是否重签。总方案第 69 行的追溯引用宜改为 reviews/16–18。
