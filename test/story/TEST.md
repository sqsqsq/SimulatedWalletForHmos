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

### 0.1 测试目标与观测边界

- 正式 Case 是组合业务场景；叙述变形只做离线检查，不构成正式 Case。
- 每个 Case 只能看到自身 workspace、初始任务和已发送交互，不得接触 `test/story/` 维护材料、其他 Case 或历史 suite。
- 观测者（外层协调器）不得替被测模型运行 gate、修改被测产物或清理阶段状态。

### 0.2 宿主在实跑期间的角色：需求方 / 评审人

宿主此时**不是维护者，是提出这个需求的人**。被测模型面对的应当是一个懂业务、不懂本框架的对话方。

| | 做 | 不做 |
|---|---|---|
| 读什么 | 送审给你的归档件（叙事主件与评审记录）——评审意见要从它读出来 | 实现件（规格件、方案、契约、源码）与门禁报告。评审人拿不到也不看 |
| 说什么 | 需求侧的话：范围怎么切、哪条优先、验收期望、评审意见、对某个结论同不同意 | **实现路径**——不点名脚本、命令、文件、字段、门禁与判据 |
| 卡住时 | 重申需求意图，让它自己找出路 | 告诉它该跑哪个命令、该改哪个文件、该走哪条流程分支 |

**为什么这条是硬规则**：说出解法的那一刻，测的就不再是「被测模型能不能自己走通」，而是「宿主
知不知道答案」。实测出现过一次——宿主用维护者口吻回话，把重开流程的路径直接喂了过去。

其余纪律：只 poll / 回复 / 记录；不开子 agent 或后台任务（宿主会话的 Stop/SubagentStop hook 会按
阶段状态往被测 feature 目录写报告）；不在主工程跑 harness。**评测在 finalize 之后以维护者身份做，
实跑期间不切换身份。**

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

**阶段推进是驱动器的职责，不是被测模型的**：`run_case.py` 在每个阶段边界按 `end_phase`
算出下一个未闭环阶段，**指名下发**推进指令（`continuation_reply`——「现在执行 plan 阶段」）。
所以：

- **Case 的 `prompt` 里不写阶段链**。只写起点动作（`/story init …`）、业务任务与执行要求；
  「随后依次完成 spec、plan、coding」这类话一律不写。写了有三个后果：与驱动器双写、
  把「模型会不会自己一路跑」混进观测（测的就不再是驱动器能不能推动它）、
  改终点时两边对不上（实测协调器记着「到 spec 为止」而 prompt 写着「继续完成 plan」，
  模型照 prompt 进了 plan，白跑一段还得人工停）。
- **要改本轮终点，只改 `end_phase` 一行**，不必也不该动 prompt。
- story 流程内的动作（取材、归档送审、评审意见处置）不在 `PHASE_ORDER`（spec…testing）里，
  驱动器不会下发，所以**要写在 prompt 里**——但写成需求方的话（「做到评审」「评审我来回」），
  不是命令名。

### 2.1 prompt 怎么写：说需求，不说做法

prompt 是**提需求那个人说的话**。他懂业务、不懂这套流程，也不知道你在观测什么。

| 写 | 不写 |
|---|---|
| 单号或单据性质、材料在哪、做到哪一步、谁来拍板 | 命令、脚本、文件名、目录名、关卡名 |
| 「有些材料还在我手上，你要的时候跟我说」 | 「先检查占位件，然后要补料」 |
| 「这张只做挂失，补卡我另找人」——**在关卡里说** | 把拆法预先写进 prompt |
| 「这轮别动 doc/extensions、test/story、framework」（工作纪律，唯一的例外） | 「注意材料之间有冲突」「记得保留图片链接」 |

**处置法一个字都不写**：冲突怎么办、未决项怎么办、图片怎么办、要不要拆——
这些正是要观测的东西，写进 prompt 就等于把答案给了它，那一轮测的是宿主知不知道答案。
诉求要由人**在关卡上说出口**（`interaction-script.yaml`），不能预塞进初始 prompt：
模型走到关卡时它已在几十步之外，测出来的是记忆衰减，与关卡交互无关。

