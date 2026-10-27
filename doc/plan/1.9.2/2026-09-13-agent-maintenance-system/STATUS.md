# 当前实施状态

入口：[00-总览](00-总览.md)。当前范围为用户级 AGENTS.md/CLAUDE.md 重写、三个项目维护依据、maintenance-agent 维护诊断及其验收。其他完成情况按实际证据登记。

| 步骤 | 前置 | 状态 | 实施证据 |
|---|---|---|---|
| S1 用户级两份规范正文 | 无 | R1/R2 复核通过，文档交付通过；已提交用户仓 `abee940` | 见 07 本次复核 |
| S2 Defect 项目依据 | S1 | 主入口/角色及 N3 复核通过；已提交 Defect main `e342b7f` | 见 09 最新复核 |
| S3 WalletKit 项目依据 | S1 | 文档交付复核通过，运行期行为待 S6；已提交 WalletKit main `7f2bef0` | 见 09 §5 与原实施记录 |
| S4 Story 项目依据 | S1 | 主入口/角色、原义务及 N4 复核通过；已提交 Story `62d9467c`（只含本任务段落） | 见 09 最新复核 |
| S5 用户级三项补充及维护诊断 | S1–S4 | 用户条款及安装文件静态核对通过；S5-R1/R2 复核通过；两宿主新会话发现与调用经用户 2026-09-13 决定不做专门验证，改为使用中观察（未验证）；用户条款与 Skill 文件已提交用户仓 `abee940` | 见 [10-S5实施评审](10-S5实施评审.md) 与下方“S5 记录”“S5-R1/R2 修正记录” |
| S6 维护体系验收 | S1–S5 | 未执行；T2（maintenance-agent 三次真实调用）经用户决定不做，记为未验证、使用中观察；其余收口待设计者判断 | 见“下一动作”中的用户决定 |

以下 S1–S3 为实施者交回记录；自检与设计者审查结论分别记录，当前结论以本表及 07 为准。

## S1 记录（2026-09-13）

- 改动：`C:/Users/kangz/.agents/AGENTS.md` 按四节重写（新增“角色与工作对象”，合并设计、方案、表达与验证要求，删除旧“Agent 产品维护”指针段）；`cp` 同步到 `.codex/AGENTS.md`、`.claude/CLAUDE.md`；删除未跟踪的旧 `.agents/maintenance.md`（三个项目及用户入口无有效引用，Defect CHANGES.md 命中为无关文件名）。
- U1–U6 落点：U1 角色与工作对象第 4 条；U2 同节第 1–5 条；U3 设计与改动第 3、5 条及方案与文档第 4–5 条；U4 设计与改动第 2、5 条及表达与验证第 4、7 条；U5 设计与改动第 6 条；U6 表达与验证第 3–4 条及方案与文档过程文件条。
- 验证：见 R1–R5 修正记录中的最新内容标识；正文检索无 maintenance、Skill、项目名、项目路径、预算或 Case；授权、目录和重写约定保留。
- 未验证：新会话实际加载与行为（S6）；被测模型会话对新增内容的影响仅按“内容中性”静态核对。

## S2 记录（2026-09-13，AIDefectHelpler）

- 当前改动：根 `AGENTS.md` 仅“两种角色”标题改“维护与消费”、执行者改称消费模型，其余保持原文。`CLAUDE.md` 删除与根 AGENTS 重复的导航与状态义务，只留 `@AGENTS.md`。`test/product/AGENTS.md` §3 标题改“维护与消费边界”、执行者改称消费模型，维护者职责原文保留。`docs/PROJECT.md`、`README.md`、`docs/STATUS.md` 与 HEAD 一致。
- 自检后恢复：首轮实施删除了 STATUS 进度可视化与 ☑▶☐、README 系统构成表与公开产物列、PROJECT §5 自建词法的失败原因、根 AGENTS 十二理念/app 特点/红线全文，并收窄了测试 AGENTS 维护者职责；这些删除超出方案或未核对读者与承接，已按 HEAD 恢复。
- 核对：STATUS 读数与 `implementation-state.yaml` 一致（29 项、完成 2 项；各阶段 2/2、0/8、0/5、0/9、0/5；正在做 1.1、下一个 1.2），无需修改。
- 验证：`git diff --check` 通过；S2 路径外的在途修改（.gitignore、demo、20260903/20260905 方案、未跟踪 node 目录）未动。

## S3 记录（2026-09-13，AIWalletKit）

