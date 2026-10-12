# tools/cli：同步副本（禁改）

本目录是中央底座 **`C:\Users\kangz\.agents\tools\cli-runtime`**（独立 git 仓）的同步副本，
由其 `sync.py` 维护。**禁止直接编辑** `tools/cli/**` 与 `test/tools/cli/{tests,fixtures}/**`——
它们会在下一次同步时被覆盖，本地改动会以孤儿逻辑的形式留在仓里。

> 2026-10-12 切换记录：本目录原为独立 fork（含包内测试）。切换后运行时与中央 v1.0.0
> 逐字节一致（新增 dsh provider、`model_in_argv`、kill-safety 终止模型、`open_text_retry`
> 流式读），包内旧测试（29 项，针对旧运行时）已被中央契约测试（55 项，位于
> `test/tools/cli/tests`）取代并移除。`TEST.md` 与 `cli_observation_harness_reference.md`
> 为本仓保留的历史文档，不随底座同步。

## 日常操作

```powershell
$central = 'C:\Users\kangz\.agents\tools\cli-runtime'

# 漂移检查（有 CHANGED/EXTRA_LOCAL = 本地被私改或落后中央，都属异常）
python $central\sync.py --check E:\Project\SimulatedWalletForHmos

# 同步到本仓（写 tools/cli/.sync-stamp.json）
python $central\sync.py --to E:\Project\SimulatedWalletForHmos --keep TEST.md --keep cli_observation_harness_reference.md
```

## 需要新能力 / 修缺陷

到中央仓改 + 测（`pytest test/tools/cli -q`）+ commit + tag，再执行上面的同步。
同步后在本仓跑：

1. 工具契约测试：`python -m pytest test/tools/cli -q`（含 kill-safety 回归）；
2. 消费者冒烟：本仓消费方为 `test/scripts/run_case.py` 等评审脚本
   （`CliClient.start/poll/stop` 用法，公开 API 与切换前一致）；按本仓测试门禁执行。

## 边界

- 同步范围：`tools/cli/**`（镜像，多余文件会被删除——`--keep` 可保护过渡文件）；
  `test/tools/cli/{tests,fixtures}/**`（只增改、不删除）；
- 当前版本：读 `tools/cli/.sync-stamp.json`（中央 commit + tree hash + 时间）。
