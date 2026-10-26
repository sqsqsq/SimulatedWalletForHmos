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
| 用户级维护 Skill 的 doctor / doctor env / review 接入 | §6.5按调用分流：env仅检查接入；doctor核使用证据并新增报告；效果评审再读§4.3、§6.2—§6.4及金样入口 |
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
| `output/scratch/` | **临时**：一次性脚本、pytest 缓存与 basetemp、离线验证的日志与模板装配记录 `verify/<时刻>-<场景>/`、临时工作区 | 维护者、pytest、§5 | 不作证据引用，可以随时删；交回要引用的脚本先复制进 `output/evidence/<题>/scripts/` |
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
等只读检查。本轮要改终点时改 `case.yaml` 的 `end_at`；`--end-at` 只作一次性覆盖（§4.1）。

### 1.2 起跑前的固定顺序

0. **实例前置自检**（缺一不起跑）：`framework.config.json` 配了 `paths.ui_kit_target_dir` 且该目录已物化 UI kit 组件，否则跑到 coding 的
   Case 都会被 UI kit 门禁拦在「目标目录无法解析」上；demo 的 `framework/harness/state/` 下没有属于别人的阶段状态（有则先弄清归属，
   再决定是否 clear-state）；demo 是发布基线：顶层没有维护目录（`test`、`tools`、`output`、`scratch`、`.bak`、`.git`）、没有 `doc/features`，
   git 查询成功且非忽略改动为空。Windows 上被测 CLI 在 PATH 里解析到原生可执行文件，不是 npm 的 `.cmd` 包装（配法见
   [tools/cli/README](../tools/cli/README.md)），否则首条请求会在启动前被拒。被测 CLI 的容量事实已固定并写进本轮运行证据：二进制版本、
   请求实际用的 model 与 config 路径、生效的输入 / 上下文 / 输出上限、上下文压缩怎样触发、服务计量约束，只记非秘密字段；
   查不清的项照实标未知，上一轮出过输入超限而它仍未知时不起跑，报容量风险未核。
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
`oh_modules`、`build`、`.hvigor`、`__pycache__` 等运行态，业务模块自己的单测目录照常带上）→ 换上被测 Framework：按
[`test/config/framework-under-test.json`](config/framework-under-test.json) 从维护仓 Git 的固定发布提交取 framework 子树原始字节（核树 OID 与发布清单，
只留 harness 依赖、锁文件、运行报告与状态等运行态，依赖声明变了就停），核并应用同一文件登记的本地宿主补丁，配置的 `materialized_adapters`
纳入登记的 adapter，在干净进程环境里跑原生 UPDATE 物化，核补丁动过的子代理模板与物化产物逐字节同源 → 把根 `extensions/` 的当前开发源
（含未提交改动）装进模板的 `doc/extensions/`、按原生物化写宿主入口 → 核模板与开发源逐字节同源 → 再核 demo 提交与干净状态未变。任一步
不成立，模板作废、不建 Case、不起跑，修好后重新装配。demo 平时保持其已接入的 Framework；被测组合只存在于模板。各 Case 工作区从模板复制，
再放入该 Case 的输入；启动前检查路径边界与软链接，并在 `workspace-boundary.json` 记录 demo 提交、被测 Framework（发布提交、树 OID、版本与
source_commit、补丁及其摘要、物化清单、子代理产物摘要）、`copied`、`excluded`、安装结果和各 Case 的 `case_seeded`。
每次启动 Case 前，按这次选中的 CLI 用 Framework 的 `check-personal-setup --ensure --select-adapter <CLI 名>` 写好这个隔离工程的
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
这层配置由被测 Framework（固定发布树 + `test/fixtures/framework-local/` 补丁）的原生 UPDATE 物化进工作区模板，不在 demo；模板里没有它时 `start` 在装配后、任何 Case 起跑前停下。

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

1. 读 `adaptive_reply_requests[]`：`model_prompt` 是模型的完整原话，`question` 只是前 1200 字的展示摘要（`question_truncated` 为真时
   作答前读完整的那份，不把摘要当原话）；`run_id` 与 `turn` 是这一问的身份，回话原样带回。`candidate_steps` 列出等待类型一致、
   还没答过的规划条目，每项有 `id / text / deliver / expected_kind / expected_phase / phase_ready`：当前阶段已知时只列阶段前提成立的，
   阶段未知时都列、`phase_ready` 为假。候选只说明阶段与类型可能相关，是不是这一问、立场等不等价由宿主读完整问题判断。
   `planned_*` 是首个候选的派生展示，没有候选时为空并在 `plan_note` 写明，按 `answered` 只答所问；`script_cursor` 是第一个未答条目的位置；
