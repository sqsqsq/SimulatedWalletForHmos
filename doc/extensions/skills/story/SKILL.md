---
name: story
description: /story 需求流程编排——init 拉取需求资料并生成 AR/design.md、archive 归档评审载体、restore 回退归档覆盖。内含 AR 生成规则与 spec 宿主扩展章节生成规则。
---

# story — 需求开发流程编排

指令与章节的对应关系见跳板（命令转化表）；本文件各章节按动作组织。数据对接（需求系统拉取/归档/备份）统一由 [scripts/story.js](scripts/story.js) 承担。

## MCP Token

脚本调用需求系统 MCP 需要 Token。按以下步骤获取：

### 步骤 1：脚本获取

```bash
node doc/extensions/skills/story/scripts/token.js
```

- exit 0：**stdout 即为 token**（纯文本，不是 JSON），直接作为后续 story.js 调用的 `<mcp-token>` 参数
- 非 0 退出：进入步骤 2

### 步骤 2：模型获取

从 `~/.cac.json` 或 `~/.claude.json`（Windows：`%USERPROFILE%\.cac.json`）按当前工程路径读取，位置为 `projects.<工程路径>.mcpServers.requirement-mcp.headers.X-MCP-Token`。

若读取不到，须告知用户：

> 未找到 MCP Token，请在 `%USERPROFILE%\.cac.json` 中为当前工程添加配置：
> ```json
> {
>   "projects": {
>     "<当前工程路径>": {
>       "mcpServers": {
>         "requirement-mcp": {
>           "type": "http",
>           "url": "https://mcp.wisedevops.huawei.com/requirement/mcp",
>           "headers": { "X-MCP-Token": "<你的Token>" }
>         }
>       }
>     }
>   }
> }
> ```
> Token 获取：https://wisedevops.huawei.com/app/toolhub/tokenManagement

---

## 初始化

- **输入**：AR 单号 + `<mcp-token>`（见「MCP Token」章节）
- **操作概要**：拉取 AR 及父 SR、根 RR 的需求详情与设计文档；`AR/design.md` 不存在则生成空模板（已有内容不覆盖）
- **输出**：

  | 目录 | 文件 |
  |------|------|
  | `doc/features/<AR>/AR/` | `detail.json` + `design.md` + `template.md` |
  | `doc/features/<AR>/SR/` | `detail.json` + `design.md` |
  | `doc/features/<AR>/RR/` | `detail.json` + `prd.md` |

  stdout 单行 JSON：`{"mode":"init","reqNo":"...","parentNo":"SR编号","rrNo":"RR编号","initNeeded":true,"success":true}`

```bash
node doc/extensions/skills/story/scripts/story.js init <AR> <mcp-token>
```

`initNeeded` 恒为 true（强制重新生成）。解析 stdout JSON：`initNeeded === true` → 执行「生成design.md」章节，完成后进入「init 完成后提示」。

> `AR/template.md` 是平台的模板骨架，属 init 的落盘产物；**它不是 design.md 的生成输入**——design.md 的结构以 [rules/ar_design_init.md](rules/ar_design_init.md) 的五段为准。

---

## 归档

- **输入**：AR 单号 + `<mcp-token>`；要求 `AR/story.md` 与 `AR/review.md` **两份都在**（缺任一即拒绝，无降级路径）
- **操作概要**：两份归档件过 `merge-story --check` → 备份系统当前正文 → 上传需求系统（`AR/story.md` 作正文、`AR/review.md` 作附件）+ 本地 `.archive/` 回执
- **输出**：stdout 单行 JSON `{"mode":"archive","reqNo":"...","archived":true,"backupPath":"...","verified":true,"success":true}`

**系统侧正文名固定为 `design.md`**——这也是 init 拉下来的是 `AR/design.md` 的原因。归档不是新建文档，而是覆盖系统上的这一份。`AR/story.md` → 系统正文的改名映射**由脚本内部完成**，skill 层只关心「story.md + review.md 两份归档」，不要求在工作区改名。

**archive 前后工作区 `AR/design.md` 字节不变**：脚本上传时会临时借用这个文件名，并在任何结果下还原。工作区里它的身份只有「RR+SR 提取件」一种。

