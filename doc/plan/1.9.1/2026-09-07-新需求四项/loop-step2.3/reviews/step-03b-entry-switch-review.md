# step-03b-entry-switch · 评审记录

> 本文件只追加，不改写。记录按事件序号或时间分节。步骤合同见 [../steps/step-03b-entry-switch.md](../steps/step-03b-entry-switch.md)；设计真源是 `../../steps/02.3-02-整篇编排与成文.md` 与总方案 §6 退出清单。

## 2026-09-10 · 激活（executor）

3a 已获批并提交（`c4bb6343`），本步按 `advance` 激活。实施前审视写在下一节。

## seq 49 后 · 实施前审视（executor，3b）

### 已加载路径 → 影响的实施/验收决定

| 路径 | 影响 |
|---|---|
| `steps/step-03b-entry-switch.md` 全文 | 范围＝02 §3–§7 接线 + 总方案 §6 全部退出；落地那一刻只剩一条链 |
| `02.3-02` §3、§4、§5、§6、§7 | 视图与草稿、chapter 检查、prepare 八种状态与输出、接线表、十条完成条件 |
| `02.3-03` §5、§6 | 退出核对清单本步就要满足 |
| `story-build.mjs` 的 `guidanceInputs` / 指导区七函数 / `refreshGuidance` / `writeDrafts` / `cmdSkeleton` / `wholePassOutput` / `prepareNext` / `prepareAfterWrite` / `cmdPrepare` / `cmdChapter` / `chapterDraft` / `chapterSeed` / `renderSlot` / `requiredShapes` / `chapterProblems` / `stripGuidance` | 逐个定去留（下表） |
| `story-chapters.json` 的 `context_chapters` 与 `context_chapters_note` | 删字段与说明键 |
| 02 §6 表的六份文件 + `SPEC_STAGE_ORDER` | 接线与 v3 说法退出 |

### 逐函数的去留 —— 先列清单再动手

| 现有 | 去留 | 依据 |
|---|---|---|
| `guidanceRows` / `relatedChapters` | **退** | 总方案 §6；它们把范围、决策、已写章原文重复灌进每章草稿 |
| `guidanceSpan` / `putGuidance` / `guidanceBlock` / `quoteGuidance` / `stripGuidanceZone` / `bufferLines` / `GUIDE_*` | **退** | §6：输入与输出分离，正文不再承载可刷新指导区 |
| `guidanceInputs` / `refreshGuidance` | **退** | 它们只服务指导区 |
| `prepareNext` / `prepareAfterWrite` / `wholePassOutput` | **退** | §6：改为同一 prepare 入口按磁盘产物给短行动 |
| `methodBlock` 与 story-write 的 `story-method:*` 块 | **退** | 作业书主干换成四段，方法不再靠 stdout 当场投送 |
| `context_chapters` 字段与说明键 | **退** | §6：每个需求的 template 决定真实信息关系 |
| `chapterDraft` / `chapterSeed` / `renderSlot` | **留并改**：种子照旧从真源打（术语表、附录、必要结构），另加 template 的建议标题与 structures 种子 | §3.2「原合同与动态要求合并生成」 |
| `requiredShapes` | **留，改落点**：从指导区改到材料视图 | 合同必要结构仍由 `chapterProblems` 机器核，作者动笔前必须知道它核什么，否则又回到「靠报错学要求」 |
| `chapterProblems` / `chapter --from` / `number` / `project` / `build` / `stripGuidance`（剥 `{{}}` 脚手架）/ `currentScope` | **留** | 步骤文件「关键决定」明列保留 |

### 我打算怎么切，以及为什么这样切

`skeleton` 从「播十份带指导区的草稿」改成两件事：**先按 3a 的分配函数写材料视图**
（`chapters/<章ID>.md` 与 `shared.md`），**再按 template + 合同铺草稿**（只铺形状：
建议标题、structures 种子、合同必要结构、真源打底）。已有草稿一个字节不碰。

`prepare` 不再刷新任何文件，只回答「现在该做什么、去读哪几个位置」。八种状态按 02 §5
的表从磁盘事实派生，`related` 经 3a 的 `relatedTargets` 解析成实际路径。

`chapter` 在既有 `chapterProblems` 之外加一条：本章 template 声明的 structures
在声明位置落实了没有（调 3a 的 `structureProblems` / `locateSection`，不另判）。

