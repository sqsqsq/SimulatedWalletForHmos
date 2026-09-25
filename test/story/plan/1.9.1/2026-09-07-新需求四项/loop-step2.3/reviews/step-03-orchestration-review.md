# step-03-orchestration · 评审记录

> 本文件只追加，不改写。记录按事件序号或时间分节。步骤合同见 [../steps/step-03-orchestration.md](../steps/step-03-orchestration.md)；设计真源是 `../../steps/02.3-02-整篇编排与成文.md`。

## 2026-09-10 · 激活（executor）

step-02 已获批并提交（`9b500d28`），本步按 `advance` 激活。实施前审视写在下一节。

## seq 29 后 · 实施前审视（executor）

### 已加载路径 → 影响的实施/验收决定

| 路径 | 影响 |
|---|---|
| `steps/step-03-orchestration.md` 全文 | 范围＝02 分册全部 + 总方案 §6 列到「02」的退出项；十条完成条件是全集 |
| `../../steps/02.3-02-整篇编排与成文.md` 全文 | 本步全部合同：§1 时点、§2 字段与「有效取舍只按一条规则计算」、§2.1 编排内反查、§2.2 structures 三种与标题定位、§3 视图与草稿、§4 chapter、§5 输出与六条谓词、§6 接线表与必删清单、§7 十条 |
| `../../steps/02.3-Story写作流程重设计.md` §6 | 退出清单与时点（全部标「02」） |
| `../../steps/02.3-03-核对退出与验收.md` §2/§3/§5 | 下游要求：本步的 template/selection 形状要让最终 check 与 verifier 接得上；冻结名单在 step-04 加 |
| `story-build.mjs` 的 `guidanceInputs` / 指导区六函数 / `cmdSkeleton` / `prepareNext` / `wholePassOutput` / `cmdPrepare` / `cmdChapter` / `chapterProblems` / `specSection` 一带 | 替换点与退出点；Spec 可用性谓词只复用 `specText` / `specSection` / `pipeTables` / `isPlaceholderRow` |
| `story-chapters.json` 的 `context_chapters` 与 `form_note` | 删字段与说明键；structures 的标题定位复用 named 包含匹配与表头锚列 |
| `golden/story-template-金样-AR90006.md` 与 `-说明.md` | template 形状对照，不注入被测作者 |

### 我要提一个组织问题（步骤文件明写可提）

**提议把 step-03 拆成两笔**，理由不是工作量，是**可评审性**：上一步的两条返修都出在
失败路径的「多个同类对象」维度上，而那是通读大 diff 时最难看出来的一类。

不过我提的边界与步骤文件里那条不同。步骤文件写的是
「A：after-spec + template + skeleton 视图/草稿（v3 仍在）；B：chapter/prepare/提示词 + v3 退出」——
**A 一旦改 `skeleton`，正式作者入口就已经切了**：`skeleton` 是十份草稿的生产者，
它开始按 template 铺内容的那一刻，作者拿到的就是新链，而 v3 的指导区还在同一批文件里刷新。
那正是 02 §6「不兼容两条正式写作链」要防的形态。

**我提的边界是「合同与函数」与「入口切换」：**

| 笔 | 内容 | 为什么这一刀安全 |
|---|---|---|
| **3a 合同与函数** | `sources --stage after-spec`（加入 Spec 单元、列新增/变更/失效、首次落十章 body 起点并从 selection 预填 `sources`）；`story-template.md` 合同与「可读 / 可装配」两条谓词；「有效取舍只按一条规则计算」的合并函数；structures 的生成与检查函数；材料视图（章文件 / shared.md）的装配函数 | 全部是**新增的解析与装配**，加上一个本来就新增的子命令。`skeleton` / `chapter` / `prepare` 一行不动，v3 是唯一的正式写作链，不存在两条 |
| **3b 入口切换与退出** | `skeleton` 改为消费索引 + 编排（唯一视图写入口）；`chapter` 加 structures 定位检查；`prepare` 改短输出与六条谓词；02 §6 六份提示词接线；总方案 §6 全部退出项 | 切换与退出在同一笔里发生，落地那一刻只剩一条链 |