**前置检查**：若决策件缺失或状态仍是「草稿」，先发起 Step 4 的确认关卡；用户明确选择「暂不确认、按现状归档」时才继续——此时叙事件带草稿水印归档，评审前须补确认。任一份缺失或未过 `--check` 即拒绝归档：缺就停，比默默传个次品强。

```bash
node doc/extensions/skills/story/scripts/story.js archive <AR> <mcp-token>
```

完成后按 JSON 回执向用户复述（是否归档成功、备份位置），并告知可用 `/story restore` 回退覆盖。

---

## 恢复

- **输入**：AR 单号 + `<mcp-token>`；要求有备份（仅 archive 之后可用）
- **操作概要**：从最新备份解析源数据，重新上传回需求系统，回退 archive 对**系统正文**的覆盖
- **输出**：stdout 单行 JSON `{"mode":"restore","reqNo":"...","restored":true,"verified":true,"success":true}`

**恢复的是平台侧文档，本地 `AR/design.md` 不变**——它本来就没被 archive 改过，无需恢复。

```bash
node doc/extensions/skills/story/scripts/story.js restore <AR> <mcp-token>
```

---

## 检视

**当前状态：尚未实现**，`/story review` 不可调用。

- **目标能力**：脚本从需求系统拉回评审人已填写的 review 内容，交给模型据此更新 `spec.md`。
- **接口占位**：`node doc/extensions/skills/story/scripts/story.js review <AR> <mcp-token>`，stdout 单行 JSON（`mode/reqNo/...`）。当前返回 `success:false` 并非 0 退出，接通后按此形状返回结果。
- **当前替代做法**：`build` 渲染出的 `AR/review.md` 由评审人**离线**逐条填写表态；AI 不代填表态、不改状态行。

> 实现前有几件事必须先解决：评审人表态没有反向回写 `decisions.json` 的通道；`review.md` 的人工区靠 HTML 注释锚点定位，经系统富文本往返可能丢失；状态行「草稿（待开发确认）」目前由 `build` 固定重渲染。

---

## 生成design.md

触发条件：init 的 stdout JSON 含 `initNeeded: true`，或用户明确要求重新生成。

生成规则以 [rules/ar_design_init.md](rules/ar_design_init.md) 为准，生成前完整阅读其四段内容：①本部件申明 ②交互方清单 ③提取原则 ④生成规则（含需求提取五段结构、上游信息类别清单、不做的事）。输入为 `RR/prd.md` + `SR/design.md`，产物落 `doc/features/<AR>/AR/design.md`。

---

## init 完成后提示

init 流程收尾（`AR/design.md` 就绪）后按「交互关卡语义」处理：

- 提问「下一步？」，选项 `1=进入 /spec` / `2=先修改 AR/design.md 再继续` / `3=暂停，稍后处理`；
- 选 1 时**同时告知 /spec 的输入清单**：`AR/design.md`（主输入）+ `RR/prd.md`（业务场景与验收意图）+ `SR/design.md`（跨部件交互、云侧接口、系统级存储；AR §4 上游索引的章节号指向此文件，须直读原文），随后引导执行 /spec；
- 选 2 协助修改后回到本关卡；选 3 结束本轮。

---

## 交互关卡语义（所有关卡统一适用）

**所有关卡都停等用户选择，AI 不得代答**——无论它是需要真人拍板的（spec 事实确认、事实抽查、上线决策、定稿），还是只选流程走向的（init 完成后下一步、是否立即归档）。决策权在人、笔在 AI：用户逐项选择，AI 依据其明确选择写回文件，不要求用户手动编辑文件或运行脚本。

呈现方式按宿主能力：确认组件（如 AskUserQuestion）可用时用组件；不可用时（如 opencode）输出 **portable 编号菜单**——同一轮消息内给出 `1=… / 2=…`，等用户回复编号。

---

## spec 阶段的三份产物（适用于所有 feature，与是否走 /story 无关）

spec 阶段是**一次 pass 产出三份文档**。切分判据是**谁是作者、写给谁看**：

