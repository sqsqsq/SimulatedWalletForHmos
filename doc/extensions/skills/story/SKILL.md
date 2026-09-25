---
name: story
description: /story 需求流程编排——init 拉取需求资料并建工作区骨架、成文归档叙事件、archive 归档评审载体、restore 回退归档覆盖、update 承接新材料、评审回流、人的新决定与直接改稿，更新已有产物。
---

# story — 需求开发流程编排

> 读者：执行 `/story` 的主 agent。时机：启动 `/story` 时读一遍；中途只按 `status` 的 `next` 回到对应规则页。

本文件只讲**链条怎么走、在哪停、产物各是什么**。各步的作业规则在 `rules/` 与 `phases/`，
命令由脚本自己打印，不在这里复述第二遍。`/story adapt` 是把本扩展装到别的工程的运维动作，
见 [../story-adaptation/SKILL.md](../story-adaptation/SKILL.md)。

## 链条

```
S1 取材        →  拉三套材料、建工作区骨架
S2 导入+初析   →  列 inbox → 导入 → 材料盘点 →（材料确认后）有会议时读会，有要人定的话题停一次 → 需求分析
S3 关卡        →  材料 →（会议）→ 范围怎么定 → 承载哪份
S4 收口        →  按已定范围写提取稿，`complete --from` 提交为 AR/design.md、契约置 complete
   ↓
[framework spec 阶段闭环]
   ├─ 阶段内一次 pass 产出三份：spec.md / AR/review.md / AR/story.md
   └─ story：起手 → 写写作设计 → 照骨架按章写、按章落盘 → 回看 → `story_flow.py story` 登记
   ↓
S5 归档        →  /story archive 上传叙事件与评审记录
```

**位置由契约回答，不靠回忆**：`story_flow.py status --feature <AR>` 读契约给出 `next` 与下一步动作。

**先做完对应产物，再问对应问题**：盘点完材料才问还缺什么，分析完范围才问范围怎么定——人裁决的是结果不是预测。
**材料确认后再做需求分析**：材料一变，分析全废。

| 步 | 规则 |
|---|---|
| S1 骨架与占位件判读 | 本文「命令入口 · 初始化」 |
| S2 导入 | [rules/inbox_import.md](rules/inbox_import.md) |
| S2 读会（导入了会议材料时） | [phases/meeting-read.md](phases/meeting-read.md) |
| S2 初析与流程契约 | [rules/init_analysis.md](rules/init_analysis.md) |
| S3 关卡怎么摆 | [rules/scope_gate.md](rules/scope_gate.md) |
| S4 写提取稿并提交 | [rules/ar_design_init.md](rules/ar_design_init.md) |
| spec 阶段作业（含成文顺序、verifier 与交付门） | [phases/spec.md](phases/spec.md) |
| 成文：写作设计、按章写与回看 | [phases/story-write.md](phases/story-write.md) |
| 产物更新 | [phases/update.md](phases/update.md) |

**作者要求怎么取**：原则页是 `doc/extensions/hooks/<阶段>/author.md`（六个阶段各一份）；
spec 与 plan 阶段另有**本次任务包**，动笔前跑 `node doc/extensions/hooks/spec/author.mjs --feature <名>` 或 `node doc/extensions/hooks/plan/author.mjs --feature <名>` 拿到。

## 推进契约

**这一节是本扩展里推进授权的唯一定义**，各阶段须知与作业书只引用它、不复述。

**`/story <AR>` 的启动语义 = 做到 spec 闭环并通过交付门**。这是本扩展对 framework 推进策略的
batch 多阶段声明（`framework/skills/reference/user-confirmation-ux.md` §8.1 第 2 条、§8.2）：
**范围之内不再逐阶段要授权**，超出这个范围（plan 及其之后）仍按 framework 的默认策略停等。
`status` 在收口那一步会把这句声明原样打出来。