- 当前改动：根 `AGENTS.md` §1 改“维护与消费”，合并删去“澄清需求、制定方案”及同文件 §5.1/§6.2/§8 已具体承载的“交付可达、边界、完成条件”句；§2 改“接入能力定位”；§5.2 删与同文件 §2 同义的机械事实条；全文执行者改称消费模型。`README.md` 删十一个文件清单，改用途摘要并链官方资产清单。`task/README.md` 增加“状态以各任务目录为准”说明，原状态说明保留，与目录内 README 不一致的 cli-parallel、skill-redesign 两项标“待核”。`test/walletkit/AGENTS.md` §1 标题改“测试模式中的维护与消费”并改称谓。`TEST.md` 只把 6 处执行者改为消费模型。
- 自检后恢复：首轮实施删除的根 AGENTS §7.1“不围绕最终报错增加特例”、§7.2 中间态与迁移桥义务、§8 分步自检，测试 AGENTS §7 迁移桥义务与 §8“无主迁移桥或平行真源”自检，以及 task/README 的状态说明，均属本项目具体义务或导航，已恢复原文。
- 验证：`git diff --check` 通过；工作区只有 S3 五个文件修改；无残留“执行者/只有两种角色/十一个文件”；资产清单链接可达。
- 未处理：task/ 下 08-22 两轮、08-26、09-03 目录未列入导航（是否属当前优化需维护者判断）；协议、资产、Truth/Case 未改。

## S4 记录（2026-09-13，Story，T1 实施会话）

- 取得依据（T1-1）：宿主注入的用户级 `.claude/CLAUDE.md`（S1 已核与 AGENTS 同内容）和项目根 CLAUDE.md；首次编辑前读了总览、STATUS、07、01、02、03C、05、test/story/AGENTS.md 全文、TEST 任务索引及称谓命中段，还读了 03A/03B/04/06 作参照。
- 开工工作区（T1-2）：HEAD `239a025b3a3c681b3d4088a47335c6b7b00368d3`。AGENTS 在途 diff 为 §7.5 整节改写（维护预算与分级复核）；TEST 在途 diff 为 §7 并行说明、`compileall -j 0`、§7.9 并行实测与 `-k` 行，以及第 7 项预算判读句。另有预算 yaml 开头 reviewer 裁定注释与 `interim_ceiling`、test_mechanism_budget.py、test_story_build.py、R01 夹具和四个 core mjs 的在途修改。以上均保留，未要求先提交。开工时把 7 个本步文件复制到会话 scratchpad `s4-before/`，本轮差异按它对照，不计入 HEAD 在途差异。
- 实际改动（T1-3/T1-4），均相对 test/story：
  - `AGENTS.md`：“执行者”24 处改“消费模型”，均指使用 Extension 的模型，§7.5 无命中。§1 标题改“维护与消费”，§1.2 标题随之改。§1.1 末段补“历史记录沿用旧称‘执行者’，按语境区分，不追溯改名”。§0 轮次项改为“当前轮次 → 该总览给出现行实施入口”，链接不变，FEATURE 暂存说明不变。其余条款、§7.5 在途内容和 §8 均未改；§7.3 的“方案维护者/实施者”原文保留。
  - `TEST.md`：§7.0.2、§7.2、§8 第 6 项说明和 §10.6 共 4 处“执行者”改“消费模型”，命令、授权、隔离、评分协议未改。任务索引与 AGENTS 指针已能分流，无需改。
  - `scripts/check_failure_modes.py` m02 docstring、`tests/test_narrative_variants.py` 模块及 `TheAnswerIsNotInTheDeliverable` docstring、`tests/test_requirement_system.py` `TheDefaultEntryFindsTheProjectRoot` docstring：执行者改消费模型，verifier 保持不变。
  - `tests/test_run_measurement.py` `DesignArtifactsStayOutOfTheIndex` docstring：执行者改维护实施者。
  - `regression/mechanism-budget.yaml` “三个角色”注释（现第 15/17 行，因在途头注释下移）：维护者改维护设计者，执行者改维护实施者，“评审”保持；预算键值和第 82 行历史 reason 中的“执行者”未改。
