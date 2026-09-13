# Story 并行 CLI 测试指南

本指南是 Story 测试域的当前端到端操作协议。维护约束见 [AGENTS.md](AGENTS.md)，演进背景见
[EVOLUTION.md](EVOLUTION.md)。这些维护文件不得进入被测模型上下文。

## 按当前任务读取

| 任务 | 必须读取 |
|---|---|
| 启动、恢复或驱动真实Story CLI | §0–§6完整运行协议；结束后按§8、§10评价 |
| 维护脚本或做离线验证 | §7及本次涉及的运行分支；需要评价运行行为时再读§8、§10 |
| 评估已有测试、比较历史或对照金样 | §5证据、§8测量与行为还原、§10评分与跨轮比较 |
| 定位verifier链路故障 | §7.0；真实smoke另按§7.0.1及§0授权边界 |
| 排查真实稿件与审查结论不符 | 先按§8.1还原证据；确需专项诊断时才读§9 |

命令参数与配置以当前入口及配置文件为准；历史动机查EVOLUTION或Git，不从过期批次文字推导现行义务。未实施的设计不能当成当前运行能力。

## 0. 新会话协议

宿主模型完整阅读§0–§6后，用户输入“开始测试”即进入编排。宿主负责测试生命周期、观测和回复；
被测模型是隔离 Case 中由 CLI 启动的模型。宿主每次从当前 `cases/*/case.yaml` 动态读取可用 Case，
按读取结果生成编号多选项，并另列“全部当前 Case”。不得假定固定数量、名称、feature 或顺序。

允许单选、多选或全选。确认前复述实际 Case、feature、目标阶段、隔离 workspace 和回灌范围；只能执行
`plan` 等只读检查，不能创建 suite、迁移 features 或启动 CLI。

**CLI 测试一律以非沙箱启动**（用户长期授权，2026-09-04 复述确认）：`start` 必须传
`--authorize-non-sandbox`，`plan`、`poll`、`reply`、`conclude`、`finalize` 同样在非沙箱环境跑。
驱动器要拉起并探测子进程、读写隔离 workspace、把产物回灌进本仓，沙箱里这些都做不成。
每一轮不必重新征求授权。

这条只管**宿主**：不是要求被测模型切换环境，也不得写入 Case prompt。
宿主自身的权限层若拦下某条命令，请用户放行，不要改写命令绕开——绕过去的那一跑不算数。

### 0.1 测试目标与观测边界

- 正式 Case 是组合业务场景；叙述变形只做离线检查，不构成正式 Case。
- 每个 Case 只能看到自身 workspace、初始任务和已发送交互，不得接触 `test/story/` 维护材料、其他 Case 或历史 suite。
- 观测者（外层协调器）不得替被测模型运行 gate、修改被测产物或清理阶段状态。

### 0.2 宿主在实跑期间的角色：需求方 / 评审人

宿主仍属于维护者，由本次任务指定的维护角色担任（分工见 [AGENTS.md §1](AGENTS.md)），但实跑期间只代理需求方/评审人职责。被测模型面对的是一个懂业务、不代它研究框架实现的对话方。

| | 做 | 不做 |
|---|---|---|
| 读什么 | 送审给你的归档件（叙事主件与评审记录）——评审意见要从它读出来 | 实现件（规格件、方案、契约、源码）与门禁报告。评审人拿不到也不看 |
| 说什么 | 需求侧的话：范围怎么切、哪条优先、验收期望、评审意见、对某个结论同不同意 | **实现路径**——不点名脚本、命令、文件、字段、门禁与判据 |
| 卡住时 | 重申需求意图，让它自己找出路 | 告诉它该跑哪个命令、该改哪个文件、该走哪条流程分支 |

**为什么这条是硬规则**：说出解法的那一刻，测的就不再是「被测模型能不能自己走通」，而是「宿主
知不知道答案」。实测出现过一次——宿主用维护者口吻回话，把重开流程的路径直接喂了过去。

其余纪律：按本协议poll / 回复 / 记录；heartbeat及代跑轮询只承担§3.1/§4的观测唤醒，不另派Agent或维护任务研究、改写被测产物，避免宿主hook污染证据。不在主工程跑harness。**评测在finalize之后做，实跑期间不切换成实现维护职责。**

## 0.3 人手跑一遍（不经测试装置）

想自己在本仓试 `/story init`，先装本地需求系统——`story.js` 把需求系统当一个本地目录读，
而它的默认目录**在仓里从来没存在过**（装置从不走这条回落，所以只有人手跑才撞得上）：

```powershell
python test/story/scripts/bootstrap_local_story.py --list              # 有哪些单
python test/story/scripts/bootstrap_local_story.py --verify AR90006    # 装上并验证链路
```

装完**不用设任何环境变量**（目标目录就是 `story.js` 的默认值），会话里直接说
`/story init AR90006` 即可。三点要知道：

- 目录是**可写**的——`archive` 会覆盖单据正文、`restore` 会回退；想回出厂状态跑 `--reset`；
- `doc/features/<单号>/` 已存在时脚本会**拦下来**：`story.js` 落材料时「已存在就跳过」，
  残留会让新一轮材料拉不进来且不报错。先把它移走；
- 补料（`supplements/` 里那些 docx）不会自动进 `inbox/`——那正是「模型会不会开口要材料」
  要观测的东西，手跑时等它开口，你再复制过去。

**这套东西只给本仓**：真实工程有自己的需求系统，`story.js`/`review.js`/`token.js`
三个替身本来就要换成自己的实现，连带也不需要这个脚本。它因此不随扩展包交付。

**它与 CLI 测试互不干扰**：装置给每个 Case 的需求系统指针要么指向该 Case 自己的快照、
要么指向一个不存在的路径，绝不会落到这个目录（有机械回归守着）。

