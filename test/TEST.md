# Story 并行 CLI 测试指南

本指南是 Story 测试域的操作协议。维护约束见根 [AGENTS.md](../AGENTS.md)，规则的事故来源与演进见 [EVOLUTION.md](EVOLUTION.md)。
这些维护文件不进入被测模型上下文。

## 按当前任务读取

| 任务 | 读取 |
|---|---|
| 启动、恢复或驱动真实 Story CLI | §0–§4 完整读；结束后按 §6 评价 |
| 维护脚本或做离线验证 | §5 及本次涉及的运行分支 |
| 评估已有测试、比较历史或对照金样 | §4.3 证据、§6 |
| 定位 verifier 链路故障 | §5.1；真实 smoke 另按 §5.2 与 §0 的授权边界 |
| 排查真实稿件与审查结论不符 | 先按 §6.2 还原证据，确需专项诊断再读 §6.3 |
| 人手试用 `/story` | §1.3 |
| 编写或修改 Case | [cases/README.md](cases/README.md) |

命令参数与配置以当前入口及配置文件为准。

## 0. 边界与授权

### 0.1 谁在测什么

- 宿主是外层协调模型，负责测试生命周期、观测和回复；被测模型是隔离 Case 中由 CLI 启动的模型。
- 正式 Case 是组合业务场景；叙述变形只做离线检查。
- 每个 Case 只能看到自身 workspace、初始任务和已发送交互；它接触不到 `test/`、`doc/` 维护材料、其他 Case 和历史 suite。
- 被测模型自己跑 gate、改产物、管阶段状态；宿主只观测和回话，也不在 demo 里跑 harness。

### 0.2 非沙箱授权

CLI 测试一律以非沙箱启动（用户长期授权，每轮不必重新征求）：`start` 传 `--authorize-non-sandbox`，`plan`、`poll`、`reply`、`conclude`、
`finalize` 同样在非沙箱环境跑。驱动器要拉起并探测子进程、读写隔离 workspace、把需求产物回流到维护仓 `doc/features/`、把源码回灌进 demo。
这条只管宿主，不写进 Case prompt。宿主自身的权限层拦下某条命令时请用户放行，不改写命令绕开；绕过去的那一跑不算数。

真实 CLI 只在用户启动或明确授权时运行；重复运行与换场景按本轮方案与用户授权安排。

### 0.3 宿主在实跑期间是需求方 / 评审人

