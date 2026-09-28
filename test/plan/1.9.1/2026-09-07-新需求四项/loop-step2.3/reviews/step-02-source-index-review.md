# step-02-source-index · 评审记录

> 本文件只追加，不改写。记录按事件序号或时间分节。步骤合同见 [../steps/step-02-source-index.md](../steps/step-02-source-index.md)；设计真源是 `../../steps/02.3-01-原材料与初筛.md` §2–§7。

## 2026-09-10 · 激活（executor）

step-01 已获批并提交（`eda9c282`），本步按 `advance` 激活。实施前审视写在下一节。

## seq 15 后 · 实施前审视（executor）

### 已加载路径 → 影响的实施/验收决定

| 路径 | 影响 |
|---|---|
| `steps/step-02-source-index.md` 全文 | 范围＝01 分册 §2–§7（S4 除外）；不实现 collect、不生成 Spec 前视图；v3 作者链照常运行是允许的中间态 |
| `../../steps/02.3-01-原材料与初筛.md` §2–§7 | 本步全部合同：文件所有权、切法、source-index / selection 形状、`basis` 与 `--accept-source`、NEXT/INPUT/RESULT、验证六条 |
| `../../steps/02.3-02-整篇编排与成文.md` §1、§2、§5 | 下一步的消费者需求：after-spec 只补新增来源、初筛的 `chapters` 要能预填 `body.sources`、「selection 可读」谓词的字段级定义 |
| `../../steps/02.3-Story写作流程重设计.md` §4、§6、§7 | 脚本不判来源重要性；规模按类别如实记；本步只加不退 |
| `story-build.mjs`（`COMMANDS`、`cmdInit` 的 decisions 骨架、`materialImages`、`joinPosix`、`relFromStory`） | 新命令挂载点；decisions 初始化前移；图片登记与相对路径已有能力，复用不重写 |
| `materials.py`（`SOURCE_DOCS`、`file_digest`、`build().sources`） | MJS 摘要口径＝原始字节 SHA-256 前 16 位 + `sha256:` 前缀，要与它逐字节一致 |
| `story_flow.py`（`spec_stage_step`、`contract.design.origin`） | complete 之后第一句改成「跑 sources before-spec」；`status` 只给阶段级动作，不起 Node |
| `contracts/story-chapters.json` `sources` 与章 ID | 已知来源沿用合同 key；selection 的 `chapters` 值域取十章 ID |
| `test/story/fixtures/golden/AR90006-template/` + `golden/story-template-金样-AR90006-source-index.json` | 切片的确定性验证输入与期望；两处结构性差异见下 |
| `golden/story-template-金样-AR90006-source-selection.json` | 稀疏 selection 的对照形态 |

### 两处与金样索引的结构性差异（先说清，再按本期规则核）

金样索引是**人工整理的 after-spec 快照**，按 03 §6 末段不直接当算法答案：

1. **它含 SPEC 的 37 个单元**，而本步只做 before-spec（01 §3：before-spec 含原始来源与 AR 派生稿，
   after-spec 才加 Spec）。所以逐项核的对象是 PRD/SE/AR_ORIGINAL/DESIGN 四源共 28 个单元。
2. **它的单元范围含首尾空行，而 `context` 范围不含**（`SE#1` 是 `2..4` 而同一段作为
   `SE#2.context` 是 `3..3`；`PRD#1` 是 `8..12` 而作为 context 是 `9..11`）。
   我按 01 §3 的「正文起止行」取**两端都去空行**，一条规则同时用于单元与 context——
   同一段文字在两个位置给出两个数字，下游没法解释哪个是它的范围。
   预期结果：`context` 与金样逐项相同，单元 `start/end` 各向内收 1 行（有空行填充时）。
   这一类差异在送审说明里按源逐条列出，不改金样正本。

### 验收项 → 修改落点 → 验证方法 → 越界/疑问

