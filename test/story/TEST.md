# Story 并行 CLI 测试指南

本指南是 Story 测试域的当前端到端操作协议。维护约束见 [AGENTS.md](AGENTS.md)，演进背景见
[EVOLUTION.md](EVOLUTION.md)。这些维护文件不得进入被测模型上下文。

## 0. 新会话协议

宿主模型完整阅读本文件后，用户输入“开始测试”即进入编排。宿主负责协调、观察和回复；被测模型是
隔离 Case 中由 CLI 启动的模型。宿主从 `cases/*/case.yaml` 提供可多选选项：

1. `pattern-image-review`：Story → Review。
2. `split-interactive`：Story → Story Review。
3. `source-conflict-review`：Story → Spec。
4. `split-two-ar`：Story → Plan。
5. 全部 Case。

允许单选、多选或全选，portable 输入允许回复 `1,3`、单个编号或“全部”。确认前复述 Case、feature、目标阶段、隔离 workspace 和回灌范围；只能执行
`plan` 等只读检查，不能创建 suite、迁移 features 或启动 CLI。

用户已授权宿主模型启动外层协调器时使用非沙箱环境。`start`/`run` 必须在非沙箱环境执行并传入
`--authorize-non-sandbox`。这不是要求被测模型切换环境，也不得写入 Case prompt。

## 1. 唯一入口与启动

正式测试统一使用 `scripts/run_multi_case.py`，即使只运行一个 Case，也不直接运行 `run_case.py`。

```powershell
python test/story/scripts/run_multi_case.py plan --all --jobs 4 --isolated-workspaces
python test/story/scripts/run_multi_case.py start --all --jobs 4 --isolated-workspaces `
  --suite-id story-suite-20260822-140000 --authorize-non-sandbox
python test/story/scripts/run_multi_case.py poll --suite-id story-suite-20260822-140000 --wait-sec 15
python test/story/scripts/run_multi_case.py status --suite-id story-suite-20260822-140000
```

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

活动 PID、有效 lease、路径越界、软链接风险、未知目录类型、所有权不明或无法可靠枚举进程时，必须
保留现场并在 feature 迁移前停止。部分删除失败时记录每个目标结果并拒绝继续。非 suite 长期目录不
自动清理。features 是迁移归档，不在本轮结束时恢复；本轮 workspace/output 也保留到下一轮。

## 3. 交互驱动

每个 Case 的 `interaction-script.yaml` 提供预设回复。协调器只在 `awaiting_reply` 后核对 turn/kind，
再发送自然语言并记录接受与消费状态。若没有匹配脚本，宿主阅读当前问题、本 Case 公开输入和已发生
交互，给出推进场景所需的最小回复。不得读取其他 Case、历史答案或提示遗漏项。意外行为要继续诊断、
回复和推进，并记录为观测事实。

```powershell
python test/story/scripts/run_multi_case.py reply --suite-id story-suite-20260822-140000 `
  --case split-interactive --reply-mode adaptive --reason "依据当前问题和本 Case 输入" `
  --text "本单先做策略查询与创建签约，状态查询与解约交给兄弟单据。"
```

## 4. 15/120 秒观测

- 未全部稳定进入 Spec 前，每 15 秒读取所有 Case 状态并优先处理交互。
- 事件积压、终态和 `awaiting_reply` 立即处理。
- 全部所选 Case 连续两轮、间隔 15 秒稳定处于 Spec 或后续自动阶段后，才切换到 120 秒。

每轮 15 秒完整观测后统一判断：全部成功启动并曾进入 Spec；所有非终态 Case 当前仍处于 Spec 或
后续阶段；没有 pending、starting、Story 阶段或 awaiting_reply；本轮状态读取全部成功。第一次满足
时确认数为 1 并保持 15 秒，第二次连续满足后写入 `ready_at`，建立绑定当前 suite、每 2 分钟触发一次的 heartbeat，
执行同一 suite 的 poll/status。

任一条件不满足立即清零。已进入 Spec 后终止的 Case 保留资格；未进入 Spec 就失败的 Case 不能触发
120 秒。120 秒期间出现等待回复、阶段回退或状态异常时暂停 heartbeat 并恢复 15 秒；重新连续确认
两轮后再启用。全部后处理完成后关闭 heartbeat 并结束 Goal。

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

回灌依据是 Case 已终态且 workspace 存在。成功或失败 Case 的 `doc/features/<feature>` 都复制回主工程；
受控源码差异仅在主工程无漂移、无冲突时回灌，删除只记录不执行。每个 Case 生成不可变原始
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
python test/story/scripts/run_multi_case.py plan --all --jobs 4 --isolated-workspaces
```

这些命令不启动真实被测 CLI，只检查接口、状态转换、清理预检、稳定观测和确定性规则。
