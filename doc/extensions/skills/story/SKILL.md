---
name: story
description: /story 需求流程编排——init 拉取需求资料并生成 AR/design.md、成文归档叙事件、archive 归档评审载体、restore 回退归档覆盖、review 拉回评审反馈。
---

# story — 需求开发流程编排

本文件只讲**链条怎么走、关卡怎么判、产物各是什么**。
各步的作业规则在 `rules/` 与 `phases/`，命令由脚本自己打印，不在这里复述第二遍。

`/story adapt` 不在本文件——它是把本扩展装到／升级到别的工程的工程运维动作，
与需求流程无关，见 [../story-adaptation/SKILL.md](../story-adaptation/SKILL.md)。

## 链条

```
S1 取材        →  拉三套材料、建工作区骨架
S2 导入+初析   →  列 inbox → 导入 → 材料盘点 →（材料确认后）需求分析
S3 三级关卡    →  材料够不够 → 范围怎么定 → 承载哪份
S4 收口        →  按已定范围生成 AR/design.md，契约置 complete
   ↓
[framework spec 阶段闭环]
   ├─ 阶段内一次 pass 产出三份：spec.md / AR/review.md / AR/story.md
   └─ story：建骨架 → 按章写、按章落盘 → 统稿 → `story_flow.py story` 登记
   ↓
S5 归档        →  /story archive 上传叙事件与评审记录
```

**`/story <AR>` 的启动语义 = 做到 spec 闭环并通过交付门**（归档送审与进入 plan 由用户在交付门之后选）。这一句是本扩展对 framework 推进策略的
batch 多阶段声明（`framework/skills/reference/user-confirmation-ux.md` §8.1 第 2 条、§8.2）：
声明范围 = 从取材到 spec 阶段闭环、再到 `/story archive`。**范围之内不再逐阶段要授权**，
超出这个范围（plan 及其之后）仍按 framework 的默认策略停等。
`status` 在收口那一步会把这句声明原样打出来。

**位置由契约回答，不靠回忆**：`story_flow.py status --feature <AR>` 读契约给出 `next`
与下一步动作。中断后不要凭记忆重建位置。

**先做完对应产物，再问对应问题**：盘点完材料才问材料够不够，分析完范围才问范围怎么定
——人裁决的是**结果**不是预测。反过来，**材料没确认就别做需求分析**：材料一变，分析全废。

### 各步的规则在哪

| 步 | 规则 |
|---|---|
| S1 骨架与占位件判读 | 本文「初始化」节 |
| S2 导入 | [rules/inbox_import.md](rules/inbox_import.md) |
| S2 初析与流程契约 | [rules/init_analysis.md](rules/init_analysis.md) |
| S3 三级关卡 | [rules/scope_gate.md](rules/scope_gate.md) |
| S4 生成 design.md | [rules/ar_design_init.md](rules/ar_design_init.md) |
| spec 阶段作业（含成文顺序） | [phases/spec.md](phases/spec.md) |
| 成文：按章写与统稿 | [phases/story-write.md](phases/story-write.md) |
| 评审回流 | [rules/review_reflow.md](rules/review_reflow.md) |

## 推进契约

**这一节是本扩展里推进授权的唯一定义**，各阶段须知与作业书只引用它、不复述。

### 授权分两层

| 层 | 谁说了算 | 怎么推进 |
|---|---|---|
| **story 流程段内**：S1→S4、spec 阶段内的成文与登记、S5 归档 | 本节 | 用户启动 `/story` 即构成明示授权，段内按契约 `next` 一路走完，不逐段问 |
| **framework 阶段之间**：spec 闭环 → plan 及之后 | framework 的推进策略 | 本节管不着，见下 |

**story 契约 `next` 覆盖的就是第一层**：`init → 材料 → 关卡 → design.md → spec 闭环
（三份产物）→ 归档`。它不驱动 plan 及之后——那属于 framework 的阶段边界。

**第二层不另造一套授权，也不替它问。** framework 的推进策略解析的是**用户消息**，
扩展写什么都改变不了它的判定结果。所以用户的目标越过 spec 时（例如「做到 plan」
「全链路交付」），那是 framework 阶段边界要处理的事——**本扩展既不问也不判**。