**为什么材料视图要带 `requiredShapes`**：合同的必要结构是机器核的，作者动笔前不知道
就只能靠提交被拒才学到——那正是 §4.1 说的「报错不是首次交付规则的渠道」。
它是合同派生的确定性内容，放视图里不占编排的位置。

### 「同类对象 ≥ 2」的反例清单（先列再动手）

上一步的教训：判据对着谁比，只有出现第二个同类对象时才暴露。本步逐条列：

1. **一次 template 修改同时影响两章** → 两章都点名，未受影响的章不出现；两章草稿都不动。
2. **两个 related 目标一个有草稿一个没有** → 各给各的路径（3a 已有函数级证据，本步验接线）。
3. **同一章内两处 structures 声明** → 各自在自己的位置核，互不顶替。
4. **两章都引用同一单元** → 视图里全文只在 shared 一份，两章各给定位。
5. **两份草稿都缺失、其中一章 Story 里已写** → 已写的按现稿补回，未写的按 template 铺。

### 结论：无阻断疑问

一条必要假设：**`requiredShapes` 留下并改落点**。步骤文件的退出清单没点它，
它现在的唯一消费者是要退场的指导区；我判断它承载的是「机器核什么」这条送达义务，
不随指导区退场。若评审认为它该随之退掉、由 `chapterProblems` 的报错承担，我照改——
那是一次删除，不影响别处。

## seq 49 后 · 送审（executor，3b）

### 做了什么

| 落点 | 内容 |
|---|---|
| `skeleton` | 改成消费索引 + 编排：**唯一的正式视图写入口**，写 `chapters/<章ID>.md` 与 `shared.md`，再按编排与合同铺草稿（已有草稿一个字节不碰）；编排改了报哪几章变了 |
| `prepare` | 改成 NEXT/INPUT/RESULT 短输出，按 02 §5 的八种状态从磁盘事实派生动作，`related` 解析到实际路径；**不改任何文件** |
| `chapter` | 加「本章编排声明的结构在声明位置落实了没有」（调 3a 的函数，不另判）；最后一章落盘时首屏就是写后核对 |
| 六份提示词 | `story-write.md` 主干换成四段（初筛 → 整篇编排 → 按编排成文 → 写后核对），「编排调整规则」只定义一次；`spec.md` 阶段内顺序、`SKILL.md` 链条与路由、`author.mjs` 的成文入口、`author.md`、`story_flow.py` 的接续文案 |
| `story-chapters.json` | 删 `context_chapters` 与它的说明键（version 4.3）；**按原格式只删该删的行**——我第一版用 `json.dumps` 重排了整份文件，那不是我的改动，回滚重做 |
| 退出 | `guidanceRows` / `relatedChapters` / `guidanceSpan` / `putGuidance` / `stripGuidanceZone` / `quoteGuidance` / `guidanceBlock` / `bufferLines` / `GUIDE_*` / `methodBlock` / `METHOD_MARKS` / `guidanceInputs` / `refreshGuidance` / `prepareNext` / `prepareAfterWrite` / `wholePassOutput` / `story-method:*` 标记 |
| 测试 | 新建 `test_entry_switch.py`（17 例）；`test_writing_flow.py` 退掉六组 v3 用例并按新链改写；新建共享夹具 `orchestration_fixture.py`，四处工作区接上 |

### 一处我补的缺口

**范围原来靠指导区送达，指导区退了它不能跟着退。** `assemblyInputs` 现在读流程契约取
本 AR 当前范围（判据与阶段门禁同源），范围没定就一个字节不写；视图开头第一行就是
「本 AR 当前承载」，切分时连兄弟单据承载什么一起给。
`SkeletonReadsBeforeItWrites` 那六条既有用例因此原样存活。

顺带修了一个我自己写出来的 bug：兄弟单据渲染成了 `[object Object]`——`siblings`
是对象数组不是字符串数组。既有用例当场抓到。

### 一处判据我改了落点

**已选的结构也写进材料视图**（原来只铺进草稿）。起因是「一次编排修改同时影响两章」
那条用例：改 `structures` 时视图不变，差异判据看不见它。补进视图之后两件事一起解决——
差异看得见了，作者也终于能在读材料时看到「这是我自己选的形式，它会在这个位置被核」。

### 编排差异不另存快照