| 文件 | 作者 | 持有什么 | 受众 | 归档 |
|---|---|---|---|---|
| `spec/spec.md` | AI | **代码要求** | **AI**（plan 编码 / test-plan 出用例）+ 门禁 | 否 |
| `AR/review.md` | AI 起草 + **人确认** | 以自然语言问题组织的审核记录（建议、依据、影响、责任人与可填写结果） | 人（评审者线上批注） | **是** |
| `AR/story.md` | AI 撰写 | 人类事实守恒的完整需求叙事（全局双层 + 规约索引附录 + 独立可读） | 人（评审者，只读） | **是** |

三份在同一次撰写中完成——上游取证上下文（SR / PRD / 约束规约）此时都在手上，散了再补代价高得多。spec 阶段门禁校验三份齐备，缺任一份即 BLOCKER。

> **story 不是 spec 的排版件**：两者共享约六成事实（场景 / 功能 / 异常 / 验收 / 非功能），这些**一条都不能少**（判据是覆盖，不是逐字）；story 在事实之上加的是 spec 里没有也不该有的东西——判断、权衡、风险、合规回显。

### Step 1 — spec.md：只装与代码有关的东西（AI 动作）

**判据一句话：与最终代码无关的内容，不进 spec。**

core spec 模板缺少交付流程要求 spec 承载的接口契约 / 存储 / 配置 / 埋点 / 依赖，须在 **§8 验收标准之后追加一章**——spec 阶段门禁会校验，缺章/缺小节/未填写即 BLOCKER：

- **§9 技术契约**（9.1 端云接口 / 9.2 数据存储 / 9.3 配置项 / 9.4 埋点 / 9.5 依赖变更）→ 给下游 AI。**一律表格**，每行一个编号实体；不涉及的写一行「不涉及 + 依据」。

0. **必读取证规则（BLOCKER）**：先完整阅读 [reference/evidence-rules.md](reference/evidence-rules.md)——各节的 信息源/提取步骤/输出规则/降级规则 以其为准；核心公式：**事实 = 变更意图 × 代码库现状**，只有意图没有现状比对的条目视为未取证。
1. **读取输入**（evidence-rules 信息源总表为准）：
   - `doc/features/<feature>/AR/design.md`、`RR/prd.md`、`SR/design.md`（存在时；SR 是对外面调用方 / 端云接口 / 系统级存储的取证源，按 AR「上游索引」精确定位）
   - `doc/architecture.md` + `doc/module-catalog.yaml`（代码库现状：模块边界、`key_exports`、依赖规则）
   - spec Scope 声明 `in_scope_modules` 对应的源码目录（按 evidence-rules 各节检索式扫描现状）
   - `doc/extensions/knowledge/constraints/`（合规判定的基准，见 Step 2）
2. **按模板生成**：模板见 [templates/spec-sections.md](templates/spec-sections.md)。
3. **填写规则（BLOCKER 级约束）**：
   - **结论具体到可按名回查**：写全接口名/存储键/事件名/配置项名/模块名/错误码——「`feature_entry_enabled`（管理台功能开关，新增）：默认 `false`…」而非「新增了一个管理台开关」；**代码库现状**（仓内文件路径、检索式零命中）是结论的组成部分，须写进正文；不涉及的小节写「不涉及 + 一句判断依据」，**禁止留空**；
   - **不写文档坐标**：不挂 `spec §x`/`SR §x`/`RR §x`/`AR §x`，小节之间也不用「见 A5」互指——改用事物的名字；约束规约写中文域名 + 编号 + 含义括注（`安全隐私规约 SEC-03（…）`）；
   - **数值标来源类型**：阈值/时长/次数三选一注明——`（上游约束：<文档名>）`/`（本工程设定，无上游依据）`/`（平台基线）`；标「上游约束」时门禁读 SR/RR 原文验证该数值真实存在；
   - **概念红线（客户端语境）**：禁用「灰度」「回滚」「回退」（版本层面）、「部署」「集群」「QPS/TPS/容量」「熔断限流」，**单独使用也算**。改说：功能开关关闭 / 开关管控 / 市场·管理台放量 / 端云接口请求量与触发频次评估 / 随版本发布。

### Step 2 — 合规判定：过程不落盘，只输出三样（AI 动作）

逐个读取 `doc/extensions/knowledge/constraints/` 下全部约束文件（`README.md` 有清单与 `applies_when`），按各文件「回显指引」逐条判定；`compatibility-checklist.md` 是兼容性逐项过表的数据源，「本部件适用性 = 不适用」的行不参与判定。

