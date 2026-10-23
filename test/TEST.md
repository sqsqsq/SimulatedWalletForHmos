# Story 并行 CLI 测试指南

本指南是 Story 测试域的操作协议。维护约束见根 [AGENTS.md](../AGENTS.md)，规则的事故来源与演进见 [EVOLUTION.md](EVOLUTION.md)。
这些维护文件不进入被测模型上下文。

## 按当前任务读取

| 任务 | 读取 |
|---|---|
| 启动、恢复或驱动真实 Story CLI | §0–§4 完整读；结束后按 §6 评价 |
| 维护脚本或做离线验证 | §5 及本次涉及的运行分支 |
| 评估已有测试、比较历史或对照金样 | §4.3 证据、§6 |
| 制定/修改维护方案、开工核对、实现或版本评审 | 先读§6.5、全量评价标准及本版评价标准变更；按条目取得原件，再核具体实现/运行证据 |
| 用户级维护 Skill 的 doctor / review 接入 | §6.5 的项目接入与对象分流；自检只读，效果评审再读§4.3、§6.2—§6.4及金样入口 |
| 定位 verifier 链路故障 | §5.1；真实 smoke 另按 §5.2 与 §0 的授权边界 |
| 排查真实稿件与审查结论不符 | §6.2 还原证据，§6.3 核审查效果 |
| 人手试用 `/story` | §1.3 |
| 决定测试现场、运行记录、维护证据放哪 | §0.4 |
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
模型参与的验证（审查是否判对、作者是否做对、收尾是否被执行等）统一在正式 Case 里取得；维护者不另起样本诊断，也不用自己的会话或子代理代跑。

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

### 0.4 东西放在哪

本节是测试现场、回流产物与 `output/` 分工的唯一规则；其它章节与根 AGENTS 只引用这里。

| 位置 | 放什么 | 谁写 | 清理 |
|---|---|---|---|
| `%TEMP%/sw-story/<名>/` | 可丢弃的测试现场：每轮 suite 的模板与 Case 工作区、§5 现建的离线模板 | 测试装置 | 每次起跑先清掉其中全部无活动的子目录（§1.2），活动的保留并停下 |
| `%TEMP%/sw-sys/<名>-<根摘要>/` | 正式 Case 的需求系统副本 | 测试装置 | 随它的 sw-story 工作区一起清 |
| `doc/features/` | 测试完回流的需求产物，上一轮的先归档到 `doc/features/archive/`（§1.2、§4.5） | finalize / 检查点 | 不入库，按回流规则覆盖与归档 |
| `output/story/` | **CLI 运行记录**：每轮 suite `story-suite-<时刻>/`（`suite.json`、`cases/<case>/<run>/` 事件流与 `cli-runtime/`、usage 快照、原生会话、回流清单）；不属于 suite 的单次真实 CLI 运行（启动核验、看图冒烟、verifier smoke）一次一目录 `<用途>-<日期>[-序号]/`，属于某轮 suite 的放进那一轮的子目录 | 测试装置；手工跑真实 CLI 时按下面的约定 | **永不清理**：任何脚本都不删；同一轮 finalize 只重写本轮派生的快照 |
| `output/evidence/` | **维护过程证据**：评审复验、实施交回引用的重放、探针、计量、截图与原件副本；一题一目录 `<版本>-<主题>-<日期>/`，复现它的驱动脚本放该目录 `scripts/` | 维护者 | 不自动清理；方案、评审与交回按路径引用 |
| `output/scratch/` | **临时**：一次性脚本、pytest 缓存与 basetemp、离线模板的装配记录 `offline-<时刻>/`、临时工作区 | 维护者、pytest、§5 | 不作证据引用，可以随时删；交回要引用的脚本先复制进 `output/evidence/<题>/scripts/` |
| `output/cli-tests/` | 中央 runtime 同步来的单测（`test/tools/cli/tests`）的临时根 | runtime 单测 | 可以随时删 |

手工跑真实 CLI 时把运行记录放进 `output/story/`：

- `python -m tools.cli ...`、`tools.cli.scripts.cli_runtime`、`smoke_test` 一律带 `--runtime-root output/story/<用途>-<日期>/cli-runtime`。
  不带时，中央 runtime 默认写到 `output/cli/`；那里出现运行就是漏带了参数，挪进 `output/story/` 对应目录。
- verifier smoke（§5.2）的 `--workspace` 与 `--evidence` 给 `output/story/<用途>-<日期>/` 下的路径：
  这个入口把 runtime 记录写进这个目录（`.smoke-cli/`）。

`output/` 整体不入库。2026-10-21 按本节做过一次迁移：维护证据从 `output/story/` 迁到 `output/evidence/`，文档引用已按新路径改写。
旧路径与新路径的对照在 `output/evidence/MIGRATION-20261021.json`。

## 1. 准备

### 1.1 选 Case