**S4 收口之后直接进 spec，不问。** 本轮的终点在 `/story` 启动时就声明了（见上「启动语义」）：
做到 spec 闭环并归档。在流程中途再问一遍，是把一个已经有主的问题重问一次，
而它固定长在 S4 收口处——那就是第三个停等点。

### 停等点：只有两处，都无条件

本扩展**新增的**停等点只有这两处，此外一律不问：

| # | 停在哪 | 什么时候停 |
|---|---|---|
| 1 | **材料关卡**（`material_scope`） | `init` 之后**必停**，无论材料看起来够不够 |
| 2 | **范围关卡**（`scope_decision` 及其追问 `split_carrier`） | **必停**。切法与承载哪份是同一次对话里的追问，算这一处 |

**两处都是无条件的。** 「要不要停」不由判断材料够不够、范围有没有变来决定——
那等于把停等的开关交给被停的那一方。你的判断只进**选项推荐**，定不定由人。
脚本层也这么拦：三级关卡的决策**只认人签**，`decide --by` 没有 AI 这一档。

**补料之后不再问第二遍**：人选「补充材料」就是对「材料够不够」的回答。
新一轮照样**重新盘点**（那是你的活），但盘点结果没有新缺口时直接进需求分析——
`status` 会把 `next` 给成 `run_analysis`。
盘出**新的**缺口时才再停一次：把新选项写进选项侧车（`gate` 写 `material_scope`），
`next` 随之回到材料关卡。所以这一处停几次由材料状态决定，不由轮次决定。

侧车必须写明是给哪一级摆的——三级共用一个文件名，不写明的话，你为范围关卡摆的选项
会被材料关卡读成「材料上又出了新缺口」，流程被拨回上一级而下一步的 `decide` 被挡住。

**签与导入不分先后**：`decide --chosen supplement` 看的是料到没到——inbox 里有未导入的，
或材料指纹已经变了，两者有一个就成立。需求方把料放好再回一句「已放进去了」，
和先签这一笔再去放料，都是同一件事。

「门禁报错了要不要修」「check 过了下一步做什么」「进 harness 还是进 verifier」
「这一步做完了要不要继续」**都不是停等点**——那是义务不是选择题。

**verifier PASS 之后的顺序是固定的**：`check-receipt` →
`story-build check --deliver`（交付门）→ **停下问一次**：归档送审、进入 plan，
或先归档再进 plan（本地单只有进 plan）。**中间不再跑 harness**。harness 每跑一次都重新派生 subject，换了代就要重审，
而产物一个字节没动。只有 `check-receipt` 报 subject 失配时才重跑 harness，
并且那之后 verifier 要再来一次。
**完成回执不用你填**：它是 harness 的只读投影，`check-receipt` 自己生成并校验。

### 停等消息怎么写：三段，不超过 12 行

人在这里只做一个动作——选一项。让他为此读三十行，就是把成本从你这边挪到他那边。

```
<一句现状>                    盘点/分析做完了什么，一句话
<一句缺口或问题>              要他定的是什么，结论句
1. <选项>（推荐）             每项一行，推荐标出来
2. <选项>
```

**不放**：材料总表（清单在 `init-analysis.md` 里，要看他会去看）、已经说过的事、
流程解释、命令、文件路径、判据名。选项文字写成他的话——「不拆，整体承载」，
不是「carry_all」。

需要展开的证据留在产物里：他要细节时会去读 `AR/init-analysis.md`，
那是它存在的理由。

### 失败出口（不是确认点）

停下来说「我修不动了」不是问人要授权，是**报告修不动、请人接手**。它有前提，
而且前提是**可核的**，不是自述：

> 同一判据类在 `story-build check` 的**连续三次运行**里都报了，且三次之间产物
> 确有改动。判据类有名字（check 的报错按类分组输出），所以「同一处」核得出来。

不满足这个前提就不是合法停等——**照报错文案修，改完重跑**。
写成「同一处连续 3 次修不好」而由你自己判的话，试一次就能宣布修不好然后合法停下，
那和把停等开关交给被停方是同一个毛病。

### 既有确认点（不计入上面两处）

归档、恢复这类不可逆或覆盖线上内容的操作，有它们**既有的**确认点。
那不是本扩展新增的停等，按各自的规则走。

