# Adapter 工具事件证据源盘点（t3a，plan f7a3d9c2）

> 目的：verified critic 回执（「工具调用发生过且图片输入被注入」的调用侧证明）只能建立在
> **CLI 产生的结构化工具事件**之上——禁止从普通文本正则猜测 Read（解析器契约红线）。
> 本文档是各 adapter 证据源能力的 SSOT；`tool_event_provenance` 声明（adapter.yaml
> goal_capability）必须与本表结论一致，且**每个合格 adapter 须配真实日志 fixture 单测**
> 后方可在 critic-receipt-producer 注册解析器。
>
> 证明力边界（恒定）：验读记录=「工具调用发生过」，≠「模型看懂了图」（invocation
> records, not model cognition）。

## 结论表（2026-07-11 初盘，基于 CLI 静态调用形态）

| adapter | 当前 headless 形态 | 证据源结论 | tool_event_provenance | 状态 |
|---|---|---|---|---|
| claude | `claude -p`（纯文本输出，prompt 走 stdin） | 默认输出**无工具事件**。两条可行路线：①`--output-format stream-json --verbose`——stdout 变 NDJSON 事件流（含 `tool_use`/Read 记录），经 t3a 三文件分流写 agent-events.jsonl（人读投影 agent-output.log 不变，b8f36a12 日志消费链不受影响——**此为选定路线**，理由：事件即时、无 session 定位问题）；②本地 session transcript（`~/.claude/projects/<slug>/*.jsonl` 含 tool_use）——`-p` 不回显 session id，定位靠 mtime 猜，弃 | `structured_events`（**须在 adapter.yaml headless_invoke 显式加 stream-json 参数后才可声明**；未声明前恒 none） | 解析器已实装（`parseClaudeImageReadEvents`）；**待真机 fixture 复验**（t9 前采一份真实 stream-json 日志入 fixtures） |
| chrys | `chrys run --json` | `--json` 信封为结构化输出；**事件粒度是否含逐条工具调用待实测**（现有消费仅解析 headless_interaction_required 信封） | 暂 `none`（实测确认事件含图片读取记录后再升 structured_events） | 待宿主实测 |
| codex | `codex exec`（stdin prompt） | exec 进度输出含命令执行记录，但**codex 无 Read 工具**——本地图片注入走 `view_image`/`-i`，其事件是否稳定出现在 stdout 待实测；`cat` 图片≠视觉注入，不得计入 | 暂 `none` | 待宿主实测 |
| cursor | `cursor-agent -p`（stdin prompt） | 输出为文本流，未见结构化工具事件开关 | `none` | 恒 unverified（复查 CLI 更新再议） |
| opencode | `opencode run --dangerously-skip-permissions`（stdin prompt） | 输出为文本流，未见结构化工具事件开关 | `none` | 恒 unverified（复查 CLI 更新再议） |

## 契约要点

1. **三文件分流**（agent-invoke，`toolEventCapture: 'structured_events'` 时启用）：
   - `agent-events.jsonl`——仅 stdout（NDJSON 纯净）。**attestation 绑定本文件**；
   - `agent-stderr.log`——stderr 分流（stderr 插行会破坏 NDJSON，实测混写已证实）；
   - `agent-output.log`——混合人读投影，既有消费者（API 断流哨兵/心跳/no-output 判定）不动。
2. **解析器只吃结构化事件**：JSON.parse 失败的行直接跳过；不做任何文本正则回退。
3. **无解析器/无声明 = 恒 unverified**：produceCriticReceipt 不产出，agent 侧手写回执
   照旧走 unverified 档；手写 verified 会因缺 runner attestation 被 check 降级。
4. **verified 最低输入集**：visual-diff.json 全部 finalized 屏的被评截图 +（有 paired
   attest 时）全部 crops 均有验读记录；部分缺失 → unverified + unread_* 清单。

## 待宿主复验项（t9 合并执行）

- [ ] claude：真机 goal run 采一份 `--output-format stream-json --verbose` 事件日志 →
      固化为 fixture（`harness/tests/fixtures/`）→ 解析器单测从合成样本换真实样本；
      确认 stream-json 下 b8f36a12 消费链（人读投影不变）确实零回归。
- [ ] chrys：`--json` 事件流是否含逐条工具调用与图片输入记录。
- [ ] codex：`view_image` 事件是否稳定出现在 exec stdout。
- [ ] 结论回填本表 + adapter.yaml 声明同步。
