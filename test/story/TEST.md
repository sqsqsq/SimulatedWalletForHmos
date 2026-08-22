# Story 并行 CLI 测试指南

本指南是 Story 测试域的当前端到端操作协议。维护约束见 [AGENTS.md](AGENTS.md)，演进背景见
[EVOLUTION.md](EVOLUTION.md)。这些维护文件不得进入被测模型上下文。

## 0. 新会话协议

宿主模型完整阅读本文件后，用户输入“开始测试”即进入编排。宿主负责测试生命周期、语义观察和回复；
被测模型是隔离 Case 中由 CLI 启动的模型。宿主每次从当前 `cases/*/case.yaml` 动态读取可用 Case，
按读取结果生成编号多选项，并另列“全部当前 Case”。不得假定固定数量、名称、feature 或顺序。

允许单选、多选或全选。确认前复述实际 Case、feature、目标阶段、隔离 workspace 和回灌范围；只能执行
`plan` 等只读检查，不能创建 suite、迁移 features 或启动 CLI。

用户已授权宿主模型启动外层协调器时使用非沙箱环境。`start` 必须在非沙箱环境执行并传入
`--authorize-non-sandbox`。这不是要求被测模型切换环境，也不得写入 Case prompt。

## 1. 唯一入口与启动

正式测试统一使用 `scripts/run_multi_case.py`，即使只运行一个 Case，也不直接运行 `run_case.py`。

```powershell
python test/story/scripts/run_multi_case.py plan --all --jobs <实际Case数> --isolated-workspaces
python test/story/scripts/run_multi_case.py start --all --jobs <实际Case数> --isolated-workspaces `
  --suite-id story-suite-20260822-140000 --authorize-non-sandbox