2. 判断属于哪一种、说什么，用 `--reply-kind` 如实标注：

   | `--reply-kind` | 什么时候用 | 说什么 |
   |---|---|---|
   | `planned` | 模型问到了规划里候选条目对应的事，`phase_ready` 为真 | 把立场用自己的话说出来；`--step <id>` 指名这次实际回答了哪几条，一个合并的问题可重复给多个 `--step`，未问到的条目不带 |
   | `answered` | 规划之外、需求方答得上的问题（范围、优先级、口径）；framework 的术语确认与视觉 provider 询问、模型自开 update 时问补料也属这类 | 一句需求方立场，不捎带规划里别的立场；不带 `--step` |
   | `neutral` | 模型没有提问，只是在推进，装置照例叫了宿主 | 一句不含事实的推进（「继续」）；不替它确认材料、范围、口径，也不重放上一条的编号。同一件事连续没有进展时不刷「继续」，报用户定；不带 `--step` |
   | `improvised` | 以上都不是 | 尽量不用；它会污染观测，原话要进交付报告 |

3. 同一回合立即再 `poll` 确认消费。

**怎么说**：需求方是在拍板，只答模型实际问到的业务问题，话说短。

- 模型给了编号选项：整个选项与需求方的既定立场等价时只回编号（「1」「A」）。选项夹带了立场里没有的结论、或没有等价选项时，不选编号，用一句业务话把决定限定到立场本身（如立场是「失败后怎么处理待定」，就不批准一个同时写着「可直接重走验证」的选项）。术语确认只确认需求方能确认的业务含义，工程模块怎么对应归工程事实。
- 一次问了几件：同一次回话逐项具名答，带上议题与结果（「T1 加更新接口；T2 保持待定」），可以带编号但不裸回几组编号；没被问到的立场不预送。
- 已经有效答过的问题被再问：指回已有的决定并继续，记成额外确认，不当成新的批准；没有依据的真实选择交用户或保持未决。
- 材料关卡：模型第一次停在材料关卡，就把该 Case `supplements/` 里 `on_request` 的补料全部 `--deliver` 进收件箱，再只回表示「已放入」的编号；
  之后再问，回表示「材料就这些」的编号。人手上的材料一次交齐，不按模型点名挑着给，也不描述文件里有什么。
- 规划外的问题：一句立场，不点命令、文件、字段、关卡名，不复述它已说过的。
- 同图增强是产品自己的工作：不回「补不补」「补上吧」替它决定；做不完、读不出是产品或装置的事实，如实记录，诊断性的救场要有用户授权并记 `improvised`。
- 业务终点之后的推进（例如方案做完问要不要编码）：明确「本轮停在方案，不进入编码」，同一条消息里的其他问题照常逐项答。
- 本地阅读状态读不出是技术故障：装置在停等里自己重探，恢复了直接往下走，宿主不用回「收到」；读得出而没做完时才交宿主。

`awaiting_reply` 在它出现的那次唤醒内回复完：`model_prompt` 就是原话，`case_inputs_hint` 是本 Case 的公开输入清单，当轮即可作答；推到下一个周期
按协调失误记入观测记录，延迟在观测与成本报告里如实写明。宿主只读本 Case 的公开输入，不读其他 Case、历史答案或提示遗漏项。意外行为与关键词只记录和理解；`stop` 与 `retry` 只响应用户
明确要求（§4.2），单个 Case 失败不停其他 Case。

```powershell
python test/scripts/run_multi_case.py reply --suite-id story-suite-20260822-140000 `
  --case <case-id> --run-id <run> --turn <turn> --reply-mode adaptive --reply-kind planned `
  --step <id1> --step <id2> --reason "模型问范围怎么定，对应规划里的不拆单立场" --text-file <UTF-8回复文件>
```