判定的**推演过程是工作底稿，三份文档都不写**。它只有三个出口：

| 判定产出 | 去哪 | 为什么 |
|---|---|---|
| **代码要求** | spec §7（新增「UX 适配要求」小节；§7.1 触发频次行；§7.2 存储兼容行；§7.3 补个人数据采集行） | 这类要求只在合规判定时才冒出来，spec 别处没有，漏了就到不了编码 |
| **需要人工选择的事项** | `AR/review.md` 中的自然语言问题（卡点排最前） | 每项给出建议、依据、影响、责任人与可填写审核结果；叙事件不得出现议程措辞 |
| **命中 / 不涉及的结论** | `AR/story.md` 的影响面与风险章（兼容性自检表 + 应用域约束符合性表） | 这两张表**零条代码要求**，纯粹是给评审者的完备性回显——放 spec 里就违反了「与代码无关的不进 spec」 |

### Step 3 — story.md：逐章装配的完整需求叙事（AI 动作）

输出 `doc/features/<feature>/AR/story.md`——**面向人的完整需求文档**。它与决策件一并上传，评审者只读本文
就能看懂完整需求与落地设计（不打开 spec/PRD/SE）。

**story 不是写出来的，是装配出来的**。撰写红线见 [rules/rules.md](rules/rules.md)（每条都标了执行通道）。

#### 3.1 起手：按章节合同注入源材料

```bash
node doc/extensions/skills/story/scripts/story-build.mjs scaffold --feature <feature>
```

它按 [contracts/story-chapters.json](contracts/story-chapters.json) 为每一章生成一个起手文件
`AR/story-src/chapters/<章节 id>.md`，并把该章声明的源章节**原样注入**进去（PRD / SE / spec / AR design）。
文件头的注释写明本章的必答问题与强制表达形态。合同为每个输入声明一组候选标题，
都未命中时降级注入整篇；某章声明了输入却一个都注不进来时 scaffold 失败。

> **为什么是章节粒度**：起手完整只保证初稿有料，保证不了终稿；能一次重写整篇，就能一次丢掉
> 整篇的细节。章节粒度让「一次写完整篇」这个动作不存在，每章的源与终稿始终一一对照。

#### 3.2 逐章转写

对每个章节文件：读文件头的必答问题 → 在 `source-material` 区块**之后**写转写正文。

- **区块原样保留**：它是对照基准，装配时会被自动剔除，不进归档件。章节是否完成看区块之外
  有没有正文，不看区块删没删；
- 源材料里的流程图、状态机、表格**保持同类形态与数量**，不得降级为箭头文字或摘要（装配会拦）；
- **任何决策性内容都不在正文下结论**——无论待定还是已定，先在
  `AR/story-src/decisions.json` 登记（见 Step 4），正文只写 `{{DEC-00X}}` 引用。
  story 讲需求是什么、为什么、怎么落地；决策由谁定、定成什么，归《决策与评审记录》；
- 被引用的规约与验收编号登记到 `AR/story-src/ids.json`（编号 + 标题与含义 + 本需求落点），
  标题与含义从权威约束文件读取，不得凭记忆编造；
- 每章写到足以支撑其必答问题为止，**不设篇幅上限**；避免无意义重复，但事实完整优先于篇幅。

#### 3.3 装配与校验

```bash
node doc/extensions/skills/story/scripts/story-build.mjs build  --feature <feature>   # ① 装配 story + 渲染 review
node doc/extensions/skills/story/scripts/story-build.mjs check  --feature <feature>   # ② 装配一致性
node doc/extensions/skills/story/scripts/merge-story.mjs --feature <feature> --check  # ③ 覆盖不丢 + 归档红线
```

`build` 会：拼接全部章节 → 渲染 `{{DEC-*}}` / `{{ID:*}}` 引用 → 渲染 story 的编号速查附录（三列）→
渲染或**追加** `AR/review.md` 的议题（已填写内容一个字节都不动）→ 写入装配指纹。

装配失败的情形（都是结构问题，报错会指出具体章节）：缺章、区块外无正文、形态或数量降级、
悬空 `{{DEC-*}}`、正文出现裸 `DEC-00X` 编号。

