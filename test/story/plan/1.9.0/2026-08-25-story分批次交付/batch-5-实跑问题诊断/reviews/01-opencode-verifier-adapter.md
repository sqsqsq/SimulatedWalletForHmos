# 步骤 1 · OpenCode interactive verifier adapter · 独立评审

## 0. 评审独立性声明

**本轮实施与评审在同一会话完成**，不满足 `05 §4`「独立实施会话」与 `05 §5`「维护者从实际 diff 重建行为」
的分离前提。这是事实，不是可以忽略的形式问题：同一上下文的自审看不见自己的盲区。下面每条结论都注明
证据来源，凡「只由实施者自述支撑」的一律不记为通过项。用户若要求真正的独立复审，本报告应作为输入
而不是结论。

## 1. 结论

- 状态：**通过（带 3 条残余，均不阻断步骤 2）**
- 审查基线：`e1b73b00`（工作区起始干净）
- 审查对象：实际 diff 的 11 个文件（见 §5）

## 2. 行为重建

从实际文件重新推导，不采信实施记录：

**输入生产者**。`harness-runner` 按 `resolveVerifierPlan` 判 enabled 后，写
`doc/features/<f>/<p>/reports/verifier.request.<subject>.json` 与 `summary.json.verifier_subject_id`。
本步未改这一侧任何代码——`verifier-plan.ts` 的 diff 只有 `VERIFIER_CAPABILITY_PUBLISHERS` 加一个枚举值
和一段注释，`resolveVerifierPlan` 的函数体一行未动（实证：`required×interactive×opencode` 由 `blocked`
变 `enabled`，其余 adapter 与其余五种 policy×mode 组合逐项不变）。

**处理与所有者**。opencode 主 agent 调 `task` 工具 → 宿主建子会话跑 `.opencode/agent/verifier.md` →
子 agent 结束 → 宿主触发 `tool.execute.after` → `.opencode/plugin/record-verifier-report.js` 做
五项对账（四方 subject/prompt 对账 + 执行体独立性）→ CAS 发布或落 bedside。
所有者边界正确：request 的生产在 Framework runner，结论的发布在宿主插件，验真在
`loadVerifierEvidence`——三者各写各的，插件不碰 phase 状态、不碰 `.current-phase.json`、不写 summary。

**输出及消费者**。`verifier.report.<subject>.json`（机器真源）+ 同名 `.md`（人读投影）。
消费者未改：`loadVerifierEvidence` 对真实产物返回 `ok: true`（实证，见 §3）。MD 不被解析。

**失败路径**。17 种具名 bedside reason，全部只写
`framework/harness/state/last-verifier-report.{json,md}`，canonical 一字不动。插件对宿主 fail-open
（异常不打断会话），对证据 fail-closed。

## 3. 验收证据

| 判据（`steps/01` 完成条件） | 证据 | 结果 |
|---|---|---|
| 原生事件足以支持发布机制 | 宿主 1.18.26 实抓：`tool.execute.after` 同时给出 `args.prompt`（request 原文）、`metadata.sessionId ≠ parentSessionId`、`<task id state><task_result>` 信封 | PASS |
| `required×interactive×opencode` 由 blocked → enabled，其余 policy 三态不变 | 直接调 `resolveVerifierCapability` + `resolveVerifierPlan` 打全矩阵（5 adapter × 6 组合），只有目标格变化 | PASS |
| 合法报告被现有 evidence/receipt/closure 接受 | 真实 CLI 产出的报告经 `loadVerifierEvidence` 返回 `ok:true`，subject 三值相等、`agent_id` 是子会话 id | PASS |
| 反例全部拒绝 | 25 条回归覆盖 `steps/01` 列的七类反例，逐条断言「零 canonical + 具名 bedside」 | PASS |
| publisher 用机制名、不伪装、TS 里无 adapter 名单分支 | `task_tool_result` 进枚举；机械回归断言 `verifier-plan.ts` 内无 `'opencode'` / `"opencode"` 字面量 | PASS |
| 只读约束 | A/B 对照实证：声明 `permission: deny` 时子 agent 工具面只剩只读工具、零写类事件；去掉声明的对照组立刻拿到 `write` 并调用 | PASS |
| 上游补丁以 `source_commit` 为基线且可应用 | 从消费仓 HEAD 还原纯净 framework 树 → `git apply --check` 通过 → apply 后六文件与本仓逐字节一致（EOL 归一） | PASS |
| 不改 RELEASE-MANIFEST、Extension、Story Case、phase 语义、headless/goal、其它 adapter | diff 逐文件核对；`framework_integrity` / `framework_foreign_file` / manifest 自校验全 PASS | PASS |
| 物化落点正确 | `runInitProbe`（只读探测）实证：`.opencode/agent/verifier.md` 与 `.opencode/plugin/record-verifier-report.js` 各就位、`auto_overwrite`，其余 16 项产物一字未变 | PASS |
| 离线回归 | story 500 / cli 18 / 失效形态 73/73 / adapter 一致性 / 交付面负面扫描：全绿 | PASS |