| 层 | 谁说了算 | 怎么推进 |
|---|---|---|
| **story 流程段内**：S1→S4、spec 阶段内的成文与登记、S5 归档 | 本节 | 用户启动 `/story` 即构成明示授权，段内按契约 `next` 一路走完，只在下表列的地方停 |
| **framework 阶段之间**：spec 闭环 → plan 及之后 | framework 的推进策略 | 它解析的是用户消息，本扩展既不问也不判 |

**S4 收口之后直接进 spec，不问**：本轮的终点在启动时就声明了，中途再问是把一个已经有主的问题重问一次。

## 停等真值表

整条链只在这几处停，**这张表是全部停等点的唯一清单**；表外一律不问。「门禁报错了要不要修」「check 过了下一步做什么」
「进 harness 还是进 verifier」「这一步做完了要不要继续」**都不是停等点**——那是义务不是选择题。

| 停在哪 | 谁问、何时问 | 选项来源 | 怎样记录 |
|---|---|---|---|
| **材料关卡**（`material_scope`） | 你问。第一轮必停；此后只在你拿新材料重新盘出缺口时停；`/story update` 的输入阶段每次必停一次 | 两项固定，顺序与标签来自章节合同；推荐由脚本按你写的缺口文件算 | `decide --ask --reply` |
| **会议裁决**（`meeting`） | 你问。材料确认之后，会议判断里有带 `question` 的话题时停一次，逐话题 | 会议判断里那个话题的选项 | 同上，另加 `--meeting --item` |
| **范围关卡**（`scope_decision` 及追问 `split_carrier`） | 你问。需求分析之后必停；切法与承载哪份是同一次对话里的追问 | 契约里需求分析定下的选项集；份表 | 同上 |
| **术语确认**（framework 的关卡） | 你问。spec 阶段写术语表时，交互态下请人逐条确认 | spec §0 术语映射表 | 人确认之后才勾 `[x]`；人没确认的不勾 |
| **视觉 provider**（framework 的个人设置询问） | framework 在阶段入口问 | framework 给的候选 | 人答了用 framework 的 `record-visual-provider` 落盘 |
| **交付门之后** | 你问。`story-build check --deliver` 通过后问一次：「归档送审 / 进入 plan」（本地单只有进 plan）。用户开场说做到送审或做到评审时，这一问就是本轮终点的停等 | 交付门打印的选项 | 人选归档就走「命令入口 · 归档」 |
| **查无此单** | 你问。全是占位件且取材报「查无此单」 | 确认单号 | 按人给的单号重取 |
| **归档、恢复** | 你问。不可逆或覆盖线上内容的操作 | 各自的既有确认点 | 按各自的既有确认点 |

**停等的开关不交给被停的那一方**：「要不要停」不由判断材料齐不齐、范围有没有变来决定。你的判断只进推荐与提议，定不定由人。

### 问法由脚本出

到了停等点，`story_flow.py status` 除 `next` 之外返回 `ask`（问法编号 `ask_id`、编号选项、推荐、缺口）并写侧车。
停等消息三段：

```
<一句结论与缺口>              盘点或分析做完了什么、要人定的是什么
<ask.block 原样>              选项一项一行，推荐单独一行「推荐：n（理由）」
```

**不放**：材料总表（在 `init-analysis.md` 里）、已经说过的事、流程解释、命令、文件路径、判据名。选项标签不改写、不调顺序。
有确认组件就用组件，没有就给编号菜单，同一轮消息内给全。

**人签只来自人的回话**：人答了之后跑 `decide --gate <本级> --ask <ask_id> --reply "<人的原话>"`。原话写了编号或标签，
脚本照它映射；原话是他自己的话，加 `--chosen <编号>` 写明他选的是哪一项。没有当前问法的人签写不进契约。
`rejected`（退出码 2）是「记下了但不能按它走」，按脚本给的补救动作原地重问同一个关卡。
回应给出新诉求 → 这是讨论的开始：去分析、把方案摆出来，收敛了再问。**人确认前不记录、不往下走**；他已经确认过的事不再问第二遍。

**你自己的判断记成提议**：`decide --gate <本级> --propose --chosen <编号> --why "<理由>"` 记为 `by: model`，
流程不因它前进；下一次停等时脚本把它列进问法，请人确认。「按推荐走、别逐个问」免不掉材料与范围这两级——定错了后面全废。