宿主完整读过 §0–§4 后，用户输入「开始测试」即进入编排。每次从当前 `cases/*/case.yaml` 动态读取可用 Case，生成编号多选项并另列
「全部当前 Case」，允许单选、多选或全选。确认前复述实际 Case、feature、目标阶段、隔离 workspace 和回流范围；确认之前只执行 `plan`
等只读检查。本轮要改终点时改 `case.yaml` 的 `end_phase`；`--end-phase` 只作一次性覆盖（§4.1）。

### 1.2 起跑前的固定顺序

0. **实例前置自检**（缺一不起跑）：`framework.config.json` 配了 `paths.ui_kit_target_dir` 且该目录已物化 UI kit 组件，否则跑到 coding 的
   Case 都会被 UI kit 门禁拦在「目标目录无法解析」上；demo 的 `framework/harness/state/` 下没有属于别人的阶段状态（有则先弄清归属，
   再决定是否 clear-state）；demo 是发布基线：顶层没有维护目录（`test`、`tools`、`output`、`scratch`、`.bak`、`.git`）、没有 `doc/features`，
   git 查询成功且非忽略改动为空。
1. 创建本轮 `output/story/<suite-id>/` 控制目录。
2. 枚举本机临时根 `%TEMP%/sw-story/` 下的全部旧现场（旧 Case 工作区、离线模板，不论名字）；`output/story/<名>/suite.json` 在的按它核终态。
3. 整体预检终态、PID、lease、路径边界与链接；没有 suite.json 的核进程清单里没有引用它的命令。
4. 全部安全后删除这些临时现场，以及由同一工作区根算出的需求系统副本（`sw-sys/<名>-<根摘要>`），写入 `previous-run-cleanup.json`；`output/` 一概不碰（§0.4）。删除与剩余枚举走 Windows 长路径前缀（深层报告路径常超过
   260 字符），归属、进程与证据仍按原始路径。个别目录删除失败时逐个记录 `retained_cleanup_warning` 与残留路径，其它可删的照删，
   下一轮重试，本轮照常继续。
5. 将维护仓 `doc/features/` 下的需求目录（上一轮回流的需求产物）归档到 `doc/features/archive/Story-Features-<时间戳>/`，本轮结束不恢复；
   `archive` 自身不搬，意外出现的文件留在原处并记入 `feature-migration.json`。`archive` 是保留名，需求编号与它同名的 Case 在读取时即被拒绝。
   单个 Case 新链起跑时，工作区里同名的旧产物存进该次运行输出目录的 `feature-history/`。
6. 创建模板及各 Case workspace，再顺序启动 CLI。

活动 PID、有效 lease、路径越界、链接风险或无法可靠枚举进程时，保留现场并在第 5 步之前停止。
`sw-story/` 只放可丢弃的临时现场，要长期保留的东西不放在那里。

模板按固定顺序装配：核 demo（结构、没有 `doc/features`、git 干净、记下提交）→ 复制 demo（排除 `doc/features`、Framework 活动状态、
`oh_modules`、`build`、`.hvigor`、`__pycache__` 等运行态，业务模块自己的单测目录照常带上）→ 把根 `extensions/` 的当前开发源（含未提交改动）
装进模板的 `doc/extensions/`、写入口与扩展段 → 核模板与开发源逐字节同源 → 再核 demo 提交与干净状态未变。任一步不成立，模板作废、
不建 Case、不起跑，修好后重新装配。各 Case 工作区从模板复制，
再放入该 Case 的输入；启动前检查路径边界与软链接，并在 `workspace-boundary.json` 记录 demo 提交、`copied`、`excluded`、安装结果和各 Case 的
`case_seeded`。每次启动 Case 前，按这次选中的 CLI 用 Framework 的 `check-personal-setup --ensure --select-adapter <CLI 名>` 写好这个隔离工程的
个人 adapter（只在 CLI 与已物化的同名 adapter 对得上时写，DevEco 等本地配置保留；对不上记 `unmapped` 不猜），结果记在 `adapter_seed`，
被测模型不再为个人设置停下来问。随后在 Case 根 `git init` 并按工程自己的忽略规则提交一次起跑基线，`rev-parse --show-toplevel` 必须
正好是这个 Case 根，被测工程不再继承外层目录所在的仓（临时目录可能落在用户配置仓里）；提交只用本次命令的测试身份，不配 remote。
根、初始 HEAD、外层原本会认的仓根和被忽略的关键文件记在 `git_boundary`（`doc/features/` 被工程规则忽略，Case 输入如实列为未跟踪）。
这个 HEAD 只代表隔离基线，维护源身份仍是 demo 提交与 Extension 指纹。续跑只核现存身份不重新提交；建不起来就不起跑。
边界检查只放行这个根 `.git` 目录，其它位置的 `.git` 以及根下的 `.git` 文件或链接照拒。

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