> **`AR/story.md` 是装配产物，不要直接编辑它**——要改内容就改章节文件再 `build`。
> 直接手改会被 `check` 发现（正文逐字比对 + 装配指纹）。

`--check` 与门禁只拦「评审者自己发现不了的伤害」：覆盖不丢、归档件红线、装配一致。
**形式好不好、叙述顺不顺、理由充不充分不在门禁里**——那些由人和独立评价者判断。
verifier 与 harness 照常跑（spec 阶段四件套不变），但结论不进归档件。

### Step 4 — 决策收集：让 review 成为本需求的决策全景（AI 动作）

`doc/features/<feature>/AR/review.md` 承载**人对决策的审核**（与 story.md 同为归档件，故同在 `AR/`）。
它由 `AR/story-src/decisions.json` 渲染而来，不手写——Step 3 的 `build` 已把每条登记的决策渲染成
议题块。你在这一步要做的是**把决策收齐**。

**review 是决策全景，不是待办清单。** 评审者需要先知道「本需求做了哪些决策、结论各是什么」，
才谈得上判断它们对不对。因此**已经有结论的决策同样要登记**（`status: "settled"`），
与待定项一样带表态位；已定不等于不必过目。

**逐类扫描收集**，五类来源缺一不可：

| 来源 | 找什么 |
|---|---|
| PRD 产品规则 | 阈值、默认值、开关策略、边界规则等直接约束实现的产品结论 |
| SE 技术约定 | 接口、存储、有效期、隔离、清理、兼容与恢复策略 |
| 工程设定值 | 无上游依据、由起草方设定的数字与默认值 |
| 约束规约命中项 | 合规判定中命中的规约及其落实方式 |
| 上线与协同 | 上线顺序、依赖是否阻塞、跨团队需知悉或配合的事项 |

**准入判据是实质影响**：开发必须理解、遵守或实现的结论就要登记，无论它来自上游已定、
既有约束还是本需求新设。纯粹复述事实、既不改变任何实现/数据/配置/验证/交付决策、
也不需要任何人表态的内容，才不登记。

**登记字段**：

```json
{"id": "DEC-001",
 "status": "open",
 "question": "<人在评审会上真会说出口的问题句>",
 "proposal": "<可直接审核的实质结论>",
 "rationale": "<依据：上游文档、约束规约、代码库现状，或说明为何是工程设定>",
 "impact": ["<受影响的验收编号>", "<受影响的章节>"],
 "source": "<上游已定 / AI 设定（无上游依据）/ 约束规约>",
 "decider": "<具体角色>"}
```

`status: "settled"` 的条目把 `proposal` 换成 `conclusion`（已定的结论），其余字段相同。
渲染时开放项排在前、已定项在「已定决策（请逐条过目）」一节。

**`question` = 人在评审会上真会说出口的问题或决策句**——形如「某某指标是否定为 X？」
「某某默认值是否由云侧下发？」。**禁止**写成「待定项 1 / 决策队列 / 实现契约 / DFX 与合规」
这类分类词；排序、来源、阻塞性是字段，不是标题。

**AI 不得预填表态结果**，也不改 `**状态**：草稿（待开发确认）`。人工审核、修改回写与定稿
属于「检视」章的职责，不在本流程内。

> 决策有增改时改 `decisions.json` 再 `build`：机器区按登记表重新渲染，
> 人工已填写的内容逐字节保留。

### 完成标准

- 三份产物齐备：`spec/spec.md` 含 §9 且各小节已填、`AR/review.md` 存在、`AR/story.md` 存在；
- spec 阶段 harness 零 BLOCKER；
- `story-build check` 通过（章节齐备、形态守恒、产物未被手改、议题与登记表一致）；
- `merge-story --check` 通过（共有区覆盖不丢、归档件红线无命中）；
- `AR/review.md` 为首版草稿，状态行保持「**状态**：草稿（待开发确认）」。

> 这四条全绿只说明没有明显缺陷，**不说明这是一份好的评审材料**——后者由人和独立评价者判断。

---

## story.js 契约（替换实现时必须保持）