**流程契约只由脚本写**：`story-flow.json` 带自身摘要，手改会被报出来并给恢复路径；要改一笔记录，用对应命令重新记。

### 失败出口（不是停等点）

停下来说「我修不动了」是**报告修不动、请人接手**。它的前提是可核的：同一判据类在 `story-build check` 的
**连续三次运行**里都报了，且三次之间产物确有改动。不满足就不是合法停等——照报错文案修，改完重跑。

## 命令入口

### 初始化

- **输入**：AR 单号 + `<mcp-token>`（取法见「需求系统 Token」）
- **输出**：`doc/features/<AR>/` 下的 `RR/` `SR/` `AR/` `inbox/` 四个目录与骨架文件

```bash
node doc/extensions/skills/story/scripts/adapters/story.js init <AR> <mcp-token>   # ① 取材
python doc/extensions/skills/story/scripts/core/story_flow.py init --feature <AR>  # ② 建骨架（唯一写入者，重跑安全）
```

① 失败就停下，报出它的 `error`，不建骨架。

**看骨架判材料**：`RR/prd.md`、`SR/design.md` 是正文还是占位件（正文写着「本文档未从需求系统拉取到」）。
有占位件就当缺料，请用户把对应文档放进 `inbox/` 走导入。

**没有需求系统单据时**（问题单、别人发来的需求文档）：入口不变，仍是 `/story init <编号>`。
非 `AR` 开头的编号不碰需求系统，跳过 ①、直接建骨架。**本地单没有归档环节**——交付终点是仓内的
`spec/spec.md` + `AR/story.md` + `AR/review.md` 三件。

### 归档

- **前置**：spec 阶段已闭环，`AR/story.md` 与 `AR/review.md` 齐备；不适用于本地单
- **archive 不修改工作区任何文件**

```bash
node doc/extensions/skills/story/scripts/core/story-build.mjs check --deliver --feature <AR>   # ① 交付门
node doc/extensions/skills/story/scripts/adapters/story.js archive <AR> <mcp-token>        # ② 上传
python doc/extensions/skills/story/scripts/core/story_flow.py archived --feature <AR>  # ③ 登记（自带 ① 的门禁，不可逆）
```

② 失败就停下，不做 ③ 登记。

**③ 登记之后**，`AR/review.md` **归人所有——只备份，不重建**。决策件带着未勾的议题去归档是常态路径：
评审的形态就是评审人在线上批注表态，归档时提示一句即可，**不停等确认**。

### 恢复

`node .../story.js restore <AR> <mcp-token>`——把需求系统上的正文恢复到上一版，回退 archive 那次覆盖。

### 更新

`/story update` 承接一切让已有产物不再成立的依据变化，**只有这一个入口**：

| 变化 | 怎么进来 |
|---|---|
| 新材料 | 人放进 `inbox/`，或系统需求经取材取回，走导入链 |
| 评审回流 | 评审人在 review.md 人工区表态；系统需求的评审回稿经取材取回 |
| 人的新决定 | 人在对话里说的，经 `decide --update` 记原话 |
| 有人直接改过的文档 | 八项比较报出来 |

- **前置**：这个单已经有产物（Spec / Story / Review / Plan 至少一样）
- **取材不写业务文件**：取回的只往本单 `inbox/` 放；`AR/review.md` 里人刚写的意见原样留着，改哪些产物由读过原文的你与人决定

```bash
python doc/extensions/skills/story/scripts/core/story_flow.py update --feature <编号> --action status    # ① 续行状态与本需求的 paths
node doc/extensions/skills/story/scripts/adapters/story.js fetch <AR> <mcp-token> --project-root "<paths.project_root>" --out "<paths.inbox>"   # ② 取上游（系统需求必做）
python doc/extensions/skills/story/scripts/core/story_flow.py update --feature <编号> --action inputs    # ③ 报输入，材料关卡停一次问补料
python doc/extensions/skills/story/scripts/core/story_flow.py update --feature <编号> --action prepare   # ④ 比较并开这一轮
python doc/extensions/skills/story/scripts/core/story_flow.py update --feature <编号> --action close     # ⑤ 写好 update-notes.md 后收口
```

