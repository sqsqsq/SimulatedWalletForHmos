# 批次 5 · 实跑问题诊断 · 进展跟踪

| 项 | 值 |
|---|---|
| 状态 | **步骤 1 通过并提交；步骤 2 待开工** |
| 输入 | 批次 1～4 全部需求/方案/判据/报告与提交史；F8 局部优化现场；外网 suite `20260901-230253-23468`；内网反馈 |
| 诊断文件 | [00-问题记录与原因分析.md](00-问题记录与原因分析.md)（P1–P16，行为链/所有者/批次分类与实跑证据）<br>[01-四批次全量问题与根因审计.md](01-四批次全量问题与根因审计.md)（两个维护认知根因、十个机制根因、处置边界与方案制定方式）<br>[02-AGENTS重写与信息迁移审计.md](02-AGENTS重写与信息迁移审计.md)（旧内容逐项保留、去重、迁移或退役）<br>[04-失效形态长期要求审计.md](04-失效形态长期要求审计.md)（73 条逐项分为长期不变量、目标迁移、旧实现专属）<br>[06-验收追踪矩阵.md](06-验收追踪矩阵.md)（P1～P16、D1～D12、73 条到步骤的完整对账）<br>[07-方案评审意见.md](07-方案评审意见.md)（独立评审原文及维护者逐项处置） |
| 决策记录 | [03-方案讨论决策.md](03-方案讨论决策.md)（D1～D11 与 Q1～Q29 共识；D12 不适用） |
| 范围 | 批次 1～4；批次 0 与更早轮次只作根因追溯证据 |
| 方案文件 | [05-实施方案总览.md](05-实施方案总览.md)；`steps/01`～`steps/11` |
| 评审规则 | [reviews/README.md](reviews/README.md)；每步一份独立报告 |

## 步骤状态

| 步骤 | 状态 | 评审报告 |
|---|---|---|
| 1 OpenCode verifier adapter | **通过** | [reviews/01-opencode-verifier-adapter.md](reviews/01-opencode-verifier-adapter.md) |
| 2 OpenCode verifier Spec smoke | 未开始 | 待生成 |
| 3 测试观测与效率事实 | 未开始 | 待生成 |
| 4 Framework 作者上下文入口 | 未开始；实施前重新取得 Framework 修改授权 | 待生成 |
| 5 Extension 六阶段作者入口 | 未开始 | 待生成 |
| 6 材料版本与流程状态 SSOT | 未开始 | 待生成 |
| 7 Story 语义审查资格门 | 未开始 | 待生成 |
| 8 Story/Review 确定性生成 | 未开始 | 待生成 |
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