## 1. 唯一入口与启动

正式测试统一使用 `scripts/run_multi_case.py`，即使只运行一个 Case，也不直接运行 `run_case.py`。

```powershell
python test/story/scripts/run_multi_case.py plan --all --jobs <实际Case数>
python test/story/scripts/run_multi_case.py start --all --jobs <实际Case数> `
  --suite-id story-suite-20260822-140000 --authorize-non-sandbox
python test/story/scripts/run_multi_case.py poll --suite-id story-suite-20260822-140000 --wait-sec 0
```

四步都在非沙箱环境执行（§0）。

一轮跑下来就这四步，其余都是它们的细则：

| 步 | 干什么 | 细则 |
|---|---|---|
| 1 | `plan` 只读确认：选中哪几个 Case、feature、目标阶段 | §0 |
| 2 | `start` 起跑，建 15 秒 heartbeat | 本节 |
| 3 | **循环**：`poll` → 读 `adaptive_reply_requests` → 以需求方身份回话 → 再 `poll` | §3.0 怎么回、§3.5 什么时候收工 |
| 4 | 全部终态后 `finalize --promote` 回灌产物 | §6 |

`start` 返回统一控制对象及 `next_action=poll_after_interval`、`next_interval_sec=15`。宿主模型立即创建
名称包含 suite-id、绑定当前任务的 15 秒 heartbeat。heartbeat 建立成功后，启动回合可以结束，
后续由定时唤醒继续驱动。`status` 只用于只读诊断：不消费事件、不回复、不增加观测次数或稳定确认，
不能替代 `poll`。

**一轮实跑只有三种收场**：目标阶段客观闭环（装置自己停）、你判定到位（`conclude`）、
被测进程真的死了。**装置侧的阈值不再终止任何东西**——没有时限、没有轮次上限、
等你回话也没有上限。看到别的失败终态，那是真的出了事，不是被装置掐的。

Case 严格顺序启动：前一个取得有效 run-id、worker/lease 和活动状态后才启动下一个。确认启动后的
worker 并行运行。启动失败时检查活动指针、run、worker、lease、workspace 和原始输出，最多恢复并
重试 3 次；仍失败则保留完整事实并继续启动其余 Case。不要套外层 timeout 或输出截断管道。

起跑前的这几道（启动重试、worker 租约、稳定性确认）**保留**——它们判的是「进程起没起来、
还在不在」，那是事实，不是进度快慢。被裁掉的是拿进度当失败的那一类。

### 1.1 CLI 配置组与单 Case 故障重跑

CLI 测试按 `config/test.yaml > cli.configurations` 的顺序选宿主。具体配置条目不在执行协议中
复述，以配置文件为唯一真源。

配置组只处理 **CLI 基础设施失败**，不接管需求方角色：材料交付、范围拍板、关卡回复和
`conclude` 判断仍全部由宿主模型按 §0.2 / §3.0 执行。脚本不得因为切换配置而自动回答关卡、
自动选择需求方案或替宿主判断阶段是否到位。

两类可自动恢复的失败：

| 失败 | 识别 | 当前 Case | 其他 Case |
|---|---|---|---|
| 内容审查 400 | 只认 `DataInspectionFailed` / `Output data may contain inappropriate content` 等明确签名；裸 400 不算 | 保存失败 attempt；用同一配置从干净基线重跑一次；再次命中则终态 `content_policy_rejected` | 不停止、不重跑 |
| 鉴权 401 | `auth_required`（401 / unauthorized / invalid api key） | 当前配置在本 suite 熔断，从干净基线切换下一配置；全部耗尽则终态 `cli_config_exhausted` | 已运行的不强杀；后续 attempt 跳过已熔断配置 |

“干净基线”同时重建该 Case 的隔离 workspace、需求系统快照、补料投放状态、交互规划游标和
阶段观测游标；失败run的artifact、事件、原始输出和attempt记录保留在本suite，不被新attempt覆盖；后续清理遵循§2。新attempt回到
相同业务起点，之后仍等待宿主逐关回复。重跑是原 suite 内的单 Case attempt，不创建新 suite。

provider 失败后不对半成品跑业务 gate；只完成证据归档和运行态还原，再由协调器重建 Case。
`poll` 快照必须展示 attempt、`cli_config_id`、`failure_kind` 和配置健康状态，使宿主看得见切换，
但无需手工执行重跑命令。

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
诉求要由人**在关卡上说出口**（`interaction-script.yaml` 记的是这个立场，由宿主说出来），
不能预塞进初始 prompt：
模型走到关卡时它已在几十步之外，测出来的是记忆衰减，与关卡交互无关。

判据在 `tests/test_multi_scenario_cases.py`（词表扫描）与 `tests/test_harness.py`。

### 2.2 材料分三处，按真实体验投放

| 目录 | 是什么 | 什么时候到 |
|---|---|---|
| `cases/<id>/system/` | 需求系统上挂着的单据（一个子目录一张单，含 `detail.json` 与正文 md） | 起跑时复制到系统临时目录（**workspace 之外**，模型 `ls` 看不见），被测侧只经环境变量知道它在哪 |
| `cases/<id>/workspace/` | 起跑那一刻需求目录里就有的东西 | 起跑时 |
| `cases/<id>/supplements/` | 人手上备着、**要来的**那几份 | `deliver: start` 起跑时；`deliver: on_request` 等它开口 |

**需求系统只承载 md，不承载图片**。图片只有一条路进来：人给的文档（docx）里内嵌，
导入时抽出来。多留一条路，「归档件里的图能不能打开」测的就不是真实链路了。

材料由**宿主**在回话时带出去：`reply --text "…" --deliver <文件名>`——文件先落进收件箱，
那句话才排进队列；反过来模型会照着「我放进去了」去看一个还不存在的目录。
规划条目的 `deliver:` 只是告诉宿主「这一关该把哪份交出去」，它自己不投
（`planned_deliver`，见 §3.0）。
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
保留现场并在feature迁移前停止。安全预检已通过后的个别文件删除失败，按上文第5项记录并继续；不把它与路径或所有权风险混为一类。非suite长期目录不自动清理。features是迁移归档，不在本轮结束时恢复；本轮 workspace/output 也保留到下一轮。

## 3. 主模型驱动与单轮 poll

一次 `poll --wait-sec 0` 是完整事务：读取 suite 中全部实际 Case；并行消费所有非终态 Case 的新事件、模型输出、
阶段和状态；只处理真实 `awaiting_reply`；把每一关连同「这一关按规划本该表达什么」交给宿主
（见 §3.0，装置不自动应答）；最后统一计算稳定状态。定时器是唯一等待来源，poll 自身不得再次等待；零等待确认不计入 15 秒稳定确认。

阶段不按模型回复文本猜测。worker 运行期间和每次正式 poll 都从 Case workspace 的结构化证据校正：
feature 匹配的 `framework/harness/state/.current-phase.json` 为首选，阶段目录中的非 `reports/` 产物为后备。
`current_phase` 是当前观测阶段，`highest_phase_reached` 是本轮曾到达的最高阶段且不回退；兼容字段
`last_phase` 镜像 `current_phase`。首次确认最高阶段达到 Spec 时写入且保留 `spec_entered_at`。

每次 `start`/`poll` 返回 `suite_terminal`、`selected_case_count`、动态 `cases`、`interactions`、
`adaptive_reply_requests`、`automation_stability` 和 `next_action`。`next_action` 仅有：
`poll_after_interval`、`reply_then_poll`、`finalize`。同时返回 `progress_changed`、`changes` 和
`next_interval_sec`。每次 heartbeat 唤醒都简短展示全部实际 Case 当前阶段、交互、错误及下一间隔；
无变化也显示仍在观测。

### 3.0 谁来当需求方：宿主，不是脚本

**每一关都由宿主回答。装置不再自动应答。**

`interaction-script.yaml` 是**需求方的立场**，不是应答器：它写明这一关需求方持什么
立场、该把哪份材料交出去。宿主按当时的情境**自然地把那个意思说出来**——不逐字照抄。
真实的需求方本来就不会两次说出一模一样的句子；照本宣科还会在关卡漂移时把后面的话
提前送进前面的关卡。

上一版是「三重比对全等就自动投逐字原话，否则回落给宿主」，两个后果都实测出现过：

- `expected_turn` 是绝对序号，模型多问一关，从那关起后面**全部**条目失配、永久回落，
  设计好的话术被大面积跳过而**没有任何信号**说跳了几条（一轮里五条只投出三条，
  评审意见那条从头到尾没排上）；
- 回落时只给宿主「模型说了什么」、不给「这一关本该说什么」，宿主要自己去翻脚本；
  翻漏了就临场发挥，观测里于是掺进了宿主自己的话。

15 秒 / 120 秒的 heartbeat 正是为「宿主当人、及时接话」设的——自动应答架空的就是它。

**宿主每一关按三步走**：

1. 读 `adaptive_reply_requests[]`：`question` 是模型的原话，`planned_intent` 是这一关
   按规划本该表达的立场，`planned_deliver` 是该交出去的材料，`planned_phase` 是那句话
   的阶段前提（如评审意见要归档之后才说得通），`script_cursor` 是规划走到第几条；
2. 判断这一关属于哪一种，据此决定说什么——**并用 `--reply-kind` 如实标注**：

   | `--reply-kind` | 什么时候用 | 说什么 |
   |---|---|---|
   | `planned` | 模型问到了规划里这一条对应的事，且阶段前提已满足 | 把 `planned_intent` 的**意思**说出来，用自己的话；同时 `--step <id>` 指名覆盖了哪一条，规划指针才前进 |
   | `answered` | 模型提了规划之外的问题，但那是需求方答得上的（范围、优先级、口径） | 按需求方立场回答，不点命令、文件、字段、关卡名 |
   | `neutral` | **模型没有提问**——它只是在自言自语地推进，装置照例叫了宿主 | 一句**不含事实**的推进（「继续」）。不替它确认材料、范围、口径里的任何一件（那些是它该来问的），不注入做法或写作指引，也**不重放上一条的编号**——下一轮的编号可能对应另一组选项 |
   | `improvised` | 以上都不是，宿主自己的话 | 尽量别用。它会污染观测，评测时要单独拎出来看 |

3. 同一回合立即再 `poll` 确认消费，继续驱动。

**回话只回选项或一句短语（用户 2026-09-05 裁定）**。需求方是在拍板，不是在写说明：

- 模型给了编号选项：**只回编号**（「1」「2」「A」），不回选项内容、不解释为什么（用户 2026-09-06 裁定）——回内容等于把它的措辞又送回去一遍，产物上分不清那句话是它自己写的还是宿主给的；
- 补料：先 `--deliver` 把文件送进收件箱，再回一句「已放入」或对应选项，不描述文件里有什么；
- 模型问了规划外的问题：一句立场，不点命令、文件、字段、关卡名，不复述它已经说过的；
- 模型没提问：一句中性推进。

一次回话不超过一句。多说的每一个字都是宿主的话进了观测：模型会照着它做，产物上就分不清哪些是它自己判断的。
`interaction-script.yaml` 的 `text` 也按这条写——它记的是**立场**，不是台词。

**`--reply-kind` 是记账，不是形式**：产物出来之后要回答「这份东西有多少是被宿主的话
影响的」，只数回复次数答不出来。`improvised` 那几条要连原话一起进交付报告。

`planned_phase` 是那句话的**阶段前提**（`story` / `spec` / `archived`）。装置不再据它
决定发不发——它交到宿主手上，由宿主判断这话现在说出口通不通。评审意见在归档之前说，
模型只会答非所问。

**`awaiting_reply` 必须在它出现的那一次唤醒内回复完毕**：poll 返回的
`adaptive_reply_requests[].question` 就是模型的原话，`case_inputs_hint` 是本 Case 的公开输入清单，
当轮即可作答，不需要另开一轮去翻 runlog。只看 `status` 不读 `question`、把回复推到下一个周期，
按协调失误记入观测记录——一次跨周期等待就是白等一个完整间隔。
有 Case 处于 `awaiting_reply` 时 `next_interval_sec` 一律回到 15 秒，不受自动化稳定态影响。不得读取其他
Case、历史答案或提示遗漏项。意外行为、维护文件名或任何关键词只能记录和理解，不能据此调用
`stop`；`stop` 只响应用户明确要求。单个 Case 失败也不得停止其他 Case。

```powershell
python test/story/scripts/run_multi_case.py reply --suite-id story-suite-20260822-140000 `
  --case <case-id> --reply-mode adaptive --reply-kind planned --step scope-do-both-in-one `
  --reason "模型问范围怎么定，对应规划里的不拆单立场" `
  --text "只做挂失，不做补卡。"
```