判据在 `tests/test_multi_scenario_cases.py`（词表扫描）与 `tests/test_harness.py`。

### 2.2 材料分三处，按真实体验投放

| 目录 | 是什么 | 什么时候到 |
|---|---|---|
| `cases/<id>/system/` | 需求系统上挂着的单据（一个子目录一张单，含 `detail.json` 与正文 md） | 起跑时复制进该 Case 自己的 workspace，被测侧经环境变量看到 |
| `cases/<id>/workspace/` | 起跑那一刻需求目录里就有的东西 | 起跑时 |
| `cases/<id>/supplements/` | 人手上备着、**要来的**那几份 | `deliver: start` 起跑时；`deliver: on_request` 等它开口 |

**需求系统只承载 md，不承载图片**。图片只有一条路进来：人给的文档（docx）里内嵌，
导入时抽出来。多留一条路，「归档件里的图能不能打开」测的就不是真实链路了。

投放由脚本条目的 `deliver:` 触发（先投文件、再发话），宿主实时回话时用
`run_case.py <case> reply --text "…" --deliver <文件名>`，同一条路径。
起跑时收件箱里只有说明书——提前把材料铺满，「它会不会发现材料不够」就永远测不到。

0. **实例前置自检**（缺一不起跑）：`framework.config.json` 配了 `paths.ui_kit_target_dir`
   且该目录已物化 UI kit 组件——没有的话，任何跑到 coding 的 Case 都会被 UI kit 门禁拦死在
   「目标目录无法解析」上，与被测能力无关；主工程 `framework/harness/state/` 下没有属于
   别人的阶段状态（有则先弄清归属，**不要盲目 clear-state**）。
1. 创建本轮 `output/story/<suite-id>/` 控制目录。
2. 扫描并关联 `%TEMP%/sw-story/*` 与 `output/story/*` 中的历史 suite。
3. 整体预检终态、PID、lease、路径边界、软链接和所有权。
4. 全部安全后尝试删除历史 workspace/output，写入 `previous-run-cleanup.json`。
5. 若安全预检通过但个别历史目录删除失败，逐目标记录 `retained_cleanup_warning` 和残留路径，保留现场供下一轮重试，
   不阻断本轮 feature 迁移、workspace 创建或 CLI 启动；只有活动 PID、有效 lease、路径越界、软链接风险、所有权不明或
   进程无法可靠枚举等安全预检失败才停止。
6. 清理预检通过后，将当前 `doc/features/*` 整体迁移到
   `E:\Project\bak\Story-Features-<时间戳>/`。
7. 创建模板及各 Case workspace，再顺序启动 CLI。

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

每个 Case 的 `interaction-script.yaml` 提供预设回复。协调器只在 `awaiting_reply` 后核对 turn/kind
与可选的 `expected_phase`，再发送自然语言并记录接受与消费状态。若没有匹配脚本（或该 Case 没有脚本文件），
宿主阅读当前问题、本 Case 公开输入和已发生交互，给出推进场景所需的最小回复，然后同一回合立即再次
`poll` 确认消费并继续驱动。

`expected_phase` 是回复的**阶段前提**（`story` / `spec` / `archived`）：turn 编号只说「第几关」，
说不出「这一关在哪个阶段」。评审意见这类回复必须在归档之后才有意义——只按 turn 排队，
模型少停一关就会把后面的话提前送进前面的关卡。回落原因：

| `last_adaptive_request.reason` | 含义 |
|---|---|
| `interaction_script_exhausted` | 脚本用完，后面的关卡由宿主实时回 |
| `interaction_gate_mismatch` | 关卡编号或类型与脚本下一条对不上 |
| `interaction_phase_mismatch` | 编号类型都对，但阶段前提未满足（如评审意见的关卡出现在归档之前） |