- **①** 有开着的更新（`open`）时按它的记录续做，本轮已经取过材的不再重复取。
- **②** 只对 AR 开头的系统需求执行，先按「需求系统 Token」取 token；两个路径取自 ① 返回的 `paths`，按当前 shell 加引号。
  这一轮没取过上游，③ 会停下并指回这一步。本地需求跳过 token 与 ②。取材成功与否以这一次调用 stdout 末行的
  `success` 与逐份状态为准：失败就停在这里，报出哪一份读取失败，不拿上一次的回执或「没有变化」代替。
- **③** 收件箱有新原件先导入、`round` 登记到本轮，再 ④；④ 见到未并入的原件会拒绝并列出文件。

**④ 八项真的没变**就报「未检测到变化」退出，不碰任何业务文件；有变化才把本次执行前的现场留一份，交你读原文判断。
整轮要撤回用 `--action restore`。每一步做什么、怎么判，完整一份在 [phases/update.md](phases/update.md)。

**人写过意见的议题，正文改了或被删了，渲染会停下来**：他答的是上一版的问题。
意思没变，请他确认沿用，用 `story_flow.py decide --feature <编号> --update <议题 id> --reply "<他的原话>"` 记一笔再重跑；
意思变了就让他重新看一眼那一条。

## 产物定位

| 产物 | 回答什么 |
|---|---|
| `RR/prd.md` | 业务上为什么做、要什么价值（外部输入） |
| `SR/design.md` | 整体方案、三方分工、系统级约定（外部输入） |
| `AR/story-src/upstream.md` | 人工补录的本部件上游材料（外部输入） |
| `ux-reference/` | 界面参考图与设计基准（外部输入） |
| `AR/story-src/init-analysis.md` | 关卡决策的支撑分析与来源初筛（**非交付件**；Spec 与成文从它的来源初筛起步） |
| `AR/story-src/story-template.md` | 本需求的整篇写作设计：阅读主线与每章骨架（作者写，成文登记时随稿冻结） |
| `AR/story-src/materials.json` | 手上有哪些材料、各自的身份与版本；收件箱里哪些原件还没并入正文 |
| `AR/story-src/story-flow.json` | init→归档的流程契约：每轮的材料版本、并入与决策（谁、何时、依据） |
| `AR/design.md` | 上游要**本部件（本 AR 范围内）**做什么（S4 提取件，/spec 的输入） |
| `spec/spec.md` | 本部件**要做什么**（需求侧规格，意图 SSOT） |
| `AR/review.md` | 上线要定什么、评审定了什么（**人的决策**，AI 不得覆盖）；与 spec 并列交付，前者 AI 写、后者人写 |
| `acceptance.yaml` | 怎么算做对了 |
| `AR/story.md` | 把上述组织成可评审的叙述（派生物，零新事实；archive 的上传正文） |

## 需求系统 Token

`story.js` 的每条命令都要 `<mcp-token>`。按顺序取，取到即用：

1. 跑 `node doc/extensions/skills/story/scripts/adapters/token.js`——exit 0 时 stdout 即 token；
2. 读 `~/.cac.json` 或 `~/.claude.json`（Windows 在 `%USERPROFILE%\` 下）：先看顶层
   `mcpServers.requirement-mcp.headers.X-MCP-Token`，再看
   `projects.<当前工程路径>.mcpServers.requirement-mcp.headers.X-MCP-Token`；
3. 都没有就向用户要，拿到后写入 `~/.cac.json` 顶层 `mcpServers.requirement-mcp`
   （`type: http`、`url` 为需求系统的 MCP 地址、`headers.X-MCP-Token` 为 token），
   只增改这一项、其余原样保留，写完继续执行原命令。

要 token 时对用户说明：需要需求系统的访问 token 才能拉取需求单，请到需求系统的
token 管理页申请后发给我，配一次以后都不用再配。