正式测试统一使用 `test/scripts/run_multi_case.py`，只跑一个 Case 也一样，不直接运行 `run_case.py`。以下都在非沙箱环境执行（§0.2）：

```powershell
python test/scripts/run_multi_case.py plan --all --jobs <实际Case数>
python test/scripts/run_multi_case.py start --all --jobs <实际Case数> `
  --suite-id story-suite-20260822-140000 --authorize-non-sandbox
python test/scripts/run_multi_case.py poll --suite-id story-suite-20260822-140000 --wait-sec 0
```

`plan` 只读确认选中的 Case、feature、目标阶段；`start` 起跑并返回 `next_action=poll_after_interval`、`next_interval_sec=15`。宿主随即创建绑定
suite-id 的 heartbeat（§3.5），启动回合可以结束，之后由定时唤醒驱动。`status` 只做只读诊断：不消费事件、不回复、不计观测，不能替代 `poll`；它的 `runs` 给出每个 Case 当前运行目录，以及每一轮 CLI 会话的回合、runtime 目录、session 与状态（由 `live.jsonl` 的 `cli_run_started` 对上 `cli-runtime/<id>/run.json`，对不上如实标出）。不给 `--suite-id` 时套件名是 `story-suite-YYYYMMDD-HHMMSS`，同秒已有就加两位递增后缀。

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

配置组里有 dsh 时，`start` 在 suite 根写一份 `cli-registry.json`：只含 dsh 一项，启动与续跑都在 `--profile` 后插入
`--patch {cwd}/.dsh/framework-verifier.patch.yml`，各 Case 的 cwd 仍是自己的工程，其余宿主照用中央 `tools/cli/config/clis.json`。
demo 没物化这层配置时 `start` 在装配后、任何 Case 起跑前停下。

## 3. 观察与回复

### 3.1 一次 poll

一次 `poll --wait-sec 0` 是完整事务：读取 suite 全部 Case，并行消费所有非终态 Case 的新事件、模型输出、阶段和状态，把每个真实
`awaiting_reply` 连同「这一关按规划本该表达什么」交给宿主，最后统一计算稳定状态。poll 自身不等待，等待只来自定时器。

阶段不按模型回复文本猜：从 Case workspace 的结构化证据校正，feature 匹配的 `framework/harness/state/.current-phase.json` 为首选，阶段目录中
非 `reports/` 产物为后备。`current_phase` 是当前阶段，`highest_phase_reached` 是本轮到过的最高阶段、不回退（`last_phase` 与 `current_phase` 同值），
首次到达 Spec 时写入 `spec_entered_at`。

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

- 按返回的 `next_interval_sec` 更新同一个 heartbeat，不创建第二个任务。poll 在全部 Case 连续两轮稳定处于 Spec 或之后时给 120 秒，
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

### 4.1 终点：`case.yaml` 的 `end_phase`

终点的真源是 `case.yaml` 的 `end_phase`，一个 Case 一行；`cases/` 属被测输入，改它单独记一笔账。`--end-phase` 是命令行 override，
记在 suite 记录的 `requested_end_phase` 与 `effective_phase_scope`，而 `end_phase` 字段始终回显 `case.yaml` 原值。

`end_phase` 决定驱动器的推进目标、跑哪几个 gate、`closure.target_phase` 的比对基准。目标阶段闭环时自动 Case 由装置自己停；没闭环而宿主判断本轮
已到位时用 `conclude`（§4.2），逐 Case 生效。

交互 Case（`interactive: true`）目标闭环后不立即终止，停在第一检查点（`awaiting_kind: initial_checkpoint`），模型最后那一问在 `pending_question`：
它是本段的交付选择（系统单交付门问「归档送审 / 进入 plan」）时，按该 Case 公开任务与 `interaction-script.yaml` 的立场 `reply`，模型做完被授权的动作
后再停一次；本段没有待办或已做完，按 §4.2 `conclude`，终态 `finished`。是否归档只看公开任务、交互规划与真实人答，系统单不因到了 spec 就算授权上传；
用户仍在选择时不提前收工为已送审。没配 `after_initial: update` 的 Case 在这里没有第二段，`resume-update` 被拒、不投 update 输入；配了的按 §4.4。
到目标却没拿到 session 时本段续不了，终态 `cli_session_lost`，不报完成、不另起 run。

### 4.2 何时 `conclude`

装置只报事实，收不收工由宿主判定。每次 poll 的 Case 条目里有 `closure`：

| 字段 | 说的是 |
|---|---|
| `target_phase` / `target_closed` | 本轮目标阶段；它的四件凭证齐没齐 |
| `target_missing` | 差哪几件（`trace.json` / `summary.json` / 完成回执 / verifier 报告） |
| `artifacts_ready` | spec.md、AR/story.md、AR/review.md 三件在不在 |
| `next_unclosed_phase` | 目标之前第一个还没闭环的阶段 |
| `beyond_target_evidence` | 目标之后的阶段有没有真实产物（模型真建了下一阶段产物才非空） |

| 看到 | 做什么 |
|---|---|
| `target_closed = true` | 自动 Case 装置自己停；交互 Case 停在第一检查点，按 §4.1 答完本段交付选择或无待办后 conclude |
| `target_closed = false`，模型宣告「进入下一阶段 / 本阶段已完成」，且 `target_phase` 就是当前阶段 | 判定本轮到位 → `conclude` |
| `target_closed = false`，`target_missing` 还差凭证、模型也没宣告 | 按需求方身份继续回话 |
| 拿不准 | 再 poll 一轮 |

```powershell
python test/scripts/run_multi_case.py conclude --suite-id story-suite-20260822-140000 `
  --case <case-id> --reason "模型宣告进入 plan，本轮目标 spec 已到位"
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

story 门禁按产品的阶段顺序跑：先派发 `pre_phase` 的视图钩子把 story 放回正式形态（Mermaid 按源、阅读槽置空），再跑 spec 门禁——
本地阅读图展开时直接读，会读到与登记不同的那一份。`gate_diagnostics.json` 里四种情形分开记：没到达的阶段 `skipped`、检查没跑成 `not_run`、
已闭环只读复核 `pass`（`source: existing_summary`）、harness 自己的结论；完整输出在对应的 `gate_*.log`。

**本域不设时限与轮次上限**：`soft_timeout` / `hard_timeout` / `phase_hard_timeout` / `max_turns` / `reply_wait_sec` 写进配置会被
`run_case.py` 启动即拒绝。worker 停在 `awaiting_reply` 会一直等，每 5 分钟发一条 `awaiting_reply_stale` 事件、Case 条目带 `waited_sec`，
出口只有宿主回话或 `conclude`。出现 `timed_out` 说明有人把时限重新引进来了。

权威状态只来自 `state.json` 和运行事件；同仓多个会话并存时，状态归属以本会话实际执行命令的 transcript 与状态写入事件为证据。
历史清理的 `completed_with_warnings` 不是 Case 失败。典型目录：

```text
output/story/<suite-id>/
├─ suite.json
├─ cli-registry.json            # 配置组有 dsh 时才有（§2.1）
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
      ├─ cli-runtime/<runtime-id>/{request.json,run.json,raw.jsonl,events.jsonl}
      ├─ usage/<point>/usage.json   # 该运行工作区全局 doc/usage.json 的原字节快照，point 为 initial / update / final
      ├─ native-sessions/<session-id>/  # finalize 时按 run.json 的 dsh session_id 复制的原生会话原件与子会话（manifest.json 记来源与摘要）
      └─ artifact/