02 §3.2 要报「编排改了哪几章的什么」。我本来打算存一份 `.plan-snapshot.json`，
写到一半改了：**盘上那一份旧的材料视图就是「上次是什么样」**。存快照的话，
快照与视图各记一次同一件事，对不上时没人说得清该信哪一份。现在比的是新旧视图。

### 验收逐项

| 验收项 | 结果 |
|---|---|
| 同一单元两个编排项引用 / 一个 / 无人引用 | 公共材料里只有一份全文、两章各拿到定位；单引用进所属章；其余只给索引行 |
| **一次 template 修改同时影响两章** | 两章都点名、未受影响的章不出现、三份草稿字节不变 |
| 声明 sequenceDiagram 交 flowchart / 表缺列 / 图片放到另一节 | 三种都在当前节提交被拒并报出编排坐标（`05-flow/body` 这样） |
| 未声明结构的建议标题改了名 / 正文新增编排没列的小节 | 都通过，不拦 |
| 最后一章提交的 stdout | 首屏第一行 `NEXT: 十章都有正文了，做写后核对：…`，写作设计的位置在 INPUT 里 |
| prepare | 不改任何文件（逐字节比对整棵树）；视图未建时指向 skeleton；编排没填完时指向 after-spec 并点名是哪一处；`related` 一个有草稿一个没有时各给各的路径 |
| 视图 | 开头是本 AR 当前承载；写明自己是工作输入不是内容上限 |
| 退出核对 | 15 个 v3 标识符在 `doc/extensions` 全部零命中（用例逐个 `git grep`）；合同里已无 `context_chapters` |
| 端到端 | 金样输入跑通 before-spec → 初筛 → after-spec → 编排 → skeleton（11 份视图 + 10 份草稿）→ prepare |

### 四道门

| 门 | 结果 |
|---|---|
| 离线全量 | **908 passed, 6 skipped**，0 failed |
| 失效形态 | **70 条 FAIL 0** |
| adapt-scan | 退出 0 |
| framework | 0 行 |

### 规模：**本步是净增，不是净减** —— 按总方案 §7 请专项审视

| 类别 | 3a 末 | 现在 | 本步净 |
|---|---:|---:|---:|
| scripts_mjs | 3700 | 3753 | **+53** |
| prompts_md | 1815 | 1847 | +32 |
| hooks_mjs | 3013 | 3017 | +4 |
| scripts_py | 1737 | 1738 | +1 |
| data | 752 | 742 | **−10** |
| **总量** | **11017** | **11097** | **+80** |
| 同范围完整字符量 | 552664 | 554777 | +2113 |

**退出量是有的**，逐文件按代码行（注释与空行不计）：

| 文件 | 加 | 退 | 净 |
|---|---:|---:|---:|
| `story-build.mjs` | 359 | **310** | +49 |
| `story-write.md` | 57 | 34 | +23 |
| `story-chapters.json` | 1 | 12 | −11 |
| 其余六份 | 45 | 36 | +9 |
| 合计 | 462 | **392** | +70 |

**说清楚这 392 行退在哪、+80 从哪来**：v3 那条链是「一个渲染器把七类输入拼成一段文字，
写进每份草稿的头部，再按字节刷新」。新链做的是它没做过的事——按编排把材料分配到十份
视图与一份公共材料、八种状态的下一动作派生、已选结构的生成与在声明位置的检查、
新旧视图的差异归类。**换掉的那件事比被换掉的那件事做得多**，所以退了 392 行仍是净增。

**按总方案 §7 的四问自审**（结论交评审复核）：

1. **旧职责是否真正删除**——是。15 个标识符在 `doc/extensions` 零命中，有用例逐个 `git grep` 守着；
   `story-chapters.json` 的字段与说明键一起删掉。不存在换名保留的第二套作者输入。
2. **是否同一判据多处维护**——没有。结构检查只有 `structureProblems` 一处，
   `chapter` 与将来的最终 check 调同一个；`norm`/`tableHeaders` 在 3a 已收成一份。
3. **是否保留旧链再加分支**——没有。落地那一刻只剩一条链：`skeleton` 是视图的唯一写入口，
   `prepare` 不写盘，v3 的刷新路径整条不在了。
4. **新增工作是否确实降低重复理解与返修**——**这一条我证明不了**。它是行为问题，
   要真实 CLI 跑出来看：同一批原文不再被十份草稿各灌一遍、编排一次定归属之后返修少不少。
   在那之前，我只能如实说「静态上是净增」。

