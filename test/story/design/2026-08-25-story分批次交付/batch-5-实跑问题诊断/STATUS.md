# 批次 5 · 实跑问题诊断 · 进展跟踪

| 项 | 值 |
|---|---|
| 状态 | **步骤 1～5 已通过独立复审（4+5 合审，唯一 blocker 已改）；步骤 4 已提交 `8a8d8a51`，步骤 5 随本次提交。下一步：步骤 6** |
| 输入 | 批次 1～4 全部需求/方案/判据/报告与提交史；F8 局部优化现场；外网 suite `20260901-230253-23468`；内网反馈 |
| 诊断文件 | [00-问题记录与原因分析.md](00-问题记录与原因分析.md)（P1–P16，行为链/所有者/批次分类与实跑证据）<br>[01-四批次全量问题与根因审计.md](01-四批次全量问题与根因审计.md)（两个维护认知根因、十个机制根因、处置边界与方案制定方式）<br>[02-AGENTS重写与信息迁移审计.md](02-AGENTS重写与信息迁移审计.md)（旧内容逐项保留、去重、迁移或退役）<br>[04-失效形态长期要求审计.md](04-失效形态长期要求审计.md)（73 条逐项分为长期不变量、目标迁移、旧实现专属）<br>[06-验收追踪矩阵.md](06-验收追踪矩阵.md)（P1～P16、D1～D12、73 条到步骤的完整对账）<br>[07-方案评审意见.md](07-方案评审意见.md)（独立评审原文及维护者逐项处置）<br>[09-AGENTS维护契约审核.md](09-AGENTS维护契约审核.md)（grill-me Q1～Q18、长期规则修正与三轴评分基线） |
| 决策记录 | [03-方案讨论决策.md](03-方案讨论决策.md)（D1～D11 与 Q1～Q29 共识；D12 不适用） |
| 范围 | 批次 1～4；批次 0 与更早轮次只作根因追溯证据 |
| 方案文件 | [05-实施方案总览.md](05-实施方案总览.md)；`steps/01`～`steps/11` |
| 评审规则 | [reviews/README.md](reviews/README.md)；审核点 A(4+5)、B(6+8)、7、9、10、11，每步仍各自一提交 |

## 步骤状态

| 步骤 | 状态 | 评审报告 |
|---|---|---|
| 1 OpenCode verifier adapter | **通过** | [reviews/01-opencode-verifier-adapter.md](reviews/01-opencode-verifier-adapter.md) |
| 2 OpenCode verifier Spec smoke | **已实施（装置）；实跑待验证** | [reviews/02-opencode-verifier-smoke.md](reviews/02-opencode-verifier-smoke.md) |
| 3 测试观测与效率事实 | **通过**；返修已做：`TEST.md` 三处失效的 `--isolated-workspaces` 已删（`80f5cc3e`） | [reviews/03-test-observation-truth.md](reviews/03-test-observation-truth.md) |
| 4 Framework 作者上下文入口 | **通过**；已提交 `8a8d8a51`（framework + config + TEST），交接件 `artifacts/04-*` 随步骤 5 提交 | [reviews/04-05-author-context-channel.md](reviews/04-05-author-context-channel.md) |
| 5 Extension 六阶段作者入口 | **通过**；本次提交（扩展 + 入口文件 + 测试） | 同上（4+5 合并一份） |
| 6 材料版本与流程状态 SSOT | **通过**（`da35bbb7`、`cb7b7797`） | [reviews/06-08-material-and-deterministic.md](reviews/06-08-material-and-deterministic.md) |
| 7 Story 语义审查资格门 | **装置通过**；资格实跑按 D10 修订撤销，夹具与驱动器留为离线诊断器材，区分力由步骤 11 真实结果观察 | [reviews/07-story-semantic-oracle.md](reviews/07-story-semantic-oracle.md) |
| 8 Story/Review 确定性生成 | **通过**（`4e9a6d21`；两条裁定见评审 §4） | 同上 |
| 9 正向 Story 作者路径切换 | 第一段（按章落盘）与小段 1（换输入模型）已过评审返修；**小段 2（删逐单元判据 + 迁台账）已实施，等待评审**；小段 3 待做 | [reviews/09-story-authoring-cutover.md](reviews/09-story-authoring-cutover.md) |
| 10 三类 Knowledge 消费与传递 | 未开始 | 待生成 |
| 11 集成实跑与旧发现者退场 | 未开始 | 待生成 |

## 事件日志

- 2026-09-02 用户裁定开始批次 5：先记录并分析问题原因，不给方案。
- 2026-09-02 诊断件落盘：11 个问题；P1 定位到「语言红线从材料 token 里切出伪标识 `share`，与形态守恒对图片引用行互斥，
  `material_only` 是唯一不被拦的出口」；P2/P4 定位到「裁决是成文第 ④ 步、同一上下文，opencode 无第二执行体」；
  P3 定位到「opencode adapter 无 verifier 登记，终点 plan 在前两个配置下不可达，五轮都撞到」；P5 定位到三处文本对轮次边界定义相斥；
  P6 定位到提交级（知识写入 11 分钟后代码被删）；P8 定位到度量脚本不读 `tool_output`。当时留下的两项待查证据现已补完。
- 2026-09-02 用户补充外网、内网与 framework 七类现象，诊断扩展为 P1～P16；三路只读调查分别核对
  framework/extension 协作机制、历史需求演进、114 个 extension 提交及补丁地层。
- 2026-09-02 用户明确「四批次」指批次 1～4 的全部历史。新增 `01-四批次全量问题与根因审计.md`：
  分批列出 50 个历史问题点，归并为十个跨批次根因；记录 24 个真实缺陷修复与 30 个“修上一轮修复”的结构事实；
  给出保留、重新定义、不得长期保留三类边界，但不写具体方案。
- 2026-09-02 补完原待查证据：P10 的错误阶段来自 `gates_started` 无条件以 `end_phase` 写 runner hint，
  不是 spec 闭环判断错误；P4 的 93→147 由 93 条既有无效引文与 54 条尚无裁决行同时报告构成。
- 2026-09-02 用户明确 opencode 可以补 verifier，后续方案可把 framework/opencode 能力补齐纳入范围；
  当前仅登记授权事实，尚未修改只读 `framework/` 发布件。
- 2026-09-02 用户纠正知识目标：`knowledge/` 在 Demo 中主要是样板，真实内网仓会按自身事实修正、扩展；
  核心验收不是 Demo 知识内容永久准确，而是知识在合适时机被看到、理解、应用并传给下游。诊断已将 P6 与 RC6
  从「事实自动保鲜」改为「知识消费生命周期未被端到端证明」，`relationalStore` 仅保留为样板漂移旁证。
- 2026-09-02 整体重写 `test/story/AGENTS.md`：以整个 Extension 为维护对象，统一两角色、AI Agent 系统认知、
  Framework/Extension/Knowledge/Adaptation/Test 所有权、Agent-first 设计、知识链和分步独立审查；删除 Case、历史数字、
  命令与实现快照沉积。测试命令在 `TEST.md §7.2` 原权威章节内合并去重；状态归属证据并入 `TEST.md §5`。
  当前 hook 时序的实现事实移入四批次审计，未写成跨版本常驻规则；未修改 `doc/extensions` 或 `framework/`。
- 2026-09-02 按最新 AGENTS 重审批次 5：P1～P16 新增行为链位置、真实所有者和批次 5 分类；新增 MRC1
  「把 Agent 系统当代码产品」与 MRC2「维护者/执行者视角混用」，十个 RC 改为其下的机制根因；清理批次 1 摘要中
  「事实复核」对 Demo 知识准确性的错误导向；冻结独立会话逐步实施、本维护会话独立审查、单步不跑真实 Story、
  按依赖/风险/成本选择少量里程碑实测的方案制定方式。具体技术解决方案仍未制定。
- 2026-09-02 用户确认 D1：独立 verifier 先行，归 Framework adapter 能力，先补 opencode interactive 闭环。
  决策记录明确不能只补 capability YAML；必须交付 request、独立只读执行、可信终稿、报告发布、subject 验真、receipt/closure
  整条链。具体 publisher 由 OpenCode 原生 agent/event smoke 决定；本步骤使用最小 phase 夹具验收，不运行真实 Story，
  不修改 Extension 语义内容或其他 adapter。
- 2026-09-02 用户确认 D2：不能假设执行者会 100% 遵循提示词，也不能因不信任执行者而让脚本代判语义。
  后续方案按风险组合提示词/作者任务包、确定性脚本、独立 verifier、隔离行为测试；各层共享事实、结构和状态真源，
  但不强制所有文字由同一机器 schema 生成。一次成文、少量返修和尽量完整报错是效率目标，不写死成固定次数；
  是否停止依据问题是否收敛。同一认知已写入 `test/story/AGENTS.md §4.3`，作为整个 Extension 的长期维护约束。
- 2026-09-02 用户纠正 D2 初稿的过度理想化：「只允许一次返修」只能是目标，不能写死进机制。专项复核同时修正
  “每项能力四层齐全”“所有内容由单一机器合同生成”“确定性问题必须一次全部发现”“真实 Story 固定两个时点”与
  “脚本直接证明模型理解”等同类表述。现口径为：按风险选择适用控制层；共享事实/结构/状态真源；返修与实跑次数由
  收敛证据、风险、成本和用户授权决定；有限 holdout 只提供泛化证据，不宣称绝对证明。