宿主的维护角色见 [AGENTS.md §1](../AGENTS.md#1-本项目的角色职责)；实跑期间它只代理需求方和评审人：
被测模型面对的是一个懂业务、不代它研究框架实现的对话方。

| | 做 | 不做 |
|---|---|---|
| 读什么 | 送审给你的归档件（叙事主件与评审记录），评审意见从它读出来 | 实现件（规格件、方案、契约、源码）与门禁报告 |
| 说什么 | 需求侧的话：范围怎么切、哪条优先、验收期望、评审意见、对某个结论同不同意 | 实现路径：脚本、命令、文件、字段、门禁与判据 |
| 卡住时 | 重申需求意图，让它自己找出路 | 告诉它跑哪个命令、改哪个文件、走哪条流程分支 |

这是硬规则：说出解法的那一刻，测的就成了宿主知不知道答案。heartbeat 与 `watch` 只负责唤醒观测（§3.5），不另派 Agent 研究或改写被测产物；
评测在 finalize 之后做，实跑期间不切换成实现维护职责。

## 1. 准备

### 1.1 选 Case

宿主完整读过 §0–§4 后，用户输入「开始测试」即进入编排。每次从当前 `cases/*/case.yaml` 动态读取可用 Case，生成编号多选项并另列
「全部当前 Case」，允许单选、多选或全选。确认前复述实际 Case、feature、目标阶段、隔离 workspace 和回流范围；确认之前只执行 `plan`
等只读检查。本轮要改终点时改 `case.yaml` 的 `end_at`；`--end-at` 只作一次性覆盖（§4.1）。

### 1.2 起跑前的固定顺序

0. **实例前置自检**（缺一不起跑）：`framework.config.json` 配了 `paths.ui_kit_target_dir` 且该目录已物化 UI kit 组件，否则跑到 coding 的
   Case 都会被 UI kit 门禁拦在「目标目录无法解析」上；demo 的 `framework/harness/state/` 下没有属于别人的阶段状态（有则先弄清归属，
   再决定是否 clear-state）；demo 是发布基线：顶层没有维护目录（`test`、`tools`、`output`、`scratch`、`.bak`、`.git`）、没有 `doc/features`，
   git 查询成功且非忽略改动为空。Windows 上被测 CLI 在 PATH 里解析到原生可执行文件，不是 npm 的 `.cmd` 包装（配法见
   [tools/cli/README](../tools/cli/README.md)），否则首条请求会在启动前被拒。
1. 创建本轮 `output/story/<suite-id>/` 控制目录。
2. 扫描并关联 `%TEMP%/sw-story/*` 与 `output/story/*` 中的历史 suite。
3. 整体预检终态、PID、lease、路径边界、软链接和所有权。
4. 全部安全后删除历史 workspace/output，写入 `previous-run-cleanup.json`。个别目录删除失败时逐个记录 `retained_cleanup_warning`
   与残留路径，下一轮重试，本轮照常继续。
5. 将维护仓 `doc/features/` 下的需求目录（上一轮回流的需求产物）归档到 `doc/features/archive/Story-Features-<时间戳>/`，本轮结束不恢复；
   `archive` 自身不搬，意外出现的文件留在原处并记入 `feature-migration.json`。`archive` 是保留名，需求编号与它同名的 Case 在读取时即被拒绝。
   单个 Case 新链起跑时，工作区里同名的旧产物存进该次运行输出目录的 `feature-history/`。
6. 创建模板及各 Case workspace，再顺序启动 CLI。

活动 PID、有效 lease、路径越界、软链接风险、未知目录类型、所有权不明或无法可靠枚举进程时，保留现场并在第 5 步之前停止。
非 suite 的长期目录不自动清理。

模板按固定顺序装配：核 demo（结构、没有 `doc/features`、git 干净、记下提交）→ 复制 demo（排除 `doc/features`、Framework 活动状态、
`oh_modules`、`build`、`.hvigor`、`__pycache__` 等运行态，业务模块自己的单测目录照常带上）→ 把根 `extensions/` 的当前开发源（含未提交改动）
装进模板的 `doc/extensions/`、按原生物化写宿主入口 → 核模板与开发源逐字节同源 → 再核 demo 提交与干净状态未变。任一步不成立，模板作废、
不建 Case、不起跑，修好后重新装配。各 Case 工作区从模板复制，
再放入该 Case 的输入；启动前检查路径边界与软链接，并在 `workspace-boundary.json` 记录 demo 提交、`copied`、`excluded`、安装结果和各 Case 的
`case_seeded`。

### 1.3 人手试用

人手试用在从 demo 复制出的隔离副本里做，用的是 demo 装着的发布版扩展；demo 本身保持发布基线。bootstrap 装好本地需求系统、验证链路，
再按模板的复制规则把 demo 复制到系统临时目录的 `sw-story-trial/<时间>`，回执给出路径：

```powershell
python test/scripts/bootstrap_local_story.py --verify AR90006     # 单据装到 test/requirement-system，临时目录验证链路，建试用副本
$env:STORY_REQUIREMENT_SYSTEM_DIR = "<回执里的 system_dir>"
cd "<回执里的 trial_root>"                                         # 在副本根下起 CLI 会话，说 /story init <单号>
```

产物只落在副本的 `doc/features/`，用完自己删；不设这个变量时，副本里的替身对接层报「需求系统不可达」。开发版的试跑走 §1.2 的模板装配。
正式 CLI 测试不用它，每个 Case 用自己的隔离系统快照。

## 2. 起跑

正式测试统一使用 `scripts/run_multi_case.py`，只跑一个 Case 也一样，不直接运行 `run_case.py`。以下都在非沙箱环境执行（§0.2）：

```powershell
python test/scripts/run_multi_case.py plan --all --jobs <实际Case数>
python test/scripts/run_multi_case.py start --all --jobs <实际Case数> `
  --suite-id story-suite-20260822-140000 --authorize-non-sandbox
python test/scripts/run_multi_case.py poll --suite-id story-suite-20260822-140000 --wait-sec 0
```

`plan` 只读确认选中的 Case、feature、目标阶段；`start` 起跑并返回 `next_action=poll_after_interval`、`next_interval_sec=15`。宿主随即创建绑定
suite-id 的 heartbeat（§3.5），启动回合可以结束，之后由定时唤醒驱动。`status` 只做只读诊断：不消费事件、不回复、不计观测，不能替代 `poll`。

Case 严格顺序启动：前一个取得有效 run-id、worker/lease 和活动状态后才启动下一个，启动后的 worker 并行运行。启动失败时检查活动指针、run、
worker、lease、workspace 和原始输出，最多恢复重试 3 次；仍失败则保留完整事实并继续启动其余 Case。启动重试与租约判的是进程起没起来、
还在不在，不是进度快慢。不套外层 timeout 或输出截断管道。

### 2.1 CLI 配置组与单 Case 故障重跑

CLI 宿主按 `config/test.yaml > cli.configurations` 的顺序选，配置条目以该文件为准。配置组只处理 CLI 基础设施失败；材料交付、范围拍板、
关卡回复与 `conclude` 仍由宿主按 §3.2、§4.2 判断，切换配置不自动作答。

| 失败 | 识别 | 当前 Case | 其他 Case |
|---|---|---|---|
| 内容审查 400 | 只认 `DataInspectionFailed` / `Output data may contain inappropriate content` 等明确签名；裸 400 不算 | 保存失败 attempt，同一配置从干净基线重跑一次；再次命中则终态 `content_policy_rejected` | 不停、不重跑 |
| 鉴权 401 | `auth_required`（401 / unauthorized / invalid api key） | 该配置在本 suite 熔断，从干净基线切下一配置；全部耗尽则终态 `cli_config_exhausted` | 已运行的不强杀；后续 attempt 跳过已熔断配置 |

「干净基线」同时重建该 Case 的隔离 workspace、需求系统快照、补料投放状态、交互规划游标和阶段观测游标；失败 attempt 的 artifact、事件、
原始输出与记录保留在本 suite。重跑是原 suite 内的单 Case attempt，回到相同业务起点后仍等宿主逐关回复。`poll` 快照展示 attempt、
`cli_config_id`、`failure_kind` 与配置健康状态，宿主不用手工执行重跑。

## 3. 观察与回复

### 3.1 一次 poll

一次 `poll --wait-sec 0` 是完整事务：读取 suite 全部 Case，并行消费所有非终态 Case 的新事件、模型输出、阶段和状态，把每个真实
`awaiting_reply` 连同「这一关按规划本该表达什么」交给宿主，最后统一计算稳定状态。poll 自身不等待，等待只来自定时器。

阶段不按模型回复文本猜，也不看目录出现没有：从需求流程契约与 worker 每回合发布的原生终点观测（`closure`）推出，依次是 `story`（成文登记之前）、
`design_handoff`（施工单位还没全部可施工）、各原生阶段（所有活动施工单位里最早还没闭环的那个）。`current_phase` 是当前阶段，
`highest_phase_reached` 是本轮到过的最远阶段、不回退（`last_phase` 与 `current_phase` 同值），需求首次成文登记时写入 `story_done_at`。

每次返回 `suite_terminal`、`selected_case_count`、动态 `cases`、`interactions`、`adaptive_reply_requests`、`automation_stability`、`next_action`
（`poll_after_interval` / `reply_then_poll` / `finalize`）、`progress_changed`、`changes` 与 `next_interval_sec`。

### 3.2 每一关由宿主回答

装置不自动应答。`interaction-script.yaml` 记的是需求方在每一关的**立场**和该交出的材料，宿主按当时情境用自己的话说出那个意思；逐字照抄
会在关卡漂移时把后面的话提前送进前面的关卡。每一关三步：

1. 读 `adaptive_reply_requests[]`：`question` 是模型原话，`planned_intent` 是这一关按规划该表达的立场，`planned_deliver` 是该交的材料，
   `planned_phase` 是那句话的阶段前提（只在与当前阶段一致时给出），`script_cursor` 是规划走到第几条。规划里没有对应这一问时这几项为空，
   `plan_note` 写明，按 `answered` 只答所问；
2. 判断属于哪一种、说什么，用 `--reply-kind` 如实标注：

   | `--reply-kind` | 什么时候用 | 说什么 |
   |---|---|---|
   | `planned` | 模型问到了规划里这一条对应的事，阶段前提已满足 | 把 `planned_intent` 的意思用自己的话说出来；`--step <id>` 指名覆盖了哪一条，规划指针才前进 |
   | `answered` | 规划之外、需求方答得上的问题（范围、优先级、口径）；framework 的术语确认与视觉 provider 询问、模型自开 update 时问补料也属这类 | 一句需求方立场，不捎带规划里别的立场 |
   | `neutral` | 模型没有提问，只是在推进，装置照例叫了宿主 | 一句不含事实的推进（「继续」）；不替它确认材料、范围、口径，也不重放上一条的编号 |
   | `improvised` | 以上都不是 | 尽量不用；它会污染观测，原话要进交付报告 |

3. 同一回合立即再 `poll` 确认消费。

**怎么说**：需求方是在拍板，一次回话不超过一句。

- 模型给了编号选项：只回编号（「1」「A」），几组选项按组号逐组写（「T1 1，T2 2」）；回选项内容会让产物分不清那句话是它写的还是宿主给的。
- 材料关卡：模型第一次停在材料关卡，就把该 Case `supplements/` 里 `on_request` 的补料全部 `--deliver` 进收件箱，再只回表示「已放入」的编号；
  之后再问，回表示「材料就这些」的编号。人手上的材料一次交齐，不按模型点名挑着给，也不描述文件里有什么。
- 规划外的问题：一句立场，不点命令、文件、字段、关卡名，不复述它已说过的。

`awaiting_reply` 在它出现的那次唤醒内回复完：`question` 就是原话，`case_inputs_hint` 是本 Case 的公开输入清单，当轮即可作答；推到下一个周期
按协调失误记入观测记录。宿主只读本 Case 的公开输入，不读其他 Case、历史答案或提示遗漏项。意外行为与关键词只记录和理解；`stop` 与 `retry` 只响应用户
明确要求（§4.2），单个 Case 失败不停其他 Case。

```powershell
python test/scripts/run_multi_case.py reply --suite-id story-suite-20260822-140000 `
  --case <case-id> --reply-mode adaptive --reply-kind planned --step scope-do-both-in-one `
  --reason "模型问范围怎么定，对应规划里的不拆单立场" `
  --text "只做挂失，不做补卡。"
```

回话要带材料时加 `--deliver <文件名>`（取自该 Case 的 `supplements/`）：文件先落进收件箱，那句话才排进队列。

### 3.3 原话取不到时

`prompt_source` 是 `cli_text_event` 时 `question` 就是原文；是 `unavailable`（模型这一轮没发 text 事件）时，读该 Case run 目录下 `events.jsonl`
尾部的 `type: text` 事件。读的是模型对需求方说的话，观测边界不变。

### 3.4 关卡漂移：换回法，不换话术

模型少停或多停一关时，脚本后面的话与阶段对不上，落成 `interaction_phase_mismatch`。用那一关本该说的话以 adaptive 方式回，跑完再把脚本里的
`expected_turn` / `expected_phase` 按实跑顺序校准。话术保持不变，这个 Case 才观测的是同一件事。

### 3.5 heartbeat 与 watch

唤醒方式二选一：宿主工具有定时唤醒时用 heartbeat；没有时用 `watch` 在后台敲门，退出后宿主处理完再重起。

heartbeat 绑定 suite-id，每次唤醒只执行一次 `poll --wait-sec 0`：

- 按返回的 `next_interval_sec` 更新同一个 heartbeat，不创建第二个任务。poll 在全部 Case 连续两轮稳定处于需求成文登记之后时给 120 秒，
  有 `awaiting_reply`、阶段回退或状态异常时回到 15 秒。
- `next_action=reply_then_poll`：按 §3.2 当轮回复并立即再 poll；`finalize`：执行 §4.5 回灌、输出逐 Case 汇总并暂停 heartbeat。
- 命令失败时诊断并重试一次，仍失败则保持 15 秒并报告。
- 只在 suite 终态、装置或 CLI 故障、需要用户拍板时向用户说话。

`watch` 是敲门器，按间隔做零等待 poll，有 Case 要回话、有 Case 停在检查点、suite 结束或 poll 连续失败三次时退出并打印原因，每次结果存到
`output/story/<suite>/host/last-poll.json`：

```powershell
python test/scripts/run_multi_case.py watch --suite-id story-suite-20260822-140000 --interval 60
```

`watch` 不回话、不判断：宿主读结果按 §3.2 作答，答完再起一次。`watch` 没打印原因就结束了（后台任务被回收、终端被关）时直接恢复：
先零等待 poll，有要回的回完，再以 `--interval 60` 重起，并在给用户的回复里用一句话说明。

## 4. 收工与回流

### 4.1 终点：`case.yaml` 的 `end_at`

终点的真源是 `case.yaml` 的 `end_at: {kind, phase?, delivery?}`，一个 Case 一行；`cases/` 属被测输入，改它单独记一笔账。`--end-at`
（`story` / `story:submitted` / `blueprint` / `design_handoff` / `phase:<阶段>`）是命令行 override，记在 suite 记录的 `requested_end_at`，
实际终点记 `effective_end_at`，`end_at` 字段始终回显 `case.yaml` 原值。`phase` 只在 `kind: phase` 时写；`delivery` 只在 `kind: story` 时写，
Case 里必须写明 `local` 或 `submitted`，命令行的 `story` 简写取 `local`。

| kind | 到达的判据（`test/scripts/end_target.py`，只读原生对象） |
|---|---|
| `story` | 需求已登记成文，交付门 `story-build check --deliver` 通过——它只读已做过的独立审查结论，不重跑检查、不写报告；不要求 Spec/Plan 或施工单位。`delivery: submitted` 另要当前这一版已真实送审：流程契约的发布记录与已发布副本是当前 Story 与 Review，需求系统上的正文与评审记录附件逐字是这两件；装置只读，不替模型上传 |
| `blueprint` | 蓝图已准入，评审投影与这一版有效；不创建 Story、不要求施工单位 |
| `design_handoff` | 蓝图已准入，至少一个活动施工单位，且每个都被原生判为可施工；不要求施工 |
| `phase` | 在 `design_handoff` 之上，每个活动施工单位在终点及之前各阶段：冻结范围要执行的，原生完成证据身份相符、收口且质量结论 PASS，认定到达时阶段物证仍新鲜；不执行的，必需义务由原生承接证据满足（合法复用），或义务全部不适用 |

蓝图取需求流程契约里的设计关联；直接走 Framework 的 Case 在 `case.yaml` 显式写 `blueprint_id`。有一个施工单位没到，整单就没到。
`end_at` 决定驱动器的推进目标、跑哪几个 gate（需求交付门，加每个施工单位每个负责阶段的 `harness_<阶段>@<施工单位>`）。
终点到了装置自己停；没到而宿主判断本轮已到位时用 `conclude`（§4.2），逐 Case 生效。

### 4.2 何时 `conclude`

装置只报事实，收不收工由宿主判定。每次 poll 的 Case 条目里有 `closure`：

| 字段 | 说的是 |
|---|---|
| `end_at` / `target_closed` | 本轮终点；按 §4.1 的判据到没到 |
| `target_missing` | 差什么：交付门的原话、蓝图准入与投影、缺施工单位或设计判定、执行范围没冻结、某施工单位某阶段的完成证据、质量结论、物证新鲜度或承接证据 |
| `blueprint_id` / `units` | 需求关联的蓝图；逐施工单位的身份、设计判定与各负责阶段的结论（`closed` / `reused` / `not_applicable` / `not_in_scope` / `open`）及原生事实 |
| `story_registered` | 需求成文登记过没有 |
| `beyond_target_evidence` | 诊断：终点之后的阶段目录里看得到文件（`<阶段>@<施工单位>`），不认完成 |

| 看到 | 做什么 |
|---|---|
| `target_closed = true` | 装置自己停，不用 conclude |
| `target_closed = false`，模型宣告本轮已完成，且 `target_missing` 只剩宿主已判为不属本轮的项 | 判定本轮到位 → `conclude` |
| `target_closed = false`，`target_missing` 还差凭证、模型也没宣告 | 按需求方身份继续回话 |
| 拿不准 | 再 poll 一轮 |

```powershell
python test/scripts/run_multi_case.py conclude --suite-id story-suite-20260822-140000 `
  --case <case-id> --reason "需求说明已送审，本轮终点 story 已到位"
```

`conclude` 在模型这一轮结束时生效：worker 在轮与轮之间读收工请求，自己退出续话循环，门禁照跑、产物齐全。

模型在一轮里陷入循环（同一件事反复做、runlog 里自述绕不出去），或 poll 报一个 Case 长时间没有产出（`events_idle_sec` / `stalled`）时，
按故障向用户报告现象与依据，由用户决定处置：

- 重启这一个 Case：`retry --suite-id <suite> --case <case-id> --reason "<用户同意的理由>"`，走 §2.1 的干净基线链路（attempt+1），其他 Case 不动；
- 停掉整个 suite：`stop --suite-id <suite>`，逐个强杀所有活动 Case 的进程树、不跑门禁，之后照常 finalize，终态记 `stopped`。

诊断写进本轮评审意见。

### 4.3 终态、退出码与证据

退出码只表达这次运行有没有装置或 CLI 层面的故障；被测做得好不好看 `target_reached` 与 `closure.target_missing`。

| `stop_reason` / 情形 | 终态 | 退出码 | 谁的账 |
|---|---|---|---|
| `target_reached` | `finished` | 0 | 自然到达 |
| `host_concluded`，已闭环 | `finished` | 0 | 宿主收工，目标也到了 |
| `host_concluded`，未闭环 | `concluded_by_host` | 0 | 宿主判定到此为止，是有效观测（模型自认为完成而凭证不齐） |
| 自然结束而产物不齐 | `target_not_reached` | 1 | 模型没做完 |
| `cli_cannot_continue` | `cli_failed` | 1 | CLI 层失败（凭据被拒等） |
| `no_session_id` | `cli_session_lost` | 2 | adapter 回了 succeeded 却没给 session id |
| 内容审查第二次拒绝 | `content_policy_rejected` | 1 | 同配置重跑额度耗尽（§2.1） |
| 配置组全部鉴权失败 | `cli_config_exhausted` | 1 | 本 suite 无可用 CLI 配置（§2.1） |
| 用户要求 `stop`（整个 suite） | `stopped` | — | 强停，门禁未跑 |
| 装置漏跑 gate，或 story 门禁没跑成（检查进程没起来、没有自己的结论） | `harness_incomplete` | 2 | 装置的账；原因记在 `gate_diagnostics.json` 该项 `status: not_run` |
| 检查器给出不通过结论 | `gate_failed` | 1 | 被测对象的账 |
| 进程真的不在了 | `worker_lost` | — | 进程丢失 |

**本域不设时限与轮次上限**：`soft_timeout` / `hard_timeout` / `phase_hard_timeout` / `max_turns` / `reply_wait_sec` 写进配置会被
`run_case.py` 启动即拒绝。worker 停在 `awaiting_reply` 会一直等，每 5 分钟发一条 `awaiting_reply_stale` 事件、Case 条目带 `waited_sec`，
出口只有宿主回话或 `conclude`。出现 `timed_out` 说明有人把时限重新引进来了。

权威状态只来自 `state.json` 和运行事件；同仓多个会话并存时，状态归属以本会话实际执行命令的 transcript 与状态写入事件为证据。
历史清理的 `completed_with_warnings` 不是 Case 失败。典型目录：

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

**阶段闭环证据**：读取当前运行的 closure、summary、trace 与回执，按当前协议定位 verifier 报告；文件存在不等于绑定本轮或审查通过。
评价时分别记对象/版本绑定、报告结构结果和实际语义结论。报告缺失、尚未到审查时点、宿主未启用能力和业务不适用分开说明，是否允许降级
按当前已批准政策。

### 4.4 双检查点（只对配了 `after_initial: update` 的 Case）

配了这一行的 Case 第一段到目标不终止，停在检查点等宿主评完、回流，再在同一次对话里跑第二段。顺序固定（下表命令都带 `--suite-id`）：

| 步 | 动作 | 为什么在这一步 |
|---|---|---|
| 1 | Case 自己停在第一检查点（`awaiting_kind: initial_checkpoint`），模型最后那一问在 `question` 与 `pending_question` 里；等待期间 `reply` 一律被拒 | 到目标就终止只能另起 run，那是重启新会话冒充续行 |
| 2 | `checkpoint --case <id> --point initial` | 它停着、没有写入者，复制才说得清是哪一刻；需求目录、关联蓝图与需求目录外的 Story 审查报告同一刻固定，复制前后目录摘要不同则快照作废 |
| 3 | 只读评测那份快照 | 工作区马上要跑第二段 |
| 4 | `promote-checkpoint --case <id> --point initial` | 第一段回流到维护仓 `doc/features/<需求编号>`；不先回流，第一段产物就只剩快照 |
| 5 | `resume-update --case <id> --text "<case.yaml 的 update_request>"` | 只投第二段请求；交付选择在第一段的关卡上已经答过，终点真正到了才停在检查点，这里不替模型答别的。`update_inputs` 在这一步按下表自动投放，`--deliver` 只投 `supplements/` 里的补料 |
| 6 | 第二段起手在材料关卡停一次，按该 Case `interaction-script.yaml` 的 `update-material` 作答；之后 Case 停在第二检查点（`stop_reason: update_checkpoint`） | 终点以流程契约里这一轮 update 关闭为准，模型说「更新完成」不算 |
| 7 | `checkpoint --point update` → 只读后评 → `conclude` | story 门禁已在进第二检查点前跑过；第二检查点的唯一出口是 conclude，不发的话 worker 一直等，最后只能被外部停掉、终态成 `worker_lost` |
| 8 | 全部终态后 `finalize --promote` | 第二段真跑过时终态文档落到 `<需求编号>-update`，第一段那份不被覆盖；第一段没到终点就收尾的，终态用原编号 |

| `update_inputs` 的 `kind` | 投到哪 | 模拟的是 |
|---|---|---|
| `local_material` | 需求目录的收件箱 | 人手上的新版文档 |
| `system` | 需求系统里那张单（`destination` 指文件） | 上游正文或评审回稿被更新，update 取上游时取回 |
| `review_human_zone` | 评审记录里标题含 `match` 词的那条议题的人工区 | 评审人表态；找不到或不止一条就不写并记下 |

本地单没有需求系统，送审件就是工作区里的 `AR/review.md` 与 `AR/story.md`。等待窗口里只固定快照、只读评测，不向被测会话发评分、缺陷清单、
脚本路径或修法；恢复驱动后仍只扮演需求方。第一段到目标却没拿到 session 时终态是 `cli_session_lost`，不另起 run 接着跑。

### 4.5 回灌与现场保留

全部 Case 终态后执行：

```powershell
python test/scripts/run_multi_case.py finalize `
  --suite-id story-suite-20260822-140000 --promote
```

- Case 已终态且 workspace 存在就回灌；成功或失败 Case 的 `doc/features/<feature>` 都独立复制到维护仓 `doc/features/`（双检查点单的终态
  另名 `<feature>-update`），目标已存在时仅内容完全相同视为已回灌，否则保留双方并记录冲突。
- 受控源码差异逐文件回灌 demo，做三方检查：目标仍等于 suite 基线时写入，已等于该 Case 结果时记幂等完成，同时不同于两者时记冲突；
  删除只记录不执行；不因同批其他 Case 已写入源码而跳过。
- 每个 Case 生成不可变的 `observations.jsonl` 与汇总 `observation-record.md`：启动与恢复、阶段和状态变化、观测、交互、CLI/gate/基础设施错误、
  回灌结果和保留路径。
- `finalize --cleanup` 已停用并明确报错；本轮 workspace 与 suite output 保留到下一轮起跑时清理。
- finalize 前确认 demo 的阶段状态文件不存在或不属于本次 feature；否则宿主会话的 hook 会把报告写进回灌后的产物。

## 5. 离线验证

离线验证用 `test/scripts/verify.py`，从仓根执行，只选场景。并行参数、模板装配与先后顺序都写在脚本里，不手拼 pytest 或检查命令：

| 场景 | 命令 | 什么时候跑 |
|---|---|---|
| 改一处 | `python test/scripts/verify.py affected <测试文件…> [-k <关键词>]` | 改动后跑直接覆盖它的用例；子步骤收尾时把它所在功能块的几个测试文件一起给 |
| 全量 | `python test/scripts/verify.py full` | 提交或交回前一次 |
| 失效形态 | `python test/scripts/verify.py failure-modes` | 现建装好开发源的模板（与 §1.2 同一装配函数）再跑 §5.4 |
| 交回 | `python test/scripts/verify.py handback` | 交回前一次：全量 → 失效形态 → CLI 测试、compileall、validate_clis、每个 `.mjs` 的 `node --check`，依次串行 |
| Case 计划 | `python test/scripts/verify.py cases` | 改了 Case 或多 Case 编排时：全部 Case 出计划，并行数取 Case 数 |

每步的完整输出写到 `output/verify/<时刻>-<场景>/<步骤>.log`，控制台只打印每步的结论行与耗时；有一步失败退出码非 0。
全量与失效形态不要同时起两个场景：两者争用同一份共享测试状态缓存。

`test/tests/conftest.py` 给测试起的 node 进程带上 ts-node 转译缓存（系统临时目录 `story-ts-transpile-cache`，按内容取键，删了只会重新转译）；
要读原生 Framework 的用例按准备状态分小类，一个类只造一种状态：`loadscope` 按类分 worker，大类会串行拖住整轮。

- 按影响范围分层跑：改一处用 `affected`；全量与失效形态回归只在提交或交回前各跑一次（`handback` 一次跑完）；无新改动不重复刷全量，要看某条失败的细节用 `affected` 只重跑那个文件。全量用时预算与超预算的处置见 [tests/README.md](tests/README.md)「用时预算」。
- 跳过与预期失败按当前用例声明与实际输出逐项说明。这些命令不启动真实被测 CLI。
- pytest 缓存由根 `pytest.ini` 放在 `output/scratch/pytest-cache`；需要 `--basetemp` 或临时工作区时用 `output/scratch/<本次任务>/` 下的新目录。
- 串行只在排障时用，且只串行跑那一条：`python -m unittest discover test/tests`。测试隔离与慢用例的编写纪律见 [tests/README.md](tests/README.md)。

### 5.1 verifier 通道（OpenCode）

opencode 的 verifier 子代理定义物化在 `.opencode/agent/verifier.md`，报告由派它的 agent 原样写到 `summary.verifier_report`。两条命令都不启动真实 CLI：

```powershell
python -m unittest discover -s test/tests -p "test_verifier_chain_in_workspace.py"
npx ts-node scripts/check-adapter-catalog-consistency.ts --framework-root <仓根>\demo\framework   # 在 demo/framework/harness 下跑
```

第一条核工作区带没带上子代理定义与作者入口、定义是不是当前协议；第二条用 `demo/framework/harness/node_modules/ts-node`。

### 5.2 verifier smoke（真实 CLI，独立于 Story）

`test/verifier-smoke/` 用一个固定小需求跑到 spec 闭环验证 verifier 链路，不在 `cases/*` 里、不进 `--all`。工程是合成的最小 `generic` 工程，
不挂 Extension，`build` 调真正的 init 物化 `.opencode/`：

```powershell
python test/verifier-smoke/run_smoke.py build  --workspace <隔离目录> --force
python test/verifier-smoke/run_smoke.py run    --workspace <隔离目录> `
  --cli-config <config/test.yaml 里的配置 id> --evidence <隔离目录>\smoke-evidence.json
python test/verifier-smoke/run_smoke.py verify  --workspace <隔离目录>
python -m unittest discover -s test/tests -p "test_verifier_smoke.py"   # 离线判据，不启动 CLI
```

两个结论分开记：**A 链路**（`verify` 的逐项绑定检查与 receipt 闭环，脚本判）与 **B 语义**（verifier 是否真读了需求与 spec、判断是否相关，人看报告）。
结论只绑实际跑的 `cli_config_id`。现场纪律：

- `harness-runner.ts` 按自身位置解析工程根；阶段门禁由被测模型在 workspace 内自己跑，在 demo 里跑会把报告写进 demo 并误建 `doc/features/<feature>/`。
- 确认按 `confirmation-registry.yaml` 的 portable 菜单文案匹配（`fixture/replies.yaml`），没有条目命中就停等报 `unknown_question`。
- `spec.feature_path` 冲突，以及 verifier request 生成前的 Research / 术语 / track / 冻结门 BLOCKER，归 `environment_or_fixture_failed`：修夹具或环境后重跑。

### 5.3 作者起手通道

```powershell
python -m unittest discover -s test/tests -p "test_author_context_entry.py"
node doc/extensions/hooks/shared/knowledge-task.mjs --project-root <根> --feature <feature> --action <阶段> --audience author
```

第二条是消费模型动笔前跑的那一条（Framework 按 phase_bindings 调 story-knowledge）。各阶段原则页是
`doc/extensions/hooks/<phase>/author.md`，知识任务第 5 块指回它。非零退出码表示取不全：缺对象或动作报用法，激活知识读不到或原生输入缺失报对象、缺口与责任。

### 5.4 失效形态全量回归

`check_failure_modes.py` 跑 `regression/failure-modes.yaml` 的全部形态，两段缺一不可：

| 段 | 对象 | 判据 |
|---|---|---|
| 夹具自检 | `fixtures/failure-modes/<id>/{bad,good}` | 反夹具必 FAIL、正夹具必 PASS；不过即 checker 本身失效 |
| 真实目标 | 机制层源码扫描读 `extensions`（开发源）；执行器与产物层读 `--project-root` 给的模板及其中 `--feature` 指定的新产物 | `status: fixed` 的形态一条不许命中 |

`status: pending_capability` 报 SKIP；`retired` 须带 `reason` + `approved_by`。`--historical` 是观察档：对维护仓 `doc/features/` 下的需求目录与
`doc/features/archive/` 每个归档批次下的需求目录跑产物类 checker（报告用相对回流根的路径区分同编号），检出是预期结果，不参与 PASS/FAIL。

### 5.5 维护不变量的机械回归

| 不变量（AGENTS §3） | 台账形态 |
|---|---|
| 机制层零测试特征 | M02（从 Case 目录动态提取单号与业务词） |
| 两层一桥（机制层对目标仓零强依赖） | M01（写死域前缀与知识标识）、M03（架构层名）、M04（绝对路径、来源仓与外部工程路径） |
| 引用必须真实存在 | M17（查无此物的死判据） |
| 正向实现，不打补丁 | M16（死代码、静默降级、待办标记） |
| 知识不含维护信息，定位只写一处 | M18（facts 引规约编号、知识指向机制、规约带源码路径、阶段矩阵；经真实 `selfCheck`） |

维护历史混进交付面（实测数字、轮次与批次故事）还没有台账形态，提交前人工扫一次：

```powershell
rg -n '实测[^。]{0,40}[0-9]|首跑 [0-9]|批次 *[0-9]|上一轮那|F[0-9]+ (首版|实测)' extensions -g '!extensions/knowledge/**'
```

扫描面含 Markdown、提示词、注释、docstring 与合同说明，它们都会进入消费模型上下文。机械回归未命中不证明语义通用或架构合理，
仍按 AGENTS §3「机制层零测试特征」做过拟合与职责审视。

## 6. 评价

### 6.1 实跑度量

跑完一轮后，`measure_run.py` 从 `events.jsonl` 读出以下各项；它只报数，达标与否由人看着数字判断，数字不进写作命令或 PASS 条件：

```powershell
python test/scripts/measure_run.py output/story/<suite>/cases/<case>/<run>
python test/scripts/measure_run.py <同上> --json      # 需要机器读时
```

| # | 指标 | 参照目标 |
|---|---|---|
| 1 | 门禁回环时间占比 | < 15% |
| 2 | 作者读 `framework/**` + `doc/extensions/**` | ≤ 20 次/阶段 |
| 3 | 读 checker 源码 | 0 |
| 4 | 同一 check id FAIL 次数 | ≤ 2 |
| 5 | spec 阶段上下文增量 | ≤ 150K |
| 6 | verifier 扩展注入 | ≤ 15KB/阶段 |

`segments` 按段给出（双检查点单分 `initial` / `update`，普通单一段 `whole`）：`duration_min`、`model_gap_sec`、`tool_gap_sec`、`verifier_runs`、
`verifier_gap_sec`、`first_harness`、`first_story_register`、`rework_min`；等人时间只有全程数 `human_wait_sec`。各项读数口径见 `measure_run.py` 文件头。

第 3 项是调查信号：记录作者为何读 checker、读后做了什么，与产物、性能、Knowledge 应用及跨 Case 重复情况一起判断（AGENTS §1）。

### 6.2 从证据还原行为

评价在 finalize 之后，以保留的 events、runlog、版本对应的输入/产物和报告为依据，不改原件补证据。一次工具事件含多条命令时读完整入参，
读取命令、offset/limit、管道截断和实际返回一起核对。

| 要判断什么 | 可支持的证据 | 替代不了它的 |
|---|---|---|
| 机制能生成要求 | 源码、离线输出或装配结果 | 运行时已送达 |
| 要求实际送达 | 当前工具完整输入、返回、读取范围与分页/截断 | 文件存在、hook 返回过、读取次数 |
| 执行了相关工作 | 实际编辑、调用、比较对象和产物变化 | 「已认真检查」等自述，或只列章名 |
| 内容正确 | 原始义务、已确认决策与成品对照 | 门禁绿、来源 ID 齐、与模板一致 |
| 审查有效 | 实际缺陷与报告发现对应，对象版本一致 | 报告结构 PASS、来源列表 |

先找最早偏离点，再区分输入/职责错误、执行偏离、语义判断、机械误判和外部故障；报告分别写观察事实、解释假设与待验证项。

### 6.3 审查故障诊断

只在真实产物与审查结论明显不符、且 §6.2 不足以定位原因时使用；调用模型的步骤须用户授权。先保留原稿，在独立临时副本上复现具体问题：

```powershell
python test/scripts/make_narrative_variants.py --list
python test/scripts/make_narrative_variants.py --out <独立临时目录>
python test/scripts/run_review_qualification.py --config <当前配置> --out <独立输出目录>   # 调用模型，须本次诊断授权
```

变体与预期以当前 index 为准；保留输入改动、配置、输出原文与发现位置。结果只说明这次诊断现象，正式效果仍按 §6.4 评价。

### 6.4 Story init 三轴评分

每次获准运行真实 Story init 后评分。评分对象是该次运行的完整结果与过程；评价范围来自本轮已确认目标及需要保持的原有能力（AGENTS §4）。

#### 评分项

| 评分项 | 评价对象 | 主要证据 |
|---|---|---|
| 产物结果 | `story.md + review.md` 作为一组评审载体 | 已确认范围与原始材料、最终 decisions、金样的形似/神似、verifier 与人工审阅 |
| 性能 | 从 Story init 开始到可交付结果的完整过程 | 总墙钟、作者/脚本/verifier/返修耗时、循环次数、上下文增长、规则与 checker 读取；人工等待和外部故障单列 |
| Knowledge 应用 | 适用知识在本次需求中的消费结果 | 看到、理解、应用、传递四段证据；用确有适用知识的 Case |

三项各 100 分，不加权、不互相补偿：`90–100` 达到目标；`70–89` 未达目标，记录主要缺口继续优化；`<70` 本次测试失败，回对应所有者定位。
代表性测试三项均达到 90 且经用户确认，才能宣布达到评分目标；已结束轮次保持其用户裁定。

#### 评分锚

- **产物结果**：高分表示 Story/Review 在范围内完整、正确、无编造，详略符合实际需求，决策已定/未定清楚，图文与章节便于评审；
  有明显遗漏、详略失衡或 Review 决策负担时落入 70–89；关键内容大量缺失、矛盾、编造或无法评审时低于 70。字数、表格数、图片数不直接计分。
- **性能**：高分表示主要工作时间接近期望（半小时是期望值）、检查与返修聚焦、上下文和源码读取与任务规模相称；有明显重复检查、无效读取、
  上下文膨胀或远离期望耗时时落入 70–89；多小时反复撞门、错误不收敛或主要时间耗在学习隐藏规则上时低于 70。人工等待与外部故障如实展示、不归责。
- **Knowledge 应用**：高分要求适用知识在正确时机进入正确执行体、形成判断、改变产物并被下游取得；链路成立但个别判断弱时落入 70–89；
  没被看到、只回显名称、关键适用项漏判或传不到下游时低于 70。

#### 证据与用户确认

脚本只采集时间、轮次、上下文、文件和事件等原始事实；verifier 提供语义证据，不拥有评分权；维护者按证据向用户呈现三项建议分与扣分原因，
用户确认或调整后才是最终分数。每次测试在该 run 的 `evaluation/scorecard.md` 记录评分协议版本（`story-init-score@1`）、Case、宿主/模型配置、
产物版本、建议分、扣分证据、用户确认分与确认时间，确认后同步到当前轮次的评审报告。

#### 长期基线与跨轮比较

用户确认的评分量表、代表性结果及其适用 Case/宿主配置写入 `test/baselines/story-init-quality.md`（目前尚未建立，首次晋升时建立），作为后续演进
基线；修改量表、阈值或基线样本先向用户说明并取得确认。

比较前核对机制版本、宿主/模型配置、原材料、确认范围、交互与干预、结束阶段及产物版本；相同条件的独立重复才提供稳定性证据，
少量重复通过不等于高成功率，同时看最差一轮与关键缺陷。
每轮并列记录目标变化、非重点能力变化、成本变化与证据缺口，重点核「优化 A 是否损害 B」。历史检索先查 output 中的 artifact 与保留记录，
再查 `doc/features/archive/` 的归档批次；维护仓 `doc/features` 下的需求目录只是最近一次回流，找不到的证据标不可比。被长期评价引用的材料要有明确保留位置，
下一轮起跑会清理的 suite 目录不能当档案。

#### 金样

金样入口为 [golden/README.md](golden/README.md)。使用前核用户认可的用途、版本与尚未确定的业务口径，区分效果对照、已冻结业务结论和已批准的
机器否决锚。对比金样看需求是否完整准确、关系是否清楚、形式是否适合、责任与交付是否可判断，不要求同名小节、同字数或同句式；
正文里有依据的新增解释不因模板没列而判错。金样与维护分析留在评价域，不进入被测 Case。