- 验证（T1-5）：7 个本步文件 `git diff --check` 通过；4 个 py 文件 `py_compile` 通过。按快照做字符级 `git diff --no-index --word-diff`，只出现上述称谓、§0 和 §1 改动，无断言、语句、预算数值或在途段落变化。test/story（不含 design）剩余“执行者”只有 AGENTS §1.1 的旧称说明和预算历史 reason。全仓（不含 framework）没有对“只有两种角色”或 AGENTS §1 的引用，无链接需同步。
- 读取路径核查：AGENTS §0 → `plan/2026-09-11-Extension旧机制退场与新机制替换/00-总览.md` → `13-实现质量替换/00-执行总览.md`，均存在，与当前 Q5 线路一致。运行/离线/评价由 TEST 任务索引分流。
- 未验证/未处理：未跑 pytest，仅改 docstring 与注释，按 S4 无需新测试。根 AGENTS/CLAUDE 按范围不改，故不宣称普通新会话自动路由已解决。`test/story/plan/` 历史方案（含退场总览第 7 行“执行者”指维护实施者）和 EVOLUTION 不追溯。
- 工作区同时出现本步以外的并发修改：约 26 个 `fixtures/failure-modes/*/{bad,good}/.../story.md`，以及未跟踪的 `B01.../_probe_check.mjs`。它们应属其他在途任务，本步未触碰。

## S4 修正记录（2026-09-13，按 09 与修正后 03C）

- 输入：08、09、修正后 00/03C/05 的 S6 项目层三项检查、用户级角色段（宿主注入）、当前 AGENTS §0–§1/§7.3、TEST §0.1–§0.2。先前的称谓修改和七文件安全证据按 08 复用，不重做。
- `AGENTS.md` §0：删除固定的 2026-09-11 轮次链接和 FEATURE 暂存/移入安排，相应文件未动。“维护 Extension”改为按本次任务取得需求、设计和状态记录。“判定当前需求”采用 03C 的任务定位语义：以用户本次目标、需求、计划和状态为输入，在 spec/design 中按该任务查找，歧义时补齐，不默认进入日期或最新轮次；`doc/features/*` 是历史产物的句子保留。
- `AGENTS.md` §1 改为“维护与消费的角色”：
  - 引言说明三角色，“维护者”只作前两者合称，不由一个会话包办方案与实现，并保留旧称说明。
  - §1.1 三角色表承接原“维护者”五项：定位、澄清/方案/验收、审查和按证据决定下一轮归维护设计者；实现、writing-for-agents 送达、运行验证归维护实施者。另写明 §7 的“方案制定者/reviewer/评审”属维护设计者职责，确认权限按 §7.5。
  - 共同义务承接不进入业务管线、CLI 宿主代理身份与回复边界，以及 TEST 宿主/观测者/需求方代理，宿主由本次任务指定的维护角色担任。
  - §1.2 消费模型原文保留；verifier 句改为“产品内部的独立审查能力，按 Framework + Extension 的使用流程工作”，删去“第三种项目角色”。
- `AGENTS.md` §7.3：方案拆步归维护设计者，单步实施归维护实施者（独立会话），从实际文件还原行为的审查归维护设计者。评审意见同步中，方案与验收由维护设计者改，直接消费者由维护实施者按方案改。其余句子和 §7.5 在途内容未改。
- `TEST.md` §0.2：宿主身份补“由本次任务指定的维护角色担任（分工见 AGENTS.md §1）”，协议未改。
- 验证：两文件 `git diff --check` 通过。与开工快照逐行对比，AGENTS 变化只在 §0、§1、§7.3 及已登记的称谓行，§7.5 无差异；TEST 只多 §0.2 一句。test/story 下 tests/scripts 没有读取或断言 AGENTS 角色/轮次正文。
- 任务独立性推演：本任务（plan/2026-09-13-agent-maintenance-system）和 Q5 实现质量替换（plan/2026-09-11…/13-实现质量替换）都从 §0 进入，再按用户给定任务到 design 下定位；AGENTS 不再把任一任务送往另一轮，换任务无需改长期规范。
- 原义务核对：原 §1.1 五项、CLI 代理两句、分工/隔离一句、§1.2 与测试角色句均有落点，没有删除事实、隔离、迁移或验收条件。
- 未处理：`EVOLUTION.md` 第 8 行仍写“当前工作入口为 spec/2026-09-04…”，属历史文件、不在 S4 文件表，是否清理交设计者判断。AGENTS §8 与 TEST 中的“本轮”泛指当次任务或 suite，不属绑定。新会话行为待 S6。

## S2/S3 修正记录（2026-09-13，按 09 与修正后 03A/03B）