- 2026-09-02 用户要求除 D3 外先记录其余优化方向。新增 D4～D9：Story 主叙事与确定性内容分工；review 在 Story
  之后由最终 decisions 渲染；逐单元语义证明系统整体退场但保留确定性控制；Knowledge 以消费链为目标；材料、流程、阶段、
  决策和测试状态各有唯一所有者；独立会话分步实施、本维护会话审查、按风险选择里程碑实跑。D1 同时注明其属于既有
  Framework verifier 对 opencode 的能力补齐，不计为批次 5 新增 Framework 功能。本事件时点 D3 尚未确认，后续结论见下一条。
- 2026-09-02 用户将当前运行模式限定为 interactive，并要求写入 `test/story/AGENTS.md`；headless/goal 不进入当前设计、
  实现和验收，未来单独立项。基于该前提确认 D3：不新增生命周期、hook、状态或 adapter 能力，只在 Framework 共享行为规约
  增加阶段起手动作，提供一个复用现有 loader/dispatcher 的只读薄解析器，并删除 harness 末尾错误的 `on_context_load` 调用。
  D3 预计 3～5 个文件、100～250 行实现和测试，数字只作估算，不是验收阈值。
- 2026-09-02 外部模型复核指出新链缺少旧质量锚迁移。核实后修正：半小时改为期望 KPI；D1 原生 OpenCode agent/event
  不成立时直接 blocked，独立进程 provider 另立 Framework 需求；D3 更正为五个 Skill 已读共享行为规约、device-testing 需补入口，
  估算调整为 4～6 文件、100～300 行；D8 明确材料 manifest digest 是唯一轮次边界，初析 hash 不再划轮。
- 2026-09-02 新增 D10～D12：D10 在 D6 前完成 verifier 成对缺陷区分力、73 条失效形态责任迁移和原始材料/金样/质量维度
  三层内容锚；D11 先修 P8/P10、补 P9，并把半小时作为持续观测而非硬门禁。随后用户明确批次 5 目录加入 `.gitignore`
  白名单，方案、步骤文件和逐步评审报告进入版本管理；其他历史 design 目录继续忽略。由于每次 CLI 测试使用独立隔离 workspace，
  不存在上一轮在途 feature 的内部状态迁移，D12 判为不适用，不设计 legacy 分支或兼容机制。
- 2026-09-02 用户明确金样只约束“形似 + 神似”：信息组织、详略、表达形态和评审可用性应达到金样效果，业务内容、字数、
  表格数、图片数和小节数由实际需求决定，不设数量配额。`test/story/golden/` 成为 story、review 与归档图片唯一正本；删除
  design 临时金样及 fixture 中的输出副本，测试直接读取唯一正本，fixture 仅保留构造场景所需的原始输入。
- 2026-09-02 完成 73 条失效形态的实现无关性审查：42 条属于 Extension 长期不变量，27 条的目标长期成立但 form/checker
  必须随新机制迁移，4 条只属于待退场旧实现。分类记录在 `04-失效形态长期要求审计.md`；这一步不等于保留 69 个旧 checker，
  也不等于立即把 4 条改成 retired，实际责任迁移仍是 D6 前置验收项。
- 2026-09-02 完成 Q1～Q29 grill-me。新增冻结内容：D1 获得本工程内修改 Framework 的单步授权，D3 到步骤 4 前重新决策；
  D1 基础设施与语义效果分别判定；Story 保留十章但不设内容数量配额；内容完整性以正向作者任务为主、独立 verifier 为安全网；
  blocker 与 advisory 分离；Plan 不得静默改变 Story 的产品要求；Facts、Constraints、Design patterns 使用不同消费链；Story 完整性
  只覆盖已确认 AR 范围、已定 decisions、范围内事实和 Spec 已成立产品约束。
- 2026-09-02 冻结 D1 低成本真实验证：新增永久独立的 `opencode-verifier-smoke`，直接运行 full Spec，不经过 Story，也不进入
  Story `--all`。固定需求为“隐藏余额”六条规则，无需求系统、补料、图片、人工决策或 Plan；真实 CLI 只验证 OpenCode verifier
  身份、request/subject/report/receipt/closure 和基本语义有效性。
- 2026-09-02 形成 [05-实施方案总览.md](05-实施方案总览.md) 与 11 份步骤文件。步骤 2 是 D1 go/no-go 门；步骤 3～11
  在其后条件生效。另一个会话每次只实施一个步骤，本维护会话在 `reviews/` 写独立报告；通过后按步骤提交。
- 2026-09-02 处置独立方案评审：接受 B1/B3/B4/B5/B6；B2 按用户已定策略改为“本仓验证＋上游可复现补丁＋内网发布状态分离”，
  不把等待上游合入设成本批 D1 blocker。Story 改为任务包一次给全、按章原子落盘和缺章续写；verifier 资格绑定 `cli_config_id`；
  Spec §10/§11 改为 `knowledge-use.yaml` 生成区；非占位仅检查空正文/明确 marker；材料 hash 由唯一 `materials.json` 模块计算。
  A1/A2/A3/A4/A6 已进入对应步骤，A7 经正本图片、零旧路径引用和离线测试核实关闭。方案重新冻结。

## 步骤 1 实施记录（2026-09-02）

**基线** HEAD `e1b73b00`，工作区无用户在途改动。**实跑配置** opencode 1.18.26 +
`bailian/deepseek-v4-flash-0731`（用户指定），对应 `cli_config_id = bailian-deepseek`。

**机制裁决**：opencode 没有 SubagentStop 这一层，但它的 `task` 工具建的是**子会话**，完成时经插件钩子
`tool.execute.after` 一次交出调用入参（= request JSON 原文）、子/主会话 id 与终稿信封。publisher 因此取
机制名 `task_tool_result`，不冒充 `subagent_stop`。transport 复用 `repo_file_request`；subject 派生、
request 契约、报告 JSON、`loadVerifierEvidence`/receipt/closure 全部零改动；物化复用既有的 `hooks` 与
`commands.subagents` 两个通用目录复制字段，未新建物化通道；TypeScript 里未加任何 adapter 名分支。

**改动**（六个 Framework 文件 + 测试域）：`agents/opencode/templates/plugin/record-verifier-report.js`（新增，
发布器）、`agents/opencode/templates/agents/verifier.md`（新增，只读子 agent）、`agents/opencode/adapter.yaml`、
`agents/adapter-schema.yaml`、`agents/README.md`、`harness/scripts/utils/verifier-plan.ts`；
`test/story/tests/test_opencode_verifier_publisher.py`（新增 25 条）、`TEST.md §7.0`、
`test_verifier_report_protocol.py`（只改已过时的「opencode 没有这个钩子」表述）、`framework.config.json`
（6 条具名 drift allowlist，`approved_by: WYK`，rationale 写明上游合入后即失效须删除）。

**两条宿主行为差点让实现静默失效，已处置并各有机械回归**：

1. **终稿截断**——工具输出超 `tool_output` 上限（默认 2000 行 / 51200 字节）会**从头部保留**、全文另存
   `metadata.outputPath`。终态块在末尾，只读可见正文会得到「无终态块」而误判成 verifier 没给结论。
2. **装载器会把每一个导出的函数当插件入口调一遍**（实抓证实）。首版有具名导出，于是
   `publishFromTaskResult(PluginInput)` 抛错、**整个插件注册中断**——第一次真实实跑的现场就是
   「task 跑完了，canonical 和 bedside 都没有」，没有任何报错指向插件。现改为只导出 default。

**验收证据**：
- 能力面三态：opencode `required×interactive` 由 `blocked` → `enabled`；其余 adapter 与其它 policy 态一字未变；
- 25 条发布器回归全过——正例经真实 `loadVerifierEvidence` 接受；主执行者自写、无独立执行体、信封会话不符、
  子任务失败、错 subject、迟到 subject、能力 off、篡改字段、夹带键、追加散文、prompt 换代、prompt 缺失、
  跨 feature/越界路径、缺终态块、双终态块、冲突结论、截断不可恢复——各自落 bedside 且零 canonical；
  幂等与 conflict 单调升级成立；与 TS SSOT 的 subject/规范化串/结论指纹跨实现等值；
- 离线全绿：story 500、cli 18、失效形态 73/73、`check-adapter-catalog-consistency` PASS、
  `framework_integrity` / `framework_foreign_file` / `manifest_selfcheck` / `workspace_tmp_hygiene` 全 PASS
  （allowlist 真人签放行 9 项 = 原有 3 + 本步 6）；机制层负面扫描零命中；
- **真实 CLI 全链**：opencode + deepseek 起一次 spec 审查 → 独立子会话（`agent_id` 是子会话 id、≠ 主会话）
  只读读完 ai-prompt 与 spec 并逐项引证 → 插件发布 canonical → framework 验真面返回 `ok: true`，
  `invocation_subject == result_subject == summary 现值`；运行前后产品源码零差异；
- 上游补丁 `artifacts/01-framework-opencode-verifier.patch` 以 `source_commit 7401f22` 为基线，
  在纯净 framework 树上 `git apply` 通过、结果与本仓逐字节一致（行尾归一，与完整性校验同口径）；
  交接说明见 `artifacts/01-upstream-handoff.md`。

**交付边界**：本仓验证通过 ≠ 内网已获得该能力。上游合入并经 framework-init UPDATE 回本仓前，内网 P3 原样存在，
且那 6 条 allowlist 届时即失效、必须删除。

