# SimulatedWalletForHmos 维护契约

> 本仓维护 Story Extension。本文是项目级唯一维护契约，写给维护设计者与维护实施者；消费模型在 `demo/` 或隔离 workspace 里工作，
> 不读本文件、`doc/`、`doc/archive/` 与 `test/`。角色定义、方法和交付要求按用户级 AGENTS，本文只写本项目特有的对象、事实、约束和入口。

## 0. 入口

| 对象/任务 | 权威位置及读取时机 |
|---|---|
| `extensions/` | Story Extension 开发源（机制、知识样板；宿主入口由 Framework 按 manifest 物化） |
| `demo/` | 完整消费工程：业务代码与业务文档、`framework/` 发布件、消费配置、宿主物化与已安装的 Extension（发布版） |
| `doc/` | 项目文档：`spec/` 需求与版本范围，`plan/` 方案、评审与交回，`release/` 按版本的发布说明（只写本版增量）与 AI 交付流程说明；`features/` 是 CLI 测试回流的需求产物（不入库） |
| `doc/archive/` | 旧轮次维护资料；追溯旧设计、评审和未完成项时从 [归档入口](doc/archive/README.md) 查找，当前任务仍从 `doc/spec/`、`doc/plan/` 进入 |
| `README.md` | 项目说明与使用指南，只写当前状态；维护者据此分发给使用者 |
| `test/` | 测试域：测试协议、脚本、Case、夹具、回归台账、金样、演进记录与本地需求系统 |
| `tools/cli/` | 实跑用的 CLI runtime |
| `output/` | 不入库：`output/story/` 放运行证据，`output/scratch/` 放临时脚本、临时工作区与 pytest 缓存 |

`extensions/` 是当前开发版；测试时它被装进从 demo 复制的一次性 template；demo 只在正式发布时更新，平时保持上一个发布版。

版本目标、分支安排、实施进度与当前交接入口记录在对应的 spec/plan 中；本文维护项目长期适用的职责、所有权和工作规则。

- 维护任务以用户本次给定的目标、需求、计划和状态为输入，在 `doc/spec/`、`doc/plan/` 中按该任务查找已有材料；新需求命名与批次/步骤按用户级约定，旧任务原位接续；对应不上时先补齐歧义。
  `doc/features/*` 是测试回流的运行产物，其下 `archive/` 按批次存历轮起跑前的归档；维护需求在 `doc/spec/`。
- `doc/spec/`、`doc/plan/`、`doc/release/` 与 `doc/archive/` 随提交留下历史；归档版本号属于对应旧轮次，复用前核当前需求与实际接口。运行证据（事件流、运行日志、截图、材料原件、压缩包）放 `output/story/` 并在过程件里按路径引用；
  临时脚本与临时工作区放 `output/scratch/<本次任务>/`。