`--step` 指名这一句覆盖了规划里的哪一条，规划指针据它前进——**不再拿回复文本去和
脚本逐字比对**。宿主是把意思说出来的，不会逐字重合，上一版因此几乎从不推进指针，
规划条目一条条烂在后面没人知道。

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

### 3.2 原话就在 poll 返回里，取不到才走兜底

`adaptive_reply_requests[].question` **就是模型本轮最后说的那段话**，poll 直接给你，
当轮就能回。它旁边的 `prompt_source` 说明这份原话是哪来的：

| `prompt_source` | 含义 |
|---|---|
| `cli_text_event` | 模型确实说了话，`question` 就是原文 |
| `unavailable` | 取不到（模型这一轮一个 text 事件都没发） |

`question` 为 `null` 而不是空串——空串与「模型什么都没说」同形，那是静默降级。

只有 `prompt_source` 是 `unavailable` 时才走兜底：读该 Case run 目录下
`events.jsonl` 尾部的 `type: text` 事件。读的是模型对需求方说的话，不是它的产物——
观测边界（§0.1）不变。

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

**`end_phase` 不再是唯一的终止开关**。它现在管三件事：驱动器算下一个未闭环阶段时的
推进目标、跑哪几个 gate 的范围、以及 `closure.target_phase` 这个比对基准。
目标阶段**真的闭环**了装置仍会自己停（那是客观事实，不是机械计数）；
没闭环而你判断本轮已经到位时，用 `conclude` 收工——见 §3.5。