开工快照：会话 scratchpad `s2-before/`（Defect 4 个文件）、`s3-before/`（WalletKit 5 个文件）。本轮差异按快照对照，先前已核准的称谓、导入去重和 R3–R5 恢复不重算。

### S2 Defect（HEAD `042808126884bf1d6fd465205e92c6d8ec316dd3`）

- 根 `AGENTS.md`：
  - 开头“新会话实现任何需求前先读 PROJECT”改为“维护本产品时先读 PROJECT；业务任务按 §6 执行路径”。
  - §4 改为“维护与消费的角色”：引言规定“维护者”只作合称；三角色表中，原“产品需求、方案、实现、评测和演进”拆为设计者（需求、交付能力、知识/感知职责、方案、评测范围与验收、评审、演进决定）和实施者（交付能力、契约与测试资产的修改、已定评测与门禁、材料同步）。
  - 共同读取与记录保留 PROJECT → STATUS 必读、测试域 AGENTS/TEST 和“完成原子或步骤后更新 STATUS”；原“再读当前建设方案”改为本次方案以用户任务为准，未明确时在 `docs/specs/` 定位，不默认进入 STATUS 当前在建方案。
  - §6 维护路径同步为“PROJECT → STATUS 了解现状 → 本次任务的方案 → 测试域”。消费模型段、§1–§3、§5 红线未改。
- `docs/PROJECT.md`：
  - §5 删去“（2026-09-11 一轮）”“（2026-09-12 一版）”和提交号 `52cbe55`，回退、ArkAnalyzer 事实层和词法退役条件原样保留。
  - §7 第 2 步改为“本文件与本次任务的方案”。
  - §11 改为维护时读本文件与 STATUS 了解现状，本次方案以用户任务为准，STATUS 的当前在建方案不作为所有任务的默认方案。
  - §8 恢复句未动。
- `test/product/AGENTS.md` §3 改“角色与边界”：设计者负责需求分析与方案、评价范围和判据、评审和演进决定；实施者负责实现交付能力、维护测试装置、执行已定验证并交证据；维护者为合称，并保留“按最早责任层处理”句。消费模型句不变；Oracle/Evaluator/Verifier 改为“评测机制名称，不参与上述角色划分”，其余边界不变。
- CLAUDE、README、STATUS 本轮未改；`test/product/common` 只有产品内部“维护工作流”消费者，不改。
- 验证：本步路径 `git diff --check` 通过；四文件与快照逐行对比只含上述变化。Select-String 剩余命中：PROJECT 第 128–129 行“执行者”指产品引擎执行模型（产品内部）；第 207 行是 STATUS 现状指针。
- 未处理：`product/contracts/README.md` 第 20 行“由当前建设方案（PROJECT §11 指向）按阶段新增”属产品契约文档、不在 03A 文件表；`test/product/AGENTS.md` §2 的“（2026-09-13：…）”日期叙事不在 §3 动作范围。两处交设计者判断。

### S3 WalletKit（HEAD `0fd3301d9afe8892ac87b8400a06a6721464be39`）

- 根 `AGENTS.md`：
  - §0 维护入口由“读取当前未完成任务的方案与状态”改为按用户本次任务取得，`task/README.md` 只作查找，不默认续接某一轮。
  - §1 改“维护与消费的角色”，三角色表承接原维护职责：查明事实、设计合同/加载链/资产使用/验收、定位问题、依据证据评价归设计者；更新 Skill/资产接入/Truth/Case/测试装置、调度 CLI 并交证据、同步消费者归实施者。R5 代理需求方原句保留，消费模型段不变；机制句改为“机制名称，不参与上述角色划分”。
  - §5.2“测试维护者”评价改维护设计者。
  - §7.2 实施会话/评审者分别改维护实施者/维护设计者。
  - R4（第 36 行）和 R5（第 25 行）在位。
- `test/walletkit/AGENTS.md`：
  - §1 改“测试模式中的角色”：设计者负责测试范围、隔离要求、评价判据、独立评价与归因；实施者负责编排/隔离/证据装置、运行已定测试并交证据；维护者为合称。需求方代理由本次任务指定的维护角色担任，三条回复边界与“不用 Skill/Case 证明测试自身”原样保留；机制句同根文件。
  - §3 表“维护者评价”、§5.1 和 §5.2 的评价改维护设计者；§7 改维护实施者/维护设计者。
