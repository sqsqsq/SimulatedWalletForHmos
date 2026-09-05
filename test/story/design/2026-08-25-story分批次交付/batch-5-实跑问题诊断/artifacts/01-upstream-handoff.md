# 步骤 1 上游交接：OpenCode interactive verifier adapter

## 这份补丁做什么

给 Framework 已有的 verifier 能力补上 OpenCode interactive 的 adapter 实现。补丁前
`required × interactive × opencode` 解析为 `blocked`（runner 生成 request，但没有任何机制发布结论），
补丁后为 `enabled`。**不改变任何 verifier 协议、产物格式或其它 adapter 的行为**。

## 基线与应用

| 项 | 值 |
|---|---|
| 补丁文件 | `01-framework-opencode-verifier.patch` |
| 基线 | `framework/RELEASE-MANIFEST.json` 的 `source_commit` = `85e266f185fbaec92263377dc71f6c15512ea3db`（发布版本 3.0.0 正式版） |
| 路径基准 | Framework 仓根（已剥掉消费仓的 `framework/` 前缀），`git apply` 直接可用 |
| 验证 | 从 `85e266f` 还原一份纯净 3.0.0 树 → `git apply --check` 通过 → apply 后六个文件与本仓实现**逐字节一致**（行尾归一后，与 `framework_integrity` 同一口径） |

## 六个文件

| 文件 | 改动 |
|---|---|
| `agents/opencode/templates/plugin/record-verifier-report.js` | **新增**。发布器：`task` 工具完成时做四方对账并发布 `verifier.report.<subject>.json`。subject 按 3.0.0 的 `maison-verifier-request@2` 派生，字段与顺序同 `harness/scripts/utils/verifier-request.ts` 的 `canonicalRequestInput`；request 认 `schema_version` **1.1**（与 `VERIFIER_REQUEST_SCHEMA_VERSION` 同值——两处分叉时插件会把真实 request 整份拒收，结论只落 bedside） |
| `agents/opencode/templates/agents/verifier.md` | **新增**。只读 verifier 子 agent 定义，`permission:` 逐工具 deny |
| `agents/opencode/adapter.yaml` | 增 `commands.subagents`（→ `.opencode/agent`）、`hooks`（→ `.opencode/plugin`）、`verifier_capability` |
| `harness/scripts/utils/verifier-plan.ts` | `VERIFIER_CAPABILITY_PUBLISHERS` 增枚举值 `task_tool_result` |
| `agents/adapter-schema.yaml` | publisher 枚举**加一档** `task_tool_result` 与它的说明；`hooks` / `commands.subagents` 的描述放宽到「宿主自动发现」这一类落地方式。3.0.0 正式版改写过同一段（`subagent_stop` 的措辞），本补丁是**在你们的新措辞上加档**，不覆盖它 |
| `agents/README.md` | 新机制的消费契约、降级矩阵与产物表 |

**没有新增机制的地方**：transport 复用 `repo_file_request`；subject 派生口径（`@2`）、request 契约、
报告 JSON 结构、`loadVerifierEvidence` / receipt / closure 全部零改动——插件只是把 TS 侧的
`canonicalRequestInput` 在 JS 里复刻一遍，两边逐项相同；物化复用既有的 `hooks` 与
`commands.subagents` 两个通用目录复制字段，没有为 opencode 新建物化通道；TypeScript 里没有任何
adapter 名分支——能力面仍只由 `adapter.yaml` 的声明决定。

## 机制：为什么不是 `subagent_stop`

opencode 没有 SubagentStop 这一层事件。但它的 `task` 工具**建的是一个子会话**，完成时通过插件钩子
`tool.execute.after` 一次交出全部绑定材料，比读转录更直接——调用正文就是工具入参本身。所以 publisher
取机制名 `task_tool_result`，不冒充别的宿主的机制。

四方对账、CAS 发布、conflict 单调升级、bedside fail-closed 与 claude 家族逐字相同，另加一条本机制
特有的**执行体独立性**校验：子会话 id 存在、≠ 主会话 id、且 == 终稿信封 `<task id="…">` 自述的会话 id。

## 三条宿主实证事实（opencode 1.18.26 实抓，模型 `bailian/deepseek-v4-flash-0731`）

1. **一次 `tool.execute.after` 就给全三样材料**：`input.args.prompt`（投递的 request JSON 原文）、
   `output.metadata.sessionId` / `parentSessionId`（子/主会话，实抓中不同）、
   `output.output`（`<task id state><task_result>终稿</task_result></task>`）。

2. **只读来自声明，不是模型自述**。A/B 对照：子 agent frontmatter 写 `permission:` 逐工具 deny 时，
   工具面只剩 glob/grep/read/skill、零写类事件；**去掉该声明**的对照组立刻拿到 `write` 工具并调用它。
   `--auto` 只自动批准未被显式 deny 的权限（对照组写项目外目录时仍停等确认）。

3. **两个会让实现静默失效的宿主行为**——都已在实现里处置，改动时不要回退：
   - **终稿截断**：工具输出超 `tool_output` 上限（默认 2000 行 / 51200 字节）会**从头部保留**，
     全文另存 `metadata.outputPath`。终态块在终稿末尾，只读 `output.output` 会得到「无终态块」
     而误判成 verifier 没给结论。`truncated === true` 时必须改读 `outputPath`。
   - **装载器会调用每一个导出的函数**（实证：一个具名导出的 helper 被当作插件入口调了一遍，
     入参是 PluginInput）。所以插件**只导出 default**，内部函数挂在它身上。踩到这条时的现场是
     「task 跑完了，canonical 和 bedside 都没有」，没有任何报错指向插件——本仓已加机械回归守它。

## 消费仓验证情况

- 25 条发布器回归（正例经真实 `loadVerifierEvidence` 接受；每种绑定不成立形态各自落 bedside 且零 canonical；
  与 TS SSOT 的 subject/指纹跨实现等值）：全过；
- 全量离线 608 条、失效形态自检 70 条 FAIL 0、`check-adapter-catalog-consistency`、
  `framework_integrity` / `framework_foreign_file`：全过（均在 3.0.0 正式版地基上复跑）；
- **真实 CLI 全链**：opencode + deepseek 起一次 spec 审查 → 独立子会话 verifier 只读读完材料 →
  插件发布 canonical → framework 验真面返回 `ok: true`，`invocation_subject == result_subject ==
  summary 现值`，`agent_id` 是子会话 id。

## 交付边界

**本仓验证通过 ≠ 内网已获得该能力。** 消费仓的 `framework/` 来自上游发布件，本地改动靠
`framework.config.json` 的 `integrity.drift_allowlist` 具名放行，下一次 `framework-init UPDATE`
会把它冲掉。上游合入并发布前，内网 OpenCode 的 P3（verifier 无法闭环）原样存在。

**allowlist 的失效条件**：上游补丁经 framework-init UPDATE 回到消费仓后，那 6 条 allowlist 条目
即失效，**必须删除**——留着会掩盖真实漂移。条目的 `rationale` 里已写明这一条。