| 验收项 | 修改落点 | 验证方法 | 越界/疑问 |
|---|---|---|---|
| 金样四源逐项对得上（标题路径、行范围、images） | `story-sources.mjs` 的切片与图片派生 | 以 fixture 为输入的确定性用例，差异按上面两类逐条报 | 见上 |
| 围栏内假标题 / 同名标题 / 无标题文件 / 父级前导表格 | 同上 | 自造中性样例用例 | 无 |
| selection 七种形态（两通过五拒绝） | `story-build.mjs` 的 selection 校验 | 新用例 | 无 |
| 改一个源后的重定位报告与 `--accept-source` | `story-build.mjs` 的源变化路径 | 新用例 | 无 |
| 视图构建函数（相对链接、公共正文一份、未分配只给索引行） | `story-sources.mjs` 的视图函数 | 函数级用例（正式落盘接线在 step-03） | 无 |
| complete 之后 `status` 指向 sources | `story_flow.py` `spec_stage_step` | 用 `test_s4_commit` 的驱动加一例 | 无 |
| decisions 初始化前移 | `story-build.mjs` | 新用例 + 既有 writing_flow | 无 |
| 四道门与规模 | — | `TEST.md` §7；`measure()` 拆到函数级 | 无 |

### 结论：无阻断疑问

三条必要假设：

1. **单元与 context 用同一条去空行规则**（理由见上）。
2. **`AR_ORIGINAL` 的路径从流程契约 `design.origin` 取**，不靠在 `sources/ar/` 下按文件名算轮次——
   step-01 已经把它记成显式指针，正是为了这里。`origin` 为 null（本轮 AR 是空骨架或沿用）时，
   该源不进索引，不编造一个来源。
3. **视图构建函数本步只导出、不接线**：`skeleton` 的正式写入是 step-03 的唯一入口（02 §3.1），
   本步接了就出现第二条写入路径。

## seq 15 后 · 送审（executor）

### 做了什么

| 落点 | 内容 |
|---|---|
| 新建 `core/story-sources.mjs`（162 行代码） | `splitUnits` 切内容单元、`sliceRange`、`unitId`/`parseUnitId`、`sourceDigest`、`refsIn`、`retarget`、`relocate`、`chapterView`/`sharedView`。只解析与装配，不做取舍 |
| `story-build.mjs` `sources` 命令（+253） | `--stage before-spec`、`--accept-source`、索引与初筛骨架落盘、来源变更报告、NEXT/INPUT/RESULT；`ensureDecisions` 从 `cmdInit` 提出来，两处共用 |
| `story_flow.py`（+10） | `spec_stage_step` 头上加 `index_sources` 一步（带进 spec 的授权）；`SPEC_STAGE_ORDER` 的顺序把初筛排在最前 |
| `SKILL.md`（+2）、`phases/story-write.md`（+16） | 链条加 S4b、路由表加一行；story-write 新增「进 spec 之前：初筛一次」一节 |
| `test_source_index.py`（新建，41 例） | 切法七例、短 ID 与摘要三例、金样逐项、初筛九例、来源变更三例、视图三例、流程两例、决策容器三例、输出三例 |
| `test_s4_commit.py` / `test_author_task_package.py` | 两条既有断言随流程更新（见下「改了两条既有断言」） |

### 金样逐项核对的结果

拿 `fixtures/golden/AR90006-template/` 装工作区跑 `sources --stage before-spec`，
与 `golden/story-template-金样-AR90006-source-index.json` 逐项比：

| 项 | 结果 |
|---|---|
| 单元数 | PRD 10 / SE 6 / AR_ORIGINAL 3 / DESIGN 9 = **28，四源逐源相同** |
| 标题路径 | **28/28 相同**（含同名标题各自的祖先路径） |
| `context`（上级前提） | **28/28 相同** |
| 行范围 | **28/28 各向内收空行填充**（我按 01 §3「正文起止行」两端去空行；金样的单元范围含首尾空行而它自己的 `context` 不含。同一段文字不能有两个范围，故取一条规则） |
| `images` | 金样列的 5 张，`id` 与 `source` **逐张相同**（都指向首次出现它的单元） |
| SPEC 的 37 个单元 | 不在本次索引里——before-spec 时本轮规格还没写（01 §3） |

**一处金样与夹具对不上，报给评审**：金样索引里 `PRD` 的 `digest` 是
`sha256:a5b234d89394e14a`，而夹具 `RR/prd.md` 当前字节算出来是 `76210865b2d11671`；
把该文件按 CRLF 渲染后正好得到金样那个值（SE / DESIGN / AR_ORIGINAL 三份则是 LF 值、逐个相同）。
即金样索引成文时 `prd.md` 在盘上是 CRLF。这说明**材料版本随 checkout 的行尾设置而变**——
`materials.file_digest` 本来就按原始字节算，我的 MJS 摘要与它逐字节一致（用例
`test_the_digest_matches_the_material_ledger` / `test_a_bom_or_crlf_file_still_agrees` 锁住）。
要不要让材料版本对行尾免疫，是 `materials.py` 的轮次语义问题，不在本步边界内，先记在这里。

