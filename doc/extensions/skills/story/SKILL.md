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
   └─ story：分配落点 → 逐章渲染 → 裁决 → `story_flow.py story` 登记
      （子 agent 可选，宿主没有 Task 工具时主 agent 自己做）
   ↓
S5 归档        →  /story archive 上传叙事件与评审记录
```

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
| 成文：分配与逐章渲染 | [phases/story-write.md](phases/story-write.md) |
| 成文：裁决者怎么裁 | [phases/story-verify.md](phases/story-verify.md) |
| 评审回流 | [rules/review_reflow.md](rules/review_reflow.md) |

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
node doc/extensions/skills/story/scripts/story-build.mjs check --feature <AR>      # ① 门禁
node doc/extensions/skills/story/scripts/story.js archive <AR> <mcp-token>        # ② 上传
python doc/extensions/skills/story/scripts/story_flow.py archived --feature <AR>  # ③ 登记
```

**③ 登记之后**，`AR/review.md` **归人所有——只备份，不重建**，评审人的线上批注与
`/story review` 拉回的回稿都留在里面。③ 自带 ① 的门禁，通过才登记；登记不可逆。

**决策件处于「草稿（待开发确认）」是常态路径**——评审的形态就是评审人在线上批注表态，
归档正是送审动作。归档时提示一句即可，**不停等确认**。

## 恢复

`node .../story.js restore <AR> <mcp-token>`——把需求系统上的正文恢复到上一版，
回退 archive 那次覆盖。本地工作区不参与。

## 检视

`/story review <AR>` 把评审人在系统上留下的反馈拉回来，写入 `AR/review.md`（先备份原件）。

评审表态由评审人填写——**你不代填表态、不改状态行**。人可能在系统上批注，也可能直接改本地
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
3. **用户明说「按推荐走、别逐个问」就照办**，但 `scope_decision` / `split_carrier`
   **代选永远不选拆分**——拆分改变的是交付边界，那是对后续单据的承诺，只能由人拍板。

**代替人做的选择，报告一个字不少**：采用了哪一项、依据是什么。
选项集无论人选还是代选都要落进契约——**它是给人事后推翻用的**。

## 产物定位

| 产物 | 回答什么 |
|---|---|
| `RR/prd.md` | 业务上为什么做、要什么价值（外部输入） |
| `SR/design.md` | 整体方案、三方分工、系统级约定（外部输入） |
| `AR/upstream.md` | 人工补录的本部件上游材料（外部输入） |
| `ux-reference/` | 界面参考图与设计基准（外部输入） |
| `AR/init-analysis.md` | 关卡决策的支撑分析（**非交付件**：/spec 不读、归档不含） |
| `AR/story-flow.json` | init→归档的流程契约：每轮的输入、导入与决策（谁、何时、依据） |
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