**2.3 累计**：scripts_mjs 2825 → 3753（**+928**），总量 9942 → 11097（**+1155**），
而总方案 §7 的估算是完成时 9772–10432。**差得很远，这不是估算误差的量级。**
我不自己压、也不裁功能（§7.5 明令），把事实与上面的四问自审交评审与用户判断：
要么承认 2.3 的实际形态比方案设想的大，要么有一整块该退而没退的东西我没看见。
我看不到后者——退出清单逐项核过了，但那正是我该被复核的地方。

### 提交边界与剩余限制

- 将纳入：`story-build.mjs`、`story-sources.mjs`、`story_flow.py`、`story-chapters.json`、
  `SKILL.md`、`phases/spec.md`、`phases/story-write.md`、`hooks/spec/author.mjs`、`author.md`、
  `flow-check.mjs`；测试 `test_entry_switch.py`（新）、`test_writing_flow.py`、
  `test_story_build.py`、`test_author_task_package.py`、`test_image_registration.py`、
  `orchestration_fixture.py`（新）。
- 不带：工作区里他人的未提交改动；`98` 与本目录。
- 剩余限制：① 真实 CLI 未跑——新链一次也没有被真的作者走过，行为待验；
  ② 03 分册的最终 check 条件、verifier 输入、冻结名单仍在 step-04；
  ③ 02-N1（`DERIVED_KEYS` 读合同）本步没做——`derived` 在合同里的既有语义是
  「模板生成的中间产物」而 `sources_note` 明写 design 不声明它，改它会与那句话冲突；
  我留了原样并把这条理由写在这里，请评审裁定是改合同语义还是维持硬编码。
- 本步问题反思：我一开始想给编排差异存一份快照文件，写到一半才想起「上次是什么样」
  盘上已经有了。**加一份记录之前，先找现有产物里有没有同一件事的记录**——
  两份记录一旦并存，它们迟早会不一致，而那时没有第三个人能裁决谁对。

## seq 52 · 评审（reviewer，3b）

### 独立核对

| 项 | 本次亲跑 | 与送审自述 |
|---|---|---|
| 离线全量 | 908 passed / 6 skipped / 219 subtests，0 failed | 一致 |
| 失效形态 / adapt-scan / framework | 退出 0 / 退出 0 / 0 行 | 一致 |
| `measure()` | scripts_mjs 3753、prompts_md 1847、hooks_mjs 3017、scripts_py 1738、data 742，总量 11097 | 一致 |
| 退出核对 | 我自己按 15 个标识符逐个扫 `doc/extensions`：`guidanceRows` / `relatedChapters` / `guidanceSpan` / `putGuidance` / `stripGuidanceZone` / `quoteGuidance` / `guidanceBlock` / `bufferLines` / `GUIDE_` / `methodBlock` / `METHOD_MARKS` / `story-method` / `story-author:` / `guidanceInputs` / `refreshGuidance` / `prepareNext` / `prepareAfterWrite` / `wholePassOutput` / `context_chapters` **全部 0** | 一致 |
| 合同 | `story-chapters.json` 无 `context_chapters` 与说明键，按原格式只删该删的行（未整份重排） | 一致 |
| 用例覆盖 | 读了 `test_entry_switch.py` 五个类：两处引用共享一份、一次编排改动点名两章且第三章不出现、三种结构声明在声明位置被拒、建议标题改名与新增小节不拦、prepare 逐字节不写盘、related 一个有草稿一个没有 | 「同类对象 ≥ 2」的清单确实逐条落成了用例 |
| 端到端 | ChainCase 走通 before-spec → 初筛 → after-spec → 编排 → skeleton → 十章 chapter → prepare | 一致 |

`assemblyInputs` / `writeViews` / `draftBody` / `cmdPrepare` / `declaredStructureProblems` 逐段读过。范围从指导区改由 `scopeOf` 取流程契约、判据与阶段门禁同源，是对的补法；「不另存编排快照、拿盘上旧视图比」也对——两份记录并存迟早不一致。

### 强制返修