**顺带发现，未在本步处理**：`TEST.md` §1/§7 的 `run_multi_case.py plan --all --jobs N --isolated-workspaces`
里 `--isolated-workspaces` 已不被脚本接受（`unrecognized arguments`），照抄会直接报错；去掉该参数后 plan 正常。
属步骤 3 测试域范围，本步未改。

## 步骤 2 实施记录（2026-09-02）

**基线** `4334ba5c`。**两项用户裁定**已写回 `steps/02`：工程用**最小合成工程、不挂 Extension**
（本仓 Extension 的 spec post_check 即使跳过 story 判据，§9/§10/§11 三章仍无条件强制，挂上就等于
顺带测了 Extension 的 spec 要求，而那些失败归不到 D1）；`cli_config_id` 用 **`bailian-deepseek`**
（与步骤 1 取得全链实证的宿主一致，不中途换模型）。

**交付**：`test/story/verifier-smoke/`——合成 `generic` 工程夹具（config + architecture/catalog/
glossary）、六条需求 prompt、按 `confirmation-registry.yaml` 的 portable 菜单文案索引的固定回复表、
`run_smoke.py`（build / run / verify）；`test/story/tests/test_verifier_smoke.py` 14 条离线判据；
`TEST.md §7.0.1`。物化走**真正的 init**（`init-orchestrate.ts`），不另写物化器——顺带把步骤 1 的
物化声明从「只读探测通过」加强为「真实 init 落地通过」。

**⚠ 实跑未执行**：用户 2026-09-02 明确「写完 smoke 不进行 CLI 测试，留着，登记待验证（WYK 授权），
并进入下一阶段」。因此：

- 步骤 2 的**结论 A（Framework 能力）与结论 B（语义审查是否有效）均未取得**；
- `steps/03`～`steps/11` 的进入条件「步骤 2 允许继续」是**授权跳过**，不是证据满足；
- 后续引用「D1 已验证」时只能限定为**步骤 1 的探针级全链实证**（opencode 1.18.26 +
  `bailian/deepseek-v4-flash-0731`），不得说成「smoke 已通过」；
- `reviews/01` 的残余 R1「插件注册失败无声」本指望本步覆盖，仍未覆盖。

**恢复方式**：按 `TEST.md §7.0.1` 三条命令跑一次，把 A/B 两个结论分别写回 `reviews/02` 的新轮次小节。

**本步发现并已修复的现场**：调试时把 `harness-runner.ts` 当成接受 `--project-root` 的命令跑了两次
——它不接受该参数、minimist 静默忽略，两次都跑在**主工程**上（覆盖了 gitignored 的
`framework/harness/reports/_global/catalog/`，并误建 `doc/features/hide-balance-toggle/`）。两处已清理，
工作区干净；这条事实已写进驱动文件头与 `TEST.md §7.0.1` 的现场纪律。

**离线全绿**：story 514、失效形态 73/73、`compileall`。

## 步骤 3 实施记录（2026-09-02）

**基线** `49f9ed54`。只改测试域四个文件，Framework / Extension / 产品源码一字未动。

**P8 的根因比诊断记录的深一层，是两处同时坏**：`_text_of` 完全没读 `tool_output`；且 check id
正则写成 `<id> FAIL`，而真实控制台输出是 `FAIL [BLOCKER] <id>`——**方向相反**。叠加结果是
「反复 FAIL 的 check」在任何真实事件流上恒为空，读起来像「没有反复失败」。现在拆成
`_request_text`（作者要什么，路径类判定只看它）与 `_output_text`（工具回了什么，门禁结论只看它），
并按**门禁轮次**去重。回读历史轮次立刻兑现：`verifier_provider_unavailable` 失败 5 轮、
`lifecycle_hook_post_check_extension` 4 轮、`feature_to_acceptance` 4 轮、读 checker 源码 1 次、
上下文 11.7K→584K——这些数此前一个都读不出来。

**P10**：`refresh_worker_lease(phase=...)` 把参数无条件写成 `current_phase` /
`highest_phase_reached` / `phase_source="runner_hint"`，而三个调用点传的分别是起跑阶段、下一个
未闭环阶段、`gates_started` 时的 **`end_phase`（本轮目标）**——没有一个是「模型到了哪」的证据。
现改为只写 `phase_intent` 留痕；阶段一律由 `derive_phase_state` 从 framework 状态与真实产物推导。
`observe.py` / `phase_state.py` 未改——推导本就只认证据，坏的是喂给它的 hint。

**人工等待独立计时**：驱动器在等待循环里累计 `human_wait_sec` / `human_wait_events`；度量侧只读，
读不到报 `null` 而不是 0。新增 `gate_rounds_with_fail` 与 `gap_sec_by_kind`（门禁/verifier/成文/其它，
**按事件间隔归属的近似值**——事件流里没有工具开始事件，拿不到真实 span，字段名如实标注）。

**P9 判为责任错位，外送步骤 6**：按 `TEST.md §2.2`，图片进来只有一条路——docx 内嵌、导入时抽出、
落 `<feature>/assets/<stem>/`；而 `material_inputs` 只覆盖 RR/SR/AR 四份文本与 `ux-reference/`。
**实证**：`assets/` 下加一张图，`material_fingerprint` 一字不变，「只补图片」对轮次完全隐形。
修它要改 Extension 的材料版本定义（步骤 6 的 material manifest 单一真源），`steps/03` 明令此时
停下回报。缺口以 `unittest.expectedFailure` 钉成机械事实：步骤 6 落地后它会意外通过、
unittest 报错，逼着摘标记，忘不掉。

**顺带修正一条既有测试的旧契约**：`test_heartbeat_renews_the_lease_atomically` 原先断言
`phase="plan"` 会写进 `last_phase`——那正是 P10 的病。改为断言新规则，原主题（心跳/租约原子性）未动。

**离线全绿**：story 538（含 1 条 expectedFailure = P9 缺口标记）、cli 18、失效形态 73/73。

**下一步**：`steps/04` 有授权门——用户只授权了步骤 1；步骤 4 开始前须重新取得是否允许在本工程
修改 `framework/` 的明确决定，未获授权即为「阻塞」。
- 2026-09-03 独立评审者（Claude）复审步骤 1～3：步骤 1、2 结论与自审一致（步骤 2 为装置通过、A/B 未取得）；步骤 3 通过并附返修
  （`TEST.md` 三处失效参数）。复审结论追加在各 `reviews/0N` 末尾。主仓残留待清理：`framework/harness/state/last-verifier-report.*`、
  `framework/harness/reports/_global/catalog`。
- 2026-09-03 评审者按 25 次实跑的 author.md 读取时序核实步骤 4 的必要性（spec 14/16 写前读到，plan 3/3 与 coding 1/1 写后才读），
  判定步骤 4 的五处 Framework 改动必要且最小；建议并落盘：留痕借用既有 `context_exploration_inputs_coverage` 门禁
  （extension overlay 的 `exploration_thresholds.phase_input_snippets_extra` 声明 author 钩子路径），Framework 零新增门禁与状态。
  `steps/04`、`steps/05` 已按此更新。**用户 2026-09-03 授权步骤 4 在本工程修改 `framework/`**，纪律同步骤 1（具名 allowlist 带失效条件、上游补丁与交接件）。


## 步骤 4+5 实施记录（2026-09-03）

**授权**：用户 2026-09-03 明确授权本步在当前工程直接修改 vendored `framework/`，范围 = `steps/04`
允许范围；纪律同步骤 1（只为实际修改的文件加真人具名 allowlist、写明失效条件、产出上游补丁）。
用户同时指示本轮 4、5 一起做完再等评审。

**基线** `80f5cc3e`。先清了评审提的两项：`TEST.md` 三处 `--isolated-workspaces`（参数已退场，
隔离是唯一形态）；主仓遗留的 `last-verifier-report.*` 与误跑留下的 `reports/_global/catalog`。
交接件数字 24/499 → 25/500 同步订正。

**病根**：`on_context_load` 一直能产出片段，但全仓唯一调用点在 `harness-runner.ts` 的 verifier
装配处——**通道存在、接错了对象**。片段只进 verifier 上下文，作者一次也看不到。25 次实跑里
plan 到达 3 次全部先写完 `plan.md` 再读作者要求（晚 2～70 分钟），coding 到达 1 次先改代码后读；
spec 正常是因为 `/story` 链自己指向了它，不是机制在起作用。

**改法（零新增机制）**：新增只读入口 `harness/scripts/author-context.ts`（复用 `loadResolvedProfile`
+ `dispatchLifecycleHooks`，顺序与 harness 内部一致）；六个 feature Skill 共用
`agent-behavioral-principles.md` 的**约束 0**（device-testing 补上缺失引用，原本 6 缺 1）；
删掉 harness 里那个错误的后置调用；manifest 六个 phase 登记现有 `author.md`（**author 正文一字未动**）；
五份 overlay 声明 author 钩子路径为既有门禁 `context_exploration_inputs_coverage` 的必需片段。
没有新生命周期、新 hook 事件、新状态、新门禁、新 adapter 能力。

**一处全局裁决**：片段来源标识由**文件名**改为**仓内相对路径**。六个阶段的钩子都叫 `author.md`，
只写 basename 时六份标识一模一样——既指不出阶段，也没法被 `key_inputs_read` 逐字覆盖（门禁做子串
匹配，`author.md` 会命中任何阶段，等于不设防）。已确认全仓无程序解析该标识。

