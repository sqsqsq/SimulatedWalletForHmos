# 步骤 11 · 集成实跑、73 条收口与旧发现者退场

## 目标

在新作者任务、确定性生成、Knowledge 链、独立 verifier 和测试观测全部集成后，运行一次现有真实 Story，确认新产物没有相对
金样和历史期望退化；通过后才删除旧回归发现者和无消费者资产。

## 实跑顺序（用户 2026-09-03 最终裁定）

批次 5 的 CLI 原定只有一次；首跑（2026-09-04）因环境缺陷不计分，用户裁定改完下节全部内容后**再跑一次**，跑的仍是**正常需求**：

1. **真实 Story**：见下方「实跑选择」；配置从 `test/story/config/test.yaml` 里选，记入 `cli_config_id`，结论只绑该配置；
2. **三轴评分**：按 `TEST.md §10` 由维护者呈证据与建议分，用户确认；审查者的区分力从「用户找到的问题它报没报」里读出，记入报告；
3. **退场**：见「73 条与清理」。

进入本步的前提：步骤 9 第二段与步骤 10 已通过评审。不跑 smoke、不跑合成资格门。

## 首跑结果与二跑前的修正（评审者拟，用户 2026-09-04 裁定纳入本步）

首跑：`story-suite-20260904-091600/auto-topup`，`bailian-deepseek`，91 分钟到 spec 闭环。事实与证据见
`reviews/11-real-run-observation.md`、执行会话的 `11-实跑报告.md`。**首跑不计正式三轴分**：verifier 证据由被测主模型手造
（`agent_id: storiesuite-verifier-stub`），上下文 525K，18 分钟流程死锁靠手改 `story-flow.json` 走出。产物（十章、review、
决策 10 条）留作诊断样本，不进基线。用户裁定：**先改完下列全部内容，再跑一次 CLI**，那一次才计分。

### 一、环境缺陷（回开步骤 1、3 的遗留）

| 编号 | 缺陷 | 改动 | 验收 |
|---|---|---|---|
| E1 | 本仓 `.opencode/` 从未物化 verifier 子代理与发布插件（`reviews/01` 当时记为 advisory） | 按 `framework/agents/opencode/adapter.yaml` 物化 `.opencode/agent/verifier.md` 与 `.opencode/plugin/record-verifier-report.js`（走 framework-init UPDATE 或等价的只读探测 + 落盘）；`.opencode/.gitignore` 不得忽略它们；入库 | 两文件在仓且被 git 跟踪；`framework_integrity` 不报漂移 |
| E2 | 测试工作区不带 `.opencode/`：`run_multi_case.py` 的 `WORKSPACE_ALLOWED_DIRS` 只有产品目录、`framework`、`doc/extensions` | 白名单加 `.opencode`（`node_modules` 已按名排除，opencode 自装依赖） | 工作区模板里有 `.opencode/agent/verifier.md`、`.opencode/plugin/record-verifier-report.js`、`.opencode/skill/story/SKILL.md` |
| E3 | 没有任何离线测试守「工作区带着 verifier 链」 | `tools/cli` 或 `test/story/tests` 加一条静态测试：建模板后断言 E2 那三个文件存在。**不跑模型、不是 smoke** | 测试进全量离线；删掉任一文件即红 |
| E4 | `_state_evidence` 判进程存活只比 pid 号，pid 复用把几天前的 worker 当活的，新 suite 起不来（执行会话首跑前实测） | 判活比进程身份（启动时间或命令行），不只比 pid | 用一个已复用的 pid 造夹具，预检不再报 active |

### 二、机制缺陷（回开步骤 6、8、9；各一个可回退提交，逐个评审）