| 编号 | 需求依据 | 真实错误及证据 | 强制结果 | 复验方法 |
|---|---|---|---|---|
| **3b-R1（P2）** | 02 §4：已声明 structures 在声明位置落实是 `chapter` 提交前要拦的机械事实；02 §5 谓词分两层，「可装配」的用途是能不能据它铺材料与草稿，不是能不能核结构 | `declaredStructureProblems` 开头 `const ready = assemblyInputs(ctx); if (ready.problems.length \|\| !ready.template) return [];`——编排只要装配不起来，本章声明的结构就**一条也不核，且不说一个字**。实测：`01-background` 声明 mermaid sequenceDiagram、正文里没有图，编排可装配时 `rc=1` 报「声明的图不在」；随后把**另一章**的 sources 改成 `PRD#9999`（编排变成读得出但装配不起来），同一份正文再提交 → **`rc=0`，story.md 被写入，stdout 首行照常给下一章**。basis 过期同理。也就是说一处无关的引用错误，会让全部十章的结构检查一起消失 | 结构检查只依赖「编排读得出」：`templateReadable` 通过就照常核（`assemblyInputs` 在装配失败那一支已经把 `index` 与 `template` 返回出来了，够用）。编排连读都读不出来时，报「编排读不出来，本章声明的结构无法核」并拦住，不返回空数组 | 新用例：把别章 sources 改成不存在的单元 → 本章缺声明的结构仍 `rc=1` 且报出该结构与编排坐标；编排 json 块坏掉 → `rc=1` 且报「读不出来」；既有 `test_a_flowchart_where_a_sequence_was_declared_is_refused` 等三条仍绿 |
| **3b-R2（P3）** | AGENTS §5.3 交付面只留当前在用的；总方案 §6「归属和规模写回反馈，不能只给删除文件数」 | `writeDrafts` 改调 `draftBody` 之后，`chapterDraft`（story-build.mjs:2658，23 行）**在 `doc/extensions` 里只剩定义、零调用**（基线 `0a177cf2` 是 2 处，现在 1 处）。另有 `declarationProblems` 被 import 进 story-build.mjs（:51）却没有任何调用者。两处都是本步产生的 | 删 `chapterDraft` 与那个 import；顺带核一遍本步改动波及的其它函数还有没有同类（`carryableBlock` 与 `IDENTIFIER_SHAPE` 在基线就只出现一次，是既有问题，本步不必处理） | 再跑一次「只出现一次的标识符」扫描，本步新增的为零；离线全量仍绿 |
| **3b-R3（P3）** | AGENTS §8 完成前自检「本轮目标与保护项都已检查：原有关键能力是否保持」 | `test_writing_flow.py` 退掉的六个类里，`TestFinalPassIsInTheFlow` 有两条**与 v3 机制无关**的守恒断言：① 统稿一节必须含三个动作与七项归并进来的义务（逐字 / 引导 / 承接 / 独立读懂 / 指得出依据 / 四处对着读 / 起草过程的痕迹）；② `spec.md` 的阶段内顺序里「按章写 → 统稿 → 登记」的先后。它们守的是**内容不被下一次改写悄悄丢掉**，不是指导区。我核过：十项在改写后的「第四步 · 写后核对」里全都还在，`spec.md` 的 ④ → ④b → ⑤ 顺序也对——**但现在没有任何测试守它们**（全仓仅命中一个陈旧 `.pyc`） | 按新形态把这两条接回来：第四步一节含三个动作与七项义务、`spec.md` 里 ④ 按章写 < ④b 写后核对 < ⑤ 登记。不恢复 `story-method` 标记——那是 v3 的送达机制，退场是对的 | 两条新用例；故意从 story-write.md 第四步删掉「四处对着读」应当红 |

### 02-N1 裁定：维持硬编码，补一句注释

`DERIVED_KEYS` 与合同的 `derived` 不是同一件事，各有各的消费者：合同那个判**落点义务**（这一份是本轮生成的中间产物，标识名与工程数值不必在 story 里找地方），`sources_note` 明写 design 不声明它；来源索引这个判**权威性**（提取稿不能顶替它自己盖掉的上游原话）。让一个字段同时承担两种判断是错的。**维持硬编码**，在 `DERIVED_KEYS` 上补一句说明它与合同 `derived` 判的不是同一件事——否则下一个维护者会以为这里漏读了合同。随 R1–R3 一起改。

### 规模：专项审视结论

用户 2026-09-10 裁定「不降/净增须专项审查旧职责是否退出、是否叠加补丁」。我按 `code_lines` 逐文件独立测过：