**A05 抓到一次真实疏漏**：先只改了 `CLAUDE.md`，仓根给 codex/opencode 用的 `AGENTS.md` 没同步，
`A05-entry-misses-section` 立刻 FAIL——这条形态正是为此而设，按设计工作了。

**验收**：13 条行为回归（六阶段各取到自己那一份、标识是相对路径而非文件名、互不串台、无扩展→空且
零失败、钩子抛错→明确失败不降级为空、入口无写操作、harness 不再发 `on_context_load`、声明字符串与
入口标识逐字一致、testing 无门禁如实不声明、author 正文全仓仅一份、入口文件不再逐阶段传输）；
离线全绿 story 551 / cli 18 / 失效形态 73/73 / 完整性四项（allowlist 放行 21 = 3 + 6 + 12）；
上游补丁 `artifacts/04-*` 在 `source_commit` 基线上 apply 通过、逐字节一致。

**仍未证的一条**：执行者会不会**真的**在动笔前跑那一条，只有真实实跑能看到。本轮交付的是通道与
机械留痕，不是行为证据；在步骤 11 读到数之前，不要说「A03/A05 已解决」。

## 步骤 4+5 评审处置与全批校准（2026-09-03）

**评审结论**：`reviews/04-05-author-context-channel.md` §7 判「不通过（仅一项，交付面文案）」。
全批校准见 [08-批次5校准.md](08-批次5校准.md)：12 条 AGENTS 条款核为未偏离，5 条偏离（X1～X5）。

**X1（blocker）已改**：三处把本仓实跑读数写进了交付面（`harness-runner.ts`、`author-context.ts`、
`manifest.yaml` 注释），其中两处随上游补丁出仓——违反 AGENTS §5.3「交付面不含某次运行数字与维护故事」。
已全部改写成失效形态描述，`artifacts/04-*.patch` 重新生成并复验：12 个文件在纯净基线上 apply 后逐字节一致。

**X5 的处置调整并说明理由**：校准建议把 §7.2 扫描词表扩成 `实测|实跑|实证`，归步骤 11。
我先试扫了一遍——扩词后捞出一条**既有**命中：`doc/extensions/skills/story/phases/story-verify.md:106`
「两轮实证，「2 秒」与「10KB」」。它不在步骤 4/5 范围内，且该文件在步骤 9 要退场。
所以**本步不改词表**：现在扩词会让每次提交都显示一条我无权修的命中，反而训练人忽略这条扫描。
词表扩展与那条既有命中一并留给步骤 9/11 处理，此处只登记发现。

**X2**：步骤 1～5 的实施与自审同会话（各报告 §0 已自述），由用户的外部独立复审补偿；
后续按 05 §4 分会话。自审文件已定位为「实施记录」，结论以评审者的 `## 独立评审` 节为准。

**X3**：4、5 分两次提交；本条补登 `80f5cc3e`——它是计划外的未编号提交，内容是把 TEST.md 收回操作协议
（删掉我在步骤 1～3 塞进去的实现背景与批次内部编号，那些各自已有真源），属清理不属新增能力。

**X4**：05 §5 补写审核分组（A(4+5)、B(6+8)、7、9、10、11；分组只改何时审，每步仍各自一提交）；
本表状态行同步。

**步骤 1 的遗留（校准 X1 后半，按校准裁定不单独起一步）**：`agents/opencode/adapter.yaml` 的入册凭据里
写了会话 id 片段与模型名。宿主版本号属框架既有惯例可留，会话 id 与模型名要删。
**下次触碰该文件时一并删除并重生成 `artifacts/01` 补丁**——挂在这里，别丢。

**提交前复跑（2026-09-03，实施者）**：story 551（1 expectedFailure = P9 钉子）、cli 18、compileall、
`validate_clis`、失效形态 73/73、`node --check` 全部 `.mjs`、§7.2 五条扫描（前四条只有既有占位与 XML 噪声，
第五条零命中）全绿。

**新登记一条测试域脆弱点（不在步骤 4/5 范围，挂给步骤 3 的所有者或步骤 11）**：
`test_story_build.TestKnowledgeUnits.test_repo_manifest_derives_units_too` 直接 `int(proc.stdout)`，
当宿主终端让 node 判定为 TTY 时，输出带 ANSI 颜色码（`[33m15[39m`），用例报 ValueError 而非断言失败。
本次首跑撞到，`NO_COLOR=1 FORCE_COLOR=0` 后 551 全绿。修法是用例侧剥色或给子进程固定关色，不是改被测脚本。

## AGENTS 维护契约审核（2026-09-03）

用户与维护者用 grill-me 完成 Q1～Q18，结论见 [09-AGENTS维护契约审核.md](09-AGENTS维护契约审核.md)。
AGENTS 删除测试字段和“一次成文”等批次实现细节，允许有退出条件的分步中间态，补齐三类 Knowledge 生命周期、
正向提示、内容守恒边界、Demo 问题处置和 checker 读取的综合判定。TEST §10 新增 Story init 三轴评分：产物结果、性能、
Knowledge 应用各 100 分且不互相补偿；维护者只给建议分，用户确认最终分数。批次 5 成功后，该量表与确认结果晋升为后续演进基线。


## 步骤 6 实施记录（2026-09-03）

**基线** `00c46802`。允许范围按 `steps/06`：`import_sources.py`、`story_flow.py`、`flow-check.mjs`、
新增的唯一 manifest 写入模块、材料合同及其直接测试。工作区里用户并行写入的
`TEST.md §10`、`09-AGENTS维护契约审核.md` 与几份 steps 文本**不纳入本步**，只有 STATUS 这一份
因为要写实施记录而与用户本轮的 AGENTS 审核段落同处一个文件。

**做了什么**

| 位置 | 改动 |
|---|---|
| 新增 `scripts/materials.py` | 材料清单 `AR/story-src/materials.json` 的唯一算法与唯一写入者：枚举四份正文 + `ux-reference/` + `assets/`，逐份记身份，算出 `digest` |
| `story_flow.py` | 删掉自己那份 `material_inputs` / `material_fingerprint` / `digest`；`round` 改调 `materials.refresh()` 按磁盘现状重算；轮次条目只留 `materials: {path, digest}`，`inputs` 删除 |
| `story_flow.py` | 删掉导入回执的读取与销毁；`imported` 改由清单里「已并入」的原件派生；`pending_material` 改问清单，不再靠契约里的导入账本 |
| `import_sources.py` | 不再落 `AR/.last-import.json`；转换逻辑抽成 `convert_sources()`，与清单判「已并入」共用同一套算法 |
| `flow-check.mjs` | 轮次判据从 `analysis.sha256` 改为 `materials.digest`——初析件不再划轮次 |
| `rules/init_analysis.md`、`SKILL.md` | 轮次定义与产物表同步：材料清单进产物表，回执的说法删除 |
| `test_material_rounds.py` | 补 15 条：契约只指向清单、导入不留回执、放料未导算 pending、导入后换版本、同名换内容重新 pending、重复导入幂等、坏归类件停下、空材料仍有清单、README 变化不动图片身份、改初析不开新轮、契约不镜像 Framework phase、哈希只有一处算法、对接层零引用、替身 js 取材后 `round` 仍生成清单 |
| `test_run_measurement.py` | P9 的 `expectedFailure` 摘除（`assets/` 补图现在换版本），另加「同一张图两个落点仍是一张图」 |

**几处判断，评审重点看**

1. **「已并入」按磁盘判，不按事件判。** 删掉回执后，「这份原件导没导过」的答案改从磁盘取：
   把收件箱那批料用 `convert_sources` 重转一遍与正文比对，一致即已并入。代价是每次 `round`
   要重解析一遍 docx；换来的是同名原件被换了内容也算新料——那是任何一份「导过什么」的名单都记不住的。
2. **图片按内容归并，一张图一条登记。** 界面图按规则要从内嵌位置复制一份到 `ux-reference/`
   起语义名。逐路径各记一条的话，下游看到的是两张一模一样的图。清单因此对 image 按内容合并，
   `paths` 列出它的全部落点；正文不做这种归并（两份内容相同的文档仍是两份材料）。
3. **`materials.json` 留在 `story-src/` 的清扫白名单里，但不随稿冻结。** 一开始把它并进
   `STORY_SRC_FROZEN`（那样清扫自然放过它），自查时发现那会和 `story-build check` 的 ⓪ 撞上：
   ⓪ 说「材料在成文登记之后变了，只记一笔不必处置」，而台账指纹核对会把同一件事判成
   「台账被换过」——同一份文件被当成两种东西。它是材料真源、会随材料演化，所以清扫单列放过，
   冻结不含它；定稿那一刻手里是哪版材料，记在契约当轮的 `materials.digest` 里，那才是快照。
4. **收件箱不进 digest。** 料放进收件箱还没导，流程消费的仍是旧正文，材料版本不该动；
   导入之后正文变了，版本随之变——「补料开出新一轮」因此是机械事实而不是约定。

**没做什么（登记，不静默略过）**

- 6 条主要迁移到本步的失效形态（M05、M06、S10、S11、S16、S17）**checker 一行未改**。清单现在是
  图片身份的唯一真源，但消费它的那一侧（材料清单生成、图片单元枚举）在步骤 8/9；旧路径还没被替代完，
  此时把 checker 改成 `generated_by_construction` 会留下一段没有发现者的空窗。台账留给步骤 8/9 一并处置。