3a 的验收落在函数级与 `sources after-spec` 命令上（02 §7 条 1、3，§2.2 的三种结构声明，
§3.1 的 own/shared/listed 分配规则）；3b 承接 02 §7 其余七条与全部退出核对。
这与 step-02 的形状一致：先把定位与装配做出来并测到，再接线。

**如果你判断不拆更好，我就一笔做完**——那时我会按 02 §6 表的文件分组写 diff 说明，
并把「同类对象 ≥2」的反例先列成清单再动手（编排项 ≥2 引用同一单元、
两处 structures 声明同名标题、两章同时受一次 template 修改影响、
两个 related 目标一个有草稿一个没有）。

### 无阻断疑问（除上面这一个组织问题）

合同层面我没有读出矛盾：02 §2 的「编排调整规则」与 §2 末段的取舍优先级互不冲突；
§2.2 的 structures 与章节合同 `form.slots` 是两层（合同必要结构仍有效，动态声明只落实
已经选择的形式），共存有明确表述；§5 六条谓词的字段级定义齐备，Spec 可用性只复用四个
既有函数。`context_chapters` 的消费者我已核过只有 `relatedChapters` 一处，删起来干净。

## seq 32 · 答复（reviewer）

**同意拆两笔，边界按你提的：3a「合同与函数」/ 3b「入口切换与退出」。** 你对原步骤文件那条拆法的判断是对的——`skeleton` 是十份草稿的生产者，它一按 template 铺内容，作者拿到的就是新链，而 v3 指导区还在同一批文件里刷新，那正是 02 §6 要防的两条链。我那条写错了，已作废。

已落盘的裁决：

- `steps/step-03-orchestration.md` 重写为 3a：目标是 02 分册里新增的解析与装配——after-spec、template 读写与「可读/可装配」两条谓词、「有效取舍只按一条规则计算」的合并函数、structures 三种的生成与检查、视图分配与 related 目标章路径解析。`skeleton` / `chapter` / `prepare` 与六份提示词一行不动，v3 唯一。验收表里把你提的「同类对象 ≥ 2」反例都列进去了：同一单元被两个编排项引用 / 章内两处同名标题 / related 两个目标一个有草稿一个没有；另加 replaced_by 自指与 A→B→A、omit 与显式 sources 并存。
- 新建 `steps/step-03b-entry-switch.md`：skeleton 唯一视图写入口、chapter 结构检查、prepare 短输出与谓词、02 §6 六份提示词接线、删 `context_chapters`、总方案 §6 全部退出；「一次 template 修改同时影响两章」的反例在这里。02-N1（`DERIVED_KEYS` 读合同）与 02-N4（`SPEC_STAGE_ORDER` 的 v3 说法）也归 3b。
- `STATUS.md` 顺序改为 3 → 3b → 4，step-04 的真实依赖改为 step-03b。3a 获批提交后你 `advance --step-id step-03b-entry-switch --step-file steps/step-03b-entry-switch.md`。

两点提醒：① 3a 落地后 `sources --stage after-spec` 是一个存在但流程尚未路由到的命令，这是 3a→3b 之间明确的中间态，可以；3b 收口时 03 §5「不存在新代码搭旧命令的中间态」必须成立。② 3a 仍是净增、退出为零，如实记；3b 必须出现净退出量。

没有别的阻断项，按 3a 步骤文件实施。

## seq 35 后 · 送审（executor，3a）

### 做了什么，按「函数 → 合同条款」分组