`story.js` 与 `token.js` 是**部署环境自备**的数据对接层，不随本 skill 分发。本章是双方的接口约定：
skill 正文里所有对脚本输出的解析都以这张表为准，实现与之不符即为实现方的缺陷。

| 项 | 约定 |
|---|---|
| CLI | `node story.js <init|archive|restore|review|help> <AR> [mcp-token] [--project-root <abs>]`；成功 0 / 失败非 0 |
| stdout | 单行 JSON 结果（`mode`、`reqNo`、`success` 必有；失败 `{"mode":"...","reqNo":"...","success":false,"error":"..."}`）；人类可读日志走 stderr；help 例外（纯文本） |
| mcp-token | 第三位置参数，`token.js` 获取（见「MCP Token」章节；其 stdout 即 token 本身）；缺失即失败 |
| init | 拉取 AR 及父 SR、根 RR：各自 `detail.json`，加 `RR/prd.md`、`SR/design.md`、`AR/template.md`（幂等）；`AR/design.md` 不存在→生成空模板（已有内容不覆盖）；`initNeeded` 恒 true；JSON 含 `parentNo/rrNo` |
| archive | `AR/story.md` 与 `AR/review.md` 缺任一即失败、未过 `merge-story --check` 即失败（**无降级路径**）；备份系统当前正文；`AR/story.md` 改名为系统正文 `design.md` 上传、`AR/review.md` 作附件；须落本地 `.archive/` 回执；**archive 前后工作区 `AR/design.md` 字节不变**；JSON 含 `archived/backupPath/verified` |
| restore | 从最新备份解析源数据重新上传回系统，恢复平台侧正文；**不改本地 `AR/design.md`**；无备份即失败；JSON 含 `restored/verified` |
| review | 见「检视」章，尚未实现；当前返回 `success:false` 并非 0 退出 |
| AR 生成 | **不属 story.js 职责**——由本 Skill「生成design.md」章节（AI）完成 |

### 落地改造清单

按上表与既有实现差分，需要改动的只有 `archive` 一处：

| 子命令 | 既有实现 | 目标契约 | 要改吗 |
|---|---|---|---|
| `init` | 拉取 AR/SR/RR 三套单据与文档 | 一致 | **不改** |
| `archive` | 归档 `design.md`；无 `story.md` 时用 `spec.md` 顶替 | 前置要求两份归档件齐备且过 `merge-story --check`；上传 `AR/story.md` 作正文（沿用既有的临时改名 + 必还原机制）、`AR/review.md` 作附件；落 `.archive/` 回执 | **要改** |
| `restore` | 从最新备份重新上传回系统 | 一致 | **不改** |
| `review` | 无 | 占位，接口形状见上表 | 后续实现 |
| `fetch` | 有（条件触发 init） | 本 skill 不再调用 | **不要求删**——留着无害，删了反而动到既有能力 |

## 产物定位

**职责模型**：

| 产物 | 回答什么 |
|---|---|
| `RR/prd.md` | 业务上为什么做、要什么价值（外部输入） |
| `SR/design.md` | 整体方案、三方分工、系统级约定（外部输入） |
| `AR/design.md` | 上游要**本部件**做什么（§3.1 承载全局方案与部件分工） |
| `spec/spec.md` | 本部件**要做什么**（需求侧规格，意图 SSOT） |
| `review.md` | 上线要定什么、评审看过什么、评审定了什么（**人的决策**，AI 不得覆盖） |
| `acceptance.yaml` | 怎么算做对了 |
| `AR/story.md` | 把上述组织成可评审的形态（派生物，零新事实） |

spec 与 review 是 spec 阶段**并列**交付物，不是上下游——前者 AI 写、后者人写。

| | `AR/design.md` | `AR/story.md` |
|---|---|---|
| 流程角色 | 输入端：/spec 的输入（AI 从 RR+SR 提取） | 输出端：spec 阶段由 AI 按章节合同逐章装配的评审载体（单一线性文档，面向人） |
| 归档语义 | 工作区里身份唯一：「RR+SR 提取件」。archive 会临时借用它的文件名上传，并在任何结果下还原，**前后字节不变** | archive 的上传正文（在系统侧占 `design.md` 这个位，与 `AR/review.md` 一并上传） |