- `rules/init_analysis.md` 的命令表里仍写着 `--by human|ai`，而 `story_flow.py` 的 `ACTORS` 只剩 `human`。
  这是既有的文本与实现相斥，不在本步允许范围（代选路径的退场归更早的轮次），此处登记发现。

**离线**：story 566（新增 15 条，P9 的 expectedFailure 已摘）、cli 18、失效形态 73/73、
`node --check` flow-check、compileall 全绿。真实 Story 未运行（本步不需要）。


## 步骤 8 实施记录（2026-09-03）

**基线** `cb7b7797`。允许范围按 `steps/08`：`story-build.mjs` 的确定性装配部分、
`review-render.mjs`、Review/Story flow 的直接调用点、材料清单与图片路径检查、相关测试。
`story-chapters.json`、`story-template.md`、`headings.mjs` 在允许范围内但**没有动**——这一步
不需要改它们。工作区里用户并行写入的 `TEST.md §10`、`09-AGENTS维护契约审核.md` 与几份 steps
文本不纳入本步。

**顺序说明（先记在前面）**：`05 §3` 写的步骤 8 进入条件是「步骤 7 通过」，而用户 2026-09-03
裁定的审核分组是 A(4+5)、**B(6+8)**、7、9、10、11——8 排在 7 之前。本步按分组执行，
并把 8 的完成条件逐条核过：都能机械验证，没有一条预设步骤 7 的 verifier 产物。
代价见下面「没做什么」的第一条。

**做了什么**

| 位置 | 改动 |
|---|---|
| `story-build.mjs` · build | 加 `requireStoryFirst()`：story 里没有章就拒绝渲染 review。review 是判断的台账，而判断在成文过程中还会长出来——台账定在「只读过 spec」那个时点上，后面新登记的议题就进不来了 |
| `phases/spec.md` | 成文顺序补入 build（⑤ 渲染 review，在裁决之后、登记之前），后续编号顺延，并写清为什么在成文之后 |
| `story-build.mjs` · 图片 | 图片登记的唯一来源改成材料清单：`materialImages()` 读 `materials.json`，按**内容**认身份。归档件自己的图片目录仍可放副本，但要按字节核出它是材料里的哪一张；两个不同路径指向同一条登记 = 同一张图引了两次 |
| `story-build.mjs` · 材料清单 | 加 `materialListTargets()`：必列 = 清单里真的在盘上的那几份正文，可列 = 收件箱原件，其余一律不是材料。漏列与多列两面都报 |
| 同上 | 有清单时，目录白名单那条粗判让位（`allowDirs: []`）——两条同时开会对同一行报两遍，读的人以为是两个问题 |
| `story-build.mjs` · ⑫a | 新增「非占位」一段：章有正文、模板占位符 `{{…}}` 换掉。**只有这两件事**，不设任何字数、行数、表格、图片、条目下限 |
| `check_failure_modes.py` | 夹具跑 story-build 之前先跑一次 `story_flow.py round`——不然没有清单，新判据只会说「未执行」，S10/S11/S17 的 bad 夹具会逃检（实测：改完判据后这三条当场变成「期望 FAIL 实际 PASS」） |
| `test_story_build.py` | 新增 4 个类 18 条：review 后置与幂等 5 条、图片身份 5 条、材料清单集合 5 条、非占位 3 条 |

**几处判断，评审重点看**

1. **材料清单没有改成整节机器生成。** `steps/08` 第 3 条写的是「材料清单只从 material manifest
   生成」。按字面做会和「现有金样仍应通过」直接撞上：金样每行是「语义标签——来源与提供方式：
   内容贡献。原文：链接」，其中只有路径能机械产出，「这份材料贡献了什么」是语义。
   所以落成**集合由清单定、语义由作者写**：有哪几份、链到哪里不再由作者自由决定，
   漏一份或多一份当场点名。这是这条要求可实现的内核，但确实不是字面的「生成」，请评审裁定。
2. **归档副本区按字节核对。** 归档件自己的图片目录（合同 `story_image_dir`）是允许的副本区，
   否则 story 引不到任何图。判据因此不是「不许有副本」，而是「副本必须真的是材料里那张图」——
   同一张图改名复制进去会被认出来（S17 的形态），放一张来路不明的图也会被认出来。
3. **判据在没有清单时明说「未执行」，不静默放过。** offline 仲裁（金样那条路）没有需求目录，
   清单不可能在。两条新判据都会在 notes 里说明未执行与怎么让它能执行；夹具自检那一侧
   则用先跑 round 的办法保证判据真的跑过。

**没做什么（登记，不静默略过）**

- **既有的小节配额没有删。** 合同里 `min_sections: 1` 只有两处，语义是「该分节的章有没有分节」，
  不是「每章几节」那种凑数配额，注释里也明说不设配额，所以留着。但真正把「章平铺成散文」
  从固定形式改成效果判断的是 **S08/S09 归的步骤 7**（verifier 资格门）。8 先于 7 实施，
  此刻删任何一条形式判据都会留下没有发现者的空窗，所以本步不动它们。
- **台账 9 条（M07、M10、P09、P10、P14、S06、S07、S15、S19）的 checker 一行未改**，理由同步骤 6：
  它们仍在守，responsibility 的改写等 7/9 落地后一并处置。S10/S11/S17 的 checker 也没改，
  改的是让它们跑得到新判据的那一步。
- 真实 Story 未运行（本步不需要）。

**离线**：story 586（新增 18 条）、cli 18、失效形态 73/73、`node --check` 全部 `.mjs`、
compileall、TEST §7.2 五条扫描（命中与本步之前逐条相同，全是既有占位与 XML 噪声）。
- 2026-09-03 独立评审者复审 B 组（6+8）：通过。裁定①材料清单节「集合由 manifest 派生核对、贡献说明由作者写」不算偏离 D8；裁定②步骤 6/8 名下 15 条形态的旧 checker 保留为登记迁移桥，responsibility 改写与退场在步骤 9/11。已回写 `steps/08`、D8 表、06 矩阵与 05 §3。下一步：步骤 7。


## 步骤 7 实施记录（2026-09-03）

**基线** `4e9a6d21`。允许范围按 `steps/07`：Extension 的 Story verifier 任务与 prompt 组装、
`test/story/fixtures/narrative-variants/**` 与对应资格测试、`TEST.md` 的资格测试入口。
工作区里用户并行写入的 `TEST.md §10`、`09-AGENTS维护契约审核.md` 与几份 steps/design 文本不纳入本步；
`TEST.md` 因为要写 §8.1 与 §9.1 而与用户那段改动同处一个文件。

**用户 2026-09-03 裁定：CLI 实跑先暂缓**，与步骤 2 的 verifier smoke 一并等授权。
本步交付的是**装置**：审查任务、成对夹具、判据与入口全部就位，资格结论登记为待验证。

**做了什么**

| 位置 | 改动 |
|---|---|
| `rules/spec-rules.overlay.yaml` | 新增 `story_reader_review`：独立的归档叙事件审查。输入是材料清单指向的每一份材料、已确认范围、已登记判断与 spec 已成立的约束；按合同里每章的读者问题与章级维度审十个方面；**不逐条核来源单元、不出裁决表**；结论只有 `blocking_findings` 与 `advisories` 两类 |
| `fixtures/narrative-variants/pairs/base-receipt.story.md` | good 基底一：交易凭证下载，十章齐全的完整稿 |
| `fixtures/narrative-variants/pairs/base-queue.{brief,story}.md` | good 基底二：门店排队叫号提醒，业务名、术语、编号与基底一完全不同 |
| `fixtures/narrative-variants/pairs/pairs.json` | 六族缺陷 × 每族两个变体的**精确编辑**定义（删事实、掏空章、编造、删流程图、知识回显、同义改写） |
| `scripts/make_narrative_variants.py` | 由基底 + 编辑现生成样本；锚点在基底里不是恰好一次就停下报错 |
| `tests/test_narrative_variants.py` | 13 条：夹具立不立得住、六族齐备、每族跨两个业务域、good 基底十章齐、生成确定性、锚点漂移会被拦、**交付面零泄漏**、审查任务已登记且不要裁决表 |
| `TEST.md §9.1` | 资格门入口：器材怎么生成、怎么跑、判据表（good 与同义改写零 blocking，其余五族须点名到本族缺陷）、按配置记结论、small/large 尺度观察、与 §9 的并存关系 |
| `TEST.md §8.1` + `baseline_coverage.py` | 消费者审计结论落盘（见下） |

**几处判断，评审重点看**

1. **样本不整份存仓，只存「差在哪」。** 六族两变体是十二份 bad 加两份 good；整份存进去，
   改一句基底就要同步改十四处，而它们本该只差声明的那一处，差异还会淹没在整篇文本里。
   现在仓里只有两份基底和一份 `pairs.json`，样本由脚本现生成；锚点在基底里不是恰好出现一次
   就停下报错——那说明基底改过而定义没跟上，再生成出来的样本已经不是它自称的那种缺陷。
2. **第二个基底换的是业务，不是措辞。** 门店排队叫号与交易凭证下载在术语、编号、参与方上
   没有一处重叠。同一种缺陷只在一个业务里测得出来的话，测的是它有没有记住固定文本。
3. **审查任务不要那张逐单元裁决表。** 逐条核来源单元的量随材料条数涨，而读者拿到的判断
   不增加——那正是要退的形态。新任务判的是机器判不了的那一类：讲了没有、讲清没有、是不是编的。
   旧的三张表仍在正式路径上，两边并存到它的退场步骤。