终点不同的两个 Case 不再互相拖累：`conclude` 是**逐 Case** 的。
（此前 `stop` 只有整 suite 一档，先到终点的那个要陪着另一个干等，实测空转 18 分钟。）

### 3.5 什么时候收工：`conclude`，判定在你

**装置只报事实，收不收工你说了算。** 每次 poll 的 Case 条目里有一个 `closure` 块，
它把判定要用的东西一次给全：

| 字段 | 说的是 |
|---|---|
| `target_phase` / `target_closed` | 本轮目标阶段；它的四件凭证齐没齐 |
| `target_missing` | 差哪几件（`trace.json` / `summary.json` / 完成回执 / verifier 报告） |
| `artifacts_ready` | spec.md、AR/story.md、AR/review.md 三件在不在 |
| `next_unclosed_phase` | 目标之前第一个还没闭环的阶段 |
| `beyond_target_evidence` | 目标**之后**的阶段有没有真实产物 |

`beyond_target_evidence` 是「模型说要进下一阶段」这件事的**事实那一半**：
它嘴上说的时候这里是空的，它真建了下一阶段的产物时才非空。
两者一起看——`question` 里是它怎么说的，这里是它实际做到哪儿。

**装置不据模型的散文改阶段、也不据它自动收工。** 判据：

| 看到 | 做什么 |
|---|---|
| `target_closed = true` | 装置会自己停，**不用** conclude |
| `target_closed = false`，但模型在宣告「进入下一阶段 / 本阶段已完成」，而 `target_phase` 就是当前阶段 | **判定本轮到位** → `conclude` |
| `target_closed = false`，`target_missing` 还差凭证、模型也没宣告 | 按需求方身份继续回话推进 |
| 拿不准 | 再 poll 一轮。**不要 stop**——`stop` 只响应用户明确要求 |

```powershell
python test/story/scripts/run_multi_case.py conclude --suite-id story-suite-20260822-140000 `
  --case <case-id> --reason "模型宣告进入 plan，本轮目标 spec 已到位"