`--run-id` 与 `--turn` 必给，回复只落到宿主看到的那一问：同一问已有成功回复时，同样的话、材料与条目重发返回原结果、不再发，
不同的被拒；没有成功记录时目标必须正是当前在等的那一问，模型已换到下一问或换了 attempt 就不收。`--step` 重复或不在规划里、
类型或阶段对不上、补料不在本 Case 的 `supplements/` 里，都在发送前拒绝，不消费条目；发送失败也不消费。发送结果不确定时输出写明，
先核该 run 的 `events.jsonl`，不自动重发。成功的回复在 `observations.jsonl` 记下 `run_id / turn / text / deliver / covered_steps`，
Case 的 `answered_steps` 是本 attempt 已答条目的集合（新 attempt 从空起，初段转 update 沿用），相邻两问再次确认同一立场不重复计入；
未问到的条目收尾时标未发生，不判成败。

回话要带材料时加 `--deliver <文件名>`（取自该 Case 的 `supplements/`）：文件先落进收件箱，那句话才排进队列。
回话多行、带引号或以 `/` 开头时写进一个 UTF-8 文件，用 `--text-file <文件>` 代替 `--text`：Git Bash 会把命令行里以 `/`
开头的参数改写成 Windows 路径（`/story update` 会变成 `<Git 安装目录>/story update`），从文件读不经 shell。

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

Claude Code 在系统内存紧张时会回收空闲的后台任务，并提示「不要自行重启、等用户要求」。**用户已长期授权（2026-10-24）：
CLI 测试的后台 `watch` 因内存被回收时，宿主直接按上一段恢复，不再逐次征求同意。** 授权只覆盖重起这一个敲门器：
不重启被测 Case、不 `retry`/`stop`、不改配置；回收后先零等待 poll 补回漏掉的回话，再重起，并在回复里说明是内存回收后的重启。
同一 suite 反复被回收、或 poll 本身失败时停下报告用户。

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

交互 Case（`interactive: true`）目标闭环后不立即终止，停在第一检查点（`awaiting_kind: initial_checkpoint`），模型最后那一问在 `pending_question`：
它是本段的交付选择（系统单交付门的交付选择，如送审）时，按该 Case 公开任务与 `interaction-script.yaml` 的立场 `reply`，模型做完被授权的动作
后再停一次；本段没有待办或已做完，按 §4.2 `conclude`，终态 `finished`。是否归档只看公开任务、交互规划与真实人答，系统单不因到了 spec 就算授权上传；
用户仍在选择时不提前收工为已送审。没配 `after_initial: update` 的 Case 在这里没有第二段，`resume-update` 被拒、不投 update 输入；配了的按 §4.4。
到目标却没拿到 session 时本段续不了，终态 `cli_session_lost`，不报完成、不另起 run。

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
| `target_closed = true` | 自动 Case 装置自己停；交互 Case 停在第一检查点，按 §4.1 答完本段交付选择或无待办后 conclude |
| `target_closed = false`，模型宣告本轮已完成，且 `target_missing` 只剩宿主已判为不属本轮的项 | 判定本轮到位 → `conclude` |
| `target_closed = false`，`target_missing` 还差凭证、模型也没宣告 | 按需求方身份继续回话 |
| 拿不准 | 再 poll 一轮 |

```powershell
python test/scripts/run_multi_case.py conclude --suite-id story-suite-20260822-140000 `
  --case <case-id> --reason "需求说明已送审，本轮终点 story 已到位"