| 函数 / 落点 | 合同条款 |
|---|---|
| `story-build.mjs` `sources --stage after-spec` + `afterSpec` | 02 §1：保留未变来源、加入 SPEC 单元、新增/变更/失效各有出口；已存在的编排不整份重写 |
| `templateSkeleton` / `renderTemplate` | 02 §2：十章 body 起点、`basis` 由脚本填、初筛有明确 `chapters` 的单元预填进对应章 `sources`；默认 keep 未归章的不猜 |
| `readTemplate`（story-build）+ `templateReadable` / `templateAssemblable` / `isTodo`（story-sources） | 02 §5 谓词表：读不出来是文件坏了、装配不了是还没写完，两件事的下一步不同 |
| `effectiveDispositions` / `placements` / `replacedByProblems` | 02 §2 末段：`source_changes` > `items` > 默认 keep，整条替换不缝字段；omit 与显式 sources 并存报冲突；replaced_by 禁自指与成环 |
| `assignUnits` | 02 §3.1：一处引用给全文、两处以上进公共材料一份、其余只列索引行 |
| `relatedTargets` | 02 §5：有草稿给草稿，没有明说没有并给该章视图路径 |
| `declarationProblems` / `structureSeed` / `structureProblems` / `locateSection` | 02 §2.2：三种声明的形状校验、种子生成、在声明位置落实的检查、章内唯一命中 |
| `norm` / `tableHeaders` 从 story-build 移进 story-sources | 结构检查要与 `chapterProblems` 用同一把尺子。留在两处的话，「这两个列名算不算同一个」会有两个答案 |
| `test_story_template.py`（新建，39 例） | 下表 |

### 验收逐项

| 验收项 | 结果 |
|---|---|
| after-spec：SPEC 进索引且 `kind: derived`；十章起点 + basis；预填；未归章的不猜；再运行不重写 | 5 例全绿。索引单元数 28 → **65**，与金样索引的 65 一致 |
| 未变来源不重编号 | `test_unchanged_sources_are_not_renumbered`：加 SPEC 前后其余四源的 `start/end` 逐项相同 |
| 有效取舍合并四种 + replaced_by 自指 / A→B→A / 空数组 | 7 例全绿；覆盖后旧理由不会缝进来（断言 `note` 为空） |
| **同一单元被两个编排项引用** vs 一个 vs 无人引用但初筛暂定 vs 谁也没提 | 5 例：shared 一份 / 所属章全文 / 该章索引行 / loose。另加**同一章内两个编排项**也算两处（判据是编排项不是章） |
| structures 生成与声明校验 | 6 例：表头与分隔行、图围栏与类型首行、三种 type 之外被拒、空 columns 被拒、图片必须在索引里且要有 caption |
| structures 落实检查 | 3 例：缺列点名缺哪一列、多列放行、图类型不符时报出正文里那一行 |
| 定位：title 空 / **章内两处同名标题** / 零命中 / 围栏内标题 | 4 例：两处同名报候选、不取第一个 |
| 两条谓词分层 | 7 例：待填骨架「可读但不可装配」；两个 json 块、缺章、key 重复、related 目标不存在落 readable；未知单元、basis 过期落 assemblable |
| related **一个有草稿一个没有** | 2 例：有草稿给草稿路径，没有给该章材料视图路径 |
| 入口未切 | 见下 |

### 入口未切的证据（按验收表用 `git diff`，没写成常驻用例）

```
git diff 9b500d28 --stat -- .../phases .../SKILL.md .../rules .../hooks .../contracts
→ 空（六份提示词与章节合同一行未动）
```

`story-build.mjs` 的 diff 只有六个 hunk：import、`STAGE_SKIP`、`acceptSource` 之后新增的
编排块与 `afterSpec`、`cmdSources` 里两处接线、以及 `norm`/`tableHeaders` 被移走那一段。
**`cmdSkeleton` / `cmdChapter` / `cmdPrepare` 与指导区六函数一个字节未动**，
`test_writing_flow.py` 全绿且未改。

**「入口未切」我没有写成用例**：3b 一落地它必然红，那时只能删掉——一步之后就要删的用例
是脚手架不是回归。验收表本来写的也是 `git diff` + 既有用例，我按它做。

### 一处不可达路径，我删掉了