**`awaiting_reply` 必须在它出现的那一次唤醒内回复完毕**：poll 返回的
`adaptive_reply_requests[].question` 就是模型的原话，`case_inputs_hint` 是本 Case 的公开输入清单，
当轮即可作答，不需要另开一轮去翻 runlog。只看 `status` 不读 `question`、把回复推到下一个周期，
按协调失误记入观测记录——一次跨周期等待就是白等一个完整间隔。
有 Case 处于 `awaiting_reply` 时 `next_interval_sec` 一律回到 15 秒，不受自动化稳定态影响。不得读取其他
Case、历史答案或提示遗漏项。意外行为、维护文件名或任何关键词只能记录和理解，不能据此调用
`stop`；`stop` 只响应用户明确要求。单个 Case 失败也不得停止其他 Case。

```powershell
python test/story/scripts/run_multi_case.py reply --suite-id story-suite-20260822-140000 `
  --case <case-id> --reply-mode adaptive --reason "依据当前问题和本 Case 输入" `
  --text "这张只做挂失，补卡那张我另外找人做。"
```

回话要带上人手上的材料时，加 `--deliver <文件名>`（文件名取自该 Case 的
`supplements/`）：文件先落进收件箱，那句话才排进队列。反过来，模型会照着
「我放进去了」这句话去看一个还不存在的目录。

### 3.1 用脚本代跑 heartbeat 时：`reply_then_poll` 必须把宿主叫醒

上一条纪律（当轮回完）只在**人或模型亲自看每一次 poll 返回**时成立。实际操作里宿主常把
heartbeat 交给一个后台轮询脚本代跑——那个脚本若只做「poll、按 `next_interval_sec` 睡、再 poll」，
`reply_then_poll` 就没有任何出口：驱动器一直等，日志一直刷，没有人被通知。
实测一轮：两个 Case 分别空等 **45 分钟**与 **33 分钟**，其间轮询正常、状态正常、
`last_error` 为空——**没有任何异常信号**，只有 `next_action` 那一行在反复说「该回话了」。

所以代跑脚本必须满足两条，缺一条这段等待就会重演：

1. **`next_action == "reply_then_poll"` 时立刻退出**（或以其它方式唤醒宿主），不要自己续睡；
2. 退出前把「因为要回话而停」写进日志——事后看得出是**等宿主**，不是脚本自己挂了。

脚本只负责按间隔敲门与在该叫人时叫人；**判断一律留在驱动器里**，多想一步就会与它分叉。

### 3.2 模型的原话取不到时去哪儿读

`adaptive_reply_requests[].question` 是首选，但它可能是空串（`status` 子命令甚至返回 `null`）。
此时**不要凭 `case_inputs_hint` 猜模型在问什么**，按下面顺序取原话：

| 读什么 | 给你什么 |
|---|---|
| `output/story/<suite>/cases/<case>/observations.jsonl` 末条 | 这次停等的 `kind` / `turn` / `reason` |
| 该 Case run 目录下 `events.jsonl` 尾部的 `type: text` 事件 | **模型说的最后一段话**——它问的问题就在这里 |

读的是模型对需求方说的话，不是它的产物——观测边界（§0.1）不变：产物内容仍然不读。

### 3.3 `expected_phase` 漂移的处置：换回法，不换话术

模型少停一关或多停一关，脚本后面的话就会与阶段对不上，落成
`interaction_phase_mismatch`。处置是**用那一关本该说的那句话以 adaptive 方式回**
（话术是需求方的话，不因阶段变而变），跑完再把脚本里的 `expected_turn` / `expected_phase`
按实跑顺序校准回来。**不要为了让脚本对上而改话术**——话术一改，这个 Case 观测的就不是同一件事了。
本轮两个 Case 都漂了一关：一个的术语确认排在 story 之后才轮到，另一个的第二份材料模型自始至终没开口要。

### 3.4 改测试终点：改 `case.yaml` 的 `end_phase` 一行

**终点的真源是 `case.yaml` 的 `end_phase`**，`cases/` 里的注释本就写明了这一点。
要让某一轮停在 spec 或 plan，就改那一行——一个 Case 一行，改完即生效，
不必也不该在命令行上想办法。`cases/` 属被测输入，改它单独记一笔账。

`--end-phase` 是**同一件事的命令行 override**，不是坏的：`start` 收到它以后会随
后台驱动进程一路传下去（`run_case.py` 的 `start` → `run`，驱动器用的就是 override 值）。
容易读错的是回显——suite 记录里每个 Case 的 `end_phase` 字段**始终回显 `case.yaml` 的原值**，
override 记在 `requested_end_phase` 与 `effective_phase_scope` 两个字段里。
只看 `end_phase` 会得出「传了不算数」的结论，那是回显差，不是装置缺陷。