- `test/walletkit/TEST.md`：§0 补分工指针，§6 建立 evaluation 与 §6.6 裁决改维护设计者；命令、Case 选择、授权、评价与恢复协议未改。
- `task/README.md` 导航句补“维护任务按用户本次目标查找对应材料，不默认续接下列某一轮”。
- README 本轮未改。
- 验证：五文件 `git diff --check` 通过；与快照逐行对比只含上述变化；Select-String 在四个规约文件中没有“另一种角色/测试维护者/评审者/当前未完成任务/执行者”残留。

### 三项目共同核对（05 §1 项目层检查）

- 任务独立性：三个项目入口都改为“用户本次任务 → 按目标在既有方案目录查找”，状态页/任务索引只作现状或导航，换任务无需改长期规范。
- 三角色：各项目根入口和测试入口都有设计者/实施者职责落点，消费模型原定义保留，“维护者”只作合称，机制名称不再定义角色数量。
- 原义务：各段对照快照，原职责逐项有落点；事实、隔离、迁移桥、自检和测试协议没有删除。
- 未验证：新会话实际按新入口工作的行为待 S6；三仓均未提交。

## R1–R5 修正记录（2026-09-13）

- R1：用户 `.agents/AGENTS.md`“表达与验证”第 3 条替换为 07 给出的原文（责任来源维护、各入口按读者和使用时机交付、摘要标来源并同步）。
- R2：“角色与工作对象”改为以维护 Agent 产品为适用条件，使用维护设计者、维护实施者、消费模型；写明维护设计者不代维护实施者修改产品、消费模型执行产品内部 spec/plan 阶段仍是产品使用方、角色由用户指定。其余用户规则未改。
- R1/R2 同步：`cp` 到 `.codex/AGENTS.md`、`.claude/CLAUDE.md`；三份 `git hash-object` 均为 `89aa21d510425568baf90f7446d24e7bf1362544`；`git diff --check` 通过。
- R3：Defect `docs/PROJECT.md` §8 原位置恢复“删除失效功能、契约、fixture 和测试时同步关闭其引用”；`git diff --quiet` 确认 PROJECT 与 HEAD 一致。
- R4：WalletKit 根 `AGENTS.md` §2 恢复“Skill、引用资料、官方资产、脚本、Truth、Case 和报告都是载体；”，行为链与证据边界未动。
- R5：WalletKit 根 `AGENTS.md` §1 改为“维护者在 CLI 实跑中可以代理普通需求方作必要回复，但仍属于维护者；不得把测试答案、维护历史或具体修法提供给消费模型。”其余 §1 合并内容保留。
- 验证：两个项目仓本步路径 `git diff --check` 通过；R4/R5 原文经 grep 确认在位。

## N3/N4 记录（2026-09-13）

- N3（Defect `product/contracts/README.md`，开工无在途修改）：
  - 第 3–4 行按 09 原文改为“跨能力协作的现行公开契约。系统分层与产品边界见 docs/PROJECT.md；现行字段、枚举和校验约束见本目录正式 JSON Schema 及本文说明”，沿用原 PROJECT 相对链接，删去 core-loop-v2 草案链接；草案文件未动。
  - 第 19–21 行四类新增改为“按用户本次确认的任务和契约变更办理”，facts/普查不是公开契约的句子，以及“先在矩阵登记生产者/消费者/层再进入 SCHEMA_NAMES”的义务保留。
  - 契约矩阵、校验分层、schema 和 gate.py 未改。
- N4（Story `test/story/EVOLUTION.md`，开工无在途修改）：
  - 标题改“Story 演进记录”；页首改为“记录对应日期或版本的代码事实、证据和待验证边界；当前任务以用户目标及现行规约确定”，后一句历史约束保留。
  - 第 1 节改“演进记录”；9 月 7 日记录“当前工作入口”改“当时工作入口”。
  - 其余日期、链接、事实和历史决定未改。
- 验证：
  - 两文件 `git diff` 只含上述行，`git diff --check` 通过。
  - 引用排查：Story 仓（不含 framework）无指向 EVOLUTION 旧标题或锚点的链接；Defect 仓（不含 docs/specs）只有 README.md:46 与 docs/product/knowledge-sync/contract.md:5 引用契约 README，均指向契约矩阵，不受影响；无其他现行文件引用 core-loop-v2 草案。

## S5 记录（2026-09-13）

### 用户级三项局部修订