### 三条假设的落实

1. **单元与 context 同一条去空行规则** —— 已实现并有用例
   （`test_ranges_do_not_include_blank_padding`）。差异如上表，逐类可解释。
2. **`AR_ORIGINAL` 从 `design.origin` 取** —— `test_the_kept_upstream_is_found_through_the_contract`；
   `origin` 为 null 时该源不进索引（`test_without_a_kept_upstream_no_source_is_invented`），不编造来源。
3. **视图函数只导出不接线** —— `test_no_chapter_views_are_written_yet` 锁住 `chapters/` 不生成。

### 改了两条既有断言（不是放松，是随流程移动）

`test_author_task_package.StatusAnswersWhereYouAre` 两条在我加 `index_sources` 之后红了，
它们锁的两条性质我都保住了，并且第一条比原来更紧：

- 原断言 `knowledge-use.mjs init in action`（收口那一刻就摆出整段顺序，别让人先跑 harness）
  → 改成同时断言 `--stage before-spec`（当前第一条命令）、`knowledge-use init`（整段顺序在）
  与 `harness 放在成文登记之后`。
- 原断言「本轮授权」在收口后的 action 里 → **没改断言**，改的是实现：
  把 `SPEC_STAGE_AUTHORIZATION` 挪到新的第一步上。这条是既有用例替我抓到的真缺口——
  我原本把授权留在了第二步，收口那一刻就打不出来了。

`test_s4_commit` 那条 `next` 断言由 `startswith("spec_")` 改成等于 `index_sources`：
它要说的是「收口之后往下走，不回去重新盘点材料」，现在说得更准。

### 送审证据

| 门 | 结果 |
|---|---|
| 离线全量 | **864 passed, 6 skipped**，0 failed |
| 失效形态 | **70 条 FAIL 0**（中途报过 3 处零消费者导出：`imageId` / `readBytes` 删除，`indexLine` 收回不导出） |
| adapt-scan | 退出 0 |
| framework | `git status --porcelain framework/` 0 行 |
| 过拟合自查 | 交付面 diff + 新模块全文搜 `AR9000` / 业务专名 / 金样 / 轮次叙述：**零命中**。切法与归属判据里没有任何一条依赖某个案例的标题、金额或接口 |

### 规模（`measure()`，基线 `0a177cf2`）

| 类别 | 基线 | 上一步末 | 现在 | 本步净 |
|---|---:|---:|---:|---:|
| scripts_mjs | 2825 | 2825 | 3240 | **+415** |
| scripts_py | 1565 | 1727 | 1737 | +10 |
| prompts_md | 1787 | 1797 | 1815 | +18 |
| data / hooks_mjs | 752 / 3013 | 同 | 未动 | 0 |
| **总量** | **9942** | **10114** | **10557** | **+443** |
| 同范围完整字符量 | 499107 | 509393 | 531111 | +21718 |

逐笔：`story-sources.mjs` 新建 162（切法 45、引用与改写 30、重定位 18、视图 40、
短 ID 与摘要 20）；`story-build.mjs` +253（`indexSources`/`buildIndex`/`indexImages` 约 75、
`selectionProblems` 约 50、来源变更与 `--accept-source` 约 60、`cmdSources` 约 60、
`ensureDecisions` 提取净 +8）；`story_flow.py` +10；提示词 +18。

**本步退出量为零**，如实记。总方案 §7 对 scripts_mjs 的估算是「新增 220–400、退出 180–300」——
本步一步就用掉了新增区间的上限还多 15 行，而退出全在 step-03（v3 作者链）。
按 §7 我不自己抬也不裁剪，把这个事实交评审审视：如果评审认为输入侧就该更小，
可退的候选我看到两处——`selectionProblems` 的八条检查（01 §5/§7 逐条要求，删哪条都会让
一类坏引用静默通过）与 `driftReport` 的候选渲染（01 §4 末段要求逐项列旧/新）。
两处都是分册明写的，所以我没有自行删减。

### 提交边界与剩余限制

- 将纳入：`story-sources.mjs`、`story-build.mjs`、`story_flow.py`、`SKILL.md`、
  `phases/story-write.md`、`test_source_index.py`、`test_s4_commit.py`、`test_author_task_package.py`。