```

`conclude` 在模型这一轮结束时生效：worker 在轮与轮之间读收工请求，自己退出续话循环，门禁照跑、产物齐全。

模型没有提问、在正常推进时，按 §3.2 的 `neutral` 回一句；模型在一轮里陷入循环（同一件事反复做、重复输出同一个词、runlog 里自述绕不出去）、
没有业务进展地生成，或 poll 报一个 Case 长时间没有产出（`events_idle_sec` / `stalled`）时，这是异常，不机械连发「继续」把它算成正常运行：
保留原话与事件，按故障向用户报告现象与依据，由用户决定处置（宿主不自行获得停测权限）：

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
| 1a | 那一问是第一段里的业务动作（系统单交付门的交付选择，如送审）时，按 `interaction-script.yaml` 的立场用 `reply` 回答；模型在第一段里把它做完（归档以核心 archive 的回执、读回与本地登记为准）后再停到第一检查点。已固定的快照随之作废留证（`initial.superseded-*`），从第 2 步重来 | 归档是第一段的终点动作，和第二段的投料不合成一轮；本地单没有归档，不为凑覆盖调对接层 |
| 2 | `checkpoint --case <id> --point initial` | 它停着、没有写入者，复制才说得清是哪一刻；需求目录、关联蓝图与需求目录外的 Story 审查报告同一刻固定，复制前后目录摘要不同则快照作废 |
| 3 | 只读评测那份快照 | 工作区马上要跑第二段 |
| 4 | `promote-checkpoint --case <id> --point initial` | 第一段回流到维护仓 `doc/features/<需求编号>`；不先回流，第一段产物就只剩快照 |
| 5 | `resume-update --case <id>`（投 case.yaml 的 `update_request`，与第一段的 `prompt` 同一条路）；Case 有 `review_human_zone` 时加 `--review-feedback-file <本次反馈文件>` | 只投第二段请求；第一段回流之后 `reply` 被拒，不再在第一段里继续。`update_inputs` 在这一步按下表投放，`--deliver` 只投 `supplements/` 里的补料；全部输入写前核完，一项不成立就一项不写、不发请求 |
| 6 | 第二段起手在材料关卡停一次，按该 Case `interaction-script.yaml` 的 `update-material` 作答；之后 Case 停在第二检查点（`stop_reason: update_checkpoint`） | 终点以流程契约里这一轮 update 关闭为准，模型说「更新完成」不算 |
| 7 | `checkpoint --point update` → 只读后评 → `conclude` | story 门禁已在进第二检查点前跑过；第二检查点的唯一出口是 conclude，不发的话 worker 一直等，最后只能被外部停掉、终态成 `worker_lost` |
| 8 | 全部终态后 `finalize --promote` | 实际续跑过第二段，终态文档落到 `<需求编号>-update`，第一段那份不被覆盖；只跑了第一段则回原编号，`promotion-manifest.json` 的 `segment` / `partial` 说明是哪一段、走没走到检查点 |

| `update_inputs` 的 `kind` | 投到哪 | 模拟的是 |
|---|---|---|
| `local_material` | 需求目录的收件箱 | 人手上的新版文档 |
| `system` | 需求系统里那张单（`destination` 指文件） | 上游正文或评审回稿被更新，update 取上游时取回 |
| `review_human_zone` | 宿主指定的那条 D 议题的人工区 | 评审人表态；静态意见只写结论与意见，见下 |

**人工区意见文件**：宿主读第一检查点那份 Review，按语义为每条静态意见选它真实对应的 D 议题，写一份 UTF-8 YAML 非空列表，每项
`{source_item: 1, decision_id: D1, verdict: 需修改, opinion: <原意见>}`。`source_item` 按 Case 里各 `review_human_zone` 源的声明顺序、
条目顺序从 1 连续编号，只指已有输入的位置；文件要恰好覆盖每一条一次，`decision_id` 不重复，`verdict` 与 `opinion` 等于静态意见
（按 YAML 解析后的值比，不比缩进与引号）。找不到真实对应的 D 时停下，把未投的那条意见交维护设计者裁定，不伪造 D、不塞进相似议题。

脚本核：初段 Review 与工作区 Review 的机器区逐字一致、D 标记唯一、人工区三态与修改意见行齐全。都成立才一次写入：目标三态勾一项、
其余两项不勾，写修改意见行，原换行与其余文本不动；空白人工区可写，已有完全相同的意见是幂等重投，已有不同的人工意见保留并报投递冲突。
执行中途 IO 失败时不启动模型，输出已投与未投的明细，已写的人工区如实报出，修好后按同样输入重试。

```powershell
python test/scripts/run_multi_case.py resume-update --suite-id <suite> --case <case> --review-feedback-file <本次反馈文件>
```

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

离线验证用 `test/scripts/verify.py`，从仓根执行，只选场景。并行参数（`-n auto --dist loadscope`）、模板装配与先后顺序都写在脚本里，不手拼 pytest 或检查命令：

| 场景 | 命令 | 什么时候跑 |
|---|---|---|
| 改一处 | `python test/scripts/verify.py affected <测试文件…> [-k <关键词>]` | 改动后跑直接覆盖它的用例；子步骤收尾时把它所在功能块的几个测试文件一起给 |
| 全量 | `python test/scripts/verify.py full` | 提交或交回前一次 |
| 失效形态 | `python test/scripts/verify.py failure-modes` | 现建装好开发源的模板（与 §1.2 同一装配函数）再跑 §5.4；各条形态按进程并行，结果按台账顺序输出 |
| 交回 | `python test/scripts/verify.py handback` | 交回前一次：全量、失效形态、其余离线检查（CLI 测试、compileall、validate_clis、每个 `.mjs` 的 `node --check`）三条通道同时跑 |
| Case 计划 | `python test/scripts/verify.py cases` | 改了 Case 或多 Case 编排时：全部 Case 出计划，并行数取 Case 数 |
| 装配专项 | `python test/scripts/verify.py assembly` | 第二次从空目录经同一入口重建工作区模板，身份核对与第一次相同。`test/config/framework-under-test.json`、`test/fixtures/framework-local/` 补丁或 `create_workspace_template` 装配代码相对上次专项证据有变时必跑，交回引用该次 `output/verify/<时刻>-assembly/`；没变时复用上次证据并写明被测 Framework 与补丁的身份。全量只保留一次当前装配与协议核对，不选这一类 |

每步的完整输出写到 `output/verify/<时刻>-<场景>/<步骤>.log`，控制台按完成先后打印每步的结论行与耗时，多步时最后按固定顺序汇总；有一步失败退出码非 0。
同时跑的前提是各步只写自己的位置：每次现建自己的模板，测试与失效形态各用自己的临时目录，跨进程共享的重夹具（`tests/shared_state.py`）有锁、造好再改名。
新写的测试或失效形态检查要守这一条；要排查并行带来的问题时，失效形态加 `--jobs 1` 串行对照。

`test/tests/conftest.py` 给测试起的 node 进程带上 ts-node 转译缓存（系统临时目录 `story-ts-transpile-cache`，按内容取键，删了只会重新转译）；
要读原生 Framework 的用例按准备状态分小类，一个类只造一种状态：`loadscope` 按类分 worker，大类会串行拖住整轮。

- 按影响范围分层跑：改一处用 `affected`；全量与失效形态回归只在提交或交回前跑一次（`handback` 同时跑完）；无新改动不重复刷全量，要看某条失败的细节用 `affected` 只重跑那个文件。全量用时预算与超预算的处置见 [tests/README.md](tests/README.md)「用时预算」。
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
`verifier_gap_sec`、`delegations_unresolved`、`first_harness`、`first_story_register`、`rework_min`；等人时间只有全程数 `human_wait_sec`。各项读数口径见 `measure_run.py` 文件头。

计数按调用：同一 run 里同一调用编号的开始与结果事件归并成一次，名称与入参取开始，输出与终态取结果。
- shell 工具认 bash / pwsh / shell / shell_command。
- verifier 只认专用 `verifier` 工具与 `subagent_type=verifier` 的 task；其它委派记进 `delegations_unresolved`，是不是审查由人判断。
- 首次门禁、登记与返工只看有结果的调用，命令报错也算没过；读一份旧门禁报告不是一轮门禁。
- 归并不了或被宿主输出截断的条目（只有开始、只有结果、同键冲突、跨检查点、`source_truncated`）列在 `incomplete_tool_events`，此时计数只是已观察到的次数；被截断的门禁结果不出结论。
- 门禁结论另按种类给全程数：`gate_fail_by_kind`、`gate_unknown_by_kind`（harness / story_register 分计，没结果、冲突或截断记判不了）；`gate_rounds_with_fail` 只数原生 harness，不能用它为 0 概括本轮没有 FAIL。
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
| 产物结果 | `story.md`、`review.md` 与设计附件 `design-review.md` 作为一组评审载体 | 已确认范围与原始材料、最终 decisions、金样的形似/神似、verifier 与人工审阅 |
| 性能 | 从 Story init 开始到可交付结果的完整过程 | 总墙钟、作者/脚本/verifier/返修耗时、循环次数、上下文增长、规则与 checker 读取；人工等待和外部故障单列 |
| Knowledge 应用 | 适用知识在本次需求中的消费结果 | 看到、理解、应用、传递四段证据；用确有适用知识的 Case |

三项各 100 分，不加权、不互相补偿：`90–100` 达到目标；`70–89` 未达目标，记录主要缺口继续优化；`<70` 本次测试失败，回对应所有者定位。
代表性测试三项均达到 90 且经用户确认，才能宣布达到评分目标；已结束轮次保持其用户裁定。

2026-10-23用户确认：性能先消除已证无效循环，不为半小时继续扩机制。未达到性能期望仍如实评分；用户可接受剩余耗时作为版本限制，发布决定与“已达评分目标”分别记录，不因此改写旧分或自动判高分。

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
2026-10-23用户确认：每次评测必须以金样为目标并排核图、表/文字、形态、内容、叙述逻辑、条件/异常、知识及成本；不要求完全相同。每项差距给出金样效果、实际位置、输入与人答差异、作者得到的信息和决定、独审反应、最终结果，判断合理变体、模型波动、机制缺陷、装置问题或证据不足。机制归因须有实际生产/消费位置，不把未覆盖当失败、不将所有差距归随机性、不用金样额外前提代替授权。

测试探针仅用于检验所声明的能力，不是产品规则：不要求模型问完交互脚本中所有备选问题，不要求固定议题标题/D号、图数或金样额外方案。Review未处理不自动构成失败；只核当前工作是否因真实缺依据而需要确认。意见未投放与产品漏处理分开，前者列未覆盖并回测试装置，不追加通用审批或范围外实跑。

当前正本是 `golden/auto-topup/`（止于 Spec）与 `golden/car-key-sharing/`（止于 Plan），只在这一处维护；文件身份、引用与图源由 `test_golden_sample.py` 核，第二份副本由 `test_run_measurement.py` 核。

### 6.5 维护标准与评审

目标依据由用户有效决定及需求正本维护；[全量评价标准](regression/extension-acceptance.md)维护当前Extension能力的效果与判法。每版在`doc/spec/<版本>/评价标准变更.md`记录增量、采用修订、保持集合和核对结果。标准正文只保留一份；历史正文用Git或当次固定文本保存，历史报告保持当时结论。

#### 用户级维护 Skill 的项目接入

`maintenance-designer review` 按下方对象分流取得材料，不缩成代码diff检查。两个维护Skill共用doctor方法：`doctor env`只检查根AGENTS、标准/任务入口、§5验证和证据引用是否可读一致，不深入业务历史、不写诊断报告；没有具体任务版本时仅列任务级前提，不猜版本或判全环境损坏。

默认 `doctor` 先核环境，再从README项目定位、`doc/spec/`有效版本范围和`doc/plan/`当前入口建立全貌；沿需求/方案、答疑、实施反馈、评审/返修、实际`extensions/`与相关配置/消费者，核目标、协作及规则/Skill使用。读取相关未提交、未跟踪及指向的被忽略材料；按有效总览定位批次/步骤及各批实施反馈、评审，跨批返修沿原问题引用复查；旧目录可接续，不按时间或目录名断定有效性。索引全貌与深入核查分别报告，不要求无差别读所有历史。

维护讨论先读相关Spec/Plan、交回和评审的“讨论与修订依据”或等价章节，沿原诉求、当时处理、纠正和落实核原话、修改前对象及实际差异；缺记录列未知，不据最终成功推断无需干预。它们是维护协作证据，不替代消费模型正式运行证据，也不投放给消费模型。记录方法由用户级共享文档约定维护，doctor只报告缺口，不补写被审材料。

使用证据从当前交回/评审引用定位：离线结果与维护原件在`output/evidence/`，正式运行原事件和产物在`output/story/`，需求回流按§4.5；分析实际行为读§4.3、§6.2—6.4及所用金样组前提，绑定当时输入、源码和标准，不以最新工作件追改旧结论。会话只沿已有明确指针读取，无原件或被截断的部分列未覆盖。用户纠正、执行者补设计、无效循环和模型波动按现有归因方法判断。

报告统一新建`doc/diagnosis/YYYY-MM-DD-HHmmss-维护自检.md`，可覆盖多版本；关联前次同项目报告，分别核采纳、实际落地、退场、效果证据与新增问题，缺证据保持待验证。必要副本/摘录和摘要放`output/evidence/<本次诊断>/`，优先复用已有固定原件。诊断报告按用户级约定逐次保留，doctor不提交，后续归档沿本仓规则和授权。

缺必需依赖只限制相关判断；doctor仅写本次报告和必要证据，不修规约/Skill/配置/产品/标准，不生成正式Spec/Plan、不启动新模型或设备测试。候选优化由用户选择后进入既有设计实施流程；项目特例不直接升级为用户级规则，公共Skill原件不自动改写。

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