- 编辑源 `C:/Users/kangz/.agents/AGENTS.md`，开工内容标识 `89aa21d…`，与 S1 复核一致；用户仓 HEAD `067018ff28bc034a79d0fc3837fd265ff77af585`，三入口仍为 S1 的未提交修改。
- 设计与改动第 6 条（生产者、消费者和验证位置）合并完整退场：明确新增、保留、替换和删除；被替代或失效的旧机制及其专用测试随完整需求交付退出，包括指令、实现、状态、入口、兼容分支、配置和文档引用；仍有效的业务能力及回归覆盖保留或迁移，没有替换对象的新增不制造删除项；过渡路径写消费者与退出条件；验收同时核新行为与旧路径退出。
- 设计与改动第 7 条（实施前核对工作区……评审……）融入适用性：实施依据真实契约与适用范围，样例、夹具和单次报错用于理解问题；特殊分支须有业务或协议依据；评审检查是否依赖样例名、固定值或单一场景，并用其他合法输入或相关异常路径核实；有效协议常量、已确认业务规则和有界场景差异保留，不过度泛化。在途修改保护和责任归位原句保留。本条适用所有任务，因此写成“实施/评审”，没有使用限定维护 Agent 产品的角色名。
- 方案与文档第 5 条改为交付规模：通常拆 1–4 个可独立验收步骤；超过时先审视边界，优先拆成多个需求，拆出需求的目标和范围按用户授权确定；无法拆分时说明必要性，不为凑步数合并或遗漏。原有“多目标用总览加步骤文档”和交付前推演要求保留。
- 同步：`Copy-Item` 到 `.codex/AGENTS.md`、`.claude/CLAUDE.md`；三份 `git hash-object` 均为 `c1ccf05119c08f0d41af216d0b62a2461a2e1cea`；限定三路径的 `git diff --check` 通过。
- 只改三条的证据：`89aa21d` 未写入 Git 对象库，无法直接 diff。改用逆向核对：在 scratchpad 把当前编辑源里的三条新句逐一替换回原句（每条均唯一命中），`git hash-object --no-filters` 结果为 `89aa21d510425568baf90f7446d24e7bf1362544`，即除这三条外全文与 S1 通过版本逐字节一致。
- 完成条件核对：三项分别进入原条款，没有新增同义规则清单；角色、授权、文档处理和读者边界未动；退场区分旧机制专用测试与有效回归；适用性同时约束实施与评审，并保留有效协议常量。
- 未验证：新会话加载后的实际行为待 S6；未提交。

### maintenance-agent 主体与安装

- 主体（编辑源）：
  - `C:/Users/kangz/.agents/skills/maintenance-agent/SKILL.md`（79 行）：frontmatter 与 04 逐字一致；正文由 04“诊断能力与产出”和“执行步骤”改写，含六项诊断内容、判断尺度及五步，每步写明完成条件。去掉了本计划步骤号、部署和验收说明。
  - `agents/openai.yaml`：与 04 逐字一致。
  - 没有 references、scripts、状态记录或第二个 Skill。用户级来源写成“宿主已加载的用户级 AGENTS/CLAUDE 及其声明的编辑源和同步副本”，不写死本机路径。
- Claude 跳板：`C:/Users/kangz/.claude/skills/maintenance-agent/SKILL.md`（9 行），按本机 implementation-loop 跳板格式写：frontmatter 与主体前 5 行 `diff` 一致，正文一行链接 `../../../.agents/skills/maintenance-agent/SKILL.md`，已核能解析到主体。没有复制 agents 或正文，也没有建 junction。
- `.gitignore`：原文件以 LF 结尾，末尾追加 `!.claude/skills/`、`!.claude/skills/maintenance-agent/`、`!.claude/skills/maintenance-agent/SKILL.md` 三行；`git diff --check` 通过。
- 状态核对：
  - `git status --short --ignored --untracked-files=all -- .claude/skills` 只新出现跳板文件。
  - `check-ignore --no-index` 显示跳板命中第 38 行放行规则。
- 事实更正：01 说 implementation-loop 跳板“被忽略”不准确。它早已被 Git 跟踪（`git ls-files` 可见），只是规则上命中第 1 行 `*`；追加后它的跟踪状态和规则命中都没有变化。
- 主体检索无 design 路径、STATUS、S1–S6、本轮/反思、项目名或日期。用户仓 HEAD `067018ff…` 和分支 main 未变，未提交。
- 未验证：
  - Codex 新会话能否显式发现并调用 `$maintenance-agent`、Claude 新会话能否发现 `/maintenance-agent` 并读到主体，都需要在新会话中实测，本会话无法代替。两个宿主暂不声称已支持。
  - 核心诊断能力按 S6 的 T2 验证。

