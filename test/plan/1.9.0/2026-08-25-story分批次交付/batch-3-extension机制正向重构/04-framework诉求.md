# 04 framework 本体诉求（单列，由用户裁定是否立项）

> **批次 3 不改 framework；扩展设计不依赖本文任何一条**（用户 2026-08-28 裁定）。下面四条是效率与可靠性增益，每条附「不改时扩展怎么办」，由用户另行决定是否合入。framework 在本仓只读；改动走 framework 发布分支。

| # | 诉求 | 证据 | 不改时扩展的替代 |
|---|---|---|---|
| 1 | `verify-coding.md` `{script_report}` 出现两次（`:24` 行内、`:57` 代码块）+ `report-generator.ts:257` 全局替换 → harness JSON 内联两遍（43.3KB / 18.4%）；`{context_files}` 改为文件清单让 verifier 自行 Read | AR90004 `coding/reports/ai-prompt.md` 剖析 | 无法替代（模板与拼装都在 framework）；扩展只能把自己的注入压到 ≤15KB |
| 2 | hook **通过也留 CheckResult**（`hooks-dispatcher.ts:177-188` 只在 `ok:false` 记）；hook 崩栈/超时保留 `severityOverride`（`:190-200` 退回 MAJOR） | 见左 | 扩展 `evidence.mjs` 六阶段留痕；每个 post_check 顶层 try/catch 自报 BLOCKER |
| 3 | overlay YAML 解析失败出声（`profile-loader.ts:182-193` 静默 `return current`）；manifest 路径错在 feature 相 BLOCKER（`extension-loader.ts:55-73` 静默清空，只有 `--phase extensions` 报） | 见左 | 扩展 spec post_check 首条自检 manifest 与 overlay 可解析 |
| 4 | `on_context_load` 触发顺序（`:766`）晚于 `post_check`（`:750`），命名与语义相斥；建议拆为 `author_context`（阶段开始、给主 agent）与 `verifier_context`（现行为） | `lifecycle-hooks-schema.yaml:28-29` 描述「While assembling ai-prompt.md」 | 扩展不依赖该事件给主 agent 送任何东西（作者面走入口文件与作业包） |

**建议**：第 1 条是纯 bug（43KB 重复注入）；第 2 条改动最小、价值最大（dispatcher 两处）；第 3、4 条可后置。均不阻塞批次 3。