```

**`conclude` 不是 `stop`**：

| | 进程 | 门禁 | 产物 | 终态 |
|---|---|---|---|---|
| `conclude` | 不杀，worker 自己退出续话循环 | 照跑 | `phase-results/`、`artifact/` 齐全 | `concluded_by_host` |
| `stop` | 强杀进程树 | **从不运行** | 残的 | `stopped` |

**一条要提前说清的张力**：模型宣告「进入 plan」而 spec 的凭证没齐时，收工得到的是
`concluded_by_host` + `target_reached=false` + `target_missing=[...]`。
**那是一条有效观测（模型自认为完成而凭证不齐），不是装置失败**——退出码 0 表达的是
「这次运行没有装置或 CLI 层面的故障」，产物到不到位由 `target_reached` 与
`target_missing` 单独说，评测看那两个。

### 3.6 等你回话没有上限

worker 停在 `awaiting_reply` 会**一直等**，不设时限。它等的不是人的键盘，是**你**
有没有把回复放进去——而你会被别的事打断、会跨会话。此前那道 1 小时的线踩上就静默
break，还被记成 `target_not_reached`，报告上完全看不出是没人回话（实测两个 Case
分别空等 45 分钟与 33 分钟，距那条线只差 15 分钟）。

现在它每 5 分钟发一条 `awaiting_reply_stale` 事件，Case 条目里带 `waited_sec`。
代跑 heartbeat 的脚本据它叫人（§3.1）。等待的唯一另一个出口是 `conclude`。

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
协调器继续测试并在下一轮起跑重试残留。权威状态只来自 `state.json` 和运行事件。
同仓多个会话并存时，状态归属以本会话实际执行命令的 transcript 与状态写入事件为证据，不按消息时间或谁先结束猜测。
典型目录：

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

**阶段闭环证据**：读取当前运行的closure、summary、trace与回执，按当前协议定位verifier报告。历史命名变体只能帮助发现候选文件，文件存在不等于绑定本轮或审查通过。评价时分别记录对象/版本绑定、报告结构结果、实际语义结论；不从一个笼统的PASS推断三者都成立。报告缺失、尚未到审查时点、宿主未启用能力和业务不适用分开说明，是否允许降级按当前已批准政策，不自行改口径。

**为什么停在这里 → 记成什么**。上一版把三件不同的事塞进同一个 `target_not_reached`，
事后分不出是模型没做完、没人回话、还是 CLI 压根没回 session id——而后两种不是被测
对象的账。现在一一对应：

| `stop_reason` | 终态 | 退出码 | 谁的账 |
|---|---|---|---|
| `target_reached` | `finished` | 0 | 自然到达 |
| `host_concluded`（且已闭环） | `finished` | 0 | 宿主收工，目标也到了 |
| `host_concluded`（未闭环） | `concluded_by_host` | **0** | 宿主判定到此为止——**不是失败**，见 §3.5 |
| （无，自然结束而产物不齐） | `target_not_reached` | 1 | **模型真没做完**，只剩这一种 |
| `cli_cannot_continue` | `cli_failed` | 1 | CLI 层失败（凭据被拒等） |
| `no_session_id` | `cli_session_lost` | 2 | adapter 回了 succeeded 却没给 session id |
| 内容审查第二次拒绝 | `content_policy_rejected` | 1 | 单 Case 的同配置重跑额度耗尽 |
| 配置组全部鉴权失败 | `cli_config_exhausted` | 1 | 当前 suite 无可用 CLI 配置 |

另外两个与被测能力无关的终态：`harness_incomplete`（退出码 2）= **装置自己漏跑了 gate**
（gate 判红是被测对象的账，没跑是装置的账，两件事分开）；`worker_lost` = 进程真的不在了。

退出码表达的是「**这次运行有没有装置或 CLI 层面的故障**」，不是「被测做得好不好」——
后者看 `target_reached` 与 `closure.target_missing`。

**本域不设任何时限与轮次上限**：`soft_timeout` / `hard_timeout` / `phase_hard_timeout` /
`max_turns` / `reply_wait_sec` 写进配置会被直接拒绝（`run_case.py` 启动即 `SystemExit`），
防的是「以为还在生效」。真出现 `timed_out` 说明有人把时限重新引进来了，装置会出声告警。

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
python -m pytest test/story/tests -n auto --dist loadscope
python -m pytest tools/cli/tests -n auto --dist loadscope
python -m compileall -q tools/cli test/story/scripts
python -m tools.cli.scripts.validate_clis
python test/story/scripts/run_multi_case.py plan --all --jobs <实际Case数>
python test/story/scripts/check_failure_modes.py
node --check <每个 doc/extensions 下的 .mjs>
```

相关修改先跑有区分力的用例，通过后在完整需求收口运行必要全量；无新改动或疑点不重复刷全量。verifier通道见§7.0，真实smoke见§7.0.1。跳过/预期失败按当前用例声明与实际输出逐项说明，不在本指南固定失败数量。

这些命令不启动真实被测 CLI，只检查接口、状态转换、清理预检、稳定观测和确定性规则。

### 7.0 verifier 通道（OpenCode）

opencode 的 verifier 子代理定义物化在 `.opencode/agent/verifier.md`；报告由派它的那个
agent 原样写到 `summary.verifier_report`，没有发布器这一环。两条命令都不启动真实 CLI：

```powershell
python -m unittest discover -s test/story/tests -p "test_verifier_chain_in_workspace.py"
npx ts-node scripts/check-adapter-catalog-consistency.ts --framework-root <仓根>\framework   # 在 framework/harness 下跑
```

第一条核工作区带没带上子代理定义与作者入口、定义说的是不是当前这一版协议；
第二条走 `framework/harness/node_modules/ts-node`。

### 7.0.1 verifier smoke（真实 CLI，独立于 Story）

`test/story/verifier-smoke/` 用一个固定小需求跑到 spec 闭环，验证 verifier 链路。
它**不在 `cases/*` 里、不进 `--all`**，跑它不影响 Story Case 的发现与统计。

```powershell
python test/story/verifier-smoke/run_smoke.py build  --workspace <隔离目录> --force
python test/story/verifier-smoke/run_smoke.py run    --workspace <隔离目录> `
  --cli-config bailian-deepseek --evidence <隔离目录>\smoke-evidence.json