## S5-R1/R2 修正记录（2026-09-13）

只改 `C:/Users/kangz/.agents/skills/maintenance-agent/SKILL.md` 正文五处；frontmatter、openai.yaml、Claude 跳板、`.gitignore` 和用户条款均未动。

- S5-R1（第 2 步取清单）：
  - 原“用 `git ls-files` 取完整清单”改为按当前工作区取清单：Git 仓内合并 `git ls-files`（已跟踪）与 `git ls-files --others --exclude-standard`（未跟踪），再用文件工具补看本次相关的被忽略材料（如本地方案和状态记录）。按项目约定跳过依赖缓存和生成物。补一句说明只列已跟踪文件会漏掉正在交付的新内容。
  - 没有新增脚本、登记表或状态记录。
- S5-R2（非 Git 与版本信息）：
  - 第 1 步项目根：明确不在 Git 仓时以 cwd 为根，Git 根与 HEAD 记“不适用”；权限、信任或工具错误记“未取得”并写原因，这类错误不说明没有仓库。用户级来源按同样规则记录。
  - 第 1 步完成条件：改为确定对象、两级材料位置和计划路径，并记录 Git 根与 HEAD 或“不适用”“未取得（原因）”。
  - 第 4 步 plan.md“目标与事实”：记录可得的 Git 根与 HEAD，非 Git 记不适用，未取得的写原因，不推测版本；版本缺口影响某项结论时，把该结论列为待核。
  - 第 5 步：索引、分支和 HEAD 的核对限定在 Git 仓内。
- 验证：
  - R1：Defect `product/common/arkts/node` 已跟踪部分为空，合并未跟踪后得到 `package.json`、`package-lock.json`。被 Git 忽略的 `docs/specs/project/20260905-wallet-app-productization/` 方案文件可用文件工具列出，不会因未入 Git 被排除。
  - R2 正常 Git：Story 仓 `git rev-parse` 返回根 `E:/Project/SimulatedWalletForHmos` 与 HEAD `caa79c5…`（另一会话的新提交，与本步无关），exit 0。
  - R2 明确非 Git：scratchpad 内目录受用户仓 `C:/Users/kangz` 包含，首测误得用户仓根；设 `GIT_CEILING_DIRECTORIES` 截断向上查找后返回 `fatal: not a git repository`，exit 128，对应“不适用”。
  - R2 获取失败：`PATH` 置空后返回 `git: command not found`，exit 127，与“不是仓库”区分，对应“未取得（原因）”，不要求补造 HEAD。
  - 主体仍为 79 行，frontmatter 与跳板一致，正文检索没有计划路径、步骤号、项目名或日期。用户仓 HEAD `067018ff…` 未变，状态只含 `.gitignore` 与三个新文件，`git diff --check` 通过。
- 未验证：两宿主新会话发现与调用；实际诊断质量待 S6。未提交。

## 下一动作

N3/N4 与 S5-R1/R2 均已复核通过；用户条款及 S1–S4 不重做。

用户决定（2026-09-13，原话：“无需验证这个skill，后续我用的时候再看效果”）：

- 不做 maintenance-agent 的两宿主新会话发现与调用验证，也不做 S6 T2 的三次真实调用。Skill 效果由用户在后续实际使用中观察。
- 由此，Codex/Claude 能否发现并调用，以及诊断与计划质量，均记为“未验证”，不按通过登记。静态核对结论（文件、元信息、跳板、放行规则、R1/R2 语义）仍然有效。
- S6 中 T1（S4 真实实施证据）与项目层三项检查的汇总是否仍需单独收口，由设计者判断；实施者在得到指示前不自行宣告 S6 完成。
- 用户仓已按用户要求提交（2026-09-13，main `abee940`）：三份用户入口、`.gitignore`、maintenance-agent 主体两文件及 Claude 跳板，共 7 个文件。工作区里另有用户自己的 `.claude/settings.json` 修改（插件启用与模型设置），与本任务无关，没有包含在内。
- WalletKit 已按用户要求提交（2026-09-13，main `7f2bef0`）：根 AGENTS、README、task/README、test/walletkit/AGENTS、TEST 共 5 个文件，也就是 S3 的全部改动，提交后工作区干净。
- Defect 已按用户要求提交（2026-09-13，main `e342b7f`），只含本任务 5 个文件：根 AGENTS、CLAUDE、docs/PROJECT、test/product/AGENTS、product/contracts/README（N3）。其他任务的在途修改没有纳入，仍留在工作区：.gitignore、demo/sdk/Framework/BuildProfile.ets、20260903/20260905 方案记录、未跟踪的 product/common/arkts/node/。
- Story 已按用户要求提交（2026-09-13，story 分支 `62d9467c`），只含本任务的段落：
  - `AGENTS.md` §0、§1、§7.3 和各处称谓；
  - `TEST.md` §0.2 一句和 4 处称谓；
  - `EVOLUTION.md` 页首（N4）；
  - `regression/mechanism-budget.yaml` “三个角色”注释的两处称谓；
  - `tests/test_narrative_variants.py` 两处 docstring。