| 编号 | 缺陷 | 根因 | 改动 | 验收 |
|---|---|---|---|---|
| M1 | `story-build init` 因 `ux-reference/` 有图而无 `README.md` 阻断（合同 `UX.warn_if_siblings`） | 与步骤 6/8 定的「`materials.json` 唯一材料真源、README 不是登记」相悖，是 P13 根因回潮 | 图片来源只认 `materials.json`；`warn_if_siblings` 那一档从 BLOCKER 降为记一笔；README 有则作可选来源读，无则不提 | 夹具：`ux-reference/` 两张图、无 README → `init` 通过并记一笔；`check ④ 图片身份` 仍按 `materials.json` 认图；73 条不变 |
| M2 | `complete` 之后补材料 → digest 变 → `round` 开出新轮 → 新轮无决策而 `decide` 被 `status=complete` 挡 → 死锁 | 轮次边界只看 digest，没有「收口后材料变了」这一态 | `complete` 之后 `round` 不再开轮：只更新当轮 `materials.digest` 并记一笔「收口后材料有变」；要重新决策由人显式发起（新增 `reopen`，或 `decide --reopen`，维护者定一种） | 夹具：`complete` 后改材料再跑 `round` → 无新轮、`status` 仍 `enter_spec`、记一笔可见；`reopen` 后才允许 `decide` |
| M3 | 小节标题重复编号：`### 1.1 1 闸机前的窘境`（39 处里 32 处） | `headings.mjs` 的 `NUMBER_PREFIX` 只剥「带点或分级」的序号，作者写的裸 `1 ` 不剥，`number` 再铺一层 | `NUMBER_PREFIX` 增加「1–2 位裸整数 + 空白」这一形态；4 位数（`2026 年改版`）仍不剥 | `### 1 闸机前的窘境` → `### 1.1 闸机前的窘境`；`### 2026 年改版` 不动；重跑幂等 |

不改的：`check-spec.ts` 的 AC↔F 交叉引用报错没说清期望格式，作者去读了它的源码——那是 framework 判据，记入上游观察，本批不动。

### 三、本步顺序（改后的）

1. 一、二两组改完并逐个评审通过（已通过，见 `reviews/11` §7–§8）；
1b. **预算口径与注释规则**（用户 2026-09-04 裁定，内容见 `reviews/11` §9.2）：预算只数代码行并按 §9.1 重算配额；注释只写当前说明、不写演进史与测试数据，写进 AGENTS；清扫交付面注释并把兜底扩进 M02。一个提交，评审后进下一项；
2. 「73 条与清理」与「预算」节照做：退场、死代码、夹具清理、ceiling 压到 target（压不到按类别列差额交用户裁定，不砍判据）；`requirement.status` 保持 `in_progress`；
3. 全量离线、金样、73 条、E3 静态测试全绿；
4. **CLI 一次**（`auto-topup` 到 spec，配置按 `test.yaml` 现顺序）。**硬条件**：verifier 证据 JSON 必须由插件发布——`agent_id` 不是 stub、`state: published` 来自 `record-verifier-report.js`；首个 verifier 完成事件后若插件未触发，**当场停，不修不重试**，写总结回开步骤 1；
5. 三轴评分由用户确认；通过后 `requirement.status: closed`、建长期基线；
6. 首跑产物保留在 `output/` 原位作诊断样本，不进 `fixtures/`。

### 四、二跑要专门看的（进评分与观察项）

- **签约主路径有没有图**：首跑 story 零 mermaid，主路径写成七步列表，而同一模型在 spec 5.1 已画了流程图——S01「图降级」在真实产物上出现。二跑先看作者画没画；再看 `story_reader_review` 报没报——这是审查者区分力的第一份真实证据（首跑的审查者是 stub，不算）。
- 小节编号（M3 修后应零重复）、`story_reader_review` 结果块两小节形态是否合法（`advisories: []` 后面不该再跟条目）。
- 度量（`measure_run.py`）：`context_total` ≤150K；读 checker 源码 0；同一门禁 id FAIL ≤2 轮；作者读规则文本 ≤20/阶段；总墙钟与半小时期望的差距要能按段解释。
- 首跑里成立、二跑要保持的：`story-src/` 只有三件；§11 生成区被正确使用；判定表与 YAML 一致；`DLV-02` 判评审动作；三张图落在讲它的章。

### 五、预算影响