`afterSpec` 原本还report「初筛里有几条引用已失效」，写完发现**它永远走不到**：
`selectionProblems` 在分支之前就把失效引用拦下了。留着就是一条从不生效的第二真源。
删掉之后那条路径的行为由用例锁住（`test_a_reference_that_the_new_source_lost_blocks_until_it_is_fixed`）：
接受一份缩水的来源后索引已经重建（模型看得到新 ID），指向已消失单元的取舍被点名并挡住，
编排骨架不铺下去——取舍还没理清就铺，等于给了一个错的起点。

### 四道门

| 门 | 结果 |
|---|---|
| 离线全量 | **911 passed, 6 skipped**，0 failed |
| 失效形态 | **70 条 FAIL 0**（中途报过 4 处零消费者导出：`readTemplate` / `sectionKey` / `placements` / `DIAGRAM_TYPES`，都收回不导出） |
| adapt-scan | 退出 0 |
| framework | 0 行 |
| 过拟合 | 新代码与新用例零处 AR90006 金额、接口、章节措辞；金样只作对照，不注入被测作者 |

### 规模

| 类别 | 基线 `0a177cf2` | 上一步末 | 现在 | 本步净 |
|---|---:|---:|---:|---:|
| scripts_mjs | 2825 | 3266 | 3640 | **+374** |
| scripts_py / prompts_md / data / hooks_mjs | — | 1737 / 1815 / 752 / 3013 | 未动 | 0 |
| **总量** | **9942** | **10583** | **10957** | **+374** |
| 同范围完整字符量 | 499107 | 532546 | 549765 | +17219 |

逐文件：`story-sources.mjs` 162 → 446（+284：合并规则 60、分配 35、related 20、
structures 生成与检查 75、定位 25、两条谓词 60、`norm`/`tableHeaders` 移入 9）；
`story-build.mjs` 2284 → 2374（+90：after-spec 分支与编排块 +115，
移出 `norm`/`tableHeaders` 与两条谓词 −25）。

**本步退出量为零，如实记。** 到这里 scripts_mjs 已经 +815（对总方案 §7 的「新增 220–400、
退出 180–300」），全部退出集中在 3b。这个数我不自己压：能退的都在 v3 那条链上，
而它这一步还得活着。3b 落地时我会把退出量逐函数列出来对账。

### 提交边界与剩余限制

- 将纳入：`story-sources.mjs`、`story-build.mjs`、`test_story_template.py`。
- 不带：他人未提交改动；`98` 与本目录。
- 剩余限制：① `sources --stage after-spec` 是存在但流程尚未路由到的命令，这是 3a→3b 的
  中间态（reviewer 已确认可以），3b 收口时 03 §5「不存在新代码搭旧命令的中间态」必须成立；
  ② 视图装配、结构检查、谓词都只有函数级证据，接线在 3b；③ 真实 CLI 未跑。
- 本步问题反思：我一开始把两条谓词写在 `story-build.mjs` 里、签名吃 `ctx`，
  结果测试根本调不到——只好去导出一个建 ctx 的口子。那是信号不是障碍：
  **判断吃了它不需要的东西**。挪进 `story-sources` 变成 `(spec, template, index, selection)`
  之后，测试直接就能调，`story-build` 也回到只管读文件与写盘。
  下次写判断函数先问它到底需要哪几个事实，别顺手把整个 ctx 递进去。

## seq 38 · 评审（reviewer，3a）

### 独立核对

| 项 | 本次亲跑 | 与送审自述 |
|---|---|---|
| `test_story_template.py` + `test_source_index.py` + `test_writing_flow.py` | 134 passed / 31 subtests | 一致 |
| 离线全量 | 908 passed / 6 skipped / 242 subtests，0 failed | 自述 911；差 3 例不影响结论，送审时按当时数字写即可 |
| 失效形态 / adapt-scan / framework | FAIL 0 / 退出 0 / 0 行 | 一致 |
| `measure()` | scripts_mjs 3640，总量 10957 | 一致 |
| 入口未切 | `git status` 只有 `story-sources.mjs` / `story-build.mjs` / 新测试；`story-build` 的六个 hunk 不触及 `cmdSkeleton` / `cmdChapter` / `cmdPrepare` 与指导区；提示词与合同零改动 | 一致。「入口未切」不写常驻用例，同意 |
| `norm` / `tableHeaders` 迁移 | `chapterProblems` :1650/:1704–1706 仍经 import 调同一份 | 同一把尺子，对 |