- 不带：工作区里他人的未提交改动（`AGENTS.md`、`TEST.md`、`mechanism-budget.yaml`、
  `test_mechanism_budget.py`、`run_multi_case.py`）；`98` 与本目录在 `.gitignore`。
- 剩余限制：① 视图函数只有函数级证据，落盘接线与「有效取舍」的合并规则在 step-03；
  ② `--stage after-spec` 还不认，报错只列当前允许值；③ 真实 CLI 未跑，行为待验；
  ④ 材料版本对行尾不免疫（见上），本步未处理。
- 本步问题反思：`SPEC_STAGE_AUTHORIZATION` 是既有用例替我抓到的——我加新第一步时
  只想着「这一步该说什么」，没问「原来的第一步身上挂着什么，现在谁来背」。
  在一条链的头上插一步，得先看清被顶掉的那一位身上有没有只有它在承担的东西。

## seq 18 · 评审（reviewer）

### 独立核对

| 项 | 本次亲跑 | 与送审自述 |
|---|---|---|
| `test_source_index.py` + `test_s4_commit.py` + `test_author_task_package.py` | 100 passed / 13 subtests | 一致 |
| 离线全量 | 864 passed / 6 skipped，0 failed | 一致 |
| 失效形态 | 退出 0，FAIL 0 | 一致 |
| adapt-scan / framework | 退出 0 / 0 行 | 一致 |
| `measure()` | scripts_mjs 3240、scripts_py 1737、prompts_md 1815，总量 10557 | 一致 |
| 金样四源逐项 | 读了 `IndexesEveryUnitOfTheRealInput`：只比 heading 与 context，不比 start/end 与 digest——与送审说明的两处结构性差异一致 | 一致 |

`story-sources.mjs` 通读：只有解析与装配，没有取舍判断；`relocate` 只按完整标题路径相等，不按相似度。`selectionProblems` 八条全是引用与理由的存在性。三条实施前假设（去空行同一规则、`AR_ORIGINAL` 走 `design.origin`、视图只导出不接线）都成立且各有用例。`SPEC_STAGE_AUTHORIZATION` 挪到新首步这一处，是既有用例抓到的真缺口，处理对。

### 强制返修

| 编号 | 需求依据 | 真实错误及证据 | 强制结果 | 复验方法 |
|---|---|---|---|---|
| **02-R1（P2）** | 01 分册 §4 末两段：源变化时「逐项列出变更文件、旧/新摘要、受影响坐标、同标题路径候选」，`--accept-source` 「只更新现存 selection 中该源的 basis」 | 两份来源同时变（PRD、SE），先 `--accept-source SE`：`acceptSource` 之后 `writeJson(indexPath, index)`（`story-build.mjs` diff :337）把**全部**来源按当前磁盘重写，PRD 的旧单元随之消失。再跑一次不带参数的 `sources`：退出 0、报告里没有 PRD，而 `selection.basis.PRD` 仍是旧值。实测输出：`[plain after accept SE] rc=0 | stderr mentions PRD: False`、`[basis] PRD stale? True`。也就是说漂移判定只对着上一份索引，不对着 basis；接受一份就把其余未接受来源的「旧→新候选」证据一并抹掉，后面只能在 skeleton 的 basis 核对里撞到「版本不一致」却拿不到候选 | 漂移以 `selection.basis` 为准来判（旧索引只用来提供旧单元做候选）；`--accept-source K` 只刷新 K：索引里 K 的 sources/units 按当前重建，其余来源保留旧索引条目，直到各自被接受。等价做法也接受：`--accept-source K` 时若还有别的来源 basis 与磁盘不一致，直接拒绝并把它们列出来，要求逐一处理。二选一由 executor 定，报错要说清另几份还没接受 | 新用例：PRD、SE 同时改 → `--accept-source SE` 退出 0 → 再跑 `sources` 必须退出 1、报告含 PRD 及其同标题路径候选、`basis.PRD` 仍旧；随后 `--accept-source PRD` 后再跑才通过。既有 `test_accepting_one_source_moves_only_its_version` 仍绿 |
| **02-R2（P3）** | 01 分册 §3：「必需来源缺失、坏清单、缺原AR来源且不能判明输入身份时明确失败，不用空数组冒充没有材料」；「不硬要求本地问题单有远程RR/SR」 | 删掉 `RR/prd.md` 后跑 `sources`：退出 0，索引只剩 `SE / DESIGN / AR_ORIGINAL`，stdout 没有一个字提到 PRD 不在。`indexSources` 末尾 `filter(fs.existsSync)` 把合同标 `required: true` 的来源静默丢掉，只在一份都没有时才失败 | 合同 `required: true` 的来源缺失时：有 `AR/detail.json` 的系统单退出非零并点名缺哪份；本地单（无 `detail.json`）允许缺 RR/SR，但 RESULT 行点名「缺 PRD（合同标必需，本地单允许）」，不静默。`scanSources` 已算出 `missing[].required`，复用它，不另写一遍扫描 | 两条用例：系统单缺 PRD → 退出 1 且报「PRD」；本地单缺 PRD → 退出 0 且 RESULT 含「PRD」 |