python test/story/scripts/run_multi_case.py poll --suite-id story-suite-20260822-140000 --wait-sec 0
```

`start` 返回统一控制对象及 `next_action=poll_after_interval`、`next_interval_sec=15`。宿主模型立即创建
名称包含 suite-id、绑定当前任务的 15 秒 Codex heartbeat。heartbeat 建立成功后，启动回合可以结束，
后续由定时唤醒继续驱动。`status` 只用于只读诊断：不消费事件、不回复、不增加观测次数或稳定确认，
不能替代 `poll`。

Case 严格顺序启动：前一个取得有效 run-id、worker/lease 和活动状态后才启动下一个。确认启动后的
worker 并行运行。启动失败时检查活动指针、run、worker、lease、workspace 和原始输出，最多恢复并
重试 3 次；仍失败则保留完整事实并继续启动其余 Case。不要套外层 timeout 或输出截断管道。

## 2. 起跑前固定顺序

1. 创建本轮 `output/story/<suite-id>/` 控制目录。
2. 扫描并关联 `%TEMP%/sw-story/*` 与 `output/story/*` 中的历史 suite。
3. 整体预检终态、PID、lease、路径边界、软链接和所有权。
4. 全部安全后删除历史 workspace/output，写入 `previous-run-cleanup.json`。
5. 清理全部成功后，将当前 `doc/features/*` 整体迁移到
   `E:\Project\bak\Story-Features-<时间戳>/`。
6. 创建模板及各 Case workspace，再顺序启动 CLI。

workspace 只复制产品源码和构建配置、`framework/`、`doc/extensions/`、architecture/catalog/glossary
以及当前 Case 所需输入。递归排除 `test/`、`tools/`、`output/`、`.git`、历史 `doc/features`、其他
Case 输入和历史 suite。启动前递归检查路径边界与软链接，并在 `workspace-boundary.json` 分别记录
`copied`、`excluded` 和各 Case 的 `case_seeded` 清单。边界失败只阻止起跑，不产生额外运行状态。

活动 PID、有效 lease、路径越界、软链接风险、未知目录类型、所有权不明或无法可靠枚举进程时，必须
保留现场并在 feature 迁移前停止。部分删除失败时记录每个目标结果并拒绝继续。非 suite 长期目录不
自动清理。features 是迁移归档，不在本轮结束时恢复；本轮 workspace/output 也保留到下一轮。

## 3. 主模型驱动与单轮 poll

一次 `poll --wait-sec 0` 是完整事务：读取 suite 中全部实际 Case；并行消费所有非终态 Case 的新事件、模型输出、
阶段和状态；只处理真实 `awaiting_reply`；自动发送匹配的预置回复并立即零等待确认接受和消费；最后
统一计算稳定状态。定时器是唯一等待来源，poll 自身不得再次等待；零等待确认不计入 15 秒稳定确认。

阶段不按模型回复文本猜测。worker 运行期间和每次正式 poll 都从 Case workspace 的结构化证据校正：
feature 匹配的 `framework/harness/state/.current-phase.json` 为首选，阶段目录中的非 `reports/` 产物为后备。
`current_phase` 是当前观测阶段，`highest_phase_reached` 是本轮曾到达的最高阶段且不回退；兼容字段
`last_phase` 镜像 `current_phase`。首次确认最高阶段达到 Spec 时写入且保留 `spec_entered_at`。

每次 `start`/`poll` 返回 `suite_terminal`、`selected_case_count`、动态 `cases`、`interactions`、
`adaptive_reply_requests`、`automation_stability` 和 `next_action`。`next_action` 仅有：
`poll_after_interval`、`reply_then_poll`、`finalize`。同时返回 `progress_changed`、`changes` 和
`next_interval_sec`。每次 heartbeat 唤醒都简短展示全部实际 Case 当前阶段、交互、错误及下一间隔；
无变化也显示仍在观测。

每个 Case 的 `interaction-script.yaml` 提供预设回复。协调器只在 `awaiting_reply` 后核对 turn/kind，
再发送自然语言并记录接受与消费状态。若没有匹配脚本，宿主阅读当前问题、本 Case 公开输入和已发生
交互，给出推进场景所需的最小回复，然后同一回合立即再次 `poll` 确认消费并继续驱动。不得读取其他
Case、历史答案或提示遗漏项。意外行为、维护文件名或任何关键词只能记录和理解，不能据此调用
`stop`；`stop` 只响应用户明确要求。单个 Case 失败也不得停止其他 Case。

```powershell
python test/story/scripts/run_multi_case.py reply --suite-id story-suite-20260822-140000 `
  --case split-interactive --reply-mode adaptive --reason "依据当前问题和本 Case 输入" `
  --text "本单先做策略查询与创建签约，状态查询与解约交给兄弟单据。"
```

## 4. 15/120 秒 heartbeat

- 未全部稳定进入 Spec 前，同一个 heartbeat 每 15 秒唤醒，执行一次
  `poll --suite-id <suite-id> --wait-sec 0`。
- 事件积压、终态和 `awaiting_reply` 立即处理。
- 全部所选 Case 连续两轮、间隔至少 15 秒稳定处于 Spec 或后续自动阶段后，把同一个 heartbeat 更新为
  120 秒；不创建第二个任务。

每轮 15 秒完整观测后统一判断：全部成功启动并曾进入 Spec；所有非终态 Case 当前仍处于 Spec 或
后续阶段；没有 pending、starting、Story 阶段或 awaiting_reply；本轮状态读取全部成功。第一次满足
时确认数为 1 并保持 15 秒，第二次连续满足后写入 `ready_at`，返回 `next_interval_sec=120`。heartbeat
改频后仍执行同一 suite 的真实零等待 `poll` 并继续处理交互；不得调用 `status` 代替观测。

任一条件不满足立即清零。已进入 Spec 后终止的 Case 保留资格；未进入 Spec 就失败的 Case 不能触发
120 秒。120 秒期间出现等待回复、阶段回退或状态异常时，把同一个 heartbeat 改回 15 秒；重新连续
确认两轮后再改为 120 秒。poll 返回 `reply_then_poll` 时，主模型在本次唤醒中发送自适应回复并立即
再次零等待 poll。返回 `finalize` 时执行回灌、输出逐 Case 汇总并暂停 heartbeat，不调用 `stop`。

heartbeat 提示词必须包含当前 suite-id，并要求：每次只执行一次 `poll --wait-sec 0`；处理自适应回复后
立即再 poll；按 `next_interval_sec` 更新当前 heartbeat；每轮展示简短完整快照；命令失败时诊断并重试
一次，仍失败则保留 15 秒节奏并报告；终态 finalize 后暂停当前 heartbeat。重复唤醒不得创建新任务。

## 5. 状态与证据

静默不是终态，`awaiting_reply` 必须处理。权威状态只来自 `state.json` 和运行事件。典型目录：

```text
output/story/<suite-id>/
├─ suite.json
├─ previous-run-cleanup.json
├─ feature-migration.json
├─ workspace-boundary.json
├─ controls/<case-id>/{active.json,latest.json}
└─ cases/<case-id>/
   ├─ observations.jsonl
   ├─ observation-record.md
   ├─ promotion-manifest.json
   ├─ source-diff/
   └─ <run-id>/
      ├─ state.json
      ├─ live.jsonl
      ├─ events.jsonl
      ├─ runlog.md
      ├─ worker.log
      ├─ gate_*.log
      ├─ gate_diagnostics.json
      ├─ phase-results/
      └─ artifact/
```

原生 phase gates 仍由被测流程执行并记录。退出码只表达执行结果：正常完成且到达目标阶段为 0；
CLI、gate、恢复或基础设施失败为非零。

## 6. 回灌与现场保留

全部 Case 终态后执行：

```powershell
python test/story/scripts/run_multi_case.py finalize `
  --suite-id story-suite-20260822-140000 --promote
```

回灌依据是 Case 已终态且 workspace 存在。成功或失败 Case 的 `doc/features/<feature>` 都独立复制回主工程，
不得因同批其他 Case 已写入源码而跳过。受控源码差异逐文件做三方检查：目标仍等于 suite 基线时写入，
目标已等于该 Case 结果时记为幂等完成，只有目标同时不同于基线和 Case 结果时记录真实冲突；删除只记录
不执行。Feature 目标已存在时仅在内容完全相同时视为已回灌，否则保留双方并记录冲突。每个 Case 生成不可变原始
`observations.jsonl` 和汇总 `observation-record.md`，记录启动与恢复、阶段和状态变化、15/120 秒观测、
交互、CLI/gate/基础设施错误、回灌结果和保留路径。

`finalize --cleanup` 已停用，必须明确报错且不删除现场。finalize 后本轮 workspace 和整个 suite output
保留到下一轮起跑时统一清理。

## 7. 离线验证

```powershell
python -m unittest discover -s test/story/tests
python -m unittest discover -s tools/cli/tests
python -m compileall -q tools/cli test/story/scripts
python -m tools.cli.scripts.validate_clis
python test/story/scripts/run_multi_case.py plan --all --jobs <实际Case数> --isolated-workspaces
```

这些命令不启动真实被测 CLI，只检查接口、状态转换、清理预检、稳定观测和确定性规则。
