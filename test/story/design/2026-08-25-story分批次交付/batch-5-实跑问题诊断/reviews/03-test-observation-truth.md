# 步骤 3 · 测试观测与效率事实 · 独立评审

## 0. 评审独立性与前提

同前两步：**实施与评审同一会话**，是自审。

**前提提醒**：本步的进入条件「步骤 2 允许继续」是用户授权跳过的，不是证据满足的
（见 `reviews/02` §0）。本步只改测试域，不依赖 D1 的结论，所以这条前提不影响本步成立；
但它仍挂在整批账上。

## 1. 结论

- 状态：**通过**
- 审查基线：`49f9ed54`
- 审查对象：`measure_run.py`、`run_case.py`、`test_harness.py`、`test_run_measurement.py`（新增）、`TEST.md`

## 2. 行为重建

**P8 — 度量读的不是真事件**。根因比诊断记录的还深一层，是**两处**同时坏：

1. `_text_of` 只拼 `content` + `tool_input`，**完全没有 `tool_output`**；
2. check id 的正则写成 `<id>\s*(FAIL|未通过)`——而真实控制台输出是
   `✗ FAIL [BLOCKER] <id>`，**id 在 FAIL 之后**，方向正好相反。

两处叠加的结果：`repeated_check_fails` 在任何一份真实事件流上恒为空，读起来像「没有反复失败」。
现在拆成两个取值面——`_request_text`（作者要什么，路径类判定只看它）与 `_output_text`
（工具回了什么，门禁结论只看它），并按**门禁轮次**去重计数。

**这条修复直接在历史数据上兑现**：回读 `20260901-230253-23468/car-key-sharing`，
`verifier_provider_unavailable` 失败 5 轮、`lifecycle_hook_post_check_extension` 4 轮、
`feature_to_acceptance` 4 轮、读 checker 源码 1 次、上下文 11.7K → 584K。这些数此前一个都读不出来。

**P10 — 阶段被目标抬上去**。`refresh_worker_lease(..., phase=...)` 把参数无条件写成
`current_phase` / `highest_phase_reached` / `phase_source="runner_hint"`。三个调用点传的分别是
起跑阶段、下一个未闭环阶段、以及 `gates_started` 时的 **`end_phase`（本轮目标）**——没有一个是
「模型到了哪」的证据。现在它只写 `phase_intent` 留痕，阶段状态一律由 `derive_phase_state`
从 framework 状态与真实阶段产物推导。

**人工等待**：由驱动器在等待循环里累计（它才知道何时开始等、何时等到），落
`state.human_wait_sec` / `human_wait_events`；度量侧只读，不自己重建等待区间。

**P9 — 只补图片认不认得出**：见 §4，本步只钉事实，不修。

## 3. 验收证据

| 判据（`steps/03` 完成条件） | 证据 | 结果 |
|---|---|---|
| P8 每个缺失指标都有正反固定样本 | 门禁 FAIL→点名/全绿→零且不是「识别不到」/同文本只在入参→不计/输出面四种形态（None、空串、dict、list、数字）不炸不误报 | PASS |
| 乱码不影响分类 | Windows 乱码样本（中文整段花掉、ASCII 完好）仍认出 check id | PASS |
| 同一 check 多次与失败后恢复 | 一轮内重复只记一轮；跨轮累加；第二轮全绿则停在 1，而门禁运行次数仍记 2 | PASS |
| P10 两个历史假阳性不再记为到达 Plan | 只有 `phase_intent=plan` 时阶段仍是 story；只有 `plan/reports/` 时不算到达 | PASS |
| 真实 Plan 产物样本仍能升级 | framework 状态 → spec；真实 `spec.md` 落盘 → spec，来源分别为 `framework_current_phase` / `phase_artifact` | PASS |
| 图片-only 补料能区分内容不变与资产改变 | 正文改 → 换版本；`ux-reference/` 加图 → 换版本；**`assets/` 加图 → 不换**（见 §4） | 部分：缺口已钉死 |
| 现有 Case 计划、交互脚本、输出目录协议不变 | 只改测试域四个文件；`run_multi_case.py plan` 输出不变；538+18 条测试与 73/73 全绿 | PASS |
| 不运行真实 CLI 或 Story | 未运行 | PASS |
| 批次 5 白名单与唯一金样路径只做回归确认 | 两条只读断言，未新建第二份状态记录 | PASS |

## 4. 问题

**blocker**：无。

**已钉死、按责任归属外送的缺口**：

- **P9 归步骤 6（责任错位，如实回报）**。按 `TEST.md §2.2`，图片进来**只有一条路**：人给的
  docx 内嵌、导入时抽出，落 `<feature>/assets/<stem>/`。而 `material_inputs` 只覆盖
  `RR/SR/AR` 四份文本与 `ux-reference/` 目录——**实证**：`assets/` 下加一张图，
  `material_fingerprint` 一字不变。于是「补了一份只多几张图的文档」对轮次完全隐形。
  修它必须改 Extension 的材料版本定义，正是步骤 6 的 material manifest 单一真源；
  `steps/03` 明写「若修复必须改变……Extension 材料版本定义，停止并回报责任错位」，故本步不修。
  缺口以 `unittest.expectedFailure` 钉成机械事实：步骤 6 落地后它会**意外通过**，
  unittest 因此报错，逼着摘掉标记——不靠记忆，也忘不掉。

**advisory**：

- **R7 · 分段耗时是近似值**。事件流里一次工具调用只有一条 `completed`/`error` 事件，
  **没有开始事件**，真实 span 拿不到。现用「上一条事件到本条事件的间隔」归属，字段名
  `gap_sec_by_kind` 如实标注。要真值须让 adapter 补发工具开始事件，那是 CLI 层的改动，不在本步。
- **R8 · 历史 run 的人工等待仍是 `not_recorded`**。累计器从本步起生效，之前的运行没有这个字段，
  度量如实报 `null`。跨轮次比较 KPI 时要注意口径断点。
- **R9 · 修改了一条既有测试的断言**。`test_heartbeat_renews_the_lease_atomically` 原先断言
  `phase="plan"` 会写进 `last_phase`——那正是 P10 的旧契约。已改为断言新规则（提示只进
  `phase_intent`、不得抬升阶段），该用例的原主题（心跳与租约原子性）未动。

## 5. 范围与回归

允许范围（`steps/03`）内：`measure_run.py`、`run_case.py`、必要的直接测试
（`test_harness.py` 一处断言、`test_run_measurement.py` 新增）、`TEST.md`。
`observe.py` 与 `phase_state.py` 本步未需改动——`derive_phase_state` 的推导本就只认证据，
坏的是**喂给它的** hint。

**保护区差异：零**。产品源码、`framework/`、`doc/extensions/`、`test/story/golden/`、
两个真实 Story Case 的输入与脚本一字未动。构造样本全部内联在测试里，未新增夹具目录。

**未运行的高成本测试**：真实 CLI / 真实 Story（本步明令不跑）。

## 6. 后续

- 允许提交：**是**
- 下一步是否可开始：**步骤 4 需要先取得 Framework 修改授权**（`steps/04` 的授权门：
  用户只授权了步骤 1，步骤 4 开始前必须重新取得是否允许在本工程修改 `framework/` 的明确决定；
  未获授权时状态为「阻塞」，且不得用 Extension wrapper 或根 AGENTS 加长替代）。
- 带给步骤 6 的输入：P9 的实证与 `expectedFailure` 标记。