- 运行、修改或评价测试按 [test/TEST.md](test/TEST.md)，命令、状态、证据与评分只在那里维护；测试命令从仓根执行。
- 定方案、开工与评审先读 [TEST §6.5](test/TEST.md#65-维护标准与评审)、[全量评价标准](test/regression/extension-acceptance.md)及本版 `doc/spec/<版本>/评价标准变更.md`；先核标准再实现，按对象取证。
- [test/EVOLUTION.md](test/EVOLUTION.md) 记录演进与规则来源，是追溯证据，不是当前实现依据。
- `demo/framework/` 是 AgentMaison 发布件，只读，变化只经 §6 进入 demo。本仓根不挂 Framework 的阶段钩子与写保护钩子，只读边界由维护者遵守。
- 新 checkout 先按下方「维护环境准备」恢复依赖。
- 维护范围只覆盖 interactive 运行模式；Framework 的 headless/goal 能力不在 Extension 的兼容、状态与测试范围内，用户明确提出时另立需求。

### 维护环境准备

依赖目录不入库，clone 之后按下面装齐（PowerShell，在仓根执行）：

```powershell
python -m pip install pytest pytest-xdist pyyaml                     # 维护脚本与测试
cd demo/framework/harness; npm install; cd ../../..                  # framework harness（门禁、渲染脚本）
cd demo/.opencode; npm install @opencode-ai/plugin@1.18.26; cd ../..  # opencode 插件；package.json 由 opencode 生成、不入库
$env:OHPM_EXE = "<DevEco>\tools\ohpm\bin\ohpm.bat"                    # 鸿蒙依赖用本机 DevEco 自带的 ohpm 与 node
$env:DEVECO_NODE = "<DevEco>\tools\node\node.exe"
demo/scripts/build-dependence.ps1                                     # 重建 demo 各模块的 oh_modules
```

`package-lock.json` 不入库，harness 的依赖会解析到各自版本范围内的最新补丁版。人手试用 `/story` 还要装本地需求系统，见 TEST §1.3。

`doc/features/`是测试回流产物，不是维护需求；archive按批次保留。`doc/spec/plan/release`按本仓约定随提交留历史。运行记录在`output/story/`且永不清理；交回引用的原件、重放、计量等在`output/evidence/<题>/`，临时脚本/工作区在`output/scratch/<题>/`；具体以[TEST §0.4](test/TEST.md#04-东西放在哪)为准。

维护范围仅 interactive。Framework headless/goal 不纳入兼容、状态和测试，用户明确提出时另立需求；doctor/review读取现有证据，不自动启动真实运行；doctor仅新增本次诊断报告及必要证据副本，不改被审对象。

## 1. 本项目的角色职责

设计者负责 Extension 行为根因、职责设计、标准及效果评审；执行者实现、验证、同步并自动交回，对方案冲突有据质疑。维护者直接检查 Framework、Extension、知识、宿主、Harness、Verifier及测试的源码与证据，不用被维护系统自己的闭环证明其正确。

实跑宿主由本次指定维护角色担任，代理需求方边界按 TEST §0.3。消费模型只依赖需求、目标工程及 Framework/Extension 上下文；不向它投放维护方案、测试答案、失败用例或checker源码。读取checker按TEST§6.1调查：排查工具错误与据隐藏判据改产物分别归因。verifier是产品内独立审查能力。

## 2. 产品定位与所有权

评价消费模型完成未知需求的实际行为：输入事实→送达→理解/决定→产物→下游→恢复→证据。载体字段、代码和门禁只证明各自局部性质；确定性helper核其真实输入输出及消费者，用户可见组合效果按完整链验收。

| 部分 | 负责 / 边界 |
|---|---|
| Framework | 通用阶段、上下文装配、工具与宿主、verifier调度、闭环和公共扩展点；不管实例知识与Story专属语义 |
| Extension机制 | 需求流程、作者任务、阶段扩展、知识路由、产物合同与确定性辅助；不带目标专名/答案，不复制影子Framework |
| Knowledge | 目标仓项目事实、规约与设计模式，正文由目标仓维护；不管阶段调度、消费落点和维护历史 |
| Adaptation | 脚本按所有权安装升级机制/入口、写已适配版本，不读写知识；模型首装写部件定位知识，其余按演进主题逐题判适用（无适配版本从基线起），从目标仓事实写起步知识；后续扩充归目标维护者，不按目标业务改写通用机制 |
| 测试域 | 隔离输入、调度、观测、证据、回归和行为评价；不代消费模型做业务或注入答案 |

缺 Framework 能力回其所有者，不在 Extension 另建旁路。`demo/framework/`只读，版本/构建身份以其 RELEASE-MANIFEST.json 为准；正式交付经上游发布件与framework-init UPDATE进入。只有用户明确授权的单步验证可临时改副本，须保留上游基线、可复现补丁及临时放行失效条件。本仓根不挂Framework阶段或写保护钩子，由维护者守边界。

- `demo/framework/` 是 AgentMaison 的 vendored 发布件，版本与构建身份以 `demo/framework/RELEASE-MANIFEST.json` 为准。正式交付落在上游，经 framework-init UPDATE
  进入消费仓；本仓副本只在用户明确授权的单步验证中临时修改，交付时保留上游基线、可复现补丁和临时放行的失效条件。
- 本仓对 framework 的三组本地定制（opencode 子代理、dsh adapter 与审查员 Preset、专用 verifier 调用文字）的实际文件、接入后恢复与退出条件在
  [维护操作§2](doc/release/维护操作.md#2-framework-本地定制)维护。它们不含逻辑改动、不交上游，不随 story-adaptation 进目标仓；目标仓的宿主入口
  由它自己的 Framework 按扩展 manifest 物化。
- 测试 template 装的被测 Framework 与本地宿主定制只有一份来源：[`test/config/framework-under-test.json`](test/config/framework-under-test.json) 固定发布提交，
  `test/fixtures/framework-local/` 下的补丁保存相对它的三组定制（opencode 子代理、dsh adapter 与审查员 Preset、专用 verifier 调用文字），装配见 TEST §1.2；
  demo 正式接入同一发布件时按 §6 用同一补丁内容，不另维护第二份定制。
- `demo/.opencode/` 同时是 CLI 测试装置（Case 工作区从 demo 复制）：外网实跑用 opencode，内网用 codex。

## 3. 不变量

回归台账的clause继续按下列名称引用；通用方法在用户级Skill，以下保留本项目约束。

### 3.1 Agent-first

- **信息先于决策**：目标、事实、边界、能力、完成条件在动作前进入实际上下文；磁盘/登记/hook返回不等于送达。首次规则先于报错，错误说明缺口及正确恢复路径。
- **模型与脚本按能力分工**：模型判断语义、适用性、冲突、取舍、叙事与质量；脚本导入转换、枚举解析、结构检查、确定渲染、状态记录和可复现比较。表头/图语法/引用位置由模型选后脚本生成检查；词数/子串/相似度/字段存在只证明机械事实。新增确定性机制须说明必要性、原责任为何不能直接修及替换对象。
- **提示词不是执行保证**：按风险组合完整作者输入、确定性输入/状态/结构控制、独立verifier语义判断及隔离行为证据。作者与checker共用事实/结构/状态真源；确定性门一次报完整问题及前置缺失未执行项。verifier是纠偏安全网，主体目标为一次高质量完成，不固定生成或返修次数；helper按职责闭合，不强制全链实跑。
- **区分约束层级**：已定业务、工具协议与表达建议分别对待；模板/来源编排保存理解而非正文上限，允许有据深化。业务结论变化回真源，表达深化不增加审批或自证字段。

### 3.2 Extension 结构

- **按运行位置设计**：开发源在extensions，链接命令按消费工程安装位置`doc/extensions/`及宿主位置编写验证；测试装隔离template，发布才更新demo，对外adapt从demo已装发布版执行。
- **两层一桥**：机制为knowledge以外的skills/hooks/rules/contracts/manifest及宿主入口，走公共扩展点，对目标模块、SDK、业务名、绝对路径和Case零强依赖；knowledge是可适配样板，适配按所有权接入，目标维护知识。
- **机制层零测试特征**：机制/注入件无Case单号、测试业务或答案特征。按用户级review核所有模型可见的提示、代码、命名、注释、工具输出、输入与环境及实际生成内容；换合法题材/表达仍成立，不能由预列关系限制正常业务。中性例子与适用条件分开；当前需求业务名/数字核来源即可。机械回归见TEST§5.5，专名零命中不代签。
- **单一真源**：事实、状态、配置、编号含义、图登记和决定各有真源；派生视图由其生成。随工程变化的约定进合同/配置；域/条目/模式/角色从权威清单与正文派生，失败报错。ID只作身份追踪；Story/Review完整性由独立语义判断范围内事实、关系、流程、异常、验收和决定。
- **引用必须真实存在**：先核目标条目/章号/钩子/字段，改合同同步消费者。
- **显式不适用优于静默跳过**：下游无动作给理由；降级可观察且有条件，正常路径不靠静默降级。
- **正向表达**：交付面直接写目标、输入、动作、结果与恢复，禁止性规则保留必要边界。注释写当前责任/理由；案例、模型、suite、运行数字和维护历史留测试/演进域，退场在方案明确。
- **正向实现，不打补丁**：同一职责不新旧并存，新增导出有消费者，临时/TODO不跨轮遗留；替换旧机制完整退出。Extension不兼容历史功能/数据格式，遇旧格式明确报旧版收口或init重起；adapt演进记录只写扩展安装及知识/对接适配，不在adapt里处理旧需求；有效能力与回归保留，纯新增不造删除项。

### 3.3 Knowledge

- **知识三类与边界**：

  | 类型 | 回答 | 内容要求 |
  |---|---|---|
  | 项目事实 | 目标仓有什么、在哪里、通常怎样使用 | 真实路径、类名、API、封装形态和工程惯例；不写阶段路由与维护规则 |
  | 规约 | 什么条件下必须做或禁止做什么 | 一条一个可独立判断的要求，写清命中条件、边界与例外；实现专名引用项目事实 |
  | 设计模式 | 什么情形适用、由哪些角色协作、怎样验证 | 适用与不适用条件、角色、骨架和验证清单；目标仓是否采用由具体需求决定 |

  只收跨模块复用或全项目约束，单一业务模块与编码规范不入知识（编码规范归 Framework）。同一知识只在一个面登记。`manifest.yaml > provides.knowledge` 是知识激活清单的唯一来源，只登记路径；每份知识用 frontmatter 的 `kind`、
  `form` 与 `applies_when` 描述自己，机制按它把知识交给当前阶段。框架只读清单列出的文件，派生为空即报错。机制只维护消费时机和产物出口。
- **知识不含维护信息，定位只写一处**：知识正文只写给消费模型——项目概念、事实、已定规范、项目方法的应用步骤、选择依据、参考例子与完成判断；
  阶段目标、何时读、结果写进哪份产物与命令归机制（作者页、模板、任务包）。归属按「什么变了它才变」判；读写规则在机制侧
  `skills/story/reference/knowledge/protocol.md`，适配方法在 `skills/story-adaptation/reference/knowledge-adaptation.md`。
- **知识链**：验收「看到 → 理解 → 应用 → 传递」。看到：当前阶段需要的知识实际进入正确执行体的输入，适用与否由该阶段读后判断；
  理解：执行体结合当前需求判断适用、不适用或冲突，以判断、产物变化和独立审查为证据；应用：适用知识改变本阶段的具体产物、设计或契约实体，
  有可指认的业务落点；传递：下游读取上游已形成的判断与义务，提供落实证据或明确不适用。项目事实从蓝图设计起作为目标仓事实使用，发现错误回
  Knowledge 真源；规约由蓝图设计判断命中，义务挂到承担它的设计对象契约实体上，施工单位的 Plan 定落点细节与验证方式；设计模式由蓝图设计选型，
  角色落到承担它的实体，Plan 按下篇落实结构。
  知识判断在受其影响的设计之前形成。新增、删除或修改知识时，通用机制无需增加域名、编号、文件名或特例。
- **声明不是应用**：知识应用决定须投影为契约实体（`must` / `pattern_roles`）并有可指认落点；回显名称、anchor 指回声明表自己都不算。
- **Demo 样板义务**：本仓维护者保证样板结构有效、类型边界正确，能演示和测试完整知识链；验证发现样板有真实问题时按实际所有权修复并加回归。
  真实目标仓负责把三类知识修正和扩展为自身事实。适配模型按演进主题与质量判据从目标仓证据起步，不照搬 Demo 正文；依赖相同的设计模式
  可作底稿改写；演进知识条目只写主题与问题，起步后的扩充归目标维护者。

## 4. 验收

- **设计闭合**：确定性、作者、verifier与行为测试分工明确；忽略/误解/略写/编造/跳步有发现者和恢复路径，合法未知题材可用，判据能分正误。实现符合目标与关键设计分别核，绿测不抵消偏离。
- **证据分层**：结构/确定性、独立语义和真实行为分别结论；独审核对象绑定、报告结构及真实语义。构造稿仅用于确定性自检和诊断，正式审查效果按TEST取证；真实CLI限用户启动的里程碑，评分由用户确认。
- **实际范围**：核本轮目标加原能力保持，不删事实/改范围/降要求求绿。缺陷与归因分开，模型波动和历史反复风险按[TEST§6](test/TEST.md#6-评价)观察与后续获准验证，不直接堆叠功能，也不据不确定性豁免可靠性差距。

## 5. 维护预算与分级复核

预算用于发现实现走偏、补丁叠加、被替代旧机制未退出和废弃内容残留，不限制功能的正向实现；不删正常功能、必要测试或说明来凑预算，
也不只改预算把问题变绿。阈值和判定原则只在本节维护。

**计量范围（唯一来源，用户裁定）**：只计 `extensions/` 中交付的实现与指令内容，排除 `knowledge/`、`skills/story/scripts/adapters/`
和安装器的升级演进记录 `skills/story-adaptation/reference/upgrade-changes.md`；安装器 `skills/story-adaptation/` 的其余部分计入。依赖、缓存和
适配现场等运行态不计；`test/`、`tools/` 的维护脚本、测试和文档不计，方案不另设预算域；执行批次不重置预算包起点或累计值，实际映射写Plan。有效行剥离注释/空行的算法由现有计量函数维护。

| 触点 | 必须带到当前工作中的内容 |
|---|---|
| 制定/修改方案 | 能力目标、新旧职责替换、退出范围；计量基线、预计新增量、旧机制退出清单与预计删除量、实施峰值与完成总量；先推演正常路径与异常，再估量 |
| 拆步实施/交接 | 引用本节；给本包新承担者、被替换旧内容及保留能力，写明每步对需求预算的预计增减 |
| 预算报告/超限 | 实际差额、所需复核动作与本节入口；先查实现与方案 |
| 评审/收口 | 核实际 diff 与消费者：有没有更简单完整的实现、旧内容是否真退、是否干扰正常功能 |

新增说明承担什么职责，删除说明由谁接替；移动、格式变化和重复记账不算净减；阶段分项只用于定位，不通过拆步骤重置预算。

**分级比例** `R = 本次累计实际新增实现量 / 初始批准的新增实现预算`。新增包括替换旧实现所写的新实现，旧机制删除量另核；各指标同口径分别计算，
方案指定主要判定指标。纯删除或预算为零时不算百分比；未预算的新实现先由 reviewer 核必要性、确定正预算与适用起点。

| 比例 | 必须采取的动作 | 推进条件 |
|---|---|---|
| R≤100% | 按方案实现并正常评审 | 仍做功能、质量与退场检查 |
| 100%＜R≤125% | 维护实施者自查重复实现、未退旧机制、范围扩大和方案漏算，记录差额与原因 | 可继续 |
| 125%＜R≤150% | 自查后交方案制定者或其指定 reviewer 确认，同时审实现与方案有无更简单完整的替代 | reviewer 具名确认后继续 |
| R＞150% | reviewer 整体反思实现与方案，形成保留/替换/预算调整建议 | 人工确认后继续，reviewer 不能代替 |

需确认时仍可做收敛性修正、删除、必要验证和准备评审材料；未确认前不扩大实现、不宣告完成、不进入下一实施包。确认记录写入该需求的方案、
评审或预算记录，注明范围、额度、理由与确认角色；初始预算与累计变化保留，连续小幅改签不能规避 150% 人工确认。完成时同时核功能质量、
实际新增、旧机制退出与最终总量：预算以内但旧实现未退出不能完成；超预算但必要合理的按上表权限调整。§3 的质量要求不能通过增加预算豁免。

**统计与检查**：计量只用 `python test/scripts/budget_report.py`（只读；`--package <id>` 出包维度，`--out` 存证据），不另写计量脚本。它按类型、模块、文件、
文件状态、提交与责任项给出固定指标，交回和评审用指标名引用：`endpoint` 是基线到对象一次差分的 G/X，**整版判定用它**，对照台账 `release.control_g`；
`invested` 是逐提交累计，**包的 R 分子用包起点以来的它**，分母是台账 `packages[].approved_g`，不因改签重置；`churn`（invested−endpoint）、
`relocated`（移动或改缩进）、X 的来源（退出上一正式版保留行或本版新增行）与 `peak` 只用于定位与解释。`control` 只报告 R 档位、缺失的具名确认
与各类型对台账的差额，不拦提交；必要性、替代方案与旧路径退出仍由 reviewer 按本节判断。基线不在对象的 first-parent 链上（如合并进来的第二父链）时
只采用 `endpoint`，`series`/`invested`/`churn`/`peak` 置空并列出未执行的检查；包起点必须在链上，否则报前置不成立。`test_mechanism_budget.py` 检查分类总量对台账生效上限
（进行中看 interim_ceiling，closed 看 target）及 release/packages 字段，测试通过不代表分级复核已做。历史额度与确认见台账文件头注释。

## 6. framework 接入

输入是 Maison 的已验证发布件（zip），版本与构建身份看其中 `framework/RELEASE-MANIFEST.json`。
`python test/scripts/check_framework_drift.py` 比较 main 与 demo 接入的版本：退出 0 相同，1 不同，2 读取失败。

1. demo 先干净：`git status --porcelain -- demo` 为空。
2. 把发布件解压到 demo 根，替换 `demo/framework/`；用 `git diff --stat -- demo/framework` 核改动面与发布件的 `MIGRATION.md` 相符。
3. 三组本地定制（§2，文件清单见维护操作§2）被发布件覆盖时，在新文件上重新加回定制内容，不整文件回退到旧版；上游已带同义内容的那组不再加回。
4. 在 demo 根按 [framework-init](demo/framework/skills/project/framework-init/SKILL.md) 做 UPDATE（S1–S4），物化清单按本轮实际选择。
5. 宿主入口由 Framework 按已装 Extension 的 manifest 原生物化：UPDATE 后跑
   `node demo/doc/extensions/skills/story-adaptation/scripts/entries.mjs --project-root demo --action check`，核入口文件与原生渲染一致、
   每个扩展 Skill 的入口都在；不一致按它点名的项处理，不手改入口文件。
6. 装置同步：根 `.opencode/agent/verifier.md` 逐字节复制自 `demo/.opencode/agent/verifier.md`。
7. 验证：demo 下 `cd framework/harness && npm test`；`check_framework_drift.py` 结果与本次接入一致；按 [TEST §5](test/TEST.md) 跑与改动相关的离线回归。
8. 提交 demo，并在 [test/EVOLUTION.md](test/EVOLUTION.md) 登记发布件版本、source_commit、定制处理与验证结果。

失败时用 git 查看并还原 demo；framework 自身的缺陷报回上游。

## 7. Extension 安装与发布

同一个安装函数 `test/scripts/publish_to_demo.py` 服务两种目标，顺序固定：宿主入口写前核（只读）→ 整体替换目标 `doc/extensions` →
撤下已核的旧入口、Framework 原生物化宿主入口并写后核。入口的核与物化只有一份实现，即扩展里的
`skills/story-adaptation/scripts/entries.mjs`，对外 adapt 用的也是它：待装的扩展先用目标的 Framework 原生加载器核 manifest 与全部登记引用；
入口文件去掉已装旧版的扩展段后须与 Framework 的渲染逐字相同，已装旧版登记的入口须与旧发布源相同才撤下，要物化的 Skill 入口位置上
不能有无归属的文件；不成立就停在写之前。物化中途失败时按前后字节报出已写、已删的入口与原始错误；共用目录的宿主互相改写（Framework
已知限制）留在结果的 warnings 里。

- **测试**：只装一次性 template，由 `run_multi_case.py` 按 TEST §1.2 装配，离线检查用的 template 按 TEST §5 现建。测试不写 demo；
  需求产物回流到维护仓 `doc/features/`。
- **版本号**：新版本第一次改动 `extensions/` 的提交就把 `manifest.yaml` 的 `version` 升到新版本号。
- **正式发布**：前置是用户已决定发布本版本、demo 干净。

  ```powershell
  python test/scripts/publish_to_demo.py --source extensions --target demo --dry-run   # 看计划
  python test/scripts/publish_to_demo.py --source extensions --target demo             # 退出 0 = 已安装
  ```

  验证 `git status -- demo` 的改动只在 `demo/doc/extensions/`、Framework 物化的扩展 Skill 入口与入口文件，再核 demo 扩展与开发源同源（打印 `True`）：

  ```powershell
  python -c @"
  import sys
  from pathlib import Path
  sys.path.insert(0, 'test/scripts')
  import publish_to_demo as p
  src, dst = Path('extensions'), Path('demo/doc/extensions')
  files = p.enumerate_source(src)
  print(files == p.enumerate_source(dst) and all((src / f).read_bytes() == (dst / f).read_bytes() for f in files))
  "@
  ```

  然后跑 `python test/scripts/check_failure_modes.py`（缺省检查 demo）。发布提交带上 demo、`doc/release/<版本>.md` 与更新后的
  [README](README.md)，并在 EVOLUTION 登记。提交前核：本版增量里使用者可见的每项变化都已反映在 README 的当前描述里
  （命令、能力、产物、入口、安装），与发布版本一致；README 只写当前状态，版本变化只写在本版发布说明。
- **失败**：退出 2 是输入读取、git 前置或宿主入口写前核不成立，目标没写；退出 1 是写入或物化中途失败，结果 JSON 列出实际完成项。用 git 查看并还原 demo，
  修好后从同一源重装。
- **对外升级**：其他仓的安装与升级用 demo 里已装的发布版 adapt（`demo/doc/extensions/skills/story-adaptation/`）。