另一件与终点相关、确实要提前想好的事：`stop` **只有整 suite 一档，没有单 Case**
（`command_stop` 遍历全部 case_states）。两个 Case 终点不同时，先到终点的那个会一直挂着，
直到另一个也跑完才能一起停。所以两个 Case 的 `end_phase` 差得越远，空转越久——
F4 那轮实测空转 18 分钟。终点分歧大时，把它们分两个 suite 跑更省。

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
再次零等待 poll（heartbeat 由脚本代跑时见 §3.1——脚本必须在这一步把宿主叫醒，否则这句话落空）。返回 `finalize` 时执行回灌、输出逐 Case 汇总并暂停 heartbeat，不调用 `stop`。

heartbeat 提示词必须包含当前 suite-id，并要求：每次只执行一次 `poll --wait-sec 0`；处理自适应回复后
立即再 poll；按 `next_interval_sec` 更新当前 heartbeat；每轮展示简短完整快照；命令失败时诊断并重试
一次，仍失败则保留 15 秒节奏并报告；终态 finalize 后暂停当前 heartbeat。重复唤醒不得创建新任务。

## 5. 状态与证据

静默不是终态，`awaiting_reply` 必须处理。历史清理的 `completed_with_warnings` 不是 Case 失败；只要安全预检通过，
协调器继续测试并在下一轮起跑重试残留。权威状态只来自 `state.json` 和运行事件。典型目录：

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

**阶段闭环凭证**：`trace.json`、`summary.json`、完成回执，以及 **verifier 报告**——
后者认一组文件名（`verifier.report.md` / `verifier-report.yaml` / `verifier-*-result.yaml` /
`verifier-*.md` / `verify-*.md`），任一存在即算。命名不是契约：按单一文件名判闭环时，
换个命名就会被判成「未闭环」，驱动器会反复下发同一条推进指令而模型正确地拒绝重跑。

**`stop_reason` 语义**：`phase_turn_budget_exhausted` = 同一阶段连续续话超过 `PHASE_TURNS`
上限仍未闭环（空转，已中止）；`awaiting_reply_timeout` = 等人回话超时；
其余为 CLI/基础设施原因。出现 `phase_turn_budget_exhausted` 时先查该阶段的闭环凭证是否齐备，
再查驱动器判据与被测产物命名是否对得上。

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

finalize 前确认主工程的阶段状态文件不存在、或不属于本次 feature——否则宿主会话的 hook 会按那份状态
把报告写进回灌后的产物里，事后分不清哪些是被测模型产出的、哪些是宿主的副作用。

## 7. 离线验证

```powershell
python -m unittest discover -s test/story/tests
python -m unittest discover -s tools/cli/tests
python -m compileall -q tools/cli test/story/scripts
python -m tools.cli.scripts.validate_clis
python test/story/scripts/run_multi_case.py plan --all --jobs <实际Case数> --isolated-workspaces
python test/story/scripts/check_failure_modes.py
node --check <每个 doc/extensions 下的 .mjs>
```

这些命令不启动真实被测 CLI，只检查接口、状态转换、清理预检、稳定观测和确定性规则。

### 7.1 失效形态全量回归

`check_failure_modes.py` 跑 `regression/failure-modes.yaml` 的全部形态，两段缺一不可：

| 段 | 对象 | 判据 |
|---|---|---|
| 夹具自检 | `fixtures/failure-modes/<id>/{bad,good}` | 反夹具必 FAIL、正夹具必 PASS；不过 = checker 本身失效 |
| 真实目标 | 机制层 = `doc/extensions`；产物层 = `--feature` 指定的**新**产物 | `status: fixed` 的形态一条不许命中 |

`status: pending_capability` 报 SKIP（目标能力尚未建，不算回归失败）；`retired` 须带 `reason` + `approved_by`。