```

**阶段闭环证据**：读取当前运行的 closure、summary、trace 与回执，按当前协议定位 verifier 报告；文件存在不等于绑定本轮或审查通过。
评价时分别记对象/版本绑定、报告结构结果和实际语义结论。报告缺失、尚未到审查时点、宿主未启用能力和业务不适用分开说明，是否允许降级
按当前已批准政策。

### 4.4 双检查点（只对配了 `after_initial: update` 的 Case）

配了这一行的 Case 第一段到目标不终止，停在检查点等宿主评完、回流，再在同一次对话里跑第二段。顺序固定（下表命令都带 `--suite-id`）：

| 步 | 动作 | 为什么在这一步 |
|---|---|---|
| 1 | Case 自己停在第一检查点（`awaiting_kind: initial_checkpoint`），模型最后那一问在 `question` 与 `pending_question` 里 | 到目标就终止只能另起 run，那是重启新会话冒充续行 |
| 1a | 那一问是第一段里的业务动作（系统单交付门问「归档送审 / 进入 plan」）时，按 `interaction-script.yaml` 的立场用 `reply` 回答；模型在第一段里把它做完（归档以核心 archive 的回执、读回与本地登记为准）后再停到第一检查点。已固定的快照随之作废留证（`initial.superseded-*`），从第 2 步重来 | 归档是第一段的终点动作，和第二段的投料不合成一轮；本地单没有归档，不为凑覆盖调对接层 |
| 2 | `checkpoint --case <id> --point initial` | 它停着、没有写入者，复制才说得清是哪一刻；复制前后目录摘要不同则快照作废 |
| 3 | 只读评测那份快照 | 工作区马上要跑第二段 |
| 4 | `promote-checkpoint --case <id> --point initial` | 第一段回流到维护仓 `doc/features/<需求编号>`；不先回流，第一段产物就只剩快照 |
| 5 | `resume-update --case <id> --text "<case.yaml 的 update_request>"`，不传 `--answer` | 只投第二段的业务请求；第一段回流之后 `reply` 被拒，不再在第一段里继续。`update_inputs` 在这一步按下表自动投放，`--deliver` 只投 `supplements/` 里的补料 |
| 6 | 第二段起手在材料关卡停一次，按该 Case `interaction-script.yaml` 的 `update-material` 作答；之后 Case 停在第二检查点（`stop_reason: update_checkpoint`） | 终点以流程契约里这一轮 update 关闭为准，模型说「更新完成」不算 |
| 7 | `checkpoint --point update` → 只读后评 → `conclude` | story 门禁已在进第二检查点前跑过；第二检查点的唯一出口是 conclude，不发的话 worker 一直等，最后只能被外部停掉、终态成 `worker_lost` |
| 8 | 全部终态后 `finalize --promote` | 实际续跑过第二段，终态文档落到 `<需求编号>-update`，第一段那份不被覆盖；只跑了第一段则回原编号，`promotion-manifest.json` 的 `segment` / `partial` 说明是哪一段、走没走到检查点 |

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

- Case 已终态且 workspace 存在就回灌；成功或失败 Case 的 `doc/features/<feature>` 都独立复制到维护仓 `doc/features/`（实际续跑过第二段的
  终态另名 `<feature>-update`，回流身份按实际走到的段落定，不按计划的 `after_initial` 推断），目标已存在时仅内容完全相同视为已回灌，否则保留双方并记录冲突。检查点与 finalize 各把工作区全局 `doc/usage.json` 原字节留到该运行的 `usage/<point>/`，缺失记 missing、已固定的不覆盖。finalize 还把 dsh 原生会话原件（父会话按记录的 session_id，子会话按父会话登记的 childId）复制到 `native-sessions/`。缺失、多候选、复制失败记在 manifest 的 `not_captured`，解不出、头部 id/cwd 或 parentSession 不符记在该会话的 `problems`（父会话头部不符时不采它登记的子会话），任一项都让 `status` 为 `incomplete`：拷到文件不等于取得本次可信原件，已复制的原字节照留；dsh 的 JSON 流会截断长字符串，事件里的 `source_truncated` 标出哪些记录不完整，原样核对以会话原件为准。
- 受控源码差异逐文件回灌 demo，做三方检查：目标仍等于 suite 基线时写入，已等于该 Case 结果时记幂等完成，同时不同于两者时记冲突；
  删除只记录不执行；不因同批其他 Case 已写入源码而跳过。
- 每个 Case 生成不可变的 `observations.jsonl` 与汇总 `observation-record.md`：启动与恢复、阶段和状态变化、观测、交互、CLI/gate/基础设施错误、
  回灌结果和保留路径。
- `finalize --cleanup` 已停用并明确报错；本轮 workspace 保留到下一轮起跑时清理，suite 的运行记录留在 `output/story/`，永不清理（§0.4）。
- finalize 前确认 demo 的阶段状态文件不存在或不属于本次 feature；否则宿主会话的 hook 会把报告写进回灌后的产物。

## 5. 离线验证

命令从仓根执行，并行参数照抄不删（`-n auto --dist loadscope`、`--jobs`、`-j`；`--dist loadscope` 让同一个类的用例共用夹具、不互相踩）：

```powershell
python -m pytest test/tests -n auto --dist loadscope
python -m pytest test/tools/cli -n auto --dist loadscope
python -m compileall -q -j 0 tools/cli test/scripts
python -m tools.cli.scripts.validate_clis
python test/scripts/run_multi_case.py plan --all --jobs <实际Case数>
python test/scripts/check_failure_modes.py --project-root <装好开发源的模板>
node --check <每个 extensions 下的 .mjs>      # 彼此无依赖，可同时起
```

`--project-root` 给装好开发源的模板：用最近一次 `start` 的 `%TEMP%/sw-story/<suite-id>/workspace-template`，或不起 CLI、按 §1.2 同一装配顺序
现建一份（`<id>` 每次取新值，打印的是模板路径）：

```powershell
$id = "offline-" + (Get-Date -Format yyyyMMdd-HHmmss)
python -c @"
import sys, pathlib
sys.path.insert(0, 'test/scripts')
import run_multi_case as m
d = pathlib.Path('output/scratch/$id'); d.mkdir(parents=True)
print(m.create_workspace_template(d, '$id')[0])
"@
```

- 相关修改先跑有区分力的用例（`-k <关键词>`，看慢项加 `-q --durations 10`），通过后在完整需求收口跑必要全量；无新改动不重复刷全量。
- 跳过与预期失败按当前用例声明与实际输出逐项说明。这些命令不启动真实被测 CLI。
- 运行证据的位置由 `test_run_measurement.py::ProcessArtifactsEnterTheIndex` 核：`doc/spec`、`doc/plan` 下的截图、日志、事件流、压缩包按运行证据报：CLI 运行记录放 `output/story/`，维护过程证据放 `output/evidence/`（§0.4）。两类图是评价参照而不是运行证据：待审定金样候选里被该 Case story 引用的 `ux-reference` 图；已确认的分析归档 `doc/spec/1.9.9/04-稳定性与性能分析/data/golden/`（性质由其 MANIFEST 声明）里被所属对象 story 图片或 spec Visual Handoff 实际引用的 PNG。归档里未引用、映射到别的对象、缺 MANIFEST 的图与其它后缀照常报，断开的引用逐条报出。
- pytest 缓存由根 `pytest.ini` 放在 `output/scratch/pytest-cache`；需要 `--basetemp` 或临时工作区时用 `output/scratch/<本次任务>/` 下的新目录（§0.4）。
- 串行只在排障时用，且只串行跑那一条：`python -m unittest discover test/tests`。测试隔离与慢用例的编写纪律见 [tests/README.md](tests/README.md)。

### 5.1 verifier 通道（OpenCode / dsh）

opencode 的 verifier 子代理定义物化在 `.opencode/agent/verifier.md`；dsh 的是 `.dsh/framework-verifier.patch.yml` 里名为 `verifier` 的只读工具实例，
启动时经 `--patch` 装载（§2.1）。作者读到的调用指引统一指向宿主登记的专用 verifier 角色，通用研究/开发子 agent 不顶替（[维护操作§2](../doc/release/维护操作.md#2-framework-本地定制)）。
报告由派它的 agent 原样写到 `summary.verifier_report`。两条命令都不启动真实 CLI：

```powershell
python -m unittest discover -s test/tests -p "test_verifier_chain_in_workspace.py"
npx ts-node scripts/check-adapter-catalog-consistency.ts --framework-root <仓根>\demo\framework   # 在 demo/framework/harness 下跑
```

第一条核工作区带没带上子代理定义与作者入口、定义是不是当前协议、调用指引是否都指向专用角色；第二条用 `demo/framework/harness/node_modules/ts-node`。

### 5.2 verifier smoke（真实 CLI，独立于 Story）

`test/verifier-smoke/` 用一个固定小需求跑到 spec 闭环验证 verifier 链路，不在 `cases/*` 里、不进 `--all`。工程是合成的最小 `generic` 工程，
不挂 Extension，`build` 调真正的 init 物化 `.opencode/`：

```powershell
python test/verifier-smoke/run_smoke.py build  --workspace output/story/verifier-smoke-<日期>/workspace --force
python test/verifier-smoke/run_smoke.py run    --workspace output/story/verifier-smoke-<日期>/workspace `
  --cli-config <config/test.yaml 里的配置 id> --evidence output/story/verifier-smoke-<日期>/smoke-evidence.json
python test/verifier-smoke/run_smoke.py verify  --workspace output/story/verifier-smoke-<日期>/workspace
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
node doc/extensions/hooks/spec/author.mjs --feature <feature>    # 在装好开发源的模板根下跑（demo 里是发布版）
```

第二条是消费模型动笔前跑的那一条。各阶段原则页是 `doc/extensions/hooks/<phase>/author.md`，作者按 SKILL、入口文件扩展段与
`story_flow.py status` 的下一步去取。非零退出码表示取不全：缺 `--feature` 退 2，章节合同读不到退 1。

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
`verifier_gap_sec`、`delegations_unresolved`、`first_harness`、`first_story_register`、`rework_min`；等人时间只有全程数 `human_wait_sec`。各项读数口径见 `measure_run.py` 文件头。

计数按调用：同一 run 里同一调用编号的开始与结果事件归并成一次，名称与入参取开始，输出与终态取结果。
- shell 工具认 bash / pwsh / shell / shell_command。
- verifier 只认专用 `verifier` 工具与 `subagent_type=verifier` 的 task；其它委派记进 `delegations_unresolved`，是不是审查由人判断。
- 首次门禁、登记与返工只看有结果的调用，命令报错也算没过；读一份旧门禁报告不是一轮门禁。
- 归并不了或被宿主输出截断的条目（只有开始、只有结果、同键冲突、跨检查点、`source_truncated`）列在 `incomplete_tool_events`，此时计数只是已观察到的次数；被截断的门禁结果不出结论。
- `context_growth` 是首末两次请求的 context_total 读数之差，不是单阶段净上下文。
- `*_gap_sec` 仍是事件间隔估计；并发调用相互重叠，不能相加成墙钟。

旧运行要按新口径看，在评审证据目录另存重投影与重测结果，不改原运行记录。

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

先判结果缺陷，再找最早偏离点；归因方法按用户级维护review，报告区分机制缺失/错误或未送达、实现偏离、输入/装置/环境故障、合法变体、支持模型波动的证据及原因未知。机制存在或一次成功不证明此次送达，模型波动也不使错误产物变正确。

历史反复差距关联原报告及原件，核版本、输入、人答、宿主/模型、干预和终点的可比性，说明影响、已核事实、未排除解释及下一责任。不可比或证据缺失保留未知，不按少量样本计算稳定概率；反复影响目标须报告可靠性差距，不能长期用不确定性豁免。

风险接续写当前评审和获准测试安排：要覆盖的差距/合法变体、既有独审与恢复是否有效、需观察的复现/纠正/最终影响/成本，以及继续观察、关闭风险或转机制整改的证据条件。未覆盖风险保留，不自动追加轮数或重跑到绿，不向Case注入金样答案。机制调整须有缺口或合理收益证据，按职责比较最小修法；运行结果和发布/评分仍按各自权限。

### 6.3 审查效果从正式运行取证

审查判没判对，只从正式 Case 取证：按原生事件核实际调用的工具与子会话、请求对象和原报告（§4.3），再对照产物与原件逐处核——
真实问题有没有点中、合法写法有没有被拒、错误建议有没有被采纳扩散。作者这次没写错的地方，看不出审查能否拦住，如实记未覆盖，
不另造样本补测。

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
下一轮起跑会清理的 `sw-story/` 工作区不能当档案；运行记录看 `output/story/`，维护证据看 `output/evidence/`（§0.4）。

#### 金样

金样入口为 [golden/README.md](golden/README.md)。使用前核用户认可的用途、版本与尚未确定的业务口径，区分效果对照与已冻结业务结论；
金样不作判据的机器否决锚，判据对错按真实依据与中性正反例判。对比金样看需求是否完整准确、关系是否清楚、形式是否适合、责任与交付是否可判断，不要求同名小节、同字数或同句式；
正文里有依据的新增解释不因模板没列而判错。金样与维护分析留在评价域，不进入被测 Case。
当前正本是 `golden/auto-topup/`（止于 Spec）与 `golden/car-key-sharing/`（止于 Plan），只在这一处维护；文件身份、引用与图源由 `test_golden_sample.py` 核，第二份副本由 `test_run_measurement.py` 核。

### 6.5 维护标准与评审

目标依据由用户有效决定及需求正本维护；[全量评价标准](regression/extension-acceptance.md)维护当前Extension能力的效果与判法。每版在`doc/spec/<版本>/评价标准变更.md`记录增量、采用修订、保持集合和核对结果。标准正文只保留一份；历史正文用Git或当次固定文本保存，历史报告保持当时结论。

#### 用户级维护 Skill 的项目接入

`maintenance-designer review` 先核下方对象分流及其材料，不把本仓评审缩成代码差异检查。设计者和执行者的 `doctor` 只读检查根 AGENTS、对应任务的 Spec/Plan 与本版标准变更、全量标准修订、§5验证入口及本节证据引用是否齐备且一致；任务版本未给出时列任务级待取得，不猜版本或判全环境损坏。已有任务原目录可用，不要求迁移。缺必需材料只限制相关判断，自检不代跑测试、不编造配置或评价标准。

本仓维护文档的内容与命名方法来自用户级 Skill；本文只维护项目标准、取证和评分。执行疑问、自动交回及第二轮起的返修反思按角色方法执行；涉及本仓目标或验法变化时同步本版标准变更并固定新对象，原报告保留。

#### 标准先于实现

顺序为：需求与目标确定 → 更新标准和本版变更 → 核覆盖与判法 → 开始实现 → 按绑定修订评审验收。设计者写目标/效果/适用边界、正常和必要失败的判法及证据依赖；设计者或指定reviewer核来源有效、能分对错、消费者和保持/退出完整，实施者开工核对并固定身份。作者核对标自查，不宣称独立评审；无需用户重复批准已确认目标的技术验法。

开工核对须能读到本版记录、对应标准、全部目标与保持集合、具体判法/证据依赖、关键未决及固定身份。标准未就绪可调查和验证可行性，受影响目标的产品实现待核对后开始；已定且无依赖工作继续。真实CLI证据可后取，依赖缺失限制完成结论，不自动阻止全部实现。已有在途版本先补当前核对，不倒填历史开工日期。

| 变化 | 标准和交接动作 |
|---|---|
| 新增 | 写目的、效果、边界、判法/证据及与旧能力组合验证，再实现 |
| 修改效果/输入范围 | 保留能力ID、增加条目修订，写前后差异、有效版本、消费者与旧证据失效范围 |
| 退出 | 列有效需求依据、接替者、入口/状态/数据/指令/文档/专用测试的退出及保留能力 |
| 拆分/合并 | 记录旧新ID映射和所有原要求去向，避免重复计覆盖；退休ID不另赋无关能力 |
| 方法改进 | 目标不变时记录方法的区分力及证据门槛变化；旧对象可复核则另写重判，不追写旧run |
| 保持 | 引用固定修订的完整保持集合并核依赖；共享/组合改动影响时做定向回归，不以“文件没改”直接签符合 |

中途发现目标变化，先更新标准再改受影响实施；发现实现错误修实现。标准自身错误回有效目标，若涉及承诺、额外人工中断、评分量表或范围改变，由用户决定；其余技术验法在已有授权内核定。先明确样例是格式、输入、效果参照还是已确认答案，再同步样例/金样/测试；金样实质业务变化仍按既有确认规则。

#### 对象、修订与证据绑定

开工/报告记录：任务类型与范围、目标版本、标准修订/条目修订及本版变更、源码/安装/运行对象身份、需求材料和决定版本、证据层次；涉及运行再记宿主/模型/配置、Case/阶段/干预及终点。未提交内容纳入身份：在`output/evidence/<题>/`保存实际文本及SHA-256，不能只报HEAD或未来会变的路径。并行版本各自固定标准；共享标准合并有效增量时明确各版适用范围，不能覆盖另一版目标。

旧证据复用先核目标、输入、源码/配置、消费者及证据职责未变；不同则失效或仅支持未变部分。重判写新记录，指向原对象和旧报告；新修复不能成为旧运行收益。外部Framework故障归因单列，当前消费者效果不据此伪判Extension通过或擅改Framework。

#### 四类任务的范围与评法

| 任务 | 必核范围 | 证据入口 |
|---|---|---|
| 需求/方案评审 | 新/变目标、受影响保持能力；目标→标准→方案是否有效、必要且可实施 | 有效Spec/Plan、用户决定、全量标准/本版变更、当前工程事实；不强索未来运行 |
| 实现评审 | 实际diff及全部消费者、新旧职责替换、保护和退出；目标对齐与实现符合分别判断 | 实施交回、含未提交/新增文件的差异、真实调用位置、§5验证及固定证据 |
| 效果/单次运行评审 | 实际覆盖条目和副作用、输入送达、理解/决定、产物、下游使用、恢复与成本；未走到的仍列未覆盖 | §4.3原生事件与对象身份、§6.2过程、§6.3独审原报告、§6.4产物与金样；读取[金样入口](golden/README.md)及所用组的前提与原始材料 |
| 版本/全量评审 | 对应修订的全量适用条目，改变与保持均核，当前缺口/收口/发布条件分别报告 | 全量标准与变更、候选源码/安装身份、相关运行和上述效果证据；未覆盖保留，评分与发布分别处理 |

先定位有效目标和原件，再核作者声明。逐项沿生产者→行动前送达→理解/决定→产物→消费者→失败恢复查事实。机械判断复用§5工具；语义核完整原件、业务关系、责任、未决和产物，独立审查区别于作者自述；组合行为需正常入口实际证据。helper仅证明自己的真实输入输出与消费者即可，不强制每项CLI。

按用户级review分别交回目标、方案、实现、验证、过拟合、补丁与退场判断；实现完整消费者及工作区差异必须与已定关键设计对照，绿测不代签目标或实现符合。全范围过拟合包含本次可见的提示词、代码命名/注释、工具输出、输入/夹具和环境及实际装配结果，不仅搜Case专名。合法业务/协议/平台条件与局部选择保留。

按真实功能、数据和权限影响判阻塞及最小关闭条件。构造反例只说明该边界，不自动扩大产品范围。新职责有消费者，旧机制含入口/状态/配置/引用及专用测试退出，有效能力/保护保留；纯新增不造退场。根因未定或支持模型波动时按§6.2记录与接续，不将每个差距直接改为产品功能。

#### 结论与报告

逐条用：目标ID/修订与预期｜目标/方案对齐｜实现与旧机制退出｜证据对象/层次及效果结论｜差距、责任、下一动作。独立子条件分别判，结构/语义/行为分开；方案评审没有实现时实现/行为列明确未到位，不强索未来运行。

| 结论 | 使用条件 |
|---|---|
| 符合 | 条件适用、对象一致、结果成立且该层必需证据已取得 |
| 偏离 | 有具体事实说明目标、实现或效果不满足有效要求 |
| 未覆盖 | 未跑、未读全、无原件、缺环境/权限或方法尚不能证明；保留条目及依赖 |
| 不适用 | 有输入/范围事实及来源证明触发条件不成立；设备/视觉/目标仓缺失不属此类 |

报告保存在该任务原有评审目录，包含对象/修订/范围、逐条表、完整保持集合与实际覆盖集合、未覆盖/不适用及理由、根因和最小动作。对需求对齐、实现/退场、确定性、独立语义、真实行为、成本、用户确认与发布条件分别汇总。单次运行可按范围紧凑分组引用保持集合；版本验收逐条列出全量适用集合，不能用父组通过掩盖子项。

需覆盖比例时以固定修订适用条目为分母，并列符合/偏离/未覆盖，不适用单列；多标签不重复计，未映射齐不报百分比。覆盖比例不作为质量分。评分、用户确认和基线晋升仍按§6.4；Spec/Plan只评Extension扩展与义务，Framework主设计另归因，Story/Review整体评价。成本先核区间/等待/外部故障/并发，工具截断只报观察数；历史可比条件和同条件独立重复仍按§6.4，不新增统一次数/成功率阈值。