| 文件 | `0a177cf2` | 现在 | 净 |
|---|---:|---:|---:|
| `story-build.mjs` | 2005 | 2450 | +445 |
| `story-sources.mjs` | 0 | 483 | +483 |
| 其余四份 core mjs | 820 | 820 | 0 |
| **scripts_mjs** | **2825** | **3753** | **+928** |
| **总量** | **9942** | **11097** | **+1155** |

对照总方案 §7 的完成估算 9772–10432，超出上限约 665 行。四问的独立结论：

1. **旧职责真退了**——15 个标识符零命中是我自己扫的，不是读它的自述；`story-build.mjs` 内部退掉约 310 行指导区机器。**唯一的例外是 R2 那 23 行死代码**，量小但性质就是「该退没退」，执行者说自己看不见的正是它。
2. **没有同一判据两处维护**——结构检查只有 `structureProblems` 一处，`chapter` 与将来的最终 check 调同一个；`norm` / `tableHeaders` 在 3a 已收成一份；漂移判据只有 `staleSources` 一处。
3. **没有保留旧链再加分支**——`skeleton` 是视图唯一写入口，`prepare` 不写盘（用例逐字节比对整棵树），v3 的刷新路径整条不在。
4. **新增能不能换来更少的重复理解与返修**——同意执行者的说法：这一条静态证明不了，归 03 §7 的真实运行。

**我的判断：这是估算与实际形态的差距，不是叠加补丁。** 逐块追下来，来源索引与漂移/接受、有效取舍合并、structures 三种的生成与检查、材料分配、八状态派生、两层谓词，每一块都能指到 01/02 分册的明写条款，没有一块在替模型做判断，也没有第二份同义真源。§7 那个区间是按「新增必要输入整理能力并替换作者流程」一句话估的，没有分解到这些块——所以它偏小。**这不构成 3b 的返修项**：按 §7.5，方案估错要回方案改估算，不是砍实现。

**交用户在 2.3 收口时裁定的是**：承认 2.3 的实际形态就是这个量级（那时按现值重定 target 并移除 `interim_ceiling: null` 例外），还是把「机制变小」另开一轮需求。若走后者，我会先看两处：`viewDrift` 现在靠正则回读渲染出来的视图文本判差异，改成直接比 `assign` / `effective` / `template` 这三份结构化数据更短也更准；`chapterLead` 把编排的 content/form 抄进视图，而视图同时又把 `story-template.md` 列为 INPUT，同一份内容读者会看到两遍。两处都不是本步该动的。

**本轮结论：changes_requested。** R1 是一条机械检查会因为无关输入而整体消失（已实测到 `rc=0` 且产物被写入），R2 是死代码，R3 是守恒断言随 v3 用例一起被退掉。三条都不改设计。

## seq 55 后 · 返修送审（executor，3b）

沿用 `3b-R1`–`3b-R3` 编号。三条都先确认了红再改。

### 3b-R1 → 最终修改位置 → 验证及实际结果

**洞成立，而且是这一步里最要紧的一条**：`declaredStructureProblems` 拿
「编排装配得起来」当前提，于是别的章一个引用写错，**这十章的结构检查一条也不核、
一个字不说**——而作者手上这一章的正文什么都没变。

根因是我把两层谓词的用途混了：「可装配」回答的是**能不能据它铺材料与草稿**，
不是能不能核结构。核结构只需要「读得出来」。

最终修改在 `story-build.mjs` 的 `declaredStructureProblems`：

- 前提换成 `templateReadable`；`index` 单独读，读不到就按空索引走（结构声明本身仍核）；
- **读不出来时不返回空数组**，报「整篇写作设计读不出来（…），本章声明的结构核不了」
  并拦住——这条检查做不了的时候要说出来，不是当作过了；
- 编排文件根本不存在时返回空：那时没有声明过的结构，不是漏检。

用例两条（都先确认改前绿、改后红）：

| 用例 | 实际结果 |
|---|---|
| `test_an_unrelated_broken_reference_does_not_switch_the_check_off` | 先确认编排可装配时能拦住（否则这条用例没有对象）；再把**另一章**的 sources 改成 `PRD#9999` → 同一份正文仍 `rc=1`，报出 `01-background/body` 与「图不在」 |
| `test_an_unreadable_plan_is_reported_not_silently_passed` | 编排里塞第二个 json 块 → `rc=1`，报「读不出来」 |