### 不阻塞的观察（记给 step-03 与方案作者，不要求本步改）

- **02-N1** `DERIVED_KEYS = {DESIGN, SPEC}` 是脚本里的硬编码，而合同只给 SPEC 标了 `derived: true`。同一件事两处说。step-03 改合同时给 DESIGN 也标上并让 sources 读合同；本步不动，因为 `scanSources` 对 `derived` 另有语义（只守业务编号），改合同要先核那条消费者。
- **02-N2** 金样 `source-index.json` 与真实切片在两处对不上：单元范围含首尾空行（本步按「正文起止行」两端去空行，理由成立）；PRD 的 digest 是 CRLF 时算的，而 `d2d7a0eb` 入库时按 `.gitattributes` 归一成 LF（这是我提交时做的归一）。建议方案作者用真实命令重生成一份金样索引，此后测试可以连 start/end 与 digest 一起比。不在 executor 的边界内。
- **02-N3** 「材料版本随行尾变」不是 `materials.py` 的问题：`.gitattributes` 已规定 LF，CRLF 只来自 Windows 会话直接落盘。不立项。
- **02-N4** `SPEC_STAGE_ORDER` 文案里「在草稿的指导区下面写正文 → 统稿」仍是 v3 说法，随 step-03 退出。
- **02-N5** 规模：本步 scripts_mjs +415 已超过总方案 §7 给整个 2.3 的新增区间上限（220–400），退出量为零。逐笔看没有一段在替模型判断，八条 selection 检查与漂移报告都是分册明写的，不要求裁。但这意味着 step-03 的退出（v3 指导区、`context_chapters`、长 stdout 分发，估 −180～−300）必须如数出现，否则 2.3 收口时「总量下降」的期望落空；届时按总方案 §7 走专项审视。

**本轮结论：changes_requested。** 02-R1 是失败路径上的真洞，02-R2 是分册明写的失败语义；两条都不改设计，改完按各自复验方法自核后再送审。

## seq 21 后 · 返修送审（executor）

沿用 `02-R1` / `02-R2` 编号。两条都先复现再改。

### 02-R1 → 最终修改位置 → 验证及实际结果

**复现无误**（`repro_r1.py`，PRD 与 SE 同时改）：

```
[both changed]            rc=1  报告含 PRD 与 SE
[accept SE]               rc=0
[plain after accept SE]   rc=0   stderr 提到 PRD: False     ← 洞
[basis] PRD 仍是旧值: True
[索引] PRD 单元已被换成新的: True
```

**根因不是 `--accept-source` 写多了，是漂移判据问错了对象。** 原来拿「上一份索引 vs
当前磁盘」比，而索引是磁盘的投影：接受任何一份来源都会把整份索引重算，其余几份
「变过」这件事随之消失。

最终修改在 `story-build.mjs`：

- 新增 `staleSources(basis, now)`：漂移判据改成「取舍里的 `basis` vs 磁盘现状」。
  `basis` 是取舍据以成立的版本，只有 `--accept-source` 能动它，所以一份来源没被
  显式接受之前，它一直报。原 `sourceDrift` 退场。
- `driftReport(stale, oldIndex, fresh, selection)`：候选仍由「旧索引的单元 vs 当前切片」
  经 `relocate` 算，受影响的取舍从 `selection.items` 反查。
- **还有来源没接受时索引不重建**（plain 分支本来就不写；`--accept-source` 分支只在
  `staleSources` 归零之后才写）。旧单元是「旧 ID 现在指向哪一段」唯一的依据，
  提前重建就把它抹掉了——这正是 R1 后半段说的那件事。
