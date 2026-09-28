# 问题记录 · writer 子 agent 返回空、不落盘

> 2026-08-29 记录。**只记问题，方案另议**（用户裁定）。
> 阻塞对象：KF-1b（ISSUE-410 CLI 重跑到 plan）。该轮已按用户要求 `stop`。

## 现象

writer 子 agent 被 Task 启动后，跑完返回**空结果**，`AR/story.md` 没有落盘。
外层看到的是 `<task state="completed">` + 空 `<task_result>`——**报成功，实则没产物**。

## 频次：4 次尝试 3 次空

| 轮次 | Case | 结果 |
|---|---|---|
| `story-suite-20260828-191953` | AR90004 | 第 1 次空 → 第 2 次成功（37KB story 落盘） |
| `story-suite-20260829-101242` | ISSUE-410 | 第 1 次空 → 第 2 次空 → 停在第 3 次 |

上一轮我登记为 O6「待判：是作业书没写清，还是子 agent 侧的返回约定问题」。现在两个 Case、
两个独立会话都复现，**不是偶发**。

## 排除了什么（被测模型自己做的诊断，证据在 events.jsonl 的三次 task 调用里）

| 假设 | 证伪 |
|---|---|
| 是 prompt 没说要写文件 | 第 2 次 prompt 明写「**第二步：用 Write 工具**把 `AR/story.md` 一次写成」，14 个标题、判定表编号全列了——仍返回空 |
| 是子 agent 不能写文件 | 被测模型做了控制实验：让子 agent 写 `hello` 到临时文件 → **成功**并返回路径 |
| 是输出被截断 | 上游 issue 明确排除：「output size is minimal, well below limits」 |

**结论：与提示词无关，与子 agent 的文件写入能力无关。只在「读 8 份材料 + 写一篇 14 章长文」
这个规模上发生。** 第 2 次跑了 14 分钟才交回空手。

## 上游：opencode 的已知未修缺陷

同一形态在 opencode 仓库有多条 open issue：

- [#32132 Subagent terminates prematurely mid-execution but reports completed](https://github.com/anomalyco/opencode/issues/32132)
  ——与我们观测到的形态完全一致（提前终止 + 谎报 completed + 空结果）。
  作者列了三个疑似成因：Task 工具里的硬超时（~30–60s）、LLM provider 中途超时、
  工具调用挂死中断子 agent 循环。**无维护者回复、无修复版本、仍 open。**
- [#27210 GPT OSS 120B subagent stops mid-reasoning and returns empty result after several tool calls](https://github.com/anomalyco/opencode/issues/27210)
- [#18423 Ollama subagent executes tool calls correctly but always returns empty text to orchestrator](https://github.com/anomalyco/opencode/issues/18423)
- [#18378 Subagent tasks hang indefinitely in high-concurrency environment](https://github.com/anomalyco/opencode/issues/18378)
- [#6792 Task Tool Timeouts & Early Termination in Multi-Agent Conductor Pattern](https://github.com/anomalyco/opencode/issues/6792)
  ——提问者试过 provider 级 600000ms 超时、agent 级超时设置，**全部无效**；
  Task 工具本身**没有可配的超时参数**。该 issue 被 **Closed as not planned**。

**与我们观测的出入**：#32132 猜的是 30–60 秒硬超时，而我们第 2 次跑了 14 分钟才返回空。
所以更像「provider 中途超时」或「工具调用挂死」那两条，不是固定短超时。

上游 issue 里出现过的通用规避只有一条：**把长任务拆成更短的顺序子任务**
（#6792 结论段）。**这里只作记录，不作为本项目的方案**。

## 对 story 链的影响

作业书要求「**一份写成**」，于是 writer 的产出是**全有或全无**：子 agent 返回空时磁盘上
没有任何中间产物，前面读的 8 份材料全白读，重试从零开始。

对比同一条链上的 verifier：它的作业书有「## 产物：写 `story-verdicts.md`」，任务是**逐条追加**，
本轮两次对抗测试都一次落盘成功。

> **这条对比后来被推翻**（见文末「追加观测」）：verifier 在 61 条的规模上同样空返回。
> 空返回与任务能否分段无关，是子 agent 在这个规模／时长上普遍不稳。

## 待定

成文机制怎么改由用户裁定——它会动到「一份写成」这条口径（C 批次为了治「同一事实被四个
章节合同各指一次、于是写四遍」才定的），不在本轮自作主张。

## 追加观测（2026-08-29，suite `story-suite-20260829-115836`）

**verifier 子 agent 也空返回了一次**，被测模型自己接手完成。

- ISSUE-410 spec 阶段：story 已成文（14 章、audit 待处理 0），起 verifier 子 agent 裁 61 条
  `by: author` → 子 agent 返回空、未写 `story-verdicts.md`；
- 模型原话：`Sub-agent returned nothing and wrote no file. I'll adjudicate myself
  (host has Task but sub-agent failed; per SKILL the main agent can do it).`
- 它引用的正是 D5 写进作业书的那句「子 agent 可选，没有 Task 的宿主主 agent 自己做」，
  并把它用在**子 agent 失败**这个场景上——**机制不依赖子 agent，这一条在真实失败下被验证了**。

**这条推翻了一个中途假设**：此前观察到「writer（整篇、不可分段）空返回，而 verifier
（逐条追加、可分段）两次对抗测试都成功」，据此猜过「能分段的子 agent 任务是稳的」。
现在 verifier 在 61 条的规模上也空返回，**说明空返回与任务能否分段无关**，
是子 agent 在这个规模/时长上普遍不稳（与上游 issue 描述一致）。

因此 D5 的价值不是「把任务改成可分段所以子 agent 就稳了」，而是
**不把机制押在子 agent 上**——分段带来的是主 agent 自己也做得动、断了能续。

累计：**6 次子 agent 调用，5 次空返回**（writer 4 次里 3 次空、verifier 1 次空；
另有 2 次对抗测试的 verifier 调用成功，那是本会话直接起的、不经被测宿主）。