E1–E4 不在 `doc/extensions`，不计入。M1 净减（去掉 siblings 阻断分支）；M2 小增（记一笔 + `reopen` 入口，估 ≤40 行 `scripts_py`，在 2000 峰值内）；M3 +1 行。
不申请抬任何 ceiling；本步收口时仍按「预算」节压到 target。

## 三跑观察后的修正（用户 2026-09-05 裁定，四跑前完成；证据见 `reviews/11` §13）

story 段停等目标：**两次**——放材料、确认范围。补料之后不再为「确认材料」单独停，只在模型发现**新缺口**时再停。

| 编号 | 改动 | 验收 |
|---|---|---|
| T1 | 材料关卡改为「补料后只在发现新缺口时再停」：`next_step` 对由 `supplement` 开出的新一轮不再要求第二次 `confirm_scope`——补料回话本身就是确认；模型若在新一轮盘点出新缺口，写新的 `gate-options` 侧车再停。SKILL「停等点」节、`init_analysis.md`、用例脚本（`init-wrap-up` 那条改为仅在新缺口时使用）同步 | 夹具：补料后无新缺口 → `status.next` 直接进分析，不出现第二个材料关卡；有新缺口 → 再停一次 |
| T2 | 导入加「只抽图、正文不动」一档，**由模型按材料判断选用，不新增问人的选项**：系统已有同类正文且补料是原稿/参考稿时走这一档，RR 正文不被覆盖 | 夹具：docx 走只抽图档 → 三张图进 `assets/`、RR 字节不变、材料指纹变 |
| T3 | `ar_design_init.md` 第 4 条删「须经用户确认」：S4 生成提取件覆盖预填版，旧版进 `.backup/`，不停 | 全树无「不静默覆盖」停等；`OnlyTwoStopsAndBothUnconditional` 仍绿 |
| T4 | 进 spec 的授权转成 framework 认得的形态：`/story` 启动语义在 SKILL 里明写为「做到 spec 闭环」的 batch 声明，`status` 在 S4 收口时原样回显；或 `complete` 时写 `phase.next_step` 确认——按 framework 契约二选一 | 夹具：收口后 `status.action` 含授权原话；四跑在 spec 入口不问 |
| T5 | **停等消息要简洁明确**：SKILL 加「停等消息格式」——三段固定：一句现状、一句缺口或问题、编号选项各一行（推荐标出）；不放材料总表、不复述已知、不解释流程；上限 12 行。`init_analysis.md`/`scope_gate.md` 里的关卡报告示例按此改写 | 四跑每次停等消息 ≤12 行；用例脚本的回话保持一句话 |

| T6 | 需求方回话只回选项或一句短语（已由评审改入 `TEST.md §3.0` 与三个用例的 `interaction-script.yaml`）；四跑执行会话照此回话 | 四跑每次回话 ≤1 句 |

预算：T1/T2 各 +30 行以内（`story_flow.py`、`import_sources.py`），T3/T5 净减，T4 按所选形态 ≤20 行；属必要增长，reason 写明。

## 实跑选择

默认只运行 `auto-topup` 到 Spec：它同时覆盖需求系统、按需 docx 补料、图片、范围/承载、Story/Review、Knowledge 和 verifier，
且终点早于 `car-key-sharing` 的 Plan，能以较低成本覆盖本批主要风险。若步骤 1～10 出现它不覆盖的高风险事实，由用户决定是否增加
第二个 Case；机制不写死数量。

实跑配置在开始前冻结 `cli_config_id`；优先使用与可比较历史轮次相同的配置。

正式命令、观察和收工方式只按 `TEST.md`。实跑前冻结当前提交、CLI/模型配置、Case 输入和旧发现者状态。

## 实跑验收

### 产物质量

- Story 十章齐备且核心章内容与实际材料复杂度相称，不以空泛短句占位；
- 与金样比较信息架构、详略、表达形态、主叙事/附录分工、图文位置和评审可用性；
- 不要求字数、表格数、图片数或小节数相等；
- Review 来自 Story 后的最终 decisions，未决与已定清楚；
- 范围内关键事实、关系、流程、异常、验收和交付没有明显遗漏或编造。

