# 第一批：usage 幂等、stats 直接成文与装置小修——实施交回

2026-10-21，维护实施者。**已实施，等待第一批集中评审。** 依据 [02](../02-usage采集与结算修正.md)、[03](../03-测试装置与证据修正.md)、[99](../99-预算与执行接续.md)。没有调用模型，没有起跑真实 CLI，没有发布或推送。

**开工身份**：HEAD `7a6b1e2d`。工作区里原有的在途改动都保留了：
- Case Git 边界（`run_multi_case.py`、`run_case.py` 注释、`TEST.md`、两个测试文件，见 [Git 边界交回](2026-10-21-Case工作区Git边界-实施交回.md)）；
- 设计者对 00/01/02/03/04/06/99、spec 00/05/08/11、`mechanism-budget.yaml` 的修改；
- 未跟踪的 `doc/spec/1.10.0/`、`.playwright-mcp/`、`04-稳定性与性能分析/data/golden/`。

本批在 Git 边界已改的 `run_multi_case.py`、`TEST.md`、`test_multi_case_cli.py` 上继续加改，没有回退或覆盖其中任何一处。

证据目录：`output/evidence/1.9.9-batch1-usage-replay-20261021/`（`sequence.md`、逐步 `facts.json`/`commands.json`/`usage.json`/`summary.json`、`budget.json`）。重放驱动与计量脚本在该目录 `scripts/`（原在 `output/scratch/batch1-usage/`）。

## 1. usage：同对象重提交与同内容重登不再清空耗时

| 位置 | 新承担者 | 退出 / 保持 |
|---|---|---|
| `flow/phase_facts.py::event` | 事件 `id` 只由来源、终态类型和原生对象身份组成，`ended_at` 只用于计时。新增 `utc()` 统一时区写法 | 退出「结束时刻进 id」：重跑 harness 只刷新闭环时刻，不再被当成新完成 |
| `phase_facts.closure_event` | 对象身份用 `verifier_subject_id`。依据：Framework `verifier-request.ts::canonicalRequestInput` 由审查材料 sha 和门禁集指纹派生 subject，并明确排除 `source_commit_sha`/`worktree_digest`。<br>没有 subject（该阶段未启用审查）时认不出同一对象，闭环时刻放进身份，每次提交都按新终态算 | 不用阶段加路径认同对象，也不用 `worktree_digest`：重放 s4e 改了 spec.md 后它不变 |
| `usage.py::take_terminal` | 与游标同 id、时刻更晚的事件：<br>· 本轮起点之后的，算这一轮的完成，只计一次并清空起点；<br>· 没有起点、或早于起点的，只是原生流程重写了时刻——游标跟到新时刻，完成与耗时不动 | 以下保持不变：<br>· 同刻异 id 的终态记未知；<br>· 多 feature 一律未知；<br>· 早于起点的**新**对象终态记未知；<br>· 无起点的新对象完成成立、耗时未知；<br>· 未知之后不累加 |
| `usage.py::events` 的 update 分支 | 结束时刻显式放进身份，与旧口径等价 | update close/restore 语义保持 |
| `flow/lifecycle.py::cmd_story` | 先记下登记前的 `story_written_at` 和 `story_digests`。完整的 project→number→view→build→check 照跑；成功后五份登记文件的指纹逐份相同，就沿用原登记时刻，有变化才取当前时刻 | 保持：<br>· 作废先行、检查失败不签登记（失败后重登算新登记）；<br>· 不加登记历史；<br>· 基准与路由不变 |
| `story/AGENTS.section.md` | 一句：内容不变时重跑检查或重新登记不会重复计时 | — |
| spec 11 | 设计者已写的幂等口径保持；删去「改动尚待实施」 | — |

**部署后第一次对账**：现存记录里没有旧格式游标，也就不会因 id 公式变化出现假的同刻终态，所以没有加兼容分支。
- 发布版 demo 1.9.8 不含 `usage.py`；
- 维护仓与 demo 都没有 `doc/usage.json`；
- 最近一轮两个 Case 的 `usage.json` 里 `last_result` 全是 null。

**验证**：