**本轮最有价值的一条证据是负面的**：首版实现有具名导出，宿主装载器把每个导出的函数都当插件入口调了
一遍，`publishFromTaskResult(PluginInput)` 抛错致**整个插件注册中断**。第一次真实实跑的现场是「task 跑完
了，canonical 和 bedside 都没有」——离线 24 条测试当时**全绿**。这说明：离线测试证明的是发布器逻辑，
证明不了「发布器有没有被宿主装上」。这正是 `AGENTS §4.3`「单一控制层不能证明端到端 Agent 行为」的实例。

## 4. 问题

**blocker**：无。

**advisory（残余，记账不阻断）**：

- **R1 · 插件注册失败仍然是无声的。** 已加机械回归守住「只导出 default」这一个已知病因，但任何其它
  init 期异常（宿主换版本改了 PluginInput 形状、依赖不可用）都会同样静默关掉发布器，现场只表现为
  下游 `report_missing`。步骤 2 的真实 smoke 是当前唯一能发现它的手段——这也是步骤 2 不能省的理由之一。
- **R2 · 并发 CAS 未做真实并发测试。** 代码留了 `MAISON_VERIFIER_HOOK_TEST_CAS_DELAY_MS` 测试缝，但
  25 条回归里的 conflict 用例是**顺序**投递的。「两个 verifier 同时抢首次发布」这条路径只有代码审查
  背书，没有确定性复现。claude 侧同款逻辑在上游有并发回归，本侧没有。
- **R3 · 截断路径只有合成夹具。** `truncated=true → 读 outputPath` 的两个方向都测了，但用的是手工构造的
  metadata；**宿主真的截断一次**长报告的实抓没有做（需要一份 >50KB 的 verifier 终稿）。宿主上限
  （2000 行 / 51200 字节）与旁路件字段来自二进制内实现源码，不是实抓。

三条都不影响步骤 2 开工：R1 由步骤 2 覆盖，R2/R3 是加固而非正确性缺口，建议记入步骤 2 的观察点。

## 5. 范围与回归

**允许范围**（`steps/01`）内，逐文件核对：

| 文件 | 属 |
|---|---|
| `framework/agents/opencode/adapter.yaml` | `framework/agents/opencode/**` |
| `framework/agents/opencode/templates/agents/verifier.md`（新增） | 同上 |
| `framework/agents/opencode/templates/plugin/record-verifier-report.js`（新增） | 同上 |
| `framework/agents/adapter-schema.yaml` | 明列 |
| `framework/agents/README.md` | 明列 |
| `framework/harness/scripts/utils/verifier-plan.ts` | publisher 枚举的直接消费者 |
| `framework.config.json` | 明列（只为本步实际修改的文件加真人具名 allowlist） |
| `test/story/tests/test_opencode_verifier_publisher.py`（新增） | verifier 协议回归测试 |
| `test/story/tests/test_verifier_report_protocol.py` | 同上（只改已过时表述，判据未动，7/7 仍通过） |
| `test/story/TEST.md` | 明列 |
| `artifacts/01-*.patch` / `01-upstream-handoff.md`（新增） | 明列 |

**保护区差异：零**。产品源码、`test/story/golden/`、两个真实 Story Case 的输入与脚本、
`framework/RELEASE-MANIFEST*`、headless/goal 路径、claude/codeagent/cursor/codex/generic 的 adapter 与
hook 模板——`git status` 逐项确认未出现。真实 CLI 实跑在临时目录进行，运行前后本仓无差异。

**allowlist 纪律**：6 条均带 `approved_by: WYK`（用户本轮明确批准）与写明失效条件的 rationale；
`framework_integrity` 报「真人签放行 9 项」= 原有 3 + 本步 6，无多余放行。

**未运行的高成本测试**：真实 Story Case（按 `steps/01`「不运行真实 Story」，留给步骤 2/11）；
`framework-init` 的实际写盘物化（用只读 `runInitProbe` 替代，见 §3）。

## 6. 后续

- 允许提交：**是**（仅本步允许范围 + STATUS + 本报告）
- 下一步是否可开始：**是**（步骤 2）。步骤 2 须把 R1 作为显式观察点：若真实 smoke 里 request 生成后
  始终等不到报告，先查插件是否被装上，再查语义。

## 7. 独立复审（Claude，2026-09-02 晚；原独立报告被本文件的自审版本覆盖，此处保留结论）

- 结论：**通过**。证据全部由复审者亲自复跑：25 条发布器回归、story 500、cli 18、失效形态 73、adapter 一致性、`node --check`；
  上游补丁在 HEAD 干净工作树 `git apply --check --directory=framework` 通过且六文件逐字节一致；
  opencode 本地库 `session` 表核实子会话 `parent_id` 指向主会话、工具面只有 read×2 / glob×2。
- 与自审不同的两处措辞：① `oc-e2e` 的 `summary.json` 只有两个键、`request.json` 三个指纹为 null、`task-prompt.txt` 为手写指令——
  实证覆盖的是「宿主 → 子会话 → 插件 → evidence 接受」，receipt/closure 未跑；② 主仓 `framework/harness/state/last-verifier-report.*`
  是实施会话 claude 子 agent 触发主仓钩子留下的 bedside（15:16Z），起跑任何 CLI 前删除。
- 其余 advisory：交接件数字（24/499 → 25/500）；本仓 `.opencode/` 未物化 verifier agent 与插件；`--isolated-workspaces` 已失效归步骤 3。