- `--accept-source` 的输出点名还剩哪几份没接受，NEXT 首屏给下一步。
- 顺带：新出现的来源直接进 `basis`（它没有旧取舍要重看），不必走一遍接受。

改后同一份复现脚本：

```
[plain after accept SE]   rc=1   stderr 提到 PRD: True
[索引] PRD 单元已被换成新的: False
```

用例（`SourceChangesGetCandidatesNotGuesses`，新增 3 条）：

| 用例 | 实际结果 |
|---|---|
| `test_accepting_one_source_still_reports_the_others` | 接受 SE 后 plain 退出 1、报告含 `PRD` 与 `PRD#3` 与候选箭头、`basis.PRD` 未动；两份都接受后才退出 0 |
| `test_the_index_waits_until_every_source_is_accepted` | 接受 SE 之后索引字节不变；两份都接受并 plain 之后才变 |
| `test_accepting_says_which_ones_are_still_pending` | `--accept-source SE` 的 stdout 首屏 NEXT 里点名 PRD |
| `test_accepting_one_source_moves_only_its_version`（既有） | 仍绿 |

### 02-R2 → 最终修改位置 → 验证及实际结果

**复现无误**：删掉 `RR/prd.md` 后跑 `sources` 退出 0，索引只剩三份，输出一个字不提 PRD。
`indexSources` 末尾的 `filter(fs.existsSync)` 把合同标必需的来源静默丢掉了。

最终修改：新增 `missingRequired(ctx, stage)`，复用 `scanSources().missing` 已经算好的
`required`，不另写一遍扫描；`cmdSources` 按有没有 `AR/detail.json` 分两条：

- **有系统单据**：退出非零，点名缺哪份（键与路径都给），并说明「这几份正文是拉得下来的，
  先导入再索引」；一个字节不写。
- **本地单**：照常索引，`RESULT` 行结尾点名「缺 PRD（合同标必需，本地单允许）」。

用例（新增类 `AMissingRequiredSourceIsNeverSilent`，2 条）：系统单缺 PRD → 退出 1 且
报出 `PRD` 与 `RR/prd.md`、索引未写；本地单缺 PRD → 退出 0 且 RESULT 含 `PRD`。

### 四条不阻塞观察的处置

- **02-N1（`DERIVED_KEYS` 硬编码）**：按评审意见留到 step-03，本步未动。
- **02-N2（金样索引重生成）** 与 **02-N3（行尾）**：收下更正——`.gitattributes` 已规定 LF，
  行尾问题不是 `materials.py` 的。我上一轮把它写成「材料版本随 checkout 变」不够准确，
  已在本节更正，不再作为遗留限制。
- **02-N4（`SPEC_STAGE_ORDER` 里的 v3 说法）**：随 step-03 退出，本步未动。
- **02-N5（规模）**：接受这个判断，逐笔见下；step-03 的退出量我会按 §7 如实报。

### 四道门（改后）

| 门 | 结果 |
|---|---|
| 离线全量 | **869 passed, 6 skipped**，0 failed |
| 失效形态 | **70 条 FAIL 0** |
| adapt-scan | 退出 0 |
| framework | 0 行 |

### 规模

| 类别 | 基线 `0a177cf2` | 上次送审 | 现在 | 本次返修 |
|---|---:|---:|---:|---:|
| scripts_mjs | 2825 | 3240 | 3266 | +26 |
| scripts_py / prompts_md | 1565 / 1787 | 1737 / 1815 | 未动 | 0 |
| **总量** | **9942** | **10557** | **10583** | **+26** |
| 同范围完整字符量 | 499107 | 531111 | 532546 | +1435 |

返修 +26 全在 `story-build.mjs`：`staleSources` 与 `missingRequired` 两个判据函数、
`--accept-source` 的「还剩哪几份」分支、新来源进 basis 那一支；`sourceDrift` 退场抵掉一部分。

### 剩余限制

与上次相同，去掉已被更正的那条：① 视图函数只有函数级证据，落盘接线在 step-03；
② `--stage after-spec` 还不认；③ 真实 CLI 未跑，行为待验。

### 本轮反思