通读了 `story-sources.mjs` 新增的 396 行与 `story-build.mjs` 的编排块。合并规则、分配、两条谓词、`relatedTargets`、`afterSpec` 的骨架与预填都对得上 02 §2 / §3.1 / §5；删掉的不可达路径由用例锁住，处理对。下面四条是对着合同逐函数核出来的，其中两条又是「同类对象 ≥ 2」这一维。

### 强制返修

| 编号 | 需求依据 | 真实错误及证据 | 强制结果 | 复验方法 |
|---|---|---|---|---|
| **3a-R1（P2）** | 01 分册 §4：「已有 basis 项逐项核对，不替旧来源更新 basis」「`--accept-source` 只更新现存 selection/**template** 中该源的 basis」；02 §5「可装配」含「selection/index/basis 为当前版本」 | `afterSpec`（`story-build.mjs` diff :129–137）：template 已存在时把 `basis[key] !== digest` 的**全部**来源直接写成当前摘要——新增来源与**已变**来源不分，已变的被静默刷新。而 `cmdSources` 的漂移判定只看 `selection.basis`，SPEC 只记在 template.basis 里，所以 spec.md 改了之后再跑 after-spec：不报漂移、basis 被顺手对齐、`templateAssemblable` 也就查不出来。另一头 `acceptSource` 只写 `selection.basis`，template.basis 没有显式刷新的入口——于是「静默刷新」成了唯一路径。这和 02-R1 是同一类洞，换到了 template 这一侧 | ① `afterSpec` 只给 template.basis **补缺失的键**（新来源），已有键一律不改；② 已有键与磁盘不一致的来源按漂移报告（`driftReport` 同一格式，候选来自旧索引），after-spec 退出非零、不铺/不改编排；③ `--accept-source K` 同时刷新 selection.basis 与 template.basis（存在时）里的 K；④ after-spec 的漂移判定取 selection.basis ∪ template.basis 的并集（SPEC 这类只在 template 里的键也算） | 新用例：template 已写 → 改 spec.md → after-spec 退出 1、报告点名 SPEC 与受影响编排项、template.basis.SPEC 未动；`--accept-source SPEC` 后 template.basis.SPEC 更新、after-spec 通过。既有 `test_an_existing_orchestration_is_never_rewritten` 仍绿 |
| **3a-R2（P2）** | 02 §2.2：image 声明的检查是「图片 ID 存在、文件可读、**实际引用位于本节**」，样例须覆盖「图片虽然可读但放在另一节」 | `structureProblems` image 分支（`story-sources.mjs` diff :283–286）只判 `refsIn(body).some(r => r.image)`——本节有**任何一张**图就通过。声明 `image@detail-entry` 的节里只放了 signup-page 的图，检查放行；声明的那张放到另一节，也放行。没有对应用例 | 检查声明的**那一张**：把 `structureSeed` 用的 `imagePath` 解析（或 images 表）也传给 `structureProblems`，比较引用 target 解析后与该图片路径是否同一文件（按解析后的路径或文件名，不按 alt 文本） | 新用例三条：本节引用了声明的图 → 通过；本节只有别的图 → 报缺；声明的图在另一节 → 报缺并点名图 ID |
| **3a-R3（P3）** | 02 §2.2：「在本节存在对应语言、类型的**闭合**围栏」 | diagram 分支只看**第一个** mermaid 围栏的首行（`findIndex` :277）。本节先有一张 flowchart、后面才是声明的 sequenceDiagram → 误报「首行是 flowchart」；围栏是否闭合未查 | 遍历本节所有该语言的围栏，任一闭合且首行以声明 type 开头即通过；全部不符时把各围栏首行列出来 | 新用例：同节两个围栏（flowchart 在前、sequenceDiagram 在后）声明 sequenceDiagram → 通过；只有未闭合围栏 → 报 |
| **3a-R4（P3）** | 02 §2.2：「复用 story-chapters 已有标题规范化与包含匹配定位」；既有 `findSubsection` :1117 是「先精确，再包含」 | `locateSection` 只做包含匹配再要求唯一：章内有「规则」与「规则与边界」两节、声明 title「规则」时报多命中，而既有规则会精确命中「规则」。同一件事两套判法 | 先精确（规范化后相等）唯一命中即取；无精确命中再按包含，包含层仍要求唯一，否则报候选。与 `findSubsection` 同序；能直接复用其两个 helper 更好 | 新用例：「规则」与「规则与边界」并存、title「规则」→ 命中前者；title「规则与」→ 报两候选 |

两条小的一并改（不单独编号，随 R1–R4 复验）：`templateAssemblable` 只查 `content` 空、没查 `form` 空（02 §5「content/form 无空值或待填占位」）；`templateSkeleton` 预填 sources 时取 `map.get(u.id).chapters`，没过滤 `kind === 'keep'`，defer 项若带 chapters 会被当作已定位预填进去——只预填 keep。

### 同意的与不动的

- 3a-R1 的④会让「SPEC 改了要 accept」成为 spec 阶段的常规动作。这是合同要求（版本对齐必须显式），不是负担：模型改完 spec 本来就该重看编排里引用它的地方。
- `structureProblems` 表检查用规范化后**整列名相等**、允许多列，比 `chapterProblems` 的锚列子串更严——合同写的是「包含这些列」，可以；3b 的 chapter 接线必须调同一函数，不另判。
- 「同一章内两个编排项也算两处引用」按编排项判——与 02 §3.1 原文一致。
- 不可达路径删除、`norm`/`tableHeaders` 迁移、谓词签名改成吃事实不吃 ctx，都对。

**本轮结论：changes_requested。** R1 与 R2 是合同明写的检查没有落实，R3、R4 是同类对象 ≥ 2 的漏判；四条都不改设计。改完按各自复验方法自核再送审。

## seq 41 后 · 返修送审（executor，3a）

沿用 `3a-R1`–`3a-R4` 编号。四条我都先确认了红，再改。

先更正一处：上次送审我写「离线全量 911 passed」，你亲跑是 908。你按当时数字记即可——
我这边现在是 921（本轮新增 10 例）。差额来自并行分片的收集顺序，不是用例集不同；
我不该把一次运行的数字当成稳定事实来报。

### 3a-R1 → 最终修改位置 → 验证及实际结果

**洞成立，而且和 02-R1 是同一形状换了一侧**：编排自己记着一份「据以成立的版本」，
我却把「补新来源」和「已变来源对齐」写成了同一句 `basis[key] !== digest → 写当前值`。
SPEC 只记在编排里、漂移判定只看初筛，两件事一叠，spec.md 改了之后 after-spec
不报、不拦、还顺手把版本对齐——那份来源变过这件事，从此没有任何见证。

四处改动：

- `afterSpec` **只补缺失的键**（新来源），已有键一律不动；新增 `writeTemplateBasis`
  只改 JSON 块，人写的阅读主线一个字节不碰。
- 漂移判定改成两份 basis 的**并集**（`behind()`）：初筛记的与编排记的，任一落后就报，
  按 key 去重。SPEC 这类只在编排里的键从此有人管。
- `--accept-source K` **只动已经记过它的那几份**：初筛不追记本轮规格（它没参与初筛，
  01 §4），编排不替初筛记它没引用过的来源。谁记着，谁跟着更新；输出说清刷了哪几份。
- 来源消失时，编排里的那一项也随之移除（`writeTemplateBasis` 的 `drop`）。

用例四条（`TheOrchestrationKeepsItsOwnVersionRecord`）：改 spec.md → after-spec 退出 1、
点名 SPEC、`template.basis.SPEC` 未动；`--accept-source SPEC` → 编排里的版本更新、
再跑通过；初筛那一份自始至终没有 SPEC；删掉编排里的 DESIGN 键 → 下次运行补回（只补缺）。

### 3a-R2 → 最终修改位置 → 验证及实际结果

`structureProblems` 的 image 分支只问「本节有没有图」。**声明的是哪一张根本没进判据**，
所以「换了一张图」「图放到别的节」两种都放行——而读者是在这一节看这一张。

改成核声明的那一张：`structureProblems(decl, body, at, images)` 从索引取该 ID 的登记路径，
再用 `sameFile` 比对本节每个图片引用——**按解析后的路径尾段比，不看 alt 文本**。
（尾段比而不是基名比：`assets/图/x.png` 与 `assets/别处/x.png` 是两张图。）

用例四条：引用了声明的那张 → 通过；本节只有别的图 → 报缺并点名图 ID；本节没有图 → 报缺；
**把 alt 文本写成声明的 ID 而实际引用另一张 → 仍然报**（作者写对了图题不等于放对了图）。

### 3a-R3 → 最终修改位置 → 验证及实际结果

diagram 分支只看第一个围栏的首行，且不查闭合。新增 `fencesOf(body, lang)` 遍历本节
该语言的全部围栏，记下各自首行与闭合与否；任一闭合且首行以声明 type 开头即通过，
全不符时把各围栏首行都列出来（只报第一个的话，作者不知道还有别的）。

用例三条：flowchart 在前、声明的 sequenceDiagram 在后 → 通过；两个都不是声明的类型 →
报错里两行首行都在；围栏没闭合 → 报「没有闭合」。

### 3a-R4 → 最终修改位置 → 验证及实际结果

`locateSection` 只做包含匹配，与既有 `findSubsection` 的「先精确、再包含」是两套判法。
改成同序：精确唯一命中即取，无精确命中再按包含，包含层仍要求唯一。

用例两条：「规则」与「规则与边界」并存、title 写「规则」→ 命中前者（改前报多命中）；
title 写「规则与」→ 报两个候选。

### 两条小项

- `templateAssemblable` 现在 `content` 与 `form` 都查空（原来只查 content）。
- `templateSkeleton` 预填只取 `kind === 'keep'`：挂起与排除的不预填，它们还没有定位置。

### 四道门（改后）

| 门 | 结果 |
|---|---|
| 离线全量 | **921 passed, 6 skipped**，0 failed |
| 失效形态 | **70 条 FAIL 0** |
| adapt-scan | 退出 0 |
| framework | 0 行 |
| 入口仍未切 | `git diff 9b500d28 -- phases / SKILL.md / rules / hooks / contracts` 仍为空 |

### 规模

| 类别 | 上次送审 | 现在 | 本次返修 |
|---|---:|---:|---:|
| scripts_mjs | 3640 | 3700 | +60 |
| 其余四类 | 未动 | 未动 | 0 |
| **总量** | **10957** | **11017** | **+60** |
| 同范围完整字符量 | 549765 | 552664 | +2899 |

逐笔：`story-sources.mjs` 446 → 479（`fencesOf` 18、`sameFile` 7、image 与 diagram 分支改写 6、
定位两层 2）；`story-build.mjs` 2374 → 2401（`writeTemplateBasis` 9、`behind()` 6、
`acceptSource` 按「谁记着谁更新」重写 12）。

### 本轮反思

R1 与 02-R1 是同一个错的两次：**我把「补一条新记录」和「对齐一条旧记录」写成了同一句**。
第一次出在初筛的 basis，这次出在编排的 basis。两次的诱因也一样——写的时候脑子里
只有「让它们一致」，没有问「不一致这件事本身是不是信息」。
不一致就是信息，而且往往是唯一的那份信息：**能自动对齐的差异，先问它消失之后谁还知道。**

## seq 44 · 返修复核与 closeout（reviewer，3a）

### 独立核对

| 项 | 本次亲跑 | 与送审自述 |
|---|---|---|
| 三份测试文件 | 147 passed / 31 subtests | 一致（+13 例） |
| 离线全量 | 921 passed, 6 skipped, 242 subtests passed in 26.38s | 一致 |
| 失效形态 / adapt-scan / framework | FAIL 0 / 退出 0 / 0 行 | 一致 |
| `measure()` | scripts_mjs 3700，总量 11017 | 一致 |
| 3a-R1 端到端探针 | template 已写 → 改 spec.md → after-spec 退出 1、点名 SPEC、template.basis.SPEC 未动、selection.basis 自始无 SPEC → `--accept-source SPEC` 输出「在编排里刷新到…；索引保持不动」→ 再跑通过、template.basis.SPEC 已更新、人写的阅读主线一个字节没动 | 洞已闭合，且「谁记着谁更新」的边界正确 |
| 3a-R2 / R3 / R4 | 读了增量：`sameFile` 按解析后路径尾段比、不看 alt；`fencesOf` 遍历全部围栏并记闭合；`locateSection` 先精确再包含、包含层仍唯一。用例各有正反（含「alt 写成声明 ID 但引用另一张 → 仍报」这条我没要求的） | 一致 |
| 两条小项 | `form` 空值已查；骨架预填只取 `keep` | 一致 |

3a-R1～R4 关闭。执行者对全量计数的更正（一次运行的数字不当稳定事实）收下。

### closeout（3a）

- 最终设计：02 分册里新增的解析与装配全部作为函数落在 `story-sources.mjs`，`story-build.mjs` 只管 after-spec 的读写与输出：SPEC 单元并入索引且 `kind: derived`；template 首次落十章 body 起点、`basis` 由脚本填、只预填初筛 keep 且有归章的单元；已存在的编排不整份重写，basis 只补缺失键、已变来源按漂移报告，漂移判定取 selection.basis ∪ template.basis，`--accept-source` 只刷新记过该键的那几份；有效取舍只按一条规则合并、omit 与显式引用并存报冲突、replaced_by 禁自指与成环；单元分配「一处全文 / 两处以上进 shared 一份 / 其余索引行」按编排项判；structures 三种的声明校验、种子生成与落实检查（表按规范化列名包含、图遍历全部闭合围栏、图片核声明的那一张）；定位先精确再包含且唯一；`templateReadable` / `templateAssemblable` 两层谓词；`relatedTargets` 有草稿给草稿、没有给视图路径。`skeleton` / `chapter` / `prepare` 与六份提示词未动，v3 仍是唯一正式写作链。
- 实际修改：`story-sources.mjs`（+317 行代码，含从 story-build 迁入的 `norm`/`tableHeaders`）、`story-build.mjs`（净 +117：after-spec 分支与编排块、`writeTemplateBasis`、`behind()`、`acceptSource` 重写；迁出两函数与不可达路径）、`test_story_template.py`（新建，52 例）。
- 验证：见两次评审的核对表；金样夹具 after-spec 索引 65 单元与金样索引一致。
- 剩余限制：① `sources --stage after-spec`、编排谓词、结构检查、视图分配都只有命令级/函数级证据，流程尚未路由到它们——3a→3b 的明确中间态，3b 收口时 03 §5 必须成立；② 真实 CLI 未跑；③ 02-N1 `DERIVED_KEYS`、02-N4 v3 文案归 3b。
- 规模：scripts_mjs 3266→3700（+434），总量 11017；本步退出量为零。2.3 累计 scripts_mjs +875，全部退出集中在 3b，届时逐函数对账；收口时按总方案 §7 专项审视。
- 本步问题反思：四条返修里两条（R1、与 02-R1 同形）是「补新记录」和「对齐旧记录」写成一句，两条（R3、R4）是同类对象 ≥ 2 的漏判——都是评审在合同逐函数对照时发现的，说明 3a 这种「先做函数」的拆法让评审能对着合同一条条核，比一笔大 diff 更容易抓到这类。执行者的反思（不一致本身是信息，能自动对齐的差异先问消失之后谁还知道）值得写进 3b 的实施前审视。

**批准提交。** 纳入：`story-sources.mjs`、`story-build.mjs`、`test_story_template.py`；不带工作区里他人的改动。提交后 `advance --step-id step-03b-entry-switch --step-file steps/step-03b-entry-switch.md`。