- 做法：三个混有其他任务改动的文件（AGENTS、TEST、预算 yaml）按 HEAD 加本任务改动生成暂存版本，工作区文件没动。已核对：暂存区相对 HEAD 只有本任务段落，工作区相对暂存区只剩其他任务段落。
- 未纳入、仍留在工作区的其他任务修改：AGENTS §7.5 预算分级改写；TEST §7 并行说明、§7.9 并行实测、第 7 项预算判读；预算 yaml 头部 reviewer 注释、`interim_ceiling` 与 total；`test_mechanism_budget.py`；提交时新出现的 `story-build.mjs`、`test_verifier_report_protocol.py`。
- 本任务早先改的三个 py docstring（`check_failure_modes.py`、`test_requirement_system.py`、`test_run_measurement.py`）已由其他会话的 Q2/Q6/Q7 整文件提交带入 HEAD，本次无需再提交。
- 用户随后要求把 AGENTS.md 和 TEST.md 的剩余修改一起提交（2026-09-13，story 分支 `913bca77`）：AGENTS §7.5 维护预算与分级复核，TEST §7 并行说明、§7.9 并行实测与 `-k` 命令、第 7 项预算判读。提交前核对过，两个文件的剩余差异只有这几段。提交后 AGENTS §1 引用的“方案制定者/reviewer”与已提交的 §7.5 对上，此前记录的中间态已解除。
- Story 工作区仍未提交的修改：`regression/mechanism-budget.yaml`（头部 reviewer 注释、`interim_ceiling` 与 total）、`tests/test_mechanism_budget.py`，以及其他会话正在改的 `story-build.mjs`、`tests/test_verifier_report_protocol.py`。

## 计划检查

当前有效决定：S1 用 U1–U6 和文件一致性作静态验收；S6 绑定 S4 的真实新会话任务及三次工具调用，明确评审者和判负条件。S5 每次完整诊断，不做增量复用、不保存状态记录、不设 `.maintenance-agent/` 归档；只有 maintenance-agent 一个 Skill，主体在 `.agents/skills/maintenance-agent/`（SKILL.md + agents/openai.yaml），与用户级、项目级规约相互独立；Claude 只放跳板 SKILL.md，经用户仓 `.gitignore` 白名单跟踪。过程文件一律不归档，只归档有用的状态与结果，已有归档历史的仓不追溯（S2 不改 docs/specs/README）。

Defect 已核到 0428081，common 域和在途修改已列明。Story 当前 AGENTS 修改位于 §7.5，S4 基于工作区继续，并明确具名注释的角色含义。Claude 安装按 S5 的既定跳板方式处理。

文档检查只评价当前计划。规约部署后仍需按 S6 观察新会话的读取、判断和交付，不能据条款存在声称相同错误已不会发生。

## 读取与记录

实施只需总览、当前步骤及具名材料；[本轮反思](06-本轮设计反思.md) 只供追溯，不是额外规则。S6 以实际诊断和计划质量判断核心功能。

用户级规范只有 AGENTS.md 和 CLAUDE.md，要求直接写入正文；本机 AGENTS 的两个既有落点同步。旧独立文件及维护指针在 S1 核实承接后退出。maintenance-agent 只由人调用，读取两级规约作完整诊断，不保存增量状态。

## 历史与范围

所有设计文档维护本地当前稿，不归档、不提交，不因 ignored 而强制加入 Git；已存在历史材料不再更新。当前目录被 Git 忽略符合这一要求。

其他维护任务的在途修改不回滚。