### Agent 行为

- 作者在动笔前收到任务包，不读 `test/story`、历史方案或 checker 源码；
- 确定性检查不教授首次规则；verifier 来自独立上下文；
- blocker/advisory 分开，返修问题总体收敛；
- Knowledge 三类在正确时机进入并传递；
- 记录作者、脚本、verifier、返修、人工等待、总墙钟和上下文增长。半小时是期望指标，超出不自动失败，但须解释主要耗时。
- 结果只支持所用 `cli_config_id`，不外推到其它宿主/模型。

### 三轴评分与用户确认

- 按 `test/story/TEST.md §10` 分别评价产物结果（Story+Review）、性能和 Knowledge 应用；
- 脚本原始数据与 verifier 结论只作为证据，维护者逐项向用户呈现建议分、扣分原因和不确定项；
- 用户确认或调整三项最终分数。任一项低于 70，本次测试失败；70～89 未达目标并继续优化；三项均至少 90 才达到评分目标；
- 未经用户确认不得宣布步骤 11、批次 5 或 Extension 达标；
- 用户确认批次 5 成功后，将 `story-init-score@1` 量表、实际结果、Case 与宿主配置写入长期基线。

## 73 条与清理

实跑通过后：

1. 对 `failure-modes.yaml` 73 条逐项登记现行责任：deterministic、verifier、generated_by_construction、behavior_test 或 retired；
2. 42 条长期不变量全部有发现者；27 条用新目标重写 form/checker/applicable_when；
3. M08、M12、M15、R04 只有在旧消费者确实消失后，提交 reason 并取得用户批准再标 retired；
4. 删除旧回归 checker、夹具、配置和产品 helper 前再次扫描消费者；
5. `baseline_coverage.py` 若步骤 9 未删则在此删除；
6. 全树检查死代码、静默空集、TODO、悬空引用、双入口和测试特征。

若实跑失败，步骤 11 不修产品：按责任重新打开步骤 5～10，写明最早失效点。修复步骤重新评审并提交后，再重跑本步骤。

## 允许范围

- 实跑证据、度量与本步骤评审报告；
- `failure-modes.yaml`、`check_failure_modes.py`、旧夹具/历史诊断工具的最终清理；
- 仅由清理造成的悬空引用和测试索引修正。

不得在本步改变 Story、Knowledge 或 Framework 业务行为；发现行为问题必须回开原步骤。

## 完成条件

- 真实 Story 的产物质量、Agent 行为、Knowledge 链和 Framework verifier 均通过独立评审；
- 73 条数量对账仍为 73，所有非 retired 条目有现行发现者：确定性的带夹具自检；responsibility 为 verifier / behavior_test 的登记观察方式（真实 Story 里由谁、看什么），不造夹具；
- 纯旧实现条目得到用户批准后才 retired；
- 正式路径不存在 source-units/audit/paraphrase 语义代理、旧入口、长期兼容或无消费者代码；
- 全量离线测试、金样测试、Extension 机制扫描和 Git 范围检查通过；
- 最终报告如实记录未运行的 Case、性能偏差与剩余风险。
- STATUS 明确本仓 D1 验证与上游/内网发布是两个状态；上游尚未合入时不得宣称内网 P3 已解决。
- 三项建议分、用户确认分和确认理由已按 TEST 留痕；只有用户确认三项达标后才创建或更新长期评分基线。

## 预算（对照 `test/story/regression/mechanism-budget.yaml`）

本步是收口：把各类别与总量的 ceiling 压到 target（按 1b 重算后的数字；`semantic_proxy` 0）并全绿，作为完成条件之一。
压不到的类别不改 target 迁就，按类别列出差额与原因交用户裁定：是退场没做完（回开对应步骤），还是 target 定错（用户签字改 target）。
本步自身预计只减不增：删旧回归发现者、无消费者 helper、`baseline_coverage.py` 及其引用。