4. **`baseline_coverage.py` 的消费者审计结论：随步骤 9 退场。** 新的语义链不消费它；
   它的枚举依赖 `source-units.mjs`，那是逐单元系统的一部分。在那之前只作历史诊断、
   不参与任何 PASS/FAIL。结论写进了工具自己的 docstring 与 `TEST.md §8.1`，不只写在这里。

**没做什么（登记，不静默略过）**

- **资格实跑未进行**（用户裁定暂缓）。因此这几条完成条件登记为待验证：每族 good 通过 / bad 命中、
  「十章在而内容大量丢失」稳定失败、报告规模按问题族增长、各配置的独立资格结论与配置矩阵、
  small/large 尺度观测。步骤 11 的 `cli_config_id` 必须来自将来的通过集合，现在没有通过集合。
- **P11、C01、R01、F02 及相关 S 类形态的台账未改。** 新发现者（`story_reader_review`）已上线，
  旧发现者仍在守——这正是 D10 的次序。responsibility 的改写与旧发现者退场归步骤 9/11，
  与步骤 6、8 的处置一致。
- 未新增任何 token、相似度或数量 checker：本步只有一条 verifier 任务文本、两份基底、
  一份编辑定义与一个生成器，生成器里没有阈值。

**离线**：story 599（新增 13 条）、cli 18、失效形态 73/73、compileall、
`TEST §7.2` 五条扫描（命中与本步之前逐条相同）。真实 CLI 未运行。
- 2026-09-03 独立评审者复审步骤 7：装置通过、区分力结论未取得（授权暂缓）。返修一条：扩展的「注入≠执行」收口只覆盖 `knowledge_` 前缀判据，`story_reader_review` 无执行证明，须在步骤 9 切换前补进必答清单与报告核对。四条 advisory 见评审。
- 2026-09-03 用户裁定：步骤 7 资格门与步骤 2 smoke 一并暂缓，合入步骤 11 的唯一 CLI 窗口，顺序固定为 smoke → 资格门 → 真实 Story → 退场，任一环不成立即停。前提：步骤 7 执行证明返修离线完成；9、10 不删旧发现者。已写入 05 §3 与 `steps/11`。


## 步骤 7 评审返修（2026-09-03）

`reviews/07` 判「装置通过，附一条返修（须在步骤 9 切换前落地）」。返修已补，未重做任何设计。

**§4 执行证明缺失**：判据注入了 verifier 的上下文，不等于它被执行——实测过整份必答清单
一条没裁而 harness 照收 PASS。步骤 9 之后 `story_reader_review` 是 story 语义质量的唯一发现者，
同一形态重演时没人会知道那一轮根本没审。

补法（只核形态，不核内容）：

| 位置 | 改动 |
|---|---|
| `hooks/shared/verifier-report.mjs` | 新增 `storyReviewProblems()`：报告里要有以 `story_reader_review` 为标记的结果块，块内 `blocking_findings` 与 `advisories` 两个小节。**空列表是合法结论**——审过而没发现问题，与没审是两件事；块里出现逐单元裁决表的表头则点名「做成了另一件事」 |
| `hooks/spec/post_check.mjs` | 登记为 `story_review_persisted`；story.md 不在或报告还没有时 NOT_APPLICABLE（那不是通过，是还轮不到判） |
| `rules/spec-rules.overlay.yaml` | 审查任务补上落盘约定：结果写成那一块、两个小节、没有阻断问题就写空列表，只写在 YAML 输出里不算 |
| `tests/test_verifier_report_protocol.py` | 新增 6 条：缺结果块点名、空列表通过、缺小节点名、逐单元表点名形态不对、无 story 与无报告各为 NOT_APPLICABLE |

**advisory 的处置**：A1（资格门驱动器）与 A3（第二基底用的是简报而非四源）都要等实跑恢复才谈得上，
随实跑一并处理；A2（`blocking_findings` 非空是否映射为 BLOCKER）归步骤 9 定，它属于作者路径切换时的收敛口径；
A4（异常与验收章没有掏空变体）按评审建议不预先加，实跑后按误判情况再定。

**离线**：story 605（返修新增 6 条）、失效形态 73/73、全部 `.mjs` `node --check`。


## 步骤 9 实施记录（2026-09-03）· 第一段：按章落盘

**基线** `7e973e13`。允许范围按 `steps/09`：Story phase 作业包与正式入口、`story-build.mjs`
的相关路径、Spec 阶段调用顺序、构建与写作流测试。

**做了什么**

| 位置 | 改动 |
|---|---|
| `story-build.mjs skeleton` | 建十章骨架：每章一个稳定章锚 + 一个待写 marker。已有 story.md 时不覆盖——它是起手动作，不是重置键 |
| `story-build.mjs chapter` | 把一章原子替换进 story.md：校验章名在合同里、章锚在文里、正文非空，替换区间就是那一章，别处一个字节不碰。正文走文件不走参数 |
| `story-build.mjs check` | 新增「还有几章带着待写 marker」——骨架当成品交，是实测出现过的形态 |
| `phases/story-write.md` | 第二步改为「先建骨架、每章经 `chapter` 落盘」，第三步统稿改为「要动第五章就重写第五章再落盘一次，不重新输出整篇」 |
| `phases/spec.md` | 成文顺序补入 ③ 建骨架，逐章渲染改为经命令落盘 |
| `test_story_build.py` | 新增 9 条：骨架十章带 marker、骨架不覆盖已有稿、写一章其余字节不变、**第 4 章中断恢复前三章逐字节不变**、**统稿只改第 5 章其余九章相同**、未知章名/空正文/缺 `--from` 各自被拒、check 点名仍待写的章 |

这一段关掉的是 `07 §6.2` 的 R1 与 R3：统稿与逐章写入都只能经同一条命令落盘，
「已完成的章字节不变」由此成为机械事实而不是期望；不存在一次写入整篇的路径。

**逐单元退场没有做，理由是退场次序，不是漏做**

`05 §7` 把退场次序钉死为：

```text
新作者任务可达且可按章中断恢复      ← 本段刚做完
→ 新 verifier good/bad 有区分力      ← 卡在这里：资格实跑按用户裁定暂缓
→ 准备实跑的 cli_config_id 逐个取得资格
→ …… → 删除旧发现者并批准纯旧实现形态 retired
```

删掉正式路径上的 `source-units`/`audit` 生产环节，就必须同时删掉读它们的判据
（② 落点守恒、④ 形态守恒、⑥ 裁决核实、⑥b 逐问与逐章、⑧ 术语表实体词守恒）。
而这些判据正是十条失效形态现行的唯一发现者：`B02`、`C01`、`R01`、`S01`、`S02`、
`S05`、`S08`、`S09`、`S20` 与 `R02` 的一部分。判据一删，它们的 bad 夹具当场逃检，
73 条回归红——这与步骤 8 改图片判据时 `S10/S11/S17` 当场变成「期望 FAIL 实际 PASS」
是同一种事故，只是那次有新判据接住，这次没有。

它们的接手者是步骤 7 建的 `story_reader_review`，而它的区分力**尚未经资格实跑证明**。
在没有证明之前把旧发现者删掉，等于用一个未经验证的发现者换掉十条形态的守门，
`failure-modes.yaml` 里它们的合法状态只剩 `retired`——那要 `reason + approved_by`，
方案把它定在步骤 11。

所以本段停在这里。三条出路，请裁定：

1. **恢复资格实跑**（步骤 7 §9.1，一个基底 7 次 verifier 调用起），拿到区分力结论后再退场；
2. **现在批准那十条形态转 `pending_capability` 并调整夹具自检口径**——等于承认一段没有
   机械发现者的空窗，须签字；
3. **步骤 9 只交付本段**，退场整体推到资格实跑之后（与步骤 11 合并或另立一步）。

**离线**：story 614（新增 9 条）、cli 18、失效形态 73/73、compileall、`node --check` 全部 `.mjs`。
真实 Story 未运行。
- 2026-09-03 步骤 9 第一段查明：停产 audit/source-units 会让十条形态的现行发现者失去输入，「保留到步骤 11」只是名义。用户授权恢复步骤 7 资格实跑（评审者复核：授权正确，前置是先跑步骤 2 smoke 定 D1）。05 §3 与 `steps/11` 的 CLI 窗口位置已改为「smoke + 资格门在步骤 9 第二段之前；真实 Story + 退场留在步骤 11」，覆盖当日早先的合并裁定。
- 2026-09-03 用户裁定数量目标必须生效。新建机制层预算门：`test/story/regression/mechanism-budget.yaml`（按类别 ceiling/target，具名抬高）+ `tests/test_mechanism_budget.py`（进全量离线回归，每步必过；另核语义代理标识不增长）。现值冻结为 ceiling，退场后步骤 11 把 ceiling 压到 target（总量 9500，低于批次 3 收口）。TEST §8 第 7 项、AGENTS §7.3/§8、reviews/README 同步。
- 2026-09-03 预算门补成三时点：方案（步骤文件必须有《预算》节，已补到 steps/09、10、11；05 §4 写明缺则不受理）、实现后自检（预算门报错指向 AGENTS §4.2/§7.2/§7.3，明写「不是裁剪令」）、测试后审查（reviews/README 预算一栏对照《预算》节与预算文件 diff）。
- 2026-09-03 用户纠正：预算是一次完整需求的要求，不按步骤拦中间态。预算门改为需求级：进行中核方案声明的峰值 interim_ceiling，完成（status: closed）时核 target；语义代理标识任何时候不增长。三角色分工（维护者给预算 / 执行者自检超出与不足 / 评审申请特别审视）写入 AGENTS §7.2、05 §4 与预算文件头。
- 2026-09-03 用户要求规则本身写清、新会话读 AGENTS 即知：预算规则独立成 AGENTS §7.5（对象、三角色三时点、三条判据、不按步骤拦中间态、不砍方案）。脚本只保留一个测试文件，不再加拦截。