### 成文到闭环的衔接链

`story-build check` 通过之后，到阶段闭环是**一条义务链，链内没有停等点**：

```
check 通过 → 取本阶段作者要求 → 写产物 → 主 agent 自己跑 harness
          → 结构级 PASS → 主 agent 主动触发 verifier → 闭环
```

**作者要求怎么取**：原则页是 `doc/extensions/hooks/<阶段>/author.md`（六个阶段各一份）；
spec 阶段另有**本次任务包**，动笔前跑 `node doc/extensions/hooks/spec/author.mjs --feature <名>`
拿到——你现在在哪、本轮激活几条、材料里有哪几张图、十章各答什么、哪些词不能用，都在里面。

`check` FAIL 时按报错文案修，改完重跑，直到通过或触发**失败出口**（见上，有可核前提）。
报错文案自带「缺什么 / 写到哪 / 怎么写」，不需要问该不该修。

## 初始化

- **输入**：AR 单号 + `<mcp-token>`（取法见「需求系统 Token」）
- **输出**：`doc/features/<AR>/` 下的 `RR/` `SR/` `AR/` `inbox/` 四个目录与骨架文件

```bash
node doc/extensions/skills/story/scripts/story.js init <AR> <mcp-token>   # ① 取材
python doc/extensions/skills/story/scripts/story_flow.py init --feature <AR>  # ② 建骨架
```

**② 是骨架的唯一写入者**：缺什么补什么，已有的一律不动，重跑安全。

**看骨架判材料**：`RR/prd.md`、`SR/design.md` 是正文还是占位件（占位件正文写着
「本文档未从需求系统拉取到」）。有占位件就当缺料，请用户把对应文档放进 `inbox/` 走导入；
全是占位件且 ① 报「查无此单」时，停下问人先确认单号。

**没有需求系统单据时**（问题单、别人发来的需求文档）：入口不变，仍是 `/story init <编号>`。
非 `AR` 开头的编号不碰需求系统，跳过 ①、直接建骨架。
**本地单没有归档环节**——交付终点是仓内的 `spec/spec.md` + `AR/story.md` + `AR/review.md` 三件，
走到归档时直接告诉用户这一点，不必尝试。

## 归档

- **前置**：spec 阶段已闭环（成文态 `status = story_written` 在那时登记），`AR/story.md` 与 `AR/review.md` 齐备
- **不适用于本地单**（见「初始化」）
- **archive 不修改工作区任何文件**，可以放心执行

```bash
node doc/extensions/skills/story/scripts/story-build.mjs check --deliver --feature <AR>   # ① 交付门：回执 + 读者审查形态
node doc/extensions/skills/story/scripts/story.js archive <AR> <mcp-token>        # ② 上传
python doc/extensions/skills/story/scripts/story_flow.py archived --feature <AR>  # ③ 登记
```

**③ 登记之后**，`AR/review.md` **归人所有——只备份，不重建**，评审人的线上批注与
`/story review` 拉回的回稿都留在里面。③ 自带 ① 的门禁，通过才登记；登记不可逆。

**决策件带着未勾的议题去归档是常态路径**——评审的形态就是评审人在线上批注表态，
归档正是送审动作。归档时提示一句即可，**不停等确认**。

## 恢复

`node .../story.js restore <AR> <mcp-token>`——把需求系统上的正文恢复到上一版，
回退 archive 那次覆盖。本地工作区不参与。

## 检视

`/story review <AR>` 把评审人在系统上留下的反馈拉回来，写入 `AR/review.md`（先备份原件）。

评审表态由评审人填写——**你不代填表态、不动人工区**。人可能在系统上批注，也可能直接改本地
文件：**流程不关心来源，模型的输入唯一就是 `AR/review.md`**。处置前完整读一遍
[rules/review_reflow.md](rules/review_reflow.md)。产物是 `AR/review-disposition.json`
与被修订的 `spec/spec.md`；**`AR/story.md` 与归档件不动**——story 定稿于评审时点。

## 交互关卡语义（所有关卡统一适用）

**关卡是讨论的收敛点，不是选择题的交卷处。** 决策权在人、笔在 AI——
AI 依据人的决定写回文件，不要求用户手动编辑文件或运行脚本。

