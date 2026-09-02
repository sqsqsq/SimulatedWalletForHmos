# 步骤 2 · OpenCode verifier 专用 Spec smoke · 独立评审

## 0. 评审独立性与本步的特殊状态

同步骤 1：**实施与评审在同一会话**，不满足 `05 §4/§5` 的分离前提，本报告是自审。

更要紧的一条：**本步的真实 CLI 实跑没有执行**。用户 2026-09-02 明确「写完 smoke 不进行 CLI 测试，
留着，登记待验证（WYK 授权），并进入下一阶段」。所以本步交付的是**可运行的 smoke 装置**，
不是 smoke 的**运行结论**。

## 1. 结论

- 状态：**已实施（装置）；实跑待验证 —— 结论 A / B 均未取得**
- 审查基线：`4334ba5c`
- 审查对象：`test/story/verifier-smoke/**`、`test/story/tests/test_verifier_smoke.py`、`TEST.md §7.0.1`

**必须挂在明面上的一条**：`steps/03`～`steps/11` 的进入条件原本是「步骤 2 允许继续」。现在这个
条件是**用户授权跳过的，不是被证据满足的**。据此往下走时：

- D1 的**基础设施**结论有步骤 1 的真实全链实证兜底（opencode + deepseek，见 `reviews/01`），
  但那是在一个手工探针工程上取得的，不是走 harness 生成的 request；
- D1 的**语义有效性**（结论 B：verifier 是否真读了材料、判断是否与产物相关）**零证据**；
- `reviews/01` 的残余 R1「插件注册失败是无声的」本来指望本步覆盖，现在仍未覆盖。

后续任何一步引用「D1 已验证」时，必须限定为「步骤 1 的探针级全链」，不能说成「smoke 已通过」。

## 2. 行为重建

**输入生产者**：`fixture/` 冻结四样东西——合成工程（config + architecture/catalog/glossary）、
六条需求 prompt、full track 声明、按 registry portable 文案索引的固定回复表。

**处理与所有者**：
`build` 复制 `framework/`（排除 node_modules 与运行态）、落夹具、写 `feature.yaml: track: full`，
然后调**真正的 init**（`init-orchestrate.ts` 的 staging → execute）物化 `.opencode/`。
`run` 用 `tools/cli` 的 `CliClient` 逐轮驱动，按 portable 文案匹配确认点。
`verify` 只从 workspace 磁盘原件重建链路，并用 workspace 自己的 `check-receipt.ts` 判闭环。
所有权正确：阶段门禁由被测模型在 workspace 内自己跑，驱动不代跑。

**输出及消费者**：`--evidence` 的逐轮留痕（轮次、匹配到的确认 id、模型原话、回复、墙钟）
+ `verify` 的六项绑定检查。消费者是维护者的评审，不进任何门禁。

**失败路径**：`cli_failed` / `unknown_question`（有编号菜单但无对应条目 → 停等）/
`environment_or_fixture_failed`（`spec.feature_path` 冲突等）/ `no_progress`（连续 N 轮既无确认
也无闭环）/ `closure_reached`。

## 3. 已取得的证据（装置层面）

| 判据 | 证据 | 结果 |
|---|---|---|
| smoke 可独立、重复、显式运行，不影响 Story Case | 独立目录与驱动，不在 `cases/*`；全量 514 条离线测试通过，Story Case 计划输出不变 | PASS |
| 六条需求与 full track 由夹具冻结 | `fixture/prompt.md` 六条逐条锚在测试里；`feature.yaml: track: full` 由 build 写入 | PASS |
| 确认按稳定 ID 匹配、未知即停等 | 匹配键逐条对 `confirmation-registry.yaml` 校验；未知菜单不命中任何规则；自述推进不被误判为提问 | PASS |
| 物化与真实消费仓同源 | build 走 `init-orchestrate.ts`；实跑一次确认 `.opencode/agent/verifier.md`、`.opencode/plugin/record-verifier-report.js`、`.opencode/skill/spec/SKILL.md`、`AGENTS.md` 全部就位 | PASS |
| 链路校验只认磁盘原件，且反例判 FAIL | 六种形态（无 subject / 无报告 / subject 失配 / 无独立执行体 / 非本机制发布 / 全绑定成立）离线锚死 | PASS |
| 运行前后产品源码零差异 | 驱动只写隔离 workspace；**且本步已发现并修掉一次相反的现场**（见 §4） | PASS |
| 两个结论分别记录 | `TEST.md §7.0.1` 的 A/B 表 + 本报告结构 | PASS |
| Framework 能力结论 / 语义观察结论 | **未取得** —— 实跑未执行 | 待验证 |