## 步骤 7 资格实跑（2026-09-03）· 结论未取得，已按用户裁定收手

用户 2026-09-03 授权恢复资格实跑，同日在跑了七八轮之后裁定打住。这一节记清楚**拿到了什么、
没拿到什么、为什么停**——下一轮接手的人不必重跑这些路。

### 配置

| cli_config_id | 可用性 | 每份耗时 |
|---|---|---|
| `bailian-deepseek`（OpenCode） | 可用，本轮全部读数出自它 | 100–265 秒 |
| `volcengine-glm-flash`（OpenCode） | 可用但慢，且有一份 600 秒超时零输出 | 275–600 秒 |

`codex-luna` 未跑。两个配置在同一份任务定义上表现差得很远，这本身就是「资格结论按配置记、
不能互相代替」的实证。

### 装置的三处修正（都在实跑中暴露）

| 现象 | 真因 | 修法 |
|---|---|---|
| 一个模型收到全文、另一个回「判据和归档叙事件都没提供」 | 长 prompt 走命令行参数不可靠，而它带着 story 全文注定长 | 任务写成工作区里的 `REVIEW-TASK.md`，命令行只留一句指引 |
| 首跑 300 秒超时零输出 | 让它自己去工作区翻文件，预算花在找文件上 | 同上——一份文件读一次就齐 |
| 中途停掉，前五份输出正文全丢 | 驱动器全跑完才落盘 | 每份跑完立刻落盘，支持续跑 |

另把「没跑出来」与「审查者看过没报」在数据里分成三态（`blocking` / `clean` / `no_output`），
不让装置故障混进命中率。

### 夹具的四轮清理

审查者每轮挑出的问题**没有一条是误判**，四轮挑出的都是基底真缺陷：

1. 材料只有一页要点时，story 里正常的背景展开被判「无材料支持」；材料清单链到工作区里不存在的路径；
2. 「无网络也能保存」与「每次生成都重新查询」正面冲突；规约判定依据与功能说明自相矛盾；
3. 我改基底时引入的死分支、跨章字段对不上、编造的埋点行为；遗留的删除时机数不一致、用户可见行为无据；
4. 我自己逐条审出的 12 处：六处无出处推断、四处合同要求没答、两处材料清单不全。

第四轮之后 `receipt.good` 与 `queue.good` 都零 blocking——基底干净了。

### 可信读数（人工核对过点名）

| 族 | 结论 | 点名 |
|---|---|---|
| `knowledge_echo` ×2 | blocking ✅ | 「依据只回显规约名，没落到任何具体事实上」——判据收紧后才点得出，之前它判 advisory |
| `image_dropped` ×2 | blocking ✅ | 「版式事实与图的引用整篇缺失」 |
| `chapter_hollow_queue` | blocking ✅ | 本轮，未逐字读输出 |
| `fabricated_receipt` | blocking ✅ | 本轮，未逐字读输出 |
| `receipt.good` / `queue.good` | clean ✅ | 最终基底上两份都干净 |

### 没取得的，以及为什么

- **`fact_deleted` 结论悬空**。早期两次报了且点名精确，最终基底上却判 clean。真因是
  **两个族的编辑区域重叠**：`image_dropped` 的版式段与图插进了功能说明的「详情页凭证入口」小节，
  正好是 `fact_deleted` 要删的那段所在的节；删掉入口条件后那节还剩版式与图，看起来不缺内容，
  而入口条件在验收表、流程图节点、术语定义里仍有痕迹。审查者判 advisory 是合理的。
  **这是夹具设计缺陷，不是审查者失准。**
- **`image_dropped` 与 `knowledge_echo` 未在最终基底上复核**（它们的确证读数出自第三轮基底）。
- **`same_meaning` 一份未跑**（误报面只有 good 两份支撑）。
- **第二个配置没有资格结论**。

### 三条要带走的教训

1. **解析用穷举补丁对付开放集合，错了三次。** 模型的空结论写法是开放的——`- （无）`、
   `` ` []（无）` ``、`**: []` 三种形态各让我误判一轮，而每一次误判都触发了一轮本不必要的夹具修改。
   正确判法是「剥掉全部 markdown 装饰后还有没有实质条目」，不是「是不是我认识的空写法」。
2. **两个变体的编辑区域不能重叠**，否则一族的注入会削弱另一族——`pairs.json` 需要一条
   「各族编辑区互不相交」的自检。
3. **不要拿真实 CLI 当找 bug 的工具**。它的报告是有取舍的抽样，不是完整缺陷清单，所以
   「跑一次改一处」永远收敛不完。先自审到位、一次改全、跑最小集。

### 两条判据缺口（属方案层，未擅改）

- **判据没要求可复现**。实测撞到过同一份稿的同一个问题一轮判 advisory、下一轮判 blocking。
  按现有判据两次都「通过」，但步骤 9 若把 `blocking_findings` 非空映射成门禁 BLOCKER
  （评审 A2 问的正是这件事），作者会遇到不可复现的红。建议补一条：关键样本跑两次结论一致。
- **「good 零 blocking」实际在要求夹具完美**，而不是在测审查者。四轮里它对诚实稿子挑出的
  每一条都成立。更贴合本意的 good 判据也许是「报出的每一条都不成立才算误报」。

### 结论

步骤 7 维持 **装置通过、资格结论未取得**。步骤 11 的 `cli_config_id` 仍没有通过集合可选，
因此**步骤 9 的逐单元退场继续挂账**（退场次序卡在「新 verifier 有区分力」这一环）。
下一轮接手时先改两件事再跑：解析换判法、`image_dropped` 的插入位置挪出 `fact_deleted` 的删除区。
- 2026-09-03 用户裁定（最终）：不构造异常场景给审查者造考题；批次 5 的 CLI 只有步骤 11 一次，跑正常需求、按三轴评分确认。D10 §1 资格门撤销（03 有修订记录），退场次序删去两环，步骤 9 第二段直接实施，十条形态 responsibility 改 verifier/behavior_test 由真实结果兜底（用户签字）。步骤 2 smoke 与步骤 7 合成夹具留为离线器材；TEST §9/§9.1 标为诊断工具。评审者承认此前两次仍在用程序测试思路提方案。
- 2026-09-03 按「只跑正常需求」校准全批：05 步骤 7 行与步骤 2 前提、06 矩阵 D10/步骤 7 行、steps/02、steps/11 退场措辞已改；steps/09 第二段增加台账 `observed` 状态（不造夹具）；AGENTS §7.4 加一句原则。已实现代码零改动，测试装置（smoke、成对夹具、驱动器、TEST §9/§9.1）降为诊断器材。


## 步骤 9 第二段 · 小段 1（2026-09-03）：换输入模型 · 已实施，等待评审

**基线** `c8ad6f47`。范围严格限定：只改 ⑦ 与 ⑨ 两条判据的**取数口**，一条判据不删、
`audit` 与 `init` 的枚举不动、不夹带步骤 10 的任何改动。

**做了什么**

| 位置 | 改动 |
|---|---|
| `story-build.mjs` 新增 `materialUnitsNow(ctx, docs)` | 按当前材料现场枚举来源单元。`init` 与 `check` 共用同一套参数——各写一份的话，排除表、编号形态或模板约定差一项，枚举出的 token 集合就不同，而这类不同是静默的 |
| `cmdInit` | 改调 `materialUnitsNow`，原地那段枚举代码删除（同一算法只留一处） |
| ⑦ 规约判定表 | 规约编号与域名改从**激活清单**取（`activeKnowledgeEntries`），不再经「材料单元」那一层 |
| ⑨ 归档件四红线 | 工程标识改为**现场按材料枚举**（`materialUnitsForRedline`），不读 `init` 落盘的那份清单；`ruleIds` 同样取激活清单 |

`check` 因此对这两条判据完全不经 `doc.units`。离线仲裁没有工程上下文，两个取数口都给空数组——
依赖它们的判项自然不判，而不是拿空清单去判「一条规约都没判到」。

**等价性证据**

1. **代码级**：⑦ 原先经 `knowledgeUnits(entries)`，而那个函数的定义就是
   `tokens: [e.id]`、`domain: e.domainTitle` —— 换成直接读 `entries` 是同一份数据换个形状。
   ⑨ 原先读的那份清单，正是 `init` 用 `materialUnitsNow` 生成的；现在 `check` 调同一个函数、
   同一套参数、同一份材料，所以集合逐元素相同。材料若在枚举之后变过，⓪ 判据照旧会报——
   那一条本小段没动。
2. **黑盒对照**：金样 + 两份实跑快照（`scratch/adv/root` 的 AR90004、`scratch/f4/run` 的
   AR90006）+ 每份两个反例，共九次运行，⑦ 与 ⑨ 的报错**逐条相同**（对照器
   `equiv_79b.py` 改前改后各跑一次，`diff` 无差异）。九次里 ⑦⑨ 均为 0 条——
   这三份产物本来就不违反这两条，所以这一半证据只证明**不误报**；「判得出同样的问题」
   由上面的代码级论证承担。