`--historical` 是**观察档**：对实施前基线样本（`doc/features/*` 与
`E:\Project\bak\Story-Features-*`）跑产物类 checker。这些样本本就含历史缺陷，检出是预期结果
（等同额外的反夹具），**不参与 PASS/FAIL**。

### 7.2 机制层负面扫描

提交前固定跑，期望全部零命中（对应台账 M01–M04）：

```powershell
grep -rnE "\b[A-Z]{2,8}-[0-9]{2}\b" doc/extensions --exclude-dir=knowledge
grep -rnE "\b(AR|DTS|ISSUE)-?[0-9]{4,}\b" doc/extensions --exclude-dir=knowledge
grep -rnE "\b0[1-9]-[A-Z][A-Za-z]{3,}\b" doc/extensions --exclude-dir=knowledge
grep -rnE "[A-Za-z]:[\\/]|\bbackup/" doc/extensions
```

**扫描面含 `.md`**：早先只扫代码、放过 Markdown（理由是「写作指令允许出现形态示例」），
实测 16 处硬编码里有 10 处藏在注入件里全部逃检——注入件恰恰是模型直接读到的东西，
它写死了域名，新增一个域时模型就照着旧清单干活。

人工快查会有噪声（占位形态、反例说明、激活清单本身都会命中），准确判定以
`check_failure_modes.py` 的 M01/M17 为准：它们的基准从激活清单派生，
能区分「真实标识」「占位形态」「查无此物的死判据」三种情况。

### 7.3 三条维护不变量的机械回归

`AGENTS.md §2` 的四条约束各有对应形态，**只写文档会被跳过，机械回归不依赖记忆**：

| 不变量 | 台账形态 |
|---|---|
| 机制层零测试特征（反过拟合） | M02（从 Case 目录动态提取业务词） |
| 机制层不硬编码 knowledge 内容 | M01（真实标识）+ M17（查无此物的死判据） |
| 正向实现，不打补丁 | M16（死代码 / 静默降级 / 待办标记） |
| 知识不含维护信息、定位只写一处 | M18（facts 引规约编号 / 知识指向机制 / 规约带源码路径 / 阶段矩阵；经真实 `selfCheck`） |

## 8. 实跑效率度量（批次 3 · 七项目标）

跑完一轮后，用 `measure_run.py` 从 `events.jsonl` 读出这七项。**它只报数，不判 PASS/FAIL**
——数字是诊断信息，不进写作命令、不进 PASS 条件（G8）。达标与否由人看着数字判断。

```bash
python test/story/scripts/measure_run.py output/story/<suite>/cases/<case>/<run>
python test/story/scripts/measure_run.py <同上> --json      # 需要机器读时
```

| # | 指标 | 目标 | 诊断基线（批次 3 之前） |
|---|---|---|---|
| 1 | 门禁回环时间占比 | < 15% | **49.3%**（spec 47.4 min / plan 10.5 / coding 11.5） |
| 2 | 作者读 `framework/**` + `doc/extensions/**` | ≤ 20 次/阶段 | 60 + 40 次 |
| 3 | **读 checker 源码** | **0** | `check-spec.ts` 被读 9 次；14 条 bash 在 grep checker 反推判据 |
| 4 | 同一 check id FAIL 次数 | ≤ 2 | 5（`lifecycle_hook_post_check_extension` 洋葱式暴露五层） |
| 5 | spec 阶段上下文增量 | ≤ 150K | +397K（全程 11K → 818K，零 compaction） |
| 6 | verifier 扩展注入 | ≤ 15KB/阶段 | spec 阶段扩展占 prompt 44.3% |
| 7 | `doc/extensions` 非知识层行数 | ≤ 7500（未达成时如实写「未达成」，不改本目标） | 基线 10358 |

**第 3 项是最直接的信号**：作者去读 checker 源码，说明它从别处拿不到要求——
批次 3 的作者面通道（入口文件 → `hooks/<phase>/author.md` → 模板 → 报错文案）就是为它建的。
这一项不为零，说明通道没通。

第 5 项要在 **spec 阶段单独取**：成文由 writer 子 agent 在新鲜上下文里做，主 agent 不读材料，
增量应显著下降；若仍接近基线，说明 writer 子 agent 没有真的独立跑（KC-4）。