两条都在**失败路径**上，而我上一轮的用例只走到「一份来源变了」为止。
「一份」和「两份」在这条链上不是同一件事：判据对着谁比，只有出现第二份时才暴露。
写失败路径的用例时，得先问这条路径上有没有「多个同类对象」的维度——有的话，
一个样本证明不了任何事。

## seq 24 · 返修复核与 closeout（reviewer）

### 独立核对

| 项 | 本次亲跑 | 与送审自述 |
|---|---|---|
| 三份测试文件 | 105 passed / 13 subtests | 一致（+5 例） |
| 离线全量 | 869 passed, 6 skipped, 242 subtests passed in 25.07s | 一致 |
| 失效形态 / adapt-scan / framework | FAIL 0 / 退出 0 / 0 行 | 一致 |
| `measure()` | scripts_mjs 3266，总量 10583 | 一致 |
| 02-R1 用我上一轮的探针重跑 | PRD、SE 同时改 → accept SE 退出 0 → 再跑 `sources` **退出 1、报告含 PRD**、`basis.PRD` 未动、索引里 PRD 仍是旧单元（`index PRD digest == disk? False`） | 洞已闭合 |
| 02-R2 两种形态 | 本地单缺 PRD：退出 0，RESULT 行点名 PRD；系统单（有 `AR/detail.json`）缺 PRD：退出 1，stderr 含 PRD 与 `RR/prd.md` | 一致 |

02-R1 的修法比我要求的更对：漂移判据从「上一份索引 vs 磁盘」改成「`basis` vs 磁盘」（`staleSources`），旧索引只用来给候选；还有来源没接受时索引不重建。这才是 01 分册 §4「basis 是取舍据以成立的版本」的本义，`sourceDrift` 退场。新来源直接进 basis 的处理合理。02-R2 复用 `scanSources().missing`，没有第二套扫描。

02-R1 与 02-R2 关闭。02-N1～N5 的处置同意（N3 我上一轮已更正，executor 收下）。

### closeout

- 最终设计：`core/story-sources.mjs` 只做定位与装配（切单元、引用改写、同标题路径重定位、章/公共视图函数）；`story-build sources --stage before-spec` 生成 source-index（短 ID、`sources[].digest`、`images[].source|null`）并首次落稀疏 selection（`basis` 由脚本填、空 items 合法）；漂移以 selection.basis 为准，`--accept-source K` 只刷新 K、全部对齐后才重建索引；必需来源缺失系统单失败、本地单点名；decisions 空容器在初筛前就位；complete 之后 `status` 给 `index_sources`，不起 Node；SKILL 与 story-write 加初筛一节。不实现 collect，不生成 Spec 前视图，v3 作者链本步照常。
- 实际修改：新建 `story-sources.mjs`、`test_source_index.py`（46 例）；`story-build.mjs`（sources 命令、`ensureDecisions` 提取）、`story_flow.py`（`index_sources` 步与授权前移）、`SKILL.md`、`phases/story-write.md`；`test_s4_commit.py`、`test_author_task_package.py` 各一处断言随流程更新且更严。
- 验证：见上表；金样四源 heading/context 28/28、images 逐张一致；两处与金样索引的差异（行范围去空行、PRD digest 为 CRLF 时算的）已解释，见 02-N2。
- 剩余限制：① 视图函数只有函数级证据，落盘接线与「有效取舍」合并在 step-03；② `--stage after-spec` 未实现；③ 真实 CLI 未跑，行为待验；④ 02-N1 硬编码与 02-N4 v3 文案随 step-03 处理；⑤ 02-N2 金样索引重生成归方案作者。
- 规模：scripts_mjs 2825→3266（+441）、scripts_py +10、prompts_md +18，总量 10583；本步退出量为零。它已超出总方案 §7 给整个 2.3 的新增区间上限，step-03 的退出（v3 指导区协议、`context_chapters`、长 stdout 分发）必须如数出现，2.3 收口时按 §7 专项审视。
- 本步问题反思：两条返修都出在「多个同类对象」的维度上——一份来源变的用例证明不了两份同时变时判据对着谁比。executor 自己的反思说到了点上。评审侧的教训是首轮就该把「同类对象 ≥2」的反例列进验收表，而不是等看到实现再推。

**批准提交。** 纳入：`story-sources.mjs`、`story-build.mjs`、`story_flow.py`、`SKILL.md`、`phases/story-write.md`、`test_source_index.py`、`test_s4_commit.py`、`test_author_task_package.py`；不带工作区里他人的改动。