单测，`test_usage.py` 新增两条：
1. **同 subject 重跑 harness**：spec 与依附它的 story 的耗时保持，游标跟进，再对账字节不变；早于新起点的重提交不结束新一轮；新起点之后的同 subject 闭环照计（1800→1920）。
2. **新 subject 与无 subject**：新 subject 没有起点记未知；没有 subject 的重提交认不出是同一对象，记未知。

`test_story_update.py` 新增一条：同内容重新登记，时刻不变；改章后重登，时刻更新。

usage 三个测试文件 49 passed，`StoryIsRegisteredAgainAfterChanges` 15 passed。

**变异**：下面三处各改回旧行为，对应新用例都变红：
- 事件 id 带回结束时刻；
- 起点之后的同对象重提交被吞掉；
- 登记一律取当前时刻。

**真实入口重放**（`sequence.md`）：
- **现场**：上一轮 car-key 工作区原样复制；用 `publish_to_demo.py` 装当前开发源；用 `ensure_case_git` 建自有基线，重放全程 `source_commit_sha` 稳定。
- **命令**：harness、check-receipt、spec 作者入口、Story 登记、usage 对账都是真实命令；只有审查报告用结构合法的 PASS 桩。桩只证明结算，不代表独立审查语义通过。

| 步 | 动作 | 结果 |
|---|---|---|
| s1b | 首次闭环 | spec 68143、story 67068 |
| s2 | 同一闭环重复对账 | 字节不变 |
| s3 | 不改业务重跑 harness（committed_at 变、subject 不变） | 两者都保持 |
| s3b | 同内容重新登记 | 登记时刻仍为 08:13:28，story 保持，usage 字节不变 |
| s4a / s4b | 作者入口两次 | 起点保持 |
| s4c | 起点之后同内容重跑 | +10 |
| s4e | 改 spec 后闭环 | +9；story 因 spec 换了新 subject 且没有本轮起点，记未知 |
| s5 | 不经作者入口改 spec | 未知 |
| s6 | 再对账 | 不再累加 |

「早于新起点的同对象重提交」在真实入口里排不出来：begin 先对账，重提交在那时就被吸收了。这一条只有单测覆盖。

## 2. stats：脚本直接生成报告