既有三条（flowchart 顶替 sequenceDiagram、表缺列、图片错节）仍绿。

### 3b-R2 → 最终修改位置 → 验证

`chapterDraft`（34 行连注释）在 `writeDrafts` 改调 `draftBody` 之后零调用者，删掉；
`declarationProblems` 被 import 进 `story-build.mjs` 却没有调用者（它的消费者在
`story-sources.mjs` 内部），去掉那一项 import。两处都是本步产生的，不是既有问题。

**你点的这一处正是我说「看不见」的那一块**——量小，但性质就是「该退没退」。
我自审时只逐项核了退出清单里**列名的**那些，没有反过来问「本步改动之后，
还有谁失去了唯一的调用者」。这两件事不是同一个动作。

### 3b-R3 → 最终修改位置 → 验证

新增 `TheFinalPassKeepsWhatItAbsorbed`（2 例）：

- 第四步那一节含三个动作与并进来的七项义务（逐字 / 引导 / 承接 / 独立读懂 /
  指得出依据 / 四处对着读 / 起草过程的痕迹），逐项 subTest；
- `spec.md` 里 ④ 按章写 < ④b 写后核对 < ⑤ 登记。

**做了突变核对**：把 story-write.md 第四步的「四处对着读」改成「四处对照」→
该 subTest 当场红；改回去 → 绿。不恢复 `story-method` 标记——那是 v3 的送达机制。

### 02-N1 → 按你的裁定补了注释

`DERIVED_KEYS` 维持硬编码，注释写清它与合同 `derived` 判的是两件事：这里判**权威性**
（提取稿不能顶替它自己盖掉的上游原话），合同那个判**落点义务**。
第一版我写成了「不要去读那一个」——**失效形态当场判它以错误为参照**（AGENTS §5.3），
改成两种判断各说各的正面表述。

### 四道门（改后）

| 门 | 结果 |
|---|---|
| 离线全量 | **912 passed, 6 skipped**，0 failed |
| 失效形态 | **70 条 FAIL 0**（中途报过我自己那一句，已改） |
| adapt-scan | 退出 0 |
| framework | 0 行 |

### 规模

| 类别 | 上次送审 | 现在 | 本次返修 |
|---|---:|---:|---:|
| scripts_mjs | 3753 | 3743 | **−10** |
| 其余四类 | — | 未动 | 0 |
| **总量** | **11097** | **11087** | **−10** |
| 同范围完整字符量 | 554777 | 554223 | −554 |

R2 删掉的 34 行连注释里代码行是 22；R1 的新判据 +12。

### 你那两条「若另开一轮该先看哪里」我收下了

`viewDrift` 靠正则回读渲染出来的视图文本判差异——比 `assign` / `effective` / `template`
三份结构化数据更长也更容易误判；`chapterLead` 把编排的 content/form 抄进视图，
而视图同时把 `story-template.md` 列为 INPUT，同一份内容读者看两遍。
两处都不是本步该动的，我记在这里，2.3 收口时若走「机制变小」那条路，从它们开始。

### 本轮反思

R2 指出的那 22 行，是我自审时的一个盲区：我逐项核了退出清单里**列名的**那些，
但没有反过来问「本步改动之后，还有谁失去了唯一的调用者」。
**「清单上的都退了」与「没有新的死代码」是两个方向的检查**，只做前一个，
新产生的孤儿就永远查不出来——而它们正是下一轮「机制怎么又大了」的来源。

## seq 58 · 返修复核与 closeout（reviewer，3b）

### 独立核对

| 项 | 本次亲跑 | 与送审自述 |
|---|---|---|
| 离线全量 | 912 passed / 6 skipped / 229 subtests，0 failed | 一致 |
| 失效形态 / adapt-scan / framework | 退出 0 / 退出 0 / 0 行 | 一致 |
| `measure()` | scripts_mjs 3743，总量 11087（较上次 −10） | 一致 |
| **3b-R1** 用我上一轮的探针原样重跑 | 声明 mermaid 时序图而正文无图：编排可装配时 `rc=1`、story 未写入；把**另一章** sources 改成 `PRD#9999` 之后同一份正文仍 `rc=1`、story 仍未写入（上一轮这里是 `rc=0` 且已写入） | 洞已闭合 |
| **3b-R2** 死代码复扫 | `story-build.mjs` 里只出现一次的标识符只剩 `IDENTIFIER_SHAPE` 与 `carryableBlock`（两者基线即如此，非本步产生）；`chapterDraft` 已删、`declarationProblems` 的 import 计数归零 | 一致 |
| **3b-R3** 两条断言各做一次突变核对 | 把 story-write.md 第四步的「四处对着读」改成「四处对照」→ 该 subTest 当场 SUBFAILED；把 spec.md 的 `④b 写后核对` 改成 `④c` → 顺序断言 FAILED；两处还原后各自回绿 | 两条都有区分力，不是摆设 |
| 02-N1 注释 | 读过：两种判断各说各的正面表述（权威性 / 落点义务），没有以「不要去读那一个」为参照 | 一致；执行者自己被失效形态判了一次并改对，处置正确 |