3. **回归**：失效形态 73/73（委派 0）、story 619 条全绿。

**没做什么**

- 一条判据都没删（②④⑥⑥b⑧ 原样保留，它们仍读 `doc.units` 与 `audit.json`）；
- `audit` 命令、`init` 的枚举、`source-units.mjs`、作业书、台账都没动；
- `check` 里读了两遍材料（⓪ 的 `scanSources` 一次、⑨ 的现场枚举一次）。可以合并成一次，
  但那要跨半个函数传变量，留给小段 3 一并处理，本段不动。
- 2026-09-03 独立评审步骤 9 小段 1：代码干净、回归全绿，但把 ⑨ 语言红线的「材料派生标识清单」当保留项加固——那正是 P1 的根因，steps/09 分工表与 04 审计 M10/P08 都要它退。返修：删 `identifiers` 输入与 `materialUnitsForRedline`，⑨ 只留明确形态的红线，主叙事英文词问题交 `story_reader_review`；⑦ 取激活清单可接受（步骤 10 后成生成一致性）。预备提交 c8ad6f47 通过。


## 步骤 9 第二段 · 小段 1 返修（2026-09-03）

`reviews/09` 判 2a **不通过（方向）**：⑩ 语言红线里「材料派生的词表」那一路正是 P1 的根因，
方案里本就要退，而我把它当保留项做了等价迁移——方向反了。返修按评审 §4「只减不加」执行。

**改了什么**

| 位置 | 改动 |
|---|---|
| `lint-rules.mjs` | 删掉 `identifiers` 这一路输入与它的那段匹配。红线保留**形态本身就是工程标识**的几类：行内代码、驼峰、下划线、仓内路径，以及规约编号、文档坐标、来源括注、检索腔、占位标题、AI 腔标题、装置词 |
| `story-build.mjs` | 删掉 `identifiers` 的构造与传参、删掉 `materialUnitsForRedline`。`check` 里不再有任何按材料枚举单元的调用 |
| `materialUnitsNow` | 只剩 `init` 一个消费者，按评审 A1 留到小段 3 随 `init` 枚举一起退 |

「主叙事里这个英文词该不该出现」交 `story_reader_review`——它本来就在审「主叙事是否被工程语言打断」。

**结果判据（评审 §4 逐条）**

1. **P1 形状不再误报**。评审指的那份快照是事后产物，作者已经绕开了这条红线，改前也不报——
   所以我按 P1 的形状精确复现：在 `scratch/f4/run` 的 ISSUE-206 副本主叙事里插一行
   「分享设置页（share）与接受页（accept）是本次的两个入口」，而材料 token 里确实有
   `share` 与 `accept`（从 `source-units.json` 核过）。
   - 改前：`主叙事出现工程标识 2 处（5 行「share」，5 行「accept」）`
   - 改后：这一条消失，同一次运行里的 `harness_artifact 5 处（31 行「人话」…）` **逐字保留**
2. **其余红线逐条相同**：金样 + 两份快照 + 四反例共九次运行，⑦ 与 ⑨ 报错逐条相同（`diff` 无差异）。
3. **回归**：失效形态 73/73（委派 0）、story 619 全绿。
4. **预算**：`semantic_proxy` 计数不升（预算门 5 条通过）；`scripts_mjs` 因删代码净减。


## 步骤 9 第二段 · 小段 2（2026-09-03）：删五类逐单元判据并迁台账 · 已实施，等待评审

**基线** `41ff385f`。范围：`story-build.mjs` 的判据、`failure-modes.yaml`、
`check_failure_modes.py`、三份测试。`audit` 命令、`init` 枚举、`source-units.mjs`、
作业书都没动（归小段 3）；不夹带步骤 10。

**判据退场**

五类整段删除，不缩不改：② 落点守恒、④ 形态守恒、⑥ 裁决核实、⑥b 逐问与逐章、
⑧ 术语表实体词守恒。⓪a 与 ⓪（来源齐备、材料未在枚举后变过）不在本段范围。

**一处误删已纠正**：图片枚举与图片身份两块物理上挂在「④ 形态守恒」这个 mark 底下，
跟着被删，S10/S11/S17 三条形态当场失去发现者。它们判的是「引用可不可解析、在不在登记里」，
属 `steps/09` 脚本分工里的「链接/图片」，与「分几张画几张」无关——救出来独立成
`④ 图片身份`，名字不再挂在形态守恒下面。

**台账迁移**

三条形态因判据退场而失去机械发现者，登记为 `observed`（`c8ad6f47` 建的委派档），
各带 `reason` / `approved_by`（用户 2026-09-03 D10 修订签字）/ `observed_by`：

| 形态 | 真实 Story 里由谁看什么 |
|---|---|
| `C01-story-conservation` | `story_reader_review` 的 blocking 是否点出关键业务事实缺失；用户按 TEST §10「产物结果」一轴看他在成品里找到的遗漏审查者报没报 |
| `R01-verdict-echo` | 审查结论的定位与引用是否指向 story 自己的原文而非材料原话；用户按同一轴复核结论是否站得住 |
| `S01-diagram-degraded` | 审查「图与文的配合」这一维度是否点出流程表达降级；用户看成品里的图是否还原了材料的结构 |

`checker` / `bad_fixture` / `good_fixture` 三个字段随之删除——发现者不是脚本了，留着就是
零消费者配置。`check_failure_modes` 对 `observed` 只核字段（缺 `observed_by` 判 FAIL），
夹具自检与真实目标两步都不跑，回归里单列一档。委派档补了 `observed` 这一目：
`verifier` / `behavior_test` 说的是「换给哪个执行体」，而这三条是「在真实结果里看」，
是观察安排不是换执行体。

**测试退场（按三分类，71 条）**

判定按**类主题**，不按当次是红是绿——一个类整体守的是刚退场的判据时，它里面还绿的那几条
是假绿（判据没了，断言「应该通过」自然通过），留着比红更糟。

| 类 | 处置 | 条数 | 守的是 |
|---|---|---|---|
| `test_negative_guards.FiguresMustNotVanish` | 整类 | 4 | 形态守恒·图与图片消失 |
| `test_negative_guards.FormShortfallIsVisibleWhileWriting` | 整类 | 5 | 形态欠账 |
| `test_negative_guards.FormShortfallCountsPerChapterPerKind` | 整类 | 10 | 形态欠账粒度 |
| `test_negative_guards.MaterialOnlyIsTheOnlyWayToNotDraw` | 整类 | 6 | audit 的 material_only 三态 |
| `test_negative_guards.DiagramsHaveNoMaterialOnly` | 整类 | 2 | 同上 |
| `test_negative_guards.IdentifiersMustBeConservedWhereTheyLand` | 整类 | 4 | 标识符落点守恒 |
| `test_negative_guards.GlossaryEntitiesMustReachTheStory` | 整类 | 5 | 术语实体词守恒 |
| `test_story_build.TestMachinePlacement` | 整类 | 2 | 落点守恒·机器落点 |
| `test_story_build.TestHardFactConservation` | 整类 | 3 | 落点守恒·硬事实 |
| `test_story_build.TestAllocationDomain` | 整类 | 3 | 落点守恒·分配域 |
| `test_story_build.TestAuthorPlacement` | 整类 | 3 | 落点守恒·作者落点三态 |
| `test_story_build.TestMachineFacingColumns` | 整类 | 2 | 落点守恒·机器面列 |
| `test_story_build.TestVerdicts` | 整类 | 7 | 裁决核实 |
| `test_story_build.TestQuoteSentenceBounds` | 整类 | 9 | 裁决核实·引文句边界 |
| `test_story_build.TestGlossaryAndRedlines` | 方法 | 2 | 术语实体词守恒（留仓内路径红线那条） |
| `test_story_build.TestDecisionUnits` | 方法 | 1 | 落点守恒（留其余四条） |
| `test_story_build.TestErrorWordingPointsAtForm` | 方法 | 2 | 落点与术语的报错文案（留文案风格那条） |
| `test_story_allocate_render.TestAllocation` | 方法 | 1 | `covered_by` 落点（留 audit 分配那三条） |

**第二类（保留断言、只改搭建）本段只有一处**：`TheLibraryItselfIsComplete` 守「反例库
不许有缺号」，退掉九条之后编号断了。判据一个字没动，动的是它比对的基线——剩下三条重新
编号 N1..N3、`NEGATIVE_COUNT` 改 3。真正因搭建依赖 `audit` / `source-units` 而红的一条没有：
那两样本段都还在。

**那条测试间干扰不属本段**：`CliRuntimeIsolationTest` 在小段 1 的提交点 `41ff385f` 上
全量跑是绿的，本段改动后也绿——先前那次「全量红、单跑绿」是我的诊断脚本传了精简 `env`
造成的假阳性，仓库里没有这个问题。

**验收**

- 73 条对账仍是 73：FAIL 0、委派 3、PASS 70；
- `check_failure_modes` 对 `observed` 只核字段、不跑夹具；
- 不新增任何数量或相似度判据；预算门 5 条通过，`semantic_proxy` 30 处（ceiling 37）只降不升；
- story 548 全绿（619 − 71 条退场）、cli 18、金样离线 check 通过、`node --check` 通过；
- `story-build.mjs` 2411 行（判据删了五类、救回图片两块、净减）。