python test/story/verifier-smoke/run_smoke.py verify  --workspace <隔离目录>
```

`build` 会调真正的 init 物化 `.opencode/`；工程是合成的最小 `generic` 工程，**不挂 Extension**，
架构/画像/术语表在 `fixture/doc/`。

**两个结论分开记**，不能混成一句「smoke 过了」：**A 链路**（`verify` 的逐项绑定检查 + receipt 闭环，
脚本判）与 **B 语义**（verifier 是否真读了需求与 spec、判断是否与产物相关，人看那份报告 MD）。
链路通不等于审查有效。**结论只绑实际跑的 `cli_config_id`**，不外推到别的宿主或模型。

三条现场纪律：

- `harness-runner.ts` **没有** `--project-root`，它按自身位置解析工程根。阶段门禁由被测模型在
  workspace 内自己跑；**别在主工程跑它**——跑了会把报告写进主仓、还会误建 `doc/features/<feature>/`。
- 确认按 `confirmation-registry.yaml` 的 portable 菜单文案匹配（`fixture/replies.yaml`），
  **不按轮次序号**。没有条目命中就停等报 `unknown_question`，不盲答。
- `spec.feature_path` 冲突、以及 verifier request 生成前的 Research / 术语 / track / 冻结门 BLOCKER，
  一律归 `environment_or_fixture_failed`：修夹具或环境后重跑，**不算被测对象的账**，也不在驱动里绕过门禁。

离线判据（不启动 CLI）：

```powershell
python -m unittest discover -s test/story/tests -p "test_verifier_smoke.py"
```

### 7.0.2 作者起手通道

```powershell
python -m unittest discover -s test/story/tests -p "test_author_context_entry.py"
node doc/extensions/hooks/spec/author.mjs --feature <feature>
```

第二条是消费模型在动笔前跑的那一条，维护侧手查通道时也用它。
各阶段的原则页是 `doc/extensions/hooks/<phase>/author.md`，作者按 SKILL、
CLAUDE.md 扩展段与 `story_flow.py status` 的下一步文本去取。
**非零退出码 = 取不全**，不是「没有要求」：缺 `--feature` 退 2，章节合同读不到退 1。

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

本节是机制层负面扫描命令的唯一维护位置。提交前固定运行；前四项检查知识/工程标识与绝对路径，
第五项检查交付面是否混入维护历史：

```powershell
rg -n '\b[A-Z]{2,8}-[0-9]{2}\b' doc/extensions -g '!doc/extensions/knowledge/**'
rg -n '\b(AR|DTS|ISSUE)-?[0-9]{4,}\b' doc/extensions -g '!doc/extensions/knowledge/**'
rg -n '\b0[1-9]-[A-Z][A-Za-z]{3,}\b' doc/extensions -g '!doc/extensions/knowledge/**'
rg -n '[A-Za-z]:[\\/]|\bbackup/' doc/extensions
rg -n '实测[^。]{0,40}[0-9]|首跑 [0-9]|批次 *[0-9]|上一轮那|F[0-9]+ (首版|实测)' doc/extensions -g '!doc/extensions/knowledge/**'
```

扫描面包含 Markdown、提示词、注释、docstring 和合同说明；这些内容都会进入消费模型上下文，按交付物处理。
业务词不在命令中维护固定清单，由 M02 从当前 Case 动态派生。

人工快查会有噪声（占位形态、反例说明、激活清单本身都会命中），准确判定以
`check_failure_modes.py` 的 M01/M17 为准：它们的基准从激活清单派生，
能区分「真实标识」「占位形态」「查无此物的死判据」三种情况。

### 7.3 维护不变量的机械回归

以下机械回归覆盖维护不变量的可确定部分；未命中不证明语义通用性或架构合理，仍按AGENTS第5.3节做过拟合与职责审视：

| 不变量 | 台账形态 |
|---|---|
| 机制层零测试特征（反过拟合） | M02（从 Case 目录动态提取业务词） |
| 机制层不硬编码 knowledge 内容 | M01（真实标识）+ M17（查无此物的死判据） |
| 正向实现，不打补丁 | M16（死代码 / 静默降级 / 待办标记） |
| 知识不含维护信息、定位只写一处 | M18（facts 引规约编号 / 知识指向机制 / 规约带源码路径 / 阶段矩阵；经真实 `selfCheck`） |

## 7.9 离线回归怎么跑

```powershell
python -m pytest test/story/tests -n auto --dist loadscope   # 默认：并行
python -m pytest test/story/tests -n auto --dist loadscope -q --durations 10  # 并行并查看慢项
python -m unittest discover test/story/tests         # 只在排障时用：串行、输出线性
```

**默认并行**。测试彼此隔离是本域的既有约束，不是并行带来的新要求——并行只是让违反它的
地方立刻现形（写到共享路径的那条会当场撞车，而串行下它一直是绿的）。三条规约：

- **每条测试只写自己的临时目录**。落到 `%TEMP%` 下固定名字的路径不算「自己的」——
  几个 worker 会撞同一条；要带上进程号或用 `TemporaryDirectory`。
- **重夹具一个类建一次**（`setUpClass`）。工作区模板这类要复制整棵工程树的夹具，
  一条用例建一次就够整轮跑的时间翻倍。并行时加 `--dist loadscope`：同一个类的用例
  落到同一个 worker，那份夹具才真的只建一次（默认的 `load` 按用例散开，
  拿到该类用例的每个 worker 都会各建一份）。
- **慢的要报出来**：`--durations 10` 看最慢十条；单条超过 5 秒，要么让它快，
  要么在测试文档字符串里写明它为什么必须慢。

## 8. 实跑效率度量

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
| 7 | `doc/extensions` 非知识层**代码行**（注释与空行不计） | 由 `regression/mechanism-budget.yaml` 的当前峰值/完成上限执行（`test_mechanism_budget.py`）；阶段边界按AGENTS §7.5区分。**配额限的是机制规模不是文字长短**：注释算进去，省下来的只会是解释；逐类怎么剥注释见预算文件头部 | 新口径基线 8116 |

上表前六项目标保留为诊断参照，不自动换算为质量分、重试次数或输入截断阈值；第7项按当前签定预算执行。历史规模方向及旧计数不作为新需求的现值，新增/退出职责和实际规模按AGENTS §7.5说明。

**读数口径**：第 2、3 项只看工具**入参**（读了什么）——**含 bash 里的读**
（`cat` / `sed` / `grep`，以及 `node -e "readFileSync(...)"`：一轮实跑读判据脚本 68 次
全走最后这一种，而当时的口径只认前几种，报表上写着 0）；
第 3 项的对象含 framework 的 `check-*.ts` 与**扩展自己的判据脚本**（`hooks/`、`skills/` 下的
`.mjs`/`.py`），不含知识层——读知识是正当的。第 4 项只看工具**输出**（门禁报了什么），
同一 check id 按**门禁轮次**去重——一份报告被 console 打一次、又被 `cat` 一次不算两轮。

三个字段：`gate_rounds_with_fail`（有 FAIL 的门禁轮次）、`gap_sec_by_kind`
（门禁 / verifier / 成文 / 其它的时间去向，**是按事件间隔归属的近似值**——事件流里没有工具开始
事件，拿不到真实 span，字段名如实标注）、`human_wait_sec`（**由驱动器累计**，与模型耗时分开；
读不到时报 `null` 而不是 0——「这轮没人等过」和「这份记录里没这个字段」是两件事）。

**第 3 项是调查信号，不单独下结论**：记录作者为何读取 checker、读取后做了什么，并与产物结果、性能、Knowledge 应用
及跨 Case/配置的重复情况一起判断。为学习隐藏验收条件而反向读源码、随后只迎合字段/关键词，通常指向作者信息或门禁设计问题；
为定位明确脚本内部错误而读取，不能据此判通道失效。最终评价按 §10 由维护者呈现证据、用户确认。

第5项按本次实际执行体和阶段取值，说明input/output/cache/context字段的含义与累计方式。run_id变化不证明上下文重置，上下文大小不证明是否派过独立作者；无法取得的轨迹标未知。第6项分开记录装配内容和消费模型实际收到的内容，字节不直接当token。耗时拆分要标工具时间、事件间隔估计或人工等待，扣除故障后的估算不是修复后的实测。

## 8.1 从证据还原行为

评价在finalize之后，以保留的events、runlog、版本对应的输入/产物和报告为依据；不修改原件补证据。一次工具事件含多条命令时读完整入参，不能只看开头；读取命令、offset/limit、管道截断和实际返回一起核对。

| 要判断什么 | 可支持的证据 | 不能替代它的东西 |
|---|---|---|
| 机制能生成要求 | 源码、离线输出或装配结果 | 不能据此推定运行时已送达 |
| 要求实际送达 | 当前工具完整输入、返回、读取范围及分页/截断情况 | 文件存在、hook返回过、统计读了几次 |
| 执行了相关工作 | 实际编辑、调用、比较对象和产物变化 | “已认真检查”等自述，或仅列章名 |
| 内容正确 | 原始义务、已确认决策与成品对照，真实问题是否消除 | 原生门禁绿、来源ID齐、与模板一致 |
| 审查有效 | 实际缺陷与报告发现对应，对象版本一致 | 报告结构PASS、来源列表、猜测子代理读完 |

先找最早偏离点，再区分输入/职责错误、执行偏离、语义判断、机械误判和外部故障。多个原因可同时存在；没有内层代理轨迹时不推定内部行为。报告中分别写观察事实、解释假设与待验证项，成功概率和因果关系不能由单轮表现推导。

## 9. 可选的审查故障诊断

只有真实产物与审查结论明显不符、且普通证据还原不足以定位原因时，才讨论专项诊断。它不是每轮必跑项、配置资格门或正式评分的替代；涉及真实CLI/模型调用仍须用户启动或明确授权。

先保留原稿，明确待定位的是来源遗漏、对象送达、报告解析还是语义判断；优先在独立临时副本上复现具体问题，不触碰原运行状态。构造反例可验证确定性判据或定位特定症状，不能证明模型在未知需求上的判断力。

### 9.1 现有诊断器材（条件使用）

需要定位时复用以下工具，不新建评测平台；参数先查当前入口帮助。工具名中的qualification不代表已启用准入门禁。

```powershell
python test/story/scripts/make_narrative_variants.py --list
python test/story/scripts/make_narrative_variants.py --out <独立临时目录>
# 以下会调用模型，只有获得本次诊断授权后运行
python test/story/scripts/run_review_qualification.py --config <当前配置> --out <独立输出目录>
```

以当前index给出的变体及预期为准，不在操作协议固定族数或删几条事实。保留输入改动、配置、输出原文和实际发现的位置；非空blocking_findings只是可计算现象，是否找对缺陷仍由维护者核对。同义表达的误报、样本通过或漏报只说明这次诊断现象，不自动判全部历史审查可信/无效，也不据此选择性省略正式验收。

正式效果仍由正常需求的实际运行按§10评价。已退场的逐字覆盖、裁决表、发布器及阶段假设不恢复为义务；历史追溯查EVOLUTION、当时方案及Git。

## 10. Story init 三轴评分与演进基线

每次获准运行真实 Story init 后及时评分。评分对象是该次运行的完整结果与过程，不强调“首轮”，也不把分章落盘、
中断恢复或 verifier 修订次数本身当成质量结论。

评价范围来自本轮已确认目标及需要保持的原有能力，不能只收集新功能或最后一条报错。区分首次成文、实际返修与最终结果：改进项是否变好，其它关键事实/关系是否保持，是否通过删内容、改范围或降低要求取得通过。方法缺陷归维护层处理，不把每次波动都解释成模型忘记。

### 10.1 三项独立评分

| 评分项 | 评价对象 | 主要证据 |
|---|---|---|
| 产物结果 | `story.md + review.md` 作为一组评审载体 | 已确认范围与原始材料、最终 decisions、金样的形似/神似、verifier 与人工审阅 |
| 性能 | 从 Story init 开始到可交付结果的完整过程 | 总墙钟、作者/脚本/verifier/返修耗时、循环次数、上下文增长、规则与 checker 读取；人工等待和外部故障单列 |
| Knowledge 应用 | 适用知识在本次需求中的消费结果 | 看到、理解、应用、传递四段证据；使用确有适用知识的 Case，不能用零命中取得高分 |

三项各 100 分，不计算加权总分，也不允许互相补偿：

- `90–100`：达到目标；
- `70–89`：未达目标，记录主要缺口并继续分析、优化；
- `<70`：本次测试失败，回对应所有者定位方案或实现问题。

代表性测试的三项分数均达到90、且经用户确认后，才能宣布达到评分目标。单次偶然高分不能替代多个实际结果的趋势；单次70–89不直接证明整个系统失败，但不能用其它高分掩盖。已经结束的轮次保持其用户裁定，后续结果进入新轮次评价，不追溯改写旧交付状态。

### 10.2 评分锚

**产物结果**：高分表示 Story/Review 在范围内完整、正确、无编造，核心方案、流程、功能、异常、验收与交付的详略符合实际需求，
决策已定/未定清楚，图文与章节形态便于评审。可用但存在明显遗漏、详略失衡或 Review 决策负担时落入 70–89；关键内容大量缺失、
矛盾、编造或无法评审时低于 70。字数、表格数、图片数和小节数不直接计分。

**性能**：高分表示主要工作时间接近期望、检查与返修聚焦、上下文和源码读取与任务规模相称；完成了但存在明显重复检查、无效读取、
上下文膨胀或远离期望耗时时落入 70–89；由 Agent 系统造成的多小时反复撞门、错误不收敛或主要时间耗在学习隐藏规则上时低于 70。
半小时是期望值，不按单一墙钟自动换算分数；人工等待和外部服务故障不归责于 Extension 性能，但必须如实展示。

**Knowledge 应用**：高分要求适用知识在正确时机进入正确执行体，结合当前需求形成判断，改变具体产物/决策，并由下游取得；链路成立
但个别判断或落点较弱时落入 70–89；知识没被看到、只回显名称/原文、关键适用项漏判或无法传给下游时低于 70。

### 10.3 证据、建议分与用户确认

1. 脚本只采集时间、轮次、上下文、文件和事件等原始事实，不自动给最终质量分；
2. verifier 提供遗漏、编造、表达质量和 Knowledge 应用的语义证据，不拥有最终评分权；
3. 维护者按证据来源、扣分原因和不确定项，向用户呈现三项建议分；
4. 用户确认或调整每项分数及是否达标；调整结果与理由一起记录；
5. 未经用户确认的建议分不得写成最终分数，也不得据此宣布批次或 Extension 达标。

每次测试在该 run 的 `evaluation/scorecard.md` 记录原始证据、建议分和用户确认状态；用户确认后，把最终三项分数同步到当前批次的
评审报告或 STATUS。记录至少包含评分协议版本、Case、宿主/模型配置、产物版本、三项建议分、扣分证据、用户确认分与确认时间。

### 10.4 晋升为长期基线

本节协议版本为 `story-init-score@1`。将用户确认的评分量表、代表性测试结果及其适用Case/宿主配置写入受版本管理的
`test/story/baselines/story-init-quality.md`，成为后续 Extension 演进基线。后续真实测试继续按三项独立评分：既比较已冻结基线，
也观察多次结果趋势。修改量表、阈值或基线样本须先向用户说明原因并取得确认，不能为让新版本过线而静默改口径。

### 10.5 跨轮比较与稳定性

比较前核对实际机制版本、宿主/模型配置、原材料、确认范围、交互与干预、结束阶段及产物版本。相同条件的独立重复可提供稳定性证据；不同条件的历史结果只提供线索，不能把所有改善归功于最近改动，或把所有下降归咎于模型随机性。

按本轮方案与用户授权安排重复运行及不同场景，不因本节自动启动测试。少量重复通过不转换为高成功概率；同时看最差一轮与关键缺陷，不只看平均分。具体措辞、合理分节或图表形态可以变化；业务约束、关键关系与未决边界应保持。

每轮在原有报告中并列记录：本轮目标的变化、非重点能力的变化、成本变化与证据缺口。重点核“优化A是否损害B”：减少重复时是否丢条件，图变丰富时是否丢验收责任，模板更完整时是否限制必要深化。来源不再适用的旧内容不能为保持一致强行继承。

历史检索先查output中的artifact与保留记录，再查已登记的feature备份和基线位置；当前doc/features只是某次回灌，不等于所有历史。列来源路径、内容摘要和可比条件，同文副本去重，保存时间不冒充生成时间。找不到的证据标不可比，不根据目录为空直接断言某步未执行。被长期评价引用的材料须有明确保留位置；下一轮清理会移除的目录不能当永久档案，按既有归档方式保留必要证据，不新建影子历史库。

### 10.6 金样与开放的表达空间

金样入口为 [golden/README.md](golden/README.md)。使用前核用户认可的用途、版本与尚未确定的业务口径，区分效果对照、已冻结业务结论和已经批准的机器否决锚；三者不自动互相升级。

对比金样评价需求是否完整准确、关系是否清楚、形式是否适合、责任与交付是否可判断，不要求同名小节、同字数、同图表数或同句式。模板金样保存已有依据与待解释问题，不要求消费模型在成文前预定全部答案；正文中有依据的新增解释不因模板没列而判错。

从成品反推的模板能说明期望，不能证明模型能从原材料正向生成。金样、历史优点与维护分析留在评价域，不进入被测Case作为答案。旧稿中的好形式与错误业务结论须分开取舍，不能把所有旧段落拼成更大的固定模板。