| 位置 | 新承担者 | 退出 |
|---|---|---|
| `stats.py::render` 及 `md`、`markdown_table` | 读随包模板，组装报告头（`facts.info`）、逐节标题、该节说明、表，以及统计口径。<br>· 首列左对齐，整列数值右对齐（同 spec 样例）；<br>· 数据值里的换行并成空格，`\ ` * _ [ ] < > \|` 加反斜杠；<br>· 模板有脚本不认识的占位或缺 `{{sections}}` 时，报「模板与统计脚本对不上」 | — |
| `stats.py::collect`（main） | 同一锁内写 `facts.json` 与脚本生成的 `report.draft.md`，pending 记两者的 sha256。`raw` 增加 `distribution`（本范围各业务版本的需求数），供总览说明使用 | 退出返回给模型的 `draft`/`template` 路径 |
| `stats.py::publish` | 核 analysis_id、facts 摘要，以及候选报告是否仍是 collect 写下的字节，然后原子发布。续发（已改名为 report.md）、替代拒绝、清理旧输出都保持 | 退出 `outline`、`report_problems`：Markdown 逆解析与逐标题/逐格判定，共 72 行 |
| `templates/report.md` | 报告结构、各节说明（按表 id 一行，`{{requirements}}`/`{{distribution}}` 由脚本填）、五条统计口径，作为组装依据保留。纯字符串替换，不引入模板依赖 | 退出写给模型的抄表指令 |
| `SKILL.md` | collect → publish → 读报告向用户概括，回答只取报告里的数字与口径 | 退出「按模板成文、逐格照抄、按列出的每条改候选再发布」 |
| spec 11 §3、§5 | 写当前实现：候选由脚本生成、pending 记摘要、改过就拒绝；模板由脚本读取 | 退出「模型仅组织报告、由 Skill 引用」 |

**测试迁移**（`test_usage_stats.py`）：

退出（只防模型抄错）：
- 模拟模型成文的 `render`；
- 候选报告 15 种排版负例（10 种命名形态加 5 种缩进：改数、多列、代码块、注释、标题提前等）；
- 模板形态报告过逆解析、两版步骤表互换被拦。

保留 8 条：聚合、分母、版本筛选、环境均值、空范围、裸克隆、快照字节一致、对账这 7 条断言未改；安装入口那条把模板路径断言改为核已安装脚本按随包模板生成了报告。

新增：
- **全版本报告逐项核**：报告头、全部节标题与顺序、各节说明、每张表的表头/对齐/每一行、五条口径、没有注释和占位残留。期望值是按夹具业务数字写出的完整 Markdown，不是拿生成函数的输出比自己；
- **指定版本与空范围**：节序、各自分母，空范围不编时间、环境表只有表头；
- **数据值里有竖线、星号、换行、尖括号**时表格不裂；
- **模板与脚本不对应**时明确报错；
- **发布规则**：
  - 发布的就是 collect 生成的那一份，重复发布幂等；
  - 改过的候选、改过的 facts 都拒绝，上份报告保持；
  - 旧请求被替代时拒绝；
  - 改名后中断可以续发，旧输出被清理。

13 passed。变异：去掉发布摘要核对、去掉转义，各让对应用例变红。

## 3. 装置：取证错误汇总（复核 R1）

`run_multi_case.capture_native_sessions`：
- **未取得的**：缺失、多候选、复制失败（OSError）记进 `not_captured`，其它已取得的会话照常留存。
- **取得但不可信的**：解不开、父头 id/cwd 不符、子头 id 与 catalog 的 childId 不符、parentSession 不符、catalog 条目缺 childId，记进该会话的 `problems`。
- **父头不符时**：不再用它的 catalog 去采子会话，已复制的父会话原字节与摘要保留。
- **整体状态**：任一项不可信都让 `status` 为 `incomplete`。
- **不让取证异常盖住 finalize**：读取器起不来、manifest 写入失败都不外抛，记成 incomplete。

**没有改的**：没有第二份 manifest，没有自动修复，也没有扩展损坏协议矩阵。

**新增用例 2 条**：
1. 子会话三种不可信（坏 zstd、子头 id 不符、parentSession 不符）都判 incomplete，原件逐字节保留，manifest 一致；
2. 外工程父会话不采子级；子会话复制失败时只把它记为未取得，父会话不受连累。

原有两条照过。变异两处（只看父级状态、外父仍采子级）各让对应用例变红。

## 4. 装置：已登记 offline 现场的清理（复核 R2）

`run_multi_case.cleanup_previous_test_runs` 新增 `_registered_workspaces`。

**扫描范围**：输出根 `output/story/*` 与同级 `output/scratch/*` 下一层的 `workspace-boundary.json`。TEST §5 的离线模板登记就在 `output/scratch/<id>/`。

**认领条件**：
- `owner_repo` 是本仓；
- `workspace_root` 正好在 `%TEMP%/sw-story/` 下一层；
- 同一工作区的多份登记合成一个目标，其中任一份归别的仓，就不认领。

**删除范围**：
- 认领后只删登记的工作区，不按名字去配输出目录；
- 进程、链接、路径边界的预检沿用现有那套，删除失败照旧告警后继续；
- 删净后撤掉登记文件；登记处空了一并删除，有别的文件就留着。

**不认领的**（其它仓、读不出归属、登记的工作区在 `sw-story` 之外）列进 `ignored` 并写明原因。story-suite 的认领路径没有改。

**新增用例 2 条**：
1. 下面几种情形一次覆盖：
   - 本仓登记在 scratch、登记处与工作区不同名；
   - 同一工作区在 output 与 scratch 各有一份登记（去重）；
   - 别的仓的登记、一本仓一外仓的混合登记、缺归属的登记、未登记的工作区，都不删；
   - 与工作区同名但没登记的输出目录不删；
   - 登记处另有文件时，只撤登记 json。
2. 登记的现场正被进程使用时，停在 `blocked_orphan_process`，现场和登记都保留。

变异三处（不查登记、按名字配输出、混合归属也认领）各让用例变红。

TEST §1.2 第 2、4 步及「不自动清理」一句、§4.5 原生会话状态含义已同步。

## 5. 回归与检查

| 命令 | 结果 |
|---|---|
| 与改动相关的 38 个测试文件加 `test_mechanism_budget.py`，`-n auto --dist loadscope` | 1478 passed、2 skipped；1 failed，见下 |
| 失败那条 `CaseWorkspaceOwnsItsGitRoot::test_a_git_pointer_or_nested_repo_is_still_refused` 单独复跑 | 3 次都是 5 passed；`test_multi_case_cli.py` 按文件并行 95 passed |
| 按 TEST §5 现建模板 `offline-20261021-100544` 后跑 `check_failure_modes.py` | 61 条 FAIL 0（委派 8、PASS 53） |
| `git diff --check` | 通过 |

那条失败发生在 Git 边界用例里：它写入 `.git` 指针文件、断言之后删除，删除时报 WinError 32（文件被占用）。这段时间里没有 git 子进程，应是全量并行负载下外部程序（扫描或索引）短暂占用。用例属上一项 Git 边界在途改动，我没有改它，如实列出。按 99，两批最终候选再跑一次必要全量。

## 6. 预算（AGENTS §5）

口径同 `test_mechanism_budget`：只计交付范围，剥注释和空行，相对 HEAD 按有效行做差。原始结果见 `budget.json`。

| 段 | 文件 | 实际 G/X | 99 预测 G/X |
|---|---|---:|---:|
| usage | `usage.py` 10/5、`phase_facts.py` 5/3、`lifecycle.py` 4/4、`AGENTS.section.md` 1/1 | **20/13** | 15/15 |
| stats | `stats.py` 51/72、`templates/report.md` 11/11、`SKILL.md` 7/9 | **69/92** | 30/100 |
| 装置 | `run_multi_case.py` 与测试、TEST | 测试域，不计 | 0/0 |
| 合计 | | **G89/X105** | G45/X115 |

**分类总量**：mjs 5218、py 4294、hooks 4464、prompts 2511、data 805，合计 17292（开工时 17308，净 −16）。分类上限与总量检查通过。

**分级**：
- **R8**：累计 1017+89=**1106**，初批分母 1000，R≈**110.6%**，落在 100%—125% 档。下面已自查，可以继续。
- **整版连续账**：约 4875+89=**约 4964**。99 原来预测两批做完是 4963；第一批实际比预测多 44，第二批再按预测 43 算，完成时约 5007。整版本来就超过 150%，它的人工确认覆盖的是「已展示范围」——这个差额要请设计者判断，是否仍在那次确认之内。

**自查（差额来源，不是重复实现或范围扩大）**：
- stats 预测 G30 漏算了成文本身要的几块：
  - 表格渲染、对齐与转义：约 9；
  - 按模板的节说明和占位校验：约 10；
  - 总览说明用的版本分布：4；
  - 发布改成核候选的产物摘要：约 8；
  - 模板是 Markdown，注释与说明块按整行计入：11；
  - SKILL 按新流程改写：7。
- usage 多出的 5 行：`utc()` 辅助、无 subject 回退、游标跟进分支。
- 旧机制已退场：
  - 逆解析 72 行、SKILL 抄表步骤、模板抄表指令，都已删除；
  - 给模型的 draft/template 返回值已退出；
  - 没有新旧两套并存，新增的每一项都有消费者（collect/publish、报告读者、usage 结算）。
- 可以再省的只有两处，我没有删，请设计者裁定：
  - 模板占位校验约 4 行：去掉后模板错配只会在报告里留下 `{{…}}`；
  - 总览说明约 5 行：全版本时版本汇总表已能看出分布。

## 7. 未做与后置

- 真实 CLI 没有跑，按 99 要等两批都完成、并经用户授权。
- usage 的名称/版本理解、真实采集链、stats 由模型向用户概括，这些都要模型产出证据，留到 CLI 阶段验收。
- 真实 DSH profile/model 路由、patch 与资格声明，按 Git 边界交回所说，在获授权的运行里核。
- 本次现建的离线模板 `offline-20261021-100544` 已登记，下一轮起跑时由本批的清理认领删除。我自己建的、未登记的重放现场 `sw-story/s2-replay3` 已删净。

## 8. 交给设计者

1. 第一批集中复核：usage 身份与结算、stats 成文与发布、R1、R2。
2. 预算：R8 在 110.6%，已自查；整版完成时预计约 5007，比 99 原预测多约 44，请判断是否仍在已确认范围内。第 6 节末两处可省的行请裁定。
3. 复核通过后进入第二批（04）。
