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
| 7 Story 语义审查资格门 | **已实施（装置）；资格实跑待授权** | 待生成 |
| 8 Story/Review 确定性生成 | **通过**（`4e9a6d21`；两条裁定见评审 §4） | 同上 |
| 9 正向 Story 作者路径切换 | 未开始 | 待生成 |
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