## 8.1 内容基线对照：新写的比以前少讲了什么

与 §8 并列，同样**只报数**（G8）。跑完一轮、story 成文之后，对每个 Case 做一次。

```bash
python test/story/scripts/baseline_coverage.py <新的 AR/story.md> --baseline AR90004
python test/story/scripts/baseline_coverage.py <同上> --baseline AR90004 --json
```

对照物是 `fixtures/content-baseline/` 里那三份批次 1 实跑产出的 story，它们冻结不动。
**不跟上一轮比**——那样每轮只需比上一轮好一点，慢慢就滑走了；**不跟批次 3 的产物比**
——那本身是已知劣化的。

**对照是单向的**：只判「基线有而新 story 无」，不判反向。基线自己也有重复和工程细节
泄漏，那正是批次 4 要治的，当满分去对齐会把旧毛病一起抄回来。

输出里有三样：

| 项 | 怎么读 |
|---|---|
| 覆盖率 | 与同一行的**机器可核上限**比，不与 1.0 比。上限是基线对照自己的结果——有些单元短到切不出可核片段，机器在任何文档里都核不到它们 |
| 缺失清单 | 逐条点名（来源行、类型、正文）。只报个数字，人无从判断丢的要不要紧 |
| 形态对照 | 行数 / 章 / 表行 / 围栏图 / 图片，新的少于基线就标出来 |

机器只能说「这几条找不到」，说不了「丢掉要不要紧」——那要人看。
机器核不到的那些由裁决者的三张表管，不在这里判死。

## 9. 常驻行为回归：审稿者审不审得出「没讲」

与 §8 并列，同样**只报数**（G8）。跑完一轮后，对**每个到达 spec 的 Case** 做一次。

story 的守恒分三层：机器层守可核事实（token、图、编号），模型层守语义（裁决者逐条裁），
人层抽样。前两层的数由 `measure_run.py` 报（「机器核实 N 条 / 模型裁决 M 条」）。
**机器层可以自证，模型层不能**——它说「讲清了」，你没有别的办法知道它是不是在盖橡皮章。
唯一的办法是给它一份**已知有缺口**的产物，看它报不报。

### 怎么做

1. 取该 Case 的 `AR/story.md` **副本**（连同 `story-src/` 一起复制到临时目录，别动原件）；
2. 从副本里删掉 **5 个事实**，其中**至少 2 个是纯中文单元**（没有 token、机器核不到的那种
   ——正是模型层独自负责的部分）。记下删了哪 5 条；
3. 另外**整章挖空一处**：挑一章，把它的正文换成一句无关的话（不要换成「本需求不涉及。」
   ——那是合法的空章，判据会豁免它）。记下是哪一章；
4. 在副本上重跑 verifier 子 agent（prompt 用 `phases/story-verify.md`）；
5. 三张表分别数：
   - **逐单元**：多少条「未讲清」，点名的是不是你删的那 5 条；
   - **逐问**：挖空那一章的读者问题，是不是被裁成「没答」；
   - **逐章**：挖空那一章的六个维度，有没有判出「不达标」。

### 判据与处置

| 结果 | 含义 |
|---|---|
| 逐单元 ≥5 条「未讲清」且点名对上，且挖空那章在逐问被裁「没答」、逐章被裁「不达标」 | 三张表都有区分力，这一轮的裁决可信 |
| 报了但点名对不上 | 它在猜。检查作业书是不是又掺进了整篇印象题 |
| 逐单元报了、逐问逐章全绿 | 后两张表在盖橡皮章——整章都换成无关内容了还判「答了」，说明它没真去读那一章 |
| **一条都没报** | **模型层无效**——这一轮所有「讲清」都不作数，回 `phases/story-verify.md` 看任务是否良定 |

不删事实、不挖空时再跑一次作对照：结果应与现产物一致；不一致说明裁决本身不稳定。

**这一项不达标不改 check**：不要往 `story-build check` 里加相似度或重叠度判据去补。
机器判不了「这句是不是在讲那件事」——加了只会得到一个能被措辞绕过的假门禁，
真正要修的是作业书里那个任务定义。