R1 的改法比我要求的更完整：编排文件不存在时返回空（那时没有声明过的结构，不是漏检），读不出来时报出来并拦住，读得出来就照常核。三条既有反例仍绿。

3b-R1～R3 关闭。

### closeout（3b）

- 最终设计：`skeleton` 是材料视图的唯一写入口，按 3a 的分配函数写十份章视图与一份公共材料，再按编排与合同铺草稿（已有草稿一个字节不碰），并把新旧视图的差异按来源分配 / 编排项 / 阅读重点三类报出来；`prepare` 只回答不写盘，按磁盘事实派生八种状态与要读的位置，`related` 解析成实际路径（有草稿给草稿，没有给该章视图并说明）；`chapter` 在合同必要结构之外，按编排声明的位置核已选结构，前提只是「编排读得出」，读不出来就说出来而不是当作过了；本 AR 当前范围改由流程契约取，判据与阶段门禁同源，写进视图第一行；六份提示词按 02 §6 表接线，story-write.md 主干换成四段并把「编排调整规则」只定义一处；`context_chapters` 字段与说明键退场。v3 那条链的 19 个标识符在交付面零命中。
- 实际修改：`story-build.mjs`（+445 净，退出约 310）、`story-sources.mjs`（`sharedView` 收未分配来源）、`story_flow.py`、`story-chapters.json`、`SKILL.md`、`phases/spec.md`、`phases/story-write.md`、`hooks/spec/author.mjs`、`author.md`、`flow-check.mjs`；测试新建 `test_entry_switch.py`（21 例）与共享夹具 `orchestration_fixture.py`，`test_writing_flow.py` 退掉六组 v3 用例并按新链改写，另三份测试随流程更新。
- 验证：两轮评审的核对表；R1 用真实工作区端到端探针、R3 用两次突变核对。
- 剩余限制：① **真实 CLI 未跑，新链一次也没有被真的作者走过，行为待验**；② 03 分册的最终 check 条件、verifier 输入重定、冻结名单扩展仍在 step-04；③ 若 2.3 收口后另开「机制变小」一轮，先看 `viewDrift`（改成比结构化数据而不是回读渲染文本）与 `chapterLead`（编排内容在视图与 template 里各出现一次）。
- 规模：2.3 累计 scripts_mjs 2825 → 3743（+918），总量 9942 → 11087（+1145），对照总方案 §7 完成估算 9772–10432 超出上限约 655 行。**专项审视结论见 seq 52 那一节**：旧职责真退了（本步补删的 22 行死代码是唯一例外，已闭合）、无同一判据两处维护、无保留旧链再加分支、每一块都能追到分册明写条款且没有替模型做判断——是估算与实际形态的差距，不是叠加补丁。是否承认这个量级并按现值重定 target、移除 `interim_ceiling: null` 例外，交用户在 2.3 收口时裁定。
- 本步问题反思：三条返修各指向一类自审盲区。R1 是把两层谓词的用途混了，让一条机械检查依赖了它并不需要的前提——**判断吃了它不需要的东西**，与 3a 那次同源。R2 是「清单上的都退了」与「没有新的死代码」被当成同一个检查，只做了前一个；这两个方向的差别值得写进后续步骤的自审。R3 是退用例时按「这个类叫什么」而不是「这条断言守的是什么」来判去留，把两条与 v3 无关的内容守恒断言一起退掉了——内容这次侥幸没丢，但守它的人没了。

**批准提交。** 纳入送审说明列出的那批文件；不带工作区里他人的改动。提交后 `advance --step-id step-04-verify-and-retire --step-file steps/step-04-verify-and-retire.md`。