**顺带取得的一条步骤 1 加强证据**：`.opencode/agent/verifier.md` 与 `.opencode/plugin/
record-verifier-report.js` 这次是经**真实 init** 落地的，比 `reviews/01` 里用只读 `runInitProbe`
推导的物化清单更强——步骤 1 的物化声明因此从「探测通过」升为「实跑通过」。

## 4. 问题

**blocker**：无（在「本步只交付装置」的前提下）。

**已在本步修掉的现场（记账，防复发）**：
调试期间我把 `harness-runner.ts` 当成接受 `--project-root` 的命令跑了两次——它**不接受**该参数，
minimist 静默忽略，于是两次都跑在**主工程**上：写了 `framework/harness/reports/_global/catalog/`
（gitignored 运行态产物，被覆盖）、并误建了 `doc/features/hide-balance-toggle/`。两处已清理，
`git status` 干净。这条事实已写进驱动文件头与 `TEST.md §7.0.1` 的现场纪律，因为它对任何
「想在主仓顺手跑一下门禁」的人都成立。

**advisory**：

- **R4 · `run` 分支未经真实执行**。`build` 与 `verify` 都跑通过，`run` 的逐轮循环只有离线单测
  覆盖它的判定分支（匹配 / 未知 / 自述），**整段与 `CliClient` 的实际交互没跑过**。首次实跑很可能
  要修驱动本身（`_last_text` 的字段名、session 续话形态），那属于夹具问题，按
  `environment_or_fixture_failed` 处置，不计为 D1 失败。
- **R5 · `no_progress` 的阈值是新引入的停止条件**。测试域明令不设时限与轮次上限；这里用的是
  「连续 N 轮既无确认也无闭环」的**进展**判据而非计时/计次，默认 8。它仍是一个人为常数，
  实跑时要看它有没有过早掐断，必要时调大而不是改判据形态。
- **R6 · 只读工具证据尚未接上**。`export_verifier_session()` 已写好（`opencode export <子会话>`
  可拿到子 agent 的工具调用记录），但没有在 `verify` 里作为断言接进去——实跑时应把它接上，
  用真实工具记录取代「模型自述只有只读工具」。

## 5. 范围与回归

允许范围（`steps/02`）内：`test/story/verifier-smoke/**`（新增）、
`test/story/tests/test_verifier_smoke.py`（对应测试，新增）、`TEST.md §7.0.1`、
`steps/02` 文件（记录用户两项裁定）、STATUS 与本报告。

**保护区差异：零**。产品源码、`test/story/golden/`、两个真实 Story Case 的输入与脚本、
`framework/`、`framework.config.json` 本步一字未动。

**未运行的高成本测试**：真实 CLI smoke —— 用户授权暂缓，登记待验证。

## 6. 后续

- 允许提交：**是**
- 下一步是否可开始：**是（按用户授权）**，但 `STATUS` 与后续每一步的报告都须带上「步骤 2 实跑待验证」
  这一条前提；步骤 3 起的结论不得建立在「smoke 已通过」之上。
- 待验证项恢复方式：按 `TEST.md §7.0.1` 三条命令跑一次，把 A/B 两个结论分别写回本报告的新轮次小节。

## 独立复审（Claude，2026-09-03）

- 结论：**装置通过；结论 A/B 未取得**（用户授权暂不实跑）。复审者复跑 `test_verifier_smoke.py` 15 条通过；
  `replies.yaml` 四条匹配键逐条对应 `confirmation-registry.yaml` 的 portable 文案；`verify()` 六项检查与 `check-receipt` 闭环判定只读 workspace 磁盘原件。
- 与自审一致的一条边界：合成 `generic` 工程不挂 Extension，所以结论 B 只能证明 verifier 读了六条需求与 spec，证明不了它对扩展的 `pre_verifier` 判据有区分力——那是步骤 7 的事。
- 待清理：主仓 `framework/harness/state/last-verifier-report.*` 与 `framework/harness/reports/_global/catalog` 仍在（后者是本步误跑留下的），起跑前处理。