**呈现**：摆出分析结论与可选方案，每项写清它意味着什么。有确认组件就用组件，
没有就输出 portable 编号菜单，按宿主**能力**判断，同一轮消息内给全。
选项标签要自带执行前提：**选中它的那一刻脚本会去校验的动作，必须写进标签**
（写「我已把材料放进 `<完整路径>`」，不写「补充材料后继续」——后者读起来像「我打算去补」，
而脚本当场就要检查目录）。

**人回应之后**只有两条路：

- **回应对上了某一项** → 跑 `story_flow.py decide` 落契约（`basis` 引他的原话），按 `next` 继续。
  `rejected`（退出码 2）是「记下了但不能按它走」：按脚本给的补救动作**原地重提同一个关卡**，
  不前进、不换题；
- **回应给出新诉求** → **这是讨论的开始，不是待映射的答案**。去做分析、把方案摆出来讨论清楚，
  收敛了再记录。

**三条底线**：

1. **人确认前不记录、不往下走。** 你需要写一段推理才能把他的话对上某个选项，说明还没确认，去问；
2. **他已经确认过的事不再问第二遍。** 记录完照 `next` 直接做；
3. **「按推荐走、别逐个问」免不掉这两级。** 免掉的是流程段内其它一切询问；
   材料与范围仍然停——定错了后面全废，它们值得那两次等待。

**选项集必须落进契约**——它是给人事后推翻用的：只记选中项的话，
「看过选项后选了不拆」与「压根没生成拆分选项」事后完全同形。

## 产物定位

| 产物 | 回答什么 |
|---|---|
| `RR/prd.md` | 业务上为什么做、要什么价值（外部输入） |
| `SR/design.md` | 整体方案、三方分工、系统级约定（外部输入） |
| `AR/upstream.md` | 人工补录的本部件上游材料（外部输入） |
| `ux-reference/` | 界面参考图与设计基准（外部输入） |
| `AR/init-analysis.md` | 关卡决策的支撑分析（**非交付件**：/spec 不读、归档不含） |
| `AR/story-src/materials.json` | 手上有哪些材料、各自的身份与版本；收件箱里哪些原件还没并入正文 |
| `AR/story-flow.json` | init→归档的流程契约：每轮的材料版本、并入与决策（谁、何时、依据） |
| `AR/design.md` | 上游要**本部件（本 AR 范围内）**做什么 |
| `spec/spec.md` | 本部件**要做什么**（需求侧规格，意图 SSOT） |
| `AR/review.md` | 上线要定什么、评审看过什么、评审定了什么（**人的决策**，AI 不得覆盖） |
| `acceptance.yaml` | 怎么算做对了 |
| `AR/story.md` | 把上述组织成可评审的叙述（派生物，零新事实） |

`spec` 与 `review` 是 spec 阶段**并列**交付物，不是上下游——前者 AI 写、后者人写。

| | `AR/design.md` | `AR/story.md` |
|---|---|---|
| 流程角色 | 输入端：/spec 的输入（从四源提取，按本 AR 范围裁剪） | 输出端：spec 阶段内逐章渲染成的评审载体（面向人） |
| 归档语义 | 工作区里身份唯一：「上游提取件」，不承载归档产物 | archive 的上传正文（与 `AR/review.md` 一并上传） |

## 需求系统 Token

`story.js` 的每条命令都要 `<mcp-token>`。按顺序取，取到即用：

1. 跑 `node doc/extensions/skills/story/scripts/token.js`——exit 0 时 stdout 即 token；
2. 读 `~/.cac.json` 或 `~/.claude.json`（Windows 在 `%USERPROFILE%\` 下）：先看顶层
   `mcpServers.requirement-mcp.headers.X-MCP-Token`，再看
   `projects.<当前工程路径>.mcpServers.requirement-mcp.headers.X-MCP-Token`；
3. 都没有就向用户要，拿到后写入 `~/.cac.json` 顶层 `mcpServers.requirement-mcp`
   （`type: http`、`url` 为需求系统的 MCP 地址、`headers.X-MCP-Token` 为 token），
   只增改这一项、其余原样保留，写完继续执行原命令。

要 token 时对用户说明：需要需求系统的访问 token 才能拉取需求单，请到需求系统的
token 管理页申请后发给我，配一次以后都不用再配。
